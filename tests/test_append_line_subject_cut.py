# SPDX-License-Identifier: Apache-2.0
"""`append-line`'s commit subject cut, on a register at `mode=primary`, under
an unset locale (feature 007, opensoft/openRepoTools#165; lane 5's test for
T425, as lane 3 asked in comment 6870386695; placed here as lane 2 agreed in
comment 6870458906).

THE DEFECT. `append-line` builds its commit subject with a cut of 72:
`msg="LANES(<lane>@<ws>): append line — ${text:0:72}"` for the plain form,
and `${le_line:0:72}` for T425's `--landing-expired` (`lanes-edit.sh`
:29629 and :3482 at line R merge101 `44f487d1`). Bash counts that cut in
characters only under a UTF-8 locale. With `LANG`, `LC_ALL` and `LC_CTYPE`
all unset, the locale is POSIX, bash counts BYTES, and the cut can end inside
a UTF-8 character. The seam writes `msg` as it is given (:5424), and
`lanes-index register commit` decodes it as UTF-8 and refuses it with 2,
"msg is not UTF-8" (`lanes-index` :13523-13527, read at :13849), before it
opens the store. So on primary a line whose text has a multibyte character
across byte 72 is refused and never written. Files mode commits the same
line, but not the same subject: git's commit reads the stray bytes of the
split character as Latin-1, so the subject it stores is valid UTF-8 that ends
in a wrong character (a stray E2 becomes `â`, U+00E2, bytes C3 A2), not in
bytes that are not UTF-8.

THE RULE (lane 3, comment 6870386695), which lane 4 builds in T425's next
round: each subject takes the longest prefix of at most 72 bytes that ends
where a UTF-8 character ends, computed on bytes under `LC_ALL=C`, so the
result is the same under any locale. Both modes then commit the same valid
subject. `subject_cut` below is that rule, as this module's oracle.

THE CASES, each on its own estate of lane 2's (`test_sql_register_order.py`'s
`Estate`, test 4's workstation over a clone of `tmpl` at `primary`), each
running `lanes-edit.sh` with `LANG`, `LC_ALL` and `LC_CTYPE` REMOVED from
its environment (the estate sets `LC_ALL=C`, and GitHub's runners set a UTF-8
`LANG`, which would hide the byte cut):

  * an ASCII text of 100 bytes, the control: it commits, and its subject keeps
    the text's first 72 bytes. It passes before the fix and after it.
  * a text whose em dash (U+2014, bytes E2 80 94) starts at byte 71, so that
    byte 72 falls inside it: on primary it must commit, and its subject must
    be valid UTF-8 and keep the text's first 71 bytes. It FAILS until T425's
    fix: `register commit` refuses the attempt, and the failure quotes that
    refusal.
  * the same text in files mode, on the same kind of estate with a `mode=files`
    configuration: the commit on the origin must carry the same subject. It
    FAILS until the fix too: git's commit reads the 72-byte cut's stray E2 as
    Latin-1, so files mode commits valid UTF-8 ending `splitsâ` (C3 A2), a
    wrong character, not bytes that are not UTF-8. After the fix both modes
    commit the subject that ends `... splits`.
  * `append-line --landing-expired`, a guard that passes before and after:
    the line it composes is `LANDING EXPIRED — lane <writer>, session
    <uuid>@<ws>, ...`: its em dash takes bytes 16 to 18, and from byte 19 to
    past byte 72 it is ` lane `, the writer's lane name (ASCII,
    `check_lane_name`, at least one byte), `, session ` and a 36-byte UUID
    (`valid_uuid`). So its cut at 72 can never end inside a character today,
    and the case checks that its subject keeps the line's first 72 bytes,
    which the rule gives too.

HOW THE STORED SUBJECT IS READ. On primary, the journal's `message` for the
write's seq, as hex of its UTF-8 bytes (`encode(convert_to(message,
'UTF8'), 'hex')`), so `psql`'s client encoding never touches it; the estate
runs no renderer, so there is no mirror commit to read. In files mode, the
raw commit object at the origin's `main` (`git cat-file commit`), whose
message's first line is the subject, compared as bytes.

WHY A TEE IN FRONT OF `lanes-index`. When `register commit` refuses with 2,
the parent relays only its `ERROR:` and `DETAIL:` lines (`pw_decide`), and
then removes the attempt directory with `commit.err` in it
(`pw_end` -> `pw_run_dir_done`), so the writer's stderr says only that the
commit "exited 2, above". Each case therefore runs a copy of the estate's
`lanes-edit.sh` (with its `repos.tsv` and `lane-start`) from a directory of
its own, where `lanes-index` is a small `sh` script that execs the estate's
own `lanes-index` for every call but `register commit`, whose stderr it also
keeps in a log the failure message quotes. The copy is byte for byte the
estate's, and `lanes-edit.sh` reads only those three files beside itself.

WHERE IT RUNS. Lane 2's estate is not on line R: this module needs a tree
that carries `tests/test_sql_register_order.py`, `tests/pgcluster.py` and
`tests/sql_register_helpers.py`, as a round's verify tree does. Where one of
them is missing, the module is skipped whole at collection, naming it, so a
tree without them still collects; that skip is no pass. Without PostgreSQL 16
every case skips by the engine's banner, as lane 2's do.

THE LANDING GATE (lane 2's T280, comment 6870449334): every id here waits
for T425, the task whose round carries the fix.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Sequence

import pytest

#: Lane 2's modules this one imports from, and the modules they import. A
#: tree without one of them cannot run these cases (see "WHERE IT RUNS").
LANE_2_ESTATE = ("test_sql_register_order", "pgcluster", "sql_register_helpers",
                 "test_lane_start_claude_current")

try:
    from test_sql_register_order import (CLIENT, EM, KEY, LA, LANES_MD, LB, PR, REGISTER, W_WS,
                                         Estate, Writer, estates, kind_line, session_of)  # noqa: F401
except ModuleNotFoundError as missing:
    if missing.name not in LANE_2_ESTATE:
        raise
    pytest.skip(f"lane 2's estate is not in this tree ({missing.name}.py is missing), so "
                f"append-line's subject cut cannot be run here; this skip is no pass",
                allow_module_level=True)

#: T280's table (lane 2, opensoft/openRepoTools#165 comment 6870449334): every
#: id of this module waits for T425, lane 4's task whose round fixes the cut.
SQL_REGISTER_GATE_TABLE = {"*": ("T425",)}

#: The locale variables removed from every run's environment.
LOCALE = ("LANG", "LC_ALL", "LC_CTYPE")

#: The cut, in bytes.
SUBJECT_BYTES = 72

#: The control: ASCII only, 100 bytes, no blank at byte 71.
ASCII_TEXT = (f"NOTE: lane {LA} appends an ASCII line longer than 72 bytes; its subject keeps "
              "the first 72 (T425)")

#: The defect's text: its em dash takes bytes 71 to 73, so byte 72 is inside
#: it, and the rule's cut is its first 71 bytes, which end on the `s` of
#: "splits".
DASH_TEXT = f"NOTE: lane {LA} has an em dash at byte 71 so a cut at byte 72 splits{EM}it (T425)"

#: The word `--landing-expired` carries, as lane 2's table case gives it.
WORD = "Release the stale LANDING (Recommended)"
WORD_WHERE = "lane openRepoTools-2's session"

#: The tee in front of the estate's `lanes-index` (see "WHY A TEE").
_TEE = r'''#!/bin/sh
# test_append_line_subject_cut.py: the estate's own lanes-index, exec'd for
# every call but `register commit`, whose stderr is also appended to the log.
if [ "${1-}" = register ] && [ "${2-}" = commit ]; then
  @REAL@ "$@" 2>@LOG@.$$
  rc=$?
  cat @LOG@.$$ >&2
  cat @LOG@.$$ >>@LOG@
  exit "$rc"
fi
exec @REAL@ "$@"
'''


def subject_cut(text: str, limit: int = SUBJECT_BYTES) -> bytes:
    """Lane 3's rule: the longest prefix of `text`'s UTF-8 bytes, at most
    `limit` long, that ends where a character ends."""
    data = text.encode("utf-8")[:limit]
    while data:
        try:
            data.decode("utf-8")
            return data
        except UnicodeDecodeError:
            data = data[:-1]
    return data


def prefix(lane: str) -> bytes:
    """The subject's words before the cut text, for a write by `lane`."""
    return f"LANES({lane}@{W_WS}): append line {EM} ".encode("utf-8")


