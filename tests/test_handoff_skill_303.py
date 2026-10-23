# SPDX-License-Identifier: Apache-2.0
"""`skills/handoff/SKILL.md`'s ordinary path over a lane's object log that
could not be read: R7 on opensoft/openRepoTools#303, Brett Heap's ruling
"Write swap, name the gap", held to the skill by lane 3's ruling 651.

The manual calls the skill the single source of the act, and a session's
`/handoff` runs the skill's own steps and never calls `lane-handoff`. Step 2
publishes through `lanes-edit.sh publish-handoff`, which is fenced on the
lane's restart intent: where the lane's log could not be read, where that
intent is kept is not known (`restart-intent` exits 10), and the publisher
refuses rather than write over a restart nobody could look for. The skill said
nothing about that refusal, and step 4 wrote `; handoff refreshed` whatever
step 2 had done - a false register line. Now step 2 goes on past this one
refusal and names the gap, and step 4 writes R7's words, as `lane-handoff`
does in the same case (`tests/test_log_read_status_303.py` holds the shell's
half).

THE BLOCKS ARE RUN, NOT READ, in `tests/test_handoff_skill_72_80.py`'s sandbox
(imported, not copied), under `bash` and under `zsh -f` where one is
installed. `lanes-edit.sh` is a stub that records every call and answers
`publish-handoff` and `restart-intent` as a case sets them, `tmux` answers
nothing and `date` one fixed instant, so nothing reaches a register.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

import pytest

from conftest import REPO, WINDOWS_SKIP
from test_handoff_skill_72_80 import SHELLS
from test_handoff_skill_72_80 import Sandbox as SkillSandbox
from test_skill_shell_blocks import SHELL_TAGS, fenced_blocks

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None, reason="the skill's blocks are shell")]

SKILL = REPO / "skills/handoff/SKILL.md"
LANE_HANDOFF = REPO / "lane-handoff"

LANE = "repoHS-1"
UUID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
NOW = "2026-10-19T01:02:03Z"

#: The markers that find the two blocks: step 2's publication, and step 4.
PUBLISH = 'publish-handoff "$lane" "$handoff_file" "$prepared_file"'
STEP4 = "# (c) the row: ONE WRITE"

#: What the gap is, in the words `lane-handoff` names it in.
GAP = f"lane {LANE}'s object log could not be read, so where its restart intent is kept is NOT established"
#: The register line's tail where no handoff was published (R7).
R7_TAIL = "; handoff NOT published: object log unreadable"
#: What a later publication waits on: the intent, not the log (the review of
#: R7, 653(c)), in the words `lane-handoff`'s own note uses.
WAIT_ON = (f"once `lanes-edit.sh restart-intent {LANE}` answers 8, `ready` or `failed`, publish "
           f"this block with `publish-handoff`; read `lane-handoff --restart-status --lane {LANE}` "
           "before relaunching")

#: Each call is one file holding the `LANES_NO_FETCH` it was made under, then
#: every argument, NUL-separated. `publish-handoff` succeeds where
#: `STUB_PUBLISH_RC` is 0 and otherwise refuses with that code and its words;
#: `restart-intent` exits `STUB_INTENT_RC`; `lane-dir` answers 8, no answer;
#: every other verb succeeds.
STUB = """#!/usr/bin/env bash
n=$(ls "$STUB_CALLS" | wc -l)
n=$((n + 1))
printf '%s\\0' "${LANES_NO_FETCH-<unset>}" "$@" > "$STUB_CALLS/$(printf '%04d' "$n")"
case "$1" in
  lane-dir) exit 8 ;;
  publish-handoff)
    if [ "${STUB_PUBLISH_RC:-0}" = 0 ]; then printf '%s\\n' "$3"; exit 0; fi
    printf 'lanes-edit: %s\\n' "$STUB_PUBLISH_ERR" >&2
    exit "$STUB_PUBLISH_RC" ;;
  restart-intent) exit "${STUB_INTENT_RC:-8}" ;;
