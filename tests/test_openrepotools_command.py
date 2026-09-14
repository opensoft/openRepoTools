# SPDX-License-Identifier: Apache-2.0
"""`openRepoTools` — the installer, and the whole of what it does.

OFFLINE, LIKE THE REST OF THIS SUITE. Run from a file, `--install` copies the
bytes beside it and reaches nothing at all; the tests that exercise the
FETCHING path put a fake `gh` first on `$PATH` — `fetch_from_repo` tries the
API before the raw URL, so answering that one call is the whole of the server
they need — and shadow `curl` with a script that refuses, so a run cannot fall
through to the network even if the fake `gh` stops matching. `INSTALLED`
below is what this suite answers for, because `--install` places every name
in it, or none.

What a fake `gh` cannot show is which way round the real two are tried, so THAT
rule — the authenticated call first, because an organisation can block
raw.githubusercontent.com and still have a working `gh` — stays asserted
against the script's text, the way this suite guards other things it cannot
run.

ADAPTED FROM openRepoShape's `tests/test_openreposhape_command.py`, whose shim
these install semantics are a deliberate copy of (openRepoShape #82, F10 of the
review on its #83). Nothing about a scaffold comes over: this command has no
verb, no `--doctor` and no `setup.sh`.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess

from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

COMMAND = REPO / "openRepoTools"

#: EVERY FILE `--install` PLACES INTO THE BIN DIRECTORY. One install line for
#: the whole toolset: a second engineer gets the estate verbs AND the lane
#: helpers from the README's one line and nothing depends on anyone's dotfiles.
#: `openRepoTools` is first because it is the one a person types to get the
#: others; the last five came here from `opensoft/brett-wip` with their history
#: under lane-collision-protocol Amendment 9(b), and `repos.tsv` is data placed
#: at 755 with the commands because `--install` has one list, one destination
#: and one mode.
INSTALLED = ("openRepoTools", "park", "resume", "status", "restart", "lanes",
             "lane-handoff", "lanes-edit.sh", "lane-start", "lane-end",
             "link-estates", "repos.tsv")

#: The skills `--install` also places, at two paths each, and the paths they are
#: fetched from when there is no checkout to copy them out of (Amendment 9(b),
#: inheriting A8 Addendum 2 R-A8-5; `restart` joins under Amendment 11 clause
#: (f) and ratified decision 7; `handoff` under Amendment 17(a), which renames
#: the act `lane-swap` performed and keeps `lane-swap` as an ALIAS FILE naming
#: it — one skill is the source of the act and the aliases add nothing).
SKILL_NAMES = ("handoff", "lane-swap", "restart")
SKILL_PATHS = tuple(f"skills/{n}/SKILL.md" for n in SKILL_NAMES)
SKILL_PATH = SKILL_PATHS[0]

#: The COMMAND FILES `--install` also places, at the matching pair of paths
#: (A11 Addendum 4 ruling 9, ratified "a11 addendum 4 yes"). `/swap` is clause
#: (g)'s alias of `/lane-swap`; `opensoft/workBenches#74` deletes the launcher's
#: copy, and adoption act 6 — which would have the launcher keep vendoring
#: command files — lands after act 3, so without this it would be installed by
#: nobody (F-X28). `/handoff` is the act's own word and `/ctx` is
#: `/handoff --restart`, both under Amendment 17 (clauses (a) and (f)).
COMMAND_NAMES = ("handoff", "ctx", "swap")
COMMAND_PATHS = tuple(f"commands/{n}.md" for n in COMMAND_NAMES)

#: Everything a stdin install has to fetch: the twelve files, the three skills
#: and the three command files.
FETCHED = INSTALLED + SKILL_PATHS + COMMAND_PATHS

#: TWENTY-FIVE ARTIFACTS, AND THE COUNT IS THE INVARIANT: twelve files in the
#: bin directory, three skills in the shared skills directory, their three
#: bare-run copies, three command files at that same pair of destinations, and
#: one merged entry in `~/.claude/settings.json`. Derived from the three lists
#: rather than restated, so adding a skill or a command moves it.
ARTIFACTS = len(INSTALLED) + 2 * len(SKILL_NAMES) + 2 * len(COMMAND_NAMES) + 1

USAGE_LINES = (
    "openRepoTools --install            install (or update) the twelve estate and",
    "openRepoTools wip init             create your workspace repository, clone it,",
    "openRepoTools --help | --version",
)

#: The command is bash, and Windows has no shebang execution for the fake `gh`
#: either. There is no Windows twin to run instead: on Windows the way in is
#: WSL2, exactly as it is for openRepoShape's `setup.sh`.
pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="openRepoTools is a bash script"),
              WINDOWS_SKIP]

#: `--install` HARD-REQUIRES `jq` SINCE lane-collision-protocol AMENDMENT 9(b):
#: one of its twenty-five artifacts is a merged entry inside a JSON file somebody
#: else owns, and the clause has it refuse naming `jq` rather than rewriting
#: that file by hand. So a run of `--install` on a host without `jq` is a
#: REFUSAL BY DESIGN, and a test that asserts a successful placement there is
#: asserting against the contract. Marked rather than left to fail, because a
#: red suite on a minimal image is how a fork stops being finished — the same
#: reason `AGENTS.md` gives for the submodule SKIP.
#:
#: The tests NOT marked are the ones that never reach the merge: the refusals,
#: `--help`, `--version`, and `test_install_places_all_nine_or_none`, which is
#: refused at `collect_commands` before `plan_hook_merge` is called at all.
#: `test_without_jq_it_refuses_and_places_nothing` is the positive case for the
#: same fact and is deliberately unmarked.
NEEDS_JQ = pytest.mark.skipif(
    shutil.which("jq") is None,
    reason="`--install` merges one SessionStart entry with jq (Amendment 9(b))")


def command_env(home: Path | None = None, env: dict | None = None) -> dict:
    """The environment this suite controls, for a run of the command.

    Every `$OPENREPOTOOLS_*` variable the command reads is cleared first, so a
    developer's own shell cannot change what these tests assert.

    AND SO ARE THE TWO THAT SAY WHERE `~/.claude` IS. Since Amendment 9(b),
    `--install` writes a skill into `$CLAUDE_PROFILES_HOME/shared/skills/` and
    merges a hook entry into `$CLAUDE_USER_DIR/settings.json` — real
    directories on the machine running this suite. Redirecting `HOME` is what
    keeps those writes inside `tmp_path`, and it only works while neither
    variable is inherited from the developer's own shell. A suite that
    installed a skill into a person's live profile set would be a suite nobody
    could run twice.
    """
    environ = dict(os.environ)
    for name in ("OPENREPOTOOLS_REF", "OPENREPOTOOLS_REPO",
                 "OPENREPOTOOLS_BIN_DIR", "CLAUDE_PROFILES_HOME",
                 "CLAUDE_USER_DIR", "AGENT_PROTOCOL_ROOT", "PROJECTS_DIR"):
        environ.pop(name, None)
    if home is not None:
        environ["HOME"] = str(home)
        environ["CLAUDE_PROFILES_HOME"] = str(home / ".claude-profiles")
        environ["CLAUDE_USER_DIR"] = str(home / ".claude")
        environ["AGENT_PROTOCOL_ROOT"] = str(home / ".agents")
    environ.update(env or {})
    return environ


def run_cmd(*args: str, home: Path | None = None,
            env: dict | None = None) -> subprocess.CompletedProcess:
    """The command, run from its file, with that environment.

    `input=""` means stdin is a pipe rather than a terminal, which is what
    every run in this file wants: nothing here may ask a question.
    """
    return subprocess.run(["bash", str(COMMAND), *args], capture_output=True,
                          text=True, check=False, input="",
                          env=command_env(home, env))


# --- what it says about itself ---------------------------------------------

def test_help_prints_every_usage_line():
    """Every line `--help` promises: a usage line nobody asserts on is a usage
    line that can go stale without anything noticing."""
    result = run_cmd("--help")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    for line in USAGE_LINES:
        assert line in lines, f"--help never printed:\n    {line}"


def test_help_names_every_command_it_places_and_the_standards_front_door():
    """`--install` places twelve files, and eleven of them are commands this one
    knows nothing about — so `--help` has to say what they are and where the
    rest is written down. A command a person has on PATH and cannot find
    written down is a command they will not use.

    It also has to say what this command is NOT: `openRepoShape` is the
    standard's front door, and somebody who typed `openRepoTools Atlas`
    expecting a scaffold needs that sentence rather than a usage dump. What it
    no longer says is "and does nothing else" — Brett Heap ruled `wip init`
    (Amendment 9, ruling 4), so that line, the `*)` arm and the test that
    pinned them are what changed (R-A9-1).
    """
    result = run_cmd("--help")
    assert result.returncode == 0, result.stderr
    for line in ("park [<Name>]", "resume [<Name>]", "status [<Name>]",
                 "lane-start <repo> <n>", "lane-end <lane>",
                 "lanes-edit.sh <verb>", "link-estates", "repos.tsv"):
        assert line in result.stdout, line
    assert "`openRepoShape` is the standard's front door" in result.stdout
    assert "this command scaffolds none" in result.stdout


def test_help_documents_the_verb_pair_the_setup_step_probes_for():
    """opensoft/workBenches#68's `setup-workspace-repo.sh` decides whether this
    openRepoTools can create a workspace by grepping `--help` for the VERB
    PAIR, never by running the verb and reading an exit code — because `die`'s
    default exit is 2 and so is a genuine refusal's, and a probe that read the
    code would report the administrator's `gh repo create` block as "no such
    subcommand" and print a degradation recipe over the top of the one thing
    the person needed (Amendment 9(c)).

    This test IS that probe, byte for byte, so the contract cannot drift on
    this side of the seam without a red test here.
    """
    result = run_cmd("--help")
    assert result.returncode == 0, result.stderr
    probe = re.compile(r"(^|\s)wip\s+init(\s|$)", re.MULTILINE)
    assert probe.search(result.stdout), (
        "workBenches' setup step greps --help for `wip init` and would report "
        "this openRepoTools as having no workspace verb")


def test_help_names_every_variable_it_reads():
    """Every variable the script honours, named in the usage: one it reads and
    the usage does not name is a variable nobody finds."""
    result = run_cmd("--help")
    for name in ("$OPENREPOTOOLS_REPO", "$OPENREPOTOOLS_REF",
                 "$OPENREPOTOOLS_BIN_DIR", "$AGENT_PROTOCOL_ROOT",
                 "$CLAUDE_PROFILES_HOME", "$PROJECTS_DIR"):
        assert name in result.stdout, name


def test_no_argument_at_all_prints_the_usage_and_exits_zero():
    """A person who typed the name to see what it is has asked a question, not
    made a mistake — so this is stdout and 0, not the refusal."""
    result = run_cmd()
    assert result.returncode == 0, result.stderr
    assert USAGE_LINES[0] in result.stdout
    assert "REFUSED" not in result.stderr


def test_version_names_the_repository_and_the_ref():
    """There is no version number here, for openRepoShape's reason: the
    identity is a commit. So the honest answer to `--version` is WHICH BYTES it
    will fetch — repo and ref."""
    result = run_cmd("--version")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "openRepoTools (opensoft/openRepoTools @ main)"


def test_version_follows_the_ref_it_would_fetch():
    result = run_cmd("--version", env={"OPENREPOTOOLS_REF": "v1.2.3"})
    assert result.returncode == 0, result.stderr
    assert "@ v1.2.3" in result.stdout


def test_version_follows_the_repository_it_would_fetch():
    """A fork or a mirror is named once and both fetch forms follow it, so
    `--version` has to say which one answered."""
    result = run_cmd("--version", env={"OPENREPOTOOLS_REPO": "someone/fork"})
    assert result.returncode == 0, result.stderr
    assert "openRepoTools (someone/fork @ main)" in result.stdout.strip()


# --- the refusal ------------------------------------------------------------

#: Everything a person might reasonably type at this command that it does not
#: take: a verb (which is a separate file on their PATH), a project name (which
#: is `openRepoShape`'s), a flag from either, and a second argument to
#: `--install`.
NOT_ITS_ARGUMENTS = ["park", "resume", "status", "Atlas", "--doctor", "--org",
                     "--dry-run", "-x", "lane-start", "lanes-edit.sh"]


@pytest.mark.parametrize("argument", NOT_ITS_ARGUMENTS)
def test_anything_else_is_refused_and_names_the_verbs(argument):
    """ONE VERB PAIR AND THREE FLAGS, and nothing else. The refusal names
    `park --help` and `resume --help` rather than reprinting the usage:
    somebody typing `openRepoTools park` wants `park`, and the shortest true
    answer is where it is.

    `--org` and `--dry-run` stay in this list although `wip init` takes both:
    they are ITS options, reached through the verb, and at the top level they
    are still not this command's arguments. So is a lane helper's own name —
    `lane-start` is a command `--install` places, not a word this one answers
    to.
    """
    result = run_cmd(argument)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "installs the estate commands and creates the workspace they read" \
        in result.stderr
    assert "--install," in result.stderr
    assert "`wip init`" in result.stderr
    assert "--help or --version" in result.stderr
    assert "`park --help`" in result.stderr
    assert "`resume --help`" in result.stderr
    assert "`status --help`" in result.stderr


def test_wip_alone_names_its_one_verb():
    """`wip` is a noun and takes exactly one verb. The refusal prints the whole
    line rather than a list, because there is only one thing to say."""
    result = run_cmd("wip")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "openRepoTools wip init" in result.stderr


def test_wip_with_an_unknown_verb_is_refused():
    result = run_cmd("wip", "destroy")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "`wip destroy` is not a thing this command does" in result.stderr
    assert "openRepoTools wip init" in result.stderr


@pytest.mark.parametrize("flag", ["--nope", "--repo"])
def test_wip_init_refuses_an_option_it_does_not_take(flag):
    result = run_cmd("wip", "init", flag)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "--org, --login, --team and --dry-run" in result.stderr


def test_install_refuses_a_second_argument_and_installs_nothing(tmp_path):
    """`--install` takes no other arguments, and the refusal comes BEFORE
    anything is placed: a run that half-understood its own command line must
    not leave a file behind."""
    bin_dir = tmp_path / "bin"
    result = run_cmd("--install", "Atlas", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "creates the workspace they read" in result.stderr
    assert not bin_dir.exists(), "the refusal placed a file anyway"


# --- --install --------------------------------------------------------------

@NEEDS_JQ
def test_install_writes_an_executable_copy(tmp_path):
    """All NINE files, each 755 and byte-identical to this checkout's.

    A `park` that is not executable is not a command, and a `park` that is a
    near-copy is a command whose refusals nobody reviewed — so the bytes are
    compared rather than the presence of a file.
    """
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    for name in INSTALLED:
        target = tmp_path / ".local" / "bin" / name
        assert target.is_file(), result.stdout + f" (missing {name})"
        assert stat.S_IMODE(target.stat().st_mode) == 0o755, name
        assert target.read_bytes() == (REPO / name).read_bytes(), name
        assert f"{name}: installed at" in result.stdout
    assert f"openRepoTools: {len(INSTALLED)} of {len(INSTALLED)} placed" \
        in result.stdout, (
        "a person reading eight lines cannot tell whether a ninth was meant "
        "to be there; the count says so")


@NEEDS_JQ
def test_installing_twice_changes_nothing(tmp_path):
    """Idempotent BY CONTENT, per file: the second run must not rewrite one
    that already holds these bytes, and must say so rather than claim an
    install."""
    first = run_cmd("--install", home=tmp_path)
    assert first.returncode == 0, first.stderr
    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    for name in INSTALLED:
        assert f"{name}: already installed at" in second.stdout, name
    # TWENTY-FIVE, not twelve: the six skill copies, the six command-file copies
    # and the hook entry each report `unchanged` too, and the count is the
    # invariant Amendment 9(b) names — derived from the three lists, never
    # restated, so a new skill or command moves it.
    assert second.stdout.count("unchanged") == ARTIFACTS


@pytest.mark.parametrize("name", INSTALLED)
@NEEDS_JQ
def test_install_replaces_a_copy_that_has_drifted(tmp_path, name):
    """Per file, and only the one that drifted: an install that rewrote all
    twelve every time would have nothing to say about which one was stale."""
    assert run_cmd("--install", home=tmp_path).returncode == 0
    target = tmp_path / ".local" / "bin" / name
    target.write_text(target.read_text(encoding="utf-8") + "# drift\n",
                      encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert f"{name}: updated at" in result.stdout
    assert target.read_bytes() == (REPO / name).read_bytes()
    for other in INSTALLED:
        if other != name:
            assert f"{other}: already installed at" in result.stdout, other


@NEEDS_JQ
def test_a_copy_whose_bytes_are_right_and_whose_mode_is_not_says_so(tmp_path):
    """THE ELEVEN HAVE ALWAYS BEEN STAMPED EVERY TIME, AND THE LINE DID NOT SAY
    SO (#40, finding 2).

    `chmod 755` sits outside the bytes comparison here — a copy that is not
    executable is not a command — so this half was never the defect the skills
    and the command files had. What it did was report `unchanged` over a mode
    it had just repaired, which is a line a person reads as "nothing to look
    at" about the one thing that run actually did to that file.

    The bytes are asserted untouched as well: a mode is fixed with `chmod`, not
    by rewriting a file.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    target = tmp_path / ".local" / "bin" / "park"
    before = target.read_bytes()
    os.chmod(target, 0o644)

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    assert target.read_bytes() == before
    assert f"park: already installed at {target} (mode restored to 755)" \
        in result.stdout, result.stdout
    for other in INSTALLED:
        if other != "park":
            assert f"{other}: already installed at " \
                   f"{tmp_path / '.local' / 'bin' / other} (unchanged)" \
                in result.stdout, other


@NEEDS_JQ
def test_bin_dir_overrides_where_it_lands(tmp_path):
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(tmp_path / "elsewhere")})
    assert result.returncode == 0, result.stderr
    for name in INSTALLED:
        assert (tmp_path / "elsewhere" / name).is_file(), name
        assert not (tmp_path / ".local" / "bin" / name).exists(), name


