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

His RULING of 2026-09-11, verbatim: "next layer: fork against upstream". A
remote named `upstream` is read from local refs, `origin/<branch>` against
`upstream/<branch>`, and `--fetch` fetches it too; with no such remote, and
only under `--fetch`, an origin on github.com is asked about once with `gh
api` — a FAKE `gh` on PATH here, answering the two calls the command makes,
and a `url.<base>.insteadOf` rewrite so an origin that LOOKS like github.com
still fetches from a bare repository on disk. Nothing here reaches the
network. The third section holds that layer.

His RULING of 2026-09-11, verbatim: "next layer: shape-pin drift". Every
root and holder carries `contracts/shape-pin.yaml`, a COPY PIN: the
openRepoShape commit its copied shape files came from and a sha256 per copy.
The fourth section holds that layer: a copy edited in place is drift, a
missing copy is named, a `shape:` mirror naming another commit is out of
step, and the pin is read against the standard's `main` — from a clone of it
under the projects directory (a bare repository on disk here, its origin
spelled as github.com so the clone is found by slug and never fetched), or
under `--fetch` from a fake `gh`'s compare answer.

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

FETCHED = ("fetched first (--fetch): origin — and upstream, where a fork has "
           "one — is asked in every repository below, then it is read.")
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
    leg_main_was = git("rev-parse", "refs/heads/main", cwd=leg).stdout

    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    branches = git("for-each-ref", "--format=%(refname:short)", "refs/heads",
                   cwd=leg).stdout.split()
    assert "doomed" in branches, "--prune deleted a LOCAL branch"
    assert "main" in branches
    # THE OTHER ROUTE: git maps every fetched ref through the CONFIGURED
    # refspecs too ("opportunistic remote-tracking updates"), so a pinned
    # refspec alone still moved a detached leg's local `main` under a mirror
    # config; `--refmap` is what stops it, and this is the line that proves it.
    assert git("rev-parse", "refs/heads/main", cwd=leg).stdout == leg_main_was, (
        "the pinned fetch moved the leg's LOCAL main through the configured "
        "refspec")
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


# --- the fork against its upstream --------------------------------------------
#
# Brett Heap's RULING of 2026-09-11, verbatim: "next layer: fork against
# upstream".

def parent_ahead(base: Path, remote: dict, tag: str) -> Path:
    """The PARENT the fork's origin was forked from, one commit ahead of it:
    a bare copy of origin's bare, then a push to it from elsewhere."""
    parent = base / "remotes" / f"{tag}-parent.git"
    git("clone", "-q", "--bare", str(remote["bare"]), str(parent), cwd=base)
    push_from_elsewhere(base, parent, tag, stem="parent-elsewhere")
    return parent


def github_origin(repo: Path, bare: Path, slug: str) -> None:
    """Make `origin` LOOK like github.com while every byte still comes from
    the bare on disk: `url.<base>.insteadOf` rewrites it for the fetch, and
    `status` reads the CONFIGURED url to decide whom to ask about."""
    url = f"https://github.com/{slug}.git"
    git("config", f"url.{bare}.insteadOf", url, cwd=repo)
    git("remote", "set-url", "origin", url, cwd=repo)


