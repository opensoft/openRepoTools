# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the secure managed-lane state primitives.

The implementation is intentionally not present in the first test-first
slice.  These tests therefore import :mod:`lane_managed_state` directly and
are expected to be red until T004 supplies the module.  The public surface
used here is deliberately small and is shared with the implementation task:

* ``canonical_lane`` validates a lane name and preserves its canonical
  spelling;
* ``resolve_workspace`` delegates to ``lanes-edit.sh workspace-root`` and
  distinguishes its exit-8 absence result from an exit-1/unknown failure;
* ``WorkspaceIdentity`` carries the Git common directory and state roots;
* ``ManagedStateStore`` owns private atomic JSON/journal files and an fcntl
  lock; and
* the same store owns the host/workspace-global writer exclusion.

Only temporary local files and the Python standard library are used.  No lane
helper is hand-rolled here: subprocess fixtures that emulate its exit status
are only used to prove that the state module preserves the helper boundary.
"""

from __future__ import annotations

import multiprocessing
import json
import os
import queue
import stat
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

import pytest

from lane_managed_state import (
    ManagedStateError,
    ManagedStateStore,
    WorkspaceIdentity,
    canonical_lane,
    resolve_workspace,
)


def _helper(tmp_path: Path, *, output: str = "", returncode: int = 0) -> Path:
    """Create a tiny executable standing in for ``lanes-edit.sh``.

    The helper is a test seam, not a replacement workspace resolver: the
    module still has to invoke it and preserve its status distinction.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    script = tmp_path / "lanes-edit.sh"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if len(sys.argv) < 2 or sys.argv[1] != 'workspace-root':\n"
        "    sys.exit(64)\n"
        f"sys.stdout.write({output!r})\n"
        f"sys.exit({returncode})\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _identity(workspace, *, lane: Optional[str] = None,
              host: str = "eagle"):
    """Resolve the fixture workspace through the pinned state API."""
    helper = _helper(
        workspace.workspace_repo.parent / "workspace-helper",
        output=f"{workspace.workspace_repo.resolve()}\n",
    )
    env = dict(workspace.env)
    env["LANES_WORKSTATION"] = host
    return resolve_workspace(lane or workspace.lane, env=env, helper=helper)


def _store(workspace, *, lane: str | None = None, host: str = "eagle"):
    return ManagedStateStore(_identity(workspace, lane=lane, host=host))


def _ensure_layout(store):
    """Create a first private record only through the state API."""
    store.write_json("owner.json", {})
    return store


def _race_child(workspace: str, lane: str, host: str, action: str,
                barrier, result):
    """Run one ownership contender in a separate process.

    ``fcntl`` locks are process-scoped on POSIX, so this must not be replaced
    with two threads: a thread-only test would pass with an in-process mutex
    while allowing two real lane processes to race.
    """
    helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
    identity = resolve_workspace(
        lane,
        env={"LANES_WORKSTATION": host},
        helper=helper,
    )
    owner = ManagedStateStore(identity)
    barrier.wait()
    try:
        if action == "managed":
            record = owner.enroll_managed(daemon_id="daemon-race")
        else:
            record = owner.begin_legacy(
                pid=os.getpid(), start_token="race-token", pgid=os.getpid()
            )
        result.put(("ok", action, record.get("mode") if isinstance(record, dict)
                    else getattr(record, "mode", None)))
    except ManagedStateError as exc:
        result.put(("error", action, exc.code, exc.returncode))
    except Exception as exc:  # pragma: no cover - turns a child bug readable
        result.put(("crash", action, type(exc).__name__, str(exc)))


def test_canonical_lane_validation_accepts_literal_swap_and_rejects_paths():
    assert canonical_lane("swap") == "swap"
    assert canonical_lane("build_01") == "build_01"
    assert canonical_lane("Build-01") == "Build-01"

    for value in ("", ".", "..", ".hidden", "-leading", "a/b", "a b",
                  "a\tb", "a\nb", None, 7):
        with pytest.raises(ManagedStateError) as raised:
            canonical_lane(value)
        assert raised.value.code == "invalid"


def test_workspace_helper_preserves_success_and_exit_8_absence(
        tmp_path: Path, managed_workspace):
    expected = managed_workspace.workspace_repo.resolve()
    helper = _helper(tmp_path / "success", output=f"{expected}\n")
    identity = resolve_workspace(managed_workspace.lane,
                                 env=managed_workspace.env, helper=helper)
    assert isinstance(identity, WorkspaceIdentity)
    assert identity.workspace_root == expected

    absent = _helper(tmp_path / "absent", returncode=8)
    with pytest.raises(ManagedStateError) as raised:
        resolve_workspace(managed_workspace.lane,
                          env=managed_workspace.env, helper=absent)
    assert raised.value.returncode == 8
    assert raised.value.code == "absent"


def test_workspace_helper_treats_exit_1_and_unknown_status_as_read_failure(
        tmp_path: Path, managed_workspace):
    failed = _helper(tmp_path / "failed", output="unknown\n", returncode=1)
    with pytest.raises(ManagedStateError) as raised:
        resolve_workspace(managed_workspace.lane,
                          env=managed_workspace.env, helper=failed)
    assert raised.value.returncode == 1
    assert raised.value.code == "unknown"

    unexpected = _helper(tmp_path / "unexpected", returncode=23)
    with pytest.raises(ManagedStateError) as raised:
        resolve_workspace(managed_workspace.lane,
                          env=managed_workspace.env, helper=unexpected)
    assert raised.value.returncode == 23
    assert raised.value.code == "unknown"


def test_state_paths_are_under_workspace_git_common_dir(managed_workspace):
    identity = _identity(managed_workspace, lane="build")
    assert identity.common_dir == managed_workspace.common_dir.resolve()
    assert identity.state_root == (
        managed_workspace.common_dir / "openrepotools-managed" / "eagle" /
        "build"
    )
    assert identity.state_root.is_relative_to(identity.common_dir)
    assert identity.global_root == (
        managed_workspace.common_dir / "openrepotools-managed" / "eagle"
    )
    assert identity.lane == "build"
    assert identity.host == "eagle"


def test_lane_display_case_collapses_to_one_state_owner_key(managed_workspace):
    upper = _identity(managed_workspace, lane="Build")
    lower = _identity(managed_workspace, lane="build")
    assert canonical_lane("Build") == "Build"
    assert upper.lane == "Build"
    assert upper.lane_key == lower.lane_key == "build"
    assert upper.state_root == lower.state_root
    assert upper.global_root == lower.global_root

    ManagedStateStore(upper).enroll_managed(daemon_id="daemon-upper")
    with pytest.raises(ManagedStateError) as raised:
        ManagedStateStore(lower).enroll_managed(daemon_id="daemon-lower")
    assert raised.value.code in {"busy", "ownership-conflict"}


@pytest.mark.parametrize("bad_lane", ["../escape", "lane/child", "/tmp/x"])
def test_state_paths_reject_lane_traversal(managed_workspace, bad_lane):
    with pytest.raises(ManagedStateError) as raised:
        _identity(managed_workspace, lane=bad_lane)
    assert raised.value.code == "invalid"


def test_private_state_layout_rejects_unsafe_modes(managed_workspace):
    store = _ensure_layout(_store(managed_workspace))
    store.identity.state_root.chmod(0o755)
    with pytest.raises(ManagedStateError) as raised:
        store.read_json("owner.json")
    assert raised.value.code == "unsafe-state"

    store.identity.state_root.chmod(0o700)
    owner = store.identity.state_root / "owner.json"
    owner.write_text("{}\n", encoding="utf-8")
    owner.chmod(0o644)
    with pytest.raises(ManagedStateError) as raised:
        store.read_json("owner.json")
    assert raised.value.code == "unsafe-state"


def test_private_state_layout_rejects_foreign_owner(managed_workspace,
                                                    monkeypatch):
    store = _ensure_layout(_store(managed_workspace))
    current_uid = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: current_uid + 1)
    with pytest.raises(ManagedStateError) as raised:
        store.read_json("owner.json")
    assert raised.value.code == "unsafe-state"


def test_private_state_layout_rejects_symlink_components(managed_workspace):
    identity = _identity(managed_workspace)
    managed = identity.global_root
    outside = managed_workspace.workspace_repo.parent / "outside-state"
    outside.mkdir(mode=0o700)
    managed.parent.mkdir(mode=0o700, exist_ok=True)
    managed.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ManagedStateError) as raised:
        ManagedStateStore(_identity(managed_workspace))
    assert raised.value.code == "unsafe-state"


def test_private_state_layout_rejects_symlinked_record(managed_workspace):
    store = _ensure_layout(_store(managed_workspace))
    outside = managed_workspace.workspace_repo.parent / "outside-owner.json"
    outside.write_text("{}\n", encoding="utf-8")
    owner = store.identity.state_root / "owner.json"
    owner.unlink()
    owner.symlink_to(outside)
    with pytest.raises(ManagedStateError) as raised:
        store.read_json("owner.json")
    assert raised.value.code == "unsafe-state"


def _lock_holder(workspace: str, lane: str, host: str, ready, release):
    helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
    identity = resolve_workspace(
        lane,
        env={"LANES_WORKSTATION": host},
        helper=helper,
    )
    store = ManagedStateStore(identity)
    with store.locked():
        ready.put(True)
        release.get()


def _lock_contender(workspace: str, lane: str, host: str, acquired):
    helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
    identity = resolve_workspace(
        lane,
        env={"LANES_WORKSTATION": host},
        helper=helper,
    )
    store = ManagedStateStore(identity)
    with store.locked(shared=True):
        acquired.put(True)


def _forked_exclusive_lock_contender(workspace: str, lane: str, host: str,
                                     started, acquired, errors):
    """Attempt the exclusive lock after a fork, reporting boundedly."""
    try:
        helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
        identity = resolve_workspace(
            lane,
            env={"LANES_WORKSTATION": host},
            helper=helper,
        )
        store = ManagedStateStore(identity)
        started.set()
        with store.locked():
            acquired.set()
    except BaseException as exc:  # pragma: no cover - child diagnostics
        errors.put((type(exc).__name__, str(exc)))


def _enroll_owner_child(workspace: str, lane: str, host: str, daemon: str,
                        barrier, result):
    """Race two first writers through the true create-only owner path."""
    try:
        helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
        identity = resolve_workspace(
            lane,
            env={"LANES_WORKSTATION": host},
            helper=helper,
        )
        store = ManagedStateStore(identity)
        barrier.wait(timeout=3)
        record = store.enroll_managed(daemon_id=daemon)
        result.put(("ok", daemon, _record_field(record, "mode")))
    except ManagedStateError as exc:
        result.put(("error", daemon, exc.code, exc.returncode))
    except BaseException as exc:  # pragma: no cover - child diagnostics
        result.put(("crash", daemon, type(exc).__name__, str(exc)))


def _begin_pending_owner_child(workspace: str, lane: str, host: str,
                               request_id: str, result):
    """Create a pending lease in a short-lived creator process."""
    try:
        helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
        identity = resolve_workspace(
            lane,
            env={"LANES_WORKSTATION": host},
            helper=helper,
        )
        store = ManagedStateStore(identity)
        start_token = _current_process_start_token(os.getpid())
        if start_token is None:
            result.put(("skip", "portable child process start token unavailable"))
            return
        record = store.begin_pending_launch(
            request_id=request_id,
            pid=os.getpid(),
            start_token=start_token,
        )
        result.put(("ok", record, start_token))
    except ManagedStateError as exc:
        result.put(("error", exc.code, exc.returncode))
    except BaseException as exc:  # pragma: no cover - child diagnostics
        result.put(("crash", type(exc).__name__, str(exc)))


def _pending_or_managed_child(workspace: str, lane: str, host: str,
                              action: str, barrier, result):
    """Race pending-launch creation against managed enrollment."""
    try:
        helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
        identity = resolve_workspace(
            lane,
            env={"LANES_WORKSTATION": host},
            helper=helper,
        )
        store = ManagedStateStore(identity)
        barrier.wait(timeout=3)
        if action == "pending":
            start_token = _current_process_start_token(os.getpid())
            if start_token is None:
                result.put(("skip", action,
                            "portable child process start token unavailable"))
                return
            record = store.begin_pending_launch(
                request_id="race-request",
                pid=os.getpid(),
                start_token=start_token,
            )
        else:
            record = store.enroll_managed(daemon_id="race-daemon")
        result.put(("ok", action, record))
    except ManagedStateError as exc:
        result.put(("error", action, exc.code, exc.returncode))
    except BaseException as exc:  # pragma: no cover - child diagnostics
        result.put(("crash", action, type(exc).__name__, str(exc)))


def _read_owner_child(workspace: str, lane: str, host: str, result):
    """Read one record in a child so a buggy FIFO open cannot hang pytest."""
    try:
        helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
        identity = resolve_workspace(
            lane,
            env={"LANES_WORKSTATION": host},
            helper=helper,
        )
        record = ManagedStateStore(identity).read_json("owner.json")
        result.put(("ok", record))
    except ManagedStateError as exc:
        result.put(("error", exc.code, exc.returncode))
    except BaseException as exc:  # pragma: no cover - child diagnostics
        result.put(("crash", type(exc).__name__, str(exc)))


def _durable_state_bytes(store):
    """Snapshot durable state while ignoring the advisory lock inode."""
    root = store.identity.global_root
    if not root.exists():
        return {}
    snapshot = {}
    for path in sorted(root.rglob("*")):
        if (path.name == "state.lock" or path.is_symlink() or
                not path.is_file()):
            continue
        snapshot[str(path.relative_to(root))] = path.read_bytes()
    return snapshot


def _recovery_proof(runtime, **overrides):
    """Build the complete trusted exclusion proof for one old runtime."""
    proof = {
        "pid": runtime["pid"],
        "start_token": runtime["start_token"],
        "pgid": runtime["pgid"],
        "process_group_owned": True,
        "exited": True,
        "group_excluded": True,
        "process_domain": runtime.get("process_domain", "local"),
    }
    proof.update(overrides)
    return proof


def _recovery_arguments(owner, runtime, socket_path, *, daemon_id="daemon-new",
                        pid=46101, start_token="new-daemon-start",
                        pgid=46102, request_id="recovery-request", proof=None):
    """Return the scalar CAS contract used by ``recover_managed_owner``."""
    return {
        "old_daemon_id": owner["daemon_id"],
        "old_generation": owner["generation"],
        "old_pid": runtime["pid"],
        "old_start_token": runtime["start_token"],
        "old_pgid": runtime["pgid"],
        "new_daemon_id": daemon_id,
        "new_pid": pid,
        "new_start_token": start_token,
        "new_pgid": pgid,
        "process_domain": "local",
        "socket_path": str(socket_path),
        "request_id": request_id,
        "exclusion_proof": (_recovery_proof(runtime) if proof is None else proof),
    }


