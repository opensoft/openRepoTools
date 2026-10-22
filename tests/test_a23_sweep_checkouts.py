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
import signal
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
    assert _tagged(rows, "remove") == {str(box.checkout(CLOSED)), str(box.checkout(OLD))}, rows
    assert rows[str(box.checkout(OLD))][1].startswith(f"a former name of lane {NEW}"), rows
    assert box.everything() == before, "a dry run changes nothing under <W>-lanes/ or beside W"
    assert box.origin_head() == head, "nothing reached origin"
    assert not list(box.lanes_root.glob("*/lanes/.lanes-edit.lock")), "a dry run takes no lock"
    assert "LANES_LANE=<your lane> lane-end --sweep-checkouts --yes" in result.stdout


def test_dry_run_with_nothing_to_remove_exits_0(sweep):
    """0 is nothing to remove: with the CLOSED lane's checkout and the former
    name's gone, every entry is kept."""
    box = sweep.box
    for lane in (CLOSED, OLD):
        box.checkout(lane).rename(box.root / f"aside-{lane}")
    result, rows = sweep()
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not _tagged(rows, "remove"), rows
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
    assert _tagged(rows, "remove") == {str(box.checkout(CLOSED)), str(box.checkout(OLD))}


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
    judged = _tagged(rows, "remove") | _tagged(rows, "hold")
    assert judged and all(Path(p).parent == box.lanes_root for p in judged), rows
    assert "listed and never removed by this build" in result.stdout


# ------------------------------------------------------- the act, and holds

def _assert_under(base: Path, paths) -> None:
    """Every path the run removed is under the test's own basetemp."""
    for path in paths:
        assert Path(os.path.realpath(path)).is_relative_to(base), path


def _no_aside(box: Sweep) -> None:
    assert not list(box.lanes_root.glob(".*.removing-*")), "no half-removed aside is left"


def test_closed_lane_checkout_removed_live_kept(sweep, tmp_path):
    """`--yes`, run by a lane, removes the CLOSED lane's checkout and the former
    name's beside its new one, and leaves every other entry — the LIVE lane's,
    the PAUSED one's, a non-clone, a link — and every clone beside W exactly
    as they were. Its own checkout moves only by the NOTED commit it pushed."""
    box = sweep.box
    before = box.everything()
    runner = str(box.checkout(RUNNER))
    gone = {str(box.checkout(CLOSED)), str(box.checkout(OLD))}
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == gone, rows
    _assert_under(Path(os.path.realpath(tmp_path)), gone)
    for path in gone:
        assert not os.path.lexists(path), path
    after = box.everything()
    assert {k: v for k, v in before.items() if k not in gone and k != runner} == \
        {k: v for k, v in after.items() if k != runner}, \
        "nothing but the two removed entries changed, under <W>-lanes/ or beside W"
    assert box.git("-C", runner, "rev-parse", "HEAD").strip() == box.origin_head(), \
        "the runner's checkout moved only to the NOTED commit it pushed"
    assert after[runner][1:] == before[runner][1:], "and holds nothing new"
    assert _tagged(rows, "beside") == {str(c) for c in box.profile_clones}
    _no_aside(box)
    assert not list(box.lanes_root.glob("*/lanes/.lanes-edit.lock")), "every lock it took is released"


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
    assert c.is_dir() and box.everything()[str(c)] == before, "the held checkout is as it was"
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
    listing finds repoS4-8's checkout beside its new name's; at its own fetch
    the new name's checkout goes, so the former name's checkout IS that
    lane's own again until its next write renames it (S1), and is kept."""
    box = sweep.box
    old, new = box.checkout(OLD), box.checkout(NEW)
    _, rows = sweep()
    assert rows[str(old)][0] == "remove", rows[str(old)]
    _hook_on_fetch_of(box, old, f"mv -- {new} {box.root / 'aside-new'}")
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert rows[str(old)][0] == "hold", rows[str(old)]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (f"it is no longer a former name of lane {NEW} beside that lane's own checkout"
            in rows[str(old)][1]), rows[str(old)]
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
    assert c.is_dir() and not (c / "lanes" / ".lanes-edit.lock").exists()


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
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED)), str(box.checkout(OLD))}, rows
    noted = [line for line in box.origin_file(f"lanes/log/{RUNNER}.md").splitlines()
             if line.startswith("NOTED")]
    assert len(noted) == 1, noted
    assert f"lane {RUNNER}, session {UUID[RUNNER]}@" in noted[0], noted
    assert noted[0].endswith(
        "sweep-checkouts (Amendment 23 S6.2): removed 2 register checkout(s) under "
        f"brett-wip-lanes/ that held nothing unpublished: {CLOSED} {OLD}; "
        "3 clone(s) beside W listed and left"), noted
    assert str(box.root) not in noted[0], "no host path is written into the log"
    assert box.git("-C", str(runner), "rev-parse", "HEAD").strip() == box.origin_head(), \
        "the NOTED commit is the runner's checkout's own"
    assert box.git("-C", str(box.w), "rev-parse", "HEAD").strip() == w_head, "W's HEAD did not move"
    lines = box.net_log.read_text(encoding="utf-8").splitlines()
    mine = [i for i, line in enumerate(lines) if f"-C {runner} " in line]
    fetches = [i for i in mine if lines[i].startswith("fetch ")]
    pushes = [i for i in mine if lines[i].startswith("push ")]
    assert fetches and pushes and fetches[0] < pushes[0], lines
    assert "NOTED in lane" in result.stdout, result.stdout


