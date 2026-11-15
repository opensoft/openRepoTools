# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 7 (AT-7, L2-N2; T211): `lanes-index import --at <C>`,
its byte-identical proof and its refusal on a difference, and R04's parity
test of `register classify` (opensoft/openRepoTools#165).

THE FIXTURE REGISTER (the test plan's AT-7, "Fixture"). A files-mode
workspace repository at commit C, on a bare origin, as
`test_lanes_index.py`'s `Estate` builds one, with a `lanes-edit.sh log NOTED`
write on top, so C's tip is bytes `lanes-edit.sh` wrote. It holds what AT-7
adds:

- `WORD` lines whose UTC carries milliseconds (`repoW-1`'s log);
- the six HOLD-shaped kinds R3 counted (Q17(B)): `HOLD (refresh)`,
  `HOLD (run id)`, `HOLD WITHDRAWN`, `HOLD EXPIRED`, `QUEUED-HOLD` and
  `LANDING WITHDRAWN`;
- a `HOLD` and a `LANDING` with no UTC, and a `LANDING` whose stamp does not
  parse, `2026-13-45T99:99Z` (U3), each on a repository of its own;
- a line in the `LANDING EXPIRED` shape with no `for lane`;
- an archived lane, aliases, and `lanes/repos.tsv` and `lanes/log/README.md`
  outside the render set (Q18 (A));
- a lane whose log file's name differs from the lane's in case (`repoD-1`,
  `lanes/log/RepoD-1.md`), and a lane with no log file (`repoC-1`);
- for `main_slots`' pairing, `LANDING` and `LANDED` lines naming one
  repository under two spellings (`opensoft/repoE`, `OpenSoft/RepoE`) and
  closing takes out of order; and, committed on C by the `main_slots` case
  alone, a `LANDED` naming no repository after its lane's `LANDING`s for
  one PR on two repositories (`REPOLESS_LANDED`; T211g; lane 3, #165
  comment 6771569269).

THE PARITY TEST, `test_register_classify_parity_holds_on_every_line` (R04;
CLI4.10 section 3.5, CLI4.10:629-638; R-F9-9), needs no engine: it feeds
every line of C's render set, and one of each text `append-line` refuses on
primary, to `parse_register_line` in process and to `lanes-index register
classify` by argv and stdin, and holds the five fields equal on every line.
Lane 1's T122 runs it by `sql_register_import and classify_parity`. It fails
until T122 lands: at `a2073eae` `register classify` is not a subcommand.

THE OTHER ELEVEN are real-engine tests, on `tests/pgcluster.py`'s `pg`: a
database cloned from the template, which holds the bootstrap's schema once
lane 2's T227 builds it (L1-A7). Without an engine they skip with T205's
banner. They fail until L1-A13 (`import --at`, lane 1's T115), L1-A16 (T118's
kinds) and lane 3's T301 (the scratch render the proof runs) land.

- The refusal's code is read from `lanes-index`'s named constant,
  `EXIT_IMPORT_REFUSED`, PC-10's code for `import --at`'s refusal (lane 1's
  T102 proposes 2; `contracts/exit-codes.md` sections 1, 3.2 and 4).
- The `lanes` count is one row per lane that a row names, in
  `lanes/LANES.md` and `lanes/archive/` together (design.md's `lanes`
  table, "one row per lane", and step 7, "each row's `raw` must equal its
  line's text"), never `build_records`' full count, which adds a record for
  each lane with a log and no row (`repoB-1` here; lane 1's T115 finding,
  #165 comment 6780760076).
- Only CRLF is a difference the import refuses. A trailing blank in a table
  row and a line of a kind the parser does not know are arms of the success
  case, `[trailing-blank]` and `[unknown-kind]` beside `[at-c]`: each line is
  stored as it stands and rendered back unchanged, so the import exits 0
  and the proof holds (design.md:1176, :1181, :1300-1304, :1467; lane 3's
  batches 9 and 11 (4), #165 comments 6781033556 and 6783909985).
- The import runs as the operator lane, `LANES_LANE=repoA-2`, through that
  lane's checkout (lane 1's T115; D24), with `LANES_INDEX_CONFIG` naming a
  configuration whose `register_url=` and `reader_url=` name the session
  cluster's Unix socket (the block's configuration rule), as the cluster's
  own user until T228's logins exist.
- "From SQL" in the read comparison is SQL's own render, `render_file` (lane
  1's T107), of every path in `files`, committed to a second workspace; each
  read then runs in files mode on both workspaces, which needs no reader of
  primary's (lanes 4 and 5).

TEST 7'S CUTOVER CASES (T272; AT-7, "The cutover (G)" and "The abort",
TP:1455-1481) are phase G's, at the end of this module. `CutoverRegister`
imports the fixture register at C, then runs `lanes-index cutover --import
<C>` as the operator lane through its checkout, by T203's flipped copy:
while `RENDER_GIT_HALF` is False, `cutover` refuses `lanes_register`, a
schema that is not a scratch one (lane 1's T116), and a write on primary
needs the flipped copy too, and the operator lane's own register checkout,
`<W>-lanes/repoA-2`, which `CutoverRegister.write` makes before the first
write (lane 3's batch g Q119). AT-F2's cases in `test_sql_register_cutover.py`
build on the same class. They fail until L1-A14 and lane 3's T327, the
marker's push, read-back and abort: until T327, `cutover`'s 0 is its
transaction alone, the marker stays `adding`, and nothing is pushed (T116's
point 1). The first write's mirror commit also needs the renderer's fork,
`render --checkout` (lane 3's T321 to T323, which T327 depends on).

NOTHING HERE STARTS A DATABASE OF ITS OWN, and every remote is a bare
repository under `tmp_path`.
"""

from __future__ import annotations

import atexit
import base64
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280, `tests/sql_register_gate.py`; task sets
#: version 12b's rule 11, opensoft/openRepoTools#165 6877673742), TEMPORARY:
#: T281 removes it in the last set. Where the gate is active, each id here is
#: skipped until every task its row names has landed, and the skip names them.
#: Each row is the fails-until clause of T211's Order (tasks:1961) or T272's
#: (tasks:2497) in tasks.md at lane 3's commit 17, 204145ae, each L-label as
#: the task that covers it (L1-A13 T115, L1-A14 T116, L1-A16 T118), as lane
#: 2's plan GP-24 v1 (sha256 16d738b9) gives it. No "*" row: the rows share
#: no task.
SQL_REGISTER_GATE_TABLE = {
    "test_a_cutover_pushes_one_fast_forward_marker_commit_with_no_credential": ("T116", "T327"),  # T272; tasks:2497
    "test_a_first_cutover_over_a_hold_with_no_readable_time_is_refused_2_and_sets_nothing": ("T112", "T115", "T116", "T118", "T301"),  # T211; tasks:1961
    "test_a_handoff_commit_on_the_tip_does_not_abort_the_cutover": ("T116", "T327"),  # T272; tasks:2497
    "test_a_reimport_replaces_seq_0": ("T115", "T118", "T301"),  # T211; tasks:1961
    "test_import_answers_every_read_as_the_files_do": ("T115", "T118", "T301"),  # T211; tasks:1961
    "test_import_at_a_commit_proves_a_byte_identical_render": ("T115", "T118", "T301"),  # T211; tasks:1961
    "test_import_loads_takes_with_no_readable_utc_and_a_holderless_landing_expired_as_they_stand": ("T115", "T118", "T301"),  # T211; tasks:1961
    "test_import_reads_origin_only_and_never_a_local_line": ("T115", "T118", "T301"),  # T211; tasks:1961
    "test_import_refuses_on_a_difference_and_loads_nothing": ("T115", "T118", "T301"),  # T211; tasks:1961
    "test_line_scopes_agrees_with_build_records_rules_over_every_line_of_the_imported_register": ("T115", "T118", "T301"),  # T211; tasks:1961
    "test_main_slots_pairing_equals_files_mode_rule_6_on_imported_history": ("T112", "T115", "T118", "T301"),  # T211; tasks:1961
    "test_register_classify_parity_holds_on_every_line": ("T115", "T118", "T122", "T301"),  # T211; tasks:1961
    "test_the_cutover_aborts_when_main_moved_under_lanes": ("T116", "T327"),  # T272; tasks:2497
    "test_the_first_write_after_cutover_is_the_cutovers_seq_plus_1_with_lag_0": ("T116", "T327", "T415", "T416"),  # T272; tasks:2497
    "test_the_imports_proof_is_timed_and_recorded": ("T115", "T118", "T301"),  # T211; tasks:1961
    "test_the_log_path_sidecar_names_the_same_log_file_in_unreadable_warnings": ("T113", "T115", "T118", "T301"),  # T211; tasks:1961
    "test_word_lines_with_milliseconds_import_verbatim_and_flagged": ("T115", "T118", "T301"),  # T211; tasks:1961
}

LANES_EDIT = REPO / "lanes-edit.sh"
INDEXER = REPO / "lanes-index"

#: The register's schema, `register_schema=`'s default (CLI4.10 section 2.5).
SCHEMA = "lanes_register"
#: The operator lane the import runs as (lane 1's T115: "It runs with
#: `LANES_LANE=<operator lane>`, through that lane's checkout").
OPERATOR = "repoA-2"
#: The label the configuration's `register_label=` carries.
LABEL = "register-test"

UUID_A1 = "aaaaaaaa-0001-4000-8000-00000000a001"
UUID_A2 = "aaaaaaaa-0003-4000-8000-00000000a003"
UUID_B1 = "bbbbbbbb-0001-4000-8000-00000000b001"
UUID_C1 = "dddddddd-0001-4000-8000-00000000d001"
UUID_D1 = "dddddddd-0002-4000-8000-00000000d002"
UUID_W1 = "eeeeeeee-0002-4000-8000-00000000e002"
UUID_Z1 = "eeeeeeee-0001-4000-8000-00000000e001"
TIP_A = "0123456789abcdef0123456789abcdef01234567"

#: Every lane the fixture register names, with its session: the rows of
#: `lanes/LANES.md` and the archived row.
LANES = {"repoA-1": UUID_A1, "repoA-2": UUID_A2, "repoC-1": UUID_C1, "repoD-1": UUID_D1,
         "repoW-1": UUID_W1, "repoZ-1": UUID_Z1}


def _row(lane: str, ids: str, state: str, started: str = "2026-10-01T00:00Z",
         ws: str = "Eagle / test / brett", objects: str = "none") -> str:
    return (f"| `{lane}` | harness {ids} | {ws} | {started} | {objects} | handoffs/{lane}.md "
            f"| {state} |")


#: THE TAKES AT-7 PUTS IN THE REGISTER, each named for the case that reads it.
TAKE_LINES = {
    "hold-no-utc": f"HOLD — lane repoA-2 (Eagle), window w: opensoft/repoH main {TIP_A} for a "
                   f"window with no stamp",
    "landing-no-utc": f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, PR #11 into "
                      f"opensoft/repoL main",
    "bad-stamp": f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, 2026-13-45T99:99Z, PR #12 "
                 f"into opensoft/repoS main",
}
#: THE DEAD `HOLD`'S RELEASE (lane 3's B16 post, #165 6814260122): the take
#: `TAKE_LINES["hold-no-utc"]` has no readable time, and lane 1's open-`HOLD`
#: check (T116 follow-up 6, line R's merge21f6) counts it as open, on lane 3's
#: ruling (#165 6813195977), so a first-form cutover over it refuses with 2.
#: Its holder, the operator lane, releases it, as an operator releases a dead
#: one before the freeze (operations.md act 4's steps 1 and 3), by
#: `lanes-edit.sh append-line`, before `CutoverRegister`'s import.
HOLD_NO_UTC_RELEASE = (f"HOLD RELEASED — lane repoA-2 (Eagle), 2026-10-01T05:20:00Z: "
                       f"opensoft/repoH main {TIP_A}")
#: The `LANDING EXPIRED` shape with no `for lane`: it names repoA-2's open
#: take, PR #9 on opensoft/repoE, and must release nothing (U3; F13).
EXPIRED_NO_HOLDER = (f"LANDING EXPIRED — lane repoA-1, session {UUID_A1}@Eagle, "
                     f"2026-10-01T05:00:00Z, PR #9 into opensoft/repoE main")

REGISTER_TEXT = "\n".join([
    "# LANES.md — the import's fixture register",
    "",
    "| lane | session id | workstation / env / user | started (UTC) | objects owned | handoff path | state |",
    "|---|---|---|---|---|---|---|",
    _row("repoA-1", f"`{UUID_A1}`", "PAUSED · 2026-10-01T01:00:00Z · parked for the night"),
    _row("repoA-2", f"`{UUID_A2}`", "LIVE · 2026-10-01T02:00:00Z · the operator lane"),
    _row("repoC-1", f"`{UUID_C1}`", "ENDED · 2026-09-01T00:00:00Z · a row with no log",
         started="2026-09-01"),
    _row("repoD-1", f"`{UUID_D1}`", "LIVE · 2026-10-02T00:00:00Z · its log is RepoD-1.md"),
    _row("repoW-1", f"`{UUID_W1}`", "LIVE · 2026-10-02T00:00:00Z · its log has WORD lines"),
    "",
    f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T02:00:00Z, PR #7 into opensoft/repoA main",
    f"LANDED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T02:05:00Z, PR #7 into opensoft/repoA main → abc1234",
    f"HOLD — lane repoA-2 (Eagle), window w, 2026-10-01T03:00:00Z: opensoft/repoA main {TIP_A} for a frozen window",
    f"HOLD (refresh) — lane repoA-2 (Eagle), window w, 2026-10-01T03:10:00Z: opensoft/repoA main {TIP_A}",
    "HOLD (run id) — lane repoA-2 (Eagle), window w, 2026-10-01T03:11:00Z: opensoft/repoA main run 4242",
    f"HOLD RELEASED — lane repoA-2 (Eagle), 2026-10-01T03:30:00Z: opensoft/repoA main {TIP_A}",
    f"HOLD — lane repoA-1 (Eagle), window w, 2026-10-01T03:35:00Z: opensoft/repoB main {TIP_A} for a check",
    "HOLD WITHDRAWN — lane repoA-1 (Eagle), 2026-10-01T03:40:00Z: opensoft/repoB main",
    f"HOLD — lane repoA-1 (Eagle), window w, 2026-10-01T03:42:00Z: opensoft/repoX main {TIP_A} for a check",
    "HOLD EXPIRED — lane repoA-1 (Eagle), 2026-10-01T03:45:00Z: opensoft/repoX main",
    "QUEUED-HOLD — lane repoA-2 (Eagle), 2026-10-01T03:50:00Z: opensoft/repoB main",
    f"LANDING WITHDRAWN — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T03:55:00Z, PR #8 into opensoft/repoA main",
    f"LANDING — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T04:00:00Z, PR #9 into opensoft/repoE main",
    f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T04:01:00Z, PR #10 into OpenSoft/RepoE main",
    f"LANDED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T04:05:00Z, PR #10 into OpenSoft/RepoE main → def5678",
    TAKE_LINES["hold-no-utc"],
    TAKE_LINES["landing-no-utc"],
    TAKE_LINES["bad-stamp"],
    EXPIRED_NO_HOLDER,
    "",
])

#: THE `main_slots` CASE'S OWN LINES (T211g; lane 3, #165 comment 6771569269,
#: and T211's text at B12b :1917): a `LANDED` naming no repository, in the
#: real register's form (its verb, lane, UTC, PR and merge sha, with no
#: `into <repository> main`), after its lane's `LANDING`s for one PR on two
#: repositories. Files mode's Rule 6 pairs it by lane and PR alone and closes
#: the newer `LANDING` still open, opensoft/repoG's, so opensoft/repoF's
#: stays open (`RULE6_AWK`, R24); lane 3 rules that `main_slots` pairs it
#: the same way. Committed on C by that case alone, since before lane 1's
#: T112 follow-up the import of such a line ends 23514 and loads nothing.
EM, ARROW = chr(0x2014), chr(0x2192)
REPOLESS_LANDED = [
    f"LANDING {EM} lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T05:10:00Z, PR #16 into "
    f"opensoft/repoF main",
    f"LANDING {EM} lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T05:11:00Z, PR #16 into "
    f"opensoft/repoG main",
    f"LANDED {EM} lane repoA-1, 2026-10-01T05:15:00Z, PR #16 {ARROW} "
    f"5f16a5f16a5f16a5f16a5f16a5f16a5f16a5f16a",
]

#: `WORD` lines whose UTC carries milliseconds (Q4(d)(i)): kept verbatim, and
#: flagged.
WORD_LINES = [
    f"NOTED — lane repoW-1, session {UUID_W1}@Eagle, 2026-10-02T00:10:00.123Z, lane:repoW-1 — a stamp with milliseconds",
    f"NOTED — lane repoW-1, session {UUID_W1}@Eagle, 2026-10-02T00:11:00.456Z, lane:repoW-1 — another",
]

#: C's files, before the `lanes-edit.sh` write on top. `lanes/repos.tsv` and
#: `lanes/log/README.md` are outside the render set (Q18 (A)).
SEED = {
    "lanes/LANES.md": REGISTER_TEXT,
    "lanes/log/README.md": "# the object logs\n",
    "lanes/repos.tsv": "# alias\towner/repo\nrepoE\topensoft/repoE\n",
    "lanes/log/repoA-1.md": "\n".join([
        "# lane repoA-1 — object log (lane-collision-protocol Amendment 7)",
        f"STARTED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:00:00Z, lane:repoA-1 → home opensoft/repoA; dir /work/repoA1; profile team-01a",
        f"OPENED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T01:30:00Z, opensoft/repoA#7",
        ""]),
    "lanes/log/repoA-2.md": "\n".join([
        "# lane repoA-2 — object log (lane-collision-protocol Amendment 7)",
        f"STARTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T02:00:00Z, lane:repoA-2 → home opensoft/repoA; dir /work/repoA2; profile team-01b",
        ""]),
    "lanes/log/repoB-1.md": "\n".join([
        "# lane repoB-1 — object log (lane-collision-protocol Amendment 7)",
        f"STARTED — lane repoB-1, session {UUID_B1}@Eagle, 2026-10-01T00:30:00Z, lane:repoB-1 → home opensoft/repoB; dir /work/repoB; profile team-02a",
        ""]),
    "lanes/log/RepoD-1.md": "\n".join([
        "# lane repoD-1 — object log (lane-collision-protocol Amendment 7)",
        f"STARTED — lane repoD-1, session {UUID_D1}@Eagle, 2026-10-02T00:00:00Z, lane:repoD-1 → home opensoft/repoD; dir /work/repoD",
        "a line no parser reads, in a log whose name differs from its lane's in case",
        ""]),
    "lanes/log/repoW-1.md": "\n".join([
        "# lane repoW-1 — object log (lane-collision-protocol Amendment 7)",
        f"STARTED — lane repoW-1, session {UUID_W1}@Eagle, 2026-10-02T00:00:00Z, lane:repoW-1 → home opensoft/repoW; dir /work/repoW",
        *WORD_LINES,
        ""]),
    "lanes/aliases.tsv": "# old\tnew\tutc\nrepoOld-1\trepoA-2\t2026-09-30T00:00:00Z\n",
    "lanes/archive/LANES-retired.md": "\n".join([
        "# retired rows (Amendment 19(d))", "",
        _row("repoZ-1", f"`{UUID_Z1}`", "RETIRED · 2026-09-02T00:00:00Z · retired"),
        ""]),
}

#: The render set (Q18 (A); CLI4.10 section 3.6): `lanes/LANES.md`,
#: `lanes/aliases.tsv`, each `lanes/log/<lane>.md` but the README, and the
#: archive. `lanes/STORE` joins it at the cutover, which T272 tests.
RENDER_SET = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|archive/[^/]+\.md"
                        r"|log/(?!README\.md$)[^/]+\.md)$")

#: One of each text `append-line` refuses on primary (CLI4.10 section 3.5,
#: "Why"), for the parity test.
REFUSED_ON_PRIMARY = {
    "hand-typed-landing-expired": f"LANDING EXPIRED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T05:00:00Z, for lane repoA-1, PR #11 into opensoft/repoL main",
    "take-no-utc": f"HOLD — lane repoA-2 (Eagle), window w: opensoft/repoT main {TIP_A} for a check",
    "take-no-repository": "HOLD — lane repoA-2 (Eagle), window w, 2026-10-01T03:00:00Z: for a frozen window",
    "landing-lane-unread": f"LANDING — session {UUID_A1}@Eagle, 2026-10-01T02:00:00Z, PR #13 into opensoft/repoA main",
}

#: Stamps that cannot be a time (lane 1's reading 2, F9b NOTES question 31)
#: and a CR inside a line: the parity holds on these too.
PARITY_EDGES = [
    f"HOLD — lane repoA-2 (Eagle), window w, 2026-10-01T24:00:00Z: opensoft/repoA main {TIP_A}",
    f"HOLD — lane repoA-2 (Eagle), window w, 2026-10-01T10:60Z: opensoft/repoA main {TIP_A}",
    f"HOLD — lane repoA-2 (Eagle), window w, 2026-10-01T10:00:60Z: opensoft/repoA main {TIP_A}",
    f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, 2026-02-30T10:00:00Z, PR #14 into opensoft/repoA main",
    f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, 0000-01-01T10:00Z, PR #15 into opensoft/repoA main",
    f"HOLD — lane repoA-2 (Eagle), 2026-10-01T03:00:00Z: opensoft/repoA main\rcarried on after a CR",
]

#: The S3 reads the import's proof answers the same from the files and from
#: SQL (AT-7, "Oracle"), with each one's arguments for a lane.
READS = {
    "who": lambda lane: ["who", "--lane", lane],
    "binding": lambda lane: ["binding", lane],
    "live-holder": lambda lane: ["live-holder", lane],
    "next-free": lambda lane: ["next-free", lane.split("-", 1)[0]],
    "lane-last": lambda lane: ["lane-last", lane],
    "register-row": lambda lane: ["register-row", lane],
    "session-lane": lambda lane: ["session-lane", LANES[lane]],
    "canon-lane": lambda lane: ["canon-lane", lane],
    "resolve-home": lambda lane: ["resolve-home", lane],
    "managed-projection": lambda lane: ["managed-projection", lane],
}

HEX = re.compile(r"[0-9a-f]{7,}")
UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2})?Z")
AGE = re.compile(r"\b[0-9]+h [0-9]{2}m\b|\b[0-9]+[smhd] ago\b")


#: THE PATH MASK (lane 2's rule for wave 11, "mask, never drop"): the names
#: no directory of the caller's `PATH` may offer a case. This helper once
#: dropped each directory holding a `lanes-index`; it now masks that name,
#: and every name that starts `pg_`, the client wrappers postgresql-16's
#: package puts in `/usr/bin` beside `psql`.
MASKED_NAMES = ("lanes-index",)
MASKED_PREFIX = "pg_"
#: {a directory's real path: its mirror, or None where it holds no masked
#: name}, filled once a process.
_MIRRORS: dict = {}
#: The one `l2-pathmask-` directory the mirrors live in, made on first need
#: and removed at exit.
_MASK_ROOT: list = []


def _is_masked(name: str) -> bool:
    return name in MASKED_NAMES or name.startswith(MASKED_PREFIX)


def _mirror(directory: str):
    """`directory`'s private mirror, or None where it holds no masked name
    or cannot be listed: a directory of symlinks, one per entry, each to the
    entry's absolute path, the masked names left out. Built once a process,
    cached by the directory's real path."""
    real = os.path.realpath(directory)
    if real in _MIRRORS:
        return _MIRRORS[real]
    try:
        names = os.listdir(real)
    except OSError:
        names = []
    mirror = None
    if any(_is_masked(name) for name in names):
        if not _MASK_ROOT:
            _MASK_ROOT.append(tempfile.mkdtemp(prefix="l2-pathmask-"))
            atexit.register(shutil.rmtree, _MASK_ROOT[0], True)
        mirror = os.path.join(_MASK_ROOT[0], str(len(_MIRRORS)))
        os.mkdir(mirror)
        for name in names:
            if not _is_masked(name):
                os.symlink(os.path.join(real, name), os.path.join(mirror, name))
    _MIRRORS[real] = mirror
    return mirror


def _masked_path() -> str:
    """The caller's PATH with every directory kept, in its place, and each
    one that holds a masked name swapped for its mirror (`_mirror`), so an
    installed indexer is never what a case runs. A directory is never
    dropped: a GitHub runner's `/usr/bin` holds `psql`, `git` and `bash`
    together (postgresql-16's client package; `/bin` is a link to it), so
    dropping a directory for one name it holds drops `git` and `bash` with
    it (lane 1's census, #165 comment 6807454856). A directory that holds no
    masked name passes through unchanged."""
    return os.pathsep.join(_mirror(part) or part
                           for part in os.environ.get("PATH", "").split(os.pathsep) if part)


def load_indexer():
    """`lanes-index` as a module, fresh, as `test_lanes_index.py`'s
    `load_indexer` loads it. Called inside a test, never at import."""
    import importlib.util
    loader = SourceFileLoader("lanes_index_import_module", str(INDEXER))
    spec = importlib.util.spec_from_loader("lanes_index_import_module", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _lines(data: bytes) -> list:
    """A file's lines as `register classify` cuts its stdin: at LF alone, a
    last line with no LF kept, and nothing for an empty file."""
    parts = data.split(b"\n")
    if parts[-1] == b"":
        parts.pop()
    return parts


def _utc_epoch(utc) -> str:
    """CLI4.10 section 3.5's `<utc_ts>`: the stamp as epoch seconds, or `-`
    where it is missing or cannot be a time."""
    if not utc:
        return "-"
    fmt = "%Y-%m-%dT%H:%M:%SZ" if utc.count(":") == 2 else "%Y-%m-%dT%H:%MZ"
    try:
        stamp = datetime.datetime.strptime(utc, fmt)
    except ValueError:
        return "-"
    return str(int(stamp.replace(tzinfo=datetime.timezone.utc).timestamp()))


def _normal(text: str, *roots: Path) -> str:
    """What is the clock's or the temporary directory's, not the read's."""
    for root in roots:
        text = text.replace(str(root), "<ROOT>")
    return HEX.sub("<HEX>", AGE.sub("<AGE>", UTC.sub("<UTC>", text)))


class Workspace:
    """A whole files-mode workspace in `root`: a bare origin, its clone, the
    pointer file that joins them, a fake `tmux`, and the environment every
    command here runs in, as `test_lanes_index.py`'s `Estate` has them.
    `files` is committed and pushed by git alone, so two paths one case
    apart stay two files on a case-insensitive disk."""

    def __init__(self, root: Path, files: dict):
        self.root = root
        self.home = root / "home"
        self.agents = self.home / ".agents"
        self.origin = root / "origin.git"
        self.wip = self.home / "projects" / "wip"
        self.fakebin = root / "fakebin"
        self.conf = root / "conf"
        for d in (self.home, self.agents, self.fakebin, self.conf, root / "state",
                  root / "config", root / "tmp"):
            d.mkdir(parents=True, exist_ok=True)
        (self.fakebin / "tmux").write_text("#!/bin/sh\nexit 1\n")
        (self.fakebin / "tmux").chmod(0o755)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("LANES_", "CLAUDE_", "WORKBENCHES_", "TMUX", "XDG_", "PG",
                                    "AGENT_PROTOCOL_ROOT", "PROJECTS_"))}
        env.update(
            HOME=str(self.home), AGENT_PROTOCOL_ROOT=str(self.agents), TMPDIR=str(root / "tmp"),
            XDG_STATE_HOME=str(root / "state"), XDG_CONFIG_HOME=str(root / "config"),
            CLAUDE_CONFIG_DIR=str(self.home / ".claude"), LANES_WORKSTATION="Eagle",
            LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none",
            LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1", LANES_EDIT=str(LANES_EDIT),
            GIT_AUTHOR_NAME="lanes-index tests", GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_NAME="lanes-index tests", GIT_COMMITTER_EMAIL="test@example.invalid",
            PATH=str(self.fakebin) + os.pathsep + _masked_path())
        self.env = env
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)],
                       check=True, env=self.env)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.wip)],
                       check=True, env=self.env, capture_output=True)
        self.commit(files, "seed the register")
        # AMENDMENT 23 S5, as `Estate` sets it up: W is a view of the clone,
        # and the writes name the clone by `LANES_REPO`.
        self.ws = root / "ro" / "wip"
        self.ws.mkdir(parents=True)
        (self.ws / ".git").write_text(f"gitdir: {os.path.realpath(self.wip / '.git')}\n",
                                      encoding="utf-8")
        (self.ws / "lanes").symlink_to(self.wip / "lanes")
        (self.agents / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.ws}\n", encoding="utf-8")
        self.env["LANES_REPO"] = str(self.wip)

    def git(self, *args: str, input_bytes: bytes | None = None) -> str:
        proc = subprocess.run(["git", *args], cwd=str(self.wip), capture_output=True,
                              input=input_bytes, env=self.env, check=False)
        assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr.decode(errors='replace')}"
        return proc.stdout.decode("utf-8", "replace")

    def commit(self, files: dict, message: str, *, push: bool = True) -> str:
        """Commit `files` ({path: str or bytes, or None to remove}) through
        git alone, push it unless told not to, and return the commit."""
        for path, text in files.items():
            if text is None:
                self.git("rm", "-q", "--cached", "--", path)
                continue
            data = text.encode("utf-8") if isinstance(text, str) else text
            sha = self.git("hash-object", "-w", "--stdin", input_bytes=data).strip()
            self.git("-c", "core.ignorecase=false", "update-index", "--add", "--cacheinfo",
                     f"100644,{sha},{path}")
        self.git("-c", "core.ignorecase=false", "commit", "-q", "-m", message)
        if push:
            self.git("push", "-q", "origin", "main")
        self.git("-c", "core.ignorecase=false", "checkout", "-q", "-f", "HEAD")
        return self.git("rev-parse", "HEAD").strip()

    def run(self, *argv, env: dict | None = None, input_text: str | None = None,
            timeout: float = 120, cwd: Path | None = None) -> subprocess.CompletedProcess:
        child = dict(self.env)
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True,
                              env=child, timeout=timeout, cwd=str(cwd or self.root),
                              input=input_text,
                              stdin=None if input_text is not None else subprocess.DEVNULL)

    def edit(self, *args, env: dict | None = None, **kw) -> subprocess.CompletedProcess:
        return self.run("bash", LANES_EDIT, *args, env=env, **kw)

    def tip(self) -> str:
        return self.git("rev-parse", "origin/main").strip()

    def tree(self, sha: str, path: str = "lanes") -> str:
        return self.git("rev-parse", f"{sha}:{path}").strip()

    def blob(self, sha: str, path: str) -> bytes:
        proc = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=str(self.wip),
                              capture_output=True, env=self.env, check=True)
        return proc.stdout

    def paths(self, sha: str) -> list:
        return [p for p in self.git("ls-tree", "-r", "--name-only", sha, "--", "lanes/").splitlines()
                if p]

    def rendered(self, sha: str) -> dict:
        """C's render set, {path: bytes}."""
        return {p: self.blob(sha, p) for p in self.paths(sha) if RENDER_SET.match(p)}


