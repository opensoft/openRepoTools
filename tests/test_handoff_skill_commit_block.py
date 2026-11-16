# SPDX-License-Identifier: Apache-2.0
"""`skills/handoff/SKILL.md`'s step-2 write: ONE call to `write-handoff`, held to
Amendment 23 (opensoft/openRepoTools#198, slice 3) in seconds rather than the
shell suite's hour.

The skill used to publish its handoff and then COMMIT it itself:

    cd <the checkout that holds the handoff>
    git add "$handoff"
    git commit -m "handoff(<lane>@<ws>): PAUSED, <one-line state>" -m "Lane: <lane>" -- "$handoff"
    git pull --rebase origin main && git push origin main

opensoft/openRepoTools#197 made that block resolve its checkout (`$LANES_REPO`,
then the helper's `workspace-root`), refuse a staged entry it did not make and
an operation in progress, and abort a conflicted rebase. It was still one of
the three writers that commit to a checkout with NO LOCK and then pull and push
(finding 282 of the review of #307, with `lane-start`'s stamp and
`lane-handoff`'s PAUSED commit), and its fallback could land in W, the readers'
copy (Amendment 23 S5). Slice 2a gave the one act that replaces all of it:

    handoff-path <lane> --create                                  where the file is
    write-handoff <lane> --prepend <block file> --subject <s>

which takes the lane checkout's lock, brings the checkout to origin, reads the
handoff there, puts the new top block, `---` and a blank line in front of it,
proves the old file survives, replaces the file atomically, commits it by its
own pathspec with the `Lane:` trailer, pushes, reads origin back and replays a
refused push (lane openRepoTools-3's finding 981 on #311, option (a): the
`--whole` call this file held before took a file the session had glued
together, and a block with no final newline merged into the old one). So this
file holds the skill's two blocks to what is left of them: derive the path,
send the call with exactly those arguments, say what each exit means and never
stop the swap (`R-A11-11`), and spell no checkout of its own.

THE BLOCKS ARE RUN, NOT READ, under `bash` and under `zsh` where one is
installed, because the Bash tool runs a skill's block under the user's own
shell. Two layers:

  * against a STUB `lanes-edit.sh` that answers `handoff-path` and
    `write-handoff`, logs every argv and the `LANES_LANE` it was called under,
    and exits as each case says: the arguments, the words and the exits;
  * against the REAL `lanes-edit.sh` in slice 2a's sandbox
    (`tests/test_a23_write_handoff.py`'s `Box`: a bare origin, W, the lane's
    row and handoff, `LANES_ROUTE_WRITES=1`): the handoff is pushed from the
    lane's own checkout C, and W is untouched.

NOTHING HERE READS THE CALLER'S ENVIRONMENT OR TOUCHES A REAL REGISTER, W OR
GITHUB. Every environment is an explicit dict (no `LANES_*`, no `TMUX*`, `HOME`
under `tmp_path`), the stub helper and `tmux` live under `tmp_path`, and the
real helper runs only in the sandbox, whose `gh` and `tmux` refuse.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from test_a23_write_handoff import (BLOCK, HANDOFF, HANDOFF_REL, Box as RealBox, _other_repository,
                                   prepended)

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the skill's blocks are shell, and the sandbox runs git")]

SKILL = REPO / "skills/handoff/SKILL.md"
HELPER = REPO / "lanes-edit.sh"

#: Each carried by exactly one shell block of the skill: how the blocks are found.
B1 = 'handoff_file="$(LANES_READ_MIRROR=1 "$L" handoff-path "$lane" --create)"'
B2 = '--prepend "$block_file"'
STEP4 = "# (c) the row: ONE WRITE"

LANE = "repoHS-1"
UUID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
OLD = ("Lane: repoHS-1 (p, session s) — single-use resume prompt\n\n"
       "## RESUME PROMPT — PAUSED, the old block\n\nthe old state\n")
#: The session's new top block, which it writes to `$block_file`, and the
#: complete new file `write-handoff --prepend` makes of it under its lock.
TOP = ("Lane: repoHS-1 (p, session s) — single-use resume prompt\n\n"
       "## RESUME PROMPT — PAUSED, the new block\n\n")

SHELLS = [
    pytest.param("bash", id="bash"),
    pytest.param("zsh", id="zsh", marks=pytest.mark.skipif(
        shutil.which("zsh") is None, reason="no zsh here")),
]


# --- the skill's text, as the file holds it ----------------------------------

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
    """The prose-and-code of one numbered `## <n>. …` step of the skill; it
    ends at the next NUMBERED step, because the handoff's own template opens
    with a `## RESUME PROMPT` of its own."""
    text = _text()
    start = text.index(heading)
    end = re.compile(r"\n## \d+\. ").search(text, start + 1)
    return text[start:end.start() if end else len(text)]


def _prose(heading: str) -> list[str]:
    """A step's paragraphs with their fences cut out and their lines joined."""
    prose = re.sub(r"```.*?```", "", _section(heading), flags=re.DOTALL)
    return [" ".join(p.split()) for p in prose.split("\n\n") if p.strip()]


def _code_lines(blocks: list[str]) -> list[str]:
    return [line for block in blocks for line in block.splitlines()
            if not line.lstrip().startswith("#")]


# --- a stub helper that logs what it is asked, and answers what a case says ---

#: The interpreter that is running pytest, so the stub needs nothing on PATH.
#: Since feature 007's T431, step 4 opens with its own base and reads the
#: identity again, so two verbs answer what a lane's own window would get (R-Q23;
#: lane 2 reviews these stub hunks): `register-row` the lane's row for the
#: window's name, `$STUB_WINDOW`, and nothing for any other name; and
#: `canon-lane` the name it was given. `window-lane` and `swapped` keep the
#: stub's 2: the ladder asks them only where the window's name has NO row, and
#: `register-row` answers for `$STUB_WINDOW`, the name `tmux` gives, so no case asks.
STUB = f"""#!{sys.executable}
import json, os, sys
argv = sys.argv[1:]
rec = {{"argv": argv, "lane": os.environ.get("LANES_LANE"),
       "no_fetch": os.environ.get("LANES_NO_FETCH")}}
if argv[:1] == ["write-handoff"] and "--prepend" in argv:
    try:
        with open(argv[argv.index("--prepend") + 1], "rb") as f:
            rec["block"] = f.read().decode("utf-8")
    except (OSError, IndexError):
        rec["block"] = None
with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(rec) + "\\n")
verb = argv[0] if argv else ""
if verb == "handoff-path":
    if os.environ.get("STUB_HP_ERR"):
        print(os.environ["STUB_HP_ERR"], file=sys.stderr)
    if os.environ.get("STUB_HP_OUT"):
        print(os.environ["STUB_HP_OUT"])
    sys.exit(int(os.environ.get("STUB_HP_RC", "0")))
if verb == "write-handoff":
    if os.environ.get("STUB_WH_OUT"):
        print(os.environ["STUB_WH_OUT"])
    sys.exit(int(os.environ.get("STUB_WH_RC", "0")))
if verb == "register-row":
    if argv[1:2] == [os.environ.get("STUB_WINDOW", "")]:
        print("| `" + argv[1] + "` | row |")
    sys.exit(0)
if verb == "canon-lane":
    print(argv[1] if len(argv) > 1 else "")
    sys.exit(0)
if verb in ("log", "append-line", "set-row-state"):
    sys.exit(0)
sys.exit(8 if verb == "lane-dir" else 2)
"""

#: A `tmux` that answers only the window's name, which is the lane's own, as a
#: lane window's is (Amendment 8(b)); every other question gets nothing, so the
#: host's own server is never read.
TMUX = """#!/bin/sh
case "$*" in
  *'#W'*) printf '%s\\n' "$STUB_WINDOW" ;;
  *) exit 1 ;;
esac
"""