def fake_gh(tmp_path: Path, *, failing: bool = False,
            not_found: str | None = None,
            not_found_prefix: str | None = None) -> tuple[dict, Path]:
    """A fake `gh` first on PATH that answers the two calls `status` makes —
    `api repos/<slug>` (Atlas is a fork of opensoft/Atlas, its leg is not) and
    the compare (3 behind, 1 ahead) — printing what the `--jq` filter would,
    fields joined by 0x1F, and logging every call. `failing` answers as a
    `gh` nobody logged in to (exit 4, true of every repository);
    `not_found=<slug>` answers 404 (exit 1) for THAT repository's own call
    only, and `not_found_prefix=<slug>` for every call under it (its compare
    too)."""
    shim = tmp_path / "gh-shim"
    shim.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh-calls.log"
    body = f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{log}"\n'
    if failing:
        body += ("printf 'To get started with GitHub CLI, please run:  gh auth "
                 "login\\n' >&2\nexit 4\n")
    else:
        body += 'case "$*" in\n'
        if not_found:
            body += (f"*\"repos/{not_found} \"*) printf 'gh: Not Found (HTTP 404)"
                     "\\n' >&2; exit 1 ;;\n")
        if not_found_prefix:
            body += (f"*\"repos/{not_found_prefix}\"*) printf 'gh: Not Found (HTTP 404)"
                     "\\n' >&2; exit 1 ;;\n")
        body += (
            "*\"repos/opensoft/openRepoShape/compare/\"*) printf '0\\0374\\n' ;;\n"
            "*\"repos/opensoft/openRepoShape \"*) printf 'main\\n' ;;\n"
            "*\"/compare/\"*) printf '3\\0371\\n' ;;\n"
            "*\"repos/testorg/Atlas-spec \"*) printf 'false\\037\\037\\n' ;;\n"
            "*\"repos/testorg/Atlas \"*) printf 'true\\037opensoft/Atlas\\037main\\n' ;;\n"
            "*) printf 'fake gh: unexpected: %s\\n' \"$*\" >&2; exit 1 ;;\n"
            "esac\n")
    (shim / "gh").write_text(body, encoding="utf-8")
    (shim / "gh").chmod(0o755)
    return {"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}, log


def test_a_fork_behind_its_upstream_remote_reads_from_local_refs(
        atlas, home, status_remotes):
    """The convention every fork guide teaches: a remote named `upstream`.
    Before it has ever been fetched there is nothing to compare, and the
    finding says so and names `--fetch`; after one fetch of it the drift is
    read from local refs, as of that fetch, with no network at all."""
    parent = parent_ahead(status_remotes["base"], status_remotes["Atlas"],
                          "forkbehind")
    git("remote", "add", "upstream", str(parent), cwd=atlas)
    unfetched = run(STATUS, "Atlas", home=home)
    assert unfetched.returncode == 1, unfetched.stdout + unfetched.stderr
    assert ("    - fork: no upstream/main here: the upstream remote was never "
            "fetched (`--fetch` asks it)") in unfetched.stdout

    git("fetch", "-q", "upstream", cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - fork: origin/main is 1 commit(s) behind upstream/main, as of "
            "the last fetch") in result.stdout
    assert "in sync with origin/main" not in result.stdout.split("leg    main")[0], (
        "the root row has a finding, so no in-sync line")
    assert "1 finding(s) in 2 repositories" in result.stdout


def test_fetch_fetches_the_upstream_remote_under_the_pinned_refspec(
        atlas, home, status_remotes):
    """`--fetch` asks upstream as well as origin, says so on its own line,
    and the pinned refspec bounds that write too: a mirror-style refspec in
    `remote.upstream.fetch` cannot make `--prune` delete a local branch."""
    parent = parent_ahead(status_remotes["base"], status_remotes["Atlas"],
                          "forkfetch")
    git("remote", "add", "upstream", str(parent), cwd=atlas)
    git("config", "remote.upstream.fetch", "+refs/heads/*:refs/heads/*",
        cwd=atlas)
    git("branch", "doomed", cwd=atlas)
    main_was = git("rev-parse", "refs/heads/main", cwd=atlas).stdout
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    fetched origin: nothing new on origin/main" in result.stdout
    assert "    fetched upstream: upstream/main is here now, at " in result.stdout, (
        "with a mirror-style refspec configured, git would map the fetched main "
        "onto the CHECKED-OUT local main and refuse; --refmap is what makes "
        "this line appear")
    assert git("rev-parse", "refs/heads/main", cwd=atlas).stdout == main_was
    assert ("    - fork: origin/main is 1 commit(s) behind upstream/main, as of "
            "the last fetch") in result.stdout
    branches = git("for-each-ref", "--format=%(refname:short)", "refs/heads",
                   cwd=atlas).stdout.split()
    assert "doomed" in branches, "--prune on the upstream fetch deleted a LOCAL branch"
    assert git("rev-parse", "-q", "--verify", "refs/remotes/upstream/main",
               cwd=atlas, check=False).returncode == 0


def test_a_fork_pushed_ahead_of_its_upstream_is_a_finding(atlas, home,
                                                          status_remotes):
    """The other direction: commits on the fork's `main` that the parent
    does not have — somebody pushed to the fork's main instead of opening a
    pull request upstream."""
    base = status_remotes["base"]
    parent = base / "remotes" / "forkahead-parent.git"
    git("clone", "-q", "--bare", str(status_remotes["Atlas"]["bare"]),
        str(parent), cwd=base)
    push_from_elsewhere(base, status_remotes["Atlas"]["bare"], "forkahead")
    git("remote", "add", "upstream", str(parent), cwd=atlas)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - fork: origin/main has 1 commit(s) upstream/main does not"
            in result.stdout)
    assert "    - behind origin/main by 1 commit(s)" in result.stdout, (
        "the local main is behind the fork's main too, and that is read as before")


