# SPDX-License-Identifier: Apache-2.0
"""`skills/handoff/SKILL.md`'s step-1 fence and step-4 `window` ref, held to
opensoft/openRepoTools#72 item 8 and #80 item 4.

#72 ITEM 8 — AN EXIT 2 IS TWO ANSWERS, AND THE SKILL HEARD ONE. Every read in
step 1 goes through `sread`, whose `8|2) sr_out=""` arm read every exit 2 as
"no answer" and fell to the next rung. But `2` is also `canon_lane`'s refusal
of a register holding two rows that differ only by case (Amendment 15(d)),
which `register-row` and every other read that takes a lane name carry. Falling
through THAT binds the window to whatever the next rung answers, and the last
rung is the workstation's NEWEST SWAP: a different lane, which the skill then
renames the window for and writes a PAUSED record and a restart command about.
`lane-handoff`'s own `sread` tells the two apart by the helper's words (#47
round 2); the skill now does the same, and an old helper's unknown-subcommand
2 still falls through as it did. And because only rung 1 reads its name
through the resolver, the bound name is then read through `canon-lane` and
the same fence whichever rung answered, as `lane-handoff` does after its rungs
(the independent review of #260): a case twin bound by `window-lane` or by
the newest swap refuses there too.

#80 ITEM 4 — A `<session>:<index>` CHECKED BY A PREFIX GLOB. Step 4 held the
live `#S:#I` and the launcher's `WORKBENCHES_CLAUDE_WINDOW_REF` to
`case "$win" in *:[0-9]*)`, so `s:1junk` passed and went into the append-only
`window` sub-field, where `window-lane` can never resolve it. Both checks are
now the whole-string `[[ "$win" =~ ^.+:[0-9]+$ ]]` the `<@id>` beside them
already used, and because that regex's `.` matches a line break, a value
carrying a newline or a carriage return is dropped beside each check:
`log PAUSED` would refuse the whole record over it.

THE BLOCKS ARE RUN, NOT READ. They are found the way
`tests/test_skill_shell_blocks.py` finds them (its own fence reader, imported
rather than copied), cut by the same two ranges the shell suite's
`sfence_probe` and `skill_win_of` cut, and run under `bash` and under `zsh -f`
where one is installed, because a session's Bash tool runs a skill's block
under the user's own shell. Every RED case below fails against the block as it
stood at 08e7550 and passes with the fix, and the review round's cases (the
lower rungs, `canon-lane`'s answers and a line break before the index) fail
against c9d681f as well; the rest pin what did not change.

NOTHING HERE READS THE CALLER'S ENVIRONMENT. A lane window exports
`WORKBENCHES_CLAUDE_WINDOW_REF`, `_WINDOW_ID`, `TMUX` and the `LANES_*` seams,
which are exactly what these blocks read, so the environment is an explicit
dict and never `os.environ` plus changes. `lanes-edit.sh` is a stub on a
private `PATH` and `tmux` is a shell function, so nothing reaches a register,
a tmux server or the network.
"""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

import pytest

from conftest import REPO, WINDOWS_SKIP
from test_skill_shell_blocks import SHELL_TAGS, fenced_blocks

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None, reason="the skill's blocks are shell")]

SKILL = REPO / "skills/handoff/SKILL.md"

SHELLS = [
    pytest.param("bash", id="bash"),
    pytest.param("zsh", id="zsh", marks=pytest.mark.skipif(
        shutil.which("zsh") is None, reason="no zsh here")),
]

#: What `lanes-edit.sh`'s `canon_lane` writes to stderr before it returns 2 for
#: two rows whose lane names differ only by case (`lanes-edit.sh`, the
#: `cl_n -gt 1` arm), cut to its first sentence of advice.
WORDS_15D = (
    "lanes-edit: the register has 2 rows whose lane names differ only by case "
    "for 'repo-1': repo-1 Repo-1\n"
    "lanes-edit: a lane name is ONE name under any case (Amendment 15), so no "
    "read and no write under it is unambiguous. Merge them into one row "
    "(Amendment 15(d)): append the newer row's session id(s) to the older "
    "row's session cell, in order.\n")

