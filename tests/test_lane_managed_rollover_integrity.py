# SPDX-License-Identifier: Apache-2.0
"""Adversarial reload coverage for native invocation history and rollovers.

The normal rollover tests prove the happy path at the controller/runtime
boundary.  These cases begin with a complete, durable A-to-B snapshot and
then alter one nested binding at a time.  Each altered history/rollover entry
gets a freshly recomputed outer integrity digest, so a reload refusal must be
caused by the record's own context, roster, or cross-record authority rather
than by a stale checksum.  Reload is performed with an inert runtime and the
store is checked for writes/journal activity.
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any, Callable, Dict, Mapping

import pytest

from lane_managed_controller import ControllerError, ManagedController
from test_lane_managed_controller_rollover import (
    _canonical_digest,
    _operation_id,
    _released_native_fixture,
    _submit_next,
    _value,
)


def _recompute_entry_integrity(entry: Dict[str, Any]) -> None:
    """Recompute the controller's canonical record digest after a mutation."""
    entry["integrity_digest"] = _canonical_digest({
        key: value for key, value in entry.items() if key != "integrity_digest"
    })


def _terminal_proof_digest(history: Mapping[str, Any]) -> str:
    drain = history["independent_drain"]
    return _canonical_digest({
        "parent_result": history["terminal_result"],
        "roster": history["joined_roster"],
        "roster_digest": _canonical_digest(history["joined_roster"]),
        "observation_watermark": drain["observation_watermark"],
        "uncertainty": drain["uncertainty"],
        "overflow": drain["overflow"],
    })


def _committed_rollover_snapshot():
    """Return a real persisted A-to-B snapshot before any adversarial edit."""
    controller, store, runtime, coordinator, released, first = (
        _released_native_fixture()
    )
    second = _submit_next(controller, coordinator)
    delivered = asyncio.run(controller.dispatch_next(
        _operation_id(released), recipient_id=coordinator.participant_id
    ))
    assert _value(delivered, "message_id") == _value(second, "message_id")
    assert _value(delivered, "state") == "acknowledged"
    record = copy.deepcopy(store.documents["controller.json"])
    histories = record["native_invocation_history"]
    rollovers = record["native_invocation_rollovers"]
    assert isinstance(histories, Mapping) and len(histories) == 1
    assert isinstance(rollovers, Mapping) and len(rollovers) == 1
    return controller, store, runtime, record


def _history_and_rollover(record: Dict[str, Any]):
    history_id, history = next(iter(record["native_invocation_history"].items()))
    rollover_id, rollover = next(iter(record["native_invocation_rollovers"].items()))
    return history_id, history, rollover_id, rollover


def _assert_reload_refuses(store: Any, candidate: Dict[str, Any]) -> None:
    """Reload the candidate with no runtime access and no durable side effect."""
    store.documents["controller.json"] = copy.deepcopy(candidate)
    writes = copy.deepcopy(store.write_calls)
    journal = copy.deepcopy(store.journal)

    with pytest.raises(ControllerError):
        ManagedController(
            store,
            runtime=object(),
            clock=lambda: 1000.0,
            transcript_verifier=store.transcript_verifier,
        )

    assert store.documents["controller.json"] == candidate
    assert store.write_calls == writes
    assert store.journal == journal


