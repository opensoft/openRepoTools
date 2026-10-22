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
import re
import shutil
import signal
import subprocess
import time
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
CHAIN = ("repoS4-5", "repoS4-6", "repoS4-7")   # ENDED: checkouts made by `_chain`
UTC = "2026-10-20T10:00:00Z"
UUID = {lane: f"a23a{n}04d-5404-4000-8000-a23a{n}04d5404"
        for n, lane in ((1, RUNNER), (2, CLOSED), (3, LIVE), (4, PAUSED),
                        (5, CHAIN[0]), (6, CHAIN[1]), (7, CHAIN[2]), (9, NEW))}
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
    checkout, a symbolic link and a hidden creation lock. The CHAIN lanes are
    ENDED in the register and the logs, and have no checkout until `_chain`
    makes them. Beside W: three
    per-profile clones, each borrowing from the one before it and the first
    from W (c3 → c2 → c1 → W), and a clone of another repository."""

    def __init__(self, root: Path) -> None:
        lanes = (RUNNER, CLOSED, LIVE, PAUSED, NEW)
        files = {
            REGISTER: register_text([_row(RUNNER, "LIVE · running the sweep"),
                                     _row(CLOSED, "ENDED · closed"),
                                     _row(LIVE, "LIVE · working"),
                                     _row(PAUSED, "PAUSED · swapped"),
                                     _row(NEW, "LIVE · renamed from repoS4-8"),
                                     *(_row(lane, "ENDED · closed") for lane in CHAIN)]),
            f"lanes/log/{RUNNER}.md": _log(RUNNER, "STARTED"),
            f"lanes/log/{CLOSED}.md": _log(CLOSED, "STARTED", "ENDED"),
            f"lanes/log/{LIVE}.md": _log(LIVE, "STARTED"),
            f"lanes/log/{PAUSED}.md": _log(PAUSED, "STARTED", "PAUSED"),
            f"lanes/log/{NEW}.md": _log(NEW, "STARTED"),
            **{f"lanes/log/{lane}.md": _log(lane, "STARTED", "ENDED") for lane in CHAIN},
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


def _closed_checkout(box: Sweep) -> Path:
    """The first CHAIN lane's checkout, made, borrowing from W alone: a CLOSED
    lane's checkout for a case that needs a candidate besides repoS4-2's."""
    return box.clone(box.checkout(CHAIN[0]), reference=box.w)


def _new_name_ended(box: Sweep) -> None:
    """Lane repoS4-9, OLD's new name, ENDS on origin (its log and its row),
    and W reads it, since a dry run reads what W last fetched: OLD's checkout
    is then a former name of a CLOSED lane, and repoS4-9's own is CLOSED too."""
    box.peer_edits(f"lanes/log/{NEW}.md", _log(NEW, "STARTED"), _log(NEW, "STARTED", "ENDED"),
                   f"{NEW} ends")
    box.peer_edits(REGISTER, _row(NEW, "LIVE · renamed from repoS4-8"), _row(NEW, "ENDED · closed"),
                   f"{NEW}'s row says so")
    box.git("-C", str(box.w), "pull", "-q", "--ff-only", "origin", "main")


# ------------------------------------------------------------- the dry run

def test_dry_run_lists_and_removes_nothing(sweep):
    """THE DEFAULT IS THE DRY RUN: it names the CLOSED lane's checkout as a
    candidate, keeps the former name's beside its new one while that lane is
    not CLOSED (D29), and removes, fetches and locks nothing (Amendment
    19(c)'s shape, S6.2). 3 says something is there to remove."""
    box = sweep.box
    before, head = box.everything(), box.origin_head()
    result, rows = sweep()
    assert result.returncode == 3, (result.stdout, result.stderr)
    assert "DRY RUN" in result.stdout, result.stdout
    assert _tagged(rows, "remove") == {str(box.checkout(CLOSED))}, rows
    assert rows[str(box.checkout(OLD))][0] == "keep", rows
    assert rows[str(box.checkout(OLD))][1].startswith(f"a former name of lane {NEW}"), rows
    assert box.everything() == before, "a dry run changes nothing under <W>-lanes/ or beside W"
    assert box.origin_head() == head, "nothing reached origin"
    assert not list(box.lanes_root.glob("*/lanes/.lanes-edit.lock")), "a dry run takes no lock"
    assert "LANES_LANE=<your lane> lane-end --sweep-checkouts --yes" in result.stdout


def test_dry_run_with_nothing_to_remove_exits_0(sweep):
    """0 is nothing to remove: with the CLOSED lane's checkout gone, every
    entry is kept, the former name's too (its lane is not CLOSED, D29)."""
    box = sweep.box
    box.checkout(CLOSED).rename(box.root / f"aside-{CLOSED}")
    result, rows = sweep()
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not _tagged(rows, "remove"), rows
    assert "there is nothing to remove" in result.stdout, result.stdout


def _no_last_session(box: Sweep) -> dict:
    """`LANES_LANE` set and `LANES_SESSION` unset, with a `last-session` that
    names no session for any lane (8, no record)."""
    return {"LANES_LANE": RUNNER,
            "LANES_EDIT": _wrapped(box, "lanes-edit-no-last-session", "last-session", "  exit 8\n")}


REFUSALS = [
    pytest.param(lambda box: {}, ("LANES_LANE=<your lane> lane-end --sweep-checkouts --yes",),
                 id="no LANES_LANE"),
    pytest.param(lambda box: {"LANES_LANE": RUNNER, "LANES_NO_FETCH": "1"},
                 ("LANES_NO_FETCH=1 is set",), id="LANES_NO_FETCH=1"),
    pytest.param(lambda box: {"LANES_LANE": RUNNER, "LANES_SESSION": "unknown"},
                 ("has no transcript uuid for the session field",
                  "LANES_SESSION is 'unknown', which is not a transcript uuid"),
                 id="a LANES_SESSION that is no uuid"),
    pytest.param(_no_last_session,
                 ("has no transcript uuid for the session field",
                  f"LANES_SESSION is unset, and `lanes-edit.sh last-session {RUNNER}` names none"),
                 id="no LANES_SESSION and no last session"),
]


@pytest.mark.parametrize("env,said", REFUSALS)
def test_yes_is_refused_before_anything_is_removed(sweep, env, said):
    """`--yes` IS REFUSED (2) BEFORE ANYTHING IS READ OR REMOVED where the
    NOTED line it ends with could not be written: with no `LANES_LANE`, since
    the line goes into the log of the lane that runs it; under
    `LANES_NO_FETCH=1`, a writer S3 refuses (ratified choice 2), since
    `--yes` fetches each checkout before it decides (rv1b's MUST 3); and with
    no transcript uuid for the line's session field (Amendment 7(b), D19),
    whether `LANES_SESSION` names something else or is unset and
    `last-session` names none (rv4's NIT 5). Each is met here, and not by the
    line after the removals."""
    box = sweep.box
    before, head = box.everything(), box.origin_head()
    result, _ = sweep("--yes", **env(box))
    assert result.returncode == 2, (result.stdout, result.stderr)
    for text in (*said, "Nothing was removed"):
        assert text in result.stderr, result.stderr
    assert box.everything() == before
    assert box.origin_head() == head


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
    assert _tagged(rows, "remove") == {str(box.checkout(CLOSED))}, rows


def test_a_paused_lane_is_kept_without_LANES_REPO(sweep):
    """PAUSED is a lane somebody may pick up, not a CLOSED one."""
    box = sweep.box
    result, rows = sweep()
    assert rows[str(box.checkout(PAUSED))] == ("keep", f"lane {PAUSED} is PAUSED, not CLOSED (Amendment 19)")


@pytest.mark.parametrize("lane", [LIVE, CLOSED],
                         ids=["a LIVE lane", "an ENDED lane a live session record names"])
def test_a_live_lanes_checkout_is_kept_by_the_live_rule(sweep, lane):
    """A LANE THAT IS LIVE HERE IS KEPT BY THE LIVE RULE, whose reason names
    the live session record; so is a lane whose log says ENDED while a live
    session record here names its transcript, which is LIVE and not CLOSED.
    The class check would keep both as well, because `lanes` gives a LIVE
    lane no class at all (`lanes-edit.sh`: `ENDED|RETIRED) lr_class=closed`,
    `LIVE) :`), so no listing has a lane that is LIVE and classed closed:
    the reason is what shows that the LIVE rule kept it."""
    box = sweep.box
    if lane == CLOSED:
        record, body = _live_record(box, CLOSED)
        record.write_text(body + "\n", encoding="utf-8")
    for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
        result, rows = sweep(*args, **env)
        assert rows[str(box.checkout(lane))] == (
            "keep", f"lane {lane} is LIVE: a live session record here names it"), rows
        assert result.returncode in (0, 3), (result.stdout, result.stderr)
    assert box.checkout(lane).is_dir()


@pytest.mark.parametrize("yes", [False, True], ids=["dry run", "--yes"])
def test_a_closed_runner_keeps_its_own_checkout(sweep, yes):
    """THE RUNNER'S OWN CHECKOUT IS NEVER A CANDIDATE, even where the runner's
    own lane is CLOSED: the NOTED line goes through that checkout. Only
    another CLOSED lane's checkout is swept."""
    box = sweep.box
    other = _closed_checkout(box)
    result, rows = sweep(*(("--yes",) if yes else ()), LANES_LANE=CLOSED)
    assert rows[str(box.checkout(CLOSED))] == (
        "keep", f"lane {CLOSED} runs this sweep: its checkout is the one its NOTED line goes through"), rows
    assert result.returncode == (0 if yes else 3), (result.stdout, result.stderr)
    assert _tagged(rows, "removed" if yes else "remove") == {str(other)}, rows
    assert box.checkout(CLOSED).is_dir()
    assert os.path.lexists(other) is not yes


@pytest.mark.parametrize("yes", [False, True], ids=["dry run", "--yes"])
def test_a_former_name_of_the_runners_own_lane_is_kept_for_its_own_reason(sweep, yes):
    """A FORMER NAME OF THE RUNNER'S OWN LANE IS KEPT FOR ITS OWN TRUE REASON
    (rv4-c4's NIT c4-1, P6). Lane repoS4-8 is renamed repoS4-9, and repoS4-9
    ENDS and runs the sweep: its former name's checkout is kept, but not
    "until that lane is CLOSED", which it is already. What it may still be
    written through is a process started before the rename, whose
    `LANES_REPO` names the old path; the NOTED line goes through the lane's
    own checkout, which is kept by its own reason. Only repoS4-2's, a CLOSED
    lane that is not the runner's, is swept."""
    box = sweep.box
    old, new = box.checkout(OLD), box.checkout(NEW)
    _new_name_ended(box)
    result, rows = sweep(*(("--yes",) if yes else ()), LANES_LANE=NEW)
    assert rows[str(old)] == (
        "keep", f"a former name of lane {NEW}, which runs this sweep: a process it started "
                f"before the rename may still write through this path"), rows[str(old)]
    assert rows[str(new)] == (
        "keep", f"lane {NEW} runs this sweep: its checkout is the one its NOTED line goes through"), rows[str(new)]
    assert result.returncode == (0 if yes else 3), (result.stdout, result.stderr)
    assert _tagged(rows, "removed" if yes else "remove") == {str(box.checkout(CLOSED))}, rows
    assert old.is_dir() and new.is_dir()


def test_a_closed_lanes_checkout_named_by_LANES_REPO_is_kept(sweep):
    """THE CHECKOUT A CALLER'S `LANES_REPO` NAMES IS NEVER A CANDIDATE, even a
    CLOSED lane's: a write of that window may go through it."""
    box = sweep.box
    other = _closed_checkout(box)
    result, rows = sweep(LANES_REPO=str(box.checkout(CLOSED)))
    assert rows[str(box.checkout(CLOSED))] == (
        "keep", "the checkout LANES_REPO names, which a write of this window may go through"), rows
    assert result.returncode == 3, (result.stdout, result.stderr)
    assert _tagged(rows, "remove") == {str(other)}, rows


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
    judged = _tagged(rows, "remove") | _tagged(rows, "hold")
    assert judged, rows
    assert all(Path(p).parent == box.lanes_root for p in judged), rows
    assert "listed and never removed by this build" in result.stdout


