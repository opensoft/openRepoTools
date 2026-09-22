# SPDX-License-Identifier: Apache-2.0
"""Test-first native-child observation and dispatch boundaries.

These tests stay on one connected authority chain:

``ManagedStateStore -> ManagedDaemon -> ManagedController -> NativeLineageLedger``

The ledger receives the same admission acknowledgement that the real daemon
callback persists, then joins the actual ``TaskStarted``/``SubagentStart``
identity.  The observation callback is the private authenticated seam from
``runner-evidence.md``.  The frame cases below are explicitly manual
ingestion-contract cases: they verify the frozen persistence/validation shape
but are not evidence that a selected SDK emits this frame.  The current
implementation is expected to be red until the frozen child-observation API
lands.

The six-stage coordinator ctx/restart fixture is intentionally deferred.  No
legacy independent-worker roster, child SDK connection, accepted parent send,
or synthetic restart flag is used here.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Mapping

import pytest

from lane_managed_controller import ControllerError, MailboxEntry, ManagedController, _digest
from lane_managed_sdk import (
    NativeLineageLedger,
    _event_to_mapping,
)
from test_lane_managed_coordinator_interrupt import (
    _fenced_authority,
    _roster as _interrupt_roster,
)
from test_lane_managed_interrupt_integration import real_interrupt_authority
from test_lane_managed_sdk import (
    _begin_native,
    _native_agent_pre,
    _native_definition,
    _native_hooks,
    _native_start,
    _native_stop,
    _native_task_notification,
    _native_task_progress,
    _native_task_started,
)


NATIVE_AGENT = "agent-native-1"
NATIVE_TASK = "task-native-1"
NATIVE_TOOL = "tool-native-1"
NATIVE_INVOCATION = "invocation-1"
NATIVE_EVENT_UUID = "task-event-native-1"
NATIVE_OBSERVATION = "observation-native-1"


class _ObservationAdapter:
    """Add only the frozen child-observation callback to the real adapter.

    The wrapped adapter remains the daemon's runtime object.  It has no
    ``send``/query implementation, so an unsupported child route cannot be
    mistaken for a parent prompt or a fake child transport.
    """

    def __init__(self, delegate):
        self._delegate = delegate
        self.admission_callback = None
        self.observation_callback = None

    def bind_native_admission(self, callback):
        self.admission_callback = callback
        return self._delegate.bind_native_admission(callback)

    def bind_native_child_observation(self, callback):
        self.observation_callback = callback

    def __getattr__(self, name):
        return getattr(self._delegate, name)


def _native_definitions():
    # Read-only tools keep the projection eligible for the existing SDK
    # roster rules without fabricating an effect inventory.
    return {"writer": _native_definition(tools=("Read",))}


def _context_binding_digest(context: Mapping[str, object]) -> str:
    value = copy.deepcopy(dict(context))
    value.pop("fenced", None)
    return _digest(value)


def _child_record(snapshot: Mapping[str, object]) -> Mapping[str, object]:
    children = snapshot["children"]
    assert isinstance(children, list)
    matches = [item for item in children if item.get("agent_id") == NATIVE_AGENT]
    assert len(matches) == 1
    return matches[0]


def _child_projection(snapshot: Mapping[str, object], *, status: str = "active"):
    """Map the SDK's joined child record to the frozen exact 15-field shape."""

    child = _child_record(snapshot)
    task_events = [
        item
        for item in child["task_events"]
        if item.get("kind") == "taskstarted"
    ]
    assert len(task_events) == 1
    task_start = task_events[0]
    incarnation = child["lineage_incarnation"]
    assert isinstance(incarnation, Mapping)
    admission = next(
        item for item in snapshot["admissions"]
        if item["tool_use_id"] == NATIVE_TOOL
    )
    terminal_watermark = None
    if status != "active":
        terminal_events = [
            item
            for item in child["task_events"]
            if item.get("status") in {
                "completed", "complete", "success", "done",
                "stopped", "failed", "failure", "error",
                "cancelled", "canceled", "terminated", "killed",
            }
        ]
        if terminal_events:
            terminal_watermark = terminal_events[-1]["watermark"]
        else:
            # A SubagentStop-only observation has no TaskNotification fact;
            # the ledger's stop watermark is the only bounded terminal fact.
            terminal_watermark = child.get("stop_watermark")
        assert isinstance(terminal_watermark, int)
    return {
        "admission_id": admission["admission_id"],
        "tool_use_id": child["tool_use_id"],
        "agent_id": child["agent_id"],
        "task_id": child["task_id"],
        "parent_agent_id": child["parent_links"].get("parent_agent_id"),
        "invocation_id": child["parent_links"]["invocation_id"],
        "lineage_incarnation": incarnation["number"],
        "trusted_definition_digest": admission["trusted_definition_digest"],
        "start_watermark": incarnation["start_watermark"],
        "task_start_event": {
            "event_uuid": task_start["event_uuid"],
            "watermark": task_start["watermark"],
            "task_type": task_start["task_type"],
        },
        "status": status,
        "terminal_watermark": terminal_watermark,
        "active_tool_ids": [],
        "uncertain_tool_ids": [],
        "unresolved_effect_ids": [],
    }


