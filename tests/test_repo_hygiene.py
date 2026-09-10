# SPDX-License-Identifier: Apache-2.0
"""Properties of THIS repository that a fork depends on and nobody re-checks.

Adapted from openRepoShape's `tests/test_repo_hygiene.py` — the rules travel
with the files. NOTHING HERE NEEDS THE SUBMODULE, on purpose: these are facts
about the three bash files and the four documents this repository ships, so
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
#: file a person has on their PATH — the installer and the two estate verbs —
#: so each is held to the same shebang, mode bit and `set -euo pipefail` rule.
#: The macOS job parses these same three with `/bin/bash -n`, one command per
#: file, which is what keeps the bash-3.2 claim true.
SHIPPED_BASH = ["openRepoTools", "park", "resume"]

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


@WINDOWS_SKIP
@pytest.mark.parametrize("name", SHIPPED_BASH)
def test_shipped_bash_parses_under_bash(name):
    """`bash -n` on all three shipped bash files, everywhere there is a bash.

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


def test_the_two_verbs_carry_the_same_estate_resolver_byte_for_byte():
    """THE DUPLICATION IS DELIBERATE AND THE CLAIM HAS TO STAY TRUE.

    `park` and `resume` are each ONE file a person has on PATH, so the estate
    resolver is copied rather than sourced: a shared `orp-estate.sh` would be a
    fourth file for `--install` to place and a broken command the first time
    somebody copied only one of them. A copy that has drifted is two answers to
    "which estate is this", which is the one thing the block exists to prevent.

    ASSERTED HERE AS WELL AS IN `test_park_resume_commands.py`, on purpose.
    That file carries `NEEDS_UPSTREAM` and a `bash` guard, so in a clone made
    without `--recurse-submodules` — or on Windows — its copy of this check
    SKIPS. This invariant is about two files in this repository and needs
    neither the submodule nor a shell, so it also lives where it always runs.
    """
    def block(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        start = text.index("# --- BEGIN shared estate resolver")
        end = text.index("# --- END shared estate resolver")
        return text[start:end]

    park, resume = block(REPO / "park"), block(REPO / "resume")
    assert park == resume, (
        "park and resume have drifted apart in the shared estate resolver")
    assert len(park.splitlines()) > 100, "the marker moved, not the block"


def code_lines(path: Path) -> str:
    """The file with its whole-line comments dropped.

    Every rule below is about what these files DO, and the sentences in them
    that name openRepoShape are about the standard, about a ruling, or about
    where the code came from. Matching on the word alone would make a comment
    into a finding, which teaches the next person to delete the comment.
    """
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def test_the_verbs_name_no_runtime_dependency_on_the_standard():
    """`park` and `resume` depend on the ESTATE, never on openRepoShape.

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
    """
    for name in ("park", "resume"):
        code = code_lines(REPO / name)
        assert "OPENREPOSHAPE" not in code, (
            f"{name} reads an $OPENREPOSHAPE_* variable; the estate commands "
            f"take no environment from the standard")
        assert "raw.githubusercontent.com" not in code, (
            f"{name} names a raw URL; the verbs fetch nothing")
        assert "gh api" not in code, f"{name} calls the API; the verbs fetch nothing"


def test_the_installer_reaches_only_this_repository():
    """The installer fetches from `$OPENREPOTOOLS_REPO` and from nowhere else.

    An `--install` that reached into openRepoShape to complete itself would
    make this repository's installer depend on the standard at run time, which
    is the direction the pin's own header spends a paragraph refusing — and it
    is the mirror of the rule openRepoShape's own `--install` follows by
    printing a POINTER at this repository rather than fetching from it.
    """
    for line in code_lines(REPO / "openRepoTools").splitlines():
        if "gh api" in line or "raw.githubusercontent.com" in line:
            assert "$REPO" in line, (
                f"the installer fetches from a repository that is not "
                f"$OPENREPOTOOLS_REPO:\n    {line.strip()}")


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
    """openRepoShape #91 (RULING 2026-09-10, its #93) SUPERSEDED ruling 3 of
    its #82 for one case: bare `park`, with no `<Name>` and no estate around
    the cwd, PARKS EVERY ESTATE instead of refusing — and `resume` keeps the
    refusal for its own bare form.

    Both halves, in both documents. This is the sentence most likely to go
    stale here, because these two files are the only place the installed
    commands are written down once openRepoShape's own carve removes its
    paragraph, and because the OLD text reads perfectly well — a document
    that says `park` refuses is not obviously broken, it is just wrong, and
    an assistant reading it tells somebody to name an estate the bare form
    does not need.
    """
    for name in ("README.md", "AGENTS.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "PARKS EVERY ESTATE" in text, (
            f"{name} does not say what bare `park` does since #91")
        assert "#91" in text, f"{name} does not cite the ruling"
        assert "in name order" in text, (
            f"{name} does not say the order, which is the whole of what a "
            f"person watching a park-everything run sees")
    assert "keeps that old refusal for its own bare form" in \
        (REPO / "README.md").read_text(encoding="utf-8"), (
        "README.md does not say resume's own bare form still refuses")
    assert "`resume`'s OWN bare form still refuses" in \
        (REPO / "AGENTS.md").read_text(encoding="utf-8"), (
        "AGENTS.md does not say resume's own bare form still refuses")
    park = (REPO / "park").read_text(encoding="utf-8")
    assert "PARKS EVERY ESTATE" in park, (
        "the `park` in this repository predates #91; re-take it from the pin")


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
    """
    lines = (REPO / "AGENTS.md").read_text().splitlines()
    assert len(lines) <= 90, f"AGENTS.md is {len(lines)} lines; the cap is 90"


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
    """
    lines = (REPO / "README.md").read_text().splitlines()
    assert len(lines) <= 172, f"README.md is {len(lines)} lines; the cap is 172"


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
    every `\\n` in these three bash files into `\\r\\n`, and the comparison is
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
    proc = subprocess.run(["git", "ls-files", "--eol", "--", *SHIPPED_BASH],
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
