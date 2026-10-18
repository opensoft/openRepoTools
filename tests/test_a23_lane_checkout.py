# SPDX-License-Identifier: Apache-2.0
"""Amendment 23 S1: one register checkout per lane, made on first use.

Every write resolves by default here — no `LANES_REPO` — so what runs is the
path a lane takes on a workstation: `workspace.yaml` names W, and the write goes
through `<W>-lanes/<lane>/`, a clone of W's origin that borrows W's objects,
made under a creation lock the first time the lane writes. Anything at that path
that is not a clone of the register is refused with exit 1, and nothing at it is
deleted, moved or repaired (S1).

Each case is the real `lanes-edit.sh` in a sandbox: a bare origin (with a second
branch, so `--single-branch` shows), W cloned from it, and `workspace.yaml`
joining the two. Nothing reaches a real remote, `gh` or `tmux`.
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

LANE = "repoCK-1"
REGISTER = "lanes/LANES.md"
UUID = "a23c0001-0c0c-4000-8000-a23c00010c0c"

SCRUBBED_PREFIXES = ("LANES_", "LANE_START_", "CLAUDE_", "OPENREPOTOOLS_",
                     "FAKE_", "GIT_", "TMUX")
SCRUBBED = {"AGENT_PROTOCOL_ROOT", "PROJECTS_ROOT", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME"}

REFUSE = """#!/usr/bin/env bash
printf 'FAKE %s REFUSED: %s -- this suite reaches no real surface\\n' "${0##*/}" "$*" >&2
exit 90
"""


def _row(lane: str, state: str = "LIVE · seeded") -> str:
    return (f"| `{lane}` | harness `{UUID}` | Eagle / test / tester | 2026-10-17T00:00Z "
            f"| — | handoffs/repoCK/{lane}.md | {state} |")


class Box:
    """A bare origin, W cloned from it, and the workspace.yaml naming W."""

    def __init__(self, root: Path, *, rows=("repoCK-1", "repoCK-2", "repoCK-3", "repoCK-5"),
                 aliases: str = "", w_reference: Path | None = None) -> None:
        # REAL PATHS, because the helper prints W and its lane checkouts as
        # `pwd -P` spells them (a temp root under a symlink would not match).
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
        register = ("# LANES.md -- the sandbox register\n\n"
                    "| lane | session id | workstation / env / user | started (UTC) "
                    "| objects owned | handoff path | state |\n"
                    "|---|---|---|---|---|---|---|\n"
                    + "".join(f"{_row(lane)}\n" for lane in rows))
        self.write(seed, REGISTER, register)
        self.write(seed, "handoffs/README.md", "# handoffs\n")
        paths = [REGISTER, "handoffs/README.md"]
        if aliases:
            self.write(seed, "lanes/aliases.tsv", aliases)
            paths.append("lanes/aliases.tsv")
        self.git("-C", str(seed), "add", "--", *paths)
        self.git("-C", str(seed), "commit", "-q", "-m", "seed")
        self.git("-C", str(seed), "push", "-q", "origin", "main")
        # A SECOND BRANCH ON ORIGIN, so a clone that took every branch shows.
        self.git("-C", str(seed), "push", "-q", "origin", "main:refs/heads/side")
        self.seed = seed
        clone = ["clone", "-q"]
        if w_reference is not None:
            clone += ["--reference", str(w_reference)]
        self.git(*clone, str(self.origin), str(self.w))
        self.quiet(self.w)
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.w}\n", encoding="utf-8")

    def quiet(self, repo: Path, *, bare: bool = False) -> None:
        """gc.auto=0 and maintenance.auto=false: W is what lane checkouts borrow."""
        where = ["--git-dir", str(repo)] if bare else ["-C", str(repo)]
        self.git(*where, "config", "gc.auto", "0")
        self.git(*where, "config", "maintenance.auto", "false")

    def git(self, *args: str, check: bool = True) -> str:
        return subprocess.run(["git", *args], env=self.env, check=check,
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

    def popen(self, *args: str, **extra: str) -> subprocess.Popen:
        return subprocess.Popen(["bash", str(REPO / "lanes-edit.sh"), *args],
                                env=dict(self.env, **extra), cwd=str(self.root),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def stamp(self, lane: str, words: str, **extra: str) -> subprocess.CompletedProcess:
        return self.helper("set-row-state", lane, f"LIVE · {words}", **extra)

    def checkout(self, lane: str) -> Path:
        return self.lanes_root / lane

    def origin_register(self) -> str:
        return self.git("--git-dir", str(self.origin), "show", f"main:{REGISTER}")

    def origin_head(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse", "main").strip()

    def w_state(self) -> tuple[str, str, str]:
        return (self.git("-C", str(self.w), "rev-parse", "HEAD").strip(),
                self.git("-C", str(self.w), "rev-parse", "HEAD^{tree}").strip(),
                self.git("-C", str(self.w), "status", "--porcelain"))

    def clone_by_hand(self, dest: Path, *, origin: Path | None = None,
                      reference: Path | None = None) -> None:
        args = ["clone", "-q"]
        if reference is not None:
            args += ["--reference", str(reference)]
        self.git(*args, str(origin or self.origin), str(dest))
        self.quiet(dest)


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def real(path: Path) -> str:
    return os.path.realpath(str(path))


def assert_refused_exit_1(box: Box, result: subprocess.CompletedProcess, path: Path) -> None:
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert str(path) in result.stderr, result.stderr
    assert "Nothing was written" in result.stderr, result.stderr
    assert "mv " in result.stderr and ".aside-" in result.stderr, result.stderr


# --------------------------------------------------------------- creation

def test_first_write_creates_the_lane_checkout_by_reference(box: Box):
    before = box.w_state()
    result = box.stamp(LANE, "first write")
    assert result.returncode == 0, (result.stdout, result.stderr)
    c = box.checkout(LANE)
    assert (c / ".git").is_dir(), "the lane's checkout is a clone of its own"
    alternates = (c / ".git" / "objects" / "info" / "alternates").read_text(encoding="utf-8").split()
    assert [real(Path(a)) for a in alternates] == [real(box.w / ".git" / "objects")], alternates
    remote_branches = [b for b in box.git("-C", str(c), "for-each-ref", "--format=%(refname)",
                                          "refs/remotes").split() if not b.endswith("/HEAD")]
    assert remote_branches == ["refs/remotes/origin/main"], \
        f"--single-branch: origin's other branch is not borrowed: {remote_branches}"
    assert box.git("-C", str(c), "config", "--get-all", "remote.origin.fetch").split() == \
        ["+refs/heads/main:refs/remotes/origin/main"]
    assert " · first write |" in box.origin_register()
    assert box.git("-C", str(c), "rev-parse", "HEAD").strip() == box.origin_head()
    # W IS THE READERS' COPY: its HEAD, its tree and its working tree are as
    # they were, though the write landed on origin.
    assert box.w_state() == before


def test_two_first_writers_race_on_creation(box: Box):
    one = box.popen("set-row-state", LANE, "LIVE · writer one")
    two = box.popen("set-row-state", LANE, "LIVE · writer two")
    out_one = one.communicate(timeout=240)
    out_two = two.communicate(timeout=240)
    assert one.returncode == 0, out_one
    assert two.returncode == 0, out_two
    subjects = box.git("--git-dir", str(box.origin), "log", "--format=%s", "main")
    assert "writer one" in subjects and "writer two" in subjects, subjects
    entries = sorted(p.name for p in box.lanes_root.iterdir())
    assert entries == [LANE], f"one checkout, no partial and no lock left: {entries}"
    c = box.checkout(LANE)
    assert sorted(p.name for p in c.iterdir() if p.name.startswith(".")) == [".git"], \
        "no clone nested inside the checkout"
    assert sum("creating lane" in o[1] for o in (out_one, out_two)) == 1, \
        "exactly one of the two writers cloned"


def test_leftover_partial_is_moved_aside(box: Box):
    partial = box.lanes_root / f".{LANE}.partial"
    partial.mkdir(parents=True)
    (partial / "half-cloned.txt").write_text("an earlier attempt\n", encoding="utf-8")
    result = box.stamp(LANE, "after a leftover")
    assert result.returncode == 0, (result.stdout, result.stderr)
    asides = [p for p in box.lanes_root.iterdir() if p.name.startswith(f".{LANE}.partial.aside-")]
    assert len(asides) == 1, list(box.lanes_root.iterdir())
    assert (asides[0] / "half-cloned.txt").read_text(encoding="utf-8") == "an earlier attempt\n", \
        "the leftover is moved aside whole, never deleted or cloned into"
    assert not partial.exists()
    assert (box.checkout(LANE) / ".git").is_dir()
    assert "moved" in result.stderr and "aside" in result.stderr


def test_target_appearing_before_mv_is_not_nested(box: Box):
    target = box.checkout(LANE)
    shim = box.fakebin / "appearing-git"
    shim.write_text(f"""#!/usr/bin/env bash
