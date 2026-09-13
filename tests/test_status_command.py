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

His RULING of 2026-09-11, verbatim: "next layer: parked record against disk".
`park` records every open feature in the private workspace repository that
`~/.agents/workspace.yaml` names, and `resume` rebuilds worktrees from it; the
fifth section holds the ways record and disk drift apart, read the way
`resume.sh` will judge them: a recorded feature with no worktree here, a
worktree whose tip moved on from, fell behind, or diverged from the parked
commit, a leg parked with `--no-push` — or one whose `pushed:` is missing or
neither true nor false, which `resume` refuses just as flatly — a worktree
the record does not know, and a family's record matched to each member by its
`root:`.
The config and the workspace checkout are plain files under the fake home;
nothing is pulled.

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
    ORG, MEMBERS, FAMILY, FAKE_SHA, commit_all, estate, family_manifest,
    remotes, run, probe_project,
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


#: A root `load_repo_shape` calls THREE-LEG, which is four conditions and not
#: one: `kind: project-manifest`, `schema: project-repo-schema`, and BOTH a
#: `spec` and a `code` leg declared. `ROOT_WITH_LEG_YAML` above is the other
#: shape — no `schema:` line, no `code` leg — which is `single` however many
#: legs it mounts, and `resume` maps only a `repo` leg onto it.
THREE_LEG_YAML = """\
schema_version: 1
kind: project-manifest
schema: project-repo-schema
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
  - role: code
    repository: {org}/{name}-code
    path: code
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


def seed_three_leg_root(base: Path, name: str) -> dict:
    """Bare remotes for a root of the OTHER shape: two legs, both mounted as
    submodules, and a `project.yaml` that satisfies every condition
    `load_repo_shape` puts on `three-leg`. Built here rather than shared with
    `seed_root_with_leg` because the two exist to differ."""
    bares = {}
    for role in ("spec", "code"):
        seed = base / "seed" / f"{name}-{role}"
        seed.mkdir(parents=True)
        (seed / f"{role}.md").write_text(f"# the {role} leg\n", encoding="utf-8")
        git("init", "-q", "-b", "main", ".", cwd=seed)
        commit_all(seed, f"the {role} leg")
        bares[role] = base / "remotes" / f"{name}-{role}.git"
        bares[role].parent.mkdir(parents=True, exist_ok=True)
        git("clone", "-q", "--bare", str(seed), str(bares[role]), cwd=base)

    seed = base / "seed" / name
    seed.mkdir(parents=True)
    (seed / "project.yaml").write_text(
        THREE_LEG_YAML.format(id=name.lower(), name=name, org=ORG),
        encoding="utf-8")
    (seed / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    # A three-leg root's `worktree_root` is `worktrees` INSIDE it, so the
    # feature worktrees `park` and `resume` make show in the root's own `git
    # status` unless it ignores them: `setup-openspeckit` writes the line, and
    # `resume.sh` warns where it is missing ("'…/.gitignore' does not ignore
    # /worktrees/; the recreated worktrees will show in `git status` at the
    # root"). A fixture without it would report dirt no real root has.
    (seed / ".gitignore").write_text("worktrees/\n", encoding="utf-8")
    git("init", "-q", "-b", "main", ".", cwd=seed)
    commit_all(seed, "seed")
    for role in ("spec", "code"):
        git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
            str(bares[role]), role, cwd=seed)
    commit_all(seed, "the legs, pinned")
    bare = base / "remotes" / f"{name}.git"
    git("clone", "-q", "--bare", str(seed), str(bare), cwd=base)
    return {"bare": bare, "spec_bare": bares["spec"], "code_bare": bares["code"]}


@pytest.fixture
def trio(home, tmp_path) -> Path:
    """A THREE-LEG estate under the fake projects directory, both legs
    mounted — the shape `resume` maps `spec` and `code` onto, and the one it
    refuses a `repo` leg in."""
    base = tmp_path / "trio-remotes"
    base.mkdir()
    return clone_root(home, seed_three_leg_root(base, "Trio"), "Trio")


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


def test_a_leftover_directory_under_the_root_is_not_read_as_a_worktree(
        atlas, home):
    """The extension puts feature worktrees UNDER the root, so a registered
    path whose `.git` is gone is a plain directory inside the root's own
    working tree. `git status` there finds no repository, walks UP, and hands
    back the ROOT's dirty paths — which this layer would print on that
    worktree's row, under a branch that has nothing to do with them. A
    worktree is a directory with its own `.git`, the rule the record layer
    and its sweep apply, and this reader applies it too."""
    where = atlas / "worktrees" / "001-a-thing"
    feature_worktree(atlas, "001-a-thing", where)
    (where / ".git").unlink()       # the directory stays, inside the root
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "dirty" in result.stdout, "the root itself is dirty: the leftover"
    assert "on 001-a-thing: dirty" not in result.stdout, (
        "the root's own dirty paths, reported on the worktree's row")


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


def test_a_leg_whose_submodule_name_carries_a_space_is_one_leg_and_a_valueless_key_none(
        atlas, home):
    """`.gitmodules` read with `git config -z`: the leg under
    `[submodule "sp ace"]` is still the one leg at `spec`, and a key with no
    value beside it is not a phantom leg declared and never mounted."""
    git("config", "--file", ".gitmodules", "--rename-section",
        "submodule.spec", "submodule.sp ace", cwd=atlas)
    with (atlas / ".gitmodules").open("a", encoding="utf-8") as handle:
        handle.write('[submodule "empty"]\n\tpath\n')
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr  # .gitmodules is dirty
    assert result.stdout.count("  leg    main   ") == 1, result.stdout
    assert f"  leg    main   {atlas / 'spec'}" in result.stdout
    assert "ace.path" not in result.stdout
    assert "submodule.empty.path" not in result.stdout
    assert "declared in .gitmodules and not mounted" not in result.stdout


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
    # AN EMPTY VALUE IS THE SAME REFUSAL, and these two arms never went
    # through `${2:?…}` at all: they have been arity-only since this file's
    # first commit, so Copilot's review of #14 — which caught exactly this in
    # `park` and `resume`, where `[ $# -ge 2 ]` had just replaced `${2:?…}` —
    # never had `status` in front of it. RUN FROM INSIDE THE ESTATE, which is
    # what makes it bite: before the fix the empty slug fell past the
    # `--repo` branch of the resolver into the walk-up, and Atlas was read
    # and reported as though `--repo` had never been typed. Nothing is
    # printed at all now — the refusal is raised in the argument loop, before
    # the estate is resolved and before the first `say` — so an empty stdout
    # is the proof that the fallback was never reached.
    empty = [(flag, run(STATUS, flag, "", home=home, cwd=atlas))
             for flag in ("--repo", "--name", "--project")]
    for flag, result in empty:
        assert result.returncode == 2, result.stdout + result.stderr
        assert f"REFUSED: {flag} needs a value" in result.stderr
        assert "${2:?" not in result.stderr
        assert "parameter null or not set" not in result.stderr
        assert "line " not in result.stderr, "bash's own message leaked"
        assert result.stdout == "", (
            "nothing may be resolved, said or read before an empty value is "
            f"refused; stdout was {result.stdout!r}")
    for result in (both, unknown, nope, valueless, *(r for _, r in empty)):
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
    # EVERY FETCH IS MADE BEFORE ANY ROW IS PRINTED, and each row still
    # carries its own fetch's line and its own fetch's finding: the failure
    # belongs to the root, the "nothing new" to the leg.
    root_block, _, leg_block = result.stdout.partition("  leg    main")
    assert "    - fetch failed: " in root_block
    assert "    fetched origin: nothing new on origin/main" in leg_block, (
        "the leg's fetch still ran, and its line is on the leg's row")
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


# --- the parked record against disk ---------------------------------------------
#
# Brett Heap's RULING of 2026-09-11, verbatim: "next layer: parked record
# against disk".

def workspace_config(home: Path) -> Path:
    """`~/.agents/workspace.yaml` naming a workspace checkout under the fake
    home — a plain directory: `status` reads it and never pulls it."""
    checkout = home / "wip"
    (checkout / "workspaces" / ORG).mkdir(parents=True, exist_ok=True)
    agents = home / ".agents"
    agents.mkdir(exist_ok=True)
    (agents / "workspace.yaml").write_text(
        f"repository: tester/wip\npath: {checkout}\n", encoding="utf-8")
    return checkout


def record(checkout: Path, project_id: str, *, branch: str, role: str,
           commit: str, pushed: str | None = "true", parked_on: str = "Eagle",
           root: str | None = None, org: str = ORG, wip_depth: int = 1) -> Path:
    """One standalone record as `park.sh` writes one: one project, one
    feature, one leg. `commit=""` leaves the `parked_commit:` key out, as
    `park.sh` leaves out any key whose value is empty; `pushed=None` leaves
    the `pushed:` KEY out the same way — which is what
    `workspace_write_manifest` does with an empty value, and what a hand-edit
    or a bad merge of the record leaves behind."""
    root = root or project_id.capitalize()
    commit_line = f"            parked_commit: {commit}\n" if commit else ""
    pushed_line = "" if pushed is None else f"            pushed: {pushed}\n"
    text = f"""\
schema_version: 1
kind: workspace-manifest
written_by: speckit park
projects:
  - id: {project_id}
    repository: {org}/{root}
    shape: three-leg
    root: {root}
    tracking_branch: main
    worktree_root: worktrees
    parked_at: 2026-09-10T20:00:00Z
    parked_on: {parked_on}
    parked_by_lane: xfactory-2
    active_feature: {branch}
    active_feature_source: state_file
    features:
      - branch: {branch}
        feature_directory: worktrees/{branch}
        legs:
          - role: {role}
            remote: origin
{commit_line}            wip: true
            wip_depth: {wip_depth}
{pushed_line}"""
    (checkout / "workspaces" / org).mkdir(parents=True, exist_ok=True)
    path = checkout / "workspaces" / org / f"{project_id}.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def parked_worktree(root: Path, branch: str, mount: str | None = None) -> Path:
    """THE ONE PATH `resume.sh` READS AS A FEATURE'S WORKTREE, and the one
    `park.sh` collects features from: `collect_legs` computes
    `<worktree_root>/<branch>` for a single root's `repo` leg and
    `<worktree_root>/<branch>/<leg mount>` for a three-leg one, and
    `get_config_value`'s default for `worktree_root` is `../<root
    folder>-worktrees` BESIDE a single root and `worktrees` INSIDE a three-leg
    one — these fixtures carry no `.specify/extensions/git/git-config.yml` to
    say otherwise. A worktree anywhere else is one neither verb sees, which is
    a finding of its own; every fixture below that means "the worktree `park`
    made" therefore puts it here."""
    if mount is None:
        return root.parent / f"{root.name}-worktrees" / branch
    return root / "worktrees" / branch / mount


def feature_worktree(repo: Path, branch: str, where: Path, *, push: bool = True) -> str:
    """A linked worktree on a new branch with one commit, pushed so the branch
    itself is not a finding; returns the tip sha."""
    where.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "-b", branch, str(where), cwd=repo)
    (where / "feature.md").write_text("wip\n", encoding="utf-8")
    commit_all(where, "feature work")
    if push:
        git("push", "-q", "-u", "origin", branch, cwd=where)
    return git("rev-parse", "HEAD", cwd=where).stdout.strip()


RECORD_NOTE_NONE = "parked record: none for 'atlas' under"


def origin_has_branch(repo: Path, branch: str, at: str = "main") -> None:
    """The branch ON ORIGIN, with a remote-tracking ref for it here and no
    worktree and no local branch: what a `park` on another workstation leaves
    behind for this one, and what `resume.sh`'s RR2 looks for before it
    recreates anything. Every record whose feature is meant to be RESUMABLE
    here needs it — since the reading below, a leg whose repository has no
    `origin/<branch>` is a leg `resume` may refuse instead."""
    git("push", "-q", "origin", f"{at}:refs/heads/{branch}", cwd=repo)
    git("fetch", "-q", "origin", cwd=repo)


def drop_from_origin(repo: Path, branch: str) -> None:
    """The branch deleted where origin keeps it — a feature that landed, or a
    branch deleted by mistake — and pruned here, which is the state `resume`
    refuses at RR2."""
    git("push", "-q", "origin", "--delete", branch, cwd=repo)
    git("fetch", "-q", "--prune", "origin", cwd=repo)



def test_no_workspace_config_is_a_note_not_a_finding(atlas, home):
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (f"  parked record: no {home}/.agents/workspace.yaml on this machine, "
            "so parked features are not read (`resume --workspace "
            "<owner>/<repo>` writes it)") in result.stdout


def test_no_record_for_the_estate_is_a_note(atlas, home):
    checkout = workspace_config(home)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"  {RECORD_NOTE_NONE} {checkout}" in result.stdout
    assert "nothing of this estate has been parked" in result.stdout


def test_a_recorded_feature_with_no_worktree_here_names_resume(atlas, home):
    checkout = workspace_config(home)
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"  parked record: {path}, as of its last pull" in result.stdout
    assert ("    parked record: 1 feature(s), parked 2026-09-10T20:00:00Z on "
            "Eagle (lane xfactory-2); active 001-a-thing") in result.stdout
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here; parked 2026-09-10T20:00:00Z on Eagle — `resume Atlas` "
            "brings it back") in result.stdout
    assert "1 finding(s) in 2 repositories" in result.stdout


def test_a_worktree_at_the_parked_commit_is_in_sync(atlas, home):
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "    parked record: 1 feature(s)" in result.stdout
    assert "parked feature" not in result.stdout


def test_a_recorded_features_deleted_worktree_names_the_prune_then_the_resume(
        atlas, home):
    """`worktree list --porcelain` keeps the block of a linked worktree whose
    directory was deleted until somebody runs `git worktree prune`. Read as a
    worktree, the recorded feature sat at the parked commit and was therefore
    reported CLEAN — the one answer that hides the case this layer exists for.

    And the registration that is left is not nothing: `resume.sh` matches a
    leg on the registered PATH alone, so it reads that block as already done
    and recreates nothing, or has its `git worktree add` refused for a path
    git still holds. So the prune comes first and the `resume` second, and
    the bare line — which names an exit that cannot run — never appears."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    rmtree(where)           # and NO `git worktree prune`
    porcelain = git("worktree", "list", "--porcelain", cwd=atlas).stdout
    assert "001-a-thing" in porcelain, "git pruned it for us; the test is moot"
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            f"branch here, but a stale worktree registration for it is still "
            f"recorded at {where} — clear it with `git -C {atlas} worktree "
            "prune`, then `resume Atlas` brings it back") in result.stdout
    assert "no worktree on that branch here; parked" not in result.stdout


def test_a_worktree_that_moved_on_since_it_was_parked(atlas, home):
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    (where / "more.md").write_text("more\n", encoding="utf-8")
    commit_all(where, "more work")
    git("push", "-q", "origin", "001-a-thing", cwd=where)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): moved on since it was "
            f"parked, 1 commit(s) after {tip[:7]} — park again before leaving"
            ) in result.stdout


def test_a_worktree_behind_a_newer_record_is_what_resume_refuses(atlas, home):
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    feature_worktree(atlas, "001-a-thing", where)
    (where / "more.md").write_text("more\n", encoding="utf-8")
    commit_all(where, "parked elsewhere, later")
    git("push", "-q", "origin", "001-a-thing", cwd=where)
    newer = git("rev-parse", "HEAD", cwd=where).stdout.strip()
    git("reset", "-q", "--hard", "HEAD~1", cwd=where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=newer,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): this worktree is BEHIND "
            f"the parked commit {newer[:7]}, parked 2026-09-10T20:00:00Z on "
            "Falcon — the record is newer, and `resume` refuses to reset it"
            ) in result.stdout


# --- the path `resume` computes, and no other ------------------------------
#
# The independent reviewer's note of 2026-09-12, verbatim: "`worktree_on_branch`
# (in `status`) matches any path while RR4 matches only the computed one."

def path_finding(root, branch: str, at, want, wtroot, repo=None) -> str:
    """The one line the reading below prints, for a LINKED worktree.

    IT NAMES THE OUTCOME AND NOT THE CHECK since the independent review of
    this branch, 2026-09-12: "`resume.sh` only reaches that `worktree add`
    when the leg also clears RR3, RR2, RR1 and RR5." Run against the real
    `resume.sh` on four twin estates the same day, an off-path worktree at
    the parked commit is refused at the `git worktree add` ("already used by
    worktree at …"); moved on it is RR1's divergence, behind it is RR5, and
    with the branch gone from origin it is RR2 — the same whole-feature
    refusal and the same exit in all of them, and a quoted sentence the
    other end does not print in four of the five. So the line says what
    `resume` does, and keeps the quoted `worktree add` for the state that
    prints it."""
    repo = repo or root
    return (f"    - parked feature {branch} (repo leg): its worktree is at "
            f"{at}, which is not the {want} `resume` computes for it — "
            "`resume` matches a leg's worktree on that path alone, so it does "
            "not read this one as already recreated and refuses the WHOLE "
            "feature, the other legs with it, at whichever of its own checks "
            "this leg reaches first (with the branch still at the parked "
            "commit that is the `git worktree add` it makes last of all, "
            "which cannot take a branch another worktree holds); `park` does "
            "not carry it either, because it parks the features under "
            f"{wtroot} and no others — move it where both "
            f"look: `mkdir -p {Path(want).parent} && git -C {repo} worktree "
            f"move {at} {want}`, which is yours to run — `worktree move` "
            "creates no parent directory of its own")


def test_a_worktree_off_the_computed_path_is_a_finding_not_silence(atlas, home):
    """VERIFIED AGAINST THE EXTENSION on 2026-09-12, on a scratch single-shape
    estate with the real scripts: with the worktree on the branch at
    `$HOME/elsewhere/001-a-thing` rather than `worktrees/001-a-thing`, and the
    record's `pushed: true` and its parked commit origin's tip, `resume.sh`
    answered "Error: could not add the repo leg worktree
    'worktrees/001-a-thing' for '001-a-thing'; that feature was NOT recreated.
    / fatal: '001-a-thing' is already used by worktree at
    '…/elsewhere/001-a-thing'", "REFUSED: 001-a-thing — git worktree add
    failed", exit 2 — while `status` answered "0 finding(s) in 1 repository",
    exit 0. The feature read as CLEAN AND PRESENT, which is the one answer
    that hides the state this layer exists for: RR4 matches a leg on the
    registered PATH alone, and a worktree at any other path is not that leg's."""
    checkout = workspace_config(home)
    where = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path_finding(atlas, "001-a-thing", where,
                        parked_worktree(atlas, "001-a-thing"),
                        home / "projects" / "Atlas-worktrees") in result.stdout


def test_the_path_reading_ends_the_leg_because_park_is_blind_to_it_too(
        atlas, home):
    """Every arm below that one exits through "park again", and `park.sh`
    collects a single checkout's features through `verify_git_worktree_candidate
    "$REPO_ROOT" "$WORKTREE_ROOT" …`, which drops every worktree outside that
    root: run on the same scratch estate the same day, `park --dry-run`
    answered "[specify] No open features under 'worktrees'; nothing to park.",
    and answered "PARKED: 001-a-thing" with the worktree at the computed path.
    So the moved-on line, whose exit is exactly that park, must not follow
    it — and what it would have said is said on the run after the move."""
    checkout = workspace_config(home)
    where = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    (where / "more.md").write_text("more\n", encoding="utf-8")
    commit_all(where, "more work")
    git("push", "-q", "origin", "001-a-thing", cwd=where)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path_finding(atlas, "001-a-thing", where,
                        parked_worktree(atlas, "001-a-thing"),
                        home / "projects" / "Atlas-worktrees") in result.stdout
    assert "moved on since it was parked" not in result.stdout


def test_the_worktree_root_in_git_config_moves_the_path_both_verbs_use(
        atlas, home):
    """`worktree_root:` in `.specify/extensions/git/git-config.yml` is where
    the other end gets it — `get_config_value "worktree_root"
    "$DEFAULT_WORKTREE_ROOT" "SPECKIT_GIT_WORKTREE_ROOT"` — taking the LAST
    line for the key, stripping a `#` comment only where whitespace comes
    first, and unquoting. So the DEFAULT path is the wrong one here, and the
    configured one is right: both halves are run, and the `worktree move`
    between them is the very command the finding names."""
    checkout = workspace_config(home)
    config = atlas / ".specify" / "extensions" / "git" / "git-config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("checkout_mode: worktree\n"
                      'worktree_root: "wt"   # beside the legs\n',
                      encoding="utf-8")
    where = parked_worktree(atlas, "001-a-thing")       # the DEFAULT path
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path_finding(atlas, "001-a-thing", where,
                        atlas / "wt" / "001-a-thing",
                        atlas / "wt") in result.stdout
    (atlas / "wt").mkdir()      # `worktree move` creates no parent
    git("worktree", "move", str(where), str(atlas / "wt" / "001-a-thing"),
        cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert "parked feature" not in result.stdout, result.stdout
    assert "    parked record: 1 feature(s)" in result.stdout


def test_the_environment_override_moves_that_path_too(atlas, home):
    """`get_config_value` reads `$SPECKIT_GIT_WORKTREE_ROOT` BEFORE the config
    file and before the default, so a person who runs `park` and `resume` with
    it set has their worktrees somewhere else entirely. One estate, two runs:
    without the variable the worktree is off the path, with it the same
    worktree IS the path, and nothing on disk moved between them."""
    checkout = workspace_config(home)
    where = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path_finding(atlas, "001-a-thing", where,
                        parked_worktree(atlas, "001-a-thing"),
                        home / "projects" / "Atlas-worktrees") in result.stdout
    result = run(STATUS, "Atlas", home=home,
                 env={"SPECKIT_GIT_WORKTREE_ROOT": str(home / "elsewhere")})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "parked feature" not in result.stdout


def test_a_three_leg_legs_worktree_is_judged_under_its_own_mount(trio, home):
    """`collect_legs` computes `$WORKTREE_ROOT/$branch/$SHAPE_SPEC_PATH` for a
    `spec` leg, so the feature directory itself is not that leg's worktree —
    and a three-leg root's `worktree_root` defaults to `worktrees` INSIDE it,
    not to the `../<folder>-worktrees` a single root gets."""
    checkout = workspace_config(home)
    leg = trio / "spec"
    git("checkout", "-q", "main", cwd=leg)
    where = trio / "worktrees" / "001-s-thing"
    tip = feature_worktree(leg, "001-s-thing", where)
    record(checkout, "trio", branch="001-s-thing", role="spec", commit=tip,
           root="Trio", parked_on="Falcon")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-s-thing (spec leg): its worktree is at "
            f"{where}, which is not the {where / 'spec'} `resume` computes "
            "for it — ") in result.stdout
    assert f"worktree move {where} {where / 'spec'}`" in result.stdout


def test_the_legs_own_checkout_on_that_branch_names_no_worktree_move(
        atlas, home):
    """`worktree_on_branch` answers with the MAIN worktree too, and `git
    worktree move` refuses one: "'…' is a main working tree" (git 2.43,
    2026-09-12). Naming it would be naming an exit that does not work, which
    is the one thing the rule at the top of `check_parked_leg` forbids — and
    `resume` refuses a root on a feature branch in any case, which the row
    above says in the local layer's own words."""
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    git("worktree", "remove", str(parked_worktree(atlas, "001-a-thing")),
        cwd=atlas)
    git("checkout", "-q", "001-a-thing", cwd=atlas)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its worktree is at "
            f"{atlas}, which is not the "
            f"{parked_worktree(atlas, '001-a-thing')} `resume` computes for "
            "it — ") in result.stdout
    assert (f"and no others — {atlas} is the repo leg's OWN checkout rather "
            "than a worktree of it, and no `worktree move` moves a main "
            "working tree, so there is nothing here to move: neither verb "
            "sees this feature while that checkout is on that branch"
            ) in result.stdout
    assert "worktree move" in result.stdout
    assert f"worktree move {atlas}" not in result.stdout


def test_a_feature_resume_refuses_whole_says_nothing_about_the_path(
        atlas, home):
    """The rule the verdict already carries: no line of a feature
    `collect_legs` throws out may claim a refusal reached later. RR4 is never
    reached for one, so the leg's own path is not what stops it, and the
    feature's line — the one that names the leg that costs it — is the whole
    answer."""
    checkout = workspace_config(home)
    where = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", where)
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=tip)
    text = path.read_text(encoding="utf-8")
    path.write_text(text + "          - role: nope\n"
                    "            remote: origin\n"
                    f"            parked_commit: {tip}\n"
                    "            wip: true\n"
                    "            wip_depth: 1\n"
                    "            pushed: true\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (nope leg): the record names a "
            "leg this root does not mount here; `resume` maps each leg's role "
            "onto this checkout and refuses the WHOLE feature") in result.stdout
    assert "which is not the" not in result.stdout
    assert "1 finding(s)" in result.stdout


def test_a_symlinked_spelling_of_the_root_is_the_path_git_spells(atlas, home):
    """The independent review of this branch, 2026-09-12, its first blocker,
    verbatim: "`$root` is the estate path as `estate_walk_up "$PWD"` /
    `$PROJECTS_DIRS` spell it — LEXICAL, symlinks intact. `$tree` is
    `worktree_on_branch`'s answer, which comes from `git worktree list
    --porcelain` and is ALWAYS the physical path. `resume.sh` sets
    `REPO_ROOT="$(git rev-parse --show-toplevel)"`, which is also always
    physical."

    RUN BOTH WAYS ON ONE ESTATE the same day, with the worktree AT the
    computed path and nothing differing but the SPELLING of the projects
    directory — a symlink to the very same directory. `resume.sh`, run from
    the symlinked spelling, answered "[specify] 001-a-thing (repo): worktree
    already registered at worktrees/001-a-thing; left as it is", "RESUMED:
    001-a-thing", exit 0; this layer answered "a directory is at
    …/proj-link/Atlas-worktrees/001-a-thing, which is the path `resume`
    computes for this leg", refused the WHOLE feature and named an `mv` of
    the feature's own worktree — because `[ -e ]` follows the link where an
    exact-string match of the registered paths cannot. A healthy feature read
    as somebody else's obstruction is the worst answer this arm has.

    THE ROOT IS RESOLVED AS FAR AS GIT RESOLVES IT AND NO FURTHER, which is
    the test below this one."""
    checkout = workspace_config(home)
    at = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", at)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "parked feature" not in result.stdout
    link = home / "proj-link"
    link.symlink_to(home / "projects", target_is_directory=True)
    result = run(STATUS, "Atlas", home=home, env={"PROJECTS_DIR": str(link)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "parked feature" not in result.stdout
    assert f"root   main   {link / 'Atlas'}" in result.stdout


def test_a_symlinked_worktree_root_is_a_miss_at_both_ends(atlas, home):
    """AND NO FURTHER THAN GIT, which is the other half of the blocker above:
    `get_config_value` does not resolve `worktree_root:` and
    `resolve_path_from_repo_root` is `os.path.abspath`, which resolves no
    symlink either. So where the WORKTREE ROOT is a symlink `collect_legs`
    computes the unresolved path, `git worktree list` reports the resolved
    one, and RR4 misses at the other end exactly as it misses here.

    Run against the extension on 2026-09-12 with `worktree_root: wtlink`
    pointing at a directory elsewhere and the worktree added through the
    link: `resume.sh` answered "Error: 'wtlink/001-a-thing' exists and is not
    a registered worktree of the repo leg; that feature was NOT recreated …
    Move it aside", "REFUSED: 001-a-thing — an unrelated path is in the way",
    exit 2. The finding stands, and it is RR3's: resolving the root harder
    than git does would have deleted a refusal the other end makes."""
    checkout = workspace_config(home)
    config = atlas / ".specify" / "extensions" / "git" / "git-config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("checkout_mode: worktree\nworktree_root: wtlink\n",
                      encoding="utf-8")
    real = home / "real-wt"
    real.mkdir()
    (atlas / "wtlink").symlink_to(real, target_is_directory=True)
    at = atlas / "wtlink" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", at)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): a directory is at "
            f"{at}, which is the path `resume` computes for this leg and is "
            "not this branch's worktree") in result.stdout
    assert 'refused as "an unrelated path is in the way"' in result.stdout


def test_a_registration_at_that_path_with_nothing_on_disk_wants_the_prune(
        atlas, home):
    """THE STATE THE COMMIT BELOW FOUND AND DID NOT TAKE: a PRUNABLE
    registration AT the computed path for ANOTHER branch, with no directory
    on disk. `load_git_worktrees` DROPS a prunable block, so RR4 never sees
    it; `[ -e "$tree" ]` is false, so RR3 finds nothing; RR2, RR1 and RR5
    pass — and the run dies at the very end, on the `git worktree add` that
    is the last thing it does.

    RUN AGAINST THE EXTENSION on 2026-09-12, on a scratch single-shape estate
    with the real scripts: "Error: could not create the repo leg worktree
    'worktrees/001-a-thing' from 'origin/001-a-thing'; that feature was NOT
    recreated. / fatal: '…/worktrees/001-a-thing' is a missing but already
    registered worktree; use 'add -f' to override, or 'prune' or 'remove' to
    clear", "REFUSED: 001-a-thing — git worktree add failed", exit 2 — while
    this layer said "`resume Atlas` brings it back". It is neither RR3 nor
    RR4 and its REFUSED line is its own, and it belongs with the
    stale-registration arms, which look for the RECORDED BRANCH and never at
    the path: the exit is the same `worktree prune`, and after it `resume`
    does bring the feature back."""
    checkout = workspace_config(home)
    want = parked_worktree(atlas, "001-a-thing")
    want.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "-b", "002-other", str(want), cwd=atlas)
    rmtree(want)                # and NO `git worktree prune`
    porcelain = git("worktree", "list", "--porcelain", cwd=atlas).stdout
    assert "prunable" in porcelain, "git pruned it for us; the test is moot"
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here, but a stale worktree registration for `002-other` "
            f"is still recorded at the {want} `resume` computes for this leg, "
            f"with nothing on disk there — clear it with `git -C {atlas} "
            "worktree prune`, then `resume Atlas` brings it back"
            ) in result.stdout


def test_that_registration_is_in_the_way_of_a_move_as_well(atlas, home):
    """AND IT OUTLIVES THE MOVE the arm above names, which is why the two are
    one reading: with the feature's own worktree off the path AND a dead
    registration on it, `git worktree move` refuses the destination in the
    same words `git worktree add` refuses it — "a missing but already
    registered worktree" (git 2.43, 2026-09-12) — so the prune comes FIRST
    and the move second.

    Run against the extension the same day on both spellings of it, the
    registration naming another branch and the RECORDED one: each answered
    "Error: could not add the repo leg worktree 'worktrees/001-a-thing' for
    '001-a-thing'; that feature was NOT recreated. / fatal: '…' is a missing
    but already registered worktree", "REFUSED: 001-a-thing — git worktree
    add failed", exit 2 — the registration, not the branch already in use
    elsewhere, being what the add hits first."""
    checkout = workspace_config(home)
    want = parked_worktree(atlas, "001-a-thing")
    want.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "-b", "002-other", str(want), cwd=atlas)
    rmtree(want)                # and NO `git worktree prune`
    where = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): its worktree is at "
            f"{where}, which is not the {want} `resume` computes for it"
            ) in result.stdout
    # THE PRUNE IS IN THE COMMAND AND NOT BESIDE IT since Copilot's fifth
    # round on #27 (2026-09-13, suppressed), verbatim: "In the `held == 2`
    # recovery, the required destination prune appears only in the prose; the
    # copy-pastable command is `${unlock}mkdir -p ... && git worktree move ...`
    # and never runs `git worktree prune`. With a live off-path source and a
    # stale destination registration, the advertised command therefore still
    # fails at `worktree move`." Right, and it is this file's own rule: an exit
    # a person can run is one they can paste, so every step the destination
    # wants is in the sequence and the reason for each is behind it.
    assert ("move it where both look: "
            f"`git -C {atlas} worktree prune && mkdir -p {want.parent} && "
            f"git -C {atlas} worktree move {where} {want}`, which is yours to "
            "run — `worktree move` creates no parent directory of its own, and "
            'it refuses a destination git still holds registered ("a missing '
            'but already registered worktree") until the prune') in (
        result.stdout), result.stdout


def test_no_sibling_leg_of_an_off_path_feature_offers_resume(trio, home):
    """THE RULE AT THE TOP OF `check_parked_leg`, applied to this reading: a
    worktree off the computed path refuses the WHOLE feature at the other
    end, so no line of that feature may name `resume <Name>`. A three-leg
    record is where it shows — the `spec` leg's worktree at the feature
    directory instead of under its own mount, and a `code` leg with no
    worktree here at all — and the `code` leg's line said "`resume Trio`
    brings it back" while the `spec` leg's said the feature was refused
    whole.

    Verified against the extension on 2026-09-12: with the spec leg's
    worktree off the path, `resume.sh` refuses at the `git worktree add`
    ("already used by worktree at …"), "REFUSED", exit 2, and recreates
    nothing for any leg of that feature."""
    checkout = workspace_config(home)
    leg = trio / "spec"
    git("checkout", "-q", "main", cwd=leg)
    where = trio / "worktrees" / "001-s-thing"
    tip = feature_worktree(leg, "001-s-thing", where)
    path = record(checkout, "trio", branch="001-s-thing", role="spec",
                  commit=tip, root="Trio", parked_on="Falcon")
    text = path.read_text(encoding="utf-8")
    path.write_text(text + leg_block("code", FAKE_SHA), encoding="utf-8")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "`resume Trio`" not in result.stdout, result.stdout


