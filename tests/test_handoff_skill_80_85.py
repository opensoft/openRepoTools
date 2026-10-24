# SPDX-License-Identifier: Apache-2.0
"""`skills/handoff/SKILL.md`'s two record writes and the why they carry, held to
opensoft/openRepoTools#80 item 7 and #85's skill half.

#80 ITEM 7 — THE RECORD WRITES CARRIED THE TEMPLATE, NOT THE VALUE. Step 4
computes `why_text` (the operator's why, then the kind's word) and then wrote
neither line with it. The object log's PAUSED free text was the literal
`on <operator>'s word: <sanitized verbatim>`, and the register's file-level
line carried `<sanitized verbatim>` and `<what's open, or NOTHING CLAIMED>`,
so a person who ran the block as printed recorded the placeholders.
`lane-handoff`, the same act from a shell (Amendment 17(a)), passes its
computed text to both writes. The two are now held to write the same lines for
the same why.

#85, THE SKILL'S HALF — A LINE BREAK IN THE WHY. #218 made `append-line` and
`lane-handoff` refuse a why carrying a newline or a carriage return before
anything is written, and made `lane-handoff`'s `sanitize` spell every break
`; ` as the second line of defence. The skill did neither. Its why reached step
2's top block and step 4's two one-line writes as typed, and step 4 did not
replace ` — ` either, though its own prose says it does. The skill now refuses
such a why before step 1, as `lane-handoff` does right after reading its
arguments, and step 4 sanitizes the why as `lane-handoff`'s `sanitize` does.

THE BLOCKS ARE RUN, NOT READ. They are found with
`tests/test_skill_shell_blocks.py`'s own fence reader and run in
`tests/test_handoff_skill_72_80.py`'s sandbox (both imported, not copied),
under `bash` and under `zsh -f` where one is installed, because a session's
Bash tool runs a skill's block under the user's own shell.
`lane-handoff`'s side of every comparison is ITS OWN code: its `sanitize`
function, its kind-word lines and its register-line template, cut out of the
file. So the two cannot drift apart with this file still green. Every case
marked RED fails against the skill at b707bd7 and passes with the fix.

NOTHING HERE READS THE CALLER'S ENVIRONMENT. A lane window exports
`WORKBENCHES_CLAUDE_*`, `TMUX`, `LANES_AGENT` and the other `LANES_*` seams,
which are exactly what these blocks read, so the environment is an explicit
dict and never `os.environ` plus changes. `lanes-edit.sh` is a stub on a
private `PATH` that records every call's arguments, `tmux` answers nothing and
`date` answers one fixed instant, so nothing reaches a register, a tmux server
or the network.
"""

from __future__ import annotations

import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

import pytest

from conftest import REPO, WINDOWS_SKIP
from test_handoff_skill_72_80 import SHELLS
from test_handoff_skill_72_80 import Sandbox as SkillSandbox
from test_skill_shell_blocks import SHELL_TAGS, Block, fenced_blocks

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None, reason="the skill's blocks are shell")]

SKILL = REPO / "skills/handoff/SKILL.md"
LANE_HANDOFF = REPO / "lane-handoff"

LANE = "repoHS-1"
WS = "Eagle"
UUID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
#: What the stub `date` answers, so the register line can be compared whole.
NOW = "2026-10-19T01:02:03Z"

#: The three verbs step 4 writes with. Nothing else it calls writes.
WRITES = ("log", "append-line", "set-row-state")

#: A template placeholder: `<` and `>` around words, as the template spells
#: `<sanitized verbatim>`, `<operator>` and `<what's open, or NOTHING CLAIMED>`.
PLACEHOLDER = re.compile(r"<[^<>\n]+>")

#: The markers that find the blocks, each carried by exactly one shell block.
STEP4 = "# (c) the row: ONE WRITE"
DOOR = "REFUSED: the why is ONE line"


# --- the blocks, as the files hold them --------------------------------------

def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _shell_blocks() -> List[Block]:
    return [b for b in fenced_blocks(_skill_text()) if b.tag in SHELL_TAGS]