def _history_admission(history: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a body-valid admission record for the historical A context."""
    context = history["context"]
    lineage = context["lineage"]
    definition_name, definition = next(iter(context["definitions"].items()))
    admission = {
        "admission_id": "admission-extra",
        "tool_use_id": "tool-extra",
        "agent_type": definition_name,
        "invocation_id": history["invocation_id"],
        "parent": {
            "session_id": lineage["session_uuid"],
            "agent_id": None,
            "invocation_id": history["invocation_id"],
            "prompt_id": context["prompt_id"],
        },
        "custom_definition": copy.deepcopy(definition),
        "definition_digest": definition["digest"],
        "trusted_definition_digest": definition["digest"],
        "watermark": context["invocation_watermark"] + 1,
        "owner_generation": lineage["owner_generation"],
        "lineage_id": lineage["lineage_id"],
        "runner_incarnation": history["runner_incarnation"],
        "launch_completed": False,
    }
    return {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "pending-admission",
        "request_id": "admission-extra",
        "digest": _canonical_digest(admission),
        "admission": admission,
        "claim_ref": copy.deepcopy(lineage["workspace_claim"]),
        "ack": {
            "accepted": True,
            "admission_id": admission["admission_id"],
            "owner_generation": admission["owner_generation"],
            "lineage_id": admission["lineage_id"],
            "runner_incarnation": admission["runner_incarnation"],
            "invocation_id": admission["invocation_id"],
            "tool_use_id": admission["tool_use_id"],
            "trusted_definition_digest": admission["trusted_definition_digest"],
        },
    }


def _history_child(history: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the bounded child projection used by the history roster."""
    definition = next(iter(history["context"]["definitions"].values()))
    terminal = history["terminal_watermark"]
    source = history["source_watermark"]
    return {
        "admission_id": "admission-extra",
        "tool_use_id": "tool-extra",
        "agent_id": "agent-extra",
        "task_id": "task-extra",
        "parent_agent_id": None,
        "invocation_id": history["invocation_id"],
        "lineage_incarnation": 1,
        "trusted_definition_digest": definition["digest"],
        "start_watermark": max(1, source),
        "task_start_event": {
            "event_uuid": "event-extra",
            "watermark": max(1, source + 1),
            "task_type": "local_agent",
        },
        "status": "completed",
        "terminal_watermark": terminal,
        "active_tool_ids": [],
        "uncertain_tool_ids": [],
        "unresolved_effect_ids": [],
    }


def _set_history_roster(history: Dict[str, Any], children: list[Dict[str, Any]]) -> None:
    roster = copy.deepcopy(history["joined_roster"])
    roster["children"] = children
    history["joined_roster"] = roster
    history["terminal_proof_digest"] = _terminal_proof_digest(history)


@pytest.mark.parametrize("collection", [
    "native_invocation_history",
    "native_invocation_rollovers",
])
def test_reload_refuses_present_null_native_history_collection(collection: str):
    _controller, store, _runtime, candidate = _committed_rollover_snapshot()
    # Keep the other collection valid/empty so this isolates explicit null
    # from the allowed omitted-collection form.
    if collection == "native_invocation_history":
        candidate["native_invocation_rollovers"] = {}
    candidate[collection] = None
    _assert_reload_refuses(store, candidate)


def test_reload_refuses_terminal_proof_digest_that_is_only_format_valid():
    _controller, store, _runtime, candidate = _committed_rollover_snapshot()
    _history_id, history, _rollover_id, _rollover = _history_and_rollover(candidate)
    history["terminal_proof_digest"] = "0" * 64
    _recompute_entry_integrity(history)
    _assert_reload_refuses(store, candidate)


def test_reload_refuses_history_child_without_matching_admission():
    _controller, store, _runtime, candidate = _committed_rollover_snapshot()
    _history_id, history, _rollover_id, _rollover = _history_and_rollover(candidate)
    # The child projection is internally complete and the proof digest is
    # recomputed.  Its admission is absent, so an empty admissions map cannot
    # be treated as a wildcard for a non-empty terminal roster.
    _set_history_roster(history, [_history_child(history)])
    history["admissions"] = {}
    _recompute_entry_integrity(history)
    _assert_reload_refuses(store, candidate)


def test_reload_refuses_admission_omitted_from_terminal_roster():
    _controller, store, _runtime, candidate = _committed_rollover_snapshot()
    _history_id, history, _rollover_id, _rollover = _history_and_rollover(candidate)
    history["admissions"] = {
        "admission-extra": _history_admission(history),
    }
    _set_history_roster(history, [])
    _recompute_entry_integrity(history)
    _assert_reload_refuses(store, candidate)


def test_reload_refuses_history_admission_with_foreign_runner_context():
    _controller, store, _runtime, candidate = _committed_rollover_snapshot()
    _history_id, history, _rollover_id, _rollover = _history_and_rollover(candidate)
    admission_record = _history_admission(history)
    admission = admission_record["admission"]
    admission["runner_incarnation"] = "foreign-runner"
    admission_record["digest"] = _canonical_digest(admission)
    admission_record["ack"]["runner_incarnation"] = "foreign-runner"
    history["admissions"] = {"admission-extra": admission_record}
    _set_history_roster(history, [_history_child(history)])
    _recompute_entry_integrity(history)
    _assert_reload_refuses(store, candidate)


@pytest.mark.parametrize("control_key", ["native_stops", "coordinator_interrupts"])
def test_reload_refuses_unbound_history_terminal_control(control_key: str):
    _controller, store, _runtime, candidate = _committed_rollover_snapshot()
    _history_id, history, _rollover_id, _rollover = _history_and_rollover(candidate)
    controls = copy.deepcopy(history["terminal_controls"])
    controls[control_key] = {
        "foreign-control": {
            "invocation_id": "foreign-invocation",
            "task_id": "foreign-task",
            "definition_digest": "0" * 64,
        }
    }
    history["terminal_controls"] = controls
    _recompute_entry_integrity(history)
    _assert_reload_refuses(store, candidate)


@pytest.mark.parametrize("mutate", [
    pytest.param(
        lambda rollover: rollover["preparation_intent"]["request"].update(
            {"binding_digest": "0" * 64}
        ),
        id="preparation-request-digest",
    ),
    pytest.param(
        lambda rollover: rollover["reservation_binding"].update(
            {"next_invocation_id": rollover["prior_invocation_id"]}
        ),
        id="reservation-next-invocation",
    ),
    pytest.param(
        lambda rollover: rollover["startup_binding"].update(
            {"invocation_id": rollover["prior_invocation_id"]}
        ),
        id="startup-invocation",
    ),
    pytest.param(
        lambda rollover: rollover["dispatch_intent"].update(
            {"message_id": rollover["prior_mailbox_id"]}
        ),
        id="dispatch-mailbox",
    ),
    pytest.param(
        lambda rollover: rollover["next_context"].update(
            {"runner_incarnation": "foreign-runner"}
        ),
        id="next-context-runner",
    ),
])
def test_reload_refuses_recomputed_rollover_nested_binding_tampering(
        mutate: Callable[[Dict[str, Any]], None],
):
    _controller, store, _runtime, candidate = _committed_rollover_snapshot()
    _history_id, _history, _rollover_id, rollover = _history_and_rollover(candidate)
    mutate(rollover)
    _recompute_entry_integrity(rollover)
    _assert_reload_refuses(store, candidate)

@pytest.mark.parametrize("field", [
    "history_id",
    "next_context",
    "startup_binding",
    "reservation_binding",
    "dispatch_intent",
])
def test_reload_refuses_committed_rollover_missing_required_binding(field: str):
    _controller, store, _runtime, candidate = _committed_rollover_snapshot()
    _history_id, _history, _rollover_id, rollover = _history_and_rollover(candidate)
    rollover[field] = None
    _recompute_entry_integrity(rollover)
    _assert_reload_refuses(store, candidate)


def test_reload_refuses_rollover_history_operation_cross_record_mismatch():
    _controller, store, _runtime, candidate = _committed_rollover_snapshot()
    _history_id, history, _rollover_id, rollover = _history_and_rollover(candidate)
    history["operation_id"] = "foreign-operation"
    _recompute_entry_integrity(history)
    # The rollover still names the original operation and history ID; a valid
    # outer digest cannot authorize a history from another operation.
    _recompute_entry_integrity(rollover)
    _assert_reload_refuses(store, candidate)
