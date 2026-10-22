# SPDX-License-Identifier: Apache-2.0
"""opensoft/openRepoTools#309 (found by the review of #291): A LOOKUP THAT COULD
NOT BE MADE IS NOT AN ABSENT RECORD, IN TWO WRITERS.

A lane's lifecycle snapshot and its `trees/` inventory are under its control
root, `<parent of its dir>/.lane-state/<lane>`. The shell's `[ -e ]`, `[ -r ]`
and `[ -L ]` are all false for a path under a directory this account may not
SEARCH, or under a link it cannot follow: stat fails there with EACCES exactly
as it fails with ENOENT for a name that is gone. #291 taught the READERS to tell
the two apart (`lookup_blocked`; `lane-state` and `lane-trees` exit 10, never
the 8 of "none"). Two WRITERS still read the false answer as the true one:

  * `rename-lane` moves a lane's control root with it once the rename's commit
    has landed (`lane_state_rename`). Its guard for an old root that is not
    there takes a root it could not look for for one that is not there, so the
    move is skipped without a word: the rename stands, the records stay under
    the old name, `lane-state` and `lane-trees` answer 8 on the new one and
    `lane-reconcile` says `no-state`, "the one answer a launcher goes past".
    Every other failure to move says so, and says that the rename has landed.
    The only way here is a folder that turns unsearchable AFTER the rename's
    up-front checks (a folder that is already unsearchable is refused, with
    nothing written) and before the move, that is during its push; so the
    case is made here by a `pre-push` hook of the register clone that does it,
    and `lane_state_rename` is also held alone, cut out of `lanes-edit.sh`, in
    every way the lookup can stop.
  * `set-lane-state`'s fence, and `set-lane-tree`'s where it names a
    `--generation` or an `--operation`, read the snapshot through a name they
    cannot see: state, generation and operation come out empty, the fence
    compares them with `none`, `0` and `none`, and answers 7, the one number
    that means *you lost the race*. No act did. A finalizer takes that 7 for
    "superseded" and stands down; the printed `state none` is a state nobody
    read. (`--expect none` passes the fence over the same blindness and fails
    at the write, saying nothing of why.)

What these tests hold, for each place the lookup can stop - the folder that
holds the root at mode 000 and at mode 400 (readable, not searchable), the root
itself readable and not searchable, a directory above the folder, a link to the
folder whose target is gone, and a link into a directory that cannot be
searched:

  * `rename-lane`, and `lane_state_rename` alone, over an old root nobody could
    look for: nothing is moved, nothing is created at the new name, the records
    are as they were, and the note says that they COULD NOT be moved, that the
    rename has landed, and that whether the root is there could not be read -
    and never says that they moved. Its advice is to move `lane-state.yaml`
    and `trees/` by hand and leave any `restart-intent.yaml` where it is,
    because completed restart history stays at the old root (#309's review,
    563). The exit stays 0: the rename has landed, and `lane-rename` goes on
    to name the window and the session on a 0.
  * `set-lane-state` and `set-lane-tree` over a snapshot nobody could look for
    write nothing, answer 10, print no state, and say, in the words
    `lane-state` uses for the same fact, that the snapshot could not be looked
    for. 10 is the readers' number for that fact (lane openRepoTools-3's ruling
    R1 on the design), and never the 7 of a lost race or the 1 `lane-handoff`
    reads as "no control root". A `set-lane-state` that names no fence does not
    say that a fence went unchecked (567).
  * `lane-handoff`, which the 10 reaches (562): `lifecycle_begin` takes it to
    its generic arm and records no transition, and `lifecycle_finish` leaves
    the lane `SWAPPING`, which its summary prints, and never stands down as
    superseded. Both are cut out of `lane-handoff` and run against the real
    helper, with the folder blocked for the one `set-lane-state` they make.
  * the controls: a root or a snapshot that is truly absent behaves as it did -
    `rename-lane` and the function are silent, a stale `--expect` or
    `--generation` over no snapshot is a true 7, `--expect none` passes - a
    searchable snapshot still fences with 7, a snapshot that is there and
    cannot be read keeps its own refusal (1), and a folder that is unsearchable
    BEFORE `rename-lane` starts is still refused with nothing written.

Every mode set here is restored before the case ends. Root searches and reads a
mode-000 directory, so a case that sets a mode proves nothing as root and skips
there; the link whose target is gone sets none, and runs as root too.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import WINDOWS_SKIP
from test_lanes_index import LANES_EDIT, UUID_A1B, UUID_C1, Estate

pytestmark = [
    WINDOWS_SKIP,
    pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                       reason="the lane tooling is bash over git"),
]

#: ONLY A CASE THAT SETS A MODE SKIPS AS ROOT (as #291's do). Root searches and
#: reads a mode-000 directory, so a lookup a mode blocks is not blocked there.
NOT_AS_ROOT = pytest.mark.skipif(
    getattr(os, "geteuid", lambda: -1)() == 0,
    reason="root searches and reads a mode-000 directory: nothing to prove here")

LANE = "repoA-1"          # `Estate`'s seed gives it a register row and an object log
NEW = "repoA-3"
OP = "op-test-309"
HEAD = "7" * 40
TREE = f"/nowhere/{LANE}/w"
OBSERVED = ("--branch", "feat/309", "--head", HEAD, "--upstream", "none",
            "--dirty", "0", "--unpushed", "0")

#: Where the lookup can stop, as `lookup_blocked` walks it. `control-root` is for
#: the writers that read INTO the root; the rename's old root is the root itself,
#: and a root that is readable and not searchable is still found by stat.
FENCE_KINDS = [
    pytest.param("state-dir", marks=NOT_AS_ROOT, id="folder-mode-000"),
    pytest.param("state-dir-no-search", marks=NOT_AS_ROOT, id="folder-mode-400"),
    pytest.param("control-root", marks=NOT_AS_ROOT, id="root-mode-600"),
    pytest.param("above", marks=NOT_AS_ROOT, id="above-the-folder"),
    pytest.param("dangling-link", id="link-whose-target-is-gone"),
    pytest.param("link-into-locked-dir", marks=NOT_AS_ROOT, id="link-into-a-locked-dir"),
]
RENAME_KINDS = [kind for kind in FENCE_KINDS if kind.values[0] != "control-root"]


@contextlib.contextmanager
def _modes(changes):
    """Each path at its mode for the block, and every one put back to the mode
    it had, in reverse order, whatever the block did."""
    done = []
    try:
        for path, mode in changes:
            restore = stat.S_IMODE(path.stat().st_mode)
            path.chmod(mode)
            done.append((path, restore))
        yield
    finally:
        for path, restore in reversed(done):
            path.chmod(restore)


class Layout:
    """The folder a lane's control roots are kept in - what
    `LANES_LANE_STATE_ROOT` names, the `.lane-state` of the estate's own
    layout - made so that one way of not being able to look into it is ready:
    `block()` is that, for the block's length, and `blocked_by_the_push()` is
    the same thing done by a `pre-push` hook of the register clone.

    `state` is the folder (a link, for the two link kinds, so every path under
    it is read through the link), `why` is what `lookup_blocked` says about
    where it stops, in the words every reader prints."""

    def __init__(self, base: Path, kind: str, lane: str = LANE):
        self.kind, self.lane = kind, lane
        base.mkdir(parents=True, exist_ok=True)
        if kind in ("state-dir", "state-dir-no-search", "control-root"):
            self.state = base / "state"
            self.state.mkdir()
            self.where = self.state / lane if kind == "control-root" else self.state
            mode = {"state-dir": 0o000, "state-dir-no-search": 0o400, "control-root": 0o600}[kind]
            self._changes = [(self.where, mode)]
        elif kind == "above":
            outer = base / "vault"
            self.state = outer / "state"
            self.state.mkdir(parents=True)
            self.where = outer
            self._changes = [(outer, 0o000)]
        elif kind == "link-into-locked-dir":
            locked = base / "locked"
            (locked / "state").mkdir(parents=True)
            self.state = base / "state"
            self.state.symlink_to(locked / "state")
            self.where = self.state
            self._changes = [(locked, 0o000)]
        elif kind == "dangling-link":
            self.real, self.aside = base / "real", base / "real-aside"
            self.real.mkdir()
            self.state = base / "state"
            self.state.symlink_to(self.real)
            self.where = self.state
            self._changes = []
        else:
            raise AssertionError(kind)
        self.why = (f"{self.where} is a symbolic link that cannot be followed"
                    if kind in ("link-into-locked-dir", "dangling-link")
                    else f"the directory {self.where} cannot be searched")

    @contextlib.contextmanager
    def block(self):
        """The folder cannot be looked into for the length of the block."""
        if self.kind == "dangling-link":
            self.real.rename(self.aside)
            try:
                assert self.state.is_symlink() and not self.state.exists(), \
                    "the link does not dangle: nothing to prove"
                yield
            finally:
                self.aside.rename(self.real)
        else:
            with _modes(self._changes):
                yield

    @contextlib.contextmanager
    def blocked_by_the_push(self, estate: Estate):
        """The same block, made by the register clone's `pre-push` hook: it
        turns up after every check `rename-lane` makes before it writes, and
        is there when the rename's commit has landed and the move is made.
        Put back when the block ends; the hook then does nothing."""
        if self.kind == "dangling-link":
            lines = f"[ -e '{self.real}' ] && mv -- '{self.real}' '{self.aside}'\n"
        else:
            lines = "".join(f"chmod {mode:04o} '{path}'\n" for path, mode in self._changes)
        restore = [(path, stat.S_IMODE(path.stat().st_mode)) for path, _ in self._changes]
        hook = estate.wip / ".git" / "hooks" / "pre-push"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(f"#!/bin/sh\n{lines}exit 0\n", encoding="utf-8")
        hook.chmod(0o755)
        try:
            yield
        finally:
            hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            if self.kind == "dangling-link":
                if self.aside.exists():
                    self.aside.rename(self.real)
            for path, mode in reversed(restore):
                path.chmod(mode)


def _contents(root: Path) -> dict:
    """Every regular file under `root`, by its path below it, with its bytes."""
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file()}


def _write_the_lane(estate: Estate, lay: Layout) -> dict:
    """The lane RUNNING at generation 1 under `OP`, with one tree recorded,
    written by the real writers while the folder can still be searched.
    Returns the environment that names the folder."""
    env = {"LANES_LANE_STATE_ROOT": str(lay.state)}
    put = estate.edit("set-lane-state", LANE, "RUNNING", "--expect", "none",
                      "--operation", OP, env=env)
    assert put.returncode == 0, (put.stdout, put.stderr)
    rec = estate.edit("set-lane-tree", LANE, TREE, *OBSERVED, env=env)
    assert rec.returncode == 0, (rec.stdout, rec.stderr)
    return env


@pytest.fixture
def estate(tmp_path):
    return Estate(tmp_path / "e")


# ============================================================ the two fences

def _fence_problems(label: str, res: subprocess.CompletedProcess, lay: Layout, root: Path) -> list:
    """Everything wrong with `res` as the answer of a fenced writer that could
    not look for the snapshot at `root`/lane-state.yaml."""
    said = (f"whether lane {LANE} has a lifecycle snapshot could not be read: "
            f"{root}/lane-state.yaml could not be looked for, because {lay.why}.")
    problems = []
    if res.returncode in (0, 7, 8):
        meaning = {0: "done", 7: "you lost the race", 8: "there is no such record"}[res.returncode]
        problems.append(f"{label}: exit {res.returncode}, which says '{meaning}', "
                        f"for a snapshot nobody could look for")
    elif res.returncode != 10:
        problems.append(f"{label}: exit {res.returncode}, where a snapshot nobody could look "
                        f"for is 10, the number `lane-state` answers for the same fact (R1)")
    if res.stdout:
        problems.append(f"{label}: printed {res.stdout!r}, a state nobody read")
    if said not in res.stderr:
        problems.append(f"{label}: stderr does not say that the snapshot could not be "
                        f"looked for ({said!r}): {res.stderr!r}")
    for fact in ("state is none and", "generation is 0 and", "operation is none and"):
        if fact in res.stderr:
            problems.append(f"{label}: says the lane's {fact!r} what it never read: "
                            f"{res.stderr!r}")
    return problems


@pytest.mark.parametrize("kind", FENCE_KINDS)
def test_set_lane_state_over_a_snapshot_nobody_could_look_for_is_not_a_lost_race(
        estate, tmp_path, kind):
    """THE FENCE'S 7 IS A RACE LOST, AND NO ACT GOT THERE FIRST (#309 item 2).
    The snapshot is RUNNING, generation 1, under `OP`. With the lookup blocked,
    every `set-lane-state` that reads it - a state, a generation or an operation
    fence, `--expect none`, and the write that names none, whose generation it
    follows from - writes nothing, answers a code that is neither done, nor a
    lost race, nor "none", prints no state, and says the snapshot could not be
    looked for. The snapshot and the inventory are byte for byte as they were
    when the folder can be searched again."""
    lay = Layout(tmp_path / "ls", kind)
    env = _write_the_lane(estate, lay)
    root = lay.state / LANE
    before = _contents(root)
    assert "generation: 1" in (root / "lane-state.yaml").read_text(encoding="utf-8")
    calls = {
        "--expect RUNNING": ("--expect", "RUNNING"),
        "--expect-generation 1": ("--expect-generation", "1"),
        "--expect-operation": ("--expect-operation", OP),
        "--expect none": ("--expect", "none"),
        "no fence at all": (),
    }
    problems = []
    with lay.block():
        assert not os.path.exists(root / "lane-state.yaml"), "the block did not take: nothing to prove"
        for label, flags in calls.items():
            res = estate.edit("set-lane-state", LANE, "SWAPPING", *flags, env=env)
            problems += _fence_problems(label, res, lay, root)
    assert not problems, "\n".join(problems)
    assert _contents(root) == before  # nothing written, and no half-written file left


@pytest.mark.parametrize("kind", FENCE_KINDS)
def test_set_lane_tree_over_a_snapshot_nobody_could_look_for_is_not_a_lost_race(
        estate, tmp_path, kind):
    """`set-lane-tree` READS THE SNAPSHOT THE SAME WAY for its `--generation` and
    `--operation` fence (#309 item 2), and it is the writer a handoff files
    every tree through. With the lookup blocked, a call naming either flag, or
    both, records nothing, answers a code that is neither done, nor a lost race,
    nor "none", prints nothing, and says the snapshot could not be looked for -
    not that "the lane moved while this observation was being made". (One that
    names neither never reads the snapshot and still fails at the write, as it
    did, which #291 pins.)"""
    lay = Layout(tmp_path / "ls", kind)
    env = _write_the_lane(estate, lay)
    root = lay.state / LANE
    before = _contents(root)
    calls = {
        "--generation 1 --operation": ("--generation", "1", "--operation", OP),
        "--generation 1": ("--generation", "1"),
        "--operation": ("--operation", OP),
    }
    problems = []
    with lay.block():
        assert not os.path.exists(root / "lane-state.yaml"), "the block did not take: nothing to prove"
        for label, flags in calls.items():
            res = estate.edit("set-lane-tree", LANE, TREE, *OBSERVED, *flags, env=env)
            problems += _fence_problems(label, res, lay, root)
            if "NOT recorded" not in res.stderr and f"was NOT recorded for lane {LANE}" not in res.stderr:
                problems.append(f"{label}: does not say that the tree was not recorded: {res.stderr!r}")
    assert not problems, "\n".join(problems)
    assert _contents(root) == before  # not one record written, and no half-written file left


def test_set_lane_state_says_what_it_could_not_do_with_a_fence_and_without_one(estate, tmp_path):
    """WHAT THE REFUSAL SAYS IT COULD NOT DO (#309's review, 567). A call that
    names a fence could not check it. A call that names none had no fence to
    check: what it could not take from the snapshot is the generation it would
    advance from, so it says that and never that a fence went unchecked. The
    link whose target is gone sets no mode, so this runs as root too."""
    lay = Layout(tmp_path / "ls", "dangling-link")
    env = _write_the_lane(estate, lay)
    with lay.block():
        fenced = estate.edit("set-lane-state", LANE, "SWAPPING", "--expect", "RUNNING", env=env)
        bare = estate.edit("set-lane-state", LANE, "SWAPPING", env=env)
    assert (fenced.returncode, bare.returncode) == (10, 10), (fenced.stderr, bare.stderr)
    assert "So the fence this call names could not be checked against it" in fenced.stderr, \
        fenced.stderr
    assert "So the generation this transition would advance from could not be taken from it" \
        in bare.stderr, bare.stderr
    assert "could not be checked" not in bare.stderr, bare.stderr


@pytest.mark.parametrize("shape", ["no-root", "root-without-snapshot"])
def test_a_snapshot_that_is_truly_absent_is_still_none_to_both_fences(estate, tmp_path, shape):
    """THE CONTROL FOR A SNAPSHOT THAT IS NOT THERE: looked for under a folder
    that CAN be searched, it is `none`, and the fences mean what they meant. A
    stale `--expect` over it is a true 7 (the lane is in no state, and the
    caller was told it was RUNNING), printing `state none`; so is a
    `--generation` no snapshot can match; `--expect none` passes and writes
    generation 1. Nothing of #309's applies where the lookup was made."""
    state = tmp_path / "ls" / "state"
    state.mkdir(parents=True)
    env = {"LANES_LANE_STATE_ROOT": str(state)}
    if shape == "root-without-snapshot":
        rec = estate.edit("set-lane-tree", LANE, TREE, *OBSERVED, env=env)
        assert rec.returncode == 0, (rec.stdout, rec.stderr)
        assert (state / LANE / "trees").is_dir() and not (state / LANE / "lane-state.yaml").exists()
    stale = estate.edit("set-lane-state", LANE, "SWAPPING", "--expect", "RUNNING", env=env)
    assert stale.returncode == 7, (stale.returncode, stale.stdout, stale.stderr)
    assert stale.stdout == "state\tnone\ngeneration\t0\noperation\tnone\n", stale.stdout
    assert "state is none and --expect named RUNNING" in stale.stderr, stale.stderr
    tree = estate.edit("set-lane-tree", LANE, TREE, *OBSERVED, "--generation", "1",
                       "--operation", OP, env=env)
    assert tree.returncode == 7, (tree.returncode, tree.stdout, tree.stderr)
    assert "generation is 0 and --generation named 1" in tree.stderr, tree.stderr
    assert not (state / LANE / "lane-state.yaml").exists()  # a refusal wrote nothing
    first = estate.edit("set-lane-state", LANE, "RUNNING", "--expect", "none",
                        "--operation", OP, env=env)
    assert first.returncode == 0, (first.returncode, first.stdout, first.stderr)
    assert first.stdout == f"state\tRUNNING\ngeneration\t1\noperation\t{OP}\n", first.stdout
    assert (state / LANE / "lane-state.yaml").is_file()


def test_a_snapshot_that_can_be_searched_still_fences_with_7_and_a_matching_fence_passes(
        estate, tmp_path):
    """THE CONTROL FOR A SNAPSHOT THAT IS THERE: stale fences are the true 7s
    they were, naming what the snapshot says, and a matching fence moves the
    lane. A fix that took every refusal for a lookup that could not be made
    would turn these into something else."""
    lay = Layout(tmp_path / "ls", "state-dir")
    env = _write_the_lane(estate, lay)
    root = lay.state / LANE
    current = f"state\tRUNNING\ngeneration\t1\noperation\t{OP}\n"
    for flags, fact in ((("--expect", "SWAPPED"), "state is RUNNING and --expect named SWAPPED"),
                        (("--expect-generation", "9"), "generation is 1 and --expect-generation named 9"),
                        (("--expect-operation", "op-other"),
                         f"operation is {OP} and --expect-operation named op-other")):
        res = estate.edit("set-lane-state", LANE, "SWAPPING", *flags, env=env)
        assert res.returncode == 7, (flags, res.returncode, res.stdout, res.stderr)
        assert res.stdout == current, (flags, res.stdout)
        assert fact in res.stderr, (flags, res.stderr)
    tree = estate.edit("set-lane-tree", LANE, TREE, *OBSERVED, "--generation", "9",
                       "--operation", OP, env=env)
    assert tree.returncode == 7, (tree.returncode, tree.stdout, tree.stderr)
    assert "generation is 1 and --generation named 9" in tree.stderr, tree.stderr
    assert "generation: 1" in (root / "lane-state.yaml").read_text(encoding="utf-8")
    moved = estate.edit("set-lane-state", LANE, "SWAPPING", "--expect", "RUNNING",
                        "--expect-generation", "1", "--expect-operation", OP, env=env)
    assert moved.returncode == 0, (moved.returncode, moved.stdout, moved.stderr)
    assert moved.stdout.startswith("state\tSWAPPING\ngeneration\t2\n"), moved.stdout


@NOT_AS_ROOT
def test_a_snapshot_that_is_there_and_cannot_be_read_keeps_its_own_refusal(estate, tmp_path):
    """THE BOUNDARY OF THE NEW REFUSAL: it is for a snapshot nobody could look
    for. One that IS there - stat finds it - and cannot be opened is the
    refusal it always was, 1, "it is there and could not be read": a fix that
    asked `lookup_blocked` of every name that is not readable would say the
    wrong thing here, in the words of the wrong case."""
    lay = Layout(tmp_path / "ls", "state-dir")
    env = _write_the_lane(estate, lay)
    snapshot = lay.state / LANE / "lane-state.yaml"
    with _modes([(snapshot, 0o000)]):
        state = estate.edit("set-lane-state", LANE, "SWAPPING", "--expect", "RUNNING", env=env)
        tree = estate.edit("set-lane-tree", LANE, TREE, *OBSERVED, "--generation", "1",
                           "--operation", OP, env=env)
        for res in (state, tree):
            assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
            assert "it is there and could not be read" in res.stderr, res.stderr
            assert "could not be looked for" not in res.stderr, res.stderr


# ================================================ lane_state_rename, alone

#: THE FUNCTION IS CUT OUT OF `lanes-edit.sh` AND RUN ON ITS OWN, with the three
#: it calls that are not the shell's: its note, `lc` and `lookup_blocked`.
#: Whatever a fix makes it call besides those has to be named here.
RENAME_FUNCTIONS = ("note", "lc", "lookup_blocked", "lane_state_rename")


def _function_source(name: str, source: Path = LANES_EDIT) -> str:
    lines = source.read_text(encoding="utf-8").splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(f"{name}() {{")]
    assert starts, (f"{source.name} has no `{name}`: this file stacks on #291's "
                    f"`lookup_blocked` and cuts what it runs out of the source")
    start = starts[0]
    first = lines[start]
    if first.count("{") == first.count("}"):   # a one-line function
        return first + "\n"
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "}")
    return "\n".join(lines[start:end + 1]) + "\n"


