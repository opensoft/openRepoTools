# SPDX-License-Identifier: Apache-2.0
"""Offline fake-Engine tests for the private Docker source provider."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Mapping

import pytest

from lane_managed_state import ManagedStateError
from lane_managed_supervised_jobs import ClaudeCliSupervisedJobsLedger
from lane_managed_docker_source import (
    DockerSourceContainerProvider, LinuxCgroupV2MembershipProbe,
    RetainedCgroupV2Parent, _hash, normalize_config,
)
from lane_managed_claude_launch import REQUIRED_ENV, build_launch
from test_lane_managed_supervised_jobs import (
    PARENT_UUID, SOURCE_MANIFEST, SUPERVISOR_INCARNATION, _WitnessProvider,
    _claim_source, _digest, _seed,
)


ENGINE = {
    "endpoint_identity": "unix:test-docker",
    "engine_id": "docker-engine-fake",
    "engine_incarnation": "daemon-start-token-1",
    "host_boot_identity": "boot-id-fake",
    "os": "linux",
    "cgroup_driver": "systemd",
    "cgroup_version": 2,
    "rootless": False,
    "local_host": True,
    "live_restore": False,
}
CONTAINER_ID = "a" * 64
ALLOCATION_ID = "00000000-0000-4000-8000-000000000099"


def test_retained_cgroup_fd_maps_only_to_exact_host_mount():
    info = "41 30 0:27 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n"
    assert RetainedCgroupV2Parent._path_from_mountinfo(
        "/sys/fs/cgroup/l1/source", 41, info) == "/l1/source"
    escaped = "41 30 0:27 / /sys/fs/cgroup\\040host rw - cgroup2 cgroup rw\n"
    assert RetainedCgroupV2Parent._path_from_mountinfo(
        "/sys/fs/cgroup host/l1/source", 41, escaped) == "/l1/source"
    for fd_path, mountinfo in (
        ("/sys/fs/cgroup/l1/source (deleted)", info),
        ("/other/l1/source", info),
        ("/sys/fs/cgroup/l1/source", info.replace("cgroup2", "tmpfs")),
        ("/sys/fs/cgroup/l1/source", info.replace(" / /sys/", " /hidden /sys/")),
        ("/sys/fs/cgroup/l1/source", info + info),
    ):
        with pytest.raises(ManagedStateError):
            RetainedCgroupV2Parent._path_from_mountinfo(fd_path, 41, mountinfo)


def test_probe_rejects_a_caller_supplied_cgroup_path():
    parent = object.__new__(RetainedCgroupV2Parent)
    parent.cgroup_path = "/l1/source"
    parent.host_boot_identity = "boot-id-fake"
    parent.mount_id = 41
    parent.namespaces = {"pid": "pid:[1]", "cgroup": "cgroup:[1]", "mnt": "mnt:[1]"}
    job = object.__new__(RetainedCgroupV2Parent)
    job.cgroup_path = "/l1/jobs"
    job.host_boot_identity = parent.host_boot_identity
    job.mount_id = parent.mount_id
    job.namespaces = parent.namespaces
    with pytest.raises(ManagedStateError) as rejected:
        LinuxCgroupV2MembershipProbe(
            parent, parent_cgroup_path="/l1/other", job_domain=job,
            job_domain_id="jobs-cgroup-domain")
    assert rejected.value.code == "ownership-conflict"


def test_process_probe_reads_real_process_start_token_and_membership():
    start_token, cgroup_path = LinuxCgroupV2MembershipProbe._process(os.getpid())
    assert start_token.isdecimal()
    assert cgroup_path.startswith("/")
    assert LinuxCgroupV2MembershipProbe._process_start_token(
        Path("/proc") / str(os.getpid())
    ) == start_token


def test_job_witness_refuses_recycled_pid_or_process_moved_into_source():
    parent = object.__new__(RetainedCgroupV2Parent)
    parent.cgroup_path = "/l1/source"
    parent.host_boot_identity = "boot-id-fake"
    parent.mount_id = 41
    parent.namespaces = {"pid": "pid:[1]", "cgroup": "cgroup:[1]", "mnt": "mnt:[1]"}
    parent.snapshot = lambda: _parent()
    job = object.__new__(RetainedCgroupV2Parent)
    job.cgroup_path = "/l1/jobs"
    job.host_boot_identity = parent.host_boot_identity
    job.mount_id = parent.mount_id
    job.namespaces = parent.namespaces
    job.snapshot = lambda: _parent(populated=1)
    probe = LinuxCgroupV2MembershipProbe(
        parent, parent_cgroup_path="/l1/source", job_domain=job,
        job_domain_id="jobs-cgroup-domain")
    row = {
        "job_id": "job-one", "pid": 100, "start_token": "original-start",
        "domain_id": "jobs-cgroup-domain", "job_domain_id": "jobs-cgroup-domain",
    }
    probe._process = lambda pid: ("original-start", "/l1/jobs/worker")
    assert probe.job_domain_witness(
        _hash_parent(_parent()), "jobs-cgroup-domain", [row],
    )["membership_complete"] is False
    for observed in (("recycled-start", "/l1/jobs/worker"),
                     ("original-start", "/l1/source/escaped")):
        probe._process = lambda pid, observed=observed: observed
        with pytest.raises(ManagedStateError) as rejected:
            probe.job_domain_witness(_hash_parent(_parent()), "jobs-cgroup-domain", [row])
        assert rejected.value.code == "ownership-conflict"


def _hash_parent(snapshot):
    return {key: value for key, value in snapshot.items()
            if key not in {"populated", "frozen"}}


def _parent(populated: int = 0) -> dict:
    identity = {
        "allocation_id": ALLOCATION_ID,
        "host_boot_identity": ENGINE["host_boot_identity"],
        "mount_id": 41,
        "device": 52,
        "inode": 63,
        "cgroup_type": "domain",
    }
    identity["identity_digest"] = _hash(identity)
    return {**identity, "populated": populated, "frozen": 0}


def _source_identity(path: Path) -> str:
    info = path.stat()
    return _hash({
        "path": str(path), "device": info.st_dev, "inode": info.st_ino,
        "mode": __import__("stat").S_IFMT(info.st_mode), "uid": info.st_uid,
    })


def _config(tmp_path: Path, store) -> dict:
    roles = (
        ("worktree", False), ("repo_metadata", False), ("history", False),
        ("profile_config", True), ("job_broker", False),
    )
    mounts = []
    for role, read_only in roles:
        source = tmp_path / ("mount-" + role)
        source.mkdir()
        mounts.append({
            "role": role,
            "source_path": str(source),
            "source_identity": _source_identity(source),
            "target": {
                "worktree": "/workspace/current",
                "repo_metadata": "/run/l1/repository-metadata",
                "history": "/run/claude/history",
                "profile_config": "/run/claude/profile",
                "job_broker": "/run/l1/job-broker",
            }[role],
            "read_only": read_only,
            "propagation": "rprivate",
        })
    return {
        "image_digest": "sha256:" + "1" * 64,
        "cli_executable_digest": "sha256:" + "2" * 64,
        "entrypoint": ["/usr/local/libexec/claude-wait-for-release"],
        "user": "1000:1000",
        "read_only_rootfs": True,
        "no_new_privileges": True,
        "seccomp_digest": "3" * 64,
        "lsm_profile": "openrepotools-claude-source",
        "memory_limit_bytes": 1073741824,
        "pids_limit": 128,
        "restart_policy": "no",
        "auto_remove": False,
        "privileged": False,
        "pid_mode": "private",
        "ipc_mode": "private",
        "cgroup_mode": "private",
        "network_id": "network-source-egress",
        "network_policy_digest": "4" * 64,
        "published_ports": [],
        "cap_add": [],
        "cap_drop": ["ALL"],
        "devices": [],
        "device_requests": [],
        "mounts": mounts,
        "healthcheck": None,
        "init": False,
        "environment": list(REQUIRED_ENV),
        "extra_hosts": [],
        "claude_launch": build_launch(
            parent_uuid=PARENT_UUID,
            mcp_config_digest="5" * 64,
            settings_digest="6" * 64,
        ),
    }


class _FakeCgroup:
    evidence_kind = "offline-fake-test"

    def __init__(self):
        self.observation = _parent()
        self.supervisor_is_outside = True
        self.jobs_are_outside = True
        self.job_domain_live = True
        self.job_membership_complete = True

    def parent_snapshot(self):
        return dict(self.observation)

    def assert_engine_host(self, engine):
        return engine == ENGINE

    def bind_container(self, host_pid: int):
        return {
            "pid": host_pid,
            "start_token": "proc-start-1",
            "membership_digest": _digest("container-cgroup-path"),
            "parent_identity_digest": self.observation["identity_digest"],
        }

    def supervisor_outside(self, parent: Mapping[str, Any]) -> bool:
        return self.supervisor_is_outside

    def job_domain_witness(self, parent: Mapping[str, Any], job_domain_id: str,
                           jobs):
        return {
            "job_domain_id": job_domain_id,
            "domain_identity_digest": _digest("jobs-domain-identity"),
            "domain_live": self.job_domain_live,
            "outside_parent": self.jobs_are_outside,
            "membership_complete": self.job_membership_complete,
            "job_roster_digest": _hash(jobs),
            "live_processes_digest": _hash(jobs),
        }


class _FakeEngine:
    def __init__(self, cgroup: _FakeCgroup):
        self.cgroup = cgroup
        self.calls = []
        self.container = None

    def identity(self, *, deadline: float):
        assert deadline > 0
        return dict(ENGINE)

    def create(self, admission_id: str, config: Mapping[str, Any], *, deadline: float):
        self.calls.append(("create", admission_id))
        self.container = {
            "container_id": CONTAINER_ID,
            "creation_identity": "created-at-1",
            "configuration_digest": _hash(config),
            "state": "created",
            "running": False,
            "restarting": False,
            "paused": False,
            "removing": False,
            "init_pid": 0,
            "finished_identity": None,
            "exit_code": None,
            "exec_ids": [],
            "network_policy_digest": config["network_policy_digest"],
            "parent_allocation_id": ALLOCATION_ID,
        }
        return CONTAINER_ID

    def inspect(self, container_id: str, *, deadline: float):
        self.calls.append(("inspect", container_id))
        assert container_id == CONTAINER_ID
        return dict(self.container)

    def start(self, container_id: str, *, deadline: float):
        self.calls.append(("start", container_id))
        assert container_id == CONTAINER_ID
        self.container.update({
            "state": "running", "running": True, "init_pid": 5151,
        })
        self.cgroup.observation["populated"] = 1

    def kill(self, container_id: str, signal_name: str, *, deadline: float):
        self.calls.append(("kill", container_id, signal_name))
        assert container_id == CONTAINER_ID
        assert signal_name == "SIGKILL"
        self.container.update({
            "state": "exited", "running": False, "init_pid": 0,
            "finished_identity": "finished-at-2", "exit_code": 137,
        })
        self.cgroup.observation["populated"] = 0


def _provider(managed_workspace, tmp_path: Path, *, test_only_fake_witness=True):
    store = _seed(managed_workspace, tmp_path)
    delegate = _WitnessProvider()
    cgroup = _FakeCgroup()
    engine = _FakeEngine(cgroup)
    ledger = ClaudeCliSupervisedJobsLedger(store, delegate)
    provider = DockerSourceContainerProvider(
        ledger, engine, cgroup, "jobs-cgroup-domain", delegate,
        test_only_fake_witness=test_only_fake_witness,
    )
    ledger.witness_provider = provider
    source = _claim_source(ledger)
    config = _config(tmp_path, store)
    return ledger, provider, engine, cgroup, source, config


def _create_and_start(provider, source, config):
    admission_id = "00000000-0000-4000-8000-000000000088"
    created = provider.create_source(
        admission_id=admission_id,
        claim_generation=source["claim_generation"],
        parent_uuid=PARENT_UUID,
        runtime_incarnation=source["runtime_incarnation"],
        invocation_id=source["invocation_id"],
        source_domain_id=source["domain_id"],
        manifest_digest=source["manifest_digest"],
        config=config,
    )
    assert created["phase"] == "created"
    started = provider.start_source(admission_id, config=config)
    assert started["phase"] == "started"
    return admission_id


def test_docker_config_rejects_privilege_and_keeps_normal_tokens(managed_workspace, tmp_path):
    store = _seed(managed_workspace, tmp_path)
    config = _config(tmp_path, store)
    normalized = normalize_config(config, state_root=store.identity.state_root)
    assert normalized["network_id"] == "network-source-egress"

    config["privileged"] = True
    with pytest.raises(ManagedStateError) as rejected:
        normalize_config(config, state_root=store.identity.state_root)
    assert rejected.value.code == "unsupported"


@pytest.mark.parametrize("change", [
    lambda cfg: cfg["environment"].clear(),
    lambda cfg: cfg["claude_launch"]["environment"].clear(),
    lambda cfg: cfg["claude_launch"]["argv"].__setitem__(5, "default"),
    lambda cfg: cfg["claude_launch"]["argv"].append("--bg"),
    lambda cfg: cfg["claude_launch"]["argv"].remove("--restricted"),
    lambda cfg: cfg["claude_launch"].__setitem__("cli_version", "2.1.282"),
    lambda cfg: cfg["claude_launch"].__setitem__(
        "parent_uuid", "00000000-0000-4000-8000-000000000002"),
])
def test_docker_config_refuses_weakened_claude_policy(
        managed_workspace, tmp_path, change):
    store = _seed(managed_workspace, tmp_path)
    config = _config(tmp_path, store)
    change(config)
    with pytest.raises(ManagedStateError) as rejected:
        normalize_config(config, state_root=store.identity.state_root)
    assert rejected.value.code == "unsupported"


def test_source_create_refuses_claude_resume_of_different_parent(
        managed_workspace, tmp_path):
    _, provider, engine, _, source, config = _provider(managed_workspace, tmp_path)
    config["claude_launch"] = build_launch(
        parent_uuid="00000000-0000-4000-8000-000000000002",
        mcp_config_digest="5" * 64,
        settings_digest="6" * 64,
    )
    with pytest.raises(ManagedStateError) as rejected:
        provider.create_source(
            admission_id="00000000-0000-4000-8000-000000000088",
            claim_generation=source["claim_generation"],
            parent_uuid=PARENT_UUID,
            runtime_incarnation=source["runtime_incarnation"],
            invocation_id=source["invocation_id"],
            source_domain_id=source["domain_id"],
            manifest_digest=source["manifest_digest"],
            config=config,
        )
    assert rejected.value.code == "ownership-conflict"
    assert not engine.calls


def test_source_create_refuses_unattested_engine_host_before_mutation(
        managed_workspace, tmp_path):
    _, provider, engine, cgroup, source, config = _provider(managed_workspace, tmp_path)
    cgroup.assert_engine_host = lambda identity: False
    with pytest.raises(ManagedStateError) as rejected:
        provider.create_source(
            admission_id="00000000-0000-4000-8000-000000000088",
            claim_generation=source["claim_generation"],
            parent_uuid=PARENT_UUID,
            runtime_incarnation=source["runtime_incarnation"],
            invocation_id=source["invocation_id"],
            source_domain_id=source["domain_id"],
            manifest_digest=source["manifest_digest"],
            config=config,
        )
    assert rejected.value.code == "unsupported"
    assert not engine.calls


def test_source_exclusion_rechecks_container_parent_and_outside_domains(
        managed_workspace, tmp_path):
    ledger, provider, engine, cgroup, source, config = _provider(
        managed_workspace, tmp_path,
    )
    _create_and_start(provider, source, config)
    ledger.prepare_swap(
        operation_id="docker-stop-one",
        request_id="docker-stop-request",
        request_digest=_digest("docker-stop"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=_digest("target"),
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )
    stopped = provider.stop_source("docker-stop-one")
    assert stopped["phase"] == "stopped"
    assert [item[0] for item in engine.calls].count("kill") == 1

    first = ledger.observe_source_exclusion("docker-stop-one")
    assert first["source_exclusion"]["active_source_processes"] == 0
    first_inspections = [item for item in engine.calls if item[0] == "inspect"]
    second = ledger.observe_source_exclusion("docker-stop-one")
    assert second["source_exclusion"]["witness_digest"] != ""
    second_inspections = [item for item in engine.calls if item[0] == "inspect"]
    assert len(second_inspections) == len(first_inspections) + 1

    cgroup.observation["populated"] = 1
    with pytest.raises(ManagedStateError) as populated:
        ledger.observe_source_exclusion("docker-stop-one")
    assert populated.value.code == "unknown"


def test_source_stop_waits_for_one_kill_to_drain_without_replay(
        managed_workspace, tmp_path):
    ledger, provider, engine, cgroup, source, config = _provider(
        managed_workspace, tmp_path)
    _create_and_start(provider, source, config)
    ledger.prepare_swap(
        operation_id="docker-delayed-stop",
        request_id="docker-delayed-stop-request",
        request_digest=_digest("docker-delayed-stop"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=_digest("delayed-target"),
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )
    original_kill = engine.kill
    original_inspect = engine.inspect
    pending = {"remaining": 2}

    def delayed_kill(container_id, signal_name, *, deadline):
        original_kill(container_id, signal_name, deadline=deadline)
        engine.container.update({
            "state": "running", "running": True, "init_pid": 5151,
            "finished_identity": None, "exit_code": None,
        })
        cgroup.observation["populated"] = 1

    def delayed_inspect(container_id, *, deadline):
        if any(call[0] == "kill" for call in engine.calls):
            pending["remaining"] -= 1
            if pending["remaining"] <= 0:
                engine.container.update({
                    "state": "exited", "running": False, "init_pid": 0,
                    "finished_identity": "finished-after-drain", "exit_code": 137,
                })
                cgroup.observation["populated"] = 0
        return original_inspect(container_id, deadline=deadline)

    engine.kill = delayed_kill
    engine.inspect = delayed_inspect
    stopped = provider.stop_source("docker-delayed-stop")
    assert stopped["phase"] == "stopped"
    assert [call[0] for call in engine.calls].count("kill") == 1
    assert pending["remaining"] <= 0


def test_source_exclusion_refuses_jobs_inside_source_parent(managed_workspace, tmp_path):
    ledger, provider, engine, cgroup, source, config = _provider(
        managed_workspace, tmp_path,
    )
    _create_and_start(provider, source, config)
    ledger.prepare_swap(
        operation_id="docker-stop-two",
        request_id="docker-stop-request-two",
        request_digest=_digest("docker-stop-two"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=_digest("target-two"),
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )
    provider.stop_source("docker-stop-two")
    cgroup.jobs_are_outside = False

    with pytest.raises(ManagedStateError) as rejected:
        ledger.observe_source_exclusion("docker-stop-two")
    assert rejected.value.code == "unsupported"
    assert [item[0] for item in engine.calls].count("kill") == 1


def test_source_exclusion_refuses_unproven_job_domain_liveness(
        managed_workspace, tmp_path):
    ledger, provider, engine, cgroup, source, config = _provider(
        managed_workspace, tmp_path,
    )
    _create_and_start(provider, source, config)
    ledger.prepare_swap(
        operation_id="docker-stop-three",
        request_id="docker-stop-request-three",
        request_digest=_digest("docker-stop-three"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=_digest("target-three"),
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )
    provider.stop_source("docker-stop-three")
    cgroup.job_domain_live = False

    with pytest.raises(ManagedStateError) as rejected:
        ledger.observe_source_exclusion("docker-stop-three")
    assert rejected.value.code == "unsupported"


def test_production_source_exclusion_stays_disabled_without_host_broker(
        managed_workspace, tmp_path):
    _ledger, provider, _engine, _cgroup, _source, _config = _provider(
        managed_workspace, tmp_path, test_only_fake_witness=False,
    )
    with pytest.raises(ManagedStateError) as rejected:
        provider.source_exclusion({})
    assert rejected.value.code == "unsupported"


def test_docker_start_serializes_with_the_durable_source_fence(
        managed_workspace, tmp_path):
    ledger, provider, engine, cgroup, source, config = _provider(
        managed_workspace, tmp_path,
    )
    admission_id = "00000000-0000-4000-8000-000000000077"
    provider.create_source(
        admission_id=admission_id,
        claim_generation=source["claim_generation"],
        parent_uuid=PARENT_UUID,
        runtime_incarnation=source["runtime_incarnation"],
        invocation_id=source["invocation_id"],
        source_domain_id=source["domain_id"],
        manifest_digest=source["manifest_digest"],
        config=config,
    )

    entered = threading.Event()
    continue_start = threading.Event()

    class _BlockingStart(_FakeEngine):
        def start(self, container_id: str, *, deadline: float):
            entered.set()
            assert continue_start.wait(timeout=5)
            super().start(container_id, deadline=deadline)

    blocking_engine = _BlockingStart(cgroup)
    blocking_engine.container = engine.container
    provider.engine = blocking_engine
    start_result = []
    start_thread = threading.Thread(
        target=lambda: start_result.append(provider.start_source(admission_id, config=config)),
    )
    start_thread.start()
    assert entered.wait(timeout=5)
    fence_result = []
    fence_thread = threading.Thread(target=lambda: fence_result.append(ledger.prepare_swap(
        operation_id="fence-after-start",
        request_id="fence-after-start-request",
        request_digest=_digest("fence-after-start"),
        target_profile_ref="profile-team-b",
        target_manifest_digest=_digest("fence-target"),
        parent_uuid=PARENT_UUID,
        claim_generation=source["claim_generation"],
    )))
    fence_thread.start()
    assert not fence_result
    continue_start.set()
    start_thread.join(timeout=5)
    fence_thread.join(timeout=5)
    assert not start_thread.is_alive()
    assert not fence_thread.is_alive()
    assert start_result[0]["phase"] == "started"
    assert fence_result[0]["source_restart_denied"] is True
    with pytest.raises(ManagedStateError) as rejected:
        provider.start_source(admission_id, config=config)
    assert rejected.value.code in {"uncertain-effect", "ownership-conflict"}