def _seed_managed_recovery(store, managed_workspace, tmp_path, socket_path):
    """Enroll one owner, endpoint, and native lineage claim for recovery tests."""
    lineage_id = "lineage-recovery"
    coordinator_session_uuid = "coordinator-recovery"
    owner = store.enroll_managed(
        daemon_id="daemon-old", process_domain="local",
        lineage_id=lineage_id,
        coordinator_session_uuid=coordinator_session_uuid,
    )
    runtime = store.register_runtime(
        daemon_id=owner["daemon_id"], generation=owner["generation"],
        pid=46001, start_token="old-daemon-start", pgid=46002,
        process_domain="local", socket_path=socket_path,
    )
    worktree = (tmp_path / "recovery-coordinator").resolve()
    worktree.mkdir()
    claim = store.claim_lineage_workspace(
        lineage_id=lineage_id,
        owner_generation=owner["generation"],
        lineage_generation=1,
        workspace=str(worktree),
        common_dir=str(store.identity.common_dir.resolve()),
        repository=str(managed_workspace.project.resolve()),
        coordinator_session_uuid=coordinator_session_uuid,
    )
    return owner, runtime, worktree, claim


def _recover_managed_child(workspace: str, lane: str, host: str,
                           arguments, barrier, result):
    """Race two exact recovery contenders through the owner CAS."""
    try:
        helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
        identity = resolve_workspace(
            lane, env={"LANES_WORKSTATION": host}, helper=helper,
        )
        store = ManagedStateStore(identity)
        barrier.wait(timeout=3)
        record = store.recover_managed_owner(**arguments)
        result.put(("ok", arguments["new_daemon_id"], record))
    except ManagedStateError as exc:
        result.put(("error", arguments["new_daemon_id"], exc.code,
                    exc.returncode))
    except BaseException as exc:  # pragma: no cover - child diagnostics
        result.put(("crash", arguments["new_daemon_id"],
                    type(exc).__name__, str(exc)))


def _crash_recovery_after_owner_write(workspace: str, lane: str, host: str,
                                      arguments, result):
    """Hard-stop recovery after ownerNEW, before runtimeNEW is published."""
    try:
        helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
        identity = resolve_workspace(
            lane, env={"LANES_WORKSTATION": host}, helper=helper,
        )
        store = ManagedStateStore(identity)

        def crash_before_runtime(_record):
            os._exit(77)

        store._write_runtime = crash_before_runtime
        store.recover_managed_owner(**arguments)
        result.put(("unexpected-return",))
    except ManagedStateError as exc:
        result.put(("error", exc.code, exc.returncode))
    except BaseException as exc:  # pragma: no cover - child diagnostics
        result.put(("crash", type(exc).__name__, str(exc)))


def _claim_payload(store):
    """Return the global claims path and decoded payload after one claim."""
    path = store.identity.global_root / "claims.json"
    assert path.is_file(), f"global claims record is missing: {path}"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _first_claim(payload):
    """Locate the first claim in the supported mapping/list wire shape."""
    claims = payload.get("claims") if isinstance(payload, dict) else payload
    if isinstance(claims, dict):
        key = next(iter(claims))
        return claims[key]
    if isinstance(claims, list):
        return claims[0]
    raise AssertionError(f"unexpected claims record shape: {payload!r}")


def test_fcntl_lock_serializes_processes_and_supports_shared_readers(
        managed_workspace):
    store = _ensure_layout(_store(managed_workspace))
    ctx = multiprocessing.get_context("fork")
    ready, release, acquired = ctx.Queue(), ctx.Queue(), ctx.Queue()
    args = (str(managed_workspace.workspace_repo), managed_workspace.lane,
            "eagle")
    holder = ctx.Process(target=_lock_holder, args=args + (ready, release))
    contender = ctx.Process(target=_lock_contender, args=args + (acquired,))
    holder.start()
    contender_started = False
    try:
        assert ready.get(timeout=5) is True
        contender.start()
        contender_started = True
        time.sleep(0.2)
        with pytest.raises(Exception):
            acquired.get_nowait()
        release.put(True)
        assert acquired.get(timeout=5) is True
    finally:
        if holder.is_alive():
            release.put(True)
        holder.join(timeout=5)
        if contender_started:
            contender.join(timeout=5)
        if holder.is_alive():
            holder.terminate()
            holder.join(timeout=5)
        if contender_started and contender.is_alive():
            contender.terminate()
            contender.join(timeout=5)
    assert holder.exitcode == 0
    assert contender.exitcode == 0


def _json_writer(workspace: str, lane: str, host: str, writer: str,
                 iterations: int, finished):
    helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
    identity = resolve_workspace(lane, env={"LANES_WORKSTATION": host},
                                 helper=helper)
    store = ManagedStateStore(identity)
    for iteration in range(iterations):
        store.write_json(
            "record.json",
            {"writer": writer, "iteration": iteration,
             "payload": [writer, iteration]},
        )
    finished.put(True)


def _journal_writer(workspace: str, lane: str, host: str, writer: str,
                    iterations: int, finished):
    helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
    identity = resolve_workspace(lane, env={"LANES_WORKSTATION": host},
                                 helper=helper)
    store = ManagedStateStore(identity)
    for iteration in range(iterations):
        store.append_journal(
            "events.jsonl",
            {"writer": writer, "iteration": iteration},
        )
    finished.put(True)


def test_json_replace_is_atomic_and_leaves_no_partial_temp_files(
        managed_workspace):
    store = _store(managed_workspace)
    store.write_json(
        "record.json", {"writer": "seed", "iteration": -1, "payload": ""}
    )
    ctx = multiprocessing.get_context("fork")
    finished = ctx.Queue()
    writer = ctx.Process(
        target=_json_writer,
        args=(str(managed_workspace.workspace_repo), managed_workspace.lane,
              "eagle", "child", 80, finished),
    )
    writer.start()
    try:
        observed = [store.read_json("record.json")]
        while writer.is_alive():
            document = store.read_json("record.json")
            assert isinstance(document, dict)
            assert set(document) == {"writer", "iteration", "payload"}
            assert document["writer"] in {"seed", "child"}
            observed.append(document["iteration"])
            time.sleep(0.001)
        assert finished.get(timeout=5) is True
        writer.join(timeout=5)
        final = store.read_json("record.json")
        assert final["writer"] == "child"
        assert final["iteration"] == 79
        assert observed
        assert not list(store.identity.state_root.glob("record.json.*"))
    finally:
        if writer.is_alive():
            writer.terminate()
            writer.join(timeout=5)


def test_journal_appends_are_complete_json_lines_across_processes(
        managed_workspace):
    store = _store(managed_workspace)
    ctx = multiprocessing.get_context("fork")
    finished = ctx.Queue()
    writers = [
        ctx.Process(
            target=_journal_writer,
            args=(str(managed_workspace.workspace_repo),
                  managed_workspace.lane, "eagle", writer, 40, finished),
        )
        for writer in ("one", "two")
    ]
    for writer in writers:
        writer.start()
    try:
        assert [finished.get(timeout=5) for _ in writers] == [True, True]
        for writer in writers:
            writer.join(timeout=5)
        journal = store.identity.state_root / "events.jsonl"
        lines = journal.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 80
        events = [json.loads(line) for line in lines]
        assert {event["writer"] for event in events} == {"one", "two"}
        assert all(set(event) == {"writer", "iteration"} for event in events)
        assert journal.stat().st_mode & 0o777 == 0o600
    finally:
        for writer in writers:
            if writer.is_alive():
                writer.terminate()
                writer.join(timeout=5)


def _record_field(record, field):
    if isinstance(record, dict):
        return record[field]
    return getattr(record, field)


def _runtime_path(store):
    """Return the private durable runtime-discovery record path."""
    return store.identity.state_root / "runtime.json"


def _current_process_start_token(pid: int) -> Optional[str]:
    """Read a portable process-incarnation token for a live child."""
    try:
        raw = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
        suffix = raw.rsplit(")", 1)[-1].split()
        if len(suffix) > 19 and suffix[19].isdigit():
            return suffix[19]
    except (OSError, UnicodeError, ValueError):
        pass
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            check=False,
            timeout=1.0,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[0] if len(lines) == 1 else None


@pytest.fixture
def runtime_socket_path():
    """Provide a unique owner-private endpoint below the Unix socket limit."""
    with tempfile.TemporaryDirectory(prefix="lm-runtime-") as root:
        runtime_dir = Path(root).resolve()
        runtime_dir.chmod(0o700)
        socket_path = runtime_dir / "managed.sock"
        assert stat.S_IMODE(runtime_dir.stat().st_mode) == 0o700
        assert not runtime_dir.is_symlink()
        assert str(socket_path) == str(socket_path.resolve())
        assert len(os.fsencode(str(socket_path))) < 104
        assert not socket_path.exists()
        assert not socket_path.is_symlink()
        yield socket_path


def test_managed_owner_is_durable_and_blocks_legacy_after_daemon_loss(
        managed_workspace):
    store = _store(managed_workspace)
    record = store.enroll_managed(daemon_id="daemon-a")
    assert _record_field(record, "mode") == "managed"
    durable = store.read_json("owner.json")
    assert durable["mode"] == "managed"
    assert durable["daemon_id"] == "daemon-a"
    assert "pid" not in durable
    assert "start_token" not in durable

    # Closing the enrolling object stands in for a daemon that has stopped.
    # The durable marker, not process liveness, remains the authority.
    replacement = _store(managed_workspace)
    with pytest.raises(ManagedStateError) as raised:
        replacement.begin_legacy(pid=999999, start_token="new-legacy", pgid=999998)
    assert raised.value.code in {"busy", "ownership-conflict"}
    assert replacement.read_json("owner.json") == durable


def test_legacy_owner_is_pid_start_token_bound_and_managed_enrollment_refuses(
        managed_workspace):
    store = _store(managed_workspace)
    record = store.begin_legacy(
        pid=os.getpid(), start_token="token-a", pgid=os.getpid()
    )
    assert _record_field(record, "mode") == "legacy-lease"
    durable = store.read_json("owner.json")
    assert durable["mode"] == "legacy-lease"
    assert durable["pid"] == os.getpid()
    assert durable["start_token"] == "token-a"
    assert durable["pgid"] == os.getpid()

    with pytest.raises(ManagedStateError) as raised:
        store.enroll_managed(daemon_id="daemon-a")
    assert raised.value.code in {"busy", "ownership-conflict"}
    assert store.read_json("owner.json") == durable


def test_legacy_owner_records_pgid_and_exact_release_clears_it(
        managed_workspace):
    """Legacy ownership binds a process group and releases only as one act."""
    store = _store(managed_workspace)
    record = store.begin_legacy(
        pid=51001, start_token="legacy-release-token", pgid=51002
    )

    assert _record_field(record, "mode") == "legacy-lease"
    assert _record_field(record, "pid") == 51001
    assert _record_field(record, "start_token") == "legacy-release-token"
    assert _record_field(record, "pgid") == 51002
    durable = store.read_json("owner.json")
    assert durable["pgid"] == 51002

    released = store.release_legacy(
        pid=51001, start_token="legacy-release-token", pgid=51002
    )
    assert released == {} or _record_field(released, "mode") in {"", "released"}
    assert store.read_json("owner.json") == {}


@pytest.mark.parametrize(
    "field,bad_value",
    [("pid", 51011), ("start_token", "wrong-release-token"),
     ("pgid", 51012)],
)
def test_legacy_release_requires_exact_pid_token_and_pgid_without_mutation(
        managed_workspace, field, bad_value):
    """A mismatched legacy release cannot clear another holder's lease."""
    store = _store(managed_workspace)
    store.begin_legacy(pid=51010, start_token="exact-release-token", pgid=51009)
    owner_path = store.identity.state_root / "owner.json"
    before = owner_path.read_bytes()
    arguments = {
        "pid": 51010,
        "start_token": "exact-release-token",
        "pgid": 51009,
    }
    arguments[field] = bad_value

    with pytest.raises(ManagedStateError) as raised:
        store.release_legacy(**arguments)
    assert raised.value.code in {"busy", "invalid", "ownership-conflict",
                                 "stale-generation", "unknown"}
    assert owner_path.read_bytes() == before
    assert store.read_json("owner.json")["mode"] == "legacy-lease"


def test_pending_launch_cannot_be_released_as_legacy(
        managed_workspace):
    """Pending ownership has its own exact bind/abort lifecycle."""
    store = _store(managed_workspace)
    pending = store.begin_pending_launch(
        request_id="pending-not-legacy-release",
        pid=51020,
        start_token="pending-token",
    )
    owner_path = store.identity.state_root / "owner.json"
    before = owner_path.read_bytes()

    with pytest.raises(ManagedStateError) as raised:
        store.release_legacy(pid=51020, start_token="pending-token", pgid=51021)
    assert raised.value.code in {"busy", "invalid", "ownership-conflict",
                                 "stale-generation", "unknown"}
    assert owner_path.read_bytes() == before
    assert store.read_json("owner.json")["lease_id"] == pending["lease_id"]


def test_legacy_release_and_new_begin_are_atomic_under_outer_lock(
        managed_workspace):
    """A caller can rotate a legacy lease without an unlocked gap."""
    store = _store(managed_workspace)
    store.begin_legacy(pid=51030, start_token="old-token", pgid=51031)

    with store.locked():
        store.release_legacy(pid=51030, start_token="old-token", pgid=51031)
        replacement = store.begin_legacy(
            pid=51032, start_token="new-token", pgid=51033
        )

    assert replacement["mode"] == "legacy-lease"
    assert replacement["pid"] == 51032
    assert replacement["start_token"] == "new-token"
    assert replacement["pgid"] == 51033
    assert store.read_json("owner.json") == replacement


@pytest.mark.parametrize(
    "holder_pid,holder_kind",
    [(os.getpid(), "live"), (2147483647, "unknown")],
)
def test_live_or_unknown_legacy_holder_refuses_enrollment_without_mutation(
        managed_workspace, holder_pid, holder_kind):
    """Enrollment must not replace either live or unverified legacy ownership."""
    store = _store(managed_workspace)
    store.begin_legacy(
        pid=holder_pid, start_token="legacy-%s" % holder_kind, pgid=holder_pid
    )
    before = {
        path.name: path.read_bytes()
        for path in store.identity.state_root.iterdir()
        if path.is_file()
    }

    with pytest.raises(ManagedStateError) as raised:
        _store(managed_workspace).enroll_managed(daemon_id="must-not-enroll")

    assert raised.value.code in {"busy", "live-unverified", "ownership-conflict"}
    after = {
        path.name: path.read_bytes()
        for path in store.identity.state_root.iterdir()
        if path.is_file()
    }
    assert after == before


