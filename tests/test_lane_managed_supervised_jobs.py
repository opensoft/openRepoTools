# SPDX-License-Identifier: Apache-2.0
"""Offline contract tests for the private supervised-jobs ledger foundation.

These tests exercise durable state and injected evidence only.  They do not
start a Claude CLI, a persistent job, a container, or any public capability.
"""

from __future__ import annotations

import hashlib
import multiprocessing
from pathlib import Path
from typing import Any, Mapping

import pytest

from lane_managed_state import ManagedStateError, ManagedStateStore
from lane_managed_supervised_jobs import ClaudeCliSupervisedJobsLedger
from test_lane_managed_state import _store


PARENT_UUID = "00000000-0000-4000-8000-000000000001"
LINEAGE_ID = "lineage-supervised-jobs-test"
SUPERVISOR_INCARNATION = "supervisor-incarnation-test"
SOURCE_MANIFEST = hashlib.sha256(b"source manifest").hexdigest()
TARGET_MANIFEST = hashlib.sha256(b"target manifest").hexdigest()
COMMAND_DIGEST = hashlib.sha256(b"command config").hexdigest()
REQUEST_DIGEST = hashlib.sha256(b"job request").hexdigest()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _WitnessProvider:
    """Deterministic trusted-provider stand-in; never executes a command."""

    persistent_job_domain_id = "test-cgroup:l1-jobs"

    def __init__(self):
        self.watermark = 0
        self.jobs = {}
        self.target_state = "absent"
        self.source_watermark_override = None
        self.history_watermark_override = None
        self.on_source_exclusion = None

    def _next(self) -> int:
        self.watermark += 1
        return self.watermark

    def source_exclusion(self, binding: Mapping[str, Any]):
        watermark = self._next()
        if self.source_watermark_override is not None:
            watermark = self.source_watermark_override
        witness = {
            "witness_id": "source-exclusion-%d" % self.watermark,
            "witness_digest": _digest("source-exclusion-%d" % self.watermark),
            "observation_watermark": watermark,
            "source_runtime_incarnation": binding["source_runtime_incarnation"],
            "source_domain_id": binding["source_domain_id"],
            "supervisor_incarnation": binding["supervisor_incarnation"],
            "parent_uuid": binding["parent_uuid"],
            "membership_complete": True,
            "escape_coverage_complete": True,
            "active_source_processes": 0,
            "restart_fence_effective": True,
            "job_domain_live": True,
        }
        callback = self.on_source_exclusion
        self.on_source_exclusion = None
        if callback is not None:
            callback()
        return witness

    def history_manifest(self, binding: Mapping[str, Any]):
        watermark = self._next()
        if self.history_watermark_override is not None:
            watermark = self.history_watermark_override
        return {
            "witness_id": "history-%d" % self.watermark,
            "witness_digest": _digest("history-%d" % self.watermark),
            "parent_uuid": binding["parent_uuid"],
            "manifest_digest": _digest("history-manifest"),
            "worktree_manifest_digest": _digest(
                ",".join(binding["worktree_ids"])),
            "observation_watermark": watermark,
            "complete": True,
        }

    def job_status(self, binding: Mapping[str, Any], job_id: str):
        job = self.jobs[job_id]
        return {
            "witness_id": "job-%s-%d" % (job_id, self.watermark),
            "witness_digest": _digest("job-%s-%d" % (job_id, self.watermark)),
            "job_id": job_id,
            "command_digest": job["command_digest"],
            "domain_id": self.persistent_job_domain_id,
            "observation_watermark": self._next(),
            "state": job["state"],
            "effect_state": job["effect_state"],
            "process_identity": job.get("process_identity"),
            "output_ref": job.get("output_ref"),
            "result_digest": job.get("result_digest"),
        }

    def target_status(self, binding: Mapping[str, Any]):
        witness = {
            "witness_id": "target-%d" % self.watermark,
            "witness_digest": _digest("target-%d" % self.watermark),
            "observation_watermark": self._next(),
            "state": self.target_state,
            "parent_uuid": binding["parent_uuid"],
            "profile_ref": binding["profile_ref"],
            "manifest_digest": binding["manifest_digest"],
            "claim_generation": binding["target_claim_generation"],
            "runtime_incarnation": "runtime-b",
            "invocation_id": "invocation-b-1",
            "domain_id": "target-domain-b",
            "process_identity": {
                "pid": 4242,
                "start_token": "target-process-start",
                "domain_id": "target-domain-b",
            },
            "account_identity_digest": _digest("profile-team-b-account"),
        }
        return witness


