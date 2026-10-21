# SPDX-License-Identifier: Apache-2.0
"""Amendment 23 S6.2: `lane-end --sweep-checkouts`, the sweep of the register
checkouts lanes leave behind.

Every lane writes the register through a clone of its own, `<W>-lanes/<lane>/`
(S1). A lane that has CLOSED (Amendment 19) leaves its clone behind, and so
does an old name beside its new one after a rename. The sweep has Amendment
19's shape: a dry run that lists them and removes nothing, then a person's
`--yes`, which needs `LANES_LANE`. The per-profile clones BESIDE W are listed
with what they hold and never removed by this build: nothing outside
`<W>-lanes/` is ever removed.

EVERY RUN HERE IS THE REAL `lane-end` AND THE REAL `lanes-edit.sh` IN A
SANDBOX: `tests/a23_box.py`'s `RegisterBox` (a bare origin, W cloned from it,
the `workspace.yaml` naming W, a `$HOME` of its own), with lanes in the
register and the logs, their checkouts under `<W>-lanes/`, and three
per-profile clones beside W chained by alternates. The fixture is #202's
`ended` style (`tests/test_precision_90a_96.py`): one function that runs the
command and hands back what it said. EVERY PATH THIS MODULE COULD REMOVE IS
UNDER THE TEST'S OWN BASETEMP, and the fixture asserts that before any run.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from a23_box import REGISTER, RegisterBox, register_text
from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lane-end is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

RUNNER = "repoS4-1"     # IDLE: the lane that runs the sweep
CLOSED = "repoS4-2"     # ENDED: its checkout is the sweep's
LIVE = "repoS4-3"       # a live session record here names it
PAUSED = "repoS4-4"     # PAUSED: a lane somebody may pick up
OLD, NEW = "repoS4-8", "repoS4-9"   # renamed: OLD is a former name of NEW
UTC = "2026-10-20T10:00:00Z"
UUID = {lane: f"a23a{n}04d-5404-4000-8000-a23a{n}04d5404"
        for n, lane in ((1, RUNNER), (2, CLOSED), (3, LIVE), (4, PAUSED), (9, NEW))}
PROFILE_CLONES = ("brett-wip-team01-laneA", "brett-wip-team02-laneA", "brett-wip-team03-laneA")


def _row(lane: str, state: str) -> str:
    return (f"| `{lane}` | harness `{UUID[lane]}` | Eagle / test / tester | 2026-10-20T00:00Z "
            f"| — | handoffs/repoS4/{lane}.md | {state} |")


def _log(lane: str, *verbs: str) -> str:
    head = f"# lane {lane} — object log (lane-collision-protocol Amendment 7)\n"
    return head + "".join(
        f"{verb} — lane {lane}, session {UUID[lane]}@Eagle, {UTC}, lane:{lane}\n"
        for verb in verbs)


class Sweep(RegisterBox):
    """W, `<W>-lanes/` with a checkout for each lane, and the clones beside W.

    `<W>-lanes/` holds: the runner's, the CLOSED lane's, the LIVE lane's and
    the PAUSED lane's checkouts; OLD's beside NEW's; a directory that is no
    checkout, a symbolic link and a hidden creation lock. Beside W: three
    per-profile clones, each borrowing from the one before it and the first
    from W (c3 → c2 → c1 → W), and a clone of another repository."""

    def __init__(self, root: Path) -> None:
        lanes = (RUNNER, CLOSED, LIVE, PAUSED, NEW)
        files = {
            REGISTER: register_text([_row(RUNNER, "LIVE · running the sweep"),
                                     _row(CLOSED, "ENDED · closed"),
                                     _row(LIVE, "LIVE · working"),
                                     _row(PAUSED, "PAUSED · swapped"),
                                     _row(NEW, "LIVE · renamed from repoS4-8")]),
            f"lanes/log/{RUNNER}.md": _log(RUNNER, "STARTED"),
            f"lanes/log/{CLOSED}.md": _log(CLOSED, "STARTED", "ENDED"),
            f"lanes/log/{LIVE}.md": _log(LIVE, "STARTED"),
            f"lanes/log/{PAUSED}.md": _log(PAUSED, "STARTED", "PAUSED"),
            f"lanes/log/{NEW}.md": _log(NEW, "STARTED"),
            "lanes/aliases.tsv": f"{OLD}\t{NEW}\t{UTC}\n",
            "handoffs/README.md": "# handoffs\n",
        }
        super().__init__(root, files)
        self.lanes_root.mkdir()
        for lane in (*lanes, OLD):
            self.clone(self.lanes_root / lane, reference=self.w)
        (self.lanes_root / "notes").mkdir()
        (self.lanes_root / "notes" / "todo.txt").write_text("not a clone\n", encoding="utf-8")
        (self.lanes_root / "a-link").symlink_to(self.checkout(CLOSED))
        (self.lanes_root / f".{CLOSED}.lock").mkdir()
        projects = self.w.parent
        previous = self.w
        self.profile_clones = []
        for name in PROFILE_CLONES:
            previous = self.clone(projects / name, reference=previous)
            self.profile_clones.append(previous)
        other = root / "other.git"
        self.git("init", "-q", "--bare", "-b", "main", str(other))
        self.clone(projects / "otherrepo", origin=other)
        # THE LIVE LANE: a session record naming its transcript, held by a
        # live process (`tests/test_lanes_index.py`'s shape), killed by PID.
        self.sleeper = subprocess.Popen(["sleep", "600"], cwd=str(root))
        sessions = self.home / ".claude" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        (sessions / "live.json").write_text(
            '{"pid":%d,"sessionId":"%s","kind":"interactive","status":"busy"}\n'
            % (self.sleeper.pid, UUID[LIVE]), encoding="utf-8")

    def close(self) -> None:
        self.sleeper.kill()
        self.sleeper.wait()

    def everything(self) -> dict:
        """Every entry under `<W>-lanes/` and beside W, with its HEAD, its
        status and its alternates: what a run that removes nothing leaves."""
        out = {}
        for parent in (self.lanes_root, self.w.parent):
            for entry in sorted(parent.iterdir()):
                key = str(entry)
                if entry.is_symlink() or not (entry / ".git").is_dir():
                    out[key] = "present"
                    continue
                c = ["-C", key]
                alt = entry / ".git" / "objects" / "info" / "alternates"
                out[key] = (self.git(*c, "rev-parse", "HEAD", check=False).strip(),
                            self.git(*c, "status", "--porcelain", "--untracked-files=all",
                                     check=False),
                            alt.read_text(encoding="utf-8") if alt.exists() else "")
        return out


def _rows(text: str) -> dict:
    """{path: (tag, why)} for the report's entry lines."""
    rows = {}
    for line in text.splitlines():
        if not line.startswith("    ") or line.startswith("     "):
            continue
        tag, _, rest = line.strip().partition(" ")
        path, _, why = rest.strip().partition("  ")
        rows[path] = (tag, why)
    return rows


