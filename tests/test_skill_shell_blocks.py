# SPDX-License-Identifier: Apache-2.0
"""The shell blocks INSIDE the shipped skills, and one claim a skill must not make.

opensoft/openRepoTools#78 and #79, both found by opensoft/workBenches'
`devcontainer.test/` while it vendored `skills/handoff/SKILL.md` byte for byte.

WHY A SKILL'S SHELL BLOCKS NEED THEIR OWN PARSE CHECK. `tests/test_repo_hygiene.py`
runs `bash -n` on the twelve top-level command files, and it never reads a
fenced block inside a `SKILL.md`. A block there is prose to every other test in
the suite, but it is also what a person copies into a terminal, and the skill's
own text says so: *"every command is copy-pasteable as written"*. #78 was one
such block, `pclaude <profile>  # and only then`: bash reads `<` and `>` as
redirections whatever stands beside them, so a person who pasted it got a parse
error instead of a command. The command has since been renamed `lclaude`, and
the bare placeholder was carried through the rename untouched, because nothing
in this repository ever parsed it.

THE CHECK IS `bash -n`, which parses and never runs: a block here may name
`tmux send-keys`, `lane-end` or `git push`, and nothing in it is executed. It is
asked of EVERY fenced `sh`/`bash` block in EVERY `skills/*/SKILL.md`, found by
walking the directory, so a fourth skill is covered the day it is added.

A FENCE WITH NO LANGUAGE IS A FAILURE, not a skip. "Skip what is clearly marked
as not shell" means `text`, `json` and the like; a block that says nothing is
not marked as anything, and treating it as prose would let the next unparsable
example in by leaving its tag off. Today there is none, so this costs a writer
one word.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, NamedTuple

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="the check is `bash -n`"),
              WINDOWS_SKIP]

#: The fence tags whose blocks are parsed. Anything else that carries a tag
#: (`text`, `json`, `diff`) is marked as not shell and is left alone.
SHELL_TAGS = ("sh", "bash", "shell")

#: An opening or closing fence: up to three spaces, three or more backticks, and
#: the info string (no backtick in it, which is what tells a fence from a span
#: of inline code that happens to start a line).
FENCE = re.compile(r"^ {0,3}(`{3,})([^`]*)$")

HANDOFF_SKILL = REPO / "skills/handoff/SKILL.md"


class Block(NamedTuple):
    tag: str      # the fence's first info word, "" where it has none
    opens: int    # the 1-based line of the opening fence
    body: str     # the lines between the fences, newline-terminated


def fenced_blocks(text: str) -> List[Block]:
    """Every fenced block in `text`, in order.

    A fence closes with a bare fence of at least as many backticks, as in
    CommonMark, and what stands between two fences is that block's whatever its
    tag: a ```sh example quoted inside a ```text block is the text block's
    content and is never read as a second block. A block still open at the end
    of the file is returned with the tag `UNTERMINATED`, because it would
    otherwise swallow the rest of the file in silence."""
    blocks: List[Block] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        opening = FENCE.match(lines[i])
        if not opening:
            i += 1
            continue
        ticks, info = opening.group(1), opening.group(2).strip()
        tag = info.split()[0] if info else ""
        start = i
        body: List[str] = []
        i += 1
        closed = False
        while i < len(lines):
            closing = FENCE.match(lines[i])
            if closing and not closing.group(2).strip() \
                    and len(closing.group(1)) >= len(ticks):
                closed = True
                break
            body.append(lines[i])
            i += 1
        blocks.append(Block(tag if closed else "UNTERMINATED", start + 1,
                            "".join(line + "\n" for line in body)))
        i += 1
    return blocks


def parse_problems(rel: str, text: str) -> List[str]:
    """What is wrong with the fenced blocks of `text`, one line each, every one
    naming `rel` and the line IN THE FILE of the thing that is wrong.

    `bash -n` reports `line N` of the block, so the block's own first line is
    added back: the person who reads the failure goes straight to the file."""
    env = {k: v for k, v in os.environ.items() if k not in ("BASH_ENV", "ENV")}
    problems: List[str] = []
    for block in fenced_blocks(text):
        if block.tag == "UNTERMINATED":
            problems.append(f"{rel}:{block.opens}: this fence is never closed")
        elif block.tag == "":
            problems.append(
                f"{rel}:{block.opens}: this fence names no language, so nothing "
                "says whether it is shell; tag it `sh` or `bash` to have it "
                "parsed, or `text` to say it is not shell")
        elif block.tag in SHELL_TAGS:
            proc = subprocess.run(["bash", "-n"], input=block.body, env=env,
                                  capture_output=True, text=True, check=False)
            if proc.returncode == 0:
                continue
            body_lines = block.body.split("\n")
            found = False
            for report in proc.stderr.splitlines():
                at = re.match(r"bash: line (\d+): ([^`].*)$", report)
                if not at:
                    continue   # bash's second line quotes the source in backticks
                n = int(at.group(1))
                quoted = body_lines[n - 1].strip() if 0 < n <= len(body_lines) else ""
                problems.append(
                    f"{rel}:{block.opens + n}: {at.group(2)} -- in `{quoted}` "
                    f"(the ```{block.tag} block that opens at line {block.opens})")
                found = True
            if not found:
                problems.append(
                    f"{rel}:{block.opens}: this ```{block.tag} block does not "
                    f"parse: {proc.stderr.strip()}")
    return problems


def shipped_skills() -> List[Path]:
    return sorted((REPO / "skills").glob("*/SKILL.md"))


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


# --- #78 --------------------------------------------------------------------

def test_every_shell_block_in_every_skill_parses():
    """EVERY ```sh AND ```bash BLOCK IN EVERY `skills/*/SKILL.md` PARSES UNDER
    `bash -n`, and every fence says what it is. The failure names the file, the
    line and the text of what does not parse."""
    skills = shipped_skills()
    assert skills, "no skills/*/SKILL.md found — this test is looking in the wrong tree"
    problems: List[str] = []
    for path in skills:
        problems += parse_problems(rel(path), path.read_text(encoding="utf-8"))
    assert not problems, (
        "a skill's example block is what a person pastes into a terminal, and "
        "these do not parse (a bare `<placeholder>` is the usual cause: bash "
        "reads `<` and `>` as redirections; spell it "
        "`\"${CLAUDE_PROFILE_NAME:-<profile>}\"` or put it in a comment):\n  "
        + "\n  ".join(problems))


def test_the_checker_is_not_blind_to_the_blocks_it_checks():
    """A checker whose fence reader went wrong would pass over a skill whose
    every block it had failed to find. The two skills that carry the longest
    sequences of commands are asserted to yield blocks, in both spellings of
    the tag between them."""
    seen = set()
    for name in ("handoff", "restart"):
        path = REPO / f"skills/{name}/SKILL.md"
        blocks = [b for b in fenced_blocks(path.read_text(encoding="utf-8"))
                  if b.tag in SHELL_TAGS]
        assert len(blocks) >= 5, (
            f"{rel(path)} yielded {len(blocks)} shell blocks; it carries well "
            "over that, so the fence reader is skipping them")
        seen |= {b.tag for b in blocks}
    assert {"sh", "bash"} <= seen, f"only {sorted(seen)} found; both tags are in use"


#: #78's block as filed, line for line, set between prose and a `text` fence
#: that quotes the same bare placeholder, which is NOT shell and must not be
#: parsed. The `sh` block that follows it spells the placeholder the way step 5
#: does and must pass.
ISSUE_78_DOCUMENT = """\
Run the late record, then restart:

