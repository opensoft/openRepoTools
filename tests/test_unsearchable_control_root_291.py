# SPDX-License-Identifier: Apache-2.0
"""opensoft/openRepoTools#291 (the review of #289, its SHOULD-4): A LANE CONTROL
ROOT THAT CANNOT BE SEARCHED IS NOT A LANE WITH NO TREES.

A lane's trees and its lifecycle snapshot are under its control root,
`<parent of its dir>/.lane-state/<lane>` (or `$PROJECTS_ROOT/.lane-state/<lane>`
for a lane whose `dir` has no parent here). The shell's `[ -d ]`, `[ -e ]` and
`[ -r ]` are all false for a path under a directory this account may not
SEARCH - stat fails with EACCES there exactly as it fails with ENOENT for a
name that is gone - so a `.lane-state` at mode 000 read as a lane with no
trees (the review's probe P5): `lanes-edit.sh worktrees --all` said nothing of
the lane (or "none", exit 8, where it was the only lane with trees), and
`lanes-index sync` wrote `0 upserted, 1 removed`, deleting its rows.
`lane-trees <lane>` and `lane-state <lane>` answered 8 - "this lane recorded no
tree", "this lane has no snapshot" - which a launcher answers by going on, and
`lane-reconcile <lane>` pronounced `no-state`. The rungs that place the root
did the same one level up: a recorded `dir` whose parent could not be looked
for fell to `$PROJECTS_ROOT`, a different root, and a `$PROJECTS_ROOT` that
could not be looked for left the lane no root at all.

What these tests hold the helper to, for each place the lookup can stop - the
lane's `.lane-state`, its control root itself (readable and not searchable), a
directory above the recorded `dir`'s parent, one above `$PROJECTS_ROOT`, and a
`.lane-state` that is a link into a directory that cannot be searched:

  * the listing names the lane `UNREAD` - its inventory could not be read - and
    never leaves it out. It is the lane's own line because the listing NAMED
    the lane and only its inventory is unread, which is what `UNREAD` has
    meant since #171; #289's `PARTIAL` is for a lane listing that could not
    name a lane at all, and it holds every lane's rows, not this one's;
  * `lanes-index sync` holds that lane's rows and removes nothing;
  * `lane-trees <lane>` and `lane-state <lane>` exit 10, "could not be read",
    and `lane-reconcile <lane>` pronounces nothing (`indeterminate`);
  * a root, a `trees` or a snapshot that is simply not there is still the 8 of
    "none", and a lane with no trees still holds nothing in a sync.

Beside them: a `trees` directory that is there and cannot be searched (the
read #157 item 4e already made `UNREAD`, kept as it is), and a tree record that
cannot be read - `lane-trees` names it as its own `<unreadable>` row with exit
0, which the handoff reads per record (#255), and the listing now holds the
lane too, so a sync no longer swaps the tree's row for one with no path.

The lane has trees and NO lifecycle snapshot, as in the review's probe. A
snapshot would hide the removal from a `sync`: it asks `lane-state` for the
generation of a lane whose rows would all leave, and rows written at
generation 1 that now read 0 are held, for the wrong reason, while `reconcile`
removes them.

Every mode set here is restored before the case ends, and root - which
searches and reads a mode-000 directory - proves nothing here and skips.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
from pathlib import Path

import pytest

from conftest import WINDOWS_SKIP
from test_lanes_index import HEADS, US, UUID_B1, Inventory, _sidecar, _wt

pytestmark = [
    WINDOWS_SKIP,
    pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                       reason="the lane tooling is bash over git"),
    pytest.mark.skipif(getattr(os, "geteuid", lambda: -1)() == 0,
                       reason="root searches and reads a mode-000 directory: nothing to prove here"),
]

LANE = "repoB-1"
SIDECAR_ID = f"c0-{LANE}"
KEY = f"{LANE}:/nowhere/{LANE}/w"
HELD = f"lane {LANE}: its rows are kept as they are - "


@pytest.fixture
def inv(tmp_path):
    """test_lanes_index's estate with an inventory, made here as it is there."""
    made = Inventory(tmp_path / "i")
    yield made
    made.close()


@contextlib.contextmanager
def _modes(changes: list[tuple[Path, int]]):
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


