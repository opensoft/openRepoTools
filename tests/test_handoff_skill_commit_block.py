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
    write-handoff <lane> --whole <prepared> --expect-digest <sha> --subject <s>

which takes the lane checkout's lock, brings the checkout to origin, checks the
digest, replaces the file atomically, commits it by its own pathspec with the
`Lane:` trailer, pushes, reads origin back and replays a refused push. So this
file holds the skill's two blocks to what is left of them: derive the path and
the digest, send the call with exactly those arguments, say what each exit
means and never stop the swap (`R-A11-11`), and spell no checkout of its own.

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

import hashlib
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
from test_a23_write_handoff import BLOCK, HANDOFF, HANDOFF_REL, Box as RealBox, prepended

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the skill's blocks are shell, and the sandbox runs git")]

SKILL = REPO / "skills/handoff/SKILL.md"
HELPER = REPO / "lanes-edit.sh"

#: Each carried by exactly one shell block of the skill: how the blocks are found.
B1 = 'handoff_file="$("$L" handoff-path "$lane" --create)"'
B2 = '--whole "$prepared_file"'
STEP4 = "# (c) the row: ONE WRITE"

LANE = "repoHS-1"
UUID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
OLD = ("Lane: repoHS-1 (p, session s) — single-use resume prompt\n\n"
       "## RESUME PROMPT — PAUSED, the old block\n\nthe old state\n")
#: The session's new top block, which it writes to `$block_file`, and the
#: complete new file the skill builds from it: `write-handoff --prepend`'s layout.
TOP = ("Lane: repoHS-1 (p, session s) — single-use resume prompt\n\n"
       "## RESUME PROMPT — PAUSED, the new block\n\n")
