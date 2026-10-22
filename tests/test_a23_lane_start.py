# SPDX-License-Identifier: Apache-2.0
"""Amendment 23, act 2's slice 2b: `lane-start` writes only through the lane's
own register checkout, and W moves only by fast-forward.

Until this slice `lane-start` wrote the handoff's Rule 3 stamp itself: it
published it under W's lock and then added, committed, pulled and pushed it in
W with no lock at all (lane openRepoTools-3's finding 282, its first writer).
Under the default resolution the lane's other writes already went through
`<W>-lanes/<lane>/` (slice 1a), so the stamp was the one write left in W, and
it read W's copy of the handoff, which nothing brought up to date.

Now:
  * `refresh-workspace` fast-forwards W before the first read and again once
    the writes are done, and the row is read from W after the first;
  * the lane's checkout is made at "5. the row", and its writable handoff path
    is printed beside the row's spelling;
  * the stamp is ONE `write-handoff --stamp` call, under the checkout's lock
    and S3/S4, and its exit is a note: the launch is refused only by a
    restart's own fences;
  * the first prompt is read from the file that call writes.

Each case drives a real `lane-start` in `test_lane_start_row_stamp`'s sandbox
with the default resolution (no `LANES_REPO`, no `LANES_FILE`) and the opt-in
`LANES_ROUTE_WRITES=1`. A "peer" is another clone of the sandbox's origin that
commits and pushes, as another workstation's lane does.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from test_a23_lane_start_read import default_resolution, rows
from test_lane_start_row_stamp import LANE, Sandbox, _checkout_of_length, pytestmark, short_root  # noqa: F401

HANDOFF = "Lane: repoZ-1 — single-use resume prompt\n\n# state\n\nthe lane's own words\n"
FF = "merge origin/main: Fast-forward"
PEER_SID = "bbbb0001-2222-4000-8000-bbbb00012222"


# ------------------------------------------------------------------ helpers

def _quiet(box: Sandbox, repo: Path) -> None:
    for key, value in (("gc.auto", "0"), ("maintenance.auto", "false")):
        box.git("-C", str(repo), "config", key, value)


def _origin(box: Sandbox, *args: str) -> str:
    return box.git("--git-dir", str(box.root / "origin.git"), *args)


def _published(box: Sandbox, rel: str) -> str:
    return _origin(box, "show", f"main:{rel}")


def _tip(box: Sandbox) -> str:
    return _origin(box, "rev-parse", "main").strip()


def _cell(box: Sandbox) -> str:
    """The handoff cell of the lane's published row."""
    found = [r for r in _published(box, "lanes/LANES.md").splitlines()
             if r.startswith(f"| `{LANE}`")]
    assert len(found) == 1, found
    return found[0].split("|")[6].strip()


def _peer(box: Sandbox) -> Path:
    p = box.root / "peer"
    if not p.exists():
        box.git("clone", "-q", str(box.root / "origin.git"), str(p))
        _quiet(box, p)
    box.git("-C", str(p), "fetch", "-q", "origin", "main")
    box.git("-C", str(p), "merge", "-q", "--ff-only", "origin/main")
    return p


def _peer_push(box: Sandbox, files: dict[str, str], msg: str) -> None:
    p = _peer(box)
    for rel, text in files.items():
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(text, encoding="utf-8")
    box.git("-C", str(p), "add", "--", *files)
    box.git("-C", str(p), "commit", "-q", "-m", msg)
    box.git("-C", str(p), "push", "-q", "origin", "HEAD:main")


