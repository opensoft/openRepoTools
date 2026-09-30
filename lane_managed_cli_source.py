# SPDX-License-Identifier: Apache-2.0
"""Per-session Linux source custodian for the shared-container CLI capability.

The custodian is a *single-threaded* child subreaper.  It starts exactly one
Claude CLI after a durable spawn intent, then reaps every descendant, including
clone children which do not deliver SIGCHLD.  It never launches persistent jobs
or a target CLI.  A drained answer is meaningful only while this same custodian
is alive and answering fresh challenges.
"""

from __future__ import annotations

import ctypes
import base64
import errno
import fcntl
import hashlib
import json
import os
import pty
import re
import secrets
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


_PR_SET_CHILD_SUBREAPER = 36
_PR_GET_CHILD_SUBREAPER = 37
_WAIT_ALL = 0x40000000  # Linux __WALL: also wait for non-SIGCHLD clone children.
_MAX_MESSAGE = 128 * 1024
_RECENT_EVENTS = 128
_MAX_TTY_BUFFER = 1024 * 1024
_MAX_PTY_PUMP_BYTES = 256 * 1024
_CLI_TITLE = re.compile(
    rb"Claude(?:[ \t]|\x1b\[[0-?]*[ -/]*[@-~])*Code"
    rb"(?:[ \t]|\x1b\[[0-?]*[ -/]*[@-~])*v2\.1\.283"
)
_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_OSC = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")


def _screen_compact(data: bytes) -> str:
    text = data.decode("utf-8", "replace")
    return re.sub(r"\s+", "", _OSC.sub("", _CSI.sub("", text)))


def _socket_path(directory: Path) -> Path:
    """Short, owner-private socket name bound to the full durable directory."""
    if not directory.is_absolute():
        raise SourceCustodyError("custodian socket identity is not absolute")
    root = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / (
        "openrepotools-cli-%d" % os.getuid())
    if root.is_symlink():
        raise SourceCustodyError("custodian socket root is linked")
    root.mkdir(mode=0o700, exist_ok=True)
    if root.resolve(strict=True) != root or root.stat().st_mode & 0o077:
        raise SourceCustodyError("custodian socket root is not owner-private")
    path = root / (_digest(str(directory))[:32] + ".sock")
    if len(str(path).encode("utf-8")) >= 108:
        raise SourceCustodyError("custodian socket path exceeds AF_UNIX bound")
    return path


class SourceCustodyError(RuntimeError):
    """The source boundary has not supplied an authoritative observation."""


class MonotonicWitnessSequence:
    """One strictly increasing observation clock shared by all witnesses."""

    def __init__(self, initial: int = 0):
        if isinstance(initial, bool) or not isinstance(initial, int) or initial < 0:
            raise SourceCustodyError("observation sequence initial value is malformed")
        self._last = initial
        self._lock = threading.Lock()

    def next(self, floor: int) -> int:
        if isinstance(floor, bool) or not isinstance(floor, int) or floor < 0:
            raise SourceCustodyError("observation sequence floor is malformed")
        with self._lock:
            self._last = max(self._last + 1, floor + 1, time.monotonic_ns())
            return self._last


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def auth_account_digest(manifest: Mapping[str, Any], expected_email: str) -> str:
    """Read the pinned CLI's scoped account identity without a model request.

    The observation is intentionally made only after a target release.  It
    proves local auth binding, while a later authenticated model response is
    still required to establish that the selected seat can serve requests.
    """
    from lane_managed_cli_runtime import validate_runtime_launch
    launch = validate_runtime_launch(manifest)
    try:
        result = subprocess.run(
            [launch["cli_executable"], "auth", "status", "--json"],
            cwd=launch["cwd"], env=launch["environment"],
            capture_output=True, timeout=10, check=False,
        )
        if result.returncode != 0 or len(result.stdout) > 65536:
            raise SourceCustodyError("bound target profile is not authenticated")
        status = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise SourceCustodyError("target account status is unavailable") from exc
    if (not isinstance(expected_email, str) or not expected_email or
            not isinstance(status, dict) or status.get("loggedIn") is not True or
            not isinstance(status.get("email"), str) or
            status["email"].casefold() != expected_email.casefold()):
        raise SourceCustodyError("bound target profile is not logged in")
    stable = {key: status[key] for key in (
        "email", "accountId", "userId", "organizationId", "orgId",
        "authMethod", "apiProvider",
    ) if isinstance(status.get(key), str) and status[key]}
    if not any(key in stable for key in (
            "email", "accountId", "userId", "organizationId", "orgId")):
        raise SourceCustodyError("target account status lacks a stable identity")
    return _digest({"loggedIn": True, "identity": stable})


def _identity(pid: int) -> Dict[str, Any]:
    """Read a non-reused Linux process identity in this PID namespace."""
    try:
        raw = Path("/proc/%d/stat" % pid).read_text(encoding="ascii")
        fields = raw[raw.rindex(")") + 2:].split()
        start_ticks = int(fields[19])  # stat field 22; fields start at field 3.
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        namespace = os.readlink("/proc/%d/ns/pid" % pid)
    except (OSError, ValueError, IndexError) as exc:
        raise SourceCustodyError("process identity is unreadable") from exc
    return {"pid": pid, "start_token": "%s:%s:%d" % (boot, namespace, start_ticks),
            "boot_id": boot, "pid_namespace": namespace}


def _subreaper(enabled: Optional[bool] = None) -> bool:
    libc = ctypes.CDLL(None, use_errno=True)
    if enabled is not None and libc.prctl(_PR_SET_CHILD_SUBREAPER,
                                         int(enabled), 0, 0, 0) != 0:
        raise SourceCustodyError("PR_SET_CHILD_SUBREAPER failed: %d" % ctypes.get_errno())
    result = ctypes.c_int()
    if libc.prctl(_PR_GET_CHILD_SUBREAPER, ctypes.byref(result), 0, 0, 0) != 0:
        raise SourceCustodyError("PR_GET_CHILD_SUBREAPER failed: %d" % ctypes.get_errno())
    return result.value == 1


def _write_durable(path: Path, value: Mapping[str, Any]) -> None:
    encoded = _canonical(value) + b"\n"
    if len(encoded) > 1024 * 1024:
        raise SourceCustodyError("source custody journal exceeds size bound")
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(8))
    fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(str(temporary), str(path))
        directory_fd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _receive(connection: socket.socket, *, deadline: Optional[float] = None) -> Mapping[str, Any]:
    data = bytearray()
    while len(data) <= _MAX_MESSAGE:
        remaining = 3.0 if deadline is None else min(3.0, deadline - time.monotonic())
        if remaining <= 0:
            raise SourceCustodyError("custodian request deadline exceeded")
        connection.settimeout(remaining)
        chunk = connection.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in chunk:
            break
    if len(data) > _MAX_MESSAGE or not data.endswith(b"\n"):
        raise SourceCustodyError("custodian request is malformed or too large")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise SourceCustodyError("custodian request is malformed")
    return value


def _reply(connection: socket.socket, value: Mapping[str, Any]) -> None:
    connection.sendall(_canonical(value) + b"\n")


