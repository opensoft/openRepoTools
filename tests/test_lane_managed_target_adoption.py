# SPDX-License-Identifier: Apache-2.0
"""Test-first held native ownership adoption transaction boundary.

These tests deliberately stop at the controller/state seam.  Adoption is an
ownership descriptor only: no runtime is opened, interrupted, released, or
published, and the source controller history remains intact.
"""

from __future__ import annotations

import copy

import pytest

from lane_managed_controller import ControllerError, ManagedController, Participant, native_record_marker
from lane_managed_state import ManagedStateError
from test_lane_managed_controller import READ_ONLY_METADATA
from test_lane_managed_lineage_transfer import _seed_source
from test_lane_managed_source_history import _two_admission_fenced_authority


INTENT_FIELDS = {
    "schema_version", "architecture", "record_kind", "adoption_id",
    "archive_id", "archive_digest", "operation_id", "owner_generation",
    "expected_daemon_id", "source_identity", "source_claim", "target_claim",
    "source_claim_digest", "target_claim_digest", "evidence_digest",
    "runtime_identity_digest", "evidence_reference", "intent_digest",
    "phase", "controller_commit_digest",
}
REFERENCE_FIELDS = {
    "adoption_id", "intent_digest", "archive_id", "archive_digest",
    "target_claim_digest", "phase",
}


class AdoptionMemoryStore:
    """Small state-method adapter over the existing controller fixture."""

    def __init__(self, store):
        self._store = store
        self.adoptions = {}
        self.calls = []
        self.reconcile_status = "target-held"
        self.finalize_fail_once = False

    def __getattr__(self, name):
        return getattr(self._store, name)

    def prepare_lineage_adoption(self, intent):
        self.calls.append(("prepare", copy.deepcopy(intent)))
        adoption_id = intent["adoption_id"]
        existing = self.adoptions.get(adoption_id)
        if existing is not None:
            if existing != intent:
                raise ControllerError("invalid", "adoption intent changed")
            return copy.deepcopy(existing)
        self.adoptions[adoption_id] = copy.deepcopy(intent)
        return copy.deepcopy(intent)

    def read_lineage_adoption(self, adoption_id):
        self.calls.append(("read", adoption_id))
        value = self.adoptions.get(adoption_id)
        return None if value is None else copy.deepcopy(value)

    def apply_lineage_adoption(self, adoption_id, *, expected_daemon_id,
                               authoritative=False):
        self.calls.append(("apply", adoption_id, expected_daemon_id, authoritative))
        value = self.adoptions[adoption_id]
        if value["phase"] != "prepared":
            raise ControllerError("uncertain-effect", "adoption is not prepared")
        value["phase"] = "claim-transferred"
        return copy.deepcopy(value)

    def reconcile_lineage_adoption(self, adoption_id, *, expected_daemon_id):
        self.calls.append(("reconcile", adoption_id, expected_daemon_id))
        value = self.adoptions[adoption_id]
        if self.reconcile_status == "source-held":
            value["phase"] = "indeterminate"
        elif self.reconcile_status == "target-held":
            value["phase"] = "claim-transferred"
        return copy.deepcopy(value)

    def finalize_lineage_adoption(self, adoption_id, *, expected_daemon_id,
                                  controller_digest):
        self.calls.append(("finalize", adoption_id, expected_daemon_id,
                           controller_digest))
        if self.finalize_fail_once:
            self.finalize_fail_once = False
            raise ControllerError(
                "uncertain-effect", "simulated finalization crash"
            )
        value = self.adoptions[adoption_id]
        value["phase"] = "controller-committed"
        value["controller_commit_digest"] = controller_digest
        return copy.deepcopy(value)

    def assess_lineage_workspace_adoption(
            self, expected_source_claim, expected_target_claim, *,
            expected_daemon_id):
        self.calls.append(("assess", expected_daemon_id))
        value = self.adoptions.get("adoption-1")
        phase = value["phase"] if value is not None else "prepared"
        return {
            "status": "target-held" if phase in {
                "claim-transferred", "controller-committed"
            } else "source-held",
            "blockers": [],
            "source_matches": 0 if phase in {
                "claim-transferred", "controller-committed"
            } else 1,
            "target_matches": 1 if phase in {
                "claim-transferred", "controller-committed"
            } else 0,
        }