def test_nothing_removed_writes_nothing(sweep):
    """Nothing removed is nothing to record: with the CLOSED lane's checkout
    held and the former name's gone, `--yes` removes nothing, writes no line
    and makes no commit."""
    box = sweep.box
    box.checkout(OLD).rename(box.root / f"aside-{OLD}")
    _commit_unpushed(box, box.checkout(CLOSED))
    head = box.origin_head()
    runner_head = box.git("-C", str(box.checkout(RUNNER)), "rev-parse", "HEAD").strip()
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not _tagged(rows, "removed"), rows
    assert box.origin_head() == head and "NOTED" not in box.origin_file(f"lanes/log/{RUNNER}.md")
    assert box.git("-C", str(box.checkout(RUNNER)), "rev-parse", "HEAD").strip() == runner_head
    assert "NOTED in lane" not in result.stdout


def _wrapped_log(box: Sweep, name: str, log_body: str) -> str:
    """A `LANES_EDIT` that runs `log_body` for `log` and the real
    `lanes-edit.sh`, which `$REAL` names, for every other verb."""
    wrapper = box.fakebin / name
    wrapper.write_text(f'#!/usr/bin/env bash\nREAL={REPO / "lanes-edit.sh"}\n'
                       f'if [ "${{1-}}" = log ]; then\n{log_body}fi\nexec bash "$REAL" "$@"\n',
                       encoding="utf-8")
    wrapper.chmod(0o755)
    return str(wrapper)


def _noted_on_origin(box: Sweep) -> list:
    return [line for line in box.origin_file(f"lanes/log/{RUNNER}.md").splitlines()
            if line.startswith("NOTED")]


def _remedies(stderr: str) -> list:
    """The commands a failed NOTED write hands out on lines of their own."""
    return [line.split(":", 1)[1].strip() for line in stderr.splitlines()
            if line.startswith("lane-end:   LANES_LANE=")]


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
    refusing = _wrapped_log(box, "lanes-edit-refusing-log", (
        "  printf 'FAKE: the register refused this line\\n' >&2\n"
        "  exit 2\n"))
    result, rows = sweep("--yes", LANES_LANE=RUNNER, LANES_EDIT=refusing)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED)), str(box.checkout(OLD))}, rows
    assert "the NOTED line recording this sweep was NOT written" in result.stderr, result.stderr
    assert "Nothing was lost" in result.stderr
    by_hand = result.stderr.split("Write the line by hand: ", 1)[1].strip()
    assert by_hand.startswith(f"LANES_LANE={RUNNER} LANES_SESSION={UUID[RUNNER]} lanes-edit.sh log NOTED "), by_hand
    assert not _noted_on_origin(box)
    done = _by_hand(box, by_hand)
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert "sweep-checkouts (Amendment 23 S6.2): removed 2" in box.origin_file(f"lanes/log/{RUNNER}.md")


def test_noted_line_unconfirmed_is_never_written_again(sweep):
    """A NOTED write that exits 3, `pushed, not confirmed`, MAY BE ON ORIGIN
    (rv4's SHOULD 2, P2). Here the line did land and the read-back is what
    failed. The sweep exits 1 without saying "NOT written", and hands out
    one command, the publish act, which sends the commit only where origin
    lacks it by content: run, it finds nothing to send, and origin still
    holds the line once."""
    box = sweep.box
    exit3 = _wrapped_log(box, "lanes-edit-unconfirmed-log", (
        '  bash "$REAL" "$@"; rc=$?\n'
        "  if [ \"$rc\" = 0 ]; then printf 'FAKE: pushed, not confirmed\\n' >&2; exit 3; fi\n"
        '  exit "$rc"\n'))
    result, rows = sweep("--yes", LANES_LANE=RUNNER, LANES_EDIT=exit3)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED)), str(box.checkout(OLD))}, rows
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
    act first, and the by-hand line only for a publish act that finds nothing
    to send. With pushes allowed again, the publish act sends the kept commit,
    and origin holds the line once."""
    box = sweep.box
    gate = box.root / "push.refused"
    gate.write_text("", encoding="utf-8")
    box.use_net(hook=f'case "$1" in push) if [ -e {gate} ]; then exit 1; fi ;; esac\nexit 0\n')
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == {str(box.checkout(CLOSED)), str(box.checkout(OLD))}, rows
    assert not _noted_on_origin(box)
    assert "was NOT written" not in result.stderr, result.stderr
    assert "kept on HEAD" in result.stderr, result.stderr
    remedies = _remedies(result.stderr)
    assert len(remedies) == 2, remedies
    publish, by_hand = remedies
    assert publish.startswith(f"LANES_LANE={RUNNER} lanes-edit.sh commit "), remedies
    assert by_hand.startswith(f"LANES_LANE={RUNNER} LANES_SESSION={UUID[RUNNER]} lanes-edit.sh log NOTED "), remedies
    gate.rename(box.root / "push.allowed")
    done = _by_hand(box, publish)
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert len(_noted_on_origin(box)) == 1, _noted_on_origin(box)


def test_yes_without_a_session_uuid_is_refused(sweep):
    """The NOTED line's session field is a transcript uuid and only that
    (Amendment 7(b)): a `LANES_SESSION` that is none is refused before
    anything is removed, not met by the line after the removals."""
    box = sweep.box
    before, head = box.everything(), box.origin_head()
    result, _ = sweep("--yes", LANES_LANE=RUNNER, LANES_SESSION="unknown")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "has no transcript uuid for the session field" in result.stderr, result.stderr
    assert "Nothing was removed" in result.stderr
    assert box.everything() == before and box.origin_head() == head


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
    assert c.is_dir() and store.is_dir()
    box.git("-C", str(borrower), "fsck", "--connectivity-only")


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
    assert d.is_dir() and box.w_state() == w_before