class FixtureRegister(Workspace):
    """AT-7's fixture register at C: `SEED`, then a `lanes-edit.sh log NOTED`
    write as the operator lane, so C's tip is bytes the files-mode verbs
    wrote."""

    def __init__(self, root: Path):
        super().__init__(root, SEED)
        proc = self.edit("log", "NOTED", f"lane:{OPERATOR}", "the import's fixture, at C",
                         env={"LANES_LANE": OPERATOR})
        assert proc.returncode == 0, f"lanes-edit.sh log NOTED: {proc.stdout}{proc.stderr}"
        self.c = self.tip()

    def config(self, pg) -> Path:
        """The operator's configuration (CLI4.10 section 2.5): `mode=index`,
        the register's two URLs on the cluster's Unix socket, a private
        password file each, and `register_label=`. Outside every work tree,
        mode 0600."""
        passfile = self.conf / "pgpass"
        passfile.write_text("", encoding="utf-8")
        passfile.chmod(0o600)
        path = self.conf / "lanes-index.conf"
        path.write_text("\n".join([
            "mode=index",
            f"register_url={pg.url()}",
            f"register_passfile={passfile}",
            f"reader_url={pg.url()}",
            f"reader_passfile={passfile}",
            f"register_label={LABEL}",
            f"register_schema={SCHEMA}",
            ""]), encoding="utf-8")
        path.chmod(0o600)
        return path

    def import_at(self, pg, sha: str, *, config: Path | None = None) -> subprocess.CompletedProcess:
        """`lanes-index import --at <sha>`, as the operator lane through its
        checkout. #160's run-wide `LANES_INDEX=off` is not this command's."""
        return self.run(sys.executable, INDEXER, "import", "--at", sha, cwd=self.wip,
                        timeout=400,
                        env={"LANES_INDEX_CONFIG": str(config or self.config(pg)),
                             "LANES_LANE": OPERATOR, "LANES_INDEX": None})