def _observation(
    *,
    context: Mapping[str, object],
    lineage,
    snapshot: Mapping[str, object],
    observation_id: str = NATIVE_OBSERVATION,
    terminal_outcome=None,
    status: str = "active",
):
    source_identity = {
        "owner_generation": lineage.owner_generation,
        "lineage_id": lineage.lineage_id,
        "lineage_generation": lineage.lineage_generation,
        "session_uuid": lineage.session_uuid,
        "runner_incarnation": context["runner_incarnation"],
        "invocation_id": context["invocation_id"],
    }
    child = _child_projection(snapshot, status=status)
    return {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-child-observation",
        "observation_id": observation_id,
        "source_identity": source_identity,
        "context_binding_digest": _context_binding_digest(context),
        "claim_digest": _digest(lineage.workspace_claim),
        "observation_watermark": snapshot["event_cursor"],
        "terminal_outcome": terminal_outcome,
        "child": child,
    }


def _child_run_id(observation: Mapping[str, object]) -> str:
    child = observation["child"]
    return _digest({
        "source_identity": observation["source_identity"],
        "admission_id": child["admission_id"],
        "tool_use_id": child["tool_use_id"],
        "agent_id": child["agent_id"],
        "task_id": child["task_id"],
        "lineage_incarnation": child["lineage_incarnation"],
        "start_watermark": child["start_watermark"],
    })


def _observation_frame(
    observation: Mapping[str, object], context: Mapping[str, object]
) -> dict[str, object]:
    """Build the exact private frame for an ingestion-contract test.

    This helper intentionally constructs a manual frame.  It must never be
    described as a selected SDK producer or runtime capability.
    """

    return {
        "type": "native-child-observation",
        "participant_id": "coordinator",
        "session_id": context["lineage"]["session_uuid"],
        "runner_instance_id": context["runner_incarnation"],
        "observation": copy.deepcopy(dict(observation)),
    }


def _status_child_projection(
    observation: Mapping[str, object], *, lifecycle_status: str
) -> dict[str, object]:
    """Return the exact frozen ``status.native_children`` row."""

    child = observation["child"]
    return {
        "child_run_id": _child_run_id(observation),
        "source_identity": copy.deepcopy(observation["source_identity"]),
        "admission_id": child["admission_id"],
        "tool_use_id": child["tool_use_id"],
        "agent_id": child["agent_id"],
        "task_id": child["task_id"],
        "lineage_incarnation": child["lineage_incarnation"],
        "trusted_definition_digest": child["trusted_definition_digest"],
        "observation_id": observation["observation_id"],
        "observation_watermark": observation["observation_watermark"],
        "lifecycle_status": lifecycle_status,
        "terminal_outcome": observation["terminal_outcome"],
        "restoration": None,
    }


