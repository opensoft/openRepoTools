# SPDX-License-Identifier: Apache-2.0
"""Amendment 23, act 2, slice 2a: the handoff verbs.

`publish-handoff` keeps its contract for every old caller, and its act — the
link followed to the physical file, the restart fences, the prior digest, and
the bytes replaced by one rename beside the file — is `handoff_publish_atomic`,
which `write-handoff` shares.

`write-handoff <lane> (--stamp | --prepend | --whole) --subject …` writes the
lane's handoff in the checkout its writes go through (the lane's own under the
opt-in, the explicit `LANES_REPO` seam, W with the opt-in off), under the
checkout's lock: S3 first, the row's cell translated (S2), the read in that
checkout, the splice proven, the restart fences and the one-rename replace under
the workstation's sidecar lock nested inside, then S4 — commit by pathspec with
the `Lane:` trailer, push, read back, and a refused push replayed on origin's
new tip (a whole-file write only over the copy it started from). S3's refusal
leaves `--stamp` unwritten and `--prepend`/`--whole` written and uncommitted
(R-A11-11). `handoff-path` answers where the handoff is written.

The sandbox is the real `lanes-edit.sh`; nothing reaches a real remote. The box
is slice 1b's (`tests/test_a23_publish_replay.py`: two rows, a peer clone, and
a push-time `race` hook), imported rather than copied, with the lane's handoff
published on origin, W brought to it, and a restart state root of its own.
"""

from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest

from a23_box import ME, REGISTER
from conftest import WINDOWS_SKIP
from test_a23_publish_replay import LANE, NEIGHBOUR, Box as ReplayBox, _git_shim, _stamp

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

#: The handoff cell `_row` gives the lane, and the file origin carries there:
#: a header line, the blank that ends the header block, then the block.
HANDOFF_REL = f"handoffs/repoS4/{LANE}.md"
HANDOFF = (f"Lane: {LANE} (profile p, session s) — single-use resume prompt\n"
           "\n"
           "## RESUME PROMPT — the block the next session reads\n"
           "\n"
           "Preserved task.\n")


SUBJECT = f"handoff({LANE}@Eagle): RESUMED by a23-tester"
STAMP = f"RESUMED by a23-tester (lane {LANE}) at 2026-10-20T21:00:00Z — lane-start on Eagle"
BLOCK = (f"Lane: {LANE} (profile p, session s) — single-use resume prompt\n"
         "\n"
         "## RESUME PROMPT — PAUSED, the newer block\n"
         "\n")
#: The fences `--restart` names, and the intent `restart()` makes to match.
FENCE = ("op-a23", "3", "1", "starting", "sid-a23")
#: How long a waiter is watched to prove it is still waiting (it polls at 1 s).
WATCH = 4


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stamped(text: str, line: str = STAMP) -> str:
    """`lane-start`'s splice: the line after the first blank line after line
    1, else directly under line 1."""
    lines = text.splitlines(keepends=True)
    at = next((i + 1 for i, l in enumerate(lines) if i > 0 and not l.strip()), 1)
    return "".join(lines[:at]) + line + "\n" + "".join(lines[at:])


def prepended(text: str, block: str = BLOCK) -> str:
    return block + "---\n\n" + text


class Box(ReplayBox):
    """Slice 1b's box, with the lane's handoff on origin, W brought to it (the
    S6.5 state), and the restart intents under a state root of the box's own."""

    def __init__(self, root: Path, **kw) -> None:
        root = Path(os.path.realpath(root))
        state = root / "state"
        env = dict(kw.pop("env", None) or {}, LANES_LANE_STATE_ROOT=str(state))
        super().__init__(root, env=env, **kw)
        self.state = state
        self.peer_pushes(HANDOFF_REL, HANDOFF)
        self.w_current()

    def w_current(self) -> None:
        """W fast-forwarded by the fixture, as `refresh-workspace` would."""
        self.git("-C", str(self.w), "fetch", "-q", "origin")
        self.git("-C", str(self.w), "merge", "-q", "--ff-only", "refs/remotes/origin/main")

    def write_handoff(self, *args: str, **extra: str) -> subprocess.CompletedProcess:
        return self.helper("write-handoff", LANE, *args, **extra)

    def restart(self, handoff: Path) -> None:
        """The operation FENCE names, as a `/ctx` and its supervisor leave it:
        `pending` bound to `handoff` (its digest taken there), then `starting`
        with the attempt and the transcript the launch prepares."""
        self.intent("pending", "--expect", "none", "--operation", FENCE[0], "--generation", FENCE[1],
                    "--handoff", str(handoff))
        self.intent("starting", "--expect", "pending", "--expect-operation", FENCE[0],
                    "--attempt", FENCE[2], "--new-transcript", FENCE[4])

    def cell_is(self, cell: str) -> None:
        """The peer publishes the lane's row with another handoff cell."""
        self.peer_edits(REGISTER, f"| {HANDOFF_REL} |", f"| {cell} |", "a peer respells the handoff cell")

    def last_message(self) -> list:
        return self.git("--git-dir", str(self.origin), "log", "-1", "--format=%B", "main").splitlines()

    def w_reflog(self) -> str:
        return self.git("-C", str(self.w), "reflog", "--format=%H %gs", "HEAD")

    def intent(self, state: str, *extra: str) -> None:
        made = self.helper("set-restart-intent", LANE, state, *extra)
        assert made.returncode == 0, (made.stdout, made.stderr)

    def intent_field(self, key: str) -> str:
        text = (self.state / LANE / "restart-intent.yaml").read_text(encoding="utf-8")
        return next(line.split(": ", 1)[1] for line in text.splitlines()
                    if line.startswith(f"{key}: "))


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def _no_temporary_beside(path: Path) -> None:
    assert [p.name for p in path.parent.iterdir() if ".resume." in p.name] == []


# ------------------------------------------------- publish-handoff's contract

def test_publish_handoff_prints_the_physical_file_and_keeps_its_mode(box: Box):
    """Through a link, the physical file is replaced by one rename beside it:
    it is the one line on stdout, it keeps its mode, the link stays a link,
    nothing is committed, and no temporary is left beside it."""
    c = box.seam()
    real = c / HANDOFF_REL
    real.chmod(0o640)
    link = box.root / "estate" / "handoff.md"
    link.parent.mkdir()
    link.symlink_to(real)
    prepared = box.root / "prepared.md"
    prepared.write_text("# published whole\n", encoding="utf-8")
    head, tip = box.head(c), box.origin_head()
    result = box.helper("publish-handoff", LANE, str(link), str(prepared),
                        "--expect-digest", sha(real))
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{real}\n"
    assert real.read_text(encoding="utf-8") == "# published whole\n"
    assert stat.S_IMODE(real.stat().st_mode) == 0o640
    assert link.is_symlink()
    _no_temporary_beside(real)
    assert box.head(c) == head, "publish-handoff commits nothing"
    assert box.origin_head() == tip, "publish-handoff pushes nothing"


def test_publish_handoff_refuses_a_handoff_that_changed_exit_7(box: Box):
    c = box.seam()
    real = c / HANDOFF_REL
    prepared = box.root / "prepared.md"
    prepared.write_text("# published whole\n", encoding="utf-8")
    result = box.helper("publish-handoff", LANE, str(real), str(prepared),
                        "--expect-digest", "0" * 64)
    assert result.returncode == 7, result.stderr
    assert "the handoff changed before publication; nothing was published" in result.stderr
    assert real.read_text(encoding="utf-8") == HANDOFF
    assert result.stdout == ""
    _no_temporary_beside(real)


FENCES = {
    # name: (the intent's state, the publish's fence flags, exit, words)
    "owned": ("preparing", ("--operation", "op-a23", "--generation", "3", "--attempt", "0",
                            "--state", "preparing", "--transcript", "none"), 0, ""),
    "lost": ("preparing", ("--operation", "op-a23", "--generation", "4", "--attempt", "0",
                           "--state", "preparing", "--transcript", "none"), 7,
             "this handoff publisher lost restart ownership; nothing was published"),
    "active": ("pending", (), 7, "an active restart owns this handoff; nothing was published"),
    "half": ("preparing", ("--operation", "op-a23"), 64,
             "operation publication needs generation, attempt, state and transcript fences"),
}


@pytest.mark.parametrize("case", FENCES)
def test_publish_handoff_restart_fences(box: Box, case: str):
    """The five fences are the intent's own or nothing is published: a lost
    operation is 7, an active restart with no fences is 7, and an operation
    without its other four fences is 64."""
    c = box.seam()
    real = c / HANDOFF_REL
    state, flags, code, words = FENCES[case]
    box.intent(state, "--expect", "none", "--operation", "op-a23", "--generation", "3",
               "--handoff", str(real))
    prepared = box.root / "prepared.md"
    prepared.write_text("# fenced\n", encoding="utf-8")
    result = box.helper("publish-handoff", LANE, str(real), str(prepared),
                        "--expect-digest", sha(real), *flags)
    assert result.returncode == code, result.stderr
    assert words in result.stderr
    assert real.read_text(encoding="utf-8") == ("# fenced\n" if code == 0 else HANDOFF)
    _no_temporary_beside(real)


def test_publish_handoff_refuses_a_file_the_restart_did_not_bind(box: Box):
    """Under an operation, the file published must be the one the intent
    binds — compared as the same file, never by spelling (2)."""
    c = box.seam()
    real = c / HANDOFF_REL
    other = c / "handoffs" / "README.md"
    box.intent("preparing", "--expect", "none", "--operation", "op-a23", "--generation", "3",
               "--handoff", str(other))
    prepared = box.root / "prepared.md"
    prepared.write_text("# fenced\n", encoding="utf-8")
    result = box.helper("publish-handoff", LANE, str(real), str(prepared),
                        "--expect-digest", sha(real), "--operation", "op-a23",
                        "--generation", "3", "--attempt", "0", "--state", "preparing",
                        "--transcript", "none")
    assert result.returncode == 2, result.stderr
    assert "the publication target is not the operation-bound handoff" in result.stderr
    assert real.read_text(encoding="utf-8") == HANDOFF


# ------------------------------------------------------------ write-handoff

def _released(box: Box, c: Path) -> None:
    assert not box.lock_of(c).exists(), "the checkout's lock is released"
    assert not (box.lanes_root / ".lane-state.lock").exists(), "the sidecar lock is released"


def _line(path: Path) -> str:
    """write-handoff's one line on stdout for the file it wrote."""
    return f"{path}\t{sha(path)}\n"


def _staged_foreign(box: Box, c: Path) -> None:
    box.write(c, "handoffs/README.md", "# handoffs\na peer's staged line\n")
    box.git("-C", str(c), "add", "--", "handoffs/README.md")


# ------------------------------------------------- --stamp

def test_stamp_spliced_committed_pushed_with_lane_trailer(box: Box):
    """`lane-start`'s splice, moved: the stamp under the header block, proven,
    committed by pathspec with the `Lane:` trailer, pushed and read back."""
    c = box.seam()
    f = c / HANDOFF_REL
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF)
    assert box.origin_file(HANDOFF_REL) == stamped(HANDOFF)
    msg = box.last_message()
    assert msg[0] == SUBJECT, msg
    assert f"Lane: {LANE}" in msg, msg
    assert box.git("--git-dir", str(box.origin), "show", "--name-only", "--format=", "main").split() == [HANDOFF_REL]
    assert result.stdout == _line(f)
    assert "pushed origin/main" in result.stderr
    assert box.head(c) == box.origin_head()
    assert box.unpublished(c) == []
    _released(box, c)


@pytest.mark.parametrize("row", ["staged", "no-fetch"])
def test_stamp_refused_by_S3_writes_nothing_prints_line(box: Box, row: str):
    """S3 refuses (a foreign staged entry; a fetch that did not run): the
    stamp is written by nobody, the line it would have written is printed, and
    the checkout and origin are as they were (2)."""
    c = box.seam()
    extra = {}
    if row == "staged":
        _staged_foreign(box, c)
        words = "staged entries this write did not make: handoffs/README.md"
    else:
        extra = {"LANES_NO_FETCH": "1"}
        words = "LANES_NO_FETCH=1 is set"
    before = box.snapshot(c)
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, **extra)
    assert result.returncode == 2, result.stderr
    assert words in result.stderr
    assert "Nothing was written." in result.stderr
    assert f"the stamp line it would have written under the handoff's header block: {STAMP}" in result.stderr
    assert result.stdout == ""
    assert box.snapshot(c) == before
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    _released(box, c)


@pytest.mark.parametrize("peer", ["another-file", "the-handoff"])
def test_stamp_replays_on_new_content(box: Box, peer: str):
    """A peer's commit lands at the moment of the push: the stamp's commit is
    dropped and the verb runs again on origin's new tip, splicing the stamp
    into the new content. One stamp reaches origin, and one line is printed."""
    c = box.seam()
    base = HANDOFF
    if peer == "another-file":
        box.peer_prepares("handoffs/README.md", None, "# handoffs, by a peer\n", "a peer writes another file")
    else:
        base = HANDOFF.replace("Preserved task.\n", "Preserved task, and a peer's line.\n")
        box.peer_prepares(HANDOFF_REL, "Preserved task.\n", "Preserved task, and a peer's line.\n",
                          "a peer edits the handoff")
    box.race(prepared=True)
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert "push refused (attempt 1 of 6)" in result.stderr
    published = box.origin_file(HANDOFF_REL)
    assert published == stamped(base)
    assert published.count(STAMP) == 1
    f = c / HANDOFF_REL
    assert result.stdout == _line(f), "one line: the last attempt's"
    assert box.subjects()[0] == SUBJECT
    assert box.head(c) == box.origin_head()
    assert box.unpublished(c) == []
    _released(box, c)


def test_stamp_that_does_not_prove_out_writes_nothing(box: Box):
    """A one-line handoff with no newline would have the stamp glued to it:
    the proof fails, and nothing is written (2)."""
    c = box.seam()
    box.write(c, HANDOFF_REL, "one line and no newline")
    box.commit(c, "a handoff of one unterminated line", HANDOFF_REL)
    box.git("-C", str(c), "push", "-q", "origin", "main")
    tip = box.origin_head()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 2, result.stderr
    assert "did not prove out" in result.stderr
    assert STAMP in result.stderr
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == "one line and no newline"
    assert box.origin_head() == tip
    assert result.stdout == ""
    _released(box, c)