def test_pending_launch_survives_creator_exit_and_blocks_new_owners(
        managed_workspace):
    """A creator's exit must not expire a pending launch lease."""
    _helper(
        managed_workspace.workspace_repo.parent / "workspace-helper",
        output=f"{managed_workspace.workspace_repo.resolve()}\n",
    )
    ctx = multiprocessing.get_context("fork")
    result = ctx.Queue()
    creator = ctx.Process(
        target=_begin_pending_owner_child,
        args=(str(managed_workspace.workspace_repo), managed_workspace.lane,
              "eagle", "request-survives-exit", result),
    )
    creator.start()
    outcome = None
    try:
        outcome = result.get(timeout=3)
        creator.join(timeout=3)
    finally:
        if creator.is_alive():
            creator.terminate()
        creator.join(timeout=3)

    assert not creator.is_alive()
    assert creator.exitcode == 0
    if outcome is not None and outcome[0] == "skip":
        pytest.skip(outcome[1])
    assert outcome is not None and outcome[0] == "ok", outcome
    pending = outcome[1]
    creator_start_token = outcome[2]
    assert _record_field(pending, "mode") == "pending-launch"
    assert _record_field(pending, "request_id") == "request-survives-exit"
    assert _record_field(pending, "start_token") == creator_start_token
    assert _record_field(pending, "lease_id")

    store = _store(managed_workspace)
    owner_path = store.identity.state_root / "owner.json"
    durable = store.read_json("owner.json")
    before = owner_path.read_bytes()
    assert durable["mode"] == "pending-launch"
    assert durable["pid"] == pending["pid"]
    assert durable["start_token"] == creator_start_token

    with pytest.raises(ManagedStateError) as managed_error:
        store.enroll_managed(daemon_id="must-not-enroll")
    assert managed_error.value.code in {"busy", "ownership-conflict"}
    with pytest.raises(ManagedStateError) as legacy_error:
        store.begin_legacy(
            pid=os.getpid(), start_token="must-not-begin", pgid=os.getpid()
        )
    assert legacy_error.value.code in {"busy", "ownership-conflict"}
    assert owner_path.read_bytes() == before


def test_pending_launch_same_request_and_holder_is_idempotent_but_conflicts_on_change(
        managed_workspace):
    """Pending creation retries are safe, while request/holder changes refuse."""
    store = _store(managed_workspace)
    first = store.begin_pending_launch(
        request_id="request-idempotent",
        pid=41001,
        start_token="holder-token",
    )
    retry = store.begin_pending_launch(
        request_id="request-idempotent",
        pid=41001,
        start_token="holder-token",
    )
    assert _record_field(retry, "lease_id") == _record_field(first, "lease_id")
    assert store.read_json("owner.json")["lease_id"] == first["lease_id"]
    before = (store.identity.state_root / "owner.json").read_bytes()

    conflicting = [
        {"request_id": "request-changed", "pid": 41001,
         "start_token": "holder-token"},
        {"request_id": "request-idempotent", "pid": 41002,
         "start_token": "holder-token"},
        {"request_id": "request-idempotent", "pid": 41001,
         "start_token": "holder-token-changed"},
    ]
    for arguments in conflicting:
        with pytest.raises(ManagedStateError) as raised:
            store.begin_pending_launch(**arguments)
        assert raised.value.code in {"busy", "ownership-conflict"}
        assert (store.identity.state_root / "owner.json").read_bytes() == before


def test_wrong_pending_lease_bind_or_abort_refuses_without_mutation(
        managed_workspace):
    """A stale lease ID cannot bind or clear another pending launch."""
    store = _store(managed_workspace)
    pending = store.begin_pending_launch(
        request_id="request-wrong-lease",
        pid=42001,
        start_token="creator-token",
    )
    owner_path = store.identity.state_root / "owner.json"
    before = owner_path.read_bytes()

    with pytest.raises(ManagedStateError) as bind_error:
        store.bind_pending_launch(
            lease_id="not-the-pending-lease",
            pid=42002,
            start_token="launcher-token",
            pgid=42003,
        )
    assert bind_error.value.code in {"busy", "invalid", "ownership-conflict",
                                     "stale-generation"}
    assert owner_path.read_bytes() == before

    with pytest.raises(ManagedStateError) as abort_error:
        store.abort_pending_launch(lease_id="not-the-pending-lease")
    assert abort_error.value.code in {"busy", "invalid", "ownership-conflict",
                                      "stale-generation"}
    assert owner_path.read_bytes() == before
    assert store.read_json("owner.json")["lease_id"] == pending["lease_id"]


def test_exact_pending_bind_uses_new_launcher_holder_and_preserves_creator_journal(
        managed_workspace):
    """Binding verifies the lease, then publishes the new legacy holder."""
    store = _store(managed_workspace)
    pending = store.begin_pending_launch(
        request_id="request-bind",
        pid=43001,
        start_token="creator-token",
    )
    journal = store.identity.state_root / "ownership.jsonl"
    journal_before = journal.read_bytes()
    bound = store.bind_pending_launch(
        lease_id=pending["lease_id"],
        pid=43002,
        start_token="launcher-token",
        pgid=43003,
    )

    assert _record_field(bound, "mode") == "legacy-lease"
    assert _record_field(bound, "pid") == 43002
    assert _record_field(bound, "start_token") == "launcher-token"
    assert _record_field(bound, "pgid") == 43003
    durable = store.read_json("owner.json")
    assert durable["mode"] == "legacy-lease"
    assert durable["pid"] == 43002
    assert durable["start_token"] == "launcher-token"
    assert durable["pgid"] == 43003
    journal_after = journal.read_bytes()
    assert journal_after.startswith(journal_before)
    assert b"creator-token" in journal_after


def test_exact_pending_abort_atomically_clears_owner(
        managed_workspace):
    """Aborting the exact lease clears pending ownership without a fallback."""
    store = _store(managed_workspace)
    pending = store.begin_pending_launch(
        request_id="request-abort",
        pid=44001,
        start_token="creator-token",
    )
    result = store.abort_pending_launch(lease_id=pending["lease_id"])

    assert result == {} or _record_field(result, "mode") in {"", "unowned"}
    assert store.read_json("owner.json") == {}
    assert (store.identity.state_root / "owner.json").is_file()


def test_runtime_registration_requires_exact_managed_owner_daemon_and_generation(
        managed_workspace, runtime_socket_path):
    """Runtime discovery cannot register against absent or mismatched ownership."""
    store = _store(managed_workspace)
    socket_path = runtime_socket_path
    arguments = {
        "daemon_id": "daemon-runtime",
        "generation": 1,
        "pid": 45001,
        "start_token": "runtime-token",
        "pgid": 45002,
        "socket_path": socket_path,
    }

    with pytest.raises(ManagedStateError) as absent_error:
        store.register_runtime(**arguments)
    assert absent_error.value.code in {"busy", "invalid", "ownership-conflict",
                                       "stale-generation", "unknown"}
    assert not _runtime_path(store).exists()

    owner = store.enroll_managed(daemon_id="daemon-runtime")
    arguments["generation"] = owner["generation"]
    for field, value in (("daemon_id", "another-daemon"),
                         ("generation", owner["generation"] + 1)):
        changed = dict(arguments)
        changed[field] = value
        with pytest.raises(ManagedStateError) as raised:
            store.register_runtime(**changed)
        assert raised.value.code in {"busy", "invalid", "ownership-conflict",
                                     "stale-generation", "unknown"}
        assert not _runtime_path(store).exists()


def test_runtime_register_and_read_roundtrip_uses_canonical_private_socket_path(
        managed_workspace, runtime_socket_path):
    """A valid runtime record round-trips its bounded endpoint identity."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-roundtrip")
    socket_path = runtime_socket_path
    registered = store.register_runtime(
        daemon_id="daemon-roundtrip",
        generation=owner["generation"],
        pid=45002,
        start_token="roundtrip-token",
        pgid=45003,
        socket_path=socket_path,
    )

    assert _record_field(registered, "daemon_id") == "daemon-roundtrip"
    assert _record_field(registered, "generation") == owner["generation"]
    assert _record_field(registered, "pid") == 45002
    assert _record_field(registered, "start_token") == "roundtrip-token"
    assert _record_field(registered, "pgid") == 45003
    assert str(_record_field(registered, "socket_path")) == str(socket_path.resolve())
    runtime = store.read_runtime()
    assert runtime is not None
    assert runtime["daemon_id"] == "daemon-roundtrip"
    assert runtime["generation"] == owner["generation"]
    assert runtime["pid"] == 45002
    assert runtime["start_token"] == "roundtrip-token"
    assert runtime["pgid"] == 45003
    assert runtime["socket_path"] == str(socket_path.resolve())
    runtime_file = _runtime_path(store)
    assert runtime_file.is_file()
    assert stat.S_IMODE(runtime_file.stat().st_mode) == 0o600


def test_runtime_record_missing_pgid_fails_closed_unchanged(
        managed_workspace, runtime_socket_path):
    """An older endpoint schema without process-group identity is invalid."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-old-runtime-schema")
    store.register_runtime(
        daemon_id="daemon-old-runtime-schema",
        generation=owner["generation"],
        pid=45022,
        start_token="old-schema-token",
        pgid=45023,
        socket_path=runtime_socket_path,
    )
    runtime_file = _runtime_path(store)
    payload = json.loads(runtime_file.read_text(encoding="utf-8"))
    assert payload.pop("pgid") == 45023
    runtime_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    before = runtime_file.read_bytes()

    with pytest.raises(ManagedStateError) as raised:
        store.read_runtime()
    assert raised.value.code in {"invalid", "corrupt", "unsafe-state", "unknown",
                                 "schema-mismatch", "migration-required"}
    assert runtime_file.read_bytes() == before


def test_runtime_register_is_idempotent_but_conflicting_identity_refuses_unchanged(
        managed_workspace, runtime_socket_path):
    """A runtime endpoint is compare-and-swap state, not a last-writer cache."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-cas")
    socket_path = runtime_socket_path
    first = store.register_runtime(
        daemon_id="daemon-cas", generation=owner["generation"],
        pid=45009, start_token="cas-token",
        pgid=45013,
        socket_path=socket_path,
    )
    runtime_file = _runtime_path(store)
    before = runtime_file.read_bytes()
    retry = store.register_runtime(
        daemon_id="daemon-cas", generation=owner["generation"],
        pid=45009, start_token="cas-token",
        pgid=45013,
        socket_path=socket_path,
    )
    assert retry == first
    assert runtime_file.read_bytes() == before

    conflicting = [
        {"pid": 45010, "start_token": "cas-token",
         "pgid": 45013,
         "socket_path": socket_path},
        {"pid": 45009, "start_token": "cas-token-changed",
         "pgid": 45013,
         "socket_path": socket_path},
        {"pid": 45009, "start_token": "cas-token",
         "pgid": 45013,
         "socket_path": socket_path.with_name("cas-other.sock")},
        {"pid": 45009, "start_token": "cas-token", "pgid": 45014,
         "socket_path": socket_path},
    ]
    for changed in conflicting:
        with pytest.raises(ManagedStateError) as raised:
            store.register_runtime(
                daemon_id="daemon-cas", generation=owner["generation"],
                **changed,
            )
        assert raised.value.code in {"busy", "invalid", "ownership-conflict",
                                     "stale-generation", "unknown"}
        assert runtime_file.read_bytes() == before


@pytest.mark.parametrize(
    "owner_case",
    ["missing", "nonmanaged", "daemon-changed", "generation-changed",
     "lane-changed"],
)
def test_read_runtime_refuses_when_current_owner_is_missing_or_stale(
        managed_workspace, runtime_socket_path, owner_case):
    """A valid endpoint is usable only with the exact current managed owner."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-current")
    store.register_runtime(
        daemon_id="daemon-current", generation=owner["generation"],
        pid=45011, start_token="current-token",
        pgid=45015,
        socket_path=runtime_socket_path,
    )
    runtime_file = _runtime_path(store)
    runtime_before = runtime_file.read_bytes()
    owner_file = store.identity.state_root / "owner.json"

    if owner_case == "missing":
        owner_file.unlink()
    elif owner_case == "nonmanaged":
        # The public begin_legacy API must correctly refuse while the managed
        # owner is live.  Install a valid non-managed snapshot directly so
        # this read-side stale-owner case does not ask that API to violate its
        # ownership contract.
        changed_owner = {
            "mode": "legacy-lease",
            "pid": 45012,
            "start_token": "legacy-owner",
            "pgid": 45013,
            "lane": owner["lane"],
            "lane_key": owner["lane_key"],
            "host": owner["host"],
            "created_at": time.time(),
        }
        owner_file.write_text(json.dumps(changed_owner) + "\n",
                              encoding="utf-8")
        owner_file.chmod(0o600)
        assert stat.S_IMODE(owner_file.stat().st_mode) == 0o600
    else:
        changed_owner = json.loads(owner_file.read_text(encoding="utf-8"))
        if owner_case == "daemon-changed":
            changed_owner["daemon_id"] = "daemon-other"
        elif owner_case == "generation-changed":
            changed_owner["generation"] = owner["generation"] + 1
        else:
            changed_owner["lane"] = "other-lane"
        owner_file.write_text(json.dumps(changed_owner) + "\n",
                              encoding="utf-8")

    with pytest.raises(ManagedStateError) as raised:
        store.read_runtime()
    assert raised.value.code in {"invalid", "busy", "ownership-conflict",
                                 "stale-generation", "unknown"}
    assert runtime_file.read_bytes() == runtime_before


@pytest.mark.parametrize(
    "socket_path_kind",
    ["relative", "dot-component", "symlink-alias", "overlong"],
)
def test_runtime_registration_rejects_noncanonical_or_nonprivate_socket_path(
        managed_workspace, runtime_socket_path, socket_path_kind):
    """Endpoint paths must be absolute, canonical, and below private state."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-path")
    if socket_path_kind == "relative":
        socket_path = Path("runtime.sock")
    elif socket_path_kind == "dot-component":
        socket_path = (runtime_socket_path.parent / "nested" / ".." /
                       runtime_socket_path.name)
    elif socket_path_kind == "symlink-alias":
        alias_parent = runtime_socket_path.parent / "state-alias"
        alias_parent.symlink_to(runtime_socket_path.parent, target_is_directory=True)
        socket_path = alias_parent / "managed.sock"
    else:
        socket_path = runtime_socket_path.parent / ("x" * 100) / "managed.sock"
        assert len(os.fsencode(str(socket_path))) >= 104

    with pytest.raises(ManagedStateError) as raised:
        store.register_runtime(
            daemon_id="daemon-path",
            generation=owner["generation"],
            pid=45003,
            start_token="path-token",
            pgid=45016,
            socket_path=socket_path,
        )
    assert raised.value.code in {"invalid", "unsafe-state", "ownership-conflict",
                                 "unknown"}
    assert not _runtime_path(store).exists()


def test_malformed_runtime_record_fails_closed_unchanged(
        managed_workspace, runtime_socket_path):
    """Malformed runtime discovery state is not treated as no running daemon."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-malformed")
    store.register_runtime(
        daemon_id="daemon-malformed", generation=owner["generation"],
        pid=45004, start_token="malformed-token",
        pgid=45017,
        socket_path=runtime_socket_path,
    )
    runtime_file = _runtime_path(store)
    runtime_file.write_text("{not-json\n", encoding="utf-8")
    before = runtime_file.read_bytes()

    with pytest.raises(ManagedStateError) as raised:
        store.read_runtime()
    assert raised.value.code in {"invalid", "corrupt", "unsafe-state", "unknown"}
    assert runtime_file.read_bytes() == before


