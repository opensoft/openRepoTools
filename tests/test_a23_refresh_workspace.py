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

from a23_box import ME, REGISTER, RegisterBox, register_text
from conftest import WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

UUID = "a23f0001-ffff-4000-8000-a23f0001ffff"


def _row(lane: str, cell: str) -> str:
    return (f"| `{lane}` | harness `{UUID}` | Eagle / test / tester | 2026-10-17T00:00Z "
            f"| — | {cell} | LIVE · seeded |")


class Box(RegisterBox):
    """Two rows whose handoff cells W's strays are named by, and the seed
    clone kept as a peer that pushes."""

    def __init__(self, root: Path) -> None:
        rows = [_row("repoFF-1", "handoffs/repoFF/repoFF-1.md"),
                _row("repoFF-2", "~/projects/repoFF/handoffs/repoFF-2.md")]
        super().__init__(root, {REGISTER: register_text(rows),
                                "handoffs/repoFF/README.md": "# repoFF\n"}, seed_dir="peer")
        self.peer = self.seed

    def wgit(self, *args: str) -> str:
        return self.git("-C", str(self.w), *args)

    def peer_pushes(self, rel: str = "handoffs/repoFF/peer.md", text: str = "from a peer\n") -> None:
        super().peer_pushes(rel, text)

    def refresh(self, **extra: str) -> subprocess.CompletedProcess:
        return self.helper("refresh-workspace", timeout=120, **extra)

    def head(self) -> str:
        return self.wgit("rev-parse", "HEAD").strip()

    def origin_main(self) -> str:
        return self.origin_head()

    def snapshot(self) -> tuple:
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
