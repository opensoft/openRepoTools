# SPDX-License-Identifier: Apache-2.0
"""Amendment 23 S3: before the edit, fetch, check, fast-forward — or refuse
with nothing written.

Every writer runs `checkout_sync` under its checkout's lock, before it reads
the file it writes. Its rows, in the amendment's order: a fetch that fails (or
`LANES_NO_FETCH=1`, which is one for a writer); an operation in progress or
unmerged entries; not on the branch; staged entries that are not the write's
own; unpushed commits by content; a diverged branch; a pending hand edit of the
register. The first that holds refuses with 2, names the checkout, says nothing
was written, prints its recovery, and releases the lock. Otherwise the checkout
is fast-forwarded and the edit is made on origin's tip — the 2026-10-13T13:12Z
shape (#198), clean and 10 behind with an adjacent row changed on origin, is
pushed instead of stranded.

The writes go through a clone named by the explicit `LANES_REPO` (S2.1, the
test seam), and S3 applies there as in a lane's own checkout (B1). Two cases
show the same guard through a routed lane checkout and through W with routing
off. The sandbox is the real `lanes-edit.sh`; nothing reaches a real remote.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from a23_box import REGISTER, RegisterBox, register_text
from conftest import WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

LANE = "repoS3-1"
NEIGHBOUR = "repoS3-2"
NEW_LANE = "repoS3-3"
UUID = "a23b3001-a2a2-4000-8000-a23b3001a2a2"
UUID2 = "a23b3002-a2a2-4000-8000-a23b3002a2a2"
OBJ = "opensoft/repoS3#1"
HOME_FLAG = ("--home", "opensoft/repoS3")


def _row(lane: str, uuid: str = UUID, state: str = "LIVE · seeded") -> str:
    return (f"| `{lane}` | harness `{uuid}` | Eagle / test / tester | 2026-10-20T00:00Z "
            f"| — | handoffs/repoS3/{lane}.md | {state} |")


class Box(RegisterBox):
    """Two adjacent rows, the lane's log, and a handoffs file a peer may hold."""

    def __init__(self, root: Path, **kw) -> None:
        root = Path(os.path.realpath(root))
        files = {
            REGISTER: register_text([_row(LANE), _row(NEIGHBOUR, uuid=UUID2)]),
            f"lanes/log/{LANE}.md":
                f"# lane {LANE} — object log (lane-collision-protocol Amendment 7)\n",
            "handoffs/README.md": "# handoffs\n",
        }
        super().__init__(root, files, **kw)

    def hand_edit(self, checkout: Path, lane: str = LANE, state: str = "LIVE · a hand edit") -> None:
        """An uncommitted edit of one row's state cell, as a person makes it."""
        path = checkout / REGISTER
        text = path.read_text(encoding="utf-8")
        uuid = UUID if lane == LANE else UUID2
        old = _row(lane, uuid=uuid)
        assert old in text, text
        path.write_text(text.replace(old, _row(lane, uuid=uuid, state=state)), encoding="utf-8")


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


# -------------------------------------------------------- the writing verbs

#: Each writing verb, as a caller runs it: (argv, extra environment).
VERBS = {
    "set-row-state": (("set-row-state", LANE, "LIVE · the guarded write"), {}),
    "replace-in-row": (("replace-in-row", LANE, "seeded", "reseeded", "the guarded write"), {}),
    "append-session-id": (("append-session-id", LANE, UUID, "harness `a23b3009-a2a2-4000-8000-a23b3009a2a2`"), {}),
    "append-line": ((f"append-line", f"LANDING — lane {LANE}, session {UUID}@Eagle, "
                     "2026-10-20T00:00:00Z, PR #7 into opensoft/repoS3 main"), {"LANES_LANE": LANE}),
    "add-row": (("add-row", _row(NEW_LANE, uuid="a23b3003-a2a2-4000-8000-a23b3003a2a2")), {}),
    "log": (("log", "NOTED", f"lane:{LANE}", "the guarded note", *HOME_FLAG),
            {"LANES_LANE": LANE, "LANES_SESSION": UUID}),
    "claim": (("claim", OBJ, "--no-github", *HOME_FLAG), {"LANES_LANE": LANE, "LANES_SESSION": UUID}),
    "release": (("release", OBJ, "the guarded release", "--no-github", *HOME_FLAG),
                {"LANES_LANE": LANE, "LANES_SESSION": UUID}),
    "commit": (("commit", "the guarded hand edit"), {"LANES_LANE": LANE}),
}