def test_symlinked_runtime_record_fails_closed_unchanged(
        managed_workspace, runtime_socket_path, tmp_path: Path):
    """Discovery refuses a runtime record replaced by a symlink."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-symlink")
    store.register_runtime(
        daemon_id="daemon-symlink", generation=owner["generation"],
        pid=45005, start_token="symlink-token",
        pgid=45018,
        socket_path=runtime_socket_path,
    )
    runtime_file = _runtime_path(store)
    outside = tmp_path / "outside-runtime.json"
    outside.write_text("{}\n", encoding="utf-8")
    runtime_file.unlink()
    runtime_file.symlink_to(outside)

    with pytest.raises(ManagedStateError) as raised:
        store.read_runtime()
    assert raised.value.code in {"unsafe-state", "invalid", "unknown"}
    assert runtime_file.is_symlink()
    assert runtime_file.readlink() == outside


def test_noncanonical_socket_in_runtime_record_fails_closed_unchanged(
        managed_workspace, runtime_socket_path):
    """A record cannot smuggle a normalized-but-noncanonical endpoint spelling."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-noncanonical")
    socket_path = runtime_socket_path
    store.register_runtime(
        daemon_id="daemon-noncanonical", generation=owner["generation"],
        pid=45006, start_token="noncanonical-token", pgid=45019,
        socket_path=socket_path,
    )
    runtime_file = _runtime_path(store)
    payload = json.loads(runtime_file.read_text(encoding="utf-8"))
    nested = socket_path.parent / "nested"
    nested.mkdir(mode=0o700)
    nested.chmod(0o700)
    noncanonical = nested / ".." / socket_path.name
    assert str(noncanonical) != str(noncanonical.resolve())
    payload["socket_path"] = str(noncanonical)
    runtime_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    before = runtime_file.read_bytes()

    with pytest.raises(ManagedStateError) as raised:
        store.read_runtime()
    assert raised.value.code in {"invalid", "unsafe-state", "unknown"}
    assert runtime_file.read_bytes() == before


@pytest.mark.parametrize(
    "field,bad_value",
    [("daemon_id", "daemon-other"), ("generation", 99),
     ("pid", 45099), ("start_token", "wrong-token"), ("pgid", 45099)],
)
def test_stale_runtime_clear_refuses_without_mutating_record(
        managed_workspace, runtime_socket_path, field, bad_value):
    """Clearing requires the exact daemon generation and process identity."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-clear-stale")
    store.register_runtime(
        daemon_id="daemon-clear-stale", generation=owner["generation"],
        pid=45007, start_token="clear-token",
        pgid=45020,
        socket_path=runtime_socket_path,
    )
    runtime_file = _runtime_path(store)
    before = runtime_file.read_bytes()
    arguments = {
        "daemon_id": "daemon-clear-stale",
        "generation": owner["generation"],
        "pid": 45007,
        "start_token": "clear-token",
        "pgid": 45020,
    }
    arguments[field] = bad_value

    with pytest.raises(ManagedStateError) as raised:
        store.clear_runtime(**arguments)
    assert raised.value.code in {"busy", "invalid", "ownership-conflict",
                                 "stale-generation", "unknown"}
    assert runtime_file.read_bytes() == before


def test_exact_runtime_clear_removes_record_but_preserves_owner_and_claims(
        managed_workspace, runtime_socket_path, tmp_path: Path):
    """Runtime cleanup is narrowly scoped and cannot release durable ownership."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(
        daemon_id="daemon-clear-exact",
        lineage_id="lineage-clear-exact",
        coordinator_session_uuid="coordinator-clear-exact",
    )
    worktree = tmp_path / "runtime-claim"
    worktree.mkdir()
    store.claim_lineage_workspace(
        lineage_id="lineage-clear-exact",
        owner_generation=owner["generation"],
        lineage_generation=1,
        workspace=str(worktree.resolve()),
        common_dir=str(store.identity.common_dir.resolve()),
        repository=str(managed_workspace.project.resolve()),
        coordinator_session_uuid="coordinator-clear-exact",
    )
    store.register_runtime(
        daemon_id="daemon-clear-exact", generation=owner["generation"],
        pid=45008, start_token="exact-clear-token",
        pgid=45021,
        socket_path=runtime_socket_path,
    )
    runtime_file = _runtime_path(store)
    owner_file = store.identity.state_root / "owner.json"
    claims_file = store.identity.global_root / "claims.json"
    owner_before = owner_file.read_bytes()
    claims_before = claims_file.read_bytes()

    store.clear_runtime(
        daemon_id="daemon-clear-exact", generation=owner["generation"],
        pid=45008, start_token="exact-clear-token",
        pgid=45021,
    )

    assert not runtime_file.exists()
    assert store.read_runtime() is None
    assert owner_file.read_bytes() == owner_before
    assert claims_file.read_bytes() == claims_before


def test_enrollment_and_legacy_start_race_has_exactly_one_owner(
        managed_workspace):
    # The state directory itself is created by the contenders while the owner
    # record is absent.  Both operations must take the same fcntl boundary.
    _helper(
        managed_workspace.workspace_repo.parent / "workspace-helper",
        output=f"{managed_workspace.workspace_repo.resolve()}\n",
    )
    ctx = multiprocessing.get_context("fork")
    barrier, results = ctx.Barrier(2), ctx.Queue()
    args = (str(managed_workspace.workspace_repo), managed_workspace.lane,
            "eagle", barrier, results)
    managed = ctx.Process(target=_race_child, args=args[:3] + ("managed",) + args[3:])
    legacy = ctx.Process(target=_race_child, args=args[:3] + ("legacy",) + args[3:])
    managed.start()
    legacy.start()
    try:
        outcomes = [results.get(timeout=5), results.get(timeout=5)]
        managed.join(timeout=5)
        legacy.join(timeout=5)
        assert sum(outcome[0] == "ok" for outcome in outcomes) == 1, outcomes
        assert sum(outcome[0] == "error" for outcome in outcomes) == 1, outcomes
        owner = _store(managed_workspace).read_json("owner.json")
        winner = next(outcome for outcome in outcomes if outcome[0] == "ok")
        assert owner["mode"] == ("managed" if winner[1] == "managed"
                                  else "legacy-lease")
    finally:
        for process in (managed, legacy):
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)


def test_enrollment_and_pending_launch_race_has_exactly_one_owner(
        managed_workspace):
    """Managed enrollment and pending launch share one create-only boundary."""
    _helper(
        managed_workspace.workspace_repo.parent / "workspace-helper",
        output=f"{managed_workspace.workspace_repo.resolve()}\n",
    )
    ctx = multiprocessing.get_context("fork")
    barrier, results = ctx.Barrier(2), ctx.Queue()
    args = (str(managed_workspace.workspace_repo), managed_workspace.lane,
            "eagle", barrier, results)
    pending = ctx.Process(
        target=_pending_or_managed_child,
        args=args[:3] + ("pending",) + args[3:],
    )
    managed = ctx.Process(
        target=_pending_or_managed_child,
        args=args[:3] + ("managed",) + args[3:],
    )
    pending.start()
    managed.start()
    outcomes = []
    try:
        outcomes = [results.get(timeout=5), results.get(timeout=5)]
        pending.join(timeout=5)
        managed.join(timeout=5)
    finally:
        for process in (pending, managed):
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)

    assert pending.exitcode == 0
    assert managed.exitcode == 0
    if any(outcome[0] == "skip" for outcome in outcomes):
        pytest.skip(next(outcome[2] for outcome in outcomes
                         if outcome[0] == "skip"))
    assert sum(outcome[0] == "ok" for outcome in outcomes) == 1, outcomes
    assert sum(outcome[0] == "error" for outcome in outcomes) == 1, outcomes
    winner = next(outcome for outcome in outcomes if outcome[0] == "ok")
    durable = _store(managed_workspace).read_json("owner.json")
    assert durable["mode"] == (
        "pending-launch" if winner[1] == "pending" else "managed"
    )


def test_global_writer_claims_reject_equal_alias_ancestor_and_descendant(
        managed_workspace, tmp_path: Path):
    """Native child worktree claims reject every canonical path overlap."""
    store = _store(managed_workspace, lane="native-claims")
    owner = store.enroll_managed(
        daemon_id="daemon-native-claims",
        lineage_id="lineage-native-claims",
        coordinator_session_uuid="coordinator-native-claims",
    )
    workspace = (tmp_path / "lineage-workspace").resolve()
    workspace.mkdir()
    common_dir = str(store.identity.common_dir.resolve())
    repository = str(managed_workspace.project.resolve())
    store.claim_lineage_workspace(
        lineage_id="lineage-native-claims",
        owner_generation=owner["generation"], lineage_generation=1,
        workspace=str(workspace), common_dir=common_dir,
        repository=repository,
        coordinator_session_uuid="coordinator-native-claims",
    )
    worktrees = tmp_path / "worktrees"
    worktree = worktrees / "writer"
    worktrees.mkdir()
    worktree.mkdir()
    alias_root = tmp_path / "alias-root"
    alias_root.symlink_to(worktrees, target_is_directory=True)
    alias = alias_root / "writer"
    descendant = worktree / "nested"
    descendant.mkdir()
    ancestor = worktrees

    child_arguments = {
        "lineage_id": "lineage-native-claims",
        "coordinator_session_uuid": "coordinator-native-claims",
        "owner_generation": owner["generation"],
        "lineage_generation": 1,
        "workspace": str(workspace),
        "common_dir": common_dir,
        "repository": repository,
        "worktree": str(worktree),
    }
    store.claim_child_worktree(
        **child_arguments,
        agent_id="agent-native-writer", task_id="task-native-writer",
    )
    for conflicting in (worktree, alias, descendant, ancestor):
        candidate = dict(child_arguments)
        candidate["worktree"] = str(conflicting)
        with pytest.raises(ManagedStateError) as raised:
            store.claim_child_worktree(
                **candidate,
                agent_id="agent-native-conflict", task_id="task-native-conflict",
            )
        assert raised.value.code == "ownership-conflict"

    store.release_child_worktree_claim(
        "lineage-native-claims", "agent-native-writer", "task-native-writer",
        coordinator_session_uuid="coordinator-native-claims",
        owner_generation=owner["generation"], lineage_generation=1,
        authoritative=True,
    )
    dirty = worktrees / "unique-dirty"
    dirty.mkdir()
    untracked = dirty / "untracked.txt"
    untracked.write_text("leave me\n", encoding="utf-8")
    dirty_arguments = dict(child_arguments)
    dirty_arguments["worktree"] = str(dirty)
    store.claim_child_worktree(
        **dirty_arguments,
        agent_id="agent-native-dirty", task_id="task-native-dirty",
    )
    assert untracked.read_text(encoding="utf-8") == "leave me\n"
    assert dirty.resolve() != worktree.resolve()


def _claim_race_paths(tmp_path: Path, shape: str):
    root = tmp_path / "raced-claims"
    root.mkdir()
    if shape == "equal":
        target = root / "equal"
        target.mkdir()
        return target, target
    if shape == "symlink-alias":
        target = root / "alias-target"
        target.mkdir()
        alias_root = tmp_path / "raced-claims-alias"
        alias_root.symlink_to(root, target_is_directory=True)
        return target, alias_root / target.name
    if shape == "ancestor":
        ancestor = root / "ancestor"
        descendant = ancestor / "descendant"
        descendant.mkdir(parents=True)
        return ancestor, descendant
    raise AssertionError("unknown claim race shape: %s" % shape)


@pytest.mark.parametrize("shape", ["equal", "symlink-alias", "ancestor"])
def test_equal_alias_or_ancestor_claim_race_has_exactly_one_winner(
        managed_workspace, tmp_path: Path, shape):
    """The locked native child index rejects one overlapping contender."""
    first_path, second_path = _claim_race_paths(tmp_path, shape)
    _helper(
        managed_workspace.workspace_repo.parent / "workspace-helper",
        output=f"{managed_workspace.workspace_repo.resolve()}\n",
    )
    lane = "native-race"
    store = _store(managed_workspace, lane=lane)
    owner = store.enroll_managed(
        daemon_id="daemon-native-race",
        lineage_id="lineage-native-race",
        coordinator_session_uuid="coordinator-native-race",
    )
    workspace_path = (tmp_path / "native-race-workspace").resolve()
    workspace_path.mkdir()
    common_dir = str(store.identity.common_dir.resolve())
    repository = str(managed_workspace.project.resolve())
    store.claim_lineage_workspace(
        lineage_id="lineage-native-race",
        owner_generation=owner["generation"], lineage_generation=1,
        workspace=str(workspace_path), common_dir=common_dir,
        repository=repository,
        coordinator_session_uuid="coordinator-native-race",
    )
    ctx = multiprocessing.get_context("fork")
    barrier, results = ctx.Barrier(2), ctx.Queue()
    base = (str(managed_workspace.workspace_repo),)
    first = ctx.Process(
        target=_native_claim_child,
        args=base + (lane, "eagle", str(first_path), "lineage-native-race",
                     "coordinator-native-race", owner["generation"], 1,
                     str(workspace_path), common_dir, repository, "first",
                     barrier, results),
    )
    second = ctx.Process(
        target=_native_claim_child,
        args=base + (lane, "eagle", str(second_path), "lineage-native-race",
                     "coordinator-native-race", owner["generation"], 1,
                     str(workspace_path), common_dir, repository, "second",
                     barrier, results),
    )
    first.start()
    second.start()
    outcomes = []
    try:
        outcomes = [results.get(timeout=3), results.get(timeout=3)]
        first.join(timeout=3)
        second.join(timeout=3)
    finally:
        for process in (first, second):
            if process.is_alive():
                process.terminate()
            process.join(timeout=3)

    assert first.exitcode == 0
    assert second.exitcode == 0
    assert sum(outcome[0] == "ok" for outcome in outcomes) == 1, outcomes
    assert sum(outcome[0] == "error" for outcome in outcomes) == 1, outcomes
    loser = next(outcome for outcome in outcomes if outcome[0] == "error")
    assert loser[2] == "ownership-conflict"


def test_dirty_unique_worktree_claim_is_accepted_and_preserved(
        managed_workspace, tmp_path: Path):
    """Dirty files do not turn a unique native worktree into a conflict."""
    worktree = tmp_path / "dirty-unique"
    worktree.mkdir()
    dirty_file = worktree / "untracked.txt"
    dirty_file.write_text("preserve this\n", encoding="utf-8")

    store = _store(managed_workspace, lane="dirty-writer")
    owner = store.enroll_managed(
        daemon_id="daemon-dirty-writer",
        lineage_id="lineage-dirty-writer",
        coordinator_session_uuid="coordinator-dirty-writer",
    )
    workspace = (tmp_path / "dirty-lineage-workspace").resolve()
    workspace.mkdir()
    common_dir = str(store.identity.common_dir.resolve())
    repository = str(managed_workspace.project.resolve())
    store.claim_lineage_workspace(
        lineage_id="lineage-dirty-writer",
        owner_generation=owner["generation"], lineage_generation=1,
        workspace=str(workspace), common_dir=common_dir,
        repository=repository,
        coordinator_session_uuid="coordinator-dirty-writer",
    )
    record = store.claim_child_worktree(
        lineage_id="lineage-dirty-writer", worktree=str(worktree),
        repository=repository,
        coordinator_session_uuid="coordinator-dirty-writer",
        owner_generation=owner["generation"], lineage_generation=1,
        workspace=str(workspace), common_dir=common_dir,
        agent_id="agent-native-dirty", task_id="task-native-dirty",
    )

    assert record["worktree"] == str(worktree.resolve())
    assert dirty_file.read_text(encoding="utf-8") == "preserve this\n"