@NEEDS_JQ
def test_install_says_how_to_put_it_on_path(tmp_path):
    """ONE path note for the four of them: the directory is the same one, and
    four copies of the same `export` line reads as four problems."""
    result = run_cmd("--install", home=tmp_path)
    assert f'export PATH="{tmp_path}/.local/bin:$PATH"' in result.stdout
    assert result.stdout.count("export PATH=") == 1


@NEEDS_JQ
def test_install_from_a_file_never_calls_gh(tmp_path):
    """`--install` run from a file copies THOSE bytes. A machine with no `gh`
    — or no network — must still be able to install the commands, so a `gh` on
    $PATH that fails loudly may not be reached at all."""
    shim = tmp_path / "bin"
    shim.mkdir()
    marker = tmp_path / "gh-was-called"
    (shim / "gh").write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n",
                             encoding="utf-8")
    (shim / "gh").chmod(0o755)
    result = run_cmd("--install", home=tmp_path,
                     env={"PATH": f"{shim}:{os.environ['PATH']}"})
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "--install from a file must not call gh"
    # `park` and `resume` sit BESIDE this file, so a run from a file copies
    # the siblings it finds rather than fetching them.
    for name in INSTALLED:
        assert (tmp_path / ".local" / "bin" / name).is_file(), name