```sh
lane-handoff --late --at 2026-09-14T12:02:27Z "late; usage limit hit before the swap"
pclaude <profile>      # and only then
```

What a person sees, which is not shell:

```text
pclaude <profile>
```

And spelled so that it parses:

```bash
lclaude "${CLAUDE_PROFILE_NAME:-<profile>}"      # and only then
```
"""


def test_the_checker_reports_the_defect_issue_78_filed_where_it_is():
    """THE CHECKER ITSELF, ON #78's OWN BLOCK. It must name the file and the
    line IN THE FILE of the bare `pclaude <profile>` (line 5 of the document
    above, not line 2 of the block), must say nothing about the `text` fence
    that carries the same characters, and must pass the quoted spelling."""
    problems = parse_problems("skills/x/SKILL.md", ISSUE_78_DOCUMENT)
    assert len(problems) == 1, problems
    assert problems[0].startswith("skills/x/SKILL.md:5: "), problems[0]
    assert "pclaude <profile>      # and only then" in problems[0], problems[0]
    assert "opens at line 3" in problems[0], problems[0]


def test_a_fence_with_no_language_and_a_fence_never_closed_are_refused():
    """The two ways an example block could leave the check by being written
    carelessly rather than wrongly: an opening fence that says nothing, and one
    that is never closed (which would otherwise read the rest of the file as
    one block, or as none)."""
    bare = parse_problems("skills/x/SKILL.md", "```\nlclaude <profile>\n```\n")
    assert len(bare) == 1 and "names no language" in bare[0], bare
    assert bare[0].startswith("skills/x/SKILL.md:1: "), bare[0]
    open_ended = parse_problems("skills/x/SKILL.md", "text\n```sh\necho hi\n")
    assert len(open_ended) == 1 and "never closed" in open_ended[0], open_ended
    assert open_ended[0].startswith("skills/x/SKILL.md:2: "), open_ended[0]


def test_a_fenced_example_inside_a_text_block_is_that_blocks_content():
    """A ```sh fence quoted INSIDE a longer ```` ```text ```` fence is the text
    block's own content: it is never read as a block of its own and never
    parsed, and the longer fence is what closes the outer one."""
    document = "````text\n```sh\npclaude <profile>\n```\n````\n"
    assert parse_problems("skills/x/SKILL.md", document) == []


# --- #79 --------------------------------------------------------------------

def test_the_handoff_skill_does_not_call_rename_the_only_act_there_is():
    """AMENDMENT 12'S NAME GUARD TYPES `/rename <lane>` ITSELF, so the
    operator's own `/rename` is the fallback and not "the only act there is".

    Step 5's comment said it was the only act, which was true until Amendment 12
    (`lanes-edit.sh session-start`, the `SessionStart` hook, and
    `lanes-edit.sh guard`, the `UserPromptSubmit` guard: `guard_type` sends the
    keys to the session's own pane, and `docs/README-lanes.md` says so under
    "The `SessionStart` block's own line"). What is still true, and is kept: no
    API renames a running session from inside — a keystroke is not an API."""
    text = HANDOFF_SKILL.read_text(encoding="utf-8")
    stale = [n for n, line in enumerate(text.splitlines(), 1)
             if "only act there is" in line]
    assert not stale, (
        f"{rel(HANDOFF_SKILL)}:{stale[0]} calls the operator's /rename the only "
        "act there is, which Amendment 12's name guard made false: it types the "
        "rename itself, and the operator's is the fallback (#79)")
    comment = text.split("# WHICH ACT REMOVES THIS LINE", 1)
    assert len(comment) == 2, "step 5's `WHICH ACT REMOVES THIS LINE` comment is gone"
    paragraph = comment[1].split("echo 'then, in the session that comes up", 1)[0]
    for name in ("SessionStart", "UserPromptSubmit", "Amendment 12"):
        assert name in paragraph, (
            f"step 5's comment no longer names {name}, which is who types the "
            "rename ahead of the operator")
    assert "FALLBACK" in paragraph, (
        "step 5's comment must say the operator's /rename is the fallback")
    assert "no API" in paragraph, (
        "the true half of the claim stays: no API renames a running session")