# --- and what is AT that path, which is the other half of the question -----
#
# `resume.sh`'s RR4 second arm and RR3, the two readings the commit above
# verified and recorded rather than took. Both refuse the WHOLE feature, both
# are reached before RR2 reads origin, and this layer offered `resume <Name>`
# for each.

def in_the_way_finding(branch: str, role: str, what: str, at, why: str,
                       exit_clause: str) -> str:
    """The one line this reading prints, for the culprit leg."""
    return (f"    - parked feature {branch} ({role} leg): {what} is at {at}, "
            "which is the path `resume` computes for this leg and is not this "
            "branch's worktree — `resume` reads that path and no other, "
            "overwrites nothing it did not create, and refuses the WHOLE "
            "feature, the other legs with it (\"… exists and is not a "
            f"registered worktree of the {role} leg\", refused as \"{why}\"), "
            f"so nothing here brings it back while that is there — {exit_clause}")


def move_aside(at) -> str:
    return (f"move it aside with `mv {at} <a path of your choosing>`, which "
            "is yours to run — nothing here moves or deletes a path it did "
            "not create")


def worktree_move_aside(repo, at) -> str:
    return (f"move it aside with `git -C {repo} worktree move {at} <a path of "
            "your choosing>`, which is yours to run — a registered worktree "
            "moved with `mv` leaves git holding the path it was at")


def unlock_then_move(repo, at) -> str:
    return ("git holds that worktree LOCKED and `worktree move` refuses a "
            "locked one (\"cannot move a locked working tree\"), so the "
            f"unlock comes first: `git -C {repo} worktree unlock {at}`, then "
            f"`git -C {repo} worktree move {at} <a path of your choosing>`, "
            "both yours to run — a registered worktree moved with `mv` "
            "leaves git holding the path it was at")


def move_aside_and_prune(repo, at) -> str:
    return (f"move it aside with `mv {at} <a path of your choosing>` and "
            "clear the stale registration git still holds for that path with "
            f"`git -C {repo} worktree prune`, both yours to run — nothing "
            "here moves or deletes a path it did not create, and `git "
            "worktree add` refuses a path it is still registered at (\"a "
            "missing but already registered worktree\")")


def test_a_stray_path_at_the_computed_path_is_rr3_and_never_a_resume(
        atlas, home):
    """VERIFIED AGAINST THE EXTENSION on 2026-09-12, on a scratch single-shape
    estate with the real scripts — a bare remote in a temp dir, a fake `$HOME`
    — whose record carried `pushed: true` and a parked commit that was
    origin's tip, with NO worktree for the feature here: a plain directory at
    `worktrees/001-a-thing` answered "Error: 'worktrees/001-a-thing' exists
    and is not a registered worktree of the repo leg; that feature was NOT
    recreated. / Nothing here overwrites a directory it did not create. /
    look:  git -C . worktree list / Move it aside, then re-run `make
    resume`.", "REFUSED: 001-a-thing — an unrelated path is in the way", exit
    2 — and a plain FILE there answered exactly the same. With nothing at that
    path the same estate RESUMED the feature, exit 0. `status` at fd9ae96, this
    branch's base, answered "`resume Atlas` brings it back" for both."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    origin_has_branch(atlas, "001-a-thing")
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=git("rev-parse", "origin/001-a-thing", cwd=atlas).stdout.strip())

    where.mkdir(parents=True)
    (where / "notes.md").write_text("somebody else's\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo", "a directory", where,
                              "an unrelated path is in the way",
                              move_aside(where)) in result.stdout
    assert "`resume Atlas` brings it back" not in result.stdout

    rmtree(where)
    where.write_text("somebody else's\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo", "a file", where,
                              "an unrelated path is in the way",
                              move_aside(where)) in result.stdout
    assert "`resume Atlas` brings it back" not in result.stdout


def test_a_worktree_of_another_branch_at_that_path_is_rr4s_second_arm(
        atlas, home):
    """`leg_registered_at` matches the PATH and then tests the branch, and
    `[ "$LEG_REGISTERED_BRANCH" = "$branch" ]` failing is RR4's second arm.
    Run against the extension on the same estate the same day, a worktree of
    `002-other` at `worktrees/001-a-thing` answered the same four stderr lines
    as RR3 and "REFUSED: 001-a-thing — an unrelated worktree is in the way",
    exit 2; a worktree with a DETACHED head there answered the same, because
    a detached block has no `branch` line and `LEG_REGISTERED_BRANCH` is then
    the empty string, which is no branch name either.

    THE EXIT IS NOT THE STRAY PATH'S. `mv` on a registered worktree leaves
    git holding the path it was at, and `git worktree move` is the command
    that moves the directory and the registration together."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    origin_has_branch(atlas, "001-a-thing")
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=git("rev-parse", "origin/001-a-thing", cwd=atlas).stdout.strip())

    where.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "-b", "002-other", str(where), cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo", "a worktree on `002-other`",
                              where, "an unrelated worktree is in the way",
                              worktree_move_aside(atlas, where)) in result.stdout
    assert "`resume Atlas` brings it back" not in result.stdout

    git("worktree", "remove", str(where), cwd=atlas)
    git("branch", "-q", "-D", "002-other", cwd=atlas)
    git("worktree", "add", "-q", "--detach", str(where), "main", cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo",
                              "a worktree with a detached head", where,
                              "an unrelated worktree is in the way",
                              worktree_move_aside(atlas, where)) in result.stdout
    assert "`resume Atlas` brings it back" not in result.stdout


def test_a_locked_registration_of_another_branch_names_the_unlock_not_a_move(
        atlas, home):
    """A block git calls `prunable` is one `load_git_worktrees` DROPS, so
    `resume` never sees it — but it computes no `prunable` for a LOCKED one
    (git 2.43), and `leg_registered_at` therefore matches it and RR4's second
    arm refuses the feature. Verified against the extension on 2026-09-12:
    with the worktree of `002-other` at `worktrees/001-a-thing` locked and its
    `.git` deleted, it answered "REFUSED: 001-a-thing — an unrelated worktree
    is in the way", exit 2.

    AND THE EXIT IS NOT A `worktree move` THERE: the directory is no longer a
    worktree, so what clears the registration is the unlock and the prune the
    stale-registration arms already name — with the directory the prune
    leaves behind moved aside, because `resume` refuses a path that exists
    whatever git holds."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    origin_has_branch(atlas, "001-a-thing")
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=git("rev-parse", "origin/001-a-thing", cwd=atlas).stdout.strip())
    where.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "-b", "002-other", str(where), cwd=atlas)
    git("worktree", "lock", str(where), cwd=atlas)
    (where / ".git").unlink()       # the directory stays; the worktree does not
    porcelain = git("worktree", "list", "--porcelain", cwd=atlas).stdout
    assert "prunable" not in porcelain, "git called a locked block prunable"

    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding(
        "001-a-thing", "repo", "a worktree on `002-other`", where,
        "an unrelated worktree is in the way",
        "the worktree it registers is not there and git holds the "
        "registration LOCKED, which is why it calls it no `prunable` — clear "
        f"it with `git -C {atlas} worktree unlock {where}`, then `git -C "
        f"{atlas} worktree prune`, which is yours to run, and move aside "
        "whatever the prune leaves behind there, which `resume` refuses for "
        "existing whatever git holds") in result.stdout
    assert "worktree move" not in result.stdout


def test_a_locked_worktree_of_another_branch_puts_the_unlock_first(
        atlas, home):
    """RR4's second arm again, and the EXIT is the whole of what is new: git
    holds a live worktree there LOCKED, `leg_registered_at` matches it because
    a locked block carries no `prunable`, and the extension answered "REFUSED:
    001-a-thing — an unrelated worktree is in the way", exit 2, on 2026-09-12.
    `git worktree move` REFUSES a locked worktree — "fatal: cannot move a
    locked working tree; use 'move -f -f' to override or unlock first", git
    2.43 the same day — so the plain move this layer named at fd9ae96 is an
    exit that does not run, and the unlock goes in front of it (run there
    too: `unlock` then `move` exits 0)."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    origin_has_branch(atlas, "001-a-thing")
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=git("rev-parse", "origin/001-a-thing", cwd=atlas).stdout.strip())
    where.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "-b", "002-other", str(where), cwd=atlas)
    git("worktree", "lock", str(where), cwd=atlas)

    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo", "a worktree on `002-other`",
                              where, "an unrelated worktree is in the way",
                              unlock_then_move(atlas, where)) in result.stdout
    assert worktree_move_aside(atlas, where) not in result.stdout


def test_a_prunable_registration_at_that_path_names_the_prune_with_the_move(
        atlas, home):
    """A block git calls `prunable` is one `load_git_worktrees` DROPS, so
    `leg_registered_at` misses it and what refuses the feature is the
    DIRECTORY: RR3, "an unrelated path is in the way", exit 2 against the
    extension on 2026-09-12 with a worktree of `002-other` at the computed
    path whose `.git` had been deleted.

    AND THE `mv` IS NOT THE WHOLE EXIT THERE. The registration outlives the
    directory, and the `git worktree add` at the end of the run dies on it
    instead — "'…' is a missing but already registered worktree; use 'add -f'
    to override, or 'prune' or 'remove' to clear" — with the directory moved
    aside or not (git 2.43, both spellings run the same day). So the prune is
    named beside the move, and neither half is optional."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    origin_has_branch(atlas, "001-a-thing")
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=git("rev-parse", "origin/001-a-thing", cwd=atlas).stdout.strip())
    where.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "-b", "002-other", str(where), cwd=atlas)
    (where / ".git").unlink()       # prunable, with its directory still there
    assert "prunable" in git("worktree", "list", "--porcelain",
                             cwd=atlas).stdout

    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo", "a directory", where,
                              "an unrelated path is in the way",
                              move_aside_and_prune(atlas, where)) in result.stdout
    assert move_aside(where) not in result.stdout


def test_a_worktree_registered_at_that_path_is_the_leg_however_many_others(
        atlas, home):
    """RR4's QUESTION IS THE PATH'S, AND THE BRANCH IS TESTED AFTER IT (the
    independent review of fd9ae96, 2026-09-12, blocker 2). `leg_registered_at`
    walks the registered paths for an exact match and only then reads the
    branch on the block it found; `worktree_on_branch` walks the BRANCHES and
    answers with the first live worktree holding it, which `git worktree list`
    orders by path. Where one branch is checked out twice — `worktree add
    --force`, the state this file's own comments already name — the two
    answers are different worktrees, and the base read the wrong one: it
    refused the WHOLE feature and named a `git worktree move` ONTO the very
    worktree `resume` had just resumed the feature from. Verified against the
    extension on 2026-09-12 with exactly this estate: "[specify] 001-a-thing
    (repo): worktree already registered at worktrees/001-a-thing; left as it
    is", "RESUMED: 001-a-thing", exit 0. So there is nothing to say here, and
    the decoy's own path sorting before or after the computed one changes
    nothing."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    decoy = home / "elsewhere" / "001-a-thing"
    decoy.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "--force", str(decoy), "001-a-thing",
        cwd=atlas)

    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 finding(s)" in result.stdout
    assert "which is not the" not in result.stdout
    assert "which is the path `resume` computes for this leg" not in result.stdout


def test_a_prunable_registration_on_the_recorded_branch_is_not_in_the_way(
        atlas, home):
    """The state the stale-registration arms already answer, and the one this
    reading must not answer twice. `_git_worktree_finalize_record` stages a
    block only `if [ "$prunable" = false ]`, so `leg_registered_at` never sees
    this one and RR4 is not reached — and the prune, plus a move of the
    directory it leaves behind, is what `resume` needs before it can recreate
    anything, which is exactly what that line says. Two findings about one
    path, one of them promising a `resume` and the other refusing it, is the
    contradiction this guard exists to prevent.

    AND IT IS THE LINE, NOT THE BLOCK, THAT DECIDES IT: the carve-out asks
    `worktree_on_branch` which block it answered with, because that is the
    one this layer prints. Put a LIVE worktree on the branch somewhere else
    and it answers with that instead, nothing names the obstructed path at
    all, and the reading is the only one left that does — with the prune in
    the exit, because the dead registration is still on that path."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    (where / ".git").unlink()       # prunable, with its directory still there
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            f"branch here, but a stale worktree registration for it is still "
            f"recorded at {where}, whose path is still on disk and is no "
            f"longer a worktree — clear it with `git -C {atlas} worktree "
            "prune` and a move of what is there aside (`git worktree add` "
            "refuses a path that \"already exists\"), then `resume Atlas` "
            "brings it back") in result.stdout
    assert "which is the path `resume` computes for this leg" not in result.stdout

    elsewhere = home / "elsewhere" / "001-a-thing"
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "--force", str(elsewhere), "001-a-thing",
        cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo", "a directory", where,
                              "an unrelated path is in the way",
                              move_aside_and_prune(atlas, where)) in result.stdout
    assert "a stale worktree registration" not in result.stdout


def test_the_legs_own_checkout_at_that_path_names_nothing_to_move(atlas, home):
    """`worktree list --porcelain` names the MAIN worktree too, so a root
    whose computed worktree path is the root itself is a registration RR4
    matches and refuses the feature for. Verified against the extension on
    2026-09-12 on a scratch estate whose `git-config.yml` said `worktree_root:
    ..` and whose recorded branch was named for the root folder: it answered
    "Error: '.' exists and is not a registered worktree of the repo leg",
    "REFUSED: Atlas — an unrelated worktree is in the way", exit 2.

    `git worktree move` refuses a main working tree, so this spelling names no
    command at all: an exit that cannot run is the one thing the rule at the
    top of `check_parked_leg` forbids. `$SPECKIT_GIT_WORKTREE_ROOT` is the
    override both verbs read first, which is how the fixture reaches the state
    without a config file."""
    checkout = workspace_config(home)
    origin_has_branch(atlas, "Atlas")
    record(checkout, "atlas", branch="Atlas", role="repo",
           commit=git("rev-parse", "origin/Atlas", cwd=atlas).stdout.strip())
    result = run(STATUS, "Atlas", home=home,
                 env={"SPECKIT_GIT_WORKTREE_ROOT": str(home / "projects")})
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding(
        "Atlas", "repo", "a worktree on `main`", atlas,
        "an unrelated worktree is in the way",
        f"{atlas} is the repo leg's OWN checkout rather than a worktree of "
        "it, and no `worktree move` moves a main working tree, so there is "
        "nothing here to move aside: while the worktree root this checkout "
        "computes puts this feature on top of that checkout, neither verb can "
        "do anything with it") in result.stdout
    assert "worktree move" in result.stdout
    assert f"worktree move {atlas}" not in result.stdout


def test_the_reading_ends_the_leg_because_resume_never_gets_past_it(
        atlas, home):
    """RR3 and RR4 come before RR2 and RR1, so every arm below this one names
    an exit `resume` never reaches. Two records prove it on one estate: a
    branch origin has LOST, whose own line offers RR2's two exits, and a
    record naming NO PARKED COMMIT, whose line offers a re-park — under a
    stray directory neither is what happens, and the extension answered "an
    unrelated path is in the way" for both on 2026-09-12."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    origin_has_branch(atlas, "001-a-thing")
    tip = git("rev-parse", "origin/001-a-thing", cwd=atlas).stdout.strip()
    where.mkdir(parents=True)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    drop_from_origin(atlas, "001-a-thing")
    result = run(STATUS, "Atlas", "--fetch", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo", "a directory", where,
                              "an unrelated path is in the way",
                              move_aside(where)) in result.stdout
    assert "is no longer on origin in the repo leg" not in result.stdout

    record(checkout, "atlas", branch="001-a-thing", role="repo", commit="")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo", "a directory", where,
                              "an unrelated path is in the way",
                              move_aside(where)) in result.stdout
    assert "names no parked commit" not in result.stdout


def test_it_is_read_before_the_path_the_worktree_is_at_because_rr4_is_first(
        atlas, home):
    """The feature's own worktree somewhere else AND a stray directory at the
    computed path: `resume` refuses at RR3 without ever reaching the `git
    worktree add` the arm below predicts — "REFUSED: 001-a-thing — an
    unrelated path is in the way", exit 2, against the extension on
    2026-09-12. And the arm below would name a `git worktree move` INTO that
    directory, which does not fail: `git worktree move` behaves like `mv` and
    puts the worktree INSIDE an existing destination, leaving it at
    `worktrees/001-a-thing/001-a-thing` — still where neither verb looks, and
    now under the stray directory (git 2.43, the same day). An exit that
    quietly misfiles the work is worse than one that refuses."""
    checkout = workspace_config(home)
    elsewhere = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", elsewhere)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    where = parked_worktree(atlas, "001-a-thing")
    where.mkdir(parents=True)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-a-thing", "repo", "a directory", where,
                              "an unrelated path is in the way",
                              move_aside(where)) in result.stdout
    assert "which is not the" not in result.stdout


def test_rr6_is_read_first_so_a_no_push_record_says_what_it_always_said(
        atlas, home):
    """`resume.sh` tests `[ "$pushed" != true ]` at the top of the leg loop
    and `break`s there, so no path is ever looked at for such a leg: the
    refusal is RR6's, the exit is a park from the workstation that has the
    WIP commit, and a stray directory here changes neither.

    AND WITH A WORKTREE OFF THE PATH TOO the path-parity arm below goes quiet
    as well, for the same stray directory and a reason of its own: the
    `git worktree move` it names does not fail on an occupied destination, it
    behaves like `mv` and puts the worktree INSIDE it (git 2.43, 2026-09-12).
    An exit that quietly misfiles the work is worse than one line fewer, and
    the line above already says what this record needs."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    where.mkdir(parents=True)
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=FAKE_SHA, pushed="false", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): parked with "
            "--no-push on Falcon and no worktree on that branch here; only "
            "that workstation has the WIP commit, so nothing here brings it "
            "back — park it again from there") in result.stdout
    assert "which is the path `resume` computes for this leg" not in result.stdout

    elsewhere = home / "elsewhere" / "001-a-thing"
    feature_worktree(atlas, "001-a-thing", elsewhere, push=False)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): parked with "
            "--no-push on Falcon; only that workstation has the WIP commit, "
            "and `resume` refuses it") in result.stdout
    assert "which is the path `resume` computes for this leg" not in result.stdout
    assert "which is not the" not in result.stdout


def test_an_rr6_leg_still_says_where_its_own_worktree_sits(atlas, home):
    """AFTER THE `pushed:` ARMS, AND NOT INSTEAD OF THEM — the claim the first
    commit of this branch makes, met on `main` by a verdict that had not
    existed when it was written. Since Copilot's third round on #23 a leg
    whose `pushed:` is not `true` is RR6's refusal OF THE WHOLE FEATURE and
    `read_record` hands that verdict down to every leg, so the test that
    silences this arm for a feature `resume` refuses whole would have silenced
    it here too.

    IT MUST NOT. `resume.sh` tests `[ "$pushed" != true ]` at the TOP of the
    leg loop, so RR6 IS "whichever of its own checks this leg reaches first",
    and what this line says is true of THIS workstation whatever the record
    says: a worktree on the recorded branch sitting where neither verb looks,
    which `park` here does not collect either, and a `git worktree move` that
    RUNS. The two lines answer different things and neither is the other's
    second reading.

    AND AN EARLIER LEG'S RR6 DOES SILENCE IT, which is the other half and is
    the round's own rule: `resume` breaks at the first refusing leg in the
    record's order, so a later leg is one the run never reaches and a line
    about the check it would have reached first is a refusal this layer would
    be inventing. RUN AGAINST THE EXTENSION on 2026-09-13, on a scratch
    three-leg estate with the `code` leg recorded FIRST as `pushed: false` and
    the `spec` leg's worktree at `$HOME/elsewhere/001-a-thing`: "Error:
    001-a-thing (code leg) was parked with --no-push; that feature was NOT
    recreated", "REFUSED: 001-a-thing — parked with --no-push", exit 2 — and
    the same estate with that leg's `pushed: true`, which is the control,
    "Error: could not add the spec leg worktree 'worktrees/001-a-thing/spec'
    for '001-a-thing'", "REFUSED: 001-a-thing — git worktree add failed",
    exit 2."""
    checkout = workspace_config(home)
    elsewhere = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", elsewhere)
    want = parked_worktree(atlas, "001-a-thing")
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           pushed="false", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): parked with "
            "--no-push on Falcon; only that workstation has the WIP commit, "
            "and `resume` refuses it") in result.stdout
    assert (f"    - parked feature 001-a-thing (repo leg): its worktree is at "
            f"{elsewhere}, which is not the {want} `resume` computes for it"
            ) in result.stdout
    assert f"git -C {atlas} worktree move {elsewhere} {want}" in result.stdout


def test_a_later_leg_says_nothing_about_a_path_an_rr6_leg_beat_it_to(
        trio, home):
    """The other half of the test above, in the shape that needs two legs: the
    `code` leg recorded FIRST and parked `--no-push`, the `spec` leg's worktree
    off the path. `resume` breaks at RR6 on the first leg and never reads the
    second, so the second says nothing about its path — the run above is the
    proof, and so is its `pushed: true` control, which reaches the add."""
    checkout = workspace_config(home)
    spec, code = trio / "spec", trio / "code"
    for leg in (spec, code):
        git("checkout", "-q", "main", cwd=leg)
        origin_has_branch(leg, "001-a-thing")
    spec_tip = git("rev-parse", "origin/001-a-thing", cwd=spec).stdout.strip()
    code_tip = git("rev-parse", "origin/001-a-thing", cwd=code).stdout.strip()
    elsewhere = home / "elsewhere" / "001-a-thing"
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", str(elsewhere), "001-a-thing", cwd=spec)
    path = record(checkout, "trio", branch="001-a-thing", role="code",
                  commit=code_tip, pushed="false", parked_on="Falcon",
                  root="Trio")
    path.write_text(path.read_text(encoding="utf-8")
                    + leg_block("spec", spec_tip), encoding="utf-8")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == [
        "- parked feature 001-a-thing (code leg): parked with --no-push on "
        "Falcon and no worktree on that branch here; only that workstation "
        "has the WIP commit, so nothing here brings it back — park it again "
        "from there"], findings
    assert "worktree move" not in result.stdout, (
        "RR6 on the first leg breaks the loop before the second leg's path "
        "is read at all")

    # AND WITH THAT LEG'S `pushed: true` — the control — the run reaches the
    # add, and this layer says so on the leg whose worktree is off the path.
    path = record(checkout, "trio", branch="001-a-thing", role="code",
                  commit=code_tip, parked_on="Falcon", root="Trio")
    path.write_text(path.read_text(encoding="utf-8")
                    + leg_block("spec", spec_tip), encoding="utf-8")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"its `spec` leg's worktree is at {elsewhere}") in result.stdout
    assert "`resume Trio`" not in result.stdout


def test_no_line_of_a_feature_a_path_in_the_way_refuses_offers_resume(
        trio, home):
    """THE VERDICT IS THE FEATURE'S, because the refusal is. RR3 and RR4 are
    per leg and `break` the leg loop, so one leg's obstructed path takes every
    other leg of that feature with it — and a sibling leg with no worktree
    here would otherwise print "`resume Trio` brings it back" beside the line
    that says the feature is refused. `read_record`'s first pass asks the
    question of each leg in the record's order and hands the answer down, as
    it does for every verdict `collect_legs` makes; what is new is that this
    one carries its own EXIT, because a park on another workstation moves
    nothing out of this checkout's way.

    The `spec` leg's worktree belongs under its own mount — `collect_legs`
    computes `$WORKTREE_ROOT/$branch/$SHAPE_SPEC_PATH` — so the stray
    directory goes there and not at the feature directory."""
    checkout = workspace_config(home)
    for leg in ("spec", "code"):
        git("checkout", "-q", "main", cwd=trio / leg)
        origin_has_branch(trio / leg, "001-s-thing")
    where = parked_worktree(trio, "001-s-thing", "spec")
    where.mkdir(parents=True)
    tip = git("rev-parse", "origin/001-s-thing", cwd=trio / "spec").stdout.strip()
    path = record(checkout, "trio", branch="001-s-thing", role="spec",
                  commit=tip, root="Trio", parked_on="Falcon")
    code_tip = git("rev-parse", "origin/001-s-thing",
                   cwd=trio / "code").stdout.strip()
    path.write_text(path.read_text(encoding="utf-8")
                    + "          - role: code\n"
                      "            remote: origin\n"
                      f"            parked_commit: {code_tip}\n"
                      "            wip: true\n"
                      "            wip_depth: 1\n"
                      "            pushed: true\n", encoding="utf-8")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert in_the_way_finding("001-s-thing", "spec", "a directory", where,
                              "an unrelated path is in the way",
                              move_aside(where)) in result.stdout
    assert ("    - parked feature 001-s-thing (code leg): no worktree on that "
            "branch here, parked 2026-09-10T20:00:00Z on Falcon; `resume` "
            f"refuses the WHOLE feature, because a directory is at the {where} "
            "it computes for its `spec` leg, so it does not bring this leg "
            "back "
            f"— {move_aside(where)}") in result.stdout
    assert "`resume Trio` brings it back" not in result.stdout


def test_a_feature_collect_legs_refuses_whole_says_nothing_about_that_path(
        atlas, home):
    """`collect_legs` is answered before any leg is read, so a feature it
    throws out never reaches RR3 or RR4 and the path is not what stops it.
    The verdict that wins is the one that is made first, and the line that
    names the leg costing the feature is the whole answer."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    where.mkdir(parents=True)
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon")
    path.write_text(path.read_text(encoding="utf-8")
                    + "          - role: nope\n"
                      "            remote: origin\n"
                      f"            parked_commit: {FAKE_SHA}\n"
                      "            wip: true\n"
                      "            wip_depth: 1\n"
                      "            pushed: true\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (nope leg): the record names a "
            "leg this root does not mount here; `resume` maps each leg's role "
            "onto this checkout and refuses the WHOLE feature") in result.stdout
    assert "which is the path `resume` computes for this leg" not in result.stdout
    assert "`resume Atlas` brings it back" not in result.stdout


def test_a_leg_parked_with_no_push_is_a_finding(atlas, home):
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           pushed="false", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): parked with --no-push "
            "on Falcon; only that workstation has the WIP commit, and `resume` "
            "refuses it") in result.stdout


def test_an_unreadable_pushed_is_a_finding_where_the_worktree_is_in_sync(
        atlas, home):
    """The second independent review of #18, 2026-09-11, note (d): a `pushed:`
    that is neither `true` nor `false` was read as `true` everywhere, because
    only `= false` was ever tested. `park.sh` writes one of those two words
    and nothing else, so this record is a hand-edit — and `resume.sh`'s RR6,
    `[ "$pushed" != true ]`, refuses the leg for it exactly as it refuses a
    `--no-push` one. So it is a finding of its own, as `--no-push` is, even
    where the worktree here sits at the parked commit; and the line NAMES the
    value rather than deciding what it must have meant."""
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           pushed="maybe", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): its `pushed:` says "
            "'maybe', which is neither true nor false, so whether its parked "
            "commit ever left Falcon cannot be read; `resume` refuses a leg "
            "whose `pushed:` is not true, so park it again from there to write "
            "the record afresh") in result.stdout
    assert "--no-push" not in result.stdout, (
        "a --no-push claim the record does not make")

    # `pushed: ""` is the empty value in quotes — `trim_unquote` takes the
    # pair off, so it reads as the bare `pushed:` it is rather than as a
    # value spelled with two quote characters.
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           pushed='""', parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): its `pushed:` has no "
            "value, which is neither true nor false, so whether its parked "
            "commit ever left Falcon cannot be read; `resume` refuses a leg "
            "whose `pushed:` is not true, so park it again from there to write "
            "the record afresh") in result.stdout


def test_a_record_with_no_pushed_key_at_all_is_a_finding_not_silence(
        atlas, home):
    """The independent review of #19, 2026-09-11, which recorded it there as
    out of scope: the hole beside note (d) is larger than note (d), and this
    is it. A leg whose record carries no `pushed:` KEY drew NOTHING — exit 0,
    the parked-record note and no finding — because `record_rows` emitted a
    leg's row AT its `pushed:` line and a leg without one had no row at all.

    Meanwhile `workspace-common.sh`'s `workspace_load_project` — before
    workBenches #60 (ec2b450) — seeded every leg's `MANIFEST_LEG_PUSHED` with
    `false` at the `- role:` line and overwrote it only where a `pushed:`
    followed (since #60 it seeds nothing and refuses a missing key for being
    missing; the refusal and the exit are the same), so `resume.sh`'s RR6,
    `[ "$pushed" != true ]`, REFUSED that leg in the `--no-push` words — run
    against such a record on 2026-09-11 the extension answered "Error:
    001-a-thing (repo leg) was parked with --no-push; that feature was NOT
    recreated", exit 2. `status` was silent about a record `resume` will not
    resume, which is the same family as note (d) and strictly worse: a wrong
    line can be argued with, a missing one cannot.

    That paragraph is workBenches BEFORE #60 (ec2b450). That pull request,
    merged as 98b8bd1, stops the loader inventing `pushed: false` for an
    absent key, and RR6 then refuses the leg in words of its own — "the
    record has no `pushed:` for this leg", exit 2, run on 2026-09-11 against
    its scripts. What the line below asserts is what is true under both: the
    record does not say, `resume` refuses the leg for that, and the exit is a
    park from the workstation that has it.

    So it is a finding of its own, as `--no-push` and the unreadable value
    are, even where the worktree here sits at the parked commit; and it names
    what the record does not say rather than deciding what it must have
    meant."""
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=tip, pushed=None, parked_on="Falcon")
    assert "pushed" not in path.read_text(encoding="utf-8"), (
        "the record still carries the key; the test is moot")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): the record has no "
            "`pushed:` for that leg, so whether its parked commit ever left "
            "Falcon cannot be read; `resume` refuses a leg whose record has no "
            "`pushed:`, so park it again from there to write the record "
            "afresh") in result.stdout
    assert "--no-push" not in result.stdout, (
        "a --no-push claim the record does not make")
    assert "neither true nor false" not in result.stdout, (
        "the reading for a value that IS there; this record has none")


def test_an_absent_pushed_key_and_a_bare_one_are_not_the_same_finding(
        atlas, home):
    """Two states, not one, and the row carries them in separate fields: a
    bare `pushed:` is PRESENT and unreadable — note (d) of the second
    independent review of #18 — while no `pushed:` at all is the record
    saying nothing about that leg. Both leave the value empty, so a reader
    told only "has no value" would go looking for a line that is not there,
    and one told only "has no `pushed:`" would miss the one that is. Each is
    named for what it is."""
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))

    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           pushed=None, parked_on="Falcon")
    absent = run(STATUS, "Atlas", home=home)
    assert absent.returncode == 1, absent.stdout + absent.stderr
    assert "the record has no `pushed:` for that leg" in absent.stdout
    assert "has no value" not in absent.stdout

    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           pushed="", parked_on="Falcon")
    bare = run(STATUS, "Atlas", home=home)
    assert bare.returncode == 1, bare.stdout + bare.stderr
    assert ("its `pushed:` has no value, which is neither true nor false"
            in bare.stdout)
    assert "the record has no `pushed:`" not in bare.stdout


