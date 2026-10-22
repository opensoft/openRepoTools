# SPDX-License-Identifier: Apache-2.0
"""A directory, a repository or a ref no line can print as it reads is refused (#241).

`openRepoTools` names three values from the environment in its lines as they
were typed: `$OPENREPOTOOLS_BIN_DIR`, in the `$PATH` note, in every `installed
at` line and in every refusal that names a target, and `$OPENREPOTOOLS_REPO`
and `$OPENREPOTOOLS_REF`, in `--version` and in every request and refusal about
the source. A `:` splits a `$PATH`, a newline breaks a line in two, a carriage
return rewrites it, an escape is the terminal's to act on, and a character a
terminal draws as something other than itself shows one name as another's. So
each is asked once, before anything is placed, fetched or named, and a refusal
says which KIND of character it found and never repeats the value.

openRepoShape holds its own `install.sh` and `openRepoShape --install` to the
same rule (its #760, #837, #858, #866 and #940), and this file is that suite's
cases for it, adapted: `CONTROL_RULE` is its table, one answer per row, asked
here of each of the three values. The two cases its #858 left open are rows of
their own, so that nobody changes either by accident: a name a multibyte locale
reads as text is placed, and a lone `0x9B` byte is placed (a known limit).

HERMETIC, LIKE THE REST OF THIS SUITE. Every run has a sandbox `$HOME` that
starts empty, so whatever it holds afterwards is what the run placed, and the
cases that must show nothing was fetched put a `gh` and a `curl` first on
`$PATH` that write down every call and refuse. The values travel in the
environment as Python hands them to a child: a character is its UTF-8, and a
surrogate (`chr(0xDCE9)`) is the one byte it stands for.

THE CHECKOUT ROUTE AND THE PACKAGE ROUTE ARE ONE SCRIPT. The wheel's payload is
this checkout's `openRepoTools` byte for byte, so the cases at the end run the
payload of a fake installed package (`package_layout.package_tree`) through the
same refusals, and show that a package's `--version`, which prints neither the
repository nor the ref, asks neither of them anything.

`wip init` IS ASKED ALL THREE TOO, from every route and with `--dry-run`. Its
step 7 sends the repository and the ref as typed when it runs from an INSTALLED
COPY, which has no pin beside it to read (the review of #241, MUST-1), and the
`link-estates` it runs names the directory as typed in its own lines (the
operator's word, after the review), so it refuses an unsafe one of the three
before it makes or asks anything: the directory in words of its own, since it
places nothing. The cases are under "a bad value stops the run before it asks
anyone anything". The colon, which only the directory refuses (in `wip init` as
in `--install`), has cases of its own beside the rows the rule takes, for the
repository and the ref and for the directory.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import package_layout as layout
from conftest import WINDOWS_SKIP
from test_install_by_rename import installer_function
from test_openrepotools_command import (COMMAND, INSTALLED, NEEDS_JQ,
                                        command_env)
from test_wip_init_command import fake_gh

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="openRepoTools is a bash script"),
              WINDOWS_SKIP]

#: Control characters, typed as their numbers: no escape sequence is written
#: into this file, because a tool that writes it may write the raw character
#: (U+009B is the C1 "control sequence introducer" a terminal runs).
ESCAPE = chr(0x1B)
DELETE = chr(0x7F)
C1_CSI = chr(0x9B)
#: A lone 0xE9 byte, which no UTF-8 text holds, as Python hands one to a
#: child's environment (the byte comes back through `surrogateescape`).
NOT_UTF8 = chr(0xDCE9)
#: U+202E RIGHT-TO-LEFT OVERRIDE, the one of `MISDRAWN` most cases hold, and
#: U+200B ZERO WIDTH SPACE, the one that is drawn as nothing at all.
RLO = chr(0x202E)
ZWSP = chr(0x200B)

#: THE CHARACTERS A TERMINAL DRAWS AS SOMETHING OTHER THAN THEMSELVES, by code
#: point, as the script's `MISDRAWN_CHARACTERS` lists them (openRepoShape
#: #837): the soft hyphen, the twelve bidirectional controls, the line and
#: paragraph separators, and the format characters of no width that nothing
#: needs, three of them past U+FFFF. Written out here, not read from the
#: script, so that a change to its list is a change to this one too: the
#: function test below holds the two to each other.
MISDRAWN = (0x00AD, 0x061C, 0x200B, 0x200E, 0x200F, *range(0x2028, 0x202F),
            *range(0x2060, 0x2070), 0xFEFF, *range(0xFFF9, 0xFFFC),
            *range(0x1D173, 0x1D17B), 0xE0001)

#: What each refusal says of a value, by the kind it found.
HOLDS_A_COLON = "holds a ':'"
HOLDS_A_CONTROL_CHARACTER = "holds a control character"


def drawn_as_another(named: str) -> str:
    """What every refusal of a value holding `named` says of it: the
    `U+XXXX` of each character of `MISDRAWN` in it, comma-separated."""
    return ("holds a character a terminal draws as something other than "
            f"itself ({named}): one that is invisible, is drawn as another "
            "character, ends a line or reorders the text around it")


#: The two locales a value is tried under: `C` reads one byte at a time, and
#: `C.UTF-8` reads UTF-8 text where it is valid.
LOCALES = ["C", "C.UTF-8"]

#: A row of `CONTROL_RULE` the rule takes: the value goes on to the next
#: check, and is placed or printed as typed. A refused one says
#: `HOLDS_A_CONTROL_CHARACTER`, or the code points it names.
TAKEN = "taken"
CONTROL = HOLDS_A_CONTROL_CHARACTER

#: How a value with a letter past ASCII ends, the row a person meets: a
#: directory called `café`, a mirror at `/srv/café/...`, a ref named after one
#: (openRepoShape #940). `[![:print:]]` refused it under `C` as a control
#: character, so the rule is `[[:cntrl:]]` and the C1 bytes, under `LC_ALL=C`.
A_LETTER_PAST_ASCII = "caf" + chr(0xE9)

#: THE TABLE: one answer per row, the same for the directory, the repository
#: and the ref, under `C` and `C.UTF-8` alike. Each row is how a value ends,
#: and what the rule says of it:
#:   * `TAKEN`: an e with an acute accent, a no-break space (whose bytes
#:     `0xC2 0xA0` come right after the C1 range's last, `0xC2 0x9F`), a
#:     Persian word whose parts U+200C keeps apart and an emoji sequence that
#:     U+200D makes (which that script and that sequence need), U+2026 and
#:     U+FF21 (which start with the bytes most of `MISDRAWN` start with), and
#:     a subdivision flag (whose first three bytes are U+E0001's);
#:   * `TAKEN` AS A KNOWN LIMIT (openRepoShape #858 and #867): a lone `0x9B`
#:     byte, a lone `0xE9` byte (Latin-1's e with an acute accent) and an
#:     escape in an overlong form (`0xC0 0x9B`), none of them UTF-8. A
#:     terminal that reads UTF-8 draws such a byte as a character it cannot
#:     read, and only one set to an 8-bit charset acts on it;
#:   * `CONTROL`: an escape, a newline, a carriage return, a tab, DEL, the
#:     first, the last and two more of the C1 controls (so that an arm that
#:     stops one short at either end is caught), a newline at the end, and a
#:     lone `0xE9` byte before U+009B, which makes a UTF-8 locale's
#:     `[[:cntrl:]]` match byte by byte and miss the control;
#:   * a control character before a misdrawn one, which is the control's;
#:   * a code point: U+202E, U+200B, U+2028 and U+2029, which no control check
#:     matches in any locale, and two at once, named in `MISDRAWN`'s order.
#: A refused value ends in `forged`, or in a newline after it, which no
#: refusal may echo.
CONTROL_RULE = [pytest.param(end, said, id=name) for name, end, said in (
    ("an-e-acute", A_LETTER_PAST_ASCII, TAKEN),
    ("a-no-break-space", "a" + chr(0xA0) + "b", TAKEN),
    ("a-persian-word-and-u+200c",
     "".join(map(chr, (0x0646, 0x0627, 0x0645, 0x0647, 0x200C, 0x0647,
                       0x0627))), TAKEN),
    ("an-emoji-sequence-and-u+200d",
     chr(0x1F469) + chr(0x200D) + chr(0x1F4BB), TAKEN),
    ("u+2026", "a" + chr(0x2026) + "b", TAKEN),
    ("u+ff21", "a" + chr(0xFF21) + "b", TAKEN),
    ("a-subdivision-flag",
     "".join(map(chr, (0x1F3F4, 0xE0067, 0xE0062, 0xE0065, 0xE006E, 0xE0067,
                       0xE007F))), TAKEN),
    ("a-lone-0x9b-byte", "a" + chr(0xDC9B) + "b", TAKEN),
    ("a-lone-0xe9-byte", "caf" + NOT_UTF8, TAKEN),
    ("an-overlong-escape", "a" + chr(0xDCC0) + chr(0xDC9B) + "b", TAKEN),
    ("an-escape", "a" + ESCAPE + "[31mforged", CONTROL),
    ("a-newline", "a\nforged", CONTROL),
    ("a-carriage-return", "a\rforged", CONTROL),
    ("a-tab", "a\tforged", CONTROL),
    ("a-delete", "a" + DELETE + "forged", CONTROL),
    ("u+0080", "a" + chr(0x80) + "forged", CONTROL),
    ("u+0085", "a" + chr(0x85) + "forged", CONTROL),
    ("u+009b", "a" + C1_CSI + "31mforged", CONTROL),
    ("u+009f", "a" + chr(0x9F) + "forged", CONTROL),
    ("a-newline-at-the-end", "forged\n", CONTROL),
    ("a-lone-0xe9-byte-then-u+009b",
     "caf" + NOT_UTF8 + C1_CSI + "31mforged", CONTROL),
    ("a-tab-then-u+202e", "a\t" + RLO + "forged", CONTROL),
    ("u+202e", "a" + RLO + "forged", "U+202E"),
    ("u+200b", "a" + ZWSP + "forged", "U+200B"),
    ("u+2028", "a" + chr(0x2028) + "forged", "U+2028"),
    ("u+2029", "a" + chr(0x2029) + "forged", "U+2029"),
    ("two-at-once", "a" + RLO + "b" + ZWSP + "forged", "U+200B, U+202E"),
    ("a-lone-0xe9-byte-then-u+202e", "caf" + NOT_UTF8 + RLO + "forged",
     "U+202E"),
)]

#: The rows of `CONTROL_RULE` whose value is no UTF-8 text. A macOS file system
#: (APFS) refuses to create a directory named so, so a case that places into
#: one is not run there.
NOT_UTF8_ROWS = {"a-lone-0x9b-byte", "a-lone-0xe9-byte", "an-overlong-escape"}

TAKEN_ROWS = [row for row in CONTROL_RULE if row.values[1] == TAKEN]
REFUSED_ROWS = [row for row in CONTROL_RULE if row.values[1] != TAKEN]

#: The taken rows a directory is made for: the three that are no UTF-8 text are
#: skipped on macOS.
TAKEN_BIN_DIRS = [
    pytest.param(*row.values, id=row.id, marks=pytest.mark.skipif(
        sys.platform == "darwin" and row.id in NOT_UTF8_ROWS,
        reason="a macOS file system refuses a name that is not UTF-8"))
    for row in TAKEN_ROWS]

BIN_DIR = "OPENREPOTOOLS_BIN_DIR"
REPOSITORY = "OPENREPOTOOLS_REPO"
REF = "OPENREPOTOOLS_REF"

#: The three values, each with how a value of it starts and the words its
#: refusal opens with: the directory's is `--install`'s and names the commands
#: it would have placed, the other two are the variables'.
FORMS = [
    pytest.param(BIN_DIR, "{d}/", f"`--install` would place the "
                 f"{len(INSTALLED)} commands in a directory whose name ",
                 id="the-directory"),
    pytest.param(REPOSITORY, "acme/r", "$OPENREPOTOOLS_REPO ",
                 id="the-repository"),
    pytest.param(REF, "v1", "$OPENREPOTOOLS_REF ", id="the-ref"),
]
#: The two that `--version` prints.
PRINTED_FORMS = [form for form in FORMS if form.values[0] != BIN_DIR]


# --- running the command -----------------------------------------------------

def sandbox(tmp_path: Path) -> Path:
    """`<tmp_path>/home`, the HOME of a run, empty: whatever it holds after
    the run is what the run placed."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return home


