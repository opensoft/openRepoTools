# SPDX-License-Identifier: Apache-2.0
"""Bounded, offline probe of the pinned CLI through the shared-session launcher.

This is a manual diagnostic, not an authenticated account-swap acceptance test.
It uses the production immutable launch builder and source custodian, a fresh
fake-key profile, and an explicitly selected network isolation mode. No model
prompt is submitted. Seccomp denies non-AF_UNIX socket creation, io_uring
setup and pidfd_getfd; it does not confine AF_UNIX paths or measure attempted
provider requests.
The custodian's idle-prompt hint only licenses the owned /exit attempt; its
source-exit and drained observations remain separate required witnesses.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import http.server
import json
import os
import re
import resource
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import psutil


PINNED_VERSION = "2.1.283 (Claude Code)"
PROMPT = "❯".encode("utf-8")
MAX_SECONDS = 45
MAX_CAPTURE = 64 * 1024


class _RejectingAPI(http.server.BaseHTTPRequestHandler):
    calls: list[tuple[str, str]] = []
    lock = threading.Lock()

    def _reject(self) -> None:
        with type(self).lock:
            type(self).calls.append((self.command, self.path[:128]))
        self.send_response(503)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = _reject
    do_POST = _reject
    do_PUT = _reject

    def log_message(self, *_args: object) -> None:
        pass


def _private_json(path: Path, value: object) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")


def _capture_add(capture: bytearray, data: bytes) -> None:
    capture.extend(data)
    if len(capture) > MAX_CAPTURE:
        del capture[:-MAX_CAPTURE]


def _sanitized_screen(data: bytes, root: Path) -> dict[str, object]:
    """Keep only a short redacted UI excerpt from this disposable fixture."""
    rendered = data.decode("utf-8", "replace")
    rendered = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", rendered)
    rendered = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", rendered)
    rendered = rendered.replace(str(root), "<private-root>")
    rendered = rendered.replace("sk-ant-offline-probe", "<fake-key>")
    rendered = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "<uuid>", rendered)
    rendered = "".join(character if character.isprintable() or character in "\n\r\t"
                       else " " for character in rendered)
    lines = [line.strip()[:180] for line in rendered.splitlines() if line.strip()]
    return {"line_count": len(lines), "last_lines": lines[-12:]}


def _owned_tree(pid: int | None) -> list[tuple[psutil.Process, float]]:
    if pid is None:
        return []
    try:
        root = psutil.Process(pid)
        return [(p, p.create_time()) for p in root.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []


def _stop_owned(pid: int | None) -> None:
    """Clean up only this probe's direct custodian and its verified descendants."""
    if pid is None:
        return
    descendants = _owned_tree(pid)
    for process, created in reversed(descendants):
        try:
            if process.create_time() == created:
                process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    alive: list[psutil.Process] = []
    for process, created in descendants:
        try:
            if process.create_time() == created:
                alive.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _, alive = psutil.wait_procs(alive, timeout=2)
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    psutil.wait_procs(alive, timeout=2)
    try:
        ended, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return
    if ended:
        return
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        ended, _ = os.waitpid(pid, os.WNOHANG)
        if ended:
            return
        time.sleep(.02)
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)


