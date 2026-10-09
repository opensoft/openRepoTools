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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import REPO, WINDOWS_SKIP  # noqa: E402
from test_triad_lane_tooling import (  # noqa: E402
    NEEDS_TEMPLATE, US, Bench, build_assembly, normalise, parse_golden, render_golden, shown)

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


def handoff(b: Bench, lane: str, cwd: Path, why: str = "t018 handoff") -> subprocess.CompletedProcess:
    return b.tool("lane-handoff", "--lane", lane, "--transcript", "none", "--agent", "claude",
                  why, cwd=cwd)


def top_block(b: Bench, lane: str) -> str:
    return (b.wip / "handoffs" / f"{lane}.md").read_text().split("\n---\n", 1)[0]


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

@NEEDS_TEMPLATE
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

    proc = handoff(b, "triad-1", a)
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


@NEEDS_TEMPLATE
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
    proc = handoff(b, "triad-1", a)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"writers polled: 2 under {a}" in proc.stderr, proc.stderr
    assert inventory(b, "triad-1") == {str(lane_root): str(a), str(paired_code): str(code)}


@NEEDS_TEMPLATE
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
    assert f"{a}/project.yaml is there and its legs could not be read" in proc.stderr, proc.stderr
    assert "paired feature trees" in proc.stderr and "were NOT polled" in proc.stderr
    assert f"WRITER {paired_code} —" not in proc.stdout, proc.stdout
    assert f"WRITER {lane_code} —" in proc.stdout and f"WRITER {lane_root} —" in proc.stdout
    assert f"the worktree inventory entry for {lane_code} was NOT written" in proc.stderr
    assert "lifecycle: SWAPPING" in proc.stdout, proc.stdout
    assert "the assembly's legs could not be read" in proc.stderr
    block = top_block(b, "triad-1")
    assert "- NOT POLLED: " in block and f"`{a}/worktrees`" in block, block
    assert inventory(b, "triad-1") == {str(lane_code): str(code), str(lane_root): str(a)}


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
