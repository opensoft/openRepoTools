# SPDX-License-Identifier: Apache-2.0
"""The release stamp, and what the command says about its release
(opensoft/openRepoTools#228, User Story 2).

A package's `openrepotools/_release.py` names the release it was built as.
BASH IS ITS ONE READER AT RUN TIME (design.md Decision 5): `stamp_read` reads
it by contracts/stamp.md's fixed grammar, and never sources, imports or runs
it. Hatchling reads its `VERSION` at build time with a pattern of its own, and
the two must never disagree. contracts/cli-output.md holds every line the
command prints about it. Six groups, one prefix each (plan.md, "The test
layout"):

- `test_stamp_reader_*` runs the installer's OWN `stamp_read`, cut out of the
  script with `installer_function`, on the committed stamp, on stamped ones,
  and on one fixture per row of contracts/stamp.md's refusal table. Every
  installer function it calls is cut out with it, and so is every `ORT_*` and
  `STAMP_*` constant the installer sets at the top level, so the harness is
  the installer's text and never a restatement of it;
- `test_stamp_hatch_*` runs hatch's version pattern, copied below with its
  citation, and `stamp_read` on the same files;
- `test_package_version_*` holds `--version`'s five lines, stamped and
  unstamped, from `package_tree` layouts;
- `test_package_broken_stamp_*` holds the one refusal a broken stamp gets: for
  every invocation, `--help` included, before any argument is acted on, with
  nothing placed and no version printed;
- `test_package_no_env_channel_*` sets every `OPENREPOTOOLS_PACKAGE_*`
  variable research R4 names, and requires that none of them changes a word.
  A checkout and the one-line install still print `openRepoTools (<repo> @
  <ref>)`, and a package still prints its own stamp or its own refusal;
- `test_package_parser_*` holds `--help`, no argument, `--install --version`
  and the parser's refusals, in a package whose stamp is sound, to what a
  checkout does.

EVERY PACKAGE RUN IS `bash <payload>/openRepoTools`, as the entry module's
exec runs it. `test_entry_*` in `tests/test_package.py` holds the console
script itself. A run's `gh` and `curl` are fakes that write down that they
were asked and refuse, so a package run that went further than it should
reaches no network and says so.

A REASON'S TEXT IS THE IMPLEMENTER'S, APART FROM ITS CAUSE (contracts/stamp.md,
"Refusal reasons"). So a refusal is held to its cause, `cannot be read (…)`,
`is partial: …` or `is malformed: …`; to the field, the line (`line N`) or the
docstring its row of the table names; to one line; and, across the rows, to
being distinct. The words around them are free.

Nothing here reads `specs/`: that tree goes to the spec leg at the triad
cutover, and this module goes to the code leg.
"""

from __future__ import annotations

import functools
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

import package_layout as layout
from conftest import WINDOWS_SKIP
from test_install_by_rename import installer_function
from test_openrepotools_command import COMMAND, NOT_ROOT, command_env

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="openRepoTools is a bash script"),
              WINDOWS_SKIP]

# --- the exact lines (contracts/cli-output.md) ------------------------------

#: `--version` from a stamped package: five lines, two spaces meaning two.
STAMPED_VERSION = ("openRepoTools {VERSION} ({REPOSITORY} @ {COMMIT})\n"
                   "  version   {VERSION}\n"
                   "  tag       {TAG}\n"
                   "  commit    {COMMIT}\n"
                   "  digest    {DIGEST} (sorted-ls-tree-r-v1)\n")

#: `--version` from an unstamped package, as the `package` job builds one.
UNSTAMPED_VERSION = ("openRepoTools 0.0.0 (an unstamped package)\n"
                     "  version   0.0.0, unstamped: a package built from a "
                     "checkout, not a release\n"
                     "  tag       none\n"
                     "  commit    none\n"
                     "  digest    none\n")

#: `--version` from a checkout or the one-line install, unchanged.
CHECKOUT_VERSION = "openRepoTools ({repo} @ {ref})\n"

#: The broken-stamp refusal, which `die` prints after a blank line, on stderr,
#: with exit 2. `{why}` is `stamp_read`'s `STAMP_WHY`.
BROKEN_STAMP = ("REFUSED: this package's stamp (openrepotools/_release.py) "
                "{why}, so this build is broken and nothing ran. A package's "
                "stamp is a release's whole stamp or the unstamped one. "
                "Reinstall it: pipx reinstall openrepotools")
_BEFORE_WHY, _AFTER_WHY = BROKEN_STAMP.split("{why}")
BROKEN_STAMP_STDERR = re.compile("\n" + re.escape(_BEFORE_WHY)
                                 + r"(?P<why>[^\n]+)"
                                 + re.escape(_AFTER_WHY) + "\n")

#: THE THREE CAUSES a reason begins with, each in the form
#: contracts/cli-output.md gives it, so that the refusal reads as a sentence.
CAUSES = {
    "cannot be read": re.compile(r"cannot be read \([^\n]+\)"),
    "is partial:": re.compile(r"is partial: [^\n]+"),
    "is malformed:": re.compile(r"is malformed: [^\n]+"),
}

# --- the stamps -------------------------------------------------------------

#: Stamps a release build could write. The first is v1.1.0 as the code leg
#: will build it; the second a TestPyPI rehearsal from this repository.
RELEASE = {"VERSION": "1.1.0", "TAG": "v1.1.0",
           "COMMIT": "0123456789abcdef0123456789abcdef01234567",
           "DIGEST": "89abcdef01234567" * 4,
           "REPOSITORY": "opensoft/openRepoTools-code"}
PRE_RELEASE = {"VERSION": "1.1.0rc1", "TAG": "v1.1.0rc1",
               "COMMIT": "fedcba9876543210fedcba9876543210fedcba98",
               "DIGEST": "0f1e2d3c4b5a6978" * 4,
               "REPOSITORY": "opensoft/openRepoTools"}
PATCH = {"VERSION": "2.10.30", "TAG": "v2.10.30",
         "COMMIT": "a1" * 20, "DIGEST": "b2" * 32,
         "REPOSITORY": "some-org/some.repo_name"}
STAMPS = {"final": RELEASE, "pre-release": PRE_RELEASE, "patch": PATCH}

#: Research R4's variables: the names a future change might reach for to hand
#: bash a stamp. Together they make a whole stamp that passes every rule, so a
#: command that trusted any one of them would print something else.
PACKAGE_VARIABLES = {
    "OPENREPOTOOLS_PACKAGE_VERSION": "9.9.9",
    "OPENREPOTOOLS_PACKAGE_TAG": "v9.9.9",
    "OPENREPOTOOLS_PACKAGE_COMMIT": "abcdef0123456789abcdef0123456789abcdef01",
    "OPENREPOTOOLS_PACKAGE_DIGEST": "9876543210fedcba" * 4,
    "OPENREPOTOOLS_PACKAGE_REPOSITORY": "someone/elsewhere",
}

#: `<repo>` and `<ref>` when nothing names them, and a pair that does.
DEFAULT_SOURCE = {"repo": "opensoft/openRepoTools", "ref": "main"}
NAMED_SOURCE = {"repo": "someone/fork", "ref": "v1.2.3"}


def stamp(**fields: str) -> str:
    """The committed stamp's text with `fields` in place of its values."""
    return layout.stamp_text(**fields)


