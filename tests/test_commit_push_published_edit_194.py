# SPDX-License-Identifier: Apache-2.0
"""A register edit that is already a local commit is PUBLISHED by the re-run
its own RECOVERY prints (opensoft/openRepoTools#194).

`commit_push` returned at *"nothing staged … no commit made"* BEFORE its push
loop. So when a peer's uncommitted file had blocked the rebase and the helper
had exited 3 with the edit as a local commit, the RECOVERY it printed — the
peer commits its file, then `LANES_LANE=<lane> lanes-edit.sh commit "<what you
wrote>"` — staged nothing, exited 0 and pushed nothing. The commit stayed local
until some later write from that checkout happened to carry it.

Every run here is the real `lanes-edit.sh` in a sandbox: a bare origin, the
workstation's shared workspace checkout `wip` that `workspace.yaml` names, and
a second clone `peer` standing in for another workstation. `LANES_GIT` is a
wrapper that logs every NETWORK call the helper makes and runs the real git,
so a case can say whether the push loop was reached at all. Nothing reaches a
real remote.
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

LANE = "repoP-1"
PEER_LANE = "repoQ-1"
REGISTER = "lanes/LANES.md"
PEER_HANDOFF = f"handoffs/{PEER_LANE}.md"
SUBJECT = "row rewritten by hand"

#: The environment a case must not inherit from the host that runs it.
SCRUBBED_PREFIXES = ("LANES_", "LANE_START_", "CLAUDE_", "OPENREPOTOOLS_",
                     "FAKE_", "GIT_", "TMUX")
SCRUBBED = {"AGENT_PROTOCOL_ROOT", "PROJECTS_ROOT", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME"}

NET_GIT = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_NET_LOG"
exec git "$@"
"""

FAKE_GH = """#!/usr/bin/env bash
printf 'FAKE gh REFUSED: %s -- this suite reaches no GitHub surface\\n' "$*" >&2
exit 90
"""


def _row(lane: str, state: str) -> str:
    return (f"| `{lane}` | `{lane}-uuid` / window `{lane}` | Eagle / WSL2 / tester "
            f"| 2026-10-11T00:00Z | — | handoffs/{lane}.md | {state} |")


class Box:
    """One workstation's shared workspace checkout, its origin and a peer."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "home"
        self.origin = root / "origin.git"
        self.wip = self.home / "projects" / "wip"
        self.peer = root / "peer"
        self.net_log = root / "net.log"
        fakebin = root / "fakebin"
        for d in (self.home / ".agents", self.home / "projects", root / "tmp", fakebin):
            d.mkdir(parents=True, exist_ok=True)
        self.net_log.write_text("", encoding="utf-8")
        for name, text in (("net-git", NET_GIT), ("gh", FAKE_GH)):
            (fakebin / name).write_text(text, encoding="utf-8")
            (fakebin / name).chmod(0o755)

        env = {k: v for k, v in os.environ.items()
               if k not in SCRUBBED and not k.startswith(SCRUBBED_PREFIXES)}
        env.update({
            "HOME": str(self.home),
            "TMPDIR": str(root / "tmp"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "PATH": f"{fakebin}{os.pathsep}{env.get('PATH', '')}",
            "AGENT_PROTOCOL_ROOT": str(self.home / ".agents"),
            "LANES_WORKSTATION": "Eagle",
            "LANES_NO_GITHUB": "1",
            "LANES_INDEX": "off",
            "LANES_GIT": str(fakebin / "net-git"),
            "FAKE_NET_LOG": str(self.net_log),
            "GIT_AUTHOR_NAME": "commit_push tests",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "commit_push tests",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        self.env = env

        self.git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.git("clone", "-q", str(self.origin), str(self.wip))
        self.write(self.wip, REGISTER,
                   "# LANES.md -- the sandbox register\n\n"
                   "| lane | session id | workstation / env / user | started (UTC) "
                   "| objects owned | handoff path | state |\n"
                   "|---|---|---|---|---|---|---|\n"
                   f"{_row(LANE, 'LIVE · seeded')}\n"
                   f"{_row(PEER_LANE, 'LIVE · seeded')}\n")
        self.write(self.wip, PEER_HANDOFF, f"# {PEER_LANE}\n")
        self.git("-C", str(self.wip), "add", "--", REGISTER, PEER_HANDOFF)
        self.git("-C", str(self.wip), "commit", "-q", "-m", "seed")
        self.git("-C", str(self.wip), "push", "-q", "origin", "main")
        self.git("clone", "-q", str(self.origin), str(self.peer))
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.wip}\n", encoding="utf-8")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    def wgit(self, *args: str) -> str:
        return self.git("-C", str(self.wip), *args)

    def ogit(self, *args: str) -> str:
        return self.git("--git-dir", str(self.origin), *args)

    @staticmethod
    def write(checkout: Path, rel: str, text: str) -> None:
        path = checkout / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def set_state(self, checkout: Path, lane: str, state: str) -> None:
        """A hand edit of one row's state cell, the edit `commit` wraps."""
        path = checkout / REGISTER
        text = path.read_text(encoding="utf-8")
        old = _row(lane, "LIVE · seeded")
        assert old in text, text
        path.write_text(text.replace(old, _row(lane, state)), encoding="utf-8")

    def peer_pushes(self, rel: str, text: str, message: str) -> None:
        """Origin moves on: a commit from another workstation."""
        self.write(self.peer, rel, text)
        self.git("-C", str(self.peer), "add", "--", rel)
        self.git("-C", str(self.peer), "commit", "-q", "-m", message)
        self.git("-C", str(self.peer), "push", "-q", "origin", "main")

    def peer_edit_in_wip(self, line: str) -> None:
        """A peer lane's handoff, mid-write and uncommitted in THIS checkout."""
        with (self.wip / PEER_HANDOFF).open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def helper(self, *args: str, lane: str = LANE, **extra: str) -> subprocess.CompletedProcess:
        self.net_log.write_text("", encoding="utf-8")
        env = dict(self.env, LANES_LANE=lane, **extra)
        return subprocess.run(["bash", str(REPO / "lanes-edit.sh"), *args],
                              env=env, cwd=str(self.wip), capture_output=True,
                              text=True, timeout=180, check=False)

    def net_calls(self) -> list[str]:
        return self.net_log.read_text(encoding="utf-8").splitlines()

    def unpublished(self) -> list[str]:
        return self.wgit("rev-list", "origin/main..HEAD").split()

    def origin_file(self, rel: str) -> str:
        return self.ogit("show", f"main:{rel}")

    def origin_subjects(self) -> list[str]:
        return self.ogit("log", "--format=%s", "main").splitlines()


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def _line_of(stderr: str, needle: str) -> int:
    for number, line in enumerate(stderr.splitlines()):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} is on no line of:\n{stderr}")


