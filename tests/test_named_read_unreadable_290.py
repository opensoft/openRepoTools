# SPDX-License-Identifier: Apache-2.0
"""A READ THAT COULD NOT BE MADE IS NEVER "NONE" (opensoft/openRepoTools#290).

#289 made the whole-listing read (`worktrees --all`, the one the inventory
index syncs from) refuse a listing that is not whole. These are the reads
beside it that still answered a failed read as an answer:

  * a NAMED read (`worktrees <lane>`, `lanes --worktrees <lane>`) whose one
    read of the lane's log failed said "none" (exit 8) - the log gives the
    lane's `dir`, its trees are under the root that `dir` places, and the root
    fell to `$PROJECTS_ROOT/.lane-state` (#289's review r1, SHOULD-3);
  * a named read with the register unreadable resolved the name as typed, so
    a name typed in another case found no root and said "none" too, and a
    tree's writer read `0` where the register's ids were never read;
  * the `lanes` listing said nothing where the list of the logs could not be
    made, and an empty listing over reads that all failed said "no lane";
  * with no `origin`, one log file that would not open left no warning - and
    `mawk`, which stops at the first file it cannot open, dropped every log
    after it as well;
  * `lanes-index` read a failed read of a lane's log in `lane-state` as
    generation 0, and held the lane for that (review r3's NIT-A).

And the guards the fixes for those need: a named read reads its lane's log
ONCE, and finds the trees by that read; a tree whose lane's log - its binding
- was not read has no writer pronounced, named or in the whole listing, and
none has where the events' own list of the logs failed; a row whose log could
not be listed is never classed DORMANT; and `lane-state`'s 10 for a snapshot it
could not read names the file its one read of the log placed.

Every case runs on `test_lanes_index`'s own estate and its helpers.
"""

from __future__ import annotations

import os

import pytest

from test_lanes_index import (HEADS, LANES, SHOW_LOG_B1, US, _a_lane_found_through_its_log,
                              _git_shim, _row, _shim_calls, _sidecar, _unreadable, _wt, inv)

__all__ = ["inv"]  # the fixture, imported so that pytest finds it here

LOG_B1 = "origin/main:lanes/log/repoB-1.md"
REGISTER = "origin/main:lanes/LANES.md"
ARCHIVE = "origin/main:lanes/archive/LANES-retired.md"
LOG_TREE = "origin/main:lanes/log"
SHOW_REGISTER = "show origin/main:lanes/LANES.md "
LIST_LOGS = "ls-tree --name-only origin/main -- lanes/log/ "
NO_GIT = {"LANES_NO_GIT": "1"}


def _lines(stdout: str) -> list[list[str]]:
    return [line.split(US) for line in stdout.splitlines() if line]


def _no_dead_writer(lines: list[list[str]]) -> None:
    """No TREE line pronounces its writer `0` - "nobody is writing there"."""
    for fields in lines:
        if fields[0] == "TREE":
            assert fields[10] != "0", fields


# ------------------------------------------------- SHOULD-3: the lane's log