NEW = TOP + "---\n\n" + OLD
OLD_DIGEST = hashlib.sha256(OLD.encode("utf-8")).hexdigest()

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
STUB = f"""#!{sys.executable}
import json, os, sys
argv = sys.argv[1:]
rec = {{"argv": argv, "lane": os.environ.get("LANES_LANE"),
       "no_fetch": os.environ.get("LANES_NO_FETCH")}}
if argv[:1] == ["write-handoff"] and "--whole" in argv:
    try:
        with open(argv[argv.index("--whole") + 1], "rb") as f:
            rec["prepared"] = f.read().decode("utf-8")
    except (OSError, IndexError):
        rec["prepared"] = None
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
if verb in ("log", "append-line", "set-row-state"):
    sys.exit(0)
sys.exit(8 if verb == "lane-dir" else 2)
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
        # A `tmux` that answers nothing, so the host's own server is never read.
        (self.bin / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        for tool in (self.helper, self.bin / "tmux"):
            tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
        self.handoff = root / "checkout" / "handoffs" / "estate" / f"{LANE}.md"
        self.handoff.parent.mkdir(parents=True)
        self.handoff.write_text(OLD, encoding="utf-8")

    def run(self, shell: str, script: str, **extra: str) -> subprocess.CompletedProcess:
        env = {"HOME": str(self.home), "TMPDIR": str(self.tmp), "STUB_LOG": str(self.log),
               "PATH": os.pathsep.join([str(self.bin), "/usr/bin", "/bin"]),
               "STUB_HP_OUT": str(self.handoff), **extra}
        argv = ["bash", "-c", script] if shell == "bash" else \
            [shutil.which("zsh") or "zsh", "-f", "-c", script]
        return subprocess.run(argv, env=env, cwd=str(self.home), capture_output=True,
                              text=True, check=False, timeout=120)

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in
                self.log.read_text(encoding="utf-8").splitlines()]

    def verbs(self) -> list[str]:
        return [c["argv"][0] for c in self.calls()]

    def step2(self, *, ws: str = "Eagle", why: str = "'a usage reset'",
              prepare: str = "block") -> str:
        """Step 2 as a session runs it: the first block, the session's own act
        of writing its new top block, and only it, to `$block_file`, then the
        block that builds the complete new file and makes the one call. `ws` and
        `why` are shell words, so a case can hand the block an ANSI-C string.
        `prepare` is "block" (as the skill says), "none" (nothing written), or
        "by-hand" (the old habit: the whole new file written into
        `$prepared_file`, and `$block_file` left empty)."""
        write = {
            "block": f'[ -z "$block_file" ] || printf %s {shlex.quote(TOP)} > "$block_file"',
            "none": ":",
            "by-hand": f'[ -z "$prepared_file" ] || printf %s {shlex.quote(NEW)} > "$prepared_file"',
        }[prepare]
        return "\n".join([f"L={shlex.quote(str(self.helper))}", f"lane={LANE}", f"ws={ws}",
                          f"why={why}", _block(B1), write, _block(B2),
                          'printf "AFTER\\n"'])

    def step4(self, *, ws_missing: str = "", uuid_missing: str = "") -> str:
        return "\n".join([f"L={shlex.quote(str(self.helper))}", f"lane={LANE}", "ws=Eagle",
                          'why="a usage reset"', f'uuid="{UUID}"', f'ws_missing="{ws_missing}"',
                          f'uuid_missing="{uuid_missing}"', _block(STEP4),
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
def test_block_calls_write_handoff_with_whole_and_expect_digest(estate, shell):
    """The handoff's place is asked of `handoff-path --create`, its digest is
    read from the bytes there, and `write-handoff` is called ONCE with the
    prepared file the session wrote, that digest, and the subject: the lane, the
    workstation and the why. `LANES_LANE` is the lane."""
    proc = estate.run(shell, estate.step2(), STUB_WH_OUT=f"{estate.handoff}\tdeadbeef")
    assert proc.returncode == 0, proc.stderr
    assert estate.verbs() == ["handoff-path", "write-handoff"], estate.calls()
    assert estate.calls()[0]["argv"] == ["handoff-path", LANE, "--create"]
    call = _write_call(estate)
    argv = call["argv"]
    assert argv[:3] == ["write-handoff", LANE, "--whole"], argv
    assert argv[4:] == ["--expect-digest", OLD_DIGEST, "--subject",
                        f"handoff({LANE}@Eagle): PAUSED, a usage reset"], argv
    assert call["prepared"] == NEW, (
        "the file sent is the session's top block, `---` and a blank line, then the old file whole")
    assert Path(argv[3]).parent == estate.tmp, "the prepared file is a temporary one"
    assert call["lane"] == LANE
    assert f"handoff written: {estate.handoff}" in proc.stdout, proc.stdout
    assert proc.stdout.endswith("AFTER\n")
    assert estate.handoff.read_text(encoding="utf-8") == OLD, (
        "the skill never writes the handoff itself: the verb does")


@pytest.mark.parametrize("shell", SHELLS)
def test_the_digest_is_of_the_bytes_that_are_there(estate, shell):
    """Not of a copy and not of the row's spelling: the file `handoff-path`
    named, read as it stands."""
    other = "a different handoff\nwith other bytes\n"
    estate.handoff.write_text(other, encoding="utf-8")
    estate.run(shell, estate.step2())
    argv = _write_call(estate)["argv"]
    assert argv[argv.index("--expect-digest") + 1] == hashlib.sha256(other.encode()).hexdigest()


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
                argv[3] = "<prepared>"
            out.append(dict(call, argv=argv))
        return out

    estate.run(shell, estate.step2(), STUB_WH_OUT=f"{estate.handoff}\tx")
    plain = shape()
    estate.log.write_text("", encoding="utf-8")
    estate.run(shell, estate.step2(), STUB_WH_OUT=f"{estate.handoff}\tx",
               LANES_REPO=str(estate.root / "elsewhere"), LANES_BRANCH="not-main")
    assert "workspace-root" not in estate.verbs(), estate.calls()
    assert shape() == plain, "an ambient LANES_REPO changed the call"


def test_the_three_variables_the_old_call_named_are_defined_in_a_block():
    """`publish-handoff "$lane" "$handoff_file" "$prepared_file" --expect-digest
    "$prior_sha256"` used its three variables without defining any of them."""
    code = "\n".join(_code_lines([_block(B1)]))
    for name in ("handoff_file", "prior_sha256", "prepared_file"):
        assert re.search(rf"(?m)^\s*{name}=", code), f"no block defines ${name}"
    assert "publish-handoff" not in "\n".join(_blocks(_text())), (
        "the old call is gone: write-handoff is the one act")


def test_the_skill_never_pulls_with_rebase_outside_a_comment():
    """Amendment 23 S3-S4 (`tests/test_repo_hygiene.py`'s no-pull rule, whose
    file list takes this file at the merge): no line of the skill that is not a
    comment runs, or tells a person to run, a rebasing pull."""
    pull = re.compile(r"\bpull\b[^\n]*?(?:--rebase\b|\s-r\b)")
    found = [n for n, line in enumerate(_text().splitlines(), 1)
             if not line.lstrip().startswith("#") and pull.search(line)]
    assert not found, f"{SKILL.name} line(s) {found} run or print a rebasing pull"


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


# --- the words: what each exit says, and that the swap goes on ---------------

def _says(estate: Estate) -> dict:
    path = str(estate.handoff)
    return {
        # rv3's NIT 2: the 0 arm claims no push of its own; the verb's note says what it
        # committed and where (an Amendment 8(d) handoff in its own top level, S2).
        "pushed": (0, True, [f"handoff written: {path} (", "says what was committed and where it was pushed"],
                   ["HANDOFF NOT", "pushed from the lane checkout", "never committed"]),
        "refused-after-writing": (2, True, [
            "HANDOFF NOT COMMITTED", f"written at {path}, uncommitted", "Nothing was pushed",
            "Do not call it again", "refused (7)"], ["HANDOFF NOT WRITTEN"]),
        "refused-before-writing": (2, False, [
            "HANDOFF NOT WRITTEN", "wrote nothing"], ["HANDOFF NOT COMMITTED"]),
        "pushed-not-confirmed": (3, True, [
            "HANDOFF PUSHED, NOT CONFIRMED", "(exit 3",
            "Do not call it published until it is read back"], []),
        "kept-on-head": (6, True, ["HANDOFF NOT PUSHED", "kept on HEAD", "(exit 6)",
                                   "Never force"], []),
        "moved-or-owned": (7, False, [
            "HANDOFF NOT WRITTEN", f"digest {OLD_DIGEST}", "(exit 7;",
            "run the block under WHERE THE HANDOFF IS again", "reads a new digest",
            "makes a new prepared file", "run this block once more",
            "a restart owns it, do not retry"], []),
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
         "kept-on-head", "moved-or-owned", "no-handoff", "environment", "lock",
         "written-then-failed"]


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
def test_the_new_file_is_kept_and_named_wherever_nothing_was_written(estate, shell, case):
    """rv3's MUST 1, for the call's own outcomes: where the verb wrote nothing
    (no stdout), the session's new file is not lost with the swap. The block
    names the temporary file that holds it, for the report; where the verb
    wrote the handoff, there is nothing to keep and nothing is said of it."""
    rc, written, _, _ = _says(estate)[case]
    out = f"{estate.handoff}\tdeadbeef" if written else ""
    proc = estate.run(shell, estate.step2(), STUB_WH_RC=str(rc), STUB_WH_OUT=out)
    sent = _write_call(estate)["argv"][3]
    kept = f"kept at {sent}"
    top = f"its new top block alone at {_block_file(proc)}"
    if written:
        assert kept not in proc.stdout, proc.stdout
        assert top not in proc.stdout, proc.stdout
    else:
        assert kept in proc.stdout, f"{case}: the new file is not named\n{proc.stdout}"
        assert top in proc.stdout, f"{case}: the top block's file is not named\n{proc.stdout}"
        assert "name both paths in the report" in proc.stdout, proc.stdout


def _block_file(proc: subprocess.CompletedProcess) -> str:
    """The `$block_file` block 1 printed for the session to write its top block in."""
    found = re.findall(r"(?m)^block_file=(.+)$", proc.stdout)
    assert len(found) == 1, proc.stdout
    return found[0]


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
    assert estate.verbs() == ["handoff-path"], estate.calls()
    assert proc.stdout.endswith("AFTER\n")


#: `lanes-edit.sh`'s unknown-subcommand refusal, as a helper predating
#: `handoff-path` (main at `33ce26d`) prints it on stderr, with exit 2.
OLDER_HELPER = ("lanes-edit.sh: unknown subcommand 'handoff-path' "
                "(verify-row|set-row-state|append-line|commit|publish-handoff)")

#: 601's refusal, as slice 2a's `handoff-path` says it from A54 (`6d861d4`) on:
#: the row names a handoff in another checkout of the register beside W, so the
#: path is not printed, with exit 2 (lane openRepoTools-3's correction 6368669583).
ANOTHER_REPOSITORY = (
    "lanes-edit.sh: lane repoHS-1's handoff handoffs/estate/repoHS-1.md is "
    "/w-lanes/repoHS-2/handoffs/estate/repoHS-1.md, in another checkout of the register "
    "beside W (/w), not in the checkout /w-lanes/repoHS-1 this lane's writes go through: "
    "a lane's handoff is written in its own checkout only (Amendment 23 S1, S2): "
    "`write-handoff` refuses it, so no path is printed for a restart to bind or a launch "
    "to read (601). Nothing was written.")


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("rc, err, must, never", [
    ("1", "the register could not be read (R22: never 8)",
     ["exited 1 (its words are above)"], ["Update lanes-edit.sh", "step 2 again"]),
    ("2", "the clone of the lane checkout failed",
     ["exited 2 (its words are above)"], ["Update lanes-edit.sh", "step 2 again"]),
    ("2", OLDER_HELPER,
     ["exited 2", "unknown subcommand", "predates handoff-path", "Update lanes-edit.sh",
      "step 2 again"], ["belongs to another repository"]),
    ("2", ANOTHER_REPOSITORY,
     ["exited 2 (its words are above)",
      "the handoff it names belongs to another repository and not to this lane: "
      "nothing is to be written there, by this skill or by hand"],
     ["Update lanes-edit.sh", "step 2 again"]),
    ("4", "the lock that makes the lane checkout is held",
     ["exited 4", "Run step 2 again"], ["Update lanes-edit.sh"]),
    ("64", "usage: handoff-path <lane> [--create]",
     ["exited 64 (its words are above)"], ["Update lanes-edit.sh", "step 2 again"]),
    ("127", "lanes-edit.sh: not found",
     ["exited 127 (its words are above)"], ["Update lanes-edit.sh", "step 2 again"]),
], ids=["unreadable", "clone-failed", "older-helper", "another-repository", "lock", "usage",
        "no-helper"])
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
    assert "write-handoff" not in estate.verbs(), estate.calls()


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
@pytest.mark.parametrize("prepare", ["none", "by-hand"])
def test_a_top_block_the_session_never_wrote_is_never_sent(estate, shell, prepare):
    """`mktemp` makes an empty file, and an empty `$block_file` is no new top
    block: the block does not build a file or ask. A whole file written by hand
    into `$prepared_file` (the old habit, where a session that forgot the
    history sent only its block, rv3's SHOULD 1) is not what is sent either."""
    proc = estate.run(shell, estate.step2(prepare=prepare))
    assert proc.returncode == 0
    assert "HANDOFF NOT WRITTEN" in proc.stdout, proc.stdout
    assert "was NOT called" in proc.stdout, proc.stdout
    assert estate.verbs() == ["handoff-path"], estate.calls()


#: The register line's last phrase where the new file did not keep the old one.
LOST = "; handoff NOT refreshed (the new file did not keep the old handoff whole)"


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("how", ["short", "failed"])
def test_a_new_file_that_lost_the_old_one_is_never_sent(estate, shell, how):
    """rv3's SHOULD 1 on #311, option (b): the block builds the complete new
    file itself, the top block from `$block_file`, `---` and a blank line, then
    `cat -- "$handoff_file"`, and proves the old file survives at its end, byte
    for byte (`tail -c <old size> | cmp`), before the call. A build that lost the
    old file's bytes, here a `cat` that wrote only the first ten of them or
    failed, is never sent: the call is not made, the block says why and names
    the top block's file for the report, and step 4's line says the handoff was
    NOT refreshed."""
    cut = 'head -c 10 -- "$last"; exit 0' if how == "short" else "exit 1"
    shim = estate.bin / "cat"
    shim.write_text(f'#!/bin/sh\nfor last in "$@"; do :; done\n'
                    f'[ "$last" = "$STUB_CAT_CUT" ] || exec {shutil.which("cat")} "$@"\n{cut}\n',
                    encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    proc = estate.run(shell, estate.step2() + "\n" + estate.step4(),
                      STUB_CAT_CUT=str(estate.handoff))
    assert proc.returncode == 0, proc.stderr
    assert "write-handoff" not in estate.verbs(), estate.calls()
    assert "HANDOFF NOT WRITTEN" in proc.stdout, proc.stdout
    assert "does not end with the old handoff whole" in proc.stdout, proc.stdout
    assert "write-handoff was NOT called" in proc.stdout, proc.stdout
    assert f"kept at {_block_file(proc)}" in proc.stdout, proc.stdout
    assert _register_line(estate).endswith(LOST), _register_line(estate)


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
    ({"STUB_WH_RC": "2"}, False, True,
     "; handoff NOT refreshed (write-handoff exited 2 and wrote nothing)"),
    ({"STUB_WH_RC": "2"}, True, True,
     "; handoff written, its publication NOT confirmed (write-handoff exited 2)"),
    ({"STUB_WH_RC": "3"}, True, True,
     "; handoff written, its publication NOT confirmed (write-handoff exited 3)"),
    ({"STUB_WH_RC": "6"}, True, True,
     "; handoff written, its publication NOT confirmed (write-handoff exited 6)"),
    ({"STUB_WH_RC": "1"}, True, True,
     "; handoff written, its publication NOT confirmed (write-handoff exited 1)"),
    ({"STUB_HP_RC": "8", "STUB_HP_OUT": ""}, False, True,
     "; handoff NOT refreshed (no handoff found)"),
    ({"STUB_HP_RC": "4", "STUB_HP_OUT": ""}, False, True,
     "; handoff NOT refreshed (the handoff read failed, exit 4)"),
    ({"STUB_HP_RC": "2", "STUB_HP_OUT": "", "STUB_HP_ERR": OLDER_HELPER}, False, True,
     "; handoff NOT refreshed (the handoff read failed, exit 2)"),
    ({}, False, False, "; handoff NOT refreshed (write-handoff was not called)"),
], ids=["pushed", "moved-or-owned", "refused-before-writing", "refused-after-writing",
        "pushed-not-confirmed", "kept-on-head", "written-then-failed", "not-found", "read-failed",
        "older-helper", "never-prepared"])
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


