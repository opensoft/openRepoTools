# SPDX-License-Identifier: Apache-2.0
"""A utility run through `command` under `set -e`, on macOS's bash 3.2 (#292).

THE QUIRK. Under `set -e`, GNU bash 3.2.57, the `/bin/bash` every Mac ships,
exits when a utility run through the `command` builtin fails, even where
`set -e` is suspended: on the left of `||` or `&&`, after `!`, in an `if`,
`while` or `until` condition, and in a function called from any of those.
bash 5.2 carries on there, as POSIX says it must. Measured under
`set -euo pipefail` on a musl build of GNU bash 3.2.57 and on bash 5.2.21:

* exits under 3.2 and carries on under 5.2: `command false || :`,
  `if command grep -q x /dev/null; then :; fi`, `! command false`,
  `rc=0; command false || rc=$?`, `while command false; do :; done`,
  `{ command false; } || :`, `FOO=1 command false || :`, a `case` arm's
  `command cd /nonexistent || :`, and `f() { command false || :; }; f`;
* the same under both: `grep -q x /dev/null || :`, with no `command`;
  `command -v nonexistent || :`; `printf '' | command grep -q x || :`, where
  bash forks the pipeline element; `x=$(command false; echo after)`, because
  neither bash runs a command substitution under `set -e` outside POSIX mode;
  and `(command false) || :`, a subshell whose whole body is the command.

THE THREE PLACES IT ENDED A SHIPPED COMMAND on `a42946e`, each run below the
way its script runs it. Each case FAILS under bash 3.2.57 before #292's fix
and passes under bash 5.2, before the fix and after it:

* `lanes --worktrees` (`lanes:317`): `grep -v` drops the helper's "not
  fetching" note from its stderr, and exits 1 when it has selected nothing, so
  a helper that said nothing else ended `lanes` with exit 1 and no output;
* `openRepoTools`' `wip_hygiene_lines` (`:4014`): its `grep -Fqx` fails
  exactly when a hygiene line is missing from the `.gitignore`, which is the
  case the function exists for;
* `lane-end`'s `dh_settle_gone` (`:1377`): `command -p ps -p` fails exactly
  when the pid is gone, which is the answer the function waits for.

THESE CASES RUN UNDER THE `bash` ON PATH, which is the bash the scripts run
under, since each starts `#!/usr/bin/env bash`. CI cannot show their red: the
macOS jobs left `tests.yml` with #227, so every job runs Linux's bash 5. To
see it, put a directory holding a bash 3.2 first on PATH and run them again;
on a Mac whose PATH has no other bash, that is `/bin/bash` already.

WHAT LINUX CI CAN SEE is the scan below. It reads every shipped bash file that
turns `set -e` on with bash's OWN PARSER, and it allows a `command <utility>`
only where `ALLOWED` names the use and the reason it cannot trip the quirk.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP,
              pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="bash is not installed")]

LANES = REPO / "lanes"
OPEN_REPO_TOOLS = REPO / "openRepoTools"
LANE_END = REPO / "lane-end"

#: The note `lanes-edit.sh` prints when it reads the register without a fetch,
#: and the one line `lanes --worktrees` drops from the helper's stderr.
NOT_FETCHING = ("lanes-edit: LANES_NO_FETCH=1 — not fetching; reading origin/main "
                "as the ref already stands here")


def bash_env(**extra: str) -> dict:
    """The caller's environment, without what could change what bash runs.

    `BASH_ENV` and `ENV` are files a non-interactive bash sources first, and
    an exported `BASH_FUNC_*` is a function every bash child defines, so a
    developer's own would change these answers. PATH STAYS: the `bash` on it
    is the bash under test.
    """
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("LANES_", "TMUX", "CLAUDE_", "BASH_FUNC_"))
           and k not in ("BASH_ENV", "ENV")}
    env.update(extra)
    return env


def source_between(path: Path, start: str, end: str, after: str = "") -> str:
    """The text of `path` from `start` through the first `end` that follows
    `after` (itself searched for from `start`)."""
    source = path.read_text(encoding="utf-8")
    for mark in (start, after):
        assert mark in source, f"{path.name} no longer carries {mark.strip()!r}"
    i = source.index(start)
    return source[i:source.index(end, source.index(after, i)) + len(end)]


# --- lanes --worktrees (lanes:317) --------------------------------------------

def tree_row() -> str:
    """One `TREE` row of `lanes-edit.sh worktrees`, sixteen fields joined by
    the unit separator, in the order `lanes` reads them."""
    return "\x1f".join([
        "TREE", "Eagle", "openRepoTools-4", "lane", "/w/openRepoTools-4/tree-292",
        "fix/bash32-command-errexit-292", "main", "RUNNING", "1", "-", "1",
        "2026-10-20T23:00Z", "-", "0", "0", "inventory"]) + "\n"


@pytest.mark.parametrize("helper_stderr", [
    pytest.param(NOT_FETCHING + "\n", id="only-the-not-fetching-note"),
    pytest.param("", id="nothing"),
    pytest.param(NOT_FETCHING + "\nlanes-edit: read: the sidecars\n",
                 id="the-note-and-another-line"),
])
def test_lanes_worktrees_lists_the_trees_whatever_the_helper_said_on_stderr(
        tmp_path, helper_stderr):
    """`lanes --worktrees` filters the helper's stderr with `grep -v`, which
    exits 1 when it selects nothing: when the helper printed only the "not
    fetching" note, or nothing at all. Spelled `command grep … || :`, that
    ended `lanes` under bash 3.2 with exit 1 and NO OUTPUT, before the header.
    The third case selects a line, so it never tripped; it pins that the
    filter passes every other line on and drops only the note."""
    rows = tmp_path / "rows"
    rows.write_text(tree_row(), encoding="utf-8")
    err = tmp_path / "err"
    err.write_text(helper_stderr, encoding="utf-8")
    helper = tmp_path / "lanes-edit.sh"
    helper.write_text('#!/bin/sh\n'
                      '[ "$1" = worktrees ] || { echo "unexpected: $*" >&2; exit 70; }\n'
                      'cat -- "$FAKE_ROWS"\ncat -- "$FAKE_ERR" >&2\n', encoding="utf-8")
    helper.chmod(0o755)
    (tmp_path / "home").mkdir()
    (tmp_path / "tmp").mkdir()
    proc = subprocess.run(
        ["bash", str(LANES), "--worktrees", "--all"], capture_output=True, text=True,
        check=False, timeout=60, stdin=subprocess.DEVNULL,
        env=bash_env(HOME=str(tmp_path / "home"), TMPDIR=str(tmp_path / "tmp"),
                     LANES_EDIT=str(helper), FAKE_ROWS=str(rows), FAKE_ERR=str(err)))
    assert proc.returncode == 0, (
        f"lanes --worktrees exited {proc.returncode}\nstdout: {proc.stdout!r}\n"
        f"stderr: {proc.stderr!r}")
    assert "/w/openRepoTools-4/tree-292" in proc.stdout, proc.stdout
    assert "1 worktree(s) in 1 lane(s) on 1 workstation(s)" in proc.stdout, proc.stdout
    assert "not fetching" not in proc.stderr, proc.stderr
    for line in helper_stderr.splitlines():
        if "not fetching" not in line:
            assert line in proc.stderr, (line, proc.stderr)


# --- openRepoTools' wip_hygiene_lines (openRepoTools:4014) -----------------------

#: `openRepoTools`' `WIP_HYGIENE_LINES`, restated so a case can name its answer.
HYGIENE_LINES = ("__pycache__/", "*.pyc", "*.pyo", ".pytest_cache/", ".mypy_cache/",
                 ".ruff_cache/", "node_modules/", ".venv/", "venv/", "site-packages/")


@pytest.mark.parametrize("have", [
    pytest.param("*.swp\n", id="carries-none-of-them"),
    pytest.param("__pycache__/\n*.pyc\nvenv/\n", id="carries-three"),
    pytest.param("".join(f"{x}\n" for x in HYGIENE_LINES), id="carries-them-all"),
])
def test_wip_hygiene_lines_collects_the_missing_lines_under_set_e(tmp_path, have):
    """`wip_hygiene_lines` runs under `openRepoTools`' `set -euo pipefail`,
    called as its caller calls it: on the left of `||`, appending to the file
    it reads. Its `grep -Fqx` fails exactly when a line is MISSING, which is the
    case the function is for; spelled `command grep`, that ended the script
    under bash 3.2 instead of collecting the line, part-way through writing a
    template's `.gitignore`. A file that carries every line never fails a
    `grep`, so that case never tripped; it pins that nothing is repeated."""
    gitignore = tmp_path / "gitignore"
    gitignore.write_text(have, encoding="utf-8")
    function = source_between(OPEN_REPO_TOOLS, "\nWIP_HYGIENE_LINES=(", "\n}\n",
                              after="\nwip_hygiene_lines()")
    script =("set -euo pipefail\n" + function
              + '\nwip_hygiene_lines "$1" >>"$1" || { echo "the caller refused" >&2; exit 3; }\n'
              + "printf 'reached\\n'\n")
    proc = subprocess.run(["bash", "-c", script, "bash", str(gitignore)],
                          capture_output=True, text=True, check=False, timeout=60,
                          env=bash_env())
    assert (proc.returncode, proc.stdout) == (0, "reached\n"), (
        f"exit {proc.returncode}\nstdout: {proc.stdout!r}\nstderr: {proc.stderr!r}")
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    for line in HYGIENE_LINES:
        assert lines.count(line) == 1, (line, lines)


# --- lane-end's dh_settle_gone (lane-end:1377) -----------------------------------

def test_lane_end_settles_a_gone_pid_as_gone_under_set_e(tmp_path):
    """`dh_settle_gone` answers 0 once `kill -0` AND `ps -p` both say a pid is
    gone. It runs under `lane-end`'s `set -euo pipefail`, called on the left of
    `||` and asking `ps` after `!` in an `if`, and `ps -p` fails exactly when
    the pid is gone: spelled `! command -p ps -p …`, that ended `lane-end`
    under bash 3.2 at the moment it had its answer.

    THE `ps` ON PATH HERE CALLS EVERY PID ALIVE, as the shell suite's fake does
    for its whole run. `command -p` is how `dh_settle_gone` reaches the REAL
    `ps` past it (the comment above the function says why), so a bare `ps -p`
    would answer "still alive" for two seconds and this case would fail too.
    """
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    (fakebin / "ps").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (fakebin / "ps").chmod(0o755)
    gone = subprocess.Popen(["true"])
    gone.wait()
    function = source_between(LANE_END, "\n    dh_settle_gone() {", "\n    }\n",
                              after="\n    dh_settle_gone() {")
    script = ("set -euo pipefail\n" + function
              + 'settled=1; dh_settle_gone "$1" || settled=0\n'
              + "printf 'settled=%s\\n' \"$settled\"\n")
    env = bash_env()
    env["PATH"] = str(fakebin) + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(["bash", "-c", script, "bash", str(gone.pid)],
                          capture_output=True, text=True, check=False, timeout=60, env=env)
    assert (proc.returncode, proc.stdout) == (0, "settled=1\n"), (
        f"exit {proc.returncode}\nstdout: {proc.stdout!r}\nstderr: {proc.stderr!r}")


# --- the scan Linux CI can see ---------------------------------------------------

#: THE SCAN, IN BASH. `command` and `set` are aliased to marker words, and the
#: file is parsed as the body of a function that is never called. bash expands
#: an alias only where the word is in COMMAND POSITION, as the parser reads it,
#: and `declare -f` prints the parsed function back with the markers in place.
#: So a `command` in a string, a heredoc or a comment is never a finding, and
#: every `command` bash would run as the builtin is one. bash 3.2.57 and 5.2.21
#: print every line this file keys on alike.
#:
#: A command substitution's text is printed as it was written, so a `command`
#: inside `$( )` or backticks is not seen. Neither bash runs a command
#: substitution under `set -e` outside POSIX mode (measured: under 3.2.57,
#: `x=$(command false; echo after)` sets `after`), so none can trip the quirk.
SCAN = r"""
shopt -s expand_aliases
alias command=__ort292_command_word__
alias set=__ort292_set_word__
scanned=$(cat -- "$1") || exit 3
eval "__ort292_scanned__() {
$scanned
}" || exit 4
declare -f __ort292_scanned__
"""
COMMAND_WORD = "__ort292_command_word__"
SET_WORD = "__ort292_set_word__"

#: `command -v`, `-V` and `-pv` look a name up and run nothing.
LOOKUP = re.compile(r"-[pvV]*[vV][pvV]*")

#: THE USES THAT STAY, each with the reason it cannot trip the quirk. A key is
#: the line as `declare -f` prints it, `command` put back; the scan's failure
#: prints a new use in exactly this form. Each entry allows ONE occurrence.
ALLOWED = {
    ("lanes", r"""printf '%s\n' "$fetch_err" | command grep '^read: ' 1>&2 || :"""):
        "a pipeline element: bash forks it, so `set -e` ending that child at "
        "`grep` ends it with grep's own status, which the pipeline hands to "
        "`|| :` as under bash 5 (measured: `printf '' | command grep -q x || :` "
        "carries on under 3.2.57)",
    ("lane-end", r"""if ! kill -0 "$1" 2> /dev/null && ! ( command -p ps -p "$1" > /dev/null 2>&1 ); then"""):
        "the whole body of a subshell, whose status is ps's whether or not "
        "`set -e` ends it there (measured: `(command false) || :` carries on "
        "under 3.2.57). `command -p` stays: the shell suite fakes `ps` on PATH "
        "for its whole run, and `command -p` reaches the real one on the "
        "default PATH, as the comment above `dh_settle_gone` says",
}


def shipped_bash() -> list:
    """Every bash file `--install` places, read out of the installer's own
    `INSTALLABLES`, as `test_repo_hygiene` reads it for the modes: the next
    command this repository ships is scanned without anyone coming here."""
    text = OPEN_REPO_TOOLS.read_text(encoding="utf-8")
    match = re.search(r"^INSTALLABLES=\(([^)]*)\)$", text, re.MULTILINE)
    assert match, "openRepoTools no longer declares `INSTALLABLES=( … )`"
    return [name for name in match.group(1).split()
            if (REPO / name).read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n")]


def parsed(path: Path) -> str:
    """`path` as bash's parser read it, with the two marker words in place."""
    proc = subprocess.run(["bash", "-c", SCAN, "scan", str(path)], capture_output=True,
                          encoding="utf-8", errors="replace", check=False, timeout=120,
                          env=bash_env())
    assert proc.returncode == 0, f"bash could not parse {path}:\n{proc.stderr}"
    return proc.stdout


