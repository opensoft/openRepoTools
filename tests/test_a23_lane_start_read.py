# SPDX-License-Identifier: Apache-2.0
"""Amendment 23, act 2's slice 1a: `lane-start` and `lane-end` read a lane's
row where that lane's writes go.

Under the default resolution every write of a lane goes through its own register
checkout, `<W>-lanes/<lane>/`, and W, the readers' copy that `workspace.yaml`
names, moves only by `refresh-workspace`. Both commands used to read the lane's
row from W's working tree. A new lane's first start added its row through the
checkout, so W never showed it. The second start then saw a row on origin and
none "in this checkout", and refused to add a duplicate (`lane-start:1591`). A
`lane-end` read the same W and found no row to end.

Each case drives the real commands with no `LANES_REPO` and no `LANES_FILE`, so
the helper routes every write and the commands resolve W from `workspace.yaml`
as a lane window does. The sandbox is `test_lane_start_row_stamp`'s, with its
explicit seam taken back out.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from conftest import REPO
from test_lane_start_row_stamp import LANE, Sandbox, _checkout_of_length, pytestmark, short_root  # noqa: F401


def default_resolution(box: Sandbox) -> Path:
    """No seam: workspace.yaml names `box.wip` as W again. Returns the lane's checkout."""
    for key in ("LANES_REPO", "LANES_FILE"):
        box.env.pop(key, None)
    (box.home / ".agents" / "workspace.yaml").write_text(
        f"repository: {box.root / 'origin.git'}\npath: {box.wip}\n", encoding="utf-8")
    return Path(os.path.realpath(box.wip) + "-lanes") / LANE


def rows(register: Path) -> list[str]:
    return [r for r in register.read_text(encoding="utf-8").splitlines()
            if r.startswith(f"| `{LANE}`")]


def started(tmp_path: Path, short_root: Path) -> tuple[Sandbox, Path]:
    """A NEW lane's first start: its row is added through its own checkout."""
    box = Sandbox(tmp_path)
    checkout = default_resolution(box)
    lane_dir = _checkout_of_length(short_root, None)
    box.checkout(lane_dir)
    first = box.start("--dir", str(lane_dir), window_name="claude")
    assert first.returncode == 0, first.stderr
    assert (checkout / ".git").is_dir(), "the first write made the lane's checkout"
    assert len(rows(checkout / "lanes" / "LANES.md")) == 1
    assert rows(box.wip / "lanes" / "LANES.md") == [], "W's working tree took no write"
    return box, checkout


def test_a_new_lanes_second_start_reads_its_row_in_its_own_checkout(tmp_path, short_root):
    box, checkout = started(tmp_path, short_root)
    second = box.start(window_name=LANE)
    assert second.returncode == 0, second.stderr
    assert "ALREADY has a row" not in second.stderr, second.stderr
    assert len(rows(checkout / "lanes" / "LANES.md")) == 1, "one row, and no second one added"
    published = box.git("--git-dir", str(box.root / "origin.git"), "show", "main:lanes/LANES.md")
    assert sum(1 for r in published.splitlines() if r.startswith(f"| `{LANE}`")) == 1
    assert rows(box.wip / "lanes" / "LANES.md") == [], "and W's working tree still took none"


def test_lane_end_finds_the_row_its_lane_start_wrote(tmp_path, short_root):
    box, checkout = started(tmp_path, short_root)
    for name in ("lane-end", "lane-worktrees"):
        shutil.copy2(REPO / name, box.bin / name)
        (box.bin / name).chmod(0o755)
    end = subprocess.run([str(box.bin / "lane-end"), LANE, "--dry-run"], env=box.env,
                         capture_output=True, text=True, timeout=120, check=False)
    assert "has no row for lane" not in end.stderr, end.stderr
    assert end.returncode == 0, (end.stdout, end.stderr)
    assert rows(box.wip / "lanes" / "LANES.md") == []


def test_a_dry_run_start_makes_no_checkout(tmp_path, short_root):
    """`--dry-run` renames, writes and launches nothing, so it clones nothing
    either: with no checkout yet, the row is read from W."""
    box = Sandbox(tmp_path)
    checkout = default_resolution(box)
    lane_dir = _checkout_of_length(short_root, None)
    box.checkout(lane_dir)
    plan = box.start("--dir", str(lane_dir), "--dry-run", window_name="claude")
    assert plan.returncode == 0, plan.stderr
    assert not checkout.exists() and not checkout.parent.exists(), "a dry run made no lane checkout"


def test_a_LANES_REPO_alone_is_the_register_read(tmp_path, short_root):
    """A caller's `LANES_REPO` without `LANES_FILE` is the checkout the helper
    writes in (Amendment 23 S2), so it is the register `lane-start` reads: the
    second start finds the row the first one wrote there."""
    box = Sandbox(tmp_path)                 # W is the reader copy; LANES_REPO is box.wip
    box.env.pop("LANES_FILE")
    lane_dir = _checkout_of_length(short_root, None)
    box.checkout(lane_dir)
    first = box.start("--dir", str(lane_dir), window_name="claude")
    assert first.returncode == 0, first.stderr
    assert len(rows(box.wip / "lanes" / "LANES.md")) == 1, "the write landed where LANES_REPO points"
    second = box.start(window_name=LANE)
    assert second.returncode == 0, second.stderr
    assert "ALREADY has a row" not in second.stderr, second.stderr
    assert len(rows(box.wip / "lanes" / "LANES.md")) == 1
