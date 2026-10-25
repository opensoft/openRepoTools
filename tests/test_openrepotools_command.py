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

import bisect
import hashlib
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time

from datetime import datetime
from pathlib import Path

import pytest

import package_layout as layout
from conftest import REPO, ROOTS, WINDOWS_SKIP

COMMAND = REPO / "openRepoTools"

#: EVERY FILE `--install` PLACES INTO THE BIN DIRECTORY. One install line for
#: the whole toolset: a second engineer gets the estate verbs AND the lane
#: helpers from the README's one line and nothing depends on anyone's dotfiles.
#: `openRepoTools` is first because it is the one a person types to get the
#: others; the last five came here from `opensoft/brett-wip` with their history
#: under lane-collision-protocol Amendment 9(b), and `repos.tsv` is data placed
#: at 755 with the commands because `--install` has one list, one destination
#: and one mode.
#:
#: `lane` TAKES `restart`'s PLACE AND THE COUNT DOES NOT MOVE (Amendment 18
#: Addendum 1, the word, and Addendum 2, the retirement — ratified
#: 2026-09-14T14:05:54Z and 16:50:32Z). `lane <name>` is `restart <lane>`'s act
#: — the launcher's path, the lane's own recorded directory and profile, asking
#: nothing — plus the numbered pick, the attach and the handoff branch, so what
#: a person is given is one word instead of two. `lane-handoff` joined beside it
#: under Amendment 17(a), which made the list TWELVE; `lane-rename` joined it
#: under Amendment 16 (ratified 2026-09-14T09:24:35Z), whose clause (h) is why
#: it is a word rather than a `lanes` option — `lanes` writes nothing and a
#: rename is four files in one commit — which made the list THIRTEEN.
#: `claude-current` and `claude-restart-check` joined it for
#: opensoft/workBenches#119 (Brett Heap's home ruling of 2026-09-29), at the END
#: so every index taken below still names the file it did, which made the list
#: FIFTEEN. `lanes-index` joined it for opensoft/openRepoTools#160
#: (lane-collision-protocol Amendment 14, ratified 2026-10-05), at the END for
#: the same reason, and it is the one command in the list that is Python rather
#: than bash, which made the list SIXTEEN. `lane-worktrees` joined it for
#: opensoft/openRepoTools#162 (Brett Heap's word of 2026-10-05, "build 162"),
#: at the END for the same reason, and Python like `lanes-index`: the list is
#: what follows.
INSTALLED = ("openRepoTools", "park", "resume", "status", "lane", "lanes",
             "lane-handoff", "lane-rename", "lanes-edit.sh", "lane-start",
             "lane-end", "link-estates", "repos.tsv", "claude-current",
             "claude-restart-check", "lanes-index", "lane-worktrees")

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

#: Everything a stdin install has to fetch: the files, the skills and the
#: command files.
FETCHED = INSTALLED + SKILL_PATHS + COMMAND_PATHS

#: THIRTY-ONE ARTIFACTS, AND THE COUNT IS THE INVARIANT: one file per `INSTALLED`
#: name in the bin directory, one skill per `SKILL_NAMES` name in the shared
#: skills directory, its bare-run copy, one command file per `COMMAND_NAMES`
#: name at that same pair of destinations, and TWO merged entries in
#: `~/.claude/settings.json`. Derived from the three
#: lists rather than restated, so adding a skill or a command moves it.
#:
#: THE `HOOK_ENTRIES` IS THE ONE TERM THAT IS NOT A LIST, and it moved from 1
#: to 2 on 2026-09-14 for lane-collision-protocol Amendment 12 adoption act 3:
#: the `UserPromptSubmit` NAME GUARD entry is placed beside the `SessionStart`
#: one, in the same file, under the same all-or-nothing merge. There is no list
#: of hook entries to derive it from — the two are different events with
#: different shapes, one with a matcher and one without, and one carrying
#: `|| true` where the other must not — so this is the number that is
#: hand-kept, and the assertions below are what notice when it stops being true.
#:
#: AND SINCE opensoft/openRepoTools#237 THE TWO ARE CONDITIONAL: `--install`
#: merges them only once `~/projects/xFactory/lanes-edit.sh` — the path both
#: call — exists, is executable and answers `guard`, which is the
#: `claude-profile` launcher's own rule. So the count is `ALWAYS` (twenty-nine)
#: on every run, plus `HOOK_ENTRIES` once that path answers; a test that means
#: the thirty-one links it first, with `link_xfactory` below.
HOOK_ENTRIES = 2
ALWAYS = len(INSTALLED) + 2 * len(SKILL_NAMES) + 2 * len(COMMAND_NAMES)
ARTIFACTS = ALWAYS + HOOK_ENTRIES