esac
exit 0
"""


class Call(NamedTuple):
    no_fetch: str
    argv: List[str]


class Sandbox(SkillSandbox):
    """`tests/test_handoff_skill_72_80.py`'s sandbox, with the stub above, a
    `tmux` that answers nothing and a `date` that answers `NOW`."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.calls_dir = root / "calls"
        self.calls_dir.mkdir()
        for name, body in (("lanes-edit.sh", STUB), ("tmux", "#!/bin/sh\nexit 1\n"),
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

    def verbs(self) -> List[str]:
        return [c.argv[0] for c in self.recorded() if c.argv]


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


def _block(marker: str) -> str:
    found = [b.body for b in fenced_blocks(SKILL.read_text(encoding="utf-8"))
             if b.tag in SHELL_TAGS and marker in b.body]
    assert len(found) == 1, (
        f"expected exactly one shell block of {SKILL.name} carrying {marker!r}, "
        f"found {len(found)}: this test is stale")
    return found[0]


#: What steps 1 and 2 bind before the publication and step 4 run.
def _bound(box: Sandbox) -> str:
    return "\n".join([
        f'L="{box.helper}"', f"lane={LANE}", "ws=Eagle", f"uuid={UUID}",
        'ws_missing=""', 'uuid_missing=""', 'why="a usage reset"',
        f'handoff_file="{box.root}/handoff.md"', f'prepared_file="{box.root}/prepared.md"',
        f"prior_sha256={'0' * 64}", ""])


def _answers(publish_rc: int, intent_rc: int, err: str = "") -> Dict[str, str]:
    return {"STUB_PUBLISH_RC": str(publish_rc), "STUB_INTENT_RC": str(intent_rc),
            "STUB_PUBLISH_ERR": err or "restart ownership could not be read; no handoff was published"}


def _step2(box: Sandbox, shell: str, publish_rc: int, intent_rc: int,
           err: str = "") -> subprocess.CompletedProcess:
    # The status the block itself ends on is the process's, so a refusal that
    # stops the skill is read from `proc.returncode`: the line that prints
    # what the block bound hands `$?` on as its own exit.
    script = (_bound(box) + _block(PUBLISH) +
              "\nblock_rc=$?\nprintf 'AFTER unpublished=[%s]\\n' \"${handoff_unpublished-<unset>}\"\n"
              "exit \"$block_rc\"\n")
    return box.run(shell, script, _answers(publish_rc, intent_rc, err))


#: What the block's caller sees bound where no gap is: nothing, or not bound.
NO_GAP = {"AFTER unpublished=[]", "AFTER unpublished=[<unset>]"}


def _the_one(box: Sandbox, verb: str) -> Call:
    found = [c for c in box.recorded() if c.argv and c.argv[0] == verb]
    assert len(found) == 1, (verb, box.recorded())
    return found[0]


@pytest.mark.parametrize("shell", SHELLS)
def test_step_2_goes_on_past_a_refusal_over_a_log_nobody_could_read_and_names_the_gap(
        box: Sandbox, shell: str) -> None:
    """RED at 969806f (lane 3's ruling 651). `publish-handoff` refuses, and
    `restart-intent` says why: 10, the lane's log could not be read. Step 2
    goes on - the block ends, and what it binds is the gap - and says what was
    not published, that the swap is still written, where the prepared block
    is, and what to wait on before publishing it: the intent, read with no
    fetch, as every read in this skill but the row's is."""
    proc = _step2(box, shell, publish_rc=1, intent_rc=10)
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert f"AFTER unpublished=[{GAP}]" in proc.stdout, (proc.stdout, proc.stderr)
    said = proc.stdout + proc.stderr
    for words in (f"HANDOFF NOT PUBLISHED: {GAP}", WAIT_ON, f"{box.root}/prepared.md",
                  "step 4 still writes the PAUSED record, the register line and the row",
                  "skip the commit below"):
        assert words in said, (words, said)
    assert box.verbs() == ["publish-handoff", "restart-intent"], box.recorded()
    assert _the_one(box, "restart-intent").no_fetch == "1"


@pytest.mark.parametrize("shell", SHELLS)
def test_step_2_publishes_as_it_did_where_the_publisher_answers(box: Sandbox, shell: str) -> None:
    """THE CONTROL: a publication that lands binds no gap - empty, or not
    bound at all, which step 4 reads alike - asks nothing more and says
    nothing more."""
    proc = _step2(box, shell, publish_rc=0, intent_rc=8)
    assert proc.returncode == 0, (proc.returncode, proc.stderr)
    assert NO_GAP & set(proc.stdout.splitlines()), proc.stdout
    assert "NOT PUBLISHED" not in proc.stdout + proc.stderr
    assert box.verbs() == ["publish-handoff"], box.recorded()


@pytest.mark.parametrize("shell", SHELLS)
def test_step_2_takes_no_other_refusal_for_the_gap(box: Sandbox, shell: str) -> None:
    """AND ONLY THAT REFUSAL IS THE GAP: a publication refused because a
    restart that was READ owns the lane (7, the intent `preparing`) is the
    helper's own refusal, in its own words, and binds no gap - R7 writes the
    swap over a log nobody could read, never over a restart somebody can. So
    the refusal STOPS the skill: the block exits with the helper's own status,
    7 (lane 3's review of R7, finding 1001: on the skill's ordinary path
    nothing reads the restart intent before step 2, so this refusal is the one
    guard, and a block that exited 0 let step 4 write the PAUSED record, a
    false `; handoff refreshed` and the row over a restart somebody can read;
    `lane-handoff` refuses the same case before any write)."""
    proc = _step2(box, shell, publish_rc=7, intent_rc=0,
                  err="an active restart owns this handoff; nothing was published")
    assert proc.returncode == 7, (proc.returncode, proc.stdout, proc.stderr)
    assert NO_GAP & set(proc.stdout.splitlines()), (proc.stdout, proc.stderr)
    assert "an active restart owns this handoff" in proc.stderr, proc.stderr
    assert "NOT PUBLISHED" not in proc.stdout + proc.stderr


def _step4(box: Sandbox, shell: str, unpublished: Optional[str]) -> subprocess.CompletedProcess:
    script = (_bound(box) +
              (f'handoff_unpublished="{unpublished}"\n' if unpublished is not None else "") +
              _block(STEP4))
    proc = box.run(shell, script)
    assert proc.returncode == 0, (proc.returncode, proc.stderr)
    return proc


@pytest.mark.parametrize("shell", SHELLS)
def test_step_4_says_the_handoff_was_not_published_where_step_2_published_nothing(
        box: Sandbox, shell: str) -> None:
    """RED at 969806f (651). Step 4 wrote `; handoff refreshed` whatever step 2
    had done. Where step 2 bound the gap, the register line ends in R7's words
    - the words `lane-handoff` writes, which are in its own file - and the
    PAUSED record and the row are still written (`R-A11-11`)."""
    _step4(box, shell, GAP)
    line = _the_one(box, "append-line")
    assert line.argv[1:] == [f"PAUSED — lane {LANE}, session {UUID}@Eagle, {NOW}, "
                             f"a usage reset kind unknown{R7_TAIL}"], line.argv
    assert box.verbs() == ["lane-dir", "log", "append-line", "set-row-state"], box.recorded()
    assert LANE_HANDOFF.read_text(encoding="utf-8").count(R7_TAIL.lstrip("; ")) == 1, (
        "lane-handoff no longer writes the same words in the same case: the two "
        "surfaces of one act were held to one line")


@pytest.mark.parametrize("shell", SHELLS)
def test_step_4_still_says_refreshed_where_step_2_published(box: Sandbox, shell: str) -> None:
    """THE CONTROL, with the gap bound empty as step 2 binds it after a
    publication that landed."""
    _step4(box, shell, "")
    assert _the_one(box, "append-line").argv[1:] == [
        f"PAUSED — lane {LANE}, session {UUID}@Eagle, {NOW}, "
        "a usage reset kind unknown; handoff refreshed"]


@pytest.mark.parametrize("shell", SHELLS)
def test_steps_2_and_4_in_one_shell_write_the_swap_and_name_the_gap(box: Sandbox,
                                                                    shell: str) -> None:
    """RED at 969806f. Steps 2 and 4 in ONE shell, as a session runs them, so
    what step 2 decides is what step 4 writes: the publication refused over a
    log nobody could read, then the PAUSED record, the register line naming
    the gap and the row - the swap written, the gap named."""
    script = _bound(box) + _block(PUBLISH) + "\n" + _block(STEP4)
    proc = box.run(shell, script, _answers(1, 10))
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert box.verbs() == ["publish-handoff", "restart-intent", "lane-dir", "log",
                           "append-line", "set-row-state"], box.recorded()
    assert _the_one(box, "append-line").argv[-1].endswith(R7_TAIL), box.recorded()