def test_a_named_read_whose_log_could_not_be_read_says_so_and_not_none(inv):
    """THE NAMED READ'S ONE READ OF THE LANE'S LOG (the review of #289,
    SHOULD-3, its probe P4). Where no override names a control root, a lane's
    trees are under the root its log's `dir` places, and a named read reads
    that log once, through `lanes_rows --lane`. A published log git could not
    read gave no `dir`, the root fell to `$PROJECTS_ROOT/.lane-state`, and the
    read said "none": exit 8, and `lanes --worktrees` said "no worktree is
    inventoried". It is now ONE `UNREAD` line naming the log, exit 0, which
    `lanes --worktrees` prints as NOT READ. The `lanes --lane` read of the same
    lane - the one `lane <name>` makes - still answers, and says it."""
    by_dir, key = _a_lane_found_through_its_log(inv)
    whole = inv.e.edit("worktrees", "repoB-1", env=by_dir)
    assert whole.returncode == 0, whole.stderr
    assert [f[0] for f in _lines(whole.stdout)] == ["TREE"], whole.stdout  # not vacuous
    with _unreadable(inv.e, LOG_B1):
        res = inv.e.edit("worktrees", "repoB-1", env=by_dir)
        assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
        lines = _lines(res.stdout)
        assert len(lines) == 1 and lines[0][:3] == ["UNREAD", "Eagle", "repoB-1"], res.stdout
        assert "its object log lanes/log/repoB-1.md could not be read" in lines[0][3], lines[0]
        listed = _wt(inv, "repoB-1", env=by_dir)
        assert listed.returncode == 0, (listed.stdout, listed.stderr)
        assert "inventory NOT READ: its object log lanes/log/repoB-1.md could not be read" \
            in listed.stdout, listed.stdout
        assert "no worktree is inventoried" not in listed.stdout, listed.stdout
        row = inv.e.edit("lanes", "--lane", "repoB-1", env=by_dir)
        assert row.returncode == 0, (row.stdout, row.stderr)
        assert row.stdout.startswith("repoB-1\t"), row.stdout
        assert "these published logs could not be read, so no lane of theirs is classed " \
            "DORMANT: lanes/log/repoB-1.md" in row.stderr, row.stderr


def test_a_named_read_of_a_lane_with_no_published_log_still_says_none(inv):
    """A LOG THAT IS NOT THERE IS NOT ONE THAT COULD NOT BE READ. repoC-1 has a
    row and no log: `git show` of its log fails because origin has no such
    path, and the tree says so - the read is the 8 it always was, and a lane
    with a tree of its own lists it.

    ASKED WITH NO OVERRIDE NAMING THE CONTROL ROOT, as a workstation asks it
    (the review of #290, SHOULD-1(a)). The fixture's `LANES_LANE_STATE_ROOT`
    places every lane's root without its log, so the named read never reaches
    its `UNREAD` line and `lane-state` never reads the log: a read that took
    "no such path" for "could not be read" passed under it. Without it the
    named read is still 8 and empty, `lanes --lane` says nothing of a log that
    could not be read, and `lane-state` is 8 - never the 10 of a log it could
    not read, which `lanes-index` holds a lane for."""
    no_root = {"LANES_LANE_STATE_ROOT": None}
    res = inv.e.edit("worktrees", "repoC-1", env=no_root)
    assert res.returncode == 8, (res.returncode, res.stdout, res.stderr)
    assert res.stdout == "", res.stdout
    row = inv.e.edit("lanes", "--lane", "repoC-1", env=no_root)
    assert row.returncode == 0 and row.stdout.startswith("repoC-1\t"), (row.stdout, row.stderr)
    assert "could not be read" not in row.stderr, row.stderr
    state = inv.e.edit("lane-state", "repoC-1", env=no_root)
    assert state.returncode == 8, (state.returncode, state.stdout, state.stderr)
    _sidecar(inv.lsr, "repoC-1", HEADS["repoC-1"])
    res = inv.e.edit("worktrees", "repoC-1")
    assert res.returncode == 0, res.stderr
    assert [f[:3] for f in _lines(res.stdout)] == [["TREE", "Eagle", "repoC-1"]], res.stdout


@pytest.mark.parametrize("what,mode", [("dir", 0o000), ("dir", 0o400), ("file", 0o000)],
                         ids=["dir-000", "dir-400", "file-000"])