# ------------------------------------------------------- the act, and holds

def _assert_under(base: Path, paths) -> None:
    """Every path the run removed is under the test's own basetemp."""
    for path in paths:
        assert Path(os.path.realpath(path)).is_relative_to(base), path


def _no_aside(box: Sweep) -> None:
    assert not list(box.lanes_root.glob(".*.removing-*")), "no half-removed aside is left"


def test_closed_lane_checkout_removed_live_kept(sweep, tmp_path):
    """`--yes`, run by a lane, removes the CLOSED lane's checkout, and leaves
    every other entry — the LIVE lane's, the PAUSED one's, the former name's
    beside its new one while that lane is not CLOSED (D29), a non-clone, a
    link — and every clone beside W exactly as they were. Its own checkout
    moves only by the NOTED commit it pushed."""
    box = sweep.box
    before = box.everything()
    runner = str(box.checkout(RUNNER))
    gone = {str(box.checkout(CLOSED))}
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == gone, rows
    _assert_under(Path(os.path.realpath(tmp_path)), gone)
    for path in gone:
        assert not os.path.lexists(path), path
    after = box.everything()
    assert {k: v for k, v in before.items() if k not in gone and k != runner} == \
        {k: v for k, v in after.items() if k != runner}, \
        "nothing but the removed entry changed, under <W>-lanes/ or beside W"
    assert box.git("-C", runner, "rev-parse", "HEAD").strip() == box.origin_head(), \
        "the runner's checkout moved only to the NOTED commit it pushed"
    assert after[runner][1:] == before[runner][1:], "and holds nothing new"
    assert _tagged(rows, "beside") == {str(c) for c in box.profile_clones}
    _no_aside(box)
    assert not list(box.lanes_root.glob("*/lanes/.lanes-edit.lock")), "every lock it took is released"


def test_ignored_files_are_named_at_the_act(sweep):
    """IGNORED FILES HOLD NOTHING, AND THE ACT NAMES THEM as the dry run does
    (rv4's NIT 2), so what went with a removed checkout is on its line."""
    box = sweep.box
    c = box.checkout(CLOSED)
    (c / ".git" / "info" / "exclude").write_text("*.log\n", encoding="utf-8")
    box.write(c, "scratch.log", "ignored\n")
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(c)][0] == "removed", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "ignored, which holds nothing: 1 (scratch.log)" in rows[str(c)][1], rows[str(c)]


def _commit_unpushed(box: Sweep, c: Path) -> None:
    box.write(c, "lanes/extra.md", "a record never pushed\n")
    box.commit(c, "an unpushed record", "lanes/extra.md")


def _stash(box: Sweep, c: Path) -> None:
    (c / "handoffs" / "README.md").write_text("# handoffs\nstashed\n", encoding="utf-8")
    box.git("-C", str(c), "stash", "-q")


def _staged(box: Sweep, c: Path) -> None:
    box.write(c, "handoffs/staged.md", "staged, never committed\n")
    box.git("-C", str(c), "add", "--", "handoffs/staged.md")


def _modified(box: Sweep, c: Path) -> None:
    (c / "handoffs" / "README.md").write_text("# handoffs\nedited by hand\n", encoding="utf-8")


def _untracked_handoff(box: Sweep, c: Path) -> None:
    box.write(c, "handoffs/repoS4/draft.md", "a handoff written, never committed\n")


def _untracked_elsewhere(box: Sweep, c: Path) -> None:
    box.write(c, "notes.txt", "a person's note in the root\n")


def _side_branch(box: Sweep, c: Path) -> None:
    box.git("-C", str(c), "switch", "-q", "-c", "side")
    _commit_unpushed(box, c)
    box.git("-C", str(c), "switch", "-q", "main")


def _detached(box: Sweep, c: Path) -> None:
    box.git("-C", str(c), "switch", "-q", "--detach")
    _commit_unpushed(box, c)


def _merge_only(box: Sweep, c: Path) -> None:
    """A merge commit origin lacks, whose parents origin has both, carrying
    content of its own. `git cherry` skips merges, so it lists no `+` line at
    all here, and only the merge check can hold it: B, an empty commit, is
    published to origin's main; main goes back to B's parent; and B is merged
    in with `--no-ff` and a file only the merge carries."""
    c_ = ["-C", str(c)]
    box.git(*c_, "commit", "-q", "--allow-empty", "-m", "B, published")
    box.git(*c_, "push", "-q", "origin", "main")
    box.git(*c_, "reset", "-q", "--keep", "HEAD~1")
    box.git(*c_, "merge", "-q", "--no-ff", "--no-commit", "refs/remotes/origin/main")
    box.write(c, "lanes/evil.md", "content only the merge carries\n")
    box.git(*c_, "add", "--", "lanes/evil.md")
    box.git(*c_, "commit", "-q", "-m", "merge B, with content")
    cherry = box.git(*c_, "cherry", "refs/remotes/origin/main", "refs/heads/main")
    assert not [line for line in cherry.splitlines() if line.startswith("+")], cherry
    assert box.git(*c_, "rev-list", "--merges", "refs/heads/main", "--not",
                   "refs/remotes/origin/main").strip(), "the merge is the one commit origin lacks"


def _tag(box: Sweep, c: Path) -> None:
    box.git("-C", str(c), "commit", "-q", "--allow-empty", "-m", "tagged, never pushed")
    box.git("-C", str(c), "tag", "kept")
    box.git("-C", str(c), "reset", "-q", "--keep", "HEAD~1")


def _lock(box: Sweep, c: Path) -> None:
    (c / "lanes" / ".lanes-edit.lock").mkdir()
    (c / "lanes" / ".lanes-edit.lock" / "pid").write_text("1 none unknown\n", encoding="utf-8")


def _worktree(box: Sweep, c: Path) -> None:
    """A linked worktree of the checkout, made by hand in the shape `git
    worktree add` leaves (this suite runs no `git worktree add`): its admin
    directory under `.git/worktrees/`, and the worktree's own `.git` file."""
    linked = box.root / "wt-of-closed"
    linked.mkdir()
    admin = c / ".git" / "worktrees" / "wt-of-closed"
    admin.mkdir(parents=True)
    head = box.git("-C", str(c), "rev-parse", "HEAD").strip()
    (admin / "HEAD").write_text(head + "\n", encoding="utf-8")
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    (admin / "gitdir").write_text(f"{linked / '.git'}\n", encoding="utf-8")
    (linked / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
    assert str(linked) in box.git("-C", str(c), "worktree", "list"), "git sees the linked worktree"


def _assume_unchanged(box: Sweep, c: Path) -> None:
    box.git("-C", str(c), "update-index", "--assume-unchanged", "handoffs/README.md")
    (c / "handoffs" / "README.md").write_text("# handoffs\nhidden from status\n", encoding="utf-8")


def _merging(box: Sweep, c: Path) -> None:
    head = box.git("-C", str(c), "rev-parse", "HEAD").strip()
    (c / ".git" / "MERGE_HEAD").write_text(head + "\n", encoding="utf-8")


def _no_origin_main(box: Sweep, c: Path) -> None:
    box.git("-C", str(c), "update-ref", "-d", "refs/remotes/origin/main")


HOLDS = [
    pytest.param(_commit_unpushed, "commit(s) origin lacks by content", id="a + on main"),
    pytest.param(_side_branch, "branch side has 1 commit(s) origin lacks", id="a + on a branch"),
    pytest.param(_detached, "its detached HEAD has 1 commit(s)", id="a + on a detached HEAD"),
    pytest.param(_merge_only, "a merge commit origin lacks", id="a merge only"),
    pytest.param(_tag, "refs/tags/kept reaches commits", id="a tag"),
    pytest.param(_stash, "a stash of 1 entr(ies)", id="a stash"),
    pytest.param(_staged, "staged or modified: 1 (handoffs/staged.md)", id="staged"),
    pytest.param(_modified, "staged or modified: 1 (handoffs/README.md)", id="modified"),
    pytest.param(_untracked_handoff, "untracked: 1 (handoffs/repoS4/draft.md)", id="untracked under handoffs"),
    pytest.param(_untracked_elsewhere, "untracked: 1 (notes.txt)", id="untracked elsewhere"),
    pytest.param(_assume_unchanged, "marked assume-unchanged or skip-worktree", id="assume-unchanged"),
    pytest.param(_merging, "an operation in progress (MERGE_HEAD)", id="a merge in progress"),
    pytest.param(_lock, "lanes/.lanes-edit.lock", id="its writers' lock"),
    pytest.param(_worktree, "linked worktree(s) of it", id="a linked worktree"),
]


@pytest.mark.parametrize("make,said", HOLDS)
def test_holds(sweep, make, said):
    """S6.2 (a): each hold is reported with what it holds, and the checkout is
    left — by the dry run, and by `--yes`, which decides under its lock after
    a fetch and releases that lock as it leaves."""
    box = sweep.box
    c = box.checkout(CLOSED)
    make(box, c)
    before = box.everything()[str(c)]
    result, rows = sweep()
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert said in rows[str(c)][1], rows[str(c)]
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert said in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()
    assert box.everything()[str(c)] == before, "the held checkout is as it was"
    if make is not _lock:
        assert not (c / "lanes" / ".lanes-edit.lock").exists(), "the sweep's own lock is released"
    _no_aside(box)


def test_no_origin_main_holds_the_dry_run(sweep):
    """A checkout with no `refs/remotes/origin/main` has nothing its branches
    can be compared with, so the dry run, which fetches nothing, holds it.
    `--yes` fetches it first with an explicit refspec, which makes that ref
    again, and decides on what the fetch brought: here nothing holds it."""
    box = sweep.box
    c = box.checkout(CLOSED)
    _no_origin_main(box, c)
    _, rows = sweep()
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert "it has no refs/remotes/origin/main" in rows[str(c)][1], rows[str(c)]
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "removed", rows[str(c)]
    assert not os.path.lexists(c)
    _no_aside(box)


def _hand_edit_kept(box: Sweep, c: Path) -> Path:
    """S3 step 4's carry, refused (lane openRepoTools-3's MUST 351): the
    CLOSED lane's row is edited by hand in its checkout, a peer changes the
    same row on origin, and `lanes-edit.sh commit` KEEPS the edit in a file
    under `.git/lanes-edit/` and leaves the register at origin's version, so
    `git status` and the untracked list see nothing. The kept file's path."""
    reg = c / REGISTER
    reg.write_text(reg.read_text(encoding="utf-8").replace(
        _row(CLOSED, "ENDED · closed"), _row(CLOSED, "ENDED · closed, and a person's hand note")),
        encoding="utf-8")
    box.peer_edits(REGISTER, _row(CLOSED, "ENDED · closed"),
                   _row(CLOSED, "ENDED · closed, and a peer's note"), "a peer's note")
    done = box.helper("commit", "a person's hand note", LANES_LANE=CLOSED)
    assert done.returncode == 2, (done.stdout, done.stderr)
    kept = list((c / ".git" / "lanes-edit").glob("hand-edit-*.diff"))
    assert len(kept) == 1, (kept, done.stderr)
    assert box.git("-C", str(c), "status", "--porcelain") == "", "git status sees nothing"
    return kept[0]


@pytest.mark.parametrize("listable", [
    True,
    pytest.param(False, marks=pytest.mark.skipif(getattr(os, "geteuid", lambda: 1)() == 0,
                                                 reason="root lists a directory whose mode is 000")),
], ids=["the kept edit is named", "its directory cannot be listed"])
def test_a_hand_edit_lanes_edit_kept_holds(sweep, listable):
    """A HAND EDIT THAT `commit` KEPT IN `.git/lanes-edit/` HOLDS THE CHECKOUT
    (lane openRepoTools-3's MUST 351): it may be a person's only copy of the
    edit, and nothing else in the checkout shows it. The dry run and `--yes`
    both hold the checkout and name the file, and both stay. A directory
    that cannot be listed holds it as well: what it keeps is unknown."""
    box = sweep.box
    c = box.checkout(CLOSED)
    kept = _hand_edit_kept(box, c)
    said = (f"lanes-edit.sh keeps 1 ({kept.name}) in .git/lanes-edit/: a hand edit" if listable
            else "its .git/lanes-edit/, where lanes-edit.sh keeps a hand edit of the register "
                 "its commit could not carry, cannot be listed")
    if not listable:
        kept.parent.chmod(0)
    try:
        for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
            result, rows = sweep(*args, **env)
            assert rows[str(c)][0] == "hold", rows[str(c)]
            assert result.returncode == 0, (result.stdout, result.stderr)
            assert said in rows[str(c)][1], rows[str(c)]
    finally:
        kept.parent.chmod(0o755)
    assert c.is_dir()
    assert kept.is_file()


def test_lanes_edit_scratch_alone_holds_nothing(sweep):
    """`.git/lanes-edit/` ALSO HOLDS `lanes-edit.sh`'S OWN SCRATCH, git's words
    from a write (`apply.err`, `fetch.err`, `ff.err`, `reset.err`) and the
    lines a carry removed (`removed`), which every write leaves behind. That
    alone holds nothing (MUST 351's fix): the checkout is removed."""
    box = sweep.box
    c = box.checkout(CLOSED)
    scratch = c / ".git" / "lanes-edit"
    scratch.mkdir()
    for name in ("apply.err", "fetch.err", "ff.err", "removed", "reset.err"):
        (scratch / name).write_text("git's own words\n", encoding="utf-8")
    _, rows = sweep()
    assert rows[str(c)][0] == "remove", rows[str(c)]
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(c)][0] == "removed", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not os.path.lexists(c)


