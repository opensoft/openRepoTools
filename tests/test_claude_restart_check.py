# SPDX-License-Identifier: Apache-2.0
"""`claude-restart-check`: the RESTART NEEDED line for a running session
(opensoft/workBenches#119, the added scope of 2026-09-29).

THE PROCESS TABLE IS A DIRECTORY THIS SUITE BUILDS. `CLAUDE_RESTART_CHECK_PROC`
points the command at a fake `/proc` under `tmp_path`: each process is a
directory holding a `status` file with its `PPid:` and an `exe` symlink whose
TEXT is the target the kernel would report, including the ` (deleted)`
suffix a replaced binary carries. Nothing here reads the real `/proc` or runs
a real Claude Code.

The shape measured on py-bench, 2026-09-29, is the default fixture: the status
line command runs under `/bin/sh -c`, dash does not exec it, so its parent is
the shell and claude is the shell's parent. npm renames the old package
directory before deleting it, so the running exe path names a directory like
`.claude-code-h9B5EqFE` that no longer exists.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

CMD = REPO / "claude-restart-check"
GREEN, RESET = "\033[32m", "\033[0m"

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="claude-restart-check is a bash script"),
              WINDOWS_SKIP]


class Proc:
    """A fake process table plus the installs it points into."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.proc = root / "proc"
        self.proc.mkdir()
        self.prefix = root / "npm-global"
        self.versions = root / "home" / ".local" / "share" / "claude" / "versions"

    def process(self, pid: int, ppid: int, exe: str | None = None) -> None:
        d = self.proc / str(pid)
        d.mkdir()
        (d / "status").write_text(f"Name:\tx\nPid:\t{pid}\nPPid:\t{ppid}\n")
        if exe is not None:
            (d / "exe").symlink_to(exe)

    def npm_package(self, version: str) -> Path:
        pkg = self.prefix / "lib" / "node_modules" / "@anthropic-ai" / "claude-code"
        (pkg / "bin").mkdir(parents=True, exist_ok=True)
        (pkg / "package.json").write_text(
            '{\n  "name": "@anthropic-ai/claude-code",\n'
            f'  "version": "{version}",\n  "bin": {{ "claude": "bin/claude.exe" }}\n}}\n')
        exe = pkg / "bin" / "claude.exe"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        return exe

    def replaced_npm_exe(self) -> str:
        """What the kernel reports after npm swapped the package underneath."""
        return str(self.prefix / "lib" / "node_modules" / "@anthropic-ai"
                   / ".claude-code-h9B5EqFE" / "bin" / "claude.exe") + " (deleted)"

    def native(self, *versions: str) -> None:
        self.versions.mkdir(parents=True, exist_ok=True)
        for v in versions:
            f = self.versions / v
            f.write_text("#!/bin/sh\n")
            f.chmod(0o755)

    def run(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        full = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
        full["CLAUDE_RESTART_CHECK_PROC"] = str(self.proc)
        full.update(env)
        return subprocess.run([str(CMD), *args], env=full, capture_output=True,
                              text=True, timeout=30, check=False)


@pytest.fixture
def table(tmp_path: Path) -> Proc:
    return Proc(tmp_path)


def status_line_tree(t: Proc, claude_exe: str) -> None:
    """claude (200) -> /bin/sh -c (100): the status line passes --pid 100."""
    t.process(200, 1, claude_exe)
    t.process(100, 200, "/usr/bin/dash")


def restart(old: str, new: str) -> str:
    return f"RESTART NEEDED: running {old}, installed {new}; /ctx at your next breakpoint"


def test_a_binary_npm_replaced_under_the_session_asks_for_a_restart(table):
    table.npm_package("2.1.284")
    status_line_tree(table, table.replaced_npm_exe())
    result = table.run("--running", "2.1.283", "--pid", "100", NO_COLOR="1")
    assert result.returncode == 0, result.stderr
    assert result.stdout == restart("2.1.283", "2.1.284") + "\n"


def test_the_line_is_green_unless_no_color_is_set(table):
    table.npm_package("2.1.284")
    status_line_tree(table, table.replaced_npm_exe())
    result = table.run("--running", "2.1.283", "--pid", "100")
    assert result.stdout == f"{GREEN}{restart('2.1.283', '2.1.284')}{RESET}\n"


def test_a_current_session_prints_nothing(table):
    exe = table.npm_package("2.1.284")
    status_line_tree(table, str(exe))
    result = table.run("--running", "2.1.284", "--pid", "100")
    assert (result.returncode, result.stdout) == (0, "")


def test_an_installed_version_newer_than_the_running_one_asks_even_undeleted(table):
    exe = table.npm_package("2.1.284")
    status_line_tree(table, str(exe))
    result = table.run("--running", "2.1.283", "--pid", "100", NO_COLOR="1")
    assert result.stdout == restart("2.1.283", "2.1.284") + "\n"


def test_a_native_session_behind_the_newest_native_version_asks(table):
    """The native updater writes the new version beside the old one, so the
    running file is still there: the version comparison is what notices."""
    table.native("2.1.283", "2.1.284")
    status_line_tree(table, str(table.versions / "2.1.283"))
    result = table.run("--pid", "100", NO_COLOR="1")
    assert result.stdout == restart("2.1.283", "2.1.284") + "\n"


def test_a_native_session_on_the_newest_version_prints_nothing(table):
    table.native("2.1.9", "2.1.10")
    status_line_tree(table, str(table.versions / "2.1.10"))
    assert table.run("--pid", "100").stdout == ""


def test_a_running_version_that_is_not_a_version_falls_back_to_the_path(table):
    table.native("2.1.283", "2.1.284")
    status_line_tree(table, str(table.versions / "2.1.283"))
    result = table.run("--running", "unknown", "--pid", "100", NO_COLOR="1")
    assert result.stdout == restart("2.1.283", "2.1.284") + "\n"


def test_a_replaced_binary_with_no_readable_versions_still_asks(table):
    status_line_tree(table, table.replaced_npm_exe())
    result = table.run("--pid", "100", NO_COLOR="1")
    assert result.stdout == restart("an older build", "a newer build") + "\n"


def test_the_walk_reaches_claude_three_processes_up_and_no_further(table):
    table.npm_package("2.1.284")
    table.process(300, 1, table.replaced_npm_exe())
    table.process(200, 300, "/usr/bin/bash")
    table.process(100, 200, "/usr/bin/dash")
    found = table.run("--running", "2.1.283", "--pid", "100", NO_COLOR="1")
    assert found.stdout == restart("2.1.283", "2.1.284") + "\n"
    table.process(50, 100, "/usr/bin/bash")
    too_far = table.run("--running", "2.1.283", "--pid", "50")
    assert (too_far.returncode, too_far.stdout) == (0, "")


def test_the_walk_starts_at_the_parent_by_default(table):
    """No --pid: the walk starts at this command's own parent, which for a
    `subprocess.run` is the test process itself."""
    table.npm_package("2.1.284")
    table.process(200, 1, table.replaced_npm_exe())
    table.process(os.getpid(), 200, "/usr/bin/python3")
    result = table.run("--running", "2.1.283", NO_COLOR="1")
    assert result.stdout == restart("2.1.283", "2.1.284") + "\n"


def test_no_claude_above_it_prints_nothing(table):
    table.process(200, 1, "/usr/bin/tmux")
    table.process(100, 200, "/usr/bin/dash")
    assert table.run("--pid", "100").stdout == ""


def test_a_host_with_no_process_table_prints_nothing_and_exits_0(table):
    result = table.run("--running", "2.1.283", "--pid", "100",
                       CLAUDE_RESTART_CHECK_PROC=str(table.root / "no-proc"))
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_a_pid_that_is_not_a_number_prints_nothing_and_exits_0(table):
    result = table.run("--pid", "not-a-pid")
    assert (result.returncode, result.stdout) == (0, "")


def test_help_and_an_unknown_argument(table):
    result = table.run("--help")
    assert result.returncode == 0
    assert result.stdout.startswith("claude-restart-check [--running <version>] [--pid <pid>]\n")
    result = table.run("--bogus")
    assert result.returncode == 64
    assert "unknown argument: --bogus" in result.stderr
    assert table.run("--pid").returncode == 64