class NoRuntime:
    def __getattr__(self, name):
        raise AssertionError("adoption touched runtime attribute %s" % name)


def _authority(tmp_path, *, provider=None):
    controller, raw_store, lineage, _first, _second, operation = (
        _two_admission_fenced_authority(tmp_path)
    )
    controller = ManagedController(
        raw_store,
        runtime=NoRuntime(),
        _coordinator_interrupt_daemon_id="daemon-test",
        _native_adoption_evidence_provider=provider,
    )
    archive = controller.archive_native_source(
        "archive-1", operation.operation_id, lineage["owner_generation"]
    )
    source_claim = copy.deepcopy(raw_store.read_lineage_claims()[0])
    source_claim["state"] = "active"
    target_claim = copy.deepcopy(source_claim)
    target_claim.update({
        "lineage_id": "lineage-target-8",
        "coordinator_session_uuid": "99999999-9999-4999-8999-999999999999",
        "lineage_generation": source_claim["lineage_generation"] + 1,
    })
    fake_state = AdoptionMemoryStore(raw_store)
    controller.store = fake_state
    return controller, fake_state, archive, operation, source_claim, target_claim


def _provider_for(archive, operation, source_claim, target_claim, calls=None):
    def provider(binding):
        if calls is not None:
            calls.append(copy.deepcopy(binding))
        return {
            **copy.deepcopy(binding),
            "runtime_identity_digest": "a" * 64,
            "evidence_reference": "evidence://adoption-1/1",
            "source_writers_excluded": True,
            "source_effects_resolved": True,
            "native_worker_state_cleared": True,
            "control_epoch_request_free": True,
            "target_startup_hold_supported": True,
        }
    return provider


def _prepare_args(operation, source_claim, target_claim):
    return (
        "adoption-1", "archive-1", operation.operation_id,
        operation.generation, source_claim, target_claim,
    )


def test_prepare_requires_internal_evidence_before_any_controller_or_state_write(
        tmp_path):
    controller, state, archive, operation, source, target = _authority(tmp_path)
    before = copy.deepcopy(controller._read_record())
    with pytest.raises(ControllerError, match="evidence"):
        controller.prepare_native_adoption(*_prepare_args(operation, source, target))
    assert controller._read_record() == before
    assert state.adoptions == {}
    assert not [call for call in state.calls if call[0] == "prepare"]


def test_prepare_persists_exact_reference_then_state_intent_and_exact_retry_is_read_only(
        tmp_path):
    calls = []
    controller, state, archive, operation, source, target = _authority(tmp_path)
    controller._native_adoption_evidence_provider = _provider_for(
        archive, operation, source, target, calls
    )
    result = controller.prepare_native_adoption(
        *_prepare_args(operation, source, target)
    )
    assert set(result) == INTENT_FIELDS
    assert result["phase"] == "prepared"
    assert result["archive_digest"] == archive["snapshot_digest"]
    assert set(controller.status()["operation"]["metadata"]["native_adoption"]) == REFERENCE_FIELDS
    assert state.adoptions["adoption-1"] == result

    writes = copy.deepcopy(controller._read_record())
    call_count = len(state.calls)
    retried = controller.prepare_native_adoption(
        *_prepare_args(operation, source, target)
    )
    assert retried == result
    assert controller._read_record() == writes
    assert len(state.calls) == call_count + 1  # observational state read only


def test_prepare_rejects_valid_divergent_same_id_ledger_before_retry_success(
        tmp_path):
    controller, state, archive, operation, source, target = _authority(tmp_path)
    controller._native_adoption_evidence_provider = _provider_for(
        archive, operation, source, target
    )
    prepared = controller.prepare_native_adoption(
        *_prepare_args(operation, source, target)
    )
    divergent = copy.deepcopy(prepared)
    divergent["evidence_reference"] = "evidence://adoption-1/divergent"
    divergent["evidence_digest"] = "b" * 64
    divergent["intent_digest"] = controller._native_adoption_intent_digest(
        divergent
    )
    state.adoptions["adoption-1"] = divergent

    with pytest.raises(ControllerError, match="immutable content"):
        controller.prepare_native_adoption(
            *_prepare_args(operation, source, target)
        )


