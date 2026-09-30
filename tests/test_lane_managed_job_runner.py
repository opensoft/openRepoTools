# SPDX-License-Identifier: Apache-2.0
"""Offline contract tests for the private T053 job-runner foundation.

The injected domain below is a deterministic fake. It records a proposed
launch and writes fixture bytes, but never executes an operating-system
process. These tests prove one-shot intent handling, fail-closed result
custody, and the witness adapter path; they do not prove a production job
domain or host process isolation.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

import pytest

from lane_managed_docker_source import DockerSourceContainerProvider
from lane_managed_job_runner import (
    ManagedJobRunner,
    ManagedJobWitnessAdapter,
)
from lane_managed_state import ManagedStateError
from lane_managed_supervised_jobs import CAPABILITY, ClaudeCliSupervisedJobsLedger
from test_lane_managed_supervised_jobs import (
    PARENT_UUID,
    REQUEST_DIGEST,
    _WitnessProvider,
    _claim_source,
    _seed,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _OfflineJobDomain:
    """Fake authority for tests; it never launches or adopts an OS process."""

    persistent_job_domain_id = "test-cgroup:l1-jobs"

    def __init__(self, *, output: bytes = b"fixture output",
                 launch_error: bool = False, subtree_empty: bool = True,
                 result: Optional[Mapping[str, Any]] = None):
        self.output = output
        self.launch_error = launch_error
        self.subtree_empty = subtree_empty
        self.result = result or {"exit_code": 0, "output_truncated": False}
        self.launch_count = 0
        self.running = True
        self.terminal = False
        self.command_digest = None
        self.on_process_status = None

    def assert_ready(self) -> None:
        return None

    def launch_new(self, *, job_id: str, launch_intent_id: str,
                   argv, cwd: str, environment: Mapping[str, str],
                   output_fd: int, output_limit_bytes: int,
                   deadline: float) -> int:
        self.launch_count += 1
        if self.launch_error:
            raise RuntimeError("simulated lost launch acknowledgement")
        os.write(output_fd, self.output)
        return 4242

    def read_process_identity(self, pid: int) -> Mapping[str, Any]:
        return {
            "pid": pid,
            "start_token": "test-process-start-1",
            "domain_id": self.persistent_job_domain_id,
        }

    def process_is_running(self, process_identity: Mapping[str, Any]) -> bool:
        callback = self.on_process_status
        self.on_process_status = None
        if callback is not None:
            callback()
        return self.running

    def wait_result(self, *, job_id: str,
                    process_identity: Mapping[str, Any], timeout: float):
        self.running = False
        self.terminal = True
        return dict(self.result)

    def job_subtree_empty(self, *, job_id: str,
                          process_identity: Mapping[str, Any]) -> bool:
        return self.subtree_empty

    def job_status_witness(self, *, binding: Mapping[str, Any], job_id: str,
                           process_identity: Optional[Mapping[str, Any]],
                           output_ref: Optional[str], result_digest: Optional[str],
                           minimum_watermark: int) -> Mapping[str, Any]:
        watermark = minimum_watermark + 1
        return {
            "witness_id": "runner-test-witness-%d" % watermark,
            "witness_digest": _digest("runner-test-witness-%d" % watermark),
            "job_id": job_id,
            "command_digest": self.command_digest,
            "domain_id": self.persistent_job_domain_id,
            "observation_watermark": watermark,
            "state": "completed" if self.terminal else "running",
            "effect_state": "known" if self.terminal else "unknown",
            "process_identity": process_identity,
            "output_ref": output_ref,
            "result_digest": result_digest,
        }


def _setup(managed_workspace, tmp_path: Path, *, domain: _OfflineJobDomain):
    store = _seed(managed_workspace, tmp_path)
    delegate = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, delegate)
    source = _claim_source(ledger)
    runner = ManagedJobRunner(ledger, domain, output_limit_bytes=32)
    adapter = ManagedJobWitnessAdapter(runner, delegate)
    # Mirror the intended provider composition: DockerSourceContainerProvider
    # delegates its non-container witnesses to this adapter, and the ledger
    # gets job observations from the same trusted adapter.
    ledger.witness_provider = adapter
    return ledger, source, runner, adapter


def _start(ledger, source, runner, *, job_id: str, cwd: str,
           request_id: Optional[str] = None):
    return runner.start_job(
        job_id=job_id,
        request_id=request_id or "request-" + job_id,
        request_digest=REQUEST_DIGEST,
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
        argv=[sys.executable, "-c", "print('runner-test-argument')"],
        cwd=cwd,
        environment={"LANG": "C"},
        resource_ids=[source["worktree_ids"][0]],
    )


def test_runner_consumes_one_launch_intent_and_never_persists_command_text(
        managed_workspace, tmp_path):
    domain = _OfflineJobDomain()
    ledger, source, runner, _adapter = _setup(
        managed_workspace, tmp_path, domain=domain,
    )
    started = _start(
        ledger, source, runner, job_id="job-runner-once",
        cwd=str(managed_workspace.workspace_repo.resolve()),
    )

    assert started["state"] == "running"
    assert started["process_identity"]["pid"] == 4242
    assert domain.launch_count == 1
    state = ledger.status()
    admitted = state["jobs"]["job-runner-once"]
    assert admitted["state"] == "launch-intent"
    assert admitted["launch_state"] == "intent-recorded"
    assert state["reservations"][source["worktree_ids"][0]] == "job-runner-once"

    record_path = runner._record_path("job-runner-once")
    raw_record = record_path.read_bytes()
    assert b"runner-test-argument" not in raw_record
    assert os.fsencode(sys.executable) not in raw_record
    with pytest.raises(ManagedStateError):
        _start(
            ledger, source, runner, job_id="job-runner-once",
            cwd=str(managed_workspace.workspace_repo.resolve()),
        )
    assert domain.launch_count == 1


def test_lost_launch_acknowledgement_is_uncertain_and_not_replayed(
        managed_workspace, tmp_path):
    domain = _OfflineJobDomain(launch_error=True)
    ledger, source, runner, _adapter = _setup(
        managed_workspace, tmp_path, domain=domain,
    )
    with pytest.raises(ManagedStateError) as start_error:
        _start(
            ledger, source, runner, job_id="job-runner-lost-ack",
            cwd=str(managed_workspace.workspace_repo.resolve()),
        )
    assert start_error.value.code == "uncertain-effect"
    assert domain.launch_count == 1
    assert ledger.status()["jobs"]["job-runner-lost-ack"]["launch_state"] == "intent-recorded"
    assert runner._load_record("job-runner-lost-ack")["state"] == "uncertain"

    with pytest.raises(ManagedStateError):
        _start(
            ledger, source, runner, job_id="job-runner-lost-ack",
            cwd=str(managed_workspace.workspace_repo.resolve()),
        )
    assert domain.launch_count == 1


def test_source_fence_after_intent_prevents_os_dispatch(
        managed_workspace, tmp_path, monkeypatch):
    domain = _OfflineJobDomain()
    ledger, source, runner, _adapter = _setup(
        managed_workspace, tmp_path, domain=domain,
    )
    begin_job_launch = ledger.begin_job_launch

    def consume_then_fence(*, job_id: str, request_digest: str):
        intent = begin_job_launch(job_id=job_id, request_digest=request_digest)
        ledger.prepare_swap(
            operation_id="swap-between-intent-and-spawn",
            request_id="request-fence-between-intent-and-spawn",
            request_digest=_digest("swap fence request"),
            target_profile_ref="profile-team-b",
            target_manifest_digest=_digest("target manifest"),
            parent_uuid=PARENT_UUID,
            claim_generation=source["claim_generation"],
        )
        return intent

    monkeypatch.setattr(ledger, "begin_job_launch", consume_then_fence)
    with pytest.raises(ManagedStateError):
        _start(
            ledger, source, runner, job_id="job-runner-fenced-before-spawn",
            cwd=str(managed_workspace.workspace_repo.resolve()),
        )

    assert domain.launch_count == 0
    assert (
        ledger.status()["jobs"]["job-runner-fenced-before-spawn"]["launch_state"] ==
        "intent-recorded"
    )
    assert runner._load_record("job-runner-fenced-before-spawn")["state"] == "uncertain"


def test_leader_exit_with_live_descendant_keeps_reservation_and_no_result(
        managed_workspace, tmp_path):
    domain = _OfflineJobDomain(subtree_empty=False)
    ledger, source, runner, _adapter = _setup(
        managed_workspace, tmp_path, domain=domain,
    )
    _start(
        ledger, source, runner, job_id="job-runner-descendant",
        cwd=str(managed_workspace.workspace_repo.resolve()),
    )

    with pytest.raises(ManagedStateError) as wait_error:
        runner.wait_job("job-runner-descendant", timeout=0.25)
    assert wait_error.value.code == "uncertain-effect"
    record = runner._load_record("job-runner-descendant")
    assert record["state"] == "uncertain"
    assert record["uncertainty"] == "job-subtree-live"
    assert record["result_digest"] is None
    state = ledger.status()
    assert state["reservations"][source["worktree_ids"][0]] == "job-runner-descendant"


def test_stale_status_observation_cannot_overwrite_completed_wait(
        managed_workspace, tmp_path):
    domain = _OfflineJobDomain()
    ledger, source, runner, _adapter = _setup(
        managed_workspace, tmp_path, domain=domain,
    )
    _start(
        ledger, source, runner, job_id="job-runner-status-cas",
        cwd=str(managed_workspace.workspace_repo.resolve()),
    )
    domain.on_process_status = lambda: runner.wait_job(
        "job-runner-status-cas", timeout=0,
    )

    status = runner.status("job-runner-status-cas")
    record = runner._load_record("job-runner-status-cas")
    assert status["state"] == "completed"
    assert status["result_digest"] is not None
    assert record["state"] == "completed"
    assert record["result_digest"] == status["result_digest"]


def test_extra_output_byte_requires_matching_truncation_attestation(
        managed_workspace, tmp_path):
    domain = _OfflineJobDomain(
        output=b"x" * 33,
        result={"exit_code": 0, "output_truncated": False},
    )
    ledger, source, runner, _adapter = _setup(
        managed_workspace, tmp_path, domain=domain,
    )
    _start(
        ledger, source, runner, job_id="job-runner-truncation-mismatch",
        cwd=str(managed_workspace.workspace_repo.resolve()),
    )

    with pytest.raises(ManagedStateError) as wait_error:
        runner.wait_job("job-runner-truncation-mismatch", timeout=0)
    assert wait_error.value.code == "uncertain-effect"
    record = runner._load_record("job-runner-truncation-mismatch")
    assert record["state"] == "uncertain"
    assert record["uncertainty"] == "output-truncation-witness-mismatch"
    assert record["output_truncated"] is False
    assert record["result_digest"] is None
    assert (
        ledger.status()["reservations"][source["worktree_ids"][0]] ==
        "job-runner-truncation-mismatch"
    )


def test_terminal_result_requires_drain_and_bridges_through_docker_other(
        managed_workspace, tmp_path):
    domain = _OfflineJobDomain(output=b"captured result")
    ledger, source, runner, adapter = _setup(
        managed_workspace, tmp_path, domain=domain,
    )
    _start(
        ledger, source, runner, job_id="job-runner-result",
        cwd=str(managed_workspace.workspace_repo.resolve()),
    )
    domain.command_digest = ledger.status()["jobs"]["job-runner-result"]["command_digest"]

    result = runner.wait_job("job-runner-result", timeout=0)
    assert result["state"] == "completed"
    assert runner.read_output("job-runner-result") == b"captured result"
    assert result["output_size"] == len(b"captured result")

    provider = DockerSourceContainerProvider(
        ledger, engine=object(), cgroup=object(),
        job_domain_id=domain.persistent_job_domain_id,
        other_witness_provider=adapter,
    )
    assert adapter.persistent_job_domain_id == domain.persistent_job_domain_id
    job = ledger.status()["jobs"]["job-runner-result"]
    binding = {
        "capability": CAPABILITY,
        "owner_generation": job["owner_generation"],
        "parent_uuid": job["parent_uuid"],
        "lineage_id": job["lineage_id"],
        "lineage_generation": job["lineage_generation"],
        "source_claim_generation": job["source_claim_generation"],
        "worktree_ids": list(job["resource_ids"]),
    }
    witness = provider.job_status(binding, "job-runner-result")
    assert witness["state"] == "completed"
    assert witness["effect_state"] == "known"
    assert witness["process_identity"] == result["process_identity"]
    assert witness["output_ref"] == result["output_ref"]
    assert witness["result_digest"] == result["result_digest"]


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 10 ** 1000])
def test_wait_rejects_nonfinite_timeout_before_lookup(
        managed_workspace, tmp_path, timeout):
    domain = _OfflineJobDomain()
    ledger, _source, runner, _adapter = _setup(
        managed_workspace, tmp_path, domain=domain,
    )
    with pytest.raises(ManagedStateError) as wait_error:
        runner.wait_job("unknown-job", timeout=timeout)
    assert wait_error.value.code == "invalid"
