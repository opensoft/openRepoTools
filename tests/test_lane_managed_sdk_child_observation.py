# SPDX-License-Identifier: Apache-2.0
"""Native-child observation producer and ACK contract tests.

The frozen runner contract has an observation *producer* boundary.  The
current SDK snapshot may not implement it yet; in that case these offline
tests fail at the explicit missing seam instead of skipping or claiming
support.  Sol may select an isolated snapshot when coordinating temporary
collection policy, but this test module has no opt-in environment gate.

The harness below is intentionally different from the manual persistence
cases in ``test_lane_managed_native_worker_boundaries.py``.  It drives the
existing private runner path with one fake SDK client, one native ledger, and
the real hook/event join:

``PreToolUse(Agent) -> SubagentStart -> TaskStarted -> parent Result ->
TaskNotification``

No test constructs a ``native-child-observation`` frame.  The observation sink
only receives frames emitted by the SDK producer seam and returns the frozen
ACK, so a passing test cannot be mistaken for selected-runtime capability.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

import lane_managed_sdk as sdk
from test_lane_managed_sdk import (
    FakeHookMatcher,
    _native_agent_post,
    _native_agent_pre,
    _native_start,
    _native_task_notification,
    _native_task_started,
)
from test_lane_managed_sdk_admission_ipc import (
    EOF as ADMISSION_EOF,
    FakeProcess,
    QueueBridge,
    cancel,
)


SESSION = "11111111-1111-4111-8111-111111111111"
RUNNER = "incarnation-1"
LINEAGE = "lineage-1"
INVOCATION = "invocation-A"
LAUNCH_TOOL = "launch-A"
AGENT = "agent-A"
TASK = "task-A"

DEFINITION = {
    "description": "A configured reviewer",
    "prompt": "Read the requested code.",
    "tools": ["Read", "Grep"],
    "model": "sonnet",
    "effort": "high",
    "permissionMode": "default",
}

CONTEXT = {
    "owner_generation": 7,
    "lineage_id": LINEAGE,
    "lineage_generation": 3,
    "runner_incarnation": RUNNER,
}


@dataclass
class _FakeAgentDefinition:
    """The SDK-shaped definition object used only by the fake module."""

    description: str
    prompt: str
    tools: list[str]
    model: str
    effort: str
    permissionMode: str


def _spec(tmp_path):
    return sdk.RunnerSpec(
        profile="team-a",
        participant="coordinator",
        participant_id="coordinator",
        session_id=SESSION,
        resume=True,
        model="sonnet",
        permission_mode="default",
        worktree=tmp_path,
        account_email="fake@example.invalid",
        supported_models=("sonnet",),
        read_only=True,
        read_only_tools=("Read", "Grep"),
        startup_deadline=1,
        operation_deadline=1,
        fingerprint={
            "lineage_context": copy.deepcopy(CONTEXT),
            "lineage_claim": {
                "claim_id": "claim-1",
                "session_id": SESSION,
                "workspace": str(tmp_path),
            },
            "trusted_definitions": {"reviewer": copy.deepcopy(DEFINITION)},
        },
    )


def _admission_ack(admission: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "accepted": True,
        **{
            key: admission[key]
            for key in sdk._ADMISSION_ACK_FIELDS
        },
    }


def _observation_ack(frame: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact ACK for a frame emitted by the SDK producer seam."""

    observation = frame["observation"]
    child = observation["child"]
    child_run_input = {
        "source_identity": observation["source_identity"],
        **{
            key: child[key]
            for key in (
                "admission_id",
                "tool_use_id",
                "agent_id",
                "task_id",
                "lineage_incarnation",
                "start_watermark",
            )
        },
    }
    return {
        "recorded": True,
        "observation_id": observation["observation_id"],
        "observation_digest": sdk._native_full_digest(observation),
        "child_run_id": sdk._native_full_digest(child_run_input),
        "observation_watermark": observation["observation_watermark"],
    }


class _ObservationSink:
    """Controller-side callback double for the frozen private seam.

    This object never creates an observation.  It records only what the SDK
    producer publishes, and can hold, fail, cancel, or await channel closure
    before returning the exact controller ACK.
    """

    def __init__(self, mode: str = "ack"):
        self.mode = mode
        self.frames: list[dict[str, Any]] = []
        self.called = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def __call__(self, frame: Mapping[str, Any]) -> dict[str, Any]:
        self.frames.append(copy.deepcopy(dict(frame)))
        self.called.set()
        if self.mode == "pending":
            await self.release.wait()
        elif self.mode == "error":
            raise sdk.SdkAdapterError(
                "loader-failed", "test controller observation persistence failed"
            )
        elif self.mode == "cancel":
            self.cancelled.set()
            raise asyncio.CancelledError()
        elif self.mode == "eof":
            try:
                await self.release.wait()
            finally:
                self.cancelled.set()
            raise sdk.SdkAdapterError(
                "loader-failed", "observation callback channel reached EOF"
            )
        return _observation_ack(frame)


