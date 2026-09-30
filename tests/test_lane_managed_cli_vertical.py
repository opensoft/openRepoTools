# SPDX-License-Identifier: Apache-2.0
"""A model-free vertical test of the opt-in shared CLI session route.

The WIP state repository and the linked project worktree are real, distinct Git
repositories. The control and job sockets, ledger, subreaper custodian, history
reader, and job worker are production code. Only the Claude executable and its
local account/provider replies are emulated; no model or network is contacted.
"""

from __future__ import annotations

import json
import os
import runpy
import signal
import socket
import stat
import struct
import subprocess
import sys
import termios
import tty
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

from lane_managed_cli_control import LaneCliControlService, control_endpoint, control_request
from lane_managed_cli_source import SourceCustodianLauncher, SourceCustodyError
from lane_managed_local_jobs import _call_supervisor, _credential
from lane_managed_state import ManagedStateError, ManagedStateStore, resolve_workspace
from lane_managed_supervised_jobs import ClaudeCliSupervisedJobsLedger


REPO = Path(__file__).resolve().parents[1]
PARENT = "11111111-1111-4111-8111-111111111111"
LANE = "vertical"


_FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys
import termios
import tty

os.umask(0o077)
args = sys.argv[1:]
if args == ["--version"]:
    print("2.1.283 (Claude Code)")
    raise SystemExit(0)
if args == ["auth", "status", "--json"]:
    profile = Path(os.environ["CLAUDE_CONFIG_DIR"]).name
    email = "a@example.invalid" if profile == "team-a" else "b@example.invalid"
    print(json.dumps({"loggedIn": True, "email": email,
                      "accountId": "offline-" + profile}))
    raise SystemExit(0)

mode = "fresh" if "--session-id" in args else "resume"
parent = args[args.index("--session-id" if mode == "fresh" else "--resume") + 1]
settings = json.loads(Path(args[args.index("--settings") + 1]).read_text())
hook = settings["hooks"]["SessionStart"][0]["hooks"][0]
cwd = Path.cwd()
key = "".join(character if character.isascii() and character.isalnum()
              else "-" for character in str(cwd).replace("\\", "/"))
project = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / key
project.mkdir(parents=True, exist_ok=True)
transcript = project / (parent + ".jsonl")
if mode == "fresh":
    assert not transcript.exists()
    transcript.write_text(json.dumps({"type": "user", "sessionId": parent,
                                      "message": {"content": "offline parent"}}) + "\n" +
                          json.dumps({"type": "assistant", "sessionId": parent,
                                      "message": {"content": [{"type": "tool_use",
                                                              "name": "Agent",
                                                              "id": "toolu_offline"}]}}) + "\n")
    children = project / parent / "subagents"
    children.mkdir(parents=True)
    (children / "agent-child.meta.json").write_text('{"toolUseId":"toolu_offline"}\n')
    (children / "agent-child.jsonl").write_text(json.dumps({
        "type": "assistant", "sessionId": parent, "agentId": "child",
        "message": {"content": "offline child finished"}}) + "\n")
else:
    assert transcript.exists()
with (Path(os.environ["CLAUDE_CONFIG_DIR"]) / "fake-invocations.jsonl").open("a") as output:
    output.write(json.dumps({"mode": mode, "parent": parent, "cwd": str(cwd)}) + "\n")
if (cwd / ".fake-untrusted").exists():
    original = termios.tcgetattr(0)
    tty.setraw(0)
    try:
        print("Accessing workspace:\n" + str(cwd) + "\n"
              "Quick safety check: Is this a project you created or one you trust?\n"
              "Claude Code'll be able to read files.\n"
              "❯ No, exit\nYes, I trust this folder", flush=True)
        navigation = b""
        while len(navigation) < 3:
            navigation += os.read(0, 3 - len(navigation))
        assert navigation == b"\x1b[B", navigation
        print("No, exit\n❯ Yes, I trust this folder", flush=True)
        assert os.read(0, 1) in (b"\r", b"\n")
    finally:
        termios.tcsetattr(0, termios.TCSANOW, original)
event = {"hook_event_name": "SessionStart", "session_id": parent,
         "source": "startup" if mode == "fresh" else "resume",
         "cwd": str(cwd), "transcript_path": str(transcript.resolve())}