def test_advance_requires_target_assessment_and_commits_only_held_descriptor(
        tmp_path):
    controller, state, archive, operation, source, target = _authority(tmp_path)
    controller._native_adoption_evidence_provider = _provider_for(
        archive, operation, source, target
    )
    controller.prepare_native_adoption(*_prepare_args(operation, source, target))
    before_context = copy.deepcopy(controller.status()["native_context"])
    result = controller.advance_native_adoption("adoption-1")
    assert result["phase"] == "controller-committed"
    assert controller.status()["operation"]["phase"] == "paused"
    assert controller.status()["native_context"] == before_context
    assert [call[0] for call in state.calls].count("apply") == 1
    assert [call[0] for call in state.calls].count("finalize") == 1


def test_pending_target_held_recovery_never_retries_claim_cas(tmp_path):
    controller, state, archive, operation, source, target = _authority(tmp_path)
    controller._native_adoption_evidence_provider = _provider_for(
        archive, operation, source, target
    )
    controller.prepare_native_adoption(*_prepare_args(operation, source, target))
    state.adoptions["adoption-1"]["phase"] = "claim-cas-pending"
    state.reconcile_status = "target-held"

    result = controller.recover_native_adoption("adoption-1")

    assert result["phase"] == "controller-committed"
    assert not [call for call in state.calls if call[0] == "apply"]
    assert [call[0] for call in state.calls].count("reconcile") == 1


def test_controller_ack_ahead_of_state_finalization_recovers_without_controller_write(
        tmp_path):
    controller, state, archive, operation, source, target = _authority(tmp_path)
    provider = _provider_for(archive, operation, source, target)
    controller._native_adoption_evidence_provider = provider
    controller.prepare_native_adoption(*_prepare_args(operation, source, target))
    state.finalize_fail_once = True

    with pytest.raises(ControllerError, match="finalization crash"):
        controller.advance_native_adoption("adoption-1")
    assert state.adoptions["adoption-1"]["phase"] == "claim-transferred"
    assert controller.status()["operation"]["metadata"]["native_adoption"]["phase"] == (
        "controller-committed"
    )
    writes_before_recovery = len(state._store.write_calls)

    reloaded = ManagedController(
        state,
        runtime=NoRuntime(),
        _coordinator_interrupt_daemon_id="daemon-test",
        _native_adoption_evidence_provider=provider,
    )
    result = reloaded.recover_native_adoption("adoption-1")

    assert result["phase"] == "controller-committed"
    assert len(state._store.write_calls) == writes_before_recovery
    assert [call[0] for call in state.calls].count("apply") == 1


def test_changed_provider_refuses_before_advance_or_recovery_effect(tmp_path):
    controller, state, archive, operation, source, target = _authority(tmp_path)
    stable = _provider_for(archive, operation, source, target)
    controller._native_adoption_evidence_provider = stable
    controller.prepare_native_adoption(*_prepare_args(operation, source, target))

    def changed_provider(binding):
        response = stable(binding)
        response["runtime_identity_digest"] = "d" * 64
        return response

    controller._native_adoption_evidence_provider = changed_provider
    before_record = copy.deepcopy(controller._read_record())
    with pytest.raises(ControllerError, match="evidence"):
        controller.advance_native_adoption("adoption-1")
    assert controller._read_record() == before_record
    assert not [call for call in state.calls if call[0] == "apply"]

    controller, state, archive, operation, source, target = _authority(tmp_path)
    controller._native_adoption_evidence_provider = stable = _provider_for(
        archive, operation, source, target
    )
    controller.prepare_native_adoption(*_prepare_args(operation, source, target))
    state.adoptions["adoption-1"]["phase"] = "claim-cas-pending"
    state.reconcile_status = "target-held"
    controller._native_adoption_evidence_provider = changed_provider
    before_calls = len(state.calls)
    with pytest.raises(ControllerError, match="evidence"):
        controller.recover_native_adoption("adoption-1")
    assert len(state.calls) >= before_calls
    assert not [call for call in state.calls[before_calls:] if call[0] == "reconcile"]
    assert state.adoptions["adoption-1"]["phase"] == "claim-cas-pending"