def _rows(pg, sql: str) -> list:
    """`sql`'s rows as JSON objects, read in the register's schema. By
    `jsonb_agg`, whose text is one line: `json_agg` puts a line break
    between its elements, so a last-line read of it fails on two rows."""
    out = pg.psql(f"SET search_path TO {SCHEMA};\n"
                  f"SELECT coalesce(jsonb_agg(t), '[]'::jsonb) FROM ({sql}) t;\n").stdout
    return json.loads(out.strip().splitlines()[-1])


def _count(pg, table: str) -> int:
    return _rows(pg, f"SELECT count(*) AS n FROM {table}")[0]["n"]


def _state(pg) -> dict:
    """What a refused import must leave as it was: the journal and every
    table's rows, by count, and the seq-0 row."""
    tables = ("journal", "journal_files", "files", "doc_lines", "lanes", "log_lines",
              "register_lines", "object_holds")
    state = {t: _count(pg, t) for t in tables}
    state["seq0"] = _rows(pg, "SELECT seq, write_id, git_commit, git_tree FROM journal "
                              "WHERE seq = 0")
    return state


def _renders(pg) -> dict:
    """SQL's own render (lane 1's T107, `render_file`) of every path in
    `files`, {path: bytes}."""
    return {r["path"]: base64.b64decode(r["b64"]) for r in _rows(
        pg, "SELECT path, encode(render_file(path), 'base64') AS b64 FROM files ORDER BY path")}