def test_a_named_read_with_no_origin_whose_log_will_not_open_says_so(inv, what, mode):
    """THE SAME READ WITH NO `origin` (`LANES_NO_GIT=1`): the lane's log is this
    checkout's file. A log directory that cannot be searched hid the file -
    the read found no log, no `dir`, and said "none" - and a log file that
    would not open did the same through the parser's own status, which the
    listing threw away."""
    by_dir, key = _a_lane_found_through_its_log(inv)
    env = {**by_dir, **NO_GIT}
    whole = inv.e.edit("worktrees", "repoB-1", env=env)
    assert whole.returncode == 0 and "TREE" + US in whole.stdout, whole.stdout  # not vacuous
    logdir = inv.e.wip / "lanes" / "log"
    target = logdir if what == "dir" else logdir / "repoB-1.md"
    before = target.stat().st_mode & 0o777
    target.chmod(mode)
    try:
        if what == "dir" and os.access(logdir, os.R_OK) and os.access(logdir, os.X_OK) \
                or what == "file" and os.access(target, os.R_OK):
            pytest.skip(f"this account reads a mode-{mode:03o} {what} (root): nothing to prove")
        res = inv.e.edit("worktrees", "repoB-1", env=env)
        assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
        lines = _lines(res.stdout)
        assert len(lines) == 1 and lines[0][:3] == ["UNREAD", "Eagle", "repoB-1"], res.stdout
        assert "its object log lanes/log/repoB-1.md could not be read" in lines[0][3], lines[0]
    finally:
        target.chmod(before)


# ------------------------------------------- the register, for a named read


def test_a_named_read_with_the_register_unreadable_never_says_none(inv):
    """THE REGISTER SPELLS THE LANE, AND ITS IDS SAY WHO WRITES (#289's writer's
    items, filed on #290). With the register unreadable, `canon_lane` hands
    back the name as typed: typed in another case, it named a control root
    that is not there, and the read said "none". Where the register could not
    be read and no tree was found, that is now an `UNREAD` line naming the
    register - a case-folding filesystem finds the trees instead - and a tree
    that is found is never pronounced writer `0`: whether a writer holds it is
    the register's ids, which nobody read."""
    folds = (inv.lsr / "REPOA-1").is_dir()
    with _unreadable(inv.e, REGISTER):
        other = inv.e.edit("worktrees", "REPOA-1")
        assert other.returncode == 0, (other.returncode, other.stdout, other.stderr)
        lines = _lines(other.stdout)
        _no_dead_writer(lines)
        if not folds:
            assert len(lines) == 1 and lines[0][:3] == ["UNREAD", "Eagle", "REPOA-1"], \
                other.stdout
            assert "the register lanes/LANES.md could not be read" in lines[0][3], lines[0]
        listed = _wt(inv, "REPOA-1")
        assert listed.returncode == 0, (listed.stdout, listed.stderr)
        assert "no worktree is inventoried" not in listed.stdout, listed.stdout
        same = inv.e.edit("worktrees", "repoA-1")
        assert same.returncode == 0, same.stderr
        trees = [f for f in _lines(same.stdout) if f[0] == "TREE"]
        assert len(trees) == 2, same.stdout
        assert [f[10] for f in trees] == ["", ""], trees  # unknown, never `0`


def test_a_named_read_answers_by_the_register_read_made_before_its_name(inv):
    """THE REGISTER READ THE NAME WAS RESOLVED BY IS THE ONE THE READ ANSWERS BY.
    A register read that succeeds is kept for the process; one that fails is
    asked again. Here the read made before the name was resolved fails, and so
    does `canon_lane`'s own, which hands back `REPOA-1` as typed - and the
    next read succeeds: a read that asked the register again after the name
    was resolved took the register for read, looked under a root no lane has,
    and said "none"."""
    env, log = _git_shim(inv, SHOW_REGISTER, first=1, last=2)
    res = inv.e.edit("worktrees", "REPOA-1", env=env)
    calls = _shim_calls(log)
    assert len(calls) >= 3, calls  # two reads failed and a later one read: not vacuous
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr, calls)
    lines = _lines(res.stdout)
    _no_dead_writer(lines)
    assert lines and all(f[2].lower() == "repoa-1" for f in lines), res.stdout