def _a_lane_with_trees(inv: Inventory, away: Path, env: dict, *,
                       state: Path | None = None, make_dir: bool = True) -> Path:
    """repoB-1 RESUMED with `dir <away>/repoB` - `away` need not be there - and
    one tree, and no snapshot, under the control root that `dir` places
    (`state`, `<away>/.lane-state` by default; a lane whose `dir` has no parent
    here is placed under `$PROJECTS_ROOT/.lane-state`), synced with no override
    naming a control root. Returns that root. Before anything is recorded the
    root is not there and the lookup that says so was made: the 8 of "none",
    which is what this file must not take from a lane anywhere else."""
    if make_dir:
        (away / "repoB").mkdir(parents=True, exist_ok=True)
    log = inv.e.wip / "lanes" / "log" / f"{LANE}.md"
    log.write_text(log.read_text(encoding="utf-8") +
                   f"RESUMED — lane {LANE}, session {UUID_B1}@Eagle, 2026-10-05T00:00:00Z, "
                   f"lane:{LANE} → dir {away / 'repoB'}; profile team-02a\n", encoding="utf-8")
    inv.e._git("add", "-A")
    inv.e._git("commit", "-q", "-m", f"{LANE} resumed with a dir of its own")
    inv.e._git("push", "-q", "origin", "main")
    root = (state or away / ".lane-state") / LANE
    for verb in ("lane-trees", "lane-state"):
        none = inv.e.edit(verb, LANE, env=env)
        assert none.returncode == 8, (verb, none.returncode, none.stdout, none.stderr)
    _sidecar(root.parent, LANE, HEADS[LANE])
    synced = inv.sync(env=env)
    assert synced.returncode == 0, (synced.stdout, synced.stderr)
    assert "kept as they are" not in synced.stdout, synced.stdout  # no lane is unread yet
    assert KEY in inv.rows(), sorted(inv.rows())  # found through `dir` alone
    return root


def _layout(inv: Inventory, case: str) -> tuple[dict, Path, list[tuple[Path, int]], str]:
    """`(env, control root, the modes that block it, the words the helper
    gives for where the lookup stops)` for one case."""
    env = {"LANES_LANE_STATE_ROOT": None}
    if case == "lane-state-dir":         # the review's probe P5, as the issue gives it
        away = inv.root / "elsewhere"
        root = _a_lane_with_trees(inv, away, env)
        where = away / ".lane-state"
        return env, root, [(where, 0o000)], f"the directory {where} cannot be searched"
    if case == "control-root":           # readable, and not searchable: the x bit decides
        away = inv.root / "elsewhere"
        root = _a_lane_with_trees(inv, away, env)
        return env, root, [(root, 0o600)], f"the directory {root} cannot be searched"
    if case == "above-the-dirs-parent":  # rung 2: the parent of `dir` could not be looked for
        projects = inv.root / "projects"
        projects.mkdir()
        env["PROJECTS_ROOT"] = str(projects)
        away = inv.root / "far" / "away"
        root = _a_lane_with_trees(inv, away, env)
        where = inv.root / "far"
        return env, root, [(where, 0o000)], f"the directory {where} cannot be searched"
    if case == "above-projects-root":    # rung 3: `$PROJECTS_ROOT` could not be looked for
        where = inv.root / "vault"
        projects = where / "projects"
        projects.mkdir(parents=True)
        env["PROJECTS_ROOT"] = str(projects)
        away = inv.root / "gone"         # not there, so rung 2 has no parent here
        root = _a_lane_with_trees(inv, away, env, state=projects / ".lane-state",
                                  make_dir=False)
        return env, root, [(where, 0o000)], f"the directory {where} cannot be searched"
    if case == "link-into-a-locked-dir":  # stat cannot tell this link from a dangling one
        away = inv.root / "elsewhere"
        locked = away / "locked"
        (locked / "lane-state").mkdir(parents=True)
        (away / ".lane-state").symlink_to(locked / "lane-state")
        root = _a_lane_with_trees(inv, away, env)
        where = away / ".lane-state"
        return env, root, [(locked, 0o000)], f"{where} is a symbolic link that cannot be followed"
    raise AssertionError(case)


def _lines(text: str, kind: str, lane: str | None = None) -> list[list[str]]:
    rows = [line.split(US) for line in text.splitlines() if line.startswith(kind + US)]
    return [r for r in rows if lane is None or r[2] == lane]


