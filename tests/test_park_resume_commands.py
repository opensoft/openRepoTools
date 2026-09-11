# SPDX-License-Identifier: Apache-2.0
"""`park` and `resume` — the two installed USER COMMANDS (#82).

They ADD NO MECHANICS, so this file asserts exactly what they do add: finding
the estate, driving the estate's own `make park` / `make resume`, rebuilding or
fast-forwarding the estate before the verb runs, and every refusal. The WIP
commit, the push, the `git worktree add` and the soft reset belong to the
Speckit git extension and are tested in its own suite; `make park` / `make
resume` themselves are tested in `test_park_resume_targets.py`.

OFFLINE, LIKE THE REST OF THIS SUITE, and offline in three ways at once. The
extension script is a STUB that echoes its arguments (the same stub #80's tests
use). Every remote is a BARE REPOSITORY IN A TEMPORARY DIRECTORY, reached
through `$OPENREPOTOOLS_REMOTE_BASE` — `resume`'s documented test path, the
same concession `setup-project.py --local-remote-dir` and `family.py
--local-remote-dir` make. And `$HOME` is a temporary directory too, so the
`~/projects` / `~/Projects` spellings and `~/.agents/workspace.yaml` are the
test's own and never the developer's. Nothing here may create a real
repository, and nothing here reaches the network.

THE WORKSPACE MANIFEST IS WRITTEN BY HAND, at `schema_version: 1` — the schema
`opensoft/workBenches`'s `park.sh` writes as of its S1 (merged 2026-09-09).
Written out rather than generated, because a test that needed a workBenches
checkout beside this one would skip on every machine that has only this
repository, which is every fork.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import NEEDS_UPSTREAM, REPO, UPSTREAM, WINDOWS_SKIP, git, rmtree

PARK = REPO / "park"
RESUME = REPO / "resume"
STATUS = REPO / "status"
MAKE = shutil.which("make")

#: Both reasons this whole file needs a POSIX machine: the commands are bash,
#: and they run `make` in a root that execs a `#!`-shebang script.
pytestmark = [
    NEEDS_UPSTREAM,
    WINDOWS_SKIP,
    pytest.mark.skipif(shutil.which("bash") is None,
                       reason="park and resume are bash scripts"),
    pytest.mark.skipif(MAKE is None, reason="needs `make` on PATH"),
]

#: Where `setup-openspeckit` installs the extension's bash scripts, and so
#: where a stub has to live to be found by the `park` / `resume` targets.
OVERLAY = Path(".specify/extensions/git/scripts/bash")

#: `git` reads one-off configuration out of the environment, which is how a
#: test gives a plain `git clone`/`git submodule update` permission to clone a
#: local path without the tool under test knowing anything about it. `resume`
#: deliberately grants no such permission of its own. Copied from
#: `test_family.py`, for its reasons.
ALLOW_FILE_PROTOCOL = {"GIT_CONFIG_COUNT": "1",
                       "GIT_CONFIG_KEY_0": "protocol.file.allow",
                       "GIT_CONFIG_VALUE_0": "always"}

ORG = "testorg"
FAMILY = "TestFam"
MEMBERS = ("Alpha", "Bravo")
WORKSPACE_SLUG = "tester/wip"

#: A `parked_commit` has to be a 40-hex sha to be the schema's own shape. It
#: never has to RESOLVE here: nothing in this repository reads it — the
#: extension's `resume.sh` does, and it is stubbed.
FAKE_SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"

#: A Makefile whose two verbs only SAY WHERE THEY RAN. Estate resolution is
#: what most of this file is about, and a probe that names its own directory
#: proves the answer in one line — where a real root would prove it through
#: three layers of somebody else's code.
PROBE_MAKEFILE = """\
.PHONY: park resume bootstrap siblings
park:
\t@echo "PROBE park in $(CURDIR) ARGS=[$(ARGS)]"
resume:
\t@echo "PROBE resume in $(CURDIR) ARGS=[$(ARGS)]"
bootstrap:
\t@echo "PROBE bootstrap in $(CURDIR)"
siblings:
\t@echo "PROBE siblings in $(CURDIR)"
"""

#: The same probe, except `park` exits 3 after printing — #91's
#: park-everything has to be shown continuing past ONE estate's refusal
#: while still parking the rest, and this is the cheapest way to make one
#: estate's own `make park` fail without a real extension stub.
FAILING_PARK_PROBE_MAKEFILE = """\
.PHONY: park resume bootstrap siblings
park:
\t@echo "PROBE park in $(CURDIR) ARGS=[$(ARGS)]"
\t@exit 3
resume:
\t@echo "PROBE resume in $(CURDIR) ARGS=[$(ARGS)]"
bootstrap:
\t@echo "PROBE bootstrap in $(CURDIR)"
siblings:
\t@echo "PROBE siblings in $(CURDIR)"
"""

FAMILY_YAML = """\
schema_version: 1
kind: family-manifest
id: {id}
name: "{name}"
org: {org}
repository: {org}/{name}
tracking_branch: main
members_dir: members
members:{members}
"""

PROJECT_YAML = """\
schema_version: 1
kind: project-manifest
id: {id}
name: "{name}"
tracking_branch: main
legs:
  - role: assembly
    repository: {org}/{name}
    path: "."
