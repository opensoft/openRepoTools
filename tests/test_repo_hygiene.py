# SPDX-License-Identifier: Apache-2.0
"""Properties of THIS repository that a fork depends on and nobody re-checks.

Adapted from openRepoShape's `tests/test_repo_hygiene.py` — the rules travel
with the files. NOTHING HERE NEEDS THE SUBMODULE, on purpose: these are facts
about the four bash files and the four documents this repository ships, so
they run in a clone made without `--recurse-submodules` and they run on
Windows, which is what the Windows job is for.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

#: EVERY BASH FILE THIS REPOSITORY SHIPS, and nothing else is one. Each is a
#: file a person has on their PATH — the installer, the two estate verbs and
#: the read-only `status` — so each is held to the same shebang, mode bit and
#: `set -euo pipefail` rule. The macOS job parses these same four with
#: `/bin/bash -n`, one command per file, which is what keeps the bash-3.2
#: claim true.
#: `restart` and `lanes` join under lane-collision-protocol Amendment 11's
#: ratified decisions 7 and 6: each is one word a person has on PATH, placed by
#: `--install`, so each is held to the same shebang, the same executable bit,
#: the same LF index, the same bash-3.2 parse AND the same `set -euo pipefail`.
#: They are NOT in `LANE_BASH`, and the reason is the resolver test below: they
#: carry no copy of Amendment 9(a)'s workspace resolver because they resolve no
#: workspace — every fact either one needs comes from `lanes-edit.sh`, through
#: the reads clause (h) adds, which is the same "one implementation, several
#: callers" rule those reads exist for. A third copy of that block in a file
#: that never uses it would be a third way for it to drift.
SHIPPED_BASH = ["openRepoTools", "park", "resume", "status", "restart", "lanes"]

#: THE LANE HELPERS, which arrived here from `opensoft/brett-wip` with their
#: history under lane-collision-protocol Amendment 9(b). They are shipped bash
#: and `--install` places them, so they are held to the same shebang, the same
#: executable bit, the same LF index and the same bash-3.2 parse — but NOT to
#: `set -euo pipefail`, and the exception is deliberate rather than an
#: oversight. `lanes-edit.sh` runs `set -u` alone, because it is the register's
#: only writer and a failing command inside a lock-holding write must reach its
#: own refusal and release the lock rather than exiting where it stands.
LANE_BASH = ["lanes-edit.sh", "lane-start", "lane-end", "link-estates"]

#: Every bash file this repository ships, for the claims that are about BASH
#: and not about a command's failure discipline: the parse gate and the LF
#: index. The moved suite is 196 KB of it and is in this list for the reason
#: Amendment 9's act-3 obligation 4 gives — the macOS job parses it with bash
#: 3.2, where a `${x,,}` that nobody ran is still a syntax error.
ALL_BASH = SHIPPED_BASH + LANE_BASH + ["tests/test_lane_helpers.sh"]

#: THE COMMANDS THAT CARRY THE SHARED ESTATE RESOLVER, byte for byte. Every
#: estate command is one; the installer is not, it finds no estate.
ESTATE_COMMANDS = ["park", "resume", "status"]

#: The install line this repository documents, and openRepoShape's `--install`
#: PRINTS as its pointer. Byte-identical in both places or a person following
#: the pointer lands somewhere else, so it is spelled here once and asserted
#: against the README.
RAW_INSTALL_LINE = (
    "curl -fsSL https://raw.githubusercontent.com/opensoft/openRepoTools/main/"
    "openRepoTools | bash -s -- --install")


@pytest.mark.parametrize("name", SHIPPED_BASH)
def test_shipped_bash_is_executable_and_fails_loudly(name):
    script = REPO / name
    assert script.is_file()
    assert os.access(script, os.X_OK), f"{name} must be executable: chmod +x"
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text, (
        "a command a person has on PATH must stop on the first failure, not "
        "carry on with an unset variable")


@pytest.mark.parametrize("name", LANE_BASH)
def test_the_lane_helpers_are_executable_and_declare_their_discipline(name):
    """The lane helpers, held to what they are rather than to what the estate
    commands are (Amendment 9(b)).

    Same shebang and same executable bit — `--install` stamps 755 on everything
    it places, and a copy that is not executable is not a command. `set -u` is
    the floor all four share; `set -e` is NOT required of `lanes-edit.sh`,
    whose whole job is to hold a lock, reach its own refusal and release it.
    """
    script = REPO / name
    assert script.is_file()
    assert os.access(script, os.X_OK), f"{name} must be executable: chmod +x"
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash\n")
    assert ("set -u" in text or "set -euo pipefail" in text), (
        f"{name} must at least `set -u`: an installed command that reads an "
        "unset variable as the empty string writes somewhere nobody named")


@WINDOWS_SKIP
@pytest.mark.parametrize("name", ALL_BASH)
def test_shipped_bash_parses_under_bash(name):
    """`bash -n` on every bash file this repository ships, everywhere there is
    a bash.

    SKIPPED ON WINDOWS, AND `shutil.which` IS NOT ENOUGH TO SEE WHY. The
    `bash` a stock Windows install puts on PATH is
    `C:\\Windows\\System32\\bash.exe`, the WSL launcher — `which` finds it, it
    exits 1 with "no installed distributions" in UTF-16, and the failure reads
    as a syntax error in the file. The bash that IS a bash there, Git Bash, is
    handed `D:\\a\\...\\park` by this test and converts the path on its way in.
    Neither one answers the question this test asks, and the question is
    answered on every other platform in CI — including by the macOS job's
    `/bin/bash -n`, which asks it of the bash a Mac actually ships.
    """
    if shutil.which("bash") is None:
        pytest.skip("bash is not installed")
    proc = subprocess.run(["bash", "-n", str(REPO / name)],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr


def test_the_estate_commands_carry_the_same_estate_resolver_byte_for_byte():
    """THE DUPLICATION IS DELIBERATE AND THE CLAIM HAS TO STAY TRUE.

    `park`, `resume` and `status` are each ONE file a person has on PATH, so
    the estate resolver is copied rather than sourced: a shared `orp-estate.sh`
    would be a fifth file for `--install` to place and a broken command the
    first time somebody copied only one of them. A copy that has drifted is two
    answers to "which estate is this", which is the one thing the block exists
    to prevent. Three copies since `status` (Brett Heap's RULING of 2026-09-10,
    "lets go with a fourth file"): the cost that ruling accepted, held here.

    ASSERTED HERE AS WELL AS IN `test_park_resume_commands.py`, on purpose.
    That file carries `NEEDS_UPSTREAM` and a `bash` guard, so in a clone made
    without `--recurse-submodules` — or on Windows — its copy of this check
    SKIPS. This invariant is about three files in this repository and needs
    neither the submodule nor a shell, so it also lives where it always runs.
    """
    def block(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        start = text.index("# --- BEGIN shared estate resolver")
        end = text.index("# --- END shared estate resolver")
        return text[start:end]

    blocks = {name: block(REPO / name) for name in ESTATE_COMMANDS}
    reference = blocks["park"]
    for name, text in blocks.items():
        assert text == reference, (
            f"park and {name} have drifted apart in the shared estate resolver")
    assert len(reference.splitlines()) > 100, "the marker moved, not the block"


def test_the_lane_helpers_carry_the_same_workspace_resolver_byte_for_byte():
    """THE SAME DISCIPLINE AS THE ESTATE RESOLVER ABOVE, for the same reason,
    on the block lane-collision-protocol AMENDMENT 9(a) is made of.

    `lanes-edit.sh`, `lane-start`, `lane-end` and `link-estates` are each ONE
    file a person has on PATH, placed by `--install`, so the resolver that
    answers "where is this person's workspace repository" is copied into all
    four rather than sourced — a shared `orp-workspace.sh` would be a tenth
    file to place and a broken helper the first time somebody copied only one.

    A drifted copy is TWO ANSWERS to that question, and one answer is the whole
    of what clause (a) buys: it retired deriving the register from a script's
    own real path precisely because "a second way to find it is a second
    answer". Four copies that disagree would put that defect straight back, one
    helper at a time, and the person would meet it as a register that one
    command can write and another cannot find.

    The block carries its own markers so this test names the drift rather than
    a line number, exactly as the estate resolver's does.
    """
    def block(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        start = text.index("# --- BEGIN shared workspace resolver")
        end = text.index("# --- END shared workspace resolver")
        return text[start:end]

    blocks = {name: block(REPO / name) for name in LANE_BASH}
    reference = blocks["lanes-edit.sh"]
    for name, text in blocks.items():
        assert text == reference, (
            f"lanes-edit.sh and {name} have drifted apart in the shared "
            f"workspace resolver (Amendment 9(a))")
    assert len(reference.splitlines()) > 100, "the marker moved, not the block"
    # THE PIECES THAT MAKE IT THE AMENDMENT'S RESOLVER AND NOT SOME OTHER ONE.
    # A block that kept the markers and lost the checkout test would pass the
    # comparison above four times over.
    assert '"${AGENT_PROTOCOL_ROOT:-$HOME/.agents}/workspace.yaml"' in reference, (
        "the resolver no longer reads the one pointer file clause (a) names")
    for field in ("repository", "path"):
        assert f'lanes_ws_field {field} "$yaml"' in reference, (
            f"the resolver no longer reads `{field}:`")
    assert "rev-parse --show-toplevel" in reference, (
        "the resolver no longer checks that `path:` is the ROOT of the "
        "checkout, which clause (a) added as new behaviour")
    assert "openRepoTools wip init" in reference, (
        "the refusal no longer names the one command that fixes it")


def test_the_workspace_refusal_carries_the_reason_it_computed():
    """SIX DIAGNOSES ARE COMPUTED AND ALL SIX USED TO BE THROWN AWAY.

    `lanes_workspace_root` sets `$LANES_WS_WHY` to the one sentence that says
    WHICH of clause (a)'s ways it failed — no file, no `repository:`, no
    `path:`, a `path:` that is not a checkout, a checkout of something else, or
    a subdirectory rather than the root. Every caller reaches the resolver
    through `LANES_WS_ROOT="$(lanes_workspace_root || :)"`, a COMMAND
    SUBSTITUTION, so that assignment happened in a subshell and died with it:
    the parent printed "no reason recorded" for all six.

    Clause (a) makes failing to find the workspace "a refusal, never a guess",
    and the estate's own convention (`status:3076-3078`) is that a refusal must
    not be readable as something else. A refusal that names none of the six is
    one a person cannot act on — the fix line `openRepoTools wip init` is
    right for three of them and wrong for the other three, which want a
    `workspace.yaml` edited rather than a repository created.

    `lanes_workspace_why` therefore re-derives the reason in the PARENT shell
    before printing. This test holds that line, because nothing else would
    notice its loss: the refusal still exits 1 and still names the command.
    """
    for name in LANE_BASH:
        text = (REPO / name).read_text(encoding="utf-8")
        assert '[ -n "$LANES_WS_WHY" ] || lanes_workspace_root >/dev/null 2>&1 || :' \
            in text, (
            f"{name}'s `lanes_workspace_why` does not re-derive the reason in "
            f"the parent shell, so every refusal reads `no reason recorded`")


def test_status_carries_resumes_expand_home_byte_for_byte():
    """`expand_home` reads the `~` a person writes in `~/.agents/workspace.yaml`
    the same way in both commands that read that file. It sits OUTSIDE the
    shared resolver block — `park` has no use for it — so the resolver test
    does not hold the two copies together; this does."""
    def function(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        start = text.index("expand_home() {")
        return text[start:text.index("\n}\n", start)]
    assert function(REPO / "status") == function(REPO / "resume"), (
        "status and resume have drifted apart in expand_home")


def code_lines(path: Path) -> str:
    """The file with its whole-line comments dropped.

    Every rule below is about what these files DO, and the sentences in them
    that name openRepoShape are about the standard, about a ruling, or about
    where the code came from. Matching on the word alone would make a comment
    into a finding, which teaches the next person to delete the comment.
    """
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def test_the_estate_commands_name_no_runtime_dependency_on_the_standard():
    """`park`, `resume` and `status` depend on the ESTATE, never on openRepoShape.

    They run the estate's own `make park` / `make resume`; nothing in either
    reaches for a checkout of the standard, fetches from it, or reads an
    `$OPENREPOSHAPE_*` variable at run time. That is the whole dependency
    direction this repository exists inside: tools depend on the shape, the
    shape depends on nothing, and neither reaches for the other at run time.

    The `$OPENREPOSHAPE_REMOTE_BASE` these two used to read is
    `$OPENREPOTOOLS_REMOTE_BASE` here — a prefixed variable in a shipped file
    names the tool that ships it (openRepoShape #92, decision 2). The ONE
    mention of the old prefix that survives is a comment in `resume` naming
    `$OPENREPOSHAPE_SETUP_SH`, which is openRepoShape's own shim's documented
    offline path and still exists there; that is a cross-reference, not a call,
    which is why this test reads code and not comments.

    THE ONE `gh api` IN THESE THREE FILES is inside `status`'s `gh_api_line`,
    which every question `status` puts to GitHub goes through — the fork
    check (Brett Heap's RULING of 2026-09-11, "next layer: fork against
    upstream") and the shape pin against the standard's main (his RULING of
    the same day, "next layer: shape-pin drift") — under `--fetch` only,
    read-only, host pinned. The only other `gh` in `status` is `gh_ready`'s
    `command -v gh`. The verbs run no `gh` at all. A second call site would
    be a second place the network is reached and a second place the failure
    policy would have to be right, which is what this rule is for.
    """
    for name in ESTATE_COMMANDS:
        code = code_lines(REPO / name)
        assert "OPENREPOSHAPE" not in code, (
            f"{name} reads an $OPENREPOSHAPE_* variable; the estate commands "
            f"take no environment from the standard")
        assert "raw.githubusercontent.com" not in code, (
            f"{name} names a raw URL; the estate commands fetch nothing")
        if name == "status":
            # The usage text NAMES `gh api` to say when it is asked; that is
            # prose in a heredoc, not a call, and is set aside here.
            head, rest = code.split("cat <<'USAGE'", 1)
            calls = head + rest.split("\nUSAGE\n", 1)[1]
            api = calls.split("gh_api_line() {", 1)[1].split("\n}", 1)[0]
            ready = calls.split("gh_ready() {", 1)[1].split("\n}", 1)[0]
            assert "gh api" in api, "status's gh_api_line no longer asks gh"
            assert "--hostname github.com" in api, (
                "the one gh call no longer pins the host it asks")
            elsewhere = calls.replace(api, "").replace(ready, "")
            assert not re.search(r"(?<![\w-])gh\s", elsewhere), (
                "status runs gh outside gh_api_line / gh_ready")
        else:
            assert "gh api" not in code, (
                f"{name} calls the API; the verbs fetch nothing")


#: THE VALUE-TAKING ARMS ACROSS THE THREE COMMANDS: `park`'s three (--lane,
#: --repo, --name | --project), `resume`'s four (--repo, --workspace, --org,
#: --name | --project) and `status`'s two (--repo, --name | --project). Kept
#: by hand so that a TENTH is read rather than merely guarded — see the test.
VALUE_TAKING_ARMS = 9


def test_every_value_taking_arm_refuses_an_empty_value():
    """A FLAG GIVEN AN EMPTY VALUE IS REFUSED, in all three commands.

    `[ $# -ge 2 ]` checks only that an argument slot exists; the `${2:?…}`
    it replaced rejected an unset OR NULL one. The difference is silent every
    time, because every one of these values is read further down as "was this
    given at all?": `park --lane ""` parked with the lane dropped out of the
    WIP commit subject, and `--repo ""` in any of the three fell past the
    `--repo` branch of the resolver into the walk-up and acted on the estate
    around the current directory — the one thing naming a clone's origin was
    there to prevent.

    THIS SHIPPED TWICE, AND AN OUTSIDE REVIEWER CAUGHT IT BOTH TIMES. Into
    `park` and `resume` at 83a1601, which swapped `${2:?…}` for the arity
    check; and into `status` at fbf6f11, its first commit, where the arm was
    written that way from the start and so was never in front of the review
    that caught the other two. Nothing in this suite could see either one,
    because each command's own tests ask what a REFUSAL says, and an arm that
    does not refuse says nothing for them to read. So it is asked here, of the
    text: every line that takes `$2` into a variable carries the whole guard
    within the three lines above it.

    THE COUNT IS ASSERTED TOO, and it is hand-kept on purpose. That the guard
    is right on nine arms is what the loop proves; the number is what makes a
    TENTH — a value-taking flag somebody adds next year — arrive as a failure
    to be read rather than as a silent pass. Move it in the same commit that
    adds the arm.

    Whole-line comments are dropped first, by `code_lines`, so the three
    comment lines that QUOTE `[ $# -ge 2 ]` in order to explain why it was not
    enough on its own cannot stand in for the guard they describe.
    """
    found = 0
    for name in ESTATE_COMMANDS:
        lines = code_lines(REPO / name).splitlines()
        for i, line in enumerate(lines):
            if re.match(r'\s*[A-Z_]+="\$2"', line):
                found += 1
                guard = "\n".join(lines[max(0, i - 3):i])
                assert '[ $# -ge 2 ] && [ -n "$2" ]' in guard, (
                    f"{name}: {line.strip()} takes $2 without refusing an "
                    f"empty one")
    assert found == VALUE_TAKING_ARMS, (
        f"{found} lines take $2, not {VALUE_TAKING_ARMS}: a value-taking flag "
        f"was added or removed. Read the new arm, then move the number.")


#: `--flag <value>` and `--flag=<value>` are two spellings of ONE flag. The
#: pattern half of a `case` arm, up to its `)`, with grouped patterns kept whole.
CASE_ARM_HEAD = re.compile(r"^\s*(--[A-Za-z0-9=*|_ -]+?)\)(\s|$)")
#: The guard the two-token arms of this estate are written with.
EMPTY_VALUE_GUARD = re.compile(r'\[ -n "\$\{?[A-Za-z_][A-Za-z0-9_]*\}?" \]')


def _value_flag_arms(text: str) -> dict:
    """{flag: {"plain": arm text, "equals": arm text}} for every option arm.

    An arm runs from its pattern line to the line carrying its `;;`, so a
    multi-line arm (`lane-end`'s `--retire=*`) is read whole and not by its
    first line. Grouped patterns (`--repo | --dir | --ws | --prefix)`) count
    for every flag they name.
    """
    lines = text.splitlines()
    arms: dict = {}
    for i, line in enumerate(lines):
        head = CASE_ARM_HEAD.match(line)
        if not head or line.lstrip().startswith("#"):
            continue
        body, j = [line], i
        while ";;" not in lines[j] and j + 1 < len(lines) and j - i < 15:
            j += 1
            body.append(lines[j])
        whole = "\n".join(body)
        for token in head.group(1).split("|"):
            token = token.strip()
            if not token.startswith("--"):
                continue
            equals = token.endswith("=*")
            flag = token[2:-2] if equals else token[2:]
            if not flag:
                continue
            arms.setdefault(flag, {})["equals" if equals else "plain"] = whole
    return arms


@pytest.mark.parametrize("name", ALL_BASH)
def test_the_two_spellings_of_a_flag_refuse_the_same_empty_value(name):
    """ONE FLAG, TWO SPELLINGS, ONE ANSWER (#26, the review of `c3ebcfe`,
    `lane-start:707`).

    `lane-start --dir ""` refuses; `lane-start --dir=` set the variable to
    nothing and FELL THROUGH as if no directory had been named at all, so the
    rungs below it ran — one of which is `$PROJECTS_ROOT/<repo>` — and the
    command started in a checkout the operator never asked for instead of
    refusing a path they never gave. `restart:151`, the same flag on the
    sibling command, has carried the guard on both spellings all along, which
    is what makes this a DIVERGENCE and not a decision: eight arms across three
    files had the guard on the two-token spelling and none on the `=` one, and
    not one of them was reachable by any test in this suite, because an arm
    that does not refuse says nothing for a test to read. That is the same
    reasoning `test_every_value_taking_arm_refuses_an_empty_value` was written
    from, one command over, after an outside reviewer caught the same class
    twice.

    Derived from the arms themselves and never from a list: where a flag's
    two-token arm carries the estate's own `[ -n "$var" ]` guard, its `=` arm
    must carry one too. A flag guarded in NEITHER spelling is not this rule's
    business — `--text` is deliberately one — and a flag with only one spelling
    has nothing to disagree with.
    """
    arms = _value_flag_arms((REPO / name).read_text(encoding="utf-8"))
    offenders = [
        flag for flag, spelling in sorted(arms.items())
        if "plain" in spelling and "equals" in spelling
        and EMPTY_VALUE_GUARD.search(spelling["plain"])
        and not EMPTY_VALUE_GUARD.search(spelling["equals"])]
    assert not offenders, (
        f"{name}: `--{'`, `--'.join(offenders)}` refuses an empty value when "
        f"it is spelled `--flag \"\"` and takes one when it is spelled "
        f"`--flag=`. The second spelling then reads as ABSENT, and every rung "
        f"below the flag runs on a value the operator did give.")


#: The four helpers every assertion in the shell suite is written with, and the
#: DESCRIPTION each takes first — the string a person reads in the output.
SUITE_ASSERT_DESC = re.compile(r'^\s*(?:is|has|hasnt|skip)\s+"((?:[^"\\]|\\.)*)"')


def test_the_suite_descriptions_run_no_command_of_their_own():
    """A BACKTICK IN A DOUBLE-QUOTED STRING IS A COMMAND SUBSTITUTION, and this
    estate writes prose full of them.

    Found in the `tests-macos` log of `29d3417`, which prints the suite's own
    stderr when it fails: *"command substitution: line 4016: syntax error near
    unexpected token `newline'"*, twice. The lines are descriptions —
    `hasnt "…and never `kill <pid>`, which the ruling refuses by name"` — where
    bash read the backticks as a substitution, tried to run `kill <pid>`, and
    handed the assertion a description with a hole in it. A third,
    `the `forks` read beside it`, RAN `forks`. None of them can fail a test,
    which is why all three sat there: the description is not compared to
    anything. What they cost is the output a person reads when something else
    fails, and on one of them the words that went missing name the act the
    ruling refuses.

    So: in the description of every `is`, `has`, `hasnt` and `skip`, a backtick
    is escaped. The other arguments are untouched — they are `$(…)`
    substitutions by design.
    """
    bad = []
    for number, line in enumerate(
            (REPO / "tests/test_lane_helpers.sh").read_text(
                encoding="utf-8").splitlines(), 1):
        hit = SUITE_ASSERT_DESC.match(line)
        if hit and re.search(r"(?<!\\)`", hit.group(1)):
            bad.append(f"{number}: {line.strip()[:120]}")
    assert not bad, (
        "these assertion descriptions carry an UNESCAPED backtick, so bash "
        "runs what is between them and the description a person reads has a "
        "hole where those words were. Write ``\\` ``:\n  " + "\n  ".join(bad))


#: A line that actually FETCHES, as opposed to a line of the usage heredoc
#: that says the word. Both spellings take a quoted argument, which the prose
#: never does.
def fetching_lines(path: Path) -> list[str]:
    return [line for line in code_lines(path).splitlines()
            if 'gh api "' in line or 'raw.githubusercontent.com/$' in line]


def test_the_installer_reaches_only_this_repository():
    """`--install` fetches from `$OPENREPOTOOLS_REPO` and from nowhere else.

    An `--install` that reached into openRepoShape to complete itself would
    make this repository's installer depend on the standard at run time, which
    is the direction the pin's own header spends a paragraph refusing — and it
    is the mirror of the rule openRepoShape's own `--install` follows by
    printing a POINTER at this repository rather than fetching from it.

    `wip init` IS THE ONE EXCEPTION, and it is not `--install`'s (lane protocol
    Amendment 9(c) step 7). It materializes openRepoShape's
    `templates/workspace-root/` — nine files this repository deliberately does
    not carry a copy of, because a copy is a second answer to what the template
    is — and it does it AT THE PINNED COMMIT, not at that repository's `main`.
    The test below is the one that holds it to the pin. Every other fetch in
    this file is still `$REPO`'s.
    """
    for line in fetching_lines(REPO / "openRepoTools"):
        assert "$REPO" in line or "$SHAPE_REPOSITORY" in line, (
            f"the command fetches from a repository that is neither "
            f"$OPENREPOTOOLS_REPO nor the pinned standard:\n    {line.strip()}")


def test_the_template_is_fetched_from_the_pinned_standard_and_at_the_pin():
    """`wip init` seeds a person's workspace repository from bytes it fetches,
    and WHICH bytes is a pin question, not a `main` question.

    openRepoShape squash-merges, so a commit on a branch there is orphaned by
    the merge and a raw fetch of it 404s for the next person — the reason
    `contracts/openreposhape-pin.yaml` refuses a commit that is not on that
    repository's default branch. This test is why `wip_shape_ref` reads the pin
    rather than spelling `main`: a template that drifted under a person's feet
    would seed two workstations differently from one command.
    """
    text = (REPO / "openRepoTools").read_text(encoding="utf-8")
    assert 'SHAPE_REPOSITORY="opensoft/openRepoShape"' in text, (
        "the template's source repository is a constant in this file, by "
        "Amendment 9(c) step 7's substitution table")
    for line in fetching_lines(REPO / "openRepoTools"):
        if "$SHAPE_REPOSITORY" in line:
            assert "$ref" in line, (
                "a template fetch that does not carry the pinned ref would "
                f"take whatever openRepoShape's main holds today:\n    {line.strip()}")
    # `-e`, and not a bare script followed by `--`: BSD's `getopt` stops at the
    # first operand, so `sed -n 'script' -- "$file"` reads `--` as a FILENAME
    # there (A9 Addendum 4, R-A9-11, and the two tests at the foot of this
    # file).
    assert 'sed -n -e \'s/^commit:[[:space:]]*//p\'' in text, (
        "wip_shape_ref must read `commit:` out of "
        "contracts/openreposhape-pin.yaml rather than spelling a ref")


def test_the_readme_prints_the_install_line_the_pointer_prints():
    """openRepoShape's `--install` prints one `curl` line pointing here, and a
    reader who follows it must land on the same bytes this README documents.
    Two spellings of one install line is one of them being wrong."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert RAW_INSTALL_LINE in readme, (
        "README.md does not carry the install line openRepoShape's --install "
        f"points at, byte for byte:\n    {RAW_INSTALL_LINE}")


def test_the_readme_also_carries_the_gh_api_form():
    """BOTH FORMS, because an organisation whose policy blocks
    raw.githubusercontent.com still has a working `gh` — the same reason the
    installer tries the API first. The shim's own pointer has room for one
    line; the READMEs are where the twin lives."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "gh api repos/opensoft/openRepoTools/contents/openRepoTools" in readme
    assert "-H 'Accept: application/vnd.github.raw'" in readme
    assert "bash -s -- --install" in readme


def test_the_readme_carries_the_two_line_onboarding_chain():
    """lane-collision-protocol AMENDMENT 9(e), "The chain": a new person, from
    nothing to a lane, in TWO LINES — and neither of them is a command in this
    repository.

    `./setup.sh` runs `openRepoTools --install` and then `openRepoTools wip
    init` for the person, each best-effort, so neither is a line anybody has to
    know to type. Brett Heap's direction of 2026-09-12, verbatim "we need to
    also keep that clean so there is the least choices possible to not confuse
    the user", is the measure that clause is written to, and an earlier draft
    of it failed the measure with twelve steps.

    Held here for the reason every other document test in this file is held:
    the chain is the one part of this repository's story that is TRUE ONLY
    ELSEWHERE — in workBenches' `setup.sh` — so nothing in this repository's
    own behaviour goes red when it rots. The two preconditions are held with
    it, because a chain that omits them is a chain that fails on line 1 for a
    reason the person cannot see: `gh auth login`, since `wip init` derives the
    login from `gh api user`, and `~/.local/bin` on `PATH`, which needs a
    restarted terminal before anything `--install` placed can be typed.
    """
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "gh repo clone opensoft/workBenches && cd workBenches && ./setup.sh" \
        in readme, (
        "README.md does not carry Amendment 9(e)'s first line, byte for byte")
    assert "pclaude run <profile> --lane <repo>-<n>" in readme, (
        "README.md does not carry Amendment 9(e)'s second line")
    assert "gh auth login" in readme, (
        "README.md names neither of the chain's two preconditions: `wip init` "
        "derives the login from `gh api user`, so an unauthenticated `gh` "
        "meets a refusal on line 1")
    assert "restarted terminal" in readme, (
        "README.md does not say ~/.local/bin needs a restarted terminal "
        "before the commands --install placed are on PATH")
    assert "openRepoTools wip init" in readme, (
        "README.md does not name the act that creates the workspace, which is "
        "the by-hand half of the chain for a host with no workBenches")


def test_no_document_offers_a_windows_powershell_twin():
    """NATIVE WINDOWS PARKS NOTHING, and saying otherwise is worse than saying
    nothing. All three files here are bash; there is no `Invoke-WebRequest`
    two-liner and no PowerShell twin to point at, so on Windows the way in is
    WSL2 — which both documents say, once each."""
    for name in ("README.md", "AGENTS.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "Invoke-WebRequest" not in text, (
            f"{name} offers a Windows download line for a bash-only toolset")
        assert "WSL2" in text, f"{name} must say what a Windows reader does"


def test_claude_md_points_at_agents_md():
    assert "AGENTS.md" in (REPO / "CLAUDE.md").read_text()


def test_the_documents_say_what_bare_park_does_now():
    """Brett Heap's RULING of 2026-09-10 in this repository, verbatim: "lets
    change that so it parks the current repo. if not in a repo, then asks if
    want to park all. and park all should be park -a or park --all." It
    supersedes his openRepoShape #91 ruling of the same day (its #93), under
    which the bare form with no estate around the cwd PARKED EVERY ESTATE
    unasked — which had itself superseded ruling 3 of its #82, REFUSE and
    list. So, now: the estate around the cwd; outside every estate, list and
    ASK; `--all` / `-a` as the sweep without the question; and `resume`
    keeping the refusal for its own bare form, with no `--all` of its own.

    All of it, in both documents and the command's own header. This is the
    sentence most likely to go stale here, because these two files are the
    only place the installed commands are written down, and because every
    text this sentence has had reads perfectly well — a document that says
    `park` refuses, or that it sweeps unasked, is not obviously broken, it is
    just wrong, and an assistant reading it either tells somebody to name an
    estate the bare form does not need or, worse, treats a bare `park` in the
    wrong folder as a one-keystroke sweep of the workstation.
    """
    for name in ("README.md", "AGENTS.md", "park"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "--all" in text, f"{name} does not name the sweep's flag"
        assert re.search(r"(?<![\w-])-a(?![\w-])", text), (
            f"{name} does not name the short form, -a")
        assert "ASKS" in text, (
            f"{name} does not say the bare form ASKS outside every estate")
        assert "#91" in text, (
            f"{name} does not cite the ruling this one supersedes")
        assert "in name order" in text, (
            f"{name} does not say the order, which is the whole of what a "
            f"person watching a sweep sees")
    assert "keeps that old refusal for its own bare form" in \
        (REPO / "README.md").read_text(encoding="utf-8"), (
        "README.md does not say resume's own bare form still refuses")
    assert "`resume`'s OWN bare form still refuses" in \
        (REPO / "AGENTS.md").read_text(encoding="utf-8"), (
        "AGENTS.md does not say resume's own bare form still refuses")
    park = (REPO / "park").read_text(encoding="utf-8")
    assert "PARKED EVERY ESTATE unasked" in park, (
        "the `park` header no longer says what #91's bare form did and that "
        "it is superseded; a reader of the ruling trail needs both")


def test_the_documents_say_what_status_is_and_is_not():
    """Brett Heap's RULING of 2026-09-10 in this repository, verbatim: "lets go
    with a fourth file. start with the local status layer." `status` is the
    read-only view of an estate — what is in and out of sync — and the LOCAL
    layer: it fetches nothing unless told to, so every answer is as of the
    last fetch. His RULING of 2026-09-11, verbatim: "next layer: --fetch" —
    the flag asks origin first, the one write the command makes, to
    remote-tracking refs and nothing else.

    All of it in both documents and in the command's own header, for the
    reason the other document tests give: the wrong reading is the one an
    assistant reaches for unaided. A `status` that "checks the remote" is one
    somebody runs `git fetch` on behalf of to make current — when the flag
    is what they should reach for — and a report of findings with exit 1 is
    one somebody calls a failure. The install count is held too, because the
    install story is the sentence a first-time reader trusts — and it is NINE
    from lane-collision-protocol Amendment 9(b), not four: the four estate
    commands plus `lanes-edit.sh`, `lane-start`, `lane-end`, `link-estates`
    and the shipped `repos.tsv`. The number is asserted rather than the word
    "four" precisely so that a document which grows the install and forgets
    to say so is a red test.
    """
    for name in ("README.md", "AGENTS.md", "status"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "fetches nothing" in text, (
            f"{name} does not say status fetches nothing without the flag")
        assert "--fetch" in text, f"{name} does not name the flag"
        assert "remote-tracking refs" in text, (
            f"{name} does not bound the one write --fetch makes")
        assert "`upstream`" in text, (
            f"{name} does not say how a fork is read: a remote named upstream")
        assert "shape-pin.yaml" in text, (
            f"{name} does not say the shape pin is read")
        assert "update-shape.py" in text, (
            f"{name} does not name the exit for a shape pin that is behind")
        assert "workspace.yaml" in text, (
            f"{name} does not say the parked record is read against disk")
        assert "gh api" in text, (
            f"{name} does not say the fork check may ask gh, and only under "
            f"--fetch")
        assert "as of the last fetch" in text.lower(), (
            f"{name} does not say every answer is as of the last fetch")
        assert "local layer" in text.lower(), (
            f"{name} does not say this is the local layer, with more to come")
    for name in ("README.md", "AGENTS.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "`status`" in text, f"{name} never names the fourth command"
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "ELEVEN files" in readme, "README.md does not count the eleven files"
    assert "11 of 11 placed" in readme, (
        "README.md does not show the count line `--install` actually prints")
    status = (REPO / "status").read_text(encoding="utf-8")
    assert "--no-optional-locks" in status, (
        "status takes locks: a read-only command beside an editor must not be "
        "the thing that says index.lock exists")


def test_the_documents_say_the_sweep_skips_a_root_without_the_overlay():
    """#6, under Brett Heap's RULING of 2026-09-10 on openRepoShape #92
    ("skip roots without the overlay"): in the SWEEP, a root with no Speckit
    git overlay is SKIPPED and named, counted apart, and left out of the exit
    code — while `park <Name>` on that same root still relays the Makefile's
    refusal.

    Held in both documents and in the command's own header for the reason the
    test above is: the wrong half of this is the half that reads fine. A
    document that says only "continuing past a refusal" is not obviously
    stale, and an assistant reading it tells somebody a clean sweep failed —
    or, worse, treats four never-installed roots as four things to fix before
    the park can be trusted.
    """
    for name in ("README.md", "AGENTS.md", "park"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "SKIPPED" in text, (
            f"{name} does not say the sweep SKIPS a root without the overlay")
        assert "Speckit git overlay" in text, (
            f"{name} does not name WHAT is missing from such a root")
        assert "#92" in text, f"{name} does not cite the ruling"
        assert "setup-openspeckit" in text, (
            f"{name} does not name the installer, which is the whole of what "
            f"the person reading a skipped line has to do next")
    for name in ("README.md", "AGENTS.md"):
        assert "skipped (no overlay)" in (REPO / name).read_text(
            encoding="utf-8"), (
            f"{name} does not show the summary clause a person actually sees")


def _parser_long_options(text):
    """Every long option the file's argument loop has an arm for, taken from
    the arms themselves rather than from a list beside them."""
    loop = re.search(r"^while \[ \$# -gt 0 \]; do$(.*?)^done$", text,
                     re.S | re.M)
    assert loop, "no `while [ $# -gt 0 ]` argument loop found"
    found = set()
    for line in loop.group(1).splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        found.update(re.findall(r"--[a-z][a-z0-9-]+", stripped.split(")", 1)[0]))
    return found


@pytest.mark.parametrize("name", ["lanes", "restart"])
def test_every_option_the_parser_accepts_is_in_the_usage(name):
    """AN OPTION NOT IN THE SYNOPSIS IS AN OPTION NOBODY FINDS.

    `lanes --prefix <repo>` was parsed, documented in the BODY of `--help` and
    used by `lane-start <repo>` with no position - and missing from the SYNOPSIS
    LINE, which is the line a person reads first and often the only one they
    read. So the one way to ask for a repository's lanes by name was invisible
    to everybody who did not read to the bottom. The defect is the same one
    `test_the_unknown_subcommand_refusal_names_every_subcommand_there_is`
    exists for, one file over, and the fix is the same: DERIVE the list from
    the arms rather than restate it beside them.

    The SYNOPSIS is what is asserted, not the whole of `--help`: the body had
    `--prefix` all along, so a rule that accepted the body would have passed
    over the defect it was written for. `--help` itself is exempt, because a
    synopsis that lists it says nothing a reader typing `--help` does not
    already know.

    Held for the two words Amendment 11 adds, and not yet for the eight files
    beside them: their parsers are older, larger and not all of this shape, and
    widening the rule to them is an act with its own evidence rather than a
    line in this one.
    """
    text = (REPO / name).read_text(encoding="utf-8")
    usage = re.search(r"^usage\(\) \{\n\tcat <<'USAGE'\n(.*?)^USAGE$", text,
                      re.S | re.M)
    assert usage, f"{name} has no `usage()` heredoc"
    synopsis = usage.group(1).split("\n\n", 1)[0]
    missing = sorted(opt for opt in _parser_long_options(text)
                     if opt != "--help" and opt not in synopsis)
    assert not missing, (
        f"{name} parses {', '.join(missing)} and its usage line never names "
        f"them: an option a person cannot find is an option they do not use")


def test_restart_fences_a_lane_name_the_way_the_helper_does():
    """ONE RULE FOR WHAT A LANE NAME IS, AND `restart` HAD A WEAKER ONE.

    `lanes-edit.sh`'s `check_lane_name` refuses `"" | *[!A-Za-z0-9._-]* | .* |
    -*` - the WHOLE string, and the two leading characters a path or an option
    would start with. `restart` tested `[A-Za-z0-9]*)`, which in a `case`
    pattern pins the FIRST CHARACTER and nothing else: `repoA11-1/extra`,
    `repoA11-1 x` and `repoA11-1*` all passed it and went on to `register-row`,
    which then answered "the register has no row for lane X" about a string
    that is not a lane name at all. The refusal a person needs ("that is not a
    lane name") was replaced by one that sends them looking for a missing row.

    Held by comparing the two patterns rather than by restating either: a
    second spelling of one rule is how the two files come to disagree.
    """
    helper = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    wanted = re.search(r"check_lane_name\(\) \{\s*case \S+ in\s*\n\s*(\S.*?)\)",
                       helper)
    assert wanted, "lanes-edit.sh has no `check_lane_name` case pattern"
    pattern = wanted.group(1).strip()
    text = (REPO / "restart").read_text(encoding="utf-8")
    assert pattern in text, (
        "`restart` does not fence a lane name with `lanes-edit.sh`'s own "
        f"pattern.\n  the helper refuses: {pattern}\n  and `restart` must "
        f"refuse the same string, not merely a first character")


#: The words clause (c)'s ladder is counted in, in `lane-start` and in the
#: manual. Both spell the number out; neither writes a digit.
RUNG_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
              "seven": 7, "eight": 8, "nine": 9}


def test_the_directory_precedence_states_every_rung_it_implements():
    """THE CONTRACT THE CODE CARRIES SAID *"THERE IS NO FIFTH RUNG"* WHILE THE
    CODE A HUNDRED LINES BELOW IT HAD SIX (#26, the review of `c3ebcfe`,
    `lane-start:780`).

    `708395e` added rungs 5 and 6 for Evidence 7 - the estate's `project.yaml`
    legs and a checkout named for the home's repository, each proved by that
    directory's own `origin` - and `2f44da0` corrected the MANUAL's count to
    six. The block at the top of `lane-start` that clause (c) states the ladder
    in was corrected in neither. A contract that contradicts the code beneath
    it makes that code look unreachable, and the one act that reading invites
    is deleting it.

    Derived from the two files rather than restated: the count the block
    DECLARES, the rungs it LISTS, the rungs the implementation MARKS with its
    own `# Rung <n>` comments, and the count the manual's heading states must
    be one number. Any of the four moving alone is the drift this catches.
    """
    code = (REPO / "lane-start").read_text(encoding="utf-8")
    head = re.search(r"^# ([A-Z]+) RUNGS, FIRST ANSWER WINS", code, re.M)
    assert head, "`lane-start` no longer declares clause (c)'s rung count"
    declared = RUNG_WORDS[head.group(1).lower()]
    # FROM THE LINE AFTER THE DECLARATION TO THE FIRST LINE OF CODE: the block
    # is one run of comment lines, and the numbered items are the ladder.
    lines = code.splitlines()
    first = next(i for i, l in enumerate(lines)
                 if l.startswith(f"# {head.group(1)} RUNGS, FIRST ANSWER WINS"))
    listed = set()
    for line in lines[first + 1:]:
        if not line.startswith("#"):
            break
        item = re.match(r"#\s{3}(\d+)\. ", line)
        if item:
            listed.add(int(item.group(1)))
    implemented = {int(n) for n in re.findall(r"^# Rung (\d+) ", code, re.M)}
    assert implemented <= listed, (
        f"`lane-start` implements rungs {sorted(implemented - listed)} that "
        f"clause (c)'s own block does not list: {sorted(listed)}")
    assert listed == set(range(1, declared + 1)), (
        f"the block says {declared} rungs and lists {sorted(listed)}")
    manual = (REPO / "docs/README-lanes.md").read_text(encoding="utf-8")
    stated = re.search(r"The lane's directory, in (\w+) rungs", manual)
    assert stated, "the manual has no directory-precedence heading to count"
    assert RUNG_WORDS[stated.group(1).lower()] == declared, (
        f"the manual counts {stated.group(1)} rungs and `lane-start` counts "
        f"{head.group(1).lower()}")


def test_the_documents_say_what_a_bare_lanes_lists():
    """THE SETTLED DEFAULT, AND THE FOUR PLACES THAT STATED THE OLD ONE.

    Brett Heap settled clause (j) on 2026-09-13T20:38:11Z, verbatim "Narrow
    inside a checkout (Recommended)": a bare `lanes` INSIDE a lane checkout
    lists THAT REPOSITORY's lanes and ends with the next free position and the
    `lane-start <repo> <n>` that takes it; `lanes --all`, and a bare `lanes`
    outside every checkout, are the every-lane listing.

    The code took it in the same round that documented the OPPOSITE. `lanes`'s
    own header line, README.md's code block, the manual's "two words" block and
    `--help`'s entry all still read "every lane on this workstation" - the
    pre-settlement default, and wrong twice over, because the scope is the
    ESTATE now and inside a checkout it is one repository. Nothing was red for
    it: no assertion in this repository had ever read those four sentences,
    which is RV-B2's rule one file over - an untested sentence is a sentence
    that drifts.

    The ABSENCE half is the half that bites. A reader promised every lane who
    gets one repository's does not read a narrowing, they read a broken
    command, and the one word that would have answered them - `--all` - is the
    word the stale sentence does not carry.
    """
    surfaces = ("README.md", "docs/README-lanes.md", "lanes", "restart",
                "openRepoTools")
    for name in surfaces:
        text = (REPO / name).read_text(encoding="utf-8")
        assert "every lane on this workstation" not in text, (
            f"{name} still calls `lanes` the listing of every lane on this "
            f"workstation, which is the pre-settlement default")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "Narrow inside a checkout" in readme, (
        "README.md does not quote the settlement that narrowed the bare word")
    assert "lanes --all" in readme, (
        "README.md never shows the word that asks for every lane")
    assert "next free position" in readme, (
        "README.md does not say the narrowed listing ends with the next free "
        "position, which is the half of the settlement that is not a filter")
    usage = (REPO / "openRepoTools").read_text(encoding="utf-8")
    assert "lanes [--all] [--fetch]" in usage, (
        "`openRepoTools --help` does not offer --all, so a person narrowed "
        "into a checkout cannot find the way back to every lane")
    manual = (REPO / "docs/README-lanes.md").read_text(encoding="utf-8")
    assert "Narrow inside a checkout (Recommended)" in manual, (
        "the manual does not quote the settlement verbatim")
    assert "Yes, list and suggest (Recommended)" in manual, (
        "the manual does not quote the settlement for `lane-start <repo>` "
        "with no position, which was ratified in the same breath")


def test_agents_md_names_the_pin_rules():
    """The three rules an agent touching the submodule has to have read, and
    the reason they are in AGENTS.md rather than only in the pin's header: an
    assistant is told to read this file, and a procedure that lives outside it
    is a procedure performed from memory."""
    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert "Never edit anything under `upstream/openRepoShape` in place" in text
    assert "Never pin a commit that is not on that repository's `main`" in text
    assert "RECOMPUTED, never adjusted" in text
    assert "git submodule update --init upstream/openRepoShape" in text


def test_agents_md_is_short_enough_to_be_read():
    """THE CAP IS TODAY'S COUNT, deliberately, and it starts here.

    This repository was created on 2026-09-10 by openRepoShape's #92, and its
    AGENTS.md is the two paragraphs and two rule blocks that moved out of that
    repository's own "Parking and resuming" section plus the rules for the
    pinned submodule. A cap set at the day's count is a cap that bites from the
    first line added: the exit is to raise it and say here, in a dated entry in
    this docstring, which RULE the new lines bought — never for prose. That is
    the form openRepoShape's own two caps are kept in, and it is the form that
    makes a cap worth having.

    84 -> 90 the same day, for park-everything (openRepoShape #91, RULING
    2026-09-10, landed there as its #93). Rule 1's opening sentence is the
    part an assistant gets wrong if it is inferred rather than read: bare
    `park` with no `<Name>` and no estate around the cwd no longer REFUSES —
    it parks every estate in name order, continuing past a refusal — so
    telling somebody to name one estate is now stale advice, not a courtesy.
    The six lines are both halves of that, because `resume`'s own bare form
    deliberately keeps the refusal and an assistant is never to name one
    estate on the person's behalf to route around it.

    90 -> 95 on 2026-09-10, for #6 (Brett Heap's RULING of that day on
    openRepoShape #92, "skip roots without the overlay"). Rule 1 now says
    that a sweep ending `…, 4 skipped (no overlay)` and exiting 0 is a CLEAN
    run and that what those four want is `setup-openspeckit`, because the
    reading an assistant reaches for unaided is the opposite one — four
    estates that "did not park" look like four things to chase, and chasing
    them means rerunning a park that was never going to run there. The fifth
    line is the other half: naming such a root still refuses, and relaying
    that refusal is the answer.

    95 -> 99 on 2026-09-10, for the `--all` ruling (Brett Heap, that day, in
    this repository: "lets change that so it parks the current repo. if not
    in a repo, then asks if want to park all. and park all should be park -a
    or park --all"). Rule 1's opening now says the three things an assistant
    gets wrong unaided: the bare form parks the estate around the cwd;
    outside every estate it ASKS, and the assistant's stdin is not a
    terminal, so in its hands that is a refusal naming `--all`; and `--all`
    is for when the person wants everything, never a way past naming the one
    estate they meant. The fourth line says `resume` has no `--all`, so
    nobody invents one.

    99 -> 111 on 2026-09-10, for `status` (Brett Heap's RULING of that day,
    "lets go with a fourth file. start with the local status layer"). One
    line in the opening for the third command, and rule 4 — the one an
    assistant gets wrong unaided in both directions: `status` fetches
    nothing, so a stale answer is not a bug to fetch around but the local
    layer doing what it says; and exit 1 is findings printed, not a failure,
    so relay the lines. The rule also says the bare form outside every
    estate reads them all WITHOUT asking, so nobody waits for a question
    `status` never asks.

    111 -> 117 on 2026-09-11, for `--fetch` (Brett Heap's RULING of that day,
    "next layer: --fetch"). Rule 4 now says the flag is the ONE way `status`
    reaches the network and the one write it makes, bounded to
    remote-tracking refs — so an assistant asked for a current answer runs
    `status --fetch` rather than fetching by hand, and knows a failed fetch
    is a finding on that row, not a reason to retry the whole report.

    117 -> 122 on 2026-09-11, for the fork layer (Brett Heap's RULING of that
    day, "next layer: fork against upstream"). Five lines in rule 4 say how a
    fork is read — a remote named `upstream`, or `gh api` once under `--fetch`
    — and the two things an assistant gets wrong unaided: that this is the
    ONE use of `gh` in these commands and it is read-only, and that the
    `git remote add upstream …` a finding names is the person's to run.

    122 -> 133 on 2026-09-11, for the shape-pin layer (Brett Heap's RULING of
    that day, "next layer: shape-pin drift"). Rule 4 says what an assistant
    must never do about a drift finding — re-digest the copy or edit the pin
    — and what it must not read into "currency not read": that the pin is
    current. Both are the readings reached for unaided.

    133 -> 140 on 2026-09-11, for the parked-record layer (Brett Heap's RULING
    of that day, "next layer: parked record against disk"). Eight lines in
    rule 4 say the three things an assistant reaches for and must not: a
    `git worktree add` for a feature the record has and disk does not
    (`resume <Name>` is the exit), a reset for a worktree behind a newer
    record (rule 1 stands), and a hand-edit of the record for a worktree it
    does not know (`park` is the exit).

    140 -> 142 on 2026-09-11, for the record layer's review (Copilot on #13).
    Rule 4 now carries the one exception to "`resume <Name>` is the exit": a
    record parked with `--no-push` never sent the WIP commit anywhere, so
    `resume` refuses it and reaching for it is the advice the rule's own next
    clause rules out — the exit is the workstation that has the commit. Two
    lines, because an assistant handed that finding otherwise reaches for the
    one command the finding beside it has just refused.

    142 -> 145 on 2026-09-11, for the review of #18: a STALE WORKTREE
    REGISTRATION — the block `worktree list` keeps for a directory that is
    gone — is `git worktree prune`'s to clear, and `resume` cannot work
    around it, because the extension matches a leg on the registered path
    alone. Three lines, for the two reaches an assistant makes when `resume`
    says "already registered" or `git` says "already used by worktree at":
    `worktree add --force`, which builds the pair git refused to build, and a
    delete under `.git/worktrees/`, which is the record of the registration
    and not a scratch directory.

    145 -> 147 on 2026-09-11, for the same review's next round: `git worktree
    prune` SKIPS a LOCKED registration, so the rule above was an exit that
    does not work for that one. Two lines put `git worktree unlock <path>` in
    front of it and say the finding names which kind it is — without them an
    assistant follows the prune, watches nothing change, and reaches for the
    two deletes the same sentence forbids.

    147 -> 149 on 2026-09-11, for the round after that: a registration git
    calls prunable can have its DIRECTORY still on disk, and the prune clears
    the registration without touching it, so `git worktree add` then refuses
    the path in its own words, "already exists". Two lines say that directory
    is moved aside and not deleted — it holds whatever the worktree held, and
    an assistant that deletes it to make `resume` run has thrown away the one
    copy of somebody's work.

    149 -> 150 on 2026-09-11, for note (d) of the second independent review of
    #18: a record whose `pushed:` is neither `true` nor `false` is one
    `resume` refuses exactly as it refuses `--no-push` — `resume.sh`'s RR6 is
    `[ "$pushed" != true ]` — and rule 4 gave `resume <Name>` as the exit for
    it. One line puts it in the same exception, because an assistant that
    reads the rule rather than the finding beside it reaches for the one
    command that cannot answer that record.

    150 -> 152 on 2026-09-11, for note 7 of the independent review of #20: a
    record that names NO PARKED COMMIT for a leg is a THIRD record `resume`
    refuses, and rule 4 gave `resume <Name>` as the exit for it. It is not
    the `pushed:` exception in other words — `resume.sh` refuses this one at
    RR1, comparing origin's tip with a parked commit that is absent and so
    never matches, not at RR6 — so the two lines are its own clause and its
    own reason, with the same re-park as the exit. An assistant that reads
    the rule and not the finding beside it reaches for `resume <Name>`
    again, and this is the record that answers it with "has moved since it
    was parked".

    152 -> 153 on 2026-09-11, for note 8 of the same review: a record that
    gives a leg NO ROLE, which `resume` refuses the WHOLE feature for — its
    `collect_legs` maps each role onto the checkout and its `*) return 1`
    takes every other leg of that feature with it — in words about the
    project's SHAPE that say nothing about the role. One line, in the same
    exception and with the same re-park, because "`resume <Name>` brings it
    back" is the sentence it falsifies too.

    153 -> 155 on 2026-09-11, for the independent review of #21 and its note
    on a ROLE THIS CHECKOUT'S SHAPE DOES NOT MOUNT: the same `collect_legs`
    refusal of the WHOLE feature as a leg with no role, reached by a
    different line of it, and the two lines the clause buys are the two
    exits, which are not one. A misspelt role is a record to write afresh
    from the workstation that has the feature; a role that is really another
    shape's is a record that is RIGHT, and the feature comes back in a
    checkout of that shape — an assistant told only "re-park" would send
    somebody round that loop for ever.

    155 -> 159 on 2026-09-12, for the same review's note on a BRANCH GONE
    FROM ORIGIN: `resume` refuses that record at RR2 — "<branch> is no longer
    on origin in the <role> leg" — before it compares any commit, and rule 4
    gave `resume <Name>` as the exit for it. The four lines are the two exits
    RR2 actually gives and the flag that reaches them. NEITHER IS A RE-PARK,
    which is why this is not one more clause on the exception above it: a
    feature that LANDED wants its record entry deleted, and a branch deleted
    by mistake wants pushing again from the workstation that parked it, and
    an assistant that reaches for the re-park it has read four times by now
    writes a record `resume` refuses again for the same reason. The
    `--fetch` half is the other thing it would get wrong unaided: without
    that flag a missing `origin/<branch>` here is USUALLY a branch parked
    elsewhere since this clone last fetched, which `resume` fetches and
    brings back, so the finding still names `resume` and the flag is what
    settles the two apart.

    159 -> 162 on 2026-09-12, for the follow-up's own note on A ROLE THIS
    CHECKOUT'S SHAPE HAS NO PLACE FOR, which the rule had as "a ROLE THIS
    SHAPE DOES NOT MOUNT". Mounting is not the test `resume` makes:
    `collect_legs` maps `spec` and `code` only onto a three-leg checkout and
    `repo` only onto a single one, so a role this root mounts perfectly well
    — `assembly`, which the three-leg shape HAS, or the other shape's role in
    a root that happens to have the directory — is refused with the rest. The
    three lines buy the widened rule and A THIRD EXIT: an assistant told
    "re-park, or a checkout of that shape" has nowhere to send a record whose
    role belongs to NEITHER shape, and would send somebody round the re-park
    loop for ever, which is the loop the entry above this one bought its two
    lines to stop.

    162 -> 169 on 2026-09-12, for the independent reviewer's note that
    `worktree_on_branch` matches ANY path while RR4 matches only the COMPUTED
    one. Seven lines, and every one buys a thing an assistant gets wrong
    unaided. That the path is computed HERE — `<worktree_root>/<branch>` out
    of this checkout's `git-config.yml`, the leg's own mount under it — and
    not read out of the record, which carries a `worktree_root:` of its own
    that `resume.sh` loads and never uses. That a worktree on the branch
    somewhere else is not merely unseen but a WHOLE-FEATURE refusal, because
    `git worktree add` cannot take a branch another worktree holds. That
    `park` is blind to it too, which is what rules out the "park it again"
    every other exception in this rule ends in. And that the exit is a `git
    worktree move`, the PERSON'S to run, with no such command for a leg's own
    checkout. Without them "a recorded feature with no worktree here" reads as
    "a worktree on the branch is a worktree here", which is the reading this
    layer had.

    169 -> 177 on 2026-09-12, for that reviewer's second and third notes —
    RR3, a path that merely EXISTS at the computed path, and RR4's second
    arm, a worktree REGISTERED there on another branch. Eight lines, and the
    entry above is why they are not free: it taught the rule that the
    computed path is the only one either verb reads, and an assistant that
    knows only that reads "nothing of ours is there" as "`resume` will make
    it". What these buy is that the refusal comes BEFORE origin is read — so
    neither RR2's exits nor the re-park below them is what answers it — and
    that the exit turns on one thing only, WHAT GIT HOLDS at that path: a
    `git worktree move` where it holds a worktree, because `mv` on a
    registered one leaves git holding the path it was at, and a plain `mv`
    where it holds none, because `git worktree move` is no command for a
    directory git never made. The `unlock` and the `prune` ride in one
    clause rather than a sentence each, because they are the pair this rule
    already names above it, and both are exits that were RUN: `worktree
    move` refuses a locked worktree and `worktree add` refuses a path a dead
    registration still names, so neither command clears the path alone.
    177 -> 181 on 2026-09-12, for the independent review's should-fixes on
    this same paragraph. Four lines, and every one of them a sentence the
    rule had wrong rather than one it was missing. That the root is read out
    of `$SPECKIT_GIT_WORKTREE_ROOT` FIRST — the variable both verbs read
    before any file, which "out of THIS checkout's `git-config.yml`, and
    read no other" actively denied, sending an agent that has it set to the
    wrong path with the rule's own authority behind it. That the refusal is
    made at whichever check the leg reaches first, the `git worktree add`
    being only the one it reaches with the branch still AT the parked
    commit: moved on it is the divergence, behind it the behind-ness, gone
    from origin the gone-ness, all four run against the extension that day,
    and a rule that quotes the wrong mechanism teaches an assistant to
    disbelieve the refusal when the words do not match. And that a `worktree
    prune` goes in front of the move where git still holds the destination
    registered with nothing on disk, because `worktree move` refuses such a
    destination in the same sentence `worktree add` does — an exit that was
    run and did not work is worse than no exit at all.

    181 -> 182 on 2026-09-13, for Copilot's first round on #27 (suppressed),
    verbatim: "This contract documents only the environment override and
    `git-config.yml`, but the implementation also falls back to the shape
    default (`worktrees` for a three-leg root or `../<root>-worktrees` for a
    single root). For an estate without either override, readers cannot derive
    the path that `resume` and the recovery guidance use; include that third
    source in this statement and its mirrored help/README wording." ONE line,
    and it buys the case an estate usually IS: the entry above spent four
    lines making the rule name `$SPECKIT_GIT_WORKTREE_ROOT` because "read no
    other" denied a source, and this list denied the one almost every estate
    actually uses. A rule that reads as exhaustive and is not sends an agent
    to look for a `git-config.yml` that was never written, and then to guess.

    182 -> 187 on 2026-09-13, for Copilot's fourth round on #27 (suppressed),
    verbatim: "This contract says every off-path worktree's exit is `git
    worktree move`, but the implementation deliberately suppresses that command
    for `path: \".\"` and for a symlink-spelled worktree root because the move
    cannot produce a path `resume` registers. Please document those exceptions
    here so the operational guidance does not direct users to a non-working
    recovery." IT IS DRIFT THIS BRANCH MADE, in the two rounds that suppressed
    those commands, and it is the drift these caps exist to catch: a rule that
    promises a command the command itself refuses to print. Five lines — the
    `worktree unlock` a locked source wants, and the three states that get no
    move at all, with the reason for the one a reader cannot guess (git
    registers the path a link resolves to and `resume` compares the one you
    wrote, so the move runs and changes nothing).

    155 -> 179 on 2026-09-13, for lane-collision-protocol AMENDMENT 9, ratified
    that day, and its adoption act 3 — the one change to this repository that
    is not a change to the estate verbs at all. Four executables, a shipped
    data file, a suite and a manual arrived here from a person's workspace
    repository, and `openRepoTools` grew the verb that creates such a
    repository. The lines buy four things an assistant cannot infer from the
    files:

    (a) the opening count, which said THREE INSTALLED COMMANDS and now says
    what `--install` actually places, because the install story is the
    sentence a first-time reader trusts and this is the release that moved it;

    (b) the one paragraph that says the lane tooling answers to a DIFFERENT
    document — the lane collision protocol, not openRepoShape — that the code
    is here and the data is not, that all four resolve the register through
    `$AGENT_PROTOCOL_ROOT/workspace.yaml` and never from their own location,
    and that their exit codes are the protocol's: 1 is *registry not found*
    there and *findings were printed* here. Two toolsets now ship under one
    installer, so one number means two things across that seam, and an
    assistant that reads a 1 without knowing which command produced it reports
    a refusal as a report or a report as a refusal (Amendment 9(a), (c));

    (c) rule 2, which was "the ONLY writer of `~/.agents/workspace.yaml`" and
    is now the two, because clause (c) step 9 makes `wip init` the second. The
    invariant retired ON PURPOSE and is rewritten here rather than found by a
    red test (Amendment 9, act 3 obligation 3) — and the rule it still carries
    is the one that matters, that the assistant is neither writer and passes
    neither `--workspace` nor `wip init` on its own initiative;

    (d) the bash-3.2 line in the testing section. The four arriving
    executables are parsed under macOS bash 3.2 in CI, where `${x,,}` is a
    syntax error — that gate found `lanes-edit.sh`'s `${base,,}` on arrival —
    and an assistant that edits 380 KB of newly arrived bash without knowing
    the dialect writes the same defect back in. It names the runner for the
    moved suite in the same breath, because a 122 KB bash suite that no job
    runs is not a suite (act 3 obligations 4 and 6).

    162 AND 179 MEET AT 186 on 2026-09-13, where act 3's branch merged `main`.
    Both raises start from the same 155 and neither touches the other's lines:
    `main` bought 7 for `resume`'s two refusals, this branch bought 24 for
    Amendment 9's arrival, and the merged file is 186. The cap is the count of
    what merged, not either side's number — and both entries stay, because each
    still names the rule its own lines bought.
    211 -> 214 on 2026-09-13, for Copilot's eighth round on #27 (suppressed):
    the round before it widened the symlink QUESTION from the worktree root to
    every parent of the computed path and left this rule naming the root, which
    for a link at the feature directory or a mount's parent is the wrong
    setting to send a person to. Three lines, and they are the difference
    between a remedy that works and one that does not: a link AT or ABOVE the
    worktree root is a `worktree_root` to respell, and a link BELOW it is a
    component that has to BE a directory rather than point at one.

    187 AND 186 MEET AT 211 on 2026-09-13, where this branch merged `main`
    after Amendment 9's act 3 landed there. Both raises start from 162 — the
    count after the commit below this branch — and neither touches the other's
    lines: `main` bought 24 for the lane tooling's arrival, this branch bought
    25 for the path `resume` computes and the four rounds of review on it, and
    the merged file is 211. The cap is the count of what merged, not either
    side's number, and every entry above stays, because each still names the
    rule its own lines bought.
    """
    lines = (REPO / "AGENTS.md").read_text().splitlines()
    assert len(lines) <= 214, f"AGENTS.md is {len(lines)} lines; the cap is 214"


def test_readme_is_short_enough_to_be_read():
    """THE CAP IS TODAY'S COUNT, for the reason above and set the same day.

    The README says what the two commands are, that they add no mechanics, both
    install forms, the environment, the dependency direction, how to bump the
    pin and how to run the tests. That is the whole of what this repository
    has to explain — the estate verbs' own behaviour is `park --help`,
    `resume --help` and openRepoShape's README, which this one links rather
    than restates. A cap raised for prose is not a cap; a cap raised in a dated
    entry naming the rule it bought is.

    160 -> 165 the same day, for park-everything (openRepoShape #91, RULING
    2026-09-10, landed there as its #93). Five lines rewrite the "How the
    estate is found" sentence that used to say bare `park` REFUSES with no
    estate around the cwd: it now parks every estate it finds, in name order,
    continuing past a refusal, and the same sentence says `resume`
    deliberately keeps the old refusal — so a reader of one paragraph gets
    both halves rather than one turning stale next to the other. It tracks
    openRepoShape's own README, which moved 1219 -> 1225 for the same rule.

    165 -> 172 the same day, for the pin-bump procedure's ORDER. The fenced
    block staged `contracts/openreposhape-pin.yaml` on the line ABOVE the
    sentence telling the reader to edit it, so run literally it committed the
    moved gitlink with the old pin — and that is invisible where you are
    standing, because this suite reads the pin out of the working tree and the
    gitlink out of `git ls-tree HEAD`. Green locally, red in CI. Seven lines
    put the edit inside the block and say why the order is the order; a
    procedure that is wrong in the one document a first-time bumper reads is
    worth more than seven lines.

    172 -> 178 the same day, for #6 (Brett Heap's RULING of 2026-09-10 on
    openRepoShape #92, "skip roots without the overlay"). Six lines finish
    the "How the estate is found" paragraph #91 rewrote: the sweep SKIPS a
    root with no Speckit git overlay rather than failing on it, shows the
    `…, 4 skipped (no overlay)` clause a person actually sees, names
    `setup-openspeckit` as what such a root wants, and says that naming that
    same root still relays its refusal. Both halves in one paragraph, for the
    reason the #91 lines are: a reader who gets one of them and not the other
    reads a clean sweep as a failed one.

    178 -> 182 on 2026-09-10, for the `--all` ruling (Brett Heap, that day,
    in this repository). One line in the code block for `park --all`, and
    three in the "How the estate is found" paragraph, which now says what the
    bare form does outside every estate — list, ASK, and refuse naming
    `--all` where there is no terminal — and that `--all` / `-a` is the sweep
    without the question, from anywhere. The #91 sentence it replaces said
    the bare form swept unasked, which is the reading this paragraph now
    exists to correct.

    182 -> 203 on 2026-09-10, for `status` (Brett Heap's RULING of that day,
    "lets go with a fourth file. start with the local status layer"). The
    install story moves from three files to four in every sentence that
    counted them; one paragraph says what `status` reads and that it fetches
    nothing; two lines in the "Using them" block show its two forms; and one
    paragraph gives the exit codes and the bare-form rule — read them all,
    without asking — because a read-only report that "checks the remote" is
    the reading a first-time user brings, and this is where it is corrected.

    203 -> 214 on 2026-09-11, for `--fetch` (Brett Heap's RULING of that day,
    "next layer: --fetch"). Four lines in the `status` paragraph name the
    flag, what it runs and the one write it makes; one line in the "Using
    them" block shows it; one sentence in the exit-code paragraph says a
    failed fetch is a finding on its row. The sentence that said `--fetch`
    refuses by name is gone, because it no longer does.

    214 -> 221 on 2026-09-11, for the fork layer (Brett Heap's RULING of that
    day, "next layer: fork against upstream"). Seven lines in the `status`
    paragraph say how a fork is read — a remote named `upstream` from local
    refs, or `gh api` once under `--fetch` for an origin on github.com — that
    a fork is a finding naming the parent and the remote to add, and that
    this is the one use of `gh` in these commands; the list of layers still
    to come loses one.

    221 -> 232 on 2026-09-11, for the shape-pin layer (Brett Heap's RULING of
    that day, "next layer: shape-pin drift"). Seven lines in the `status`
    paragraph say what the pin is, the three things read against it, where
    currency comes from and the exit named; the list of layers still to come
    loses another.

    232 -> 241 on 2026-09-11, for the parked-record layer (Brett Heap's RULING
    of that day, "next layer: parked record against disk"). Seven lines in
    the `status` paragraph say what the record is, where it is found, the
    four ways record and disk drift apart, and that no config or no record
    is a note; the list of layers still to come is gone, because none is.

    241 -> 242 on 2026-09-11, for the record layer's review (Copilot on #13).
    One line in the `status` paragraph gives the exception to "`resume
    <Name>` brings it back": where the record says `--no-push`, only the
    workstation that parked it can. It was left to be inferred from the
    `--no-push` finding two clauses later, and `status` itself now says the
    two states in one line rather than in two that contradicted each other.

    242 -> 244 on 2026-09-11, for the review of #18: the STALE REGISTRATION
    state, which the paragraph did not have. Two lines say that a worktree
    which is gone while `git worktree list` still holds its registration is a
    prune — after an unlock if it is locked — BEFORE `resume <Name>` can do
    anything, because the paragraph otherwise promises a recovery the
    command's own finding contradicts.

    244 -> 245 on 2026-09-11, for the round after that: the registration can
    be stale with its DIRECTORY still on disk, which the prune leaves behind
    and `git worktree add` then refuses. One line says that directory is
    moved aside, so the recovery the README describes is the whole of the one
    `status` prints.

    245 -> 246 on 2026-09-11, for note (d) of the second independent review of
    #18: the same exception in this paragraph's own words — a `pushed:` that
    is neither true nor false is a record `resume` refuses just as flatly as a
    `--no-push` one, and the paragraph otherwise promises a recovery the
    command's own finding rules out. One line, and the finding list beside it
    names that record too.

    246 -> 248 on 2026-09-11, for note 7 of the independent review of #20: a
    record that names no parked commit for a leg. One line puts it in the
    paragraph's own exception — with it, only the workstation that parked it
    can park it again, because `resume` refuses such a leg as moved-on — and
    one puts it in the finding list beside "a worktree whose tip is not the
    parked commit", which is the arm that CANNOT RUN when the record names
    none to compare the tip with. Both halves for the reason the note (d)
    line was written: the paragraph otherwise promises a recovery the
    command's own finding rules out.

    248 -> 249 on 2026-09-11, for note 8 of the same review: a leg the record
    gives no role. The same two places — the exception, because `resume`
    refuses the whole feature for such a leg and only a re-park writes the
    roles back, and the finding list, because this is a finding on the root's
    row and not on any leg's.

    249 -> 250 on 2026-09-11, for the review of #21's note on a role this
    shape does not mount: the same two places again — the exception, because
    `resume` refuses the whole feature for it, and the finding list — and
    one line, because the paragraph repacked as it took the words. The
    second exit is in it for the reason the AGENTS.md entry gives.

    250 -> 251 on 2026-09-12, for note 1 of that review: a FEATURE the record
    lists no leg for, which `collect_legs` refuses whole at its closing
    `[ "${#LEG_ROLES[@]}" -gt 0 ]`. One line, and it buys the one word that
    keeps the list honest — "feature", where every other entry beside it is a
    leg. AGENTS.md takes the same state in the words it already had and
    repacks, so its cap does not move.

    363 -> 382 on 2026-09-13, for lane-collision-protocol AMENDMENT 11's
    ratified decisions 6 and 7: two new words on PATH, `restart` and `lanes`,
    which a person reading this file has to be told exist and told what they
    do, plus the `$LANES_WORKSTATION` row that decision 8(d) makes
    load-bearing. The cap moves with the toolset and never with prose, and it
    is raised from the 363 the merge of `main` left rather than from the 358
    this branch started at — both histories below, newest first.

    251 -> 255 on 2026-09-12, for the same review's note on a BRANCH GONE
    FROM ORIGIN. The same two places once more: three lines put it in the
    exception, because the exits are the record's own entry and a push from
    the workstation that parked it rather than the re-park every other
    exception ends in, and one puts it in the finding list, because a
    recorded branch this repository has no `origin/<branch>` for is a state
    of the RECORD against origin that no other entry in that list covers.
    The `--fetch` clause is in the exception for the reason the AGENTS.md
    entry gives: without it the two readings of a missing ref are not one
    the command may choose between.

    255 -> 256 on 2026-09-12, for the same widening: "a role this shape does
    not mount" becomes "a role this shape has no place for", with what that
    covers and the third exit, in the exception and in the finding list. One
    line, because the paragraph repacked as it took the words — and it is a
    line about the RULE and not about the wording: a reader who takes
    "mount" literally reads `assembly`, which this repository's own fixtures
    mount at `.`, as a role that is fine.

    256 -> 261 on 2026-09-12, for the same reviewer's note on the PATH a
    worktree is at. Five lines, and all five in the finding list rather than
    in the exception above it, because this is not an exception to `resume
    <Name>`: nothing is being brought back — the work is already here, and
    neither verb can see it. What they buy is the path itself, said to be
    computed in THIS checkout and not carried by the record, and the exit,
    which is a `git worktree move` and not the re-park every other entry
    beside it ends in: `park` collects the features under that root and no
    others, so a re-park writes nothing about this one.

    261 -> 267 on 2026-09-12, for the same reviewer's second and third notes
    on WHAT IS AT that path. Six lines, and all six in the EXCEPTION
    above the finding list rather than in the list itself, which is where the
    entry above put its own: this IS a record `resume <Name>` brings back —
    the work is not here, and nothing of the person's is at that path — and
    all that stands between the two is a directory, a file or somebody else's
    worktree. So it is an exception to the promise, and the promise is what
    it falsifies; and the exit is neither the re-park every other exception
    ends in nor the prune the one above it names, but a move whose command
    depends on what git holds at that path — two of the six lines, because
    a `worktree move` that names no `unlock` in front of a locked worktree,
    or an `mv` that leaves a dead registration standing, is an exit that was
    run and did not work.

    267 -> 268 on 2026-09-13, for the same round's suppressed comment read
    against this text: the finding list said the path is "read out of
    `$SPECKIT_GIT_WORKTREE_ROOT` or this checkout's `git-config.yml`" and left
    out the SHAPE's own default, which is where every estate with neither
    override gets it — which is most of them. One line, and the same one
    AGENTS.md rule 4 and `status --help` take, because the three texts say the
    same things or one of them is wrong.

    268 -> 270 on 2026-09-13, for the same round read against this text: the
    finding list promised a `git worktree move` as the off-path exit without
    the three states where `status` deliberately prints none. Two lines, and
    the same two AGENTS.md rule 4 and `status --help` take, because a reader
    sent to a command the command will not print is worse off than one told
    nothing.

    251 -> 353 on 2026-09-13, for lane-collision-protocol AMENDMENT 9, ratified
    that day, and its adoption act 3. This is the largest single raise this
    file has taken and the reason is not prose: the repository grew a second
    toolset and a verb. The docstring above says the cap is today's count
    because "the README says what the two commands are … that is the whole of
    what this repository has to explain" — and after this release it is not
    the whole, so the sentence that set the cap is what changed. Four
    sections, and each is the answer to a question a reader of the old README
    could not answer at all:

    § "The lane tooling" — that `lane-start`, `lane-end`, `lanes-edit.sh` and
    `link-estates` are here now, with their history; that what moved is the
    CODE and the register, the logs and the handoffs stay in the person's own
    workspace repository where Amendments 4 and 5 put them; and that every one
    of them finds that data through `$AGENT_PROTOCOL_ROOT/workspace.yaml` and
    never from its own location, refusing rather than guessing. A reader who
    finds four unexplained executables at this repository's root otherwise
    reaches the opposite conclusion — that the data moved too — which is the
    one thing Amendment 9 does not do.

    § "`openRepoTools wip init`" — the verb. `openRepoTools:13` said "IT
    INSTALLS AND IT DOES NOTHING ELSE. There is no verb here", and Brett
    Heap's ruling 4 of 2026-09-12 ("openRepoTools wip init") retired that
    line. A command that creates a repository, seeds it from a pinned
    template, pushes, writes a file outside every repository and runs a linker
    cannot be documented in a sentence, and the paragraph that costs the most
    lines is the one that earns them: the push to `main` IS the ruleset probe,
    so a person meets the organisation's PR-only gate here rather than at
    their first `lane-start`, which is the worst place to meet it. Two of
    these lines are the OTHER half of that probe, and they were added after
    an adversarial read found the command could not keep the promise the
    first half makes: a refused push is exit 2 with the clone and the seed
    commit left where they are, so the re-run after an administrator acts has
    only to push. A reader who is not told that reaches for `--dry-run`, a
    second `--install`, or a hand-made repository.

    the two-line onboarding chain at the head of § "Install" (Amendment 9(e))
    — `gh repo clone opensoft/workBenches && cd workBenches && ./setup.sh`,
    then `pclaude run <profile> --lane <repo>-<n>` — with its two
    preconditions named, `gh auth login` and `~/.local/bin` on `PATH`, and the
    by-hand pair for a host that has this toolset without workBenches. Brett
    Heap's direction of 2026-09-12, "we need to also keep that clean so there
    is the least choices possible to not confuse the user", is the measure
    that section is written to, and a chain a person cannot find is the same
    as no chain.

    and the rewrite of § "Install" itself — FOUR files became NINE and four
    artifacts became TWELVE, since `--install` now also places the
    `/lane-swap` skill in the shared skills directory and in `~/.claude`, and
    merges one `SessionStart` entry into `~/.claude/settings.json`. The
    all-or-nothing rule is the thing being restated, not decorated: the merge
    is computed with the nine files in hand before any is placed, so a
    settings file it cannot understand costs a whole install rather than half
    of one. Three environment variables join the table for the same reason
    they exist — `$AGENT_PROTOCOL_ROOT`, `$CLAUDE_PROFILES_HOME`,
    `$PROJECTS_DIR`.

    And the retired invariant, in the same release and named here because it
    is a DELETION that cost lines rather than saved them: "the only thing in
    this toolset that writes a file outside a repository" is now two things
    writing one file, `resume --workspace` and `wip init`, both only on a
    machine that has none (Amendment 9(c) step 9, act 3 obligation 3).

    353 -> 358 on 2026-09-13, for A9 Addendum 4's R-A9-12 and R-A9-14, ratified
    the same day on the adversarial review of act 3's PR. Five lines, all in
    § "Install", and every one of them behaviour a person MEETS rather than
    prose about it: that `--install` refuses a target that is not a regular
    file, naming each one and the `rm` that clears it, because `cp` follows a
    symlink and the thing on the other end of the two this estate actually has
    is the workspace checkout every lane writes — the review measured
    `9 of 9 placed` and exit 0 while the two commands stayed uninstalled and
    `brett-wip`'s worktree went dirty. The other two words are corrections
    rather than additions: the conflict arm keys on `session-start` and not on
    `lanes-edit.sh` (R-A9-14), and the merge WRITES the file back at mode 600
    where this said it preserved a mode it in fact sets.

    256 AND 358 MEET AT 363, the same merge and the same arithmetic: `main`'s
    5 lines for a branch gone from origin and a role with no place, this
    branch's 107 for the install story Amendment 9 rewrote, both from 251, and
    363 in the file that merged.

    363 AND 372 MEET AT 382, and that is TWO raises read back in one place
    rather than a number nobody can reconstruct. Amendment 11's branch raised
    its own cap twice from the 353 it inherited — 372 for ratified decisions 6
    and 7 (two new words on PATH, `restart` and `lanes`, and the
    `$LANES_WORKSTATION` row decision 8(d) makes load-bearing) and 382 for the
    round that followed — while `main` went 353 -> 358 -> 363 for A9 Addendum
    4. Merging `main` at `d4b5710` brings both sets of lines into one file, and
    the cap is the branch's own 382 because it is the higher of the two and the
    merged README measures 382 exactly. The cap moves with the TOOLSET and
    never with prose, which is why the four lines A11 Addendum 4 ruling 9 adds
    — `--install`'s command-file list, and `commands/swap.md` in it — fit
    inside it rather than raising it again.

    382 -> 389 on 2026-09-13, for TWO rules, and the second is a correction.

    The first is the SETTLED DEFAULT of clause (j)'s listing
    (Brett Heap, 2026-09-13T20:38:11Z, verbatim "Narrow inside a checkout
    (Recommended)"). Five lines, and every one of them is behaviour a person
    MEETS: the code block said `lanes  # every lane on this workstation`, which
    was the pre-settlement default and is now wrong twice over - a bare `lanes`
    inside a checkout lists THAT REPOSITORY's lanes and ends with the next free
    position and the `lane-start <repo> <n>` that takes it, and outside one it
    lists every lane the estate knows rather than one workstation's. A reader
    who types the word from a checkout and is told the listing is broken,
    because the document promised them every lane, is the cost of leaving it.
    The second line of the block is `lanes --all`, which is the sentence's
    other half and the thing to type when the narrowing is not what you meant.

    The second is the COMMAND FILE the install paragraph never named. A11
    Addendum 4 ruling 9 gave `--install` `commands/swap.md` at the same pair of
    paths a skill takes, and the count below that paragraph was raised to
    eighteen - but the paragraph itself still said "five things that are not
    files in that directory" and listed four skill copies and the hook. Two
    lines name the command file and its two destinations, which is the half of
    the install contract a person cannot verify from the count alone: they can
    count to eighteen and still not know where `/swap` lands.
    270 AND 363 MEET AT 377, the same merge and the same arithmetic: this
    branch's 14 lines for the computed path, its three sources and the states
    that get no move, and `main`'s 107 for the install story Amendment 9
    rewrote, both from 256, and 377 in the file that merged.

    389 AND 377 MEET AT 403, the same merge and the same arithmetic, and both
    halves of it are above: this branch's 26 lines from 363 - 372 for ratified
    decisions 6 and 7, 382 for the round after them, 389 for the settled
    narrowing and the command file - and `main`'s 14 for the computed worktree
    path (#27, `7efc850`), both from 363, and 403 in the file that merged.
    Neither dated entry is dropped, because a cap is only worth having while
    the reason for every line of it can still be read back.
    """
    lines = (REPO / "README.md").read_text().splitlines()
    assert len(lines) <= 403, f"README.md is {len(lines)} lines; the cap is 403"


#: A host-absolute path baked into a committed file (the estate's Rule 1):
#: it names one machine, one user, or one session, and silently breaks the
#: moment the repository moves to a different machine or a different user's
#: checkout - which is exactly what openRepoShape #61 found in one of its own
#: tests, a scratchpad path from one session that no other machine could ever
#: match.
#:
#: Each alternative requires a REAL-LOOKING segment rather than matching on
#: the word alone, checked against what this repository's tracked text
#: actually carries today:
#:   - requiring the segment to contain no whitespace excludes a Windows
#:     example that illustrates a SPACE in a username to make a quoting point;
#:     this repository has none today and the exclusion costs nothing.
#:   - .github/workflows/tests.yml would otherwise be flagged for the
#:     GitHub-hosted Windows runner's own fixed account - a shared,
#:     nobody's-machine-in-particular login. THE FILE IS SCANNED LIKE EVERY
#:     OTHER: it is that ACCOUNT that is exempted, by the `(?!runneradmin\\)`
#:     lookahead in the pattern below, so a real user's path in that same
#:     workflow is still a finding.
#:   - This definition would otherwise flag ITSELF: the Claude-scratchpad
#:     tmp-directory prefix this guard exists to catch is therefore spelled
#:     as two concatenated pieces, not written out contiguously.
_CLAUDE_TMP_PREFIX = "/tmp/" + "claude-"
HOST_ABSOLUTE_PATH = re.compile(
    r"/home/[a-z][a-z0-9_-]*/"
    "|" + re.escape(_CLAUDE_TMP_PREFIX) +
    r"|/Users/[A-Za-z][A-Za-z0-9_-]*/"
    r"|C:\\Users\\(?!runneradmin\\)[^\s\\]+\\"
)


def _dispatcher_arms(text: str) -> list[str]:
    """Every subcommand the main dispatcher has an arm for, in file order.

    The dispatcher is the LAST `case "$cmd" in` in the file — the two before it
    are the pre-flight guards (the dirty-checkout capture and Amendment 11's
    container refusal), which name a subset deliberately.
    """
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if l.strip() == 'case "$cmd" in']
    assert starts, "lanes-edit.sh has no `case \"$cmd\" in` at all"
    out: list[str] = []
    for line in lines[starts[-1] + 1:]:
        # `startswith` AND NOT `line.strip() == "esac"`, and it is deliberate:
        # the dispatcher's arms contain NESTED `case` statements whose `esac` is
        # indented, so a whitespace-insensitive test ends the scan at the first
        # of those. Measured: with `line.strip() == "esac"` this parser finds
        # TWO arms instead of thirty and the test below fails on its own guard
        # ("the parser has drifted"). The unindented `esac` is the dispatcher's
        # own, which is exactly the property being relied on.
        if line.startswith("esac"):
            break
        m = re.match(r"^  ([a-z][a-z0-9|-]*)\)", line)
        if m:
            out.extend(m.group(1).split("|"))
    return out


def test_the_unknown_subcommand_refusal_names_every_subcommand_there_is():
    """`2` FROM THE `*)` ARM IS HOW A CALLER DETECTS AN OLD HELPER, and the
    list it prints is the only place a person learns what this file answers to.

    `fetch-age` was missing from it (F-X16): the arm existed, the read worked,
    and the refusal for a typo listed twenty-nine of the thirty verbs — so a
    person who mistyped `fetch-age` was told, by omission, that it does not
    exist. The list is DERIVED here from the dispatcher's own arms rather than
    restated, because a restated list is the thing that drifted.
    """
    text = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    arms = _dispatcher_arms(text)
    assert len(arms) > 25, f"only {len(arms)} arms parsed — the parser has drifted"
    m = re.search(r"unknown subcommand '\$cmd' \(([^)]*)\)", text)
    assert m, "no unknown-subcommand refusal found in lanes-edit.sh"
    listed = m.group(1).split("|")
    assert sorted(set(listed)) == sorted(set(arms)), (
        "the unknown-subcommand refusal and the dispatcher disagree:\n"
        f"  in the arms but not the list: {sorted(set(arms) - set(listed))}\n"
        f"  in the list but not the arms: {sorted(set(listed) - set(arms))}")
    assert len(listed) == len(set(listed)), "the refusal lists a verb twice"


def test_the_exit_code_table_carries_every_code_the_file_exits_with():
    """*"EXIT CODES — every subcommand, one table, no two meanings on one
    number"* is a claim the table makes about itself (`lanes-edit.sh:160`).

    **64 was in no table at all** while twenty-one `die`s used it and the
    contract gave it to every read Amendment 11 added (F-X16). A table that
    says it is complete and is not is worse than no table, because it is the
    thing a reader checks the code against.
    """
    text = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    start = text.index("# EXIT CODES — every subcommand, one table")
    # The table ends where the next header does. `\n#\n` is NOT the boundary:
    # a row long enough to need a blank comment line inside it would truncate
    # the table and the test would pass by reading less of it.
    end = text.index("# --no-sweep", start)
    table = text[start:end]
    used = set()
    for m in re.finditer(r'\bdie "(?:[^"\\]|\\.)*" (\d+)', text, re.S):
        used.add(m.group(1))
    for m in re.finditer(r"^\s*(?:return|exit) (\d+)\b", text, re.M):
        used.add(m.group(1))
    documented = set(re.findall(r"^#\s+(\d+)\s{2}", table, re.M))
    missing = sorted(int(c) for c in used - documented - {"0"})
    assert not missing, (
        f"these exit codes are used and are in no row of the table: {missing}\n"
        f"the table documents {sorted(int(c) for c in documented)}")
    assert "64" in documented, "64 is the code every Amendment 11 read uses"


#: ADOPTION ACT 0, AND THE ONE SHA THAT IS IT. `opensoft/brett-wip#5` merged
#: 2026-09-13T19:14:37Z, SQUASHED — so the PR's pre-merge head is not an
#: ancestor of `origin/main` and names code that never landed, while the merge
#: commit does and is (F-X18, A11 Addendum 4 ruling 13).
ACT0_MERGED = "3719d97"
ACT0_DRAFT_HEAD = "95e7a4c"
#: `opensoft/brett-wip#5` @`<sha>` — the citation shape this repository uses.
ACT0_CITATION = re.compile(
    r"`?opensoft/brett-wip#5`?\s*@`([0-9a-f]{7,40})`")


def test_adoption_act_zero_is_cited_by_the_sha_that_landed():
    """A SHA IN A COMMENT IS A CLAIM ABOUT HISTORY, and this one was false in
    two files: `lane-start:1027` and `lanes-edit.sh:4794` both cited act 0 —
    the register veto this branch builds its second layer beside — as
    `95e7a4c`, which is `#5`'s DRAFT head. Measured: `git merge-base
    --is-ancestor 95e7a4c origin/main` is false and the same test on
    `3719d97` is true.

    The draft head may still be NAMED, and both files now name it — as the
    thing that did not land. What is checked here is the citation form
    `opensoft/brett-wip#5 @<sha>`, which asserts "this is act 0".
    """
    tracked = subprocess.run(["git", "ls-files"], cwd=str(REPO),
                             capture_output=True, text=True,
                             check=True).stdout.splitlines()
    offenders = {}
    cited = 0
    for rel in tracked:
        path = REPO / rel
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        # THE CITATION WRAPS, AND A LINE-BY-LINE MATCH WOULD MISS THE ONE THAT
        # DID. `lane-start` writes it as "(`opensoft/brett-wip#5`\n#     @`…`)",
        # so the comment marker of the continuation line sits between the two
        # halves. Joined here before matching — measured: without this the
        # regex found only `lanes-edit.sh`'s one-line citation and the mutation
        # of `lane-start`'s survived.
        flat = re.sub(r"\n[ \t]*#?[ \t]*", " ", text)
        for sha in ACT0_CITATION.findall(flat):
            cited += 1
            if not (sha.startswith(ACT0_MERGED) or ACT0_MERGED.startswith(sha)):
                offenders.setdefault(rel, []).append(sha)
    assert cited, (
        "no file cites adoption act 0 at all — this test has stopped testing "
        "anything, or the citation form has changed")
    assert not offenders, (
        f"act 0 is cited by a sha that is not the merge commit {ACT0_MERGED}: "
        f"{offenders}. `{ACT0_DRAFT_HEAD}` is the draft head and is not an "
        "ancestor of origin/main.")


#: EVERY SURFACE THAT PRINTS SOMETHING ABOUT A LIVE FORK. Six of them: `who`,
#: the SessionStart hook, `live-holder`, `lanes`, `restart` and the `/restart`
#: skill — and `lane-end`, which A11 Addendum 4 ruling 8 makes the DOOR and
#: which must therefore hold to the same rule as the surfaces that print it.
FORK_SURFACES = ("lanes-edit.sh", "lanes", "restart", "skills/restart/SKILL.md",
                 "lane-end")
#: A line that offers an act for a fork says `FORK` or `fork(s)` and an
#: imperative beside it. Matched on the two spellings the surfaces use.
FORK_ACT_LINE = re.compile(r"^.*(?:live FORK|live fork\(s\)).*$", re.M)


#: The two halves of the `/lane-swap` skill that must spell the launch the same
#: way: the `restart_cmd=` the skill EXECUTES into its printed line, and the
#: prose three paragraphs below that explains it.
SWAP_SKILL = "skills/lane-swap/SKILL.md"


def test_the_swap_skill_snippet_and_its_prose_spell_the_same_command():
    """AMENDMENT 11 CLAUSE (a), EDIT 5 OF SIX: *"Every printed restart command
    becomes the short form … Amendment 8(a) step 5's prescribed
    `pclaude run <profile>` becomes that short form wherever it is printed."*

    At `dae38be` this file took the snippet half of that edit and left the
    prose half — `restart_cmd="pclaude ${CLAUDE_PROFILE_NAME:-<profile>}"` with
    three paragraphs below it still saying `pclaude run <profile>`. That is not
    a wording nit: `opensoft/workBenches#74`'s
    `devcontainer.test/test-claude-profile-skill-install.sh` EXECUTES step 5's
    branch rather than grepping it, and reported
    `FAIL: RV-S2: normal-path restart_cmd='pclaude work', expected the
    unqualified command` against the vendored bytes
    (openRepoTools#26-5656319349). The executed snippet and the paragraph
    explaining it produced different commands.

    So: no `restart_cmd=` may spell the verb, and every `pclaude run` left in
    the file must be on a line that says WHY the long form is being named — it
    is quoted twice, as the sentence clause (a) edits and as the argv the short
    form builds — rather than printed as the act.
    """
    text = (REPO / SWAP_SKILL).read_text(encoding="utf-8")
    bad_cmd = [l.strip() for l in text.splitlines()
               if "restart_cmd=" in l and "pclaude run" in l]
    assert not bad_cmd, (
        "clause (a) makes every PRINTED restart command the short form, and "
        f"these assignments spell the verb:\n{bad_cmd}")
    assigns = [l for l in text.splitlines() if l.strip().startswith("restart_cmd=")]
    assert len(assigns) >= 2, (
        f"{SWAP_SKILL} has {len(assigns)} `restart_cmd=` assignments; step 5 "
        "has two branches (with --lane and without) and this test is stale")
    unexplained = [l.strip()[:120] for l in text.splitlines()
                   if "pclaude run" in l
                   and "short form" not in l and "SAME argv" not in l]
    assert not unexplained, (
        "these lines print the LONG form without naming it as the one clause "
        f"(a) supersedes, so the prose no longer agrees with the snippet:\n"
        f"{unexplained}")
    # AND `--lane` IS LEADING, on both halves. Measured on the live launcher
    # (`claude-profile`): `--lane` is read only BEFORE the action or the
    # profile — *"the first token that is not one of them ends this loop"* — so
    # a `--lane` after the profile is handed to Claude and the lane is never
    # taken.
    after = [l.strip()[:120] for l in text.splitlines()
             if re.search(r"pclaude (?:run )?[^`\s]*<?profile>? --lane", l)
             and "never after" not in l and "handed to Claude" not in l]
    assert not after, (
        "`--lane` is a LEADING option of the launcher; after the profile it is "
        f"passed to Claude and the lane is never taken:\n{after}")


def test_every_fork_surface_prints_the_one_act():
    """CLAUSE (k) RULE (e), and it names the act: *"both print the one act:
    **retire it**, under Amendment 6(d) … **Neither kills a process** … and
    `lane-end`'s `--retire` is the door."*

    At `dae38be` the estate printed THREE other things and not that one
    (F-X8): `restart:214` printed `lanes-edit.sh forks <lane>`, which is a
    READ that retires nothing; `lanes:173` printed *"Name them"*; and `who`,
    `live-holder`, the SessionStart hook and the `/restart` skill printed
    `kill <pid>` — the one act the ruling refuses by name.

    Derived rather than restated: every line in every surface that speaks of a
    live fork must name `--retire`, and none may offer a `kill`. The IDLE
    HOLDERS of a lane are a different population — earlier sessions of the lane
    ITSELF, Amendment 6(d)'s orphans, which `lane-end --retire` refuses because
    they are not forks — and their `kill` lines are deliberately untouched, so
    this matches fork lines only.
    """
    offenders = {}
    for rel in FORK_SURFACES:
        text = (REPO / rel).read_text(encoding="utf-8")
        for line in FORK_ACT_LINE.findall(text):
            # `\bkill\b` AND NOT `"kill" in line`: the word `skill` contains it,
            # and `skills/restart/SKILL.md` is one of the files being walked.
            if re.search(r"\bkill\b", line) and "--retire" not in line:
                offenders.setdefault(rel, []).append(line.strip()[:160])
    assert not offenders, (
        "these fork lines still offer a `kill` and not clause (k) rule (e)'s "
        f"one act:\n{offenders}")
    # …and the act is actually printed somewhere in each of the four.
    missing = [rel for rel in FORK_SURFACES
               if "--retire" not in (REPO / rel).read_text(encoding="utf-8")]
    assert not missing, f"these surfaces name no `--retire` act at all: {missing}"


def test_the_manual_offers_the_fork_act_and_not_a_kill():
    """THE SAME RULE AS THE TEST ABOVE, READ BY PARAGRAPH BECAUSE PROSE WRAPS.

    `test_every_fork_surface_prints_the_one_act` matches LINES, and a line is
    the right unit in a bash file where each message is one string. It is the
    wrong unit in a manual: `README-lanes.md`'s fork paragraph said *"none of
    them kills anything - retiring is `kill <pid>`, typed by a person"*, and
    the two halves of that contradiction sat on two different lines, so no
    line-matching rule could see it and the document went on offering the one
    act clause (k) rule (e) refuses BY NAME while the five surfaces beside it
    had all been corrected (F-X8).

    So the manual is read as PARAGRAPHS: any paragraph that speaks of a fork
    and offers a `kill` must name `--retire`. The idle holders of a lane are a
    different population - Amendment 6(d)'s orphans, which `lane-end --retire`
    refuses because they are not forks - and their `kill` lines are untouched
    here for the same reason the test above leaves them alone.
    """
    text = (REPO / "docs/README-lanes.md").read_text(encoding="utf-8")
    offenders = [" ".join(para.split())[:200]
                 for para in re.split(r"\n\s*\n", text)
                 if re.search(r"\bfork\b", para, re.I)
                 and re.search(r"\bkill\b", para)
                 and "--retire" not in para]
    assert not offenders, (
        "these paragraphs of the manual offer a `kill` for a fork and never "
        f"clause (k) rule (e)'s one act:\n  " + "\n  ".join(offenders))
    assert "lane-end <lane> --retire <pid|uuid>" in text, (
        "the manual never spells the one fork act in full")


def test_no_committed_file_names_a_host_absolute_path():
    """openRepoShape #61: a suite stayed green on every machine but the one a
    fixed path was written on, because the ONE test that read it SKIPPED when
    it was absent. Nothing checked the path itself for being the kind of thing
    that should never have been committed. This is that check.

    Every file `git ls-files` tracks, decoded as UTF-8 - a file that fails to
    decode is skipped rather than failed, because this test is about paths
    written in text, not about what counts as text. The gitlink at
    `upstream/openRepoShape` is listed as a path and is not a file, so it is
    skipped too: what the standard's own tree carries is the standard's own
    suite to police.
    """
    tracked = subprocess.run(["git", "ls-files"], cwd=str(REPO),
                             capture_output=True, text=True,
                             check=True).stdout.splitlines()
    offenders = {}
    for rel in tracked:
        path = REPO / rel
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        hits = HOST_ABSOLUTE_PATH.findall(text)
        if hits:
            offenders[rel] = hits
    assert not offenders, (
        f"committed file(s) name a host-absolute path: {offenders}")


def test_the_root_carries_the_line_ending_rule():
    """`* text=auto eol=lf`, for openRepoShape's reason retold for this
    repository: `openRepoTools --install` compares the bytes it is about to
    place against the bytes already there with `cmp`, and its own tests compare
    an installed copy to this checkout's file byte for byte. Git for Windows'
    installer default is `core.autocrlf=true`; a checkout made under it turns
    every `\\n` in these four bash files into `\\r\\n`, and the comparison is
    then about line endings rather than about content. The rule normalises text
    to LF in the object store on check-in and checks it out as LF on every
    platform, whatever `core.autocrlf` says — so nobody has to be told a git
    setting before cloning, and nobody who was never told is punished for it.
    """
    text = (REPO / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in text


def test_every_shipped_bash_file_is_tracked_with_lf():
    """The rule above, checked against the object store rather than the
    intention. `git ls-files --eol` reports the index and working-tree endings;
    a `crlf` in the index would mean the rule was added after the file was
    committed under `autocrlf=true`, which is the state it exists to prevent.
    """
    proc = subprocess.run(["git", "ls-files", "--eol", "--", *ALL_BASH],
                          cwd=str(REPO), capture_output=True, text=True,
                          check=True)
    for row in proc.stdout.splitlines():
        assert "i/lf" in row, f"not LF in the index:\n    {row}"


def test_the_python_files_compile():
    """The suite is the only Python here, and a file that does not parse is a
    file that fails as a collection ERROR rather than as a test — which reads
    as the suite being broken instead of as one file being wrong.

    `compile()` rather than `py_compile`: nothing is written anywhere, so this
    runs in a read-only checkout and leaves no `__pycache__` behind.
    """
    for path in sorted((REPO / "tests").glob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


# --- the macOS job RUNS this bash, it does not only parse it (R-A9-11) ------

#: Which options of which utility take a SEPARATE argument. Everything after
#: the first token that is neither an option nor an option's argument is an
#: OPERAND, and an operand is where BSD's `getopt` stops looking for options.
_OPTIONS_WITH_ARGUMENTS = {
    "sed": {"-e", "-f", "-i", "-l"},
    "grep": {"-e", "-f", "-m", "-A", "-B", "-C", "--include", "--exclude"},
    "awk": {"-v", "-f"},
}


def _shell_tokens(text: str) -> list[str]:
    """Split one shell command into tokens, keeping a quoted run together.

    Deliberately small: it expands nothing and does not care what a token
    MEANS. All it has to answer is "is this token exactly `--`, and did an
    operand come before it".
    """
    tokens: list[str] = []
    current: list[str] = []
    quote, started = "", False
    for ch in text:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote, started = ch, True
            current.append(ch)
        elif ch.isspace():
            if started:
                tokens.append("".join(current))
            current, started = [], False
        else:
            started = True
            current.append(ch)
    if started:
        tokens.append("".join(current))
    return tokens


def _end_of_options_after_an_operand(text: str) -> list[str]:
    """Every `sed`/`grep`/`awk` call in `text` that passes `--` too late.

    THE BUG THIS IS ABOUT. GNU's `getopt` PERMUTES: it finds options wherever
    they appear, so `sed -n 'script' -- "$file"` reads `--` as end-of-options
    and `$file` as the one file. BSD's stops at the first operand — the script
    — so `--` is left as a FILENAME and macOS answers
    `sed: --: No such file or directory`, exit 1. The same goes for
    `grep 'pattern' -- "$f"` and `awk 'program' -- "$f"`.

    `sed -n -e 'script' "$file"` has no operand before the file list at all,
    which is why that is the shape this repository uses. The protection `--`
    was there for — a filename that begins with `-` — is kept by every call
    that still spells it before the operand, which is what the file list of
    `rm -f -- "$x"` and `grep -v -x -F -- "$pattern"` are.
    """
    bad = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for piece in re.split(r"[|;&()]|\$\(|`", line):
            tokens = _shell_tokens(piece)
            for start, token in enumerate(tokens):
                tool = token.rsplit("/", 1)[-1]
                if tool not in _OPTIONS_WITH_ARGUMENTS:
                    continue
                takes_argument = _OPTIONS_WITH_ARGUMENTS[tool]
                seen_operand = False
                index = start + 1
                while index < len(tokens):
                    argument = tokens[index]
                    if argument == "--":
                        if seen_operand:
                            bad.append(f"{tool}: {line.strip()}")
                        break
                    if not seen_operand and argument.startswith("-") and argument != "-":
                        if argument in takes_argument:
                            index += 1
                    else:
                        seen_operand = True
                    index += 1
                break
    return bad


@pytest.mark.parametrize("name", ALL_BASH)
def test_no_shipped_bash_ends_its_options_after_an_operand(name):
    """THE macOS JOB IS A RUN GATE AND NOT ONLY A PARSE GATE (A9 Addendum 4,
    R-A9-11, ratified 2026-09-13 after F4 of the #24 review).

    Act 3's obligation 4 bought `/bin/bash -n` on every bash file this
    repository ships, and obligation 6 made the same job RUN 196 KB of bash
    that had only ever run on Linux. It went 507 passed / 447 failed, and the
    first of the two causes named in that job's own log was seventeen calls of
    this one shape. `bash -n` cannot see it: the grammar is fine, and the
    utility is not bash.

    So it is held here, where it costs nothing and runs in EVERY job —
    `tests-windows` included, which skips every bash claim and can still read a
    file.
    """
    text = (REPO / name).read_text(encoding="utf-8")
    bad = _end_of_options_after_an_operand(text)
    assert not bad, (
        f"{name} passes `--` AFTER an operand, which BSD's `getopt` reads as a "
        f"FILENAME (macOS: `sed: --: No such file or directory`). Put the "
        f"script behind `-e` instead:\n  " + "\n  ".join(bad))


@pytest.mark.parametrize("name", ALL_BASH)
def test_no_shipped_bash_leaves_a_variable_name_to_bash_3_2s_locale(name):
    """`bash -n` PARSES THIS AND macOS DIES ON IT (A9 Addendum 4, R-A9-11).

    Bash decides where a variable NAME ends with `isalnum()`, which is
    LOCALE-DEPENDENT. Under the `en_US.UTF-8` the macOS runner sets, bash 3.2
    on Darwin reads the bytes of `\u2026`, `\u2014` and `\u00b7` as name characters, so
    `"\u2026$excerpt\u2026"` is a reference to a variable called `excerpt\u2026` \u2014 unset,
    and under `set -u` the script DIES. It cost `lane-end` the whole refusal
    branch its `--force` message lives in: exit 0 where the estate expects
    exit 2, and `lane-end: line 573: excerpt\u2026: unbound variable` on stderr.

    This estate writes every message with those three characters in it, so the
    rule is held for all of them rather than for the one that was found.
    """
    text = (REPO / name).read_text(encoding="utf-8")
    bad = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for hit in re.finditer(r"\$[A-Za-z_][A-Za-z0-9_]*", line):
            rest = line[hit.end():hit.end() + 1]
            if rest and ord(rest) > 127:
                bad.append(f"{number}: {line.strip()}")
                break
    assert not bad, (
        f"{name} ends an UNBRACED `$name` against a non-ASCII character. Bash "
        f"3.2 on macOS reads that character as part of the name and the "
        f"lookup fails under `set -u`. Write `${{name}}`:\n  "
        + "\n  ".join(bad))


@pytest.mark.parametrize("name", ALL_BASH)
def test_no_shipped_bash_quotes_the_replacement_half_of_a_substitution(name):
    """BASH 3.2 KEEPS THOSE QUOTES AS CHARACTERS (A9 Addendum 4, R-A9-11).

    In `${var/pattern/replacement}`, bash 4.3 and later read quotes as "this
    half is a literal, not a pattern". Bash 3.2 removes them from the PATTERN
    half and KEEPS THEM IN THE REPLACEMENT, so `${row/"$old"/"$new"}` wrote
    `"<new>"` \u2014 with the quote marks \u2014 into the register on macOS, and nothing
    went red for it: the write succeeded, the commit landed, the row was
    quietly wrong. `lane-end --retire` produced `| "RETIRED 2026-09-13T\u2026" \u00b7 \u2026`
    where every reader of that column expects `| RETIRED 2026-\u2026`.

    Take the replacement out of the pattern machinery instead \u2014 `%%` for the
    prefix and `#` for the tail, then concatenate.
    """
    text = (REPO / name).read_text(encoding="utf-8")
    bad = [line.strip() for line in text.splitlines()
           if not line.lstrip().startswith("#")
           and re.search(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]*\])?/[^}]*/[^}]*\"",
                         line)]
    assert not bad, (
        f"{name} quotes the replacement half of a `${{var/pat/rep}}`; bash 3.2 "
        f"writes those quote marks out as text. Build the string from "
        f"`${{var%%\"$pat\"*}}` and `${{var#*\"$pat\"}}` instead:\n  "
        + "\n  ".join(bad))


@pytest.mark.parametrize("name", ALL_BASH)
def test_no_shipped_bash_opens_a_case_inside_a_command_substitution(name):
    """A `)` THAT CLOSES A `case` PATTERN CLOSES THE SUBSTITUTION TOO (A9
    Addendum 4, R-A9-11).

    Bash 3.2 - the bash the macOS job parses these files with - reads the `)`
    that ends a case PATTERN as the one that ends the enclosing `$( )`. So
    `$(case "$x" in a) printf yes ;; *) printf no ;; esac)` is a SYNTAX ERROR
    there and nowhere else, and what the caller gets back is a fragment of the
    script's own source. The job answered `command substitution: line 3284:
    syntax error near unexpected token 'newline'` at `dcf1027`; two more of the
    shape were written into this amendment's own suite afterwards, and at
    `708395e` `tests-macos` compared ` printf 'resumed Y' ;; *) printf 'did
    not' ;; esac)` against `did not` - twice, and green on every GNU runner.

    A `bash -n` ON A GNU RUNNER PARSES IT, which is why this is a text rule
    rather than a parse gate: all eleven files already pass `bash -n` in CI,
    and the macOS job is the only place the defect exists. The fix is one line
    each time - hoist the `case` above the assertion and read the variable it
    sets - so the rule is held for every bash file this repository ships
    rather than for the two that were found.

    Only the same-line form is matched. A `case` inside a multi-line `$(` ...
    `)` is the same defect and wants the same hoist, but a line-level regex is
    what the three rules beside this one are, and a paren-counting scanner that
    misread one quoted `)` would refuse a file for nothing.
    """
    text = (REPO / name).read_text(encoding="utf-8")
    bad = [f"{number}: {line.strip()}"
           for number, line in enumerate(text.splitlines(), 1)
           if not line.lstrip().startswith("#")
           and re.search(r"\$\([^()]*\bcase\b", line)]
    assert not bad, (
        f"{name} opens a `case` inside a `$( )`; bash 3.2 ends the "
        f"substitution at the first pattern's `)` and hands the caller a piece "
        f"of the script's own source. Hoist the `case` onto its own line and "
        f"read the variable it sets:\n  " + "\n  ".join(bad))


@pytest.mark.parametrize("name", ALL_BASH)
def test_no_shipped_bash_reaches_for_gnu_only_utilities_unaccompanied(name):
    """THE SECOND CAUSE IN THAT JOB'S LOG, AND THE FOUR BESIDE IT.

    `date -d`, `stat -c`, `xargs -r`, `sort -z`, `sha256sum` and BRE `\\|` are
    GNU; macOS answers the first with `illegal option -- d`, does not ship
    `sha256sum` on a stock install, and reads `\\|` as two literal characters —
    which is the worst of the five, because it is not an error at all, it is a
    pattern that quietly matches nothing.

    None of them is forbidden. GNU is what every lane workstation runs, and
    this is not a rule about writing to the lowest common denominator: it is a
    rule that the BSD spelling must be within reach of the GNU one, beside the
    thing it falls back from rather than in a comment somewhere else.
    """
    text = (REPO / name).read_text(encoding="utf-8")
    lines = [line for line in text.splitlines()
             if not line.lstrip().startswith("#")]
    # BSD spells reading a stamp `date -u -j -f <format> <stamp>` and spells
    # arithmetic `date -u -v-5H`; either answers a `date -d`, and a `-d` with
    # neither within ten lines is a GNU-only call.
    for index, line in enumerate(lines):
        if not re.search(r"\bdate\b[^\n|]*\s-d\b", line):
            continue
        window = "\n".join(lines[max(0, index - 10):index + 7])
        assert re.search(r"\bdate\b[^\n|]*\s-j\b", window) or "-v" in window, (
            f"{name} reads a stamp with GNU `date -d` and carries no BSD "
            f"spelling within ten lines of it (`date -u -j -f <format>` reads "
            f"one, `date -u -v-5H` is the arithmetic):\n  {line.strip()}")
    for line in lines:
        if re.search(r"\bstat\b[^\n|]*\s-c\b", line):
            assert re.search(r"\bstat\b[^\n|]*\s-f\b", line), (
                f"{name} uses GNU `stat -c` with no `stat -f` beside it on the "
                f"same line:\n  {line.strip()}")
        assert not re.search(r"\bcmp\b[^\n|]*\s-n\b", line), (
            f"{name} passes GNU `cmp -n <limit>`; BSD `cmp`'s trailing numbers "
            f"are SKIPS, not a limit, so macOS answers `illegal option -- n` "
            f"and exits 2 \u2014 which turns a PROOF into a refusal of a write that "
            f"was correct. Build what the file must now be and compare that: "
            f"`{{ cat -- old; printf ...; }} | cmp -s -- file -`. Not "
            f"`head -c <n>` either: BSD `head` rejects a count of 0:"
            f"\n  {line.strip()}")
        assert not re.search(r"\bwc\b\s+-[lcwm]", line) or "tr -d ' '" in line, (
            f"{name} reads a count out of `wc` and does not strip the spaces "
            f"BSD `wc` pads it with. `wc -l < f` answers `\"       5\"` on macOS "
            f"and `\"5\"` under GNU, so the moment that value meets anything "
            f"unpadded \u2014 an arithmetic `$((n + 1))`, a literal, a count from "
            f"anywhere else \u2014 a `[ x = y ]` between them is FALSE on one "
            f"platform and true on the other. That is exactly how "
            f"`append_text_line` came to refuse every append it had already "
            f"made on the macOS job, and to say `append changed line count by "
            f"1` while doing it. Spell it `| tr -d ' '`, as `park:564` and "
            f"`status:746` always have:\n  {line.strip()}")
        assert not re.search(r"\bxargs\b[^\n|]*\s-r\b", line), (
            f"{name} passes GNU `xargs -r`, which BSD `xargs` does not "
            f"take:\n  {line.strip()}")
        assert not re.search(r"\bsort\b[^\n|]*\s-z\b", line), (
            f"{name} passes GNU `sort -z`; sorting the lines a digest prints "
            f"is as deterministic and needs no NUL:\n  {line.strip()}")
        assert not (re.search(r"\b(sed|grep)\b", line) and "\\|" in line), (
            f"{name} spells alternation `\\|`, which is a GNU extension to "
            f"BRE: BSD `grep` and `sed` match it literally and report no "
            f"error. Use a second `-e`, or `-E`:\n  {line.strip()}")
    if "sha256sum" in "\n".join(lines):
        assert "shasum" in "\n".join(lines), (
            f"{name} names `sha256sum`, which a stock macOS does not ship, and "
            f"never names `shasum -a 256`")



def test_the_rule_6_register_scan_takes_its_alias_table_from_the_environment():
    """`awk -v` CARRIES ONE LINE (A9 Addendum 4, R-A9-11, round 5).

    POSIX says a `-v assignment` value is processed as if it were a STRING
    LITERAL, and a string literal cannot span lines. macOS's awk \u2014 one-true-awk,
    `awk version 20200816` on the runner \u2014 enforces exactly that and refuses one
    outright: `awk: newline in string \u2026 at source line 1`, exit 2, nothing on
    stdout. gawk and mawk accept it without a word, which is what made this the
    last macOS group standing after four rounds and the only one no Linux run
    of the suite could see.

    `who_landing` handed `awk -v aliases=` the whole `repos.tsv` alias table,
    one `<alias>\\037<owner/repo>` per line. So on that platform the REGISTER
    half of `who --landing` produced nothing at all and every open LANDING in
    the estate read as `none open` \u2014 fourteen red assertions on that job, and
    off CI a workstation running macOS that cannot see the estate's merge holds
    while reporting, in words, that there are none.

    Pinned rather than held as a shape. The shape rule \u2014 "a shell FUNCTION's
    output is a stream, so it does not go into a `-v`" \u2014 was written first and
    is wrong about this file: `lc`, `short_ws` and `object_slug` are functions
    too, and each transforms ONE value, so it reddened three call sites that
    are correct. A hygiene test with three carve-outs teaches the wrong rule.
    The general claim is held where it can be held honestly \u2014
    `tests/test_lane_helpers.sh` runs `who --landing` under a proxy that
    refuses a many-line `-v` exactly as that awk does \u2014 and this pins the one
    line that proxy exists for, in a test that also runs on Windows.
    """
    text = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    assert 'na = split(ENVIRON["LANES_RULE6_ALIASES"], ar, "\\n")' in text, (
        "RULE6_AWK must read the alias table out of the environment; "
        "`ENVIRON` is POSIX awk and takes a value with newlines in it")
    assert ('wd_rows="$(register_text | LANES_RULE6_ALIASES="$wd_aliases" '
            'awk "$RULE6_AWK")"') in text, (
        "the Rule 6 register scan must put the alias table in the environment "
        "of that one awk, not in a `-v`")
    assert "-v aliases=" not in text, (
        "the alias table is many lines and `awk -v` carries one: macOS's awk "
        "answers `newline in string ... at source line 1` and exits 2, and "
        "`who --landing` then reports every merge hold in the estate as "
        "`none open`")