def _reconcile(text: str) -> dict:
    return {r[0]: r[1:] for r in (line.split(US) for line in text.splitlines())
            if r[0] in ("ROOT", "STATE", "VERDICT")}


BLOCKED = ["lane-state-dir", "control-root", "above-the-dirs-parent", "above-projects-root",
           "link-into-a-locked-dir"]


@pytest.mark.parametrize("case", BLOCKED, ids=BLOCKED)
def test_a_control_root_nobody_could_search_is_not_a_lane_with_no_trees(inv, case):
    """THE LOOKUP THAT SAYS A ROOT IS NOT THERE HAS TO HAVE BEEN MADE (#291).
    Where it could not be - a directory on the way that cannot be searched, a
    link on the way that cannot be followed - the lane's inventory and its
    snapshot are UNREAD, never absent: the listing says so in the lane's own
    `UNREAD` line, a sync holds the lane's rows and removes none, the named
    reads exit 10, and the reconciliation pronounces nothing. Put back, the
    next sync takes the lane's marker away and nothing else."""
    env, root, modes, why = _layout(inv, case)
    unread = f"whether its trees directory {root}/trees is there could not be read: {why}"
    kept = set(inv.rows())
    assert KEY in kept  # not vacuous: the row a wrong read would remove
    with _modes(modes):
        assert not os.path.exists(root / "trees"), "the block did not take: nothing to prove"
        res = inv.sync(env=env)
        assert res.returncode == 0, (res.stdout, res.stderr)
        assert " 0 removed" in res.stdout, res.stdout
        assert KEY in inv.rows(), (res.stdout, sorted(inv.rows()))
        assert HELD in res.stdout and f"({unread})" in res.stdout, res.stdout

        listed = inv.e.edit("worktrees", "--all", env=env)
        assert listed.returncode == 0, (listed.returncode, listed.stdout, listed.stderr)
        assert _lines(listed.stdout, "UNREAD", LANE) == [["UNREAD", "Eagle", LANE, unread]], \
            listed.stdout
        assert _lines(listed.stdout, "TREE", LANE) == [], listed.stdout
        assert _lines(listed.stdout, "PARTIAL") == [], listed.stdout  # the lane IS named

        trees = inv.e.edit("lane-trees", LANE, env=env)
        assert trees.returncode == 10, (trees.returncode, trees.stdout, trees.stderr)
        assert trees.stdout == "", trees.stdout
        assert f"whether lane {LANE} has a worktree inventory could not be read: {root}/trees " \
            f"could not be looked for, because {why}. That is NOT 'this lane recorded no " \
            f"tree'" in trees.stderr, trees.stderr

        state = inv.e.edit("lane-state", LANE, env=env)
        assert state.returncode == 10, (state.returncode, state.stdout, state.stderr)
        assert f"whether lane {LANE} has a lifecycle snapshot could not be read: " \
            f"{root}/lane-state.yaml could not be looked for, because {why}. That is NOT " \
            f"'this lane has no snapshot'" in state.stderr, state.stderr

        rec = inv.e.edit("lane-reconcile", LANE, env=env)
        assert rec.returncode == 0, (rec.returncode, rec.stdout, rec.stderr)
        facts = _reconcile(rec.stdout)
        assert facts.get("ROOT") == [str(root)], rec.stdout
        assert facts.get("STATE", [""])[0] == "UNREADABLE", rec.stdout
        assert facts.get("VERDICT", [""])[0] == "indeterminate", rec.stdout
        assert f"whether this lane has a lifecycle snapshot at {root}/lane-state.yaml could not " \
            f"be read: {why}, so where its session stopped is NOT established" \
            in facts["VERDICT"][1], rec.stdout

        named = _wt(inv, LANE, env=env)
        assert named.returncode == 0, (named.returncode, named.stdout, named.stderr)
        assert f"inventory NOT READ: {unread}" in named.stdout, named.stdout
    healed = inv.sync(env=env)
    assert healed.returncode == 0 and "0 upserted" in healed.stdout, healed.stdout
    assert "kept as they are" not in healed.stdout, healed.stdout
    assert set(inv.rows()) == kept, (healed.stdout, sorted(inv.rows()))
    assert inv.e.edit("lane-trees", LANE, env=env).returncode == 0
    assert inv.e.edit("lane-state", LANE, env=env).returncode == 8  # none, and looked for