def test_the_printed_recovery_publishes_the_edit_it_stranded(box):
    """THE ISSUE'S OWN SEQUENCE, END TO END. Origin moves on; a peer's handoff
    is uncommitted in the shared checkout; a register write commits, cannot
    pull, has its push rejected six times and exits 3 with the RECOVERY. The
    peer then commits its file exactly as that RECOVERY says, and the re-run it
    names must PUBLISH: one copy of the edit on origin, the peer's commit with
    it, and the commit origin already had kept — not exit 0 with nothing sent.
    """
    box.peer_pushes("handoffs/repoR-1.md", "# repoR-1\n",
                    "handoff(repoR-1@Raven): another workstation's write")
    box.peer_edit_in_wip("a peer's line, mid-write")
    box.set_state(box.wip, LANE, "LIVE · edited by hand")

    stranded = box.helper("commit", SUBJECT)
    assert stranded.returncode == 3, stranded.stderr
    assert "a peer's uncommitted file blocks the rebase" in stranded.stderr
    assert len(box.unpublished()) == 1, "the edit is a local commit and only that"
    # The RECOVERY names the re-run and says what it does once nothing is staged.
    assert 'LANES_LANE=<lane> lanes-edit.sh commit "<what you wrote>"' in stranded.stderr
    assert "pushes the local commits this lists" in stranded.stderr, stranded.stderr

    box.wgit("commit", "-q", "-m", f"handoff({PEER_LANE}@Eagle): the mid-write line",
             "--", PEER_HANDOFF)
    rerun = box.helper("commit", SUBJECT)
    assert rerun.returncode == 0, rerun.stderr
    assert "pushed origin/main" in rerun.stderr, rerun.stderr
    assert box.wgit("rev-parse", "HEAD") == box.ogit("rev-parse", "main")
    assert _row(LANE, "LIVE · edited by hand") in box.origin_file(REGISTER)
    assert "a peer's line, mid-write" in box.origin_file(PEER_HANDOFF)
    assert box.origin_file("handoffs/repoR-1.md") == "# repoR-1\n"
    subjects = box.origin_subjects()
    assert sum(s.endswith(f"): {SUBJECT}") for s in subjects) == 1, subjects
    assert len(subjects) == 4, ("seed, the other workstation's write, the edit and "
                                f"the peer's handoff — no commit of the re-run's own: {subjects}")


