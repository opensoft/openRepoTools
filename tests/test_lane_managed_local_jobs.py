# SPDX-License-Identifier: Apache-2.0
"""Model-free Linux process tests for the persistent job supervisor backend."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from lane_managed_job_runner import ManagedJobRunner, ManagedJobWitnessAdapter
from lane_managed_local_jobs import (
    JobSupervisorService,
    LedgerCredentialVerifier,
    LocalJobExecutionDomain,
    _call_supervisor,
)
from lane_managed_state import ManagedStateError
from lane_managed_supervised_jobs import ClaudeCliSupervisedJobsLedger
from test_lane_managed_supervised_jobs import (
    PARENT_UUID,
    REQUEST_DIGEST,
    _WitnessProvider,
    _claim_source,
    _seed,
)


pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper domain")


def _setup(managed_workspace, tmp_path: Path, *, runtime: int = 8,
           output_limit: int = 1024):
    store = _seed(managed_workspace, tmp_path)
    witness = _WitnessProvider()
    ledger = ClaudeCliSupervisedJobsLedger(store, witness)
    source = _claim_source(ledger)
    domain_dir = tmp_path / "job-domain"
    domain_dir.mkdir(mode=0o700)
    domain = LocalJobExecutionDomain(
        domain_dir, "local-job-test", max_runtime_seconds=runtime,
        next_watermark=lambda floor: max(floor + 1, time.monotonic_ns()),
    )
    runner = ManagedJobRunner(ledger, domain, output_limit_bytes=output_limit)
    ledger.witness_provider = ManagedJobWitnessAdapter(runner, witness)
    return ledger, source, domain, runner


def _start(source, runner, cwd: Path, job_id: str, script: str):
    return runner.start_job(
        job_id=job_id, request_id="request-" + job_id,
        request_digest=REQUEST_DIGEST, parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
        argv=[sys.executable, "-c", script], cwd=str(cwd.resolve()),
        resource_ids=[source["worktree_ids"][0]],
        effects_scope="local-worktree",
    )


def test_worker_subreaps_orphan_and_preserves_one_job_identity(
        managed_workspace, tmp_path):
    ledger, source, domain, runner = _setup(managed_workspace, tmp_path)
    started = _start(
        source, runner, managed_workspace.workspace_repo, "job-orphan",
        "import subprocess,sys; subprocess.Popen([sys.executable,'-c',"
        "'import time; time.sleep(1.0)'],start_new_session=True); print('leader')",
    )
    identity = started["process_identity"]
    assert identity["domain_id"] == "local-job-test"
    assert domain.job_subtree_empty(job_id="job-orphan", process_identity=identity) is False
    with pytest.raises(ManagedStateError):
        _start(source, runner, managed_workspace.workspace_repo, "job-orphan", "print('again')")
    result = runner.wait_job("job-orphan", timeout=5)
    assert result["state"] == "completed"
    assert result["process_identity"] == identity
    assert runner.read_output("job-orphan") == b"leader\n"
    assert domain.job_subtree_empty(job_id="job-orphan", process_identity=identity)
    assert runner.read_result("job-orphan") == result
    assert ledger.status()["reservations"][source["worktree_ids"][0]] == "job-orphan"
    domain.runner = runner
    witness = domain.job_status_witness(
        binding={}, job_id="job-orphan", process_identity=identity,
        output_ref=result["output_ref"], result_digest=result["result_digest"],
        minimum_watermark=0,
    )
    assert witness["state"] == "completed"
    assert witness["effect_state"] == "known"
    with ledger._locked() as owner:
        state = ledger._load(owner)
        ledger._apply_job_observation(state, witness)
        state["observation_watermark"] = witness["observation_watermark"]
        ledger._write(state)
    (managed_workspace.workspace_repo / "later-writer.txt").write_text("changed")
    changed = domain.job_status_witness(
        binding={}, job_id="job-orphan", process_identity=identity,
        output_ref=result["output_ref"], result_digest=result["result_digest"],
        minimum_watermark=witness["observation_watermark"],
    )
    assert changed["state"] == "completed"
    assert changed["effect_state"] == "known"
    assert changed["witness_digest"] != witness["witness_digest"]
    receipts = list(domain.state_dir.glob("*.settlement.json"))
    assert len(receipts) == 1
    receipt = receipts[0]
    original = receipt.read_bytes()
    corrupted = json.loads(original)
    corrupted["result_digest"] = "0" * 64
    receipt.write_text(json.dumps(corrupted))
    with pytest.raises(ManagedStateError) as tampered:
        domain.job_status_witness(
            binding={}, job_id="job-orphan", process_identity=identity,
            output_ref=result["output_ref"], result_digest=result["result_digest"],
            minimum_watermark=changed["observation_watermark"],
        )
    assert tampered.value.code == "ownership-conflict"
    receipt.write_bytes(original)
    receipt.unlink()
    with pytest.raises(ManagedStateError) as missing:
        domain.job_status_witness(
            binding={}, job_id="job-orphan", process_identity=identity,
            output_ref=result["output_ref"], result_digest=result["result_digest"],
            minimum_watermark=changed["observation_watermark"],
        )
    assert missing.value.code == "uncertain-effect"


@pytest.mark.parametrize("output_bytes,expected_truncated", [
    (32, False), (33, True), (34, True),
])
def test_worker_output_boundary_is_finalized_without_uncertainty(
        managed_workspace, tmp_path, output_bytes, expected_truncated):
    _ledger, source, _domain, runner = _setup(
        managed_workspace, tmp_path, output_limit=32,
    )
    _start(source, runner, managed_workspace.workspace_repo,
           "job-output-%d" % output_bytes,
           "import sys; sys.stdout.write('x' * %d)" % output_bytes)
    result = runner.wait_job("job-output-%d" % output_bytes, timeout=5)
    assert result["state"] == "completed"
    assert result["output_truncated"] is expected_truncated
    assert runner.read_output("job-output-%d" % output_bytes) == b"x" * min(output_bytes, 32)


def test_running_known_scope_can_settle_first_terminal_receipt(
        managed_workspace, tmp_path):
    ledger, source, domain, runner = _setup(managed_workspace, tmp_path)
    started = _start(source, runner, managed_workspace.workspace_repo,
                     "job-running-settlement", "import time; time.sleep(2.0)")
    domain.runner = runner
    running = domain.job_status_witness(
        binding={}, job_id="job-running-settlement",
        process_identity=started["process_identity"],
        output_ref=started["output_ref"], result_digest=None,
        minimum_watermark=0,
    )
    assert running["state"] == "running"
    assert running["effect_state"] == "known"
    with ledger._locked() as owner:
        state = ledger._load(owner)
        ledger._apply_job_observation(state, running)
        state["observation_watermark"] = running["observation_watermark"]
        ledger._write(state)
    result = runner.wait_job("job-running-settlement", timeout=5)
    settled = domain.job_status_witness(
        binding={}, job_id="job-running-settlement",
        process_identity=started["process_identity"],
        output_ref=started["output_ref"],
        result_digest=result["result_digest"],
        minimum_watermark=running["observation_watermark"],
    )
    assert settled["state"] == "completed"
    assert settled["effect_state"] == "known"


def test_worktree_inventory_records_link_without_following_external_target(tmp_path):
    from lane_managed_local_jobs import _inventory
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("first")
    (root / "link").symlink_to(outside)
    before = _inventory(root, time.monotonic() + 2)
    outside.write_text("second")
    after = _inventory(root, time.monotonic() + 2)
    assert before == after


def test_job_cancellation_is_scoped_and_idempotent(managed_workspace, tmp_path):
    _ledger, source, domain, runner = _setup(managed_workspace, tmp_path)
    started = _start(source, runner, managed_workspace.workspace_repo,
                     "job-cancel", "import time; time.sleep(60)")
    identity = started["process_identity"]
    assert domain.request_cancel(job_id="job-cancel", process_identity=identity,
                                 cancel_id="cancel-once")["state"] == "cancel-requested"
    assert domain.request_cancel(job_id="job-cancel", process_identity=identity,
                                 cancel_id="cancel-once")["state"] in {"cancel-requested", "completed"}
    result = runner.wait_job("job-cancel", timeout=5)
    assert result["state"] == "failed"
    assert result["exit_code"] < 0


def test_scoped_credential_revokes_on_retired_source(managed_workspace, tmp_path):
    ledger, source, _domain, runner = _setup(managed_workspace, tmp_path)
    credential_root = tmp_path / "credentials"
    credential_root.mkdir(mode=0o700)
    authority = LedgerCredentialVerifier(ledger, credential_root)
    path = authority.issue_credential(
        credential_root / "source.json", parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
        runtime_incarnation=source["runtime_incarnation"],
    )
    from lane_managed_local_jobs import _credential
    credential = _credential(path)
    authority(credential, "start_job", "job-credential")
    ledger.prepare_swap(
        operation_id="swap-revokes-job-credential", request_id="swap-credential",
        request_digest=hashlib.sha256(b"swap credential").hexdigest(),
        target_profile_ref="profile-b",
        target_manifest_digest=hashlib.sha256(b"target manifest").hexdigest(),
        parent_uuid=PARENT_UUID, claim_generation=source["claim_generation"],
    )
    with pytest.raises(ManagedStateError) as error:
        authority(credential, "start_job", "job-after-retirement")
    assert error.value.code == "stale-generation"


def test_credential_preissue_is_inert_until_exact_source_claim(
        managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    ledger = ClaudeCliSupervisedJobsLedger(store, _WitnessProvider())
    credential_root = tmp_path / "preissued"
    credential_root.mkdir(mode=0o700)
    authority = LedgerCredentialVerifier(ledger, credential_root)
    path = authority.issue_credential(
        credential_root / "source.json", parent_uuid=PARENT_UUID,
        claim_generation=1, runtime_incarnation="runtime-a",
    )
    from lane_managed_local_jobs import _credential
    credential = _credential(path)
    with pytest.raises(ManagedStateError):
        authority(credential, "start_job", "job-before-claim")
    source = _claim_source(ledger)
    assert source["runtime_incarnation"] == "runtime-a"
    authority(credential, "start_job", "job-after-claim")

    future_path = authority.issue_credential(
        credential_root / "target.json", parent_uuid=PARENT_UUID,
        claim_generation=2, runtime_incarnation="runtime-b",
    )
    with pytest.raises(ManagedStateError) as future:
        authority(_credential(future_path), "start_job", "job-before-target")
    assert future.value.code == "stale-generation"


def test_authenticated_tool_service_reads_live_and_final_output(
        managed_workspace, tmp_path):
    ledger, source, _domain, runner = _setup(managed_workspace, tmp_path)
    control = tmp_path / "control"
    control.mkdir(mode=0o700)
    authority = LedgerCredentialVerifier(ledger, control)
    credential_path = authority.issue_credential(
        control / "source.json", parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
        runtime_incarnation=source["runtime_incarnation"],
    )
    from lane_managed_local_jobs import _credential
    credential = _credential(credential_path)
    socket_path = control / "jobs.sock"
    service = JobSupervisorService(socket_path, runner, authority)
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if socket_path.exists():
                break
            time.sleep(0.01)
        assert socket_path.exists()
        started = _call_supervisor(socket_path, credential, "start_job", {
            "job_id": "job-mcp", "request_id": "request-mcp",
            "argv": [sys.executable, "-c",
                     "import sys,time; print('first',flush=True); time.sleep(1.0); print('last')"],
            "cwd": str(managed_workspace.workspace_repo.resolve()),
            "resource_ids": [source["worktree_ids"][0]],
            "effects_scope": "local-worktree",
        })
        assert started["state"] == "running"
        live = _call_supervisor(socket_path, credential, "read_output",
                                {"job_id": "job-mcp", "limit_bytes": 16})
        assert live["finalized"] is False
        assert live["eof"] is False
        done = _call_supervisor(socket_path, credential, "wait_job",
                                {"job_id": "job-mcp", "timeout": 5})
        assert done["state"] == "completed"
        final = _call_supervisor(socket_path, credential, "read_output",
                                 {"job_id": "job-mcp", "limit_bytes": 16})
        assert final["finalized"] is True
        assert final["output_digest"] == done["output_digest"]
        with pytest.raises(ManagedStateError) as error:
            _call_supervisor(socket_path, credential, "create_runtime", {})
        assert error.value.code == "invalid"
    finally:
        service.stop()
        thread.join(timeout=2)


def test_mcp_stdio_bridge_exposes_bounded_job_tools_only(
        managed_workspace, tmp_path):
    ledger, source, _domain, runner = _setup(managed_workspace, tmp_path)
    control = tmp_path / "c"
    control.mkdir(mode=0o700)
    authority = LedgerCredentialVerifier(ledger, control)
    credential_path = authority.issue_credential(
        control / "source.json", parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
        runtime_incarnation=source["runtime_incarnation"],
    )
    socket_path = control / "s"
    service = JobSupervisorService(socket_path, runner, authority)
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if socket_path.exists():
                break
            time.sleep(0.01)
        assert socket_path.exists()
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "start_job", "arguments": {
                    "job_id": "job-mcp-wire", "request_id": "request-mcp-wire",
                    "argv": [sys.executable, "-c", "print('wire')"],
                    "cwd": str(managed_workspace.workspace_repo.resolve()),
                    "resource_ids": [source["worktree_ids"][0]],
                    "effects_scope": "local-worktree",
                }}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
                "name": "wait_job", "arguments": {
                    "job_id": "job-mcp-wire", "timeout": 5,
                }}},
        ]
        wire = b"".join(json.dumps(row).encode() + b"\n" for row in requests)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] /
                                 "lane_managed_local_jobs.py"),
             "mcp", str(socket_path), str(credential_path)],
            input=wire, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=12, check=False,
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        assert [row["id"] for row in replies] == [1, 2, 3, 4]
        names = {tool["name"] for tool in replies[1]["result"]["tools"]}
        assert names == {"start_job", "job_status", "read_output", "wait_job", "cancel_job"}
        started = json.loads(replies[2]["result"]["content"][0]["text"])
        finished = json.loads(replies[3]["result"]["content"][0]["text"])
        assert started["job_id"] == finished["job_id"] == "job-mcp-wire"
        assert finished["state"] == "completed"
    finally:
        service.stop()
        thread.join(timeout=2)
