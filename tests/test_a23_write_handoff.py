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
from test_a23_publish_replay import LANE, Box as ReplayBox

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
    assert box.head(c) == head and box.origin_head() == tip, "publish-handoff commits nothing"


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
    assert msg[0] == SUBJECT and f"Lane: {LANE}" in msg, msg
    assert box.git("--git-dir", str(box.origin), "show", "--name-only", "--format=", "main").split() == [HANDOFF_REL]
    assert result.stdout == _line(f)
    assert "pushed origin/main" in result.stderr
    assert box.head(c) == box.origin_head() and box.unpublished(c) == []
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
    assert words in result.stderr and "Nothing was written." in result.stderr
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
    assert published == stamped(base) and published.count(STAMP) == 1
    f = c / HANDOFF_REL
    assert result.stdout == _line(f), "one line: the last attempt's"
    assert box.subjects()[0] == SUBJECT
    assert box.head(c) == box.origin_head() and box.unpublished(c) == []
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
    assert "did not prove out" in result.stderr and STAMP in result.stderr
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == "one line and no newline"
    assert box.origin_head() == tip and result.stdout == ""
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
    assert box.origin_head() == tip and result.stdout == ""
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
    assert msg[0] == subject and f"Lane: {LANE}" in msg
    assert result.stdout == _line(f)
    assert box.unpublished(c) == []
    _released(box, c)


def test_prepend_refused_by_S3_still_writes_file_no_commit(box: Box):
    """R-A11-11: a swap is never left unwritten. S3 refuses the commit (a
    foreign staged entry), the handoff is written all the same, nothing is
    committed or pushed, S3's words are printed, and so is the path (2)."""
    c = box.seam()
    f = c / HANDOFF_REL
    _staged_foreign(box, c)
    head, tip = box.head(c), box.origin_head()
    result = box.write_handoff("--prepend", str(_block(box)), "--subject", "handoff: PAUSED")
    assert result.returncode == 2, result.stderr
    assert "staged entries this write did not make: handoffs/README.md" in result.stderr
    assert "the handoff is WRITTEN and NOT committed" in result.stderr
    assert f.read_text(encoding="utf-8") == prepended(HANDOFF)
    assert result.stdout == _line(f)
    assert box.head(c) == head and box.origin_head() == tip
    assert box.git("-C", str(c), "diff", "--cached", "--name-only").split() == ["handoffs/README.md"]
    _released(box, c)


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
    assert result.stdout == "" and box.origin_head() == tip
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
    assert box.head(c) == head and box.origin_head() == tip
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
    "unbound": (("--restart", *FENCE), 2, "the publication target is not the operation-bound handoff"),
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
    assert result.stdout == "" and box.origin_head() == tip
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
    """The handoff changed under the restart: `lane-start`'s refusal (2), and
    nothing written or reserved."""
    c = box.seam()
    f = c / HANDOFF_REL
    box.restart(f)
    result = box.write_handoff("--stamp", STAMP, "--subject", SUBJECT, "--restart", *FENCE,
                               "--expected-digest", "1" * 64)
    assert result.returncode == 2, result.stderr
    assert "the restart handoff changed before its owned resume stamp" in result.stderr
    assert f.read_text(encoding="utf-8") == HANDOFF
    assert box.intent_field("prepared_digest") == "none"
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
    assert box.w_state() == w_before and box.w_reflog() == reflog
    assert (box.w / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    assert box.head(c) == box.origin_head() and box.unpublished(c) == []
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
        assert made.stdout == f"{c / HANDOFF_REL}\n" and (c / HANDOFF_REL).is_file()
    for argv in (("repoS4-9",), ("repoS4-9", "--create")):
        none = box.helper("handoff-path", *argv)
        assert none.returncode == 8, none.stderr
        assert "no row for it in the register" in none.stderr and none.stdout == ""
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
], ids=["no-mode", "no-subject", "two-modes", "whole-no-digest", "expected-no-restart",
        "stamp-two-lines", "restart-short"])
def test_usage_is_64_and_writes_nothing(box: Box, argv):
    c = box.seam()
    box.use_net()
    before = box.snapshot(c)
    result = box.write_handoff(*argv)
    assert result.returncode == 64, result.stderr
    assert box.snapshot(c) == before and box.net_ops() == []


def test_write_handoff_for_a_lane_with_no_row_is_8(box: Box):
    """No row, no handoff cell: nothing to write (8), and the stamp it would
    have written is said."""
    c = box.seam()
    before = box.snapshot(c)
    result = box.helper("write-handoff", "repoS4-9", "--stamp", STAMP, "--subject", SUBJECT)
    assert result.returncode == 8, result.stderr
    assert "row names no handoff, so there is none to write" in result.stderr
    assert f"the stamp line it would have written under the handoff's header block: {STAMP}" in result.stderr
    assert result.stdout == "" and box.snapshot(c) == before
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
    assert box.origin_file(HANDOFF_REL) == HANDOFF and result.stdout == ""
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
    assert box.w_state() == w_before and box.origin_head() == tip and result.stdout == ""


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