def test_stamp_over_an_uncommitted_change_to_the_handoff_is_refused(box: Box):
    """S3 step 4 for the handoff: a change nobody committed would ride the
    stamp's commit under its subject. Refused (2), and the change is left as
    it was, unstamped."""
    c = box.seam()
    f = c / HANDOFF_REL
    edited = HANDOFF + "A line somebody wrote and did not commit.\n"
    f.write_text(edited, encoding="utf-8")
    tip = box.origin_head()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 2, result.stderr
    assert f"these paths this write commits hold an uncommitted change: {HANDOFF_REL}" in result.stderr
    assert f.read_text(encoding="utf-8") == edited
    assert box.origin_head() == tip
    assert result.stdout == ""
    _released(box, c)


# ------------------------------------------------- --prepend

def _block(box: Box) -> Path:
    block = box.root / "block.md"
    block.write_text(BLOCK, encoding="utf-8")
    return block


def test_prepend_written_committed(box: Box):
    """`lane-handoff`'s shape, moved: the block, `---` and a blank line, then
    the old file whole; committed with the trailer, pushed, read back."""
    c = box.seam()
    f = c / HANDOFF_REL
    subject = f"handoff({LANE}@Eagle): PAUSED, a23"
    result = box.write_handoff("--prepend", str(_block(box)), "--subject", subject)
    assert result.returncode == 0, result.stderr
    assert f.read_text(encoding="utf-8") == prepended(HANDOFF)
    assert box.origin_file(HANDOFF_REL) == prepended(HANDOFF)
    msg = box.last_message()
    assert msg[0] == subject
    assert f"Lane: {LANE}" in msg
    assert result.stdout == _line(f)
    assert box.unpublished(c) == []
    _released(box, c)


def _written_uncommitted_under_S3(box: Box, mode: str) -> None:
    """S3 refuses the commit (a foreign staged entry); the handoff is written
    all the same, nothing is committed or pushed, S3's words are printed, and
    so is the path (2)."""
    c = box.seam()
    f = c / HANDOFF_REL
    if mode == "prepend":
        args, after = ("--prepend", str(_block(box))), prepended(HANDOFF)
    else:
        args, after = ("--whole", str(_prepared(box)), "--expect-digest", sha(f)), "# the handoff, written whole\n"
    _staged_foreign(box, c)
    head, tip = box.head(c), box.origin_head()
    result = box.write_handoff(*args, "--subject", "handoff: PAUSED")
    assert result.returncode == 2, result.stderr
    assert "staged entries this write did not make: handoffs/README.md" in result.stderr
    assert "the handoff is WRITTEN and NOT committed" in result.stderr
    assert f.read_text(encoding="utf-8") == after
    assert result.stdout == _line(f)
    assert box.head(c) == head
    assert box.origin_head() == tip
    assert box.git("-C", str(c), "diff", "--cached", "--name-only").split() == ["handoffs/README.md"]
    _released(box, c)


def test_prepend_refused_by_S3_still_writes_file_no_commit(box: Box):
    """R-A11-11: a swap is never left unwritten, so S3's refusal leaves the
    new top block written and uncommitted."""
    _written_uncommitted_under_S3(box, "prepend")


def test_whole_refused_by_S3_still_writes_file_no_commit(box: Box):
    """The same for the skill's whole-file write (R-A11-11's path): the
    prepared handoff is written, uncommitted, with S3's words and the path."""
    _written_uncommitted_under_S3(box, "whole")


# ------------------------------------------------- --whole

def _prepared(box: Box, text: str = "# the handoff, written whole\n") -> Path:
    prepared = box.root / "prepared.md"
    prepared.write_text(text, encoding="utf-8")
    return prepared


def test_whole_expect_digest_mismatch_exit_7_nothing_published(box: Box):
    c = box.seam()
    tip = box.origin_head()
    result = box.write_handoff("--whole", str(_prepared(box)), "--expect-digest", "0" * 64,
                               "--subject", "handoff: PAUSED")
    assert result.returncode == 7, result.stderr
    assert "the handoff changed before publication; nothing was published" in result.stderr
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    assert result.stdout == ""
    assert box.origin_head() == tip
    _released(box, c)


def test_whole_replays_only_when_origin_copy_unchanged(box: Box):
    """Origin moved under the push, and its copy of the handoff is still the
    one this write started from: the whole-file write replays and lands."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.peer_prepares("handoffs/README.md", None, "# handoffs, by a peer\n", "a peer writes another file")
    box.race(prepared=True)
    result = box.write_handoff("--whole", str(_prepared(box)), "--expect-digest", sha(f),
                               "--subject", "handoff: PAUSED")
    assert result.returncode == 0, result.stderr
    assert "push refused (attempt 1 of 6)" in result.stderr
    assert box.origin_file(HANDOFF_REL) == "# the handoff, written whole\n"
    assert box.origin_file("handoffs/README.md") == "# handoffs, by a peer\n"
    assert result.stdout == _line(f)
    _released(box, c)


def test_whole_refuses_with_commit_kept_exit_6_when_origin_changed_it(box: Box):
    """S4.4: origin's copy moved under the push, so the whole-file write does
    not replay over that change. The handoff stays written, its commit is kept
    on HEAD and named (6), and origin keeps the peer's version."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.peer_prepares(HANDOFF_REL, "Preserved task.\n", "Preserved task, and a peer's line.\n",
                      "a peer edits the handoff")
    box.race(prepared=True)
    result = box.write_handoff("--whole", str(_prepared(box)), "--expect-digest", sha(f),
                               "--subject", "handoff: PAUSED")
    assert result.returncode == 6, result.stderr
    kept = box.head(c)
    assert "is no longer the one this whole-file write started from" in result.stderr
    assert f"kept on HEAD: {kept}" in result.stderr
    assert "push refused (attempt" not in result.stderr, "no replay"
    assert f.read_text(encoding="utf-8") == "# the handoff, written whole\n"
    assert "and a peer's line" in box.origin_file(HANDOFF_REL)
    assert [line.split()[1] for line in box.unpublished(c)] == [kept]
    assert result.stdout == _line(f)
    _released(box, c)


# ------------------------------------------------- the translation (S2)

def _estate_link(box: Box) -> str:
    """`~/projects/repoS4/handoffs`, the estate link into W, and the cell
    spelled through it (Amendment 4(e))."""
    estate = box.home / "projects" / "repoS4"
    estate.mkdir(parents=True)
    (estate / "handoffs").symlink_to(box.w / "handoffs" / "repoS4")
    return f"~/projects/repoS4/handoffs/{LANE}.md"


@pytest.mark.parametrize("how", ["seam", "routed"])
def test_estate_spelled_cell_is_written_in_checkout(box: Box, how: str):
    """A cell spelled through the estate link resolves into W, and is
    TRANSLATED, never followed: the lane's checkout's copy is written and
    committed, and W's is left alone."""
    box.cell_is(_estate_link(box))
    c = box.seam() if how == "seam" else box.checkout(LANE)
    w_file = box.w / HANDOFF_REL
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == stamped(HANDOFF)
    assert box.origin_file(HANDOFF_REL) == stamped(HANDOFF)
    assert w_file.read_text(encoding="utf-8") == HANDOFF, "W's copy is never written"
    assert result.stdout == _line(c / HANDOFF_REL)
    _released(box, c)


@pytest.mark.parametrize("how", ["seam", "routed", "default"])
def test_repo_relative_cell(tmp_path: Path, how: str):
    """The repository-relative cell is joined to the checkout the write goes
    through: the lane's own routed, the seam's, and W's with the opt-in off —
    where every writer goes through W, as before Amendment 23."""
    box = Box(tmp_path, route=(how != "default"))
    c = {"seam": box.seam, "routed": lambda: box.checkout(LANE), "default": lambda: box.w}[how]()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert result.stdout == _line(c / HANDOFF_REL)
    assert box.origin_file(HANDOFF_REL) == stamped(HANDOFF)
    if how != "default":
        assert (box.w / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    _released(box, c)


def test_cell_in_another_repository_is_published_not_committed(box: Box):
    """Amendment 8(d): a handoff in another repository is not the register's.
    It is written there, and committed nowhere."""
    other = box.root / "other"
    box.git("init", "-q", "-b", "main", str(other))
    box.write(other, "handoff.md", HANDOFF)
    box.commit(other, "another repository's handoff", "handoff.md")
    box.cell_is(str(other / "handoff.md"))
    c = box.seam()
    other_head = box.git("-C", str(other), "rev-parse", "HEAD").strip()
    head, tip = box.head(c), box.origin_head()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert "another repository's handoff (Amendment 8(d))" in result.stderr
    assert (other / "handoff.md").read_text(encoding="utf-8") == stamped(HANDOFF)
    assert box.git("-C", str(other), "rev-parse", "HEAD").strip() == other_head
    assert box.git("-C", str(other), "status", "--porcelain").split() == ["M", "handoff.md"]
    assert box.head(c) == head
    assert box.origin_head() == tip
    assert result.stdout == _line(other / "handoff.md")
    _released(box, c)


def test_a_cell_through_a_link_into_W_is_refused_S5(box: Box):
    """S5: a handoff in the lane's checkout that is a link into W would write
    W's file. Refused before a byte (2), naming the checkout and the lane."""
    c = box.seam()
    f = c / HANDOFF_REL
    f.unlink()
    f.symlink_to(box.w / HANDOFF_REL)
    result = box.write_handoff("--prepend", str(_block(box)), "--subject", "handoff: PAUSED")
    assert result.returncode == 2, result.stderr
    assert "the readers' copy, where no tool writes (Amendment 23 S5)" in result.stderr
    assert f"LANES_LANE={LANE}" in result.stderr
    assert (box.w / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    assert result.stdout == ""
    _released(box, c)


# ------------------------------------------------- the restart (Amendment 17)

def test_restart_fences_under_sidecar_lock(box: Box):
    """The restart's fence and the replace run under the workstation's sidecar
    lock, taken INSIDE the checkout's: while another act holds it, the write
    waits holding its checkout lock and writes nothing; then it lands."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.restart(f)
    sidecar = box.lanes_root / ".lane-state.lock"
    holder = subprocess.Popen(["sleep", "300"])
    try:
        sidecar.mkdir(parents=True)
        (sidecar / "pid").write_text(f"{holder.pid} {ME}\n", encoding="utf-8")
        waiter = box.popen("write-handoff", LANE, "--stamp", STAMP, "--subject", SUBJECT,
                           "--restart", *FENCE)
        time.sleep(WATCH)
        assert waiter.poll() is None, "it waits on the workstation's sidecar lock"
        assert box.lock_of(c).is_dir(), "…holding its checkout lock, taken first"
        assert f.read_text(encoding="utf-8") == HANDOFF
    finally:
        holder.kill()
        holder.wait()
    out, err = waiter.communicate(timeout=120)
    assert waiter.returncode == 0, err
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF)
    assert out == _line(f)
    _released(box, c)


REFUSED_FENCES = {
    "lost": (("--restart", "op-a23", "4", "1", "starting", "sid-a23"), 7,
             "this handoff publisher lost restart ownership"),
    "unbound": (("--restart", *FENCE), 7, "the publication target is not the operation-bound handoff"),
    "active": ((), 7, "an active restart owns this handoff"),
}


@pytest.mark.parametrize("case", REFUSED_FENCES)
def test_restart_fence_refusals_write_nothing(box: Box, case: str):
    c = box.seam()
    f = c / HANDOFF_REL
    box.restart(c / "handoffs" / "README.md" if case == "unbound" else f)
    flags, code, words = REFUSED_FENCES[case]
    tip = box.origin_head()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, *flags)
    assert result.returncode == code, result.stderr
    assert words in result.stderr
    assert f.read_text(encoding="utf-8") == HANDOFF
    assert result.stdout == ""
    assert box.origin_head() == tip
    assert box.intent_field("prepared_digest") == "none", "nothing was reserved"
    _released(box, c)


def test_intent_bound_to_W_path_is_translated(box: Box):
    """An intent an older `lane-handoff` bound to W's spelling of the file
    still fences the lane's own copy: the bound path is TRANSLATED into the
    checkout before it is compared. `publish-handoff` keeps the strict test."""
    w_file = box.w / HANDOFF_REL
    box.restart(w_file)
    made = box.helper("set-row-state", LANE, "LIVE · the checkout is made")
    assert made.returncode == 0, made.stderr
    c = box.checkout(LANE)
    strict = box.helper("publish-handoff", LANE, str(c / HANDOFF_REL), str(_prepared(box)),
                        "--expect-digest", sha(c / HANDOFF_REL), "--operation", FENCE[0],
                        "--generation", FENCE[1], "--attempt", FENCE[2], "--state", FENCE[3],
                        "--transcript", FENCE[4])
    assert strict.returncode == 2, strict.stderr
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, "--restart", *FENCE)
    assert result.returncode == 0, result.stderr
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == stamped(HANDOFF)
    assert w_file.read_text(encoding="utf-8") == HANDOFF
    assert box.intent_field("handoff") == str(w_file), "the intent itself is not rewritten"
    _released(box, c)


def test_prepared_digest_recorded_before_publication(box: Box):
    """`lane-start`'s reservation, in-process: the stamped file's digest is the
    intent's prepared digest BEFORE the bytes are replaced — here the replace
    fails (no temporary can be made beside the file), and the reservation is
    already there, with the bound digest and the operation kept."""
    if os.geteuid() == 0:
        pytest.skip("a directory this process cannot write needs an unprivileged runner")
    c = box.seam()
    f = c / HANDOFF_REL
    box.restart(f)
    bound = box.intent_field("digest")
    assert bound == sha(f)
    f.parent.chmod(0o555)
    try:
        result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, "--restart", *FENCE,
                                   "--expected-digest", bound)
    finally:
        f.parent.chmod(0o755)
    assert result.returncode == 1, result.stderr
    assert "the publication temporary file could not be made" in result.stderr
    assert f.read_text(encoding="utf-8") == HANDOFF
    assert box.intent_field("prepared_digest") == sha_of(stamped(HANDOFF))
    assert box.intent_field("digest") == bound
    assert box.intent_field("reason") == "owned handoff stamp prepared"
    assert (box.intent_field("operation"), box.intent_field("state")) == (FENCE[0], FENCE[3])
    again = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, "--restart", *FENCE,
                              "--expected-digest", bound)
    assert again.returncode == 0, again.stderr
    assert sha(f) == box.intent_field("prepared_digest")
    _released(box, c)


def test_restart_pre_image_must_be_the_bound_digest(box: Box):
    """The handoff changed under the restart: `lane-start`'s refusal, and
    nothing written or reserved. A restart fence, so 7 (603): this verb's 2
    is S3's refusal."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.restart(f)
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, "--restart", *FENCE,
                               "--expected-digest", "1" * 64)
    assert result.returncode == 7, result.stderr
    assert "the restart handoff changed before its owned resume stamp" in result.stderr
    assert f.read_text(encoding="utf-8") == HANDOFF
    assert box.intent_field("prepared_digest") == "none"
    _released(box, c)


def test_under_a_restart_2_is_the_checkouts_refusal_and_a_fence_is_7(box: Box):
    """603 of lane openRepoTools-3's review of #312: `write-handoff`'s 2 meant
    both "S3 refused this checkout" and "the restart fence refused" (its bound
    file, its pre-image), so slice 2b's `lane-start`, which notes the first
    and dies on the second under an active restart (act2-plan §2.7), could
    not tell them apart. This verb answers the shared act's two fence 2s with
    7 (the cases above), and S3's refusal under the same `--restart` is 2
    still: the stamp not written, its line said, nothing reserved.
    `publish-handoff` keeps its documented 2 for the bound file
    (`test_publish_handoff_refuses_a_file_the_restart_did_not_bind`)."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.restart(f)
    bound = box.intent_field("digest")
    _staged_foreign(box, c)
    tip = box.origin_head()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, "--restart", *FENCE,
                               "--expected-digest", bound)
    assert result.returncode == 2, result.stderr
    assert "the stamp is NOT written" in result.stderr
    assert f"the stamp line it would have written under the handoff's header block: {STAMP}" in result.stderr
    assert "nothing was published" not in result.stderr.lower()
    assert f.read_text(encoding="utf-8") == HANDOFF
    assert box.intent_field("prepared_digest") == "none"
    assert box.origin_head() == tip
    assert result.stdout == ""
    _released(box, c)


def test_only_the_stamp_reserves(box: Box):
    """`lane-handoff`'s prepend binds at `preparing` and the digest is taken
    again at `pending`: a fenced prepend writes, and reserves nothing."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.intent("preparing", "--expect", "none", "--operation", FENCE[0], "--generation", FENCE[1],
               "--handoff", str(f))
    result = box.write_handoff("--prepend", str(_block(box)), "--subject", "handoff: PAUSED",
                               "--restart", FENCE[0], FENCE[1], "0", "preparing", "none")
    assert result.returncode == 0, result.stderr
    assert f.read_text(encoding="utf-8") == prepended(HANDOFF)
    assert box.intent_field("prepared_digest") == "none"
    _released(box, c)


