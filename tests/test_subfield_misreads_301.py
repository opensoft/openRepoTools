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

WHAT IS RED AT THE BRANCH'S HEAD AND WHAT IS NOT. The cases that name the three
defects fail; the control cases (an ordinary dir, a dir with a space, a host
with none) pass before the fix and have to keep passing, and so does
`test_the_worktree_listing_keeps_every_lanes_trees` for the lanes whose dir
holds a backslash: it passes today only because the listing and the writers are
wrong in the same way, and a fix of the writers' read that left the listing's
alone would lose those lanes in `worktrees --all`.

THE `by host` CASES ASK WHAT A READER GETS BACK, NOT HOW THE LINE IS SPELLED.
Whether the writer quotes a host that holds a space (the grammar's own rule for
a `dir` or a `profile`) or refuses or drops it is Brett Heap's and lane 3's
to rule; the case holds every spelling that reads back whole, or is not read
back as something else, and fails the one that reads back cut.

EVERY CASE RUNS WITHOUT `LANES_LANE_STATE_ROOT`, the suite's usual seam for the
control root: it answers before any payload is read, so with it set the
defects in the first two items cannot be seen at all.
"""

from __future__ import annotations

import os
import re
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
    that is somebody else's."""

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
    res = misread.e.run("bash", LANES, "--all")
    assert res.returncode == 0, (res.stdout, res.stderr)
    assert "repoT-1" in res.stdout, res.stdout
    assert "DEFECT" not in res.stdout, "\n".join(
        line for line in res.stdout.splitlines() if "DEFECT" in line or "repoT-1" in line)


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


def _function(name: str) -> str:
    """One top-level function of lanes-edit.sh as it is written there: the
    code that runs is the file's own, cut out and run in `bash`."""
    text = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(name)}\(\) \{{[^\n]*\n.*?^\}}\n", text, re.M | re.S)
    assert match, f"`{name}() {{` ... `}}` is no longer in lanes-edit.sh"
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
    back wrongly. Which of those is the fix is for the rulings the design asks
    for. The ordinary host is the control: it is written bare, as the
    amendment spells it, and comes back as it is."""
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