# --- the real helper: the handoff is pushed from C, and W is untouched --------

REAL_NEW = prepended(HANDOFF, BLOCK)
REAL_LANE = "repoS4-1"
REAL_WHY = "a usage reset"


def _real_script(shell_between: str = "", *, lane: str = REAL_LANE, block: str = BLOCK) -> str:
    """Step 2 whole: the session writes its new top block alone, and the skill
    builds `REAL_NEW` from it and the old file."""
    return "\n".join([
        f"L={shlex.quote(str(HELPER))}", f"lane={lane}", "ws=Eagle", f"why={shlex.quote(REAL_WHY)}",
        _block(B1), shell_between,
        f'[ -z "$block_file" ] || printf %s {shlex.quote(block)} > "$block_file"',
        _block(B2)])


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
    the history survives, because the skill builds the file."""
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


@pytest.mark.parametrize("shell", SHELLS)
def test_a_handoff_that_moved_after_its_digest_was_read_is_refused_and_nothing_is_published(
        real, shell):
    """The digest is of the bytes the new file was made from. A peer's edit that
    lands between the read and the call is exit 7: the verb fetches the lane's
    checkout, finds other bytes, and publishes nothing; the block says so and
    tells the session to read it again."""
    peer = shlex.quote(str(real.seed))
    rel = shlex.quote(HANDOFF_REL)
    between = (f"git -C {peer} pull -q --ff-only origin main && "
               f"printf '%s\\n' 'a peer line' >> {peer}/{rel} && "
               f"git -C {peer} add -- {rel} && "
               f"git -C {peer} commit -q -m 'a peer edits the handoff' && "
               f"git -C {peer} push -q origin main")
    proc = _real_run(real, shell, _real_script(between))
    assert proc.returncode == 0, _said(proc)
    assert "HANDOFF NOT WRITTEN" in proc.stdout, _said(proc)
    assert "once more" in proc.stdout, _said(proc)
    assert "nothing was published" in proc.stderr, _said(proc)
    assert real.subjects()[0] == "a peer edits the handoff"
    assert "a peer line" in real.origin_file(HANDOFF_REL)
    assert real.origin_file(HANDOFF_REL) != REAL_NEW


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("how", ["routed", "seam"])
def test_a_lane_checkout_behind_origin_is_7_once_and_written_when_step_2_is_run_again(
        real, shell, how):
    """rv3's SHOULD 2 (question 3 of the body), ported from its probe. A lane
    checkout behind origin on its handoff: `handoff-path --create` leaves it
    as it is, the digest is of its stale copy, and the verb fast-forwards it
    first, so the first call is 7 with nothing published. The 7 arm's words
    are the way out: the block under WHERE THE HANDOFF IS run again reads the
    digest the checkout has now, and the call made once more writes the new
    block over the peer's file, which survives under it."""
    if how == "seam":
        real.seam()
    else:
        made = real.helper("handoff-path", REAL_LANE, "--create")
        assert made.returncode == 0, made.stderr
    peer_text = HANDOFF + "a peer line, pushed from elsewhere\n"
    real.peer_pushes(HANDOFF_REL, peer_text)
    script = _real_script()
    first = _real_run(real, shell, script)
    assert first.returncode == 0, _said(first)
    assert "(exit 7;" in first.stdout, _said(first)
    assert "run the block under WHERE THE HANDOFF IS again" in first.stdout, _said(first)
    assert real.origin_file(HANDOFF_REL) == peer_text, "nothing is published on a 7"
    second = _real_run(real, shell, script)
    assert second.returncode == 0, _said(second)
    assert "handoff written:" in second.stdout, _said(second)
    assert real.origin_file(HANDOFF_REL) == prepended(peer_text, BLOCK), _said(second)


