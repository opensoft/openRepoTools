# SPDX-License-Identifier: Apache-2.0
"""TEST 14: THE BUILD BEFORE THE RENDERER'S GIT HALF (feature 007; the test
plan's AT-14; FR-001, FR-002, FR-003, FR-059).

One constant is the flip: `RENDER_GIT_HALF`, beside `SCHEMA_VERSION` in the
checkout's `lanes-index` (lane 1's T105, L1-A3). While it is False, Q6(c)'s
refusal of `mode=primary` is built in, and lane 3's T328 is the only change
that sets it True. So the module builds both states from the one checkout,
with T203's `flipped_copy` (PC-5): the REFUSING copy has the constant False,
the FLIPPED copy has it True, whichever way the checkout's own says.

WHAT IT HOLDS, by task:

  * T212 (L2-N2), the refusing state:
    - `test_mode_primary_is_refused_until_the_git_half_and_goes_to_sql_once_
      flipped[refusing]`: `lanes-index mode` exits 78 with the fixed text and
      nothing on stdout, and so does it over `store=sqlite` or no
      `register_url=`, since Q6(c)'s check runs first (Y:4849; lane 1, #165
      6747929926 point 1); every other command this build has that reads the
      configuration exits 2 with the same text: `status`, `sync` and
      `reconcile` with `LANES_INDEX` unset, and `export`, which writes it to
      `<out>/why`; `cutover --import <sha>`, `rollback` and `set-mode
      primary` exit 2 with it too, once a build has them (TP:2598-2600). No
      `psql` runs, no store is made, and the files, the HEAD and origin are
      unchanged;
    - `[mode-under-index-off]`: with `LANES_INDEX=off` kept set over the same
      file, `lanes-index mode` still exits 78 with the text, never `index`
      (lane 3, #165 6747957479; lane 1, 6748099727). Its `[J3]` word is
      `sql_register_build_flip and mode-under-index-off`;
    - `test_lanes_edit_asks_lanes_index_mode_only_where_a_configuration_
      exists` (D3): with no configuration file and `LANES_INDEX_CONFIG`
      unset, a logging stand-in at `lanes-index`'s path records no call, and
      the verb writes in files mode;
    - `test_mode_primary_with_sqlite_is_refused` (P162-163; R-F9-5): on T203's
      FLIPPED copy, where Q6(c)'s refusal is lifted, `mode=primary` with
      `store=sqlite`, or with no `register_url=`, is T104's refusal, 2 (lane
      1's L1v4.10:117), and not Q6(c)'s text. On the refusing copy Q6(c)'s 78
      comes first, which `[refusing]` holds. This is lane 2's reading of the
      two lines together (NOTES question 29);
    - `test_register_read_exits_78_under_the_refusal[readers|for-guard]`:
      `register read` exits 78 with the text, never 2, in the readers' forms
      (contract section 3.6's forms 1 and 3) and in `--for guard`'s (forms 2
      and 4), as contract section 2.7's 78 row names them;
    - `test_readers_under_the_refusal_answer_the_78_as_a_failed_read[<read>|
      listing|session-start|guard|projection]`: run from the same estate under
      the refusal, with the fake `psql`'s log empty, a read that decides
      exits 69 with nothing on stdout; the listings and the `SessionStart`
      block answer from the mirror, exit 0, and carry the `read: mirror`
      line; the prompt guard exits 2, run in the lane's window with a live
      session record and compact hook JSON, since without them it refuses 2
      before any read (lane 3's T507 ruling (1), #165 6783977598); and
      `managed-projection` answers 1, UNKNOWN, never 8.
  * T256 (L2-W6), the flipped state and the render fork's stub test, each a
    REAL-ENGINE case (the flipped state is RE: its write is a `register
    snapshot` reply and a commit, which a fake cannot fabricate), and
    `[replay-keeps-pid]`, which needs no engine:
    - `[flipped]`: on the FLIPPED copy, with `register_url=` on the session
      cluster's socket, on an imported register after the cutover, the same
      `log NOTED` exits 0, the journal gains one entry, the shim's log holds
      one attempt of two calls (the snapshot and the commit, sent as
      `register_url=`'s login with `register_passfile=` and no `PGPASSWORD`),
      the files are unchanged, since there is no git half in this build, and
      the stand-in logs one `mode` call, the primary half of the rule that
      the ask is made once: the parent asks it, and the attempt's child asks
      none (Y:5038, Y:5452);
    - `[replay-keeps-pid]` (R-T409-9; lane 3, #165 6747281902, T409's item
      9; lane 3's proposal, 6852014823, which lane 2 confirmed in
      6858869119): with a configuration, an unrouted write whose first push
      loses a race runs again by S4's replay, an `exec` that keeps the pid,
      and the stand-in logs one `mode` call across it (Y:4858, Y:5121: the
      ask is made once). It runs in `index` mode, with no engine, since no
      primary writer that asks the mode ever replays. Its `[J3]` word is
      `sql_register_build_flip and replay-keeps-pid`;
    - `test_a_primary_write_forks_render_checkout_on_the_lane_checkout_
      detached[plain|no-fetch-set|index-off-set]`: after a primary write
      commits, the stand-in's log holds one `render` call, `render --checkout
      <c>`, `<c>` the writing lane's checkout, `<W>-lanes/<lane>/`; its
      environment has no `LANES_NO_FETCH`, though the verb ran with it set in
      `[no-fetch-set]` (D12); it is made though `LANES_INDEX=off` is set in
      `[index-off-set]`; its stdin is closed or `/dev/null` and its
      descriptors 3 to 9 are closed, as `index_nudge`'s fork has them; and
      the writer exits with the verb's own code while the stand-in holds the
      `render` call on a FIFO, so no fork waits, and the flipped copy's
      answer to it, "git half not installed", is never read.
  * T282 (lane 2's, with lane 1's T124 and in its pull request), T124's cached
    module (tasks:2850-2878; AT-14, TP:2660; FR-064): a start of the refusing
    copy's `lanes-index mode` runs `lanes_index_main.py`'s checked-hash cached
    bytecode (PEP 552) where its hash matches the module's bytes
    (`test_a_start_runs_the_cached_module_whose_checked_hash_matches_its_source`),
    never bytecode whose source has changed
    (`test_a_start_never_runs_cached_bytecode_whose_source_has_changed`), and
    the module's source where it has no bytecode
    (`test_a_start_runs_the_module_source_where_it_has_no_bytecode`); and every
    subcommand in the usage answers alike from the cached module and from its
    source, with the argv seen at the module's entry and at its dispatch equal
    to the vector the test gave the launcher, `argv[0]` included
    (`test_each_subcommand_answers_alike_from_the_cached_module_and_from_its_source`).
    Each first asserts that `flipped_copy` placed the module beside the copy,
    T124's hunk in `tests/sql_register_helpers.py`.

THE CODES ARE READ FROM THE CONSTANTS (contracts/exit-codes.md section 1:
"the tests read the constant, never a literal"): `EXIT_CONFIG` and
`EXIT_REFUSED`, which T105 names in `lanes-index`. A code `lanes-edit.sh`
exits with (69, 1 and 2 from the readers) has no constant, and is a literal.

THE REFUSING STATE'S CONFIGURATION (T212's bullet; lane 1's CLI4.5 section
2.5; R09): `mode=primary`, with `register_url=` and `reader_url=` on
`db.invalid`, each carrying `sslmode=verify-full` and an `sslrootcert=` that
names a test root file, and 0600 password files. That meets the block's
configuration rule, and Q6(c)'s 78 does not rest on it: Q6(c) runs before
T104's R8, R9, R10 and R15, so test 14's own state, a register URL on
`db.invalid` with no TLS, gives the same 78 (R-F9-5).

THE FAKE-`psql` HOST RULE (L1v4.5:525; lane 1, #165 6741670709 item 9): the
refusing state's `register_url=`, on `db.invalid`, meets it by `verify-full`
and a root file, and every other configuration here either names no URL or
carries the same `verify-full` and root file, since T104 refuses any other at
load (CLI4.5 section 2.5). The fake is T203's `REGISTER_FAKE_PSQL`, first on
`PATH`; its log stays empty in every case here, since nothing connects.

`LANES_INDEX` (R-F9-5): `tests/conftest.py` sets `LANES_INDEX=off` for the
whole run, and `Estate` builds its environment without it. Under it `sync`
and `reconcile` keep #160's no-op exit 0, even over a `mode=primary` file, so
`[refusing]` runs them with it unset; `lanes-index mode` reads the
configuration whatever it says, which `[mode-under-index-off]` holds.

THE STAND-IN AT `lanes-index`'S PATH. The checkout's `lanes-edit.sh` finds
`lanes-index` beside itself (`$SCRIPT_DIR/lanes-index`, then `PATH`), so each
`lanes-edit.sh` case runs a copy of it, with what it reads beside it, and puts
`LOGGING_WRAPPER` at `lanes-index`'s path there: it logs each call, then runs
the `lanes-index` it stands in front of. A reader case first asserts that the
reader asked `lanes-index`, so a case that never reaches the refusal fails on
that, never vacuously (`session-start` excepted, as T217's mirror test does).

NO NETWORK. Every remote is a bare repository under `tmp_path`, `$HOME` is
temporary, and `db.invalid` is never resolved: in the refusing state nothing
connects.

THE REAL ENGINE, for T256's flipped state and render fork only. The flipped
state takes `pg` from `tests/pgcluster.py`, one database cloned from the
session's template, and so skips with T205's banner where no PostgreSQL 16 is
found, unless `OPENREPOTOOLS_REQUIRE_PG=1`. The render fork's test asks for
`pg` itself, so its fixture closure holds `pg_engine` (T200's rule).
`[flipped]` shares its function with the refusing state and with
`[replay-keeps-pid]`, which need no engine and always run (AT-14: "The
refusing state is FP"), so it takes `pg` by `request.getfixturevalue` and
skips alone. Its register is reached as
AT-LR006's fixture reaches one (TP:4610-4615), by the documented functions as
`lanes_register_writer`: `commit_write` with an `import` entry holding the
estate's render set, then a `cutover` entry, then `record_marker`, as T221's
module does; the template is T227's, built by `lanes-index bootstrap
--no-passwords`. Two logins join the writer and the reader groups and connect
by the cluster's trust. The shim (T203's `PSQL_SHIM`, unarmed) stands in front
of the cluster's own `psql` and logs every call. Each flipped estate also has
the writing lane's own register checkout `<c>`, `<W>-lanes/<lane>/`, a clone
of W's origin, as lane 2's writes module makes one (`make_lane_checkout`): on
primary a write makes no clone, since a clone is a fetch (D12), so lane 4's
T415 refuses a write whose lane has none (`pw_checkout`; tasks:1154-1155).

`[replay-keeps-pid]`'S ESTATE (lane 3's proposal, 6852014823; lane 2's build
notes, 6858869119). No primary writer that asks the mode replays: on primary
T415's arm runs `pw_run` before 1a's routing (R17), and the attempt's child
asks nothing and stops at the seam before any push (Y:5038, Y:5040, Y:5042).
So the case runs in `index` mode, which `lanes-index mode` answers from the
file alone: a 0600 `mode=index` file named by `LANES_INDEX_CONFIG`, with
`LANES_INDEX=off`, which skips the index's nudge and never the mode question
(Y:5718), and the logging stand-in in front of the checkout's `lanes-index`.
The write is unrouted, through `Estate`'s explicit `LANES_REPO`, so it has no
`LANES__PID` and its replay keeps the mode only by `LANES__REPLAY_PID`, which is
R-T409-9's half. Its first push loses a race: `tests/a23_box.py`'s `NET_GIT`
is `LANES_GIT`, and its `FAKE_NET_HOOK` lands one commit of a peer, a clone of
the estate's origin, before the first push only, as
`tests/test_a23_publish_replay.py`'s `Box.race` does. With no race there is no
`push refused` note, and with no stand-in found there is no `mode` call, so
the case cannot pass vacuously.

WHAT EACH WAITS FOR (the block's Order): T212's tests fail until L1-A3, L1-A4,
L1-A11 and L5-A5 land: lane 1's T105 (the constant and `mode`), T113
(`register read`) and lane 5's T504 (the read door). D3's test passes at once
on a build that never asks the mode. T256's real-engine cases fail until L4-B1
and L4-B13 land, and on an engine they also need T227's template and lane 1's
T107 functions. `[replay-keeps-pid]` fails until lane 4's T409 follow-up for
its item 9, and needs Amendment 23's S4 replay and `NET_GIT`. T282's four
cases fail until lane 1's T124 lands, whose launcher and module they start,
and T124's verify selects them (tasks:2850, :2878).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import marshal
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from importlib.machinery import SourceFileLoader
from pathlib import Path
from urllib.parse import quote

import pytest

import sql_register_helpers as helpers
from conftest import REPO, WINDOWS_SKIP
from test_lanes_index import UUID_A2, Estate, estate

__all__ = ["estate"]  # the fixture, imported so that pytest finds it here

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

SQL_REGISTER_GATE_TABLE = {
    "test_a_primary_write_forks_render_checkout_on_the_lane_checkout_detached": ("T409", "T415", "T416"),  # T256; tasks:2436
    "test_lanes_edit_asks_lanes_index_mode_only_where_a_configuration_exists": (),  # T212; tasks:1974
    "test_mode_primary_is_refused_until_the_git_half_and_goes_to_sql_once_flipped": ("T104", "T105", "T113", "T504", "T505", "T506"),  # T212; tasks:1974
    "test_mode_primary_with_sqlite_is_refused": ("T104", "T105", "T113", "T504", "T505", "T506"),  # T212; tasks:1974
    "test_readers_under_the_refusal_answer_the_78_as_a_failed_read": ("T104", "T105", "T113", "T504", "T505", "T506"),  # T212; tasks:1974
    "test_readers_under_the_refusal_answer_the_78_as_a_failed_read[guard]": ("T104", "T105", "T113", "T504", "T505", "T506", "T507"),  # T212; tasks:1974, and T507 (T212h)
    "test_readers_under_the_refusal_answer_the_78_as_a_failed_read[session-start]": ("T104", "T105", "T113", "T504", "T505", "T506", "T508"),  # T212; tasks:1974, and T508 (T212h)
    "test_register_read_exits_78_under_the_refusal": ("T104", "T105", "T113", "T504", "T505", "T506"),  # T212; tasks:1974
    "test_mode_primary_is_refused_until_the_git_half_and_goes_to_sql_once_flipped[flipped]": ("T409", "T415", "T416"),  # T256; tasks:2436
    "test_mode_primary_is_refused_until_the_git_half_and_goes_to_sql_once_flipped[replay-keeps-pid]": ("T409",),  # T256; tasks:2436
    "test_a_start_runs_the_cached_module_whose_checked_hash_matches_its_source": ("T124",),  # T282; tasks:2877
    "test_a_start_never_runs_cached_bytecode_whose_source_has_changed": ("T124",),  # T282; tasks:2877
    "test_a_start_runs_the_module_source_where_it_has_no_bytecode": ("T124",),  # T282; tasks:2877
    "test_each_subcommand_answers_alike_from_the_cached_module_and_from_its_source": ("T124",),  # T282; tasks:2877
}

LANES_EDIT = REPO / "lanes-edit.sh"

#: Q6(c)'S FIXED TEXT (agreement test 14; the test plan's AT-14, TP:2540-2542;
#: design Y:4872). The design may reword it, not weaken it (P1413), and the
#: test pins what the design prints.
REFUSED_TEXT = ("mode=primary is not available in this build: the renderer's git half is not "
                "installed, so a write could not be mirrored; nothing was written")

#: `lanes-index`'s own stderr lines are prefixed so (contract section 2.6).
PREFIX = "lanes-index: "

#: A subcommand a build does not have yet answers 64 with these words (lane
#: 1's T105; #165 6747929926: "so does every subcommand not yet built").
NOT_BUILT = "this build does not have it"

#: What a case copies beside the stand-in, as T217's `Primary` does (CLI4.5:885).
COPIED_BESIDE = ("lanes-edit.sh", "lanes", "repos.tsv", "lane-start", "lane-worktrees")

#: The stand-in's files, beside it: its log, the FIFO a `render` call is held
#: on where a case names one, and the held calls' ends.
CALL_LOG = "lanes-index.calls"
HOLD_FILE = "lanes-index.hold"
ENDS_LOG = "lanes-index.ends"

#: THE LOGGING STAND-IN (AT-14's fixture; TP:2613-2616: "a logging wrapper
#: that records each call's argv, environment and open descriptors, and then
#: runs the flipped copy"): `lanes-index` at the path `lanes-edit.sh` finds.
#: It logs each call, one JSON object per line: its argv, the NAMES in its
#: environment (never a value), and the state of descriptors 0 to 9 as it
#: found them, `closed`, `devnull` or `open`. Then it runs `TARGET`, the
#: `lanes-index` it stands in front of, with the same argv, stdin and
#: descriptors. A `render` call, where `lanes-index.hold` beside it names a
#: FIFO, is first held on that FIFO until a case opens it for writing and
#: closes it; then it runs, and its end goes to `lanes-index.ends`.
LOGGING_WRAPPER = r'''#!/usr/bin/env python3
# TEST 14's LOGGING STAND-IN at lanes-index's path (feature 007, AT-14;
# TP:2613-2616): one JSON object per call in lanes-index.calls beside it, with
# the call's argv, the names in its environment and the state of descriptors 0
# to 9, then the lanes-index it stands in front of. A `render` call, where
# lanes-index.hold beside it names a FIFO, is held on that FIFO first, then
# run, and its end is logged in lanes-index.ends.
import json, os, stat, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def descriptor(number):
    try:
        found = os.fstat(number)
    except OSError:
        return "closed"
    try:
        null = os.stat(os.devnull)
    except OSError:
        return "open"
    if stat.S_ISCHR(found.st_mode) and found.st_rdev == null.st_rdev:
        return "devnull"
    return "open"


# THE DESCRIPTORS FIRST, before this script opens anything of its own.
fds = {str(number): descriptor(number) for number in range(10)}
argv = sys.argv[1:]
record = {"argv": argv, "pid": os.getpid(), "ppid": os.getppid(), "fds": fds,
          "env": sorted(os.environ)}
with open(os.path.join(HERE, "lanes-index.calls"), "a", encoding="utf-8") as log:
    log.write(json.dumps(record) + "\n")
hold = os.path.join(HERE, "lanes-index.hold")
if argv[:1] == ["render"] and os.path.exists(hold):
    import subprocess
    with open(hold, encoding="utf-8") as handle:
        fifo = handle.read().strip()
    with open(fifo, encoding="utf-8") as held:
        held.read()
    code = subprocess.call([sys.executable, TARGET] + argv)
    with open(os.path.join(HERE, "lanes-index.ends"), "a", encoding="utf-8") as ends:
        ends.write(json.dumps({"argv": argv, "exit": code}) + "\n")
    sys.exit(code)
os.execv(sys.executable, [sys.executable, TARGET] + argv)
'''

#: The `read: mirror` line (design S3, "The mirror reads"), on stderr.
MIRROR_LINE = re.compile(r"^read: mirror at [0-9a-f]{12}, .*$", re.M)

#: THE GUARD'S WINDOW (lane 3's T507 ruling (1), #165 6783977598; lane 5's
#: post that found this case, 6809022654). The guard keeps its order: with no
#: window, or no live session record in it, it refuses 2 before any read, and
#: T507's prefetch, the first call that asks `lanes-index`, comes after the
#: session-record check (lane 5, #165 6755266457). So `[guard]` runs in the
#: lane's window with a live record of the hook's session, as lane 2's T215e
#: gave AT-P3's case in the outage module (T203c's `guard_session`; built
#: here in its form, since this module runs on lines that lack that helper).
#: The window's stand-in `tmux` answers `display-message` as a real one does,
#: with each `@...@` word below filled in.
GUARD_WINDOW, GUARD_TMUX_SESSION, GUARD_WINDOW_ID, GUARD_PANE = "repoA-2", "testsess", "@1", "%1"
GUARD_TMUX = r'''#!/bin/sh
# TEST 14's STAND-IN tmux for the guard's window (feature 007, T507 ruling
# (1)): it answers display-message as the lane's window does, a target that is
# not that window with tmux's own "can't find window" and 1, and every other
# command with nothing and 0.
[ "${1-}" = display-message ] || exit 0
target=""; prev=""; fmt=""
for a in "$@"; do
  [ "$prev" = -t ] && target="$a"
  prev="$a"; fmt="$a"
done
case "$target" in
  ''|'@ID@'|'@SESSION@:@ID@'|'@PANE@'|'@SESSION@:@ID@.@PANE@') ;;
  *) printf "can't find window: %s\n" "$target" >&2; exit 1 ;;
esac
case "$fmt" in
  '#{session_name}:#{window_id}') printf '%s\n' '@SESSION@:@ID@' ;;
  '#{session_name}') printf '%s\n' '@SESSION@' ;;
  '#{window_id}') printf '%s\n' '@ID@' ;;
  '#{pane_id}') printf '%s\n' '@PANE@' ;;
  '#{pane_pid}') printf '%s\n' '@PID@' ;;
  *) printf '%s\n' '@WINDOW@' ;;
esac
exit 0
'''

#: THE READS THAT DECIDE (TP:2587-2589), each with an argv `Estate` answers in
#: files mode, as T217's readers' table gives them: under the refusal each
#: exits 69 with nothing on stdout.
DECIDE_READS = {
    "who": ("who", "opensoft/repoA#7"),
    "binding": ("binding", "repoA-1"),
    "live-holder": ("live-holder", "repoA-1"),
    "next-free": ("next-free", "repoA"),
    "lane-last": ("lane-last", "repoA-1"),
    "register-row": ("register-row", "repoC-9"),
    "session-lane": ("session-lane", UUID_A2),
    "canon-lane": ("canon-lane", "repoA-1"),
    "resolve-home": ("resolve-home", "repoA-1"),
}

#: The listings (TP:2590): each answers from the mirror, exit 0.
LISTINGS = (("lanes",), ("history", "--all"))

#: `[<read>|listing|session-start|guard|projection]` (TP:2644).
READER_CASES = sorted(DECIDE_READS) + ["listing", "session-start", "guard", "projection"]

#: What a decide read and `managed-projection` exit, `lanes-edit.sh`'s own
#: codes (contracts/exit-codes.md, `lanes-edit.sh`'s table; design S3).
READ_FAILED, PROJECTION_UNKNOWN, PROJECTION_NEVER, GUARD_REFUSED = 69, 1, 8, 2

#: THE FLIPPED STATE'S REGISTER (T256), as T221's module names it: the
#: schema, its three groups, and the two logins `lanes-index` connects as,
#: made once per cluster, members of the writer and the reader groups, with no
#: password.
SCHEMA = "lanes_register"
WRITER, READER = "lanes_register_writer", "lanes_register_reader"
LOGIN_WRITER, LOGIN_READER = "t256_register_writer", "t256_register_reader"

#: What the fixture's own entries are stamped with (AT-LR006's fixture).
FIXTURE_LANE, FIXTURE_WS, FIXTURE_AUTHOR = "Lane-T256", "ws-t256", "T256 <t256@example.invalid>"
NOT_AFTER = "2100-01-01T00:00:00Z"            # well past every case (lane 1's v2.3)
MARKER_COMMIT = "e" * 40
STORE_LABEL, STORE_UTC = "t256", "2026-11-10T12:00:00Z"

#: The writing lane of every flipped write: a LIVE row in `Estate`'s register.
WRITING_LANE = "repoA-2"

#: How long a case waits for a detached fork to show in the stand-in's log.
FORK_SECONDS = 20.0

#: `[replay-keeps-pid]`'S RACE: the body of `FAKE_NET_HOOK` behind
#: `tests/a23_box.py`'s `NET_GIT`, as `tests/test_a23_publish_replay.py`'s
#: `Box.race` writes it with `times=1`: before the helper's first push only,
#: the peer, a clone of the estate's origin, lands one commit of its own on
#: origin, so that push is refused and the write runs again. `@PEER@` and
#: `@COUNT@` are filled in, each quoted.
RACE_HOOK = """#!/usr/bin/env bash
[ "$1" = push ] || exit 0
n=$(cat @COUNT@ 2>/dev/null || echo 0)
[ "$n" -lt 1 ] || exit 0
echo $((n + 1)) > @COUNT@
git -C @PEER@ fetch -q origin
git -C @PEER@ merge -q --ff-only refs/remotes/origin/main
git -C @PEER@ commit -q --allow-empty -m "a peer's commit lands first ($((n + 1)))"
git -C @PEER@ push -q origin main
exit 0
"""

#: THE RENDER FORK'S THREE (TP:2621-2624): the verb's own environment.
FORK_CASES = {
    "plain": {},
    "no-fetch-set": {"LANES_NO_FETCH": "1"},
    "index-off-set": {"LANES_INDEX": "off"},
}


# ------------------------------------------------------------------ helpers
def shown(proc: subprocess.CompletedProcess) -> str:
    return (f"exit {proc.returncode}\n--- stdout ---\n{proc.stdout[-3000:]}"
            f"\n--- stderr ---\n{proc.stderr[-3000:]}")


def load_index(path: Path = helpers.LANES_INDEX):
    """`lanes-index` as a module, fresh, as `test_lanes_index.py` loads it."""
    loader = SourceFileLoader("lanes_index_build_flip_module", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def exit_code(name: str) -> int:
    """The checkout's `lanes-index`'s named exit code (contracts/exit-codes.md
    section 1), asserted to be there: T105 names `EXIT_CONFIG`, `EXIT_REFUSED`
    and `EXIT_USAGE`."""
    module = load_index()
    assert isinstance(getattr(module, name, None), int), (
        f"the checkout's lanes-index names no `{name}`: Q6(c)'s exit codes are named "
        f"with lane 1's T105 (L1-A4; contracts/exit-codes.md section 1)")
    return getattr(module, name)


def constant_lines(path: Path = helpers.LANES_INDEX) -> list:
    return helpers.RENDER_GIT_HALF_LINE.findall(Path(path).read_bytes())


def state_copy(directory: Path, value: bool) -> Path:
    """T203's `flipped_copy` of the checkout's `lanes-index` (PC-5): `False`
    is the refusing state, `True` the flipped one. The checkout must hold the
    constant's one line, which lane 1's T105 adds (L1-A3)."""
    found = constant_lines()
    assert len(found) == 1, (
        f"the checkout's lanes-index holds {len(found)} `RENDER_GIT_HALF = ` lines, not one: "
        f"Q6(c)'s constant lands with lane 1's T105 (L1-A3)")
    return helpers.flipped_copy(helpers.LANES_INDEX, directory, value)


def write_private(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    return path


def calls(bin_dir: Path) -> list:
    """The stand-in's log: one dict per call, in call order."""
    path = bin_dir / CALL_LOG
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def forget_calls(bin_dir: Path) -> None:
    path = bin_dir / CALL_LOG
    if path.exists():
        path.write_text("", encoding="utf-8")