def test_the_absent_pushed_clause_says_the_refusal_not_the_loader(atlas, home):
    """The independent review of workBenches #60, 2026-09-11. The clause this
    layer carried for an absent `pushed:` — "`resume` reads a missing one as
    not pushed and refuses it" — was the MECHANISM of one loader written into
    this command's output: `workspace_load_project` seeded every leg's pushed
    with `false`, so a missing key reached RR6 as `false`. #60 stops that
    invention (the seed is the empty string, and a new
    `MANIFEST_LEG_PUSHED_SEEN[]` keeps absent apart from bare, which is what
    `record_rows`'s sixth field does here), and `resume` then reads a missing
    key as NOTHING and refuses it for that, in words of its own.

    A line that says HOW the other end reads the record goes stale the day
    the other end changes; a line that says WHAT IT DOES does not. Both
    loaders refuse the leg at the same test, `[ "$pushed" != true ]`, and
    both leave the same exit — verified against both on 2026-09-11: main
    answered "Error: 001-a-thing (repo leg) was parked with --no-push; that
    feature was NOT recreated", #60's scripts "Error: 001-a-thing (repo leg):
    the record has no `pushed:` for this leg; that feature was NOT
    recreated", exit 2 each. So the clause names the refusal and the exit and
    nothing else, and it must not say either loader's reading — not "as not
    pushed", which is main's, and not `--no-push`, which is the claim the
    record does not make."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed=None, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "`resume` refuses a leg whose record has no `pushed:`" in result.stdout
    assert "reads a missing one as not pushed" not in result.stdout, (
        "one loader's reading of the absent key, in a line about both")
    assert "not pushed" not in result.stdout, (
        "the record says nothing about the push; only the refusal is shared")
    assert "--no-push" not in result.stdout, (
        "a --no-push claim the record does not make")


def test_a_registration_git_calls_prunable_is_stale_with_its_directory_there(
        atlas, home):
    """Delete only the worktree's `.git` file: the DIRECTORY stays, and git
    calls the registration "prunable gitdir file points to non-existent
    location". A `-d` test alone read that as a live worktree and, sitting at
    the parked commit, said nothing at all — while `resume` still saw the
    registration. Git's own verdict is the one to trust, and the exit is both
    halves: the prune clears the registration and leaves the directory, which
    `git worktree add` then refuses ("already exists")."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    (where / ".git").unlink()       # the directory stays; the worktree does not
    porcelain = git("worktree", "list", "--porcelain", cwd=atlas).stdout
    assert "prunable" in porcelain, "git no longer says prunable; the test is moot"
    assert where.is_dir(), "the directory is what makes this case"
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here, but a stale worktree registration for it is still "
            f"recorded at {where}, whose path is still on disk and is no "
            f"longer a worktree — clear it with `git -C {atlas} worktree prune`"
            " and a move of what is there aside (`git worktree add` refuses a "
            'path that "already exists"), then `resume Atlas` brings it back'
            ) in result.stdout


def test_a_locked_registration_whose_git_file_is_gone_is_stale_too(atlas, home):
    """Git computes no `prunable` for a LOCKED block, so a locked worktree
    whose `.git` file is deleted says only `locked` while its directory sits
    there: nothing in the porcelain calls it stale, and a directory test
    alone called it live and the recorded feature clean. What a worktree has
    is its own `.git`, and without it this is a leftover directory plus a
    registration `resume` still trips on — cleared by unlock, then prune,
    then moving the directory aside."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    git("worktree", "lock", str(where), cwd=atlas)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    (where / ".git").unlink()       # locked, directory kept, worktree gone
    porcelain = git("worktree", "list", "--porcelain", cwd=atlas).stdout
    assert "\nlocked" in porcelain, "not locked; the test is moot"
    assert "prunable" not in porcelain, "git judges a locked block now"
    assert where.is_dir()
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here, but a stale worktree registration for it is still "
            f"recorded at {where} and LOCKED, which `worktree prune` skips, "
            "whose path is still on disk and is no longer a worktree — "
            f"clear it with `git -C {atlas} worktree unlock {where}`, then "
            f"`git -C {atlas} worktree prune` and a move of what is there "
            'aside (`git worktree add` refuses a path that "already exists"), '
            "then `resume Atlas` brings it back") in result.stdout


def test_a_locked_registration_that_is_not_a_worktree_is_not_unparked_work(
        atlas, home):
    """The sweep's twin of the same case: a directory with no `.git` in it is
    not a worktree, so it was never parked work either — and `park` would
    carry nothing if somebody ran it."""
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    gone = home / "Atlas-wt" / "002-unparked"
    feature_worktree(atlas, "002-unparked", gone)
    git("worktree", "lock", str(gone), cwd=atlas)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    (gone / ".git").unlink()        # locked, directory kept, worktree gone
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "002-unparked" not in result.stdout


def test_the_locked_one_of_two_stale_registrations_is_the_one_named(atlas, home):
    """`worktree add --force` is how one branch ends up with two
    registrations. `prune` takes every UNLOCKED one with it, so the locked
    one is what has to be named: naming the unlocked path would leave the
    locked registration standing and `resume` still blocked, which is the
    state the first draft's "first stale block wins" produced."""
    checkout = workspace_config(home)
    first = parked_worktree(atlas, "001-a-thing")
    second = home / "Atlas-wt2" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", first)
    git("worktree", "add", "--force", "-q", str(second), "001-a-thing", cwd=atlas)
    git("worktree", "lock", str(second), cwd=atlas)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    rmtree(first)
    rmtree(second)          # both gone, and NO `git worktree prune`
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"recorded at {second} and LOCKED, which `worktree prune` skips — "
            f"clear it with `git -C {atlas} worktree unlock {second}`, then "
            f"`git -C {atlas} worktree prune`") in result.stdout
    assert f"recorded at {first}" not in result.stdout, (
        "the unlocked path, whose prune would leave the locked one standing")
    assert f"worktree unlock {first}" not in result.stdout


def test_a_locked_stale_registration_names_the_unlock_before_the_prune(
        atlas, home):
    """`git worktree prune` SKIPS a locked registration — against git 2.43,
    `prune -v` prints nothing for one, `unlock` then `prune` removes it, and
    `worktree remove --force` refuses it ("cannot remove a locked working
    tree; use 'remove -f -f' to override or unlock first"). So the finding
    that named the prune alone would have left `resume` blocked by the very
    thing it said to clear."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    git("worktree", "lock", str(where), cwd=atlas)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    rmtree(where)           # locked, and NO `git worktree prune`
    porcelain = git("worktree", "list", "--porcelain", cwd=atlas).stdout
    assert "\nlocked" in porcelain, "the registration is not locked; the test is moot"
    assert "prunable" not in porcelain, "git marks a locked one prunable now"
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here, but a stale worktree registration for it is still "
            f"recorded at {where} and LOCKED, which `worktree prune` skips — "
            f"clear it with `git -C {atlas} worktree unlock {where}`, then "
            f"`git -C {atlas} worktree prune`, then `resume Atlas` brings it "
            "back") in result.stdout
    assert f"recorded at {where} — clear it with" not in result.stdout, (
        "the prune-only line, which cannot clear a locked registration")


def test_a_no_push_record_with_no_worktree_here_never_names_resume(atlas, home):
    """The two lines contradicted each other: `resume` refuses this record,
    and then `resume Atlas` brings it back. Only the workstation that parked
    it has the WIP commit — which is what `resume.sh` refuses the leg for — so
    the two states are one line, and the exit is that workstation."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed="false", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): parked with --no-push "
            "on Falcon and no worktree on that branch here; only that "
            "workstation has the WIP commit, so nothing here brings it back — "
            "park it again from there") in result.stdout
    assert "`resume Atlas` brings it back" not in result.stdout

    # The same record with a stale registration left behind: the prune is
    # named, and `resume` still is not — there is nothing here to resume.
    where = parked_worktree(atlas, "001-a-thing")
    feature_worktree(atlas, "001-a-thing", where)
    rmtree(where)           # and NO `git worktree prune`
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): parked with --no-push "
            "on Falcon and no worktree on that branch here, but a stale "
            f"worktree registration for it is still recorded at {where} — "
            f"clear it with `git -C {atlas} worktree prune`; only that "
            "workstation has the WIP commit, so nothing here brings it back — "
            "park it again from there") in result.stdout
    assert "brings it back" in result.stdout and "`resume Atlas`" not in result.stdout


def test_an_unreadable_pushed_with_no_worktree_here_never_names_resume(
        atlas, home):
    """The same note, on the arm above: with no worktree here, `pushed:`
    valueless fell past the `= false` test into "`resume Atlas` brings it
    back" — the exit `resume.sh` refuses this record for. Whether the parked
    commit ever left that workstation cannot be read either, so the line says
    that instead of asserting it, and the exit is the one that works: park it
    again from there, which writes the record afresh."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed="", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): its `pushed:` has no "
            "value, which is neither true nor false, and no worktree on that "
            "branch here; whether its parked commit ever left Falcon cannot be "
            "read, and `resume` refuses a leg whose `pushed:` is not true, so "
            "nothing here brings it back — park it again from there, which "
            "writes the record afresh") in result.stdout
    assert "`resume Atlas` brings it back" not in result.stdout

    # And with a stale registration left behind: the prune is named first,
    # exactly as it is for a `--no-push` record, and `resume` still is not.
    where = parked_worktree(atlas, "001-a-thing")
    feature_worktree(atlas, "001-a-thing", where)
    rmtree(where)           # and NO `git worktree prune`
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): its `pushed:` has no "
            "value, which is neither true nor false, and no worktree on that "
            "branch here, but a stale worktree registration for it is still "
            f"recorded at {where} — clear it with `git -C {atlas} worktree "
            "prune`; whether its parked commit ever left Falcon cannot be "
            "read, and `resume` refuses a leg whose `pushed:` is not true, so "
            "nothing here brings it back — park it again from there, which "
            "writes the record afresh") in result.stdout
    assert "`resume Atlas`" not in result.stdout


def test_no_pushed_key_with_no_worktree_here_never_names_resume(atlas, home):
    """The same pair of arms for the state the independent review of #19
    named on 2026-09-11: with no `pushed:` key and no worktree here, the leg
    had no row at all, so `status` said nothing — not even the `resume
    <Name>` line the missing key would otherwise have fallen into. Now it is
    read the way `resume.sh` judges it — RR6 is `[ "$pushed" != true ]`, and
    an absent key is `false` to workBenches before #60 (ec2b450) and the
    empty string under #60, neither of them `true`: nothing here brings it
    back either way, and the exit is the workstation that parked it.

    And where a stale registration is left behind, the prune is named FIRST,
    exactly as it is for a `--no-push` record and for an unreadable value —
    `resume` cannot recreate a worktree git still believes it has, and it is
    not the exit here in any case."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed=None, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): the record has no "
            "`pushed:` for that leg, and no worktree on that branch here; "
            "whether its parked commit ever left Falcon cannot be read, and "
            "`resume` refuses a leg whose record has no `pushed:`, so "
            "nothing here brings it back — park it again from there, which "
            "writes the record afresh") in result.stdout
    assert "`resume Atlas` brings it back" not in result.stdout

    # And with a stale registration left behind: the prune first, and
    # `resume` still not named.
    where = parked_worktree(atlas, "001-a-thing")
    feature_worktree(atlas, "001-a-thing", where)
    rmtree(where)           # and NO `git worktree prune`
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): the record has no "
            "`pushed:` for that leg, and no worktree on that branch here, but "
            "a stale worktree registration for it is still recorded at "
            f"{where} — clear it with `git -C {atlas} worktree prune`; whether "
            "its parked commit ever left Falcon cannot be read, and `resume` "
            "refuses a leg whose record has no `pushed:`, so nothing here "
            "brings it back — park it again from there, which writes the "
            "record afresh") in result.stdout
    assert "`resume Atlas`" not in result.stdout


def test_a_record_that_names_no_parked_commit_never_names_resume(atlas, home):
    """Note 7 of the independent review of #20, 2026-09-11, recorded there as
    out of scope: with `pushed: true` and NO `parked_commit:` for the leg,
    `check_parked_leg`'s `[ -n "$commit" ] || return 0` sat AFTER the
    no-worktree arm, so the line was "no worktree on that branch here; parked
    … — `resume Atlas` brings it back" — and the real `resume.sh` refuses that
    record: RR6 passes on `pushed: true`, RR4 and RR3 find nothing already
    there, RR2 finds the branch on origin, and RR1 compares origin's tip with
    the parked commit, which an absent one never equals ("has moved since it
    was parked", exit 2, verified against the extension the same day, with
    the empty commit printing as a gap in its own report). Naming an exit
    that cannot work is the one
    thing this layer's rule forbids, so the state gets a line of its own, and
    the exit is the park that writes the record afresh.

    And where a stale registration is left behind, the prune is named FIRST,
    exactly as it is for `--no-push` and for an unreadable `pushed:`."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit="",
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): the record names no "
            "parked commit for that leg, and no worktree on that branch here; "
            "`resume` matches origin's tip against the parked commit before it "
            "recreates anything, an absent one never matches, and it refuses "
            "the leg as having moved on since it was parked, so nothing here "
            "brings it back — park it again from Falcon, which writes the "
            "record afresh") in result.stdout
    assert "`resume Atlas` brings it back" not in result.stdout

    where = parked_worktree(atlas, "001-a-thing")
    feature_worktree(atlas, "001-a-thing", where)
    rmtree(where)           # and NO `git worktree prune`
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): the record names no "
            "parked commit for that leg, and no worktree on that branch here, "
            "but a stale worktree registration for it is still recorded at "
            f"{where} — clear it with `git -C {atlas} worktree prune`; "
            "`resume` matches origin's tip against the parked commit before it "
            "recreates anything, an absent one never matches, and it refuses "
            "the leg as having moved on since it was parked, so nothing here "
            "brings it back — park it again from Falcon, which writes the "
            "record afresh") in result.stdout
    assert "`resume Atlas`" not in result.stdout


def test_a_record_that_names_no_parked_commit_still_reads_the_worktree_here(
        atlas, home):
    """The same hole from its other side, and the half that was pure silence:
    with a worktree on that branch here, the `return 0` skipped the three tip
    arms — the only thing this layer says about a worktree that IS here — and
    `status` exited 0 with nothing said about the record at all.

    Those arms cannot run: there is nothing to compare the tip WITH, and the
    empty string is not a commit — `cat-file -e "^{commit}"` fails on it, so
    without this arm the layer would print "its parked commit  is not here",
    a reason invented for a commit the record never named. So the line says what
    cannot be compared and names no refusal — `resume.sh`'s RR4 calls a leg
    whose worktree is already at the path it computes recreated and only
    warns, "the parked WIP was NOT un-committed" — and the exit is the
    moved-on arm's: park again, from the workstation the worktree is on.

    Under `--fetch` it says the same thing, because no fetch can bring back a
    commit the record does not name."""
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit="",
           parked_on="Falcon")
    for extra in ([], ["--fetch"]):
        result = run(STATUS, *extra, "Atlas", home=home)
        assert result.returncode == 1, result.stdout + result.stderr
        assert ("    - parked feature 001-a-thing (repo leg): the record names "
                "no parked commit for that leg, so there is nothing to read "
                "this worktree's tip against; whether it moved on, fell behind "
                "or diverged since it was parked cannot be told here — park "
                "again before leaving, which writes that leg's parked commit"
                ) in result.stdout
        for guess in ("moved on since it was parked", "is BEHIND the parked",
                      "diverged from the parked commit", "is not here"):
            assert guess not in result.stdout, result.stdout


def test_a_branch_this_clone_has_no_origin_ref_for_is_named_beside_resume(
        atlas, home):
    """The independent review of #21, 2026-09-11, recorded there as out of
    scope: "if origin has lost the branch, `resume.sh` refuses first at RR2 —
    'Error: `<branch>` is no longer on origin in the `<role>` leg' — with a
    different remedy paragraph; `check_parked_leg` never reads
    `origin/<branch>` for this leg, so it cannot tell."

    IT STILL CANNOT TELL WITHOUT A FETCH, and that is the whole of what this
    line says. RR2's test is a REF in the leg's repository — it fetches
    `+refs/heads/<branch>:refs/remotes/origin/<branch>` first and then reads
    it — so the question here is the local layer's own `has_ref`, AS OF THE
    LAST FETCH, and a missing ref reads two ways: a branch origin has lost,
    or a branch pushed on another workstation since this clone last fetched,
    which is the ORDINARY state of a feature parked elsewhere and one
    `resume` fetches and brings back. So the exit stays and the other reading
    is named beside it, with the one flag that settles them.

    With the branch really on origin the line is the one it always was, byte
    for byte: that is the state the promise belongs to."""
    checkout = workspace_config(home)
    origin_has_branch(atlas, "001-a-thing")
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == [
        "- parked feature 001-a-thing (repo leg): no worktree on that branch "
        "here; parked 2026-09-10T20:00:00Z on Falcon — `resume Atlas` brings "
        "it back"], findings

    # And with no `origin/001-a-thing` here, the same line plus the reading
    # it cannot rule out — RR2's own sentence, and the flag that settles it.
    drop_from_origin(atlas, "001-a-thing")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == [
        "- parked feature 001-a-thing (repo leg): no worktree on that branch "
        "here; parked 2026-09-10T20:00:00Z on Falcon — `resume Atlas` brings "
        "it back, unless origin has lost that branch: there is no "
        "`origin/001-a-thing` here as of the last fetch, and `resume` "
        "refuses a leg whose branch is not on origin, taking the WHOLE "
        "feature with it (\"001-a-thing is no longer on origin in the repo "
        "leg\") — `status --fetch` settles which"], findings


def test_under_fetch_a_branch_origin_has_lost_names_rr2_and_not_resume(
        atlas, home):
    """After a fetch that WORKED in that repository there is nothing left to
    settle: origin has not got the branch, and `resume` refuses the WHOLE
    feature at RR2 before it compares any commit. Verified against the
    extension on 2026-09-12 — a scratch single-shape estate, the branch
    deleted in the bare and pruned in the clone — which answered "Error:
    001-a-thing is no longer on origin in the repo leg; that feature was NOT
    recreated", then the manifest's recorded commit, "If the feature landed,
    delete its entry: … remove the `- branch: 001-a-thing` block", "If it was
    deleted by mistake, push it again from the workstation that parked it",
    "REFUSED: 001-a-thing — gone from origin", exit 2.

    BOTH ITS EXITS ARE THE LINE'S, because they are not one and neither is
    the re-park every other exception in this layer ends in: a feature that
    landed is a record entry to delete, and a branch deleted by mistake is a
    branch to push again."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    git("worktree", "remove", str(where), cwd=atlas)
    git("branch", "-q", "-D", "001-a-thing", cwd=atlas)
    git("push", "-q", "origin", "--delete", "001-a-thing", cwd=atlas)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here, parked 2026-09-10T20:00:00Z on Falcon, and no "
            "`origin/001-a-thing` here after this run's fetch: origin has not "
            "got that branch, so `resume` refuses the WHOLE feature for it, "
            "\"001-a-thing is no longer on origin in the repo leg\", and "
            "nothing here brings it back — the exits are to delete its "
            "`- branch: 001-a-thing` block from the record where the feature "
            "landed, or to push the branch again from Falcon where it went "
            "by mistake") in result.stdout
    assert "`resume Atlas`" not in result.stdout
    assert "status --fetch` settles which" not in result.stdout, (
        "the fetch settled it; there is nothing left for the flag to answer")


def test_a_gone_branch_names_the_stale_registration_that_blocks_it_too(
        atlas, home):
    """The prune is still the person's to run — the registration is a state
    of this disk, and `resume` is blocked by it whatever origin has — so it
    is named first and the refusal after it, exactly as the `--no-push` and
    absent-commit arms name it."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    rmtree(where)                        # and NO `git worktree prune`
    git("push", "-q", "origin", "--delete", "001-a-thing", cwd=atlas)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            f"branch here, but a stale worktree registration for it is still "
            f"recorded at {where} — clear it with `git -C {atlas} worktree "
            "prune`; and no `origin/001-a-thing` here after this run's fetch, "
            "so origin has not got that branch and `resume` refuses the WHOLE "
            "feature for it, \"001-a-thing is no longer on origin in the repo "
            "leg\" — nothing here brings it back: the exits are to delete its "
            "`- branch: 001-a-thing` block from the record where the feature "
            "landed, or to push the branch again from Falcon where it went by "
            "mistake") in result.stdout
    assert "`resume Atlas`" not in result.stdout


def test_under_fetch_a_gone_branch_outranks_the_absent_parked_commit(
        atlas, home):
    """RR2 IS BEFORE RR1, so a record that names no parked commit AND whose
    branch origin has lost is refused for the branch, not for the commit.
    Verified against the extension on 2026-09-12 on that same scratch estate:
    with the parked commit left out and the branch deleted on origin, it
    answered "Error: 001-a-thing is no longer on origin in the repo leg" —
    "The manifest recorded it at , parked …" — and not "has moved since it
    was parked", which is what it answers when origin still has the branch.

    Without a fetch the two readings of the missing ref are not settled, so
    the absent-commit arm keeps the line it had: that one is true whenever
    origin does still have the branch, and this layer does not choose."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit="",
           parked_on="Falcon")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("no `origin/001-a-thing` here after this run's fetch: origin has "
            "not got that branch, so `resume` refuses the WHOLE feature for "
            "it") in result.stdout
    assert "an absent one never matches" not in result.stdout, result.stdout

    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): the record names no "
            "parked commit for that leg, and no worktree on that branch here; "
            "`resume` matches origin's tip against the parked commit before "
            "it recreates anything, an absent one never matches") in \
        result.stdout


def test_the_gone_branch_reading_stops_where_resume_s_own_order_does(
        atlas, home):
    """`resume.sh` reads RR6, then RR4, RR3, RR2 — and `collect_legs` before
    all of them — so this reading is the fourth thing to speak, not the
    first, and three states of the same missing ref keep the lines they had.

    A WORKTREE HERE is RR4's, not RR2's: with the worktree at the path it
    computes, the extension answered "[specify] 001-a-thing (repo): worktree
    already registered at …; left as it is" and exited 0 with the branch gone
    from origin (verified 2026-09-12), so the tip arms go on saying what they
    said and nothing here mentions origin. A FEATURE `collect_legs` REFUSES
    WHOLE never reaches RR2 at all. And a leg RR6 refuses — `--no-push` — is
    refused before origin is read."""
    checkout = workspace_config(home)
    # The reading itself, so this test bites: no worktree, branch gone.
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert "is no longer on origin in the repo leg" in result.stdout

    # RR4: a worktree here, and the tip arms' line alone.
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    (where / "more.md").write_text("more\n", encoding="utf-8")
    commit_all(where, "more work")
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    git("push", "-q", "origin", "--delete", "001-a-thing", cwd=atlas)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): moved on since it "
            f"was parked, 1 commit(s) after {tip[:7]} — park again before "
            "leaving") in result.stdout
    assert "is no longer on origin" not in result.stdout, result.stdout
    assert "`resume Atlas`" not in result.stdout

    # `collect_legs`: a role this root does not mount, and no worktree.
    git("worktree", "remove", "--force", str(where), cwd=atlas)
    git("branch", "-q", "-D", "001-a-thing", cwd=atlas)
    record(checkout, "atlas", branch="001-a-thing", role="nope",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (nope leg): the record names a "
            "leg this root does not mount here;") in result.stdout
    assert "is no longer on origin" not in result.stdout, result.stdout

    # RR6: `--no-push`, refused before origin is read.
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=FAKE_SHA, parked_on="Falcon", pushed="false")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): parked with "
            "--no-push on Falcon and no worktree on that branch here; only "
            "that workstation has the WIP commit, so nothing here brings it "
            "back — park it again from there") in result.stdout
    assert "is no longer on origin" not in result.stdout, result.stdout


def test_a_caveat_after_a_fetch_that_failed_here_does_not_name_the_flag(
        atlas, home):
    """The independent review of this branch, 2026-09-12, verbatim: "Under
    --fetch where the fetch FAILED in that repository, the caveat tells the
    person to run the flag they just ran."

    `fetched_ok_at` is false for three different runs — one made without the
    flag, one whose fetch in THIS repository failed, and one that never
    fetched here at all — and only the first of them is answered by `status
    --fetch`. The row above has already said the fetch failed and that what
    follows is as of the last fetch that worked; the caveat says that the
    reading under it is one of those things, rather than naming a command
    that has just been run and settled nothing."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=FAKE_SHA, parked_on="Falcon")
    git("remote", "set-url", "origin", str(home / "nowhere" / "Atlas.git"),
        cwd=atlas)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    - fetch failed: " in result.stdout
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here; parked 2026-09-10T20:00:00Z on Falcon — `resume "
            "Atlas` brings it back, unless origin has lost that branch: there "
            "is no `origin/001-a-thing` here as of the last fetch, and "
            "`resume` refuses a leg whose branch is not on origin, taking the "
            "WHOLE feature with it (\"001-a-thing is no longer on origin in "
            "the repo leg\") — the fetch this run made there failed, so "
            "nothing has settled it") in result.stdout
    assert "settles which" not in result.stdout, (
        "the flag was run; it is not what is left to run")

    # AND WITHOUT THE FLAG THE SAME RECORD KEEPS THE FLAG, because there the
    # fetch that would settle it has not been made: the clause is about THIS
    # RUN's fetch and not about the URL.
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "— `status --fetch` settles which" in result.stdout
    assert "the fetch this run made there failed" not in result.stdout


CAVEAT_HEAD = ("no worktree on that branch here; parked 2026-09-10T20:00:00Z "
               "on Falcon — `resume {name}` brings it back, unless origin has "
               "lost that branch: there is no `origin/001-a-thing` here as of "
               "the last fetch, and `resume` refuses a leg whose branch is not "
               "on origin, taking the WHOLE feature with it (\"001-a-thing is "
               "no longer on origin in the {role} leg\") — ")


def test_a_caveat_where_no_fetch_could_be_made_says_so_and_not_that_one_failed(
        atlas, trio, home):
    """Copilot's second round on #23, verbatim: "`fetch_tried_at` is true for
    every repository entered by the pre-pass, including a readable repository
    where `fetch_remote` returned early because no `origin` remote exists. In
    that case this message says "the fetch this run made there failed" even
    though no fetch was attempted, which makes the new diagnostic inaccurate."

    THE STORE HELD FOUR STATES IN ONE FLAG. `fetch_remote` returns before it
    runs anything for a repository git cannot read and for one with no
    `origin` remote, and the pre-pass stores an entry for both — so "is there
    an entry" said yes about a repository nothing was fetched in, and this
    caveat contradicted the row two lines above it on the same report, which
    had just said "no remote named origin, so nothing could be fetched".
    `FETCH_STATE_AT` carries `fetch_remote`'s own word now, and the clause is
    the one that is true of this run: a fetch that failed, a repository with
    no remote to ask, one that could not be read, or — the flag's own case —
    no fetch there at all."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=FAKE_SHA, parked_on="Falcon")
    git("remote", "remove", "origin", cwd=atlas)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - fetch: no remote named origin, so nothing could be fetched"
            ) in result.stdout
    assert ("    - parked feature 001-a-thing (repo leg): "
            + CAVEAT_HEAD.format(name="Atlas", role="repo")
            + "that repository has no `origin` remote for this run's fetch to "
            "have asked, so nothing has settled it") in result.stdout
    assert "the fetch this run made there failed" not in result.stdout, (
        "a fetch that never ran was reported as one that failed")
    assert "settles which" not in result.stdout, (
        "the flag was run, and there is no remote for it to ask")

    # A LEG, WHICH IS THE SHAPE THE COMMENT NAMES, in the checkout whose shape
    # maps `spec`: the record layer asks the store about the path
    # `project.yaml` gives the role, and the answer is that leg's own.
    record(checkout, "trio", branch="001-a-thing", role="spec",
           commit=FAKE_SHA, parked_on="Falcon", root="Trio")
    git("remote", "remove", "origin", cwd=trio / "spec")
    result = run(STATUS, "--fetch", "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (spec leg): "
            + CAVEAT_HEAD.format(name="Trio", role="spec")
            + "that repository has no `origin` remote for this run's fetch to "
            "have asked, so nothing has settled it") in result.stdout
    assert "the fetch this run made there failed" not in result.stdout

    # AND A REPOSITORY GIT CANNOT READ AT ALL is the other early return, and
    # not the same sentence: nothing is wrong with its remotes, and the row
    # above it says what is.
    git("remote", "add", "origin", str(trio / "spec"), cwd=trio / "spec")
    rmtree(trio / ".git" / "modules" / "spec")
    result = run(STATUS, "--fetch", "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - fetch: not a readable git repository (a gitfile whose "
            "gitdir is gone?), so nothing could be fetched") in result.stdout
    assert ("    - parked feature 001-a-thing (spec leg): "
            + CAVEAT_HEAD.format(name="Trio", role="spec")
            + "that repository could not be read this run, so no fetch was "
            "made there and nothing has settled it") in result.stdout
    assert "the fetch this run made there failed" not in result.stdout


def test_a_caveat_in_a_repository_this_runs_fetch_never_listed_says_so(
        atlas, home, status_remotes):
    """Copilot's third round on #23, 2026-09-12, verbatim: "When `--fetch` is
    active, `fetch_state_at` can still be `none` for a mapped role path that
    `project.yaml` names but `estate_repos` did not enumerate (the code
    explicitly allows that path not to be one of the fetch-store entries).
    This fallback then tells the user to run `status --fetch`, even though
    that flag has already run and repeated runs will not fetch a path absent
    from `.gitmodules`; either fetch all mapped leg repositories or report
    that this repository was not included in the fetch."

    IT IS REAL, AND THE SECOND OF ITS TWO EXITS IS THE ONE TAKEN: `status
    --fetch`'s one write is bounded to the repositories the estate declares —
    the root and the legs of its `.gitmodules` — which is what AGENTS.md rule
    4, the README and the help all say, so the reading says what this run DID
    rather than widening what the flag does. The state is a `project.yaml`
    that mounts a leg where `.gitmodules` declares none: `load_repo_shape`
    maps the role onto that path and `collect_legs` hands it straight to
    `resume`, while the pre-pass never sees it and no rerun of the flag ever
    will.

    WITHOUT THE FLAG THE FLAG IS STILL THE ANSWER, which is the control under
    it: there the run has not asked at all, and what the flag settles is the
    root and the legs it lists."""
    checkout = workspace_config(home)
    code_leg_onto_the_spec_checkout(atlas, path_line="    path: docs\n")
    git("clone", "-q", str(status_remotes["Atlas"]["leg_bare"]),
        str(atlas / "docs"), cwd=atlas)
    record(checkout, "atlas", branch="001-a-thing", role="code",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (code leg): "
            + CAVEAT_HEAD.format(name="Atlas", role="code")
            + "this run's fetch did not reach that repository: it fetches the "
            "root and the legs `.gitmodules` declares, and `project.yaml` maps "
            "this role onto a path that is not one of them, so nothing has "
            "settled it") in result.stdout
    assert "settles which" not in result.stdout, (
        "the flag was run, and no rerun of it reaches a path `.gitmodules` "
        "does not declare")
    assert "fetched origin" not in " ".join(
        line for line in result.stdout.splitlines() if "docs" in line), (
        "the fetch stays bounded to the repositories the estate declares")

    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (code leg): "
            + CAVEAT_HEAD.format(name="Atlas", role="code")
            + "`status --fetch` settles which") in result.stdout
    assert "did not reach that repository" not in result.stdout


def test_a_leg_the_record_gives_no_role_is_a_finding_not_silence(atlas, home):
    """Note 8 of the independent review of #20, 2026-09-11, recorded there as
    out of scope: an empty `- role:` value. `record_rows` dropped such a leg —
    `[ -n "$role" ]` at both emit sites — so the record layer said nothing
    about it, while `workspace_load_project` CREATES that leg (its indent-10
    arm keys on `role` and assigns whatever the scalar is, empty or not) and
    `resume.sh`'s `collect_legs` then hits its `*) return 1`, refusing the
    WHOLE feature: "Error: 001-a-thing was parked from a single project and
    this checkout is single; that feature was NOT recreated", exit 2, verified
    against the extension the same day — a sentence about the SHAPE that says
    nothing about the role, which is what this line explains in advance.

    It is the ROOT's row, because no leg repository can be found for a leg
    with no role, and it is NOT the "does not mount here" arm: those words are
    true of `role: nope` and misleading here, where the record names no role
    to mount and the refusal is of the whole feature. It is answered before
    `leg_repo_for_role` is asked, too, because that function's last test for
    an empty role is `[ -d "$root/" ]` — always true — and it would hand back
    the root, reading the leg as if the record had named `repo`."""
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    path = record(checkout, "atlas", branch="001-a-thing", role="", commit=tip,
                  parked_on="Falcon")
    for extra in ([], ["--fetch"]):
        result = run(STATUS, *extra, "Atlas", home=home)
        assert result.returncode == 1, result.stdout + result.stderr
        assert ("    - parked feature 001-a-thing: a leg of it in the record "
                "has no role; `resume` maps each leg's role onto this checkout "
                "and refuses the WHOLE feature — the other legs with it — "
                "where one does not map, reporting it as a shape mismatch, so "
                "nothing here brings it back — park that feature again from "
                "the workstation that has it (the record says Falcon), which "
                "writes the roles this checkout's own shape has") in result.stdout
        assert "does not mount here" not in result.stdout
        assert "( leg)" not in result.stdout

    # The same record as a park that REFUSED the feature rewrites it —
    # `workspace_write_manifest` keeps `role:` when its value is empty, the
    # one leg key it does not drop — and it is the same empty role.
    path.write_text(path.read_text(encoding="utf-8").replace(
        "          - role: \n", '          - role: ""\n'), encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing: a leg of it in the record has "
            "no role;") in result.stdout

    # AND A LEG WITH NO `- role:` LINE AT ALL is not a LEG in either reader:
    # the loader's `[ "$key" = "role" ] || continue` starts none, and nothing
    # opens one here — that much the two readers agree about, and it is still
    # all that is held about the LINE: no leg-level finding names it. What
    # they did NOT agree about was the FEATURE, which this record leaves with
    # no legs at all and `collect_legs`'s closing `[ "${#LEG_ROLES[@]}" -gt
    # 0 ]` refuses whole for that ("REFUSED: 001-a-thing — shape mismatch",
    # exit 2, verified against the extension 2026-09-11) while this layer said
    # nothing. That per-FEATURE reading is done now, so the finding here is
    # the feature's — no leg named, because there is no leg to name.
    path.write_text(path.read_text(encoding="utf-8").replace(
        '          - role: ""\n', "          - nickname: x\n"), encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing: the record lists no leg for it;"
            ) in result.stdout
    assert "a leg of it in the record has no role" not in result.stdout, (
        "the LEG-level reading, for a line that is no leg to either reader")
    assert "does not mount here" not in result.stdout