def run_verb(box: Box, verb: str, **extra: str):
    argv, env = VERBS[verb]
    return box.helper(*argv, **dict(env, **extra))


# -------------------------------------------------------- the rows of S3
#
# Each setup puts the checkout `c` in one state and returns the extra
# environment the write runs with and the words its refusal must carry: the
# row's own reason and its recovery.

def _local_commit(box: Box, c: Path, rel: str, text: str, message: str) -> str:
    box.write(c, rel, text)
    box.commit(c, message, rel)
    return box.git("-C", str(c), "rev-parse", "HEAD").strip()


def _rebase(box: Box, c: Path):
    """A rebase stopped on a conflict, in a file the write does not touch."""
    _local_commit(box, c, "handoffs/README.md", "# handoffs\nmine\n", "a local change")
    box.peer_pushes("handoffs/README.md", "# handoffs\ntheirs\n")
    box.git("-C", str(c), "fetch", "-q", "origin")
    box.git("-C", str(c), "rebase", "refs/remotes/origin/main", check=False)
    assert (c / ".git" / "rebase-merge").is_dir() or (c / ".git" / "rebase-apply").is_dir()
    return {}, ["a rebase is in progress", "rebase --abort", "never --continue what you did not start"]


def _merge(box: Box, c: Path):
    box.git("-C", str(c), "switch", "-q", "-c", "side")
    _local_commit(box, c, "handoffs/side.md", "side\n", "a side line")
    box.git("-C", str(c), "switch", "-q", "main")
    box.git("-C", str(c), "merge", "-q", "--no-ff", "--no-commit", "side")
    assert (c / ".git" / "MERGE_HEAD").exists()
    return {}, ["a merge is in progress", "merge --abort"]


def _cherry_pick(box: Box, c: Path):
    head = box.git("-C", str(c), "rev-parse", "HEAD").strip()
    (c / ".git" / "CHERRY_PICK_HEAD").write_text(head + "\n", encoding="utf-8")
    return {}, ["a cherry-pick is in progress", "cherry-pick --abort"]


def _revert(box: Box, c: Path):
    head = box.git("-C", str(c), "rev-parse", "HEAD").strip()
    (c / ".git" / "REVERT_HEAD").write_text(head + "\n", encoding="utf-8")
    return {}, ["a revert is in progress", "revert --abort"]


def _unmerged(box: Box, c: Path):
    """Unmerged entries with no operation recorded: a conflicted merge whose
    MERGE_HEAD is gone."""
    box.git("-C", str(c), "switch", "-q", "-c", "side")
    _local_commit(box, c, "handoffs/README.md", "# handoffs\nside\n", "side")
    box.git("-C", str(c), "switch", "-q", "main")
    _local_commit(box, c, "handoffs/README.md", "# handoffs\nmain\n", "main")
    box.git("-C", str(c), "merge", "-q", "side", check=False)
    for name in ("MERGE_HEAD", "MERGE_MSG", "MERGE_MODE"):
        (c / ".git" / name).unlink(missing_ok=True)
    assert box.git("-C", str(c), "ls-files", "-u").strip()
    return {}, ["unmerged entries: handoffs/README.md", "git -C"]


def _detached(box: Box, c: Path):
    box.git("-C", str(c), "checkout", "-q", "--detach")
    return {}, ["HEAD is detached, not refs/heads/main", "switch main"]


def _branch(box: Box, c: Path):
    box.git("-C", str(c), "switch", "-q", "-c", "elsewhere")
    return {}, ["HEAD is refs/heads/elsewhere, not refs/heads/main", "switch main"]


def _staged(box: Box, c: Path):
    box.write(c, "handoffs/README.md", "# handoffs\na peer's staged line\n")
    box.git("-C", str(c), "add", "--", "handoffs/README.md")
    return {}, ["staged entries this write did not make: handoffs/README.md",
                "restore --staged -- handoffs/README.md",
                "never commit staged entries you did not make"]


def _unpushed(box: Box, c: Path):
    sha = _local_commit(box, c, "handoffs/repoS3/note.md", "a note\n", "an unpushed note")
    return {}, ["1 unpublished commit(s)", f"+ {sha}", "cherry -v origin/main HEAD",
                "the publish act", "reset --keep origin/main"]


