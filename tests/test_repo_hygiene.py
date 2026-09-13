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
SHIPPED_BASH = ["openRepoTools", "park", "resume", "status"]

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
    assert 'sed -n \'s/^commit:[[:space:]]*//p\'' in text, (
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
    one somebody calls a failure. The four-file count is held too, because
    the install story is the sentence a first-time reader trusts.
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
    assert "FOUR files" in readme, "README.md does not count the four files"
    assert "4 of 4 placed" in readme, (
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
    """
    lines = (REPO / "AGENTS.md").read_text().splitlines()
    assert len(lines) <= 155, f"AGENTS.md is {len(lines)} lines; the cap is 155"


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
    """
    lines = (REPO / "README.md").read_text().splitlines()
    assert len(lines) <= 251, f"README.md is {len(lines)} lines; the cap is 251"


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
