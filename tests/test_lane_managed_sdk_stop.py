# SPDX-License-Identifier: Apache-2.0
"""Focused SDK native-stop control and transport tests.

These tests use the explicit nonofficial SDK seam.  They exercise the runner
control path and IPC acknowledgement handling without importing, probing, or
authenticating an official runtime.
"""

from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace

import pytest

import lane_managed_sdk as sdk


SESSION = "11111111-1111-4111-8111-111111111111"
IDENTITY = {
    "participant_id": "coordinator",
    "session_id": SESSION,
    "runner_instance_id": "runner-1",
}


class QueueBridge:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.outgoing = asyncio.Queue()

    async def read(self):
        return await self.incoming.get()

    async def write(self, value):
        await self.outgoing.put(copy.deepcopy(value))


class FakeProcess:
    pid = None
    stdin = stdout = stderr = None

    @staticmethod
    def poll():
        return None


class FakeHookMatcher:
    def __init__(self, matcher=None, hooks=None, timeout=None):
        self.matcher = matcher
        self.hooks = list(hooks or ())
        self.timeout = timeout


def _spec() -> sdk.RunnerSpec:
    return sdk.RunnerSpec(
        session_id=SESSION,
        account_email="target@example.invalid",
        permission_mode="default",
        model="sonnet",
        supported_models=("sonnet",),
        fingerprint={
            "lineage_context": {
                "owner_generation": 1,
                "lineage_id": "lineage-1",
                "runner_incarnation": IDENTITY["runner_instance_id"],
            },
        },
        startup_deadline=0.5,
        operation_deadline=0.1,
    )


def _intent() -> dict:
    return {
        "type": "native-stop-intent",
        **IDENTITY,
        "stop": {
            "stop_id": "stop-1",
            "owner_generation": 1,
            "lineage_id": "lineage-1",
            "invocation_id": "message-1",
            "admission_id": "admission-1",
            "tool_use_id": "tool-1",
            "agent_id": "agent-1",
            "task_id": "actual-task-1",
            "lineage_incarnation": 1,
            "trusted_definition_digest": "a" * 64,
            "observed_watermark": 3,
            "observation": {
                "status": "active",
                "task_terminal": False,
                "start_watermark": 1,
                "task_start_event": {
                    "event_uuid": "task-start-1",
                    "watermark": 2,
                    "task_type": "local_agent",
                },
                "active_tool_ids": [],
                "uncertain_tool_ids": [],
                "unresolved_effect_ids": [],
            },
        },
    }


def _runtime_evidence(intent: dict) -> dict:
    stop = intent["stop"]
    return {
        "type": "native-stop-evidence",
        **IDENTITY,
        "evidence": {
            "evidence_id": "stop-1:runtime-ack",
            "stop_id": stop["stop_id"],
            "kind": "runtime-ack",
            "agent_id": stop["agent_id"],
            "task_id": stop["task_id"],
            "lineage_incarnation": stop["lineage_incarnation"],
            "observed_watermark": stop["observed_watermark"],
            "accepted": True,
            "ack_kind": "accepted-stop",
        },
    }


class FakeStopIPC:
    def __init__(self, *, authorize=True, evidence_recorded=True):
        self.authorize = authorize
        self.evidence_recorded = evidence_recorded
        self.intent_frames = []
        self.evidence_frames = []

    async def request_native_stop_intent(self, frame):
        self.intent_frames.append(copy.deepcopy(frame))
        return {
            "recorded": True,
            "authorize_send": self.authorize,
            "stop_id": frame["stop"]["stop_id"],
        }

    async def request_native_stop_evidence(self, frame):
        self.evidence_frames.append(copy.deepcopy(frame))
        evidence = frame["evidence"]
        return {
            "recorded": self.evidence_recorded,
            "evidence_id": evidence["evidence_id"],
            "stop_id": evidence["stop_id"],
        }


def _fake_sdk(holder, stop_behavior="success"):
    class Client:
        def __init__(self, options):
            self.options = options
            self.calls = []
            self.closed = asyncio.Event()
            holder.append(self)

        async def connect(self, prompt=None):
            assert prompt is None

        async def get_server_info(self):
            return {
                "type": "system",
                "subtype": "init",
                "account": {"email": "target@example.invalid"},
                "current_permission_mode": "default",
                "session_state": "idle",
                "models": ["sonnet"],
            }

        async def receive_messages(self):
            await self.closed.wait()
            if False:  # keep this an async generator
                yield {}

        async def query(self, prompt):
            self.calls.append(("query", prompt))

        async def stop_task(self, task_id):
            self.calls.append(("stop_task", task_id))
            if stop_behavior == "timeout":
                raise asyncio.TimeoutError
            if stop_behavior == "disconnect":
                raise ConnectionError("runner disconnected")

        async def disconnect(self):
            self.calls.append(("disconnect",))
            self.closed.set()

    return SimpleNamespace(
        __name__="lane_managed_test_sdk",
        ClaudeSDKClient=Client,
        HookMatcher=FakeHookMatcher,
    )