def _diverged(box: Box, c: Path):
    """Every commit on HEAD already on origin by content, under another sha."""
    _local_commit(box, c, "handoffs/README.md", "# handoffs\nthe same line\n", "mine")
    box.peer_pushes("handoffs/README.md", "# handoffs\nthe same line\n")
    return {}, ["this checkout has diverged", "reset --keep origin/main"]


def _fetch_fails(box: Box, c: Path):
    box.use_net('[ "$1" = fetch ] && { echo "fatal: unable to access origin" >&2; exit 128; }\nexit 0\n')
    return {}, ["the fetch of origin main failed", "unable to access origin",
                f"git -C {c} fetch origin main"]


def _no_fetch(box: Box, c: Path):
    return {"LANES_NO_FETCH": "1"}, ["LANES_NO_FETCH=1 is set",
                                     "a fetch that did not run is a fetch that failed"]


def _pending_register(box: Box, c: Path):
    box.hand_edit(c, lane=NEIGHBOUR, state="LIVE · a peer's half-written cell")
    return {}, ["lanes/LANES.md holds an uncommitted edit", "which may be a peer's",
                " commit \"<what the edit is>\""]


ROWS = {
    "rebase": _rebase,
    "merge": _merge,
    "cherry-pick": _cherry_pick,
    "revert": _revert,
    "unmerged": _unmerged,
    "detached": _detached,
    "branch": _branch,
    "staged": _staged,
    "unpushed": _unpushed,
    "diverged": _diverged,
    "fetch-fails": _fetch_fails,
    "no-fetch": _no_fetch,
    "pending-register": _pending_register,
}

#: `commit` CARRIES a pending register hand edit (S3 step 4); that row is
#: `test_a23_publish_replay`'s, and here it is the one pair left out.
CASES = [(v, r) for r in ROWS for v in VERBS if not (v == "commit" and r == "pending-register")]


@pytest.mark.parametrize("verb,row", CASES, ids=[f"{v}--{r}" for v, r in CASES])
def test_every_S3_row_refuses_every_writer_with_nothing_written(box: Box, verb: str, row: str):
    c = box.seam()
    extra, words = ROWS[row](box, c)
    if verb == "commit":
        # `commit` with nothing of its own is the publish act, which the
        # unpushed row exempts; the guard is asked of its hand-edit form.
        box.hand_edit(c)
    before = box.snapshot(c)
    w_before = box.w_state()
    result = run_verb(box, verb, **extra)
    err = result.stderr
    assert result.returncode == 2, (result.stdout, err)
    assert f"in {c}:" in err, "the refusal names the checkout"
    assert "Nothing was written." in err, err
    for phrase in words:
        assert phrase in err, (phrase, err)
    if row == "pending-register":
        # The recovery names the lane the write is for: `add-row`'s is the row's.
        assert f"LANES_LANE={NEW_LANE if verb == 'add-row' else LANE} " in err, err
    assert box.snapshot(c) == before, "HEAD, the branch, the index, the tree and origin are as they were"
    assert box.w_state() == w_before, "W is untouched"
    assert not box.lock_of(c).exists(), "the lock is released"


# -------------------------------------------------------- the fast-forward

def test_ff_refusal_names_the_file(box: Box):
    """An unstaged change to a file origin has since changed: git refuses the
    fast-forward rather than overwrite it, and the refusal is S3's, quoting
    git and naming the file."""
    c = box.seam()
    box.write(c, "handoffs/README.md", "# handoffs\na peer's line, mid-write\n")
    box.peer_pushes("handoffs/README.md", "# handoffs\norigin's newer line\n")
    before = box.snapshot(c)
    result = run_verb(box, "set-row-state")
    assert result.returncode == 2, result.stderr
    assert "the fast-forward to origin/main refused" in result.stderr
    assert "handoffs/README.md" in result.stderr, "git's words name the file"
    assert "Nothing was written." in result.stderr
    assert box.snapshot(c) == before
    assert (c / "handoffs/README.md").read_text(encoding="utf-8") == "# handoffs\na peer's line, mid-write\n"
    assert not box.lock_of(c).exists()