def release_at(version: str) -> dict:
    """RELEASE with another `VERSION`, and the `TAG` that names it."""
    return {**RELEASE, "VERSION": version, "TAG": "v" + version}


def assignment(name: str, value: str) -> str:
    return f'{name} = "{value}"'


def lines_of(text: str) -> list:
    return text.split("\n")


def text_of(lines: list) -> str:
    return "\n".join(lines)


def line_number(text: str, line: str) -> int:
    """The 1-based number of the one line of `text` that is `line`."""
    where = [i for i, held in enumerate(lines_of(text)) if held == line]
    assert len(where) == 1, (f"the fixture is wrong: {line!r} is "
                             f"{len(where)} lines of the stamp, not one")
    return where[0] + 1


def docstring_span(text: str) -> tuple:
    """The 1-based numbers of the lines that open and close the docstring."""
    lines = lines_of(text)
    opening = next(i for i, line in enumerate(lines) if line.startswith('"""'))
    closing = next(i for i in range(opening + 1, len(lines))
                   if '"""' in lines[i])
    return opening + 1, closing + 1


def replaced(text: str, line: str, new: str) -> tuple:
    """`text` with its one `line` replaced by `new`, and that line's number."""
    number = line_number(text, line)
    lines = lines_of(text)
    lines[number - 1] = new
    return text_of(lines), number


def inserted(text: str, after: int, new: str) -> tuple:
    """`text` with `new` as a line after line `after`, and its number."""
    lines = lines_of(text)
    lines.insert(after, new)
    return text_of(lines), after + 1


def appended(text: str, new: str) -> tuple:
    """`text` with `new` as its last line, before the final newline."""
    lines = lines_of(text)
    assert lines[-1] == "", "the fixture is wrong: the stamp has no final newline"
    lines.insert(len(lines) - 1, new)
    return text_of(lines), len(lines) - 1


def removed(text: str, line: str) -> str:
    lines = lines_of(text)
    del lines[line_number(text, line) - 1]
    return text_of(lines)


