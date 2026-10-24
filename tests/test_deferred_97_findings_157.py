# SPDX-License-Identifier: Apache-2.0
"""opensoft/openRepoTools#157, section 4: findings of #97's round on `8c5958f`
that were filed rather than taken there. Items 4a, 4d and 4e, each through the
real `lane-start` and `lanes-edit.sh` in the lane-start sandbox (a bare origin,
a register clone, a fake tmux and a fake gh; nothing reaches the network).

  * 4a. `managed-projection` read the published row only, while every
    `lanes-edit.sh` writer also reads THIS checkout's row (`managed_seam_refuse`)
    and refuses vocabulary that only this copy carries. So a marker committed
    here and not pushed passed `lane-start`'s gate, which asks that read, and
    the launch went on until a later writer refused. The read now answers 1
    for it, as the writers do.
  * 4d. NO CHANGE, as the issue's own reasoning says: a malformed row with no
    managed-owner vocabulary cannot be a marker, so it is legacy in either
    copy, and the writer that rewrites it refuses its shape on its own. The
    case below pins both halves, and that the 4a read stops at vocabulary.
  * 4e. A `trees/` directory that is there and cannot be listed was read as no
    inventory at all (8). `lane-trees` now answers 10 for it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from test_lane_start_claude_current import Sandbox, LANE, pytestmark  # noqa: F401


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    box = Sandbox(tmp_path)
    box.env["LANES_LANE_STATE_ROOT"] = str(tmp_path / "state")
    box.resolver()
    seeded = box.start("--no-launch")
    assert seeded.returncode == 0, seeded.stderr
    return box


def helper(box: Sandbox, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(box.bin / "lanes-edit.sh"), *args],
                          cwd=box.lane_dir, env=box.env, text=True,
                          capture_output=True, timeout=60, check=False)


def register(box: Sandbox) -> Path:
    return box.wip / "lanes" / "LANES.md"


def commit_state_cell_here(box: Sandbox, cell: str, message: str,
                           checkout: Path | None = None) -> None:
    """Replace the lane's state cell in THIS checkout (or `checkout`) and commit
    it, unpushed — as a writer that crashed between its commit and its push
    leaves it."""
    checkout = checkout or box.wip
    path = checkout / "lanes" / "LANES.md"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith(f"| `{LANE}` "):
            body = line.rstrip("\n").rstrip()
            assert body.endswith(" |"), line
            head, _, _ = body[:-2].rpartition(" | ")
            lines[i] = f"{head} | {cell} |\n"
            break
    else:
        raise AssertionError(f"no row for {LANE} in the sandbox register")
    path.write_text("".join(lines), encoding="utf-8")
    box.git("-C", str(checkout), "commit", "-qam", message)


def says_which_copy(stderr: str, read: Path) -> None:
    """The refusal names the register file it READ and both ways the two
    copies can disagree, each with its remedy."""
    assert f"register file, {read.resolve()}, carries" in stderr, stderr
    assert "AHEAD of origin" in stderr and "publish that change or undo it" in stderr
    assert "BEHIND it" in stderr and "fast-forward it" in stderr
    assert f"git -C {read.resolve().parent} status --short --branch -- LANES.md" in stderr


def fingerprint(box: Sandbox) -> tuple:
    return (box.git("-C", str(box.wip), "rev-parse", "HEAD"),
            box.git("--git-dir", str(box.origin), "rev-parse", "main"),
            box.git("-C", str(box.wip), "status", "--porcelain"),
            register(box).read_bytes(), box.lane_log(), box.claude_runs(),
            box.tmux_log.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 4a

def test_4a_an_unpushed_local_marker_reads_as_unknown_not_legacy(box):
    published = helper(box, "managed-projection", LANE)
    assert published.returncode == 8, published.stderr
    commit_state_cell_here(box, "MANAGED OWNER · ledger-1",
                           "an unpushed marker, in this checkout only")
    result = helper(box, "managed-projection", LANE)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert result.stdout == ""
    assert "UNKNOWN" in result.stderr
    says_which_copy(result.stderr, register(box))


def test_4a_a_checkout_behind_an_origin_that_dropped_the_marker_reads_as_unknown(box):
    commit_state_cell_here(box, "MANAGED OWNER · ledger-1", "the ledger's marker")
    box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    assert helper(box, "managed-projection", LANE).stdout == "ledger-1\n"
    peer = box.root / "peer"
    box.git("clone", "-q", str(box.origin), str(peer))
    commit_state_cell_here(box, "PAUSED · 2026-10-13T00:00:00Z · the ledger let go",
                           "the ledger drops its marker, elsewhere", checkout=peer)
    box.git("-C", str(peer), "push", "-q", "origin", "main")
    result = helper(box, "managed-projection", LANE)
    assert result.returncode == 1, (result.stdout, result.stderr)
    says_which_copy(result.stderr, register(box))


def test_4a_a_runtime_clone_names_the_register_file_read_not_the_clone(box):
    clone = box.root / "runtime-clone"
    box.git("clone", "-q", str(box.origin), str(clone))
    commit_state_cell_here(box, "MANAGED OWNER · ledger-1",
                           "an unpushed marker, in this checkout only")
    env = dict(box.env, LANES_REPO=str(clone))
    result = subprocess.run([str(box.bin / "lanes-edit.sh"), "managed-projection", LANE],
                            cwd=box.lane_dir, env=env, text=True,
                            capture_output=True, timeout=60, check=False)
    assert result.returncode == 1, (result.stdout, result.stderr)
    says_which_copy(result.stderr, register(box))
    assert str(clone) not in result.stderr


def test_4a_lane_start_refuses_an_unpushed_local_marker_at_its_gate(box):
    commit_state_cell_here(box, "MANAGED OWNER · ledger-1",
                           "an unpushed marker, in this checkout only")
    before = fingerprint(box)
    result = box.start()
    assert result.returncode == 1, (result.stdout, result.stderr)
    # THE GATE'S OWN REFUSAL, before the binding, the transcript move and every
    # write — not a later writer's.
    assert f"managed-projection {LANE}` exited 1" in result.stderr
    assert "a lane start is refused here" in result.stderr
    assert fingerprint(box) == before


# ---------------------------------------------------------------- 4d

def test_4d_a_malformed_local_row_with_no_vocabulary_is_legacy_and_its_writer_refuses_it(box):
    commit_state_cell_here(box, "PAUSED · 2026-10-11T00:00:00Z · a literal | pipe",
                           "a seventh separator, in this checkout only")
    result = helper(box, "managed-projection", LANE)
    assert result.returncode == 8, (result.stdout, result.stderr)
    before = fingerprint(box)
    # AMENDMENT 23 S3 (#198, slice 1b): the commit is unpushed, so every writer
    # refuses it first, by content, with nothing written — never as UNKNOWN.
    result = helper(box, "set-row-state", LANE, "PAUSED · the writer asks")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "1 unpublished commit(s)" in result.stderr
    assert "UNKNOWN" not in result.stderr
    assert fingerprint(box) == before
    # Published, the same row is the writer's own row-shape refusal.
    box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    before = fingerprint(box)
    result = helper(box, "set-row-state", LANE, "PAUSED · the writer asks")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "separators where a seven-column row carries 6" in result.stderr
    assert "UNKNOWN" not in result.stderr
    assert fingerprint(box) == before


# ---------------------------------------------------------------- 4e

def trees_dir(box: Sandbox) -> Path:
    return Path(box.env["LANES_LANE_STATE_ROOT"]) / LANE / "trees"


def test_4e_an_empty_trees_directory_is_still_no_inventory(box):
    recorded = helper(box, "set-lane-tree", LANE, str(box.lane_dir))
    assert recorded.returncode == 0, recorded.stderr
    listed = helper(box, "lane-trees", LANE)
    assert listed.returncode == 0, listed.stderr
    assert str(box.lane_dir) in listed.stdout
    for sidecar in trees_dir(box).iterdir():
        sidecar.unlink()
    assert helper(box, "lane-trees", LANE).returncode == 8


@pytest.mark.parametrize("mode", [0o000, 0o300, 0o600],
                         ids=["no-access", "no-read", "no-search"])
def test_4e_a_trees_directory_that_cannot_be_listed_is_never_no_inventory(box, mode):
    if os.geteuid() == 0:
        pytest.skip("permission regression requires an unprivileged runner")
    recorded = helper(box, "set-lane-tree", LANE, str(box.lane_dir))
    assert recorded.returncode == 0, recorded.stderr
    trees = trees_dir(box)
    trees.chmod(mode)
    try:
        result = helper(box, "lane-trees", LANE)
    finally:
        trees.chmod(0o700)
    assert result.returncode == 10, (result.stdout, result.stderr)
    assert result.stdout == ""
    assert "could not be listed" in result.stderr
    assert str(trees) in result.stderr