def _git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _records(reg: Workspace, sha: str) -> dict:
    """The register's records as the files give them at `sha`: #160's
    `build_records` over `read_snapshot`, in process (code/lanes-index:765)."""
    mod = load_indexer()
    return mod.build_records(mod.read_snapshot(str(reg.wip), sha))


def _row_lanes(reg: Workspace, sha: str) -> set:
    """The lanes a row names at `sha`, case-folded: `row_name` over every
    line of `lanes/LANES.md` and of each file under `lanes/archive/`. The
    design keeps "one row per lane, LANES.md and archive/ together", so a
    lane with a row in both has one, and a lane with a log and no row has
    none (design.md, the `lanes` table and "Why the text"; step 7)."""
    mod = load_indexer()
    names = set()
    for path, data in reg.rendered(sha).items():
        if path == "lanes/LANES.md" or path.startswith("lanes/archive/"):
            for line in data.decode("utf-8").split("\n"):
                name = mod.row_name(line)
                if name:
                    names.add(name.lower())
    return names


def _assert_proved(reg: FixtureRegister, pg, sha: str) -> None:
    """The import's oracle at `sha` (AT-7, "Success"): seq 0 holds the
    commit, its `lanes` tree id and the digests; each table's count equals
    the files'; every rendered path's blob id equals the commit's. The
    `lanes` count is the lanes a row names (`_row_lanes`), not
    `build_records`' records, which hold a lane with a log and no row too."""
    seq0 = _rows(pg, "SELECT kind, git_commit, git_tree FROM journal WHERE seq = 0")
    assert seq0 == [{"kind": "import", "git_commit": sha, "git_tree": reg.tree(sha)}], seq0
    rendered = reg.rendered(sha)
    digests = {r["path"]: r["sha256"] for r in _rows(
        pg, "SELECT path, sha256 FROM journal_files WHERE seq = 0 AND present")}
    assert digests == {p: hashlib.sha256(b).hexdigest() for p, b in rendered.items()}
    records = _records(reg, sha)
    assert _count(pg, "lanes") == len(_row_lanes(reg, sha)), "lanes' count: the lanes a row names"
    for table in ("log_lines", "register_lines"):
        assert _count(pg, table) == len(records[table]), f"{table}'s count"
    assert _count(pg, "files") == len(rendered)
    renders = _renders(pg)
    assert {p: _git_blob_id(b) for p, b in renders.items()} == \
        {p: reg.git("rev-parse", f"{sha}:{p}").strip() for p in rendered}


# ============================================================ the parity (R04)

def test_register_classify_parity_holds_on_every_line(tmp_path):
    """R04 (CLI4.10 section 3.5; R-F9-9): the five fields, `<kind>`,
    `<slot_role>`, `<repo_key>`, `<utc_ts>` and `<lane>`, from `register
    classify` by argv and stdin, equal the in-process side on every line of
    the fixture register's render set at C and on one of each text
    `append-line` refuses on primary. The in-process side is the regex's
    kind, `REGISTER_SLOTS`' role, and `parse_register_line`'s repository,
    UTC and lane, with `-` for each that is absent."""
    reg = FixtureRegister(tmp_path / "e")
    feed = []
    for path, data in sorted(reg.rendered(reg.c).items()):
        feed += [(f"{path}:{n}", raw) for n, raw in enumerate(_lines(data), 1)]
    feed += [(f"refused:{name}", text.encode("utf-8")) for name, text in REFUSED_ON_PRIMARY.items()]
    feed += [(f"edge:{n}", text.encode("utf-8")) for n, text in enumerate(PARITY_EDGES, 1)]
    stdin = b"".join(raw + b"\n" for _, raw in feed)
    proc = subprocess.run([sys.executable, str(INDEXER), "register", "classify"], input=stdin,
                          capture_output=True, env=reg.env, cwd=str(reg.root), timeout=120)
    assert proc.returncode == 0, (f"`lanes-index register classify` exited {proc.returncode}: "
                                  f"{proc.stderr.decode(errors='replace')}")
    answered = proc.stdout.decode("utf-8").split("\n")
    assert answered[-1] == "", "the answer's last line is not LF-ended"
    answered = answered[:-1]
    assert len(answered) == len(feed), "one line out for each line in"
    mod = load_indexer()
    compared = 0
    for (where, raw), out in zip(feed, answered):
        line = raw.decode("utf-8", "replace")
        m = mod.REGISTER_KIND_RE.match(line)
        kind = m.group(1) if m else "-"
        role = (mod.REGISTER_SLOTS[kind][0] or "-") if m else "-"
        fields = mod.parse_register_line(line) or {}
        expected = (kind, role, fields.get("repo") or "-", _utc_epoch(fields.get("utc")),
                    fields.get("lane") or "-")
        assert tuple(out.split("\t")) == expected, f"{where}: {line!r}"
        compared += 1
    assert compared == len(feed) and compared > 0
    kinds = {out.split("\t")[0] for out in answered}
    assert {"HOLD (refresh)", "HOLD (run id)", "HOLD WITHDRAWN", "HOLD EXPIRED", "QUEUED-HOLD",
            "LANDING WITHDRAWN", "LANDING EXPIRED"} <= kinds, "the fixture's kinds were fed"


# ======================================================= the import (real engine)

#: Two lines that are no difference (AT-7, "Success"; lane 3's batches 9 and
#: 11 (4), #165 comments 6781033556 and 6783909985): a line's text bars only
#: `\n` and `\r` (design.md:1181), and each line is stored as it stands
#: (:1176, :1467) and rendered back unchanged (:1300-1304), so a commit on C
#: holding either one imports with exit 0 and the proof holds.
#: {id: (path, a function of C's text giving that commit's)}.
NO_DIFFERENCE = {
    "trailing-blank": ("lanes/LANES.md", lambda text: text.replace(
        "· the operator lane |\n", "· the operator lane | \n", 1)),
    "unknown-kind": ("lanes/LANES.md", lambda text: text + (
        "HOLD REQUESTED — lane repoA-2 (Eagle), 2026-10-01T06:00:00Z: opensoft/repoA main\n")),
}


@pytest.mark.parametrize("case", ["at-c", *NO_DIFFERENCE])
def test_import_at_a_commit_proves_a_byte_identical_render(pg, tmp_path, case):
    """The import exits 0; seq 0 holds the commit's sha, its `lanes` tree id
    and the digests; each table's count equals the files'; every rendered
    path's blob id equals the commit's (AT-7, "Success"; R3's three-part
    proof). `[at-c]` imports C itself; `[trailing-blank]` and
    `[unknown-kind]` each import a commit on C whose `lanes/LANES.md`
    holds one line that is no difference (`NO_DIFFERENCE`)."""
    reg = FixtureRegister(tmp_path / "e")
    sha = reg.c
    if case in NO_DIFFERENCE:
        path, change = NO_DIFFERENCE[case]
        good = reg.blob(reg.c, path)
        changed = change(good.decode("utf-8")).encode("utf-8")
        assert changed != good, f"{case}: the change found no line of {path} to change"
        sha = reg.commit({path: changed}, f"C with {case}")
    proc = reg.import_at(pg, sha)
    assert proc.returncode == 0, proc.stderr
    _assert_proved(reg, pg, sha)


#: C' differs from C in the one way the renderer cannot reproduce (AT-7, "The
#: difference"): a CRLF line ending, since a line's text holds no `\r`
#: (design.md:1181; lane 3's batch 11 (4)). The two lines once listed here
#: beside it are `NO_DIFFERENCE`'s. {id: (path, a function of C's text giving
#: C's')}.
DIFFERENCES = {
    "crlf": ("lanes/log/repoA-2.md", lambda text: text.replace("\n", "\r\n", 1)),
}