#: What a `lanes-edit.sh` predating a subcommand writes from its `*)` arm.
WORDS_OLD = "lanes-edit: unknown subcommand 'some-verb' (verify-row|log|who)\n"


# --- the blocks, as the file holds them --------------------------------------

def _shell_blocks() -> List[str]:
    return [b.body for b in fenced_blocks(SKILL.read_text(encoding="utf-8"))
            if b.tag in SHELL_TAGS]


def _one_block(marker: str) -> List[str]:
    found = [b for b in _shell_blocks() if marker in b]
    assert len(found) == 1, (
        f"expected exactly one shell block of {SKILL.name} carrying "
        f"{marker!r}, found {len(found)}: this test is stale")
    return found[0].split("\n")


def _cut(lines: List[str], first: str, last: str, exact_last: bool) -> str:
    """The lines from the one starting `first` to the next one that is `last`
    (or starts with it), inclusive — the shell suite's awk ranges."""
    starts = [i for i, line in enumerate(lines) if line.startswith(first)]
    assert len(starts) == 1, f"{first!r} opens {len(starts)} lines: stale"
    for j in range(starts[0] + 1, len(lines)):
        if (lines[j] == last) if exact_last else lines[j].startswith(last):
            return "\n".join(lines[starts[0]:j + 1]) + "\n"
    raise AssertionError(f"no {last!r} after {first!r}: this test is stale")


def sread_fence() -> str:
    """`sread()` through its closing `}` — `sfence_probe`'s
    `awk '/^sread\\(\\) \\{/,/^\\}$/'`."""
    return _cut(_one_block("sread() {"), "sread() {", "}", exact_last=True)


def step1_block() -> str:
    """Step 1's whole block: the window name, the workstation and the three
    rungs, each read through `sread`."""
    return "\n".join(_one_block('sread row_probe ')) + "\n"


def window_block() -> str:
    """Step 4's `window` sub-field, from the live `#S:#I` read through the line
    that puts the `<@id>` beside it — `skill_win_of`'s range."""
    first = "win=\"$(tmux display-message -p '#S:#I'"
    return _cut(_one_block(first), first,
                '[[ "$wid" =~ ^@[0-9]+$ ]] && win=', exact_last=False)


# --- a sandbox with a stub helper and no inherited environment ---------------

class Verb(NamedTuple):
    rc: int
    out: str = ""
    err: str = ""