def test_a_leg_with_no_role_does_not_take_the_legs_around_it_with_it(
        atlas, home):
    """The row goes out where the leg ENDS and `$open` — not the role's value
    — is what says a leg is open, so an empty role costs the record neither a
    leg before it nor one after it. Both of the others are read as they were,
    and the roleless one is read too.

    "As they were" is now "as they are": the `repo` leg with no worktree here
    is still READ and still first, and what its line says has changed —
    Copilot on #21, second round, 2026-09-11 — because `resume` refuses this
    whole feature and the line used to offer `resume Atlas` for it two lines
    under the one that says so. The `spec` leg's `--no-push` line is
    untouched, which is the other half of the same rule: an arm that already
    rules `resume` out needs no verdict to do it. Since the shape reading it
    is preceded by one more of the leg's own: this root is `single`, so
    `collect_legs` refuses a `spec` leg here too, and that is said before
    what `--no-push` means for a leg with a worktree — four lines, in the
    record's order, none of them naming `resume` as an exit."""
    checkout = workspace_config(home)
    leg = atlas / "spec"
    git("checkout", "-q", "main", cwd=leg)
    spec_tip = feature_worktree(leg, "001-a-thing", home / "Atlas-wt" /
                                "001-a-thing" / "spec")
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "            pushed: true\n",
        "            pushed: true\n"
        "          - role: \n"
        "            remote: origin\n"
        f"            parked_commit: {FAKE_SHA}\n"
        "            wip: true\n"
        "            wip_depth: 1\n"
        "            pushed: true\n"
        "          - role: spec\n"
        "            remote: origin\n"
        f"            parked_commit: {spec_tip}\n"
        "            wip: true\n"
        "            wip_depth: 1\n"
        "            pushed: false\n")
    path.write_text(text, encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 4, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (repo leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        "WHOLE feature, because a leg of it in the record has no role, so it "
        "does not bring this leg back — park that feature again from the "
        "workstation that has it (the record says Falcon)"), findings[0]
    assert findings[1].startswith(
        "- parked feature 001-a-thing: a leg of it in the record has no role;"
        ), findings[1]
    assert findings[2].startswith(
        "- parked feature 001-a-thing (spec leg): " + SHAPE_SPEC), findings[2]
    assert findings[3].startswith(
        "- parked feature 001-a-thing (spec leg): parked with --no-push on "
        "Falcon"), findings[3]
    assert "`resume Atlas`" not in result.stdout


def test_a_role_this_shape_does_not_mount_names_the_whole_feature_refusal(
        atlas, home):
    """The independent review of #21, 2026-09-11, nobody having ruled on it:
    a leg whose role this checkout's shape has not got drew "parked feature
    001-a-thing (nope leg): the record names a leg this root does not mount
    here" and stopped — no refusal, no exit, and it read as ONE leg of the
    feature going unread. `resume.sh`'s `collect_legs` maps every leg's role
    onto this checkout (`spec` and `code` only where `REPO_SHAPE` is
    three-leg, `repo` only where it is single, `*) return 1` for anything
    else) and takes the WHOLE FEATURE with the one that does not map: run
    against a scratch single-shape estate on 2026-09-11, `role: nope`
    answered "Error: 001-a-thing was parked from a single project and this
    checkout is single; that feature was NOT recreated", "REFUSED:
    001-a-thing — shape mismatch", exit 2 — the same refusal, in the same
    words about the SHAPE, that the empty-role arm above explains in
    advance.

    ONE REFUSAL FOR BOTH KINDS OF ROLE, because this arm cannot tell them
    apart: `leg_repo_for_role` returns nothing for a MISSPELLING (`nope`) and
    nothing for ANOTHER SHAPE'S ROLE (`code` here, `spec` in the family
    fixture's members), and `collect_legs` refuses both as a shape mismatch —
    the first at its `*) return 1`, the second at its own `[ "$REPO_SHAPE" =
    … ] || return 1`, both verified the same day. THE EXIT IS NOT ONE
    WORDING, though it was when this test was written (Copilot's first round
    on #23): a park from the workstation that has the feature writes the
    roles ITS shape has, and for `code` — a role the OTHER shape maps — that
    is the whole answer, the feature coming back in a checkout of that shape.
    For `nope` no checkout of either shape maps it, so the line says that
    first; the test for that split is its own, beside the `assembly` one.
    Promising a re-park alone would send somebody round the second loop for
    ever either way.

    AND ONLY FOR A ROLE THIS ROOT HAS NO REPOSITORY FOR, which is what
    proved the refusal before this checkout's SHAPE was read: `load_repo_shape`
    calls a checkout three-leg only where `project.yaml` is a
    `project-repo-schema` project manifest declaring both a `spec` and a
    `code` LEG — the leg, not its `path:`, which defaults to the role's own
    name — so a role this root can find no repository for is one
    `collect_legs` cannot map either way. The block at the end of this test
    is the one that changed with the shape reading, and its comment says
    why."""
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    for role, exits in (
            ("nope", "nor does any other checkout, of either shape, so the "
                     "one exit is to park that feature again from the "
                     "workstation that has it (the record says Falcon), which "
                     "writes the roles its own shape has — `park` writes "
                     "`spec` and `code` in a three-leg project and `repo` in "
                     "a single one, and never this word — and the feature "
                     "comes back in a checkout of that shape, which is this "
                     "one only where the two agree"),
            ("code", "park that feature again from the workstation that has "
                     "it (the record says Falcon), which writes the roles its "
                     "own shape has; where that shape is not this checkout's, "
                     "the feature comes back in a checkout of that shape, not "
                     "here")):
        record(checkout, "atlas", branch="001-a-thing", role=role, commit=tip,
               parked_on="Falcon")
        for extra in ([], ["--fetch"]):
            result = run(STATUS, *extra, "Atlas", home=home)
            assert result.returncode == 1, result.stdout + result.stderr
            assert (f"    - parked feature 001-a-thing ({role} leg): the record "
                    "names a leg this root does not mount here; `resume` maps "
                    "each leg's role onto this checkout and refuses the WHOLE "
                    "feature — the other legs with it — where one does not map, "
                    "reporting it as a shape mismatch, so nothing here brings it "
                    "back — " + exits) in result.stdout

    # With no `parked_on:` the exit still names the workstation, and says the
    # record does not say which — the empty-role arm's words for the same gap.
    record(checkout, "atlas", branch="001-a-thing", role="nope", commit=tip,
           parked_on="")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("park that feature again from the workstation that has it (the "
            "record does not say where)") in result.stdout

    # AND A LEG THIS ROOT MOUNTS THAT IS NOT A CHECKOUT is read against the
    # SHAPE, which is what this layer could not do when this block was
    # written: Atlas is `single` — `kind: project-manifest`, no `schema:`
    # line, an `assembly` leg and a `spec` leg and no `code` one — so
    # `collect_legs` refuses a `spec` leg here whatever that directory holds,
    # and "the record names a leg this root does not mount here" would send
    # somebody to `make bootstrap` for a feature no bootstrap brings back.
    # THE HALF THIS USED TO HOLD IS HELD WHERE IT IS TRUE: in a root whose
    # shape DOES map the role, an unfetched leg claims no refusal and keeps
    # that sentence — `test_a_three_leg_checkout_maps_spec_and_code_and_
    # nothing_else` below, in the three-leg fixture.
    spec = atlas / "spec"
    rmtree(spec)
    spec.mkdir()
    record(checkout, "atlas", branch="001-a-thing", role="spec", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (spec leg): " + SHAPE_SPEC
            ) in result.stdout
    assert "does not mount here" not in result.stdout, result.stdout


def test_a_leg_this_manifest_declares_with_no_path_is_mounted_at_its_role(
        atlas, home):
    """The independent review of this branch, 2026-09-12. `leg_repo_for_role`
    learned a role's path from a `path:` key in `project.yaml` or a same-named
    directory and answered NOTHING otherwise — while `git-common.sh`'s
    `_shape_record_leg` DEFAULTS the path of the two legs it knows: `spec)
    _SHAPE_LEG_SPEC_PATH="${path:-spec}"` and `code) … "${path:-code}"`. So a
    root that declares `- role: spec` with no `path:`, and whose `spec/` is
    not checked out, drew the whole-feature refusal above — a line `resume`
    never prints there. `load_repo_shape` calls that manifest three-leg, and
    `resume.sh` refuses the whole ESTATE before it reads a feature at all:
    "Error: the spec leg 'spec' is not an initialised Git checkout at
    '…/spec'. / Run 'git submodule update --init' (or 'make bootstrap') in the
    project root first.", exit 1 — neither the refusal that line claims nor
    either exit it offers.

    The role maps now, as it does at the other end, and what is left is the
    short line above: the leg is not mounted here, which is `make bootstrap`'s
    to place. This layer says that and stops."""
    checkout = workspace_config(home)
    manifest = atlas / "project.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace("kind: project-manifest\n",
                 "kind: project-manifest\nschema: project-repo-schema\n")
        .replace("  - role: spec\n"
                 f"    repository: {ORG}/Atlas-spec\n"
                 "    path: spec\n",
                 "  - role: spec\n"
                 f"    repository: {ORG}/Atlas-spec\n"
                 "  - role: code\n"
                 f"    repository: {ORG}/Atlas-code\n"),
        encoding="utf-8")
    assert "path: spec" not in manifest.read_text(encoding="utf-8"), (
        "the leg still has a path; the test is moot")
    rmtree(atlas / "spec")      # declared, and not checked out here
    record(checkout, "atlas", branch="001-a-thing", role="spec",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == [
        "- parked feature 001-a-thing (spec leg): the record names a leg this "
        "root does not mount here"], findings
    assert "refuses the WHOLE feature" not in result.stdout, (
        "a refusal this layer cannot prove, and not the one `resume` makes")


def test_an_unmountable_role_is_read_beside_the_legs_it_refuses_with(
        atlas, home):
    """The refusal is of the FEATURE, so the good leg beside it is read too
    and both lines print — the leg's own state, and the whole-feature refusal
    the record's other leg costs it. The order is the record's, and the good
    leg's line says what the feature's verdict makes of it rather than
    offering `resume` for a feature `resume` throws out."""
    checkout = workspace_config(home)
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon")
    path.write_text(path.read_text(encoding="utf-8").replace(
        "            pushed: true\n",
        "            pushed: true\n"
        "          - role: nope\n"
        "            remote: origin\n"
        f"            parked_commit: {FAKE_SHA}\n"
        "            wip: true\n"
        "            wip_depth: 1\n"
        "            pushed: true\n"), encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (repo leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        "WHOLE feature, because its `nope` leg names a role this root does "
        "not mount, so it does not bring this leg back — park that feature "
        "again from the workstation that has it (the record says Falcon)"
        ), findings[0]
    assert findings[1].startswith(
        "- parked feature 001-a-thing (nope leg): the record names a leg this "
        "root does not mount here; `resume` maps each leg's role onto this "
        "checkout and refuses the WHOLE feature"), findings[1]
    assert "`resume Atlas`" not in result.stdout


#: The first clause of a `spec` leg's finding in a SINGLE root, which is
#: every root this suite's Atlas fixture builds: `kind: project-manifest`, no
#: `schema:` line, an `assembly` leg and a `spec` leg and no `code` one.
SHAPE_SPEC = ("`resume` maps the role `spec` onto a three-leg checkout only, "
              "and this one is single (its `project.yaml` declares no "
              "`schema: project-repo-schema` and no `code` leg), so it "
              "refuses the WHOLE feature")

#: The rest of the `spec`-in-a-single-root finding, whose first clause two
#: other tests read as `SHAPE_SPEC`: the refusal both shape findings share,
#: the disagreement this suite's `record()` always writes (`shape:
#: three-leg`), and the exit. THE DISAGREEMENT IS LAST since the independent
#: verification of this branch, 2026-09-12: the `*)` exit opens "nor does any
#: other checkout, of either shape", which answers "nothing here brings it
#: back", and spliced between the two the disagreement left that "nor" denying
#: "not one this layer can settle". The three pieces are the same; the order
#: is the reading.
MISMATCH = (" — the other legs with it — reporting it as a shape mismatch, "
            "and nothing here brings it back")
DISAGREE_S = ("; the record calls the project three-leg where this checkout "
              "is single, which is the disagreement `resume` reports and not "
              "one this layer can settle")
EXIT_S = (" — park that feature again from the workstation that has it (the "
          "record says Eagle), which writes the roles its own shape has; "
          "where that shape is not this checkout's, the feature comes back "
          "in a checkout of that shape, not here")

#: The three pieces of the `assembly` finding, which two tests read: the
#: refusal, the clause a record that disagrees about the shape adds, and the
#: exit. Split because the second phase below is the same line without the
#: middle, and a copy of 60 words would hide that.
ASSEMBLY = (
    "- parked feature 001-a-thing (assembly leg): `resume` maps the role "
    "`assembly` onto no checkout of either shape — it knows `spec` and "
    "`code` in a three-leg project and `repo` in a single one — and this one "
    "is single (its `project.yaml` declares no `schema: project-repo-schema` "
    "and no `code` leg), so it refuses the WHOLE feature — the other legs with it — reporting "
    "it as a shape mismatch, and nothing here brings it back")
DISAGREE = ("; the record calls the project three-leg where this checkout is "
            "single, which is the disagreement `resume` reports and not one "
            "this layer can settle")
EXIT = (
    " — park that feature again from the workstation that has it (the record "
    "says Falcon), which writes the roles its own shape has; where that shape "
    "is not this checkout's, the feature comes back in a checkout of that "
    "shape, not here")

#: AND THE EXIT FOR A ROLE OF NEITHER SHAPE IS NOT THAT ONE (Copilot's first
#: round on #23): `EXIT` above ends by naming the checkout the feature comes
#: back in, which is the right thing to say about `spec` in a single root and
#: the wrong thing to leave a person with about `assembly`, where no checkout
#: of either shape resumes the record as it stands. So the `*)` roles get
#: their own, which says that first and then the one thing that changes it.
EXIT_NEITHER = (
    " — nor does any other checkout, of either shape, so the one exit is to "
    "park that feature again from the workstation that has it (the record "
    "says Falcon), which writes the roles its own shape has — `park` writes "
    "`spec` and `code` in a three-leg project and `repo` in a single one, and "
    "never this word — and the feature comes back in a checkout of that "
    "shape, which is this one only where the two agree")


def test_a_role_resume_maps_in_no_shape_costs_the_whole_feature(atlas, home):
    """The reading the feature-level commit recorded and did not take: "a
    role this root DOES mount that `collect_legs` refuses anyway —
    `assembly`, or `spec` in a root whose `project.yaml` declares no `code`
    leg, which `load_repo_shape` therefore calls `single` — for which
    `leg_repo_for_role` hands back a repository, so the leg is read against
    disk and nothing here mentions the refusal."

    `assembly` is the role that proves it is not a misspelling: the three-leg
    SHAPE has it — it is the assembly root itself, `path: "."` in this
    fixture's own `project.yaml` — and `collect_legs` maps it in NEITHER
    shape, because the root's worktree is the `repo` leg's. Run against the
    extension on 2026-09-12, on a scratch estate shaped like this fixture (an
    `assembly` leg at `.` and a `spec` leg at `spec/`, no `schema:` line and
    no `code` leg): "Error: 001-a-thing was parked from a three-leg project
    and this checkout is single; that feature was NOT recreated", "REFUSED:
    001-a-thing — shape mismatch", exit 2.

    THE SENTENCE `resume` PRINTS NAMES NO ROLE AND CAN CONTRADICT ITSELF —
    "parked from a single project and this checkout is single" where the
    record agrees — so this line names the role, the shape this checkout is
    and WHY it is that shape, in `load_repo_shape`'s own terms. The record's
    own `shape:` is held against it and NOT judged: which of the two is right
    is not readable from either file."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="assembly",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == [ASSEMBLY + EXIT_NEITHER + DISAGREE], findings
    assert "`resume Atlas`" not in result.stdout

    # AND WHERE THE RECORD AGREES WITH THIS CHECKOUT there is nothing to hold
    # against it: the same refusal, without the clause.
    path = checkout / "workspaces" / ORG / "atlas.yaml"
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("shape: three-leg", "shape: single"),
                    encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == [ASSEMBLY + EXIT_NEITHER], findings

    # AND A WORD THAT MERELY MATCHES A DIRECTORY reaches the same arm by the
    # other route: `leg_repo_for_role`'s last case answers `docs` with
    # `<root>/docs` once that directory exists, so the "does not mount here"
    # arm above cannot see it either, and `collect_legs` maps it no better
    # than `assembly` — its `*) return 1` is one case for both. (An empty
    # directory is nothing to git, so the root is not dirty for it.)
    (atlas / "docs").mkdir()
    record(checkout, "atlas", branch="001-a-thing", role="docs",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (docs leg): `resume` maps the "
            "role `docs` onto no checkout of either shape — it knows `spec` "
            "and `code` in a three-leg project and `repo` in a single one — "
            "and this one is single (its `project.yaml` declares no `schema: "
            "project-repo-schema` and no `code` leg), so it refuses the WHOLE "
            "feature") in result.stdout
    assert "does not mount here" not in result.stdout, result.stdout


def test_a_role_of_neither_shape_is_offered_no_checkout_of_the_other(
        atlas, trio, home):
    """Copilot's first round on #23, verbatim: "for roles such as `assembly`
    or `docs`, `role_shape_long` correctly says that `resume` maps the role
    onto no checkout of either shape, but this common suffix still says the
    feature can come back in a checkout of the other shape … contradicts the
    new help/README wording that a role of neither shape has no resumable
    checkout."

    THE RE-PARK IS NOT IMPOSSIBLE, which is the half of that note to
    disagree with: the suffix's "that shape" is the WORKSTATION's, named two
    clauses earlier, and `park.sh`'s `build_legs` is `LEG_ROLES=("spec"
    "code")` in a three-leg root and `("repo")` in a single one — so the park
    it names does write a role some checkout maps, and this suite's own
    end-to-end run of `resume.sh` on a `code` leg brought the feature back,
    exit 0. WHAT WAS MISSING IS THE OTHER HALF OF WHAT THE HELP AND THE
    README ALREADY SAY: "where the role is really another shape's, only a
    checkout of that shape, and where it is NEITHER shape's, no checkout at
    all". The suffix said the first of those to both kinds, so a person
    reading `assembly` was left with a checkout somewhere that resumes this
    record, and there is none: run against the extension on 2026-09-12, both
    `role: assembly` and `role: docs` in a real three-leg root — both legs
    mounted, the four conditions met — answered "Error: 001-a-thing was
    parked from a three-leg project and this checkout is three-leg; that
    feature was NOT recreated", "REFUSED: 001-a-thing — shape mismatch",
    exit 2, which is the refusal both words already draw in a single root.
    Refused in BOTH shapes is a record no checkout brings back.

    IT REACHES THE "DOES NOT MOUNT HERE" ARM TOO, because a role of neither
    shape gets there whenever it matches no directory (`nope`) — while a
    `spec` or a `code` that arm sees IS another shape's role and keeps the
    suffix it had, byte for byte."""
    checkout = workspace_config(home)
    for role in ("assembly", "docs", "nope"):
        if role == "docs":
            (atlas / "docs").mkdir()
        record(checkout, "atlas", branch="001-a-thing", role=role,
               commit=FAKE_SHA, parked_on="Falcon")
        result = run(STATUS, "Atlas", home=home)
        assert result.returncode == 1, result.stdout + result.stderr
        findings = [line.strip() for line in result.stdout.splitlines()
                    if line.strip().startswith("- parked feature")]
        assert len(findings) == 1, findings
        # THE EXIT IS LAST WHERE THERE IS NO DISAGREEMENT TO REPORT, and the
        # disagreement follows it where there is: `assembly` and `docs` reach
        # the SHAPE arm, whose line holds the record's `shape:` against this
        # checkout's, while `nope` matches no directory and reaches the mount
        # arm, which has no such clause.
        tail = EXIT_NEITHER[3:] + ("" if role == "nope" else DISAGREE)
        assert findings[0].endswith(tail), findings[0]
        assert "comes back in a checkout of that shape, not here" not in \
            result.stdout, (
                "a role no shape maps was still offered the other shape")
        assert "`resume Atlas`" not in result.stdout

    # ANOTHER SHAPE'S ROLE KEEPS THE EXIT IT HAD, which is the line this one
    # is not: `spec` reaches the shape arm and `code` the mount arm, and both
    # really do come back in a checkout of the shape that maps them.
    for role in ("spec", "code"):
        record(checkout, "atlas", branch="001-a-thing", role=role,
               commit=FAKE_SHA, parked_on="Falcon")
        result = run(STATUS, "Atlas", home=home)
        assert result.returncode == 1, result.stdout + result.stderr
        assert ("park that feature again from the workstation that has it "
                "(the record says Falcon), which writes the roles its own "
                "shape has; where that shape is not this checkout's, the "
                "feature comes back in a checkout of that shape, not here"
                ) in result.stdout
        assert "nor does any other checkout" not in result.stdout

    # AND THE SHAPE IT IS REFUSED IN CHANGES NOTHING: `assembly` is the
    # three-leg shape's own root, and `resume` maps it there no better.
    checkout = workspace_config(home)
    record(checkout, "trio", branch="001-a-thing", role="assembly",
           commit=FAKE_SHA, parked_on="Falcon", root="Trio")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 1, findings
    assert findings[0].endswith(EXIT_NEITHER[3:]), findings[0]
    assert "`resume Trio`" not in result.stdout


def test_a_spec_leg_this_single_root_mounts_is_still_the_shape_refusal(
        atlas, home):
    """The other half of the same state, and the one that reads as fine: this
    root MOUNTS `spec`, `leg_repo_for_role` answers with its repository, the
    worktree is there at the parked commit — and `collect_legs` refuses the
    whole feature anyway, because `spec` maps onto a three-leg checkout only
    and this one is single. Verified against the extension the same day, in
    the same estate with the `spec` leg really mounted: "shape mismatch",
    exit 2. Before this reading `status` printed nothing at all here and
    exited 0.

    WITH A WORKTREE HERE THE ARMS BELOW STILL RUN, because they are about
    this workstation's own work and true whatever `collect_legs` does: the
    second half moves that worktree on, and both lines print, the refusal
    first."""
    checkout = workspace_config(home)
    leg = atlas / "spec"
    git("checkout", "-q", "main", cwd=leg)
    where = home / "Atlas-wt" / "001-s-thing" / "spec"
    tip = feature_worktree(leg, "001-s-thing", where)
    record(checkout, "atlas", branch="001-s-thing", role="spec", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == [
        "- parked feature 001-s-thing (spec leg): `resume` maps the role "
        "`spec` onto a three-leg checkout only, and this one is single (its "
        "`project.yaml` declares no `schema: project-repo-schema` and no "
        "`code` leg), so it refuses the WHOLE feature — the other legs with it — reporting it "
        "as a shape mismatch, and nothing here brings it back "
        "— park that feature again from the workstation that has it (the "
        "record says Falcon), which writes the roles its own shape has; "
        "where that shape is not this checkout's, the feature comes back in "
        "a checkout of that shape, not here; the record "
        "calls the project three-leg where this checkout is single, which is "
        "the disagreement `resume` reports and not one this layer can settle"
        ], findings

    (where / "more.md").write_text("more\n", encoding="utf-8")
    commit_all(where, "more work")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0].startswith(
        "- parked feature 001-s-thing (spec leg): `resume` maps the role "
        "`spec` onto a three-leg checkout only"), findings[0]
    assert findings[1] == (
        "- parked feature 001-s-thing (spec leg): moved on since it was "
        f"parked, 1 commit(s) after {tip[:7]} — park again before leaving"
        ), findings[1]


def test_a_repo_leg_in_a_three_leg_checkout_costs_the_whole_feature(
        trio, home):
    """The mirror image, and the one that needs a root of the other shape:
    `repo` maps onto a SINGLE checkout only. Verified against the extension
    on 2026-09-12 in a real three-leg scratch estate — `kind:
    project-manifest`, `schema: project-repo-schema`, both legs mounted —
    which answered "Error: 001-a-thing was parked from a three-leg project
    and this checkout is three-leg; that feature was NOT recreated",
    "REFUSED: 001-a-thing — shape mismatch", exit 2: the sentence that names
    the same shape twice and says nothing about the role, which is what this
    line exists to explain in advance.

    NO DISAGREEMENT CLAUSE HERE, because there is none: the record calls the
    project three-leg and so does this checkout. The record's `shape:` never
    decides anything at either end — `collect_legs` maps roles onto the shape
    of the CHECKOUT — and a line that read it as the reason would be wrong
    about both."""
    checkout = workspace_config(home)
    record(checkout, "trio", branch="001-a-thing", role="repo",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == [
        "- parked feature 001-a-thing (repo leg): `resume` maps the role "
        "`repo` onto a single checkout only, and this one is three-leg (its "
        "`project.yaml` declares both a `spec` and a `code` leg), so it "
        "refuses the WHOLE feature — the other legs with it — reporting it "
        "as a shape mismatch, and nothing here brings it back — park that "
        "feature again from the workstation that has it (the record says "
        "Falcon), which writes the roles its own shape has; where that shape "
        "is not this checkout's, the feature comes back in a checkout of "
        "that shape, not here"], findings
    assert "`resume Trio`" not in result.stdout


def test_a_three_leg_checkout_maps_spec_and_code_and_nothing_else(trio, home):
    """What the shape reading must NOT do, held in the root where the roles
    change places. `spec` maps here — the extension RESUMED that record on
    2026-09-12 in this shape — so a `spec` leg at its parked commit is silent
    exactly as a `repo` leg is in a single root; a `spec` leg this root
    mounts that is NOT A CHECKOUT keeps the sentence it had and claims no
    refusal, because `collect_legs` maps roles by name onto the paths
    `load_repo_shape` computed and never looks at the directory; and
    `assembly` is refused here too, which is the half that says the reading
    is about the ROLE and not about the shape it came from."""
    checkout = workspace_config(home)
    leg = trio / "spec"
    git("checkout", "-q", "main", cwd=leg)
    tip = feature_worktree(leg, "001-s-thing",
                           parked_worktree(trio, "001-s-thing", "spec"))
    record(checkout, "trio", branch="001-s-thing", role="spec", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "parked feature" not in result.stdout

    # A LEG THIS ROOT MOUNTS THAT IS NOT A CHECKOUT: `make bootstrap`'s, and
    # no refusal claimed — the half the single-shape fixture can no longer
    # hold, because there `spec` is refused for the shape whatever the
    # directory is.
    rmtree(leg)
    leg.mkdir()
    record(checkout, "trio", branch="001-s-thing", role="spec",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-s-thing (spec leg): the record names a "
            "leg this root does not mount here") in result.stdout
    assert "refuses the WHOLE feature" not in result.stdout, (
        "a refusal this layer cannot prove for a leg the shape does map")

    # And `assembly`, in the shape that has an assembly leg of its own.
    record(checkout, "trio", branch="001-a-thing", role="assembly",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (assembly leg): `resume` maps "
            "the role `assembly` onto no checkout of either shape — it knows "
            "`spec` and `code` in a three-leg project and `repo` in a single "
            "one — and this one is three-leg (its `project.yaml` declares "
            "both a `spec` and a `code` leg), so it refuses the WHOLE "
            "feature") in result.stdout


def test_the_shape_verdict_reaches_the_legs_beside_it(atlas, home):
    """The refusal is the FEATURE's, so a good `repo` leg beside a `spec` one
    is read too and its line says what `collect_legs` will do rather than
    offering a `resume` that throws the feature out — the rule Copilot's
    second round on #21 set, reached now by a third route."""
    checkout = workspace_config(home)
    origin_has_branch(atlas, "001-a-thing")
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon")
    path.write_text(path.read_text(encoding="utf-8").replace(
        "            pushed: true\n",
        "            pushed: true\n"
        "          - role: spec\n"
        "            remote: origin\n"
        f"            parked_commit: {FAKE_SHA}\n"
        "            wip: true\n"
        "            wip_depth: 1\n"
        "            pushed: true\n"), encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (repo leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        "WHOLE feature, because its `spec` leg names a role `resume` maps "
        "only onto a three-leg checkout, and this one is single, so it does "
        "not bring this leg back — park that feature again from the "
        "workstation that has it (the record says Falcon)"), findings[0]
    assert findings[1].startswith(
        "- parked feature 001-a-thing (spec leg): `resume` maps the role "
        "`spec` onto a three-leg checkout only"), findings[1]
    assert "`resume Atlas`" not in result.stdout


def test_a_feature_the_record_lists_no_leg_for_is_a_finding_not_silence(
        atlas, home):
    """Note 1 of the independent review of #21, 2026-09-11, and the note-8
    commit's own "recorded for later"; nobody has ruled on it. A feature the
    record leaves with NO LEGS AT ALL — an empty `legs:`, `legs: []`, or leg
    items with no `- role:` line — drew nothing whatever: no finding, exit 0,
    the parked-record note counting the feature and saying no more. Every
    reading this layer had was a LEG's, and there is no leg here to hang one
    on.

    `resume.sh` is not silent about it. `collect_legs` ends
    `[ "${#LEG_ROLES[@]}" -gt 0 ]`, so it refuses the WHOLE feature in the
    shape words: run on 2026-09-11 against a scratch single-shape estate —
    bare remote in a temp dir, fake `$HOME`, the extension's own scripts —
    each of the three spellings answered "Error: 001-a-thing was parked from
    a single project and this checkout is single; that feature was NOT
    recreated", "REFUSED: 001-a-thing — shape mismatch", exit 2. So the
    finding is the FEATURE's, printed where the feature is, and the exit is
    the one the roleless arm names: only a park that parks the feature
    THROUGH writes legs for it — `workspace_write_manifest` writes `legs: []`
    for a feature it has none for, and `emit_recorded_feature` carries a
    REFUSED feature's legs forward out of the loaded manifest, which for this
    one is none."""
    checkout = workspace_config(home)
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon")
    head = path.read_text(encoding="utf-8").split("        legs:\n")[0]
    for legs in ("        legs:\n",
                 "        legs: []\n",
                 "        legs:\n"
                 "          - remote: origin\n"
                 f"            parked_commit: {FAKE_SHA}\n"
                 "            wip: true\n"
                 "            wip_depth: 1\n"
                 "            pushed: true\n"):
        path.write_text(head + legs, encoding="utf-8")
        for extra in ([], ["--fetch"]):
            result = run(STATUS, *extra, "Atlas", home=home)
            assert result.returncode == 1, result.stdout + result.stderr
            assert ("    - parked feature 001-a-thing: the record lists no leg "
                    "for it; `resume` collects a feature's legs before it "
                    "recreates anything and refuses the WHOLE feature where it "
                    "finds none, reporting it as a shape mismatch, so nothing "
                    "here brings it back — park that feature again from the "
                    "workstation that has it (the record says Falcon), which "
                    "writes the record afresh with the legs it parks"
                    ) in result.stdout, legs
            assert "( leg)" not in result.stdout, legs
            assert "`resume Atlas`" not in result.stdout, legs


def test_a_feature_with_no_legs_is_still_a_feature_the_record_knows(
        atlas, home):
    """The unrecorded-worktree sweep reads the branch, not the legs: a
    feature the record lists no leg for is still IN the record, so a worktree
    on that branch was parked and must not be called unparked. `record_rows`
    emits the `branch` row wherever the branch line is, legs or none, and
    `$recorded` is built from those rows — so this holds without a line of
    its own, and the test is what keeps it holding.

    The feature COUNT on the record's own row counts it too, for the same
    reason: it is a feature of this estate that was parked, and a count that
    skipped it would disagree with the finding printed under it."""
    checkout = workspace_config(home)
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon")
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    head = path.read_text(encoding="utf-8").split("        legs:\n")[0]
    path.write_text(head + "        legs:\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    parked record: 1 feature(s)" in result.stdout
    assert ("    - parked feature 001-a-thing: the record lists no leg for it;"
            ) in result.stdout
    assert "never parked" not in result.stdout, (
        "a worktree whose branch the record names is not unparked work")


def test_a_feature_with_no_legs_is_read_in_the_record_s_own_order(
        atlas, home):
    """One feature with legs, one with none, one with legs: the feature-level
    finding prints where its feature is, between the legs of the features
    around it, because the judgement is made in a first pass and read back at
    the `branch` row. A finding printed after everything else would read as a
    fourth feature."""
    checkout = workspace_config(home)
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "            pushed: true\n",
        "            pushed: true\n"
        "      - branch: 002-b-thing\n"
        "        legs:\n"
        "      - branch: 003-c-thing\n"
        "        legs:\n"
        "          - role: repo\n"
        "            remote: origin\n"
        f"            parked_commit: {FAKE_SHA}\n"
        "            wip: true\n"
        "            wip_depth: 1\n"
        "            pushed: false\n")
    path.write_text(text, encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    parked record: 3 feature(s)" in result.stdout
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 3, findings
    assert findings[0].startswith(
        "- parked feature 001-a-thing (repo leg): no worktree on that branch "
        "here"), findings[0]
    assert findings[1].startswith(
        "- parked feature 002-b-thing: the record lists no leg for it;"
        ), findings[1]
    assert findings[2].startswith(
        "- parked feature 003-c-thing (repo leg): parked with --no-push on "
        "Falcon"), findings[2]


def leg_block(role: str, commit: str, *, pushed: str = "true") -> str:
    """One more leg under the feature `record()` wrote, in its layout."""
    return (f"          - role: {role}\n"
            "            remote: origin\n"
            f"            parked_commit: {commit}\n"
            "            wip: true\n"
            "            wip_depth: 1\n"
            f"            pushed: {pushed}\n")


def two_leg_record(checkout, *, second: str, first_commit: str,
                   second_commit: str, order: str = "good-first"):
    """A one-feature record with two legs: a good `repo` leg with no worktree
    here, and `second` — the leg that costs the feature."""
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=first_commit, parked_on="Falcon")
    good = leg_block("repo", first_commit)
    spoiler = leg_block(second, second_commit)
    text = path.read_text(encoding="utf-8")
    assert text.count(good) == 1, text
    path.write_text(text.replace(
        good, good + spoiler if order == "good-first" else spoiler + good),
        encoding="utf-8")
    return path


def test_no_line_of_a_feature_resume_refuses_whole_offers_resume(atlas, home):
    """Copilot on #21, second round, 2026-09-11, verbatim: "This finding is
    emitted per leg, but `read_record` still invokes `check_parked_leg` for
    every sibling. Thus a feature with one roleless leg also prints the normal
    `resume <Name> brings it back` advice for another leg, even though this
    message says `resume` refuses the whole feature; the combined report
    recommends a command that cannot recreate it."

    True of both whole-feature refusals a leg can cause — a leg with no role,
    and a role this root cannot answer — and in both orders, which is the
    reason the verdict is made in a pass of its own: with the spoiling leg
    LAST, no reader that judges a leg as it arrives can know. `resume` will
    not recreate any of it, so no line of it may name `resume`; the sibling's
    line says what `collect_legs` will do and why, and ends at the one exit
    there is."""
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-b-other",
                           parked_worktree(atlas, "001-b-other"))
    for second, why in (
            ("", "a leg of it in the record has no role"),
            ("nope", "its `nope` leg names a role this root does not mount")):
        for order in ("good-first", "spoiler-first"):
            two_leg_record(checkout, second=second, first_commit=FAKE_SHA,
                           second_commit=tip, order=order)
            result = run(STATUS, "Atlas", home=home)
            assert result.returncode == 1, result.stdout + result.stderr
            assert ("    - parked feature 001-a-thing (repo leg): no worktree "
                    "on that branch here, parked 2026-09-10T20:00:00Z on "
                    f"Falcon; `resume` refuses the WHOLE feature, because {why}"
                    ", so it does not bring this leg back — park that feature "
                    "again from the workstation that has it (the record says "
                    "Falcon)") in result.stdout, (second, order)
            assert "`resume Atlas`" not in result.stdout, (second, order)


def test_a_refused_feature_still_names_the_prune_that_blocks_it(atlas, home):
    """A stale registration is still the person's to clear — `resume` cannot
    recreate a worktree git believes it has, whatever else it refuses — so
    the prune keeps its place at the front of the line, and only the `resume`
    at the end of it goes."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    feature_worktree(atlas, "001-a-thing", where)
    rmtree(where)               # and NO `git worktree prune`
    two_leg_record(checkout, second="", first_commit=FAKE_SHA,
                   second_commit=FAKE_SHA)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here, but a stale worktree registration for it is still "
            f"recorded at {where} — clear it with `git -C {atlas} worktree "
            "prune`; and `resume` refuses the WHOLE feature in any case, "
            "because a leg of it in the record has no role, so it does not "
            "bring this leg back either — park that feature again from the "
            "workstation that has it (the record says Falcon)") in result.stdout
    assert "`resume Atlas`" not in result.stdout