class _LifecycleClient:
    """One fake client that emits the measured native child lifecycle."""

    STOP = object()

    def __init__(self, options):
        self.options = options
        self.events: asyncio.Queue[Any] = asyncio.Queue()
        self.calls: list[tuple[Any, ...]] = []
        self.event_order: list[str] = []

    async def connect(self, prompt=None):
        self.calls.append(("connect", prompt))
        assert prompt is None
        await self.events.put(
            {
                "type": "system",
                "subtype": "init",
                "session_id": SESSION,
                "account": {"email": "fake@example.invalid"},
                "current_permission_mode": "default",
                "session_state": "idle",
                "model": "sonnet",
                "models": ["sonnet"],
            }
        )

    async def receive_messages(self):
        self.calls.append(("receive_messages",))
        while True:
            event = await self.events.get()
            if event is self.STOP:
                return
            yield event

    async def query(self, payload):
        self.calls.append(("query", payload))
        hooks = self.options.hooks
        pre_hook = hooks["PreToolUse"][0].hooks[0]
        start_hook = hooks["SubagentStart"][0].hooks[0]
        post_hook = hooks["PostToolUse"][0].hooks[0]

        # The actual hook path creates/adopts the durable admission.  No child
        # row or observation is supplied by this test.
        pre = _native_agent_pre(LAUNCH_TOOL, agent_type="reviewer")
        pre["tool_input"]["description"] = DEFINITION["description"]
        pre["tool_input"]["prompt"] = DEFINITION["prompt"]
        assert await pre_hook(pre, LAUNCH_TOOL, {"signal": None}) == {}
        assert await start_hook(
            _native_start(AGENT, agent_type="reviewer"),
            None,
            {"signal": None},
        ) == {}
        self.event_order.append("subagent-start")

        self.event_order.append("task-started")
        await self.events.put(
            _native_task_started(
                TASK,
                "task-start-A",
                tool_use_id=LAUNCH_TOOL,
                task_type="local_agent",
            )
        )

        # The parent Result arrives before the known child's terminal
        # notification.  The result is therefore not a complete drain proof.
        self.event_order.append("parent-result")
        await self.events.put(
            {
                "type": "result",
                "subtype": "success",
                "session_id": SESSION,
                "message_id": INVOCATION,
                "sequence": 5,
                "is_error": False,
            }
        )
        assert await post_hook(
            _native_agent_post(pre),
            LAUNCH_TOOL,
            {"signal": None},
        ) == {}

        self.event_order.append("task-notification")
        terminal = _native_task_notification(
            TASK,
            "task-terminal-A",
            status="completed",
            tool_use_id=LAUNCH_TOOL,
        )
        terminal["sequence"] = 6
        await self.events.put(terminal)

    async def disconnect(self):
        self.calls.append(("disconnect",))
        await self.events.put(self.STOP)


@dataclass
class _HeldRunner:
    adapter: Any
    runner_task: asyncio.Task[Any]
    runner_bridge: Any
    adapter_bridge: Any
    client: _LifecycleClient
    sink: _ObservationSink
    observed: Any
    send_error: BaseException | None