def unset_locale(e: Estate) -> None:
    """Every later run of `e` with no `LANG`, `LC_ALL` or `LC_CTYPE`."""
    for name in LOCALE:
        e.env.pop(name, None)
    assert not [name for name in LOCALE if name in e.env]


def case_bin(e: Estate) -> Path:
    """The case's own copy of the estate's `lanes-edit.sh`, `repos.tsv` and
    `lane-start`, with the tee as its `lanes-index`. Made once per estate."""
    where = e.root / "alsc-bin"
    if not where.exists():
        where.mkdir()
        for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
            shutil.copy2(str(e.bindir / name), str(where / name))
        tee = (_TEE.replace("@REAL@", shlex.quote(str(e.bindir / "lanes-index")))
               .replace("@LOG@", shlex.quote(str(where / "register-commit.err"))))
        (where / "lanes-index").write_text(tee, encoding="utf-8")
        (where / "lanes-index").chmod(0o755)
    return where


def commit_said(e: Estate) -> str:
    """What `register commit` printed on stderr in `e`'s runs, or empty."""
    log = e.root / "alsc-bin" / "register-commit.err"
    return log.read_text(encoding="utf-8", errors="replace").strip() if log.exists() else ""


def run(e: Estate, lane: str, argv: Sequence[str], extra: Optional[dict] = None) -> Writer:
    return e.run(lane, list(argv), script=case_bin(e) / "lanes-edit.sh", extra=extra)