def _seed(managed_workspace, tmp_path: Path):
    store = _store(managed_workspace)
    owner = store.enroll_managed(
        daemon_id="daemon-supervised-jobs-test",
        lineage_id=LINEAGE_ID,
        coordinator_session_uuid=PARENT_UUID,
    )
    store.claim_lineage_workspace(
        lineage_id=LINEAGE_ID,
        owner_generation=owner["generation"],
        lineage_generation=1,
        workspace=str(managed_workspace.workspace_repo.resolve()),
        common_dir=str(store.identity.common_dir.resolve()),
        repository=str(managed_workspace.project.resolve()),
        parent_read_only=False,
        coordinator_session_uuid=PARENT_UUID,
    )
    return store


def _claim_source(ledger: ClaudeCliSupervisedJobsLedger, *, runtime="runtime-a"):
    return ledger.claim_source(
        supervisor_incarnation=SUPERVISOR_INCARNATION,
        parent_uuid=PARENT_UUID,
        lineage_id=LINEAGE_ID,
        lineage_generation=1,
        profile_ref="profile-team-a",
        runtime_incarnation=runtime,
        invocation_id="invocation-a-1",
        domain_id="source-domain-a",
        manifest_digest=SOURCE_MANIFEST,
    )


def _competing_claim(identity, runtime_incarnation, barrier, result):
    try:
        barrier.wait(timeout=10)
        ledger = ClaudeCliSupervisedJobsLedger(
            ManagedStateStore(identity), _WitnessProvider(),
        )
        claim = _claim_source(ledger, runtime=runtime_incarnation)
        result.put(("claimed", claim["runtime_incarnation"]))
    except ManagedStateError as exc:
        result.put(("refused", exc.code))
    except BaseException as exc:  # pragma: no cover - makes child errors visible
        result.put(("crashed", type(exc).__name__, str(exc)))


def _competing_target_claim(identity, claimant_id, owner_generation,
                            claim_generation, barrier, result):
    try:
        barrier.wait(timeout=10)
        ledger = ClaudeCliSupervisedJobsLedger(
            ManagedStateStore(identity), _WitnessProvider(),
        )
        claim = ledger.claim_target(
            operation_id="swap-target-race",
            claimant_id=claimant_id,
            parent_uuid=PARENT_UUID,
            owner_generation=owner_generation,
            claim_generation=claim_generation,
            profile_ref="profile-team-b",
            manifest_digest=TARGET_MANIFEST,
        )
        result.put(("claimed", claim["claimant_id"]))
    except ManagedStateError as exc:
        result.put(("refused", exc.code))
    except BaseException as exc:  # pragma: no cover - makes child errors visible
        result.put(("crashed", type(exc).__name__, str(exc)))