def recording_net(tmp_path: Path, answering: Path | None = None) -> Path:
    """A `gh` and a `curl` first on `$PATH` that write down every call they
    are asked for, in `<net>/calls.log`, and refuse. With `answering`, a
    directory holding a `gh` and a `curl`, each runs that one after it has
    written the call down, so a run goes on as it would and the log still
    shows everything it asked. Returns the directory to put first on `$PATH`;
    `calls_to` reads the log."""
    net = tmp_path / "net"
    net.mkdir(exist_ok=True)
    for tool in ("gh", "curl"):
        then = ("exit 1\n" if answering is None
                else f"exec {shlex.quote(str(answering / tool))} \"$@\"\n")
        (net / tool).write_text(
            "#!/bin/sh\n"
            f"printf '%s %s\\n' {tool} \"$*\" >> "
            f"{shlex.quote(str(net / 'calls.log'))}\n" + then,
            encoding="utf-8")
        (net / tool).chmod(0o755)
    return net


def calls_to(net: Path) -> list:
    log = net / "calls.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def go(tmp_path: Path, *args: str, env: dict | None = None,
       piped: bool = False, home: Path | None = None,
       command: Path = COMMAND,
       net: Path | None = None) -> subprocess.CompletedProcess:
    """The command with `args`, in a sandbox HOME, from `tmp_path`.

    From its file, or from stdin where `piped`, which is the documented
    one-line install: there is no file beside it, so `--install` fetches.
    `net` is put first on `$PATH`. The output is read as UTF-8 with
    `surrogateescape`, so a byte that is not UTF-8 comes back as the
    surrogate a test spelled it with.
    """
    environ = command_env(home if home is not None else sandbox(tmp_path), env)
    if net is not None:
        environ["PATH"] = f"{net}{os.pathsep}{environ['PATH']}"
    argv = ["bash", "-s", "--", *args] if piped else ["bash", str(command), *args]
    return subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8",
        errors="surrogateescape", check=False,
        input=COMMAND.read_text(encoding="utf-8") if piped else "",
        cwd=str(tmp_path), env=environ)


def assert_refused_saying(result: subprocess.CompletedProcess, said: str,
                          typed: str | None = None) -> str:
    """`result` is a refusal, exit 2, saying `said` on stderr, and nothing on
    stdout. No control character, no character of `MISDRAWN` and no `forged`
    tail reaches either stream, and neither does the value itself, which a
    refusal never repeats: `typed` is looked for whole. The refusal, its
    whitespace collapsed, is returned."""
    assert result.returncode == 2, result.stdout + result.stderr
    said_in_full = " ".join(result.stderr.split())
    assert said in said_in_full, said_in_full
    for stream in (result.stdout, result.stderr):
        assert "forged" not in stream, stream
        for bad in (ESCAPE, DELETE, C1_CSI, "\r", "\t"):
            assert bad not in stream, (hex(ord(bad)), stream)
        for code in MISDRAWN:
            assert chr(code) not in stream, (f"U+{code:04X}", stream)
        if typed:
            assert typed not in stream, stream
    assert result.stdout == ""
    return said_in_full


def nothing_placed(home: Path) -> bool:
    """The sandbox HOME is as empty as it began: nothing was placed or made."""
    return sorted(home.rglob("*")) == []


def installed_copy(tmp_path: Path) -> Path:
    """`openRepoTools` as `--install` leaves it in a bin directory: the one
    file, with no `contracts/` or `upstream/` beside it. A run from it has no
    pin to read, so what it needs of the source it asks the source for."""
    where = tmp_path / "installed"
    where.mkdir(exist_ok=True)
    shutil.copy2(COMMAND, where / "openRepoTools")
    return where / "openRepoTools"


def refusal_words(opening: str, said: str) -> str:
    """The whole opening of a refusal: the value's own words, then what it
    holds, by the kind: a control character, or the code points named."""
    return opening + (HOLDS_A_CONTROL_CHARACTER if said == CONTROL
                      else drawn_as_another(said))