@pytest.mark.parametrize("difference", list(DIFFERENCES))
def test_import_refuses_on_a_difference_and_loads_nothing(pg, tmp_path, difference):
    """C' is refused with the design's code, its stderr naming the first
    differing path, and nothing is loaded: no seq 0 on an empty register,
    and the previous import's seq 0 and tables unchanged after one. Once C'
    is fixed, a re-run succeeds (AT-7, "Refusal")."""
    reg = FixtureRegister(tmp_path / "e")
    refused = load_indexer().EXIT_IMPORT_REFUSED
    path, change = DIFFERENCES[difference]
    good = reg.blob(reg.c, path)
    bad = change(good.decode("utf-8")).encode("utf-8")
    assert bad != good
    c_bad = reg.commit({path: bad}, f"C': {difference}")
    empty = _state(pg)
    proc = reg.import_at(pg, c_bad)
    assert proc.returncode == refused, proc.stderr
    assert path in proc.stderr, f"stderr names {path}: {proc.stderr}"
    assert _state(pg) == empty and not empty["seq0"], "an empty register stays empty"
    c_fixed = reg.commit({path: good}, "C' fixed")
    proc = reg.import_at(pg, c_fixed)
    assert proc.returncode == 0, proc.stderr
    _assert_proved(reg, pg, c_fixed)
    loaded = _state(pg)
    c_bad_again = reg.commit({path: bad}, f"C' again: {difference}")
    proc = reg.import_at(pg, c_bad_again)
    assert proc.returncode == refused, proc.stderr
    assert path in proc.stderr, f"stderr names {path}: {proc.stderr}"
    assert _state(pg) == loaded, "the previous import's seq 0 and tables are unchanged"


@pytest.mark.parametrize("read", list(READS))
def test_import_answers_every_read_as_the_files_do(pg, tmp_path, read):
    """For every lane, the S3 read answers the same from the files at C as
    from SQL: stdout, the exit code, and stderr less its `read:` lines, the
    `unreadable:` warnings included (AT-7, "Success"). SQL's side is SQL's
    own render of every path in `files`, with C's files outside the render
    set beside it, in a workspace of its own."""
    reg = FixtureRegister(tmp_path / "e")
    proc = reg.import_at(pg, reg.c)
    assert proc.returncode == 0, proc.stderr
    renders = _renders(pg)
    assert set(renders) == set(reg.rendered(reg.c))
    outside = {p: reg.blob(reg.c, p) for p in reg.paths(reg.c) if not RENDER_SET.match(p)}
    sql = Workspace(tmp_path / "s", {**renders, **outside})
    rows = reg.blob(reg.c, "lanes/LANES.md").decode("utf-8")
    for lane in LANES:
        argv = READS[read](lane)
        stdin = rows if read == "next-free" else None
        answers = []
        for ws in (reg, sql):
            got = ws.edit(*argv, env={"LANES_LANE": OPERATOR}, input_text=stdin)
            err = "\n".join(l for l in got.stderr.splitlines() if not l.startswith("read:"))
            answers.append((got.returncode, _normal(got.stdout, ws.root),
                            _normal(err, ws.root)))
        assert answers[0] == answers[1], f"{read} for {lane}: files {answers[0]!r}, SQL {answers[1]!r}"


def test_a_reimport_replaces_seq_0(pg, tmp_path):
    """A second import replaces seq 0, and the counts are unchanged (AT-7,
    "Re-import"; P1283-1286)."""
    reg = FixtureRegister(tmp_path / "e")
    assert reg.import_at(pg, reg.c).returncode == 0
    first = _state(pg)
    proc = reg.import_at(pg, reg.c)
    assert proc.returncode == 0, proc.stderr
    second = _state(pg)
    assert _rows(pg, "SELECT seq FROM journal ORDER BY seq") == [{"seq": 0}]
    assert [(r["git_commit"], r["git_tree"]) for r in second["seq0"]] == \
        [(reg.c, reg.tree(reg.c))]
    assert {k: v for k, v in second.items() if k != "seq0"} == \
        {k: v for k, v in first.items() if k != "seq0"}
    _assert_proved(reg, pg, reg.c)


def test_word_lines_with_milliseconds_import_verbatim_and_flagged(pg, tmp_path):
    """`WORD` lines whose UTC carries milliseconds are kept verbatim and
    carry the design's flag, an unreadable log line (7(b); Q4(d)(i)), and
    their file renders byte-identically (AT-7, "`WORD` lines")."""
    reg = FixtureRegister(tmp_path / "e")
    proc = reg.import_at(pg, reg.c)
    assert proc.returncode == 0, proc.stderr
    rows = _rows(pg, "SELECT raw, unreadable, unreadable_why FROM log_lines "
                     "WHERE file = 'lanes/log/repoW-1.md' ORDER BY ordinal")
    for line in WORD_LINES:
        found = [r for r in rows if r["raw"] == line]
        assert len(found) == 1, f"kept verbatim: {line!r}"
        assert found[0]["unreadable"] is True and found[0]["unreadable_why"], f"flagged: {line!r}"
    assert _renders(pg)["lanes/log/repoW-1.md"] == reg.blob(reg.c, "lanes/log/repoW-1.md")


def test_import_reads_origin_only_and_never_a_local_line(pg, tmp_path):
    """The operator's clone holds one local, unpushed line; the import of
    origin's C loads origin's text, and the local line is absent from SQL
    (AT-7, "Origin only"; Q4(c)(i))."""
    reg = FixtureRegister(tmp_path / "e")
    local = f"NOTED — lane {OPERATOR}, session {UUID_A2}@Eagle, 2026-10-03T00:00:00Z, lane:{OPERATOR} — a local line, never pushed"
    log = f"lanes/log/{OPERATOR}.md"
    reg.commit({log: reg.blob(reg.c, log) + local.encode("utf-8") + b"\n"}, "a local line",
               push=False)
    assert reg.tip() == reg.c
    proc = reg.import_at(pg, reg.c)
    assert proc.returncode == 0, proc.stderr
    assert _rows(pg, f"SELECT line_id FROM doc_lines WHERE text = '{local}'") == []
    assert _rows(pg, f"SELECT line_id FROM log_lines WHERE raw = '{local}'") == []
    assert _renders(pg)[log] == reg.blob(reg.c, log)
    _assert_proved(reg, pg, reg.c)


@pytest.mark.parametrize("case", ["hold-no-utc", "landing-no-utc", "bad-stamp",
                                  "expired-no-holder"])
def test_import_loads_takes_with_no_readable_utc_and_a_holderless_landing_expired_as_they_stand(
        pg, tmp_path, case):
    """Each take with no readable UTC loads as a take with a NULL `utc_ts`,
    and the import is not refused for it; the line in the `LANDING EXPIRED`
    shape with no `for lane` is a line of no kind, with no slot role, that
    releases nothing. A re-import loads them the same way (AT-7, "Takes
    with no UTC, and a release with no holder"; U3; F13).

    A line of no kind is loaded as text: one `doc_lines` line in
    `lanes/LANES.md`, and no `register_lines` row, since the import makes a
    row only for a line of a kind (design.md:1412 at spec#17 `8523aa0c`:
    "an import loads it as text instead of failing on it";
    test-plan.md:1447-1453; lane 1's triage, group 3, #165 comment
    6807494089). `main_slots` still lists repoA-2's open `LANDING` of PR #9
    on opensoft/repoE, the take the line names."""
    reg = FixtureRegister(tmp_path / "e")
    line = EXPIRED_NO_HOLDER if case == "expired-no-holder" else TAKE_LINES[case]
    quoted = "'" + line.replace("'", "''") + "'"
    loads = []
    for _ in range(2):
        proc = reg.import_at(pg, reg.c)
        assert proc.returncode == 0, proc.stderr
        rows = _rows(pg, "SELECT kind, slot_role, slot_kind, utc_ts, for_lane FROM "
                         "register_lines WHERE raw = " + quoted)
        if case == "expired-no-holder":
            as_text = _rows(pg, "SELECT path FROM doc_lines WHERE text = " + quoted)
            assert as_text == [{"path": "lanes/LANES.md"}], f"loaded once, as text: {line!r}"
            assert rows == [], f"a line of no kind has no register_lines row: {rows!r}"
            open_e = _rows(pg, "SELECT lane, pr FROM main_slots WHERE slot_kind = 'landing' "
                               "AND lower(repo_key) LIKE '%repoe'")
            assert open_e == [{"lane": "repoA-2", "pr": 9}], "it releases nothing"
            row = {"doc_lines": as_text, "register_lines": rows, "open": open_e}
        else:
            assert len(rows) == 1, f"loaded once, as it stands: {line!r}"
            row = rows[0]
            assert (row["slot_role"], row["utc_ts"]) == ("take", None)
        loads.append(row)
    assert loads[0] == loads[1], "a re-import loads it the same way"


def _rule6_open(reg: Workspace, sha: str) -> list:
    """Files mode's Rule 6 pairing over C's `lanes/LANES.md`, by
    `lanes-edit.sh`'s own `RULE6_AWK`: the takes it leaves open, each
    (lane, PR, repository lower-cased), in the order of the line that holds
    each, which is its place."""
    text = LANES_EDIT.read_text(encoding="utf-8")
    m = re.search(r"^RULE6_AWK='\n(.*?)'\n", text, re.S | re.M)
    assert m, "lanes-edit.sh no longer declares RULE6_AWK='…' the way this test reads it"
    register = reg.blob(sha, "lanes/LANES.md").decode("utf-8")
    proc = subprocess.run(["awk", m.group(1)], input=register, capture_output=True, text=True,
                          env=dict(reg.env, LANES_RULE6_ALIASES=""), check=True)
    open_takes = []
    for out in proc.stdout.splitlines():
        state, lane, pr, _utc, repo = out.split("\x1f")[:5]
        if state == "LANDING":
            open_takes.append((lane, int(pr), repo.lower()))
    order = {}
    for number, line in enumerate(register.split("\n"), 1):
        if line.startswith("LANDING — "):
            for take in open_takes:
                if (f"lane {take[0]}," in line and f"PR #{take[1]} " in line
                        and f"into {take[2]} main" in line.lower()):
                    order[take] = number
    return sorted(open_takes, key=lambda t: order[t])


