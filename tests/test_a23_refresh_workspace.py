# SPDX-License-Identifier: Apache-2.0
"""Amendment 23 S5: W is read-only, and it is only ever fast-forwarded.

`lanes-edit.sh refresh-workspace` is the read-side verb S5 (2) names. It runs
two git acts in W — `fetch origin main` and `merge --ff-only origin/main` — and
nothing else. Whatever would stop a fast-forward is reported and skipped (exit
2, nothing changed): W not on main, an operation in progress, staged entries,
W ahead of or diverged from origin, a live legacy lock in W, or git's own
refusal over a file in the way. It never resets, stashes, commits or aborts.
And a file written into W through an estate link is reported by path and, where
a row's handoff cell names it, by its lane ("People too").
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

REGISTER = "lanes/LANES.md"
UUID = "a23f0001-ffff-4000-8000-a23f0001ffff"
ME = "bench-a hosta"

SCRUBBED_PREFIXES = ("LANES_", "LANE_START_", "CLAUDE_", "OPENREPOTOOLS_",
                     "FAKE_", "GIT_", "TMUX")
SCRUBBED = {"AGENT_PROTOCOL_ROOT", "PROJECTS_ROOT", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME"}

REFUSE = """#!/usr/bin/env bash
printf 'FAKE %s REFUSED: %s -- this suite reaches no real surface\\n' "${0##*/}" "$*" >&2
exit 90
"""


def _row(lane: str, cell: str) -> str:
    return (f"| `{lane}` | harness `{UUID}` | Eagle / test / tester | 2026-10-17T00:00Z "
            f"| — | {cell} | LIVE · seeded |")


class Box:
    """A bare origin, W and a peer cloned from it, and workspace.yaml naming W."""

    def __init__(self, root: Path) -> None:
        root = Path(os.path.realpath(root))
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.home = root / "home"
        self.origin = root / "origin.git"
        self.w = self.home / "projects" / "brett-wip"
        self.lanes_root = self.home / "projects" / "brett-wip-lanes"
        self.peer = root / "peer"
        self.fakebin = root / "fakebin"
        for d in (self.home / ".agents", self.home / "projects", root / "tmp", self.fakebin):
            d.mkdir(parents=True, exist_ok=True)
        for name in ("gh", "tmux"):
            (self.fakebin / name).write_text(REFUSE, encoding="utf-8")
            (self.fakebin / name).chmod(0o755)
        env = {k: v for k, v in os.environ.items()
               if k not in SCRUBBED and not k.startswith(SCRUBBED_PREFIXES)}
        env.update({
            "HOME": str(self.home),
            "TMPDIR": str(root / "tmp"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "PATH": f"{self.fakebin}{os.pathsep}{env.get('PATH', '')}",
            "AGENT_PROTOCOL_ROOT": str(self.home / ".agents"),
            "LANES_WORKSTATION": "Eagle",
            "LANES_HOST": "hosta",
            "LANES_CONTAINER": "bench-a",
            "LANES_NO_GITHUB": "1",
            "LANES_INDEX": "off",
            "LANE_WORKTREES_REPORT": "off",
            "GIT_AUTHOR_NAME": "a23 tests",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "a23 tests",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        self.env = env
        self.git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.quiet(self.origin, bare=True)
        self.git("clone", "-q", str(self.origin), str(self.peer))
        self.quiet(self.peer)
        self.write(self.peer, REGISTER,
                   "# LANES.md -- the sandbox register\n\n"
                   "| lane | session id | workstation / env / user | started (UTC) "
                   "| objects owned | handoff path | state |\n"
                   "|---|---|---|---|---|---|---|\n"
                   f"{_row('repoFF-1', 'handoffs/repoFF/repoFF-1.md')}\n"
                   f"{_row('repoFF-2', '~/projects/repoFF/handoffs/repoFF-2.md')}\n")
        self.write(self.peer, "handoffs/repoFF/README.md", "# repoFF\n")
        self.commit(self.peer, "seed", REGISTER, "handoffs/repoFF/README.md")
        self.git("-C", str(self.peer), "push", "-q", "origin", "main")
        self.git("clone", "-q", str(self.origin), str(self.w))
        self.quiet(self.w)
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.w}\n", encoding="utf-8")

    def quiet(self, repo: Path, *, bare: bool = False) -> None:
        where = ["--git-dir", str(repo)] if bare else ["-C", str(repo)]
        self.git(*where, "config", "gc.auto", "0")
        self.git(*where, "config", "maintenance.auto", "false")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    def wgit(self, *args: str) -> str:
        return self.git("-C", str(self.w), *args)

    @staticmethod
    def write(checkout: Path, rel: str, text: str) -> None:
        path = checkout / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, checkout: Path, message: str, *paths: str) -> None:
        self.git("-C", str(checkout), "add", "--", *paths)
        self.git("-C", str(checkout), "commit", "-q", "-m", message)

    def peer_pushes(self, rel: str = "handoffs/repoFF/peer.md", text: str = "from a peer\n") -> None:
        self.write(self.peer, rel, text)
        self.commit(self.peer, f"a peer writes {rel}", rel)
        self.git("-C", str(self.peer), "push", "-q", "origin", "main")

    def refresh(self, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(REPO / "lanes-edit.sh"), "refresh-workspace"],
                              env=dict(self.env, **extra), cwd=str(self.root),
                              capture_output=True, text=True, timeout=120, check=False)

    def head(self) -> str:
        return self.wgit("rev-parse", "HEAD").strip()

    def origin_main(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse", "main").strip()

    def snapshot(self) -> tuple[str, str, str]:
        return (self.head(), self.wgit("status", "--porcelain", "--untracked-files=all"),
                self.wgit("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"))


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def test_behind_is_fast_forwarded(box: Box):
    box.peer_pushes()
    assert box.head() != box.origin_main()
    result = box.refresh()
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert box.head() == box.origin_main()
    assert "fast-forwarded W" in result.stderr
    again = box.refresh()
    assert again.returncode == 0 and "is current" in again.stderr, again.stderr
    assert not box.lanes_root.exists(), "a read-side act makes no lane checkout"


def _block(box: Box, how: str) -> str:
    """Put W in the state `how` names; return the words its report carries."""
    if how == "ahead":
        box.write(box.w, "handoffs/repoFF/local.md", "committed in W\n")
        box.commit(box.w, "a commit made in W", "handoffs/repoFF/local.md")
        return "ahead of origin/main"
    box.peer_pushes()                     # W is behind for every other case
    if how == "diverged":
        box.write(box.w, "handoffs/repoFF/local.md", "committed in W\n")
        box.commit(box.w, "a commit made in W", "handoffs/repoFF/local.md")
        return "diverged from origin/main"
    if how == "not on main":
        box.wgit("switch", "-q", "-c", "elsewhere")
        return "not on main: HEAD is elsewhere"
    if how == "an operation":
        sha = box.head()
        (box.w / ".git" / "MERGE_HEAD").write_text(sha + "\n", encoding="utf-8")
        return "an operation in progress"
    if how == "staged entries":
        box.write(box.w, "handoffs/repoFF/staged.md", "staged in W\n")
        box.wgit("add", "--", "handoffs/repoFF/staged.md")
        return "staged entries: handoffs/repoFF/staged.md"
    if how == "a live legacy lock":
        lock = box.w / "lanes" / ".lanes-edit.lock"
        lock.mkdir()
        (lock / "pid").write_text(f"{os.getpid()} {ME}\n", encoding="utf-8")
        return "a lock held"
    if how == "an untracked file in the way":
        box.write(box.w, "handoffs/repoFF/peer.md", "a different file, never committed\n")
        return "git refused to fast-forward"
    raise AssertionError(how)  # pragma: no cover


@pytest.mark.parametrize("how", ["ahead", "diverged", "not on main", "an operation", "staged entries",
                                 "a live legacy lock", "an untracked file in the way"])
def test_blocked_is_reported_and_skipped(box: Box, how: str):
    words = _block(box, how)
    before = box.snapshot()
    result = box.refresh()
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert words in result.stderr, result.stderr
    assert "nothing in it was changed" in result.stderr
    assert box.snapshot() == before, "no reset, stash, commit, abort or fast-forward"
    if how == "an operation":
        assert (box.w / ".git" / "MERGE_HEAD").is_file(), "the operation is not aborted"


def test_stray_handoff_named_by_lane(box: Box):
    # repoFF-1's cell is repository-relative; repoFF-2's is the estate spelling,
    # through an estate link into W — the way a person writes one by habit.
    estate = box.home / "projects" / "repoFF"
    estate.mkdir()
    (estate / "handoffs").symlink_to(box.w / "handoffs" / "repoFF")
    box.write(box.w, "handoffs/repoFF/repoFF-1.md", "a handoff written into W\n")
    (estate / "handoffs" / "repoFF-2.md").write_text("through the estate link\n", encoding="utf-8")
    box.write(box.w, "handoffs/repoFF/nobody.md", "no row names this one\n")
    result = box.refresh()
    assert result.returncode == 0, (result.stdout, result.stderr)
    err = result.stderr
    assert ("a stray in W: handoffs/repoFF/repoFF-1.md (??) — lane repoFF-1's handoff, which "
            f"belongs in its own checkout: {box.lanes_root}/repoFF-1/handoffs/repoFF/repoFF-1.md") in err, err
    assert ("a stray in W: handoffs/repoFF/repoFF-2.md (??) — lane repoFF-2's handoff, which "
            f"belongs in its own checkout: {box.lanes_root}/repoFF-2/handoffs/repoFF/repoFF-2.md") in err, err
    assert "a stray in W: handoffs/repoFF/nobody.md (??)\n" in err, err
    assert (box.w / "handoffs" / "repoFF" / "repoFF-1.md").is_file(), "a stray is reported, never moved"


def test_W_reflog_shows_only_fetch_and_ff(box: Box):
    box.peer_pushes()
    head_log = box.wgit("reflog", "--format=%gs", "HEAD").splitlines()
    remote_log = box.wgit("reflog", "--format=%gs", "refs/remotes/origin/main").splitlines()
    refs = box.wgit("for-each-ref", "--format=%(refname)").split()
    result = box.refresh()
    assert result.returncode == 0, (result.stdout, result.stderr)
    new_head = box.wgit("reflog", "--format=%gs", "HEAD").splitlines()
    assert new_head[:-len(head_log)] == ["merge origin/main: Fast-forward"], new_head
    new_remote = box.wgit("reflog", "--format=%gs", "refs/remotes/origin/main").splitlines()
    assert len(new_remote) == len(remote_log) + 1 and new_remote[0].startswith("fetch"), new_remote
    assert box.wgit("for-each-ref", "--format=%(refname)").split() == refs, "no ref made or deleted"
    assert box.wgit("stash", "list") == ""