def test_a_github_origin_with_no_upstream_remote_is_asked_only_under_fetch(
        atlas, home, status_remotes, tmp_path):
    """No `upstream` remote, an origin on github.com: without `--fetch`
    nothing is asked and nothing is said; with it, `gh api` is asked once
    per repository, a fork is a finding naming the parent and the remote to
    add, the compare gives the counts, and a repository GitHub says is NOT a
    fork says nothing."""
    github_origin(atlas, status_remotes["Atlas"]["bare"], "testorg/Atlas")
    github_origin(atlas / "spec", status_remotes["Atlas"]["leg_bare"],
                  "testorg/Atlas-spec")
    env, log = fake_gh(tmp_path)

    plain = run(STATUS, "Atlas", home=home, env=env)
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert not log.exists(), "without --fetch, gh must not be asked"
    assert "fork" not in plain.stdout

    fetched = run(STATUS, "--fetch", "Atlas", home=home, env=env)
    assert fetched.returncode == 1, fetched.stdout + fetched.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 3, calls
    assert calls[0].startswith("api repos/testorg/Atlas --hostname github.com ")
    assert calls[1].startswith(
        "api repos/opensoft/Atlas/compare/main...testorg:main?per_page=1 "
        "--hostname github.com ")
    assert calls[2].startswith("api repos/testorg/Atlas-spec --hostname github.com ")
    assert ("    - fork of opensoft/Atlas (per GitHub), and no remote named "
            "upstream here: `git remote add upstream "
            "https://github.com/opensoft/Atlas.git` reads the drift locally"
            ) in fetched.stdout
    assert ("    - fork: origin/main is 3 commit(s) behind opensoft/Atlas's main "
            "(per GitHub)") in fetched.stdout
    assert ("    - fork: origin/main has 1 commit(s) opensoft/Atlas's main does "
            "not (per GitHub)") in fetched.stdout
    assert fetched.stdout.count("fork of") == 1, "the leg is not a fork"
    assert "    fetched origin: nothing new on origin/main" in fetched.stdout, (
        "the insteadOf rewrite still fetched from the bare on disk")
    assert "3 finding(s) in 2 repositories" in fetched.stdout


