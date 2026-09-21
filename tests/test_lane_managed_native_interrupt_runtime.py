# SPDX-License-Identifier: Apache-2.0
"""Fake native coordinator interrupt send-boundary integration.

The durable intent, validation acknowledgement, SDK receipt, and lifecycle
facts are deliberately exercised as separate observations.  The test seam
uses the production controller/daemon/SDK IPC readers with bounded queues;
the fake client is never allowed to turn an acknowledgement into quiescence
or capability evidence.
"""

from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace

import pytest

import lane_managed_sdk as sdk
from lane_managed_controller import ControllerError
from test_lane_managed_coordinator_interrupt import _digest
from test_lane_managed_interrupt_integration import (
    admitted_interrupt,
    real_interrupt_authority,
)
from test_lane_managed_sdk_admission_ipc import FakeProcess, QueueBridge, cancel
from test_lane_managed_sdk import (
    FakeHookMatcher,
    MODEL,
    _native_admission_ack,
    _native_agent_pre,
    _native_definition,
    _native_start,
    _native_task_notification,
    _native_task_started,
)


def _validation_frame(intent, intent_digest, *, validation_id="validation-1"):
    return {
        "type": "coordinator-interrupt-validate",
        "participant_id": intent["participant_id"],
        "session_id": intent["session_id"],
        "runner_instance_id": intent["runner_instance_id"],
        "validation_id": validation_id,
        "interrupt_id": intent["interrupt"]["interrupt_id"],
        "intent_digest": intent_digest,
    }


def _validation_bridge(daemon, adapter, intent):
    """Route validation through the production daemon callback and IPC reader."""

    identity = {
        key: intent[key]
        for key in ("participant_id", "session_id", "runner_instance_id")
    }
    spec = sdk.RunnerSpec(
        session_id=identity["session_id"],
        participant_id="coordinator",
        account_email="fake@example.invalid",
        permission_mode="default",
        model="sonnet",
        supported_models=("sonnet",),
        operation_deadline=1,
        fingerprint={
            "lineage_context": {
                "owner_generation": intent["interrupt"]["owner_generation"],
                "lineage_id": intent["interrupt"]["lineage_id"],
                "lineage_generation": intent["interrupt"]["lineage_generation"],
                "runner_incarnation": identity["runner_instance_id"],
            }
        },
    )
    connection = sdk._RunnerConnection(
        "coordinator",
        spec,
        FakeProcess(),
        identity["runner_instance_id"],
        strict_process_group=False,
        coordinator_interrupt_intent=adapter.interrupt_intent,
        coordinator_interrupt_evidence=adapter.interrupt_evidence,
        coordinator_interrupt_validate=daemon._validate_coordinator_interrupt_callback,
    )
    supervisor, runner = QueueBridge(), QueueBridge()
    supervisor.incoming, supervisor.outgoing = runner.outgoing, runner.incoming
    connection.bridge = supervisor
    connection.started = connection.ready = True
    channel = sdk._NativeAdmissionIPC(runner, identity)
    controls = asyncio.Queue(maxsize=8)
    readers = (
        asyncio.create_task(connection._read_events()),
        asyncio.create_task(sdk._queue_controls(runner, controls, channel)),
    )
    return connection, channel, readers


def test_validate_send_is_after_durable_intent_and_does_not_mutate_store(
    tmp_path, managed_workspace
):
    """Validation is a fresh no-mutation check, not a second authorization."""

    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )

    async def scenario():
        intent = await admitted_interrupt(daemon, adapter, lineage)
        before_missing = copy.deepcopy(store.read_json("controller.json"))
        missing = _validation_frame(intent, "0" * 64, validation_id="before-intent")
        with pytest.raises(ControllerError) as caught:
            daemon.controller.validate_coordinator_interrupt_send(missing)
        assert caught.value.code in {"unknown", "invalid", "stale-generation"}
        assert store.read_json("controller.json") == before_missing

        await adapter.interrupt_intent(intent)
        record = store.read_json("controller.json")["coordinator_interrupts"][
            intent["interrupt"]["interrupt_id"]
        ]
        digest = record["digest"]
        frame = _validation_frame(intent, digest)
        before_validate = copy.deepcopy(store.read_json("controller.json"))
        acknowledgement = daemon.controller.validate_coordinator_interrupt_send(frame)
        assert acknowledgement == {
            "validated": True,
            "validation_id": "validation-1",
            "interrupt_id": "interrupt-1",
            "intent_digest": digest,
        }
        assert store.read_json("controller.json") == before_validate
        # The validation reply is evidence for the one SDK send boundary; it
        # does not itself append a runtime receipt or child/tool fact.
        assert record.get("runtime_ack") is None
        assert record.get("evidence", {}) == {}

    asyncio.run(scenario())