# --- the directory: what no line about `$PATH` can name ---------------------

#: Directories no `export PATH=` line can name, and what their refusal says:
#: a `:` is what splits a `$PATH`, whatever the quoting, and a Windows spelling
#: holds one (nothing here spells one the way bash does, and on Windows the way
#: in is WSL2). A control character or a misdrawn one is refused FIRST, so a
#: directory holding both is refused for that, in its words: they are the
#: checks that never echo.
UNNAMEABLE_BIN_DIRS = [
    pytest.param("{d}/a:b/bin", HOLDS_A_COLON, id="a-colon"),
    pytest.param("{d}/bin:{d}/other", HOLDS_A_COLON, id="two-directories"),
    pytest.param("D:tools", HOLDS_A_COLON, id="a-drive-relative-name"),
    pytest.param("D:\\tools\\bin", HOLDS_A_COLON, id="a-windows-spelling"),
    pytest.param("{d}/a:b" + ESCAPE + "[31mforged/bin",
                 HOLDS_A_CONTROL_CHARACTER, id="a-colon-and-an-escape"),
    pytest.param("{d}/a:b" + RLO + "forged/bin",
                 drawn_as_another("U+202E"), id="a-colon-and-u+202e"),
    pytest.param("D:\\tools" + RLO + "forged\\bin",
                 drawn_as_another("U+202E"),
                 id="a-windows-spelling-and-u+202e"),
]


@pytest.mark.parametrize("value, said", UNNAMEABLE_BIN_DIRS)
def test_a_bin_dir_no_path_line_can_name_is_refused_before_it_places_anything(
        tmp_path, value, said):
    """A `:` splits a `$PATH`, so the PATH note could not name such a
    directory: `--install` refuses it with exit 2, before a file is placed or
    a directory made, naming the kind of character it found and saying what to
    set instead. It never repeats the directory, not even for a colon (the
    issue's line, and a stricter one than openRepoShape's, which names it)."""
    typed = value.replace("{d}", str(sandbox(tmp_path)))
    result = go(tmp_path, "--install", env={BIN_DIR: typed})
    said_in_full = assert_refused_saying(result, said, typed)
    assert "NOTHING was installed and nothing already installed was replaced" \
        in said_in_full, said_in_full
    assert "Set $OPENREPOTOOLS_BIN_DIR to a directory without one" \
        in said_in_full, said_in_full
    assert nothing_placed(sandbox(tmp_path))


#: A `$HOME` is the directory when `$OPENREPOTOOLS_BIN_DIR` is not set
#: (`~/.local/bin`), so a home holding one is refused the same way.
BAD_HOMES = [
    pytest.param("a:b", HOLDS_A_COLON, id="a-colon"),
    pytest.param("a\nforged", HOLDS_A_CONTROL_CHARACTER, id="a-newline"),
    pytest.param("a" + RLO + "forged", drawn_as_another("U+202E"),
                 id="u+202e"),
]


@pytest.mark.parametrize("name, said", BAD_HOMES)
def test_a_home_no_path_line_can_name_is_refused_when_no_bin_dir_is_set(
        tmp_path, name, said):
    """The directory is `${OPENREPOTOOLS_BIN_DIR:-$HOME/.local/bin}`, as
    `install_commands` computes it: a `$HOME` holding a colon, a newline or
    U+202E makes the default one no line can name, and is refused before
    anything is placed in it."""
    home = tmp_path / name
    home.mkdir()
    result = go(tmp_path, "--install", home=home)
    assert_refused_saying(result, said, str(home))
    assert nothing_placed(home)


# --- the one rule, asked of all three values ---------------------------------

@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("variable, start, opening", FORMS)
@pytest.mark.parametrize("end, said", REFUSED_ROWS)
def test_the_rule_refuses_every_row_it_refuses_for_all_three_values(
        tmp_path, variable, start, opening, end, said, locale):
    """The directory by `--install`, the repository and the ref by
    `--version`, which prints both: each answers every refused row of
    `CONTROL_RULE` the same, in both locales, with the one refusal for the
    value, never an echo of it, and nothing placed."""
    typed = start.replace("{d}", str(sandbox(tmp_path))) + end
    args = ("--install",) if variable == BIN_DIR else ("--version",)
    result = go(tmp_path, *args, env={variable: typed, "LC_ALL": locale})
    assert_refused_saying(result, refusal_words(opening, said), typed)
    assert nothing_placed(sandbox(tmp_path))


@pytest.mark.parametrize("variable, start, opening", FORMS)
@pytest.mark.parametrize("code", MISDRAWN, ids=lambda code: f"u+{code:04x}")
def test_each_misdrawn_character_is_refused_by_its_code_point(
        tmp_path, variable, start, opening, code):
    """Every one of `MISDRAWN` in each of the three values, refused in words
    that name it by its code point, because nobody can see it, and say nothing
    else of the value (openRepoShape #837). Its bytes are looked for as bytes,
    so the locale changes nothing."""
    typed = start.replace("{d}", str(sandbox(tmp_path))) \
        + "a" + chr(code) + "forged"
    args = ("--install",) if variable == BIN_DIR else ("--version",)
    result = go(tmp_path, *args, env={variable: typed})
    assert_refused_saying(
        result, refusal_words(opening, f"U+{code:04X}"), typed)
    assert nothing_placed(sandbox(tmp_path))


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("variable, start, opening", PRINTED_FORMS)
@pytest.mark.parametrize("end, said", TAKEN_ROWS)
def test_version_prints_every_value_the_rule_takes_as_typed(
        tmp_path, variable, start, opening, end, said, locale):
    """The rule refuses a character no line can print as it reads, and nothing
    else: `--version` prints the rest as typed, exit 0, under `C` and
    `C.UTF-8`, byte for byte what it printed before. That includes a letter
    past ASCII, which `[![:print:]]` refused under `C` (openRepoShape #940),
    and the bytes that are not UTF-8, which are the known limit."""
    value = start + end
    result = go(tmp_path, "--version", env={variable: value, "LC_ALL": locale})
    repository, ref = "opensoft/openRepoTools", "main"
    if variable == REPOSITORY:
        repository = value
    else:
        ref = value
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == f"openRepoTools ({repository} @ {ref})\n"
    assert result.stderr == ""


#: A `:` in the repository and in the ref. The rule refuses one in the DIRECTORY
#: alone, because only that is a `$PATH` for a `:` to split
#: (`UNNAMEABLE_BIN_DIRS`): neither of these two is, so each is a sound value.
COLON_VALUES = [
    pytest.param(REPOSITORY, "acme/r:x", id="the-repository"),
    pytest.param(REF, "refs/tags/a:b", id="the-ref"),
]


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("variable, value", COLON_VALUES)
def test_a_colon_is_the_directorys_alone_a_repository_or_ref_may_hold_one(
        tmp_path, variable, value, locale):
    """The review's SHOULD-1: nothing pinned that a `:` is refused ONLY for the
    directory, so a rule that refused it for the repository and the ref as well
    (`refuse_bad_values` is the one function all three runs that ask the two
    values share) would have passed every other test. `--version` prints a
    repository or a ref holding one as typed, exit 0, under `C` and `C.UTF-8`;
    `test_wip_init_from_an_installed_copy_goes_on_and_sends_a_sound_value_as_typed`
    holds the same for the request `wip init` sends, and the `a-colon` row of
    `test_wip_init_refuses_a_bad_directory_*` holds the other half: a `:` in
    the directory is refused by `wip init` as by `--install`."""
    result = go(tmp_path, "--version", env={variable: value, "LC_ALL": locale})
    repository, ref = ((value, "main") if variable == REPOSITORY
                       else ("opensoft/openRepoTools", value))
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == f"openRepoTools ({repository} @ {ref})\n"
    assert result.stderr == ""


@NEEDS_JQ
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("end, said", TAKEN_BIN_DIRS)
def test_a_bin_dir_the_rule_takes_is_placed(tmp_path, end, said, locale):
    """The rule is `[[:cntrl:]]` and not `[![:print:]]`: under `LC_ALL=C` the
    two bytes of an e with an acute accent are not printable, so the second
    would refuse a directory called `café` for a fault it has not got
    (openRepoShape #760 and #940). It is placed in either locale, and so is
    everything else the table takes, a lone `0x9B` byte included: that one is
    the known limit, held here so that nobody changes it by accident."""
    typed = f"{sandbox(tmp_path)}/{end}"
    result = go(tmp_path, "--install", env={BIN_DIR: typed, "LC_ALL": locale})
    assert result.returncode == 0, result.stdout + result.stderr
    assert (Path(typed) / "openRepoTools").read_bytes() == COMMAND.read_bytes()
    assert "REFUSED" not in result.stderr