def test_a_clean_checkout_with_nothing_ahead_is_still_a_no_op(box):
    """TODAY'S BEHAVIOUR, KEPT. Nothing staged and nothing on HEAD that origin
    lacks: the same note, exit 0, no commit and no network call at all."""
    head, origin = box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")
    result = box.helper("commit", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert f"nothing staged for {REGISTER} — no commit made" in result.stderr
    assert "push" not in result.stderr, result.stderr
    assert box.net_calls() == []
    assert (box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")) == (head, origin)


def test_a_checkout_behind_origin_with_nothing_of_its_own_is_still_a_no_op(box):
    """Behind is not ahead: origin's newer commits are no local commit to
    publish, so this is the no-op above and not a pull."""
    box.peer_pushes("handoffs/repoR-1.md", "# repoR-1\n", "a newer commit elsewhere")
    box.wgit("fetch", "-q", "origin")
    head = box.wgit("rev-parse", "HEAD")
    result = box.helper("commit", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert f"nothing staged for {REGISTER} — no commit made" in result.stderr
    assert box.net_calls() == []
    assert box.wgit("rev-parse", "HEAD") == head


def test_publishing_past_a_peers_dirty_file_keeps_the_dirty_elsewhere_guard(box):
    """The publish takes the SAME push loop a commit does, guard included: with
    a peer's file still uncommitted it warns, names the file, skips the pull,
    pushes straight out, and leaves that file exactly as it found it."""
    box.set_state(box.wip, LANE, "LIVE · edited by hand")
    box.wgit("commit", "-q", "-m", f"LANES({LANE}@Eagle): {SUBJECT}", "--", REGISTER)
    box.peer_edit_in_wip("a peer's line, still mid-write")

    result = box.helper("commit", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert f"nothing staged for {REGISTER} — no commit made" in result.stderr
    assert ("WARNING: this checkout has uncommitted changes to files OTHER than the register"
            in result.stderr)
    assert PEER_HANDOFF in result.stderr
    assert "pushed origin/main (attempt 1, no pull" in result.stderr, result.stderr
    calls = [f" {c} " for c in box.net_calls()]
    assert not any(" pull " in c for c in calls), calls
    assert any(" push " in c for c in calls), calls
    assert box.wgit("rev-parse", "HEAD") == box.ogit("rev-parse", "main")
    assert _row(LANE, "LIVE · edited by hand") in box.origin_file(REGISTER)
    assert box.wgit("diff", "--name-only").split() == [PEER_HANDOFF]
    assert "still mid-write" not in box.origin_file(PEER_HANDOFF)


def test_the_conflict_recovery_warns_that_a_reset_drops_a_peers_commits(box):
    """The issue's near-loss of 2026-10-09: the conflict RECOVERY ended in
    `reset --hard origin/main`, which in a shared checkout also drops a PEER's
    unpushed commit. The RECOVERY lists every unpublished commit by content and
    says, before the reset, that it must not run while any of them is not the
    reader's own — and the helper itself leaves the peer's commit in place."""
    box.peer_edit_in_wip("a peer's handoff, committed and not yet pushed")
    box.wgit("commit", "-q", "-m", f"handoff({PEER_LANE}@Eagle): unpushed",
             "--", PEER_HANDOFF)
    peer_commit = box.wgit("rev-parse", "HEAD").strip()
    box.set_state(box.peer, LANE, "LIVE · the peer rewrote this row")
    box.git("-C", str(box.peer), "commit", "-q", "-am", "the same row, elsewhere")
    box.git("-C", str(box.peer), "push", "-q", "origin", "main")
    box.set_state(box.wip, LANE, "LIVE · edited by hand")

    result = box.helper("commit", SUBJECT)
    err = result.stderr
    assert result.returncode == 3, err
    assert "REBASE CONFLICT on origin/main" in err
    assert box.wgit("merge-base", "--is-ancestor", peer_commit, "HEAD") == ""

    count = _line_of(err, "cherry origin/main")
    listing = _line_of(err, "cherry -v origin/main")
    warning = _line_of(err, "never reset, stash or overwrite a peer's work")
    drops = _line_of(err, "drops EVERY '+' commit in this checkout")
    reset = _line_of(err, "reset --hard origin/main")
    assert count < listing < warning <= drops < reset, err

    # The listing the RECOVERY prints is a command that runs, and it names
    # the peer's commit as one origin does not have.
    command = err.splitlines()[listing].split("lanes-edit: ", 1)[1].split("#", 1)[0].split()
    listed = subprocess.run(command, env=box.env, capture_output=True,
                            text=True, check=True).stdout
    assert f"+ {peer_commit}" in listed, listed


def test_the_dirty_checkout_refusal_names_the_act_to_re_run(box):
    """`refuse_dirty_checkout`'s RECOVERY used to end in *"then re-run:"*
    followed by two COMMIT commands, which read as if `lanes-edit.sh commit`
    were the re-run. The authors commit their files; what is re-run is the
    act that was refused, whose own push publishes their commits."""
    box.peer_edit_in_wip("a peer's line, mid-write")
    # An event names the transcript taking the act (Amendment 7(b)); without
    # one the write refuses before it ever reads the checkout.
    result = box.helper("log", "NOTED", f"lane:{LANE}", "a note",
                        LANES_SESSION="0e3c9a52-6d1b-4b8e-9f3a-2a7c5d4e6f81")
    assert result.returncode == 2, result.stderr
    assert "RECOVERY — whoever wrote those files commits them:" in result.stderr
    assert "then re-run the refused write NOTED" in result.stderr, result.stderr