def test_the_whole_listing_with_the_register_unreadable_pronounces_no_writer_dead(inv):
    """AND IN THE WHOLE LISTING TOO: it is `PARTIAL` there, and the sync
    writes nothing over it, but `lanes --worktrees` prints its rows - and a
    writer whose lane's ids the register held is unknown, not `0`. A writer
    found LIVE through this checkout's own copy of the row stays LIVE: that is
    a session record naming one of the lane's ids, read."""
    with _unreadable(inv.e, REGISTER):
        res = inv.e.edit("worktrees", "--all")
        assert res.returncode == 0, res.stderr
        lines = _lines(res.stdout)
        assert any(f[0] == "PARTIAL" for f in lines), res.stdout
        _no_dead_writer(lines)
        live = {f[4]: f[10] for f in lines if f[0] == "TREE"}
        assert live[str(inv.a2_tree)] == "1", live
        assert live[str(inv.run_tree)] == "" and live[str(inv.dirty_tree)] == "", live


# --------------------------------------------- the `lanes` listing itself


def test_the_lane_listing_says_when_the_list_of_the_logs_could_not_be_made(inv):
    """THE LISTING ITSELF, NOT `--worktrees` (#289's writer's items, on #290).
    The lanes are named from the register, the archive and the list of the
    logs, and the logs' lines are read through a second list of them. Where
    both lists failed, the listing said nothing: a lane with a log and no row
    was simply missing, and no row showed what its log says. It says both
    now - and that no row is classed DORMANT over it, the words `lane-end
    --retire-dormant` refuses on."""
    env, log = _git_shim(inv, LIST_LOGS, first=1)
    res = inv.e.edit("lanes", "--all", env=env)
    assert len(_shim_calls(log)) >= 2, _shim_calls(log)  # both lists failed: not vacuous
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert "repoA-1\t" in res.stdout and "repoB-1\t" not in res.stdout, res.stdout
    assert "the object logs under origin/main:lanes/log/ could not be listed, so a lane " \
        "with a log and no row in the register or the archive is missing from this listing" \
        in res.stderr, res.stderr
    assert "could not be listed for their lines" in res.stderr, res.stderr
    assert "no row is classed DORMANT here" in res.stderr, res.stderr


def test_a_lane_listing_its_failed_reads_left_empty_is_not_none(inv):
    """AN EMPTY LISTING OVER READS THAT FAILED IS NOT "NO LANE". With the
    register, the archive and the list of the logs all unreadable, the listing
    named no lane and said so as 8 - and `lanes` printed "no lane is recorded"
    - before any of its notes. Each read that failed is said, and the read is
    1: the listing could not be read."""
    with _unreadable(inv.e, ARCHIVE, REGISTER, LOG_TREE):
        res = inv.e.edit("lanes", "--all")
        assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
        assert res.stdout == "", res.stdout
        for said in ("the register (lanes/LANES.md, published or this checkout's) could not "
                     "be read",
                     "lanes/archive/LANES-retired.md exists and could not be read",
                     "the object logs under origin/main:lanes/log/ could not be listed"):
            assert said in res.stderr, (said, res.stderr)
        wrapped = inv.e.run("bash", LANES, "--all")
        assert wrapped.returncode == 1, (wrapped.returncode, wrapped.stdout, wrapped.stderr)
        assert "no lane is recorded" not in wrapped.stdout, wrapped.stdout


# ------------------------------------------ no `origin`, one log file