def stored(e: Estate, seq: int) -> dict:
    """The journal entry at `seq`: its verb and lane, its message's bytes and
    the bytes of each line it appended to `lanes/LANES.md`."""
    row = e.c.json(
        "SELECT json_build_object('verb', j.verb, 'lane', j.lane, "
        "'message', encode(convert_to(j.message, 'UTF8'), 'hex'), "
        "'appended', (SELECT coalesce(json_agg(encode(convert_to(x.new_text, 'UTF8'), 'hex') "
        f"ORDER BY x.ord), '[]'::json) FROM {REGISTER}.journal_edits x WHERE x.seq = j.seq "
        f"AND x.op = 'append' AND x.path = '{LANES_MD}')) "
        f"FROM {REGISTER}.journal j WHERE j.seq = {seq};")
    return {"verb": row["verb"], "lane": row["lane"], "message": bytes.fromhex(row["message"]),
            "appended": [bytes.fromhex(h) for h in row["appended"]]}


def utf8_or_why(data: bytes) -> str:
    try:
        data.decode("utf-8")
        return ""
    except UnicodeDecodeError as exc:
        return f"not UTF-8 ({exc})"


def refused(w: Writer, e: Estate, what: str) -> str:
    """The failure text of a run that should have exited 0."""
    said = commit_said(e) or "nothing: no register commit was run"
    return (f"{what}: exit {w.code}, not 0. lanes-index register commit said: {said}. "
            f"Its stderr ends: {w.err[-500:]}")


def committed_on_primary(e: Estate, lane: str, argv: Sequence[str], what: str) -> dict:
    """Run `argv` as `lane` on primary, and the one entry it journaled."""
    head = e.c.head()
    w = run(e, lane, argv)
    assert w.code == 0, refused(w, e, what)
    assert e.c.head() == head + 1, f"{what}: exit 0, but the head is {e.c.head()}, not {head + 1}"
    entry = stored(e, head + 1)
    assert (entry["verb"], entry["lane"]) == ("append-line", lane), entry
    return entry


@CLIENT
def test_append_line_subject_cut_keeps_72_bytes_of_an_ascii_text(estates):
    """The control: on primary, an ASCII line of 100 bytes commits, and the
    journal's message is the subject's prefix and the line's first 72 bytes."""
    data = ASCII_TEXT.encode("utf-8")
    assert data.isascii() and len(data) > SUBJECT_BYTES and data[SUBJECT_BYTES - 1:SUBJECT_BYTES] != b" "
    e = estates()
    unset_locale(e)
    entry = committed_on_primary(e, LA, ["append-line", ASCII_TEXT], "the ASCII line on primary")
    assert entry["appended"] == [data], entry["appended"]
    want = prefix(LA) + data[:SUBJECT_BYTES]
    assert entry["message"] == want, f"the stored subject is {entry['message']!r}, not {want!r}"


