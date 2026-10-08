# SPDX-License-Identifier: Apache-2.0
"""`lanes-edit.sh pathspec-check` - what a workspace commit would stage that
is bytecode, a cache or an environment (opensoft/openRepoTools#162) - held
to three of #170's findings, against the REAL helper and a fixture
workspace (`test_lane_worktrees._real_estate`), in seconds rather than the
shell suite's hour:

  * G4: the `.gitignore` repair command it offers names the workspace path
    quoted for the shell, so a path with a space in it still works pasted;
  * E1: a STAGED bytecode file whose name is not ASCII is refused - `git
    diff --name-only` C-quotes such a path, and the closing quote hid the
    `.pyc`;
  * E2: the `add '<path>'` lines it parses are read in the C locale, never
    in whatever language the workstation's git speaks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import WINDOWS_SKIP
import test_lane_worktrees as LW

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="the helper is bash, and it reads git")]


def _workspace(tmp_path: Path, name: str = "wip") -> tuple:
    """The fixture estate's workspace, moved to `projects/<name>` and named
    there in `workspace.yaml`."""
    e, wip = LW._real_estate(tmp_path, "eagle")
    if name != "wip":
        moved = e.projects / name
        shutil.move(str(wip), str(moved))
        yaml = Path(e.env["AGENT_PROTOCOL_ROOT"]) / "workspace.yaml"
        yaml.write_text(yaml.read_text().replace(f"path: {wip}\n", f"path: {moved}\n"))
        wip = moved
    return e, wip


def _check(e, *paths, env: dict | None = None) -> subprocess.CompletedProcess:
    child = dict(e.env)
    child.update(env or {})
    return subprocess.run(["bash", str(LW.LANES_EDIT), "pathspec-check", *paths],
                          capture_output=True, env=child, check=False)


def test_the_offered_gitignore_command_survives_a_space_in_the_path(tmp_path):
    e, wip = _workspace(tmp_path, "my wip")
    (wip / "handoffs" / "x" / "__pycache__").mkdir(parents=True)
    (wip / "handoffs" / "x" / "__pycache__" / "m.cpython-312.pyc").write_bytes(b"\0")
    proc = _check(e, "handoffs/x")
    err = proc.stderr.decode()
    assert proc.returncode == 2, err
    offered = [ln.strip() for ln in err.splitlines() if ln.strip().startswith("printf '%s\\n'")]
    assert offered, err
    ran = subprocess.run(["bash", "-c", offered[0]], cwd=str(tmp_path), capture_output=True,
                         text=True)
    assert ran.returncode == 0, (offered[0], ran.stderr)
    assert "__pycache__/" in (wip / ".gitignore").read_text().splitlines(), offered[0]


def test_a_staged_bytecode_file_whose_name_is_not_ascii_is_refused(tmp_path):
    e, wip = _workspace(tmp_path)
    name = "café.cpython-312.pyc"
    (wip / "handoffs" / "x").mkdir(parents=True)
    (wip / "handoffs" / "x" / name).write_bytes(b"\0")
    e.git("add", "-f", "--", f"handoffs/x/{name}", cwd=wip)
    proc = _check(e, "handoffs/x")
    assert proc.returncode == 2, proc.stderr.decode()
    assert f"handoffs/x/{name}".encode() in proc.stdout, proc.stdout


def test_the_add_lines_are_read_in_the_c_locale(tmp_path):
    """A `git` that answers as a translated one does whenever the locale is
    not C: `add --dry-run` says `hinzufügen '<path>'`."""
    e, wip = _workspace(tmp_path)
    (wip / "handoffs" / "x" / "__pycache__").mkdir(parents=True)
    (wip / "handoffs" / "x" / "__pycache__" / "m.cpython-312.pyc").write_bytes(b"\0")
    shim = tmp_path / "de-git"
    shim.mkdir()
    real_git = shutil.which("git")
    (shim / "git").write_text(
        "#!/bin/sh\n"
        'case "${LC_ALL:-${LC_MESSAGES:-${LANG:-C}}}" in C|POSIX) exec "' + real_git + '" "$@" ;; esac\n'
        'case " $* " in *" add --dry-run "*)\n'
        '  out="$("' + real_git + '" "$@")"; rc=$?\n'
        "  printf '%s\\n' \"$out\" | sed \"s/^add '/hinzufuegen '/\"; exit \"$rc\" ;;\n"
        "esac\n"
        'exec "' + real_git + '" "$@"\n')
    (shim / "git").chmod(0o755)
    env = {"PATH": f"{shim}{os.pathsep}{e.env['PATH']}", "LC_ALL": "de_DE.UTF-8",
           "LANGUAGE": "de"}
    proc = _check(e, "handoffs/x", env=env)
    assert proc.returncode == 2, (proc.stdout, proc.stderr.decode())
    assert b"handoffs/x/__pycache__/m.cpython-312.pyc" in proc.stdout