@pytest.fixture
def sweep(tmp_path: Path):
    """`sweep(*args, **env)` runs `lane-end --sweep-checkouts <args>` and
    returns the process and its report's rows; `sweep.box` is the sandbox."""
    root = Path(os.path.realpath(tmp_path)) / "s"
    box = Sweep(root)
    # EVERY PATH A RUN COULD REMOVE IS UNDER THIS TEST'S OWN BASETEMP: W, its
    # parent, `<W>-lanes/` and the `$HOME` every helper reads are the box's.
    base = Path(os.path.realpath(tmp_path))
    for path in (box.w, box.w.parent, box.lanes_root, box.home):
        assert Path(os.path.realpath(path)).is_relative_to(base), path
    assert box.env["HOME"] == str(box.home)

    def run(*args: str, **env: str):
        full = dict(box.env, **env)
        result = subprocess.run(["bash", str(REPO / "lane-end"), "--sweep-checkouts", *args],
                                env=full, cwd=str(box.root), capture_output=True,
                                text=True, timeout=300, check=False)
        return result, _rows(result.stdout)

    run.box = box
    yield run
    box.close()


def _tagged(rows: dict, tag: str) -> set:
    return {path for path, (t, _) in rows.items() if t == tag}


# ------------------------------------------------------------- the dry run

def test_dry_run_lists_and_removes_nothing(sweep):
    """THE DEFAULT IS THE DRY RUN: it names the CLOSED lane's checkout and the
    former name's beside its new one as candidates, and removes, fetches and
    locks nothing (Amendment 19(c)'s shape, S6.2). 3 says something is there
    to remove."""
    box = sweep.box
    before, head = box.everything(), box.origin_head()
    result, rows = sweep()
    assert result.returncode == 3, (result.stdout, result.stderr)
    assert "DRY RUN" in result.stdout, result.stdout
    assert _tagged(rows, "candidate") == {str(box.checkout(CLOSED)), str(box.checkout(OLD))}, rows
    assert rows[str(box.checkout(OLD))][1].startswith(f"a former name of lane {NEW}"), rows
    assert box.everything() == before, "a dry run changes nothing under <W>-lanes/ or beside W"
    assert box.origin_head() == head, "nothing reached origin"
    assert not list(box.lanes_root.glob("*/lanes/.lanes-edit.lock")), "a dry run takes no lock"
    assert f"LANES_LANE=<your lane> lane-end --sweep-checkouts --yes" in result.stdout


def test_dry_run_with_nothing_to_remove_exits_0(sweep):
    """0 is nothing to remove: with the CLOSED lane's checkout and the former
    name's gone, every entry is kept."""
    box = sweep.box
    for lane in (CLOSED, OLD):
        box.checkout(lane).rename(box.root / f"aside-{lane}")
    result, rows = sweep()
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not _tagged(rows, "candidate"), rows
    assert "there is nothing to remove" in result.stdout, result.stdout


