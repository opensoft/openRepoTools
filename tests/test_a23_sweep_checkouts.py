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
    assert _tagged(rows, "remove") == {str(box.checkout(CLOSED)), str(box.checkout(OLD))}, rows
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
    the PAUSED one's, its own, a non-clone, a link — and every clone beside W
    exactly as they were."""
    box = sweep.box
    before = box.everything()
    gone = {str(box.checkout(CLOSED)), str(box.checkout(OLD))}
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert _tagged(rows, "removed") == gone, rows
    _assert_under(Path(os.path.realpath(tmp_path)), gone)
    for path in gone:
        assert not os.path.lexists(path), path
    after = box.everything()
    assert {k: v for k, v in before.items() if k not in gone} == after, \
        "nothing but the two removed entries changed, under <W>-lanes/ or beside W"
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


def _hook_on_fetch_of(box: Sweep, target: Path, body: str) -> None:
    """A `LANES_GIT` hook that runs `body` when the sweep fetches `target`."""
    box.use_net(hook=(
        f'case " $* " in *" -C {target} fetch "*) {body} ;; esac\n'
        "exit 0\n"))


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
    resumed = (f"RESUMED — lane {CLOSED}, session {UUID[CLOSED]}@Eagle, "
               f"2026-10-21T09:00:00Z, lane:{CLOSED}\n")
    peer = box.seed
    _hook_on_fetch_of(box, c, (
        f"git -C {peer} pull -q --ff-only origin main && "
        f"printf '%s' '{resumed}' >> {peer}/lanes/log/{CLOSED}.md && "
        f"git -C {peer} commit -q -am resumed && git -C {peer} push -q origin main"))
    result, rows = sweep("--yes", LANES_LANE=RUNNER)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert rows[str(c)][0] == "hold", rows[str(c)]
    assert f"lane {CLOSED} is IDLE now, not CLOSED" in rows[str(c)][1], rows[str(c)]
    assert c.is_dir()


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
