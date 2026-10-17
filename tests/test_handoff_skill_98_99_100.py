# SPDX-License-Identifier: Apache-2.0
"""`skills/handoff/SKILL.md`, held to three findings of opensoft/workBenches#93's
audit of it (opensoft/openRepoTools#98, #99 and #100), in seconds rather than
the shell suite's hour. The skill is prose a session follows, so what can be
RUN is run: the fenced blocks are extracted from the file and executed under
bash against a stub `lanes-edit.sh` that records every call it is given, and
what cannot is read as text.

  * #98 — a lane that has NEVER HAD A SESSION RECORDED has no uuid in its row,
    and `R-A11-5` says the skill refuses before it writes, naming the act that
    supplies one, and names the gap in the handoff, exactly as `R-A11-14` does
    for a missing workstation. Step 2 sets `$uuid_missing`; step 4 then writes
    neither the object-log `PAUSED` (the writer refuses a `session` field that
    is not a transcript uuid) nor the register's file-level line (which would
    read `session @<ws>`), and still sets the row's state cell, as
    `lane-handoff` does.
  * #99 — a comment said `(c) below still runs` of a swap with no workstation,
    the promise `R-A11-27` exists to refuse: the code gates (c) behind
    `$ws_missing` with (a) and (b). The code is run here, so the comment is
    held to what the code does.
  * #100 — `$L` was `~/projects/xFactory/lanes-edit.sh` alone, where every
    sibling resolves `lanes-edit.sh` on `PATH` first, `/restart` included.

NOTHING HERE TOUCHES A REAL REGISTER OR A REAL `$HOME`: the helper is a stub,
`tmux` is a stub that answers nothing, and every path is under `tmp_path`.
"""

from __future__ import annotations

import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None, reason="the skill's steps are bash")]

BASH = shutil.which("bash") or "bash"
ZSH = shutil.which("zsh")

#: zsh is a session's own shell and the one its Bash tool runs in, so a block a
#: session pastes runs under it, and it differs from bash where this file has
#: tripped before (`BASH_REMATCH` is empty there; zsh fills `$match`). The
#: blocks are held to the same answers under both wherever zsh is installed.
NEEDS_ZSH = pytest.mark.skipif(
    ZSH is None, reason="zsh is not installed, so the skill's blocks are not "
                        "run under a session's own shell")
SKILL = REPO / "skills/handoff/SKILL.md"
RESTART_SKILL = REPO / "skills/restart/SKILL.md"
UUID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
OLDER_UUID = "11111111-2222-4333-8444-555555555555"

#: What a session records the helper's calls as: verb, the `LANES_SESSION` it
#: was handed, then every argument. `lane-dir` answers 8 (no answer) and
#: `register-row` prints `$STUB_ROW` and exits `$STUB_REGISTER_RC`, which are the
#: only two reads these blocks make of it that matter here.
STUB = """#!/usr/bin/env bash
printf '%s\\tsession=[%s]\\t%s\\n' "$1" "${LANES_SESSION-<unset>}" "$*" >> "$STUB_LOG"
case "$1" in
  lane-dir) exit 8 ;;
  register-row) [ -z "${STUB_ROW:-}" ] || printf '%s\\n' "$STUB_ROW"; exit "${STUB_REGISTER_RC:-0}" ;;
esac
exit 0
"""


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _blocks(text: str) -> list[str]:
    return re.findall(r"^```(?:sh|bash)\n(.*?)\n```$", text,
                      re.DOTALL | re.MULTILINE)


def _block(marker: str) -> str:
    found = [b for b in _blocks(_text()) if marker in b]
    assert len(found) == 1, (
        f"expected exactly one fenced block of {SKILL.name} carrying "
        f"{marker!r}, found {len(found)}: this test is stale")
    return found[0]


def _section(heading: str) -> str:
    """The prose-and-code of one numbered `## <n>. …` step of the skill. It
    ends at the next NUMBERED step, because the handoff's own template, in a
    fence of step 2, opens with a `## RESUME PROMPT` of its own."""
    text = _text()
    start = text.index(heading)
    end = re.compile(r"\n## \d+\. ").search(text, start + 1)
    return text[start:end.start() if end else len(text)]


