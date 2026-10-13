# SPDX-License-Identifier: Apache-2.0
"""The register sweeps and their reads fail closed: opensoft/openRepoTools#138
(the `lanes-edit.sh` items) and #157 item 4b.

Each case builds a throwaway register — a bare repository and a clone of it in
a temporary directory, with a temporary `$HOME` — and runs the real
`lanes-edit.sh` against it. A read that has to FAIL is made to fail by a `git`
on `PATH` that refuses one exact argument and hands every other call to the
real one, or by a permission or a file type the case puts on disk. Nothing here
reaches a network or the operator's own register.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None, reason="lanes-edit.sh is a bash command")]

#: The sweeping lane's transcript, and the old one the dormant rows carry.
WRITER_ID = "aaaa0138-0001-4000-8000-000000000001"
OLD_ID = "bbbb0138-0002-4000-8000-000000000002"
HEADER = ("| lane | session id | workstation / env / user | started (UTC) "
          "| objects owned | handoff path | state |\n|---|---|---|---|---|---|---|\n")
ROOT_ONLY = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="a permission case needs an unprivileged runner")


def row(lane: str, sid: str, state: str, started: str = "2026-08-27") -> str:
    return (f"| `{lane}` | harness `{sid}` | Eagle / test / brett | {started} "
            f"| none | none | {state} |\n")


def log_text(lane: str, *lines: str) -> str:
    head = f"# lane {lane} — object log (lane-collision-protocol Amendment 7)\n"
    return head + "".join(line + "\n" for line in lines)


def lane_line(verb: str, lane: str, sid: str, utc: str) -> str:
    return f"{verb} — lane {lane}, session {sid}@Eagle, {utc}, lane:{lane}"


class Register:
    """One workspace repository: `origin` bare, `wip` its clone."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.origin = tmp / "origin.git"
        self.wip = tmp / "wip"
        self.home = tmp / "home"
        self.fakebin = tmp / "fakebin"
        for d in (self.home / ".agents", self.home / ".claude" / "sessions",
                  self.home / "projects", tmp / "tmp", self.fakebin):
            d.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("LANES_", "CLAUDE_", "TMUX"))}
        env.update(HOME=str(self.home), TMPDIR=str(tmp / "tmp"),
                   AGENT_PROTOCOL_ROOT=str(self.home / ".agents"),
                   PROJECTS_ROOT=str(self.home / "projects"),
                   LANES_WORKSPACE_ROOT=str(self.wip), LANES_WORKSTATION="Eagle",
                   LANES_HOST="Eagle", LANES_CONTAINER="none", LANES_IN_CONTAINER="0",
                   LANES_OS="linux", LANES_NO_GITHUB="1", LANES_INDEX="off",
                   GIT_AUTHOR_NAME="register tests", GIT_AUTHOR_EMAIL="t@example.invalid",
                   GIT_COMMITTER_NAME="register tests", GIT_COMMITTER_EMAIL="t@example.invalid",
                   PATH=str(self.fakebin) + os.pathsep + os.environ.get("PATH", ""))
        self.env = env
        self.raw_git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.raw_git("clone", "-q", str(self.origin), str(self.wip))
        (self.wip / "lanes" / "log").mkdir(parents=True)
        self.write("lanes/LANES.md", "# LANES.md\n\n" + HEADER
                   + row("repoX-1", WRITER_ID, "PAUSED · 2026-09-11T00:00:00Z · the sweeper", "2026-09-11")
                   + row("repoX-2", OLD_ID, "old words")
                   + row("repoX-3", OLD_ID, "more old words"))
        self.write("lanes/log/repoX-1.md", log_text(
            "repoX-1", lane_line("STARTED", "repoX-1", WRITER_ID, "2026-09-11T00:00:00Z"),
            lane_line("PAUSED", "repoX-1", WRITER_ID, "2026-09-11T01:00:00Z")))
        self.publish("seed the register")

    def raw_git(self, *args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              check=True, env=self.env).stdout

    def git(self, *args: str) -> str:
        return self.raw_git("-C", str(self.wip), *args)

    def write(self, rel: str, text: str) -> Path:
        path = self.wip / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def read(self, rel: str) -> str:
        return (self.wip / rel).read_text(encoding="utf-8")

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def publish(self, message: str) -> None:
        self.commit(message)
        self.git("push", "-q", "-u", "origin", "main")

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def dirty(self) -> str:
        return self.git("status", "--porcelain")

    def refuse_git(self, *needles: str) -> None:
        """A `git` first on PATH that exits 128 when its arguments contain any
        of `needles`, and runs the real one otherwise."""
        real = shutil.which("git", path=os.environ.get("PATH"))
        cases = "\n".join(f'  *"{n}"*) echo "test shim: git $* refused" >&2; exit 128 ;;'
                          for n in needles)
        shim = self.fakebin / "git"
        shim.write_text(f'#!/usr/bin/env bash\ncase " $* " in\n{cases}\nesac\nexec "{real}" "$@"\n')
        shim.chmod(0o755)

    def live(self, sid: str) -> None:
        """A session record this workstation reads as LIVE: this test's own pid."""
        (self.home / ".claude" / "sessions" / f"{sid}.json").write_text(
            f'{{"pid":{os.getpid()},"sessionId":"{sid}","cwd":"x","procStart":"",'
            f'"tmux":"","name":"n","status":"idle"}}\n')

    def run(self, *args: str, **extra: str) -> subprocess.CompletedProcess:
        env = dict(self.env)
        env.update(extra)
        return subprocess.run(["bash", str(REPO / "lanes-edit.sh"), *args],
                              cwd=str(self.wip), env=env, text=True,
                              capture_output=True, timeout=120, check=False)

    def sweep(self, *lanes: str, **extra: str) -> subprocess.CompletedProcess:
        extra.setdefault("LANES_LANE", "repoX-1")
        return self.run("retire-rows", *lanes, "--reason", "test sweep", **extra)


