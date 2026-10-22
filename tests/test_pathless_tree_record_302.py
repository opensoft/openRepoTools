# SPDX-License-Identifier: Apache-2.0
"""opensoft/openRepoTools#302: A TREE RECORD THAT NAMES NO ABSOLUTE PATH IS NOT A
TREE WITH THE PATH OF ITS ID.

The inventory index keys every tree `<lane>:<path>`. `lanes-edit.sh worktrees`
lists a record it cannot make a whole row of as a row of its own: `malformed
sidecar` for one of this schema that is not whole (#115), `unknown schema <n>`
for one of a schema it does not write, `unreadable sidecar` for one it could not
open (#255). Where the record names no path - or an empty one - the record's id
stands in the path column, so the key is `<lane>:<id>`; where it names a path
that is not absolute, the key is `<lane>:<that text>`. Either way the key is NOT
the tree's, and a sync took the row for the whole truth: it wrote the new row and
REMOVED the one the record last gave under its real path - the tree's path,
branch, counts and last commit - as a tree the lane no longer had.

#291's part F stopped that for a record that could not be READ: the lane is
`UNREAD` beside the record's row, and an indexer holds an `UNREAD` lane's rows
and syncs every other lane (`its rows are kept as they are`). A record that is
read, and names no absolute path, had no such line. These tests hold the helper to
the same line for it, at each of the shapes the issue probed (at main `33ce26d`
and at `457b73b`) and that were probed again, in a sandbox estate, at `3e97ae5`,
the branch head of #291 that this file is written on:

  * a schema 1 record with no `path:` line;
  * a schema 1 record with an empty `path:` value, which counts as none;
  * a schema 2 record with no `path:` line;
  * a schema 1 record whose `path:` is not absolute (relative text keys the row
    by that text).

and at two shapes the issue does not list but its rule reaches - the design
holds a lane for ANY record whose row would be keyed by something that is not an
absolute path, in the arm for a record that is not whole and the arm for one of
another schema alike:

  * a schema 2 record whose `path:` is not absolute;
  * an EMPTY file, a record cut to nothing, which reads as `unknown schema
    <none>` with no path.

For each: after a second sync the tree's row is exactly as the first left it, no
row keyed by the record's id (or by its relative path) appears, and the sync says
why in part F's words - `lane repoB-1: its rows are kept as they are - its
inventory could not be read (<the helper's UNREAD line>)`. The helper's own
`UNREAD` line names the record, and it is ONE line for the lane, because the
indexer keeps one reason per lane (`unread[lane] = why`): a lane holding both an
unreadable record and one with no absolute path says both in that line. The
record's own row stays in the listing, for a person to read, and `lane-trees`
keeps its exit-0 row, which the handoff reads per record (#255). Put right, the
next sync takes the lane's marker away and nothing else.

Controls, which hold at `3e97ae5` and must hold after the fix: a whole record is
still upserted in place and holds nothing; a record that is not whole or of
another schema but names an ABSOLUTE path keeps its key, and its row is rewritten
in place as it was (the issue's line, and a ruling to take to lane 3); and part
F's unreadable record keeps F's words.

THE WORDS OF THE NEW CLAUSE ARE THE DESIGN'S, in `_no_absolute_path` below and
nowhere else, so a ruling that rewords them changes one function.

The estate is #291's (`test_unsearchable_control_root_291`): `repoB-1` RESUMED
with a `dir` of its own, one whole tree record under the control root that `dir`
places, NO lifecycle snapshot (a snapshot would hide the removal from a sync
behind its generation fence, for the wrong reason), and a first sync that wrote
every row. Only the cases that set a file mode skip as root.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import NamedTuple

import pytest

from conftest import WINDOWS_SKIP
from test_lanes_index import HEADS, US, Inventory, _wt
from test_unsearchable_control_root_291 import (
    HELD, KEY, LANE, NOT_AS_ROOT, SIDECAR_ID, _a_lane_with_trees, _lines, _modes)

pytestmark = [
    WINDOWS_SKIP,
    pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                       reason="the lane tooling is bash over git"),
]

#: The lane's unread marker row, keyed as `lanes-index` keys it.
MARKER = f"{LANE}:{US}unread"
#: The path of the lane's tree, as a record may name it WITHOUT being absolute.
RELATIVE = f"nowhere/{LANE}/w"
#: Two more records of one lane, for the case that holds more than one.
SECOND = f"c1-second-{LANE}"
THIRD = f"c2-third-{LANE}"


@pytest.fixture
def inv(tmp_path):
    """test_lanes_index's estate with an inventory, made here as it is there."""
    made = Inventory(tmp_path / "i")
    yield made
    made.close()


