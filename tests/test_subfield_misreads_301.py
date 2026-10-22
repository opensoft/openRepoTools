# SPDX-License-Identifier: Apache-2.0
r"""A stored lane sub-field is read back as it was written (#301).

A lane's `dir` and a handoff request's `by host` are sub-fields of an event's
payload, and three reads of them give back something the log does not hold.

1. A TAB IN A RECORDED `dir`. `lanes_rows` prints the dir into the listing's
   TAB-separated row, seventeen columns, and every reader of that row splits it
   on TAB. A TAB inside the dir is one more separator, so every column after
   the dir arrives one place early. `worktree_rows` takes its `dir` from that
   row, so the lane's root is worked out from the cut value and the lane leaves
   `worktrees --all` and the inventory index in silence (no `UNREAD`, no
   `PARTIAL`, 8 from `worktrees <lane>`) while the named `lane-trees <lane>`
   still lists the trees. The `lanes` command renders the same shifted row: the
   AGE column holds the objects, the DIRECTORY is cut at the TAB, and the fork
   count is the lane's home, which prints a DEFECT line for a fork nobody ran.
   `lane-start` does not refuse a TAB in a dir.

2. BACKSLASH ESCAPES. `payload_subfield` passes the payload through `awk -v`,
   which processes its value as a string literal: a `dir` that holds a
   backslash and a `t` reads back holding a real TAB, `\\` as one backslash,
   `\n` as a newline that splits the answer in two, `\101` as `A`. So
   `lane-dir` answers a path that does not exist, and `lane_control_root`
   places the lane's snapshot and trees by it: under `$PROJECTS_ROOT` where
   the expanded path's parent is not a directory, and in some OTHER directory
   where it is. The listing's own pass over the log reads from stdin and does
   not expand, so its column 7 still holds the dir as it was written, and
   `worktrees --all` agrees with the writers by making the same wrong pass.

3. `by host`. `request-handoff` writes the requester's host into its `by host`
   sub-field unquoted, and the one reader (the bound session's prompt guard)
   takes a single ref, up to the first space: a host that holds a space comes
   back cut at it, in the note the session is shown and in the
   `/handoff --exit requested by ...` line typed into its pane. Nothing fences
   the host: `write_event` checks the sub-fields named `host`, `os` and
   `container`, and `by host` is none of them.

WHAT WAS RED AT `e0970a8`, WHERE THIS BRANCH BEGAN, AND WHAT WAS NOT. The cases
that name the three defects failed; the control cases (an ordinary dir, a dir
with a space, a host with none) passed before the fix and have to keep passing,
and so does `test_the_worktree_listing_keeps_every_lanes_trees` for the lanes
whose dir holds a backslash: it passed then only because the listing and the
writers were wrong in the same way, and a fix of the writers' read that left
the listing's alone would lose those lanes in `worktrees --all`.

THE FIX, ONE ITEM AT A TIME.

1. COLUMN 7 IS ESCAPED (lane 3's ruling 1, option C). `lanes_rows` writes the
   dir the way `lane-worktrees`' porcelain `pesc` writes a field (a backslash
   as `\\`, a TAB as `\t`, a newline as `\n`, a carriage return as `\r`), at the
   print and only where the dir holds one of them, and every reader that
   shows the dir or takes it for a path decodes it: `worktree_rows`, `lane`'s
   `split_row` and the `lanes` renderer. The row keeps its seventeen columns
   whatever the dir holds, and `lane` reaches the dir the log records.

3. THE ASKING HOST IS FENCED (lane 3's ruling 2, R). `request-handoff` refuses,
   with 2 and "Nothing was written", a host `lanes_binding_value_ok` rejects -
   the fence `binding_subfields_add` holds the binding's own host to - before
   either of the two lines that carry one is planned or written: the request's
   `by host <h>` and the forced release's `forced by <uuid>@<h>/<container>`.
   The refusal names `LANES_HOST`, where the value came from or what overrides
   it.

THE `by host` CASES ASK WHAT A READER GETS BACK, NOT HOW THE LINE IS SPELLED.
Whether the writer quoted a host that holds a space (the grammar's own rule for
a `dir` or a `profile`) or refused or dropped it was Brett Heap's and lane 3's
to rule; that case holds every spelling that reads back whole, or is not read
back as something else, and fails the one that reads back cut. Lane 3 ruled R,
the refusal, and `test_a_host_the_binding_fence_refuses_is_never_written` holds
it on both paths that write a host.

EVERY CASE RUNS WITHOUT `LANES_LANE_STATE_ROOT`, the suite's usual seam for the
control root: it answers before any payload is read, so with it set the
defects in the first two items cannot be seen at all.
"""

from __future__ import annotations

import os
import random
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

import test_lanes_index
from conftest import REPO
from test_lanes_index import LANES, Estate, _row

