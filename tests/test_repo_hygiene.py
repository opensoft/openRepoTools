# SPDX-License-Identifier: Apache-2.0
"""Properties of THIS repository that a fork depends on and nobody re-checks.

Adapted from openRepoShape's `tests/test_repo_hygiene.py` — the rules travel
with the files. NOTHING HERE NEEDS THE SUBMODULE, on purpose: these are facts
about the bash files this repository ships (`SHIPPED_BASH` and `LANE_BASH`
below) and the documents beside them, so they run in a clone made without
`--recurse-submodules` and they run on Windows, which is what the Windows job
is for.

EACH FILE IS READ FROM THE ROOT THAT OWNS IT (opensoft/openRepoTools#186,
T009). A command, a test or a pin is the CODE root's (`REPO`); `README.md`,
`AGENTS.md` and `CLAUDE.md` are the ASSEMBLY root's and `docs/` the SPEC
leg's, read through `doc()` below. On today's layout the three are one tree,
so nothing here changes; in a standalone code leg a document test skips naming
the root it needs, and in the composed run it fails rather than skip.
"""

from __future__ import annotations

import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tokenize
from collections import namedtuple
from pathlib import Path

import pytest

from conftest import REPO, ROOTS, WINDOWS_SKIP


def doc(rel: str) -> Path:
    """`rel` from the root that owns it: `ROOTS.path_for`, which skips a
    standalone code leg's test (fails a composed one) where that root is
    absent. A command passed here is simply the code root's file."""
    return ROOTS.path_for(rel)


def code_first(*names: str) -> list:
    """`names`, the code root's own files first: where a test reads a command
    AND the documents about it, a standalone code leg still asserts the
    command's half before the first document's root ends the test."""
    return sorted(names, key=lambda name: ROOTS.owner_of(name) != "code")


def tracked_files():
    """(label, path) for every file `git ls-files` tracks in every repository
    this run can read — the code root alone on today's layout, and in the
    composed run the assembly and the spec leg too, so a claim about every
    COMMITTED file still covers every file the single repository had."""
    for role, root in ROOTS.tracked_roots():
        listed = subprocess.run(["git", "ls-files"], cwd=str(root),
                                capture_output=True, text=True,
                                check=True).stdout.splitlines()
        for rel in listed:
            yield (rel if role == "code" else f"{role} root: {rel}"), root / rel

#: EVERY BASH FILE THIS REPOSITORY SHIPS, and nothing else is one. Each is a
#: file a person has on their PATH — the installer, the two estate verbs, the
#: read-only `status` and the two lane words below — so each is held to the
#: same shebang, mode bit and `set -euo pipefail` rule. The macOS job parses
#: these same SIX with `/bin/bash -n`, one command per file, which is what
#: keeps the bash-3.2 claim true. (It said "four" while the list held six,
#: which is a description contradicting the inventory it explains; Copilot
#: round 3 on #45.)
#: `lane` and `lanes` join under lane-collision-protocol Amendment 18 Addendum 1
#: and Amendment 11's ratified decision 6: each is one word a person has on
#: PATH, placed by `--install`, so each is held to the same shebang, the same
#: executable bit, the same LF index, the same bash-3.2 parse AND the same
#: `set -euo pipefail`. (`restart` was the third until Addendum 2 retired it —
#: `lane <name>` is that act, and one word a person is given rather than two.)
#: They are NOT in `LANE_BASH`, and the reason is the resolver test below: they
#: carry no copy of Amendment 9(a)'s workspace resolver because they resolve no
#: workspace — every fact either one needs comes from `lanes-edit.sh`, through
#: the reads clause (h) adds, which is the same "one implementation, several
#: callers" rule those reads exist for. A third copy of that block in a file
#: that never uses it would be a third way for it to drift.
SHIPPED_BASH = ["openRepoTools", "park", "resume", "status", "lane", "lanes"]

#: THE LANE HELPERS, which arrived here from `opensoft/brett-wip` with their
#: history under lane-collision-protocol Amendment 9(b). They are shipped bash
#: and `--install` places them, so they are held to the same shebang, the same
#: executable bit, the same LF index and the same bash-3.2 parse — but NOT to
#: `set -euo pipefail`, and the exception is deliberate rather than an
#: oversight. `lanes-edit.sh` runs `set -u` alone, because it is the register's
#: only writer and a failing command inside a lock-holding write must reach its
#: own refusal and release the lock rather than exiting where it stands.
LANE_BASH = ["lanes-edit.sh", "lane-start", "lane-end", "link-estates"]

#: `lane-handoff`, under lane-collision-protocol Amendment 17(a) — *"the act
#: Amendment 8(a) calls the swap is the HANDOFF: `lane-handoff` on `PATH`
#: (placed by `openRepoTools --install`) from a shell"*. It is shipped bash and
#: `--install` places it, so it takes the shebang, the executable bit, the LF
#: index, the bash-3.2 parse and the flag-spelling rule with the lane helpers.
#:
#: IT IS IN NEITHER LIST ABOVE, and each of them states its own reason. Not
#: `SHIPPED_BASH`, because it does not `set -e`: `R-A11-11` is that a swap is
#: never left unwritten, so a read that fails part-way through must reach this
#: command's own refusal — or drop one sub-field and carry on — rather than
#: exiting where it stands, which is `lanes-edit.sh`'s exception one file over.
#: Not `LANE_BASH`, because it carries no copy of Amendment 9(a)'s workspace
#: resolver: it resolves no workspace, and the one path it needs comes back
#: from `lanes-edit.sh workspace-root`. That is the same "one implementation,
#: several callers" rule `restart` and `lanes` are out of `LANE_BASH` for.
#:
#: `lane-rename` joins it under Amendment 16, ratified 2026-09-14T09:24:35Z, for
#: BOTH of those reasons unchanged. It does not `set -e`: clause (f)'s two acts
#: — the tmux window and the typed `/rename` — follow a write that has already
#: landed, and a command that exited where it stood would leave the register
#: renamed and the window carrying a name the register no longer has, which is
#: the one state Amendment 12's guard refuses every prompt over. And it carries
#: no workspace resolver either: its whole write is `lanes-edit.sh rename-lane`.
HELPER_BASH = ["lane-handoff", "lane-rename"]

#: Every bash file this repository ships, for the claims that are about BASH
#: and not about a command's failure discipline: the parse gate and the LF
#: index. The moved suite is 196 KB of it and is in this list for the reason
#: Amendment 9's act-3 obligation 4 gives — the macOS job parses it with bash
#: 3.2, where a `${x,,}` that nobody ran is still a syntax error.
#:
#: `tests/run.sh` (opensoft/openRepoTools#51) is bash for the same reason and
#: is held to the same parse: it is the wrapper that takes the suite's lock,
#: its `mkdir` fallback is there BECAUSE macOS has no `flock`, and a wrapper
#: that does not parse on the platform its fallback exists for is no wrapper.
#: It is in no list above — `--install` does not place it and nobody has it on
#: PATH — so the mode and discipline rules those lists carry are not asked of
#: it; this one is.
ALL_BASH = (SHIPPED_BASH + LANE_BASH + HELPER_BASH
            + ["tests/test_lane_helpers.sh", "tests/run.sh"])

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


@pytest.mark.parametrize("name", LANE_BASH + HELPER_BASH)
def test_the_lane_helpers_are_executable_and_declare_their_discipline(name):
    """The lane helpers, held to what they are rather than to what the estate
    commands are (Amendment 9(b)).

    Same shebang and same executable bit — `--install` stamps 755 on everything
    it places, and a copy that is not executable is not a command. `set -u` is
    the floor all five share; `set -e` is NOT required of `lanes-edit.sh`,
    whose whole job is to hold a lock, reach its own refusal and release it,
    nor of `lane-handoff`, whose whole job is to leave no swap unwritten.
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


#: THE FILES `--install` PLACES, READ OUT OF THE INSTALLER'S OWN LIST rather
#: than restated here. `openRepoTools` declares them once — *"One list, so the
#: installer, the fetch and the report cannot disagree"* — and deriving from it
#: is what makes the rule below hold for the NEXT file this repository ships
#: without anyone remembering to come here.
def _installables() -> list[str]:
    text = (REPO / "openRepoTools").read_text(encoding="utf-8")
    match = re.search(r"^INSTALLABLES=\(([^)]*)\)$", text, re.MULTILINE)
    assert match, "openRepoTools no longer declares `INSTALLABLES=( … )`"
    names = match.group(1).split()
    assert len(names) > 1, "INSTALLABLES parsed as one entry; the shape moved"
    return names


def test_every_placed_file_carries_in_the_index_the_mode_it_is_placed_with():
    """A COMMAND THAT IS NOT EXECUTABLE IS NOT A COMMAND, AND THE INDEX IS
    WHERE A FRESH CLONE READS THAT FROM.

    `--install` stamps 755 on everything it places, so an installed copy runs
    whatever the checkout says. What does NOT is the checkout itself: `./park`
    from a clone, and the `cp -p` the lane suite copies `lane-handoff` with,
    both take the mode git recorded.

    WHAT THIS TEST IS DERIVED FROM, AND WHY IT IS ASKED OF THE INDEX. The first
    `lane-handoff` commit under Amendment 17(a) landed 100644 and the lane
    suite's own `chmod` hid it; `e25b54c` made it 100755 and added this row, so
    the mode is now git's and the fixture reads it back rather than making it.
    The two tests above are PER-NAME, and a name nobody added to either of them
    is a name neither one asks about — which is the whole reason this one reads
    the installer's own `INSTALLABLES` list instead of a list restated here.
    (Any finding that says `lane-handoff` is 100644 is reading this paragraph
    and not the index: `git ls-files -s lane-handoff` is the answer.)

    The data file is the exception and is named as one: `repos.tsv` is read,
    never run.
    """
    names = _installables()
    proc = subprocess.run(["git", "ls-files", "-s", "--", *names],
                          cwd=str(REPO), capture_output=True, text=True,
                          check=True)
    modes = {row.split("\t", 1)[1]: row.split(" ", 1)[0]
             for row in proc.stdout.splitlines()}
    assert sorted(modes) == sorted(names), (
        f"`--install` names a file git does not track: {sorted(set(names) - set(modes))}")
    for name in names:
        want = "100644" if name.endswith(".tsv") else "100755"
        assert modes[name] == want, (
            f"{name} is {modes[name]} in the index and `--install` places it "
            f"as {want}. For a command that is `git update-index --chmod=+x "
            f"{name}`; a file that is DATA rather than a command wants the "
            f"rule above it widened, not this one loosened")


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


def test_the_three_row_writers_carry_the_same_one_line_cut_byte_for_byte():
    """THE SAME DISCIPLINE ONE BLOCK DOWN, on Amendment 13(a)'s cut.

    `lane-start`, `lane-end` and `lane-handoff` each write a row's `state` cell,
    and the cell's line is capped at 240 characters (ratified decision O1). Each
    is ONE file a person has on PATH, so the cut is copied rather than sourced,
    exactly as the workspace resolver above is — and a copy that has drifted is
    two answers to "how long may this line be, and where may it be cut".

    The question is not cosmetic. `${s:0:n}` counts BYTES wherever the locale is
    not a UTF-8 one, and these lines are full of `—`, `·` and `→`: a copy that
    cut at a bare offset would put half a character in the register, and a copy
    that cut at 239 and appended a three-byte `…` would write 242 bytes into a
    240-byte cap and be REFUSED — which is how this block came to exist, from a
    `lane-end --force` that could not close its own row (measured 2026-09-15).
    """
    def block(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        start = text.index("# --- BEGIN shared one-line cut")
        end = text.index("# --- END shared one-line cut")
        return text[start:end]

    writers = ("lane-start", "lane-end", "lane-handoff")
    blocks = {name: block(REPO / name) for name in writers}
    reference = blocks["lane-start"]
    for name, text in blocks.items():
        assert text == reference, (
            f"lane-start and {name} have drifted apart in the shared one-line "
            f"cut (Amendment 13(a))")
    assert "ctl=\"${ctl:0:230}\"" in reference, (
        "the cut no longer bounds the line at 230, which is what leaves room "
        "for the marker inside ratified decision O1's cap of 240")
    assert "ctl=\"${ctl% *}\"" in reference, (
        "the cut no longer drops the last partial word, which is the whole of "
        "what keeps a byte offset from landing inside a character")
    assert 'ctl="${ctl// \u00b7 /; }"' in reference, (
        "the cut no longer replaces the phrase's own separator, which "
        "`set-row-state` refuses inside the line")
    assert "ctl=\"${ctl//$'\\n'/; }\"" in reference, (
        "the cut no longer flattens a newline, and a row is ONE line of a "
        "table: one in this text splits the row in two and every row after it "
        "is read as a lane")
    # AND THE SKILL'S OWN COPY CARRIES THE SAME FOUR. `/handoff` is the same act
    # as `lane-handoff` under one name (Amendment 17(a)), so it writes the state
    # cell too — and a copy that dropped one of the four would be REFUSED by the
    # writer exactly where the command is not (Copilot round 4 on #82). It is
    # prose in a skill rather than a shell function, so the substitutions are
    # asserted rather than compared byte for byte.
    skill = (REPO / "skills/handoff/SKILL.md").read_text(encoding="utf-8")
    for spelling in ("hs_line=\"${payload//$'\\r'/ }\"",
                     "hs_line=\"${hs_line//$'\\n'/; }\"",
                     'hs_line="${hs_line// \u00b7 /; }"',
                     'hs_line="${hs_line//|/\u00a6}"'):
        assert spelling in skill, (
            f"the /handoff skill's row write no longer carries {spelling}, so "
            f"it can hand `set-row-state` a line that writer refuses")
    assert 'ctl="${ctl//|/\u00a6}"' in reference, (
        "the cut no longer replaces a `|`, which `set-row-state` refuses "
        "because it would forge a cell boundary in the row — and a launch "
        "flag or a directory may legitimately carry one")


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


def test_the_estate_commands_carry_the_same_flag_value_byte_for_byte():
    """`flag_value` reads `--flag value` and `--flag=value` the same way in
    all three, and the comment above it is held too.

    It sits OUTSIDE the shared estate resolver on purpose: that block answers
    "which estate is this", and this answers "did this flag get a value" —
    naming one the other would make the resolver's own header a lie. So it is
    held here, the way `expand_home` is, and for the same reason: three files
    a person has on PATH, and one answer.

    THE QUESTIONS IT ASKS ARE ASSERTED TOO, because byte-identity alone is
    satisfied by three copies of a function that asks none of them. Each is
    the whole of one refusal: the arity check #14 wrote (`park --lane` at the
    end of the line), the emptiness check `${2:?…}` used to make and #17 put
    back (`--lane ""`), and the `-*` check (`--lane --dry-run`, which parked
    with the lane set to the flag a person typed). The `=` split is the
    fourth, and it is what keeps a value that really does begin with `-`
    sayable at all.
    """
    def block(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        start = text.index("# THE VALUE OF A VALUE-TAKING FLAG")
        return text[start:text.index("\n}\n", start)]

    blocks = {name: block(REPO / name) for name in ESTATE_COMMANDS}
    reference = blocks["park"]
    for name, text in blocks.items():
        assert text == reference, (
            f"park and {name} have drifted apart in flag_value")
    for asked in ('[ $# -ge 2 ] && [ -n "$2" ] || return 1',
                  '[ -n "$FLAG_VALUE" ] || return 1',
                  'FLAG_VALUE="${1#*=}"'):
        assert asked in reference, f"flag_value no longer asks: {asked}"
    dash = reference.split('case "$2" in', 1)[1]
    assert dash.lstrip().startswith("-*)"), (
        "flag_value no longer refuses a value that begins with `-`")


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


#: THE VALUE-TAKING ARMS ACROSS THE ESTATE COMMANDS: `park`'s three (--lane,
#: --repo, --name | --project), `resume`'s four (--repo, --workspace, --org,
#: --name | --project) and `status`'s two (--repo, --name | --project). Kept
#: by hand so that a TENTH is read through `flag_value` rather than straight
#: from `$2` — the test names one that is not, and counts one that is.
VALUE_TAKING_ARMS = 9


def test_every_value_taking_arm_reads_its_value_through_flag_value():
    """A FLAG GIVEN NO VALUE, AN EMPTY ONE, OR A FLAG is refused, in every
    estate command, and every arm can also be given its value after an `=`.

    `[ $# -ge 2 ]` checks only that an argument slot exists; the `${2:?…}` it
    replaced rejected an unset OR NULL one; and neither ever asked what the
    slot HELD. The difference is silent every time, because every one of these
    values is read further down as "was this given at all?": `park --lane ""`
    parked with the lane dropped out of the WIP commit subject, `--repo ""` in
    any of the three fell past the `--repo` branch of the resolver into the
    walk-up and acted on the estate around the current directory, and `park
    Atlas --lane --dry-run` ran a REAL park whose lane was `--dry-run` — the
    flag a person typed, swallowed as a value, with nothing but the commit
    subject to say so.

    THE EMPTY HALF SHIPPED TWICE, AND AN OUTSIDE REVIEWER CAUGHT IT BOTH
    TIMES. Into `park` and `resume` at 83a1601, which swapped `${2:?…}` for
    the arity check; and into `status` at fbf6f11, its first commit, where the
    arm was written that way from the start and so was never in front of the
    review that caught the other two. Nothing in this suite could see either
    one, because each command's own tests ask what a REFUSAL says, and an arm
    that does not refuse says nothing for them to read. So it is asked here,
    of the text.

    ONE QUESTION PER ARM NOW, not three: `flag_value` (held byte-identical
    above) asks all of them, and each arm supplies its own words and its own
    `die`. So what this reads is that every line taking a value into a
    variable goes through it, within the three lines above; that the arm's
    refusal carries both its own sentence and `$FLAG_HINT`, which is where the
    `-`-led value's own line comes from; and that the case label above it
    carries BOTH spellings of every flag it names — `--lane` and `--lane=*` —
    because the `=` form is the only way left to pass a value beginning with
    `-`, and an arm that had only the spaced spelling would have taken one
    away without giving it back.

    THE COUNT IS ASSERTED TOO, and it is hand-kept on purpose. That the guard
    is right on nine arms is what the loop proves; the number is what makes a
    TENTH — a value-taking flag somebody adds next year — arrive as a failure
    to be read rather than as a silent pass. Move it in the same commit that
    adds the arm.

    Whole-line comments are dropped first, by `code_lines`, so a comment that
    QUOTES an arm in order to explain it cannot stand in for the arm.

    THE EXEMPTION IS A LINE RANGE, NOT A STRING (Copilot's review of #37,
    2026-09-14). The one legitimate read of `$2` in each file is the one
    INSIDE `flag_value`, and exempting the text `FLAG_VALUE="$2"` wherever it
    appeared was not the same claim: an arm that wrote that very line and then
    read the value back as `${FLAG_VALUE}` was exempted here AND invisible to
    the counter below, so it left nine and PASSED — the same silent pass the
    2026-09-11 review caught in the version before this one, reached by a
    different door. Proved on a scratch copy of `park` before it was changed.
    So the helper's own body is located by line number and the exemption is
    "inside it", and the assignment this reads is any shell variable in either
    spelling of `$2` — `value2="$2"` and `X="${2}"` are the same arm written
    in a different case and in braces, and neither was matched before. The
    counter reads `${FLAG_VALUE}` as well as `$FLAG_VALUE` for the same
    reason. The match stays ANCHORED at the start of the statement, because a
    `local file="$1" key="$2" line` is a function reading its own parameters
    and not an arm at all — thirty-five of those lines across the three files
    is what an unanchored search would have called a finding.
    """
    #: An assignment that takes `$2` straight, in either spelling and whatever
    #: the variable is called, ANCHORED at the start of the statement so that
    #: a function reading its own parameters (`local file="$1" key="$2" line`)
    #: is not one.
    takes_dollar_two = re.compile(r'\s*[A-Za-z_][A-Za-z0-9_]*="\$\{?2\}?"')
    #: An arm reading the value the helper answered with, in either spelling.
    reads_flag_value = re.compile(
        r'\s*[A-Za-z_][A-Za-z0-9_]*="\$\{?FLAG_VALUE\}?"')

    found = 0
    for name in ESTATE_COMMANDS:
        lines = code_lines(REPO / name).splitlines()
        # THE HELPER'S OWN BODY, by line number: `flag_value() {` to the `}`
        # in column 0 that closes it. This is the whole of the exemption
        # below, and it is a RANGE rather than a string for the reason the
        # docstring gives.
        opens = [i for i, l in enumerate(lines)
                 if l.startswith("flag_value() {")]
        assert len(opens) == 1, (
            f"{name}: {len(opens)} definitions of flag_value, expected one")
        start = opens[0]
        closes = [i for i in range(start + 1, len(lines)) if lines[i] == "}"]
        assert closes, f"{name}: flag_value is never closed in column 0"
        end = closes[0]
        for i, line in enumerate(lines):
            # A TENTH ARM WRITTEN THE OLD WAY — `X="$2"` — must be caught, not
            # missed: the count below sees only arms that read `$FLAG_VALUE`,
            # so an arm that bypasses `flag_value` would leave it at nine and
            # pass (the independent review of this branch, 2026-09-11, and
            # Copilot's of #37). The one legitimate read of `$2` in each file
            # is the one inside `flag_value` itself, and INSIDE is asked of
            # the line number, not of the text.
            if takes_dollar_two.match(line):
                assert start < i < end, (
                    f"{name}: {line.strip()} takes $2 straight from the "
                    f"command line, outside flag_value; every value-taking "
                    f"arm reads its value through flag_value")
                continue
            if not reads_flag_value.match(line):
                continue
            found += 1
            where = f"{name}: {line.strip()}"
            guard = "\n".join(lines[max(0, i - 3):i])
            assert 'flag_value "$@" ||' in guard, (
                f"{where} takes a value without asking flag_value for it")
            assert "needs a value:" in guard and "$FLAG_HINT" in guard, (
                f"{where} refuses in words that are not this arm's, or drops "
                f"the line that names the `=` spelling")
            head = i - 1
            while head >= 0 and not re.match(r"\s*-.*\)$", lines[head]):
                head -= 1
            assert head >= 0, f"{where} is not inside a case arm at all"
            spellings = [s.strip()
                         for s in lines[head].strip()[:-1].split("|")]
            spaced = [s for s in spellings if not s.endswith("=*")]
            assert sorted(spellings) == sorted(
                spaced + [s + "=*" for s in spaced]), (
                f"{where}: the arm matches {spellings}, which is not every "
                f"flag it names in both spellings")
    assert found == VALUE_TAKING_ARMS, (
        f"{found} lines take a flag's value, not {VALUE_TAKING_ARMS}: a "
        f"value-taking flag was added or removed. Read the new arm, then move "
        f"the number.")


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
#: that says the word: a `gh api "…"`, a raw-content URL, or an
#: `api.github.com/repos/…` URL (a `curl` of the REST API, which the first
#: reading did not scan; lane openRepoTools-3's review of #191, delta 5). Each
#: takes a quoted or variable argument, which the prose never does.
def fetching_lines_of(code: str) -> list[str]:
    return [line for line in code.splitlines()
            if 'gh api "' in line or 'raw.githubusercontent.com/$' in line
            or 'api.github.com/repos/' in line]


def fetching_lines(path: Path) -> list[str]:
    return fetching_lines_of(code_lines(path))


#: The REPOSITORY a fetching line names: what follows `repos/` or the raw
#: host, read as one shell expansion (`$X`, or `${…}` whole).
FETCH_REPOSITORY = re.compile(
    r"(?:repos/|raw\.githubusercontent\.com/)(\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*)")
#: `$P`, `${P}`, or `${P:-$REPO}`: a variable standing for the repository.
PAYLOAD_SLOT = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)(?::-\$REPO)?\}?")


def assigned_values(code: str, name: str) -> list[tuple[str, str]]:
    """Every `name=<value>` in `code`, as (value with its quotes off, the
    line it is on)."""
    found = []
    pattern = re.compile(r"(?:^|[\s;(])" + re.escape(name)
                         + r"""=("[^"]*"|'[^']*'|[^\s;)]*)""")
    for line in code.splitlines():
        for match in pattern.finditer(line):
            found.append((match.group(1).strip("\"'"), line.strip()))
    return found


