# SPDX-License-Identifier: Apache-2.0
"""Amendment 23 S2 and S5: which checkout a write goes through.

S2's order: an explicit `LANES_REPO` keeps its meaning (the test seam and an
operator's override), and one that names W by real path is refused (S5);
otherwise the write goes through the checkout of the lane it is attributed to;
and with no lane there is no write — never a fallback to W. `LANES_DIR` and
`LANES_FILE` locate files inside the checkout and never choose it. Reads keep
W, through workspace.yaml.

The sandbox is the real `lanes-edit.sh`: a bare origin, W cloned from it, and
`workspace.yaml` naming W. Nothing reaches a real remote, `gh` or `tmux`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from a23_box import REGISTER, RegisterBox, register_text
from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

LANE = "repoA23-1"
DORMANT = "repoA23-9"
TARGET = "repoA23-4"
UUID = "a23a0001-a2a2-4000-8000-a23a0001a2a2"
TARGET_UUID = "a23a0004-a2a2-4000-8000-a23a0004a2a2"
ASKER_UUID = "a23a0005-a2a2-4000-8000-a23a0005a2a2"


def _row(lane: str, uuid: str = UUID, state: str = "LIVE · seeded") -> str:
    return (f"| `{lane}` | harness `{uuid}` | Eagle / test / tester | 2026-10-17T00:00Z "
            f"| — | handoffs/repoA23/{lane}.md | {state} |")


class Box(RegisterBox):
    """Four rows; the TARGET of a request bound in another container."""

    def __init__(self, root: Path, **kw) -> None:
        root = Path(os.path.realpath(root))
        rows = [_row(LANE), _row("repoA23-2"),
                _row(DORMANT, uuid="a23a0009-a2a2-4000-8000-a23a0009a2a2"),
                _row(TARGET, uuid=TARGET_UUID)]
        files = {
            REGISTER: register_text(rows),
            # THE TARGET OF A REQUEST IS BOUND ELSEWHERE: its last lane-kind line
            # is a STARTED from another container on this host (Amendment 18).
            f"lanes/log/{TARGET}.md":
                f"# lane {TARGET} — object log (lane-collision-protocol Amendment 7)\n"
                f"STARTED — lane {TARGET}, session {TARGET_UUID}@Eagle, 2026-10-17T09:00:00Z, "
                f"lane:{TARGET} → home opensoft/repoA23; estate repoA23; dir {root}/lanedir; "
                f"profile team-05a; window othersess:4 @62; host hosta; os linux; container bench-b\n",
            f"lanes/log/{LANE}.md":
                f"# lane {LANE} — object log (lane-collision-protocol Amendment 7)\n",
            "handoffs/README.md": "# handoffs\n",
        }
        super().__init__(root, files, **kw)


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def assert_nothing_written(box: Box, head: str, w_before) -> None:
    assert box.origin_head() == head, "nothing reached origin"
    assert box.w_state() == w_before, "W is as it was"


# ------------------------------------------------------- (3) no lane, no write

@pytest.mark.parametrize("args", [
    ("commit", "a hand edit"),
    ("append-line", "a line that names nobody at all"),
    ("add-row", "| no backticked lane | x | Eagle / t / u | 2026-10-17T00:00Z | — | h | LIVE |"),
], ids=["commit", "append-line", "add-row"])
def test_no_lane_no_write_exit_2(box: Box, args):
    head, w_before = box.origin_head(), box.w_state()
    result = box.helper(*args)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "no lane, no write" in result.stderr, result.stderr
    assert "LANES_LANE=<lane>" in result.stderr, "the refusal names the form that writes"
    assert not box.lanes_root.exists(), "no checkout was made for a write with no lane"
    assert_nothing_written(box, head, w_before)


# ------------------------------------------------------- (1) explicit LANES_REPO

@pytest.mark.parametrize("how", ["direct", "symlink"])
def test_LANES_REPO_naming_W_is_refused(box: Box, how: str):
    named = box.w
    if how == "symlink":
        named = box.root / "a-link-to-w"
        named.symlink_to(box.w)
    head, w_before = box.origin_head(), box.w_state()
    result = box.helper("set-row-state", LANE, "LIVE · into W", LANES_REPO=str(named))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "readers' copy" in result.stderr and "Amendment 23 S5" in result.stderr, result.stderr
    assert f"LANES_LANE={LANE}" in result.stderr, "it names the form that writes"
    assert f"{box.lanes_root}/{LANE}/" in result.stderr, "it names the lane's own checkout"
    if how == "symlink":
        assert "through" in result.stderr
    assert_nothing_written(box, head, w_before)
    assert not box.lanes_root.exists()


def test_explicit_LANES_REPO_is_honoured_and_derives_dir_and_file(box: Box):
    other = box.clone(box.root / "elsewhere" / "register")
    w_before = box.w_state()
    result = box.helper("set-row-state", LANE, "LIVE · in the override", LANES_REPO=str(other))
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert " · in the override |" in (other / REGISTER).read_text(encoding="utf-8"), \
        "the edit landed in the checkout LANES_REPO names, where git committed it"
    assert " · in the override |" in box.origin_file(REGISTER)
    assert box.git("-C", str(other), "status", "--porcelain") == ""
    assert box.w_state() == w_before, "LANES_DIR and LANES_FILE no longer default to W"
    assert not box.lanes_root.exists(), "an explicit LANES_REPO makes no lane checkout"
    assert "WARNING" not in result.stderr


def test_per_profile_clone_warns_with_S1_path(box: Box):
    profile = box.clone(box.home / "projects" / "brett-wip-team02e-lane2")
    result = box.helper("set-row-state", LANE, "LIVE · through a profile clone",
                        LANES_REPO=str(profile))
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "per-profile clone" in result.stderr, result.stderr
    assert f"{box.lanes_root}/{LANE}/" in result.stderr, "the warning names S1's path"
    assert " · through a profile clone |" in box.origin_file(REGISTER), "and it is honoured"


@pytest.mark.parametrize("how", ["default", "explicit"])
def test_LANES_DIR_outside_checkout_is_refused(box: Box, how: str):
    extra = {"LANES_DIR": str(box.w / "lanes")}
    if how == "explicit":
        extra["LANES_REPO"] = str(box.clone(box.root / "elsewhere" / "register"))
    head, w_before = box.origin_head(), box.w_state()
    result = box.helper("set-row-state", LANE, "LIVE · never written", **extra)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "outside the checkout" in result.stderr, result.stderr
    assert_nothing_written(box, head, w_before)
    assert not box.checkout(LANE).exists(), "nothing was cloned for a refused write"


@pytest.mark.parametrize("verb", ["set-row-state", "add-row", "append-line"])
def test_a_writer_missing_its_lane_keeps_its_own_usage_refusal(box: Box, verb: str):
    """A WRITER WITH NO ARGUMENTS IS A USAGE ERROR, NOT A WRITE WITH NO LANE:
    routing steps aside, and the arm refuses with its own words and code before
    reading anything, as it always has."""
    head, w_before = box.origin_head(), box.w_state()
    result = box.helper(verb)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert f"usage: {verb}" in result.stderr, result.stderr
    assert "no lane, no write" not in result.stderr, result.stderr
    assert not box.lanes_root.exists()
    assert_nothing_written(box, head, w_before)


@pytest.mark.parametrize("verb", ["archive-rows", "migrate-state-cells"])
def test_dry_runs_make_no_checkout(box: Box, verb: str):
    """Without `--yes` these two print a plan, take no lock and write nothing,
    so they are reads, and a lane named beside them makes no checkout."""
    head, w_before = box.origin_head(), box.w_state()
    result = box.helper(verb, LANES_LANE=LANE)
    assert not box.lanes_root.exists(), (result.stdout, result.stderr)
    assert_nothing_written(box, head, w_before)


# ------------------------------------------------------- the re-run

def test_inherited_markers_are_dropped(box: Box):
    """A PROCESS A ROUTED WRITE STARTED is not the re-run itself: its
    `LANES__PID` names another process, so both markers, and the three paths
    only the re-run exports beside them, are dropped, and its own write goes
    through its own lane's checkout (S2), not the one it inherited."""
    made = box.helper("set-row-state", LANE, "LIVE · made the first checkout")
    assert made.returncode == 0, (made.stdout, made.stderr)
    c = box.checkout(LANE)
    inherited = {"LANES__CHECKOUT_LANE": LANE, "LANES__PID": "1", "LANES_REPO": str(c),
                 "LANES_DIR": str(c / "lanes"), "LANES_FILE": str(c / REGISTER)}
    result = box.helper("set-row-state", "repoA23-2", "LIVE · through its own checkout", **inherited)
    assert result.returncode == 0, (result.stdout, result.stderr)
    other = box.checkout("repoA23-2")
    assert (other / ".git").is_dir(), "the write resolved its own lane's checkout"
    assert "through its own checkout" in box.git("-C", str(other), "log", "-1", "--format=%s")
    assert "through its own checkout" not in box.git("-C", str(c), "log", "-1", "--format=%s")