def test_the_verdict_reaches_only_the_feature_it_belongs_to(atlas, home):
    """Per FEATURE, not per record: a second feature in the same block, with
    every leg mappable, keeps the line it always had. The verdict is read
    back at each feature's own `branch` row, and a record where one feature
    is refused and another is not is the test of that."""
    checkout = workspace_config(home)
    path = two_leg_record(checkout, second="", first_commit=FAKE_SHA,
                          second_commit=FAKE_SHA)
    text = path.read_text(encoding="utf-8")
    path.write_text(text + "      - branch: 002-b-thing\n        legs:\n"
                    + leg_block("repo", FAKE_SHA), encoding="utf-8")
    # THE SECOND FEATURE'S BRANCH IS ON ORIGIN, which is what "the line it
    # always had" now needs: since the gone-from-origin reading, a leg whose
    # repository has no `origin/<branch>` carries that reading beside the
    # `resume`, and the line under test here is the one with nothing wrong
    # with it at all.
    origin_has_branch(atlas, "002-b-thing")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 3, findings
    assert findings[0].startswith(
        "- parked feature 001-a-thing (repo leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        "WHOLE feature"), findings[0]
    assert findings[1].startswith(
        "- parked feature 001-a-thing: a leg of it in the record has no role;"
        ), findings[1]
    assert findings[2] == (
        "- parked feature 002-b-thing (repo leg): no worktree on that branch "
        "here; parked 2026-09-10T20:00:00Z on Falcon — `resume Atlas` brings "
        "it back"), findings[2]


def test_the_gone_branch_verdict_reaches_the_legs_beside_it(trio, home):
    """The independent review of this branch, 2026-09-12, its BLOCKER,
    verbatim: "The RR2 refusal ("origin has not got that branch, so `resume`
    refuses the WHOLE feature") is PRINTED as a whole-feature refusal but is
    NOT made the FEATURE's verdict, so a SIBLING leg in the same report still
    says "`resume <Name>` brings it back"."

    `resume.sh` walks a feature's legs in the record's order and RR2 is
    `refused=true; break` — the loop stops and `[ "$refused" = false ] ||
    continue` throws the whole feature out, the other legs with it — so a
    report that names the refusal on one leg's line and `resume Trio` on the
    next recommends a command that cannot recreate any of it, which is the
    rule Copilot's second round on #21 set and this reading broke by a fourth
    route. The verdict is made in `read_record`'s first pass now, beside the
    two `collect_legs` asks, and the culprit leg still says it in RR2's own
    words because a leg that meets that test says it for itself — the way two
    unmappable roles each draw the long shape line.

    THIS FIXTURE IS THE THREE-LEG ONE because a feature with two legs in two
    DIFFERENT repositories is the state that shows it: the branch is on origin
    in the `code` leg and gone from origin in the `spec` leg, so the sibling
    is a leg with nothing whatever wrong with it and the base's report offered
    `resume Trio` for it. BOTH EXITS TRAVEL WITH THE VERDICT, because the
    re-park every other whole-feature refusal ends in is the wrong thing to
    name for a branch origin has lost: the feature may have LANDED.

    AND THE SECOND HALF IS THE ORDER THE TWO VERDICTS COME IN: `collect_legs`
    runs to the end before any RR does, so the same record with a ROLELESS leg
    beside the gone one is refused for the role, in the words and with the
    exit that refusal has always had, and nothing in the report mentions
    origin at all."""
    checkout = workspace_config(home)
    spec, code = trio / "spec", trio / "code"
    for leg in (spec, code):
        git("checkout", "-q", "main", cwd=leg)
        origin_has_branch(leg, "001-a-thing")
    drop_from_origin(spec, "001-a-thing")
    path = record(checkout, "trio", branch="001-a-thing", role="spec",
                  commit=FAKE_SHA, parked_on="Falcon", root="Trio")
    path.write_text(path.read_text(encoding="utf-8")
                    + leg_block("code", FAKE_SHA), encoding="utf-8")
    result = run(STATUS, "--fetch", "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (spec leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon, and no "
        "`origin/001-a-thing` here after this run's fetch: origin has not got "
        "that branch, so `resume` refuses the WHOLE feature for it, "
        "\"001-a-thing is no longer on origin in the spec leg\", and nothing "
        "here brings it back — the exits are to delete its `- branch: "
        "001-a-thing` block from the record where the feature landed, or to "
        "push the branch again from Falcon where it went by mistake"
        ), findings[0]
    assert findings[1] == (
        "- parked feature 001-a-thing (code leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        "WHOLE feature, because there is no `origin/001-a-thing` in its "
        "`spec` leg after this run's fetch, so it does not bring this leg "
        "back — the exits are to delete its `- branch: 001-a-thing` block "
        "from the record where the feature landed, or to push the branch "
        "again from Falcon where it went by mistake"), findings[1]
    assert "`resume Trio`" not in result.stdout
    assert "park that feature again" not in result.stdout, (
        "the re-park is the exit for the refusals `collect_legs` makes; a "
        "feature that landed is a record entry to delete")

    # AND `collect_legs` COMES FIRST, so a feature IT refuses is refused for
    # that and the verdict the legs carry is the one with the re-park exit —
    # RR2 never reads origin for that feature at all. The gone reading is kept
    # in an array of its own for this, and read back only where the questions
    # `collect_legs` asks found nothing, whatever the order of the legs.
    path.write_text(path.read_text(encoding="utf-8")
                    .replace(leg_block("code", FAKE_SHA),
                             leg_block("", FAKE_SHA)), encoding="utf-8")
    result = run(STATUS, "--fetch", "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (spec leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        "WHOLE feature, because a leg of it in the record has no role, so it "
        "does not bring this leg back — park that feature again from the "
        "workstation that has it (the record says Falcon)"), findings[0]
    assert findings[1].startswith(
        "- parked feature 001-a-thing: a leg of it in the record has no role;"
        ), findings[1]
    assert "is no longer on origin" not in result.stdout, (
        "RR2 is never reached for a feature `collect_legs` throws out")
    assert "`resume Trio`" not in result.stdout


def test_the_features_verdict_is_the_first_leg_resume_refuses_at(trio, home):
    """Copilot's THIRD round on #23, 2026-09-12, verbatim: "`feature_gone` is
    propagated to every leg without accounting for an earlier per-leg
    refusal. For example, if the first leg has `pushed: false` (RR6) or no
    `parked_commit:` (RR1) and a later leg has a missing origin branch,
    `resume` stops at the first leg in record order, but this makes the whole
    feature report RR2's gone-origin verdict and exits. Track the first
    applicable refusal/order before promoting a later origin check to a
    feature verdict, or suppress that promotion when an earlier leg already
    blocks resume."

    THE ORDER IS THE RECORD'S: `workspace_load_project` appends each leg in
    file order, `collect_legs` walks `MANIFEST_LEG_ROLE` in that order, and
    the per-leg loop under it breaks at the FIRST refusal — RR6, RR4, RR3,
    RR2, RR1, RR5, each `refused=true; break`, with `[ "$refused" = false ] ||
    continue` throwing the whole feature out after it. Run against the
    extension on 2026-09-12 on a scratch three-leg estate — bare remotes in a
    temp dir, a fake `$HOME`, the extension's own scripts — one feature, two
    legs in two repositories, the record's order the variable:

      `code` (`pushed: false`) then `spec` (branch deleted on origin)
        "Error: 001-a-thing (code leg) was parked with --no-push; that feature
        was NOT recreated", "REFUSED: 001-a-thing — parked with --no-push",
        exit 2
      `code` (no `parked_commit:`) then `spec` (branch deleted on origin)
        "Error: 001-a-thing (code leg) has moved since it was parked; that
        feature was NOT recreated", "REFUSED: 001-a-thing — divergence",
        exit 2
      `spec` (branch deleted on origin) then `code` (`pushed: false`)
        "Error: 001-a-thing is no longer on origin in the spec leg; that
        feature was NOT recreated", "REFUSED: 001-a-thing — gone from
        origin", exit 2

    ORIGIN IS NEVER READ IN THE FIRST TWO, so no line of them may say origin
    has lost that branch and no line of them may name RR2's exits: deleting
    the record entry is the wrong thing to do about a leg that was never
    pushed. The verdict is the first REFUSING leg's, and every leg of the
    feature carries it.

    THE FOURTH BLOCK IS RR6 AGAINST RR4, because the order inside one leg is
    as load-bearing as the order between legs: RR6 is the FIRST test of the
    loop and carries no worktree condition, so a `--no-push` leg with its
    worktree standing here still breaks the loop and still costs the feature,
    while the gone-origin sibling two rows down is one `resume` never reaches.
    Run against the extension on 2026-09-13, on a scratch three-leg estate
    built the same way, the `code` leg's worktree registered at the parked
    commit and the `spec` leg's branch deleted on origin:

      `code` (`pushed: false`, worktree present) then `spec` (branch gone)
        "Error: 001-a-thing (code leg) was parked with --no-push; that
        feature was NOT recreated", "REFUSED: 001-a-thing — parked with
        --no-push", exit 2, origin never mentioned
      the same estate with that leg's `pushed: true` — the control
        "Error: 001-a-thing is no longer on origin in the spec leg", "REFUSED:
        001-a-thing — gone from origin", exit 2

    So RR4 does not shield the leg from RR6, and it is RR6 that decides which
    refusal the person gets.

    THE FOURTH BLOCK'S WORKTREE IS AT THE PATH `resume` COMPUTES, which is
    what "registered at the parked commit" meant in the run above and is what
    this file's `parked_worktree` builds: RR4 matches ONE string, and a
    worktree anywhere else is not the already-recreated leg this block needs
    in order to be about RR6 at all. It was written at `Trio-wt/<branch>/
    code`, a path neither verb reads, before this branch's own reading of RR4
    existed to say so."""
    checkout = workspace_config(home)
    spec, code = trio / "spec", trio / "code"
    for leg in (spec, code):
        git("checkout", "-q", "main", cwd=leg)
        origin_has_branch(leg, "001-a-thing")
    drop_from_origin(spec, "001-a-thing")
    afresh = ("park that feature again from Falcon, which writes the record "
              "afresh")

    # RR6 FIRST, RR2 SECOND. The `--no-push` leg keeps the line it always had
    # — its own refusal, in its own words — and the leg origin has lost stops
    # claiming a refusal `resume` never reaches.
    path = record(checkout, "trio", branch="001-a-thing", role="code",
                  commit=FAKE_SHA, pushed="false", parked_on="Falcon",
                  root="Trio")
    path.write_text(path.read_text(encoding="utf-8")
                    + leg_block("spec", FAKE_SHA), encoding="utf-8")
    result = run(STATUS, "--fetch", "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (code leg): parked with --no-push on "
        "Falcon and no worktree on that branch here; only that workstation "
        "has the WIP commit, so nothing here brings it back — park it again "
        "from there"), findings[0]
    assert findings[1] == (
        "- parked feature 001-a-thing (spec leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        "WHOLE feature, because its `code` leg was parked with --no-push, so "
        "it does not bring this leg back — " + afresh), findings[1]
    assert "is no longer on origin" not in result.stdout, (
        "RR6 breaks the loop before RR2 reads origin at all")
    assert "delete its `- branch:" not in result.stdout, (
        "a leg that was never pushed is no reason to delete the record entry")
    assert "`resume Trio`" not in result.stdout

    # RR1 FIRST, RR2 SECOND, and the same again: a leg the record names no
    # commit for is refused at RR1 — after RR2 in one leg, before RR2 in the
    # next one.
    path = record(checkout, "trio", branch="001-a-thing", role="code",
                  commit="", parked_on="Falcon", root="Trio")
    path.write_text(path.read_text(encoding="utf-8")
                    + leg_block("spec", FAKE_SHA), encoding="utf-8")
    result = run(STATUS, "--fetch", "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (code leg): the record names no parked "
        "commit for that leg, and no worktree on that branch here; `resume` "
        "matches origin's tip against the parked commit before it recreates "
        "anything, an absent one never matches, and it refuses the leg as "
        "having moved on since it was parked, so nothing here brings it back "
        "— park it again from Falcon, which writes the record afresh"
        ), findings[0]
    assert findings[1] == (
        "- parked feature 001-a-thing (spec leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        "WHOLE feature, because the record names no parked commit for its "
        "`code` leg, so it does not bring this leg back — " + afresh
        ), findings[1]
    assert "is no longer on origin" not in result.stdout
    assert "`resume Trio`" not in result.stdout

    # AND THE OTHER ORDER IS THE ONE THIS LAYER ALREADY READ RIGHT: with the
    # gone leg FIRST, RR2 is the refusal `resume` makes and the report is the
    # one it always was, the `--no-push` leg saying its own piece under it.
    path = record(checkout, "trio", branch="001-a-thing", role="spec",
                  commit=FAKE_SHA, parked_on="Falcon", root="Trio")
    path.write_text(path.read_text(encoding="utf-8")
                    + leg_block("code", FAKE_SHA, pushed="false"),
                    encoding="utf-8")
    result = run(STATUS, "--fetch", "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (spec leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon, and no "
        "`origin/001-a-thing` here after this run's fetch: origin has not got "
        "that branch, so `resume` refuses the WHOLE feature for it, "
        "\"001-a-thing is no longer on origin in the spec leg\", and nothing "
        "here brings it back — the exits are to delete its `- branch: "
        "001-a-thing` block from the record where the feature landed, or to "
        "push the branch again from Falcon where it went by mistake"
        ), findings[0]
    assert findings[1] == (
        "- parked feature 001-a-thing (code leg): parked with --no-push on "
        "Falcon and no worktree on that branch here; only that workstation "
        "has the WIP commit, so nothing here brings it back — park it again "
        "from there"), findings[1]
    assert "`resume Trio`" not in result.stdout

    # AND RR6 IS BEFORE RR4, SO A WORKTREE HERE DOES NOT SAVE THE LEG, which
    # is the one thing that could have made the first block above an accident
    # of the fixture: RR2 and RR1 are read here only for a leg with NO
    # worktree, because RR4 sits in front of them and `continue`s past a leg
    # already recreated, and if the `pushed:` arm had been written with them
    # it would have inherited that guard and let the gone-origin leg take the
    # feature after all. `resume.sh` tests `[ "$pushed" != true ]` as the
    # FIRST thing in the loop, with nothing about the worktree in it, so the
    # `--no-push` leg still breaks the loop with its worktree standing — and
    # the verdict the `spec` leg carries is still RR6's.
    tip = feature_worktree(code, "001-a-thing",
                           parked_worktree(trio, "001-a-thing", "code"))
    path = record(checkout, "trio", branch="001-a-thing", role="code",
                  commit=tip, pushed="false", parked_on="Falcon", root="Trio")
    path.write_text(path.read_text(encoding="utf-8")
                    + leg_block("spec", FAKE_SHA), encoding="utf-8")
    result = run(STATUS, "--fetch", "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (code leg): parked with --no-push on "
        "Falcon; only that workstation has the WIP commit, and `resume` "
        "refuses it"), findings[0]
    assert findings[1] == (
        "- parked feature 001-a-thing (spec leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        "WHOLE feature, because its `code` leg was parked with --no-push, so "
        "it does not bring this leg back — " + afresh), findings[1]
    assert "is no longer on origin" not in result.stdout, (
        "RR6 breaks the loop with the worktree standing, and RR2 is never "
        "reached for the leg origin has lost")
    assert "`resume Trio`" not in result.stdout


def test_every_command_it_hands_a_person_survives_a_space_in_the_path(
        status_remotes, home):
    """COPILOT'S FIRST ROUND ON #27 (2026-09-13), verbatim: "The remediation
    command here interpolates `$repo` and `$want` directly into a shell
    snippet. Valid paths containing spaces split the command, and shell
    metacharacters make the copy-pasted `git worktree move` unsafe, so the
    prescribed cleanup is not reliably runnable. Please emit shell-quoted
    operands through a shared formatter (and cover such paths in tests)."

    IT IS RIGHT, and by this layer's own rule: every one of these lines ends
    in "which is yours to run", and the rule at the top of `check_parked_leg`
    is that an arm may not name an exit that does not run. `~/My Projects` is
    an ordinary spelling on a Mac, and a `git -C <that>/Atlas worktree move
    <a> <b>` built by splicing it in is four operands where git wants two.

    `sh_operand` is that formatter, and it quotes ONLY where a shell would
    need it — a path of letters, digits and `/._@%+:,=-` is its own operand
    everywhere — which is why no other pin in this file moves. This test is
    the other half: a projects directory with a SPACE in it, where every
    command the record layer prints must come back quoted and runnable.

    The estate NAME is not tested for it because it cannot carry one:
    `is_safe_folder_name` refuses anything outside `[A-Za-z0-9_.+@-]`, so
    `resume <Name>` has no operand to quote."""
    spaced = home / "my projects"
    spaced.mkdir()
    git("-c", "protocol.file.allow=always", "clone", "-q",
        "--recurse-submodules", str(status_remotes["Atlas"]["bare"]),
        str(spaced / "Atlas"), cwd=spaced)
    atlas = spaced / "Atlas"
    checkout = workspace_config(home)
    origin_has_branch(atlas, "001-a-thing")
    tip = git("rev-parse", "origin/001-a-thing", cwd=atlas).stdout.strip()
    want = parked_worktree(atlas, "001-a-thing")
    want.mkdir(parents=True)
    (want / "stray.txt").write_text("not ours\n", encoding="utf-8")
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home,
                 env={"PROJECTS_DIR": str(spaced)})
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"move it aside with `mv '{want}' <a path of your choosing>`" in (
        result.stdout), result.stdout
    assert str(want) in result.stdout

    # AND THE MOVE, WHICH TAKES TWO OF THEM: the worktree off the path, with
    # nothing at the path this time, so the arm that names `worktree move` is
    # the one that speaks.
    rmtree(want)
    elsewhere = home / "not the place" / "001-a-thing"
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", str(elsewhere), "001-a-thing", cwd=atlas)
    result = run(STATUS, "Atlas", home=home,
                 env={"PROJECTS_DIR": str(spaced)})
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"`mkdir -p '{want.parent}' && git -C '{atlas}' worktree move "
            f"'{elsewhere}' '{want}'`") in result.stdout, result.stdout

    # AND A SINGLE QUOTE IS THE ONE CHARACTER SINGLE QUOTES CANNOT HOLD, so
    # the escape that ends them, adds a literal one and reopens them is what
    # the formatter writes — `'it'\''s'` is `it's` to every POSIX shell.
    quoted = home / "it's projects"
    quoted.mkdir()
    git("-c", "protocol.file.allow=always", "clone", "-q",
        "--recurse-submodules", str(status_remotes["Atlas"]["bare"]),
        str(quoted / "Atlas"), cwd=quoted)
    q_atlas = quoted / "Atlas"
    origin_has_branch(q_atlas, "001-a-thing")
    q_tip = git("rev-parse", "origin/001-a-thing", cwd=q_atlas).stdout.strip()
    q_want = parked_worktree(q_atlas, "001-a-thing")
    q_want.mkdir(parents=True)
    (q_want / "stray.txt").write_text("not ours\n", encoding="utf-8")
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=q_tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home,
                 env={"PROJECTS_DIR": str(quoted)})
    assert result.returncode == 1, result.stdout + result.stderr
    shell_safe = "'" + str(q_want).replace("'", "'\\''") + "'"
    assert f"move it aside with `mv {shell_safe} <a path of your choosing>`" in (
        result.stdout), result.stdout

    # AND A PATH THAT NEEDS NOTHING IS LEFT ALONE, which is why every other
    # pin in this file still passes: the same estate under a plain projects
    # directory prints the same command unquoted.
    plain = clone_root(home, status_remotes["Atlas"], "Atlas")
    origin_has_branch(plain, "001-a-thing")
    plain_tip = git("rev-parse", "origin/001-a-thing", cwd=plain).stdout.strip()
    plain_want = parked_worktree(plain, "001-a-thing")
    plain_want.mkdir(parents=True)
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=plain_tip, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"`mv {plain_want} <a path of your choosing>`" in result.stdout


def test_what_the_prune_leaves_behind_is_a_path_and_not_a_directory(
        atlas, home):
    """COPILOT'S SECOND ROUND ON #27 (2026-09-13, suppressed), verbatim: "For a
    stale registration on the recorded branch whose old worktree path is now a
    regular file, the `-d` check is false, so status tells the user to prune
    and then resume even though the file remains and `resume` still rejects the
    existing destination. Detect and describe any leftover path here, not just
    directories." Its twin on the LOCKED arm says the same of that one.

    BOTH ARE REAL, and git says so in three words. Run on 2026-09-13: a
    worktree registered, its directory replaced by a regular FILE, git calling
    the block "prunable gitdir file points to non-existent location"; `git
    worktree prune` cleared the registration and `git worktree add` at that
    same path then answered "fatal: '…' already exists". The reason is the
    path EXISTING and not what kind of path it is, so the clause asks `-e` and
    says "whatever the prune leaves behind"."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    rmtree(where)
    where.write_text("a file now\n", encoding="utf-8")   # not a directory
    porcelain = git("worktree", "list", "--porcelain", cwd=atlas).stdout
    assert "prunable" in porcelain, "git no longer says prunable; moot"
    assert where.is_file(), "the FILE is what makes this case"
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("whose path is still on disk and is no longer a worktree") in (
        result.stdout), result.stdout
    assert ("worktree prune` and a move of what is there aside (`git worktree "
            'add` refuses a path that "already exists")') in result.stdout

    # AND THE LOCKED ARM'S OWN CLAUSE, which is the same test on the other
    # side: git computes no `prunable` for a locked block, so that path is
    # RR4's second arm and the exit is the unlock, the prune and the move.
    where.unlink()
    where.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "prune", cwd=atlas)
    git("worktree", "add", "-q", "-b", "002-other", str(where), cwd=atlas)
    git("worktree", "lock", str(where), cwd=atlas)
    rmtree(where)
    where.write_text("a file now\n", encoding="utf-8")
    record(checkout, "atlas", branch="001-a-thing", role="repo",
           commit=git("rev-parse", "origin/001-a-thing",
                      cwd=atlas).stdout.strip())
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("and move aside whatever the prune leaves behind there, which "
            "`resume` refuses for existing whatever git holds") in (
        result.stdout), result.stdout


def test_the_move_names_a_parent_that_is_never_the_empty_string(atlas, home):
    """COPILOT'S SECOND ROUND ON #27 (2026-09-13), verbatim: "When the
    configured worktree root is `/`, `want` can be `/branch`, so `${want%/*}`
    expands to the empty string. The generated recovery command becomes `mkdir
    -p '' && git worktree move ...`, which fails before the move even though
    `resume` only needs the already-existing `/` parent. Use a parent-directory
    fallback of `/` (or `dirname`) when constructing this command."

    IT IS RIGHT AND IT WAS RUN: `mkdir -p ''` answers "cannot create directory
    ''", so the exit dies on its first operand. `parent_dir` is that fallback,
    and `/` is the one directory `${p%/*}` cannot name.

    NOTHING IS CREATED BY THIS TEST: `status` reads and changes nothing, and
    the only thing it does with `/001-a-thing` is ask whether it exists."""
    checkout = workspace_config(home)
    config = atlas / ".specify" / "extensions" / "git"
    config.mkdir(parents=True, exist_ok=True)
    (config / "git-config.yml").write_text(
        "checkout_mode: worktree\nworktree_root: /\n", encoding="utf-8")
    elsewhere = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", elsewhere)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    # `//001-a-thing` AND NOT `/001-a-thing`, because that is the string the
    # other end computes: `resolve_path_from_repo_root` hands an absolute
    # value back unchanged and `collect_legs` joins `$WORKTREE_ROOT/$branch`,
    # so both ends spell the doubled slash and the comparison is exact.
    assert "which is not the //001-a-thing `resume` computes for it" in (
        result.stdout), result.stdout
    assert (f"`mkdir -p / && git -C {atlas} worktree move {elsewhere} "
            "//001-a-thing`") in result.stdout, result.stdout
    assert "mkdir -p ''" not in result.stdout
    assert "mkdir -p  &&" not in result.stdout


def test_the_ref_in_the_diverged_command_is_a_shell_operand_too(atlas, home):
    """COPILOT'S THIRD ROUND ON #27 (2026-09-13), verbatim: "The generated `git
    log` command now quotes the repository path but still interpolates `branch`
    unquoted. Git refnames can contain shell metacharacters such as `$`, so a
    valid recorded branch can make this copy-pasted diagnostic expand or split
    in the user's shell. Pass the ref through the same shell-operand formatter
    and cover a metacharacter-bearing branch in the command-output test."

    IT IS RIGHT: `git check-ref-format` takes `$` in a refname, and `git log
    --oneline <sha>..feat/$HOME-thing` in a shell is `git log --oneline
    <sha>..feat/` followed by whatever `$HOME-thing` expands to. The whole
    revision range is one operand, so the whole range goes through
    `sh_operand` — which leaves an ordinary branch name untouched, and is why
    the pin beside this one did not move."""
    checkout = workspace_config(home)
    branch = "001-a-$thing"
    where = parked_worktree(atlas, branch)
    base = feature_worktree(atlas, branch, where)
    (where / "theirs.md").write_text("theirs\n", encoding="utf-8")
    commit_all(where, "parked elsewhere")
    git("push", "-q", "origin", branch, cwd=where)
    theirs = git("rev-parse", "HEAD", cwd=where).stdout.strip()
    git("reset", "-q", "--hard", base, cwd=where)
    (where / "mine.md").write_text("mine\n", encoding="utf-8")
    commit_all(where, "mine")
    record(checkout, "atlas", branch=branch, role="repo", commit=theirs)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"reconcile by hand: `git -C {atlas} log --oneline "
            f"'{theirs[:7]}..{branch}'`") in result.stdout, result.stdout
    assert f"--oneline {theirs[:7]}..{branch}`" not in result.stdout, (
        "the ref is an operand, and an unquoted `$` is the shell's")


def test_an_off_path_leg_whose_branch_origin_lost_carries_rr2s_exits(
        atlas, home):
    """COPILOT'S THIRD ROUND ON #27 (2026-09-13, suppressed), two comments and
    one finding. On the RR2 predicate: "The `worktree_here` check above
    delegates to `worktree_on_branch`, so it returns true for any live worktree
    on this branch, not just the path RR4 computes. With `--fetch`, an off-path
    worktree plus a successfully fetched missing `origin/<branch>` should reach
    RR2 in `resume`, but this return suppresses the first-pass `gone` verdict
    and can make sibling legs recommend the wrong re-park/move exit." And on
    the arm it feeds: "this row instead recommends moving the worktree and
    hides the delete/push exits for the actual refusal."

    BOTH ARE REAL, and one run settles them. On a scratch estate on 2026-09-13
    with the leg's worktree at `$HOME/elsewhere/001-a-thing` and its branch
    deleted on origin, `resume.sh` answered "Error: 001-a-thing is no longer on
    origin in the spec leg; that feature was NOT recreated", "REFUSED:
    001-a-thing — gone from origin", exit 2 — RR4 missing ON THE PATH, RR3
    finding nothing there, and RR2 refusing before any add — while this layer
    named a `git worktree move`, which brings back no branch origin has lost.

    SO `already_recreated` REPLACES `worktree_here` in RR2's predicate — RR4's
    first arm asked the way RR4 asks it, a registration AT the computed path on
    this branch — and the off-path line keeps its FACT and takes RR2's EXITS.
    The fact is still worth a line: where the worktree sits is true of this
    workstation, RR2's own words do not carry it, and `park` here will not
    collect it either."""
    checkout = workspace_config(home)
    elsewhere = home / "elsewhere" / "001-a-thing"
    want = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", elsewhere)
    drop_from_origin(atlas, "001-a-thing")
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its worktree is at "
            f"{elsewhere}, which is not the {want} `resume` computes for it"
            ) in result.stdout, result.stdout
    assert ("there is no `origin/001-a-thing` in this leg after this run's "
            "fetch either, so `resume` refuses at that before it reaches any "
            "add — the exits are to delete its `- branch: 001-a-thing` block "
            "from the record where the feature landed, or to push the branch "
            "again from Falcon where it went by mistake") in result.stdout
    assert "worktree move" not in result.stdout, (
        "a move brings back no branch origin has lost")

    # AND WITHOUT THE FLAG the reading is not made at all — a missing
    # `origin/<branch>` has a second and commoner reading there — so the move
    # is the exit again, which is the control for the arm above.
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"worktree move {elsewhere} {want}" in result.stdout, result.stdout