def test_validation_rechecks_identity_and_does_not_accept_cross_id_digest(
    tmp_path, managed_workspace
):
    """A fresh validation cannot be satisfied by an old intent or ID."""

    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )

    async def scenario():
        intent = await admitted_interrupt(daemon, adapter, lineage)
        await adapter.interrupt_intent(intent)
        digest = store.read_json("controller.json")["coordinator_interrupts"][
            "interrupt-1"
        ]["digest"]

        wrong_digest = _validation_frame(intent, _digest({"wrong": True}))
        with pytest.raises(ControllerError) as digest_error:
            daemon.controller.validate_coordinator_interrupt_send(wrong_digest)
        assert digest_error.value.code in {"invalid", "stale-generation"}

        wrong_interrupt = _validation_frame(
            {**intent, "interrupt": {**intent["interrupt"], "interrupt_id": "other"}},
            digest,
            validation_id="validation-2",
        )
        with pytest.raises(ControllerError) as id_error:
            daemon.controller.validate_coordinator_interrupt_send(wrong_interrupt)
        assert id_error.value.code in {"unknown", "invalid", "busy", "stale-generation"}

        valid = _validation_frame(intent, digest, validation_id="validation-3")
        assert daemon.controller.validate_coordinator_interrupt_send(valid)[
            "validated"
        ] is True

    asyncio.run(scenario())


@pytest.mark.parametrize("takeover", [False, True])
def test_real_ipc_validation_roundtrip_is_read_only_and_owner_bound(
    tmp_path, managed_workspace, takeover
):
    """The validation waiter crosses real IPC and cannot outlive ownership."""

    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )

    async def scenario():
        intent = await admitted_interrupt(daemon, adapter, lineage)
        connection, channel, readers = _validation_bridge(daemon, adapter, intent)
        try:
            intent_ack = await asyncio.wait_for(
                channel.request_coordinator_interrupt_intent(intent), 2
            )
            assert intent_ack["authorize_send"] is True
            before_validation = copy.deepcopy(store.read_json("controller.json"))
            validation = _validation_frame(
                intent,
                store.read_json("controller.json")["coordinator_interrupts"][
                    "interrupt-1"
                ]["digest"],
            )
            if takeover:
                owner = store.read_owner()
                owner["daemon_id"] = "replacement-daemon"
                store.write_json("owner.json", owner)
                acknowledgement = await asyncio.wait_for(
                    channel.request_coordinator_interrupt_validation(validation), 2
                )
                assert acknowledgement["validated"] is False
                assert acknowledgement["code"] == "ownership-conflict"
            else:
                acknowledgement = await asyncio.wait_for(
                    channel.request_coordinator_interrupt_validation(validation), 2
                )
                assert acknowledgement == {
                    "validated": True,
                    "validation_id": "validation-1",
                    "interrupt_id": "interrupt-1",
                    "intent_digest": validation["intent_digest"],
                }
            # Validate is a no-mutation check in either branch: a takeover
            # refuses the waiter, while a positive reply does not append a
            # receipt/evidence fact or synthesize readiness.
            assert store.read_json("controller.json") == before_validation
            assert channel.coordinator_interrupt_validation_pending == {}
        finally:
            await cancel(*readers)

    asyncio.run(scenario())