def test_the_re_run_leaves_no_temporary_file_behind(box: Box):
    """`exec` runs no EXIT trap, so what the first run made before it — its
    event cache in TMPDIR — is removed first, by `cleanup_for_exec`."""
    tmp = box.root / "tmp-of-one-write"
    tmp.mkdir()
    result = box.helper("set-row-state", LANE, "LIVE · one write", TMPDIR=str(tmp))
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (box.checkout(LANE) / ".git").is_dir(), "the write was routed, so the file ran twice"
    assert sorted(p.name for p in tmp.glob("lanes-edit-*")) == [], "neither run left its cache"


# ------------------------------------------------------- (2) the attributed lane

def test_sweep_writes_through_runner_lane(box: Box):
    result = box.helper("retire-rows", DORMANT, LANES_LANE=LANE, LANES_SESSION=UUID)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (box.checkout(LANE) / ".git").is_dir(), "the sweep went through the runner's checkout"
    assert not box.checkout(DORMANT).exists(), "and never through the swept lane's"
    register = box.origin_file(REGISTER)
    assert any(line.startswith(f"| `{DORMANT}` |") and "RETIRED" in line
               for line in register.splitlines()), register
    assert f"RETIRED — lane {DORMANT}, session {UUID}@Eagle" in box.origin_file(f"lanes/log/{DORMANT}.md")