class Sandbox:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.bin = root / "bin"
        self.bin.mkdir()
        (root / "home").mkdir()
        (root / "tmp").mkdir()
        self.calls = root / "helper-calls"
        self.helper = self.bin / "lanes-edit.sh"
        usage = self.bin / "claude-usage"
        usage.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        usage.chmod(usage.stat().st_mode | stat.S_IXUSR)
        dirs: List[str] = [str(self.bin)]
        for tool in ("bash", "zsh"):
            found = shutil.which(tool)
            if found and os.path.dirname(found) not in dirs:
                dirs.append(os.path.dirname(found))
        for fallback in ("/usr/bin", "/bin"):
            if fallback not in dirs:
                dirs.append(fallback)
        self.env: Dict[str, str] = {
            "HOME": str(root / "home"), "PATH": os.pathsep.join(dirs),
            "TMPDIR": str(root / "tmp"), "LC_ALL": "C", "TZ": "UTC",
        }

    def stub(self, verbs: Dict[str, Verb]) -> None:
        """`lanes-edit.sh`: each verb answers as given, and any other one is an
        old helper's unknown subcommand. Every call is logged with the
        `LANES_NO_FETCH` it was made under."""
        arms = []
        for verb, (rc, out, err) in verbs.items():
            arms.append(f"  {verb}) printf '%s' {shlex.quote(out)}; "
                        f"printf '%s' {shlex.quote(err)} >&2; exit {rc} ;;")
        self.helper.write_text(
            "#!/bin/sh\n"
            f"printf '%s|%s\\n' \"${{LANES_NO_FETCH-unset}}\" \"$*\" >> "
            f"{shlex.quote(str(self.calls))}\n"
            "case \"$1\" in\n" + "\n".join(arms) + "\n"
            "  *) printf \"lanes-edit: unknown subcommand '%s'\\n\" \"$1\" >&2;"
            " exit 2 ;;\nesac\n", encoding="utf-8")
        self.helper.chmod(self.helper.stat().st_mode | stat.S_IXUSR)

    def logged(self) -> List[str]:
        if not self.calls.exists():
            return []
        return self.calls.read_text(encoding="utf-8").splitlines()

    def run(self, shell: str, script: str,
            extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        env = dict(self.env)
        env.update(extra or {})
        argv = [shutil.which(shell) or shell]
        if shell == "zsh":
            argv.append("-f")
        return subprocess.run([*argv, "-c", script], cwd=str(self.root),
                              env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, check=False,
                              timeout=60)


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


def _sread_script(box: Sandbox) -> str:
    return (f"L={shlex.quote(str(box.helper))}\n" + sread_fence() +
            "v=unset\n"
            "sread v \"'a thing it is not'\" some-verb arg1\n"
            "printf 'AFTER rc=%s v=[%s]\\n' \"$?\" \"$v\"\n")


# --- #72 item 8: the fence ---------------------------------------------------

@pytest.mark.parametrize("shell", SHELLS)
def test_an_exit_2_carrying_amendment_15d_stops_the_skill(box: Sandbox,
                                                          shell: str) -> None:
    """RED at 08e7550. A read that exits 2 with `canon_lane`'s words is a
    REFUSAL: the fence stops the skill where it stands (nothing after the read
    runs), says so naming the read, and relays the helper's own words. The
    words come from asking the same read again with only its stderr kept, so
    the helper sees the same arguments and `LANES_NO_FETCH=1` both times."""
    box.stub({"some-verb": Verb(2, "ANSWER\n", WORDS_15D)})
    proc = box.run(shell, _sread_script(box))
    assert "AFTER" not in proc.stdout, (
        "the fence fell through on Amendment 15(d)'s refusal and the skill "
        f"carried on with an empty answer (#72 item 8):\n{proc.stdout}")
    assert proc.returncode == 2, (proc.returncode, proc.stderr)
    assert "REFUSED" in proc.stderr, proc.stderr
    assert "Amendment 15(d)" in proc.stderr, proc.stderr
    assert "some-verb" in proc.stderr, "the refusal must name the read"
    assert "differ only by case for 'repo-1'" in proc.stderr, (
        "the helper's own words must be relayed")
    assert "will not bind a lane" in proc.stderr, proc.stderr
    assert box.logged() == ["1|some-verb arg1", "1|some-verb arg1"], box.logged()


class FenceCase(NamedTuple):
    verb: Verb
    stdout: str
    returncode: int


FENCE_CASES = {
    # 2 from a helper predating the read: still the next rung, as before.
    "old-helper-2": FenceCase(Verb(2, "ANSWER\n", WORDS_OLD),
                              "AFTER rc=0 v=[]\n", 0),
    "silent-2": FenceCase(Verb(2, "ANSWER\n", ""), "AFTER rc=0 v=[]\n", 0),
    "no-answer-8": FenceCase(Verb(8, "ANSWER\n", ""), "AFTER rc=0 v=[]\n", 0),
    "answer-0": FenceCase(Verb(0, "ANSWER\n", ""), "AFTER rc=0 v=[ANSWER]\n", 0),
    # A failed read stops the skill, as it did: exit 1, and nothing after it.
    "failed-6": FenceCase(Verb(6, "", "boom\n"), "", 1),
}


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("case", sorted(FENCE_CASES))
def test_every_other_code_reads_as_it_did(box: Sandbox, shell: str,
                                          case: str) -> None:
    """What did not change: an old helper's 2 and a silent 2 still fall to the
    next rung with the variable empty, 8 does too, 0 is the answer, and any
    other code is a read that failed and stops the skill."""
    want = FENCE_CASES[case]
    box.stub({"some-verb": want.verb})
    proc = box.run(shell, _sread_script(box))
    assert (proc.stdout, proc.returncode) == (want.stdout, want.returncode), (
        proc.stdout, proc.returncode, proc.stderr)
    if case == "failed-6":
        assert "failed (exit 6)" in proc.stderr, proc.stderr
    else:
        assert "REFUSED" not in proc.stderr, proc.stderr


STEP1_TMUX = (
    "tmux() { case \"$*\" in *'#W'*) printf '%s\\n' \"$STUB_WINDOW\" ;; "
    "*window_id*) printf '@5\\n' ;; *'#S:#I'*) printf 's:1\\n' ;; esac; }\n")

SWAP_ROW = "other-7\t2026-10-18T00:00:00Z\n"

#: Amendment 15(d)'s words for the lane rungs 2 and 3 bind below.
WORDS_15D_OTHER = WORDS_15D.replace("repo-1", "other-7").replace(
    "Repo-1", "Other-7")

#: The two rungs below the window name, each answering `other-7` for a window
#: named `zsh` — which the register has no row for (`register-row` 8). This is
#: the shape the independent review of #260 measured.
LOWER_RUNGS = {
    "rung-2-window-lane": {"register-row": Verb(8),
                           "window-lane": Verb(0, "other-7\n")},
    "rung-3-swapped": {"register-row": Verb(8), "window-lane": Verb(8),
                       "swapped": Verb(0, SWAP_ROW)},
}


def _step1(box: Sandbox, shell: str, window: str,
           verbs: Dict[str, Verb]) -> subprocess.CompletedProcess:
    box.stub(dict(verbs, workstation=Verb(0, "Eagle\tconfigured\n")))
    script = (f"L={shlex.quote(str(box.helper))}\n" + sread_fence() +
              STEP1_TMUX + step1_block())
    return box.run(shell, script, {"STUB_WINDOW": window})


def _verbs(box: Sandbox) -> List[str]:
    return [line.split("|", 1)[1].split()[0] for line in box.logged()]


@pytest.mark.parametrize("shell", SHELLS)
def test_step_1_does_not_bind_the_newest_swap_over_a_case_twin_row(
        box: Sandbox, shell: str) -> None:
    """RED at 08e7550, the consequence #72 item 8 names. The window is named
    `repo-1` and the register holds `repo-1` and `Repo-1`, so `register-row`
    refuses with 2 and Amendment 15(d)'s words. The skill used to read that as
    "this window is not a lane", ask `window-lane` (8, none) and then take the
    workstation's NEWEST SWAP, `other-7`: a different lane, printed as this
    one. Now step 1 stops before any rung below the refusal is asked."""
    proc = _step1(box, shell, "repo-1", {
        "register-row": Verb(2, "", WORDS_15D),
        "window-lane": Verb(8),
        "swapped": Verb(0, SWAP_ROW),
    })
    assert "lane=" not in proc.stdout, (
        "step 1 bound a lane over Amendment 15(d)'s refusal (#72 item 8):\n"
        f"{proc.stdout}")
    assert proc.returncode == 2, (proc.returncode, proc.stderr)
    assert "Amendment 15(d)" in proc.stderr, proc.stderr
    assert "window-lane" not in _verbs(box), (
        f"a rung below the refusal was asked: {box.logged()}")
    assert "swapped" not in _verbs(box), (
        f"a rung below the refusal was asked: {box.logged()}")


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("rung", sorted(LOWER_RUNGS))
def test_step_1_refuses_a_case_twin_lane_whichever_rung_bound_it(
        box: Sandbox, shell: str, rung: str) -> None:
    """RED at c9d681f (the review of #260). Rung 1 is refused through
    `register-row`, but rungs 2 and 3 answer with a record's lane field and the
    swap row's first cell, which nothing read through the resolver: a lane
    whose register holds `other-7` and `Other-7` bound from either, and step 1
    printed `lane=other-7` and exited 0. The bound name is now read through
    `canon-lane` and the fence, as `lane-handoff` does after its rungs, so
    Amendment 15(d)'s 2 refuses there whichever rung answered."""
    proc = _step1(box, shell, "zsh", dict(
        LOWER_RUNGS[rung], **{"canon-lane": Verb(2, "", WORDS_15D_OTHER)}))
    assert "lane=" not in proc.stdout, (
        f"step 1 bound a case-twin lane from {rung} (#72 item 8, the review "
        f"of #260):\n{proc.stdout}")
    assert proc.returncode == 2, (proc.returncode, proc.stderr)
    assert "Amendment 15(d)" in proc.stderr, proc.stderr
    assert "canon-lane" in proc.stderr, "the refusal must name the read"
    assert "1|canon-lane other-7" in box.logged(), box.logged()


class CanonCase(NamedTuple):
    verb: Verb
    returncode: int
    lane: Optional[str]      # the `lane=` line step 1 prints, None for none


CANON_CASES = {
    # The register row's spelling replaces the bound one.
    "row-spelling": CanonCase(Verb(0, "Other-7\n"), 0, "Other-7"),
    # A read that failed stops the skill (66 is an alias table that could not
    # be read, which `canon-lane` carries rather than flattening to 2).
    "failed-66": CanonCase(Verb(66, "", "lanes-edit: aliases.tsv COULD NOT "
                                "BE READ\n"), 1, None),
    "same-name": CanonCase(Verb(0, "other-7\n"), 0, "other-7"),
    "old-helper-2": CanonCase(Verb(2, "", WORDS_OLD), 0, "other-7"),
}


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("case", sorted(CANON_CASES))
def test_step_1_reads_the_bound_name_through_canon_lane(
        box: Sandbox, shell: str, case: str) -> None:
    """What `canon-lane`'s other answers do to a lane rung 3 bound: the
    register row's spelling replaces the bound one, a failed read stops the
    skill like every failed read through the fence, and an answer naming the
    same lane or an old helper's 2 leaves `other-7` as it was. Every case is
    RED at c9d681f, where `canon-lane` was never asked; `row-spelling` and
    `failed-66` also printed a different answer there."""
    want = CANON_CASES[case]
    proc = _step1(box, shell, "zsh", dict(
        LOWER_RUNGS["rung-3-swapped"], **{"canon-lane": want.verb}))
    assert proc.returncode == want.returncode, (proc.returncode, proc.stderr)
    if want.lane is None:
        assert "lane=" not in proc.stdout, proc.stdout
        assert "failed (exit 66)" in proc.stderr, proc.stderr
    else:
        assert proc.stdout.splitlines()[-1] == f"lane={want.lane}", proc.stdout
    assert "1|canon-lane other-7" in box.logged(), box.logged()


@pytest.mark.parametrize("shell", SHELLS)
def test_step_1_still_falls_through_an_old_helpers_2(box: Sandbox,
                                                     shell: str) -> None:
    """The fall-through the fence keeps: a `register-row` that exits 2 as an
    old helper's unknown subcommand is "no answer", and step 1 goes on to the
    newest swap exactly as it did before the fix. That helper has no
    `canon-lane` either (the stub's unknown-subcommand 2), and the swap's name
    is kept."""
    proc = _step1(box, shell, "repo-1", {
        "register-row": Verb(2, "", WORDS_OLD),
        "window-lane": Verb(8),
        "swapped": Verb(0, SWAP_ROW),
    })
    assert proc.returncode == 0, (proc.returncode, proc.stderr)
    assert proc.stdout.splitlines()[-1] == "lane=other-7", proc.stdout


# --- #80 item 4: the `<session>:<index>` ref ---------------------------------

class WinCase(NamedTuple):
    live_ref: str
    live_id: str
    env_ref: str
    env_id: str
    want: str


WIN_CASES = {
    "clean": WinCase("s:1", "@12", "", "", "s:1 @12"),
    # RED at 08e7550: each of these was taken by the prefix glob.
    "live-ref-junk": WinCase("s:1junk", "@12", "", "", "@12"),
    "env-ref-junk": WinCase("", "", "s:1junk", "@12", "@12"),
    "live-junk-falls-to-env": WinCase("s:1junk", "", "s:4", "", "s:4"),
    "no-session-part": WinCase(":1", "", "", "", ""),
    "env-ref-newline": WinCase("", "", "s:1\njunk", "", ""),
    # RED at c9d681f too (the review of #260): the regex's `.` matches a line
    # break, so a ref with one BEFORE the index passed it, and `log PAUSED`
    # refuses a payload carrying a newline or a carriage return.
    "env-ref-newline-before-index": WinCase("", "", "junk\ns:1", "", ""),
    "live-ref-newline-falls-to-env": WinCase("junk\ns:1", "", "s:4", "", "s:4"),
    "env-ref-carriage-return": WinCase("", "", "junk\rs:1", "", ""),
    # Unchanged: digits after the LAST colon, no index at all, and the
    # `<@id>` beside it, which was already checked whole.
    "last-colon": WinCase("s:1:2", "", "", "", "s:1:2"),
    "no-index": WinCase("s:", "", "", "", ""),
    "id-junk-live-and-env": WinCase("s:1", "@12junk", "", "@12junk", "s:1"),
}


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("case", sorted(WIN_CASES))
def test_the_window_ref_is_checked_as_a_whole_string(box: Sandbox, shell: str,
                                                     case: str) -> None:
    """Step 4's `window` sub-field takes a `<session>:<index>` only where the
    WHOLE value is one — from tmux and from the launcher's export alike — so
    `s:1junk` is dropped, and a live value that is dropped falls back to the
    export as an empty one does."""
    want = WIN_CASES[case]
    script = (
        "tmux() { case \"$*\" in *'#S:#I'*) printf '%s\\n' \"$STUB_REF\" ;; "
        "*window_id*) printf '%s\\n' \"$STUB_ID\" ;; esac; }\n"
        + window_block() + "printf '[%s]' \"$win\"\n")
    proc = box.run(shell, script, {
        "STUB_REF": want.live_ref, "STUB_ID": want.live_id,
        "WORKBENCHES_CLAUDE_WINDOW_REF": want.env_ref,
        "WORKBENCHES_CLAUDE_WINDOW_ID": want.env_id,
    })
    assert proc.returncode == 0, (proc.returncode, proc.stderr)
    assert proc.stdout == f"[{want.want}]", (
        f"{case}: tmux #S:#I={want.live_ref!r} #{{window_id}}="
        f"{want.live_id!r}, exported ref={want.env_ref!r} id={want.env_id!r} "
        f"recorded {proc.stdout!r}, expected [{want.want}] (#80 item 4)")


def test_no_prefix_glob_is_left_on_a_window_ref() -> None:
    """The two globs #80 item 4 names are gone from every shell block of the
    skill, so a later copy cannot bring one back beside the fixed lines."""
    left = [line.strip() for block in _shell_blocks()
            for line in block.split("\n") if "*:[0-9]*)" in line]
    assert not left, f"a prefix glob still checks a window ref: {left}"