def test_a_failing_gh_is_said_once_and_a_local_origin_is_never_asked(
        atlas, home, status_remotes, tmp_path):
    github_origin(atlas, status_remotes["Atlas"]["bare"], "testorg/Atlas")
    github_origin(atlas / "spec", status_remotes["Atlas"]["leg_bare"],
                  "testorg/Atlas-spec")
    env, log = fake_gh(tmp_path, failing=True)
    result = run(STATUS, "--fetch", "Atlas", home=home, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("    fork check: `gh api repos/testorg/Atlas` "
                               "failed (") == 1
    assert "gh auth login); not asked again this run" in result.stdout
    assert result.stdout.count("fork check:") == 1, "said once, not per row"
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1

    plain_origin = clone_root(home, status_remotes["Atlas"], "Borealis")
    env2, log2 = fake_gh(tmp_path / "second")
    result = run(STATUS, "--fetch", "Borealis", home=home, env=env2)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not log2.exists(), "an origin that is not on github.com is never asked"
    assert str(plain_origin) in result.stdout


def test_a_404_on_one_repository_does_not_silence_the_others(
        atlas, home, status_remotes, tmp_path):
    """Not logged in (gh exit 4) is true of every repository and settles the
    run; a 404 is true of ONE — a repository this token cannot see — and the
    leg beside it must still be asked, or a fork nobody asked about reads as
    clean with the one trace under a different row."""
    github_origin(atlas, status_remotes["Atlas"]["bare"], "testorg/Atlas")
    github_origin(atlas / "spec", status_remotes["Atlas"]["leg_bare"],
                  "testorg/Atlas-spec")
    env, log = fake_gh(tmp_path, not_found="testorg/Atlas")
    result = run(STATUS, "--fetch", "Atlas", home=home, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("    fork check: `gh api repos/testorg/Atlas` failed (gh: Not Found "
            "(HTTP 404)); the other repositories are still asked") in result.stdout
    assert "not asked again this run" not in result.stdout
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 2, calls
    assert calls[1].startswith("api repos/testorg/Atlas-spec ")


def test_only_an_origin_whose_host_is_github_dot_com_is_asked(
        atlas, home, status_remotes, tmp_path):
    """`github.company.com` is somebody's GitHub Enterprise and `notgithub.com`
    somebody else's server; the question goes to github.com, so neither is
    asked — a match on the substring would send a private repository's name,
    with the person's token, to a server that never had it."""
    bare = status_remotes["Atlas"]["bare"]
    for i, url in enumerate((
            "https://github.company.com/testorg/Atlas.git",
            "https://notgithub.com/testorg/Atlas.git",
            "https://github.com.evil.example/testorg/Atlas.git",
            "https://gitlab.com/testorg/github.com-mirror.git")):
        git("config", "--add", f"url.{bare}.insteadOf", url, cwd=atlas)
        git("remote", "set-url", "origin", url, cwd=atlas)
        env, log = fake_gh(tmp_path / f"host{i}")
        result = run(STATUS, "--fetch", "Atlas", home=home, env=env)
        assert result.returncode == 0, url + result.stdout + result.stderr
        assert not log.exists(), f"{url} was asked about on github.com"
    for url in ("git@github.com:testorg/Atlas.git",
                "ssh://git@github.com:22/testorg/Atlas.git",
                "https://token@GitHub.com/testorg/Atlas.git"):
        git("config", "--add", f"url.{bare}.insteadOf", url, cwd=atlas)
        git("remote", "set-url", "origin", url, cwd=atlas)
        env, log = fake_gh(tmp_path / url.replace("/", "_").replace(":", "_"))
        result = run(STATUS, "--fetch", "Atlas", home=home, env=env)
        assert log.exists(), f"{url} IS github.com and must be asked"
        assert "fork of opensoft/Atlas" in result.stdout, url


def test_a_github_origin_with_an_upstream_remote_is_read_locally_not_asked(
        atlas, home, status_remotes, tmp_path):
    github_origin(atlas, status_remotes["Atlas"]["bare"], "testorg/Atlas")
    parent = parent_ahead(status_remotes["base"], status_remotes["Atlas"],
                          "localfirst")
    git("remote", "add", "upstream", str(parent), cwd=atlas)
    env, log = fake_gh(tmp_path)
    result = run(STATUS, "--fetch", "Atlas", home=home, env=env)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - fork: origin/main is 1 commit(s) behind upstream/main, as of "
            "the last fetch") in result.stdout
    assert not log.exists(), "with an upstream remote the answer is local"


# --- the shape pin --------------------------------------------------------------
#
# Brett Heap's RULING of 2026-09-11, verbatim: "next layer: shape-pin drift".

SHAPE_SOURCE = "opensoft/openRepoShape"

SHAPE_PIN_YAML = """\
schema_version: 1
kind: pinned_contract_manifest

# shape-pin.yaml — the openRepoShape revision this project was cut from.
# A COPY PIN, NOT A SUBMODULE PIN. EDITING A COPIED FILE IS DRIFT.

pin_role: shape
source_repository: {source}
materialization: copied

commit: "{commit}"
revision_kind: commit

digest_algorithm: sha256
digest_definition: sorted-ls-tree-r-v1
digests:
  tree_sha256: "{tree}"

verify_pin: scripts/validate-pins.py

files:
{rows}
"""

SHAPE_MIRROR_YAML = """\
shape:
  repository: {source}
  revision_kind: commit
  commit: "{commit}"
  digest_algorithm: sha256
  digest_definition: sorted-ls-tree-r-v1
  digests:
    tree_sha256: "{tree}"
"""


def fake_standard(base: Path, commits: int = 3) -> dict:
    """A bare repository standing in for opensoft/openRepoShape, `commits`
    commits deep on `main`, plus one commit on a branch `main` never had.
    Returns the bare and the shas, oldest first."""
    seed = base / "seed" / "openRepoShape"
    seed.mkdir(parents=True)
    git("init", "-q", "-b", "main", ".", cwd=seed)
    shas = []
    for i in range(commits):
        (seed / f"shape-{i}.md").write_text(f"shape {i}\n", encoding="utf-8")
        commit_all(seed, f"shape commit {i}")
        shas.append(git("rev-parse", "HEAD", cwd=seed).stdout.strip())
    git("checkout", "-q", "-b", "orphan-branch", shas[0], cwd=seed)
    (seed / "branch.md").write_text("never on main\n", encoding="utf-8")
    commit_all(seed, "a branch commit")
    branch_sha = git("rev-parse", "HEAD", cwd=seed).stdout.strip()
    git("checkout", "-q", "main", cwd=seed)
    bare = base / "remotes" / "openRepoShape.git"
    git("clone", "-q", "--bare", str(seed), str(bare), cwd=base)
    return {"bare": bare, "shas": shas, "branch_sha": branch_sha}


def standard_clone(home: Path, bare: Path) -> Path:
    """A clone of the fake standard under the projects directory whose origin
    is SPELLED as github.com, so `clone_with_origin` finds it by slug — with
    the remote-tracking refs the clone made from the bare, and never fetched
    again (the url is only a name)."""
    clone = home / "projects" / "openRepoShape"
    git("clone", "-q", str(bare), str(clone), cwd=home / "projects")
    git("remote", "set-url", "origin", f"https://github.com/{SHAPE_SOURCE}.git",
        cwd=clone)
    return clone


def pin_shape(root: Path, commit: str, copies: dict, *, mirror: str | None = None,
              push: bool = True) -> None:
    """Write the copies, the pin with their real digests, and the mirror in
    project.yaml; commit, and push so the clone stays in sync with origin."""
    import hashlib
    rows = []
    for rel, body in copies.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        rows.append(f"  - path: {rel}\n    sha256: \"{digest}\"")
    tree = "0" * 64
    (root / "contracts").mkdir(exist_ok=True)
    (root / "contracts" / "shape-pin.yaml").write_text(
        SHAPE_PIN_YAML.format(source=SHAPE_SOURCE, commit=commit, tree=tree,
                              rows="\n".join(rows)), encoding="utf-8")
    manifest = root / "project.yaml"
    text = manifest.read_text(encoding="utf-8")
    cut = text.find("\nshape:\n")
    if cut >= 0:
        text = text[:cut + 1]
    manifest.write_text(text + SHAPE_MIRROR_YAML.format(
        source=SHAPE_SOURCE, commit=mirror or commit, tree=tree),
        encoding="utf-8")
    commit_all(root, "pin the shape")
    if push:
        git("push", "-q", "origin", "main", cwd=root)


COPIES = {"Makefile": ".PHONY: park\npark:\n\t@echo park\n",
          "scripts/validate-pins.py": "#!/usr/bin/env python3\nprint('ok')\n"}


def test_a_pinned_root_with_matching_copies_says_so_and_names_what_it_did_not_read(
        atlas, home, status_remotes):
    """The note line every pinned root gets: what is pinned, how many copies
    match, and — with no clone of the standard here and no `--fetch` — that
    currency was NOT read, so "no finding" is never mistaken for "current"."""
    standard = fake_standard(status_remotes["base"])
    pin_shape(atlas, standard["shas"][-1], COPIES)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (f"    shape: pinned at {standard['shas'][-1][:7]} of {SHAPE_SOURCE}; "
            f"2/2 copies match their digests; currency not read (no clone of "
            f"{SHAPE_SOURCE} with its default branch fetched under the projects "
            f"directory; --fetch asks GitHub)") in result.stdout
    assert "in sync with origin/main; clean" in result.stdout


def test_an_edited_or_missing_copy_is_drift(atlas, home, status_remotes):
    standard = fake_standard(status_remotes["base"])
    pin_shape(atlas, standard["shas"][-1], COPIES)
    (atlas / "Makefile").write_text("# edited in place\n", encoding="utf-8")
    (atlas / "scripts" / "validate-pins.py").unlink()
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - shape copy Makefile edited in place: its sha256 is not the one "
            "contracts/shape-pin.yaml records (drift: carry the change upstream, "
            "never re-digest)") in result.stdout
    assert ("    - shape copy scripts/validate-pins.py is missing; "
            "contracts/shape-pin.yaml names it (update-shape.py check --root "
            f"{atlas})") in result.stdout
    assert "0/2 copies match their digests" in result.stdout
    assert "dirty: 2 path(s)" in result.stdout, "the edits are dirty paths too, read as before"