def _whole_record(**changes: str | None) -> str:
    """The WHOLE record `_sidecar` writes for the lane's one tree, field by
    field, with `changes` applied: a value replaces the field's, `None` leaves
    the line out. A value of `""` is `key: ` with nothing after it."""
    fields: dict[str, str | None] = {
        "schema": "1", "lane": LANE, "tree": SIDECAR_ID, "path": f"/nowhere/{LANE}/w",
        "checkout": "unknown", "branch": f"feat/{LANE}", "head": HEADS[LANE],
        "upstream": "none", "dirty": "0", "unpushed": "0", "writer": "none",
        "generation": "0", "operation": "none", "observed": "2026-10-04T00:00:00Z"}
    fields.update(changes)
    return "".join(f"{key}: {value}\n" for key, value in fields.items() if value is not None)


class Shape(NamedTuple):
    """One record shape, and what the helper makes of it at `3e97ae5`."""
    text: str          # the record, as the shape has it
    row_path: str      # what the listing's TREE row carries where the path would be
    branch: str        # the row's branch
    trees_path: str    # `lane-trees`' second field for it
    trees_schema: str  # `lane-trees`' last field for it


#: The four shapes of the issue first, then the two its rule reaches. Every
#: value here was read off `lanes-edit.sh worktrees --all` and `lane-trees` at
#: `3e97ae5`, in a sandbox estate, before this was written.
SHAPES = {
    "no-path-line": Shape(_whole_record(path=None), SIDECAR_ID, "malformed sidecar", "",
                          "<malformed>"),
    "empty-path": Shape(_whole_record(path=""), SIDECAR_ID, "malformed sidecar", "",
                        "<malformed>"),
    "schema-2-no-path": Shape(_whole_record(schema="2", path=None), SIDECAR_ID,
                              "unknown schema 2", "", "2"),
    "relative-path": Shape(_whole_record(path=RELATIVE), RELATIVE, "malformed sidecar",
                           RELATIVE, "<malformed>"),
    "schema-2-relative-path": Shape(_whole_record(schema="2", path=RELATIVE), RELATIVE,
                                    "unknown schema 2", RELATIVE, "2"),
    "empty-file": Shape("", SIDECAR_ID, "unknown schema <none>", "", "<none>"),
}


def _unreadable(root: Path, ids: str) -> str:
    """#291's part F, as it gave it: the clause for a record that could not be
    read. Its words are F's, and a control below pins them."""
    return f"these records under {root}/trees could not be read: {ids}"


def _no_absolute_path(root: Path, ids: str) -> str:
    """#302's clause for a record that WAS read and names no absolute path -
    none, an empty one, or one that is relative. The design's wording, and the
    one place it is written in this file."""
    return (f"these records under {root}/trees were read and name no absolute path, so "
            f"the tree each stands for is not known: {ids}")


def _a_lane_with_a_whole_record(inv: Inventory, env: dict) -> tuple[Path, Path, dict]:
    """`(control root, the lane's one record, the index's rows)` for repoB-1 with
    one whole record, after a first sync that wrote every row and held none."""
    root = _a_lane_with_trees(inv, inv.root / "elsewhere", env)
    record = root / "trees" / f"{SIDECAR_ID}.yaml"
    assert record.read_text(encoding="utf-8") == _whole_record(), \
        "the builder here no longer writes what `_sidecar` writes"
    rows = inv.rows()
    assert KEY in rows and MARKER not in rows, sorted(rows)
    return root, record, rows


def _held(said: str) -> str:
    """The line a sync prints for a lane its helper's `UNREAD` line holds."""
    return f"{HELD}its inventory could not be read ({said})"


ENV = {"LANES_LANE_STATE_ROOT": None}


