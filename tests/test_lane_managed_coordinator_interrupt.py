# SPDX-License-Identifier: Apache-2.0
"""Durable coordinator-interrupt authority and evidence contracts.

These tests stop at the internal controller/store boundary.  They do not
start a runner or call an SDK interrupt.  The fixture creates the native
context and admission through the existing public authorities, then enters a
durably fenced operation before submitting the coordinator-wide frame.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from lane_managed_controller import ControllerError, ManagedController
from test_lane_managed_native_stop import _native_stop_authority


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"),
                  ensure_ascii=True, allow_nan=False).encode("utf-8")
    ).hexdigest()


def _roster_identity(roster):
    """Build the frozen identity projection, excluding progress fields."""
    projection = dict(roster)
    projection.pop("parent_state", None)
    projection["children"] = []
    for child in sorted(roster["children"], key=lambda value: value["admission_id"]):
        item = dict(child)
        for key in (
            "status", "terminal_watermark", "start_watermark",
            "task_start_event",
        ):
            item.pop(key, None)
        for key in (
            "active_tool_ids", "uncertain_tool_ids", "unresolved_effect_ids",
        ):
            item[key] = sorted(item[key])
        projection["children"].append(item)
    for key in (
        "pending_admission_ids", "pending_task_ids", "parent_active_tool_ids",
        "parent_uncertain_tool_ids", "parent_unresolved_effect_ids",
        "descendant_ids",
    ):
        projection[key] = sorted(projection[key])
    return _digest(projection)


def _fenced_authority(tmp_path):
    """Return a real controller context/admission in the fenced phase."""
    _native_stop_controller, store, lineage, admission, context = _native_stop_authority(
        tmp_path
    )
    # Native task-stop and whole-coordinator interrupt authorities are
    # distinct trusted daemon seams.  Reopen the same durable fixture with
    # both identities explicitly configured before exercising the latter.
    controller = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )
    # The admission was persisted while the initial public operation was
    # released.  Start a fresh swap through the public operation authority,
    # then use its real fence transition to seal context and roster.  Keeping
    # this lifecycle on the controller surface catches an interrupt that is
    # accidentally accepted against a hand-edited operation snapshot.
    operation = controller.begin_operation(
        "coordinator-interrupt-operation", "swap", 7,
        request_content={"target": "synthetic-test-profile"},
    )
    operation_id = operation.operation_id
    controller.fence(operation_id)
    context = store.documents["controller.json"]["native_context"]
    assert context["fenced"] is True
    return controller, store, lineage, admission, context, operation_id


def _roster(admission, *, child_status="active", terminal_watermark=None,
            pending_admission_ids=None, task_id="task-1"):
    child = {
        "admission_id": admission["admission_id"],
        "tool_use_id": admission["tool_use_id"],
        "agent_id": "agent-1",
        "task_id": task_id,
        "parent_agent_id": None,
        "invocation_id": admission["invocation_id"],
        "lineage_incarnation": 1,
        "trusted_definition_digest": admission["trusted_definition_digest"],
        "start_watermark": 3,
        "task_start_event": {
            "event_uuid": "task-start-1",
            "watermark": 4,
            "task_type": "local_agent",
        },
        "status": child_status,
        "terminal_watermark": terminal_watermark,
        "active_tool_ids": (
            [] if child_status == "completed" else ["child-tool-1"]
        ),
        "uncertain_tool_ids": [],
        # The evidence matrix includes an unresolved effect outcome.  Keep
        # that ID in the sealed child inventory so the controller can match
        # the fact to its durable roster rather than accepting an arbitrary
        # effect ID from the runner.
        "unresolved_effect_ids": ["effect-1"],
    }
    roster = {
        "parent_state": "active",
        "children": [child] if pending_admission_ids is None else [],
        "pending_admission_ids": (
            [] if pending_admission_ids is None else list(pending_admission_ids)
        ),
        "pending_task_ids": [],
        "parent_active_tool_ids": [],
        "parent_uncertain_tool_ids": [],
        "parent_unresolved_effect_ids": [],
        "descendant_ids": [],
    }
    return roster


def _intent(lineage, admission, operation_id, *, roster=None,
            interrupt_id="interrupt-1", fence_epoch=3,
            runner_instance_id="runner-current",
            roster_seal_watermark=8, request_entry_watermark=7):
    roster = _roster(admission) if roster is None else roster
    return {
        "type": "coordinator-interrupt-intent",
        "participant_id": "coordinator",
        "session_id": lineage["session_uuid"],
        "runner_instance_id": runner_instance_id,
        "interrupt": {
            "interrupt_id": interrupt_id,
            "operation_id": operation_id,
            "owner_generation": lineage["owner_generation"],
            "lineage_id": lineage["lineage_id"],
            "lineage_generation": lineage["lineage_generation"],
            "invocation_id": "invocation-1",
            "fence_epoch": fence_epoch,
            "roster_identity_digest": _roster_identity(roster),
            "roster_seal_watermark": roster_seal_watermark,
            "capability_digest": "c" * 64,
            "request_epoch_id": "request-epoch-1",
            "request_entry_watermark": request_entry_watermark,
            "roster": roster,
        },
    }


def _evidence(frame, kind, *, evidence_id=None, observed_watermark=9,
              data=None):
    interrupt = frame["interrupt"]
    if data is None:
        data = {
            "runtime-ack": {
                "accepted": True,
                "ack_kind": "accepted-interrupt",
            },
            "member-terminal": {
                "agent_id": "agent-1",
                "task_id": "task-1",
                "lineage_incarnation": 1,
                "tool_use_id": "tool-1",
                "event_kind": "task_notification",
                "event_uuid": "task-stop-1",
                "status": "stopped",
            },
            "tool-terminal": {
                "tool_use_id": "child-tool-1",
                "agent_id": "agent-1",
                "lineage_incarnation": 1,
                "status": "cancelled",
            },
            "effect-outcome": {
                "effect_id": "effect-1",
                "status": "unknown",
            },
            "admission-closed": {
                "admission_id": "admission-1",
                "closed": True,
            },
            "parent-drained": {
                "invocation_id": "invocation-1",
                "state": "drained",
            },
            "request-observation": {
                "epoch_id": interrupt["request_epoch_id"],
                "entry_watermark": interrupt["request_entry_watermark"],
                "through_watermark": observed_watermark,
                "new_requests": 0,
                "observable": True,
            },
            "process-excluded": {
                "process_identity_digest": "e" * 64,
                "status": "excluded",
            },
        }[kind]
    return {
        "type": "coordinator-interrupt-evidence",
        "participant_id": frame["participant_id"],
        "session_id": frame["session_id"],
        "runner_instance_id": frame["runner_instance_id"],
        "evidence": {
            "evidence_id": evidence_id or "evidence-" + kind,
            "interrupt_id": interrupt["interrupt_id"],
            "kind": kind,
            "observed_watermark": observed_watermark,
            "data": data,
        },
    }


def test_interrupt_persists_before_authorization_and_deduplicates_after_reload(
    tmp_path,
):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    frame = _intent(lineage, admission, operation_id)

    assert controller.persist_coordinator_interrupt_intent(frame) == {
        "recorded": True,
        "authorize_send": True,
        "interrupt_id": "interrupt-1",
    }
    record = store.documents["controller.json"]["coordinator_interrupts"][
        "interrupt-1"
    ]
    assert record["may_have_been_sent"] is True
    assert record["authorization_count"] == 1
    assert record["frame"] == frame
    assert "quiescent" not in record
    assert "ready" not in record

    before = copy.deepcopy(store.documents["controller.json"])
    reloaded = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )
    assert reloaded.persist_coordinator_interrupt_intent(copy.deepcopy(frame)) == {
        "recorded": True,
        "authorize_send": False,
        "interrupt_id": "interrupt-1",
    }
    assert store.documents["controller.json"] == before


@pytest.mark.parametrize("field", [
    "interrupt_id", "operation_id", "fence_epoch", "roster_identity_digest",
])
def test_changed_source_ids_cannot_bypass_unresolved_interrupt(
    tmp_path, field,
):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    original = _intent(lineage, admission, operation_id)
    controller.persist_coordinator_interrupt_intent(original)
    before = copy.deepcopy(store.documents["controller.json"])
    changed = copy.deepcopy(original)
    changed["interrupt"]["interrupt_id"] = "interrupt-changed-" + field
    if field == "interrupt_id":
        pass
    elif field == "operation_id":
        changed["interrupt"][field] = "operation-changed"
    elif field == "fence_epoch":
        changed["interrupt"][field] = 4
    else:
        roster = changed["interrupt"]["roster"]
        roster["children"][0]["task_id"] = "task-changed"
        changed["interrupt"][field] = _roster_identity(roster)

    with pytest.raises(ControllerError):
        controller.persist_coordinator_interrupt_intent(changed)
    assert store.documents["controller.json"] == before


def test_fenced_roster_requires_exact_admission_coverage_and_no_reused_ids(
    tmp_path,
):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    original = _intent(lineage, admission, operation_id)
    cases = []

    missing = copy.deepcopy(original)
    missing["interrupt"]["roster"]["children"] = []
    missing["interrupt"]["roster_identity_digest"] = _roster_identity(
        missing["interrupt"]["roster"]
    )
    cases.append(missing)

    unknown = copy.deepcopy(original)
    unknown["interrupt"]["roster"]["children"][0]["admission_id"] = (
        "missing-admission"
    )
    unknown["interrupt"]["roster"]["children"][0]["trusted_definition_digest"] = (
        admission["trusted_definition_digest"]
    )
    unknown["interrupt"]["roster_identity_digest"] = _roster_identity(
        unknown["interrupt"]["roster"]
    )
    cases.append(unknown)

    duplicate = copy.deepcopy(original)
    duplicate["interrupt"]["roster"]["children"].append(
        copy.deepcopy(duplicate["interrupt"]["roster"]["children"][0])
    )
    duplicate["interrupt"]["roster_identity_digest"] = _roster_identity(
        duplicate["interrupt"]["roster"]
    )
    cases.append(duplicate)

    for candidate in cases:
        with pytest.raises(ControllerError):
            controller.persist_coordinator_interrupt_intent(candidate)
        assert store.documents["controller.json"].get("coordinator_interrupts", {}) == {}


def test_pending_admission_and_natural_completion_are_preserved_without_stop_inference(
    tmp_path,
):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    for field, value in (
        ("pending_admission_ids", [admission["admission_id"]]),
        ("pending_task_ids", ["task-1"]),
    ):
        pending_roster = _roster(
            admission,
            pending_admission_ids=(
                [admission["admission_id"]]
                if field == "pending_admission_ids" else None
            ),
        )
        pending_roster[field] = value
        pending = _intent(
            lineage, admission, operation_id, roster=pending_roster,
            interrupt_id="interrupt-pending-" + field,
        )
        with pytest.raises(ControllerError):
            controller.persist_coordinator_interrupt_intent(pending)
    assert store.documents["controller.json"].get("coordinator_interrupts", {}) == {}

    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    completed_roster = _roster(
        admission, child_status="completed", terminal_watermark=7
    )
    completed = _intent(
        lineage, admission, operation_id, roster=completed_roster,
        interrupt_id="interrupt-completed",
    )
    assert controller.persist_coordinator_interrupt_intent(completed) == {
        "recorded": True,
        "authorize_send": True,
        "interrupt_id": "interrupt-completed",
    }
    saved = store.documents["controller.json"]["coordinator_interrupts"][
        "interrupt-completed"
    ]["frame"]["interrupt"]["roster"]["children"][0]
    assert saved["status"] == "completed"
    assert saved["terminal_watermark"] == 7
    assert "stopped" not in json.dumps(saved)


@pytest.mark.parametrize(
    "order",
    [
        ("runtime-ack", "member-terminal", "tool-terminal", "effect-outcome",
         "admission-closed", "parent-drained", "request-observation",
         "process-excluded"),
        ("process-excluded", "request-observation", "parent-drained",
         "admission-closed", "effect-outcome", "tool-terminal",
         "member-terminal", "runtime-ack"),
    ],
)
def test_interrupt_evidence_is_independent_and_never_synthesizes_quiescence(
    tmp_path, order,
):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    frame = _intent(lineage, admission, operation_id)
    controller.persist_coordinator_interrupt_intent(frame)

    for kind in order:
        assert controller.persist_coordinator_interrupt_evidence(
            _evidence(frame, kind)
        ) == {
            "recorded": True,
            "evidence_id": "evidence-" + kind,
            "interrupt_id": "interrupt-1",
        }

    record = store.documents["controller.json"]["coordinator_interrupts"][
        "interrupt-1"
    ]
    assert set(record["evidence"]) == {
        "evidence-" + kind for kind in order
    }
    assert record["evidence"]["evidence-runtime-ack"]["frame"]["evidence"][
        "data"
    ]["accepted"] is True
    assert "quiescent" not in record
    assert "ready" not in record
    assert "capability" not in record
    before = copy.deepcopy(store.documents["controller.json"])
    assert controller.persist_coordinator_interrupt_evidence(
        _evidence(frame, "runtime-ack")
    ) == {
        "recorded": True,
        "evidence_id": "evidence-runtime-ack",
        "interrupt_id": "interrupt-1",
    }
    assert store.documents["controller.json"] == before


def test_interrupt_schema_refusal_preserves_bytes_and_keeps_native_stop_separate(
    tmp_path,
):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    frame = _intent(lineage, admission, operation_id)
    controller.persist_coordinator_interrupt_intent(frame)
    before = copy.deepcopy(store.documents["controller.json"])

    malformed = copy.deepcopy(before)
    del malformed["coordinator_interrupts"]["interrupt-1"]["frame"][
        "interrupt"
    ]["roster"]
    store.documents["controller.json"] = malformed
    with pytest.raises(ControllerError):
        ManagedController(
            store,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="daemon-test",
        )
    assert store.documents["controller.json"] == malformed

    store.documents["controller.json"] = before
    native_as_interrupt = copy.deepcopy(before)
    native_as_interrupt["coordinator_interrupts"]["native-stop"] = copy.deepcopy(
        native_as_interrupt["coordinator_interrupts"]["interrupt-1"]
    )
    native_as_interrupt["coordinator_interrupts"]["native-stop"]["record_kind"] = (
        "native-stop"
    )
    store.documents["controller.json"] = native_as_interrupt
    with pytest.raises(ControllerError):
        ManagedController(
            store,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="daemon-test",
        )
    assert store.documents["controller.json"] == native_as_interrupt


def test_malformed_request_count_cross_child_tool_and_process_identity_refuse(
    tmp_path,
):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    frame = _intent(lineage, admission, operation_id)
    controller.persist_coordinator_interrupt_intent(frame)

    cases = []
    bad_count = _evidence(frame, "request-observation")
    bad_count["evidence"]["data"]["new_requests"] = True
    cases.append(bad_count)
    wrong_tool_owner = _evidence(frame, "tool-terminal")
    wrong_tool_owner["evidence"]["data"]["agent_id"] = "agent-other"
    cases.append(wrong_tool_owner)
    missing_process_identity = _evidence(frame, "process-excluded")
    missing_process_identity["evidence"]["data"]["process_identity_digest"] = None
    cases.append(missing_process_identity)

    for candidate in cases:
        before = copy.deepcopy(store.documents["controller.json"])
        with pytest.raises(ControllerError):
            controller.persist_coordinator_interrupt_evidence(candidate)
        assert store.documents["controller.json"] == before


def test_completed_sealed_member_cannot_be_relabelled_stopped(
    tmp_path,
):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    completed_roster = _roster(
        admission, child_status="completed", terminal_watermark=7
    )
    frame = _intent(
        lineage, admission, operation_id, roster=completed_roster,
        interrupt_id="interrupt-completed-terminal",
    )
    controller.persist_coordinator_interrupt_intent(frame)
    changed = _evidence(frame, "member-terminal")
    changed["evidence"]["observed_watermark"] = 9
    changed["evidence"]["data"]["status"] = "stopped"
    before = copy.deepcopy(store.documents["controller.json"])
    with pytest.raises(ControllerError):
        controller.persist_coordinator_interrupt_evidence(changed)
    assert store.documents["controller.json"] == before


def test_interrupt_requires_the_live_native_fence_before_authorization(tmp_path):
    _old_controller, store, lineage, admission, _context = _native_stop_authority(
        tmp_path
    )
    controller = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )
    operation = controller.begin_operation(
        "coordinator-interrupt-unfenced", "swap", 7,
        request_content={"target": "synthetic-test-profile"},
    )
    frame = _intent(lineage, admission, operation.operation_id)
    before = copy.deepcopy(store.documents["controller.json"])
    with pytest.raises(ControllerError):
        controller.persist_coordinator_interrupt_intent(frame)
    assert store.documents["controller.json"] == before