def _native_claim_child(workspace: str, lane: str, host: str, worktree: str,
                        lineage_id: str, coordinator_session_uuid: str,
                        owner_generation: int, lineage_generation: int,
                        workspace_path: str, common_dir: str, repository: str,
                        child_suffix: str, barrier, result):
    helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
    identity = resolve_workspace(lane, env={"LANES_WORKSTATION": host},
                                 helper=helper)
    store = ManagedStateStore(identity)
    barrier.wait()
    try:
        store.claim_child_worktree(
            lineage_id=lineage_id, worktree=worktree, repository=repository,
            coordinator_session_uuid=coordinator_session_uuid,
            owner_generation=owner_generation,
            lineage_generation=lineage_generation,
            workspace=workspace_path, common_dir=common_dir,
            agent_id="agent-native-race-" + child_suffix,
            task_id="task-native-race-" + child_suffix,
        )
        result.put(("ok", lane))
    except ManagedStateError as exc:
        result.put(("error", lane, exc.code))


def test_equal_worktree_claim_race_across_lanes_has_one_winner(
        managed_workspace, tmp_path: Path):
    """Two native lineages cannot claim one isolated worktree concurrently."""
    worktree = tmp_path / "raced-worktree"
    worktree.mkdir()
    _helper(
        managed_workspace.workspace_repo.parent / "workspace-helper",
        output=f"{managed_workspace.workspace_repo.resolve()}\n",
    )
    stores = {
        "race-a": _store(managed_workspace, lane="race-a"),
        "race-b": _store(managed_workspace, lane="race-b"),
    }
    claim_context = {}
    for lane, store in stores.items():
        lineage_id = "lineage-" + lane
        coordinator = "coordinator-" + lane
        owner = store.enroll_managed(
            daemon_id="daemon-" + lane,
            lineage_id=lineage_id,
            coordinator_session_uuid=coordinator,
        )
        workspace = (tmp_path / (lane + "-workspace")).resolve()
        workspace.mkdir()
        common_dir = str(store.identity.common_dir.resolve())
        repository = str(managed_workspace.project.resolve())
        store.claim_lineage_workspace(
            lineage_id=lineage_id, owner_generation=owner["generation"],
            lineage_generation=1, workspace=str(workspace),
            common_dir=common_dir, repository=repository,
            coordinator_session_uuid=coordinator,
        )
        claim_context[lane] = (
            lineage_id, coordinator, owner["generation"], 1, str(workspace),
            common_dir, repository,
        )

    ctx = multiprocessing.get_context("fork")
    barrier, results = ctx.Barrier(2), ctx.Queue()
    args_a = claim_context["race-a"]
    args_b = claim_context["race-b"]
    base = str(managed_workspace.workspace_repo)
    lane_a = ctx.Process(
        target=_native_claim_child,
        args=(base, "race-a", "eagle", str(worktree), *args_a, "a",
              barrier, results),
    )
    lane_b = ctx.Process(
        target=_native_claim_child,
        args=(base, "race-b", "eagle", str(worktree), *args_b, "b",
              barrier, results),
    )
    lane_a.start()
    lane_b.start()
    try:
        outcomes = [results.get(timeout=5), results.get(timeout=5)]
        lane_a.join(timeout=5)
        lane_b.join(timeout=5)
        assert sum(outcome[0] == "ok" for outcome in outcomes) == 1, outcomes
        assert sum(outcome[0] == "error" for outcome in outcomes) == 1, outcomes
        losing = next(outcome for outcome in outcomes if outcome[0] == "error")
        assert losing[2] == "ownership-conflict"
    finally:
        for process in (lane_a, lane_b):
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)


def test_fcntl_lock_serializes_threads_without_nested_fast_path(
        managed_workspace):
    """A second thread in this process cannot inherit the holder's lock."""
    store = _ensure_layout(_store(managed_workspace))
    holder_ready = threading.Event()
    contender_started = threading.Event()
    contender_acquired = threading.Event()
    release = threading.Event()
    errors = []

    def hold_lock():
        try:
            with store.locked():
                holder_ready.set()
                if not release.wait(timeout=3):
                    raise AssertionError("test lock holder was not released")
        except BaseException as exc:  # pragma: no cover - thread diagnostics
            errors.append(exc)

    def contend_for_lock():
        contender_started.set()
        try:
            with store.locked():
                contender_acquired.set()
        except BaseException as exc:  # pragma: no cover - thread diagnostics
            errors.append(exc)

    holder = threading.Thread(target=hold_lock)
    contender = threading.Thread(target=contend_for_lock)
    holder.start()
    try:
        assert holder_ready.wait(timeout=2)
        contender.start()
        assert contender_started.wait(timeout=2)
        assert not contender_acquired.wait(timeout=0.15)
        release.set()
        assert contender_acquired.wait(timeout=2)
    finally:
        release.set()
        holder.join(timeout=3)
        contender.join(timeout=3)

    assert not holder.is_alive()
    assert not contender.is_alive()
    assert errors == []


def test_forked_child_reacquires_lock_after_parent_releases(
        managed_workspace):
    """A fork cannot reuse a parent-held lock as an inherited fast path."""
    store = _ensure_layout(_store(managed_workspace))
    ctx = multiprocessing.get_context("fork")
    started, acquired, errors = ctx.Event(), ctx.Event(), ctx.Queue()
    args = (str(managed_workspace.workspace_repo), managed_workspace.lane,
            "eagle", started, acquired, errors)
    child = ctx.Process(target=_forked_exclusive_lock_contender, args=args)
    with store.locked():
        child.start()
        assert started.wait(timeout=2)
        assert not acquired.wait(timeout=0.15)

    try:
        assert acquired.wait(timeout=2), (
            "forked contender did not acquire after parent release"
        )
        child.join(timeout=2)
        assert not child.is_alive(), "forked contender did not exit cleanly"
    finally:
        if child.is_alive():
            child.terminate()
        child.join(timeout=3)

    assert child.exitcode == 0
    with pytest.raises(queue.Empty):
        errors.get_nowait()


def test_create_only_owner_race_never_overwrites_fresh_enrollment(
        managed_workspace):
    """Only one first enrollment wins, and its durable daemon identity survives."""
    identity = _identity(managed_workspace)
    assert not identity.state_root.exists()
    ctx = multiprocessing.get_context("fork")
    barrier, results = ctx.Barrier(2), ctx.Queue()
    args = (str(managed_workspace.workspace_repo), managed_workspace.lane,
            "eagle", barrier, results)
    first = ctx.Process(
        target=_enroll_owner_child, args=args[:3] + ("daemon-first",) + args[3:]
    )
    second = ctx.Process(
        target=_enroll_owner_child, args=args[:3] + ("daemon-second",) + args[3:]
    )
    first.start()
    second.start()
    try:
        outcomes = [results.get(timeout=5), results.get(timeout=5)]
        first.join(timeout=5)
        second.join(timeout=5)
    finally:
        for process in (first, second):
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    assert all(outcome[0] in {"ok", "error"} for outcome in outcomes), outcomes
    assert sum(outcome[0] == "ok" for outcome in outcomes) == 1, outcomes
    assert sum(outcome[0] == "error" for outcome in outcomes) == 1, outcomes
    losing = next(outcome for outcome in outcomes if outcome[0] == "error")
    assert losing[2] in {"busy", "ownership-conflict"}
    winner = next(outcome for outcome in outcomes if outcome[0] == "ok")
    durable = _store(managed_workspace).read_json("owner.json")
    assert durable["mode"] == "managed"
    assert durable["daemon_id"] == winner[1]


@pytest.mark.parametrize(
    "corrupt_owner",
    ["{not-json", "[]", '{"mode": "not-a-valid-owner"}'],
)
def test_corrupt_owner_record_fails_closed_without_overwrite(
        managed_workspace, corrupt_owner):
    """Malformed owner state is refused and its bytes remain unchanged."""
    store = _ensure_layout(_store(managed_workspace))
    owner = store.identity.state_root / "owner.json"
    owner.write_text(corrupt_owner, encoding="utf-8")
    before = owner.read_bytes()

    with pytest.raises(ManagedStateError) as raised:
        store.enroll_managed(daemon_id="must-not-overwrite")

    assert raised.value.code in {"invalid", "corrupt", "unsafe-state", "unknown"}
    assert owner.read_bytes() == before


@pytest.mark.parametrize("corrupt_claims", ["{not-json", "[]"])
def test_corrupt_global_claims_record_fails_closed_without_overwrite(
        managed_workspace, tmp_path: Path, corrupt_claims):
    """Malformed native claim state cannot be treated as an empty index."""
    store_a = _store(managed_workspace, lane="claims-a")
    owner_a = store_a.enroll_managed(
        daemon_id="daemon-claims-a",
        lineage_id="lineage-claims-a",
        coordinator_session_uuid="coordinator-claims-a",
    )
    workspace_a = (tmp_path / "claimed-workspace").resolve()
    workspace_a.mkdir()
    store_a.claim_lineage_workspace(
        lineage_id="lineage-claims-a", owner_generation=owner_a["generation"],
        lineage_generation=1, workspace=str(workspace_a),
        common_dir=str(store_a.identity.common_dir.resolve()),
        repository=str(managed_workspace.project.resolve()),
        coordinator_session_uuid="coordinator-claims-a",
    )
    claims_path, _ = _claim_payload(store_a)
    claims_path.write_text(corrupt_claims, encoding="utf-8")
    before = claims_path.read_bytes()

    store_b = _store(managed_workspace, lane="claims-b")
    owner_b = store_b.enroll_managed(
        daemon_id="daemon-claims-b",
        lineage_id="lineage-claims-b",
        coordinator_session_uuid="coordinator-claims-b",
    )
    worktree_b = tmp_path / "other"
    worktree_b.mkdir()
    with pytest.raises(ManagedStateError) as raised:
        store_b.claim_lineage_workspace(
            lineage_id="lineage-claims-b", owner_generation=owner_b["generation"],
            lineage_generation=1, workspace=str(worktree_b.resolve()),
            common_dir=str(store_b.identity.common_dir.resolve()),
            repository=str(managed_workspace.project.resolve()),
            coordinator_session_uuid="coordinator-claims-b",
        )

    assert raised.value.code in {"invalid", "corrupt", "unsafe-state", "unknown",
                                 "schema-mismatch", "migration-required",
                                 "ownership-conflict"}
    assert claims_path.read_bytes() == before


@pytest.mark.skipif(os.name == "nt", reason="FIFO records require POSIX")
def test_fifo_owner_record_is_rejected_as_non_regular_without_blocking(
        managed_workspace):
    """State readers inspect record type before opening a FIFO."""
    store = _ensure_layout(_store(managed_workspace))
    owner = store.identity.state_root / "owner.json"
    owner.unlink()
    os.mkfifo(owner, 0o600)
    ctx = multiprocessing.get_context("fork")
    result = ctx.Queue()
    child = ctx.Process(
        target=_read_owner_child,
        args=(str(managed_workspace.workspace_repo), managed_workspace.lane,
              "eagle", result),
    )
    child.start()
    try:
        try:
            outcome = result.get(timeout=2)
        except queue.Empty:
            pytest.fail("reading a FIFO record blocked instead of refusing")
    finally:
        if child.is_alive():
            child.terminate()
        child.join(timeout=3)

    assert outcome[0] == "error", outcome
    assert stat.S_ISFIFO(os.lstat(owner).st_mode)


@pytest.mark.parametrize(
    "field,stale_value",
    [("generation", -1), ("lane", "foreign-lane"),
     ("repository", "foreign-repository")],
)
def test_stale_claim_generation_or_identity_refuses_without_ignoring_record(
        managed_workspace, tmp_path: Path, field, stale_value):
    """A stale native claim is an error, never an invitation to claim anew."""
    store_a = _store(managed_workspace, lane="stale-a")
    owner_a = store_a.enroll_managed(
        daemon_id="daemon-stale-a", lineage_id="lineage-stale-a",
        coordinator_session_uuid="coordinator-stale-a",
    )
    workspace_a = (tmp_path / "claimed-workspace").resolve()
    workspace_a.mkdir()
    store_a.claim_lineage_workspace(
        lineage_id="lineage-stale-a", owner_generation=owner_a["generation"],
        lineage_generation=1, workspace=str(workspace_a),
        common_dir=str(store_a.identity.common_dir.resolve()),
        repository=str(managed_workspace.project.resolve()),
        coordinator_session_uuid="coordinator-stale-a",
    )
    claims_path, payload = _claim_payload(store_a)
    claim = _first_claim(payload)
    claim["owner_generation" if field == "generation" else field] = stale_value
    claims_path.write_text(json.dumps(payload), encoding="utf-8")
    before = claims_path.read_bytes()

    store_b = _store(managed_workspace, lane="stale-b")
    owner_b = store_b.enroll_managed(
        daemon_id="daemon-stale-b", lineage_id="lineage-stale-b",
        coordinator_session_uuid="coordinator-stale-b",
    )
    workspace_b = (tmp_path / "other-workspace").resolve()
    workspace_b.mkdir()
    with pytest.raises(ManagedStateError) as raised:
        store_b.claim_lineage_workspace(
            lineage_id="lineage-stale-b", owner_generation=owner_b["generation"],
            lineage_generation=1, workspace=str(workspace_b),
            common_dir=str(store_b.identity.common_dir.resolve()),
            repository=str(managed_workspace.project.resolve()),
            coordinator_session_uuid="coordinator-stale-b",
        )

    assert raised.value.code in {"invalid", "corrupt", "stale-generation",
                                 "ownership-conflict", "unknown"}
    assert claims_path.read_bytes() == before


def test_lock_timeout_is_bounded_and_refuses_while_held(managed_workspace):
    """The public lock context accepts a finite timeout and fails closed."""
    store = _ensure_layout(_store(managed_workspace))
    holder_ready = threading.Event()
    release = threading.Event()
    errors = []

    def hold_lock():
        try:
            with store.locked():
                holder_ready.set()
                release.wait(timeout=3)
        except BaseException as exc:  # pragma: no cover - thread diagnostics
            errors.append(exc)

    holder = threading.Thread(target=hold_lock)
    holder.start()
    try:
        assert holder_ready.wait(timeout=2)
        with pytest.raises(ManagedStateError) as raised:
            with store.locked(timeout=0.05):
                raise AssertionError("timed-out lock unexpectedly acquired")
        assert raised.value.code in {"busy", "timeout", "deadline"}
    finally:
        release.set()
        holder.join(timeout=3)

    assert not holder.is_alive()
    assert errors == []