def write_stamp(directory: Path, text: str) -> Path:
    """`text` as `<directory>/_release.py`, byte for byte: written as bytes,
    so a carriage return in it is the file's own."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "_release.py"
    path.write_bytes(text.encode("utf-8"))
    return path


# --- the reader, cut out of the installer -----------------------------------

#: A function the installer defines over several lines, by its header line.
FUNCTION_HEADER = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\(\) \{[ \t]*(?:#[^\n]*)?$", re.MULTILINE)
#: ...and one it defines on one line, `name() { …; }`.
ONE_LINE_FUNCTION = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\(\) \{ [^\n]*; \}$", re.MULTILINE)
#: The top-level constants a reader may lean on: the installer's shared
#: character sets (`ORT_ALNUM`, `ORT_TAB`, `ORT_CR`) and anything of its own.
READER_CONSTANT = re.compile(r"^(?:ORT|STAMP)_[A-Za-z0-9_]*=[^\n]*$",
                             re.MULTILINE)
#: A `#` that begins a comment: at the start of a line, or after a blank.
COMMENT = re.compile(r"(?:^|(?<=[ \t]))#.*$")

STAMP_VARIABLES = ("STAMP_STATE", "STAMP_VERSION", "STAMP_TAG",
                   "STAMP_COMMIT", "STAMP_DIGEST", "STAMP_REPOSITORY",
                   "STAMP_WHY")

#: What the harness does once the definitions are in: one `stamp_read` of the
#: file it is given, as the installer calls a reader (`|| …`, so its status is
#: read and `set -e` does not end the harness), then its status and every
#: `STAMP_*` value, each ended by a NUL, because a reason may quote a line.
REPORT = ("status=0\n"
          'stamp_read "$1" || status=$?\n'
          "printf 'status=%s\\0' \"$status\"\n"
          + "".join(f"printf '{name}=%s\\0' \"${{{name}-}}\"\n"
                    for name in STAMP_VARIABLES))


def _calls(body: str, names) -> list:
    """The installer functions `body` names outside its comments."""
    code = "\n".join(COMMENT.sub("", line) for line in body.split("\n"))
    return [name for name in names
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
                         code)]


@functools.lru_cache(maxsize=4)
def _harness_text(installer: str) -> str:
    multi = {m.group(1) for m in FUNCTION_HEADER.finditer(installer)}
    single = {m.group(1): m.group(0) + "\n"
              for m in ONE_LINE_FUNCTION.finditer(installer)
              if m.group(1) not in multi}
    names = sorted(multi | set(single))
    wanted: list = []
    queue = ["stamp_read"]
    while queue:
        name = queue.pop(0)
        if name in wanted:
            continue
        wanted.append(name)
        text = single[name] if name in single else installer_function(name)
        body = text.split("{", 1)[1]
        queue += [called for called in _calls(body, names)
                  if called not in wanted]
    definitions = "".join(single[name] if name in single
                          else installer_function(name) for name in wanted)
    constants = "".join(line + "\n"
                        for line in READER_CONSTANT.findall(installer))
    return "set -euo pipefail\n" + constants + definitions + REPORT


def reader_harness() -> str:
    """`stamp_read` AS THE INSTALLER CARRIES IT, with what it needs.

    `installer_function` cuts it out of `openRepoTools`, and with it every
    installer function its body calls, and every one those call: whatever
    helpers `stamp_read` leans on (`is_lower_hex`, `is_slug`, or its own),
    the harness carries the installer's text of them. Then the top-level
    `ORT_*` and `STAMP_*` lines, and the `REPORT`. Read afresh at each call,
    so an edit to the installer is what the next test runs.
    """
    installer = COMMAND.read_text(encoding="utf-8")
    assert re.search(r"^stamp_read\(\) \{", installer, re.MULTILINE), (
        "openRepoTools defines no `stamp_read() {`: contracts/stamp.md's "
        "reader, the one reader of a package's stamp, is not there")
    return _harness_text(installer)


class Read(NamedTuple):
    """What one `stamp_read <file>` answered."""
    status: int
    state: str
    version: str
    tag: str
    commit: str
    digest: str
    repository: str
    why: str

    def values(self) -> dict:
        return {"VERSION": self.version, "TAG": self.tag,
                "COMMIT": self.commit, "DIGEST": self.digest,
                "REPOSITORY": self.repository}


def read_stamp(work: Path, path: Path) -> Read:
    """Run the installer's `stamp_read` on `path`, under the installer's own
    `set -euo pipefail`, and return what it answered.

    The reader is a function that sets variables and returns: it prints
    nothing, on either stream. A message from bash itself, such as a
    redirection that failed, would land in the middle of the broken-stamp
    refusal, so stderr must be empty here too.
    """
    work.mkdir(parents=True, exist_ok=True)
    harness = work / "stamp-read.sh"
    harness.write_text(reader_harness(), encoding="utf-8")
    result = subprocess.run(["bash", str(harness), str(path)],
                            capture_output=True, check=False,
                            stdin=subprocess.DEVNULL, cwd=str(work),
                            env=command_env(work / "home"))
    said = (f"exit {result.returncode}\n--- stdout\n{result.stdout!r}\n"
            f"--- stderr\n{result.stderr.decode('utf-8', 'replace')}")
    assert result.returncode == 0, (
        f"the harness around stamp_read did not finish:\n{said}")
    fields = {}
    for record in result.stdout.split(b"\0")[:-1]:
        name, _, value = record.decode("utf-8", "surrogateescape").partition("=")
        fields[name] = value
    assert set(fields) == {"status", *STAMP_VARIABLES}, (
        f"the harness reported {sorted(fields)}:\n{said}")
    assert result.stderr == b"", f"stamp_read printed on stderr:\n{said}"
    return Read(int(fields["status"]), *(fields[n] for n in STAMP_VARIABLES))


def assert_accepted(read: Read, state: str, values: dict) -> None:
    assert read.status == 0, (
        f"stamp_read refused a {state} stamp: status {read.status}, "
        f"STAMP_WHY {read.why!r}")
    assert read.state == state, f"STAMP_STATE is {read.state!r}, not {state!r}"
    assert read.values() == values, (
        f"stamp_read read {read.values()}, and the file holds {values}")


def names_word(text: str, word: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])",
                     text) is not None


def assert_refused(read: Read, cause: str, fields=(), lines=(),
                   words=()) -> None:
    """`stamp_read` returned 1, with a one-line `STAMP_WHY` that begins with
    `cause` in its contract form and names each of `fields` (case and all),
    each `line N` of `lines` and each of `words` (in any case)."""
    why = read.why
    assert read.status == 1, (
        f"stamp_read did not refuse: status {read.status}, STAMP_STATE "
        f"{read.state!r}, values {read.values()}, STAMP_WHY {why!r}")
    assert CAUSES[cause].fullmatch(why), (
        f"STAMP_WHY does not begin with {cause!r} in the form "
        f"contracts/cli-output.md gives it, on one line: {why!r}")
    for field in fields:
        assert names_word(why, field), f"STAMP_WHY does not name {field}: {why!r}"
    for number in lines:
        assert re.search(rf"\bline {number}\b", why), (
            f"STAMP_WHY does not name line {number}: {why!r}")
    for word in words:
        assert word.lower() in why.lower(), (
            f"STAMP_WHY does not name the {word}: {why!r}")


# --- test_stamp_reader_*: what it accepts -----------------------------------

def test_stamp_reader_reads_the_committed_file_as_unstamped(tmp_path):
    """THE COMMITTED FILE, BYTE FOR BYTE: the SPDX line, which rule 2 skips as
    a `#` line, the docstring, which rule 3 skips, and the five lines,
    `0.0.0` and four empty values."""
    read = read_stamp(tmp_path, layout.STAMP_SOURCE)
    assert_accepted(read, "unstamped", dict(layout.UNSTAMPED))


@pytest.mark.parametrize("which", STAMPS)
def test_stamp_reader_reads_a_stamped_file_as_its_five_values(tmp_path, which):
    """A STAMP THE RELEASE BUILD COULD WRITE: the committed file with its five
    lines replaced once each, every other byte kept. A final, a pre-release
    and a patch with more than one digit in a component."""
    path = write_stamp(tmp_path / "stamp", stamp(**STAMPS[which]))
    assert_accepted(read_stamp(tmp_path, path), "stamped", STAMPS[which])


def grammar_variant(which: str) -> str:
    """A stamped file in a shape the grammar allows and the committed file
    does not use (contracts/stamp.md, rules 2 and 3)."""
    text = stamp(**RELEASE)
    opening, closing = docstring_span(text)
    lines = lines_of(text)
    if which == "blank-lines-and-comments-everywhere":
        digest = line_number(text, assignment("DIGEST", RELEASE["DIGEST"]))
        version = line_number(text, assignment("VERSION", RELEASE["VERSION"]))
        lines[digest - 1:digest - 1] = ["# a comment between two", ""]
        lines[version - 1:version - 1] = ["", "# a comment after it", ""]
        lines[1:1] = ["", "# a comment before the docstring", ""]
        return text_of(lines)
    if which == "a-one-line-docstring":
        lines[opening - 1:closing] = ['"""The release stamp, on one line."""']
        return text_of(lines)
    if which == "a-docstring-line-that-only-begins-with-the-word":
        return inserted(text, opening, "Version numbers come only from the "
                                       "tag; this line names no value.")[0]
    raise ValueError(which)


@pytest.mark.parametrize("which", [
    "blank-lines-and-comments-everywhere", "a-one-line-docstring",
    "a-docstring-line-that-only-begins-with-the-word"])
def test_stamp_reader_reads_every_shape_the_grammar_allows(tmp_path, which):
    """RULES 2 AND 3, AS WRITTEN. A blank line or a `#` line is skipped before
    the docstring as well as after it; a docstring closes on its own line when
    a second `\"\"\"` follows the opening one; and the guard refuses a
    docstring line only where `version` or `__version__` is followed by
    optional spaces and `=`, never one that merely begins with the word."""
    path = write_stamp(tmp_path / "stamp", grammar_variant(which))
    assert_accepted(read_stamp(tmp_path, path), "stamped", RELEASE)


def test_stamp_reader_never_runs_the_file(tmp_path):
    """IT NEVER SOURCES, IMPORTS OR RUNS THE FILE (contracts/stamp.md).

    The docstring is free text, so a line of it holds a `$(…)` and a
    backtick command, each of which would make a marker file if bash ever
    ran the stamp: sourced, the docstring is one double-quoted word, and
    both substitutions expand. Read by the grammar it is an unstamped stamp,
    and no marker appears.
    """
    markers = [tmp_path / "ran-a-command-substitution",
               tmp_path / "ran-a-backtick-command"]
    text = stamp()
    opening, _ = docstring_span(text)
    text, _ = inserted(text, opening,
                       f"A command, $(touch {shlex.quote(str(markers[0]))}), and "
                       f"another, `touch {shlex.quote(str(markers[1]))}`.")
    path = write_stamp(tmp_path / "stamp", text)
    read = read_stamp(tmp_path, path)
    ran = [str(marker) for marker in markers if marker.exists()]
    assert not ran, f"stamp_read ran a line of the stamp it was reading: {ran}"
    assert_accepted(read, "unstamped", dict(layout.UNSTAMPED))


# --- test_stamp_reader_*: one fixture per row of the refusal table ----------

@pytest.mark.parametrize("how", [
    "a-directory",
    pytest.param("no-read-permission", marks=NOT_ROOT)])
def test_stamp_reader_refuses_an_unreadable_file(tmp_path, how):
    """ROW: the file is unreadable, `cannot be read (<detail>)`.

    contracts/cli-output.md's own example is `cannot be read (it is a
    directory)`: the file the reason is about is the one the refusal's line
    names around it, so what is held here is the cause and its form. A
    directory refuses for root too; a mode-000 file does not, because root
    reads whatever it likes."""
    if how == "a-directory":
        path = tmp_path / "stamp" / "_release.py"
        path.mkdir(parents=True)
        result = read_stamp(tmp_path, path)
    else:
        path = write_stamp(tmp_path / "stamp", stamp())
        os.chmod(path, 0)
        try:
            result = read_stamp(tmp_path, path)
        finally:
            os.chmod(path, 0o644)
    assert_refused(result, "cannot be read")


def with_a_carriage_return(where: str) -> tuple:
    """The committed stamp with a carriage return, and the line it is on."""
    text = stamp()
    opening, closing = docstring_span(text)
    lines = lines_of(text)
    if where == "every-line-crlf":
        return text.replace("\n", "\r\n"), 1
    if where == "the-spdx-line":
        number = 1
    elif where == "a-docstring-line":
        number = 4
        assert opening < number < closing and lines[number - 1], (
            "the fixture is wrong: line 4 is not a docstring line with text")
    elif where == "the-version-line":
        number = line_number(text, assignment("VERSION", "0.0.0"))
    elif where == "inside-a-docstring-line":
        number = opening + 3
        line = lines[number - 1]
        lines[number - 1] = line[:5] + "\r" + line[5:]
        return text_of(lines), number
    else:
        raise ValueError(where)
    lines[number - 1] += "\r"
    return text_of(lines), number


@pytest.mark.parametrize("where", [
    "the-spdx-line", "a-docstring-line", "inside-a-docstring-line",
    "the-version-line", "every-line-crlf"])
def test_stamp_reader_refuses_a_carriage_return_naming_its_line(tmp_path,
                                                                where):
    """ROW: a carriage return on line N, `is malformed:` naming line N.

    Rule 1 comes before the others, so it holds on a `#` line and inside the
    docstring as well as on an assignment, and a file checked out with CRLF
    endings is refused at its first line."""
    text, number = with_a_carriage_return(where)
    path = write_stamp(tmp_path / "stamp", text)
    assert_refused(read_stamp(tmp_path, path), "is malformed:", lines=(number,))


@pytest.mark.parametrize("name", layout.STAMP_FIELDS)
def test_stamp_reader_refuses_a_missing_name(tmp_path, name):
    """ROW: a name missing, each of the five in turn, `is malformed:`
    naming it (rule 5)."""
    text = removed(stamp(), assignment(name, layout.UNSTAMPED[name]))
    path = write_stamp(tmp_path / "stamp", text)
    assert_refused(read_stamp(tmp_path, path), "is malformed:", fields=(name,))


@pytest.mark.parametrize("name, value", [
    *[(name, layout.UNSTAMPED[name]) for name in layout.STAMP_FIELDS],
    ("VERSION", "2.0.0")],
    ids=[*layout.STAMP_FIELDS, "VERSION-with-another-value"])
def test_stamp_reader_refuses_a_repeated_name(tmp_path, name, value):
    """ROW: a name repeated, `is malformed:` naming it (rule 5), whether the
    second line says the same as the first or something else."""
    base = stamp()
    text, _ = inserted(base, line_number(base, assignment(
        name, layout.UNSTAMPED[name])), assignment(name, value))
    path = write_stamp(tmp_path / "stamp", text)
    assert_refused(read_stamp(tmp_path, path), "is malformed:", fields=(name,))


@pytest.mark.parametrize("name", ["Version", "version", "BUILD"])
def test_stamp_reader_refuses_an_unknown_name(tmp_path, name):
    """ROW: an unknown name, such as `Version` or `BUILD`, `is malformed:`
    naming it (rule 4): a name is one of the five, spelled as the five are."""
    text, _ = appended(stamp(), assignment(name, "0.0.0"))
    path = write_stamp(tmp_path / "stamp", text)
    assert_refused(read_stamp(tmp_path, path), "is malformed:", fields=(name,))


#: Lines that are not `NAME = "VALUE"` from column 0 with one space either
#: side of `=`, or whose value holds a `"`, `\` or `$` (rule 4): the line
#: each replaces, and what is written in its place.
NOT_AN_ASSIGNMENT = {
    "no-spaces": ('VERSION = "0.0.0"', 'VERSION="0.0.0"'),
    "two-spaces-before": ('VERSION = "0.0.0"', 'VERSION  = "0.0.0"'),
    "two-spaces-after": ('VERSION = "0.0.0"', 'VERSION =  "0.0.0"'),
    "tabs": ('VERSION = "0.0.0"', 'VERSION\t=\t"0.0.0"'),
    "single-quotes": ('VERSION = "0.0.0"', "VERSION = '0.0.0'"),
    "unquoted": ('VERSION = "0.0.0"', "VERSION = 0.0.0"),
    "a-quote-that-does-not-close": ('VERSION = "0.0.0"', 'VERSION = "0.0.0'),
    "not-at-column-0": ('VERSION = "0.0.0"', ' VERSION = "0.0.0"'),
    "a-trailing-comment": ('VERSION = "0.0.0"',
                           'VERSION = "0.0.0"  # the release'),
    "a-quote-in-the-value": ('TAG = ""', 'TAG = "v1"1"'),
    "a-backslash-in-the-value": ('REPOSITORY = ""',
                                 'REPOSITORY = "opensoft\\x"'),
    "a-dollar-in-the-value": ('REPOSITORY = ""',
                              'REPOSITORY = "opensoft/$HOME"'),
    "a-statement": (None, "print(VERSION)"),
}


@pytest.mark.parametrize("which", NOT_AN_ASSIGNMENT)
def test_stamp_reader_refuses_a_line_that_is_not_name_equals_value(tmp_path,
                                                                  which):
    """ROW: a line that is not `NAME = "VALUE"`, `is malformed:` naming its
    line number (rule 4)."""
    old, new = NOT_AN_ASSIGNMENT[which]
    text, number = (appended(stamp(), new) if old is None
                    else replaced(stamp(), old, new))
    path = write_stamp(tmp_path / "stamp", text)
    assert_refused(read_stamp(tmp_path, path), "is malformed:", lines=(number,))


def test_stamp_reader_refuses_an_unclosed_docstring(tmp_path):
    """ROW: an unclosed docstring, `is malformed:` naming the docstring.
    With its closing line gone, the five assignments are docstring lines, and
    the file ends inside it (rule 3)."""
    text = stamp(**RELEASE)
    _, closing = docstring_span(text)
    lines = lines_of(text)
    assert lines[closing - 1] == '"""', "the fixture is wrong: no closing line"
    del lines[closing - 1]
    path = write_stamp(tmp_path / "stamp", text_of(lines))
    assert_refused(read_stamp(tmp_path, path), "is malformed:",
                   words=("docstring",))