class Estate:
    """A stub helper, a handoff file, and a hermetic environment."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.bin = root / "bin"
        self.bin.mkdir()
        self.home = root / "home"
        self.home.mkdir()
        self.tmp = root / "tmp"
        self.tmp.mkdir()
        self.log = root / "calls.jsonl"
        self.log.write_text("", encoding="utf-8")
        self.helper = self.bin / "lanes-edit.sh"
        self.helper.write_text(STUB, encoding="utf-8")
        # A `tmux` that answers the window's name and nothing else, so the host's
        # own server is never read.
        (self.bin / "tmux").write_text(TMUX, encoding="utf-8")
        for tool in (self.helper, self.bin / "tmux"):
            tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
        self.handoff = root / "checkout" / "handoffs" / "estate" / f"{LANE}.md"
        self.handoff.parent.mkdir(parents=True)
        self.handoff.write_text(OLD, encoding="utf-8")

    def run(self, shell: str, script: str, **extra: str) -> subprocess.CompletedProcess:
        env = {"HOME": str(self.home), "TMPDIR": str(self.tmp), "STUB_LOG": str(self.log),
               "PATH": os.pathsep.join([str(self.bin), "/usr/bin", "/bin"]),
               "STUB_HP_OUT": str(self.handoff), "STUB_WINDOW": LANE, **extra}
        argv = ["bash", "-c", script] if shell == "bash" else \
            [shutil.which("zsh") or "zsh", "-f", "-c", script]
        return subprocess.run(argv, env=env, cwd=str(self.home), capture_output=True,
                              text=True, check=False, timeout=120)

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in
                self.log.read_text(encoding="utf-8").splitlines()]

    def replay(self, shell: str, proc: subprocess.CompletedProcess) -> dict:
        """Run the one call block 2 printed, as printed, and return the call
        it made (983: a kept block goes into the handoff by that call)."""
        line = _printed_call(proc)
        before = len(self.calls())
        again = self.run(shell, line)
        assert again.returncode == 0, again.stderr
        made = self.calls()[before:]
        assert len(made) == 1, made
        return made[0]

    def verbs(self) -> list[str]:
        return [c["argv"][0] for c in self.calls()]

    def step2(self, *, ws: str = "Eagle", why: str = "'a usage reset'",
              prepare: str = "block") -> str:
        """Step 2 as a session runs it: the first block, the session's own act
        of writing its new top block, and only it, to `$block_file`, then the
        block that makes the one call. `ws` and `why` are shell words, so a
        case can hand the block an ANSI-C string. `prepare` is "block" (as the
        skill says) or "none" (nothing written)."""
        write = {
            "block": f'[ -z "$block_file" ] || printf %s {shlex.quote(TOP)} > "$block_file"',
            "none": ":",
        }[prepare]
        return "\n".join([f"L={shlex.quote(str(self.helper))}", f"lane={LANE}", f"ws={ws}",
                          f"why={why}", _block(B1), write, _block(B2),
                          'printf "AFTER\\n"'])

    def tool(self, name: str, script: str) -> None:
        """A tool of that name first on the blocks' PATH, ahead of the host's."""
        path = self.bin / name
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def step4(self, *, ws_missing: str = "", uuid_missing: str = "",
              hf_record: str | None = None) -> str:
        """Step 4's block. `hf_record`, where given, is set as a session sets
        block 2's last printed line in the shell that runs step 4 (984)."""
        carried = [] if hf_record is None else [f"hf_record={shlex.quote(hf_record)}"]
        return "\n".join([f"L={shlex.quote(str(self.helper))}", f"lane={LANE}", "ws=Eagle",
                          'why="a usage reset"', f'uuid="{UUID}"', f'ws_missing="{ws_missing}"',
                          f'uuid_missing="{uuid_missing}"', *carried, _block(STEP4),
                          'printf "row_write_refused=[%s]\\n" "$row_write_refused"'])


@pytest.fixture
def estate(tmp_path: Path) -> Estate:
    return Estate(tmp_path)


def _write_call(estate: Estate) -> dict:
    found = [c for c in estate.calls() if c["argv"][0] == "write-handoff"]
    assert len(found) == 1, estate.calls()
    return found[0]


# --- the call: the arguments, and nothing else -------------------------------

@pytest.mark.parametrize("shell", SHELLS)
def test_block_calls_write_handoff_with_prepend_and_the_block_file(estate, shell):
    """The handoff's place is asked of `handoff-path --create`, and
    `write-handoff` is called ONCE with `--prepend` and the block file block 1
    printed, which holds the session's new top block and only it, and the
    subject: the lane, the workstation and the why. No digest is sent: the verb
    reads the handoff itself, under its lock (lane openRepoTools-3's finding 981
    on #311, option (a)). `LANES_LANE` is the lane."""
    proc = estate.run(shell, estate.step2(), STUB_WH_OUT=f"{estate.handoff}\tdeadbeef")
    assert proc.returncode == 0, proc.stderr
    assert estate.verbs() == ["handoff-path", "write-handoff"], estate.calls()
    assert estate.calls()[0]["argv"] == ["handoff-path", LANE, "--create"]
    call = _write_call(estate)
    assert call["argv"] == ["write-handoff", LANE, "--prepend", _block_file(proc), "--subject",
                            f"handoff({LANE}@Eagle): PAUSED, a usage reset"], call["argv"]
    assert call["block"] == TOP, "the file sent is the session's new top block, and only it"
    assert Path(_block_file(proc)).parent == estate.tmp, "the block file is a temporary one"
    assert call["lane"] == LANE
    assert f"handoff written: {estate.handoff}" in proc.stdout, proc.stdout
    assert proc.stdout.endswith("AFTER\n")
    assert estate.handoff.read_text(encoding="utf-8") == OLD, (
        "the skill never writes the handoff itself: the verb does")


@pytest.mark.parametrize("shell", SHELLS)
def test_no_digest_is_read_and_no_new_file_is_built(estate, shell):
    """981, option (a): the skill reads no digest and builds no complete new
    file, so a `sha256sum` or `shasum` it would ask is never asked, the one
    temporary file it makes is the block file, and none of `--whole`,
    `--expect-digest`, `prior_sha256` or `prepared_file` is left in either
    block for a later edit to send."""
    for tool in ("sha256sum", "shasum"):
        estate.tool(tool, f'#!/bin/sh\necho "w3 shim {tool} asked" >&2\nexit 1\n')
    proc = estate.run(shell, estate.step2(), STUB_WH_OUT=f"{estate.handoff}\tdeadbeef")
    assert proc.returncode == 0, proc.stderr
    assert "w3 shim" not in proc.stderr, proc.stderr
    assert [p.name.split(".")[0] for p in estate.tmp.iterdir()] == ["handoff-block"], (
        list(estate.tmp.iterdir()))
    code = "\n".join(_code_lines([_block(B1), _block(B2)]))
    for gone in ("--whole", "--expect-digest", "prior_sha256", "prepared_file", "sha256sum", "shasum"):
        assert gone not in code, f"step 2's blocks still say {gone!r}"


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("ws, why, subject", [
    ("Eagle", "'a usage reset'", f"handoff({LANE}@Eagle): PAUSED, a usage reset"),
    ("''", "''", f"handoff({LANE}@unknown): PAUSED, handoff"),
    ("Eagle", "$'a\\tb\\x1bc'", f"handoff({LANE}@Eagle): PAUSED, a b c"),
    ("Eagle", "'reset — switch'", f"handoff({LANE}@Eagle): PAUSED, reset — switch"),
], ids=["a-why", "no-workstation-no-why", "control-characters-as-spaces", "a-dash-is-kept"])
def test_the_subject_is_one_line_with_no_control_character(estate, shell, ws, why, subject):
    """The verb exits 64 on a control character in the subject and writes
    nothing, so a why with a stray tab would cost the swap its handoff: it is
    made a space, not refused over. A why the operator did not give is
    `handoff`, and a missing workstation is `unknown`: 2b's `lane-handoff`
    writes the same act's subject so (`subject_text`, `${ws:-unknown}`), and
    the two writers of one act spell it one way (rv3's NIT 1 on #311)."""
    estate.run(shell, estate.step2(ws=ws, why=why))
    assert _write_call(estate)["argv"][-1] == subject


@pytest.mark.parametrize("shell", SHELLS)
def test_no_spelled_checkout_and_no_workspace_root_fallback(estate, shell):
    """No checkout path is written anywhere in the skill, none is taken from
    the environment, and the helper's `workspace-root` is never asked: a caller's
    `LANES_REPO` changes nothing about what is called."""
    text = _text()
    for spelled in ("~/projects/brett-wip", "workspace-root", "LANES_REPO", "LANES_BRANCH"):
        assert spelled not in text, f"{SKILL.name} still says {spelled!r}"
    blocks = _blocks(text)
    git_writes = [line.strip() for line in _code_lines(blocks)
                  if re.search(r"\bgit\b[^\n]*\b(add|commit|pull|push|rebase|merge|reset|"
                               r"checkout|stash|cherry-pick|clean|restore)\b", line)]
    assert not git_writes, f"a shell block of the skill runs a git write: {git_writes}"
    step2 = [b for b in blocks if b in (_block(B1), _block(B2))]
    assert not [line for line in _code_lines(step2) if re.match(r"\s*cd\b", line)], (
        "step 2 changes directory: it has no checkout of its own")
    def shape() -> list[dict]:
        """The calls, the temporary file's random name aside."""
        out = []
        for call in estate.calls():
            argv = list(call["argv"])
            if argv[0] == "write-handoff":
                argv[3] = "<block file>"
            out.append(dict(call, argv=argv))
        return out

    estate.run(shell, estate.step2(), STUB_WH_OUT=f"{estate.handoff}\tx")
    plain = shape()
    estate.log.write_text("", encoding="utf-8")
    estate.run(shell, estate.step2(), STUB_WH_OUT=f"{estate.handoff}\tx",
               LANES_REPO=str(estate.root / "elsewhere"), LANES_BRANCH="not-main")
    assert "workspace-root" not in estate.verbs(), estate.calls()
    assert shape() == plain, "an ambient LANES_REPO changed the call"