if [ "${{1-}}" = clone ]; then
  git "$@" || exit $?
  mkdir -p '{target}' && printf 'made by someone else\\n' > '{target}/theirs.txt'
  exit 0
fi
exec git "$@"
""", encoding="utf-8")
    shim.chmod(0o755)
    head = box.origin_head()
    result = box.stamp(LANE, "never written", LANES_GIT=str(shim))
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert sorted(p.name for p in target.iterdir()) == ["theirs.txt"], \
        "the clone was not moved INTO the directory that appeared"
    assert (box.lanes_root / f".{LANE}.partial" / ".git").is_dir(), "the clone is left at .partial"
    assert box.origin_head() == head, "nothing was written"


def _not_a_clone(box: Box, kind: str, path: Path) -> None:
    if kind == "file":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not a checkout\n", encoding="utf-8")
    elif kind == "plain directory":
        path.mkdir(parents=True)
        (path / "notes.txt").write_text("a directory, not a checkout\n", encoding="utf-8")
    elif kind == "another repository":
        path.mkdir(parents=True)
        box.git("init", "-q", "-b", "main", str(path))
        box.git("-C", str(path), "remote", "add", "origin", "https://github.com/opensoft/not-the-register.git")
    elif kind == "linked worktree":
        # A checkout whose `.git` is a FILE pointing at its git directory —
        # the shape a linked worktree has — with the register's own origin, so
        # the `.git`-is-a-directory test is the one that refuses it.
        path.parent.mkdir(parents=True, exist_ok=True)
        box.git("init", "-q", "-b", "main", f"--separate-git-dir={box.root / 'separate.git'}", str(path))
        box.git("-C", str(path), "remote", "add", "origin", str(box.origin))
    elif kind == "clone of another origin":
        other = box.root / "other.git"
        box.git("init", "-q", "--bare", "-b", "main", str(other))
        path.parent.mkdir(parents=True, exist_ok=True)
        box.git("clone", "-q", str(other), str(path))
    else:  # pragma: no cover
        raise AssertionError(kind)


def _listing(path: Path) -> list[str]:
    if path.is_file():
        return ["<file>", path.read_text(encoding="utf-8")]
    return sorted(str(p.relative_to(path)) for p in path.rglob("*"))


#: What each refusal says is there — the one test, of S1's several, that refused it.
WHAT_IS_THERE = {
    "file": "it is a file, not a directory",
    "plain directory": "it is a directory that is not a git checkout",
    "another repository": "it is a checkout of https://github.com/opensoft/not-the-register.git, where",
    "linked worktree": "it is a checkout whose .git is a file",
    "clone of another origin": "it is a checkout of {other}, where",
}


@pytest.mark.parametrize("kind", ["file", "plain directory", "another repository",
                                  "linked worktree", "clone of another origin"])
def test_non_clone_at_the_path_is_refused_exit_1(box: Box, kind: str):
    path = box.checkout(LANE)
    _not_a_clone(box, kind, path)
    before = _listing(path)
    head = box.origin_head()
    result = box.stamp(LANE, "never written")
    assert_refused_exit_1(box, result, path)
    assert "not a clone of the register" in result.stderr, result.stderr
    assert WHAT_IS_THERE[kind].format(other=box.root / "other.git") in result.stderr, result.stderr
    assert _listing(path) == before, "nothing at the path was deleted, moved or repaired"
    assert box.origin_head() == head
    assert not (box.lanes_root / f".{LANE}.partial").exists(), "nothing was cloned beside it"


def test_empty_directory_counts_as_absent(box: Box):
    box.checkout(LANE).mkdir(parents=True)
    result = box.stamp(LANE, "into an empty directory")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (box.checkout(LANE) / ".git").is_dir()
    assert " · into an empty directory |" in box.origin_register()


def test_alternates_not_naming_W_is_refused(box: Box):
    other = box.root / "other-store"
    box.clone_by_hand(other)
    c = box.checkout(LANE)
    box.clone_by_hand(c, reference=other)
    head = box.origin_head()
    result = box.stamp(LANE, "never written")
    assert_refused_exit_1(box, result, c)
    assert "borrows objects from" in result.stderr, result.stderr
    assert "cherry -v" in result.stderr, "the fix names the look-first read"
    assert box.origin_head() == head


def test_alternates_naming_a_missing_store_is_refused(box: Box):
    c = box.checkout(LANE)
    box.clone_by_hand(c, reference=box.w)
    gone = box.root / "gone" / "objects"
    (c / ".git" / "objects" / "info" / "alternates").write_text(f"{gone}\n", encoding="utf-8")
    head = box.origin_head()
    result = box.stamp(LANE, "never written")
    assert_refused_exit_1(box, result, c)
    assert "borrowed objects are gone" in result.stderr, result.stderr
    assert "cherry -v" in result.stderr
    assert box.origin_head() == head


def test_W_with_alternates_clones_without_reference(tmp_path: Path):
    store = tmp_path / "store.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(store)], check=True)
    box = Box(tmp_path / "b", w_reference=store)
    assert (box.w / ".git" / "objects" / "info" / "alternates").is_file()
    result = box.stamp(LANE, "one level only")
    assert result.returncode == 0, (result.stdout, result.stderr)
    c = box.checkout(LANE)
    assert not (c / ".git" / "objects" / "info" / "alternates").exists(), \
        "W borrows already, so the lane checkout borrows from nobody: one level"
    assert " · one level only |" in box.origin_register()


def test_the_clone_outlasts_a_short_network_bound(box: Box):
    """A COLD CLONE IS NOT A PUSH. Every other network call is bounded by
    `LANES_GIT_TIMEOUT`; the clone gets ten minutes, or that bound where it is
    longer, so a one-second bound does not kill a clone that takes three."""
    shim = box.fakebin / "slow-clone-git"
    shim.write_text("""#!/usr/bin/env bash