#: Docstring lines that begin, in any case, with `version` or `__version__`
#: followed by optional spaces and `=` (rule 3). Hatch would take the first
#: four as the version; the guard is the rule, and holds for the rest too.
GUARDED_LINES = {
    "version": 'version = "9.9.9"',
    "VERSION": 'VERSION = "9.9.9"',
    "__version__": "__version__ = '9.9.9'",
    "__Version__-without-spaces": '__Version__="9.9.9"',
    "unquoted": "Version=9.9.9",
    "spaces-then-nothing": "version   =",
}


@pytest.mark.parametrize("which", GUARDED_LINES)
def test_stamp_reader_refuses_a_docstring_line_hatch_could_read_as_the_version(
        tmp_path, which):
    """ROW: a docstring line hatch could read as the version, `is malformed:`
    naming that line. Hatch takes the first line anywhere in the file that
    its pattern matches, docstring or not, so such a line would make the
    build and the command read two different versions."""
    base = stamp(**RELEASE)
    opening, _ = docstring_span(base)
    text, number = inserted(base, opening, GUARDED_LINES[which])
    path = write_stamp(tmp_path / "stamp", text)
    assert_refused(read_stamp(tmp_path, path), "is malformed:", lines=(number,))


#: contracts/stamp.md's three partial rows: the stamp, and the fields that are
#: empty in it, which the reason names. In the second, `TAG` is the one of
#: `TAG`, `COMMIT` and `DIGEST` that is set, and `REPOSITORY` is set too, so
#: the empty fields are exactly the two.
PARTIAL = {
    "a-commit-and-no-digest": ({**RELEASE, "DIGEST": ""}, ("DIGEST",)),
    "a-tag-alone": ({**RELEASE, "COMMIT": "", "DIGEST": ""},
                    ("COMMIT", "DIGEST")),
    "unstamped-looking-with-a-repository": (
        {"REPOSITORY": "opensoft/openRepoTools"}, ("REPOSITORY",)),
}