pytestmark = test_lanes_index.pytestmark
US = "\x1f"
TAB = "\t"
#: A TREE row's columns, as `worktree_rows` documents them.
TREE_COLS = ["kind", "workstation", "lane", "owner", "path", "branch", "base", "lifecycle",
             "generation", "operation", "writer_live", "last_seen_utc", "last_commit",
             "dirty", "unpushed", "provenance"]

#: ONE CASE PER RECORDED `dir`: (lane, the parent the dir sits in, below the
#: estate's root, the dir's own name). The parent is a real directory, so the
#: control root the recorded dir places is `<parent>/.lane-state/<lane>`, and
#: that is where the writers have to file the lane. A backslash below is a
#: backslash in the file name: `\t` is two characters, not a TAB.
CASES = {
    "plain": ("repoP-1", "plain", "repoP"),
    "space": ("repoS-1", "My Projects", "repoS"),
    "tab": ("repoT-1", "work/a\tb", "repoT"),
    "bs-t": ("repoB-1", "work2/back\\tslash", "repoB"),
    "bs-bs": ("repoD-1", "work3/dbl\\\\slash", "repoD"),
    "bs-n": ("repoN-1", "work4/new\\nline", "repoN"),
    "bs-octal": ("repoO-1", "work5/oct\\101x", "repoO"),
}
BACKSLASH = [k for k in CASES if k.startswith("bs-")]


def _started(lane: str, uuid: str, dir_field: str) -> str:
    """The lane's STARTED line, its `dir` sub-field spelled as the caller gives it."""
    return (f"STARTED — lane {lane}, session {uuid}@Eagle, 2026-10-01T00:40:00Z, "
            f"lane:{lane} → home opensoft/{lane[:-2]}; dir {dir_field}; profile team-02a\n")


class Misread:
    """test_lanes_index's Estate with one lane for each of CASES, started by a
    log line that records its dir as `lane-start` would spell it (quoted where
    it holds a space, bare where it does not) and given its snapshot and one
    tree by the two writers, `set-lane-state` and `set-lane-tree`, which find
    the lane's root from its log. `PROJECTS_ROOT` is the estate's own
    `<home>/projects`, so a lane the writers could not place by its dir is
    filed under `<home>/projects/.lane-state/<lane>`.

    `bs-octal` has a sibling, `octAx`, where `awk -v` expands the name of its
    parent to: a read that expands `\\101` places that lane in a directory
    that is somebody else's.

    Each recorded dir is a real directory too, as a lane's checkout is, so
    `lane <name>` can be asked to reach it."""

    def __init__(self, root: Path):
        self.root = root
        self.e = Estate(root / "e")
        assert "LANES_LANE_STATE_ROOT" not in self.e.env
        self.lane: dict[str, str] = {}
        self.dir: dict[str, str] = {}
        self.parent: dict[str, Path] = {}
        self.tree: dict[str, str] = {}
        log = self.e.wip / "lanes" / "log"
        for n, (cid, (lane, parent_rel, leaf)) in enumerate(CASES.items(), 1):
            parent = root / parent_rel
            parent.mkdir(parents=True)
            recorded = f"{parent}/{leaf}"
            Path(recorded).mkdir()
            field = f'"{recorded}"' if " " in recorded else recorded
            uuid = f"66666666-{n:04d}-4000-8000-00000000{6000 + n}"
            (log / f"{lane}.md").write_text(_started(lane, uuid, field), encoding="utf-8")
            self.lane[cid], self.dir[cid], self.parent[cid] = lane, recorded, parent
            self.tree[cid] = f"/nowhere/{lane}/w"
        (root / "work5" / "octAx").mkdir()
        self.e._git("add", "-A")
        self.e._git("commit", "-q", "-m", "one lane for each recorded dir")
        self.e._git("push", "-q", "origin", "main")
        for cid, lane in self.lane.items():
            self.ok("set-lane-state", lane, "RUNNING", "--operation", f"op-test-{lane}")
            self.ok("set-lane-tree", lane, self.tree[cid], "--checkout", "/nowhere",
                    "--branch", f"feat/{lane}", "--head", "7" * 40, "--upstream", "none",
                    "--dirty", "0", "--unpushed", "0")
        self._listing: dict[str, list[str]] | None = None
        self._worktrees: tuple | None = None
        self._lanes: subprocess.CompletedProcess | None = None

    def ok(self, *args: str) -> subprocess.CompletedProcess:
        res = self.e.edit(*args)
        assert res.returncode == 0, (args, res.stdout, res.stderr)
        return res

    def listing(self) -> dict[str, list[str]]:
        """`lanes --all` as the rows it prints, each split on TAB as every
        reader of the row splits it, by the lane in its first column. The
        lines are split on a newline and nothing else: `str.splitlines()` also
        ends a line at 0x1c-0x1e, which a recorded dir can hold, and a row cut
        there would read as two rows of the wrong shape (#301 review, 507)."""
        if self._listing is None:
            res = self.ok("lanes", "--all")
            self._listing = {line.split(TAB)[0]: line.split(TAB)
                             for line in res.stdout.split("\n") if line}
        return self._listing

    def worktrees(self, *args: str) -> tuple[subprocess.CompletedProcess, list, list]:
        """`lanes-edit.sh worktrees <args>`: the answer, its TREE rows as
        dicts, and every other line it printed (`UNREAD`, `PARTIAL`)."""
        res = self.e.edit("worktrees", *args)
        lines = [line for line in res.stdout.split("\n") if line]
        rows = [dict(zip(TREE_COLS, line.split(US))) for line in lines
                if line.startswith("TREE" + US)]
        other = [line for line in lines if not line.startswith("TREE" + US)]
        return res, rows, other

    def lanes_command(self) -> subprocess.CompletedProcess:
        """The `lanes` command's `--all`, the listing a person reads, run once."""
        if self._lanes is None:
            self._lanes = self.e.run("bash", LANES, "--all")
        return self._lanes

    def all_trees(self) -> tuple[subprocess.CompletedProcess, list, list]:
        if self._worktrees is None:
            self._worktrees = self.worktrees("--all")
        return self._worktrees

    def want_row(self, cid: str) -> tuple:
        lane = self.lane[cid]
        return (lane, "legacy", self.tree[cid], f"feat/{lane}", "RUNNING", "1",
                f"op-test-{lane}")

    def filed(self, lane: str) -> list[str]:
        """Every `<...>/<lane>/lane-state.yaml` in the estate, as paths below
        its root: where the writers filed the lane's snapshot."""
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("lane-state.yaml")
                      if p.parent.name == lane)