def test_source_fence_is_durable_idempotent_and_blocks_late_job_dispatch(
        managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    provider = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, provider)
    source = _claim_source(ledger)
    resource_id = source["worktree_ids"][0]

    admitted = ledger.admit_job(
        job_id="job-before-fence",
        request_id="request-before-fence",
        request_digest=REQUEST_DIGEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
        command_digest=COMMAND_DIGEST,
        resource_ids=[resource_id],
    )
    assert admitted["state"] == "admitted"
    assert ledger.status()["reservations"][resource_id] == "job-before-fence"
    with pytest.raises(ManagedStateError) as changed_job:
        ledger.admit_job(
            job_id="job-before-fence",
            request_id="request-before-fence",
            request_digest=_digest("changed request"),
            parent_uuid=PARENT_UUID,
            claim_generation=source["claim_generation"],
            command_digest=COMMAND_DIGEST,
            resource_ids=[resource_id],
        )
    assert changed_job.value.code == "ownership-conflict"

    launch = ledger.begin_job_launch(
        job_id="job-before-fence", request_digest=REQUEST_DIGEST,
    )
    assert launch["launch_state"] == "intent-recorded"
    request_digest = _digest("swap request")
    operation = ledger.prepare_swap(
        operation_id="swap-one",
        request_id="swap-request-one",
        request_digest=request_digest,
        target_profile_ref="profile-team-b",
        target_manifest_digest=TARGET_MANIFEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )
    assert operation["source_restart_denied"] is True
    assert source["claim_generation"] in ledger.status()["retired_source_generations"]

    # Reload from a distinct store object to prove the fence is durable.
    reloaded = ClaudeCliSupervisedJobsLedger(
        ManagedStateStore(store.identity), provider,
    )
    assert reloaded.status()["operations"]["swap-one"]["source_restart_denied"] is True
    with pytest.raises(ManagedStateError) as source_restart:
        reloaded.authorize_source_creation(
            claim_generation=source["claim_generation"],
            parent_uuid=PARENT_UUID,
            manifest_digest=SOURCE_MANIFEST,
            runtime_incarnation="runtime-a",
        )
    assert source_restart.value.code in {"ownership-conflict", "stale-generation"}
    with pytest.raises(ManagedStateError) as late_dispatch:
        reloaded.begin_job_launch(
            job_id="job-before-fence", request_digest=REQUEST_DIGEST,
        )
    assert late_dispatch.value.code == "ownership-conflict"

    # An exact prepare retry reads the existing intent; changed replay refuses.
    assert reloaded.prepare_swap(
        operation_id="swap-one",
        request_id="swap-request-one",
        request_digest=request_digest,
        target_profile_ref="profile-team-b",
        target_manifest_digest=TARGET_MANIFEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    ) == operation
    with pytest.raises(ManagedStateError) as changed_swap:
        reloaded.prepare_swap(
            operation_id="swap-one",
            request_id="swap-request-one",
            request_digest=_digest("different swap request"),
            target_profile_ref="profile-team-b",
            target_manifest_digest=TARGET_MANIFEST,
            parent_uuid=PARENT_UUID,
            claim_generation=source["claim_generation"],
        )
    assert changed_swap.value.code == "ownership-conflict"


