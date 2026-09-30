# SPDX-License-Identifier: Apache-2.0
"""The prompt guard respects process launch mode without lane infrastructure."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None, reason="the guard is a bash command")]


@pytest.fixture
def guard_launch_mode(tmp_path):
    home = tmp_path / "home"
    projects = home / "projects"
    projects.mkdir(parents=True)
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    tmux_log = tmp_path / "tmux.log"
    tmux = fakebin / "tmux"
    tmux.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$GUARD_TMUX_LOG"\nexit 1\n')
    tmux.chmod(0o755)
    probe_log = tmp_path / "identity-probes.log"
    for name in ("git", "hostname", "readlink", "sed"):
        probe = fakebin / name
        probe.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$GUARD_PROBE_LOG"\nexit 1\n')
        probe.chmod(0o755)
    env = {name: value for name, value in os.environ.items()
           if not name.startswith(("LANES_", "CLAUDE_", "WORKBENCHES_", "TMUX"))}
    env.update(HOME=str(home), AGENT_PROTOCOL_ROOT=str(home / ".agents"),
               PROJECTS_ROOT=str(projects), GUARD_TMUX_LOG=str(tmux_log),
               GUARD_PROBE_LOG=str(probe_log),
               PATH=str(fakebin) + os.pathsep + env.get("PATH", ""))
    payload = json.dumps({"session_id": "profile-session", "cwd": str(projects),
                          "prompt": "do the work", "hook_event_name": "UserPromptSubmit"})

    def run(marker, *, command="guard", hook_input=payload, prefix_args=(), extra_args=()):
        child_env = dict(env)
        if marker is not None:
            child_env["CLAUDE_NO_LANE"] = marker
        return subprocess.run(["bash", str(REPO / "lanes-edit.sh"), *prefix_args, command, *extra_args],
                              input=hook_input, text=True, capture_output=True,
                              env=child_env, timeout=10, check=False)

    return run, home, tmux_log, probe_log


@pytest.mark.parametrize("hook_input", [None, "not JSON", ""])
def test_guard_launch_mode_profile_session_skips_identity_reads(guard_launch_mode, hook_input):
    run, home, tmux_log, probe_log = guard_launch_mode
    result = run("1") if hook_input is None else run("1", hook_input=hook_input)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert not tmux_log.exists()
    assert not probe_log.exists()
    assert not (home / ".agents").exists()
    assert not (home / ".claude").exists()


@pytest.mark.parametrize("marker", [None, "", "0", "true", "2"])
def test_guard_launch_mode_other_values_keep_enforcement(guard_launch_mode, marker):
    run, _, _, _ = guard_launch_mode
    result = run(marker)
    assert result.returncode == 2, result.stderr
    assert "THE NAME GUARD REFUSES" in result.stderr


def test_guard_launch_mode_does_not_exempt_other_commands(guard_launch_mode):
    run, _, _, _ = guard_launch_mode
    result = run("1", command="verify-row")
    assert result.returncode == 1, result.stderr
    assert "openRepoTools wip init" in result.stderr


@pytest.mark.parametrize("flag", ["--no-sweep", "--sweep", "--no-github"])
def test_guard_launch_mode_global_flags_keep_early_exemption(guard_launch_mode, flag):
    run, _, tmux_log, probe_log = guard_launch_mode
    result = run("1", prefix_args=(flag,))
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert not tmux_log.exists()
    assert not probe_log.exists()


def test_guard_launch_mode_invalid_arguments_still_refuse(guard_launch_mode):
    run, _, tmux_log, probe_log = guard_launch_mode
    result = run("1", extra_args=("unexpected",))
    assert result.returncode == 2
    assert "usage: guard" in result.stderr
    assert not tmux_log.exists()
    assert not probe_log.exists()