def _edit(box: Sandbox, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([str(box.bin / "lanes-edit.sh"), *args], env=env or box.env,
                          capture_output=True, text=True, timeout=180, check=False)


def _reflog(box: Sandbox) -> list[str]:
    return box.git("-C", str(box.wip), "reflog", "--format=%gs", "HEAD").splitlines()


def _boxed(tmp_path: Path, short_root: Path) -> tuple[Sandbox, Path, Path]:
    """The sandbox with the default resolution and the opt-in, W kept from gc."""
    box = Sandbox(tmp_path)
    checkout = default_resolution(box)
    _quiet(box, box.wip)
    for key, value in (("gc.auto", "0"), ("maintenance.auto", "false")):
        _origin(box, "config", key, value)
    lane_dir = _checkout_of_length(short_root, None)
    box.checkout(lane_dir)
    return box, checkout, lane_dir


def _started(tmp_path: Path, short_root: Path) -> tuple[Sandbox, Path, Path, list[str]]:
    """A new lane's first start, with W's reflog as it stood before it."""
    box, checkout, lane_dir = _boxed(tmp_path, short_root)
    before = _reflog(box)
    first = box.start("--dir", str(lane_dir), window_name="claude")
    assert first.returncode == 0, first.stderr
    assert (checkout / ".git").is_dir(), "the first start made the lane's checkout"
    return box, checkout, lane_dir, before


def _assert_W_only_fast_forwarded(box: Sandbox, before: list[str]) -> None:
    after = _reflog(box)
    assert after[len(after) - len(before):] == before, (before, after)
    new = after[:len(after) - len(before)]
    assert all(entry == FF for entry in new), new
    assert box.git("-C", str(box.wip), "status", "--porcelain") == "", "W is clean"


def _assert_nothing_unpublished(box: Sandbox, checkout: Path) -> None:
    cherry = box.git("-C", str(checkout), "cherry", "origin/main", "HEAD")
    assert not [c for c in cherry.splitlines() if c.startswith("+")], cherry


# -------------------------------------------------------------------- cases

def test_launch_creates_checkout_and_writes_only_there(tmp_path, short_root):
    box, checkout, _lane_dir, before = _started(tmp_path, short_root)
    cell = _cell(box)
    _peer_push(box, {cell: HANDOFF}, "the lane's handoff, written elsewhere")

    second = box.start("--fresh", window_name=LANE)
    assert second.returncode == 0, second.stderr

    register = _published(box, "lanes/LANES.md")
    assert sum(1 for r in register.splitlines() if r.startswith(f"| `{LANE}`")) == 1
    row = [r for r in register.splitlines() if r.startswith(f"| `{LANE}`")][0]
    assert "LIVE · " in row and "RESUMED by " in row, row
    assert f"RESUMED — lane {LANE}, session " in _published(box, f"lanes/log/{LANE}.md")
    stamped = _published(box, cell)
    assert f"(lane {LANE}) at " in stamped and stamped.splitlines()[2].startswith("RESUMED by "), stamped
    assert _origin(box, "log", "-1", "--format=%s%n%b", "main").startswith(f"handoff({LANE}@Eagle): RESUMED by ")
    assert f"Lane: {LANE}" in _origin(box, "log", "-1", "--format=%b", "main")

    _assert_W_only_fast_forwarded(box, before)
    assert box.git("-C", str(box.wip), "rev-parse", "HEAD").strip() == _tip(box), "W ends on origin's tip"
    _assert_nothing_unpublished(box, checkout)


def test_launch_fast_forwards_W_before_and_after(tmp_path, short_root):
    box, checkout, lane_dir = _boxed(tmp_path, short_root)
    made = _edit(box, "lane-checkout", LANE, "--create")
    assert made.returncode == 0, made.stderr
    before = _reflog(box)
    # Another workstation's start of this lane: its row, and its handoff.
    register = _published(box, "lanes/LANES.md")
    row = (f"| `{LANE}` | harness `{PEER_SID}` (minted by lane-start, 2026-10-22T00:00:00Z) | "
           f"Eagle / default / peer | 2026-10-22T00:00Z | none | handoffs/repoZ/peer.md | "
           f"LIVE · 2026-10-22T00:00:00Z · STARTED by {PEER_SID} (lane {LANE}) — lane-start on Eagle: row created |")
    _peer_push(box, {"lanes/LANES.md": register + row + "\n", "handoffs/repoZ/peer.md": HANDOFF},
               "a peer's start of the lane")

    start = box.start("--dir", str(lane_dir), "--fresh", window_name=LANE)
    assert start.returncode == 0, start.stderr
    assert "ALREADY has a row" not in start.stderr, start.stderr
    assert len(rows(box.wip / "lanes" / "LANES.md")) == 1, "W was brought up to the peer's row first"
    assert box.git("-C", str(box.wip), "rev-parse", "HEAD").strip() == _tip(box), "and to the stamp after"
    assert _origin(box, "log", "-1", "--format=%s", "main").startswith(f"handoff({LANE}@Eagle): RESUMED by ")
    _assert_W_only_fast_forwarded(box, before)
    _assert_nothing_unpublished(box, checkout)


def test_launch_not_refused_when_S3_refuses(tmp_path, short_root):
    box, checkout, _lane_dir, _before = _started(tmp_path, short_root)
    cell = _cell(box)
    _peer_push(box, {cell: HANDOFF}, "the lane's handoff, written elsewhere")
    assert _edit(box, "refresh-workspace").returncode == 0
    foreign = checkout / "handoffs" / "repoQ" / "foreign.md"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text("a person's file, staged and never committed\n", encoding="utf-8")
    box.git("-C", str(checkout), "add", "--", "handoffs/repoQ/foreign.md")
    tip = _tip(box)

    start = box.start("--fresh", window_name=LANE)
    assert start.returncode == 0, start.stderr
    assert _tip(box) == tip, "nothing was published, from the lane's checkout or from W"
    assert "RESUMED by " not in _published(box, cell)
    assert "the stamp line it would have written under the handoff's header block: RESUMED by " in start.stderr, start.stderr
    assert "handoffs/repoQ/foreign.md" in box.git("-C", str(checkout), "diff", "--cached", "--name-only")
    assert box.git("-C", str(box.wip), "status", "--porcelain") == "", "W took no write"


def test_the_1312Z_shape_all_three_writes_pushed(tmp_path, short_root):
    """The shape of 2026-10-17T13:12Z: the lane's checkout clean, nothing
    ahead and ten commits behind, one of them a change to the row beside the
    lane's, one the lane's handoff. The row state, the log line and the stamp
    all land on origin."""
    box, checkout, _lane_dir, _before = _started(tmp_path, short_root)
    cell = _cell(box)
    register = _published(box, "lanes/LANES.md")
    other = (f"| `repoZ-2` | harness `{PEER_SID}` | Eagle / default / peer | 2026-10-22T00:00Z | none | "
             "handoffs/repoZ/two.md | LIVE · 2026-10-22T00:00:00Z · STARTED by peer |")
    _peer_push(box, {"lanes/LANES.md": register + other + "\n"}, "repoZ-2's row")
    changed = other.replace("STARTED by peer", "PAUSED by peer")
    _peer_push(box, {"lanes/LANES.md": register + changed + "\n"}, "repoZ-2's state")
    _peer_push(box, {cell: HANDOFF}, "the lane's handoff")
    for n in range(7):
        _peer_push(box, {f"handoffs/repoQ/note-{n}.md": f"note {n}\n"}, f"another lane's note {n}")
    box.git("-C", str(checkout), "fetch", "-q", "origin", "main")
    assert box.git("-C", str(checkout), "rev-list", "--left-right", "--count",
                   "HEAD...origin/main").split() == ["0", "10"]
    assert box.git("-C", str(checkout), "status", "--porcelain") == ""

    start = box.start("--fresh", window_name=LANE)
    assert start.returncode == 0, start.stderr
    published = _published(box, "lanes/LANES.md")
    row = [r for r in published.splitlines() if r.startswith(f"| `{LANE}`")]
    assert len(row) == 1 and "RESUMED by " in row[0], row
    assert changed in published, "the peer's change to the row beside it is kept"
    assert f"RESUMED — lane {LANE}, session " in _published(box, f"lanes/log/{LANE}.md")
    assert _published(box, cell).splitlines()[2].startswith("RESUMED by "), _published(box, cell)
    _assert_nothing_unpublished(box, checkout)


def test_first_prompt_reads_the_checkout_copy(tmp_path, short_root):
    box, checkout, _lane_dir, _before = _started(tmp_path, short_root)
    cell = _cell(box)
    _peer_push(box, {cell: HANDOFF}, "the lane's handoff, written elsewhere")
    assert _edit(box, "refresh-workspace").returncode == 0
    stray = box.wip / cell
    stray.write_text(HANDOFF.replace("# state", "# state STRAY-W-EDIT"), encoding="utf-8")

    start = box.start("--fresh", window_name=LANE)
    assert start.returncode == 0, start.stderr
    assert "RESUMED by " in start.stdout and f"(lane {LANE}) at " in start.stdout, start.stdout
    assert "STRAY-W-EDIT" not in start.stdout, start.stdout
    assert "STRAY-W-EDIT" not in _published(box, cell), "W's stray never reaches origin"
    assert "STRAY-W-EDIT" in stray.read_text(encoding="utf-8"), "and W's stray is a person's to settle"


def test_writable_handoff_path_printed(tmp_path, short_root):
    box, checkout, _lane_dir, _before = _started(tmp_path, short_root)
    cell = _cell(box)
    second = box.start(window_name=LANE)
    assert second.returncode == 0, second.stderr
    assert f"{checkout}/{cell}" in second.stderr, second.stderr
    assert cell in second.stderr


def test_dry_run_creates_nothing_and_leaves_W(tmp_path, short_root):
    box, checkout, lane_dir = _boxed(tmp_path, short_root)
    box.env.pop("LANES_ROUTE_WRITES")
    first = box.start("--dir", str(lane_dir), window_name="claude")
    assert first.returncode == 0, first.stderr
    assert not checkout.parent.exists(), "without the opt-in the row is W's"
    box.env["LANES_ROUTE_WRITES"] = "1"
    _peer_push(box, {_cell(box): HANDOFF}, "the lane's handoff, written elsewhere")
    head = box.git("-C", str(box.wip), "rev-parse", "HEAD")
    before = _reflog(box)

    plan = box.start("--fresh", "--dry-run", window_name=LANE)
    assert plan.returncode == 0, plan.stderr
    assert not checkout.exists() and not checkout.parent.exists(), "a dry run makes no lane checkout"
    assert box.git("-C", str(box.wip), "rev-parse", "HEAD") == head, "W did not move"
    assert _reflog(box) == before
    for planned in ("refresh-workspace", f"lane-checkout {LANE} --create", f"write-handoff {LANE} --stamp"):
        assert any("PLAN" in line and planned in line for line in plan.stderr.splitlines()), (planned, plan.stderr)


def test_publish_failure_no_longer_refuses_a_plain_resume(tmp_path, short_root):
    """`lane-start:4455` died 2 after the row and the log were written, when
    `publish-handoff` failed, a lock wait over 60 s included. The stamp is the
    record of the resume, never its licence."""
    box, _checkout, _lane_dir, _before = _started(tmp_path, short_root)
    cell = _cell(box)
    _peer_push(box, {cell: HANDOFF}, "the lane's handoff, written elsewhere")
    assert _edit(box, "refresh-workspace").returncode == 0
    wrapper = box.root / "refusing-lanes-edit.sh"
    wrapper.write_text(f"""#!/usr/bin/env bash
case "${{1-}}" in publish-handoff|write-handoff) echo "test: $1 refused" >&2; exit 1 ;; esac
exec '{box.bin / "lanes-edit.sh"}' "$@"
""", encoding="utf-8")
    wrapper.chmod(0o755)

    start = subprocess.run([str(box.bin / "lane-start"), "repoZ", "1", "--no-launch", "--fresh"],
                           env=dict(box.env, LANES_EDIT=str(wrapper), FAKE_TMUX_WINDOW_NAME=LANE),
                           capture_output=True, text=True, timeout=180, check=False)
    assert start.returncode == 0, start.stderr
    assert "test: write-handoff refused" in start.stderr, start.stderr
    assert "RESUMED by " in start.stderr and "write-handoff" in start.stderr
    assert "Nothing was launched" not in start.stderr
    assert "RESUMED by " not in _published(box, cell)
    assert os.path.exists(box.wip / cell)