def _lanes_edit_dir(box: Sweep) -> tuple:
    """The CLOSED lane's checkout and its `.git/lanes-edit/`, not yet made."""
    c = box.checkout(CLOSED)
    return c, c / ".git" / "lanes-edit"


LOOK_ALIKES = ["apply.err.bak", "fetch.errx", "xff.err", "reset.err~", "Reset.err",
               "removed.bak", "removed2", "xremoved", "hand-edit-1.reset.err",
               ".hidden-diff", "hand edit.diff", "-hand-edit.diff"]


@pytest.mark.parametrize("name", LOOK_ALIKES)
def test_a_name_that_only_looks_like_scratch_holds(sweep, name):
    """THE SCRATCH EXEMPTION IS BY EXACT NAME (lane openRepoTools-3's SHOULD
    391): a file whose name only begins or ends like one of the five, a
    backup, a suffix, another case, a hidden file, a name with a space or a
    leading dash, is a person's, and holds the checkout in the dry run and
    under `--yes`. The file stays."""
    box = sweep.box
    c, d = _lanes_edit_dir(box)
    d.mkdir()
    (d / name).write_text("a person's note\n", encoding="utf-8")
    for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
        _, rows = sweep(*args, **env)
        assert rows[str(c)][0] == "hold", (name, rows[str(c)])
        assert "in .git/lanes-edit/: a hand edit" in rows[str(c)][1], (name, rows[str(c)])
    assert (d / name).is_file()


def test_a_subdirectory_of_lanes_edit_holds(sweep):
    """A directory in `.git/lanes-edit/` is not one of the five names, and
    what is in it may be a person's: it holds (SHOULD 391)."""
    box = sweep.box
    c, d = _lanes_edit_dir(box)
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "kept.diff").write_text("a person's note\n", encoding="utf-8")
    _, rows = sweep()
    assert rows[str(c)][0] == "hold", rows[str(c)]


def test_a_dangling_link_for_lanes_edit_holds(sweep):
    """A `.git/lanes-edit` that is a link to nowhere holds (SHOULD 391: the
    `-L` half of the guard). `-e` alone is false for a dangling link, so only
    `-L` brings it in, and what it once named is unknown."""
    box = sweep.box
    c, d = _lanes_edit_dir(box)
    d.symlink_to(box.root / "nowhere-at-all")
    _, rows = sweep()
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert ".git/lanes-edit/" in rows[str(c)][1], rows[str(c)]


def test_an_empty_lanes_edit_holds_nothing(sweep):
    """An empty `.git/lanes-edit/`, which every write makes, holds nothing:
    the checkout is removed."""
    box = sweep.box
    c, d = _lanes_edit_dir(box)
    d.mkdir()
    _, rows = sweep()
    assert rows[str(c)][0] == "remove", rows[str(c)]
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(c)][0] == "removed", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not os.path.lexists(c)


def _a_file(name: str):
    def make(d: Path) -> Path:
        d.mkdir()
        (d / name).write_text("a person's note\n", encoding="utf-8")
        return d / name
    return make


def _a_folder(name: str):
    def make(d: Path) -> Path:
        (d / name).mkdir(parents=True)
        (d / name / "kept.diff").write_text("a person's note\n", encoding="utf-8")
        return d / name / "kept.diff"
    return make


NOT_SCRATCH_BY_KIND = [
    pytest.param(_a_file("   "), id="a name of only blanks"),
    pytest.param(_a_file("\t"), id="a name of only a TAB"),
    pytest.param(_a_file("removed\n"), id="removed and a newline"),
    pytest.param(_a_file("fetch.err\nff.err"), id="fetch.err, a newline, ff.err"),
    pytest.param(_a_folder("removed"), id="a folder named removed"),
    pytest.param(_a_folder("fetch.err"), id="a folder named fetch.err"),
]


@pytest.mark.parametrize("make", NOT_SCRATCH_BY_KIND)
def test_only_a_plain_file_with_a_scratch_name_is_scratch(sweep, make):
    """`find` DECIDES WHAT IS SCRATCH, AND NO TEXT IS PARSED (lane
    openRepoTools-3's NIT 392): only a plain file named exactly as one of
    the five is the writer's. A name of blanks or with a newline in it, and
    a folder that only carries a scratch name, are a person's, and hold the
    checkout, in the dry run and under `--yes`; what they keep stays."""
    box = sweep.box
    c, d = _lanes_edit_dir(box)
    kept = make(d)
    for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
        result, rows = sweep(*args, **env)
        assert rows[str(c)][0] == "hold", rows[str(c)]
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "in .git/lanes-edit/: a hand edit" in rows[str(c)][1], rows[str(c)]
    assert kept.is_file()


def _names_lanes_edit_writes_there() -> list:
    """Every name `lanes-edit.sh` writes into `.git/lanes-edit/` but the hand
    edit's own (`hand-edit-<UTC>-<pid>.diff`), read from the script of the
    tree under test: `$cs_tmp/<name>` and `.../lanes-edit/<name>`."""
    text = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    found = set(re.findall(r"(?:\$cs_tmp|/lanes-edit)/([A-Za-z0-9_.][A-Za-z0-9_.-]*)", text))
    return sorted(n for n in found if not n.startswith("hand-edit-"))


def test_the_names_lanes_edit_writes_there_are_found():
    """The drift guard below reads its cases from `lanes-edit.sh`'s text, so
    it must find them: `fetch.err`, which every write leaves, is among them.
    Without this, a renamed variable would leave the guard with no case."""
    assert "fetch.err" in _names_lanes_edit_writes_there()


@pytest.mark.parametrize("name", _names_lanes_edit_writes_there())
def test_every_other_name_lanes_edit_writes_there_holds_nothing(sweep, name):
    """THE TWO LISTS MUST NOT DRIFT (SHOULD 391). The sweep exempts five
    names by hand; a slice that makes `lanes-edit.sh` write a sixth
    (`pull.err`, say) would hold every checkout that ever wrote, for good.
    The cases are made from the script's own text, so a sixth name fails
    here until `lane-end` knows it."""
    box = sweep.box
    c, d = _lanes_edit_dir(box)
    d.mkdir()
    (d / name).write_text("git's own words\n", encoding="utf-8")
    _, rows = sweep()
    assert rows[str(c)][0] == "remove", (name, rows[str(c)])


def test_a_live_cwd_holds(sweep):
    """S6.2 (c): a live process working inside the checkout holds it. The
    process is a `sleep` started there, killed by its PID afterwards."""
    box = sweep.box
    c = box.checkout(CLOSED)
    sleeper = subprocess.Popen(["sleep", "600"], cwd=str(c / "lanes"))
    try:
        result, rows = sweep("--yes", LANES_LANE=RUNNER)
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert rows[str(c)][0] == "hold", rows[str(c)]
        assert f"a live process works in it (pid {sleeper.pid})" in rows[str(c)][1], rows[str(c)]
        assert c.is_dir()
    finally:
        sleeper.kill()
        sleeper.wait()


def _mountinfo_path(path: Path) -> str:
    """A path as `/proc/self/mountinfo` spells it: space, TAB, newline and
    backslash as octal escapes."""
    return (str(path).replace("\\", "\\134").replace(" ", "\\040")
            .replace("\t", "\\011").replace("\n", "\\012"))


def _mount_table(box: Sweep, *points: Path, name: str = "mountinfo") -> str:
    """A mount table in `/proc/self/mountinfo`'s form, naming `/` and each of
    `points`, for `LANE_END_MOUNTINFO`, the test seam: this suite mounts
    nothing (a bind mount needs privileges a test host does not give)."""
    table = box.root / name
    lines = ["21 1 0:20 / / rw,relatime - overlay overlay rw",
             "22 21 0:21 / /proc rw,nosuid - proc proc rw"]
    lines += [f"{30 + i} 21 0:{40 + i} /outside-{i} {_mountinfo_path(p)} rw,relatime - ext4 /dev/x rw"
              for i, p in enumerate(points)]
    table.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(table)


@pytest.mark.parametrize("where", ["ignored-mnt", ".git/mnt", "ignored mnt"],
                         ids=["at an ignored path", "inside .git", "at a path with a space"])
def test_a_mount_inside_a_checkout_holds(sweep, where):
    """A FILE SYSTEM MOUNTED AT OR UNDER A CHECKOUT HOLDS IT (lane
    openRepoTools-3's SHOULD 371, and 357). A mount point at an ignored path,
    or inside `.git/`, holds nothing else, and the `mv` carries the mount
    along with its directory, so `rm -rf` would delete what the mount shows,
    which is not under `<W>-lanes/`. Here the mount table names one there:
    the dry run and `--yes` both hold the checkout, naming the mount point."""
    box = sweep.box
    c = box.checkout(CLOSED)
    (c / ".git" / "info" / "exclude").write_text("ignored-mnt/\nignored mnt/\n", encoding="utf-8")
    box.write(c, f"{where}/shown.txt", "what the mount shows, which lives elsewhere\n")
    table = _mount_table(box, c / where)
    for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
        result, rows = sweep(*args, LANE_END_MOUNTINFO=table, **env)
        assert rows[str(c)][0] == "hold", rows[str(c)]
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert (f"a file system is mounted at or under it: 1 ({_mountinfo_path(c / where)})"
                in rows[str(c)][1]), rows[str(c)]
    assert (c / where / "shown.txt").is_file()


