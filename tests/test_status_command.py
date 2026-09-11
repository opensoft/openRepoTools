# SPDX-License-Identifier: Apache-2.0
"""`status` — the read-only view of an estate: the LOCAL layer, and `--fetch`.

Brett Heap's RULING of 2026-09-10 in this repository, verbatim: "lets go with
a fourth file. start with the local status layer." So this file asserts what
that layer is: the same estate resolution `park` and `resume` have (held
byte-for-byte elsewhere), one row per repository the estate reads — holder or
root, each member's working clone, every mounted leg — and, for each, what
this machine already knows without a fetch: ahead/behind the tracking
branch's origin AS OF THE LAST FETCH, dirty and stashed, feature branches
never pushed or whose remote branch is gone, dirty feature worktrees, and a
leg checked out away from its pin or pinned behind its origin. And the two
things it never does without being asked: fetch, and change anything.

His RULING of 2026-09-11, verbatim: "next layer: --fetch". With the flag,
`git fetch --prune origin` runs in every repository before it is read — the
ONE write this command makes, to remote-tracking refs and nothing else — and
the second section of this file holds exactly that: what moved is said, a
deleted remote branch reads as gone, a fetch that fails is a finding and the
read goes on, the leg is fetched too, and local branches, HEAD, index,
working tree and stash are untouched.

OFFLINE, LIKE THE REST OF THIS SUITE. Every remote is a BARE REPOSITORY IN A
TEMPORARY DIRECTORY and every `$HOME` is a temporary directory. Nothing here
needs `make` or the Speckit overlay, because `status` runs nothing; the one
family test borrows the estate fixture `test_park_resume_commands.py` builds
out of openRepoShape's own template bytes, and skips with it where the
submodule is not checked out.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import NEEDS_UPSTREAM, REPO, WINDOWS_SKIP, git, rmtree
from test_park_resume_commands import (  # noqa: F401  (fixtures by name)
    ORG, MEMBERS, FAMILY, commit_all, estate, remotes, run, probe_project,
)

STATUS = REPO / "status"

#: The command is bash, and it runs `git` in a checkout; Windows has no
#: shebang execution for it. On Windows the way in is WSL2.
pytestmark = [
    WINDOWS_SKIP,
    pytest.mark.skipif(shutil.which("bash") is None,
                       reason="status is a bash script"),
]

#: THE ONE LINE EVERY RUN CARRIES. A status that stopped saying this is one
#: somebody reads as current, and then does not fetch.
CAVEAT = "as of the last fetch: status reads local refs only and fetches nothing."

ROOT_WITH_LEG_YAML = """\
schema_version: 1
kind: project-manifest
id: {id}
name: "{name}"
tracking_branch: main
legs:
  - role: assembly
    repository: {org}/{name}
    path: "."
  - role: spec
    repository: {org}/{name}-spec
    path: spec