def _one_block(marker: str) -> Block:
    found = [b for b in _shell_blocks() if marker in b.body]
    assert len(found) == 1, (
        f"expected exactly one shell block of {SKILL.name} carrying "
        f"{marker!r}, found {len(found)}")
    return found[0]


def _lane_handoff_lines() -> List[str]:
    return LANE_HANDOFF.read_text(encoding="utf-8").split("\n")


def _the_line(lines: List[str], start: str) -> str:
    found = [line for line in lines if line.startswith(start)]
    assert len(found) == 1, (
        f"lane-handoff has {len(found)} top-level lines starting {start!r}: "
        "this test is stale")
    return found[0]


def lane_handoff_why_text() -> str:
    """`lane-handoff`'s own `sanitize` and the three lines that build its
    `why_text` from `$why` and `$handoff_kind`, cut out of the file."""
    lines = _lane_handoff_lines()
    starts = [i for i, line in enumerate(lines) if line == "sanitize() {"]
    assert len(starts) == 1, "lane-handoff's `sanitize() {` is gone: stale"
    end = next(j for j in range(starts[0] + 1, len(lines)) if lines[j] == "}")
    return "\n".join(lines[starts[0]:end + 1] + [
        _the_line(lines, 'kind_word="$handoff_kind"'),
        _the_line(lines, '[ "$handoff_kind" = unknown ] && kind_word='),
        _the_line(lines, 'why_text="$(sanitize '),
    ]) + "\n"


def lane_handoff_register_line() -> str:
    """The double-quoted word `lane-handoff` hands `append-line` for the
    register's file-level PAUSED line, cut out of the file."""
    found = re.findall(r'append-line ("PAUSED — lane [^"\n]*")',
                       LANE_HANDOFF.read_text(encoding="utf-8"))
    assert len(found) == 1, (
        f"lane-handoff has {len(found)} register PAUSED lines: stale")
    return found[0]


# --- a sandbox with a stub helper and no inherited environment ---------------

#: Each call is one file holding the `LANES_SESSION` it was made under, then
#: every argument, NUL-separated, so an argument carrying a line break is
#: recorded as the one argument it is. `lane-dir` answers 8, no answer, and
#: every other verb succeeds.
STUB = """#!/usr/bin/env bash
n=$(ls "$STUB_CALLS" | wc -l)
n=$((n + 1))
printf '%s\\0' "${LANES_SESSION-<unset>}" "$@" > "$STUB_CALLS/$(printf '%04d' "$n")"
case "$1" in
  lane-dir) exit 8 ;;
esac
exit 0
"""


class Call(NamedTuple):
    session: str
    argv: List[str]