def test_a_mirror_naming_another_commit_is_out_of_step(atlas, home,
                                                        status_remotes):
    standard = fake_standard(status_remotes["base"])
    pin_shape(atlas, standard["shas"][-1], COPIES, mirror=standard["shas"][0])
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - shape: project.yaml mirrors {standard['shas'][0][:7]} but "
            f"contracts/shape-pin.yaml pins {standard['shas'][-1][:7]}: out of "
            "step (update-shape.py moves both together)") in result.stdout


def test_the_pin_is_read_against_a_clone_of_the_standard_under_projects(
        atlas, home, status_remotes):
    """Local refs, no network: a clone of the standard under the projects
    directory, found by its origin's slug, says the pin is behind — or not on
    `main` at all."""
    standard = fake_standard(status_remotes["base"])
    clone = standard_clone(home, standard["bare"])
    pin_shape(atlas, standard["shas"][0], COPIES)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - shape pin {standard['shas'][0][:7]} is 2 commit(s) behind "
            f"{SHAPE_SOURCE} main (per the clone at {clone}, as of its last "
            f"fetch): update-shape.py check --root {atlas}") in result.stdout
    assert f"against {SHAPE_SOURCE} main per a clone under the projects directory" \
        in result.stdout
    assert "currency not read" not in result.stdout

    git("checkout", "-q", "main", cwd=atlas)
    pin_shape(atlas, standard["shas"][-1], COPIES)
    current = run(STATUS, "Atlas", home=home)
    assert current.returncode == 0, current.stdout + current.stderr
    assert "shape pin" not in current.stdout, "at main's tip there is nothing to say"

    pin_shape(atlas, standard["branch_sha"], COPIES)
    orphan = run(STATUS, "Atlas", home=home)
    assert orphan.returncode == 1, orphan.stdout + orphan.stderr
    assert (f"    - shape pin {standard['branch_sha'][:7]} is not on {SHAPE_SOURCE} "
            f"main (per the clone at {clone}): a branch commit, which the "
            "standard's squash-merge orphans") in orphan.stdout