# --- a bad value stops the run before it asks anyone anything ----------------

#: The runs that name or fetch with the values, each as its arguments and
#: whether the command arrives on stdin: `--install` from its file, which
#: copies what is beside it; `--install` from stdin, the documented install
#: line, which fetches every file; and `--version`, which prints both. `wip
#: init` is another, and not in this table: from an installed copy its step 7
#: sends the repository and the ref as typed, and the `link-estates` it runs
#: names the directory as typed, so it is asked all three before it does
#: anything, by every route and with `--dry-run`, which is what its own cases
#: vary (`test_wip_init_refuses_*`, below).
RUNS = {
    "install": (("--install",), False),
    "install-from-stdin": (("--install",), True),
    "version": (("--version",), False),
}

#: A bad value for each of the three, a different character each, as the
#: variable, the value and what its refusal says.
BAD_VALUES = [
    (BIN_DIR, "{d}/a" + ESCAPE + "[31mforged/bin", HOLDS_A_CONTROL_CHARACTER),
    (REPOSITORY, "acme/r" + RLO + "forged", drawn_as_another("U+202E")),
    (REF, "v1\nforged", HOLDS_A_CONTROL_CHARACTER),
]

#: Each of them with each run that reads it: the directory matters only to
#: `--install`.
BAD_VALUE_RUNS = [
    pytest.param(variable, value, said, run_name,
                 id=f"{variable.removeprefix('OPENREPOTOOLS_').lower()}-"
                    f"{run_name}")
    for variable, value, said in BAD_VALUES for run_name in RUNS
    if variable != BIN_DIR or RUNS[run_name][0] == ("--install",)]


@pytest.mark.parametrize("variable, value, said, run_name", BAD_VALUE_RUNS)
def test_a_bad_value_is_refused_before_any_request_and_before_anything_is_placed(
        tmp_path, variable, value, said, run_name):
    """Exit 2, that one refusal and nothing else, no call to `gh` or `curl`,
    nothing placed or made, and no part of the value in either stream. The
    other two values are sound: a good directory, so that a placement would
    show in the sandbox HOME, and the defaults."""
    args, piped = RUNS[run_name]
    home = sandbox(tmp_path)
    typed = value.replace("{d}", str(home))
    net = recording_net(tmp_path)
    env = {BIN_DIR: str(home / "bin"), variable: typed}
    result = go(tmp_path, *args, env=env, piped=piped, net=net)
    assert calls_to(net) == []
    assert_refused_saying(result, said, typed)
    assert nothing_placed(home)


def test_the_run_a_bad_value_stops_does_ask_the_network_when_every_value_is_sound(
        tmp_path):
    """THE CONTROL FOR THE TEST ABOVE: the same run with nothing wrong with
    any value does call `gh`, so an empty log up there means the check came
    first and not that this run never asks."""
    args, piped = RUNS["install-from-stdin"]
    home = sandbox(tmp_path)
    net = recording_net(tmp_path)
    go(tmp_path, *args, env={BIN_DIR: str(home / "bin")}, piped=piped, net=net)
    assert calls_to(net), "`--install` from stdin asked the network nothing"


#: THE ROUTES A `wip init` IS RUN BY, each as the script it runs. From an
#: INSTALLED COPY, with no `contracts/openreposhape-pin.yaml` beside it, step 7
#: asks the source for the standard's pin and SENDS `$OPENREPOTOOLS_REPO` and
#: `$OPENREPOTOOLS_REF` as typed: the run that reached the fetch (the review of
#: #241, MUST-1). The checkout's file has the pin beside it and reads it, and a
#: package's payload carries it too, so neither sends them, and both are held
#: to the same refusals (the directory's too), because they are asked before
#: the route matters.
WIP_ROUTES = {
    "an-installed-copy": installed_copy,
    "the-checkout": lambda tmp_path: COMMAND,
    "a-package": lambda tmp_path: installed_package(tmp_path),
}

#: A bad repository and a bad ref, the kinds of character the rule refuses in
#: both (a control character, a misdrawn one), as the variable, the value and
#: what the refusal says of it. The third is the forged ref the review sent.
WIP_BAD_VALUES = [
    pytest.param(REPOSITORY, "acme/r" + ESCAPE + "[31mforged",
                 HOLDS_A_CONTROL_CHARACTER, id="a-repository-with-an-escape"),
    pytest.param(REPOSITORY, "acme/r" + RLO + "forged",
                 drawn_as_another("U+202E"), id="a-repository-with-u+202e"),
    pytest.param(REF, "v1\nforged" + ESCAPE + "[31m",
                 HOLDS_A_CONTROL_CHARACTER,
                 id="a-ref-with-a-newline-and-an-escape"),
    pytest.param(REF, "v1" + ZWSP + "forged", drawn_as_another("U+200B"),
                 id="a-ref-with-u+200b"),
]


def run_wip_init(tmp_path: Path, command: Path, *flags: str, env: dict,
                 home: Path | None = None
                 ) -> tuple[subprocess.CompletedProcess, Path]:
    """`wip init` with `flags`, run from `command` in a sandbox HOME (`home`,
    where a test names another) against the repo's own fake `gh`
    (`test_wip_init_command.fake_gh`: it answers `repo view`, `repo create`,
    `repo clone` and the template files, with real bare repositories under
    `<tmp_path>/github`), behind a `gh` and a `curl` that write down every
    call first. Returns the result and the directory `calls_to` reads."""
    answering = fake_gh(tmp_path)
    net = recording_net(tmp_path, answering=tmp_path / "fake-path")
    return go(tmp_path, "wip", "init", *flags, command=command, net=net,
              home=home, env={**answering, **env}), net


@pytest.mark.parametrize("flags", [(), ("--dry-run",)],
                         ids=["a-run", "a-dry-run"])
@pytest.mark.parametrize("route", WIP_ROUTES)
@pytest.mark.parametrize("variable, value, said", WIP_BAD_VALUES)
def test_wip_init_refuses_a_bad_repository_or_ref_before_it_asks_or_makes_anything(
        tmp_path, variable, value, said, route, flags):
    """`wip init` refuses an unsafe `$OPENREPOTOOLS_REPO` and, separately, an
    unsafe `$OPENREPOTOOLS_REF`: exit 2, in the words every refusal of the two
    uses (the variable named, never the value), before it has asked the
    network anything or made anything.

    FROM AN INSTALLED COPY THIS IS THE RUN THAT REACHED THE FETCH: with no pin
    beside the script, step 7 sent both values as typed in a `gh api` call and
    a raw URL, after steps 5 and 6 had made the repository and cloned it (the
    review of #241, MUST-1). So the log of calls is empty, the sandbox HOME is
    as empty as it began, and the fake server holds no repository. The
    checkout and the package are held to it too, and so is `--dry-run`: it
    reads neither value, but it is the rehearsal of a run that refuses.

    (The test this replaced ran `--dry-run` from the checkout, where
    `wip_shape_ref` reads the pin beside the script and the run stops before
    step 7, so it could not see the send, and it asserted the opposite.)"""
    command = WIP_ROUTES[route](tmp_path)
    result, net = run_wip_init(tmp_path, command, *flags, env={variable: value})
    assert calls_to(net) == [], "`wip init` asked the network before it refused"
    said_in_full = assert_refused_saying(result, f"${variable} {said}", value)
    assert "Nothing was fetched, installed or replaced" in said_in_full, \
        said_in_full
    assert nothing_placed(sandbox(tmp_path))
    assert sorted((tmp_path / "github").rglob("*")) == [], \
        "`wip init` made a repository"