class Sandbox(SkillSandbox):
    """`tests/test_handoff_skill_72_80.py`'s sandbox: its private `PATH`, its
    explicit environment and its `run` under `bash` or `zsh -f`. On top of it
    go a helper stub that records every argument, a `tmux` that answers
    nothing and a `date` that answers `NOW`."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.calls_dir = root / "calls"
        self.calls_dir.mkdir()
        for name, body in (("lanes-edit.sh", STUB),
                           ("tmux", "#!/bin/sh\nexit 1\n"),
                           ("date", f"#!/bin/sh\nprintf '%s\\n' '{NOW}'\n")):
            tool = self.bin / name
            tool.write_text(body, encoding="utf-8")
            tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
        self.env["STUB_CALLS"] = str(self.calls_dir)

    def recorded(self) -> List[Call]:
        out = []
        for path in sorted(self.calls_dir.iterdir()):
            fields = path.read_bytes().decode("utf-8").split("\0")[:-1]
            out.append(Call(fields[0], fields[1:]))
        return out

    def writes(self, verb: str) -> List[Call]:
        return [c for c in self.recorded() if c.argv and c.argv[0] == verb]


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


def _why_env(why: Optional[str], kind: Optional[str] = None) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if why is not None:
        env["STUB_WHY"] = why
    if kind is not None:
        env["STUB_KIND"] = kind
    return env


#: How a session holds the operator's words when it reaches a block: `$why`,
#: set where the operator gave one and unset where they did not.
WHY_PRELUDE = ('if [ "${STUB_WHY+set}" = set ]; then why="$STUB_WHY"; '
               'else unset why; fi\n')


def _step4(box: Sandbox, shell: str, why: Optional[str],
           kind: Optional[str] = None) -> subprocess.CompletedProcess:
    """Step 4's whole block, with what steps 1 and 2 would have bound: step 2's
    `$hf_record` is a call that exited 0 (`lane-handoff`'s own line)."""
    script = (f'L="{box.helper}"\nlane={LANE}\nws={WS}\nuuid={UUID}\n'
              'ws_missing=""\nuuid_missing=""\nhf_record="handoff refreshed"\n' + WHY_PRELUDE +
              '[ -z "${STUB_KIND-}" ] || kind="$STUB_KIND"\n' +
              _one_block(STEP4).body)
    proc = box.run(shell, script, _why_env(why, kind))
    assert proc.returncode == 0, (proc.returncode, proc.stderr)
    return proc


def _lane_handoff_writes(box: Sandbox, why: str,
                         kind: Optional[str]) -> List[str]:
    """What `lane-handoff`'s own code hands the two writes for this why: the
    log's free text and the register line, with the same lane, session,
    workstation and instant the skill is run with."""
    script = ('why="$STUB_WHY"; handoff_kind="$STUB_KIND"\n' +
              lane_handoff_why_text() +
              f'lane={LANE}; uuid={UUID}; ws={WS}; UTC={NOW}\n'
        f'printf \'%s\\0%s\\0\' "$why_text" {lane_handoff_register_line()}\n')
    proc = box.run("bash", script, _why_env(why, kind or "unknown"))
    assert proc.returncode == 0, (proc.returncode, proc.stderr)
    return proc.stdout.split("\0")[:-1]


def _the_one(box: Sandbox, verb: str) -> Call:
    found = box.writes(verb)
    assert len(found) == 1, (verb, box.recorded())
    return found[0]


# --- #80 item 7: the two writes carry the computed why -----------------------

@pytest.mark.parametrize("shell", SHELLS)
def test_both_record_writes_carry_the_why_the_block_computed(
        box: Sandbox, shell: str) -> None:
    """RED at b707bd7. The object log's PAUSED line takes the why, then the
    kind's word, as its free text, and the register's file-level line is the
    shape `lane-handoff` writes: lane, session@workstation, the instant, that
    same text, then `handoff refreshed`."""
    _step4(box, shell, "a usage reset")
    log = _the_one(box, "log")
    assert log.argv[:4] == ["log", "PAUSED", f"lane:{LANE}", "→"], log.argv
    assert log.session == UUID, log
    assert log.argv[-1] == "a usage reset kind unknown", (
        "the object log's PAUSED free text is not the why the block computed "
        f"(#80 item 7): {log.argv[-1]!r}")
    line = _the_one(box, "append-line")
    assert line.argv[1:] == [
        f"PAUSED — lane {LANE}, session {UUID}@{WS}, {NOW}, "
        "a usage reset kind unknown; handoff refreshed"], (
        f"the register's PAUSED line is not the computed one (#80 item 7): "
        f"{line.argv[1:]!r}")


@pytest.mark.parametrize("shell", SHELLS)
def test_no_write_records_a_template_placeholder(box: Sandbox,
                                                 shell: str) -> None:
    """RED at b707bd7. Run as printed, no argument of any write is a
    `<placeholder>`: what the template showed a reader is never what the
    block records."""
    _step4(box, shell, "a usage reset")
    left = [(c.argv[0], arg) for c in box.recorded() if c.argv[0] in WRITES
            for arg in c.argv if PLACEHOLDER.search(arg)]
    assert not left, f"a write recorded the template's placeholder: {left}"
    assert [c.argv[0] for c in box.recorded() if c.argv[0] in WRITES] == \
        list(WRITES), box.recorded()


def test_no_shell_block_carries_the_placeholders_80_item_7_names() -> None:
    """RED at b707bd7. The three placeholders the finding quotes are gone from
    every shell block of the skill, so no later copy brings one back beside
    the fixed writes."""
    left = [line.strip() for block in _shell_blocks()
            for line in block.body.split("\n")
            if "<sanitized verbatim>" in line or "<operator>" in line
            or "<what's open" in line]
    assert not left, f"a shell block still carries a placeholder: {left}"


class WhyCase(NamedTuple):
    why: str
    kind: Optional[str]      # None leaves `$kind` unset, which is `unknown`


WHY_CASES = {
    "plain": WhyCase("a usage reset", None),
    "em-dash": WhyCase("swap — usage reset", None),
    "respawn": WhyCase("clear", "respawn"),
    "in-process": WhyCase("clear", "in-process"),
    "empty": WhyCase("", None),
    # `lane-handoff` refuses these at its door; its `sanitize` is the second
    # line of defence, and the skill's step 4 is held to that too.
    "line-breaks": WhyCase("a\r\nb\rc\nd — e", None),
    "trailing-newline": WhyCase("usage reset\n", "respawn"),
}


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("case", sorted(WHY_CASES))
def test_the_skill_writes_what_lane_handoff_writes_for_the_same_why(
        box: Sandbox, shell: str, case: str) -> None:
    """RED at b707bd7. For the same why and the same kind, the skill hands
    `log PAUSED` and `append-line` exactly what `lane-handoff`'s own code
    hands them: `sanitize` (` — ` and every line break spelled `; `), an empty
    why written `handoff`, then the kind's word (`kind unknown`, `respawn`,
    `in-process`), and its register-line template around that."""
    want = WHY_CASES[case]
    free_text, register_line = _lane_handoff_writes(box, want.why, want.kind)
    _step4(box, shell, want.why, want.kind)
    assert _the_one(box, "log").argv[-1] == free_text, (
        f"{case}: the skill's PAUSED free text differs from lane-handoff's")
    assert _the_one(box, "append-line").argv[1:] == [register_line], (
        f"{case}: the skill's register line differs from lane-handoff's")


@pytest.mark.parametrize("shell", SHELLS)
def test_a_line_break_reaches_neither_one_line_write(box: Sandbox,
                                                     shell: str) -> None:
    """RED at b707bd7 (#85). A break that reaches step 4 anyway, whatever its
    spelling, is one `; `, as #218 spelled it for `lane-handoff`: the record
    is still written, on one line, and no write is handed a newline or a
    carriage return."""
    _step4(box, shell, "a\r\nb\rc\nd — e")
    assert _the_one(box, "log").argv[-1] == "a; b; c; d; e kind unknown"
    broken = [(c.argv[0], arg) for c in box.recorded() if c.argv[0] in WRITES
              for arg in c.argv if "\n" in arg or "\r" in arg]
    assert not broken, f"a write was handed a line break (#85): {broken}"


# --- #85: the door ------------------------------------------------------------

def _door(box: Sandbox, shell: str,
          why: Optional[str]) -> subprocess.CompletedProcess:
    script = WHY_PRELUDE + _one_block(DOOR).body + "printf 'AFTER\\n'\n"
    return box.run(shell, script, _why_env(why))


REFUSED_WHYS = {
    "newline": "clear\nsecond line",
    "carriage-return": "clear\rsecond line",
    "crlf": "clear\r\nsecond line",
    "trailing-newline": "usage reset\n",
}


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("case", sorted(REFUSED_WHYS))
def test_a_why_carrying_a_line_break_is_refused_at_the_door(
        box: Sandbox, shell: str, case: str) -> None:
    """RED at b707bd7, where there was no door. A why carrying a newline or a
    carriage return stops the skill where it stands (nothing after the block
    runs) with exit 2, and says what `lane-handoff` says at its own door: the
    why is ONE line, nothing was written, put `; ` where the break was."""
    proc = _door(box, shell, REFUSED_WHYS[case])
    assert "AFTER" not in proc.stdout, (
        f"{case}: the skill went on with a why carrying a line break (#85)")
    assert proc.returncode == 2, (proc.returncode, proc.stderr)
    for words in ("the why is ONE line", "Nothing was renamed or written",
                  "with '; ' where the break was"):
        assert words in proc.stderr, (words, proc.stderr)
    assert "the why is ONE line" in LANE_HANDOFF.read_text(encoding="utf-8"), (
        "lane-handoff's own door no longer says the why is ONE line: the two "
        "refusals were written to say the same thing")
    assert box.recorded() == []


PASSED_WHYS = {
    "plain": "a usage reset",
    "em-dash": "swap — usage reset",
    "empty": "",
    "unset": None,
}


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("case", sorted(PASSED_WHYS))
def test_a_one_line_why_passes_the_door_untouched(box: Sandbox, shell: str,
                                                  case: str) -> None:
    """What the door leaves alone: a one-line why, a ` — ` (step 4's sanitize
    spells it), an empty why and none at all go through with nothing said."""
    proc = _door(box, shell, PASSED_WHYS[case])
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "AFTER\n", ""), (
        case, proc.returncode, proc.stdout, proc.stderr)