@pytest.mark.parametrize("shape", list(SHAPES), ids=list(SHAPES))
def test_a_tree_record_that_names_no_absolute_path_holds_its_lanes_rows(inv, shape):
    """THE TREE'S ROW IS NOT THE ROW OF ITS RECORD'S ID (#302). A record that is
    read and names no absolute path is listed as a row keyed by its id (or by its
    relative text), which a sync took for a tree the lane never had: it wrote
    that row and REMOVED the tree's own. The listing now says the lane is
    `UNREAD` beside the record's row - in words that say the record WAS read,
    and why that is not enough - so the sync holds the lane's rows, removes
    nothing, writes only the lane's marker, and says why. The record's row
    stays in the listing, for a person to read. Put right, the next sync takes
    the marker away and nothing else."""
    s = SHAPES[shape]
    root, record, before = _a_lane_with_a_whole_record(inv, ENV)
    said = _no_absolute_path(root, SIDECAR_ID)
    record.write_text(s.text, encoding="utf-8")

    res = inv.sync(env=ENV)
    assert res.returncode == 0, (res.stdout, res.stderr)
    after = inv.rows()
    assert after.get(KEY) == before[KEY], (
        "the tree's row was not kept as the first sync left it", res.stdout, sorted(after))
    assert f"{LANE}:{s.row_path}" not in after, (
        "a row keyed by the record's id (or its relative path) was written",
        res.stdout, sorted(after))
    assert " 0 removed" in res.stdout, res.stdout
    assert _held(said) in res.stdout, res.stdout
    assert set(before) <= set(after) and set(after) - set(before) == {MARKER}, (
        "the lane's marker is the one row written", res.stdout, sorted(after))

    listed = inv.e.edit("worktrees", "--all", env=ENV)
    assert listed.returncode == 0, (listed.returncode, listed.stdout, listed.stderr)
    assert _lines(listed.stdout, "UNREAD", LANE) == [["UNREAD", "Eagle", LANE, said]], \
        listed.stdout
    tree = _lines(listed.stdout, "TREE", LANE)
    assert len(tree) == 1 and (tree[0][4], tree[0][5]) == (s.row_path, s.branch), listed.stdout
    assert _lines(listed.stdout, "PARTIAL") == [], listed.stdout  # the listing did name the lane

    record.write_text(_whole_record(), encoding="utf-8")
    healed = inv.sync(env=ENV)
    assert healed.returncode == 0, (healed.stdout, healed.stderr)
    assert "0 upserted, 1 removed" in healed.stdout, healed.stdout
    assert "kept as they are" not in healed.stdout, healed.stdout
    assert inv.rows() == before, (healed.stdout, sorted(inv.rows()))


def test_the_reads_beside_a_record_that_names_no_absolute_path_say_not_read(inv):
    """A PERSON READING THE LISTINGS SEES WHAT THE SYNC KEPT (#302). `lanes
    --worktrees <lane>`, the sidecars' own read, lists the record's row and says
    the inventory was NOT READ, and why. After the sync, `lanes --index
    --worktrees <lane>` says the same and shows the tree's row as the first sync
    left it - its real path and branch - and not one keyed by the record's id.
    `lane-trees` is not touched: it keeps its exit-0 `<malformed>` row, which the
    handoff reads per record (#255)."""
    s = SHAPES["no-path-line"]
    root, record, before = _a_lane_with_a_whole_record(inv, ENV)
    said = _no_absolute_path(root, SIDECAR_ID)
    record.write_text(s.text, encoding="utf-8")

    named = _wt(inv, LANE, env=ENV)
    assert named.returncode == 0, (named.returncode, named.stdout, named.stderr)
    assert f"inventory NOT READ: {said}" in named.stdout, named.stdout
    assert "malformed sidecar" in named.stdout, named.stdout  # the record's row stays
    assert "1 worktree(s) in 1 lane(s) on 1 workstation(s)" in named.stdout, named.stdout

    res = inv.sync(env=ENV)
    assert res.returncode == 0, (res.stdout, res.stderr)
    idx = _wt(inv, LANE, "--index", env=ENV)
    assert idx.returncode == 0, (idx.returncode, idx.stdout, idx.stderr)
    assert "read: index (sqlite)" in idx.stderr, idx.stderr
    assert f"inventory NOT READ: {said} - the 1 row(s) listed for it are kept from the last " \
        f"sync that read it" in idx.stdout, idx.stdout
    kept = [line for line in idx.stdout.splitlines()
            if line.startswith("Eagle") and line.endswith(f"/nowhere/{LANE}/w")]
    assert len(kept) == 1 and f"feat/{LANE}" in kept[0], idx.stdout
    assert "1 worktree(s) in 1 lane(s) on 1 workstation(s)" in idx.stdout, idx.stdout
    assert "malformed sidecar" not in idx.stdout, idx.stdout

    trees = inv.e.edit("lane-trees", LANE, env=ENV)
    assert trees.returncode == 0, (trees.returncode, trees.stdout, trees.stderr)
    rows = [line.split(US) for line in trees.stdout.splitlines()]
    assert len(rows) == 1 and rows[0][0] == SIDECAR_ID and rows[0][1] == s.trees_path \
        and rows[0][12] == s.trees_schema, trees.stdout


