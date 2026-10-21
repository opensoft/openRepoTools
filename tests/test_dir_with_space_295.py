# SPDX-License-Identifier: Apache-2.0
"""A lane whose recorded `dir` holds a space keeps its trees (#295).

THE DEFECT. `lane-start` writes a `dir` that holds a space QUOTED
(`quote_subfield`), and every read of the lane's own log takes it whole:
`lane-dir`, and the control root `set-lane-state` and `set-lane-tree` file
the lane's snapshot and trees under, `<parent of dir>/.lane-state/<lane>`.
`worktree_rows`, the read behind `lanes-edit.sh worktrees` and `lanes-index
sync --source inventory`, does not read the log again. It builds the payload
of its three reads (`lane_control_root`, `lane_trees_list` and
`lane_state_read`) from the listing's column 7, which is the `dir` with its
quotes already taken off, and it handed that on bare, as `dir <column 7>`.
`payload_subfield` reads a bare value only up to its first space, so
`<root>/My Projects/repoS` came back as `<root>/My`. That one's
parent IS a directory, so the root became `<root>/.lane-state/repoS-1`, where
no `trees` is, and the lane was skipped in silence: no `UNREAD`, no
`PARTIAL`, no row in `worktrees --all`, 8 ("none") from `worktrees <lane>`,
and no trees in the index. The named `lane-trees <lane>` listed them all the
while.

THE FIX re-quotes the value by `quote_subfield`'s own rule: quoted where it
holds a space, and bare where it does not. It does not quote every value,
because a quoted value ends at its first `"`. A `dir` carrying one is a value
`lane-start` refuses to write, but a hand-written `log` line can carry it, and
quoting it would cut it there and lose the lane exactly as the space did. The
last case holds that, and it passes before the fix too.

EVERY CASE RUNS WITHOUT `LANES_LANE_STATE_ROOT`, the suite's usual seam for
the control root. That override answers before any payload is read, so with it
set the defect cannot be seen at all.
"""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

import test_lanes_index
from test_lanes_index import Estate

pytestmark = test_lanes_index.pytestmark
US = "\x1f"
UUID_S1 = "55555555-0001-4000-8000-000000005001"
UUID_P1 = "55555555-0002-4000-8000-000000005002"
UUID_Q1 = "55555555-0003-4000-8000-000000005003"
#: A TREE row's columns, as `worktree_rows` documents them.
TREE_COLS = ["kind", "workstation", "lane", "owner", "path", "branch", "base", "lifecycle",
             "generation", "operation", "writer_live", "last_seen_utc", "last_commit",
             "dirty", "unpushed", "provenance"]


def _started(lane: str, uuid: str, dir_field: str) -> str:
    """The lane's STARTED line, its `dir` sub-field spelled as the caller gives it."""
    return (f"STARTED — lane {lane}, session {uuid}@Eagle, 2026-10-01T00:40:00Z, "
            f"lane:{lane} → home opensoft/{lane[:-2]}; {dir_field}; profile team-02a\n")


