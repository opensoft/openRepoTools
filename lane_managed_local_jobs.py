# SPDX-License-Identifier: Apache-2.0
"""Local Linux job execution and bounded MCP bridge for managed lanes.

The supervisor owns this module's JobSupervisorService.  A Claude session runs
only the stdio MCP bridge, which connects to the supervisor's Unix socket.  A
job is a *new* child of the supervisor, inside its own subreaping worker.  The
worker never adopts a process supplied by a client.  Loss of a worker/result
leaves the T053 intent uncertain; no path here retries it.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import re
import secrets
import selectors
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from lane_managed_state import ManagedStateError


MAX_FRAME = 1024 * 1024
MAX_MCP_LINE = 1536 * 1024
MAX_RUNTIME_SECONDS = 3600
PR_SET_CHILD_SUBREAPER = 36
WAIT_ALL_CHILDREN = 0x40000000  # Linux __WALL, including non-SIGCHLD clone children
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,255}\Z")


def job_socket_path(identity: str) -> Path:
    """Choose a short owner-private runtime socket path for one lane identity."""
    if not isinstance(identity, str) or not identity or len(identity) > 1024:
        _fail("invalid", "job socket identity is malformed")
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    candidates: list[tuple[Path, bool]] = []
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        candidates.append((Path(runtime), True))
    candidates.append((Path(tempfile.gettempdir()), False))
    for base, private_base in candidates:
        try:
            if private_base:
                _private_dir(base)
            directory = base / ("ort-job-%d-%s" % (os.getuid(), key))
            directory.mkdir(mode=0o700, exist_ok=True)
            _private_dir(directory)
            candidate = directory / "jobs.sock"
            if len(os.fsencode(candidate)) < 100:
                return candidate
        except (OSError, ManagedStateError):
            continue
    _fail("unsupported", "no short private job socket path is available")


def _fail(code: str, message: str) -> None:
    raise ManagedStateError(code, message)


def _json_bytes(value: Any) -> bytes:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")
    if len(data) > MAX_FRAME:
        _fail("invalid", "job control frame exceeds its bound")
    return data


def _private_dir(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        _fail("unsafe-state", "job supervisor state directory is not private")


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    if "integrity_digest" in value:
        _fail("invalid", "job custody record supplies its own integrity")
    sealed = dict(value)
    sealed["integrity_digest"] = hashlib.sha256(_json_bytes(value)).hexdigest()
    data = _json_bytes(sealed) + b"\n"
    temporary = path.with_name(path.name + "." + secrets.token_hex(8))
    fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        offset = 0
        while offset < len(data):
            offset += os.write(fd, data[offset:])
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    dirfd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)


def _read_json(path: Path) -> Optional[Mapping[str, Any]]:
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > MAX_FRAME:
            _fail("unsafe-state", "job custody file is unsafe")
        chunks = []
        total = 0
        while total <= MAX_FRAME:
            block = os.read(fd, min(65536, MAX_FRAME + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
        data = b"".join(chunks)
        if len(data) > MAX_FRAME:
            _fail("unsafe-state", "job custody file exceeds its bound")
    finally:
        os.close(fd)
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, ValueError):
        _fail("uncertain-effect", "job custody file is malformed")
    if not isinstance(value, dict):
        _fail("uncertain-effect", "job custody file is malformed")
    integrity = value.pop("integrity_digest", None)
    if (not isinstance(integrity, str) or
            not hmac.compare_digest(integrity, hashlib.sha256(_json_bytes(value)).hexdigest())):
        _fail("ownership-conflict", "job custody file integrity changed")
    return value


def _start_token(pid: int) -> str:
    try:
        stat_line = Path("/proc/%d/stat" % pid).read_text()
        # comm may contain spaces or parentheses; fields after the final ')'
        # begin with field 3, so starttime (field 22) is item 19.
        value = stat_line.rsplit(")", 1)[1].split()[19]
        if not value.isdigit():
            raise ValueError("invalid start time")
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        namespace = os.readlink("/proc/%d/ns/pid" % pid)
        return "%s:%s:%s" % (boot, namespace, value)
    except (OSError, ValueError, IndexError):
        _fail("uncertain-effect", "job process start identity is unavailable")


def _direct_children(pid: int) -> list[int]:
    try:
        data = Path("/proc/%d/task/%d/children" % (pid, pid)).read_text()
        return [int(item) for item in data.split()]
    except (OSError, ValueError):
        _fail("uncertain-effect", "job descendant list is unavailable")


def _reap_children(leader: Optional[int]) -> tuple[Optional[int], bool]:
    leader_code = None
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG | WAIT_ALL_CHILDREN)
        except ChildProcessError:
            return leader_code, True
        if pid == 0:
            return leader_code, False
        if pid == leader:
            leader_code = os.waitstatus_to_exitcode(status)


def _job_key(job_id: str) -> str:
    if not isinstance(job_id, str) or not _TOKEN.fullmatch(job_id):
        _fail("invalid", "job ID is malformed")
    return hashlib.sha256(job_id.encode("utf-8")).hexdigest()


def _inventory(root: Path, deadline: float) -> Mapping[str, Any]:
    """Hash bounded local worktree bytes, including dirty and untracked files.

    `.git` is shared Git metadata, outside the declared local-worktree scope.
    The policy for this scope forbids commands that mutate Git metadata or
    remote services; those require a separate effects reconciler. Symlinks are
    recorded as links and never followed. Mounts inside the root are refused.
    """
    resolved = root.resolve(strict=True)
    if str(resolved) != str(root) or not root.is_dir() or root.is_symlink():
        _fail("unsupported", "job inventory root is not a real directory")
    root = resolved
    root_device = root.stat().st_dev
    digest = hashlib.sha256()
    entries = 0
    total_bytes = 0
    pending = [(root, "")]
    while pending:
        directory, relative = pending.pop()
        if time.monotonic() > deadline:
            _fail("uncertain-effect", "job inventory deadline elapsed")
        with os.scandir(directory) as scan:
            children = sorted(list(scan), key=lambda entry: entry.name)
        for entry in children:
            if not relative and entry.name == ".git":
                continue
            entries += 1
            if entries > 50000:
                _fail("uncertain-effect", "job inventory entry bound exceeded")
            name = relative + "/" + entry.name if relative else entry.name
            path = Path(entry.path)
            info = path.lstat()
            if info.st_dev != root_device or os.path.ismount(path):
                _fail("unsupported", "job inventory crosses a mount")
            prefix = _json_bytes({"path": name, "mode": stat.S_IMODE(info.st_mode),
                                  "kind": stat.S_IFMT(info.st_mode),
                                  "inode": info.st_ino, "links": info.st_nlink,
                                  "uid": info.st_uid, "gid": info.st_gid,
                                  "size": info.st_size,
                                  "mtime_ns": info.st_mtime_ns})
            digest.update(len(prefix).to_bytes(4, "big"))
            digest.update(prefix)
            if stat.S_ISDIR(info.st_mode):
                pending.append((path, name))
            elif stat.S_ISLNK(info.st_mode):
                target = os.readlink(path).encode("utf-8", "surrogateescape")
                digest.update(len(target).to_bytes(4, "big"))
                digest.update(target)
            elif stat.S_ISREG(info.st_mode):
                fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                try:
                    opened = os.fstat(fd)
                    if opened.st_ino != info.st_ino or opened.st_dev != info.st_dev:
                        _fail("uncertain-effect", "job inventory file changed during open")
                    file_digest = hashlib.sha256()
                    while True:
                        if time.monotonic() > deadline:
                            _fail("uncertain-effect", "job inventory deadline elapsed")
                        block = os.read(fd, 65536)
                        if not block:
                            break
                        total_bytes += len(block)
                        if total_bytes > 512 * 1024 * 1024:
                            _fail("uncertain-effect", "job inventory byte bound exceeded")
                        file_digest.update(block)
                    final = os.fstat(fd)
                    if final.st_size != opened.st_size or final.st_mtime_ns != opened.st_mtime_ns:
                        _fail("uncertain-effect", "job inventory file changed during read")
                    digest.update(file_digest.digest())
                finally:
                    os.close(fd)
            else:
                _fail("unsupported", "job inventory contains a special file")
    return {"digest": digest.hexdigest(), "entries": entries, "bytes": total_bytes}


def _signal_owned_child(wrapper_pid: int, child_pid: int) -> None:
    """Signal a verified direct child through a non-reusable pidfd."""
    fd = os.pidfd_open(child_pid)
    try:
        raw = Path("/proc/%d/stat" % child_pid).read_text()
        fields = raw.rsplit(")", 1)[1].split()
        if len(fields) < 20 or int(fields[1]) != wrapper_pid or not fields[19].isdigit():
            _fail("uncertain-effect", "job cancellation lost direct-child identity")
        signal.pidfd_send_signal(fd, signal.SIGKILL)
    finally:
        os.close(fd)


def _worker(control_fd: int, output_fd: int, state_dir: Path, domain_id: str,
            job_id: str, intent_id: str) -> int:
    control = socket.socket(fileno=control_fd)
    try:
        payload = control.recv(MAX_FRAME + 1)
    finally:
        control.close()
    if len(payload) > MAX_FRAME:
        return 90
    try:
        request = json.loads(payload)
        argv = request["argv"]
        cwd = request["cwd"]
        environment = request["environment"]
        limit = request["output_limit_bytes"]
        runtime = request["runtime_seconds"]
        effects_scope = request["effects_scope"]
        worktree_root = Path(request["worktree_root"])
        start_deadline = request["start_deadline"]
        if not isinstance(argv, list) or not argv or not isinstance(cwd, str) or not isinstance(environment, dict):
            return 90
        if not isinstance(limit, int) or not 0 < limit <= MAX_FRAME + 1 or not isinstance(runtime, int) or not 0 < runtime <= MAX_RUNTIME_SECONDS:
            return 90
        if effects_scope not in {"unknown", "local-worktree"} or not isinstance(start_deadline, (int, float)):
            return 90
        libc = ctypes.CDLL(None, use_errno=True)
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
            return 91
        state = ctypes.c_int()
        if libc.prctl(37, ctypes.byref(state), 0, 0, 0) != 0 or state.value != 1:
            return 91
        started_path = state_dir / (_job_key(job_id) + ".started.json")
        result_path = state_dir / (_job_key(job_id) + ".result.json")
        identity = {"pid": os.getpid(), "start_token": _start_token(os.getpid()), "domain_id": domain_id}
        before = None
        if effects_scope == "local-worktree":
            before = _inventory(worktree_root, start_deadline)
        if time.monotonic() >= start_deadline:
            return 94
        read_fd, write_fd = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
        os.set_blocking(write_fd, True)
        try:
            child = subprocess.Popen(argv, cwd=cwd, env=environment,
                                     stdin=subprocess.DEVNULL, stdout=write_fd,
                                     stderr=subprocess.STDOUT, close_fds=True,
                                     start_new_session=True)
        finally:
            os.close(write_fd)
        # Publish only after the actual command has been spawned. A caller may
        # fence the source immediately after observing this identity; no new
        # source-authorized command can still be queued in the worker then.
        _atomic_json(started_path, {"job_id": job_id, "launch_intent_id": intent_id,
                                    "process_identity": identity,
                                    "effects_scope": effects_scope,
                                    "worktree_root": str(worktree_root),
                                    "before_inventory": before})
        selector = selectors.DefaultSelector()
        selector.register(read_fd, selectors.EVENT_READ)
        deadline = time.monotonic() + runtime
        cancel_path = state_dir / (_job_key(job_id) + ".cancel.json")
        total = 0
        truncated = False
        leader_code = None
        pipe_open = True
        drained = False
        while True:
            code, no_children = _reap_children(
                child.pid if leader_code is None else None)
            if code is not None:
                leader_code = code
            if no_children and not pipe_open and leader_code is not None:
                drained = True
                break
            if time.monotonic() >= deadline or cancel_path.exists():
                # The subreaper's direct children include reparented orphans.
                # Repeat as the tree collapses; never signal a session, user or
                # process group shared with another job.
                for pid in _direct_children(os.getpid()):
                    try:
                        _signal_owned_child(os.getpid(), pid)
                    except ProcessLookupError:
                        pass
            for _key, _mask in selector.select(0.05):
                try:
                    chunk = os.read(read_fd, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(read_fd)
                    os.close(read_fd)
                    pipe_open = False
                    continue
                available = max(0, limit - total)
                if len(chunk) > available:
                    truncated = True
                if available:
                    retained = chunk[:available]
                    offset = 0
                    while offset < len(retained):
                        offset += os.write(output_fd, retained[offset:])
                    total += len(retained)
        if not drained:
            return 92
        # An ECHILD observation after the leader exit is the completion proof.
        # The worker cannot create another child after sealing this record.
        # The runner gives us N+1 bytes to distinguish exact N from overflow.
        # Reaching that sentinel is already truncation even if no later byte
        # arrived in the same read chunk.
        truncated = truncated or total >= limit
        os.fsync(output_fd)
        after = None
        if effects_scope == "local-worktree":
            after = _inventory(worktree_root, time.monotonic() + 15)
        _atomic_json(result_path, {"job_id": job_id, "launch_intent_id": intent_id,
                                   "process_identity": identity, "exit_code": leader_code,
                                   "output_truncated": truncated, "subtree_empty": True,
                                   "effects_scope": effects_scope,
                                   "worktree_root": str(worktree_root),
                                   "before_inventory": before, "after_inventory": after})
        return 0
    except Exception:
        # A missing result is deliberately uncertain. Never claim ECHILD after
        # an unexpected exception or attempt to replay this intent.
        return 93
    finally:
        os.close(output_fd)


class LocalJobExecutionDomain:
    """Trusted domain used only inside the long-lived supervisor process."""

    def __init__(self, state_dir: Path | str, domain_id: str,
                 *, max_runtime_seconds: int = MAX_RUNTIME_SECONDS,
                 effects_reconciler: Optional[Callable[[Mapping[str, Any], str,
                     Mapping[str, Any]], Mapping[str, Any]]] = None,
                 next_watermark: Optional[Callable[[int], int]] = None):
        if sys.platform != "linux":
            _fail("unsupported", "local supervised jobs require Linux")
        self.state_dir = Path(state_dir).resolve()
        self.persistent_job_domain_id = domain_id
        self.max_runtime_seconds = max_runtime_seconds
        self.effects_reconciler = effects_reconciler
        self.next_watermark = next_watermark
        self.runner: Any = None
        self._worktree_roots: dict[str, tuple[str, str]] = {}
        self._worktree_lock = threading.Lock()
        if not isinstance(domain_id, str) or not _TOKEN.fullmatch(domain_id):
            _fail("invalid", "job domain ID is malformed")
        if not isinstance(max_runtime_seconds, int) or not 0 < max_runtime_seconds <= MAX_RUNTIME_SECONDS:
            _fail("invalid", "job runtime deadline is invalid")
        self._supervisor_pid = os.getpid()

    def assert_ready(self) -> None:
        if os.getpid() != self._supervisor_pid:
            _fail("ownership-conflict", "job domain is outside its supervisor")
        _private_dir(self.state_dir)
        if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
            _fail("unsupported", "Linux pidfd cancellation is unavailable")
        if not Path("/proc/self/task/%d/children" % os.getpid()).exists():
            _fail("unsupported", "Linux child accounting is unavailable")

    def _paths(self, job_id: str) -> tuple[Path, Path, Path]:
        key = _job_key(job_id)
        return tuple(self.state_dir / (key + suffix) for suffix in
                     (".intent.json", ".started.json", ".result.json"))

    def bind_worktree_root(self, *, job_id: str, worktree_root: str,
                           effects_scope: str) -> None:
        """Receive the runner's registered root before intent consumption."""
        self.assert_ready()
        _job_key(job_id)
        if effects_scope not in {"unknown", "local-worktree"}:
            _fail("invalid", "job effects scope is unsupported")
        path = Path(worktree_root).resolve(strict=True)
        if str(path) != worktree_root or not path.is_dir():
            _fail("ownership-conflict", "job worktree root is not canonical")
        with self._worktree_lock:
            existing = self._worktree_roots.get(job_id)
            if existing is not None and existing != (worktree_root, effects_scope):
                _fail("ownership-conflict", "job root binding changed")
            self._worktree_roots[job_id] = (worktree_root, effects_scope)

    def launch_new(self, *, job_id: str, launch_intent_id: str,
                   argv: Sequence[str], cwd: str, environment: Mapping[str, str],
                   output_fd: int, output_limit_bytes: int, deadline: float) -> int:
        self.assert_ready()
        with self._worktree_lock:
            binding = self._worktree_roots.pop(job_id, None)
        if binding is None:
            _fail("unsupported", "job has no registered worktree root binding")
        worktree_root, effects_scope = binding
        if os.path.commonpath((worktree_root, cwd)) != worktree_root:
            _fail("ownership-conflict", "job cwd is outside registered worktree")
        intent, started, result = self._paths(job_id)
        if any(path.exists() for path in (intent, started, result)):
            _fail("uncertain-effect", "job launch intent was already consumed")
        _atomic_json(intent, {"job_id": job_id, "launch_intent_id": launch_intent_id,
                              "domain_id": self.persistent_job_domain_id})
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "_worker",
                 str(child.fileno()), str(output_fd), str(self.state_dir),
                 self.persistent_job_domain_id, job_id, launch_intent_id],
                pass_fds=(child.fileno(), output_fd), close_fds=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
            child.close()
            parent.send(_json_bytes({"argv": list(argv), "cwd": cwd,
                                     "environment": dict(environment),
                                     "output_limit_bytes": output_limit_bytes,
                                     "runtime_seconds": self.max_runtime_seconds,
                                     "worktree_root": worktree_root,
                                     "effects_scope": effects_scope,
                                     "start_deadline": deadline}))
            while time.monotonic() < deadline:
                observed = _read_json(started)
                if observed is not None:
                    if observed.get("job_id") != job_id or observed.get("launch_intent_id") != launch_intent_id:
                        _fail("ownership-conflict", "job worker identity changed")
                    identity = observed.get("process_identity")
                    if not isinstance(identity, dict) or identity.get("pid") != proc.pid:
                        _fail("ownership-conflict", "job worker PID changed")
                    return proc.pid
                if proc.poll() is not None:
                    _fail("uncertain-effect", "job worker exited before process identity publication")
                time.sleep(0.01)
            # No ACK means the worker might still be between its deadline
            # check and exec. Stop that exact wrapper by pidfd and observe its
            # exit before releasing the runner's source-fence lock. A command
            # already spawned remains uncertain; this is never a replay.
            pidfd = os.pidfd_open(proc.pid)
            try:
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            finally:
                os.close(pidfd)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _fail("uncertain-effect", "job worker timeout termination is uncertain")
            _fail("uncertain-effect", "job worker identity publication timed out")
        finally:
            parent.close()
            child.close()

    def _record_for_identity(self, identity: Mapping[str, Any]) -> Mapping[str, Any]:
        self.assert_ready()
        if identity.get("domain_id") != self.persistent_job_domain_id:
            _fail("ownership-conflict", "job process domain changed")
        for path in self.state_dir.glob("*.started.json"):
            record = _read_json(path)
            if record and record.get("process_identity") == dict(identity):
                return record
        _fail("uncertain-effect", "job worker identity is not in supervisor custody")

    def read_process_identity(self, pid: int) -> Mapping[str, Any]:
        self.assert_ready()
        current_start = _start_token(pid)
        for path in self.state_dir.glob("*.started.json"):
            record = _read_json(path)
            identity = record.get("process_identity") if record else None
            if (isinstance(identity, dict) and identity.get("pid") == pid and
                    identity.get("start_token") == current_start):
                return identity
        _fail("uncertain-effect", "job worker PID is not in supervisor custody")

    def process_is_running(self, process_identity: Mapping[str, Any]) -> bool:
        self._record_for_identity(process_identity)
        try:
            return _start_token(process_identity["pid"]) == process_identity["start_token"]
        except ManagedStateError:
            return False

    def _result(self, job_id: str, identity: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        self._record_for_identity(identity)
        _intent, _started, result = self._paths(job_id)
        value = _read_json(result)
        if value is None:
            return None
        started = self._record_for_identity(identity)
        if (value.get("job_id") != job_id or
                value.get("launch_intent_id") != started.get("launch_intent_id") or
                value.get("process_identity") != dict(identity) or
                value.get("subtree_empty") is not True):
            _fail("ownership-conflict", "job drain result changed identity")
        return value

    def wait_result(self, *, job_id: str, process_identity: Mapping[str, Any],
                    timeout: float) -> Optional[Mapping[str, Any]]:
        end = time.monotonic() + timeout
        while True:
            result = self._result(job_id, process_identity)
            if result is not None:
                return {"exit_code": result["exit_code"],
                        "output_truncated": result["output_truncated"]}
            if time.monotonic() >= end:
                return None
            time.sleep(min(0.05, end - time.monotonic()))

    def job_subtree_empty(self, *, job_id: str,
                          process_identity: Mapping[str, Any]) -> bool:
        return self._result(job_id, process_identity) is not None

    def request_cancel(self, *, job_id: str, process_identity: Mapping[str, Any],
                       cancel_id: str) -> Mapping[str, Any]:
        """Persist one cooperative cancellation intent for this exact worker."""
        if not isinstance(cancel_id, str) or not _TOKEN.fullmatch(cancel_id):
            _fail("invalid", "job cancellation ID is malformed")
        started = self._record_for_identity(process_identity)
        if started.get("job_id") != job_id:
            _fail("ownership-conflict", "cancellation names another job")
        if self._result(job_id, process_identity) is not None:
            return {"job_id": job_id, "state": "completed"}
        path = self.state_dir / (_job_key(job_id) + ".cancel.json")
        existing = _read_json(path)
        if existing is not None:
            if existing.get("cancel_id") != cancel_id or existing.get("process_identity") != dict(process_identity):
                _fail("uncertain-effect", "job cancellation was already requested")
            return {"job_id": job_id, "state": "cancel-requested"}
        # Only the worker of this job observes this file; a timeout or source
        # exit never authorizes a broad signal to the supervisor namespace.
        _atomic_json(path, {"job_id": job_id, "cancel_id": cancel_id,
                            "process_identity": dict(process_identity)})
        return {"job_id": job_id, "state": "cancel-requested"}

    def job_status_witness(self, *, binding: Mapping[str, Any], job_id: str,
                           process_identity: Optional[Mapping[str, Any]],
                           output_ref: Optional[str], result_digest: Optional[str],
                           minimum_watermark: int) -> Mapping[str, Any]:
        runner = self.runner
        if runner is None:
            _fail("unsupported", "local job witness is not attached to its runner")
        job = runner.ledger.status()["jobs"].get(job_id)
        if not isinstance(job, dict):
            _fail("unknown", "job observation has no admitted job")
        record = runner._load_record(job_id)
        if (record.get("process_identity") != process_identity or
                record.get("output_ref") != output_ref or
                record.get("result_digest") != result_digest):
            _fail("ownership-conflict", "job observation custody changed")
        state = record["state"]
        effect_state = "unknown"
        effect_digest = None
        if state == "running" and process_identity is not None:
            started = self._record_for_identity(process_identity)
            if (started.get("effects_scope") == "local-worktree" and
                    isinstance(started.get("before_inventory"), dict) and
                    self.process_is_running(process_identity)):
                # The exact worker is still running under its whole-worktree
                # reservation. Its final bytes are pending, but its local
                # effects are bounded to the declared scope.
                effect_state = "known"
                effect_digest = hashlib.sha256(_json_bytes({
                    "scope": "local-worktree", "root": started["worktree_root"],
                    "before": started["before_inventory"],
                    "process_identity": process_identity,
                })).hexdigest()
        if state in {"completed", "failed"}:
            runner.read_result(job_id)
            worker = self._result(job_id, process_identity)
            if worker is None:
                _fail("uncertain-effect", "job worker drain result disappeared")
            if worker.get("effects_scope") == "local-worktree":
                root = worker.get("worktree_root")
                before = worker.get("before_inventory")
                after = worker.get("after_inventory")
                if (not isinstance(root, str) or not isinstance(before, dict) or
                        not isinstance(after, dict) or
                        not all(re.fullmatch(r"[0-9a-f]{64}", str(row.get("digest")))
                                for row in (before, after))):
                    _fail("uncertain-effect", "job local effects inventory is malformed")
                settlement = {"job_id": job_id, "command_digest": job["command_digest"],
                              "domain_id": self.persistent_job_domain_id,
                              "process_identity": dict(process_identity),
                              "output_ref": output_ref,
                              "result_digest": result_digest,
                              "root": root, "before": before, "after": after}
                expected_digest = hashlib.sha256(_json_bytes(settlement)).hexdigest()
                receipt_path = self.state_dir / (_job_key(job_id) + ".settlement.json")
                receipt = _read_json(receipt_path)
                if receipt is not None:
                    if receipt != {**settlement, "settlement_digest": expected_digest}:
                        _fail("ownership-conflict", "job settlement receipt changed")
                    effect_state = "known"
                    effect_digest = expected_digest
                elif (job.get("effect_state") == "known" and
                      job.get("state") in {"completed", "failed"}):
                    _fail("uncertain-effect", "known job lost its settlement receipt")
                else:
                    # While T053 still holds the reservation, compare a fresh
                    # scan to the worker's ECHILD snapshot. Seal this one-time
                    # receipt before T053 can release that reservation. Later
                    # legitimate jobs may change the worktree without making
                    # this settled historical result unknown again.
                    observed = _inventory(Path(root), time.monotonic() + 15)
                    if observed == after:
                        _atomic_json(receipt_path, {**settlement,
                                                     "settlement_digest": expected_digest})
                        effect_state = "known"
                        effect_digest = expected_digest
            elif self.effects_reconciler is not None:
                # Remote/shared-metadata effects need a separately trusted
                # producer. The model cannot assert known effects itself.
                effect = self.effects_reconciler(dict(binding), job_id, dict(record))
                if not isinstance(effect, Mapping) or set(effect) != {"effect_state", "evidence_digest"}:
                    _fail("uncertain-effect", "job effects reconciliation is malformed")
                if effect["effect_state"] not in {"known", "unknown"} or not re.fullmatch(
                        r"[0-9a-f]{64}", str(effect["evidence_digest"])):
                    _fail("uncertain-effect", "job effects reconciliation is malformed")
                effect_state = effect["effect_state"]
                effect_digest = effect["evidence_digest"]
            if effect_state == "unknown":
                state = "uncertain"
        if self.next_watermark is None:
            _fail("unsupported", "shared supervisor observation clock is unavailable")
        watermark = self.next_watermark(minimum_watermark)
        if isinstance(watermark, bool) or not isinstance(watermark, int) or watermark <= minimum_watermark:
            _fail("uncertain-effect", "job observation watermark did not advance")
        base = {"job_id": job_id, "command_digest": job["command_digest"],
                "domain_id": self.persistent_job_domain_id,
                "observation_watermark": watermark, "state": state,
                "effect_state": effect_state, "process_identity": process_identity,
                "output_ref": output_ref, "result_digest": result_digest,
                "effect_evidence_digest": effect_digest}
        digest = hashlib.sha256(_json_bytes(base)).hexdigest()
        del base["effect_evidence_digest"]
        return {"witness_id": "local-job-" + digest[:32],
                "witness_digest": digest, **base}


def _credential(path: Path) -> Mapping[str, Any]:
    value = _read_json(path)
    if value is None or set(value) != {"token", "parent_uuid", "claim_generation", "runtime_incarnation"}:
        _fail("ownership-conflict", "source job credential is unavailable")
    if (not isinstance(value["token"], str) or len(value["token"]) != 64 or
            isinstance(value["claim_generation"], bool) or
            not isinstance(value["claim_generation"], int) or
            not isinstance(value["runtime_incarnation"], str)):
        _fail("ownership-conflict", "source job credential is malformed")
    return value


class LedgerCredentialVerifier:
    """Issue scoped source credentials and revoke them on owner change.

    The bridge sees only its credential file. The supervisor keeps a digest,
    never a raw token, in a separate private registry. Both the registry and
    T053's current claim are checked for every call.
    """

    def __init__(self, ledger: Any, credential_root: Path | str):
        self.ledger = ledger
        self.credential_root = Path(credential_root).resolve()
        _private_dir(self.credential_root)

    def issue_credential(self, path: Path | str, *, parent_uuid: str,
                         claim_generation: int,
                         runtime_incarnation: str) -> Path:
        if (not isinstance(parent_uuid, str) or not _TOKEN.fullmatch(parent_uuid) or
                isinstance(claim_generation, bool) or
                not isinstance(claim_generation, int) or claim_generation <= 0 or
                not isinstance(runtime_incarnation, str) or
                not _TOKEN.fullmatch(runtime_incarnation)):
            _fail("invalid", "job credential binding is malformed")
        path = Path(path).resolve(strict=False)
        if path.parent != self.credential_root or path.exists() or path.is_symlink():
            _fail("ownership-conflict", "job credential path is unavailable")
        with self.ledger._locked() as owner:
            # Credential bytes are part of the immutable CLI manifest, so
            # issuance precedes claim_source(manifest_digest). Authenticate
            # the managed owner and registered worktree now; the token remains
            # inert until __call__ sees this exact active source claim.
            identity = self.ledger.store.identity
            if (owner.get("coordinator_session_uuid") not in {None, parent_uuid} or
                    owner.get("mode") != "managed"):
                _fail("ownership-conflict", "job credential parent is outside managed owner")
            claims = [row for row in self.ledger.store._load_claims()
                      if row.get("state") == "active" and
                      row.get("coordinator_session_uuid") == parent_uuid and
                      row.get("owner_generation") == owner.get("generation") and
                      row.get("lane_key") == identity.lane_key and
                      row.get("host") == identity.host and
                      row.get("common_dir") == str(identity.common_dir)]
            lineages = {(row.get("lineage_id"), row.get("lineage_generation"))
                        for row in claims}
            if len(lineages) != 1:
                _fail("ownership-conflict", "job credential lacks one registered worktree lineage")
            lineage_id, lineage_generation = next(iter(lineages))
            self.ledger._registered_worktrees(
                lineage_id, lineage_generation, parent_uuid, owner["generation"])
            if self.ledger._path().exists():
                state = self.ledger._load(owner)
                current = state.get("current_claim")
                if claim_generation in state["retired_source_generations"]:
                    _fail("stale-generation", "job credential source generation is retired")
                if claim_generation not in {state["claim_generation"],
                                            state["claim_generation"] + 1}:
                    _fail("stale-generation", "job credential generation is not current or next")
                if isinstance(current, dict):
                    if current.get("parent_uuid") != parent_uuid:
                        _fail("ownership-conflict", "job credential parent conflicts with source")
                    if (current.get("claim_generation") == claim_generation and
                            current.get("runtime_incarnation") != runtime_incarnation):
                        _fail("ownership-conflict", "job credential runtime conflicts with source")
            elif claim_generation != 1:
                _fail("stale-generation", "first job credential must target first source generation")
            token = secrets.token_hex(32)
            digest = hashlib.sha256(bytes.fromhex(token)).hexdigest()
            registry = self.credential_root / (digest + ".grant.json")
            if path.exists() or path.is_symlink():
                _fail("ownership-conflict", "job credential path was filled during issuance")
            grant = {"token_digest": digest, "parent_uuid": parent_uuid,
                     "claim_generation": claim_generation,
                     "runtime_incarnation": runtime_incarnation}
            _atomic_json(registry, grant)
            _atomic_json(path, {"token": token, "parent_uuid": parent_uuid,
                                "claim_generation": claim_generation,
                                "runtime_incarnation": runtime_incarnation})
        return path

    def __call__(self, credential: Mapping[str, Any], method: str,
                 job_id: Optional[str]) -> None:
        if not isinstance(credential, Mapping) or set(credential) != {
                "token", "parent_uuid", "claim_generation", "runtime_incarnation"}:
            _fail("ownership-conflict", "job credential is malformed")
        token = credential.get("token")
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{64}", token):
            _fail("ownership-conflict", "job credential is malformed")
        if (isinstance(credential.get("claim_generation"), bool) or
                not isinstance(credential.get("claim_generation"), int)):
            _fail("ownership-conflict", "job credential generation is malformed")
        digest = hashlib.sha256(bytes.fromhex(token)).hexdigest()
        grant = _read_json(self.credential_root / (digest + ".grant.json"))
        if grant is None or not hmac.compare_digest(
                str(grant.get("token_digest", "")), digest):
            _fail("ownership-conflict", "job credential is not issued")
        if any(grant.get(key) != credential.get(key) for key in (
                "parent_uuid", "claim_generation", "runtime_incarnation")):
            _fail("ownership-conflict", "job credential binding changed")
        with self.ledger._locked() as owner:
            state = self.ledger._load(owner)
            current = state.get("current_claim")
            if (not isinstance(current, dict) or current.get("state") != "active" or
                    current.get("parent_uuid") != credential["parent_uuid"] or
                    current.get("claim_generation") != credential["claim_generation"] or
                    current.get("runtime_incarnation") != credential["runtime_incarnation"] or
                    credential["claim_generation"] in state["retired_source_generations"]):
                _fail("stale-generation", "job credential source generation is retired")
            if method != "start_job":
                job = state["jobs"].get(job_id)
                if (not isinstance(job, dict) or
                        job.get("parent_uuid") != current["parent_uuid"] or
                        job.get("lineage_id") != current["lineage_id"] or
                        job.get("lineage_generation") != current["lineage_generation"]):
                    _fail("ownership-conflict", "job is outside this source lineage")


class JobSupervisorService:
    """Supervisor-owned AF_UNIX tool endpoint; no runtime or owner verbs."""

    def __init__(self, socket_path: Path | str, runner: Any,
                 verify_credential: Callable[[Mapping[str, Any], str, Optional[str]], None]):
        self.socket_path = Path(socket_path)
        self.runner = runner
        if hasattr(runner.domain, "runner"):
            runner.domain.runner = runner
        self.verify_credential = verify_credential
        self._stopping = threading.Event()
        self._slots = threading.BoundedSemaphore(8)

    def stop(self) -> None:
        """Stop accepting requests in tests or supervisor shutdown.

        This does not signal, wait for, or cancel an admitted job worker.
        """
        self._stopping.set()

    def _handle(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        method = request.get("method")
        params = request.get("params")
        credential = request.get("credential")
        if method not in {"start_job", "job_status", "read_output", "wait_job", "cancel_job"} or not isinstance(params, dict) or not isinstance(credential, dict):
            _fail("invalid", "unsupported job tool request")
        job_id = params.get("job_id")
        self.verify_credential(credential, method, job_id)
        if method == "start_job":
            allowed = {"job_id", "request_id", "argv", "cwd", "environment", "resource_ids", "effects_scope"}
            if set(params) - allowed or not {"job_id", "request_id", "argv", "cwd"}.issubset(params):
                _fail("invalid", "unexpected job start parameter")
            request_digest = hashlib.sha256(_json_bytes({
                "method": method, "params": params,
                "parent_uuid": credential["parent_uuid"],
                "claim_generation": credential["claim_generation"],
            })).hexdigest()
            result = self.runner.start_job(
                job_id=job_id, request_id=params["request_id"],
                request_digest=request_digest,
                parent_uuid=credential["parent_uuid"],
                claim_generation=credential["claim_generation"],
                argv=params["argv"], cwd=params["cwd"],
                environment=params.get("environment"),
                resource_ids=params.get("resource_ids"),
                effects_scope=params.get("effects_scope", "unknown"),
            )
        elif method == "job_status":
            if set(params) != {"job_id"}:
                _fail("invalid", "unexpected job status parameter")
            # Finalize an already sealed worker result before asking the
            # runner's status path whether a process is still live.
            result = self.runner.wait_job(job_id, timeout=0)
            if result.get("state") == "running":
                try:
                    result = self.runner.status(job_id)
                except ManagedStateError as exc:
                    if exc.code != "uncertain-effect":
                        raise
                    # A result may have sealed between the two observations.
                    result = self.runner.wait_job(job_id, timeout=0)
                    if result.get("state") == "running":
                        raise
        elif method == "read_output":
            if set(params) - {"job_id", "offset", "limit_bytes"}:
                _fail("invalid", "unexpected output parameter")
            offset = params.get("offset", 0)
            limit = params.get("limit_bytes", 65536)
            if (isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or
                    isinstance(limit, bool) or not isinstance(limit, int) or not 0 < limit <= 65536):
                _fail("invalid", "output slice is outside its bound")
            record = self.runner._load_record(job_id)
            finalized = record["state"] in {"completed", "failed"}
            if finalized:
                data = self.runner.read_output(job_id)
            else:
                # Live bytes are a snapshot, not a completion or effect
                # witness. The final read always goes through result custody.
                fd = self.runner._open_output(record["output_ref"], create=False)
                try:
                    observed_size = min(os.fstat(fd).st_size,
                                        self.runner.output_limit_bytes + 1)
                    data = os.pread(fd, min(limit, max(0, observed_size - offset)), offset)
                finally:
                    os.close(fd)
                self.verify_credential(credential, method, job_id)
                return {"job_id": job_id, "offset": offset,
                        "observed_size": observed_size,
                        "observation_watermark_ns": time.monotonic_ns(),
                        "finalized": False, "eof": False,
                        "data_base64": base64.b64encode(data).decode("ascii")}
            chunk = data[offset:offset + limit]
            result = {"job_id": job_id, "offset": offset,
                      "total_bytes": len(data), "eof": offset + len(chunk) >= len(data),
                      "finalized": True, "output_digest": record["output_digest"],
                      "result_digest": record["result_digest"],
                      "data_base64": base64.b64encode(chunk).decode("ascii")}
        elif method == "wait_job":
            if set(params) - {"job_id", "timeout"} or "job_id" not in params:
                _fail("invalid", "unexpected wait parameter")
            result = self.runner.wait_job(job_id, timeout=params.get("timeout", 0))
        else:
            if set(params) != {"job_id", "cancel_id"}:
                _fail("invalid", "unexpected cancellation parameter")
            with self.runner.ledger._locked() as owner:
                state = self.runner.ledger._load(owner)
                current = state.get("current_claim")
                if (not isinstance(current, dict) or current.get("state") != "active" or
                        current.get("parent_uuid") != credential["parent_uuid"] or
                        current.get("claim_generation") != credential["claim_generation"] or
                        current.get("runtime_incarnation") != credential["runtime_incarnation"]):
                    _fail("stale-generation", "job cancellation source was fenced")
                record = self.runner._load_record_unlocked(job_id)
                identity = record.get("process_identity")
                if identity is None:
                    _fail("uncertain-effect", "job cancellation has no observed worker")
                result = self.runner.domain.request_cancel(
                    job_id=job_id, process_identity=identity,
                    cancel_id=params["cancel_id"],
                )
        if method in {"job_status", "read_output", "wait_job"}:
            self.verify_credential(credential, method, job_id)
            if ((method in {"job_status", "wait_job"} and
                 result.get("state") in {"completed", "failed"}) or
                    (method == "read_output" and result.get("finalized") is True)):
                # The runner's result is sealed, but only the independent job
                # witness may release the active ledger's reservation. Never
                # use a caller-supplied completion or a provisional output
                # slice as that witness.
                self.runner.ledger.observe_active_job(
                    job_id=job_id,
                    parent_uuid=credential["parent_uuid"],
                    claim_generation=credential["claim_generation"],
                    runtime_incarnation=credential["runtime_incarnation"],
                )
        return result

    def serve_forever(self) -> None:
        self.runner.domain.assert_ready()
        _private_dir(self.socket_path.parent)
        if len(os.fsencode(self.socket_path)) >= 100:
            _fail("invalid", "job supervisor socket path exceeds Unix bound")
        if self.socket_path.exists() or self.socket_path.is_symlink():
            _fail("ownership-conflict", "job supervisor socket already exists")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        server.listen(32)
        server.settimeout(0.2)
        try:
            while not self._stopping.is_set():
                try:
                    conn, _addr = server.accept()
                except socket.timeout:
                    continue
                if not self._slots.acquire(blocking=False):
                    with conn:
                        conn.send(_json_bytes({"ok": False, "error": {
                            "code": "busy", "message": "job supervisor request limit reached"}}))
                    continue
                threading.Thread(target=self._serve_one, args=(conn,), daemon=True).start()
        finally:
            server.close()
            self.socket_path.unlink(missing_ok=True)

    def _serve_one(self, conn: socket.socket) -> None:
        try:
            with conn:
                try:
                    conn.settimeout(10)
                    data = conn.recv(MAX_FRAME + 1)
                    if len(data) > MAX_FRAME:
                        _fail("invalid", "job tool request exceeds its bound")
                    request = json.loads(data)
                    if not isinstance(request, dict):
                        _fail("invalid", "job tool request is malformed")
                    response = {"ok": True, "result": self._handle(request)}
                except ManagedStateError as exc:
                    response = {"ok": False, "error": {"code": exc.code, "message": exc.message}}
                except Exception:
                    response = {"ok": False, "error": {"code": "uncertain-effect", "message": "job tool request outcome is uncertain"}}
                conn.send(_json_bytes(response))
        finally:
            self._slots.release()


def _call_supervisor(socket_path: Path, credential: Mapping[str, Any],
                     method: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as conn:
        wait = params.get("timeout", 0) if method == "wait_job" else 0
        if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not 0 <= wait <= 3600:
            _fail("invalid", "job wait timeout is outside its bound")
        conn.settimeout(10 + wait)
        conn.connect(str(socket_path))
        conn.send(_json_bytes({"credential": credential, "method": method,
                               "params": params}))
        raw = conn.recv(MAX_FRAME + 1)
    if len(raw) > MAX_FRAME:
        _fail("uncertain-effect", "job supervisor response exceeds its bound")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("ok") not in {True, False}:
        _fail("uncertain-effect", "job supervisor response is malformed")
    if value["ok"] is False:
        error = value.get("error", {})
        _fail(error.get("code", "uncertain-effect"), error.get("message", "job tool refused"))
    return value["result"]


_MCP_TOOLS = [
    {"name": "start_job", "description": "Start one persistent Linux command. Supply an absolute executable and exact argv; for shell syntax use /bin/sh with -lc and one command string. Job and request IDs are stable one-use keys. Declare effects_scope=local-worktree only for commands confined to the registered worktree, with no Git metadata or remote effects; otherwise omit it and effects remain unresolved until separately reconciled. The supervisor computes the request digest and reserves the registered working directory.",
     "inputSchema": {"type": "object", "required": ["job_id", "request_id", "argv", "cwd"],
                     "properties": {"job_id": {"type": "string"}, "request_id": {"type": "string"},
                                    "argv": {"type": "array", "items": {"type": "string"}},
                                    "cwd": {"type": "string"}, "environment": {"type": "object"},
                                    "resource_ids": {"type": "array", "items": {"type": "string"}},
                                    "effects_scope": {"type": "string", "enum": ["unknown", "local-worktree"]}}}},
    {"name": "job_status", "description": "Read an existing job state without relaunching it.",
     "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}}},
    {"name": "read_output", "description": "Read a bounded output slice as base64. A live slice is provisional; only finalized output has a result digest.",
     "inputSchema": {"type": "object", "required": ["job_id"],
                     "properties": {"job_id": {"type": "string"}, "offset": {"type": "integer", "minimum": 0},
                                    "limit_bytes": {"type": "integer", "minimum": 1, "maximum": 65536}}}},
    {"name": "wait_job", "description": "Wait up to a bounded number of seconds for an existing job.",
     "inputSchema": {"type": "object", "required": ["job_id"],
                     "properties": {"job_id": {"type": "string"}, "timeout": {"type": "number", "minimum": 0, "maximum": 3600}}}},
    {"name": "cancel_job", "description": "Request cancellation of one existing job by a one-use cancellation ID. Observe its result separately.",
     "inputSchema": {"type": "object", "required": ["job_id", "cancel_id"],
                     "properties": {"job_id": {"type": "string"}, "cancel_id": {"type": "string"}}}},
]


def mcp_stdio(socket_path: Path | str, credential_file: Path | str) -> None:
    """Run an MCP stdio bridge. It has no owner/runtime control method."""
    socket_path = Path(socket_path)
    credential_file = Path(credential_file)
    while True:
        line = sys.stdin.buffer.readline(MAX_MCP_LINE + 1)
        if not line:
            return
        if len(line) > MAX_MCP_LINE:
            return
        request = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                continue
            request_id = request.get("id")
            method = request.get("method")
            if request_id is None:
                continue
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                          "serverInfo": {"name": "lane-managed-jobs", "version": "1"}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": _MCP_TOOLS}
            elif method == "tools/call":
                params = request.get("params", {})
                name = params.get("name")
                arguments = params.get("arguments", {})
                if name not in {tool["name"] for tool in _MCP_TOOLS} or not isinstance(arguments, dict):
                    _fail("invalid", "unknown managed job tool")
                value = _call_supervisor(socket_path, _credential(credential_file),
                                         name, arguments)
                result = {"content": [{"type": "text", "text": json.dumps(value, sort_keys=True)}]}
            else:
                _fail("invalid", "unsupported MCP method")
            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except ManagedStateError as exc:
            response = {"jsonrpc": "2.0", "id": request.get("id"),
                        "error": {"code": -32000, "message": "%s: %s" % (exc.code, exc.message)}}
        except Exception:
            response = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                        "error": {"code": -32001, "message": "managed job tool failed"}}
        sys.stdout.buffer.write(_json_bytes(response) + b"\n")
        sys.stdout.buffer.flush()


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 3 and args[0] == "mcp":
        mcp_stdio(args[1], args[2])
        return 0
    if len(args) == 7 and args[0] == "_worker":
        return _worker(int(args[1]), int(args[2]), Path(args[3]),
                       args[4], args[5], args[6])
    print("usage: lane_managed_local_jobs.py mcp SOCKET CREDENTIAL_FILE", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