def test_under_fetch_with_no_clone_github_is_asked_once_about_the_pin(
        atlas, home, status_remotes, tmp_path):
    """No clone of the standard here: under `--fetch` the fake `gh` answers
    the compare (0 behind, 4 ahead of the pin), the finding names the exit,
    and without `--fetch` nothing is asked."""
    standard = fake_standard(status_remotes["base"])
    pin_shape(atlas, standard["shas"][0], COPIES)
    env, log = fake_gh(tmp_path)
    plain = run(STATUS, "Atlas", home=home, env=env)
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert not log.exists(), "without --fetch, gh must not be asked"
    assert "currency not read" in plain.stdout

    fetched = run(STATUS, "--fetch", "Atlas", home=home, env=env)
    assert fetched.returncode == 1, fetched.stdout + fetched.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls == [
        f"api repos/{SHAPE_SOURCE} --hostname github.com "
        "--jq .default_branch // \"main\"",
        f"api repos/{SHAPE_SOURCE}/compare/{standard['shas'][0]}...main?per_page=1 "
        "--hostname github.com "
        "--jq [(.behind_by|tostring), (.ahead_by|tostring)] | join(\"\\u001f\")",
    ], calls
    assert (f"    - shape pin {standard['shas'][0][:7]} is 4 commit(s) behind "
            f"{SHAPE_SOURCE} main (per GitHub): update-shape.py check --root "
            f"{atlas}") in fetched.stdout
    assert f"against {SHAPE_SOURCE} main per GitHub" in fetched.stdout