def test_the_sidecar_lock_is_released_before_the_push(box: Box):
    """The workstation's lock is held for the fence and the replace only; the
    push and the read-back run under the checkout's lock alone."""
    c = box.seam()
    sidecar = shlex.quote(str(box.lanes_root / ".lane-state.lock"))
    checkout_lock = shlex.quote(str(box.lock_of(c)))
    seen = box.root / "at-push"
    box.use_net('[ "$1" = push ] || exit 0\n'
                f"{{ [ -d {sidecar} ] && echo sidecar; [ -d {checkout_lock} ] && echo checkout; }} "
                f">> {shlex.quote(str(seen))}\nexit 0\n")
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert seen.read_text(encoding="utf-8").split() == ["checkout"]
    _released(box, c)


# ------------------------------------------------- always: W

def test_W_untouched(box: Box):
    """Routed, every mode writes the lane's own checkout and origin. W is the
    readers' copy: its HEAD, its working tree and its reflog do not move."""
    w_before, reflog = box.w_state(), box.w_reflog()
    stamp = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert stamp.returncode == 0, stamp.stderr
    c = box.checkout(LANE)
    prepend = box.write_handoff("--prepend", str(_block(box)), "--subject", "handoff: PAUSED")
    assert prepend.returncode == 0, prepend.stderr
    whole = box.write_handoff("--whole", str(_prepared(box)), "--expect-digest", sha(c / HANDOFF_REL),
                              "--subject", "handoff: whole")
    assert whole.returncode == 0, whole.stderr
    assert box.origin_file(HANDOFF_REL) == "# the handoff, written whole\n"
    assert box.subjects()[:3] == ["handoff: whole", "handoff: PAUSED", SUBJECT]
    assert box.w_state() == w_before
    assert box.w_reflog() == reflog
    assert (box.w / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    assert box.head(c) == box.origin_head()
    assert box.unpublished(c) == []
    _released(box, c)


# ------------------------------------------------- handoff-path

@pytest.mark.parametrize("how", ["routed", "seam", "default"])
def test_handoff_path_names_where_write_handoff_writes(tmp_path: Path, how: str):
    """A read: the row's cell translated into the checkout `write-handoff`
    writes through. Routed, the path is derived before the checkout exists,
    and `--create` makes it."""
    box = Box(tmp_path, route=(how != "default"))
    c = {"seam": box.seam, "routed": lambda: box.checkout(LANE), "default": lambda: box.w}[how]()
    result = box.helper("handoff-path", LANE)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{c / HANDOFF_REL}\n"
    if how == "routed":
        assert not c.exists(), "a read makes no checkout"
        made = box.helper("handoff-path", LANE, "--create")
        assert made.returncode == 0, made.stderr
        assert made.stdout == f"{c / HANDOFF_REL}\n"
        assert (c / HANDOFF_REL).is_file()
    for argv in (("repoS4-9",), ("repoS4-9", "--create")):
        none = box.helper("handoff-path", *argv)
        assert none.returncode == 8, none.stderr
        assert "no row for it in the register" in none.stderr
        assert none.stdout == ""
    assert not box.checkout("repoS4-9").exists(), "a lane with no row gets no checkout"


# ------------------------------------------------- usage

@pytest.mark.parametrize("argv", [
    ("--subject", SUBJECT),
    ("--stamp", STAMP),
    ("--stamp", STAMP, "--prepend", "x", "--subject", SUBJECT),
    ("--whole", "x", "--subject", SUBJECT),
    ("--stamp", STAMP, "--subject", SUBJECT, "--expected-digest", "0" * 64),
    ("--stamp", "two\nlines", "--subject", SUBJECT),
    ("--stamp", STAMP, "--subject", SUBJECT, "--restart", "op"),
    ("--stamp", "", "--subject", SUBJECT),
    ("--stamp", STAMP, "--subject", "two\nlines"),
    ("--whole", "x", "--expect-digest", "g" * 64, "--subject", SUBJECT),
    ("--stamp", STAMP, "--subject", SUBJECT, "--expect-digest", "0" * 64),
    ("--stamp", STAMP, "--subject", SUBJECT, "--restart", *FENCE, "--expected-digest", "abc"),
    ("--stamp", STAMP, "--subject", SUBJECT, "--restart", "", *FENCE[1:]),
], ids=["no-mode", "no-subject", "two-modes", "whole-no-digest", "expected-no-restart",
        "stamp-two-lines", "restart-short", "stamp-empty", "subject-two-lines",
        "whole-digest-not-hex", "expect-digest-with-stamp", "expected-digest-short",
        "restart-empty-fence"])
def test_usage_is_64_and_writes_nothing(box: Box, argv):
    """Every argument is checked before the lock, and a bad one is 64 with
    nothing written and no fetch made. m2a's battery found six checks no case
    supplied the bad value for (its A02-A10): an empty stamp, a subject of two
    lines, an `--expect-digest` that is not hex, one beside `--stamp`, an
    `--expected-digest` that is not 64 long, and an empty fence, which left
    the operation empty, so the write went out unfenced."""
    c = box.seam()
    box.use_net()
    before = box.snapshot(c)
    result = box.write_handoff(*argv)
    assert result.returncode == 64, result.stderr
    assert box.snapshot(c) == before
    assert box.net_ops() == []


def test_write_handoff_for_a_lane_with_no_row_is_8(box: Box):
    """No row, no handoff cell: nothing to write (8), and the stamp it would
    have written is said."""
    c = box.seam()
    before = box.snapshot(c)
    result = box.helper("write-handoff", "repoS4-9", "--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 8, result.stderr
    assert "lane repoS4-9 has no row in the register" in result.stderr
    assert f"the stamp line it would have written under the handoff's header block: {STAMP}" in result.stderr
    assert result.stdout == ""
    assert box.snapshot(c) == before
    _released(box, c)


def test_a_block_with_no_last_newline_is_refused(box: Box):
    c = box.seam()
    block = box.root / "block.md"
    block.write_text("a block whose last line has no newline", encoding="utf-8")
    result = box.write_handoff("--prepend", str(block), "--subject", "handoff: PAUSED")
    assert result.returncode == 64, result.stderr
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF


# ------------------------------------------------- the seam, asked on S3's tip (A28)

def test_a_managed_marker_landing_inside_the_s3_window_is_refused(box: Box):
    """The managed seam is asked before the lock on this checkout's
    origin/main as it last stood, and AGAIN on what S3 fetched: a peer's row
    carrying managed-owner vocabulary, landed at the moment of S3's fetch, is
    read, and the stamp is refused with nothing written."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.peer_prepares(REGISTER, f"| handoffs/repoS4/{LANE}.md | LIVE · seeded |",
                      f"| handoffs/repoS4/{LANE}.md | LIVE · managed-owner: daemon-a23 |",
                      "a peer's row names a managed owner")
    peer = shlex.quote(str(box.peer))
    count = shlex.quote(str(box.count))
    box.use_net('[ "$1" = fetch ] || exit 0\n'
                f'[ -e {count} ] && exit 0\n'
                f"echo 1 > {count}\n"
                f"git -C {peer} push -q origin main\n"
                "exit 0\n")
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode in (1, 2), result.stderr
    assert "managed ledger" in result.stderr
    assert f.read_text(encoding="utf-8") == HANDOFF, "nothing written"
    assert "managed-owner: daemon-a23" in box.origin_register(), "the peer's row landed"
    assert box.origin_file(HANDOFF_REL) == HANDOFF
    assert result.stdout == ""
    assert box.net_ops()[0] == "fetch", "the marker landed at S3's fetch, after the first ask"
    _released(box, c)


# ------------------------------------------------- a lane with no row, routed (A23)

@pytest.mark.parametrize("fetch", ["fetched", "no-fetch"])
def test_routed_write_handoff_for_a_lane_with_no_row_clones_nothing(box: Box, fetch: str):
    """R4-1's rule for this verb: routed, a lane with no row has no handoff,
    and it is refused (2) before its checkout is cloned — after one fetch of
    W, or at once under `LANES_NO_FETCH=1`, which a writer cannot run on."""
    extra = {"LANES_NO_FETCH": "1"} if fetch == "no-fetch" else {}
    w_before, tip = box.w_state(), box.origin_head()
    result = box.helper("write-handoff", "repoS4-9", "--stamp", STAMP, "--subject", SUBJECT, **extra)
    assert result.returncode == 2, result.stderr
    if fetch == "fetched":
        assert "writes the handoff that lane's row names: there is none to write" in result.stderr
    else:
        assert "LANES_NO_FETCH=1 is set" in result.stderr
    assert "was not cloned" in result.stderr
    assert not box.checkout("repoS4-9").exists(), "nothing is cloned for a lane with no row"
    assert box.w_state() == w_before
    assert box.origin_head() == tip
    assert result.stdout == ""


# ------------------------------------------------- set-restart-intent --handoff

def _bound(box: Box, cell: str) -> subprocess.CompletedProcess:
    """A `/ctx`'s `pending`, bound to `cell` as the caller spells it."""
    return box.helper("set-restart-intent", LANE, "pending", "--expect", "none", "--operation", FENCE[0],
                      "--generation", FENCE[1], "--handoff", cell)


@pytest.mark.parametrize("how", ["seam", "routed", "default"])
def test_set_restart_intent_binds_a_repository_relative_cell_in_the_checkout(tmp_path: Path, how: str):
    """The row's repository-relative cell is translated into the checkout the
    lane's writes go through and stored as that absolute path, with that
    file's digest; the owned stamp then lands on it, fenced and reserved."""
    box = Box(tmp_path, route=(how != "default"))
    if how == "routed":
        made = box.helper("handoff-path", LANE, "--create")
        assert made.returncode == 0, made.stderr
    c = {"seam": box.seam, "routed": lambda: box.checkout(LANE), "default": lambda: box.w}[how]()
    f = c / HANDOFF_REL
    made = _bound(box, HANDOFF_REL)
    assert made.returncode == 0, made.stderr
    assert f"--handoff {HANDOFF_REL} is bound as {f}" in made.stderr
    assert box.intent_field("handoff") == str(f)
    assert box.intent_field("digest") == sha(f)
    box.intent("starting", "--expect", "pending", "--expect-operation", FENCE[0],
               "--attempt", FENCE[2], "--new-transcript", FENCE[4])
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, "--restart", *FENCE,
                               "--expected-digest", box.intent_field("digest"))
    assert result.returncode == 0, result.stderr
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF)
    assert box.intent_field("prepared_digest") == sha(f)
    if how != "default":
        assert (box.w / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF


def test_set_restart_intent_binds_the_estate_spelling_in_the_checkout(box: Box):
    """`~/…` through the estate link is W's file, and is bound as the
    checkout's copy of it, never followed into W."""
    cell = _estate_link(box)
    c = box.seam()
    made = _bound(box, cell)
    assert made.returncode == 0, made.stderr
    assert box.intent_field("handoff") == str(c / HANDOFF_REL)
    assert box.intent_field("digest") == sha(c / HANDOFF_REL)


def test_set_restart_intent_keeps_an_absolute_path_as_given(box: Box):
    """Every older caller's spelling: an absolute path is stored exactly as
    given, W's included — `lane-start` compares it with the file it resolves
    in W until slice 2b, and the older `lane-handoff` publishes that file."""
    w_file = box.w / HANDOFF_REL
    made = _bound(box, str(w_file))
    assert made.returncode == 0, made.stderr
    assert box.intent_field("handoff") == str(w_file)
    assert box.intent_field("digest") == sha(w_file)
    assert "is bound as" not in made.stderr


@pytest.mark.parametrize("cell", ["notes/handoff.md", "handoffs/../lanes/LANES.md",
                                  "handoffs/./repoS4/repoS4-1.md", "~user/handoff.md"])
def test_set_restart_intent_refuses_any_other_relative_path(box: Box, cell: str):
    """Only the row's own spellings are translated; any other relative path
    is still refused (64) and nothing is written."""
    made = _bound(box, cell)
    assert made.returncode == 64, made.stderr
    assert "--handoff" in made.stderr
    assert not (box.state / LANE / "restart-intent.yaml").exists()


# ------------------------------------------------- rv2a's pre-review of slice 2a

#: A handoff the checkout has and git has never tracked: a new lane's first, or
#: a peer's.
NEW_REL = "handoffs/repoS4/new-untracked.md"


@pytest.mark.parametrize("mode", ["stamp", "prepend", "whole"])
def test_an_untracked_handoff_is_refused_and_never_dropped(box: Box, mode: str):
    """MUST 1: the row names a handoff the checkout has and git has never
    tracked, and a peer's commit lands at the push. This write's commit would
    add the file under its own subject, and the lost race's replay dropped that
    commit and the file with it (8, "Nothing was written"). S3 step 4 counts it
    as a pending change: refused (2) before any commit, `--stamp` writing
    nothing and `--prepend`/`--whole` writing it, uncommitted (R-A11-11). The
    file is still there in every mode, still untracked, and nothing is pushed."""
    c = box.seam()
    box.cell_is(NEW_REL)
    f = c / NEW_REL
    f.write_text(HANDOFF, encoding="utf-8")
    box.race()
    if mode == "stamp":
        args, after = ("--stamp", STAMP), HANDOFF
    elif mode == "prepend":
        args, after = ("--prepend", str(_block(box))), prepended(HANDOFF)
    else:
        args, after = ("--whole", str(_prepared(box)), "--expect-digest", sha(f)), "# the handoff, written whole\n"
    result = box.write_handoff(*args, "--subject", "handoff: PAUSED")
    assert result.returncode == 2, result.stderr
    assert f"{NEW_REL}, this write's handoff, is not tracked yet" in result.stderr
    assert f.read_text(encoding="utf-8") == after
    assert box.git("-C", str(c), "status", "--porcelain", "--", NEW_REL).split() == ["??", NEW_REL]
    assert box.head(c) == box.origin_head(), "S3's fast-forward, and no commit of this write"
    assert "push" not in box.net_ops()
    assert NEW_REL not in box.git("--git-dir", str(box.origin), "ls-tree", "-r", "--name-only", "main").split()
    if mode == "stamp":
        assert result.stdout == ""
        assert f"the stamp line it would have written under the handoff's header block: {STAMP}" in result.stderr
    else:
        assert result.stdout == _line(f)
        assert f"git -C {c} add -- {NEW_REL} && git -C {c} commit" in result.stderr
    _released(box, c)


@pytest.mark.parametrize("handoff", ["untracked", "tracked"])
def test_the_recovery_under_another_S3_refusal_names_git_add_for_an_untracked_handoff(box: Box, handoff: str):
    """rv2a-c2's NIT 1 (its probe N1): S3 refuses for a foreign staged entry,
    and the row names a handoff git does not track. `--prepend` writes it,
    uncommitted (2), and the recovery's commit by pathspec needs the `git
    add` first: git refuses a pathspec it does not know. The note left the
    `add` out wherever S3 had refused for a reason of its own. It names it
    now (A45), and the two commands, run as printed, commit the handoff
    alone, the foreign entry still staged. A tracked handoff's note names no
    `add`, as before."""
    c = box.seam()
    rel = NEW_REL if handoff == "untracked" else HANDOFF_REL
    if handoff == "untracked":
        box.cell_is(NEW_REL)
        (c / NEW_REL).write_text(HANDOFF, encoding="utf-8")
    _staged_foreign(box, c)
    result = box.write_handoff("--prepend", str(_block(box)), "--subject", "handoff: PAUSED")
    err = result.stderr
    assert result.returncode == 2, err
    assert "staged entries this write did not make: handoffs/README.md" in err
    assert "the handoff is WRITTEN and NOT committed" in err
    add = f"git -C {c} add -- {rel}"
    commit = f'git -C {c} commit -m "handoff: PAUSED" -m "Lane: {LANE}" -- {rel}'
    if handoff == "tracked":
        assert f"publish it: {commit}, then" in err, err
        assert f"add -- {rel}" not in err
        _released(box, c)
        return
    assert f"publish it: {add} && {commit}, then" in err, err
    for printed in (add, commit):
        box.git(*shlex.split(printed)[1:])
    assert box.git("-C", str(c), "show", "--name-only", "--format=", "HEAD").split() == [NEW_REL]
    assert (c / NEW_REL).read_text(encoding="utf-8") == prepended(HANDOFF)
    assert box.git("-C", str(c), "diff", "--cached", "--name-only").split() == ["handoffs/README.md"]
    _released(box, c)


@pytest.mark.parametrize("how", ["target", "cell", "tracked-file", "git-config", "dotdot"])
def test_a_target_outside_handoffs_is_refused_and_nothing_written(box: Box, how: str):
    """SHOULD 1: this verb replaces a file and pushes it, so in the checkout
    it writes a file under `handoffs/` and nothing else. A `--target` naming
    the register, or a row cell that climbs out of `handoffs/` to the lane's
    append-only object log, is refused (2) before a byte: the checkout's copy
    and origin's are as they were, and nothing is printed on stdout. The rule
    is `handoffs/` itself, not only the register's and `lanes/`'s exclusions
    (m2a's E01 and E02): a tracked file elsewhere in the tree, this
    checkout's own `.git/config`, and a target whose last part is `..` are
    refused the same way."""
    if how == "tracked-file":
        box.peer_pushes("docs/plan.md", "# a plan, tracked outside handoffs/\n")
    c = box.seam()
    if how == "target":
        rel = REGISTER
        args = ("--whole", str(_prepared(box, "# not a register any more\n")),
                "--expect-digest", sha(c / REGISTER), "--target", REGISTER)
    elif how == "cell":
        rel = f"lanes/log/{LANE}.md"
        box.cell_is(f"handoffs/../{rel}")
        args = ("--prepend", str(_block(box)))
    elif how == "tracked-file":
        rel = "docs/plan.md"
        args = ("--stamp", STAMP, "--target", str(c / rel))
    elif how == "git-config":
        rel = ".git/config"
        args = ("--whole", str(_prepared(box, "[core\n")), "--expect-digest", sha(c / rel),
                "--target", str(c / rel))
    else:
        rel = "handoffs/repoS4/.."
        args = ("--stamp", STAMP, "--target", str(c / rel))
    watched = c / (HANDOFF_REL if how == "dotdot" else rel)
    before, tip = watched.read_bytes(), box.origin_head()
    published = None if how in ("git-config", "dotdot") else box.origin_file(rel)
    result = box.write_handoff(*args, "--subject", "handoff: PAUSED")
    assert result.returncode == 2, result.stderr
    assert f"is {rel} in the checkout {c}, which is not a file under handoffs/" in result.stderr
    assert "Nothing was written." in result.stderr
    assert watched.read_bytes() == before
    if published is not None:
        assert box.origin_file(rel) == published
    assert box.origin_head() == tip
    assert box.git("-C", str(c), "config", "gc.auto").strip() == "0", "git still reads the checkout's config"
    assert result.stdout == ""
    _released(box, c)


@pytest.mark.parametrize("how", ["whole-register", "prepend-log", "cell-register"])
def test_a_target_in_another_clone_of_the_register_keeps_the_handoffs_rule(box: Box, how: str):
    """rv2a-c2's SHOULD 1 (its probe N3): the `handoffs/` rule held only in
    this checkout, so a `--target`, or a row cell, naming a file of ANOTHER
    clone of the register — a sibling lane's checkout, `<W>-lanes/<lane>/` —
    was taken for another repository's handoff (8(d)): `--whole` replaced
    that clone's register in place and `--prepend` put a block on its
    append-only object log, uncommitted, exit 0, and that lane's next write
    then refused at S3 step 4 over a change it never made. The rule holds
    relative to that clone's own top level (A44): 2, nothing written there or
    here, nothing on stdout."""
    d = box.lanes_root / NEIGHBOUR
    rel = f"lanes/log/{NEIGHBOUR}.md" if how == "prepend-log" else REGISTER
    if how == "cell-register":
        box.cell_is(str(d / REGISTER))
    c = box.seam()
    box.clone(d)
    if how == "whole-register":
        args = ("--whole", str(_prepared(box, "# not a register any more\n")),
                "--expect-digest", sha(d / REGISTER), "--target", str(d / REGISTER))
    elif how == "prepend-log":
        args = ("--prepend", str(_block(box)), "--target", str(d / rel))
    else:
        args = ("--stamp", STAMP)
    text, theirs, mine = (d / rel).read_bytes(), box.snapshot(d), box.snapshot(c)
    result = box.write_handoff(*args, "--subject", "handoff: PAUSED")
    assert result.returncode == 2, result.stderr
    assert f"is {rel} in {d}, another checkout of the register" in result.stderr
    assert "Nothing was written." in result.stderr
    assert "another repository's handoff" not in result.stderr
    assert (d / rel).read_bytes() == text
    assert box.snapshot(d) == theirs
    assert box.snapshot(c) == mine
    assert result.stdout == ""
    _released(box, c)


def _beside_w_dir(box: Box, where: str) -> Path:
    """Where another checkout of the register BESIDE W is: a sibling lane's
    `<W>-lanes/<lane>/` (S1), or a per-profile `<W>-<name>/` clone."""
    if where == "lanes-sibling":
        return box.lanes_root / NEIGHBOUR
    return box.w.parent / f"{box.w.name}-p2"


def _beside_w(box: Box, where: str) -> Path:
    """Another checkout of the register beside W, cloned."""
    return box.clone(_beside_w_dir(box, where))


def _climb(box: Box, f: Path) -> str:
    """`f` spelled as a repository-relative cell of the seam `<root>/c` that
    climbs out of it with `..` (lane 3's 723 scenario's second spelling)."""
    return "handoffs/../" + os.path.relpath(f, box.root / "c")


@pytest.mark.parametrize("how", ["target", "abs-cell", "climb-cell"])
@pytest.mark.parametrize("where", ["lanes-sibling", "profile-clone"])
def test_a_handoff_in_another_checkout_of_the_register_beside_W_is_refused(box: Box, where: str, how: str):
    """601 (MUST) and Q3 of lane openRepoTools-3's review of #312. A file
    under `handoffs/` in another checkout of the register beside W was taken
    for another repository's handoff (8(d)): written there, uncommitted,
    exit 0, and that lane's own next `--stamp` refused at S3 step 4 over a
    change it never made, its next `--prepend` printed a recovery that would
    commit this lane's line under its own trailer. This test pinned that as
    `test_a_handoff_in_another_clone_of_the_register_is_still_another_repositorys`
    until lane 3's ruling. A lane's handoff is written in its own checkout
    only, so the path refuses it (2), by `--target` or by an absolute cell:
    nothing written there or here, the stamp line said, nothing on stdout.
    A relative cell that climbs there with `..` is refused the same (2), by
    602's rule, which asks the spelling first (A55)."""
    if how == "abs-cell":
        box.cell_is(str(_beside_w_dir(box, where) / HANDOFF_REL))
    if how == "climb-cell":
        box.cell_is(_climb(box, _beside_w_dir(box, where) / HANDOFF_REL))
    c = box.seam()
    d = _beside_w(box, where)
    f = d / HANDOFF_REL
    args = ("--target", str(f)) if how == "target" else ()
    text, theirs, mine = f.read_bytes(), box.snapshot(d), box.snapshot(c)
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, *args)
    assert result.returncode == 2, result.stderr
    if how == "climb-cell":
        assert (f"lane {LANE}'s handoff {_climb(box, f)} is a repository-relative spelling, joined to "
                f"this write's checkout {c}, and its '.' or '..' components climb out of it (to {f})"
                ) in result.stderr
    else:
        assert f"is {f}, in another checkout of the register beside W ({box.w})" in result.stderr
    assert "Nothing was written." in result.stderr
    assert "another repository's handoff" not in result.stderr
    assert f"the stamp line it would have written under the handoff's header block: {STAMP}" in result.stderr
    assert f.read_bytes() == text
    assert box.snapshot(d) == theirs, "that lane's checkout is as it was: nothing pending for its S3"
    assert box.snapshot(c) == mine
    assert result.stdout == ""
    _released(box, c)