def _recorded_custodian(directory: Path) -> int | None:
    """Recover the exact direct child if launcher acknowledgment was interrupted."""
    for name in ("launch.json", "custodian.json"):
        try:
            identity = json.loads((directory / name).read_bytes()).get("custodian")
            pid = identity.get("pid") if isinstance(identity, dict) else None
            if isinstance(pid, int) and pid > 0:
                # A running direct child cannot have a reused PID before waitpid.
                if psutil.Process(pid).ppid() == os.getpid():
                    return pid
        except (OSError, ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def _timeout(_signal: int, _frame: object) -> None:
    raise TimeoutError("offline probe exceeded its inner deadline")


def _loopback_ready(port: int) -> None:
    """Require the fake provider to be reachable within the isolated netns."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    except OSError as exc:
        raise RuntimeError("isolated loopback is unavailable; no CLI launched") from exc


class _SeccompCompare(ctypes.Structure):
    _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]


def _install_seccomp() -> dict[str, object]:
    """Install a native inherited filter before any production module import."""
    if sys.platform != "linux" or threading.active_count() != 1:
        raise RuntimeError("seccomp requires a single-threaded Linux child")
    ceiling = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
    if ceiling == resource.RLIM_INFINITY:
        ceiling = 1_048_576
    os.closerange(3, min(int(ceiling), 1_048_576))
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                           ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    # PR_SET_NO_NEW_PRIVS / PR_GET_NO_NEW_PRIVS.
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(39, 0, 0, 0, 0) != 1:
        raise RuntimeError("no-new-privileges could not be verified")
    try:
        seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as exc:
        raise RuntimeError("native libseccomp is unavailable") from exc
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint,
        ctypes.POINTER(_SeccompCompare)]
    seccomp.seccomp_rule_add_array.restype = ctypes.c_int
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_load.restype = ctypes.c_int
    allow = 0x7FFF0000  # SCMP_ACT_ALLOW
    deny = 0x00050000 | errno.EPERM  # SCMP_ACT_ERRNO(EPERM)
    context = seccomp.seccomp_init(allow)
    if not context:
        raise RuntimeError("libseccomp could not initialize the filter")
    try:
        for name in (b"socket", b"socketpair"):
            number = seccomp.seccomp_syscall_resolve_name(name)
            if number < 0:
                raise RuntimeError("libseccomp cannot resolve a socket syscall")
            # SCMP_CMP_NE: deny every socket domain other than AF_UNIX.
            comparison = _SeccompCompare(0, 1, socket.AF_UNIX, 0)
            result = seccomp.seccomp_rule_add_array(
                context, deny, number, 1, ctypes.byref(comparison))
            if result != 0:
                raise RuntimeError("libseccomp rejected a socket-domain rule")
        for name in (b"io_uring_setup", b"io_uring_enter",
                     b"io_uring_register", b"pidfd_getfd"):
            number = seccomp.seccomp_syscall_resolve_name(name)
            if number < 0:
                raise RuntimeError("libseccomp cannot resolve a bypass syscall")
            if seccomp.seccomp_rule_add_array(context, deny, number, 0, None) != 0:
                raise RuntimeError("libseccomp rejected a bypass-syscall rule")
        if seccomp.seccomp_load(context) != 0:
            raise RuntimeError("libseccomp could not load the filter")
    finally:
        seccomp.seccomp_release(context)
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            with socket.socket(family, socket.SOCK_STREAM):
                raise RuntimeError("seccomp allowed a network socket")
        except OSError as exc:
            if exc.errno != errno.EPERM:
                raise RuntimeError("network socket preflight did not return EPERM") from exc
    left, right = socket.socketpair(socket.AF_UNIX)
    try:
        left.sendall(b"offline-probe")
        if right.recv(32) != b"offline-probe":
            raise RuntimeError("AF_UNIX socketpair preflight failed")
    finally:
        left.close()
        right.close()
    status = Path("/proc/self/status").read_text(encoding="ascii")
    if "Seccomp:\t2\n" not in status or libc.prctl(39, 0, 0, 0, 0) != 1:
        raise RuntimeError("loaded seccomp/no-new-privileges state is unavailable")
    return {"filter": "libseccomp-default-allow-v1",
            "no_new_privileges": True, "seccomp_mode": 2,
            "denied_socket_domains": "all-except-AF_UNIX",
            "denied_syscalls": ["io_uring_setup", "io_uring_enter",
                                "io_uring_register", "pidfd_getfd"],
            "ipv4_ipv6_preflight": "EPERM", "unix_socketpair_preflight": "passed"}


_SAFE_PROC_TEXT = re.compile(r"[A-Za-z0-9_.+-]{1,64}\Z")
_SAFE_CLI_FLAGS = frozenset({
    "--session-id", "--resume", "--name", "--restricted", "--tools",
    "--disallowedTools", "--settings", "--strict-mcp-config",
    "--mcp-config", "--append-system-prompt", "--debug", "--debug-file",
})
_LOG_MARKERS = ("EPERM", "EACCES", "ENOSYS", "EPIPE", "ECONNREFUSED",
                "ENETUNREACH", "EAI_AGAIN", "permission denied", "error",
                "failed", "timeout", "auth", "mcp", "hook", "sessionstart")


def _safe_proc_text(value: str) -> str:
    return value if _SAFE_PROC_TEXT.fullmatch(value) else "redacted"


def _fd_kind(pid: int, number: int) -> tuple[str, str | None]:
    try:
        target = os.readlink("/proc/%d/fd/%d" % (pid, number))
    except OSError:
        return "unreadable", None
    if target.startswith("/dev/pts/"):
        return "pty-slave", target
    if target == "/dev/null":
        return "null-device", target
    if target.startswith("pipe:["):
        return "pipe", target
    if target.startswith("socket:["):
        return "socket", target
    return "file-or-device", target


def _process_diagnostic(pid: int, project: Path, admitted: dict[str, object]) -> dict[str, object]:
    """Project only fixed numeric proc fields; no argv values or host paths."""
    result: dict[str, object] = {"pid": pid,
                                 "admitted_source_pid": pid == admitted.get("pid")}
    try:
        raw = Path("/proc/%d/stat" % pid).read_text(encoding="ascii")
        fields = raw[raw.rindex(")") + 2:].split()
        stat = {"state": fields[0], "ppid": int(fields[1]),
                "pgrp": int(fields[2]), "session": int(fields[3]),
                "tty_nr": int(fields[4]), "utime_ticks": int(fields[11]),
                "stime_ticks": int(fields[12]), "start_ticks": int(fields[19])}
        result["stat"] = stat
        expected_ticks = str(admitted.get("start_token", "")).rsplit(":", 1)[-1]
        result["admitted_source_identity_matches"] = (
            pid == admitted.get("pid") and str(stat["start_ticks"]) == expected_ticks)
    except (OSError, ValueError, IndexError):
        result["stat"] = "unreadable"
    try:
        result["wchan"] = _safe_proc_text(
            Path("/proc/%d/wchan" % pid).read_text(encoding="ascii").strip())
    except OSError:
        result["wchan"] = "unreadable"
    try:
        args = [item for item in Path("/proc/%d/cmdline" % pid).read_bytes()[:8192].split(b"\0")
                if item]
        text_args = [item.decode("utf-8", errors="replace") for item in args]
        result["cmdline"] = {
            "executable_name": _safe_proc_text(Path(text_args[0]).name) if text_args else None,
            "argument_count": len(text_args),
            "known_flags": [arg.split("=", 1)[0] for arg in text_args[1:]
                            if arg.split("=", 1)[0] in _SAFE_CLI_FLAGS][:32],
            "truncated_at_bytes": 8192,
        }
    except OSError:
        result["cmdline"] = "unreadable"
    fds = [_fd_kind(pid, number) for number in (0, 1, 2)]
    result["stdio"] = {"kinds": [kind for kind, _ in fds],
                       "same_target": all(target is not None and target == fds[0][1]
                                          for _, target in fds)}
    try:
        result["cwd_is_private_project"] = os.path.samefile(
            "/proc/%d/cwd" % pid, project)
    except OSError:
        result["cwd_is_private_project"] = None
    try:
        result["thread_count"] = len(os.listdir("/proc/%d/task" % pid))
        result["open_fd_count"] = len(os.listdir("/proc/%d/fd" % pid))
    except OSError:
        result["thread_count"] = None
        result["open_fd_count"] = None
    return result


def _private_debug_logs(profile: Path) -> dict[str, object]:
    """Summarize only private debug logs; never publish raw lines or paths."""
    debug = profile / "debug"
    if not debug.is_dir() or debug.is_symlink():
        return {"directory_present": False, "files": []}
    files = sorted((item for item in debug.iterdir()
                    if item.is_file() and not item.is_symlink()),
                   key=lambda item: item.stat().st_mtime, reverse=True)[:8]
    rows = []
    for item in files:
        try:
            with item.open("rb") as stream:
                sample = stream.read(65536)
            lower = sample.decode("utf-8", errors="replace").lower()
            rows.append({"size_bytes": item.stat().st_size,
                         "sample_bytes": len(sample),
                         "sample_sha256": hashlib.sha256(sample).hexdigest(),
                         "marker_counts": {marker: lower.count(marker.lower())
                                           for marker in _LOG_MARKERS
                                           if lower.count(marker.lower())}})
        except OSError:
            rows.append({"readable": False})
    return {"directory_present": True, "file_count_at_most": len(files),
            "files": rows}


def _startup_diagnostics(*, custodian_pid: int, source: dict[str, object],
                         project: Path, profile: Path, challenge: dict[str, object]) -> dict[str, object]:
    pids = {custodian_pid, int(source["pid"])}
    try:
        pids.update(process.pid for process in
                    psutil.Process(custodian_pid).children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    observed = {"phase": challenge.get("phase"),
                "sequence": challenge.get("sequence"),
                "subreaper": challenge.get("subreaper"),
                "prompt_ready": challenge.get("prompt_ready"),
                "turn_busy": challenge.get("turn_busy"),
                "turn_sequence": challenge.get("turn_sequence"),
                "session_start_seen": challenge.get("session_start") is not None,
                "source_exit_seen": challenge.get("source_exit") is not None,
                "drained": challenge.get("drained"),
                "source_pid_matches_admission":
                    (challenge.get("source") or {}).get("pid") == source["pid"]}
    return {"challenge": observed,
            "processes": [_process_diagnostic(pid, project, source)
                          for pid in sorted(pids)[:24]],
            "process_count_at_most": min(len(pids), 24),
            "processes_truncated": len(pids) > 24,
            "private_debug_logs": _private_debug_logs(profile)}


def _inside(isolation: str, parent_network_namespace: str | None = None,
            policy: dict[str, object] | None = None,
            untrusted_diagnostic: bool = False) -> int:
    if sys.platform != "linux":
        raise RuntimeError("Linux subreaper contract is required")
    if isolation == "bwrap" and os.readlink("/proc/self/ns/net") == parent_network_namespace:
        raise RuntimeError("network namespace isolation was not established")
    if isolation == "seccomp" and policy is None:
        raise RuntimeError("seccomp preflight did not establish its policy")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    # Imports occur after the offline boundary, including the CLI version check.
    from lane_managed_cli_runtime import (create_runtime_launch,
                                          runtime_launch_digest,
                                          validate_runtime_launch)
    from lane_managed_cli_source import SourceCustodianLauncher

    _RejectingAPI.calls = []
    with tempfile.TemporaryDirectory(prefix="managed-shared-cli-") as temporary:
        root = Path(temporary)
        home = root / "home"
        profile = root / "profile"
        project = root / "project"
        runtimes = root / "runtimes"
        custody = root / "custody"
        for directory in (home, profile, project, runtimes, custody):
            directory.mkdir(mode=0o700)
        # The production builder checks --version with its process environment.
        # Clear the probe runner first so even that check sees no real account.
        safe_path = os.environ.get("PATH", "/usr/bin:/bin")
        os.environ.clear()
        os.environ.update({"PATH": safe_path, "HOME": str(home),
                           "CLAUDE_CONFIG_DIR": str(profile),
                           "TMPDIR": str(root), "LANG": "C.UTF-8",
                           "TERM": "xterm-256color"})
        subprocess.run(["git", "init", "-q", str(project)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5,
                       env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
                            "GIT_CONFIG_GLOBAL": "/dev/null"})
        gateway = None
        server_thread = None
        if isolation == "bwrap":
            gateway = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RejectingAPI)
            server_thread = threading.Thread(target=gateway.serve_forever, daemon=True)
            server_thread.start()
        custodian_pid: int | None = None
        try:
            profile_state = {
                "hasCompletedOnboarding": True,
                "lastOnboardingVersion": "2.1.283",
                "theme": "dark",
                "projects": ({} if untrusted_diagnostic else
                             {str(project): {"hasTrustDialogAccepted": True}}),
            }
            settings_env = {"DISABLE_TELEMETRY": "1",
                            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
            if gateway is not None:
                _loopback_ready(gateway.server_address[1])
                endpoint = "http://127.0.0.1:%d" % gateway.server_address[1]
                settings_env.update({"ANTHROPIC_API_KEY": "offline-test-key",
                                     "ANTHROPIC_BASE_URL": endpoint})
            else:
                # A disposable managed-key fixture; socket denial makes every
                # provider connection fail before it can leave this process.
                profile_state["primaryApiKey"] = "sk-ant-offline-probe"
            _private_json(profile / ".claude.json", profile_state)
            _private_json(profile / "settings.json", {"env": settings_env})
            credential = root / "job-credential"
            fd = os.open(credential, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(b"offline-job-fixture-only")
            binary = shutil.which("claude")
            if binary is None:
                raise RuntimeError("pinned Claude CLI is unavailable")
            binary = str(Path(binary).resolve(strict=True))
            version = subprocess.run([binary, "--version"], env=dict(os.environ), check=True,
                                     capture_output=True, text=True,
                                     timeout=5).stdout.strip()
            if version != PINNED_VERSION:
                raise RuntimeError("Claude CLI differs from pinned version: " + version)
            repo = Path(__file__).resolve().parents[2]
            runtime_id, parent_uuid = str(uuid.uuid4()), str(uuid.uuid4())
            manifest = create_runtime_launch(
                root=str(runtimes), runtime_id=runtime_id, parent_uuid=parent_uuid,
                profile_ref="offline-fake", profile_config_dir=str(profile),
                session_name="offline-managed-probe", cwd=str(project),
                mcp_bridge_module=str(repo / "lane_managed_local_jobs.py"),
                custodian_dir=str(custody / "source"),
                job_socket=str(root / "unused-job.sock"),
                job_credential_file=str(credential), launch_mode="fresh",
                claude_executable=binary,
                inherited_environment={
                    "HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "TERM": "xterm-256color", "LANG": "C.UTF-8",
                    "TMPDIR": str(root),
                },
            )
            validate_runtime_launch(manifest)
            manifest_digest = runtime_launch_digest(manifest)
            launcher = SourceCustodianLauncher(manifest["custodian_dir"])
            intent = {"digest": manifest_digest,
                      "runtime_id": runtime_id, "parent_uuid": parent_uuid,
                      "cwd": str(project), "operation_id": None}
            started = launcher.launch(
                argv=manifest["argv"], environment=manifest["environment"],
                cwd=manifest["cwd"], intent=intent,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            custodian_pid = started["custodian"]["pid"]
            launcher.tty_resize(30, 100)
            if untrusted_diagnostic:
                # The disposable project is deliberately absent from the fake
                # profile's trust map. Observe the exact production launch and
                # forward Enter only after a trust-specific UI marker, never
                # after a bare chooser glyph or ordinary model prompt.
                capture = bytearray()
                started_at = time.monotonic()
                trust_at = None
                session_start_at = None
                prompt_at = None
                before = launcher.challenge()
                deadline = started_at + 28
                while time.monotonic() < deadline:
                    _capture_add(capture, launcher.tty_read())
                    rendered = capture.decode("utf-8", "replace")
                    rendered = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", rendered)
                    compact = re.sub(r"\s+", "", rendered)
                    trust_markers = ("Accessingworkspace:",
                                     "Quicksafetycheck:Isthisa projectyoucreatedoroneyoutrust?".replace(" ", ""),
                                     "Yes,Itrustthisfolder", "No,exit")
                    if (trust_at is None and all(marker in compact for marker in trust_markers)
                            and str(project).replace(" ", "") in compact):
                        trust_at = round(time.monotonic() - started_at, 3)
                        break
                    before = launcher.challenge()
                    if session_start_at is None and before["session_start"] is not None:
                        session_start_at = round(time.monotonic() - started_at, 3)
                    if prompt_at is None and before["prompt_ready"]:
                        prompt_at = round(time.monotonic() - started_at, 3)
                    if before["source_exit"] is not None:
                        break
                    time.sleep(.05)
                initial_screen = _sanitized_screen(capture, root)
                before = launcher.challenge()
                entered = False
                down_forwarded = False
                selected_confirm = False
                navigation_screen = None
                after = before
                if trust_at is not None and before["source_exit"] is None:
                    # This pinned chooser remounts with default No after a
                    # 150 ms startup epoch. Let that settle before navigation;
                    # selecting Yes during the held epoch is not stable.
                    time.sleep(.28)
                    _capture_add(capture, launcher.tty_read())
                    before = launcher.challenge()
                    # This pinned chooser focuses `No, exit` by default.
                    # Down selects the confirm option; inspect the fresh UI
                    # before Enter so the probe cannot submit a model turn.
                    if before["source_exit"] is None and before["startup_trust_state"] == "offered":
                        launcher.tty_write(b"\x1b[B")
                        down_forwarded = True
                    navigation_capture = bytearray()
                    nav_deadline = time.monotonic() + 1
                    while time.monotonic() < nav_deadline:
                        _capture_add(navigation_capture, launcher.tty_read())
                        navigation_screen = _sanitized_screen(navigation_capture, root)
                        selected_confirm = any(
                            re.search(r"❯\s*Yes,\s*I\s*trust\s*this\s*folder", line)
                            for line in navigation_screen["last_lines"])
                        if selected_confirm:
                            break
                        time.sleep(.05)
                    _capture_add(capture, navigation_capture)
                if selected_confirm and before["source_exit"] is None:
                    launcher.tty_write(b"\r")
                    entered = True
                    deadline = time.monotonic() + 7
                    while time.monotonic() < deadline:
                        _capture_add(capture, launcher.tty_read())
                        after = launcher.challenge()
                        if session_start_at is None and after["session_start"] is not None:
                            session_start_at = round(time.monotonic() - started_at, 3)
                        if prompt_at is None and after["prompt_ready"]:
                            prompt_at = round(time.monotonic() - started_at, 3)
                        if after["source_exit"] is not None or after["prompt_ready"]:
                            break
                        time.sleep(.05)
                startup_ready = bool(entered and after["session_start"] is not None and
                                     after["prompt_ready"] and not after["turn_busy"] and
                                     not after["submission_pending"])
                exit_requested = False
                final = after
                if startup_ready:
                    operation_id = str(uuid.uuid4())
                    launcher.fence(operation_id=operation_id,
                                   parent_uuid=parent_uuid, runtime_id=runtime_id)
                    launcher.request_exit(operation_id=operation_id,
                                          parent_uuid=parent_uuid, runtime_id=runtime_id)
                    exit_requested = True
                    exit_deadline = time.monotonic() + 8
                    while time.monotonic() < exit_deadline:
                        _capture_add(capture, launcher.tty_read())
                        final = launcher.challenge()
                        if final["source_exit"] is not None and final["drained"]:
                            break
                        time.sleep(.05)
                journal = json.loads((Path(manifest["custodian_dir"]) /
                                      "custodian.json").read_bytes())
                source_exit = final["source_exit"]
                complete = bool(startup_ready and exit_requested and
                                source_exit is not None and
                                source_exit["pid"] == started["source"]["pid"] and
                                source_exit["exited"] is True and
                                source_exit["signaled"] is False and
                                os.waitstatus_to_exitcode(source_exit["status"]) == 0 and
                                final["drained"] is True and final["phase"] == "drained" and
                                journal["exit_requested"] is True and
                                journal["exit_dispatched"] is True)
                print(json.dumps({
                    "schema": "managed-shared-cli-untrusted-startup-diagnostic-v1",
                    "complete": complete,
                    "exact_managed_route": True,
                    "isolation": isolation, "isolation_policy": policy,
                    "cli_sha256": manifest["cli_executable_digest"],
                    "runtime_manifest_sha256": manifest_digest,
                    "fixture": "fresh-fake-profile-untrusted-project",
                    "trust_marker_seen": trust_at is not None,
                    "trust_down_forwarded": down_forwarded,
                    "confirm_selection_observed": selected_confirm,
                    "trust_enter_forwarded": entered,
                    "initial_screen": initial_screen,
                    "navigation_screen": navigation_screen,
                    "after_screen": _sanitized_screen(capture, root),
                    "first_seen_seconds": {"trust": trust_at,
                                           "session_start": session_start_at,
                                           "prompt_ready": prompt_at},
                    "before": {"session_start": before["session_start"] is not None,
                               "prompt_ready": before["prompt_ready"],
                               "turn_busy": before["turn_busy"],
                               "turn_sequence": before["turn_sequence"]},
                    "after": {"session_start": after["session_start"] is not None,
                              "prompt_ready": after["prompt_ready"],
                              "turn_busy": after["turn_busy"],
                              "submission_pending": after["submission_pending"],
                              "startup_trust_state": after["startup_trust_state"],
                              "turn_sequence": after["turn_sequence"],
                              "source_exit": after["source_exit"] is not None},
                    "provider_attempts": "not-measured",
                    "model_prompt_submitted": False,
                    "owned_exit_requested": exit_requested,
                    "exit_dispatched": journal["exit_dispatched"],
                    "source_exit_code": (os.waitstatus_to_exitcode(source_exit["status"])
                                         if source_exit is not None else None),
                    "drained_after_echild": final["drained"],
                    "startup_diagnostic": _startup_diagnostics(
                        custodian_pid=custodian_pid, source=started["source"],
                        project=project, profile=profile, challenge=after),
                }, sort_keys=True))
                return 0 if complete else 1
            capture = bytearray()
            session_start = None
            prompt_ready = False
            first_title_at = None
            first_prompt_at = None
            first_session_start_at = None
            probe_started_at = time.monotonic()
            initial_deadline = time.monotonic() + 30
            while time.monotonic() < initial_deadline:
                _capture_add(capture, launcher.tty_read())
                if first_title_at is None and b"Claude" in capture:
                    first_title_at = round(time.monotonic() - probe_started_at, 3)
                if first_prompt_at is None and PROMPT in capture:
                    first_prompt_at = round(time.monotonic() - probe_started_at, 3)
                observed = launcher.challenge()
                session_start = observed["session_start"]
                if first_session_start_at is None and session_start is not None:
                    first_session_start_at = round(time.monotonic() - probe_started_at, 3)
                if session_start is not None and observed["prompt_ready"]:
                    prompt_ready = True
                    break
                if observed["source_exit"] is not None:
                    break
                time.sleep(.05)
            exit_requested = False
            final = launcher.challenge()
            if prompt_ready:
                operation_id = str(uuid.uuid4())
                launcher.fence(operation_id=operation_id,
                               parent_uuid=parent_uuid, runtime_id=runtime_id)
                launcher.request_exit(operation_id=operation_id,
                                      parent_uuid=parent_uuid, runtime_id=runtime_id)
                exit_requested = True
                exit_deadline = time.monotonic() + 8
                while time.monotonic() < exit_deadline:
                    _capture_add(capture, launcher.tty_read())
                    final = launcher.challenge()
                    if final["source_exit"] is not None and final["drained"]:
                        break
                    time.sleep(.05)
            _capture_add(capture, launcher.tty_read())
            final = launcher.challenge()
            source_exit = final["source_exit"]
            journal = json.loads((Path(manifest["custodian_dir"]) /
                                  "custodian.json").read_bytes())
            with _RejectingAPI.lock:
                api_calls = list(_RejectingAPI.calls) if gateway is not None else None
            complete = bool(
                session_start is not None and prompt_ready and exit_requested and
                source_exit is not None and source_exit["pid"] == started["source"]["pid"] and
                source_exit["exited"] is True and source_exit["signaled"] is False and
                os.waitstatus_to_exitcode(source_exit["status"]) == 0 and
                final["drained"] is True and final["phase"] == "drained" and
                journal["exit_requested"] is True and journal["exit_dispatched"] is True and
                journal["event_count"] >= 1 and (api_calls is None or not api_calls)
            )
            diagnostic = None
            if not complete:
                diagnostic = _startup_diagnostics(
                    custodian_pid=custodian_pid, source=started["source"],
                    project=project, profile=profile, challenge=final)
                diagnostic["screen"] = _sanitized_screen(capture, root)
                banner_at = capture.find(b"Claude")
                diagnostic["banner_raw_hex"] = (
                    capture[max(0, banner_at - 16):banner_at + 128].hex()
                    if banner_at >= 0 else None)
                diagnostic["first_seen_seconds"] = {
                    "title": first_title_at, "prompt": first_prompt_at,
                    "session_start": first_session_start_at,
                }
            print(json.dumps({
                "schema": "managed-shared-cli-offline-probe-v1",
                "complete": complete, "isolation": isolation,
                "isolation_policy": policy,
                "auth_fixture": ("fake-profile-settings-env" if gateway is not None else
                                 "fake-profile-primaryApiKey"),
                "provider_attempts": ("counted-by-rejecting-loopback" if gateway is not None
                                      else "not-measured"),
                "stop_event_proved": False,
                "complete_scope": "SessionStart, idle prompt, owned exit, source drain only",
                "cli_version": version,
                "cli_sha256": manifest["cli_executable_digest"],
                "runtime_manifest_sha256": runtime_launch_digest(manifest),
                "session_start_seen": session_start is not None,
                "session_start_source": session_start.get("source") if session_start else None,
                "prompt_ready": prompt_ready, "owned_exit_requested": exit_requested,
                "exit_dispatched": journal["exit_dispatched"],
                "source_exited_normally": bool(source_exit and source_exit["exited"] and
                                               not source_exit["signaled"]),
                "source_exit_code": (os.waitstatus_to_exitcode(source_exit["status"])
                                     if source_exit is not None else None),
                "drained_after_echild": final["drained"],
                "custodian_phase": final["phase"],
                "custodian_event_count": journal["event_count"],
                "fake_api_calls": api_calls,
                "bounded_screen_sha256": hashlib.sha256(capture).hexdigest(),
                "main_ui_title_seen": b"Claude Code" in capture,
                "prompt_marker_seen": PROMPT in capture,
                "screen_bytes_retained": len(capture),
                "startup_diagnostic": diagnostic,
            }, sort_keys=True))
            return 0 if complete else 1
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            if custodian_pid is None:
                custodian_pid = _recorded_custodian(custody / "source")
            _stop_owned(custodian_pid)
            if gateway is not None and server_thread is not None:
                gateway.shutdown()
                gateway.server_close()
                server_thread.join(timeout=2)


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--inside-offline-net":
        signal.signal(signal.SIGALRM, _timeout)
        signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS - 5)
        return _inside("bwrap", sys.argv[2])
    if sys.argv[1:] == ["--inside-seccomp"]:
        signal.signal(signal.SIGALRM, _timeout)
        signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS - 5)
        try:
            policy = _install_seccomp()
        except (OSError, RuntimeError) as exc:
            print(json.dumps({"schema": "managed-shared-cli-offline-probe-v1",
                              "complete": False, "stage": "seccomp-isolation",
                              "claude_launched": False,
                              "reason": str(exc)[:240]}, sort_keys=True))
            return 2
        return _inside("seccomp", policy=policy)
    if sys.argv[1:] == ["--inside-seccomp-untrusted"]:
        signal.signal(signal.SIGALRM, _timeout)
        signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS - 5)
        try:
            policy = _install_seccomp()
        except (OSError, RuntimeError) as exc:
            print(json.dumps({"schema": "managed-shared-cli-untrusted-startup-diagnostic-v1",
                              "claude_launched": False, "reason": str(exc)[:240]},
                             sort_keys=True))
            return 2
        return _inside("seccomp", policy=policy, untrusted_diagnostic=True)
    if sys.argv[1:] not in ([], ["--isolation", "seccomp"],
                           ["--isolation", "seccomp", "--untrusted-project"]):
        raise SystemExit("usage: managed_cli_shared_session_probe.py "
                         "[--isolation seccomp [--untrusted-project]]")
    if sys.platform != "linux":
        raise RuntimeError("Linux subreaper contract is required")
    if sys.argv[:3] == [sys.argv[0], "--isolation", "seccomp"]:
        with tempfile.TemporaryDirectory(prefix="managed-seccomp-outer-") as temporary:
            outer = Path(temporary)
            home, config = outer / "home", outer / "config"
            home.mkdir(mode=0o700)
            config.mkdir(mode=0o700)
            environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                           "HOME": str(home), "CLAUDE_CONFIG_DIR": str(config),
                           "TMPDIR": str(outer), "LANG": "C.UTF-8",
                           "TERM": "xterm-256color"}
            inside_flag = (
                "--inside-seccomp-untrusted" if
                sys.argv[1:] == ["--isolation", "seccomp", "--untrusted-project"] else
                "--inside-seccomp")
            command = [sys.executable, str(Path(__file__).resolve()), inside_flag]
            result = subprocess.run(command, env=environment, timeout=MAX_SECONDS,
                                    check=False, capture_output=True, text=True)
            if result.stdout:
                sys.stdout.write(result.stdout[:65536])
            if result.stderr:
                sys.stderr.write(result.stderr[:65536])
            return result.returncode
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        raise RuntimeError("bubblewrap is required to isolate all external network")
    parent_namespace = os.readlink("/proc/self/ns/net")
    command = [bwrap, "--die-with-parent", "--unshare-net", "--bind", "/", "/", "--",
               sys.executable, str(Path(__file__).resolve()),
               "--inside-offline-net", parent_namespace]
    result = subprocess.run(command, timeout=MAX_SECONDS, check=False,
                            capture_output=True, text=True)
    if result.stdout:
        sys.stdout.write(result.stdout[:65536])
    if result.stderr.lstrip().startswith("bwrap:") and not result.stdout:
        detail = result.stderr.lower()
        reason = ("bubblewrap could not create an isolated network namespace"
                  if "no permissions to create new namespace" in detail else
                  "bubblewrap refused isolated startup")
        print(json.dumps({
            "schema": "managed-shared-cli-offline-probe-v1",
            "complete": False, "stage": "network-isolation",
            "claude_launched": False, "reason": reason,
            "isolation_exit_code": result.returncode,
        }, sort_keys=True))
        return 2
    if result.stderr:
        sys.stderr.write(result.stderr[:65536])
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"schema": "managed-shared-cli-offline-probe-v1",
                          "complete": False, "error": str(exc)}, sort_keys=True),
              file=sys.stderr)
        raise SystemExit(2)