def _rename_function(old: Path, new: str, cwd: Path):
    """`lane_state_rename <old> <new>`, run as `lanes-edit.sh` runs it (`set -u`):
    `(exit status, the nudge it left for the indexer, stdout, stderr)`."""
    script = ("set -u\n" + "".join(_function_source(name) for name in RENAME_FUNCTIONS) +
              'LANES_INDEX_NUDGE_INV=0\nlane_state_rename "$1" "$2"\nrc=$?\n'
              "printf 'RC=%s NUDGE=%s\\n' \"$rc\" \"$LANES_INDEX_NUDGE_INV\"\n")
    proc = subprocess.run(["bash", "-c", script, "lane_state_rename", str(old), new],
                          capture_output=True, text=True, cwd=str(cwd), check=False, timeout=60,
                          stdin=subprocess.DEVNULL, env={"PATH": os.environ["PATH"]})
    assert proc.stdout.startswith("RC=") and proc.stdout.count("\n") == 1, (proc.stdout, proc.stderr)
    fields = dict(part.split("=") for part in proc.stdout.split())
    return fields["RC"], fields["NUDGE"], proc.stdout, proc.stderr


def _fill(root: Path) -> None:
    """What a control root holds, in two files: the function moves a directory
    and reads nothing in it."""
    (root / "trees").mkdir(parents=True)
    (root / "lane-state.yaml").write_text("schema: 1\nlane: x\nstate: RUNNING\n", encoding="utf-8")
    (root / "trees" / "c0-x.yaml").write_text("schema: 1\ntree: c0-x\n", encoding="utf-8")