def _fenced_contract_observation(
    context: Mapping[str, object],
    lineage: Mapping[str, object],
    admission: Mapping[str, object],
    *,
    observation_id: str,
    child_status: str,
    terminal_watermark: int | None,
    terminal_outcome: str | None,
    observation_watermark: int,
) -> dict[str, object]:
    """Build a bounded manual frame body for archive/seal refusal tests."""

    child = _interrupt_roster(
        admission,
        child_status=child_status,
        terminal_watermark=terminal_watermark,
    )["children"][0]
    child["unresolved_effect_ids"] = []
    child["active_tool_ids"] = []
    return {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-child-observation",
        "observation_id": observation_id,
        "source_identity": {
            "owner_generation": lineage["owner_generation"],
            "lineage_id": lineage["lineage_id"],
            "lineage_generation": lineage["lineage_generation"],
            "session_uuid": lineage["session_uuid"],
            "runner_incarnation": context["runner_incarnation"],
            "invocation_id": context["invocation_id"],
        },
        "context_binding_digest": _context_binding_digest(context),
        "claim_digest": _digest(context["lineage"]["workspace_claim"]),
        "observation_watermark": observation_watermark,
        "terminal_outcome": terminal_outcome,
        "child": child,
    }


def _complete_manual_source_binding(store, context):
    """Complete a synthetic released fixture; this is not runtime evidence.

    These fixtures already fixed their invocation before startup/mailbox
    binding existed. Public submit allocates a new ID, and startup preparation
    cannot retrofit the old operation after the fenced fixture begins swap.
    Retain the existing source and validate the completed snapshot on reload.
    """

    record = copy.deepcopy(store.read_json("controller.json"))
    sources = [
        item for item in record["operations"]
        if item["mode"] == "start" and item["phase"] == "released"
    ]
    assert len(sources) == 1
    source = sources[0]
    lineage = context["lineage"]
    assert source["generation"] == lineage["owner_generation"]
    assert "native_startup" not in source["metadata"]
    assert not any(
        item["message_id"] == context["invocation_id"]
        for item in record["mailboxes"]
    )
    source["metadata"]["native_startup"] = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "coordinator-startup",
        "participant_id": record["coordinator_id"],
        "session_id": lineage["session_uuid"],
        "runner_incarnation": context["runner_incarnation"],
        "lineage_id": lineage["lineage_id"],
        "lineage_generation": lineage["lineage_generation"],
        "lineage": copy.deepcopy(lineage),
        "definitions": copy.deepcopy(context["definitions"]),
        "invocation_id": context["invocation_id"],
        "invocation_bound": True,
    }
    record["mailboxes"].append(MailboxEntry(
        message_id=context["invocation_id"],
        request_id="manual-source-invocation",
        recipient_id=record["coordinator_id"],
        payload_ref="payload://manual-source-invocation",
        state="acknowledged",
        generation=source["generation"],
        operation_id=source["operation_id"],
        dispatch_attempt=1,
        runtime_ack={"message_id": context["invocation_id"], "accepted": True},
    ).to_dict())
    store.write_json("controller.json", record)
    reloaded = ManagedController(store)
    assert reloaded.status()["native_context"] == context
    resolved = reloaded._native_child_source_operation_locked(context)
    assert resolved.operation_id == source["operation_id"]
    assert store.read_json("controller.json") == record


