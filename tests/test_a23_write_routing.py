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
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

LANE = "repoA23-1"
DORMANT = "repoA23-9"
TARGET = "repoA23-4"
REGISTER = "lanes/LANES.md"
UUID = "a23a0001-a2a2-4000-8000-a23a0001a2a2"
TARGET_UUID = "a23a0004-a2a2-4000-8000-a23a0004a2a2"
ASKER_UUID = "a23a0005-a2a2-4000-8000-a23a0005a2a2"

SCRUBBED_PREFIXES = ("LANES_", "LANE_START_", "CLAUDE_", "OPENREPOTOOLS_",
                     "FAKE_", "GIT_", "TMUX")
SCRUBBED = {"AGENT_PROTOCOL_ROOT", "PROJECTS_ROOT", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME"}

REFUSE = """#!/usr/bin/env bash
printf 'FAKE %s REFUSED: %s -- this suite reaches no real surface\\n' "${0##*/}" "$*" >&2
exit 90
"""


def _row(lane: str, uuid: str = UUID, state: str = "LIVE · seeded") -> str:
    return (f"| `{lane}` | harness `{uuid}` | Eagle / test / tester | 2026-10-17T00:00Z "
            f"| — | handoffs/repoA23/{lane}.md | {state} |")


class Box:
    """A bare origin, W cloned from it, and the workspace.yaml naming W."""

    def __init__(self, root: Path) -> None:
        root = Path(os.path.realpath(root))
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.home = root / "home"
        self.origin = root / "origin.git"
        self.w = self.home / "projects" / "brett-wip"
        self.lanes_root = self.home / "projects" / "brett-wip-lanes"
        self.fakebin = root / "fakebin"
        for d in (self.home / ".agents", self.home / "projects", root / "tmp", self.fakebin):
            d.mkdir(parents=True, exist_ok=True)
        for name in ("gh", "tmux"):
            (self.fakebin / name).write_text(REFUSE, encoding="utf-8")
            (self.fakebin / name).chmod(0o755)
        env = {k: v for k, v in os.environ.items()
               if k not in SCRUBBED and not k.startswith(SCRUBBED_PREFIXES)}
        env.update({
            "HOME": str(self.home),
            "TMPDIR": str(root / "tmp"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "PATH": f"{self.fakebin}{os.pathsep}{env.get('PATH', '')}",
            "AGENT_PROTOCOL_ROOT": str(self.home / ".agents"),
            "LANES_WORKSTATION": "Eagle",
            "LANES_HOST": "hosta",
            "LANES_CONTAINER": "bench-a",
            "LANES_NO_GITHUB": "1",
            "LANES_INDEX": "off",
            "LANE_WORKTREES_REPORT": "off",
            "GIT_AUTHOR_NAME": "a23 tests",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "a23 tests",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        self.env = env
        self.git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.quiet(self.origin, bare=True)
        seed = root / "seed"
        self.git("clone", "-q", str(self.origin), str(seed))
        self.quiet(seed)
        rows = [_row(LANE), _row("repoA23-2"), _row(DORMANT, uuid="a23a0009-a2a2-4000-8000-a23a0009a2a2"),
                _row(TARGET, uuid=TARGET_UUID)]
        self.write(seed, REGISTER,
                   "# LANES.md -- the sandbox register\n\n"
                   "| lane | session id | workstation / env / user | started (UTC) "
                   "| objects owned | handoff path | state |\n"
                   "|---|---|---|---|---|---|---|\n" + "".join(f"{r}\n" for r in rows))
        # THE TARGET OF A REQUEST IS BOUND ELSEWHERE: its last lane-kind line is
        # a STARTED from another container on this host (Amendment 18).
        self.write(seed, f"lanes/log/{TARGET}.md",
                   f"# lane {TARGET} — object log (lane-collision-protocol Amendment 7)\n"
                   f"STARTED — lane {TARGET}, session {TARGET_UUID}@Eagle, 2026-10-17T09:00:00Z, "
                   f"lane:{TARGET} → home opensoft/repoA23; estate repoA23; dir {root}/lanedir; "
                   f"profile team-05a; window othersess:4 @62; host hosta; os linux; container bench-b\n")
        self.write(seed, f"lanes/log/{LANE}.md",
                   f"# lane {LANE} — object log (lane-collision-protocol Amendment 7)\n")
        self.write(seed, "handoffs/README.md", "# handoffs\n")
        self.git("-C", str(seed), "add", "--", REGISTER, "handoffs/README.md", "lanes/log")
        self.git("-C", str(seed), "commit", "-q", "-m", "seed")
        self.git("-C", str(seed), "push", "-q", "origin", "main")
        self.seed = seed
        self.git("clone", "-q", str(self.origin), str(self.w))
        self.quiet(self.w)
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.w}\n", encoding="utf-8")

    def quiet(self, repo: Path, *, bare: bool = False) -> None:
        where = ["--git-dir", str(repo)] if bare else ["-C", str(repo)]
        self.git(*where, "config", "gc.auto", "0")
        self.git(*where, "config", "maintenance.auto", "false")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    @staticmethod
    def write(checkout: Path, rel: str, text: str) -> None:
        path = checkout / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def helper(self, *args: str, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(REPO / "lanes-edit.sh"), *args],
                              env=dict(self.env, **extra), cwd=str(self.root),
                              capture_output=True, text=True, timeout=180, check=False)

    def checkout(self, lane: str) -> Path:
        return self.lanes_root / lane

    def clone(self, dest: Path) -> Path:
        self.git("clone", "-q", str(self.origin), str(dest))
        self.quiet(dest)
        return dest

    def origin_head(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse", "main").strip()

    def origin_file(self, rel: str) -> str:
        return self.git("--git-dir", str(self.origin), "show", f"main:{rel}")

    def w_state(self) -> tuple[str, str]:
        return (self.git("-C", str(self.w), "rev-parse", "HEAD").strip(),
                self.git("-C", str(self.w), "status", "--porcelain", "--untracked-files=all"))


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