def _could_not_move(old: Path, lay: Layout) -> tuple:
    """The four things a note for a root nobody could look for says, none of
    which a move or an absent root says. The last is its advice (563): a move
    takes the two parts, and completed restart history stays where it is."""
    return (f"could NOT be moved from {old} to {lay.state / NEW}",
            "the rename itself has landed",
            f"whether {old} is there could not be read, because {lay.why}",
            f"move its lane-state.yaml and trees/ into {lay.state / NEW} by hand and "
            f"leave any restart-intent.yaml where it is")


@pytest.mark.parametrize("kind", RENAME_KINDS)
def test_lane_state_rename_over_an_old_root_nobody_could_look_for_moves_nothing_and_says_so(
        tmp_path, kind):
    """`[ -e old ] || [ -L old ] || return 0` IS THE SAME BLINDNESS (#309 item
    1): under a folder nobody can search both are false, and the function
    returned 0 with nothing moved and nothing said, where each of its other
    failures says that the records could NOT be moved and that the rename has
    landed. A root nobody could look for is NOT a root that is not there: it
    moves nothing, makes nothing at the new name, leaves the indexer no nudge
    (nothing changed), and says what the others say, and why."""
    lay = Layout(tmp_path / "ls", kind, LANE)
    old = lay.state / LANE
    _fill(old)
    before = _contents(old)
    with lay.block():
        assert not os.path.exists(old), "the block did not take: nothing to prove"
        rc, nudge, _, err = _rename_function(old, NEW, tmp_path)
    assert rc == "0", (rc, err)             # the rename has landed: a 0, as with every failure to move
    for words in _could_not_move(old, lay):
        assert words in err, (words, err)
    assert "moved with the rename" not in err, err
    assert nudge == "0", nudge               # nothing moved, so there is nothing to sync
    assert not os.path.lexists(lay.state / NEW)
    assert _contents(old) == before          # every record where it was, byte for byte