def test_a_clone_of_the_standard_is_read_before_github_even_under_fetch(
        atlas, home, status_remotes, tmp_path):
    """The documents promise the clone first and GitHub only when no clone
    answered — and the first draft did the reverse under `--fetch`, spending
    a round-trip, and a strike against gh's budget, on a question the clone
    beside it could answer for free."""
    standard = fake_standard(status_remotes["base"])
    standard_clone(home, standard["bare"])
    pin_shape(atlas, standard["shas"][0], COPIES)
    env, log = fake_gh(tmp_path)
    result = run(STATUS, "--fetch", "Atlas", home=home, env=env)
    assert result.returncode == 1, result.stdout + result.stderr
    assert not log.exists(), "the clone answered; GitHub must not be asked"
    assert "per a clone under the projects directory" in result.stdout
    assert " is 2 commit(s) behind " in result.stdout


def test_one_pin_on_two_roots_is_one_question_to_github(home, status_remotes,
                                                         tmp_path):
    """A family's holder and members are cut from the same commit. Asking
    GitHub once per root would be N round-trips and N strikes against the
    budget the fork check shares; the answer about a pin serves every root
    that carries it, while each root still names its own `--root`."""
    standard = fake_standard(status_remotes["base"])
    atlas = clone_root(home, status_remotes["Atlas"], "Atlas")
    borealis = clone_root(home, status_remotes["Atlas"], "Borealis")
    pin_shape(atlas, standard["shas"][0], COPIES)
    pin_shape(borealis, standard["shas"][0], COPIES, push=False)
    env, log = fake_gh(tmp_path)
    result = run(STATUS, "--all", "--fetch", home=home, env=env)
    assert result.returncode == 1, result.stdout + result.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 2, calls
    assert calls[0].startswith(f"api repos/{SHAPE_SOURCE} --hostname")
    assert "/compare/" in calls[1]
    for root in (atlas, borealis):
        assert (f"is 4 commit(s) behind {SHAPE_SOURCE} main (per GitHub): "
                f"update-shape.py check --root {root}") in result.stdout


def test_a_404_on_the_shape_question_leaves_the_fork_check_asked(
        atlas, home, status_remotes, tmp_path):
    """The shape check's own failure is said on its row, and the leg's fork
    check beside it is still asked — one failure is not a settled run."""
    standard = fake_standard(status_remotes["base"])
    pin_shape(atlas, standard["shas"][0], COPIES)
    github_origin(atlas / "spec", status_remotes["Atlas"]["leg_bare"],
                  "testorg/Atlas-spec")
    env, log = fake_gh(tmp_path, not_found_prefix=SHAPE_SOURCE)
    result = run(STATUS, "--fetch", "Atlas", home=home, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (f"    shape check: `gh api repos/{SHAPE_SOURCE}` failed (gh: Not Found "
            "(HTTP 404)); the other repositories are still asked") in result.stdout
    assert ("currency NOT read: no clone of opensoft/openRepoShape with its "
            "default branch fetched under the projects directory, and GitHub "
            "did not answer (an earlier line says why)") in result.stdout
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 2, calls
    assert calls[1].startswith("api repos/testorg/Atlas-spec "), (
        "the leg's fork check was still asked")


def test_a_manifest_without_a_shape_mirror_is_out_of_step(atlas, home,
                                                          status_remotes):
    """`update-shape.py` refuses a manifest with no `shape:` block, so a pin
    beside one is the same half-done state as two different commits."""
    standard = fake_standard(status_remotes["base"])
    pin_shape(atlas, standard["shas"][-1], COPIES)
    manifest = atlas / "project.yaml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text[:text.index("\nshape:\n") + 1], encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - shape: project.yaml carries no `shape:` commit beside "
            "contracts/shape-pin.yaml (update-shape.py moves both together)"
            ) in result.stdout