def test_recover_managed_owner_replaces_incarnation_without_gap_or_claim_loss(
        managed_workspace, runtime_socket_path, tmp_path: Path, monkeypatch):
    """Recovery keeps the owner and claim while replacing only the daemon identity."""
    store = _store(managed_workspace)
    owner, runtime, _worktree, _claim = _seed_managed_recovery(
        store, managed_workspace, tmp_path, runtime_socket_path,
    )
    claims_file = store.identity.global_root / "claims.json"
    claims_before = claims_file.read_bytes()
    generation_file = store.identity.state_root / "generation.json"
    generation_before = generation_file.read_bytes()
    owner_writes = []
    write_owner = store._write_owner

    def observe_owner_write(record):
        owner_writes.append(dict(record))
        return write_owner(record)

    monkeypatch.setattr(store, "_write_owner", observe_owner_write)
    arguments = _recovery_arguments(
        owner, runtime, runtime_socket_path.with_name("recovered.sock"),
    )
    recovered = store.recover_managed_owner(**arguments)

    assert recovered["mode"] == "managed"
    assert recovered["daemon_id"] == "daemon-new"
    assert recovered["generation"] == owner["generation"]
    assert recovered["lane"] == owner["lane"]
    assert recovered["lane_key"] == owner["lane_key"]
    assert recovered["host"] == owner["host"]
    # There is no clear-owner write between the old and new incarnations.
    assert len(owner_writes) == 1
    assert owner_writes[0]["mode"] == "managed"
    assert owner_writes[0]["daemon_id"] == "daemon-new"

    current_owner = store.read_json("owner.json")
    current_runtime = store.read_runtime()
    assert current_owner == recovered
    assert current_runtime["daemon_id"] == "daemon-new"
    assert current_runtime["generation"] == owner["generation"]
    assert current_runtime["pid"] == arguments["new_pid"]
    assert current_runtime["start_token"] == arguments["new_start_token"]
    assert current_runtime["pgid"] == arguments["new_pgid"]
    assert current_runtime["socket_path"] == str(
        Path(arguments["socket_path"]).resolve()
    )
    assert claims_file.read_bytes() == claims_before
    assert generation_file.read_bytes() == generation_before


@pytest.mark.parametrize("evidence_case", ["missing", "unknown", "stale", "changed"])
def test_recover_managed_owner_refuses_missing_unknown_stale_or_changed_evidence_unchanged(
        managed_workspace, runtime_socket_path, tmp_path: Path, evidence_case):
    """Recovery never guesses old-process death or overwrites a changed CAS."""
    store = _store(managed_workspace)
    owner, runtime, _worktree, _claim = _seed_managed_recovery(
        store, managed_workspace, tmp_path, runtime_socket_path,
    )
    proof = _recovery_proof(runtime)
    arguments = _recovery_arguments(
        owner, runtime, runtime_socket_path.with_name("refused-recovery.sock"),
        proof=proof,
    )
    if evidence_case == "missing":
        arguments["exclusion_proof"] = {"pid": runtime["pid"]}
    elif evidence_case == "unknown":
        arguments["exclusion_proof"] = _recovery_proof(
            runtime, process_group_owned=False, exited=False, group_excluded=False,
        )
    elif evidence_case == "stale":
        arguments["exclusion_proof"] = _recovery_proof(
            runtime, pid=runtime["pid"] + 1,
        )
    else:
        # The supplied expected runtime identity changed after the evidence
        # was collected.  A stale caller must not be allowed to replace it.
        arguments["old_start_token"] = "changed-old-daemon-start"

    before = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as raised:
        store.recover_managed_owner(**arguments)

    assert raised.value.code in {"live-unverified", "invalid", "busy",
                                 "ownership-conflict", "stale-generation",
                                 "unknown", "uncertain-effect"}
    assert _durable_state_bytes(store) == before


def test_concurrent_managed_recovery_has_one_exact_cas_winner_and_preserves_claims(
        managed_workspace, runtime_socket_path, tmp_path: Path):
    """Two recovery contenders cannot publish different daemon incarnations."""
    store = _store(managed_workspace)
    owner, runtime, _worktree, _claim = _seed_managed_recovery(
        store, managed_workspace, tmp_path, runtime_socket_path,
    )
    claims_file = store.identity.global_root / "claims.json"
    claims_before = claims_file.read_bytes()
    base = _recovery_arguments(
        owner, runtime, runtime_socket_path.with_name("recovery-one.sock"),
        daemon_id="daemon-recovery-one", pid=46111,
        start_token="recovery-one-start", pgid=46112,
        request_id="recovery-one-request",
    )
    alternate = dict(base)
    alternate.update({
        "new_daemon_id": "daemon-recovery-two",
        "new_pid": 46121,
        "new_start_token": "recovery-two-start",
        "new_pgid": 46122,
        "socket_path": str(runtime_socket_path.with_name("recovery-two.sock")),
        "request_id": "recovery-two-request",
    })
    _helper(
        managed_workspace.workspace_repo.parent / "workspace-helper",
        output=f"{managed_workspace.workspace_repo.resolve()}\n",
    )
    ctx = multiprocessing.get_context("fork")
    barrier, results = ctx.Barrier(2), ctx.Queue()
    args = (str(managed_workspace.workspace_repo), managed_workspace.lane,
            "eagle", barrier, results)
    first = ctx.Process(
        target=_recover_managed_child,
        args=args[:3] + (base, ) + args[3:],
    )
    second = ctx.Process(
        target=_recover_managed_child,
        args=args[:3] + (alternate, ) + args[3:],
    )
    first.start()
    second.start()
    outcomes = []
    try:
        outcomes = [results.get(timeout=5), results.get(timeout=5)]
        first.join(timeout=5)
        second.join(timeout=5)
    finally:
        for process in (first, second):
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)

    assert first.exitcode == 0
    assert second.exitcode == 0
    assert sum(outcome[0] == "ok" for outcome in outcomes) == 1, outcomes
    assert sum(outcome[0] == "error" for outcome in outcomes) == 1, outcomes
    loser = next(outcome for outcome in outcomes if outcome[0] == "error")
    assert loser[2] in {"busy", "ownership-conflict", "stale-generation",
                         "live-unverified", "uncertain-effect"}
    winner = next(outcome for outcome in outcomes if outcome[0] == "ok")
    expected = base if winner[1] == base["new_daemon_id"] else alternate
    final_owner = store.read_json("owner.json")
    final_runtime = store.read_runtime()
    assert final_owner["daemon_id"] == winner[1]
    assert final_owner["generation"] == owner["generation"]
    assert final_runtime["daemon_id"] == winner[1]
    assert final_runtime["pid"] == expected["new_pid"]
    assert final_runtime["start_token"] == expected["new_start_token"]
    assert final_runtime["pgid"] == expected["new_pgid"]
    assert claims_file.read_bytes() == claims_before


def test_recovery_hard_stop_after_owner_new_is_reconciled_by_exact_retry(
        managed_workspace, runtime_socket_path, tmp_path: Path):
    """An ownerNEW/runtimeNEW crash leaves intent recoverable, never unowned."""
    store = _store(managed_workspace)
    owner, runtime, _worktree, _claim = _seed_managed_recovery(
        store, managed_workspace, tmp_path, runtime_socket_path,
    )
    arguments = _recovery_arguments(
        owner, runtime, runtime_socket_path.with_name("crash-recovery.sock"),
        daemon_id="daemon-crash-recovery", pid=46131,
        start_token="crash-recovery-start", pgid=46132,
        request_id="crash-recovery-request",
    )
    claims_file = store.identity.global_root / "claims.json"
    claims_before = claims_file.read_bytes()
    generation_file = store.identity.state_root / "generation.json"
    generation_before = generation_file.read_bytes()
    ctx = multiprocessing.get_context("fork")
    result = ctx.Queue()
    child = ctx.Process(
        target=_crash_recovery_after_owner_write,
        args=(str(managed_workspace.workspace_repo), managed_workspace.lane,
              "eagle", arguments, result),
    )
    child.start()
    try:
        child.join(timeout=5)
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)

    assert child.exitcode == 77
    reloaded = _store(managed_workspace)
    interrupted_owner = reloaded.read_json("owner.json")
    assert interrupted_owner["daemon_id"] == arguments["new_daemon_id"]
    assert interrupted_owner["generation"] == owner["generation"]
    with pytest.raises(ManagedStateError) as unresolved:
        reloaded.read_runtime()
    assert unresolved.value.code in {"ownership-conflict", "stale-generation",
                                     "live-unverified", "invalid",
                                     "uncertain-effect"}
    assert (reloaded.identity.state_root / "owner.json").exists()

    recovered = reloaded.recover_managed_owner(**arguments)
    assert recovered["daemon_id"] == arguments["new_daemon_id"]
    final_runtime = reloaded.read_runtime()
    assert final_runtime["daemon_id"] == arguments["new_daemon_id"]
    assert final_runtime["pid"] == arguments["new_pid"]
    assert final_runtime["start_token"] == arguments["new_start_token"]
    assert final_runtime["pgid"] == arguments["new_pgid"]
    assert claims_file.read_bytes() == claims_before
    assert generation_file.read_bytes() == generation_before

    # Exact retry after successful reconciliation is idempotent and writes no
    # second claim/owner transition.
    after_success = _durable_state_bytes(reloaded)
    assert reloaded.recover_managed_owner(**arguments) == recovered
    assert _durable_state_bytes(reloaded) == after_success

    changed = dict(arguments)
    changed.update({
        "new_daemon_id": "daemon-different-request",
        "new_pid": 46141,
        "new_start_token": "different-request-start",
        "new_pgid": 46142,
        "socket_path": str(runtime_socket_path.with_name("different.sock")),
        "request_id": "different-recovery-request",
    })
    before_changed = _durable_state_bytes(reloaded)
    with pytest.raises(ManagedStateError) as changed_error:
        reloaded.recover_managed_owner(**changed)
    assert changed_error.value.code in {"busy", "ownership-conflict",
                                        "stale-generation", "invalid",
                                        "live-unverified", "uncertain-effect"}
    assert _durable_state_bytes(reloaded) == before_changed


def test_managed_unenroll_requires_released_claims_runtime_clear_and_quiescence(
        managed_workspace, runtime_socket_path, tmp_path: Path):
    """Only the exact quiescent owner may clear ownership, with generation tombstone."""
    store = _store(managed_workspace)
    owner, runtime, worktree, claim = _seed_managed_recovery(
        store, managed_workspace, tmp_path, runtime_socket_path,
    )
    owner_file = store.identity.state_root / "owner.json"
    claims_file = store.identity.global_root / "claims.json"
    before_active = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as active_error:
        store.unenroll_managed(
            owner["daemon_id"], owner["generation"], quiescent=True,
        )
    assert active_error.value.code in {"ownership-conflict", "busy",
                                       "live-unverified"}
    assert _durable_state_bytes(store) == before_active

    store.release_lineage_claim(
        lineage_id=claim["lineage_id"],
        coordinator_session_uuid=claim["coordinator_session_uuid"],
        owner_generation=owner["generation"],
        lineage_generation=claim["lineage_generation"],
        authoritative=True,
    )
    before_runtime = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as runtime_error:
        store.unenroll_managed(
            owner["daemon_id"], owner["generation"], quiescent=True,
        )
    assert runtime_error.value.code in {"ownership-conflict", "busy",
                                        "live-unverified"}
    assert _durable_state_bytes(store) == before_runtime

    store.clear_runtime(
        runtime["daemon_id"], runtime["generation"], runtime["pid"],
        runtime["start_token"], runtime["pgid"],
    )
    before_unquiescent = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as quiescence_error:
        store.unenroll_managed(
            owner["daemon_id"], owner["generation"], quiescent=False,
        )
    assert quiescence_error.value.code in {"live-unverified", "invalid",
                                           "ownership-conflict"}
    assert _durable_state_bytes(store) == before_unquiescent

    assert store.unenroll_managed(
        owner["daemon_id"], owner["generation"], quiescent=True,
    ) == {}
    assert owner_file.read_bytes() == b"{}\n"
    assert store.read_runtime() is None
    claims_payload = json.loads(claims_file.read_text(encoding="utf-8"))
    assert claims_payload["claims"] == []
    generation_payload = json.loads(
        (store.identity.state_root / "generation.json").read_text(
            encoding="utf-8"
        )
    )
    assert generation_payload["generation"] == owner["generation"]

    reenrolled = store.enroll_managed(daemon_id="daemon-next-generation")
    assert reenrolled["generation"] > owner["generation"]
    assert reenrolled["generation"] != 1

    stale_before = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as stale_error:
        store.unenroll_managed(
            owner["daemon_id"], owner["generation"], quiescent=True,
        )
    assert stale_error.value.code in {"ownership-conflict", "busy",
                                      "stale-generation", "invalid"}
    assert _durable_state_bytes(store) == stale_before

    # An old generation cannot submit a post-unenrollment recovery either.
    stale_recovery = _recovery_arguments(
        owner, runtime, runtime_socket_path.with_name("stale.sock"),
    )
    with pytest.raises(ManagedStateError) as stale_recovery_error:
        store.recover_managed_owner(**stale_recovery)
    assert stale_recovery_error.value.code in {"ownership-conflict", "busy",
                                               "stale-generation", "invalid",
                                               "live-unverified", "uncertain-effect"}
    assert _durable_state_bytes(store) == stale_before


def test_lineage_claim_retry_is_one_locked_index_write_and_exact_retry(
        managed_workspace, tmp_path: Path, monkeypatch):
    """A repeated native claim never publishes a claim gap or duplicate."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(
        daemon_id="daemon-lineage-retry",
        lineage_id="lineage-lineage-retry",
        coordinator_session_uuid="coordinator-lineage-retry",
    )
    workspace_path = (tmp_path / "lineage-retry-workspace").resolve()
    workspace_path.mkdir()
    repository = str(managed_workspace.project.resolve())
    arguments = {
        "lineage_id": "lineage-lineage-retry",
        "owner_generation": owner["generation"],
        "lineage_generation": 1,
        "workspace": str(workspace_path),
        "common_dir": str(store.identity.common_dir.resolve()),
        "repository": repository,
        "coordinator_session_uuid": "coordinator-lineage-retry",
    }
    first = store.claim_lineage_workspace(
        **arguments,
    )
    claims_file = store.identity.global_root / "claims.json"
    writes = []
    write_claims = store._write_claims

    def observe_claim_write(claims):
        writes.append([dict(claim) for claim in claims])
        return write_claims(claims)

    monkeypatch.setattr(store, "_write_claims", observe_claim_write)
    retry = store.claim_lineage_workspace(**arguments)

    assert retry == first
    assert retry["state"] == "active"
    assert retry["lineage_id"] == "lineage-lineage-retry"
    assert len(writes) == 0
    payload = json.loads(claims_file.read_text(encoding="utf-8"))
    assert len(payload["claims"]) == 1
    assert payload["claims"][0]["lineage_id"] == "lineage-lineage-retry"


def test_independent_claim_transfer_api_refuses_without_mutation(
        managed_workspace, tmp_path: Path):
    """The old participant transfer API cannot mutate native claims."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(
        daemon_id="daemon-transfer-refuse",
        lineage_id="lineage-transfer-refuse",
        coordinator_session_uuid="coordinator-transfer-refuse",
    )
    workspace_path = (tmp_path / "transfer-refuse-workspace").resolve()
    workspace_path.mkdir()
    repository = str(managed_workspace.project.resolve())
    store.claim_lineage_workspace(
        lineage_id="lineage-transfer-refuse",
        owner_generation=owner["generation"], lineage_generation=1,
        workspace=str(workspace_path),
        common_dir=str(store.identity.common_dir.resolve()),
        repository=repository,
        coordinator_session_uuid="coordinator-transfer-refuse",
    )
    claims_file = store.identity.global_root / "claims.json"
    before = _durable_state_bytes(store)

    with pytest.raises(ManagedStateError) as raised:
        store.transfer_writer_claim(
            old_participant_id="coordinator-old",
            worktree=str(workspace_path), repository=repository,
            lane=owner["lane"], generation=owner["generation"],
            new_participant_id="coordinator-new",
        )

    assert raised.value.code == "unsupported"
    assert _durable_state_bytes(store) == before
    assert claims_file.read_bytes() == before[
        str(claims_file.relative_to(store.identity.global_root))
    ]