def beside(bin_dir: Path, target: Path) -> Path:
    """`bin_dir` holding a copy of the checkout's `lanes-edit.sh` and what it
    reads beside it, with `LOGGING_WRAPPER` at `lanes-index`'s path there in
    front of `target`. Returns the copied `lanes-edit.sh`."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in COPIED_BESIDE:
        shutil.copy2(REPO / name, bin_dir / name)
    wrapper = bin_dir / "lanes-index"
    wrapper.write_text(LOGGING_WRAPPER.replace("TARGET", repr(str(target))), encoding="utf-8")
    wrapper.chmod(0o755)
    return bin_dir / "lanes-edit.sh"


class Refusing:
    """Test 14's refusing state over an `Estate`: the configuration that says
    `mode=primary` at the workstation's default path (and named by
    `LANES_INDEX_CONFIG`), the refusing copy of `lanes-index`, and T203's fake
    `psql` first on `PATH`, logging every call."""

    def __init__(self, estate: Estate):
        self.e = estate
        self.root = estate.root / "test14"
        self.root.mkdir(parents=True, exist_ok=True)
        # A stand-in root file for `sslrootcert=`: it must exist as a regular
        # file (contract section 2.5), and nothing ever reads it as a root.
        self.root_file = self.root / "tls" / "register-root.pem"
        self.root_file.parent.mkdir(parents=True, exist_ok=True)
        self.root_file.write_text("test 14's stand-in root file; nothing connects to db.invalid\n",
                                  encoding="utf-8")
        self.passfile = write_private(self.root / "secrets" / "register.pgpass",
                                      "db.invalid:5432:lanes:lanes_w_test14:not-a-secret\n")
        self.reader_passfile = write_private(self.root / "secrets" / "reader.pgpass",
                                             "db.invalid:5432:lanes:lanes_r_test14:not-a-secret\n")
        self.config = estate.write_config(self.config_text())
        self.copy = state_copy(self.root / "refusing", False)
        self.psql_dir = self.root / "psqlbin"
        self.psql_dir.mkdir(parents=True, exist_ok=True)
        fake = self.psql_dir / "psql"
        fake.write_text(helpers.REGISTER_FAKE_PSQL, encoding="utf-8")
        fake.chmod(0o755)
        self.psql_log = self.root / "psql.log"

    def url(self, user: str) -> str:
        """A URL on `db.invalid` that meets the block's configuration rule."""
        root = quote(str(self.root_file), safe="/")
        return f"postgresql://{user}@db.invalid:5432/lanes?sslmode=verify-full&sslrootcert={root}"

    def config_text(self, *, mode: str = "primary", store: str | None = None,
                    register: bool = True) -> str:
        lines = [f"mode={mode}"]
        if store:
            lines.append(f"store={store}")
        if register:
            lines += [f"register_url={self.url('lanes_w_test14')}",
                      f"register_passfile={self.passfile}",
                      f"reader_url={self.url('lanes_r_test14')}",
                      f"reader_passfile={self.reader_passfile}"]
        return "\n".join(lines) + "\n"

    def other_config(self, name: str, text: str) -> Path:
        """A second 0600 configuration, outside every work tree, for a case
        that names it by `LANES_INDEX_CONFIG`."""
        return write_private(self.root / "configs" / name, text)

    def env(self, **extra) -> dict:
        env = {"LANES_INDEX_CONFIG": str(self.config), "FAKE_PSQL_LOG": str(self.psql_log),
               "PATH": self.e.path_with(self.psql_dir), "LANES_INDEX": None,
               "LANES_EDIT": str(LANES_EDIT)}
        env.update(extra)
        return env

    def index(self, copy: Path, *args, **extra) -> subprocess.CompletedProcess:
        """`copy` run as `Estate.index` runs the checkout's `lanes-index`."""
        return self.e.run(sys.executable, copy, *args, env=self.env(**extra))

    def edit(self, edit_path: Path, *args, input_text: str | None = None,
             **extra) -> subprocess.CompletedProcess:
        """The copied `lanes-edit.sh` at `edit_path`, on this workstation."""
        env = self.env(LANES_EDIT=str(edit_path), **extra)
        return self.e.run("bash", edit_path, *args, env=env, input_text=input_text)

    def psql_calls(self) -> list:
        if not self.psql_log.exists():
            return []
        return [line for line in self.psql_log.read_text(encoding="utf-8").splitlines() if line]

    def origin_and_head(self) -> tuple:
        return self.e.tip(), self.e._git("rev-parse", "HEAD").strip()