def test_an_unreadable_log_file_with_no_origin_is_said_and_drops_no_other(inv):
    """WITH NO `origin` THE LOGS ARE THIS CHECKOUT'S FILES, read in one parser
    run - and one that would not open left no warning naming it: the listing
    took it for a lane with no log and the inventory's read for whole. `mawk`
    (Debian's and Ubuntu's `awk`) ends at the first file it cannot open, so
    every log after it was gone as well. The file is said now, by name - the
    inventory's read is `PARTIAL` over it - and the logs after it are read."""
    log = inv.e.wip / "lanes" / "log" / "repoA-2.md"
    log.chmod(0)
    try:
        if os.access(log, os.R_OK):
            pytest.skip("this account reads a mode-000 file (root): nothing to prove here")
        res = inv.e.edit("worktrees", "--all", env=NO_GIT)
        assert res.returncode == 0, res.stderr
        partial = [f for f in _lines(res.stdout) if f[0] == "PARTIAL"]
        assert len(partial) == 1, res.stdout
        assert "these object logs could not be read: lanes/log/repoA-2.md" in partial[0][2], \
            partial
        listed = inv.e.edit("lanes", "--all", env=NO_GIT)
        assert listed.returncode == 0, listed.stderr
        assert "these published logs could not be read, so no lane of theirs is classed " \
            "DORMANT: lanes/log/repoA-2.md" in listed.stderr, listed.stderr
        b1 = [row for row in listed.stdout.splitlines() if row.startswith("repoB-1\t")]
        assert len(b1) == 1 and b1[0].split("\t")[1] == "IDLE", listed.stdout  # read, after it
    finally:
        log.chmod(0o644)


# ------------------------------------- NIT-A: `lanes-index`'s generation read


def test_a_generation_read_whose_log_failed_says_so_and_holds(inv):
    """THE SYNC ASKS `lane-state` FOR THE GENERATION OF A LANE WHOSE ROWS WOULD
    ALL LEAVE (review r3 of #289, NIT-A). That read worked the lane's root out
    again from its log and threw a failed `git show` away: `lane-state` said
    8, read as generation 0, and the sync held the lane because its
    "generation reads 0 and its rows were written at 1" - a hold for a reason
    that was not the one. `lane-state` now reads the lane's `dir` once, with
    its status, and a log it could not read is its 10 - the record is there
    and could not be read, never the 8 of none - and the hold says so. A
    `reconcile` over the same read keeps the rows too, for the same reason,
    and the first read that succeeds takes the lane as it stands."""
    by_dir, key = _a_lane_found_through_its_log(inv)
    put = inv.e.edit("set-lane-state", "repoB-1", "RUNNING", "--operation", "op-test-b1",
                     env=by_dir)
    assert put.returncode == 0, put.stderr
    assert inv.sync(env=by_dir).returncode == 0
    assert inv.rows()[key]["generation"] == 1, inv.rows()[key]  # rows written at 1
    with _unreadable(inv.e, LOG_B1):
        state = inv.e.edit("lane-state", "repoB-1", env=by_dir)
        assert state.returncode == 10, (state.returncode, state.stdout, state.stderr)
        assert "lane repoB-1's object log could not be read" in state.stderr, state.stderr
    for sidecar in (inv.root / "elsewhere" / ".lane-state" / "repoB-1" / "trees").iterdir():
        sidecar.unlink()  # its rows would all leave: the sync asks for its generation
    why = "its lifecycle generation could not be read - lane repoB-1's object log could not " \
        "be read"
    shim, log = _git_shim(inv, SHOW_LOG_B1, first=2, last=2)
    res = inv.sync(env={**by_dir, **shim})
    calls = _shim_calls(log)
    assert len(calls) == 2, calls  # the listing's read, then `lane-state`'s: not vacuous
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert key in inv.rows(), (res.stdout, calls)  # a refused hold stays a hold
    assert "generation reads 0" not in res.stdout, res.stdout
    assert f"lane repoB-1: its rows are kept as they are - {why}" in res.stdout, res.stdout
    shim, log = _git_shim(inv, SHOW_LOG_B1, first=2, last=2)
    rec = inv.e.index("reconcile", "--source", "inventory", env={**by_dir, **shim})
    assert len(_shim_calls(log)) == 2, _shim_calls(log)
    assert rec.returncode == 0, (rec.stdout, rec.stderr)
    assert "went back from 1 to 0" not in rec.stdout, rec.stdout
    assert f"lane repoB-1: its rows are kept as they are - {why}" in rec.stdout, rec.stdout
    assert key in inv.rows(), rec.stdout
    healed = inv.sync(env=by_dir)
    assert healed.returncode == 0, healed.stderr
    assert "0 upserted, 1 removed" in healed.stdout, healed.stdout
    assert key not in inv.rows(), healed.stdout