# --- the fetch order, asserted against the text -----------------------------

def test_the_api_is_tried_before_the_raw_url():
    """ORDER IS THE RULE. `gh api` is authenticated and works inside an
    organisation whose policy blocks raw.githubusercontent.com; the raw URL is
    the fallback for a machine with no `gh` on it. Fetching cannot be tested
    offline, so the order is read out of the script itself."""
    text = COMMAND.read_text(encoding="utf-8")
    body = text.split("fetch_from_repo() {", 1)[1].split("\n}", 1)[0]
    assert "gh api" in body and "curl -fsSL" in body
    assert body.index("gh api") < body.index("curl -fsSL"), (
        "the raw URL is fetched before the API in fetch_from_repo(); the "
        "authenticated call must be tried first")
    assert "raw.githubusercontent.com" in body


def test_the_duplicated_fetch_logic_says_so_out_loud():
    """The forty lines this command shares with openRepoShape's shim are a
    DELIBERATE copy, and the reason has to be in the file: a shared library
    would be a fifth file for `--install` to place. A duplication nobody wrote
    down is a duplication the next person removes."""
    text = COMMAND.read_text(encoding="utf-8")
    assert "DELIBERATE COPY" in text
    assert "FIFTH FILE" in text


# --- the fetch path, offline, through a fake `gh` ---------------------------