def test_main_slots_pairing_equals_files_mode_rule_6_on_imported_history(pg, tmp_path):
    """On the imported fixture register, whose `LANDING` and `LANDED` lines
    name one repository under two spellings and close takes out of order,
    the open landing takes `main_slots` lists, with their places, equal
    those files mode's Rule 6 pairing leaves open on the same files (AT-7,
    "Tests"; lane 1's point 3, comment 6710770304).

    Its fixture also holds a `LANDED` naming no repository after its lane's
    `LANDING`s for one PR on two repositories (`REPOLESS_LANDED`, committed
    on C; T211g; lane 3, #165 comment 6771569269): Rule 6 closes the newer,
    opensoft/repoG's, and leaves opensoft/repoF's open, and `main_slots`
    must agree. It fails until lane 1's T112 follow-up, in T115's import:
    before it the import ends 23514 on migration 1's slot CHECKs and loads
    nothing (lane 1, 6771151979), and with lane 1's fix alone, no slot for
    the line, `main_slots` keeps both open; lane 3's pairing (6771569269,
    point 2) closes repoG's."""
    reg = FixtureRegister(tmp_path / "e")
    register = reg.blob(reg.c, "lanes/LANES.md") + "".join(
        f"{line}\n" for line in REPOLESS_LANDED).encode("utf-8")
    c = reg.commit({"lanes/LANES.md": register},
                   "a LANDED naming no repository after two LANDINGs of one PR")
    files = _rule6_open(reg, c)
    assert ("repoA-1", 16, "opensoft/repof") in files and \
        ("repoA-1", 16, "opensoft/repog") not in files, \
        f"Rule 6 closes the newer LANDING of the LANDED with no repository: {files}"
    proc = reg.import_at(pg, c)
    assert proc.returncode == 0, proc.stderr
    slots = _rows(pg, "SELECT lane, pr, lower(repo_key) AS repo, line_id FROM main_slots "
                      "WHERE slot_kind = 'landing' ORDER BY line_id")
    assert files, "the fixture leaves landings open"
    assert [(s["lane"], s["pr"]) for s in slots] == [(t[0], t[1]) for t in files]
    for s, t in zip(slots, files):
        assert s["repo"].endswith(t[2].split("/")[-1]), (s, t)


#: The verbs whose log line gives `bind:L` (design.md:1493 at spec#17
#: `8523aa0c`, the `bind:L` row: "a line of `lanes/log/L.md` whose verb ... is
#: `STARTED`, `RESUMED`, `PAUSED`, `ENDED`, `RETIRED` or `RENAMED`"), as SQL's
#: `line_scopes` gives it. A `NOTED`, `RULED` or `HANDOFF-REQUESTED` line on a
#: `lane:` object gives none (design.md:5666; test-plan.md:4983-4986; lane 1's
#: triage, group 2, #165 comment 6807494089).
BIND_VERBS = ("STARTED", "RESUMED", "PAUSED", "ENDED", "RETIRED", "RENAMED")


def _build_records_scopes(mod, path: str, text: str) -> set:
    """The scopes `build_records`' own reads give one line in Python (the
    test plan's S7 agreement test): a row's lane by `row_name` in
    `LANES.md` or the archive, an archived row's normalized key, a
    lane-kind log line's lane by `parse_log_line` in the log `file_lane`
    names, where its object is `lane:...` and its verb is one of
    `BIND_VERBS` (so the fixture's `NOTED` lines in `repoA-2` and
    `repoW-1` give no `bind:`), an alias line's first two fields, and
    every uuid `UUID_RE` finds."""
    scopes = set()
    if path in ("lanes/LANES.md", "lanes/archive/LANES-retired.md"):
        name = mod.row_name(text)
        if name:
            scopes.add(("archive:" if path.startswith("lanes/archive/") else "row:")
                       + name.lower())
            cells = text.split("|")
            if len(cells) > 2:
                scopes |= {"sid:" + u.lower() for u in mod.UUID_RE.findall(cells[2])}
    elif path == "lanes/aliases.tsv":
        if not text.startswith("#"):
            parts = text.split("\t")
            if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
                scopes |= {"alias:" + parts[0].strip().lower(), "alias:" + parts[1].strip().lower()}
    elif path.startswith("lanes/log/"):
        parsed = mod.parse_log_line(text)
        if (parsed and str(parsed.get("object", "")).startswith("lane:")
                and parsed.get("verb") in BIND_VERBS):
            scopes.add("bind:" + mod.file_lane(path).lower())
    return scopes


def test_line_scopes_agrees_with_build_records_rules_over_every_line_of_the_imported_register(
        pg, tmp_path):
    """S7's agreement test: for every line of `lanes/LANES.md`,
    `lanes/log/*.md`, `lanes/archive/**` and `lanes/aliases.tsv`, no scope
    the Python side gives is missing from `line_scopes(<path>, <text>)`'s.
    That is the whole assertion; it counts the lines compared, not 0, and
    records the extras by kind without asserting them (AT-7, "S7's
    agreement test")."""
    reg = FixtureRegister(tmp_path / "e")
    proc = reg.import_at(pg, reg.c)
    assert proc.returncode == 0, proc.stderr
    mod = load_indexer()
    lines = _rows(pg, "SELECT d.path, d.text, coalesce((SELECT json_agg(s) FROM "
                      "line_scopes(d.path, d.text) s), '[]'::json) AS scopes FROM doc_lines d "
                      "ORDER BY d.path, d.line_no")
    compared, extras = 0, {}
    for row in lines:
        python = _build_records_scopes(mod, row["path"], row["text"])
        sql = set(row["scopes"])
        assert not python - sql, f"{row['path']}: {row['text']!r} misses {sorted(python - sql)}"
        for scope in sql - python:
            extras[scope.split(":", 1)[0]] = extras.get(scope.split(":", 1)[0], 0) + 1
        compared += 1
    assert compared > 0
    print(f"line_scopes agreement: {compared} lines compared; extras by kind: "
          f"{json.dumps(extras, sort_keys=True)}")


#: The sidecar's three lanes (the phase plan's "Question 10"): {id: (lane,
#: the log file a warning names, or None for no log)}.
SIDECAR_CASES = {
    "unreadable-words": ("repoW-1", "lanes/log/repoW-1.md"),
    "case-differs": ("repoD-1", "lanes/log/RepoD-1.md"),
    "no-log": ("repoC-1", None),
}


def _to_primary(pg, reg: FixtureRegister, mod) -> None:
    """The imported register brought to `primary` with the marker `present`
    by AT-LR006's route (TP:4610-4615): `commit_write` with a `cutover`
    entry on the import's seq, then `record_marker`, by the documented
    functions. No `lanes-index cutover` runs."""
    gen = _rows(pg, "SELECT generation FROM register_switch")[0]["generation"]
    store = "".join(f"{k}={v}\n" for k, v in (
        ("store", "primary"), ("database", LABEL), ("import", reg.c),
        ("lanes-tree", reg.tree(reg.c)), ("utc", "2026-10-03T00:00:00Z")))
    edits = [{"ord": 1, "op": "create", "path": "lanes/STORE"}] + [
        {"ord": n, "op": "append", "path": "lanes/STORE", "new_text": text}
        for n, text in enumerate(store.splitlines(), 2)]
    entry = {"journal": {"kind": "cutover", "verb": "cutover", "lane": OPERATOR,
                         "workstation": "Eagle", "author": "lanes-index tests <test@example.invalid>",
                         "message": "cutover"},
             "edits": edits,
             "files": [{"path": "lanes/STORE", "present": True,
                        "sha256": hashlib.sha256(store.encode("utf-8")).hexdigest(),
                        "final_newline": True}],
             "not_after": "2999-01-01T00:00:00Z"}
    version = mod.REGISTER_SCHEMA_VERSION
    pg.psql(f"SET search_path TO {SCHEMA};\n"
            f"SELECT commit_write(0, '{uuid.uuid4()}', {version}, '{gen}', "
            f"'{json.dumps(entry)}'::jsonb);\n"
            f"SELECT record_marker({version}, 1, '{'c' * 40}', 'Eagle');\n")
    assert _rows(pg, "SELECT mode, marker_state FROM register_switch") == \
        [{"mode": "primary", "marker_state": "present"}]


@pytest.mark.parametrize("case", list(SIDECAR_CASES))
def test_the_log_path_sidecar_names_the_same_log_file_in_unreadable_warnings(pg, tmp_path, case):
    """A read of a log names its file by the path in the sidecar
    `.logpath.<lane>`, beside the cached log text: the lane with unreadable
    `WORD` lines, and the lane whose log file's spelling differs in case,
    get the same warning naming the same `lanes/log/<File>.md` from SQL as
    from the files; the lane with no log has an empty sidecar and no warning
    (AT-7, "Success"; the phase plan's "Question 10"). SQL's side is
    `register read`'s form 1 with the member `log:<lane>` (CLI4.10 section
    3.6, whose `.logpath.<key>` is the resolved `lanes/log/<File>.md`, empty
    where none resolves) on the imported register at `primary`, from T203's
    flipped copy. The files side is `lane-last`'s `unreadable:` warnings."""
    from sql_register_helpers import flipped_copy
    lane, logfile = SIDECAR_CASES[case]
    reg = FixtureRegister(tmp_path / "e")
    proc = reg.import_at(pg, reg.c)
    assert proc.returncode == 0, proc.stderr
    mod = load_indexer()
    _to_primary(pg, reg, mod)
    files_side = reg.edit("lane-last", lane, env={"LANES_LANE": OPERATOR})
    warned = sorted(set(re.findall(r"unreadable: (lanes/log/[^:]+\.md):", files_side.stderr)))
    config = reg.config(pg)
    config.write_text(config.read_text(encoding="utf-8").replace("mode=index", "mode=primary"),
                      encoding="utf-8")
    copy = flipped_copy(INDEXER, tmp_path / "flipped", True)
    cache = tmp_path / "cache" / "reg"
    cache.parent.mkdir()
    read = reg.run(sys.executable, copy, "register", "read", "--prefetch", "--cache", cache,
                   "--files", f"register,aliases,log:{lane}",
                   env={"LANES_INDEX_CONFIG": str(config), "LANES_INDEX": None})
    assert read.returncode == 0, read.stderr
    sidecar = cache.parent / f"reg.logpath.{lane}"
    named = sidecar.read_text(encoding="utf-8").strip() if sidecar.exists() else ""
    if logfile is None:
        assert named == "" and warned == [], (named, warned)
    else:
        assert warned == [logfile], f"files mode's warning: {files_side.stderr}"
        assert named == logfile, f"the sidecar names {named!r}"