def test_a_dangling_symlink_at_that_path_is_the_adds_refusal_not_rr3s(
        atlas, home):
    """COPILOT'S FOURTH ROUND ON #27 (2026-09-13, suppressed), verbatim: "`[ -e
    "$want" ]` follows symlinks, so a dangling symlink at the computed
    destination is treated as absent. `git worktree add` still rejects that
    existing path, so a parked feature with no branch worktree falls through to
    the `resume` success guidance even though `resume` fails at its final add."

    IT IS REAL AND GIT SAYS SO: run on 2026-09-13, with a dangling symlink at a
    path, `[ -e ]` is false, `[ -L ]` is true, and `git worktree add` answers
    "fatal: '…' already exists".

    AND IT IS THE ADD's REFUSAL, NOT RR3's. `resume.sh`'s RR3 is the same
    `[ -e "$tree" ]`, so it looks straight through the link too and the run
    goes on to RR2, RR1, RR5 and dies on the last thing it does — which is
    exactly the shape of the prunable registration this layer already reads in
    the stale arms' words. So this is read there too, in words of its own: what
    settles it is not a prune, because nothing is registered at that path, but
    the `mv` every other leftover there wants. `path_in_the_way` still asks
    `[ -e ]` and nothing more, because a reading harder than the other end's
    would invent an RR3 refusal `resume` does not make."""
    checkout = workspace_config(home)
    want = parked_worktree(atlas, "001-a-thing")
    want.parent.mkdir(parents=True, exist_ok=True)
    want.symlink_to(home / "nowhere-at-all")
    assert not want.exists() and want.is_symlink(), "the dangling link is the case"
    origin_has_branch(atlas, "001-a-thing")
    tip = git("rev-parse", "origin/001-a-thing", cwd=atlas).stdout.strip()
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): no worktree on that "
            f"branch here, but a dangling symlink is at the {want} `resume` "
            "computes for this leg, which `[ -e ]` looks straight through and "
            '`git worktree add` refuses all the same ("already exists") — '
            f"clear it with a move of it aside (`mv {want} <a path of your "
            "choosing>`), then `resume Atlas` brings it back") in (
        result.stdout), result.stdout
    assert "is in the way" not in result.stdout, (
        "RR3 looks through the link at the other end too")
    assert "worktree prune" not in result.stdout, (
        "nothing is registered at that path to prune")


def test_an_off_path_worktree_with_a_dangling_link_at_the_path_is_not_silence(
        atlas, home):
    """COPILOT'S FIFTH ROUND ON #27 (2026-09-13), verbatim: "`dest_exists`
    treats a dangling symlink as occupied, but `resume`'s RR3 uses `[ -e ]` and
    therefore proceeds to its final `git worktree add`, which still rejects
    that symlink. With an off-path live worktree and a dangling symlink at this
    computed destination, this condition is false, so no add verdict is carried
    to sibling legs and the report can claim the feature is clean even though
    `resume` fails."

    IT IS RIGHT, AND THE ROUND BEFORE IT MADE THAT SILENCE. `[ -e ]` is the
    test RR3 makes at the other end, so a path only a link occupies is one the
    run walks PAST — and then the add refuses it. The feature is refused, the
    finding is the off-path one, and clearing the link is a STEP IN ITS EXIT
    rather than a reason to say nothing: the `mv` goes in front of the `mkdir
    -p`, where the prune goes for a stale registration, and the clause behind
    the command says which of them git refuses for what."""
    checkout = workspace_config(home)
    want = parked_worktree(atlas, "001-a-thing")
    want.parent.mkdir(parents=True, exist_ok=True)
    want.symlink_to(home / "nowhere-at-all")
    assert not want.exists() and want.is_symlink()
    elsewhere = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", elsewhere)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its worktree is at "
            f"{elsewhere}, which is not the {want} `resume` computes for it"
            ) in result.stdout, result.stdout
    # THE `mv` NAMES NO DESTINATION OF ITS OWN since Copilot's sixth round on
    # #27 (2026-09-13, suppressed): a hard-coded `<want>.aside` would overwrite
    # that path where it already exists, which is the one thing every `mv` this
    # file prints has refused to do since the commit that first named one.
    assert (f"move it where both look: `mv {want} <a path of your choosing> "
            f"&& mkdir -p {want.parent} && git -C {atlas} worktree move "
            f"{elsewhere} {want}`") in result.stdout, result.stdout
    assert ("`git worktree add` refuses the dangling symlink at that path "
            '("already exists") whatever `[ -e ]` says of it') in result.stdout


def test_a_symlinked_parent_of_the_computed_path_gets_no_move_either(
        trio, home):
    """COPILOT'S SIXTH ROUND ON #27 (2026-09-13, suppressed), verbatim: "The
    symlink safeguard only checks `RECORD_WORKTREE_ROOT`, not all components of
    the computed destination. If an existing `$WORKTREE_ROOT/$branch` (or a
    parent from a declared mount) is a symlink while the final `$want` is
    absent, this branch advertises `mkdir -p ... && git worktree move ...`;
    both commands follow the link and Git records the physical target, while
    `resume` later compares the lexical `$want` and still refuses at RR3."

    RIGHT, and it is the same fault one level down: the question is asked of
    the destination's PARENT now, which `has_symlink_component` walks prefix by
    prefix — so the root, the feature directory and every mount above the last
    component are all in it. The FINAL component is deliberately out: a link
    there is the leftover the `mv` clears, not a spelling to correct."""
    checkout = workspace_config(home)
    spec = trio / "spec"
    git("checkout", "-q", "main", cwd=spec)
    origin_has_branch(spec, "001-a-thing")
    tip = git("rev-parse", "origin/001-a-thing", cwd=spec).stdout.strip()
    want = parked_worktree(trio, "001-a-thing", "spec")
    # THE FEATURE DIRECTORY IS THE LINK, and the mount under it is not there at
    # all — the shape a root-only question cannot see, and the reason this is a
    # three-leg estate: a single root's computed path IS the feature directory,
    # so a link there is the FINAL component, which RR3 sees and an `mv` fixes.
    real = home / "real-feature"
    real.mkdir()
    want.parent.parent.mkdir(parents=True, exist_ok=True)
    want.parent.symlink_to(real)
    elsewhere = home / "elsewhere" / "001-a-thing"
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", str(elsewhere), "001-a-thing", cwd=spec)
    record(checkout, "trio", branch="001-a-thing", role="spec", commit=tip,
           parked_on="Falcon", root="Trio")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "no `worktree move` fixes this one, because the worktree root " in (
        result.stdout), result.stdout
    assert f"worktree move {elsewhere}" not in result.stdout, result.stdout


def test_every_root_mount_spelling_gets_the_same_no_command_reading(
        atlas, home):
    """COPILOT'S SIXTH ROUND ON #27 (2026-09-13, suppressed), verbatim:
    "`dot_mount` only recognizes a destination whose raw string ends in `/.`.
    The manifest parser preserves other non-empty root spellings such as `path:
    "./"`, so `collect_legs` can produce `<worktree_root>/<branch>/./`; this
    helper misses it and `off_path_exit` advertises a move."

    RIGHT: `_shape_record_leg` keeps any non-empty `path:` verbatim, so `.`,
    `./` and `.//` all reach `collect_legs` and all name the feature directory
    itself — and every operand built on them was already run and refused (the
    tip of this branch, and the round that stopped advertising one). Trailing
    slashes come off before the `.` is looked for."""
    checkout = workspace_config(home)
    where = home / "Atlas-wt" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="code", commit=tip,
           parked_on="Falcon")
    pristine = (atlas / "project.yaml").read_text(encoding="utf-8")
    for spelling in ('    path: "./"\n', '    path: ".//"\n'):
        (atlas / "project.yaml").write_text(pristine, encoding="utf-8")
        code_leg_onto_the_spec_checkout(atlas, path_line=spelling)
        result = run(STATUS, "Atlas", home=home)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "`mkdir -p " not in result.stdout, result.stdout
        assert f"worktree move {where}" not in result.stdout, result.stdout
        assert ("there is no command that puts it where `resume` looks: this "
                'leg is declared `path: "."` in `project.yaml`') in (
            result.stdout), result.stdout


def test_a_feature_directory_that_is_not_a_directory_is_read_too(trio, home):
    """COPILOT'S SIXTH ROUND ON #27 (2026-09-13, suppressed), verbatim:
    "`dest_exists` only checks the final component. For a three-leg
    destination, `want` is `<worktree_root>/<branch>/<mount>`, but `resume`
    first runs `mkdir -p <worktree_root>/<branch>`; if that feature directory
    is a regular file or dangling symlink, the final path appears absent and
    status can recommend `resume` (or emit a `mkdir -p ... && git worktree move
    ...`) even though the mkdir fails before the worktree is added."

    RUN on 2026-09-13: `mkdir -p <file>/spec` answers "mkdir: cannot create
    directory '…': Not a directory". So the run stops EARLIER than the add and
    in `resume.sh`'s own words rather than git's, and this layer said "`resume
    Trio` brings it back". It is read with the other paths in the way of a step
    no RR looks at, and cleared by the same `mv`.

    THE SHAPE IS THE THREE-LEG ONE, because a single root's `repo` leg has no
    mount under the feature directory: its computed path IS that directory, and
    a file there is already the dangling/existing reading above."""
    checkout = workspace_config(home)
    spec = trio / "spec"
    git("checkout", "-q", "main", cwd=spec)
    origin_has_branch(spec, "001-a-thing")
    tip = git("rev-parse", "origin/001-a-thing", cwd=spec).stdout.strip()
    want = parked_worktree(trio, "001-a-thing", "spec")
    feature_dir = want.parent
    feature_dir.parent.mkdir(parents=True, exist_ok=True)
    feature_dir.write_text("a file where the feature directory goes\n",
                           encoding="utf-8")
    assert feature_dir.is_file() and not want.exists()
    record(checkout, "trio", branch="001-a-thing", role="spec", commit=tip,
           parked_on="Falcon", root="Trio")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (spec leg): no worktree on that "
            f"branch here, but the {feature_dir} `resume` makes the feature's "
            "worktrees under is not a directory, and `resume` runs `mkdir -p` "
            'on it before it adds any leg ("cannot create directory …: Not a '
            f"directory\") — clear it with a move of it aside (`mv "
            f"{feature_dir} <a path of your choosing>`), then `resume Trio` "
            "brings it back") in result.stdout, result.stdout


def test_a_leftover_at_the_destination_is_named_beside_a_prune_elsewhere(
        atlas, home):
    """COPILOT'S FIFTH ROUND ON #27 (2026-09-13, suppressed), verbatim:
    "Restricting this probe to `[ -z "$ghost" ]` misses a destination
    obstruction whenever the recorded branch has a stale registration at some
    other path … so the destination is never examined and the report offers
    `resume` even though its final `git worktree add` is blocked by the
    destination registration."

    THE PRUNE ITSELF IS NOT THE GAP: `git worktree prune` walks every
    registration in the repository, not one, so the exit those arms name
    already clears a stale block at the destination too. WHAT THE PRUNE DOES
    NOT DO IS MOVE ANYTHING ON DISK — and a leftover at the DESTINATION is what
    `git worktree add` refuses after it, which is the half worth a clause. It
    is named where the two paths differ, which is the only shape in which the
    arms above have not named it already."""
    checkout = workspace_config(home)
    want = parked_worktree(atlas, "001-a-thing")
    want.parent.mkdir(parents=True, exist_ok=True)
    # a stale registration for the RECORDED branch somewhere else…
    elsewhere = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", elsewhere)
    (elsewhere / ".git").unlink()          # prunable, the directory left
    # …and a DANGLING SYMLINK at the path `resume` computes, which is the one
    # shape RR3 walks past — a real directory there is RR3's own refusal and
    # the in-the-way arm says it, above all of this.
    want.symlink_to(home / "nowhere-at-all")
    assert not want.exists() and want.is_symlink()
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f", and a move aside of what is at the {want} `resume` computes "
            "for this leg, which the prune does not touch and `git worktree "
            "add` refuses for existing") in result.stdout, result.stdout


def test_a_locked_off_path_worktree_names_the_unlock_before_the_move(
        atlas, home):
    """COPILOT'S FOURTH ROUND ON #27 (2026-09-13, suppressed), verbatim: "When
    the off-path worktree itself is locked, `worktree_on_branch` still returns
    it as live, but this branch only checks `held` for the destination and
    prints `git worktree move <tree> <want>`. Git refuses moving a locked
    source, so the recovery command cannot run; please carry the source
    registration's lock state through the lookup and prepend `git worktree
    unlock <tree>` before the move."

    RUN on 2026-09-13: `git worktree move` with a locked source answered
    "fatal: cannot move a locked working tree; use 'move -f -f' to override or
    unlock first", and after `git worktree unlock` the same move exited 0. The
    unlock goes in front, which is the pair the in-the-way arm has named for a
    locked DESTINATION since this branch's second commit; this is its twin on
    the source, and `$held` was only ever the destination's."""
    checkout = workspace_config(home)
    elsewhere = home / "elsewhere" / "001-a-thing"
    want = parked_worktree(atlas, "001-a-thing")
    tip = feature_worktree(atlas, "001-a-thing", elsewhere)
    git("worktree", "lock", str(elsewhere), cwd=atlas)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"move it where both look: `git -C {atlas} worktree unlock "
            f"{elsewhere} && mkdir -p {want.parent} && git -C {atlas} "
            f"worktree move {elsewhere} {want}`, which is yours to run — "
            "`worktree move` creates no parent directory of its own, and it "
            "refuses a LOCKED source until the unlock in front of it") in (
        result.stdout), result.stdout

    # AND WITH THE LOCK OFF the command is the pair it always was, which is
    # the control: one `git worktree unlock` apart.
    git("worktree", "unlock", str(elsewhere), cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"move it where both look: `mkdir -p {want.parent} && git -C "
            f"{atlas} worktree move {elsewhere} {want}`") in result.stdout
    assert "worktree unlock" not in result.stdout


def test_no_move_is_named_where_the_worktree_root_is_itself_a_symlink(
        atlas, home):
    """COPILOT'S THIRD ROUND ON #27 (2026-09-13, suppressed), verbatim:
    "`off_path_exit` still advertises this move when `worktree_root` is a
    symlink. `record_worktree_root` deliberately preserves that lexical
    spelling, while Git reports the physical worktree path; moving an off-path
    worktree to this `want` therefore leaves `registered_at` unable to match
    it, so the next `resume` still refuses at RR3."

    IT IS REAL AND IT WAS RUN END TO END on 2026-09-13: the move exited 0, git
    then held the worktree at the PHYSICAL `…/real-wt/001-a-thing/spec`, and
    `resume.sh` answered "Error: '…/wtlink/001-a-thing/spec' exists and is not
    a registered worktree of the spec leg", "REFUSED: 001-a-thing — an
    unrelated path is in the way", exit 2. The move ran and fixed nothing,
    which is the one thing the rule at the top of `check_parked_leg` forbids.

    THE EXIT THAT DOES WORK IS THE SPELLING, and that was run too: the same
    estate with `worktree_root` set to the path git spells RESUMED the feature,
    exit 0. So the line names that, and the resolving is still not done here —
    a `worktree_root` resolved harder than the other end resolves it would
    compute a path `resume` does not, which is the finding this branch already
    carries from the other side."""
    checkout = workspace_config(home)
    real = home / "real-wt"
    real.mkdir()
    (home / "wtlink").symlink_to(real)
    where = atlas / ".specify" / "extensions" / "git"
    where.mkdir(parents=True, exist_ok=True)
    (where / "git-config.yml").write_text(
        f"checkout_mode: worktree\nworktree_root: {home / 'wtlink'}\n",
        encoding="utf-8")
    elsewhere = home / "elsewhere" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", elsewhere)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip,
           parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"no `worktree move` fixes this one, because the worktree root "
            f"itself is reached through a symlink: both verbs compute "
            f"{home / 'wtlink'} and git reports the path that link resolves "
            f"to, so `resume` matches nothing registered there however the "
            f"worktree is moved — spell `worktree_root` (or "
            f"`$SPECKIT_GIT_WORKTREE_ROOT`) as the directory git spells, "
            f"which is {real}, and the `git worktree move` this line would "
            "otherwise name becomes one that works") in result.stdout, (
        result.stdout)

    # AND A LINK WHOSE TARGET IS NOT THERE YET is the same refusal, which
    # `physical_path` cannot see (Copilot's fourth round on #27): `cd` into it
    # fails, so the fallback returns the lexical path and the two compare
    # equal — while `[ -L ]` on the component answers whether or not the
    # target exists, and `mkdir -p` through such a link answers "cannot create
    # directory '…': File exists", so the exit would die on its first operand.
    rmtree(real)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "no `worktree move` fixes this one" in result.stdout, result.stdout
    assert "the directory git spells, and the `git worktree move`" in (
        result.stdout), "with no target there, git spells no directory yet"
    real.mkdir()
    assert f"worktree move {elsewhere}" not in result.stdout

    # AND WITH THE ROOT SPELLED THE WAY GIT SPELLS IT the move is named again,
    # which is the control: the same estate, the same worktree, one line of
    # config apart.
    (where / "git-config.yml").write_text(
        f"checkout_mode: worktree\nworktree_root: {real}\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"worktree move {elsewhere} {real / '001-a-thing'}") in (
        result.stdout), result.stdout


def test_only_the_leg_the_run_stops_at_speaks_for_the_path(trio, home):
    """COPILOT'S FIRST ROUND ON #27 (2026-09-13, suppressed), verbatim: "When
    an earlier leg has already set the feature verdict to `inway` (or `add`),
    `refused_exit` is nonempty for every sibling, so this guard still lets
    later legs re-enter `path_in_the_way` (and the analogous off-path guard
    below). If a later leg also has an obstruction, its own refusal/exit is
    reported even though `resume` stops at the earlier leg and the first-pass
    verdict is meant to be carried to all siblings. Track the refusing leg and
    only run these path checks for that leg; otherwise render the stored
    verdict for siblings."

    IT IS REAL, and the run says so. On a scratch three-leg estate on
    2026-09-13 — bare remotes in a temp dir, a fake `$HOME`, workBenches' own
    scripts — with a stray DIRECTORY at the `spec` leg's computed path and a
    worktree of another branch at the `code` leg's, `resume.sh` answered
    ONCE: "Error: 'worktrees/001-a-thing/spec' exists and is not a registered
    worktree of the spec leg; that feature was NOT recreated", "REFUSED:
    001-a-thing — an unrelated path is in the way", exit 2. It breaks at the
    FIRST leg in the record's order and never reads the second leg's path, so
    a second line quoting "an unrelated worktree is in the way" is a REFUSED
    reason that run does not print — the drift this file's own rules forbid,
    and the one the round before this closed from the other side.

    So the verdict carries its leg's ORDINAL now, and the two arms that read
    a path run for that leg alone. The sibling says what every sibling of a
    refused feature says: the verdict, and the exit that travels with it."""
    checkout = workspace_config(home)
    spec, code = trio / "spec", trio / "code"
    for leg in (spec, code):
        git("checkout", "-q", "main", cwd=leg)
        origin_has_branch(leg, "001-a-thing")
    spec_tip = git("rev-parse", "origin/001-a-thing", cwd=spec).stdout.strip()
    code_tip = git("rev-parse", "origin/001-a-thing", cwd=code).stdout.strip()
    spec_want = parked_worktree(trio, "001-a-thing", "spec")
    code_want = parked_worktree(trio, "001-a-thing", "code")
    spec_want.mkdir(parents=True)
    (spec_want / "stray.txt").write_text("not ours\n", encoding="utf-8")
    code_want.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "-b", "002-other", str(code_want), cwd=code)
    path = record(checkout, "trio", branch="001-a-thing", role="spec",
                  commit=spec_tip, parked_on="Falcon", root="Trio")
    path.write_text(path.read_text(encoding="utf-8")
                    + leg_block("code", code_tip), encoding="utf-8")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0].startswith(
        f"- parked feature 001-a-thing (spec leg): a directory is at "
        f"{spec_want}, which is the path `resume` computes for this leg"
        ), findings[0]
    assert findings[1] == (
        "- parked feature 001-a-thing (code leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        f"WHOLE feature, because a directory is at the {spec_want} it "
        "computes for its `spec` leg, so it does not bring this leg back — "
        f"move it aside with `mv {spec_want} <a path of your choosing>`, "
        "which is yours to run — nothing here moves or deletes a path it did "
        "not create"), findings[1]
    assert "an unrelated worktree is in the way" not in result.stdout, (
        "`resume` stops at the spec leg and never reads the code leg's path")
    assert str(code_want) not in result.stdout, (
        "the later leg's obstruction is one the run never reaches")
    assert "`resume Trio`" not in result.stdout

    # AND WITH THE RECORD'S ORDER REVERSED the other leg is the one that
    # speaks, which is what makes this the record's order and not a priority
    # between readings.
    path = record(checkout, "trio", branch="001-a-thing", role="code",
                  commit=code_tip, parked_on="Falcon", root="Trio")
    path.write_text(path.read_text(encoding="utf-8")
                    + leg_block("spec", spec_tip), encoding="utf-8")
    result = run(STATUS, "Trio", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0].startswith(
        f"- parked feature 001-a-thing (code leg): a worktree on `002-other` "
        f"is at {code_want}, which is the path `resume` computes for this leg"
        ), findings[0]
    assert "an unrelated path is in the way" not in result.stdout, (
        "with the code leg first, the spec leg's directory is never read")


def test_the_path_takes_its_place_in_that_order_and_the_add_does_not(
        trio, home):
    """THE SAME ORDER, WITH THE TWO READINGS THIS BRANCH ADDS IN IT. The test
    above settled that the feature's verdict is the FIRST leg `resume`
    refuses in the RECORD's order; this branch teaches that pass two more
    refusals — RR4's second arm and RR3, which are the PATH, and the `git
    worktree add` that is the LAST thing the run does — and where each of
    them goes is not a matter of taste. `resume.sh`'s leg loop is RR6 -> RR4
    -> RR3 -> RR2 -> RR1 -> RR5, every one of them `refused=true; break`, and
    the loop that creates the worktrees runs only after every leg has passed
    all six.

    COPILOT'S FIFTH ROUND ON #23 (2026-09-13, suppressed), verbatim: "A
    stale-registration leg before a later gone-origin leg is not represented
    in this verdict pass … `resume` stops at RR3 first." FIVE ESTATES WERE
    BUILT TO SETTLE IT, on 2026-09-13, against workBenches' own `resume.sh`,
    `park.sh`, `git-common.sh` and `workspace-common.sh` — a three-leg estate
    with bare remotes in a temp dir and a fake `$HOME`, the `spec` leg
    recorded FIRST and the `code` leg second with `code`'s branch deleted on
    its origin:

      (a) a stray DIRECTORY at the `spec` leg's computed path
          "Error: 'worktrees/001-a-thing/spec' exists and is not a registered
          worktree of the spec leg", "REFUSED: 001-a-thing — an unrelated
          path is in the way", exit 2 — RR3 on the EARLIER leg, and origin
          never read for the later one. THE ROUND IS RIGHT ABOUT THIS SHAPE.
      (b) a PRUNABLE registration at that path with nothing on disk
          "Error: 001-a-thing is no longer on origin in the code leg",
          "REFUSED: 001-a-thing — gone from origin", exit 2 — in BOTH
          spellings, the registration for ANOTHER branch and the one for the
          RECORDED branch: `load_git_worktrees` drops a prunable block so RR4
          never sees it, `[ -e "$tree" ]` finds nothing so RR3 passes, and
          the LATER leg's RR2 is the refusal the person gets. THE ROUND'S
          PREMISE IS WRONG FOR A STALE REGISTRATION.
      (c) the `spec` leg's WORKTREE on the branch, off the computed path
          "Error: 001-a-thing is no longer on origin in the code leg",
          "REFUSED: 001-a-thing — gone from origin", exit 2 — the add is the
          last thing the run does and every RR of every leg comes first, so
          the later leg's RR2 takes it. THE ROUND'S PREMISE IS WRONG HERE
          TOO, and this reading never claimed otherwise.

    And the control that tells (a) from (b): a LOCKED registration for
    another branch at that path with nothing on disk — which git computes no
    `prunable` for, so `leg_registered_at` DOES match it — answered "REFUSED:
    001-a-thing — an unrelated worktree is in the way", exit 2, RR4's second
    arm on the earlier leg in front of the later leg's RR2.

    So the round is REAL for a path in the way and WRONG for a stale
    registration, which is the distinction `path_in_the_way` already makes;
    what this pins is that the VERDICT PASS makes it too, in one array, so
    that no reading overtakes another by being read back in a different
    order."""
    checkout = workspace_config(home)
    spec, code = trio / "spec", trio / "code"
    for leg in (spec, code):
        git("checkout", "-q", "main", cwd=leg)
        origin_has_branch(leg, "001-a-thing")
    spec_tip = git("rev-parse", "origin/001-a-thing", cwd=spec).stdout.strip()
    code_tip = git("rev-parse", "origin/001-a-thing", cwd=code).stdout.strip()
    drop_from_origin(code, "001-a-thing")

    def two_legs():
        path = record(checkout, "trio", branch="001-a-thing", role="spec",
                      commit=spec_tip, parked_on="Falcon", root="Trio")
        path.write_text(path.read_text(encoding="utf-8")
                        + leg_block("code", code_tip), encoding="utf-8")

    def findings(*args):
        result = run(STATUS, *args, home=home)
        assert result.returncode == 1, result.stdout + result.stderr
        return result, [line.strip() for line in result.stdout.splitlines()
                        if line.strip().startswith("- parked feature")]

    want = parked_worktree(trio, "001-a-thing", "spec")

    # (a) RR3 ON THE EARLIER LEG BEATS RR2 ON THE LATER ONE.
    want.mkdir(parents=True)
    (want / "stray.txt").write_text("not ours\n", encoding="utf-8")
    two_legs()
    result, lines = findings("--fetch", "Trio")
    assert len(lines) == 2, lines
    assert lines[0].startswith(
        f"- parked feature 001-a-thing (spec leg): a directory is at {want}, "
        "which is the path `resume` computes for this leg"), lines[0]
    assert lines[1] == (
        "- parked feature 001-a-thing (code leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon; `resume` refuses the "
        f"WHOLE feature, because a directory is at the {want} it computes for "
        "its `spec` leg, so it does not bring this leg back — move it aside "
        f"with `mv {want} <a path of your choosing>`, which is yours to run — "
        "nothing here moves or deletes a path it did not create"), lines[1]
    assert "is no longer on origin" not in result.stdout, (
        "RR3 breaks the loop on the earlier leg and origin is never read")
    assert "delete its `- branch:" not in result.stdout, (
        "RR2's exits are the wrong thing to name for a path in the way")
    rmtree(want)

    # (b) A STALE REGISTRATION IS NOT RR3's, AND THE LATER LEG'S RR2 TAKES IT
    # — in both spellings, the one for another branch and the one for the
    # recorded branch, because `load_git_worktrees` drops a prunable block
    # whichever branch it names.
    for other in ("002-other", "001-a-thing"):
        want.parent.mkdir(parents=True, exist_ok=True)
        if other == "001-a-thing":
            git("worktree", "add", "-q", str(want), "001-a-thing", cwd=spec)
        else:
            git("worktree", "add", "-q", "-b", other, str(want), cwd=spec)
        rmtree(want)            # and NO `git worktree prune`
        porcelain = git("worktree", "list", "--porcelain", cwd=spec).stdout
        assert "prunable" in porcelain, "git pruned it for us; the test is moot"
        two_legs()
        result, lines = findings("--fetch", "Trio")
        assert len(lines) == 2, lines
        assert "worktree prune`" in lines[0], lines[0]
        assert ("`resume` refuses the WHOLE feature in any case, because there "
                "is no `origin/001-a-thing` in its `code` leg after this run's "
                "fetch") in lines[0], lines[0]
        assert lines[1].endswith(
            "the exits are to delete its `- branch: 001-a-thing` block from "
            "the record where the feature landed, or to push the branch again "
            "from Falcon where it went by mistake"), lines[1]
        assert "is in the way" not in result.stdout, (
            "RR4 never sees a prunable block and RR3 finds nothing on disk")
        git("worktree", "prune", cwd=spec)

    # (c) THE ADD RUNS LAST, so the later leg's RR2 beats it — while WITHOUT
    # the flag, which is the only run that reads RR2 here, the off-path
    # worktree is the verdict and the move is the exit.
    elsewhere = home / "elsewhere" / "001-a-thing"
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", str(elsewhere), "001-a-thing", cwd=spec)
    two_legs()
    result, lines = findings("--fetch", "Trio")
    assert len(lines) == 1, lines
    assert lines[0].startswith(
        "- parked feature 001-a-thing (code leg): no worktree on that branch "
        "here, parked 2026-09-10T20:00:00Z on Falcon, and no "
        "`origin/001-a-thing` here after this run's fetch"), lines[0]
    assert "worktree move" not in result.stdout, (
        "every RR of every leg is asked before the first worktree is added")
    result, lines = findings("Trio")
    assert len(lines) == 2, lines
    assert lines[0].startswith(
        "- parked feature 001-a-thing (spec leg): its worktree is at "
        f"{elsewhere}, which is not the {want} `resume` computes for it"
        ), lines[0]
    assert (f"`resume` refuses the WHOLE feature, because its `spec` leg's "
            f"worktree is at {elsewhere}") in lines[1], lines[1]
    assert "`resume Trio`" not in result.stdout


def test_no_leg_beside_one_rr6_refuses_says_resume_brings_it_back(trio, home):
    """THE HOLE THE VERDICT CLOSES ON ITS WAY PAST, and the rule is the one at
    the top of `check_parked_leg`: NO LINE OF A FEATURE `resume` REFUSES WHOLE
    MAY NAME `resume <Name>` (Copilot on #21, second round). RR6 is
    `[ "$pushed" != true ]` and it is the FIRST test in the per-leg loop —
    before RR4, so a worktree here does not save it — and it ends
    `refused=true; break`, which throws the feature out with every other leg
    of it. A good leg beside a `--no-push` one therefore went on saying
    "`resume Trio` brings it back" about a feature `resume` will not recreate,
    which is the pair the rule forbids.

    ALL FOUR SPELLINGS RR6 REFUSES, and in both orders, because the record's
    order decides which refusal is REPORTED and not whether the feature is
    refused: the loop breaks at the first one wherever it sits, and the legs
    before it were only ever collected."""
    checkout = workspace_config(home)
    spec, code = trio / "spec", trio / "code"
    for leg in (spec, code):
        git("checkout", "-q", "main", cwd=leg)
        origin_has_branch(leg, "001-a-thing")
    for pushed, why in (
            ("false", "its `code` leg was parked with --no-push"),
            (None, "the record has no `pushed:` for its `code` leg"),
            ("", "its `code` leg's `pushed:` has no value, which is neither "
                 "true nor false"),
            ("maybe", "its `code` leg's `pushed:` says 'maybe', which is "
                      "neither true nor false")):
        for order in ("spoiler-first", "good-first"):
            path = record(checkout, "trio", branch="001-a-thing", role="code",
                          commit=FAKE_SHA, pushed=pushed, parked_on="Falcon",
                          root="Trio")
            spoiler = path.read_text(encoding="utf-8")
            good = leg_block("spec", FAKE_SHA)
            head, _, culprit = spoiler.partition("          - role: code\n")
            path.write_text(
                spoiler + good if order == "spoiler-first"
                else head + good + "          - role: code\n" + culprit,
                encoding="utf-8")
            result = run(STATUS, "Trio", home=home)
            assert result.returncode == 1, result.stdout + result.stderr
            assert ("    - parked feature 001-a-thing (spec leg): no worktree "
                    "on that branch here, parked 2026-09-10T20:00:00Z on "
                    f"Falcon; `resume` refuses the WHOLE feature, because {why}"
                    ", so it does not bring this leg back — park that feature "
                    "again from Falcon, which writes the record afresh"
                    ) in result.stdout, (pushed, order, result.stdout)
            assert "`resume Trio`" not in result.stdout, (pushed, order)