def test_a_mount_in_a_checkout_whose_own_path_has_a_space_holds(tmp_path):
    """THE CHECKOUT'S OWN PATH IS SPELLED AS THE MOUNT TABLE SPELLS IT (SHOULD
    371): `/proc/self/mountinfo` writes a space in a mount point as `\\040`,
    so a checkout whose own path holds one (here W's parent, `with space/`)
    matches its mount points only once that path is escaped the same way.
    The dry run holds it, naming the mount point as the table spells it."""
    root = Path(os.path.realpath(tmp_path)) / "with space"
    box = Sweep(root)
    try:
        assert " " in str(box.lanes_root)
        c = box.checkout(CLOSED)
        (c / ".git" / "info" / "exclude").write_text("ignored-mnt/\n", encoding="utf-8")
        box.write(c, "ignored-mnt/shown.txt", "what the mount shows\n")
        table = _mount_table(box, c / "ignored-mnt")
        result = subprocess.run(["bash", str(REPO / "lane-end"), "--sweep-checkouts"],
                                env=dict(box.env, LANE_END_MOUNTINFO=table), cwd=str(box.root),
                                capture_output=True, text=True, timeout=300, check=False)
        rows = _rows(result.stdout)
        assert rows[str(c)][0] == "hold", (rows.get(str(c)), result.stdout, result.stderr)
        assert (f"a file system is mounted at or under it: 1 ({_mountinfo_path(c / 'ignored-mnt')})"
                in rows[str(c)][1]), rows[str(c)]
        assert result.returncode == 0, (result.stdout, result.stderr)
    finally:
        box.close()


def test_a_mount_made_after_the_listing_holds(sweep):
    """THE MOUNT TABLE IS READ AGAIN UNDER THE LOCK (SHOULD 371: "under the
    lock, just before the mv"): the table names nothing in the checkout at
    the listing, and a mount point inside its `.git/` at its own fetch. It
    is held."""
    box = sweep.box
    c = box.checkout(CLOSED)
    box.write(c, ".git/mnt/shown.txt", "what the mount shows\n")
    table = _mount_table(box)
    later = _mount_table(box, c / ".git" / "mnt", name="mountinfo.later")
    _, rows = sweep(LANE_END_MOUNTINFO=table)
    assert rows[str(c)][0] == "remove", rows[str(c)]
    _hook_on_fetch_of(box, c, f"cp -- {later} {table}")
    result, rows = sweep("--yes", LANES_LANE=RUNNER, LANE_END_MOUNTINFO=table)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert f"a file system is mounted at or under it: 1 ({c}/.git/mnt)" in rows[str(c)][1], rows[str(c)]
    assert (c / ".git" / "mnt" / "shown.txt").is_file()


@pytest.mark.parametrize("table", ["no table", "a table that names no /"])
def test_a_mount_table_that_cannot_be_read_holds(sweep, table):
    """WHERE NO MOUNT TABLE CAN BE READ, WHETHER A FILE SYSTEM IS MOUNTED IN A
    CHECKOUT CANNOT BE TOLD, AND IT IS HELD (SHOULD 371): `LANE_END_MOUNTINFO`
    names no file and `mount` fails, or names a table without `/`, which is
    no host's mount table. The dry run and `--yes` both hold it."""
    box = sweep.box
    c = box.checkout(CLOSED)
    path = box.root / "mountinfo"
    if table != "no table":
        path.write_text("30 21 0:40 /x /elsewhere rw,relatime - ext4 /dev/x rw\n", encoding="utf-8")
    shim = box.fakebin / "mount"
    shim.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    shim.chmod(0o755)
    for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
        result, rows = sweep(*args, LANE_END_MOUNTINFO=str(path), **env)
        assert rows[str(c)][0] == "hold", rows[str(c)]
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "whether a file system is mounted in it cannot be told" in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()


def test_a_cwd_that_appears_after_the_listing_holds(sweep):
    """S6.2 (c) IS READ AGAIN UNDER THE LOCK, AFTER THE FETCH (rv4's SHOULD 1,
    R1, P4): a process that starts working in the checkout after the listing,
    here at the checkout's own fetch, holds it. The process is a `sleep`,
    killed by its PID afterwards."""
    box = sweep.box
    c = box.checkout(CLOSED)
    pidfile = box.root / "late.pid"
    _hook_on_fetch_of(box, c, (
        f'( cd {c}/handoffs && exec sleep 600 ) </dev/null >/dev/null 2>&1 & '
        f'printf "%s" "$!" > {pidfile}'))
    try:
        result, rows = sweep("--yes", LANES_LANE=RUNNER)
        late = pidfile.read_text(encoding="utf-8")
        assert rows[str(c)][0] == "hold", rows[str(c)]
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert f"a live process works in it (pid {late})" in rows[str(c)][1], rows[str(c)]
        assert c.is_dir()
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text(encoding="utf-8")), signal.SIGKILL)
            except (ProcessLookupError, ValueError):
                pass


def _hook_on_fetch_of(box: Sweep, target: Path, body: str) -> None:
    """A `LANES_GIT` hook that runs `body` when the sweep fetches `target`."""
    box.use_net(hook=(
        f'case " $* " in *" -C {target} fetch "*) {body} ;; esac\n'
        "exit 0\n"))


def _push_from_peer(box: Sweep, path: str, text: str, message: str) -> str:
    """A hook's shell command: the peer that seeded origin appends `text` to
    `path` and pushes it, as another session's write lands on origin."""
    peer = box.seed
    return (f"git -C {peer} pull -q --ff-only origin main && "
            f"printf '%s' '{text}' >> {peer}/{path} && "
            f"git -C {peer} commit -q -am {message} && git -C {peer} push -q origin main")


def _resumed_on_origin(box: Sweep, lane: str) -> str:
    """A hook's shell command: `lane` RESUMES on origin, so it is no longer
    CLOSED there."""
    line = (f"RESUMED — lane {lane}, session {UUID[lane]}@Eagle, "
            f"2026-10-21T09:00:00Z, lane:{lane}\n")
    return _push_from_peer(box, f"lanes/log/{lane}.md", line, "resumed")


def test_recheck_before_removal(sweep):
    """THE HOLDS ARE READ AGAIN UNDER THE LOCK, AFTER THE FETCH: a handoff
    written into the checkout after the listing and before its removal holds
    it, whatever the listing said."""
    box = sweep.box
    c = box.checkout(CLOSED)
    _, rows = sweep()
    assert rows[str(c)][0] == "remove", rows[str(c)]
    _hook_on_fetch_of(box, c, f"printf late > {c}/handoffs/late.md")
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert "untracked: 1 (handoffs/late.md)" in rows[str(c)][1], rows[str(c)]
    assert (c / "handoffs" / "late.md").is_file()
    assert "fetch" in box.net_ops(), "the candidate was fetched before it was decided"


def test_a_lane_resumed_after_the_listing_is_kept(sweep):
    """THE LANE'S STATE IS ASKED AGAIN UNDER THE LOCK, AFTER A FETCH (rv1b's
    MUSTs 1-2): a CLOSED lane that RESUMED on origin after the listing read it
    is kept."""
    box = sweep.box
    c = box.checkout(CLOSED)
    _hook_on_fetch_of(box, c, _resumed_on_origin(box, CLOSED))
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert f"lane {CLOSED} is IDLE now, not CLOSED" in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()


def test_a_former_name_whose_new_checkout_goes_after_the_listing_is_kept(sweep):
    """A FORMER NAME IS ASKED AGAIN UNDER THE LOCK (rv4's SHOULD 1, R3). The
    listing finds repoS4-8's checkout beside its new name's, a CLOSED lane's
    (D29); at its own fetch the new name's checkout goes, so the former
    name's checkout IS that lane's own again until its next write renames it
    (S1), and is kept."""
    box = sweep.box
    old, new = box.checkout(OLD), box.checkout(NEW)
    _new_name_ended(box)
    _, rows = sweep()
    assert rows[str(old)][0] == "remove", rows[str(old)]
    _hook_on_fetch_of(box, old, f"mv -- {new} {box.root / 'aside-new'}")
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(old)][0] == "hold", rows[str(old)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (f"it is no longer a former name of lane {NEW} beside that lane's own checkout"
            in rows[str(old)][1]), rows[str(old)]
    assert old.is_dir()


def _live_record(box: Sweep, lane: str) -> tuple:
    """A session record here naming `lane`'s transcript, held by the box's own
    live `sleep`, which makes `lane` LIVE: its path and its text."""
    return (box.home / ".claude" / "sessions" / f"{lane}.json",
            '{"pid":%d,"sessionId":"%s","kind":"interactive","status":"busy"}'
            % (box.sleeper.pid, UUID[lane]))


def _live_session_of(box: Sweep, lane: str) -> str:
    """A hook's shell command that writes `_live_record`."""
    record, body = _live_record(box, lane)
    return f"printf '%s\\n' '{body}' > {record}"


def _former_name_kept(lane_said: str) -> str:
    """The keep reason of OLD's checkout beside repoS4-9's (D29)."""
    return (f"a former name of lane {NEW}, beside that lane's own checkout, kept until that "
            f"lane is CLOSED: a process started before the rename may still write through "
            f"this path; {lane_said}")


def test_a_former_name_of_a_lane_not_closed_is_kept(sweep):
    """A FORMER NAME'S CHECKOUT IS SWEPT ONLY ONCE ITS LANE IS CLOSED, as every
    other checkout is (rv4-c3's SHOULD c3-1, P1; D29, superseding D27's LIVE
    test). Since 10-19 the launcher exports `LANES_REPO=<W>-lanes/<lane>`, and
    a process started before the rename still names the old path: here a
    landing pilot's stand-in, a `sleep` carrying `LANES_REPO=<W>-lanes/OLD`,
    working elsewhere, that outlived its window's session, so repoS4-9 is
    IDLE and not LIVE. The checkout is kept by the dry run and by `--yes`."""
    box = sweep.box
    old = box.checkout(OLD)
    pilot = subprocess.Popen(["sleep", "600"], cwd=str(box.root),
                             env=dict(box.env, LANES_REPO=str(old)))
    try:
        for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
            result, rows = sweep(*args, **env)
            assert rows[str(old)] == ("keep", _former_name_kept(
                f"lane {NEW} is IDLE, not CLOSED (Amendment 19)")), rows[str(old)]
            assert result.returncode in (0, 3), (result.stdout, result.stderr)
        assert old.is_dir()
    finally:
        pilot.kill()
        pilot.wait()


def test_a_former_name_of_a_closed_lane_is_removed(sweep):
    """ONCE ITS LANE IS CLOSED, A FORMER NAME'S CHECKOUT BESIDE ITS NEW ONE IS A
    CANDIDATE (S1: *"reports `<W>-lanes/<old>/`, which S6's sweep lists"*;
    D29): repoS4-9 ENDS, so the dry run lists repoS4-8's checkout as a former
    name to remove, and `--yes` removes it, and repoS4-9's own CLOSED one."""
    box = sweep.box
    old, new = box.checkout(OLD), box.checkout(NEW)
    _new_name_ended(box)
    result, rows = sweep()
    assert result.returncode == 3, (result.stdout, result.stderr)
    assert rows[str(old)] == ("remove", f"a former name of lane {NEW}, beside that lane's own "
                              f"checkout {new}; lane {NEW} is CLOSED (ENDED)"), rows[str(old)]
    assert rows[str(new)][0] == "remove", rows[str(new)]
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED)), str(old), str(new)}, rows
    assert not os.path.lexists(old)
    assert not os.path.lexists(new)