# --------------------------------------- the named read reads its log once


def test_a_named_read_reads_its_lanes_log_once_and_finds_its_trees_by_it(inv):
    """ONE READ OF THE LANE'S LOG, AND IT IS THE ONE ITS TREES ARE FOUND BY
    (#290). The named read reads the log with its status, and the listing it
    asks for the lane's row takes that read from it (`PIN_LANE_LOG`) instead of
    making a second one: a second read that failed where the first had not gave
    the row no `dir`, the root fell to the third rung, and the read said "none"
    over the trees the first read had placed."""
    by_dir, key = _a_lane_found_through_its_log(inv)
    shim, log = _git_shim(inv, SHOW_LOG_B1, first=2)
    res = inv.e.edit("worktrees", "repoB-1", env={**by_dir, **shim})
    calls = _shim_calls(log)
    assert len(calls) == 1, calls  # read once, and so never by the read that fails
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr, calls)
    assert [f[:3] for f in _lines(res.stdout)] == [["TREE", "Eagle", "repoB-1"]], res.stdout


# ------------------------------------------------ a binding nobody read


@pytest.mark.parametrize("named", [True, False], ids=["named", "whole"])
def test_a_tree_whose_lanes_log_was_not_read_has_no_writer_pronounced(inv, named):
    """THE LANE'S LOG IS ITS BINDING, AND A BINDING NOBODY READ IS NOT ONE THAT
    IS HERE (#290, Amendment 18(b)). A writer of `0` says that no live record
    here names one of the lane's ids AND that its binding is here or nowhere;
    with the lane's log unread the second half was never read - the lane may be
    bound on another host - so the writer is unknown, as it is for a lane
    bound elsewhere. An override naming the control root still finds the
    trees, so they are listed. A lane whose log was read keeps its own answer
    beside it: repoA-2 is still LIVE."""
    with _unreadable(inv.e, "origin/main:lanes/log/repoA-1.md"):
        res = inv.e.edit("worktrees", *(["repoA-1"] if named else ["--all"]))
        assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
        lines = _lines(res.stdout)
        a1 = {f[4]: f[10] for f in lines if f[0] == "TREE" and f[2] == "repoA-1"}
        assert a1 == {str(inv.run_tree): "", str(inv.dirty_tree): ""}, lines
        if not named:
            assert any(f[0] == "PARTIAL" for f in lines), lines  # and the listing is not whole
            a2 = {f[4]: f[10] for f in lines if f[0] == "TREE" and f[2] == "repoA-2"}
            assert a2 == {str(inv.a2_tree): "1"}, lines


def test_a_listing_whose_logs_could_not_be_listed_pronounces_no_writer(inv):
    """AND WHERE THE EVENTS' OWN LIST OF THE LOGS COULD NOT BE MADE, NO LANE'S
    BINDING WAS READ (#290). The listing's first list of the logs is pinned and
    names the lanes; the events list them again for their lines, and where that
    list failed the read is `PARTIAL` - and no tree in it has a writer
    pronounced, LIVE included, because a lane bound on another host is
    unknown from here whatever a local record says (Amendment 18(b))."""
    shim, log = _git_shim(inv, LIST_LOGS, first=2)
    res = inv.e.edit("worktrees", "--all", env=shim)
    assert len(_shim_calls(log)) == 2, _shim_calls(log)  # the check's list, then the events'
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    lines = _lines(res.stdout)
    assert any(f[0] == "PARTIAL" and "could not be listed" in f[2] for f in lines), lines
    writers = {f[4]: f[10] for f in lines if f[0] == "TREE"}
    assert str(inv.a2_tree) in writers and len(writers) >= 3, lines  # not vacuous
    assert set(writers.values()) == {""}, writers


# ---------------------------------- the DORMANT class over a failed log list

UUID_D1 = "dddddddd-0002-4000-8000-00000000d002"