USAGE_LINES = (
    "openRepoTools --install            install (or update) the seventeen estate and",
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
#: two of its thirty-one artifacts are merged entries inside a JSON file somebody
#: else owns, and the clause has it refuse naming `jq` rather than rewriting
#: that file by hand. So a run of `--install` on a host without `jq` is a
#: REFUSAL BY DESIGN, and a test that asserts a successful placement there is
#: asserting against the contract. Marked rather than left to fail, because a
#: red suite on a minimal image is how a fork stops being finished — the same
#: reason `AGENTS.md` gives for the submodule SKIP.
#:
#: The tests NOT marked are the ones that never reach the merge: the refusals,
#: `--help`, `--version`, and `test_install_places_all_or_none`, which is
#: refused at `collect_commands` before `plan_hook_merge` is called at all.
#: `test_without_jq_it_refuses_and_places_nothing` is the positive case for the
#: same fact and is deliberately unmarked.
NEEDS_JQ = pytest.mark.skipif(
    shutil.which("jq") is None,
    reason="`--install` merges two hook entries with jq (Amendment 9(b), Amendment 12 act 3)")


#: A MODE-000 FILE IS ONLY UNREADABLE TO SOMEBODY WHO IS NOT ROOT. The same
#: idiom `tests/test_install_skill_and_hook.py` carries for the destinations it
#: makes unwritable: a root `--install` opens whatever it likes, so the cases
#: that need a receipt it CANNOT open are skipped there, not made to pass.
NOT_ROOT = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root can read a file whose mode says otherwise")


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

    AND `$XDG_DATA_HOME` IS CLEARED FOR THAT SAME REASON (#57). Since
    `--install` writes its receipt to
    `${OPENREPOTOOLS_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/openRepoTools}`,
    a developer who exports `$XDG_DATA_HOME` — and on a Linux desktop that is
    a normal thing to have exported — would have this suite writing into their
    real data directory however carefully `$HOME` was redirected. Cleared, the
    default applies, the default hangs off `$HOME`, and every byte lands in
    `tmp_path`. `$OPENREPOTOOLS_DATA_DIR` is cleared with the rest of the
    `$OPENREPOTOOLS_*` family, so a developer's own shell cannot move what
    these tests assert about.
    """
    environ = dict(os.environ)
    for name in ("OPENREPOTOOLS_REF", "OPENREPOTOOLS_REPO",
                 "OPENREPOTOOLS_BIN_DIR", "OPENREPOTOOLS_DATA_DIR",
                 "XDG_DATA_HOME", "CLAUDE_PROFILES_HOME",
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
            env: dict | None = None,
            cwd: Path | None = None) -> subprocess.CompletedProcess:
    """The command, run from its file, with that environment.

    `input=""` means stdin is a pipe rather than a terminal, which is what
    every run in this file wants: nothing here may ask a question.

    `cwd` is for the tests that name a RELATIVE path — a `$OPENREPOTOOLS_BIN_DIR`
    spelled `bin` means a different directory from every working directory it
    is run in, and that is exactly what they are about (#57, Copilot on #103).
    """
    return subprocess.run(["bash", str(COMMAND), *args], capture_output=True,
                          text=True, check=False, input="",
                          env=command_env(home, env), cwd=cwd)


def link_xfactory(home: Path, target: Path | None = None) -> Path:
    """`~/projects/xFactory/lanes-edit.sh` the way `link-estates` leaves it: a
    symlink to the bin directory's `lanes-edit.sh` (#237).

    The hook pair is merged only once that path answers `guard`, so a test
    that asserts the pair is placed links it first. Made BEFORE the install it
    is for, it dangles until that install's bin loop places the far end — which
    is the order the gate asks in, after that loop. `target` names another far
    end, for a test whose bin directory is not `~/.local/bin`.
    """
    link = home / "projects" / "xFactory" / "lanes-edit.sh"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target if target is not None
                    else home / ".local" / "bin" / "lanes-edit.sh")
    return link


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
    """`--install` places everything `INSTALLED` lists, and most of it is commands
    this one knows nothing about — so `--help` has to say what they are and
    where the rest is written down. A command a person has on PATH and cannot
    find written down is a command they will not use.

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
                 "lanes-edit.sh <verb>", "link-estates", "repos.tsv",
                 "claude-current [--porcelain]", "claude-restart-check",
                 "lanes-index sync|reconcile|status",
                 "lane-worktrees sweep <lane>"):
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
                 "$OPENREPOTOOLS_BIN_DIR", "$OPENREPOTOOLS_DATA_DIR",
                 "$XDG_DATA_HOME", "$AGENT_PROTOCOL_ROOT",
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
    """A checkout and the one-line install name the repository and the ref
    they fetch from: the honest answer to `--version` there is WHICH BYTES it
    will fetch. A package names its release instead, from its own stamp, and
    no `OPENREPOTOOLS_PACKAGE_*` variable changes what a checkout prints."""
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
    """Every `INSTALLED` file, each 755 and byte-identical to this checkout's.

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
    link_xfactory(tmp_path)
    first = run_cmd("--install", home=tmp_path)
    assert first.returncode == 0, first.stderr
    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    for name in INSTALLED:
        assert f"{name}: already installed at" in second.stdout, name
    # EVERY ARTIFACT, not only `INSTALLED`: the skill and command-file copies
    # and BOTH hook entries each report `unchanged` too, and the count is the
    # invariant Amendment 9(b) names — derived from the three lists, never
    # restated, so a new skill or command moves it. It was eighteen until
    # Amendment 12 adoption act 3 put the name guard beside the SessionStart
    # entry, which is the `HOOK_ENTRIES` term above — and the two count only
    # because `link_xfactory` gave them a target that answers `guard` (#237);
    # without it the count is `ALWAYS` (`tests/test_install_hook_gate.py`).
    assert second.stdout.count("unchanged") == ARTIFACTS


@pytest.mark.parametrize("name", INSTALLED)
@NEEDS_JQ
def test_install_replaces_a_copy_that_has_drifted(tmp_path, name):
    """Per file, and only the one that drifted: an install that rewrote all of
    `INSTALLED` every time would have nothing to say about which one was stale."""
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


# --- every placement is a RENAME, never a rewrite in place (#167) ----------
#
# `cp` onto an installed file keeps its inode and rewrites its bytes, and bash
# reads a script from its file WHILE it runs it: after every command that forks
# it seeks back to where it had got to and reads on from there. So a lane tool
# that was running when an install replaced it went on reading the NEW text
# from the OLD offset — measured on 2026-09-30 as `A.sh: line 4: ript,: command
# not found`, then the new text's commands run from its middle. A rename puts a
# new inode at the path and leaves the old one to whoever has it open.

#: THE TEXT A LANE TOOL IS RUNNING WHEN THE INSTALL REPLACES IT. It announces
#: itself, then waits — `sleep` forks, which is what makes bash seek back and
#: read on from its file — until `$GO` exists, then finishes. Bounded, so a
#: test that fails before it says go leaves no process behind for long.
OLD_RUNNING = ("#!/usr/bin/env bash\n"
               "printf 'old: started\\n'\n"
               'i=0; until [ -e "$GO" ] || [ "$i" -ge 1200 ]; do '
               'sleep 0.05; i=$((i + 1)); done\n')
OLD_TAIL = "printf 'old: finished\\n'\nexit 0\n"


def new_text_read_from(offset: int) -> str:
    """NEW bytes with a line of their own starting at exactly `offset`.

    That is the byte the running OLD text resumes reading at once its wait is
    over. In place, the process reads THIS line instead of its own next one,
    says so and exits 7. By rename it never sees these bytes at all. Built to
    the offset rather than left to chance, so the failure a regression prints
    is one line that says what happened.
    """
    head = "#!/usr/bin/env bash\n# "
    assert offset > len(head), "the old text is shorter than the new header"
    return (head + "x" * (offset - len(head) - 1) + "\n"
            + "printf 'new: read from the old offset\\n'; exit 7\n")


def source_tree(root: Path) -> Path:
    """A copy of everything `--install` reads beside itself, for a test that
    needs the NEW bytes to be its own. Run from a file, the command copies
    what is beside it and fetches nothing, so the copy is complete or the run
    would try the network, which this suite never reaches."""
    src = root / "src"
    for rel in ("openRepoTools",) + FETCHED:
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, src / rel)
    return src


def install_from(src: Path, home: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(src / "openRepoTools"), "--install"],
                          capture_output=True, text=True, check=False,
                          input="", env=command_env(home))


def placement_temporaries(home: Path) -> list[str]:
    """Every `.<name>.openrepotools.*` left in a directory `--install` writes:
    a temporary a placement made and never renamed or removed."""
    dirs = [home / ".local" / "bin", home / ".claude",
            home / ".claude" / "commands",
            home / ".claude-profiles" / "shared" / "commands"]
    for name in SKILL_NAMES:
        dirs += [home / ".claude" / "skills" / name,
                 home / ".claude-profiles" / "shared" / "skills" / name]
    return sorted(str(p) for d in dirs if d.is_dir() for p in d.iterdir()
                  if ".openrepotools." in p.name)


def one_of_each_kind(home: Path) -> list[tuple[Path, Path, int]]:
    """`(target, source, mode)` for a command, a skill and a command file, at
    every destination each one has."""
    skill, command = SKILL_NAMES[0], COMMAND_NAMES[0]
    return [
        (home / ".local" / "bin" / "lanes-edit.sh", REPO / "lanes-edit.sh",
         0o755),
        (home / ".claude-profiles" / "shared" / "skills" / skill / "SKILL.md",
         REPO / SKILL_PATHS[0], 0o644),
        (home / ".claude" / "skills" / skill / "SKILL.md",
         REPO / SKILL_PATHS[0], 0o644),
        (home / ".claude-profiles" / "shared" / "commands" / f"{command}.md",
         REPO / COMMAND_PATHS[0], 0o644),
        (home / ".claude" / "commands" / f"{command}.md",
         REPO / COMMAND_PATHS[0], 0o644),
    ]


@NEEDS_JQ
def test_a_running_lane_tool_finishes_on_its_own_text_when_an_install_replaces_it(
        tmp_path):
    """THE DEFECT ITSELF, END TO END (#167).

    A lane tool is running from its installed path — `lanes-edit.sh` here,
    the one whose register writes run longest — when `--install` replaces
    it with newer bytes. The process must finish on the text it started with,
    and the path must hold the new text afterwards. Written in place, the
    process reads the new text from the old offset instead: it prints
    `new: read from the old offset` and exits 7.
    """
    src = source_tree(tmp_path)
    home = tmp_path / "home"
    first = install_from(src, home)
    assert first.returncode == 0, first.stdout + first.stderr
    name = "lanes-edit.sh"
    target = home / ".local" / "bin" / name
    target.write_text(OLD_RUNNING + OLD_TAIL, encoding="utf-8")
    new = new_text_read_from(len(OLD_RUNNING))
    (src / name).write_text(new, encoding="utf-8")

    go = tmp_path / "go"
    running = subprocess.Popen(["bash", str(target)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               env={**os.environ, "GO": str(go)})
    try:
        assert running.stdout.readline() == "old: started\n"
        second = install_from(src, home)
        assert second.returncode == 0, second.stdout + second.stderr
        assert f"{name}: updated at {target}" in second.stdout, second.stdout
        go.touch()
        out, err = running.communicate(timeout=120)
    finally:
        if running.poll() is None:
            running.kill()
            running.communicate()
    assert (out, err, running.returncode) == ("old: finished\n", "", 0), (
        "the running copy did not finish on its own text — the install "
        f"rewrote the file under it:\nstdout {out!r}\nstderr {err!r}\n"
        f"exit {running.returncode}")
    assert target.read_text(encoding="utf-8") == new
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    assert placement_temporaries(home) == []


@NEEDS_JQ
def test_every_placement_replaces_its_target_rather_than_rewriting_it(tmp_path):
    """A NEW INODE AT EVERY PATH THAT CHANGED, AND THE OLD ONE LEFT WHOLE.

    One of each kind `--install` writes — a command, a skill and a command
    file — at every destination each one has. Each is drifted, and held OPEN
    the way a running process holds its script, before the install that
    repairs it. Afterwards the path holds the right bytes at the right mode
    under a different inode, and the handle still reads the drifted bytes
    whole. In place, the inode is the same one and the handle reads the new
    bytes. A `SKILL.md` executes nothing, but one way to place a file is one
    rule to read, and a session that opens it mid-install sees the old text or
    the new, never a truncated one.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    held = []
    try:
        for target, source, mode in one_of_each_kind(tmp_path):
            drifted = target.read_bytes() + b"# drift\n"
            target.write_bytes(drifted)
            handle = target.open("rb")
            held.append((target, source, mode, drifted,
                         os.fstat(handle.fileno()).st_ino, handle))
        result = run_cmd("--install", home=tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        for target, source, mode, drifted, inode, handle in held:
            assert f"updated at {target}" in result.stdout, target
            assert target.stat().st_ino != inode, (
                f"{target} was rewritten in place: same inode {inode}")
            assert handle.read() == drifted, (
                f"a reader holding the old {target} saw the new bytes")
            assert target.read_bytes() == source.read_bytes(), target
            assert stat.S_IMODE(target.stat().st_mode) == mode, target
    finally:
        for *_, handle in held:
            handle.close()
    assert placement_temporaries(tmp_path) == []


@NEEDS_JQ
def test_an_install_that_changes_no_byte_renames_nothing(tmp_path):
    """THE `cmp -s` SKIP STAYS (#167). A path whose bytes are already right
    keeps its inode on a second run: renaming every file on every run would
    turn an install that changed nothing into thirty-odd new inodes."""
    assert run_cmd("--install", home=tmp_path).returncode == 0
    targets = [tmp_path / ".local" / "bin" / n for n in INSTALLED]
    targets += [t for t, _, _ in one_of_each_kind(tmp_path)]
    before = {t: t.stat().st_ino for t in targets}
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {t: t.stat().st_ino for t in targets} == before


@pytest.mark.parametrize("tool, says", [
    ("cp", "could not write"),
    ("chmod", "could not set mode 755 on"),
    ("mv", "could not move the new"),
])
@NEEDS_JQ
def test_a_placement_that_fails_leaves_the_old_copy_and_no_temporary(
        tmp_path, tool, says):
    """EACH STEP OF THE RENAME CAN FAIL, AND NONE OF THEM COSTS THE OLD COPY.

    A `cp` into the temporary, the mode stamp on it, or the `mv` over the
    target is refused for ONE command by a fake first on `$PATH` that defers to
    the real tool for everything else. The run refuses (2) naming the target,
    the command already installed there keeps its bytes and its inode, no
    temporary is left beside it, and the loop goes no further.
    """
    real = shutil.which(tool)
    if real is None:
        pytest.skip(f"no real `{tool}` on PATH for the fake to defer to")
    assert run_cmd("--install", home=tmp_path).returncode == 0
    bin_dir = tmp_path / ".local" / "bin"
    name = INSTALLED[1]
    target = bin_dir / name
    old = target.read_bytes() + b"# an older copy\n"
    target.write_bytes(old)
    inode = target.stat().st_ino
    shim = tmp_path / f"fake-{tool}"
    shim.mkdir()
    (shim / tool).write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '\tcase "$arg" in\n'
        f'\t"{bin_dir}/.{name}.openrepotools."*)\n'
        f"\t\tprintf 'fake {tool}: refused\\n' >&2\n"
        "\t\texit 1 ;;\n"
        "\tesac\n"
        "done\n"
        f'exec {real} "$@"\n', encoding="utf-8")
    (shim / tool).chmod(0o755)

    result = run_cmd("--install", home=tmp_path,
                     env={"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "REFUSED:" in result.stderr, result.stderr
    assert f"{says} {target}" in result.stderr, result.stderr
    assert target.read_bytes() == old, "the old copy was not left as it was"
    assert target.stat().st_ino == inode, "the old copy was replaced"
    assert placement_temporaries(tmp_path) == []
    assert f"{INSTALLED[2]}: " not in result.stdout, (
        "the loop carried on past a placement it could not make")


def fake_owner_ls(root: Path, target: Path, uid: int, gid: int) -> Path:
    """A `ls` first on `$PATH` that says `target` belongs to `uid:gid`, and is
    the real one for every other path. OWNERSHIP IS WHAT THIS STANDS IN FOR,
    as the fake `chmod` above stands in for it: no fixture here can make a file
    another account owns, and `owner_of` asks `ls -lnd` and nothing else."""
    real = shutil.which("ls")
    if real is None:
        pytest.skip("no real `ls` on PATH for the fake to defer to")
    shim = root / "fake-ls"
    shim.mkdir()
    (shim / "ls").write_text(
        "#!/bin/sh\n"
        'last=""\n'
        'for arg in "$@"; do last="$arg"; done\n'
        f'if [ "$last" = "{target}" ]; then\n'
        f"\tprintf '%s\\n' '-rwxr-xr-x 1 {uid} {gid} 1 Jan  1 00:00 {target}'\n"
        "\texit 0\n"
        "fi\n"
        f'exec {real} "$@"\n', encoding="utf-8")
    (shim / "ls").chmod(0o755)
    return shim


@NEEDS_JQ
def test_a_replaced_copy_is_handed_back_to_the_account_that_owned_it(tmp_path):
    """THE OWNER STAYS WHO IT WAS (Copilot on #172).

    A rename puts the temporary's inode at the path, and the temporary belongs
    to whoever ran the install — so a root `--install` into another user's
    home would leave that user root-owned copies their own next `--install`
    refuses as unwritable. `cp` kept the owner by keeping the inode. So where
    the owner differs, the temporary is given the target's uid AND gid before
    the rename: the `chown` is asked for exactly once, on the temporary, with
    the old owner. A fake records it, because only root could make it.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    bin_dir = tmp_path / ".local" / "bin"
    name = INSTALLED[1]
    target = bin_dir / name
    target.write_bytes(target.read_bytes() + b"# drift\n")
    uid, gid = os.getuid() + 4242, os.getgid() + 4243
    ls_shim = fake_owner_ls(tmp_path, target, uid, gid)
    log = tmp_path / "chown.log"
    chown_shim = tmp_path / "fake-chown"
    chown_shim.mkdir()
    (chown_shim / "chown").write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> '{log}'\n"
        "exit 0\n", encoding="utf-8")
    (chown_shim / "chown").chmod(0o755)

    result = run_cmd("--install", home=tmp_path, env={
        "PATH": os.pathsep.join([str(ls_shim), str(chown_shim),
                                 os.environ["PATH"]])})
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{name}: updated at {target}" in result.stdout, result.stdout
    calls = log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 1, calls
    assert re.fullmatch(
        rf"-- {uid}:{gid} {re.escape(str(bin_dir))}/\.{re.escape(name)}"
        r"\.openrepotools\.\S+", calls[0]), calls
    assert target.read_bytes() == (REPO / name).read_bytes()
    assert placement_temporaries(tmp_path) == []


@NOT_ROOT
@NEEDS_JQ
def test_a_copy_another_account_owns_is_refused_and_left_as_it_was(tmp_path):
    """AND WHERE THE OWNER CANNOT BE KEPT, NOTHING IS TAKEN OVER (Copilot on
    #172). An account that is not root may not give a file away, so the real
    `chown` refuses, and a rename would leave the other account's file this
    account's. The run refuses (2) naming the owner, the old copy keeps its
    bytes and its inode, and no temporary is left beside it.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    bin_dir = tmp_path / ".local" / "bin"
    name = INSTALLED[1]
    target = bin_dir / name
    old = target.read_bytes() + b"# another account's copy\n"
    target.write_bytes(old)
    inode = target.stat().st_ino
    uid = os.getuid() + 4242
    ls_shim = fake_owner_ls(tmp_path, target, uid, os.getgid() + 4243)

    result = run_cmd("--install", home=tmp_path, env={
        "PATH": f"{ls_shim}{os.pathsep}{os.environ['PATH']}"})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "REFUSED:" in result.stderr, result.stderr
    assert f"{target} belongs to uid {uid}" in result.stderr, result.stderr
    assert target.read_bytes() == old
    assert target.stat().st_ino == inode
    assert placement_temporaries(tmp_path) == []
    assert f"{INSTALLED[2]}: " not in result.stdout, (
        "the loop carried on past a placement it refused")


@NEEDS_JQ
def test_a_copy_whose_owner_cannot_be_read_is_refused_and_left_as_it_was(
        tmp_path):
    """AN OWNER NOBODY COULD READ IS NOT "NOTHING TO KEEP" (Copilot on #172 at
    bef4b85). `owner_of` answers nothing where `ls` cannot say, and an empty
    answer is what an ABSENT target gives — so a target that EXISTS and whose
    owner could not be read was renamed over with this run's own temporary, and
    a root `--install` took the file over after all. A `ls` first on `$PATH`
    that fails for that one path stands in for the unreadable owner: the run
    refuses (2) naming the target, the old copy keeps its bytes and its inode,
    and no temporary is left beside it.
    """
    real = shutil.which("ls")
    if real is None:
        pytest.skip("no real `ls` on PATH for the fake to defer to")
    assert run_cmd("--install", home=tmp_path).returncode == 0
    bin_dir = tmp_path / ".local" / "bin"
    name = INSTALLED[1]
    target = bin_dir / name
    old = target.read_bytes() + b"# a copy whose owner cannot be read\n"
    target.write_bytes(old)
    inode = target.stat().st_ino
    shim = tmp_path / "failing-ls"
    shim.mkdir()
    (shim / "ls").write_text(
        "#!/bin/sh\n"
        'last=""\n'
        'for arg in "$@"; do last="$arg"; done\n'
        f'if [ "$last" = "{target}" ]; then\n'
        "\tprintf 'ls: cannot read %s\\n' \"$last\" >&2\n"
        "\texit 2\n"
        "fi\n"
        f'exec {real} "$@"\n', encoding="utf-8")
    (shim / "ls").chmod(0o755)

    result = run_cmd("--install", home=tmp_path, env={
        "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "REFUSED:" in result.stderr, result.stderr
    assert f"could not read who owns {target}" in result.stderr, result.stderr
    assert target.read_bytes() == old
    assert target.stat().st_ino == inode
    assert placement_temporaries(tmp_path) == []
    assert f"{INSTALLED[2]}: " not in result.stdout, (
        "the loop carried on past a placement it refused")


@NEEDS_JQ
def test_a_group_that_cannot_be_kept_does_not_stop_the_placement(tmp_path):
    """THE GROUP IS KEPT WHERE IT CAN BE, AND IS NO REASON TO REFUSE (Copilot
    round 2 on #172). The owner is this account and the group is one it is not
    in, so the real `chown` to that group is refused. At 755 and 644 the
    group's bits are the other bits, so nobody gains or loses a permission by
    it: the copy is placed, as `cp` placed it.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    bin_dir = tmp_path / ".local" / "bin"
    name = INSTALLED[1]
    target = bin_dir / name
    target.write_bytes(target.read_bytes() + b"# drift\n")
    ls_shim = fake_owner_ls(tmp_path, target, os.getuid(), os.getgid() + 4243)

    result = run_cmd("--install", home=tmp_path, env={
        "PATH": f"{ls_shim}{os.pathsep}{os.environ['PATH']}"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{name}: updated at {target}" in result.stdout, result.stdout
    assert target.read_bytes() == (REPO / name).read_bytes()
    assert placement_temporaries(tmp_path) == []


#: THE TWO PLACES A SIGNAL CAN FIND A TEMPORARY. A slow `cp` holds the run
#: between `mktemp` and `mv`. A slow `mktemp` holds it AFTER the file is made
#: and BEFORE its name comes back — the window Copilot's round 2 on #172 named,
#: which a name learnt from `mktemp`'s answer could not cover. Each defers to
#: the real tool and is slow only for a temporary.
SLOW_TOOLS = {
    "cp": ('for arg in "$@"; do\n'
           '\tcase "$arg" in *.openrepotools.*) sleep 3 ;; esac\n'
           'done\n'
           'exec {real} "$@"\n'),
    "mktemp": ('made=$({real} "$@") || exit $?\n'
               'case "$made" in *.openrepotools.*) sleep 3 ;; esac\n'
               "printf '%s\\n' \"$made\"\n"),
}


@pytest.mark.parametrize("slow", sorted(SLOW_TOOLS))
@pytest.mark.parametrize("signame, to_group", [
    ("SIGTERM", False),   # a `kill` from another shell
    ("SIGINT", True),     # Ctrl-C: the whole foreground process group
])
@NEEDS_JQ
def test_a_run_killed_mid_placement_leaves_no_temporary(tmp_path, signame,
                                                         to_group, slow):
    """THE `EXIT` TRAP REMOVES WHAT A PLACEMENT HAS NOT YET RENAMED (#167).

    `place_by_rename` removes its temporary on every failure it sees; a signal
    is one it cannot see, which is what `$PLACING` and the trap `workdir`
    sets are for. A tool first on `$PATH` that is SLOW for a temporary holds
    the run where one exists; the signal lands there. The run dies of it, and
    nothing named `.<name>.openrepotools.*` is left beside a target. Without
    the trap's clause every one of these leaves it behind, and with a trap that
    knew only `mktemp`'s answer the Ctrl-C into a slow `mktemp` still did.

    THE CHILD STARTS WITH BOTH SIGNALS AT THEIR DEFAULT, as a foreground job at
    a terminal has them. A runner started in the background by a
    non-interactive shell (`nohup pytest … &`) has SIGINT IGNORED, an ignored
    signal survives `exec`, and a shell may not un-ignore one it was started
    with — so without this the case would measure the runner, not the trap.
    """
    real = shutil.which(slow)
    if real is None:
        pytest.skip(f"no real `{slow}` on PATH for the slow one to defer to")
    shim = tmp_path / f"slow-{slow}"
    shim.mkdir()
    (shim / slow).write_text(
        "#!/bin/sh\n" + SLOW_TOOLS[slow].format(real=real), encoding="utf-8")
    (shim / slow).chmod(0o755)
    sig = getattr(signal, signame)

    def default_signals() -> None:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    run = subprocess.Popen(
        ["bash", str(COMMAND), "--install"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=command_env(tmp_path, {
            "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}),
        start_new_session=True, preexec_fn=default_signals)
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not placement_temporaries(tmp_path):
            time.sleep(0.05)
        assert placement_temporaries(tmp_path), (
            "no placement ever made a temporary for the signal to land beside")
        if to_group:
            os.killpg(run.pid, sig)
        else:
            run.send_signal(sig)
        out, err = run.communicate(timeout=60)
    finally:
        if run.poll() is None:
            os.killpg(run.pid, signal.SIGKILL)
            run.communicate()
    assert run.returncode in (-sig, 128 + sig), (
        f"the run did not die of {signame}: exit {run.returncode}\n{out}{err}")
    assert placement_temporaries(tmp_path) == []


#: THE INSTANTS THE TEST ABOVE MEETS ABOUT ONCE IN A HUNDRED RUNS, MET EVERY
#: TIME (#250). That test signals when a temporary shows up, and bash takes the
#: signal wherever it happens to be. This library is built at test time and
#: preloaded into the installer's bash, and it sends the signal from INSIDE the
#: shell, at one instant (`ORT_HOOK_AT`), once a `.openrepotools.` name is in
#: `ORT_HOOK_DIR`:
#:
#: * `fork`: just after the shell forks a command, in the parent, while bash
#:   still has the signal blocked, so bash takes it before it has closed that
#:   command's pipeline;
#: * `waitpid`: while the shell is blocked waiting for a child, polling until
#:   a temporary exists, which is the wait for `mktemp` once it made the file;
#: * `forkwait`: armed by the first such fork, in the shell's next blocking
#:   wait, which is the wait for that command.
#:
#: Only the process-group leader fires (the installer, started in a session of
#: its own), and only once. It leaves `ORT_HOOK_MARK` first, so a case that
#: never reached its instant fails as that, rather than passing.
SIGNAL_HOOK_C = r"""
#define _GNU_SOURCE
#include <dirent.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static int fired, armed;

static int temporary_exists(void)
{
	const char *dir = getenv("ORT_HOOK_DIR");
	DIR *d;
	struct dirent *e;
	int found = 0;

	if (dir == NULL || (d = opendir(dir)) == NULL)
		return 0;
	while ((e = readdir(d)) != NULL)
		if (strstr(e->d_name, ".openrepotools.") != NULL) {
			found = 1;
			break;
		}
	closedir(d);
	return found;
}

static int wanted(const char *at)
{
	const char *want = getenv("ORT_HOOK_AT");

	return !fired && want != NULL && strcmp(want, at) == 0 &&
	       getpid() == getpgrp();
}

static void fire(void)
{
	const char *sig = getenv("ORT_HOOK_SIG");
	const char *mark = getenv("ORT_HOOK_MARK");
	int fd;

	fired = 1;
	if (mark != NULL &&
	    (fd = open(mark, O_WRONLY | O_CREAT | O_TRUNC, 0644)) >= 0)
		close(fd);
	kill(getpid(), sig != NULL ? atoi(sig) : SIGINT);
}

pid_t fork(void)
{
	static pid_t (*real)(void);
	int now, then;
	pid_t pid;

	if (real == NULL)
		real = (pid_t (*)(void))dlsym(RTLD_NEXT, "fork");
	now = wanted("fork") && temporary_exists();
	then = wanted("forkwait") && !armed && temporary_exists();
	pid = real();
	if (pid > 0 && now)
		fire();
	if (pid > 0 && then)
		armed = 1;
	return pid;
}

pid_t waitpid(pid_t pid, int *status, int options)
{
	static pid_t (*real)(pid_t, int *, int);
	struct timespec pause = { 0, 1000000 };
	pid_t got;

	if (real == NULL)
		real = (pid_t (*)(pid_t, int *, int))dlsym(RTLD_NEXT, "waitpid");
	if ((options & WNOHANG) == 0 && wanted("forkwait") && armed) {
		fire();
	} else if ((options & WNOHANG) == 0 && wanted("waitpid")) {
		for (;;) {
			if (temporary_exists()) {
				fire();
				break;
			}
			got = real(pid, status, options | WNOHANG);
			if (got != 0) {
				if (got > 0 && temporary_exists())
					fire();
				return got;
			}
			nanosleep(&pause, NULL);
		}
	}
	return real(pid, status, options);
}
"""


@pytest.fixture(scope="module")
def signal_hook(tmp_path_factory) -> Path:
    """`SIGNAL_HOOK_C` built, and seen to fire in this bash at a fork and at a
    wait, or a skip that names which of the three it lacks: Linux's loader, a
    `cc`, or a bash whose own `fork` and `waitpid` the library can stand in
    front of. The proof is a bash that forks and waits once, with a temporary
    already in the hook's directory and signal 0, which sends nothing."""
    if not sys.platform.startswith("linux"):
        pytest.skip("the signal hook is an LD_PRELOAD library for Linux's loader")
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("no `cc` to build the signal hook with")
    where = tmp_path_factory.mktemp("signal-hook")
    source, hook = where / "hook.c", where / "hook.so"
    source.write_text(SIGNAL_HOOK_C, encoding="utf-8")
    built = subprocess.run([cc, "-shared", "-fPIC", "-o", str(hook),
                            str(source), "-ldl"],
                           capture_output=True, text=True, check=False)
    if built.returncode != 0:
        pytest.skip(f"`cc` could not build the signal hook: {built.stderr}")
    probe = where / "probe"
    probe.mkdir()
    (probe / ".probe.openrepotools.0").touch()
    sh = shutil.which("sh") or "/bin/sh"
    for at in ("fork", "waitpid"):
        mark = where / f"fired-{at}"
        ran = subprocess.run(
            ["bash", "-c", '"$0" -c :; "$0" -c :', sh],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            check=False, timeout=60, start_new_session=True,
            env={**os.environ, "LD_PRELOAD": str(hook),
                 "ORT_HOOK_DIR": str(probe), "ORT_HOOK_AT": at,
                 "ORT_HOOK_SIG": "0", "ORT_HOOK_MARK": str(mark)})
        if not mark.exists():
            pytest.skip(f"bash never reached the signal hook at `{at}` "
                        f"(exit {ran.returncode}): {ran.stderr.strip()}")
    return hook


#: WAITS FOR THE HOOK'S MARK, BOUNDED: after ten seconds it goes on regardless.
WAIT_FOR_MARK = ('i=0; while [ ! -e "$ORT_HOOK_MARK" ] && [ "$i" -lt 200 ]; '
                 'do sleep 0.05; i=$((i + 1)); done\n')

#: THE STAND-IN EACH CASE PUTS FIRST ON `$PATH`, different for a temporary
#: only: a `cp` that refuses to write one; a `mktemp` that makes one, answers,
#: closes its output and stays until the hook has fired, so the shell is
#: still waiting for it; and a `cp` that holds the copy until the hook has
#: fired, then makes it.
HOOKED_TOOLS = {
    "cp-refuses": ("cp", 'for arg in "$@"; do\n'
                         '\tcase "$arg" in *.openrepotools.*)\n'
                         "\t\tprintf 'fake cp: refused\\n' >&2\n"
                         '\t\texit 1 ;;\n'
                         '\tesac\n'
                         'done\n'
                         'exec {real} "$@"\n'),
    "mktemp-stays": ("mktemp", 'made=$({real} "$@") || exit $?\n'
                               "printf '%s\\n' \"$made\"\n"
                               'case "$made" in *.openrepotools.*)\n'
                               '\texec >&-\n'
                               '\t' + WAIT_FOR_MARK +
                               '\t;;\n'
                               'esac\n'),
    "cp-holds": ("cp", 'for arg in "$@"; do\n'
                       '\tcase "$arg" in *.openrepotools.*)\n'
                       '\t\t' + WAIT_FOR_MARK +
                       '\t\t;;\n'
                       '\tesac\n'
                       'done\n'
                       'exec {real} "$@"\n'),
}


@pytest.mark.parametrize("at, signame, tool", [
    ("fork", "SIGINT", "cp-refuses"),
    ("fork", "SIGTERM", "cp-refuses"),
    ("waitpid", "SIGINT", "mktemp-stays"),
    ("forkwait", "SIGINT", "cp-holds"),
], ids=["SIGINT-at-the-fork-of-cp", "SIGTERM-at-the-fork-of-cp",
        "SIGINT-in-the-wait-for-mktemp", "SIGINT-in-the-wait-for-cp"])
@NEEDS_JQ
def test_a_signal_at_each_instant_of_a_placement_ends_the_run_and_leaves_no_temporary(
        tmp_path, signal_hook, at, signame, tool):
    """A SIGNAL AT ANY INSTANT OF A PLACEMENT ENDS THE RUN, AND LEAVES NO
    TEMPORARY (#250). These are the three instants where it did not, each
    reached on purpose by `SIGNAL_HOOK_C`, with a stand-in first on `$PATH`:

    * AT THE FORK of the `cp` into the temporary, with a `cp` that refuses.
      bash ran the `EXIT` trap before it had closed that `cp`'s pipeline, the
      trap's first `rm` joined the pipeline and took the `cp`'s failure under
      `pipefail`, and `errexit` ended the trap before its `rm` of the
      temporary. The run died of the signal and left the temporary, for a
      SIGINT and for a `kill`'s SIGTERM alike.
    * IN THE WAIT FOR `mktemp`, once the file is made. A SIGINT that arrives
      in the wait for a `$(…)` is lost, so the install went on to exit 0.
    * IN THE WAIT FOR A `cp` THAT THEN SUCCEEDS. bash took it that `cp` had
      handled the SIGINT, so the install went on to exit 0.

    THE CHILD STARTS WITH BOTH SIGNALS AT THEIR DEFAULT, for the reason the
    test above gives.
    """
    name, body = HOOKED_TOOLS[tool]
    real = shutil.which(name)
    if real is None:
        pytest.skip(f"no real `{name}` on PATH for the stand-in to defer to")
    shim = tmp_path / f"hooked-{name}"
    shim.mkdir()
    (shim / name).write_text("#!/bin/sh\n" + body.format(real=real),
                             encoding="utf-8")
    (shim / name).chmod(0o755)
    sig = getattr(signal, signame)
    mark = tmp_path / "fired"
    preload = os.environ.get("LD_PRELOAD")

    def default_signals() -> None:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    run = subprocess.Popen(
        ["bash", str(COMMAND), "--install"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=command_env(tmp_path, {
            "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
            "LD_PRELOAD": f"{signal_hook}:{preload}" if preload
                          else str(signal_hook),
            "ORT_HOOK_DIR": str(tmp_path / ".local" / "bin"),
            "ORT_HOOK_AT": at, "ORT_HOOK_SIG": str(int(sig)),
            "ORT_HOOK_MARK": str(mark)}),
        start_new_session=True, preexec_fn=default_signals)
    try:
        out, err = run.communicate(timeout=60)
    finally:
        if run.poll() is None:
            os.killpg(run.pid, signal.SIGKILL)
            run.communicate()
    assert mark.exists(), (
        f"the hook never fired at `{at}`, so no signal landed: exit "
        f"{run.returncode}\n{out}{err}")
    assert run.returncode in (-sig, 128 + sig), (
        f"the run did not die of {signame}: exit {run.returncode}\n{out}{err}")
    assert placement_temporaries(tmp_path) == []


#: THE ANSWERS A PLACEMENT WAITS FOR, EACH LANDED IN ON PURPOSE (#250, SHOULD
#: 1 of its review). Before its temporary exists, `place_by_rename` asks
#: `dirname` for the target's directory; after the `cp` and the `chmod` it asks
#: `owner_of` (`ls -lnd` into `awk`) who owns the target, then the temporary.
#: Each answer came back through `$(…)`, whose wait bash keeps outside its job
#: table. `dirname` was its substitution's one process, and a SIGINT that
#: reached the shell once it had closed its output was lost however it was
#: trapped. Each `owner_of` was a pipeline in its substitution's subshell, which
#: held the output open until its `ls` had exited: a SIGINT during that hold was
#: run once the substitution finished, and only one in the instant between the
#: subshell's end and its reaping was lost (#318). The test above lands only at
#: the fork and in the wait of the `cp`, and in the wait for `mktemp`, so it
#: passed with any of these three put back.
#:
#: SO A STAND-IN FIRST ON `$PATH` HOLDS EACH OF THOSE WAITS OPEN. It gives the
#: real tool's answer and closes its output, so where that answer is all a
#: `$(…)` waits to read, as `dirname`'s is, the shell has all of it and waits,
#: as one that takes it through a file does. Then, once (at the first call
#: whose last argument `{at}` matches, while the hook has not fired), it
#: writes what it was asked to `held`, leaves a `.openrepotools.` name in
#: `$ORT_HOOK_DIR`, which nothing else writes to, and stays until the hook's
#: mark. The hook, at `waitpid`, fires in the shell's first wait that sees
#: that name. `released` follows in `held` only when the mark came before the
#: bound: the signal reached the shell while it waited, and the command it was
#: waiting for was the stand-in's.
HELD_ANSWER = ('last=""\n'
               'for arg in "$@"; do last="$arg"; done\n'
               '{real} "$@"\n'
               'answered=$?\n'
               'case "$last" in\n'
               '{at})\n'
               '\tif [ ! -e "$ORT_HOOK_MARK" ]; then\n'
               '\t\texec >&-\n'
               "\t\tprintf '%s\\n' \"$*\" >\"$ORT_HOOK_DIR/held\"\n"
               '\t\t: >"$ORT_HOOK_DIR/.held.openrepotools.$$"\n'
               '\t\t' + WAIT_FOR_MARK +
               '\t\t[ "$i" -ge 200 ] || '
               "printf 'released\\n' >>\"$ORT_HOOK_DIR/held\"\n"
               '\tfi\n'
               '\t;;\n'
               'esac\n'
               'exit "$answered"\n')


@pytest.mark.parametrize("tool, flags, held_on", [
    ("dirname", "--", "target"),
    ("ls", "-lnd --", "target"),
    ("ls", "-lnd --", "temporary"),
], ids=["SIGINT-in-the-wait-for-dirname",
        "SIGINT-in-the-wait-for-the-owner-of-the-target",
        "SIGINT-in-the-wait-for-the-owner-of-the-temporary"])
@NEEDS_JQ
def test_a_sigint_in_the_wait_for_each_answer_of_a_placement_ends_the_run_and_leaves_no_temporary(
        tmp_path, signal_hook, tool, flags, held_on):
    """A SIGINT IN THE WAIT FOR ANY ANSWER A PLACEMENT TAKES ENDS THE RUN, AND
    LEAVES NO TEMPORARY (#250). The first placement, `openRepoTools` into the
    bin directory, is held by `HELD_ANSWER` at one of three waits:

    * THE WAIT FOR `dirname`, before any temporary exists;
    * THE WAIT FOR THE OWNER OF THE TARGET, after the `cp` and the `chmod`,
      with the temporary beside it;
    * THE WAIT FOR THE OWNER OF THE TEMPORARY, just after that.

    Taken through `$(…)`, no SIGINT the hook landed ended the run in the wait
    held. In the wait for `dirname` it landed while the stand-in held, and was
    lost: the install went on to exit 0. For each owner it landed only once
    the hold was over, because the hook fires where the shell blocks in
    `waitpid`, and until then the shell was still reading the output
    `owner_of`'s subshell held open: there it was lost, or it ended the run
    later, and `released` never came. A SIGINT during that hold would have
    been run after it (#318). Taken through a file, the `INT` trap is run once
    the wait is over: the run dies of SIGINT, re-raised rather than exited
    with a status, and nothing is left beside a target.

    EACH CASE PROVES WHERE IT LANDED: the hook's mark, and `held`, which names
    the call the stand-in held and then `released`, written only when the mark
    came while it was holding. THE CHILD STARTS WITH BOTH SIGNALS AT THEIR
    DEFAULT, for the reason the test of a run killed mid-placement gives.
    """
    real = shutil.which(tool)
    if real is None:
        pytest.skip(f"no real `{tool}` on PATH for the stand-in to defer to")
    bin_dir = tmp_path / ".local" / "bin"
    if held_on == "target":
        target = str(bin_dir / INSTALLED[0])
        at, call = shlex.quote(target), re.escape(f"{flags} {target}")
    else:
        prefix = f"{bin_dir}/.{INSTALLED[0]}.openrepotools."
        at = shlex.quote(prefix) + "*"
        call = re.escape(f"{flags} {prefix}") + r"[0-9]+\.[^/]{6}"
    shim = tmp_path / f"held-{tool}"
    shim.mkdir()
    (shim / tool).write_text(
        "#!/bin/sh\n" + HELD_ANSWER.format(real=shlex.quote(real), at=at),
        encoding="utf-8")
    (shim / tool).chmod(0o755)
    hook_dir = tmp_path / "held"
    hook_dir.mkdir()
    mark = tmp_path / "fired"
    preload = os.environ.get("LD_PRELOAD")

    def default_signals() -> None:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    run = subprocess.Popen(
        ["bash", str(COMMAND), "--install"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=command_env(tmp_path, {
            "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
            "LD_PRELOAD": f"{signal_hook}:{preload}" if preload
                          else str(signal_hook),
            "ORT_HOOK_DIR": str(hook_dir), "ORT_HOOK_AT": "waitpid",
            "ORT_HOOK_SIG": str(int(signal.SIGINT)),
            "ORT_HOOK_MARK": str(mark)}),
        start_new_session=True, preexec_fn=default_signals)
    try:
        out, err = run.communicate(timeout=60)
    finally:
        if run.poll() is None:
            os.killpg(run.pid, signal.SIGKILL)
            run.communicate()
    record = hook_dir / "held"
    held = (record.read_text(encoding="utf-8").splitlines()
            if record.exists() else [])
    assert mark.exists(), (
        f"the hook never fired, so no signal landed: exit {run.returncode}; "
        f"the stand-in held {held}\n{out}{err}")
    assert run.returncode == -signal.SIGINT, (
        f"the run did not die of SIGINT: exit {run.returncode}; the stand-in "
        f"held {held}\n{out}{err}")
    assert (len(held) == 2 and re.fullmatch(call, held[0])
            and held[1] == "released"), (
        f"the SIGINT did not land while the shell waited for `{tool} {flags}` "
        f"on the {held_on}: the stand-in held {held}")
    assert placement_temporaries(tmp_path) == []


#: THE SAME HOLD, AT THE WAITS #318 TOOK OUT OF `$(…)`. `HELD_ANSWER` holds the
#: first call whose last argument matches; these need two things more. `find`
#: names its path FIRST, so `{key}` is the argument `{at}` is matched against.
#: And pipx's link is asked about twice with the same arguments, in planning
#: and at the placement loop's own turn, so the stand-in lets `{skip}` matching
#: calls through before it holds one, counting each with a file of its own in
#: `$ORT_HOOK_DIR`. The rest is `HELD_ANSWER`'s: the real answer, the output
#: closed, `held`, the `.openrepotools.` name the hook fires at, and `released`
#: only when the mark came while the stand-in was holding.
HELD_CALL = ('asked="$*"\n'
             'first="$1"\n'
             'last=""\n'
             'for arg in "$@"; do last="$arg"; done\n'
             '{real} "$@"\n'
             'answered=$?\n'
             'case "{key}" in\n'
             '{at})\n'
             '\tif [ ! -e "$ORT_HOOK_MARK" ]; then\n'
             '\t\t: >"$ORT_HOOK_DIR/call.$$"\n'
             '\t\tset -- "$ORT_HOOK_DIR"/call.*\n'
             '\t\tif [ "$#" -gt {skip} ]; then\n'
             '\t\t\texec >&-\n'
             "\t\t\tprintf '%s\\n' \"$asked\" >\"$ORT_HOOK_DIR/held\"\n"
             '\t\t\t: >"$ORT_HOOK_DIR/.held.openrepotools.$$"\n'
             '\t\t\t' + WAIT_FOR_MARK +
             '\t\t\t[ "$i" -ge 200 ] || '
             "printf 'released\\n' >>\"$ORT_HOOK_DIR/held\"\n"
             '\t\tfi\n'
             '\tfi\n'
             '\t;;\n'
             'esac\n'
             'exit "$answered"\n')

#: A `chmod` THAT MAKES A LINK AS LATE AS A TEST CAN, as #257's cases of a late
#: link do: the first time it is handed `{at}`, the temporary beside the
#: target, it makes the target a link to `{value}`, then stamps the mode as the
#: real `chmod` does.
LINK_AT_THE_STAMP = ('for arg in "$@"; do\n'
                     '\tcase "$arg" in\n'
                     '\t{at})\n'
                     '\t\tif [ ! -e {made} ]; then\n'
                     '\t\t\t{ln} -s {value} {target} || exit 1\n'
                     '\t\t\t: >{made}\n'
                     '\t\tfi\n'
                     '\t\tbreak ;;\n'
                     '\tesac\n'
                     'done\n'
                     'exec {real} "$@"\n')


def stand_in(shim: Path, name: str, body: str, **fields: str) -> None:
    """`shim/name`, a `/bin/sh` script of `body` with `fields` filled in and
    `{real}` the real `name` on `PATH`, quoted; or a skip where there is none."""
    real = shutil.which(name)
    if real is None:
        pytest.skip(f"no real `{name}` on PATH for the stand-in to defer to")
    shim.mkdir(exist_ok=True)
    (shim / name).write_text(
        "#!/bin/sh\n" + body.format(real=shlex.quote(real), **fields),
        encoding="utf-8")
    (shim / name).chmod(0o755)


#: THE WAITS #318 TOOK OUT OF `$(…)`, one case each: the tool `HELD_CALL`
#: holds, the argument it matches, how many matching calls it lets through,
#: and what the home holds before the run.
SIGINT_WAITS_318 = {
    "SIGINT-in-the-wait-for-find-asking-a-command-mode":
        ("find", "$first", 0, "installed"),
    "SIGINT-in-the-wait-for-dirname-before-a-skill-file-mkdir":
        ("dirname", "$last", 0, "skill"),
    "SIGINT-in-the-wait-for-dirname-before-a-command-file-mkdir":
        ("dirname", "$last", 0, "command"),
    "SIGINT-in-the-wait-for-pipx-link-in-planning":
        ("readlink", "$last", 0, "pipx"),
    "SIGINT-in-the-wait-for-pipx-link-at-its-own-turn":
        ("readlink", "$last", 1, "pipx"),
    "SIGINT-in-the-wait-for-readlink-naming-a-late-link":
        ("readlink", "$last", 0, "late-link"),
}


@pytest.mark.parametrize("case", list(SIGINT_WAITS_318))
@NEEDS_JQ
def test_a_sigint_in_each_wait_on_the_placement_path_ends_the_run_and_leaves_no_temporary(
        tmp_path, signal_hook, case):
    """A SIGINT IN THE WAIT FOR ANY ANSWER THE PLACEMENT TAKES ENDS THE RUN,
    AND LEAVES NO TEMPORARY (#318), at the waits #250 left in `$(…)`. Each is
    held by `HELD_CALL`, and the hook lands its SIGINT there:

    * `find`, asking `mode_is` the mode of `openRepoTools` in the bin
      directory, on a second `--install` that finds its bytes already right;
    * `dirname`, asked for the directory of the first `SKILL.md`, and of the
      first command file, before each one's `mkdir -p`;
    * `readlink`, where pipx's link at `<dir>/openRepoTools` is asked about:
      in planning, and again at the placement loop's own turn;
    * `readlink`, naming a link that appears at `<dir>/park` as its
      temporary's mode is stamped, in the refusal before the rename.

    Taken through `$(…)`, no SIGINT ended the run in the wait held. For
    `dirname` the substitution's one process is the stand-in, so the hook
    lands while it is held, and the SIGINT is lost: the install goes on to
    exit 0. The others run under a subshell of the substitution's own: bash
    does not replace it with `find`, which carries a `2>/dev/null`, nor with
    the late link's `readlink`, behind a `||`, and `link_venv` is a function
    whose `readlink` is deeper still. That subshell holds its output open
    until the stand-in has exited, so the hook, which fires where the shell
    blocks in `waitpid`, lands only after the hold, as the shell reaps it:
    there the SIGINT was lost and the install went on to exit 0, or it ended
    the run later, and `released` never came. Taken as #318 takes them,
    the shell waits for a plain command, a pipeline or a `( … )` subshell, the
    hook lands while the stand-in holds, and the run dies of SIGINT, with no
    temporary beside a target and a link left as it was.

    EACH CASE PROVES WHERE IT LANDED, as `HELD_ANSWER`'s do: the hook's mark,
    and `held`, the call the stand-in held, then `released`.
    """
    tool, key, skip, setup = SIGINT_WAITS_318[case]
    home = tmp_path
    bin_dir = home / ".local" / "bin"
    shared = home / ".claude-profiles" / "shared"
    shim = tmp_path / "held-tools"
    link = value = None
    if setup == "installed":
        first = run_cmd("--install", home=home)
        assert first.returncode == 0, first.stdout + first.stderr
        target = bin_dir / INSTALLED[0]
        call = f"{target} -maxdepth 0 -perm 755 -print"
    elif setup in ("skill", "command"):
        target = (shared / "skills" / SKILL_NAMES[0] / "SKILL.md"
                  if setup == "skill"
                  else shared / "commands" / f"{COMMAND_NAMES[0]}.md")
        call = f"-- {target}"
    elif setup == "pipx":
        venv = layout.pipx_venv(home / ".local" / "share" / "pipx", "1.17.8")
        target = link = bin_dir / "openRepoTools"
        value = str(venv / "bin" / "openRepoTools")
        bin_dir.mkdir(parents=True)
        link.symlink_to(value)
        call = f"-- {target}"
    else:
        mine = home / "my-own" / "park"
        mine.parent.mkdir()
        mine.write_text("#!/usr/bin/env bash\necho my own park\n",
                        encoding="utf-8")
        target = link = bin_dir / "park"
        value = str(mine)
        ln = shutil.which("ln")
        if ln is None:
            pytest.skip("no `ln` on PATH for the late link")
        stand_in(shim, "chmod", LINK_AT_THE_STAMP,
                 at=shlex.quote(f"{bin_dir}/.park.openrepotools.") + "*",
                 made=shlex.quote(str(tmp_path / "linked")),
                 ln=shlex.quote(ln), value=shlex.quote(value),
                 target=shlex.quote(str(target)))
        call = f"-- {target}"
    stand_in(shim, tool, HELD_CALL, key=key, at=shlex.quote(str(target)),
             skip=str(skip))
    hook_dir = tmp_path / "held"
    hook_dir.mkdir()
    mark = tmp_path / "fired"
    preload = os.environ.get("LD_PRELOAD")

    def default_signals() -> None:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    run = subprocess.Popen(
        ["bash", str(COMMAND), "--install"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=command_env(home, {
            "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
            "LD_PRELOAD": f"{signal_hook}:{preload}" if preload
                          else str(signal_hook),
            "ORT_HOOK_DIR": str(hook_dir), "ORT_HOOK_AT": "waitpid",
            "ORT_HOOK_SIG": str(int(signal.SIGINT)),
            "ORT_HOOK_MARK": str(mark)}),
        start_new_session=True, preexec_fn=default_signals)
    try:
        out, err = run.communicate(timeout=60)
    finally:
        if run.poll() is None:
            os.killpg(run.pid, signal.SIGKILL)
            run.communicate()
    record = hook_dir / "held"
    held = (record.read_text(encoding="utf-8").splitlines()
            if record.exists() else [])
    assert mark.exists(), (
        f"the hook never fired, so no signal landed: exit {run.returncode}; "
        f"the stand-in held {held}\n{out}{err}")
    assert run.returncode == -signal.SIGINT, (
        f"the run did not die of SIGINT: exit {run.returncode}; the stand-in "
        f"held {held}\n{out}{err}")
    assert held == [call, "released"], (
        f"the SIGINT did not land while the shell waited for `{tool} {call}`: "
        f"the stand-in held {held}")
    assert placement_temporaries(home) == []
    if link is not None:
        assert link.is_symlink() and os.readlink(link) == value, (
            f"the link at {link} was not left as it was:\n{out}{err}")


#: WHERE THE PLACEMENT RUNS (#318): the functions it calls from the `mkdir` of
#: the bin directory to the hook pair, and that stretch of `install_commands`,
#: which the comment above `remove_workdir` says take no answer with `$(…)`.
#: Left out is what that comment says still does: `hook_write_settings`,
#: `hook_target_answers` and `hook_pair_defer`'s refusal. `pipx_link_paths` is
#: left out too: it runs only inside `pipx_link_match`'s `( … )`, so its
#: `$(…)` are that subshell's waits and not the shell's.
PLACEMENT_FUNCTIONS = ("mode_is", "place_by_rename", "pipx_link_match",
                       "pipx_release", "place_skill_and_hook",
                       "place_hook_pair", "install_commands")


def placement_code(name: str) -> list[str]:
    """The lines of `name` as the installer carries it, less its comments; of
    `install_commands`, only those from the `mkdir` of the bin directory to
    the call of `place_skill_and_hook`."""
    text = COMMAND.read_text(encoding="utf-8")
    found = re.search(rf"^{re.escape(name)}\(\) \{{[^\n]*\n.*?^\}}\n", text,
                      re.MULTILINE | re.DOTALL)
    assert found, f"`{name}() {{` … `}}` is no longer in openRepoTools"
    body = found.group(0)
    if name == "install_commands":
        start = body.index('\tmkdir -p -- "$dir" ||')
        body = body[start:body.index("\n\tplace_skill_and_hook\n", start)]
    return [line for line in body.splitlines()
            if not line.lstrip().startswith("#")]


@pytest.mark.parametrize("name", PLACEMENT_FUNCTIONS)
def test_the_placement_takes_no_answer_with_a_command_substitution_that_can_lose_a_sigint(
        name):
    """NO ANSWER THE PLACEMENT WAITS FOR IS TAKEN WITH `$(…)` (#318), read
    from the installer's text. The cases above land a SIGINT in each wait a
    stand-in can hold open, and these are the ones it cannot: a `$(…)` whose
    child runs only builtins (`skills_home`, `claude_home`, `install_source`,
    `pipx_release`'s reader) closes its output only as it exits, so no case
    can land a signal there, and put back, each would still lose one in the
    instant between that exit and its reaping. `$((…))` is arithmetic, not a
    substitution, and is not matched."""
    found = [line.strip() for line in placement_code(name)
             if re.search(r"\$\((?!\()", line)]
    assert found == [], (
        f"`{name}` takes an answer with `$(…)`, where a SIGINT can be lost "
        "(search \"A `$(…)` IS NOT A PLAIN COMMAND\" in openRepoTools):\n  "
        + "\n  ".join(found))


def two_substitution_commands(text: str) -> list[int]:
    """The first line of each simple command, at the shell's own level, that
    holds two or more `$(…)` (#342): in its words, its assignments, its
    redirections and the `${…}` in them, and in a `for`'s list. A `$(…)`
    inside another is that substitution's child's, and is not counted; nor is
    a `$((…))`, a backtick, a `<(…)` or a heredoc's body. A newline, `;`, `&`,
    `|`, `(` and `)` end a command, except the `(` that opens an array
    assignment, whose elements are words of the same one. Comments are
    skipped. It reads text, so a command inside a `( … )` counts as well: a
    conservative reading, and this file has none."""
    n = len(text)
    newlines = [k for k, ch in enumerate(text) if ch == "\n"]
    found: list[int] = []
    state = {"count": 0, "start": None}

    def begin(k: int) -> None:
        if state["start"] is None:
            state["start"] = k

    def flush() -> None:
        if state["start"] is not None and state["count"] >= 2:
            found.append(bisect.bisect_left(newlines, state["start"]) + 1)
        state["count"], state["start"] = 0, None

    def skip_single(k: int) -> int:          # after the opening '
        end = text.find("'", k)
        return n if end < 0 else end + 1

    def skip_escaped(k: int, close: str) -> int:   # after $' or `
        while k < n:
            if text[k] == "\\":
                k += 2
            elif text[k] == close:
                return k + 1
            else:
                k += 1
        return n

    def skip_arith(k: int) -> int:           # after $(( or ((
        depth = 2
        while k < n and depth:
            depth += {"(": 1, ")": -1}.get(text[k], 0)
            k += 1
        return k

    def skip_dollar(k: int, counting: bool) -> int:   # at a $: one expansion
        if text.startswith("$((", k):
            return skip_arith(k + 3)
        if text.startswith("$(", k):
            if counting:
                begin(k)
                state["count"] += 1
            return skip_body(k + 2)
        if text.startswith("${", k):
            return skip_brace(k + 2, counting)
        if text.startswith("$'", k):
            return skip_escaped(k + 2, "'")
        if text.startswith('$"', k):
            return skip_double(k + 2, counting)
        return k + 1

    def skip_double(k: int, counting: bool) -> int:   # after the opening "
        while k < n:
            ch = text[k]
            if ch == "\\":
                k += 2
            elif ch == '"':
                return k + 1
            elif ch == "$":
                k = skip_dollar(k, counting)
            elif ch == "`":
                k = skip_escaped(k + 1, "`")
            else:
                k += 1
        return n

    def skip_brace(k: int, counting: bool) -> int:    # after ${
        depth = 1
        while k < n:
            ch = text[k]
            if ch == "\\":
                k += 2
            elif ch == "'":
                k = skip_single(k + 1)
            elif ch == '"':
                k = skip_double(k + 1, counting)
            elif ch == "$":
                k = skip_dollar(k, counting)
            elif ch == "`":
                k = skip_escaped(k + 1, "`")
            else:
                depth += {"{": 1, "}": -1}.get(ch, 0)
                k += 1
                if depth == 0:
                    return k
        return n

    def skip_body(k: int) -> int:            # after $( or <( : past its )
        depth, at_word = 1, True
        while k < n:
            ch = text[k]
            if ch == "#" and at_word:
                end = text.find("\n", k)
                k = n if end < 0 else end
                continue
            at_word = ch in " \t\n;&|()"
            if ch == "\\":
                k += 2
            elif ch == "'":
                k = skip_single(k + 1)
            elif ch == '"':
                k = skip_double(k + 1, False)
            elif ch == "`":
                k = skip_escaped(k + 1, "`")
            elif ch == "$":
                k = skip_dollar(k, False)
            else:
                depth += {"(": 1, ")": -1}.get(ch, 0)
                k += 1
                if depth == 0:
                    return k
        return n

    heredocs: list[tuple[str, bool]] = []
    i, at_word = 0, True
    while i < n:
        ch = text[i]
        if ch == "\n":
            flush()
            i += 1
            while heredocs:
                delimiter, tabs = heredocs.pop(0)
                while i < n:
                    end = text.find("\n", i)
                    end = n if end < 0 else end
                    body = text[i:end]
                    i = end + 1
                    if (body.lstrip("\t") if tabs else body) == delimiter:
                        break
            at_word = True
            continue
        if ch == "#" and at_word:
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        at_word = ch in " \t;&|()"
        if ch in " \t":
            i += 1
        elif ch == "\\" and text.startswith("\\\n", i):
            i += 2
        elif ch in ";&|":
            flush()
            while i < n and text[i] in ";&|":
                i += 1
        elif ch == "(" and state["start"] is None and text.startswith("((", i):
            i = skip_arith(i + 2)
        elif ch == "(" and state["start"] is not None and text[i - 1] == "=":
            i += 1                           # x=( and x+=( : an array's words
        elif ch in "()":
            flush()
            i += 1
        else:
            begin(i)
            if ch == "\\":
                i += 2
            elif ch == "'":
                i = skip_single(i + 1)
            elif ch == '"':
                i = skip_double(i + 1, True)
            elif ch == "`":
                i = skip_escaped(i + 1, "`")
            elif ch == "$":
                i = skip_dollar(i, True)
            elif ch in "<>" and text.startswith("(", i + 1):
                i = skip_body(i + 2)         # a process substitution's child
            elif text.startswith("<<", i) and not text.startswith("<<<", i):
                opened = re.match(r"<<(-?)[ \t]*(['\"]?)\\?([A-Za-z_]\w*)\2",
                                  text[i:])
                if opened:
                    heredocs.append((opened.group(3), bool(opened.group(1))))
                    i += opened.end()
                else:
                    i += 2
            else:
                i += 1
    flush()
    return found


def function_spans(text: str) -> list[tuple[int, int, str]]:
    """`(first line, last line, name)` of each `name() {` … `}` in `text`:
    closed on its own line, as `say() { …; }` is, or by the `}` in the first
    column, as `placement_code` reads the others."""
    spans = []
    for opened in re.finditer(r"^([A-Za-z_]\w*)\(\) \{(.*)$", text,
                              re.MULTILINE):
        first = text.count("\n", 0, opened.start()) + 1
        if re.search(r"\}\s*(#.*)?$", opened.group(2)):
            spans.append((first, first, opened.group(1)))
            continue
        closed = text.find("\n}\n", opened.start())
        spans.append((first, text.count("\n", 0, closed) + 2 if closed >= 0
                      else len(text), opened.group(1)))
    return spans


def enclosing_function(spans: list[tuple[int, int, str]], line: int) -> str:
    """The function of `function_spans` that holds `line`, or `(top level)`."""
    for first, last, name in spans:
        if first <= line <= last:
            return name
    return "(top level)"


#: THE FUNCTIONS WHOSE COMMANDS MAY HOLD TWO `$(…)`, AND WHY (#342): no line of
#: theirs runs in a shell whose `INT` trap is set. The test below checks each
#: reason against the file's text as well as the lines.
TWO_SUBSTITUTIONS_ALLOWED = {
    "stamp_read": "run by `package_init`, at the top level before any "
                  "argument is read, so before `workdir` can set a trap, and "
                  "by `pipx_release` only inside a `( … )` subshell, where a "
                  "trap is reset",
    "hook_strip_refusal": "run only as `$(hook_strip_refusal …)`, in that "
                          "substitution's subshell, where a trap is reset",
}


def test_a_sigint_cannot_meet_a_command_holding_two_command_substitutions():
    """NO SIMPLE COMMAND THAT CAN RUN ONCE THE `INT` TRAP IS SET HOLDS TWO
    `$(…)` (#342), read from the installer's text, as
    `test_the_placement_takes_no_answer_with_a_command_substitution_that_can_lose_a_sigint`
    reads it. A SIGINT that bash took while it waited for the first `$(…)` was
    run as bash parsed the second, and parsed the trap's string as the rest of
    that `$(…)`: `interrupt trap: line 2: unexpected EOF while looking for
    matching `)'`, and exit 2 under `set -e`, the refusal's code, instead of
    death by the signal. Fourteen commands at the merge of #318's and #332's
    branches held two: the `for` lists and `dirs+=(…)` of the two homes in
    `receipt_record` and `plan_skill_targets`, `venv_note`'s `say`,
    `payload_local_feature`'s `[`, `receipt_record`'s note on a relative data
    directory, and five refusals in `plan_hook_merge`.

    `TWO_SUBSTITUTIONS_ALLOWED` names the functions that are not exposed, and
    their reasons hold: every call of `stamp_read` is in `package_init`, which
    runs once at the top level before the arguments are read and does not
    reach `workdir`, or opens a `( … )`; every call of `hook_strip_refusal` is
    a `$(…)`."""
    text = COMMAND.read_text(encoding="utf-8")
    lines = text.split("\n")
    spans = function_spans(text)
    exposed = [f"openRepoTools:{line} ({enclosing_function(spans, line)}): "
               f"{lines[line - 1].strip()}"
               for line in two_substitution_commands(text)
               if enclosing_function(spans, line) not in TWO_SUBSTITUTIONS_ALLOWED]
    assert exposed == [], (
        "a command that can run once the INT trap is set holds two `$(…)`, so "
        "a SIGINT in the first ends the run with a false parse error and exit "
        "2 (search \"HOLDS TWO\" in openRepoTools):\n  " + "\n  ".join(exposed))

    def calls(name: str) -> list[tuple[int, str]]:
        """Each line that runs `name`: the word, unquoted and outside a
        comment, and not followed by the `()` of its definition."""
        found = []
        for number, code in enumerate(lines, 1):
            code = re.sub(r"(^|\s)#.*", "", code)
            code = re.sub(r"`[^`]*`|'[^']*'", "", code)
            if re.search(rf"(?<![\w-]){name}(?![\w(-])", code):
                found.append((number, code))
        return found

    for number, code in calls("stamp_read"):
        assert (enclosing_function(spans, number) == "package_init"
                or re.search(r"\(\s*stamp_read\b", code)), (
            f"`stamp_read` is called at openRepoTools:{number} outside "
            f"`package_init` and outside a `( … )`: {code.strip()}")
    for number, code in calls("package_init"):
        assert enclosing_function(spans, number) == "(top level)", (
            f"`package_init` is called from a function at openRepoTools:{number}")
    for name in ("package_init", "stamp_read"):
        body = re.search(rf"^{name}\(\) \{{.*?^\}}$", text,
                         re.MULTILINE | re.DOTALL)
        assert body and not re.search(r"\bworkdir\b", body.group(0)), (
            f"`{name}` reaches `workdir`, which sets the INT trap")
    for number, code in calls("hook_strip_refusal"):
        assert re.search(r"\$\(hook_strip_refusal\b", code), (
            f"`hook_strip_refusal` is called at openRepoTools:{number} other "
            f"than inside a `$(…)`: {code.strip()}")


@pytest.mark.parametrize("setup", ["a-pipx-link-at-the-target",
                                   "a-link-into-a-venv-with-no-pyvenv-cfg",
                                   "a-clean-home"])
def test_a_failed_mktemp_for_the_workdir_ends_the_install_with_exit_1_whatever_asks(
        tmp_path, setup):
    """A DIRECTORY THE INSTALL CANNOT MAKE ENDS THE RUN WITH EXIT 1, FROM
    WHICHEVER CALLER ASKED FIRST (#318).

    #318 made planning's question of pipx's link ask for the workdir, from
    inside an `if` condition, where `set -e` is off, so a failed `mktemp -d`
    there no longer ended the run: `$WORKDIR` stayed empty and the next line
    wrote `/answer`. `$TMPDIR` is a directory that is not there, which
    fails `mktemp -d` for any user, root included.

    * With a pipx link at the target, into a venv that holds `pyvenv.cfg` as
      pipx's does, that run took the failed write for "not pipx's link" and
      exited 2 with a false `REFUSED`: a link into a Python environment in a
      layout the installer does not recognise, to be left where it is. That
      refusal has no `rm -f` in it.
    * With the same link into a venv that has no `pyvenv.cfg`, the false
      `REFUSED` was the other one, which tells the person to `rm -f` pipx's
      own link. That is the case the `rm -f` assertion, the first one made,
      bites in; a real pipx venv holds the file, so this one is a fixture's
      shape and not pipx's.
    * On a clean home it exited 1 as it should, but only after trying to write
      `/answer` and after a second `mktemp` message.

    The run now ends at the first message: exit 1 and nothing else said. The
    link is left as it was, and nothing is placed.
    """
    bin_dir = tmp_path / ".local" / "bin"
    link = value = None
    if setup != "a-clean-home":
        venv = layout.pipx_venv(tmp_path / ".local" / "share" / "pipx",
                                "1.17.8")
        if setup == "a-link-into-a-venv-with-no-pyvenv-cfg":
            (venv / "pyvenv.cfg").unlink()
        link = bin_dir / "openRepoTools"
        value = str(venv / "bin" / "openRepoTools")
        bin_dir.mkdir(parents=True)
        link.symlink_to(value)
    missing = tmp_path / "no-such-tmpdir"

    result = run_cmd("--install", home=tmp_path,
                     env={"TMPDIR": str(missing)})

    said = result.stdout + result.stderr
    assert "rm -f" not in said, (
        f"the run advised removing a link that is pipx's:\n{said}")
    assert result.returncode == 1, said
    assert "REFUSED" not in said, said
    assert result.stderr.count("mktemp:") == 1, (
        "the run did not end at the first failed `mktemp`:\n" + said)
    assert not re.search(r"(?:^|[\s'\"`])/answer(?![\w.-])", said,
                         re.MULTILINE), (
        f"a write went to /answer, the empty `$WORKDIR`'s:\n{said}")
    assert placement_temporaries(tmp_path) == []
    placed = sorted(p.name for p in bin_dir.iterdir()) if bin_dir.is_dir() \
        else []
    assert placed == (["openRepoTools"] if link else []), (
        f"the install placed something in {bin_dir}:\n{said}")
    if link is not None:
        assert link.is_symlink() and os.readlink(link) == value, (
            f"the link at {link} was not left as it was:\n{said}")


#: A `mktemp` THAT HOLDS THE MAKING OF THE WORKDIR (#342). Every call but the
#: workdir's goes to the real one. For `-d` it makes the directory with the
#: real `mktemp`, and then, by `WORKDIR_MKTEMP_THEN`: `holds` gives the answer,
#: leaves a `.openrepotools.` name in `$ORT_HOOK_DIR` and stays, its output
#: still open, while the shell that called it is alive (ten seconds at most),
#: so a shell taking the answer through `$(…)` is still reading it; `exits`
#: gives the answer, closes its output, leaves that name and exits, so the
#: shell has all of it and is waiting for the child or past it;
#: `makes-a-second` makes another directory from the same template before it
#: answers, as somebody racing the run for its name would.
WORKDIR_MKTEMP = ('case " $* " in\n'
                  '*" -d "*) ;;\n'
                  '*) exec {real} "$@" ;;\n'
                  'esac\n'
                  'made=$({real} "$@") || exit $?\n')
WORKDIR_MKTEMP_THEN = {
    "holds": ("printf '%s\\n' \"$made\"\n"
              ': >"$ORT_HOOK_DIR/.made.openrepotools.$$"\n'
              'i=0\n'
              'while kill -0 "$PPID" 2>/dev/null && [ "$i" -lt 200 ]; do\n'
              '\tsleep 0.05\n'
              '\ti=$((i + 1))\n'
              'done\n'),
    "exits": ("printf '%s\\n' \"$made\"\n"
              'exec >&-\n'
              ': >"$ORT_HOOK_DIR/.made.openrepotools.$$"\n'),
    "makes-a-second": ('{real} "$@" >/dev/null || exit $?\n'
                       "printf '%s\\n' \"$made\"\n"),
}


def workdirs_left(tmpdir: Path) -> list[str]:
    """Every directory in the run's `$TMPDIR`: a workdir nothing removed."""
    return sorted(p.name for p in tmpdir.iterdir() if p.is_dir())


@pytest.mark.parametrize("signame, to_group", [
    ("SIGINT", True),     # Ctrl-C: the whole foreground process group
    ("SIGTERM", False),   # a `kill` from another shell
], ids=["SIGINT-to-the-group", "SIGTERM-to-the-shell"])
@NEEDS_JQ
def test_a_signal_while_mktemp_makes_the_workdir_ends_the_run_and_leaves_no_directory(
        tmp_path, signame, to_group):
    """A SIGNAL WHILE THE WORKDIR IS MADE ENDS THE RUN AND LEAVES NO DIRECTORY
    (#342). `workdir` made it with `WORKDIR="$(mktemp -d)"` and set the `EXIT`
    and `INT` traps after, so a signal while bash waited for that `$(…)` ended
    the run with neither trap set, and the directory stayed in `$TMPDIR` with
    nothing on stderr: for a Ctrl-C to the group and for a `kill` of the shell
    alike. Now the name's prefix is known and both traps are set before
    `mktemp -d` runs, as a plain command, and `remove_workdir` takes what
    starts with that prefix until `$WORKDIR` holds the name.

    `WORKDIR_MKTEMP`, first on `$PATH`, makes the directory and holds there,
    its output open. Once the directory exists the signal lands: the run dies
    of it, and no directory is left in `$TMPDIR`. THE CHILD STARTS WITH ALL
    THREE SIGNALS AT THEIR DEFAULT, for the reason the test of a run killed
    mid-placement gives.
    """
    shim = tmp_path / "held-mktemp"
    stand_in(shim, "mktemp", WORKDIR_MKTEMP + WORKDIR_MKTEMP_THEN["holds"])
    tmpdir, made = tmp_path / "tmp", tmp_path / "made"
    tmpdir.mkdir()
    made.mkdir()
    sig = getattr(signal, signame)

    def default_signals() -> None:
        for each in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(each, signal.SIG_DFL)

    run = subprocess.Popen(
        ["bash", str(COMMAND), "--install"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=command_env(tmp_path, {
            "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
            "TMPDIR": str(tmpdir), "ORT_HOOK_DIR": str(made)}),
        start_new_session=True, preexec_fn=default_signals)
    try:
        deadline = time.monotonic() + 60
        while (time.monotonic() < deadline and run.poll() is None
               and not any(made.iterdir())):
            time.sleep(0.05)
        held = workdirs_left(tmpdir)
        if any(made.iterdir()) and to_group:
            os.killpg(run.pid, sig)
        elif any(made.iterdir()):
            run.send_signal(sig)
        out, err = run.communicate(timeout=60)
    finally:
        if run.poll() is None:
            os.killpg(run.pid, signal.SIGKILL)
            run.communicate()
    assert held, (f"`mktemp -d` never made the workdir for the signal to land "
                  f"beside: exit {run.returncode}\n{out}{err}")
    assert run.returncode == -sig, (
        f"the run did not die of {signame}: exit {run.returncode}\n{out}{err}")
    assert workdirs_left(tmpdir) == [], (
        f"the workdir outlived the run: {held}\n{out}{err}")


@pytest.mark.parametrize("signame", ["SIGINT", "SIGTERM"])
@NEEDS_JQ
def test_a_signal_in_the_wait_for_the_workdir_mktemp_ends_the_run_and_leaves_no_directory(
        tmp_path, signal_hook, signame):
    """A SIGNAL IN THE SHELL'S WAIT FOR THE WORKDIR'S `mktemp`, ONCE IT HAS MADE
    THE DIRECTORY AND CLOSED ITS OUTPUT, ENDS THE RUN AND LEAVES NO DIRECTORY
    (#342). Taken through `$(…)`, that wait was outside bash's job table and
    before either trap: a SIGINT that reached the shell alone there was lost,
    the install went on to exit 0, and only a later `EXIT` trap took the
    directory; a SIGTERM ended the run with the directory left in `$TMPDIR`.
    Now the wait is a plain command's, after both traps are set: the SIGINT
    runs the `INT` trap once `mktemp` is done and the SIGTERM the `EXIT` trap,
    and each takes the directory by its prefix.

    `WORKDIR_MKTEMP`'s `exits` makes the directory, answers, closes its output
    and leaves its name in `$ORT_HOOK_DIR`; `SIGNAL_HOOK_C`, at `waitpid`,
    sends the signal to the shell in its wait for that child. The hook's mark
    proves it fired. THE CHILD STARTS WITH ALL THREE SIGNALS AT THEIR DEFAULT.
    """
    shim = tmp_path / "exiting-mktemp"
    stand_in(shim, "mktemp", WORKDIR_MKTEMP + WORKDIR_MKTEMP_THEN["exits"])
    tmpdir, made, mark = tmp_path / "tmp", tmp_path / "made", tmp_path / "fired"
    tmpdir.mkdir()
    made.mkdir()
    sig = getattr(signal, signame)
    preload = os.environ.get("LD_PRELOAD")

    def default_signals() -> None:
        for each in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(each, signal.SIG_DFL)

    run = subprocess.Popen(
        ["bash", str(COMMAND), "--install"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=command_env(tmp_path, {
            "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
            "TMPDIR": str(tmpdir),
            "LD_PRELOAD": f"{signal_hook}:{preload}" if preload
                          else str(signal_hook),
            "ORT_HOOK_DIR": str(made), "ORT_HOOK_AT": "waitpid",
            "ORT_HOOK_SIG": str(int(sig)), "ORT_HOOK_MARK": str(mark)}),
        start_new_session=True, preexec_fn=default_signals)
    try:
        out, err = run.communicate(timeout=60)
    finally:
        if run.poll() is None:
            os.killpg(run.pid, signal.SIGKILL)
            run.communicate()
    assert mark.exists(), (
        f"the hook never fired, so no signal landed: exit {run.returncode}"
        f"\n{out}{err}")
    assert run.returncode == -sig, (
        f"the run did not die of {signame}: exit {run.returncode}\n{out}{err}")
    assert workdirs_left(tmpdir) == [], (
        f"the workdir outlived the run:\n{out}{err}")


@NEEDS_JQ
def test_a_workdir_prefix_naming_more_than_the_directory_mktemp_made_ends_the_run_and_removes_nothing(
        tmp_path):
    """THE WORKDIR IS TAKEN ONLY WHEN ITS PREFIX NAMES EXACTLY THE ONE DIRECTORY
    `mktemp -d` MADE (#342). `workdir` reads the name back by the prefix's
    glob, so a second directory under the same prefix — somebody racing the
    run for its name — would leave it two candidates, and a `$WORKDIR` it did
    not make would be somebody else's to fill. `WORKDIR_MKTEMP`'s
    `makes-a-second` makes that second one. The run ends with exit 1 and one
    line, as a workdir that cannot be made does (#318), places nothing and
    REMOVES NOTHING: it cannot tell its own directory from the other one.
    Taken through `$(…)`, the run took the name `mktemp` printed and went on.
    """
    shim = tmp_path / "racing-mktemp"
    stand_in(shim, "mktemp",
             WORKDIR_MKTEMP + WORKDIR_MKTEMP_THEN["makes-a-second"])
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()

    result = run_cmd("--install", home=tmp_path, env={
        "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
        "TMPDIR": str(tmpdir)})

    said = result.stdout + result.stderr
    assert result.returncode == 1, said
    assert "REFUSED" not in said, said
    lines = result.stderr.splitlines()
    assert len(lines) == 1 and "cannot tell which is its own" in lines[0], (
        f"the run did not end with the one line naming the prefix:\n{said}")
    assert len(workdirs_left(tmpdir)) == 2, (
        f"the run removed a directory it could not tell was its own: "
        f"{workdirs_left(tmpdir)}\n{said}")
    bin_dir = tmp_path / ".local" / "bin"
    assert not bin_dir.is_dir() or not any(bin_dir.iterdir()), (
        f"the install placed something in {bin_dir}:\n{said}")


#: THE WORDS THIS INSTALLER USED TO PLACE AND DOES NOT ANY MORE. `restart` left
#: under lane-collision-protocol Amendment 18 Addendum 2 (ratified
#: 2026-09-14T16:50:32Z, verbatim "ratify"): `lane <name>` is that act, and the
#: addendum's words are *"`restart` is no longer a command a person is given"*.
RETIRED = ("restart",)


@pytest.mark.parametrize("name", RETIRED)
@NEEDS_JQ
def test_install_removes_a_word_it_used_to_place(tmp_path, name):
    """DROPPING IT FROM THE LIST ONLY STOPS THE NEXT COPY.

    The install loop places `INSTALLABLES` and removes nothing, so a
    workstation that took the install while `restart` was in that list keeps
    `restart` on its PATH for ever — and the addendum that retired it says the
    opposite. The retirement is therefore an ACT of `--install` and not an
    absence from a list, which is what this holds.

    Pre-seeded with a copy carrying this installer's own header, which is what
    marks a file as one it wrote.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    stale = bin_dir / name
    stale.write_text(
        "#!/usr/bin/env bash\n"
        "# SPDX-License-Identifier: Apache-2.0\n"
        "#\n"
        f"# {name} — the word this installer used to place.\n"
        "#\n"
        "# Installed on PATH by `openRepoTools --install`, which is where it came from.\n"
        "echo stale\n", encoding="utf-8")
    stale.chmod(0o755)
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not stale.exists(), (
        f"`{name}` is still on PATH after an install that retired it:\n"
        + result.stdout)
    assert f"{name}: RETIRED" in result.stdout, (
        "the removal is said out loud, because a file that vanishes without a "
        f"line is a file nobody can ask about:\n{result.stdout}")


@pytest.mark.parametrize("name", RETIRED)
@NEEDS_JQ
def test_install_never_removes_a_file_it_did_not_write(tmp_path, name):
    """AND IT DELETES ONLY WHAT IT WROTE.

    A person's own script that happens to carry a retired name is theirs. It
    is NAMED, the line that removes it is printed, and the file is left exactly
    where it is — because an installer that deletes a stranger's script to
    tidy its own list has done something no list can justify.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    mine = bin_dir / name
    mine.write_text("#!/usr/bin/env bash\n# my own script\necho mine\n",
                    encoding="utf-8")
    mine.chmod(0o755)
    before = mine.read_bytes()
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert mine.is_file(), "a file this installer did not write was deleted"
    assert mine.read_bytes() == before
    assert f"{name}: RETIRED" in result.stdout
    assert f'rm -f -- "{mine}"' in result.stdout, (
        "the one line that removes it is printed, filled in, because the act "
        f"is the person's:\n{result.stdout}")


@pytest.mark.parametrize("name", RETIRED)
@NEEDS_JQ
def test_install_never_unlinks_a_symlink_of_a_retired_name(tmp_path, name):
    """`-f` FOLLOWS THE LINK, AND A LINK IS SOMEBODY'S DECISION.

    A person's own `restart` symlink pointing at a file that happens to carry
    this installer's header would be unlinked by an ownership test written as
    `[ -f "$target" ]` alone — and `plan_install_targets` refuses a `-L`
    target for exactly that reason, naming the link rather than writing
    through it. The retirement holds to the same rule: the link is NAMED and
    left, and both it and what it points at are still there afterwards.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    real = tmp_path / "elsewhere.sh"
    real.write_text(
        "#!/usr/bin/env bash\n"
        "# Installed on PATH by `openRepoTools --install`, once upon a time.\n"
        "echo linked\n", encoding="utf-8")
    real.chmod(0o755)
    link = bin_dir / name
    link.symlink_to(real)
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert link.is_symlink(), (
        f"a symlink named `{name}` was unlinked by the retirement:\n"
        + result.stdout)
    assert real.is_file(), "and what it pointed at is still there"
    assert f"{name}: RETIRED" in result.stdout
    assert f'rm -f -- "{link}"' in result.stdout


@pytest.mark.parametrize("name", RETIRED)
@NEEDS_JQ
def test_install_names_a_dangling_symlink_of_a_retired_name(tmp_path, name):
    """AND `-e` IS FALSE FOR A LINK WHOSE TARGET IS GONE.

    Copilot round 4 on #45, `openRepoTools:261`. `[ -e "$target" ] || continue`
    follows the link, so a `restart` symlink pointing at a file that has since
    been removed was skipped outright: still on PATH, still the first `restart`
    a shell finds, and not one word about it in the run that was supposed to
    retire that name. The pre-move `link-estates` put exactly these links in a
    workstation's `~/.local/bin`. It is NAMED like any other link — and left,
    because a link is somebody's decision about their own PATH.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    link = bin_dir / name
    link.symlink_to(tmp_path / "gone-with-the-checkout.sh")
    assert not link.exists() and link.is_symlink(), "the fixture is a dangling link"
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert link.is_symlink(), (
        f"a dangling symlink named `{name}` was removed by the retirement:\n"
        + result.stdout)
    assert f"{name}: RETIRED" in result.stdout, (
        "a retired name still on PATH is named, whatever kind of file it is:\n"
        + result.stdout)
    assert f'rm -f -- "{link}"' in result.stdout


@pytest.mark.parametrize("name", RETIRED)
@NEEDS_JQ
def test_install_retires_only_after_the_placement_it_migrates_to(tmp_path, name):
    """THE ONE DESTRUCTIVE STEP IS THE LAST ONE.

    Copilot round 7 on #45, `openRepoTools:369`. `retire_commands` ran BEFORE
    `place_skill_and_hook`, so a skills directory this run could not write left
    a workstation with the old word already deleted and the adoption it was
    migrating to unfinished — while every other refusal in that file places
    NOTHING rather than half of it. Here `~/.claude/skills` is a regular file,
    which is a `mkdir -p` that cannot succeed.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    stale = bin_dir / name
    stale.write_text(
        "#!/usr/bin/env bash\n"
        f"# {name} — the word this installer used to place.\n"
        "# Installed on PATH by `openRepoTools --install`, which is where it came from.\n"
        "echo stale\n", encoding="utf-8")
    stale.chmod(0o755)
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "skills").write_text("a file where the skills directory goes\n",
                                   encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode != 0, (
        "the placement could not finish and the run said it did:\n"
        + result.stdout)
    assert stale.is_file(), (
        f"`{name}` was retired by a run whose placement then failed:\n"
        + result.stdout + result.stderr)
    assert f"{name}: RETIRED" not in result.stdout, (
        "and it never said it had been:\n" + result.stdout)


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
def test_a_mode_stamp_the_bin_loop_cannot_make_reads_as_a_refusal(tmp_path):
    """THE ONE MODE STAMP IN THIS COMMAND THAT HAD NO `die` BESIDE IT (#48).

    `--install`'s codes are this toolset's — 0 done, 1 findings printed, 2 a
    refusal — and an unguarded `chmod` under `set -e` exits with the shell's own
    1 from a run that is refusing, with the commands before it already placed.
    Every other stamp in the file already died; this loop's did not.

    WHY IT CAN FAIL AT ALL, AND WHY NOTHING PREFLIGHTS IT. `-w` proves this euid
    may write a file's CONTENTS and `chmod` wants its OWNER, so a group- or
    ACL-writable file owned by another account passes every planning check and
    refuses the stamp. The question that would catch it first is `[ -O ]`, and
    it is declined for the reason written beside `unplaceable_kind` (search
    "WHAT `-w` DOES NOT PROVE") and ruled in R-A9-15: no fixture here can make a
    second account to own the target, and it would refuse a root `--install`
    into another user's home, where the stamp does in fact succeed.

    SO THE FAILURE ITSELF IS WHAT IS TESTED, through a `chmod` first on `$PATH`
    that refuses ONE path and is the real one for every other — the same way
    this suite answers a `gh` it cannot call and a `jq` it must do without.
    Ownership is what this stands in for; a fixture cannot make the ownership,
    and the stamp's own failure is the same failure either way.

    THE FAKE REFUSES THE ONE FILE BY EITHER NAME (#167): a copy that is being
    WRITTEN is stamped on its temporary beside the target, before the rename,
    so the target is never at the wrong mode — and a stamp that fails there
    leaves no temporary behind.
    """
    real = shutil.which("chmod")
    if real is None:
        pytest.skip("no real `chmod` on PATH for the fake to defer to")
    bin_dir = tmp_path / ".local" / "bin"
    refused = bin_dir / INSTALLED[1]
    shim = tmp_path / "fake-chmod"
    shim.mkdir()
    (shim / "chmod").write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '\tcase "$arg" in\n'
        f'\t"{refused}"|"{bin_dir}/.{refused.name}.openrepotools."*)\n'
        "\t\tprintf 'fake chmod: this one is not ours to mode\\n' >&2\n"
        "\t\texit 1 ;;\n"
        "\tesac\n"
        "done\n"
        f'exec {real} "$@"\n', encoding="utf-8")
    (shim / "chmod").chmod(0o755)

    result = run_cmd("--install", home=tmp_path,
                     env={"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "REFUSED:" in result.stderr, result.stderr
    assert f"could not set mode 755 on {refused}" in result.stderr, result.stderr
    assert (bin_dir / INSTALLED[0]).is_file(), (
        "the run refused before it reached the file whose stamp fails")
    assert not (bin_dir / INSTALLED[2]).exists(), (
        "the loop carried on past a mode stamp it could not make")
    assert not refused.exists(), "a copy whose mode failed was placed anyway"
    assert placement_temporaries(tmp_path) == []
    assert not (tmp_path / ".claude").exists(), (
        "the skills, the command files or the hook entries were placed by a "
        "run that refused")


def unguarded_mode_stamps(lines: list[str]) -> list[str]:
    """Every `chmod` line in `lines` whose failure does not reach `die`.

    THE HANDLER IS WHAT IS READ, AND NOT THE BARE `||` (Copilot round 1 on
    #102). A stamp written `chmod 755 "$x" || true` carries a `||` and is the
    exact defect this rule exists to stop — a mode-stamp failure that is not a
    refusal — so the text after the `||` has to name `die`, on that line or, for
    the two-line spelling this file uses, on the one below it.

    AND `die` HAS TO BE THE COMMAND THE HANDLER RUNS (round 2), not a word
    inside it: `|| echo die` names it and refuses nothing. So it is matched at a
    command position — the start of the handler, or after the `;`, `&&`, `||` or
    `{` that begins one — which is what makes `{ rm -f -- …; die …; }`, the
    spelling the settings file's temporary needs, a handler this accepts.
    """
    out = []
    for number, line in enumerate(lines, 1):
        if not line.strip().startswith("chmod "):
            continue
        handler = line.split("||", 1)[1] if "||" in line else ""
        if line.rstrip().endswith("||"):
            handler = lines[number] if number < len(lines) else ""
        if not re.search(r"(?:^|[;&|{(])\s*die\b", handler.strip()):
            out.append(f"{number}: {line.strip()}")
    return out


def test_every_mode_stamp_in_this_command_fails_through_die():
    """AND THE RULE IS ASKED OF EVERY SITE, NOT ONLY THE ONE ABOVE (#48).

    The bin loop's was the stamp nobody guarded, and a test that proves only
    that stamp is a test the NEXT unguarded one walks straight past — the same
    reason `test_repo_hygiene.py` asks its questions per name rather than of a
    list somebody keeps. Read out of the script's text, because a `chmod` that
    cannot fail in this suite is a `chmod` no run here reaches.

    AND THE RULE IS PROVED TO HAVE TEETH in the same breath, against lines
    written here: a check that accepted any `||` would accept `|| true`, which
    is a handler and not a refusal.
    """
    lines = COMMAND.read_text(encoding="utf-8").splitlines()
    stamps = [line for line in lines if line.strip().startswith("chmod ")]
    assert len(stamps) >= 5, (
        f"this command performs {len(stamps)} mode stamps; the shape this test "
        "reads has moved and it is now proving less than it says")
    unguarded = unguarded_mode_stamps(lines)
    assert not unguarded, (
        "every `chmod` this command performs must fail through `die` — exit 2 "
        "and a REFUSED line naming the target — never the shell's own 1 under "
        "`set -e`, which this toolset spends on \"findings were printed\":\n  "
        + "\n  ".join(unguarded))
    assert unguarded_mode_stamps(['\tchmod 755 "$target"']) == [
        '1: chmod 755 "$target"'], "an unguarded stamp is not caught"
    assert unguarded_mode_stamps(['\tchmod 755 "$target" || true']) == [
        '1: chmod 755 "$target" || true'], "`|| true` is a handler, not a refusal"
    assert unguarded_mode_stamps(['\tchmod 755 "$target" || echo die']) == [
        '1: chmod 755 "$target" || echo die'], (
        "`die` has to be the command the handler RUNS, not a word inside it")
    assert unguarded_mode_stamps(['\tchmod 644 "$t" || die "no."']) == []
    assert unguarded_mode_stamps(['\tchmod 600 "$t" ||',
                                  '\t\t{ rm -f -- "$t"; die "no."; }']) == [], (
        "the two-line spelling this file uses must read as guarded")


@pytest.mark.parametrize("name", RETIRED)
@NEEDS_JQ
def test_the_retirement_prints_a_removal_that_can_be_pasted(tmp_path, name):
    """A PRINTED COMMAND IS A LINE SOMEBODY TYPES BACK.

    Copilot round 9 on #45, `openRepoTools:281`. `OPENREPOTOOLS_BIN_DIR` is a
    path a person chooses, and the retirement printed `rm <path>` bare — so a
    directory with a space in it produced a line that removes nothing (or, with
    the wrong path, something else). Both planners in this file already print
    `rm -f -- "<path>"` out of a `paths` they build with the quotes in; this is
    the same spelling.
    """
    bin_dir = tmp_path / "my bin dir"
    bin_dir.mkdir(parents=True)
    mine = bin_dir / name
    mine.write_text("#!/usr/bin/env bash\n# my own script\necho mine\n",
                    encoding="utf-8")
    mine.chmod(0o755)
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
    assert result.returncode == 0, result.stderr
    assert mine.is_file(), "a file this installer did not write was deleted"
    assert f'rm -f -- "{mine}"' in result.stdout, (
        "the removal is printed quoted, because the path has a space in it:\n"
        + result.stdout)
    assert f"rm {mine}\n" not in result.stdout


# --- the receipt of what it placed ------------------------------------------

#: THE RECEIPT'S PATH UNDER A REDIRECTED `$HOME`. `command_env` clears
#: `$XDG_DATA_HOME` as well as `$OPENREPOTOOLS_DATA_DIR`, so what these tests
#: exercise is the DEFAULT — `~/.local/share/openRepoTools/installed.tsv` — and
#: it lands inside `tmp_path` because `$HOME` does.
def receipt_path(home: Path) -> Path:
    return home / ".local" / "share" / "openRepoTools" / "installed.tsv"


def receipt_rows(home: Path) -> list:
    """The receipt as a list of `(name, destination, sha256, utc)` tuples."""
    return [tuple(line.split("\t"))
            for line in receipt_path(home).read_text(
                encoding="utf-8").splitlines() if line]


def receipt_rows_at(receipt: Path) -> list:
    """`receipt_rows`, for a receipt that is not at the default path."""
    return [tuple(line.split("\t"))
            for line in receipt.read_text(encoding="utf-8").splitlines()
            if line]


def placed_files(home: Path) -> dict:
    """Every REGULAR FILE an `--install` into `home` places, by destination.

    Derived from the same three lists the artifact count is, and it comes to
    `ARTIFACTS - HOOK_ENTRIES`: the two hook entries are entries inside
    somebody else's JSON file rather than files this command placed, so they
    get no row. The NAME beside each is the word `--install` prints on the line
    that places it — `park`, `handoff`, `/ctx` — because one name is a skill
    AND a command file at four different paths, which is why the row's subject
    is its destination.
    """
    files = {str(home / ".local" / "bin" / name): name for name in INSTALLED}
    for name in SKILL_NAMES:
        for root in (home / ".claude-profiles" / "shared", home / ".claude"):
            files[str(root / "skills" / name / "SKILL.md")] = name
    for name in COMMAND_NAMES:
        for root in (home / ".claude-profiles" / "shared", home / ".claude"):
            files[str(root / "commands" / f"{name}.md")] = f"/{name}"
    return files


@NEEDS_JQ
def test_install_writes_a_receipt_of_every_file_it_placed(tmp_path):
    """ONE ROW PER PLACED FILE, WITH THE DIGEST OF THE BYTES THAT ARE THERE
    (#57).

    The only evidence `retire_commands` had that a file on a PATH was one this
    installer wrote is the `Installed on PATH by ` header — a content
    substring, which Copilot's round-3 review of #45 named at
    `openRepoTools:263` and which a person's own script can carry by having
    been copied from an old installation. A receipt is the evidence that
    substring is not: the digest of what this run actually placed, at the path
    it placed it.

    ONE ROW PER PLACED REGULAR FILE, which is `ARTIFACTS - HOOK_ENTRIES` and
    is derived rather than stated: the `INSTALLED` files plus the skill and
    command files at both of their destinations. The two hook entries are
    entries inside `~/.claude/settings.json` and not files this command
    placed, and the receipt carries no row for itself either. Today that is
    31 artifacts and 29 rows (17 + 6 + 6, since opensoft/openRepoTools#162 put
    `lane-worktrees` in the list); the number moves with those three lists and
    with nothing else, which is why no assertion below spells it.
    """
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    receipt = receipt_path(tmp_path)
    assert receipt.is_file(), result.stdout
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600, (
        "the receipt is born at mktemp's 0600 and no chmod touches it: every "
        "chmod this command performs must fail through die (#48), and a "
        "receipt that cannot be written is a note and never a refusal (#57), "
        "so the one mode both rules allow is the one mktemp gives")
    rows = receipt_rows(tmp_path)
    expected = placed_files(tmp_path)
    assert len(rows) == ARTIFACTS - HOOK_ENTRIES == len(expected), (
        f"{len(rows)} rows for {len(expected)} placed files:\n" + receipt.read_text(encoding="utf-8"))
    for name, destination, digest, utc in rows:
        assert destination in expected, f"a row for a file nothing placed: {destination}"
        assert name == expected[destination], destination
        assert digest == hashlib.sha256(
            Path(destination).read_bytes()).hexdigest(), (
            f"the row for {destination} carries a digest of other bytes")
        datetime.strptime(utc, "%Y-%m-%dT%H:%M:%SZ")
    assert {row[1] for row in rows} == set(expected)
    assert f"receipt: {len(rows)} placed files recorded in {receipt}" \
        in result.stdout, (
        "a file written without a line is a file nobody can ask about:\n"
        + result.stdout)


def test_the_help_and_the_readme_say_the_mode_the_receipt_is_born_at():
    """THE CONTRACT IS ONE NUMBER IN FOUR PLACES, AND THE TEST ABOVE ONLY HOLDS
    ONE OF THEM (Copilot on #103, `openRepoTools:503`).

    The pull request's description said the receipt is 0644 while the code, the
    test and the README said 0600 — deliberately: #48's "every `chmod` this
    command performs fails through `die`" meets #57's "a receipt it cannot write
    is a note", and a stamp that may neither die nor fall silent is a stamp that
    must not exist, so `mktemp`'s 0600 stands. A description can be edited and a
    usage line cannot be reviewed away, so the two documents a person reads
    from the install say it and this reads them: each says 0600 in its receipt
    paragraph and neither carries a 0644 there.
    """
    help_text = run_cmd("--help").stdout
    # The README is the ASSEMBLY root's in the triad (#186, T009): read from
    # the root that owns it - a skip in a standalone code leg, and in the
    # composed run a failure, never a skip, if that root is absent.
    readme = ROOTS.path_for("README.md").read_text(encoding="utf-8")
    for where, text, start in (("--help", help_text, "It then writes a RECEIPT"),
                               ("README.md", readme, "**And it writes down what it placed.**")):
        assert start in text, f"{where} no longer has the receipt paragraph"
        paragraph = text.split(start, 1)[1].split("\n\n", 1)[0]
        assert "mode 0600" in paragraph, (
            f"{where} does not say the mode the receipt is born at:\n{paragraph}")
        assert "0644" not in paragraph and "644" not in paragraph, (
            f"{where} says a mode the receipt is not:\n{paragraph}")


@pytest.mark.parametrize("name", RETIRED)
@NEEDS_JQ
def test_a_retirement_reads_the_receipt_before_the_header(tmp_path, name):
    """AND THE RECEIPT IS STRONGER THAN THE HEADER, WHICH IS THE WHOLE POINT.

    The file here carries NO marker at all — nothing a `grep` could find — and
    it is still removed, because a row of this installer's own receipt says
    those exact bytes were placed at that exact path. That is ownership
    evidence rather than a searchable substring (#57, on Copilot round 3 of
    #45 at `openRepoTools:263`).

    And the row goes with the file: a receipt that still named the path would
    answer `edited` about whatever somebody puts there next.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    stale = bin_dir / name
    stale.write_text("#!/usr/bin/env bash\n"
                     f"# {name}, with no banner of any kind in it\n"
                     "echo stale\n", encoding="utf-8")
    stale.chmod(0o755)
    receipt = receipt_path(tmp_path)
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        f"{name}\t{stale}\t{hashlib.sha256(stale.read_bytes()).hexdigest()}"
        "\t2026-09-15T04:04:16Z\n", encoding="utf-8")

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not stale.exists(), (
        f"the receipt names `{name}` and its digest still matches, and it is "
        "still on PATH:\n" + result.stdout)
    assert f"{name}: RETIRED" in result.stdout, result.stdout
    assert "receipt carries its digest" in result.stdout, (
        "the line says which evidence removed it, because the two kinds are "
        f"not the same claim:\n{result.stdout}")
    assert not [row for row in receipt_rows(tmp_path) if row[1] == str(stale)], (
        "the row of a file that is no longer there was kept:\n"
        + receipt.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", RETIRED)
@NEEDS_JQ
def test_a_file_the_receipt_no_longer_recognises_is_named_and_left(tmp_path, name):
    """A DIGEST THAT HAS MOVED IS SOMEBODY'S EDIT, AND IT OUTRANKS THE MARKER.

    This file carries the header — `grep` finds it, and today's fallback would
    delete it — and the receipt says the bytes at that path are NOT the ones it
    placed. So it is a person's edit of an installed command, or their own file
    at a path one used to be at, and either way not this installer's to remove:
    named, left exactly as it is, with the one line that removes it printed for
    them, like every other file this installer did not write.

    Its row is KEPT, because the file is: a receipt drops a row when the file
    goes, not when it stops matching.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    mine = bin_dir / name
    mine.write_text(
        "#!/usr/bin/env bash\n"
        "# Installed on PATH by `openRepoTools --install`, and then edited.\n"
        "echo my own edit\n", encoding="utf-8")
    mine.chmod(0o755)
    before = mine.read_bytes()
    receipt = receipt_path(tmp_path)
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        f"{name}\t{mine}\t{hashlib.sha256(b'the bytes it placed').hexdigest()}"
        "\t2026-09-15T04:04:16Z\n", encoding="utf-8")

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert mine.is_file() and mine.read_bytes() == before, (
        "a file whose digest the receipt does not recognise was deleted on the "
        "strength of the header substring the receipt exists to replace:\n"
        + result.stdout)
    assert f"{name}: RETIRED" in result.stdout
    assert "no longer holds the bytes this installer's receipt recorded" \
        in result.stdout, result.stdout
    assert f'rm -f -- "{mine}"' in result.stdout, (
        "the act is the person's, so the line is printed filled in:\n"
        + result.stdout)
    assert [row for row in receipt_rows(tmp_path) if row[1] == str(mine)], (
        "the row of a file that is still there was dropped:\n"
        + receipt.read_text(encoding="utf-8"))


def path_without(tmp_path: Path, *names: str) -> str:
    """A `$PATH` on which none of `names` EXISTS, not one where they fail.

    A directory of symlinks to every executable the real `$PATH` carries
    except those names, in the real `$PATH`'s own order. A shim that exits 1
    (see `test_a_digest_it_cannot_take_is_a_note_too`) is a tool that FAILS;
    this is a machine that has none, which is the other thing a reviewer
    means by "a missing digest tool", and the two reach `sha256_of` through
    different arms. `bash`, `cp`, `jq` and the rest are all still found, so
    the install itself runs exactly as it does everywhere else.
    """
    farm = tmp_path / "path-without"
    farm.mkdir()
    for directory in os.environ["PATH"].split(os.pathsep):
        try:
            entries = sorted(os.listdir(directory))
        except OSError:
            continue
        for entry in entries:
            source = os.path.join(directory, entry)
            link = farm / entry
            if (entry in names or link.is_symlink()
                    or not (os.path.isfile(source)
                            and os.access(source, os.X_OK))):
                continue
            link.symlink_to(source)
    found = {name: shutil.which(name, path=str(farm)) for name in names}
    assert not any(found.values()), f"the farm still answers for {found}"
    return str(farm)


@pytest.mark.parametrize("how", ["absent", "failing"])
@pytest.mark.parametrize("name", RETIRED)
@NEEDS_JQ
def test_a_row_it_cannot_verify_is_named_and_left_never_removed(tmp_path, name, how):
    """A ROW THAT CANNOT BE CHECKED IS NOT "NO ROW" (Copilot on #103,
    `openRepoTools:711`).

    `receipt_verdict` answered `unknown` when the digest could not be taken,
    which is also what it answers when there is no row at all — so the header
    fallback ran and REMOVED the file. On a host with a missing or failing
    digest tool that is an edited, receipt-tracked command that still carries
    the header being deleted, which is the ownership mistake the receipt
    exists to prevent. The header is for "no matching row", and nothing else.

    The file carries the header, and its row names bytes it does not have —
    the exact case where the header would have been the only thing standing
    between the file and `rm`. It is left byte for byte and named with the
    `rm` printed, whether the tool is ABSENT from `$PATH` or merely FAILING,
    and the receipt is not touched: the row is about a file that is still
    there.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    mine = bin_dir / name
    mine.write_text(
        "#!/usr/bin/env bash\n"
        "# Installed on PATH by `openRepoTools --install`, and then edited.\n"
        "echo my own edit\n", encoding="utf-8")
    mine.chmod(0o755)
    before = mine.read_bytes()
    receipt = receipt_path(tmp_path)
    receipt.parent.mkdir(parents=True)
    seeded = (f"{name}\t{mine}\t{hashlib.sha256(b'the bytes it placed').hexdigest()}"
              "\t2026-09-15T04:04:16Z\n")
    receipt.write_text(seeded, encoding="utf-8")
    if how == "absent":
        path = path_without(tmp_path, "sha256sum", "shasum")
    else:
        shim = tmp_path / "shims"
        shim.mkdir()
        for tool in ("sha256sum", "shasum"):
            (shim / tool).write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            (shim / tool).chmod(0o755)
        path = f"{shim}{os.pathsep}{os.environ['PATH']}"

    result = run_cmd("--install", home=tmp_path, env={"PATH": path})
    assert result.returncode == 0, result.stdout + result.stderr
    assert mine.is_file() and mine.read_bytes() == before, (
        "a file with a receipt row that could not be checked was deleted on "
        "the strength of the header the receipt exists to replace:\n"
        + result.stdout)
    retired = [line for line in result.stdout.splitlines()
               if line.startswith(f"{name}: RETIRED")]
    assert len(retired) == 1, result.stdout
    assert str(mine) in retired[0], "the line names the destination"
    assert "could not be checked" in retired[0], retired[0]
    assert "no digest tool" in retired[0], retired[0]
    assert f'rm -f -- "{mine}"' in retired[0], (
        "the act is the person's, so the line is printed filled in:\n"
        + retired[0])
    assert "removed from" not in result.stdout
    assert receipt.read_text(encoding="utf-8") == seeded, (
        "the receipt was rewritten by a run that could digest nothing")


@NEEDS_JQ
def test_a_receipt_it_cannot_write_is_a_note_and_never_a_refusal(tmp_path):
    """FAIL CLOSED, OUT LOUD, IN ONE LINE, AND CARRY ON (#57).

    The commands, the skills and the hook entries are what a person asked for.
    A record of them this installer could not write is its problem and not
    theirs — and the header marker is still there for a later retirement to
    fall back to, which is exactly the population that fallback exists for. So
    the install SUCCEEDS and says where it could not write, why, and what that
    costs.

    A regular file where the data directory goes, because that is a `mkdir -p`
    that cannot succeed for any user, root included.
    """
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the data directory goes\n",
                       encoding="utf-8")
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_DATA_DIR": str(blocked / "data")})
    assert result.returncode == 0, result.stdout + result.stderr
    for name in INSTALLED:
        assert (tmp_path / ".local" / "bin" / name).is_file(), name
    assert f"openRepoTools: {len(INSTALLED)} of {len(INSTALLED)} placed" \
        in result.stdout
    assert f"receipt: NOT written to {blocked / 'data' / 'installed.tsv'}" \
        in result.stdout, result.stdout
    assert f"{blocked} is not a directory" in result.stdout, (
        "the note says WHY, because a person who cannot see the reason cannot "
        f"fix it:\n{result.stdout}")
    assert "falls back to the `Installed on PATH by` header" in result.stdout
    assert "$OPENREPOTOOLS_DATA_DIR" in result.stdout, (
        "and names the way out")
    assert "REFUSED" not in result.stderr


@NEEDS_JQ
def test_a_receipt_that_is_a_symlink_is_not_written_through(tmp_path):
    """THE SAME RULE EVERY OTHER PATH IN THIS FILE IS HELD TO.

    `mv -f` replaces the LINK rather than what it points at, so a receipt
    written over one silently swaps a person's link for a regular file — which
    is what `cp` through a link does, in the other direction. It is named and
    left, like every other path this installer did not make, and the install is
    untouched.
    """
    data = tmp_path / "data"
    data.mkdir()
    elsewhere = tmp_path / "somewhere-else.tsv"
    elsewhere.write_text("mine\n", encoding="utf-8")
    (data / "installed.tsv").symlink_to(elsewhere)

    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_DATA_DIR": str(data)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert (data / "installed.tsv").is_symlink(), (
        "the link was replaced by a regular file:\n" + result.stdout)
    assert elsewhere.read_text(encoding="utf-8") == "mine\n", (
        "and the bytes were written through it")
    assert f"receipt: NOT written to {data / 'installed.tsv'}" in result.stdout
    assert f"it is a symlink to {elsewhere}" in result.stdout, result.stdout
    for name in INSTALLED:
        assert (tmp_path / ".local" / "bin" / name).is_file(), name


@NOT_ROOT
@NEEDS_JQ
def test_a_receipt_it_cannot_read_is_left_whole_and_its_rows_are_not_lost(tmp_path):
    """A RECEIPT THAT EXISTS AND CANNOT BE OPENED IS NOT AN EMPTY ONE (Copilot
    round 4 on #103, `openRepoTools:575`).

    `receipt_rows_except` ended in an unconditional `return 0`, so a receipt
    whose `done <"$1"` redirection failed reported a clean scan of no rows —
    and `receipt_record` then REPLACED it with this run's rows alone, losing
    every row about a copy this run did not place. The read failure now
    propagates: the caller prints its "could not be read" note and the old
    receipt is not touched.

    The receipt is made mode 000 and seeded with a row about a file this run
    does not place, so that row's survival is the proof. The install itself is
    whole — a receipt that cannot be maintained is a note and never a refusal
    (#57) — and the receipt is read back after the mode is restored.
    """
    receipt = receipt_path(tmp_path)
    receipt.parent.mkdir(parents=True)
    elsewhere = tmp_path / "bin-elsewhere" / "park"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_text("#!/usr/bin/env bash\necho an older copy\n",
                         encoding="utf-8")
    seeded = (f"park\t{elsewhere}"
              f"\t{hashlib.sha256(elsewhere.read_bytes()).hexdigest()}"
              "\t2026-09-15T04:04:16Z\n")
    receipt.write_text(seeded, encoding="utf-8")
    receipt.chmod(0o000)
    try:
        result = run_cmd("--install", home=tmp_path)
    finally:
        receipt.chmod(0o600)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "REFUSED" not in result.stderr
    for name in INSTALLED:
        assert (tmp_path / ".local" / "bin" / name).is_file(), name
    assert f"receipt: NOT written to {receipt}" in result.stdout, result.stdout
    assert "the rows already there could not be read" in result.stdout, (
        "the note says WHY:\n" + result.stdout)
    assert receipt.read_text(encoding="utf-8") == seeded, (
        "an unreadable receipt was replaced, and the rows in it are gone")
    assert [p.name for p in receipt.parent.iterdir()] == ["installed.tsv"], (
        "a temporary was left in the data directory")


@pytest.mark.parametrize("name", RETIRED)
@NOT_ROOT
@NEEDS_JQ
def test_a_receipt_it_cannot_read_never_lets_the_header_remove_a_file(tmp_path, name):
    """UNREADABLE IS NOT "NO ROW" (Copilot round 4 on #103,
    `openRepoTools:716`).

    `receipt_verdict` scanned the receipt through a `done <"$file"` whose
    failure nothing read, so a receipt that exists and cannot be opened looked
    exactly like one that was scanned and has nothing to say about this path —
    `unknown`, and the header fallback removed an edited file. `unknown` is now
    for a scan that RAN and found no row; a receipt that cannot be opened
    answers `unreadable`, and the retirement names the receipt, names and
    leaves the file, and prints the `rm`, as it does for a row it cannot
    digest.

    The file carries the header and its row names other bytes, so the header
    is the only thing between it and `rm`.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    mine = bin_dir / name
    mine.write_text(
        "#!/usr/bin/env bash\n"
        "# Installed on PATH by `openRepoTools --install`, and then edited.\n"
        "echo my own edit\n", encoding="utf-8")
    mine.chmod(0o755)
    before = mine.read_bytes()
    receipt = receipt_path(tmp_path)
    receipt.parent.mkdir(parents=True)
    seeded = (f"{name}\t{mine}\t{hashlib.sha256(b'the bytes it placed').hexdigest()}"
              "\t2026-09-15T04:04:16Z\n")
    receipt.write_text(seeded, encoding="utf-8")
    receipt.chmod(0o000)
    try:
        result = run_cmd("--install", home=tmp_path)
    finally:
        receipt.chmod(0o600)
    assert result.returncode == 0, result.stdout + result.stderr
    assert mine.is_file() and mine.read_bytes() == before, (
        "a receipt that could not be opened was read as having no row, and the "
        "header removed an edited file:\n" + result.stdout)
    retired = [line for line in result.stdout.splitlines()
               if line.startswith(f"{name}: RETIRED")]
    assert len(retired) == 1, result.stdout
    assert str(receipt) in retired[0], "the line names the receipt"
    assert "could not be read" in retired[0], retired[0]
    assert str(mine) in retired[0], "and the destination"
    assert f'rm -f -- "{mine}"' in retired[0], (
        "the act is the person's, so the line is printed filled in:\n"
        + retired[0])
    assert "removed from" not in result.stdout
    assert receipt.read_text(encoding="utf-8") == seeded


@NEEDS_JQ
def test_a_digest_it_cannot_take_is_a_note_too(tmp_path):
    """AND NEITHER DIGEST TOOL IS A HARD DEPENDENCY.

    `sha256sum` is GNU and a stock macOS ships none; `shasum -a 256` is the
    spelling that is there instead. A machine that can answer with NEITHER — or
    one where the call fails, which is what the shims here are — still gets its
    commands, its skills and its hook entries, and the note says why the record
    of them is missing. An installer that refused to install because it could
    not write its own bookkeeping would have the priorities backwards.
    """
    shim = tmp_path / "shims"
    shim.mkdir()
    for name in ("sha256sum", "shasum"):
        (shim / name).write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (shim / name).chmod(0o755)
    result = run_cmd("--install", home=tmp_path,
                     env={"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"})
    assert result.returncode == 0, result.stdout + result.stderr
    for name in INSTALLED:
        assert (tmp_path / ".local" / "bin" / name).is_file(), name
    assert not receipt_path(tmp_path).exists(), (
        "a receipt was written out of digests nothing could take:\n"
        + result.stdout)
    assert f"receipt: NOT written to {receipt_path(tmp_path)}" in result.stdout
    assert "could not be digested" in result.stdout, result.stdout
    assert "REFUSED" not in result.stderr


@pytest.mark.parametrize("character", ["\t", "\n"], ids=["tab", "newline"])
@NEEDS_JQ
def test_a_bin_dir_that_resolves_to_a_tab_or_newline_gets_no_receipt_and_a_whole_install(tmp_path, character):
    """THE FAIL-CLOSED HALF OF THE TSV GUARD (Copilot on #103,
    `openRepoTools:425`, which asked for the test this is).

    A receipt is a tab-separated file with no escape, and
    `$OPENREPOTOOLS_BIN_DIR` is a path a person chooses. A destination
    carrying a TAB would be silently one column too many and one carrying a
    NEWLINE silently two rows — and a receipt that quietly lacks exactly the
    file a retirement will ask about is worse than none. So the whole receipt
    is not written, out loud, in one line naming the reason; and since a
    receipt that cannot be written is a note and never a refusal (#57), the
    install itself is complete.

    SINCE #241 THE DIRECTORY AS SUPPLIED CAN NO LONGER BE THE ONE THAT HOLDS
    THE CHARACTER: `--install` refuses a `$OPENREPOTOOLS_BIN_DIR` with a tab or
    a newline in it before it places anything
    (`tests/test_install_unprintable_values_241.py`). What this guard still
    answers is the CANONICAL spelling, which `receipt_add` asks about as well
    and which a symlink in the directory can make carry a character the
    supplied one never had, so that is what is driven here: a clean `bin` that
    is a link to a directory with a tab or a newline in its name. Both
    characters are accepted by the planner there (nothing before the receipt
    looks past the supplied spelling), so both are driven.
    The receipt that is already there is seeded with a row for a file that
    does not exist, which any rewrite would DROP — so byte-for-byte equality
    afterwards is the proof it was not replaced — and nothing but it may be
    in the data directory, so no temporary was left behind either.
    """
    real = tmp_path / f"real{character}dir"
    real.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.symlink_to(real)
    receipt = receipt_path(tmp_path)
    receipt.parent.mkdir(parents=True)
    seeded = ("# a receipt that somebody else's run wrote\n"
              f"a-word-that-left\t{tmp_path / 'nowhere'}"
              f"\t{hashlib.sha256(b'the bytes it placed').hexdigest()}"
              "\t2026-09-15T04:04:16Z\n")
    receipt.write_text(seeded, encoding="utf-8")

    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "REFUSED" not in result.stderr
    for name in INSTALLED:
        assert (real / name).is_file(), f"{name} was not placed"
    assert f"openRepoTools: {len(INSTALLED)} of {len(INSTALLED)} placed" \
        in result.stdout
    assert receipt.read_text(encoding="utf-8") == seeded, (
        "the receipt was replaced by a run whose destinations cannot be "
        "written as a tab-separated row")
    assert [p.name for p in receipt.parent.iterdir()] == ["installed.tsv"], (
        "a temporary was left in the data directory")
    assert f"receipt: NOT written to {receipt}" in result.stdout, result.stdout
    assert "has a tab or a newline in it and this file is tab-separated" \
        in result.stdout, (
        "the note says WHY, because a person who cannot see the reason "
        f"cannot fix it:\n{result.stdout}")
    assert "placed files recorded" not in result.stdout


@NEEDS_JQ
def test_installing_twice_leaves_no_duplicate_rows(tmp_path):
    """A ROW'S SUBJECT IS ITS DESTINATION, AND A RUN REPLACES THE ROW OF EVERY
    DESTINATION IT PLACED.

    An installer that APPENDED would grow a file by one row per placed file
    every run and would answer a retirement out of whichever one it read first.

    WHAT DOES CHANGE ON THE SECOND RUN IS THE UTC, and that is deliberate: the
    stamp says when the run RECORDED the row, not when those bytes were first
    placed, which is the honest reading of a column written by a run that
    verified a file it did not rewrite. `test_installing_twice_changes_nothing`
    is about the bin directory and the artifacts — the lines each placement
    prints — and the receipt is not one of them.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    first = receipt_rows(tmp_path)
    second_run = run_cmd("--install", home=tmp_path)
    assert second_run.returncode == 0, second_run.stderr
    second = receipt_rows(tmp_path)
    assert len(second) == len(first) == ARTIFACTS - HOOK_ENTRIES
    assert len({row[1] for row in second}) == len(second), (
        "a destination has two rows:\n"
        + receipt_path(tmp_path).read_text(encoding="utf-8"))
    assert {row[:3] for row in second} == {row[:3] for row in first}, (
        "the second run changed a name or a digest")


@NEEDS_JQ
def test_a_row_whose_file_is_gone_is_not_kept(tmp_path):
    """THE WINDOW CLOSES BY ITSELF (Copilot round 1 on #103).

    `receipt_forget` runs AFTER the `rm` it accompanies, so a write that fails
    in the instant between them would leave the receipt naming a path this
    installer's copy has left — and a row nothing ever clears is a row that
    answers a question about whatever somebody puts there next. The merge drops
    a row whose file is gone, so the next `--install` repairs it whatever
    happened, and the receipt does not grow for ever with the bin directories
    and profile roots people delete.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    receipt = receipt_path(tmp_path)
    ghost = tmp_path / ".local" / "bin" / "a-word-that-left"
    with receipt.open("a", encoding="utf-8") as handle:
        handle.write(f"a-word-that-left\t{ghost}"
                     f"\t{hashlib.sha256(b'the bytes it placed').hexdigest()}"
                     "\t2026-09-15T04:04:16Z\n")
    assert len(receipt_rows(tmp_path)) == ARTIFACTS - HOOK_ENTRIES + 1

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not [row for row in receipt_rows(tmp_path) if row[1] == str(ghost)], (
        "a row for a path with nothing at it survived an install:\n"
        + receipt.read_text(encoding="utf-8"))
    assert len(receipt_rows(tmp_path)) == ARTIFACTS - HOOK_ENTRIES, (
        "and the rows of the files that ARE there were kept")


@pytest.mark.parametrize("kind", ["directory", "symlink"])
@NEEDS_JQ
def test_a_row_whose_path_is_no_longer_a_regular_file_is_not_kept(tmp_path, kind):
    """AND WHAT IS KEPT IS WHAT COULD HAVE BEEN WRITTEN (Copilot round 2 on
    #103).

    A row is evidence about a REGULAR FILE this installer placed — that is
    `receipt_add`'s own test — so a destination that has become a directory or
    a symlink is a path the file the row is about is not at. The first shape of
    the rule above asked only "is there anything at all at that path", which
    kept those rows; the two halves now spell one test.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    gone = tmp_path / "bin-elsewhere" / "park"
    gone.parent.mkdir(parents=True)
    gone.write_text("#!/usr/bin/env bash\necho an older copy\n", encoding="utf-8")
    receipt = receipt_path(tmp_path)
    with receipt.open("a", encoding="utf-8") as handle:
        handle.write(f"park\t{gone}"
                     f"\t{hashlib.sha256(gone.read_bytes()).hexdigest()}"
                     "\t2026-09-15T04:04:16Z\n")
    gone.unlink()
    if kind == "directory":
        gone.mkdir()
    else:
        gone.symlink_to(tmp_path / ".local" / "bin" / "park")

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not [row for row in receipt_rows(tmp_path) if row[1] == str(gone)], (
        f"a row was kept for a path that is now a {kind}:\n"
        + receipt.read_text(encoding="utf-8"))
    assert len(receipt_rows(tmp_path)) == ARTIFACTS - HOOK_ENTRIES


@NEEDS_JQ
def test_the_receipt_keeps_the_rows_of_a_directory_it_no_longer_writes(tmp_path):
    """OTHER ROWS ARE KEPT, and the reason is the retirement.

    A person who moves `$OPENREPOTOOLS_BIN_DIR` still has the copies in the old
    one, and a later retirement that walks that directory is exactly the run
    that needs this evidence. A receipt keyed on the NAME would have dropped
    those rows the moment the same name was placed somewhere else.
    """
    first_dir = tmp_path / "bin-one"
    second_dir = tmp_path / "bin-two"
    assert run_cmd("--install", home=tmp_path,
                   env={"OPENREPOTOOLS_BIN_DIR": str(first_dir)}).returncode == 0
    assert run_cmd("--install", home=tmp_path,
                   env={"OPENREPOTOOLS_BIN_DIR": str(second_dir)}).returncode == 0
    destinations = {row[1] for row in receipt_rows(tmp_path)}
    for name in INSTALLED:
        assert str(first_dir / name) in destinations, (
            f"the row for the copy still in {first_dir} was dropped")
        assert str(second_dir / name) in destinations, name
    # The skill and command files are at the same paths both times, so they are
    # REPLACED rather than added; what the second directory adds is one more
    # row per file in `INSTALLED`, on top of everything the first run recorded.
    assert len(receipt_rows(tmp_path)) == ARTIFACTS - HOOK_ENTRIES + len(INSTALLED)


@NEEDS_JQ
def test_a_relative_bin_dir_is_recorded_absolute_and_asked_about_from_anywhere(tmp_path):
    """THE RECEIPT NAMES A FILE, NOT A SPELLING OF ONE (Copilot on #103,
    `openRepoTools:524`).

    `$OPENREPOTOOLS_BIN_DIR=bin` is a directory the planner accepts, and it is
    a different directory from every working directory it is run in. The first
    shape recorded `bin/park` exactly as supplied, so a later run from another
    directory compared the same string against ITS `bin/` — hashing, and
    removing, a file that was never the one the row was written for. Every
    destination is now recorded as a CANONICAL ABSOLUTE path, and every read
    resolves the target the same way before it compares.

    Here: an install from `here` with the relative `bin` leaves only absolute
    rows (and drops the old-shape relative row seeded in front of it, which is
    a row no working directory can honestly answer). Then a run from `there`
    that names the SAME directory a different way, `../here/bin`, retires the
    `restart` in `here/bin` on the strength of its absolute row — and leaves
    the user's own `restart` in `there/bin`, which has no row and no marker.
    """
    here = tmp_path / "here"
    there = tmp_path / "there"
    here.mkdir()
    (there / "bin").mkdir(parents=True)
    receipt = receipt_path(tmp_path)
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        f"park\tbin/park\t{hashlib.sha256(b'an older park').hexdigest()}"
        "\t2026-09-15T04:04:16Z\n", encoding="utf-8")

    first = run_cmd("--install", home=tmp_path,
                    env={"OPENREPOTOOLS_BIN_DIR": "bin"}, cwd=here)
    assert first.returncode == 0, first.stdout + first.stderr
    rows = receipt_rows(tmp_path)
    assert all(row[1].startswith("/") for row in rows), (
        "a destination was recorded as supplied:\n"
        + receipt.read_text(encoding="utf-8"))
    assert str(here / "bin" / "park") in {row[1] for row in rows}
    assert len(rows) == ARTIFACTS - HOOK_ENTRIES, (
        "the old-shape relative row was kept beside the absolute ones")

    stale = here / "bin" / "restart"
    stale.write_text("#!/usr/bin/env bash\n# restart, with no banner of any kind\n"
                     "echo stale\n", encoding="utf-8")
    stale.chmod(0o755)
    decoy = there / "bin" / "restart"
    decoy.write_text("#!/usr/bin/env bash\n# my own restart, nothing to do with "
                     "that installer\necho mine\n", encoding="utf-8")
    decoy.chmod(0o755)
    before = decoy.read_bytes()
    with receipt.open("a", encoding="utf-8") as handle:
        handle.write(f"restart\t{stale}"
                     f"\t{hashlib.sha256(stale.read_bytes()).hexdigest()}"
                     "\t2026-09-15T04:04:16Z\n")

    second = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": "../here/bin"}, cwd=there)
    assert second.returncode == 0, second.stdout + second.stderr
    assert not stale.exists(), (
        "the row names this file by its absolute path and its digest matches, "
        "and a run from another directory did not recognise it:\n"
        + second.stdout)
    assert "receipt carries its digest" in second.stdout, second.stdout
    assert decoy.is_file() and decoy.read_bytes() == before, (
        "the file in the OTHER directory's bin was removed")
    assert not [row for row in receipt_rows(tmp_path) if row[1] == str(stale)]


@NEEDS_JQ
def test_a_relative_row_never_names_another_directorys_file(tmp_path):
    """THE OTHER HALF OF THE SAME FINDING: A ROW WRITTEN AS `bin/restart` IS
    NOT EVIDENCE ABOUT ANY `bin/restart`.

    This is the deletion Copilot described, set up directly — the row's
    digest is the digest of THIS directory's file, because that is what a
    row recorded from the other directory's `bin/` would also say about a
    same-named file here. The old comparison was string against string, so it
    matched and removed a file the row was never about. A relative row is
    never matched now, and `receipt_rows_except` does not keep one, so it
    cannot linger and answer the next run either.
    """
    there = tmp_path / "there"
    (there / "bin").mkdir(parents=True)
    mine = there / "bin" / "restart"
    mine.write_text("#!/usr/bin/env bash\n# my own restart, nothing to do with "
                    "that installer\necho mine\n", encoding="utf-8")
    mine.chmod(0o755)
    before = mine.read_bytes()
    receipt = receipt_path(tmp_path)
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        f"restart\tbin/restart\t{hashlib.sha256(before).hexdigest()}"
        "\t2026-09-15T04:04:16Z\n", encoding="utf-8")

    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": "bin"}, cwd=there)
    assert result.returncode == 0, result.stdout + result.stderr
    assert mine.is_file() and mine.read_bytes() == before, (
        "a file was removed on the strength of a row that named a RELATIVE "
        "path, which is a row about whichever directory the run happened to "
        "be in:\n" + result.stdout)
    assert "is NOT this installer's copy" in result.stdout, result.stdout
    assert all(row[1].startswith("/") for row in receipt_rows(tmp_path)), (
        "a relative row outlived the run:\n"
        + receipt.read_text(encoding="utf-8"))


@NEEDS_JQ
def test_a_relative_data_dir_is_resolved_and_one_receipt_is_read_from_anywhere(tmp_path):
    """THE RECEIPT'S OWN DIRECTORY IS CANONICAL TOO (Copilot round 4 on #103,
    `openRepoTools:365`).

    `$OPENREPOTOOLS_DATA_DIR=data` is accepted, and `receipt_file` handed that
    string straight to every reader and writer, so the one printed path was
    `data/installed.tsv` — a spelling that means a different file from every
    working directory. The directory is now resolved (`mkdir -p` first, where
    this run is the one making it) and every read, write and line goes through
    the resolved path.

    WHAT RESOLVING CANNOT DO is make `data` mean the same directory from two
    working directories — a relative value names a different one from each, and
    that is inherent in being relative. So the run SAYS so, beside the line
    that names where the receipt went: the absolute path it resolved to and the
    way out. Here: an install from `here` with `data` writes
    `here/data/installed.tsv` and prints it absolute, with that note; a run from
    `there` that names the same directory another way, `../here/data`, reads
    the SAME receipt — the row for `restart` is found and the file removed —
    and no second receipt appears anywhere.
    """
    here = tmp_path / "here"
    there = tmp_path / "there"
    here.mkdir()
    there.mkdir()
    first = run_cmd("--install", home=tmp_path,
                    env={"OPENREPOTOOLS_DATA_DIR": "data"}, cwd=here)
    assert first.returncode == 0, first.stdout + first.stderr
    receipt = here / "data" / "installed.tsv"
    assert receipt.is_file(), first.stdout
    assert (f"receipt: {len(receipt_rows_at(receipt))} placed files recorded "
            f"in {receipt}") in first.stdout, (
        "the line names the receipt as a canonical absolute path:\n"
        + first.stdout)
    assert "a RELATIVE path" in first.stdout and f"resolved it to {receipt.parent}" \
        in first.stdout, (
        "a relative data directory is said out loud, with where it went:\n"
        + first.stdout)

    stale = tmp_path / ".local" / "bin" / "restart"
    stale.write_text("#!/usr/bin/env bash\n# restart, with no banner of any kind\n"
                     "echo stale\n", encoding="utf-8")
    stale.chmod(0o755)
    with receipt.open("a", encoding="utf-8") as handle:
        handle.write(f"restart\t{stale}"
                     f"\t{hashlib.sha256(stale.read_bytes()).hexdigest()}"
                     "\t2026-09-15T04:04:16Z\n")
    second = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_DATA_DIR": "../here/data"}, cwd=there)
    assert second.returncode == 0, second.stdout + second.stderr
    assert not stale.exists(), (
        "the row is in the receipt the first run wrote and the second did not "
        "read it:\n" + second.stdout)
    assert "receipt carries its digest" in second.stdout, second.stdout
    assert sorted(tmp_path.rglob("installed.tsv")) == [receipt], (
        "a second receipt appeared:\n"
        + "\n".join(str(p) for p in tmp_path.rglob("installed.tsv")))
    assert not (there / "data").exists()


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
    """ONE path note for everything `--install` places: the directory is the
    same one, and the same `export` line once per file reads as a problem for
    each of them."""
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
    places all of them or none, and the only way to prove "or none" is a server
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
    # THE ONE FILE A REAL GITHUB IS ASKED FOR BEFORE ANY OF THOSE (#186,
    # T007), answered the way it answers for a single repository: a 404 for
    # the code pin, which `gh` reports on stderr with the status in it. Every
    # assertion below is unchanged; the server just answers the one question
    # the installer now asks first.
    routes += (
        "*/contents/contracts/code-pin.yaml\\?*) "
        "printf 'gh: Not Found (HTTP 404)\\n' >&2; exit 1 ;;\n")
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
    of the files `--install` places. `curl` is shadowed by a script that
    exits 1 — belt and braces, so that a fake `gh` which stopped matching could
    never quietly become a real request to raw.githubusercontent.com.
    """
    return fake_github(tmp_path, FETCHED)


def test_install_places_all_or_none(tmp_path):
    """ALL IN HAND BEFORE ANY IS PLACED (openRepoShape #82, F10 of the review
    on its #83). One file at a time, dying on the first fetch that failed,
    leaves a person with a NEW `openRepoTools` and no `park` — a half-install
    that prints `installed at` and is not one — with nothing on screen to say
    which of them were missing.

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
    for its siblings and not for the lane helpers, the alias table or the
    skill — so `install_commands` fetches each of them at this ref into a
    temporary directory. THAT DIRECTORY HAS TO STILL BE THERE:
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


def test_install_names_the_repository_venv_and_whether_it_is_there(tmp_path):
    """One virtual environment per repository, outside the estate (#162):
    `--install` names this repository's, says whether it is there, and - when
    it is not - prints the two commands that make it. It never makes one: that
    needs pip and the network, and an install from a checkout needs neither."""
    cache = tmp_path / "cache"
    venv = cache / "openRepoTools" / "venvs" / "openRepoTools"
    first = run_cmd("--install", home=tmp_path, env={"XDG_CACHE_HOME": str(cache)})
    assert first.returncode == 0, first.stderr
    assert (f"openRepoTools: this repository's virtual environment is {venv} "
            "(not created; one per repository, outside the estate):") in first.stdout
    assert f"python3 -m venv {venv} && {venv}/bin/python3 -m pip install pytest" in first.stdout
    assert not venv.exists(), "the install made a venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python3").write_text("#!/bin/sh\nexit 0\n")
    (venv / "bin" / "python3").chmod(0o755)
    second = run_cmd("--install", home=tmp_path, env={"XDG_CACHE_HOME": str(cache)})
    assert second.returncode == 0, second.stderr
    assert f"virtual environment is {venv} (present;" in second.stdout


def test_the_printed_venv_command_survives_a_path_with_a_space(tmp_path):
    """Copilot round 2 on #169: the command is pasted into a shell, and the
    cache directory is the person's to choose."""
    cache = tmp_path / "my cache"
    venv = cache / "openRepoTools" / "venvs" / "openRepoTools"
    result = run_cmd("--install", home=tmp_path, env={"XDG_CACHE_HOME": str(cache)})
    assert result.returncode == 0, result.stderr
    (line,) = [ln.strip() for ln in result.stdout.splitlines()
               if ln.strip().startswith("python3 -m venv ")]
    words = shlex.split(line)
    assert words[:4] == ["python3", "-m", "venv", str(venv)], words
    assert words[5] == str(venv / "bin" / "python3"), words