def fake_github(tmp_path, served_names) -> dict:
    """A fake `gh` serving exactly `served_names`, and a `curl` that refuses.

    Factored out of the fixture so one test can WITHHOLD a file: `--install`
    places all four or none, and the only way to prove "or none" is a server
    that cannot answer for one of them.
    """
    served = tmp_path / "served"
    served.mkdir(exist_ok=True)
    for name in served_names:
        target = served / name
        # NESTED, because one of the things `--install` fetches is not at the
        # root: `skills/handoff/SKILL.md`. The route below matches on the
        # whole path after `contents/`, so the file has to sit under the same
        # shape here.
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO / name).read_bytes())

    fake = tmp_path / "fake-path"
    fake.mkdir(exist_ok=True)
    routes = "".join(
        f"*/contents/{name}\\?*) exec cat '{served / name}' ;;\n"
        for name in served_names)
    (fake / "gh").write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        + routes +
        "esac\n"
        'printf \'fake gh: unexpected call: %s\\n\' "$*" >&2\n'
        "exit 1\n", encoding="utf-8")
    (fake / "gh").chmod(0o755)
    (fake / "curl").write_text(
        "#!/bin/sh\n"
        "printf 'fake curl: no test here may reach the network\\n' >&2\n"
        "exit 1\n", encoding="utf-8")
    (fake / "curl").chmod(0o755)
    return {"PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"}