"""


@pytest.fixture
def home(tmp_path) -> Path:
    """A fake home with `projects/` in it — the common spelling."""
    target = tmp_path / "home"
    (target / "projects").mkdir(parents=True)
    return target


def seed_root_with_leg(base: Path, name: str) -> dict:
    """Bare remotes for ONE standalone root that mounts ONE leg.

    The leg has two commits so a checkout can be moved one back and be
    genuinely away from its pin; the root pins the leg's tip. No Makefile and
    no overlay: `status` runs nothing, so a root here is a `project.yaml`, a
    `.gitmodules` and git.
    """
    leg_seed = base / "seed" / f"{name}-spec"
    leg_seed.mkdir(parents=True)
    (leg_seed / "spec.md").write_text("# the spec leg\n", encoding="utf-8")
    git("init", "-q", "-b", "main", ".", cwd=leg_seed)
    commit_all(leg_seed, "the leg")
    (leg_seed / "more.md").write_text("more spec\n", encoding="utf-8")
    commit_all(leg_seed, "the leg moved on")
    leg_bare = base / "remotes" / f"{name}-spec.git"
    leg_bare.parent.mkdir(parents=True, exist_ok=True)
    git("clone", "-q", "--bare", str(leg_seed), str(leg_bare), cwd=base)

    seed = base / "seed" / name
    seed.mkdir(parents=True)
    (seed / "project.yaml").write_text(
        ROOT_WITH_LEG_YAML.format(id=name.lower(), name=name, org=ORG),
        encoding="utf-8")
    (seed / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    git("init", "-q", "-b", "main", ".", cwd=seed)
    commit_all(seed, "seed")
    git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
        str(leg_bare), "spec", cwd=seed)
    commit_all(seed, "the leg, pinned")
    bare = base / "remotes" / f"{name}.git"
    git("clone", "-q", "--bare", str(seed), str(bare), cwd=base)
    return {"bare": bare, "leg_bare": leg_bare, "leg_seed": leg_seed,
            "seed": seed}


@pytest.fixture
def status_remotes(tmp_path) -> dict:
    """PER TEST, not per session: `push_from_elsewhere` moves a bare's `main`,
    and a bare shared across tests would hand the next test a clone whose
    pin is already behind — a true finding, in the wrong test."""
    base = tmp_path / "status-remotes"
    base.mkdir()
    return {"base": base, "Atlas": seed_root_with_leg(base, "Atlas")}


def clone_root(home: Path, remote: dict, name: str) -> Path:
    """The root cloned under the fake projects directory, leg mounted."""
    root = home / "projects" / name
    git("-c", "protocol.file.allow=always", "clone", "-q",
        "--recurse-submodules", str(remote["bare"]), str(root),
        cwd=home / "projects")
    return root


@pytest.fixture
def atlas(home, status_remotes) -> Path:
    return clone_root(home, status_remotes["Atlas"], "Atlas")


def push_from_elsewhere(base: Path, bare: Path, tag: str,
                        stem: str = "elsewhere") -> None:
    """One more commit on `main` in the bare, made from ANOTHER clone — so the
    clone under test is behind and knows nothing about it until it fetches."""
    other = base / f"{stem}-{tag}"
    git("clone", "-q", str(bare), str(other), cwd=base)
    (other / f"{tag}.md").write_text(f"{tag}\n", encoding="utf-8")
    commit_all(other, f"{tag} from elsewhere")
    git("push", "-q", "origin", "main", cwd=other)
    rmtree(other)


def snapshot(repo: Path) -> str:
    """Everything a read-only command must leave alone, as one string."""
    refs = git("for-each-ref", cwd=repo).stdout
    head = git("rev-parse", "HEAD", cwd=repo).stdout
    porcelain = git("status", "--porcelain", "--ignore-submodules=none",
                    cwd=repo).stdout
    stash = git("stash", "list", cwd=repo).stdout
    return refs + head + porcelain + stash


# --- a fresh clone --------------------------------------------------------

def test_a_fresh_clone_is_in_sync_and_says_so_per_repository(atlas, home):
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"status: Atlas - the assembly root at {atlas}" in result.stdout
    assert CAVEAT in result.stdout
    assert f"root   main   {atlas}" in result.stdout
    assert f"leg    main   {atlas / 'spec'}" in result.stdout
    assert "in sync with origin/main; clean" in result.stdout
    assert ("at its pin, which is origin/main's tip as of the last fetch; "
            "clean") in result.stdout
    assert ("status: Atlas - 0 finding(s) in 2 repositories; nothing was "
            "changed.") in result.stdout
    assert result.stderr == ""


def test_help_prints_the_first_usage_line_and_the_exit_codes():
    result = subprocess.run(["bash", str(STATUS), "--help"],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].startswith("status [<Name>]")
    assert "EXIT 0" in result.stdout and "EXIT 1" in result.stdout
    assert "FETCHES NOTHING unless you say `--fetch`" in result.stdout
    assert "  --fetch " in result.stdout


# --- the root against its origin -------------------------------------------

def test_an_unpushed_commit_on_the_root_is_a_finding_and_exit_one(atlas, home):
    (atlas / "local.md").write_text("only here\n", encoding="utf-8")
    commit_all(atlas, "a commit origin has not seen")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    - ahead of origin/main by 1 commit(s): unpushed" in result.stdout
    assert "1 finding(s) in 2 repositories" in result.stdout


def test_behind_is_known_only_after_a_fetch_because_status_never_fetches(
        atlas, home, status_remotes):
    """THE CAVEAT, PROVED. A commit lands on origin from another workstation;
    this clone has not fetched, so `status` — which fetches nothing — must
    still say in sync, and say as of the last fetch. After a fetch the same
    command reports behind."""
    push_from_elsewhere(status_remotes["base"], status_remotes["Atlas"]["bare"],
                        "behind")
    before = run(STATUS, "Atlas", home=home)
    assert before.returncode == 0, before.stdout + before.stderr
    assert "- behind origin/main" not in before.stdout
    assert CAVEAT in before.stdout

    git("fetch", "-q", "origin", cwd=atlas)
    after = run(STATUS, "Atlas", home=home)
    assert after.returncode == 1, after.stdout + after.stderr
    assert ("    - behind origin/main by 1 commit(s), as of the last fetch"
            in after.stdout)


def test_dirty_and_stashed_are_counted(atlas, home):
    (atlas / "untracked.txt").write_text("x\n", encoding="utf-8")
    (atlas / "README.md").write_text("changed\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1
    assert "    - dirty: 2 path(s)" in result.stdout

    git("stash", "-q", cwd=atlas)  # the README change; the untracked stays
    result = run(STATUS, "Atlas", home=home)
    assert "    - dirty: 1 path(s)" in result.stdout
    assert "    - 1 stash(es)" in result.stdout


def test_a_root_on_a_feature_branch_or_detached_is_a_finding(atlas, home):
    git("checkout", "-q", "-b", "001-a-thing", cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1
    assert ("    - on branch 001-a-thing, not main (`resume` refuses a root on "
            "a feature branch)") in result.stdout

    git("checkout", "-q", "--detach", cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1
    assert "    - detached HEAD at " in result.stdout
    assert "; expected to be on main" in result.stdout


def test_feature_branches_never_pushed_unpushed_and_gone(atlas, home):
    """Three states of a feature branch, without a fetch for the first two
    and after a prune for the third. The root itself is put back on `main`
    each time, so the ONLY finding is the branch's."""
    git("checkout", "-q", "-b", "001-a-thing", cwd=atlas)
    (atlas / "feature.md").write_text("wip\n", encoding="utf-8")
    commit_all(atlas, "feature work")
    git("checkout", "-q", "main", cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - branch 001-a-thing: 1 commit(s) never pushed (no upstream "
            "branch)") in result.stdout
    assert "1 finding(s)" in result.stdout

    git("push", "-q", "-u", "origin", "001-a-thing", cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "001-a-thing" not in result.stdout, "pushed and level is not a finding"

    git("checkout", "-q", "001-a-thing", cwd=atlas)
    (atlas / "feature2.md").write_text("more wip\n", encoding="utf-8")
    commit_all(atlas, "more feature work")
    git("checkout", "-q", "main", cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1
    assert ("    - branch 001-a-thing: 1 commit(s) unpushed to "
            "origin/001-a-thing") in result.stdout

    git("push", "-q", "origin", "--delete", "001-a-thing", cwd=atlas)
    git("fetch", "-q", "--prune", "origin", cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1
    assert ("    - branch 001-a-thing: its remote branch origin/001-a-thing is "
            "gone (merged, or deleted)") in result.stdout


def test_a_dirty_feature_worktree_is_a_finding(atlas, home):
    """The Speckit extension's shape: a feature in a LINKED worktree. Its
    branch is read like any other; what only the worktree can say is that it
    holds uncommitted work, which is what `park` would have to carry."""
    worktree = home / "projects" / "Atlas-wt" / "001-a-thing"
    worktree.parent.mkdir(parents=True)
    git("worktree", "add", "-q", "-b", "001-a-thing", str(worktree),
        cwd=atlas)
    (worktree / "wip.md").write_text("uncommitted\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    - worktree " in result.stdout
    assert "on 001-a-thing: dirty, 1 path(s)" in result.stdout
    assert ("    - branch 001-a-thing: never pushed; no commit of its own yet "
            "(no upstream branch)") in result.stdout, (
        "the branch is read as well, and a branch with no commit of its own "
        "is not `0 commit(s) never pushed`")


# --- the leg against its pin -------------------------------------------------

def test_a_leg_checked_out_away_from_its_pin_is_reported_once(atlas, home):
    """Moved but not pinned — and reported on the LEG's row only: the root's
    porcelain would also show ` M spec`, which is the same fact twice."""
    leg = atlas / "spec"
    git("checkout", "-q", "HEAD~1", cwd=leg)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    - checked out at " in result.stdout
    assert ": moved but not pinned (scripts/bump-leg.py)" in result.stdout
    assert "dirty" not in result.stdout, (
        "the moved leg must not be counted again as a dirty root")
    assert "1 finding(s) in 2 repositories" in result.stdout


def test_a_leg_on_a_feature_branch_at_its_pin_is_a_finding(atlas, home):
    """AGENTS.md rule 1: `resume` refuses a root whose LEG sits on a feature
    branch, because that root's own `make bootstrap` would walk the leg back.
    The superproject looks clean in that state — which is why the leg's row
    has to say it, pin or no pin — while a leg detached at its pin (every
    fresh clone) and a leg on its tracking branch are both not findings."""
    leg = atlas / "spec"
    git("checkout", "-q", "-b", "001-leg-work", cwd=leg)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - on branch 001-leg-work, not main (`resume` refuses a root "
            "whose leg sits on a feature branch)") in result.stdout
    assert ("    - branch 001-leg-work: never pushed; no commit of its own yet "
            "(no upstream branch)") in result.stdout, (
        "the branch itself is read too, as it is in a root")
    assert "moved but not pinned" not in result.stdout, "it is AT the pin"
    assert "dirty" not in result.stdout, "the superproject looks clean"
    assert "2 finding(s) in 2 repositories" in result.stdout

    git("checkout", "-q", "main", cwd=leg)
    git("branch", "-q", "-D", "001-leg-work", cwd=leg)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_pin_behind_its_legs_origin_after_the_leg_fetched(atlas, home,
                                                             status_remotes):
    leg = atlas / "spec"
    push_from_elsewhere(status_remotes["base"],
                        status_remotes["Atlas"]["leg_bare"], "legbehind")
    before = run(STATUS, "Atlas", home=home)
    assert before.returncode == 0, before.stdout + before.stderr

    git("fetch", "-q", "origin", cwd=leg)
    after = run(STATUS, "Atlas", home=home)
    assert after.returncode == 1, after.stdout + after.stderr
    assert "    - pin " in after.stdout
    assert (" is 1 commit(s) behind origin/main, as of the last fetch"
            in after.stdout)
    assert "moved but not pinned" not in after.stdout, (
        "the checkout is still AT the pin; only the pin is stale")


def test_a_pin_on_a_commit_the_leg_never_pushed(atlas, home):
    """`bump-leg` ran, the leg did not push: the root now pins a commit
    origin/main does not have. Two findings, one per repository."""
    leg = atlas / "spec"
    git("checkout", "-q", "main", cwd=leg)
    (leg / "local.md").write_text("leg work\n", encoding="utf-8")
    commit_all(leg, "leg work not pushed")
    git("add", "spec", cwd=atlas)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm",
        "pin the leg's new commit", cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    - ahead of origin/main by 1 commit(s): unpushed" in result.stdout
    assert " is not on origin/main: 1 commit(s) unpushed in the leg" \
        in result.stdout
    assert "2 finding(s) in 2 repositories" in result.stdout


def test_a_leg_declared_and_not_mounted_is_a_finding(home, status_remotes):
    root = home / "projects" / "Atlas"
    git("clone", "-q", str(status_remotes["Atlas"]["bare"]), str(root),
        cwd=home / "projects")  # no --recurse-submodules: spec/ is empty
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"leg    main   {root / 'spec'}" in result.stdout
    assert ("    - declared in .gitmodules and not mounted (`make bootstrap` "
            "places it)") in result.stdout


# --- a family ---------------------------------------------------------------

@NEEDS_UPSTREAM
def test_a_family_reads_the_holder_and_each_working_clone_and_names_a_missing_one(
        estate, home):
    """The holder, then each member's working clone beside it — the same rows
    `park`'s report reads — and a member with NO working clone is a finding
    rather than a silent skip: the estate as recorded is not all here."""
    result = run(STATUS, FAMILY, home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"holder main   {estate['holder']}" in result.stdout
    for name in MEMBERS:
        assert f"root   main   {estate['siblings'][name]}" in result.stdout
    assert "0 finding(s) in 3 repositories" in result.stdout

    rmtree(estate["siblings"]["Bravo"])
    result = run(STATUS, FAMILY, home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - not here: no working clone beside the holder (`resume "
            f"{FAMILY}` places it)") in result.stdout
    assert "1 finding(s) in 3 repositories" in result.stdout


# --- every estate ------------------------------------------------------------

@pytest.mark.parametrize("flag", ["--all", "-a"])
def test_all_reads_every_estate_in_name_order_with_a_summary(home,
                                                             status_remotes,
                                                             flag):
    clone_root(home, status_remotes["Atlas"], "Borealis")
    atlas = clone_root(home, status_remotes["Atlas"], "Atlas")
    result = run(STATUS, flag, home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "status --all: reading every estate under" in result.stdout
    assert result.stdout.index("=== status Atlas ===") < \
        result.stdout.index("=== status Borealis ===")
    assert "  in sync    Atlas" in result.stdout
    assert "  in sync    Borealis" in result.stdout
    assert ("status: 2 estate(s) in sync, 0 with findings; nothing was "
            "changed.") in result.stdout

    (atlas / "dirty.txt").write_text("x\n", encoding="utf-8")
    result = run(STATUS, flag, home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "  findings   Atlas (1)" in result.stdout
    assert "  in sync    Borealis" in result.stdout
    assert "status: 1 estate(s) in sync, 1 with findings" in result.stdout


def test_bare_status_outside_every_estate_reads_them_all_without_asking(
        home, status_remotes):
    """Unlike `park`, whose bare form asks before a sweep that WRITES: a read
    changes nothing, so the answer to "which estate did you mean" is all of
    them, and `run` hands it a pipe for stdin — nothing may be asked."""
    clone_root(home, status_remotes["Atlas"], "Atlas")
    result = run(STATUS, home=home, cwd=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: no estate around" in result.stdout
    assert "reading every estate under" in result.stdout
    assert "[y/N]" not in result.stdout + result.stderr
    assert "=== status Atlas ===" in result.stdout


def test_bare_status_inside_an_estate_reads_only_that_one(home,
                                                          status_remotes):
    clone_root(home, status_remotes["Atlas"], "Borealis")
    atlas = clone_root(home, status_remotes["Atlas"], "Atlas")
    result = run(STATUS, home=home, cwd=atlas / "spec")
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"status: Atlas - the assembly root at {atlas}" in result.stdout
    assert "Borealis" not in result.stdout
    assert "reading every estate" not in result.stdout


# --- refusals, and the one promise ------------------------------------------

def test_refusals_read_nothing(home, status_remotes):
    atlas = clone_root(home, status_remotes["Atlas"], "Atlas")
    both = run(STATUS, "Atlas", "--all", home=home)
    assert both.returncode == 2 and "both <Name> ('Atlas') and --all" in both.stderr
    unknown = run(STATUS, "--dry-run", home=home)
    assert unknown.returncode == 2 and "does not know --dry-run" in unknown.stderr
    assert "-- --dry-run" not in unknown.stderr, "there is no extension to pass to"
    nope = run(STATUS, "Nope", home=home)
    assert nope.returncode == 2 and "no estate named 'Nope'" in nope.stderr
    # A MISSING VALUE IS THIS COMMAND'S refusal, exit 2 — not bash's `${2:?}`
    # message and exit 1, which is what `status` means by "findings".
    valueless = run(STATUS, "--repo", home=home)
    assert valueless.returncode == 2, valueless.stdout + valueless.stderr
    assert "REFUSED: --repo needs a value" in valueless.stderr
    for result in (both, unknown, nope, valueless):
        assert str(atlas) not in result.stdout, "a refusal read nothing"


def test_a_git_that_cannot_run_is_refused_not_reported(atlas, home, tmp_path):
    """Every git call is `|| true`-guarded so a missing ref is a finding, not
    a crash — so a git that refuses EVERY command would otherwise come back as
    an estate with no commits, no branch and no legs, exit 1, and nothing to
    say that nothing was read. A shim that rejects `--no-optional-locks`, the
    way a git older than 2.15 does, has to be refused by name instead."""
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "git").write_text("#!/bin/sh\nexit 129\n", encoding="utf-8")
    (shim / "git").chmod(0o755)
    result = run(STATUS, "Atlas", home=home,
                 env={"PATH": f"{shim}:{os.environ['PATH']}"})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "does not know `--no-optional-locks`" in result.stderr
    assert "no commits at all" not in result.stdout + result.stderr
    assert "finding(s)" not in result.stdout, "nothing may be reported"


def test_no_estate_anywhere_refuses(home):
    result = run(STATUS, home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "nothing to read" in result.stderr
    everything = run(STATUS, "--all", home=home)
    assert everything.returncode == 2
    assert "--all found no estate under" in everything.stderr


# --- --fetch: the second layer ------------------------------------------------
#
# Brett Heap's RULING of 2026-09-11, verbatim: "next layer: --fetch".

FETCHED = ("fetched first (--fetch): origin is asked in every repository "
           "below, then it is read.")
FETCH_CLAUSE = "only remote-tracking refs and fetched objects were changed (--fetch)."


def local_state(repo: Path) -> str:
    """Everything `--fetch` must leave alone: local branches, HEAD, the
    porcelain and the stash list. NOT the remote-tracking refs — moving those
    is the one thing a fetch is for."""
    heads = git("for-each-ref", "refs/heads", cwd=repo).stdout
    head = git("rev-parse", "HEAD", cwd=repo).stdout
    porcelain = git("status", "--porcelain", "--ignore-submodules=none",
                    cwd=repo).stdout
    stash = git("stash", "list", cwd=repo).stdout
    return heads + head + porcelain + stash


def test_fetch_makes_behind_visible_and_says_what_moved(atlas, home,
                                                        status_remotes):
    """The caveat's other half: with `--fetch`, the commit that landed on
    origin from another workstation is seen in one run, the report says which
    ref moved and from where, and the footer says what was changed."""
    push_from_elsewhere(status_remotes["base"], status_remotes["Atlas"]["bare"],
                        "fetchme")
    was = git("rev-parse", "origin/main", cwd=atlas).stdout.strip()[:7]
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert FETCHED in result.stdout
    assert CAVEAT not in result.stdout
    assert f"    fetched origin: origin/main moved {was} -> " in result.stdout
    assert ("    - behind origin/main by 1 commit(s), as of the last fetch"
            in result.stdout)
    assert "    fetched origin: nothing new on origin/main" in result.stdout, (
        "the leg was fetched too, and had nothing new")
    assert FETCH_CLAUSE in result.stdout
    assert "nothing was changed." not in result.stdout

    plain = run(STATUS, "Atlas", home=home)
    assert plain.returncode == 1, "the fetch persisted: a plain run knows too"
    assert "- behind origin/main by 1 commit(s)" in plain.stdout


def test_fetch_changes_remote_tracking_refs_and_nothing_else(atlas, home,
                                                             status_remotes):
    """THE ONE WRITE, bounded: origin/main moves; no local branch, HEAD,
    index entry, working-tree path or stash does — in the root or the leg."""
    leg = atlas / "spec"
    push_from_elsewhere(status_remotes["base"], status_remotes["Atlas"]["bare"],
                        "moveorigin")
    (atlas / "dirty.txt").write_text("x\n", encoding="utf-8")
    (atlas / "README.md").write_text("changed\n", encoding="utf-8")
    git("stash", "-q", cwd=atlas)
    git("branch", "001-a-thing", cwd=atlas)
    before = local_state(atlas) + local_state(leg)
    remote_was = git("rev-parse", "origin/main", cwd=atlas).stdout

    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert local_state(atlas) + local_state(leg) == before
    assert git("rev-parse", "origin/main", cwd=atlas).stdout != remote_was, (
        "the remote-tracking ref is what a fetch moves")
    assert not (atlas / ".git" / "index.lock").exists()
    # The leg's `.git` is a GITFILE; its real git dir is under the root's
    # `.git/modules/`, which is where a lock would be.
    leg_gitdir = Path(git("rev-parse", "--absolute-git-dir", cwd=leg).stdout.strip())
    assert leg_gitdir.is_dir()
    assert not (leg_gitdir / "index.lock").exists()


def test_fetch_prunes_so_a_branch_deleted_elsewhere_reads_as_gone(
        atlas, home, status_remotes):
    """A merged pull request deletes the remote branch UNDER a local feature.
    Deleted from another clone, this clone's `origin/001-a-thing` is stale
    and a plain read sees nothing wrong; `--fetch` prunes, and the branch
    reads as gone — which is the finding that says the worktree can go."""
    git("checkout", "-q", "-b", "001-a-thing", cwd=atlas)
    (atlas / "feature.md").write_text("wip\n", encoding="utf-8")
    commit_all(atlas, "feature work")
    git("push", "-q", "-u", "origin", "001-a-thing", cwd=atlas)
    git("checkout", "-q", "main", cwd=atlas)

    other = status_remotes["base"] / "elsewhere-delete"
    git("clone", "-q", str(status_remotes["Atlas"]["bare"]), str(other),
        cwd=status_remotes["base"])
    git("push", "-q", "origin", "--delete", "001-a-thing", cwd=other)
    rmtree(other)

    plain = run(STATUS, "Atlas", home=home)
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert "gone" not in plain.stdout, "a stale remote-tracking ref hides it"

    fetched = run(STATUS, "--fetch", "Atlas", home=home)
    assert fetched.returncode == 1, fetched.stdout + fetched.stderr
    assert ("    - branch 001-a-thing: its remote branch origin/001-a-thing is "
            "gone (merged, or deleted)") in fetched.stdout


def test_a_failed_fetch_is_a_finding_and_the_read_goes_on(atlas, home):
    """No network, a dead URL, a password prompt nobody is there for: the
    row says the fetch failed and is read as of the last fetch that worked;
    the leg, whose origin is fine, is still fetched and still read."""
    git("remote", "set-url", "origin", str(home / "nowhere" / "Atlas.git"),
        cwd=atlas)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    - fetch failed: " in result.stdout
    assert "as of the last fetch that worked" in result.stdout
    assert "    fetched origin: nothing new on origin/main" in result.stdout, (
        "the leg's fetch still ran")
    assert ("at its pin, which is origin/main's tip as of the last fetch; "
            "clean") in result.stdout
    assert "1 finding(s) in 2 repositories" in result.stdout
    assert FETCH_CLAUSE in result.stdout


def test_fetch_reaches_the_leg(atlas, home, status_remotes):
    push_from_elsewhere(status_remotes["base"],
                        status_remotes["Atlas"]["leg_bare"], "legmove")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    fetched origin: origin/main moved " in result.stdout
    assert " is 1 commit(s) behind origin/main, as of the last fetch" \
        in result.stdout
    assert "moved but not pinned" not in result.stdout


def test_fetch_prune_never_touches_a_local_branch_or_tag_whatever_the_config_says(
        atlas, home, status_remotes):
    """THE REFSPEC IS PINNED, and this is why. A leg whose `remote.origin.fetch`
    maps heads onto LOCAL branches (a `--mirror` clone, or a hand-edited
    config) plus `--prune` would delete a local branch that origin no longer
    has; `fetch.pruneTags` set anywhere would delete a local tag the same way.
    The review of this layer did exactly that through the configured form.
    With the refspec named on the command line, neither can happen — and
    `origin/main` still moves, so the fetch itself still did its job."""
    leg = atlas / "spec"
    git("config", "remote.origin.fetch", "+refs/heads/*:refs/heads/*", cwd=leg)
    git("config", "fetch.pruneTags", "true", cwd=leg)
    git("branch", "doomed", cwd=leg)
    git("tag", "keepme", cwd=leg)
    git("config", "fetch.pruneTags", "true", cwd=atlas)
    git("tag", "keepme-too", cwd=atlas)
    push_from_elsewhere(status_remotes["base"],
                        status_remotes["Atlas"]["leg_bare"], "legmoved")

    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    branches = git("for-each-ref", "--format=%(refname:short)", "refs/heads",
                   cwd=leg).stdout.split()
    assert "doomed" in branches, "--prune deleted a LOCAL branch"
    assert "main" in branches
    assert git("tag", cwd=leg).stdout.split() == ["keepme"], "a local tag went"
    assert git("tag", cwd=atlas).stdout.split() == ["keepme-too"]
    assert "    fetched origin: origin/main moved " in result.stdout, (
        "the pinned refspec must still move the remote-tracking ref")
    assert " is 1 commit(s) behind origin/main" in result.stdout


def test_fetch_says_when_the_tracking_branch_is_gone_from_origin(
        atlas, home, status_remotes):
    """A default-branch rename on origin: `--prune` removes `origin/main`,
    which is the right thing to do and the wrong thing to describe as
    "nothing new". The fetch line says GONE and from what, and the finding
    below it says origin has no such branch — not "never fetched", which
    the line above would contradict."""
    bare = status_remotes["Atlas"]["bare"]
    git("branch", "-m", "main", "main2", cwd=bare)
    git("symbolic-ref", "HEAD", "refs/heads/main2", cwd=bare)

    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    fetched origin: origin/main is GONE (was " in result.stdout
    assert "): deleted or renamed on origin" in result.stdout
    assert ("    - no origin/main after the fetch: origin has no branch main "
            "(deleted or renamed there)") in result.stdout
    assert "never fetched" not in result.stdout
    assert "nothing new on origin/main" in result.stdout, "the leg, untouched"


def test_fetch_on_a_leg_whose_gitdir_is_gone_says_so(atlas, home):
    """A gitfile pointing at a `.git/modules/<leg>` that was deleted: the
    leg is still "mounted" by the `.git` test, every git call in it fails,
    and the diagnosis must be the broken repository — not "add a remote"."""
    rmtree(atlas / ".git" / "modules" / "spec")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - fetch: not a readable git repository (a gitfile whose gitdir "
            "is gone?), so nothing could be fetched") in result.stdout
    assert "no remote named origin, so nothing could be fetched" \
        not in result.stdout
    plain = run(STATUS, "Atlas", home=home)
    assert plain.returncode == 1, "and without --fetch it still does not crash"


def test_fetch_with_no_origin_is_a_finding(atlas, home):
    leg = atlas / "spec"
    git("remote", "remove", "origin", cwd=leg)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - fetch: no remote named origin, so nothing could be fetched"
            in result.stdout)


def test_fetch_with_all_fetches_every_estate(home, status_remotes):
    clone_root(home, status_remotes["Atlas"], "Borealis")
    clone_root(home, status_remotes["Atlas"], "Atlas")
    result = run(STATUS, "--all", "--fetch", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("    fetched origin: nothing new on origin/main") == 4, (
        "two roots and two legs, each fetched")
    assert result.stdout.count(FETCHED) == 2
    assert f"status: 2 estate(s) in sync, 0 with findings; {FETCH_CLAUSE}" \
        in result.stdout


# --- the one promise ----------------------------------------------------------

def test_status_changes_nothing_and_takes_no_lock(atlas, home, status_remotes):
    """THE ONE PROMISE, against a repository in every state this file knows:
    ahead, dirty, stashed, a feature branch, a moved leg and a stale pin. Every
    ref, HEAD, the porcelain and the stash list are identical before and
    after, no `index.lock` is left behind, and the origin's `main` was not
    fetched — the clone still does not know it is behind."""
    leg = atlas / "spec"
    (atlas / "local.md").write_text("only here\n", encoding="utf-8")
    commit_all(atlas, "ahead")
    (atlas / "README.md").write_text("changed\n", encoding="utf-8")
    git("stash", "-q", cwd=atlas)
    (atlas / "dirty.txt").write_text("x\n", encoding="utf-8")
    git("branch", "001-a-thing", cwd=atlas)
    git("checkout", "-q", "HEAD~1", cwd=leg)
    push_from_elsewhere(status_remotes["base"], status_remotes["Atlas"]["bare"],
                        "unfetched")

    before = snapshot(atlas) + snapshot(leg)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert snapshot(atlas) + snapshot(leg) == before
    assert not (atlas / ".git" / "index.lock").exists()
    assert "- behind origin/main" not in result.stdout, "status fetched"
    assert "nothing was changed." in result.stdout
