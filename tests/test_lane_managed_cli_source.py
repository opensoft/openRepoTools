# SPDX-License-Identifier: Apache-2.0
"""Model-free shared-PID-namespace source and manifest checks."""

import base64
import errno
import hashlib
import json
import os
import pathlib
import secrets
import subprocess
import sys
import time
import uuid

import pytest

import lane_managed_cli_source as source_module
from lane_managed_cli_source import (
    SharedParentRegistry, SharedSessionSourceProvider, SourceCustodianLauncher,
    SourceCustodyError, request,
)
from lane_managed_cli_runtime import (
    create_runtime_launch, runtime_launch_digest, validate_runtime_launch,
)
from lane_managed_state import ManagedStateError


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("bounded source observation timed out")


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper contract")
def test_first_custodian_challenge_waits_for_listen_without_replaying_start(tmp_path,
                                                                            monkeypatch):
    original_request = source_module.request
    attempts = {"challenge": 0, "start": 0}

    def delayed_listen(directory, credential, method, **arguments):
        if method == "challenge":
            attempts["challenge"] += 1
            if attempts["challenge"] == 1:
                raise ConnectionRefusedError(errno.ECONNREFUSED, "bind preceded listen")
        if method == "start":
            attempts["start"] += 1
        return original_request(directory, credential, method, **arguments)

    monkeypatch.setattr(source_module, "request", delayed_listen)
    directory = tmp_path / "custodian"
    identity = None
    try:
        result = SourceCustodianLauncher(str(directory)).launch(
            argv=[sys.executable, "-c", "pass"], environment=dict(os.environ),
            cwd=str(tmp_path), intent={"digest": "a" * 64},
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        identity = result["custodian"]
        assert attempts["challenge"] >= 2
        assert attempts["start"] == 1
        assert result["source"]["pid"] != identity["pid"]
    finally:
        if identity is not None:
            try:
                os.kill(identity["pid"], 15)
            except ProcessLookupError:
                pass


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper contract")
def test_lost_start_ack_keeps_intent_and_does_not_respawn(tmp_path, monkeypatch):
    original_request = source_module.request
    starts = []

    def lost_ack(directory, credential, method, **arguments):
        if method == "start":
            starts.append(original_request(directory, credential, method, **arguments))
            raise ConnectionRefusedError(errno.ECONNREFUSED, "lost start acknowledgment")
        return original_request(directory, credential, method, **arguments)

    monkeypatch.setattr(source_module, "request", lost_ack)
    directory = tmp_path / "custodian"
    launcher = SourceCustodianLauncher(str(directory))
    try:
        with pytest.raises(ConnectionRefusedError):
            launcher.launch(argv=[sys.executable, "-c", "pass"],
                            environment=dict(os.environ), cwd=str(tmp_path),
                            intent={"digest": "a" * 64}, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        journal = json.loads((directory / "launch.json").read_text())
        assert journal["phase"] == "custodian-ready"
        assert len(starts) == 1
        assert starts[0]["source"]["pid"] != journal["custodian"]["pid"]
        observed = original_request(directory, (directory / "credential").read_text(),
                                    "challenge", nonce=secrets.token_hex(16))
        assert observed["source"] == starts[0]["source"]
        with pytest.raises(SourceCustodyError, match="already exists"):
            launcher.launch(argv=[sys.executable, "-c", "pass"],
                            environment=dict(os.environ), cwd=str(tmp_path),
                            intent={"digest": "a" * 64})
        assert len(starts) == 1
    finally:
        if directory.exists():
            try:
                pid = json.loads((directory / "launch.json").read_text())["custodian"]["pid"]
                os.kill(pid, 15)
            except (OSError, ValueError, KeyError, TypeError):
                pass


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper contract")
def test_exact_source_drain_keeps_independent_session_and_job_alive(tmp_path):
    # C and J are independent children of the test/supervisor, never children
    # of A's custodian.  A's native-like double fork deliberately changes PGID.
    marker = tmp_path / "child-finished"
    c = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    j = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    custodian_dir = tmp_path / "a-custodian"
    code = ("import os,time,pathlib; pid=os.fork(); "
            "os._exit(0) if pid else None; os.setsid(); time.sleep(.45); "
            "pathlib.Path(%r).write_text('done'); os._exit(0)" % str(marker))
    try:
        result = SourceCustodianLauncher(str(custodian_dir)).launch(
            argv=[sys.executable, "-c", code], environment=dict(os.environ),
            cwd=str(tmp_path), intent={"digest": "a" * 64},
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        launcher = SourceCustodianLauncher(str(custodian_dir))
        exited = _wait_until(lambda: (
            answer if (answer := launcher.challenge()).get("source_exit") else None
        ))
        assert exited["source_exit"]["exited"] is True
        assert exited["drained"] is False
        assert c.poll() is None and j.poll() is None
        drained = _wait_until(lambda: (
            answer if (answer := launcher.challenge())["drained"] else None
        ))
        assert marker.read_text() == "done"
        assert drained["custodian"] == result["custodian"]
        assert drained["source"] == result["source"]
        assert c.poll() is None and j.poll() is None
        credential = (custodian_dir / "credential").read_text()
        with pytest.raises(SourceCustodyError, match="already consumed"):
            request(custodian_dir, credential, "start", argv=[sys.executable],
                    environment={}, cwd=str(tmp_path), intent={"digest": "b" * 64})
    finally:
        # Only processes created in this fixture are terminated, by exact PID.
        for process in (c, j):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=3)
        if custodian_dir.exists():
            try:
                identity = launcher.challenge()["custodian"]
                os.kill(identity["pid"], 15)
            except (NameError, OSError, SourceCustodyError):
                pass


@pytest.mark.skipif(sys.platform != "linux", reason="Linux PID namespace key")
def test_cross_lane_parent_registry_refuses_duplicate_and_wrong_transition(tmp_path):
    root = tmp_path / "registry"
    root.mkdir(mode=0o700)
    history = tmp_path / "history"
    history.mkdir()
    parent = str(uuid.uuid4())
    registry = SharedParentRegistry(str(root))
    first = registry.claim_source(
        history_store=str(history), parent_uuid=parent, lane="lane-a",
        generation=1, runtime_id=str(uuid.uuid4()), manifest_digest="a" * 64,
    )
    with pytest.raises(SourceCustodyError, match="already has"):
        registry.claim_source(
            history_store=str(history), parent_uuid=parent, lane="lane-c",
            generation=1, runtime_id=str(uuid.uuid4()), manifest_digest="b" * 64,
        )
    with pytest.raises(SourceCustodyError, match="identity or phase"):
        registry.transition(
            history_store=str(history), parent_uuid=parent, lane="lane-c",
            expected_phase="source-intent", phase="source-running",
            runtime_id=first["runtime_id"],
        )


def test_immutable_runtime_launch_refuses_credential_and_tool_policy_tamper(tmp_path):
    root = tmp_path / "runtimes"
    profile = tmp_path / "profile"
    cwd = tmp_path / "cwd"
    for path in (root, profile, cwd):
        path.mkdir(mode=0o700)
    credential = tmp_path / "credential"
    credential.write_text("source-scoped-token")
    credential.chmod(0o600)
    executable = tmp_path / "fake-claude"
    executable.write_text("#!/bin/sh\necho '2.1.283 (Claude Code)'\n")
    executable.chmod(0o700)
    module = pathlib.Path(__file__).resolve().parents[1] / "lane_managed_local_jobs.py"
    manifest = create_runtime_launch(
        root=str(root), runtime_id=str(uuid.uuid4()), parent_uuid=str(uuid.uuid4()),
        profile_ref="source", profile_config_dir=str(profile), session_name="lane-test",
        cwd=str(cwd),
        mcp_bridge_module=str(module), custodian_dir=str(tmp_path / "custodian"),
        job_socket=str(tmp_path / "job.sock"),
        job_credential_file=str(credential), claude_executable=str(executable),
        inherited_environment={"HOME": str(tmp_path), "ANTHROPIC_API_KEY": "wrong-seat",
                               "CLAUDE_CODE_HARBOR_KITE": "1",
                               "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"},
    )
    assert "ANTHROPIC_API_KEY" not in manifest["environment"]
    assert manifest["environment"]["CLAUDE_CODE_HARBOR_KITE"] == "0"
    assert manifest["environment"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "0"
    denied = manifest["argv"][manifest["argv"].index("--disallowedTools") + 1:
                              manifest["argv"].index("--settings")]
    assert denied == ["Bash", "PowerShell"]
    assert manifest["argv"][manifest["argv"].index("--tools") + 1] == \
        "Read,Glob,Grep,Edit,Write,NotebookEdit,Agent,SendMessage"
    settings_path = pathlib.Path(manifest["settings_path"])
    manifest_path = settings_path.with_name("manifest.json")
    original_settings = settings_path.read_bytes()
    original_manifest = manifest_path.read_bytes()
    settings = json.loads(original_settings)
    assert "SendMessage" in settings["permissions"]["allow"]
    assert settings["permissions"]["deny"] == ["Bash", "PowerShell"]
    assert {"Edit", "Write", "NotebookEdit"} <= set(settings["permissions"]["allow"])
    assert runtime_launch_digest(manifest)

    def canonical_bytes(value):
        return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True) + "\n").encode("utf-8")

    # Rewriting both a policy file and its manifest digest must still fail the
    # canonical allowlist, rather than passing a mere byte-integrity check.
    settings["permissions"]["allow"].remove("SendMessage")
    altered_settings = canonical_bytes(settings)
    settings_path.write_bytes(altered_settings)
    altered_manifest = dict(manifest)
    altered_manifest["settings_digest"] = hashlib.sha256(altered_settings).hexdigest()
    manifest_path.write_bytes(canonical_bytes(altered_manifest))
    with pytest.raises(ManagedStateError, match="settings policy changed"):
        validate_runtime_launch(altered_manifest)
    settings_path.write_bytes(original_settings)
    manifest_path.write_bytes(original_manifest)

    altered_manifest = dict(manifest)
    altered_manifest["environment"] = dict(manifest["environment"],
                                            CLAUDE_CODE_HARBOR_KITE="1")
    manifest_path.write_bytes(canonical_bytes(altered_manifest))
    with pytest.raises(ManagedStateError, match="effective per-runtime environment changed"):
        validate_runtime_launch(altered_manifest)
    manifest_path.write_bytes(original_manifest)

    altered_manifest = dict(manifest)
    altered_manifest["environment"] = dict(manifest["environment"],
                                            CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS="1")
    manifest_path.write_bytes(canonical_bytes(altered_manifest))
    with pytest.raises(ManagedStateError, match="effective per-runtime environment changed"):
        validate_runtime_launch(altered_manifest)
    manifest_path.write_bytes(original_manifest)

    altered_manifest = dict(manifest)
    altered_manifest["argv"] = list(manifest["argv"])
    altered_manifest["argv"][altered_manifest["argv"].index("--tools") + 1] = \
        "Read,Glob,Grep,Agent"
    manifest_path.write_bytes(canonical_bytes(altered_manifest))
    with pytest.raises(ManagedStateError, match="Claude foreground launch policy changed"):
        validate_runtime_launch(altered_manifest)
    manifest_path.write_bytes(original_manifest)

    with pytest.raises(ManagedStateError):
        create_runtime_launch(
            root=str(root), runtime_id=manifest["runtime_id"],
            parent_uuid=manifest["parent_uuid"], profile_ref="other",
            profile_config_dir=str(profile), session_name="lane-test", cwd=str(cwd),
            mcp_bridge_module=str(module), custodian_dir=str(tmp_path / "custodian"),
            job_socket=str(tmp_path / "job.sock"),
            job_credential_file=str(credential), claude_executable=str(executable),
        )
    credential.write_text("replaced")
    with pytest.raises(ManagedStateError, match="credential changed"):
        validate_runtime_launch(manifest)


def test_admitted_profile_history_store_cannot_be_rebound(tmp_path):
    root = tmp_path / "runtimes"
    profile = tmp_path / "profile"
    cwd = tmp_path / "project"
    original = tmp_path / "shared-history"
    replacement = tmp_path / "replacement-history"
    for path in (root, profile, cwd, original, replacement):
        path.mkdir(mode=0o700)
    (profile / "projects").symlink_to(original, target_is_directory=True)
    credential = tmp_path / "job-credential"
    credential.write_text("scoped")
    credential.chmod(0o600)
    executable = tmp_path / "fake-claude"
    executable.write_text("#!/bin/sh\necho '2.1.283 (Claude Code)'\n")
    executable.chmod(0o700)
    runtime_id = str(uuid.uuid4())
    parent = str(uuid.uuid4())
    manifest = create_runtime_launch(
        root=str(root), runtime_id=runtime_id, parent_uuid=parent,
        profile_ref="source", profile_config_dir=str(profile), session_name="lane-test",
        cwd=str(cwd), mcp_bridge_module=str(pathlib.Path(__file__).resolve().parents[1] /
                                              "lane_managed_local_jobs.py"),
        custodian_dir=str(tmp_path / "custodian"), job_socket=str(tmp_path / "job.sock"),
        job_credential_file=str(credential), claude_executable=str(executable),
        inherited_environment={"HOME": str(tmp_path)},
    )
    admission = {
        "manifest_path": str(root / runtime_id / "manifest.json"),
        "manifest_digest": runtime_launch_digest(manifest),
        "runtime_id": runtime_id, "parent_uuid": parent,
        "profile_ref": "source", "history_store": str(original),
    }
    assert SharedSessionSourceProvider._launch_manifest(admission) == manifest
    (profile / "projects").unlink()
    (profile / "projects").symlink_to(replacement, target_is_directory=True)
    with pytest.raises(SourceCustodyError, match="history store changed"):
        SharedSessionSourceProvider._launch_manifest(admission)


@pytest.mark.parametrize("hook_event_name", ["Stop", "StopFailure"])
def test_identical_stop_events_settle_distinct_turns_without_replay(
        monkeypatch, hook_event_name):
    custodian = object.__new__(source_module._Custodian)
    parent_uuid = str(uuid.uuid4())
    custodian.main_prompt_seen = False
    custodian.record = {
        "phase": "running", "turn_busy": True, "turn_sequence": 1,
        "turn_start_tick": 10, "stop_begin": None,
        "launch_intent": {"parent_uuid": parent_uuid},
        "source": {"pid": 100}, "session_started": True,
        "exit_requested": False,
    }
    custodian._record = lambda **changes: custodian.record.update(changes)
    custodian._source_descendant = lambda peer_pid: peer_pid in {201, 202, 203}
    monkeypatch.setattr(source_module, "_identity", lambda peer_pid: {
        "pid": peer_pid,
        "start_token": "boot:namespace:%d" % {201: 11, 202: 21, 203: 22}[peer_pid],
    })
    event = {"hook_event_name": hook_event_name, "session_id": parent_uuid}
    if hook_event_name == "Stop":
        event.update(background_tasks=[], session_crons=[], stop_hook_active=False)

    first = custodian._stop_begin(201)
    first_request = {"event": event, "ticket": first["ticket"],
                     "turn_sequence": first["turn_sequence"]}
    first_result = custodian._stop_event(first_request, 201)
    with pytest.raises(SourceCustodyError, match="settled parent turn"):
        custodian._stop_event(first_request, 201)

    custodian._record(turn_busy=True, turn_sequence=2, turn_start_tick=20,
                      turn_event_digest=None)
    with pytest.raises(SourceCustodyError, match="predates submitted turn"):
        custodian._stop_begin(201)
    second = custodian._stop_begin(202)
    with pytest.raises(SourceCustodyError, match="settled parent turn"):
        custodian._stop_event({**first_request, "turn_sequence": 2}, 202)
    second_request = {"event": event, "ticket": second["ticket"],
                      "turn_sequence": second["turn_sequence"]}
    with pytest.raises(SourceCustodyError, match="settled parent turn"):
        custodian._stop_event(second_request, 203)
    second_result = custodian._stop_event(second_request, 202)
    assert first_result["turn_sequence"] == 1
    assert second_result["turn_sequence"] == 2
    assert second_result["event_digest"] != first_result["event_digest"]


def test_continuous_pty_output_yields_to_custodian_socket(monkeypatch):
    custodian = object.__new__(source_module._Custodian)
    custodian.pty_master = 99
    custodian.pty_eof = False
    custodian.output_buffer = bytearray()
    custodian.output_dropped = 0
    custodian.prompt_tail = b""
    custodian.trust_tail = b""
    custodian.trust_offered_at = None
    custodian.trust_navigation_tail = b""
    custodian.main_ui_seen = False
    custodian.main_prompt_seen = False
    custodian.record = {"session_started": False, "startup_trust_state": "awaiting",
                        "launch_intent": {"cwd": "/private-project"}}
    reads = []

    def continuous_output(_fd, size):
        reads.append(size)
        if len(reads) > 8:
            raise AssertionError("PTY output kept the custodian from its socket loop")
        return b"x" * size

    monkeypatch.setattr(source_module.os, "read", continuous_output)
    custodian._pump_pty()
    assert reads == [32768] * 8
    assert len(custodian.output_buffer) == 256 * 1024
    assert custodian.pty_eof is False


@pytest.mark.parametrize("title_parts", [
    [b"Claude Code"],
    [b"ClaudeCode"],
    [b"Clau", b"de\x1b[1C\x1b[0mCode"],
])
def test_prompt_hint_accepts_measured_cli_title_renderings(monkeypatch, title_parts):
    custodian = object.__new__(source_module._Custodian)
    custodian.pty_master = 99
    custodian.pty_eof = False
    custodian.output_buffer = bytearray()
    custodian.output_dropped = 0
    custodian.prompt_tail = b""
    custodian.trust_tail = b""
    custodian.trust_offered_at = None
    custodian.trust_navigation_tail = b""
    custodian.main_ui_seen = False
    custodian.main_prompt_seen = False
    custodian.prompt_ready = False
    custodian.clean_epoch_pending = False
    custodian.input_clean = True
    custodian.input_line = bytearray()
    custodian.record = {"session_started": True, "turn_busy": False,
                        "submission_pending": False, "startup_trust_state": "complete",
                        "exit_requested": False}
    chunks = iter([*title_parts, b"v2.1.283\r\n\xe2\x9d\xaf "])

    def read_chunk(_fd, _size):
        try:
            return next(chunks)
        except StopIteration:
            raise BlockingIOError

    monkeypatch.setattr(source_module.os, "read", read_chunk)
    custodian._pump_pty()
    assert custodian.main_ui_seen is True
    assert custodian.prompt_ready is True


@pytest.mark.parametrize("session_started", [False, True])
def test_chooser_prompt_without_main_title_never_sets_ready(monkeypatch, session_started):
    custodian = object.__new__(source_module._Custodian)
    custodian.pty_master = 99
    custodian.pty_eof = False
    custodian.output_buffer = bytearray()
    custodian.output_dropped = 0
    custodian.prompt_tail = b""
    custodian.trust_tail = b""
    custodian.trust_offered_at = None
    custodian.trust_navigation_tail = b""
    custodian.main_ui_seen = False
    custodian.main_prompt_seen = False
    custodian.prompt_ready = False
    custodian.record = {"session_started": session_started, "turn_busy": False,
                        "submission_pending": False, "startup_trust_state": "complete",
                        "exit_requested": False}
    chunks = iter([b"Choose account\r\n\xe2\x9d\xaf 1", b""])
    monkeypatch.setattr(source_module.os, "read", lambda _fd, _size: next(chunks))
    custodian._pump_pty()
    assert custodian.main_ui_seen is False
    assert custodian.prompt_ready is False


def test_prompt_drawn_before_exact_session_start_becomes_ready(monkeypatch):
    custodian = object.__new__(source_module._Custodian)
    custodian.pty_master = 99
    custodian.pty_eof = False
    custodian.output_buffer = bytearray()
    custodian.output_dropped = 0
    custodian.prompt_tail = b""
    custodian.trust_tail = b""
    custodian.trust_offered_at = None
    custodian.trust_navigation_tail = b""
    custodian.main_ui_seen = False
    custodian.main_prompt_seen = False
    custodian.prompt_ready = False
    custodian.clean_epoch_pending = False
    custodian.input_clean = False
    custodian.input_line = bytearray()
    parent = str(uuid.uuid4())
    custodian.record = {
        "phase": "running", "session_started": False,
        "launch_intent": {"parent_uuid": parent, "cwd": "/private-project"},
        "turn_busy": False, "exit_requested": False,
        "submission_pending": False, "startup_trust_state": "awaiting",
    }
    custodian._record = lambda **changes: custodian.record.update(changes)
    custodian._source_descendant = lambda pid: pid == 201
    monkeypatch.setattr(source_module, "_identity", lambda pid: {"pid": pid})
    chunks = iter([b"Claude\x1b[19GCode v2.1.283\r\n\xe2\x9d\xaf ", b""])
    monkeypatch.setattr(source_module.os, "read", lambda _fd, _size: next(chunks))
    custodian._pump_pty()
    assert custodian.main_ui_seen is True
    assert custodian.main_prompt_seen is True
    assert custodian.prompt_ready is False
    custodian._session_start({"event": {
        "hook_event_name": "SessionStart", "session_id": parent,
        "source": "startup", "cwd": "/private-project",
        "transcript_path": "/private-project/parent.jsonl",
    }}, 201)
    assert custodian.prompt_ready is True


def test_next_prompt_waits_for_exact_stop_ticket_when_drawn_early(monkeypatch):
    custodian = object.__new__(source_module._Custodian)
    custodian.pty_master = 99
    custodian.pty_eof = False
    custodian.output_buffer = bytearray()
    custodian.output_dropped = 0
    custodian.prompt_tail = b""
    custodian.trust_tail = b""
    custodian.trust_offered_at = None
    custodian.trust_navigation_tail = b""
    custodian.main_ui_seen = True
    custodian.main_prompt_seen = False
    custodian.prompt_ready = False
    custodian.clean_epoch_pending = False
    custodian.input_clean = False
    custodian.input_line = bytearray()
    parent = str(uuid.uuid4())
    ticket = "t" * 64
    peer = {"pid": 201, "start_token": "boot:ns:123"}
    custodian.record = {
        "phase": "running", "session_started": True,
        "launch_intent": {"parent_uuid": parent},
        "source": {"pid": 100}, "turn_busy": True,
        "turn_sequence": 1, "exit_requested": False,
        "submission_pending": False, "startup_trust_state": "complete",
        "stop_begin": {
            "ticket_digest": source_module.hashlib.sha256(ticket.encode()).hexdigest(),
            "peer": peer, "turn_sequence": 1,
        },
    }
    custodian._record = lambda **changes: custodian.record.update(changes)
    custodian._source_descendant = lambda pid: pid == 201
    monkeypatch.setattr(source_module, "_identity", lambda pid: peer)
    chunks = iter([b"\r\n\xe2\x9d\xaf ", b""])
    monkeypatch.setattr(source_module.os, "read", lambda _fd, _size: next(chunks))
    custodian._pump_pty()
    assert custodian.main_prompt_seen is True
    assert custodian.prompt_ready is False
    event = {"hook_event_name": "Stop", "session_id": parent,
             "background_tasks": [], "session_crons": [],
             "stop_hook_active": False}
    with pytest.raises(SourceCustodyError, match="settled parent turn"):
        custodian._stop_event({"event": event, "ticket": "wrong",
                               "turn_sequence": 1}, 201)
    assert custodian.prompt_ready is False
    custodian._stop_event({"event": event, "ticket": ticket,
                           "turn_sequence": 1}, 201)
    assert custodian.record["turn_busy"] is False
    assert custodian.prompt_ready is True


def _input_custodian(monkeypatch, *, started=True, target=False):
    custodian = object.__new__(source_module._Custodian)
    parent = str(uuid.uuid4())
    intent = {"parent_uuid": parent, "runtime_id": "runtime-1",
              "cwd": "/private-project", "manifest_digest": "a" * 64}
    if target:
        intent["launch_intent_id"] = "target-launch-one"
    custodian.record = {
        "phase": "running", "source": {"pid": 100}, "source_exit": None,
        "launch_intent": intent, "exit_requested": False,
        "session_started": started,
        "session_start": ({"cwd": "/private-project",
                           "transcript_path": "/private-project/parent.jsonl"}
                          if started else None),
        "startup_trust_state": "complete" if started else "awaiting",
        "model_input_admitted": started and not target,
        "submission_pending": False, "turn_busy": False,
        "turn_sequence": 0, "turn_start_tick": None, "stop_begin": None,
    }
    custodian._record = lambda **changes: custodian.record.update(changes)
    custodian._reap = lambda: None
    custodian._source_descendant = lambda pid: pid == 201
    ticks = iter((100, 100, 101, 102))
    custodian._boot_tick = lambda: next(ticks, 102)
    custodian.pty_master = 99
    custodian.pty_eof = False
    custodian.output_buffer = bytearray()
    custodian.output_dropped = 0
    custodian.prompt_tail = b""
    custodian.trust_tail = b""
    custodian.trust_offered_at = None
    custodian.trust_navigation_tail = b""
    custodian.trust_key_buffer = b""
    custodian.main_ui_seen = started
    custodian.main_prompt_seen = started
    custodian.prompt_ready = started
    custodian.input_line = bytearray()
    custodian.input_clean = started
    custodian.clean_epoch_pending = False
    writes = []
    monkeypatch.setattr(source_module.os, "write", lambda _fd, data: writes.append(data) or len(data))
    monkeypatch.setattr(source_module, "_identity", lambda pid: {
        "pid": pid, "start_token": "boot:ns:101"})
    return custodian, parent, writes


def _input(custodian, data):
    return custodian._tty_write({"data": base64.b64encode(data).decode("ascii")})


def _emit(monkeypatch, custodian, data):
    chunks = iter((data,))
    def read(_fd, _size):
        try:
            return next(chunks)
        except StopIteration:
            raise BlockingIOError
    monkeypatch.setattr(source_module.os, "read", read)
    custodian._pump_pty()


def test_pending_prompt_survives_echo_repaint_until_authenticated_begin_and_stop(monkeypatch):
    custodian, parent, writes = _input_custodian(monkeypatch)
    _input(custodian, b"h")
    _emit(monkeypatch, custodian, b"h\r\n\xe2\x9d\xaf ")
    assert custodian.input_line == b"h"
    assert _input(custodian, b"\r") == {"written": 1}
    assert writes == [b"h", b"\r"]
    assert custodian.record["submission_pending"] is True
    assert custodian.record["turn_busy"] is False
    assert custodian.record["turn_start_tick"] == 100
    _emit(monkeypatch, custodian, b"ClaudeCodev2.1.283\r\n\xe2\x9d\xaf ")
    assert custodian.prompt_ready is False
    with pytest.raises(SourceCustodyError, match="fenced"):
        _input(custodian, b"again\r")
    with pytest.raises(SourceCustodyError, match="not admitted"):
        custodian._prompt_begin({"event": {"hook_event_name": "UserPromptSubmit",
                                           "session_id": str(uuid.uuid4()),
                                           "cwd": "/private-project",
                                           "transcript_path": "/private-project/parent.jsonl"}}, 201)
    assert custodian.record["submission_pending"] is True
    monkeypatch.setattr(source_module, "_identity", lambda pid: {
        "pid": pid, "start_token": "boot:ns:100"})
    with pytest.raises(SourceCustodyError, match="predates submitted input"):
        custodian._prompt_begin({"event": {"hook_event_name": "UserPromptSubmit",
                                           "session_id": parent,
                                           "cwd": "/private-project",
                                           "transcript_path": "/private-project/parent.jsonl"}}, 201)
    monkeypatch.setattr(source_module, "_identity", lambda pid: {
        "pid": pid, "start_token": "boot:ns:101"})
    begun = custodian._prompt_begin({"event": {"hook_event_name": "UserPromptSubmit",
                                               "session_id": parent,
                                               "cwd": "/private-project",
                                               "transcript_path": "/private-project/parent.jsonl",
                                               "prompt": "h"}}, 201)
    assert begun["turn_sequence"] == 1
    assert custodian.record["turn_busy"] is True
    assert custodian.record["submission_pending"] is False
    with pytest.raises(SourceCustodyError, match="not admitted"):
        custodian._prompt_begin({"event": {"hook_event_name": "UserPromptSubmit",
                                           "session_id": parent,
                                           "cwd": "/private-project",
                                           "transcript_path": "/private-project/parent.jsonl"}}, 201)
    ticket = custodian._stop_begin(201)
    custodian._stop_event({"ticket": ticket["ticket"],
                           "turn_sequence": ticket["turn_sequence"],
                           "event": {"hook_event_name": "Stop", "session_id": parent,
                                     "background_tasks": [], "session_crons": [],
                                     "stop_hook_active": False}}, 201)
    assert custodian.prompt_ready is True
    assert custodian.record["turn_busy"] is False


def test_blank_enter_local_and_history_repaint_cannot_clear_taint(monkeypatch):
    custodian, _, writes = _input_custodian(monkeypatch)
    assert _input(custodian, b"\r") == {"written": 1}
    assert writes == []
    assert custodian.record["turn_sequence"] == 0
    assert custodian.prompt_ready is True
    assert custodian.input_clean is True and not custodian.input_line
    _input(custodian, b"\x1b[A")
    assert custodian.input_clean is False
    _emit(monkeypatch, custodian, b"ClaudeCodev2.1.283\r\n\xe2\x9d\xaf ")
    assert custodian.input_clean is False
    _input(custodian, b"\r")
    assert writes == [b"\x1b[A", b"\r"]
    assert custodian.record["submission_pending"] is True


def test_exact_trust_dialog_one_shot_precedes_target_activation(monkeypatch):
    custodian, parent, writes = _input_custodian(monkeypatch, started=False, target=True)
    dialog = (b"Accessing workspace:\r\n/private-project\r\n"
              b"Quick safety check: Is this a project you created or one you trust?\r\n"
              b"Claude Code'll be able to read files.\r\n"
              b"\xe2\x9d\xaf No, exit\r\nYes, I trust this folder\r\n")
    _emit(monkeypatch, custodian, dialog.replace(b"/private-project", b"/other-project"))
    assert custodian.record["startup_trust_state"] == "awaiting"
    with pytest.raises(SourceCustodyError, match="exact first trust"):
        _input(custodian, b"\r")
    _emit(monkeypatch, custodian, dialog)
    assert custodian.record["startup_trust_state"] == "offered"
    with pytest.raises(SourceCustodyError, match="exact first trust"):
        _input(custodian, b"\r")
    for byte in (b"\x1b", b"[", b"B"):
        _input(custodian, byte)
    assert writes == [b"\x1b[B"]
    assert custodian.record["startup_trust_state"] == "navigation-pending"
    _emit(monkeypatch, custodian, b"No, exit\r\n\xe2\x9d\xaf Yes, I trust this folder")
    assert custodian.record["startup_trust_state"] == "confirm-selected"
    _input(custodian, b"\r")
    assert custodian.record["startup_trust_state"] == "submitted"
    with pytest.raises(SourceCustodyError, match="exact first trust"):
        _input(custodian, b"\r")
    custodian._session_start({"event": {"hook_event_name": "SessionStart",
                                          "session_id": parent, "source": "resume",
                                          "cwd": "/private-project",
                                          "transcript_path": "/private-project/parent.jsonl"}}, 201)
    assert custodian.record["startup_trust_state"] == "complete"
    with pytest.raises(SourceCustodyError, match="fenced"):
        _input(custodian, b"model prompt\r")
    custodian._activate_input({"parent_uuid": parent, "runtime_id": "runtime-1",
                               "launch_intent_id": "target-launch-one",
                               "manifest_digest": "a" * 64})
    assert custodian.record["model_input_admitted"] is True


def test_latest_trust_selection_revokes_historical_yes(monkeypatch):
    custodian, _, writes = _input_custodian(monkeypatch, started=False, target=True)
    custodian.record["startup_trust_state"] = "navigation-pending"
    _emit(monkeypatch, custodian,
          "❯ Yes, I trust this folder\r\n❯ No, exit".encode())
    assert custodian.record["startup_trust_state"] == "selection-lost"
    with pytest.raises(SourceCustodyError, match="exact first trust"):
        _input(custodian, b"\r")
    assert writes == []


def test_split_trust_selector_withholds_enter_and_checks_queued_redraw(monkeypatch):
    custodian, _, writes = _input_custodian(monkeypatch, started=False, target=True)
    custodian.record["startup_trust_state"] = "navigation-pending"
    _emit(monkeypatch, custodian, b"\xe2\x9d")
    assert custodian.record["startup_trust_state"] == "navigation-pending"
    _emit(monkeypatch, custodian, b"\xaf Yes, I trust this folder")
    assert custodian.record["startup_trust_state"] == "confirm-selected"
    _emit(monkeypatch, custodian, b"\xe2\x9d\xaf N")
    assert custodian.record["startup_trust_state"] == "navigation-pending"
    with pytest.raises(SourceCustodyError, match="exact first trust"):
        _input(custodian, b"\r")
    _emit(monkeypatch, custodian, b"o, exit")
    assert custodian.record["startup_trust_state"] == "selection-lost"
    assert writes == []

    second, _, second_writes = _input_custodian(monkeypatch, started=False, target=True)
    second.record["startup_trust_state"] = "confirm-selected"
    second.trust_navigation_tail = "❯ Yes, I trust this folder".encode()
    chunks = iter(("❯ No, exit".encode(),))
    def read(_fd, _size):
        try:
            return next(chunks)
        except StopIteration:
            raise BlockingIOError
    monkeypatch.setattr(source_module.os, "read", read)
    with pytest.raises(SourceCustodyError, match="selection changed"):
        _input(second, b"\r")
    assert second.record["startup_trust_state"] == "selection-lost"
    assert second_writes == []


@pytest.mark.parametrize("payload", [
    b"{",
    b"[]",
    b'{"hook_event_name":"UserPromptSubmit"}',
    b"x" * (128 * 1024 + 1),
], ids=["truncated-json", "array", "unbound-prompt", "oversized"])
def test_invalid_prompt_hook_blocks_with_fixed_bounded_stderr(tmp_path, payload):
    observer = pathlib.Path(source_module.__file__).with_name("lane-managed-cli")
    completed = subprocess.run([sys.executable, str(observer), "hook-observe",
                                str(tmp_path / "missing-custodian")],
                               input=payload, capture_output=True, timeout=5)
    assert completed.returncode == 2
    assert completed.stdout == b""
    assert completed.stderr == b"Managed lane prompt was not admitted.\n"
