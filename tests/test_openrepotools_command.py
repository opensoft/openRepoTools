# SPDX-License-Identifier: Apache-2.0
"""`openRepoTools` — the installer, and the whole of what it does.

OFFLINE, LIKE THE REST OF THIS SUITE. Run from a file, `--install` copies the
bytes beside it and reaches nothing at all; the tests that exercise the
FETCHING path put a fake `gh` first on `$PATH` — `fetch_from_repo` tries the
API before the raw URL, so answering that one call is the whole of the server
they need — and shadow `curl` with a script that refuses, so a run cannot fall
through to the network even if the fake `gh` stops matching. There are FOUR
files to answer for (`openRepoTools`, `park`, `resume`, `status`), because
`--install` places all four or none.

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
import shutil
import stat
import subprocess

from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

COMMAND = REPO / "openRepoTools"

#: EVERY FILE `--install` PLACES. One install line for the whole toolset: a
#: second engineer gets the estate verbs from the README's one line and nothing
#: depends on anyone's dotfiles. `openRepoTools` is first because it is the one
#: a person types to get the other three.
INSTALLED = ("openRepoTools", "park", "resume", "status")

USAGE_LINES = (
    "openRepoTools --install            install (or update) park, resume, status and",
    "                                   this command into ~/.local/bin",
    "openRepoTools --help | --version",
)

#: The command is bash, and Windows has no shebang execution for the fake `gh`
#: either. There is no Windows twin to run instead: on Windows the way in is
#: WSL2, exactly as it is for openRepoShape's `setup.sh`.
pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="openRepoTools is a bash script"),
              WINDOWS_SKIP]


def command_env(home: Path | None = None, env: dict | None = None) -> dict:
    """The environment this suite controls, for a run of the command.

    Every `$OPENREPOTOOLS_*` variable the command reads is cleared first, so a
    developer's own shell cannot change what these tests assert.
    """
    environ = dict(os.environ)
    for name in ("OPENREPOTOOLS_REF", "OPENREPOTOOLS_REPO",
                 "OPENREPOTOOLS_BIN_DIR"):
        environ.pop(name, None)
    if home is not None:
        environ["HOME"] = str(home)
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


def test_help_names_the_three_commands_and_the_standards_front_door():
    """`--install` places four files, and three of them are commands this one
    knows nothing about — so `--help` has to say what they are and where the
    rest is written down. A command a person has on PATH and cannot find
    written down is a command they will not use.

    It also has to say what this command is NOT: `openRepoShape` is the
    standard's front door, and somebody who typed `openRepoTools Atlas`
    expecting a scaffold needs that sentence rather than a usage dump.
    """
    result = run_cmd("--help")
    assert result.returncode == 0, result.stderr
    assert "installs the estate commands and does nothing else" in result.stdout
    assert "park [<Name>]" in result.stdout
    assert "resume [<Name>]" in result.stdout
    assert "status [<Name>]" in result.stdout
    assert "`park --help`, `resume --help` and `status --help`" in result.stdout
    assert "`openRepoShape` is the standard's front door" in result.stdout


def test_help_names_every_variable_it_reads():
    """Three variables, and the file reads exactly these three. A variable the
    script honours and the usage does not name is a variable nobody finds."""
    result = run_cmd("--help")
    for name in ("$OPENREPOTOOLS_REPO", "$OPENREPOTOOLS_REF",
                 "$OPENREPOTOOLS_BIN_DIR"):
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
                     "--dry-run", "-x"]


@pytest.mark.parametrize("argument", NOT_ITS_ARGUMENTS)
def test_anything_else_is_refused_and_names_the_verbs(argument):
    """It installs and it does nothing else. The refusal names `park --help`
    and `resume --help` rather than reprinting the usage: somebody typing
    `openRepoTools park` wants `park`, and the shortest true answer is where it
    is."""
    result = run_cmd(argument)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "installs the estate commands and does nothing else" in result.stderr
    assert "--install," in result.stderr
    assert "--help or --version" in result.stderr
    assert "`park --help`" in result.stderr
    assert "`resume --help`" in result.stderr
    assert "`status --help`" in result.stderr


def test_install_refuses_a_second_argument_and_installs_nothing(tmp_path):
    """`--install` takes no other arguments, and the refusal comes BEFORE
    anything is placed: a run that half-understood its own command line must
    not leave a file behind."""
    bin_dir = tmp_path / "bin"
    result = run_cmd("--install", "Atlas", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "does nothing else" in result.stderr
    assert not bin_dir.exists(), "the refusal placed a file anyway"


# --- --install --------------------------------------------------------------

def test_install_writes_an_executable_copy(tmp_path):
    """All FOUR commands, each 755 and byte-identical to this checkout's.

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
        "a person reading four lines cannot tell whether a fifth was meant "
        "to be there; the count says so")


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
    assert second.stdout.count("unchanged") == len(INSTALLED)


@pytest.mark.parametrize("name", INSTALLED)
def test_install_replaces_a_copy_that_has_drifted(tmp_path, name):
    """Per file, and only the one that drifted: an install that rewrote all
    four every time would have nothing to say about which one was stale."""
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


def test_bin_dir_overrides_where_it_lands(tmp_path):
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(tmp_path / "elsewhere")})
    assert result.returncode == 0, result.stderr
    for name in INSTALLED:
        assert (tmp_path / "elsewhere" / name).is_file(), name
        assert not (tmp_path / ".local" / "bin" / name).exists(), name


def test_install_says_how_to_put_it_on_path(tmp_path):
    """ONE path note for the four of them: the directory is the same one, and
    four copies of the same `export` line reads as four problems."""
    result = run_cmd("--install", home=tmp_path)
    assert f'export PATH="{tmp_path}/.local/bin:$PATH"' in result.stdout
    assert result.stdout.count("export PATH=") == 1


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
        (served / name).write_bytes((REPO / name).read_bytes())

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
    return fake_github(tmp_path, INSTALLED)


def test_install_places_all_four_or_none(tmp_path):
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
    withheld = fake_github(tmp_path, [n for n in INSTALLED if n != "park"])
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


def test_install_from_stdin_fetches_itself_into_a_live_workdir(offline_github,
                                                               tmp_path):
    """The documented install line: `gh api …/contents/openRepoTools … |
    bash -s -- --install`.

    Run from stdin there is no file to copy from — not for this command and not
    for its three siblings — so `install_commands` fetches each of the four at
    this ref into a temporary directory. THAT DIRECTORY HAS TO STILL BE THERE:
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