def test_request_handoff_writes_through_target_lane(box: Box):
    result = box.helper("request-handoff", TARGET, "--no-wait", LANES_SESSION=ASKER_UUID)
    # An empty wait refuses (2) — the request is written FIRST, and that is
    # the write under test here.
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert (box.checkout(TARGET) / ".git").is_dir(), "the request went through the TARGET lane's checkout"
    assert sorted(p.name for p in box.lanes_root.iterdir()) == [TARGET]
    log = box.origin_file(f"lanes/log/{TARGET}.md")
    assert f"HANDOFF-REQUESTED — lane {TARGET}, session {ASKER_UUID}@Eagle" in log, log


def test_request_handoff_dry_run_is_a_read(box: Box):
    head = box.origin_head()
    result = box.helper("request-handoff", TARGET, "--dry-run", LANES_SESSION=ASKER_UUID)
    assert "PLAN:" in result.stderr, (result.stdout, result.stderr)
    assert not box.lanes_root.exists(), "a dry run writes nothing, so it makes no checkout"
    assert box.origin_head() == head


def test_reads_still_resolve_W(box: Box):
    assert box.helper("set-row-state", LANE, "LIVE · written through C").returncode == 0
    root = box.helper("workspace-root")
    assert root.returncode == 0 and root.stdout.strip() == str(box.w)
    local = box.helper("register-row-local", LANE)
    assert local.returncode == 0, (local.stdout, local.stderr)
    assert "LIVE · seeded" in local.stdout, "a read of the working tree reads W's, which no write touched"
    assert " · written through C |" in (box.checkout(LANE) / REGISTER).read_text(encoding="utf-8")
    before = sorted(p.name for p in box.lanes_root.iterdir())
    for read in (("verify-row", "repoA23-2"), ("register-row-local", "repoA23-2"),
                 ("canon-lane", "REPOA23-2"), ("lane-checkout", "repoA23-2")):
        box.helper(*read)
    assert sorted(p.name for p in box.lanes_root.iterdir()) == before, "a read makes no checkout"