@CLIENT
def test_append_line_subject_cut_ends_on_a_whole_character(estates):
    """The defect: on primary, a line whose em dash starts at byte 71 commits,
    and the journal's message is valid UTF-8 and is the prefix and the line's
    first 71 bytes, the longest cut of at most 72 that ends on a character.
    Until T425's fix the 72-byte cut ends with E2, and `register commit`
    refuses the attempt, "msg is not UTF-8"."""
    data = DASH_TEXT.encode("utf-8")
    assert data[71:74] == EM.encode("utf-8"), "the text's em dash does not start at byte 71"
    assert utf8_or_why(data[:SUBJECT_BYTES]) != "", "the text's 72-byte cut is UTF-8"
    assert subject_cut(DASH_TEXT) == data[:71]
    e = estates()
    unset_locale(e)
    entry = committed_on_primary(e, LA, ["append-line", DASH_TEXT],
                                 f"the line with an em dash across byte 72, on primary (its 72-byte cut "
                                 f"ends {data[66:SUBJECT_BYTES]!r}, inside the dash)")
    assert entry["appended"] == [data], entry["appended"]
    message = entry["message"]
    assert not utf8_or_why(message), f"the stored subject is {utf8_or_why(message)}: {message!r}"
    want = prefix(LA) + data[:71]
    assert message == want, f"the stored subject is {message!r}, not {want!r}"


@CLIENT
def test_append_line_subject_cut_ends_on_a_whole_character_in_files_mode(estates):
    """The same line in files mode: it commits to the origin, and the
    commit's subject is the bytes primary stores, valid UTF-8. Until T425's
    fix git's commit reads the 72-byte cut's stray E2 as Latin-1, so files
    mode commits valid UTF-8 ending `splitsâ` (C3 A2): a wrong character, not
    bytes that are not UTF-8."""
    data = DASH_TEXT.encode("utf-8")
    e = estates()
    unset_locale(e)
    conf = e.root / "alsc-files.conf"
    conf.write_text("mode=files\n", encoding="utf-8")
    conf.chmod(0o600)
    w = run(e, LA, ["append-line", DASH_TEXT], extra={"LANES_INDEX_CONFIG": str(conf)})
    assert w.code == 0, refused(w, e, "the line with an em dash across byte 72, in files mode")
    shown = subprocess.run(["git", "show", "main:lanes/LANES.md"], cwd=str(e.origin), env=e.env,
                           capture_output=True, check=False)
    assert shown.returncode == 0 and data + b"\n" in shown.stdout, (
        f"the origin's lanes/LANES.md lacks the line: {shown.stderr[-300:]!r}")
    commit = subprocess.run(["git", "cat-file", "commit", "main"], cwd=str(e.origin), env=e.env,
                            capture_output=True, check=False)
    assert commit.returncode == 0, commit.stderr[-300:]
    subject = commit.stdout.partition(b"\n\n")[2].split(b"\n", 1)[0]
    want = prefix(LA) + data[:71]
    why = utf8_or_why(subject) or "UTF-8"
    assert subject == want, f"files mode committed the subject {subject!r}, {why}, not {want!r}"


@CLIENT
def test_append_line_subject_cut_keeps_72_bytes_of_the_stale_landing_form(estates):
    """The guard for `--landing-expired` (:3482): lane B releases lane A's
    LANDING of 31 minutes ago. The line's bytes 19 to 72 are ASCII by its
    composition (see the module's head), so its 72-byte cut ends on a
    character, and the journal's
    message is the prefix and the line's first 72 bytes, before the fix and
    after it."""
    e = estates()
    unset_locale(e)
    landing = run(e, LA, ["append-line", kind_line(e, "LANDING", LA, 31)])
    assert landing.code == 0, refused(landing, e, "lane A's LANDING")
    entry = committed_on_primary(
        e, LB, ["append-line", "--landing-expired", LA, "--pr", str(PR), "--repo", KEY, "--word", WORD,
                "--word-where", WORD_WHERE, "--word-utc", e.utc(1)], "the release of lane A's LANDING")
    assert len(entry["appended"]) == 1, entry["appended"]
    line = entry["appended"][0]
    opening = f"LANDING EXPIRED {EM} lane {LB}, session {session_of(LB)}@".encode("utf-8")
    assert line.startswith(opening) and len(line) > SUBJECT_BYTES, line
    assert subject_cut(line.decode("utf-8")) == line[:SUBJECT_BYTES], line[:SUBJECT_BYTES + 4]
    want = prefix(LB) + line[:SUBJECT_BYTES]
    assert entry["message"] == want, f"the stored subject is {entry['message']!r}, not {want!r}"