def test_real_ipc_validation_untyped_callback_exception_stays_loader_failed(
    tmp_path, managed_workspace
):
    """Unexpected validation callback errors remain sanitized at the IPC edge."""

    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )

    async def scenario():
        intent = await admitted_interrupt(daemon, adapter, lineage)
        connection, channel, readers = _validation_bridge(daemon, adapter, intent)

        async def untyped_failure(_frame):
            raise RuntimeError("synthetic callback failure")

        connection.coordinator_interrupt_validate = untyped_failure
        try:
            intent_ack = await asyncio.wait_for(
                channel.request_coordinator_interrupt_intent(intent), 2
            )
            assert intent_ack["authorize_send"] is True
            validation = _validation_frame(
                intent,
                store.read_json("controller.json")["coordinator_interrupts"][
                    "interrupt-1"
                ]["digest"],
            )
            acknowledgement = await asyncio.wait_for(
                channel.request_coordinator_interrupt_validation(validation), 2
            )
            assert acknowledgement["validated"] is False
            assert acknowledgement["code"] == "loader-failed"
        finally:
            await cancel(*readers)

    asyncio.run(scenario())


def test_drive_client_coordinator_interrupt_joins_readonly_child_and_records_independent_facts():
    """The native send path fences a real joined child before one SDK call."""

    session_id = "11111111-1111-4111-8111-111111111111"
    invocation_id = "mailbox-message-1"
    launch_tool_id = "launch-tool-1"
    task_id = "actual-task-1"
    agent_id = "agent-1"
    task_started_seen = asyncio.Event()
    result_seen = asyncio.Event()
    terminal_seen = asyncio.Event()
    clients = []
    emitted = []
    protocol_order = []

    class AgentDefinition:
        def __init__(self, **values):
            self.values = values

    class CoordinatorIPC:
        def __init__(self):
            self.intent_frames = []
            self.validation_frames = []
            self.evidence_frames = []

        async def request_coordinator_interrupt_intent(self, frame):
            self.intent_frames.append(copy.deepcopy(frame))
            protocol_order.append("intent")
            interrupt_id = frame["interrupt"]["interrupt_id"]
            return {
                "recorded": True,
                "authorize_send": True,
                "interrupt_id": interrupt_id,
            }

        async def request_coordinator_interrupt_validation(self, frame):
            self.validation_frames.append(copy.deepcopy(frame))
            protocol_order.append("validation")
            return {
                "validated": True,
                "validation_id": frame["validation_id"],
                "interrupt_id": frame["interrupt_id"],
                "intent_digest": frame["intent_digest"],
            }

        async def request_coordinator_interrupt_evidence(self, frame):
            self.evidence_frames.append(copy.deepcopy(frame))
            evidence = frame["evidence"]
            return {
                "recorded": True,
                "evidence_id": evidence["evidence_id"],
                "interrupt_id": evidence["interrupt_id"],
            }

    ipc = CoordinatorIPC()

    async def emit(event):
        emitted.append(copy.deepcopy(event))
        if event.get("subtype") == "task_started":
            task_started_seen.set()
        if event.get("type") == "result":
            result_seen.set()
        if event.get("subtype") == "task_notification":
            terminal_seen.set()

    class Client:
        _STOP = object()

        def __init__(self, options):
            self.options = options
            self.events = asyncio.Queue()
            self.calls = []
            clients.append(self)

        async def connect(self, prompt=None):
            self.calls.append(("connect", prompt))
            assert prompt is None

        async def get_server_info(self):
            self.calls.append(("get_server_info",))
            return {
                "type": "system",
                "subtype": "init",
                "account": {"email": "target@example.invalid"},
                "current_permission_mode": "default",
                "session_state": "idle",
                "models": [MODEL],
            }

        async def receive_messages(self):
            self.calls.append(("receive_messages",))
            while True:
                event = await self.events.get()
                if event is self._STOP:
                    return
                yield event

        async def query(self, _prompt):
            self.calls.append(("query", _prompt))
            hooks = self.options["hooks"]
            pre_agent = hooks["PreToolUse"][0].hooks[0]
            subagent_start = hooks["SubagentStart"][0].hooks[0]
            pre = _native_agent_pre(launch_tool_id)
            assert await pre_agent(pre, launch_tool_id, {"signal": None}) == {}
            assert await subagent_start(
                _native_start(agent_id), None, {"signal": None}
            ) == {}
            await self.events.put(
                _native_task_started(task_id, "task-start-uuid", tool_use_id=launch_tool_id)
            )
            await asyncio.wait_for(task_started_seen.wait(), 0.5)
            await self.events.put({
                "type": "result",
                "subtype": "success",
                "duration_ms": 1,
                "duration_api_ms": 1,
                "is_error": False,
                "num_turns": 1,
                "session_id": session_id,
                "uuid": "parent-result-uuid",
                "terminal_reason": "completed",
                "origin": None,
            })
            await asyncio.wait_for(result_seen.wait(), 0.5)

        async def interrupt(self):
            self.calls.append(("interrupt",))
            await self.events.put(
                _native_task_notification(
                    task_id,
                    "task-terminal-uuid",
                    status="stopped",
                    tool_use_id=launch_tool_id,
                )
            )
            await asyncio.wait_for(terminal_seen.wait(), 0.5)
            protocol_order.append("interrupt")

        async def disconnect(self):
            self.calls.append(("disconnect",))
            await self.events.put(self._STOP)

    async def persist_admission(admission):
        return _native_admission_ack(admission)

    async def scenario():
        controls = asyncio.Queue()
        await controls.put({"operation": "release", "request_id": "release-1"})
        await controls.put({
            "operation": "query",
            "request_id": "query-1",
            "message_id": invocation_id,
            "payload_ref": "inspect native child",
        })
        await controls.put({
            "operation": "coordinator-interrupt",
            "request_id": "interrupt-request-1",
            "payload_ref": {
                "operation_id": "operation-1",
                "interrupt_id": "interrupt-1",
                "fence_epoch": 1,
                "capability_digest": "a" * 64,
                "request_epoch_id": "request-epoch-1",
            },
        })
        await controls.put({"operation": "shutdown", "request_id": "shutdown-1"})

        result = await sdk.drive_client(
            sdk.RunnerSpec(
                session_id=session_id,
                account_email="target@example.invalid",
                permission_mode="default",
                model=MODEL,
                supported_models=(MODEL,),
                read_only=True,
                read_only_tools=("Read",),
                fingerprint={
                    "lineage_context": {
                        "owner_generation": 1,
                        "lineage_id": "lineage-runtime-1",
                        "lineage_generation": 1,
                        "runner_incarnation": "runner-runtime-1",
                    },
                    "trusted_definitions": {
                        "writer": _native_definition(tools=("Read",)),
                    },
                },
                startup_deadline=0.5,
                operation_deadline=0.5,
            ),
            controls=controls,
            emit=emit,
            sdk_module=SimpleNamespace(
                __name__="lane_managed_test_sdk",
                ClaudeSDKClient=Client,
                HookMatcher=FakeHookMatcher,
                AgentDefinition=AgentDefinition,
            ),
            persist_admission=persist_admission,
            coordinator_interrupt_ipc=ipc,
            coordinator_interrupt_identity={
                "participant_id": "coordinator",
                "session_id": session_id,
                "runner_instance_id": "runner-runtime-1",
            },
        )

        assert result["ok"] is True
        assert protocol_order == ["intent", "validation", "interrupt"]
        assert len(clients) == 1
        assert [call for call in clients[0].calls if call[0] == "interrupt"] == [
            ("interrupt",)
        ]
        assert len(ipc.intent_frames) == 1
        assert len(ipc.validation_frames) == 1
        intent = ipc.intent_frames[0]
        assert set(intent["interrupt"]) == {
            "interrupt_id",
            "operation_id",
            "owner_generation",
            "lineage_id",
            "lineage_generation",
            "invocation_id",
            "fence_epoch",
            "roster_identity_digest",
            "roster_seal_watermark",
            "capability_digest",
            "request_epoch_id",
            "request_entry_watermark",
            "roster",
        }
        roster = intent["interrupt"]["roster"]
        assert roster["pending_admission_ids"] == []
        assert roster["pending_task_ids"] == []
        assert len(roster["children"]) == 1
        child = roster["children"][0]
        assert child["agent_id"] == agent_id
        assert child["task_id"] == task_id
        assert child["tool_use_id"] == launch_tool_id
        assert child["status"] == "active"
        assert child["active_tool_ids"] == []
        evidence_by_kind = {
            frame["evidence"]["kind"]: frame for frame in ipc.evidence_frames
        }
        assert "runtime-ack" in evidence_by_kind
        assert "request-observation" in evidence_by_kind
        runtime = evidence_by_kind["runtime-ack"]["evidence"]
        request_observation = evidence_by_kind["request-observation"]["evidence"]
        assert runtime["data"] == {
            "accepted": True,
            "ack_kind": "accepted-interrupt",
        }
        assert request_observation["data"]["new_requests"] is None
        assert request_observation["data"]["observable"] is False
        assert runtime["evidence_id"] != request_observation["evidence_id"]
        assert "member-terminal" in evidence_by_kind
        accepted = next(
            event
            for event in emitted
            if event.get("type") == "coordinator-interrupt-ack"
            and event.get("accepted") is True
        )
        assert accepted["interrupt_id"] == "interrupt-1"
        assert "quiescent" not in accepted
        assert result["lineage"]["children"][0]["task_id"] == task_id

    asyncio.run(scenario())