@pytest.mark.parametrize("shell", SHELLS)
def test_a_staged_entry_in_the_lane_checkout_leaves_the_handoff_written_and_uncommitted(
        real, shell):
    """S3's refusal (2) with `--whole`: the file is written (`R-A11-11`), nothing
    is committed or pushed, the entry that is not the handoff's stays staged and
    unpublished, and the block says exactly that."""
    c = real.seam()
    real.write(c, "handoffs/foreign.md", "someone else's entry\n")
    real.git("-C", str(c), "add", "--", "handoffs/foreign.md")
    tip, head = real.origin_head(), real.head(c)

    proc = _real_run(real, shell, _real_script())

    assert proc.returncode == 0, _said(proc)
    assert "HANDOFF NOT COMMITTED" in proc.stdout, _said(proc)
    assert f"written at {c / HANDOFF_REL}, uncommitted" in proc.stdout, _said(proc)
    assert (c / HANDOFF_REL).read_text(encoding="utf-8") == REAL_NEW
    assert real.origin_head() == tip
    assert real.head(c) == head
    assert real.git("-C", str(c), "diff", "--cached", "--name-only").split() == [
        "handoffs/foreign.md"]
    assert "handoffs/foreign.md" not in _tree(real)


@pytest.mark.parametrize("shell", SHELLS)
def test_a_lane_with_no_row_has_nothing_to_write_and_nothing_is_cloned(real, shell):
    tip = real.origin_head()
    proc = _real_run(real, shell, _real_script(lane="repoS4-9"))
    assert proc.returncode == 0, _said(proc)
    assert "HANDOFF NOT FOUND" in proc.stdout, _said(proc)
    assert "was NOT called" in proc.stdout, _said(proc)
    assert not real.checkout("repoS4-9").exists()
    assert real.origin_head() == tip
