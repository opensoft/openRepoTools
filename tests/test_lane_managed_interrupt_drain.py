# SPDX-License-Identifier: Apache-2.0
"""Adversarial read-only projections for coordinator interrupt drain facts.

The controller-facing projection is deliberately tested against the existing
durable interrupt fixture.  These tests do not call a runtime, recover an
authorization, advance an operation, release a claim, or edit the durable
schema.  Sol is the executor for the focused suite; this module is authored
test-first for the controller implementation.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping

import pytest

from lane_managed_controller import ControllerError, ManagedController
from test_lane_managed_coordinator_interrupt import (
    _digest,
    _evidence,
    _fenced_authority,
    _intent,
    _roster,
)
from test_lane_managed_native_stop import _native_stop_authority


SUMMARY_FIELDS = {
    "interrupt_id",
    "runtime_acknowledged",
    "graph_quiescent",
    "children",
    "blockers",
    "process_exclusion",
    "request_observation",
    "roster_seal_watermark",
    "progress_watermark",
}


def _new_interrupt(
    tmp_path, *, roster=None, roster_factory=None, interrupt_id="interrupt-1"
):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    if roster_factory is not None:
        roster = roster_factory(admission)
    elif roster is None:
        roster = _roster(admission)
    frame = _intent(
        lineage,
        admission,
        operation_id,
        roster=roster,
        interrupt_id=interrupt_id,
    )
    assert controller.persist_coordinator_interrupt_intent(frame) == {
        "recorded": True,
        "authorize_send": True,
        "interrupt_id": interrupt_id,
    }
    return controller, store, frame


def _persist(controller, frame, kind, *, evidence_id=None,
             observed_watermark=9, updates=None):
    candidate = _evidence(
        frame,
        kind,
        evidence_id=evidence_id,
        observed_watermark=observed_watermark,
    )
    if updates:
        candidate["evidence"]["data"].update(copy.deepcopy(updates))
    return controller.persist_coordinator_interrupt_evidence(candidate)


def _fact_frames(
    frame,
    *,
    omit=(),
    member_status=None,
    effect_statuses=None,
    request_data=None,
    request_observed_watermark=9,
    process_status="excluded",
):
    """Build independently submitted facts for the simple one-child roster."""
    omit = set(omit)
    interrupt = frame["interrupt"]
    roster = interrupt["roster"]
    children = roster["children"]
    result = []

    if "runtime-ack" not in omit:
        result.append(_evidence(frame, "runtime-ack"))

    for child in children:
        if "member-terminal" not in omit:
            status = member_status
            if status is None:
                status = (
                    child["status"]
                    if child["status"] in {"completed", "failed", "stopped"}
                    else "stopped"
                )
            observed = 9
            if child["terminal_watermark"] is not None and status == child["status"]:
                observed = child["terminal_watermark"]
            member_data = _evidence(
                frame,
                "member-terminal",
                observed_watermark=observed,
            )["evidence"]["data"]
            member_data.update(
                {
                    "agent_id": child["agent_id"],
                    "task_id": child["task_id"],
                    "tool_use_id": child["tool_use_id"],
                    "lineage_incarnation": child["lineage_incarnation"],
                    "status": status,
                }
            )
            result.append(
                _evidence(
                    frame,
                    "member-terminal",
                    evidence_id="evidence-member-" + child["admission_id"],
                    observed_watermark=observed,
                    data=member_data,
                )
            )

        if "tool-terminal" not in omit:
            for tool_use_id in child["active_tool_ids"] + child["uncertain_tool_ids"]:
                tool_data = _evidence(frame, "tool-terminal")["evidence"]["data"]
                tool_data.update(
                    {
                        "tool_use_id": tool_use_id,
                        "agent_id": child["agent_id"],
                        "lineage_incarnation": child["lineage_incarnation"],
                    }
                )
                result.append(
                    _evidence(
                        frame,
                        "tool-terminal",
                        evidence_id="evidence-tool-" + tool_use_id,
                        data=tool_data,
                    )
                )

        if "admission-closed" not in omit:
            result.append(
                _evidence(
                    frame,
                    "admission-closed",
                    evidence_id="evidence-admission-" + child["admission_id"],
                    data={
                        "admission_id": child["admission_id"],
                        "closed": True,
                    },
                )
            )

    if "effect-outcome" not in omit:
        effect_statuses = effect_statuses or {}
        effect_ids = list(roster["parent_unresolved_effect_ids"])
        for child in children:
            effect_ids.extend(child["unresolved_effect_ids"])
        for effect_id in effect_ids:
            status = effect_statuses.get(effect_id, "resolved")
            result.append(
                _evidence(
                    frame,
                    "effect-outcome",
                    evidence_id="evidence-effect-" + effect_id + "-" + status,
                    data={"effect_id": effect_id, "status": status},
                )
            )

    if roster["parent_state"] == "active" and "parent-drained" not in omit:
        result.append(_evidence(frame, "parent-drained"))

    if "request-observation" not in omit:
        data = _evidence(frame, "request-observation")["evidence"]["data"]
        if request_data:
            data.update(copy.deepcopy(request_data))
        result.append(
            _evidence(
                frame,
                "request-observation",
                observed_watermark=request_observed_watermark,
                data=data,
            )
        )

    if "process-excluded" not in omit:
        process_data = _evidence(frame, "process-excluded")["evidence"]["data"]
        process_data["status"] = process_status
        if process_status == "unknown":
            process_data["process_identity_digest"] = None
        result.append(
            _evidence(frame, "process-excluded", data=process_data)
        )

    return result


def _persist_frames(controller, frames):
    for frame in frames:
        controller.persist_coordinator_interrupt_evidence(frame)


def _assert_projection_shape(summary):
    assert SUMMARY_FIELDS.issubset(summary)
    assert type(summary["interrupt_id"]) is str
    assert type(summary["runtime_acknowledged"]) is bool
    assert type(summary["graph_quiescent"]) is bool
    assert isinstance(summary["children"], list)
    assert isinstance(summary["blockers"], list)
    assert isinstance(summary["process_exclusion"], dict)
    assert isinstance(summary["request_observation"], dict)
    assert type(summary["roster_seal_watermark"]) is int
    assert type(summary["progress_watermark"]) is int
    assert not any(
        "support" in key.casefold()
        or "safe_to_restore" in key.casefold()
        or key.casefold() in {"release", "authorize_send"}
        for key in summary
    )


def _blocker_text(summary):
    return json.dumps(summary["blockers"], sort_keys=True).casefold()


def _assert_blocker_mentions(summary, *terms):
    text = _blocker_text(summary)
    assert any(term.casefold() in text for term in terms), (terms, text)


def _child(summary, *, agent_id="agent-1", task_id="task-1"):
    for child in summary["children"]:
        if not isinstance(child, Mapping):
            continue
        if child.get("agent_id") == agent_id or child.get("task_id") == task_id:
            return child
    raise AssertionError("summary has no matching child")


def _child_status(child):
    for key in ("status", "terminal_status", "state"):
        if key in child:
            return child[key]
    raise AssertionError("summary child has no status field")


def _effect_row(summary, effect_id):
    for effect in summary["effects"]:
        if effect.get("effect_id") == effect_id:
            return effect
    raise AssertionError("summary has no matching effect")


def _summary(controller, interrupt_id="interrupt-1"):
    value = controller.coordinator_interrupt_status(interrupt_id)
    _assert_projection_shape(value)
    public = controller.status()
    assert public["coordinator_interrupt_summaries"][interrupt_id] == value
    assert interrupt_id in public["coordinator_interrupts"]
    return value


def _read_snapshot(store, interrupt_id):
    raw = copy.deepcopy(store.documents["controller.json"])
    record = raw["coordinator_interrupts"][interrupt_id]
    operation = next(
        item
        for item in raw["operations"]
        if item["operation_id"] == record["frame"]["interrupt"]["operation_id"]
    )
    return {
        "documents": raw,
        "journal": copy.deepcopy(store.journal),
        "writes": copy.deepcopy(store.write_calls),
        "claims": copy.deepcopy(store.read_lineage_claims()),
        "owner": copy.deepcopy(store.read_owner()),
        "phase": operation["phase"],
        "authorization": {
            key: copy.deepcopy(record[key])
            for key in (
                "source_exclusion_key",
                "may_have_been_sent",
                "authorization_count",
            )
        },
    }


def _two_child_interrupt(tmp_path, *, interrupt_id="interrupt-two-child"):
    """Create two real durable admissions before the native fence seals them."""
    _old_controller, store, lineage, first_admission, _context = (
        _native_stop_authority(tmp_path)
    )
    controller = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )
    second_admission = copy.deepcopy(first_admission)
    second_admission.update(
        {
            "admission_id": "admission-2",
            "tool_use_id": "tool-2",
            "watermark": 3,
        }
    )
    controller.persist_native_admission(
        "request-2", lineage["owner_generation"], second_admission
    )
    operation = controller.begin_operation(
        "coordinator-interrupt-two-child",
        "swap",
        lineage["owner_generation"],
        request_content={"target": "synthetic-test-profile"},
    )
    controller.fence(operation.operation_id)

    first = _roster(first_admission)["children"][0]
    second = copy.deepcopy(first)
    second.update(
        {
            "admission_id": "admission-2",
            "tool_use_id": "tool-2",
            "agent_id": "agent-2",
            "task_id": "task-2",
            "start_watermark": 4,
            "task_start_event": {
                "event_uuid": "task-start-2",
                "watermark": 5,
                "task_type": "local_agent",
            },
            "active_tool_ids": ["child-tool-2"],
            "unresolved_effect_ids": ["effect-2"],
        }
    )
    roster = {
        "parent_state": "active",
        "children": [first, second],
        "pending_admission_ids": [],
        "pending_task_ids": [],
        "parent_active_tool_ids": [],
        "parent_uncertain_tool_ids": [],
        "parent_unresolved_effect_ids": [],
        "descendant_ids": [],
    }
    frame = _intent(
        lineage,
        first_admission,
        operation.operation_id,
        roster=roster,
        interrupt_id=interrupt_id,
    )
    assert controller.persist_coordinator_interrupt_intent(frame) == {
        "recorded": True,
        "authorize_send": True,
        "interrupt_id": interrupt_id,
    }
    return controller, store, frame


class _NoRuntimeCalls:
    def __getattr__(self, name):
        raise AssertionError("drain status accessed runtime attribute %s" % name)


def test_ack_only_is_not_a_drain_and_projection_has_minimum_shape(tmp_path):
    controller, store, frame = _new_interrupt(tmp_path)
    _persist(controller, frame, "runtime-ack")
    controller.runtime = _NoRuntimeCalls()

    summary = _summary(controller)

    assert summary["runtime_acknowledged"] is True
    assert summary["graph_quiescent"] is False
    for term in ("child", "tool", "effect", "admission", "parent"):
        _assert_blocker_mentions(summary, term)
    assert "safe_to_restore" not in summary


def test_projection_is_read_only_and_preserves_raw_authority_claims_and_journal(
    tmp_path,
):
    controller, store, frame = _new_interrupt(tmp_path)
    _persist(controller, frame, "runtime-ack")
    before = _read_snapshot(store, "interrupt-1")
    controller.runtime = _NoRuntimeCalls()

    direct = controller.coordinator_interrupt_status("interrupt-1")
    public = controller.status()
    assert public["coordinator_interrupt_summaries"]["interrupt-1"] == direct
    assert public["coordinator_interrupts"]["interrupt-1"] == before["documents"][
        "coordinator_interrupts"
    ]["interrupt-1"]

    assert controller.coordinator_interrupt_status("interrupt-1") == direct
    assert controller.status() == public
    after = _read_snapshot(store, "interrupt-1")
    assert after == before


def test_missing_ack_does_not_erase_natural_completion(tmp_path):
    controller, _store, frame = _new_interrupt(
        tmp_path,
        roster_factory=lambda admission: _roster(
            admission,
            child_status="completed",
            terminal_watermark=7,
        ),
        interrupt_id="interrupt-natural-complete",
    )
    _persist_frames(
        controller,
        _fact_frames(frame, omit={"runtime-ack"}),
    )

    summary = _summary(controller, "interrupt-natural-complete")

    assert summary["runtime_acknowledged"] is False
    assert _child_status(_child(summary)) == "completed"
    assert summary["graph_quiescent"] is True


def test_matching_sealed_preterminal_completion_counts_without_relabeling(tmp_path):
    controller, _store, frame = _new_interrupt(
        tmp_path,
        roster_factory=lambda admission: _roster(
            admission,
            child_status="completed",
            terminal_watermark=7,
        ),
        interrupt_id="interrupt-preterminal-complete",
    )
    _persist_frames(controller, _fact_frames(frame))

    summary = _summary(controller, "interrupt-preterminal-complete")

    assert summary["runtime_acknowledged"] is True
    assert summary["graph_quiescent"] is True
    assert _child_status(_child(summary)) == "completed"


def test_failed_terminal_status_remains_failed_and_is_terminal(tmp_path):
    controller, _store, frame = _new_interrupt(tmp_path)
    _persist_frames(
        controller,
        _fact_frames(frame, member_status="failed"),
    )

    summary = _summary(controller)

    assert summary["graph_quiescent"] is True
    assert _child_status(_child(summary)) == "failed"


@pytest.mark.parametrize(
    ("missing_kind", "blocker_terms"),
    [
        ("member-terminal", ("child-terminal-missing",)),
        ("tool-terminal", ("tool-terminal-missing",)),
        ("effect-outcome", ("effect-outcome-missing",)),
        ("admission-closed", ("admission-closed-missing",)),
        ("parent-drained", ("parent-drain-missing",)),
    ],
)
def test_each_missing_graph_fact_is_visible_as_a_blocker(
    tmp_path, missing_kind, blocker_terms
):
    controller, _store, frame = _new_interrupt(tmp_path)
    _persist_frames(controller, _fact_frames(frame, omit={missing_kind}))

    summary = _summary(controller)

    assert summary["graph_quiescent"] is False
    _assert_blocker_mentions(summary, *blocker_terms)


def test_unknown_and_resolved_effects_with_different_ids_still_block_graph(
    tmp_path,
):
    def roster_factory(admission):
        roster = _roster(admission)
        roster["children"][0]["unresolved_effect_ids"] = [
            "effect-1",
            "effect-2",
        ]
        return roster

    controller, store, frame = _new_interrupt(
        tmp_path,
        roster_factory=roster_factory,
    )
    _persist_frames(
        controller,
        _fact_frames(
            frame,
            effect_statuses={"effect-1": "unknown", "effect-2": "resolved"},
        ),
    )

    summary = _summary(controller)

    assert summary["graph_quiescent"] is False
    effect_one = _effect_row(summary, "effect-1")
    effect_two = _effect_row(summary, "effect-2")
    assert effect_one["status"] == "unknown"
    assert effect_two["status"] == "resolved"
    assert effect_one["outcome_evidence_ids"]
    assert effect_two["outcome_evidence_ids"]
    raw_evidence = store.documents["controller.json"]["coordinator_interrupts"][
        "interrupt-1"
    ]["evidence"]
    assert raw_evidence["evidence-effect-effect-1-unknown"]["frame"][
        "evidence"
    ]["data"]["effect_id"] == "effect-1"
    assert raw_evidence["evidence-effect-effect-2-resolved"]["frame"][
        "evidence"
    ]["data"]["effect_id"] == "effect-2"
    _assert_blocker_mentions(summary, "effect-outcome-unknown:effect-1")


def test_effect_semantic_conflict_with_distinct_evidence_ids_remains_blocked(
    tmp_path,
):
    controller, store, frame = _new_interrupt(tmp_path)
    _persist_frames(
        controller,
        _fact_frames(frame, effect_statuses={"effect-1": "unknown"}),
    )
    _persist(
        controller,
        frame,
        "effect-outcome",
        evidence_id="evidence-effect-1-resolved-later",
        observed_watermark=10,
        updates={"effect_id": "effect-1", "status": "resolved"},
    )

    summary = _summary(controller)

    assert summary["graph_quiescent"] is False
    effect = _effect_row(summary, "effect-1")
    assert effect["status"] == "conflicted"
    assert {
        "evidence-effect-effect-1-unknown",
        "evidence-effect-1-resolved-later",
    } <= set(effect["outcome_evidence_ids"])
    raw_evidence = store.documents["controller.json"]["coordinator_interrupts"][
        "interrupt-1"
    ]["evidence"]
    assert {
        raw_evidence["evidence-effect-effect-1-unknown"]["frame"][
            "evidence"
        ]["evidence_id"],
        raw_evidence["evidence-effect-1-resolved-later"]["frame"][
            "evidence"
        ]["evidence_id"],
    } == {
        "evidence-effect-effect-1-unknown",
        "evidence-effect-1-resolved-later",
    }
    _assert_blocker_mentions(summary, "effect-outcome-conflict:effect-1")
    _assert_blocker_mentions(effect, "effect-outcome-conflict:effect-1")


@pytest.mark.parametrize(
    ("kind", "first_status", "second_status"),
    [
        ("member-terminal", "stopped", "failed"),
        ("tool-terminal", "cancelled", "failed"),
    ],
)
def test_member_and_tool_conflicts_with_distinct_ids_refuse_on_reload(
    tmp_path, kind, first_status, second_status
):
    controller, store, frame = _new_interrupt(tmp_path)
    _persist(controller, frame, kind)
    raw = copy.deepcopy(store.documents["controller.json"])
    record = raw["coordinator_interrupts"]["interrupt-1"]
    candidate = _evidence(
        frame,
        kind,
        evidence_id="evidence-" + kind + "-conflict",
        observed_watermark=10,
    )
    candidate["evidence"]["data"]["status"] = second_status
    # The first status is asserted here to make the fixture's semantic
    # contradiction explicit, rather than relying on the helper's default.
    assert record["evidence"]["evidence-" + kind]["frame"]["evidence"]["data"][
        "status"
    ] == first_status
    evidence_id = candidate["evidence"]["evidence_id"]
    record["evidence"][evidence_id] = {
        "digest": _digest(candidate),
        "frame": copy.deepcopy(candidate),
        "result": {
            "recorded": True,
            "evidence_id": evidence_id,
            "interrupt_id": "interrupt-1",
        },
    }
    record["progress_watermark"] = 10
    store.documents["controller.json"] = raw
    before = copy.deepcopy(store.documents["controller.json"])

    with pytest.raises(ControllerError):
        ManagedController(
            store,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="daemon-test",
        )
    assert store.documents["controller.json"] == before


def test_missing_one_terminal_in_two_child_roster_blocks_graph(tmp_path):
    controller, _store, frame = _two_child_interrupt(tmp_path)
    frames = [
        candidate
        for candidate in _fact_frames(frame)
        if not (
            candidate["evidence"]["kind"] == "member-terminal"
            and candidate["evidence"]["data"]["task_id"] == "task-2"
        )
    ]
    _persist_frames(controller, frames)

    summary = _summary(controller, "interrupt-two-child")
    children = {child["task_id"]: child for child in summary["children"]}

    assert set(children) == {"task-1", "task-2"}
    assert {
        row["admission_id"] for row in summary["admissions"]
    } == {"admission-1", "admission-2"}
    assert children["task-1"]["status"] == "stopped"
    assert children["task-2"]["status"] is None
    assert "child-terminal-missing:admission-2" in children["task-2"][
        "blockers"
    ]
    assert summary["graph_quiescent"] is False


def test_opaque_descendant_is_unproven_even_when_it_matches_a_sealed_agent(
    tmp_path,
):
    def roster_factory(admission):
        roster = _roster(admission)
        # This is deliberately the actual sealed agent ID, not a made-up
        # value; the current schema still provides no typed descendant link.
        roster["descendant_ids"] = [roster["children"][0]["agent_id"]]
        return roster

    controller, _store, frame = _new_interrupt(
        tmp_path,
        roster_factory=roster_factory,
    )
    _persist_frames(controller, _fact_frames(frame))

    summary = _summary(controller)

    assert json.dumps(summary["process_exclusion"], sort_keys=True).casefold().find(
        "excluded"
    ) >= 0
    assert summary["graph_quiescent"] is False
    descendant = next(
        row
        for row in summary["descendants"]
        if row["descendant_id"] == "agent-1"
    )
    assert descendant["mapped_admission_id"] is None
    assert descendant["resolved"] is False
    _assert_blocker_mentions(summary, "descendant")


@pytest.mark.parametrize(
    ("parent_state", "omit_parent_fact"),
    [("idle", True), ("active", False)],
)
def test_parent_idle_at_seal_and_active_parent_drain_are_distinct_valid_facts(
    tmp_path, parent_state, omit_parent_fact
):
    def roster_factory(admission):
        roster = _roster(admission)
        roster["parent_state"] = parent_state
        return roster

    controller, _store, frame = _new_interrupt(
        tmp_path,
        roster_factory=roster_factory,
    )
    omit = {"parent-drained"} if omit_parent_fact else set()
    _persist_frames(controller, _fact_frames(frame, omit=omit))
    if parent_state == "active":
        # A later positively idle observation is compatible with the earlier
        # drained observation; distinct evidence IDs do not make a semantic
        # conflict.
        _persist(
            controller,
            frame,
            "parent-drained",
            evidence_id="evidence-parent-idle",
            observed_watermark=10,
            updates={"state": "idle"},
        )

    summary = _summary(controller)

    assert summary["graph_quiescent"] is True
    assert "parent-drain-missing" not in _blocker_text(summary)
    assert "parent-drained-conflict" not in _blocker_text(summary)


def test_unknown_request_count_history_remains_after_later_zero(tmp_path):
    controller, _store, frame = _new_interrupt(tmp_path)
    frames = _fact_frames(
        frame,
        omit={"request-observation"},
    )
    earlier = _evidence(
        frame,
        "request-observation",
        evidence_id="evidence-request-earlier",
        observed_watermark=9,
        data={
            **_evidence(frame, "request-observation")["evidence"]["data"],
            "new_requests": None,
            "observable": True,
            "through_watermark": 9,
        },
    )
    later = _evidence(
        frame,
        "request-observation",
        evidence_id="evidence-request-later-zero",
        observed_watermark=10,
        data={
            **_evidence(frame, "request-observation")["evidence"]["data"],
            "through_watermark": 10,
            "new_requests": 0,
            "observable": True,
        },
    )
    _persist_frames(controller, frames + [earlier, later])

    summary = _summary(controller)

    assert summary["graph_quiescent"] is True
    request = summary["request_observation"]
    assert request["new_requests"] == 0
    assert request["unknown_count_history"] is True
    assert request["positive_new_requests"] is False
    assert request["through_watermark"] == 10
    _assert_blocker_mentions(summary, "unknown-count-history")
    assert request["pre_entry_observation_proven"] is False


def test_unobservable_request_history_remains_after_later_observable_zero(
    tmp_path,
):
    controller, _store, frame = _new_interrupt(tmp_path)
    frames = _fact_frames(
        frame,
        omit={"request-observation"},
    )
    earlier = _evidence(
        frame,
        "request-observation",
        evidence_id="evidence-request-unobservable",
        observed_watermark=9,
        data={
            **_evidence(frame, "request-observation")["evidence"]["data"],
            "through_watermark": 9,
            "new_requests": 0,
            "observable": False,
        },
    )
    later = _evidence(
        frame,
        "request-observation",
        evidence_id="evidence-request-observable-zero",
        observed_watermark=10,
        data={
            **_evidence(frame, "request-observation")["evidence"]["data"],
            "through_watermark": 10,
            "new_requests": 0,
            "observable": True,
        },
    )

    # Both observations go through the public persistence validator; no raw
    # record is manufactured to bypass request-history checks.
    _persist_frames(controller, frames + [earlier, later])

    summary = _summary(controller)

    assert summary["graph_quiescent"] is True
    request = summary["request_observation"]
    assert request["observable"] is False
    assert request["new_requests"] == 0
    _assert_blocker_mentions(summary, "request-observation-unobservable")
    assert "request-observation-unobservable" in request["blockers"]


def test_positive_request_count_regression_is_refused_and_prior_fact_remains(
    tmp_path,
):
    controller, store, frame = _new_interrupt(tmp_path)
    frames = _fact_frames(
        frame,
        omit={"request-observation"},
    )
    earlier = _evidence(
        frame,
        "request-observation",
        evidence_id="evidence-request-positive",
        observed_watermark=9,
        data={
            **_evidence(frame, "request-observation")["evidence"]["data"],
            "through_watermark": 9,
            "new_requests": 1,
            "observable": True,
        },
    )
    _persist_frames(controller, frames + [earlier])
    before = copy.deepcopy(store.documents["controller.json"])
    later = _evidence(
        frame,
        "request-observation",
        evidence_id="evidence-request-later-zero",
        observed_watermark=10,
        data={
            **_evidence(frame, "request-observation")["evidence"]["data"],
            "through_watermark": 10,
            "new_requests": 0,
            "observable": True,
        },
    )

    with pytest.raises(ControllerError) as raised:
        controller.persist_coordinator_interrupt_evidence(later)

    assert raised.value.code == "stale-generation"
    assert store.documents["controller.json"] == before
    summary = _summary(controller)
    request = summary["request_observation"]
    assert request["new_requests"] == 1
    assert request["positive_new_requests"] is True
    assert request["latest_evidence_id"] == "evidence-request-positive"
    _assert_blocker_mentions(summary, "positive")


def test_request_latest_watermark_gap_keeps_pre_entry_coverage_unproven(tmp_path):
    controller, _store, frame = _new_interrupt(tmp_path)
    frames = _fact_frames(
        frame,
        request_data={"new_requests": 0, "observable": True},
        request_observed_watermark=9,
    )
    # The latest request interval stops at 9 while another validated fact has
    # advanced the durable progress watermark to 10.
    frames.append(
        _evidence(
            frame,
            "process-excluded",
            evidence_id="evidence-process-later",
            observed_watermark=10,
        )
    )
    _persist_frames(controller, frames)

    summary = _summary(controller)

    assert summary["graph_quiescent"] is True
    assert summary["progress_watermark"] == 10
    assert summary["request_observation"]["coverage_gap"] is True
    _assert_blocker_mentions(summary, "coverage-gap")
    assert summary["request_observation"]["pre_entry_observation_proven"] is False


def test_unknown_process_exclusion_is_accepted_but_remains_a_separate_blocker(
    tmp_path,
):
    controller, _store, frame = _new_interrupt(tmp_path)
    _persist_frames(
        controller,
        _fact_frames(frame, process_status="unknown"),
    )

    summary = _summary(controller)

    assert summary["graph_quiescent"] is True
    assert summary["process_exclusion"]["status"] == "unknown"
    _assert_blocker_mentions(summary, "process")


def test_observable_zero_requests_does_not_prove_external_entry_coverage(tmp_path):
    controller, _store, frame = _new_interrupt(tmp_path)
    _persist_frames(
        controller,
        _fact_frames(
            frame,
            request_data={"new_requests": 0, "observable": True},
        ),
    )

    summary = _summary(controller)

    assert summary["graph_quiescent"] is True
    blocker_text = _blocker_text(summary)
    assert "request" in blocker_text and "entry" in blocker_text
    assert summary["request_observation"][
        "external_entry_coverage_proven"
    ] is False
    assert not any(
        key.casefold() in {"safe_to_restore", "support", "runtime_support"}
        for key in summary
    )


def test_reloaded_projection_matches_current_and_status_mapping(tmp_path):
    controller, store, frame = _new_interrupt(tmp_path)
    _persist_frames(controller, _fact_frames(frame))
    expected = controller.coordinator_interrupt_status("interrupt-1")

    reloaded = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )

    assert reloaded.coordinator_interrupt_status("interrupt-1") == expected
    assert reloaded.status()["coordinator_interrupt_summaries"] == {
        "interrupt-1": expected
    }


def test_unknown_interrupt_id_refuses_without_mutating_durable_state(tmp_path):
    controller, store, frame = _new_interrupt(tmp_path)
    _persist(controller, frame, "runtime-ack")
    before = _read_snapshot(store, "interrupt-1")

    with pytest.raises(ControllerError) as raised:
        controller.coordinator_interrupt_status("interrupt-does-not-exist")
    assert raised.value.code == "unknown"
    assert _read_snapshot(store, "interrupt-1") == before


@pytest.mark.parametrize("corruption", ["missing-evidence", "progress-drift"])
def test_invalid_durable_record_refuses_projection_instead_of_summarizing(
    tmp_path, corruption
):
    controller, store, frame = _new_interrupt(tmp_path)
    _persist(controller, frame, "runtime-ack")
    raw = copy.deepcopy(store.documents["controller.json"])
    record = raw["coordinator_interrupts"]["interrupt-1"]
    if corruption == "missing-evidence":
        del record["evidence"]
    else:
        record["progress_watermark"] = (
            frame["interrupt"]["roster_seal_watermark"] - 1
        )
    store.documents["controller.json"] = raw
    before = copy.deepcopy(store.documents["controller.json"])

    with pytest.raises(ControllerError):
        controller.coordinator_interrupt_status("interrupt-1")
    assert store.documents["controller.json"] == before


def test_projection_and_status_results_are_defensively_copied(tmp_path):
    controller, store, frame = _new_interrupt(tmp_path)
    _persist(controller, frame, "runtime-ack")
    baseline = controller.coordinator_interrupt_status("interrupt-1")
    public_baseline = controller.status()
    durable_before = copy.deepcopy(store.documents["controller.json"])

    result = controller.coordinator_interrupt_status("interrupt-1")
    result["children"][0]["status"] = "forged"
    result["children"][0]["blockers"].append("forged-child")
    result["process_exclusion"]["status"] = "forged"
    result["process_exclusion"]["blockers"].append("forged-process")
    result["request_observation"]["new_requests"] = 999
    result["request_observation"]["blockers"].append("forged-request")
    result["blockers"].append({"kind": "forged"})

    public = controller.status()
    public["coordinator_interrupt_summaries"]["interrupt-1"]["children"][0][
        "status"
    ] = "forged-public"
    public["coordinator_interrupt_summaries"]["interrupt-1"][
        "process_exclusion"
    ]["status"] = "forged-public"
    public["coordinator_interrupt_summaries"]["interrupt-1"][
        "request_observation"
    ]["new_requests"] = 1000
    public["coordinator_interrupt_summaries"]["interrupt-1"][
        "request_observation"
    ]["blockers"].append("forged-public-request")
    public["coordinator_interrupt_summaries"]["interrupt-1"]["blockers"].append(
        {"kind": "forged-public"}
    )

    assert controller.coordinator_interrupt_status("interrupt-1") == baseline
    assert controller.status() == public_baseline
    assert store.documents["controller.json"] == durable_before