def test_a_former_name_whose_lane_resumes_after_the_listing_is_kept(sweep):
    """A FORMER NAME'S LANE IS ASKED AGAIN UNDER THE LOCK, as every lane is
    (D29): repoS4-9 is CLOSED at the listing and RESUMES on origin at its
    former name's own fetch, so the re-ask reads it IDLE, and the checkout
    is kept."""
    box = sweep.box
    old = box.checkout(OLD)
    _new_name_ended(box)
    _hook_on_fetch_of(box, old, _resumed_on_origin(box, NEW))
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(old)][0] == "hold", rows[str(old)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert f"lane {NEW} is IDLE now, not CLOSED" in rows[str(old)][1], rows[str(old)]
    assert old.is_dir()


def test_a_former_name_of_a_live_lane_is_kept(sweep):
    """A FORMER NAME'S CHECKOUT IS KEPT WHILE ITS LANE IS LIVE (rv4's SHOULD 4),
    as while it is anything but CLOSED (D29). Here repoS4-9 is LIVE: a live
    session record names its transcript. Its former name's checkout is kept
    by the dry run and by `--yes`."""
    box = sweep.box
    old = box.checkout(OLD)
    record, body = _live_record(box, NEW)
    record.write_text(body + "\n", encoding="utf-8")
    for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
        result, rows = sweep(*args, **env)
        assert rows[str(old)] == ("keep", _former_name_kept(
            f"lane {NEW} is LIVE: a live session record here names it")), rows[str(old)]
        assert result.returncode in (0, 3), (result.stdout, result.stderr)
    assert old.is_dir()


def test_a_former_name_whose_lane_goes_live_after_the_listing_is_kept(sweep):
    """THE SAME RULE, ASKED AGAIN UNDER THE LOCK (D29): repoS4-9 is CLOSED at
    the listing, so its former name's checkout is a candidate, and comes LIVE
    at that checkout's own fetch. It is kept."""
    box = sweep.box
    old = box.checkout(OLD)
    _new_name_ended(box)
    _hook_on_fetch_of(box, old, _live_session_of(box, NEW))
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(old)][0] == "hold", rows[str(old)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert f"lane {NEW} is LIVE now" in rows[str(old)][1], rows[str(old)]
    assert old.is_dir()


def test_a_fetch_that_fails_holds(sweep):
    """`--yes` decides on a fetched origin: a candidate whose fetch fails is
    held, and its lock released."""
    box = sweep.box
    c = box.checkout(CLOSED)
    box.use_net(hook=f'case " $* " in *" -C {c} fetch "*) exit 1 ;; esac\nexit 0\n')
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert "its fetch of origin main failed" in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()
    assert not (c / "lanes" / ".lanes-edit.lock").exists(), "its lock is released"


def test_a_checkout_whose_origin_changes_after_the_listing_is_held(sweep):
    """WHAT MADE IT A REGISTER CHECKOUT IS ASKED AGAIN UNDER THE LOCK (rv4's
    NIT 4): at its own fetch the CLOSED lane's checkout is pointed at another
    repository (W's path here, which that fetch then reads), so it is no
    longer a clone of the register's origin, and it is held."""
    box = sweep.box
    c = box.checkout(CLOSED)
    _hook_on_fetch_of(box, c, f"git -C {c} remote set-url origin {box.w}")
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert f"a checkout of {box.w}, not of the register's origin" in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()


def test_the_lock_is_refreshed_before_the_reask(sweep):
    """THE SWEEP KEEPS ITS LOCK FRESH (rv4's NIT 4; rv4-c3's NIT c3-4, P5). A
    writer in another container ages a lock by its directory's mtime alone
    (`mutex_stale`'s ten minutes, `find -mmin -10`), so the sweep refreshes
    it (`sc_lock_beat`, `touch -c`) before each slow step. Here the lock is
    aged twenty minutes during the candidate's own fetch; when the lane's
    state is asked again under that lock, it reads under ten minutes old."""
    box = sweep.box
    c = box.checkout(CLOSED)
    lock = box.lock_of(c)
    aged, fresh = box.root / "aged.txt", box.root / "fresh.txt"
    stamp = time.strftime("%Y%m%d%H%M.%S", time.gmtime(time.time() - 20 * 60))
    _hook_on_fetch_of(box, c, (
        f"TZ=UTC0 touch -t {stamp} {lock} && "
        f'printf "[%s]\\n" "$(find {lock} -maxdepth 0 -mmin +10)" >> {aged}'))
    wrapper = _wrapped(box, "lanes-edit-age", "lanes", (
        f'  case " $* " in *" --lane {CLOSED} "*) '
        f'printf "[%s]\\n" "$(find {lock} -maxdepth 0 -mmin -10)" >> {fresh} ;; esac\n'))
    result, rows = sweep("--yes", LANES_LANE=RUNNER, LANES_EDIT=wrapper)
    assert aged.read_text(encoding="utf-8") == f"[{lock}]\n", "the hook aged the lock"
    assert fresh.read_text(encoding="utf-8") == f"[{lock}]\n", "fresh again at the re-ask"
    assert rows[str(c)][0] == "removed", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)


@pytest.mark.parametrize("then,why", [
    ("", "its writers' lock lanes/.lanes-edit.lock is no longer this sweep's (1 other-container otherhost)"),
    ("; exit 1", "its fetch of origin main failed"),
], ids=["then the move is asked", "then the fetch fails"])
def test_a_lock_taken_over_under_the_sweep_holds_and_is_left(sweep, then, why):
    """THE LOCK IS THE SWEEP'S UNTIL THE MOVE, OR NOTHING IS MOVED (rv4's NIT
    4): at the checkout's fetch another writer's pid line replaces the
    sweep's in its `lanes/.lanes-edit.lock`, as a takeover from another
    container does. The checkout is held, by the pid line read again before
    the move, or by whatever else holds it first (here, a fetch that fails),
    and in both that writer's lock is left as it is, as `lanes-edit.sh`'s
    `mutex_release` leaves a lock it no longer holds."""
    box = sweep.box
    c = box.checkout(CLOSED)
    pid = c / "lanes" / ".lanes-edit.lock" / "pid"
    _hook_on_fetch_of(box, c, f"printf '1 other-container otherhost\\n' > {pid}{then}")
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert why in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()
    assert pid.read_text(encoding="utf-8") == "1 other-container otherhost\n"


def test_a_lock_taken_over_is_left_by_a_sweep_ended_by_a_signal(sweep):
    """THE WAY OUT LEAVES A LOCK TAKEN OVER, TOO (rv4's NIT 4): at the
    checkout's fetch, another writer's pid line replaces the sweep's and the
    sweep is sent TERM. It exits 143, and `cleanup`, run on the way out,
    leaves that writer's lock as it is and the checkout where it was."""
    box = sweep.box
    c = box.checkout(CLOSED)
    pid = c / "lanes" / ".lanes-edit.lock" / "pid"
    _hook_on_fetch_of(box, c, (
        f"read -r swept _ < {pid}; printf '1 other-container otherhost\\n' > {pid}; "
        'kill -TERM "$swept"; exit 1'))
    result, _ = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 143, (result.stdout, result.stderr)
    assert c.is_dir()
    assert pid.read_text(encoding="utf-8") == "1 other-container otherhost\n"


@pytest.mark.parametrize("after", [
    pytest.param("chmod 500 {lock}", id="the lock directory cannot be written in",
                 marks=pytest.mark.skipif(getattr(os, "geteuid", lambda: 1)() == 0,
                                          reason="root writes in a directory it may not write in")),
    pytest.param("ln -s /dev/full {lock}/pid", id="the pid file's write fails, as on a full disk",
                 marks=pytest.mark.skipif(not os.path.exists("/dev/full"),
                                          reason="no /dev/full here to fail a write")),
])
def test_a_lock_whose_pid_line_cannot_be_written_is_let_go(sweep, after):
    """THE SWEEP'S PID LINE IS WRITTEN, OR ITS LOCK IS LET GO (rv4-c3's NIT
    c3-2, P2; rv4-c4's NIT c4-2, P7). A lock that names no holder is one its
    writers wait ten minutes on (`mutex_stale`), and the check before the
    move read the sweep's own pid-less lock as taken over and left it there,
    so every later sweep held that checkout. Here the sweep's `mkdir` of the
    CLOSED lane's lock (a `mkdir` first on PATH) leaves a lock its line
    cannot be written into, in two ways. The directory is read-only, so the
    open fails and no pid file is made. Or a pid file is there whose writes
    fail: on a full disk the open succeeds and leaves an EMPTY pid file, and
    the `rmdir` takes the lock away only once the sweep's `rm -f` has removed
    that file. Either way the checkout is held with that reason, the lock is
    gone, and the next sweep removes the checkout."""
    box = sweep.box
    c = box.checkout(CLOSED)
    lock = box.lock_of(c)
    shim = box.fakebin / "mkdir"
    shim.write_text(f'#!/usr/bin/env bash\n{shutil.which("mkdir")} "$@" || exit\n'
                    f'case " $* " in *" {lock} "*) {after.format(lock=lock)} ;; esac\n',
                    encoding="utf-8")
    shim.chmod(0o755)
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not os.path.lexists(lock), (
        "a lock that names no holder is not left behind", sorted(os.listdir(lock)))
    assert ("its writers' lock was taken, and this sweep's pid line could not be written "
            "into it, so the lock was let go again") in rows[str(c)][1], rows[str(c)]
    shim.rename(box.root / "mkdir.aside")
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(c)][0] == "removed", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)


@pytest.mark.parametrize("op,note", [
    ("fetch", "fetch failed — reading the logs as they stand locally"),
    ("ls-remote", "NO FETCH WAS MADE"),
], ids=["the fetch fails after ls-remote (fell-back)", "ls-remote fails (no fetch)"])
def test_a_W_fetch_that_fails_at_the_listing_refuses_yes(sweep, op, note):
    """`--yes` decides on a register fetched just now (D14). Either way W's
    fetch can fail refuses it before the first removal, with nothing written:
    the FETCH fails while `ls-remote` succeeds, which `log_sync` says as
    `fell-back` — it reads the stale ref and exits 0, and the listing's own
    note has the phrase "reading the logs as they stand locally" without "NO
    FETCH WAS MADE" (rv4's MUST 1, P5) — or `ls-remote` fails, and no fetch is
    made at all (rv4-r2's NIT 1)."""
    box = sweep.box
    before, head = box.everything(), box.origin_head()
    box.use_net(hook=f'case " $* " in *" -C {box.w} {op} "*) exit 1 ;; esac\nexit 0\n')
    result, _ = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert note in result.stderr, result.stderr
    assert "reading the logs as they stand locally" in result.stderr, result.stderr
    assert "W's fetch did not complete" in result.stderr, result.stderr
    assert "Nothing was removed" in result.stderr, result.stderr
    assert box.everything() == before
    assert box.origin_head() == head
    assert "push" not in box.net_ops()


def test_a_lane_resumed_while_W_cannot_fetch_is_kept(sweep):
    """THE RE-CHECK UNDER THE LOCK IS A FRESH READ OR NONE (rv4's MUST 1, P1).
    W fetches at the listing; the CLOSED lane then RESUMES on origin at its
    own checkout's fetch, and W's fetch fails from then on, so the re-ask in
    `sc_still` reads the stale ref, in which the lane is still CLOSED. That is
    not a decision made after a fetch: the checkout is kept, and the reason
    says why."""
    box = sweep.box
    c = box.checkout(CLOSED)
    marker = box.root / "resumed.marker"
    box.use_net(hook=(
        'case " $* " in\n'
        f'  *" -C {c} fetch "*) {_resumed_on_origin(box, CLOSED)} && touch {marker} ;;\n'
        f'  *" -C {box.w} fetch "*) if [ -e {marker} ]; then exit 1; fi ;;\n'
        'esac\nexit 0\n'))
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert marker.exists(), box.net_log.read_text(encoding="utf-8")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert "was not read fresh" in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()