def test_raw_interrupt_control_requires_coordinator_authority_before_sdk_call(
    tmp_path,
):
    """Native lineage makes legacy interrupt/cancel controls fail closed.

    This drives the real SDK control loop.  The lineage fingerprint marks the
    runner as native while the coordinator IPC arguments are deliberately
    absent, so neither legacy spelling may reach ``client.interrupt``.
    """

    session_id = "11111111-1111-4111-8111-111111111111"
    clients = []

    class Client:
        _STOP = object()

        def __init__(self, _options):
            self.calls = []
            self.events = asyncio.Queue()
            clients.append(self)

        async def connect(self, prompt=None):
            self.calls.append(("connect", prompt))
            assert prompt is None

        async def get_server_info(self):
            self.calls.append(("get_server_info",))
            return {
                "type": "system",
                "subtype": "init",
                "account": {"email": "target@example.invalid"},
                "current_permission_mode": "default",
                "session_state": "idle",
                "models": ["sonnet"],
            }

        async def receive_messages(self):
            self.calls.append(("receive_messages",))
            while True:
                event = await self.events.get()
                if event is self._STOP:
                    return
                yield event

        async def interrupt(self):
            self.calls.append(("interrupt",))

        async def disconnect(self):
            self.calls.append(("disconnect",))
            await self.events.put(self._STOP)

    async def scenario():
        controls = asyncio.Queue()
        await controls.put({"operation": "interrupt", "request_id": "raw-1"})
        await controls.put({"operation": "cancel", "request_id": "raw-2"})
        await controls.put({"operation": "shutdown", "request_id": "shutdown-1"})
        emitted = []
        result = await sdk.drive_client(
            sdk.RunnerSpec(
                session_id=session_id,
                account_email="target@example.invalid",
                permission_mode="default",
                model="sonnet",
                supported_models=("sonnet",),
                fingerprint={
                    "lineage_context": {
                        "owner_generation": 1,
                        "lineage_id": "lineage-raw-control",
                        "lineage_generation": 1,
                        "runner_incarnation": "runner-raw-control",
                    },
                },
                startup_deadline=0.5,
                operation_deadline=0.5,
            ),
            controls=controls,
            emit=emitted.append,
            client_factory=Client,
            # No coordinator_interrupt_ipc or identity is passed on purpose.
        )
        assert result["ok"] is True
        assert len(clients) == 1
        assert not [call for call in clients[0].calls if call[0] == "interrupt"]
        refusals = [
            event
            for event in emitted
            if event.get("type") == "adapter-error"
            and event.get("request_id") in {"raw-1", "raw-2"}
        ]
        assert {event["request_id"] for event in refusals} == {"raw-1", "raw-2"}
        assert all(event["code"] == "unsupported" for event in refusals)
        assert all("durable coordinator authorization" in event["message"] for event in refusals)
        assert not any(event.get("type") == "interrupt-ack" for event in emitted)

    asyncio.run(scenario())