def _of(rows: list, lane: str) -> list:
    return [(r["lane"], r["owner"], r["path"], r["branch"], r["lifecycle"], r["generation"],
             r["operation"]) for r in rows if r["lane"] == lane]


def _shown(text: str) -> str:
    """An answer with its unit separators and TABs made visible, for a failure message."""
    return text.replace(US, " | ").replace(TAB, "<TAB>")


@pytest.fixture(scope="module")
def misread(tmp_path_factory):
    return Misread(tmp_path_factory.mktemp("subfield-misreads-301"))


# ------------------------------------------------------------ the preconditions


def test_the_writers_file_a_lane_with_a_tab_in_its_dir_beside_its_checkout(misread):
    """THE PRECONDITION OF ITEM 1, which holds before the fix and after it: the
    named reads take the dir whole (a TAB is not what `awk -v` expands, and the
    named reads never meet the listing's row), so `lane-dir` answers it,
    `set-lane-state` and `set-lane-tree` filed repoT-1 under
    `<root>/work/a<TAB>b/.lane-state/repoT-1`, and the named `lane-trees` lists
    the tree. Nothing is under `<home>/projects/.lane-state`, the root the
    listing works out from the dir cut at its TAB, where the lane is not."""
    lane = misread.lane["tab"]
    assert misread.ok("lane-dir", lane).stdout == misread.dir["tab"] + "\n"
    snapshot = misread.parent["tab"] / ".lane-state" / lane / "lane-state.yaml"
    assert snapshot.is_file(), misread.filed(lane)
    assert len(list((snapshot.parent / "trees").glob("*.yaml"))) == 1
    named = misread.ok("lane-trees", lane)
    assert [line.split(US)[1] for line in named.stdout.splitlines() if line] \
        == [misread.tree["tab"]], _shown(named.stdout)


# ------------------------------------------------------ item 1: a TAB in a dir


@pytest.mark.parametrize("cid", list(CASES))
def test_a_row_of_the_lane_listing_keeps_its_seventeen_columns(misread, cid):
    """THE ROW IS SEVENTEEN COLUMNS WHATEVER ITS CELLS HOLD, because its readers
    (`worktree_rows`, `lanes`, `lane`, `lane-end`, `lane_groups`) split it on
    TAB and take each column by its place: 13 is the locality, 14 the class.
    The dir is column 7. A dir that holds a TAB printed a row of eighteen,
    and the fork count, the locality and the class were each read one place
    early. Every other dir, the ones with a space or a backslash included,
    prints seventeen, and this holds that they still do."""
    lane = misread.lane[cid]
    row = misread.listing().get(lane)
    assert row is not None, sorted(misread.listing())
    assert len(row) == 17, f"{len(row)} columns: " + _shown("|".join(row))
    assert row[12] in {"here", "elsewhere", "none"}, ("column 13", row[12])
    assert row[13] in {"closed", "dormant", "none"}, ("column 14", row[13])


