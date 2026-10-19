# SPDX-License-Identifier: Apache-2.0
"""T018 (b) (opensoft/openRepoTools#186): `lane-handoff` and `lane-reconcile`
see a TRIAD's trees.

A lane's checkout is an ASSEMBLY when its own `project.yaml` declares a leg
other than itself - read by `lanes-edit.sh project-legs`, the one reader every
lane tool asks. Its legs are submodules, and a feature's trees are worktrees of
the LEGS' repositories, so before this (docs/triad-lane-tooling-analysis.md
§4.4 and §4.7):

  1. `lane-handoff`'s writer poll never looked in the paired feature trees
     `<assembly>/worktrees/<feature>/{spec,code}`, so a lane with unpushed work
     there was absent from its WRITERS block;
  2. a handoff re-recorded a tree made by `lane-worktrees add --checkout
     <assembly>/code` with the ASSEMBLY as its checkout, so the leg `add` had
     recorded was lost from the inventory at the first handoff;
  3. `lane-reconcile` recomputed from the checkout's own worktree registrations
     and never read the legs', nor the paired root.

Each is held here on an assembly built from openRepoShape's own template bytes
at the pinned commit, with every leg a real git repository behind a bare local
origin and a fake `gh` that exits 1 (the bench of `tests/test_triad_lane_tooling.py`,
imported, so the two modules build one assembly one way). AND THE CONDITION OF
ALL THREE: on a single repository - no `project.yaml`, or one naming no leg but
itself - the handoff's output, its top block, the inventory it writes and the
reconciliation are byte for byte what `c45a452`'s tools printed, even where the
repository is laid out to look like a triad (a submodule with a worktree under
`worktrees/<feature>/code`, and a tree recorded with the submodule as its
checkout). That "before" is STORED (`tests/fixtures/t018-handoff/`), generated
ONCE from `c45a452`'s own tools by this module's `--capture`, because CI checks
out at depth 1; `tests/test_triad_lane_tooling.py`'s own golden covers the
ordinary single repository and keeps passing unregenerated.

NOTHING REAL IS TOUCHED: every repository, origin, register, `$HOME` and state
directory is under `tmp_path`, and the network is never reached.
"""

from __future__ import annotations

import difflib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import NEEDS_UPSTREAM, REPO, WINDOWS_SKIP  # noqa: E402
from test_triad_lane_tooling import (  # noqa: E402
    US, Bench, build_assembly, normalise, parse_golden, porcelain_rows, render_golden, shown)

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="the lane tools are bash and Python over git")]

GOLDEN = (Path(__file__).resolve().parent / "fixtures" / "t018-handoff"
          / "single-repository-decoys.golden")


# ================================================================== helpers

def inventory(b: Bench, lane: str) -> dict:
    """{path: checkout} of the lane's #97 inventory, `lane-trees`' tenth field."""
    proc = b.tool("lanes-edit.sh", "lane-trees", lane)
    assert proc.returncode in (0, 8), proc.stderr
    rows = {}
    for line in proc.stdout.splitlines():
        cols = line.split(US)
        if len(cols) > 9:
            rows[cols[1]] = cols[9]
    return rows


def reconcile_rows(out: str) -> dict:
    """{physical path: (class, why)} of `lane-reconcile`'s TREE rows. Keyed by
    the PHYSICAL path, because git's registrations are spelled physically and
    a recorded tree as it was polled (macOS keeps `$TMPDIR` under `/var`, a
    symlink); look a path up with `real()`."""
    rows = {}
    for line in out.splitlines():
        cols = line.split(US)
        if cols[0] == "TREE" and len(cols) > 4:
            rows[real(cols[3])] = (cols[2], cols[4])
    return rows


def real(path) -> str:
    return os.path.realpath(str(path))


def field(out: str, key: str) -> list:
    return next((ln.split(US)[1:] for ln in out.splitlines() if ln.split(US)[0] == key), [])


def handoff(b: Bench, lane: str, cwd: Path, why: str = "t018 handoff",
            *flags: str) -> subprocess.CompletedProcess:
    return b.tool("lane-handoff", "--lane", lane, "--transcript", "none", "--agent", "claude",
                  *flags, why, cwd=cwd)


def writers_file(b: Bench, lane: str, rows: dict) -> Path:
    """A `--writers-file`: `<worktree> TAB <brief>`, one a line."""
    path = b.root / f"writers-{lane}.tsv"
    path.write_text("".join(f"{tree}\t{brief}\n" for tree, brief in rows.items()))
    return path


def top_block(b: Bench, lane: str) -> str:
    return (b.wip / "handoffs" / f"{lane}.md").read_text().split("\n---\n", 1)[0]


def git_says(b: Bench, leg: Path) -> str:
    """WHAT EVERY READER QUOTES for a leg git cannot read - the sweep's
    `probe_leg`, `lane-reconcile` and `lane-handoff` alike: git's own answer to
    `rev-parse --show-toplevel` in the leg, its first non-empty error line, or
    `git answers <toplevel> there` where git names another checkout. Asked of
    the git under test, never spelled here, because git words the same
    condition differently by version: for a `.git` file naming a directory that
    does not exist, 2.43 says `fatal: not a git repository: <that path>` and
    2.55 (CI's ubuntu runner, PR #246) says `fatal: not a git repository:
    (null)`. The tools read the CONDITION (git's toplevel there is not the leg,
    and a `.git` stands in it); only this quoted clause is git's."""
    proc = b.run("git", "-C", leg, "rev-parse", "--show-toplevel")
    if proc.returncode == 0:
        return f"git answers {proc.stdout.strip()} there"
    return next((ln.strip() for ln in proc.stderr.splitlines() if ln.strip()), "no answer")


def leg_tree(b: Bench, leg: Path, path: Path, branch: str) -> Path:
    """A worktree of `leg`'s repository at `path`, on a new branch from origin/main."""
    b.git("worktree", "add", "-q", "-b", branch, path, "origin/main", cwd=leg)
    return path


@pytest.fixture
def triad(tmp_path):
    b = Bench(tmp_path / "bench", REPO)
    t = build_assembly(b)
    b.lanes("opensoft/triad", t["assembly"], "triad-1", "triad-2")
    return b, t


# ============================================================= (1) and (2)

