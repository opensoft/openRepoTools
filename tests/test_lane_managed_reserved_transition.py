# SPDX-License-Identifier: Apache-2.0
"""Focused tests for the swap-only reserved-to-written transition."""

from __future__ import annotations

import asyncio
import copy

import pytest

import test_lane_managed_controller as base
from lane_managed_controller import ControllerError
from test_lane_managed_controller import (
    COORDINATOR_SESSION,
    RESERVED_SESSION,
    SwapRuntime,
    _assert_error,
    _operation_record,
    _release_state,
    _run_swap,
    _runtime_writes_target_transcript_holders,
    _successful_swap_statuses,
    _swap_open_result,
    _swap_roster,
    _value,
)


def _reserved_roster():
    statuses = _successful_swap_statuses()
    statuses["worker-a"] = [
        base._swap_status(
            "worker-a", RESERVED_SESSION
        )
    ]
    runtime = SwapRuntime(statuses)
    metadata = base._source_metadata(
        RESERVED_SESSION,
        transcript_exists=False,
        transcript_written=False,
        transcript_reserved=True,
    )
    metadata["runner_spec"]["mode"] = "fresh"
    metadata["runner_spec"]["fresh"] = True
    metadata["runner_spec"].pop("resume", None)
    controller, store, _ = _swap_roster(
        runtime,
        participant_metadata={"worker-a": metadata},
        participant_sessions={"worker-a": RESERVED_SESSION},
    )
    return controller, store, runtime


def _written_reserved_roster():
    controller, store, runtime = _reserved_roster()
    first = _run_swap(controller, request_id="reserved-seed")
    _runtime_writes_target_transcript_holders(store, runtime)
    first_record = _operation_record(store, "reserved-seed")
    runner_instances = first_record["metadata"]["runner_instances"]
    _release_state(controller, first)
    for participant_id, session_id in (
        ("coordinator", COORDINATOR_SESSION),
        ("worker-a", RESERVED_SESSION),
        ("worker-b", base.WORKER_B_SESSION),
    ):
        runtime.statuses[participant_id] = [
            _swap_open_result(
                participant_id,
                session_id,
                runner_instance_id=runner_instances[participant_id],
            )
        ]
    return controller, store, runtime


def test_swap_promotes_written_reserved_target_before_persist_and_open():
    controller, store, runtime = _reserved_roster()

    first = _run_swap(controller, request_id="reserved-fresh")
    assert _value(first, "phase") == "ready-held"
    _runtime_writes_target_transcript_holders(store, runtime)
    first_record = _operation_record(store, "reserved-fresh")
    runner_instances = first_record["metadata"]["runner_instances"]
    _release_state(controller, first)
    for participant_id, session_id in (
        ("coordinator", COORDINATOR_SESSION),
        ("worker-a", RESERVED_SESSION),
        ("worker-b", base.WORKER_B_SESSION),
    ):
        runtime.statuses[participant_id] = [
            _swap_open_result(
                participant_id,
                session_id,
                runner_instance_id=runner_instances[participant_id],
            )
        ]

    prior_open_count = len(runtime.opened)
    second = _run_swap(controller, request_id="reserved-resume")

    assert _value(second, "phase") == "ready-held"
    record = _operation_record(store, "reserved-resume")
    target = record["metadata"]["target_specs"]["worker-a"]
    assert target["mode"] == "resume"
    assert target.get("resume") is True
    assert "fresh" not in target
    opened = [
        spec for participant_id, spec in runtime.opened[prior_open_count:]
        if participant_id == "worker-a"
    ]
    assert len(opened) == 1
    assert opened[0]["mode"] == "resume"
    assert opened[0].get("fresh") is not True


def test_explicit_fresh_against_written_history_refuses_before_runtime():
    controller, store, runtime = _reserved_roster()

    first = _run_swap(controller, request_id="reserved-fresh-explicit")
    _runtime_writes_target_transcript_holders(store, runtime)
    _release_state(controller, first)
    before = copy.deepcopy(runtime.calls)
    specs = {
        participant_id: copy.deepcopy(participant.metadata["runner_spec"])
        for participant_id, participant in controller._participants.items()
        if participant.state.casefold() not in {"completed", "stopped"}
    }
    specs["worker-a"]["mode"] = "fresh"
    specs["worker-a"]["fresh"] = True
    specs["worker-a"].pop("resume", None)

    with pytest.raises(ControllerError) as raised:
        asyncio.run(
            controller.swap(
                "reserved-explicit-fresh",
                7,
                base.SWAP_PROFILE,
                runner_specs=specs,
            )
        )

    _assert_error(raised, "ownership-conflict")
    assert runtime.calls == before
    assert _operation_record(store, "reserved-explicit-fresh")["phase"] == "failed"


def test_written_fresh_without_exact_holder_refuses_before_metadata_mutation():
    controller, store, runtime = _reserved_roster()
    evidence = store.transcript_evidence["worker-a"]
    evidence["transcript"].update({
        "exists": True,
        "written": True,
        "reserved": False,
    })
    before_metadata = copy.deepcopy(
        controller._participants["worker-a"].metadata["runner_spec"]
    )

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller, request_id="reserved-no-holder")

    _assert_error(raised, "profile-mismatch")
    assert runtime.calls == []
    assert controller._participants["worker-a"].metadata["runner_spec"] == before_metadata


def test_written_fresh_with_ambiguous_holder_refuses_before_runtime():
    controller, store, runtime = _written_reserved_roster()
    holders = copy.deepcopy(store.transcript_evidence["worker-a"]["holders"])
    store.transcript_evidence["worker-a"]["holders"] = holders + [copy.deepcopy(holders[0])]
    before = copy.deepcopy(runtime.calls)

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller, request_id="reserved-ambiguous")

    _assert_error(raised, "ownership-conflict")
    assert runtime.calls == before


def test_written_fresh_with_foreign_holder_refuses_before_runtime():
    controller, store, runtime = _written_reserved_roster()
    store.transcript_evidence["worker-a"]["holders"][0]["session_id"] = "foreign-session"
    before = copy.deepcopy(runtime.calls)

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller, request_id="reserved-foreign")

    _assert_error(raised, "ownership-conflict")
    assert runtime.calls == before