def _unreadable(box: Box, d: Path, how: str, c: Path) -> dict:
    """Make the clone at `d` one git cannot read: a broken line in its
    config, or another owner (git's `dubious ownership`, with this box's own
    repositories named safe). Returns the environment the write runs with."""
    extra = {}
    if how == "bad-config":
        with open(d / ".git" / "config", "a", encoding="utf-8") as fh:
            fh.write("[broken\n")
    else:
        safe = (c, box.w, box.origin, box.seed, box.peer)
        (box.home / ".gitconfig").write_text(
            "[safe]\n" + "".join(f"\tdirectory = {x}\n" for x in safe), encoding="utf-8")
        extra = {"GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}
    probe = subprocess.run(["git", "-C", str(d), "rev-parse", "--show-toplevel"],
                           env=dict(box.env, **extra), capture_output=True, text=True, check=False)
    assert probe.returncode != 0, ("git can still read the clone", probe.stdout)
    mine = subprocess.run(["git", "-C", str(c), "rev-parse", "--show-toplevel"],
                          env=dict(box.env, **extra), capture_output=True, text=True, check=False)
    assert mine.returncode == 0, ("git cannot read this checkout either", mine.stderr)
    return extra


@pytest.mark.parametrize("how", ["bad-config", "other-owner"])
@pytest.mark.parametrize("where", ["beside-W", "elsewhere"])
def test_a_clone_git_cannot_read_is_never_taken_for_no_repository(box: Box, where: str, how: str):
    """601's second half: A44 and A47 asked git about the other clone and
    read a failed answer as "no repository" (against R22), so where git
    could not read that clone — a broken config line, or another owner —
    `--whole` replaced its register in place, exit 0, which A44 exists to
    refuse. Beside W the path refuses it (2); anywhere else, a `.git` on the
    way up from the target that git gave no answer for refuses (1, R22).
    Nothing written there or here, nothing on stdout."""
    c = box.seam()
    d = box.clone(box.lanes_root / NEIGHBOUR if where == "beside-W" else box.root / "elsewhere-clone")
    reg = d / REGISTER
    before, mine = reg.read_bytes(), box.snapshot(c)
    extra = _unreadable(box, d, how, c)
    result = box.write_handoff("--whole", str(_prepared(box, "# not a register any more\n")),
                               "--expect-digest", sha(reg), "--subject", "handoff: PAUSED",
                               "--target", str(reg), **extra)
    if where == "beside-W":
        assert result.returncode == 2, result.stderr
        assert f"is {reg}, in another checkout of the register beside W ({box.w})" in result.stderr
    else:
        assert result.returncode == 1, result.stderr
        assert f"is {reg}, under {d}, which holds a git repository that git could not read here" in result.stderr
        assert "a read that failed is never 'no repository' (R22)" in result.stderr
    assert "Nothing was written." in result.stderr
    assert "another repository's handoff" not in result.stderr
    assert reg.read_bytes() == before
    assert box.snapshot(c) == mine
    assert result.stdout == ""
    _released(box, c)


HANDOFF_PATH_REFUSED = [("W", "climb-cell"), ("W", "link-cell"), ("lanes-sibling", "abs-cell"),
                        ("lanes-sibling", "climb-cell"), ("profile-clone", "abs-cell"),
                        ("profile-clone", "climb-cell")]


@pytest.mark.parametrize("where,how", HANDOFF_PATH_REFUSED)
def test_handoff_path_refuses_what_write_handoff_refuses(box: Box, where: str, how: str):
    """Finding 723 of lane openRepoTools-3's review of #316, and its
    correction for 601 (#312 6368669583): with the refusal in `write-handoff`
    alone, `handoff-path` still printed a sibling checkout's handoff, and
    `lane-start` delivered that sibling's top block as this lane's first
    prompt. The three verbs now share one check, so `handoff-path` refuses
    what `write-handoff` refuses (2): a cell that lands in W (S5), or in
    another checkout of the register beside W, absolute or climbing with
    `..`. No path on stdout, the refusal named, nothing written there or
    here. W's own absolute spelling is still translated into the checkout
    (S2), so W is reached here only by climbing, or through a link in the
    checkout. A relative cell that climbs out is refused by 602's rule,
    which asks the spelling first (A55), as `write-handoff` does."""
    if where == "W":
        box.w_current()
        d = box.w
    else:
        d = _beside_w(box, where)
    f = d / HANDOFF_REL
    assert f.is_file()
    if how != "link-cell":
        box.cell_is(str(f) if how == "abs-cell" else _climb(box, f))
    c = box.seam()
    if how == "link-cell":
        (c / HANDOFF_REL).unlink()
        (c / HANDOFF_REL).symlink_to(f)
    theirs, mine = box.snapshot(d), box.snapshot(c)
    result = box.helper("handoff-path", LANE)
    assert result.returncode == 2, result.stderr
    if how == "climb-cell":
        assert (f"lane {LANE}'s handoff cell {_climb(box, f)} is a repository-relative spelling, joined to "
                "the checkout its writes go through, and its '.' or '..' components climb out of it"
                ) in result.stderr
        assert "so write-handoff refuses it too. Nothing was printed." in result.stderr
    elif where == "W":
        assert f"is {f}, inside the workspace checkout {box.w}, the readers' copy" in result.stderr
    else:
        assert f"is {f}, in another checkout of the register beside W ({box.w}), not in the checkout {c}" in result.stderr
    if how != "climb-cell":
        assert "`write-handoff` refuses it, so no path is printed" in result.stderr
    assert "another repository's handoff" not in result.stderr
    assert result.stdout == ""
    assert box.snapshot(d) == theirs
    assert box.snapshot(c) == mine


@pytest.mark.parametrize("how", ["abs", "abs-climb", "estate-cell"])
@pytest.mark.parametrize("where", ["lanes-sibling", "profile-clone"])
def test_set_restart_intent_refuses_a_handoff_beside_W_that_is_not_the_lanes(box: Box, where: str, how: str):
    """601 in the third verb that translates a handoff: `set-restart-intent
    --handoff` binds a restart to a file `write-handoff` would then refuse,
    so it refuses the same file by the same check (2), whether the path is
    absolute, absolute and climbing with `..`, or the estate's `~/` cell:
    no intent written, the refusal named, nothing on stdout. W's absolute
    path is still kept as given (every older caller's binding)."""
    c = box.seam()
    d = _beside_w(box, where)
    f = d / HANDOFF_REL
    assert f.is_file()
    if how == "abs":
        spelled = str(f)
    elif how == "abs-climb":
        spelled = str(c / "handoffs" / ".." / os.path.relpath(f, c))
    else:
        spelled = "~/" + os.path.relpath(f, box.home)
    theirs, mine = box.snapshot(d), box.snapshot(c)
    made = _bound(box, spelled)
    assert made.returncode == 2, made.stderr
    assert (f"--handoff {spelled} is {f}, in another checkout of the register beside W ({box.w}), "
            f"not in the checkout {c}") in made.stderr
    assert "Nothing was written." in made.stderr
    assert made.stdout == ""
    assert not (box.state / LANE / "restart-intent.yaml").exists()
    assert box.snapshot(d) == theirs
    assert box.snapshot(c) == mine


@pytest.mark.parametrize("mode", ["stamp", "whole"])
@pytest.mark.parametrize("where", ["sibling-clone", "bare-clone"])
def test_a_target_inside_another_clones_git_directory_is_refused_and_nothing_written(
        box: Box, where: str, mode: str):
    """rv2a-c3's SHOULD 1 (its probe N4): a path inside ANOTHER clone's git
    directory — a sibling lane's `<W>-lanes/<lane>/.git/config` — or inside a
    bare clone is in no work tree, so A44's test could not see it, and it was
    written as another repository's handoff (8(d)), exit 0: `--stamp` put its
    line under `[core]`, `--whole` replaced the file, and every git command in
    that clone then failed (128), its own lane's S3 with them. No handoff
    lives in a git directory (A47): 2 before a byte, nothing written there or
    here, that clone's git still reads its config, and nothing on stdout.
    A `--stamp` refused here says the line it would have written, as every
    refusal of it does (m2a's N03): a stamp that is owed is a stamp somebody
    writes by hand."""
    c = box.seam()
    if where == "sibling-clone":
        d = box.clone(box.lanes_root / NEIGHBOUR)
        gd = d / ".git"
    else:
        d = None
        gd = box.root / "bare.git"
        box.git("clone", "-q", "--bare", str(box.origin), str(gd))
        box.quiet(gd, bare=True)
    cfg = gd / "config"
    if mode == "stamp":
        args = ("--stamp", STAMP)
    else:
        args = ("--whole", str(_prepared(box, "[core\n")), "--expect-digest", sha(cfg))
    before, mine = cfg.read_bytes(), box.snapshot(c)
    theirs = box.snapshot(d) if d is not None else None
    result = box.write_handoff(*args, "--subject", "handoff: PAUSED", "--target", str(cfg))
    assert result.returncode == 2, result.stderr
    assert f"is {cfg}, inside a git directory ({gd})" in result.stderr
    assert "Nothing was written." in result.stderr
    assert "another repository's handoff" not in result.stderr
    said = f"the stamp line it would have written under the handoff's header block: {STAMP}" in result.stderr
    assert said == (mode == "stamp"), result.stderr
    assert cfg.read_bytes() == before
    assert box.git("--git-dir", str(gd), "config", "core.bare").strip() == (
        "true" if d is None else "false"), "that clone's git still reads its config"
    if d is not None:
        assert box.snapshot(d) == theirs
    assert box.snapshot(c) == mine
    assert result.stdout == ""
    _released(box, c)


def _managed_row(box: Box) -> tuple:
    """The lane's row as a peer republishes it, with a managed-owner marker
    that parses, so the seam's answer is "owned", not "unknown"."""
    return (f"| handoffs/repoS4/{LANE}.md | LIVE · seeded |",
            f"| handoffs/repoS4/{LANE}.md | LIVE · 2026-10-21T00:00:00Z · managed-owner mode=managed "
            f"daemon=ledger-a23 generation=3 bound-lane={LANE} |")


def test_a_managed_marker_landing_at_S3s_fetch_refuses_even_where_S3_refused(box: Box):
    """SHOULD 3: the seam is asked again on what S3 fetched WHATEVER S3
    answered. A peer's managed-owner marker lands at S3's fetch, and S3 then
    refuses (a foreign staged entry): a `--prepend`, which S3's refusal leaves
    written (R-A11-11), is refused by the managed ledger instead, with nothing
    written, nothing printed, and the staged entry left as it was."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.peer_prepares(REGISTER, *_managed_row(box), "a peer's row names a managed owner")
    peer = shlex.quote(str(box.peer))
    count = shlex.quote(str(box.count))
    box.use_net('[ "$1" = fetch ] || exit 0\n'
                f'[ -e {count} ] && exit 0\n'
                f"echo 1 > {count}\n"
                f"git -C {peer} push -q origin main\n"
                "exit 0\n")
    _staged_foreign(box, c)
    result = box.write_handoff("--prepend", str(_block(box)), "--subject", "handoff: PAUSED")
    assert result.returncode == 2, result.stderr
    assert "is owned by the managed ledger (owner ledger-a23" in result.stderr
    assert "the handoff is WRITTEN" not in result.stderr
    assert f.read_text(encoding="utf-8") == HANDOFF, "a managed lane's handoff is never written"
    assert "daemon=ledger-a23" in box.origin_register(), "the peer's row landed at S3's fetch"
    assert result.stdout == ""
    assert box.git("-C", str(c), "diff", "--cached", "--name-only").split() == ["handoffs/README.md"]
    _released(box, c)


def test_a_managed_marker_already_fetched_is_refused_before_the_lock(box: Box):
    """The FIRST ask, before the lock: a marker this checkout's origin/main
    already carries refuses the write before S3 runs, so no fetch is made and
    nothing is written."""
    box.peer_edits(REGISTER, *_managed_row(box), "a peer's row names a managed owner")
    c = box.seam()
    f = c / HANDOFF_REL
    box.use_net()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 2, result.stderr
    assert "is owned by the managed ledger (owner ledger-a23" in result.stderr
    assert box.net_ops() == [], "refused before the lock: S3's fetch never ran"
    assert f.read_text(encoding="utf-8") == HANDOFF
    assert result.stdout == ""
    _released(box, c)


@pytest.mark.parametrize("mode", ["stamp", "prepend"])
def test_another_repositorys_handoff_is_written_when_S3_refuses_this_checkout(box: Box, mode: str):
    """SHOULD 2: a handoff in another repository is never committed
    (Amendment 8(d)), so S3's refusal of the REGISTER checkout — here no
    fetch can run, `LANES_NO_FETCH=1` — does not stop its write, as the old
    `publish-handoff` never fetched for it. Written, said, its line printed,
    exit 0; the register checkout and origin are as they were."""
    c = box.seam()
    other = box.root / "otherrepo" / "h.md"
    other.parent.mkdir(parents=True)
    other.write_text(HANDOFF, encoding="utf-8")
    args, after = (("--stamp", STAMP), stamped(HANDOFF)) if mode == "stamp" else \
        (("--prepend", str(_block(box))), prepended(HANDOFF))
    before = box.snapshot(c)
    result = box.write_handoff(*args, "--subject", SUBJECT, "--target", str(other), LANES_NO_FETCH="1")
    assert result.returncode == 0, result.stderr
    assert "LANES_NO_FETCH=1 is set" in result.stderr
    assert f"does not stop this write: {other} is another repository's handoff (Amendment 8(d))" in result.stderr
    assert "another repository's handoff (Amendment 8(d)): it is written there" in result.stderr
    assert "the stamp is NOT written" not in result.stderr
    assert "the handoff is WRITTEN and NOT committed" not in result.stderr
    assert other.read_text(encoding="utf-8") == after
    assert result.stdout == _line(other)
    assert box.snapshot(c) == before
    _released(box, c)


def test_target_names_the_file_written(box: Box):
    """`--target`, the old callers' spelling, is the file written: a tracked
    handoff that is not the row's is stamped, committed and pushed, and the
    row's own handoff is left as it was, in the checkout and on origin."""
    rel = "handoffs/repoS4/old-callers.md"
    box.peer_pushes(rel, HANDOFF)
    c = box.seam()
    f = c / rel
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, "--target", str(f))
    assert result.returncode == 0, result.stderr
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF)
    assert box.origin_file(rel) == stamped(HANDOFF)
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    assert box.origin_file(HANDOFF_REL) == HANDOFF
    assert result.stdout == _line(f)
    _released(box, c)