def _install_stop_seams(monkeypatch, attempted, *, revalidate=True):
    intent = _intent()
    runtime = _runtime_evidence(intent)
    monkeypatch.setattr(
        sdk.NativeLineageLedger,
        "prepare_native_stop",
        lambda self, selection, *, participant_id, runner_instance_id: copy.deepcopy(intent),
    )
    monkeypatch.setattr(
        sdk.NativeLineageLedger,
        "mark_native_stop_intent_persisted",
        lambda self, stop_id, acknowledgement: None,
    )
    monkeypatch.setattr(
        sdk.NativeLineageLedger,
        "revalidate_native_stop",
        lambda self, stop_id, prepared: revalidate,
    )

    def mark_attempted(self, stop_id):
        attempted.append(stop_id)

    monkeypatch.setattr(sdk.NativeLineageLedger, "mark_native_stop_attempted", mark_attempted)
    monkeypatch.setattr(
        sdk.NativeLineageLedger,
        "native_stop_runtime_evidence",
        lambda self, stop_id: copy.deepcopy(runtime),
    )
    monkeypatch.setattr(
        sdk.NativeLineageLedger,
        "native_stop_pending_terminal_evidence",
        lambda self, stop_id: None,
    )


async def _run_flow(
    monkeypatch,
    *,
    authorize=True,
    evidence_recorded=True,
    stop_behavior="success",
    revalidate=True,
):
    attempted = []
    _install_stop_seams(monkeypatch, attempted, revalidate=revalidate)
    clients = []
    ipc = FakeStopIPC(authorize=authorize, evidence_recorded=evidence_recorded)
    emitted = []
    controls = asyncio.Queue()
    for command in (
        {"operation": "release", "request_id": "release-1"},
        {
            "operation": "query",
            "request_id": "query-1",
            "message_id": "message-1",
            "payload_ref": "inspect",
        },
        {
            "operation": "native-stop",
            "request_id": "stop-1",
            "payload_ref": {"task_id": "actual-task-1", "stop_id": "stop-1"},
        },
        {"operation": "shutdown", "request_id": "shutdown-1"},
    ):
        await controls.put(command)

    result = await sdk.drive_client(
        _spec(),
        controls=controls,
        emit=emitted.append,
        sdk_module=_fake_sdk(clients, stop_behavior),
        native_stop_ipc=ipc,
        native_stop_identity=IDENTITY,
    )
    return result, clients[0], ipc, attempted, emitted


def test_stop_task_demuxes_native_ack_and_preserves_actual_task_id():
    async def scenario():
        connection = sdk._RunnerConnection(
            "coordinator",
            _spec(),
            FakeProcess(),
            IDENTITY["runner_instance_id"],
            strict_process_group=False,
        )
        connection.bridge = QueueBridge()
        connection.start_reader()
        try:
            pending = asyncio.create_task(
                connection.stop_task("actual-task-1", stop_id="stop-1")
            )
            request = await asyncio.wait_for(connection.bridge.outgoing.get(), 1)
            assert request["payload_ref"] == {
                "task_id": "actual-task-1",
                "stop_id": "stop-1",
            }
            await connection.bridge.incoming.put({
                **IDENTITY,
                "type": "native-stop-ack",
                "request_id": request["request_id"],
                "stop_id": "stop-1",
                "task_id": "actual-task-1",
                "accepted": True,
            })
            result = await asyncio.wait_for(pending, 1)
            assert result["task_id"] == "actual-task-1"
            assert result["stop_id"] == "stop-1"
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_adapter_binds_native_stop_callbacks_before_open():
    adapter = sdk.SdkRunnerAdapter()

    async def intent(_frame):
        return {}

    async def evidence(_frame):
        return {}

    adapter.bind_native_stop(intent, evidence)
    assert adapter._native_stop_intent is intent
    assert adapter._native_stop_evidence is evidence
    with pytest.raises(sdk.SdkAdapterError, match="callable"):
        adapter.bind_native_stop(None, evidence)


def test_authorize_false_makes_zero_sdk_stop_calls(monkeypatch):
    result, client, ipc, attempted, emitted = asyncio.run(
        _run_flow(monkeypatch, authorize=False)
    )
    assert result["ok"] is True
    assert attempted == []
    assert [call for call in client.calls if call[0] == "stop_task"] == []
    assert ipc.evidence_frames == []
    refusal = next(item for item in emitted if item.get("type") == "native-stop-ack")
    assert refusal["accepted"] is False
    assert refusal["authorize_send"] is False


def test_successful_stop_uses_actual_task_id_and_persists_runtime_ack(monkeypatch):
    result, client, ipc, attempted, emitted = asyncio.run(_run_flow(monkeypatch))
    assert result["ok"] is True
    assert attempted == ["stop-1"]
    assert [call for call in client.calls if call[0] == "stop_task"] == [
        ("stop_task", "actual-task-1"),
    ]
    assert len(ipc.intent_frames) == 1
    assert len(ipc.evidence_frames) == 1
    assert ipc.evidence_frames[0]["evidence"]["kind"] == "runtime-ack"
    accepted = next(item for item in emitted if item.get("type") == "native-stop-ack")
    assert accepted["accepted"] is True
    assert accepted["ack_kind"] == "accepted-stop"


