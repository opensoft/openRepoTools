# SPDX-License-Identifier: Apache-2.0
"""`openRepoTools wip init` — the one act that creates the workspace.

lane-collision-protocol Amendment 9(c), under Brett Heap's ruling 4. NO
NETWORK AND NO GITHUB, exactly as the rest of this suite: every run here meets
a fake `gh` first on `$PATH`, backed by BARE REPOSITORIES IN A TEMPORARY
DIRECTORY, so `gh repo create`, `gh repo clone` and the seed's push are all
real git against real refs and none of them is a stub. A test that needed a
real `gh` would be the wrong test.

WHAT EACH SCENARIO IS FOR, since a reader meeting eleven steps at once cannot
tell which ones matter:

* rights present — the whole path, end to end: derive, create, clone, seed,
  substitute, push, write the pointer file, link. The push IS the ruleset
  probe, so a test that stops before it has not tested the thing the amendment
  added it for.
* rights ABSENT — ruling 2. It prints the administrator's block with every
  value already substituted and stops at exit 2, having created nothing. The
  block is three acts, not two: Addendum 1(2) on brettheap/new-workstation#17.
* a workstation that already has one — step 1's whole idempotence, which is a
  file test and not a network call.
* a pointer file naming a repository its path is NOT a checkout of — the
  refusal Amendment 9(a) calls new behaviour in so many words: "nothing
  validates it today ... so a `path:` pointing at some other repository is
  currently accepted and after this is not."
* teams 0, 1 and 2 — ratified decision 2, derive or omit, never a placeholder.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

COMMAND = REPO / "openRepoTools"
TEMPLATE = REPO / "upstream" / "openRepoShape" / "templates" / "workspace-root"

#: The nine template files, which are clause (d)'s list and `openRepoTools`'
#: own `WIP_TEMPLATE_FILES`. Named here rather than globbed, for the reason the
#: command names them rather than listing a directory at runtime: the set is a
#: published contract, not whatever upstream happens to hold.
TEMPLATE_FILES = ("README.md", "AGENTS.md", "CLAUDE.md", ".gitattributes",
                  ".gitignore", "handoffs/README.md", "lanes/LANES.md",
                  "lanes/log/README.md", "workspaces/.gitkeep")

NEEDS_TEMPLATE = pytest.mark.skipif(
    not (TEMPLATE / "README.md").is_file(),
    reason="the pinned openRepoShape is not checked out; "
           "run `git submodule update --init upstream/openRepoShape`")

pytestmark = [WINDOWS_SKIP, NEEDS_TEMPLATE]


def fake_gh(tmp_path: Path, *, login: str = "brettheap",
            teams: tuple[str, ...] = ("platform",),
            may_create: bool = True,
            exists: bool = False,
            refuse_push: bool = False) -> dict:
    """A `gh` that answers the five calls `wip init` makes, and refuses the rest.

    `repo create` makes a BARE repository under `<tmp>/github/<org>/<name>.git`
    and `repo clone` clones it, so the seed commit and its push are real git
    against a real ref — which is the only way the ruleset-probe branch can be
    exercised at all. `may_create=False` is the account without the right, and
    `exists=True` is the administrator having already run the block.

    `refuse_push=True` IS THE ORGANISATION'S PR-ONLY RULESET, and it is a real
    `pre-receive` hook in the bare repository rather than a stubbed exit code:
    clause (c) step 8 makes the seed's push the probe for that gate, so a test
    that faked the rejection would be testing the fake. The hook refuses while
    a marker file sits beside it; deleting that marker is the administrator
    excluding the repository, and the re-run afterwards is the path step 8
    promises has "only to push".
    """
    server = tmp_path / "github"
    server.mkdir(parents=True, exist_ok=True)
    teams_json = "\n".join(
        '{"slug":"%s","organization":{"login":"opensoft"}}' % t for t in teams)
    ruleset_call = 'install_ruleset "$(slug_path "$target")"' if refuse_push else ":"
    fake = tmp_path / "fake-path"
    fake.mkdir(exist_ok=True)
    (fake / "gh").write_text(textwrap.dedent(f"""\
        #!/usr/bin/env bash
        set -u
        server={server!s}
        slug_path() {{ printf '%s\\n' "$server/$1.git"; }}
        # THE ORGANISATION'S PR-ONLY RULESET, as a real pre-receive hook: it
        # refuses every push while `ruleset-on` sits in the bare repository,
        # which is the state a NEW repository is in until an administrator
        # excludes it (clause (c) step 8, Addendum 1(2)).
        install_ruleset() {{
            d="$1"
            : > "$d/ruleset-on"
            {{
                printf '%s\\n' '#!/bin/sh'
                printf '%s\\n' '[ -e "$(dirname "$0")/../ruleset-on" ] || exit 0'
                printf '%s\\n' 'echo "remote: refused by the PR-only ruleset" >&2'
                printf '%s\\n' 'exit 1'
            }} > "$d/hooks/pre-receive"
            chmod 755 "$d/hooks/pre-receive"
        }}
        case "$1 ${{2-}}" in
        "api user")
            printf '%s\\n' "{login}"; exit 0 ;;
        "api --paginate")
            # /user/teams, read with -q; the fake answers the filter's input.
            printf '%s\\n' {"'" + (teams_json or "") + "'"} \\
                | sed -n 's/.*"slug":"\\([^"]*\\)".*/\\1/p'
            exit 0 ;;
        esac
        case "$*" in
        "repo view "*)
            target="$3"
            [ -d "$(slug_path "$target")" ] && exit 0
            exit 1 ;;
        "repo create "*)
            {"" if may_create else "printf 'GraphQL: Resource not accessible by personal access token\\n' >&2; exit 1;"}
            target="$3"
            mkdir -p -- "$(dirname -- "$(slug_path "$target")")"
            git init -q --bare -b main "$(slug_path "$target")"
            {ruleset_call}
            exit 0 ;;
        "repo clone "*)
            target="$3"; dest="$4"
            git clone -q "$(slug_path "$target")" "$dest" || exit 1
            git -C "$dest" config user.email wip@example.invalid
            git -C "$dest" config user.name "wip init tests"
            exit 0 ;;
        "api --method PUT"*) exit 0 ;;
        *"/contents/"*)
            path="${{*}}"
            path="${{path##*/contents/}}"; path="${{path%%\\?*}}"
            src="{REPO!s}/upstream/openRepoShape/$path"
            [ -f "$src" ] && exec cat -- "$src"
            src="{REPO!s}/$path"
            [ -f "$src" ] && exec cat -- "$src"
            exit 1 ;;
        esac
        printf 'fake gh: unexpected call: %s\\n' "$*" >&2
        exit 1
        """), encoding="utf-8")
    (fake / "gh").chmod(0o755)
    (fake / "curl").write_text(
        "#!/bin/sh\nprintf 'no test here may reach the network\\n' >&2\nexit 1\n",
        encoding="utf-8")
    (fake / "curl").chmod(0o755)
    if exists:
        d = server / "opensoft" / f"{login}-wip.git"
        d.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(d)],
                       check=True)
    return {"PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"}


def wip_env(home: Path, extra: dict) -> dict:
    environ = dict(os.environ)
    for name in ("OPENREPOTOOLS_REF", "OPENREPOTOOLS_REPO",
                 "OPENREPOTOOLS_BIN_DIR", "CLAUDE_PROFILES_HOME",
                 "CLAUDE_USER_DIR", "AGENT_PROTOCOL_ROOT", "PROJECTS_DIR",
                 "OPENREPOTOOLS_WIP_ORG"):
        environ.pop(name, None)
    environ["HOME"] = str(home)
    environ["AGENT_PROTOCOL_ROOT"] = str(home / ".agents")
    environ["PROJECTS_DIR"] = str(home / "projects")
    environ["OPENREPOTOOLS_BIN_DIR"] = str(home / "bin")
    environ["GIT_AUTHOR_NAME"] = environ["GIT_COMMITTER_NAME"] = "wip tests"
    environ["GIT_AUTHOR_EMAIL"] = environ["GIT_COMMITTER_EMAIL"] = \
        "wip@example.invalid"
    environ.update(extra)
    return environ


def run_wip(home: Path, *args: str, extra: dict | None = None,
            stdin: str = "") -> subprocess.CompletedProcess:
    (home / "projects").mkdir(parents=True, exist_ok=True)
    return subprocess.run(["bash", str(COMMAND), "wip", "init", *args],
                          capture_output=True, text=True, check=False,
                          input=stdin, cwd=str(REPO),
                          env=wip_env(home, extra or {}))


# --- the whole path, where the person may create the repository -------------

def test_wip_init_creates_clones_seeds_pushes_and_points_at_it(tmp_path):
    """Steps 2 to 10 in one run, and every one of them checked.

    The seed is checked for its SUBSTITUTED bytes rather than its presence: a
    template written with `{{LOGIN}}` still in it is the failure clause (c)
    step 7 refuses by name, and a file that is merely there proves nothing
    about that.
    """
    home = tmp_path / "home"
    result = run_wip(home, extra=fake_gh(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr

    checkout = home / "projects" / "brettheap-wip"
    for rel in TEMPLATE_FILES:
        assert (checkout / rel).is_file(), f"{rel}\n{result.stdout}"
    readme = (checkout / "README.md").read_text(encoding="utf-8")
    assert "{{" not in readme, "a placeholder was written into the repository"
    assert "brettheap" in readme
    assert "opensoft" in readme

    # The pointer file, which is the whole of what a later run reads.
    config = home / ".agents" / "workspace.yaml"
    assert config.is_file(), result.stdout
    text = config.read_text(encoding="utf-8")
    assert "repository: opensoft/brettheap-wip" in text
    assert "path: ~/projects/brettheap-wip" in text, (
        "the path is written with a `~` where it is under $HOME, so the file "
        "travels with the thing it points at")

    # THE PUSH IS THE RULESET PROBE, so the seed has to be on the remote.
    remote = subprocess.run(
        ["git", "-C", str(checkout), "ls-remote", "origin", "main"],
        capture_output=True, text=True, check=True)
    assert remote.stdout.strip(), "the seed never landed on main"
    assert "pushed the seed" in result.stdout

    assert "pclaude run <profile> --lane <repo>-<n>" in result.stdout


def test_wip_init_is_idempotent_and_a_second_run_writes_nothing(tmp_path):
    """Step 1: a file test, not a network call, and the whole of the
    idempotence. `setup.sh` runs this on every host on every run, so a second
    run that did anything at all would do it on every machine, every time."""
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    assert run_wip(home, extra=env).returncode == 0
    config = home / ".agents" / "workspace.yaml"
    before = config.read_bytes()
    mtime = config.stat().st_mtime

    second = run_wip(home, extra=env)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "nothing to do" in second.stdout
    assert config.read_bytes() == before
    assert config.stat().st_mtime == mtime


def test_dry_run_rehearses_and_writes_nothing(tmp_path):
    home = tmp_path / "home"
    result = run_wip(home, "--dry-run", extra=fake_gh(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--dry-run, so nothing below was done" in result.stdout
    assert not (home / ".agents" / "workspace.yaml").exists()
    assert not (home / "projects" / "brettheap-wip").exists()


# --- ruling 2: where the person may NOT create it ---------------------------

def test_without_the_right_it_prints_the_administrators_three_acts(tmp_path):
    """RULING 2, verbatim "print the command" — and THREE acts, not two.

    Every value is already substituted, so what is printed runs as it stands:
    a block with a `<org>` left in it is a placeholder a person must fill,
    which is a question wearing a different hat (R-A9-3).

    Exit 2 and NOT 1: 1 in this toolset means "findings were printed".
    """
    home = tmp_path / "home"
    result = run_wip(home, extra=fake_gh(tmp_path, may_create=False))
    assert result.returncode == 2, result.stdout + result.stderr
    out = result.stdout + result.stderr
    assert "gh repo create opensoft/brettheap-wip --private --team platform" in out
    assert "/orgs/opensoft/teams/platform/repos/opensoft/brettheap-wip" in out
    assert "gh api /orgs/opensoft/rulesets" in out, (
        "the third administrator act — without the ruleset exclusion, Rule 9's "
        "one commit per write cannot land and the register is unwritable")
    assert "{{" not in out and "<org>" not in out and "<login>" not in out
    assert not (home / ".agents" / "workspace.yaml").exists()
    assert not (home / "projects" / "brettheap-wip").exists()


def test_with_no_terminal_it_does_not_wait_on_a_person(tmp_path):
    """An unattended launch — `setup.sh` under CI, a container build — must not
    block on a person. Where stdin is not a terminal it does not ask at all."""
    home = tmp_path / "home"
    result = run_wip(home, extra=fake_gh(tmp_path, may_create=False))
    assert result.returncode == 2
    assert "no terminal to wait on" in result.stderr


def test_it_adopts_a_repository_an_administrator_already_created(tmp_path):
    """The other half of ruling 2: once the repository exists, a re-run picks
    up from there. That is what makes the printed block a step in a sequence
    rather than a dead end."""
    home = tmp_path / "home"
    result = run_wip(home, extra=fake_gh(tmp_path, may_create=False, exists=True))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "already there; this run adopts it" in result.stdout
    assert (home / ".agents" / "workspace.yaml").is_file()


# --- ratified decision 2: derive the team, or drop it ----------------------

def test_one_matching_team_is_used(tmp_path):
    home = tmp_path / "home"
    result = run_wip(home, extra=fake_gh(tmp_path, teams=("platform",)))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "team                platform (the one team you are in there)" \
        in result.stdout


@pytest.mark.parametrize("teams,why", [
    ((), "you are in no team"),
    (("platform", "infra"), "you are in 2 teams"),
])
def test_no_single_team_drops_the_flag_entirely_and_says_why(tmp_path, teams, why):
    """NOT a placeholder, and not a question: the flag is omitted from what is
    run AND from what is printed, with one line saying why. (Ratified
    decision 2.)"""
    home = tmp_path / "home"
    result = run_wip(home, extra=fake_gh(tmp_path, teams=teams, may_create=False))
    out = result.stdout + result.stderr
    assert why in out, out
    assert "--team" not in out.split("openRepoTools wip init")[0] or \
        "--team platform" not in out
    assert "gh repo create opensoft/brettheap-wip --private \\" in out
    assert "teams/" not in out, (
        "a team grant for a team that was not derived is a command that fails")


# --- the refusals -----------------------------------------------------------

def test_a_login_that_cannot_form_a_compliant_name_is_refused(tmp_path):
    """openRepoShape's naming contract, named with its source. A name repaired
    by guesswork is a repository nobody can find again."""
    home = tmp_path / "home"
    result = run_wip(home, extra=fake_gh(tmp_path, login="bad_login"))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "cannot form a compliant" in result.stderr
    assert "^[a-z0-9]+(-[a-z0-9]+)*-wip$" in result.stderr


def test_a_pointer_file_whose_path_is_another_repository_is_refused(tmp_path):
    """THE CHECKOUT TEST IS NEW BEHAVIOUR and Amendment 9(a) says so: nothing
    validated it before, so a `path:` pointing at some other repository was
    accepted and after this is not. It is a refusal rather than an overwrite,
    because which private repository holds a person's unfinished work is
    theirs to name."""
    home = tmp_path / "home"
    other = home / "projects" / "somebody-elses"
    other.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(other)], check=True)
    subprocess.run(["git", "-C", str(other), "remote", "add", "origin",
                    "https://github.com/opensoft/not-your-wip.git"], check=True)
    (home / ".agents").mkdir(parents=True)
    (home / ".agents" / "workspace.yaml").write_text(
        f"repository: opensoft/brettheap-wip\npath: {other}\n", encoding="utf-8")

    result = run_wip(home, extra=fake_gh(tmp_path))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "is not the root of a checkout of it" in result.stderr
    assert "never overwrites that file" in result.stderr


def test_an_existing_checkout_of_another_repository_is_refused(tmp_path):
    """A clone already sitting where the workspace would go, of something
    else. It is neither written into nor moved aside: moving somebody's
    checkout is not an installer's to do."""
    home = tmp_path / "home"
    squatter = home / "projects" / "brettheap-wip"
    squatter.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(squatter)], check=True)
    subprocess.run(["git", "-C", str(squatter), "remote", "add", "origin",
                    "https://github.com/opensoft/something-else.git"], check=True)
    marker = squatter / "KEEP.md"
    marker.write_text("somebody's work\n", encoding="utf-8")

    result = run_wip(home, extra=fake_gh(tmp_path, exists=True))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "already a checkout, and not of opensoft/brettheap-wip" in result.stderr
    assert marker.read_text(encoding="utf-8") == "somebody's work\n"
    assert not (home / ".agents" / "workspace.yaml").exists()