#: What `wip init` says before it asks the two values, each as its arguments
#: and a phrase of the refusal: the verb, an option it lacks, an option with no
#: value, and a login no `<user>-wip` name can be made of.
WIP_OWN_REFUSALS = [
    pytest.param(("wip",), "`wip` takes one verb and it is `init`",
                 id="no-verb"),
    pytest.param(("wip", "bogus"),
                 "`wip bogus` is not a thing this command does",
                 id="another-verb"),
    pytest.param(("wip", "init", "--bogus"),
                 "`wip init` takes --org, --login, --team and --dry-run",
                 id="an-option-it-lacks"),
    pytest.param(("wip", "init", "--org"), "--org needs a value",
                 id="an-option-with-no-value"),
    pytest.param(("wip", "init", "--login", "No_Good"),
                 "cannot form a compliant `<user>-wip` name",
                 id="a-login-that-cannot-form-a-name"),
]


@pytest.mark.parametrize("args, said", WIP_OWN_REFUSALS)
def test_wip_init_gives_its_own_refusals_before_it_asks_the_three_values(
        tmp_path, args, said):
    """The values are asked after the arguments and `--login`, so each of those
    refusals is the one it always was, though the repository, the ref and the
    directory are bad too: the person fixes what they typed first, and a bad
    value cannot change what a mistyped option says."""
    net = recording_net(tmp_path)
    result = go(tmp_path, *args, net=net, env={
        REPOSITORY: "acme/r" + RLO + "forged",
        REF: "v1" + ESCAPE + "[31mforged",
        BIN_DIR: str(sandbox(tmp_path) / "a:b") + "\nforged"})
    said_in_full = assert_refused_saying(result, said)
    assert "$OPENREPOTOOLS_REPO holds" not in said_in_full, said_in_full
    assert "$OPENREPOTOOLS_REF holds" not in said_in_full, said_in_full
    assert "link-estates" not in said_in_full, said_in_full
    assert calls_to(net) == []
    assert nothing_placed(sandbox(tmp_path))


#: Sound values, and the two that hold a colon, which neither is a `$PATH` to
#: split: the rule refuses a `:` in the directory alone.
WIP_SOUND_VALUES = [
    pytest.param(REPOSITORY, "acme/r", id="a-repository"),
    pytest.param(REF, "v1.2.3", id="a-ref"),
    pytest.param(REPOSITORY, "acme/r:x", id="a-repository-with-a-colon"),
    pytest.param(REF, "refs/tags/a:b", id="a-ref-with-a-colon"),
]


@pytest.mark.parametrize("variable, value", WIP_SOUND_VALUES)
def test_wip_init_from_an_installed_copy_goes_on_and_sends_a_sound_value_as_typed(
        tmp_path, variable, value):
    """THE CONTROL FOR THE TEST ABOVE: the same run from the same installed
    copy, with a sound value in place of the bad one, is not refused and does
    send it, in the `gh api` call that asks the source for the standard's pin,
    so the empty log up there means the refusal came first and not that this
    run never asks. A colon is a sound value in a repository or a ref."""
    result, net = run_wip_init(tmp_path, installed_copy(tmp_path),
                               env={variable: value})
    assert f"${variable} holds" not in " ".join(result.stderr.split())
    repository, ref = ((value, "main") if variable == REPOSITORY
                       else ("opensoft/openRepoTools", value))
    asked = f"repos/{repository}/contents/contracts/code-pin.yaml?ref={ref}"
    assert any(asked in call for call in calls_to(net)), calls_to(net)


#: A bad directory, the kinds of character the rule refuses in it: a control
#: character (an escape, and a newline, which breaks a line in two), a misdrawn
#: one and the `:` that only the directory refuses (a `$PATH` is what it
#: splits), each as the directory and what its refusal says of it.
WIP_BAD_DIRS = [
    pytest.param("{d}/a" + ESCAPE + "[31mforged/bin",
                 HOLDS_A_CONTROL_CHARACTER, id="an-escape"),
    pytest.param("{d}/a\nforged/bin", HOLDS_A_CONTROL_CHARACTER,
                 id="a-newline"),
    pytest.param("{d}/a" + RLO + "forged/bin", drawn_as_another("U+202E"),
                 id="u+202e"),
    pytest.param("{d}/a:b/bin", HOLDS_A_COLON, id="a-colon"),
]

#: How `wip init`'s refusal of the directory opens. It is in `wip init`'s own
#: words and not `--install`'s: `wip init` places nothing, and the lines that
#: would name the directory are the `link-estates` it runs.
WIP_REFUSES_THE_DIRECTORY = ("`wip init` may run `link-estates` from a "
                             "directory whose name ")


@pytest.mark.parametrize("flags", [(), ("--dry-run",)],
                         ids=["a-run", "a-dry-run"])
@pytest.mark.parametrize("route", WIP_ROUTES)
@pytest.mark.parametrize("value, said", WIP_BAD_DIRS)
def test_wip_init_refuses_a_bad_directory_before_it_asks_or_makes_anything(
        tmp_path, value, said, route, flags):
    """`wip init` refuses an unsafe `$OPENREPOTOOLS_BIN_DIR` (the operator's
    word, after the review): exit 2, the variable named and never the
    directory, before it has asked the network anything or made anything.

    `wip init`'s own lines never name the directory (`wip_run_link_estates`
    only runs `<dir>/link-estates`), but the `link-estates` it runs does, as
    typed, in its `Error`, `STALE` and `NOTE` lines, and a `:` splits the
    `$PATH` that `NOTE` is about. So the rule is `--install`'s whole, the colon
    included, and the refusal is in `wip init`'s own words: it never says
    `--install`. The sandbox HOME is as empty as it began and the fake server
    holds no repository, from an installed copy, the checkout and a package,
    with `--dry-run` as without."""
    command = WIP_ROUTES[route](tmp_path)
    typed = value.replace("{d}", str(sandbox(tmp_path)))
    result, net = run_wip_init(tmp_path, command, *flags, env={BIN_DIR: typed})
    assert calls_to(net) == [], "`wip init` asked the network before it refused"
    said_in_full = assert_refused_saying(
        result, WIP_REFUSES_THE_DIRECTORY + said, typed)
    assert "Set $OPENREPOTOOLS_BIN_DIR to a directory without one" \
        in said_in_full, said_in_full
    assert "Nothing was fetched, created or changed" in said_in_full, \
        said_in_full
    assert "--install" not in said_in_full, said_in_full
    assert nothing_placed(sandbox(tmp_path))
    assert sorted((tmp_path / "github").rglob("*")) == [], \
        "`wip init` made a repository"


@pytest.mark.parametrize("name, said", BAD_HOMES)
def test_wip_init_refuses_a_home_no_line_can_name_when_no_bin_dir_is_set(
        tmp_path, name, said):
    """The directory is `${OPENREPOTOOLS_BIN_DIR:-$HOME/.local/bin}`, as
    `link-estates` computes it and as `install_commands` does, so a `$HOME`
    holding a colon, a newline or U+202E makes the default one no line can name,
    and `wip init` refuses it as `--install` does, before it asks or makes
    anything."""
    home = tmp_path / name
    home.mkdir()
    result, net = run_wip_init(tmp_path, COMMAND, env={}, home=home)
    assert calls_to(net) == []
    assert_refused_saying(result, WIP_REFUSES_THE_DIRECTORY + said, str(home))
    assert nothing_placed(home)


def test_wip_init_goes_on_with_a_directory_the_rule_takes(tmp_path):
    """THE CONTROL FOR THE DIRECTORY'S REFUSAL: the same run with a directory
    the rule takes, one with a letter past ASCII in it (`café`, which
    `[![:print:]]` refused under `C`: openRepoShape #940), is not refused and
    reaches its plan, so the refusals above are the rule's and not a refusal of
    every unusual name. A `--dry-run` with the login, the team and the
    organisation given asks the network nothing, so the empty log holds here
    too."""
    net = recording_net(tmp_path)
    typed = f"{sandbox(tmp_path)}/{A_LETTER_PAST_ASCII}/bin"
    result = go(tmp_path, "wip", "init", "--dry-run", "--login", "brettheap",
                "--team", "platform", "--org", "opensoft", net=net,
                env={BIN_DIR: typed})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--dry-run, so nothing below was done:" in result.stdout
    assert "REFUSED" not in result.stderr
    assert calls_to(net) == []