def test_the_lanes_command_prints_no_defect_for_a_dir_with_a_tab(misread):
    """THE `lanes` COMMAND RENDERS THE SAME ROW. With the dir's TAB read as a
    separator the fork count (column 12) was the lane's home, `opensoft/repoT`,
    which is not 0, so the listing printed `DEFECT: opensoft/repoT live
    fork(s) of this lane transcript` under a lane nobody had forked, and its
    AGE column held the objects it holds. No lane in this estate has a fork."""
    res = misread.lanes_command()
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert "repoT-1" in res.stdout, res.stdout
    assert "DEFECT" not in res.stdout, "\n".join(
        line for line in res.stdout.splitlines() if "DEFECT" in line or "repoT-1" in line)


def _pesc(value: str) -> str:
    """`lane-worktrees`' porcelain escape, `pesc`, which column 7 is written in:
    a backslash as `\\\\`, a TAB as `\\t`, a newline as `\\n`, a carriage
    return as `\\r`."""
    return (value.replace("\\", "\\\\").replace("\t", "\\t")
            .replace("\n", "\\n").replace("\r", "\\r"))


@pytest.mark.parametrize("cid", list(CASES))
def test_column_seven_is_the_recorded_dir_escaped_as_pesc_escapes_a_field(misread, cid):
    """COLUMN 7'S BYTES (lane 3's review of #301, 501). The dir is written into
    the row the way `lane-worktrees`' porcelain writes a field, so a TAB in it
    is `\\t` and no separator, and a backslash is `\\\\` so that a dir that
    really holds `\\t` is not decoded as a TAB. A dir holding none of the
    four is the dir as it was, which the plain and space cases hold. Before the
    fix the TAB cut the column, and a backslash went out undoubled."""
    lane = misread.lane[cid]
    row = misread.listing().get(lane)
    assert row is not None, sorted(misread.listing())
    assert len(row) == 17, f"{len(row)} columns: " + _shown("|".join(row))
    assert row[6] == _pesc(misread.dir[cid]), \
        f"column 7 is {row[6]!r}; the dir {misread.dir[cid]!r} escaped is {_pesc(misread.dir[cid])!r}"


@pytest.mark.parametrize("cid", list(CASES))
def test_the_lanes_command_shows_each_dir_as_it_was_recorded(misread, cid):
    """The `lanes` command decodes column 7 before it shows it: its DIRECTORY
    is the dir the log records, byte for byte. Before the fix the lane whose
    dir holds a TAB showed it cut at the TAB; decoded nowhere, a backslash
    lane would show its backslashes doubled."""
    res = misread.lanes_command()
    assert res.returncode == 0, (res.stdout, res.stderr)
    lane = misread.lane[cid]
    lines = [line for line in res.stdout.split("\n") if line.startswith(lane + " ")]
    assert len(lines) == 1, lines
    assert lines[0].endswith(" " + misread.dir[cid]), \
        f"{_shown(lines[0])!r} does not end with {_shown(misread.dir[cid])!r}"


@pytest.mark.parametrize("cid", list(CASES))
def test_lane_reaches_each_lanes_recorded_dir(misread, cid):
    """`lane <name>` decodes column 7 in `split_row`, so `go_available` tests
    and enters the directory the log records (#301, lane 3's ruling 1). Before
    the fix the lane whose dir holds a TAB was refused as "does not exist", for
    the dir cut at the TAB; decoded nowhere, every backslash lane would be. A
    dry run prints the act and launches nothing."""
    lane = misread.lane[cid]
    res = misread.e.run("bash", REPO / "lane", lane, "--dry-run",
                        env={"PCLAUDE": shutil.which("true") or "/bin/true"})
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    first = res.stdout.split("\n", 1)[0]
    assert first == f"lane {lane} · dir {misread.dir[cid]} · profile team-02a · from the lane record", \
        _shown(res.stdout)


@pytest.mark.parametrize("cid", list(CASES))
def test_the_worktree_listing_keeps_every_lanes_trees(misread, cid):
    """`worktrees --all` lists the tree the writers filed for each lane, with the
    lifecycle its snapshot holds, and says nothing else about it. Before the
    fix the lane whose dir holds a TAB had no row (and no `UNREAD` or `PARTIAL`
    line either), beside every other lane's.

    FOR THE BACKSLASH LANES THIS PASSES TODAY, and has to go on passing: the
    writers file them by the dir `awk -v` expanded, and the listing finds them
    by the same expansion. Once the writers' read is exact, the listing must be
    exact with it, or those lanes are lost here instead."""
    res, rows, other = misread.all_trees()
    assert res.returncode == 0, res.stderr
    lane = misread.lane[cid]
    assert _of(rows, lane) == [misread.want_row(cid)], _shown(res.stdout)
    assert [line for line in other if lane in line] == [], other