"""


# --- the environment every run gets ----------------------------------------

def command_env(home: Path, env: dict | None = None) -> dict:
    """A fake `$HOME`, every variable these commands read cleared first.

    Cleared rather than merely defaulted, so a developer's own `$PROJECTS_DIR`
    or `$AGENT_PROTOCOL_ROOT` cannot change what these tests assert.
    `PYTHON=<this interpreter>` because the Makefiles say `PYTHON ?= python3`
    and `?=` honours the environment: the suite must exercise the interpreter
    it is running under, not whichever `python3` is first on PATH.
    """
    environ = dict(os.environ)
    for name in ("PROJECTS_DIR", "AGENT_PROTOCOL_ROOT",
                 "OPENREPOTOOLS_REMOTE_BASE", "MAKEFLAGS", "MAKELEVEL",
                 "SPECKIT_WORKSPACE_PATH", "SPECKIT_WORKSPACE_REPOSITORY",
                 "SPECKIT_GIT_WORKTREE_ROOT"):
        environ.pop(name, None)
    environ["HOME"] = str(home)
    environ["PYTHON"] = sys.executable
    environ.setdefault("GIT_AUTHOR_NAME", "openRepoShape tests")
    environ.setdefault("GIT_AUTHOR_EMAIL", "tests@openreposhape.invalid")
    environ.setdefault("GIT_COMMITTER_NAME", "openRepoShape tests")
    environ.setdefault("GIT_COMMITTER_EMAIL", "tests@openreposhape.invalid")
    environ.update(env or {})
    return environ


def run(command: Path, *args: str, home: Path, cwd: Path | None = None,
        env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(command), *args], capture_output=True,
                          text=True, check=False, input="",
                          cwd=str(cwd) if cwd else str(home),
                          env=command_env(home, env))


@pytest.fixture
def home(tmp_path) -> Path:
    """A fake home with `projects/` in it — the common spelling."""
    target = tmp_path / "home"
    (target / "projects").mkdir(parents=True)
    return target


# --- estates on disk, with no remote at all ---------------------------------

def write_stub(root: Path, verb: str, code: int = 0, label: str = "") -> Path:
    """An executable stand-in for the extension's `<verb>.sh` (#80's stub)."""
    script = root / OVERLAY / f"{verb}.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        f'#!/bin/sh\necho "{label or verb}.sh ran with: $*"\nexit {code}\n',
        encoding="utf-8")
    script.chmod(0o755)
    return script


def probe_family(projects: Path, name: str) -> Path:
    """A family FOLDER with a holder in it and a probe Makefile. Returns the
    holder, which is where both verbs must run."""
    holder = projects / name / name
    holder.mkdir(parents=True)
    (holder / "family.yaml").write_text(
        FAMILY_YAML.format(id=name.lower(), name=name, org=ORG,
                           members=" []"), encoding="utf-8")
    (holder / "Makefile").write_text(PROBE_MAKEFILE, encoding="utf-8")
    return holder


def probe_project(projects: Path, name: str, *, at: Path | None = None) -> Path:
    """A standalone project root with a probe Makefile."""
    root = at if at is not None else projects / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.yaml").write_text(
        PROJECT_YAML.format(id=name.lower(), name=name, org=ORG),
        encoding="utf-8")
    (root / "Makefile").write_text(PROBE_MAKEFILE, encoding="utf-8")
    return root


def sweepable_project(projects: Path, name: str, *, at: Path | None = None) -> Path:
    """A standalone root THE SWEEP WILL RUN: a probe root plus the overlay.

    Since #6 the no-estate sweep asks a standalone root for the Speckit git
    overlay before running anything in it, the way
    `templates/assembly-root/Makefile` asks — `test -x
    .specify/extensions/git/scripts/bash/park.sh`. The stub is never
    EXECUTED by these tests, because the probe Makefile echoes instead of
    running it; its presence is the whole point, and a `probe_project`
    without it is now a root the sweep skips, which is what
    `probe_project` is left meaning.
    """
    root = probe_project(projects, name, at=at)
    write_stub(root, "park")
    return root


# --- the offline remotes, built once ---------------------------------------

def commit_all(path: Path, message: str) -> None:
    git("add", "-A", cwd=path)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message,
        cwd=path)


def seed_member(base: Path, name: str) -> Path:
    """A bare repository holding one member of the family.

    Everything the flow reads and nothing else: an `origin` to identify it by,
    its own `project.yaml` id and tracking branch, the REAL assembly-root
    Makefile (so `make park` / `make resume` / `make bootstrap` are the shipped
    recipes), a `scripts/bootstrap.py` STUB, and the two overlay stubs. TWO
    commits, so a clone can be reset one back and be genuinely behind.
    """
    seed = base / "seed" / name
    (seed / "scripts").mkdir(parents=True)
    (seed / "project.yaml").write_text(
        PROJECT_YAML.format(id=name.lower(), name=name, org=ORG),
        encoding="utf-8")
    shutil.copy2(UPSTREAM / "templates" / "assembly-root" / "Makefile",
                 seed / "Makefile")
    # THE TEMPLATE'S OWN `.gitignore`, because a root that did not ignore
    # `__pycache__/` would read as a DIRTY ROOT the moment anything ran a
    # script in it - which is a fiction about the project, not about park.
    shutil.copy2(UPSTREAM / "templates" / "assembly-root" / ".gitignore",
                 seed / ".gitignore")
    (seed / "scripts" / "bootstrap.py").write_text(
        "#!/usr/bin/env python3\n"
        f'print("BOOTSTRAP-{name} ran")\n', encoding="utf-8")
    for verb in ("park", "resume"):
        write_stub(seed, verb, label=name)
    git("init", "-q", "-b", "main", ".", cwd=seed)
    commit_all(seed, "seed")
    (seed / "NOTES.md").write_text("the member moved on\n", encoding="utf-8")
    commit_all(seed, "a second commit, so a clone can be behind")
    bare = base / "remotes" / f"{name}.git"
    bare.parent.mkdir(exist_ok=True)
    git("clone", "-q", "--bare", str(seed), str(bare), cwd=base)
    return bare


def seed_holder(base: Path, members: dict) -> Path:
    """A bare repository holding the family HOLDER, with real submodules.

    Built from the template bytes, the way `test_park_resume_targets.py`'s
    fixture is, but with `git submodule add` so a `git clone
    --recurse-submodules` of it produces the pinned `members/<Project>` copies
    the holder's own `make bootstrap` and `make validate` read.
    """
    seed = base / "seed" / FAMILY
    (seed / "scripts").mkdir(parents=True)
    template = UPSTREAM / "templates" / "family-root"
    shutil.copy2(template / "Makefile", seed / "Makefile")
    shutil.copy2(template / ".gitignore", seed / ".gitignore")
    for rel in ("scripts/bootstrap.py", "scripts/siblings.py"):
        shutil.copy2(template / rel, seed / rel)
    shutil.copy2(UPSTREAM / "scripts" / "repo_shape.py",
                 seed / "scripts" / "repo_shape.py")
    rows = ""
    for name in MEMBERS:
        rows += (f"\n  - project: {name}\n"
                 f"    id: {name.lower()}\n"
                 f"    repository: {ORG}/{name}\n"
                 f"    path: members/{name}\n")
    (seed / "family.yaml").write_text(
        FAMILY_YAML.format(id=FAMILY.lower(), name=FAMILY, org=ORG,
                           members=rows), encoding="utf-8")
    git("init", "-q", "-b", "main", ".", cwd=seed)
    commit_all(seed, "seed")
    for name in MEMBERS:
        git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
            str(members[name]), f"members/{name}", cwd=seed)
    commit_all(seed, "the members, pinned")
    (seed / "NOTES.md").write_text("the holder moved on\n", encoding="utf-8")
    commit_all(seed, "a second commit, so a clone can be behind")
    bare = base / "remotes" / f"{FAMILY}.git"
    git("clone", "-q", "--bare", str(seed), str(bare), cwd=base)
    return bare


def family_manifest(family: str = FAMILY) -> str:
    """One workspace manifest as `park.sh` WRITES ONE, by hand.

    THE CASING IS THE POINT, and it is why this is written out rather than
    invented (F2 of the review on #83). `park.sh` takes the header's `family:`
    from `family.yaml`'s **`id:`** — `workspace_family_name` reads that key —
    and an id is LOWERCASE by construction (`family.py`: `--id … or
    family.lower()`, checked against `PROJECT_ID_RE = ^[a-z0-9][a-z0-9-]*$`).
    The manifest FILE is named for the same id. The family FOLDER, and the
    holder repository, are the family's CamelCase `name:` — and the only place
    in the file that carries it is each member's
    `root: <family folder>/<project folder>`, which
    `workspace_manifest_root_value` writes with the real casing.

    So: `family: testfam`, `workspaces/<org>/testfam.yaml`, `root:
    TestFam/Alpha`. A resume that read the folder out of `family:` clones
    `<org>/testfam` into `~/projects/testfam/testfam`, and this fixture is
    what makes that fail here instead of on somebody's workstation.
    """
    blocks = ""
    for name in MEMBERS:
        blocks += f"""\
  - id: {name.lower()}
    repository: {ORG}/{name}
    shape: three-leg
    root: {family}/{name}
    tracking_branch: main
    worktree_root: worktrees
    parked_at: 2026-09-09T18:42:11Z
    parked_on: Eagle
    parked_by_lane: xfactory-2
    active_feature: 001-{name.lower()}-thing
    active_feature_source: state_file
    features:
      - branch: 001-{name.lower()}-thing
        feature_directory: worktrees/001-{name.lower()}-thing/spec/specs/001-{name.lower()}-thing
        legs:
          - role: spec
            remote: origin
            parked_commit: {FAKE_SHA}
            wip: true
            wip_depth: 1
            pushed: true
"""
    return (f"schema_version: 1\nkind: workspace-manifest\n"
            f"family: {family.lower()}\nwritten_by: speckit park\nprojects:\n"
            + blocks)


def standalone_manifest(project: str) -> str:
    """A STANDALONE project's manifest: no `family:` key, so the root
    repository is `projects[0].repository` and the folder is its `root:`.

    Named for the project's `project.yaml` id (`alpha`), which is what the
    extension names it — and not for the folder a person types (`Alpha`),
    which is why the file is matched case-insensitively.
    """
    return f"""schema_version: 1
kind: workspace-manifest
written_by: speckit park
projects:
  - id: {project.lower()}
    repository: {ORG}/{project}
    shape: three-leg
    root: {project}
    tracking_branch: main
    worktree_root: worktrees
    parked_at: 2026-09-09T18:42:11Z
    parked_on: Eagle
    parked_by_lane: xfactory-2
    active_feature: 001-{project.lower()}-thing
    active_feature_source: state_file
    features:
      - branch: 001-{project.lower()}-thing
        legs:
          - role: repo
            remote: origin
            parked_commit: {FAKE_SHA}
            wip: false
            wip_depth: 0
            pushed: true
"""


#: The member for the leg guard: the REAL assembly-root bootstrap, and a real
#: submodule leg. `Charlie` rather than one of MEMBERS because the family
#: fixtures are session-scoped and this one is the only place that wants a leg.
LEG_MEMBER = "Charlie"


def seed_leg_member(base: Path) -> tuple[Path, Path]:
    """A bare project WITH A LEG, carrying the REAL `scripts/bootstrap.py`.

    THE GUARD MUST GUARD THE REAL THING (F3 of the review on #83). The other
    seeded members ship a bootstrap STUB that only echoes, which would let a
    leg-guard test pass against a script that could not have moved anything.
    This one ships `templates/assembly-root/scripts/bootstrap.py` itself — the
    file whose `checkout_tracking_branch` runs `git checkout <tracking>` in a
    leg whose branch tip equals the pin — so the test is about that code.
    """
    leg_seed = base / "seed" / f"{LEG_MEMBER}-spec"
    leg_seed.mkdir(parents=True)
    (leg_seed / "spec.md").write_text("# the spec leg\n", encoding="utf-8")
    git("init", "-q", "-b", "main", ".", cwd=leg_seed)
    commit_all(leg_seed, "the leg")
    leg_bare = base / "remotes" / f"{LEG_MEMBER}-spec.git"
    leg_bare.parent.mkdir(exist_ok=True)
    git("clone", "-q", "--bare", str(leg_seed), str(leg_bare), cwd=base)

    seed = base / "seed" / LEG_MEMBER
    (seed / "scripts").mkdir(parents=True)
    (seed / "project.yaml").write_text(
        "schema_version: 1\nkind: project-manifest\n"
        f"id: {LEG_MEMBER.lower()}\nname: \"{LEG_MEMBER}\"\n"
        "tracking_branch: main\nlegs:\n"
        f"  - role: assembly\n    repository: {ORG}/{LEG_MEMBER}\n"
        '    path: "."\n'
        f"  - role: spec\n    repository: {ORG}/{LEG_MEMBER}-spec\n"
        "    path: spec\n", encoding="utf-8")
    shutil.copy2(UPSTREAM / "templates" / "assembly-root" / "Makefile",
                 seed / "Makefile")
    shutil.copy2(UPSTREAM / "templates" / "assembly-root" / ".gitignore",
                 seed / ".gitignore")
    shutil.copy2(UPSTREAM / "templates" / "assembly-root" / "scripts" / "bootstrap.py",
                 seed / "scripts" / "bootstrap.py")
    shutil.copy2(UPSTREAM / "scripts" / "repo_shape.py",
                 seed / "scripts" / "repo_shape.py")
    for verb in ("park", "resume"):
        write_stub(seed, verb, label=LEG_MEMBER)
    git("init", "-q", "-b", "main", ".", cwd=seed)
    commit_all(seed, "seed")
    git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
        str(leg_bare), "spec", cwd=seed)
    commit_all(seed, "the leg, pinned")
    bare = base / "remotes" / f"{LEG_MEMBER}.git"
    git("clone", "-q", "--bare", str(seed), str(bare), cwd=base)
    return bare, leg_bare


def seed_workspace(base: Path, name: str, files: dict) -> Path:
    """A bare repository standing in for the person's private `<user>-wip`."""
    seed = base / "seed" / f"ws-{name}"
    seed.mkdir(parents=True)
    for rel, body in files.items():
        target = seed / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    git("init", "-q", "-b", "main", ".", cwd=seed)
    commit_all(seed, "the record")
    bare = base / "remotes" / f"{name}.git"
    bare.parent.mkdir(exist_ok=True)
    git("clone", "-q", "--bare", str(seed), str(bare), cwd=base)
    return bare


@pytest.fixture(scope="session")
def remotes(tmp_path_factory) -> dict:
    """Every bare repository this file clones from, built once."""
    base = tmp_path_factory.mktemp("parkresume")
    members = {name: seed_member(base, name) for name in MEMBERS}
    holder = seed_holder(base, members)
    workspace = seed_workspace(
        base, "wip",
        {f"workspaces/{ORG}/{FAMILY.lower()}.yaml": family_manifest()})
    two_orgs = seed_workspace(
        base, "twoorgs",
        {f"workspaces/orga/{FAMILY.lower()}.yaml": family_manifest(),
         f"workspaces/orgb/{FAMILY.lower()}.yaml": family_manifest()})
    solo = seed_workspace(
        base, "solo",
        {f"workspaces/{ORG}/alpha.yaml": standalone_manifest("Alpha")})
    leg_member, leg_bare = seed_leg_member(base)
    legged = seed_workspace(
        base, "legged",
        {f"workspaces/{ORG}/{LEG_MEMBER.lower()}.yaml":
            standalone_manifest(LEG_MEMBER)})
    # A `root:` that walks OUT of the projects directory, which the schema's
    # own invariant forbids and a hand-edited file can still carry (F7).
    escaping = seed_workspace(
        base, "escaping",
        {f"workspaces/{ORG}/runaway.yaml":
            standalone_manifest("Alpha").replace(
                "root: Alpha", "root: ../../elsewhere/Alpha").replace(
                "id: alpha", "id: runaway")})
    return {"base": base, "dir": base / "remotes", "members": members,
            "holder": holder, "workspace": workspace, "two_orgs": two_orgs,
            "solo": solo, "leg_member": leg_member, "leg_bare": leg_bare,
            "legged": legged, "escaping": escaping}


def offline(remotes: dict, extra: dict | None = None) -> dict:
    return {"OPENREPOTOOLS_REMOTE_BASE": str(remotes["dir"]),
            **ALLOW_FILE_PROTOCOL, **(extra or {})}


@pytest.fixture
def estate(remotes, home) -> dict:
    """The family estate ALREADY on this machine: holder plus both siblings.

    Cloned rather than resumed, so the tests about `park` and about a REFRESH
    do not depend on the fresh-machine path working first.
    """
    projects = home / "projects"
    folder = projects / FAMILY
    folder.mkdir(parents=True, exist_ok=True)
    git("-c", "protocol.file.allow=always", "clone", "-q",
        "--recurse-submodules", str(remotes["holder"]), str(folder / FAMILY),
        cwd=projects)
    siblings = {}
    for name in MEMBERS:
        git("clone", "-q", str(remotes["members"][name]),
            str(folder / name), cwd=projects)
        siblings[name] = folder / name
    return {"projects": projects, "folder": folder, "holder": folder / FAMILY,
            "siblings": siblings}


# ===========================================================================
# estate resolution — the half both commands share
# ===========================================================================

@pytest.mark.parametrize("spelling", ["projects", "Projects"])
def test_a_named_estate_is_found_under_either_spelling(tmp_path, spelling):
    """People spell it both ways, which is the issue's own words."""
    fake_home = tmp_path / "home"
    projects = fake_home / spelling
    projects.mkdir(parents=True)
    holder = probe_family(projects, "InkRouter")
    result = run(PARK, "InkRouter", home=fake_home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {holder} ARGS=[]" in result.stdout


def test_projects_dir_overrides_both_spellings(tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    elsewhere = tmp_path / "code"
    elsewhere.mkdir()
    root = probe_project(elsewhere, "Atlas")
    result = run(PARK, "Atlas", home=fake_home,
                 env={"PROJECTS_DIR": str(elsewhere)})
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {root} ARGS=[]" in result.stdout


def test_a_family_folder_wins_over_a_standalone_root_of_the_same_name(home):
    """The holder is what drives the members. A family answered as one of its
    own members would park one project and report the estate parked."""
    projects = home / "projects"
    holder = probe_family(projects, "Dual")
    probe_project(projects, "Dual", at=projects / "Dual")
    result = run(PARK, "Dual", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {holder}" in result.stdout
    assert f"PROBE park in {projects / 'Dual'} " not in result.stdout


def test_with_no_name_the_estate_around_the_cwd_is_used(home):
    """`park` from a subdirectory, which is how a person actually types it."""
    projects = home / "projects"
    holder = probe_family(projects, "InkRouter")
    deep = holder / "scripts" / "inner"
    deep.mkdir(parents=True)
    result = run(PARK, home=home, cwd=deep)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {holder}" in result.stdout


def test_nearest_wins_so_a_member_parks_itself(home):
    """Standing inside a member of a family, the member is the estate. Nearest
    wins: it is where the person is."""
    projects = home / "projects"
    probe_family(projects, "InkRouter")
    member = probe_project(projects, "IRRS", at=projects / "InkRouter" / "IRRS")
    result = run(PARK, home=home, cwd=member)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {member}" in result.stdout


# --- the bare form outside every estate ASKS; `--all` / `-a` is the sweep ----
#
# THIS IS WHERE `park` AND `resume` STOP SHARING THE ANSWER. Ruling 3 of #82
# ("no <Name> and no estate around the cwd REFUSES and lists what it found")
# was superseded for `park`'s bare form by Brett Heap's RULING of 2026-09-10
# on openRepoShape #91 (the bare form PARKED EVERY ESTATE, unasked), and that
# was superseded the same day by his RULING in this repository, verbatim:
# "lets change that so it parks the current repo. if not in a repo, then asks
# if want to park all. and park all should be park -a or park --all." The
# sweep itself is #91's; HOW IT IS REACHED is what these tests hold: the
# walk-up first, then a question at a terminal, a refusal naming `--all`
# without one, and `--all` / `-a` as the sweep with no question, from
# anywhere. `resume`'s own bare form keeps ruling 3, and
# `test_resume_with_no_name_and_no_estate_refuses`, at the end of this file,
# is what holds that half still.

#: The one line `park` asks with. On STDERR, where a prompt belongs, so a
#: `park > log` still shows it; the tests read it there and nowhere else.
QUESTION = "park every estate above? [y/N]"


def run_at_a_terminal(command: Path, *args: str, answer: str, home: Path,
                      cwd: Path | None = None) -> subprocess.CompletedProcess:
    """`run`, except stdin is a PSEUDO-TERMINAL and `answer` is what the
    person types at it.

    `[ -t 0 ]` is how `park` decides whether it may ask, and the pipe `run`
    hands it is the honest way to reach the OTHER branch — so the question
    path needs a real tty on stdin, which `pty.openpty` is. stdout and stderr
    stay pipes: the question (stderr) and the report (stdout) are captured
    apart, exactly as a person's `park > log` would split them. `pty` is
    imported here and not at the top because the module does not exist on
    Windows, and this file has to IMPORT there in order to skip.
    """
    import pty
    master, slave = pty.openpty()
    try:
        proc = subprocess.Popen(
            ["bash", str(command), *args], stdin=slave,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=str(cwd) if cwd else str(home), env=command_env(home))
        os.close(slave)
        slave = -1
        # Typed before `park` reads it: the line discipline holds the line,
        # exactly as a terminal holds one typed ahead of the prompt.
        os.write(master, (answer + "\n").encode())
        out, err = proc.communicate(timeout=120)
    finally:
        if slave != -1:
            os.close(slave)
        os.close(master)
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


@pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES"])
def test_bare_park_outside_every_estate_asks_and_a_yes_parks_them_all(home,
                                                                     answer):
    """The question, then #91's sweep: the list first, every estate in NAME
    order, one summary — reached by an answer, not by default."""
    projects = home / "projects"
    holder = probe_family(projects, "TestFam")
    root = sweepable_project(projects, "Atlas")
    result = run_at_a_terminal(PARK, answer=answer, home=home, cwd=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert QUESTION in result.stderr, "the question, on stderr"
    assert "no estate around" in result.stdout
    assert "family   TestFam" in result.stdout
    assert "project  Atlas" in result.stdout

    list_at = result.stdout.index("Every estate under")
    atlas_at = result.stdout.index("=== park Atlas ===")
    testfam_at = result.stdout.index("=== park TestFam ===")
    assert list_at < atlas_at < testfam_at, (
        "the list must print first, and the estates must run in NAME order")

    assert f"PROBE park in {root} ARGS=[]" in result.stdout
    assert f"PROBE park in {holder} ARGS=[]" in result.stdout
    assert "  parked     Atlas" in result.stdout
    assert "  parked     TestFam" in result.stdout
    assert "park: 2 estate(s) parked, 0 refused or with findings" \
        in result.stdout


@pytest.mark.parametrize("answer", ["", "n", "no", "yep"],
                         ids=["enter", "n", "no", "yep"])
def test_bare_park_outside_every_estate_parks_nothing_unless_the_answer_is_yes(
        home, answer):
    """Enter is a no. So is anything that is not `y` or `yes`: parking every
    estate on a workstation is an answer a person has to GIVE."""
    projects = home / "projects"
    probe_family(projects, "TestFam")
    sweepable_project(projects, "Atlas")
    result = run_at_a_terminal(PARK, answer=answer, home=home, cwd=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert QUESTION in result.stderr
    assert "family   TestFam" in result.stdout, "the list comes before the question"
    assert "project  Atlas" in result.stdout
    assert "nothing was parked" in result.stderr
    assert "park --all" in result.stderr, "the refusal names the unasked form"
    assert "PROBE park in" not in result.stdout, "nothing ran"
    assert "=== park" not in result.stdout


def test_bare_park_outside_every_estate_with_no_terminal_refuses_and_names_all(
        home):
    """`run` hands `park` a PIPE for stdin — what a script, a cron job or an
    assistant's tool call hands it. Nothing can be asked, so nothing is
    parked, and the refusal says how a script asks for the sweep: `--all`."""
    projects = home / "projects"
    probe_family(projects, "TestFam")
    sweepable_project(projects, "Atlas")
    result = run(PARK, home=home, cwd=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no estate around" in result.stderr
    assert "not a terminal" in result.stderr
    assert "park --all" in result.stderr
    assert "family   TestFam" in result.stderr, (
        "ruling 3's list, so the person can name one")
    assert "project  Atlas" in result.stderr
    assert QUESTION not in result.stderr, "nothing was asked"
    assert "PROBE park in" not in result.stdout


def test_bare_park_inside_an_estate_still_parks_only_that_one(home):
    """THE WALK-UP WINS FIRST — "it parks the current repo": standing inside
    an estate parks that estate, asks nothing, and never parks the
    workstation."""
    projects = home / "projects"
    holder = probe_family(projects, "TestFam")
    root = probe_project(projects, "Atlas")
    result = run(PARK, home=home, cwd=holder)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"the family holder at {holder}" in result.stdout
    assert "parking every estate" not in result.stdout
    assert QUESTION not in result.stderr
    assert f"PROBE park in {root}" not in result.stdout, (
        "the OTHER estate must not have been parked")


@pytest.mark.parametrize("flag", ["--all", "-a"])
def test_park_all_parks_every_estate_in_name_order_and_asks_nothing(home,
                                                                    flag):
    """#91's sweep, asked for by name: the list under its own heading, every
    estate in NAME order, one summary, and no question — at a pipe, which is
    what `run` gives it, exactly as at a terminal."""
    projects = home / "projects"
    holder = probe_family(projects, "TestFam")
    root = sweepable_project(projects, "Atlas")
    result = run(PARK, flag, home=home, cwd=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "park --all: parking every estate under" in result.stdout
    assert "family   TestFam" in result.stdout
    assert "project  Atlas" in result.stdout
    assert QUESTION not in result.stderr
    assert "no estate around" not in result.stdout + result.stderr, (
        "--all is not a fallback; it is the ask")

    list_at = result.stdout.index("parking every estate under")
    atlas_at = result.stdout.index("=== park Atlas ===")
    testfam_at = result.stdout.index("=== park TestFam ===")
    assert list_at < atlas_at < testfam_at, (
        "the list must print first, and the estates must run in NAME order")

    assert f"PROBE park in {root} ARGS=[]" in result.stdout
    assert f"PROBE park in {holder} ARGS=[]" in result.stdout
    assert "  parked     Atlas" in result.stdout
    assert "  parked     TestFam" in result.stdout
    assert "park: 2 estate(s) parked, 0 refused or with findings" \
        in result.stdout


def test_park_all_from_inside_an_estate_still_parks_every_estate(home):
    """A flag that says every one is not narrowed by where you stand."""
    projects = home / "projects"
    holder = probe_family(projects, "TestFam")
    root = sweepable_project(projects, "Atlas")
    result = run(PARK, "--all", home=home, cwd=holder)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "park --all: parking every estate under" in result.stdout
    assert f"PROBE park in {root} ARGS=[]" in result.stdout
    assert f"PROBE park in {holder} ARGS=[]" in result.stdout
    assert "park: 2 estate(s) parked, 0 refused or with findings" \
        in result.stdout


def test_park_all_continues_past_a_refused_estate_and_still_parks_the_rest(
        home):
    """A skip is not a pass (#80's rule): one estate's own `make park`
    exiting non-zero must not stop the others, and the overall run must not
    read as clean either."""
    projects = home / "projects"
    holder = probe_family(projects, "TestFam")
    root = sweepable_project(projects, "Atlas")
    (root / "Makefile").write_text(FAILING_PARK_PROBE_MAKEFILE,
                                   encoding="utf-8")

    result = run(PARK, "--all", home=home, cwd=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"PROBE park in {root} ARGS=[]" in result.stdout, (
        "the refused estate still ran; it is refused by its OWN exit code")
    assert f"PROBE park in {holder} ARGS=[]" in result.stdout, (
        "the estate after the refused one must still be parked")
    assert "park: Atlas - `make park` exited 2" in result.stdout, (
        "make wraps the recipe's exit 3 in its own exit 2")
    assert "  refused    Atlas (exit 2)" in result.stdout
    assert "  parked     TestFam" in result.stdout
    assert "park: 1 estate(s) parked, 1 refused or with findings" \
        in result.stdout


def test_park_all_dry_run_lane_and_passthrough_args_reach_every_estate(home):
    projects = home / "projects"
    holder = probe_family(projects, "TestFam")
    root = sweepable_project(projects, "Atlas")
    result = run(PARK, "--all", "--dry-run", "--lane", "xfactory-2", "--",
                 "--feature", "001-a", home=home, cwd=home)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = "ARGS=[--dry-run --lane xfactory-2 --feature 001-a]"
    assert f"PROBE park in {root} {expected}" in result.stdout
    assert f"PROBE park in {holder} {expected}" in result.stdout
    assert result.stdout.count(
        "--dry-run: nothing was committed, pushed or recorded.") == 2


def test_park_all_with_a_name_or_a_repo_refuses(home):
    """One estate or every estate, never both spelled at once."""
    projects = home / "projects"
    root = sweepable_project(projects, "Atlas")
    named = run(PARK, "Atlas", "--all", home=home)
    assert named.returncode == 2, named.stdout + named.stderr
    assert "both <Name> ('Atlas') and --all" in named.stderr
    by_repo = run(PARK, "--all", "--repo", "TestOrg/Atlas", home=home)
    assert by_repo.returncode == 2, by_repo.stdout + by_repo.stderr
    assert "both --repo 'TestOrg/Atlas' and --all" in by_repo.stderr
    for result in (named, by_repo):
        assert f"PROBE park in {root}" not in result.stdout, "nothing ran"


def test_park_all_with_no_estate_anywhere_refuses(home):
    result = run(PARK, "--all", home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "--all found no estate under" in result.stderr
    assert "resume <Name>" in result.stderr
    assert "PROBE park in" not in result.stdout


# --- #6: the sweep SKIPS a root that has no Speckit overlay ----------------
#
# Brett Heap's RULING of 2026-09-10 on openRepoShape #92, verbatim: "rule on
# the #92 open item: skip roots without the overlay." A root whose
# `.specify/extensions/git/scripts/bash/park.sh` is not there is one whose
# own `make park` can only refuse (exit 2), so counting it as a refusal made
# a real workstation's sweep exit 1 for ever. THE SWEEP skips it; the person
# who NAMES it still gets the refusal, which is the pair of tests below. The
# sweep is driven with `--all` here, which is the form that asks nothing;
# the bare form's YES runs the identical `park_every_estate`, and the tests
# above hold that.

def test_the_sweep_skips_a_root_without_the_overlay_and_parks_the_rest(home):
    """Both answers in one run: the roots that CAN park do, the ones that
    cannot are named and counted apart, and the run is clean."""
    projects = home / "projects"
    parkable = {name: sweepable_project(projects, name)
                for name in ("Atlas", "Borealis")}
    bare = {name: probe_project(projects, name)
            for name in ("MedxEHR", "openDox")}

    result = run(PARK, "--all", home=home, cwd=home)
    assert result.returncode == 0, result.stdout + result.stderr
    for name, root in parkable.items():
        assert f"PROBE park in {root} ARGS=[]" in result.stdout
        assert f"  parked     {name}" in result.stdout
    for name, root in bare.items():
        assert f"=== park {name} ===" in result.stdout, (
            "a root left out of the run silently is one a person has to go "
            "and look for; the heading is how they see it was considered")
        assert f"PROBE park in {root}" not in result.stdout, (
            f"nothing may run in {name}: it was skipped, not parked")
        assert f"  skipped    {name} (no Speckit overlay)" in result.stdout
    assert result.stdout.count(
        "SKIPPED (no Speckit overlay; install it with: setup-openspeckit)") \
        == 2, "one line per skipped root, and it names the installer"
    assert ("park: 2 estate(s) parked, 0 refused or with findings, "
            "2 skipped (no overlay)") in result.stdout


def test_every_estate_skipped_is_exit_zero_and_says_so(home):
    """Nothing ran, so nothing failed. A workstation whose roots have never
    been given the overlay must not be told its park failed — it must be
    told what to install."""
    projects = home / "projects"
    for name in ("MedxEHR", "openDox"):
        probe_project(projects, name)

    result = run(PARK, "--all", home=home, cwd=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PROBE park in" not in result.stdout
    assert ("park: 0 estate(s) parked, 0 refused or with findings, "
            "2 skipped (no overlay)") in result.stdout
    assert "nothing here was park-able" in result.stdout
    assert "setup-openspeckit" in result.stdout


def test_a_skipped_root_never_hides_a_real_refusal(home):
    """The exit code is computed over the estates that RAN. One that refused
    still fails the run, and both lines are on screen — which is the whole
    reason the skipped ones are counted apart rather than not printed."""
    projects = home / "projects"
    refuser = sweepable_project(projects, "Atlas")
    (refuser / "Makefile").write_text(FAILING_PARK_PROBE_MAKEFILE,
                                      encoding="utf-8")
    probe_project(projects, "MedxEHR")
    holder = probe_family(projects, "TestFam")

    result = run(PARK, "--all", home=home, cwd=home)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "  refused    Atlas (exit 2)" in result.stdout
    assert "  skipped    MedxEHR (no Speckit overlay)" in result.stdout
    assert "  parked     TestFam" in result.stdout
    assert f"PROBE park in {holder} ARGS=[]" in result.stdout, (
        "the estate after the skipped one must still be parked")
    assert ("park: 1 estate(s) parked, 1 refused or with findings, "
            "1 skipped (no overlay)") in result.stdout


def test_the_sweep_dry_run_says_it_would_skip_and_creates_nothing(home):
    projects = home / "projects"
    root = probe_project(projects, "MedxEHR")
    before = sorted(p.name for p in root.iterdir())

    result = run(PARK, "--all", "--dry-run", home=home, cwd=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("would skip (no Speckit overlay; install it with: "
            "setup-openspeckit)") in result.stdout
    assert "SKIPPED (" not in result.stdout, (
        "a rehearsal reports what it WOULD do; only a real run skips")
    assert sorted(p.name for p in root.iterdir()) == before
    assert not (root / OVERLAY).exists(), "park installs nothing, ever"


def test_naming_an_overlay_less_root_still_relays_the_makefiles_refusal(home):
    """ONLY THE SWEEP SKIPS. `park <Name>` named a root, and a person who
    named one gets its own `make park` refusal — the Makefile's, verbatim,
    naming the installer.

    Against the REAL `templates/assembly-root/Makefile`, because the refusal
    under test is that file's `test -x $(PARK) || … exit 2` and a probe
    Makefile could only fake it. The same root is swept first, to show the
    two answers coming apart on one directory: skipped when nobody named it,
    refused when somebody did.
    """
    projects = home / "projects"
    root = projects / "MedxEHR"
    root.mkdir(parents=True)
    (root / "project.yaml").write_text(
        PROJECT_YAML.format(id="medxehr", name="MedxEHR", org=ORG),
        encoding="utf-8")
    shutil.copy2(UPSTREAM / "templates" / "assembly-root" / "Makefile",
                 root / "Makefile")

    swept = run(PARK, "--all", home=home, cwd=home)
    assert swept.returncode == 0, swept.stdout + swept.stderr
    assert "  skipped    MedxEHR (no Speckit overlay)" in swept.stdout

    named = run(PARK, "MedxEHR", home=home)
    assert named.returncode == 2, named.stdout + named.stderr
    assert ("make park needs the Speckit worktree overlay; install it with: "
            "setup-openspeckit") in named.stderr, (
        "the Makefile's own refusal, relayed rather than replaced")
    assert "`make park` exited 2" in named.stdout
    assert "SKIPPED" not in named.stdout + named.stderr, (
        "naming a root must never skip it")


def test_a_family_holder_in_the_sweep_is_never_pre_checked(home):
    """A holder's Makefile makes no overlay test: it fans out with
    `siblings.py --make park`, and a member's own refusal is the holder's to
    report. Pre-checking the holder would skip a whole family for want of a
    file its Makefile never reads."""
    projects = home / "projects"
    holder = probe_family(projects, "TestFam")
    assert not (holder / OVERLAY / "park.sh").exists(), (
        "the fixture must NOT carry the overlay, or this proves nothing")

    result = run(PARK, "--all", home=home, cwd=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"PROBE park in {holder} ARGS=[]" in result.stdout
    assert "  parked     TestFam" in result.stdout
    assert "skipped (no overlay)" not in result.stdout, (
        "with nothing skipped the summary is #91's line, unchanged")
    assert "park: 1 estate(s) parked, 0 refused or with findings" \
        in result.stdout


def test_no_name_and_no_estate_anywhere_refuses_without_asking(home):
    """Nothing to list and nothing to ask about: not the question, and not
    the no-terminal refusal either — there is no sweep here to say yes to.
    At a pipe and at a terminal alike."""
    piped = run(PARK, home=home)
    typed = run_at_a_terminal(PARK, answer="y", home=home)
    for result in (piped, typed):
        assert result.returncode == 2, result.stdout + result.stderr
        assert "no estate around" in result.stderr
        assert "nothing to park" in result.stderr
        assert "resume <Name>" in result.stderr
        assert QUESTION not in result.stderr
        assert "--all" not in result.stderr, "--all would find nothing either"


def test_a_name_that_is_not_an_estate_refuses_and_names_resume(home):
    projects = home / "projects"
    probe_project(projects, "Atlas")
    result = run(PARK, "Nope", home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no estate named 'Nope'" in result.stderr
    assert "resume Nope" in result.stderr
    assert "project  Atlas" in result.stderr


#: The three spellings of one repository a clone's `origin` can carry. All
#: three must answer `--repo testorg/atlas` — and the case difference is in the
#: flag on purpose: GitHub owners and names are case-insensitive.
ORIGIN_SPELLINGS = [
    "https://github.com/TestOrg/Atlas.git",
    "git@github.com:TestOrg/Atlas.git",
    "ssh://git@github.com/TestOrg/Atlas.git",
]


@pytest.mark.parametrize("origin", ORIGIN_SPELLINGS)
def test_repo_matches_a_local_clone_by_its_origin(home, origin):
    """RULING 1: `--repo` matches a clone you already have."""
    projects = home / "projects"
    root = probe_project(projects, "Atlas")
    git("init", "-q", "-b", "main", ".", cwd=root)
    git("remote", "add", "origin", origin, cwd=root)
    result = run(PARK, "--repo", "testorg/atlas", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {root}" in result.stdout


def test_repo_finds_a_member_two_levels_down(home):
    """The estates this standard places are `<projects>/<Project>` and
    `<projects>/<Family>/<Project>`, so the search is two deep."""
    projects = home / "projects"
    probe_family(projects, "InkRouter")
    member = probe_project(projects, "IRRS", at=projects / "InkRouter" / "IRRS")
    git("init", "-q", "-b", "main", ".", cwd=member)
    git("remote", "add", "origin", "https://github.com/TestOrg/IRRS.git",
        cwd=member)
    result = run(PARK, "--repo", "TestOrg/IRRS", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {member}" in result.stdout


def test_repo_with_no_match_refuses_and_names_git_clone(home):
    """RULING 1's other half: only `resume` clones, so this refusal names the
    clone command rather than running one."""
    projects = home / "projects"
    probe_project(projects, "Atlas")
    result = run(PARK, "--repo", "TestOrg/Nothing", home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no clone under your projects directory has origin TestOrg/Nothing" \
        in result.stderr
    assert "git clone --recurse-submodules https://github.com/TestOrg/Nothing.git" \
        in result.stderr
    assert "it never clones one" in result.stderr


def test_repo_that_is_not_owner_slash_name_is_refused(home):
    result = run(PARK, "--repo", "Atlas", home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "'Atlas' is not a repository" in result.stderr


def test_a_name_and_repo_together_are_refused(home):
    result = run(PARK, "Atlas", "--repo", "TestOrg/Atlas", home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "One estate per run" in result.stderr


@pytest.mark.parametrize("command", [PARK, RESUME], ids=["park", "resume"])
def test_an_unknown_flag_is_refused_and_names_the_double_dash(home, command):
    """The extension has flags these commands have no opinion about, and a
    command that ate them would be a command people stop using the moment the
    extension grows one."""
    result = run(command, "--feature", "001-a", home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "does not know --feature" in result.stderr
    assert "-- --feature" in result.stderr


@pytest.mark.parametrize("command", [PARK, RESUME], ids=["park", "resume"])
def test_help_prints_the_first_usage_line(command):
    result = subprocess.run(["bash", str(command), "--help"],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0].startswith(f"{command.name} [<Name>]")


# ===========================================================================
# park
# ===========================================================================

def test_park_drives_the_holders_make_park_and_args_arrive(estate, home):
    """The whole interface: the holder's `make park` fans out to each member's
    working clone, and `ARGS` reaches the extension in every one of them."""
    result = run(PARK, FAMILY, "--dry-run", "--lane", "xfactory-2", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"park: {FAMILY} - the family holder at {estate['holder']}" \
        in result.stdout
    assert "make park ARGS='--dry-run --lane xfactory-2'" in result.stdout
    for name in MEMBERS:
        assert f"--- {name}: make park ---" in result.stdout
        assert f"{name}.sh ran with: --dry-run --lane xfactory-2" \
            in result.stdout


def test_park_passes_extension_flags_after_a_double_dash(estate, home):
    result = run(PARK, FAMILY, "--", "--feature", "001-a", "--no-push",
                 home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    for name in MEMBERS:
        assert f"{name}.sh ran with: --feature 001-a --no-push" in result.stdout


def test_park_reports_an_unpushed_main_commit_and_a_dirty_root(estate, home):
    """What park does NOT carry. Neither is park's to touch: a root is PR-only
    and a pin bump in progress is somebody's unfinished edit."""
    alpha = estate["siblings"]["Alpha"]
    (alpha / "LOCAL.md").write_text("never pushed\n", encoding="utf-8")
    commit_all(alpha, "a commit on main that origin has not seen")
    (estate["holder"] / "PINBUMP.md").write_text("half a bump\n",
                                                 encoding="utf-8")

    result = run(PARK, FAMILY, home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "what park does NOT carry" in result.stdout
    assert f"unpushed main   root    {alpha}" in result.stdout
    assert "1 commit(s) on main that origin has not seen" in result.stdout
    assert "land them as a pull request" in result.stdout
    assert f"uncommitted    holder  {estate['holder']}" in result.stdout
    assert "A pin bump in progress is not" in result.stdout
    assert "ignored files  never travel" in result.stdout
    assert "2 thing(s) above are not park's to carry" in result.stdout


def test_park_says_when_it_left_nothing_behind(estate, home):
    result = run(PARK, FAMILY, home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "nothing else was left behind" in result.stdout
    assert "0 thing(s) above are not park's to carry" in result.stdout


def test_park_never_reads_the_pinned_copy(estate, home):
    """`members/<Project>` is pinned and DETACHED; nobody's work is there, and
    a report that named it would be reporting on the wrong copy."""
    result = run(PARK, FAMILY, home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "members/" not in result.stdout.split("what park does NOT carry")[1]


def test_park_dry_run_creates_and_commits_nothing(estate, home):
    heads = {name: git("rev-parse", "HEAD", cwd=path).stdout
             for name, path in estate["siblings"].items()}
    holder_head = git("rev-parse", "HEAD", cwd=estate["holder"]).stdout
    before = sorted(p.name for p in estate["folder"].iterdir())

    result = run(PARK, FAMILY, "--dry-run", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "--dry-run: nothing was committed, pushed or recorded." \
        in result.stdout
    for name, path in estate["siblings"].items():
        assert git("rev-parse", "HEAD", cwd=path).stdout == heads[name]
    assert git("rev-parse", "HEAD",
               cwd=estate["holder"]).stdout == holder_head
    assert sorted(p.name for p in estate["folder"].iterdir()) == before


def test_park_in_a_standalone_root_runs_that_roots_verb(estate, home):
    """A member of a family IS a standalone estate when you name it: `park
    --repo <owner>/Alpha` is the member's own root, not the holder's.

    The origin is re-spelled as the url a real member carries, because a clone
    whose origin is a bare repository ON DISK answers `<Name>` and the
    walk-up but never `--repo`: a filesystem path has a name and no owner, and
    inventing one is what `repo_slug_of` refuses to do.
    """
    git("remote", "set-url", "origin",
        f"https://github.com/{ORG}/Alpha.git", cwd=estate["siblings"]["Alpha"])
    result = run(PARK, "--repo", f"{ORG}/Alpha", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "the assembly root at" in result.stdout
    assert "Alpha.sh ran with:" in result.stdout
    assert "Bravo.sh ran with:" not in result.stdout


def test_park_passes_the_scripts_exit_code_through(estate, home):
    """A refusal must never read as success. Make flattens the extension's 3
    to its own 2 (#80's Makefile says so at the target); what matters is that
    the run is non-zero and the code is still on screen."""
    write_stub(estate["siblings"]["Alpha"], "park", code=3, label="Alpha")
    result = run(PARK, FAMILY, home=home)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "3" in result.stdout + result.stderr
    assert "`make park` exited" in result.stdout


def test_park_refuses_a_root_with_no_makefile(home):
    projects = home / "projects"
    root = projects / "Atlas"
    root.mkdir(parents=True)
    (root / "project.yaml").write_text(
        PROJECT_YAML.format(id="atlas", name="Atlas", org=ORG),
        encoding="utf-8")
    result = run(PARK, "Atlas", home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "has no Makefile" in result.stderr
    assert "update-shape.py" in result.stderr


# ===========================================================================
# resume — the fresh machine
# ===========================================================================

def test_resume_on_a_fresh_machine_builds_the_whole_estate(remotes, home):
    """The issue's own sentence, end to end and offline: `resume InkRouter` on
    a machine that has none of it — clone the workspace record, write the
    config, clone the holder into `<Family>/<Family>`, bootstrap it, place
    every member beside it, and recreate their features."""
    result = run(RESUME, FAMILY, "--workspace", WORKSPACE_SLUG, home=home,
                 env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout

    config = home / ".agents" / "workspace.yaml"
    assert config.is_file(), result.stdout + result.stderr
    assert config.read_text(encoding="utf-8") == (
        f"repository: {WORKSPACE_SLUG}\npath: ~/projects/wip\n")
    assert (home / "projects" / "wip" / "workspaces" / ORG
            / f"{FAMILY.lower()}.yaml").is_file(), (
        "park.sh names the manifest for the family's lowercase id")

    folder = home / "projects" / FAMILY
    holder = folder / FAMILY
    assert (holder / "family.yaml").is_file(), "the holder was not cloned"
    assert (holder / "members" / "Alpha" / ".git").exists(), (
        "the pinned copies came with --recurse-submodules")
    for name in MEMBERS:
        assert (folder / name / ".git").is_dir(), f"{name} is not beside it"
        assert git("rev-parse", "--abbrev-ref", "HEAD",
                   cwd=folder / name).stdout.strip() == "main"
        assert f"{name}.sh ran with:" in result.stdout, (
            "each member's own make resume must have run")
    assert "(b) the layout" in result.stdout
    assert f"holder    {FAMILY}" in result.stdout
    assert "`make resume` exited 0" in result.stdout
    assert "0 refusal(s)" in result.stdout


def test_resume_writes_the_config_only_when_asked_by_name(remotes, home):
    """One of the two files this standard ever writes outside a repository —
    and it is the SAME file as the other, `~/.agents/workspace.yaml`, written
    here only because `--workspace` asked for it.

    `openRepoTools wip init` is the second writer (Amendment 9(c) step 9), for
    the same reason and under the same condition: only on a machine that has
    none, and only because the person asked for the repository by running it.
    The invariant that retired was "the ONLY file", and it retired on purpose
    rather than by being found with a red test."""
    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no workspace record is configured" in result.stderr
    assert "--workspace <owner>/<repo>" in result.stderr
    assert not (home / ".agents" / "workspace.yaml").exists()
    assert not (home / "projects" / FAMILY).exists(), "nothing was created"


def test_resume_refuses_to_overwrite_a_config_that_names_another_repository(
        remotes, home):
    config = home / ".agents" / "workspace.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("repository: tester/other\npath: ~/projects/other\n",
                      encoding="utf-8")
    result = run(RESUME, FAMILY, "--workspace", WORKSPACE_SLUG, home=home,
                 env=offline(remotes))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "already names" in result.stderr
    assert "never overwrites one" in result.stderr
    assert config.read_text(encoding="utf-8").startswith(
        "repository: tester/other")


def test_resume_clones_the_workspace_the_config_names(remotes, home):
    """A config that is there and a checkout that is not: the repository comes
    from the config, and no flag is needed."""
    config = home / ".agents" / "workspace.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(f"repository: {WORKSPACE_SLUG}\npath: ~/projects/wip\n",
                      encoding="utf-8")
    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    assert (home / "projects" / "wip" / "workspaces").is_dir()
    assert (home / "projects" / FAMILY / FAMILY / "family.yaml").is_file()


def test_resume_refuses_when_two_orgs_record_the_same_name(remotes, home):
    """Two projects in two organisations may share a name, so nothing here
    picks one — and `--org` is how the question gets answered."""
    refused = run(RESUME, FAMILY, "--workspace", "tester/twoorgs", home=home,
                  env=offline(remotes))
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "workspace manifests record 'TestFam'" in refused.stderr
    assert "orga/testfam.yaml" in refused.stderr
    assert "orgb/testfam.yaml" in refused.stderr
    assert f"resume {FAMILY} --org <org>" in refused.stderr
    assert not (home / "projects" / FAMILY).exists()

    # The config was written by the run above, so this one needs no flag.
    answered = run(RESUME, FAMILY, "--org", "orgb", home=home,
                   env=offline(remotes))
    assert answered.returncode == 0, answered.stderr + answered.stdout
    assert "org             orgb" in answered.stdout
    assert (home / "projects" / FAMILY / FAMILY / "family.yaml").is_file()


def test_resume_refuses_a_name_no_manifest_records(remotes, home):
    config = home / ".agents" / "workspace.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(f"repository: {WORKSPACE_SLUG}\npath: ~/projects/wip\n",
                      encoding="utf-8")
    result = run(RESUME, "Nowhere", home=home, env=offline(remotes))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no workspace manifest records 'Nowhere'" in result.stderr
    assert "grep -rn 'id: '" in result.stderr


def test_resume_dry_run_clones_nothing(remotes, home):
    config = home / ".agents" / "workspace.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(f"repository: {WORKSPACE_SLUG}\npath: ~/projects/wip\n",
                      encoding="utf-8")
    result = run(RESUME, FAMILY, "--dry-run", home=home, env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "would clone" in result.stdout
    assert "nothing was cloned, pulled, bootstrapped or recreated" \
        in result.stdout
    assert not (home / "projects" / "wip").exists()
    assert not (home / "projects" / FAMILY).exists()


def test_resume_rebuilds_a_standalone_project(remotes, home):
    """One root and no holder: the repository comes from `projects[0]`, the
    folder from its `root:`, and there is no `make siblings` in it at all.

    `resume Alpha` also proves the file lookup: the manifest is `alpha.yaml`,
    named for the project id, while `Alpha` is the folder a person types.
    """
    result = run(RESUME, "Alpha", "--workspace", "tester/solo", home=home,
                 env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    root = home / "projects" / "Alpha"
    assert (root / "project.yaml").is_file(), result.stdout + result.stderr
    assert "records         a standalone estate, root repository testorg/Alpha" \
        in result.stdout
    assert "BOOTSTRAP-Alpha ran" in result.stdout
    assert "Alpha.sh ran with:" in result.stdout
    assert "make siblings" not in result.stdout
    assert "root      Alpha" in result.stdout, "the layout table names the root"
    assert not (home / "projects" / FAMILY).exists(), (
        "a standalone resume must not touch the family of the same members")


# ===========================================================================
# the review on #83 — every finding, reproduced then held
# ===========================================================================

def test_the_three_commands_carry_the_same_resolver_byte_for_byte():
    """The duplication is deliberate and the claim has to stay true.

    `park`, `resume` and `status` are each ONE file a person has on PATH, so
    the estate resolver is copied rather than sourced. A copy that has drifted
    is two answers to "which estate is this", which is the one thing the block
    exists to prevent — so the three are compared here rather than asserted in
    a PR body nobody re-reads.
    """
    def block(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        start = text.index("# --- BEGIN shared estate resolver")
        end = text.index("# --- END shared estate resolver")
        return text[start:end]

    assert block(PARK) == block(RESUME), (
        "park and resume have drifted apart in the shared estate resolver")
    assert block(PARK) == block(STATUS), (
        "park and status have drifted apart in the shared estate resolver")
    assert len(block(PARK).splitlines()) > 100, "the marker moved, not the block"


@pytest.mark.parametrize("command", [PARK, RESUME], ids=["park", "resume"])
@pytest.mark.parametrize("bad", ["../elsewhere", "/abs/where", "a/b", ".hidden"])
def test_a_name_that_is_a_path_is_refused_by_name(home, command, bad):
    """<Name> is joined to the projects directory, so a path in it would land
    the run somewhere nobody named."""
    result = run(command, bad, home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "is not an estate name" in result.stderr
    assert bad in result.stderr


#: EVERY VALUE-TAKING FLAG THE TWO COMMANDS HAVE, and nothing else is one.
#: The two tests below are the two halves of ONE rule — a flag given no value
#: and a flag given an empty one are the same refusal, in the command's own
#: words — so they read one list rather than two that can drift apart the next
#: time a flag is added.
VALUE_TAKING_FLAGS = [
    (PARK, "--lane"), (PARK, "--repo"), (PARK, "--name"), (PARK, "--project"),
    (RESUME, "--repo"), (RESUME, "--workspace"), (RESUME, "--org"),
    (RESUME, "--name"), (RESUME, "--project"),
]


def flag_id(value):
    """`park---lane` in the test id, rather than `command0-flag0`."""
    return value.name if isinstance(value, Path) else value


@pytest.mark.parametrize("command, flag", VALUE_TAKING_FLAGS, ids=flag_id)
def test_a_flag_without_its_value_is_refused_in_the_commands_own_words(
        home, command, flag):
    """`${2:?…}` was bash's message and bash's exit 1 — a status neither verb
    means anything by, and one a wrapper reads as `make`'s. Now the refusal
    is the command's own, exit 2, and it says what the value is; and nothing
    ran, cloned or was placed before it was raised."""
    probe_project(home / "projects", "Atlas")
    result = run(command, flag, home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"REFUSED: {flag} needs a value:" in result.stderr
    assert "line " not in result.stderr, "bash's own message leaked"
    assert "PROBE" not in result.stdout, "the estate must not have been touched"
    assert not (home / ".agents").exists(), "nothing may be written before a refusal"


@pytest.mark.parametrize("command, flag", VALUE_TAKING_FLAGS, ids=flag_id)
def test_a_flag_given_an_empty_value_is_refused_the_same_way(
        home, command, flag):
    """AN EMPTY VALUE IS NOT A VALUE, and it never was: `${2:?…}` rejected
    unset AND null, and the `[ $# -ge 2 ]` that replaced it rejects only the
    unset half (Copilot's review of #14, posted a minute after it merged).
    Every one of these values is read further down as "was this given at
    all?", so the half that was let through was the silent one — `--lane ""`
    parks with the lane dropped from the WIP commit subject, and `--repo ""`
    resolves the estate from the current directory, which is the one thing
    naming a clone's origin was there to prevent.

    RUN FROM INSIDE AN ESTATE, which is what makes this bite. The walk-up
    finds `Atlas` from there, so before the fix every one of these carried on
    — `park` all the way into `make park`, `resume` as far as the workspace
    record — and only the flag a person typed went missing. NOTHING IS
    PRINTED AT ALL now: the refusal is raised in the argument loop, before the
    estate is resolved and before the first `say`, so an empty stdout is the
    proof that neither the fallback nor the verb was reached.
    """
    root = probe_project(home / "projects", "Atlas")
    result = run(command, flag, "", home=home, cwd=root)
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"REFUSED: {flag} needs a value:" in result.stderr
    # BASH'S OWN MESSAGE, in either of the shapes it takes: `${2:?…}` prints
    # the file and line and "parameter null or not set", and exits 1.
    assert "${2:?" not in result.stderr
    assert "parameter null or not set" not in result.stderr
    assert "line " not in result.stderr, "bash's own message leaked"
    assert result.stdout == "", (
        "nothing may be resolved, said or run before an empty value is "
        f"refused; stdout was {result.stdout!r}")
    assert not (home / ".agents").exists(), "nothing may be written before a refusal"


@pytest.mark.parametrize("command, flag", VALUE_TAKING_FLAGS, ids=flag_id)
def test_a_flag_given_a_flag_for_its_value_is_refused_and_nothing_runs(
        home, command, flag):
    """A FLAG IS NOT A VALUE, and it was read as one until now.

    `${2:?…}` and the arity check that replaced it both asked only whether
    there was a next argument; `park Atlas --lane --dry-run` therefore ran a
    REAL park with its lane set to `--dry-run` — the flag a person typed,
    swallowed, with `--dry-run` itself never taking effect and nothing but
    the WIP commit subject to say so. That is the same silence as `--lane ""`,
    one argument further along, and this is the same refusal: exit 2, in the
    arm's own words, in the argument loop before anything is resolved or run.

    THE REFUSAL NAMES THE WAY BACK, which is the whole reason `-*` can be
    refused at all: `--lane=--dry-run` says the same thing and is not
    ambiguous, so nothing a person could legitimately mean has been taken
    away. Asserted here per flag, because a hint that named the wrong flag
    would be worse than none.

    RUN FROM INSIDE AN ESTATE, which is what makes this bite: the walk-up
    finds `Atlas` from there, so before the fix `park` went all the way into
    `make park` and `resume` as far as the workspace record. An empty stdout
    is the proof that neither the verb nor the fallback was reached.
    """
    root = probe_project(home / "projects", "Atlas")
    result = run(command, flag, "--dry-run", home=home, cwd=root)
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"REFUSED: {flag} needs a value:" in result.stderr
    assert "`--dry-run` begins with a `-`" in result.stderr
    assert f"{flag}=--dry-run" in result.stderr, (
        "the refusal must name the spelling that does take this value")
    assert result.stdout == "", (
        "nothing may be resolved, said or run before a flag given a flag is "
        f"refused; stdout was {result.stdout!r}")
    assert "PROBE" not in result.stdout + result.stderr, (
        "the estate's own make target ran: nothing was parked, and nothing "
        "may have been")
    assert not (home / ".agents").exists(), "nothing may be written before a refusal"


@pytest.mark.parametrize("command, flag", VALUE_TAKING_FLAGS, ids=flag_id)
def test_a_flag_takes_its_value_after_an_equals_sign_too(home, command, flag):
    """`--flag=value` IS `--flag value`, and it is the only way to pass a
    value that begins with `-`.

    Refusing a `-`-led value in the spaced spelling would otherwise foreclose
    such a value entirely, because these arms had no `=` form at all: before
    this, `--lane=x` fell through to the catch-all and came back as "park does
    not know --lane=x". So the two halves are asserted together — the same
    command, spelled both ways, has to produce the same bytes and the same
    exit; and `--flag=--dry-run` has to be ACCEPTED, which is what makes the
    refusal above a spelling rule rather than a value this toolset can no
    longer express.

    AN `=` WITH NOTHING AFTER IT IS AN EMPTY VALUE, refused exactly as `""`
    is: `${1#*=}` cannot tell the two apart and must not, or `--repo=` would
    be the walk-up again under a new spelling.
    """
    root = probe_project(home / "projects", "Atlas")
    spaced = run(command, flag, "zz-value", home=home, cwd=root)
    equals = run(command, f"{flag}=zz-value", home=home, cwd=root)
    assert (equals.returncode, equals.stdout, equals.stderr) == \
        (spaced.returncode, spaced.stdout, spaced.stderr), (
            f"{flag}=zz-value and {flag} zz-value are not the same run:\n"
            f"  = : {equals.returncode} {equals.stdout!r} {equals.stderr!r}\n"
            f"  ' ': {spaced.returncode} {spaced.stdout!r} {spaced.stderr!r}")
    assert "does not know" not in equals.stderr

    weird = run(command, f"{flag}=--dry-run", home=home, cwd=root)
    assert f"{flag} needs a value" not in weird.stderr, (
        f"{flag}=--dry-run is the spelling the refusal names; it must take "
        f"the value, not repeat the refusal")
    assert "does not know" not in weird.stderr, (
        f"{flag}=--dry-run reached the catch-all: the `=` arm is missing")

    nothing = run(command, f"{flag}=", home=home, cwd=root)
    assert nothing.returncode == 2, nothing.stdout + nothing.stderr
    assert f"REFUSED: {flag} needs a value:" in nothing.stderr
    assert "begins with a `-`" not in nothing.stderr, (
        "an empty value is empty, not flag-shaped")
    assert nothing.stdout == "", (
        f"nothing may be run before `{flag}=` is refused; stdout was "
        f"{nothing.stdout!r}")


def test_park_takes_a_lane_beginning_with_a_dash_through_the_equals_form(home):
    """THE CASE #17 NAMED, both halves, end to end.

    `park Atlas --lane --dry-run` is the accident: two flags typed, one
    swallowed as the other's value, a REAL park where a rehearsal was meant.
    It is now a refusal that runs nothing — the probe Makefile would say so if
    it had.

    And said with an `=` it is a lane again: `--lane=--dry-run --dry-run` puts
    BOTH through, so `ARGS` carries the rehearsal flag once from `--dry-run`
    and once as the lane's value. That second `--dry-run` is what proves the
    value survived: a lane is passed to the extension as `--lane <value>`, and
    a value beginning with `-` is exactly what this repository could not say
    before.
    """
    root = probe_project(home / "projects", "Atlas")
    refused = run(PARK, "Atlas", "--lane", "--dry-run", home=home)
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "REFUSED: --lane needs a value:" in refused.stderr
    assert "--lane=--dry-run" in refused.stderr
    assert refused.stdout == "", f"a refusal parked: {refused.stdout!r}"
    assert "PROBE park" not in refused.stdout + refused.stderr

    result = run(PARK, "Atlas", "--lane=--dry-run", "--dry-run", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "make park ARGS='--dry-run --lane --dry-run'" in result.stdout
    assert f"PROBE park in {root} ARGS=[--dry-run --lane --dry-run]" \
        in result.stdout


def test_resume_takes_the_workspace_and_the_org_after_an_equals_sign(remotes,
                                                                     home):
    """The `=` spelling is not a second parser: the value does the same work.

    Both of these flags CHANGE WHAT HAPPENS rather than merely being echoed —
    `--workspace` names the private repository to clone, `--org` picks between
    two manifests that record one name — so a spelling that arrived but was
    read as something else would show here and nowhere in the parametrized
    pair above. The two calls are the same two `test_resume_refuses_when_two_
    orgs_record_the_same_name` makes, spelled with an `=`.
    """
    refused = run(RESUME, FAMILY, "--workspace=tester/twoorgs", home=home,
                  env=offline(remotes))
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "workspace manifests record 'TestFam'" in refused.stderr
    assert f"resume {FAMILY} --org <org>" in refused.stderr
    assert (home / ".agents" / "workspace.yaml").is_file(), (
        "the workspace slug arrived: the config it writes is the proof")

    answered = run(RESUME, FAMILY, "--org=orgb", home=home,
                   env=offline(remotes))
    assert answered.returncode == 0, answered.stderr + answered.stdout
    assert "org             orgb" in answered.stdout
    assert (home / "projects" / FAMILY / FAMILY / "family.yaml").is_file()


def test_a_leg_whose_submodule_name_carries_a_space_is_still_reported(home,
                                                                       tmp_path):
    """`.gitmodules` is read with `git config -z`: a submodule NAME with a
    space (`[submodule "sp ace"]`) prints as `submodule.sp ace.path spec` in
    the plain form, and splitting that at its first space handed back
    `ace.path spec` — a path that does not exist — so the leg was silently
    left out of the not-carried report. A valueless key beside it prints
    bare and is not a path either."""
    projects = home / "projects"
    root = probe_project(projects, "Atlas")
    git("init", "-q", "-b", "main", ".", cwd=root)
    leg_seed = tmp_path / "leg-seed"
    leg_seed.mkdir()
    (leg_seed / "spec.md").write_text("# spec\n", encoding="utf-8")
    git("init", "-q", "-b", "main", ".", cwd=leg_seed)
    commit_all(leg_seed, "the leg")
    leg_bare = tmp_path / "leg.git"
    git("clone", "-q", "--bare", str(leg_seed), str(leg_bare), cwd=tmp_path)
    git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
        "--name", "sp ace", str(leg_bare), "spec", cwd=root)
    with (root / ".gitmodules").open("a", encoding="utf-8") as handle:
        handle.write('[submodule "empty"]\n\tpath\n')
    commit_all(root, "the leg, pinned, under a spaced name")
    (root / "spec" / "more.md").write_text("unpushed\n", encoding="utf-8")
    commit_all(root / "spec", "an unpushed leg commit")

    result = run(PARK, "Atlas", home=home)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"unpushed main   leg     {root / 'spec'}" in result.stdout, (
        "the leg under the spaced submodule name was left out of the report")
    assert "ace.path" not in result.stdout
    assert "submodule.empty.path" not in result.stdout


# --- F5: --repo takes any spelling -----------------------------------------

REPO_FLAG_SPELLINGS = [
    "TestOrg/Atlas",
    "TestOrg/Atlas.git",
    "TestOrg/Atlas/",
    "https://github.com/TestOrg/Atlas.git",
    "git@github.com:TestOrg/Atlas.git",
]


@pytest.mark.parametrize("spelling", REPO_FLAG_SPELLINGS)
def test_repo_accepts_any_spelling_of_the_repository(home, spelling):
    """A person pastes what they have: the slug, the slug with `.git`, or the
    whole url out of the browser. All of them are the same repository, and the
    flag goes through the same parser that reads a clone's `origin`."""
    projects = home / "projects"
    root = probe_project(projects, "Atlas")
    git("init", "-q", "-b", "main", ".", cwd=root)
    git("remote", "add", "origin", "https://github.com/TestOrg/Atlas.git",
        cwd=root)
    result = run(PARK, "--repo", spelling, home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {root}" in result.stdout


@pytest.mark.parametrize("spelling", REPO_FLAG_SPELLINGS)
def test_the_no_match_refusal_prints_one_clone_url_not_two(home, spelling):
    """The refusal used to wrap `https://github.com/` around whatever it was
    handed, so a url spelling produced
    `git clone https://github.com/https://github.com/…git.git`."""
    result = run(PARK, "--repo", spelling, home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert ("git clone --recurse-submodules "
            "https://github.com/TestOrg/Atlas.git") in result.stderr
    assert "github.com/https://" not in result.stderr


# --- F6: the walk-up skips a pinned copy and a linked worktree -------------

def test_the_walk_up_skips_the_holders_pinned_member_copy(estate, home):
    """`members/<Project>` is a whole `project.yaml` root, and it is DETACHED
    and pinned: running a write verb there acts on the wrong copy of the
    member, on a HEAD nobody is working from. The walk-up passes it and
    reaches the family folder, which is what the person is in."""
    pinned = estate["holder"] / "members" / "Alpha"
    assert (pinned / "project.yaml").is_file(), "fixture: the pinned copy is a root"
    result = run(PARK, home=home, cwd=pinned)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"the family holder at {estate['holder']}" in result.stdout
    assert f"the assembly root at {pinned}" not in result.stdout


def test_the_walk_up_skips_a_linked_worktree(home):
    """A single-repository project's FEATURE worktree is a full checkout with
    the whole `project.yaml` in it, so the walk-up used to answer
    `<worktree_root>/001-a-feature` as an estate named after the branch — and
    `park` ran the write verb inside the very worktree the extension parks."""
    projects = home / "projects"
    root = probe_project(projects, "Atlas")
    git("init", "-q", "-b", "main", ".", cwd=root)
    commit_all(root, "the project")
    worktree = root / "worktrees" / "001-a-feature"
    git("worktree", "add", "-q", "-b", "001-a-feature", str(worktree), cwd=root)
    assert (worktree / "project.yaml").is_file(), "fixture: a full checkout"

    result = run(PARK, home=home, cwd=worktree)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {root} " in result.stdout
    assert str(worktree) not in result.stdout


def test_a_pinned_copy_is_not_listed_as_an_estate(estate, home):
    """The same rule in the refusal's own list: `members/<Project>` is not
    somewhere anybody can park."""
    result = run(PARK, "Nope", home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"family   {FAMILY}" in result.stderr
    assert "members/" not in result.stderr


# --- F1: a refused holder is never bootstrapped ----------------------------

def test_a_dirty_holder_is_refused_and_its_bootstrap_never_runs(behind, home,
                                                                remotes):
    """THE ONE THAT LOSES WORK. The holder's `make bootstrap` is `git
    submodule update --init --recursive`, which snaps every `members/<X>` back
    to the recorded gitlink. Running it after a refusal printed "nothing was
    reset" discarded exactly the pin bump the refusal was protecting: a
    half-finished `family.py bump` lives as a MOVED GITLINK in the holder's
    index, and that is what the submodule update throws away.
    """
    holder = behind["holder"]
    pinned = holder / "members" / "Alpha"
    # A pin bump in progress: the member's pinned copy moved to a new commit
    # and the gitlink staged, exactly as `family.py bump` leaves it mid-flight.
    (pinned / "BUMPED.md").write_text("the member moved on\n", encoding="utf-8")
    commit_all(pinned, "a commit the family is about to pin")
    bumped = git("rev-parse", "HEAD", cwd=pinned).stdout.strip()
    git("add", "--", "members/Alpha", cwd=holder)
    (holder / "SCRATCH.md").write_text("half a bump\n", encoding="utf-8")
    staged = git("rev-parse", ":members/Alpha", cwd=holder).stdout.strip()
    assert staged == bumped, "fixture: the gitlink is staged at the new commit"

    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"REFUSED holder {FAMILY}: uncommitted changes in {holder}" \
        in result.stdout
    assert "bootstrap skipped: refused above" in result.stdout
    assert "Nothing here was fetched, moved or reset." in result.stdout
    assert git("rev-parse", ":members/Alpha",
               cwd=holder).stdout.strip() == bumped, (
        "the staged gitlink was reset — the pin bump is gone")
    assert git("rev-parse", "HEAD", cwd=pinned).stdout.strip() == bumped, (
        "the pinned copy was snapped back to the old gitlink")


def test_a_holder_on_a_feature_branch_is_refused_and_not_bootstrapped(behind,
                                                                      home,
                                                                      remotes):
    holder = behind["holder"]
    git("checkout", "-q", "-b", "pin-bump/alpha", cwd=holder)
    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"REFUSED holder {FAMILY}: HEAD is 'pin-bump/alpha'" in result.stdout
    assert "bootstrap skipped: refused above" in result.stdout
    assert git("rev-parse", "--abbrev-ref",
               "HEAD", cwd=holder).stdout.strip() == "pin-bump/alpha"


# --- F3: a leg off its tracking branch refuses the root --------------------

@pytest.fixture
def legged(remotes, home) -> dict:
    """The leg-bearing project, cloned, with a config that names its record."""
    config = home / ".agents" / "workspace.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("repository: tester/legged\npath: ~/projects/legged\n",
                      encoding="utf-8")
    git("clone", "-q", str(remotes["legged"]),
        str(home / "projects" / "legged"), cwd=home)
    root = home / "projects" / LEG_MEMBER
    git("-c", "protocol.file.allow=always", "clone", "-q",
        "--recurse-submodules", str(remotes["leg_member"]), str(root),
        cwd=home / "projects")
    return {"root": root, "leg": root / "spec"}


def test_a_leg_on_a_feature_branch_refuses_the_root_and_is_not_moved(legged,
                                                                     home,
                                                                     remotes):
    """The superproject is CLEAN when a leg sits on a clean feature branch at
    the pin, so the dirty and off-branch guards see nothing — and the root's
    own `make bootstrap` then walks that leg back onto `main`, because
    `checkout_tracking_branch` runs `git checkout <tracking>` whenever the
    leg's branch tip equals the pin. The leg is asked FIRST now.
    """
    leg = legged["leg"]
    git("checkout", "-q", "-b", "001-my-feature", cwd=leg)
    head = git("rev-parse", "HEAD", cwd=leg).stdout.strip()
    assert git("status", "--porcelain", cwd=legged["root"]).stdout == "", (
        "fixture: the superproject is clean, which is the whole point")

    result = run(RESUME, LEG_MEMBER, home=home, env=offline(remotes))
    assert result.returncode == 1, result.stdout + result.stderr
    assert (f"REFUSED root {LEG_MEMBER}: leg spec is on '001-my-feature', "
            "not its tracking branch 'main'") in result.stdout
    assert "`make bootstrap` would move it - nothing was touched." \
        in result.stdout
    assert git("rev-parse", "--abbrev-ref",
               "HEAD", cwd=leg).stdout.strip() == "001-my-feature", (
        "the leg was walked off its feature branch")
    assert git("rev-parse", "HEAD", cwd=leg).stdout.strip() == head
    assert f"{LEG_MEMBER}.sh ran with:" not in result.stdout, (
        "a refused root does not get the verb either")


def test_the_real_bootstrap_would_have_moved_that_leg(legged):
    """THE GUARD IS NOT THEATRE. The same fixture, with the guard bypassed:
    the member's OWN `scripts/bootstrap.py` — the real one, shipped in
    `templates/assembly-root/` and copied into this seed — moves the leg off
    its feature branch. That is what `resume` refuses to cause.
    """
    leg = legged["leg"]
    git("checkout", "-q", "-b", "001-my-feature", cwd=leg)
    proc = subprocess.run([sys.executable, "scripts/bootstrap.py"],
                          cwd=str(legged["root"]), capture_output=True,
                          text=True, check=False)
    assert git("rev-parse", "--abbrev-ref",
               "HEAD", cwd=leg).stdout.strip() == "main", (
        "the premise of the guard is gone: bootstrap no longer moves a leg\n"
        + proc.stdout + proc.stderr)


def test_a_leg_detached_at_the_pin_is_not_a_refusal(legged, home, remotes):
    """The state a fresh clone arrives in, and precisely what bootstrap
    exists to fix. Refusing it would refuse every first run."""
    leg = legged["leg"]
    git("checkout", "-q", "--detach", cwd=leg)
    result = run(RESUME, LEG_MEMBER, home=home, env=offline(remotes))
    assert "not its tracking branch" not in result.stdout, (
        result.stdout + result.stderr)
    assert f"{LEG_MEMBER}.sh ran with:" in result.stdout


# --- F4: two checkouts of one workspace are not two orgs -------------------

def test_two_checkouts_of_one_workspace_are_not_two_orgs(remotes, home):
    """`FOUND` counted FILES. An `orgs:` override pointing at a second clone of
    the same private repository — or just a second checkout of it — produced
    "2 workspace manifests record 'TestFam'", and `--org` could not answer it
    because both rows named the same org."""
    config = home / ".agents" / "workspace.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        f"repository: {WORKSPACE_SLUG}\npath: ~/projects/wip\n"
        "orgs:\n"
        f"  {ORG}:\n"
        f"    repository: {WORKSPACE_SLUG}\n"
        "    path: ~/projects/wip-again\n", encoding="utf-8")
    for name in ("wip", "wip-again"):
        git("clone", "-q", str(remotes["workspace"]),
            str(home / "projects" / name), cwd=home)

    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "workspace manifests record" not in result.stderr
    assert (home / "projects" / FAMILY / FAMILY / "family.yaml").is_file()


def test_two_checkouts_that_spell_the_manifest_differently_are_one_record(
        remotes, home):
    """`manifest_candidates` compares the basename CASE-INSENSITIVELY, so the
    key that decides whether two rows are two records has to fold it too:
    `testfam.yaml` in one checkout and `TestFam.yaml` in another are one
    record of one org. Keyed on the raw basename they were two, and `resume`
    refused with `--org` for an answer — naming the same org twice."""
    config = home / ".agents" / "workspace.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        f"repository: {WORKSPACE_SLUG}\npath: ~/projects/wip\n"
        "orgs:\n"
        f"  {ORG}:\n"
        f"    repository: {WORKSPACE_SLUG}\n"
        "    path: ~/projects/wip-again\n", encoding="utf-8")
    for name in ("wip", "wip-again"):
        git("clone", "-q", str(remotes["workspace"]),
            str(home / "projects" / name), cwd=home)
    spelt = (home / "projects" / "wip-again" / "workspaces" / ORG
             / f"{FAMILY.lower()}.yaml")
    spelt.rename(spelt.with_name(f"{FAMILY}.yaml"))

    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "workspace manifests record" not in result.stderr
    assert (home / "projects" / FAMILY / FAMILY / "family.yaml").is_file()


# --- F7: a `root:` that walks out of the projects directory ----------------

def test_a_manifest_root_that_escapes_the_projects_directory_is_refused(
        remotes, home):
    config = home / ".agents" / "workspace.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("repository: tester/escaping\npath: ~/projects/escaping\n",
                      encoding="utf-8")
    result = run(RESUME, "runaway", home=home, env=offline(remotes))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "root: ../../elsewhere/Alpha" in result.stderr
    assert "is not one" in result.stderr
    assert "Nothing was cloned." in result.stderr
    assert not (home.parent / "elsewhere").exists()
    assert not (home / "projects" / ".." ).joinpath("elsewhere").exists()


# --- F9: a refused member does not get the verb either ---------------------

def test_a_refused_member_does_not_get_the_verb(behind, home, remotes):
    """The holder's `make resume` is `siblings.py --make resume`, which has no
    exclusion flag — so a member this run said it would not touch was getting
    the verb run in it anyway. With a refusal on the board the verb runs per
    non-refused sibling instead."""
    alpha = behind["siblings"]["Alpha"]
    (alpha / "MINE.md").write_text("half a thought\n", encoding="utf-8")

    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "the holder's dispatch is NOT used" in result.stdout
    assert "[Alpha] refused above; `make resume` NOT run." in result.stdout
    assert "Alpha.sh ran with:" not in result.stdout, (
        "the verb ran in a clone this run refused to touch")
    assert "Bravo.sh ran with:" in result.stdout, (
        "one refusal must not stop the members after it")


# ===========================================================================
# resume — the estate that is already here
# ===========================================================================

@pytest.fixture
def behind(estate, home, remotes) -> dict:
    """The estate, one commit behind on the holder and on every sibling.

    `reset --hard HEAD~1` rather than a push to the shared bare remotes: the
    remotes are built once per session, and a test that moved one would decide
    what the next test sees.
    """
    config = home / ".agents" / "workspace.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(f"repository: {WORKSPACE_SLUG}\npath: ~/projects/wip\n",
                      encoding="utf-8")
    git("clone", "-q", str(remotes["workspace"]),
        str(home / "projects" / "wip"), cwd=home)
    for path in (estate["holder"], *estate["siblings"].values()):
        git("reset", "--hard", "-q", "HEAD~1", cwd=path)
    return estate


def test_resume_fast_forwards_the_holder_and_every_sibling(behind, home,
                                                           remotes):
    """RULING 2: a person running `resume` is asking for the estate to be
    current, so each working clone's tracking branch is fast-forwarded — and
    each one's own `make bootstrap` puts its legs at the new pins."""
    heads = {name: git("rev-parse", "HEAD", cwd=path).stdout.strip()
             for name, path in behind["siblings"].items()}
    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    for name, path in behind["siblings"].items():
        assert git("rev-parse", "HEAD", cwd=path).stdout.strip() != heads[name], (
            f"{name} was not fast-forwarded")
        assert git("rev-parse", "HEAD", cwd=path).stdout.strip() == git(
            "rev-parse", "origin/main", cwd=path).stdout.strip()
        assert f"BOOTSTRAP-{name} ran" in result.stdout
    assert "present         " in result.stdout
    assert "0 refusal(s)" in result.stdout


def test_resume_refuses_a_dirty_sibling_by_name_and_resumes_the_rest(
        behind, home, remotes):
    """RULING 2's other half. Never reset, never stashed, and named — and the
    rest of the estate still comes back."""
    alpha = behind["siblings"]["Alpha"]
    (alpha / "MINE.md").write_text("half a thought\n", encoding="utf-8")
    head = git("rev-parse", "HEAD", cwd=alpha).stdout.strip()

    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"REFUSED Alpha: uncommitted changes in {alpha}" in result.stdout
    assert "nothing was reset" in result.stdout
    assert git("rev-parse", "HEAD", cwd=alpha).stdout.strip() == head, (
        "a refused sibling must be exactly where it was")
    assert (alpha / "MINE.md").is_file(), "nothing may be discarded"
    bravo = behind["siblings"]["Bravo"]
    assert git("rev-parse", "HEAD", cwd=bravo).stdout.strip() == git(
        "rev-parse", "origin/main", cwd=bravo).stdout.strip()
    assert "Bravo.sh ran with:" in result.stdout, (
        "one refusal must not stop the members after it")
    assert "1 refusal(s)" in result.stdout


def test_resume_refuses_a_sibling_on_a_feature_branch_by_name(behind, home,
                                                              remotes):
    bravo = behind["siblings"]["Bravo"]
    git("checkout", "-q", "-b", "001-a-feature", cwd=bravo)
    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "REFUSED Bravo: HEAD is '001-a-feature', not its tracking branch " \
        "'main'" in result.stdout
    assert git("rev-parse", "--abbrev-ref",
               "HEAD", cwd=bravo).stdout.strip() == "001-a-feature"
    assert "Alpha.sh ran with:" in result.stdout


def test_resume_skips_a_member_with_no_working_clone_by_name(behind, home,
                                                            remotes):
    """A skip is not a pass — and `make siblings` is what places one, which is
    exactly what this run does before it reports."""
    rmtree(behind["siblings"]["Alpha"])
    result = run(RESUME, FAMILY, home=home, env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    assert (behind["folder"] / "Alpha" / ".git").is_dir(), (
        "`make siblings` must have placed the member back")
    assert "Alpha.sh ran with:" in result.stdout


def test_resume_with_no_name_refreshes_the_estate_around_the_cwd(behind, home,
                                                                 remotes):
    result = run(RESUME, home=home, cwd=behind["holder"], env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"resume: {FAMILY}" in result.stdout
    for name, path in behind["siblings"].items():
        assert git("rev-parse", "HEAD", cwd=path).stdout.strip() == git(
            "rev-parse", "origin/main", cwd=path).stdout.strip(), name


def test_resume_with_no_name_and_no_estate_refuses(home):
    result = run(RESUME, home=home, cwd=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no estate around" in result.stderr
    assert "resume <Name>" in result.stderr


def test_resume_refuses_a_repo_it_cannot_match(home):
    result = run(RESUME, "--repo", "TestOrg/Nothing", home=home)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no clone under your projects directory has origin" in result.stderr
    assert "resume <Name>" in result.stderr