def test_with_no_workspace_resolved_an_absolute_target_is_the_checkouts_own(tmp_path: Path):
    """A5's rule for an unresolved W: with no workspace checkout, an absolute
    path is only ever the checkout's own or another repository's — an empty W
    would read every absolute path as inside it and strip its leading `/`.
    Through the seam, a `--target` spelled absolute is written there."""
    box = Box(tmp_path, route=False)
    (box.home / ".agents" / "workspace.yaml").write_text(
        f"repository: {box.origin}\npath: {box.root / 'no-such-workspace'}\n", encoding="utf-8")
    c = box.seam()
    f = c / HANDOFF_REL
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, "--target", str(f))
    assert result.returncode == 0, result.stderr
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF)
    assert box.origin_file(HANDOFF_REL) == stamped(HANDOFF)
    assert result.stdout == _line(f)
    _released(box, c)


def test_a_push_that_cannot_be_confirmed_is_3_and_its_line_printed(box: Box):
    """S4's read-back: the push lands and the fetch that would confirm it
    fails. 3, `pushed, not confirmed: <sha>`, never the success line; the
    handoff is written, its line printed (A13), and origin does hold it."""
    c = box.seam()
    f = c / HANDOFF_REL
    mark = shlex.quote(str(box.root / "pushed"))
    box.use_net(f'[ "$1" = push ] && {{ touch {mark}; exit 0; }}\n'
                f'[ "$1" = fetch ] && [ -e {mark} ] && {{ echo "fatal: no read-back" >&2; exit 128; }}\n'
                "exit 0\n")
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 3, result.stderr
    sent = box.head(c)
    assert f"pushed, not confirmed: {sent}" in result.stderr
    assert "pushed origin/main (attempt" not in result.stderr, "never the success line"
    assert box.origin_head() == sent, "it did land: 3 never says it did not"
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF)
    assert result.stdout == _line(f)
    _released(box, c)