def test_yes_without_LANES_LANE_is_refused(sweep):
    """`--yes` writes a NOTED line into the log of the lane that runs it, so a
    run that names no lane is refused before anything is read or removed."""
    box = sweep.box
    before, head = box.everything(), box.origin_head()
    result, _ = sweep("--yes")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "LANES_LANE=<your lane> lane-end --sweep-checkouts --yes" in result.stderr
    assert "Nothing was removed" in result.stderr, result.stderr
    assert box.everything() == before and box.origin_head() == head


def test_yes_under_LANES_NO_FETCH_is_refused(sweep):
    """A writer whose fetch did not run is a writer S3 refuses (ratified choice
    2), and `--yes` fetches each checkout before it decides: refused before
    the first removal, not met by the NOTED line after it (rv1b's MUST 3)."""
    box = sweep.box
    before, head = box.everything(), box.origin_head()
    result, _ = sweep("--yes", LANES_LANE=RUNNER, LANES_NO_FETCH="1")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "LANES_NO_FETCH=1 is set" in result.stderr, result.stderr
    assert box.everything() == before and box.origin_head() == head


@pytest.mark.parametrize("extra", [
    ("--retire",), ("--force",), ("--inventory-only",), ("--state-was", "x"),
    ("--home", "opensoft/repoS4"), ("--reason", "why"), ("--retire-dormant", "repoS4"),
    (RUNNER,),
], ids=["retire", "force", "inventory-only", "state-was", "home", "reason",
        "retire-dormant", "a lane"])
def test_the_sweep_takes_no_lane_and_no_other_act(sweep, extra):
    """The sweep is its own act and ends no lane: every flag of another act,
    and a lane, is refused with nothing done."""
    box = sweep.box
    before = box.everything()
    result, _ = sweep(*extra)
    assert result.returncode == 2, (extra, result.stdout, result.stderr)
    assert box.everything() == before


# ------------------------------------------------------- never a candidate

def test_W_and_live_lane_never_candidates(sweep):
    """W, the readers' copy, is never a candidate, and neither is a LIVE lane's
    checkout, a PAUSED one, the runner's own, a directory that is no clone, a
    symbolic link (never followed), a hidden entry, or the checkout a caller's
    own `LANES_REPO` names."""
    box = sweep.box
    result, rows = sweep(LANES_LANE=RUNNER, LANES_REPO=str(box.checkout(PAUSED)))
    assert result.returncode == 3, (result.stdout, result.stderr)
    assert str(box.w) not in rows, "W is not even listed: it is not under <W>-lanes/"
    keep = {path: why for path, (tag, why) in rows.items() if tag == "keep"}
    assert "is LIVE" in keep[str(box.checkout(LIVE))], keep
    assert "runs this sweep" in keep[str(box.checkout(RUNNER))], keep
    assert "LANES_REPO names" in keep[str(box.checkout(PAUSED))], keep
    assert "no .git directory" in keep[str(box.lanes_root / "notes")], keep
    assert "symbolic link" in keep[str(box.lanes_root / "a-link")], keep
    assert f"lane {NEW} is IDLE" in keep[str(box.checkout(NEW))], keep
    assert not any(".lock" in path for path in rows), "hidden entries are never looked at"
    assert "1 hidden entr(ies)" in result.stdout, result.stdout
    assert _tagged(rows, "candidate") == {str(box.checkout(CLOSED)), str(box.checkout(OLD))}


def test_a_paused_lane_is_kept_without_LANES_REPO(sweep):
    """PAUSED is a lane somebody may pick up, not a CLOSED one."""
    box = sweep.box
    result, rows = sweep()
    assert rows[str(box.checkout(PAUSED))] == ("keep", f"lane {PAUSED} is PAUSED, not CLOSED (Amendment 19)")


def test_a_W_that_is_a_lane_checkout_is_refused(sweep):
    """FROM A LANE WINDOW, `LANES_WORKSPACE_ROOT` names the lane's own checkout,
    and every OTHER lane's checkout would stand "beside W". The sweep refuses,
    as `lanes-edit.sh`'s `lanes_home_check` does, naming the variable."""
    box = sweep.box
    before = box.everything()
    result, _ = sweep(LANES_WORKSPACE_ROOT=str(box.checkout(RUNNER)))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "Unset LANES_WORKSPACE_ROOT" in result.stderr, result.stderr
    assert box.everything() == before


def test_clones_beside_W_are_listed_and_never_candidates(sweep):
    """S6.2's per-profile clones are listed, and nothing outside `<W>-lanes/`
    is a candidate. A clone of another repository is not listed at all."""
    box = sweep.box
    result, rows = sweep()
    assert _tagged(rows, "beside") == {str(c) for c in box.profile_clones}, rows
    assert str(box.w.parent / "otherrepo") not in rows, rows
    assert all(Path(p).parent == box.lanes_root for p in _tagged(rows, "candidate")), rows
    assert "listed and never removed by this build" in result.stdout