def test_a_W_ls_remote_that_fails_at_the_recheck_holds(sweep):
    """THE RE-ASK MAKES NO FETCH AT ALL WHEN W'S `ls-remote` FAILS (rv4-r2's
    NIT 1): W fetches at the listing, and its `ls-remote` fails from the
    candidate's own fetch on, so the re-ask's note is "NO FETCH WAS MADE ...
    reading the logs as they stand locally". The checkout is kept."""
    box = sweep.box
    c = box.checkout(CLOSED)
    marker = box.root / "fetched.marker"
    box.use_net(hook=(
        'case " $* " in\n'
        f'  *" -C {c} fetch "*) touch {marker} ;;\n'
        f'  *" -C {box.w} ls-remote "*) if [ -e {marker} ]; then exit 1; fi ;;\n'
        'esac\nexit 0\n'))
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert marker.exists(), box.net_log.read_text(encoding="utf-8")
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert ("was not read fresh under its checkout's lock: W's fetch did not complete"
            in rows[str(c)][1]), rows[str(c)]
    assert c.is_dir()


@pytest.mark.skipif(getattr(os, "geteuid", lambda: 1)() == 0,
                    reason="root reads a directory whose mode is 000")
def test_session_records_unreadable_at_the_recheck_keep_the_checkout(sweep):
    """The re-ask under the lock says "session records could not be read" on
    stderr and exits 0, as the listing does; the listing's refusal is exit 1.
    Here the records are readable at the listing and are not at the re-check,
    so which lanes are LIVE is no longer established, and a LIVE lane's
    checkout is never swept: the CLOSED lane's checkout is kept."""
    box = sweep.box
    c = box.checkout(CLOSED)
    sessions = box.home / ".claude" / "sessions"
    _hook_on_fetch_of(box, c, f"chmod 000 {sessions}")
    try:
        result, rows = sweep("--yes", LANES_LANE=RUNNER)
    finally:
        sessions.chmod(0o700)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert "was not read fresh" in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()


@pytest.mark.skipif(getattr(os, "geteuid", lambda: 1)() == 0,
                    reason="root reads a file whose mode is 000")
def test_a_capture_that_cannot_be_read_back_holds_by_itself(sweep):
    """THE RE-ASK'S NOTES ARE READ BACK, OR THE CHECKOUT IS HELD FOR THAT, with
    its own reason (rv4-r2's SHOULD 1). The file `sc_still` captures the
    re-ask's notes in goes mode 000 during the re-ask's own fetch of W, so
    `cat` cannot read it back. The checkout is held because the capture could
    not be read back, not by a stand-in sentence that matches another note's
    clause and then names that note's reason."""
    box = sweep.box
    c = box.checkout(CLOSED)
    tmpdir = Path(box.env["TMPDIR"])
    marker = box.root / "fetched.marker"
    box.use_net(hook=(
        'case " $* " in\n'
        f'  *" -C {c} fetch "*) touch {marker} ;;\n'
        f'  *" -C {box.w} fetch "*) if [ -e {marker} ]; then '
        f'chmod 000 {tmpdir}/lane-end-sweep.* 2>/dev/null || :; fi ;;\n'
        'esac\nexit 0\n'))
    try:
        result, rows = sweep("--yes", LANES_LANE=RUNNER)
    finally:
        for p in tmpdir.glob("lane-end-sweep.*"):
            p.chmod(0o600)
    assert marker.exists(), box.net_log.read_text(encoding="utf-8")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert "its capture could not be read back" in rows[str(c)][1], rows[str(c)]
    assert "the register could not be read" not in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()


def test_a_register_unreadable_at_the_recheck_keeps_the_checkout(sweep):
    """The re-ask under the lock says the register "could not be read, so its
    rows are not in this listing" and exits 0, as the listing does; the
    listing's refusal is exit 1. Here the register reads at the listing; then
    origin takes a commit that changes it, and the re-ask's own fetch of W
    brings that commit in, after which its register blob is moved out of W's
    objects. The tree still names the register, so it is published and `git
    show` cannot read it: whether the lane is CLOSED is no longer established,
    and the checkout is kept."""
    box = sweep.box
    c = box.checkout(CLOSED)
    marker = box.root / "pushed.marker"
    aside = box.root / "register-blob.aside"
    touched = _push_from_peer(box, "lanes/LANES.md", "\n", "touched")
    box.use_net(hook=(
        'case " $* " in\n'
        f'  *" -C {c} fetch "*) if [ ! -e {marker} ]; then {touched} && touch {marker}; fi ;;\n'
        f'  *" -C {box.w} fetch "*) if [ -e {marker} ]; then shift; git "$@" || exit $?; '
        f'b="$(git -C {box.w} rev-parse refs/remotes/origin/main:lanes/LANES.md)" && '
        f'mv -- "{box.w}/.git/objects/${{b:0:2}}/${{b:2}}" {aside} 2>/dev/null; exit 97; fi ;;\n'
        'esac\nexit 0\n'))
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert aside.is_file(), box.net_log.read_text(encoding="utf-8")
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert ("was not read fresh under its checkout's lock: the register could not be read"
            in rows[str(c)][1]), rows[str(c)]
    assert c.is_dir()


def test_nothing_outside_W_lanes_is_removed(sweep):
    """The clones beside W are listed with what holds them, and `--yes` removes
    none of them: nothing outside `<W>-lanes/` is ever removed."""
    box = sweep.box
    before = {str(c): box.everything()[str(c)] for c in box.profile_clones}
    _, rows = sweep()
    assert rows[str(box.profile_clones[0])] == ("beside", f"holds: leaned on by {box.profile_clones[1]} (its alternates file names this clone's objects)"), rows
    assert rows[str(box.profile_clones[2])][1].startswith("nothing holds it"), rows
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert {str(c): box.everything()[str(c)] for c in box.profile_clones} == before
    assert all(rows[str(c)] == ("beside", "left") for c in box.profile_clones), rows


# ------------------------------------------------- leaves first, and chains

def _chain(box: Sweep) -> list:
    """Three CLOSED lanes' checkouts under `<W>-lanes/`, each borrowing objects
    from the one before it: 7 from 6, 6 from 5, and 5 from W."""
    out, previous = [], box.w
    for lane in CHAIN:
        previous = box.clone(box.checkout(lane), reference=previous)
        out.append(previous)
    return out


def _entries(text: str, paths) -> list:
    """`(tag, path)` for each report line naming one of `paths`, in the order
    the report gives them."""
    want = {str(p) for p in paths}
    out = []
    for line in text.splitlines():
        if not line.startswith("    ") or line.startswith("     "):
            continue
        tag, _, rest = line.strip().partition(" ")
        path = rest.strip().partition("  ")[0]
        if path in want:
            out.append((tag, path))
    return out


def test_leaves_first_in_one_run(sweep, tmp_path):
    """S6.2 (b): *"so leaves go first"*. A chain of CLOSED lanes' checkouts,
    each borrowing objects from the one before it (7 → 6 → 5 → W), is all
    removable in ONE run: the dry run lists 7, 6, 5 as removable in that
    order, though the directory lists them 5, 6, 7, and `--yes` removes them
    in that order. W, which 5 borrows from, is never a candidate."""
    box = sweep.box
    chain = _chain(box)
    leaves_first = [str(c) for c in reversed(chain)]
    result, _ = sweep()
    assert result.returncode == 3, (result.stdout, result.stderr)
    assert _entries(result.stdout, chain) == [("remove", p) for p in leaves_first], result.stdout
    result, _ = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert _entries(result.stdout, chain) == [("removed", p) for p in leaves_first], result.stdout
    _assert_under(Path(os.path.realpath(tmp_path)), chain)
    for c in chain:
        assert not os.path.lexists(c), c
    box.git("-C", str(box.w), "fsck", "--connectivity-only")   # W, which 5 borrowed from, is whole
    _no_aside(box)


@pytest.mark.parametrize("held,expect", [
    (2, {2: "commit(s) origin lacks", 1: "leaned on by {2}", 0: "leaned on by {1}"}),
    (1, {2: "removed", 1: "commit(s) origin lacks", 0: "leaned on by {1}"}),
    (0, {2: "removed", 1: "removed", 0: "commit(s) origin lacks"}),
], ids=["the leaf held", "the middle held", "the root held"])
def test_held_parent_keeps_its_dependents_chain(sweep, held, expect):
    """S6.2 (b): *"A clone still depended on by a held clone stays."* One
    link of the chain 7 → 6 → 5 holds an unpublished commit. Everything that
    link borrows from, down to W, is held by it — in the dry run and under
    `--yes`, which reads what leans on each candidate again just before its
    removal — while every link that borrows from it, held by nothing, goes."""
    box = sweep.box
    chain = _chain(box)
    _commit_unpushed(box, chain[held])
    for args, env, gone in ((), {}, "remove"), (("--yes",), {"LANES_LANE": RUNNER}, "removed"):
        result, rows = sweep(*args, **env)
        assert result.returncode in (0, 3), (result.stdout, result.stderr)
        for i, said in expect.items():
            c = str(chain[i])
            if said == "removed":
                assert rows[c][0] == gone, (c, rows[c])
            else:
                assert rows[c][0] == "hold", (c, rows[c])
                assert said.format(*chain) in rows[c][1], (c, rows[c])
    for i, said in expect.items():
        assert os.path.lexists(chain[i]) == (said != "removed"), chain[i]


@pytest.mark.skipif(getattr(os, "geteuid", lambda: 1)() == 0,
                    reason="root removes what a read-only directory holds")
def test_a_removal_that_does_not_finish_exits_1(sweep):
    """A REMOVAL THAT DOES NOT FINISH IS SAID, BY PATH, AND EXITS 1 (rv4's
    SHOULD 1, R4). The CLOSED lane's checkout holds an IGNORED directory
    (ignored files hold nothing) that is read-only, so the checkout is moved
    aside and the removal of the aside stops partway: it is named PARTLY,
    the run exits 1, and the aside stays, hidden, under `<W>-lanes/`."""
    box = sweep.box
    c = box.checkout(CLOSED)
    other = _closed_checkout(box)
    (c / ".git" / "info" / "exclude").write_text("scratch/\n", encoding="utf-8")
    box.write(c, "scratch/kept.txt", "an ignored file in a read-only directory\n")
    (c / "scratch").chmod(0o555)
    try:
        result, rows = sweep("--yes", LANES_LANE=RUNNER)
        asides = list(box.lanes_root.glob(f".{CLOSED}.removing-*"))
        assert rows[str(c)][0] == "PARTLY", rows[str(c)]
        assert result.returncode == 1, (result.stdout, result.stderr)
        assert len(asides) == 1, asides
        assert f"the removal of {asides[0]} did not finish" in result.stderr, result.stderr
        assert not os.path.lexists(c)
        assert (asides[0] / "scratch" / "kept.txt").is_file()
        # A removal that did not finish is counted apart from the ones that
        # did (rv4's NIT 3), on the summary line and in the NOTED line, and
        # its ignored files are named at the act (NIT 2).
        assert "ignored, which holds nothing: 1 (scratch/)" in rows[str(c)][1], rows[str(c)]
        assert "  1 removed, 1 moved aside and not all removed, " in result.stdout, result.stdout
        noted = _noted_on_origin(box)
        assert len(noted) == 1, noted
        assert (f"removed 1 register checkout(s) under brett-wip-lanes/ that held nothing "
                f"unpublished: {other.name}; moved aside and not all removed: {asides[0].name};") in noted[0], noted
    finally:
        for aside in box.lanes_root.glob(f".{CLOSED}.removing-*"):
            (aside / "scratch").chmod(0o755)
        if (c / "scratch").is_dir():
            (c / "scratch").chmod(0o755)


# ------------------------------------------- a stopped act, and its leftovers

def _run_own_group(box: Sweep, *args: str, **env: str):
    """`lane-end --sweep-checkouts` in a process group of its own, so a
    signal sent to the group, as a terminal's Ctrl-C is, reaches the sweep and
    its children and nothing of the test's."""
    result = subprocess.run(["bash", str(REPO / "lane-end"), "--sweep-checkouts", *args],
                            env=dict(box.env, **env), cwd=str(box.root), capture_output=True,
                            text=True, timeout=300, check=False, start_new_session=True)
    return result, _rows(result.stdout)