#: The variable a pin reader binds each parsed value to, and the function
#: that alone may set it (#191's `pin_scalar`).
PIN_SCALAR_VALUES = ("$PIN_SCALAR", "${PIN_SCALAR}")


def scalar_set_only_by_the_pin_reader(code: str) -> bool:
    """`code` has a `pin_scalar() {` … `}` reader that sets `PIN_SCALAR` to a
    parsed value, and nothing else sets it to anything but empty. Without the
    reader, or with a reader that never sets it, `$PIN_SCALAR` would be
    whatever the environment held (Copilot round 2 on #195)."""
    inside = reader = False
    parsed = 0
    for line in code.splitlines():
        stripped = line.strip()
        if re.match(r"pin_scalar\(\)", stripped):
            inside = reader = True
            continue
        if inside and stripped == "}":
            inside = False
            continue
        for value, _ in assigned_values(line, "PIN_SCALAR"):
            if not value:
                continue
            if not inside:
                return False
            parsed += 1
    return reader and parsed > 0


def installer_source_violations(code: str) -> list[str]:
    """What `test_the_installer_reaches_only_this_repository` refuses in
    `code` (comment lines already dropped): each fetching line whose
    REPOSITORY is not `$REPO`, the pinned standard, or a payload variable
    that only ever holds `$REPO` or a pin's `source_repository:` value."""
    def pin_named(var: str) -> bool:
        # Set only in a `source_repository)` arm, and only to the value the
        # pin reader parsed: an arm that assigned anything else would make
        # the payload repository come from elsewhere (Copilot on #195).
        values = assigned_values(code, var)
        return bool(values) and all(
            value == "" or ("source_repository)" in line
                            and value in PIN_SCALAR_VALUES
                            and scalar_set_only_by_the_pin_reader(code))
            for value, line in values)

    def honest(var: str) -> bool:
        values = assigned_values(code, var)
        if not values:
            return False
        for value, _line in values:
            if value in ("", "$REPO", "${REPO}"):
                continue
            inner = PAYLOAD_SLOT.fullmatch(value)
            if inner and inner.group(0) == value and pin_named(inner.group(1)):
                continue
            return False
        return True

    bad = []
    for line in fetching_lines_of(code):
        slots = FETCH_REPOSITORY.findall(line)
        if not slots:
            bad.append(f"names no repository this test can read: {line.strip()}")
        for slot in slots:
            if slot in ("$REPO", "${REPO}", "$SHAPE_REPOSITORY", "${SHAPE_REPOSITORY}"):
                continue
            var = PAYLOAD_SLOT.fullmatch(slot)
            if var and honest(var.group(1)):
                continue
            bad.append(f"fetches from {slot}, which is not $REPO, the pinned "
                       f"standard, or a variable holding only those or a pin's "
                       f"source_repository: {line.strip()}")
    return bad


def test_the_installer_reaches_only_this_repository():
    """`--install` fetches from `$OPENREPOTOOLS_REPO`, or from the code
    repository the assembly it installs from PINS, and from nowhere else.

    RESTATED for the adopted layout (#191's payload source; lane
    openRepoTools-3's review of #191, delta 5, T009's to restate). The first
    reading asked only that a fetching line CONTAIN `$REPO`, so a line fetching
    from `${PAYLOAD_REPO:-$REPO}` passed by spelling whatever `PAYLOAD_REPO`
    held, and a `curl` of `api.github.com` was never read at all. Now the
    REPOSITORY each fetching line names is read out of it, and it must be one
    of three things: `$REPO`; the pinned standard (`wip init`, below); or a
    variable whose every assignment is empty, `$REPO`, or a variable that only
    a pin's `source_repository:` sets — the code repository an adopted
    assembly's `contracts/code-pin.yaml` names, which is this repository's own
    code, moved.

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
    The test below is the one that holds it to the pin.
    """
    bad = installer_source_violations(code_lines(REPO / "openRepoTools"))
    assert not bad, ("the command fetches from a repository it may not:\n    "
                     + "\n    ".join(bad))


@pytest.mark.parametrize("code, refused", [
    pytest.param('OTHER="someone/else"\n'
                 'gh api "repos/${OTHER:-$REPO}/contents/park?ref=$REF"\n',
                 True, id="passes-by-spelling"),
    pytest.param('curl -fsSL "https://api.github.com/repos/$OTHER/commits/$REF"\n',
                 True, id="an-api-curl-the-first-reading-never-read"),
    pytest.param('PAYLOAD_REPO="$FROM_THE_ENVIRONMENT"\n'
                 'gh api "repos/${PAYLOAD_REPO:-$REPO}/contents/park"\n',
                 True, id="a-payload-variable-set-from-elsewhere"),
    pytest.param('PIN_SOURCE_REPOSITORY=""\n'
                 'case "$key" in\n'
                 '  source_repository) PIN_SOURCE_REPOSITORY="$FROM_THE_ENVIRONMENT" ;;\n'
                 'esac\n'
                 'PAYLOAD_REPO="$PIN_SOURCE_REPOSITORY"\n'
                 'gh api "repos/${PAYLOAD_REPO:-$REPO}/contents/park"\n',
                 True, id="a-pin-arm-that-assigns-something-else"),
    pytest.param('pin_scalar() {\n'
                 '\tPIN_SCALAR="${v%% #*}"\n'
                 '}\n'
                 'PIN_SCALAR="$FROM_THE_ENVIRONMENT"\n'
                 'case "$key" in\n'
                 '  source_repository) PIN_SOURCE_REPOSITORY="$PIN_SCALAR" ;;\n'
                 'esac\n'
                 'PAYLOAD_REPO="$PIN_SOURCE_REPOSITORY"\n'
                 'gh api "repos/${PAYLOAD_REPO:-$REPO}/contents/park"\n',
                 True, id="a-scalar-set-outside-the-pin-reader"),
    pytest.param('case "$key" in\n'
                 '  source_repository) PIN_SOURCE_REPOSITORY="$PIN_SCALAR" ;;\n'
                 'esac\n'
                 'PAYLOAD_REPO="$PIN_SOURCE_REPOSITORY"\n'
                 'gh api "repos/${PAYLOAD_REPO:-$REPO}/contents/park"\n',
                 True, id="no-pin-reader-so-the-scalar-is-the-environments"),
    pytest.param('pin_scalar() {\n'
                 '\tPIN_SCALAR=""\n'
                 '}\n'
                 'case "$key" in\n'
                 '  source_repository) PIN_SOURCE_REPOSITORY="$PIN_SCALAR" ;;\n'
                 'esac\n'
                 'PAYLOAD_REPO="$PIN_SOURCE_REPOSITORY"\n'
                 'gh api "repos/${PAYLOAD_REPO:-$REPO}/contents/park"\n',
                 True, id="a-pin-reader-that-never-sets-the-scalar"),
    pytest.param('PIN_SCALAR=""\n'
                 'pin_scalar() {\n'
                 '\tPIN_SCALAR="${rest%%"$q"*}"\n'
                 '\tPIN_SCALAR="${v%% #*}"\n'
                 '}\n'
                 'PIN_SOURCE_REPOSITORY=""\n'
                 'case "$key" in\n'
                 '  source_repository) PIN_SOURCE_REPOSITORY="$PIN_SCALAR" ;;\n'
                 'esac\n'
                 'PAYLOAD_REPO=""\n'
                 'PAYLOAD_REPO="$REPO" PAYLOAD_REV=""\n'
                 'PAYLOAD_REPO="$PIN_SOURCE_REPOSITORY" PAYLOAD_REV="$PIN_COMMIT"\n'
                 'gh api "repos/${PAYLOAD_REPO:-$REPO}/contents/$path"\n'
                 'curl -fsSL "https://raw.githubusercontent.com/${PAYLOAD_REPO:-$REPO}/$rev/$path"\n'
                 'curl -fsSL "https://api.github.com/repos/${PAYLOAD_REPO:-$REPO}/git/trees/$1"\n',
                 False, id="the-adopted-source-honestly"),
    pytest.param('gh api "repos/$REPO/contents/park?ref=$REF"\n'
                 'gh api "repos/$SHAPE_REPOSITORY/contents/$f?ref=$ref"\n',
                 False, id="todays-two-sources"),
])
def test_the_installer_source_rule_is_not_met_by_spelling(code, refused):
    """The restated rule against planted lines: the two shapes the first
    reading let through, a payload variable fed from anywhere else, and the
    two shapes it must keep accepting."""
    assert bool(installer_source_violations(code)) is refused, (
        installer_source_violations(code))


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
    readme = doc("README.md").read_text(encoding="utf-8")
    assert RAW_INSTALL_LINE in readme, (
        "README.md does not carry the install line openRepoShape's --install "
        f"points at, byte for byte:\n    {RAW_INSTALL_LINE}")