@NEEDS_UPSTREAM
def test_t018_the_handoff_polls_the_paired_trees_and_records_each_tree_under_its_leg(triad):
    """(1) THE PAIRED TREES ARE POLLED: a paired code tree holding the lane's
    unpushed commit and a paired spec tree holding a writer's first edit are in
    the WRITERS block, and what under the paired root is not a checkout of its
    own is not. (2) EACH TREE IS RECORDED UNDER ITS LEG: the code tree `add`
    made with `--checkout <assembly>/code` keeps the leg as its checkout through
    the handoff, the paired trees are recorded under theirs, and a tree of the
    assembly itself is still recorded under the assembly. The reconciliation
    then reads every one of them as inventoried, never as unmanaged."""
    b, t = triad
    a, code, spec = t["assembly"], t["code"], t["spec"]
    made = b.tool("lane-worktrees", "add", "triad-1", "c1", "--checkout", code)
    assert made.returncode == 0, made.stderr
    lane_code = Path(made.stdout.strip())
    assert inventory(b, "triad-1")[str(lane_code)] == str(code)
    b.commit(lane_code, "the slice's code", {"c1.txt": "c1\n"}, lane="triad-1")
    made = b.tool("lane-worktrees", "add", "triad-1", "root")
    assert made.returncode == 0, made.stderr
    lane_root = Path(made.stdout.strip())
    paired_code = leg_tree(b, code, a / "worktrees" / "007-y" / "code", "007-y")
    b.commit(paired_code, "the feature's code", {"f.txt": "f\n"}, lane="triad-1")
    paired_spec = leg_tree(b, spec, a / "worktrees" / "007-y" / "spec", "007-y")
    (paired_spec / "draft.md").write_text("a writer's first edit\n")
    # under the paired root and NOT a checkout of its own: the assembly's tree
    (a / "worktrees" / "007-y" / "notes").mkdir()
    (a / "worktrees" / "007-y" / "notes" / "n.md").write_text("n\n")
    # the spec writer has committed nothing, so no trailer finds it: the
    # writers file names it, and that makes it this lane's (M1 (a))
    wf = writers_file(b, "triad-1", {paired_spec: "the 007-y spec writer"})

    proc = handoff(b, "triad-1", a, "t018 handoff", "--writers-file", str(wf))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for tree, branch in ((lane_code, "c1"), (lane_root, "root"), (paired_code, "007-y"),
                         (paired_spec, "007-y")):
        assert f"WRITER {tree} — branch {branch}" in proc.stdout, proc.stdout
    for not_one in (a / "worktrees" / "007-y" / "notes", a / "worktrees" / "007-y"):
        assert f"WRITER {not_one} —" not in proc.stdout, proc.stdout
    assert f"writers polled: 4 under {a}" in proc.stderr, proc.stderr
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout
    assert "NOT POLLED" not in proc.stdout + proc.stderr

    block = top_block(b, "triad-1")
    assert f"(4 found under `{a}`)" in block, block
    assert (f"- `{paired_code}` — branch `007-y`, last commit" in block
            and "0 dirty, 1 unpushed" in block.split(f"`{paired_code}`", 1)[1].split("\n", 1)[0]), block
    assert "1 dirty, 0 unpushed" in block.split(f"`{paired_spec}`", 1)[1].split("\n", 1)[0], block
    assert "brief: the 007-y spec writer" in block, block
    assert "PAIRED ROOT" not in block and "PAIRED ROOT" not in proc.stdout, block

    inv = inventory(b, "triad-1")
    assert inv == {str(lane_code): str(code), str(lane_root): str(a),
                   str(paired_code): str(code), str(paired_spec): str(spec)}, inv

    rec = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
    assert rec.returncode == 0, rec.stderr
    rows = reconcile_rows(rec.stdout)
    assert rows[real(paired_code)][0] == "unpushed", rows
    assert rows[real(paired_spec)][0] == "dirty", rows
    assert not [p for p, (cls, _w) in rows.items() if cls in ("unmanaged", "stale-registration")], rows
    assert field(rec.stdout, "TREES")[0] == "4 inventoried", rec.stdout


@NEEDS_UPSTREAM
def test_t018_a_leg_that_is_not_checked_out_claims_no_tree_of_the_assembly(triad):
    """A LEG THAT IS NOT CHECKED OUT is an empty directory of the assembly's,
    where git answers the ASSEMBLY - so read naively, its repository would be
    the assembly's and every tree of the assembly would be recorded under it.
    Deinitialized, the spec leg names no tree; the code leg still names its own."""
    b, t = triad
    a, code = t["assembly"], t["code"]
    b.git("submodule", "deinit", "-q", "spec", cwd=a)
    assert not any((a / "spec").iterdir())
    made = b.tool("lane-worktrees", "add", "triad-1", "root")
    assert made.returncode == 0, made.stderr
    lane_root = Path(made.stdout.strip())
    paired_code = leg_tree(b, code, a / "worktrees" / "008-z" / "code", "008-z")
    b.commit(paired_code, "the feature's code", {"z.txt": "z\n"}, lane="triad-1")
    proc = handoff(b, "triad-1", a)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"writers polled: 2 under {a}" in proc.stderr, proc.stderr
    # not checked out is no unreadable leg: it has no `.git` of its own
    assert f"the leg {a / 'spec'} is unreadable" not in proc.stderr, proc.stderr
    assert "UNREADABLE LEG" not in top_block(b, "triad-1")
    assert inventory(b, "triad-1") == {str(lane_root): str(a), str(paired_code): str(code)}


@NEEDS_UPSTREAM
def test_t018_a_manifest_the_handoff_cannot_read_is_said_and_the_handoff_goes_on(triad):
    """A `project.yaml` that is there and cannot be read is never "no legs"
    (Amendment 7(d)), and a swap is never left unwritten (`R-A11-11`): the
    handoff exits 0, the paired root is NOT polled and the top block says so,
    a tree of the assembly's own repository is recorded as always, a tree of a
    leg keeps the checkout `add` recorded rather than one nobody could
    establish, and the lane stays SWAPPING."""
    b, t = triad
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file")
    a, code = t["assembly"], t["code"]
    made = b.tool("lane-worktrees", "add", "triad-1", "c1", "--checkout", code)
    assert made.returncode == 0, made.stderr
    lane_code = Path(made.stdout.strip())
    made = b.tool("lane-worktrees", "add", "triad-1", "root")
    assert made.returncode == 0, made.stderr
    lane_root = Path(made.stdout.strip())
    paired_code = leg_tree(b, code, a / "worktrees" / "009-w" / "code", "009-w")
    b.commit(paired_code, "the feature's code", {"w.txt": "w\n"}, lane="triad-1")
    os.chmod(a / "project.yaml", 0)
    try:
        proc = handoff(b, "triad-1", a, "unreadable manifest")
    finally:
        os.chmod(a / "project.yaml", 0o644)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (f"the legs of the assembly {a} could not be read (its project.yaml is there, "
            "and ") in proc.stderr, proc.stderr
    assert "paired feature trees" in proc.stderr and "were NOT polled" in proc.stderr
    assert f"WRITER {paired_code} —" not in proc.stdout, proc.stdout
    assert f"WRITER {lane_code} —" in proc.stdout and f"WRITER {lane_root} —" in proc.stdout
    assert f"the worktree inventory entry for {lane_code} was NOT written" in proc.stderr
    assert "lifecycle: SWAPPING" in proc.stdout, proc.stdout
    assert "the assembly's legs could not be read" in proc.stderr
    block = top_block(b, "triad-1")
    assert "- NOT POLLED: " in block and f"`{a}/worktrees`" in block, block
    assert inventory(b, "triad-1") == {str(lane_code): str(code), str(lane_root): str(a)}


@NEEDS_UPSTREAM
def test_t018_a_handoff_takes_no_other_lanes_paired_tree(triad):
    """M1 OF THE PRE-PR REVIEW, OPTION (a): THE PAIRED ROOT IS POLLED BY THE
    SWEEP'S RULE. Two lanes share one assembly, and its paired root holds lane
    2's trees: one whose HEAD's own trailer is lane 2's, unpushed, and one with
    nothing committed that only lane 2's writers file names. Lane 1's handoff
    neither polls, counts nor records either - each is one `PAIRED ROOT, not
    this lane's` line outside WRITERS - so lane 1's `lane-end` passes; and lane
    2's handoff polls and records both, each under its leg."""
    b, t = triad
    a, code, spec = t["assembly"], t["code"], t["spec"]
    theirs = leg_tree(b, code, a / "worktrees" / "020-b" / "code", "020-b")
    b.commit(theirs, "lane 2's feature code", {"b.txt": "b\n"}, lane="triad-2")
    fresh = leg_tree(b, spec, a / "worktrees" / "021-c" / "spec", "021-c")
    (fresh / "draft.md").write_text("lane 2's writer's first edit\n")
    wf2 = writers_file(b, "triad-2", {fresh: "lane 2's 021-c spec writer"})

    one = handoff(b, "triad-1", a)
    assert one.returncode == 0, one.stdout + one.stderr
    for tree in (theirs, fresh):
        assert f"WRITER {tree} —" not in one.stdout, one.stdout
        assert f"PAIRED ROOT, not this lane's: {tree} — branch" in one.stdout, one.stdout
    assert f"writers polled: 0 under {a}" in one.stderr, one.stderr
    assert "paired root: 2 tree(s)" in one.stderr, one.stderr
    assert "lifecycle: SWAPPED" in one.stdout, one.stdout
    assert "NOT POLLED" not in one.stdout + one.stderr
    block = top_block(b, "triad-1")
    writers, _sep, rest = block.partition("**PAIRED ROOT at ")
    assert "(0 found under" in writers and "- none running at the handoff." in writers, block
    assert str(theirs) not in writers and str(fresh) not in writers, block
    assert f"2 tree(s) under `{a}/worktrees` that are NOT this lane's" in rest, block
    assert (f"- PAIRED ROOT, not this lane's: `{theirs}` — branch `020-b`, last commit "
            in rest), block
    assert "HEAD's own `Lane:` trailer `triad-2`" in rest, block
    assert f"- PAIRED ROOT, not this lane's: `{fresh}` — branch `021-c`" in rest, block
    assert "HEAD's own `Lane:` trailer none" in rest, block
    assert inventory(b, "triad-1") == {}
    end = b.tool("lane-end", "triad-1")
    assert end.returncode == 0, end.stdout + end.stderr

    two = handoff(b, "triad-2", a, "t018 handoff", "--writers-file", str(wf2))
    assert two.returncode == 0, two.stdout + two.stderr
    for tree in (theirs, fresh):
        assert f"WRITER {tree} —" in two.stdout, two.stdout
    assert f"writers polled: 2 under {a}" in two.stderr, two.stderr
    assert "PAIRED ROOT" not in two.stdout and "PAIRED ROOT" not in top_block(b, "triad-2")
    assert inventory(b, "triad-2") == {str(theirs): str(code), str(fresh): str(spec)}