async def _connected_joined_child(tmp_path, managed_workspace):
    """Build one real owner/controller/store plus one joined SDK child."""

    daemon, store, delegate, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )
    adapter = _ObservationAdapter(delegate)
    # ``real_interrupt_authority`` constructs the daemon before start.  Swap
    # only its injected adapter object so the daemon can bind the frozen
    # observation callback during its normal construction order.
    daemon.adapter = adapter
    await daemon.start()
    controller = daemon.controller
    definitions = _native_definitions()
    context = controller.register_native_context(
        lineage.owner_generation,
        lineage,
        "runner-1",
        NATIVE_INVOCATION,
        definitions,
        invocation_watermark=1,
    )
    _complete_manual_source_binding(store, context)
    assert callable(adapter.admission_callback)
    ledger = NativeLineageLedger(
        lineage.session_uuid,
        trusted_definitions=definitions,
        parent_read_only=True,
        lineage_claim=lineage.workspace_claim,
        lineage_context={
            "owner_generation": lineage.owner_generation,
            "lineage_id": lineage.lineage_id,
            "lineage_generation": lineage.lineage_generation,
            "runner_incarnation": "runner-1",
        },
        persist_admission=adapter.admission_callback,
    )
    _begin_native(ledger, NATIVE_INVOCATION)
    hooks, _evidence, hook_error = _native_hooks(ledger)
    assert await hooks["PreToolUse"][0].hooks[0](
        _native_agent_pre(NATIVE_TOOL), NATIVE_TOOL, {"signal": None}
    ) == {}
    assert hook_error == {}
    assert ledger.observe(_event_to_mapping(_native_task_started(
        NATIVE_TASK,
        NATIVE_EVENT_UUID,
        tool_use_id=NATIVE_TOOL,
    ))) is None
    assert await hooks["SubagentStart"][0].hooks[0](
        _native_start(NATIVE_AGENT), None, {"signal": None}
    ) == {}
    # A later correlated fact advances the observation cursor without
    # changing the actual TaskStarted-before-SubagentStart event order.
    assert ledger.observe(_event_to_mapping(_native_task_progress(
        NATIVE_TASK, "task-progress-native-1", tool_use_id=NATIVE_TOOL,
    ))) is None
    snapshot = ledger.snapshot()
    assert _child_record(snapshot)["task_id"] == NATIVE_TASK
    assert snapshot["event_cursor"] > _child_record(snapshot)["lineage_incarnation"]["start_watermark"]
    assert callable(adapter.observation_callback)
    return daemon, controller, store, adapter, lineage, context, ledger, snapshot


async def _persist_joined_observation(
    tmp_path, managed_workspace, *, observation_id=NATIVE_OBSERVATION
):
    values = await _connected_joined_child(tmp_path, managed_workspace)
    daemon, controller, store, adapter, lineage, context, ledger, snapshot = values
    observation = _observation(
        context=context,
        lineage=lineage,
        snapshot=snapshot,
        observation_id=observation_id,
    )
    frame = _observation_frame(observation, context)
    acknowledgement = await adapter.observation_callback(frame)
    return (
        daemon,
        controller,
        store,
        adapter,
        lineage,
        context,
        ledger,
        snapshot,
        observation,
        frame,
        acknowledgement,
    )


def test_ingestion_contract_manual_frame_persists_exact_ack_and_projection(
    tmp_path, managed_workspace
):
    """Manual frame ingestion only; this is not SDK producer evidence."""

    values = asyncio.run(_persist_joined_observation(tmp_path, managed_workspace))
    _daemon, _controller, store, _adapter, _lineage, _context, _ledger, _snapshot, observation, _frame, ack = values
    assert ack == {
        "recorded": True,
        "observation_id": observation["observation_id"],
        "observation_digest": _digest(observation),
        "child_run_id": _child_run_id(observation),
        "observation_watermark": observation["observation_watermark"],
    }
    record = store.read_json("controller.json")
    persisted = record["native_child_observations"][observation["observation_id"]]
    assert persisted["observation"] == observation
    assert persisted["observation_digest"] == ack["observation_digest"]
    assert persisted["child_run_id"] == ack["child_run_id"]
    assert persisted["source_operation_id"] == "released-1"
    assert persisted["ack"] == ack
    assert set(observation["child"]) == {
        "admission_id", "tool_use_id", "agent_id", "task_id",
        "parent_agent_id", "invocation_id", "lineage_incarnation",
        "trusted_definition_digest", "start_watermark", "task_start_event",
        "status", "terminal_watermark", "active_tool_ids",
        "uncertain_tool_ids", "unresolved_effect_ids",
    }