def test_the_variables_the_call_names_are_defined_in_block_1():
    """`publish-handoff "$lane" "$handoff_file" "$prepared_file" --expect-digest
    "$prior_sha256"` used its three variables without defining any of them.
    The call `--prepend` makes names two, and block 1 defines both."""
    code = "\n".join(_code_lines([_block(B1)]))
    for name in ("handoff_file", "block_file"):
        assert re.search(rf"(?m)^\s*{name}=", code), f"no block defines ${name}"
    assert "publish-handoff" not in "\n".join(_blocks(_text())), (
        "the old call is gone: write-handoff is the one act")


def test_the_blocks_parse_under_bash(tmp_path):
    for name, marker in (("first", B1), ("second", B2)):
        script = tmp_path / f"{name}.sh"
        script.write_text(_block(marker) + "\n", encoding="utf-8")
        proc = subprocess.run(["bash", "-n", str(script)], capture_output=True,
                              text=True, check=False)
        assert proc.returncode == 0, proc.stderr


# --- step 4's three register writes carry `LANES_LANE` -----------------------

@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("ambient", [None, "some-other-lane"], ids=["unset", "another-lane"])
def test_step4_writes_carry_LANES_LANE(estate, shell, ambient):
    """`log`, `append-line` and `set-row-state` each run under the lane being
    swapped, whatever the caller's environment says: a register write goes
    through that lane's checkout and attributes its commit to it (Amendment 23
    S2), and `append-line` finds its lane from the variable first."""
    extra = {} if ambient is None else {"LANES_LANE": ambient}
    proc = estate.run(shell, estate.step4(), **extra)
    assert proc.returncode == 0, proc.stderr
    writes = {c["argv"][0]: c["lane"] for c in estate.calls()
              if c["argv"][0] in ("log", "append-line", "set-row-state")}
    assert writes == {"log": LANE, "append-line": LANE, "set-row-state": LANE}, estate.calls()


def test_every_register_write_and_the_handoff_write_names_its_lane_in_the_text():
    """The text holds the same line for the next verb that joins the list."""
    calls = [line.strip() for line in _code_lines(_blocks(_text()))
             if re.search(r'"\$L" (log|append-line|set-row-state|write-handoff)\b', line)]
    assert len(calls) == 4, calls
    for call in calls:
        assert 'LANES_LANE="$lane"' in call, f"this call does not name its lane: {call}"


# --- step 4 reads the identity again and refuses a lane it did not bind ------

#: The verbs that write: the swap's three register writes (step 4) and the
#: handoff's one (step 2). Anything else the stub logs is a read.
WRITE_VERBS = ("log", "append-line", "set-row-state", "write-handoff")


@pytest.mark.parametrize("shell", SHELLS)
def test_step4_refuses_2_and_writes_nothing_where_the_window_names_another_lane(estate, shell):
    """Pins step 4's identity refusal (`skills/handoff/SKILL.md`: `REFUSED: step 1
    bound this window to lane ...`, T431's `7c74b907`), which no case reached:
    every other case that runs step 4 ends 0, and the refusal was only ever hit
    as a failure (W36-SKF's 23 cases, before the stub answered the reads).
    `step4()` binds `lane=repoHS-1` as step 1 did, the window's own name answers
    `repoHS-2` (a row and a `canon-lane` name of its own), and the same reads,
    run again after the base, name another lane. So the block ends 2 with that
    text on stderr, has asked the reads and sends no write: no `log`,
    `append-line`, `set-row-state` or `write-handoff`, and the line step 4
    prints last is never printed. Lane 2's SHOULD on `d0bbaeb0` (6867788229:
    "One case with `STUB_WINDOW="repoHS-2"` would pin it") and lane 3's word
    (6867841072: a case "that expects 2, the refusal text and no writes, in
    bash and in its zsh twin")."""
    other = "repoHS-2"
    proc = estate.run(shell, estate.step4(), STUB_WINDOW=other)
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    assert (f'REFUSED: step 1 bound this window to lane "{LANE}", and the same reads, run again '
            f'after this block took its base, answer "{other}".') in proc.stderr, proc.stderr
    assert "Nothing of step 4 was written" in proc.stderr, proc.stderr
    asked = [c["argv"] for c in estate.calls()]
    assert ["register-row", other] in asked and ["canon-lane", other] in asked, asked
    assert [v for v in estate.verbs() if v in WRITE_VERBS] == [], estate.calls()
    assert "row_write_refused" not in proc.stdout, "the block ended before its last line"
    assert estate.handoff.read_text(encoding="utf-8") == OLD, "nothing wrote the handoff"


# --- the words: what each exit says, and that the swap goes on ---------------

def _says(estate: Estate) -> dict:
    path = str(estate.handoff)
    return {
        # rv3's NIT 2: the 0 arm claims no push of its own; the verb's note says what it
        # committed and where (an Amendment 8(d) handoff in its own top level, S2).
        # INFO 990 of lane openRepoTools-3's review of #311: a 0 may commit nothing (LANES_NO_GIT=1, an
        # 8(d) handoff in no work tree, a clone of the register not beside W), and the verb's note says so.
        "pushed": (0, True, [f"handoff written: {path} (", "says what was committed and where it was pushed",
                             "or that nothing was committed"],
                   ["HANDOFF NOT", "pushed from the lane checkout", "never committed"]),
        "refused-after-writing": (2, True, [
            "HANDOFF NOT COMMITTED", f"written at {path}, uncommitted", "Nothing was pushed",
            "Do not call it again", "a second copy of it on top"], ["HANDOFF NOT WRITTEN"]),
        "refused-before-writing": (2, False, [
            "HANDOFF NOT WRITTEN", "wrote nothing"], ["HANDOFF NOT COMMITTED"]),
        "pushed-not-confirmed": (3, True, [
            "HANDOFF PUSHED, NOT CONFIRMED", "(exit 3",
            "Do not call it published until it is read back"], []),
        # 982: the 6 arm in the verb's words after 604, where the commit is kept, or that there is none.
        "kept-on-head": (6, True, [
            "HANDOFF NOT PUSHED", "write-handoff exited 6", f"the file is written at {path}.",
            "says where its commit is kept, or that there is none", "on HEAD of the lane checkout",
            "for an Amendment 8(d) handoff, in its own repository", "where its add or its commit failed",
            "Never force"], ["its commit is kept on HEAD of the lane checkout and named above (exit 6)"]),
        # 981, option (a): with `--prepend` no digest is sent, so a 7 is a restart's.
        "owned-by-a-restart": (7, False, [
            "HANDOFF NOT WRITTEN", "an active restart owns this handoff", "(exit 7;",
            "nothing was published", "Do not retry: that restart writes this handoff"],
            ["digest", "WHERE THE HANDOFF IS", "prepared file"]),
        # 981: the verb refuses a block whose last byte is no newline (64), and writes nothing.
        "block-with-no-final-newline": (64, False, [
            "HANDOFF NOT WRITTEN", "(exit 64;", "wrote nothing",
            "Where they say the block does not end with a newline, end it with one (echo >> ",
            "run this block once more, once"], ["the file is written at"]),
        "no-handoff": (8, False, ["HANDOFF NOT PUBLISHED", "exited 8", "nothing was written"],
                       ["the file is written at"]),
        "environment": (1, False, ["HANDOFF NOT PUBLISHED", "exited 1", "nothing was written"],
                        ["the file is written at"]),
        "lock": (4, False, ["HANDOFF NOT PUBLISHED", "exited 4", "nothing was written"],
                 ["the file is written at"]),
        # rv3's SHOULD 4: the `*` arm WITH stdout, a verb that wrote the file and then
        # failed otherwise (1). The path is followed by the sentence's full stop, so a
        # stdout left unsplit (`<file><TAB><sha256>`) is not taken for the path.
        "written-then-failed": (1, True, [
            "HANDOFF NOT PUBLISHED", "exited 1", f"the file is written at {path}."],
            ["nothing was written"]),
    }