@pytest.mark.parametrize(
    "foreign_domain",
    ["linux:" + ("0" * 32) + ":pid:[999999]", "unknown"],
)
def test_process_domain_is_durable_and_same_pid_foreign_or_unknown_domain_refuses(
        managed_workspace, runtime_socket_path, tmp_path: Path, foreign_domain):
    """PID/start/PGID equality is insufficient without the exact local domain."""
    local_domain = "local"
    store = _store(managed_workspace)
    owner = store.enroll_managed(
        daemon_id="daemon-process-domain", process_domain=local_domain,
        lineage_id="lineage-process-domain",
        coordinator_session_uuid="coordinator-process-domain",
    )
    runtime = store.register_runtime(
        daemon_id=owner["daemon_id"], generation=owner["generation"],
        pid=46201, start_token="domain-runtime-start", pgid=46202,
        socket_path=runtime_socket_path, process_domain=local_domain,
    )
    worktree = tmp_path / "domain-claim"
    worktree.mkdir()
    workspace = (tmp_path / "domain-workspace").resolve()
    workspace.mkdir()
    store.claim_lineage_workspace(
        lineage_id="lineage-process-domain",
        owner_generation=owner["generation"], lineage_generation=1,
        workspace=str(workspace),
        common_dir=str(store.identity.common_dir.resolve()),
        repository=str(managed_workspace.project.resolve()),
        coordinator_session_uuid="coordinator-process-domain",
    )
    assert owner["process_domain"] == local_domain
    assert runtime["process_domain"] == local_domain
    assert store.read_runtime()["process_domain"] == local_domain

    runtime_file = _runtime_path(store)
    local_runtime_bytes = runtime_file.read_bytes()
    foreign_runtime = json.loads(local_runtime_bytes.decode("utf-8"))
    foreign_runtime["process_domain"] = foreign_domain
    runtime_file.write_text(
        json.dumps(foreign_runtime, sort_keys=True, separators=(",", ":")) +
        "\n",
        encoding="utf-8",
    )
    before_foreign_read = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as read_error:
        store.read_runtime()
    assert read_error.value.code in {"invalid", "busy", "ownership-conflict",
                                     "stale-generation", "unknown",
                                     "live-unverified"}
    assert _durable_state_bytes(store) == before_foreign_read
    runtime_file.write_bytes(local_runtime_bytes)

    before_clear = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as clear_error:
        store.clear_runtime(
            runtime["daemon_id"], runtime["generation"], runtime["pid"],
            runtime["start_token"], runtime["pgid"],
            process_domain=foreign_domain,
        )
    assert clear_error.value.code in {"invalid", "busy", "ownership-conflict",
                                      "stale-generation", "unknown",
                                      "live-unverified"}
    assert _durable_state_bytes(store) == before_clear
    assert runtime_file.read_bytes() == before_clear[
        str(runtime_file.relative_to(store.identity.global_root))
    ]

    recovery = _recovery_arguments(
        owner, runtime, runtime_socket_path.with_name("domain-recovered.sock"),
        daemon_id="daemon-process-domain-new", pid=46211,
        start_token="domain-new-start", pgid=46212,
    )
    recovery.update({
        "old_process_domain": local_domain,
        "new_process_domain": local_domain,
        "exclusion_proof": _recovery_proof(
            runtime, process_domain=foreign_domain,
        ),
    })
    before_recovery = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as recovery_error:
        store.recover_managed_owner(**recovery)
    assert recovery_error.value.code in {"invalid", "busy", "ownership-conflict",
                                         "stale-generation", "unknown",
                                         "live-unverified"}
    assert _durable_state_bytes(store) == before_recovery

    # A proof from this exact local process domain is the only one accepted.
    recovery["exclusion_proof"] = _recovery_proof(
        runtime, process_domain=local_domain,
    )
    recovered = store.recover_managed_owner(**recovery)
    assert recovered["process_domain"] == local_domain
    assert store.read_runtime()["process_domain"] == local_domain


# ---------------------------------------------------------------------------
# Native-lineage schema boundary (T005)
# ---------------------------------------------------------------------------

_NATIVE_SCHEMA_VERSION = 2
_NATIVE_ARCHITECTURE = "native-coordinator-lineage"


def _legacy_independent_worker_snapshot() -> dict:
    """Return an arbitrary old-worker blob used as supplemental evidence.

    This is intentionally not passed through ``write_json``.  A migration
    boundary must be tested against bytes that already exist on disk, and no
    state writer may get an opportunity to normalize those bytes first.
    """
    return {
        "schema_version": 1,
        "architecture": "independent-worker",
        "mode": "independent-workers",
        "participants": [
            {
                "participant_id": "worker-old",
                "session_id": "session-old",
                "session_uuid": "session-old",
                "uuid": "session-old",
                "mailbox_id": "mailbox-old",
                "mailbox": "mailbox-old",
                "runner_id": "runner-old",
                "process_group_id": "pg-old",
                "open": {"state": "active"},
                "release": {"state": "pending"},
            }
        ],
        "mailboxes": [
            {
                "message_id": "message-old",
                "recipient_id": "worker-old",
                "mailbox_id": "mailbox-old",
            }
        ],
    }


def _observed_local_process_domain() -> str:
    """Return the process-domain token the recovery API will accept locally."""
    try:
        from lane_managed_state import _local_process_domain
    except ImportError:  # pragma: no cover - old prototype had no helper
        return "local"
    return _local_process_domain() or "local"


def _legacy_owner_snapshot(store) -> dict:
    """Return the historical managed-owner record before schema v2."""
    identity = store.identity
    # The prototype's managed owner had a mode but no schema marker.  In
    # particular, this is not the independent-worker aggregate blob above.
    return {
        "mode": "managed",
        "daemon_id": "daemon-old",
        "generation": 1,
        "lane": identity.lane,
        "lane_key": identity.lane_key,
        "host": identity.host,
        "process_domain": "local",
        "created_at": 1700000000.0,
    }


def _legacy_runtime_snapshot(store, tmp_path: Path) -> dict:
    """Return the historical daemon discovery record before schema v2."""
    identity = store.identity
    socket_root = (tmp_path / "legacy-runtime-socket").resolve()
    socket_root.mkdir(mode=0o700)
    socket_root.chmod(0o700)
    return {
        "daemon_id": "daemon-old",
        "generation": 1,
        "lane": identity.lane,
        "lane_key": identity.lane_key,
        "host": identity.host,
        "pid": 41001,
        "start_token": "old-runtime-start",
        "pgid": 41002,
        "process_domain": "local",
        "socket_path": str(socket_root / "managed.sock"),
        "timestamp": 1700000000.0,
    }


def _legacy_recovery_snapshot(store, tmp_path: Path) -> dict:
    """Return the historical two-incarnation recovery intent before v2."""
    identity = store.identity
    socket_root = (tmp_path / "legacy-recovery-sockets").resolve()
    socket_root.mkdir(mode=0o700)
    socket_root.chmod(0o700)
    old_socket = socket_root / "old-managed.sock"
    new_socket = socket_root / "new-managed.sock"
    return {
        "state": "pending",
        "request_id": "legacy-recovery-request",
        "lane": identity.lane,
        "lane_key": identity.lane_key,
        "host": identity.host,
        "old_daemon_id": "daemon-old",
        "old_generation": 1,
        "old_pid": 41001,
        "old_start_token": "old-recovery-start",
        "old_pgid": 41002,
        "old_process_domain": "local",
        "old_socket_path": str(old_socket),
        "new_daemon_id": "daemon-new",
        "new_generation": 1,
        "new_pid": 41003,
        "new_start_token": "new-recovery-start",
        "new_pgid": 41004,
        "new_process_domain": "local",
        "new_socket_path": str(new_socket),
        "new_timestamp": 1700000001.0,
    }


def _legacy_claims_snapshot(store, tmp_path: Path) -> dict:
    """Return the historical version-1 global writer-claim index."""
    identity = store.identity
    worktree = (tmp_path / "legacy-claimed-worktree").resolve()
    worktree.mkdir(mode=0o700)
    worktree.chmod(0o700)
    return {
        "version": 1,
        "claims": [{
            "state": "active",
            "lane": identity.lane,
            "lane_key": identity.lane_key,
            "host": identity.host,
            "workspace": str(identity.workspace_root),
            "common_dir": str(identity.common_dir),
            "participant_id": "worker-old",
            "worktree": str(worktree),
            "repository": str(identity.workspace_root),
            "claimed_at": 1700000000.0,
            "generation": 1,
        }],
    }


def _legacy_generation_snapshot() -> dict:
    """Return the historical version-1 generation ledger."""
    return {"version": 1, "generation": 1}


def _write_raw_managed_record(store, name: str, payload: dict) -> Path:
    """Install one private raw record without invoking a state writer."""
    store.ensure_layout()
    root = store.identity.global_root if name == "claims.json" else store.identity.state_root
    path = root / name
    path.write_bytes(
        json.dumps(payload, ensure_ascii=True, sort_keys=True,
                   separators=(",", ":")).encode("utf-8") + b"\n"
    )
    path.chmod(0o600)
    return path


def _legacy_error(error: ManagedStateError) -> None:
    """Assert the stable refusal classes for an obsolete record."""
    assert error.code in {"schema-mismatch", "migration-required"}, (
        error.code, error.message
    )


@pytest.mark.parametrize(
    "record_name,loader,payload_factory",
    [
        ("owner.json", lambda store: store.read_owner(),
         lambda store, tmp_path: _legacy_owner_snapshot(store)),
        ("runtime.json", lambda store: store.read_runtime(),
         _legacy_runtime_snapshot),
        ("recovery.json", lambda store: store._load_recovery_intent(),
         _legacy_recovery_snapshot),
        ("claims.json", lambda store: store._load_claims(),
         _legacy_claims_snapshot),
        ("generation.json", lambda store: store._load_generation(),
         lambda store, tmp_path: _legacy_generation_snapshot()),
    ],
)
def test_schema_v1_independent_snapshot_is_refused_by_every_state_loader_without_rewrite(
        managed_workspace, tmp_path: Path, record_name, loader, payload_factory):
    """Each historical file shape fails closed and preserves its own bytes."""
    store = _store(managed_workspace)
    # Keep owner empty when testing a non-owner file so the selected loader is
    # the one that encounters the obsolete record.
    if record_name != "owner.json":
        store.ensure_layout()
    path = _write_raw_managed_record(
        store, record_name, payload_factory(store, tmp_path)
    )
    before = _durable_state_bytes(store)

    with pytest.raises(ManagedStateError) as raised:
        loader(store)

    _legacy_error(raised.value)
    assert _durable_state_bytes(store) == before
    assert path.read_bytes() == before[str(path.relative_to(store.identity.global_root))]


def _legacy_recovery_call(store, tmp_path: Path):
    """Call recovery with a locally observed process domain and full evidence.

    The schema check must happen before recovery can inspect or mutate a
    process identity.  The IDs are synthetic, but the process-domain token is
    the exact locally observed value (or the implementation's portable local
    token when observation is unavailable), so argument validation cannot
    mask the migration refusal.
    """
    process_domain = _observed_local_process_domain()
    return store.recover_managed_owner(
        old_daemon_id="daemon-old",
        old_generation=1,
        old_pid=41001,
        old_start_token="old-start",
        old_pgid=41002,
        new_daemon_id="daemon-new",
        new_pid=41003,
        new_start_token="new-start",
        new_pgid=41004,
        process_domain=process_domain,
        socket_path=tmp_path / "new-managed.sock",
        request_id="legacy-recovery-request",
        exclusion_proof={
            "pid": 41001,
            "start_token": "old-start",
            "pgid": 41002,
            "process_group_owned": True,
            "exited": True,
            "group_excluded": True,
            "process_domain": process_domain,
        },
    )


def test_schema_v1_snapshot_blocks_every_state_writer_and_recovery_without_mutation(
        managed_workspace, tmp_path: Path):
    """Writers/recovery cannot overwrite or adopt old worker-runner state."""
    store = _store(managed_workspace)
    owner_path = _write_raw_managed_record(
        store, "owner.json", _legacy_independent_worker_snapshot()
    )
    replacement_worktree = tmp_path / "replacement-worktree"
    replacement_worktree.mkdir()

    actions = (
        lambda: store.write_json(
            "owner.json", {"schema_version": _NATIVE_SCHEMA_VERSION,
                            "architecture": _NATIVE_ARCHITECTURE},
        ),
        lambda: store.enroll_managed(daemon_id="daemon-new"),
        lambda: store.begin_legacy(
            pid=42001, start_token="legacy-start", pgid=42002,
        ),
        lambda: store.begin_pending_launch(
            pid=42003, start_token="pending-start",
            request_id="pending-request",
        ),
        lambda: store.claim_writer(
            "lineage-new", replacement_worktree,
            repository=managed_workspace.project,
        ),
        lambda: _legacy_recovery_call(store, tmp_path),
    )

    for action in actions:
        before = _durable_state_bytes(store)
        with pytest.raises(ManagedStateError) as raised:
            action()
        _legacy_error(raised.value)
        assert _durable_state_bytes(store) == before
        assert owner_path.read_bytes() == before[
            str(owner_path.relative_to(store.identity.global_root))
        ]


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 1, "intents": {}},
        {
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "record_kind": "native-adoption-ledger",
            "intents": {"adoption-unknown": {"unexpected": True}},
        },
    ],
)
def test_native_adoption_generic_read_refuses_present_malformed_ledger_without_rewrite(
        managed_workspace, payload):
    """The generic state reader cannot bypass the adoption ledger validator."""
    store = _store(managed_workspace, lane="adoption-reader-boundary")
    store.enroll_managed(daemon_id="daemon-adoption-reader-boundary")
    path = store.identity.state_root / "native-adoptions.json"
    path.write_bytes(
        json.dumps(payload, ensure_ascii=True, sort_keys=True,
                   separators=(",", ":")).encode("utf-8") + b"\n"
    )
    path.chmod(0o600)
    before = path.read_bytes()

    with pytest.raises(ManagedStateError) as raised:
        store.read_json("native-adoptions.json")

    assert raised.value.code in {"schema-mismatch", "invalid", "unsupported"}
    assert path.read_bytes() == before