def test_ingestion_contract_manual_frame_reloads_and_projects_status_native_children(
    tmp_path, managed_workspace
):
    """The durable map reloads and exposes only the frozen status projection."""

    values = asyncio.run(_persist_joined_observation(tmp_path, managed_workspace))
    (
        _daemon,
        _controller,
        store,
        adapter,
        _lineage,
        _context,
        _ledger,
        _snapshot,
        observation,
        _frame,
        _ack,
    ) = values

    # This constructor reload is still an offline controller/store check.  It
    # does not open a runner or establish a producer/runtime capability.
    reloaded = ManagedController(store)
    status = reloaded.status()
    expected = _status_child_projection(observation, lifecycle_status="active")
    assert status["native_children"] == [expected]
    assert list(status["native_children"]) == sorted(
        status["native_children"], key=lambda item: item["child_run_id"]
    )
    assert set(status["native_children"][0]) == {
        "child_run_id",
        "source_identity",
        "admission_id",
        "tool_use_id",
        "agent_id",
        "task_id",
        "lineage_incarnation",
        "trusted_definition_digest",
        "observation_id",
        "observation_watermark",
        "lifecycle_status",
        "terminal_outcome",
        "restoration",
    }
    assert callable(adapter.observation_callback)


def test_ingestion_contract_manual_frame_retry_is_idempotent_and_content_conflict_refuses(
    tmp_path, managed_workspace
):
    """Manual ingestion contract: one ID cannot be overwritten or replayed."""

    values = asyncio.run(_persist_joined_observation(tmp_path, managed_workspace))
    _daemon, _controller, store, adapter, _lineage, _context, _ledger, _snapshot, observation, frame, ack = values
    before = store.read_json("controller.json")
    assert asyncio.run(adapter.observation_callback(frame)) == ack
    assert store.read_json("controller.json") == before

    changed = copy.deepcopy(frame)
    changed["observation"]["observation_watermark"] += 1
    with pytest.raises(Exception) as raised:
        asyncio.run(adapter.observation_callback(changed))
    assert raised.value.code == "invalid"
    assert store.read_json("controller.json") == before


def test_joined_native_target_uses_coordinator_mailbox_and_unsupported_route_does_not_query(
    tmp_path, managed_workspace
):
    """Future route contract; manual observation is not producer evidence."""

    values = asyncio.run(_persist_joined_observation(tmp_path, managed_workspace))
    _daemon, controller, _store, adapter, lineage, _context, _ledger, _snapshot, observation, _frame, _ack = values
    coordinator_id = controller.status()["coordinator_id"]
    entry = controller.submit(
        "known-native-child-message",
        NATIVE_AGENT,
        "payload://known-native-child",
        task_id=NATIVE_TASK,
        generation=lineage.owner_generation,
    )
    assert entry.state == "queued"
    assert entry.recipient_id == coordinator_id
    target = entry.metadata["native_target"]
    assert target["lineage_id"] == lineage.lineage_id
    assert target["agent_id"] == NATIVE_AGENT
    assert target["task_id"] == NATIVE_TASK
    assert target["lineage_incarnation"] == observation["child"]["lineage_incarnation"]
    assert entry.metadata["physical_recipient"]["participant_id"] == coordinator_id
    assert entry.metadata["physical_recipient"]["mailbox_id"] == entry.message_id
    assert entry.metadata["request_content_digest"]
    assert entry.metadata["routing_binding_digest"]

    # The wrapper deliberately has no native child route or generic sender.
    # The controller must preserve the pending entry and report unsupported;
    # it must not turn this into a parent query or accepted-send proof.
    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.dispatch_next(
            entry.operation_id,
            recipient_id=coordinator_id,
        ))
    assert raised.value.code == "unsupported"
    mailbox = next(
        item for item in controller.status()["mailboxes"]
        if item["message_id"] == entry.message_id
    )
    assert mailbox["state"] in {"queued", "unsupported"}
    assert not hasattr(adapter, "send")
    assert not hasattr(adapter, "query")