def test_guard_no_lane_exemption_still_first(box: Box):
    (box.home / ".agents" / "workspace.yaml").unlink()
    for extra in ({}, {"LANES_REPO": str(box.w)}):
        result = subprocess.run(["bash", str(REPO / "lanes-edit.sh"), "guard"],
                                env=dict(box.env, CLAUDE_NO_LANE="1", **extra),
                                input="{}", capture_output=True, text=True, timeout=60, check=False)
        assert result.returncode == 0, (extra, result.stdout, result.stderr)
        assert result.stdout == "" and result.stderr == ""
    assert not box.lanes_root.exists()


# ------------------------------------------------------- fix round 1 (#282's review)

def _git_wrapper(box: Box, name: str, body: str) -> Path:
    """A `LANES_GIT` — the binary the helper's NETWORK calls use, and only
    those — that runs `body` first and then the real git."""
    real = shutil.which("git")
    path = box.root / name
    path.write_text(f"#!/usr/bin/env bash\n{body}\nexec '{real}' \"$@\"\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_without_the_opt_in_a_write_goes_through_W_as_before(box: Box):
    """MUST 2: routing is opt-in until slice 1b. With no `LANES_ROUTE_WRITES`,
    the default resolution writes, commits and pushes in W, and no lane
    checkout or workstation lock is made — main's behaviour, byte for byte."""
    head = box.w_state()[0]
    result = box.helper("set-row-state", LANE, "LIVE · written in W", LANES_ROUTE_WRITES="")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not box.lanes_root.exists(), "no lane checkout, no <W>-lanes/ at all"
    assert box.w_state()[0] != head, "the commit is W's"
    assert box.w_state()[1] == ""
    assert " · written in W |" in box.origin_file(REGISTER)
    assert box.git("-C", str(box.w), "rev-parse", "HEAD").strip() == box.origin_head()


def test_a_routed_write_brings_W_origin_main_along(box: Box):
    """MUST 1: a routed write pushes from the lane's checkout, and the prompt
    guard reads W's `origin/main` OFFLINE. So W is fetched once the push has
    landed — W's ref, and an unfetched read of W, see the write — and W's
    branch and working tree stay as they were (S5: a fetch, nothing else)."""
    w_before = box.w_state()
    result = box.helper("set-row-state", LANE, "LIVE · what the guard reads")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert box.w_origin_main() == box.origin_head(), "W's origin/main followed the push"
    read = box.helper("register-row", LANE, LANES_NO_FETCH="1")
    assert read.returncode == 0, (read.stdout, read.stderr)
    assert " · what the guard reads |" in read.stdout, "an offline read of W sees the write"
    assert box.w_state() == w_before, "W itself was only fetched"


def test_a_follow_fetch_that_fails_is_said_and_fails_nothing(box: Box):
    """The write has landed by then: a W that cannot be fetched is a note."""
    assert box.helper("set-row-state", LANE, "LIVE · made the checkout").returncode == 0
    wrapper = _git_wrapper(box, "w-fetch-fails",
                           f'case " $* " in *" {box.w} fetch "*) exit 1 ;; esac')
    result = box.helper("set-row-state", LANE, "LIVE · W could not follow", LANES_GIT=str(wrapper))
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "did not learn it" in result.stderr and "refresh-workspace" in result.stderr
    assert " · W could not follow |" in box.origin_file(REGISTER)
    assert box.w_origin_main() != box.origin_head()


@pytest.mark.parametrize("how", ["both", "root-only", "same-checkout"])
def test_a_W_that_is_a_lane_checkout_refuses_naming_LANES_WORKSPACE_ROOT(box: Box, how: str):
    """MUST 3: Eagle's lane windows export `LANES_REPO` and
    `LANES_WORKSPACE_ROOT` at the lane's own checkout. That is not W: every
    write refuses, naming the variable to unset, and nothing is cloned inside
    it (`<lane>-lanes/<lane>`) and no lock is made beside it."""
    if how == "same-checkout":
        c = box.clone(box.root / "elsewhere" / "openRepoTools-3")
    else:
        box.lanes_root.mkdir(parents=True)
        c = box.clone(box.checkout(LANE))
    extra = {"LANES_WORKSPACE_ROOT": str(c)}
    if how != "root-only":
        extra["LANES_REPO"] = str(c)
    head = box.origin_head()
    result = box.helper("set-row-state", LANE, "LIVE · never written", **extra)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "Unset LANES_WORKSPACE_ROOT" in result.stderr, result.stderr
    assert "readers' copy" in result.stderr
    assert not Path(f"{c}-lanes").exists(), "nothing cloned or locked beside the lane checkout"
    assert box.origin_head() == head
    checkout = box.helper("lane-checkout", LANE, "--create", LANES_ROUTE_WRITES="", **extra)
    assert checkout.returncode == 2, (checkout.stdout, checkout.stderr)
    assert not Path(f"{c}-lanes").exists(), "lane-checkout refuses with or without the opt-in"


def test_S5_compares_the_repository_not_the_spelling(box: Box):
    """SHOULD 3: `LANES_REPO` at W's own `lanes/` directory is W — its edit
    would land in W's tree — so S5 refuses it before anything is written."""
    head, w_before = box.origin_head(), box.w_state()
    result = box.helper("set-row-state", LANE, "LIVE · never written",
                        LANES_REPO=str(box.w / "lanes"), LANES_FILE=str(box.w / REGISTER))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "readers' copy" in result.stderr and "Amendment 23 S5" in result.stderr, result.stderr
    assert_nothing_written(box, head, w_before)


def test_a_hand_edit_in_W_refuses_a_routed_write(box: Box):
    """SHOULD 4: W's register carries a hand edit. A routed `commit` — the
    verb that publishes hand edits, and since N2 the only one refused —
    refuses, naming the edit and the lane's checkout, where before it said
    "nothing staged" with exit 0 and left the edit in W."""
    register = box.w / REGISTER
    edited = register.read_text(encoding="utf-8").replace("LIVE · seeded |", "LIVE · by hand |", 1)
    register.write_text(edited, encoding="utf-8")
    head = box.origin_head()
    result = box.helper("commit", "a hand edit", LANES_LANE=LANE)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "uncommitted edit to its register" in result.stderr, result.stderr
    assert f"{box.checkout(LANE)}/lanes/LANES.md" in result.stderr, "it names where the edit belongs"
    assert register.read_text(encoding="utf-8") == edited, "the edit is still in W, untouched"
    assert box.origin_head() == head
    assert not box.checkout(LANE).exists()


def _row_published_not_in_W(box: Box, lane: str) -> None:
    """A row a peer published, which W has fetched and not fast-forwarded. It
    goes at the TOP of the table, clear of the line an append adds at the
    foot, so a checkout that predates it rebases over it cleanly."""
    head, sep, rest = box.origin_file(REGISTER).partition("|---|---|---|---|---|---|---|\n")
    box.peer_pushes(REGISTER, head + sep + _row(lane) + "\n" + rest)
    box.git("-C", str(box.w), "fetch", "-q", "origin", "main")
    assert f"`{lane}`" not in (box.w / REGISTER).read_text(encoding="utf-8")


@pytest.mark.parametrize("checkout_first", [False, True], ids=["fresh", "stale-checkout"])
def test_append_line_attribution_reads_the_published_register(box: Box, checkout_first: bool):
    """SHOULD 1: a LANDING line with no `LANES_LANE` is attributed from the
    published register, not W's working tree, and its commit carries that
    lane even where the lane's own checkout predates the row."""
    lane = "repoA23-7"
    if checkout_first:
        made = box.helper("lane-checkout", lane, "--create")
        assert made.returncode == 0, (made.stdout, made.stderr)
    _row_published_not_in_W(box, lane)
    result = box.helper("append-line", f"LANDING — lane {lane}, the published row decides")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (box.checkout(lane) / ".git").is_dir(), "it went through that lane's checkout"
    subject = box.git("--git-dir", str(box.origin), "log", "-1", "--format=%s", "main")
    assert subject.startswith(f"LANES({lane}@Eagle): append line"), subject


def test_request_handoff_why_after_the_separator_is_no_dry_run(box: Box):
    """NIT 1: after `--` every word is the `--force` why, so `--dry-run` there
    is text, the arm writes, and the write goes through the target's checkout."""
    result = box.helper("request-handoff", TARGET, "--force", "--no-wait", "--", "--dry-run",
                        LANES_SESSION=ASKER_UUID)
    assert (box.checkout(TARGET) / ".git").is_dir(), (result.stdout, result.stderr)
    assert not (box.w / "lanes" / ".lanes-edit.lock").exists()
    assert box.w_state()[1] == "", "nothing was written in W"


def test_no_git_makes_no_clone(box: Box):
    """NIT 8: `LANES_NO_GIT=1` is no commit and no push, so it is no clone."""
    result = box.helper("set-row-state", LANE, "LIVE · no git", LANES_NO_GIT="1")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "LANES_NO_GIT=1" in result.stderr and "lane-checkout" in result.stderr
    assert not box.checkout(LANE).exists()


def test_an_explicit_LANES_REPO_still_needs_a_lane(box: Box):
    """NIT 9: `LANES_REPO` chooses a checkout, never the lane a commit is for."""
    other = box.clone(box.root / "elsewhere" / "register")
    head = box.origin_head()
    result = box.helper("commit", "a hand edit", LANES_REPO=str(other))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "no lane, no write" in result.stderr and "LANES_LANE=<lane>" in result.stderr
    assert box.origin_head() == head


def test_S5_refuses_a_checkout_whose_git_directory_is_W(box: Box):
    """SHOULD 3, the second clause: a checkout whose `.git` names W's — a
    linked worktree of W, or a gitfile view like the shell suite's — commits
    into W's own refs although its top level is not W, so S5 refuses it."""
    view = box.root / "a-view-of-W"
    view.mkdir()
    (view / ".git").write_text(f"gitdir: {box.w / '.git'}\n", encoding="utf-8")
    shutil.copytree(box.w / "lanes", view / "lanes")
    head, w_before = box.origin_head(), box.w_state()
    result = box.helper("set-row-state", LANE, "LIVE · never written", LANES_REPO=str(view))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "readers' copy" in result.stderr and "Amendment 23 S5" in result.stderr, result.stderr
    assert_nothing_written(box, head, w_before)


# ------------------------------------------------------- fix round 2 (#282's re-review)

def test_a_hand_edit_in_W_warns_every_other_routed_write_and_stops_none(box: Box):
    """N2: one stray edit in W — a person's, or an older helper's write in
    progress there during the rollout — stopped every lane's routed writes, a
    launch's session-id stamp among them. Only `commit` refuses now (above).
    Another lane's write says the same thing as a WARNING, goes through its
    own checkout and lands, and the edit stays in W, untouched and captured
    by nothing."""
    register = box.w / REGISTER
    lines = register.read_text(encoding="utf-8").splitlines(keepends=True)
    edited = "".join(l.replace("LIVE · seeded |", "LIVE · by hand |") if l.startswith("| `repoA23-2` |")
                     else l for l in lines)
    register.write_text(edited, encoding="utf-8")
    w_head = box.w_state()[0]
    result = box.helper("set-row-state", LANE, "LIVE · past a stray edit in W")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "WARNING" in result.stderr and "uncommitted edit to its register" in result.stderr, result.stderr
    assert f"{box.checkout(LANE)}/lanes/LANES.md" in result.stderr, "it names where the edit belongs"
    published = box.origin_register()
    assert " · past a stray edit in W |" in published, "the write landed"
    assert "by hand" not in published, "and the edit in W was captured by nothing"
    assert register.read_text(encoding="utf-8") == edited, "the edit is still in W, untouched"
    assert box.w_state()[0] == w_head


def test_the_hand_edit_check_takes_no_lock_in_W(box: Box):
    """N3: the check's `git status` in W ran with git's optional locks, so on
    a stat-dirty index it rewrote W's index under W's `index.lock` — a write
    in W, which S5 forbids, and one that can race an older helper's `git add`
    there. W's index file is left as it was: the same inode, the same time."""
    register = box.w / REGISTER
    then = time.time() - 100
    os.utime(register, (then, then))     # its bytes as committed; its stat not the index's
    index = box.w / ".git" / "index"
    before = os.stat(index)
    result = box.helper("set-row-state", LANE, "LIVE · W's index untouched")
    assert result.returncode == 0, (result.stdout, result.stderr)
    after = os.stat(index)
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns), \
        "nothing rewrote W's index"


