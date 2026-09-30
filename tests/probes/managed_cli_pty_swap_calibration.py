# SPDX-License-Identifier: Apache-2.0
"""Offline, model-free Claude PTY prompt and local /swap exit calibration.

The literal /swap input is intercepted by this probe and never reaches Claude.
Only the built-in /exit is sent after an observed idle prompt. The disposable
configuration has a loopback API key and endpoint; every provider request is
counted and rejected. The JSON result reports bounded raw PTY byte windows.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import pexpect
import psutil


PINNED_VERSION = "2.1.283 (Claude Code)"
PROMPT = "❯".encode("utf-8")
MAX_CAPTURE = 128 * 1024


class _FakeAPI(http.server.BaseHTTPRequestHandler):
    calls: list[tuple[str, str]] = []

    def do_GET(self):
        type(self).calls.append(("GET", self.path[:128]))
        self.send_response(503)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        type(self).calls.append(("POST", self.path[:128]))
        self.send_response(503)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args):
        pass


def _append(capture: bytearray, data: bytes) -> None:
    capture.extend(data)
    if len(capture) > MAX_CAPTURE:
        del capture[:-MAX_CAPTURE]


def _sample(data: bytes) -> dict[str, str]:
    return {"base64": base64.b64encode(data).decode("ascii"),
            "repr": repr(data)}


def _owned_descendants(pid: int) -> list[psutil.Process]:
    try:
        return psutil.Process(pid).children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []


def _stop_owned(child: pexpect.spawn | None, descendants: list[psutil.Process]) -> None:
    if child is not None and child.isalive():
        child.terminate(force=True)
    for process in descendants:
        try:
            process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _, alive = psutil.wait_procs(descendants, timeout=1)
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    psutil.wait_procs(alive, timeout=1)


def main() -> int:
    if sys.argv[1:]:
        raise SystemExit("usage: managed_cli_pty_swap_calibration.py")
    _FakeAPI.calls = []
    with tempfile.TemporaryDirectory(prefix="claude-pty-cal-") as temporary:
        root = Path(temporary)
        home, config, project = root / "home", root / "config", root / "project"
        for directory in (home, config, project):
            directory.mkdir(mode=0o700)
        # This is a fresh, private CLI state file with no real seat or token.
        (config / ".claude.json").write_text(json.dumps({
            "hasCompletedOnboarding": True,
            "lastOnboardingVersion": "2.1.283",
            "theme": "dark",
            "projects": {str(project): {"hasTrustDialogAccepted": True}},
        }), encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(project)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        settings = root / "settings.json"
        settings.write_text(json.dumps({
            "permissions": {"deny": ["Bash", "PowerShell", "Edit", "Write"]},
            "enableAllProjectMcpServers": False,
        }), encoding="utf-8")
        mcp = root / "mcp.json"
        mcp.write_text('{"mcpServers":{}}', encoding="utf-8")
        gateway = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeAPI)
        server_thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        server_thread.start()
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(home), "CLAUDE_CONFIG_DIR": str(config),
            "XDG_CONFIG_HOME": str(config),
            "ANTHROPIC_API_KEY": "offline-test-key",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:%d" % gateway.server_address[1],
            "DISABLE_TELEMETRY": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
            "CLAUDE_CODE_DISABLE_AGENT_VIEW": "1",
        }
        child = None
        descendants: list[psutil.Process] = []
        try:
            binary = shutil.which("claude", path=environment["PATH"])
            if binary is None:
                raise RuntimeError("pinned Claude CLI is unavailable")
            executable = Path(binary).resolve(strict=True)
            version = subprocess.run(
                [str(executable), "--version"], env=environment, check=True,
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            if version != PINNED_VERSION:
                raise RuntimeError("installed Claude CLI is outside the pinned version")
            cli_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
            child = pexpect.spawn(
                str(executable), [
                    "--session-id", str(uuid.uuid4()), "--restricted",
                    "--tools", "Read,Glob,Grep,Agent", "--disallowedTools",
                    "Bash", "PowerShell", "Edit", "Write",
                    "--settings", str(settings), "--strict-mcp-config",
                    "--mcp-config", str(mcp),
                ], cwd=str(project), env=environment, encoding=None,
                timeout=1, dimensions=(30, 100),
            )
            capture = bytearray()
            milestones = []
            fake_key_selected = False
            main_ui_seen = False
            prompt_ready = False
            prompt_window = b""
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and child.isalive():
                try:
                    index = child.expect(
                        [b"Choose", b"Trust", b"Detected", b"Try",
                         b"Claude Code", PROMPT],
                        timeout=1,
                    )
                    _append(capture, child.before + child.after)
                    label = ("Choose", "Trust", "Detected", "Try",
                             "main-ui-title", "prompt")[index]
                    milestones.append({"event": label, "byte_offset": len(capture)})
                    if label == "Choose":
                        child.send(b"1\r")
                    elif label == "Trust":
                        child.send(b"y\r")
                    elif label == "Detected":
                        child.send(b"\x1b[A")
                        time.sleep(.1)
                        child.send(b"\r")
                        fake_key_selected = True
                    elif label == "main-ui-title" and fake_key_selected:
                        main_ui_seen = True
                    elif label == "prompt" and main_ui_seen:
                        prompt_ready = True
                        prompt_window = bytes(capture[-96:])
                        break
                except pexpect.TIMEOUT:
                    _append(capture, child.before)
                except pexpect.EOF:
                    _append(capture, child.before)
                    break
            if prompt_ready:
                # The PTY proxy has recognized this exact local command frame.
                # No byte of /swap is sent to the child.
                literal_input = b"/swap\r"
                assert literal_input == b"/swap\r"
                milestones.append({"event": "local-swap-intercept", "byte_offset": len(capture)})
                # Require a brief output-quiet interval after the main UI
                # prompt, so an auth selector's marker cannot qualify.
                quiet_deadline = time.monotonic() + 2
                while time.monotonic() < quiet_deadline:
                    try:
                        _append(capture, child.read_nonblocking(size=8192, timeout=.35))
                    except (pexpect.TIMEOUT, pexpect.EOF):
                        break
                idle_tail = bytes(capture[-768:])
                quiet_tail = bytes(capture[-96:])
                descendants = _owned_descendants(child.pid)
                exit_sent_at = time.monotonic()
                child.send(b"/exit\r")
                milestones.append({"event": "exit-input-sent", "byte_offset": len(capture),
                                   "bytes_hex": b"/exit\r".hex()})
                try:
                    child.expect(pexpect.EOF, timeout=8)
                    _append(capture, child.before)
                    exited_on_first_exit = True
                except pexpect.TIMEOUT:
                    _append(capture, child.before)
                    exited_on_first_exit = False
                exit_elapsed_ms = round((time.monotonic() - exit_sent_at) * 1000)
            else:
                idle_tail = bytes(capture[-768:])
                quiet_tail = bytes(capture[-96:])
                exited_on_first_exit = False
                exit_elapsed_ms = None
            if not descendants:
                descendants = _owned_descendants(child.pid)
            result = {
                "schema": "managed-cli-pty-swap-calibration-v1",
                "version": version, "cli_sha256": cli_sha256,
                "prompt_ready": prompt_ready,
                "fake_key_selected": fake_key_selected,
                "main_ui_seen": main_ui_seen,
                "local_swap_intercepted": prompt_ready,
                "exit_frame_hex": b"/exit\r".hex() if prompt_ready else None,
                "exit_elapsed_ms": exit_elapsed_ms,
                "exited_on_first_exit": exited_on_first_exit,
                "cli_alive_after_exit_wait": child.isalive(),
                "cli_exit_status": child.exitstatus,
                "cli_signal_status": child.signalstatus,
                "fake_api_calls": _FakeAPI.calls,
                "milestones": milestones[-20:],
                "idle_prompt_tail": _sample(idle_tail),
                "prompt_marker_window": _sample(prompt_window),
                "quiet_tail": _sample(quiet_tail),
                "post_exit_tail": _sample(bytes(capture[-768:])),
            }
            print(json.dumps(result, sort_keys=True))
            return 0 if (prompt_ready and exited_on_first_exit and
                         not child.isalive() and not _FakeAPI.calls) else 1
        finally:
            _stop_owned(child, descendants)
            gateway.shutdown()
            gateway.server_close()
            server_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