# --- step 8: the push IS the ruleset probe, and the re-run has only to push --

def remote_main(tmp_path: Path, slug: str = "opensoft/brettheap-wip") -> str:
    """What `<slug>`'s bare `main` actually points at, or "" for no such ref.

    Read from the BARE repository rather than from the clone, because the whole
    question step 8 asks is whether anything landed on the REMOTE.
    """
    bare = tmp_path / "github" / f"{slug}.git"
    done = subprocess.run(["git", "-C", str(bare), "rev-parse", "main"],
                          capture_output=True, text=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else ""


def test_a_push_the_ruleset_refuses_is_exit_2_and_leaves_the_seed_in_place(tmp_path):
    """CLAUSE (c) STEP 8, and the reason the amendment added it.

    A newly created repository is inside the organisation's PR-only ruleset
    until an administrator excludes it, and until it is, Rule 9's one commit
    per write cannot land — so the register would be unwritable. An earlier
    draft of the clause said `wip init` "names that in its output and cannot do
    it itself", and the amendment rejected that in so many words: it "let a
    person finish successfully and meet the failure at their first register
    write, which is the worst place there is to meet it."

    So: exit 2, the refusal names the PR-only ruleset and step 5's third act,
    and the clone and the seed commit are LEFT EXACTLY WHERE THEY ARE — which
    is what the next test spends.

    THE POINTER FILE IS NOT WRITTEN. It is step 9, after this, and writing it
    here would make step 1's file test return on every later run, which is the
    one state no re-run can dig out of.
    """
    home = tmp_path / "home"
    result = run_wip(home, extra=fake_gh(tmp_path, refuse_push=True))

    assert result.returncode == 2, result.stdout + result.stderr
    assert "THAT IS THE RULESET" in result.stderr
    assert "PR-only ruleset" in result.stderr
    assert "gh api /orgs/opensoft/rulesets" in result.stderr
    assert "openRepoTools wip init" in result.stderr

    assert remote_main(tmp_path) == "", "the seed reached main through the gate"
    checkout = home / "projects" / "brettheap-wip"
    assert (checkout / "lanes" / "LANES.md").is_file(), (
        "the clone and the seed were not left in place for the re-run")
    head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True)
    assert head.stdout.strip(), "the seed was not committed"
    assert not (home / ".agents" / "workspace.yaml").exists(), (
        "the pointer file was written over a push that never landed, so step "
        "1 would return on every later run and no re-run could fix it")