def test_a_trees_directory_that_cannot_be_searched_is_still_unread(inv):
    """ONE LEVEL DOWN, AS IT WAS (#157 item 4e, Copilot round 2 on #171): a
    `trees` directory that is there and readable and cannot be searched is a
    lane whose inventory could not be read - `UNREAD` in the listing, its rows
    held by a sync, and `lane-trees`' 10 in the words it has always had. The
    lookup of the root was made, so nothing of #291's is said, and the snapshot
    beside it, which is not there, is still the 8 of "none"."""
    env = {"LANES_LANE_STATE_ROOT": None}
    root = _a_lane_with_trees(inv, inv.root / "elsewhere", env)
    with _modes([(root / "trees", 0o600)]):
        listed = inv.e.edit("worktrees", "--all", env=env)
        assert listed.returncode == 0, listed.stderr
        assert _lines(listed.stdout, "UNREAD", LANE) == [[
            "UNREAD", "Eagle", LANE,
            f"its trees directory {root}/trees is there and could not be listed"]], listed.stdout
        res = inv.sync(env=env)
        assert res.returncode == 0 and " 0 removed" in res.stdout, (res.stdout, res.stderr)
        assert HELD in res.stdout, res.stdout
        assert KEY in inv.rows()
        trees = inv.e.edit("lane-trees", LANE, env=env)
        assert trees.returncode == 10, (trees.returncode, trees.stderr)
        assert f"lane {LANE}'s worktree inventory directory {root}/trees is there and could not " \
            f"be listed. That is NOT 'this lane recorded no tree'" in trees.stderr, trees.stderr
        state = inv.e.edit("lane-state", LANE, env=env)
        assert state.returncode == 8, (state.returncode, state.stdout, state.stderr)
    healed = inv.sync(env=env)
    assert healed.returncode == 0 and "0 upserted, 1 removed" in healed.stdout, healed.stdout


def test_a_tree_record_that_cannot_be_read_holds_its_lanes_rows(inv):
    """A RECORD THAT COULD NOT BE READ IS NOT A TREE WITH NO PATH. The listing
    names it as it did - a row of its own, `unreadable sidecar`, its file's
    id where the path would be - and `lane-trees` gives it as the
    `<unreadable>` row the handoff reads per record (#255), with exit 0. But a
    sync took that row for the whole truth: keyed by the id, it upserted it and
    REMOVED the tree's row - its path, its branch, its counts - as a tree the
    lane no longer had. The lane's inventory is there and could not be read,
    so the listing now says so in the lane's `UNREAD` line too, and a sync
    holds the lane's rows and removes nothing."""
    env = {"LANES_LANE_STATE_ROOT": None}
    root = _a_lane_with_trees(inv, inv.root / "elsewhere", env)
    record = root / "trees" / f"{SIDECAR_ID}.yaml"
    assert record.is_file()
    with _modes([(record, 0o000)]):
        res = inv.sync(env=env)
        assert res.returncode == 0, (res.stdout, res.stderr)
        assert " 0 removed" in res.stdout, res.stdout
        assert HELD in res.stdout, res.stdout
        assert KEY in inv.rows() and f"{LANE}:{SIDECAR_ID}" not in inv.rows(), sorted(inv.rows())
        listed = inv.e.edit("worktrees", "--all", env=env)
        assert listed.returncode == 0, listed.stderr
        assert _lines(listed.stdout, "UNREAD", LANE) == [[
            "UNREAD", "Eagle", LANE,
            f"these records under {root}/trees could not be read: {SIDECAR_ID}"]], listed.stdout
        tree = _lines(listed.stdout, "TREE", LANE)
        assert len(tree) == 1 and (tree[0][4], tree[0][5]) == (SIDECAR_ID, "unreadable sidecar"), \
            listed.stdout
        trees = inv.e.edit("lane-trees", LANE, env=env)
        assert trees.returncode == 0, (trees.returncode, trees.stderr)
        rows = [line.split(US) for line in trees.stdout.splitlines()]
        assert len(rows) == 1 and rows[0][0] == SIDECAR_ID and rows[0][1] == "" \
            and rows[0][12] == "<unreadable>", trees.stdout
    healed = inv.sync(env=env)
    assert healed.returncode == 0 and "0 upserted, 1 removed" in healed.stdout, healed.stdout
    assert KEY in inv.rows()