def test_a_row_whose_log_could_not_be_listed_is_not_classed_dormant(inv):
    """A ROW WITH A PUBLISHED LOG IS NOT A ROW WITH NO LOG BECAUSE THE LIST OF
    THE LOGS FAILED (#290). DORMANT is a row with no object log, asked of the
    events, and where their own list of the logs could not be made no lane has
    a line in them: a row whose log is on `origin` and not yet in this
    checkout, with an `ENDED` cell, was classed DORMANT - left out of the
    listing and offered to `lane-end --retire-dormant`. It is listed now, as
    the listing's note says, and its class is withheld."""
    lanes = inv.e.wip / "lanes"
    reg = lanes / "LANES.md"
    rows = reg.read_text(encoding="utf-8").split("\n")
    at = next(i for i, line in enumerate(rows) if line.startswith("| `repoC-1`"))
    rows.insert(at + 1, _row("repoD-1", f"`{UUID_D1}`", "ENDED · 2026-09-03T00:00:00Z · done",
                             started="2026-09-03"))
    reg.write_text("\n".join(rows), encoding="utf-8")
    dlog = lanes / "log" / "repoD-1.md"
    dlog.write_text(f"STARTED — lane repoD-1, session {UUID_D1}@Eagle, 2026-09-03T00:00:00Z, "
                    f"lane:repoD-1 → home opensoft/repoD; dir /work/repoD\n", encoding="utf-8")
    inv.e._git("add", "-A")
    inv.e._git("commit", "-q", "-m", "repoD-1: a row and a log")
    inv.e._git("push", "-q", "origin", "main")
    dlog.unlink()  # published, and not in this checkout
    whole = inv.e.edit("lanes", "--all")
    assert whole.returncode == 0, whole.stderr
    d1 = [row.split("\t") for row in whole.stdout.splitlines() if row.startswith("repoD-1\t")]
    assert len(d1) == 1 and d1[0][1] == "IDLE" and d1[0][13] == "none", whole.stdout  # not vacuous
    env, log = _git_shim(inv, LIST_LOGS, first=1)
    res = inv.e.edit("lanes", "--all", env=env)
    assert len(_shim_calls(log)) >= 2, _shim_calls(log)
    assert res.returncode == 0, (res.stdout, res.stderr)
    d1 = [row.split("\t") for row in res.stdout.splitlines() if row.startswith("repoD-1\t")]
    assert len(d1) == 1 and d1[0][13] == "none", (res.stdout, res.stderr)


# -------------------------- `lane-state`'s own 10 names the file it found


def test_an_unreadable_snapshot_is_named_where_the_lanes_one_read_placed_it(inv):
    """THE 10 OF A SNAPSHOT THAT COULD NOT BE READ NAMES THAT SNAPSHOT (#290).
    `lane-state` reads the lane's `dir` once and finds the snapshot by it; the
    message for a snapshot it could not read worked the root out again,
    reading the log a second time, and where that read failed it named a file
    the third rung places - not the one that could not be read."""
    by_dir, key = _a_lane_found_through_its_log(inv)
    put = inv.e.edit("set-lane-state", "repoB-1", "RUNNING", "--operation", "op-test-b1",
                     env=by_dir)
    assert put.returncode == 0, put.stderr
    snap = inv.root / "elsewhere" / ".lane-state" / "repoB-1" / "lane-state.yaml"
    assert snap.is_file(), snap  # where the log's `dir` places it: not vacuous
    snap.chmod(0)
    try:
        if os.access(snap, os.R_OK):
            pytest.skip("this account reads a mode-000 file (root): nothing to prove here")
        shim, log = _git_shim(inv, SHOW_LOG_B1, first=2)
        res = inv.e.edit("lane-state", "repoB-1", env={**by_dir, **shim})
        assert len(_shim_calls(log)) == 1, _shim_calls(log)
        assert res.returncode == 10, (res.returncode, res.stdout, res.stderr)
        assert f"Read it by hand: {snap}" in res.stderr, res.stderr
    finally:
        snap.chmod(0o644)