def _rm_shim(box: Sweep, lane: str, action: str) -> None:
    """An `rm` first on PATH: for the aside of `lane`'s checkout it runs
    `action` (a signal) first; every `rm` then runs the real one."""
    real = shutil.which("rm")
    assert real, "no rm on the test's own PATH"
    shim = box.fakebin / "rm"
    shim.write_text("#!/usr/bin/env bash\n"
                    f'case "$*" in *"/.{lane}.removing-"*) {action} ;; esac\n'
                    f'exec {real} "$@"\n', encoding="utf-8")
    shim.chmod(0o755)


@pytest.mark.parametrize("send,code", [
    pytest.param("kill -INT 0", 130, id="INT to its process group, as a Ctrl-C"),
    pytest.param("kill -TERM $PPID", 143, id="TERM to the sweep alone"),
])
def test_a_signal_during_a_removal_lets_it_finish_and_prints_the_record(sweep, send, code):
    """AN INTERRUPTED `--yes` LEAVES ITS RECORD, AND NO CHECKOUT HALF REMOVED
    (lane openRepoTools-3's SHOULD 372). Two CLOSED lanes' checkouts are
    removed, and the signal comes as the second one's `rm` starts. The `rm`
    finishes, so no aside is left, and the sweep then exits with the
    signal's code and the NOTED line by hand for both removals; no line is
    written. Run as printed, it lands once."""
    box = sweep.box
    c, other = box.checkout(CLOSED), _closed_checkout(box)
    _rm_shim(box, other.name, send)
    result, rows = _run_own_group(box, "--yes", LANES_LANE=RUNNER)
    assert result.returncode == code, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "removed", rows
    assert rows[str(other)][0] == "removed", rows
    assert not os.path.lexists(c)
    assert not os.path.lexists(other)
    _no_aside(box)
    assert not list(box.lanes_root.glob("*/lanes/.lanes-edit.lock")), "no lock is left"
    assert not _noted_on_origin(box)
    assert "a signal stopped this sweep after the removals above" in result.stderr, result.stderr
    remedies = _remedies(result.stderr)
    assert len(remedies) == 1, remedies
    assert remedies[0].startswith(
        f"LANES_LANE={RUNNER} LANES_SESSION={UUID[RUNNER]} lanes-edit.sh log NOTED "), remedies
    done = _by_hand(box, remedies[0])
    assert done.returncode == 0, (done.stdout, done.stderr)
    noted = _noted_on_origin(box)
    assert len(noted) == 1, noted
    assert (f"removed 2 register checkout(s) under brett-wip-lanes/ that held nothing "
            f"unpublished: {CLOSED} {other.name};") in noted[0], noted
    assert noted[0].endswith("; the sweep was stopped by a signal"), noted


def test_a_signal_while_the_noted_line_is_written_never_writes_it_twice(sweep):
    """A SIGNAL DURING THE NOTED WRITE MAY COME AFTER THE LINE LANDED (SHOULD
    372): here the write finishes and the sweep is then sent TERM. It exits
    143, says the line may be on origin already, and hands out the publish
    act first, which finds nothing to send: origin holds the line once."""
    box = sweep.box
    stopping = _wrapped(box, "lanes-edit-stopped-log", "log", (
        '  bash "$REAL" "$@"; rc=$?\n'
        "  trap '' TERM; kill -TERM 0\n"
        '  exit "$rc"\n'))
    result, rows = _run_own_group(box, "--yes", LANES_LANE=RUNNER, LANES_EDIT=stopping)
    assert result.returncode == 143, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED))}, rows
    assert len(_noted_on_origin(box)) == 1
    assert "the line may be on origin already" in result.stderr, result.stderr
    remedies = _remedies(result.stderr)
    assert len(remedies) == 2, remedies
    assert remedies[0].startswith(f"LANES_LANE={RUNNER} lanes-edit.sh commit "), remedies
    done = _by_hand(box, remedies[0])
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert len(_noted_on_origin(box)) == 1, "the publish act wrote no second line"


def test_a_removal_left_unfinished_is_named_by_every_run(sweep, tmp_path):
    """AN ASIDE A REMOVAL LEFT IS NAMED AGAIN, BY NAME, IN EVERY RUN (SHOULD
    372), apart from the hidden entries it would otherwise be counted with,
    and with the command that removes it; no sweep removes it. The command,
    run as printed, removes it, a read-only directory inside included."""
    box = sweep.box
    aside = box.lanes_root / f".{CLOSED}.removing-20261020T100000Z-1"
    box.write(aside, "scratch/kept.txt", "what an earlier sweep could not remove\n")
    (aside / ".git").mkdir()
    (aside / "scratch").chmod(0o555)
    try:
        for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
            result, rows = sweep(*args, **env)
            assert result.returncode in (0, 3), (result.stdout, result.stderr)
            assert rows[str(aside)][0] == "leftover", rows
            assert "(1 hidden entr(ies) under" in result.stdout, "the creation lock alone"
            assert aside.is_dir()
        command = rows[str(aside)][1].split("remove it by hand: ", 1)[1]
        assert command == f"chmod -R u+rwX -- {aside} && rm -rf -- {aside}", command
        done = subprocess.run(["bash", "-c", command], cwd=str(box.root), capture_output=True,
                              text=True, env=box.env, timeout=60, check=False)
        assert done.returncode == 0, (done.stdout, done.stderr)
        _assert_under(Path(os.path.realpath(tmp_path)), [aside])
        assert not os.path.lexists(aside)
    finally:
        if (aside / "scratch").is_dir():
            (aside / "scratch").chmod(0o755)


@pytest.mark.skipif(getattr(os, "geteuid", lambda: 1)() == 0,
                    reason="root removes what a read-only directory holds")
def test_a_removal_that_does_not_finish_is_said_when_the_noted_write_fails(sweep):
    """A REMOVAL THAT DID NOT FINISH IS SAID BEFORE THE NOTED WRITE (SHOULD
    372), so a write that is refused, and exits at once, cannot leave it
    unsaid: the PARTLY aside is named, the run exits 1, and the by-hand line
    names it too."""
    box = sweep.box
    c = box.checkout(CLOSED)
    (c / ".git" / "info" / "exclude").write_text("scratch/\n", encoding="utf-8")
    box.write(c, "scratch/kept.txt", "an ignored file in a read-only directory\n")
    (c / "scratch").chmod(0o555)
    refusing = _wrapped(box, "lanes-edit-refusing-log", "log", (
        "  printf 'FAKE: the register refused this line\\n' >&2\n"
        "  exit 2\n"))
    try:
        result, rows = sweep("--yes", LANES_LANE=RUNNER, LANES_EDIT=refusing)
        asides = list(box.lanes_root.glob(f".{CLOSED}.removing-*"))
        assert rows[str(c)][0] == "PARTLY", rows[str(c)]
        assert result.returncode == 1, (result.stdout, result.stderr)
        assert len(asides) == 1, asides
        assert f"the removal of {asides[0]} did not finish" in result.stderr, result.stderr
        assert "was NOT written" in result.stderr, result.stderr
        assert not _noted_on_origin(box)
    finally:
        for aside in box.lanes_root.glob(f".{CLOSED}.removing-*"):
            (aside / "scratch").chmod(0o755)
        if (c / "scratch").is_dir():
            (c / "scratch").chmod(0o755)


# ----------------------------------------------------------- the NOTED line

def test_noted_line_written_through_runner_checkout(sweep):
    """`--yes` ends with ONE NOTED line in the runner's own log, naming what it
    removed, written as the runner's session through the RUNNER'S OWN
    checkout (S2) under S3 and S4: the commit on origin is that checkout's
    HEAD, W's own HEAD does not move, and that checkout fetched origin before
    it pushed (no `LANES_NO_FETCH`; rv1b's MUST 3)."""
    box = sweep.box
    box.use_net()
    runner = box.checkout(RUNNER)
    w_head = box.git("-C", str(box.w), "rev-parse", "HEAD").strip()
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED))}, rows
    noted = [line for line in box.origin_file(f"lanes/log/{RUNNER}.md").splitlines()
             if line.startswith("NOTED")]
    assert len(noted) == 1, noted
    assert f"lane {RUNNER}, session {UUID[RUNNER]}@" in noted[0], noted
    assert noted[0].endswith(
        "sweep-checkouts (Amendment 23 S6.2): removed 1 register checkout(s) under "
        f"brett-wip-lanes/ that held nothing unpublished: {CLOSED}; "
        "3 clone(s) beside W listed and left"), noted
    assert str(box.root) not in noted[0], "no host path is written into the log"
    assert box.git("-C", str(runner), "rev-parse", "HEAD").strip() == box.origin_head(), \
        "the NOTED commit is the runner's checkout's own"
    assert box.git("-C", str(box.w), "rev-parse", "HEAD").strip() == w_head, "W's HEAD did not move"
    lines = box.net_log.read_text(encoding="utf-8").splitlines()
    mine = [i for i, line in enumerate(lines) if f"-C {runner} " in line]
    fetches = [i for i in mine if lines[i].startswith("fetch ")]
    pushes = [i for i in mine if lines[i].startswith("push ")]
    assert fetches, lines
    assert pushes, lines
    assert fetches[0] < pushes[0], lines
    assert "NOTED in lane" in result.stdout, result.stdout


def test_nothing_removed_writes_nothing(sweep):
    """Nothing removed is nothing to record: with the CLOSED lane's checkout
    held, and the former name's kept (its lane is not CLOSED, D29), `--yes`
    removes nothing, writes no line and makes no commit."""
    box = sweep.box
    _commit_unpushed(box, box.checkout(CLOSED))
    head = box.origin_head()
    runner_head = box.git("-C", str(box.checkout(RUNNER)), "rev-parse", "HEAD").strip()
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not _tagged(rows, "removed"), rows
    assert box.origin_head() == head
    assert "NOTED" not in box.origin_file(f"lanes/log/{RUNNER}.md")
    assert box.git("-C", str(box.checkout(RUNNER)), "rev-parse", "HEAD").strip() == runner_head
    assert "NOTED in lane" not in result.stdout


def _wrapped(box: Sweep, name: str, verb: str, body: str) -> str:
    """A `LANES_EDIT` that runs `body` for `verb` and the real
    `lanes-edit.sh`, which `$REAL` names, for every other verb."""
    wrapper = box.fakebin / name
    wrapper.write_text(f'#!/usr/bin/env bash\nREAL={REPO / "lanes-edit.sh"}\n'
                       f'if [ "${{1-}}" = {verb} ]; then\n{body}fi\nexec bash "$REAL" "$@"\n',
                       encoding="utf-8")
    wrapper.chmod(0o755)
    return str(wrapper)


def _noted_on_origin(box: Sweep) -> list:
    return [line for line in box.origin_file(f"lanes/log/{RUNNER}.md").splitlines()
            if line.startswith("NOTED")]


def _remedies(stderr: str) -> list:
    """The commands a failed NOTED write hands out, each on a line of its own,
    in the order they are to be run."""
    return [line.split(":", 1)[1].strip() for line in stderr.splitlines()
            if line.startswith("lane-end:   ")]


def _by_hand(box: Sweep, command: str) -> subprocess.CompletedProcess:
    """Runs a command the sweep printed, as a person would, with this
    worktree's `lanes-edit.sh` first on PATH."""
    return subprocess.run(["bash", "-c", command], cwd=str(box.root), capture_output=True,
                          text=True, env=dict(box.env, PATH=f"{REPO}{os.pathsep}{box.env['PATH']}"),
                          timeout=180, check=False)