def test_wip_init_asks_the_repository_then_the_ref_then_the_directory(tmp_path):
    """The three bad at once: one refusal, in the order `--install` asks them
    in (the repository, the ref, the directory), and no value echoed."""
    net = recording_net(tmp_path)
    all_three = {REPOSITORY: "acme/r" + RLO + "forged",
                 REF: "v1" + ESCAPE + "forged",
                 BIN_DIR: str(sandbox(tmp_path) / "a:b")}
    first = go(tmp_path, "wip", "init", "--dry-run", env=all_three, net=net)
    assert_refused_saying(first, "$OPENREPOTOOLS_REPO "
                          + drawn_as_another("U+202E"))
    del all_three[REPOSITORY]
    second = go(tmp_path, "wip", "init", "--dry-run", env=all_three, net=net)
    assert_refused_saying(second, "$OPENREPOTOOLS_REF "
                          + HOLDS_A_CONTROL_CHARACTER)
    del all_three[REF]
    third = go(tmp_path, "wip", "init", "--dry-run", env=all_three, net=net)
    assert_refused_saying(third, WIP_REFUSES_THE_DIRECTORY + HOLDS_A_COLON)
    assert calls_to(net) == []


def test_the_repository_is_refused_before_the_ref_and_both_before_the_directory(
        tmp_path):
    """Two values bad at once: one refusal, in the order the rule is asked
    (the repository, the ref, the directory), and neither value is echoed."""
    home = sandbox(tmp_path)
    both = {REPOSITORY: "acme/r" + RLO + "forged",
            REF: "v1" + ESCAPE + "forged", BIN_DIR: str(home / "a:b")}
    first = go(tmp_path, "--install", env=both)
    assert_refused_saying(first, "$OPENREPOTOOLS_REPO "
                          + drawn_as_another("U+202E"))
    del both[REPOSITORY]
    second = go(tmp_path, "--install", env=both)
    assert_refused_saying(second, "$OPENREPOTOOLS_REF "
                          + HOLDS_A_CONTROL_CHARACTER)
    del both[REF]
    third = go(tmp_path, "--install", env=both)
    assert_refused_saying(third, HOLDS_A_COLON)


def test_help_and_the_bare_usage_answer_past_all_three_values(tmp_path):
    """`--help` and the bare usage name the variables and never their values,
    so they answer before the values are asked (openRepoShape #866)."""
    home = sandbox(tmp_path)
    bad = {BIN_DIR: str(home / "a:b") + "\nforged", REPOSITORY: "acme/r" + RLO
           + "forged", REF: "v1" + ESCAPE + "[31mforged"}
    for args in (("--help",), ()):
        result = go(tmp_path, *args, env=bad)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "openRepoTools --install" in result.stdout
        assert "forged" not in result.stdout + result.stderr
        assert "REFUSED" not in result.stderr