def test_both_variables_naming_W_itself_refuse_and_say_it_is_W(box: Box):
    """N4: `LANES_WORKSPACE_ROOT` and `LANES_REPO` both at the `path:`
    workspace.yaml names is W, not a lane checkout. It is still refused (2) —
    under the opt-in no write goes through W (S5) — and the refusal says that,
    where it called W "a lane checkout"."""
    head, w_before = box.origin_head(), box.w_state()
    result = box.helper("set-row-state", LANE, "LIVE · never written",
                        LANES_WORKSPACE_ROOT=str(box.w), LANES_REPO=str(box.w))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert f"both name {box.w}, which is W itself" in result.stderr, result.stderr
    assert "Amendment 23 S5" in result.stderr and "Unset LANES_REPO" in result.stderr
    assert "it is a lane checkout" not in result.stderr, result.stderr
    assert_nothing_written(box, head, w_before)
    assert not box.lanes_root.exists()


def test_a_write_that_needs_a_row_clones_nothing_for_a_lane_with_none(box: Box):
    """N5: `set-row-state` for a lane with no row cloned that lane's checkout
    — half a gigabyte on Eagle — and then refused, "expected exactly 1 row",
    leaving the clone. It refuses first now (2): no row on origin, fetched into
    W to make sure, and nothing cloned."""
    head, w_before = box.origin_head(), box.w_state()
    result = box.helper("set-row-state", "repoA23-99", "LIVE · never written")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "lane repoA23-99 has no row in the register on origin/main" in result.stderr, result.stderr
    assert "expected exactly 1 row" not in result.stderr
    assert not box.lanes_root.exists(), "nothing was cloned for a lane with no row"
    assert_nothing_written(box, head, w_before)


@pytest.mark.parametrize("no_fetch", [False, True], ids=["fetched", "no-fetch"])
def test_a_row_W_has_not_fetched_is_no_reason_to_refuse(box: Box, no_fetch: bool):
    """N5's gate asks W's `origin/main` again after fetching it, so a row
    another checkout published, which W has not fetched yet, is never refused.
    Where that fetch does not run (`LANES_NO_FETCH=1`), a miss is no answer:
    the write goes on, as before, and its arm decides."""
    lane = "repoA23-7"
    head, sep, rest = box.origin_file(REGISTER).partition("|---|---|---|---|---|---|---|\n")
    box.peer_pushes(REGISTER, head + sep + _row(lane) + "\n" + rest)
    assert f"`{lane}`" not in box.git("-C", str(box.w), "show", f"refs/remotes/origin/main:{REGISTER}")
    extra = {"LANES_NO_FETCH": "1"} if no_fetch else {}
    result = box.helper("set-row-state", lane, "LIVE · a row W had not fetched", **extra)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "has no row in the register" not in result.stderr, result.stderr
    assert (box.checkout(lane) / ".git").is_dir()
    assert " · a row W had not fetched |" in box.origin_register()