class _Custodian:
    def __init__(self, directory: Path, credential_fd: int):
        if sys.platform != "linux":
            raise SourceCustodyError("session subreaper requires Linux")
        if not directory.is_dir() or directory.is_symlink():
            raise SourceCustodyError("custodian directory is absent or linked")
        mode = directory.stat().st_mode & 0o777
        if mode & 0o077:
            raise SourceCustodyError("custodian directory is not owner-private")
        credential = os.read(credential_fd, 4096)
        os.close(credential_fd)
        if len(credential) != 64 or any(item not in b"0123456789abcdef" for item in credential):
            raise SourceCustodyError("custodian credential is malformed")
        self.credential = credential.decode("ascii")
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        if not _subreaper(True):
            raise SourceCustodyError("source child subreaper was not enabled")
        self.directory = directory
        self.journal_path = directory / "custodian.json"
        self.socket_path = _socket_path(directory)
        self.identity = _identity(os.getpid())
        self.pty_master, self.pty_slave = pty.openpty()
        os.set_blocking(self.pty_master, False)
        self.record: Dict[str, Any] = {
            "schema": 1, "custodian": self.identity, "phase": "waiting",
            "source": None, "source_exit": None, "spawn_intent_digest": None,
            "sequence": 0, "events": [], "drained": False,
            "event_count": 0, "event_chain_digest": "0" * 64,
            "launch_intent": None, "exit_requested": False,
            "exit_dispatched": False, "exit_dispatch_intent": False,
            "turn_sequence": 0, "submission_pending": False, "turn_busy": False,
            "turn_event_digest": None,
            "turn_begin_digest": None,
            "turn_start_tick": None, "stop_begin": None,
            "session_started": False,
            "session_start": None,
            "startup_trust_state": "awaiting",
            "model_input_admitted": False,
        }
        self.exit_due: Optional[float] = None
        self.prompt_ready = False
        self.main_ui_seen = False
        self.main_prompt_seen = False
        self.prompt_tail = b""
        self.trust_tail = b""
        self.trust_offered_at = None
        self.trust_navigation_tail = b""
        self.trust_key_buffer = b""
        self.input_line = bytearray()
        self.input_clean = False
        self.clean_epoch_pending = False
        self.output_buffer = bytearray()
        self.output_dropped = 0
        self.pty_eof = False
        self.record["integrity_digest"] = _digest(self.record)
        _write_durable(self.journal_path, self.record)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        self.server.listen(8)
        self.server.setblocking(False)

    def _check_journal(self) -> None:
        try:
            if self.journal_path.is_symlink() or self.journal_path.stat().st_mode & 0o077:
                raise SourceCustodyError("custodian journal is not owner-private")
            raw = self.journal_path.read_bytes()
            if len(raw) > 1024 * 1024:
                raise SourceCustodyError("custodian journal exceeds its bound")
            disk = json.loads(raw)
        except (OSError, ValueError) as exc:
            raise SourceCustodyError("custodian journal is unreadable") from exc
        expected = _digest({key: item for key, item in self.record.items()
                            if key != "integrity_digest"})
        if disk != self.record or disk.get("integrity_digest") != expected:
            raise SourceCustodyError("custodian durable journal changed or was lost")

    def _record(self, **changes: Any) -> None:
        self.record.update(changes)
        self.record["sequence"] += 1
        self.record["integrity_digest"] = _digest({
            key: value for key, value in self.record.items() if key != "integrity_digest"
        })
        _write_durable(self.journal_path, self.record)

    def _reap(self) -> None:
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG | _WAIT_ALL)
            except InterruptedError:
                continue
            except ChildProcessError:
                if self.record["source"] is not None and self.record["source_exit"] is not None:
                    if not self.record["drained"]:
                        self._record(phase="drained", drained=True)
                return
            if pid == 0:
                return
            event = {"pid": pid, "status": status,
                     "exited": os.WIFEXITED(status), "signaled": os.WIFSIGNALED(status)}
            events = list(self.record["events"])
            events.append(event)
            changes: Dict[str, Any] = {
                "events": events[-_RECENT_EVENTS:],
                "event_count": self.record["event_count"] + 1,
                "event_chain_digest": _digest({
                    "previous": self.record["event_chain_digest"], "event": event,
                    "count": self.record["event_count"] + 1,
                }),
            }
            source = self.record["source"]
            if source is not None and pid == source["pid"] and self.record["source_exit"] is None:
                changes["source_exit"] = event
                changes["phase"] = "source-exited"
            self._record(**changes)

    def _start(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        if self.record["phase"] != "waiting":
            raise SourceCustodyError("custodian source admission is already consumed")
        argv = request.get("argv")
        env = request.get("environment")
        cwd = request.get("cwd")
        intent = request.get("intent")
        if (not isinstance(argv, list) or not argv or len(argv) > 128 or
                any(not isinstance(x, str) or not x or "\x00" in x for x in argv) or
                not isinstance(env, dict) or len(env) > 128 or
                any(not isinstance(k, str) or not isinstance(v, str) or
                    "\x00" in k or "\x00" in v for k, v in env.items()) or
                not isinstance(cwd, str) or not Path(cwd).is_dir() or
                not isinstance(intent, dict) or not isinstance(intent.get("digest"), str)):
            raise SourceCustodyError("source launch request is malformed")
        # This record precedes fork.  Any failure after it remains uncertain;
        # no retry path exists in this custodian.
        if intent.get("cwd") not in (None, cwd):
            raise SourceCustodyError("source launch intent working directory changed")
        self._record(phase="spawn-intent", spawn_intent_digest=intent["digest"],
                     launch_intent={**intent, "cwd": cwd})
        gate_read, gate_write = os.pipe()
        try:
            pid = os.fork()
            if pid == 0:
                try:
                    os.close(gate_write)
                    os.close(self.pty_master)
                    for target_fd in (0, 1, 2):
                        os.dup2(self.pty_slave, target_fd)
                    if self.pty_slave > 2:
                        os.close(self.pty_slave)
                    allowed = os.read(gate_read, 1)
                    os.close(gate_read)
                    if allowed != b"1":
                        os._exit(127)
                    # The wrapper has no controlling terminal.  If an admitted
                    # PTY is supplied as stdio, the CLI alone acquires it.
                    os.setsid()
                    if os.isatty(0):
                        import termios
                        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
                    os.chdir(cwd)
                    os.execvpe(argv[0], argv, env)
                except BaseException:
                    os._exit(127)
            os.close(gate_read)
            os.close(self.pty_slave)
            source = _identity(pid)
            # Identity is durable before releasing the child into exec.
            self._record(phase="running", source=source,
                         model_input_admitted="launch_intent_id" not in intent)
            os.write(gate_write, b"1")
            return {"source": source, "custodian": self.identity,
                    "sequence": self.record["sequence"],
                    "journal_digest": self.record["integrity_digest"]}
        finally:
            os.close(gate_write)

    def _pump_pty(self) -> None:
        if self.pty_eof:
            return
        remaining = _MAX_PTY_PUMP_BYTES
        while remaining > 0:
            try:
                data = os.read(self.pty_master, min(32768, remaining))
            except BlockingIOError:
                return
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
                # PTY EIO is only terminal I/O state; waitpid remains the
                # sole source-exit and subtree-drain authority.
                self.pty_eof = True
                return
            if not data:
                self.pty_eof = True
                return
            remaining -= len(data)
            self.output_buffer.extend(data)
            if len(self.output_buffer) > _MAX_TTY_BUFFER:
                excess = len(self.output_buffer) - _MAX_TTY_BUFFER
                del self.output_buffer[:excess]
                self.output_dropped += excess
            combined = self.prompt_tail + data
            if not self.record["session_started"] and self.record["startup_trust_state"] == "awaiting":
                self.trust_tail = (self.trust_tail + data)[-16384:]
                screen = _screen_compact(self.trust_tail)
                cwd = self.record["launch_intent"].get("cwd", "")
                latest = screen.rsplit("Accessingworkspace:", 1)[-1]
                if ("Accessingworkspace:" in screen and
                        latest.startswith(_screen_compact(cwd.encode("utf-8"))) and
                        "Quicksafetycheck:Isthisaprojectyoucreatedoroneyoutrust?" in latest and
                        "Yes,Itrustthisfolder" in latest and "No,exit" in latest and
                        "❯No,exit" in latest):
                    self.trust_offered_at = time.monotonic()
                    self._record(startup_trust_state="offered")
            elif self.record["startup_trust_state"] in {"navigation-pending", "confirm-selected"}:
                self.trust_navigation_tail = (self.trust_navigation_tail + data)[-8192:]
                compact = _screen_compact(self.trust_navigation_tail)
                selected = compact.rsplit("❯", 1)[-1] if "❯" in compact else ""
                if selected.startswith("No,exit"):
                    self._record(startup_trust_state="selection-lost")
                elif (selected.startswith("Yes,Itrustthisfolder") and
                      not self.trust_navigation_tail.endswith((b"\xe2", b"\xe2\x9d"))):
                    if self.record["startup_trust_state"] != "confirm-selected":
                        self._record(startup_trust_state="confirm-selected")
                elif self.record["startup_trust_state"] == "confirm-selected":
                    # A newer, incomplete selector is not evidence that Yes
                    # remains focused. Wait for its complete last value.
                    self._record(startup_trust_state="navigation-pending")
            title = _CLI_TITLE.search(combined) if not self.main_ui_seen else None
            if title is not None:
                self.main_ui_seen = True
            prompt_region = combined[title.end():] if title is not None else combined
            self.prompt_tail = combined[-256:]
            if (b"\xe2\x9d\xaf" in prompt_region and self.main_ui_seen and
                    not self.record["exit_requested"]):
                self.main_prompt_seen = True
            if (self.main_prompt_seen and self.record["session_started"] and
                    not self.record["turn_busy"] and
                    not self.record["submission_pending"] and
                    not self.record["exit_requested"]):
                # This is an input-routing hint only.  It is never source
                # exclusion or evidence that a model task has completed.
                if self.clean_epoch_pending:
                    self.input_clean = True
                    self.input_line.clear()
                    self.clean_epoch_pending = False
                if self.input_clean and not self.input_line:
                    self.prompt_ready = True

    def _tty_read(self) -> Dict[str, Any]:
        self._pump_pty()
        prefix = b""
        if self.output_dropped:
            prefix = ("\r\n[managed terminal skipped %d earlier output bytes]\r\n" %
                      self.output_dropped).encode("ascii")
            self.output_dropped = 0
        budget = max(0, 32768 - len(prefix))
        data = prefix + bytes(self.output_buffer[:budget])
        del self.output_buffer[:budget]
        return {"data": base64.b64encode(data).decode("ascii"),
                "source_exited": self.record["source_exit"] is not None}

    def _tty_write(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        intent = self.record["launch_intent"]
        if (self.record["phase"] != "running" or self.record["exit_requested"] or
                self.record["turn_busy"] or self.record["submission_pending"]):
            raise SourceCustodyError("source input is fenced or source is no longer running")
        value = request.get("data")
        if not isinstance(value, str) or len(value) > 65536:
            raise SourceCustodyError("source input frame is malformed")
        try:
            data = base64.b64decode(value, validate=True)
        except ValueError as exc:
            raise SourceCustodyError("source input is not base64") from exc
        if len(data) > 32768:
            raise SourceCustodyError("source input frame exceeds its bound")
        if not self.record["session_started"]:
            state = self.record["startup_trust_state"]
            candidate = self.trust_key_buffer + data
            if state == "offered" and b"\x1b[B".startswith(candidate):
                if candidate != b"\x1b[B":
                    self.trust_key_buffer = candidate
                    return {"written": len(data)}
                self.trust_key_buffer = b""
                if self.trust_offered_at is None:
                    raise SourceCustodyError("trust dialog timing is unavailable")
                remaining = .25 - (time.monotonic() - self.trust_offered_at)
                if remaining > 0:
                    time.sleep(remaining)
                self._pump_pty()
                self._reap()
                if (self.record["startup_trust_state"] != "offered" or
                        self.record["source_exit"] is not None):
                    raise SourceCustodyError("trust dialog changed during settling")
                self.trust_navigation_tail = b""
                self._record(startup_trust_state="navigation-pending")
                size = os.write(self.pty_master, candidate)
                if size != len(candidate):
                    raise SourceCustodyError("trust navigation write was incomplete")
                return {"written": len(data)}
            if state == "confirm-selected" and not self.trust_key_buffer and data in (b"\r", b"\n"):
                self._pump_pty()
                self._reap()
                if (self.record["startup_trust_state"] != "confirm-selected" or
                        self.record["source_exit"] is not None):
                    raise SourceCustodyError("trust selection changed before acceptance")
                # Consume this one grant before writing; old screen bytes can
                # never authorize a second startup input transaction.
                self._record(startup_trust_state="submitted")
                size = os.write(self.pty_master, data)
                if size != len(data):
                    raise SourceCustodyError("trust acceptance write was incomplete")
                return {"written": len(data)}
            raise SourceCustodyError("only the exact first trust dialog can receive startup input")
        if (not self.record["model_input_admitted"] or
                (isinstance(intent, dict) and intent.get("operation_id") is not None)):
            raise SourceCustodyError("source input is fenced or source is no longer running")
        if data:
            self.clean_epoch_pending = False
        newline_count = data.count(b"\r") + data.count(b"\n")
        if newline_count > 1 or (newline_count == 1 and data[-1:] not in (b"\r", b"\n")):
            self.input_clean = False
            raise SourceCustodyError("terminal frame contains multiple or mixed submissions")
        if newline_count:
            if self.input_clean and not self.input_line and len(data) == 1:
                # An empty Enter is a local no-op.  Native UI may contain
                # prefilled text that tty bytes alone cannot attest to.
                return {"written": 1}
            self.prompt_ready = False
            # No prompt repaint clears this fence.  Only an authenticated
            # UserPromptSubmit begin followed by its exact Stop can do so.
            self._record(turn_sequence=self.record["turn_sequence"] + 1,
                         submission_pending=True, turn_busy=False,
                         turn_event_digest=None, turn_begin_digest=None,
                         turn_start_tick=self._boot_tick(), stop_begin=None)
            self.prompt_ready = False
            self.main_prompt_seen = False
            self.prompt_tail = b""
            self.input_clean = False
            self.input_line.clear()
            # A hook fork in the same Linux clock tick as this durable
            # snapshot cannot prove it was born after submission.  Hold the
            # CR until a later tick, without weakening the strict peer fence.
            deadline = time.monotonic() + 0.25
            while self._boot_tick() <= self.record["turn_start_tick"]:
                if time.monotonic() >= deadline:
                    raise SourceCustodyError("submission tick did not advance")
                time.sleep(0.001)
        elif self.input_clean:
            if all(32 <= byte < 127 for byte in data) and len(self.input_line) + len(data) <= 4096:
                self.input_line.extend(data)
            else:
                self.input_clean = False
        if data:
            self.prompt_ready = False
        size = os.write(self.pty_master, data)
        if size != len(data):
            raise SourceCustodyError("source input write was incomplete")
        return {"written": size}

    @staticmethod
    def _boot_tick() -> int:
        return int(time.clock_gettime(time.CLOCK_BOOTTIME) * os.sysconf("SC_CLK_TCK"))

    def _session_start(self, request: Mapping[str, Any], peer_pid: int) -> Dict[str, Any]:
        event = request.get("event")
        intent = self.record["launch_intent"]
        if (self.record["phase"] != "running" or self.record["session_started"] or
                not isinstance(event, dict) or not isinstance(intent, dict) or
                self.record["startup_trust_state"] not in {"awaiting", "submitted"} or
                event.get("hook_event_name") != "SessionStart" or
                event.get("session_id") != intent.get("parent_uuid") or
                not isinstance(event.get("source"), str) or
                not isinstance(event.get("cwd"), str) or
                not isinstance(event.get("transcript_path"), str) or
                (intent.get("cwd") is not None and event.get("cwd") != intent["cwd"]) or
                not self._source_descendant(peer_pid)):
            raise SourceCustodyError("SessionStart is not this source's first parent event")
        self._record(session_started=True, session_start={
            "event_digest": _digest(event), "source": event["source"],
            "cwd": event["cwd"], "transcript_path": event["transcript_path"],
            "peer": _identity(peer_pid),
        }, startup_trust_state="complete")
        self.clean_epoch_pending = True
        if (self.main_prompt_seen and not self.record["turn_busy"] and
                not self.record["submission_pending"] and not self.record["exit_requested"]):
            # The pinned CLI may draw its idle prompt just before its
            # SessionStart hook reaches this custodian.  Reuse only the
            # title-qualified prompt already seen in that same PTY.
            self.prompt_ready = True
            self.input_clean = True
            self.input_line.clear()
            self.clean_epoch_pending = False
        return {"session_started": True}

    def _prompt_begin(self, request: Mapping[str, Any], peer_pid: int) -> Dict[str, Any]:
        event = request.get("event")
        intent = self.record["launch_intent"]
        started = self.record["session_start"]
        if (self.record["phase"] != "running" or
                not self.record["session_started"] or
                not self.record["model_input_admitted"] or
                not self.record["submission_pending"] or self.record["turn_busy"] or
                self.record["exit_requested"] or self.record["source_exit"] is not None or
                not isinstance(event, dict) or not isinstance(intent, dict) or
                not isinstance(started, dict) or intent.get("operation_id") is not None or
                event.get("hook_event_name") != "UserPromptSubmit" or
                event.get("session_id") != intent.get("parent_uuid") or
                event.get("cwd") != started.get("cwd") or
                event.get("transcript_path") != started.get("transcript_path") or
                "agent_id" in event or not self._source_descendant(peer_pid)):
            raise SourceCustodyError("parent prompt was not admitted")
        identity = _identity(peer_pid)
        tick = int(identity["start_token"].rsplit(":", 1)[1])
        if tick <= self.record["turn_start_tick"]:
            raise SourceCustodyError("parent prompt callback predates submitted input")
        digest = _digest({"event": event, "turn_sequence": self.record["turn_sequence"],
                          "source": self.record["source"]})
        self._record(submission_pending=False, turn_busy=True,
                     turn_begin_digest=digest)
        return {"turn_sequence": self.record["turn_sequence"], "begin_digest": digest}

    def _activate_input(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        intent = self.record["launch_intent"]
        if (not isinstance(intent, dict) or not isinstance(intent.get("launch_intent_id"), str) or
                self.record["phase"] != "running" or not self.record["session_started"] or
                self.record["source_exit"] is not None or
                intent.get("operation_id") is not None or
                any(request.get(key) != intent.get(key) for key in
                    ("parent_uuid", "runtime_id", "launch_intent_id", "manifest_digest"))):
            raise SourceCustodyError("target input activation does not match observed launch")
        if not self.record["model_input_admitted"]:
            self._record(model_input_admitted=True)
        return {"model_input_admitted": True}

    def _stop_begin(self, peer_pid: int) -> Dict[str, Any]:
        if (self.record["phase"] != "running" or not self.record["turn_busy"] or
                self.record["stop_begin"] is not None or
                not self._source_descendant(peer_pid)):
            raise SourceCustodyError("Stop callback cannot bind this parent turn")
        identity = _identity(peer_pid)
        start_tick = int(identity["start_token"].rsplit(":", 1)[1])
        if start_tick <= self.record["turn_start_tick"]:
            raise SourceCustodyError("Stop callback predates submitted turn")
        ticket = secrets.token_hex(32)
        self._record(stop_begin={"ticket_digest": hashlib.sha256(ticket.encode()).hexdigest(),
                                 "peer": identity, "turn_sequence": self.record["turn_sequence"]})
        return {"ticket": ticket, "turn_sequence": self.record["turn_sequence"]}

    def _stop_event(self, request: Mapping[str, Any], peer_pid: int) -> Dict[str, Any]:
        event = request.get("event")
        intent = self.record["launch_intent"]
        begun = self.record["stop_begin"]
        if (self.record["phase"] != "running" or not self.record["turn_busy"] or
                not isinstance(intent, dict) or not isinstance(event, dict) or
                not isinstance(begun, dict) or
                request.get("turn_sequence") != begun.get("turn_sequence") or
                request.get("turn_sequence") != self.record["turn_sequence"] or
                not isinstance(request.get("ticket"), str) or
                hashlib.sha256(request["ticket"].encode()).hexdigest() != begun.get("ticket_digest") or
                _identity(peer_pid) != begun.get("peer") or
                event.get("hook_event_name") not in {"Stop", "StopFailure"} or
                event.get("session_id") != intent.get("parent_uuid") or
                "agent_id" in event or
                (event.get("hook_event_name") == "Stop" and
                 (event.get("background_tasks") != [] or event.get("session_crons") != [] or
                  event.get("stop_hook_active") is not False)) or
                not self._source_descendant(peer_pid)):
            raise SourceCustodyError("Stop observation is not this source's settled parent turn")
        digest = _digest({"event": event, "turn_sequence": self.record["turn_sequence"],
                          "source": self.record["source"]})
        self._record(turn_busy=False, submission_pending=False,
                     turn_event_digest=digest, stop_begin=None)
        self.clean_epoch_pending = True
        if (self.main_prompt_seen and self.record["session_started"] and
                not self.record["exit_requested"]):
            # A completed turn can draw its next prompt before the exact Stop
            # callback reaches us.  The prompt alone never settles the turn;
            # this authenticated Stop ticket does.
            self.prompt_ready = True
            self.input_clean = True
            self.input_line.clear()
            self.clean_epoch_pending = False
        return {"turn_sequence": self.record["turn_sequence"],
                "event_digest": digest}

    def _source_descendant(self, pid: int) -> bool:
        source = self.record["source"]
        if source is None:
            return False
        for _ in range(64):
            if pid == source["pid"]:
                return True
            if pid in {0, 1, os.getpid()}:
                return False
            try:
                raw = Path("/proc/%d/stat" % pid).read_text(encoding="ascii")
                fields = raw[raw.rindex(")") + 2:].split()
                pid = int(fields[1])  # ppid is stat field 4, index 1 after comm.
            except (OSError, ValueError, IndexError):
                return False
        return False

    def _tty_resize(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        rows, columns = request.get("rows"), request.get("columns")
        if (isinstance(rows, bool) or isinstance(columns, bool) or
                not isinstance(rows, int) or not isinstance(columns, int) or
                not 10 <= rows <= 500 or not 20 <= columns <= 1000):
            raise SourceCustodyError("terminal dimensions are outside the supported bound")
        import termios
        fcntl.ioctl(self.pty_master, termios.TIOCSWINSZ,
                    struct.pack("HHHH", rows, columns, 0, 0))
        return {"rows": rows, "columns": columns}

    def _request_exit(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        # The caller is the exact scoped slash hook after the supervisor has
        # persisted its source-generation fence.  A second request is a read
        # of the same decision, never another input injection.
        intent = self.record["launch_intent"]
        if (self.record["phase"] != "running" or not self.prompt_ready or
                self.record["turn_busy"] or self.record["submission_pending"] or
                not self.input_clean or self.input_line or
                not isinstance(intent, dict) or
                request.get("parent_uuid") != intent.get("parent_uuid") or
                request.get("runtime_id") != intent.get("runtime_id") or
                request.get("operation_id") != intent.get("operation_id") or
                not isinstance(request.get("operation_id"), str)):
            raise SourceCustodyError("exit request does not match the fenced source")
        if self.record["exit_requested"]:
            return {"requested": True, "dispatched": self.record["exit_dispatched"]}
        self._record(exit_requested=True)
        # The owned attach proxy held the literal /swap input; Claude never
        # received it.  The last observed CLI UI frame showed the idle prompt.
        # This hint authorizes only an attempt at supported /exit; source exit
        # and final ECHILD remain separate mandatory witnesses.
        self.exit_due = time.monotonic()
        return {"requested": True, "dispatched": False}

    def _fence(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        intent = self.record["launch_intent"]
        operation_id = request.get("operation_id")
        if (self.record["phase"] not in {"running", "source-exited", "drained"} or
                not isinstance(intent, dict) or
                not isinstance(operation_id, str) or not operation_id or
                request.get("parent_uuid") != intent.get("parent_uuid") or
                request.get("runtime_id") != intent.get("runtime_id")):
            raise SourceCustodyError("source fence request does not match running source")
        if intent.get("operation_id") is not None:
            if intent["operation_id"] != operation_id:
                raise SourceCustodyError("source fence operation changed")
            return {"fenced": True, "operation_id": operation_id}
        changed = dict(intent)
        changed["operation_id"] = operation_id
        self._record(launch_intent=changed)
        return {"fenced": True, "operation_id": operation_id}

    def _dispatch_exit_if_due(self) -> None:
        if self.exit_due is None or time.monotonic() < self.exit_due:
            return
        self.exit_due = None
        if self.record["source_exit"] is not None:
            return
        self._record(exit_dispatch_intent=True)
        try:
            size = os.write(self.pty_master, b"/exit\r")
        except OSError as exc:
            self._record(phase="uncertain")
            raise SourceCustodyError("supported CLI exit input failed") from exc
        if size != 6:
            self._record(phase="uncertain")
            raise SourceCustodyError("supported CLI exit input was incomplete")
        self._record(exit_dispatched=True)

    def _challenge(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        nonce = request.get("nonce")
        if not isinstance(nonce, str) or len(nonce) < 16 or len(nonce) > 128:
            raise SourceCustodyError("fresh challenge nonce is malformed")
        self._check_journal()
        self._reap()
        self._check_journal()
        subreaper = _subreaper()
        if not subreaper or _identity(os.getpid()) != self.identity:
            raise SourceCustodyError("custodian identity or subreaper state changed")
        return {"nonce": nonce, "custodian": self.identity,
                "source": self.record["source"],
                "source_exit": self.record["source_exit"],
                "launch_intent": self.record["launch_intent"],
                "drained": self.record["drained"],
                "prompt_ready": self.prompt_ready,
                "clean_empty_line": self.input_clean and not self.input_line,
                "turn_busy": self.record["turn_busy"],
                "submission_pending": self.record["submission_pending"],
                "model_input_admitted": self.record["model_input_admitted"],
                "startup_trust_state": self.record["startup_trust_state"],
                "turn_sequence": self.record["turn_sequence"],
                "session_start": self.record["session_start"],
                "phase": self.record["phase"],
                "sequence": self.record["sequence"],
                "journal_digest": self.record["integrity_digest"],
                "subreaper": subreaper}

    def run(self) -> None:
        while True:
            self._check_journal()
            self._reap()
            self._dispatch_exit_if_due()
            watch = [self.server]
            if not self.pty_eof:
                watch.append(self.pty_master)
            readable, _, _ = select.select(watch, [], [], 0.1)
            if self.pty_master in readable:
                self._pump_pty()
            if not readable:
                continue
            if self.server not in readable:
                continue
            connection, _ = self.server.accept()
            with connection:
                try:
                    request = _receive(connection)
                    if not secrets.compare_digest(str(request.get("credential", "")),
                                                  self.credential):
                        raise SourceCustodyError("custodian credential refused")
                    method = request.get("method")
                    if method == "start":
                        result = self._start(request)
                    elif method == "challenge":
                        result = self._challenge(request)
                    elif method == "tty-read":
                        result = self._tty_read()
                    elif method == "tty-write":
                        result = self._tty_write(request)
                    elif method == "tty-resize":
                        result = self._tty_resize(request)
                    elif method == "activate-input":
                        result = self._activate_input(request)
                    elif method == "request-exit":
                        result = self._request_exit(request)
                    elif method == "fence":
                        result = self._fence(request)
                    elif method == "stop-event":
                        peer = struct.unpack("3i", connection.getsockopt(
                            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[0]
                        result = self._stop_event(request, peer)
                    elif method in {"stop-begin", "session-start", "prompt-begin"}:
                        peer = struct.unpack("3i", connection.getsockopt(
                            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[0]
                        result = (self._stop_begin(peer) if method == "stop-begin" else
                                  self._prompt_begin(request, peer) if method == "prompt-begin" else
                                  self._session_start(request, peer))
                    else:
                        raise SourceCustodyError("custodian method is unsupported")
                    _reply(connection, {"ok": True, "result": result})
                except (SourceCustodyError, OSError, ValueError, TypeError) as exc:
                    _reply(connection, {"ok": False, "error": str(exc)[:256]})


def custodian_main(directory: str, credential_fd: int) -> None:
    _Custodian(Path(directory), credential_fd).run()


def request(directory: Path, credential: str, method: str,
            *, deadline: Optional[float] = None, **arguments: Any) -> Dict[str, Any]:
    """Issue one bounded request; caller must compare the returned identity."""
    directory = Path(directory)
    launch_file = directory / "launch.json"
    if launch_file.exists():
        launch = json.loads(launch_file.read_bytes())
        if (launch.get("integrity_digest") != _digest({
                key: item for key, item in launch.items() if key != "integrity_digest"}) or
                not isinstance(launch.get("socket_path"), str)):
            raise SourceCustodyError("custodian socket binding journal changed")
        path = Path(launch["socket_path"])
    else:
        path = _socket_path(directory)
    if not path.is_absolute() or len(str(path).encode("utf-8")) >= 108:
        raise SourceCustodyError("custodian socket path is malformed")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        remaining = 5.0 if deadline is None else min(5.0, deadline - time.monotonic())
        if remaining <= 0:
            raise SourceCustodyError("custodian request deadline exceeded")
        connection.settimeout(remaining)
        connection.connect(str(path))
        remaining = 5.0 if deadline is None else min(5.0, deadline - time.monotonic())
        if remaining <= 0:
            raise SourceCustodyError("custodian request deadline exceeded")
        connection.settimeout(remaining)
        connection.sendall(_canonical({"method": method, "credential": credential,
                                      **arguments}) + b"\n")
        response = _receive(connection, deadline=deadline)
    if response.get("ok") is not True or not isinstance(response.get("result"), dict):
        raise SourceCustodyError(str(response.get("error", "custodian refused")))
    return response["result"]


class SharedParentRegistry:
    """Cross-lane exclusion for one exact parent in one history store.

    The root is chosen once for the whole user/host/PID namespace, not from a
    lane state directory.  A failed or uncertain launch deliberately keeps its
    record, so another lane never treats an absent PID as permission to spawn.
    """

    def __init__(self, root: str):
        self.root = Path(root)
        if not self.root.is_absolute() or self.root.is_symlink():
            raise SourceCustodyError("shared parent registry root must be absolute and real")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.resolve(strict=True) != self.root or self.root.stat().st_mode & 0o077:
            raise SourceCustodyError("shared parent registry root is not owner-private")
        self.path = self.root / "parents.json"
        self.identity_path = self.root / "parents.identity"
        self.lock_path = self.root / "parents.lock"

    def _key(self, history_store: str, parent_uuid: str) -> str:
        try:
            history = str(Path(history_store).resolve(strict=True))
            if not Path(history).is_dir() or str(__import__("uuid").UUID(parent_uuid)) != parent_uuid:
                raise ValueError("not canonical")
            stat_result = os.stat(history)
            context = _identity(os.getpid())
        except (OSError, ValueError, TypeError, SourceCustodyError) as exc:
            raise SourceCustodyError("history store or parent identity is invalid") from exc
        return _digest({"history_store": history, "device": stat_result.st_dev,
                        "inode": stat_result.st_ino, "parent_uuid": parent_uuid,
                        "boot_id": context["boot_id"],
                        "pid_namespace": context["pid_namespace"]})

    def _load(self) -> Dict[str, Any]:
        # Called only while parents.lock is held.  The sidecar distinguishes a
        # genuinely new registry from a deleted parents.json after a claim.
        # An older registry is upgraded in place without dropping its entries;
        # once identity metadata exists, either missing file is fatal.
        data_exists = os.path.lexists(str(self.path))
        identity_exists = os.path.lexists(str(self.identity_path))
        if not data_exists and not identity_exists:
            return self._initialize({})
        if not identity_exists:
            legacy = self._read_registry_json(self.path, "shared parent registry", 1024 * 1024)
            if (legacy.get("schema") != 1 or not isinstance(legacy.get("entries"), dict) or
                    "registry_id" in legacy or "integrity_digest" in legacy):
                raise SourceCustodyError("shared parent registry initialization identity is missing")
            return self._initialize(legacy["entries"])

        identity = self._read_registry_json(self.identity_path,
                                            "shared parent registry identity", 4096)
        if (identity.get("schema") != 1 or
                not self._canonical_uuid(identity.get("registry_id")) or
                identity.get("integrity_digest") != _digest({
                    key: item for key, item in identity.items()
                    if key != "integrity_digest"})):
            raise SourceCustodyError("shared parent registry identity is malformed")
        if not data_exists:
            raise SourceCustodyError("shared parent registry is missing after initialization")

        value = self._read_registry_json(self.path, "shared parent registry", 1024 * 1024)
        if (value.get("schema") != 1 or not isinstance(value.get("entries"), dict) or
                value.get("registry_id") != identity["registry_id"] or
                value.get("integrity_digest") != _digest({
                    key: item for key, item in value.items()
                    if key != "integrity_digest"})):
            raise SourceCustodyError("shared parent registry is malformed or changed")
        return value

    @staticmethod
    def _canonical_uuid(value: Any) -> bool:
        try:
            return isinstance(value, str) and str(uuid.UUID(value)) == value
        except (ValueError, AttributeError, TypeError):
            return False

    @staticmethod
    def _read_registry_json(path: Path, label: str, size_bound: int) -> Dict[str, Any]:
        if path.is_symlink():
            raise SourceCustodyError("%s is linked" % label)
        try:
            fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                    raise SourceCustodyError("%s is not an owner-private file" % label)
                with os.fdopen(fd, "rb") as input_file:
                    fd = -1
                    raw = input_file.read(size_bound + 1)
            finally:
                if fd >= 0:
                    os.close(fd)
        except OSError as exc:
            raise SourceCustodyError("%s is unavailable" % label) from exc
        if len(raw) > size_bound:
            raise SourceCustodyError("%s exceeds size bound" % label)
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            raise SourceCustodyError("%s is malformed" % label) from exc
        if not isinstance(value, dict):
            raise SourceCustodyError("%s is malformed" % label)
        return value

    def _initialize(self, entries: Dict[str, Any]) -> Dict[str, Any]:
        registry_id = str(uuid.uuid4())
        value = {"schema": 1, "registry_id": registry_id, "entries": entries}
        value["integrity_digest"] = _digest(value)
        identity = {"schema": 1, "registry_id": registry_id}
        identity["integrity_digest"] = _digest(identity)
        # If a process dies between these durable replacements, the next
        # reader sees an identity/data mismatch and refuses instead of
        # admitting a second owner.
        _write_durable(self.path, value)
        _write_durable(self.identity_path, identity)
        return value

    def _with_lock(self, callback: Any) -> Any:
        fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            value = self._load()
            result, changed = callback(value)
            if changed:
                value["integrity_digest"] = _digest({
                    key: item for key, item in value.items()
                    if key != "integrity_digest"})
                _write_durable(self.path, value)
            return result
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def claim_source(self, *, history_store: str, parent_uuid: str, lane: str,
                     generation: int, runtime_id: str, manifest_digest: str) -> Dict[str, Any]:
        key = self._key(history_store, parent_uuid)
        if (not isinstance(lane, str) or not lane or
                isinstance(generation, bool) or not isinstance(generation, int) or
                generation <= 0 or not isinstance(runtime_id, str) or
                not isinstance(manifest_digest, str)):
            raise SourceCustodyError("source registry binding is malformed")
        def change(value: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
            if key in value["entries"]:
                raise SourceCustodyError("exact parent already has a shared-session claimant")
            entry = {"key": key, "history_store": str(Path(history_store).resolve()),
                     "parent_uuid": parent_uuid, "lane": lane,
                     "generation": generation, "runtime_id": runtime_id,
                     "manifest_digest": manifest_digest, "phase": "source-intent",
                     "custodian_identity": None, "source_identity": None,
                     "operation_id": None}
            value["entries"][key] = entry
            return dict(entry), True
        return self._with_lock(change)

    def transition(self, *, history_store: str, parent_uuid: str,
                   lane: str, expected_phase: str, phase: str,
                   runtime_id: str, expected_runtime_id: Optional[str] = None,
                   **changes: Any) -> Dict[str, Any]:
        key = self._key(history_store, parent_uuid)
        valid = {"source-intent": "source-running", "source-running": "source-fenced",
                 "source-fenced": "target-intent", "target-intent": "target-running",
                 "target-running": "source-fenced"}
        if valid.get(expected_phase) != phase:
            raise SourceCustodyError("shared parent registry transition is unsupported")
        def change(value: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
            entry = value["entries"].get(key)
            if (not isinstance(entry, dict) or entry.get("lane") != lane or
                    entry.get("phase") != expected_phase or
                    entry.get("runtime_id") != (
                        expected_runtime_id if phase == "target-intent" else runtime_id)):
                raise SourceCustodyError("shared parent registry identity or phase changed")
            if phase == "target-intent" and (
                    not expected_runtime_id or expected_runtime_id == runtime_id):
                raise SourceCustodyError("target must have a distinct runtime incarnation")
            allowed = {"custodian_identity", "source_identity", "operation_id",
                       "runtime_id", "manifest_digest", "generation"}
            if any(item not in allowed for item in changes):
                raise SourceCustodyError("shared parent registry mutation is unsupported")
            entry.update(changes)
            if phase == "target-intent":
                entry["runtime_id"] = runtime_id
                entry["custodian_identity"] = None
                entry["source_identity"] = None
            entry["phase"] = phase
            return dict(entry), True
        return self._with_lock(change)

    def status(self, *, history_store: str, parent_uuid: str) -> Optional[Dict[str, Any]]:
        key = self._key(history_store, parent_uuid)
        return self._with_lock(lambda value: (value["entries"].get(key), False))


class SourceCustodianLauncher:
    """One durable, non-retrying wrapper admission for a claimed source."""

    def __init__(self, directory: str):
        self.directory = Path(directory)
        if not self.directory.is_absolute() or self.directory.is_symlink():
            raise SourceCustodyError("source custodian directory must be absolute and real")

    def launch(self, *, argv: list[str], environment: Mapping[str, str], cwd: str,
               intent: Mapping[str, Any], stdin: Any = None, stdout: Any = None,
               stderr: Any = None) -> Dict[str, Any]:
        if self.directory.exists():
            raise SourceCustodyError("source custodian admission already exists")
        self.directory.mkdir(mode=0o700, parents=True)
        credential = secrets.token_hex(32)
        credential_path = self.directory / "credential"
        fd = os.open(str(credential_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(credential.encode("ascii"))
            output.flush()
            os.fsync(output.fileno())
        launch_intent = {"phase": "wrapper-spawn-intent", "intent": dict(intent),
                         "argv_digest": _digest(argv), "environment_digest": _digest(environment),
                         "cwd": cwd, "custodian": None, "source": None,
                         "socket_path": str(_socket_path(self.directory))}
        self._write_launch(launch_intent)
        read_fd, write_fd = os.pipe()
        try:
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--custodian",
                 str(self.directory), str(read_fd)],
                pass_fds=(read_fd,), stdin=stdin, stdout=stdout, stderr=stderr,
                close_fds=True, start_new_session=True,
            )
        except BaseException:
            os.close(read_fd)
            os.close(write_fd)
            raise
        os.close(read_fd)
        try:
            os.write(write_fd, credential.encode("ascii"))
        finally:
            os.close(write_fd)
        custodian_identity = _identity(process.pid)
        deadline = time.monotonic() + 5.0
        while not _socket_path(self.directory).exists():
            if process.poll() is not None or time.monotonic() > deadline:
                raise SourceCustodyError("custodian startup is uncertain; do not retry")
            time.sleep(0.02)
        nonce = secrets.token_hex(16)
        while True:
            remaining = deadline - time.monotonic()
            if (process.poll() is not None or remaining <= 0 or
                    _identity(process.pid) != custodian_identity):
                raise SourceCustodyError("custodian startup is uncertain; do not retry")
            try:
                first = request(self.directory, credential, "challenge", nonce=nonce,
                                deadline=deadline)
                break
            except OSError as exc:
                # bind creates the socket name before listen accepts peers.
                # Retry only this read-only first challenge against the one
                # spawned custodian; never replay its start request.
                if exc.errno not in {errno.ENOENT, errno.ECONNREFUSED}:
                    raise
                time.sleep(0.02)
        if (process.poll() is not None or time.monotonic() > deadline or
                _identity(process.pid) != custodian_identity):
            raise SourceCustodyError("custodian startup is uncertain; do not retry")
        if (first.get("nonce") != nonce or first.get("phase") != "waiting" or
                first.get("source") is not None or first.get("subreaper") is not True or
                first.get("custodian") != custodian_identity):
            raise SourceCustodyError("custodian did not acknowledge an unstarted source")
        launch_intent["phase"] = "custodian-ready"
        launch_intent["custodian"] = first["custodian"]
        self._write_launch(launch_intent)
        started = request(self.directory, credential, "start", argv=argv,
                          environment=dict(environment), cwd=cwd, intent=dict(intent))
        if started.get("custodian") != first["custodian"] or not isinstance(started.get("source"), dict):
            raise SourceCustodyError("source start acknowledgment identity changed")
        launch_intent["phase"] = "source-running"
        launch_intent["source"] = started["source"]
        self._write_launch(launch_intent)
        return {"custodian": first["custodian"], "source": started["source"],
                "directory": str(self.directory)}

    def _write_launch(self, value: Dict[str, Any]) -> None:
        value["integrity_digest"] = _digest({key: item for key, item in value.items()
                                             if key != "integrity_digest"})
        _write_durable(self.directory / "launch.json", value)

    def challenge(self) -> Dict[str, Any]:
        try:
            launch = json.loads((self.directory / "launch.json").read_bytes())
            if launch.get("integrity_digest") != _digest({
                    key: item for key, item in launch.items() if key != "integrity_digest"}):
                raise SourceCustodyError("source launcher journal integrity changed")
            credential = (self.directory / "credential").read_text(encoding="ascii")
            nonce = secrets.token_hex(16)
            answer = request(self.directory, credential, "challenge", nonce=nonce)
        except (OSError, ValueError, KeyError) as exc:
            raise SourceCustodyError("source custodian journal or challenge is unavailable") from exc
        if (answer.get("nonce") != nonce or answer.get("subreaper") is not True or
                answer.get("custodian") != _identity(answer["custodian"]["pid"]) or
                launch.get("phase") != "source-running" or
                launch.get("custodian") != answer.get("custodian") or
                launch.get("source") != answer.get("source")):
            raise SourceCustodyError("source custodian challenge differs from its launch journal")
        return answer

    def _credential(self) -> str:
        try:
            return (self.directory / "credential").read_text(encoding="ascii")
        except OSError as exc:
            raise SourceCustodyError("custodian credential is unavailable") from exc

    def fence(self, *, operation_id: str, parent_uuid: str,
              runtime_id: str) -> Dict[str, Any]:
        return request(self.directory, self._credential(), "fence",
                       operation_id=operation_id, parent_uuid=parent_uuid,
                       runtime_id=runtime_id)

    def request_exit(self, *, operation_id: str, parent_uuid: str,
                     runtime_id: str) -> Dict[str, Any]:
        return request(self.directory, self._credential(), "request-exit",
                       operation_id=operation_id, parent_uuid=parent_uuid,
                       runtime_id=runtime_id)

    def tty_read(self) -> bytes:
        value = request(self.directory, self._credential(), "tty-read")
        return base64.b64decode(value["data"], validate=True)

    def tty_write(self, data: bytes) -> int:
        if len(data) > 32768:
            raise SourceCustodyError("terminal input frame exceeds its bound")
        value = request(self.directory, self._credential(), "tty-write",
                        data=base64.b64encode(data).decode("ascii"))
        return value["written"]

    def activate_input(self, *, parent_uuid: str, runtime_id: str,
                       launch_intent_id: str, manifest_digest: str) -> None:
        request(self.directory, self._credential(), "activate-input",
                parent_uuid=parent_uuid, runtime_id=runtime_id,
                launch_intent_id=launch_intent_id,
                manifest_digest=manifest_digest)

    def tty_resize(self, rows: int, columns: int) -> None:
        request(self.directory, self._credential(), "tty-resize",
                rows=rows, columns=columns)


class SharedSessionSourceProvider:
    """Bind the T053 lane ledger to a cross-lane parent claim and OS custodian.

    A separate trusted history provider and job domain are required for
    readiness.  This provider makes no synthetic native history claim.
    """

    def __init__(self, ledger: Any, registry: SharedParentRegistry,
                 admissions_root: str, *, history_provider: Any = None,
                 job_provider: Any = None, next_watermark: Any = None):
        from lane_managed_supervised_jobs import ClaudeCliSupervisedJobsLedger
        if not isinstance(ledger, ClaudeCliSupervisedJobsLedger):
            raise SourceCustodyError("shared source provider requires the T053 ledger")
        self.ledger = ledger
        self.registry = registry
        self.admissions_root = Path(admissions_root)
        if (not self.admissions_root.is_absolute() or self.admissions_root.is_symlink() or
                not self.admissions_root.is_dir() or
                self.admissions_root.stat().st_mode & 0o077):
            raise SourceCustodyError("shared source admissions root must be owner-private")
        self.history_provider = history_provider
        self.job_provider = job_provider
        self.next_watermark = next_watermark or MonotonicWitnessSequence().next
        self.persistent_job_domain_id = getattr(job_provider, "persistent_job_domain_id", None)

    def _admission_path(self, runtime_id: str) -> Path:
        try:
            if str(__import__("uuid").UUID(runtime_id)) != runtime_id:
                raise ValueError("not canonical")
        except (TypeError, ValueError, AttributeError) as exc:
            raise SourceCustodyError("runtime admission ID is malformed") from exc
        return self.admissions_root / (runtime_id + ".json")

    def _read_admission(self, runtime_id: str) -> Dict[str, Any]:
        path = self._admission_path(runtime_id)
        try:
            raw = path.read_bytes()
            if len(raw) > 64 * 1024:
                raise ValueError("too large")
            value = json.loads(raw)
        except (OSError, ValueError) as exc:
            raise SourceCustodyError("source admission journal is unavailable") from exc
        if (not isinstance(value, dict) or
                value.get("integrity_digest") != _digest({
                    key: item for key, item in value.items() if key != "integrity_digest"})):
            raise SourceCustodyError("source admission journal integrity changed")
        return value

    def _write_admission(self, value: Dict[str, Any]) -> None:
        value["integrity_digest"] = _digest({
            key: item for key, item in value.items() if key != "integrity_digest"})
        _write_durable(self._admission_path(value["runtime_id"]), value)

    def admit_source(self, *, manifest: Mapping[str, Any], history_store: str,
                     supervisor_incarnation: str, lineage_id: str,
                     lineage_generation: int, invocation_id: str,
                     stdin: Any = None, stdout: Any = None,
                     stderr: Any = None) -> Dict[str, Any]:
        """Claim before spawn; any lost acknowledgment leaves the claim held."""
        from lane_managed_cli_runtime import runtime_launch_digest, validate_runtime_launch
        launch = validate_runtime_launch(manifest)
        expected_history = Path(launch["profile_config_dir"]) / "projects"
        try:
            if (expected_history.resolve(strict=True) != Path(history_store).resolve(strict=True) or
                    not expected_history.is_dir()):
                raise SourceCustodyError("history store differs from the bound profile projects store")
        except (OSError, RuntimeError) as exc:
            raise SourceCustodyError("bound profile projects store is unavailable") from exc
        digest = runtime_launch_digest(launch)
        runtime_id = launch["runtime_id"]
        parent_uuid = launch["parent_uuid"]
        domain_id = "source-subr-" + runtime_id
        ledger_status = None
        try:
            ledger_status = self.ledger.status()
        except Exception:
            # A first admission may have no ledger yet.  The managed owner
            # remains authoritative for its actual generation.
            pass
        generation = 1 if ledger_status is None else ledger_status["claim_generation"]
        identity = self.ledger.store.identity
        with self.ledger._locked() as owner:
            worktrees = self.ledger._registered_worktrees(
                lineage_id, lineage_generation, parent_uuid, owner["generation"])
        matches = [row for row in worktrees
                   if os.path.commonpath((row["path"], launch["cwd"])) == row["path"]]
        if len(matches) != 1:
            raise SourceCustodyError("source cwd is not one registered worktree")
        self.registry.claim_source(
            history_store=history_store, parent_uuid=parent_uuid,
            lane=identity.lane, generation=generation,
            runtime_id=runtime_id, manifest_digest=digest,
        )
        claim = self.ledger.claim_source(
            supervisor_incarnation=supervisor_incarnation,
            parent_uuid=parent_uuid, lineage_id=lineage_id,
            lineage_generation=lineage_generation,
            profile_ref=launch["profile_ref"], runtime_incarnation=runtime_id,
            invocation_id=invocation_id, domain_id=domain_id,
            manifest_digest=digest,
        )
        if claim["claim_generation"] != generation:
            raise SourceCustodyError("source generation changed during registry admission")
        custodian_dir = str(self.admissions_root / (runtime_id + "-custodian"))
        admission = {
            "schema": 1, "runtime_id": runtime_id, "parent_uuid": parent_uuid,
            "profile_ref": launch["profile_ref"], "history_store": str(Path(history_store).resolve()),
            "manifest_path": str(Path(launch["settings_path"]).parent / "manifest.json"),
            "manifest_digest": digest, "claim_generation": generation,
            "source_domain_id": domain_id, "invocation_id": invocation_id,
            "supervisor_incarnation": supervisor_incarnation,
            "custodian_dir": custodian_dir,
            "phase": "source-spawn-intent", "custodian": None, "source": None,
        }
        if self._admission_path(runtime_id).exists():
            raise SourceCustodyError("source admission journal already exists")
        self._write_admission(admission)
        intent = {"digest": _digest({
            "runtime_id": runtime_id, "parent_uuid": parent_uuid,
            "manifest_digest": digest, "generation": generation,
            "domain_id": domain_id,
        }), "runtime_id": runtime_id, "parent_uuid": parent_uuid,
            "generation": generation, "manifest_digest": digest,
            "domain_id": domain_id, "operation_id": None}
        # Hold the same owner/store lock that prepare_swap acquires through
        # actual fork, identity publication and exec-gate release.  A prepare
        # either fences before this check or follows completed source spawn.
        with self.ledger._locked() as owner:
            state = self.ledger._load(owner)
            self.ledger._owner_current(owner, state)
            current = state.get("current_claim")
            if (not isinstance(current, dict) or current.get("state") != "active" or
                    current.get("claim_generation") != generation or
                    current.get("parent_uuid") != parent_uuid or
                    current.get("manifest_digest") != digest or
                    current.get("runtime_incarnation") != runtime_id or
                    generation in state["retired_source_generations"]):
                raise SourceCustodyError("source generation was fenced before spawn")
            self.ledger._assert_registered_worktree_ids(
                lineage_id=lineage_id, lineage_generation=lineage_generation,
                parent_uuid=parent_uuid, owner_generation=state["owner_generation"],
                expected_worktree_ids=current["worktree_ids"],
            )
            from lane_managed_cli_runtime import runtime_launch_digest, validate_runtime_launch
            if runtime_launch_digest(validate_runtime_launch(launch)) != digest:
                raise SourceCustodyError("source immutable launch changed before exec gate")
            result = SourceCustodianLauncher(custodian_dir).launch(
                argv=launch["argv"], environment=launch["environment"],
                cwd=launch["cwd"], intent=intent,
                stdin=stdin, stdout=stdout, stderr=stderr,
            )
        admission["phase"] = "source-running"
        admission["custodian"] = result["custodian"]
        admission["source"] = result["source"]
        self._write_admission(admission)
        self.registry.transition(
            history_store=history_store, parent_uuid=parent_uuid,
            lane=identity.lane, expected_phase="source-intent", phase="source-running",
            runtime_id=runtime_id, custodian_identity=result["custodian"],
            source_identity=result["source"],
        )
        return {"claim": claim, "admission": admission}

    def _matching_admission(self, binding: Mapping[str, Any]) -> Dict[str, Any]:
        runtime_id = binding.get("source_runtime_incarnation")
        admission = self._read_admission(runtime_id)
        checks = {
            "runtime_id": runtime_id,
            "parent_uuid": binding.get("parent_uuid"),
            "source_domain_id": binding.get("source_domain_id"),
            "manifest_digest": binding.get("source_manifest_digest"),
            "claim_generation": binding.get("source_claim_generation"),
            "invocation_id": binding.get("source_invocation_id"),
            "supervisor_incarnation": binding.get("supervisor_incarnation"),
        }
        if any(admission.get(key) != expected for key, expected in checks.items()):
            raise SourceCustodyError("source admission does not match durable operation")
        if admission.get("phase") != "source-running":
            raise SourceCustodyError("source admission has unresolved launch intent")
        self._launch_manifest(admission)
        return admission

    @staticmethod
    def _launch_manifest(admission: Mapping[str, Any]) -> Dict[str, Any]:
        from lane_managed_cli_runtime import runtime_launch_digest, validate_runtime_launch
        try:
            manifest = validate_runtime_launch(
                json.loads(Path(admission["manifest_path"]).read_bytes()))
        except (OSError, ValueError) as exc:
            raise SourceCustodyError("source launch manifest is unavailable") from exc
        if (runtime_launch_digest(manifest) != admission["manifest_digest"] or
                manifest["runtime_id"] != admission["runtime_id"] or
                manifest["parent_uuid"] != admission["parent_uuid"] or
                manifest["profile_ref"] != admission["profile_ref"]):
            raise SourceCustodyError("source launch manifest changed")
        history_store = admission.get("history_store")
        if not isinstance(history_store, str) or not history_store:
            raise SourceCustodyError("admitted history store is unavailable")
        try:
            observed_store = (Path(manifest["profile_config_dir"]) / "projects").resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SourceCustodyError("bound profile history store is unavailable") from exc
        if (str(observed_store) != history_store or not observed_store.is_dir() or
                observed_store.is_symlink()):
            raise SourceCustodyError("bound profile history store changed after admission")
        return manifest

    def source_exclusion(self, binding: Mapping[str, Any]) -> Dict[str, Any]:
        admission = self._matching_admission(binding)
        self._launch_manifest(admission)
        ledger = self.ledger.status()
        matches = [item for item in ledger["operations"].values()
                   if item.get("source_runtime_incarnation") == admission["runtime_id"] and
                   item.get("source_claim_generation") == admission["claim_generation"] and
                   item.get("parent_uuid") == admission["parent_uuid"]]
        if (len(matches) != 1 or matches[0].get("source_restart_denied") is not True or
                admission["claim_generation"] not in ledger["retired_source_generations"]):
            raise SourceCustodyError("source restart fence is not durable")
        registered = self.registry.status(
            history_store=admission["history_store"], parent_uuid=admission["parent_uuid"])
        if (not isinstance(registered, dict) or registered.get("lane") != self.ledger.store.identity.lane or
                registered.get("runtime_id") != admission["runtime_id"] or
                registered.get("phase") not in {"source-running", "source-fenced"} or
                registered.get("custodian_identity") != admission["custodian"] or
                registered.get("source_identity") != admission["source"]):
            raise SourceCustodyError("cross-lane parent registry changed")
        answer = SourceCustodianLauncher(admission["custodian_dir"]).challenge()
        source_exit = answer.get("source_exit")
        launch_intent = answer.get("launch_intent")
        if (answer.get("custodian") != admission["custodian"] or
                answer.get("source") != admission["source"] or
                not isinstance(answer.get("nonce"), str) or
                not 16 <= len(answer["nonce"]) <= 128 or
                not isinstance(launch_intent, dict) or
                launch_intent.get("runtime_id") != admission["runtime_id"] or
                launch_intent.get("parent_uuid") != admission["parent_uuid"] or
                launch_intent.get("operation_id") != matches[0]["operation_id"] or
                not isinstance(source_exit, dict) or source_exit.get("exited") is not True or
                answer.get("subreaper") is not True or answer.get("drained") is not True or
                answer.get("phase") != "drained"):
            raise SourceCustodyError("exact source has not gracefully exited and drained")
        if self.job_provider is None or not callable(getattr(self.job_provider, "assert_ready", None)):
            raise SourceCustodyError("independent persistent job domain is unavailable")
        self.job_provider.assert_ready()
        proof = {"admission_digest": admission["integrity_digest"],
                 "custodian": answer["custodian"], "source": answer["source"],
                 "exit": answer["source_exit"], "sequence": answer["sequence"],
                 "challenge_nonce": answer["nonce"],
                 "journal_digest": answer["journal_digest"],
                 "registry_digest": _digest(registered)}
        return {
            "witness_id": "shared-subr-" + admission["runtime_id"],
            "witness_digest": _digest(proof),
            "observation_watermark": self.next_watermark(ledger["observation_watermark"]),
            "source_runtime_incarnation": admission["runtime_id"],
            "source_domain_id": admission["source_domain_id"],
            "supervisor_incarnation": admission["supervisor_incarnation"],
            "parent_uuid": admission["parent_uuid"],
            "membership_complete": True, "escape_coverage_complete": True,
            "active_source_processes": 0, "restart_fence_effective": True,
            "job_domain_live": True,
        }

    def history_manifest(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.history_provider is None:
            raise SourceCustodyError("trusted Claude history witness is unavailable")
        admission = self._matching_admission(binding)
        manifest = self._launch_manifest(admission)
        extended = dict(binding)
        extended["source_profile_ref"] = admission["profile_ref"]
        extended["source_cwd"] = manifest["cwd"]
        return self.history_provider.history_manifest(extended)

    def job_status(self, binding: Mapping[str, Any], job_id: str) -> Mapping[str, Any]:
        if self.job_provider is None:
            raise SourceCustodyError("persistent job witness is unavailable")
        return self.job_provider.job_status(binding, job_id)

    def target_status(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        launch_intent_id = binding.get("launch_intent_id")
        if not isinstance(launch_intent_id, str) or not launch_intent_id:
            raise SourceCustodyError("target launch intent is malformed")
        matches = []
        for path in self.admissions_root.glob("*.json"):
            try:
                value = self._read_admission(path.stem)
            except SourceCustodyError:
                # An unrelated uncertain admission must not be silently
                # selected as this target; exact matches are checked below.
                continue
            if value.get("launch_intent_id") == launch_intent_id:
                matches.append(value)
        if len(matches) != 1:
            raise SourceCustodyError("target launch intent has no unique admission")
        admission = matches[0]
        checks = {
            "parent_uuid": binding.get("parent_uuid"),
            "profile_ref": binding.get("profile_ref"),
            "manifest_digest": binding.get("manifest_digest"),
            "claim_generation": binding.get("target_claim_generation"),
            "supervisor_incarnation": binding.get("supervisor_incarnation"),
            "launch_intent_id": launch_intent_id,
        }
        if (admission.get("phase") != "target-running" or
                any(admission.get(key) != expected for key, expected in checks.items())):
            raise SourceCustodyError("target admission differs from explicit release")
        launch = self._launch_manifest(admission)
        if launch["launch_mode"] != "resume":
            raise SourceCustodyError("target did not request exact-parent resume")
        answer = SourceCustodianLauncher(admission["custodian_dir"]).challenge()
        intent = answer.get("launch_intent")
        started = answer.get("session_start")
        if (answer.get("custodian") != admission.get("custodian") or
                answer.get("source") != admission.get("source") or
                answer.get("source_exit") is not None or
                answer.get("phase") != "running" or
                answer.get("subreaper") is not True or
                not isinstance(intent, dict) or
                intent.get("launch_intent_id") != launch_intent_id or
                intent.get("runtime_id") != admission["runtime_id"] or
                intent.get("parent_uuid") != admission["parent_uuid"] or
                not isinstance(started, dict) or
                started.get("source") != "resume" or
                started.get("cwd") != launch["cwd"] or
                _identity(admission["source"]["pid"]) != admission["source"]):
            raise SourceCustodyError("exact resumed target process was not observed")
        if self.history_provider is None:
            raise SourceCustodyError("target history identity provider is unavailable")
        resolver = self.history_provider.profile_resolver
        profile = resolver.resolve(admission["profile_ref"])
        history = resolver.verify_transcript(profile, admission["parent_uuid"],
                                             launch["cwd"])
        if (history.get("transcript", {}).get("path") != started.get("transcript_path") or
                history.get("profile", {}).get("config_dir") != launch["profile_config_dir"]):
            raise SourceCustodyError("target SessionStart named another saved parent")
        account_digest = auth_account_digest(launch, profile.email)
        if account_digest != admission.get("account_identity_digest"):
            raise SourceCustodyError("target authenticated account changed since startup")
        proof = {"admission": admission["integrity_digest"],
                 "custodian": answer["custodian"], "source": answer["source"],
                 "session_start": started, "account": account_digest,
                 "journal": answer["journal_digest"]}
        return {
            "witness_id": "shared-target-" + admission["runtime_id"],
            "witness_digest": _digest(proof),
            "observation_watermark": self.next_watermark(
                self.ledger.status()["observation_watermark"]),
            "state": "running", "parent_uuid": admission["parent_uuid"],
            "profile_ref": admission["profile_ref"],
            "manifest_digest": admission["manifest_digest"],
            "claim_generation": admission["claim_generation"],
            "runtime_incarnation": admission["runtime_id"],
            "invocation_id": admission["invocation_id"],
            "domain_id": admission["source_domain_id"],
            "process_identity": {
                "pid": admission["source"]["pid"],
                "start_token": admission["source"]["start_token"],
                "domain_id": admission["source_domain_id"],
            },
            "account_identity_digest": account_digest,
        }


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--custodian":
        raise SystemExit("usage: lane_managed_cli_source.py --custodian <private-dir> <credential-fd>")
    custodian_main(sys.argv[2], int(sys.argv[3]))