@pytest.mark.parametrize("cid", list(CASES))
def test_a_named_worktree_read_finds_every_lanes_trees(misread, cid):
    """The named read, `worktrees <lane>`, finds the same row (exit 0). It said
    8, "no trees", for the lane whose dir holds a TAB: the listing it asks for
    the lane's row is the same row, cut at the same place."""
    res, rows, other = misread.worktrees(misread.lane[cid])
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert _of(rows, misread.lane[cid]) == [misread.want_row(cid)], _shown(res.stdout)
    assert other == [], other


def test_the_inventory_index_keeps_every_lanes_trees(misread):
    """`lanes-index sync --source inventory` copies the `worktrees --all`
    listing, so the index holds one tree for each lane. Before the fix it held
    six: the lane whose dir holds a TAB was not in it."""
    res = misread.e.index("sync", "--source", "inventory")
    assert res.returncode == 0, (res.stdout, res.stderr)
    conn = sqlite3.connect(str(misread.e.sqlite))
    conn.row_factory = sqlite3.Row
    rows = {r["record_id"]: dict(r) for r in conn.execute(
        "SELECT * FROM worktrees WHERE source = 'inventory:Eagle'")}
    conn.close()
    ours = {k for k in rows if k.split(":", 1)[0] in set(misread.lane.values())}
    want = {f"{misread.lane[cid]}:{misread.tree[cid]}" for cid in CASES}
    assert ours == want, sorted(want - ours)


# ---------------------------------------------------- item 2: backslash escapes


@pytest.mark.parametrize("cid", list(CASES))
def test_lane_dir_answers_the_recorded_path_as_recorded(misread, cid):
    """`lane-dir` answers the `dir` its log holds, byte for byte. `payload_subfield`
    handed the payload to `awk -v`, which processes it as a string literal:
    `back\\tslash` came back holding a TAB, `dbl\\\\slash` holding one backslash,
    `new\\nline` as two lines, `oct\\101x` as `octAx`: a path that does not
    exist, or somebody else's. The controls, a dir with a space and one with a
    real TAB in it, were read whole before the fix."""
    res = misread.e.edit("lane-dir", misread.lane[cid])
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert res.stdout == misread.dir[cid] + "\n", \
        f"recorded {misread.dir[cid]!r}, answered {res.stdout!r}"


@pytest.mark.parametrize("cid", list(CASES))
def test_the_writers_file_a_lane_beside_its_recorded_dir(misread, cid):
    """`set-lane-state` and `set-lane-tree` file a lane's snapshot and trees
    under `<parent of its dir>/.lane-state/<lane>`, the parent being the one
    its recorded dir names. For a dir that held a backslash escape they filed
    the lane under the parent of the EXPANDED path: `<home>/projects` where
    that is not a directory, and `work5/octAx`, a directory that belongs to
    nobody this lane knows, for `oct\\101x`. Where a lane is filed is where
    every later read looks for it, so this is the answer that moves, for a lane
    already on disk, when the read is made exact."""
    lane = misread.lane[cid]
    beside = misread.parent[cid] / ".lane-state" / lane / "lane-state.yaml"
    assert misread.filed(lane) == [str(beside.relative_to(misread.root))], \
        f"filed under {misread.filed(lane)}, its dir is {misread.dir[cid]!r}"
    assert len(list((beside.parent / "trees").glob("*.yaml"))) == 1
    if cid == "bs-octal":
        assert not (misread.root / "work5" / "octAx" / ".lane-state").exists(), \
            "the lane was filed in a directory that is not its own"


# ----------------------------------------------- `payload_subfield`, on its own


def _function(name: str, source: str = "lanes-edit.sh") -> str:
    """One top-level function of a shipped file (lanes-edit.sh unless named) as
    it is written there: the code that runs is the file's own, cut out and run
    in `bash`."""
    text = (REPO / source).read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(name)}\(\) \{{[^\n]*\n.*?^\}}\n", text, re.M | re.S)
    assert match, f"`{name}() {{` ... `}}` is no longer in {source}"
    return match.group(0)


def payload_subfield(payload: str, name: str, mode: str = "") -> str:
    """What `lanes-edit.sh`'s own `payload_subfield` gives for `name` in `payload`."""
    script = _function("payload_subfield") + '\npayload_subfield "$1" "$2" "$3"\n'
    res = subprocess.run(["bash", "-c", script, "bash", payload, name, mode],
                         capture_output=True, text=True, check=False,
                         env={"PATH": os.environ["PATH"]})
    assert res.returncode == 0, (payload, res.stderr)
    return res.stdout