def test_a_reconcile_beside_a_record_that_names_no_absolute_path_keeps_the_trees_row(inv):
    """THE OTHER ACT THAT REMOVES ROWS HOLDS THE LANE TOO (#302). `reconcile
    --source inventory` takes the source as it now stands, and a lane whose
    inventory could not be read keeps its rows in either act: a read that did
    not make an answer is never one. It swapped the tree's row for the record's
    id-keyed row, as a sync did, and the marker is now the one row it writes."""
    s = SHAPES["no-path-line"]
    root, record, before = _a_lane_with_a_whole_record(inv, ENV)
    said = _no_absolute_path(root, SIDECAR_ID)
    record.write_text(s.text, encoding="utf-8")

    res = inv.e.index("reconcile", "--source", "inventory", env=ENV)
    assert res.returncode == 0, (res.stdout, res.stderr)
    after = inv.rows()
    assert after.get(KEY) == before[KEY], (
        "the tree's row was not kept as the first sync left it", res.stdout, sorted(after))
    assert f"{LANE}:{s.row_path}" not in after, (res.stdout, sorted(after))
    assert re.search(r"worktrees\s+\d+ kept\s+1 upserted\s+0 removed", res.stdout), res.stdout
    assert _held(said) in res.stdout, res.stdout
    assert set(before) <= set(after) and set(after) - set(before) == {MARKER}, sorted(after)


@NOT_AS_ROOT
def test_an_unreadable_record_and_one_with_no_absolute_path_are_one_unread_line(inv):
    """ONE LANE, ONE `UNREAD` LINE, AND EVERY OFFENDING RECORD IN IT (#302). The
    indexer keeps one reason per lane - a later `UNREAD` line for the same lane
    replaces the earlier one - so a lane holding a record that could not be read
    and one that names no absolute path says both in its one line: part F's
    clause first, as it gave it, then the new one, and the lane's whole record
    named in neither. All three records' rows are kept."""
    root, record, _ = _a_lane_with_a_whole_record(inv, ENV)
    for tid, path in ((SECOND, f"/nowhere/{LANE}/w2"), (THIRD, f"/nowhere/{LANE}/w3")):
        (root / "trees" / f"{tid}.yaml").write_text(
            _whole_record(tree=tid, path=path), encoding="utf-8")
    first = inv.sync(env=ENV)
    assert first.returncode == 0 and "kept as they are" not in first.stdout, first.stdout
    before = inv.rows()
    assert {KEY, f"{LANE}:/nowhere/{LANE}/w2", f"{LANE}:/nowhere/{LANE}/w3"} <= set(before)
    said = f"{_unreadable(root, SECOND)}; {_no_absolute_path(root, SIDECAR_ID)}"
    record.write_text(SHAPES["no-path-line"].text, encoding="utf-8")

    with _modes([(root / "trees" / f"{SECOND}.yaml", 0o000)]):
        res = inv.sync(env=ENV)
        assert res.returncode == 0, (res.stdout, res.stderr)
        after = inv.rows()
        assert {k: after.get(k) for k in before} == before, (res.stdout, sorted(after))
        assert " 0 removed" in res.stdout, res.stdout
        assert _held(said) in res.stdout, res.stdout
        assert set(after) - set(before) == {MARKER}, sorted(after)
        listed = inv.e.edit("worktrees", "--all", env=ENV)
        assert listed.returncode == 0, (listed.returncode, listed.stdout, listed.stderr)
        assert _lines(listed.stdout, "UNREAD", LANE) == [["UNREAD", "Eagle", LANE, said]], \
            listed.stdout
        assert len(_lines(listed.stdout, "TREE", LANE)) == 3, listed.stdout


# --- the controls: what holds at 3e97ae5 and must hold after the fix --------------