@pytest.mark.parametrize("shape", ["no-root", "no-folder", "under-a-file"])
def test_lane_state_rename_over_an_old_root_that_is_established_absent_stays_silent(
        tmp_path, shape):
    """THE CONTROL FOR A ROOT THAT IS NOT THERE: where the lookup WAS made - the
    folder is searchable and holds no such root, the folder is not there either
    and its parent is searchable, or a name on the way is a file, which has
    nothing below it - the absence is established and the function is silent as
    it was: nothing said, nothing moved, nothing made."""
    base = tmp_path / "ls"
    base.mkdir()
    state = base / "state"
    if shape == "no-root":
        state.mkdir()
    elif shape == "under-a-file":
        state.write_text("not a folder\n", encoding="utf-8")
    rc, nudge, out, err = _rename_function(state / LANE, NEW, tmp_path)
    assert (rc, nudge, err) == ("0", "0", ""), (rc, nudge, err)
    assert not os.path.lexists(state / NEW)
    assert sorted(p.name for p in base.iterdir()) == (["state"] if shape != "no-folder" else [])


def test_lane_state_rename_over_an_old_root_that_is_there_moves_it_and_says_so(tmp_path):
    """THE CONTROL FOR A ROOT THAT IS THERE: it moves whole to the new name, the
    old one is gone, the indexer is nudged, and the note says it moved."""
    lay = Layout(tmp_path / "ls", "state-dir", LANE)
    old = lay.state / LANE
    _fill(old)
    before = _contents(old)
    rc, nudge, _, err = _rename_function(old, NEW, tmp_path)
    assert (rc, nudge) == ("0", "1"), (rc, nudge, err)
    assert f"the lane lifecycle snapshot and inventory moved with the rename: {old} → " \
        f"{lay.state / NEW}" in err, err
    assert "could NOT be moved" not in err, err
    assert not os.path.lexists(old)
    assert _contents(lay.state / NEW) == before