def _row(session_cell: str) -> str:
    return (f"| `repoHS-1` | {session_cell} | Eagle / test / brett | "
            "2026-09-11T00:00Z | none | handoffs/repoHS/repoHS-1.md | ACTIVE |")


class Estate:
    """A stub helper and a hermetic environment for running a skill block."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.bin = root / "bin"
        self.bin.mkdir()
        self.log = root / "calls.tsv"
        self.log.write_text("")
        self.helper = self.bin / "lanes-edit.sh"
        self.helper.write_text(STUB)
        # A `tmux` that answers nothing, so the host's own server is never read.
        (self.bin / "tmux").write_text("#!/bin/sh\nexit 1\n")
        for tool in (self.helper, self.bin / "tmux"):
            tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
        self.home = root / "home"
        self.home.mkdir()

    def run(self, script: str, row: str = "", extra: dict | None = None,
            shell: str = "bash") -> subprocess.CompletedProcess:
        env = {"HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin",
               "STUB_LOG": str(self.log), "STUB_ROW": row,
               "TMPDIR": str(self.home), **(extra or {})}
        argv = [BASH, "-c", script] if shell == "bash" else [ZSH, "-f", "-c", script]
        return subprocess.run(argv, env=env, cwd=str(self.home),
                              capture_output=True, text=True, check=False)

    def calls(self) -> list[tuple[str, str, str]]:
        out = []
        for line in self.log.read_text(encoding="utf-8").splitlines():
            verb, session, args = line.split("\t", 2)
            out.append((verb, session, args))
        return out

    def verbs(self) -> list[str]:
        return [verb for verb, _, _ in self.calls()]


@pytest.fixture
def estate(tmp_path: Path) -> Estate:
    return Estate(tmp_path)


# --- #100: `$L` is resolved PATH-first, the way `/restart` resolves it --------

def _l_assignment(path: Path) -> str:
    for block in _blocks(path.read_text(encoding="utf-8")):
        for line in block.splitlines():
            if line.startswith("L="):
                return line
    raise AssertionError(f"{path.name} has no `L=` assignment in a fenced block")


def test_the_helper_is_resolved_the_way_the_restart_skill_resolves_it():
    handoff, restart = _l_assignment(SKILL), _l_assignment(RESTART_SKILL)
    assert "command -v lanes-edit.sh" in restart, (
        "the sibling this is held to no longer resolves the helper on PATH")
    assert handoff == restart, (
        "the handoff skill and the restart skill resolve `$L` differently:\n"
        f"  handoff: {handoff}\n  restart: {restart}")


@pytest.mark.parametrize("on_path", [True, False])
def test_the_helper_on_path_wins_and_the_symlink_is_the_fallback(estate, on_path):
    script = f'{_l_assignment(SKILL)}\nprintf "%s" "$L"'
    env_path = str(estate.bin) if on_path else str(estate.home / "empty")
    (estate.home / "empty").mkdir()
    proc = subprocess.run([BASH, "-c", script],
                          env={"HOME": str(estate.home), "PATH": env_path},
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    want = (str(estate.helper) if on_path
            else str(estate.home / "projects/xFactory/lanes-edit.sh"))
    assert proc.stdout == want, (
        f"`$L` came out {proc.stdout!r}, wanted {want!r}")


def test_the_prose_says_where_the_helper_is_found():
    prose = _text()[:_text().index("```sh")]
    sentence = re.search(r"`\$L`.*?\.(?=\s)", prose, re.DOTALL)
    assert sentence, "the sentence that introduces `$L` is gone"
    assert "PATH" in sentence.group(0) and "symlink" in sentence.group(0), (
        "the sentence introducing `$L` must say it is found on PATH first and "
        f"the symlink second, to agree with the line under it: {sentence.group(0)!r}")


# --- #99: no comment promises that (c) runs where there is no workstation ----

def test_no_line_promises_that_the_row_flip_runs_without_a_workstation():
    lines = _text().splitlines()
    promises = [n + 1 for n, line in enumerate(lines)
                if "still does (c)" in line
                or ("(c) below still runs" in line and "promised" not in line)]
    assert not promises, (
        "these lines assert as current fact what R-A11-27 refuses (the code "
        f"gates (c) behind $ws_missing with (a) and (b)): {promises}")


def test_the_comments_name_all_three_writes_a_missing_workstation_stops():
    text = _text()
    after = text[text.index("`workstation <ws>` is NOT omitted"):]
    assert "(a), (b) and (c)" in after[:after.index("payload=")], (
        "the comment on the `workstation` sub-field must say that (a), (b) and "
        "(c) all stop where there is none (ruling 11, R-A11-27)")
    before = text[:text.index("ws_missing=\"\"")]
    assert "skips (a), (b) and (c)" in before[before.rindex("# AND IT NEVER WRITES"):], (
        "step 1's comment must say step 4 skips (a), (b) and (c) alike")


def _step4(estate: Estate, *, uuid: str, ws_missing: str = "",
           uuid_missing: str = "") -> subprocess.CompletedProcess:
    block = _block("# (c) the row: ONE WRITE")
    script = "\n".join([
        f'L="{estate.helper}"', "lane=repoHS-1", "ws=Eagle", 'why="a usage reset"',
        f'uuid="{uuid}"', f'ws_missing="{ws_missing}"',
        f'uuid_missing="{uuid_missing}"', block,
        'printf "row_write_refused=[%s]\\n" "$row_write_refused"'])
    proc = estate.run(script)
    assert proc.returncode == 0, proc.stderr
    return proc


def test_with_a_workstation_and_a_session_all_three_writes_are_made(estate):
    """THE CONTROL: the harness records what step 4 really calls."""
    proc = _step4(estate, uuid=UUID)
    assert estate.verbs() == ["lane-dir", "log", "append-line", "set-row-state"]
    (_, session, args) = estate.calls()[1]
    assert session == f"session=[{UUID}]" and args.startswith("log PAUSED lane:repoHS-1")
    assert f"session {UUID}@Eagle" in estate.calls()[2][2]
    assert "row_write_refused=[]" in proc.stdout


def test_a_missing_workstation_stops_all_three_register_writes(estate):
    proc = _step4(estate, uuid=UUID, ws_missing="1")
    assert estate.verbs() == ["lane-dir"], estate.calls()
    assert "row_write_refused=[1]" in proc.stdout
    assert "NOT WRITTEN" in proc.stdout


# --- #98: a lane that has never had a session recorded -----------------------

STEP2 = "register-row \"$lane\" 2>/dev/null | grep '^|'"


def _step2(estate: Estate, row: str, *, lane: str = "repoHS-1",
           ws_missing: str = "", extra: dict | None = None,
           shell: str = "bash") -> subprocess.CompletedProcess:
    script = "\n".join([f'L="{estate.helper}"', f"lane={lane}",
                        f'ws_missing="{ws_missing}"', _block(STEP2),
                        'printf "uuid_missing=[%s]\\n" "${uuid_missing:-}"'])
    proc = estate.run(script, row=row, extra=extra, shell=shell)
    assert proc.returncode == 0, proc.stderr
    return proc


def _swap(estate: Estate, row: str, extra: dict | None = None) -> subprocess.CompletedProcess:
    """Step 2 and step 4 in ONE shell, as a session runs them, so what step 2
    decides is what step 4 does."""
    script = "\n".join([
        f'L="{estate.helper}"', "lane=repoHS-1", "ws=Eagle", 'why="a usage reset"',
        'ws_missing=""', _block(STEP2), _block("# (c) the row: ONE WRITE"),
        'printf "uuid_missing=[%s] row_write_refused=[%s]\\n" '
        '"${uuid_missing:-}" "$row_write_refused"'])
    proc = estate.run(script, row=row, extra=extra)
    assert proc.returncode == 0, proc.stderr
    return proc


@pytest.mark.parametrize("cell", [
    "none",
    "harness `unknown`",
    "harness `session_01AbCdEf` / `session_02GhIjKl`",
], ids=["no-session", "the-placeholder", "footer-ids-only"])
def test_a_row_that_records_no_session_uuid_is_flagged_before_any_write(estate, cell):
    proc = _step2(estate, _row(cell))
    assert "uuid=<none>" in proc.stdout
    assert "uuid_missing=[1]" in proc.stdout, proc.stdout
    assert "NO SESSION" in proc.stdout, "the guard must say so, not only flag it"
    assert "lane-start --no-launch" in proc.stdout, (
        "and name the act that supplies a uuid (Amendment 6(c)'s session-cell "
        "append), which is what R-A11-5 asks the skill to do")
    assert estate.verbs() == ["register-row"], (
        f"step 2 only reads; it must write nothing: {estate.calls()}")


@pytest.mark.parametrize("cell", [
    f"harness `{UUID}`",
    f"harness `{OLDER_UUID}` / `{UUID}`",
], ids=["one", "the-last-of-two"])
def test_a_row_that_records_a_session_is_not_flagged_and_says_nothing(estate, cell):
    proc = _step2(estate, _row(cell))
    assert f"uuid={UUID}" in proc.stdout
    assert "uuid_missing=[]" in proc.stdout
    assert "NO SESSION" not in proc.stdout


def test_a_missing_session_stops_the_two_session_keyed_writes_and_keeps_the_row(estate):
    proc = _step4(estate, uuid="", uuid_missing="1")
    assert estate.verbs() == ["lane-dir", "set-row-state"], (
        "with no transcript uuid the writer refuses `log PAUSED` and the "
        "register line would read `session @Eagle`, so neither is attempted, "
        f"while the row's state cell, which keys on no session, is: {estate.calls()}")
    assert not any("session @" in args for _, _, args in estate.calls())
    (_, _, args) = estate.calls()[1]
    assert "PAUSED · swap" in args and "transcript none" in args, args
    assert "row_write_refused=[]" in proc.stdout


def test_a_missing_session_and_a_missing_workstation_stop_every_write(estate):
    proc = _step4(estate, uuid="", ws_missing="1", uuid_missing="1")
    assert estate.verbs() == ["lane-dir"], estate.calls()
    assert "row_write_refused=[1]" in proc.stdout


def test_the_handoff_is_told_to_name_the_missing_session():
    section = _section("## 2. Refresh the handoff")
    prose = re.sub(r"```.*?```", "", section, flags=re.DOTALL)
    assert "$uuid_missing" in prose, (
        "step 2's prose must say what to write in the handoff when the lane "
        "has no session recorded (R-A11-5: *the gap named in the handoff*)")
    paragraph = " ".join(next(p for p in prose.split("\n\n")
                              if "$uuid_missing" in p).split())
    assert "lane-start --no-launch" in paragraph
    assert "NOT written" in paragraph or "NOT made" in paragraph, (
        "the paragraph must say that the object-log and register writes were "
        "not made, so the next session knows the log is behind the handoff")
    assert "`session unknown`" in paragraph and "`session none`" not in paragraph, (
        "the top block's first line carries the word `lane-handoff` writes "
        "(`${uuid:-unknown}`), not another")
    assert "nor the row's state cell" in paragraph, (
        "with the workstation also missing the row's cell is NOT set either, "
        "and the paragraph must not tell the next session it was")


# --- #98, review round: the session's own id answers first; a failed read is
# --- not an answer; the message says only what step 4 will do ----------------

def test_the_sessions_own_id_answers_where_the_row_records_none(estate):
    """`R-A11-5`: *a swap taken by a running session always has a uuid:
    `$CLAUDE_CODE_SESSION_ID` is it … the refusal fires on no ordinary path.*"""
    proc = _swap(estate, _row("none"), extra={"CLAUDE_CODE_SESSION_ID": UUID})
    assert f"uuid={UUID}" in proc.stdout and "uuid_missing=[]" in proc.stdout, proc.stdout
    assert "NO SESSION" not in proc.stdout, proc.stdout
    assert estate.verbs() == ["register-row", "lane-dir", "log", "append-line",
                              "set-row-state"], estate.calls()
    calls = {verb: (session, args) for verb, session, args in estate.calls()}
    assert calls["log"][0] == f"session=[{UUID}]"
    assert f"session {UUID}@Eagle" in calls["append-line"][1]


def test_the_sessions_own_id_beats_the_rows_last_one(estate):
    _swap(estate, _row(f"harness `{OLDER_UUID}`"),
          extra={"CLAUDE_CODE_SESSION_ID": UUID})
    calls = dict((v, s) for v, s, _ in estate.calls())
    assert calls.get("log") == f"session=[{UUID}]", estate.calls()


def test_an_environment_id_that_is_not_a_uuid_is_ignored(estate):
    proc = _swap(estate, _row(f"harness `{UUID}`"),
                 extra={"CLAUDE_CODE_SESSION_ID": "not-a-uuid"})
    assert f"uuid={UUID}" in proc.stdout
    assert dict((v, s) for v, s, _ in estate.calls())["log"] == f"session=[{UUID}]"


def test_neither_id_answering_skips_the_two_writes_and_keeps_the_row(estate):
    """The rare case that is left: no session of its own (a plain shell) and a
    row that records none."""
    proc = _swap(estate, _row("none"))
    assert "uuid_missing=[1]" in proc.stdout and "NO SESSION RECORDED" in proc.stdout
    assert estate.verbs() == ["register-row", "lane-dir", "set-row-state"], estate.calls()


def test_a_failed_row_read_is_not_a_lane_that_never_had_a_session(estate):
    """Amendment 7(d): a read that failed is never an answer. With
    `register-row` exiting 3 and printing nothing there is no row to say it
    records no session; the `$handoff` stop beneath is what handles it."""
    estate.log.write_text("")
    script = "\n".join([f'L="{estate.helper}"', "lane=repoHS-1", 'ws_missing=""',
                        _block(STEP2),
                        'printf "uuid_missing=[%s] handoff=[%s]\\n" '
                        '"${uuid_missing:-}" "$handoff"'])
    proc = estate.run(script, row="", extra={"STUB_REGISTER_RC": "3"})
    assert proc.returncode == 0, proc.stderr
    assert "NO SESSION" not in proc.stdout, proc.stdout
    assert "uuid_missing=[] handoff=[]" in proc.stdout


@pytest.mark.parametrize("ws_missing, says, never", [
    ("", "while the row's state cell still is", "for want of a workstation"),
    ("1", "and neither is the row's state cell, for want of a workstation",
     "still is"),
], ids=["workstation-present", "workstation-also-missing"])
def test_the_message_says_only_what_step_4_will_do_to_the_row(estate, ws_missing,
                                                              says, never):
    proc = _step2(estate, _row("none"), ws_missing=ws_missing)
    assert says in proc.stdout and never not in proc.stdout, proc.stdout
    _step4(estate, uuid="", ws_missing=ws_missing, uuid_missing="1")
    called_row = "set-row-state" in estate.verbs()
    assert called_row == (ws_missing == ""), (
        "the message and step 4 disagree about whether the row's cell is set")


def test_the_command_in_the_message_is_filled_in_from_the_lane(estate):
    proc = _step2(estate, _row("none"), lane="repoHS-17")
    assert "`lane-start --no-launch repoHS 17`" in proc.stdout, proc.stdout
    proc = _step2(estate, _row("none"), lane="odd-lane-name")
    assert "`lane-start --no-launch <repo> <n>`" in proc.stdout, (
        "a lane name that is not <repo>-<n> must not be split into a guess")


@NEEDS_ZSH
@pytest.mark.parametrize("name, row, extra, lane", [
    ("no-session", _row("none"), {}, "repoHS-17"),
    ("no-session-odd-name", _row("none"), {}, "odd-lane-name"),
    ("own-id", _row("none"), {"CLAUDE_CODE_SESSION_ID": UUID}, "repoHS-1"),
    ("row-id", _row(f"harness `{OLDER_UUID}` / `{UUID}`"), {}, "repoHS-1"),
    ("failed-read", "", {"STUB_REGISTER_RC": "3"}, "repoHS-1"),
])
def test_step_2_says_the_same_under_zsh_as_under_bash(tmp_path, name, row, extra, lane):
    """The restart command was filled from `BASH_REMATCH`, which zsh does not
    set: under it the message named a `lane-start --no-launch` with both
    fields empty, and the tests, which ran bash only, never saw it."""
    under_bash = _step2(Estate(tmp_path / "b"), row, lane=lane, extra=extra)
    under_zsh = _step2(Estate(tmp_path / "z"), row, lane=lane, extra=extra,
                       shell="zsh")
    assert under_zsh.stdout == under_bash.stdout, (
        f"zsh and bash disagree:\n--- bash\n{under_bash.stdout}\n--- zsh\n"
        f"{under_zsh.stdout}")
    if name == "no-session":
        assert "`lane-start --no-launch repoHS 17`" in under_zsh.stdout
    if name == "no-session-odd-name":
        assert "`lane-start --no-launch <repo> <n>`" in under_zsh.stdout
