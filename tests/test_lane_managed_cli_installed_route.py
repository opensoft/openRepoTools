# SPDX-License-Identifier: Apache-2.0
"""Private, versioned installed-route rehearsal with a live supervised job.

Both installations are the same frozen candidate bytes. The selector is a
fixture-local symlink, never a workstation command or global installation.
The real installed v1 supervisor, source custodian, ledger and job endpoint
stay alive while a client selects v2 and rolls back to v1. Only Claude is fake.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

from lane_managed_cli_control import control_endpoint, control_request
from lane_managed_cli_source import SourceCustodianLauncher, SourceCustodyError
from lane_managed_local_jobs import _call_supervisor, _credential
from lane_managed_state import ManagedStateError, ManagedStateStore, resolve_workspace
from lane_managed_supervised_jobs import ClaudeCliSupervisedJobsLedger
from test_lane_managed_cli_vertical import LANE, PARENT, REPO, _eventually, _fixture, _stop_exact


def _install_version(version: Path, fixture: dict) -> Path:
    env = dict(fixture["env"])
    env.update({"OPENREPOTOOLS_BIN_DIR": str(version / "bin"),
                "CLAUDE_PROFILES_HOME": str(version / "profiles"),
                "CLAUDE_USER_DIR": str(version / "claude")})
    env.pop("PYTHONPATH", None)
    result = subprocess.run([str(REPO / "openRepoTools"), "--install"],
                            cwd=REPO, env=env, capture_output=True, text=True,
                            timeout=40, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    # The installer owns shared skills, while the fixture supplies only fake
    # per-account metadata and a shared local history store.
    shutil.copytree(fixture["profiles"] / "profiles",
                    version / "profiles" / "profiles", symlinks=True,
                    dirs_exist_ok=True)
    for name in ("lane-managed-cli", "lane_managed_cli_control.py",
                 "lane_managed_cli_source.py", "lane_managed_local_jobs.py"):
        assert (version / "bin" / name).read_bytes() == (REPO / name).read_bytes()
    return version / "bin"


def _select(selector: Path, version_bin: Path) -> None:
    pending = selector.with_name(selector.name + ".next")
    pending.symlink_to(version_bin, target_is_directory=True)
    os.replace(pending, selector)
    assert selector.resolve(strict=True) == version_bin


def _status(selector: Path, env: dict) -> dict:
    result = subprocess.run([str(selector / "lane-managed-cli"), "status", LANE],
                            cwd=REPO, env=env, capture_output=True, text=True,
                            timeout=12, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper and job domain")
def test_private_installed_public_start_provisions_first_use_state(monkeypatch):
    with (tempfile.TemporaryDirectory(prefix="lci-public-",
                                      dir=os.environ.get("TMPDIR", "/tmp")) as name,
          tempfile.TemporaryDirectory(prefix="ortcli-", dir="/tmp") as runtime_name):
        root = Path(name)
        fixture = _fixture(root)
        installed = _install_version(root / "version", fixture)
        outside = root / "outside"
        outside.mkdir(mode=0o700)
        env = dict(fixture["env"])
        env.update({"CLAUDE_PROFILES_HOME": str(installed.parent / "profiles"),
                    "CLAUDE_USER_DIR": str(installed.parent / "claude"),
                    "OPENREPOTOOLS_BIN_DIR": str(installed),
                    "LANES_EDIT": str(installed / "lanes-edit.sh"),
                    "XDG_RUNTIME_DIR": runtime_name,
                    "PATH": str(installed) + os.pathsep + str(root / "b") +
                            os.pathsep + os.environ.get("PATH", "")})
        env.pop("PYTHONPATH", None)
        monkeypatch.setenv("XDG_RUNTIME_DIR", runtime_name)
        store = ManagedStateStore(resolve_workspace(LANE, env=env))
        managed_root = store.identity.common_dir / "openrepotools-managed"
        assert not managed_root.exists()
        assert not store.identity.global_root.exists()
        assert not store.identity.state_root.exists()
        service_pid = None
        custodian_pid = None
        source_pid = None
        source = None
        started = None
        try:
            started_command = subprocess.run(
                [str(installed / "lane-managed-cli"), "start", LANE,
                 "--source-profile", "team-a", "--target-profile", "team-b",
                 "--parent-uuid", PARENT, "--cwd", str(fixture["nested"])],
                cwd=outside, env=env, capture_output=True, text=True,
                timeout=25, check=False, preexec_fn=lambda: os.umask(0o022))
            assert started_command.returncode == 0, (started_command.stdout +
                                                     started_command.stderr)
            started = json.loads(started_command.stdout)
            endpoint = control_endpoint(LANE, env=env)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.connect(endpoint["socket"])
                service_pid = struct.unpack("3i", connection.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[0]
            assert control_request(endpoint["socket"], endpoint["credential_file"],
                                   "ping", {})["lane"] == LANE
            source = SourceCustodianLauncher(started["custodian_dir"])
            observed = _eventually(lambda: (
                answer if (answer := source.challenge())["prompt_ready"] else None))
            source_pid = observed["source"]["pid"]
            custodian_pid = observed["custodian"]["pid"]
            assert observed["session_start"]["source"] == "startup"
            for directory in (managed_root, store.identity.global_root,
                              store.identity.state_root,
                              store.identity.state_root / "cli-supervisor"):
                assert stat.S_IMODE(directory.stat().st_mode) == 0o700
            assert stat.S_IMODE((store.identity.state_root / "owner.json").stat().st_mode) == 0o600
            runtime_root = store.identity.state_root / "cli-supervisor" / "runtimes"
            manifests = list(runtime_root.glob("*/manifest.json"))
            admissions = list((store.identity.state_root / "cli-supervisor" /
                               "admissions").glob("*.json"))
            assert len(manifests) == len(admissions) == 1
            manifest = json.loads(manifests[0].read_text())
            assert Path(manifest["hook_observer_path"]) == installed / "lane-managed-cli"
            mcp = json.loads(Path(manifest["mcp_path"]).read_text())
            assert Path(mcp["mcpServers"]["lane-jobs"]["args"][0]) == (
                installed / "lane_managed_local_jobs.py")
            assert (installed / "lane_managed_cli_control.py").read_bytes() == (
                REPO / "lane_managed_cli_control.py").read_bytes()
            invocations = (installed.parent / "profiles" / "profiles" / "team-a" /
                           "fake-invocations.jsonl").read_text().splitlines()
            assert len(invocations) == 1
        finally:
            if service_pid is None:
                try:
                    endpoint = control_endpoint(LANE, env=env)
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                        connection.connect(endpoint["socket"])
                        service_pid = struct.unpack("3i", connection.getsockopt(
                            socket.SOL_SOCKET, socket.SO_PEERCRED,
                            struct.calcsize("3i")))[0]
                except (ManagedStateError, OSError):
                    pass
            if source is None and started is not None:
                try:
                    source = SourceCustodianLauncher(started["custodian_dir"])
                    last = source.challenge()
                    source_pid = last["source"]["pid"]
                    custodian_pid = last["custodian"]["pid"]
                except (KeyError, OSError, SourceCustodyError):
                    source = None
            if source is not None:
                try:
                    source.tty_write(b"/exit\r")
                    _eventually(lambda: source.challenge()["drained"], timeout=3)
                except (OSError, ManagedStateError, SourceCustodyError, AssertionError):
                    pass
            _stop_exact(source_pid)
            _stop_exact(custodian_pid)
            _stop_exact(service_pid)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper and job domain")
def test_private_installed_selector_rollback_preserves_live_job_and_v1_refs():
    with tempfile.TemporaryDirectory(prefix="lci-", dir=os.environ.get("TMPDIR", "/tmp")) as name:
        root = Path(name)
        fixture = _fixture(root)
        versions = root / "versions"
        v1 = _install_version(versions / "v1", fixture)
        v2 = _install_version(versions / "v2", fixture)
        selector = root / "selected"
        _select(selector, v1)
        env = dict(fixture["env"])
        env.update({"CLAUDE_PROFILES_HOME": str(v1.parent / "profiles"),
                    "CLAUDE_USER_DIR": str(v1.parent / "claude"),
                    "OPENREPOTOOLS_BIN_DIR": str(v1),
                    "LANES_EDIT": str(selector / "lanes-edit.sh"),
                    "PATH": str(root / "b") + os.pathsep + str(selector) +
                            os.pathsep + os.environ.get("PATH", "")})
        env.pop("PYTHONPATH", None)
        service = subprocess.Popen(
            [sys.executable, str(v1 / "lane_managed_cli_control.py"), "serve", LANE],
            cwd=root, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        barrier = root / "job-release"
        custodians: list[int] = []
        job_endpoint = None
        source_credential = None
        job_started = False
        try:
            def find_endpoint():
                status = service.poll()
                if status is not None:
                    raise AssertionError("installed v1 supervisor exited (%s): %s" %
                                         (status, service.stderr.read()))
                try:
                    return control_endpoint(LANE, env=env)
                except ManagedStateError:
                    return None

            endpoint = _eventually(find_endpoint)
            started = control_request(endpoint["socket"], endpoint["credential_file"],
                                      "start", {"source_profile": "team-a",
                                                "target_profile": "team-b",
                                                "parent_uuid": PARENT,
                                                "launch_mode": "fresh",
                                                "cwd": str(fixture["nested"])})
            source = SourceCustodianLauncher(started["custodian_dir"])
            observed = _eventually(lambda: (
                answer if (answer := source.challenge())["prompt_ready"] else None))
            custodians.append(observed["custodian"]["pid"])
            store = ManagedStateStore(resolve_workspace(LANE, env=env))
            ledger = ClaudeCliSupervisedJobsLedger(store)
            claim = ledger.status()["current_claim"]
            resource = claim["worktree_ids"][0]
            original_claims = store.read_lineage_claims()
            assert len(original_claims) == 1
            assert original_claims[0]["workspace"] == str(fixture["worktree"])
            assert original_claims[0]["repository"] == subprocess.run(
                ["git", "-C", str(fixture["worktree"]), "rev-parse",
                 "--path-format=absolute", "--git-common-dir"],
                capture_output=True, text=True, check=True).stdout.strip()

            manifest_path = (store.identity.state_root / "cli-supervisor" /
                             "runtimes" / started["runtime_id"] / "manifest.json")
            manifest = json.loads(manifest_path.read_text())
            runtime_root = store.identity.state_root / "cli-supervisor" / "runtimes"
            assert Path(manifest["settings_path"]).is_relative_to(runtime_root)
            assert Path(manifest["mcp_path"]).is_relative_to(runtime_root)
            assert Path(manifest["hook_observer_path"]).is_relative_to(v1)
            assert Path(manifest["mcp_path"]).is_file()
            immutable_bytes = {Path(manifest[key]): Path(manifest[key]).read_bytes()
                               for key in ("settings_path", "mcp_path", "hook_observer_path")}
            source_credential = _credential(Path(manifest["job_credential_path"]))
            mcp = json.loads(Path(manifest["mcp_path"]).read_text())
            bridge = Path(mcp["mcpServers"]["lane-jobs"]["args"][0])
            assert bridge.is_relative_to(v1)
            assert bridge.read_bytes() == (REPO / "lane_managed_local_jobs.py").read_bytes()
            job_endpoint = Path(mcp["mcpServers"]["lane-jobs"]["args"][2])
            script = textwrap.dedent("""
                import pathlib, sys, time
                root, release = (pathlib.Path(value) for value in sys.argv[1:])
                (root / 'installed-launch').write_text('one', encoding='utf-8')
                print('started', flush=True)
                deadline = time.monotonic() + 20
                while not release.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                if not release.exists():
                    raise SystemExit(91)
                (root / 'installed-result').write_text('done', encoding='utf-8')
                print('done', flush=True)
            """)
            job = _call_supervisor(job_endpoint, source_credential, "start_job", {
                "job_id": "installed-job", "request_id": "installed-job-request",
                "argv": [sys.executable, "-c", script,
                         str(fixture["nested"]), str(barrier)],
                "cwd": str(fixture["nested"]), "resource_ids": [resource],
                "effects_scope": "local-worktree"})
            job_started = True
            assert job["state"] == "running"
            _eventually(lambda: (fixture["nested"] / "installed-launch").exists())
            source_identity = source.challenge()["source"]
            job_identity = job["process_identity"]
            assert _status(selector, env)["current_claim"]["runtime_incarnation"] == started["runtime_id"]

            # The selector changes only which private installed client starts.
            # The already running v1 service, custodian and job keep their exact
            # identities and immutable v1 file references through rollback.
            _select(selector, v2)
            env["CLAUDE_PROFILES_HOME"] = str(v2.parent / "profiles")
            env["CLAUDE_USER_DIR"] = str(v2.parent / "claude")
            env["OPENREPOTOOLS_BIN_DIR"] = str(v2)
            switched = _status(selector, env)
            assert switched["current_claim"]["runtime_incarnation"] == started["runtime_id"]
            assert source.challenge()["source"] == source_identity
            assert store.read_lineage_claims() == original_claims
            assert _call_supervisor(job_endpoint, source_credential, "job_status",
                                    {"job_id": "installed-job"})["process_identity"] == job_identity
            assert ledger.status()["reservations"][resource] == "installed-job"
            assert not (fixture["nested"] / "installed-result").exists()
            assert all(path.read_bytes() == data for path, data in immutable_bytes.items())
            assert bridge.is_file() and Path(manifest["hook_observer_path"]).is_file()

            _select(selector, v1)
            env["CLAUDE_PROFILES_HOME"] = str(v1.parent / "profiles")
            env["CLAUDE_USER_DIR"] = str(v1.parent / "claude")
            env["OPENREPOTOOLS_BIN_DIR"] = str(v1)
            rolled_back = _status(selector, env)
            assert rolled_back["current_claim"]["runtime_incarnation"] == started["runtime_id"]
            assert source.challenge()["source"] == source_identity
            assert store.read_lineage_claims() == original_claims
            assert _call_supervisor(job_endpoint, source_credential, "job_status",
                                    {"job_id": "installed-job"})["process_identity"] == job_identity
            assert all(path.read_bytes() == data for path, data in immutable_bytes.items())
            assert v1.is_dir() and v2.is_dir()

            barrier.touch()
            completed = _call_supervisor(job_endpoint, source_credential, "wait_job",
                                         {"job_id": "installed-job", "timeout": 8})
            assert completed["state"] == "completed"
            assert ledger.status()["jobs"]["installed-job"]["state"] == "completed"
            assert resource not in ledger.status()["reservations"]
            assert (fixture["nested"] / "installed-launch").read_text() == "one"
            assert (fixture["nested"] / "installed-result").read_text() == "done"
            source.tty_write(b"/exit\r")
            _eventually(lambda: source.challenge()["drained"])
        finally:
            barrier.touch()
            if job_started and job_endpoint is not None and source_credential is not None:
                try:
                    _call_supervisor(job_endpoint, source_credential, "wait_job",
                                     {"job_id": "installed-job", "timeout": 3})
                except (ManagedStateError, OSError):
                    pass
            for journal in root.rglob("custodian.json"):
                try:
                    pid = json.loads(journal.read_text())["custodian"]["pid"]
                    if isinstance(pid, int) and pid not in custodians:
                        custodians.append(pid)
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            for pid in custodians:
                _stop_exact(pid)
            if service.poll() is None:
                service.send_signal(signal.SIGTERM)
            try:
                service.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                service.kill()
                service.communicate(timeout=4)