@pytest.mark.parametrize("which", PARTIAL)
def test_stamp_reader_refuses_a_partial_stamp_naming_its_empty_fields(tmp_path,
                                                                     which):
    """ROWS: a partial stamp, `is partial:` naming what is empty, or, for an
    unstamped-looking stamp, the `REPOSITORY` that names nothing. All or
    nothing (FR-010): a partial stamp is never read as the part it holds."""
    fields, named = PARTIAL[which]
    path = write_stamp(tmp_path / "stamp", stamp(**fields))
    assert_refused(read_stamp(tmp_path, path), "is partial:", fields=named)


#: contracts/stamp.md's malformed-field rows: every field is set, and one is
#: not the shape its rule gives it. Each stamp is wrong in that one field
#: alone, the field the reason names.
MALFORMED = {
    "version-0.0.0-with-a-tag-commit-and-digest": (
        {**RELEASE, "VERSION": "0.0.0", "TAG": "v0.0.0"}, "VERSION"),
    **{f"version-{v}": (release_at(v), "VERSION")
       for v in ("1.1", "01.1.0", "1.1.0-rc1", "1.01.0", "1.1.0.0", "v1.1.0",
                 "1.1.0rc", "1.1.0rc01", "1.1.0RC1")},
    "tag-v1.2.0": ({**RELEASE, "TAG": "v1.2.0"}, "TAG"),
    "tag-without-its-v": ({**RELEASE, "TAG": "1.1.0"}, "TAG"),
    "tag-with-a-capital-v": ({**RELEASE, "TAG": "V1.1.0"}, "TAG"),
    "commit-of-39-digits": ({**RELEASE, "COMMIT": RELEASE["COMMIT"][:39]},
                            "COMMIT"),
    "commit-of-41-digits": ({**RELEASE, "COMMIT": RELEASE["COMMIT"] + "8"},
                            "COMMIT"),
    "commit-in-upper-case": ({**RELEASE, "COMMIT": RELEASE["COMMIT"].upper()},
                             "COMMIT"),
    "digest-of-63-digits": ({**RELEASE, "DIGEST": RELEASE["DIGEST"][:63]},
                            "DIGEST"),
    "digest-in-upper-case": ({**RELEASE, "DIGEST": RELEASE["DIGEST"].upper()},
                             "DIGEST"),
    "repository-without-an-owner": ({**RELEASE, "REPOSITORY": "openRepoTools"},
                                    "REPOSITORY"),
    "repository-a-b-c": ({**RELEASE, "REPOSITORY": "a/b/c"}, "REPOSITORY"),
    "repository-without-a-name": ({**RELEASE, "REPOSITORY": "opensoft/"},
                                  "REPOSITORY"),
}


@pytest.mark.parametrize("which", MALFORMED)
def test_stamp_reader_refuses_a_malformed_field(tmp_path, which):
    """ROWS: a malformed field, `is malformed:` naming it. `VERSION` is
    `X.Y.Z` or `X.Y.ZrcN` with no leading zero and is not `0.0.0`; `TAG` is
    exactly `v$VERSION`; `COMMIT` is 40 lowercase hex digits and `DIGEST`
    64; `REPOSITORY` is an owner/name slug (contracts/stamp.md, "The checks
    after the read")."""
    fields, named = MALFORMED[which]
    path = write_stamp(tmp_path / "stamp", stamp(**fields))
    assert_refused(read_stamp(tmp_path, path), "is malformed:", fields=(named,))


def one_fixture_per_row(work: Path) -> dict:
    """A path for one fixture of each row of the refusal table, with the
    missing-name row taken for each of the five names, as the table says."""
    paths = {}
    unreadable = work / "a-directory" / "_release.py"
    unreadable.mkdir(parents=True)
    paths["unreadable"] = unreadable

    def put(row: str, text: str) -> None:
        paths[row] = write_stamp(work / row, text)

    put("carriage-return", with_a_carriage_return("a-docstring-line")[0])
    for name in layout.STAMP_FIELDS:
        put(f"missing-{name}",
            removed(stamp(), assignment(name, layout.UNSTAMPED[name])))
    base = stamp()
    put("repeated", inserted(base, line_number(base, 'COMMIT = ""'),
                             'COMMIT = ""')[0])
    put("unknown", appended(stamp(), 'BUILD = "1"')[0])
    put("not-name-equals-value",
        replaced(stamp(), 'VERSION = "0.0.0"', "VERSION = '0.0.0'")[0])
    lines = lines_of(stamp())
    del lines[docstring_span(stamp())[1] - 1]
    put("unclosed-docstring", text_of(lines))
    released = stamp(**RELEASE)
    put("guarded-docstring-line", inserted(released, docstring_span(released)[0],
                                           GUARDED_LINES["version"])[0])
    for row, (fields, _) in PARTIAL.items():
        put(row, stamp(**fields))
    for row in ("version-0.0.0-with-a-tag-commit-and-digest", "version-1.1",
                "tag-v1.2.0", "commit-of-39-digits", "digest-of-63-digits",
                "repository-without-an-owner"):
        put(row, stamp(**MALFORMED[row][0]))
    return paths


def test_stamp_reader_gives_each_row_its_own_reason(tmp_path):
    """EACH REASON MUST BE DISTINCT (contracts/stamp.md): one fixture of
    every row of the refusal table, each of the five missing names among
    them, and no two give the same `STAMP_WHY`."""
    reasons = {}
    for row, path in one_fixture_per_row(tmp_path / "rows").items():
        read = read_stamp(tmp_path / "work" / row, path)
        assert read.status == 1, f"{row}: stamp_read did not refuse it"
        reasons[row] = read.why
    same = {why: sorted(r for r in reasons if reasons[r] == why)
            for why in reasons.values()}
    shared = {why: rows for why, rows in same.items() if len(rows) > 1}
    assert not shared, f"rows that share a reason: {shared}"


# --- test_stamp_hatch_*: hatch and bash read one VERSION --------------------
#
# HATCH'S VERSION SOURCE, copied from hatchling 1.27.0, the backend
# `pyproject.toml` pins. The two copied lines are `hatchling/version/core.py:6`,
# the pattern, and `:32`, the search, read on 2026-10-18 from the published
# wheel `hatchling-1.27.0-py3-none-any.whl` (sha256
# d3a2f3567c4f926ea39849cdf924c7e99e6686c9c8e288ae1037c8fa2a5d937b), whose
# RECORD carries that file's own digest. contracts/stamp.md cites the same
# two lines; the `:31` it cited before is the blank line above the search.

