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

Every case runs on `test_lanes_index`'s own estate and its helpers.
"""

from __future__ import annotations

import os

import pytest

from test_lanes_index import (HEADS, LANES, SHOW_LOG_B1, US, _a_lane_found_through_its_log,
                              _git_shim, _shim_calls, _sidecar, _unreadable, _wt, inv)

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
    with a tree of its own lists it."""
    res = inv.e.edit("worktrees", "repoC-1")
    assert res.returncode == 8, (res.returncode, res.stdout, res.stderr)
    assert res.stdout == "", res.stdout
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