def test_the_readme_also_carries_the_gh_api_form():
    """BOTH FORMS, because an organisation whose policy blocks
    raw.githubusercontent.com still has a working `gh` — the same reason the
    installer tries the API first. The shim's own pointer has room for one
    line; the READMEs are where the twin lives."""
    readme = doc("README.md").read_text(encoding="utf-8")
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
    readme = doc("README.md").read_text(encoding="utf-8")
    assert "gh repo clone opensoft/workBenches && cd workBenches && ./setup.sh" \
        in readme, (
        "README.md does not carry Amendment 9(e)'s first line, byte for byte")
    assert "lclaude --lane <repo>-<n> <profile>" in readme, (
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
    nothing. No command here has a PowerShell twin, and there is no
    `Invoke-WebRequest` two-liner to point at, so on Windows the way in is
    WSL2 — which both documents say, once each."""
    for name in ("README.md", "AGENTS.md"):
        text = doc(name).read_text(encoding="utf-8")
        assert "Invoke-WebRequest" not in text, (
            f"{name} offers a Windows download line for a bash-only toolset")
        assert "WSL2" in text, f"{name} must say what a Windows reader does"


def test_claude_md_points_at_agents_md():
    assert "AGENTS.md" in doc("CLAUDE.md").read_text()


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
    # THE COMMAND'S OWN HALF FIRST (#186, T009): in a standalone code leg the
    # documents are another root's, and the first one read ends the test.
    park = (REPO / "park").read_text(encoding="utf-8")
    assert "PARKED EVERY ESTATE unasked" in park, (
        "the `park` header no longer says what #91's bare form did and that "
        "it is superseded; a reader of the ruling trail needs both")
    for name in code_first("README.md", "AGENTS.md", "park"):
        text = doc(name).read_text(encoding="utf-8")
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
        doc("README.md").read_text(encoding="utf-8"), (
        "README.md does not say resume's own bare form still refuses")
    assert "`resume`'s OWN bare form still refuses" in \
        doc("AGENTS.md").read_text(encoding="utf-8"), (
        "AGENTS.md does not say resume's own bare form still refuses")


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
    status = (REPO / "status").read_text(encoding="utf-8")
    assert "--no-optional-locks" in status, (
        "status takes locks: a read-only command beside an editor must not be "
        "the thing that says index.lock exists")
    for name in code_first("README.md", "AGENTS.md", "status"):
        text = doc(name).read_text(encoding="utf-8")
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
        text = doc(name).read_text(encoding="utf-8")
        assert "`status`" in text, f"{name} never names the fourth command"
    readme = doc("README.md").read_text(encoding="utf-8")
    assert "THIRTEEN files" in readme, (
        "README.md does not count the thirteen files")
    assert "13 of 13 placed" in readme, (
        "README.md does not show the count line `--install` actually prints")


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
    for name in code_first("README.md", "AGENTS.md", "park"):
        text = doc(name).read_text(encoding="utf-8")
        assert "SKIPPED" in text, (
            f"{name} does not say the sweep SKIPS a root without the overlay")
        assert "Speckit git overlay" in text, (
            f"{name} does not name WHAT is missing from such a root")
        assert "#92" in text, f"{name} does not cite the ruling"
        assert "setup-openspeckit" in text, (
            f"{name} does not name the installer, which is the whole of what "
            f"the person reading a skipped line has to do next")
    for name in ("README.md", "AGENTS.md"):
        assert "skipped (no overlay)" in doc(name).read_text(
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


@pytest.mark.parametrize("name", ["lanes", "lane"])
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

    Held for the two words a person is given — `lanes`, which Amendment 11
    added, and `lane`, which Amendment 18 Addendum 1 added and Addendum 2 made
    the only door — and not yet for the eight files beside them: their parsers
    are older, larger and not all of this shape, and widening the rule to them
    is an act with its own evidence rather than a line in this one.
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


def test_lane_fences_a_lane_name_the_way_the_helper_does():
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

    ASKED OF `lane` NOW, because that is the file that takes a `<name>` from a
    person: Amendment 18 Addendum 2 retired `restart` from the PATH and `lane
    <name>` is its act. The fence moved with it, and this rule moved with the
    fence rather than being retired beside the file it was written for.
    """
    helper = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    wanted = re.search(r"check_lane_name\(\) \{\s*case \S+ in\s*\n\s*(\S.*?)\)",
                       helper)
    assert wanted, "lanes-edit.sh has no `check_lane_name` case pattern"
    pattern = wanted.group(1).strip()
    text = (REPO / "lane").read_text(encoding="utf-8")
    assert pattern in text, (
        "`lane` does not fence a lane name with `lanes-edit.sh`'s own "
        f"pattern.\n  the helper refuses: {pattern}\n  and `lane` must "
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
    manual = doc("docs/README-lanes.md").read_text(encoding="utf-8")
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
    surfaces = ("README.md", "docs/README-lanes.md", "lanes", "lane",
                "openRepoTools")
    usage = (REPO / "openRepoTools").read_text(encoding="utf-8")
    assert "lanes [--all] [--fetch]" in usage, (
        "`openRepoTools --help` does not offer --all, so a person narrowed "
        "into a checkout cannot find the way back to every lane")
    for name in code_first(*surfaces):
        text = doc(name).read_text(encoding="utf-8")
        assert "every lane on this workstation" not in text, (
            f"{name} still calls `lanes` the listing of every lane on this "
            f"workstation, which is the pre-settlement default")
    readme = doc("README.md").read_text(encoding="utf-8")
    assert "Narrow inside a checkout" in readme, (
        "README.md does not quote the settlement that narrowed the bare word")
    assert "lanes --all" in readme, (
        "README.md never shows the word that asks for every lane")
    assert "next free position" in readme, (
        "README.md does not say the narrowed listing ends with the next free "
        "position, which is the half of the settlement that is not a filter")
    manual = doc("docs/README-lanes.md").read_text(encoding="utf-8")
    assert "Narrow inside a checkout (Recommended)" in manual, (
        "the manual does not quote the settlement verbatim")
    assert "Yes, list and suggest (Recommended)" in manual, (
        "the manual does not quote the settlement for `lane-start <repo>` "
        "with no position, which was ratified in the same breath")


def test_agents_md_names_the_pin_rules():
    """The three rules an agent touching the submodule has to have read, and
    the reason they are in AGENTS.md rather than only in the pin's header: an
    assistant is told to read this file, and a procedure that lives outside it
    is a procedure performed from memory.

    THE PATHS ARE THE ONES THAT WORK FROM WHERE THE FILE IS READ (#193 item
    14; the coordinator's decision of 2026-10-11). On today's single tree that
    is `upstream/openRepoShape` and `git submodule update --init …`. At an
    assembly root the submodule is the code leg's, so T006's `assembly-0001`
    writes `code/upstream/openRepoShape` and `git -C code submodule update
    --init …`: the unprefixed command fails there ("pathspec
    'upstream/openRepoShape' did not match any file(s) known to git", measured
    in the composed candidate). The prefix is the assembly's code mount, read
    from its code pin, so either spelling in the wrong place fails."""
    text = doc("AGENTS.md").read_text(encoding="utf-8")
    mount = ROOTS.code_mount()
    where = f"{mount}/" if mount else ""
    init = (f"git -C {mount} submodule update --init upstream/openRepoShape"
            if mount else "git submodule update --init upstream/openRepoShape")
    assert f"Never edit anything under `{where}upstream/openRepoShape` in place" in text
    assert "Never pin a commit that is not on that repository's `main`" in text
    assert "RECOMPUTED, never adjusted" in text
    assert init in text, f"AGENTS.md does not give the command that works here: {init}"


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
    214 -> 224 on 2026-09-14, for THE RECORD'S OWN KEY ORDER, which rule 4
    had nothing about at all. `workspace_load_project` reads a record by
    INDENT and shuts the `features:` list at the next key at project indent
    and a feature's `legs:` list at the next key at feature indent, so a
    project key a bad merge left between two features — or between a
    feature and its `legs:` — costs the second feature, or every leg of
    the first: `resume` makes no feature and collects no leg out of what
    sits under a shut list.
    The ten lines buy that reading and, more than it, THE ORDER OF ITS TWO
    EXITS. The key is put back BY HAND, which is the one hand-edit of the
    record these rules ask for and reads as a contradiction of the sentence
    below it that sends a worktree the record does not know to `park` rather
    than to a hand-edit; and the re-park settles it ONLY from the workstation
    that has the feature, because `workspace_write_manifest` rewrites a
    project's whole block and `emit_recorded_feature` carries forward only
    the features that loader made. An assistant told "re-park" unaided parks
    from wherever it is standing, and that park is what deletes the lines for
    good. They are the ten this branch wrote as 162 -> 172, REBASED onto the
    214 `main` reached while it waited: the same ten lines, in the same rule 4
    sentence, touching none of the lines the entries above bought — so the
    count is the one measured after the rebase and the cap is that count.

    224 AND 214 MEET AT 224 on 2026-09-14, where this branch merged `main`
    at `63a74af` — Amendment 11's tooling, #26. The cap does not move, and
    that is the reading, not an omission: #26 changed ONE WORD of this file
    — the opening count of what `--install` places, nine to eleven — and a
    word is not a line. So the 224 below is still the number MEASURED after
    the merge rather than the branch's own carried forward, which is the
    only way either of them is ever allowed to be right, and the entry
    above stays because its ten lines are still the ten in rule 4.

    224 -> 243 on 2026-09-14, for ONE SUITE AT A TIME WHERE LANES SHARE A
    WORKSTATION, and every one of the nineteen is a thing an agent MEETS on
    this repository rather than prose about it. Measured that day: six lanes
    build in sibling worktrees of this checkout, and FOUR SUITES RAN AT ONCE
    under the guard they had all been given — `pgrep -af 'python3 -m pytest' |
    grep -v pgrep >/dev/null`, which never waits where `grep` is the harness's
    own shell function whose status is 1 when its stdout is `/dev/null`, and
    whose unanchored pattern also matches the guard's own command line. The
    lines are the working form (an anchored `pgrep -fc`, its pattern split so
    it cannot match itself, and a `flock` so the waiters cannot all start
    together), the two defects it exists for, and the sentence that makes it
    usable at all — every lane on the workstation must name the SAME lock
    file. An assistant told only "run pytest" starts the fifth suite, and this
    run is minutes of bash and hundreds of `git` processes.

    243 -> 255 the same day, when those nineteen lines gained a COMMAND to
    point at (opensoft/openRepoTools#51). Prose that shows a guard is prose
    somebody retypes, and the four suites that ran at once had each retyped
    it; `tests/run.sh` is the guard written ONCE, and the twelve lines are the
    shape of naming it: the wrapper as the first thing the testing section
    says to run, what it does (waits, takes
    `${TMPDIR:-/tmp}/openrepotools-pytest.lock`, `flock` or a `mkdir` lock on
    macOS, waits again inside it), the sentence that makes a lock a lock at
    all -- every lane on one workstation names the SAME file -- and the broken
    guard kept as the thing being corrected, because an assistant that has
    seen the working one still meets the old one in older briefs. The runnable
    form stays beneath it for a person with no checkout of this repository in
    front of them.

    224 -> 228 on 2026-09-14, for THE ONE EXIT CODE THIS FILE NOW STATES
    WRONG (lane-collision-protocol Amendment 12, opensoft/openRepoTools#25).
    Four lines, and every one of them is behaviour rather than prose about
    it. The paragraph promised, without qualification, that each of the four
    "refuses with exit 1 naming `openRepoTools wip init` where that file does
    not answer" — and `lanes-edit.sh guard` deliberately does not: it is a
    `UserPromptSubmit` hook, only a 2 blocks a prompt
    (code.claude.com/docs/en/hooks), and a 1 there would print the workspace
    refusal and let the prompt THROUGH, which is the one failure clause (d)
    forbids by name. An assistant reading the old sentence and getting a 2
    back has no way to tell a blocked prompt from the "the object is held"
    that 2 has meant here since Amendment 5, which is exactly what the
    sentence beneath it — "never read a number without knowing which command
    produced it" — exists to prevent, and it could not do that while the
    clause above it named the wrong number for one of them.

    228 + 255 MEET AT 259 on 2026-09-15, where this branch merged `main` at
    `2faa883`. Four of the merged file's lines are Amendment 12's exit-code
    correction and twelve are #51's `tests/run.sh` paragraph; neither is over
    a line the other bought, and the cap is the count of what merged rather
    than either side's number — the rule the 224 entry states.

    265 -> 278 on 2026-09-15, for ONE BINDING PER LANE — lane-collision-protocol
    AMENDMENT 18, ratified 2026-09-14T13:15:18Z, opensoft/openRepoTools#38. The
    thirteen lines are a RULE and not prose, and they are the rule an assistant
    gets WRONG if it is inferred rather than read: this tooling has always said
    a lane whose recorded session is not live is a lane to take, and the one
    thing that sentence never said is WHERE it may be said from. A pid does not
    cross a pid namespace, so from another bench container on the same machine
    the liveness read is meaningless and the honest answer is UNKNOWN — measured
    on 2026-09-14, when pyBench read cloudBench's record, called a running lane
    dead and started writing it from a second place. The paragraph names the
    read that answers (`binding`), the one exception that makes a binding
    elsewhere provably dead (a window gone from a shared tmux server), the act a
    second place takes instead of taking (`--request-handoff`, and the wait),
    the one word that overrides it and the fact that it is never automatic, and
    the three variables the launcher owns. Every one of those is a thing an
    assistant would otherwise do the opposite of.

    259 -> 265 the same day, for SIX LINES that stop this file prescribing a
    guard its own wrapper refuses to use (Copilot rounds 7 and 8 on #47). The
    snippet counted with `pgrep -fc`, which `tests/run.sh` deliberately does
    not: `-c` is not in every `pgrep` this repository runs under, and the count
    — never `pgrep`'s exit status — is what decides. A document that shows a
    person a non-portable form of the very guard the wrapper exists to make
    portable is worse than one that shows none, and the six lines are the
    correction plus the sentence naming the wrapper as the canonical
    implementation, which is what an assistant reading either should reach for.

    265 -> 276 on 2026-09-16, for ELEVEN LINES that name the one portability
    rule this repository keeps paying for twice (opensoft/openRepoTools#93).
    `awk -v name=value` carries ONE LINE: the value is processed as a string
    literal, and macOS's one-true-awk refuses a newline in one outright — exit
    2, no output — while `gawk` and `mawk` take it silently. `who_landing` paid
    for it once (R-A9-11) and left the finding in a code comment where only a
    reader of that function meets it; `delete_lines` re-made it in #93 and
    tests-macos answered with six red lines whose message was about a line
    count. The bash-3.2 paragraph above it is the same kind of rule and is
    already here for the same reason — a constraint only one job can see
    belongs where it is read BEFORE the code is written, not after CI is red —
    and the eleven lines are that rule, the two rounds as evidence, the two
    spellings that are correct (`ENVIRON`, or a second file with `NR == FNR`),
    and the suite case that now makes a third round red on every platform.

    265 -> 292 on 2026-09-16, for THE CYCLE'S THREE RULINGS (Brett Heap's
    RULING of that day, "do all three", on the coordinator's three proposals
    — measured: `tests-macos` running 49-54 minutes per push against Linux's
    17-22, pull requests drawing 6-12 Copilot review rounds, and this suite
    queuing up to 1h20 behind the workstation lock the paragraph below still
    describes). The paragraph these lines replace told an assistant that
    `tests/run.sh` IS how this suite is run and that `pytest` by hand is the
    thing it exists to stop — true of the mechanism and now wrong about the
    standard, which is what made it the one to remove rather than a
    paragraph to add beside. Numbered so each stays citable on its own:
    `tests-macos` leaves the per-push `pull_request` gate for the `ready`
    label, with its own `parse-macos` split off so the bash-3.2 syntax parse
    does not leave with it; Copilot review is capped at two rounds; and
    CI's own `tests` job, not the local wrapper, is the suite of record —
    the wrapper stays exactly the tool it always was, for a person who wants
    the whole answer locally rather than one a push now waits on. 26 of the
    27 lines came in that one commit; the last, the same day, is Copilot
    round 2 on this PR taken rather than chased past its cap: `parse-macos`
    runs on `pull_request` and on push to main, the same two triggers as the
    three jobs beside it, and the sentence saying so now names both rather
    than the "every push" a reader could take for every branch.

    276 + 292 MEET AT 303 on 2026-10-03, where #93 merged `main` at `92bd21f`.
    Eleven of the merged file's lines are #93's one-line `awk -v` rule and
    twenty-seven are #119's three rulings; neither is over a line the other
    bought, and the cap is the count of what merged rather than either side's
    number — the rule the 224 entry states.

    278 + 292 MEET AT 305 on 2026-10-03, where #83 merged `main` at `92bd21f`
    (#119). Both raised the same 265: thirteen lines are Amendment 18's ONE
    BINDING rule and twenty-seven are the cycle's three rulings, and neither is
    over a line the other bought. The cap is the count of what merged, 265 + 13
    + 27, rather than either side's number — the rule the 224 entry states.

    303 + 305 MEET AT 316 on 2026-10-03, where #93 merged `main` at `6faed35`
    (#83). Each side had already counted #119's twenty-seven over the shared
    265, so the merged file is 265 + 27 + #93's eleven (the one-line `awk -v`
    rule) + #83's thirteen (the ONE BINDING rule): the count of what merged,
    rather than either side's number — the rule the 224 entry states.

    316 HERE AND 340 AT AN ASSEMBLY ROOT, on 2026-10-08 (opensoft/openRepoTools
    #186, T009). In the triad this test reads the ASSEMBLY's AGENTS.md, and
    the root guidance of T006 (`specs/004-migrate-to-triad/
    root-guidance-2026-10-08.md`, patch `assembly-0001`) adds twenty-four lines
    to it: the shape's first-line pointer and the triad map the bootstrap
    protocol requires a root to carry. The assembly's cap is this count plus
    those lines and nothing else; today's single repository keeps 316, so no
    line of prose is bought on `main` by a file that is not here yet.

    316 -> 323 HERE AND 340 -> 347 AT AN ASSEMBLY ROOT, on 2026-10-09, for the
    same work (#186, T009; the #190 review). Seven lines at the foot of
    "Testing your changes" — a blank and six — say what an agent running the
    suite now has to know and would get wrong unaided: the suite reads each
    file from the root that owns it, the three variables that name those roots
    (`OPENREPOTOOLS_CODE_ROOT`, `OPENREPOTOOLS_ASSEMBLY_ROOT`,
    `OPENREPOTOOLS_SPEC_ROOT`), and that a root a standalone checkout lacks
    SKIPS by name while `OPENREPOTOOLS_COMPOSED=1` REFUSES instead. The
    assembly's AGENTS.md is this file with T006's `assembly-0001` applied, so
    it carries the same seven and its cap moves with them. They sit below the
    last line that patch rewrites, so it still applies here and gives 347
    lines; placed under the test block, which the patch rewrites, they made it
    fail at `AGENTS.md:224` (lane openRepoTools-3's candidate review; #193
    item 2).

    323 -> 330 HERE, on 2026-10-18, for #243's decision on item 2 (Brett
    Heap's word, "fix #242 and #243"): one family laid out twice is NOT
    de-duplicated, and AGENTS.md says so instead. Seven lines, a blank and six,
    under the opening paragraph of "Driving `park <Name>`, ...": a family's
    folder named for its repository and one named for its display `name:` are
    both found, as two estates; parking both writes ONE record key, the
    family's `id:`, so the later park replaces the first one's member blocks;
    keep only the folder named for the repository, where `make siblings` moves
    a holder. An agent that does not know it parks both and loses one layout's
    members from the record.
    THE ASSEMBLY'S 347 DOES NOT MOVE HERE, although the 316 entry makes it this
    count plus T006's twenty-four. Its file does not exist yet, and
    `assembly-0001` no longer applies to today's AGENTS.md: hunks 6 and 8 fail
    on `main` without these lines, and with them the same hunks apply and fail,
    at offsets seven lines further on. The re-cut that makes the assembly's
    file again sets its cap, and `tests/test_test_roots.py` holds 347 until
    then.
    """
    lines = doc("AGENTS.md").read_text().splitlines()
    cap = 330 if ROOTS.assembly is None else 347
    assert len(lines) <= cap, f"AGENTS.md is {len(lines)} lines; the cap is {cap}"


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
    377 -> 383 on 2026-09-14, for THE RECORD'S OWN KEY ORDER, the reading
    the AGENTS.md entry above describes. Six lines in the exception, and the
    two exits are why they are here rather than only there: this is the
    paragraph somebody meets the record layer in WITHOUT rule 4 beside it,
    and a finding whose exit reads "park that feature again" is one they run
    from the machine they happen to be sitting at — which is the park that
    rewrites the block out of its own loader's reading and takes the
    unread lines with it. The six are the six this branch wrote as
    256 -> 262, rebased onto the 377 `main` reached while it waited, in the
    same sentence of the same exception and over none of the lines the
    entries above bought.

    389 AND 377 MEET AT 403, the same merge and the same arithmetic, and both
    halves of it are above: this branch's 26 lines from 363 - 372 for ratified
    decisions 6 and 7, 382 for the round after them, 389 for the settled
    narrowing and the command file - and `main`'s 14 for the computed worktree
    path (#27, `7efc850`), both from 363, and 403 in the file that merged.
    Neither dated entry is dropped, because a cap is only worth having while
    the reason for every line of it can still be read back.

    383 AND 403 MEET AT 409 on 2026-09-14, where this branch merged `main`
    at `63a74af` — Amendment 11's tooling, #26 — after waiting on review.
    Both raises start from the 377 the entry three above records, and
    neither touches the other's lines: this branch bought 6 for the
    record's own key order, `main` bought 26 for `restart`, `lanes`, the
    `$LANES_WORKSTATION` row and the settled narrowing, and the merged
    README measures 409. The cap is the count of what merged, not either
    side's number — 383 and 403 are each a half of this file and neither
    is this file — and both dated entries above stay, because each still
    names the lines it bought.

    409 -> 417 on 2026-09-14, for lane-collision-protocol AMENDMENT 12's
    SECOND HOOK ENTRY (ratified 2026-09-13T18:20:44Z, "Ratify revision 2";
    adoption act 3, opensoft/openRepoTools#25). Eight lines, and the cap moves
    with the TOOLSET as every entry above it does: `--install` now merges TWO
    entries into `~/.claude/settings.json` rather than one, so the install
    paragraph's "seven things that are not files in that directory" is eight,
    the sentence that named one merged entry names two and says what the second
    one DOES — at every prompt it checks that the tmux window, the session's own
    name and the register row are one lane, and refuses the prompt when they are
    not — the conflict sentence gains the `guard` arm, and one line says that a
    person's own `UserPromptSubmit` hooks are left where they are, which is the
    half of the contract the count cannot show. That last line is not prose
    about the install: it is the reason the arm keys on the VERB and not on the
    word anywhere in a path, and a reader whose settings already carry
    `~/projects/xFactory/guard.sh` — this estate's usage guard, in every
    profile — needs it before they run the command. The count below the
    paragraph moves 18 -> 19 with them, in the one place it is stated here and
    derived in `test_openrepotools_command.py`.
    409 -> 422 on 2026-09-14, for the FOUR FINDINGS of #40 — Copilot's review
    of the re-vendor at `8a36eb3`, filed here rather than taken there because
    they predate the pin move. Thirteen lines, and every one of them is
    BEHAVIOUR A PERSON MEETS rather than prose about it, which is the only
    kind this cap moves for. Four in the install paragraph: `--install` stamps
    the documented mode on every artifact whether or not the bytes moved, so a
    second run prints `(mode restored to 755)` where it used to print
    `(unchanged)` over a mode it had just repaired; and a target this user
    CANNOT WRITE — not only one that is not a regular file — is refused in the
    same planning phase, with the `rm -f` that clears it and the reason that
    `rm` takes a read-only file at all. Two more say the mode of the artifacts
    that are NOT files in the bin directory, where it was the defect and not
    only the line: a `SKILL.md` whose bytes were right kept a wrong mode for
    ever, and `~/.claude/settings.json` kept a widened one on the one path
    that never rewrote it. Six for `wip init`'s seed, which staged
    `git add -A -- .` and pushed whatever an ADOPTED checkout carried into the
    one repository that holds a person's unfinished work — the refusal, what
    it names, and that it is asked before a byte is written into that
    checkout. Every dated entry above stays, and none of these thirteen is
    over one of their lines.

    422 -> 428 on 2026-09-14, for THE SIX LINES #44's first review round buys,
    each of them a refusal a person meets rather than prose about one. THREE
    SAY WHAT A DIRECTORY HAS TO BE: the question is put to the nearest ancestor
    that exists, so a `$OPENREPOTOOLS_BIN_DIR` that is not there YET is refused
    for the parent that would not take it rather than dying at an unguarded
    `mkdir -p` with the shell's own 1; a create takes a directory's search bit
    as well as its write bit, so one at 0600 is refused where `-w` alone passed
    it and the `cp` failed with eleven artifacts placed; and a refusal creates
    none of those directories, where planning used to prove each writable by
    MAKING it and so left seven behind on a machine that had none. THREE SAY
    THAT `~/.claude/settings.json` MUST ITSELF BE A REGULAR FILE — the one
    artifact no walk asked about, which mattered the moment the round before
    this one gave the `present` arm a `chmod`: `chmod` follows a symlink, so a
    settings file linked into a dotfiles checkout had the 600 stamped on the
    file at the FAR END, and the merge arms replace such a link with the file
    they wrote. Every dated entry above stays, and none of these six is over a
    line one of them bought.

    428 -> 434 on 2026-09-14, for lane-collision-protocol AMENDMENT 17,
    ratified that day, and its tooling (#36) — SIX LINES on top of the
    twenty-six above, measured after this branch merged `main` at `b5244e2`
    rather than either side's own number, which is the rule the 409 entry
    states. All six are in § "Install" and every one is a fact a person MEETS:
    the file count moved 11 -> 12 because `lane-handoff` is a word the
    amendment puts on PATH (clause (a): *"`lane-handoff` on `PATH` (placed by
    `openRepoTools --install`) from a shell"*), so the sentences carrying that
    number and the `12 of 12 placed` line a person reads back off their own
    terminal all move with it; the skill list is three rather than two and the
    command-file list three rather than one, because the act was renamed
    `handoff` with `lane-swap` kept as an alias naming it, and because `/ctx` is
    `/handoff --restart`; and the artifact count is 25. The lines that earn
    their place are the last four: a reader who types `/ctx` needs to know it
    writes the record BEFORE it respawns the pane, and that the new session
    comes up with the handoff's top block as its first prompt — which is the
    whole of why the word exists. Every dated entry above stays.

    417 and 428 -> 436 on 2026-09-14, at the merge of this branch with `main`
    @ `b5244e2`. Each side raised this cap for its own lines and every dated
    entry above stays: Amendment 12's second hook entry bought 8 on this
    branch, and #40's four findings and #44's first round bought 13 and 6 on
    `main`. They meet in ONE paragraph, the install one, which both sides
    rewrote — so the merged sentence carries both facts, the TWO merged
    entries with the name guard's own sentence AND the regular-file rule with
    the modes `--install` stamps — and a paragraph that says both is longer
    than either half of it. The cap is the count of WHAT MERGED and not
    either side's number, which is the rule the 2026-09-13 entry above states
    in its own words.

    436 + 434 MEET AT 472 on 2026-09-15, where this branch merged `main` at
    `2faa883` (Amendment 12's `UserPromptSubmit` name guard, its artifact
    accounting, and #44/#53 beneath it) on top of Amendment 17's six. The
    artifact count is TWENTY-SIX, which is what the two sides' lists come to
    together — twelve files, three skills at two paths, three command files at
    two paths, and the two hook entries — and it is derived in
    `tests/test_openrepotools_command.py` rather than believed here. The cap is
    the count of what merged, not either side's number, and every dated entry
    on both sides stays because each still names the lines it bought.

    THE CAP DOES NOT MOVE FOR AMENDMENT 16 (2026-09-15), and that is worth one
    sentence rather than none: `lane-rename` is a THIRTEENTH file on PATH and a
    TWENTY-SEVENTH artifact — every count above moves with it, derived in
    `tests/test_openrepotools_command.py` as this entry says — and the fifteen
    lines it buys in § "The lane tooling" and § "Install" fit inside 472. A cap
    is a budget and not a target: an entry that raised it by fifteen because
    fifteen lines were written would make the number mean nothing.

    472 -> 484 on 2026-10-02, for #57 (the install receipt). Twelve lines: the
    ten of the receipt paragraph in § "Install", the blank line after it, and
    one row in the environment table for `$OPENREPOTOOLS_DATA_DIR`. They are
    behaviour a person MEETS rather than prose about it. The receipt is the
    only place a retirement's evidence is explained - what a row is, that a
    digest which still matches is this installer's copy and is removed, that
    one which has MOVED is the person's edit and is named and left with the
    `rm` printed, and that rows are keyed by DESTINATION, so moving
    `$OPENREPOTOOLS_BIN_DIR` keeps the old directory's evidence. 0600 and the
    fallback are the two facts a person meeting a refused retirement needs:
    the mode the file is born at, and that a path with no row is read by the
    `Installed on PATH by` header as before. The paragraph was written at
    eighteen lines and cut to ten before this entry; the cap is raised for the
    facts above and for no arithmetic - the artifact count stays where
    `tests/test_openrepotools_command.py` derives it, and not here. Every dated
    entry above stays, and none of these twelve is over a line one of them
    bought.

    484 -> 486 on 2026-10-02, for #64 (Brett Heap's RULING of that day,
    verbatim "go with option 1 on #64"). Two lines in `wip init`'s seed
    paragraph, and both are a refusal a person MEETS rather than prose about
    one: a checkout ADOPTED clean but ahead of its workspace repository's
    `main` by any commit other than an earlier run's own unpushed seed is
    refused before a byte is written into it, naming those commits, because
    step 8's push would publish every one of them — and pushing or discarding
    them is the person's. The paragraph already says why the worktree half of
    the same rule exists; this is its history half, and a reader of one should
    not meet the other as a surprise. Every dated entry above stays.

    486 HERE AND 510 AT AN ASSEMBLY ROOT, on 2026-10-08 (opensoft/openRepoTools
    #186, T009), for the reason the AGENTS.md entry of that day gives. The
    twenty-four lines `assembly-0001` adds to the assembly's README are the
    lockstep-invariant section the leg pins' `resync_runbook:` names
    (`README.md#the-lockstep-invariant`) and the three-repository front door.
    Today's single repository keeps 486.

    486 -> 505 HERE, on 2026-10-18
    (opensoft/openRepoTools #228, feature 006, T024), for what a workstation
    with pipx's link reads. Twenty lines, each one a thing a person MEETS: the
    version paragraph, 3 -> 7 (FR-043), which said "no version number" and
    now says that a release is an annotated tag, that the version comes only
    from the tag, and what `--version` prints stamped, unstamped and from a
    checkout; the one sentence that a workstation uses one install route or
    the other until workBenches#165 lets its `setup-estate-commands.sh`
    accept pipx's link, with its blank (FR-047, Brett Heap's decision of this
    day), 4; the paragraph that says what `--install` does beside that link,
    with its blank, 7; the sixteen-of-seventeen pointer on the file count and
    the one-link-skipped sentence in the symlink passage, 1 and 1; and the
    count invariant's twenty-eight placed, one left to pipx and 28 receipt
    rows, 3 (FR-044). No pipx install route is added (FR-045). Every dated
    entry above stays.
    THE ASSEMBLY'S 510 DOES NOT MOVE HERE, although the 2026-10-08 entry makes
    it this count plus T006's twenty-four, which would be 529. Its file does
    not exist yet, and the README part of `assembly-0001` no longer applies to
    today's README, at three hunks: the one at `README.md:237`, which adds the
    assembly's install sentence, fails against this entry's own rewrite of the
    file-count sentence; the one at `README.md:260`, which moves `tests/run.sh`
    under `code/`, fails against this entry's one-link-skipped sentence in the
    symlink passage; and the one at `README.md:300`, which does the same for
    `commands/swap.md`, fails against #237's (#247's) rewrite of the count
    paragraph. None of the three can be counted at this head, so
    529 would be arithmetic over a patch that does not apply. The re-cut that
    makes the assembly's file again sets its cap, as the 2026-10-18 AGENTS.md
    entry above says for its 347, and `tests/test_test_roots.py` holds 510
    until then.
    """
    lines = doc("README.md").read_text().splitlines()
    cap = 505 if ROOTS.assembly is None else 510
    assert len(lines) <= cap, f"README.md is {len(lines)} lines; the cap is {cap}"


def test_readme_says_what_a_release_is_and_offers_no_package_route():
    """What T024 put in README is held here, because the line cap is the only
    thing that bites otherwise (the review of PR 4 of #228, S2: a README
    that offered the pipx route, dropped the one-route sentence, took back
    "no version number" or counted 17 of 17 beside pipx's link, each stayed
    green).

    SC-009 and FR-045: README names no package route. No line holds `pipx
    install` or `pip install` before `openrepotools` in any spelling of the
    name, which is the check T024's own verify makes once, and makes only for
    the lower-case `pipx install openrepotools`. FR-047: the install section
    cites opensoft/workBenches#165. FR-043: the version paragraph holds the
    three first lines `--version` prints, stamped, unstamped and from a
    checkout, spelled as `contracts/cli-output.md` gives them. FR-044: the
    count line beside pipx's link and the count invariant's receipt rows.

    FR-045's later PR (the change's tasks.md 6.4) rewrites this test: it adds
    the pipx route, so the first assertion goes with it, and the other three
    follow the text it moves."""
    text = doc("README.md").read_text(encoding="utf-8")

    route = re.compile(r"(?i)\bpipx?\s+install\b.*\bopenrepotools\b")
    offered = [line for line in text.splitlines() if route.search(line)]
    assert not offered, (
        "README.md offers a package route, which FR-045 and SC-009 forbid "
        f"until the workBenches condition holds: {offered}")

    install = re.search(r"(?ms)^## Install\n(.*?)(?=^## )", text)
    assert install, "README.md has no `## Install` section"
    assert "opensoft/workBenches#165" in install.group(1), (
        "README.md's install section does not cite opensoft/workBenches#165, "
        "which FR-047 requires beside the one-route sentence")

    stamped = "openRepoTools <version> (<repository> @ <commit>)"
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text)]
    version = [p for p in paragraphs if stamped in p]
    assert version, f"README.md has no paragraph holding `{stamped}`"
    for first_line in (stamped, "openRepoTools 0.0.0 (an unstamped package)",
                       "openRepoTools (<repo> @ <ref>)"):
        assert first_line in version[0], (
            f"README.md's version paragraph does not hold `{first_line}`")

    for count in ("16 of 17 placed in <dir>, and 1 left to pipx",
                  "28 receipt rows"):
        assert count in text, (
            f"README.md does not say `{count}` beside pipx's link (FR-044)")


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

#: THE BENCH ROOT, A RULE OF ITS OWN (opensoft/openRepoTools#193, item 22). A
#: path under a bench's root names one machine as surely as a home directory
#: does, and the rule above never matched it: 87 lines in two committed files
#: carried one, checked by a person's eye alone. It is a second pattern, and
#: not a fifth alternative above, because it has an allowance the first rule
#: has no use for (`QUOTED_SEARCH_PATTERNS`, below).
#:
#: The pattern wants the root at the START of a path. Nothing that continues a
#: path segment (a word character), a home directory (`~`), a variable (`$`,
#: `}`) or a relative walk (`.`) may stand directly before it, so a relative
#: `templates/<name>/` directory called `workspace`, or `~/workspace/…`, is not
#: this bench's root and is not a finding. The root's name carries the trailing
#: slash on purpose: `workspace.yaml` and `workspace-root/` are not it.
#:
#: THE ROOT IS SPELLED IN TWO PIECES for the reason `_CLAUDE_TMP_PREFIX` is:
#: this file is scanned like every other, and a contiguous spelling here would
#: be a finding in the very file that defines the rule.
_BENCH_ROOT = "/work" + "space/"
BENCH_ABSOLUTE_PATH = re.compile(r"(?<![\w.~$}])" + re.escape(_BENCH_ROOT))

#: THE ONE ALLOWANCE: a path inside a quoted SEARCH PATTERN. A recorded
#: `grep -e '<root>/…'` says what was searched for, and swapping a placeholder
#: into it would make the record claim a different search. Three lines of
#: `specs/004-migrate-to-triad/consumer-reads-2026-10-07.md` are exactly that.
#:
#: It is narrow on purpose. An allowed span is a SINGLE-QUOTED string (the shell
#: expands nothing in one, so it is plainly a literal) that is
#:   - the first quoted operand after a `grep` word and its short flags, as in
#:     `grep -rn '^path: …'` and `grep -E '…'` (`git grep -n -e '…'` is this
#:     form too: `-e` reads as one more flag), or
#:   - the argument of a further `-e`, as in `grep -n -e 'a' -e 'b'`.
#: Everything else stays a finding. The run of flags ends at the first word that
#: is not a short flag, so a flag followed by a bare value (`grep -m 1 '…'`)
#: licenses nothing; and a bundle that carries a lowercase `f` (`-f`, `-rf`) is
#: not a flag of the run at all, because `-f` names a pattern FILE, which is a
#: path and never a pattern (`-F`, fixed strings, is an ordinary flag). Likewise
#: a second quoted operand is a FILE (`grep -n 'x' '<path>'`), a double-quoted
#: string can hold a variable, and a path before the `grep` (`git -C <path>
#: grep …`) is outside it.
#:
#: A scrubbed span is replaced by `grep ` WITH its space: a bare `grep` ends in a
#: word character, and the root's lookbehind would then drop a path glued onto
#: the closing quote. The key is the word `grep`, not a command position, so
#: prose or an `echo` that says `grep '…'` is scrubbed the same way; this is a
#: lexical rule for text a person reviews, not a shell parser. Within a line
#: only: no whitespace in these patterns may be a newline.
QUOTED_SEARCH_PATTERNS = re.compile(
    r"\bgrep(?:[ \t]+-(?![A-Za-z]*f)[A-Za-z]+)*[ \t]+'[^'\n]*'"
    r"(?:[ \t]+-e[ \t]+'[^'\n]*')*")


def host_absolute_path_hits(text: str) -> list[str]:
    """Every host-absolute path in `text`: the matched strings of
    `HOST_ABSOLUTE_PATH`, then one `line N: <the line>` for each line that
    names the bench root outside a quoted search pattern. A bare `[]` means the
    text is clean."""
    hits = HOST_ABSOLUTE_PATH.findall(text)
    for number, line in enumerate(text.splitlines(), 1):
        scrubbed = QUOTED_SEARCH_PATTERNS.sub("grep ", line)
        if BENCH_ABSOLUTE_PATH.search(scrubbed):
            hits.append(f"line {number}: {line.strip()[:120]}")
    return hits


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


#: THE THREE CAUSES OF EXIT 3, as `lanes-edit.sh`'s exit-code table and the
#: manual's copy of it give them, and what ties each cause to the `die` that
#: reports it (opensoft/openRepoTools#68 item 5).
#:
#: A DIE IS TIED TO ITS CAUSE BY WHERE IT SITS AND NEVER BY WHAT IT SAYS. #68
#: item 3 rewords `git_timeout_die`'s message and the act 2 `commit_publish`
#: rewrites the push loop's, and a rule that found each die by a run of its own
#: words would go blind at the first rewording that keeps the meaning (the
#: first version of this rule did: it found the rebase conflict's die by the
#: text `rebase conflict on origin/$LANES_BRANCH`). So:
#:
#:   * `function`: the cause owns every `die … 3` inside that function —
#:     `git_timeout_die`, which exists to report one thing;
#:   * `marker`: else the cause owns a `die … 3` that follows its marker
#:     nearer than any other cause's marker, inside the same function — the
#:     `dirty_elsewhere` guard that skips the pull and pushes straight out
#:     (a peer's uncommitted file), and the `git_net … pull` call, after which
#:     the rebase conflict's die sits (its `else` arm, reached when that call
#:     fails). Neither is the function's name, so renaming `commit_push` leaves
#:     the rule standing; and the marker is a CALL, not a word, because the
#:     peer branch's own `note` says "skipping 'pull --rebase'" a few lines
#:     above its die.
#:
#: What a die and each row that documents its cause must keep saying is
#: `concept`: one word-group per cause, loose enough that rewording keeps
#: passing ("timed out", "timeout" and "time-out" are one concept) and tight
#: enough that a row which drops the cause fails. `scoped` is the wording #32
#: put on the one cause whose die could be read as a claim about origin.
#:
#: A FOURTH CAUSE is a new row in this tuple and a new clause in BOTH rows — and
#: a fourth `die … 3` with no row is exactly what the rule below refuses.
_Exit3Cause = namedtuple("_Exit3Cause", "name function marker concept scoped")
_EXIT_3_CAUSES = (
    _Exit3Cause(
        "a network timeout", "git_timeout_die", None,
        re.compile(r"\btime[ds]?[ -]?out", re.I), None),
    _Exit3Cause(
        "six attempts blocked by a peer's uncommitted file", None,
        re.compile(r"\bdirty_elsewhere\b"),
        re.compile(r"\b(?:uncommitted|dirty)\b", re.I), None),
    _Exit3Cause(
        "a rebase conflict", None,
        re.compile(r"\bgit_net\b[^\n]*\bpull\b"),
        re.compile(r"\brebase\W+conflict", re.I),
        re.compile(r"\bnot pushed by this attempt", re.I)),
)

#: A `die` whose message is one quoted literal and whose last word is `3`; a
#: `\"` inside the message is read whole. A message that holds a command
#: substitution with quotes of its own is NOT read by this, so `_exit_3_dies`
#: also counts every line that ends `… 3` after a closing quote and compares:
#: a `die` of that shape this cannot read is a finding. What stays out of its
#: reach is a `die` whose exit code is not a literal `3` on the line that closes
#: the message: the code held in a variable, or a `3` on a backslash-continued
#: line of its own.
_DIE_EXIT_3 = re.compile(r'\bdie "((?:[^"\\]|\\.)*)"[ \t]+3\b', re.S)
_ENDS_IN_EXIT_3 = re.compile(
    r'''["'][ \t]+3(?=\s*(?:$|;|\|\||&&|\)|\}|#))''', re.M)

#: A SENTENCE THAT CLAIMS THE EDIT NEVER REACHED ORIGIN. Exit 3 is the code for
#: "this attempt cannot confirm whether it also reached origin" (#32): a hung
#: push often landed, and an aborted pull is no proof the commit stayed local
#: in a checkout every lane shares. "not pushed BY THIS ATTEMPT" is the one
#: true form of the claim, and is the one form this lets through.
_NOTHING_REACHED_ORIGIN = re.compile(
    r"\bnothing (?:was |has been )?pushed\b"
    r"|\bnot (?:been )?pushed\b(?! by this attempt)"
    r"|\bnever (?:been )?pushed\b"
    r"|\b(?:never|not|nothing) reach(?:ed)? origin\b", re.I)


def _function_around(code: str, at: int):
    """`(name, offset of its body)` of the shell function whose body holds
    offset `at` of `code`, or None where `at` is outside every function. A
    function ends at the first line after its header that is a `}` alone in
    column 0, which is how `lanes-edit.sh` closes every one of them (the `}'`
    that closes a multi-line awk program inside one is not that line)."""
    headers = list(re.finditer(r"^([A-Za-z_]\w*)\(\) *\{", code[:at], re.M))
    if not headers:
        return None
    header = headers[-1]
    if re.search(r"^\}[ \t]*(?:#.*)?$", code[header.end():at], re.M):
        return None
    return header.group(1), header.end()


def _exit_3_cause_of(code: str, at: int):
    """The cause in `_EXIT_3_CAUSES` that the `die` at offset `at` of `code`
    reports, or None where nothing anchors it to one."""
    around = _function_around(code, at)
    if around is None:
        return None
    name, body = around
    for cause in _EXIT_3_CAUSES:
        if cause.function == name:
            return cause
    nearest, nearest_at = None, -1
    for cause in _EXIT_3_CAUSES:
        if cause.marker is None:
            continue
        hits = [m.start() for m in cause.marker.finditer(code, body, at)]
        if hits and hits[-1] > nearest_at:
            nearest, nearest_at = cause, hits[-1]
    return nearest


#: Every mention of `git_timeout_die` but its definition (`git_timeout_die() {`),
#: each read as a call; and what may stand before a command on its line.
_GIT_TIMEOUT_MENTION = re.compile(r"\bgit_timeout_die\b(?!\s*\()")
_AT_COMMAND_START = re.compile(r"(?:^|&&|\|\||[;|({]|\b(?:then|do|else))\s*$")


def _timeout_operations(code: str):
    """`(operations, findings)`: the network operations every call of
    `git_timeout_die` names (`push`, `pull`, ...), read off the words that
    follow the call on its line: a quoted command "for the reader"
    (`git_timeout_die "git push origin $B"`), a bare or quoted operation word
    (`git_timeout_die push "git push origin $B"`), or both. A timeout row that
    names a push and a pull is right until a call names a fetch.

    EVERY MENTION OF THE NAME BUT ITS DEFINITION IS READ AS A CALL, and a call
    whose shape this cannot read is a finding that says exactly that. It is
    never "nothing calls it", which would be false of a call spelled in a shape
    the reader did not expect (#68 item 3 may hand it the operation as a word
    of its own)."""
    operations, findings = set(), []
    mentions = list(_GIT_TIMEOUT_MENTION.finditer(code))
    if not mentions:
        findings.append(
            "lanes-edit.sh has no call of `git_timeout_die` (every mention of "
            "it but its definition is read as one), so the timeout cause both "
            "rows document can never fire")
    for mention in mentions:
        line = code.count("\n", 0, mention.start()) + 1
        head = code.rfind("\n", 0, mention.start()) + 1
        tail = code.find("\n", mention.end())
        rest = code[mention.end():tail if tail != -1 else len(code)]
        if not _AT_COMMAND_START.search(code[head:mention.start()]):
            findings.append(
                f"lanes-edit.sh:{line} mentions `git_timeout_die` somewhere "
                "other than the start of a command, a shape this rule cannot "
                "read as a call, so it cannot tell which network operation it "
                "is called for. Make it the first word of a command; if it is "
                "only a mention in a string, leave the name out of the string")
            continue
        words = []
        for token in (_commands_on(rest) or [[]])[0]:
            if token.startswith("#"):
                break
            words.append(token)
        text = " ".join(words)
        named = set(re.findall(r"\b(push|pull|fetch|clone)\w*", text))
        if not named:
            findings.append(
                f"lanes-edit.sh:{line} calls `git_timeout_die` with {text!r}, "
                "which names no network operation (push, pull, fetch or clone) "
                "as a bare word or in a quoted command, so the rows cannot be "
                "held to it")
        operations |= named
    return operations, findings


def _exit_3_dies(src: str):
    """`(dies, operations, findings)` for the text of `lanes-edit.sh`: every
    `die "…" 3` as `(cause, line, message)`, the network operations
    `git_timeout_die` is called for, and everything about the DIES themselves
    that is wrong. The line numbers are the file's own (a whole-line comment is
    blanked, not removed), and no comment is read as code."""
    code = "\n".join("" if line.lstrip().startswith("#") else line
                     for line in src.splitlines())

    def line_of(offset: int) -> int:
        return code.count("\n", 0, offset) + 1

    dies, findings = [], []
    read = list(_DIE_EXIT_3.finditer(code))
    for m in read:
        message = re.sub(r"\s+", " ", m.group(1))
        cause = _exit_3_cause_of(code, m.start())
        if cause is None:
            around = _function_around(code, m.start())
            findings.append(
                f"lanes-edit.sh:{line_of(m.start())} has a `die … 3` in "
                f"{around[0] if around else 'no function'} that none of the "
                "documented causes explains, so the exit-code table and the "
                "manual have no clause for it. Document it in BOTH rows, then "
                f"add it to `_EXIT_3_CAUSES`: {message!r}")
            continue
        dies.append((cause, line_of(m.start()), message))
    read_ends = {m.end() for m in read}
    for m in _ENDS_IN_EXIT_3.finditer(code):
        if m.end() not in read_ends:
            findings.append(
                f"lanes-edit.sh:{line_of(m.start())} ends in `… 3`, but this "
                "rule cannot read it as a `die \"…\" 3` (a message holding a "
                "command substitution with quotes of its own?), so it cannot "
                "be held to the rows. Spell the message as one quoted literal")
    for cause, line, message in dies:
        said = _NOTHING_REACHED_ORIGIN.search(message)
        if said:
            findings.append(
                f"lanes-edit.sh:{line}: the exit-3 die for {cause.name} claims "
                f"that nothing reached origin ({said.group(0)!r}), where a "
                "push may already have landed (#32)")
        if not cause.concept.search(message):
            findings.append(
                f"lanes-edit.sh:{line}: the exit-3 die in the branch for "
                f"{cause.name} does not name that cause, so the row that "
                f"documents it describes a message nobody prints: {message!r}")
        if cause.scoped and not cause.scoped.search(message):
            findings.append(
                f"lanes-edit.sh:{line}: the exit-3 die for {cause.name} lost "
                "its attempt-scoped wording (\"not pushed by this attempt\"), "
                f"the one form of that claim #32 found true: {message!r}")
    for cause in _EXIT_3_CAUSES:
        if not any(found is cause for found, _, _ in dies):
            findings.append(
                f"no `die … 3` reports {cause.name}, which both rows document: "
                "either the cause is gone from the code and the rows are stale, "
                "or its die moved where nothing anchors it (see "
                "`_EXIT_3_CAUSES`)")
    operations, more = _timeout_operations(code)
    return dies, operations, findings + more


def _flattened(text: str) -> str:
    """`text` as one run of words, however the source wrapped it. A row that
    wraps onto a comment-continuation line puts a literal `#` back-to-back
    with the next word once newlines alone are collapsed, so the leading `#`
    (`lanes-edit.sh`'s own comment marker; a no-op on the manual's markdown,
    which never starts a line with one) goes from every line FIRST, and a
    phrase that wraps still reads as one run of words."""
    lines = (re.sub(r"^#\s*", "", line) for line in text.splitlines())
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _exit_3_row_of_the_table(table: str) -> str:
    """The exit-3 row of `lanes-edit.sh`'s table: from its `#   3  ` header to
    the next row's, continuation lines and all; the empty string if none."""
    heads = list(re.finditer(r"^#\s+(\d+)\s{2}", table, re.M))
    for index, head in enumerate(heads):
        if head.group(1) == "3":
            stop = heads[index + 1].start() if index + 1 < len(heads) else len(table)
            return table[head.start():stop]
    return ""


def _exit_3_row_of_the_manual(section: str) -> str:
    """The manual's exit-3 row, one markdown line; the empty string if none."""
    row = re.search(r"^\|\s*3\s*\|.*$", section, re.M)
    return row.group(0) if row else ""


def _exit_3_row_findings(name: str, whole: str, row: str, operations) -> list[str]:
    """What is wrong with ONE document's exit-3 row: `whole` is all the text
    of the document that is held to the old claim, `row` is the exit-3 row
    alone, both flattened."""
    findings = []
    if "nothing was pushed" in whole or "nothing pushed" in whole:
        findings.append(
            f"{name} still claims that nothing reached origin on exit 3, which "
            "an aborted pull does not prove (#32)")
    if not row:
        findings.append(f"{name} has no exit-3 row")
        return findings
    said = _NOTHING_REACHED_ORIGIN.search(row)
    if said:
        findings.append(
            f"{name}'s exit-3 row claims that nothing reached origin "
            f"({said.group(0)!r}), where a push may already have landed (#32)")
    for cause in _EXIT_3_CAUSES:
        if not cause.concept.search(row):
            findings.append(
                f"{name}'s exit-3 row no longer names {cause.name}, a cause "
                "the code's `die … 3` still reports. Exit 3 is \"no two "
                "meanings on one number\", so a code with three causes has to "
                "name all three (#50 rounds 3 and 4, 5203261904 and "
                "5203455553)")
        if cause.scoped and not cause.scoped.search(row):
            findings.append(
                f"{name}'s exit-3 row lost the attempt-scoped wording for "
                f"{cause.name} (\"not pushed by this attempt\")")
    for operation in sorted(operations):
        if not re.search(rf"\b{operation}", row, re.I):
            findings.append(
                f"{name}'s exit-3 row never names a {operation}, which "
                "`git_timeout_die` is called for: a timeout on it ends in "
                "exit 3")
    return findings


def _exit_3_findings(src: str, manual: str | None = None) -> list[str]:
    """Every way the exit-3 `die`s of `src` (the text of `lanes-edit.sh`), its
    exit-code table and — when given — the manual's copy of that table
    disagree. Empty when they agree. The code's half comes first and alone
    when there is no manual: a standalone code leg has none (#186, T009)."""
    dies, operations, findings = _exit_3_dies(src)
    start = src.index("# EXIT CODES — every subcommand, one table")
    end = src.index("# --no-sweep", start)
    table = src[start:end]
    findings += _exit_3_row_findings(
        "lanes-edit.sh's exit-code table", _flattened(table),
        _flattened(_exit_3_row_of_the_table(table)), operations)
    if manual is not None:
        heading = manual.index("### Exit codes")
        section = manual[heading:manual.index(
            "3 to 6 are the codes this helper already used", heading)]
        findings += _exit_3_row_findings(
            "docs/README-lanes.md's copy of the table", _flattened(manual),
            _flattened(_exit_3_row_of_the_manual(section)), operations)
    return findings


def test_the_exit_3_documentation_agrees_with_the_die_message_it_describes():
    """Copilot's review of PR #50 (5202640056): the `die` for exit 3 picked up
    attempt-scoped wording (#32) — *"not pushed by this attempt; a later
    write from this checkout may already carry it"* — while the exit-code
    table just above it in the same file, and the manual's own copy of that
    table (`docs/README-lanes.md`), both still read *"nothing was pushed"* /
    *"nothing pushed"*, a claim an aborted pull never proved. A table (or a
    manual) that contradicts the code it describes is worse than no table at
    all — the same claim `test_the_exit_code_table_carries_every_code_the_
    file_exits_with` makes for a code missing from the table entirely.

    Round 2 (5203033893) found this test's own gap: it read only the table
    and the manual, so a regression in the `die` MESSAGE ITSELF, back to
    "nothing was pushed", left both docs unchanged and passed anyway — a
    test that enforces two descriptions agree with each other, never that
    either agrees with the code. The die is extracted and checked first now,
    so all three have to agree with the one thing that actually runs.

    Round 3 (5203261904) named exit 3's other two causes (`git_timeout_die`,
    and six push attempts exhausted against a peer's uncommitted file) that
    this row used to leave out entirely; the row now names all three, which
    means the phrase this test looks for can legitimately wrap onto its own
    comment-continuation line — so the comparison text is whitespace-
    normalized (one space, however the source wrapped it) rather than
    matched as one literal run of characters.

    Round 4 (5203455553) found this test's own gap in THAT check: it looked
    for the bare word "timeout" only, which the round-3 wording ("timeout on
    the push itself") already satisfied while omitting `git_timeout_die`'s
    OTHER call site — a timed-out `git pull --rebase` (`commit_push`'s
    `git_timeout_die "git pull --rebase …"`) — entirely. Checking for
    "timeout" alone would keep passing even if a push is all either row ever
    names again; "push" and "pull" are now checked for too, so the row has to
    cover both keywords or the test catches it.

    ROUND 5 (5203628254) AND #68 ITEM 5: the gap that was left. Of the three
    `die "…" 3` in `lanes-edit.sh` — `git_timeout_die`'s own (:1894 at main
    08e7550), the six-attempts one in `commit_push`'s dirty-checkout branch
    (:2125) and the rebase conflict's (:2192) — this test read ONE, and the
    two rows only for the WORDS timeout, push, pull and peer's somewhere in
    the code's whole table text, not even in its exit-3 row. So either of the
    other two dies could say anything, "nothing was pushed" included, where a
    push may already have landed, and this test stayed green. It now reads
    EVERY `die … 3` and holds each to both rows. What ties a die to its cause
    (where it sits, so that a rewording that keeps the meaning cannot blind the
    rule: #68 item 3 will reword, and so will the act 2 `commit_publish`) and
    what each die and row must keep saying are written at `_EXIT_3_CAUSES`
    above. A `die … 3` no cause explains is a finding: a fourth cause needs a
    clause in BOTH rows before it ships.

    The rule is `_exit_3_findings`; its own regression cases, one red per
    mutation and one green per rewording that keeps the meaning, are the
    `EXIT_3_*` tables below it, run on a fixture and not on this file's text.
    """
    src = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    # THE CODE'S TABLE FIRST, THEN THE MANUAL (#186, T009): in a standalone
    # code leg the manual is the spec leg's, and the table's half of every
    # claim above is asserted before that absence ends the test.
    findings = _exit_3_findings(src)
    assert not findings, (
        "lanes-edit.sh's exit-3 `die` messages and its exit-code table do not "
        "agree (opensoft/openRepoTools#68 item 5):\n  " + "\n  ".join(findings))
    manual = doc("docs/README-lanes.md").read_text(encoding="utf-8")
    findings = _exit_3_findings(src, manual)
    assert not findings, (
        "the exit-3 `die` messages, the code's table and the manual's copy of "
        "it do not agree (opensoft/openRepoTools#68 item 5):\n  "
        + "\n  ".join(findings))


#: A FIXTURE FOR THE RULE ABOVE, shaped like the three places exit 3 is raised
#: and the two rows that document it, and carrying the decoys that fooled
#: simpler rules: a `die … 3` in a comment, and a `note` that says "skipping
#: 'pull --rebase'" a few lines above the peer branch's die.
EXIT_3_SOURCE = '''\
# EXIT CODES — every subcommand, one table
#   0  done
#   3  the edit is never a permanent loss, but this attempt cannot confirm
#      whether it also reached origin. THREE CAUSES:
#      a rebase conflict (not pushed BY THIS ATTEMPT; look by content first);
#      a network timeout on a push OR a pull (a hung one often landed);
#      or six attempts exhausted because a peer's own uncommitted file blocks
#      every rebase.
#   4  the mutex could not be taken within 60s
# --no-sweep is not an exit code
# die "a decoy in a comment, which nothing runs" 3
git_timeout_die() {   # <the command, for the reader>
  release_lock
  die "timed out after ${GIT_TIMEOUT}s on '$1' — your commit is local; nothing was lost." 3
}
commit_push() {
  while [ "$attempt" -le 6 ]; do
    others="$(dirty_elsewhere)"
    if [ -n "$others" ]; then
      note "skipping 'pull --rebase' and pushing straight out"
      git_net push -q origin "$BRANCH" && return 0
      [ "$GIT_TIMED_OUT" = 1 ] && git_timeout_die "git push origin $BRANCH"
      if [ "$attempt" -ge 6 ]; then
        die "could not push origin/$BRANCH: behind the remote, and a peer's uncommitted file blocks the rebase. Nothing was lost — your commit is local." 3
      fi
    elif git_net pull --rebase -q origin "$BRANCH"; then
      git_net push -q origin "$BRANCH" && return 0
      [ "$GIT_TIMED_OUT" = 1 ] && git_timeout_die "git push origin $BRANCH"
    else
      [ "$GIT_TIMED_OUT" = 1 ] && git_timeout_die "git pull --rebase origin $BRANCH"
      die "rebase conflict on origin/$BRANCH — not pushed by this attempt; a later write from this checkout may already carry it, so look before you retry." 3
    fi
  done
  die "could not push origin/$BRANCH after 6 attempts" 6
}
'''

EXIT_3_MANUAL = '''\
### Exit codes

| code | meaning |
|---|---|
| 0 | done |
| 3 | the edit is never a permanent loss, but this attempt cannot confirm whether it also reached origin — a rebase conflict (not pushed by this attempt; look by content first), a network timeout on a push or a pull (a hung one often landed), or six attempts exhausted because a peer's uncommitted file blocks every rebase |
| 4 | the mutex could not be taken within 60s |

3 to 6 are the codes this helper already used; 7 and 8 were free.
'''


def _a_fourth_die(message: str) -> str:
    """A FOURTH FUNCTION WITH AN EXIT-3 DIE, to append to the fixture's source."""
    return "index_open() {\n  die \"" + message + "\" 3\n}\n"


#: Each row is (why, where, old, new, what the findings must say): `old` is
#: replaced by `new` in the fixture's `code` or `manual`, and the rule must
#: refuse the result, in the words of the last column.
EXIT_3_REFUSED = [
    ("the timeout die says nothing was pushed", "code",
     "your commit is local; nothing was lost.",
     "your commit is local; nothing was pushed.",
     "claims that nothing reached origin"),
    ("the peer's-file die says nothing was pushed", "code",
     "Nothing was lost — your commit is local.",
     "Nothing was pushed — your commit is local.",
     "claims that nothing reached origin"),
    ("the conflict die drops its attempt-scoped wording", "code",
     "not pushed by this attempt; a later write",
     "not pushed to origin; a later write",
     "attempt-scoped"),
    ("the conflict die no longer says what failed", "code",
     "rebase conflict on origin/$BRANCH — not pushed",
     "the pull failed on origin/$BRANCH — not pushed",
     "does not name that cause"),
    ("the timeout die no longer says it timed out", "code",
     "timed out after ${GIT_TIMEOUT}s on '$1' — your commit",
     "failed on '$1' — your commit",
     "does not name that cause"),
    ("the peer's-file die no longer says what blocks the rebase", "code",
     "and a peer's uncommitted file blocks the rebase",
     "and the rebase is blocked",
     "does not name that cause"),
    ("a fourth die in a function no row documents", "code",
     'die "could not push origin/$BRANCH after 6 attempts" 6\n}\n',
     'die "could not push origin/$BRANCH after 6 attempts" 6\n}\n'
     + _a_fourth_die("the index is gone"),
     "none of the documented causes explains"),
    ("a fourth die whose message holds a command substitution", "code",
     'die "could not push origin/$BRANCH after 6 attempts" 6\n}\n',
     'die "could not push origin/$BRANCH after 6 attempts" 6\n}\n'
     + _a_fourth_die('$(describe "the index")'),
     "cannot read"),
    ("a fourth die in the push loop's success branch", "code",
     '      git_net push -q origin "$BRANCH" && return 0\n'
     '      [ "$GIT_TIMED_OUT" = 1 ] && git_timeout_die "git push origin $BRANCH"\n'
     '    else\n',
     '      git_net push -q origin "$BRANCH" && return 0\n'
     '      [ "$GIT_TIMED_OUT" = 1 ] && git_timeout_die "git push origin $BRANCH"\n'
     '      die "the push raced six times" 3\n'
     '    else\n',
     "does not name that cause"),
    ("the timeout die now exits 6, so no die reports a timeout", "code",
     "nothing was lost.\" 3\n}",
     "nothing was lost.\" 6\n}",
     "no `die … 3` reports a network timeout"),
    ("a call site names a network operation no row names", "code",
     'git_timeout_die "git pull --rebase origin $BRANCH"',
     'git_timeout_die "git fetch origin $BRANCH"',
     "never names a fetch"),
    ("a call site names no network operation at all", "code",
     'git_timeout_die "git pull --rebase origin $BRANCH"',
     'git_timeout_die "the network call"',
     "names no network operation"),
    ("a call hands git_timeout_die a bare operation word no row names", "code",
     'git_timeout_die "git pull --rebase origin $BRANCH"',
     'git_timeout_die fetch "the network call"',
     "never names a fetch"),
    ("a mention of git_timeout_die the reader cannot place as a call", "code",
     "  release_lock\n",
     "  release_lock\n  note \"git_timeout_die has released the lock\"\n",
     "cannot read as a call"),
    ("the table's row loses the timeout cause", "code",
     "#      a network timeout on a push OR a pull (a hung one often landed);\n",
     "#      a network failure on a push OR a pull (a hung one often landed);\n",
     "no longer names a network timeout"),
    ("the table's row loses the peer's-file cause", "code",
     "#      or six attempts exhausted because a peer's own uncommitted file blocks\n"
     "#      every rebase.\n",
     "#      or one more thing.\n",
     "no longer names six attempts blocked by a peer's uncommitted file"),
    ("the table's row loses the pull", "code",
     "a network timeout on a push OR a pull (a hung one often landed)",
     "a network timeout on a push (a hung one often landed)",
     "never names a pull"),
    ("the table's row loses its attempt-scoped wording", "code",
     "not pushed BY THIS ATTEMPT; look by content first",
     "look by content first",
     "lost the attempt-scoped wording"),
    ("the table's row says the edit did not reach origin", "code",
     "whether it also reached origin. THREE CAUSES:",
     "whether it also reached origin; if it did not reach origin, retry. THREE CAUSES:",
     "claims that nothing reached origin"),
    ("the table says nothing was pushed", "code",
     "#   0  done\n",
     "#   0  done, and on a refusal nothing was pushed\n",
     "still claims that nothing reached origin"),
    ("the manual's row says nothing was pushed", "manual",
     "cannot confirm whether it also reached origin",
     "cannot confirm — nothing was pushed",
     "claims that nothing reached origin"),
    ("the manual's row is gone", "manual",
     "| 3 | the edit",
     "| 13 | the edit",
     "has no exit-3 row"),
]

#: Each row is (why, where, old, new): a rewording that keeps the meaning, which
#: the rule must let through.
EXIT_3_ACCEPTED = [
    ("the timeout die is reworded and still says timeout", "code",
     "timed out after ${GIT_TIMEOUT}s on '$1' — your commit is local; nothing was lost.",
     "git hit its ${GIT_TIMEOUT}s timeout on '$1'; your commit is local and nothing was lost."),
    ("the peer's-file die says dirty and not uncommitted", "code",
     "a peer's uncommitted file blocks the rebase. Nothing was lost — your commit is local.",
     "another writer's dirty file blocks the rebase. Nothing was lost; your commit is still local."),
    ("the conflict die keeps its wording and moves its clauses", "code",
     "a later write from this checkout may already carry it, so look before you retry",
     "so look before you retry: a later write from this checkout may already carry it"),
    ("the function that holds the push loop is renamed", "code",
     "commit_push() {", "commit_publish() {"),
    ("a call hands git_timeout_die the operation as a bare word", "code",
     'git_timeout_die "git pull --rebase origin $BRANCH"',
     'git_timeout_die pull "the rebase on origin/$BRANCH"'),
    ("two spaces stand before the exit code", "code",
     "nothing was lost.\" 3\n}", "nothing was lost.\"  3\n}"),
    ("a comment trails the exit code", "code",
     "nothing was lost.\" 3\n}", "nothing was lost.\" 3   # the mutex is already released\n}"),
    ("the table wraps the attempt-scoped phrase onto a continuation line", "code",
     "not pushed BY THIS ATTEMPT;", "not pushed BY THIS\n#      ATTEMPT;"),
    ("the manual spells time-out and names each operation", "manual",
     "a network timeout on a push or a pull",
     "a network time-out on a push or on a pull"),
]


def _exit_3_fixture(where: str, old: str, new: str) -> tuple[str, str]:
    """`(code, manual)` of the fixture with `old` replaced by `new` in `where`."""
    code, manual = EXIT_3_SOURCE, EXIT_3_MANUAL
    target = code if where == "code" else manual
    assert target.count(old) == 1, (
        f"the fixture's {where} no longer holds exactly one {old!r}, so this "
        "case would pass or fail without testing what it names")
    target = target.replace(old, new)
    return (target, manual) if where == "code" else (code, target)


def test_the_exit_3_rule_is_green_on_the_fixture_it_is_mutated_from():
    assert _exit_3_findings(EXIT_3_SOURCE, EXIT_3_MANUAL) == []


@pytest.mark.parametrize("why,where,old,new,finding", EXIT_3_REFUSED,
                         ids=[row[0] for row in EXIT_3_REFUSED])
def test_the_exit_3_rule_is_red_on_a_die_or_a_row_that_disagrees(
        why, where, old, new, finding):
    """RED: each case plants one disagreement in the fixture — a die that
    claims nothing reached origin, a die or a row that lost its cause, a
    fourth die no row documents — and the rule must name it, in words that
    say WHICH check refused. A case that passed for the wrong reason would
    teach nothing: the last column is what the findings must hold."""
    code, manual = _exit_3_fixture(where, old, new)
    findings = _exit_3_findings(code, manual)
    assert any(finding in each for each in findings), (
        f"the exit-3 rule did not refuse ({why}) in the words {finding!r}; "
        f"it said: {findings}")


@pytest.mark.parametrize("why,where,old,new", EXIT_3_ACCEPTED,
                         ids=[row[0] for row in EXIT_3_ACCEPTED])
def test_the_exit_3_rule_is_green_on_a_rewording_that_keeps_the_meaning(
        why, where, old, new):
    """GREEN: #68 item 3 and the act 2 `commit_publish` will reword these
    messages, so a rule anchored to the words of one would fail on the first
    change that is only a change of words. The die is tied to its cause by
    where it sits, and the rows by what they name."""
    code, manual = _exit_3_fixture(where, old, new)
    assert _exit_3_findings(code, manual) == [], (
        f"the exit-3 rule refused a rewording that keeps the meaning ({why})")


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
    offenders = {}
    cited = 0
    for rel, path in tracked_files():
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
#: the SessionStart hook, `live-holder`, `lanes`, `lane` — which shows it where
#: a person is CHOOSING what to bind, and which is where `restart`'s listing
#: went under Amendment 18 Addendum 2 — and the `/restart` skill; and
#: `lane-end`, which A11 Addendum 4 ruling 8 makes the DOOR and which must
#: therefore hold to the same rule as the surfaces that print it.
FORK_SURFACES = ("lanes-edit.sh", "lanes", "lane", "skills/restart/SKILL.md",
                 "lane-end")
#: A line that offers an act for a fork says `FORK` or `fork(s)` and an
#: imperative beside it. Matched on the two spellings the surfaces use.
FORK_ACT_LINE = re.compile(r"^.*(?:live FORK|live fork\(s\)).*$", re.M)


#: The two halves of the `/lane-swap` skill that must spell the launch the same
#: way: the `restart_cmd=` the skill EXECUTES into its printed line, and the
#: prose three paragraphs below that explains it.
#: THE SKILL THAT CARRIES THE ACT, READ OUT OF THE INSTALLER'S OWN
#: `SKILL_NAME` rather than spelled here. Amendment 17(a) renamed the act from
#: `lane-swap` to `handoff` and left an ALIAS FILE at the old path — one that
#: restates no step, by the rule `tests/test_install_skill_and_hook.py` holds —
#: so a constant spelled here went on reading a file with nothing in it to
#: check, and every assertion below passed on an emptiness. The installer
#: declares the canonical name once; this follows it, and the next rename moves
#: both together.
def _canonical_skill_path() -> str:
    text = (REPO / "openRepoTools").read_text(encoding="utf-8")
    match = re.search(r'^SKILL_NAME="([A-Za-z0-9._-]+)"$', text, re.MULTILINE)
    assert match, "openRepoTools no longer declares `SKILL_NAME=\"…\"`"
    return f"skills/{match.group(1)}/SKILL.md"


SWAP_SKILL = _canonical_skill_path()


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
    act clause (k) rule (e) refuses BY NAME while the surfaces beside it
    had all been corrected (F-X8).

    So the manual is read as PARAGRAPHS: any paragraph that speaks of a fork
    and offers a `kill` must name `--retire`. The idle holders of a lane are a
    different population - Amendment 6(d)'s orphans, which `lane-end --retire`
    refuses because they are not forks - and their `kill` lines are untouched
    here for the same reason the test above leaves them alone.
    """
    text = doc("docs/README-lanes.md").read_text(encoding="utf-8")
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

    EVERY REPOSITORY THIS RUN CAN READ (#186, T009): the composed run scans the
    assembly and the spec leg beside the code leg, which is every file the one
    repository carried before the split. Their gitlinks are paths and not files,
    like the one above.

    THE BENCH ROOT IS A HOST PATH TOO (opensoft/openRepoTools#193, item 22):
    `host_absolute_path_hits` reads it beside the home-directory forms, with
    one allowance, a path inside a quoted `grep` search pattern. The tests
    after this one hold both halves of that rule, red and green.
    """
    offenders = {}
    for rel, path in tracked_files():
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        hits = host_absolute_path_hits(text)
        if hits:
            # FIVE PER FILE: a file with eighty-six findings should say so, not
            # print them all into one assertion.
            offenders[rel] = (hits if len(hits) <= 5
                              else hits[:5] + [f"... and {len(hits) - 5} more"])
    assert not offenders, (
        f"committed file(s) name a host-absolute path: {offenders}")


def _plant(template: str) -> str:
    """`template` with `<root>` replaced by the bench root. The rule's own
    constant fills it, so this file never spells the root contiguously and the
    scan above has nothing of its own to find."""
    return template.replace("<root>", _BENCH_ROOT)


#: TEXT THE BENCH-ROOT RULE MUST REFUSE. Each row is (why, text).
BENCH_PATH_REFUSED = [
    ("a path as a command's operand",
     "cat <root>projects/x/file"),
    ("a path in a yaml value, the shape of the ideation sample",
     "directory: <root>projects/openRepoTools"),
    ("a path in prose and in a table cell",
     "| `<root>projects/openRepoTools/handoffs` | the checkout's symlink |"),
    ("a path as `git -C` argument, though the same line quotes a pattern",
     "git -C <root>projects/x grep -n -e '<root>projects/y' HEAD -- ."),
    ("a quoted path that is not a search pattern",
     "ls '<root>projects/x'"),
    ("a second quoted operand of grep, which is a file",
     "grep -n 'x' '<root>projects/x/file'"),
    ("a path after the pattern, which is the file searched",
     "grep -n '<root>projects/x' <root>projects/y"),
    ("a double-quoted pattern, which can hold a variable",
     'grep -E "<root>projects/x" file'),
    ("a flag that takes a value ends the run of flags",
     "grep -m 1 '<root>projects/x' file"),
    ("-f names a pattern FILE, which is a path and not a pattern",
     "grep -f '<root>projects/pat.txt' log"),
    ("-f under git grep names a pattern file too",
     "git grep -f '<root>projects/pat.txt' HEAD"),
    ("-f inside a flag bundle is still -f",
     "grep -rf '<root>projects/pat.txt' ."),
    ("-f ahead of an -e chain licenses nothing in it",
     "grep -f '<root>projects/pat.txt' -e 'x' -e 'y' log"),
    ("a path glued onto the closing quote of a pattern",
     "grep -E 'x'<root>projects/y log"),
    ("a quoted path piped INTO a grep is still an echoed path",
     "echo '<root>projects/x' | grep -n 'y'"),
    ("a grep on one line licenses nothing on the next",
     "grep -n\n'<root>projects/x' file"),
    ("a file:// URL names the same host path",
     "file://<root>projects/x"),
]

#: TEXT IT MUST ACCEPT. The first five are the allowance, each in one of the
#: shapes a recorded search takes; the rest are look-alikes that are not the
#: bench's root at all.
BENCH_PATH_ACCEPTED = [
    ("grep -E with a quoted pattern",
     "grep -E '<root>projects/x' file"),
    ("grep -rn with an anchored pattern and a placeholder for the files",
     "grep -rn '^path: <root>projects/openRepoTools/' $LS/openRepoTools-{1,2,3} | wc -l"),
    ("git grep with several -e patterns and a placeholder for the checkout",
     "git -C $WB grep -n -e '<root>projects/openRepoTools' "
     "-e 'openRepoTools-worktrees' -e '\\.lane-worktrees' HEAD -- ."),
    ("a later -e carries the path",
     "grep -n -e 'a' -e '<root>projects/x' file"),
    ("a pattern after a pipe",
     "git show HEAD:x | grep -n '<root>projects/x'"),
    ("a placeholder is not a path",
     "git -C $ORT rev-parse HEAD"),
    ("a path under the home directory, by tilde, $HOME and ${HOME}",
     "~<root>x $HOME<root>x ${HOME}<root>x"),
    ("a relative directory that happens to carry the root's name",
     "templates<root>x ..<root>x .<root>x"),
    ("the workspace record and a template directory are not the root",
     "~/.agents/workspace.yaml and templates/workspace-root/ and workspace/"),
]


@pytest.mark.parametrize("why,template", BENCH_PATH_REFUSED,
                         ids=[why for why, _ in BENCH_PATH_REFUSED])
def test_the_bench_root_rule_is_red_on_a_planted_path(why, template):
    """RED: a path at the bench's root is a finding wherever it stands, except
    inside a quoted search pattern. Every row plants one in a place the
    allowance must NOT reach, and `git -C <path> grep -e '<path>'` is the row
    that matters most: the first path is as host-absolute as ever, and the
    pattern beside it licenses nothing."""
    hits = host_absolute_path_hits(_plant(template))
    assert hits, f"the rule let this through ({why}): {_plant(template)!r}"


@pytest.mark.parametrize("why,template", BENCH_PATH_ACCEPTED,
                         ids=[why for why, _ in BENCH_PATH_ACCEPTED])
def test_the_bench_root_rule_is_green_on_the_allowed_forms(why, template):
    """GREEN: a path inside a quoted search pattern is the recorded command's
    own text and stays; so does everything that merely resembles the root."""
    text = _plant(template)
    assert host_absolute_path_hits(text) == [], (
        f"the rule refused this ({why}): {text!r}")


def test_the_quoted_pattern_allowance_scrubs_the_pattern_and_nothing_beside_it():
    """One line, two roots: the allowance takes the quoted pattern out of the
    line and the other path stays a finding, reported by line number."""
    line = _plant("git -C <root>projects/x grep -n -e '<root>projects/y' HEAD")
    hits = host_absolute_path_hits("fine\n" + line + "\nalso fine\n")
    assert len(hits) == 1 and hits[0].startswith("line 2: git -C "), hits


def test_the_consumer_reads_search_lines_are_red_as_main_carried_them_and_green_fixed():
    """The three recorded searches of `consumer-reads-2026-10-07.md` (lines 94,
    132 and 142 on main), each as #189 landed it and as it reads once the root
    BESIDE the pattern is a placeholder. The pattern itself is byte for byte
    the same in both, which is the whole claim: a placeholder in it would have
    changed what the command searched for."""
    pairs = [
        ("git -C <root>projects/workBenches grep -n -e '<root>projects/openRepoTools'"
         " -e 'openRepoTools-worktrees' -e '\\.lane-worktrees' HEAD -- .",
         "git -C $WB grep -n -e '<root>projects/openRepoTools'"
         " -e 'openRepoTools-worktrees' -e '\\.lane-worktrees' HEAD -- ."),
        ("git -C <root>projects/brett-wip grep -n -e '<root>projects/openRepoTools'"
         " -e '~/projects/openRepoTools' ab88a10 -- .   # 341 lines",
         "git -C $BW grep -n -e '<root>projects/openRepoTools'"
         " -e '~/projects/openRepoTools' ab88a10 -- .   # 341 lines"),
        ("grep -rn '^path: <root>projects/openRepoTools/'"
         " <root>projects/.lane-state/openRepoTools-{1,2,3} | wc -l",
         "grep -rn '^path: <root>projects/openRepoTools/'"
         " $LS/openRepoTools-{1,2,3} | wc -l"),
    ]
    for before, after in pairs:
        assert host_absolute_path_hits(_plant(before)), _plant(before)
        assert host_absolute_path_hits(_plant(after)) == [], _plant(after)


def test_the_bench_rule_leaves_the_home_directory_rule_as_it_was():
    """The bench root is a second pattern beside the first, not an edit of it:
    the home-directory forms are still found, and the Windows runner's own
    account is still the one exemption."""
    unix = "/home" + "/alice/"
    mac = "/Users" + "/Bob/"
    assert host_absolute_path_hits(unix + "x") == [unix]
    assert host_absolute_path_hits(mac + "x") == [mac]
    assert host_absolute_path_hits("C:" + "\\Users\\runneradmin\\x") == []


def test_the_root_carries_the_line_ending_rule():
    """`* text=auto eol=lf`, for openRepoShape's reason retold for this
    repository: `openRepoTools --install` compares the bytes it is about to
    place against the bytes already there with `cmp`, and its own tests compare
    an installed copy to this checkout's file byte for byte. Git for Windows'
    installer default is `core.autocrlf=true`; a checkout made under it turns
    every `\\n` in the shipped bash files into `\\r\\n`, and the comparison is
    then about line endings rather than about content. The rule normalises text
    to LF in the object store on check-in and checks it out as LF on every
    platform, whatever `core.autocrlf` says — so nobody has to be told a git
    setting before cloning, and nobody who was never told is punished for it.

    THE CODE ROOT'S, IN EVERY LAYOUT (#186, T009). The adoption mapping places
    `.gitattributes` at the assembly, but git reads a submodule's attributes
    from the submodule's own tree: the assembly's copy protects no byte of the
    code leg. So this reads the file beside the bash files, and a code leg that
    has none is red here until it carries its own.
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


def package_modules() -> list:
    """Every `.py` file under `src/openrepotools/`, the code root's own: the
    modules the `openrepotools` wheel ships (opensoft/openRepoTools#228). A
    subdirectory is searched too, so a module cannot hide one level down, and
    an empty answer is a failure rather than a pass with nothing read."""
    modules = sorted((REPO / "src" / "openrepotools").rglob("*.py"))
    assert modules, "no module under src/openrepotools/: package missing"
    return modules


#: THE MODULES THE PACKAGE MAY IMPORT, AND WHY (FR-005, opensoft/openRepoTools
#: #228), by top-level name. This is the allowlist, and it is explicit rather
#: than "whatever `sys.stdlib_module_names` holds": it admits exactly what the
#: entry module needs, which design.md Decision 3 spells out — `cli.main()` is
#: `os.execvp("bash", ["bash", <payload>/openRepoTools, *sys.argv[1:]])`, with
#: SIGPIPE and SIGXFSZ set back to `SIG_DFL` first (the lead's amendment of
#: 2026-10-18), and, on `FileNotFoundError` or `NotADirectoryError`, a refusal
#: on stderr and exit 2. `__init__.py` holds a docstring and `_release.py` the
#: five stamp lines, so neither imports anything. Nothing else is here on
#: purpose: `pathlib`, `subprocess`, `importlib` and the package's own name
#: are all absent, because the entry module reads no stamp, runs no child and
#: passes bash nothing but the person's arguments; `__future__` is absent
#: because nothing in Decision 3's module needs an annotation postponed on
#: Python 3.9. A module that needs another name takes an edit here, with its
#: reason beside it.
PACKAGE_IMPORT_ALLOWLIST = {
    "os": ("os.execvp replaces the process with the first bash on PATH, so "
           "signals, the EXIT trap and the exit status pass through; the "
           "payload directory beside the module's own file is found from "
           "its __file__ with os.path"),
    "signal": ("Python starts with SIGPIPE and SIGXFSZ ignored, an exec keeps "
               "an ignored disposition, and a non-interactive bash cannot "
               "reset one ignored on entry, so signal.signal sets both back "
               "to SIG_DFL just before the exec, as subprocess's "
               "restore_signals does (design.md Decision 3, amended "
               "2026-10-18; FR-003)"),
    "sys": ("sys.argv[1:] is the person's arguments, passed on unchanged; "
            "sys.stderr carries the no-bash refusal that precedes its "
            "exit 2"),
}


def test_the_package_imports_only_the_standard_library():
    """FR-005: the `openrepotools` wheel declares `dependencies = []`, so a
    module under `src/openrepotools/` that imports a third-party name is a
    console script that dies with `ModuleNotFoundError` on a clean pipx
    install, before anything of ours can say why.

    The rule is the allowlist above, held to the syntax tree: every `import`
    and `from … import` at ANY depth of every module (`ast.walk`, so one inside
    a function or a `try` counts), by the top-level name, with a relative
    import refused as a name of its own. `__import__()` is refused too, since
    it names a module the tree walk would never see. Where this Python has
    `sys.stdlib_module_names` (3.10 and up), the allowlist itself must be
    standard-library names, so nobody makes the rule pass by adding `yaml` to
    it. On 3.9, which the package supports and has no such set, that one check
    is not made and NOTHING SKIPS: the explicit allowlist alone decides.
    """
    stdlib = getattr(sys, "stdlib_module_names", None)
    if stdlib is not None:
        outside = sorted(set(PACKAGE_IMPORT_ALLOWLIST) - set(stdlib))
        assert not outside, (
            "PACKAGE_IMPORT_ALLOWLIST holds names that are not in the "
            "standard library of this Python (sys.stdlib_module_names): "
            + ", ".join(outside))
    problems = []
    for path in package_modules():
        label = path.relative_to(REPO).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=label)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = ["." * node.level + (node.module or "")]
            elif (isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name)
                  and node.func.id == "__import__"):
                problems.append(
                    f"{label}:{node.lineno}: __import__() loads a module by "
                    "a name this rule cannot read; write an import")
            for name in names:
                top = name.split(".")[0]
                if top not in PACKAGE_IMPORT_ALLOWLIST:
                    note = " (a relative import)" if top == "" else ""
                    problems.append(
                        f"{label}:{node.lineno}: imports {name!r}{note}, "
                        "which is not on PACKAGE_IMPORT_ALLOWLIST (allowed: "
                        + ", ".join(sorted(PACKAGE_IMPORT_ALLOWLIST)) + ")")
    assert not problems, (
        "the package's modules may import only the standard library "
        "(FR-005, dependencies = []):\n    " + "\n    ".join(problems))


def test_the_python_files_compile():
    """The suite is the Python here, bar two shipped commands and the package's
    modules named below, and a file that does not parse is a file that fails as
    a collection ERROR rather than as a test — which reads as the suite being
    broken instead of as one file being wrong.

    `compile()` rather than `py_compile`: nothing is written anywhere, so this
    runs in a read-only checkout and leaves no `__pycache__` behind.

    opensoft/openRepoTools#160: `lanes-index` is a shipped command that is
    Python, and it has no `.py` suffix for the glob below to find, so its
    text is compiled the same way — a syntax error there is a command that
    fails on every workstation's first sync. opensoft/openRepoTools#162 put
    `lane-worktrees` beside it, for the same reason.

    opensoft/openRepoTools#228: `src/openrepotools/*.py` is the `openrepotools`
    package, which the wheel ships and whose console script runs on every
    pipx install, so a syntax error in one of its modules is a command that
    fails on every workstation the release reaches. `package_modules()` is the
    set the standard-library rule above reads, so the two cover the same files.
    """
    for path in sorted((REPO / "tests").glob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    for path in package_modules():
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    for name in ("lanes-index", "lane-worktrees"):
        command = REPO / name
        compile(command.read_text(encoding="utf-8"), str(command), "exec")


# --- the macOS job RUNS this bash, it does not only parse it (R-A9-11) ------

#: Which options of which utility take a SEPARATE argument. Everything after
#: the first token that is neither an option nor an option's argument is an
#: OPERAND, and an operand is where BSD's `getopt` stops looking for options.
_OPTIONS_WITH_ARGUMENTS = {
    "sed": {"-e", "-f", "-i", "-l"},
    "grep": {"-e", "-f", "-m", "-A", "-B", "-C", "--include", "--exclude"},
    "awk": {"-v", "-f"},
}


#: THE TOKENS THAT END ONE COMMAND ON A LINE AND BEGIN THE NEXT, as
#: `_shell_tokens` hands them back: each is a token of its own, cut out of
#: the line only where the shell reads it as syntax, and never out of a
#: quoted run.
_COMMAND_SEPARATORS = frozenset({"|", ";", "&", "(", ")", "$(", "`"})


def _shell_tokens(text: str, opened: str = "") -> tuple[list[str], bool]:
    """Split one line of shell into tokens, keeping a quoted run together and
    handing every command separator back as a token of its own. Returns the
    tokens, and whether the line ENDS inside a quoted run.

    Deliberately small: it expands nothing and does not care what a token
    MEANS. All it has to answer is "is this token exactly `--`, did an operand
    come before it, and was that in the same command".

    `opened` starts the line inside a quoted run of that kind, `'` or `"`: the
    second reading `_commands_on` gives a line that may close a quote an
    earlier line opened.

    THE LINE IS TOKENIZED BEFORE IT IS CUT, AND NOT THE OTHER WAY ROUND
    (opensoft/openRepoTools#54). The cut used to be a bare regular-expression
    split of the raw text at every `|`, `;`, `&`, `(`, `)`, `$(` and backtick,
    and a pattern is text. `grep -v 'not fetching; reading origin/' -- "$f"`
    came apart at the `;` inside its own quotes, neither half held both the
    operand and the `--` after it, and the check called a real BSD failure
    clean — in a shipped command, the same line #53 had just fixed in a skill.
    A quoted message that happened to hold `; grep x -- y` was the same cut
    the other way: a finding in a string nothing runs.

    So a separator is one only OUTSIDE a quoted run, and only where the shell
    reads it as one: `|`, `;`, `&`, `(` and `)` outside every quote, and the
    two that open a nested command, `$(` and a backtick, inside a
    double-quoted run as well — `out="$(sed -n 'p' -- "$f")"` is a command
    inside an assignment, and its quotes start afresh, so the `$(` and the
    `)` that closes it are tracked to know where the outer double quote
    resumes. A single-quoted run holds no syntax at all, and a backslash makes
    the next character plain text either way.
    """
    tokens: list[str] = []
    current: list[str] = []
    started = False
    # What encloses the character being read, innermost last: "'" or '"' for a
    # quoted run, "$(", "(" or "`" for a command nested inside the line.
    stack: list[str] = [opened] if opened else []

    def end_token() -> None:
        nonlocal current, started
        if started:
            tokens.append("".join(current))
        current, started = [], False

    index = 0
    while index < len(text):
        ch = text[index]
        inside = stack[-1] if stack else ""
        step = 1
        if inside == "'":
            current.append(ch)
            if ch == "'":
                stack.pop()
        elif ch == "\\":
            current.append(text[index:index + 2])
            started, step = True, 2
        elif inside == '"' and ch == '"':
            current.append(ch)
            stack.pop()
        elif ch == "`" and inside == "`":
            end_token()
            tokens.append(ch)
            stack.pop()
        elif ch == "`" or text.startswith("$(", index):
            opener = "`" if ch == "`" else "$("
            end_token()
            tokens.append(opener)
            stack.append(opener)
            step = len(opener)
        elif inside == '"':
            current.append(ch)
        elif ch in "'\"":
            stack.append(ch)
            current.append(ch)
            started = True
        elif ch.isspace():
            end_token()
        elif ch == "(":
            end_token()
            tokens.append(ch)
            stack.append(ch)
        elif ch == ")":
            end_token()
            tokens.append(ch)
            if inside in ("$(", "("):
                stack.pop()
        elif ch in "|;&":
            end_token()
            tokens.append(ch)
        else:
            started = True
            current.append(ch)
        index += step
    end_token()
    return tokens, bool(stack) and stack[-1] in ("'", '"')


def _commands_on(line: str) -> list[list[str]]:
    """The tokens of `line`, cut into one list per command at every separator
    token — so a quoted pattern stays whole in the command that passes it.

    A QUOTE CAN SPAN LINES, AND THIS READS ONE LINE AT A TIME. A line that
    ends inside a quoted run is the first line of such a quote or its last,
    and the line alone cannot say which. Read from outside every quote, a LAST
    line's closing quote opens one instead, and the command after it goes into
    a single token — `}' | LC_ALL=C sort | awk -v s="$US" '{ … }')"`, the
    tail of a multi-line awk program in `lanes-edit.sh`, would lose its second
    `awk` that way. So such a line is read again from inside a single-quoted
    run and from inside a double-quoted one, and the commands of every reading
    are checked; a line that closes every quote it opens is read once.
    """
    def cut(tokens: list[str]) -> list[list[str]]:
        commands: list[list[str]] = [[]]
        for token in tokens:
            if token in _COMMAND_SEPARATORS:
                commands.append([])
            else:
                commands[-1].append(token)
        return commands

    tokens, ends_quoted = _shell_tokens(line)
    commands = cut(tokens)
    if ends_quoted:
        for quote in ("'", '"'):
            commands += [command
                         for command in cut(_shell_tokens(line, quote)[0])
                         if command not in commands]
    return commands


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
        for tokens in _commands_on(line):
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


#: LINES THE END-OF-OPTIONS RULE MUST REFUSE, each with a separator inside a
#: quoted run (opensoft/openRepoTools#54). The cut over the raw text took
#: every one of them apart at that separator and called it clean. Each row is
#: (why, line).
LATE_END_OF_OPTIONS_REFUSED = [
    ("#54's own line, a semicolon inside the pattern",
     "grep -v 'not fetching; reading origin/' -- \"$local_err_file\" >&2 || :"),
    ("a pipe inside an alternation",
     "grep -E 'PARKED|RESUMED' -- \"$log\""),
    ("an ampersand inside a sed replacement",
     "sed -n 's/^lane: /[&]/p' -- \"$file\""),
    ("parentheses inside a double-quoted pattern",
     'grep -n "^cut_to_line()" -- "$f"'),
    ("a semicolon inside an awk program",
     "awk '{ n++; print n }' -- \"$f\""),
    ("a backtick inside a single-quoted pattern",
     "grep -F 'run `lane`' -- \"$f\""),
    ("a nested command inside double quotes, its pattern quoted afresh",
     "out=\"$(grep 'a;b' -- \"$f\")\""),
    ("the last line of a multi-line awk program, then a second call",
     "}' | LC_ALL=C sort | awk '{ print; }' -- \"$f\")\""),
]

#: LINES IT MUST ACCEPT: a separator inside a quoted run that the raw cut
#: turned into a call nothing makes. Each row is (why, line).
LATE_END_OF_OPTIONS_ACCEPTED = [
    ("a message that quotes the shape, after a semicolon",
     "note \"the stderr filter is gone; grep 'pattern' -- file was its shape\""),
    ("a single-quoted command line, after a double ampersand",
     "printf '%s\\n' 'cd \"$dir\" && grep pattern -- file'"),
    ("a single-quoted usage line, after a pipe",
     "usage='lanes | grep \"x\" -- file'"),
    ("parentheses inside a double-quoted message",
     "echo \"(sed 's/x/y/' -- f)\""),
    ("backticks inside a single-quoted message",
     "printf '%s\\n' 'run `sed s/a/b/ -- f` by hand'"),
    ("a correct call whose -e pattern holds a semicolon and a call",
     "grep -v -e 'x; sed s/a/b/ -- y' -- \"$f\""),
]


@pytest.mark.parametrize("why,line", LATE_END_OF_OPTIONS_REFUSED,
                         ids=[why for why, _ in LATE_END_OF_OPTIONS_REFUSED])
def test_the_end_of_options_rule_sees_a_call_whose_quotes_hold_a_separator(
        why, line):
    """RED: a quoted pattern, program or nested command keeps its separators
    to itself (opensoft/openRepoTools#54). `lanes` shipped the first row's
    line while this rule called it clean — the `;` inside the pattern cut the
    call in two before the tokenizer saw its `--` — so every row here is one
    the raw-text cut let through, and the line is tokenized before it is cut.
    """
    assert _end_of_options_after_an_operand(line), (
        f"the rule let this through ({why}): {line!r}")


@pytest.mark.parametrize("why,line", LATE_END_OF_OPTIONS_ACCEPTED,
                         ids=[why for why, _ in LATE_END_OF_OPTIONS_ACCEPTED])
def test_the_end_of_options_rule_finds_no_call_inside_a_quoted_string(
        why, line):
    """GREEN: text inside quotes is a string, not a command, whatever
    separators it holds. The raw-text cut began a new command at each of them,
    so the words after one read as a call with its `--` too late — a finding
    in a line nothing runs, which teaches a reader to stop trusting the rule.
    """
    assert _end_of_options_after_an_operand(line) == [], (
        f"the rule refused this ({why}): {line!r}")


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
    rather than a parse gate: every file in `ALL_BASH` already passes `bash -n`
    under the Linux bash CI runs, and bash 3.2 is the only place the defect
    exists. The fix is one line each time - hoist the `case` above the
    assertion and read the variable it sets - so the rule is held for every
    bash file this repository ships rather than for the two that were found.

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


def test_the_suite_wrapper_takes_one_lock_and_names_it_where_agents_read_it():
    """ONE SUITE AT A TIME WHERE LANES SHARE A WORKSTATION, and the lock has to
    be the SAME lock in every lane or there is no lock at all
    (opensoft/openRepoTools#51, measured 2026-09-14T20:4xZ on Eagle).

    Four `python3 -m pytest tests -q` runs were live at once in four worktrees,
    every one of them past a guard that had been copied into four briefs:

        while pgrep -af 'python3 -m pytest' | grep -v pgrep >/dev/null; do sleep 20; done

    It never waited. Under the harness `grep` is a shell FUNCTION, and its
    status with stdout on `/dev/null` is 1 even where it matched — the same
    pipeline captured into a variable returned 0 and six lines. The collision
    is not a shared path (the suite redirects `$HOME` and `$TMPDIR`); it is
    TIME: a suite that takes 18 minutes alone takes far longer four-wide and
    trips every wrapper's timeout around it.

    So the guard is written once, in `tests/run.sh`, and three things about it
    are held here rather than trusted, because each has already been got wrong:

      * THE LOCK PATH IS THE ESTATE'S, spelled the same in the wrapper and in
        `AGENTS.md`. A lane that locks a different file locks nothing.
      * THE PATTERN IS ANCHORED AND SPLIT, so it counts real runs and cannot
        match the guard's own command line.
      * `AGENTS.md` NAMES THE WRAPPER as the way to run the suite, because a
        document that only shows `python3 -m pytest` is the document all four
        of those runs were following.
    """
    wrapper = REPO / "tests" / "run.sh"
    assert wrapper.is_file(), "tests/run.sh is the way this suite is run"
    text = wrapper.read_text(encoding="utf-8")
    lock = '${TMPDIR:-/tmp}/openrepotools-pytest.lock'
    assert lock in text, f"the wrapper must take {lock}"

    assert "'^python3 -m pyt'" in text, (
        "the pgrep pattern must be anchored and split so it cannot match its "
        "own command line")
    # THE BROKEN FORM MAY BE QUOTED AND MUST NOT BE RUN. It is in the
    # wrapper's own head as the defect being corrected, which is worth
    # keeping: an assistant that has met the working guard still meets the
    # old one in older briefs. So the rule is asked of the CODE lines only.
    code = [ln for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    assert not any("| grep -v pgrep" in ln for ln in code), (
        "that guard never waits where `grep` is a shell function whose status "
        "is 1 with stdout on /dev/null — which is the harness every lane runs in")

    assert "flock" in text and "mkdir " in text, (
        "macOS ships no `flock`, so the wrapper needs the `mkdir` lock as its "
        "fallback — that platform is the one the fallback exists for")
    assert "python3 -m pytest tests -q" in text

    # AND THEN WHERE AGENTS READ IT — AGENTS.md is the assembly root's in the
    # triad (#186, T009), so the wrapper's own half is asserted above first.
    agents = doc("AGENTS.md").read_text(encoding="utf-8")
    assert lock in agents, (
        f"AGENTS.md must name {lock}: every lane on one workstation locks the "
        "same file or there is no lock")
    assert "tests/run.sh" in agents, (
        "AGENTS.md must name tests/run.sh as the way to run the suite")
    # THE BY-HAND FORM LEAVES NOTHING EITHER (#170 E9): the one line a person
    # with no checkout runs relocates bytecode and turns pytest's cache off, as
    # the wrapper does, or it lands `__pycache__` and `.pytest_cache` beside
    # the code the wrapper keeps clean.
    by_hand = [ln for ln in agents.splitlines() if lock in ln and "python3 -m pytest" in ln]
    assert by_hand and all("-p no:cacheprovider" in ln and "PYTHONPYCACHEPREFIX=" in ln
                           for ln in by_hand), by_hand


# --- #58: NO PROSE SPELLS A COUNT OF AN INVENTORY ITS OWN FILE DEFINES --------

_COUNT_WORDS = tuple(
    "two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())
_COUNT_VALUE = {word: number for number, word in enumerate(_COUNT_WORDS, start=2)}
#: A number word on its own: `thirty-two` and `three-wide` are not one.
_COUNT_WORD = re.compile(
    r"(?<![\w-])(" + "|".join(_COUNT_WORDS) + r")(?![\w-])", re.IGNORECASE)

#: Words that end a noun group, so a noun followed by one of them is the group's
#: head. A noun followed by anything else is a modifier of what comes next.
_FUNCTION_WORDS = frozenset(
    "and or of in inside into on at to from by with without for than is are "
    "was were be been that which who whose where when while as not but it its "
    "they them their an a the this these those each every all both also only "
    "now then still can could will would should must may might has have had "
    "do does did per beside across here there".split())
_DETERMINERS = frozenset(
    "the a an every each all these those this that its their our any some "
    "only".split())
#: Where the first noun phrase of an inventory's own comment ends.
_LEAD_ENDS = frozenset(
    "that which this these those for in into of under from on at with and by "
    "as is are was were to also joins carries holds".split())

_Inventory = namedtuple("_Inventory", "name items line nouns vocab")
_SpelledCount = namedtuple(
    "_SpelledCount", "line number phrase context inventories")


def _singular(word: str) -> str:
    word = word.lower().strip("`'")
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _comment_above(lines: list, number: int) -> list:
    """The unbroken run of `#` lines directly above 1-based line `number`."""
    block = []
    index = number - 2
    while index >= 0 and lines[index].lstrip().startswith("#"):
        block.insert(0, re.sub(r"^\s*#:?\s?", "", lines[index]))
        index -= 1
    return block


def _inventory_words(name: str, comment: list) -> tuple:
    """(item nouns, the inventory's own words): the last word of its NAME and
    the head of the first noun phrase of the comment above it, which is the
    last word before a code span, a relative word, a preposition or any
    punctuation: `EVERY BASH FILE THIS REPOSITORY SHIPS` gives `file`."""
    tokens = [_singular(token) for token in name.strip("_").split("_") if token]
    phrase = re.split(
        r"[.,:;()—`]", " ".join(comment).strip(), maxsplit=1)[0]
    lead = []
    for word in re.findall(r"[A-Za-z][A-Za-z'-]*", phrase):
        lowered = word.lower()
        if lowered in _DETERMINERS and not lead:
            continue
        if lowered in _LEAD_ENDS or lowered in _DETERMINERS:
            break
        if lowered in _COUNT_VALUE or lowered == "one":
            continue
        lead.append(_singular(word))
    nouns = {tokens[-1]} | ({lead[-1]} if lead else set())
    return nouns, set(tokens) | set(lead)


_NAME_ITEM = re.compile(r"[\w./:@-]+")


def _python_inventories(tree: ast.Module, lines: list) -> dict:
    found = {}

    def items_of(node):
        if isinstance(node, (ast.List, ast.Tuple)):
            items = [element.value for element in node.elts
                     if isinstance(element, ast.Constant)
                     and isinstance(element.value, str)
                     and _NAME_ITEM.fullmatch(element.value)]
            return items if len(items) == len(node.elts) >= 2 else None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = items_of(node.left), items_of(node.right)
            return None if left is None or right is None else left + right
        if isinstance(node, ast.Name) and node.id in found:
            return found[node.id].items
        return None

    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            target = statement.target
        else:
            continue
        items = items_of(statement.value) if isinstance(target, ast.Name) else None
        if items is not None:
            nouns, vocab = _inventory_words(
                target.id, _comment_above(lines, statement.lineno))
            found[target.id] = _Inventory(
                target.id, items, statement.lineno, nouns, vocab)
    return found


_BASH_ARRAY = re.compile(
    r"^\s*(?:local\s+|declare\s+(?:-\w+\s+)?|readonly\s+)?"
    r"([A-Z][A-Z0-9_]*)=\((.*)$")
_COMMAND_LINE_NAME = re.compile(r"_(?:ARGS|ARGV|CALL|CMD)$")
_BASH_ITEM = re.compile(r"\"[^\"]*\"|'[^']*'|[^\s\"']+")
_HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _without_comment(line: str) -> str:
    return re.sub(r"(^|\s)#.*$", r"\1", line)


def _bash_heredoc_lines(lines: list) -> set:
    """The 1-based numbers of the lines inside a here-document: text a command
    reads, so neither prose nor an array."""
    inside, terminator = set(), None
    for number, line in enumerate(lines, start=1):
        if terminator is not None:
            inside.add(number)
            if line.strip() == terminator:
                terminator = None
        elif not line.lstrip().startswith("#"):
            opener = _HEREDOC.search(line)
            if opener:
                terminator = opener.group(2)
    return inside


def _bash_inventories(lines: list, heredocs: set) -> dict:
    found, index = {}, 0
    while index < len(lines):
        match = _BASH_ARRAY.match(lines[index])
        if (not match or lines[index].lstrip().startswith("#")
                or index + 1 in heredocs):
            index += 1
            continue
        name, body, end = match.group(1), _without_comment(match.group(2)), index
        while ")" not in body and end + 1 < len(lines):
            end += 1
            body += " " + _without_comment(lines[end])
        body = body.split(")")[0]
        if (not any(char in body for char in "$`(")
                and not _COMMAND_LINE_NAME.search(name)):
            items = [item.strip("\"'") for item in _BASH_ITEM.findall(body)]
            if len(items) >= 2:
                nouns, vocab = _inventory_words(
                    name, _comment_above(lines, index + 1))
                found[name] = _Inventory(name, items, index + 1, nouns, vocab)
        index = end + 1
    return found


def _python_prose(source: str, tree: ast.Module) -> dict:
    """{line: text} for every comment and every docstring line."""
    lines = source.splitlines()
    prose = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            prose[token.start[0]] = token.string
    for node in ast.walk(tree):
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)) and node.body):
            first = node.body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                for number in range(first.lineno, first.end_lineno + 1):
                    prose[number] = lines[number - 1]
    return prose


def _bash_prose(lines: list, heredocs: set) -> dict:
    """{line: text} for every whole-line comment, as `code_lines` reads them."""
    return {number: line.lstrip() for number, line in enumerate(lines, start=1)
            if line.lstrip().startswith("#")
            and not line.lstrip().startswith("#!") and number not in heredocs}


def _python_scope_reader(lines: list, tree: ast.Module):
    """A function from a line to the code its prose is in scope of: the module
    docstring, the innermost def or class around it, or the next top-level
    statement when it is a comment between statements."""
    defs = [(node.lineno, node.end_lineno) for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef))]
    tops = [(node.lineno, node.end_lineno) for node in tree.body]
    doc = None
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        doc = tops[0]

    def scope_of(number: int) -> str:
        if doc and doc[0] <= number <= doc[1]:
            span = doc
        else:
            around = [span for span in defs if span[0] <= number <= span[1]]
            following = [span for span in tops if span[0] > number]
            span = (min(around, key=lambda s: s[1] - s[0]) if around
                    else following[0] if following else (number, number))
        return "\n".join(lines[span[0] - 1:span[1]])

    return scope_of


_BASH_FUNCTION = re.compile(r"^(?:function\s+)?[A-Za-z_][\w.:-]*\s*\(\)\s*\{")


def _bash_scope_reader(lines: list):
    """The same for bash: the function around a comment, or the comment block
    and the statement under it, up to the next blank line."""
    spans, index = [], 0
    while index < len(lines):
        if _BASH_FUNCTION.match(lines[index]):
            end = index
            if not lines[index].rstrip().endswith("}"):
                end = index + 1
                while end < len(lines) and lines[end].rstrip() != "}":
                    end += 1
            spans.append((index + 1, end + 1))
            index = end
        index += 1

    def scope_of(number: int) -> str:
        for first, last in spans:
            if first <= number <= last:
                return "\n".join(lines[first - 1:last])
        first = number
        while first > 1 and lines[first - 2].lstrip().startswith("#"):
            first -= 1
        last = number
        while last <= len(lines) and lines[last - 1].lstrip().startswith("#"):
            last += 1
        stop = last
        while (stop <= len(lines) and lines[stop - 1].strip()
               and stop - last < 40):
            stop += 1
        return "\n".join(lines[first - 1:stop])

    return scope_of


def _prose_blocks(prose: dict):
    """(text, [(offset, line)]) for each run of consecutive prose lines, joined
    so that a sentence wrapped across lines reads as one."""
    blocks, current, previous = [], [], None
    for number in sorted(prose):
        if previous is not None and number != previous + 1:
            blocks.append(current)
            current = []
        current.append(number)
        previous = number
    if current:
        blocks.append(current)
    for block in blocks:
        text, offsets = "", []
        for number in block:
            offsets.append((len(text), number))
            text += re.sub(r"^\s*#:?\s?", "", prose[number]).strip() + " "
        yield text, offsets


def _counted_phrase(rest: str, inventory: _Inventory):
    """The words after a number word, if they count `inventory`'s items: only
    its own words as modifiers, then one of its item nouns that ends the group.
    "two upload jobs" is not a count of `JOBS`, since `upload` is not its
    word, and "two command destinations" is not one of `COMMANDS`, since the
    noun `command` carries on into `destinations`."""
    words = []
    for found in re.finditer(r"\s+([A-Za-z][A-Za-z'-]*)|(.)", rest):
        if found.group(1) is None or len(words) >= 4:
            break
        words.append((found.group(1), found.end()))
    for position, (word, end) in enumerate(words):
        singular = _singular(word)
        following = re.match(r"\s+([A-Za-z][A-Za-z'-]*)", rest[end:])
        continues = (following is not None
                     and following.group(1).lower() not in _FUNCTION_WORDS)
        if singular in inventory.nouns and not continues:
            return " ".join(piece for piece, _ in words[:position + 1])
        if singular not in inventory.vocab and singular not in inventory.nouns:
            return None
    return None


def _anaphor(text: str, match) -> str:
    """"of them", "or none" or "of the" when the number word has no noun of its
    own: the shapes #58 found in `the four of them`, `all four or none` and
    `which of the four were missing`."""
    before = text[max(0, match.start() - 12):match.start()].lower()
    after = text[match.end():match.end() + 16].lower()
    if re.match(r"\s+of\s+(?:them|these|those)\b", after):
        return "of them"
    if re.match(r"\s+or\s+none\b", after):
        return "or none"
    if re.search(r"\bof\s+the\s+$", before):
        following = re.match(r"\s+([a-z]+)", after)
        if following is None or following.group(1) in _FUNCTION_WORDS:
            return "of the"
    return ""


def _spelled_counts(kind: str, source: str) -> list:
    """Every spelled count of an inventory that `source` defines, in its own
    prose. `kind` is "python" or "bash"."""
    lines = source.splitlines()
    if kind == "python":
        tree = ast.parse(source)
        inventories = _python_inventories(tree, lines)
        if not inventories:
            return []
        prose = _python_prose(source, tree)
        scope_of = _python_scope_reader(lines, tree)
    else:
        heredocs = _bash_heredoc_lines(lines)
        inventories = _bash_inventories(lines, heredocs)
        if not inventories:
            return []
        prose = _bash_prose(lines, heredocs)
        scope_of = _bash_scope_reader(lines)
    findings = []
    for text, offsets in _prose_blocks(prose):
        for match in _COUNT_WORD.finditer(text):
            value = _COUNT_VALUE[match.group(1).lower()]
            line = max(at for offset, at in offsets if offset <= match.start())
            rest = text[match.end():match.end() + 120]
            anaphor = _anaphor(text, match)
            scope, tied, phrase = None, [], ""
            for inventory in inventories.values():
                counted = _counted_phrase(rest, inventory)
                if counted is None and not anaphor:
                    continue
                scope = scope_of(line) if scope is None else scope
                named = re.search(
                    r"(?<!\w)" + re.escape(inventory.name) + r"(?!\w)", scope)
                equal = value == len(inventory.items)
                # A noun ties it where it is in scope OR is the size today; with
                # no noun, only where it is both.
                if (named or equal) if counted is not None else (named and equal):
                    tied.append((inventory.name, len(inventory.items)))
                    phrase = phrase or f"{match.group(1)} {counted or anaphor}"
            if tied:
                context = " ".join(
                    text[max(0, match.start() - 24):match.start() + 60].split())
                findings.append(_SpelledCount(
                    line, match.group(1), phrase, context, tuple(tied)))
    return findings


def _spelled_count_refusal(rel: str, finding: _SpelledCount) -> str:
    inventories = ", ".join(
        f"{name} ({size} items)" for name, size in finding.inventories)
    return (f"{rel}:{finding.line}: '{finding.number}' counts {inventories} in "
            f"prose (\"{finding.phrase}\") — derive the count or drop it, as "
            "#58 did")


#: Each entry is (file, text, why): a spelled count the rule reads as one of an
#: inventory and that is a count of something else. `text` is a part of the
#: finding's own words, so an entry follows its sentence when the file moves
#: under it, and `test_every_spelled_count_allowance_still_matches_a_finding`
#: fails on one that no longer matches anything.
SPELLED_COUNT_ALLOWED = [
    ("openRepoTools", "rename is four files",
     "the files one rename commit writes: it counts a rename, and nothing here "
     "is a list of them"),
    ("tests/test_openrepotools_command.py", "rename is four files",
     "the same sentence as the one in `openRepoTools`, for the same reason"),
    ("openRepoTools", "THE SIX FILES INSIDE THEM",
     "the SKILL.md files, 3 skills at 2 paths each: a count of paths, and not "
     "of the command names `COMMANDS` holds"),
    ("tests/test_install_pipx.py", "IN TWO MODES",
     "the 2 modes that case is parametrized over, `checkout` and `package`: a "
     "subset of the ways `MODES` lists, which is one more"),
    ("tests/test_repo_hygiene.py", "four helpers every assertion",
     "the assertion helpers of the shell suite, which only happen to be as "
     "many as `LANE_BASH` holds"),
]


def _repository_spelled_counts() -> list:
    """(file, finding) for every file this rule reads: each `tests/*.py`, and
    each bash file the hygiene checks already read, `ALL_BASH`."""
    sources = [(path.relative_to(REPO).as_posix(), "python", path)
               for path in sorted((REPO / "tests").glob("*.py"))]
    sources += [(name, "bash", REPO / name) for name in ALL_BASH]
    return [(rel, finding) for rel, kind, path in sources
            for finding in _spelled_counts(kind, path.read_text(encoding="utf-8"))]


def _spelled_count_allowance(rel: str, finding: _SpelledCount) -> list:
    return [entry for entry in SPELLED_COUNT_ALLOWED
            if entry[0] == rel and entry[1] in finding.context]


def test_no_prose_spells_a_count_of_an_inventory_its_own_file_defines():
    """#58's second decision, which Brett Heap ruled on 2026-10-23: "Add the
    rule". The prose said "four" about inventories that held 6, 10 and 11
    items, in 6 places, and each was fixed by deriving the count or wording the
    sentence without one. This is what keeps it fixed.

    WHAT IS READ. A file that DEFINES an inventory: a module-level list or
    tuple of names in `tests/*.py` (2 or more strings without a space, or a
    `+` of such), or an upper-case `NAME=( … )` array literal of 2 or more
    plain words in a bash file this module reads (`ALL_BASH`). An array holding
    an expansion, one named `*_ARGS`, `*_ARGV`, `*_CALL` or `*_CMD` (a command
    line), a lower-case one and one inside a here-document is not an inventory.
    Its PROSE is the Python comments and docstrings and the bash whole-line
    comments, with a sentence wrapped across lines joined. A string is not
    prose, and neither is a file that defines no inventory: `README.md` and
    `tests.yml` said "four" about lists they do not define.

    WHAT IS REFUSED. A number word from 2 to 20, in any case, that counts the
    inventory's items. It is TIED to an inventory by the nouns its NAME and its
    OWN COMMENT give its items, and never by a guess:
      * the item nouns are the last word of the name (`INSTALLABLES`,
        `ESTATE_COMMANDS`) and the head of the first noun phrase of the comment
        directly above it (`EVERY BASH FILE THIS REPOSITORY SHIPS` gives `file`);
      * a count is the number word, modifiers that are the inventory's own
        words, then an item noun that ends the noun group — "all <N> files are",
        "each of the <N> bash files with", "the <N> installables";
      * "two upload jobs" (a modifier `JOBS` does not use), "two command
        destinations" (the noun runs on into another), "<N>-wide" and
        "thirty-five" are other counts, and pass.
    A noun alone is too loose, since `file` is the head of half the inventories
    here, so it must ALSO be in SCOPE (the prose is the comment above the
    inventory or lives in a function, class, statement or module docstring
    whose code names it) or VALUE (the number is today's size of the
    inventory). Each refusal names the file, the line, the number word and the
    inventory with its size, and says to derive the count or drop it, as #58
    did.

    WHAT IS NOT CAUGHT. A count with no noun — "the <N> of them", "all <N> or
    none", "which of the <N> were missing" — has nothing to tie to an
    inventory. The fallback ties one only where its number EQUALS the size of
    an inventory in scope, which refuses it on the day it is true and lets it
    pass once the inventory has grown past it. A DRIFTED "the <N> of them" is
    NOT caught, and no wording of this rule can catch it without guessing which
    set "them" is; `test_a_drifted_count_with_no_noun_is_not_caught` pins the
    limit so it is not hidden. Prose in a file that defines no inventory, a
    count the nouns do not reach ("the <N> artifacts"), and a count spelled
    over the next noun group of a wrapped list are not caught either.

    A refusal that is a count of something else goes in `SPELLED_COUNT_ALLOWED`
    with the reason.
    """
    refused = [_spelled_count_refusal(rel, finding)
               for rel, finding in _repository_spelled_counts()
               if not _spelled_count_allowance(rel, finding)]
    assert not refused, "\n".join(refused)


def test_every_spelled_count_allowance_still_matches_a_finding():
    """An entry whose sentence was fixed or reworded matches nothing, and an
    allowlist that keeps entries nothing needs is how a real finding gets
    waved through by a stale one."""
    findings = _repository_spelled_counts()
    unused = [entry[:2] for entry in SPELLED_COUNT_ALLOWED
              if not any(entry[0] == rel and entry[1] in finding.context
                         for rel, finding in findings)]
    assert not unused, f"no longer matches a finding, delete it: {unused}"


_Shape = namedtuple("_Shape", "site sentence inventory caught")

#: (name, the comment above it, how many items it held when #58 was filed).
_SHAPE_INVENTORIES = {
    "bash files": ("SHIPPED_BASH", "EVERY BASH FILE THIS REPOSITORY SHIPS.", 6),
    "installables": ("INSTALLABLES", "EVERY FILE `--install` PLACES.", 11),
    "commands": ("COMMANDS", "THE COMMANDS THIS REPOSITORY SHIPS.", 6),
}

#: #58's sentences as its body quotes them, each with the inventory it was
#: about. `caught` is whether the rule refuses it once the inventory has
#: drifted past the number, as it had in every one of them: the 4 that have no
#: noun are not.
_SHAPES_58 = [
    _Shape("README.md:333", "Windows: all four files are bash",
           "bash files", True),
    _Shape("README.md:403",
           "The macOS job parses each of the four bash files with `/bin/bash -n`",
           "bash files", True),
    _Shape(".github/workflows/tests.yml:177",
           "THE SAME SUITE ON macOS, because these four files are what a Mac runs",
           "bash files", True),
    _Shape("openRepoTools:370", "ONE PATH NOTE for the four of them",
           "installables", False),
    _Shape("tests/test_repo_hygiene.py:6",
           "facts about the four bash files and the four documents",
           "bash files", True),
    _Shape("tests/test_repo_hygiene.py:2126",
           "every `\\n` in these four bash files", "bash files", True),
    _Shape("tests/test_openrepotools_command.py:9-11",
           "There are FOUR files to answer for (`openRepoTools`, `park`, "
           "`resume`, `status`), because `--install` places all four or none",
           "installables", True),
    _Shape("tests/test_openrepotools_command.py:530", "the four of them",
           "installables", False),
    _Shape("tests/test_openrepotools_command.py:590", "all four or none",
           "installables", False),
    _Shape("tests/test_openrepotools_command.py:632",
           "the four files `--install` places", "installables", True),
    _Shape("tests/test_openrepotools_command.py:644",
           "which of the four were missing", "installables", False),
    _Shape("tests/test_lane_helpers.sh:30",
           "The four commands and the shipped alias table", "commands", True),
]
_SHAPE_FORMS = ("bash comment", "python comment", "python docstring")


def _shape_source(form: str, shape: _Shape, size: int) -> tuple:
    """(kind, source) for `shape`'s sentence, written as `form` beside the
    inventory it was about, holding `size` items."""
    name, lead, _ = _SHAPE_INVENTORIES[shape.inventory]
    items = [f"item{number}" for number in range(size)]
    if form == "bash comment":
        return "bash", f"# {lead}\n# {shape.sentence}\n{name}=({' '.join(items)})\n"
    listing = f"{name} = [{', '.join(repr(item) for item in items)}]\n"
    if form == "python comment":
        return "python", f"#: {lead}\n#: {shape.sentence}\n{listing}"
    return "python", (f"#: {lead}\n{listing}\n\ndef test_it():\n"
                      f"    '''{shape.sentence}'''\n    return {name}\n")


def _shape_cases(caught: bool) -> list:
    return [pytest.param(shape, form, id=f"{shape.site} as a {form}")
            for shape in _SHAPES_58 if shape.caught == caught
            for form in _SHAPE_FORMS]


@pytest.mark.parametrize("shape, form", _shape_cases(True))
def test_the_spelled_count_rule_refuses_58s_sentences_once_the_list_has_drifted(
        shape, form):
    """The 8 sentences with a noun, rebuilt from #58's body, beside an
    inventory that holds more than they say — which is how each was found."""
    kind, source = _shape_source(
        form, shape, _SHAPE_INVENTORIES[shape.inventory][2])
    found = _spelled_counts(kind, source)
    assert found, f"{shape.site}: {shape.sentence!r} is not refused as {form}"
    assert all(name == _SHAPE_INVENTORIES[shape.inventory][0]
               for finding in found for name, _ in finding.inventories)


@pytest.mark.parametrize("shape, form", _shape_cases(True) + _shape_cases(False))
def test_the_spelled_count_rule_refuses_every_shape_at_the_size_it_was_written_for(
        shape, form):
    """All 12 sentences, with the inventory as long as the number says. That
    is the only size at which the 4 with no noun are refused, and it is the
    day the sentence is written: the rule would have stopped them then."""
    size = _COUNT_VALUE[_COUNT_WORD.search(shape.sentence).group(1).lower()]
    kind, source = _shape_source(form, shape, size)
    assert _spelled_counts(kind, source), (
        f"{shape.site}: {shape.sentence!r} is not refused as {form}")


@pytest.mark.parametrize("shape, form", _shape_cases(False))
def test_a_drifted_count_with_no_noun_is_not_caught(shape, form):
    """THE LIMIT, PINNED. "the 4 of them", "all 4 or none" and "which of the 4
    were missing" name nothing the rule can tie to an inventory, so once the
    inventory has grown past the number they pass. If this test starts to
    fail, the rule has learned to read an antecedent: say so in the rule's
    docstring and move these 4 sentences into the refused cases."""
    kind, source = _shape_source(
        form, shape, _SHAPE_INVENTORIES[shape.inventory][2])
    assert not _spelled_counts(kind, source), (
        f"{shape.site}: {shape.sentence!r} is caught now as {form}")


_OTHER_COUNTS = [
    pytest.param("bash", (
        "# EVERY BASH FILE THIS REPOSITORY SHIPS.\n"
        "SHIPPED_BASH=(openRepoTools park resume status lane lanes)\n"
        "\n"
        "# The three skills at two destinations each, three-wide, thirty-five\n"
        "# lines, twenty-one files, thirty files and one file.\n"
        "echo done\n"), id="counts of other things beside the inventory"),
    pytest.param("python", (
        "#: THE JOBS A RELEASE RUNS.\n"
        "JOBS = ('build', 'testpypi', 'install', 'pypi')\n\n\n"
        "#: Only the two upload jobs mint a token.\n"
        "def mint():\n    return JOBS\n"), id="a modifier the inventory does not use"),
    pytest.param("bash", (
        "# THE COMMANDS THIS REPOSITORY SHIPS.\n"
        "COMMANDS=(handoff ctx swap)\n"
        "# the two command destinations are added once rather than once per name.\n"
        "echo \"${COMMANDS[@]}\"\n"), id="a noun that runs on into another"),
    pytest.param("python", (
        "#: EVERY BASH FILE THIS REPOSITORY SHIPS.\n"
        "SHIPPED_BASH = ['openRepoTools', 'park', 'resume', 'status', 'lane', "
        "'lanes']\n\n\n"
        "def other():\n"
        "    '''Reads three files in this repository, none of them listed.'''\n"
        "    return 1\n"), id="the same noun out of scope at another size"),
    pytest.param("python", (
        "#: EVERY BASH FILE THIS REPOSITORY SHIPS.\n"
        "SHIPPED_BASH = ['openRepoTools', 'park', 'resume', 'status']\n\n\n"
        "def other():\n    '''Reads the four of them.'''\n    return 1\n"),
        id="a count with no noun, out of scope"),
    pytest.param("python", (
        "#: EVERY BASH FILE THIS REPOSITORY SHIPS.\n"
        "SHIPPED_BASH = ['openRepoTools', 'park', 'resume', 'status', 'lane', "
        "'lanes']\n"
        "MESSAGE = 'all four files are bash'\n"), id="a count in a string"),
    pytest.param("bash", (
        "# EVERY BASH FILE THIS REPOSITORY SHIPS.\n"
        "SHIPPED_BASH=(openRepoTools park resume status lane lanes)\n"
        "echo \"all four files are bash\"\n"), id="a count in a command"),
    pytest.param("bash", (
        "# the three retired files\n"
        "RETIRED=(restart)\n"
        "args=(status --porcelain)\n"
        "# the two files\n"), id="arrays that are not inventories"),
]


@pytest.mark.parametrize("kind, source", _OTHER_COUNTS)
def test_the_spelled_count_rule_passes_counts_of_other_things(kind, source):
    """The true negatives: a count the nouns, the scope and the size do not
    tie to an inventory is a count of something else."""
    assert _spelled_counts(kind, source) == []


def test_the_spelled_count_rule_reads_inventories_as_defined():
    python = ("A = ['x', 'y']\n"
              "B = ['x']\n"
              "C = ['two words', 'y']\n"
              "D = A + ['z', 'w']\n"
              "E = (1, 2)\n"
              "F = A + ['z']\n")
    found = _python_inventories(ast.parse(python), python.splitlines())
    assert {name: len(inventory.items)
            for name, inventory in found.items()} == {"A": 2, "D": 4}

    bash = ["# THE FILES THIS PLACES.", "PLACED=(a b", "  c  # a note, not an item",
            "  \"d e\")", "RETIRED=(restart)", "lowercase=(x y)",
            "DERIVED=(a \"$b\")", "CHILD_ARGS=(make resume)", "cat <<'EOF'",
            "HEREDOC=(p q)", "EOF"]
    found = _bash_inventories(bash, _bash_heredoc_lines(bash))
    assert {name: inventory.items for name, inventory in found.items()} == {
        "PLACED": ["a", "b", "c", "d e"]}
    assert found["PLACED"].nouns == {"placed", "file"}


def test_a_spelled_count_refusal_names_where_what_and_how_to_fix_it():
    _, source = _shape_source("bash comment", _SHAPES_58[0], 6)
    (finding,) = _spelled_counts("bash", source)
    refusal = _spelled_count_refusal("README.md", finding)
    assert refusal.startswith("README.md:2: 'four' counts SHIPPED_BASH (6 items)")
    assert "derive the count or drop it, as #58 did" in refusal