def test_competing_source_runtimes_cannot_both_claim_one_generation(
        managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    ctx = multiprocessing.get_context("fork")
    barrier = ctx.Barrier(2)
    result = ctx.Queue()
    processes = [
        ctx.Process(target=_competing_claim,
                    args=(store.identity, "runtime-a1", barrier, result)),
        ctx.Process(target=_competing_claim,
                    args=(store.identity, "runtime-a2", barrier, result)),
    ]
    for process in processes:
        process.start()
    try:
        outcomes = [result.get(timeout=15), result.get(timeout=15)]
    finally:
        for process in processes:
            process.join(timeout=10)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
    assert all(process.exitcode == 0 for process in processes)
    assert sorted(item[0] for item in outcomes) == ["claimed", "refused"]


def test_target_claim_refuses_wrong_parent_stale_generation_and_competing_claimants(
        managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    provider = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, provider)
    source = _claim_source(ledger)
    operation = ledger.prepare_swap(
        operation_id="swap-target-race",
        request_id="swap-target-race-request",
        request_digest=_digest("target race request"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=TARGET_MANIFEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )
    ledger.observe_source_exclusion("swap-target-race")
    assert ledger.reconcile("swap-target-race")["phase"] == "ready-to-resume"

    base = {
        "operation_id": "swap-target-race",
        "claimant_id": "runtime-b-invalid",
        "owner_generation": operation["owner_generation"],
        "claim_generation": operation["target_claim_generation"],
        "profile_ref": "profile-team-b",
        "manifest_digest": TARGET_MANIFEST,
    }
    with pytest.raises(ManagedStateError) as wrong_parent:
        ledger.claim_target(**base, parent_uuid="00000000-0000-4000-8000-000000000002")
    assert wrong_parent.value.code == "ownership-conflict"
    with pytest.raises(ManagedStateError) as stale_generation:
        ledger.claim_target(
            **{**base, "owner_generation": operation["owner_generation"] + 1},
            parent_uuid=PARENT_UUID,
        )
    assert stale_generation.value.code == "stale-generation"

    ctx = multiprocessing.get_context("fork")
    barrier = ctx.Barrier(2)
    result = ctx.Queue()
    processes = [
        ctx.Process(target=_competing_target_claim,
                    args=(store.identity, "runtime-b1", operation["owner_generation"],
                          operation["target_claim_generation"], barrier, result)),
        ctx.Process(target=_competing_target_claim,
                    args=(store.identity, "runtime-b2", operation["owner_generation"],
                          operation["target_claim_generation"], barrier, result)),
    ]
    for process in processes:
        process.start()
    try:
        outcomes = [result.get(timeout=15), result.get(timeout=15)]
    finally:
        for process in processes:
            process.join(timeout=10)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
    assert all(process.exitcode == 0 for process in processes)
    assert sorted(item[0] for item in outcomes) == ["claimed", "refused"]


def test_unknown_job_effect_stays_reserved_and_release_startup_is_observed_once(
        managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    provider = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, provider)
    source = _claim_source(ledger)
    resource_id = source["worktree_ids"][0]
    ledger.admit_job(
        job_id="job-l1-1",
        request_id="request-l1-1",
        request_digest=REQUEST_DIGEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
        command_digest=COMMAND_DIGEST,
        resource_ids=[resource_id],
    )
    ledger.begin_job_launch(job_id="job-l1-1", request_digest=REQUEST_DIGEST)
    provider.jobs["job-l1-1"] = {
        "command_digest": COMMAND_DIGEST,
        "state": "uncertain",
        "effect_state": "unknown",
        "process_identity": None,
        "output_ref": None,
        "result_digest": None,
    }
    operation = ledger.prepare_swap(
        operation_id="swap-job-test",
        request_id="swap-job-request",
        request_digest=_digest("swap job request"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=TARGET_MANIFEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )
    ledger.observe_source_exclusion("swap-job-test")
    with pytest.raises(ManagedStateError) as unknown_effect:
        ledger.reconcile("swap-job-test")
    assert unknown_effect.value.code == "uncertain-effect"
    assert ledger.status()["reservations"][resource_id] == "job-l1-1"
    with pytest.raises(ManagedStateError):
        ledger.claim_target(
            operation_id="swap-job-test",
            claimant_id="runtime-b-claimant",
            parent_uuid=PARENT_UUID,
            owner_generation=operation["owner_generation"],
            claim_generation=operation["target_claim_generation"],
            profile_ref="profile-team-b",
            manifest_digest=TARGET_MANIFEST,
        )

    # A later authoritative observation resolves the same admitted job; the
    # initial consumed launch intent is never replayed.
    provider.jobs["job-l1-1"].update({
        "state": "completed",
        "effect_state": "known",
        "output_ref": "result-ref:l1-1",
        "result_digest": _digest("job result"),
    })
    ledger.observe_source_exclusion("swap-job-test")
    reconciled = ledger.reconcile("swap-job-test")
    assert reconciled["phase"] == "ready-to-resume"
    assert "job-l1-1" not in ledger.status()["reservations"].values()
    assert ledger.status()["jobs"]["job-l1-1"]["result_digest"] == _digest("job result")

    target_claim = ledger.claim_target(
        operation_id="swap-job-test",
        claimant_id="runtime-b-claimant",
        parent_uuid=PARENT_UUID,
        owner_generation=operation["owner_generation"],
        claim_generation=operation["target_claim_generation"],
        profile_ref="profile-team-b",
        manifest_digest=TARGET_MANIFEST,
    )
    launch_intent = ledger.authorize_release(
        operation_id="swap-job-test",
        release_id="release-one",
        target_claim_token=target_claim["claim_token"],
    )
    assert ledger.authorize_release(
        operation_id="swap-job-test",
        release_id="release-one",
        target_claim_token=target_claim["claim_token"],
    ) == launch_intent
    with pytest.raises(ManagedStateError) as changed_release:
        ledger.authorize_release(
            operation_id="swap-job-test",
            release_id="release-two",
            target_claim_token=target_claim["claim_token"],
        )
    assert changed_release.value.code == "ownership-conflict"

    # A lost target-start ACK remains indeterminate.  A later read observes
    # the same durable launch intent and never creates a replacement intent.
    with pytest.raises(ManagedStateError) as lost_start_ack:
        ledger.observe_target_start("swap-job-test")
    assert lost_start_ack.value.code == "uncertain-effect"
    assert ledger.status()["operations"]["swap-job-test"]["phase"] == "indeterminate"
    provider.target_state = "running"
    observed = ledger.observe_target_start("swap-job-test")
    assert observed["launch_intent_id"] == launch_intent["launch_intent_id"]
    assert observed["state"] == "observed-running"
    assert ledger.status()["operations"]["swap-job-test"]["phase"] == "target-observed"

    target_source = ledger.claim_source(
        supervisor_incarnation=SUPERVISOR_INCARNATION,
        parent_uuid=PARENT_UUID,
        lineage_id=LINEAGE_ID,
        lineage_generation=1,
        profile_ref="profile-team-b",
        runtime_incarnation="runtime-b",
        invocation_id="invocation-b-1",
        domain_id="target-domain-b",
        manifest_digest=TARGET_MANIFEST,
    )
    assert target_source["claim_generation"] == operation["target_claim_generation"]
    assert target_source["claimant_id"] == "runtime-b-claimant"


def test_live_job_admission_survives_a_to_b_to_c_without_generation_rewrite(
        managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    provider = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, provider)
    source_a = _claim_source(ledger)
    resource_id = source_a["worktree_ids"][0]
    ledger.admit_job(
        job_id="job-j1",
        request_id="request-j1",
        request_digest=REQUEST_DIGEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source_a["claim_generation"],
        command_digest=COMMAND_DIGEST,
        resource_ids=[resource_id],
    )
    ledger.begin_job_launch(job_id="job-j1", request_digest=REQUEST_DIGEST)
    provider.jobs["job-j1"] = {
        "command_digest": COMMAND_DIGEST,
        "state": "running",
        "effect_state": "none",
        "process_identity": {
            "pid": 3131,
            "start_token": "j1-process-start",
            "domain_id": provider.persistent_job_domain_id,
        },
        "output_ref": None,
        "result_digest": None,
    }

    operation_ab = ledger.prepare_swap(
        operation_id="swap-a-to-b",
        request_id="request-a-to-b",
        request_digest=_digest("a to b"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=TARGET_MANIFEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source_a["claim_generation"],
    )
    assert operation_ab["job_ids"] == ["job-j1"]
    ledger.observe_source_exclusion("swap-a-to-b")
    assert ledger.reconcile("swap-a-to-b")["phase"] == "ready-to-resume"
    claim_b = ledger.claim_target(
        operation_id="swap-a-to-b",
        claimant_id="runtime-b-claimant",
        parent_uuid=PARENT_UUID,
        owner_generation=operation_ab["owner_generation"],
        claim_generation=operation_ab["target_claim_generation"],
        profile_ref="profile-team-b",
        manifest_digest=TARGET_MANIFEST,
    )
    ledger.authorize_release(
        operation_id="swap-a-to-b",
        release_id="release-a-to-b",
        target_claim_token=claim_b["claim_token"],
    )
    provider.target_state = "running"
    ledger.observe_target_start("swap-a-to-b")
    assert ledger.status()["operations"]["swap-a-to-b"]["phase"] == "target-observed"

    claim_source_b = ledger.claim_source(
        supervisor_incarnation=SUPERVISOR_INCARNATION,
        parent_uuid=PARENT_UUID,
        lineage_id=LINEAGE_ID,
        lineage_generation=1,
        profile_ref="profile-team-b",
        runtime_incarnation="runtime-b",
        invocation_id="invocation-b-1",
        domain_id="target-domain-b",
        manifest_digest=TARGET_MANIFEST,
    )
    operation_bc = ledger.prepare_swap(
        operation_id="swap-b-to-c",
        request_id="request-b-to-c",
        request_digest=_digest("b to c"),
        target_profile_ref="profile-team-c",
        target_manifest_digest=_digest("target manifest c"),
        parent_uuid=PARENT_UUID,
        claim_generation=claim_source_b["claim_generation"],
    )

    # The job's immutable admission generation stays A's, while B→C still
    # carries J1 and its live resource reservation in the operation roster.
    assert operation_bc["job_ids"] == ["job-j1"]
    persisted_job = ledger.status()["jobs"]["job-j1"]
    assert persisted_job["source_claim_generation"] == source_a["claim_generation"]
    assert persisted_job["state"] == "running"
    assert ledger.status()["reservations"][resource_id] == "job-j1"


def test_active_successor_settles_predecessor_job_without_another_swap(
        managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    provider = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, provider)
    source_a = _claim_source(ledger)
    resource_id = source_a["worktree_ids"][0]
    ledger.admit_job(
        job_id="job-a", request_id="request-a", request_digest=REQUEST_DIGEST,
        parent_uuid=PARENT_UUID, claim_generation=source_a["claim_generation"],
        command_digest=COMMAND_DIGEST, resource_ids=[resource_id],
    )
    ledger.begin_job_launch(job_id="job-a", request_digest=REQUEST_DIGEST)
    provider.jobs["job-a"] = {
        "command_digest": COMMAND_DIGEST, "state": "running",
        "effect_state": "known", "process_identity": {
            "pid": 3131, "start_token": "job-a-start",
            "domain_id": provider.persistent_job_domain_id,
        }, "output_ref": None, "result_digest": None,
    }
    operation = ledger.prepare_swap(
        operation_id="swap-a-b-active", request_id="request-swap-a-b",
        request_digest=_digest("swap-a-b-active"),
        target_profile_ref="profile-team-b", target_manifest_digest=TARGET_MANIFEST,
        parent_uuid=PARENT_UUID, claim_generation=source_a["claim_generation"],
    )
    ledger.observe_source_exclusion("swap-a-b-active")
    assert ledger.reconcile("swap-a-b-active")["phase"] == "ready-to-resume"
    assert ledger.status()["reservations"][resource_id] == "job-a"
    claim_b = ledger.claim_target(
        operation_id="swap-a-b-active", claimant_id="runtime-b-claimant",
        parent_uuid=PARENT_UUID, owner_generation=operation["owner_generation"],
        claim_generation=operation["target_claim_generation"],
        profile_ref="profile-team-b", manifest_digest=TARGET_MANIFEST,
    )
    ledger.authorize_release(
        operation_id="swap-a-b-active", release_id="release-a-b",
        target_claim_token=claim_b["claim_token"],
    )
    provider.target_state = "running"
    ledger.observe_target_start("swap-a-b-active")
    source_b = ledger.claim_source(
        supervisor_incarnation=SUPERVISOR_INCARNATION, parent_uuid=PARENT_UUID,
        lineage_id=LINEAGE_ID, lineage_generation=1,
        profile_ref="profile-team-b", runtime_incarnation="runtime-b",
        invocation_id="invocation-b-1", domain_id="target-domain-b",
        manifest_digest=TARGET_MANIFEST,
    )
    assert source_b["claim_generation"] > source_a["claim_generation"]
    provider.jobs["job-a"].update({
        "state": "completed", "effect_state": "known",
        "output_ref": "result-ref:job-a", "result_digest": _digest("job-a-result"),
    })
    observed = ledger.observe_active_job(
        job_id="job-a", parent_uuid=PARENT_UUID,
        claim_generation=source_b["claim_generation"],
        runtime_incarnation="runtime-b",
    )
    assert observed["state"] == "completed"
    assert resource_id not in ledger.status()["reservations"]
    ledger.admit_job(
        job_id="job-b", request_id="request-b",
        request_digest=_digest("job-b-request"), parent_uuid=PARENT_UUID,
        claim_generation=source_b["claim_generation"],
        command_digest=COMMAND_DIGEST, resource_ids=[resource_id],
    )
    assert ledger.status()["reservations"][resource_id] == "job-b"
    with pytest.raises(ManagedStateError) as retired_source:
        ledger.observe_active_job(
            job_id="job-a", parent_uuid=PARENT_UUID,
            claim_generation=source_a["claim_generation"],
            runtime_incarnation="runtime-a",
        )
    assert retired_source.value.code == "stale-generation"


def test_active_job_unknown_effect_and_fence_race_keep_reservation(
        managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    provider = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, provider)
    source = _claim_source(ledger)
    resource_id = source["worktree_ids"][0]
    ledger.admit_job(
        job_id="job-unknown", request_id="request-unknown",
        request_digest=REQUEST_DIGEST, parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
        command_digest=COMMAND_DIGEST, resource_ids=[resource_id],
    )
    ledger.begin_job_launch(job_id="job-unknown", request_digest=REQUEST_DIGEST)
    provider.jobs["job-unknown"] = {
        "command_digest": COMMAND_DIGEST, "state": "uncertain",
        "effect_state": "unknown", "process_identity": None,
        "output_ref": None, "result_digest": None,
    }
    with pytest.raises(ManagedStateError) as unknown:
        ledger.observe_active_job(
            job_id="job-unknown", parent_uuid=PARENT_UUID,
            claim_generation=source["claim_generation"],
            runtime_incarnation="runtime-a",
        )
    assert unknown.value.code == "uncertain-effect"
    assert ledger.status()["reservations"][resource_id] == "job-unknown"
    provider.jobs["job-unknown"].update({
        "state": "completed", "effect_state": "known",
        "output_ref": "result-ref:job-unknown",
        "result_digest": _digest("job-unknown-result"),
    })

    original = provider.job_status

    def fence_before_cas(binding, job_id):
        observation = original(binding, job_id)
        ledger.prepare_swap(
            operation_id="swap-during-job-observation", request_id="swap-race",
            request_digest=_digest("swap-race"),
            target_profile_ref="profile-team-b", target_manifest_digest=TARGET_MANIFEST,
            parent_uuid=PARENT_UUID, claim_generation=source["claim_generation"],
        )
        return observation

    provider.job_status = fence_before_cas
    with pytest.raises(ManagedStateError) as stale:
        ledger.observe_active_job(
            job_id="job-unknown", parent_uuid=PARENT_UUID,
            claim_generation=source["claim_generation"],
            runtime_incarnation="runtime-a",
        )
    assert stale.value.code == "stale-generation"
    assert ledger.status()["reservations"][resource_id] == "job-unknown"


def test_release_refuses_stale_watermarks_and_worktree_claim_change_during_observation(
        managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    provider = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, provider)
    source = _claim_source(ledger)
    operation = ledger.prepare_swap(
        operation_id="swap-stale-observation",
        request_id="request-stale-observation",
        request_digest=_digest("stale observation request"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=TARGET_MANIFEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )
    ledger.observe_source_exclusion("swap-stale-observation")
    assert ledger.reconcile("swap-stale-observation")["phase"] == "ready-to-resume"
    target_claim = ledger.claim_target(
        operation_id="swap-stale-observation",
        claimant_id="runtime-b-claimant",
        parent_uuid=PARENT_UUID,
        owner_generation=operation["owner_generation"],
        claim_generation=operation["target_claim_generation"],
        profile_ref="profile-team-b",
        manifest_digest=TARGET_MANIFEST,
    )

    persisted_floor = ledger.status()["observation_watermark"]
    # These witnesses advance relative to each other, but not beyond the last
    # persisted observation.  Without the source-witness floor check, a
    # no-job release could write this stale final watermark.
    provider.source_watermark_override = persisted_floor
    provider.history_watermark_override = persisted_floor + 1
    with pytest.raises(ManagedStateError) as stale_witness:
        ledger.authorize_release(
            operation_id="swap-stale-observation",
            release_id="release-stale-observation",
            target_claim_token=target_claim["claim_token"],
        )
    assert stale_witness.value.code == "stale-generation"
    operation_state = ledger.status()["operations"]["swap-stale-observation"]
    assert operation_state["release_intent"] is None
    assert operation_state["target_launch_intent"] is None


def test_release_refuses_worktree_claim_change_during_observation(
        managed_workspace, tmp_path):
    # A separate ready operation exercises the post-callback global-claim CAS:
    # no release intent is written if an exact claim disappears while evidence
    # callbacks run outside the state-lock critical section.
    store = _seed(managed_workspace, tmp_path)
    provider = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, provider)
    source = _claim_source(ledger)
    operation = ledger.prepare_swap(
        operation_id="swap-claim-change",
        request_id="request-claim-change",
        request_digest=_digest("claim change request"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=TARGET_MANIFEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )
    ledger.observe_source_exclusion("swap-claim-change")
    assert ledger.reconcile("swap-claim-change")["phase"] == "ready-to-resume"
    target_claim = ledger.claim_target(
        operation_id="swap-claim-change",
        claimant_id="runtime-b-claimant",
        parent_uuid=PARENT_UUID,
        owner_generation=operation["owner_generation"],
        claim_generation=operation["target_claim_generation"],
        profile_ref="profile-team-b",
        manifest_digest=TARGET_MANIFEST,
    )
    owner = store.read_owner()
    provider.on_source_exclusion = lambda: store.release_lineage_claim(
        LINEAGE_ID,
        coordinator_session_uuid=PARENT_UUID,
        owner_generation=owner["generation"],
        lineage_generation=1,
        authoritative=True,
    )
    with pytest.raises(ManagedStateError) as changed_claim:
        ledger.authorize_release(
            operation_id="swap-claim-change",
            release_id="release-claim-change",
            target_claim_token=target_claim["claim_token"],
        )
    assert changed_claim.value.code == "stale-generation"
    operation_state = ledger.status()["operations"]["swap-claim-change"]
    assert operation_state["phase"] == "indeterminate"
    assert operation_state["release_intent"] is None
    assert operation_state["target_launch_intent"] is None