@pytest.mark.parametrize("stop_behavior", ["timeout", "disconnect"])
def test_sdk_stop_failure_has_no_automatic_retry(monkeypatch, stop_behavior):
    result, client, ipc, attempted, emitted = asyncio.run(
        _run_flow(monkeypatch, stop_behavior=stop_behavior)
    )
    assert result["ok"] is True
    assert attempted == ["stop-1"]
    assert [call for call in client.calls if call[0] == "stop_task"] == [
        ("stop_task", "actual-task-1"),
    ]
    assert ipc.evidence_frames == []
    assert any(item.get("type") == "adapter-error" for item in emitted)


def test_post_authorization_revalidation_refusal_makes_zero_sdk_stop_calls(monkeypatch):
    result, client, ipc, attempted, emitted = asyncio.run(
        _run_flow(monkeypatch, revalidate=False)
    )
    assert result["ok"] is True
    assert attempted == []
    assert [call for call in client.calls if call[0] == "stop_task"] == []
    assert ipc.evidence_frames == []
    assert any(item.get("type") == "adapter-error" for item in emitted)


@pytest.mark.parametrize("kind", ["intent", "evidence"])
def test_changed_retry_at_pending_cap_fails_closed_without_scheduling_refusal(kind):
    async def scenario():
        connection = sdk._RunnerConnection(
            "coordinator",
            _spec(),
            FakeProcess(),
            IDENTITY["runner_instance_id"],
            strict_process_group=False,
        )
        connection.bridge = QueueBridge()
        tasks = []
        try:
            for _ in range(sdk.MAX_NATIVE_CHILD_RECORDS):
                task = asyncio.create_task(asyncio.Event().wait())
                tasks.append(task)
                connection._stop_tasks.add(task)
            if kind == "intent":
                original = {
                    "type": "native-stop-intent",
                    **IDENTITY,
                    "stop": {"stop_id": "stop-1", "task_id": "task-1"},
                }
                changed = copy.deepcopy(original)
                changed["stop"]["task_id"] = "task-2"
                connection._stop_intent_frames["stop-1"] = original
                connection._stop_intent_ids.add("stop-1")
                with pytest.raises(sdk.SdkAdapterError):
                    connection._start_native_stop_intent(changed)
            else:
                original = {
                    "type": "native-stop-evidence",
                    **IDENTITY,
                    "evidence": {
                        "evidence_id": "evidence-1",
                        "stop_id": "stop-1",
                        "task_id": "task-1",
                    },
                }
                changed = copy.deepcopy(original)
                changed["evidence"]["task_id"] = "task-2"
                connection._stop_evidence_frames["evidence-1"] = original
                connection._stop_evidence_ids.add("evidence-1")
                with pytest.raises(sdk.SdkAdapterError):
                    connection._start_native_stop_evidence(changed)
            assert connection.bridge.outgoing.empty()
            assert len(connection._stop_tasks) == sdk.MAX_NATIVE_CHILD_RECORDS
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await connection.close()

    asyncio.run(scenario())


def test_unrecorded_runtime_evidence_surfaces_failure_without_resending_stop(monkeypatch):
    result, client, ipc, attempted, emitted = asyncio.run(
        _run_flow(monkeypatch, evidence_recorded=False)
    )
    assert result["ok"] is True
    assert attempted == ["stop-1"]
    assert [call for call in client.calls if call[0] == "stop_task"] == [
        ("stop_task", "actual-task-1"),
    ]
    assert len(ipc.evidence_frames) == 1
    assert not any(
        item.get("type") == "native-stop-ack" and item.get("accepted") is True
        for item in emitted
    )
    assert any(item.get("type") == "adapter-error" for item in emitted)


def test_ipc_rejects_unrecorded_evidence_ack():
    async def scenario():
        bridge = QueueBridge()
        channel = sdk._NativeAdmissionIPC(bridge, IDENTITY)
        controls = asyncio.Queue()
        reader = asyncio.create_task(sdk._queue_controls(bridge, controls, channel))
        frame = {
            "type": "native-stop-evidence",
            **IDENTITY,
            "evidence": {
                "evidence_id": "stop-1:runtime-ack",
                "stop_id": "stop-1",
            },
        }
        pending = asyncio.create_task(channel.request_native_stop_evidence(frame))
        try:
            await asyncio.wait_for(bridge.outgoing.get(), 1)
            await bridge.incoming.put({
                "operation": "native-stop-evidence-ack",
                **IDENTITY,
                "evidence_id": "stop-1:runtime-ack",
                "stop_id": "stop-1",
                "ack": {
                    "recorded": False,
                    "evidence_id": "stop-1:runtime-ack",
                    "stop_id": "stop-1",
                },
            })
            with pytest.raises(sdk.SdkAdapterError):
                await asyncio.wait_for(pending, 1)
        finally:
            if not pending.done():
                pending.cancel()
            reader.cancel()
            await asyncio.gather(pending, reader, return_exceptions=True)

    asyncio.run(scenario())