def test_unstaged_change_origin_did_not_touch_does_not_block(box: Box):
    """Ratified choice 8: an unstaged change to another tracked file is not a
    refusal on its own. It blocks only where the fast-forward would overwrite
    it — and here origin moved a row of the register, not that file."""
    c = box.seam()
    box.write(c, "handoffs/README.md", "# handoffs\na peer's line, mid-write\n")
    box.peer_edits(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                   _row(NEIGHBOUR, uuid=UUID2, state="LIVE · the neighbour moved"))
    for verb in ("set-row-state", "log", "claim"):
        result = run_verb(box, verb)
        assert result.returncode == 0, (verb, result.stderr)
    register = box.origin_register()
    assert " · the guarded write |" in register
    assert "LIVE · the neighbour moved" in register, "the edit was made on origin's tip"
    assert "the guarded note" in box.origin_file(f"lanes/log/{LANE}.md")
    assert box.git("-C", str(c), "diff", "--name-only").split() == ["handoffs/README.md"]
    assert box.origin_file("handoffs/README.md") == "# handoffs\n", "the peer's line was never committed"


def test_the_1312Z_shape_is_pushed(box: Box):
    """#198's measurement, 2026-10-13T13:12Z: a private clone, clean, 0 ahead
    and 10 behind, whose adjacent row origin had changed, stranded all three
    of a launch's writes within 29 seconds. Fetched and fast-forwarded first,
    the row stamp and the log line are both pushed, and nothing is left
    unpublished."""
    c = box.seam()
    for n in range(9):
        box.peer_pushes(f"handoffs/repoS3/peer-{n}.md", f"peer {n}\n")
    box.peer_edits(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                   _row(NEIGHBOUR, uuid=UUID2, state="LIVE · the adjacent row, changed on origin"))
    box.git("-C", str(c), "fetch", "-q", "origin")
    assert box.git("-C", str(c), "rev-list", "--left-right", "--count",
                   "HEAD...refs/remotes/origin/main").split() == ["0", "10"]
    stamp = run_verb(box, "set-row-state")
    assert stamp.returncode == 0, stamp.stderr
    note = run_verb(box, "log")
    assert note.returncode == 0, note.stderr
    register = box.origin_register()
    assert " · the guarded write |" in register
    assert "the adjacent row, changed on origin" in register
    assert "the guarded note" in box.origin_file(f"lanes/log/{LANE}.md")
    assert box.unpublished(c) == [], "no `+` under git cherry: nothing stranded"
    assert box.git("-C", str(c), "rev-parse", "HEAD") == box.origin_head() + "\n"


# -------------------------------------------------------- every writer, routed or not

def test_S3_applies_through_a_routed_lane_checkout(box: Box):
    """B1: the lane's own checkout, made by routing, takes the same guard."""
    first = run_verb(box, "set-row-state")
    assert first.returncode == 0, first.stderr
    lc = box.checkout(LANE)
    assert lc.is_dir()
    _local_commit(box, lc, "handoffs/repoS3/note.md", "a note\n", "an unpushed note")
    before = box.snapshot(lc)
    result = run_verb(box, "log")
    assert result.returncode == 2, result.stderr
    assert f"in {lc}:" in result.stderr and "unpublished commit" in result.stderr
    assert box.snapshot(lc) == before
    assert not box.lock_of(lc).exists()


def test_S3_applies_without_the_opt_in(tmp_path: Path):
    """B1: with routing off a write goes through W, as on main — and S3 and S4
    are #198's fix for exactly that checkout, so they apply there too."""
    box = Box(tmp_path, route=False)
    _local_commit(box, box.w, "handoffs/repoS3/note.md", "a note\n", "an unpushed note in W")
    before = box.snapshot(box.w)
    result = run_verb(box, "set-row-state")
    assert result.returncode == 2, result.stderr
    assert f"in {box.w}:" in result.stderr and "unpublished commit" in result.stderr
    assert box.snapshot(box.w) == before
    assert not box.lanes_root.exists(), "nothing was routed"


def test_W_behind_is_fast_forwarded_by_a_write_through_it(tmp_path: Path):
    """With routing off, the write through W fast-forwards W first (S3): the
    edit is made on origin's tip and W is left at it, with nothing ahead."""
    box = Box(tmp_path, route=False)
    box.peer_edits(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                   _row(NEIGHBOUR, uuid=UUID2, state="LIVE · moved on origin"))
    result = run_verb(box, "set-row-state")
    assert result.returncode == 0, result.stderr
    assert "LIVE · moved on origin" in box.origin_register()
    assert box.unpublished(box.w) == []
    assert box.git("-C", str(box.w), "rev-parse", "HEAD") == box.origin_head() + "\n"