def test_a_root_key_between_a_branch_and_its_legs_still_reads_that_feature(
        atlas, home):
    """THIS RECORD WAS THE CRASH FIRST AND THE MISREADING SECOND, and the two
    reviews are worth keeping together.

    The independent review of this branch, 2026-09-12: the second pass read
    `${feature_why[seen_branches - 1]:-}` unguarded, where the first pass's
    lookup is guarded by `[ "$legs" -gt 0 ]` — and `$seen_branches` COULD be 0
    at a `leg` row, because `record_rows` emitted a `branch` row only where
    `$matched` was 1 AT the `- branch:` line, while a record selected by
    `root=` — one filed under the folder name, and every family member — has
    `$matched` set by its `root:` line. Put that key between a feature's
    `- branch:` line and its legs and the block yielded a leg row with no
    branch row before it: subscript -1, "bad array subscript" on bash 3.2 and,
    on bash 4.2 and later with a non-empty array, the LAST feature's verdict
    printed about a feature it is no verdict of. Against 5cb123b the first
    record below died mid-report — exit 1 with no footer, and under `--all` it
    took the sweep with it.

    Copilot's second round on #22 then named the row that was missing rather
    than the subscript it made: a block is not known to be the selected one
    until the key that selects it is read, and every row above that key was
    being thrown away for a block that DID match. So this record is read whole
    now — the `project` row with it, which is why the line below names the
    workstation and the date instead of `? on ?`, and why the feature is
    COUNTED. `record_rows` can no longer hand out a leg row with no branch row
    before it, `$named` being set by the same line that appends the branch
    row; the guard in `read_record` stays as the belt to that brace, and this
    test is what proves the record it was written for now reads."""
    checkout = workspace_config(home)
    manifest = atlas / "project.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "id: atlas\n", "id: atlas-core\n"), encoding="utf-8")
    commit_all(atlas, "an id that is not the folder's name")
    git("push", "-q", "origin", "main", cwd=atlas)
    path = record(checkout, "Atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, root="Atlas")
    text = path.read_text(encoding="utf-8")
    assert text.count("    root: Atlas\n") == 1, text
    assert text.count("        legs:\n") == 1, text
    mangled = (text.replace("    root: Atlas\n", "")
                   .replace("        legs:\n", "    root: Atlas\n"
                            "        legs:\n"))
    path.write_text(mangled, encoding="utf-8")

    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here; parked 2026-09-10T20:00:00Z on Eagle — `resume "
            "Atlas` brings it back, unless origin has lost that branch: there is no "
            "`origin/001-a-thing` here as of the last fetch, and `resume` "
            "refuses a leg whose branch is not on origin, taking the WHOLE "
            "feature with it (\"001-a-thing is no longer on origin in the "
            "repo leg\") — `status --fetch` settles which"
            ) in result.stdout
    assert ("    parked record: 1 feature(s), parked 2026-09-10T20:00:00Z on "
            "Eagle (lane xfactory-2); active 001-a-thing") in result.stdout, (
        "the block matched on `root:` and the rows above it were held, not "
        "dropped")
    assert result.stdout.splitlines()[-1] == (
        "status: Atlas - 1 finding(s) in 2 repositories; nothing was changed."
        ), "the footer, which a report that died mid-run never reaches"
    assert "refuses the WHOLE feature" not in result.stdout
    # (On this branch the leg line carries the RR2 clause as well: the
    # branch was never pushed, so origin has not got it — the commit that
    # reads a branch origin has lost. The verdict this test guards is the
    # feature one, still absent.)

    # AND WITH A FEATURE AFTER IT, the verdict that is not this leg's: on bash
    # 5 `${feature_why[-1]}` was the OTHER feature's refusal, on the line of a
    # leg the record files under this one. Each feature keeps its own now.
    path.write_text(mangled + "      - branch: 002-another\n"
                    "        legs:\n" + leg_block("nope", FAKE_SHA),
                    encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 2, findings
    assert findings[0] == (
        "- parked feature 001-a-thing (repo leg): no worktree on that branch "
        "here; parked 2026-09-10T20:00:00Z on Eagle — `resume Atlas` brings "
        "it back, unless origin has lost that branch: there is no "
        "`origin/001-a-thing` here as of the last fetch, and `resume` "
        "refuses a leg whose branch is not on origin, taking the WHOLE "
        "feature with it (\"001-a-thing is no longer on origin in the "
        "repo leg\") — `status --fetch` settles which"), findings[0]
    assert findings[1].startswith(
        "- parked feature 002-another (nope leg): the record names a leg this "
        "root does not mount here; `resume` maps each leg's role onto this "
        "checkout and refuses the WHOLE feature"), findings[1]
    assert "    parked record: 2 feature(s)" in result.stdout


def test_every_leg_of_a_record_is_read_once_and_in_order(atlas, home):
    """THE STRUCTURAL HALF of the same review note, held on its own. The leg
    row used to go out at the leg's `pushed:` line; it now goes out where the
    LEG ENDS — the next `- role:`, the next feature's `- branch:`, the next
    project block's `- id:`, or the end of the file — so a leg without that
    key is read like any other. What must not change is everything else: one
    row per leg, in the order the record lists them, and no row for a block
    that is not this root's.

    Three features in one block exercise three of the four enders at once: the second
    feature's first leg is closed by its own second `- role:`, its second leg
    by the third feature's `- branch:`, and the third feature's leg by the
    NEXT PROJECT's `- id:` — and the leg that carries no `pushed:` sits in
    the middle, where a dropped row would have been invisible in a count of
    two. The fourth ender, the end of the file, closes the last leg of every
    record `record()` writes, whose last line is a leg's last key — every
    other record-layer test holds that one."""
    checkout = workspace_config(home)
    (checkout / "workspaces" / ORG).mkdir(parents=True, exist_ok=True)
    (checkout / "workspaces" / ORG / "atlas.yaml").write_text("""\
schema_version: 1
kind: workspace-manifest
written_by: speckit park
projects:
  - id: atlas
    repository: testorg/Atlas
    shape: three-leg
    root: Atlas
    tracking_branch: main
    worktree_root: worktrees
    parked_at: 2026-09-10T20:00:00Z
    parked_on: Falcon
    parked_by_lane: xfactory-2
    features:
      - branch: 001-a-thing
        legs:
          - role: repo
            remote: origin
            parked_commit: {sha}
            wip: true
            wip_depth: 1
            pushed: false
      - branch: 002-b-thing
        legs:
          - role: repo
            remote: origin
            parked_commit: {sha}
            wip: true
            wip_depth: 1
          - role: spec
            remote: origin
            parked_commit: {sha}
            wip: true
            wip_depth: 1
            pushed: true
      - branch: 003-c-thing
        legs:
          - role: repo
            remote: origin
            parked_commit: {sha}
            wip: true
            wip_depth: 1
            pushed: true
  - id: other
    repository: testorg/Other
    shape: single
    root: Other
    features:
      - branch: 004-d-thing
        legs:
          - role: repo
            remote: origin
            parked_commit: {sha}
            wip: true
            wip_depth: 1
            pushed: true
""".format(sha=FAKE_SHA), encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    parked record: 3 feature(s)" in result.stdout
    legs = [line.split("parked feature ", 1)[1].split(":", 1)[0]
            for line in result.stdout.splitlines() if "parked feature " in line]
    assert legs == ["001-a-thing (repo leg)", "002-b-thing (repo leg)",
                    "002-b-thing (spec leg)", "003-c-thing (repo leg)"], legs
    assert "the record has no `pushed:` for that leg" in result.stdout
    assert "004-d-thing" not in result.stdout, (
        "a block that is not this root's was read")


def test_a_comment_after_pushed_is_read_as_the_loader_reads_it(atlas, home):
    """The extension's `workspace_load_project` strips a `#` comment from
    EVERY line before it reads the value, so `resume.sh` sees `pushed: true #
    note` as `true` and RECREATES the leg. Read whole here it was "neither
    true nor false", and the finding named a refusal `resume` would not make
    — the independent review of this follow-up, 2026-09-11. `pushed:` is the
    field this layer JUDGES rather than matches or prints, so it is read the
    way the judge reads it: with no worktree here, `true # note` names
    `resume <Name>` and says nothing about the value."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed="true # hand-written note", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "`resume Atlas` brings it back" in result.stdout
    assert "neither true nor false" not in result.stdout, (
        "a value `resume.sh` reads as `true`, called unreadable")

    # And `false # note` is the `--no-push` record it says it is — which
    # against a2c8521 read as `true`, the only other thing `= false` misses.
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed="false # hand-written note", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("parked with --no-push on Falcon and no worktree on that branch "
            "here") in result.stdout
    assert "neither true nor false" not in result.stdout
    assert "`resume Atlas`" not in result.stdout


def test_a_comment_after_any_records_value_is_read_as_the_loader_reads_it(
        atlas, home):
    """Copilot on #21: `role:` was read with `trim_unquote` alone, so
    `- role: # note` was NOT empty here — it was `# note` — while the
    extension's loader takes `#` and everything after it off every line before
    it reads a value, and so treats that leg as roleless and refuses the whole
    feature. Here the leg went to `leg_repo_for_role` and drew "the record
    names a leg this root does not mount here" instead. #19 closed this gap
    for `pushed:` alone; `record_scalar` now closes it for every value this
    parser reads — `role:`, `parked_commit:` and the rest — because a reader
    that judges a value must read it the way the judge will."""
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon")
    text = path.read_text(encoding="utf-8")
    assert text.count("          - role: repo\n") == 1
    assert text.count(f"            parked_commit: {FAKE_SHA}\n") == 1
    path.write_text(text
                    .replace("          - role: repo\n",
                             "          - role: repo # the leg that holds the code\n")
                    .replace(f"            parked_commit: {FAKE_SHA}\n",
                             f"            parked_commit: {FAKE_SHA} # hand-written\n"),
                    encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    # The role read as `repo` (not "does not mount here") and the commit as
    # the sha alone: the missing-commit line names it by its first seven.
    assert "does not mount here" not in result.stdout
    assert f"its parked commit {FAKE_SHA[:7]} is not here" in result.stdout

    # A role that is EMPTY under a comment is roleless to the loader, and so
    # the whole-feature finding, never the mounting arm's.
    for spelling in ("          - role: # note\n", '          - role: "" # note\n'):
        text = path.read_text(encoding="utf-8")
        text = text.replace("          - role: repo # the leg that holds the code\n",
                            spelling)
        text = text.replace("          - role: # note\n", spelling)
        text = text.replace('          - role: "" # note\n', spelling)
        path.write_text(text, encoding="utf-8")
        result = run(STATUS, "Atlas", home=home)
        assert result.returncode == 1, result.stdout + result.stderr
        assert ("    - parked feature 001-a-thing: a leg of it in the record "
                "has no role;") in result.stdout, spelling
        assert "does not mount here" not in result.stdout, spelling


def test_a_comment_after_a_project_yaml_leg_value_is_read_as_the_loader_reads_it(
        atlas, home):
    """Copilot on #22: `leg_repo_for_role` read `project.yaml`'s `role:` and
    `path:` with `trim_unquote` alone, while `load_repo_shape` takes `#` and
    everything after it off every line before it reads a key. So `- role:
    spec # the spec leg`, declared with no `path:` and not checked out here,
    never matched the role this reader wanted, and the leg fell to the arm
    that calls it a role this root cannot mount and `resume` refuses whole —
    where `resume` maps `spec` fine and refuses the whole ESTATE for the
    missing checkout instead. The values lose their comments the way the
    loader loses them, and the short line comes back."""
    checkout = workspace_config(home)
    manifest = atlas / "project.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace("kind: project-manifest\n",
                 "kind: project-manifest\nschema: project-repo-schema\n")
        .replace("  - role: spec\n"
                 f"    repository: {ORG}/Atlas-spec\n"
                 "    path: spec\n",
                 "  - role: spec # the spec leg\n"
                 f"    repository: {ORG}/Atlas-spec\n"
                 "  - role: code # the code leg\n"
                 f"    repository: {ORG}/Atlas-code\n"),
        encoding="utf-8")
    assert "role: spec # the spec leg" in manifest.read_text(encoding="utf-8")
    rmtree(atlas / "spec")
    record(checkout, "atlas", branch="001-a-thing", role="spec",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert len(findings) == 1, findings
    assert findings[0].startswith(
        "- parked feature 001-a-thing (spec leg): the record names a leg this "
        "root does not mount here"), findings
    assert "refuses the WHOLE feature" not in result.stdout, (
        "a comment after the role read as a role this root cannot mount")


def code_leg_onto_the_spec_checkout(atlas: Path, *, path_line: str,
                                    above_path: str = "") -> None:
    """The Atlas manifest made genuinely three-leg — `kind:`, `schema:`, a
    `spec` leg and a `code` one — with the CODE leg declared onto the
    directory this fixture already mounts, and `$above_path` put between that
    leg's `- role:` line and its `$path_line`.

    THE PATH HAS TO DIFFER FROM THE ROLE'S OWN NAME for a reading of it to be
    provable at all: where the path IS `code`, `_shape_record_leg`'s default
    and a `path:` this reader lost are the same answer, and there is nothing
    to tell apart. `spec/` is the one checkout under this root, so the `code`
    leg is declared onto it and the assertion is that the leg is read THERE.
    """
    manifest = atlas / "project.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace("kind: project-manifest\n",
                 "kind: project-manifest\nschema: project-repo-schema\n")
        .replace("  - role: spec\n"
                 f"    repository: {ORG}/Atlas-spec\n"
                 "    path: spec\n",
                 "  - role: spec\n"
                 f"    repository: {ORG}/Atlas-spec\n"
                 "    path: spec\n"
                 "  - role: code\n"
                 f"    repository: {ORG}/Atlas-code\n"
                 + above_path + path_line),
        encoding="utf-8")


#: What a `code` leg mounted at `spec/` reads as when this root is read the
#: way `load_repo_shape` reads it: the leg is found, and the only thing out of
#: step is that nothing here is on that branch.
CODE_LEG_AT_SPEC = ("    - parked feature 001-a-thing (code leg): no worktree "
                    "on that branch here; parked 2026-09-10T20:00:00Z on "
                    "Falcon — `resume Atlas` brings it back")


def test_a_comment_after_a_project_yaml_leg_path_is_cut_where_the_loader_cuts_it(
        atlas, home):
    """Copilot's THIRD round on #22: the `path:` half of the `#` cut #22 gave
    `leg_repo_for_role` had no test of its own. The round before it proves the
    `role:` half — `- role: spec # the spec leg`, declared with no `path:` —
    and the round after it proves a FULL-LINE comment; neither reads a `path:`
    whose own value carries a `#`, so the one line that does could have been
    dropped and the suite stayed green.

    `load_repo_shape` takes `#` and everything after it off every line before
    it splits key from value, so `path: spec # the checkout it is mounted at`
    is `spec` there and the leg is `CODE_LEG=<root>/spec`. Read whole here it
    was `<root>/spec # the checkout it is mounted at`, a path with no `.git`
    in it, and the leg drew "the record names a leg this root does not mount
    here" for a leg `resume` mounts and resumes — and it did NOT fall back to
    `_shape_record_leg`'s default either, because the `path:` arm answers
    before the default does."""
    checkout = workspace_config(home)
    code_leg_onto_the_spec_checkout(
        atlas, path_line="    path: spec # the checkout it is mounted at\n")
    assert "path: spec # the checkout it is mounted at" in \
        (atlas / "project.yaml").read_text(encoding="utf-8")
    record(checkout, "atlas", branch="001-a-thing", role="code",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert CODE_LEG_AT_SPEC in result.stdout
    assert "does not mount here" not in result.stdout, (
        "the comment read as part of the path, so the leg was looked for at a "
        "directory no manifest names")


def test_a_full_line_comment_inside_a_project_yaml_leg_does_not_end_the_leg(
        atlas, home):
    """Copilot's second round on #22: `leg_repo_for_role` lost the `#` after a
    value in the round before, and kept reading a full-line comment at COLUMN
    0 as the indent-zero key that closes the leg — `[![:space:]]*) role=""`.
    `load_repo_shape` takes `#` and everything after it off every line before
    it reads one, so that line is nothing to the loader and the `path:` below
    it still belongs to the leg above. Read as a leg-ender here, the `path:`
    was dropped and the role fell to `_shape_record_leg`'s default — the
    role's own name — so a `code` leg this manifest maps onto a directory of
    another name was reported as a leg this root does not mount, where
    `resume` maps it and brings the feature back. The same treatment #20 gave
    the record's own parser (a2c8521's `record_rows`), for the same reason."""
    checkout = workspace_config(home)
    code_leg_onto_the_spec_checkout(
        atlas, above_path="# a note a hand left here, at column 0\n",
        path_line="    path: spec\n")
    record(checkout, "atlas", branch="001-a-thing", role="code",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert CODE_LEG_AT_SPEC in result.stdout
    assert "does not mount here" not in result.stdout, (
        "a comment line read as the end of the leg, and the `path:` under it "
        "dropped")


#: The Atlas manifest made genuinely three-leg with its `legs:` list indented
#: FOUR spaces and its keys SIX — which YAML allows anywhere and
#: `load_repo_shape` reads by keying on the item's own indent, not on a
#: column. The `code` leg is declared onto `spec/`, the one checkout under this
#: root, because a path that differs from the role's own name is the only kind
#: whose reading can be proved.
DEEP_LEGS_YAML = """\
schema_version: 1
kind: project-manifest
schema: project-repo-schema
id: atlas
name: "Atlas"
tracking_branch: main
legs:
    - role: assembly
      repository: {org}/Atlas
      path: "."
    - role: spec
      repository: {org}/Atlas-spec
      path: spec
    - role: code
      repository: {org}/Atlas-code
{above}      path: spec
"""


def test_a_legs_list_indented_deeper_is_read_the_way_the_loader_reads_it(
        atlas, home):
    """The independent review of this branch, 2026-09-12, verbatim: "list
    items at 4-space indent (`    - role: spec` / `      path: docs`) → both
    shape readers say three-leg; leg_repo_for_role answers NOTHING for spec
    and code → first pass sets feature_why "names a role this root does not
    mount" → false whole-feature refusal."

    TWO READERS OF ONE FILE IS WHAT MADE THAT POSSIBLE. `read_root_shape`
    walks `project.yaml` the way `load_repo_shape` walks it — `#` and
    everything after it off every line, an empty line skipped, a `- ` item at
    ANY indent opening a leg and keys two past its own belonging to it — while
    `leg_repo_for_role` scanned the same file again by COLUMN, `'  - role:'*`
    and `'    path:'*`, and answered nothing for a manifest indented any other
    way. The shape reader therefore called this root three-leg, `collect_legs`
    maps `code` onto a three-leg checkout, and the leg was still reported as a
    role this root does not mount and the whole feature refused for it — a
    refusal `resume` does not make. The walk records each leg's role and
    `path:` as it passes now, and this function reads those back: ONE parser
    of `project.yaml` in this file.

    Verified against the extension on 2026-09-12 by sourcing `git-common.sh`
    and running `load_repo_shape` on this manifest: `REPO_SHAPE=three-leg`,
    `SHAPE_SPEC_PATH=spec`, `SHAPE_CODE_PATH=spec`, `CODE_LEG=<root>/spec`,
    with and without the column-0 comment below — and on the review's own
    spelling of it (a two-space list whose `spec` leg carries `path: docs`
    under such a comment and whose `code` leg carries `path: src`):
    `SHAPE_SPEC_PATH=docs`, `SHAPE_CODE_PATH=src`."""
    checkout = workspace_config(home)
    manifest = atlas / "project.yaml"
    manifest.write_text(DEEP_LEGS_YAML.format(org=ORG, above=""),
                        encoding="utf-8")
    record(checkout, "atlas", branch="001-a-thing", role="code",
           commit=FAKE_SHA, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert CODE_LEG_AT_SPEC in result.stdout
    assert "does not mount here" not in result.stdout, (
        "the leg was looked for at a path no manifest names, because the "
        "`path:` line was indented past the column this reader wanted")
    assert "refuses the WHOLE feature" not in result.stdout, (
        "a whole-feature refusal `resume` does not make: it maps `code` onto "
        "this checkout and brings the feature back")

    # AND A COLUMN-0 COMMENT INSIDE THE ITEM CLOSES NOTHING AT THAT INDENT
    # EITHER, which is the other half of one parser: the walk takes `#` and
    # everything after it off the line and SKIPS what is left when it is
    # empty, wherever the item's keys sit.
    manifest.write_text(DEEP_LEGS_YAML.format(
        org=ORG, above="# a note a hand left here, at column 0\n"),
        encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert CODE_LEG_AT_SPEC in result.stdout
    assert "does not mount here" not in result.stdout


def test_a_leg_declared_at_the_root_is_read_at_the_root(atlas, home):
    """Copilot's first round on #23, verbatim: "this special-cases `path: "."`
    as if the path were omitted, but the extension's `_shape_record_leg`
    preserves any non-empty path and builds `SPEC_LEG`/`CODE_LEG` as
    `$root/$SHAPE_*_PATH`; therefore a declared `spec` or `code` leg with
    `path: "."` is mapped to the root repository. Status will instead inspect
    `$root/spec` or `$root/code` (or report it missing), so its
    worktree/origin findings disagree with `resume`."

    IT DOES, AND EVERY SPELLING OF IT DOES. Run against the extension on
    2026-09-12 on a manifest whose `code` leg carries `path: "."`, `path: .`
    and `path: '.'` in turn: `load_repo_shape` answered `REPO_SHAPE=three-leg`,
    `SHAPE_CODE_PATH=.` and `CODE_LEG=<root>/.` for all three — `.` is not
    empty, so `"${path:-code}"` keeps it — and an EMPTY `path:` was the one
    spelling that fell to the default `code`. `collect_legs` hands `$CODE_LEG`
    straight to `LEG_REPOS`, so the leg `resume` reads is the ROOT. This
    reader skipped the declared `.`, found no `code/` and answered the default
    `<root>/code`, so the same estate drew "the record names a leg this root
    does not mount here" — a whole-feature refusal `resume` does not make.

    AND THE MOUNT IS `.` AT THE OTHER END TOO, which is what the proof turns
    on since this layer reads the path `collect_legs` computes: `LEG_TREES`
    for a `code` leg is `$WORKTREE_ROOT/$branch/$SHAPE_CODE_PATH`, and with
    the leg declared `path: "."` that is `worktrees/<branch>/.` — a string
    `leg_registered_at` never matches, because git spells no registered path
    with a trailing `/.`. Run end to end against the extension on 2026-09-12
    on a three-leg estate whose `code` leg carried `path: "."` and whose
    `spec` leg was a real submodule: with NOTHING at that path `resume.sh`
    RESUMED the feature — "code  worktrees/001-a-thing/.", exit 0; with the
    feature's own worktree on the recorded branch AT `worktrees/001-a-thing`
    it REFUSED, "Error: 'worktrees/001-a-thing/.' exists and is not a
    registered worktree of the code leg", "REFUSED: 001-a-thing — an
    unrelated path is in the way", exit 2; and with that worktree elsewhere
    it refused at the `git worktree add`, "'001-a-thing' is already used by
    worktree at …". So the ROOT's own registrations answer all three, and a
    leg read at `<root>/code` — a directory that does not exist — answers
    none of them.

    THE PROOF IS THE ROOT'S OWN WORKTREE LIST, not the absence of that line:
    the worktree this test makes is a worktree of the ROOT repository, and it
    is found, named and judged against `worktrees/001-a-thing/.` — the mount
    the manifest declares — while a reader looking at `<root>/code` would
    have neither the worktree nor the path."""
    checkout = workspace_config(home)
    where = home / "Atlas-wt" / "001-a-thing"
    tip = feature_worktree(atlas, "001-a-thing", where)
    record(checkout, "atlas", branch="001-a-thing", role="code", commit=tip,
           parked_on="Falcon")
    pristine = (atlas / "project.yaml").read_text(encoding="utf-8")
    computed = atlas / "worktrees" / "001-a-thing"
    for spelling in ('    path: "."\n', "    path: .\n", "    path: '.'\n"):
        (atlas / "project.yaml").write_text(pristine, encoding="utf-8")
        code_leg_onto_the_spec_checkout(atlas, path_line=spelling)
        result = run(STATUS, "Atlas", home=home)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "does not mount here" not in result.stdout
        assert (f"    - parked feature 001-a-thing (code leg): its worktree "
                f"is at {where}, which is not the {computed}/. `resume` "
                "computes for it") in result.stdout
        # AND IT NAMES NO COMMAND (Copilot's second round on #27), because
        # every operand this path could be put into was RUN and did not work:
        # `mv '<…>/001-a-thing/.' <dest>` is refused by coreutils outright,
        # and `mkdir -p <…>/001-a-thing && git worktree move <tree>
        # '<…>/001-a-thing/.'` exits 0 and leaves the worktree nested at
        # `<…>/001-a-thing/001-a-thing`, which is where neither verb looks
        # (git 2.43, GNU coreutils 9.4, both run 2026-09-12). The line says
        # so, and names the `collect_legs` that answers it.
        assert "`mkdir -p " not in result.stdout, result.stdout
        assert f"worktree move {where}" not in result.stdout, result.stdout
        assert ("there is no command that puts it where `resume` looks: this "
                'leg is declared `path: "."` in `project.yaml`') in (
            result.stdout), result.stdout
        assert ("a `collect_legs` that computes `<worktree_root>/<branch>` "
                "for a leg declared at the root, which is the standard's and "
                "not this command's") in result.stdout

    # AND WITH NO WORKTREE AT ALL the same leg is the ordinary parked feature
    # `resume` brings back — which is the other half of the same reading,
    # because a leg read at `<root>/code` is a whole-feature refusal in this
    # state too, and the extension resumed it (exit 0, the same day).
    git("worktree", "remove", "--force", str(where), cwd=atlas)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "does not mount here" not in result.stdout
    assert ("    - parked feature 001-a-thing (code leg): no worktree on that "
            "branch here") in result.stdout
    assert "`resume Atlas` brings it back" in result.stdout


def test_a_feature_the_record_gives_no_branch_name_is_a_finding_not_silence(
        atlas, home):
    """Copilot on #22: `record_rows` dropped a `- branch:` whose value is
    empty, and its legs with it, so the feature vanished from this layer —
    while `workspace_load_project` makes a feature of every `- branch:` line
    and `resume.sh` refuses the one named nothing: with legs, at RR2 with the
    name blank ("Error:  is no longer on origin in the repo leg", exit 2);
    with none, as a shape mismatch. Both run against the extension on
    2026-09-12. One line on the root's row, RR2's two exits, and no per-leg
    line for a feature whose legs have no branch to be found by."""
    checkout = workspace_config(home)
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon")
    text = path.read_text(encoding="utf-8")
    assert text.count("      - branch: 001-a-thing\n") == 1
    for spelling in ("      - branch:\n", "      - branch: # a note\n"):
        path.write_text(text.replace("      - branch: 001-a-thing\n", spelling),
                        encoding="utf-8")
        result = run(STATUS, "Atlas", home=home)
        assert result.returncode == 1, result.stdout + result.stderr
        assert ("    - parked feature with no branch name: a `- branch:` in the "
                "record has no value; `resume` reads it as a feature named "
                "nothing and refuses it as a branch origin has not got (\"is no "
                "longer on origin\", the name blank), so nothing here brings it "
                "back — if that feature landed, remove its `- branch:` block "
                "from atlas.yaml; if it was parked, park it again from the "
                "workstation that has it (the record says Falcon), which writes "
                "the branch it parks") in result.stdout, spelling
        assert "(repo leg)" not in result.stdout, spelling
        assert "`resume Atlas`" not in result.stdout, spelling
        assert "parked record: 1 feature(s)" in result.stdout, spelling

    # And with no legs under it, the refusal `resume` makes is the shape one.
    legless = text.replace("      - branch: 001-a-thing\n", "      - branch:\n")
    legless = legless[:legless.index("        legs:\n") + len("        legs:\n")]
    path.write_text(legless, encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature with no branch name: a `- branch:` in the "
            "record has no value and lists no leg; `resume` reads it as a "
            "feature named nothing and refuses it whole as a shape mismatch "
            "before it reads a leg, so nothing here brings it back — if that "
            "feature landed, remove its `- branch:` block from atlas.yaml; if "
            "it was parked, park it again from the workstation that has it "
            "(the record says Falcon), which writes the branch it parks"
            ) in result.stdout
    assert "lists no leg for it" not in result.stdout, (
        "the named-feature no-legs line, for a feature with no name")


def test_the_help_carries_the_no_push_exception_its_findings_do(home):
    """`status --help` is the other place this rule is stated, and a help
    text that sends somebody to `resume` for a record `resume` refuses is the
    same contradiction the two findings had. Read with the wrapping
    normalised, so the paragraph can be re-wrapped and not the sentence.

    It carries BOTH records `resume` refuses since the second independent
    review of #18, 2026-09-11, note (d): `--no-push`, and a `pushed:` that is
    neither true nor false, which `resume.sh`'s `[ "$pushed" != true ]`
    refuses in exactly the same breath. The independent review of #19 that
    day added the third, and it is the same clause rather than a sentence of
    its own: a `pushed:` that is MISSING is refused by that same test — the
    extension's loader, before workBenches #60, seeded an absent one with `false`, and since #60 refuses it for being absent — and settled by the
    same re-park, so splitting it out would be two sentences saying one
    thing.

    Note 7 of the independent review of #20, the same day, adds the fourth,
    and it is NOT that same clause: a record that names no `parked_commit:`
    for the leg is refused by a different test — RR1, origin's tip against a
    parked commit that is absent and so never matches — and "which `resume`
    refuses the same way" would be a claim about the extension that is not
    true. Its own half-sentence, and the same re-park at the end of both.

    Note 8 of that review adds the fifth, and it is a half-sentence of its
    own for the same reason: a leg the record gives NO ROLE is refused by
    `collect_legs`, which takes the WHOLE FEATURE with it, so neither "the
    same way" nor "as moved-on" describes it. The list beside the paragraph
    names it too, as a finding on the root's row.

    The independent review of #21, the same day, widens that fifth rather
    than adding a sixth: a role THIS CHECKOUT'S SHAPE DOES NOT MOUNT is
    refused by the same `collect_legs`, for the same whole feature, in the
    same "shape mismatch" words. What it adds is the second exit, because
    the two are not one — a misspelt role is a record to write afresh, and a
    role that is really another shape's is a record that is right about a
    checkout this is not.

    Note 1 of that review is the sixth, and the first that is not a leg's at
    all: a FEATURE the record lists no leg for, refused whole by the same
    `collect_legs` at its closing `[ "${#LEG_ROLES[@]}" -gt 0 ]`. It goes in
    the same exception because the same re-park settles it, and in the list
    as a feature rather than a leg, because that is where the finding
    prints.

    The follow-up's own note WIDENS the fifth again rather than adding to the
    list: a role this checkout's shape has no place for is not only one it
    does not mount — `assembly`, and any role only the OTHER shape maps, are
    roles this root can hand a repository for and `collect_legs` refuses
    anyway — and the exits are three, not two, because a role of NEITHER
    shape is a record no checkout of any shape resumes.

    The seventh is that review's note on a BRANCH GONE FROM ORIGIN, and it is
    the first exception whose exits are NOT the re-park: `resume` refuses
    such a record at RR2, and what answers it is the record's own entry where
    the feature landed or a push of the branch from the workstation that
    parked it. It carries the flag with it, because the two readings of a
    missing `origin/<branch>` are only settled by `--fetch` — without one the
    line still names `resume`, which is what brings back the branch this
    clone has merely not fetched yet.

    AND THE SEVENTH SAYS "THE WHOLE FEATURE" SINCE THE INDEPENDENT REVIEW OF
    THIS BRANCH, 2026-09-12: RR2 is `refused=true; break`, which throws the
    feature out with every other leg of it, and the findings said so while
    this paragraph did not. It is the same widening the fifth got, and the
    line is pinned here because a help text that describes a narrower refusal
    than the code makes is the drift these tests exist to catch.

    AND IT SETTLES ON A FETCH THAT WORKED THERE, NOT ON THE FLAG, which is
    Copilot's FOURTH round on #23 (2026-09-13), verbatim: "This help text
    says that `--fetch` settles a missing `origin/<branch>` unconditionally,
    but the implementation distinguishes failed, no-remote, unreadable, and
    unlisted repositories and leaves those readings unresolved. Qualify this
    with a successful fetch that actually reached the repository, otherwise
    the help contradicts the row-level guidance." IT IS RIGHT, and it is this
    branch's own rule turned on its help: the gone verdict is made under
    `fetched_ok_at` and nowhere else, and the four states the two rounds
    before it named — a fetch that FAILED there, no `origin` remote, a
    repository git cannot read, and a path this run's fetch never listed —
    are every one of them a run made WITH the flag that settles nothing. So
    the clause names the fetch that settles it rather than the flag that asks
    for it, and "without one" covers those four exactly as it already covered
    a run made without the flag. THE SAME ROUND'S OTHER TWO ARE NOT THIS:
    AGENTS.md rule 4's "only `status --fetch` settles that" and the README's
    "which only `--fetch` settles" are claims of EXCLUSIVITY — that nothing
    else settles it — which is true of every one of those four states and
    stays as it is.

    AND IT NAMES THE THREE STATES THAT GET NO MOVE, since Copilot's FOURTH
    round on #27 (2026-09-13, suppressed), verbatim: "This help text overstates
    the recovery for an off-path worktree: it says the exit is always `git
    worktree move`, but `off_path_exit` intentionally emits no move for a
    declared `path: "."` and for a symlink-spelled worktree root because that
    move does not produce a path `resume` can register." IT IS RIGHT, and it is
    drift this branch made in the two rounds that suppressed those commands:
    the code stopped promising a move and these three texts went on promising
    one. The leg's own checkout was already named; the other two are named
    beside it now, here, in AGENTS.md rule 4 and in the README, because the
    three say the same things or one of them is wrong.

    AND THE LIST NAMES ALL THREE SOURCES OF THAT PATH SINCE COPILOT'S FIRST
    ROUND ON #27 (2026-09-13, suppressed), verbatim: "This contract documents
    only the environment override and `git-config.yml`, but the implementation
    also falls back to the shape default (`worktrees` for a three-leg root or
    `../<root>-worktrees` for a single root). For an estate without either
    override, readers cannot derive the path that `resume` and the recovery
    guidance use; include that third source in this statement and its mirrored
    help/README wording." IT IS RIGHT, AND THE DEFAULT IS THE COMMON CASE:
    these fixtures carry no `git-config.yml` at all, so every path in every
    finding this file pins comes from the shape, and a reader told only about
    the two overrides is told about the two spellings an estate usually does
    not have. It is the same fault as the should-fix that put
    `$SPECKIT_GIT_WORKTREE_ROOT` here — a list that reads as exhaustive and is
    not — so AGENTS.md rule 4, the README and this clause all take the third
    source.

    The eighth is the independent reviewer's note of 2026-09-12 on the PATH,
    and it goes in the LIST and not in the exception: nothing is being
    brought back for a worktree that is already here, and the exit is neither
    a `resume` nor a re-park but a `git worktree move` to the path both verbs
    compute. The list says which path that is, because a reader who is not
    told it is computed HERE — from this checkout's `git-config.yml`, or the
    environment, or the shape's own default — reaches for the record's own
    `worktree_root:`, which is the one thing neither verb reads.

    The ninth is that reviewer's second and third notes of 2026-09-12, and
    they are ONE clause rather than two: `resume.sh` words RR3 and RR4's
    second arm identically — "'…' exists and is not a registered worktree of
    the <role> leg … Move it aside" — and the only thing that differs is
    WHAT GIT HOLDS at the obstructed path, which is the only thing the exit
    turns on. The `unlock` and the `prune` ride in that same clause because
    neither command clears the path without them: `git worktree move` refuses
    a locked worktree ("cannot move a locked working tree") and `git worktree
    add` refuses a path a dead registration still names ("a missing but
    already registered worktree"), both run against git 2.43 the same day.
    It goes in the EXCEPTION and not in the list beside it, unlike the
    eighth: this IS a record `resume <Name>` brings back, once the path is
    clear, and the sentence it falsifies is the promise itself."""
    result = run(STATUS, "--help", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    helptext = " ".join(result.stdout.split())
    assert ("a recorded feature with no worktree here (`resume <Name>` brings "
            "it back — unless the record says `--no-push`, or its `pushed:` "
            "is missing or neither true nor false, which `resume` refuses the "
            "same way, or it names no parked commit for that leg, which "
            "`resume` refuses as moved-on, or it gives a leg no role at "
            "all, or a role this checkout's shape has no place for — one it "
            "does not mount, or one `resume` maps only onto the other shape, "
            "or onto neither, as it maps `assembly` — or lists "
            "no leg for it at all, which "
            "`resume` refuses the whole feature for: then only the "
            "workstation that parked it can park it again — and where the "
            "role is really another shape's, only a checkout of that shape, "
            "and where it is neither shape's, no checkout at all; "
            "and unless origin has lost the branch, which `resume` refuses "
            "as gone from origin, the WHOLE feature with it — after a fetch "
            "that WORKED in that repository, which is the only way "
            "it is settled, a missing `origin/<branch>` is origin's "
            "answer and the exits are the record's own entry where the "
            "feature landed or a push of the branch from the workstation "
            "that parked it, and without one it is named beside the `resume` "
            "that still brings back a branch this clone has merely not "
            "fetched; and where `git worktree list` still "
            "holds a registration that is no longer a worktree, that is "
            "cleared with `worktree prune`, after a `worktree unlock` if it "
            "is locked and with any leftover directory moved aside, before "
            "`resume` can recreate anything; and where ANYTHING ELSE is at "
            "the path both verbs compute for that leg — a directory, a file, "
            "a worktree of another branch — `resume` refuses the WHOLE "
            "feature rather than overwrite a path it did not create, and "
            "moving that aside first is yours: a `git worktree move` where "
            "git holds it as a worktree and a plain `mv` where it does not, "
            "with the `worktree unlock` a LOCKED registration wants in front "
            "of either and the `worktree prune` a dead one wants beside the "
            "`mv`)") in helptext
    # And the LIST of findings beside it names the new one, as the README's
    # does: the two texts say the same things or one of them is wrong.
    assert ("a worktree whose tip is not the parked commit or a record that "
            "names no parked commit to compare it with, a recorded branch "
            "this repository has no `origin/<branch>` for, a leg parked with "
            "`--no-push` or whose `pushed:` is missing or neither true nor "
            "false, a leg the record gives no role or a role this shape has "
            "no place for, a feature the record lists no leg for, a worktree "
            "on a recorded branch that is not at the path BOTH VERBS compute "
            "for that leg — <worktree_root>/<branch>, with the leg's own "
            "mount under it in a three-leg root, out of "
            "$SPECKIT_GIT_WORKTREE_ROOT, else this checkout's git-config.yml, "
            "else the shape's own default, and not out of the record — which "
            "is the only "
            "worktree `resume` reads as that feature's and the only one "
            "`park` carries, so the exit is a `git worktree move` of yours "
            "— except where no move works and the line says so: the leg's own "
            "checkout, a leg declared `path: \".\"`, and a `worktree_root` "
            "spelled through a symlink — anything at that same path that is "
            "not that leg's "
            "worktree, which `resume` refuses the whole feature for before "
            "it reads origin, and a "
            "worktree the record does not know (never parked)") in helptext


def test_a_missing_parked_commit_is_read_against_what_the_record_claims(
        atlas, home):
    """`pushed: true` RULES OUT `--no-push`, so what is left is a fetch this
    repository never made or a commit origin no longer has; `pushed: false` is
    the other case, already a finding of its own, and here only says where the
    commit is. The first draft offered both reasons under either record."""
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here — the record says it was pushed, so "
            "this repository has never fetched it, or origin no longer has it"
            ) in result.stdout
    assert "--no-push" not in result.stdout

    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed="false", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here, which is what --no-push means — "
            "Falcon is the only place it is") in result.stdout
    assert "never fetched" not in result.stdout


def test_a_missing_parked_commit_under_an_unreadable_pushed_rules_nothing_out(
        atlas, home):
    """The line the second independent review of #18 named on 2026-09-11, note
    (d): with `pushed:` valueless the arm below fired and said "the record
    says it was pushed" — a claim the record does not make, and the one
    reading that rules out the commit never having left that workstation. A
    `pushed:` that rules nothing out rules nothing out in the line: every
    reason still standing is named, and the VALUE is named too, because a
    reader who is told the record cannot be read can go and look at it."""
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed="", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here, and its `pushed:` has no value, "
            "which is neither true nor false — so no reason is ruled out: it "
            "may never have left Falcon, or this repository has never fetched "
            "it, or origin no longer has it") in result.stdout
    assert "the record says it was pushed" not in result.stdout
    assert "--no-push" not in result.stdout, (
        "the other reading, and just as much a guess")

    # A value that is not empty is named as itself, for the same reason.
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed="yes", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here, and its `pushed:` says 'yes', which "
            "is neither true nor false — so no reason is ruled out: it may "
            "never have left Falcon, or this repository has never fetched it, "
            "or origin no longer has it") in result.stdout
    assert "the record says it was pushed" not in result.stdout


def test_a_full_line_comment_inside_a_leg_does_not_end_the_leg(atlas, home):
    """`workspace_load_project` takes `#` and everything after it off every
    line before it reads one, so a `# note` a hand left at column 0 between
    two of a leg's keys is nothing to the loader, and `resume.sh` reads the
    `pushed: true` below it. Read as a leg-ender here — its first character
    sits shallower than a leg's keys — it closed the leg before its `pushed:`,
    and the leg went out as if the record had none: a false "has no `pushed:`"
    finding, and `resume <Name>`, the exit that works, withheld (the review of
    this follow-up, 2026-09-11)."""
    checkout = workspace_config(home)
    path = record(checkout, "atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, pushed="true", parked_on="Falcon")
    text = path.read_text(encoding="utf-8")
    assert text.count("            pushed: true\n") == 1
    path.write_text(text.replace(
        "            pushed: true\n",
        "# a note a hand left here, at column 0\n            pushed: true\n"),
        encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "`resume Atlas` brings it back" in result.stdout
    assert "has no `pushed:`" not in result.stdout, (
        "a comment line read as the end of the leg")


def test_a_missing_parked_commit_with_no_pushed_key_rules_nothing_out(
        atlas, home):
    """The same arm for the state the independent review of #19 named on
    2026-09-11. A record that says NOTHING about `pushed:` rules out no more
    than one whose value cannot be read, so the line names every reason still
    standing — and until the leg had a row at all, it named none of them,
    because there was no line."""
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed=None, parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here, and the record has no `pushed:` for "
            "that leg — so no reason is ruled out: it may never have left "
            "Falcon, or this repository has never fetched it, or origin no "
            "longer has it") in result.stdout
    assert "the record says it was pushed" not in result.stdout
    assert "--no-push" not in result.stdout, (
        "the other reading, and just as much a guess")


def test_a_parked_commit_still_missing_after_this_runs_fetch_says_so(atlas, home):
    """After a fetch that WORKED in this repository, "never fetched" is ruled
    out, and saying it would contradict the `fetched origin:` line printed a
    moment earlier — `no_origin_branch_finding`'s rule, and this layer's too
    now that every repository is fetched before any row is read."""
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here after this run's fetch — the record "
            "says it was pushed, so origin has not got it either"
            ) in result.stdout
    assert "never fetched it" not in result.stdout


def test_an_unreadable_pushed_after_this_runs_fetch_drops_the_fetch_reason(
        atlas, home):
    """The fetched twin of the unreadable missing-commit arm, and
    `no_origin_branch_finding`'s rule: after a fetch that WORKED in this
    repository, "never fetched it" is ruled out, and saying it would
    contradict the `fetched origin:` line printed a moment earlier. What an
    unreadable `pushed:` leaves standing is the other two, and the line names
    those and no more."""
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed="maybe", parked_on="Falcon")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here after this run's fetch, and its "
            "`pushed:` says 'maybe', which is neither true nor false — so "
            "neither reason is ruled out: it may never have left Falcon, and "
            "origin may not have it either") in result.stdout
    assert "never fetched it" not in result.stdout
    assert "the record says it was pushed" not in result.stdout


def test_no_pushed_key_after_this_runs_fetch_drops_the_fetch_reason(
        atlas, home):
    """The fetched twin of the arm above, and `no_origin_branch_finding`'s
    rule again: after a fetch that WORKED in this repository, "never fetched
    it" is ruled out and saying it would contradict the `fetched origin:`
    line printed a moment earlier. An absent `pushed:` leaves the other two
    standing, and the line names those and no more."""
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           pushed=None, parked_on="Falcon")
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here after this run's fetch, and the record "
            "has no `pushed:` for that leg — so neither reason is ruled out: it "
            "may never have left Falcon, and origin may not have it either"
            ) in result.stdout
    assert "never fetched it" not in result.stdout
    assert "the record says it was pushed" not in result.stdout


def test_under_fetch_the_legs_own_fetch_comes_before_the_record_is_read(
        atlas, home, status_remotes):
    """`--fetch` says it asks origin in EVERY repository FIRST, and then
    reads. The record layer is read on the ROOT's row while the legs are rows
    of their own, so a parked commit that had only ever been pushed to the
    SPEC LEG's origin was read as "not here" by the very run that fetched it
    a moment later — a finding that vanished on a second run. With every
    fetch made before any row is read, what is left is the true one: this
    worktree is behind a record that is newer."""
    checkout = workspace_config(home)
    leg = atlas / "spec"
    git("checkout", "-q", "main", cwd=leg)
    feature_worktree(leg, "001-s-thing", home / "Atlas-wt" / "001-s-thing" / "spec")
    # The parked commit: made and pushed to the LEG's origin from another
    # workstation, so nothing here knows it until this run's fetch.
    other = status_remotes["base"] / "elsewhere-spec"
    git("clone", "-q", str(status_remotes["Atlas"]["leg_bare"]), str(other),
        cwd=status_remotes["base"])
    git("checkout", "-q", "001-s-thing", cwd=other)
    (other / "more.md").write_text("parked over there\n", encoding="utf-8")
    commit_all(other, "parked from the other workstation")
    parked = git("rev-parse", "HEAD", cwd=other).stdout.strip()
    git("push", "-q", "origin", "001-s-thing", cwd=other)
    rmtree(other)
    record(checkout, "atlas", branch="001-s-thing", role="spec", commit=parked)

    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "is not here" not in result.stdout, "read before its own fetch"
    assert (f"    - parked feature 001-s-thing (spec leg): this worktree is "
            f"BEHIND the parked commit {parked[:7]}") in result.stdout


def test_two_spellings_of_one_leg_are_one_repository_in_the_fetch_store(
        atlas, home):
    """`estate_repos` builds a leg's path out of `.gitmodules` and the record
    layer asks about the path `project.yaml` gives that role: `./spec` and
    `spec` are one leg and two strings. Keyed on the spelling, the store
    missed and the finding told the person this repository had never fetched
    a leg the same run had fetched two rows below."""
    checkout = workspace_config(home)
    manifest = atlas / "project.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "    path: spec\n", "    path: ./spec\n"), encoding="utf-8")
    leg = atlas / "spec"
    git("checkout", "-q", "main", cwd=leg)
    feature_worktree(leg, "001-s-thing", home / "Atlas-wt" / "001-s-thing" / "spec")
    record(checkout, "atlas", branch="001-s-thing", role="spec", commit=FAKE_SHA)
    result = run(STATUS, "--fetch", "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-s-thing (spec leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here after this run's fetch"
            ) in result.stdout
    assert "never fetched it" not in result.stdout


def test_a_worktree_the_record_does_not_know_was_never_parked(atlas, home):
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    feature_worktree(atlas, "002-unparked", home / "Atlas-wt" / "002-unparked")
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - worktree on 002-unparked (root): not in the parked record — "
            "never parked; `park` carries the features under this root's "
            "worktree root, anything else is yours to keep or remove"
            ) in result.stdout
    assert "worktree on 001-a-thing" not in result.stdout


def test_a_deleted_worktrees_stale_entry_is_not_an_unparked_worktree(atlas, home):
    """The other half of the porcelain's stale block: telling somebody that a
    directory which is not there was never parked is a finding about nothing,
    and `park` would carry nothing when they ran it."""
    checkout = workspace_config(home)
    tip = feature_worktree(atlas, "001-a-thing",
                           parked_worktree(atlas, "001-a-thing"))
    gone = home / "Atlas-wt" / "002-unparked"
    feature_worktree(atlas, "002-unparked", gone)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=tip)
    rmtree(gone)            # and NO `git worktree prune`
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "002-unparked" not in result.stdout


def test_a_spec_leg_is_read_in_the_legs_own_repository(atlas, home):
    """The role is mapped to a path through `project.yaml`'s legs, so the
    worktree is looked for in `spec/`, not in the root.

    THE SECOND HALF IS WHAT PROVES IT NOW: this root is `single`, so the
    shape reading refuses a `spec` leg here before any of it — that line is
    the same whether or not a worktree was found — and only the arms AFTER it
    say where the layer looked. "its parked commit … is not here" is one of
    those: it is printed for a leg whose worktree WAS found, and it is
    printed here, in the leg's own repository."""
    checkout = workspace_config(home)
    leg = atlas / "spec"
    git("checkout", "-q", "main", cwd=leg)
    tip = feature_worktree(leg, "001-s-thing", home / "Atlas-wt" / "001-s-thing" / "spec")
    record(checkout, "atlas", branch="001-s-thing", role="spec", commit=tip)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == ["- parked feature 001-s-thing (spec leg): "
                        + SHAPE_SPEC + MISMATCH + EXIT_S + DISAGREE_S], findings

    record(checkout, "atlas", branch="001-s-thing", role="spec", commit=FAKE_SHA)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-s-thing (spec leg): its parked commit "
            f"{FAKE_SHA[:7]} is not here — the record says it was pushed, so "
            "this repository has never fetched it, or origin no longer has it"
            ) in result.stdout


def test_two_orgs_recording_the_same_id_is_a_note(atlas, home):
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a", role="repo", commit=FAKE_SHA)
    record(checkout, "atlas", branch="001-a", role="repo", commit=FAKE_SHA,
           org="otherorg")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("  parked record: 2 records for 'atlas' in different orgs, and none "
            "is the org this root's origin names; not read") in result.stdout


def test_the_state_a_resume_leaves_is_not_behind(atlas, home):
    """`park` commits the WIP under `wip: park …` and records its depth;
    `resume` recreates the worktree at the parked commit and soft-resets
    exactly those commits away. That tip — `<parked>~<wip_depth>`, with the
    work back in the tree — is the state every resumed machine is in, and
    `resume.sh`'s `wip_gap_is_ours` is why it does not refuse it. So neither
    does this: the first draft called it BEHIND, forever, on every run."""
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    feature_worktree(atlas, "001-a-thing", where)
    (where / "half-done.md").write_text("half done\n", encoding="utf-8")
    git("add", "-A", cwd=where)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm",
        "wip: park 2026-09-10T20:00:00Z — lane xfactory-2", cwd=where)
    git("push", "-q", "origin", "001-a-thing", cwd=where)
    parked = git("rev-parse", "HEAD", cwd=where).stdout.strip()
    git("reset", "-q", "--soft", "HEAD~1", cwd=where)   # what resume.sh does
    git("reset", "-q", cwd=where)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=parked,
           wip_depth=1)
    result = run(STATUS, "Atlas", home=home)
    assert "BEHIND" not in result.stdout, result.stdout
    assert "parked feature" not in result.stdout, result.stdout
    assert result.returncode == 1, "the un-committed WIP is a dirty worktree, and read as one"
    assert "on 001-a-thing: dirty, 1 path(s)" in result.stdout

    # The same gap with a commit that is NOT the parked WIP is genuinely behind.
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=parked,
           wip_depth=0)
    result = run(STATUS, "Atlas", home=home)
    assert "this worktree is BEHIND the parked commit" in result.stdout


