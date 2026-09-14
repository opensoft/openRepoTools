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
            refuse_clone: bool = False,
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
    # A `gh repo clone` that fails the way a fresh machine's does — no
    # credential — and says so on STDERR, which is the whole of F9.
    clone_refusal = (
        '''printf '%s\\n' "fatal: could not read Username for 'https://github.com': terminal prompts disabled" >&2; exit 1;'''
        if refuse_clone else ":")
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
            {clone_refusal}
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


# --- the seed is the template and nothing else (#40, finding 1) -------------

def head_of(checkout: Path) -> str:
    """What `HEAD` points at, or "" in a repository with no commit."""
    done = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else ""


def staged_in(checkout: Path) -> str:
    done = subprocess.run(
        ["git", "-C", str(checkout), "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=False)
    return done.stdout


def adopted_checkout(tmp_path: Path, home: Path, env: dict) -> Path:
    """A workspace repository this workstation ADOPTS: created, seeded and
    pushed by an earlier run, carrying a file of the person's own on `main`,
    and with the pointer file gone so step 1 does not simply return.

    That is the state the finding is about — `wip init` is idempotent and
    `setup.sh` runs it on every host on every run, so the run that meets a
    checkout somebody has been working in is the normal one, not the exotic
    one.
    """
    first = run_wip(home, extra=env)
    assert first.returncode == 0, first.stdout + first.stderr
    checkout = home / "projects" / "brettheap-wip"
    log = checkout / "lanes" / "log" / "openRepoTools-3.md"
    log.write_text("the lane log this workspace already carried\n",
                   encoding="utf-8")
    for args in (["add", "--", "lanes/log/openRepoTools-3.md"],
                 ["commit", "-q", "-m", "a lane's object log"],
                 ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", "-C", str(checkout), *args], check=True)
    (home / ".agents" / "workspace.yaml").unlink()
    return checkout


@pytest.mark.parametrize("state", ["untracked", "modified", "deleted"])
def test_an_adopted_checkout_with_unrelated_changes_is_refused(tmp_path, state):
    """`git add -A -- .` PUBLISHED WHATEVER THE WORKTREE HAPPENED TO CARRY
    (#40, finding 1, P1).

    Step 8 staged every modified, deleted and untracked file in an adopted
    checkout and `push origin HEAD:main` put them on `main` as part of the
    seed. The repository on the other end of that push is the one a person
    keeps their UNFINISHED work in, which is the last place a file should
    arrive by accident.

    The question is asked BEFORE step 7 writes a byte into that checkout, for
    the reason `plan_install_targets` is asked before the fetch: at this point
    a refusal costs nothing at all, and the person's own files are still
    exactly where they left them when they read it.

    All three shapes `status --porcelain` reports, because `-A` swept up all
    three.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    checkout = adopted_checkout(tmp_path, home, env)
    head = head_of(checkout)
    log = checkout / "lanes" / "log" / "openRepoTools-3.md"
    if state == "untracked":
        (checkout / "notes.md").write_text("unfinished\n", encoding="utf-8")
        named = "notes.md"
    elif state == "modified":
        log.write_text("edited, and not committed\n", encoding="utf-8")
        named = "lanes/log/openRepoTools-3.md"
    else:
        log.unlink()
        named = "lanes/log/openRepoTools-3.md"

    result = run_wip(home, extra=env)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "carries changes this command did not write" in result.stderr
    assert named in result.stderr, result.stderr
    assert "NOTHING was written" in result.stderr and \
        "nothing was staged" in result.stderr, result.stderr
    assert staged_in(checkout) == "", (
        f"the refusal staged {staged_in(checkout)!r}")
    assert head_of(checkout) == head, "a commit was made over the refusal"
    assert remote_main(tmp_path) == head, "something was pushed to main"
    assert not (home / ".agents" / "workspace.yaml").exists(), (
        "the pointer file was written by a run that refused")


def test_the_seed_stages_the_paths_it_wrote_and_not_a_template_file_beside(
        tmp_path):
    """THE OTHER HALF OF THE SAME FINDING, and the half step 6a cannot reach.

    A template file a person has EDITED is not `unrelated` — the template names
    it, and a half-finished earlier run leaves exactly those paths behind, so
    excluding them is what makes the re-run step 7 promises actually work. That
    is precisely why step 8 stages the paths step 7 wrote BY NAME: the one path
    the refusal is deliberately blind to is the one an `-A` would have carried
    into the seed commit.

    So: a checkout missing one template file and carrying an edit to another
    finishes the run, commits the file it wrote, and leaves the edit in the
    worktree, uncommitted and unpushed.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    checkout = adopted_checkout(tmp_path, home, env)
    # A template file the workspace no longer has — the state a re-seed fixes.
    subprocess.run(["git", "-C", str(checkout), "rm", "-q", "--",
                    "handoffs/README.md"], check=True)
    subprocess.run(["git", "-C", str(checkout), "commit", "-q", "-m",
                    "somebody removed the handoffs README"], check=True)
    subprocess.run(["git", "-C", str(checkout), "push", "-q", "origin",
                    "HEAD:main"], check=True)
    # …and one the person is in the middle of editing.
    lanes = checkout / "lanes" / "LANES.md"
    edited = lanes.read_text(encoding="utf-8") + "\n| a row being written |\n"
    lanes.write_text(edited, encoding="utf-8")

    result = run_wip(home, extra=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "seeded 1 of" in result.stdout, result.stdout

    committed = subprocess.run(
        ["git", "-C", str(checkout), "show", "--name-only", "--pretty=format:",
         "HEAD"], capture_output=True, text=True, check=True)
    assert committed.stdout.split() == ["handoffs/README.md"], (
        f"the seed commit carried more than the template paths it wrote:\n"
        f"{committed.stdout}")
    assert lanes.read_text(encoding="utf-8") == edited, (
        "the person's edit was overwritten")
    dirty = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain"],
                           capture_output=True, text=True, check=True)
    assert dirty.stdout.strip() == "M lanes/LANES.md", (
        f"the edit was staged or committed:\n{dirty.stdout}")


def test_a_staged_edit_to_a_template_file_stays_out_of_the_seed(tmp_path):
    """AND THE HALF THAT WAS STILL OPEN: THE INDEX (#44 round 1,
    `openRepoTools:1525`).

    Step 8 staged the paths it wrote BY NAME and then committed with no
    pathspec, and `git commit` with no pathspec commits THE INDEX. So the one
    path step 6a is deliberately blind to — a template file the person had
    edited — rode out to `main` anyway, as long as they had `git add`ed it and
    the run had any seeding to do at all. The staging was by name and the
    commit was not, which is the same publication one line further down.

    The commit takes the same pathspec, so the person's staged edit is exactly
    where they left it when the run finishes: staged, uncommitted, unpushed.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    checkout = adopted_checkout(tmp_path, home, env)
    # A template file the workspace no longer has, so the seed has work to do.
    for args in (["rm", "-q", "--", "handoffs/README.md"],
                 ["commit", "-q", "-m", "somebody removed the handoffs README"],
                 ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", "-C", str(checkout), *args], check=True)
    # …and one the person has edited AND STAGED.
    lanes = checkout / "lanes" / "LANES.md"
    edited = lanes.read_text(encoding="utf-8") + "\n| a row being written |\n"
    lanes.write_text(edited, encoding="utf-8")
    subprocess.run(["git", "-C", str(checkout), "add", "--", "lanes/LANES.md"],
                   check=True)

    result = run_wip(home, extra=env)
    assert result.returncode == 0, result.stdout + result.stderr

    committed = subprocess.run(
        ["git", "-C", str(checkout), "show", "--name-only", "--pretty=format:",
         "HEAD"], capture_output=True, text=True, check=True)
    assert committed.stdout.split() == ["handoffs/README.md"], (
        f"the seed commit published a path the person staged:\n"
        f"{committed.stdout}")
    assert staged_in(checkout).split() == ["lanes/LANES.md"], (
        f"the seed commit consumed the person's index: {staged_in(checkout)!r}")
    assert lanes.read_text(encoding="utf-8") == edited, (
        "the person's edit was overwritten")


def test_the_rerun_after_a_commit_that_failed_carries_the_seed_it_left_behind(
        tmp_path):
    """THE OTHER HALF OF THE SAME PATHSPEC, and the one it could have cost.

    A first run that copied the nine template files and could not commit them
    — no `user.email`, which is what the refusal above is written about —
    leaves them in the worktree and in the index, and HEAD carrying none of
    them. The re-run seeds NOTHING, because step 7 leaves a file that is
    already there exactly as it is, so a commit restricted to the paths THIS
    run wrote would commit nothing, push nothing, and go on to write the
    pointer file over an empty `main`: the one state step 8's remote gate
    exists to prevent, reached from the other side.

    So the pathspec is the paths the seed OWES this checkout — what this run
    wrote, and every template path the worktree carries and HEAD does not.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path, exists=True)
    checkout = home / "projects" / "brettheap-wip"
    checkout.parent.mkdir(parents=True)
    bare = tmp_path / "github" / "opensoft" / "brettheap-wip.git"
    subprocess.run(["git", "clone", "-q", str(bare), str(checkout)], check=True)
    hook = checkout / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'no user.email here' >&2\nexit 1\n",
                    encoding="utf-8")
    hook.chmod(0o755)

    first = run_wip(home, extra=env)
    assert first.returncode == 2, first.stdout + first.stderr
    assert "could not commit the seed" in first.stderr
    assert sorted(staged_in(checkout).split()) == sorted(TEMPLATE_FILES), (
        f"the first run left something other than the seed staged: "
        f"{staged_in(checkout)!r}")
    assert head_of(checkout) == "", "the first run committed after all"

    hook.unlink()
    second = run_wip(home, extra=env)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "committed the seed" in second.stdout, second.stdout

    committed = subprocess.run(
        ["git", "-C", str(checkout), "show", "--name-only", "--pretty=format:",
         "HEAD"], capture_output=True, text=True, check=True)
    assert sorted(committed.stdout.split()) == sorted(TEMPLATE_FILES), (
        f"the re-run did not carry the seed the first run left staged:\n"
        f"{committed.stdout}")
    assert remote_main(tmp_path) == head_of(checkout), "the seed never landed"
    assert (home / ".agents" / "workspace.yaml").is_file(), (
        "step 9 did not run after the seed finally landed")


def test_an_untracked_file_at_a_template_path_is_refused_not_absorbed(tmp_path):
    """THE HALF THE `cat-file -e HEAD:` QUESTION COULD NOT TELL APART (#44
    round 2, `openRepoTools:1621`).

    An earlier run's own leftover and a person's own untracked file at a
    template path are BOTH absent from HEAD — the one question step 7 asked
    could not tell them apart, so a person's own `handoffs/README.md`, never
    committed and never named to this command, answered it exactly as this
    command's own half-finished leftover would have, and went into the seed.

    The bytes tell them apart where the question alone could not: this
    command's own leftover is what THIS RUN would itself write there, so the
    fetched, substituted template is compared against what is on disk before
    either is trusted as this command's own — and a mismatch is a refusal in
    the same voice as step 6a's, not a silent seed of somebody else's file.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    checkout = adopted_checkout(tmp_path, home, env)
    for args in (["rm", "-q", "--", "handoffs/README.md"],
                 ["commit", "-q", "-m", "somebody removed the handoffs README"],
                 ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", "-C", str(checkout), *args], check=True)
    before_head = head_of(checkout)
    foreign = checkout / "handoffs" / "README.md"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign_text = "this is somebody's own file, not the template\n"
    foreign.write_text(foreign_text, encoding="utf-8")

    result = run_wip(home, extra=env)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "handoffs/README.md exists" in result.stderr, result.stderr
    assert ("run's own template bytes was written into that checkout, "
            "and nothing was staged.") in result.stderr
    assert foreign.read_text(encoding="utf-8") == foreign_text, (
        "the foreign file was overwritten")
    assert staged_in(checkout) == "", "the foreign file was staged"
    assert head_of(checkout) == before_head, (
        "a commit was made despite the refusal")
    assert remote_main(tmp_path) == before_head, (
        "something was pushed despite the refusal")


def test_a_staged_edit_at_a_missing_path_is_refused_even_when_the_worktree_reads_back_as_the_template(
        tmp_path):
    """THE HALF THE WORKTREE COMPARISON ALONE COULD NOT TELL APART (#44
    round 3, `openRepoTools:1647`).

    HEAD lacking a template path says nothing about the INDEX: a person can
    `git add` their own edit at that path — before this command ever runs —
    and step 8's `add` stages straight from the worktree, by name, so it would
    stage over that edit the moment the WORKTREE's own bytes happen to read
    back as the template, exactly as an earlier run's real leftover does. The
    index is asked the same question the worktree already answers, so a
    staged edit does not vanish just because the file on disk no longer shows
    it.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    checkout = adopted_checkout(tmp_path, home, env)
    # What the template substitutes to, captured from the first run's own
    # seed before the path is removed from HEAD below.
    template_bytes = (checkout / "handoffs" / "README.md").read_text(
        encoding="utf-8")
    for args in (["rm", "-q", "--", "handoffs/README.md"],
                 ["commit", "-q", "-m", "somebody removed the handoffs README"],
                 ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", "-C", str(checkout), *args], check=True)
    before_head = head_of(checkout)

    foreign = checkout / "handoffs" / "README.md"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign_text = "this is somebody's own staged edit, not the template\n"
    foreign.write_text(foreign_text, encoding="utf-8")
    subprocess.run(["git", "-C", str(checkout), "add", "--",
                    "handoffs/README.md"], check=True)
    # …and now the WORKTREE copy reads back as the template, even though what
    # is STAGED at this path is still the person's own edit above.
    foreign.write_text(template_bytes, encoding="utf-8")

    result = run_wip(home, extra=env)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "handoffs/README.md exists" in result.stderr, result.stderr
    assert ("run's own template bytes was written into that checkout, "
            "and nothing was staged.") in result.stderr
    assert foreign.read_text(encoding="utf-8") == template_bytes, (
        "the worktree file was overwritten")
    assert staged_in(checkout).split() == ["handoffs/README.md"], (
        f"the staged edit was unstaged: {staged_in(checkout)!r}")
    staged_blob = subprocess.run(
        ["git", "-C", str(checkout), "show", ":handoffs/README.md"],
        capture_output=True, text=True, check=True).stdout
    assert staged_blob == foreign_text, (
        "the seed overwrote the person's staged edit with the template")
    assert head_of(checkout) == before_head, (
        "a commit was made despite the refusal")
    assert remote_main(tmp_path) == before_head, (
        "something was pushed despite the refusal")


@pytest.mark.parametrize("dangling", [True, False],
                         ids=["dangling", "live-matching-target"])
def test_a_symlink_at_a_missing_template_path_is_refused_not_followed(
        tmp_path, dangling):
    """NEITHER `cmp` NOR `cp` MAY BE TRUSTED THROUGH ONE (#44 round 3,
    `openRepoTools:1613` and `:1647`).

    `[ -e ]` alone answers false for a DANGLING symlink exactly as it does for
    nothing there at all, so without also asking `-L` this path would reach
    the MISSING branch and meet `cp` at a link — writing this run's bytes
    wherever the link points, inside the checkout or far outside it. And a
    LIVE symlink whose target happens to hold the template's own bytes would
    pass the worktree comparison the owed-candidate branch makes, and a
    `git add` of it would stage the LINK ITSELF, never the bytes at its far
    end. Both shapes are refused the same way, before either branch acts on
    the link or on whatever it points at.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    checkout = adopted_checkout(tmp_path, home, env)
    template_bytes = (checkout / "handoffs" / "README.md").read_text(
        encoding="utf-8")
    for args in (["rm", "-q", "--", "handoffs/README.md"],
                 ["commit", "-q", "-m", "somebody removed the handoffs README"],
                 ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", "-C", str(checkout), *args], check=True)
    before_head = head_of(checkout)

    link = checkout / "handoffs" / "README.md"
    link.parent.mkdir(parents=True, exist_ok=True)
    # OUTSIDE the checkout: a file inside it would itself be an untracked
    # path step 6a's own refusal catches first, and that is a different
    # test (`test_an_adopted_checkout_with_unrelated_changes_is_refused`).
    if dangling:
        target = tmp_path / "nowhere-at-all"
    else:
        target = tmp_path / "elsewhere-with-template-bytes.md"
        target.write_text(template_bytes, encoding="utf-8")
    link.symlink_to(target)

    result = run_wip(home, extra=env)

    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{link} is a symlink" in result.stderr, result.stderr
    assert ("run's own template bytes was written into that checkout, "
            "and nothing was staged.") in result.stderr, result.stderr
    assert link.is_symlink(), "the symlink was replaced"
    if not dangling:
        assert target.read_text(encoding="utf-8") == template_bytes, (
            "the symlink's target was modified")
    assert staged_in(checkout) == "", "the symlink was staged"
    assert head_of(checkout) == before_head, (
        "a commit was made despite the refusal")
    assert remote_main(tmp_path) == before_head, (
        "something was pushed despite the refusal")


def test_a_staged_addition_with_no_worktree_file_is_refused_not_overwritten(
        tmp_path):
    """THE INDEX CAN OWE SOMETHING THE WORKTREE NO LONGER HAS AT ALL (#44
    round 3, `openRepoTools:1613`).

    A person's own `git add` of a template path, followed by removing the
    worktree file, leaves the INDEX carrying something the worktree does not
    — a shape `[ -e "$checkout/$rel" ]` alone reads as plain MISSING, which
    would `cp` the template straight in and let step 8's own `add` stage over
    whatever they had. This command has never staged a path and then removed
    its own file out from under it, so an index entry with nothing on disk
    behind it is never this command's own leftover, whatever it holds.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    checkout = adopted_checkout(tmp_path, home, env)
    for args in (["rm", "-q", "--", "handoffs/README.md"],
                 ["commit", "-q", "-m", "somebody removed the handoffs README"],
                 ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", "-C", str(checkout), *args], check=True)
    before_head = head_of(checkout)

    staged = checkout / "handoffs" / "README.md"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged_text = "somebody's own staged addition, then the file was removed\n"
    staged.write_text(staged_text, encoding="utf-8")
    subprocess.run(["git", "-C", str(checkout), "add", "--",
                    "handoffs/README.md"], check=True)
    staged.unlink()

    result = run_wip(home, extra=env)

    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{staged} does not exist, HEAD does not carry" in result.stderr, (
        result.stderr)
    assert not staged.exists(), "a file was written where there was none"
    staged_blob = subprocess.run(
        ["git", "-C", str(checkout), "show", ":handoffs/README.md"],
        capture_output=True, text=True, check=True).stdout
    assert staged_blob == staged_text, (
        "the seed overwrote the person's staged addition")
    assert head_of(checkout) == before_head, (
        "a commit was made despite the refusal")
    assert remote_main(tmp_path) == before_head, (
        "something was pushed despite the refusal")


def test_a_staged_deletion_of_a_head_tracked_path_is_left_alone(tmp_path):
    """A TEMPLATE PATH HEAD ALREADY CARRIES IS THE PERSON'S EVEN MID-DELETE
    (#44 round 3, `openRepoTools:1615`).

    `git rm` of a path HEAD still carries leaves the worktree file gone and
    the index entry gone too, so it answers `[ -e ]`, `[ -L ]` and the
    stage-0 index question all false — exactly what a plain MISSING path
    answers — unless `HEAD` itself is also asked. Without that, the MISSING
    branch would fetch the template and `cp` it straight back, undoing a
    deletion this command has never modified a committed file to make.
    `HEAD:$rel` answers true here, so the path is left exactly where the
    person put it: staged, and this run commits nothing over it.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    checkout = adopted_checkout(tmp_path, home, env)
    before_head = head_of(checkout)

    lanes = checkout / "lanes" / "LANES.md"
    subprocess.run(["git", "-C", str(checkout), "rm", "-q", "--",
                    "lanes/LANES.md"], check=True)
    assert not lanes.exists()

    result = run_wip(home, extra=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "the workspace already carries every template file" in result.stdout, (
        result.stdout)
    assert not lanes.exists(), "the deleted file was restored"
    assert staged_in(checkout).split() == ["lanes/LANES.md"], (
        f"the staged deletion was not exactly what remained staged: "
        f"{staged_in(checkout)!r}")
    assert head_of(checkout) == before_head, (
        "a commit was made over the person's own staged deletion")
    assert remote_main(tmp_path) == before_head, (
        "something was pushed over the person's own staged deletion")


def test_a_template_path_with_an_unresolved_merge_conflict_is_refused(tmp_path):
    """FOUR TESTS, AND A CONFLICT ANSWERS ALL OF THEM FALSE (#44 round 3,
    `openRepoTools:1699`).

    A path at stages 1-3 with no stage 0 — an unresolved merge conflict,
    added differently on two sides with no common ancestor version — can
    have no worktree file of its own and no `HEAD` entry either, so
    `[ -e ]`, `[ -L ]`, the stage-0 index question and `HEAD:$rel` are all
    false: exactly what a plain MISSING path answers, and step 6a's own
    exclusion of template paths means no earlier gate has seen it either.
    `git ls-files -u` is asked directly instead, and a conflict there is
    refused rather than settled by whichever branch the worktree's own
    (absent) state happens to satisfy.
    """
    home = tmp_path / "home"
    env = fake_gh(tmp_path)
    checkout = adopted_checkout(tmp_path, home, env)
    for args in (["rm", "-q", "--", "handoffs/README.md"],
                 ["commit", "-q", "-m", "somebody removed the handoffs README"],
                 ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", "-C", str(checkout), *args], check=True)
    before_head = head_of(checkout)

    def hash_object(text: str) -> str:
        return subprocess.run(
            ["git", "-C", str(checkout), "hash-object", "-w", "--stdin"],
            input=text, capture_output=True, text=True, check=True
        ).stdout.strip()

    # A stage-1-3 conflict built directly through plumbing: an add/add with
    # no common ancestor has no stage 1 either, and no `git merge` is needed
    # to reach exactly the index shape this finding is about.
    ours = hash_object("ours: not the template\n")
    theirs = hash_object("theirs: not the template either\n")
    index_info = (f"100644 {ours} 2\thandoffs/README.md\n"
                  f"100644 {theirs} 3\thandoffs/README.md\n")
    subprocess.run(["git", "-C", str(checkout), "update-index", "--index-info"],
                   input=index_info, text=True, check=True)

    result = run_wip(home, extra=env)

    assert result.returncode == 2, result.stdout + result.stderr
    assert (f"{checkout} has an unresolved merge conflict at "
            "handoffs/README.md") in result.stderr, result.stderr
    assert not (checkout / "handoffs" / "README.md").exists(), (
        "a file was written where the conflict left none")
    unmerged = subprocess.run(
        ["git", "-C", str(checkout), "ls-files", "-u", "--",
         "handoffs/README.md"],
        capture_output=True, text=True, check=True).stdout
    assert unmerged.count("\n") == 2, (
        f"the conflict's own stages were touched: {unmerged!r}")
    assert head_of(checkout) == before_head, (
        "a commit was made despite the refusal")
    assert remote_main(tmp_path) == before_head, (
        "something was pushed despite the refusal")


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


# --- git's own words, on the three failures a fresh machine meets (F9) ------

def test_a_clone_that_fails_prints_what_it_said_and_not_only_a_summary(tmp_path):
    """THE COMMAND WHOSE JOB IS TO SET UP A NEW MACHINE MUST NOT SWALLOW THE
    ONE SENTENCE THAT SAYS WHAT IS WRONG WITH IT (F9 of the #24 review, ruled
    R-A9-15).

    The clone, the stage and the commit all ran `>/dev/null 2>&1` and died with
    a summary of this command's own devising: a machine with no credential got
    `could not clone <target> into <path>. Nothing else was changed.` and
    nothing else, when git had already said exactly what to do about it. Its
    stderr is kept now and the last of it is printed UNDER the refusal — the
    shape `fetch_from_repo`'s refusal already has.
    """
    home = tmp_path / "home"
    result = run_wip(home, extra=fake_gh(tmp_path, refuse_clone=True))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "could not clone" in result.stderr
    assert "What it said:" in result.stderr, result.stderr
    assert "terminal prompts disabled" in result.stderr, (
        f"the refusal dropped the only sentence that says why:\n{result.stderr}")


def test_a_commit_that_fails_prints_what_git_said(tmp_path):
    """THE SAME RULE ON THE SEED COMMIT, which is the one a machine with no
    `user.email` configured actually meets. A `pre-commit` hook standing in for
    it, because the refusal under test is "whatever git said", not one
    particular sentence git says."""
    home = tmp_path / "home"
    env = fake_gh(tmp_path, exists=True)
    checkout = home / "projects" / "brettheap-wip"
    checkout.parent.mkdir(parents=True)
    bare = tmp_path / "github" / "opensoft" / "brettheap-wip.git"
    subprocess.run(["git", "clone", "-q", str(bare), str(checkout)], check=True)
    hook = checkout / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'the commit hook said no' >&2\nexit 1\n",
                    encoding="utf-8")
    hook.chmod(0o755)

    result = run_wip(home, extra=env)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "could not commit the seed" in result.stderr
    assert "the commit hook said no" in result.stderr, (
        f"the refusal dropped what git said:\n{result.stderr}")
    assert not (home / ".agents" / "workspace.yaml").exists(), (
        "the pointer file was written by a run that never committed")