# ====================================================== rename-lane, whole

def _estate_with_the_lane(tmp_path: Path, kind: str):
    estate = Estate(tmp_path / "e")
    lay = Layout(tmp_path / "ls", kind, LANE)
    env = _write_the_lane(estate, lay)
    env["LANES_SESSION"] = UUID_A1B           # the row's own session names the act
    return estate, lay, env


@pytest.mark.parametrize("kind", [kind for kind in RENAME_KINDS
                                  if kind.values[0] in ("state-dir", "dangling-link")])
def test_rename_lane_that_cannot_look_for_the_old_root_when_it_moves_it_says_so(tmp_path, kind):
    """THE REACHABLE CASE (#309 item 1): the folder turns unsearchable during the
    rename's push - here by the register clone's `pre-push` hook, the one place
    between the up-front checks and the move that a folder can change under it.
    The rename has landed and stands: the lane is `NEW` to every reader and its
    old name resolves. The lifecycle records stay under the old name, and
    `rename-lane` has to say that they could NOT be moved, as it does for every
    other failure to move, and not leave a lane that `lane-state` answers 8 for,
    `lane-reconcile` calls `no-state` and nobody was told about. It exits 0, as
    for those, because the rename it ended in has landed."""
    estate, lay, env = _estate_with_the_lane(tmp_path, kind)
    old = lay.state / LANE
    before = _contents(old)
    with lay.blocked_by_the_push(estate):
        res = estate.edit("rename-lane", LANE, NEW, "--no-github", env=env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    landed = estate.edit("canon-lane", LANE, env=env)       # the rename stands
    assert landed.stdout.strip() == NEW, (landed.stdout, landed.stderr)
    assert f"RENAMED lane {LANE} → {NEW}" in res.stderr, res.stderr
    assert _contents(old) == before          # the records were not touched
    assert not os.path.lexists(lay.state / NEW)
    for words in _could_not_move(old, lay):
        assert words in res.stderr, (words, res.stderr)
    assert "moved with the rename" not in res.stderr, res.stderr


def test_rename_lane_still_moves_the_lifecycle_records_it_can_look_for(tmp_path):
    """THE CONTROL: with nothing blocked the records go with the rename and the
    note says so (`test_lane_helpers.sh` holds it too, through a real lane)."""
    estate, lay, env = _estate_with_the_lane(tmp_path, "state-dir")
    old = lay.state / LANE
    before = _contents(old)
    res = estate.edit("rename-lane", LANE, NEW, "--no-github", env=env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert f"snapshot and inventory moved with the rename: {old} → {lay.state / NEW}" in res.stderr
    assert "could NOT be moved" not in res.stderr, res.stderr
    assert not os.path.lexists(old)
    assert _contents(lay.state / NEW) == before


def test_rename_lane_of_a_lane_with_no_control_root_says_nothing_of_one(tmp_path):
    """THE CONTROL FOR A ROOT THAT IS TRULY ABSENT: a lane with a row and no
    records at all - the folder is there, searchable, and holds nothing of its
    - renames as it did, without a word about a snapshot or an inventory. This
    is the ordinary pre-cutover lane (Amendment 7(i))."""
    estate, lay, env = _estate_with_the_lane(tmp_path, "state-dir")
    env["LANES_SESSION"] = UUID_C1            # repoC-1: a row, no log, no root
    assert not (lay.state / "repoC-1").exists()
    res = estate.edit("rename-lane", "repoC-1", "repoC-2", "--no-github", env=env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    for word in ("snapshot", "inventory", "lifecycle"):
        assert word not in res.stderr, (word, res.stderr)
    assert not (lay.state / "repoC-2").exists()


@NOT_AS_ROOT
def test_rename_lane_is_still_refused_with_nothing_written_when_the_folder_is_already_unsearchable(
        tmp_path):
    """THE BOUNDARY OF THE DEFECT: a folder that cannot be searched when the
    rename STARTS is refused by its own up-front check (exit 1, nothing
    written, the register unmoved); #309 is only the folder that turns up
    during the push. A fix must leave this exactly as it is."""
    estate, lay, env = _estate_with_the_lane(tmp_path, "state-dir")
    old = lay.state / LANE
    before, tip = _contents(old), estate.tip()
    with lay.block():
        res = estate.edit("rename-lane", LANE, NEW, "--no-github", env=env)
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
    assert "Nothing was written." in res.stderr, res.stderr
    assert estate.tip() == tip
    assert estate.edit("canon-lane", LANE, env=env).stdout.strip() == LANE
    assert _contents(old) == before


# ====================================== lane-handoff's two lifecycle arms

#: `lane-handoff` beside the helper under test, and what its two lifecycle
#: functions call that is not the shell's: its own `note` and `step`.
LANE_HANDOFF = LANES_EDIT.parent / "lane-handoff"
HANDOFF_FUNCTIONS = ("note", "step", "lifecycle_begin", "lifecycle_finish")

#: A block made by a mode, and the one made by a link whose target is gone,
#: which sets no mode and runs as root too: the two the rename-lane cases use.
PIN_KINDS = [kind for kind in FENCE_KINDS if kind.values[0] in ("state-dir", "dangling-link")]


@contextlib.contextmanager
def _helper_blocked_for(lay: Layout, tmp_path: Path, state: str):
    """A `$LANES_EDIT` that is the real helper, except that its one
    `set-lane-state <lane> <state>` runs with the folder blocked: the folder
    turns unsearchable after `lane-handoff` has read the lane and before it
    writes, the window #309 is about. It is put back when that call returns,
    and again when the block ends, whatever happened."""
    if lay.kind == "dangling-link":
        block = f"  mv -- '{lay.real}' '{lay.aside}'\n"
        unblock = f"  mv -- '{lay.aside}' '{lay.real}'\n"
    else:
        block = "".join(f"  chmod {mode:04o} '{path}'\n" for path, mode in lay._changes)
        unblock = "".join(f"  chmod {stat.S_IMODE(path.stat().st_mode):04o} '{path}'\n"
                          for path, _ in reversed(lay._changes))
    restore = [(path, stat.S_IMODE(path.stat().st_mode)) for path, _ in lay._changes]
    helper = tmp_path / "lanes-edit-blocking-one-write"
    helper.write_text(
        "#!/bin/sh\n"
        f'if [ "${{1-}}" = set-lane-state ] && [ "${{3-}}" = {state} ]; then\n'
        f"{block}"
        f"  bash '{LANES_EDIT}' \"$@\"; rc=$?\n"
        f"{unblock}"
        '  exit "$rc"\n'
        "fi\n"
        f"exec bash '{LANES_EDIT}' \"$@\"\n", encoding="utf-8")
    helper.chmod(0o755)
    try:
        yield helper
    finally:
        if lay.kind == "dangling-link" and lay.aside.exists():
            lay.aside.rename(lay.real)
        for path, mode in reversed(restore):
            path.chmod(mode)


def _handoff_lifecycle(estate: Estate, env: dict, calls: str) -> subprocess.CompletedProcess:
    """`lane-handoff`'s lifecycle functions, cut out of it and run as it runs
    them (`set -uo pipefail`) for lane `LANE`; `calls` runs after them."""
    script = ("set -uo pipefail\nprog=lane-handoff\n" +
              "".join(_function_source(name, LANE_HANDOFF) for name in HANDOFF_FUNCTIONS) +
              f"lane={LANE}; uuid={UUID_A1B}; agent=claude; profile_name=test-309; "
              "handoff_kind=swap\n" + calls)
    return estate.run("bash", "-c", script, "lane-handoff", env=env)


@pytest.mark.parametrize("kind", PIN_KINDS)
def test_lane_handoffs_begin_takes_the_10_to_its_generic_arm_and_records_no_transition(
        estate, tmp_path, kind):
    """`lifecycle_begin` READ THE LANE AND THEN COULD NOT LOOK FOR IT (#309's
    review, 562). The folder turns unsearchable between its `lane-state` and
    its `set-lane-state … SWAPPING --expect <what it read>`. The 7 that call
    used to answer sent it to "Another process is acting on lane", for a race
    nobody ran. The 10 it answers now takes the generic arm, which says the
    lane could not be taken to SWAPPING and names the code. No transition is
    recorded (`lc_on` stays empty), the swap goes on, and the snapshot is as
    it was."""
    lay = Layout(tmp_path / "ls", kind)
    env = _write_the_lane(estate, lay)
    snapshot = lay.state / LANE / "lane-state.yaml"
    before = snapshot.read_bytes()
    with _helper_blocked_for(lay, tmp_path, "SWAPPING") as helper:
        env["LANES_EDIT"] = str(helper)
        res = _handoff_lifecycle(estate, env, 'lifecycle_begin\n'
                                 'printf "on=%s state=%s\\n" "$lc_on" "$lc_state"\n')
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert res.stdout == "on= state=\n", (res.stdout, res.stderr)
    assert ("lane-handoff: the lane lifecycle could not be taken to SWAPPING "
            "(`set-lane-state` exited 10)") in res.stderr, res.stderr
    for wrong in ("Another process is acting", "has no lifecycle control root", "-> SWAPPING"):
        assert wrong not in res.stderr, (wrong, res.stderr)
    assert snapshot.read_bytes() == before


@pytest.mark.parametrize("kind", PIN_KINDS)
def test_lane_handoffs_finish_leaves_the_lane_swapping_on_the_10_and_is_never_superseded(
        estate, tmp_path, kind):
    """`lifecycle_finish` COULD NOT LOOK FOR THE LANE IT HAD TAKEN (#309's
    review, 562). `lifecycle_begin` took the lane RUNNING -> SWAPPING, and the
    folder turns unsearchable before the `set-lane-state … SWAPPED` fenced on
    that operation. The 7 it used to answer made this handoff `superseded`,
    "NOT the act that finishes" a lane nobody else had touched. The 10 it
    answers now leaves `lc_state` SWAPPING, which the handoff's summary prints
    as `lifecycle: SWAPPING`, and the note names the code: a later session
    reads an interrupted swap, which is what this act left. The snapshot keeps
    the begin's SWAPPING, generation and operation."""
    lay = Layout(tmp_path / "ls", kind)
    env = _write_the_lane(estate, lay)
    snapshot = lay.state / LANE / "lane-state.yaml"
    with _helper_blocked_for(lay, tmp_path, "SWAPPED") as helper:
        env["LANES_EDIT"] = str(helper)
        res = _handoff_lifecycle(estate, env, 'lifecycle_begin\nlifecycle_finish ""\n'
                                 'printf "on=%s state=%s gen=%s op=%s\\n" '
                                 '"$lc_on" "$lc_state" "$lc_gen" "$lc_op"\n')
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    said = dict(part.split("=", 1) for part in res.stdout.split())
    assert (said["on"], said["state"], said["gen"]) == ("1", "SWAPPING", "2"), (res.stdout, res.stderr)
    assert "lifecycle: RUNNING -> SWAPPING (generation 2, operation " in res.stderr, res.stderr
    assert ("lane-handoff: the lane could not be recorded SWAPPED (`set-lane-state` exited 10), "
            "so it stays SWAPPING") in res.stderr, res.stderr
    for wrong in ("NOT the act that finishes", "SWAPPING -> SWAPPED"):
        assert wrong not in res.stderr, (wrong, res.stderr)
    text = snapshot.read_text(encoding="utf-8")
    for line in ("state: SWAPPING", "generation: 2", f"operation: {said['op']}"):
        assert line in text.splitlines(), (line, text)