def _stats(samples: list) -> dict:
    """Section 5.3's statistics: median and p95 by nearest rank, min-max, n."""
    ordered = sorted(samples)
    rank = lambda p: ordered[max(0, -(-p * len(ordered) // 100) - 1)]  # noqa: E731
    return {"median": rank(50), "p95": rank(95), "min": ordered[0], "max": ordered[-1],
            "n": len(ordered)}


def test_the_imports_proof_is_timed_and_recorded(pg, tmp_path):
    """M6 (section 5.1): the time of `import --at`'s render and proof over
    the fixture register, exec to exit, the first run cold and ten warm,
    recorded with section 5.3's statistics and its n in the job's log and
    `$GITHUB_STEP_SUMMARY` where it is set; never asserted. The correctness
    alongside is the import's own oracle: each run passes, and the counts
    equal the files'."""
    reg = FixtureRegister(tmp_path / "e")
    config = reg.config(pg)
    times = []
    for _ in range(11):
        start = time.monotonic_ns()
        proc = reg.import_at(pg, reg.c, config=config)
        times.append((time.monotonic_ns() - start) / 1e6)
        assert proc.returncode == 0, proc.stderr
        _assert_proved(reg, pg, reg.c)
    warm = _stats(times[1:])
    row = (f"| M6 | fixture cluster, Unix socket | `import --at` render and proof | "
           f"cold {times[0]:.1f} ms | median {warm['median']:.1f} ms, p95 {warm['p95']:.1f} ms, "
           f"{warm['min']:.1f}-{warm['max']:.1f} ms, n={warm['n']} |")
    print("\n" + row)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(row + "\n")


# ====================================================== the cutover (G; T272)

#: A password the operator's password file holds, for the marker commit's
#: scan (AT-7, "The cutover (G)": "no password, no password-file path and no
#: URL userinfo"). The session cluster's socket trusts every login, so it is
#: never needed to connect.
SECRET = "t272-pw-" + "6d1f0c2a9b"

#: The trailer each mirror commit and the marker commit carry (section 1.3).
REGISTER_SEQ = re.compile(r"^Register-Seq: ([0-9]+)$", re.M)
#: A URL's userinfo, `<scheme>://<user>[:<password>]@`.
USERINFO = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s@]+@")
#: `status`'s lag line at a lag of 0, on primary (lane 1's T117; design.md
#: section 2.1's smoke test, "a lag of 0").
LAG_0 = re.compile(r"^\s*lag:\s+0 seq", re.M)


def flipped_indexer(directory: Path) -> Path:
    """T203's flipped copy, `RENDER_GIT_HALF = True`, in `directory`, with
    `lanes-edit.sh` beside it (the copy rule, CLI4.5 section 6), so that
    `cutover` takes `lanes_register` and a write on primary goes to SQL."""
    from sql_register_helpers import RENDER_GIT_HALF_LINE, flipped_copy
    assert len(RENDER_GIT_HALF_LINE.findall(INDEXER.read_bytes())) == 1, (
        f"{INDEXER} holds no single `RENDER_GIT_HALF = ...` line, Q6(c)'s build constant "
        f"(L1-A4, lane 1's T105), so no copy can be flipped")
    copy = flipped_copy(INDEXER, directory, True)
    for name in ("lanes-edit.sh", "repos.tsv"):
        if (REPO / name).exists():
            shutil.copy2(REPO / name, copy.parent / name)
    return copy


class CutoverRegister(FixtureRegister):
    """Test 7's cutover (G): the fixture register at C, imported on `pg` by
    `import --at <C>`, and the operator's two configurations, `mode=index`
    for the import, `cutover` and `status`, and `mode=primary` for a write.
    Each command runs as the operator lane, `LANES_LANE=repoA-2`, through
    its checkout (F12; section 2.1), by the flipped copy. `extra_path` goes
    first on those commands' `PATH` (AT-F2's `git` wrapper).

    Before the import, the operator lane releases the fixture's `HOLD` with
    no readable time, `HOLD_NO_UTC_RELEASE` in files mode, so C is the tip
    after that release and no `HOLD` is open in `main_slots`: lane 1's
    open-`HOLD` check would refuse the first form otherwise (lane 3, #165
    6814260122). `release_hold=False` keeps it open, for the one case that
    expects the refusal.

    A write on primary also reads the operator lane's own register checkout,
    `<c>`, beside W, and refuses 2 where it is not there (lane 3's batch g
    Q119, #165 6813027223). `write` makes it before the first write, after
    the case's cutover has pushed from the operator's checkout
    (`lane_checkout`)."""

    def __init__(self, root: Path, pg, *, extra_path: Path | None = None,
                 release_hold: bool = True):
        super().__init__(root)
        if release_hold:
            proc = self.edit("append-line", HOLD_NO_UTC_RELEASE, env={"LANES_LANE": OPERATOR})
            assert proc.returncode == 0, (
                f"the dead HOLD's release, lanes-edit.sh append-line: {proc.stdout}{proc.stderr}")
            self.c = self.tip()
        self.pg = pg
        self.extra_path = extra_path
        self.copy = flipped_indexer(root / "flip")
        self.index_conf = self.config(pg)
        passfile = self.conf / "pgpass"
        passfile.write_text(f"*:*:*:*:{SECRET}\n", encoding="utf-8")
        passfile.chmod(0o600)
        self.primary_conf = self.conf / "lanes-index-primary.conf"
        self.primary_conf.write_text(self.index_conf.read_text(encoding="utf-8").replace(
            "mode=index", "mode=primary"), encoding="utf-8")
        self.primary_conf.chmod(0o600)
        proc = self.import_at(pg, self.c, config=self.index_conf)
        assert proc.returncode == 0, f"test 7's import at C failed: {proc.stderr}"

    def index_env(self, conf: Path | None = None, env: dict | None = None) -> dict:
        """The environment of one `lanes-index` run, as `Workspace.run`
        merges it: None removes a key."""
        child = {"LANES_INDEX_CONFIG": str(conf or self.index_conf), "LANES_LANE": OPERATOR,
                 "LANES_INDEX": None, "LANES_EDIT": str(self.copy.parent / "lanes-edit.sh")}
        if self.extra_path is not None:
            child["PATH"] = str(self.extra_path) + os.pathsep + self.env["PATH"]
        child.update(env or {})
        return child

    def index(self, *args, conf: Path | None = None, env: dict | None = None,
              timeout: float = 300) -> subprocess.CompletedProcess:
        return self.run(sys.executable, self.copy, *args, cwd=self.wip, timeout=timeout,
                        env=self.index_env(conf, env))

    def popen(self, *args, conf: Path | None = None, env: dict | None = None) -> subprocess.Popen:
        """The same run, started and not waited for."""
        child = dict(self.env)
        for key, value in self.index_env(conf, env).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return subprocess.Popen([sys.executable, str(self.copy), *[str(a) for a in args]],
                                cwd=str(self.wip), env=child, text=True,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

    def cutover(self, **kw) -> subprocess.CompletedProcess:
        """The first form, `lanes-index cutover --import <C>` (operations.md,
        act 4's step 7)."""
        return self.index("cutover", "--import", self.c, **kw)

    def lane_checkout(self) -> Path:
        """`<c>`, THE OPERATOR LANE'S OWN REGISTER CHECKOUT (lane 3's batch g
        Q119, #165 6813027223): beside the checkout `workspace.yaml` names as
        W, `ws`, at `<W>-lanes/repoA-2`, W being its real path, as
        `lanes-edit.sh`'s `lane_checkout_path` puts it (Amendment 23 S1). On
        primary a write reads its author, its pending hand edits and its
        `repos.tsv` from there, and refuses 2 where it is not there, "Nothing
        was sent" (B15 tasks:1154; T415's `pw_checkout`). A clone of origin,
        as `lane-checkout <lane> --create` makes one, in LX's T253f style.
        One that is already there is kept, so a case or an estate that made
        its own keeps it (line RB's T273f makes test 8's in the same place)."""
        real = Path(os.path.realpath(self.ws))
        target = real.parent / f"{real.name}-lanes" / OPERATOR
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "-q", str(self.origin), str(target)], check=True,
                           env=self.env, capture_output=True, stdin=subprocess.DEVNULL)
        return target

    def fetch_w(self) -> None:
        """THE READER'S FETCH OF W (lane 3's ruling (a), #165 6833830078):
        `status` reads `m` on W's `origin/main` as last fetched there and
        never fetches (tasks:545), no write on primary fetches W (D12), and
        the render pushes from `<c>`, so a lag read after a render follows
        this: `git -C <W> fetch -q origin main`, with plain git, never
        through AT-F2's wrapper (it is not on this environment's `PATH`).
        It is the case's own act, not the write's, so no write's no-fetch
        assertion changes (T240)."""
        proc = subprocess.run(["git", "-C", str(self.ws), "fetch", "-q", "origin", "main"],
                              capture_output=True, env=self.env, check=False,
                              stdin=subprocess.DEVNULL, timeout=120)
        assert proc.returncode == 0, (
            f"the harness's fetch of W, git -C {self.ws} fetch -q origin main: "
            f"{proc.stderr.decode(errors='replace')}")

    def write(self, text: str, env: dict | None = None) -> subprocess.CompletedProcess:
        """One `log NOTED` on primary, through the flipped copy's
        `lanes-edit.sh`: R3b's smoke test. The operator lane's `<c>` is made
        first where it is not there yet (`lane_checkout`): after the case's
        last push from W, so it is a clone of origin's tip then."""
        self.lane_checkout()
        return self.run("bash", self.copy.parent / "lanes-edit.sh", "log", "NOTED",
                        f"lane:{OPERATOR}", text, cwd=self.wip,
                        env=self.index_env(self.primary_conf, env))

    def origin_git(self, *args: str) -> str:
        """git in the bare origin itself, so no clone's refs move."""
        proc = subprocess.run(["git", f"--git-dir={self.origin}", *args], capture_output=True,
                              env=self.env, check=False, stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr.decode(errors='replace')}"
        return proc.stdout.decode("utf-8", "replace")

    def origin_tip(self) -> str:
        return self.origin_git("rev-parse", "refs/heads/main").strip()

    def origin_tree(self, sha: str) -> str:
        return self.origin_git("rev-parse", f"{sha}:lanes").strip()

    def seqs_on_origin(self, since: str | None = None) -> dict:
        """{commit: [its `Register-Seq` values]} for each commit on origin's
        `main` after `since` (C by default), oldest first."""
        commits = self.origin_git("rev-list", "--reverse", f"{since or self.c}..refs/heads/main")
        return {sha: REGISTER_SEQ.findall(self.origin_git("log", "-1", "--format=%B", sha))
                for sha in commits.split()}

    def wait_for_seq(self, seq: int, seconds: float = 60) -> str | None:
        """The commit on origin carrying `Register-Seq: <seq>`, once the
        renderer a write forked has pushed it, or None at the deadline."""
        deadline = time.monotonic() + seconds
        while True:
            for sha, seqs in self.seqs_on_origin().items():
                if str(seq) in seqs:
                    return sha
            if time.monotonic() > deadline:
                return None
            time.sleep(0.5)

    def other_clone(self, name: str) -> Path:
        """Another clone of origin, as another host's."""
        path = self.root / name
        subprocess.run(["git", "clone", "-q", str(self.origin), str(path)], check=True,
                       env=self.env, capture_output=True, stdin=subprocess.DEVNULL)
        return path

    def push_from(self, clone: Path, path: str, text: str, message: str) -> str:
        """Commit `text` at `path` in `clone` and push it to origin's `main`."""
        target = clone / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        for argv in (["add", "--", path], ["commit", "-q", "-m", message],
                     ["push", "-q", "origin", "HEAD:main"]):
            subprocess.run(["git", "-C", str(clone), *argv], check=True, env=self.env,
                           capture_output=True, stdin=subprocess.DEVNULL)
        return self.origin_tip()


def _switch(pg) -> dict:
    return _rows(pg, "SELECT mode, marker_state, marker_seq, marker_commit FROM register_switch")[0]


def _head(pg) -> int:
    return _rows(pg, "SELECT seq FROM register_head")[0]["seq"]


def _seqs(pg) -> list:
    return [(r["seq"], r["kind"]) for r in _rows(pg, "SELECT seq, kind FROM journal ORDER BY seq")]


def _store_fields(text: str) -> dict:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def test_a_cutover_pushes_one_fast_forward_marker_commit_with_no_credential(pg, tmp_path):
    """The cutover, run by the operator lane through its checkout, exits 0;
    the switch reads `primary`, and after the read-back the marker
    `present`. Origin's `main` gains exactly one commit, a fast-forward of
    C, carrying `Register-Seq: 1`, the cutover entry's own seq at a first
    cutover, and adding `lanes/STORE` alone, with D21's fields: `store=primary`,
    `database=` the configuration's `register_label=`, `import=<C>`,
    `lanes-tree=` C's `lanes` tree id, and `utc=`. A scan of that commit
    finds no password, no password-file path and no URL userinfo (AT-7,
    "The cutover (G)", TP:1455-1468). It fails until T327: before it, 0 is
    the transaction alone and the marker stays `adding`."""
    reg = CutoverRegister(tmp_path / "e", pg)
    assert reg.origin_tip() == reg.c
    proc = reg.cutover()
    assert proc.returncode == 0, proc.stderr
    switch = _switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
    assert _rows(pg, "SELECT seq FROM journal WHERE kind = 'cutover'") == [{"seq": 1}]
    gained = reg.seqs_on_origin()
    assert len(gained) == 1, f"origin's main gains exactly one commit: {gained}"
    (marker, seqs), = gained.items()
    assert reg.origin_git("rev-list", "--parents", "-n", "1", marker).split()[1:] == [reg.c], \
        "the marker commit is a fast-forward of C"
    assert seqs == ["1"], f"the marker carries Register-Seq: 1: {seqs}"
    assert switch["marker_commit"] == marker, "record_marker records the commit read back"
    changed = reg.origin_git("diff-tree", "--no-commit-id", "--name-status", "-r", reg.c, marker)
    assert changed.split("\n") == ["A\tlanes/STORE", ""], changed
    fields = _store_fields(reg.origin_git("show", f"{marker}:lanes/STORE"))
    assert {k: fields.get(k) for k in ("store", "database", "import", "lanes-tree")} == {
        "store": "primary", "database": LABEL, "import": reg.c,
        "lanes-tree": reg.tree(reg.c)}, fields
    assert fields.get("utc"), f"lanes/STORE carries utc=: {fields}"
    scanned = reg.origin_git("cat-file", "commit", marker) + reg.origin_git(
        "show", "--format=fuller", "--patch", marker)
    for needle in (SECRET, str(reg.conf / "pgpass"), str(reg.conf)):
        assert needle not in scanned, f"the marker commit carries {needle!r}"
    assert not USERINFO.search(scanned), f"the marker commit carries a URL's userinfo: {scanned}"


def test_the_first_write_after_cutover_is_the_cutovers_seq_plus_1_with_lag_0(pg, tmp_path):
    """After a first cutover, `log NOTED`, the smoke test, gives its SQL row
    at seq 2, the cutover's plus 1; a mirror commit carrying `Register-Seq:
    2`; a read-back equal to the row, here the mirror's file equal to SQL's
    render of it; and a lag of 0 in `status`, read after the harness's
    fetch of W, since `status` never fetches (AT-7, "The cutover (G)",
    TP:1469-1471; design.md's cutover step 4; open point 8; lane 3's
    ruling (a), #165 6833830078)."""
    reg = CutoverRegister(tmp_path / "e", pg)
    proc = reg.cutover()
    assert proc.returncode == 0, proc.stderr
    assert _switch(pg)["marker_state"] == "present", _switch(pg)
    cut = _rows(pg, "SELECT seq FROM journal WHERE kind = 'cutover'")[0]["seq"]
    note = "the smoke test, after the cutover"
    wrote = reg.write(note)
    assert wrote.returncode == 0, f"log NOTED on primary: {wrote.stdout}{wrote.stderr}"
    assert _rows(pg, f"SELECT seq, kind, lane FROM journal WHERE seq > {cut} ORDER BY seq") == \
        [{"seq": cut + 1, "kind": "write", "lane": OPERATOR}]
    rows = _rows(pg, f"SELECT file, raw FROM log_lines WHERE seq = {cut + 1}")
    assert len(rows) == 1 and note in rows[0]["raw"], rows
    commit = reg.wait_for_seq(cut + 1)
    assert commit, f"no mirror commit carries Register-Seq: {cut + 1}: {reg.seqs_on_origin()}"
    mirrored = reg.origin_git("show", f"{commit}:{rows[0]['file']}").encode("utf-8")
    assert rows[0]["raw"] in mirrored.decode("utf-8").split("\n")
    assert mirrored == _renders(pg)[rows[0]["file"]], "the read-back equals SQL's render"
    reg.fetch_w()   # open point 8: `status` reads W as last fetched (lane 3's ruling (a))
    status = reg.index("status")
    assert LAG_0.search(status.stdout), f"status shows a lag of 0: {status.stdout}{status.stderr}"


def test_the_cutover_aborts_when_main_moved_under_lanes(pg, tmp_path):
    """Another clone pushes a commit under `lanes/` after C. The cutover
    pushes nothing and exits with PC-10's abort code once `switch_to_files`
    has committed: seq 1 is gone, the head reads the import's seq, 0, and
    the switch reads `files` with the marker `absent` (AT-7, "The abort",
    TP:1473-1479; `contracts/exit-codes.md` section 4)."""
    reg = CutoverRegister(tmp_path / "e", pg)
    aborted = load_indexer().EXIT_CUTOVER_ABORTED
    log = "lanes/log/repoB-1.md"
    moved = reg.push_from(reg.other_clone("other"), log,
                          reg.blob(reg.c, log).decode("utf-8") + "a line pushed after C\n",
                          "a commit under lanes/ after C")
    assert reg.origin_tree(moved) != reg.tree(reg.c)
    proc = reg.cutover()
    assert proc.returncode == aborted, f"exit {proc.returncode}: {proc.stderr}"
    assert moved[:7] in proc.stderr, \
        f"the abort names the moved tip (exit-codes.md section 4): {proc.stderr}"
    assert reg.origin_tip() == moved, "the aborted cutover pushed nothing"
    assert "lanes/STORE" not in reg.origin_git("ls-tree", "-r", "--name-only", moved, "lanes/")
    assert _seqs(pg) == [(0, "import")], "switch_to_files deletes seq 1"
    assert _head(pg) == 0, "the head reads the import's seq"
    switch = _switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), switch