@pytest.mark.parametrize("start_offset", [
    pytest.param(-1, id="before-child-start"),
    pytest.param(0, id="equal-child-start"),
])
def test_ingestion_contract_manual_frame_rejects_lower_watermark_and_wrong_source_identity(
    tmp_path, managed_workspace, start_offset
):
    """Manual ingestion remains bound to the current child run/context."""

    values = asyncio.run(_persist_joined_observation(tmp_path, managed_workspace))
    _daemon, _controller, _store, adapter, _lineage, _context, _ledger, _snapshot, observation, frame, _ack = values
    before = _store.read_json("controller.json")

    stale = copy.deepcopy(frame)
    stale["observation"]["observation_id"] = "observation-stale-watermark"
    stale["observation"]["observation_watermark"] = (
        stale["observation"]["child"]["start_watermark"] + start_offset
    )
    with pytest.raises(Exception) as watermark_error:
        asyncio.run(adapter.observation_callback(stale))
    assert watermark_error.value.code in {"stale-generation", "invalid"}
    assert _store.read_json("controller.json") == before

    foreign = copy.deepcopy(frame)
    foreign["observation"]["observation_id"] = "observation-foreign-source"
    foreign["observation"]["source_identity"]["invocation_id"] = "other-invocation"
    with pytest.raises(Exception) as source_error:
        asyncio.run(adapter.observation_callback(foreign))
    assert source_error.value.code in {"ownership-conflict", "stale-generation", "invalid"}
    assert _store.read_json("controller.json") == before


@pytest.mark.parametrize(
    "malformation",
    [
        pytest.param("missing-child", id="missing-child"),
        pytest.param("extra-frame-field", id="extra-frame-field"),
        pytest.param("invalid-claim-digest", id="invalid-claim-digest"),
    ],
)
def test_ingestion_contract_manual_frame_rejects_malformed_without_mutation(
    tmp_path, managed_workspace, malformation
):
    """Malformed private frames refuse before durable observation mutation."""

    values = asyncio.run(_connected_joined_child(tmp_path, managed_workspace))
    (
        _daemon,
        _controller,
        store,
        adapter,
        _lineage,
        context,
        _ledger,
        snapshot,
    ) = values
    observation = _observation(
        context=context,
        lineage=_lineage,
        snapshot=snapshot,
        observation_id="observation-malformed",
    )
    frame = _observation_frame(observation, context)
    before = store.read_json("controller.json")

    if malformation == "missing-child":
        frame["observation"].pop("child")
    elif malformation == "extra-frame-field":
        frame["unexpected"] = "not-part-of-frozen-frame"
    else:
        frame["observation"]["claim_digest"] = "not-a-sha256"

    with pytest.raises(Exception) as raised:
        asyncio.run(adapter.observation_callback(frame))
    assert raised.value.code == "invalid"
    assert store.read_json("controller.json") == before


@pytest.mark.parametrize(
    "identity_field",
    [
        pytest.param("owner_generation", id="owner-generation"),
        pytest.param("lineage_id", id="lineage-id"),
        pytest.param("lineage_generation", id="lineage-generation"),
        pytest.param("session_uuid", id="session-uuid"),
        pytest.param("runner_incarnation", id="runner-incarnation"),
        pytest.param("invocation_id", id="invocation-id"),
    ],
)
def test_ingestion_contract_manual_frame_rejects_each_foreign_source_identity(
    tmp_path, managed_workspace, identity_field
):
    """Every frozen source-identity field remains bound to the current source."""

    values = asyncio.run(_connected_joined_child(tmp_path, managed_workspace))
    (
        _daemon,
        _controller,
        store,
        adapter,
        _lineage,
        context,
        _ledger,
        snapshot,
    ) = values
    observation = _observation(
        context=context,
        lineage=_lineage,
        snapshot=snapshot,
        observation_id="observation-foreign-" + identity_field,
    )
    frame = _observation_frame(observation, context)
    original = frame["observation"]["source_identity"][identity_field]
    frame["observation"]["source_identity"][identity_field] = (
        original + 1 if isinstance(original, int) else "foreign-" + str(original)
    )
    before = store.read_json("controller.json")

    with pytest.raises(Exception) as raised:
        asyncio.run(adapter.observation_callback(frame))
    assert raised.value.code in {"ownership-conflict", "stale-generation", "invalid"}
    assert store.read_json("controller.json") == before