#: (id, the stored payload, the sub-field asked for, what a reader gets back).
#: What a reader gets back is what was stored: its value, up to its first space
#: where it is bare, and the whole of it between its quotes where it is quoted.
#: A literal backslash is `\\` here, a real TAB is `\t`.
READS = [
    ("dir-plain", "home opensoft/repoP; dir /r/plain/repoP; profile team-02a",
     "dir", "/r/plain/repoP\n"),
    ("dir-quoted-space", 'home opensoft/repoS; dir "/r/My Projects/repoS"; profile p',
     "dir", "/r/My Projects/repoS\n"),
    ("dir-bare-quote-mark", 'dir /r/q"uote/repoQ; profile p', "dir", '/r/q"uote/repoQ\n'),
    ("dir-real-tab", "dir /r/a\tb/x; profile p", "dir", "/r/a\tb/x\n"),
    ("dir-backslash-t", "dir /r/a\\tb/x; profile p", "dir", "/r/a\\tb/x\n"),
    ("dir-two-backslashes", "dir /r/a\\\\b/x; profile p", "dir", "/r/a\\\\b/x\n"),
    ("dir-backslash-n", "dir /r/a\\nb/x; profile p", "dir", "/r/a\\nb/x\n"),
    ("dir-backslash-octal", "dir /r/a\\101b/x; profile p", "dir", "/r/a\\101b/x\n"),
    ("dir-backslash-hex", "dir /r/a\\x41b/x; profile p", "dir", "/r/a\\x41b/x\n"),
    ("dir-backslash-quote", 'dir /r/a\\"b/x; profile p', "dir", '/r/a\\"b/x\n'),
    ("dir-backslash-quoted-space", 'dir "/r/My Projects\\tx/y"; profile p',
     "dir", "/r/My Projects\\tx/y\n"),
    # `\/` and `\q` are not escapes to every awk: mawk keeps them, and the awk
    # of macOS and gawk do not. They pass today on this awk and must pass on
    # every one after the fix.
    ("dir-backslash-slash", "dir /r/a\\/b/x; profile p", "dir", "/r/a\\/b/x\n"),
    ("dir-backslash-other", "dir /r/a\\qb/x; profile p", "dir", "/r/a\\qb/x\n"),
    ("dir-trailing-backslash", "dir /r/trail\\", "dir", "/r/trail\\\n"),
    ("profile-backslash-t", "dir /r/x; profile a\\tb", "profile", "a\\tb\n"),
    ("by-host-bare", "by host plainhost; container none; window none; wait 0s",
     "by host", "plainhost\n"),
    ("by-host-quoted", 'by host "my host"; container none; window none; wait 0s',
     "by host", "my host\n"),
    ("by-host-backslash-t", "by host a\\tb; container none; window none; wait 0s",
     "by host", "a\\tb\n"),
]


@pytest.mark.parametrize("payload,name,want", [r[1:] for r in READS], ids=[r[0] for r in READS])
def test_payload_subfield_gives_back_what_was_stored(payload, name, want):
    """`payload_subfield` is the one reader of a payload's sub-fields (`lane-dir`,
    both control roots, the binding reads, the guard's read of `by host`), so
    what it does to a stored value is what every one of them gets. It must not
    process it: `awk -v` does, and `lane_sidecar_schema_ok` already reads its
    id through `ENVIRON` for that reason. The cases with no backslash in them,
    and the real TAB, are the controls."""
    got = payload_subfield(payload, name)
    assert got == want, f"stored {payload!r}, read {name!r} back as {got!r}, not {want!r}"


# ------------------------------------------------- column 7's escape, on its own

#: What column 7 may be asked to carry, as bytes: each escape and each near
#: miss of one, a backslash before a real TAB, a trailing backslash, bytes
#: outside ASCII and one that is no UTF-8 at all, and then two hundred strings
#: drawn over the same alphabet. No NUL: no path holds one, and no argument can.
CODEC_FIXED = [b"", b"/plain/path", b"/r/a\tb/x", b"/r/a\\tb/x", b"/r/a\\\\b/x",
               b"/r/a\\nb/x", b"/r/a\\101b/x", b"/r/trail\\", b"\\", b"\\\\", b"\\t",
               b"\t", b"\n", b"\r", b"a\\\tb", b"x\\\\\\ty", b"\\q", b"a\\qb\\",
               "caf\u00e9/\u2014/\u00e9\\t".encode(), b"\xff\xfe\\\t\x80",
               b"/r/My Projects/a b", b'/r/q"uote', b"a\x1fb", b"a\x1cb\x1e",
               b"tt\\ttt\\\\tt", b"\\n\\r\\t\\\\"]
_ALPHABET = [b"\\", b"\t", b"\n", b"\r", b"t", b"n", b"r", b"a", b" ", b"/", b"\xc3\xa9",
             b"\xff", b"\x1f", b'"']