def test_noted_line_not_written_exits_1_with_the_command(sweep):
    """A NOTED line the writer refuses after the removals is not a quiet
    success: exit 1, and the exact command that writes it by hand, which
    then writes it."""
    box = sweep.box
    refusing = _wrapped(box, "lanes-edit-refusing-log", "log", (
        "  printf 'FAKE: the register refused this line\\n' >&2\n"
        "  exit 2\n"))
    result, rows = sweep("--yes", LANES_LANE=RUNNER, LANES_EDIT=refusing)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED))}, rows
    assert "the NOTED line recording this sweep was NOT written" in result.stderr, result.stderr
    assert "Nothing was lost" in result.stderr
    by_hand = result.stderr.split("Write the line by hand: ", 1)[1].strip()
    assert by_hand.startswith(f"LANES_LANE={RUNNER} LANES_SESSION={UUID[RUNNER]} lanes-edit.sh log NOTED "), by_hand
    assert not _noted_on_origin(box)
    done = _by_hand(box, by_hand)
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert "sweep-checkouts (Amendment 23 S6.2): removed 1" in box.origin_file(f"lanes/log/{RUNNER}.md")


def test_noted_line_unconfirmed_is_never_written_again(sweep):
    """A NOTED write that exits 3, `pushed, not confirmed`, MAY BE ON ORIGIN
    (rv4's SHOULD 2, P2). Here the line did land and the read-back is what
    failed. The sweep exits 1 without saying "NOT written", and hands out
    one command, the publish act, which sends the commit only where origin
    lacks it by content: run, it finds nothing to send, and origin still
    holds the line once."""
    box = sweep.box
    exit3 = _wrapped(box, "lanes-edit-unconfirmed-log", "log", (
        '  bash "$REAL" "$@"; rc=$?\n'
        "  if [ \"$rc\" = 0 ]; then printf 'FAKE: pushed, not confirmed\\n' >&2; exit 3; fi\n"
        '  exit "$rc"\n'))
    result, rows = sweep("--yes", LANES_LANE=RUNNER, LANES_EDIT=exit3)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED))}, rows
    assert len(_noted_on_origin(box)) == 1
    assert "was NOT written" not in result.stderr, result.stderr
    assert "Write the line by hand" not in result.stderr, result.stderr
    assert "may be on origin already" in result.stderr, result.stderr
    remedies = _remedies(result.stderr)
    assert len(remedies) == 1, remedies
    assert remedies[0].startswith(f"LANES_LANE={RUNNER} lanes-edit.sh commit "), remedies
    done = _by_hand(box, remedies[0])
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert len(_noted_on_origin(box)) == 1, "the publish act wrote no second line"


def test_noted_line_kept_unpublished_is_published_not_written_again(sweep):
    """A NOTED write that exits 6 with its commit KEPT in the checkout it was
    made in (rv4's SHOULD 2): every push is refused here with origin unmoved.
    The sweep exits 1 without saying "NOT written", and hands out the publish
    act alone (lane openRepoTools-3's SHOULD 373: the line is committed, so
    a line by hand would record the sweep twice). With pushes allowed again,
    the publish act sends the kept commit, and origin holds the line once."""
    box = sweep.box
    gate = box.root / "push.refused"
    gate.write_text("", encoding="utf-8")
    box.use_net(hook=f'case "$1" in push) if [ -e {gate} ]; then exit 1; fi ;; esac\nexit 0\n')
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED))}, rows
    assert not _noted_on_origin(box)
    assert "was NOT written" not in result.stderr, result.stderr
    assert "kept on HEAD" in result.stderr, result.stderr
    remedies = _remedies(result.stderr)
    assert len(remedies) == 1, remedies
    assert remedies[0].startswith(f"LANES_LANE={RUNNER} lanes-edit.sh commit "), remedies
    gate.rename(box.root / "push.allowed")
    done = _by_hand(box, remedies[0])
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert len(_noted_on_origin(box)) == 1, _noted_on_origin(box)


def _run_in_order(box: Sweep, remedies: list) -> None:
    """Runs the commands a failed NOTED write handed out, in order, as a
    person would; each must succeed."""
    for command in remedies:
        done = _by_hand(box, command)
        assert done.returncode == 0, (command, done.stdout, done.stderr)


def test_noted_line_whose_commit_fails_is_put_back_then_written_by_hand(sweep):
    """A NOTED WRITE WHOSE `git commit` FAILS (lane openRepoTools-3's SHOULD
    373): a `pre-commit` hook in the runner's checkout refuses it, so `log`
    exits 6 with the line staged there and nothing committed. The publish act
    refuses a staged entry it did not make, and so does the line by hand, so
    neither is handed out first: the sweep says to put the log back, then to
    write the line by hand. With the hook gone, the two, run in order, land
    the line once."""
    box = sweep.box
    runner = box.checkout(RUNNER)
    hook = runner / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho 'FAKE: a pre-commit hook refuses this commit' >&2\nexit 1\n",
                    encoding="utf-8")
    hook.chmod(0o755)
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED))}, rows
    assert "git commit failed" in result.stderr, result.stderr
    assert "was NOT committed" in result.stderr, result.stderr
    assert not _noted_on_origin(box)
    remedies = _remedies(result.stderr)
    assert len(remedies) == 2, remedies
    assert remedies[0] == f"git -C {runner} restore --staged --worktree -- lanes/log/{RUNNER}.md", remedies
    assert remedies[1].startswith(
        f"LANES_LANE={RUNNER} LANES_SESSION={UUID[RUNNER]} lanes-edit.sh log NOTED "), remedies
    hook.rename(hook.with_name("pre-commit.off"))
    _run_in_order(box, remedies)
    assert len(_noted_on_origin(box)) == 1, _noted_on_origin(box)


def test_noted_line_that_loses_six_push_races_is_archived_then_written_by_hand(sweep):
    """A NOTED WRITE THAT LOSES THE RACE SIX TIMES (lane openRepoTools-3's
    SHOULD 373): a peer's commit lands on origin before every push from the
    runner's checkout, so `log` exits 6 at its bound with the line committed
    there and origin moved past it. The publish act makes only a
    fast-forward, and the line by hand meets S3's refusal of a checkout
    holding a commit origin lacks, so neither is handed out first: the sweep
    says to archive the commit on origin (S6.3), take it off the checkout,
    then write the line by hand. Run in order, the archive holds the stranded
    commit and origin's log holds the line once."""
    box = sweep.box
    runner = box.checkout(RUNNER)
    gate = box.root / "push.races"
    gate.write_text("", encoding="utf-8")
    peer = _push_from_peer(box, "handoffs/README.md", "a peer lands first\n", "a-peer-lands-first")
    box.use_net(hook=(f'case "$1" in push) case " $* " in *" -C {runner} "*)\n'
                      f"  if [ -e {gate} ]; then {peer} || exit 1; fi ;;\n"
                      "esac ;; esac\nexit 0\n"))
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED))}, rows
    assert "after six attempts" in result.stderr, result.stderr
    assert not _noted_on_origin(box)
    remedies = _remedies(result.stderr)
    assert len(remedies) == 3, remedies
    archive, reset, by_hand = remedies
    assert archive.startswith(f"git -C {runner} push origin HEAD:refs/heads/archive/{RUNNER}-stranded-"), remedies
    assert reset == f"git -C {runner} reset --keep refs/remotes/origin/main", remedies
    assert by_hand.startswith(f"LANES_LANE={RUNNER} LANES_SESSION={UUID[RUNNER]} lanes-edit.sh log NOTED "), remedies
    stranded = box.git("-C", str(runner), "rev-parse", "HEAD").strip()
    gate.rename(box.root / "push.free")
    _run_in_order(box, remedies)
    ref = archive.split("HEAD:", 1)[1]
    assert box.git("--git-dir", str(box.origin), "rev-parse", ref).strip() == stranded, "the archive holds it"
    assert len(_noted_on_origin(box)) == 1, _noted_on_origin(box)


def test_a_store_kept_inside_a_clone_is_leaned_on(sweep):
    """D18: a repository LEANS ON A CLONE when its alternates file names an
    object directory anywhere AT OR UNDER that clone, not only the clone's own
    `.git/objects`: removing the clone removes that store too. Here a store
    kept inside the CLOSED lane's `.git` is borrowed by a repository beside W,
    and the CLOSED lane's checkout is held by it, in the dry run and under
    `--yes`, and that repository stays whole."""
    box = sweep.box
    c = box.checkout(CLOSED)
    store = c / ".git" / "kept-store"
    box.git("init", "-q", "--bare", str(store))
    borrower = box.w.parent / "borrower"
    box.git("init", "-q", "-b", "main", str(borrower))
    box.write(borrower, "f.txt", "kept\n")
    box.commit(borrower, "a commit whose objects go to the store", "f.txt")
    objects = borrower / ".git" / "objects"
    for entry in objects.iterdir():
        if entry.name not in ("info", "pack"):
            shutil.copytree(entry, store / "objects" / entry.name, dirs_exist_ok=True)
    (objects / "info" / "alternates").write_text(f"{store / 'objects'}\n", encoding="utf-8")
    for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
        result, rows = sweep(*args, **env)
        assert result.returncode in (0, 3), (result.stdout, result.stderr)
        assert rows[str(c)][0] == "hold", rows[str(c)]
        assert f"leaned on by {borrower} " in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()
    assert store.is_dir()
    box.git("-C", str(borrower), "fsck", "--connectivity-only")


GIT_FILES = [
    pytest.param(lambda c, sharer: f"gitdir: {c}/.git\n", id="absolute"),
    pytest.param(lambda c, sharer: f"gitdir: {c}/.git\r\n", id="CRLF, whose CR git strips"),
    pytest.param(lambda c, sharer: f"gitdir: {os.path.relpath(c / '.git', sharer)}\n",
                 id="relative to the directory it is in"),
]


@pytest.mark.parametrize("spelled", GIT_FILES)
def test_a_git_file_naming_a_clones_git_directory_holds_it(sweep, spelled):
    """A `.git` FILE IS READ AS AN ALTERNATES FILE IS (rv4's NIT 1, P3): a
    directory beside W whose `.git` file names the CLOSED lane's `.git` works
    in that clone's git directory, and removing the clone takes it away. The
    clone is held, by the dry run and by `--yes`, naming the directory. The
    file is read as git reads it, so a CRLF line works in that directory too
    (rv4-c3's NIT c3-3, P3), and so does a path relative to the directory
    the file is in (NIT c3-4, P4)."""
    box = sweep.box
    c = box.checkout(CLOSED)
    sharer = box.w.parent / "sharer"
    sharer.mkdir()
    (sharer / ".git").write_bytes(spelled(c, sharer).encode("utf-8"))
    assert box.git("-C", str(sharer), "rev-parse", "--absolute-git-dir").strip() == f"{c}/.git"
    for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
        result, rows = sweep(*args, **env)
        assert rows[str(c)][0] == "hold", rows[str(c)]
        assert result.returncode in (0, 3), (result.stdout, result.stderr)
        assert f"its git directory is named by the .git file of {sharer}" in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()


def test_a_directory_sharing_Ws_git_directory_is_kept_as_W(sweep):
    """W IS NEVER A CANDIDATE, by its git directory as well as by its path: a
    directory under `<W>-lanes/`, named for a CLOSED lane, whose own `.git`
    names W's as its common directory (a linked worktree's admin files copied
    by hand) IS W's repository, and is kept as W, by the dry run and `--yes`."""
    box = sweep.box
    d = box.checkout(CHAIN[0])
    (d / ".git").mkdir(parents=True)
    (d / ".git" / "commondir").write_text(f"{box.w / '.git'}\n", encoding="utf-8")
    (d / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    assert box.git("-C", str(d), "rev-parse", "--git-common-dir").strip() == str(box.w / ".git")
    w_before = box.w_state()
    for args, env in ((), {}), (("--yes",), {"LANES_LANE": RUNNER}):
        result, rows = sweep(*args, **env)
        assert result.returncode in (0, 3), (result.stdout, result.stderr)
        assert rows[str(d)] == ("keep", "W itself, the readers' copy"), rows[str(d)]
    assert d.is_dir()
    assert box.w_state() == w_before
