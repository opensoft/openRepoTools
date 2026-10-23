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

2. THE PAYLOAD IS READ THROUGH THE ENVIRONMENT (item 2). `payload_subfield`
   hands the payload to `awk` as `ENVIRON["PSF_PAY"]` and keeps `want` and
   `mode` on `-v`, so every stored sub-field reads back as it was written.
   Brett Heap's ruling 3, "Accept, no migration": a lane whose recorded dir
   held an escape `awk -v` expanded now finds its control root beside its
   checkout, and what the old read filed elsewhere stays where it was. Lane
   3's ruling 5 pins what that moves in `lane-start`, in `lane-handoff` and in
   the lifecycle, at the end of this module.

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
import sys
from pathlib import Path

import pytest

import test_lanes_index
from conftest import REPO
from test_lane_start_row_stamp import Sandbox
from test_lanes_index import LANES, Estate, _row
from test_triad_lane_tooling import UUID as BENCH_UUID
from test_triad_lane_tooling import Bench

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
#: backslash in the file name: `\t` is two characters, not a TAB. `cr` holds a
#: real carriage return and nothing else of the four: it is the one dir that
#: only the guard's `\r` arm in `lanes_rows` escapes (lane 3's review, 783).
CASES = {
    "plain": ("repoP-1", "plain", "repoP"),
    "space": ("repoS-1", "My Projects", "repoS"),
    "tab": ("repoT-1", "work/a\tb", "repoT"),
    "bs-t": ("repoB-1", "work2/back\\tslash", "repoB"),
    "bs-bs": ("repoD-1", "work3/dbl\\\\slash", "repoD"),
    "bs-n": ("repoN-1", "work4/new\\nline", "repoN"),
    "bs-octal": ("repoO-1", "work5/oct\\101x", "repoO"),
    "cr": ("repoR-1", "work6/a\rb", "repoR"),
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
    `lane <name>` can be asked to reach it.

    EVERY ANSWER IS READ AS BYTES AND DECODED, NEVER WITH `text=True`
    (`edit` and `raw` here, not `Estate.edit`): universal newlines read a lone
    carriage return as a line break, so the `cr` dir, answered by `lane-dir`,
    shown by `lanes` and `lane`, would come back cut in two by the harness
    whatever the tool printed."""

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

    def raw(self, *argv, env: dict | None = None, timeout: float = 120) -> subprocess.CompletedProcess:
        """`Estate.run` with the answer decoded and nothing done to it: the
        same environment, directory and stdin, and no translation of a carriage
        return into a newline."""
        child = dict(self.e.env)
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        proc = subprocess.run([str(a) for a in argv], capture_output=True, env=child,
                              timeout=timeout, cwd=str(self.e.root), stdin=subprocess.DEVNULL,
                              check=False)
        return subprocess.CompletedProcess(proc.args, proc.returncode, proc.stdout.decode("utf-8"),
                                           proc.stderr.decode("utf-8"))

    def edit(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        """`Estate.edit`, as bytes: `bash lanes-edit.sh <args>`."""
        return self.raw("bash", test_lanes_index.LANES_EDIT, *args, env=env)

    def ok(self, *args: str) -> subprocess.CompletedProcess:
        res = self.edit(*args)
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
        res = self.edit("worktrees", *args)
        lines = [line for line in res.stdout.split("\n") if line]
        rows = [dict(zip(TREE_COLS, line.split(US))) for line in lines
                if line.startswith("TREE" + US)]
        other = [line for line in lines if not line.startswith("TREE" + US)]
        return res, rows, other

    def lanes_command(self) -> subprocess.CompletedProcess:
        """The `lanes` command's `--all`, the listing a person reads, run once."""
        if self._lanes is None:
            self._lanes = self.raw("bash", LANES, "--all")
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
    res = misread.raw("bash", REPO / "lane", lane, "--dry-run",
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
    listing, so the index holds one tree for each lane. Before the fix the
    lane whose dir holds a TAB was not in it."""
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
    res = misread.edit("lane-dir", misread.lane[cid])
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


#: WHAT NO ENCODER WRITES, handed to each decoder raw (lane 3's review of #301,
#: 784): (id, the field as a reader could meet it, what the decoder gives back).
#: A backslash before anything but another backslash, `t`, `n` or `r` is kept
#: as it stands, and so is a backslash with nothing after it, so text no
#: encoder wrote reads back as itself. `CODEC` above only ever hands a decoder
#: what `row_field_escape` wrote, which holds no such backslash, so this arm of
#: all three copies never ran, and broken, 94 of 94 cases still passed. The last
#: two rows mix the arm with the four escapes: it has to hand the character
#: after the backslash back to the loop, which is what a missing `continue`
#: would lose.
PASS_THROUGH = [
    ("other", b"a\\qb", b"a\\qb"),
    ("octal", b"\\101", b"\\101"),
    ("trailing", b"/r/trail\\", b"/r/trail\\"),
    ("alone", b"\\", b"\\"),
    ("hex-and-quote", b'/r/a\\x41b\\"c', b'/r/a\\x41b\\"c'),
    ("slash-then-escapes", b"a\\/b\\tc\\\\d\\n", b"a\\/b\tc\\d\n"),
    ("between-and-after", b"a\\qb\\tc\\\\d\\", b"a\\qb\tc\\d\\"),
]


@pytest.mark.parametrize("locale", ["C", "C.UTF-8"])
@pytest.mark.parametrize("decoder", ["lanes-edit.sh", "lane", "lanes"])
def test_a_backslash_before_anything_else_is_kept_by_each_decoder(decoder, locale):
    """THE DECODER'S PASS-THROUGH ARM, in each of its three copies
    (`lanes-edit.sh`, `lane`, `lanes`), under `set -euo pipefail` and in both
    locales as the round trip runs them: `a\\qb`, `\\101` and a trailing
    backslash come back as they went in, a backslash before another backslash
    or `t`, `n` or `r` is still decoded around them, and nothing is lost,
    doubled or left looping."""
    script = (_function("row_field_unescape_into", decoder)
              + "set -euo pipefail\n"
              + 'for v in "$@"; do\n'
              + '  row_field_unescape_into "$v"\n'
              + "  printf '%s\\0' \"$ROW_FIELD_OUT\"\n"
              + "done\n")
    res = subprocess.run(["bash", "-c", script, "bash", *[raw for _, raw, _ in PASS_THROUGH]],
                         capture_output=True, check=False, timeout=60,
                         env={"PATH": os.environ["PATH"], "LC_ALL": locale})
    assert res.returncode == 0, res.stderr
    out = res.stdout.split(b"\0")
    assert len(out) == len(PASS_THROUGH) + 1 and out[-1] == b"", (len(out), len(PASS_THROUGH))
    bad = [(name, raw, want, got) for (name, raw, want), got in zip(PASS_THROUGH, out)
           if got != want]
    assert not bad, f"{len(bad)} of {len(PASS_THROUGH)} miss, (id, raw, wanted, got): {bad}"


def test_a_dir_the_encoder_cannot_escape_is_listed_as_none_and_the_listing_says_so(tmp_path):
    """THE FALLBACK IN `lanes_rows` (the mutant pass, `fallback-removed`). An
    encoder that fails prints nothing, and an empty column 7 is one a TAB-IFS
    `read` cannot split (two TABs in a row are one separator, and every column
    after it arrives a place early), so the column says `none`, the row keeps
    its seventeen columns, and the listing says on stderr which lane's dir it
    could not escape. The failure is an `awk` in the estate's bin that exits 1
    for the one call that carries `RFE_IN`, the encoder's input, and is the real
    one for every other."""
    e = Estate(tmp_path / "e")
    lane = "repoF-1"
    (e.wip / "lanes" / "log" / f"{lane}.md").write_text(
        _started(lane, "88888888-0001-4000-8000-000000008001", "/r/back\\slash/repoF"),
        encoding="utf-8")
    e._git("add", "-A")
    e._git("commit", "-q", "-m", "repoF-1, a dir holding a backslash")
    e._git("push", "-q", "origin", "main")
    real_awk = shutil.which("awk")
    assert real_awk, "no awk on PATH"
    (e.fakebin / "awk").write_text(
        f'#!/bin/sh\n[ -n "${{RFE_IN+x}}" ] && exit 1\nexec {real_awk} "$@"\n')
    (e.fakebin / "awk").chmod(0o755)
    res = e.edit("lanes", "--all")
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    rows = {line.split(TAB)[0]: line.split(TAB) for line in res.stdout.split("\n") if line}
    row = rows.get(lane)
    assert row is not None, sorted(rows)
    assert len(row) == 17, f"{len(row)} columns: " + _shown("|".join(row))
    assert row[6] == "none", _shown("|".join(row))
    assert (f"lane {lane}'s recorded dir could not be escaped for the listing, so its "
            f"directory column says none.") in res.stderr, res.stderr


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
#: AND TWO ROWS FOR THE CONTAINER (lane 3's review of #301, 781). The forced
#: release writes it beside the host, `forced by <uuid>@<host>/<container>`, and
#: nothing fenced it there: `LANES_CONTAINER='a b'` was written whole and
#: `--force` exited 0, where the request path's `container <c>` is a sub-field
#: NAMED `container` and `write_event` refused it. One rule holds for every
#: value the tools write (ruling 2's answer 1), so the container is held to the
#: fence the host is, and a refusal names `LANES_CONTAINER` as its source.
FENCED_CONTAINERS = {"container-space": "a b", "container-semicolon": "a;b"}
FENCED = ([("LANES_HOST", host) for host in FENCED_HOSTS.values()]
          + [("LANES_CONTAINER", name) for name in FENCED_CONTAINERS.values()])


@pytest.mark.parametrize("variable,value", FENCED, ids=list(FENCED_HOSTS) + list(FENCED_CONTAINERS))
def test_a_host_the_binding_fence_refuses_is_never_written(tmp_path, variable, value):
    """RULING 2, R, ON BOTH PATHS (lane 3's rulings and answers on #301). A
    host that `lanes_binding_value_ok` rejects is never written: not by the
    request, whose `by host` the bound session's guard reads one ref deep and
    types into its pane, and not by `--force`, whose `forced by <uuid>@<host>/…`
    a person reads in the log. Each path, and each one's `--dry-run`, refuses
    with 2 and "Nothing was written" and names `LANES_HOST` as the value's
    source, and the published log is what it was. The container rows are the
    same matrix for the other half of that line (`LANES_CONTAINER`, with the
    estate's own host, which the fence takes): the same four invocations, the
    same refusal, and `LANES_CONTAINER` named as the source."""
    e = _bound_elsewhere(tmp_path)
    before = e._git("show", "origin/main:lanes/log/repoH-1.md")
    for args in (("--no-wait",), ("--no-wait", "--dry-run"),
                 ("--force", "taking it"), ("--force", "taking it", "--dry-run")):
        res = e.edit("request-handoff", "repoH-1", "--session", UUID_R, *args,
                     env={variable: value})
        assert res.returncode == 2, (args, res.returncode, res.stderr)
        assert "nothing was written" in res.stderr.lower(), (args, res.stderr)
        assert "not one ref" in res.stderr and variable in res.stderr, (args, res.stderr)
        assert e._git("show", "origin/main:lanes/log/repoH-1.md") == before, args


#: WHERE A REFUSED NAME CAME FROM, AS THE REFUSAL SAYS IT (the mutant pass,
#: `source-text-dropped`). The matrix above asks that the refusal names the
#: variable, and its closing sentence names `LANES_HOST` or `LANES_CONTAINER`
#: whichever clause went before it, so a refusal that gave the wrong source, or
#: one clause for every source, passed. One row for each source a name can come
#: from: (what is refused, the environment that selects the source, the name it
#: gives, the clause the refusal carries). The seam, the workstation's name that
#: a container writes as its host, and what `hostname` answered, which is a stub
#: in the estate's bin because the box the suite runs on has a name of its own.
SOURCES = {
    "host-seam": ("host", {"LANES_HOST": "my host"}, "my host",
                  "it is the value of LANES_HOST. A space there"),
    "host-workstation": ("host", {"LANES_HOST": None, "LANES_IN_CONTAINER": "1",
                                  "LANES_WORKSTATION": "my ws"}, "my ws",
                         "it is this workstation's name, which a container writes as its "
                         "host; LANES_HOST overrides it. A space there"),
    "host-hostname": ("host", {"LANES_HOST": None}, "my box",
                      "it is this machine's `hostname -s`; LANES_HOST overrides it. "
                      "A space there"),
    "container-seam": ("container", {"LANES_CONTAINER": "a b"}, "a b",
                       "it is the value of LANES_CONTAINER. A space there"),
    "container-hostname": ("container", {"LANES_CONTAINER": None, "LANES_IN_CONTAINER": "1"},
                           "my box",
                           "it is this container's own `hostname`, which a container with "
                           "no LANES_CONTAINER writes; LANES_CONTAINER overrides it. "
                           "A space there"),
}


@pytest.mark.parametrize("kind,env,name,clause", list(SOURCES.values()), ids=list(SOURCES))
def test_the_refusal_says_where_the_refused_name_came_from(tmp_path, kind, env, name, clause):
    """THE REFUSAL NAMES THE SOURCE OF THE VALUE IT REFUSES, for each source it
    can have: the variable that was set (`LANES_HOST`, `LANES_CONTAINER`), the
    workstation's name a container writes as its host, and what `hostname`
    answered. The person is told which of them to put right, so the clause is
    pinned whole, with the name between its quotes, on the request and on
    `--force`, for the host and for the container alike, and nothing is
    written."""
    e = _bound_elsewhere(tmp_path)
    (e.fakebin / "hostname").write_text("#!/bin/sh\nprintf 'my box\\n'\n")
    (e.fakebin / "hostname").chmod(0o755)
    before = e._git("show", "origin/main:lanes/log/repoH-1.md")
    for args in (("--no-wait",), ("--force", "taking it")):
        res = e.edit("request-handoff", "repoH-1", "--session", UUID_R, *args, env=env)
        assert res.returncode == 2, (args, res.returncode, res.stderr)
        assert f"request-handoff writes this {kind}'s name into lane repoH-1's" in res.stderr, \
            (args, res.stderr)
        assert f"and '{name}' is not one ref of Amendment 7(b)'s grammar" in res.stderr, \
            (args, res.stderr)
        assert f"): {clause}" in res.stderr, (args, res.stderr)
        assert "Nothing was written." in res.stderr, (args, res.stderr)
        assert e._git("show", "origin/main:lanes/log/repoH-1.md") == before, args


def test_a_lane_that_is_free_is_told_so_before_a_bad_host_is_refused(tmp_path):
    """THE FENCE COMES AFTER THE BINDING IS READ (the mutant pass,
    `check-before-binding-read`). A lane with nobody bound has nothing to ask,
    and what a requester is told is that it is FREE, with 8, whatever its host
    or container is called: a refusal about the requester's own settings in
    front of it would send a person to put right a name the request never
    needed. Every other case here asks a lane that is bound."""
    e = _bound_elsewhere(tmp_path)
    tip = e.tip()
    for variable, value in (("LANES_HOST", "my host"), ("LANES_CONTAINER", "a b")):
        res = e.edit("request-handoff", "repoC-1", "--session", UUID_R, "--no-wait",
                     env={variable: value})
        assert res.returncode == 8, (variable, res.returncode, res.stderr)
        assert "lane repoC-1 is FREE" in res.stderr, (variable, res.stderr)
        assert "not one ref" not in res.stderr, (variable, res.stderr)
        # THE REQUEST GOES TO repoC-1 AND `_requests` READS repoH-1's LOG, so it
        # could not have shown a line written to the lane that was asked. What
        # "nothing was written" means is that the published register has not
        # moved at all, whichever log, and the tip is the one thing that says it.
        assert e.tip() == tip, (variable, tip, e.tip())


@pytest.mark.parametrize("host,container", [("plainhost", "none"), ("plainhost", "plainc"),
                                            ("A.b-C_d:9", "A.b-C_d:9")],
                         ids=["no-container", "plain", "whole-alphabet"])
def test_a_host_the_binding_fence_takes_is_written_whole_on_both_paths(tmp_path, host, container):
    """THE CONTROL FOR R: a host and a container of the fence's own alphabet are
    written as they are, by the request (`by host <h>` and `container <c>`,
    read back whole) and by the forced release that follows it (`forced by
    <uuid>@<h>/<c>`). EVERY ROW OF THE MATRIX ABOVE IS A REFUSAL (lane 3's
    re-check of #301, 841), so this is the one place a fence that took nothing
    but `none` for a container is told from the one that takes the alphabet.
    The whole-alphabet row holds a capital as well (lane 3, 1021): `A-Z` is in
    the alphabet and no other row carries one, so a fence that dropped it
    passed every id."""
    e = _bound_elsewhere(tmp_path)
    env = {"LANES_HOST": host, "LANES_CONTAINER": container}
    res = e.edit("request-handoff", "repoH-1", "--session", UUID_R, "--no-wait", env=env)
    lines = _requests(e)
    assert len(lines) == 1, (res.returncode, res.stderr, lines)
    payload = lines[0].split(" → ", 1)[1].split(" — ", 1)[0]
    assert payload_subfield(payload, "by host") == host + "\n", payload
    assert payload_subfield(payload, "container") == container + "\n", payload
    res = e.edit("request-handoff", "repoH-1", "--session", UUID_R, "--force", "taking it", env=env)
    assert res.returncode == 0, (res.returncode, res.stderr)
    last = e._git("show", "origin/main:lanes/log/repoH-1.md").splitlines()[-1]
    assert last.startswith(f"PAUSED — lane repoH-1, session {UUID_R}@"), last
    assert f"; forced by {UUID_R}@{host}/{container}; " in last, last


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


# --------------------------------- ruling 5: what item 2 moves, pinned (502, 505)


def test_lane_start_reaches_the_recorded_dir_and_not_the_one_awk_made_of_it(tmp_path):
    """RULING 5, PIN 1 (lane 3's review of #301, 502). With no `--dir`,
    `lane-start` takes a lane's checkout from `lane-dir` (`lane-start:1267`).
    The lane is started once with `--dir <...>/work5/oct\\101x/repoO`, beside
    an existing `<...>/work5/octAx/repoO` of the same repository, and again
    with no `--dir`: the second start records the dir the first one did, and
    its launch would run there. Before the fix `awk -v` read `\\101` as `A`,
    and the second start recorded `octAx/repoO` and would have launched in a
    checkout that is not the lane's. No source of `lane-start` changes."""
    box = Sandbox(tmp_path)
    work = Path(os.path.realpath(tmp_path)) / "w" / "work5"
    real, sibling = work / "oct\\101x" / "repoO", work / "octAx" / "repoO"
    for path in (real, sibling):
        path.parent.mkdir(parents=True)
        box.git("init", "-q", "-b", "main", str(path))
        box.git("-C", str(path), "remote", "add", "origin", "https://github.com/opensoft/repoO.git")

    def start(*args: str, window_name: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(box.bin / "lane-start"), "repoO", "1", "--no-launch", *args],
                              env=dict(box.env, FAKE_TMUX_WINDOW_NAME=window_name),
                              capture_output=True, text=True, timeout=120, check=False)

    first = start("--dir", str(real), window_name="claude")
    assert first.returncode == 0, first.stderr
    second = start(window_name="repoO-1")
    assert second.returncode == 0, second.stderr
    log = (box.wip / "lanes" / "log" / "repoO-1.md").read_text(encoding="utf-8").split("\n")
    bindings = [line for line in log if line.split(" — ", 1)[0] in ("STARTED", "RESUMED")]
    assert len(bindings) == 2, log
    assert all(f"; dir {real}; " in line for line in bindings), bindings
    assert "octAx" not in "\n".join(log), log
    assert f"(its cwd would be {real})" in second.stderr, second.stderr


def _bench_lane(b: Bench, lane: str, checkout: Path, *, lifecycle: bool = True) -> None:
    """`checkout` a clone of its own origin, and `lane` registered with a STARTED
    line recording it, as `Bench.lanes` registers one - with the RUNNING
    snapshot `Bench.lanes` files, or, with `lifecycle=False`, none."""
    name = lane.rsplit("-", 1)[0]
    b.origin(name)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    b.git("clone", "-q", b.remotes / f"{name}.git", checkout)
    b.commit(checkout, "seed", {"README.md": f"{name}\n"})
    b.git("push", "-q", "origin", "main", cwd=checkout)
    if lifecycle:
        b.lanes(f"opensoft/{name}", checkout, lane)
        return
    reg = b.wip / "lanes" / "LANES.md"
    reg.write_text(reg.read_text() + (
        f"| `{lane}` | harness `{BENCH_UUID}` | Eagle / test / brett | 2026-10-08T00:00Z "
        f"| none | handoffs/{lane}.md | LIVE · 2026-10-08T00:00:00Z · working |\n"))
    (b.wip / "handoffs" / f"{lane}.md").write_text(f"# handoff {lane}\n\nwork.\n")
    (b.wip / "lanes" / "log" / f"{lane}.md").write_text(
        f"STARTED — lane {lane}, session {BENCH_UUID}@Eagle, 2026-10-08T00:00:00Z, lane:{lane} "
        f"→ home opensoft/{name}; dir {checkout}; host eagle; container none; os linux\n")
    b.git("add", "-A", cwd=b.wip)
    b.git("commit", "-q", "-m", lane, cwd=b.wip)
    b.git("push", "-q", "origin", "main", cwd=b.wip)


def _handoff(b: Bench, lane: str, checkout: Path) -> subprocess.CompletedProcess:
    return b.tool("lane-handoff", "--lane", lane, "--transcript", "none", "--agent", "claude",
                  "a #301 handoff", cwd=checkout)


def _lane_state(b: Bench, lane: str, env: dict | None = None) -> tuple[int, dict]:
    proc = b.tool("lanes-edit.sh", "lane-state", lane, env=env)
    return proc.returncode, dict(line.split("\t", 1) for line in proc.stdout.split("\n") if "\t" in line)


def test_lane_handoff_writes_a_recorded_backslash_t_back_as_it_was_recorded(tmp_path):
    """RULING 5, PIN 2 (502). `lane-handoff` takes the lane's dir from
    `lane-dir` (`lane-handoff:1862`) and writes it back into the PAUSED line it
    records (`:2774-2777`), the line a launcher restarts the lane from. A dir
    holding a backslash and a `t` goes back byte for byte, and the lifecycle
    the handoff moves is the one beside the checkout. Before the fix `awk -v`
    made the `\\t` a TAB: the PAUSED line named a directory that does not
    exist, and the snapshot was filed under `<home>/projects/.lane-state`. No
    source of `lane-handoff` changes."""
    b = Bench(tmp_path / "bench", REPO)
    checkout = b.projects / "back\\tslash" / "repoB"
    _bench_lane(b, "repoB-1", checkout)
    res = _handoff(b, "repoB-1", checkout)
    assert res.returncode == 0, res.stderr
    paused = b.last_log("repoB-1")
    assert paused.startswith("PAUSED — lane repoB-1, "), paused
    assert f"; dir {checkout}; " in paused and TAB not in paused, repr(paused)
    rc, state = _lane_state(b, "repoB-1")
    assert rc == 0 and state.get("state") == "SWAPPED", (rc, state)
    assert state.get("file") == str(checkout.parent / ".lane-state" / "repoB-1" / "lane-state.yaml"), state


def test_a_lanes_lifecycle_starts_again_at_its_new_root_and_its_old_records_stay_where_they_were(tmp_path):
    """RULING 5, PIN 3 (505): THE ROOT MOVE, AND WHAT BRETT HEAP'S "Accept, no
    migration" LEAVES. A lane recorded at `<...>/work5/oct\\101x/repoO`, beside
    an existing `<...>/work5/octAx`, had its records filed by the old read in
    `octAx/.lane-state/repoO-1`: `awk -v` read the dir as `octAx/repoO`. They
    are filed there here through `LANES_LANE_STATE_ROOT`, the seam that places a
    control root - the snapshot, one tree and a restart intent - and
    `lanes-index sync` copies the tree into the index. Then, with the read
    exact:

    * `lane-dir` answers the recorded dir, and `lane-state` answers 8: the new
      root, `oct\\101x/.lane-state/repoO-1`, holds no snapshot yet;
    * `lanes-index sync` HOLDS the lane's rows (`lanes-index:2079-2097`, `sync`
      only and only over a stored generation of at least 1): the read's
      generation 0 is below the 1 they were written at, so it writes nothing
      for the lane and says so;
    * NAMED AND NOT FIXED: `lane_restart_control_root` looks for an intent
      beside the recorded dir and under `$PROJECTS_ROOT` and nowhere else, so
      `restart-intent` answers 8 while the intent the old read filed under
      `octAx` is still there;
    * the next handoff takes SWAPPING with `--expect none` at generation 1,
      at the new root (`lane-handoff:1500-1524`), and writes the dir back as
      recorded;
    * nothing at the old root is moved, rewritten or removed;
    * and once the new root's generation reaches the one the rows were written
      at, `sync` takes the lane as it now stands: its rows leave the index,
      while the records under `octAx` stay where they are, unread."""
    b = Bench(tmp_path / "bench", REPO)
    lane = "repoO-1"
    work = b.projects / "work5"
    checkout = work / "oct\\101x" / "repoO"
    (work / "octAx").mkdir(parents=True)
    _bench_lane(b, lane, checkout, lifecycle=False)
    old_root = work / "octAx" / ".lane-state" / lane
    old_read = {"LANES_LANE_STATE_ROOT": str(old_root.parent)}
    index_env = {"LANES_INDEX": "", "LANES_EDIT": str(b.bin / "lanes-edit.sh")}
    db = b.home / ".local" / "state" / "openRepoTools" / "lanes-index.sqlite"

    def ok(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        proc = b.tool("lanes-edit.sh", *args, env=env)
        assert proc.returncode == 0, (args, proc.stdout, proc.stderr)
        return proc

    def sync(env: dict | None = None) -> subprocess.CompletedProcess:
        proc = b.run(sys.executable, REPO / "lanes-index", "sync", "--source", "inventory",
                     env=dict(index_env, **(env or {})))
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        return proc

    def indexed() -> list:
        conn = sqlite3.connect(str(db))
        rows = [tuple(r) for r in conn.execute(
            "SELECT record_id, generation FROM worktrees WHERE lane = ?", (lane,))]
        conn.close()
        return rows

    def old_records() -> dict:
        return {str(f.relative_to(old_root)): f.read_bytes() for f in sorted(old_root.rglob("*"))
                if f.is_file()}

    ok("set-lane-state", lane, "RUNNING", "--expect", "none", "--operation", "op-legacy",
       "--owner", BENCH_UUID, env=old_read)
    ok("set-lane-tree", lane, f"/nowhere/{lane}/w", "--checkout", "/nowhere", "--branch",
       f"feat/{lane}", "--head", "7" * 40, "--upstream", "none", "--dirty", "0",
       "--unpushed", "0", env=old_read)
    ok("set-restart-intent", lane, "preparing", "--expect", "none", "--operation",
       "op-restart-legacy", "--mode", "restart", "--agent", "claude", "--dir", str(checkout),
       env=old_read)
    before = old_records()
    assert sorted(before) == ["lane-state.yaml", "restart-intent.yaml",
                              f"trees/{ok('lane-trees', lane, env=old_read).stdout.split(US)[0]}.yaml"], before
    sync(old_read)
    assert indexed() == [(f"{lane}:/nowhere/{lane}/w", 1)]

    # THE READ EXACT
    assert ok("lane-dir", lane).stdout == f"{checkout}\n"
    assert _lane_state(b, lane)[0] == 8
    held = sync()
    assert (f"lane {lane}: its rows are kept as they are - its lifecycle generation reads 0 "
            f"and its rows were written at 1") in held.stdout, held.stdout
    assert indexed() == [(f"{lane}:/nowhere/{lane}/w", 1)]
    intent = b.tool("lanes-edit.sh", "restart-intent", lane)
    assert intent.returncode == 8, (intent.returncode, intent.stdout, intent.stderr)
    assert old_records() == before

    # THE NEXT HANDOFF, AT THE NEW ROOT
    res = _handoff(b, lane, checkout)
    assert res.returncode == 0, res.stderr
    assert "lifecycle: none -> SWAPPING (generation 1," in res.stderr, res.stderr
    assert f"; dir {checkout}; " in b.last_log(lane), b.last_log(lane)
    rc, state = _lane_state(b, lane)
    assert rc == 0 and (state.get("state"), state.get("generation")) == ("SWAPPED", "1"), state
    assert state.get("file") == str(checkout.parent / ".lane-state" / lane / "lane-state.yaml"), state
    assert old_records() == before

    taken = sync()
    assert "1 removed" in taken.stdout, taken.stdout
    assert indexed() == []
    assert old_records() == before