#: hatchling/version/core.py:6 in hatchling 1.27.0, exactly:
DEFAULT_PATTERN = r'(?i)^(__version__|VERSION) *= *([\'"])v?(?P<version>.+?)\2'


def hatch_version(path: Path):
    """What hatch's regex version source reads from `path`: `(version, the
    number of the line it found it on)`, or None where nothing matches.

    `VersionFile.read`, down to the steps that decide the answer: the file
    is read as text, as `:26-27` read it (so universal newlines apply, as in
    the build); the pattern is the default one, as `:29-30` choose it; and
    the first match under `re.MULTILINE` is taken, with `:32` exactly.
    """
    with open(path, encoding='utf-8') as f:
        contents = f.read()
    pattern = DEFAULT_PATTERN
    match = re.search(pattern, contents, flags=re.MULTILINE)
    if not match:
        return None
    return (match.groupdict()["version"],
            contents.count("\n", 0, match.start()) + 1)


@pytest.mark.parametrize("which", ["committed", *STAMPS])
def test_stamp_hatch_and_stamp_read_read_the_same_version(tmp_path, which):
    """FR-013: THE BUILD BACKEND AND THE COMMAND READ ONE `VERSION`, from the
    committed file and from stamped ones. Hatch's first match is the
    `VERSION` line itself: a `#` line, such as the SPDX line, can never match
    its pattern, and the docstring holds no line it could take."""
    fields = dict(layout.UNSTAMPED) if which == "committed" else STAMPS[which]
    text = stamp() if which == "committed" else stamp(**fields)
    path = write_stamp(tmp_path / "stamp", text)
    version_line = line_number(text, assignment("VERSION", fields["VERSION"]))
    assert hatch_version(path) == (fields["VERSION"], version_line), (
        f"hatch's pattern reads {hatch_version(path)} from the {which} stamp, "
        f"not {fields['VERSION']!r} on line {version_line}")
    read = read_stamp(tmp_path, path)
    assert_accepted(read, "unstamped" if which == "committed" else "stamped",
                    fields)
    assert read.version == hatch_version(path)[0]


def test_stamp_hatch_would_misread_a_guarded_docstring_line_and_stamp_read_refuses_it(
        tmp_path):
    """THE FIXTURE THE GUARD EXISTS FOR. A docstring line `version = "9.9.9"`
    above the real `VERSION = "1.1.0"` is the first line hatch's pattern
    matches, so a wheel built from it would carry 9.9.9 while its stamp says
    1.1.0. No `VERSION` can come from both here, so the agreement is that
    no run ever reads one: `stamp_read` refuses the file, naming the line,
    and a package carrying it refuses every invocation."""
    base = stamp(**RELEASE)
    text, number = inserted(base, docstring_span(base)[0],
                            GUARDED_LINES["version"])
    path = write_stamp(tmp_path / "stamp", text)
    assert hatch_version(path) == ("9.9.9", number), (
        f"the fixture is wrong: hatch's pattern reads {hatch_version(path)}, "
        f"not the docstring's line {number}")
    assert_refused(read_stamp(tmp_path, path), "is malformed:", lines=(number,))


# --- running the command ----------------------------------------------------

def environment(home: Path, network_log: Path | None = None,
                extra: dict | None = None) -> dict:
    """`command_env`, with every `OPENREPOTOOLS_PACKAGE_*` and `PIPX_*`
    variable of the caller's own shell taken out, so that a test sets the
    ones it is about. With `network_log`, a `gh` and a `curl` that write down
    that they were asked, and refuse, come first on PATH."""
    env = command_env(home)
    for name in [n for n in env
                 if n.startswith(("OPENREPOTOOLS_PACKAGE_", "PIPX_"))]:
        del env[name]
    if network_log is not None:
        shims = network_log.parent / "refusing-network"
        shims.mkdir(parents=True, exist_ok=True)
        for tool in ("gh", "curl"):
            (shims / tool).write_text(
                "#!/bin/sh\n"
                f"printf '%s %s\\n' {tool} \"$*\" >> "
                f"{shlex.quote(str(network_log))}\n"
                "exit 1\n", encoding="utf-8")
            (shims / tool).chmod(0o755)
        env["PATH"] = f"{shims}{os.pathsep}{env['PATH']}"
    env.update(extra or {})
    return env


def run(argv: list, home: Path, cwd: Path, *, network_log: Path | None = None,
        extra: dict | None = None,
        stdin: str = "") -> subprocess.CompletedProcess:
    """One run, with stdin a pipe and never a terminal, and `home` as HOME."""
    home.mkdir(parents=True, exist_ok=True)
    cwd.mkdir(parents=True, exist_ok=True)
    return subprocess.run(argv, capture_output=True, text=True, check=False,
                          input=stdin, cwd=str(cwd),
                          env=environment(home, network_log, extra))


def transcript(result: subprocess.CompletedProcess) -> str:
    return (f"exit {result.returncode}\n--- stdout\n{result.stdout}"
            f"--- stderr\n{result.stderr}")


#: Where a fake installed package goes: a plain prefix, as pip's user base
#: is, and a pipx venv under macOS's default pipx home, whose path holds a
#: space.
PLACES = ("a-prefix", "a-pipx-venv-in-a-home-with-a-space")


def package(work: Path, text: str | None = None,
            where: str = "a-prefix") -> Path:
    """A `package_tree` whose stamp is `text` (the committed one when None),
    built under `work`, which is canonical. Returns its `payload/`."""
    if where == "a-prefix":
        return layout.package_tree(work / "prefix", stamp=text)
    if where == "a-pipx-venv-in-a-home-with-a-space":
        venv = layout.pipx_venv(work / "Library" / "Application Support" / "pipx",
                                "1.17.8", stamp=text)
        found = sorted(venv.glob("lib/python*/site-packages/openrepotools/payload"))
        assert len(found) == 1, f"{venv} holds {len(found)} payloads"
        return found[0]
    raise ValueError(where)


def run_payload(work: Path, payload: Path, *args: str,
                **how) -> subprocess.CompletedProcess:
    """`bash <payload>/openRepoTools <args>`, as the entry module's exec runs
    it, with `<work>/home` as HOME."""
    return run(["bash", str(payload / "openRepoTools"), *args],
               work / "home", work / "cwd", **how)


def run_checkout(work: Path, *args: str, **how) -> subprocess.CompletedProcess:
    """This checkout's `openRepoTools <args>`, with `<work>/home` as HOME."""
    return run(["bash", str(COMMAND), *args], work / "home", work / "cwd",
               **how)


def placed(home: Path) -> list:
    """Everything a run left in its HOME, which starts empty."""
    return sorted(str(p.relative_to(home)) for p in home.rglob("*"))


# --- test_package_version_* -------------------------------------------------