@pytest.fixture
def offline_github(tmp_path):
    """A fake `gh` first on `$PATH`, and a `curl` that refuses.

    `fetch_from_repo` tries `gh api` before the raw URL, so a `gh` that
    answers the calls the command makes is the whole of the server these tests
    need: `contents/<command>` comes back as this checkout's own bytes for each
    of the four files `--install` places. `curl` is shadowed by a script that
    exits 1 — belt and braces, so that a fake `gh` which stopped matching could
    never quietly become a real request to raw.githubusercontent.com.
    """
    return fake_github(tmp_path, FETCHED)


def test_install_places_all_nine_or_none(tmp_path):
    """ALL IN HAND BEFORE ANY IS PLACED (openRepoShape #82, F10 of the review
    on its #83). One file at a time, dying on the first fetch that failed,
    leaves a person with a NEW `openRepoTools` and no `park` — a half-install
    that prints `installed at` and is not one — with nothing on screen to say
    which of the four were missing.

    Run from stdin with `park` withheld: NOTHING is placed, nothing already
    there is replaced, and the refusal names the file it could not fetch.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # TWO older copies, so "nothing was replaced" is a claim with witnesses
    # rather than an empty directory: the file the fetch COULD have served
    # (`openRepoTools`) and the WORKING COMMAND whose absence upstream is what
    # aborted the run (`park`). A person whose `park` still works must have it
    # afterwards.
    (bin_dir / "openRepoTools").write_text("# an older copy\n",
                                           encoding="utf-8")
    (bin_dir / "park").write_text("# an older park that still works\n",
                                  encoding="utf-8")
    withheld = fake_github(tmp_path, [n for n in FETCHED if n != "park"])
    result = subprocess.run(
        ["bash", "-s", "--", "--install"], capture_output=True, text=True,
        check=False, input=COMMAND.read_text(encoding="utf-8"),
        cwd=str(tmp_path),
        env=command_env(home=tmp_path,
                        env={**withheld,
                             "OPENREPOTOOLS_BIN_DIR": str(bin_dir)}))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "could not fetch park" in result.stderr
    assert "NOTHING was installed" in result.stderr
    assert "nothing already installed was replaced" in result.stderr
    assert (bin_dir / "openRepoTools").read_text(encoding="utf-8") == \
        "# an older copy\n", "the older copy was replaced by a half-install"
    assert (bin_dir / "park").read_text(encoding="utf-8") == \
        "# an older park that still works\n", (
        "a working `park` was overwritten by a run that could not fetch one")
    assert not (bin_dir / "resume").exists()
    assert not (bin_dir / "status").exists()
    assert "placed" not in result.stdout


def test_a_withheld_command_file_places_nothing_either(tmp_path):
    """THE ALL-OR-NOTHING RULE REACHES THE COMMAND FILE (A11 Addendum 4 ruling
    9). A `/swap` that could not be fetched beside a `/lane-swap` that could is
    a half-install of an ALIAS PAIR — the skill installed, the alias the text
    ratifies not, and nothing on screen saying which. `collect_skills` fetches
    both lists before anything is placed, so this refuses with the bin
    directory untouched.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "park").write_text("# an older park that still works\n",
                                  encoding="utf-8")
    withheld = fake_github(tmp_path,
                           [n for n in FETCHED if n not in COMMAND_PATHS])
    result = subprocess.run(
        ["bash", "-s", "--", "--install"], capture_output=True, text=True,
        check=False, input=COMMAND.read_text(encoding="utf-8"),
        cwd=str(tmp_path),
        env=command_env(home=tmp_path,
                        env={**withheld,
                             "OPENREPOTOOLS_BIN_DIR": str(bin_dir)}))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "NOTHING was installed" in result.stderr, result.stderr
    assert (bin_dir / "park").read_text(encoding="utf-8") == \
        "# an older park that still works\n"
    assert not (bin_dir / "resume").exists()
    assert not (tmp_path / ".claude").exists(), (
        "a skill or the hook was placed by a run that could not fetch /swap")