@pytest.fixture
def reg(tmp_path: Path) -> Register:
    return Register(tmp_path)


def peer_edit(reg: Register) -> str:
    """A peer's uncommitted edit to the register, which a capture would commit."""
    text = reg.read("lanes/LANES.md").replace("more old words", "a peer's half-written cell")
    reg.write("lanes/LANES.md", text)
    return text


# ---------------------------------------------------------------- #157 item 4b

@pytest.mark.parametrize("act", [
    ("retire-rows", "repoX-2", "repoX-2", "--reason", "test sweep"),
    ("archive-rows", "repoX", "--yes"),
    ("migrate-state-cells", "--yes"),
], ids=["retire-rows", "archive-rows", "migrate-state-cells"])
def test_a_refusal_in_the_scan_commits_no_peer_edit(reg, act):
    """#157 4b: each sweep captured a peer's register edit as its own commit
    BEFORE its scan, so a refusal in the scan left HEAD moved. The refusal now
    comes first, and the peer's edit is still uncommitted after it."""
    edited = peer_edit(reg)
    before = reg.head()
    result = reg.run(*act, LANES_LANE="repoX-1")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "captured pre-existing edit" not in result.stderr
    assert reg.head() == before
    assert reg.read("lanes/LANES.md") == edited
    assert reg.dirty().strip() == "M lanes/LANES.md"


def test_a_sweep_that_writes_still_captures_the_peer_edit_as_its_own_commit(reg):
    """The capture moved; it did not go: the peer's edit still lands in its own
    `LANES(pre-existing@…)` commit and never inside the sweep's."""
    peer_edit(reg)
    before = reg.head()
    result = reg.sweep("repoX-2")
    assert result.returncode == 0, (result.stdout, result.stderr)
    subjects = reg.git("log", "--format=%s", f"{before}..HEAD").splitlines()
    assert len(subjects) == 2, subjects
    assert subjects[1].startswith("LANES(pre-existing@Eagle)")
    assert "retire-dormant" in subjects[0]
    swept = reg.git("show", "--format=", "-U0", "HEAD", "--", "lanes/LANES.md")
    assert "a peer's half-written cell" not in swept


# ------------------------------------------------- #138: retire_rows' scan

def test_item_17_a_published_log_git_cannot_read_refuses_the_sweep(reg):
    """#138 item 17: the probe was `cat-file -e`, which fails for an unreadable
    blob exactly as for a missing path, so a log the tree names and git cannot
    read was "no published log" and the row was retired. The tree answers now.
    The local copy is out of the sparse checkout, so only origin speaks."""
    reg.write("lanes/log/repoX-2.md", log_text(
        "repoX-2", lane_line("STARTED", "repoX-2", OLD_ID, "2026-09-11T00:00:00Z"),
        lane_line("PAUSED", "repoX-2", OLD_ID, "2026-09-11T01:00:00Z")))
    reg.publish("repoX-2 is parked")
    reg.git("update-index", "--skip-worktree", "lanes/log/repoX-2.md")
    (reg.wip / "lanes/log/repoX-2.md").unlink()
    reg.refuse_git("origin/main:lanes/log/repoX-2.md")
    before = reg.head()
    result = reg.sweep("repoX-2")
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "exists on origin/main and could not be read" in result.stderr
    assert reg.head() == before
    assert not (reg.wip / "lanes/log/repoX-2.md").exists()


@ROOT_ONLY
def test_item_9_a_log_directory_that_cannot_be_listed_refuses_in_the_scan(reg):
    """#138 item 9: `log_files_named_ci` was `ls 2>/dev/null | awk`, so an
    unreadable log directory passed the scan as "no log" and the sweep failed
    on it later, inside its write loop (exit 5). It refuses in the scan now."""
    logs = reg.wip / "lanes" / "log"
    before = reg.head()
    logs.chmod(0)
    try:
        result = reg.sweep("repoX-2")
    finally:
        logs.chmod(0o755)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "exists and could not be listed" in result.stderr
    assert reg.head() == before
    assert reg.dirty() == ""