@asynccontextmanager
async def run_held_runner(monkeypatch, tmp_path, *, sink: _ObservationSink):
    """Run one fake held runner through the real SDK/ledger hook path.

    The only future dependency is the frozen adapter method
    ``bind_native_child_observation``.  If it is missing, the explicit
    assertion below fails rather than substituting a manual frame or a second
    guessed API.
    """

    runner_bridge, adapter_bridge = QueueBridge(), QueueBridge()
    runner_bridge.outgoing = adapter_bridge.incoming
    adapter_bridge.outgoing = runner_bridge.incoming
    configured = _spec(tmp_path)
    clients: list[_LifecycleClient] = []

    def client_factory(options):
        client = _LifecycleClient(options)
        clients.append(client)
        return client

    # The internal test harness deliberately uses the SDK-shaped module path
    # (not ``client_factory``) so drive_client installs its real NativeLineageLedger
    # and guard hooks before the fake client emits lifecycle events.
    fake_sdk = SimpleNamespace(
        __name__="lane_managed_internal_child_observation_test_sdk",
        ClaudeSDKClient=client_factory,
        ClaudeAgentOptions=SimpleNamespace,
        AgentDefinition=_FakeAgentDefinition,
        HookMatcher=FakeHookMatcher,
    )

    async def persist_admission(admission):
        return _admission_ack(admission)

    adapter = sdk.SdkRunnerAdapter(
        lambda _spec: FakeProcess(),
        strict_process_group=False,
    )
    adapter.bind_native_admission(persist_admission)
    adapter.bind_native_invocation(
        lambda participant_id, session_id, runner_instance_id, message_id: {
            "bound": True,
            "participant_id": participant_id,
            "session_id": session_id,
            "runner_instance_id": runner_instance_id,
            "message_id": message_id,
        }
    )
    binder = getattr(adapter, "bind_native_child_observation", None)
    assert callable(
        binder
    ), "SDK producer seam is missing: bind_native_child_observation"
    binder(sink)

    bridges = iter((adapter_bridge, runner_bridge))
    monkeypatch.setattr(
        sdk,
        "_BoundedJsonLines",
        lambda *args, **kwargs: next(bridges),
    )
    monkeypatch.setattr(sdk.os, "environ", dict(sdk.os.environ))
    monkeypatch.setattr(
        sdk,
        "_process_evidence",
        lambda: {
            "process_group_owned": True,
            "process_start_token": "fake-only",
        },
    )

    async def runner():
        first = await runner_bridge.read()
        return await sdk._runner_async(
            first,
            _test_harness=sdk._internal_test_harness(fake_sdk),
        )

    runner_task = asyncio.create_task(runner())
    send_error: BaseException | None = None
    try:
        await asyncio.wait_for(adapter.open("coordinator", configured), 2)
        connection = adapter._connections["coordinator"]
        await asyncio.wait_for(adapter.release("coordinator"), 1)
        try:
            await asyncio.wait_for(
                adapter.send("coordinator", INVOCATION, "inspect this fake child"),
                1,
            )
        except BaseException as exc:  # future ACK failure is asserted by caller
            send_error = exc
        await asyncio.wait_for(sink.called.wait(), 1)
        yield _HeldRunner(
            adapter=adapter,
            runner_task=runner_task,
            runner_bridge=runner_bridge,
            adapter_bridge=adapter_bridge,
            client=clients[0],
            sink=sink,
            # The supervisor's continuous reader is the authoritative capture
            # of emitted control/error frames; no separate synthetic event
            # list is maintained by the test.
            observed=connection.history,
            send_error=send_error,
        )
    finally:
        sink.release.set()
        for connection in list(adapter._connections.values()):
            await connection.close()
        await cancel(runner_task)


def _reservation_binding() -> dict[str, Any]:
    """Build only the pre-existing terminal-reservation wire shape."""

    value = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "reservation_version": 1,
        "reservation_id": "reservation-B",
        "operation_id": "operation-1",
        "owner_generation": CONTEXT["owner_generation"],
        "daemon_id": "daemon-1",
        "participant_id": "coordinator",
        "session_id": SESSION,
        "runner_incarnation": RUNNER,
        "lineage_id": LINEAGE,
        "lineage_generation": CONTEXT["lineage_generation"],
        "prior_invocation_id": INVOCATION,
        "next_invocation_id": "invocation-B",
        "prior_mailbox_id": INVOCATION,
        "next_mailbox_id": "invocation-B",
        "prior_watermark": 1,
        "definitions_digest": "1" * 64,
        "permissions_digest": "2" * 64,
        "claim_digest": "3" * 64,
    }
    value["binding_digest"] = sdk._native_full_digest(value)
    return value


async def _wait_for_observed_error(events: list[dict[str, Any]]) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + 1
    while asyncio.get_running_loop().time() < deadline:
        error = next(
            (
                event
                for event in list(events)
                if event.get("type") == "adapter-error"
            ),
            None,
        )
        if error is not None:
            return error
        await asyncio.sleep(0)
    raise AssertionError("future observation failure was not reported")


def test_native_child_observation_is_emitted_from_joined_lifecycle(tmp_path, monkeypatch):
    async def scenario():
        sink = _ObservationSink()
        async with run_held_runner(monkeypatch, tmp_path, sink=sink) as held:
            await asyncio.wait_for(sink.called.wait(), 1)
            assert len(sink.frames) == 1
            assert held.client.event_order == [
                "subagent-start",
                "task-started",
                "parent-result",
                "task-notification",
            ]
            # Producer output, rather than any caller-supplied observation,
            # is the only input accepted by the sink.
            assert sink.frames[0]["type"] == "native-child-observation"

    asyncio.run(scenario())