def test_with_LANES_NO_GIT_the_handoff_is_written_and_nothing_committed(box: Box):
    """`LANES_NO_GIT=1`: the handoff is written and proven as ever, and no git
    act follows — no fetch, no commit, no push. 0, said, its line printed."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.use_net()
    head, tip = box.head(c), box.origin_head()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, LANES_NO_GIT="1")
    assert result.returncode == 0, result.stderr
    assert "LANES_NO_GIT=1 — not committing" in result.stderr
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF)
    assert result.stdout == _line(f)
    assert box.head(c) == head
    assert box.origin_head() == tip
    assert box.net_ops() == []
    _released(box, c)


def test_a_target_for_a_lane_with_no_row_is_8_and_nothing_committed(box: Box):
    """NIT 3: the row is needed whatever `--target` says. Through the seam
    (and in default mode) a `--target` write for a lane with no row went on
    and committed `Lane: <a lane with no row>`; now it is 8 with nothing
    written, as the opt-in's gate refuses it before the clone."""
    c = box.seam()
    before = box.snapshot(c)
    result = box.helper("write-handoff", "repoS4-9", "--stamp", STAMP, "--subject", SUBJECT,
                        "--target", str(c / HANDOFF_REL))
    assert result.returncode == 8, result.stderr
    assert "lane repoS4-9 has no row in the register" in result.stderr
    assert result.stdout == ""
    assert box.snapshot(c) == before
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    _released(box, c)


def test_handoff_path_over_an_unreadable_register_is_1_never_8(box: Box):
    """NIT 1 (R22): a register read that fails is never "no handoff". With
    the published register unreadable, `handoff-path` is 1 and prints
    nothing, where it answered 8."""
    box.seam()
    real = shutil.which("git", path=os.environ.get("PATH"))
    shim = box.fakebin / "git"
    shim.write_text('#!/usr/bin/env bash\ncase " $* " in\n'
                    f'  *"origin/main:{REGISTER}"*) echo "test shim: git $* refused" >&2; exit 128 ;;\n'
                    f'esac\nexec "{real}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    result = box.helper("handoff-path", LANE)
    assert result.returncode == 1, result.stderr
    assert "a read that failed is never 'no handoff' (R22)" in result.stderr
    assert result.stdout == ""


def test_whole_refusal_names_HEAD_when_a_commit_landed_on_top(box: Box):
    """S4.4's refusal where another writer's commit landed on top of this
    write's while its push was in flight: HEAD is that commit, so the words
    name it and say both are kept — never "kept on HEAD" for this write's.
    Nothing is reset (6), and both commits wait for the publish act."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.peer_prepares(HANDOFF_REL, "Preserved task.\n", "Preserved task, and a peer's line.\n",
                      "a peer edits the handoff")
    peer = shlex.quote(str(box.peer))
    cq = shlex.quote(str(c))
    count = shlex.quote(str(box.count))
    box.use_net('[ "$1" = push ] || exit 0\n'
                f"[ -e {count} ] && exit 0\n"
                f"echo 1 > {count}\n"
                f"git -C {peer} push -q origin main\n"
                f"printf 'stamp' > {cq}/handoffs/stamp.md\n"
                f"git -C {cq} add -- handoffs/stamp.md\n"
                f"git -C {cq} commit -q -m 'a stamp from an unlocked writer' -- handoffs/stamp.md\n"
                "exit 0\n")
    result = box.write_handoff("--whole", str(_prepared(box)), "--expect-digest", sha(f),
                               "--subject", "handoff: PAUSED")
    assert result.returncode == 6, result.stderr
    top = box.head(c)
    mine = box.git("-C", str(c), "rev-parse", "HEAD~1").strip()
    assert box.subject(c) == "a stamp from an unlocked writer"
    assert box.subject(c, "HEAD~1") == "handoff: PAUSED"
    assert f"HEAD is {top}, not this write's commit {mine}" in result.stderr
    assert f"kept, with HEAD at {top}: {mine} handoff: PAUSED" in result.stderr
    assert f"kept on HEAD: {mine}" not in result.stderr
    assert "push refused (attempt" not in result.stderr, "no reset, no replay"
    assert len(box.unpublished(c)) == 2, "both kept, for the publish act"
    assert result.stdout == _line(f)
    _released(box, c)


def test_whole_refusal_names_a_rewritten_commit_as_rewritten(box: Box):
    """S4.4's refusal where another writer REWROTE this write's commit while
    its push was in flight (slice 1b's SHOULD A case, which S4.4 meets before
    `cp_replay` does): HEAD does not hold this write's sha at all, so nothing
    is said to be kept, on HEAD or under it, and slice 1b's `cp_not_head`
    names the rewrite. The rewrite here is an amend at the read-back fetch,
    which cannot conflict with the peer's edit as a rebase over it would."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.peer_prepares(HANDOFF_REL, "Preserved task.\n", "Preserved task, and a peer's line.\n",
                      "a peer edits the handoff")
    peer = shlex.quote(str(box.peer))
    cq = shlex.quote(str(c))
    pushed = shlex.quote(str(box.root / "pushed"))
    done = shlex.quote(str(box.root / "rewritten"))
    box.use_net(f'if [ "$1" = push ] && [ ! -e {pushed} ]; then echo 1 > {pushed}\n'
                f"  git -C {peer} push -q origin main\n"
                "  exit 0\n"
                "fi\n"
                f'if [ "$1" = fetch ] && [ -e {pushed} ] && [ ! -e {done} ]; then echo 1 > {done}\n'
                f"  git -C {cq} commit -q --amend -m 'handoff: PAUSED, reworded by an unlocked writer'\n"
                "fi\n"
                "exit 0\n")
    result = box.write_handoff("--whole", str(_prepared(box)), "--expect-digest", sha(f),
                               "--subject", "handoff: PAUSED")
    assert result.returncode == 6, result.stderr
    assert "rewrote this write's commit" in result.stderr
    assert "kept on HEAD" not in result.stderr, "this write's sha is on no branch here"
    assert "local and kept, with HEAD at" not in result.stderr, "no commit was made on top"
    assert "push refused (attempt" not in result.stderr, "no reset, no replay"
    assert box.subject(c) == "handoff: PAUSED, reworded by an unlocked writer"
    assert len(box.unpublished(c)) == 1, "the rewritten copy waits for the publish act"
    assert result.stdout == _line(f)
    _released(box, c)


# ------------------------------------------------- a handoff a peer deletes mid-push (A37)

def _peer_deletes_the_handoff(box: Box) -> None:
    """The peer clone commits the deletion of the lane's handoff WITHOUT
    pushing it: the race hook lands it at the moment this write pushes. The
    row still names the file."""
    box.git("-C", str(box.peer), "fetch", "-q", "origin")
    box.git("-C", str(box.peer), "merge", "-q", "--ff-only", "refs/remotes/origin/main")
    box.git("-C", str(box.peer), "rm", "-q", "--", HANDOFF_REL)
    box.git("-C", str(box.peer), "commit", "-q", "-m", f"a peer deletes {HANDOFF_REL}")


def _origin_has(box: Box, rel: str) -> bool:
    return rel in box.git("--git-dir", str(box.origin), "ls-tree", "-r", "--name-only", "main").split()


@pytest.mark.parametrize("mode", ["stamp", "prepend"])
@pytest.mark.parametrize("peer", ["deletes-it", "keeps-it"])
def test_a_handoff_a_peer_deletes_mid_push_keeps_the_write_on_HEAD_exit_6(box: Box, peer: str, mode: str):
    """A37: `--stamp` and `--prepend` edit the handoff IN PLACE. A peer that
    deleted it while this write's push was in flight left the replay nothing
    to write into: the re-run said "Nothing was written" (8), and the write
    was only in the commit the replay had dropped. `write-handoff` now names
    the handoff in slice 1b's `CP_KEEP_IF_GONE`, so the commit is kept on
    HEAD and named (6) before anything is dropped: the write is in this
    checkout, origin has no such file, and one commit is unpublished, this
    write's. A peer's commit that KEEPS the handoff, and changes it, is an
    ordinary lost race: the write is replayed on the peer's copy and lands
    (0)."""
    c = box.seam()
    f = c / HANDOFF_REL
    if mode == "stamp":
        args, written = ("--stamp", STAMP), stamped
    else:
        args, written = ("--prepend", str(_block(box))), prepended
    if peer == "deletes-it":
        _peer_deletes_the_handoff(box)
    else:
        box.peer_prepares(HANDOFF_REL, "Preserved task.\n", "Preserved task, and a peer's line.\n",
                          "a peer edits the handoff")
    box.race(prepared=True)
    result = box.write_handoff(*args, "--subject", SUBJECT)
    err = result.stderr
    if peer == "deletes-it":
        assert result.returncode == 6, err
        kept = box.head(c)
        assert f"origin's copy of {HANDOFF_REL} was deleted while this write's push was in flight" in err, err
        assert f"kept on HEAD: {kept}" in err
        assert "push refused (attempt" not in err, "nothing is dropped or replayed"
        assert box.subject(c) == SUBJECT
        assert f.read_text(encoding="utf-8") == written(HANDOFF), "the write is in this checkout"
        assert not _origin_has(box, HANDOFF_REL), "origin has no such file"
        assert [line.split()[1] for line in box.unpublished(c)] == [kept], "one commit unpublished, this write's"
    else:
        base = HANDOFF.replace("Preserved task.\n", "Preserved task, and a peer's line.\n")
        assert result.returncode == 0, err
        assert "push refused (attempt 1 of 6)" in err
        assert "was deleted while this write's push was in flight" not in err
        assert box.origin_file(HANDOFF_REL) == written(base)
        assert f.read_text(encoding="utf-8") == written(base)
        assert box.unpublished(c) == []
    assert result.stdout == _line(f)
    _released(box, c)


def test_whole_over_a_handoff_a_peer_deletes_mid_push_is_S4_4s_exit_6(box: Box):
    """`--whole` never names its file in `CP_KEEP_IF_GONE` (A37 is
    `--stamp`'s and `--prepend`'s): a handoff origin deleted is a copy that
    is no longer the one it started from, so S4.4 answers, before the
    replay, and keeps the commit on HEAD (6) in its own words."""
    c = box.seam()
    f = c / HANDOFF_REL
    _peer_deletes_the_handoff(box)
    box.race(prepared=True)
    result = box.write_handoff("--whole", str(_prepared(box)), "--expect-digest", sha(f),
                               "--subject", "handoff: PAUSED")
    err = result.stderr
    assert result.returncode == 6, err
    kept = box.head(c)
    assert f"origin/main's {HANDOFF_REL} is gone now" in err, err
    assert "is no longer the one this whole-file write started from" in err
    assert f"kept on HEAD: {kept}" in err
    assert "was deleted while this write's push was in flight" not in err
    assert "push refused (attempt" not in err, "no replay"
    assert f.read_text(encoding="utf-8") == "# the handoff, written whole\n"
    assert not _origin_has(box, HANDOFF_REL)
    assert [line.split()[1] for line in box.unpublished(c)] == [kept]
    assert result.stdout == _line(f)
    _released(box, c)


#: Where a peer moves the lane's handoff to (rv2a-c2's probe N2).
MOVED_REL = "handoffs/repoS4/moved-handoff.md"


def _peer_moves_the_handoff(box: Box, row: str) -> None:
    """The peer clone `git mv`s the lane's handoff to MOVED_REL in a commit
    it does NOT push: the race hook lands it at this write's push. In the
    same commit the register's row for the lane either follows the file
    ("follows": the cell names MOVED_REL) or is renamed with it ("renamed":
    the lane is `repoS4-9` now, as `rename-lane` renames a row and moves its
    handoff), so origin has no row for this write's lane."""
    p = box.peer
    box.git("-C", str(p), "fetch", "-q", "origin")
    box.git("-C", str(p), "merge", "-q", "--ff-only", "refs/remotes/origin/main")
    box.git("-C", str(p), "mv", "--", HANDOFF_REL, MOVED_REL)
    reg = p / REGISTER
    text = reg.read_text(encoding="utf-8")
    assert text.count(f"| {HANDOFF_REL} |") == 1
    new = text.replace(f"| {HANDOFF_REL} |", f"| {MOVED_REL} |")
    if row == "renamed":
        assert new.count(f"| `{LANE}` |") == 1
        new = new.replace(f"| `{LANE}` |", "| `repoS4-9` |")
    reg.write_text(new, encoding="utf-8")
    box.git("-C", str(p), "add", "--", REGISTER)
    box.git("-C", str(p), "commit", "-q", "-m", f"a peer moves {HANDOFF_REL} and its row ({row})")


@pytest.mark.parametrize("mode", ["stamp", "prepend"])
def test_a_handoff_a_peer_moves_with_its_row_cell_mid_push_is_replayed_into_the_moved_file(box: Box, mode: str):
    """rv2a-c2's NIT 2 (its probe N2): a peer moves the lane's handoff and
    points the row's cell at its new name, in one commit that lands while
    this write's push is in flight. A37 kept the commit on HEAD (6) for any
    handoff origin no longer has, though the replay's re-run reads the row
    again and writes the moved file. It is kept now only where origin's row
    still names the cell this write followed (A46): here the replay goes
    ahead, the write lands in the moved file on origin (0), and nothing is
    left unpublished."""
    c = box.seam()
    if mode == "stamp":
        args, written = ("--stamp", STAMP), stamped
    else:
        args, written = ("--prepend", str(_block(box))), prepended
    _peer_moves_the_handoff(box, "follows")
    box.race(prepared=True)
    result = box.write_handoff(*args, "--subject", SUBJECT)
    err = result.stderr
    assert result.returncode == 0, err
    assert "push refused (attempt 1 of 6)" in err
    assert "was deleted while this write's push was in flight" not in err
    assert box.origin_file(MOVED_REL) == written(HANDOFF)
    assert not _origin_has(box, HANDOFF_REL)
    assert (c / MOVED_REL).read_text(encoding="utf-8") == written(HANDOFF)
    assert box.unpublished(c) == []
    assert result.stdout == _line(c / MOVED_REL)
    _released(box, c)