def test_an_absent_optional_key_does_not_shift_the_fields(atlas, home):
    """`park.sh` writes no key for an empty value. A leg with no
    `parked_commit:` and `pushed: false` must still report the --no-push
    finding, not a parked commit called `false`."""
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit="",
           pushed="false", parked_on="Falcon")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature 001-a-thing (repo leg): parked with --no-push "
            "on Falcon") in result.stdout
    assert "parked commit false" not in result.stdout


def test_a_diverged_worktree_names_the_log_to_read(atlas, home):
    checkout = workspace_config(home)
    where = parked_worktree(atlas, "001-a-thing")
    base = feature_worktree(atlas, "001-a-thing", where)
    (where / "theirs.md").write_text("theirs\n", encoding="utf-8")
    commit_all(where, "parked elsewhere")
    git("push", "-q", "origin", "001-a-thing", cwd=where)
    theirs = git("rev-parse", "HEAD", cwd=where).stdout.strip()
    git("reset", "-q", "--hard", base, cwd=where)
    (where / "mine.md").write_text("mine\n", encoding="utf-8")
    commit_all(where, "mine")
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=theirs)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"    - parked feature 001-a-thing (repo leg): diverged from the "
            f"parked commit {theirs[:7]}, parked 2026-09-10T20:00:00Z on Eagle "
            f"— reconcile by hand: `git -C {atlas} log --oneline {theirs[:7]}"
            "..001-a-thing`") in result.stdout


def test_a_root_the_record_does_not_mention_still_has_its_worktrees_swept(
        atlas, home):
    checkout = workspace_config(home)
    feature_worktree(atlas, "001-a-thing",
                     parked_worktree(atlas, "001-a-thing"))
    record(checkout, "atlas", branch="001-x", role="repo", commit=FAKE_SHA)
    # the file is atlas.yaml, but its one block is somebody else's — by id
    # AND by root, since a block whose `root:` is this folder is this root's
    path = checkout / "workspaces" / ORG / "atlas.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "  - id: atlas\n", "  - id: somethingelse\n").replace(
        "    root: Atlas\n", "    root: Somethingelse\n"), encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    parked record: no block for this root in atlas.yaml" in result.stdout
    assert ("    - worktree on 001-a-thing (root): not in the parked record"
            in result.stdout)


def test_an_unparked_worktree_in_a_leg_is_named_with_the_leg(atlas, home):
    checkout = workspace_config(home)
    leg = atlas / "spec"
    git("checkout", "-q", "main", cwd=leg)
    feature_worktree(leg, "001-s-thing", home / "Atlas-wt" / "001-s-thing" / "spec")
    record(checkout, "atlas", branch="001-other", role="repo", commit=FAKE_SHA)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "    - worktree on 001-s-thing (spec): not in the parked record" in result.stdout


def test_two_orgs_are_settled_by_the_origins_owner(atlas, home, status_remotes):
    github_origin(atlas, status_remotes["Atlas"]["bare"], "testorg/Atlas")
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a", role="repo", commit=FAKE_SHA)
    record(checkout, "atlas", branch="001-a", role="repo", commit=FAKE_SHA,
           org="otherorg", parked_on="Nowhere")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"  parked record: {checkout}/workspaces/{ORG}/atlas.yaml" in result.stdout
    assert "on Eagle" in result.stdout and "Nowhere" not in result.stdout


def test_an_override_pointing_at_the_same_checkout_is_one_checkout(atlas, home):
    """An `orgs:` override whose `path:` is the default's clone is one clone,
    not two orgs recording the same id — `resume` dedupes by physical path
    (F4 of the review on openRepoShape #83), and so does this."""
    checkout = workspace_config(home)
    (home / ".agents" / "workspace.yaml").write_text(
        f"repository: tester/wip\npath: {checkout}\norgs:\n  {ORG}:\n"
        f"    repository: tester/wip\n    path: {checkout}/\n", encoding="utf-8")
    record(checkout, "atlas", branch="001-a", role="repo", commit=FAKE_SHA)
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "2 records for 'atlas'" not in result.stdout
    assert f"  parked record: {checkout}/workspaces/{ORG}/atlas.yaml" in result.stdout


def test_two_checkouts_of_one_workspace_repository_are_one_record(atlas, home):
    """Two CLONES of one workspace repository — the default `path:` and an
    `orgs:` override that is a second checkout of it — hold the same
    `<org>/<id>.yaml`. `resume` counts that as ONE record, by org and
    basename (F4 of the review on openRepoShape #83), because `--org` could
    not have told the two apart. Counted as two it read as "two orgs record
    this id", and a local-path origin names no owner to settle it with, so a
    record that was never ambiguous was skipped unread."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA)
    other = home / "wip-2"
    shutil.copytree(checkout, other)
    (home / ".agents" / "workspace.yaml").write_text(
        f"repository: tester/wip\npath: {checkout}\norgs:\n  {ORG}:\n"
        f"    repository: tester/wip\n    path: {other}\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "2 records for 'atlas'" not in result.stdout
    assert f"  parked record: {checkout}/workspaces/{ORG}/atlas.yaml" in result.stdout
    assert "no worktree on that branch here" in result.stdout


def test_two_checkouts_that_spell_the_record_differently_are_one_record(
        atlas, home):
    """The basename is MATCHED case-insensitively — `park` files under the id
    and `resume <Name>` looks up the folder — so the key that decides whether
    two rows are two records folds it the same way, as it already folds the
    org. `atlas.yaml` in one checkout and `Atlas.yaml` in another are one
    record of one org; keyed on the raw basename they were two, and a record
    of one org was reported as two orgs' and skipped."""
    checkout = workspace_config(home)
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA)
    other = home / "wip-2"
    shutil.copytree(checkout, other)
    (other / "workspaces" / ORG / "atlas.yaml").rename(
        other / "workspaces" / ORG / "Atlas.yaml")
    (home / ".agents" / "workspace.yaml").write_text(
        f"repository: tester/wip\npath: {checkout}\norgs:\n  {ORG}:\n"
        f"    repository: tester/wip\n    path: {other}\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "2 records for 'atlas'" not in result.stdout
    assert f"  parked record: {checkout}/workspaces/{ORG}/atlas.yaml" in result.stdout
    assert "no worktree on that branch here" in result.stdout


def test_a_checkout_not_on_this_machine_is_said(atlas, home):
    (home / ".agents").mkdir(exist_ok=True)
    (home / ".agents" / "workspace.yaml").write_text(
        f"repository: tester/wip\npath: {home}/not-cloned-yet\n", encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (f"  parked record: the workspace checkout {home}/.agents/workspace.yaml "
            f"names is not on this machine ({home}/not-cloned-yet), so parked "
            "features are not read (`resume` clones it)") in result.stdout


def test_a_record_filed_under_the_folder_name_is_found_too(atlas, home):
    """`park` files under the id; `resume <Name>` looks up the folder. Where an
    `id:` is not the folder's own name, both are tried."""
    checkout = workspace_config(home)
    manifest = atlas / "project.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "id: atlas\n", "id: atlas-core\n"), encoding="utf-8")
    record(checkout, "Atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA,
           root="Atlas")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"  parked record: {checkout}/workspaces/{ORG}/Atlas.yaml" in result.stdout
    assert "no worktree on that branch here" in result.stdout


def folder_matched_record(atlas: Path, checkout: Path) -> Path:
    """A record whose block is reached by its `root:` and not by its `id:` —
    the selector a FAMILY member is matched by, and the one a record filed
    under the folder name carries. The project's `id:` is made its own so the
    `id=` selector finds nothing and `root=Atlas` is what selects the block."""
    manifest = atlas / "project.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "id: atlas\n", "id: atlas-core\n"), encoding="utf-8")
    return record(checkout, "Atlas", branch="001-a-thing", role="repo",
                  commit=FAKE_SHA, parked_on="Falcon", root="Atlas")


def test_a_root_key_below_the_features_still_selects_the_whole_block(
        atlas, home):
    """Copilot's second round on #22: `record_rows` decides whether a row goes
    out AT the line it reads it from, and a block selected by `root=` is not
    known to be the selected one until its `root:` line — which
    `workspace_write_manifest` writes above `features:` and a hand-edit or a
    bad merge can move below it. Every row above that line was then dropped:
    the `project` row, each feature's `branch` row and every leg that ended
    before it, which for the layout `park` writes is the WHOLE BLOCK — so this
    layer said "no block for this root" about a record it had just found and
    matched, while `workspace_load_project` matches at the `- id:` line and
    reads the keys of a block by their indent, in any order."""
    checkout = workspace_config(home)
    path = folder_matched_record(atlas, checkout)
    text = path.read_text(encoding="utf-8")
    assert text.count("    root: Atlas\n") == 1
    path.write_text(text.replace("    root: Atlas\n", "") + "    root: Atlas\n",
                    encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "parked record: no block for this root" not in result.stdout, (
        "the block was matched at its `root:` and read from there on")
    assert ("    - parked feature 001-a-thing (repo leg): no worktree on that "
            "branch here; parked 2026-09-10T20:00:00Z on Falcon — `resume "
            "Atlas` brings it back") in result.stdout
    assert ("    parked record: 1 feature(s), parked 2026-09-10T20:00:00Z on "
            "Falcon (lane xfactory-2); active 001-a-thing") in result.stdout
    assert "lists no leg for it" not in result.stdout, (
        "the branch row kept and its leg dropped is a feature with no legs")


def test_a_project_key_below_the_features_is_read_as_the_loader_reads_it(
        atlas, home):
    """Copilot's first round on #23, verbatim: "the project row is serialized
    when `features:` is encountered, but `workspace_load_project` accepts the
    other project-level keys at the same indent in any order. If a
    hand-edited or merged manifest places `shape:` after the feature list,
    this assignment updates the local variable after the `project` row has
    already been buffered, so `RECORD_SHAPE` remains empty and the new
    shape-disagreement diagnostic is silently omitted even though `resume`
    reads the field."

    AND IT HOLDS FOR ALL FIVE OF THEM. The loader's indent-4 arm is one
    `case` over `shape`, `root`, `parked_at`, `parked_on`, `parked_by_lane`,
    `active_feature` and the rest, reached by INDENT and not by position: run
    against the extension on 2026-09-12 on this record, `workspace_load_project`
    returned `MANIFEST_SHAPE=three-leg`, `MANIFEST_PARKED_AT=2026-09-10T20:00:00Z`,
    `MANIFEST_PARKED_ON=Falcon`, the lane and the active feature, with the
    feature and its leg intact. Read here at the `features:` line, every one
    of them was empty: the root's note line said "parked ? on ?", the finding
    lost the clause that holds the record's `shape:` against this checkout,
    and its exit said "the record does not say where" about a record that
    says Falcon. The row is built at the flush now, from what the whole block
    left behind."""
    checkout = workspace_config(home)
    keys = ("    shape: three-leg\n",
            "    parked_at: 2026-09-10T20:00:00Z\n",
            "    parked_on: Falcon\n",
            "    parked_by_lane: xfactory-2\n",
            "    active_feature: 001-a-thing\n")
    path = record(checkout, "atlas", branch="001-a-thing", role="assembly",
                  commit=FAKE_SHA, parked_on="Falcon")
    text = path.read_text(encoding="utf-8")
    for key in keys:
        assert text.count(key) == 1, key
        text = text.replace(key, "")
    path.write_text(text + "".join(keys), encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    parked record: 1 feature(s), parked 2026-09-10T20:00:00Z on "
            "Falcon (lane xfactory-2); active 001-a-thing") in result.stdout
    findings = [line.strip() for line in result.stdout.splitlines()
                if line.strip().startswith("- parked feature")]
    assert findings == [ASSEMBLY + EXIT_NEITHER + DISAGREE], findings


def test_a_blank_branch_above_the_root_key_is_still_the_feature_resume_refuses(
        atlas, home):
    """Copilot's second round on #22, its own scenario: with the `root:` key
    between an empty `- branch:` and that feature's legs, the branch row was
    suppressed — `matched` was still false at the branch — and the leg row was
    not, so it reached `read_record` with no branch row before it, took no
    feature's verdict, and was offered `resume Atlas` under a blank name. The
    loader makes a feature of every `- branch:` line whatever sits above or
    below it, and `resume` refuses the one named nothing at RR2 ("Error:  is
    no longer on origin in the repo leg", exit 2) — so the feature's own line
    is what this record gets, and no leg line under it."""
    checkout = workspace_config(home)
    path = folder_matched_record(atlas, checkout)
    text = path.read_text(encoding="utf-8")
    assert text.count("        legs:\n") == 1
    path.write_text(text.replace("    root: Atlas\n", "")
                    .replace("      - branch: 001-a-thing\n", "      - branch:\n")
                    .replace("        legs:\n", "    root: Atlas\n        legs:\n"),
                    encoding="utf-8")
    result = run(STATUS, "Atlas", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("    - parked feature with no branch name: a `- branch:` in the "
            "record has no value; `resume` reads it as a feature named nothing "
            "and refuses it as a branch origin has not got (\"is no longer on "
            "origin\", the name blank), so nothing here brings it back — if "
            "that feature landed, remove its `- branch:` block from Atlas.yaml; "
            "if it was parked, park it again from the workstation that has it "
            "(the record says Falcon), which writes the branch it parks"
            ) in result.stdout
    assert "(repo leg)" not in result.stdout
    assert "`resume Atlas`" not in result.stdout, (
        "a feature named nothing was offered the command that refuses it")
    assert ("    parked record: 1 feature(s), parked 2026-09-10T20:00:00Z on "
            "Falcon (lane xfactory-2); active 001-a-thing") in result.stdout


def test_the_record_layer_under_all_is_located_per_estate(home, status_remotes):
    """`locate_record` runs once per estate and starts clean: Atlas finds its
    record, Borealis (whose `id:` is made its own) finds none, and neither
    leaks into the other."""
    checkout = workspace_config(home)
    clone_root(home, status_remotes["Atlas"], "Atlas")
    borealis = clone_root(home, status_remotes["Atlas"], "Borealis")
    manifest = borealis / "project.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "id: atlas\n", "id: borealis\n"), encoding="utf-8")
    record(checkout, "atlas", branch="001-a-thing", role="repo", commit=FAKE_SHA)
    result = run(STATUS, "--all", home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.count("`resume Atlas` brings it back") == 1
    assert "`resume Borealis`" not in result.stdout
    assert "  parked record: none for 'borealis' under" in result.stdout


@NEEDS_UPSTREAM
def test_a_family_record_is_matched_to_each_member_by_its_root(estate, home):
    """One block per MEMBER, matched by `root: <family folder>/<member>`; the
    holder has none. The fixture's members mount no spec leg, so the recorded
    spec leg is named as one this root does not mount — which is the match
    working, per member, and the holder row staying silent."""
    checkout = workspace_config(home)
    (checkout / "workspaces" / ORG / f"{FAMILY.lower()}.yaml").write_text(
        family_manifest(), encoding="utf-8")
    result = run(STATUS, FAMILY, home=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"  parked record: {checkout}/workspaces/{ORG}/{FAMILY.lower()}.yaml" \
        in result.stdout
    for name in MEMBERS:
        assert (f"    - parked feature 001-{name.lower()}-thing (spec leg): the "
                "record names a leg this root does not mount here") in result.stdout
    assert result.stdout.count("    parked record: 1 feature(s)") == 2
    holder_block = result.stdout.split("  root   main")[0]
    assert "    parked record:" not in holder_block, "the holder has no block"


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
