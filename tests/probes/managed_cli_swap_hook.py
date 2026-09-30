# SPDX-License-Identifier: Apache-2.0
"""Isolated, model-free CLI probe for slash-command expansion interception.

Runs pinned Claude against a disposable fake API endpoint with no real account
configuration. Prints only a bounded verdict; the hook input and CLI screen
remain in a private artifact directory for diagnosis.
"""

from __future__ import annotations

import http.server
import hashlib
import contextlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import pexpect
import psutil


class _Gateway(http.server.BaseHTTPRequestHandler):
    calls = 0

    def do_POST(self):
        type(self).calls += 1
        self.send_response(503)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        type(self).calls += 1
        self.send_response(503)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args):
        pass


def main() -> int:
    unrestricted_diagnostic = sys.argv[1:] == ["--unrestricted-diagnostic"]
    plugin_diagnostic = sys.argv[1:] == ["--plugin-diagnostic"]
    if sys.argv[1:] and not (unrestricted_diagnostic or plugin_diagnostic):
        raise SystemExit("usage: managed_cli_swap_hook.py [--unrestricted-diagnostic|--plugin-diagnostic]")
    _Gateway.calls = 0
    scratch = pathlib.Path(__file__).resolve().parents[2] / ".scratch-l1-handoff"
    scratch.mkdir(mode=0o700, exist_ok=True)
    temporary = tempfile.mkdtemp(prefix="cli-swap-hook-", dir=str(scratch))
    with contextlib.nullcontext(temporary):
        root = pathlib.Path(temporary)
        root.chmod(0o700)
        home, config, project = root / "home", root / "config", root / "project"
        for directory in (home, config, config / "commands",
                          config / "skills" / "swap",
                          project / ".claude" / "commands",
                          project / ".claude" / "skills" / "swap"):
            directory.mkdir(parents=True, mode=0o700)
        # A fresh config otherwise stops at the first-run theme selector;
        # this isolated file carries no account or credential material.
        (config / ".claude.json").write_text(json.dumps({
            "hasCompletedOnboarding": True,
            "lastOnboardingVersion": "2.1.283",
            "theme": "dark",
            "projects": {str(project): {"hasTrustDialogAccepted": True}},
        }), encoding="utf-8")
        command_text = (
            "---\ndescription: local swap control test\n---\n"
            "This command must not reach a model.\n")
        (project / ".claude" / "commands" / "swap.md").write_text(
            command_text, encoding="utf-8")
        (config / "commands" / "swap.md").write_text(
            command_text, encoding="utf-8")
        skill_text = (
            "---\nname: swap\ndescription: local swap control test\n"
            "disable-model-invocation: true\n---\n"
            "This skill must not reach a model.\n")
        (config / "skills" / "swap" / "SKILL.md").write_text(
            skill_text, encoding="utf-8")
        (project / ".claude" / "skills" / "swap" / "SKILL.md").write_text(
            skill_text, encoding="utf-8")
        plugin = root / "swap-plugin"
        (plugin / ".claude-plugin").mkdir(parents=True, mode=0o700)
        (plugin / "commands").mkdir(mode=0o700)
        (plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "swap", "description": "offline slash interception fixture"}),
            encoding="utf-8",
        )
        (plugin / "commands" / "swap.md").write_text(command_text, encoding="utf-8")
        # Give the disposable project its own git root so the CLI does not
        # climb into the feature worktree and ignore this fixture's commands.
        subprocess.run(["git", "init", "-q", str(project)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        hook_input = root / "hook-input.json"
        hook = root / "hook.py"
        hook.write_text(
            "import json,sys\n"
            "from pathlib import Path\n"
            "data=sys.stdin.buffer.read(65537)\n"
            "if len(data)>65536: sys.exit(2)\n"
            "Path(%r).write_bytes(data)\n" % str(hook_input) +
            "print(json.dumps({'decision':'block','reason':'local-swap-intercepted'}))\n",
            encoding="utf-8",
        )
        settings = root / "settings.json"
        settings.write_text(json.dumps({
            "hooks": {"UserPromptExpansion": [{
                "matcher": "swap:swap" if plugin_diagnostic else "swap", "hooks": [{
                    "type": "command", "command": "python3 " + str(hook),
                    "timeout": 5,
                }],
            }]},
        }), encoding="utf-8")
        mcp = root / "mcp.json"
        mcp.write_text('{"mcpServers":{}}', encoding="utf-8")
        gateway = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Gateway)
        thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        thread.start()
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
        executable = shutil.which("claude", path=environment["PATH"])
        if executable is None:
            raise RuntimeError("Claude CLI is not installed on the isolated PATH")
        executable_path = pathlib.Path(executable).resolve(strict=True)
        digest = hashlib.sha256()
        with executable_path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        executable_digest = digest.hexdigest()
        version = subprocess.run(
            [str(executable_path), "--version"], env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5, check=True, text=True,
        ).stdout.strip()
        if not version.startswith("2.1.283 "):
            raise RuntimeError("installed Claude CLI is outside the pinned version")
        child = None
        child_group = None
        screen = []
        try:
            cli_args = ["--tools", "Read,Edit,Write,Glob,Grep,Agent",
                        "--disallowedTools", "Bash", "PowerShell",
                        "--settings", str(settings), "--strict-mcp-config",
                        "--mcp-config", str(mcp)]
            if not unrestricted_diagnostic:
                cli_args.append("--restricted")
            if plugin_diagnostic:
                cli_args.extend(["--plugin-dir", str(plugin)])
            cli_args.extend(["--debug-file", str(root / "cli-debug.log")])
            child = pexpect.spawn(
                str(executable_path), cli_args,
                cwd=str(project), env=environment, encoding="utf-8", timeout=2,
                dimensions=(30, 100),
            )
            child_group = os.getpgid(child.pid)
            # Allow initial TUI setup, then submit the direct slash command.
            end = time.monotonic() + 15
            prompt_ready = False
            fake_key_selected = False
            while time.monotonic() < end:
                try:
                    child.expect(["Choose", "Trust", "Detected", "Try", "❯"],
                                 timeout=1)
                    screen.append(child.before[-1024:])
                    if child.after == "Choose":
                        child.send("1\r")
                        continue
                    if child.after == "Trust":
                        child.send("y\r")
                        continue
                    if child.after == "Detected":
                        child.send("\x1b[A")
                        time.sleep(0.1)
                        child.send("\r")
                        fake_key_selected = True
                        continue
                    if child.after == "❯" and not fake_key_selected:
                        continue
                    prompt_ready = True
                    break
                except pexpect.TIMEOUT:
                    screen.append(child.before[-1024:])
                    if not child.isalive():
                        break
            if child.isalive() and prompt_ready:
                child.send("/swap\r")
            end = time.monotonic() + 15
            while time.monotonic() < end and not hook_input.exists():
                try:
                    child.expect("local-swap-intercepted", timeout=0.5)
                    screen.append(child.before[-1024:] + child.after)
                    break
                except pexpect.TIMEOUT:
                    screen.append(child.before[-1024:])
                    if not child.isalive():
                        break
            if hook_input.exists() and not any(
                    "local-swap-intercepted" in item for item in screen):
                try:
                    child.expect("local-swap-intercepted", timeout=5)
                    screen.append(child.before[-1024:] + child.after)
                except (pexpect.TIMEOUT, pexpect.EOF):
                    screen.append(child.before[-1024:])
            if child.isalive():
                child.sendcontrol("c")
                child.send("/exit\r")
                try:
                    child.expect(pexpect.EOF, timeout=2)
                except pexpect.TIMEOUT:
                    child.terminate(force=True)
            event = None
            if hook_input.exists():
                raw = hook_input.read_bytes()
                if len(raw) <= 65536:
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        pass
            summary = {
                "schema_version": 1,
                "restricted": not unrestricted_diagnostic,
                "explicit_plugin": plugin_diagnostic,
                "cli_version": version,
                "cli_executable_sha256": executable_digest,
                "hook_observed": isinstance(event, dict),
                "prompt_ready": prompt_ready,
                "event_name": event.get("hook_event_name") if isinstance(event, dict) else None,
                "command_name": event.get("command_name") if isinstance(event, dict) else None,
                "expanded_prompt": event.get("prompt") if isinstance(event, dict) else None,
                "expansion_type": event.get("expansion_type") if isinstance(event, dict) else None,
                "fake_api_request_count": _Gateway.calls,
                "block_message_seen": any("local-swap-intercepted" in item for item in screen),
                "cli_exited": not child.isalive(),
            }
            (root / "screen.txt").write_text("".join(screen)[-4096:], encoding="utf-8")
            (root / "screen.txt").chmod(0o600)
            summary["artifact_dir"] = str(root.relative_to(scratch.parent))
            summary["remaining_process_group_members"] = _remaining_group(child_group)
            (root / "summary.json").write_text(
                json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
            (root / "summary.json").chmod(0o600)
            if hook_input.exists():
                hook_input.chmod(0o600)
            print(json.dumps(summary, sort_keys=True))
            expected_command = "swap:swap" if plugin_diagnostic else "swap"
            expected_prompt = "/swap:swap" if plugin_diagnostic else "/swap"
            return 0 if (summary["hook_observed"] and
                         summary["command_name"] == expected_command and
                         summary["expanded_prompt"] == expected_prompt and
                         summary["event_name"] == "UserPromptExpansion" and
                         summary["expansion_type"] == "slash_command" and
                         summary["fake_api_request_count"] == 0 and
                         summary["block_message_seen"] and summary["cli_exited"] and
                         summary["remaining_process_group_members"] == 0) else 1
        finally:
            if child is not None and child.isalive():
                child.terminate(force=True)
            if child_group is not None and child_group != os.getpgrp():
                for process in _group_members(child_group):
                    try:
                        process.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                _gone, alive = psutil.wait_procs(_group_members(child_group), timeout=1)
                for process in alive:
                    try:
                        process.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                psutil.wait_procs(alive, timeout=1)
            gateway.shutdown()
            gateway.server_close()
            thread.join(timeout=2)


def _group_members(group: int):
    members = []
    for process in psutil.process_iter(["pid"]):
        try:
            if os.getpgid(process.pid) == group:
                members.append(process)
        except (OSError, psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return members


def _remaining_group(group: int) -> int:
    return len(_group_members(group))


if __name__ == "__main__":
    raise SystemExit(main())