@pytest.mark.parametrize(
    "transport_field",
    [
        pytest.param("participant_id", id="participant"),
        pytest.param("session_id", id="transport-session"),
        pytest.param("runner_instance_id", id="transport-runner"),
    ],
)
def test_ingestion_contract_manual_frame_rejects_foreign_transport_identity(
    tmp_path, managed_workspace, transport_field
):
    """The outer participant/session/runner tuple is independently bound."""

    values = asyncio.run(_connected_joined_child(tmp_path, managed_workspace))
    (
        _daemon,
        _controller,
        store,
        adapter,
        _lineage,
        context,
        _ledger,
        snapshot,
    ) = values
    observation = _observation(
        context=context,
        lineage=_lineage,
        snapshot=snapshot,
        observation_id="observation-foreign-transport-" + transport_field,
    )
    frame = _observation_frame(observation, context)
    frame[transport_field] = "foreign-" + transport_field
    before = store.read_json("controller.json")

    with pytest.raises(Exception) as raised:
        asyncio.run(adapter.observation_callback(frame))
    assert raised.value.code in {"ownership-conflict", "stale-generation", "invalid"}
    assert store.read_json("controller.json") == before


def test_ingestion_contract_manual_frame_refuses_over_capacity_without_eviction(
    tmp_path, managed_workspace
):
    """The 17th observation for one child run refuses; the first 16 remain."""

    values = asyncio.run(_connected_joined_child(tmp_path, managed_workspace))
    (
        _daemon,
        _controller,
        store,
        adapter,
        _lineage,
        context,
        _ledger,
        snapshot,
    ) = values
    base = _observation(
        context=context,
        lineage=_lineage,
        snapshot=snapshot,
        observation_id="observation-capacity-0",
    )
    for index in range(16):
        observation = copy.deepcopy(base)
        observation["observation_id"] = "observation-capacity-%d" % index
        observation["observation_watermark"] = base["observation_watermark"] + index
        frame = _observation_frame(observation, context)
        assert asyncio.run(adapter.observation_callback(frame))["recorded"] is True

    overflow = copy.deepcopy(base)
    overflow["observation_id"] = "observation-capacity-16"
    overflow["observation_watermark"] = base["observation_watermark"] + 16
    with pytest.raises(Exception) as raised:
        asyncio.run(adapter.observation_callback(_observation_frame(overflow, context)))
    assert raised.value.code == "busy"
    record = store.read_json("controller.json")
    assert set(record["native_child_observations"]) == {
        "observation-capacity-%d" % index for index in range(16)
    }


async def _persist_terminal_observation(
    tmp_path, managed_workspace, *, terminal_outcome: str
):
    """Create a manual contract frame after bounded local ledger evidence."""

    values = await _connected_joined_child(tmp_path, managed_workspace)
    daemon, controller, store, adapter, lineage, context, ledger, _snapshot = values
    if terminal_outcome == "unknown":
        event = _native_stop(
            NATIVE_AGENT,
            transcript="/tmp/native-child-unknown-terminal.jsonl",
        )
    else:
        event = _native_task_notification(
            NATIVE_TASK,
            "task-event-native-terminal-" + terminal_outcome,
            status=terminal_outcome,
            tool_use_id=NATIVE_TOOL,
        )
    assert ledger.observe(_event_to_mapping(event)) is None
    snapshot = ledger.snapshot()
    observation = _observation(
        context=context,
        lineage=lineage,
        snapshot=snapshot,
        observation_id="observation-terminal-" + terminal_outcome,
        terminal_outcome=terminal_outcome,
        status="completed" if terminal_outcome == "completed" else "stopped",
    )
    frame = _observation_frame(observation, context)
    acknowledgement = await adapter.observation_callback(frame)
    return (
        daemon,
        controller,
        store,
        adapter,
        lineage,
        context,
        ledger,
        snapshot,
        observation,
        frame,
        acknowledgement,
    )