class Spaced:
    """test_lanes_index's Estate with three lanes of this file's own, each
    started by a log line and given its snapshot and one tree by the two
    writers, `set-lane-state` and `set-lane-tree`, which find the lane's root
    from its log:

      repoS-1  `dir "<root>/My Projects/repoS"`, quoted as `lane-start` writes
               it, with a real checkout there and a real worktree beside it;
      repoP-1  `dir <root>/plain/repoP`, the control: no space, no quote;
      repoQ-1  `dir <root>/q"uote/repoQ`, bare, as a hand-written line could
               carry it: a `"` and no space.
    """

    def __init__(self, root: Path):
        self.root = root
        self.e = Estate(root / "e")
        assert "LANES_LANE_STATE_ROOT" not in self.e.env
        self.spaced = root / "My Projects"
        self.s_checkout = self.spaced / "repoS"
        self.s_tree = self.spaced / ".lane-worktrees" / "repoS-1" / "feat-s"
        self.p_dir = root / "plain" / "repoP"
        self.q_dir = root / 'q"uote' / "repoQ"
        self.p_tree = "/nowhere/repoP-1/w"
        self.q_tree = "/nowhere/repoQ-1/w"
        origin = self.spaced / "repoS.git"
        self.spaced.mkdir(parents=True)
        self.p_dir.parent.mkdir()
        self.q_dir.parent.mkdir()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)],
                       check=True, env=self.e.env)
        subprocess.run(["git", "clone", "-q", str(origin), str(self.s_checkout)],
                       check=True, env=self.e.env, capture_output=True)
        (self.s_checkout / "a.txt").write_text("seed\n")
        self._g(self.s_checkout, "add", "-A")
        self._g(self.s_checkout, "commit", "-q", "-m", "the lane's first commit")
        self._g(self.s_checkout, "push", "-q", "origin", "main")
        self.s_tree.parent.mkdir(parents=True)
        self._g(self.s_checkout, "worktree", "add", "-q", "-b", "feat/s", str(self.s_tree))
        log = self.e.wip / "lanes" / "log"
        (log / "repoS-1.md").write_text(_started("repoS-1", UUID_S1, f'dir "{self.s_checkout}"'),
                                        encoding="utf-8")
        (log / "repoP-1.md").write_text(_started("repoP-1", UUID_P1, f"dir {self.p_dir}"),
                                        encoding="utf-8")
        (log / "repoQ-1.md").write_text(_started("repoQ-1", UUID_Q1, f"dir {self.q_dir}"),
                                        encoding="utf-8")
        self.e._git("add", "-A")
        self.e._git("commit", "-q", "-m", "three lanes and their recorded dirs")
        self.e._git("push", "-q", "origin", "main")
        self.ok("set-lane-state", "repoS-1", "RUNNING", "--operation", "op-test-s1")
        self.ok("set-lane-tree", "repoS-1", str(self.s_tree), "--checkout", str(self.s_checkout))
        for lane, tree in (("repoP-1", self.p_tree), ("repoQ-1", self.q_tree)):
            self.ok("set-lane-state", lane, "RUNNING", "--operation", f"op-test-{lane}")
            self.ok("set-lane-tree", lane, tree, "--checkout", tree.rsplit("/", 1)[0],
                    "--branch", f"feat/{lane}", "--head", "7" * 40, "--upstream", "none",
                    "--dirty", "0", "--unpushed", "0")

    def _g(self, cwd: Path, *args: str) -> str:
        proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                              env=self.e.env, check=False)
        assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"
        return proc.stdout.strip()

    def ok(self, *args: str) -> subprocess.CompletedProcess:
        res = self.e.edit(*args)
        assert res.returncode == 0, (args, res.stdout, res.stderr)
        return res

    def worktrees(self, *args: str) -> tuple[subprocess.CompletedProcess, list, list]:
        """`lanes-edit.sh worktrees <args>`: the answer, its TREE rows as
        dicts, and every other line it printed (`UNREAD`, `PARTIAL`)."""
        res = self.e.edit("worktrees", *args)
        lines = [line for line in res.stdout.splitlines() if line]
        rows = [dict(zip(TREE_COLS, line.split(US))) for line in lines
                if line.startswith("TREE" + US)]
        other = [line for line in lines if not line.startswith("TREE" + US)]
        return res, rows, other


def _of(rows: list, lane: str) -> list:
    return [(r["lane"], r["owner"], r["path"], r["branch"], r["lifecycle"], r["generation"],
             r["operation"]) for r in rows if r["lane"] == lane]


def _shown(text: str) -> str:
    """An answer with its unit separators made visible, for a failure message."""
    return text.replace(US, " | ")


@pytest.fixture(scope="module")
def spaced(tmp_path_factory):
    return Spaced(tmp_path_factory.mktemp("dir-with-space-295"))