@NEEDS_UPSTREAM
def test_t018_a_paired_directory_the_handoff_cannot_list_is_said_and_the_lane_stays_swapping(triad):
    """S1 OF THE PRE-PR REVIEW: a paired root, a feature directory, or a leg's
    directory under one that could not be listed or searched hid what stood in
    it from the poll IN SILENCE, while `lane-reconcile` said `indeterminate`
    and the sweep refused. Now each is a `- NOT POLLED` line in WRITERS and a
    note on stderr, the handoff still exits 0 (`R-A11-11`), and the lane stays
    SWAPPING; the reconciliation is `indeterminate` for every one of them."""
    b, t = triad
    if os.geteuid() == 0:
        pytest.skip("root lists and searches a mode-000 directory")
    a, code = t["assembly"], t["code"]
    mine = leg_tree(b, code, a / "worktrees" / "030-m" / "code", "030-m")
    b.commit(mine, "the lane's feature code", {"m.txt": "m\n"}, lane="triad-1")
    clone = a / "worktrees" / "031-n" / "spec"
    b.git("clone", "-q", b.remotes / "triad-spec.git", clone)
    cases = (
        (a / "worktrees", f"the assembly's paired root {a}/worktrees could not be listed", False),
        (a / "worktrees" / "030-m",
         f"the assembly's feature directory {a}/worktrees/030-m could not be listed", False),
        (clone, f"the assembly's paired tree directory {clone} could not be searched", True),
    )
    for target, words, mine_seen in cases:
        os.chmod(target, 0)
        try:
            proc = handoff(b, "triad-1", a, "unlistable")
            rec = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
        finally:
            os.chmod(target, 0o755)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert (f"WRITER {mine} —" in proc.stdout) is mine_seen, (target, proc.stdout)
        assert words in proc.stderr, (target, proc.stderr)
        assert "may not have been polled" in proc.stderr, (target, proc.stderr)
        assert "lifecycle: SWAPPING" in proc.stdout, (target, proc.stdout)
        assert f"- NOT POLLED: {words}" in top_block(b, "triad-1"), target
        verdict = field(rec.stdout, "VERDICT")
        assert verdict and verdict[0] == "indeterminate", (target, rec.stdout)
        assert words in verdict[1], (target, verdict)
    proc = handoff(b, "triad-1", a, "readable again")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"WRITER {mine} — branch 030-m" in proc.stdout, proc.stdout
    assert f"PAIRED ROOT, not this lane's: {clone} —" in proc.stdout, proc.stdout
    assert "NOT POLLED" not in proc.stdout + proc.stderr
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout


@NEEDS_UPSTREAM
def test_t018_a_tree_of_a_nested_dependency_keeps_the_checkout_add_recorded(triad):
    """N5 OF THE PRE-PR REVIEW: a tree `add` made from a dependency nested in a
    leg (`--checkout <assembly>/code/upstream/dep`) is no declared leg's, and
    the next handoff re-recorded it under the assembly - the loss (b) fixed for
    the legs. A recorded checkout of the tree's own repository is now kept."""
    b, t = triad
    dep = t["dep"]
    made = b.tool("lane-worktrees", "add", "triad-1", "d1", "--checkout", dep)
    assert made.returncode == 0, made.stderr
    tree = made.stdout.strip()
    assert inventory(b, "triad-1")[tree] == str(dep)
    proc = handoff(b, "triad-1", t["assembly"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"WRITER {tree} —" in proc.stdout, proc.stdout
    assert inventory(b, "triad-1")[tree] == str(dep)


# ===================================================================== (3)

@NEEDS_UPSTREAM
def test_t018_reconcile_reports_what_the_legs_hold_and_no_sidecar_names(triad):
    """(3) THE LEGS' REGISTRATIONS AND THE PAIRED ROOT ARE READ: a spec tree
    made away from every root, a paired code tree, a clone where a paired
    worktree belongs and a registration whose directory is gone are each
    reported - unmanaged or stale - naming the leg, while a tree the inventory
    records is not, and neither leg's own checkout is."""
    b, t = triad
    a, code, spec = t["assembly"], t["code"], t["spec"]
    away = leg_tree(b, spec, b.projects / "away-spec", "away")
    paired = leg_tree(b, code, a / "worktrees" / "010-v" / "code", "010-v")
    clone = a / "worktrees" / "010-v" / "spec"
    b.git("clone", "-q", b.remotes / "triad-spec.git", clone)
    gone = leg_tree(b, code, b.projects / "gone-code", "gone")
    shutil.rmtree(gone)
    made = b.tool("lane-worktrees", "add", "triad-1", "c1", "--checkout", code)
    assert made.returncode == 0, made.stderr
    recorded = made.stdout.strip()

    proc = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
    assert proc.returncode == 0, proc.stderr
    rows = reconcile_rows(proc.stdout)
    assert rows[real(away)][0] == "unmanaged", rows
    assert f"git registers it in {spec}, the spec leg of {a}/project.yaml (opensoft/triad-spec)" \
        in rows[real(away)][1], rows
    assert rows[real(paired)][0] == "unmanaged", rows
    assert f"the code leg of {a}/project.yaml" in rows[real(paired)][1], rows
    assert rows[real(clone)][0] == "unmanaged", rows
    assert f"paired feature trees ({a}/worktrees)" in rows[real(clone)][1], rows
    assert rows[real(gone)][0] == "stale-registration", rows
    assert f"git -C {code} worktree prune" in rows[real(gone)][1], rows
    assert rows[real(recorded)][0] == "ok", rows
    for not_a_tree in (a, code, spec, a / ".git" / "modules" / "code", a / ".git" / "modules" / "spec",
                       a / "worktrees" / "010-v"):
        assert real(not_a_tree) not in rows, rows
    assert field(proc.stdout, "TREES") == ["1 inventoried", "0 dirty or unpushed",
                                           "0 require recovery", "4 unmanaged or stale"], proc.stdout
    assert field(proc.stdout, "VERDICT")[0] == "ungraceful-stop", proc.stdout


@NEEDS_UPSTREAM
def test_t018_reconcile_pronounces_no_clearance_over_legs_nobody_read(triad):
    """A manifest, or the paired root, that could not be read leaves paths
    nobody inspected: the verdict is `indeterminate`, never a clearance."""
    b, t = triad
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file")
    a, code = t["assembly"], t["code"]
    paired = leg_tree(b, code, a / "worktrees" / "011-u" / "code", "011-u")
    os.chmod(a / "project.yaml", 0)
    try:
        proc = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
    finally:
        os.chmod(a / "project.yaml", 0o644)
    assert proc.returncode == 0, proc.stderr
    verdict = field(proc.stdout, "VERDICT")
    assert verdict[0] == "indeterminate", proc.stdout
    assert (f"the legs of the assembly {a} could not be read (its project.yaml is there and "
            "unreadable)") in verdict[1], verdict
    assert real(paired) not in reconcile_rows(proc.stdout)
    # the paired root that cannot be listed: a clone stands in it, which only
    # the listing could find (a registered tree is found through its leg)
    b.git("worktree", "remove", paired, cwd=code)
    b.git("clone", "-q", b.remotes / "triad-code.git", a / "worktrees" / "012-t" / "code")
    os.chmod(a / "worktrees", 0)
    try:
        proc = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
    finally:
        os.chmod(a / "worktrees", 0o755)
    assert proc.returncode == 0, proc.stderr
    verdict = field(proc.stdout, "VERDICT")
    assert verdict[0] == "indeterminate", proc.stdout
    assert f"the assembly's paired root {a}/worktrees could not be listed" in verdict[1], verdict


@NEEDS_UPSTREAM
def test_t018_reconcile_reports_a_leg_git_cannot_read_as_the_sweep_counts_it(triad):
    """A LEG WITH A `.git` OF ITS OWN THAT GIT CANNOT READ was passed over by
    the reconciliation IN SILENCE, as a leg that is not checked out is, while
    the sweep's `leg` row for it is `unreadable` and counted. Now it is the
    sweep's rule and the sweep's word: one TREE row, `unreadable`, that requires
    recovery - for a `.git` naming no repository, and for one where git answers
    the assembly. Its verdict is no `indeterminate`, so the sweep still lists
    and counts that leg (exit 3) rather than refusing on the verdict. Readable
    again, or not checked out at all, the leg names nothing."""
    b, t = triad
    a, spec = t["assembly"], t["spec"]
    gitfile = (spec / ".git").read_text()

    def reconciled_rows() -> tuple:
        rec = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
        assert rec.returncode == 0, rec.stderr
        return rec, reconcile_rows(rec.stdout)

    def check(answer: str) -> None:
        rec, rows = reconciled_rows()
        assert list(rows) == [real(spec)], rows
        cls, why = rows[real(spec)]
        assert cls == "unreadable", rows
        assert why.startswith(f"the spec leg of {a}/project.yaml (opensoft/triad-spec): git could "
                              "not be read through it (it has a .git of its own and git could not "
                              "read it: "), why
        assert answer in why and f"(git -C {spec} status)" in why, (answer, why)
        # N2 of the review of bf2a220: a leg is the assembly's, not a writer's tree
        assert why.endswith("before relaunching a writer onto a tree of its repository"), why
        assert field(rec.stdout, "TREES") == ["0 inventoried", "0 dirty or unpushed",
                                              "1 require recovery", "0 unmanaged or stale"], rec.stdout
        assert field(rec.stdout, "VERDICT")[0] == "ungraceful-stop", rec.stdout
        sweep = b.sweep("triad-1", "--dry-run", "--porcelain")
        assert sweep.returncode == 3, sweep.stdout + sweep.stderr
        leg = porcelain_rows(sweep.stdout, "leg")[str(spec)]
        assert leg["disposition"] == "unreadable" and leg["retire"] == "retire", leg
        assert "git could not be read through it" in leg["why"] and answer in leg["why"], leg

    (spec / ".git").write_text("gitdir: /nonexistent/t018-spec\n")
    check(git_says(b, spec))
    (spec / ".git").unlink()
    (spec / ".git").mkdir()
    check(f"git answers {real(a)} there")
    shutil.rmtree(spec / ".git")
    (spec / ".git").write_text(gitfile)
    for state in ("readable again", "deinitialized"):
        if state == "deinitialized":
            b.git("submodule", "deinit", "-q", "spec", cwd=a)
            assert not any(spec.iterdir())
        rec, rows = reconciled_rows()
        assert real(spec) not in rows, (state, rows)
        assert field(rec.stdout, "TREES")[2] == "0 require recovery", (state, rec.stdout)


@NEEDS_UPSTREAM
def test_t018_the_handoff_reports_a_leg_git_cannot_read_as_the_sweep_counts_it(triad):
    """THE SAME SILENT SKIP IN `lane-handoff`: a leg with a `.git` of its own
    that git cannot read was passed over as a leg that is not checked out is,
    so the handoff said nothing of it, and a tree `add` made from that leg was
    re-recorded under the ASSEMBLY - the loss (2) fixed. Now it is the sweep's
    rule and word: one `- UNREADABLE LEG` line in WRITERS, a note on stderr and
    a count, for a `.git` naming no repository and for one where git answers
    the assembly. The lifecycle is not held for the leg itself (the
    reconciliation's verdict is not `indeterminate` for it either): with no
    tree of that leg the lane is SWAPPED. A tree of that leg keeps the checkout
    `add` recorded - named, NOT recorded, and the lane stays SWAPPING for it -
    while a tree of the assembly is recorded as always. Readable again, the
    leg names nothing and its tree is recorded under it."""
    b, t = triad
    a, spec = t["assembly"], t["spec"]
    made = b.tool("lane-worktrees", "add", "triad-1", "root")
    assert made.returncode == 0, made.stderr
    lane_root = Path(made.stdout.strip())
    gitfile = (spec / ".git").read_text()
    words = (f"the spec leg of {a}/project.yaml (opensoft/triad-spec): git could not be read "
             "through it (it has a .git of its own and git could not read it: ")

    def check(answer: str, trees: tuple, unplaced: tuple, state: str) -> None:
        proc = handoff(b, "triad-1", a, "unreadable leg")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert f"the leg {spec} is unreadable: {words}" in proc.stderr, proc.stderr
        assert answer in proc.stderr.split(f"the leg {spec} is unreadable: ", 1)[1], proc.stderr
        assert f"legs: 1 of the assembly's legs under {a} unreadable" in proc.stderr, proc.stderr
        assert f"writers polled: {len(trees)} under {a}" in proc.stderr, proc.stderr
        for tree in trees:
            assert f"WRITER {tree} —" in proc.stdout, proc.stdout
            missed = f"the worktree inventory entry for {tree} was NOT written: "
            if tree in unplaced:
                assert (missed + "the assembly has 1 unreadable leg(s), each named by an "
                        "UNREADABLE LEG line in the top block") in proc.stderr, proc.stderr
            else:
                assert missed not in proc.stderr, proc.stderr
        assert f"lifecycle: {state}" in proc.stdout, proc.stdout
        assert "NOT POLLED" not in proc.stdout + proc.stderr
        writers = top_block(b, "triad-1").split("**WRITERS at ", 1)[1]
        line = next((ln for ln in writers.splitlines() if ln.startswith("- UNREADABLE LEG: ")), "")
        assert line.startswith(f"- UNREADABLE LEG: `{spec}` is unreadable, {words}"), writers
        assert answer in line and f"(`git -C {spec} status`)" in line, line
        assert writers.count("- UNREADABLE LEG: ") == 1, writers
        # N2 of the review of bf2a220: a leg is the assembly's, not a writer's tree
        assert line.endswith("before relaunching a writer onto a tree of its repository."), line
        assert proc.stderr.split(f"the leg {spec} is unreadable: ", 1)[1].split("\n", 1)[0] \
            .endswith("before relaunching a writer onto a tree of its repository."), proc.stderr
        # N1: the leg's line says what was withheld, and a withheld tree's own line
        # says it is NOT recorded, where a recorded tree's line does not
        if unplaced:
            assert (f"the {len(unplaced)} tree(s) this handoff could not place are named "
                    "above, each marked (NOT recorded)") in line, line
        else:
            assert ("every tree this handoff polled could still be placed, so none is "
                    "withheld for it") in line, line
        for tree in trees:
            assert (f"- `{tree}` (NOT recorded) — branch `" in writers) is (tree in unplaced), \
                (tree, writers)
            assert (f"- `{tree}` — branch `" in writers) is (tree not in unplaced), (tree, writers)

    (spec / ".git").write_text("gitdir: /nonexistent/t018-spec\n")
    check(git_says(b, spec), (lane_root,), (), "SWAPPED")
    assert inventory(b, "triad-1") == {str(lane_root): str(a)}
    rec = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
    assert reconcile_rows(rec.stdout)[real(spec)][0] == "unreadable", rec.stdout
    assert field(rec.stdout, "TREES")[2] == "1 require recovery", rec.stdout
    assert field(rec.stdout, "VERDICT")[0] == "resumable", rec.stdout
    (spec / ".git").unlink()
    (spec / ".git").mkdir()
    check(f"git answers {real(a)} there", (lane_root,), (), "SWAPPED")
    shutil.rmtree(spec / ".git")
    (spec / ".git").write_text(gitfile)

    made = b.tool("lane-worktrees", "add", "triad-1", "s1", "--checkout", spec)
    assert made.returncode == 0, made.stderr
    lane_spec = Path(made.stdout.strip())
    want = {str(lane_spec): str(spec), str(lane_root): str(a)}
    assert inventory(b, "triad-1") == want
    (spec / ".git").write_text("gitdir: /nonexistent/t018-spec\n")
    check(git_says(b, spec), (lane_spec, lane_root), (lane_spec,), "SWAPPING")
    assert inventory(b, "triad-1") == want

    (spec / ".git").write_text(gitfile)
    proc = handoff(b, "triad-1", a, "readable again")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"the leg {spec} is unreadable" not in proc.stderr, proc.stderr
    assert "of the assembly's legs under" not in proc.stderr, proc.stderr
    assert "UNREADABLE LEG" not in top_block(b, "triad-1")
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout
    assert inventory(b, "triad-1") == want


@NEEDS_UPSTREAM
def test_t018_an_unreadable_leg_withholds_no_tree_of_another_repository(triad):
    """S1 OF THE REVIEW OF bf2a220: while a leg was unreadable, the handoff
    withheld EVERY tree that was not of the assembly's own repository - a
    worktree of an unrelated repository in the lane's own root included, as
    lane openRepoTools-3's root holds today - so the lane stayed SWAPPING on
    every handoff and those trees' records went stale for as long as the leg
    stayed broken. Now only a tree that could be of the leg's repository is
    withheld: one whose common git directory lies inside the assembly, or one
    the inventory records under the unreadable leg. A worktree of a third
    repository, recorded before or new, is recorded under the lane's `dir` as
    when every leg reads, and with nothing else withheld the lane is SWAPPED."""
    b, t = triad
    a, spec = t["assembly"], t["spec"]
    third = b.projects / "third"
    b.git("clone", "-q", b.seeded("third", {"t.txt": "a third repository\n"}), third)
    root = b.projects / ".lane-worktrees" / "triad-1"
    before = leg_tree(b, third, root / "nw-before", "nw-before")
    proc = handoff(b, "triad-1", a, "every leg reads")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert inventory(b, "triad-1") == {str(before): str(a)}

    (spec / ".git").write_text("gitdir: /nonexistent/t018-spec\n")
    after = leg_tree(b, third, root / "nw-after", "nw-after")
    proc = handoff(b, "triad-1", a, "unreadable leg")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"the leg {spec} is unreadable: " in proc.stderr, proc.stderr
    assert f"writers polled: 2 under {a}" in proc.stderr, proc.stderr
    for tree in (before, after):
        assert f"WRITER {tree} — branch {tree.name}" in proc.stdout, proc.stdout
        assert f"the worktree inventory entry for {tree} was NOT written" not in proc.stderr, \
            proc.stderr
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout
    writers = top_block(b, "triad-1").split("**WRITERS at ", 1)[1]
    assert "(NOT recorded)" not in writers, writers
    assert ("every tree this handoff polled could still be placed, so none is withheld "
            "for it") in writers, writers
    assert inventory(b, "triad-1") == {str(before): str(a), str(after): str(a)}

    # A RECORD NAMING THE UNREADABLE LEG still withholds its tree, whatever
    # repository the tree's own common directory says it is of.
    named = leg_tree(b, third, root / "nw-named", "nw-named")
    rec = b.tool("lanes-edit.sh", "set-lane-tree", "triad-1", named, "--checkout", spec)
    assert rec.returncode == 0, rec.stderr
    proc = handoff(b, "triad-1", a, "unreadable leg, and a record naming it")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (f"the worktree inventory entry for {named} was NOT written: the assembly has 1 "
            "unreadable leg(s)") in proc.stderr, proc.stderr
    for tree in (before, after):
        assert f"the worktree inventory entry for {tree} was NOT written" not in proc.stderr, \
            proc.stderr
    assert "lifecycle: SWAPPING" in proc.stdout, proc.stdout
    writers = top_block(b, "triad-1").split("**WRITERS at ", 1)[1]
    assert f"- `{named}` (NOT recorded) — branch `nw-named`" in writers, writers
    for tree in (before, after):
        assert f"- `{tree}` — branch `{tree.name}`" in writers, writers
    assert ("the 1 tree(s) this handoff could not place are named above, each marked "
            "(NOT recorded)") in writers, writers
    assert inventory(b, "triad-1") == {str(before): str(a), str(after): str(a),
                                       str(named): str(spec)}


@NEEDS_UPSTREAM
def test_t018_a_tree_git_cannot_read_in_an_assembly_is_named_and_holds_the_lane_swapping(triad):
    """S2 OF THE REVIEW OF bf2a220: the poll passed over IN SILENCE any tree
    with a `.git` git cannot read. With the spec leg's module directory
    deleted after `add --checkout spec`, every tree of that leg - the one
    `add` made, and a paired spec tree the inventory names - vanished from
    WRITERS and from its count, and the lane went SWAPPED. Now each is listed
    and counted, `UNREADABLE` and `(NOT recorded)`, its record is kept, and
    the lane stays SWAPPING. Scoped to assemblies: a single repository's tree
    that git cannot read is passed over, as it always was."""
    b, t = triad
    a, spec = t["assembly"], t["spec"]
    made = b.tool("lane-worktrees", "add", "triad-1", "s1", "--checkout", spec)
    assert made.returncode == 0, made.stderr
    lane_spec = Path(made.stdout.strip())
    made = b.tool("lane-worktrees", "add", "triad-1", "root")
    assert made.returncode == 0, made.stderr
    lane_root = Path(made.stdout.strip())
    paired_spec = leg_tree(b, spec, a / "worktrees" / "040-p" / "spec", "040-p")
    b.commit(paired_spec, "the feature's spec", {"p.md": "p\n"}, lane="triad-1")
    proc = handoff(b, "triad-1", a, "every leg reads")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    want = {str(lane_spec): str(spec), str(lane_root): str(a), str(paired_spec): str(spec)}
    assert inventory(b, "triad-1") == want

    shutil.rmtree(a / ".git" / "modules" / "spec")
    proc = handoff(b, "triad-1", a, "the spec leg's module directory is gone")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"the leg {spec} is unreadable: " in proc.stderr, proc.stderr
    assert f"writers polled: 3 under {a}" in proc.stderr, proc.stderr
    assert f"WRITER {lane_root} — branch root" in proc.stdout, proc.stdout
    block = top_block(b, "triad-1")
    assert f"(3 found under `{a}`)" in block, block
    writers = block.split("**WRITERS at ", 1)[1]
    for tree in (lane_spec, paired_spec):
        assert (f"WRITER {tree} — UNREADABLE: it has a .git of its own and git could not "
                "read it: ") in proc.stdout, proc.stdout
        assert (f"the worktree inventory entry for {tree} was NOT written: it has a .git of "
                "its own and git could not read it") in proc.stderr, proc.stderr
        assert (f"- `{tree}` (NOT recorded) — UNREADABLE: it has a .git of its own and git "
                "could not read it (") in writers, writers
        assert f"(`git -C {tree} status`)" in writers, writers
    assert f"- `{lane_root}` — branch `root`" in writers, writers
    assert ("the 2 tree(s) this handoff could not place are named above, each marked "
            "(NOT recorded)") in writers, writers
    assert "lifecycle: SWAPPING" in proc.stdout, proc.stdout
    held = proc.stderr.split("the worktree inventory was not recorded for ", 1)[1].split("\n", 1)[0]
    assert str(lane_spec) in held and str(paired_spec) in held and str(lane_root) not in held, held
    assert inventory(b, "triad-1") == want

    # A SINGLE REPOSITORY PASSES OVER SUCH A TREE, AS IT ALWAYS DID.
    b.origin("plain")
    s = b.projects / "plain"
    b.git("clone", "-q", b.remotes / "plain.git", s)
    b.commit(s, "seed", {"README.md": "plain\n"})
    b.git("push", "-q", "origin", "main", cwd=s)
    b.lanes("opensoft/plain", s, "plain-1")
    made = b.tool("lane-worktrees", "add", "plain-1", "w")
    assert made.returncode == 0, made.stderr
    w = Path(made.stdout.strip())
    admin = (w / ".git").read_text().split("gitdir:", 1)[1].strip()
    shutil.rmtree(admin)
    proc = handoff(b, "plain-1", s, "a tree git cannot read")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"writers polled: 0 under {s}" in proc.stderr, proc.stderr
    assert "UNREADABLE" not in proc.stdout + proc.stderr
    assert "NOT recorded" not in proc.stdout + proc.stderr + top_block(b, "plain-1")
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout


@NEEDS_UPSTREAM
def test_t018_a_leg_tree_add_made_is_withheld_where_the_legs_git_is_an_empty_directory(triad):
    """N4 OF THE REVIEW OF bf2a220: the empty-`.git`-directory case was run
    only with no tree of that leg, and its path differs from the gitfile
    case's: git answers the ASSEMBLY in the leg, so the common directory of
    the checkout the tree's record names is the assembly's own `.git`, not
    nothing. A tree `add --checkout spec` made is still withheld - named,
    marked `(NOT recorded)`, its record kept under the leg and never moved to
    the assembly - and the lane stays SWAPPING; readable again, the tree is
    recorded under its leg and the lane is SWAPPED."""
    b, t = triad
    a, spec = t["assembly"], t["spec"]
    made = b.tool("lane-worktrees", "add", "triad-1", "s1", "--checkout", spec)
    assert made.returncode == 0, made.stderr
    lane_spec = Path(made.stdout.strip())
    want = {str(lane_spec): str(spec)}
    assert inventory(b, "triad-1") == want
    gitfile = (spec / ".git").read_text()
    (spec / ".git").unlink()
    (spec / ".git").mkdir()
    # the path this case takes: in the leg, git answers the assembly
    assert real(b.git("rev-parse", "--show-toplevel", cwd=spec)) == real(a)
    assert real(spec / b.git("rev-parse", "--git-common-dir", cwd=spec)) == real(a / ".git")
    proc = handoff(b, "triad-1", a, "the spec leg's .git is an empty directory")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"the leg {spec} is unreadable: " in proc.stderr, proc.stderr
    assert f"git answers {real(a)} there" in proc.stderr, proc.stderr
    assert f"WRITER {lane_spec} — branch s1" in proc.stdout, proc.stdout
    assert (f"the worktree inventory entry for {lane_spec} was NOT written: the assembly has 1 "
            "unreadable leg(s)") in proc.stderr, proc.stderr
    assert "lifecycle: SWAPPING" in proc.stdout, proc.stdout
    writers = top_block(b, "triad-1").split("**WRITERS at ", 1)[1]
    assert f"- `{lane_spec}` (NOT recorded) — branch `s1`" in writers, writers
    assert ("the 1 tree(s) this handoff could not place are named above, each marked "
            "(NOT recorded)") in writers, writers
    assert inventory(b, "triad-1") == want

    shutil.rmtree(spec / ".git")
    (spec / ".git").write_text(gitfile)
    proc = handoff(b, "triad-1", a, "readable again")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "UNREADABLE LEG" not in top_block(b, "triad-1")
    assert "(NOT recorded)" not in top_block(b, "triad-1")
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout
    assert inventory(b, "triad-1") == want


# ====================================================================== #255

@NEEDS_UPSTREAM
def test_255_a_leg_directory_that_cannot_be_searched_is_unreadable_in_the_handoff_and_reconcile(triad):
    """#255, OPENREPOSHAPE-2'S SHOULD ON #246: A LEG DIRECTORY THIS ACCOUNT
    CANNOT SEARCH failed the handoff's and the reconciliation's `.git` test
    as a leg that is not checked out does, so both passed over it IN SILENCE:
    no UNREADABLE LEG line, no TREE row, and the tree `add --checkout spec`
    made was re-recorded under the ASSEMBLY, over the leg `add` had recorded.
    Now it takes the path of a leg git cannot read, in the sweep's words, with
    no permission at all and with read but no search: named and counted, its
    tree withheld `(NOT recorded)` and its record kept, the lane SWAPPING, and
    one `unreadable` TREE row that requires recovery. Searchable again, it
    names nothing and its tree is recorded under it."""
    b, t = triad
    if os.geteuid() == 0:
        pytest.skip("root searches a directory whatever its mode")
    a, spec = t["assembly"], t["spec"]
    made = b.tool("lane-worktrees", "add", "triad-1", "s1", "--checkout", spec)
    assert made.returncode == 0, made.stderr
    lane_spec = Path(made.stdout.strip())
    made = b.tool("lane-worktrees", "add", "triad-1", "root")
    assert made.returncode == 0, made.stderr
    lane_root = Path(made.stdout.strip())
    want = {str(lane_spec): str(spec), str(lane_root): str(a)}
    assert inventory(b, "triad-1") == want
    words = (f"the spec leg of {a}/project.yaml (opensoft/triad-spec): git could not be read "
             "through it (its directory cannot be searched, so whether it has a .git of its own "
             "could not be tested, and git could not read it: ")
    for mode in (0, 0o600):
        os.chmod(spec, mode)
        try:
            proc = handoff(b, "triad-1", a, "a leg directory that cannot be searched")
            rec = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
        finally:
            os.chmod(spec, 0o755)
        assert proc.returncode == 0, (oct(mode), proc.stdout + proc.stderr)
        assert f"the leg {spec} is unreadable: {words}" in proc.stderr, (oct(mode), proc.stderr)
        assert f"legs: 1 of the assembly's legs under {a} unreadable" in proc.stderr, proc.stderr
        assert f"writers polled: 2 under {a}" in proc.stderr, proc.stderr
        assert f"WRITER {lane_spec} — branch s1" in proc.stdout, proc.stdout
        assert (f"the worktree inventory entry for {lane_spec} was NOT written: the assembly has "
                "1 unreadable leg(s)") in proc.stderr, proc.stderr
        assert f"the worktree inventory entry for {lane_root} was NOT written" not in proc.stderr
        assert "lifecycle: SWAPPING" in proc.stdout, (oct(mode), proc.stdout)
        writers = top_block(b, "triad-1").split("**WRITERS at ", 1)[1]
        assert f"- UNREADABLE LEG: `{spec}` is unreadable, {words}" in writers, (oct(mode), writers)
        assert writers.count("- UNREADABLE LEG: ") == 1, writers
        assert f"- `{lane_spec}` (NOT recorded) — branch `s1`" in writers, writers
        assert f"- `{lane_root}` — branch `root`" in writers, writers
        assert inventory(b, "triad-1") == want
        assert rec.returncode == 0, rec.stderr
        rows = reconcile_rows(rec.stdout)
        assert rows[real(spec)][0] == "unreadable", (oct(mode), rows)
        assert rows[real(spec)][1].startswith(words), (oct(mode), rows[real(spec)])
        assert field(rec.stdout, "TREES")[2] == "1 require recovery", (oct(mode), rec.stdout)
        assert field(rec.stdout, "VERDICT")[0] != "indeterminate", rec.stdout

    proc = handoff(b, "triad-1", a, "searchable again")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"the leg {spec} is unreadable" not in proc.stderr, proc.stderr
    assert "UNREADABLE LEG" not in top_block(b, "triad-1")
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout
    assert inventory(b, "triad-1") == want
    rec = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
    assert real(spec) not in reconcile_rows(rec.stdout), rec.stdout
    assert field(rec.stdout, "TREES")[2] == "0 require recovery", rec.stdout


def lone_sidecar(b: Bench, lane: str) -> Path:
    """The lane's one inventory record, as `set-lane-tree` filed it."""
    files = sorted((b.projects / ".lane-state" / lane / "trees").glob("*.yaml"))
    assert len(files) == 1, files
    return files[0]


def trees_row(b: Bench, lane: str, path: Path, env: dict | None = None) -> list:
    """The `lane-trees` row whose path is `path`, as the handoff's `LANES_EDIT` gives it."""
    helper = (env or {}).get("LANES_EDIT", str(b.bin / "lanes-edit.sh"))
    proc = b.run(helper, "lane-trees", lane, env=env)
    assert proc.returncode == 0, proc.stderr
    rows = [ln.split(US) for ln in proc.stdout.splitlines() if ln.split(US)[1:2] == [str(path)]]
    assert len(rows) == 1, proc.stdout
    return rows[0]


def a_paired_tree_a_broken_record_names(b: Bench, t: dict) -> tuple:
    """A paired spec tree with a writer's first edit and nothing committed - so
    no trailer finds it - recorded in triad-1's inventory with its leg as its
    checkout: (the tree, its record, the record's bytes)."""
    a, spec = t["assembly"], t["spec"]
    fresh = leg_tree(b, spec, a / "worktrees" / "050-r" / "spec", "050-r")
    (fresh / "draft.md").write_text("a writer's first edit\n")
    rec = b.tool("lanes-edit.sh", "set-lane-tree", "triad-1", fresh, "--checkout", spec)
    assert rec.returncode == 0, rec.stderr
    sidecar = lone_sidecar(b, "triad-1")
    text = sidecar.read_text()
    assert text.startswith("schema: 1\n") and f"\npath: {fresh}\n" in text, text
    return fresh, sidecar, text


def assert_the_record_is_named_and_not_polled(b: Bench, t: dict, proc, fresh: Path,
                                              sidecar: Path, before: bytes, schema: str,
                                              path: str | None = None) -> None:
    """THE HANDOFF NAMES A RECORD IT COULD NOT READ (#255): its id, schema and
    path in the NOT POLLED note, on stderr and in the top block; the tree that
    record names is not taken as this lane's writer; nothing is filed over the
    record; and the lane stays SWAPPING. `path` is the path the record keeps
    (the tree, unless told otherwise); `""` is a record that keeps none, which
    the note then names by its id and schema alone."""
    a = t["assembly"]
    kept = str(fresh) if path is None else path
    note = (f"this lane's worktree inventory holds record(s) that could not be read "
            f"({sidecar.stem} (schema {schema}{', path ' + kept if kept else ''})), so a paired "
            "tree only they name could not be told from another lane's")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert note in proc.stderr, proc.stderr
    assert f"- NOT POLLED: {note}" in top_block(b, "triad-1"), top_block(b, "triad-1")
    assert "lifecycle: SWAPPING" in proc.stdout, proc.stdout
    assert f"WRITER {fresh} —" not in proc.stdout, proc.stdout
    assert f"PAIRED ROOT, not this lane's: {fresh} — branch 050-r" in proc.stdout, proc.stdout
    assert f"writers polled: 0 under {a}" in proc.stderr, proc.stderr
    assert sidecar.read_bytes() == before, sidecar.read_text()


@NEEDS_UPSTREAM
@pytest.mark.parametrize("schema", ["2", "10"])
def test_255_an_unknown_schema_record_is_named_in_the_handoffs_not_polled_note(triad, schema):
    """#255: THE INVENTORY'S UNREADABLE RECORDS WERE ONLY THE ONES WITH NO
    PATH. A record of another schema keeps its path and nothing else
    (`lane-trees`' `${ltl_s:-<none>}` row), so the handoff read it as a record
    with an empty checkout: its paired tree became this lane's writer, and the
    poll's record for it was refused by `set-lane-tree`, which writes over no
    record of another schema - reported as a refused write, with nothing said
    of the record. Now a row whose schema - the thirteenth field - is not `1`
    is named in the NOT POLLED note and never read as a record, as the sweep
    reads it (`_discover`). Whole again, the record makes the tree this
    lane's writer, and the lane is SWAPPED. THE SCHEMA IS MATCHED WHOLE: `10`
    begins with a `1` but is not schema 1, so a rule that matched the schema by
    its first character would read this record as a whole schema-1 one."""
    b, t = triad
    a, spec = t["assembly"], t["spec"]
    fresh, sidecar, text = a_paired_tree_a_broken_record_names(b, t)
    sidecar.write_text(f"schema: {schema}\n" + text[len("schema: 1\n"):])
    before = sidecar.read_bytes()
    row = trees_row(b, "triad-1", fresh)
    assert row[0] == sidecar.stem and row[12] == schema and row[9] == "", row
    proc = handoff(b, "triad-1", a, "a record of another schema")
    assert_the_record_is_named_and_not_polled(b, t, proc, fresh, sidecar, before, schema)

    sidecar.write_text(text)
    proc = handoff(b, "triad-1", a, "a whole record again")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"WRITER {fresh} — branch 050-r" in proc.stdout, proc.stdout
    assert "NOT POLLED" not in proc.stdout + proc.stderr
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout
    assert inventory(b, "triad-1") == {str(fresh): str(spec)}


@NEEDS_UPSTREAM
def test_255_a_malformed_record_is_named_in_the_handoffs_not_polled_note(triad):
    """#255, AND #252'S `<malformed>` ROW: a schema-1 record that is not a
    whole one keeps its id, its path and the schema `<malformed>`
    (`lanes-edit.sh` at 36520b9, `lane_trees_list`). Here the record is cut to
    its first four lines, and `LANES_EDIT` is a `lanes-edit.sh` that passes
    every call through but answers `lane-trees` with #252's row for it, so
    this holds before #252 lands and after. The handoff names it in the NOT
    POLLED note, takes its tree for no writer of this lane's, files nothing
    over it, and leaves the lane SWAPPING."""
    b, t = triad
    a, spec = t["assembly"], t["spec"]
    fresh, sidecar, text = a_paired_tree_a_broken_record_names(b, t)
    sidecar.write_text("".join(text.splitlines(keepends=True)[:4]))
    before = sidecar.read_bytes()
    fake = b.root / "fake-lanes-edit.sh"
    fake.write_text(
        "#!/bin/sh\n"
        f"real={shlex.quote(str(b.bin / 'lanes-edit.sh'))}\n"
        "if [ \"${1-}\" = lane-trees ]; then\n"
        "  out=\"$(\"$real\" \"$@\")\"; rc=$?\n"
        "  [ \"$rc\" = 0 ] || { [ -z \"$out\" ] || printf '%s\\n' \"$out\"; exit \"$rc\"; }\n"
        f"  printf '%s\\n' \"$out\" | P={shlex.quote(str(fresh))} awk -F'\\037' '$2 != ENVIRON[\"P\"]'\n"
        f"  printf '%s\\037%s\\037\\037\\037\\037\\037\\037\\037\\037\\037\\037\\037<malformed>\\n' "
        f"{shlex.quote(sidecar.stem)} {shlex.quote(str(fresh))}\n"
        "  exit 0\n"
        "fi\n"
        "exec \"$real\" \"$@\"\n")
    fake.chmod(0o755)
    env = {"LANES_EDIT": str(fake)}
    row = trees_row(b, "triad-1", fresh, env)
    assert row[0] == sidecar.stem and len(row) == 13 and row[12] == "<malformed>", row
    assert not any(row[2:12]), row
    proc = b.tool("lane-handoff", "--lane", "triad-1", "--transcript", "none", "--agent", "claude",
                  "a malformed record", cwd=a, env=env)
    assert_the_record_is_named_and_not_polled(b, t, proc, fresh, sidecar, before, "<malformed>")

    sidecar.write_text(text)
    proc = handoff(b, "triad-1", a, "a whole record again")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"WRITER {fresh} — branch 050-r" in proc.stdout, proc.stdout
    assert "NOT POLLED" not in proc.stdout + proc.stderr
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout
    assert inventory(b, "triad-1") == {str(fresh): str(spec)}


@NEEDS_UPSTREAM
def test_255_a_record_with_a_tree_id_and_no_path_is_named_in_the_handoffs_not_polled_note(triad):
    """#255, `pi_bad`'S EMPTY-PATH ARM: a record that files a tree id and no
    path - #219's path-less tree - is a row with an empty path. A row with no
    path names no tree, so it is no record of whose a tree is, whatever its
    schema: before #252 the real `lanes-edit.sh` prints it as a WHOLE schema-1
    row (every field but the path), which only the empty-path rule names; with
    #252 it is `<malformed>`, which the schema rule names as well. Either way
    the handoff names it by its id and its schema - there is no path to name -
    takes the tree beside it for no writer of this lane's, files nothing over
    the record, and leaves the lane SWAPPING. Whole again, the record makes the
    tree this lane's writer."""
    b, t = triad
    a, spec = t["assembly"], t["spec"]
    fresh, sidecar, text = a_paired_tree_a_broken_record_names(b, t)
    no_path = "".join(ln for ln in text.splitlines(keepends=True) if not ln.startswith("path: "))
    assert no_path != text and "\npath:" not in no_path, no_path
    sidecar.write_text(no_path)
    before = sidecar.read_bytes()
    lt = b.tool("lanes-edit.sh", "lane-trees", "triad-1")
    assert lt.returncode == 0, lt.stderr
    rows = [ln.split(US) for ln in lt.stdout.splitlines() if ln.split(US)[0] == sidecar.stem]
    assert len(rows) == 1, lt.stdout
    row = rows[0]
    assert row[1] == "" and row[12] in ("1", "<malformed>"), row
    proc = handoff(b, "triad-1", a, "a record with no path")
    assert_the_record_is_named_and_not_polled(b, t, proc, fresh, sidecar, before, row[12], path="")

    sidecar.write_text(text)
    proc = handoff(b, "triad-1", a, "a whole record again")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"WRITER {fresh} — branch 050-r" in proc.stdout, proc.stdout
    assert "NOT POLLED" not in proc.stdout + proc.stderr
    assert "lifecycle: SWAPPED" in proc.stdout, proc.stdout
    assert inventory(b, "triad-1") == {str(fresh): str(spec)}


@NEEDS_UPSTREAM
def test_255_an_unreadable_record_is_named_in_the_handoffs_not_polled_note(triad):
    """#255: a record file this account cannot read is a row of its own, named
    by its file (`lane-trees`' `<unreadable>`, and no path). The handoff names
    it in the NOT POLLED note - by its id and its schema, there being no path -
    takes the tree beside it for no writer of this lane's, files nothing over
    it and leaves the lane SWAPPING."""
    b, t = triad
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file")
    a = t["assembly"]
    fresh, sidecar, text = a_paired_tree_a_broken_record_names(b, t)
    before = sidecar.read_bytes()
    sidecar.chmod(0)
    try:
        lt = b.tool("lanes-edit.sh", "lane-trees", "triad-1")
        proc = handoff(b, "triad-1", a, "an unreadable record")
    finally:
        sidecar.chmod(0o644)
    assert lt.returncode == 0, lt.stderr
    rows = [ln.split(US) for ln in lt.stdout.splitlines() if ln.split(US)[0] == sidecar.stem]
    assert len(rows) == 1 and rows[0][1] == "" and rows[0][12] == "<unreadable>", lt.stdout
    assert_the_record_is_named_and_not_polled(b, t, proc, fresh, sidecar, before, "<unreadable>",
                                              path="")


# ===================================================== the single repository

def single_repository_decoys(bench: Bench) -> list:
    """THE SCENARIO WHOSE OUTPUTS MAY NOT MOVE, laid out to look like a triad:
    a repository with a submodule that is NO leg, a worktree of that submodule
    under `worktrees/<feature>/code` and one of the repository itself under
    `worktrees/<feature>/spec`, and a tree under the lane's own root recorded
    with the SUBMODULE as its checkout - first with no `project.yaml`, then with
    one naming no leg but the checkout itself. The handoff's output, its top
    block and inventory, and the reconciliation before and after it."""
    b = bench
    out = []
    dep = b.seeded("dep", {"d.txt": "a dependency\n"})

    def scenario(name: str, manifest: str | None) -> None:
        lane = f"{name}-1"
        b.origin(name)
        s = b.projects / name
        b.git("clone", "-q", b.remotes / f"{name}.git", s)
        files = {"README.md": f"{name}\n", ".gitignore": "worktrees/\n"}
        if manifest is not None:
            files["project.yaml"] = manifest
        b.commit(s, "seed", files)
        b.git("submodule", "add", "-q", dep, "vendor/dep", cwd=s)
        b.commit(s, "a submodule that is no leg")
        b.git("push", "-q", "origin", "main", cwd=s)
        b.lanes(f"opensoft/{name}", s, lane)
        vendor = s / "vendor" / "dep"
        decoy_code = leg_tree(b, vendor, s / "worktrees" / "001-d" / "code", "001-d")
        b.commit(decoy_code, "decoy code", {"x.txt": "x\n"}, lane=lane)
        decoy_spec = leg_tree(b, s, s / "worktrees" / "001-d" / "spec", "001-d")
        (decoy_spec / "y.md").write_text("y\n")
        mine = leg_tree(b, vendor, b.projects / ".lane-worktrees" / lane / "dep", "dep")
        b.commit(mine, "lane work in the dependency", {"m.txt": "m\n"}, lane=lane)
        rec = b.tool("lanes-edit.sh", "set-lane-tree", lane, mine, "--checkout", vendor)
        assert rec.returncode == 0, rec.stderr
        out.append((f"{name}: lane-reconcile before", reconciled(b, lane)))
        out.append((f"{name}: lane-handoff", shown(handoff(b, lane, s), b)))
        out.append((f"{name}: lane-handoff: top block", normalise(top_block(b, lane), b)))
        trees = b.tool("lanes-edit.sh", "lane-trees", lane)
        trees.stdout = "".join(sorted(trees.stdout.splitlines(keepends=True),
                                      key=lambda line: normalise(line, b)))
        out.append((f"{name}: lane-handoff: inventory", shown(trees, b)))
        out.append((f"{name}: lane-reconcile after", reconciled(b, lane)))

    scenario("repoD", None)
    scenario("repoQ", ("schema_version: 1\nkind: project-manifest\nid: repoQ\nlegs:\n"
                       "  - role: assembly\n    repository: opensoft/repoQ\n    path: \".\"\n"))
    return out


def reconciled(b: Bench, lane: str) -> str:
    """`lane-reconcile`, its TREE rows in a stable order: the inventoried ones
    come in the order of their sidecars' file names, a checksum of the bench's
    own path, so every row is sorted by its normalised text, in place."""
    proc = b.tool("lanes-edit.sh", "lane-reconcile", lane)
    lines = proc.stdout.splitlines(keepends=True)
    idx = [i for i, ln in enumerate(lines) if ln.startswith("TREE" + US)]
    for i, ln in zip(idx, sorted((lines[i] for i in idx), key=lambda ln: normalise(ln, b))):
        lines[i] = ln
    proc.stdout = "".join(lines)
    return shown(proc, b)


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="the golden was captured on Linux, as tests/test_triad_lane_tooling.py's")
def test_t018_single_repository_handoff_and_reconcile_are_c45a452s_byte_for_byte(tmp_path):
    """THE INVARIANT, ON A REPOSITORY LAID OUT TO LOOK LIKE A TRIAD: with no
    `project.yaml` naming a leg, a `worktrees/<feature>/code` holding a
    submodule's worktree is not polled or reported as a paired tree, and a tree
    of a submodule is recorded under the lane's checkout, exactly as
    `c45a452`'s tools did - every byte of every output equal to the stored
    golden this module's `--capture` wrote from them."""
    assert GOLDEN.is_file(), f"{GOLDEN} is missing; it is generated from c45a452's tools"
    want = parse_golden(GOLDEN.read_text(encoding="utf-8"))
    got = single_repository_decoys(Bench(tmp_path / "bench", REPO))
    assert [k for k, _ in got] == [k for k, _ in want]
    for (key, have), (_k, gold) in zip(got, want):
        if have != gold:
            diff = "\n".join(difflib.unified_diff(gold.splitlines(), have.splitlines(),
                                                  f"c45a452: {key}", f"now: {key}", lineterm=""))
            raise AssertionError(f"the single-repository output of '{key}' moved:\n{diff}")


# ===================================================================== capture

def capture(tools: Path, golden: Path) -> None:
    """Write the golden file from the tools in `tools` - run ONCE, against
    `c45a452`'s (`git archive c45a452 | tar -x -C <dir>`), and committed."""
    with tempfile.TemporaryDirectory(prefix="t018-handoff-capture.") as tmp:
        text = render_golden(single_repository_decoys(Bench(Path(tmp) / "bench", tools)))
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) in (3, 4) and sys.argv[1] == "--capture":
        capture(Path(sys.argv[2]).resolve(), Path(sys.argv[3]) if len(sys.argv) == 4 else GOLDEN)
        sys.exit(0)
    sys.stderr.write("usage: test_triad_lane_tooling_handoff.py --capture <tools dir> [<golden>]\n")
    sys.exit(64)