def proc_start(pid: int) -> str:
    """The start token the guard compares, field 22 of `/proc/<pid>/stat`, cut
    after the last `) ` as `pid_alive` cuts it. Empty where there is no
    `/proc`, where `pid_alive` asks `kill -0` alone."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return stat.rsplit(") ", 1)[1].split()[19]


def in_the_lane_window(state: Refusing) -> tuple:
    """`[guard]`'s window and session (see `GUARD_TMUX`): the environment the
    hook runs in, and its input. The environment names the stand-in `tmux`'s
    server, pane and directory (first on `PATH`). The stand-in is written to
    `<root>/guard-window`, and the session's record to the estate's
    `$HOME/.claude/sessions/<pid>.json`, mode 0600, one line of compact JSON
    in the suite's record form: its live process is this test's own, so it
    needs no teardown, and its `procStart` is the live one, so the guard reads
    it live. The record's `tmux` names the window the stand-in answers for,
    and its `sessionId` is the hook's. The input is the hook's JSON, compact
    as the harness sends it, since the guard's `jstr` reads `"cwd":"<dir>"`
    with no blank after the colon; its `cwd` is the lane's checkout, under
    `$HOME/projects`, since a `cwd` outside the projects root is silent
    (clause (e))."""
    pid, cwd = os.getpid(), str(state.e.wip)
    directory = state.root / "guard-window"
    directory.mkdir(parents=True, exist_ok=True)
    text = GUARD_TMUX
    for word, value in (("@SESSION@", GUARD_TMUX_SESSION), ("@ID@", GUARD_WINDOW_ID),
                        ("@PANE@", GUARD_PANE), ("@PID@", str(pid)), ("@WINDOW@", GUARD_WINDOW)):
        text = text.replace(word, value)
    tmux = directory / "tmux"
    tmux.write_text(text, encoding="utf-8")
    tmux.chmod(0o755)
    write_private(state.e.home / ".claude" / "sessions" / f"{pid}.json", json.dumps(
        {"pid": pid, "sessionId": UUID_A2, "cwd": cwd, "procStart": proc_start(pid),
         "tmux": f"{GUARD_TMUX_SESSION}:{GUARD_WINDOW_ID}.{GUARD_PANE}", "name": GUARD_WINDOW,
         "nameSource": "user", "status": "busy", "kind": "interactive"},
        separators=(",", ":")) + "\n")
    env = {"TMUX": f"{directory / 'tmux-server'},{pid},0", "TMUX_PANE": GUARD_PANE,
           "PATH": os.pathsep.join([str(directory), state.env()["PATH"]])}
    hook = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": UUID_A2,
                       "cwd": cwd, "prompt": "hello"}, separators=(",", ":"))
    return env, hook


# ------------------------------------------ T256: the flipped state's world
def db_psql(db, script: str, role: str | None = None) -> subprocess.CompletedProcess:
    """One `psql` as the fixture's superuser, with the commit call's settings,
    as `role` where one is named (T221's form)."""
    head = "\\set VERBOSITY verbose\n\\set SHOW_CONTEXT never\nSET client_encoding = 'UTF8';\n"
    if role:
        head += f"SET ROLE {role};\n"
    return subprocess.run([db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                          input=head + script, capture_output=True, encoding="utf-8",
                          errors="replace", env=db.env(appname="t256"), timeout=120, check=False)


def sql(db, script: str, role: str | None = None) -> str:
    proc = db_psql(db, script, role)
    assert proc.returncode == 0, (f"psql{' as ' + role if role else ''} exited "
                                  f"{proc.returncode}: {proc.stderr.strip()}\n{script}")
    return proc.stdout.strip()


def window(db) -> dict:
    return json.loads(sql(db, f"SELECT to_jsonb(v) FROM {SCHEMA}.schema_version v;"))


def journal_count(db) -> int:
    return int(sql(db, f"SELECT count(*) FROM {SCHEMA}.journal;"))


def rendered(lines) -> str:
    """The sha256 of a file of `lines`, LF-ended, as `render_file` renders it."""
    return hashlib.sha256("".join(line + "\n" for line in lines).encode("utf-8")).hexdigest()


def entry(kind: str, verb: str, **parts) -> dict:
    """One `commit_write` entry: the journal object, `not_after`, and `parts`."""
    journal = {"kind": kind, "verb": verb, "lane": FIXTURE_LANE, "workstation": FIXTURE_WS,
               "author": FIXTURE_AUTHOR, "message": f"t256: {kind}"}
    journal.update(parts.pop("journal", {}))
    return {"journal": journal, "not_after": NOT_AFTER, **parts}


def render_lines(estate: Estate) -> dict:
    """The render set at the estate's origin (CLI4.5 section 3.2), each file
    as its lines: what the import loads, so the register answers as the files
    do."""
    found = {}
    for path in sorted((estate.wip / "lanes").rglob("*")):
        rel = path.relative_to(estate.wip).as_posix()
        if not (path.is_file() and helpers.RENDER_SET_PATH.match(rel)):
            continue
        text = estate.head_text(rel)
        assert text.endswith("\n"), f"{rel} has no final newline, which the import entry assumes"
        found[rel] = text[:-1].split("\n")
    return found


def import_entry(files: dict, commit: str, tree: str) -> dict:
    """An import of `files` (path to its lines) at `commit`: each created, its
    lines appended, and each path's digest as it renders."""
    edits, order = [], 0
    for path in sorted(files):
        order += 1
        edits.append({"ord": order, "op": "create", "path": path})
        for text in files[path]:
            order += 1
            edits.append({"ord": order, "op": "append", "path": path, "new_text": text})
    return entry("import", "import", journal={"git_commit": commit, "git_tree": tree},
                 edits=edits,
                 files=[{"path": p, "present": True, "sha256": rendered(files[p]),
                         "final_newline": True} for p in sorted(files)])


def cutover_entry(commit: str, tree: str) -> dict:
    """The cutover's `lanes/STORE` (D21's five fields, as T221's module writes
    them)."""
    lines = ("store=primary", f"database={STORE_LABEL}", f"import={commit}",
             f"lanes-tree={tree}", f"utc={STORE_UTC}")
    return entry("cutover", "cutover",
                 edits=[{"ord": 1, "op": "create", "path": "lanes/STORE"},
                        *({"ord": n, "op": "append", "path": "lanes/STORE", "new_text": line}
                          for n, line in enumerate(lines, start=2))],
                 files=[{"path": "lanes/STORE", "present": True, "sha256": rendered(lines),
                         "final_newline": True}])


def committed(db, base: int, body: dict, what: str) -> int:
    """The commit call as the writer sends it (AT-LR006's fixture): one
    SERIALIZABLE transaction around `commit_write`, as `lanes_register_writer`."""
    generation = sql(db, f"SELECT generation FROM {SCHEMA}.register_switch;")
    literal = json.dumps(body, ensure_ascii=True).replace("'", "''")
    proc = db_psql(db, f"BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
                       f"SELECT {SCHEMA}.commit_write({base}, '{uuid.uuid4()}'::uuid, "
                       f"{window(db)['version']}, '{generation}'::uuid, '{literal}'::jsonb);\n"
                       f"COMMIT;\n", WRITER)
    assert proc.returncode == 0, f"{what}: commit_write refused it: {proc.stderr.strip()}"
    return int(proc.stdout.strip().splitlines()[-1])


def bring_to_primary(db, estate: Estate) -> int:
    """AT-LR006's route (TP:4610-4615): as `lanes_register_writer`, an import
    of the estate's render set at its origin, then a cutover, then
    `record_marker`. Returns the head, the cutover's seq."""
    commit = estate.tip()
    tree = estate._git("rev-parse", "origin/main:lanes").strip()
    head = int(sql(db, f"SELECT seq FROM {SCHEMA}.register_head;"))
    imported = committed(db, head, import_entry(render_lines(estate), commit, tree), "the import")
    cut = committed(db, imported, cutover_entry(commit, tree), "the cutover")
    marker = sql(db, f"SELECT {SCHEMA}.record_marker({window(db)['version']}, {cut}, "
                     f"'{MARKER_COMMIT}', '{FIXTURE_WS}');", WRITER)
    assert marker == "present", f"record_marker answered {marker!r}, not present"
    switch = json.loads(sql(db, f"SELECT to_jsonb(s) FROM {SCHEMA}.register_switch s;"))
    assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
    return cut


def ensure_logins(db) -> None:
    """The writer's and the reader's login, once per cluster (roles are
    cluster-wide), members of their groups, with no password."""
    for login, group in ((LOGIN_WRITER, WRITER), (LOGIN_READER, READER)):
        sql(db, f"DO $l$ BEGIN CREATE ROLE {login} LOGIN IN ROLE {group}; "
                f"EXCEPTION WHEN duplicate_object THEN NULL; END $l$;")


def lane_checkout(estate: Estate, lane: str = WRITING_LANE) -> Path:
    """`<c>`, lane `lane`'s own register checkout, where `lanes-edit.sh`'s
    `lane_checkout_path` puts it (Amendment 23 S1): `<W>-lanes/<lane>`, W
    being the real path of `workspace.yaml`'s `path:`, `Estate.ws` (lane 2's
    form, the writes module's `lane_checkout`)."""
    real = Path(os.path.realpath(estate.ws))
    return real.parent / f"{real.name}-lanes" / lane


def make_lane_checkout(estate: Estate, lane: str = WRITING_LANE) -> Path:
    """`<c>` for `lane`, a clone of W's origin, as `lane-checkout <lane>
    --create` makes one (lane 2's `make_lane_checkout`, 5614d15:tests/
    test_sql_register_writes.py:420-427). On primary a write makes no clone,
    since a clone is a fetch (D12), so T415's `pw_checkout` refuses a write
    whose lane has no checkout before anything is sent (tasks:1154-1155)."""
    target = lane_checkout(estate, lane)
    target.parent.mkdir(parents=True, exist_ok=True)
    proc = estate.run("git", "clone", "-q", str(estate.origin), str(target))
    assert proc.returncode == 0, ("the lane's own register checkout was not made", shown(proc))
    return target


class Flipped:
    """Test 14's flipped state over an `Estate` and one `pg` database: the
    register imported from the estate and brought to `primary` with the
    marker `present`; a 0600 configuration whose `register_url=` and
    `reader_url=` name the session cluster's socket; T203's flipped copy, with
    the checkout's `lanes-edit.sh` beside the logging stand-in in front of it;
    the shim in front of the cluster's own `psql`; and the writing lane's own
    register checkout `<c>`, which T415's `pw_checkout` reads and never makes
    (`make_lane_checkout`)."""

    def __init__(self, estate: Estate, db):
        self.e, self.db = estate, db
        self.root = estate.root / "test14-flipped"
        self.root.mkdir(parents=True, exist_ok=True)
        self.checkout = make_lane_checkout(estate)
        self.passfile = write_private(self.root / "secrets" / "register.pgpass",
                                      f"*:*:*:{LOGIN_WRITER}:not-a-secret\n")
        self.reader_passfile = write_private(self.root / "secrets" / "reader.pgpass",
                                             f"*:*:*:{LOGIN_READER}:not-a-secret\n")
        ensure_logins(db)
        self.cut = bring_to_primary(db, estate)
        self.config = estate.write_config(self.config_text())
        self.copy = state_copy(self.root / "flipped", True)
        self.shim_dir = self.root / "shimbin"
        self.shim_dir.mkdir(parents=True, exist_ok=True)
        shim = self.shim_dir / "psql"
        shim.write_text(helpers.PSQL_SHIM, encoding="utf-8")
        shim.chmod(0o755)
        self.bin = self.root / "bin"
        self.edit_path = beside(self.bin, self.copy)

    def config_text(self) -> str:
        """Unix-socket URLs, so the fake-`psql` host rule holds (L1v4.5:525)."""
        return (f"mode=primary\n"
                f"register_url={self.db.url(LOGIN_WRITER)}\n"
                f"register_passfile={self.passfile}\n"
                f"reader_url={self.db.url(LOGIN_READER)}\n"
                f"reader_passfile={self.reader_passfile}\n")

    def env(self, **extra) -> dict:
        env = {"LANES_EDIT": str(self.edit_path), "LANES_INDEX_CONFIG": str(self.config),
               "PATH": self.e.path_with(self.shim_dir, Path(self.db.cluster.bindir)),
               "LANES_INDEX": None, "LANES_LANE": WRITING_LANE}
        env.update(extra)
        return env

    def write(self, text: str, timeout: float = 120, **extra) -> subprocess.CompletedProcess:
        """`log NOTED` as the writing lane: one primary write."""
        return self.e.run("bash", self.edit_path, "log", "NOTED", f"lane:{WRITING_LANE}", text,
                          env=self.env(**extra), timeout=timeout)

    def routed(self) -> dict:
        """Slice 1a's routing (Amendment 23 S2): no `LANES_REPO`, and
        `LANES_ROUTE_WRITES=1`."""
        return {"LANES_REPO": None, "LANES_ROUTE_WRITES": "1"}

    def lane_checkout(self) -> Path:
        """`<W>-lanes/<lane>/`, W being the real path `workspace.yaml` names:
        the checkout `make_lane_checkout` made."""
        return self.checkout

    def shim_calls(self) -> list:
        """The calls the shim handed on that carry a request: not `--version`."""
        path = self.shim_dir / helpers.PSQL_SHIM_LOG
        if not path.exists():
            return []
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        return [row for row in rows if row.get("kind") != "version"]

    def origin_and_head(self) -> tuple:
        return self.e.tip(), self.e._git("rev-parse", "HEAD").strip()


def the_78(proc: subprocess.CompletedProcess, config_code: int, what: str) -> None:
    """Q6(c)'s answer from `mode`: 78, nothing on stdout, and stderr exactly
    one line, the fixed text."""
    assert proc.returncode == config_code, (what, shown(proc))
    assert proc.stdout == "", (what, "stdout must be empty, never `index` or `primary`",
                               shown(proc))
    assert proc.stderr.splitlines() == [PREFIX + REFUSED_TEXT], (what, shown(proc))


# ---------------------------------------------- T212: test 14, refusing
def refusing_case(state: Refusing) -> None:
    """`[refusing]`: 78 from `mode`, 2 from every other command, the same
    text, nothing connected and nothing written."""
    config_code, refused, usage = (exit_code("EXIT_CONFIG"), exit_code("EXIT_REFUSED"),
                                   exit_code("EXIT_USAGE"))
    before = state.origin_and_head()
    the_78(state.index(state.copy, "mode"), config_code, "mode")
    # Q6(c) FIRST (Y:4849; R-F9-5): `store=sqlite`, or no `register_url=`,
    # is the same 78 while the constant is False, never T104's 2.
    for name, text in (("store-sqlite", state.config_text(store="sqlite")),
                       ("no-register-url", state.config_text(register=False))):
        conf = state.other_config(f"{name}.conf", text)
        the_78(state.index(state.copy, "mode", LANES_INDEX_CONFIG=str(conf)), config_code,
               f"mode over {name}")
    # EVERY OTHER COMMAND THIS BUILD HAS THAT READS THE CONFIGURATION: 2 with
    # the text. `sync` and `reconcile` with `LANES_INDEX` unset (R-F9-5).
    for argv in (("status",), ("sync",), ("reconcile",)):
        proc = state.index(state.copy, *argv, LANES_INDEX=None)
        assert proc.returncode == refused, (argv, shown(proc))
        assert REFUSED_TEXT in proc.stderr, (argv, shown(proc))
    out = state.root / "export-out"
    out.mkdir()
    proc = state.index(state.copy, "export", "--out", str(out), LANES_INDEX=None)
    assert proc.returncode == refused, ("export", shown(proc))
    why = (out / "why").read_text(encoding="utf-8") if (out / "why").exists() else ""
    assert REFUSED_TEXT in proc.stderr + why, ("export: the text, on stderr or in <out>/why",
                                               why, shown(proc))
    assert not (out / "meta").exists(), "export wrote an image under the refusal"
    # THE OPERATOR'S ACTS on a schema that is not a scratch schema (TP:2598-
    # 2600): 2 with the text, in a build that has them; before that, 64. Each
    # is given an argument list that parses, since a build checks a verb's
    # arguments before it reads the configuration (lane 1's T116, opensoft/
    # openRepoTools#165 6810924785): a bare `cutover` is a 64, "needs
    # --import <C> ... or --after-loss", and never reaches the refusal.
    # `--import` takes a full 40-digit sha, which names no commit here.
    imported = "0123456789abcdef0123456789abcdef01234567"
    for argv in (("cutover", "--import", imported), ("rollback",), ("set-mode", "primary")):
        proc = state.index(state.copy, *argv, LANES_INDEX=None)
        if proc.returncode == usage and NOT_BUILT in proc.stderr:
            continue
        assert proc.returncode == refused, (argv, shown(proc))
        assert REFUSED_TEXT in proc.stderr, (argv, shown(proc))
    assert state.psql_calls() == [], ("a refused configuration connected", state.psql_calls())
    assert not state.e.sqlite.exists(), "a store was made under the refusal"
    assert state.origin_and_head() == before, "the files, the HEAD or origin moved"
    assert state.config.read_text(encoding="utf-8") == state.config_text(), \
        "the configuration was rewritten"


def mode_under_index_off_case(state: Refusing) -> None:
    """`[mode-under-index-off]`: `LANES_INDEX=off` kept set over the same
    `mode=primary` file, and `mode` still answers 78 with the text, never
    `index` (lane 3, #165 6747957479; lane 1, 6748099727)."""
    config_code = exit_code("EXIT_CONFIG")
    the_78(state.index(state.copy, "mode", LANES_INDEX="off"), config_code,
           "mode under LANES_INDEX=off")
    assert state.psql_calls() == [], state.psql_calls()


def flipped_case(world: Flipped) -> None:
    """`[flipped]` (TP:2601-2606): the same `log NOTED` exits 0, the journal
    gains one entry, the shim's log holds one attempt of two calls (Q7 (A'')),
    the snapshot and then the commit, each as `register_url=`'s login with
    `register_passfile=` and no `PGPASSWORD`, and the files are unchanged."""
    before, entries = world.origin_and_head(), journal_count(world.db)
    proc = world.write("test 14 - flipped, a primary write")
    assert proc.returncode == 0, shown(proc)
    assert journal_count(world.db) == entries + 1, "the journal did not gain one entry"
    sent = world.shim_calls()
    assert len(sent) == 2, ("one attempt is two calls, the snapshot and the commit", sent)
    assert "commit_write" not in sent[0]["stdin"] and "commit_write" in sent[1]["stdin"], \
        ("the snapshot first, then the commit", [s["stdin"][:200] for s in sent])
    for call in sent:
        pg = call.get("pg", {})
        assert (pg.get("PGUSER"), pg.get("PGHOST"), pg.get("PGDATABASE")) == (
            LOGIN_WRITER, str(world.db.host), world.db.name), ("not register_url='s login", pg)
        assert call.get("passfile") == str(world.passfile), ("not register_passfile=", call)
        assert call.get("pgpassword") is False, ("PGPASSWORD reached psql", call)
    assert world.origin_and_head() == before, "the files moved: this build has no git half"
    modes = [c for c in calls(world.bin) if c["argv"] == ["mode"]]
    assert len(modes) == 1, ("the primary write asked the mode more than once, or never: the "
                             "parent asks it once, and the attempt's child asks none (Y:5038, "
                             "Y:5452)", [c["argv"] for c in calls(world.bin)])


def replay_keeps_pid_case(state: Refusing) -> None:
    """`[replay-keeps-pid]` (R-T409-9; lane 3, #165 6747281902, T409's item
    9; lane 3's proposal, 6852014823, confirmed by lane 2 in 6858869119): with
    a configuration, an unrouted write whose first push loses a race runs
    again by S4's replay, an `exec` that keeps the pid, and asks the mode
    once: one `mode` call in the stand-in's log (Y:4858, Y:5121). In `index`
    mode, with no engine: a 0600 `mode=index` file named by
    `LANES_INDEX_CONFIG`, `LANES_INDEX=off`, the write through `Estate`'s
    explicit `LANES_REPO` with no routing, and `tests/a23_box.py`'s
    `NET_GIT` as `LANES_GIT` with `RACE_HOOK` behind it. It asserts exit 0,
    `push refused (attempt 1 of 6)`, `pushed origin/main (attempt 2)`, and
    one `mode` call."""
    import a23_box
    net_git = getattr(a23_box, "NET_GIT", None)
    assert net_git, ("tests/a23_box.py has no NET_GIT, the LANES_GIT this case races the "
                     "write's first push through (Amendment 23 S4)")
    e = state.e
    conf = state.other_config("index.conf", "mode=index\n")
    bin_dir = state.root / "replay-bin"
    edit = beside(bin_dir, helpers.LANES_INDEX)
    peer = state.root / "peer"
    for argv in (("clone", "-q", str(e.origin), str(peer)),
                 ("-C", str(peer), "config", "user.name", "test 14's peer"),
                 ("-C", str(peer), "config", "user.email", "peer@example.invalid")):
        proc = e.run("git", *argv)
        assert proc.returncode == 0, ("the peer, a clone of origin", argv, shown(proc))
    net = bin_dir / "net-git"
    net.write_text(net_git, encoding="utf-8")
    net.chmod(0o755)
    hook = bin_dir / "net-hook"
    hook.write_text(RACE_HOOK.replace("@PEER@", shlex.quote(str(peer)))
                    .replace("@COUNT@", shlex.quote(str(state.root / "race.count"))),
                    encoding="utf-8")
    hook.chmod(0o755)
    proc = state.edit(edit, "log", "NOTED", f"lane:{WRITING_LANE}",
                      "test 14 - a replay keeps its pid",
                      LANES_INDEX_CONFIG=str(conf), LANES_INDEX="off", LANES_LANE=WRITING_LANE,
                      LANES_GIT=str(net), FAKE_NET_LOG=str(state.root / "net.log"),
                      FAKE_NET_HOOK=str(hook))
    assert proc.returncode == 0, shown(proc)
    assert "push refused (attempt 1 of 6)" in proc.stderr, \
        ("the first push did not lose the race, so the write did not replay", shown(proc))
    assert "pushed origin/main (attempt 2)" in proc.stderr, \
        ("the replayed write did not publish", shown(proc))
    modes = [c for c in calls(bin_dir) if c["argv"] == ["mode"]]
    assert len(modes) == 1, ("the mode ask was made more than once, or never, across the replay",
                             [c["argv"] for c in calls(bin_dir)])


STATE_CASES = {
    "refusing": refusing_case,
    "mode-under-index-off": mode_under_index_off_case,
    "flipped": flipped_case,
    "replay-keeps-pid": replay_keeps_pid_case,
}

#: The case that needs the real engine, taken by `request.getfixturevalue`.
FLIPPED_CASES = ("flipped",)


@pytest.mark.parametrize("case", list(STATE_CASES))
def test_mode_primary_is_refused_until_the_git_half_and_goes_to_sql_once_flipped(
        estate, request, case):
    """Test 14's one test of both states (AT-14): with the refusal in place,
    `mode=primary` is refused where the configuration is read, 78 from
    `mode`, 2 from every other command, with the fixed text; with the constant
    flipped, the same write goes to SQL."""
    if case in FLIPPED_CASES:
        STATE_CASES[case](Flipped(estate, request.getfixturevalue("pg")))
    else:
        STATE_CASES[case](Refusing(estate))


def test_lanes_edit_asks_lanes_index_mode_only_where_a_configuration_exists(estate):
    """D3 (FR-002; contract section 3.1, "Asked only where a configuration
    exists"): with no configuration file and `LANES_INDEX_CONFIG` unset, a
    logging stand-in at `lanes-index`'s path records no call, and the verb
    writes in files mode. `LANES_INDEX=off`, which `tests/conftest.py` sets
    for the run and which skips the index's nudge, never skips the mode query
    (Y:5717), so under it the only call a write could make is the one D3
    bars. Then `--index`, with the variable unset, reaches the stand-in, so
    the stand-in is where `lanes-edit.sh` finds `lanes-index`."""
    bin_dir = estate.root / "d3-bin"
    edit = beside(bin_dir, helpers.LANES_INDEX)
    assert not (estate.config / "openRepoTools" / "lanes-index.conf").exists()
    env = {"LANES_EDIT": str(edit), "LANES_INDEX_CONFIG": None, "LANES_INDEX": "off",
           "LANES_LANE": "repoA-2"}
    tip = estate.tip()
    text = "test 14 - D3, a write with no configuration"
    proc = estate.run("bash", edit, "log", "NOTED", "lane:repoA-2", text, env=env)
    assert proc.returncode == 0, shown(proc)
    assert calls(bin_dir) == [], ("the stand-in at lanes-index's path was called", calls(bin_dir))
    assert estate.tip() != tip, "the write did not push"
    assert text in estate._git("show", "origin/main:lanes/log/repoA-2.md"), \
        "the note is not in the files"
    proc = estate.run("bash", edit, "lanes", "--index",
                      env={"LANES_EDIT": str(edit), "LANES_INDEX_CONFIG": None,
                           "LANES_INDEX": None})
    assert [c["argv"][:1] for c in calls(bin_dir)] == [["export"]], (
        "`lanes --index` did not reach the stand-in, so it is not where lanes-edit.sh "
        "finds lanes-index", calls(bin_dir), shown(proc))


def test_mode_primary_with_sqlite_is_refused(estate):
    """`mode=primary` with `store=sqlite`, or with no `register_url=` (whose
    store is SQLite by default), on T203's flipped copy, where Q6(c)'s
    refusal is lifted: T104's refusal answers 2 (L1v4.10:117), with nothing
    on stdout and a `REFUSED:` line that is not Q6(c)'s text (lane 2's
    reading, NOTES question 29). `lanes-index mode` reads the configuration
    whatever `LANES_INDEX` says (lane 3, #165 6747957479)."""
    refused = exit_code("EXIT_REFUSED")
    state = Refusing(estate)
    copy = state_copy(state.root / "flipped", True)
    for name, text in (("store-sqlite", state.config_text(store="sqlite")),
                       ("no-register-url", state.config_text(register=False))):
        conf = state.other_config(f"{name}.conf", text)
        proc = state.index(copy, "mode", LANES_INDEX_CONFIG=str(conf))
        assert proc.returncode == refused, (name, shown(proc))
        assert proc.stdout == "", (name, shown(proc))
        lines = proc.stderr.splitlines()
        assert len(lines) == 1 and lines[0].startswith(PREFIX + "REFUSED: "), (name, shown(proc))
        assert REFUSED_TEXT not in proc.stderr, (name, "Q6(c)'s text from the flipped copy",
                                                 shown(proc))
    assert state.psql_calls() == [], state.psql_calls()


#: `register read`'s forms (contract section 3.6; its section 2.7's 78 row):
#: the readers', forms 1 and 3, and `--for guard`'s, forms 2 and 4.
def read_forms(family: str, state: Refusing) -> list:
    cache = str(state.root / "cache")
    pid = str(os.getpid())
    if family == "readers":
        return [["--prefetch", "--cache", cache, "--all"],
                ["--since", "0", "--cache", cache, "--files", "register"]]
    return [["--for", "guard", "--prefetch", "--cache", cache, "--pid", pid,
             "--repo", str(state.e.wip), "--lane=repoA-2"],
            ["--for", "guard", "--at", "1", "--pid", pid, "--cache", cache,
             "--lane=repoA-2"]]


@pytest.mark.parametrize("family", ["readers", "for-guard"])
def test_register_read_exits_78_under_the_refusal(estate, family):
    """`lanes-index register read`, in each of its forms, exits 78 with the
    text, never 2 (AT-14; contract section 2.7): readers and the guard learn
    the mode from it. Nothing connects, and no cache is written."""
    config_code = exit_code("EXIT_CONFIG")
    state = Refusing(estate)
    for argv in read_forms(family, state):
        proc = state.index(state.copy, "register", "read", *argv)
        assert proc.returncode == config_code, (argv, shown(proc))
        assert REFUSED_TEXT in proc.stderr, (argv, shown(proc))
    assert state.psql_calls() == [], state.psql_calls()
    assert not (state.root / "cache").exists(), "a cache was written under the refusal"


@pytest.mark.parametrize("reader", READER_CASES)
def test_readers_under_the_refusal_answer_the_78_as_a_failed_read(estate, reader):
    """The readers, run from the same estate under the refusal (AT-14; the
    delta's "Readers under the refusal"; the phase plan's "D3's refusal"):
    `register read` answers 78, and each reader answers it as a failed read.
    A read that decides exits 69 with nothing on stdout; a listing and the
    `SessionStart` block answer from the mirror, exit 0, with the `read:
    mirror` line on stderr; the prompt guard exits 2; `managed-projection`
    answers 1, UNKNOWN, never 8. The fake `psql`'s log stays empty, and the
    files and origin are unchanged. The guard runs in the lane's window with
    a live session record (`in_the_lane_window`), as the guard keeps its
    order: with no window, or no session record, it refuses 2 before any
    read, so it would never ask `lanes-index` (lane 3's T507 ruling (1),
    #165 6783977598)."""
    state = Refusing(estate)
    bin_dir = state.root / "bin"
    edit = beside(bin_dir, state.copy)
    before = state.origin_and_head()

    def asked(proc, what):
        assert calls(bin_dir), (what, "lanes-edit.sh never asked lanes-index, so it never met "
                                      "the refusal", shown(proc))

    if reader in DECIDE_READS:
        proc = state.edit(edit, *DECIDE_READS[reader])
        asked(proc, reader)
        assert proc.returncode == READ_FAILED, (reader, shown(proc))
        assert proc.stdout == "", (reader, shown(proc))
    elif reader == "listing":
        for argv in LISTINGS:
            forget_calls(bin_dir)
            proc = state.edit(edit, *argv)
            asked(proc, argv)
            assert proc.returncode == 0, (argv, shown(proc))
            assert MIRROR_LINE.search(proc.stderr), (argv, "no `read: mirror` line", shown(proc))
            assert not MIRROR_LINE.search(proc.stdout), (argv, shown(proc))
            assert proc.stdout.strip(), (argv, "the mirror gave no answer", shown(proc))
    elif reader == "session-start":
        proc = state.edit(edit, "session-start")
        assert proc.returncode == 0, shown(proc)
        assert MIRROR_LINE.search(proc.stderr), ("no `read: mirror` line", shown(proc))
        assert not MIRROR_LINE.search(proc.stdout), shown(proc)
    elif reader == "guard":
        window_env, hook = in_the_lane_window(state)
        proc = state.edit(edit, "guard", input_text=hook, **window_env)
        asked(proc, "guard")
        assert proc.returncode == GUARD_REFUSED, shown(proc)
    else:
        proc = state.edit(edit, "managed-projection", "repoM-1")
        asked(proc, "managed-projection")
        assert proc.returncode == PROJECTION_UNKNOWN, shown(proc)
        assert proc.returncode != PROJECTION_NEVER, shown(proc)
        assert "UNKNOWN" in proc.stderr, shown(proc)
    assert state.psql_calls() == [], ("a reader connected under the refusal", state.psql_calls())
    assert state.origin_and_head() == before, "the files or origin moved"


# ------------------------------------- T256: the render fork's stub test
def release(fifo: Path) -> bool:
    """Let a call held on `fifo` go: open it for writing, which a held reader
    makes possible at once, and close it. False where nothing holds it."""
    try:
        fd = os.open(str(fifo), os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return False
    os.close(fd)
    return True


def within(seconds: float, find):
    """`find()` once it is truthy, or its last answer when `seconds` pass."""
    deadline = time.monotonic() + seconds
    found = find()
    while not found and time.monotonic() < deadline:
        time.sleep(0.05)
        found = find()
    return found


@pytest.mark.parametrize("case", list(FORK_CASES))
def test_a_primary_write_forks_render_checkout_on_the_lane_checkout_detached(estate, pg, case):
    """The render fork (phase W's stub test; TP:2612-2629; lane 4's section,
    "What phase 2 ships for phase 3", "The renderer fork"): after a primary
    write commits, the stand-in's log holds one `render` call, made by a
    detached fork, `render --checkout <c>`, `<c>` the writing lane's
    checkout, `<W>-lanes/<lane>/`; with no `LANES_NO_FETCH` in its
    environment though the verb ran with it in `[no-fetch-set]` (D12); made
    though `LANES_INDEX=off` is set in `[index-off-set]`, since
    `lane-worktrees` sets that variable on every call (Y:5717); with its stdin
    closed or `/dev/null` and its descriptors 3 to 9 closed, as
    `index_nudge`'s fork has them; and the writer exits with the verb's own
    code while the stand-in holds the call on a FIFO, so no fork waits."""
    world = Flipped(estate, pg)
    fifo = world.root / "render.fifo"
    os.mkfifo(str(fifo))
    (world.bin / HOLD_FILE).write_text(str(fifo) + "\n", encoding="utf-8")
    try:
        try:
            proc = world.write(f"test 14 - the render fork, {case}", timeout=90,
                               **world.routed(), **FORK_CASES[case])
        except subprocess.TimeoutExpired:
            pytest.fail("the writer did not exit while the render call was held: it waited for "
                        "its fork", pytrace=False)
        assert proc.returncode == 0, ("the verb's own code", shown(proc))

        def renders():
            return [c for c in calls(world.bin) if c["argv"][:1] == ["render"]]

        held = within(FORK_SECONDS, renders)
        assert len(held) == 1, ("one render call, made by the fork",
                                [c["argv"] for c in calls(world.bin)])
        call = held[0]
        argv = call["argv"]
        assert argv[:2] == ["render", "--checkout"] and len(argv) == 3, argv
        assert os.path.realpath(argv[2].rstrip("/")) == os.path.realpath(world.lane_checkout()), \
            ("<c> is the writing lane's checkout", argv[2], world.lane_checkout())
        assert "LANES_NO_FETCH" not in call["env"], ("the fork carries LANES_NO_FETCH", case)
        assert call["fds"]["0"] in ("closed", "devnull"), ("the fork's stdin is open", call["fds"])
        assert [n for n in range(3, 10) if call["fds"][str(n)] != "closed"] == [], \
            ("descriptors 3 to 9 are not all closed", call["fds"])
        assert not (world.bin / ENDS_LOG).exists(), \
            "the held render call ended before it was let go"
    finally:
        released = within(FORK_SECONDS, lambda: release(fifo))
    assert released, "no render call was held on the FIFO to let go"
    ended = within(FORK_SECONDS, lambda: (world.bin / ENDS_LOG).exists())
    assert ended, "the render call did not end once it was let go"


# ------------------------------------- T282: T124's cached module (AT-14)
#: T124's module (tasks:2853: "The module's name, `lanes_index_main.py` here,
#: is lane 1's to fix"), which T124's hunk in `flipped_copy` places beside the
#: copy (tasks:2876).
CACHED_MODULE = "lanes_index_main.py"

#: AT-14's marker module (tasks:2876): only cached bytecode built from it can
#: print this and exit 0.
MARKER_LINE = "cached-marker"
MARKER_SOURCE = ("import sys\nsys.stdout.write(" + repr(MARKER_LINE + "\n") + ")\n"
                 "sys.stdout.flush()\nsys.exit(0)\n")

#: AN ARGUMENT NO SUBCOMMAND TAKES, for the parity case's refused-argument run.
NOT_AN_ARGUMENT = "--t282-not-an-argument"

#: THE PARITY CASE'S ARGV PROBE (RX-26's (a)), test code that the case puts in
#: the launcher's own interpreter by a `.pth` in an overlay's site-packages,
#: since `-I` ignores `PYTHONPATH` and the user site but not the interpreter's
#: own site-packages; so T124's module carries no test seam. An audit hook
#: (PEP 578) records `sys.argv` at the `exec` of a code object named for the
#: module (its entry), and `[sys.argv[0]] + argv` at the first call of the
#: module's own `main(argv)` (its dispatch); a `compile` naming the module
#: tells the source form from the cached one. One record per process, by pid.
ARGV_PROBE = r'''# T282's argv probe (feature 007, AT-14): test code in a test's overlay.
import json, os, sys
_RECORDS = os.environ.get("T282_ARGV_RECORDS")
_NAME = "lanes_index_main.py"
if _RECORDS:
    _seen = {"entry": [], "dispatch": [], "compiled": False}

    def _hexes(vector):
        return [os.fsencode(item).hex() for item in vector]

    def _save():
        path = os.path.join(_RECORDS, "%d.json" % os.getpid())
        with open(path + ".new", "w", encoding="utf-8") as handle:
            json.dump(_seen, handle)
        os.replace(path + ".new", path)

    def _profile(frame, event, arg):
        code = frame.f_code
        if event == "call" and code.co_name == "main" and code.co_filename.endswith(_NAME):
            sys.setprofile(None)
            argv = frame.f_locals.get("argv")
            _seen["dispatch"].append(_hexes([sys.argv[0]] + list(argv if argv is not None else [])))
            _save()

    def _hook(event, args):
        try:
            if event == "exec" and str(getattr(args[0], "co_filename", "")).endswith(_NAME):
                _seen["entry"].append(_hexes(sys.argv))
                _save()
                sys.setprofile(_profile)
            elif event == "compile" and len(args) > 1 and str(args[1]).endswith(_NAME):
                _seen["compiled"] = True
                _save()
        except Exception:
            pass

    sys.addaudithook(_hook)
'''


def cached_module(state: Refusing) -> Path:
    """The module beside the refusing copy, asserted there: T124's hunk in
    `flipped_copy` places it (tasks:2853, :2876), so before T124 each T282
    case fails here, never at collection."""
    module = state.copy.parent / CACHED_MODULE
    assert module.is_file(), (
        f"no {CACHED_MODULE} beside the refusing copy {state.copy}: T124's launcher runs its "
        f"body from that module, which T124's hunk in `flipped_copy` places beside the copy "
        f"(tasks:2850-2854); T282's cases wait for T124")
    return module


def bytecode_path(module: Path) -> Path:
    """Where the launcher reads the module's bytecode: the interpreter's own
    `__pycache__` name for it (PEP 3147), as lane 1 measured "a launcher
    importing from `__pycache__`" (tasks:2853). The place is lane 1's to fix.
    It is built here as `lanes-index` builds it, never by `cache_from_source`,
    which follows `sys.pycache_prefix`: `tests/run.sh` exports
    `PYTHONPYCACHEPREFIX`, and under it that name is in the run's bytecode
    cache, where no launcher reads, so the cached runs ran the source."""
    tag = sys.implementation.cache_tag
    assert tag is not None, "this interpreter has no cache tag, so no launcher reads bytecode"
    return module.parent / "__pycache__" / f"{module.stem}.{tag}.pyc"


def checked_hash_pyc(code, source: bytes) -> bytes:
    """A checked-hash `.pyc` of `code` (PEP 552, flags 0b11) that carries the
    hash of `source`."""
    return (importlib.util.MAGIC_NUMBER + (0b11).to_bytes(4, "little")
            + importlib.util.source_hash(source) + marshal.dumps(code))


def module_code(module: Path, source=None):
    """`source` (the module's own bytes by default) compiled under the
    module's path, as the interpreter compiles a module."""
    text = module.read_bytes() if source is None else source
    return compile(text, str(module), "exec", dont_inherit=True)


def place_bytecode(module: Path, code) -> Path:
    """`code` as the module's checked-hash bytecode, with the hash of the
    module's bytes as they are now."""
    pyc = bytecode_path(module)
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(checked_hash_pyc(code, module.read_bytes()))
    return pyc


def set_aside(pyc: Path) -> None:
    """No bytecode at the module's place: what is there is moved aside, in
    the test's own estate."""
    if pyc.exists():
        os.replace(pyc, pyc.with_name(f"{pyc.name}.aside-{uuid.uuid4().hex}"))
    assert not pyc.exists(), pyc


def probe_python(state: Refusing) -> Path:
    """A `pyvenv.cfg` overlay of the interpreter the tests run on, in the
    estate, whose site-packages loads `ARGV_PROBE` by a `.pth`, under `-I`
    too. Returns its `bin`, which holds `python3`."""
    overlay = state.root / "argv-probe-python"
    bin_dir = overlay / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    real = Path(os.path.realpath(sys.executable))
    (overlay / "pyvenv.cfg").write_text(
        f"home = {real.parent}\ninclude-system-site-packages = false\n", encoding="utf-8")
    python = bin_dir / "python3"
    if not python.is_symlink():
        python.symlink_to(real)
    asked = subprocess.run([str(python), "-I", "-c", "import site; print(site.getsitepackages()[0])"],
                           capture_output=True, text=True, timeout=60)
    assert asked.returncode == 0, shown(asked)
    site_dir = Path(asked.stdout.strip())
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "t282_argv_probe.py").write_text(ARGV_PROBE, encoding="utf-8")
    (site_dir / "t282_argv_probe.pth").write_text("import t282_argv_probe\n", encoding="utf-8")
    loaded = subprocess.run([str(python), "-I", "-c", "import sys; print('t282_argv_probe' in sys.modules)"],
                            capture_output=True, text=True, timeout=60)
    assert loaded.stdout.strip() == "True", ("the overlay does not load the argv probe under -I",
                                             shown(loaded))
    return bin_dir


def start_by_path(state: Refusing, vector: list, env: dict) -> tuple:
    """`vector` started as `lanes-edit.sh` starts `lanes-index`, by its path,
    in the estate's root, with `env` over the estate's environment; returns
    the started process's pid, exit, stdout and stderr."""
    child = dict(state.e.env)
    for key, value in env.items():
        if value is None:
            child.pop(key, None)
        else:
            child[key] = value
    proc = subprocess.Popen([str(a) for a in vector], cwd=str(state.e.root), env=child,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        out, err = proc.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        raise AssertionError(f"{vector} did not end in 120 s", out[-2000:], err[-2000:])
    return proc.pid, proc.returncode, out, err


def usage_subcommands(usage: str) -> list:
    """Each subcommand `lanes-index`'s usage lists, in its order: a form's
    first word, or its first two for `register`'s."""
    found = []
    for line in usage.splitlines():
        words = line.split()
        if len(words) < 2 or words[0] != "lanes-index" or not re.fullmatch(r"[a-z][a-z-]*", words[1]):
            continue
        name = tuple(words[1:3]) if words[1] == "register" and len(words) > 2 else (words[1],)
        if name not in found:
            found.append(name)
    return found


def hexes(vector: list) -> list:
    return [os.fsencode(str(item)).hex() for item in vector]


#: WHETHER T124'S LAUNCHER READS THE MODULE'S BYTECODE AT ALL: on Python 3.11
#: and later. Lane 1's gate (#165 6894131980) adds `sys.version_info >= (3, 11)`
#: beside the launcher's cache-tag and `-O` tests, so on 3.9 and 3.10 it reads
#: no bytecode and runs the source, as tasks:2876 and TP:2660 state (lane 3's
#: ruling 2, #165 6885378657).
LAUNCHER_READS_BYTECODE = sys.version_info >= (3, 11)


def test_a_start_runs_the_cached_module_whose_checked_hash_matches_its_source(estate):
    """T282's first case (AT-14; tasks:2876): with a checked-hash `.pyc` built
    from a marker module that prints `cached-marker` and exits 0, carrying the
    hash of the real module's bytes, where the launcher reads the module's
    bytecode, the refusing copy's `lanes-index mode` prints `cached-marker`
    and exits 0, which only the cached bytecode can do, on Python 3.11 and
    later. On 3.9 and 3.10, where lane 1's gate has the launcher read no
    bytecode (`LAUNCHER_READS_BYTECODE`; #165 6894131980), it never prints
    `cached-marker`, and exits 78 with the text, as the source does
    (tasks:2876, TP:2660)."""
    state = Refusing(estate)
    module = cached_module(state)
    place_bytecode(module, module_code(module, MARKER_SOURCE))
    proc = state.index(state.copy, "mode")
    if LAUNCHER_READS_BYTECODE:
        assert (proc.returncode, proc.stdout) == (0, MARKER_LINE + "\n"), (
            "the start did not run the module's checked-hash cached bytecode", shown(proc))
        return
    assert MARKER_LINE not in proc.stdout + proc.stderr, (
        "the start ran the module's cached bytecode below Python 3.11, where lane 1's gate "
        "has the launcher read none", shown(proc))
    assert proc.returncode == exit_code("EXIT_CONFIG"), shown(proc)
    assert REFUSED_TEXT in proc.stderr, shown(proc)
    assert proc.stdout == "", shown(proc)


def test_a_start_never_runs_cached_bytecode_whose_source_has_changed(estate):
    """T282's second case (AT-14; tasks:2876): the same marker `.pyc`, and
    then one byte added to the module that leaves the source's behaviour
    unchanged, a trailing newline: the start never prints `cached-marker`,
    and exits 78 with the text, as the source does."""
    state = Refusing(estate)
    module = cached_module(state)
    config_code = exit_code("EXIT_CONFIG")
    place_bytecode(module, module_code(module, MARKER_SOURCE))
    with module.open("ab") as handle:
        handle.write(b"\n")
    proc = state.index(state.copy, "mode")
    assert MARKER_LINE not in proc.stdout + proc.stderr, (
        "the start ran cached bytecode whose source has changed", shown(proc))
    assert proc.returncode == config_code, shown(proc)
    assert REFUSED_TEXT in proc.stderr, shown(proc)
    assert proc.stdout == "", shown(proc)


def test_a_start_runs_the_module_source_where_it_has_no_bytecode(estate):
    """T282's third case (AT-14; tasks:2876): with no bytecode there, the
    start exits 78 with the text, its stdout, stderr and exit equal to those
    of a start with the module's own valid checked-hash bytecode."""
    state = Refusing(estate)
    module = cached_module(state)
    config_code = exit_code("EXIT_CONFIG")
    set_aside(bytecode_path(module))
    source_run = state.index(state.copy, "mode")
    assert source_run.returncode == config_code, shown(source_run)
    assert REFUSED_TEXT in source_run.stderr, shown(source_run)
    place_bytecode(module, module_code(module))
    cached_run = state.index(state.copy, "mode")
    assert ((source_run.returncode, source_run.stdout, source_run.stderr)
            == (cached_run.returncode, cached_run.stdout, cached_run.stderr)), (
        "with no bytecode", shown(source_run), "with its own", shown(cached_run))


def test_each_subcommand_answers_alike_from_the_cached_module_and_from_its_source(estate):
    """T282's parity case (AT-14; tasks:2876, TP:2566 and :2574): each
    subcommand in the usage, with `--help`, with an argument it refuses and in
    its plain form on the refusing state's configuration, is started by the
    launcher's path as the test spells it, once with the module's own
    checked-hash bytecode in place and once with none. In each run the argv is
    seen exactly once at the module's entry and once at its dispatch, each
    the exact vector given to the launcher, `argv[0]` included, byte for
    byte, never the interpreter or its options; the cached run compiles no
    module and the source run does; and each pair's argv, stdout, stderr and
    exit are equal, byte for byte. On Python 3.9 and 3.10, where lane 1's gate
    has the launcher read no bytecode (`LAUNCHER_READS_BYTECODE`; #165
    6894131980), both runs are the source's, so both compile the module, and
    the equalities still hold (tasks:2876, TP:2660). The list is read from the
    usage, so a subcommand added later is covered."""
    state = Refusing(estate)
    module = cached_module(state)
    pyc = bytecode_path(module)
    own = checked_hash_pyc(module_code(module), module.read_bytes())
    bin_dir = probe_python(state)
    records = state.root / "argv-records"
    records.mkdir(parents=True, exist_ok=True)
    env = state.env(PATH=state.e.path_with(bin_dir, state.psql_dir),
                    T282_ARGV_RECORDS=str(records))
    launcher = os.path.relpath(state.copy, state.e.root)

    def start(vector: list, form: str) -> tuple:
        if form == "cached":
            pyc.parent.mkdir(parents=True, exist_ok=True)
            pyc.write_bytes(own)
        else:
            set_aside(pyc)
        pid, code, out, err = start_by_path(state, vector, env)
        record = records / f"{pid}.json"
        assert record.is_file(), (
            f"{form}: nothing saw the argv of {vector}: the launcher runs the module's code by "
            f"`exec` of a code object named for it, which dispatches through its own `main(argv)` "
            f"(tasks:2853)", code, out[-2000:], err[-2000:])
        seen = json.loads(record.read_text(encoding="utf-8"))
        given = hexes(vector)
        assert len(seen["entry"]) == 1 and len(seen["dispatch"]) == 1, (form, vector, seen)
        assert seen["entry"][0] == given, (form, "entry", vector, seen)
        assert seen["dispatch"][0] == given, (form, "dispatch", vector, seen)
        assert seen["compiled"] is (form == "source" or not LAUNCHER_READS_BYTECODE), (
            f"{form}: the module was {'' if seen['compiled'] else 'not '}compiled", vector)
        return seen["entry"][0], code, out, err

    _argv, _code, usage, _err = start([launcher, "--help"], "source")
    subcommands = usage_subcommands(usage)
    assert ("mode",) in subcommands, ("the usage lists no `mode`", usage[-3000:])
    compared = 0
    for name in subcommands:
        for extra in (["--help"], [NOT_AN_ARGUMENT], []):
            vector = [launcher, *name, *extra]
            cached = start(vector, "cached")
            source = start(vector, "source")
            assert cached == source, (vector, "cached", cached, "source", source)
            compared += 1
    assert compared == 3 * len(subcommands), (compared, subcommands)