@pytest.mark.parametrize("where", PLACES)
@pytest.mark.parametrize("which", STAMPS)
def test_package_version_prints_the_stamped_five_lines_exactly(tmp_path, which,
                                                               where):
    """US2 SCENARIO 1 (FR-014): A STAMPED PACKAGE NAMES ITS RELEASE, in
    exactly five lines on stdout, exit 0: the version, the repository and the
    commit, then the version, the tag, the commit and the digest with its
    definition's label. For v1.1.0 the first line is `openRepoTools 1.1.0
    (opensoft/openRepoTools-code @ <commit>)`."""
    work = tmp_path.resolve()
    payload = package(work, stamp(**STAMPS[which]), where)
    result = run_payload(work, payload, "--version")
    assert (result.returncode, result.stdout, result.stderr) == (
        0, STAMPED_VERSION.format(**STAMPS[which]), ""), transcript(result)


@pytest.mark.parametrize("where", PLACES)
def test_package_version_prints_the_unstamped_five_lines_exactly(tmp_path,
                                                                 where):
    """US2 SCENARIO 2 (FR-014): A PACKAGE BUILT FROM A CHECKOUT SAYS SO, with
    the committed stamp, as the `package` job builds it."""
    work = tmp_path.resolve()
    payload = package(work, None, where)
    result = run_payload(work, payload, "--version")
    assert (result.returncode, result.stdout, result.stderr) == (
        0, UNSTAMPED_VERSION, ""), transcript(result)


@pytest.mark.parametrize("which", ["unstamped", "final"])
def test_package_version_names_the_stamp_whatever_repo_and_ref_say(tmp_path,
                                                                   which):
    """A package's `--version` names the bytes it is, from its stamp, and not
    the source a fetch would read: `$OPENREPOTOOLS_REPO` and
    `$OPENREPOTOOLS_REF` change no line of it."""
    work = tmp_path.resolve()
    text = None if which == "unstamped" else stamp(**RELEASE)
    expected = (UNSTAMPED_VERSION if which == "unstamped"
                else STAMPED_VERSION.format(**RELEASE))
    result = run_payload(work, package(work, text), "--version", extra={
        "OPENREPOTOOLS_REPO": NAMED_SOURCE["repo"],
        "OPENREPOTOOLS_REF": NAMED_SOURCE["ref"]})
    assert (result.returncode, result.stdout, result.stderr) == (
        0, expected, ""), transcript(result)


# --- test_package_broken_stamp_* --------------------------------------------

#: One fixture for each of contracts/cli-output.md's three causes. Each is a
#: regular `_release.py`, so the run is in package mode (design.md Decision
#: 4), and broken: mode 000 (which root can read, so that case skips for
#: root); a `COMMIT` with no `DIGEST`; a `TAG` that is not `v$VERSION`.
BROKEN = {
    "cannot-be-read": "cannot be read",
    "is-partial": "is partial:",
    "is-malformed": "is malformed:",
}
BROKEN_CASES = [pytest.param("cannot-be-read", marks=NOT_ROOT,
                             id="cannot-be-read"),
                "is-partial", "is-malformed"]


def broken_package(work: Path, kind: str) -> Path:
    """A package whose stamp is broken by `kind`. Returns its `payload/`."""
    if kind == "cannot-be-read":
        payload = package(work)
        os.chmod(payload.parent / "_release.py", 0)
        return payload
    if kind == "is-partial":
        return package(work, stamp(**{**RELEASE, "DIGEST": ""}))
    if kind == "is-malformed":
        return package(work, stamp(**{**RELEASE, "TAG": "v1.2.0"}))
    raise ValueError(kind)


def mend(payload: Path) -> None:
    """Give a mode-000 stamp its mode back, so the tree can be read and
    removed after the test."""
    path = payload.parent / "_release.py"
    if path.is_file():
        os.chmod(path, 0o644)


def refusal_reason(result: subprocess.CompletedProcess, cause: str) -> str:
    """The `<why>` of an exact broken-stamp refusal, which begins with
    `cause`: exit 2, nothing on stdout (no version, no usage, no placement
    line), and on stderr the blank line `die` prints, then the one line."""
    assert result.returncode == 2, (
        "a broken stamp did not refuse with exit 2:\n" + transcript(result))
    assert result.stdout == "", (
        "a run with a broken stamp printed on stdout:\n" + transcript(result))
    match = BROKEN_STAMP_STDERR.fullmatch(result.stderr)
    assert match, ("stderr is not exactly contracts/cli-output.md's broken-stamp "
                   "refusal:\n" + transcript(result))
    why = match.group("why")
    assert CAUSES[cause].fullmatch(why), (
        f"the refusal's <why> does not begin with {cause!r} in its contract "
        f"form: {why!r}")
    return why


def same_file_spellings(why: str, payload: Path) -> str:
    """`why` with the stamp's path, however a run spells it, as `<stamp>`."""
    stamp_path = payload.parent / "_release.py"
    for spelling in sorted({str(stamp_path), str(stamp_path.resolve()),
                            f"{payload}/../_release.py",
                            f"{payload.resolve()}/../_release.py"},
                           key=len, reverse=True):
        why = why.replace(spelling, "<stamp>")
    return why


@pytest.mark.parametrize("args", [("--help",), ("--version",), ("--install",)],
                         ids=["help", "version", "install"])
@pytest.mark.parametrize("kind", BROKEN_CASES)
def test_package_broken_stamp_refuses_before_any_argument_and_places_nothing(
        tmp_path, kind, args):
    """US2 SCENARIO 4 (FR-012): A BROKEN STAMP REFUSES EVERY INVOCATION,
    `--help` included, with exit 2, before any argument is acted on.

    The refusal is contracts/cli-output.md's line, filled with `stamp_read`'s
    own `STAMP_WHY` for that file. It names the stamp file and the fix,
    `pipx reinstall openrepotools`, prints no version, places nothing in
    HOME, and asks no `gh` or `curl` anything.
    """
    work = tmp_path.resolve()
    payload = broken_package(work, kind)
    asked = work / "network-was-asked"
    try:
        result = run_payload(work, payload, *args, network_log=asked)
        why = refusal_reason(result, BROKEN[kind])
        assert placed(work / "home") == [], (
            f"a refused run left files in HOME: {placed(work / 'home')}")
        assert not asked.exists(), (
            "a refused run asked the network:\n"
            + asked.read_text(encoding="utf-8"))
        own = read_stamp(work / "reader", payload.parent / "_release.py")
        assert own.status == 1, "stamp_read accepts the stamp the run refused"
        assert same_file_spellings(why, payload) == same_file_spellings(
            own.why, payload), (
            f"the refusal's <why> is not stamp_read's STAMP_WHY for the same "
            f"file:\n  refusal:    {why!r}\n  STAMP_WHY:  {own.why!r}")
    finally:
        mend(payload)


@pytest.mark.parametrize("args", [
    (), ("--install", "--version"), ("--version", "--install"), ("Atlas",),
    ("wip",), ("wip", "init", "--dry-run")],
    ids=["no-argument", "install-then-version", "version-then-install",
         "an-unknown-argument", "wip-alone", "wip-init"])
def test_package_broken_stamp_refuses_every_other_invocation_first(tmp_path,
                                                                   args):
    """EVERY INVOCATION, NOT ONLY THE THREE NAMED (FR-012, FR-014): no
    argument at all, either order of `--install` and `--version`, an
    argument the parser refuses, and `wip`, whose `init` would otherwise ask
    `gh` for a login. Each gets the broken-stamp refusal and nothing else."""
    work = tmp_path.resolve()
    payload = broken_package(work, "is-partial")
    asked = work / "network-was-asked"
    result = run_payload(work, payload, *args, network_log=asked)
    refusal_reason(result, BROKEN["is-partial"])
    assert placed(work / "home") == [], placed(work / "home")
    assert not asked.exists(), asked.read_text(encoding="utf-8")