def test_a_handoff_commit_on_the_tip_does_not_abort_the_cutover(pg, tmp_path):
    """A third clone pushes a commit under `handoffs/` after C. The `lanes`
    tree id is unchanged, so the cutover goes ahead: it exits 0, and its one
    commit is a fast-forward of that tip, with C's import and tree in
    `lanes/STORE` (AT-7, "The abort", TP:1480-1481; design.md's cutover
    step 2, "a handoff commit on the tip only makes it rebuild")."""
    reg = CutoverRegister(tmp_path / "e", pg)
    tip = reg.push_from(reg.other_clone("third"), f"handoffs/{OPERATOR}.md",
                        "# a handoff, written after C\n", "a handoff commit after C")
    assert reg.origin_tree(tip) == reg.tree(reg.c), "the handoff leaves the lanes tree as C's"
    proc = reg.cutover()
    assert proc.returncode == 0, proc.stderr
    gained = reg.seqs_on_origin(tip)
    assert len(gained) == 1 and list(gained.values()) == [["1"]], gained
    marker = next(iter(gained))
    assert reg.origin_git("rev-list", "--parents", "-n", "1", marker).split()[1:] == [tip]
    fields = _store_fields(reg.origin_git("show", f"{marker}:lanes/STORE"))
    assert (fields.get("import"), fields.get("lanes-tree")) == (reg.c, reg.tree(reg.c)), fields
    switch = _switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch


def test_a_first_cutover_over_a_hold_with_no_readable_time_is_refused_2_and_sets_nothing(pg,
                                                                                          tmp_path):
    """The fixture's `HOLD` with no readable time, `TAKE_LINES["hold-no-utc"]`,
    left open (`release_hold=False`): the first-form cutover refuses with 2
    before its step 1, its listed line naming the take with "time
    unreadable", and sets nothing: the journal holds the import alone, the
    head is 0, the switch reads `files` with the marker `absent`, and origin's
    tip is still C, with no `lanes/STORE` (lane 1's T116 follow-up 6, its
    probe 5; lane 3's ruling, #165 6813195977, kept by its B16 post,
    6814260122). It fails until that follow-up lands (line R's merge21f6):
    before it, the cutover goes on over the open take."""
    reg = CutoverRegister(tmp_path / "e", pg, release_hold=False)
    proc = reg.cutover()
    assert proc.returncode == 2, (
        f"a first-form cutover over an open HOLD with no readable time is not refused with 2 "
        f"(lane 1's T116 follow-up 6): exit {proc.returncode}: {proc.stderr}")
    listed = [line for line in proc.stderr.splitlines() if "time unreadable" in line]
    assert len(listed) == 1 and TAKE_LINES["hold-no-utc"] in listed[0], (
        f"the refusal does not list the take with no readable time: {proc.stderr}")
    assert _seqs(pg) == [(0, "import")] and _head(pg) == 0, "the refused cutover wrote an entry"
    switch = _switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), switch
    assert reg.origin_tip() == reg.c, "the refused cutover pushed"
    assert "lanes/STORE" not in reg.origin_git("ls-tree", "-r", "--name-only", reg.c, "lanes/")