@pytest.mark.parametrize("how", ["target", "renamed"])
def test_a_moved_handoff_the_replay_cannot_follow_is_kept_on_HEAD_exit_6(box: Box, how: str):
    """A46's bounds, where A37's keep still holds (6): the replay's re-run
    could not follow the move. A `--target` names the old path again, so
    the re-run would find nothing there; and where the row was renamed with
    the file, origin has no row for this lane to re-read, so the re-run
    would be 8 ("no row"). The write is in this checkout and kept on HEAD,
    one commit unpublished, nothing replayed."""
    c = box.seam()
    f = c / HANDOFF_REL
    _peer_moves_the_handoff(box, "follows" if how == "target" else "renamed")
    box.race(prepared=True)
    extra = ("--target", str(f)) if how == "target" else ()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, *extra)
    err = result.stderr
    assert result.returncode == 6, err
    kept = box.head(c)
    assert f"origin's copy of {HANDOFF_REL} was deleted while this write's push was in flight" in err, err
    assert f"kept on HEAD: {kept}" in err
    assert "push refused (attempt" not in err, "nothing is dropped or replayed"
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF)
    assert _origin_has(box, MOVED_REL) and not _origin_has(box, HANDOFF_REL)
    assert [line.split()[1] for line in box.unpublished(c)] == [kept]
    assert result.stdout == _line(f)
    _released(box, c)


#: Where a peer moves the lane's handoff OUT of `handoffs/` (A48's third case).
OUTSIDE_REL = "notes/moved-handoff.md"


def _elsewhere(box: Box) -> Path:
    """A file in another repository's folder, which nobody wrote."""
    return box.root / "elsewhere" / "handoff.md"


def _peer_repoints_the_cell(box: Box, cell: str) -> None:
    """In one commit the peer clone does NOT push (the race hook lands it at
    this write's push), the lane's handoff leaves origin and the row's cell
    stops naming it (rv2a-c3's probe N5): "moved-no-file" deletes it and
    points the cell at MOVED_REL, which origin has no file for; "emptied"
    deletes it and empties the cell; "moved-out-of-handoffs" `git mv`s it to
    OUTSIDE_REL and points the cell there; "another-repository" deletes it
    and points the cell at a path in a folder of another repository, which
    this checkout cannot translate (m2a's N05)."""
    p = box.peer
    box.git("-C", str(p), "fetch", "-q", "origin")
    box.git("-C", str(p), "merge", "-q", "--ff-only", "refs/remotes/origin/main")
    if cell == "moved-out-of-handoffs":
        (p / OUTSIDE_REL).parent.mkdir(parents=True, exist_ok=True)
        box.git("-C", str(p), "mv", "--", HANDOFF_REL, OUTSIDE_REL)
    else:
        box.git("-C", str(p), "rm", "-q", "--", HANDOFF_REL)
    if cell == "another-repository":
        _elsewhere(box).parent.mkdir()  # the folder is there, the file is not
    new = {"moved-no-file": MOVED_REL, "emptied": "", "moved-out-of-handoffs": OUTSIDE_REL,
           "another-repository": str(_elsewhere(box))}[cell]
    reg = p / REGISTER
    text = reg.read_text(encoding="utf-8")
    assert text.count(f"| {HANDOFF_REL} |") == 1
    reg.write_text(text.replace(f"| {HANDOFF_REL} |", f"| {new} |"), encoding="utf-8")
    box.git("-C", str(p), "add", "--", REGISTER)
    box.git("-C", str(p), "commit", "-q", "-m", f"a peer repoints the lane's handoff cell ({cell})")


@pytest.mark.parametrize("cell", ["moved-no-file", "emptied", "moved-out-of-handoffs", "another-repository"])
def test_a_cell_a_peer_repoints_where_no_replay_can_write_keeps_the_write_on_HEAD_exit_6(box: Box, cell: str):
    """rv2a-c3's NIT 1 (its probe N5): A46 replayed wherever origin's row
    named another cell, though the re-run writes only a handoff that is
    there. A peer that deleted the handoff and pointed the cell at a name
    origin has no file for, or emptied it, while this write's push was in
    flight had the commit dropped and the re-run say "Nothing was written"
    (8): the write was only in the reflog. Another cell is followed now only
    to a file under `handoffs/` that origin has (A48); otherwise — no file,
    no cell, a file the re-run refuses (2, outside `handoffs/`), or a path
    this checkout cannot translate, in another repository (m2a's N05) —
    A37's keep holds: 6, the write in this checkout, one commit unpublished,
    nothing replayed, and nothing written in that other repository either."""
    c = box.seam()
    f = c / HANDOFF_REL
    _peer_repoints_the_cell(box, cell)
    box.race(prepared=True)
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    err = result.stderr
    assert result.returncode == 6, err
    kept = box.head(c)
    assert f"origin's copy of {HANDOFF_REL} was deleted while this write's push was in flight" in err, err
    assert f"kept on HEAD: {kept}" in err
    assert "push refused (attempt" not in err, "nothing is dropped or replayed"
    assert box.subject(c) == SUBJECT
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF), "the write is in this checkout"
    assert not _origin_has(box, HANDOFF_REL)
    assert [line.split()[1] for line in box.unpublished(c)] == [kept], "one commit unpublished, this write's"
    assert not _elsewhere(box).exists(), "nothing was written in another repository either"
    assert result.stdout == _line(f)
    _released(box, c)


# ------------------------------------------------- m2a's battery: what no case asked

@pytest.mark.parametrize("mode", ["prepend", "whole"])
def test_an_empty_block_or_prepared_file_is_refused(box: Box, mode: str):
    """m2a's A11: an empty `--prepend` block would put `---` and a blank
    line on top of the handoff, and an empty `--whole` file would empty the
    handoff and push that. Each is refused (1) before the lock, as
    `publish-handoff` refuses an empty prepared file: nothing written,
    committed or pushed, no fetch made, nothing on stdout."""
    c = box.seam()
    f = c / HANDOFF_REL
    empty = box.root / "empty.md"
    empty.write_text("", encoding="utf-8")
    args = (("--prepend", str(empty)) if mode == "prepend" else
            ("--whole", str(empty), "--expect-digest", sha(f)))
    box.use_net()
    before = box.snapshot(c)
    result = box.write_handoff(*args, "--subject", "handoff: PAUSED")
    assert result.returncode == 1, result.stderr
    assert f"the {mode} file {empty} is unreadable or empty. Nothing was written." in result.stderr
    assert f.read_text(encoding="utf-8") == HANDOFF
    assert box.snapshot(c) == before
    assert box.net_ops() == []
    assert result.stdout == ""
    _released(box, c)


def test_routed_a_flag_where_the_lane_goes_is_usage_and_routes_nowhere(box: Box):
    """m2a's A13: routed, the lane is `write-handoff`'s first word, and a
    flag there is the arm's own usage refusal (64), never a lane to route
    to: no checkout is cloned for it, no fetch is made, and W and origin are
    as they were."""
    box.use_net()
    w_before, tip = box.w_state(), box.origin_head()
    result = box.helper("write-handoff", "--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 64, result.stderr
    assert "usage: write-handoff <lane>" in result.stderr
    assert box.net_ops() == []
    assert not box.checkout("--stamp").exists()
    assert box.w_state() == w_before
    assert box.origin_head() == tip
    assert result.stdout == ""


def test_handoff_path_for_a_row_that_names_no_handoff_is_8(box: Box):
    """m2a's B02: a row whose handoff cell is empty names no file, so there
    is no path to answer: 8, said, nothing on stdout (never the checkout's
    own directory), and routed, `--create` clones nothing for it."""
    box.cell_is("")
    for argv in ((LANE,), (LANE, "--create")):
        result = box.helper("handoff-path", *argv)
        assert result.returncode == 8, result.stderr
        assert f"lane {LANE}'s row names no handoff" in result.stderr
        assert result.stdout == ""
    assert not box.checkout(LANE).exists(), "a row that names no handoff gets no checkout"


def test_handoff_path_reads_the_cell_from_the_register_as_published(box: Box):
    """m2a's B04: `handoff-path` fetches before it reads the row, as
    `write-handoff` does, so a peer that points the lane's cell at another
    file after this checkout last fetched is answered with that file."""
    c = box.seam()
    box.cell_is(MOVED_REL)
    result = box.helper("handoff-path", LANE)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{c / MOVED_REL}\n"


def test_handoff_path_refuses_a_lane_path_that_holds_no_clone(box: Box):
    """m2a's C02: routed, the lane's checkout path is a directory that is not
    a clone of the register. The path it would print is not one a write can
    go through: refused (1), nothing on stdout, and nothing there deleted,
    moved or written."""
    d = box.checkout(LANE)
    d.mkdir(parents=True)
    (d / "notes.md").write_text("a person's notes\n", encoding="utf-8")
    result = box.helper("handoff-path", LANE)
    assert result.returncode == 1, result.stderr
    assert f"{d} is not a clone of the register: it is a directory that is not a git checkout" in result.stderr
    assert result.stdout == ""
    assert [p.name for p in d.iterdir()] == ["notes.md"]
    assert (d / "notes.md").read_text(encoding="utf-8") == "a person's notes\n"


def test_handoff_path_through_a_directory_inside_the_seam_names_its_top_level(box: Box):
    """m2a's C03: an explicit `LANES_REPO` that names a directory inside the
    checkout is raised to that checkout's top level, so the row's
    repository-relative cell is joined to the top level and never to the
    directory as given. `LANES_REPO` alone would name no register there (1,
    "registry not found"), so `LANES_FILE` names the checkout's."""
    c = box.seam()
    box.env["LANES_REPO"] = str(c / "handoffs")
    box.env["LANES_FILE"] = str(c / REGISTER)
    result = box.helper("handoff-path", LANE)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{c / HANDOFF_REL}\n"


def test_a_handoff_that_links_out_of_the_checkout_is_another_repositorys(box: Box):
    """m2a's D08: the row's cell names a file of this checkout, and that file
    is a link to another repository's file outside W. The path is followed
    to the physical file, and that file is another repository's (Amendment
    8(d)): written there, said, its line printed, 0, committed nowhere. This
    checkout and origin are as they were, the link still a link."""
    other = box.root / "other"
    box.git("init", "-q", "-b", "main", str(other))
    box.write(other, "handoff.md", HANDOFF)
    box.commit(other, "another repository's handoff", "handoff.md")
    other_head = box.git("-C", str(other), "rev-parse", "HEAD").strip()
    seed = box.seed
    box.git("-C", str(seed), "pull", "-q", "--ff-only", "origin", "main")
    (seed / HANDOFF_REL).unlink()
    (seed / HANDOFF_REL).symlink_to(other / "handoff.md")
    box.commit(seed, "the lane's handoff is a link into another repository", HANDOFF_REL)
    box.git("-C", str(seed), "push", "-q", "origin", "main")
    c = box.seam()
    assert (c / HANDOFF_REL).is_symlink()
    before = box.snapshot(c)
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert "another repository's handoff (Amendment 8(d))" in result.stderr
    assert (other / "handoff.md").read_text(encoding="utf-8") == stamped(HANDOFF)
    assert box.git("-C", str(other), "rev-parse", "HEAD").strip() == other_head
    assert box.git("-C", str(other), "status", "--porcelain").split() == ["M", "handoff.md"]
    assert (c / HANDOFF_REL).is_symlink()
    assert box.snapshot(c) == before
    assert result.stdout == _line(other / "handoff.md")
    _released(box, c)


# ------------------------------------------------- 602: a relative spelling that climbs out

CLIMBS = {
    # name: (the spelling, where it is given, the file it reaches from the seam `<root>/c`);
    # None: the box's own file, spelled by `_climb` (a sibling checkout's handoff, W's)
    "cell-outside": ("handoffs/../../outside/x.md", "cell", "outside/x.md"),
    "target-outside": ("../outside/x.md", "target", "outside/x.md"),
    "cell-sibling": (None, "cell", None),
    "cell-W": (None, "cell", None),
    "cell-through-a-link": ("handoffs/lnk/../x.md", "cell", "elsewhere/x.md"),
    "cell-not-there-yet": ("handoffs/notyet/../../../outside/x.md", "cell", "outside/x.md"),
}


@pytest.mark.parametrize("case", CLIMBS)
def test_a_relative_spelling_that_climbs_out_of_the_checkout_is_refused(box: Box, case: str):
    """602 of lane openRepoTools-3's review of #312: a repository-relative
    cell, or a relative `--target`, is joined to the checkout (S2), and one
    whose `.` or `..` components climb out of it was written as another
    repository's handoff, exit 0, where `set-restart-intent --handoff`
    refuses the same cell (64). It names no other repository's handoff:
    refused (2), nothing written anywhere, the stamp line said. Climbing out
    is read from the text, and where the spelling resolves, from the file it
    names: `handoffs/lnk/../x.md`, with `lnk` a link out, stays in the
    checkout by its text and leaves it by its file. A link with no such
    component is still Amendment 8(d)'s (D08's test). The spelling is asked
    first (A55), so a cell that climbs into W or a checkout beside it is
    refused for its spelling too. And one that climbs out THROUGH A
    DIRECTORY NOT THERE YET (`handoffs/notyet/..`), whose file neither
    `path_physical` nor the kernel can resolve, so no check by path can say
    where it lands, is refused by its text (it said 8, "not there"), and no
    directory is made for it."""
    spelling, given, rel = CLIMBS[case]
    if case == "cell-sibling":
        f = box.lanes_root / NEIGHBOUR / HANDOFF_REL
    elif case == "cell-W":
        f = box.w / HANDOFF_REL
    else:
        f = box.root / rel
    if spelling is None:
        spelling = _climb(box, f)
    if given == "cell":
        box.cell_is(spelling)
    c = box.seam()
    if case == "cell-sibling":
        box.clone(box.lanes_root / NEIGHBOUR)
    elif case != "cell-W":
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(HANDOFF, encoding="utf-8")
    if case == "cell-through-a-link":
        (box.root / "elsewhere" / "a").mkdir()
        (c / "handoffs" / "lnk").symlink_to(box.root / "elsewhere" / "a")
    assert f.is_file()
    args = ("--target", spelling) if given == "target" else ()
    text, mine, w = f.read_bytes(), box.snapshot(c), box.w_state()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, *args)
    assert result.returncode == 2, result.stderr
    assert (f"lane {LANE}'s handoff {spelling} is a repository-relative spelling, joined to this "
            f"write's checkout {c}, and its '.' or '..' components climb out of it") in result.stderr
    assert "Nothing was written." in result.stderr
    assert "another repository's handoff" not in result.stderr
    assert f"the stamp line it would have written under the handoff's header block: {STAMP}" in result.stderr
    assert f.read_bytes() == text
    assert box.snapshot(c) == mine
    assert box.w_state() == w
    assert not (c / "handoffs" / "notyet").exists()
    assert result.stdout == ""
    _released(box, c)