observed = subprocess.run([hook["command"], *hook["args"]],
                          input=json.dumps(event), text=True, capture_output=True)
assert observed.returncode == 0, observed.stderr
print("Claude Code v2.1.283\n❯", flush=True)
while True:
    line = sys.stdin.readline()
    if not line or line.strip() == "/exit":
        break
'''


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                               text=True, timeout=10, check=True)
    return completed.stdout.strip()


def _eventually(observe, *, timeout: float = 8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = observe()
        if result:
            return result
        time.sleep(0.03)
    raise AssertionError("vertical fixture did not reach the expected observed state")


def _stop_exact(pid: int | None) -> None:
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _accept_trust(launcher: SourceCustodianLauncher):
    try:
        offered = _eventually(lambda: (
            answer if (answer := launcher.challenge())["startup_trust_state"] == "offered"
            else None))
    except AssertionError as exc:
        raise AssertionError("trust UI was not offered: %r; terminal=%r" %
                             (launcher.challenge(), launcher.tty_read()[-1500:])) from exc
    assert offered["session_start"] is None
    assert offered["model_input_admitted"] is False or offered["launch_intent"].get(
        "launch_intent_id") is None
    assert launcher.tty_write(b"\x1b[B") == 3
    _eventually(lambda: launcher.challenge()["startup_trust_state"] == "confirm-selected")
    assert launcher.tty_write(b"\r") == 1


def _fixture(root: Path) -> dict:
    home = root / "h"
    agents = home / ".agents"
    wip = root / "w"
    project = root / "p"
    worktree = root / "t"
    nested = worktree / "nested"
    for path in (home, agents, wip, project):
        path.mkdir(mode=0o700, parents=True)
    _git(wip, "init", "-q")
    origin = root / "origin.git"
    _git(root, "init", "--bare", "-q", str(origin))
    _git(wip, "remote", "add", "origin", str(origin))
    _git(project, "init", "-q")
    _git(project, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
         "commit", "--allow-empty", "-qm", "base")
    _git(project, "worktree", "add", "-q", "-b", "vertical-linked", str(worktree))
    nested.mkdir(mode=0o700)
    (agents / "workspace.yaml").write_text(
        "repository: %s\npath: %s\n" % (origin, wip))
    (agents / "workspace.yaml").chmod(0o600)
    register = wip / "lanes" / "LANES.md"
    register.parent.mkdir(mode=0o700)
    register.write_text("# Offline fixture lane registry\n")

    config = root / "c"
    profiles = root / "f"
    manifest = config / "workbenches" / "claude-profiles.json"
    manifest.parent.mkdir(mode=0o700, parents=True)
    shared = profiles / "shared" / "projects"
    shared.mkdir(mode=0o700, parents=True)
    entries = []
    for name, email in (("team-a", "a@example.invalid"),
                        ("team-b", "b@example.invalid")):
        directory = profiles / "profiles" / name
        directory.mkdir(mode=0o700, parents=True)
        metadata = {"name": name, "email": email, "family": "fixture-family", "aliases": []}
        (directory / ".profile.json").write_text(json.dumps(metadata))
        (directory / "projects").symlink_to(shared, target_is_directory=True)
        entries.append({**metadata, "status": "active", "profilePath": name,
                        "authentication": {"type": "subscription_oauth"}})
    manifest.write_text(json.dumps({"version": 1, "profiles": entries}))
    manifest.chmod(0o600)

    fake_bin = root / "b"
    fake_bin.mkdir(mode=0o700)
    fake = fake_bin / "claude"
    fake.write_text(_FAKE_CLAUDE)
    fake.chmod(0o700)
    env = dict(os.environ)
    env.update({"HOME": str(home), "AGENT_PROTOCOL_ROOT": str(agents),
                "XDG_CONFIG_HOME": str(config), "CLAUDE_PROFILES_HOME": str(profiles),
                "CLAUDE_PROFILES_MANIFEST": str(manifest), "LANES_WORKSTATION": "vertical",
                "LANES_EDIT": str(REPO / "lanes-edit.sh"),
                "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")})
    return {"env": env, "wip": wip, "project": project, "worktree": worktree,
            "nested": nested, "profiles": profiles, "fake": fake}


@pytest.mark.skipif(sys.platform != "linux", reason="Linux control and source custody")
def test_public_start_provisions_private_state_on_first_use(tmp_path, monkeypatch, capsys,
                                                            request):
    fixture = _fixture(tmp_path)
    runtime_dir = tempfile.TemporaryDirectory(prefix="ortcli-", dir="/tmp")
    request.addfinalizer(runtime_dir.cleanup)
    runtime = Path(runtime_dir.name)
    fixture["env"]["XDG_RUNTIME_DIR"] = str(runtime)
    for key, value in fixture["env"].items():
        monkeypatch.setenv(key, value)
    identity = resolve_workspace(LANE, env=fixture["env"])
    managed_root = identity.common_dir / "openrepotools-managed"
    assert not managed_root.exists()
    assert not identity.global_root.exists()
    assert not identity.state_root.exists()

    cli_main = runpy.run_path(str(REPO / "lane-managed-cli"),
                              run_name="managed_cli_frontdoor")["main"]
    service_pid = None
    source_pid = None
    custodian_pid = None
    old_umask = os.umask(0o022)
    try:
        result = cli_main(["start", LANE, "--source-profile", "team-a",
                           "--target-profile", "team-b", "--parent-uuid", PARENT,
                           "--cwd", str(fixture["nested"])])
    finally:
        os.umask(old_umask)
    try:
        output = capsys.readouterr()
        assert result == 0, output.err
        started = json.loads(output.out)
        endpoint = control_endpoint(LANE, env=fixture["env"])
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
        assert observed["session_start"]["cwd"] == str(fixture["nested"])
        for directory in (managed_root, identity.global_root, identity.state_root,
                          identity.state_root / "cli-supervisor"):
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        assert stat.S_IMODE((identity.state_root / "owner.json").stat().st_mode) == 0o600
        assert len(list((identity.state_root / "cli-supervisor" /
                         "admissions").glob("*.json"))) == 1
        invocations = (fixture["profiles"] / "profiles" / "team-a" /
                       "fake-invocations.jsonl").read_text().splitlines()
        assert len(invocations) == 1
    finally:
        if service_pid is None:
            try:
                endpoint = control_endpoint(LANE, env=fixture["env"])
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                    connection.connect(endpoint["socket"])
                    service_pid = struct.unpack("3i", connection.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED,
                        struct.calcsize("3i")))[0]
            except (ManagedStateError, OSError):
                pass
        _stop_exact(source_pid)
        _stop_exact(custodian_pid)
        _stop_exact(service_pid)
        if service_pid is not None:
            try:
                os.waitpid(service_pid, 0)
            except ChildProcessError:
                pass


@pytest.mark.skipif(sys.platform != "linux", reason="Linux control and source custody")
def test_public_start_refuses_unsafe_existing_host_before_spawn(tmp_path, monkeypatch,
                                                                capsys, request):
    fixture = _fixture(tmp_path)
    runtime_dir = tempfile.TemporaryDirectory(prefix="ortcli-", dir="/tmp")
    request.addfinalizer(runtime_dir.cleanup)
    runtime = Path(runtime_dir.name)
    fixture["env"]["XDG_RUNTIME_DIR"] = str(runtime)
    for key, value in fixture["env"].items():
        monkeypatch.setenv(key, value)
    identity = resolve_workspace(LANE, env=fixture["env"])
    managed_root = identity.common_dir / "openrepotools-managed"
    managed_root.mkdir(mode=0o700)
    identity.global_root.mkdir(mode=0o755)
    assert stat.S_IMODE(identity.global_root.stat().st_mode) == 0o755
    cli_main = runpy.run_path(str(REPO / "lane-managed-cli"),
                              run_name="managed_cli_frontdoor")["main"]
    result = cli_main(["start", LANE, "--source-profile", "team-a",
                       "--target-profile", "team-b", "--parent-uuid", PARENT,
                       "--cwd", str(fixture["nested"])])
    output = capsys.readouterr()
    assert result == 2
    assert "not private" in output.err
    assert stat.S_IMODE(identity.global_root.stat().st_mode) == 0o755
    assert not identity.state_root.exists()
    assert not (identity.state_root / "cli-supervisor" / "control-credential.json").exists()
    assert not (identity.state_root / "cli-supervisor" / "session.json").exists()
    assert not list(runtime.rglob("*control.sock"))


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper and job domain")
def test_linked_worktree_source_job_and_target_cross_real_control_boundaries():
    with tempfile.TemporaryDirectory(prefix="lcv-", dir=os.environ.get("TMPDIR", "/tmp")) as name:
        fixture = _fixture(Path(name))
        (fixture["nested"] / ".fake-untrusted").write_text("fixture-only")
        env = fixture["env"]
        worktree = fixture["worktree"]
        project_common = _git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir")
        wip_common = _git(fixture["wip"], "rev-parse", "--path-format=absolute", "--git-common-dir")
        assert project_common != wip_common
        assert Path(_git(fixture["nested"], "rev-parse", "--show-toplevel")) == worktree
        service = subprocess.Popen(
            [sys.executable, str(REPO / "lane_managed_cli_control.py"), "serve", LANE],
            env=env, cwd=REPO, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        custodians: list[int] = []
        barrier = Path(name) / "job-release"
        second_barrier = Path(name) / "second-job-release"
        try:
            def find_endpoint():
                status = service.poll()
                if status is not None:
                    raise AssertionError(
                        "control service exited before readiness (%s): %s" %
                        (status, service.stderr.read()))
                try:
                    return control_endpoint(LANE, env=env)
                except ManagedStateError:
                    return None

            endpoint = _eventually(find_endpoint)
            def control(method: str, payload: dict) -> dict:
                return control_request(endpoint["socket"], endpoint["credential_file"],
                                       method, payload)

            started = control("start", {"source_profile": "team-a", "target_profile": "team-b",
                                        "parent_uuid": PARENT, "launch_mode": "fresh",
                                        "cwd": str(fixture["nested"])})
            source = SourceCustodianLauncher(started["custodian_dir"])
            _accept_trust(source)
            source_status = _eventually(lambda: (
                observed if (observed := source.challenge())["prompt_ready"] else None))
            custodians.append(source_status["custodian"]["pid"])
            assert source_status["session_start"]["cwd"] == str(fixture["nested"])

            # The installed terminal proxy owns /help locally. Its command
            # parser also exposes observation of the single durable target.
            help_result = subprocess.run(
                [sys.executable, str(REPO / "lane-managed-cli"), "observe-target", "--help"],
                env=env, cwd=REPO, capture_output=True, text=True, timeout=5)
            assert help_result.returncode == 0
            assert "operation_id" in help_result.stdout
            attached = subprocess.run(
                [sys.executable, str(REPO / "lane-managed-cli"), "attach",
                 started["custodian_dir"]],
                input=b"/help\r\x1d", env=env, cwd=REPO,
                capture_output=True, timeout=5)
            assert attached.returncode == 0, attached.stderr
            assert b"[managed terminal]" in attached.stdout
            assert source.challenge()["turn_sequence"] == 0
            assert source.challenge()["submission_pending"] is False

            store = ManagedStateStore(resolve_workspace(LANE, env=env))
            claims = store.read_lineage_claims()
            assert len(claims) == 1
            assert claims[0]["common_dir"] == wip_common
            assert claims[0]["repository"] == project_common
            assert claims[0]["workspace"] == str(worktree)
            ledger = ClaudeCliSupervisedJobsLedger(store)
            current = ledger.status()["current_claim"]
            resource = current["worktree_ids"][0]
            source_manifest = json.loads((store.identity.state_root / "cli-supervisor" /
                                          "runtimes" / started["runtime_id"] /
                                          "manifest.json").read_text())
            source_credential = _credential(Path(source_manifest["job_credential_path"]))
            job_socket = Path(source_manifest["mcp_path"])
            job_config = json.loads(job_socket.read_text())
            job_endpoint = Path(job_config["mcpServers"]["lane-jobs"]["args"][2])
            assert job_endpoint.is_socket()
            script = textwrap.dedent("""
                import pathlib, sys, time
                root, release = (pathlib.Path(value) for value in sys.argv[1:])
                marker = root / 'launch-count'
                with marker.open('x') as output:
                    output.write('one')
                print('job-started', flush=True)
                deadline = time.monotonic() + 20
                while not release.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                if not release.exists():
                    raise SystemExit(91)
                (root / 'job-result').write_text('completed-once')
                print('job-finished', flush=True)
            """)
            job = _call_supervisor(job_endpoint, source_credential, "start_job", {
                "job_id": "vertical-job", "request_id": "vertical-request",
                "argv": [sys.executable, "-c", script, str(fixture["nested"]), str(barrier)],
                "cwd": str(fixture["nested"]), "resource_ids": [resource],
                "effects_scope": "local-worktree"})
            assert job["state"] == "running"
            _eventually(lambda: (fixture["nested"] / "launch-count").exists())

            prepared = control("prepare", {"parent_uuid": PARENT,
                                           "runtime_id": started["runtime_id"]})
            operation_id = prepared["operation_id"]
            assert ledger.status()["operations"][operation_id]["source_restart_denied"] is True
            with pytest.raises(ManagedStateError) as revoked:
                _call_supervisor(job_endpoint, source_credential, "start_job", {
                    "job_id": "too-late", "request_id": "too-late",
                    "argv": [sys.executable, "-c", "pass"],
                    "cwd": str(fixture["nested"]), "resource_ids": [resource],
                    "effects_scope": "local-worktree"})
            assert revoked.value.code == "stale-generation"
            source.request_exit(operation_id=operation_id, parent_uuid=PARENT,
                                runtime_id=started["runtime_id"])
            _eventually(lambda: source.challenge()["drained"])
            assert (fixture["nested"] / "launch-count").read_text() == "one"
            assert not (fixture["nested"] / "job-result").exists()
            # A malformed final native-history tail is observed by the real
            # history reader. The first reconcile records uncertainty. Repair
            # the fake provider's one-time partial write, then retry the same
            # durable operation through the real control socket.
            transcript = Path(source_status["session_start"]["transcript_path"])
            saved_history = transcript.read_bytes()
            try:
                with transcript.open("ab") as stream:
                    stream.write(b'{"type":')
                with pytest.raises(ManagedStateError):
                    control("reconcile", {"operation_id": operation_id})
                assert ledger.status()["operations"][operation_id]["phase"] == "indeterminate"
                with pytest.raises(ManagedStateError) as premature:
                    control("release", {"operation_id": operation_id})
                assert premature.value.code == "busy"
            finally:
                transcript.write_bytes(saved_history)
            ready = control("reconcile", {"operation_id": operation_id})
            assert ready["phase"] == "ready-to-resume"
            assert ledger.status()["jobs"]["vertical-job"]["state"] == "running"

            # A target profile can be retargeted after reconciliation. The
            # release fence must reread the real projects link before it can
            # authorize or fork B, then permit the unchanged operation once
            # the original shared store is restored.
            target_projects = fixture["profiles"] / "profiles" / "team-b" / "projects"
            bound_history = target_projects.resolve(strict=True)
            other_history = fixture["profiles"] / "other-projects"
            other_history.mkdir(mode=0o700)
            config = json.loads((store.identity.state_root / "cli-supervisor" /
                                 "session.json").read_text())
            target_admission = (store.identity.state_root / "cli-supervisor" /
                                "admissions" / (config["target_runtime_id"] + ".json"))
            target_projects.unlink()
            target_projects.symlink_to(other_history, target_is_directory=True)
            try:
                with pytest.raises(ManagedStateError) as changed_history:
                    control("release", {"operation_id": operation_id})
                assert changed_history.value.code == "ownership-conflict"
                assert not target_admission.exists()
                assert ledger.status()["operations"][operation_id]["phase"] == "ready-to-resume"
            finally:
                target_projects.unlink()
                target_projects.symlink_to(bound_history, target_is_directory=True)

            # The client intentionally drops the release ACK. The service
            # persists and launches B exactly once; observe-target must find
            # that existing locator without asking release to spawn again.
            token = json.loads(Path(endpoint["credential_file"]).read_text())["token"]
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as dropped:
                dropped.connect(str(endpoint["socket"]))
                dropped.sendall((json.dumps({"credential": token, "method": "release",
                                             "payload": {"operation_id": operation_id}}) +
                                 "\n").encode())
            _eventually(lambda: (target_admission.exists() and
                                 json.loads(target_admission.read_text()).get("phase") ==
                                 "target-running"))
            released = control("observe-target", {"operation_id": operation_id})
            assert released["phase"] == "target-starting"
            target = SourceCustodianLauncher(released["custodian_dir"])
            assert target.challenge()["model_input_admitted"] is False
            pending_target = control("observe-target", {"operation_id": operation_id})
            assert pending_target == released
            assert ledger.status()["operations"][operation_id]["phase"] == "target-starting"
            _accept_trust(target)
            _eventually(lambda: target.challenge()["session_start"] is not None)
            with pytest.raises(SourceCustodyError, match="fenced"):
                target.tty_write(b"premature model prompt\r")
            observed_target = _eventually(lambda: (
                answer if (answer := control("observe-target", {"operation_id": operation_id}))
                ["phase"] == "target-observed" else None))
            assert observed_target["runtime_id"] == released["runtime_id"]
            assert target.challenge()["model_input_admitted"] is True
            assert control("observe-target", {"operation_id": operation_id}) == observed_target
            target_status = _eventually(lambda: (
                observed if (observed := target.challenge())["prompt_ready"] else None))
            custodians.append(target_status["custodian"]["pid"])
            assert target_status["session_start"]["cwd"] == str(fixture["nested"])
            assert released["runtime_id"] != started["runtime_id"]
            invocations = (fixture["profiles"] / "profiles" / "team-b" /
                           "fake-invocations.jsonl").read_text().splitlines()
            assert [json.loads(line)["mode"] for line in invocations] == ["resume"]
            assert json.loads(invocations[0])["parent"] == PARENT

            barrier.touch()
            target_manifest = json.loads((store.identity.state_root / "cli-supervisor" /
                                          "runtimes" / released["runtime_id"] /
                                          "manifest.json").read_text())
            target_credential = _credential(Path(target_manifest["job_credential_path"]))
            done = _call_supervisor(job_endpoint, target_credential, "wait_job",
                                    {"job_id": "vertical-job", "timeout": 8})
            assert done["state"] == "completed"
            output = _call_supervisor(job_endpoint, target_credential, "read_output",
                                      {"job_id": "vertical-job", "limit_bytes": 100})
            assert output["finalized"] is True
            assert (fixture["nested"] / "job-result").read_text() == "completed-once"
            assert (fixture["nested"] / "launch-count").read_text() == "one"
            assert ledger.status()["claim_generation"] == 2
            assert ledger.status()["jobs"]["vertical-job"]["state"] == "completed"
            assert resource not in ledger.status()["reservations"]

            # The authenticated B endpoint settles J1 while B is still active,
            # freeing the same registered worktree for a second admitted job.
            second_script = script.replace("launch-count", "second-launch-count").replace(
                "job-result", "second-result")
            second_job = _call_supervisor(job_endpoint, target_credential, "start_job", {
                "job_id": "second-job", "request_id": "second-request",
                "argv": [sys.executable, "-c", second_script,
                         str(fixture["nested"]), str(second_barrier)],
                "cwd": str(fixture["nested"]), "resource_ids": [resource],
                "effects_scope": "local-worktree"})
            assert second_job["state"] == "running"
            _eventually(lambda: (fixture["nested"] / "second-launch-count").exists())
            assert (fixture["nested"] / "second-launch-count").read_text() == "one"

            # The prior A and first release are stale once B owns generation 2.
            # Neither command may create a second B process or alter the job.
            with pytest.raises(ManagedStateError) as stale_a:
                control("prepare", {"parent_uuid": PARENT,
                                    "runtime_id": started["runtime_id"]})
            assert stale_a.value.code == "ownership-conflict"
            with pytest.raises(ManagedStateError) as duplicate_release:
                control("release", {"operation_id": operation_id})
            assert duplicate_release.value.code == "ownership-conflict"
            assert len((fixture["profiles"] / "profiles" / "team-b" /
                        "fake-invocations.jsonl").read_text().splitlines()) == 1

            # Rotate back to A through the same control, ledger, custody, and
            # history boundaries. This observation also settles the job that
            # completed while B was active; no job is launched a second time.
            second_prepared = control("prepare", {"parent_uuid": PARENT,
                                                   "runtime_id": released["runtime_id"]})
            second_operation = second_prepared["operation_id"]
            assert second_operation != operation_id
            target.request_exit(operation_id=second_operation, parent_uuid=PARENT,
                                runtime_id=released["runtime_id"])
            _eventually(lambda: target.challenge()["drained"])
            second_ready = control("reconcile", {"operation_id": second_operation})
            assert second_ready["phase"] == "ready-to-resume"
            assert ledger.status()["jobs"]["second-job"]["state"] == "running"
            assert ledger.status()["reservations"][resource] == "second-job"

            # A syntactically valid new native parent record after first ready
            # changes the pinned history. Explicit ready must reobserve it and
            # refuse release, even though the source is already drained.
            pinned_history = transcript.read_bytes()
            try:
                with transcript.open("ab") as stream:
                    stream.write((json.dumps({"type": "user", "sessionId": PARENT,
                                             "message": {"content": "late native turn"}}) +
                                  "\n").encode())
                with pytest.raises(ManagedStateError) as changed_parent:
                    control("reconcile", {"operation_id": second_operation})
                assert changed_parent.value.code == "ownership-conflict"
                assert ledger.status()["operations"][second_operation]["phase"] == "indeterminate"
                with pytest.raises(ManagedStateError) as premature_second_release:
                    control("release", {"operation_id": second_operation})
                assert premature_second_release.value.code == "busy"
            finally:
                transcript.write_bytes(pinned_history)

            second_barrier.touch()
            _eventually(lambda: (fixture["nested"] / "second-result").exists())

            def refreshed_ready():
                observed = control("reconcile", {"operation_id": second_operation})
                if (observed["phase"] == "ready-to-resume" and
                        ledger.status()["jobs"]["second-job"]["state"] == "completed"):
                    return observed
                return None

            second_ready = _eventually(refreshed_ready)
            assert second_ready["phase"] == "ready-to-resume"
            assert resource not in ledger.status()["reservations"]
            assert ledger.status()["jobs"]["vertical-job"]["state"] == "completed"
            second_released = control("release", {"operation_id": second_operation})
            assert second_released["phase"] == "target-starting"
            returned_a = SourceCustodianLauncher(second_released["custodian_dir"])
            pending_second = control("observe-target", {"operation_id": second_operation})
            assert pending_second == second_released
            _accept_trust(returned_a)
            observed_second = _eventually(lambda: (
                answer if (answer := control("observe-target", {"operation_id": second_operation}))
                ["phase"] == "target-observed" else None))
            assert observed_second["runtime_id"] == second_released["runtime_id"]
            assert second_released["runtime_id"] not in {
                started["runtime_id"], released["runtime_id"]}
            returned_status = _eventually(lambda: (
                observed if (observed := returned_a.challenge())["prompt_ready"] else None))
            custodians.append(returned_status["custodian"]["pid"])
            assert returned_status["session_start"]["cwd"] == str(fixture["nested"])
            a_invocations = (fixture["profiles"] / "profiles" / "team-a" /
                             "fake-invocations.jsonl").read_text().splitlines()
            assert [json.loads(line)["mode"] for line in a_invocations] == ["fresh", "resume"]
            assert all(json.loads(line)["parent"] == PARENT for line in a_invocations)
            assert ledger.status()["claim_generation"] == 3
            assert (fixture["nested"] / "launch-count").read_text() == "one"
            assert (fixture["nested"] / "job-result").read_text() == "completed-once"
            assert (fixture["nested"] / "second-launch-count").read_text() == "one"
            assert (fixture["nested"] / "second-result").read_text() == "completed-once"
            returned_a.tty_write(b"/exit\r")
            _eventually(lambda: returned_a.challenge()["drained"])
        finally:
            barrier.touch()
            second_barrier.touch()
            # Each journal belongs to this private fixture. Recover exact owned
            # custodian PIDs even if a control reply was lost before it returned.
            for journal in Path(name).rglob("custodian.json"):
                try:
                    pid = json.loads(journal.read_text())["custodian"]["pid"]
                    if isinstance(pid, int) and pid not in custodians:
                        custodians.append(pid)
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            for pid in custodians:
                _stop_exact(pid)
            service.terminate()
            try:
                service.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                service.kill()
                service.communicate(timeout=4)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper and job domain")
def test_owner_takeover_after_target_adoption_keeps_model_input_fenced(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="lcv-takeover-", dir=os.environ.get("TMPDIR", "/tmp")) as name:
        fixture = _fixture(Path(name))
        service = LaneCliControlService(LANE, env=fixture["env"])
        custodians = []
        try:
            started = service._start({"source_profile": "team-a", "target_profile": "team-b",
                                      "parent_uuid": PARENT, "launch_mode": "fresh",
                                      "cwd": str(fixture["nested"]),
                                      "claude_executable": str(fixture["fake"])})
            source = SourceCustodianLauncher(started["custodian_dir"])
            try:
                source_status = _eventually(lambda: (
                    answer if (answer := source.challenge())["prompt_ready"] else None))
            except AssertionError as exc:
                raise AssertionError("source startup failed: %r; terminal=%r" %
                                     (source.challenge(), source.tty_read()[-1500:])) from exc
            custodians.append(source_status["custodian"]["pid"])
            operation_id = service._prepare({"parent_uuid": PARENT,
                                             "runtime_id": started["runtime_id"]})["operation_id"]
            source.request_exit(operation_id=operation_id, parent_uuid=PARENT,
                                runtime_id=started["runtime_id"])
            _eventually(lambda: source.challenge()["drained"])
            assert service._reconcile({"operation_id": operation_id})["phase"] == "ready-to-resume"
            released = service._release({"operation_id": operation_id})
            assert released["phase"] == "target-starting"
            target = SourceCustodianLauncher(released["custodian_dir"])
            target_status = _eventually(lambda: (
                answer if (answer := target.challenge())["session_start"] is not None else None))
            custodians.append(target_status["custodian"]["pid"])
            assert target_status["model_input_admitted"] is False

            original_binding = service._write_custodian_binding
            def retire_owner_after_binding(runtime_id, parent_uuid):
                original_binding(runtime_id, parent_uuid)
                with service.store.locked():
                    owner = service.store._load_owner()
                    owner["generation"] += 1
                    service.store._write_owner(owner)
                    service.store._write_generation(owner["generation"])
            monkeypatch.setattr(service, "_write_custodian_binding",
                                retire_owner_after_binding)
            with pytest.raises(ManagedStateError) as refused:
                service._observe_target({"operation_id": operation_id})
            assert refused.value.code in {"stale-generation", "ownership-conflict"}
            assert target.challenge()["model_input_admitted"] is False
            with pytest.raises(SourceCustodyError, match="fenced"):
                target.tty_write(b"model prompt after stale takeover\r")
        finally:
            for journal in Path(name).rglob("custodian.json"):
                try:
                    pid = json.loads(journal.read_text())["custodian"]["pid"]
                    if isinstance(pid, int) and pid not in custodians:
                        custodians.append(pid)
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            for pid in custodians:
                _stop_exact(pid)


@pytest.mark.parametrize("kind", ["non-git", "bare"])
def test_project_git_identity_refuses_before_enrollment_intent(kind: str):
    with tempfile.TemporaryDirectory(prefix="lcv-", dir=os.environ.get("TMPDIR", "/tmp")) as name:
        fixture = _fixture(Path(name))
        invalid = Path(name) / "invalid"
        invalid.mkdir(mode=0o700)
        if kind == "bare":
            _git(invalid, "init", "--bare", "-q")
        service = LaneCliControlService(LANE, env=fixture["env"])
        with pytest.raises(ManagedStateError) as error:
            service.handle("start", {"source_profile": "team-a",
                                     "target_profile": "team-b", "parent_uuid": PARENT,
                                     "launch_mode": "fresh", "cwd": str(invalid)})
        assert error.value.code == "unsupported"
        assert not service.config_file.exists()
        assert service.store.read_lineage_claims() == []
        assert not service.job_socket.exists()