def test_a_sentinel_repository_and_ref_are_still_sound_values(tmp_path):
    """workBenches and the `package` job run `--install` with a repository and a
    ref that name nothing, to make any fetch fail: the rule is about
    characters, never about shape, so they pass it."""
    result = go(tmp_path, "--version", env={
        REPOSITORY: "offline.invalid/sentinel",
        REF: "pinned-by-workBenches-no-fetch"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ("openRepoTools (offline.invalid/sentinel @ "
                             "pinned-by-workBenches-no-fetch)\n")


# --- the functions, alone -----------------------------------------------------

BASH = shutil.which("bash") or "bash"


def misdrawn_functions() -> str:
    """`MISDRAWN_CHARACTERS` and `misdrawn_characters`, as the script carries
    them."""
    text = COMMAND.read_text(encoding="utf-8")
    [listed] = re.findall(r"^MISDRAWN_CHARACTERS=\(.*?\)\n", text, re.M)
    return listed + installer_function("misdrawn_characters")


#: Every code point whose UTF-8 starts with the bytes one of `MISDRAWN` starts
#: with: U+0080 to U+00BF (`0xC2`), U+0600 to U+063F (`0xD8`), U+2000 to
#: U+20FF (`0xE2 0x80` to `0xE2 0x83`), U+FE00 to U+FFFF (`0xEF 0xB8` to
#: `0xEF 0xBF`), U+1D100 to U+1D1FF (`0xF0 0x9D 0x84` to `0xF0 0x9D 0x87`) and
#: U+E0000 to U+E007F (`0xF3 0xA0 0x80` and `0xF3 0xA0 0x81`); and a sample of
#: the other planes past U+FFFF: their first and last code points, an emoji, a
#: CJK ideograph, the variation selectors past U+FFFF, and the format
#: characters a script needs, which stay allowed (the Kaithi number signs, the
#: Egyptian hieroglyph and the shorthand format controls).
SHARING_ITS_BYTES = (*range(0x80, 0xC0), *range(0x600, 0x640),
                     *range(0x2000, 0x2100), *range(0xFE00, 0x10000),
                     *range(0x1D100, 0x1D200), *range(0xE0000, 0xE0080),
                     0x10000, 0x110BD, 0x110CD, *range(0x13430, 0x13440),
                     *range(0x1BCA0, 0x1BCA4), 0x1F600, 0x20000, 0xE0100,
                     0xE01EF, 0xFFFFD, 0x10FFFF)


def test_misdrawn_characters_names_its_own_and_nothing_else(tmp_path):
    """The function alone, lifted out of the script and run under `LC_ALL=C`,
    as the check runs it, over one directory name for each code point that
    starts with the bytes one it refuses starts with: it names exactly the code
    points of `MISDRAWN`, each as `U+XXXX`, and nothing for the rest, so a name
    that merely holds a byte such as `0xE2`, `0xEF` or `0xF3` is never refused,
    and the four-byte form is built right. The names travel on stdin, as bytes,
    one NUL-ended each."""
    script = tmp_path / "misdrawn.sh"
    script.write_bytes(("LC_ALL=C\n" + misdrawn_functions()
                        + 'while IFS= read -r -d "" value; do\n'
                        '\tmisdrawn_characters "$value"\n'
                        "\tprintf '\\n'\n"
                        "done\n").encode("utf-8"))
    ran = subprocess.run(
        [BASH, str(script)], capture_output=True, check=False,
        input=b"".join(f"/a{chr(code)}b".encode("utf-8") + b"\0"
                       for code in SHARING_ITS_BYTES),
        env=command_env())
    assert ran.returncode == 0, ran.stderr.decode("utf-8", "replace")
    named = ran.stdout.decode("ascii").split("\n")[:-1]
    assert dict(zip(SHARING_ITS_BYTES, named)) == {
        code: f"U+{code:04X}" if code in MISDRAWN else ""
        for code in SHARING_ITS_BYTES}


def test_the_scripts_list_is_the_one_written_out_here():
    """`MISDRAWN_CHARACTERS` expands to exactly `MISDRAWN`: a character added
    to or taken from one list and not the other fails here, by name."""
    [listed] = re.findall(r"^MISDRAWN_CHARACTERS=\((.*?)\)\n",
                          COMMAND.read_text(encoding="utf-8"), re.M)
    expanded = []
    for entry in listed.split():
        first, _, last = entry.partition("-")
        expanded += range(int(first, 16), int(last or first, 16) + 1)
    assert tuple(expanded) == MISDRAWN


# --- the locale's reading of a directory (openRepoShape #858 and #867) ------

#: The rows of `CONTROL_RULE` that a multibyte locale reads as text are the ones
#: the bytes refuse and the locale does not, so `locale_reading` has the last
#: word. No GB18030, GBK or Shift_JIS locale is installed here or on CI, and
#: none can be built, so the person's locale is a marker name, `xx_XX.<charmap>`,
#: that a `locale` first on `$PATH` answers for; bash itself runs in `C` under it.
HONEST, FAILS, MISSING, EMPTY, READS_THEN_FAILS, MARKS = (
    "honest", "fails", "missing", "empty", "reads-then-fails", "marks")

#: What the `locale` stub answers `locale charmap` with, as glibc does: from the
#: first of `$LC_ALL`, `$LC_CTYPE` and `$LANG` that is set and not empty.
CHARMAP_ANSWER = (
    '[ "$1" = charmap ] || exit 2\n'
    'name=${LC_ALL:-${LC_CTYPE:-$LANG}}\n'
    'case "$name" in\n'
    'xx_XX.*) printf \'%s\\n\' "${name#xx_XX.}" ;;\n'
    "C.UTF-8) printf 'UTF-8\\n' ;;\n"
    "*) printf 'ANSI_X3.4-1968\\n' ;;\n"
    "esac\n")

NEEDS_ICONV = pytest.mark.skipif(
    shutil.which("iconv") is None,
    reason="`locale_reading` asks `iconv` how a charset reads a name")


def put_a_locale(directory: Path, kind: str = HONEST,
                 iconv: str | None = None) -> None:
    """A `locale` in `directory` that behaves as `kind` says, and an `iconv`
    beside it that behaves as `iconv` says: this machine's (None), or
    `MISSING`, or `EMPTY`, one that prints nothing and exits 0, as no working
    one does, or `READS_THEN_FAILS`, this machine's run in full and then exit
    1, or `MARKS`, one that leaves `iconv-ran` beside itself and exits 1, so
    that a run which must not ask it shows whether it did."""
    (directory / "locale").write_bytes(("#!/bin/sh\n" + {
        HONEST: CHARMAP_ANSWER, FAILS: CHARMAP_ANSWER + "exit 1\n",
        MISSING: "exit 127\n"}[kind]).encode("utf-8"))
    (directory / "locale").chmod(0o755)
    real = shutil.which("iconv")
    assert real, "this machine has no iconv, which these cases read with"
    if iconv is None:
        (directory / "iconv").symlink_to(real)
        return
    (directory / "iconv").write_bytes(("#!/bin/sh\n" + {
        MISSING: "exit 127\n", EMPTY: "cat >/dev/null\nexit 0\n",
        READS_THEN_FAILS: f'{shlex.quote(real)} "$@"\nexit 1\n',
        MARKS: f": > {shlex.quote(str(directory / 'iconv-ran'))}\nexit 1\n",
    }[iconv]).encode("utf-8"))
    (directory / "iconv").chmod(0o755)


def the_persons_locale(charmap: str) -> dict:
    """The environment of a person whose locale reads `charmap`: `LANG` the
    marker locale, and `LC_ALL` and `LC_CTYPE` empty, as unset."""
    return {"LANG": f"xx_XX.{charmap}", "LC_ALL": "", "LC_CTYPE": ""}


#: One of the 32 hanzi that GBK, GB18030 and CP936 read `0xC2 0x80` to
#: `0xC2 0x9F` as, which in UTF-8 are a C1 control's two bytes: Python hands
#: `chr(0x9B)` to a child as `0xC2 0x9B`, U+8078 in GB18030.
A_HANZI_OF_C1_BYTES = "a" + C1_CSI + "b"

#: Names a multibyte charset reads as text, each with that charset and its
#: `iconv`: the first, the issue's and the last of the 32 hanzi, so that a C1
#: range that stops one short at either end, where it decides whether to ask
#: the locale, is caught; U+00AD's two bytes, U+9885 in GBK; U+2028's three, a
#: kanji and a half-width katakana in Shift_JIS; in Shift_JIS a half-width
#: katakana (`0xC2`) before a character whose first byte is `0x81`, read as
#: U+FF82 and then U+3005 or U+FF3F, whose UTF-8 holds a `0x80` or a `0xBF`,
#: the first and the last byte that continues a character, which the count of
#: the reading's characters must not count; and a name the bytes do not
#: refuse, which is never read again: the `iconv` there would leave its mark.
PLACED_AS_THE_LOCALE_READS = [
    pytest.param("GB18030", None, "a" + chr(0x80) + "b",
                 id="gb18030-0xc2-0x80"),
    pytest.param("GB18030", None, A_HANZI_OF_C1_BYTES,
                 id="gb18030-0xc2-0x9b"),
    pytest.param("GB18030", None, "a" + chr(0x9F) + "b",
                 id="gb18030-0xc2-0x9f"),
    pytest.param("GBK", None, "a" + chr(0xAD) + "b", id="gbk-u+00ad-bytes"),
    pytest.param("SHIFT_JIS", None, "a" + chr(0x2028) + "b",
                 id="shift_jis-u+2028-bytes"),
    pytest.param("SHIFT_JIS", None, "a" + chr(0x81) + "Xb",
                 id="shift_jis-0xc2-0x81-0x58"),
    pytest.param("SHIFT_JIS", None, "a" + chr(0x81) + "Qb",
                 id="shift_jis-0xc2-0x81-0x51"),
    pytest.param("GB18030", MARKS, A_LETTER_PAST_ASCII,
                 id="no-byte-refused-never-read-again"),
]

#: Names refused under a marker locale, and what the refusal says. The
#: locale's reading is checked itself: GB18030 writes U+009B as
#: `0x81 0x30 0x83 0x37` and U+202E as `0x81 0x36 0xA7 0x31`, which are no
#: UTF-8, so a name holding either beside a hanzi the bytes refuse is refused
#: as its reading says. And the bytes decide where `locale` fails or is not
#: there; where `iconv` is not there, prints nothing, or prints the whole
#: reading and then fails, which the round trip alone would let through; where
#: GB18030 cannot read a byte (`0xFF`); under a single-byte charset, as Latin-1
#: reads U+FEFF's three bytes, each alone; with a newline at the end, which
#: `$(...)` drops from a reading; and where `locale` answers nothing, UTF-8 or
#: ASCII, under which `iconv` is never asked.
REFUSED_AS_THE_BYTES_SAY = [
    pytest.param("GB18030", HONEST, None,
                 A_HANZI_OF_C1_BYTES + "\udc81" + "0" + "\udc83" + "7",
                 HOLDS_A_CONTROL_CHARACTER, id="gb18030-reads-u+009b"),
    pytest.param("GB18030", HONEST, None,
                 A_HANZI_OF_C1_BYTES + "\udc81" + "6" + "\udca7" + "1",
                 drawn_as_another("U+202E"), id="gb18030-reads-u+202e"),
    pytest.param("GB18030", FAILS, None, A_HANZI_OF_C1_BYTES,
                 HOLDS_A_CONTROL_CHARACTER, id="a-locale-that-fails"),
    pytest.param("GB18030", MISSING, None, A_HANZI_OF_C1_BYTES,
                 HOLDS_A_CONTROL_CHARACTER, id="no-locale"),
    pytest.param("GB18030", HONEST, MISSING, A_HANZI_OF_C1_BYTES,
                 HOLDS_A_CONTROL_CHARACTER, id="no-iconv"),
    pytest.param("GB18030", HONEST, EMPTY, A_HANZI_OF_C1_BYTES,
                 HOLDS_A_CONTROL_CHARACTER, id="an-iconv-that-prints-nothing"),
    pytest.param("GB18030", HONEST, READS_THEN_FAILS, A_HANZI_OF_C1_BYTES,
                 HOLDS_A_CONTROL_CHARACTER,
                 id="an-iconv-that-reads-then-fails"),
    pytest.param("GB18030", HONEST, None, A_HANZI_OF_C1_BYTES + chr(0xDCFF),
                 HOLDS_A_CONTROL_CHARACTER, id="a-byte-gb18030-cannot-read"),
    pytest.param("ISO-8859-1", HONEST, None, "a" + chr(0xFEFF) + "b",
                 drawn_as_another("U+FEFF"), id="a-single-byte-charset"),
    pytest.param("GB18030", HONEST, None, A_HANZI_OF_C1_BYTES + "\n",
                 HOLDS_A_CONTROL_CHARACTER, id="a-newline-at-the-end"),
    *(pytest.param(answer, HONEST, MARKS, A_HANZI_OF_C1_BYTES,
                   HOLDS_A_CONTROL_CHARACTER,
                   id=f"iconv-unasked-under-{answer or 'no-answer'}")
      for answer in ("", "UTF-8", "utf8", "ANSI_X3.4-1968", "US-ASCII")),
]

#: Names refused when the person's locale is `C` or `C.UTF-8` themselves, in
#: the same words, `iconv` never asked: three of `PLACED_AS_THE_LOCALE_READS`.
REFUSED_UNDER_C_OR_UTF_8 = [
    pytest.param(A_HANZI_OF_C1_BYTES, HOLDS_A_CONTROL_CHARACTER, id="0xc2-0x9b"),
    pytest.param("a" + chr(0xAD) + "b", drawn_as_another("U+00AD"),
                 id="u+00ad"),
    pytest.param("a" + chr(0x2028) + "b", drawn_as_another("U+2028"),
                 id="u+2028"),
]


def install_under_a_locale(tmp_path: Path, name: str, environment: dict,
                           kind: str, iconv: str | None):
    """`--install` into `<home>/<name>`, with `put_a_locale`'s `locale` and
    `iconv` first on `$PATH` in `<tmp_path>/tools`, and `environment` naming
    the person's locale. Returns the result and the typed directory."""
    tools = tmp_path / "tools"
    tools.mkdir()
    put_a_locale(tools, kind, iconv)
    typed = f"{sandbox(tmp_path)}/{name}"
    result = go(tmp_path, "--install", env={
        BIN_DIR: typed, **environment,
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"})
    return result, typed


@NEEDS_JQ
@NEEDS_ICONV
@pytest.mark.parametrize("charmap, iconv, name", PLACED_AS_THE_LOCALE_READS)
def test_a_bin_dir_a_multibyte_locale_reads_as_text_is_placed(
        tmp_path, charmap, iconv, name):
    """The control check and `misdrawn_characters` look for UTF-8's bytes, and
    GB18030 reads `0xC2 0x9B` as a hanzi, not as U+009B: the directory would be
    refused as holding a control character in a locale where it holds none
    (openRepoShape #858, the first of the two cases the issue says to decide).
    Where the bytes refuse, `locale charmap` is asked under the person's own
    `LANG`, and a multibyte charset's reading of the name, through `iconv`, has
    the last word. So a name GB18030, GBK or Shift_JIS reads as text is placed;
    and a name the bytes do not refuse is placed without `iconv` being asked."""
    result, typed = install_under_a_locale(
        tmp_path, name, the_persons_locale(charmap), HONEST, iconv)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (Path(typed) / "openRepoTools").read_bytes() == COMMAND.read_bytes()
    assert not (tmp_path / "tools" / "iconv-ran").exists()


@NEEDS_ICONV
@pytest.mark.parametrize("charmap, kind, iconv, name, said",
                         REFUSED_AS_THE_BYTES_SAY)
def test_a_bin_dir_is_refused_as_its_bytes_or_its_reading_say(
        tmp_path, charmap, kind, iconv, name, said):
    """Where the locale's reading still holds a C1 control or a character drawn
    as another, it is refused as the reading says; and where the locale's
    charset is UTF-8, ASCII, single-byte or not said, where `iconv` is not
    there, prints nothing or cannot read the name, the bytes decide, as before:
    refused, exit 2, nothing placed, never echoed. A newline at the end is
    looked for in the bytes as typed, not in the reading."""
    result, typed = install_under_a_locale(
        tmp_path, name, the_persons_locale(charmap), kind, iconv)
    assert_refused_saying(result, said, typed)
    assert nothing_placed(sandbox(tmp_path))
    assert not (tmp_path / "tools" / "iconv-ran").exists()


@NEEDS_ICONV
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("name, said", REFUSED_UNDER_C_OR_UTF_8)
def test_a_bin_dir_is_refused_as_its_bytes_say_under_c_or_c_utf_8(
        tmp_path, name, said, locale):
    """The person's locale is `C` or `C.UTF-8`, as `LC_ALL` says, and `locale
    charmap` answers `ANSI_X3.4-1968` or `UTF-8`, as glibc's does: the bytes
    decide, and `iconv` is never asked."""
    result, typed = install_under_a_locale(
        tmp_path, name, {"LC_ALL": locale}, HONEST, MARKS)
    assert_refused_saying(result, said, typed)
    assert not (tmp_path / "tools" / "iconv-ran").exists()


#: The Python codec that reads as each charset of `PLACED_AS_THE_LOCALE_READS`
#: does, and Latin-1's.
CODECS = {"GB18030": "gb18030", "GBK": "gbk", "SHIFT_JIS": "shift_jis",
          "ISO-8859-1": "latin-1"}


@NEEDS_ICONV
@pytest.mark.parametrize("locale", LOCALES)
def test_locale_reading_counts_bytes_whatever_bash_itself_reads(tmp_path,
                                                                locale):
    """`locale_reading` alone, lifted out of the script, with a `locale`
    function that answers each name's charset, under bash's own `C` and
    `C.UTF-8`. In a GB18030 locale bash itself reads GB18030, and no such
    locale can be installed here, so `C.UTF-8` stands in for a multibyte locale
    of bash's own. For each name of `PLACED_AS_THE_LOCALE_READS` the bytes
    refuse, the reading is the one Python's codec gives; for Latin-1's U+FEFF
    bytes and a byte GB18030 cannot read there is none. So the count is of
    bytes in either."""
    rows = [(param.values[0], param.values[2])
            for param in PLACED_AS_THE_LOCALE_READS if param.values[1] is None]
    rows += [("ISO-8859-1", "a" + chr(0xFEFF) + "b"),
             ("GB18030", A_HANZI_OF_C1_BYTES + chr(0xDCFF))]
    script = tmp_path / "reading.sh"
    script.write_bytes((f"LC_ALL={locale}\n"
                        "locale() { printf '%s\\n' \"$CHARMAP\"; }\n"
                        + installer_function("locale_reading")
                        + 'while IFS= read -r -d "" CHARMAP && '
                        'IFS= read -r -d "" value; do\n'
                        '\tif reading="$(locale_reading "$value")"; then\n'
                        "\t\tprintf 'read %s\\0' \"$reading\"\n"
                        "\telse\n"
                        "\t\tprintf 'none\\0'\n"
                        "\tfi\n"
                        "done\n").encode("utf-8"))
    ran = subprocess.run(
        [BASH, str(script)], capture_output=True, check=False,
        input=b"".join(charmap.encode("ascii") + b"\0"
                       + value.encode("utf-8", "surrogateescape") + b"\0"
                       for charmap, value in rows),
        env=command_env())
    assert ran.returncode == 0, ran.stderr.decode("utf-8", "replace")
    expected = [b"read " + value.encode("utf-8", "surrogateescape").decode(
        CODECS[charmap]).encode("utf-8") for charmap, value in rows[:-2]]
    assert ran.stdout.split(b"\0")[:-1] == [*expected, b"none", b"none"]


# --- the package route -------------------------------------------------------

def installed_package(tmp_path: Path) -> Path:
    """The `openRepoTools` of a fake installed package, as pip lays one out:
    the payload's copy of this checkout's file, which the wheel carries byte
    for byte."""
    return layout.package_tree(tmp_path / "prefix") / "openRepoTools"


@pytest.mark.parametrize("variable, value, said", [
    pytest.param(*bad, id=bad[0].removeprefix("OPENREPOTOOLS_").lower())
    for bad in BAD_VALUES])
def test_a_package_refuses_the_same_values_before_it_places_anything(
        tmp_path, variable, value, said):
    """The wheel runs the same payload script, so its `--install` is held to
    the rule the checkout's is: the directory, the repository and the ref, each
    refused in the same words before anything is placed or asked."""
    command = installed_package(tmp_path)
    assert command.read_bytes() == COMMAND.read_bytes()
    home = sandbox(tmp_path)
    typed = value.replace("{d}", str(home))
    net = recording_net(tmp_path)
    result = go(tmp_path, "--install", command=command, net=net,
                env={BIN_DIR: str(home / "bin"), variable: typed})
    assert calls_to(net) == []
    assert_refused_saying(result, said, typed)
    assert nothing_placed(home)


def test_a_packages_version_names_its_stamp_whatever_the_repository_and_ref_say(
        tmp_path):
    """A package's `--version` prints neither value (it names the release it
    is, from its own stamp), so it asks neither of them anything: the values a
    checkout's `--version` refuses change no line of it, as the sound ones
    change none (`test_package_stamp.py`)."""
    command = installed_package(tmp_path)
    result = go(tmp_path, "--version", command=command, env={
        REPOSITORY: "acme/r" + RLO + "forged",
        REF: "v1" + ESCAPE + "[31mforged"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith(
        "openRepoTools 0.0.0 (an unstamped package)\n"), result.stdout
    assert "forged" not in result.stdout + result.stderr
    assert result.stderr == ""