def test_a_relative_spelling_that_stays_in_the_checkout_is_its_own_handoff(box: Box):
    """602's bound: the rule is a spelling that LEAVES the checkout, not any
    `..`. A cell that climbs within it names the lane's own handoff, which
    is written, committed and pushed as the plain cell's is."""
    box.cell_is(f"handoffs/../{HANDOFF_REL}")
    c = box.seam()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert box.origin_file(HANDOFF_REL) == stamped(HANDOFF)
    assert result.stdout == _line(c / HANDOFF_REL)
    _released(box, c)


@pytest.mark.parametrize("cell", ["handoffs/../../outside/x.md", "handoffs/notyet/../../../outside/x.md"])
@pytest.mark.parametrize("how", ["seam", "routed"])
def test_handoff_path_refuses_a_relative_cell_that_climbs_out_of_the_checkout(box: Box, how: str, cell: str):
    """602 in `handoff-path`: it printed `<c>/handoffs/../../outside/x.md`
    as this checkout's own file, with no note, for a cell `write-handoff`
    now refuses, and the same for a cell that climbs out through a directory
    not there yet. It answers where that write goes, so it refuses the cell
    too (2), prints nothing, and routed, `--create` clones nothing for it:
    the text is read before any checkout is made."""
    f = box.root / "outside" / "x.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(HANDOFF, encoding="utf-8")
    box.cell_is(cell)
    c = box.seam() if how == "seam" else box.checkout(LANE)
    for argv in ((LANE,), (LANE, "--create")):
        result = box.helper("handoff-path", *argv)
        assert result.returncode == 2, result.stderr
        assert (f"lane {LANE}'s handoff cell {cell} is a repository-relative "
                "spelling, joined to the checkout its writes go through, and its '.' or '..' "
                "components climb out of it") in result.stderr
        assert result.stdout == ""
    if how == "routed":
        assert not c.exists(), "a cell that climbs out gets no checkout"
    else:
        assert not (c / "handoffs" / "notyet").exists()


# ------------------------------------------------- m2a's battery, its second half

def test_stamp_into_an_empty_handoff_is_refused_1_and_says_the_line(box: Box):
    """m2a's G05: an empty handoff has no header block to stamp under, so the
    stamp is refused (1) and the line it wants is said, as `lane-start` said
    it. Without that check the splice went on, and its proof refused it in
    other words (2, "did not prove out"). Nothing written, committed or
    pushed."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.write(c, HANDOFF_REL, "")
    box.commit(c, "an empty handoff", HANDOFF_REL)
    box.git("-C", str(c), "push", "-q", "origin", "main")
    tip = box.origin_head()
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 1, result.stderr
    assert f"the handoff at {f} is empty, so it has no header block to stamp under" in result.stderr
    assert f"The line it wants: {STAMP}" in result.stderr
    assert "did not prove out" not in result.stderr
    assert f.read_text(encoding="utf-8") == ""
    assert box.origin_head() == tip
    assert result.stdout == ""
    _released(box, c)


#: A handoff the row names under `handoffs/` and nobody ever wrote.
GONE_REL = "handoffs/repoS4/no-such-handoff.md"


@pytest.mark.parametrize("mode", ["stamp", "prepend", "whole"])
def test_a_row_naming_a_handoff_the_checkout_does_not_have_is_8_and_nothing_written(box: Box, mode: str):
    """m2a's G06: the row names a file under `handoffs/` that is not there.
    There is nothing to write into: 8, the path said (and, for `--stamp`, the
    line it would have written), never "unreadable" (1). Nothing is made,
    committed or pushed."""
    box.cell_is(GONE_REL)
    c = box.seam()
    gone = c / GONE_REL
    args = {"stamp": ("--stamp", STAMP),
            "prepend": ("--prepend", str(_block(box))),
            "whole": ("--whole", str(_prepared(box)), "--expect-digest", "0" * 64)}[mode]
    before = box.snapshot(c)
    result = box.write_handoff(*args, "--subject", SUBJECT)
    err = result.stderr
    assert result.returncode == 8, err
    assert f"lane {LANE}'s handoff is not at {gone}, so there is nothing to write into. Nothing was written." in err
    assert "unreadable" not in err
    said = f"the stamp line it would have written under the handoff's header block: {STAMP}" in err
    assert said == (mode == "stamp"), err
    assert not gone.exists()
    assert not gone.is_symlink()
    assert box.snapshot(c) == before
    assert result.stdout == ""
    _released(box, c)


def test_a_prepend_fenced_at_preparing_takes_expected_digest_none(box: Box):
    """m2a's H03: `lane-handoff` binds its prepend at `preparing`, before the
    restart has a digest, and `--expected-digest none` says so: `none` is no
    digest to compare, so the fenced write goes ahead (0) and reserves
    nothing. Compared as a digest, it was refused (2, "the restart handoff
    changed before this owned write")."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.intent("preparing", "--expect", "none", "--operation", FENCE[0], "--generation", FENCE[1],
               "--handoff", str(f))
    result = box.write_handoff("--prepend", str(_block(box)), "--subject", "handoff: PAUSED",
                               "--restart", FENCE[0], FENCE[1], "0", "preparing", "none",
                               "--expected-digest", "none")
    assert result.returncode == 0, result.stderr
    assert "the restart handoff changed before" not in result.stderr
    assert f.read_text(encoding="utf-8") == prepended(HANDOFF)
    assert box.origin_file(HANDOFF_REL) == prepended(HANDOFF)
    assert box.intent_field("prepared_digest") == "none"
    assert result.stdout == _line(f)
    _released(box, c)


#: A link under `handoffs/` to the lane's handoff, which a row's cell may name.
LINK_REL = "handoffs/repoS4/link-to-handoff.md"


def _cell_spelled(box: Box, spelling: str) -> None:
    """The peer points the lane's cell at its handoff in another spelling than
    the checkout's own path: the estate's `~/...` through the estate link, or
    a link under `handoffs/` to the lane's handoff, published first."""
    if spelling == "estate":
        box.cell_is(_estate_link(box))
        return
    seed = box.seed
    box.git("-C", str(seed), "pull", "-q", "--ff-only", "origin", "main")
    (seed / LINK_REL).symlink_to(Path(HANDOFF_REL).name)
    box.commit(seed, "a link to the lane's handoff", LINK_REL)
    box.git("-C", str(seed), "push", "-q", "origin", "main")
    box.cell_is(LINK_REL)


@pytest.mark.parametrize("mode", ["stamp", "prepend"])
@pytest.mark.parametrize("spelling", ["estate", "link"])
def test_a_cell_spelled_otherwise_whose_file_a_peer_deletes_mid_push_keeps_the_write_on_HEAD_exit_6(
        box: Box, spelling: str, mode: str):
    """m2a's J01 and J02: A37's keep names the file by its path in this
    checkout, and A46 compares origin's cell with the cell this write
    followed, each in its own spelling. Where the cell is not that path (the
    estate's `~/...`, or a link under `handoffs/` to the lane's handoff) and a
    peer deletes the file while this write's push is in flight, the row left
    as it was, the write is kept on HEAD (6) and never replayed into nothing
    (8, the write only in the reflog)."""
    _cell_spelled(box, spelling)
    c = box.seam()
    f = c / HANDOFF_REL
    if mode == "stamp":
        args, written = ("--stamp", STAMP), stamped
    else:
        args, written = ("--prepend", str(_block(box))), prepended
    _peer_deletes_the_handoff(box)
    box.race(prepared=True)
    result = box.write_handoff(*args, "--subject", SUBJECT)
    err = result.stderr
    assert result.returncode == 6, err
    kept = box.head(c)
    assert f"origin's copy of {HANDOFF_REL} was deleted while this write's push was in flight" in err, err
    assert f"kept on HEAD: {kept}" in err
    assert "push refused (attempt" not in err, "nothing is dropped or replayed"
    assert box.subject(c) == SUBJECT
    assert f.read_text(encoding="utf-8") == written(HANDOFF), "the write is in this checkout"
    assert not _origin_has(box, HANDOFF_REL)
    assert [line.split()[1] for line in box.unpublished(c)] == [kept], "one commit unpublished, this write's"
    assert result.stdout == _line(f)
    _released(box, c)


def test_a_peer_that_deletes_the_handoff_and_the_register_mid_push_keeps_the_write_on_HEAD_exit_6(box: Box):
    """m2a's J03: where origin's register cannot be read at the replay, A46
    cannot say whether the row names another cell, and a read that failed is
    never "replay" (R22). A peer's commit that deletes the lane's handoff and
    the register lands while this write's push is in flight: the write is
    kept on HEAD (6), one commit unpublished, nothing dropped."""
    c = box.seam()
    f = c / HANDOFF_REL
    p = box.peer
    box.git("-C", str(p), "fetch", "-q", "origin")
    box.git("-C", str(p), "merge", "-q", "--ff-only", "refs/remotes/origin/main")
    box.git("-C", str(p), "rm", "-q", "--", HANDOFF_REL, REGISTER)
    box.git("-C", str(p), "commit", "-q", "-m", "a peer deletes the handoff and the register")
    box.race(prepared=True)
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    err = result.stderr
    assert result.returncode == 6, err
    kept = box.head(c)
    assert f"origin's copy of {HANDOFF_REL} was deleted while this write's push was in flight" in err, err
    assert f"kept on HEAD: {kept}" in err
    assert "push refused (attempt" not in err, "nothing is dropped or replayed"
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF), "the write is in this checkout"
    assert not _origin_has(box, REGISTER)
    assert [line.split()[1] for line in box.unpublished(c)] == [kept], "one commit unpublished, this write's"
    assert result.stdout == _line(f)
    _released(box, c)


def test_a_cell_a_peer_pads_otherwise_is_the_same_cell_and_the_write_is_kept_on_HEAD_exit_6(box: Box):
    """m2a's J04b: A46 compares origin's cell with the cell this write
    followed once the blanks round it are trimmed, as the register's readers
    take it: padding is no part of a cell. A peer that moves the handoff to a
    file whose name ends in a blank and writes the row's cell unpadded, with
    that one trailing blank, has not pointed the cell anywhere else, so the
    write is kept on HEAD (6) and is not replayed into the file whose name
    ends in a blank (compared untrimmed, it was "another cell", a file origin
    has: the commit dropped and the re-run writing there)."""
    c = box.seam()
    f = c / HANDOFF_REL
    p = box.peer
    odd = HANDOFF_REL + " "
    box.git("-C", str(p), "fetch", "-q", "origin")
    box.git("-C", str(p), "merge", "-q", "--ff-only", "refs/remotes/origin/main")
    box.git("-C", str(p), "mv", "--", HANDOFF_REL, odd)
    reg = p / REGISTER
    text = reg.read_text(encoding="utf-8")
    assert text.count(f"| {HANDOFF_REL} |") == 1
    reg.write_text(text.replace(f"| {HANDOFF_REL} |", f"|{HANDOFF_REL} |"), encoding="utf-8")
    box.git("-C", str(p), "add", "--", REGISTER)
    box.git("-C", str(p), "commit", "-q", "-m", "a peer renames the file to a blank-ended name, cell unpadded")
    box.race(prepared=True)
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT)
    err = result.stderr
    assert result.returncode == 6, err
    kept = box.head(c)
    assert f"origin's copy of {HANDOFF_REL} was deleted while this write's push was in flight" in err, err
    assert f"kept on HEAD: {kept}" in err
    assert "push refused (attempt" not in err, "nothing is dropped or replayed"
    assert f.read_text(encoding="utf-8") == stamped(HANDOFF), "the write is in this checkout"
    names = box.git("--git-dir", str(box.origin), "ls-tree", "-r", "--name-only", "main").splitlines()
    assert HANDOFF_REL not in names and odd in names
    assert not (c / odd).exists(), "nothing was written into the blank-ended name"
    assert [line.split()[1] for line in box.unpublished(c)] == [kept], "one commit unpublished, this write's"
    assert result.stdout == _line(f)
    _released(box, c)


def test_a_routed_bind_of_the_rows_cell_clones_no_checkout(box: Box):
    """m2a's K03: routed, the lane has no checkout yet, and
    `set-restart-intent --handoff <the row's cell>` binds the path that
    checkout will have, as `handoff-path` derives it without `--create`. A
    bind writes the sidecar and nothing else: no checkout is cloned for it,
    and W is as it was."""
    box.use_net()
    c = box.checkout(LANE)
    w_before = box.w_state()
    made = _bound(box, HANDOFF_REL)
    assert made.returncode == 0, made.stderr
    assert f"--handoff {HANDOFF_REL} is bound as {c / HANDOFF_REL}" in made.stderr
    assert box.intent_field("handoff") == str(c / HANDOFF_REL)
    assert not c.exists(), "a bind makes no checkout"
    assert "clone" not in box.net_ops()
    assert box.w_state() == w_before


# ------------------------------------------- lane openRepoTools-3's review of #312

def test_a_commit_landing_just_after_this_writes_commit_is_told_by_its_trailer_exit_6(box: Box):
    """606: slice 1b's 291 tells this write's commit by its message where an
    unlocked writer's lands just after `git commit`. This write's message has
    the `Lane:` trailer as its second paragraph, and the subject alone never
    matched what git stored, so every such race was "cannot be told" (6,
    nothing named). Given the whole message, this write's commit is found
    under the stamp and named, nothing is replayed, and both are kept on HEAD
    (6), as `set-row-state`'s are."""
    c = box.seam()
    box.race()
    env = _git_shim(box, '*" commit -q -m handoff("*', after=_stamp(c))
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, **env)
    assert (box.root / "fired").exists(), "the stamp landed just after this write's commit"
    assert result.returncode == 6, result.stderr
    err = result.stderr
    stamp, mine = box.head(c), box.git("-C", str(c), "rev-parse", "HEAD~1").strip()
    assert box.subject(c, "HEAD~1") == SUBJECT, "this write's commit is under the stamp"
    assert box.git("-C", str(c), "log", "-1", "--format=%B", mine).strip().splitlines()[1:] == ["", f"Lane: {LANE}"]
    assert "cannot be told from another made in this checkout" not in err, err
    assert f"HEAD is {stamp}, not this write's commit {mine}" in err, err
    assert "push refused (attempt 1 of 6)" not in err, "nothing is replayed"
    assert (c / "handoffs" / "stamp.md").is_file(), "the other writer's file is still there"
    assert len(box.unpublished(c)) == 2, "both kept on HEAD"