@pytest.mark.parametrize("field", [
    "source_writers_excluded", "source_effects_resolved",
    "native_worker_state_cleared", "control_epoch_request_free",
    "target_startup_hold_supported",
])
def test_false_evidence_refuses_before_preparation(field, tmp_path):
    controller, state, archive, operation, source, target = _authority(tmp_path)

    def provider(binding):
        response = {
            **copy.deepcopy(binding),
            "runtime_identity_digest": "a" * 64,
            "evidence_reference": "evidence://adoption-1/false",
            "source_writers_excluded": True,
            "source_effects_resolved": True,
            "native_worker_state_cleared": True,
            "control_epoch_request_free": True,
            "target_startup_hold_supported": True,
        }
        response[field] = False
        return response

    controller._native_adoption_evidence_provider = provider
    before = copy.deepcopy(controller._read_record())
    with pytest.raises(ControllerError):
        controller.prepare_native_adoption(*_prepare_args(operation, source, target))
    assert controller._read_record() == before
    assert state.adoptions == {}


def test_pending_recovery_never_retries_cas_when_source_is_still_held(tmp_path):
    controller, state, archive, operation, source, target = _authority(tmp_path)
    controller._native_adoption_evidence_provider = _provider_for(
        archive, operation, source, target
    )
    controller.prepare_native_adoption(*_prepare_args(operation, source, target))
    state.adoptions["adoption-1"]["phase"] = "claim-cas-pending"
    state.reconcile_status = "source-held"
    before_apply = len([call for call in state.calls if call[0] == "apply"])
    with pytest.raises(ControllerError, match="indeterminate"):
        controller.recover_native_adoption("adoption-1")
    assert len([call for call in state.calls if call[0] == "apply"]) == before_apply
    assert state.adoptions["adoption-1"]["phase"] == "indeterminate"


def test_getter_is_defensive_and_does_not_expose_provider_or_runtime(tmp_path):
    controller, state, archive, operation, source, target = _authority(tmp_path)
    controller._native_adoption_evidence_provider = _provider_for(
        archive, operation, source, target
    )
    controller.prepare_native_adoption(*_prepare_args(operation, source, target))
    value = controller.native_adoption("adoption-1")
    value["source_identity"]["lineage_id"] = "tampered"
    assert controller.native_adoption("adoption-1")["source_identity"]["lineage_id"] != "tampered"


def _real_authority(managed_workspace, tmp_path, provider):
    """Build the same fenced source through the real state store boundary."""
    store, owner, source = _seed_source(
        managed_workspace,
        tmp_path,
        lane="adoption-real-controller",
        daemon_id="daemon-real-adoption",
        lineage_id="lineage-real-source",
        coordinator_session_uuid="coordinator-real-source",
    )
    controller = ManagedController(
        store,
        _coordinator_interrupt_daemon_id=owner["daemon_id"],
        _native_adoption_evidence_provider=provider,
    )
    coordinator_metadata = copy.deepcopy(READ_ONLY_METADATA)
    coordinator_metadata["runner_instance_id"] = "runner-real-adoption"
    coordinator = Participant(
        participant_id="coordinator",
        session_id=source["coordinator_session_uuid"],
        session_name="managed-coordinator",
        bound_lane=source["lane"],
        role="coordinator",
        parent_id=None,
        task_id="task-root",
        mailbox_id="mailbox-coordinator",
        state="held",
        read_only=True,
        metadata=coordinator_metadata,
    )
    controller.enroll(owner["generation"], coordinator)
    lineage = {
        **native_record_marker("lineage"),
        "lineage_id": source["lineage_id"],
        "lane": source["lane"],
        "owner_generation": owner["generation"],
        "lineage_generation": source["lineage_generation"],
        "session_uuid": source["coordinator_session_uuid"],
        "transcript": {"ref": "transcript://real-adoption-source"},
        "workspace": source["workspace"],
        "common_dir": source["common_dir"],
        "state": "held",
        "workspace_claim": copy.deepcopy(source),
        "read_only": True,
    }
    operation = controller.begin_operation(
        "real-adoption-operation", "swap", owner["generation"],
        request_content={"target": "held-adoption"},
    )
    definitions = {
        "writer": {
            "prompt": "private test definition",
            "tools": ["Read", "Edit"],
            "model": "configured-model",
            "effort": "medium",
            "permissionMode": "default",
            "permissions": {"allow": ["Read", "Edit"]},
        }
    }
    controller.register_native_context(
        owner["generation"], lineage, "runner-real-adoption",
        "invocation-real-adoption", definitions,
    )
    controller.fence(operation.operation_id)
    archive = controller.archive_native_source(
        "archive-1", operation.operation_id, owner["generation"]
    )
    source_claim = copy.deepcopy(source)
    target_claim = copy.deepcopy(source_claim)
    target_claim.update({
        "lineage_id": "lineage-real-target",
        "coordinator_session_uuid": "coordinator-real-target",
        "lineage_generation": source_claim["lineage_generation"] + 1,
    })
    return controller, store, owner, archive, operation, source_claim, target_claim


