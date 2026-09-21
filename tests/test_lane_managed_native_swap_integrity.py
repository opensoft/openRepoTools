# SPDX-License-Identifier: Apache-2.0
"""Adversarial reload coverage for native-swap evidence and release authority.

These tests begin with the public native-swap integration harness, clone a
complete durable controller snapshot, and then alter one nested fact at a
time.  Stage and archive digests are recomputed after each edit, so a reload
refusal must come from the durable authority joins rather than from a stale
outer checksum.  No finalized phase or positive runtime result is
constructed by hand.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from lane_managed_controller import ControllerError, ManagedController
from test_lane_managed_native_swap_integration import (
    EVIDENCE_STAGES,
    NativeSwapEvidenceProvider,
    NativeSwapRuntime,
    _digest,
    _harness,
    _start_and_release,
    _reload_fixture_controller,
)


_STAGE_BINDING_TAMPERS = (
    "operation_id",
    "request_epoch_id",
    "target_spec_digest",
    "source_archive_digest",
    "interrupt_id",
    "runtime_identity_digest",
)
_SATISFACTION_FACTS = (
    "observable",
    "continuous",
    "new_requests",
    "cleared",
)


def _active_operation(record: Mapping[str, Any]) -> dict[str, Any]:
    operation_id = record.get("active_operation_id")
    assert isinstance(operation_id, str) and operation_id
    operations = record.get("operations")
    assert isinstance(operations, list)
    operation = next(
        item for item in operations
        if isinstance(item, Mapping) and item.get("operation_id") == operation_id
    )
    assert isinstance(operation, dict)
    return operation


def _native_swap(record: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _active_operation(record).get("metadata")
    assert isinstance(metadata, Mapping)
    native_swap = metadata.get("native_swap")
    assert isinstance(native_swap, dict)
    return native_swap


def _load_clone(record: Mapping[str, Any]) -> ManagedController:
    """Load a detached controller clone with no runtime authority."""
    return ManagedController(
        {"controller.json": copy.deepcopy(dict(record))},
        runtime=None,
        clock=lambda: 1000.0,
    )


def _assert_reload_refuses(
        record: Mapping[str, Any], *, expected_code: str | None = None,
) -> None:
    """Require refusal while proving the detached candidate is not rewritten."""
    candidate = {"controller.json": copy.deepcopy(dict(record))}
    before = copy.deepcopy(candidate["controller.json"])
    with pytest.raises(ControllerError) as raised:
        _load_clone(candidate["controller.json"])
    assert candidate["controller.json"] == before
    if expected_code is not None:
        assert raised.value.code == expected_code
        return
    assert raised.value.code in {
        "invalid",
        "stale-generation",
        "ownership-conflict",
        "permission-mismatch",
        "unsupported",
    }


@contextmanager
def _real_native_swap_snapshot(
        tmp_path: Path, *, phase: str,
) -> Iterator[tuple[Any, dict[str, Any]]]:
    """Yield a real public-harness snapshot at ``ready-held`` or ``released``."""
    assert phase in {"ready-held", "released"}
    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime()
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        swapped = fixture.request(
            "native-swap-integrity-setup", "swap", {"profile": "team-b"}
        )
        assert swapped["ok"] is True
        assert swapped["result"]["phase"] == "ready-held"
        expected_stages = EVIDENCE_STAGES[:4]
        if phase == "released":
            released = fixture.request(
                "native-swap-integrity-setup-release",
                "release",
                {"operation_id": swapped["result"]["operation_id"]},
            )
            assert released["ok"] is True
            assert released["result"]["phase"] == "released"
            expected_stages = EVIDENCE_STAGES
        snapshot = copy.deepcopy(fixture.state.read_json("controller.json"))
        native_swap = _native_swap(snapshot)
        evidence = native_swap.get("native_swap_evidence")
        assert isinstance(evidence, Mapping)
        assert set(evidence) == set(expected_stages)
        assert tuple(stage for stage in EVIDENCE_STAGES if stage in evidence) == tuple(
            expected_stages
        )
        # Prove the unedited detached snapshot is accepted before introducing
        # an adversarial but body-valid mutation.
        _load_clone(snapshot)
        yield fixture, snapshot


def _recompute_stage_digests(native_swap: dict[str, Any]) -> None:
    evidence = native_swap.get("native_swap_evidence")
    assert isinstance(evidence, dict)
    for record in evidence.values():
        assert isinstance(record, dict)
        observation = record.get("observation")
        assert isinstance(observation, Mapping)
        record["evidence_digest"] = _digest(observation)

    capture = native_swap.get("entry_capture")
    if isinstance(capture, dict) and capture.get("state") == "accepted":
        entry = evidence.get("entry")
        assert isinstance(entry, Mapping)
        capture["observation_digest"] = entry["evidence_digest"]


def _tamper_stage_bindings(native_swap: dict[str, Any], field: str) -> None:
    """Rewrite one binding uniformly while retaining a valid stage stream."""
    assert field in _STAGE_BINDING_TAMPERS
    evidence = native_swap.get("native_swap_evidence")
    assert isinstance(evidence, dict)

    forged_text = "native-swap-integrity-forged-" + field
    forged_digest = _digest({"native_swap_integrity_forged": field})
    for record in evidence.values():
        assert isinstance(record, dict)
        observation = record.get("observation")
        assert isinstance(observation, dict)
        binding = observation.get("binding")
        assert isinstance(binding, dict)
        if field in {
            "operation_id",
            "request_epoch_id",
            "target_spec_digest",
        }:
            binding[field] = forged_text if field != "target_spec_digest" else forged_digest
        elif field == "source_archive_digest":
            if binding.get("source_archive_digest") is not None:
                binding["source_archive_digest"] = forged_digest
        elif field == "interrupt_id":
            if binding.get("interrupt_id") is not None:
                binding["interrupt_id"] = forged_text
                binding["interrupt_intent_digest"] = forged_digest
                clear = observation.get("worker_state_clear")
                assert isinstance(clear, dict)
                clear["interrupt_id"] = forged_text
        elif field == "runtime_identity_digest":
            observation["runtime_identity_digest"] = forged_digest
            # Keep the provider stream body-valid against the candidate's
            # selected pin.  The real target capability gate remains the
            # independent authority and must reject this recomputed pin on
            # reload.
            native_swap["runtime_identity_digest"] = forged_digest

        if field == "request_epoch_id":
            request_observation = observation.get("request_observation")
            assert isinstance(request_observation, dict)
            request_observation["epoch_id"] = forged_text

    # The release-boundary receipt is part of the stage observation.  If the
    # immutable operation/epoch binding is forged, update its nested release
    # binding and self-digest too; otherwise the test would only prove that a
    # nested receipt was malformed, not that the stage authority was missing.
    boundary_record = evidence.get("release-boundary")
    if field in {"operation_id", "request_epoch_id"} and isinstance(
            boundary_record, Mapping
    ):
        observation = boundary_record["observation"]
        boundary = observation["binding"]["release_boundary"]
        assert isinstance(boundary, dict)
        release_binding = boundary.get("binding")
        assert isinstance(release_binding, dict)
        release_binding[field] = forged_text
        release_binding["binding_digest"] = _digest({
            key: value for key, value in release_binding.items()
            if key != "binding_digest"
        })

    _recompute_stage_digests(native_swap)
    if isinstance(boundary_record, Mapping):
        observation = boundary_record["observation"]
        boundary = observation["binding"].get("release_boundary")
        if isinstance(boundary, Mapping):
            release_binding = boundary.get("binding")
            if isinstance(release_binding, dict):
                pre_release = evidence.get("pre-release")
                assert isinstance(pre_release, Mapping)
                release_binding["pre_release_evidence_digest"] = pre_release[
                    "evidence_digest"
                ]
                release_binding["binding_digest"] = _digest({
                    key: value for key, value in release_binding.items()
                    if key != "binding_digest"
                })
                boundary_record["evidence_digest"] = _digest(observation)


@pytest.mark.parametrize("phase", ("ready-held", "released"))
@pytest.mark.parametrize("field", _STAGE_BINDING_TAMPERS)
def test_reloaded_native_swap_rejects_recomputed_stage_binding_tamper(
        tmp_path: Path, phase: str, field: str,
) -> None:
    """Stage-local canonical hashes cannot replace operation authority joins."""
    with _real_native_swap_snapshot(tmp_path, phase=phase) as (_fixture, snapshot):
        candidate = copy.deepcopy(snapshot)
        native_swap = _native_swap(candidate)
        _tamper_stage_bindings(native_swap, field)
        _assert_reload_refuses(candidate)


def _tamper_satisfaction_fact(native_swap: dict[str, Any], phase: str, field: str) -> None:
    evidence = native_swap.get("native_swap_evidence")
    assert isinstance(evidence, dict)
    stage = "target-held" if phase == "ready-held" else "release-boundary"
    record = evidence.get(stage)
    assert isinstance(record, dict)
    observation = record.get("observation")
    assert isinstance(observation, dict)
    if field in {"observable", "continuous", "new_requests"}:
        request_observation = observation.get("request_observation")
        assert isinstance(request_observation, dict)
        request_observation[field] = {
            "observable": False,
            "continuous": False,
            "new_requests": 1,
        }[field]
    else:
        clear = observation.get("worker_state_clear")
        assert isinstance(clear, dict)
        clear["cleared"] = False
    record["evidence_digest"] = _digest(observation)


@pytest.mark.parametrize("phase", ("ready-held", "released"))
@pytest.mark.parametrize("field", _SATISFACTION_FACTS)
def test_reloaded_native_swap_rejects_body_valid_negative_satisfaction(
        tmp_path: Path, phase: str, field: str,
) -> None:
    """A body-valid negative observation cannot leave a ready phase accepted."""
    with _real_native_swap_snapshot(tmp_path, phase=phase) as (_fixture, snapshot):
        candidate = copy.deepcopy(snapshot)
        native_swap = _native_swap(candidate)
        _tamper_satisfaction_fact(native_swap, phase, field)
        assert _active_operation(candidate)["phase"] == phase
        # These observations are structurally valid but cannot prove safety.
        # Require the precise uncertainty refusal, not a malformed-record code.
        _assert_reload_refuses(candidate, expected_code="uncertain-effect")


def _tamper_archive_conflict(snapshot: dict[str, Any], conflict: str) -> None:
    native_swap = _native_swap(snapshot)
    archive_id = native_swap.get("source_archive_id")
    archives = snapshot.get("native_source_archives")
    assert isinstance(archive_id, str) and isinstance(archives, dict)
    archive = archives.get(archive_id)
    assert isinstance(archive, dict)
    archive_snapshot = archive.get("snapshot")
    assert isinstance(archive_snapshot, dict)
    archive_operations = archive_snapshot.get("operations")
    assert isinstance(archive_operations, list)
    archived_operation = next(
        item for item in archive_operations
        if isinstance(item, Mapping)
        and item.get("operation_id") == archive.get("operation_id")
    )
    archived_metadata = archived_operation.get("metadata")
    assert isinstance(archived_metadata, dict)
    archived_native_swap = archived_metadata.get("native_swap")
    assert isinstance(archived_native_swap, dict)

    if conflict == "context":
        context = archive_snapshot.get("native_context")
        assert isinstance(context, dict)
        forged_runner = "native-swap-archive-context-conflict"
        context["runner_incarnation"] = forged_runner
        # Keep the historical snapshot body-valid while deliberately leaving
        # its immutable startup descriptor on the old runner.  Recompute the
        # context digest and identity so this is not a checksum-only case.
        archived_native_swap["source_context"] = copy.deepcopy(context)
        archived_native_swap["source_context_digest"] = _digest(context)
        archived_native_swap["source_identity"]["runner_incarnation"] = forged_runner
        archive["source_identity"]["runner_incarnation"] = forged_runner
    else:
        source_startup = archived_native_swap.get("source_startup")
        assert isinstance(source_startup, dict)
        source_startup["runner_incarnation"] = (
            "native-swap-archive-startup-conflict"
        )

    archive["snapshot_digest"] = _digest(archive_snapshot)


@pytest.mark.parametrize("conflict", ("context", "startup"))
def test_native_source_archive_context_startup_conflict_refuses_on_reload(
        tmp_path: Path, conflict: str,
) -> None:
    """Historical archive joins are checked by a fresh reader, not only writes."""
    with _real_native_swap_snapshot(tmp_path, phase="ready-held") as (
            _fixture, snapshot
    ):
        candidate = copy.deepcopy(snapshot)
        _tamper_archive_conflict(candidate, conflict)
        _assert_reload_refuses(candidate)


def test_completed_six_stage_authorization_retry_is_false_without_regrant(
        tmp_path: Path,
) -> None:
    """An exact post-reload authorization retry observes the first grant only."""
    with _real_native_swap_snapshot(tmp_path, phase="released") as (fixture, snapshot):
        native_swap = _native_swap(snapshot)
        evidence = native_swap["native_swap_evidence"]
        assert set(evidence) == set(EVIDENCE_STAGES)
        assert tuple(stage for stage in EVIDENCE_STAGES if stage in evidence) == tuple(
            EVIDENCE_STAGES
        )
        binding = native_swap.get("release_binding")
        authorization = native_swap.get("release_authorization")
        validation_id = native_swap.get("release_validation_id")
        assert isinstance(binding, Mapping)
        assert isinstance(authorization, Mapping)
        assert authorization["authorized"] is True
        assert isinstance(validation_id, str) and validation_id
        authorization_id = authorization["authorization_id"]
        release_count = len(fixture.runtime.release_calls)
        gate_count = len(fixture.runtime.gate_receipts)
        claims_before = fixture.state.read_lineage_claims()
        durable_before = fixture.state.read_json("controller.json")

        _reload_fixture_controller(fixture)
        callback = fixture.runtime._native_swap_release_callback
        assert callable(callback)
        acknowledgement = callback(
            binding["participant_id"],
            binding["session_id"],
            binding["runner_incarnation"],
            validation_id,
            copy.deepcopy(dict(binding)),
        )
        if inspect.isawaitable(acknowledgement):
            acknowledgement = asyncio.run(acknowledgement)
        assert isinstance(acknowledgement, Mapping)
        assert acknowledgement["authorized"] is False
        assert acknowledgement["authorization_id"] == authorization_id
        assert acknowledgement["binding"] == binding
        assert acknowledgement["authorization_digest"] == _digest({
            key: value for key, value in acknowledgement.items()
            if key != "authorization_digest"
        })
        assert len(fixture.runtime.release_calls) == release_count
        assert len(fixture.runtime.gate_receipts) == gate_count
        assert fixture.state.read_lineage_claims() == claims_before
        assert fixture.state.read_json("controller.json") == durable_before