def test_a_whole_record_is_still_upserted_in_place_and_holds_nothing(inv):
    """A WHOLE RECORD IS A READ, AND ITS ROW FOLLOWS IT (control). The fix must
    not hold a lane over a record that names its path: a changed count is one
    upsert at the same key, no removal, no `UNREAD` line and no held lane."""
    root, record, before = _a_lane_with_a_whole_record(inv, ENV)
    record.write_text(_whole_record(dirty="2"), encoding="utf-8")

    res = inv.sync(env=ENV)
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert "1 upserted, 0 removed" in res.stdout, res.stdout
    assert "kept as they are" not in res.stdout, res.stdout
    after = inv.rows()
    assert set(after) == set(before) and after[KEY]["dirty_count"] == 2, (res.stdout, sorted(after))
    listed = inv.e.edit("worktrees", "--all", env=ENV)
    assert listed.returncode == 0, listed.stderr
    assert _lines(listed.stdout, "UNREAD", LANE) == [], listed.stdout
    tree = _lines(listed.stdout, "TREE", LANE)
    assert len(tree) == 1 and tree[0][4] == f"/nowhere/{LANE}/w", listed.stdout


KEEPS_ITS_KEY = {
    # not whole (no `upstream:`), and the path it names is absolute
    "malformed-absolute-path": (_whole_record(upstream=None), "malformed sidecar"),
    # of a schema the helper does not write, and the path it names is absolute
    "schema-2-absolute-path": (_whole_record(schema="2"), "unknown schema 2"),
}


@pytest.mark.parametrize("shape", list(KEEPS_ITS_KEY), ids=list(KEEPS_ITS_KEY))
def test_a_record_that_names_an_absolute_path_keeps_its_key_and_holds_nothing(inv, shape):
    """A RECORD THAT KEEPS ITS KEY IS REWRITTEN IN PLACE (control, the issue's
    own line: "a malformed record with an absolute path keeps its key, and its
    row is rewritten in place"). Its row is the tree's row - the same key - so no
    row is lost to a different one: the sync upserts it as the record now reads
    (`malformed sidecar` or `unknown schema 2`, counts empty), removes nothing,
    and holds no lane. Whether such a record should hold its lane too, so that
    the last whole observation stays, is a ruling for lane 3 and Brett Heap; it
    is not what #302's design does."""
    text, branch = KEEPS_ITS_KEY[shape]
    root, record, before = _a_lane_with_a_whole_record(inv, ENV)
    record.write_text(text, encoding="utf-8")

    res = inv.sync(env=ENV)
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert "1 upserted, 0 removed" in res.stdout, res.stdout
    assert "kept as they are" not in res.stdout, res.stdout
    after = inv.rows()
    assert set(after) == set(before), (res.stdout, sorted(after))
    assert (after[KEY]["path"], after[KEY]["branch"]) == (f"/nowhere/{LANE}/w", branch), after[KEY]
    assert after[KEY]["dirty_count"] is None, after[KEY]
    listed = inv.e.edit("worktrees", "--all", env=ENV)
    assert listed.returncode == 0, listed.stderr
    assert _lines(listed.stdout, "UNREAD", LANE) == [], listed.stdout
    assert _lines(listed.stdout, "PARTIAL") == [], listed.stdout


@NOT_AS_ROOT
def test_an_unreadable_record_keeps_part_fs_words(inv):
    """PART F IS NOT REWORDED (control). A record that could not be read is held
    in the words #291 gave it, whatever the fix does for a record that was read:
    its own clause, exactly, the lane held, the tree's row kept, and the record's
    row listed beside it as `unreadable sidecar` (test_unsearchable_control_
    root_291 has the same case; this one pins the line the new clause joins)."""
    root, record, before = _a_lane_with_a_whole_record(inv, ENV)
    said = _unreadable(root, SIDECAR_ID)

    with _modes([(record, 0o000)]):
        res = inv.sync(env=ENV)
        assert res.returncode == 0, (res.stdout, res.stderr)
        after = inv.rows()
        assert after.get(KEY) == before[KEY], (res.stdout, sorted(after))
        assert f"{LANE}:{SIDECAR_ID}" not in after, sorted(after)
        assert " 0 removed" in res.stdout, res.stdout
        assert _held(said) in res.stdout, res.stdout
        listed = inv.e.edit("worktrees", "--all", env=ENV)
        assert listed.returncode == 0, listed.stderr
        assert _lines(listed.stdout, "UNREAD", LANE) == [["UNREAD", "Eagle", LANE, said]], \
            listed.stdout
        tree = _lines(listed.stdout, "TREE", LANE)
        assert len(tree) == 1 and (tree[0][4], tree[0][5]) == (SIDECAR_ID, "unreadable sidecar"), \
            listed.stdout