@NEEDS_UPSTREAM
def test_a_family_holder_reads_its_pin_and_the_mirror_in_family_yaml(estate,
                                                                    home):
    """The holder arm: the same pin, the mirror read out of `family.yaml`
    rather than `project.yaml`. The holder here is the real family-root
    template's clone, which carries no pin; one is written with a mirror
    naming another commit, and the out-of-step finding names family.yaml."""
    import hashlib
    holder = estate["holder"]
    (holder / "contracts").mkdir(exist_ok=True)
    copy = holder / "scripts" / "validate-family.py"
    copy.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    digest = hashlib.sha256(copy.read_bytes()).hexdigest()
    pinned, mirrored = "1" * 40, "2" * 40
    (holder / "contracts" / "shape-pin.yaml").write_text(
        SHAPE_PIN_YAML.format(source=SHAPE_SOURCE, commit=pinned, tree="0" * 64,
                              rows=f"  - path: scripts/validate-family.py\n"
                                   f"    sha256: \"{digest}\""),
        encoding="utf-8")
    family_yaml = holder / "family.yaml"
    family_yaml.write_text(
        family_yaml.read_text(encoding="utf-8") + SHAPE_MIRROR_YAML.format(
            source=SHAPE_SOURCE, commit=mirrored, tree="0" * 64),
        encoding="utf-8")
    result = run(STATUS, FAMILY, home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    shape: pinned at {pinned[:7]} of {SHAPE_SOURCE}; 1/1 copies "
            "match their digests") in result.stdout
    assert (f"    - shape: family.yaml mirrors {mirrored[:7]} but "
            f"contracts/shape-pin.yaml pins {pinned[:7]}: out of step "
            "(update-shape.py moves both together)") in result.stdout
    assert result.stdout.count("    shape:") == 1, (
        "the members carry no pin and say nothing about one")


def test_a_tracking_branch_no_remote_has_is_named_after_the_fetch(
        atlas, home, status_remotes):
    """Three lines the first draft could print wrongly: a fetch of a remote
    with no such branch says so rather than "nothing new"; and with upstream
    fetched and lacking it, the fork line says "after the fetch", not "never
    fetched (--fetch asks it)"."""
    parent = parent_ahead(status_remotes["base"], status_remotes["Atlas"],
                          "nodevelop")
    git("remote", "add", "upstream", str(parent), cwd=atlas)
    manifest = atlas / "project.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "tracking_branch: main", "tracking_branch: develop"), encoding="utf-8")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    fetched origin: there is no origin/develop" in result.stdout
    assert "    fetched upstream: there is no upstream/develop" in result.stdout
    assert ("    - fork: no upstream/develop after the fetch: upstream has no "
            "branch develop") in result.stdout
    assert "nothing new on origin/develop" not in result.stdout
    assert "never fetched" not in result.stdout


def test_a_failed_upstream_fetch_is_not_blamed_on_the_person(atlas, home):
    git("remote", "add", "upstream", str(home / "nowhere" / "parent.git"),
        cwd=atlas)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    - fetch upstream failed: " in result.stdout
    assert ("    - fork: no upstream/main here, and the fetch of upstream above "
            "did not bring one") in result.stdout
    assert "--fetch` asks it" not in result.stdout


def test_a_root_without_a_shape_pin_says_nothing_about_one(atlas, home):
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "    shape:" not in result.stdout
    assert "shape pin" not in result.stdout
    assert "shape copy" not in result.stdout


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