def test_the_rerun_after_the_administrator_acts_has_only_to_push(tmp_path):
    """THE OTHER HALF OF STEP 8, and the half that is easy to lose.

    The first run committed the seed and was refused by the gate, so the
    worktree is CLEAN and the commit is unpushed. A push gated on
    `git status --porcelain` — on the WORKTREE — therefore finds nothing to do,
    prints "already carries the seed", writes the pointer file and exits 0 over
    an empty `main`; and step 1's file test then returns on every later run, so
    the command can never repair it. The gate is the REMOTE for that reason.

    Deleting the marker is the administrator adding the repository to the
    ruleset's exempt list. Nothing else changes, and the amendment's promise is
    that the re-run "has only to push".
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path, refuse_push=True)
    first = run_wip(home, extra=env)
    assert first.returncode == 2, first.stdout + first.stderr
    checkout = home / "projects" / "brettheap-wip"
    seed = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()

    # The administrator excludes it from the PR-only ruleset.
    (tmp_path / "github" / "opensoft" / "brettheap-wip.git" / "ruleset-on").unlink()

    second = run_wip(home, extra=env)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "pushed the seed" in second.stdout
    assert remote_main(tmp_path) == seed, (
        "the re-run did not push the commit the first run left behind")
    assert (home / ".agents" / "workspace.yaml").is_file(), (
        "step 9 did not run after the push finally landed")

    # AND IT IS STILL IDEMPOTENT: a third run is step 1's file test.
    third = run_wip(home, extra=env)
    assert third.returncode == 0, third.stdout + third.stderr
    assert "nothing to do" in third.stdout


def test_a_seed_already_on_main_is_not_pushed_again(tmp_path):
    """The other side of the remote gate: where `origin/main` already points at
    this commit there is nothing to push, and saying so is not the same as
    saying there was nothing to commit. A command that pushed anyway would be
    making a network call to learn what it had just read."""
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    first = run_wip(home, extra=env)
    assert first.returncode == 0, first.stdout + first.stderr
    seed = remote_main(tmp_path)
    assert seed, "the first run did not push"

    # A second workstation's view: the pointer file is gone, everything else is
    # exactly as the first run left it.
    (home / ".agents" / "workspace.yaml").unlink()
    second = run_wip(home, extra=env)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "already carries this commit" in second.stdout
    assert remote_main(tmp_path) == seed


# --- one answer to one question, across the seam between two toolsets -------

#: (name, the two yaml lines as a template, whether both sides must ACCEPT).
#: `{origin}` is the bare repository, `{wip}` its clone's root.
WORKSPACE_FIXTURES = (
    ("the root of a checkout of the repository it names",
     "repository: {origin}\npath: {wip}\n", True),
    ("a subdirectory of that checkout rather than its root",
     "repository: {origin}\npath: {wip}/lanes\n", False),
    ("a checkout of some other repository",
     "repository: {origin}\npath: {foreign}\n", False),
    ("a path that is no checkout at all",
     "repository: {origin}\npath: {nowhere}\n", False),
    ("no `repository:` line",
     "path: {wip}\n", False),
    ("no `path:` line",
     "repository: {origin}\n", False),
)


@pytest.mark.parametrize("what,yaml,accepted",
                         WORKSPACE_FIXTURES,
                         ids=[f[0] for f in WORKSPACE_FIXTURES])
def test_wip_init_and_the_lane_helpers_read_one_pointer_file_the_same_way(
        tmp_path, what, yaml, accepted):
    """TWO IMPLEMENTATIONS OF ONE QUESTION, AND THE FILE SAYS THEY MUST AGREE.

    `openRepoTools` carries `wip_config_file`, `wip_yaml_field`,
    `wip_norm_repo` and `wip_is_checkout_of`; the four lane helpers carry
    `lanes_ws_yaml`, `lanes_ws_field`, `lanes_ws_norm` and
    `lanes_workspace_root`. They are separate code because the two toolsets are
    separate files on a PATH — `wip init` cannot source a helper it may be
    running before `--install` has placed, and a helper cannot source the
    installer — and `openRepoTools`' own comment says what that costs: they
    "have to agree on what 'already has a workspace' means, or a host can pass
    one and fail the other."

    That host is the failure this pins. `wip init` accepting means step 1
    returns "nothing to do" and writes nothing ever again; the helpers refusing
    means the register cannot be found. A person in that state has a command
    that says they are set up and four commands that say they are not, and no
    re-run of anything repairs it — which is precisely the shape of defect
    Amendment 9(a) exists to remove, arriving through a different door.

    Six fixtures, one `workspace.yaml` at a time, both sides asked.
    """
    home = tmp_path / "home"
    agents = home / ".agents"
    agents.mkdir(parents=True)
    origin = tmp_path / "origin.git"
    wip = home / "projects" / "brettheap-wip"
    foreign = tmp_path / "foreign"
    nowhere = tmp_path / "nowhere"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)],
                   check=True)
    wip.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(wip)], check=True)
    (wip / "lanes").mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(foreign)], check=True)
    subprocess.run(["git", "-C", str(foreign), "remote", "add", "origin",
                    "https://github.com/opensoft/somebody-else-wip.git"],
                   check=True)

    (agents / "workspace.yaml").write_text(
        yaml.format(origin=origin, wip=wip, foreign=foreign, nowhere=nowhere),
        encoding="utf-8")

    env = wip_env(home, fake_gh(tmp_path))
    tools = run_wip(home)
    helper = subprocess.run(
        ["bash", str(REPO / "lanes-edit.sh"), "who", "--lane", "repoA-1"],
        capture_output=True, text=True, check=False, cwd=str(tmp_path), env=env)
    unfound = "the workspace repository could not be found"

    if accepted:
        assert tools.returncode == 0, tools.stdout + tools.stderr
        assert "nothing to do" in tools.stdout, (
            f"`wip init` did not accept {what}")
        assert unfound not in helper.stderr, (
            f"`wip init` accepted {what} and `lanes-edit.sh` could not find it:\n"
            f"{helper.stderr}")
    else:
        assert tools.returncode == 2, (
            f"`wip init` did not refuse {what}:\n{tools.stdout}{tools.stderr}")
        assert helper.returncode == 1, (
            f"`lanes-edit.sh` did not refuse {what} with exit 1:\n{helper.stderr}")
        assert unfound in helper.stderr, (
            f"`lanes-edit.sh` refused {what} for some other reason:\n{helper.stderr}")
        assert "no reason recorded" not in helper.stderr, (
            "the refusal reached the person without the diagnosis it computed")