@pytest.mark.parametrize("terminal_outcome", [
    "completed", "stopped", "failed", "cancelled", "unknown",
])
def test_ingestion_contract_manual_frame_retains_each_terminal_outcome(
    tmp_path, managed_workspace, terminal_outcome
):
    """Manual ingestion preserves terminal outcomes without claiming resume."""

    values = asyncio.run(
        _persist_terminal_observation(
            tmp_path,
            managed_workspace,
            terminal_outcome=terminal_outcome,
        )
    )
    (
        _daemon,
        _controller,
        store,
        _adapter,
        _lineage,
        _context,
        _ledger,
        _snapshot,
        observation,
        _frame,
        acknowledgement,
    ) = values
    assert acknowledgement["recorded"] is True
    persisted = store.read_json("controller.json")["native_child_observations"][
        observation["observation_id"]
    ]
    assert persisted["observation"]["terminal_outcome"] == terminal_outcome
    lifecycle_status = {
        "completed": "completed",
        "stopped": "stopped",
        "failed": "unresolved",
        "cancelled": "unresolved",
        "unknown": "unresolved",
    }[terminal_outcome]
    status_row = next(
        item
        for item in _controller.status()["native_children"]
        if item["child_run_id"] == _child_run_id(observation)
    )
    assert status_row == _status_child_projection(
        observation, lifecycle_status=lifecycle_status
    )
    if terminal_outcome != "completed":
        assert status_row["lifecycle_status"] != "completed"
        assert status_row["restoration"] is None


def test_ingestion_contract_fenced_active_observation_refuses_as_sealed(
    tmp_path,
):
    """A held/sealed source cannot accept a new active child observation."""

    controller, store, lineage, admission, context, _operation_id = _fenced_authority(
        tmp_path
    )
    _complete_manual_source_binding(store, context)
    observation = _fenced_contract_observation(
        context,
        lineage,
        admission,
        observation_id="observation-sealed-active",
        child_status="active",
        terminal_watermark=None,
        terminal_outcome=None,
        observation_watermark=10,
    )
    before = copy.deepcopy(store.documents["controller.json"])
    with pytest.raises(ControllerError) as raised:
        controller.persist_native_child_observation(
            observation["observation_id"],
            lineage["owner_generation"],
            observation,
            expected_daemon_id="daemon-test",
        )
    assert raised.value.code in {"busy", "stale-generation", "ownership-conflict"}
    assert store.documents["controller.json"] == before


def test_ingestion_contract_archived_source_refuses_terminal_observation(
    tmp_path,
):
    """Archiving a source seals its child history against later ingestion."""

    controller, store, lineage, admission, context, operation_id = _fenced_authority(
        tmp_path
    )
    archive = controller.archive_native_source(
        "archive-native-child-observation",
        operation_id,
        lineage["owner_generation"],
    )
    assert archive["archive_id"] == "archive-native-child-observation"
    observation = _fenced_contract_observation(
        context,
        lineage,
        admission,
        observation_id="observation-archived-terminal",
        child_status="completed",
        terminal_watermark=9,
        terminal_outcome="completed",
        observation_watermark=10,
    )
    before = copy.deepcopy(store.documents["controller.json"])
    with pytest.raises(ControllerError) as raised:
        controller.persist_native_child_observation(
            observation["observation_id"],
            lineage["owner_generation"],
            observation,
            expected_daemon_id="daemon-test",
        )
    assert raised.value.code in {"busy", "stale-generation", "ownership-conflict", "invalid"}
    assert store.documents["controller.json"] == before