def turns_errexit_on(printed: str) -> bool:
    """Whether any `set` the parser saw turns `set -e` on (`-e`, a cluster
    holding `e`, or `-o errexit`). A `set -e` anywhere counts for the whole
    file: a function the scan reads is not asked where it is called from."""
    for match in re.finditer(re.escape(SET_WORD) + r"((?:[ \t]+[^ \t;&|]+)*)", printed):
        args = match.group(1).split()
        for i, arg in enumerate(args):
            if arg == "--":
                break
            if re.fullmatch(r"-[A-Za-z]*e[A-Za-z]*", arg):
                return True
            if arg == "-o" and args[i + 1:i + 2] == ["errexit"]:
                return True
    return False


def command_uses(printed: str) -> list:
    """Every line holding a `command` that runs a utility, as printed, with
    `command` and `set` put back and the trailing `;` dropped; once per use."""
    found = []
    for line in printed.splitlines():
        for match in re.finditer(re.escape(COMMAND_WORD) + r"(?=[ \t]|$)", line):
            first = line[match.end():].split()[:1]
            if first and LOOKUP.fullmatch(first[0]):
                continue
            found.append(line.strip().rstrip(";").rstrip()
                         .replace(COMMAND_WORD, "command").replace(SET_WORD, "set"))
    return found