CASES = ["pushed", "refused-after-writing", "refused-before-writing", "pushed-not-confirmed",
         "kept-on-head", "owned-by-a-restart", "block-with-no-final-newline", "no-handoff",
         "environment", "lock", "written-then-failed"]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("case", CASES)
def test_each_exit_of_the_verb_is_said_and_the_swap_goes_on(estate, shell, case):
    rc, written, must, never = _says(estate)[case]
    out = f"{estate.handoff}\tdeadbeef" if written else ""
    proc = estate.run(shell, estate.step2(), STUB_WH_RC=str(rc), STUB_WH_OUT=out)
    assert proc.returncode == 0, "the block never stops the swap (R-A11-11)"
    assert proc.stdout.endswith("AFTER\n"), proc.stdout
    for words in must:
        assert words in proc.stdout, f"{case}: {words!r} missing from\n{proc.stdout}"
    for words in never:
        assert words not in proc.stdout, f"{case}: {words!r} must not be said\n{proc.stdout}"
    assert estate.verbs().count("write-handoff") == 1, "one call, and it is never repeated"


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("case", CASES)
def test_the_new_top_block_is_kept_and_named_wherever_nothing_was_written(estate, shell, case):
    """rv3's MUST 1, for the call's own outcomes: where the verb wrote nothing
    (no stdout), the session's new top block is not lost with the swap. The
    block names the temporary file that holds it, the one sent, for the
    report; where the verb wrote the handoff, there is nothing to keep and
    nothing is said of it."""
    rc, written, _, _ = _says(estate)[case]
    out = f"{estate.handoff}\tdeadbeef" if written else ""
    proc = estate.run(shell, estate.step2(), STUB_WH_RC=str(rc), STUB_WH_OUT=out)
    sent = _write_call(estate)["argv"][3]
    assert sent == _block_file(proc)
    kept = f"The new top block is kept at {sent}"
    if written:
        assert kept not in proc.stdout, proc.stdout
    else:
        assert kept in proc.stdout, f"{case}: the top block's file is not named\n{proc.stdout}"
        assert "name that path in the report" in proc.stdout, proc.stdout


def _block_file(proc: subprocess.CompletedProcess) -> str:
    """The `$block_file` block 1 printed for the session to write its top block in."""
    found = re.findall(r"(?m)^block_file=(.+)$", proc.stdout)
    assert len(found) == 1, proc.stdout
    return found[0]


#: The one call a kept top block goes into the handoff by, in lane
#: openRepoTools-3's words (finding 983 on #311): never a hand edit of the
#: handoff, which step 2 forbids ("Do not edit or redirect into the canonical
#: handoff directly"). Block 1 names it so; block 2 prints it filled in.
KEPT_CALL = ('LANES_LANE=<lane> lanes-edit.sh write-handoff <lane> --prepend <block file> '
             '--subject "<subject>"')


def _printed_call(proc: subprocess.CompletedProcess) -> str:
    """The one call block 2 printed, filled in, on a line of its own."""
    found = re.findall(r"(?m)^LANES_LANE=.*$", proc.stdout)
    assert len(found) == 1, proc.stdout
    return found[0]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("extra, prepare", [
    ({"STUB_WH_RC": "7"}, "block"),
    ({"STUB_WH_RC": "64"}, "block"),
    ({"STUB_WH_RC": "2"}, "block"),
    ({"STUB_HP_RC": "8", "STUB_HP_OUT": ""}, "block"),
    ({"STUB_HP_RC": "2", "STUB_HP_OUT": "", "STUB_HP_ERR": "a name refused"}, "block"),
    ({}, "none"),
], ids=["owned-by-a-restart", "block-with-no-final-newline", "refused-before-writing", "not-found",
        "read-failed", "never-prepared"])
def test_a_kept_block_goes_into_the_handoff_by_the_one_call_block_2_prints(
        estate, shell, extra, prepare):
    """983 of lane openRepoTools-3's review of #311: every message that keeps
    the new top block said it goes "at the head of the handoff by hand", which
    step 2 forbids. Block 2 now prints the one call that puts it there, filled
    in, on a line of its own, and that line, run as printed, makes exactly the
    call the block makes: the lane, `--prepend` and the block file, and the
    subject."""
    proc = estate.run(shell, estate.step2(prepare=prepare), **extra)
    assert proc.returncode == 0, proc.stderr
    assert "by hand" not in proc.stdout.replace("by this skill or by hand", ""), proc.stdout
    expected = ["write-handoff", LANE, "--prepend", _block_file(proc), "--subject",
                f"handoff({LANE}@Eagle): PAUSED, a usage reset"]
    made = estate.replay(shell, proc)
    assert made["argv"] == expected, made
    assert made["lane"] == LANE, made


@pytest.mark.parametrize("shell", SHELLS)
def test_the_printed_call_carries_a_why_with_quotes_and_dollars_unchanged(estate, shell):
    """The printed call is quoted for the shell that runs it: a why that holds
    a quote, a double quote, a `$` and a backtick reaches the verb's subject as
    the block's own call carries it."""
    why = "it's \"$HOME\" `id` a\\b"
    proc = estate.run(shell, estate.step2(why=shlex.quote(why)), STUB_WH_RC="7")
    assert proc.returncode == 0, proc.stderr
    sent = _write_call(estate)["argv"]
    assert sent[-1] == f"handoff({LANE}@Eagle): PAUSED, {why}", sent
    assert estate.replay(shell, proc)["argv"] == sent


def test_a_kept_block_is_never_said_to_go_into_the_handoff_by_hand():
    """983: no line of the skill, prose, comment or message, says the kept
    block is put "at the head of the handoff by hand"; the paragraph under
    WHERE THE HANDOFF IS names the one call instead."""
    flat = " ".join(re.sub(r"(?m)^\s*#\s?", "", _text()).split())
    assert not re.search(r"head of the handoff by hand", flat), "the hand edit is back"
    held = [p for p in _prose("## 2. Refresh the handoff") if "In every one of these cases" in p]
    assert len(held) == 1, held
    assert KEPT_CALL in held[0], held[0]
    assert "never by a hand edit" in held[0], held[0]


def test_refusal_text_keeps_R_A11_11():
    """`R-A11-11`, *a swap is never left unwritten*, is still the text's rule
    about a refusal, a conflict or a rejected push, and says what the verb does
    in each: the file is written and not committed on S3's refusal (2), a refused
    push is replayed or kept and named (6), nothing is forced and no staged
    entry that is not the handoff's is ever committed."""
    held = [p for p in _prose("## 2. Refresh the handoff")
            if "does not stop the swap" in p]
    assert len(held) == 1, held
    paragraph = held[0]
    for words in ("R-A11-11", "a swap is never left unwritten", "(2)", "has still written the handoff",
                  "commits nothing", "git's own words", "replays the write", "(6)",
                  "report carries that line", "Never force", "never commit staged entries you did not make"):
        assert words in paragraph, f"the paragraph no longer says {words!r}:\n{paragraph}"


def test_the_one_call_paragraph_says_what_2a_has_merged_and_not_what_it_once_would():
    """NIT 986 of lane openRepoTools-3's review of #311: "once ... finding 601
    ... is in" and "a restart fence's refusal is 7 too, where it is 2 today"
    were false once 2a's round was merged here. The paragraph says the verb's
    refusals as they are: 601, 602 and 607, each a 2 with nothing written, met
    first by the block under WHERE THE HANDOFF IS."""
    flat = " ".join(re.sub(r"(?m)^\s*#\s?", "", _text()).split())
    for gone in ("is in, so is", "where it is 2 today"):
        assert gone not in flat, f"{gone!r} is back"
    held = [p for p in _prose("## 2. Refresh the handoff")
            if p.startswith("**THE WRITE IS ONE CALL, AND IT COMMITS")]
    assert len(held) == 1, held
    for words in ("(601, ", "(602)", "(607)", "with nothing written",
                  "the block under WHERE THE HANDOFF IS meets them first and this call is not made"):
        assert words in held[0], f"the paragraph no longer says {words!r}:\n{held[0]}"