_DRAW = random.Random(301)
CODEC = CODEC_FIXED + [b"".join(_DRAW.choice(_ALPHABET) for _ in range(_DRAW.randint(1, 12)))
                       for _ in range(200)]


def _pesc_bytes(value: bytes) -> bytes:
    return (value.replace(b"\\", b"\\\\").replace(b"\t", b"\\t")
            .replace(b"\n", b"\\n").replace(b"\r", b"\\r"))


@pytest.mark.parametrize("locale", ["C", "C.UTF-8"])
@pytest.mark.parametrize("decoder", ["lanes-edit.sh", "lane", "lanes"])
def test_column_seven_round_trips_through_each_decoder(decoder, locale):
    """THE ESCAPE IS EXACT BOTH WAYS, for every reader that decodes it.
    `lanes-edit.sh`'s `row_field_escape` writes each value, and the copy of
    `row_field_unescape_into` in `lanes-edit.sh` (`worktree_rows`), in `lane`
    (`split_row`) and in `lanes` (the renderer) reads it back: the escaped text
    is `pesc`'s, holds no TAB, newline or carriage return, and decodes to the
    value byte for byte. Each copy runs under `set -euo pipefail`, as `lane`
    and `lanes` do, and under both locales."""
    script = (_function("row_field_escape") + _function("row_field_unescape_into", decoder)
              + "set -euo pipefail\n"
              + 'for v in "$@"; do\n'
              + '  e="$(row_field_escape "$v")"\n'
              + '  row_field_unescape_into "$e"\n'
              + "  printf '%s\\0%s\\0' \"$e\" \"$ROW_FIELD_OUT\"\n"
              + "done\n")
    res = subprocess.run(["bash", "-c", script, "bash", *CODEC], capture_output=True, check=False,
                         env={"PATH": os.environ["PATH"], "LC_ALL": locale})
    assert res.returncode == 0, res.stderr
    out = res.stdout.split(b"\0")
    assert len(out) == 2 * len(CODEC) + 1 and out[-1] == b"", (len(out), len(CODEC))
    bad = []
    for i, value in enumerate(CODEC):
        enc, dec = out[2 * i], out[2 * i + 1]
        if enc != _pesc_bytes(value) or dec != value or any(b in enc for b in (b"\t", b"\n", b"\r")):
            bad.append((value, enc, dec))
    assert not bad, f"{len(bad)} of {len(CODEC)} miss, first: {bad[:3]}"


# ---------------------------------------------------------- item 3: `by host`

UUID_H = "77777777-0001-4000-8000-000000007001"
UUID_R = "77777777-0002-4000-8000-000000007002"


def _bound_elsewhere(root: Path) -> Estate:
    """An estate with one lane, repoH-1, whose published binding is a window on
    ANOTHER host (raven): the shape a request is made against."""
    e = Estate(root / "e")
    register = e.wip / "lanes" / "LANES.md"
    rows = register.read_text(encoding="utf-8").split("\n")
    at = next(i for i, line in enumerate(rows) if line.startswith("| `repoC-1`"))
    rows.insert(at + 1, _row("repoH-1", f"`{UUID_H}`", "LIVE · 2026-10-22T10:00:00Z · working"))
    register.write_text("\n".join(rows), encoding="utf-8")
    (e.wip / "lanes" / "log" / "repoH-1.md").write_text(
        f"STARTED — lane repoH-1, session {UUID_H}@Eagle, 2026-10-22T10:00:00Z, "
        f"lane:repoH-1 → home opensoft/repoH; dir /work/repoH; window sess:1 @5; "
        f"host raven; container none; os linux\n", encoding="utf-8")
    e._git("add", "-A")
    e._git("commit", "-q", "-m", "repoH-1 bound on raven")
    e._git("push", "-q", "origin", "main")
    return e


def _requests(e: Estate) -> list[str]:
    """The HANDOFF-REQUESTED lines of repoH-1's PUBLISHED log."""
    published = e._git("show", "origin/main:lanes/log/repoH-1.md")
    return [line for line in published.splitlines() if line.startswith("HANDOFF-REQUESTED")]


#: Hosts `lanes_binding_value_ok` rejects: a space is a second ref, a `;` a
#: second sub-field, a `"` opens a quoted value, and a backslash is no part of
#: the alphabet. A TAB is not among them: `lanes_host_pair` hands the host on
#: TAB-separated from its source, so a `LANES_HOST` holding one is read as the
#: text before it, which is a host the fence takes.
FENCED_HOSTS = {"space": "my host", "semicolon": "a;b", "quote": 'a"b', "backslash": "back\\slash"}