def test_no_shipped_errexit_script_runs_a_utility_through_command_where_bash_32_exits():
    """THE QUIRK CANNOT COME BACK UNSEEN. Every `command <utility>` in a
    shipped bash file that turns `set -e` on is either named in `ALLOWED`, with
    the reason it cannot trip bash 3.2, or a finding.

    The scan asks no question about CONTEXT, on purpose: a plain statement
    inside a function is in a suspended context whenever the function is
    called from one, and no scan of one file sees every caller. So every use is
    named or gone. The fix for a finding is the bare utility, as the rest of
    these files write it; or a subshell whose whole body is the command, where
    `command` matters, with an `ALLOWED` entry saying why.

    A FILE THAT NEVER TURNS `set -e` ON IS NOT SCANNED, because no failure
    ends it: `lanes-edit.sh`, `lane-handoff`, `lane-rename` and
    `claude-restart-check` today, each for the reason `test_repo_hygiene`
    gives. The day one of them turns it on, its uses are findings here.
    """
    scanned, found = [], Counter()
    for name in shipped_bash():
        printed = parsed(REPO / name)
        text = (REPO / name).read_text(encoding="utf-8")
        if "\nset -euo pipefail\n" in text:
            assert turns_errexit_on(printed), f"the scan missed {name}'s `set -euo pipefail`"
        if not turns_errexit_on(printed):
            continue
        scanned.append(name)
        found.update((name, line) for line in command_uses(printed))
    assert {"openRepoTools", "lanes", "lane-end"} <= set(scanned), scanned
    allowed = Counter(ALLOWED.keys())
    unexplained = sorted((found - allowed).elements())
    stale = sorted((allowed - found).elements())
    assert not unexplained and not stale, (
        "macOS's bash 3.2 ends a `set -e` script where a utility run through "
        "`command` fails, even on the left of `||` or `&&`, after `!`, in a "
        "condition, or in a function called from one (#292).\n"
        + "".join(f"  NOT IN ALLOWED: {n}: {line}\n" for n, line in unexplained)
        + "".join(f"  ALLOWED BUT GONE: {n}: {line}\n" for n, line in stale)
        + "Drop `command`, or make the command a subshell's whole body and say "
          "why in ALLOWED; delete an entry whose use is gone.")