@pytest.mark.parametrize("shell", SHELLS)
def test_an_unset_why_passes_the_door_under_set_u_and_is_written_handoff(
        box: Sandbox, shell: str) -> None:
    """RED at 9b80eed, where the door read `$why` bare: under `set -u` an
    unset why stopped the shell there ("why: unbound variable" in bash,
    "parameter not set" in zsh), before step 1. A why the operator did not
    give is no why at all. It passes the door with nothing said, and step 4,
    run in the same `set -u` shell, writes it `handoff`, as `lane-handoff`
    does."""
    script = (f'set -u\nL="{box.helper}"\nlane={LANE}\nws={WS}\nuuid={UUID}\n'
              'ws_missing=""\nuuid_missing=""\nhf_record="handoff refreshed"\nunset why\n' +
              _one_block(DOOR).body + "printf 'AFTER\\n'\n" +
              _one_block(STEP4).body)
    proc = box.run(shell, script)
    assert proc.returncode == 0, (proc.returncode, proc.stderr)
    assert proc.stdout.startswith("AFTER\n"), (proc.stdout, proc.stderr)
    assert "why" not in proc.stderr, proc.stderr
    assert _the_one(box, "log").argv[-1] == "handoff kind unknown"
    assert _the_one(box, "append-line").argv[1:] == [
        f"PAUSED — lane {LANE}, session {UUID}@{WS}, {NOW}, "
        "handoff kind unknown; handoff refreshed"]