def test_the_writers_file_the_lane_where_its_quoted_dir_places_it(spaced):
    """THE PRECONDITION, which holds before the fix and after it: the named
    reads take the quoted `dir` whole, so `set-lane-state` and `set-lane-tree`
    filed repoS-1 under `<root>/My Projects/.lane-state/repoS-1`. Nothing is
    under `<root>/.lane-state`, the root the listing worked out from `<root>/My`."""
    res = spaced.ok("lane-dir", "repoS-1")
    assert res.stdout.strip() == str(spaced.s_checkout)
    lane_root = spaced.spaced / ".lane-state" / "repoS-1"
    assert (lane_root / "lane-state.yaml").is_file()
    assert len(list((lane_root / "trees").glob("*.yaml"))) == 1
    assert not (spaced.root / ".lane-state").exists()
    named = spaced.ok("lane-trees", "repoS-1")
    paths = [line.split(US)[1] for line in named.stdout.splitlines() if line]
    assert paths == [str(spaced.s_tree)], _shown(named.stdout)


def test_a_dir_with_a_space_keeps_its_trees_in_the_listing(spaced):
    """`worktrees --all` lists repoS-1's tree, with the lifecycle its snapshot
    holds, and `worktrees repoS-1` answers 0 with the same row. Before the fix
    the first had no row for it, beside repoP-1's, and the second said 8."""
    res, rows, other = spaced.worktrees("--all")
    assert res.returncode == 0, res.stderr
    want = [("repoS-1", "legacy", str(spaced.s_tree), "feat/s", "RUNNING", "1", "op-test-s1")]
    assert _of(rows, "repoS-1") == want, _shown(res.stdout)
    assert [line for line in other if "repoS-1" in line] == [], other
    assert _of(rows, "repoP-1") == [("repoP-1", "legacy", spaced.p_tree, "feat/repoP-1",
                                     "RUNNING", "1", "op-test-repoP-1")], _shown(res.stdout)
    one, one_rows, one_other = spaced.worktrees("repoS-1")
    assert one.returncode == 0, (one.returncode, one.stderr)
    assert _of(one_rows, "repoS-1") == want, _shown(one.stdout)
    assert one_other == [], one_other


def test_a_dir_with_a_space_keeps_its_trees_in_the_inventory_index(spaced):
    """`lanes-index sync --source inventory` copies the listing, so the index
    holds repoS-1's tree, with its lifecycle, beside repoP-1's. Before the fix
    it held repoP-1's alone."""
    res = spaced.e.index("sync", "--source", "inventory")
    assert res.returncode == 0, (res.stdout, res.stderr)
    conn = sqlite3.connect(str(spaced.e.sqlite))
    conn.row_factory = sqlite3.Row
    rows = {r["record_id"]: dict(r) for r in conn.execute(
        "SELECT * FROM worktrees WHERE source = 'inventory:Eagle'")}
    conn.close()
    s_id = f"repoS-1:{spaced.s_tree}"
    p_id = f"repoP-1:{spaced.p_tree}"
    ours = {k for k in rows if k.startswith(("repoS-1:", "repoP-1:"))}
    assert ours == {s_id, p_id}, sorted(rows)
    s = rows[s_id]
    assert (s["lane"], s["owner"], s["branch"], s["lifecycle"], s["generation"],
            s["operation"]) == ("repoS-1", "legacy", "feat/s", "RUNNING", 1, "op-test-s1")


def test_a_dir_with_a_quote_mark_and_no_space_keeps_its_trees_too(spaced):
    """THE FIX QUOTES ONLY WHERE A SPACE IS, as `quote_subfield` does. This
    passes before the fix too. Quoting every value would hand repoQ-1's
    `<root>/q"uote/repoQ` on as `"<root>/q"uote/repoQ"`, which
    `payload_subfield` reads up to its first `"`, so `<root>/q`, and the lane
    would leave the listing exactly as a space made repoS-1 leave it."""
    res = spaced.ok("lane-dir", "repoQ-1")
    assert res.stdout.strip() == str(spaced.q_dir)
    q_trees = spaced.q_dir.parent / ".lane-state" / "repoQ-1" / "trees"
    assert len(list(q_trees.glob("*.yaml"))) == 1
    res, rows, other = spaced.worktrees("--all")
    assert res.returncode == 0, res.stderr
    assert _of(rows, "repoQ-1") == [("repoQ-1", "legacy", spaced.q_tree, "feat/repoQ-1",
                                     "RUNNING", "1", "op-test-repoQ-1")], _shown(res.stdout)
    assert [line for line in other if "repoQ-1" in line] == [], other