if [ "${1-}" = clone ]; then sleep 3; fi
exec git "$@"
""", encoding="utf-8")
    shim.chmod(0o755)
    made = box.helper("lane-checkout", LANE, "--create", LANES_GIT=str(shim), LANES_GIT_TIMEOUT="1")
    assert made.returncode == 0, (made.stdout, made.stderr)
    assert made.stdout.strip() == str(box.checkout(LANE))
    assert (box.checkout(LANE) / ".git").is_dir()


# --------------------------------------------------------------- names

ALIAS = "repoCK-7\trepoCK-8\t2026-10-17T00:00:00Z\n"


def test_renamed_lane_directory_is_moved_once(tmp_path: Path):
    box = Box(tmp_path, rows=("repoCK-8",), aliases=ALIAS)
    old = box.checkout("repoCK-7")
    box.clone_by_hand(old, reference=box.w)
    (old / ".git" / "made-under-the-old-name").write_text("x\n", encoding="utf-8")
    first = box.stamp("repoCK-8", "after the rename")
    assert first.returncode == 0, (first.stdout, first.stderr)
    new = box.checkout("repoCK-8")
    assert (new / ".git" / "made-under-the-old-name").is_file(), "the directory itself was moved"
    assert not old.exists()
    assert "is now" in first.stderr
    second = box.stamp("repoCK-8", "and again")
    assert second.returncode == 0, (second.stdout, second.stderr)
    assert "is now" not in second.stderr, "moved once, and never again"
    assert " · and again |" in box.origin_register()


def test_both_names_present_writes_new_reports_old(tmp_path: Path):
    box = Box(tmp_path, rows=("repoCK-8",), aliases=ALIAS)
    assert box.stamp("repoCK-8", "made the new one").returncode == 0
    old = box.checkout("repoCK-7")
    box.clone_by_hand(old, reference=box.w)
    old_head = box.git("-C", str(old), "rev-parse", "HEAD").strip()
    result = box.stamp("repoCK-8", "through the new one")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert str(old) in result.stderr and "former name" in result.stderr, result.stderr
    assert box.git("-C", str(old), "rev-parse", "HEAD").strip() == old_head, "the old one is left as it is"
    assert "through the new one" in box.git("-C", str(box.checkout("repoCK-8")), "log", "-1", "--format=%s")


def test_case_variant_writes_the_row_spelling_checkout(box: Box):
    result = box.stamp("REPOck-3", "typed in another case")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert [p.name for p in box.lanes_root.iterdir()] == ["repoCK-3"], \
        "the checkout is named for the row's own spelling (Amendment 15)"
    assert " · typed in another case |" in box.origin_register()


@pytest.mark.parametrize("name", ["repoCK/1", ".repoCK-1", "repoCK 1"])
def test_name_the_log_cannot_carry_is_refused(box: Box, name: str):
    head = box.origin_head()
    result = box.stamp(name, "never written")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "is not a lane name" in result.stderr, result.stderr
    assert not box.lanes_root.exists(), "nothing was created for a name no log file can carry"
    assert box.origin_head() == head


def test_W_local_identity_is_copied(box: Box):
    box.git("-C", str(box.w), "config", "user.name", "The Workspace Person")
    result = box.stamp(LANE, "under W's own name")
    assert result.returncode == 0, (result.stdout, result.stderr)
    c = box.checkout(LANE)
    assert box.git("-C", str(c), "config", "--local", "--get", "user.name").strip() == "The Workspace Person"
    unset = subprocess.run(["git", "-C", str(c), "config", "--local", "--get", "user.email"],
                           env=box.env, capture_output=True, text=True, check=False)
    assert unset.returncode == 1, "a key W does not set locally is not copied"


# --------------------------------------------------------------- the read verb

def test_lane_checkout_verb_reads_and_creates(box: Box):
    absent = box.helper("lane-checkout", LANE)
    assert absent.returncode == 8 and absent.stdout == "", (absent.stdout, absent.stderr)
    made = box.helper("lane-checkout", LANE, "--create")
    assert made.returncode == 0, (made.stdout, made.stderr)
    assert made.stdout.strip() == str(box.checkout(LANE))
    again = box.helper("lane-checkout", "REPOCK-1")
    assert again.returncode == 0 and again.stdout.strip() == str(box.checkout(LANE))
    usage = box.helper("lane-checkout")
    assert usage.returncode == 64
