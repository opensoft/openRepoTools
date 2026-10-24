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
import re
import shlex
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
    return {}, ["1 unpublished commit(s)", f"+ {sha}", "cherry -v refs/remotes/origin/main HEAD",
                "the publish act", "reset --keep refs/remotes/origin/main"]


def _diverged(box: Box, c: Path):
    """Every commit on HEAD already on origin by content, under another sha."""
    _local_commit(box, c, "handoffs/README.md", "# handoffs\nthe same line\n", "mine")
    box.peer_pushes("handoffs/README.md", "# handoffs\nthe same line\n")
    return {}, ["this checkout has diverged", "reset --keep refs/remotes/origin/main"]


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
    unpublished.

    The stamp must push on its FIRST attempt, and the two asserts on it say so
    apart (rv1b's SHOULD 2): without S3's fast-forward the stamp edits the
    stale tree, its push is refused, and the replay's `reset --keep` catches up
    instead, so attempt 2 reaches the same end state and every other assert
    here still holds (m1b's S10 survived that way)."""
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
    assert "pushed origin/main (attempt 1)" in stamp.stderr, stamp.stderr
    assert "push refused" not in stamp.stderr, stamp.stderr
    note = run_verb(box, "log")
    assert note.returncode == 0, note.stderr
    register = box.origin_register()
    assert " · the guarded write |" in register
    assert "the adjacent row, changed on origin" in register
    assert "the guarded note" in box.origin_file(f"lanes/log/{LANE}.md")
    assert box.unpublished(c) == [], "no `+` under git cherry: nothing stranded"
    assert box.git("-C", str(c), "rev-parse", "HEAD") == box.origin_head() + "\n"


def test_a_stray_copy_from_a_rename_that_never_landed_is_named_as_one(box: Box):
    """rv1b's NIT 2: S3's fast-forward brings an old-cased PUBLISHED log into a
    checkout that holds the canonical file untracked — what a case-only rename
    whose commit never landed leaves. `ensure_log` then sees two files, and
    15(d)'s hand merge is the wrong recovery for a stray copy: a commit of it
    would publish a second file for one lane. The refusal names the tracked
    log and the untracked copy, and the cure is to remove the copy and re-run,
    after which the write renames the published log once, in its own commit."""
    c = box.seam()
    old_cased = f"lanes/log/{NEIGHBOUR.lower()}.md"
    canonical = f"lanes/log/{NEIGHBOUR}.md"
    header = f"# lane {NEIGHBOUR} — object log (lane-collision-protocol Amendment 7)\n"
    box.peer_pushes(old_cased, header)
    stray = box.write(c, canonical, header)
    origin_before = box.origin_head()
    note = ("log", "NOTED", f"lane:{NEIGHBOUR}", "the stray-copy note", *HOME_FLAG)
    env = {"LANES_LANE": NEIGHBOUR, "LANES_SESSION": UUID2}
    result = box.helper(*note, **env)
    err = result.stderr
    assert result.returncode == 2, (result.stdout, err)
    assert f"{stray} is NOT TRACKED" in err, err
    assert "a case-only rename whose commit never landed" in err, err
    assert f'rm -- "{stray}"' in err, err
    assert "renames the tracked log once, inside its own commit" in err, err
    assert "Merge them by hand" not in err, "15(d)'s hand merge is not this state's recovery"
    assert "Nothing was written." in err, err
    assert box.origin_head() == origin_before, "nothing was published"
    assert stray.read_text(encoding="utf-8") == header, "the copy is left as it was"
    assert not box.lock_of(c).exists(), "the lock is released"
    stray.unlink()
    again = box.helper(*note, **env)
    assert again.returncode == 0, again.stderr
    assert "the stray-copy note" in box.origin_file(canonical)
    logs = box.git("--git-dir", str(box.origin), "ls-tree", "--name-only", "main", "lanes/log/").split()
    assert canonical in logs, logs
    assert old_cased not in logs, "the rename landed in the write's own commit"


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
    assert f"in {lc}:" in result.stderr
    assert "unpublished commit" in result.stderr
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
    assert f"in {box.w}:" in result.stderr
    assert "unpublished commit" in result.stderr
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


@pytest.mark.parametrize("state", ["untracked", "committed"])
def test_a_migration_dry_run_names_a_rename_that_never_landed_and_never_says_pull(box: Box, state: str):
    """rv1b-c2's NIT 4: migrate-state-cells' dry run met a lane whose log is
    published under one case while this checkout has it under another, and
    said "Pull first, or merge them (15(d))". No writer pulls now, a hand pull
    in a shared checkout is the 1312Z hazard, and a hand merge of a stray copy
    would publish a second file for one lane. The skip line now says which
    state it is: the copy a rename's two `mv`s left, NOT TRACKED, with
    `ensure_log`'s recovery (compare, remove the copy, put the published log
    back, re-run); or a rename committed here and never published, with the
    publish act. The dry run writes nothing either way."""
    c = box.seam()
    old_cased = f"lanes/log/{NEIGHBOUR.lower()}.md"
    canonical = f"lanes/log/{NEIGHBOUR}.md"
    header = f"# lane {NEIGHBOUR} — object log (lane-collision-protocol Amendment 7)\n"
    box.peer_pushes(old_cased, header)
    box.git("-C", str(c), "fetch", "-q", "origin")
    box.git("-C", str(c), "merge", "-q", "--ff-only", "refs/remotes/origin/main")
    (c / old_cased).rename(c / canonical)
    if state == "committed":
        box.git("-C", str(c), "add", "-A", "--", "lanes/log")
        box.git("-C", str(c), "commit", "-q", "-m", f"LANES({NEIGHBOUR}@Eagle): a rename that never landed")
    before = box.snapshot(c)
    result = box.helper("migrate-state-cells")
    out = result.stdout
    assert result.returncode == 0, (out, result.stderr)
    assert "DRY RUN — nothing was written" in out, out
    line = next((l for l in out.splitlines() if l.strip().startswith(f"{NEIGHBOUR} ")), "")
    assert "a case-only rename whose commit never landed" in line, out
    assert "Pull first" not in out, "no writer pulls, so no recovery is a pull"
    assert "merge them" not in line, "15(d)'s hand merge is not this state's recovery"
    if state == "untracked":
        assert f"{NEIGHBOUR}.md NOT TRACKED" in line, line
        assert f'rm -- "{c / canonical}"' in line, line
        assert f"git -C {c} checkout HEAD -- {old_cased}" in line, line
    else:
        assert "committed here and not on origin" in line, line
        assert "The publish act refuses it" in line, "#214's fence takes no rename, so it is not the recovery"
        assert f"git -C {c} push origin HEAD:refs/heads/archive/{NEIGHBOUR}-stranded-" in line, line
        assert f"git -C {c} reset --keep origin/main" in line, line
    assert box.snapshot(c) == before, "a dry run writes nothing"
    if state == "untracked":
        (c / canonical).unlink()
        box.git("-C", str(c), "checkout", "HEAD", "--", old_cased)
    else:
        box.git("-C", str(c), "push", "-q", "origin", f"HEAD:refs/heads/archive/{NEIGHBOUR}-stranded-test")
        box.git("-C", str(c), "reset", "-q", "--keep", "refs/remotes/origin/main")
    again = box.helper("migrate-state-cells")
    assert again.returncode == 0, (again.stdout, again.stderr)
    assert "SKIPPED" not in again.stdout, "the recovery the line gives settles it"


def test_a_migration_dry_run_never_calls_a_staged_rename_committed(box: Box):
    """rv1b-c3's NIT D (its probe P1): the dry run asked `ls-files
    --error-unmatch` whether the rename was committed, and that reads the
    INDEX. A case-only rename that was STAGED and never committed (a write's
    `git commit` failed after its `add`) was called "committed here and not
    on origin" and given the archive recovery: an archive branch identical to
    main on origin, and a `reset --keep` that only unstaged it, which left the
    stray copy for the next dry run to name. "Committed" is said only where
    HEAD holds the file; a rename that is only staged is unstaged
    (`restore --staged`), with no archive step, and the stray-copy recovery
    that follows is the one the next line gives. The dry run writes nothing."""
    c = box.seam()
    old_cased = f"lanes/log/{NEIGHBOUR.lower()}.md"
    canonical = f"lanes/log/{NEIGHBOUR}.md"
    header = f"# lane {NEIGHBOUR} — object log (lane-collision-protocol Amendment 7)\n"
    box.peer_pushes(old_cased, header)
    box.git("-C", str(c), "fetch", "-q", "origin")
    box.git("-C", str(c), "merge", "-q", "--ff-only", "refs/remotes/origin/main")
    (c / old_cased).rename(c / canonical)
    box.git("-C", str(c), "add", "-A", "--", "lanes/log")
    assert box.git("-C", str(c), "rev-parse", "HEAD").strip() == box.origin_head(), "nothing is committed"
    before = box.snapshot(c)
    result = box.helper("migrate-state-cells")
    out = result.stdout
    assert result.returncode == 0, (out, result.stderr)
    line = next((l for l in out.splitlines() if l.strip().startswith(f"{NEIGHBOUR} ")), "")
    assert line, out
    assert "committed here" not in line, "a staged rename is not a committed one"
    assert f"{NEIGHBOUR}.md STAGED and not committed" in line, line
    assert "a case-only rename whose commit never landed" in line, line
    assert "push origin HEAD:refs/heads/archive/" not in line, "there is no commit to archive"
    assert "reset --keep" not in line, "that only unstages it, after an archive nobody needed"
    unstage = f"git -C {c} restore --staged -- {old_cased} {canonical}"
    assert unstage in line, line
    assert box.snapshot(c) == before, "a dry run writes nothing"
    # The recovery the line gives, step by step: unstaged, the copy is the
    # NOT TRACKED state and the next line says so; its own recovery then
    # settles it.
    box.git(*shlex.split(unstage)[1:])
    mid = box.helper("migrate-state-cells")
    mid_line = next((l for l in mid.stdout.splitlines() if l.strip().startswith(f"{NEIGHBOUR} ")), "")
    assert f"{NEIGHBOUR}.md NOT TRACKED" in mid_line, mid.stdout
    (c / canonical).unlink()
    box.git("-C", str(c), "checkout", "HEAD", "--", old_cased)
    again = box.helper("migrate-state-cells")
    assert again.returncode == 0, (again.stdout, again.stderr)
    assert "SKIPPED" not in again.stdout, "the recovery the line gives settles it"


@pytest.mark.parametrize("pair", ["stray-copy", "committed-rename"])
def test_a_migration_dry_run_names_a_stray_copy_beside_the_published_log_as_one(box: Box, pair: str):
    """NIT 4's neighbour: the same scan's line for a checkout holding two logs
    whose names differ only by case said "15(d)'s hand merge" of the
    stray-copy state, `ensure_log`'s B36 state: the published log tracked
    and, beside it, the untracked copy a case-only rename whose commit never
    landed leaves. A hand merge would commit the copy as a second published
    file for one lane. The line now gives B36's recovery (compare, remove
    the copy, re-run), the dry run writes nothing, and the recovery settles
    it. Where the tracked one is NOT the published log (a rename committed
    here, the published spelling back beside it untracked), removing the
    untracked one would remove the published spelling, so that recovery is
    never given there."""
    c = box.seam()
    old_cased = f"lanes/log/{NEIGHBOUR.lower()}.md"
    canonical = f"lanes/log/{NEIGHBOUR}.md"
    header = f"# lane {NEIGHBOUR} — object log (lane-collision-protocol Amendment 7)\n"
    box.peer_pushes(old_cased, header)
    box.git("-C", str(c), "fetch", "-q", "origin")
    box.git("-C", str(c), "merge", "-q", "--ff-only", "refs/remotes/origin/main")
    if pair == "stray-copy":
        untracked = box.write(c, canonical, header)
    else:
        (c / old_cased).rename(c / canonical)
        box.git("-C", str(c), "add", "-A", "--", "lanes/log")
        box.git("-C", str(c), "commit", "-q", "-m", f"LANES({NEIGHBOUR}@Eagle): a rename that never landed")
        untracked = box.write(c, old_cased, header)
    before = box.snapshot(c)
    result = box.helper("migrate-state-cells")
    out = result.stdout
    assert result.returncode == 0, (out, result.stderr)
    assert "DRY RUN — nothing was written" in out, out
    line = next((l for l in out.splitlines() if l.strip().startswith(f"{NEIGHBOUR} ")), "")
    assert line, out
    assert box.snapshot(c) == before, "a dry run writes nothing"
    if pair == "committed-rename":
        assert "NOT TRACKED" not in line, line
        assert "rm --" not in line, "the untracked file is the published spelling, never to be removed"
        return
    assert "hand merge" not in line, "15(d)'s hand merge is not this state's recovery"
    assert "a case-only rename whose commit never landed" in line, line
    assert f"published as {old_cased}, and this checkout also has {NEIGHBOUR}.md beside it, NOT TRACKED" in line, line
    assert f'diff -- "{c / old_cased}" "{untracked}"' in line, line
    assert f'rm -- "{untracked}"' in line, line
    untracked.unlink()
    again = box.helper("migrate-state-cells")
    assert again.returncode == 0, (again.stdout, again.stderr)
    assert "SKIPPED" not in again.stdout, "the recovery the line gives settles it"


# -------------------------------------------- the managed seam, after S3 too
#
# 283 of lane openRepoTools-3's review of #307 (its P2). The legacy row verbs,
# `rename-lane` and `write_event`'s lane verbs asked the managed seam before
# the lock, on the ref as last fetched (`set-row-state` runs no `log_sync` at
# all), and S3's fetch and fast-forward then brought in what the seam never
# saw: the managed ledger's marker in the lane's state cell. `set-row-state`
# wrote over it (0), and the marker was gone from origin. Ruled 2026-10-04:
# "managed ledger owns enrolled lanes; #97 owns legacy".

MARKER = "MANAGED OWNER · ledger-1"
S3_REFSPEC = "+refs/heads/main:refs/remotes/origin/main"

#: Each legacy act the seam guards, on lane LANE: (argv, extra environment,
#: what must not be on origin after it).
SEAM_ACTS = {
    "set-row-state": (("set-row-state", LANE, "LIVE · a legacy write"), {}, " · a legacy write |"),
    "replace-in-row": (("replace-in-row", LANE, "tester", "tester-x", "a legacy replace"), {}, "tester-x"),
    "append-session-id": (("append-session-id", LANE, UUID, "harness `a23b3009-a2a2-4000-8000-a23b3009a2a2`"),
                          {}, "a23b3009"),
    "rename-lane": (("rename-lane", LANE, "repoS3-9", "a legacy rename", "--no-github"),
                    {"LANES_SESSION": UUID}, "repoS3-9"),
    "log-PAUSED": (("log", "PAUSED", f"lane:{LANE}", "→", "swap; dir /nowhere", "a legacy pause"),
                   {"LANES_LANE": LANE, "LANES_SESSION": UUID}, "a legacy pause"),
}


def _the_ledger_enrols_at_s3s_fetch(box: Box) -> str:
    """The managed ledger writes its marker into lane LANE's state cell, and
    its commit lands on origin at this write's S3 fetch (its refspec): after
    the write's own seam check before the lock, before the fast-forward.
    Returns the row as the ledger left it."""
    seed = shlex.quote(str(box.seed))
    box.git("-C", str(box.seed), "pull", "-q", "--ff-only", "origin", "main")
    path = box.seed / REGISTER
    text = path.read_text(encoding="utf-8")
    enrolled = _row(LANE, state=MARKER)
    path.write_text(text.replace(_row(LANE), enrolled), encoding="utf-8")
    box.commit(box.seed, "the ledger enrols the lane", REGISTER)
    count = shlex.quote(str(box.root / "s3hook.count"))
    box.use_net('[ "$1" = fetch ] || exit 0' + "\n" +
                f'case "$*" in *"{S3_REFSPEC}"*) : ;; *) exit 0 ;; esac' + "\n" +
                f"[ -e {count} ] && exit 0" + "\n" +
                f"echo 1 > {count}" + "\n" +
                f"git -C {seed} push -q origin main" + "\n" + "exit 0" + "\n")
    return enrolled


@pytest.mark.parametrize("act", sorted(SEAM_ACTS))
def test_a_marker_S3_brings_in_is_asked_again_and_refuses_the_legacy_act(box: Box, act: str):
    """283: the seam is asked again right after S3, on what the fast-forward
    brought in. A marker that landed under the write refuses it (2), nothing
    is written, and origin keeps the ledger's row as the ledger wrote it."""
    c = box.seam()
    enrolled = _the_ledger_enrols_at_s3s_fetch(box)
    argv, env, never = SEAM_ACTS[act]
    result = box.helper(*argv, **env)
    assert (box.root / "s3hook.count").exists(), "the marker landed at S3's fetch"
    assert result.returncode == 2, result.stderr
    assert f"lane {LANE} is owned by the managed ledger" in result.stderr, result.stderr
    assert "Nothing was written" in result.stderr
    register = box.origin_register()
    assert enrolled in register.splitlines(), "the ledger's row is as the ledger wrote it"
    assert never not in register and never not in box.origin_file(f"lanes/log/{LANE}.md")
    assert "push" not in box.net_ops(), "refused before any push"
    assert box.unpublished(c) == []
    assert not box.lock_of(c).exists()


def test_a_diverged_checkout_holding_a_hand_merge_is_told_to_archive_first(box: Box):
    """NIT 287 of lane openRepoTools-3's review of #307: S3 step 6 said
    "every commit on it is on origin already by content" and printed
    `reset --keep origin/main`. `git cherry` skips merge commits, so a hand
    merge carrying a line of its own read as nothing unpublished, and the
    printed reset would drop that line. Where HEAD holds a merge origin
    lacks, the refusal (2, nothing written) now says so, and gives S6.3's
    archive before the reset."""
    c = box.seam()
    box.peer_pushes("handoffs/repoS3/peer.md", "a peer's file" + "\n")
    box.git("-C", str(c), "fetch", "-q", "origin")
    box.git("-C", str(c), "merge", "-q", "--no-ff", "-m", "a hand merge", "refs/remotes/origin/main")
    box.write(c, "handoffs/repoS3/only-in-the-merge.md", "a line the merge alone carries" + "\n")
    box.git("-C", str(c), "add", "--", "handoffs/repoS3/only-in-the-merge.md")
    box.git("-C", str(c), "commit", "-q", "--amend", "--no-edit")
    assert box.unpublished(c) == [], "cherry calls the merge published"
    before = box.snapshot(c)
    result = run_verb(box, "set-row-state")
    assert result.returncode == 2, result.stderr
    err = result.stderr
    assert "holds 1 merge commit(s) origin lacks" in err, err
    archive = err.find(f"git -C {c} push origin HEAD:refs/heads/archive/{LANE}-stranded-")
    reset = err.find(f"git -C {c} reset --keep refs/remotes/origin/main")
    assert 0 <= archive < reset, err
    assert "STOP and take it to the lane its subject names" in err
    assert "the content is already published" not in err, "a merge's content is not"
    assert box.snapshot(c) == before, "nothing was written"
    assert not box.lock_of(c).exists()


@pytest.mark.parametrize("row", ["unpushed", "diverged"])
def test_s3s_recovery_commands_read_origin_past_a_local_branch_named_origin_main(box: Box, row: str):
    """333 and 342 of lane openRepoTools-3's re-check of #307: a local
    branch named `origin/main` wins the short name over the tracking ref. S3
    compares by the full ref, but step 5's list line said `cherry -v
    origin/main HEAD`, which then listed nothing, and steps 5 and 6 said
    `reset --keep origin/main`, which reset to that branch, not to origin.
    They name `refs/remotes/origin/main` now, and followed word for word
    they read origin."""
    c = box.seam()
    if row == "unpushed":
        sha = _local_commit(box, c, "handoffs/repoS3/note.md", "a note\n", "an unpushed note")
    else:
        _local_commit(box, c, "handoffs/README.md", "# handoffs\nthe same line\n", "mine")
        box.peer_pushes("handoffs/README.md", "# handoffs\nthe same line\n")
    box.git("-C", str(c), "branch", "origin/main", "HEAD")   # the shadow
    result = run_verb(box, "set-row-state")
    err = result.stderr
    assert result.returncode == 2, err
    if row == "unpushed":
        listed = re.search(r"list them: git (-C \S+ cherry -v \S+ HEAD)", err)
        assert listed, err
        out = box.git(*shlex.split(listed.group(1)))
        assert f"+ {sha}" in out, (out, err)
    reset = re.search(r"git (-C \S+ reset --keep \S+)", err)
    assert reset, err
    box.git(*shlex.split(reset.group(1)))
    assert box.git("-C", str(c), "rev-parse", "HEAD").strip() == box.origin_head(), "the reset reached origin's tip"


def test_a_migration_dry_run_gives_an_untracked_log_a_recovery_that_works(box: Box):
    """NIT 288 of lane openRepoTools-3's review of #307 (pre-existing): the
    migration's line for a lane whose log is here and NOT TRACKED said
    "Commit it first (`git -C <c> commit -m ... -- <log>`)", and git answers
    that pathspec of an untracked file with "did not match any file(s) known
    to git" (1). And such a commit is an unpublished one, which S3 then
    refuses every writer over. The line now says `git add`, then the pathspec
    commit in this checkout, then the publish act, and following it settles
    the skip."""
    c = box.seam()
    rel = f"lanes/log/{NEIGHBOUR}.md"
    box.write(c, rel, f"# lane {NEIGHBOUR} — object log (lane-collision-protocol Amendment 7)" + "\n")
    result = box.helper("migrate-state-cells")
    out = result.stdout
    assert result.returncode == 0, (out, result.stderr)
    assert "DRY RUN — nothing was written" in out, out
    line = next((l for l in out.splitlines() if l.strip().startswith(f"{NEIGHBOUR} ")), "")
    assert "NOT TRACKED" in line, out
    assert f"git -C {c} add -- {rel} && git -C {c} commit -m" in line, line
    assert "the publish act (LANES_LANE=<lane>" in line, line
    box.git("-C", str(c), "add", "--", rel)
    box.git("-C", str(c), "commit", "-q", "-m", f"{NEIGHBOUR}(its log)", "--", rel)
    published = box.helper("commit", "its log", LANES_LANE=NEIGHBOUR)
    assert published.returncode == 0, published.stderr
    assert box.origin_file(rel).startswith(f"# lane {NEIGHBOUR}"), "the publish act sent it"
    again = box.helper("migrate-state-cells")
    assert again.returncode == 0, (again.stdout, again.stderr)
    assert "NOT TRACKED" not in again.stdout, "the recovery the line gives settles it"


def test_retire_rows_gives_an_untracked_log_the_same_recovery_and_it_works(box: Box):
    """NIT 288's siblings: `retire-rows` (and `archive-rows`, for the archive
    file) refused an untracked file with the same `commit -m … -- <path>`
    that git refuses. They say what the migration now says, and following it
    lets the sweep run."""
    c = box.seam()
    rel = f"lanes/log/{NEIGHBOUR}.md"
    box.write(c, rel, f"# lane {NEIGHBOUR} — object log (lane-collision-protocol Amendment 7)" + "\n")
    result = box.helper("retire-rows", NEIGHBOUR, LANES_LANE=LANE, LANES_SESSION=UUID)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "NOT TRACKED" in result.stderr, result.stderr
    assert f"git -C {c} add -- {rel} && git -C {c} commit -m" in result.stderr, result.stderr
    assert f"the publish act (LANES_LANE={LANE} " in result.stderr, "331: the lane it ran for"
    assert "Nothing was written" in result.stderr
    box.git("-C", str(c), "add", "--", rel)
    box.git("-C", str(c), "commit", "-q", "-m", f"{NEIGHBOUR}(its log)", "--", rel)
    published = box.helper("commit", "its log", LANES_LANE=LANE)
    assert published.returncode == 0, published.stderr
    again = box.helper("retire-rows", NEIGHBOUR, LANES_LANE=LANE, LANES_SESSION=UUID)
    assert again.returncode == 0, (again.stdout, again.stderr)
    assert f"RETIRED — lane {NEIGHBOUR}" in box.origin_file(rel)


def _a_log_nobody_tracks(checkout: Path) -> str:
    rel = f"lanes/log/{NEIGHBOUR}.md"
    RegisterBox.write(checkout, rel, f"# lane {NEIGHBOUR} — object log (lane-collision-protocol Amendment 7)" + "\n")
    return rel


def test_under_the_opt_in_a_migration_dry_run_in_W_gives_no_commit_in_W(box: Box):
    """331 of lane openRepoTools-3's re-check of #307: under the opt-in the
    migration's dry run is not routed, so it reads W, and 288's recovery said
    to commit there. Followed word for word, the commit went into W; the
    publish act routed to the lane's own checkout, found nothing to send
    there and exited 0; origin never got the log; and W was left holding a
    commit that S5 and `refresh-workspace` then refused. The line now says W
    takes no commit and gives the move into its maker's own lane checkout,
    and following that, with the maker's lane for `<lane>`, publishes the
    log and leaves W with nothing of its own."""
    rel = _a_log_nobody_tracks(box.w)
    result = box.helper("migrate-state-cells")
    out = result.stdout
    assert result.returncode == 0, (out, result.stderr)
    line = next((l for l in out.splitlines() if l.strip().startswith(f"{NEIGHBOUR} ")), "")
    assert "NOT TRACKED" in line, out
    assert "takes no commit (Amendment 23 S5)" in line, line
    assert f"git -C {box.w} add" not in line and f"git -C {box.w} commit" not in line, line
    assert f"mv -- {box.w}/{rel} {box.lanes_root}/<lane>/{rel}" in line, line
    assert f"git -C {box.lanes_root}/<lane> add -- {rel} && git -C {box.lanes_root}/<lane> commit -m" in line, line
    assert "the publish act (LANES_LANE=<lane>" in line, line
    assert f"rm -- {box.w}/{rel}" in line, line
    # Word for word, with the maker's own lane for <lane>.
    lc = box.checkout(NEIGHBOUR)
    made = box.helper("lane-checkout", NEIGHBOUR, "--create")
    assert made.returncode == 0 and made.stdout.strip() == str(lc), (made.stdout, made.stderr)
    (box.w / rel).rename(lc / rel)
    box.git("-C", str(lc), "add", "--", rel)
    box.git("-C", str(lc), "commit", "-q", "-m", f"{NEIGHBOUR}(its log)", "--", rel)
    published = box.helper("commit", "its log", LANES_LANE=NEIGHBOUR)
    assert published.returncode == 0, published.stderr
    assert box.origin_file(rel).startswith(f"# lane {NEIGHBOUR}"), "the publish act sent it"
    assert box.unpublished(box.w) == [], "W holds no commit of its own"
    assert box.git("-C", str(box.w), "status", "--porcelain", "--untracked-files=all") == ""
    refreshed = box.helper("refresh-workspace")
    assert refreshed.returncode == 0, refreshed.stderr
    again = box.helper("migrate-state-cells")
    assert again.returncode == 0, (again.stdout, again.stderr)
    assert "NOT TRACKED" not in again.stdout, "the recovery the line gives settles it"


def test_a_routed_sweep_names_its_runners_lane_in_the_publish_act(box: Box):
    """331's other half: a routed `retire-rows` goes through its runner's own
    checkout, and the publish act it printed said `LANES_LANE=<lane>`, which
    routes back to that checkout only if the reader puts in the runner's
    lane. It now prints that lane, and following the line word for word
    publishes the log and lets the sweep run."""
    made = box.helper("lane-checkout", LANE, "--create")
    lc = box.checkout(LANE)
    assert made.returncode == 0 and made.stdout.strip() == str(lc), (made.stdout, made.stderr)
    rel = _a_log_nobody_tracks(lc)
    result = box.helper("retire-rows", NEIGHBOUR, LANES_LANE=LANE, LANES_SESSION=UUID)
    assert result.returncode == 2, (result.stdout, result.stderr)
    err = result.stderr
    assert "NOT TRACKED" in err and "Nothing was written" in err, err
    assert f"git -C {lc} add -- {rel} && git -C {lc} commit -m" in err, err
    assert f"the publish act (LANES_LANE={LANE} " in err, err
    box.git("-C", str(lc), "add", "--", rel)
    box.git("-C", str(lc), "commit", "-q", "-m", f"{NEIGHBOUR}(its log)", "--", rel)
    published = box.helper("commit", "its log", LANES_LANE=LANE)
    assert published.returncode == 0, published.stderr
    assert box.origin_file(rel).startswith(f"# lane {NEIGHBOUR}"), "the publish act sent it"
    again = box.helper("retire-rows", NEIGHBOUR, LANES_LANE=LANE, LANES_SESSION=UUID)
    assert again.returncode == 0, (again.stdout, again.stderr)
    assert f"RETIRED — lane {NEIGHBOUR}" in box.origin_file(rel)


# -------------------------------------------------------- the top level

@pytest.mark.parametrize("verb", sorted(VERBS))
def test_a_lanes_repo_inside_the_checkout_refuses_before_any_edit(box: Box, verb: str):
    """`LANES_REPO` naming a directory INSIDE the checkout, with `LANES_FILE`
    naming the register (slice 2a's writer w2a-c10, on slice 1b's
    `commit_publish`). Every pathspec the helper gives git is spelled from the
    top level, and git reads one relative to the directory it runs in: the
    write's `git add` failed (6) after the edit was made, and S3's own
    pending-path check asked about a register path that is not there. It
    refuses (2) before any edit, naming the top level and the register."""
    c = box.seam()
    inside = c / "handoffs"
    if verb == "commit":
        # `commit`'s hand-edit form; with nothing of its own it is the
        # publish act, which reaches the same check.
        box.hand_edit(c)
    before = box.snapshot(c)
    w_before = box.w_state()
    result = run_verb(box, verb, LANES_REPO=str(inside), LANES_FILE=str(c / REGISTER))
    err = result.stderr
    assert result.returncode == 2, (result.stdout, err)
    assert f"in {inside}:" in err, "the refusal names the directory it was given"
    assert f"LANES_REPO names handoffs/ inside the checkout {c}, not its top level" in err, err
    assert f"LANES_REPO={c} LANES_FILE={c / REGISTER}" in err, "the recovery names both"
    assert "Nothing was written." in err, err
    assert "git add failed" not in err, err
    assert box.snapshot(c) == before, "HEAD, the branch, the index, the tree and origin are as they were"
    assert box.w_state() == w_before, "W is untouched"
    assert not box.lock_of(c).exists(), "the lock is released"


def test_the_top_level_the_refusal_names_carries_the_hand_edit(box: Box):
    """The recovery the refusal above prints, followed word for word: the
    same `commit` through the top level carries the pending hand edit and
    publishes it, and the edit was never lost to the refusal."""
    c = box.seam()
    box.hand_edit(c)
    refused = box.helper("commit", "the guarded hand edit", LANES_LANE=LANE,
                         LANES_REPO=str(c / "handoffs"), LANES_FILE=str(c / REGISTER))
    assert refused.returncode == 2, (refused.stdout, refused.stderr)
    assert "LIVE · a hand edit" in (c / REGISTER).read_text(encoding="utf-8"), "the edit is still in place"
    line = re.search(r"name the checkout itself: (LANES_REPO=\S+ LANES_FILE=\S+)", refused.stderr)
    assert line, refused.stderr
    named = dict(word.split("=", 1) for word in line.group(1).split())
    again = box.helper("commit", "the guarded hand edit", LANES_LANE=LANE, **named)
    assert again.returncode == 0, (again.stdout, again.stderr)
    assert "LIVE · a hand edit" in box.origin_register(), "the hand edit is published"
    assert box.unpublished(c) == [], "nothing is left unpublished"
