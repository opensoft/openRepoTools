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
the commands resolve W from `workspace.yaml` as a lane window does, and with
`LANES_ROUTE_WRITES=1`, the opt-in the routing stays behind until slice 1b (the
review of opensoft/openRepoTools#282, MUST 2); one case leaves it out. The
sandbox is `test_lane_start_row_stamp`'s, with its explicit seam taken back
out.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from conftest import REPO
from test_lane_start_row_stamp import LANE, Sandbox, _checkout_of_length, pytestmark, short_root  # noqa: F401


def default_resolution(box: Sandbox, *, route: bool = True) -> Path:
    """No seam: workspace.yaml names `box.wip` as W again, and the routing is
    opted into unless `route` is False. Returns the lane's checkout."""
    for key in ("LANES_REPO", "LANES_FILE"):
        box.env.pop(key, None)
    if route:
        box.env["LANES_ROUTE_WRITES"] = "1"
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


# ------------------------------------------------------- fix round 1 (#282's review)

def test_without_the_opt_in_a_new_lane_starts_through_W(tmp_path, short_root):
    """MUST 2: with no `LANES_ROUTE_WRITES` a start reads and writes W, as on
    main: no lane checkout is made, and a second start finds its row in W."""
    box = Sandbox(tmp_path)
    checkout = default_resolution(box, route=False)
    lane_dir = _checkout_of_length(short_root, None)
    box.checkout(lane_dir)
    first = box.start("--dir", str(lane_dir), window_name="claude")
    assert first.returncode == 0, first.stderr
    assert not checkout.parent.exists(), "no lane checkout, and no <W>-lanes/"
    assert len(rows(box.wip / "lanes" / "LANES.md")) == 1, "the row is W's"
    second = box.start(window_name=LANE)
    assert second.returncode == 0, second.stderr
    assert not checkout.parent.exists()


def test_a_checkout_that_cannot_be_made_is_said_and_the_start_goes_on(tmp_path, short_root):
    """SHOULD 2: where the lane's checkout cannot be cloned, the start says so
    and reads W, as it does for a dry run with none: a register act it can do
    without never refuses a launch (Amendment 8(d))."""
    box = Sandbox(tmp_path)
    checkout = default_resolution(box, route=False)
    lane_dir = _checkout_of_length(short_root, None)
    box.checkout(lane_dir)
    first = box.start("--dir", str(lane_dir), window_name="claude")
    assert first.returncode == 0, first.stderr
    real = shutil.which("git")
    wrapper = box.root / "no-clone-git"
    wrapper.write_text(f"""#!/usr/bin/env bash
case " $* " in *" clone "*) echo "test: no clone today" >&2; exit 1 ;; esac
exec '{real}' "$@"
""", encoding="utf-8")
    wrapper.chmod(0o755)
    box.env.update(LANES_ROUTE_WRITES="1", LANES_GIT=str(wrapper))
    second = box.start(window_name=LANE)
    assert "own register checkout could not be made" in second.stderr, second.stderr
    assert "so this command reads W's register" in second.stderr
    assert not checkout.exists()
    assert second.returncode == 0, second.stderr


#: lane-end prints this line, its in-flight read of the lane's log, only after
#: the register follow-up, so a case whose end must go on past the follow-up's
#: note asserts it (the re-check of #282's cases, R3-1). The end's exit is its
#: own later write's, so it cannot simply be asserted 0.
GOES_ON = "in-flight read from lanes/log/"
#: The re-check's R3-2: the slowest new cases run inside 300 s, not 120 or 180.
SLOW = 300


def _end(box: Sandbox, *args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    for name in ("lane-end", "lane-worktrees"):
        shutil.copy2(REPO / name, box.bin / name)
        (box.bin / name).chmod(0o755)
    return subprocess.run([str(box.bin / "lane-end"), LANE, *args], env=box.env,
                          capture_output=True, text=True, timeout=timeout, check=False)


def _started_in_W(tmp_path: Path, short_root: Path, *, checkout_first: bool = False):
    """A new lane started with no opt-in: its row is W's. With
    `checkout_first`, the lane's own checkout is made BEFORE the row, so only
    W shows it."""
    box = Sandbox(tmp_path)
    checkout = default_resolution(box, route=False)
    if checkout_first:
        made = subprocess.run([str(box.bin / "lanes-edit.sh"), "lane-checkout", LANE, "--create"],
                              env=box.env, capture_output=True, text=True, timeout=180, check=False)
        assert made.returncode == 0, made.stderr
    lane_dir = _checkout_of_length(short_root, None)
    box.checkout(lane_dir)
    first = box.start("--dir", str(lane_dir), window_name="claude")
    assert first.returncode == 0, first.stderr
    assert len(rows(box.wip / "lanes" / "LANES.md")) == 1, "the row is W's"
    return box, checkout


def test_without_the_opt_in_lane_end_reads_W(tmp_path, short_root):
    """MUST 2, for lane-end: with no `LANES_ROUTE_WRITES` it reads W's
    register, as on main, even where the lane has a checkout of its own —
    here one made before the lane's row, so only W shows the row."""
    box, checkout = _started_in_W(tmp_path, short_root, checkout_first=True)
    assert rows(checkout / "lanes" / "LANES.md") == [], "the lane's checkout predates its row"
    end = _end(box, "--dry-run")
    assert "has no row for lane" not in end.stderr, end.stderr
    assert end.returncode == 0, (end.stdout, end.stderr)


def _no_clone_git(box: Sandbox) -> Path:
    real = shutil.which("git")
    wrapper = box.root / "no-clone-git"
    wrapper.write_text(f"""#!/usr/bin/env bash
case " $* " in *" clone "*) echo "test: no clone today" >&2; exit 1 ;; esac
exec '{real}' "$@"
""", encoding="utf-8")
    wrapper.chmod(0o755)
    return wrapper


def test_a_checkout_that_cannot_be_made_is_said_and_the_end_goes_on(tmp_path, short_root):
    """SHOULD 2, for lane-end: where the lane's checkout cannot be cloned, the
    end says so and reads W's register — it finds the lane's row there — and
    is not refused for a register act it can do without (Amendment 8(d))."""
    box, checkout = _started_in_W(tmp_path, short_root)
    box.env.update(LANES_ROUTE_WRITES="1", LANES_GIT=str(_no_clone_git(box)))
    end = _end(box)
    assert "own register checkout could not be made" in end.stderr, end.stderr
    assert "so this command reads W's register" in end.stderr, end.stderr
    assert "has no row for lane" not in end.stderr, end.stderr
    assert GOES_ON in end.stderr, end.stderr
    assert not checkout.exists()


class _CreationLockHeld:
    """The lane's creation lock, `<W>-lanes/.<lane>.lock`, held by a live
    process in this container, and every `sleep 1` an instant — so the
    helper's wait for that lock, ten minutes and a minute of one-second
    polls, ends in seconds with its 4."""

    def __init__(self, box: Sandbox, checkout: Path) -> None:
        self.lock = checkout.parent / f".{LANE}.lock"
        real_sleep = shutil.which("sleep")
        fake = box.root / "fakebin" / "sleep"
        fake.write_text(f"""#!/usr/bin/env bash
if [ "$*" = 1 ]; then exit 0; fi
exec '{real_sleep}' "$@"
""", encoding="utf-8")
        fake.chmod(0o755)

    def __enter__(self):
        self.holder = subprocess.Popen(["sleep", "300"])
        self.lock.mkdir(parents=True)
        (self.lock / "pid").write_text(f"{self.holder.pid}\n", encoding="utf-8")
        return self

    def __exit__(self, *exc):
        self.holder.kill()
        self.holder.wait()
        return False


def test_a_held_creation_lock_is_said_and_the_start_goes_on(tmp_path, short_root):
    """SHOULD 2, its 4: where another creator holds the lane's creation lock
    past the wait, the start says so and reads W, as for a clone that failed."""
    box, checkout = _started_in_W(tmp_path, short_root)
    box.env["LANES_ROUTE_WRITES"] = "1"
    with _CreationLockHeld(box, checkout):
        second = box.start(window_name=LANE, timeout=SLOW)
    assert "own register checkout could not be made" in second.stderr, second.stderr
    assert "exited 4" in second.stderr, second.stderr
    assert "so this command reads W's register" in second.stderr
    assert not checkout.exists()
    assert second.returncode == 0, second.stderr


def test_a_held_creation_lock_is_said_and_the_end_goes_on(tmp_path, short_root):
    """SHOULD 2, its 4, for lane-end."""
    box, checkout = _started_in_W(tmp_path, short_root)
    box.env["LANES_ROUTE_WRITES"] = "1"
    with _CreationLockHeld(box, checkout):
        end = _end(box, timeout=SLOW)
    assert "own register checkout could not be made" in end.stderr, end.stderr
    assert "exited 4" in end.stderr, end.stderr
    assert "so this command reads W's register" in end.stderr
    assert "has no row for lane" not in end.stderr, end.stderr
    assert GOES_ON in end.stderr, end.stderr
    assert not checkout.exists()
