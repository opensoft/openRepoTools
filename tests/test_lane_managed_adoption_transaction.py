# SPDX-License-Identifier: Apache-2.0
"""Real-store tests for the bounded native lineage adoption ledger.

These tests exercise only the state-side ownership descriptor transaction.  The
intent carries evidence already bound by the controller-side internal seam;
the state store does not own or invoke that provider.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from lane_managed_state import (
    ManagedStateError,
    _native_digest,
    native_record_marker,
)
from test_lane_managed_lineage_transfer import _seed_source


INTENT_FIELDS = {
    "schema_version",
    "architecture",
    "record_kind",
    "adoption_id",
    "archive_id",
    "archive_digest",
    "operation_id",
    "owner_generation",
    "expected_daemon_id",
    "source_identity",
    "source_claim",
    "target_claim",
    "source_claim_digest",
    "target_claim_digest",
    "evidence_digest",
    "runtime_identity_digest",
    "evidence_reference",
    "intent_digest",
    "phase",
    "controller_commit_digest",
}


def _target(source, *, lineage_id="adoption-target-lineage",
            coordinator_session_uuid="adoption-target-coordinator"):
    target = dict(source)
    target.update({
        "lineage_id": lineage_id,
        "coordinator_session_uuid": coordinator_session_uuid,
        "lineage_generation": source["lineage_generation"] + 1,
    })
    return target


def _archive_snapshot(source):
    return {
        "native_context": {
            "lineage": {
                "workspace_claim": {
                    "workspace": source["workspace"],
                    "common_dir": source["common_dir"],
                    "repository": source["repository"],
                },
            },
        },
    }


def _evidence_facts(binding):
    runtime_identity_digest = "b" * 64
    evidence_reference = "fixture://native-adoption/evidence-1"
    response = {
        **copy.deepcopy(binding),
        "runtime_identity_digest": runtime_identity_digest,
        "evidence_reference": evidence_reference,
        "source_writers_excluded": True,
        "source_effects_resolved": True,
        "native_worker_state_cleared": True,
        "control_epoch_request_free": True,
        "target_startup_hold_supported": True,
    }
    # The controller computes the digest of the complete response.  The
    # response itself has no self-referential evidence_digest field.
    return response, _native_digest(response), runtime_identity_digest, evidence_reference


def _intent(store, owner, source, target, evidence_digest, runtime_digest,
            evidence_ref):
    source_identity = {
        "owner_generation": owner["generation"],
        "lineage_id": source["lineage_id"],
        "lineage_generation": source["lineage_generation"],
        "session_uuid": source["coordinator_session_uuid"],
        "runner_incarnation": "runner-native-adoption",
        "invocation_id": "invocation-native-adoption",
    }
    binding = {
        "adoption_id": "adoption-1",
        "archive_id": "archive-1",
        "archive_digest": _native_digest(_archive_snapshot(source)),
        "operation_id": "operation-adoption-1",
        "owner_generation": owner["generation"],
        "expected_daemon_id": owner["daemon_id"],
        "source_identity": source_identity,
        "source_claim_digest": _native_digest(source),
        "target_claim_digest": _native_digest(target),
    }
    candidate = {
        **native_record_marker("native-adoption-intent"),
        **binding,
        "source_claim": copy.deepcopy(source),
        "target_claim": copy.deepcopy(target),
        "evidence_digest": evidence_digest,
        "runtime_identity_digest": runtime_digest,
        "evidence_reference": evidence_ref,
        "phase": "prepared",
        "controller_commit_digest": None,
    }
    candidate["intent_digest"] = store._native_adoption_intent_digest(candidate)
    assert set(candidate) == INTENT_FIELDS
    return candidate


def _controller_record(intent, *, controller_phase="prepared",
                      operation_phase="paused"):
    snapshot = _archive_snapshot(intent["source_claim"])
    source_identity = copy.deepcopy(intent["source_identity"])
    archive = {
        **native_record_marker("native-source-archive"),
        "archive_id": intent["archive_id"],
        "operation_id": intent["operation_id"],
        "source_identity": source_identity,
        "snapshot_digest": _native_digest(snapshot),
        "snapshot": snapshot,
    }
    assert archive["snapshot_digest"] == intent["archive_digest"]
    reference = {
        "adoption_id": intent["adoption_id"],
        "intent_digest": intent["intent_digest"],
        "archive_id": intent["archive_id"],
        "archive_digest": intent["archive_digest"],
        "target_claim_digest": intent["target_claim_digest"],
        "phase": controller_phase,
    }
    return {
        **native_record_marker("controller"),
        "generation": intent["owner_generation"],
        "coordinator_id": "coordinator-native-adoption",
        "active_operation_id": intent["operation_id"],
        "operations": [{
            "operation_id": intent["operation_id"],
            "generation": intent["owner_generation"],
            "phase": operation_phase,
            "metadata": {"native_adoption": reference},
        }],
        "native_source_archives": {intent["archive_id"]: archive},
    }


def _fixture(managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace,
        tmp_path,
        lane="adoption-transaction",
        daemon_id="daemon-adoption-transaction",
        lineage_id="adoption-source-lineage",
        coordinator_session_uuid="adoption-source-coordinator",
    )
    target = _target(source)
    binding = {
        "adoption_id": "adoption-1",
        "archive_id": "archive-1",
        "archive_digest": _native_digest(_archive_snapshot(source)),
        "operation_id": "operation-adoption-1",
        "owner_generation": owner["generation"],
        "expected_daemon_id": owner["daemon_id"],
        "source_identity": {
            "owner_generation": owner["generation"],
            "lineage_id": source["lineage_id"],
            "lineage_generation": source["lineage_generation"],
            "session_uuid": source["coordinator_session_uuid"],
            "runner_incarnation": "runner-native-adoption",
            "invocation_id": "invocation-native-adoption",
        },
        "source_claim_digest": _native_digest(source),
        "target_claim_digest": _native_digest(target),
    }
    _evidence, evidence_digest, runtime_digest, evidence_ref = _evidence_facts(binding)
    intent = _intent(
        store, owner, source, target, evidence_digest, runtime_digest, evidence_ref,
    )
    store.write_json("controller.json", _controller_record(intent))
    return store, owner, source, target, intent


def _ledger_path(store):
    return store.identity.state_root / "native-adoptions.json"


def _controller_commit(store, intent):
    record = json.loads((store.identity.state_root / "controller.json").read_text())
    record["operations"][0]["metadata"]["native_adoption"]["phase"] = (
        "controller-committed"
    )
    store.write_json("controller.json", record)
    return _native_digest(record)


def _set_controller_phase(store, phase):
    record = json.loads((store.identity.state_root / "controller.json").read_text())
    record["operations"][0]["metadata"]["native_adoption"]["phase"] = phase
    store.write_json("controller.json", record)


def test_prepare_apply_finalize_uses_exact_ledger_and_target_descriptor(
        managed_workspace, tmp_path: Path):
    store, owner, source, target, intent = _fixture(managed_workspace, tmp_path)

    prepared = store.prepare_lineage_adoption(intent)
    assert prepared["phase"] == "prepared"
    assert set(prepared) == INTENT_FIELDS
    assert store.read_lineage_adoption(intent["adoption_id"]) == prepared
    assert source in store.read_lineage_claims()
    assert target not in store.read_lineage_claims()

    transferred = store.apply_lineage_adoption(
        intent["adoption_id"],
        expected_daemon_id=owner["daemon_id"],
        authoritative=True,
    )
    assert transferred["phase"] == "claim-transferred"
    assert target in store.read_lineage_claims()
    assert source not in store.read_lineage_claims()

    controller_digest = _controller_commit(store, intent)
    completed = store.finalize_lineage_adoption(
        intent["adoption_id"],
        expected_daemon_id=owner["daemon_id"],
        controller_digest=controller_digest,
    )
    assert completed["phase"] == "controller-committed"
    assert completed["controller_commit_digest"] == controller_digest
    assert store.read_lineage_claims() == [target]


def test_apply_requires_authoritative_precondition_before_claim_effect(
        managed_workspace, tmp_path: Path):
    store, owner, source, target, intent = _fixture(managed_workspace, tmp_path)
    store.prepare_lineage_adoption(intent)
    claims_before = store.read_lineage_claims()

    with pytest.raises(ManagedStateError) as raised:
        store.apply_lineage_adoption(
            intent["adoption_id"],
            expected_daemon_id=owner["daemon_id"],
            authoritative=False,
        )

    assert raised.value.code == "uncertain-effect"
    assert store.read_lineage_adoption(intent["adoption_id"])["phase"] == "prepared"
    assert store.read_lineage_claims() == claims_before
    assert target not in store.read_lineage_claims()


def test_changed_owner_daemon_refuses_before_claim_effect(
        managed_workspace, tmp_path: Path):
    store, owner, source, target, intent = _fixture(managed_workspace, tmp_path)
    store.prepare_lineage_adoption(intent)
    changed_owner = store.read_json("owner.json")
    changed_owner["daemon_id"] = "daemon-replaced"
    store._write_owner(changed_owner)
    claims_before = store.read_lineage_claims()

    with pytest.raises(ManagedStateError) as raised:
        store.apply_lineage_adoption(
            intent["adoption_id"],
            expected_daemon_id=owner["daemon_id"],
            authoritative=True,
        )
    assert raised.value.code == "ownership-conflict"
    assert store.read_lineage_claims() == claims_before
    assert store.read_lineage_adoption(intent["adoption_id"])["phase"] == "prepared"


@pytest.mark.parametrize("rows", ["both", "neither"])
def test_reconcile_unresolved_claim_presence_is_indeterminate(
        managed_workspace, tmp_path: Path, rows):
    (tmp_path / rows).mkdir()
    store, owner, source, target, intent = _fixture(
        managed_workspace, tmp_path / rows,
    )
    store.prepare_lineage_adoption(intent)
    pending = dict(store.read_lineage_adoption(intent["adoption_id"]))
    pending["phase"] = "claim-cas-pending"
    store._write_native_adoption_ledger({intent["adoption_id"]: pending})
    if rows == "both":
        store._write_claims([source, target])
    else:
        store._write_claims([])

    result = store.reconcile_lineage_adoption(
        intent["adoption_id"], expected_daemon_id=owner["daemon_id"],
    )
    assert result["phase"] == "indeterminate"
    assert store.read_lineage_adoption(intent["adoption_id"])["phase"] == (
        "indeterminate"
    )


def test_completed_apply_revalidates_target_instead_of_trusting_stale_ledger(
        managed_workspace, tmp_path: Path):
    store, owner, source, target, intent = _fixture(managed_workspace, tmp_path)
    store.prepare_lineage_adoption(intent)
    store.apply_lineage_adoption(
        intent["adoption_id"],
        expected_daemon_id=owner["daemon_id"],
        authoritative=True,
    )
    tampered = dict(target)
    tampered["parent_read_only"] = False
    store._write_claims([tampered])

    with pytest.raises(ManagedStateError) as raised:
        store.apply_lineage_adoption(
            intent["adoption_id"],
            expected_daemon_id=owner["daemon_id"],
            authoritative=True,
        )
    assert raised.value.code in {"uncertain-effect", "ownership-conflict"}


def test_controller_commit_before_state_finalize_is_not_claimed_as_final(
        managed_workspace, tmp_path: Path):
    store, owner, source, target, intent = _fixture(managed_workspace, tmp_path)
    store.prepare_lineage_adoption(intent)
    store.apply_lineage_adoption(
        intent["adoption_id"],
        expected_daemon_id=owner["daemon_id"],
        authoritative=True,
    )
    _set_controller_phase(store, "controller-committed")

    observed = store.reconcile_lineage_adoption(
        intent["adoption_id"], expected_daemon_id=owner["daemon_id"],
    )
    assert observed["phase"] == "claim-transferred"
    assert store.read_lineage_adoption(intent["adoption_id"])["phase"] == (
        "claim-transferred"
    )


def test_apply_crash_after_claim_cas_leaves_pending_and_retry_cannot_replay(
        managed_workspace, tmp_path: Path, monkeypatch):
    store, owner, source, target, intent = _fixture(managed_workspace, tmp_path)
    store.prepare_lineage_adoption(intent)
    original_write = store._write_native_adoption_ledger
    writes = []

    def fail_after_cas(intents):
        writes.append(copy.deepcopy(intents))
        if len(writes) == 2:
            raise ManagedStateError("unsafe-state", "injected post-CAS ledger failure")
        return original_write(intents)

    monkeypatch.setattr(store, "_write_native_adoption_ledger", fail_after_cas)
    with pytest.raises(ManagedStateError) as raised:
        store.apply_lineage_adoption(
            intent["adoption_id"],
            expected_daemon_id=owner["daemon_id"],
            authoritative=True,
        )
    assert raised.value.code == "unsafe-state"
    assert store.read_lineage_adoption(intent["adoption_id"])["phase"] == (
        "claim-cas-pending"
    )
    assert target in store.read_lineage_claims()
    assert source not in store.read_lineage_claims()

    claim_writes = []
    original_claim_write = store._write_claims
    monkeypatch.setattr(
        store, "_write_claims",
        lambda claims: (claim_writes.append(copy.deepcopy(claims)),
                        original_claim_write(claims))[1],
    )
    with pytest.raises(ManagedStateError):
        store.apply_lineage_adoption(
            intent["adoption_id"],
            expected_daemon_id=owner["daemon_id"],
            authoritative=True,
        )
    assert claim_writes == []


def test_reconcile_pending_source_marks_indeterminate_without_cas(
        managed_workspace, tmp_path: Path, monkeypatch):
    store, owner, source, target, intent = _fixture(managed_workspace, tmp_path)
    store.prepare_lineage_adoption(intent)
    pending = dict(store.read_lineage_adoption(intent["adoption_id"]))
    pending["phase"] = "claim-cas-pending"
    store._write_native_adoption_ledger({intent["adoption_id"]: pending})
    writes = []
    monkeypatch.setattr(
        store, "_write_claims",
        lambda claims: writes.append(copy.deepcopy(claims)),
    )

    result = store.reconcile_lineage_adoption(
        intent["adoption_id"], expected_daemon_id=owner["daemon_id"],
    )
    assert result["phase"] == "indeterminate"
    assert source in store.read_lineage_claims()
    assert target not in store.read_lineage_claims()
    assert writes == []


def test_malformed_ledger_is_preserved_and_getter_does_not_provision(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace,
        tmp_path,
        lane="adoption-malformed",
        daemon_id="daemon-adoption-malformed",
        lineage_id="adoption-malformed-source",
        coordinator_session_uuid="adoption-malformed-coordinator",
    )
    path = _ledger_path(store)
    path.write_bytes(b'{"schema_version":2,"unknown":true}\n')
    before = path.read_bytes()

    with pytest.raises(ManagedStateError):
        store.read_lineage_adoption("missing-adoption")

    assert path.read_bytes() == before


def test_completed_retry_is_observational_and_requires_exact_controller_digest(
        managed_workspace, tmp_path: Path, monkeypatch):
    store, owner, source, target, intent = _fixture(managed_workspace, tmp_path)
    store.prepare_lineage_adoption(intent)
    store.apply_lineage_adoption(
        intent["adoption_id"],
        expected_daemon_id=owner["daemon_id"],
        authoritative=True,
    )
    controller_digest = _controller_commit(store, intent)
    store.finalize_lineage_adoption(
        intent["adoption_id"],
        expected_daemon_id=owner["daemon_id"],
        controller_digest=controller_digest,
    )
    ledger_before = _ledger_path(store).read_bytes()

    def unexpected_write(*args, **kwargs):
        raise AssertionError("completed retry wrote adoption ledger")

    monkeypatch.setattr(store, "_write_native_adoption_ledger", unexpected_write)
    retry = store.finalize_lineage_adoption(
        intent["adoption_id"],
        expected_daemon_id=owner["daemon_id"],
        controller_digest=controller_digest,
    )
    assert retry["phase"] == "controller-committed"
    assert _ledger_path(store).read_bytes() == ledger_before
    with pytest.raises(ManagedStateError):
        store.finalize_lineage_adoption(
            intent["adoption_id"],
            expected_daemon_id=owner["daemon_id"],
            controller_digest="d" * 64,
        )