def test_the_handoff_write_is_said_as_the_verbs_and_not_as_a_commit_of_the_skill():
    """rv3's NIT 3 on #311: step 1's comment, `$ws_missing`'s paragraph and
    step 4's (c) comment called step 2's write a commit "in the LANE'S OWN
    repository", the wording from before Amendment 23. The write is
    `write-handoff`'s, in the lane's own checkout, and it is not among the verbs
    the helper's dispatcher refuses for want of a workstation."""
    flat = " ".join(re.sub(r"(?m)^\s*#\s?", "", _text()).split())
    assert "LANE'S OWN repository" not in flat, "the old wording is back"
    assert flat.count("not one of the writes the helper refuses for want of a workstation") == 3, (
        "step 1, the `$ws_missing` paragraph and step 4 say why the handoff still goes")


# --- where the handoff is not found, and the file the session never wrote ----

#: What the session is told to do with the top block it could not write.
KEEP_IN_REPORT = "put it whole in the report"


def _block_1_line(proc: subprocess.CompletedProcess, opening: str) -> str:
    """Block 1's one line that opens with `opening`."""
    found = [line for line in proc.stdout.splitlines() if line.startswith(opening)]
    assert len(found) == 1, proc.stdout
    return found[0]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("how, extra", [
    ("exit 8: no row, or a row that names no handoff", {"STUB_HP_RC": "8", "STUB_HP_OUT": ""}),
    ("exit 0 and a path that is not a file", {"STUB_HP_OUT": "/nowhere/at/all.md"}),
    ("exit 0 and no path", {"STUB_HP_OUT": ""}),
], ids=["no-handoff", "not-a-file", "no-path"])
def test_a_handoff_that_is_not_found_is_said_and_write_handoff_is_never_called(
        estate, shell, how, extra):
    proc = estate.run(shell, estate.step2(), **extra)
    assert proc.returncode == 0, "the swap goes on"
    assert "HANDOFF NOT FOUND" in proc.stdout, proc.stdout
    assert "HANDOFF READ FAILED" not in proc.stdout, proc.stdout
    assert "HANDOFF NOT WRITTEN" in proc.stdout, proc.stdout
    assert "was NOT called" in proc.stdout, proc.stdout
    assert KEEP_IN_REPORT in proc.stdout, "the new top block is kept in the report"
    assert KEPT_CALL in _block_1_line(proc, "HANDOFF NOT FOUND"), "983: the kept block's one call"
    assert estate.verbs() == ["handoff-path"], estate.calls()
    assert proc.stdout.endswith("AFTER\n")


#: `lanes-edit.sh`'s unknown-subcommand refusal, as a helper predating
#: `handoff-path` (main at `33ce26d`) prints it on stderr, with exit 2.
OLDER_HELPER = ("lanes-edit.sh: unknown subcommand 'handoff-path' "
                "(verify-row|set-row-state|append-line|commit|publish-handoff)")

#: 601's refusal, as slice 2a's `handoff-path` says it from A54 (`6d861d4`) on:
#: the row names a handoff in another checkout of the register beside W, so the
#: path is not printed, with exit 2 (lane openRepoTools-3's correction 6368669583).
ANOTHER_CHECKOUT = (
    "lanes-edit.sh: lane repoHS-1's handoff handoffs/estate/repoHS-1.md is "
    "/w-lanes/repoHS-2/handoffs/estate/repoHS-1.md, in another checkout of the register "
    "beside W (/w), not in the checkout /w-lanes/repoHS-1 this lane's writes go through: "
    "a lane's handoff is written in its own checkout only (Amendment 23 S1, S2): "
    "`write-handoff` refuses it, so no path is printed for a restart to bind or a launch "
    "to read (601). Nothing was written.")

#: 602's refusal (A55): a relative cell whose `.` or `..` components climb out
#: of the lane's checkout, 2 with nothing printed.
CLIMBS_OUT = (
    "lanes-edit.sh: lane repoHS-1's handoff cell ../repoHS-2/handoffs/estate/repoHS-1.md is a "
    "repository-relative spelling, joined to the checkout its writes go through, and its '.' or "
    "'..' components climb out of it: a relative cell names a file of that checkout, never another "
    "repository's (Amendment 23 S2), so write-handoff refuses it too. Nothing was printed.")

#: 607's refusal, which `handoff-path` makes since 2a's A60 (991): a glob
#: character in the handoff's path in the lane's checkout, 2 with no path.
GLOBBED = (
    "lanes-edit.sh: lane repoHS-1's handoff handoffs/estate/repo*.md is handoffs/estate/repo*.md "
    "in the checkout /w-lanes/repoHS-1, with a glob character ('*', '?' or '[') in its path: "
    "`write-handoff` refuses it (607), so no path is printed for a restart to bind or a launch to "
    "read (991). Nothing was written. Name the handoff without one.")

#: What the 2 arm says of a cell `handoff-path` and `write-handoff` both refuse,
#: in the helper's terms (985): another checkout of the register, never 8(d)'s
#: "another repository"; 601, 602 and 607 named; and where the kept block goes.
CELL_REFUSED = [
    "exited 2 (its words are above)",
    "in W or in another checkout of the register beside it (601)",
    "climb out of the lane checkout (602)",
    "holds a glob character (607)",
    "the file it names is not the handoff of this lane: "
    "nothing is to be written there, by this skill or by hand",
    "the new top block goes to the handoff of this lane, in its own checkout, once the handoff "
    "cell of its row is corrected to name it"]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("rc, err, must, never", [
    ("1", "the register could not be read (R22: never 8)",
     ["exited 1 (its words are above)"], ["Update lanes-edit.sh", "step 2 again"]),
    ("2", "the clone of the lane checkout failed",
     ["exited 2 (its words are above)"], ["Update lanes-edit.sh", "step 2 again"]),
    ("2", OLDER_HELPER,
     ["exited 2", "unknown subcommand", "predates handoff-path", "Update lanes-edit.sh",
      "step 2 again"], ["belongs to another repository"]),
    ("2", ANOTHER_CHECKOUT, CELL_REFUSED, ["Update lanes-edit.sh", "step 2 again", "another repository"]),
    ("2", CLIMBS_OUT, CELL_REFUSED, ["Update lanes-edit.sh", "step 2 again", "another repository"]),
    ("2", GLOBBED, CELL_REFUSED, ["Update lanes-edit.sh", "step 2 again", "another repository"]),
    ("4", "the lock that makes the lane checkout is held",
     ["exited 4", "Run step 2 again"], ["Update lanes-edit.sh"]),
    ("64", "usage: handoff-path <lane> [--create]",
     ["exited 64 (its words are above)"], ["Update lanes-edit.sh", "step 2 again"]),
    ("127", "lanes-edit.sh: not found",
     ["exited 127 (its words are above)"], ["Update lanes-edit.sh", "step 2 again"]),
], ids=["unreadable", "clone-failed", "older-helper", "another-checkout", "climbs-out", "globbed",
        "lock", "usage", "no-helper"])
def test_a_read_that_failed_is_never_said_as_no_handoff(estate, shell, rc, err, must, never):
    """rv3's MUST 1 on #311 at `b599ed9`: only `handoff-path`'s 8 is "no
    handoff". Any other exit is a read that FAILED (Amendment 7(d); the verb's
    own "R22: never 8"), and it says so with the code: an older helper's
    unknown-subcommand 2 is told to update `lanes-edit.sh`, and the creation
    lock's 4 to run step 2 again. In every one the call is not made, the
    session is told to keep its new top block in the report, and the swap goes
    on (`R-A11-11`)."""
    proc = estate.run(shell, estate.step2(), STUB_HP_RC=rc, STUB_HP_OUT="", STUB_HP_ERR=err)
    assert proc.returncode == 0, "the swap goes on"
    assert proc.stdout.endswith("AFTER\n"), proc.stdout
    assert "HANDOFF READ FAILED" in proc.stdout, proc.stdout
    assert "The read failed" in proc.stdout, proc.stdout
    assert "HANDOFF NOT FOUND" not in proc.stdout, f"exit {rc} is not 'no handoff'"
    for words in must:
        assert words in proc.stdout, f"{words!r} missing from\n{proc.stdout}"
    for words in never:
        assert words not in proc.stdout, f"{words!r} must not be said\n{proc.stdout}"
    assert "was NOT called" in proc.stdout, proc.stdout
    assert KEEP_IN_REPORT in proc.stdout, "the new top block is kept in the report"
    assert KEPT_CALL in _block_1_line(proc, "HANDOFF READ FAILED"), "983: the kept block's one call"
    assert "write-handoff" not in estate.verbs(), estate.calls()