def test_native_adoption_generic_write_validates_existing_and_candidate_ledger(
        managed_workspace):
    """Generic writes preserve the same strict adoption-ledger boundary."""
    store = _store(managed_workspace, lane="adoption-writer-boundary")
    store.enroll_managed(daemon_id="daemon-adoption-writer-boundary")
    path = store.identity.state_root / "native-adoptions.json"

    malformed = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-adoption-ledger",
        "intents": {"adoption-malformed": {"unexpected": True}},
    }
    with pytest.raises(ManagedStateError) as raised:
        store.write_json("native-adoptions.json", malformed)
    assert raised.value.code in {"invalid", "unsupported", "schema-mismatch"}
    assert not path.exists()

    legacy = {"schema_version": 1, "intents": {}}
    path.write_bytes(
        json.dumps(legacy, ensure_ascii=True, sort_keys=True,
                   separators=(",", ":")).encode("utf-8") + b"\n"
    )
    path.chmod(0o600)
    before = path.read_bytes()
    with pytest.raises(ManagedStateError) as legacy_error:
        store.write_json("native-adoptions.json", malformed)
    assert legacy_error.value.code in {"schema-mismatch", "invalid", "unsupported"}
    assert path.read_bytes() == before


def test_native_adoption_generic_write_refuses_count_and_byte_overflow(
        managed_workspace):
    """The adoption ledger keeps both bounded entries and bounded bytes."""
    store = _store(managed_workspace, lane="adoption-capacity-boundary")
    store.enroll_managed(daemon_id="daemon-adoption-capacity-boundary")
    path = store.identity.state_root / "native-adoptions.json"
    marker = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-adoption-ledger",
    }

    too_many = {
        **marker,
        "intents": {"adoption-%02d" % index: {} for index in range(17)},
    }
    with pytest.raises(ManagedStateError) as count_error:
        store.write_json("native-adoptions.json", too_many)
    assert count_error.value.code in {"invalid", "busy"}
    assert not path.exists()

    too_large = {**marker, "intents": {}, "padding": "x" * (2**20)}
    with pytest.raises(ManagedStateError) as size_error:
        store.write_json("native-adoptions.json", too_large)
    assert size_error.value.code == "invalid"
    assert not path.exists()


# ---------------------------------------------------------------------------
# Lineage-level writer claims (T007)
# ---------------------------------------------------------------------------

_LINEAGE_ID = "lineage-build-7"
_LINEAGE_GENERATION = 3


def _lineage_claim_arguments(store, managed_workspace, *, lineage_id=_LINEAGE_ID,
                             lineage_generation=_LINEAGE_GENERATION,
                             workspace=None):
    """Return the explicit durable identity for one workspace-lineage claim."""
    return {
        "lineage_id": lineage_id,
        "owner_generation": 1,
        "lineage_generation": lineage_generation,
        "workspace": str((store.identity.workspace_root if workspace is None
                           else Path(workspace)).resolve()),
        "common_dir": str(store.identity.common_dir.resolve()),
        "repository": str(managed_workspace.project.resolve()),
    }


def _child_claim_arguments(store, managed_workspace, worktree, *,
                           lineage_id=_LINEAGE_ID,
                           agent_id="agent-native-actual-1",
                           task_id="task-native-actual-1",
                           lineage_generation=_LINEAGE_GENERATION):
    """Return the actual native identity for an isolated child-worktree claim."""
    return {
        "lineage_id": lineage_id,
        "owner_generation": 1,
        "lineage_generation": lineage_generation,
        "agent_id": agent_id,
        "task_id": task_id,
        "worktree": str(Path(worktree).resolve()),
        "common_dir": str(store.identity.common_dir.resolve()),
        "repository": str(managed_workspace.project.resolve()),
    }


def test_readonly_lineage_claim_is_one_owner_for_writable_child_without_second_claim(
        managed_workspace):
    """A writable native child inherits one durable claim from its lineage."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-lineage-claim")
    arguments = _lineage_claim_arguments(store, managed_workspace)
    arguments["owner_generation"] = owner["generation"]

    claim = store.claim_lineage_workspace(**arguments)
    assert claim["lineage_id"] == _LINEAGE_ID
    assert claim["owner_generation"] == owner["generation"]
    assert claim["lineage_generation"] == _LINEAGE_GENERATION
    assert claim["workspace"] == arguments["workspace"]
    assert claim["common_dir"] == arguments["common_dir"]
    assert claim["state"] in {"held", "active"}
    assert {"agent_id", "task_id", "session_uuid", "mailbox_id",
            "process_group_id", "pgid"}.isdisjoint(claim)

    # The coordinator is read-only, but the authorized child writes through
    # this same lineage claim.  Repeating the exact lineage identity is
    # idempotent and must not create a child-owned competing claim.
    retry = store.claim_lineage_workspace(**arguments)
    assert retry == claim
    claims = store._load_claims()
    assert len(claims) == 1
    assert claims[0]["lineage_id"] == _LINEAGE_ID
    assert {"agent_id", "task_id", "session_uuid", "mailbox_id",
            "process_group_id", "pgid"}.isdisjoint(claims[0])


def test_unknown_or_changed_lineage_claim_refuses_without_mutating_claim_index(
        managed_workspace, tmp_path: Path):
    """Unknown lineage/child ownership cannot inherit or retarget a claim."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-lineage-claim-guard")
    lineage = _lineage_claim_arguments(store, managed_workspace)
    lineage["owner_generation"] = owner["generation"]
    store.claim_lineage_workspace(**lineage)

    child_worktree = (tmp_path / "isolated-child").resolve()
    child_worktree.mkdir()
    child = _child_claim_arguments(store, managed_workspace, child_worktree)
    child["owner_generation"] = owner["generation"]
    store.claim_child_worktree(**child)
    before = _durable_state_bytes(store)

    unknown = dict(child)
    unknown["lineage_id"] = "lineage-untracked"
    with pytest.raises(ManagedStateError) as unknown_error:
        store.claim_child_worktree(**unknown)
    assert unknown_error.value.code in {"unknown", "ownership-conflict",
                                        "schema-mismatch", "migration-required"}
    assert _durable_state_bytes(store) == before

    changed = dict(child)
    changed["task_id"] = "task-native-definition-changed"
    changed["worktree"] = str((tmp_path / "changed-child").resolve())
    with pytest.raises(ManagedStateError) as changed_error:
        store.claim_child_worktree(**changed)
    assert changed_error.value.code in {"ownership-conflict", "stale-generation",
                                        "unknown", "invalid"}
    assert _durable_state_bytes(store) == before

    # Identity/capability changes are immutable even when the replacement
    # path is disjoint from every active claim.  A future lifecycle transition
    # must be used for a replacement child; a new claim cannot smuggle one in
    # by avoiding path-overlap checks.
    changed_definition_root = (tmp_path / "changed-definition-child").resolve()
    changed_definition_root.mkdir()
    changed_definition = dict(child)
    changed_definition["worktree"] = str(changed_definition_root)
    changed_definition["definition_digest"] = "0" * 64
    changed_definition["capability_digest"] = "1" * 64
    before_definition = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as definition_error:
        store.claim_child_worktree(**changed_definition)
    assert definition_error.value.code in {"ownership-conflict", "stale-generation",
                                           "unknown", "invalid"}
    assert _durable_state_bytes(store) == before_definition

    # A genuinely distinct native child may use a disjoint worktree under
    # the same lineage.  It gets its own exact IDs, not aliases for the first
    # child, and the existing dirty/untracked files remain untouched.
    distinct_root = (tmp_path / "distinct-child").resolve()
    distinct_root.mkdir()
    distinct_file = distinct_root / "keep-me.txt"
    distinct_file.write_text("distinct child work\n", encoding="utf-8")
    distinct = dict(child)
    distinct["agent_id"] = "agent-native-distinct"
    distinct["task_id"] = "task-native-distinct"
    distinct["worktree"] = str(distinct_root)
    distinct_claim = store.claim_child_worktree(**distinct)
    assert distinct_claim["agent_id"] == "agent-native-distinct"
    assert distinct_claim["task_id"] == "task-native-distinct"
    assert distinct_claim["worktree"] == str(distinct_root)
    assert distinct_file.read_text(encoding="utf-8") == "distinct child work\n"


def test_isolated_child_claim_uses_actual_ids_and_rejects_overlap_but_keeps_dirty_unique_worktree(
        managed_workspace, tmp_path: Path):
    """Child claims are exact native IDs; path aliases/overlap remain exclusive."""
    store = _store(managed_workspace)
    owner = store.enroll_managed(daemon_id="daemon-isolated-claim")
    lineage = _lineage_claim_arguments(store, managed_workspace)
    lineage["owner_generation"] = owner["generation"]
    store.claim_lineage_workspace(**lineage)

    isolated_root = (tmp_path / "isolated-worktrees").resolve()
    isolated_root.mkdir()
    first = isolated_root / "child-a"
    first.mkdir()
    first_child = _child_claim_arguments(
        store, managed_workspace, first,
        agent_id="agent-native-child-a", task_id="task-native-child-a",
    )
    first_child["owner_generation"] = owner["generation"]
    claim = store.claim_child_worktree(**first_child)
    assert claim["lineage_id"] == _LINEAGE_ID
    assert claim["agent_id"] == "agent-native-child-a"
    assert claim["task_id"] == "task-native-child-a"
    assert claim["worktree"] == str(first.resolve())
    assert {"session_uuid", "session_id", "uuid", "mailbox",
            "mailbox_id", "process_group_id", "pgid", "runner_id"}.isdisjoint(claim)

    alias_root = tmp_path / "isolated-alias"
    alias_root.symlink_to(isolated_root, target_is_directory=True)
    descendant = first / "nested"
    descendant.mkdir()
    ancestor = isolated_root
    for overlapping in (alias_root / "child-a", descendant, ancestor):
        conflicting = dict(first_child)
        conflicting["agent_id"] = "agent-native-child-conflict"
        conflicting["task_id"] = "task-native-child-conflict"
        conflicting["worktree"] = str(overlapping)
        before = _durable_state_bytes(store)
        with pytest.raises(ManagedStateError) as raised:
            store.claim_child_worktree(**conflicting)
        assert raised.value.code == "ownership-conflict"
        assert _durable_state_bytes(store) == before

    dirty = isolated_root / "child-dirty"
    dirty.mkdir()
    untracked = dirty / "keep-me.txt"
    untracked.write_text("preserve native child work\n", encoding="utf-8")
    dirty_claim = dict(first_child)
    dirty_claim["agent_id"] = "agent-native-child-dirty"
    dirty_claim["task_id"] = "task-native-child-dirty"
    dirty_claim["worktree"] = str(dirty)
    accepted = store.claim_child_worktree(**dirty_claim)
    assert accepted["agent_id"] == "agent-native-child-dirty"
    assert untracked.read_text(encoding="utf-8") == "preserve native child work\n"


def test_lineage_workspace_claim_conflicts_atomically_across_two_lanes(
        managed_workspace):
    """One canonical workspace cannot be claimed by two durable lineages."""
    store_a = _store(managed_workspace, lane="claim-a")
    store_b = _store(managed_workspace, lane="claim-b")
    owner_a = store_a.enroll_managed(daemon_id="daemon-claim-a")
    owner_b = store_b.enroll_managed(daemon_id="daemon-claim-b")

    first = _lineage_claim_arguments(
        store_a, managed_workspace, lineage_id="lineage-claim-a",
    )
    first["owner_generation"] = owner_a["generation"]
    store_a.claim_lineage_workspace(**first)
    before = _durable_state_bytes(store_b)

    second = _lineage_claim_arguments(
        store_b, managed_workspace, lineage_id="lineage-claim-b",
    )
    second["owner_generation"] = owner_b["generation"]
    with pytest.raises(ManagedStateError) as raised:
        store_b.claim_lineage_workspace(**second)
    assert raised.value.code == "ownership-conflict"
    assert _durable_state_bytes(store_b) == before


def test_same_lineage_id_cannot_cross_lane_reuse_admit_or_release_claim(
        managed_workspace, tmp_path: Path):
    """A lineage ID is lane-scoped; a foreign lane cannot wield its claim."""
    store_a = _store(managed_workspace, lane="same-id-a")
    store_b = _store(managed_workspace, lane="same-id-b")
    owner_a = store_a.enroll_managed(
        daemon_id="daemon-same-id-a", lineage_id="lineage-same-id",
    )
    owner_b = store_b.enroll_managed(
        daemon_id="daemon-same-id-b", lineage_id="lineage-same-id",
    )
    assert owner_a["generation"] == owner_b["generation"] == 1

    first = _lineage_claim_arguments(
        store_a, managed_workspace, lineage_id="lineage-same-id",
    )
    first["owner_generation"] = owner_a["generation"]
    store_a.claim_lineage_workspace(**first)
    foreign_before = _durable_state_bytes(store_a)
    local_before = _durable_state_bytes(store_b)

    # The second lane intentionally presents the same lineage ID and
    # generation.  It must not be treated as an idempotent retry of lane A's
    # workspace claim.
    second = _lineage_claim_arguments(
        store_b, managed_workspace, lineage_id="lineage-same-id",
    )
    second["owner_generation"] = owner_b["generation"]
    with pytest.raises(ManagedStateError) as reuse_error:
        store_b.claim_lineage_workspace(**second)
    assert reuse_error.value.code == "ownership-conflict"
    assert _durable_state_bytes(store_a) == foreign_before
    assert _durable_state_bytes(store_b) == local_before

    # A child in lane B cannot inherit lane A's same-named lineage claim,
    # even when its own worktree is a real, unique directory.
    child_root = (tmp_path / "same-id-foreign-child").resolve()
    child_root.mkdir()
    child = _child_claim_arguments(
        store_b, managed_workspace, child_root,
        lineage_id="lineage-same-id", agent_id="agent-same-id-foreign",
        task_id="task-same-id-foreign",
    )
    child["owner_generation"] = owner_b["generation"]
    before_child = _durable_state_bytes(store_b)
    with pytest.raises(ManagedStateError) as child_error:
        store_b.claim_child_worktree(**child)
    assert child_error.value.code in {"ownership-conflict", "unknown",
                                      "stale-generation"}
    assert _durable_state_bytes(store_a) == foreign_before
    assert _durable_state_bytes(store_b) == before_child

    # Release is equally lane-scoped.  Authoritative proof cannot turn a
    # foreign same-ID claim into a release authority, and neither index may be
    # rewritten by the refusal.
    before_release = _durable_state_bytes(store_b)
    with pytest.raises(ManagedStateError) as release_error:
        store_b.release_lineage_claim(
            lineage_id="lineage-same-id",
            owner_generation=owner_b["generation"],
            lineage_generation=_LINEAGE_GENERATION,
            authoritative=True,
        )
    assert release_error.value.code in {"ownership-conflict", "stale-generation",
                                        "unknown"}
    assert _durable_state_bytes(store_a) == foreign_before
    assert _durable_state_bytes(store_b) == before_release
    claims = store_a.read_lineage_claims()
    assert len(claims) == 1
    assert claims[0]["lineage_id"] == "lineage-same-id"
    assert claims[0]["lane_key"] == store_a.identity.lane_key