# --- test_package_no_env_channel_* ------------------------------------------

def run_unpackaged(work: Path, how: str, *args: str,
                   extra: dict) -> subprocess.CompletedProcess:
    """`openRepoTools <args>` run as a checkout or the one-line install runs:
    from this checkout; piped into `bash -s` as the install line pipes it,
    from a directory holding nothing named `bash`, so its `$SELF` is no file;
    or as the one-line install leaves it, a regular file in `<dir>`."""
    home, cwd = work / "home", work / "cwd"
    if how == "a-checkout":
        return run(["bash", str(COMMAND), *args], home, cwd, extra=extra)
    if how == "a-piped-one-line-install":
        return run(["bash", "-s", "--", *args], home, cwd, extra=extra,
                   stdin=COMMAND.read_text(encoding="utf-8"))
    if how == "the-file-a-one-line-install-placed":
        bin_dir = work / "placed" / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        copy = bin_dir / "openRepoTools"
        copy.write_bytes(COMMAND.read_bytes())
        copy.chmod(0o755)
        return run(["bash", str(copy), *args], home, cwd, extra=extra)
    raise ValueError(how)


@pytest.mark.parametrize("source", ["default-source", "named-source"])
@pytest.mark.parametrize("how", ["a-checkout", "a-piped-one-line-install",
                                 "the-file-a-one-line-install-placed"])
def test_package_no_env_channel_a_checkout_and_the_one_line_install_print_their_source(
        tmp_path, how, source):
    """US2 SCENARIO 3, SC-002: WITH EVERY `OPENREPOTOOLS_PACKAGE_*` VARIABLE
    SET, A CHECKOUT AND THE ONE-LINE INSTALL PRINT EXACTLY
    `openRepoTools (<repo> @ <ref>)`, and no version number: `<repo>` and
    `<ref>` as `$OPENREPOTOOLS_REPO` and `$OPENREPOTOOLS_REF` name them, or
    `opensoft/openRepoTools @ main` where nothing does (research R4)."""
    work = tmp_path.resolve()
    names = DEFAULT_SOURCE if source == "default-source" else NAMED_SOURCE
    extra = dict(PACKAGE_VARIABLES)
    if source == "named-source":
        extra.update(OPENREPOTOOLS_REPO=names["repo"],
                     OPENREPOTOOLS_REF=names["ref"])
    result = run_unpackaged(work, how, "--version", extra=extra)
    assert (result.returncode, result.stdout, result.stderr) == (
        0, CHECKOUT_VERSION.format(**names), ""), transcript(result)


@pytest.mark.parametrize("which", ["unstamped", "final"])
def test_package_no_env_channel_a_package_prints_its_own_stamp(tmp_path, which):
    """THE STAMP COMES FROM THE FILE BESIDE THE PAYLOAD AND NOWHERE ELSE
    (FR-011): with research R4's variables naming a whole other release, an
    unstamped package still says it is unstamped, and a stamped one still
    names its own release."""
    work = tmp_path.resolve()
    text = None if which == "unstamped" else stamp(**RELEASE)
    expected = (UNSTAMPED_VERSION if which == "unstamped"
                else STAMPED_VERSION.format(**RELEASE))
    result = run_payload(work, package(work, text), "--version",
                         extra=dict(PACKAGE_VARIABLES))
    assert (result.returncode, result.stdout, result.stderr) == (
        0, expected, ""), transcript(result)


def test_package_no_env_channel_cannot_mend_a_broken_stamp(tmp_path):
    """AND NO VARIABLE MENDS A BROKEN ONE: a stamp with a `COMMIT` and no
    `DIGEST`, beside research R4's variables naming a whole stamp, is still
    refused, and no version is printed."""
    work = tmp_path.resolve()
    payload = broken_package(work, "is-partial")
    result = run_payload(work, payload, "--version",
                         extra=dict(PACKAGE_VARIABLES))
    refusal_reason(result, BROKEN["is-partial"])


# --- test_package_parser_* --------------------------------------------------

#: Arguments whose answer does not depend on where the command runs from:
#: the usage, and each refusal the parser makes before anything is read.
PARSER_ARGUMENTS = {
    "help": ("--help",),
    "h": ("-h",),
    "no-argument": (),
    "an-unknown-argument": ("Atlas",),
    "another-command-s-flag": ("--doctor",),
    "install-and-more": ("--install", "Atlas"),
    "wip-alone": ("wip",),
    "wip-an-unknown-verb": ("wip", "destroy"),
    "wip-init-an-option-with-no-value": ("wip", "init", "--org"),
}


@pytest.mark.parametrize("args", list(PARSER_ARGUMENTS.values()),
                         ids=list(PARSER_ARGUMENTS))
@pytest.mark.parametrize("which", ["final", "unstamped"])
def test_package_parser_answers_as_a_checkout_does(tmp_path, which, args):
    """US2 SCENARIO 5 (FR-014): IN A PACKAGE WHOSE STAMP IS SOUND, the usage
    and the parser's refusals are a checkout's: the same exit status, the
    same stdout and the same stderr, byte for byte, and nothing placed."""
    work = tmp_path.resolve()
    text = None if which == "unstamped" else stamp(**RELEASE)
    payload = package(work, text)
    checkout = run_checkout(work, *args)
    assert placed(work / "home") == [], placed(work / "home")
    packaged = run_payload(work, payload, *args)
    assert (packaged.returncode, packaged.stdout, packaged.stderr) == (
        checkout.returncode, checkout.stdout, checkout.stderr), (
        "the package does not answer as a checkout does.\n"
        f"=== the package\n{transcript(packaged)}\n"
        f"=== the checkout\n{transcript(checkout)}")
    assert placed(work / "home") == [], placed(work / "home")


@pytest.mark.parametrize("which", ["final", "unstamped"])
def test_package_parser_install_then_version_prints_the_release_and_installs_nothing(
        tmp_path, which):
    """`--install --version`, AS A CHECKOUT TAKES IT: the parser reaches
    `--version` before the install starts, so a checkout prints its
    `--version` and installs nothing. A package does the same with its own
    `--version`, the five lines of its stamp, and places nothing."""
    work = tmp_path.resolve()
    checkout_both = run_checkout(work, "--install", "--version")
    checkout_version = run_checkout(work, "--version")
    assert (checkout_both.returncode, checkout_both.stdout,
            checkout_both.stderr) == (0, checkout_version.stdout, ""), (
        "the case is wrong: a checkout's `--install --version` is not its "
        f"`--version`:\n{transcript(checkout_both)}")
    assert placed(work / "home") == [], placed(work / "home")
    text = None if which == "unstamped" else stamp(**RELEASE)
    expected = (UNSTAMPED_VERSION if which == "unstamped"
                else STAMPED_VERSION.format(**RELEASE))
    result = run_payload(work, package(work, text), "--install", "--version")
    assert (result.returncode, result.stdout, result.stderr) == (
        0, expected, ""), transcript(result)
    assert placed(work / "home") == [], (
        f"`--install --version` placed files: {placed(work / 'home')}")