SYNTHETIC = r"""#!/usr/bin/env bash
set -euo pipefail
note="prose: this command grep -q x is text
command grep -q x on a line of its own is text too"
# command grep -q x in a comment
cat <<'TEXT'
command grep -q x in a heredoc
TEXT
command -v git >/dev/null || :
x=$(command grep -q x /dev/null || echo none)
printf '' | command grep -q x || :
(command false) || :
f() { command grep -q x "$1" || return 1; }
if command test -e /nonexistent; then :; fi
while command false; do :; done
! command false
FOO=1 command -p false || :
"""


@pytest.mark.parametrize("set_line, errexit", [
    ("set -euo pipefail", True), ("set -e", True), ("set -o errexit", True),
    ("set -u", False), ("set +e", False), ("set -- -e", False),
])
def test_the_scan_finds_every_command_in_command_position_and_nothing_else(
        tmp_path, set_line, errexit):
    """The scan's own rule, on a file whose answer is known: prose, a comment,
    a heredoc, a command substitution and `command -v` are not uses; every
    other `command` bash runs as the builtin is one, the safe shapes included,
    because the scan names uses and `ALLOWED` judges them."""
    source = tmp_path / "synthetic"
    source.write_text(SYNTHETIC.replace("set -euo pipefail", set_line, 1), encoding="utf-8")
    printed = parsed(source)
    assert turns_errexit_on(printed) is errexit
    assert command_uses(printed) == [
        "printf '' | command grep -q x || :",
        "( command false ) || :",
        'command grep -q x "$1" || return 1',
        "if command test -e /nonexistent; then",
        "while command false; do",
        "! command false",
        "FOO=1 command -p false || :",
    ]
