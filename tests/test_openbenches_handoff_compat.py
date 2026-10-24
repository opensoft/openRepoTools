# SPDX-License-Identifier: Apache-2.0
"""Old/new launcher environment compatibility for the two handoff surfaces.

Every variable is exercised legacy-only, new-only, with equal dual values and
with conflicting dual values. The skill cases run its own fenced shell blocks;
the command cases run the real `lane-handoff` against an isolated register and
prove that a conflict is refused before any handoff or lane write.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from test_handoff_skill_72_80 import (
    SHELLS,
    Sandbox as SkillSandbox,
    Verb,
    _cut,
    _one_block,
    window_block,
)
from test_lane_start_claude_current import LANE, Sandbox as LaneSandbox, _write


pytestmark = [
    WINDOWS_SKIP,
    pytest.mark.skipif(shutil.which("bash") is None, reason="handoff is bash"),
    pytest.mark.skipif(shutil.which("git") is None, reason="the register is git"),
]

SUFFIXES = ("WINDOW_REF", "WINDOW_ID", "LANE_DIR")
MODES = ("legacy-only", "new-only", "equal-dual", "conflicting-dual")


def _names(suffix):
    return f"OPENBENCHES_CLAUDE_{suffix}", f"WORKBENCHES_CLAUDE_{suffix}"


def _clear_pair(env, suffix):
    for name in _names(suffix):
        env.pop(name, None)


def _set_pair(env, suffix, mode, new_value, legacy_value):
    new_name, legacy_name = _names(suffix)
    _clear_pair(env, suffix)
    if mode == "legacy-only":
        env[legacy_name] = legacy_value
    elif mode == "new-only":
        env[new_name] = new_value
    elif mode == "equal-dual":
        env[new_name] = new_value
        env[legacy_name] = new_value
    else:
        env[new_name] = new_value
        env[legacy_name] = legacy_value


def _assert_conflict(proc, suffix):
    new_name, legacy_name = _names(suffix)
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "AFTER" not in proc.stdout, proc.stdout
    assert new_name in proc.stderr, proc.stderr
    assert legacy_name in proc.stderr, proc.stderr
    assert "conflicting values" in proc.stderr, proc.stderr
    assert "unset the incorrect one" in proc.stderr, proc.stderr
    assert "Nothing was renamed or written" in proc.stderr, proc.stderr


def _environment_block():
    return "\n".join(_one_block("check_claude_env_dual() {")) + "\n"


def _directory_block():
    first = 'dir=""; dir_read_failed='
    return _cut(_one_block(first), first, "fi", exact_last=True)


@pytest.fixture
def skill_box(tmp_path: Path) -> SkillSandbox:
    return SkillSandbox(tmp_path)


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("suffix", SUFFIXES)
@pytest.mark.parametrize("mode", MODES)
def test_openbenches_handoff_skill_environment_matrix(skill_box, shell, suffix, mode):
    values = {
        "WINDOW_REF": ("new:7", "legacy:4"),
        "WINDOW_ID": ("@77", "@44"),
        "LANE_DIR": ("/new/checkout", "/legacy/checkout"),
    }
    new_value, legacy_value = values[suffix]
    env = {}
    _set_pair(env, suffix, mode, new_value, legacy_value)
    script = _environment_block()
    if suffix == "LANE_DIR":
        skill_box.stub({"lane-dir": Verb(8)})
        script = f"L={shlex.quote(str(skill_box.helper))}\nlane=repoOB-1\n" + script
        script += _directory_block() + "printf 'AFTER [%s]\\n' \"$dir\"\n"
        expected = new_value if mode in ("new-only", "equal-dual") else legacy_value
    else:
        if suffix == "WINDOW_REF":
            env["WORKBENCHES_CLAUDE_WINDOW_ID"] = "@9"
            selected = new_value if mode in ("new-only", "equal-dual") else legacy_value
            expected = f"{selected} @9"
        else:
            env["WORKBENCHES_CLAUDE_WINDOW_REF"] = "sess:1"
            selected = new_value if mode in ("new-only", "equal-dual") else legacy_value
            expected = f"sess:1 {selected}"
        script += "tmux() { printf '\\n'; }\n" + window_block()
        script += "printf 'AFTER [%s]\\n' \"$win\"\n"
    proc = skill_box.run(shell, script, env)
    if mode == "conflicting-dual":
        _assert_conflict(proc, suffix)
        assert skill_box.logged() == [], skill_box.logged()
    else:
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        assert proc.stdout == f"AFTER [{expected}]\n", (proc.stdout, proc.stderr)
        assert proc.stderr == "", proc.stderr


@pytest.fixture
def handoff_box(tmp_path: Path):
    box = LaneSandbox(tmp_path)
    for suffix in SUFFIXES:
        _clear_pair(box.env, suffix)
    box.env.update(
        LANES_LANE_STATE_ROOT=str(tmp_path / "state"),
        LANES_NO_FETCH="1",
        TMUX_PANE="%1",
    )
    box.resolver()
    initial = box.start("--no-launch")
    assert initial.returncode == 0, (initial.stdout, initial.stderr)
    row = next(
        line for line in (box.wip / "lanes" / "LANES.md").read_text().splitlines()
        if line.startswith(f"| `{LANE}`")
    )
    source = box.wip / row.split("|")[6].strip()
    _write(source, "# openBenches compatibility\n\nPreserved task.\n---\nHistory.\n", 0o600)
    box.git("-C", str(box.wip), "add", "--", str(source))
    box.git("-C", str(box.wip), "commit", "-qm", "seed handoff")
    box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    shutil.copy2(REPO / "lane-handoff", box.bin / "lane-handoff")
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(
        box.bin / "lanes-edit.sh",
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = lane-dir ]; then exit 8; fi\n"
        f"exec {shlex.quote(str(real))} \"$@\"\n",
    )
    return box, source


def _handoff_environment(box, suffix, mode):
    valid = {
        "WINDOW_REF": "testsess:0",
        "WINDOW_ID": "@1",
        "LANE_DIR": str(box.lane_dir),
    }
    wrong = {
        "WINDOW_REF": "othersess:9",
        "WINDOW_ID": "@9",
        "LANE_DIR": str(box.root / "wrong-checkout"),
    }
    env = {f"WORKBENCHES_CLAUDE_{name}": value for name, value in valid.items()}
    _set_pair(env, suffix, mode, wrong[suffix] if mode == "conflicting-dual" else valid[suffix], valid[suffix])
    return env


def _run_handoff(box, extra):
    env = dict(box.env)
    for suffix in SUFFIXES:
        _clear_pair(env, suffix)
    env.update(extra)
    env["LANE_HANDOFF_NO_TMUX"] = "1"
    return subprocess.run(
        [str(box.bin / "lane-handoff"), "--lane", LANE, "clear"],
        cwd=box.lane_dir,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize("suffix", SUFFIXES)
@pytest.mark.parametrize("mode", MODES)
def test_openbenches_lane_handoff_environment_matrix(handoff_box, suffix, mode):
    box, source = handoff_box
    before = {
        "source": source.read_bytes(),
        "log": box.lane_log(),
        "register": (box.wip / "lanes" / "LANES.md").read_bytes(),
        "commits": box.commits(),
    }
    proc = _run_handoff(box, _handoff_environment(box, suffix, mode))
    if mode == "conflicting-dual":
        _assert_conflict(proc, suffix)
        assert source.read_bytes() == before["source"]
        assert box.lane_log() == before["log"]
        assert (box.wip / "lanes" / "LANES.md").read_bytes() == before["register"]
        assert box.commits() == before["commits"]
        return
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    paused = [line for line in box.lane_log().splitlines() if line.startswith("PAUSED")]
    assert len(paused) == 1, box.lane_log()
    assert "; window testsess:0 @1;" in paused[0], paused[0]
    assert f"; dir {box.lane_dir};" in paused[0], paused[0]