def test_real_controller_and_real_state_store_complete_held_adoption_without_runtime(
        managed_workspace, tmp_path):
    calls = []

    def provider(binding):
        calls.append(copy.deepcopy(binding))
        return {
            **copy.deepcopy(binding),
            "runtime_identity_digest": "c" * 64,
            "evidence_reference": "evidence://real-adoption/1",
            "source_writers_excluded": True,
            "source_effects_resolved": True,
            "native_worker_state_cleared": True,
            "control_epoch_request_free": True,
            "target_startup_hold_supported": True,
        }

    controller, store, owner, archive, operation, source, target = (
        _real_authority(managed_workspace, tmp_path, provider)
    )
    before_context = copy.deepcopy(controller.status()["native_context"])
    prepared = controller.prepare_native_adoption(
        "adoption-1", "archive-1", operation.operation_id,
        owner["generation"], source, target,
    )
    assert prepared["phase"] == "prepared"
    assert (store.identity.state_root / "native-adoptions.json").exists()

    committed = controller.advance_native_adoption("adoption-1")
    assert committed["phase"] == "controller-committed"
    assert controller.status()["native_context"] == before_context
    assert controller.status()["operation"]["phase"] == "paused"
    assert store.read_lineage_claims() == [target]
    assert calls
    assert all("evidence_digest" not in binding for binding in calls)


def test_real_state_finalize_crash_recovers_ack_ahead_without_controller_rewrite(
        managed_workspace, tmp_path, monkeypatch):
    def provider(binding):
        return {
            **copy.deepcopy(binding),
            "runtime_identity_digest": "e" * 64,
            "evidence_reference": "evidence://real-adoption/crash",
            "source_writers_excluded": True,
            "source_effects_resolved": True,
            "native_worker_state_cleared": True,
            "control_epoch_request_free": True,
            "target_startup_hold_supported": True,
        }

    controller, store, owner, _archive, operation, source, target = (
        _real_authority(managed_workspace, tmp_path, provider)
    )
    controller.prepare_native_adoption(
        "adoption-1", "archive-1", operation.operation_id,
        owner["generation"], source, target,
    )
    original_finalize = store.finalize_lineage_adoption
    failed = {"once": True}

    def finalize_once(adoption_id, **kwargs):
        if failed["once"]:
            failed["once"] = False
            raise ManagedStateError("uncertain-effect", "simulated state finalization crash")
        return original_finalize(adoption_id, **kwargs)

    monkeypatch.setattr(store, "finalize_lineage_adoption", finalize_once)
    with pytest.raises(ControllerError, match="finalization crash"):
        controller.advance_native_adoption("adoption-1")

    state_after_crash = store.read_lineage_adoption("adoption-1")
    assert state_after_crash["phase"] == "claim-transferred"
    controller_bytes_after_crash = (
        store.identity.state_root / "controller.json"
    ).read_bytes()

    reloaded = ManagedController(
        store,
        _coordinator_interrupt_daemon_id=owner["daemon_id"],
        _native_adoption_evidence_provider=provider,
    )
    recovered = reloaded.recover_native_adoption("adoption-1")

    assert recovered["phase"] == "controller-committed"
    assert store.read_lineage_adoption("adoption-1")["phase"] == (
        "controller-committed"
    )
    assert (
        store.identity.state_root / "controller.json"
    ).read_bytes() == controller_bytes_after_crash