def test_the_door_stands_before_anything_is_renamed_or_written() -> None:
    """RED at b707bd7. The door is asked before step 1, which renames the
    window, and before every block that publishes, commits or writes a record,
    so its refusal leaves nothing to undo, as `lane-handoff`'s does."""
    door = _one_block(DOOR)
    lines = _skill_text().split("\n")
    step1 = [n for n, line in enumerate(lines, 1) if line.startswith("## 1. ")]
    assert len(step1) == 1, "the skill's `## 1.` heading is gone: stale"
    assert door.opens < step1[0], (
        f"the door opens at line {door.opens}, after step 1 (line {step1[0]})")
    acts = ('"$L" log', "append-line", "set-row-state", "publish-handoff",
            "commit", "rename-window", "send-keys", "lane-handoff")

    def code(block: Block) -> List[str]:
        """The lines that run: a comment that NAMES an act (the preamble's
        fence cites `lane-handoff`'s own) is not that act."""
        return [line for line in block.body.split("\n")
                if not line.lstrip().startswith("#")]

    later = [b.opens for b in _shell_blocks() if b.opens != door.opens
             and any(act in line for line in code(b) for act in acts)]
    assert later and all(opens > door.opens for opens in later), (
        door.opens, later)


def test_step_4s_prose_says_a_line_break_is_spelled_too() -> None:
    """RED at b707bd7. The sentence that tells a reader what "sanitize" means
    names the line break beside the ` — `, as the code under it now does."""
    text = _skill_text()
    start = text.index("First sanitize the operator's words")
    paragraph = text[start:text.index("```sh", start)]
    assert "line break" in paragraph, paragraph
    assert "lane-handoff" in paragraph, paragraph