def test_a_cell_the_translation_refuses_is_said_in_the_helpers_terms():
    """985 of lane openRepoTools-3's review of #311: the 2 arm and the
    paragraph above it called a file in W or in a sibling clone "another
    repository", which is Amendment 8(d)'s term; the helper calls it "another
    checkout of the register". Both now say so, and name 602 (a relative cell
    that climbs out) and 607 (a glob character, refused by `handoff-path` since
    991) beside 601."""
    flat = " ".join(re.sub(r"(?m)^\s*#\s?", "", _text()).split())
    assert "belongs to another repository" not in flat, "8(d)'s term for a sibling checkout is back"
    held = [p for p in _prose("## 2. Refresh the handoff") if "In every one of these cases" in p]
    assert len(held) == 1, held
    for words in ("in another checkout of the register beside it", "(602)", "glob character (607",
                  "is not this lane's handoff"):
        assert words in held[0], f"the paragraph no longer says {words!r}:\n{held[0]}"


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("rc", ["1", "2", "4"])
def test_only_a_2_is_asked_again_and_never_with_create(estate, shell, rc):
    """An older helper's words are read by asking the same read a second time
    with only its stderr kept, as step 1's `sread` does, and only for a 2. The
    second ask is a READ: no `--create`, so a clone that failed is not tried
    again, and the fetch is skipped."""
    estate.run(shell, estate.step2(), STUB_HP_RC=rc, STUB_HP_OUT="", STUB_HP_ERR=OLDER_HELPER)
    asked = [(c["argv"], c["no_fetch"]) for c in estate.calls()]
    if rc == "2":
        assert asked == [(["handoff-path", LANE, "--create"], None),
                         (["handoff-path", LANE], "1")], asked
    else:
        assert asked == [(["handoff-path", LANE, "--create"], None)], asked


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("prepare", ["none"])
def test_a_top_block_the_session_never_wrote_is_never_sent(estate, shell, prepare):
    """`mktemp` makes an empty file, and an empty `$block_file` is no new top
    block: the block does not ask (the verb would refuse it, 1)."""
    proc = estate.run(shell, estate.step2(prepare=prepare))
    assert proc.returncode == 0
    assert "HANDOFF NOT WRITTEN" in proc.stdout, proc.stdout
    assert "was NOT called" in proc.stdout, proc.stdout
    assert estate.verbs() == ["handoff-path"], estate.calls()


# --- step 4's register line says what step 2 did (rv3's SHOULD 3) ------------

#: The register line's last phrase where step 2's one call exited 0.
REFRESHED = "; handoff refreshed"


def _register_line(estate: Estate) -> str:
    found = [c["argv"] for c in estate.calls() if c["argv"][0] == "append-line"]
    assert len(found) == 1, estate.calls()
    return found[0][1]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("extra, written, prepare, ends", [
    ({}, True, True, REFRESHED),
    ({"STUB_WH_RC": "7"}, False, True,
     "; handoff NOT refreshed (write-handoff exited 7 and wrote nothing)"),
    ({"STUB_WH_RC": "64"}, False, True,
     "; handoff NOT refreshed (write-handoff exited 64 and wrote nothing)"),
    ({"STUB_WH_RC": "2"}, False, True,
     "; handoff NOT refreshed (write-handoff exited 2 and wrote nothing)"),
    ({"STUB_WH_RC": "2"}, True, True,
     "; handoff written, NOT published (write-handoff exited 2)"),
    ({"STUB_WH_RC": "3"}, True, True,
     "; handoff written, its publication NOT confirmed (write-handoff exited 3)"),
    ({"STUB_WH_RC": "6"}, True, True,
     "; handoff written, NOT published (write-handoff exited 6)"),
    ({"STUB_WH_RC": "1"}, True, True,
     "; handoff written, its publication NOT confirmed (write-handoff exited 1)"),
    ({"STUB_HP_RC": "8", "STUB_HP_OUT": ""}, False, True,
     "; handoff NOT refreshed (no handoff found)"),
    # NIT 987: a 0 that names no file is "no handoff found" too, never "the read failed, exit 0".
    ({"STUB_HP_OUT": "/nowhere/at/all.md"}, False, True,
     "; handoff NOT refreshed (no handoff found)"),
    ({"STUB_HP_RC": "4", "STUB_HP_OUT": ""}, False, True,
     "; handoff NOT refreshed (the handoff read failed, exit 4)"),
    ({"STUB_HP_RC": "2", "STUB_HP_OUT": "", "STUB_HP_ERR": OLDER_HELPER}, False, True,
     "; handoff NOT refreshed (the handoff read failed, exit 2)"),
    ({}, False, False, "; handoff NOT refreshed (write-handoff was not called)"),
], ids=["pushed", "owned-by-a-restart", "block-with-no-final-newline", "refused-before-writing",
        "refused-after-writing",
        "pushed-not-confirmed", "kept-on-head", "written-then-failed", "not-found", "zero-with-no-file",
        "read-failed", "older-helper", "never-prepared"])
def test_step4_register_line_says_what_step_2_did(estate, shell, extra, written, prepare, ends):
    """rv3's SHOULD 3 on #311 at `b599ed9`: the register's PAUSED line ended
    `; handoff refreshed` whatever step 2 printed. Step 2 now carries its
    outcome to step 4 in `$hf_record`, run here in the same shell as a session
    runs them: refreshed only where the call exited 0, written but not
    confirmed published where the verb wrote the file and exited otherwise,
    and NOT refreshed, with the reason, wherever nothing was written."""
    env = dict(extra)
    if written:
        env["STUB_WH_OUT"] = f"{estate.handoff}\tdeadbeef"
    proc = estate.run(shell, estate.step2(prepare="block" if prepare else "none") + "\n"
                      + estate.step4(), **env)
    assert proc.returncode == 0, proc.stderr
    line = _register_line(estate)
    assert line.endswith(ends), line
    assert line.endswith(REFRESHED) == (ends == REFRESHED), line


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("strict", [False, True], ids=["plain", "set-u"])
def test_a_step_4_that_step_2_never_reached_never_claims_a_refresh(estate, shell, strict):
    """A step 4 run where step 2's outcome is not bound (another shell, or
    step 2 stopped before its call) says the handoff was NOT refreshed rather
    than claiming it, and an unset `$hf_record` passes `set -u`."""
    proc = estate.run(shell, ("set -u\n" if strict else "") + estate.step4())
    assert proc.returncode == 0, proc.stderr
    line = _register_line(estate)
    assert line.endswith("; handoff NOT refreshed (step 2 left no outcome)"), line


#: The names block 1 prints for a session to carry to block 2, and block 2 to step 4.
CARRIED = ("handoff_file", "block_file", "hf_record")


def _printed(proc: subprocess.CompletedProcess) -> dict:
    """Every `name=value` line a block printed, of the names that cross from
    one Bash call to the next; the last of each name wins."""
    return {m.group(1): m.group(2) for m in
            re.finditer(r"(?m)^(" + "|".join(CARRIED) + r")=(.*)$", proc.stdout)}


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("extra, written, ends", [
    ({}, True, "handoff refreshed"),
    ({"STUB_WH_RC": "7"}, False, "handoff NOT refreshed (write-handoff exited 7 and wrote nothing)"),
    ({"STUB_WH_RC": "3"}, True, "handoff written, its publication NOT confirmed (write-handoff exited 3)"),
    ({"STUB_HP_RC": "8", "STUB_HP_OUT": ""}, False, "handoff NOT refreshed (no handoff found)"),
    ({"STUB_HP_RC": "4", "STUB_HP_OUT": ""}, False,
     "handoff NOT refreshed (the handoff read failed, exit 4)"),
], ids=["pushed", "owned-by-a-restart", "pushed-not-confirmed", "not-found", "read-failed"])
def test_block_1_block_2_and_step_4_each_in_its_own_shell_carry_what_step_2_did(
        estate, shell, extra, written, ends):
    """984 of lane openRepoTools-3's review of #311: every Bash call is a new
    shell, so step 4 learnt step 2's outcome only from `$hf_record` in the
    same shell, and a step 4 in its own call wrote "; handoff NOT refreshed
    (step 2 left no outcome)" after a 0, a false line in append-only
    LANES.md; block 2 in a new shell said "there is no handoff located".
    Here each runs in its own shell as a session runs them: block 1, the
    session's write of its block, block 2 with step 1's values and every
    `name=value` line block 1 printed set, and step 4 with the `hf_record=`
    line block 2 ends by printing."""
    env = dict(extra)
    if written:
        env["STUB_WH_OUT"] = f"{estate.handoff}\tdeadbeef"
    step1 = [f"L={shlex.quote(str(estate.helper))}", f"lane={LANE}", "ws=Eagle", "why='a usage reset'"]
    first = estate.run(shell, "\n".join(step1[:2] + [_block(B1)]), **env)
    assert first.returncode == 0, first.stderr
    carried = _printed(first)
    block_file = carried.get("block_file", "")
    assert block_file, first.stdout
    assert block_file != "<none>", first.stdout
    Path(block_file).write_text(TOP, encoding="utf-8")
    second = estate.run(shell, "\n".join(step1 + [f"{k}={shlex.quote(v)}" for k, v in carried.items()]
                                         + [_block(B2)]), **env)
    assert second.returncode == 0, second.stderr
    if "handoff_file" in carried:
        assert "there is no handoff located" not in second.stdout, second.stdout
    last = second.stdout.splitlines()[-1]
    assert last == f"hf_record={ends}", second.stdout
    third = estate.run(shell, estate.step4(hf_record=_printed(second)["hf_record"]))
    assert third.returncode == 0, third.stderr
    line = _register_line(estate)
    assert line.endswith(f"; {ends}"), line
    assert "step 2 left no outcome" not in line, line