@pytest.mark.parametrize("host", list(FENCED_HOSTS.values()), ids=list(FENCED_HOSTS))
def test_a_host_the_binding_fence_refuses_is_never_written(tmp_path, host):
    """RULING 2, R, ON BOTH PATHS (lane 3's rulings and answers on #301). A
    host that `lanes_binding_value_ok` rejects is never written: not by the
    request, whose `by host` the bound session's guard reads one ref deep and
    types into its pane, and not by `--force`, whose `forced by <uuid>@<host>/…`
    a person reads in the log. Each path, and each one's `--dry-run`, refuses
    with 2 and "Nothing was written" and names `LANES_HOST` as the value's
    source, and the published log is what it was."""
    e = _bound_elsewhere(tmp_path)
    before = e._git("show", "origin/main:lanes/log/repoH-1.md")
    for args in (("--no-wait",), ("--no-wait", "--dry-run"),
                 ("--force", "taking it"), ("--force", "taking it", "--dry-run")):
        res = e.edit("request-handoff", "repoH-1", "--session", UUID_R, *args,
                     env={"LANES_HOST": host})
        assert res.returncode == 2, (args, res.returncode, res.stderr)
        assert "nothing was written" in res.stderr.lower(), (args, res.stderr)
        assert "not one ref" in res.stderr and "LANES_HOST" in res.stderr, (args, res.stderr)
        assert e._git("show", "origin/main:lanes/log/repoH-1.md") == before, args


@pytest.mark.parametrize("host", ["plainhost", "a.b-c_d:9"], ids=["plain", "whole-alphabet"])
def test_a_host_the_binding_fence_takes_is_written_whole_on_both_paths(tmp_path, host):
    """THE CONTROL FOR R: a host of the fence's own alphabet is written as it
    is, by the request (`by host <h>`, read back whole) and by the forced
    release that follows it (`forced by <uuid>@<h>/none`)."""
    e = _bound_elsewhere(tmp_path)
    res = e.edit("request-handoff", "repoH-1", "--session", UUID_R, "--no-wait",
                 env={"LANES_HOST": host})
    lines = _requests(e)
    assert len(lines) == 1, (res.returncode, res.stderr, lines)
    payload = lines[0].split(" → ", 1)[1].split(" — ", 1)[0]
    assert payload_subfield(payload, "by host") == host + "\n", payload
    res = e.edit("request-handoff", "repoH-1", "--session", UUID_R, "--force", "taking it",
                 env={"LANES_HOST": host})
    assert res.returncode == 0, (res.returncode, res.stderr)
    last = e._git("show", "origin/main:lanes/log/repoH-1.md").splitlines()[-1]
    assert last.startswith(f"PAUSED — lane repoH-1, session {UUID_R}@"), last
    assert f"; forced by {UUID_R}@{host}/none; " in last, last


@pytest.mark.parametrize("host", ["plainhost", "my host"], ids=["plain", "space"])
def test_a_request_for_a_handoff_gives_its_host_back_as_it_was_written(tmp_path, host):
    """THE BOUND SESSION IS TOLD THE HOST THE REQUEST CAME FROM, and what it is
    told is what the guard reads out of the published line with
    `payload_subfield "$payload" "by host"`. `request-handoff` wrote the host
    unquoted, and a host that holds a space came back as its first word:
    `my host` as `my`, in the note the session is shown and in the
    `/handoff --exit requested by <uuid>@my/none` line typed into its pane.

    WHAT HOLDS IS THAT THE HOST IS NEVER READ BACK AS SOMETHING ELSE. Written
    quoted it comes back whole; written with the sub-field refused (nothing
    written at all) or dropped (the requester told) there is nothing to read
    back wrongly. Lane 3 ruled the refusal (R), which the case above holds. The
    ordinary host is the control: it is written bare, as the amendment spells
    it, and comes back as it is."""
    e = _bound_elsewhere(tmp_path)
    assert _requests(e) == []
    res = e.edit("request-handoff", "repoH-1", "--session", UUID_R, "--no-wait",
                 env={"LANES_HOST": host})
    lines = _requests(e)
    if not lines:
        # Refused before anything was written. `--no-wait` with nobody to answer
        # is a 2 as well, so a refusal is told from it by what it says.
        assert res.returncode == 2 and "nothing was written" in res.stderr.lower(), \
            (res.returncode, res.stderr)
        assert host != "plainhost", "an ordinary host was refused"
        return
    assert len(lines) == 1, lines
    payload = lines[0].split(" → ", 1)[1].split(" — ", 1)[0]
    read = payload_subfield(payload, "by host").rstrip("\n")
    if host == "plainhost":
        assert payload.startswith("by host plainhost; container none; "), payload
        assert read == host
    else:
        assert read in (host, ""), \
            f"the request line says {payload!r}: its host {host!r} reads back as {read!r}"
        if read == "":
            assert "host" in res.stderr, "a host that was dropped was not said"