@NEEDS_JQ
def test_install_from_stdin_fetches_itself_into_a_live_workdir(offline_github,
                                                               tmp_path):
    """The documented install line: `gh api …/contents/openRepoTools … |
    bash -s -- --install`.

    Run from stdin there is no file to copy from — not for this command, not
    for its three siblings and not for the four lane helpers, the alias table
    or the skill — so `install_commands` fetches each of the ten at this ref
    into a temporary directory. THAT DIRECTORY HAS TO STILL BE THERE:
    `workdir()` sets its EXIT trap in the main shell rather than inside a
    `$(...)` subshell, whose trap would fire the instant the substitution
    closed and take the directory away before a single fetched byte had landed
    (openRepoShape #74, which made the one-line install impossible on every
    machine).
    """
    bin_dir = tmp_path / "bin"
    result = subprocess.run(
        ["bash", "-s", "--", "--install"], capture_output=True, text=True,
        check=False, input=COMMAND.read_text(encoding="utf-8"),
        # cwd: `bash -s` leaves $BASH_SOURCE unset, so the command's $SELF is
        # the literal `bash`, and `[ -f "$SELF" ]` must be false for the
        # fetching branch to be the one under test. A directory holding
        # nothing of that name is what guarantees it.
        cwd=str(tmp_path),
        env=command_env(home=tmp_path,
                        env={**offline_github,
                             "OPENREPOTOOLS_BIN_DIR": str(bin_dir)}))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "No such file or directory" not in result.stdout + result.stderr
    assert "could not fetch" not in result.stderr
    for name in INSTALLED:
        target = bin_dir / name
        assert target.is_file(), result.stdout + result.stderr + f" ({name})"
        assert stat.S_IMODE(target.stat().st_mode) == 0o755, name
        assert target.read_bytes() == (REPO / name).read_bytes(), name
        assert f"{name}: installed at" in result.stdout


@NEEDS_JQ
def test_a_fetching_install_follows_the_ref_it_was_given(offline_github,
                                                         tmp_path):
    """`$OPENREPOTOOLS_REF` reaches the API path, so a person installing from a
    tag or a branch gets THOSE bytes. The fake `gh` matches on
    `*/contents/<name>?*`, so what this proves is that the run still succeeds
    with the ref set — and the ref is in the query string the route matched."""
    bin_dir = tmp_path / "bin"
    result = subprocess.run(
        ["bash", "-s", "--", "--install"], capture_output=True, text=True,
        check=False, input=COMMAND.read_text(encoding="utf-8"),
        cwd=str(tmp_path),
        env=command_env(home=tmp_path,
                        env={**offline_github,
                             "OPENREPOTOOLS_REF": "some-branch",
                             "OPENREPOTOOLS_BIN_DIR": str(bin_dir)}))
    assert result.returncode == 0, result.stderr + result.stdout
    for name in INSTALLED:
        assert (bin_dir / name).is_file(), name