def test_the_record_phrases_are_lane_3s_refined_set():
    """Lane openRepoTools-3's answer 6 on #311: the skill and 2b's
    `lane-handoff` record one act's outcome in one set of phrases, "refined on
    both sides": "written, NOT published (exited n)" for a 2 or a 6 that wrote
    the file, and "publication NOT confirmed" for a 3, and for any other exit
    that wrote the file, where the verb said nothing of what it published."""
    held = [p for p in _prose("## 2. Refresh the handoff")
            if p.startswith("**WHAT THIS STEP DID IS CARRIED TO STEP 4")]
    assert len(held) == 1, held
    for words in ("`handoff refreshed` only where the call exited 0",
                  "`handoff written, NOT published (write-handoff exited <n>)` where the verb wrote the file "
                  "and exited 2 or 6",
                  "`handoff written, its publication NOT confirmed (write-handoff exited <n>)` where it wrote "
                  "the file and exited 3, or otherwise"):
        assert words in held[0], f"the paragraph no longer says {words!r}:\n{held[0]}"


def test_the_prose_says_what_to_set_before_block_2_and_before_step_4():
    """984: the paragraph that carries step 2's outcome to step 4 says every
    Bash call is a new shell, what to set before block 2 (step 1's values
    and block 1's printed lines) and that `hf_record` from block 2's last line
    is set before step 4."""
    held = [p for p in _prose("## 2. Refresh the handoff")
            if p.startswith("**WHAT THIS STEP DID IS CARRIED TO STEP 4")]
    assert len(held) == 1, held
    paragraph = held[0]
    for words in ("EVERY BASH CALL IS A NEW SHELL", "Before block 2", "`L`, `lane`, `ws` and `why`",
                  "`handoff_file`, `block_file` and `hf_record`", "Before step 4",
                  "block 2's last line, `hf_record=", "quoted"):
        assert words in paragraph, f"the paragraph no longer says {words!r}:\n{paragraph}"


@pytest.mark.parametrize("shell", SHELLS)
def test_a_step_4_after_block_1_alone_never_claims_a_refresh(estate, shell):
    """NIT 987: block 1 found the handoff and set `hf_record` empty, and block
    2 never ran. Step 4 in the same shell says the handoff was NOT refreshed:
    an empty `$hf_record` is no outcome, as an unset one is."""
    script = "\n".join([f"L={shlex.quote(str(estate.helper))}", f"lane={LANE}", _block(B1),
                        estate.step4()])
    proc = estate.run(shell, script)
    assert proc.returncode == 0, proc.stderr
    assert "write-handoff" not in estate.verbs(), estate.calls()
    line = _register_line(estate)
    assert line.endswith("; handoff NOT refreshed (step 2 left no outcome)"), line


# --- the real helper: the handoff is pushed from C, and W is untouched --------

REAL_NEW = prepended(HANDOFF, BLOCK)
REAL_LANE = "repoS4-1"
REAL_WHY = "a usage reset"


def _real_script(shell_between: str = "", *, lane: str = REAL_LANE, block: str = BLOCK,
                 after: str = "") -> str:
    """Step 2 whole: the session writes its new top block alone, and the verb
    puts it in front of the old file under its lock (`REAL_NEW`). `after` is
    shell run once block 2 is done, in the same shell."""
    return "\n".join([
        f"L={shlex.quote(str(HELPER))}", f"lane={lane}", "ws=Eagle", f"why={shlex.quote(REAL_WHY)}",
        _block(B1), shell_between,
        f'[ -z "$block_file" ] || printf %s {shlex.quote(block)} > "$block_file"',
        _block(B2), after])


def _real_run(box: RealBox, shell: str, script: str) -> subprocess.CompletedProcess:
    argv = ["bash", "-c", script] if shell == "bash" else \
        [shutil.which("zsh") or "zsh", "-f", "-c", script]
    return subprocess.run(argv, env=dict(box.env), cwd=str(box.root), capture_output=True,
                          text=True, check=False, timeout=240)


def _said(proc: subprocess.CompletedProcess) -> str:
    return f"--- stdout\n{proc.stdout}--- stderr\n{proc.stderr}"


def _tree(box: RealBox) -> list[str]:
    return box.git("--git-dir", str(box.origin), "ls-tree", "-r", "--name-only", "main").split()