def test_pending_observation_ack_keeps_prepare_busy_without_seal_or_reservation(
    tmp_path, monkeypatch
):
    async def scenario():
        sink = _ObservationSink("pending")
        async with run_held_runner(monkeypatch, tmp_path, sink=sink) as held:
            connection = held.adapter._connections["coordinator"]
            with pytest.raises(sdk.SdkAdapterError) as caught:
                await held.adapter.prepare_invocation(
                    "coordinator",
                    _reservation_binding(),
                    deadline=0.2,
                )
            assert caught.value.code == "busy"
            assert connection.reservation is None
            assert connection._native_send_started is False
            assert not any(
                event.get("type") == "prepare-invocation-ack"
                for event in held.observed
            )
            sink.release.set()

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["error", "cancel", "eof"])
def test_observation_ack_failure_poisoned_without_silent_drop(
    tmp_path, monkeypatch, mode
):
    async def scenario():
        sink = _ObservationSink(mode)
        async with run_held_runner(monkeypatch, tmp_path, sink=sink) as held:
            assert len(sink.frames) == 1
            assert sink.frames[0]["type"] == "native-child-observation"
            assert held.adapter._connections["coordinator"].reservation is None
            if mode == "cancel":
                assert sink.cancelled.is_set()
            elif mode == "eof":
                # EOF is injected on the runner-side authenticated callback
                # channel, not as a fabricated observation frame.  The
                # producer must retain the attempted frame while the pending
                # callback is cancelled/poisoned.
                await held.runner_bridge.incoming.put(ADMISSION_EOF)
                await asyncio.wait_for(sink.cancelled.wait(), 1)
            else:
                error = await _wait_for_observed_error(held.observed)
                assert error["code"] in {"loader-failed", "uncertain-effect"}
            # A failed/cancelled/EOF callback retains the emitted frame and
            # cannot turn the parent query's transport ACK into readiness.
            assert held.send_error is None or isinstance(
                held.send_error, sdk.SdkAdapterError
            )

    asyncio.run(scenario())


def test_observation_transport_identity_watermark_and_terminal_outcome(
    tmp_path, monkeypatch
):
    async def scenario():
        sink = _ObservationSink()
        async with run_held_runner(monkeypatch, tmp_path, sink=sink) as held:
            frame = sink.frames[0]
            assert set(frame) == {
                "type",
                "participant_id",
                "session_id",
                "runner_instance_id",
                "observation",
            }
            assert frame["participant_id"] == "coordinator"
            assert frame["session_id"] == SESSION
            assert frame["runner_instance_id"] == RUNNER
            observation = frame["observation"]
            assert set(observation) == {
                "schema_version",
                "architecture",
                "record_kind",
                "observation_id",
                "source_identity",
                "context_binding_digest",
                "claim_digest",
                "observation_watermark",
                "terminal_outcome",
                "child",
            }
            assert observation["schema_version"] == 2
            assert observation["architecture"] == "native-coordinator-lineage"
            assert observation["record_kind"] == "native-child-observation"
            assert observation["source_identity"] == {
                "owner_generation": CONTEXT["owner_generation"],
                "lineage_id": LINEAGE,
                "lineage_generation": CONTEXT["lineage_generation"],
                "session_uuid": SESSION,
                "runner_incarnation": RUNNER,
                "invocation_id": INVOCATION,
            }
            assert isinstance(observation["observation_watermark"], int)
            assert observation["observation_watermark"] > 0
            assert observation["terminal_outcome"] == "completed"
            child = observation["child"]
            assert set(child) == {
                "admission_id",
                "tool_use_id",
                "agent_id",
                "task_id",
                "parent_agent_id",
                "invocation_id",
                "lineage_incarnation",
                "trusted_definition_digest",
                "start_watermark",
                "task_start_event",
                "status",
                "terminal_watermark",
                "active_tool_ids",
                "uncertain_tool_ids",
                "unresolved_effect_ids",
            }
            assert child["agent_id"] == AGENT
            assert child["task_id"] == TASK
            assert child["tool_use_id"] == LAUNCH_TOOL
            assert child["invocation_id"] == INVOCATION
            assert child["status"] == "completed"
            assert child["terminal_watermark"] <= observation["observation_watermark"]
            assert child["task_start_event"]["watermark"] <= observation[
                "observation_watermark"
            ]
            assert held.send_error is None

    asyncio.run(scenario())


def test_terminal_child_after_parent_result_is_drained_before_prepare_seal(
    tmp_path, monkeypatch
):
    async def scenario():
        sink = _ObservationSink("pending")
        async with run_held_runner(monkeypatch, tmp_path, sink=sink) as held:
            # The producer is called only after the known terminal notification
            # even though the parent Result was read first.  While its ACK is
            # outstanding, A remains unsealed and B has no reservation.
            assert held.client.event_order[-2:] == [
                "parent-result",
                "task-notification",
            ]
            assert sink.frames[0]["observation"]["terminal_outcome"] == "completed"
            connection = held.adapter._connections["coordinator"]
            assert connection.reservation is None
            with pytest.raises(sdk.SdkAdapterError) as caught:
                await held.adapter.prepare_invocation(
                    "coordinator",
                    _reservation_binding(),
                    deadline=0.2,
                )
            assert caught.value.code == "busy"
            assert connection.reservation is None
            sink.release.set()

    asyncio.run(scenario())