@pytest.fixture
def real(tmp_path: Path) -> RealBox:
    return RealBox(tmp_path)


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("how", ["routed", "seam"])
def test_the_handoff_is_pushed_from_the_lane_checkout_and_W_is_untouched(real, shell, how):
    """Step 2, whole, against the real helper. The lane's checkout is made by
    the first block where it is not there yet, the handoff is written, committed
    by its own pathspec with the `Lane:` trailer and pushed from it, and W, the
    readers' copy, does not move: not its HEAD, its working tree, its reflog, and
    not the entry another lane left STAGED there, which the old block committed
    and published. The session wrote its new top block alone, as rv3's probe of
    SHOULD 1 did, and origin's handoff is that block over the old file whole:
    the history survives, because the verb makes the file (`--prepend`)."""
    if how == "seam":
        c = real.seam()
    else:
        c = real.checkout(REAL_LANE)
        assert not c.exists(), "the precondition: the lane has no checkout yet"
    real.write(real.w, "handoffs/staged-in-w.md", "another lane's entry, staged in W\n")
    real.git("-C", str(real.w), "add", "--", "handoffs/staged-in-w.md")
    w_before, reflog, tip = real.w_state(), real.w_reflog(), real.origin_head()

    proc = _real_run(real, shell, _real_script())

    assert proc.returncode == 0, _said(proc)
    assert f"handoff written: {c / HANDOFF_REL}" in proc.stdout, _said(proc)
    assert real.origin_file(HANDOFF_REL) == REAL_NEW, _said(proc)
    assert real.origin_head() != tip
    assert real.subjects()[0] == f"handoff({REAL_LANE}@Eagle): PAUSED, {REAL_WHY}"
    assert real.git("--git-dir", str(real.origin), "log", "-1", "--format=%B",
                    "main").strip().splitlines()[-1] == f"Lane: {REAL_LANE}"
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == REAL_NEW
    assert real.head(c) == real.origin_head()
    assert real.unpublished(c) == []
    assert real.git("-C", str(c), "status", "--porcelain") == ""
    assert real.w_state() == w_before, "W moved"
    assert real.w_reflog() == reflog, "W's reflog moved: something committed or fast-forwarded it"
    assert (real.w / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    assert "handoffs/staged-in-w.md" not in _tree(real), "a staged entry of W's reached origin"
    assert real.git("-C", str(real.w), "diff", "--cached", "--name-only").split() == [
        "handoffs/staged-in-w.md"]
    assert not real.lock_of(c).exists(), "the checkout's lock is released"


def _peer_edit(box: RealBox) -> str:
    """Shell that a peer runs between the blocks: it appends a line to the
    lane's handoff in another clone and pushes it."""
    peer = shlex.quote(str(box.seed))
    rel = shlex.quote(HANDOFF_REL)
    return (f"git -C {peer} pull -q --ff-only origin main && "
            f"printf '%s\\n' 'a peer line' >> {peer}/{rel} && "
            f"git -C {peer} add -- {rel} && "
            f"git -C {peer} commit -q -m 'a peer edits the handoff' && "
            f"git -C {peer} push -q origin main")


@pytest.mark.parametrize("shell", SHELLS)
def test_a_peers_edit_pushed_between_the_blocks_is_kept_under_the_new_block(real, shell):
    """981, option (a), as lane openRepoTools-3 answered question 1: with
    `--whole` and a digest, a peer's edit that landed between the read and
    the call was 7 and nothing was published. With `--prepend` the verb
    reads the handoff under its lock, from what S3 has just brought from
    origin, so the new block goes on top of the peer's file and both are
    kept, newest on top: the handoff's normal shape, at the first call."""
    proc = _real_run(real, shell, _real_script(_peer_edit(real)))
    assert proc.returncode == 0, _said(proc)
    assert "handoff written:" in proc.stdout, _said(proc)
    assert real.subjects()[:2] == [f"handoff({REAL_LANE}@Eagle): PAUSED, {REAL_WHY}",
                                   "a peer edits the handoff"]
    assert real.origin_file(HANDOFF_REL) == prepended(HANDOFF + "a peer line\n", BLOCK), _said(proc)


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("how", ["routed", "seam"])
def test_a_lane_checkout_behind_origin_is_written_on_the_first_call(real, shell, how):
    """rv3's SHOULD 2 (question 3 of the body), ported from its probe, and
    lane openRepoTools-3's answer to question 4: a lane checkout behind origin
    on its handoff was 7 once with `--whole`, because the digest was of its
    stale copy. With `--prepend` the case goes away: the verb fast-forwards
    the checkout and reads the file there, so the first call writes the new
    block over the peer's file, which survives under it."""
    if how == "seam":
        real.seam()
    else:
        made = real.helper("handoff-path", REAL_LANE, "--create")
        assert made.returncode == 0, made.stderr
    peer_text = HANDOFF + "a peer line, pushed from elsewhere\n"
    real.peer_pushes(HANDOFF_REL, peer_text)
    proc = _real_run(real, shell, _real_script())
    assert proc.returncode == 0, _said(proc)
    assert "handoff written:" in proc.stdout, _said(proc)
    assert real.origin_file(HANDOFF_REL) == prepended(peer_text, BLOCK), _said(proc)


@pytest.mark.parametrize("shell", SHELLS)
def test_a_block_with_no_final_newline_is_refused_and_written_once_it_has_one(real, shell):
    """981 (MUST) of lane openRepoTools-3's review of #311 at `1913db9`: a
    top block with no final newline (a Write-tool body, a `printf %s`) was
    glued to the `---` under it, so origin's handoff read `…the newer
    block---`, and `lane-start`'s `handoff_top_block`, which stops at the
    first line opening with `---`, gave the next session the new block and the
    old one as one prompt. The verb refuses that block (64) and writes nothing;
    the block says so, and what its 64 arm says to do, an `echo` onto the
    block file and block 2 once more, writes the handoff whole."""
    c = real.seam()
    tip = real.origin_head()
    unterminated = BLOCK.rstrip("\n")
    assert not unterminated.endswith("\n")
    first = _real_run(real, shell, _real_script(
        block=unterminated, after='printf "FIRST_RECORD=%s\\n" "$hf_record"'))
    assert first.returncode == 0, _said(first)
    assert "(exit 64;" in first.stdout, _said(first)
    assert "does not end with a newline" in first.stderr, _said(first)
    assert "HANDOFF NOT WRITTEN" in first.stdout, _said(first)
    assert real.origin_head() == tip, "nothing is published on a 64"
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF, "nothing is written on a 64"
    assert ("FIRST_RECORD=handoff NOT refreshed (write-handoff exited 64 and wrote nothing)"
            in first.stdout), _said(first)
    fixed = _real_run(real, shell, _real_script(
        block=unterminated, after='echo >> "$block_file"\n' + _block(B2)))
    assert fixed.returncode == 0, _said(fixed)
    assert "handoff written:" in fixed.stdout, _said(fixed)
    assert real.origin_file(HANDOFF_REL) == prepended(HANDOFF, unterminated + "\n"), _said(fixed)
    top = real.origin_file(HANDOFF_REL).split("\n---\n")[0]
    assert top == unterminated, "the rule is a line of its own: no line of the block runs into it"


@pytest.mark.parametrize("shell", SHELLS)
def test_an_active_restart_is_a_7_and_the_block_says_not_to_retry(real, shell):
    """981, option (a): with `--prepend` a 7 is a restart's (`an active
    restart owns this handoff`), never "moved since it was read", so the arm
    says that restart writes the handoff and does not send the session back
    for a new digest. Nothing is written or published."""
    c = real.seam()
    real.restart(c / HANDOFF_REL)
    tip = real.origin_head()
    proc = _real_run(real, shell, _real_script())
    assert proc.returncode == 0, _said(proc)
    assert "an active restart owns this handoff" in proc.stderr, _said(proc)
    assert "(exit 7;" in proc.stdout, _said(proc)
    assert "Do not retry: that restart writes this handoff" in proc.stdout, _said(proc)
    assert "WHERE THE HANDOFF IS" not in proc.stdout, _said(proc)
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == HANDOFF
    assert real.origin_head() == tip


@pytest.mark.parametrize("shell", SHELLS)
def test_a_staged_entry_in_the_lane_checkout_leaves_the_handoff_written_and_uncommitted(
        real, shell):
    """S3's refusal (2) with `--prepend`: the file is written (`R-A11-11`), nothing
    is committed or pushed, the entry that is not the handoff's stays staged and
    unpublished, and the block says exactly that, and not to call it again."""
    c = real.seam()
    real.write(c, "handoffs/foreign.md", "someone else's entry\n")
    real.git("-C", str(c), "add", "--", "handoffs/foreign.md")
    tip, head = real.origin_head(), real.head(c)

    proc = _real_run(real, shell, _real_script())

    assert proc.returncode == 0, _said(proc)
    assert "HANDOFF NOT COMMITTED" in proc.stdout, _said(proc)
    assert f"written at {c / HANDOFF_REL}, uncommitted" in proc.stdout, _said(proc)
    assert "Do not call it again" in proc.stdout, _said(proc)
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == REAL_NEW
    assert real.origin_head() == tip
    assert real.head(c) == head
    assert real.git("-C", str(c), "diff", "--cached", "--name-only").split() == [
        "handoffs/foreign.md"]
    assert "handoffs/foreign.md" not in _tree(real)


@pytest.mark.parametrize("shell", SHELLS)
def test_an_8d_handoff_whose_push_fails_there_is_6_and_its_commit_is_said_to_be_there(real, shell):
    """982 of lane openRepoTools-3's review of #311: since 604 (2a's A57), a 6
    is also an Amendment 8(d) handoff, written, whose commit or push in its
    own repository failed. Here that repository has no origin: the handoff is
    written and committed there, the push cannot be made (6), the lane
    checkout's HEAD and the register's origin do not move, and the block's 6
    arm says where the commit is kept, or that there is none, from the verb's
    note, never that it is on HEAD of the lane checkout."""
    other = _other_repository(real, origin=False)
    real.cell_is(str(other / "handoff.md"))
    c = real.seam()
    before = real.git("-C", str(other), "rev-parse", "HEAD").strip()
    head, tip = real.head(c), real.origin_head()
    proc = _real_run(real, shell, _real_script())
    assert proc.returncode == 0, _said(proc)
    assert "HANDOFF NOT PUSHED" in proc.stdout, _said(proc)
    assert "write-handoff exited 6" in proc.stdout, _said(proc)
    assert "for an Amendment 8(d) handoff, in its own repository" in proc.stdout, _said(proc)
    assert "and committed there, on main" in proc.stderr, _said(proc)
    assert (other / "handoff.md").read_text(encoding="utf-8") == REAL_NEW
    assert real.git("-C", str(other), "rev-parse", "HEAD~1").strip() == before
    assert real.git("-C", str(other), "log", "-1", "--format=%B").strip().splitlines() == [
        f"handoff({REAL_LANE}@Eagle): PAUSED, {REAL_WHY}", "", f"Lane: {REAL_LANE}"]
    assert real.head(c) == head, "the lane checkout's HEAD did not move"
    assert real.origin_head() == tip, "the register's origin did not move"


@pytest.mark.parametrize("shell", SHELLS)
def test_a_lane_with_no_row_has_nothing_to_write_and_nothing_is_cloned(real, shell):
    tip = real.origin_head()
    proc = _real_run(real, shell, _real_script(lane="repoS4-9"))
    assert proc.returncode == 0, _said(proc)
    assert "HANDOFF NOT FOUND" in proc.stdout, _said(proc)
    assert "was NOT called" in proc.stdout, _said(proc)
    assert not real.checkout("repoS4-9").exists()
    assert real.origin_head() == tip
