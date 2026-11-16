# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test D9, the timeouts table, its phase-N rows (AT-D9, L2-N5;
section 4.4; T220), and lane 1's T106 case (R-F9-3)
(opensoft/openRepoTools#165).

LANE 1'S T106 ALONE, `test_postgres_store_register_roles_connect_by_their_own_
url_with_one_joined_request` (R-F9-3; lane 1, #165 6752661856), needs no
engine. It loads `lanes-index` in process, as `test_lanes_index.py`'s
`load_indexer` does, puts T203's register fake `psql` first on `PATH`, which
answers `psql --version` itself (T203b), sets an inherited `PGHOSTADDR`,
`PGSSLMODE=disable`, `PGOPTIONS` and `PGTARGETSESSIONATTRS`, and makes one
`request(statements, row)` call of two statements through
`PostgresStore(cfg, role)`, then one `_query_many(..., snapshot=True, row=...)`
call on the same store. It fails until lane 1's T106 lands: at `a2073eae`
`load_config` does not know `register_url=`, and `PostgresStore` has no
register role. Its `[J3]` word is `sql_register_bounds and
postgres_store_register_roles`.

- THE `--version` PROBE: T106 asks `psql --version` once per process
  (L1v4.10:152). T203b's fake answers it itself, `psql (PostgreSQL) 16.4`,
  and logs it as an entry of its own kind (`"kind": "version"`, no `call`),
  so the calls that carry a request are the entries with no such `kind`.
  This module's own `--version` wrapper, which T220 carried until T203b was
  in, is gone (T220d; F10's item 25).

D9'S PHASE-N ROWS are real-engine tests, on `tests/pgcluster.py`'s `pg`. The
test plan names the rows but gives them no ids, so each row has a word that
leads its id (the block's T220): `guard`, `answer-2`, `reader`,
`renderer-reads`, `reconcile`, `import`, `status`, `migration`,
`outage-probe` and `mode-query` here. T257, T278 and T237 add theirs to the
same two functions. The faults (AT-D9, "Fixture"):

- F1, a listener on loopback that accepts and never speaks (`SilentListener`);
- F2, a relay to the cluster's socket that goes silent once the startup has
  completed, at the server's first ReadyForQuery (`StartupRelay`);
- F3, an `ALTER TABLE` in an open transaction of the test's own session on
  the table the path reads, or, for a writer's commit, the head row held
  `FOR UPDATE` (`_hold_head`; T257f);
- F4, a slow statement the test creates in its own database: a row-level
  security policy that sleeps, for the path's group role. F4 is the second
  function's, `test_a_slow_statement_meets_57014_before_the_client_timer`.

`c` is 2 s and `N_a` 1: no configuration sets `connect_timeout=` or
`register_addresses=`. Each bound is asserted at twice its value, and the
guard's two rows under 4.5 s strictly; each measured time is recorded with
its margin (section 1.2's timing rules 1 to 3). The paths are lane 1's
commands, and lane 5's guard through `lanes-edit.sh guard`, from T203's
flipped copy where the path reads on primary. They fail until L1-A2, L1-A13,
L1-A15, L1-A18 and L5-A3 land, on T227's template and T228's logins; until
T228 a path's login is made here, in the row's group role.

THE GUARD'S TWO ROWS' SESSION (T203c's `guard_session`; T220d): today's guard
reads this workstation's session records after its workspace and tmux checks
and before any register read, and refuses 2 where none is live in its window.
So each guard row, `guard` and `answer-2`, is given a live session record
and a stand-in `tmux` by `guard_session(home, bin, checkout)` (the checkout
under `$HOME/projects`), its `env()` and its `hook_input()`, torn down by
`request.addfinalizer(session.close)`; and the case's base environment is
`guard_strip_env(os.environ)`, which takes `PROJECTS_ROOT` and
`AGENT_PROTOCOL_ROOT` out beside the lane's, the harness's, tmux's and
libpq's.

THE BENCH'S REGISTER NAMES THE LIVE SESSION (T220e): its `lanes/LANES.md` holds
one row, binding the lane's window `repoA-2` to `SID`, the id the guard
session is made with, in `test_lanes_index.py`'s row form (T203c's own unit
test uses it). So the guard's checks on the checkout's register all pass, and
what can refuse the prompt on the bench is the database alone. Without the row,
today's guard refuses 2 at its row check, "the register has no row for
`repoA-2`", which is also exit 2 within 4.5 s, so the guard rows would pass
against a guard that never reads the database. With it, today's guard lets the
prompt through, 0, and the guard rows fail by their exit assertion until L5-A3
and L5-A5 land.

THE TIMING WRAPPER (`TIMING_PSQL`): T203's shim records neither a call's
start time nor its stderr, so F4's oracle, "the call ending with 57014 ... no
earlier than the path's `statement_timeout` after the call's start", reads
this module's own wrapper in front of the real `psql`, which logs each
call's start and end on the monotonic clock and its stderr's first line.
Its first statement also stamps the call's begin, with its parent's pid, in
`psql-begin.log`, before it reads stdin, so a call its caller's timer kills
is stamped too (T220f).

THE SERVICE ROW'S F4 (T237y; line W3aX's finding on T237x): one guard run
meets a cold service, which answers `unavailable` until its `psql` has
connected (socket contract d8:502), and the service's connection is "one
long-lived `psql` child on pipes" (d8:229), which `TIMING_PSQL`, reading its
input to the end before it starts the real `psql`, can never run. So
`[service]`'s case starts `lanes-index serve` once, puts `STREAM_PSQL` first
on `PATH` in place of `TIMING_PSQL`, and warms the service with guard runs
until one is answered through it, with no fallback line (d8, section 5.3);
only then does it make F4's slow statement and run the guard again.
`STREAM_PSQL` starts the real `psql` at once and hands its input on chunk by
chunk, stamping each, so the held child runs through it; the 57014 timed is
the held child's, from the stamp of the request it was handed to its
`ERROR:  57014` line, at the request's 180 ms (lane 5's answer 3, #165
comment 6771208498; d8:214), the child known by its own argv's
`VERBOSITY=sqlstate` (d8:229).

`STATUS`'S TWO ROWS (T220f; lane 3's T220 bullet, #165 comment 6772120103,
and its ruling 6, 6770600106) time the register's request alone, from its
start to the exit, never from the command's start: `status` runs #160's half
first, whose `lanes-edit.sh` calls took 17 to 23 s each under load (lane 1's
T117 point 6, 6769905855). `[status-F1]`, `[status-F2]` and `[status-F3]`
take `Bench.request_elapsed()`: from the begin stamp of the first `psql` that
the command's own process starts on the register's path (its once-per-process
`psql --version`, which T117's `_run_register` counts inside the request's
client timer, or else the request's own call) to the command's exit.
`[status]`'s 57014 time was already the request's own call, from its start
to its end, as every row's is.

`[ANSWER-2-F1]` FOLLOWS A HEALTHY CALL (line BD-19b; lane 3's ruling, #165
6840828270, on TP:3586-3589). The guard's one prefetch is the first read of
every prompt, an answer to its offer included (T507), and answer 2 adds no
database call to the hook (Y:5417). So the case (`_answer_2_row`) makes the
offer on a healthy register first: the bench at `primary` with a second row,
`repoA-3` PAUSED on another session, and the session named `repoA-3`. Then
it sends `2` through `ArmedFault`, which arms F1 only once `TIMING_PSQL`'s
log shows that the hook's register read has ended. The hook must exit 2 with
"BINDING" under 4.5 s (TP:3595), with that read in the log and no register
call of its own after it (AT-F6 case 21, TP:6190-6191). The detached bind
meets F1 after the hook exits, bounded as AT-F6's fixture bounds its binds
(`LANES_BIND_BOUND_S`). The wrapper names each call's session
(`os.getsid`), and the bind runs in a session of its own (`setsid`), so the
hook's calls are told from the bind's.
"""

from __future__ import annotations

import json
import os
import pty
import re
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from importlib.machinery import SourceFileLoader
from pathlib import Path
from urllib.parse import quote

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280's reader, `tests/sql_register_gate.py`; T281
#: removes it in the last set). No `"*"` row: the module's waits share no task.
#: Each function or id waits for its owner's fails-until: T220's Order, T257's
#: (its As built line governs the ids it names; lane 3, #165 6877453897),
#: T278's, and T237's service ids. Lane 2's plan GP-24, v2.
SQL_REGISTER_GATE_TABLE = {
    "test_a_burst_of_ten_over_a_delayed_tls_link_commits_each_once_or_exits_75_with_nothing_written": ("T103", "T104", "T106", "T111", "T112", "T113", "T114", "T413", "T414", "T415", "T417"),  # T257; tasks:2451, :2455
    "test_a_connect_timeout_under_2_is_refused_at_load_config": ("T103", "T104", "T106", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_a_cutover_whose_call_expires_leaves_the_switch_unknown_and_its_rerun_reads_it_first": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_record_marker_that_expires_leaves_the_marker_adding_and_writes_refusing": ("T116", "T304", "T324", "T326", "T327", "T412", "T415"),  # T278; tasks:2558
    "test_a_register_path_drops_each_inherited_pg_variable_before_psql": ("T106",),  # T257; tasks:2455
    "test_a_rollback_that_keeps_losing_its_turn_exits_75_at_the_deadline_with_nothing_written": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_rollback_whose_first_call_expires_rereads_the_switch": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_slow_statement_meets_57014_before_the_client_timer": ("T103", "T115", "T117", "T121", "T507"),  # T220; tasks:2103
    "test_a_stray_ways_out_commit_call_is_in_doubt_like_a_writers": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_waiting_migration_gives_up_at_its_own_lock_timeout": ("T103", "T115", "T117", "T121", "T507"),  # T220; tasks:2103
    "test_an_orphaned_writer_transaction_is_ended_by_the_idle_bound": ("T103", "T104", "T106", "T112", "T413", "T414", "T415", "T417"),  # T257; tasks:2451, :2455
    "test_connect_timeout_and_register_addresses_set_each_calls_timer": ("T106",),  # T257; tasks:2451, :2455
    "test_each_database_path_exits_inside_its_bound": ("T103", "T115", "T117", "T121", "T507"),  # T220; tasks:2103
    "test_each_register_call_is_one_request": ("T103", "T104", "T106", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_import_and_reconcile_set_their_bounds_at_connect": ("T103", "T115", "T117", "T121", "T507"),  # T220; tasks:2103
    "test_over_a_delayed_tls_link_no_healthy_call_meets_its_timer": ("T103", "T104", "T106", "T111", "T112", "T113", "T114", "T413", "T414", "T415", "T417"),  # T257; tasks:2451, :2455
    "test_postgres_store_register_roles_connect_by_their_own_url_with_one_joined_request": ("T106",),  # T220; tasks:2103
    "test_the_aborts_call_that_expires_is_run_again_or_found_done_by_its_rerun": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_the_joined_snapshot_logs_one_statement_and_reads_byte_identical_to_the_one_by_one_form": ("T103", "T104", "T106", "T112", "T114", "T413", "T414", "T415", "T417"),  # T257; tasks:2451, :2455
    "test_the_lookups_tries_start_inside_the_window_and_end_in_3": ("T114", "T227", "T228"),  # T257; tasks:2451, :2455
    "test_the_lookups_wait_counts_from_the_snapshot_calls_end_and_gets_no_lr011": ("T103", "T104", "T106", "T111", "T112", "T113", "T114", "T413", "T414", "T415", "T417"),  # T257; tasks:2451, :2455
    "test_the_outage_declare_probe_ends_inside_its_bound_and_the_declaration_follows_the_rule": ("T103", "T115", "T117", "T121", "T507"),  # T220; tasks:2103
    "test_a_cutover_whose_call_expires_leaves_the_switch_unknown_and_its_rerun_reads_it_first[F3]": ("T116", "T304", "T324", "T326"),  # T278; tasks:2558
    "test_a_slow_statement_meets_57014_before_the_client_timer[cutover]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_slow_statement_meets_57014_before_the_client_timer[lookup]": ("T103", "T104", "T106", "T412", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_a_slow_statement_meets_57014_before_the_client_timer[record-marker]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_slow_statement_meets_57014_before_the_client_timer[rollback]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_slow_statement_meets_57014_before_the_client_timer[service]": ("T507", "T512", "T513"),  # T237; tasks:2297
    "test_a_slow_statement_meets_57014_before_the_client_timer[stray-calls]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_slow_statement_meets_57014_before_the_client_timer[stray-commit]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_slow_statement_meets_57014_before_the_client_timer[switch-to-files]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_a_slow_statement_meets_57014_before_the_client_timer[writer-commit-f2]": ("T103", "T104", "T106", "T412", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_a_slow_statement_meets_57014_before_the_client_timer[writer-snapshot]": ("T103", "T104", "T106", "T412", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_each_database_path_exits_inside_its_bound[answer-2-F1]": ("T103", "T115", "T117", "T121", "T502", "T507"),  # T220; tasks:2103
    "test_each_database_path_exits_inside_its_bound[cutover-F1]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_each_database_path_exits_inside_its_bound[lookup-F1]": ("T103", "T104", "T106", "T412", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_each_database_path_exits_inside_its_bound[record-marker-F1]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_each_database_path_exits_inside_its_bound[rollback-F1]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_each_database_path_exits_inside_its_bound[service-F1]": ("T507", "T512", "T513"),  # T237; tasks:2297
    "test_each_database_path_exits_inside_its_bound[service-F2]": ("T507", "T512", "T513"),  # T237; tasks:2297
    "test_each_database_path_exits_inside_its_bound[service-F3]": ("T507", "T512", "T513"),  # T237; tasks:2297
    "test_each_database_path_exits_inside_its_bound[snapshot-miss-F2]": ("T103", "T104", "T106", "T111", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_each_database_path_exits_inside_its_bound[stray-calls-F1]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_each_database_path_exits_inside_its_bound[stray-commit-F1]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_each_database_path_exits_inside_its_bound[switch-to-files-F1]": ("T116", "T304", "T324", "T326", "T327"),  # T278; tasks:2558
    "test_each_database_path_exits_inside_its_bound[whole-write-F3]": ("T103", "T104", "T106", "T412", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_each_database_path_exits_inside_its_bound[writer-commit-f2-F2]": ("T103", "T104", "T106", "T412", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_each_database_path_exits_inside_its_bound[writer-commit-f3-F3]": ("T103", "T104", "T106", "T412", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_each_database_path_exits_inside_its_bound[writer-snapshot-F1]": ("T103", "T104", "T106", "T412", "T413", "T414", "T415", "T417"),  # T257; tasks:2455
    "test_each_register_call_is_one_request[commit]": ("T112",),  # T257; tasks:2451
    "test_each_register_call_is_one_request[lookup]": ("T114",),  # T257; tasks:2451
    "test_each_register_call_is_one_request[snapshot-psql-14]": ("T111",),  # T257; tasks:2451
    "test_each_register_call_is_one_request[snapshot]": ("T111",),  # T257; tasks:2451
}

INDEXER = REPO / "lanes-index"
LANES_EDIT = REPO / "lanes-edit.sh"
#: The guard session's id, and the one register row that names it (T220e).
SID = "6b2f6c1e-3c1d-4b8e-9a4f-7d0e5a1b2c3d"
DOT = chr(0xB7)
REGISTER = "\n".join([
    "# LANES.md", "",
    "| lane | session id | workstation / env / user | started (UTC) | objects owned "
    "| handoff path | state |",
    "|---|---|---|---|---|---|---|",
    f"| `repoA-2` | harness `{SID}` | Eagle / test / brett | 2026-10-01T00:00Z | none "
    f"| handoffs/repoA-2.md | LIVE {DOT} 2026-10-01T02:00:00Z {DOT} working |",
    ""])
#: `[answer-2-F1]`'s register (line BD-19b): `REGISTER` and a second row,
#: `OFFER_TO`, PAUSED on another session, as AT-F6's estate writes its `TO`
#: row. The guard session is named `OFFER_TO` in the window `repoA-2`, whose
#: row names `SID`, so the guard's first prompt makes the offer.
OFFER_TO = "repoA-3"
OFFER_OTHER = "9d4c1b2a-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
REGISTER_OFFER = REGISTER + (
    f"| `{OFFER_TO}` | harness `{OFFER_OTHER}` | Eagle / test / brett | 2026-10-01T00:00Z "
    f"| none | handoffs/{OFFER_TO}.md | PAUSED {DOT} 2026-10-01T02:00:00Z {DOT} working |\n")
#: The detached bind's bound in `[answer-2-F1]`, in s, as AT-F6's fixture
#: sets it (`LANES_BIND_BOUND_S` for tests, TP:3595), and the longest the case
#: waits for the bind's outcome: the body's `timeout -k 10` at `bound_s - 10`,
#: the outer's sweep, and a margin.
ANSWER_2_BIND_S = 15
ANSWER_2_WAIT_S = 45
SCHEMA = "lanes_register"
#: `c` and `N_a` when no configuration sets them (D9; CLI4.10 section 2.4).
C, N_A = 2, 1

# =============================================================== lane 1's T106

#: Two statements, sent as ONE request (CLI4.10 section 2.3).
STATEMENTS = ["SELECT seq FROM register_head", "SELECT mode, marker_state FROM register_switch"]
#: CLI4.10:206, "the argv is §2.2's exactly" (lane 1, #165 6752661856).
REGISTER_ARGV = ["--no-psqlrc", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                 "-v", "VERBOSITY=verbose", "-v", "SHOW_CONTEXT=never"]
#: Inherited by the caller, and never to reach `psql` on a register path
#: (L1v4.10:147; lane 3's R-PG-1; NOTES question 26).
INHERITED = {"PGHOSTADDR": "192.0.2.9", "PGSSLMODE": "disable",
             "PGOPTIONS": "-c search_path=inherited", "PGTARGETSESSIONATTRS": "read-write"}
#: Each role: `PostgresStore`'s role, a D9 row of that role (T106's
#: `REGISTER_BOUNDS`: a writer's snapshot, a reader's read), and the keys and
#: login its connection comes from (L1v4.10:148-149; CLI4.10:211-214).
ROLES = {
    "register-writer": ("register_writer", "snapshot", "register_url", "register_passfile",
                        "t220_writer"),
    "register-reader": ("register_reader", "read", "reader_url", "reader_passfile",
                        "t220_reader"),
}


def load_indexer():
    """`lanes-index` as a module, fresh, as `test_lanes_index.py` loads it.
    Called inside a test, never at import."""
    import importlib.util
    loader = SourceFileLoader("lanes_index_bounds_module", str(INDEXER))
    spec = importlib.util.spec_from_loader("lanes_index_bounds_module", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _private(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    return path


@pytest.mark.parametrize("role", list(ROLES))
def test_postgres_store_register_roles_connect_by_their_own_url_with_one_joined_request(
        tmp_path, monkeypatch, role):
    """T106 alone (R-F9-3): one `request(statements, row)` call of two
    statements through `PostgresStore(cfg, role)` is ONE `psql` call that
    carries the request; its argv is exactly CLI4.10's list, with no `-d`
    and no URL; its connection is the role's own URL and password file, the
    reader's never the writer's; no inherited `PGHOSTADDR`, `PGSSLMODE` or
    `PGTARGETSESSIONATTRS` reaches it, and `PGOPTIONS` is not the inherited
    value; and its stdin is the two statements joined by `\\;`. Each URL is
    a loopback host with no query parameter, and each configuration carries
    `register_url=`, the reader's too, since a file with none is #160's.

    Then, on the same store, `_query_many(..., snapshot=True, row=<the
    role's row>)` (lane 1's choice (b), #165 comment 6754680212) makes ONE
    request and ONE `psql` call, besides the first; that call's stdin opens
    with `SET search_path TO <register_schema>` (L1v4.10:150), then has a
    `BEGIN`, and carries the marker `COPY (SELECT E'\\x1eLANES-INDEX-NEXT')
    TO STDOUT` (CLI4.10:234; L1v4.10:151). The writer's row is `snapshot`;
    T106's `bounds()` refuses that row for the reader ("a read never
    connects with the writer's credential"), so the reader's own row, `read`,
    is the one it sends."""
    from sql_register_helpers import REGISTER_FAKE_PSQL
    store_role, row, url_key, pass_key, login = ROLES[role]
    bindir = tmp_path / "bin"
    bindir.mkdir()
    # T203b: the fake answers `psql --version` itself, so it is `psql`.
    (bindir / "psql").write_text(REGISTER_FAKE_PSQL, encoding="utf-8")
    (bindir / "psql").chmod(0o755)
    passfiles = {"register_passfile": _private(tmp_path / "writer.pgpass"),
                 "reader_passfile": _private(tmp_path / "reader.pgpass")}
    config = _private(tmp_path / "conf" / "lanes-index.conf", "\n".join([
        "mode=index",
        "register_url=postgresql://t220_writer@127.0.0.1:55432/register_db",
        f"register_passfile={passfiles['register_passfile']}",
        "reader_url=postgresql://t220_reader@127.0.0.1:55432/register_db",
        f"reader_passfile={passfiles['reader_passfile']}",
        "register_schema=lanes_register_t220",
        ""]))
    log = tmp_path / "psql.log"
    for key in list(os.environ):
        if key.startswith("PG") or key in ("FAKE_PSQL_ANSWERS", "FAKE_PSQL_VERSION_FILE"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("LANES_INDEX_CONFIG", str(config))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("FAKE_PSQL_LOG", str(log))
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", os.defpath))
    for key, value in INHERITED.items():
        monkeypatch.setenv(key, value)

    mod = load_indexer()
    error = None
    try:
        store = mod.PostgresStore(mod.load_config(), store_role)
        store.request(list(STATEMENTS), row)
    except Exception as exc:  # the code under test, not this test, failed
        error = exc
    assert error is None, (f"PostgresStore(cfg, {store_role!r}).request(<2 statements>, "
                           f"{row!r}) raised {error!r}")

    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    calls = [r for r in records if r.get("kind") != "version"]
    assert len(calls) == 1, f"one psql call carries the request: {len(calls)}"
    call = calls[0]
    assert "refused" not in call, call["refused"]
    assert call["argv"] == REGISTER_ARGV
    pg = call["pg"]
    assert (pg.get("PGHOST"), pg.get("PGPORT"), pg.get("PGDATABASE"), pg.get("PGUSER")) == \
        ("127.0.0.1", "55432", "register_db", login), f"{url_key}='s mapping: {pg}"
    assert pg.get("PGPASSFILE") == str(passfiles[pass_key])
    other = "reader_passfile" if pass_key == "register_passfile" else "register_passfile"
    assert pg.get("PGPASSFILE") != str(passfiles[other])
    for key in ("PGHOSTADDR", "PGSSLMODE", "PGTARGETSESSIONATTRS"):
        assert key not in pg, f"the inherited {key} reached psql: {pg[key]!r}"
    assert pg.get("PGOPTIONS") != INHERITED["PGOPTIONS"], "the inherited PGOPTIONS reached psql"
    request = call["stdin"].strip()
    assert request.endswith(";") and "\n" not in request, f"one request: {call['stdin']!r}"
    assert [part.strip() for part in request[:-1].split("\\;")] == STATEMENTS

    requests, send = [], store.request

    def counted(statements, request_row, **kwargs):
        requests.append(request_row)
        return send(statements, request_row, **kwargs)
    store.request = counted
    error = None
    try:
        store._query_many(list(STATEMENTS), snapshot=True, row=row)
    except Exception as exc:  # the code under test, not this test, failed
        error = exc
    assert error is None, (f"PostgresStore(cfg, {store_role!r})._query_many(<2 queries>, "
                           f"snapshot=True, row={row!r}) raised {error!r}")
    assert requests == [row], f"one request carries the snapshot: {requests}"
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    calls = [r for r in records if r.get("kind") != "version"]
    assert len(calls) == 2, f"one more psql call carries the snapshot: {len(calls) - 1}"
    assert "refused" not in calls[1], calls[1]["refused"]
    parts = [part.strip() for part in calls[1]["stdin"].strip().rstrip(";").split("\\;")]
    # L1v4.10:150: the snapshot's `search_path` is `register_schema`.
    assert parts[0].startswith("SET search_path TO ") and "lanes_register_t220" in parts[0], parts[0]
    begin = [i for i, part in enumerate(parts) if part.startswith("BEGIN")]
    assert begin and begin[0] > 0, f"a BEGIN follows the search_path: {parts}"
    # CLI4.10:234 (L1v4.10:151): #160's `\echo` marker goes as a `COPY`.
    marker = r"COPY (SELECT E'\x1eLANES-INDEX-NEXT') TO STDOUT"
    assert marker in parts[begin[0]:], f"the COPY marker follows the BEGIN: {parts}"
    probes = [r for r in records if r.get("kind") == "version"]
    assert len(probes) <= 1, f"psql --version is asked once per process: {len(probes)}"


# ====================================================== D9's rows (real engine)

class SilentListener:
    """F1: a listener on loopback, port 0, that accepts and never speaks."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(64)
        self.port = self.sock.getsockname()[1]
        self.held, self.done = [], False
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()

    def _accept(self):
        self.sock.settimeout(0.2)
        while not self.done:
            try:
                conn, _ = self.sock.accept()
                self.held.append(conn)
            except OSError:
                continue

    def close(self):
        self.done = True
        for conn in self.held:
            conn.close()
        self.sock.close()


class StartupRelay(SilentListener):
    """F2: a relay on loopback to the cluster's Unix socket that forwards
    until the startup completes, at the server's first ReadyForQuery
    (`Z`, length 5), then goes silent, holding both ends open.

    `armed`, where given, is asked at each connection's accept (T257f;
    TP:3586-3589, "A row that follows a healthy call ... The test arms the
    fault once the shim's log shows the earlier call's end, so the call
    before it reaches the cluster"): a connection accepted while it answers
    False is relayed whole and never goes silent. Asked at the accept, it
    has no race with the caller: the timing wrapper logs a call's end before
    it hands the call's answer back. `silenced` counts the connections that
    went silent."""

    READY = re.compile(rb"Z\x00\x00\x00\x05[ITE]")

    def __init__(self, unix_path: str, armed=None):
        self.unix_path, self.armed, self.silenced = unix_path, armed, 0
        super().__init__()

    def _accept(self):
        self.sock.settimeout(0.2)
        while not self.done:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                continue
            fault = self.armed is None or bool(self.armed())
            upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            upstream.connect(self.unix_path)
            self.held += [conn, upstream]
            threading.Thread(target=self._pump, args=(conn, upstream, fault),
                             daemon=True).start()

    def _pump(self, client, server, fault=True):
        seen, silent = b"", False
        while not self.done:
            ready, _, _ = select.select([client, server], [], [], 0.2)
            for end in ready:
                try:
                    data = end.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                if silent:
                    continue
                if end is server:
                    seen = (seen + data)[-64:]
                    (client.sendall(data))
                    if fault and self.READY.search(seen):
                        silent = True
                        self.silenced += 1
                else:
                    server.sendall(data)


TIMING_PSQL = r'''#!/usr/bin/env python3
# T220's timing wrapper in front of the real psql: each call's start and end
# on the monotonic clock, its exit and its stderr's first line, one JSON
# object per call in psql-timing.log beside it. Its first statement stamps
# the call's begin, written with its parent's pid to psql-begin.log before
# it reads stdin, so a call its caller's timer kills is stamped too (T220f).
# Each logged call also says whether its request was a writer's snapshot, the
# one request that opens REPEATABLE READ (contract section 2.3), so a fault
# can be armed after the snapshot's end and an attempt's start found (T257f),
# and which of the register's write functions it called (T278). Each request
# is also stamped in psql-sent.log once read, before the real psql connects.
# Each logged call names its parent's pid too, the command that made it, so a
# missed snapshot's second request is told from a new attempt's (T257i).
# Each send stamp says whether its request is a snapshot, so a case can tell
# that a writer's SQL path ran even where the snapshot never ended (T257j).
# Each begin stamp and each logged call names its session, so a hook's own
# calls are told from those of a bind it detached with `setsid` (line BD-19b).
import time
begin = time.monotonic()
import json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "psql-begin.log"), "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": sys.argv[1:], "ppid": os.getppid(),
                             "sid": os.getsid(0), "begin": begin}) + "\n")
real = os.environ["T220_REAL_PSQL"]
data = sys.stdin.buffer.read() if sys.argv[1:] != ["--version"] else b""
KINDS = ("commit_write", "switch_to_files", "record_marker", "find_write")
if sys.argv[1:] != ["--version"]:
    # T278: the request read, stamped before the real psql connects, with the
    # write functions it calls, so a fault can be armed for one named call.
    with open(os.path.join(here, "psql-sent.log"), "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ppid": os.getppid(), "sent": time.monotonic(),
                                 "calls": [k for k in KINDS if k.encode() + b"(" in data],
                                 "snapshot": b"REPEATABLE READ" in data}) + "\n")
start = time.monotonic()
proc = subprocess.run([real] + sys.argv[1:], input=data, capture_output=True)
end = time.monotonic()
err = proc.stderr.decode("utf-8", "replace")
with open(os.path.join(here, "psql-timing.log"), "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": sys.argv[1:], "ppid": os.getppid(),
                             "sid": os.getsid(0),
                             "start": start, "end": end, "exit": proc.returncode,
                             "first": (err.strip().splitlines() or [""])[0],
                             "snapshot": b"REPEATABLE READ" in data,
                             "calls": [k for k in KINDS if k.encode() + b"(" in data]}) + "\n")
sys.stdout.buffer.write(proc.stdout)
sys.stderr.buffer.write(proc.stderr)
sys.exit(proc.returncode)
'''

STREAM_PSQL = r'''#!/usr/bin/env python3
# T237y's streaming wrapper in front of the real psql, for the service row's
# F4 case. Like TIMING_PSQL it stamps each call's begin in psql-begin.log
# before anything else, and logs a call that ends in psql-timing.log in
# TIMING_PSQL's form. Unlike it, it never reads its input to the end first:
# it starts the real psql at once and hands each chunk of stdin on as it
# comes, so the service's one long-lived psql child on pipes (d8:229) runs
# through it. Each chunk handed on is stamped, and each stderr line that
# names 57014 is logged in psql-stream.log with the stamp of the last chunk
# handed on before it: the held child's request, timed from its send to the
# server's answer. SIGINT, which the service sends on a request's expiry
# (d8:215), and SIGTERM go on to the real psql.
import time
begin = time.monotonic()
import json, os, signal, subprocess, sys, threading
here = os.path.dirname(os.path.abspath(__file__))


def log(name, record):
    with open(os.path.join(here, name), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


log("psql-begin.log", {"argv": sys.argv[1:], "ppid": os.getppid(), "begin": begin})
version = sys.argv[1:] == ["--version"]
# THE REAL psql: the bench's, or else the first psql on PATH that is not this
# wrapper, should the service hand its child a reduced environment.
real = os.environ.get("T220_REAL_PSQL") or next(
    (os.path.join(d, "psql") for d in os.environ.get("PATH", "").split(os.pathsep)
     if d and os.path.realpath(d) != os.path.realpath(here)
     and os.access(os.path.join(d, "psql"), os.X_OK)), "psql")
proc = subprocess.Popen([real] + sys.argv[1:],
                        stdin=subprocess.DEVNULL if version else subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
start = time.monotonic()
for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, lambda number, frame: proc.send_signal(number))
sent, lock, first = [], threading.Lock(), []


def feed():
    while True:
        chunk = os.read(0, 65536)
        if not chunk:
            break
        with lock:
            sent.append(time.monotonic())
        try:
            proc.stdin.write(chunk)
            proc.stdin.flush()
        except OSError:
            break
    try:
        proc.stdin.close()
    except OSError:
        pass


def out():
    while True:
        chunk = os.read(proc.stdout.fileno(), 65536)
        if not chunk:
            break
        os.write(1, chunk)


def err():
    for line in iter(proc.stderr.readline, b""):
        now = time.monotonic()
        os.write(2, line)
        text = line.decode("utf-8", "replace").strip()
        if text and not first:
            first.append(text)
        if "57014" in text:
            with lock:
                request = sent[-1] if sent else start
            log("psql-stream.log", {"argv": sys.argv[1:], "ppid": os.getppid(),
                                    "request": request, "error": now, "line": text})


if not version:
    threading.Thread(target=feed, daemon=True).start()
readers = [threading.Thread(target=out), threading.Thread(target=err)]
for reader in readers:
    reader.start()
code = proc.wait()
for reader in readers:
    reader.join()
log("psql-timing.log", {"argv": sys.argv[1:], "start": start, "end": time.monotonic(),
                        "exit": code, "first": (first or [""])[0]})
sys.exit(code if code >= 0 else 128 - code)
'''

#: D9'S PHASE-N ROWS (AT-D9's table; the block's T220): the word that leads
#: each id; how the path runs; the group role its login is in; its expected
#: exit; the design's bound on the elapsed time in s; whether that bound is
#: the guard's, strict (timing rule 1), or asserted at twice its value (rule
#: 2); the faults the first function gives it; its `statement_timeout` in ms
#: where it sets one (F4, the second function's); and the table its reads
#: wait on. `import` runs FP only for its 330 s timer, and has F1 alone.
ROWS = {
    "guard":          dict(group="lanes_register_reader", exit=2, bound=4.5, strict=True,
                           faults=("F1", "F2", "F3"), statement_ms=1500, table="register_head"),
    "answer-2":       dict(group="lanes_register_reader", exit=2, bound=4.5, strict=True,
                           faults=("F1",), statement_ms=None, table=None),
    "reader":         dict(group="lanes_register_reader", exit=69, bound=6, strict=False,
                           faults=("F1", "F2", "F3"), statement_ms=3000, table="register_head"),
    "renderer-reads": dict(group="lanes_register_reader", exit=None, bound=15, strict=False,
                           faults=("F1", "F2", "F3"), statement_ms=10000, table="register_head"),
    "reconcile":      dict(group="lanes_register_reader", exit=69, bound=15, strict=False,
                           faults=("F1", "F2", "F3"), statement_ms=10000, table="register_head"),
    "import":         dict(group="lanes_register_writer", exit=69, bound=330, strict=False,
                           faults=("F1",), statement_ms=None, table=None),
    "status":         dict(group="lanes_register_reader", exit=69, bound=8, strict=False,
                           faults=("F1", "F2", "F3"), statement_ms=5000, table="register_head"),
    "migration":      dict(group=None, exit=None, bound=None, strict=False,
                           faults=("F1",), statement_ms=None, table="register_head"),
    "outage-probe":   dict(group="lanes_register_writer", exit=0, bound=8, strict=False,
                           faults=("F1", "F2", "F3"), statement_ms=5000, table="register_switch"),
    "mode-query":     dict(group=None, exit=0, bound=2, strict=False,
                           faults=("F1",), statement_ms=None, table=None),
    # T237's row: the guard through the service, `lanes-index serve` started on
    # the same configuration, whose connection meets the fault; the guard's
    # request is answered `unavailable` and its direct read meets it too, so
    # the hook exits 2 inside its 4.5 s (lane 5's socket contract d8, section
    # 5.3's table). Its `statement_timeout` is a request's 180 ms, with
    # `lock_timeout` 150 ms, set in `PGOPTIONS` just inside the service's
    # 200 ms timer; only the image fetch differs, at 10 s and 1000 ms under an
    # 11 s timer (T237x; lane 5's answer 3, #165 comment 6771208498; d8:214,
    # d8:244). Its F4 case, `[service]`, warms the service first, then times
    # the held child's request through `STREAM_PSQL`, which streams (T237y,
    # `_service_57014`): `TIMING_PSQL` reads its stdin to the end before it
    # starts the real `psql`, so the held child (d8:229) never ran through it,
    # and T237w's case timed the guard's direct read (T237x's finding).
    "service":        dict(group="lanes_register_reader", exit=2, bound=4.5, strict=True,
                           faults=("F1", "F2", "F3"), statement_ms=180, table="register_head"),
    # T257's five rows (D9's timeouts table, test plan section 3's AT-D9):
    # a writer's snapshot, `S` 8 s, 69 at F1; the commit at F2, in doubt then
    # 3, at least `C` + `S` + `T_L` = 25 s from the commit call's start; the
    # commit at F3, 55P03 per attempt then 75 at the deadline
    # (`LANES_REGISTER_DEADLINE_S=3`), at most 3 + 8 + 8 = 19 s; the lookup,
    # `find_write`, 3 naming the id, its tries inside the 10 s window, each
    # to `T_L` 9 s; and a whole write, 75 at the deadline.
    #
    # LANE 3'S BATCH 7, ask (1) on T257a (T257f; #165, its analysis's
    # "R-F13-1, T257a's four readings"): the snapshot's and the commit's
    # `statement_timeout` is 5000 ms (CLI:250-251), the lookup's 6000 ms
    # (CLI:252). `whole-write` runs at F3, since F1 ends the first snapshot
    # with 69 (TP:3596), with its own cell: no attempt starts after the
    # deadline, and the run stays under `T_write` (`WHOLE_WRITE`). And the
    # commit's F2 is armed only once the timing log shows the snapshot's end
    # (TP:3586-3589), so the snapshot reaches the cluster and the commit
    # meets the relay; since T257i, at the commit's own send, so a missed
    # snapshot's second request reaches it too (lane 1's cut, #165
    # 6783051626). A writer's F3 is the head row held `FOR UPDATE`
    # (`_hold_head`; TP:3560-3561, "for a writer's commit, the head row held
    # `FOR UPDATE`"), which a snapshot's plain read does not wait on, so the
    # snapshot answers and each attempt's commit meets 55P03.
    #
    # THE COMMIT'S F4 (T257h; line BD9's finding on T257a): the second
    # function's `[writer-commit-f2]` meets a trigger on `journal` that
    # sleeps, which the commit's entry meets (`slow`), and the writer exits
    # 69, "a refusal the database made", not the F2 row's 3 (`f4_exit`;
    # TP:3621-3626 at B14). T257a's policy on `register_head` was met by the
    # snapshot's read first.
    "writer-snapshot":  dict(group="lanes_register_writer", exit=69, bound=8, strict=False,
                             faults=("F1",), statement_ms=5000, table="register_head"),
    "writer-commit-f2": dict(group="lanes_register_writer", exit=3, bound=25, strict=False,
                             faults=("F2",), statement_ms=5000, table="register_head",
                             f4_exit=69, slow=("journal", "INSERT")),
    "writer-commit-f3": dict(group="lanes_register_writer", exit=75, bound=19, strict=False,
                             faults=("F3",), statement_ms=None, table="register_head"),
    "lookup":           dict(group="lanes_register_writer", exit=3, bound=19, strict=False,
                             faults=("F1",), statement_ms=6000, table="register_head"),
    "whole-write":      dict(group="lanes_register_writer", exit=75, bound=19, strict=False,
                             faults=("F3",), statement_ms=None, table="register_head"),
    # T257g'S CACHE MISS (F13c's T257 bullet, R-F13c-18; lane 3's batch 7,
    # #165 6780364102, text change 18 and its ruling on T111's SHOULD-2,
    # option (b)): `register snapshot` misses the image cache, F2 is armed
    # once its first request ends, and its second request, the whole fetch
    # (Y:2515-2516), runs under what is left of `S` from the first request's
    # start, so the command ends 69 within `S`, 8 s (`_snapshot_miss`). It
    # runs on the imported register at `primary` (`Operator`): a snapshot
    # reads the switch first (its check 4), and a miss fetches from the
    # import. Its F4 is `writer-snapshot`'s, so it takes no id of the second
    # function (`SLOW_ROWS`).
    "snapshot-miss":    dict(group=None, exit=69, bound=8, strict=False,
                             faults=("F2",), statement_ms=5000, table="register_head"),
    # T257j: `writer-commit-f2`, `writer-commit-f3` and `whole-write` meet
    # their faults after the snapshot's check 4, which refuses any switch but
    # `primary` with the marker `present`; `pg` alone is a bootstrap-only
    # clone, its switch `files` with the marker `absent` and its head -1. So
    # they run on the imported register at `primary` (`Operator`, as T278's
    # rows and `snapshot-miss` do; `PRIMARY_WRITER_ROWS`), each with its id,
    # its fault and its expected exit unchanged. `writer-snapshot` meets its
    # F1 at the connect and its F4 at the snapshot's read, both before check
    # 4, so it stays on `Bench`.
    # T278'S SIX ROWS (AT-D9's table, TP:3600-3608; "The operator rows run the
    # real commands", TP:3627-3641): the operator's commands on test 7's
    # fixture register (`Operator`, below), each at F1, timed from the
    # faulted call's start. `rollback`, each call 15 s and 69, where step 1's
    # call and the switch's re-read both meet F1, 15 + 15 = 30 s; `cutover`,
    # its transaction 15 s, 69; `switch-to-files`, the cutover's abort,
    # reached by a cutover whose push the `git` wrapper fails, 15 s, 69;
    # `record-marker`, after the cutover's push and read-back, 15 s, 69; the
    # stray ways out's commit call (`stray-commit`), in doubt as a writer's,
    # then the lookup, 3, the commit's F2 row's 35.5 s; and their other calls
    # (`stray-calls`), the snapshot read, 69 in 8 s. Each `statement_timeout`
    # is lane 1's `REGISTER_BOUNDS`' (`rollback` and `cutover`, 10 s; the
    # ways out's calls, 5000 ms, TP:3607). The keys past `table`: `f4_exit`,
    # the outcome at F4 ("For a writer's commit that outcome is 69, a refusal
    # the database made", TP:3615-3617); `slow`, where F4's slow statement
    # sits (TP:3618-3624: a trigger on `journal` for the cutover, its abort
    # and the ways out's commit; on `register_switch` for `record_marker`; a
    # policy on `register_head` for the snapshot's read); `estate`; and
    # `after`, the healthy call before the faulted one, and `target`, the
    # faulted call, by the write function it calls. F1 is armed for `target`
    # at that call's own send, which `TIMING_PSQL` stamps before the real
    # `psql` connects: so "once the shim's log shows the earlier call's end"
    # (TP:3586-3589), and never earlier, whatever number of requests the
    # earlier call makes. A missed snapshot's second request (lane 1's cut,
    # `refs/l1/R-rulings` 8121903; lane 3's batch 7 SHOULD-2) is a snapshot
    # request still, and reaches the cluster.
    # `rollback`'s F4 is a trigger on `journal` (lane 3's batch 11 (7)(a),
    # #165 6783909985, which adds "the rollback's step 1" to TP's F4 list):
    # step 1 is `commit_write` with the `rollback` entry (T304), whose
    # `INSERT INTO journal` meets the trigger, as the cutover's entry does.
    # Its estate is `cutover-done` (T278d): T326's step 0 walks origin for the
    # cutover's marker commit, which `_to_primary` never pushes.
    "rollback":        dict(group=None, exit=69, bound=30, strict=False, faults=("F1",),
                            statement_ms=10000, table="journal", f4_exit=69,
                            slow=("journal", "INSERT"), estate="cutover-done", after=None,
                            target=None),
    "cutover":         dict(group=None, exit=69, bound=15, strict=False, faults=("F1",),
                            statement_ms=10000, table="journal", f4_exit=69,
                            slow=("journal", "INSERT"), estate="imported", after=None,
                            target=None),
    "switch-to-files": dict(group=None, exit=69, bound=15, strict=False, faults=("F1",),
                            statement_ms=10000, table="journal", f4_exit=69,
                            slow=("journal", "DELETE"), estate="imported",
                            after="commit_write", target="switch_to_files"),
    "record-marker":   dict(group=None, exit=69, bound=15, strict=False, faults=("F1",),
                            statement_ms=10000, table="register_switch", f4_exit=69,
                            slow=("register_switch", "UPDATE"), estate="imported",
                            after="commit_write", target="record_marker"),
    "stray-commit":    dict(group=None, exit=3, bound=35.5, strict=False, faults=("F1",),
                            statement_ms=5000, table="journal", f4_exit=69,
                            slow=("journal", "INSERT"), estate="stray", after="snapshot",
                            target="commit_write"),
    "stray-calls":     dict(group=None, exit=69, bound=8, strict=False, faults=("F1",),
                            statement_ms=5000, table="register_head", f4_exit=69,
                            slow=("register_head", "policy"), estate="stray", after=None,
                            target=None),
}
#: T278's rows, which `Operator` runs, not `Bench`.
OPERATOR_ROWS = ("rollback", "cutover", "switch-to-files", "record-marker", "stray-commit",
                 "stray-calls")
#: T257a's writer rows that `Operator`'s estate at `primary` runs (T257j).
PRIMARY_WRITER_ROWS = ("writer-commit-f2", "writer-commit-f3", "whole-write")

#: The whole write's own cell (TP's "a whole write" row; T257f): at
#: `LANES_REGISTER_DEADLINE_S=3`, no attempt starts after the deadline, and
#: from the first attempt's start the run takes at most the deadline + `S` +
#: `C` = 3 + 8 + 8 = 19 s (`ROWS`' bound, asserted at twice it), and in no
#: case over `T_write` = 62.5 + 3 * `N_a` * `c` s, 68.5 s here.
WHOLE_WRITE = dict(deadline_s=3, t_write_s=62.5 + 3 * N_A * C)
#: The rows whose F3 is the head row held `FOR UPDATE`, a writer's commit's.
HEAD_HELD_F3 = ("writer-commit-f3", "whole-write")

FIRST_CASES = [f"{row}-{fault}" for row, spec in ROWS.items() for fault in spec["faults"]]
SLOW_ROWS = [row for row, spec in ROWS.items()
             if spec["statement_ms"] and row not in ("import", "snapshot-miss")]

#: THE SERVICE ROW'S STATE HOME: SHORT, AND OUTSIDE THE TEMPORARY ROOT. The
#: service's one socket is `${XDG_STATE_HOME}/openRepoTools/run/register.sock`
#: (socket contract d8, section 2.1): `serve` binds it, and the guard's read
#: connects to it. `sun_path` holds 107 bytes on Linux and 103 on macOS, and
#: the contract's `serve` refuses a path over 103 bytes (`path-too-long`,
#: exit 2). Under the bench's `tmp_path` the path followed the temporary root,
#: about 147 bytes on the runner, where lane 1's guard rerun met `OSError:
#: AF_UNIX path too long` (verify-r5-c2b, CI run 43140203269; line AN14). So
#: the `service` row's `XDG_STATE_HOME`, for `serve` and for the guard runs it
#: answers alike, is a `mkdtemp` of the bench's own in `/tmp`, as line G's
#: estates make theirs (T213i): `/tmp/l2bd-` and mkdtemp's 8 characters, 18
#: bytes, which puts the socket at 50 whatever `TMPDIR` or `--basetemp` is.
#: The bench removes it when the test ends (`Bench.service_env`). No other row
#: starts `serve`, so every other row keeps the bench's state home.
STATE_PARENT = "/tmp"
STATE_PREFIX = "l2bd-"
#: The contract's bound on the socket's path, in bytes (section 2.1).
SOCKET_MAX = 103


class Bench:
    """One test's bench: a scratch workspace with a bare origin, the lane's
    checkout and W, a clone of its own (T220h), a copy of
    `lanes-edit.sh` beside T203's flipped `lanes-index` (the copy rule, CLI4.5
    section 6), a configuration naming the endpoint the fault gives, a login
    of the row's group where it needs one, and the timing wrapper first on
    `PATH`. For the guard's two rows it also makes a live session record and
    a stand-in `tmux` (`guard_session`, T203c) when the row is run.
    `register` is the text of the register at C (`REGISTER`), and `name` the
    guard session's name (the window's where None); `[answer-2-F1]` passes
    both (line BD-19b)."""

    def __init__(self, pg, tmp_path: Path, request, *, register: str = REGISTER,
                 name: str | None = None):
        from sql_register_helpers import flipped_copy, guard_strip_env
        self.pg, self.root, self.name = pg, tmp_path, name
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.copy = flipped_copy(INDEXER, tmp_path / "tool", True)
        for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
            if (REPO / name).exists():
                shutil.copy2(REPO / name, tmp_path / "tool" / name)
        (self.bin / "psql").write_text(TIMING_PSQL, encoding="utf-8")
        (self.bin / "psql").chmod(0o755)
        self.timing = self.bin / "psql-timing.log"
        self.passfile = _private(tmp_path / "conf" / "pgpass")
        self.origin = tmp_path / "origin.git"
        # THE LANE'S CHECKOUT IS UNDER `$HOME/projects` (HOME is `tmp_path`
        # below), so that the guard's scope test (`under_projects_root`,
        # clause (e)) lets the prompt through to its reads; outside it the
        # guard returns 0 before reading anything (line W4a's T215b).
        self.wip = tmp_path / "projects" / "wip"
        self.wip.parent.mkdir(parents=True)
        #: W, the workspace checkout (Amendment 9(a)), a clone of its own.
        self.w = tmp_path / "W"
        # THE BASE ENVIRONMENT, T203c's: the lane's, the harness's, tmux's and
        # libpq's variables out, and `PROJECTS_ROOT` and `AGENT_PROTOCOL_ROOT`
        # with them (F10's item 28), which would move the guard's scope test
        # and `workspace.yaml` away from this bench's `$HOME`.
        env = guard_strip_env(os.environ)
        env.update(HOME=str(tmp_path), XDG_STATE_HOME=str(tmp_path / "state"),
                   XDG_CONFIG_HOME=str(tmp_path / "config"), TMPDIR=str(tmp_path),
                   LANES_WORKSTATION="Eagle", LANES_NO_GITHUB="1", LANES_REPO=str(self.wip),
                   LANES_WORKSPACE_ROOT=str(self.w),
                   T220_REAL_PSQL=pg.psql_bin, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
                   PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", os.defpath))
        self.env = env
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)],
                       check=True, env=env)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.wip)], check=True,
                       env=env, capture_output=True)
        (self.wip / "lanes" / "log").mkdir(parents=True)
        (self.wip / "lanes" / "LANES.md").write_text(register, encoding="utf-8")
        for argv in (["add", "-A"], ["commit", "-q", "-m", "C"], ["push", "-q", "origin", "main"]):
            subprocess.run(["git", *argv], cwd=str(self.wip), check=True, env=env,
                           capture_output=True)
        # THE WORKSPACE, W (Amendment 9(a)), is a clone of its own at C, never
        # the lane's checkout that `LANES_REPO` names: `import` refuses a
        # `LANES_REPO` that names W, or one set where W cannot be read
        # (contract 4.18:987; lane 1's group 6, #165 6807494089), and `status`
        # and `reconcile` read W's `origin/main`. `lanes-edit.sh
        # workspace-root` answers W by `LANES_WORKSPACE_ROOT`, its test seam,
        # and `workspace.yaml`'s `path:` names the same W.
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.w)], check=True,
                       env=env, capture_output=True)
        (tmp_path / ".agents").mkdir()
        (tmp_path / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.w}\n", encoding="utf-8")
        self.c = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(self.wip), env=env,
                                capture_output=True, text=True, check=True).stdout.strip()
        self.request = request
        self.session = None
        self.service_state = None

    def to_primary(self) -> None:
        """THE BENCH'S DATABASE AT `primary` WITH THE MARKER `present` (T257m;
        line BD-18): the bench's own C imported by lane 1's `lanes-index
        import --at <C>` (T115) as the operator lane, from its checkout, as
        the superuser on the cluster's socket, as test 7's `FixtureRegister`
        imports; then AT-LR006's route, the import module's `_to_primary`
        (TP:4610-4615 at B14), as T257j's writer rows' `Operator` estate takes
        it. A writer's snapshot refuses at its check 4 on any other switch,
        and `pg` alone, or a TLS cluster's database, is a bootstrap-only
        clone, its switch `files` with the marker `absent` and its head -1
        (line BD17's run of the lookup's wait). Made with `TIMING_PSQL` off
        `PATH`, so the timing and begin logs hold the case's own calls alone.
        Only the cases whose writers commit call it."""
        from types import SimpleNamespace
        from test_sql_register_import import _to_primary
        url = self.pg.url()
        config = _private(self.root / "conf" / "import" / "lanes-index.conf", "\n".join([
            "mode=index", f"register_url={url}", f"register_passfile={self.passfile}",
            f"reader_url={url}", f"reader_passfile={self.passfile}",
            "register_label=register-test", f"register_schema={SCHEMA}", ""]))
        env = dict(self.env, LANES_INDEX_CONFIG=str(config), LANES_LANE="repoA-2",
                   PATH=os.environ.get("PATH", os.defpath))
        proc = subprocess.run([sys.executable, str(INDEXER), "import", "--at", self.c],
                              capture_output=True, text=True, env=env, cwd=str(self.wip),
                              timeout=400, stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, \
            f"the bench's import --at C (lane 1's T115): {proc.returncode}: {proc.stderr}"
        tree = subprocess.run(["git", "rev-parse", f"{self.c}:lanes"], cwd=str(self.wip),
                              env=self.env, capture_output=True, text=True,
                              check=True).stdout.strip()
        _to_primary(self.pg, SimpleNamespace(c=self.c, tree=lambda sha: tree), load_indexer())

    def lane_checkout(self) -> Path:
        """`<c>`, lane `repoA-2`'s own register checkout, made once (T257l; lane 4's triage,
        #165 6833813092, its group b1): on primary a write runs from it, and where it is not there
        the write refuses with nothing sent (`lanes-edit.sh`'s `pw_checkout`, T415's R17), since a
        clone is a fetch (D12). It sits where `lane_checkout_path` puts it (Amendment 23 S1),
        `<W>-lanes/<lane>`, W being the real path of this bench's W, which `LANES_WORKSPACE_ROOT`
        names; and it is a clone of W's origin, as `lane-checkout <lane> --create` makes one and
        as `test_sql_register_writes.py`'s `make_lane_checkout` makes it. The bench makes `<c>`
        itself, because `lane-start` makes it only under `LANES_ROUTE_WRITES=1` with neither
        `LANES_REPO` nor `LANES_FILE` set (lane 3, #165 6841265575;
        `dfc4ce4c:lane-start:1209-1210`). A bench that runs no writer makes none."""
        real = Path(os.path.realpath(self.w))
        target = real.parent / f"{real.name}-lanes" / "repoA-2"
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "-q", str(self.origin), str(target)], check=True,
                           env=self.env, capture_output=True, stdin=subprocess.DEVNULL)
        return target

    def guard_session(self):
        """The guard rows' live session (T203c): a record on this workstation
        for a live pid, and a stand-in `tmux` that answers the guard's window
        queries, written to this bench's `bin`, for the checkout under
        `$HOME/projects`, with `SID`, the id the bench's register row names
        (T220e), named `self.name` where the bench was given one. Made once,
        torn down when the test ends."""
        from sql_register_helpers import guard_session
        if self.session is None:
            self.session = guard_session(self.root, self.bin, self.wip, session_id=SID,
                                         name=self.name)
            self.request.addfinalizer(self.session.close)
        return self.session

    def login(self, group: str, floors: bool = False) -> str:
        """A login of `group`, made here until T228's logins exist. With
        `floors`, a writer login also takes the writer's floors that `login
        add` sets on each writer login (design.md section 1.4's login step,
        Y:2302-2309; `lanes-index`'s `_REGISTER_LOGIN_BLOCK`): `lock_timeout`
        2000 ms, `statement_timeout` 5 s and `idle_in_transaction_session_
        timeout` 5 s, the login's own, so a session that sets none of them
        has them, as the idle bound's held session needs (T257m; line
        BD-18). A register call's own bounds ride `PGOPTIONS`, which a
        login's settings never override."""
        name = f"t220_{uuid.uuid4().hex[:12]}"
        self.pg.psql(f"CREATE ROLE {name} LOGIN IN ROLE {group};")
        self.request.addfinalizer(lambda: self.pg.cluster.psql(f"DROP ROLE IF EXISTS {name};",
                                                               check=False))
        if floors:
            assert group == "lanes_register_writer", f"the writer's floors, on {group}"
            self.pg.psql(f"ALTER ROLE {name} SET lock_timeout = '2000ms';\n"
                         f"ALTER ROLE {name} SET statement_timeout = '5s';\n"
                         f"ALTER ROLE {name} SET idle_in_transaction_session_timeout = '5s';\n")
        return name

    def config(self, host: str, port: int, user: str, mode: str = "primary") -> Path:
        """A configuration whose two URLs name `host:port` and this test's
        database, as `user`; no `connect_timeout=` or `register_addresses=`,
        so `c` is 2 and `N_a` 1."""
        url = f"postgresql://{user}@{host}:{port}/{self.pg.name}"
        return _private(self.root / "conf" / "lanes-index.conf", "\n".join([
            f"mode={mode}", f"register_url={url}", f"register_passfile={self.passfile}",
            f"reader_url={url}", f"reader_passfile={self.passfile}",
            "register_label=register-test", f"register_schema={SCHEMA}", ""]))

    def run(self, row: str, config: Path, *, stdin: str | None = None,
            service: subprocess.Popen | None = None) -> tuple:
        """Run `row`'s path; return (the process, its elapsed seconds). The
        `service` row starts `lanes-index serve` for this run alone, unless the
        caller passes the one it holds (T237y), and runs under the service's
        short state home (`service_env`), as that `serve` does."""
        env = dict(self.env, LANES_INDEX_CONFIG=str(config), LANES_LANE="repoA-2")
        tool = self.copy.parent
        index = [sys.executable, str(self.copy)]
        if row in ("guard", "answer-2", "service"):
            argv = ["bash", str(tool / "lanes-edit.sh"), "guard"]
            # THE SESSION (T203c): a live record in the window `repoA-2` and a
            # stand-in `tmux`, so that the guard gets past its session-record
            # check, clause (d), to its register read. The hook's JSON is
            # compact, as the harness sends it: the guard's `jstr` reads
            # `"cwd":"<dir>"` with no blank after the colon.
            session = self.guard_session()
            env = session.env(env)
            stdin = session.hook_input("2" if row == "answer-2" else "hello")
            if row == "service":
                env = self.service_env(env)
        elif row == "reader":
            argv = index + ["register", "read", "--prefetch", "--cache",
                            str(self.root / "cache" / "reg"), "--files", "register,aliases"]
            (self.root / "cache").mkdir(exist_ok=True)
        elif row == "renderer-reads":
            argv = index + ["journal", "--since", "0"]
        elif row == "reconcile":
            argv = index + ["reconcile"]
        elif row == "import":
            argv = index + ["import", "--at", self.c]
        elif row == "status":
            argv = index + ["status"]
        elif row == "outage-probe":
            # `--mirror-seq 0` (T220g; T218g's, line RE's A15): on Brett's word
            # with no `--mirror-seq`, the declare reads the mirror's `m` after
            # a fetch (F11), and this bench's origin holds no `Register-Seq`,
            # so it would refuse 2, "no mirror-seq". 0 is T218g's value, which
            # lane 1's code takes as any whole number. No closed port: the
            # row's own fault keeps the probe from an answer.
            argv = index + ["outage", "declare", "--until", "2999-01-01T00:00:00Z",
                            "--why", "D9's probe row", "--mirror-seq", "0"]
        elif row == "mode-query":
            argv = index + ["mode"]
        elif row == "writer-snapshot":
            # A WRITER'S WHOLE PATH, `set-row-state` on the bench's lane, whose
            # snapshot meets the fault; the deadline is D9's test value. A
            # reading: T257's text names the rows, not the verb that carries
            # them. The writer rows whose fault comes after the snapshot's
            # check 4 run on `Operator`'s estate (`Operator.write`; T257j).
            argv = ["bash", str(tool / "lanes-edit.sh"), "set-row-state", "repoA-2",
                    f"PAUSED {DOT} T257's writer row"]
            env = dict(env, LANES_REGISTER_DEADLINE_S="3", LANES_LANE="repoA-2")
            self.lane_checkout()
        elif row == "lookup":
            # THE LOOKUP'S FORM (AT-F6 case 19; lane 1's T114, `refs/l1/T114-fu3`):
            # `journal --write-id <id> --not-after <epoch s> --generation <g>
            # --lane <l> --verb <v> --args-sha256 <h>`, for a write the database
            # never saw. `--not-after` is epoch seconds, a minute past, so a
            # healthy try would answer `absent`, never LR011; with no `--clock`
            # the client calls at once (T257c; T257a's UTC text was usage, 64).
            self.write_id = str(uuid.uuid4())
            argv = index + ["journal", "--write-id", self.write_id, "--not-after",
                            str(int(time.time()) - 60), "--generation", str(uuid.uuid4()),
                            "--lane", "repoA-2", "--verb", "set-row-state", "--args-sha256",
                            "0" * 64]
        else:
            raise AssertionError(f"no path for {row}")
        serve = None
        if row == "service" and service is None:
            serve = self.start_service(env)
        try:
            # `subprocess.run`'s form, with the command's pid and its exit
            # stamp kept for `request_elapsed` (T220f).
            start = time.monotonic()
            with subprocess.Popen(argv, stdin=subprocess.PIPE if stdin is not None
                                  else subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, env=env,
                                  cwd=str(self.wip)) as child:
                self.pid = child.pid
                try:
                    out, err = child.communicate(stdin, timeout=700)
                except subprocess.TimeoutExpired:
                    child.kill()
                    raise
                self.exited = time.monotonic()
            proc = subprocess.CompletedProcess(argv, child.returncode, out, err)
            return proc, self.exited - start
        finally:
            if serve is not None:
                self.stop_service(serve)

    def calls(self) -> list:
        if not self.timing.exists():
            return []
        return [json.loads(l) for l in self.timing.read_text(encoding="utf-8").splitlines()
                if l and json.loads(l)["argv"] != ["--version"]]

    def request_elapsed(self) -> float:
        """`status`'s time (T220f; lane 3's T220 bullet, #165 comment
        6772120103): from the register's request's start to the command's
        exit, never from the command's start, since #160's half runs first
        (lane 1's T117 point 6, 6769905855). The stamp lane 2 chooses is the
        begin stamp of the first `psql` that the command's own process starts
        on the register's path: its once-per-process `psql --version`, which
        T117's `_run_register` counts inside the request's client timer, or
        else the call with section 2.2's argv. A `psql` started by another
        process, or with #160's argv, is not the request's."""
        log = self.bin / "psql-begin.log"
        begins = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] \
            if log.exists() else []
        own = [b["begin"] for b in begins if b["ppid"] == self.pid
               and b["argv"] in (["--version"], REGISTER_ARGV)]
        assert own, "the command started no psql on the register's path: no request was sent"
        return self.exited - min(own)

    def begins(self) -> list:
        """The begin stamps (T220f) of each `psql` call that the command's own
        process started with section 2.2's argv, in order: a call its client
        timer killed is stamped too, though it never reaches the timing log
        (T257c)."""
        log = self.bin / "psql-begin.log"
        begins = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] \
            if log.exists() else []
        return [b for b in begins if b["ppid"] == self.pid and b["argv"] == REGISTER_ARGV]

    def guard_env(self, config: Path) -> dict:
        """The guard rows' environment for `config`, as `run` makes it: the
        bench's, the configuration, the lane, and the live session's."""
        env = dict(self.env, LANES_INDEX_CONFIG=str(config), LANES_LANE="repoA-2")
        return self.guard_session().env(env)

    def service_env(self, env: dict) -> dict:
        """`env` with the `service` row's state home (`STATE_PREFIX`): one
        short directory of this bench's own in `/tmp`, made at the first call
        and removed when the test ends, so `serve` and the guard runs it
        answers share one socket path within `SOCKET_MAX` bytes."""
        if self.service_state is None:
            home = Path(tempfile.mkdtemp(prefix=STATE_PREFIX, dir=STATE_PARENT))
            self.request.addfinalizer(lambda: shutil.rmtree(home, ignore_errors=True))
            sock = home / "openRepoTools" / "run" / "register.sock"
            assert len(os.fsencode(str(sock))) <= SOCKET_MAX, \
                f"the service's socket path {sock} is over {SOCKET_MAX} bytes"
            self.service_state = home
        return dict(env, XDG_STATE_HOME=str(self.service_state))

    def start_service(self, env: dict) -> subprocess.Popen:
        """`lanes-index serve` on `env`, returned once its socket is bound at
        the one socket path (socket contract d8, section 2.1)."""
        sock = Path(env.get("XDG_STATE_HOME", str(Path(env["HOME"]) / ".local" / "state"))) \
            / "openRepoTools" / "run" / "register.sock"
        serve = subprocess.Popen([sys.executable, str(self.copy), "serve"], env=env,
                                 cwd=str(self.wip), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
        end = time.monotonic() + 10
        while not sock.exists() and time.monotonic() < end and serve.poll() is None:
            time.sleep(0.05)
        if not sock.exists():
            self.stop_service(serve)
        assert sock.exists(), f"lanes-index serve bound no socket at {sock}: {serve.poll()}"
        return serve

    @staticmethod
    def stop_service(serve: subprocess.Popen) -> None:
        serve.terminate()
        try:
            serve.wait(10)
        except subprocess.TimeoutExpired:
            serve.kill()

    def stream(self) -> None:
        """`STREAM_PSQL` first on `PATH` in place of `TIMING_PSQL` (T237y)."""
        (self.bin / "psql").write_text(STREAM_PSQL, encoding="utf-8")
        (self.bin / "psql").chmod(0o755)

    def streamed(self) -> list:
        """`STREAM_PSQL`'s 57014 lines, each with its request's send stamp."""
        log = self.bin / "psql-stream.log"
        return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] \
            if log.exists() else []


def _record(row: str, elapsed: float, bound: float, rule: str) -> None:
    """Timing rule 2's record: the measured time, the design's bound, its
    margin."""
    print(f"D9 {row}: {elapsed:.2f} s against the design's {bound:g} s ({rule}); "
          f"margin {bound - elapsed:+.2f} s")


def _hold(pg, table: str):
    """F3: an `ALTER TABLE` on `table` in an open transaction of the test's
    own session, held until the session is closed. Returns the session once
    the lock is granted."""
    session = pg.session(appname="t220-f3")
    session.stdin.write(f"BEGIN;\nALTER TABLE {SCHEMA}.{table} ADD COLUMN t220_f3 integer;\n")
    session.stdin.flush()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        held = pg.psql("SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a USING (pid) "
                       "WHERE a.application_name = 't220-f3' AND l.granted "
                       "AND l.mode = 'AccessExclusiveLock';").stdout.strip()
        if held not in ("", "0"):
            return session
        time.sleep(0.1)
    session.kill()
    raise AssertionError("F3's lock was never granted")


def _end(session) -> None:
    try:
        session.stdin.write("ROLLBACK;\n")
        session.stdin.close()
        session.wait(timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        session.kill()


@pytest.mark.parametrize("case", FIRST_CASES)
def test_each_database_path_exits_inside_its_bound(pg, tmp_path, request, case):
    """D9: each phase-N path exits with its row's expiry outcome inside its
    bound, under F1 (a silent listener, met at the connect), F2 (a relay
    silent after the startup) and F3 (a lock on the table it reads). It owns
    test 10's per-path cases (section 4.4). `migration` is the dedicated
    test's below, `test_a_waiting_migration_gives_up_at_its_own_lock_timeout`,
    and its F1 case here is the migration's connect, through T109's
    `bootstrap` (`_migration`)."""
    row, fault = case.rsplit("-", 1)
    spec = ROWS[row]
    if row in OPERATOR_ROWS:
        _operator_row(pg, tmp_path, request, row, fault)
        return
    if row == "snapshot-miss":
        _snapshot_miss(pg, tmp_path, request, fault)
        return
    if row in PRIMARY_WRITER_ROWS:
        _primary_writer_row(pg, tmp_path, request, row, fault)
        return
    if row == "answer-2":
        _answer_2_row(pg, tmp_path, request, fault)
        return
    bench = Bench(pg, tmp_path, request)
    user = bench.login(spec["group"]) if spec["group"] else "lanes_test"
    if row == "migration":
        _migration(bench, fault)
        return
    listener, session = None, None
    try:
        if fault == "F1":
            listener = SilentListener()
            config = bench.config("127.0.0.1", listener.port, user)
        elif fault == "F2":
            listener = StartupRelay(f"{pg.host}/.s.PGSQL.{pg.port}")
            config = bench.config("127.0.0.1", listener.port, user)
        else:
            session = _hold(pg, spec["table"])
            config = bench.config(quote(str(pg.host), safe=""), pg.port, user)
        if row == "mode-query":
            config.write_text(config.read_text().replace("mode=primary", "mode=index"))
        proc, elapsed = bench.run(row, config)
    finally:
        if listener is not None:
            listener.close()
        if session is not None:
            _end(session)
    if spec["exit"] is not None:
        assert proc.returncode == spec["exit"], f"{case}: {proc.returncode}: {proc.stderr}"
    else:
        assert proc.returncode != 0, f"{case}: the path ended without its read"
    if row == "reader":
        # NOTHING PAST THE MODE LINE (T220j; lane 3, #165 6807694145: "the
        # contract stands"): `register read` prints its `mode` line first in
        # every form (4.18:758-760; B14 tasks:454), so a refused reader's
        # "nothing on stdout" (TP:3603) is its `mode primary` line alone.
        assert proc.stdout == "mode primary\n", \
            f"a reader's 69 prints its mode line and nothing more: {proc.stdout!r}"
    if row == "mode-query":
        assert proc.stdout == "index\n" and bench.calls() == [], "the query reads no database"
    if row == "status":
        # T220f: D9's row bounds the register's request, so `status` is timed
        # from that request's start to its exit, never from the command's
        # start (lane 3, #165 comments 6772120103 and 6770600106, ruling 6).
        elapsed = bench.request_elapsed()
    if spec["strict"]:
        assert elapsed < spec["bound"], f"{case}: {elapsed:.2f} s, not under {spec['bound']} s"
        _record(case, elapsed, spec["bound"], "timing rule 1")
    else:
        assert elapsed < 2 * spec["bound"], f"{case}: {elapsed:.2f} s against {spec['bound']} s"
        _record(case, elapsed, spec["bound"], "timing rule 2" + (
            ", from the register request's start" if row == "status" else ""))


def _answer_2_row(pg, tmp_path: Path, request, fault: str) -> None:
    """`[answer-2-F1]` (line BD-19b; lane 3's ruling, #165 6840828270): the
    row follows a healthy call (TP:3586-3589), since the guard's one prefetch
    is the first read of every prompt, an answer to its offer included
    (T507), and answer 2 adds no database call to the hook (Y:5417).

    1. The offer is made on a healthy register: the bench at `primary`
       (`Bench.to_primary`) with `REGISTER_OFFER`, its session named
       `OFFER_TO`, and one guard prompt, which must leave the offer record,
       `mode=name-drift`, as AT-F6's `make_offer` asserts it.
    2. `2` is sent through `ArmedFault`, which passes each connection whole
       until `TIMING_PSQL`'s log shows that the hook's register read has
       ended, and from then holds each new one (F1).
    3. The hook exits 2 with "BINDING" under 4.5 s (TP:3595); its read is in
       the log, ended 0; and it began no register call after it (AT-F6 case
       21, TP:6190-6191). The hook's calls are those in its own session: the
       wrapper names each call's, and `guard_answer` detaches the bind with
       `setsid` into one of its own.
    4. The detached bind meets F1 after the hook exits, bounded as AT-F6's
       fixture bounds its binds (`LANES_BIND_BOUND_S`, `ANSWER_2_BIND_S`).
       The relay stays up until the bind has written its outcome, at most
       `ANSWER_2_WAIT_S`. F1 held one connection or more, as this module's
       other F1 cases assert `silenced`, and the outcome is `bind-failed`,
       never `bound` (lane 2's RV20, NIT 12; T220m).

    It fails until T502 (T220's Order)."""
    spec = ROWS["answer-2"]
    case = f"answer-2-{fault}"
    bench = Bench(pg, tmp_path, request, register=REGISTER_OFFER, name=OFFER_TO)
    bench.to_primary()
    user = bench.login(spec["group"])
    bench.env = dict(bench.env, LANES_BIND_BOUND_S=str(ANSWER_2_BIND_S))
    mine = os.getsid(0)
    offer = tmp_path / ".claude" / "lanes" / "offers" / SID
    mark = []

    def read_ended() -> bool:
        return bool(mark) and any(c.get("sid") == mine for c in bench.calls()[mark[0]:])

    relay = ArmedFault(f"{pg.host}/.s.PGSQL.{pg.port}", fault, read_ended)
    outcome = {}
    try:
        config = bench.config("127.0.0.1", relay.port, user)
        made, _ = bench.run("guard", config)
        record = _offer_record(offer)
        assert made.returncode == 2 and record.get("mode") == "name-drift" \
            and record.get("to") == OFFER_TO, \
            f"{case}: the guard made no offer on a healthy register: {made.returncode}: " \
            f"{record}: {made.stderr}"
        begun = len(_begin_log(bench))
        mark.append(len(bench.calls()))
        proc, elapsed = bench.run("answer-2", config)
        if "BINDING" in proc.stdout + proc.stderr:
            outcome = _bind_outcome(offer, ANSWER_2_WAIT_S)
    finally:
        relay.close()
    assert proc.returncode == spec["exit"], f"{case}: {proc.returncode}: {proc.stderr}"
    assert "BINDING" in proc.stdout + proc.stderr, f"{case}: no BINDING: {proc.stderr}"
    assert elapsed < spec["bound"], f"{case}: {elapsed:.2f} s, not under {spec['bound']} s"
    reads = [c for c in bench.calls()[mark[0]:] if c.get("sid") == mine]
    assert len(reads) == 1 and reads[0]["exit"] == 0, \
        f"{case}: the hook's register read is not in the log, ended 0: {reads}"
    own = [b for b in _begin_log(bench)[begun:]
           if b.get("sid") == mine and b["argv"] != ["--version"]]
    later = [b for b in own if b["begin"] > reads[0]["end"]]
    assert len(own) == 1 and not later, \
        f"{case}: the hook made a register call besides its read (Y:5417): {own}"
    _record(case, elapsed, spec["bound"], "timing rule 1")
    print(f"D9 {case}: the detached bind's outcome {outcome.get('mode')} (rc "
          f"{outcome.get('rc')}); F1 held {relay.silenced} connection(s) after the hook's read")
    assert outcome, (f"{case}: the detached bind wrote no outcome in {ANSWER_2_WAIT_S} s, "
                     f"bounded at {ANSWER_2_BIND_S} s: {_offer_record(offer)}")
    assert relay.silenced >= 1 and outcome.get("mode") == "bind-failed", (
        f"{case}: the detached bind did not meet F1 and fail: F1 held {relay.silenced} connection(s), "
        f"and the outcome is {outcome}")


def _offer_record(path: Path) -> dict:
    """The guard's offer record, its `key=value` lines, the first of each key
    winning as the guard reads it (AT-F6's `read_record`); {} where there is
    none."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    record = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            record.setdefault(key, value)
    return record


def _bind_outcome(path: Path, limit: float) -> dict:
    """The offer record once the detached bind has written its outcome,
    `bound` or `bind-failed`; {} where it has not within `limit` s."""
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        record = _offer_record(path)
        if record.get("mode") in ("bound", "bind-failed"):
            return record
        time.sleep(0.2)
    return {}


def _begin_log(bench: Bench) -> list:
    """`TIMING_PSQL`'s begin stamps, every process's, in order."""
    log = bench.bin / "psql-begin.log"
    return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] \
        if log.exists() else []


def _slow_statement(pg, table: str, group: str, seconds: float) -> None:
    """F4: a sleep the test creates in its own database, never the
    template: a row-level security policy on `table` for `group` that sleeps
    past the path's `statement_timeout`."""
    pg.psql(f"SET search_path TO {SCHEMA};\n"
            f"CREATE FUNCTION t220_slow() RETURNS boolean LANGUAGE sql VOLATILE AS "
            f"$$ SELECT pg_sleep({seconds}) IS NOT NULL $$;\n"
            f"GRANT EXECUTE ON FUNCTION t220_slow() TO {group};\n"
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;\n"
            f"CREATE POLICY t220_slow ON {table} FOR ALL TO {group} USING (t220_slow());\n")


#: The guard's line where the service did not answer (socket contract d8,
#: section 5.3), and the warm-up's guard runs at most (T237y).
FALLBACK_LINE = "guard: direct (service unavailable)"
WARM_RUNS = 20


def _service_57014(bench: Bench, spec: dict, user: str) -> None:
    """`[service]`'s F4 (T237y; line W3aX's finding on T237x): the guard
    through a WARM service, whose held child's request meets 57014 at the
    request's 180 ms `statement_timeout` (lane 5's answer 3, #165 comment
    6771208498; d8:214). `lanes-index serve` is started once, with
    `STREAM_PSQL` first on `PATH`, so its "one long-lived `psql` child on
    pipes" (d8:229) runs through a wrapper that hands each request on as it
    comes; guard runs warm it, up to `WARM_RUNS`, until one is answered
    through the service, with no `FALLBACK_LINE` (a cold service answers
    `unavailable` until its `psql` has connected, d8:502); only then is F4's
    slow statement made and the guard run once more. The held child, known
    by its own argv's `VERBOSITY=sqlstate` (d8:229), prints `ERROR:  57014`
    no earlier than 180 ms after its request was handed to it (timing rule 3)
    and under twice it (timing rule 2), and the guard exits 2. It fails until
    L5-S1 (lane 5's T511 to T513) and L5-A3 land."""
    config = bench.config(quote(str(bench.pg.host), safe=""), bench.pg.port, user)
    statement_s = spec["statement_ms"] / 1000
    bench.stream()
    serve = bench.start_service(bench.service_env(bench.guard_env(config)))
    try:
        proc, warm = None, False
        for _ in range(WARM_RUNS):
            proc, _ = bench.run("service", config, service=serve)
            if FALLBACK_LINE not in proc.stdout + proc.stderr:
                warm = True
                break
            time.sleep(0.25)
        assert warm, (f"service: no guard run of {WARM_RUNS} was answered through the "
                      f"service: {proc.returncode}: {proc.stderr}")
        _slow_statement(bench.pg, spec["table"], spec["group"], 4 * statement_s + 5)
        proc, _ = bench.run("service", config, service=serve)
    finally:
        bench.stop_service(serve)
    held = [s for s in bench.streamed() if "VERBOSITY=sqlstate" in s["argv"]]
    assert held, f"service: the held child met no 57014: {bench.streamed()}"
    took = held[0]["error"] - held[0]["request"]
    assert statement_s <= took < 2 * statement_s, \
        f"service: the held child's 57014 {took:.3f} s after its request"
    assert proc.returncode == spec["exit"], f"service: {proc.returncode}: {proc.stderr}"
    _record("service-F4", took, statement_s, "timing rules 2 and 3, the held child's request")


@pytest.mark.parametrize("row", SLOW_ROWS)
def test_a_slow_statement_meets_57014_before_the_client_timer(pg, tmp_path, request, row):
    """F4, on every phase-N row that sets a `statement_timeout`: the call
    ends with 57014, the server's bound and not the client timer, no earlier
    than the path's `statement_timeout` after the call's start (timing rule
    3) and under twice it (timing rule 2), and the path exits with its row's
    outcome (AT-D9, "Oracle"). `[service]` times the warm service's held
    child, through `STREAM_PSQL` (T237y, `_service_57014`). A writer's
    commit, `[writer-commit-f2]`, meets a trigger on `journal` and exits 69,
    a refusal the database made (T257h), on `Operator`'s estate at `primary`
    (T257j, `_primary_writer_57014`)."""
    spec = ROWS[row]
    if row in OPERATOR_ROWS:
        _operator_57014(pg, tmp_path, request, row)
        return
    if row in PRIMARY_WRITER_ROWS:
        _primary_writer_57014(pg, tmp_path, request, row)
        return
    bench = Bench(pg, tmp_path, request)
    user = bench.login(spec["group"])
    if row == "service":
        _service_57014(bench, spec, user)
        return
    statement_s = spec["statement_ms"] / 1000
    if row == "lookup":
        # `find_write` is SECURITY DEFINER (`lanes-index:7863` at
        # `refs/l1/V-round5`), so a policy for the writer's group never binds
        # it: it locked the head row unslowed and refused LR007 on the row's
        # random `--generation` at once (AN13b's cause 3). The lookup's F4 is
        # `_slow_lookup`'s policy, forced on `journal` and `register_head`, as
        # the lookup's own `[F4]` case meets it (AT-D9's F4: "a policy forced
        # on `journal` for its owner, since `find_write` runs as the owner").
        _slow_lookup(pg, 4 * statement_s + 5)
    else:
        _slow_statement(pg, spec["table"], spec["group"], 4 * statement_s + 5)
    proc, elapsed = bench.run(row, bench.config(quote(str(pg.host), safe=""), pg.port, user))
    ended = [c for c in bench.calls() if "57014" in c["first"]]
    assert ended, f"{row}: no call ended with 57014: {bench.calls()}"
    took = ended[0]["end"] - ended[0]["start"]
    assert statement_s <= took < 2 * statement_s, f"{row}: 57014 after {took:.2f} s"
    if spec["exit"] is not None:
        assert proc.returncode == spec["exit"], f"{row}: {proc.returncode}: {proc.stderr}"
    _record(f"{row}-F4", took, statement_s, "timing rules 2 and 3")


@pytest.mark.parametrize("case", ["F1-word", "F2-word", "F3-word", "F1-rollback", "F2-rollback",
                                  "F3-rollback"])
def test_the_outage_declare_probe_ends_inside_its_bound_and_the_declaration_follows_the_rule(
        pg, tmp_path, request, case):
    """`outage declare`'s database probe (section 2.5's row): 2 s, 2000 ms,
    5000 ms, 8 s. On a person's word, the declaration is written, since the
    database does not answer from this host; in the `--rollback` form, 2 and
    no file, the switch being unread. The probe ends inside twice its 8 s
    (AT-D9's table)."""
    fault, form = case.split("-", 1)
    bench = Bench(pg, tmp_path, request)
    user = bench.login("lanes_register_writer")
    listener, session = None, None
    try:
        if fault == "F1":
            listener = SilentListener()
            config = bench.config("127.0.0.1", listener.port, user)
        elif fault == "F2":
            listener = StartupRelay(f"{pg.host}/.s.PGSQL.{pg.port}")
            config = bench.config("127.0.0.1", listener.port, user)
        else:
            session = _hold(pg, "register_switch")
            config = bench.config(quote(str(pg.host), safe=""), pg.port, user)
        # D20 (Y:3073): `outage declare --until <UTC> --why "<words>"`; the rollback
        # form is `--rollback --mirror-seq <k>`, with no `--until` (lane 1, #165
        # comment 6754680212).
        # On Brett's word the declare is given `--mirror-seq 0`, T218g's value
        # (T220g, as `Bench.run`'s `outage-probe` row): the bench's origin
        # holds no mirror `Register-Seq` to read after a fetch (F11). No
        # closed port: the case's fault keeps the probe from an answer.
        argv = [sys.executable, str(bench.copy), "outage", "declare"]
        if form == "rollback":
            argv += ["--rollback", "--mirror-seq", "1"]
        else:
            argv += ["--until", "2999-01-01T00:00:00Z", "--why", "D9's probe",
                     "--mirror-seq", "0"]
        env = dict(bench.env, LANES_INDEX_CONFIG=str(config), LANES_LANE="repoA-2")
        start = time.monotonic()
        proc = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=str(bench.wip),
                              timeout=120, stdin=subprocess.DEVNULL)
        elapsed = time.monotonic() - start
    finally:
        if listener is not None:
            listener.close()
        if session is not None:
            _end(session)
    declaration = config.parent / "register-outage"
    if form == "word":
        assert proc.returncode == 0, proc.stderr
        assert declaration.exists(), "the declaration is written"
    else:
        assert proc.returncode == 2, proc.stderr
        assert not declaration.exists(), "no file in the --rollback form"
    assert elapsed < 2 * 8, f"{case}: {elapsed:.2f} s"
    _record(f"outage-probe-{case}", elapsed, 8, "timing rule 2")


#: T109's argv (lane 1, #165 comment 6754680212): the admin is a libpq service,
#: `--admin-service <service>`, with `--label`, `--repository` and `--lane`, which
#: its USAGE lists on one synopsis (`--lane` is required unless `--roles-only`).
#: It refuses off a terminal unless `--no-passwords` is given, so each call here
#: runs under `_in_pty` and passes no `--no-passwords`.
BOOTSTRAP_FLAGS = ["--admin-service", "t220-admin", "--label", "register-test",
                   "--repository", "opensoft/t220-register", "--lane", "repoA-2"]


def _migration(bench: Bench, fault: str) -> None:
    """The migration's path, through `lanes-index bootstrap` under a pty
    (T109: it refuses when stdout is not a terminal), its admin reached only
    as the libpq service `--admin-service` names (T109). Under F1 its connect
    meets the silent listener and it is refused, writing nothing."""
    listener = SilentListener()
    try:
        service = bench.root / "pg_service.conf"
        service.write_text(f"[t220-admin]\nhost=127.0.0.1\nport={listener.port}\n"
                           f"dbname={bench.pg.name}\nuser=lanes_test\n", encoding="utf-8")
        env = dict(bench.env, PGSERVICEFILE=str(service))
        code, elapsed, timed_out = _in_pty([sys.executable, str(bench.copy), "bootstrap",
                                            *BOOTSTRAP_FLAGS], env, bench.wip)
    finally:
        listener.close()
    assert not timed_out and code != 0, "a migration that cannot connect is refused"
    assert elapsed < 2 * (N_A * C + 1), f"{elapsed:.2f} s, against its connect, c"
    _record(f"migration-{fault}", elapsed, N_A * C + 1, "timing rule 2")


def _in_pty(argv: list, env: dict, cwd: Path, *, timeout: float = 120) -> tuple:
    """Run `argv` with its stdout on a pty; return (its exit, its elapsed
    seconds, whether this helper's own timeout killed it)."""
    master, slave = pty.openpty()
    start = time.monotonic()
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=slave, stderr=slave, env=env,
                            cwd=str(cwd))
    os.close(slave)
    timed_out = False
    while True:
        ready, _, _ = select.select([master], [], [], 0.2)
        if ready:
            try:
                os.read(master, 65536)
            except OSError:
                ready = []
        if proc.poll() is not None and not ready:
            break
        if time.monotonic() - start > timeout:
            proc.kill()
            timed_out = True
            break
    os.close(master)
    return proc.wait(), time.monotonic() - start, timed_out


def _own_migration(number: int) -> str:
    """THE CASE'S OWN MIGRATION `number` (line AF13b; AN13b's cause 4), in
    section 1.5's step 3 form (Y:2342), sent by the admin through `psql` as
    T221's migration test sends its own (`migration_script` in
    `test_sql_register_schema.py`; B15 tasks:2121): one transaction that
    sets its own `lock_timeout`, 2000 ms, touches the head row, checks that
    `version` is one below its own (else LR003), makes its DDL, raises
    `version` and the floors, and records its `migrations` row. Its DDL alters
    `register_head`, the table the reader's open transaction read, since an
    ACCESS EXCLUSIVE lock on such a table is what a migration waits for
    behind a reader; T221's new table waits for no reader. `VERBOSITY
    verbose` puts the SQLSTATE in the kept output."""
    return ("\\set VERBOSITY verbose\n"
            "BEGIN;\nSET LOCAL ROLE lanes_register_owner;\n"
            f"SET LOCAL search_path TO {SCHEMA}, pg_catalog;\n"
            "SET LOCAL lock_timeout = '2000ms';\n"
            "UPDATE register_head SET seq = seq WHERE id = 1;\n"
            f"DO $m$ BEGIN IF (SELECT version FROM schema_version WHERE id = 1) <> {number - 1} "
            f"THEN RAISE EXCEPTION 'migration {number} needs schema version {number - 1}, not %', "
            "(SELECT version FROM schema_version WHERE id = 1) USING ERRCODE = 'LR003'; "
            "END IF; END $m$;\n"
            f"ALTER TABLE register_head ADD COLUMN t220_migration_{number} integer;\n"
            f"UPDATE schema_version SET version = {number}, writers_from = {number}, "
            f"readers_from = {number}, applied_utc = date_trunc('second', clock_timestamp()) "
            "WHERE id = 1;\n"
            "INSERT INTO migrations (version, script_sha256, by_lane, by_ws) "
            f"VALUES ({number}, '{'f' * 64}', 'repoA-2', 't220');\n"
            "COMMIT;\n")


def test_a_waiting_migration_gives_up_at_its_own_lock_timeout(pg, tmp_path, request):
    """A migration waiting behind a reader's open transaction is refused at
    its own `lock_timeout`, and a rerun succeeds once the reader's
    transaction ends; a new plain read is not held longer than that
    `lock_timeout` (AT-D9's migration row).

    The migration is the case's own next one (`_own_migration`), migration 2
    while this build ships migration 1 alone (`REGISTER_SCHEMA_VERSION = 1`,
    `lanes-index:6867` at `refs/l1/V-round5`): the case's database is
    already at that version, so T109's `bootstrap` has nothing to migrate and
    no `lock_timeout` to meet (round 5: "gave up after 0.22 s"). It is sent
    once the reader's transaction holds `register_head`, and each
    assertion shows the `psql` call's exit and stderr. `[migration-F1]`
    still runs `bootstrap`, for the migration's connect."""
    bench = Bench(pg, tmp_path, request)
    reader = bench.login("lanes_register_reader")
    number = int(pg.psql(f"SELECT version FROM {SCHEMA}.schema_version WHERE id = 1;").stdout) + 1
    held = pg.session(user=reader, appname="t220-reader")
    held.stdin.write(f"BEGIN;\nSELECT seq FROM {SCHEMA}.register_head;\n")
    held.stdin.flush()
    try:
        deadline = time.monotonic() + 30
        while pg.psql("SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a USING (pid) "
                      "WHERE a.application_name = 't220-reader' AND l.granted "
                      f"AND l.relation = '{SCHEMA}.register_head'::regclass "
                      "AND l.mode = 'AccessShareLock';").stdout.strip() in ("", "0"):
            assert time.monotonic() < deadline, "the reader's transaction never read register_head"
            time.sleep(0.1)
        start = time.monotonic()
        proc = pg.psql(_own_migration(number), check=False)
        elapsed = time.monotonic() - start
        said = f": migration {number} exited {proc.returncode}: {proc.stderr.strip()}"
        assert proc.returncode != 0, "the waiting migration is refused" + said
        assert "55P03" in proc.stderr, "the migration gave up at its lock_timeout, 55P03" + said
        # Y:2342 (design 1.5 step 3): each migration is one transaction that
        # begins `SET LOCAL lock_timeout = '2000ms'`: it gives up no sooner
        # than that, and well before 10 s.
        assert 1.9 <= elapsed < 10, (f"the migration gave up after {elapsed:.2f} s, "
                                     f"against its 2000 ms lock_timeout" + said)
        _record("migration-lock", elapsed, 2, "its own lock_timeout, 2000 ms (Y:2342)")
        start = time.monotonic()
        pg.psql(f"SELECT seq FROM {SCHEMA}.register_head;", user=reader)
        assert time.monotonic() - start < 60, "a plain read was held"
    finally:
        _end(held)
    proc = pg.psql(_own_migration(number), check=False)
    assert proc.returncode == 0, ("the rerun succeeds once the reader's transaction ends: "
                                  f"migration {number} exited {proc.returncode}: "
                                  f"{proc.stderr.strip()}")
    version = pg.psql(f"SELECT version FROM {SCHEMA}.schema_version WHERE id = 1;").stdout
    assert int(version) == number, f"the rerun left version {version.strip()}, not {number}"


def test_import_and_reconcile_set_their_bounds_at_connect(tmp_path):
    """FP: `import` carries `PGCONNECT_TIMEOUT=2`, `c` here, and sets
    `lock_timeout=2000` and `statement_timeout=300s` at connect, under a
    330 s client timer; `reconcile` carries its row's bounds, 1000 ms and
    10 s, at connect (AT-D9's table; T106's `PGOPTIONS`, Y:1573). No engine:
    T203's register fake, which answers `psql --version` itself (T203b),
    records each call.

    `reconcile`'s row is the register's, on primary (T117: on primary the
    register's `reconcile` is the mirror's read-only check against SQL; on
    `mode=index` it is #160's, on the local index, and calls no `psql`). So
    it runs as `Bench`'s `[reconcile]` rows run it: from T203's flipped copy,
    with `lanes-edit.sh` beside it, on a `mode=primary` configuration that
    names the same URLs (T220i)."""
    from sql_register_helpers import REGISTER_FAKE_PSQL, flipped_copy
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "psql").write_text(REGISTER_FAKE_PSQL, encoding="utf-8")
    (bindir / "psql").chmod(0o755)
    passfile = _private(tmp_path / "conf" / "pgpass")
    url = "postgresql://t220_fp@127.0.0.1:55432/register_db"
    lines = [f"register_url={url}", f"register_passfile={passfile}", f"reader_url={url}",
             f"reader_passfile={passfile}", "register_label=register-test", ""]
    config = _private(tmp_path / "conf" / "lanes-index.conf", "\n".join(["mode=index", *lines]))
    primary = _private(tmp_path / "conf-primary" / "lanes-index.conf",
                       "\n".join(["mode=primary", *lines]))
    copy = flipped_copy(INDEXER, tmp_path / "tool", True)
    for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
        if (REPO / name).exists():
            shutil.copy2(REPO / name, tmp_path / "tool" / name)
    origin, wip = tmp_path / "origin.git", tmp_path / "wip"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("LANES_", "CLAUDE_", "TMUX", "PG", "FAKE_PSQL"))}
    env.update(HOME=str(tmp_path), XDG_STATE_HOME=str(tmp_path / "state"),
               XDG_CONFIG_HOME=str(tmp_path / "config"), LANES_INDEX_CONFIG=str(config),
               LANES_LANE="repoA-2", LANES_REPO=str(wip), FAKE_PSQL_LOG=str(tmp_path / "fake.log"),
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
               PATH=str(bindir) + os.pathsep + os.environ.get("PATH", os.defpath))
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True, env=env)
    subprocess.run(["git", "clone", "-q", str(origin), str(wip)], check=True, env=env,
                   capture_output=True)
    (wip / "lanes").mkdir()
    (wip / "lanes" / "LANES.md").write_text("# LANES.md\n", encoding="utf-8")
    for argv in (["add", "-A"], ["commit", "-q", "-m", "C"], ["push", "-q", "origin", "main"]):
        subprocess.run(["git", *argv], cwd=str(wip), check=True, env=env, capture_output=True)
    c = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(wip), env=env, capture_output=True,
                       text=True, check=True).stdout.strip()
    # W, A CLONE OF ITS OWN (T220h; lane 1's group 6, #165 6807494089): with
    # `LANES_REPO` set, `import` reads W to check that the checkout is not W,
    # and refuses where W cannot be read or is the checkout (contract
    # 4.18:987), before any `psql` call; `reconcile` reads W's `origin/main`.
    # `LANES_WORKSPACE_ROOT` is `lanes-edit.sh`'s test seam. The workstation
    # is named too, as `Bench` names it: in a container with none, `import`
    # refuses 2 before any call (Amendment 11, R-A11-14).
    w = tmp_path / "W"
    subprocess.run(["git", "clone", "-q", str(origin), str(w)], check=True, env=env,
                   capture_output=True)
    env.update(LANES_WORKSPACE_ROOT=str(w), LANES_WORKSTATION="Eagle")
    log = tmp_path / "fake.log"
    for argv, tool, conf, options in (
            (["import", "--at", c], INDEXER, config,
             ("-c lock_timeout=2000", "-c statement_timeout=300000")),
            (["reconcile"], copy, primary,
             ("-c lock_timeout=1000", "-c statement_timeout=10000"))):
        if log.exists():
            log.unlink()
        proc = subprocess.run([sys.executable, str(tool), *argv], capture_output=True,
                              text=True, env=dict(env, LANES_INDEX_CONFIG=str(conf)),
                              cwd=str(wip), timeout=120, stdin=subprocess.DEVNULL)
        calls = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
        calls = [c for c in calls if c.get("kind") != "version"]
        assert calls, f"{argv[0]} made no psql call: {proc.returncode}: {proc.stderr[-400:]}"
        for call in calls:
            assert call["connect_timeout"] == str(C), (argv[0], call["connect_timeout"])
            assert all(o in (call["options"] or "") for o in options), (argv[0], call["options"])


# ============================================ AT-D9c and R-PG-1 (T257b), no engine

#: R-PG-1's three families (lane 3, #165 comment 6747611042, 18:04Z: "one case
#: per family, each set by the caller and each absent at `psql`").
INHERITED_FAMILIES = {
    "pghostaddr-sslmode-disable": {"PGHOSTADDR": "192.0.2.9", "PGSSLMODE": "disable"},
    "pgoptions": {"PGOPTIONS": "-c search_path=inherited"},
    "pgtargetsessionattrs": {"PGTARGETSESSIONATTRS": "read-write"},
}


def _register_fake(tmp_path: Path, monkeypatch, url_tail: str = "",
                   extra: tuple = ()) -> Path:
    """T203's register fake `psql` first on `PATH`, answering `psql --version`
    itself (T203b), and a configuration whose two URLs name a loopback host,
    each with `url_tail` after the database, and a private password file
    each, with the `extra` lines after them (T257c's `register_addresses=`);
    every inherited `PG*` and fake variable cleared. Returns the fake's
    log."""
    from sql_register_helpers import REGISTER_FAKE_PSQL
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "psql").write_text(REGISTER_FAKE_PSQL, encoding="utf-8")
    (bindir / "psql").chmod(0o755)
    config = _private(tmp_path / "conf" / "lanes-index.conf", "\n".join([
        "mode=index",
        f"register_url=postgresql://t257_writer@127.0.0.1:55432/register_db{url_tail}",
        f"register_passfile={_private(tmp_path / 'writer.pgpass')}",
        f"reader_url=postgresql://t257_reader@127.0.0.1:55432/register_db{url_tail}",
        f"reader_passfile={_private(tmp_path / 'reader.pgpass')}",
        "register_schema=lanes_register_t257",
        *extra,
        ""]))
    log = tmp_path / "psql.log"
    for key in list(os.environ):
        if key.startswith("PG") or key.startswith("FAKE_PSQL"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("LANES_INDEX_CONFIG", str(config))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("FAKE_PSQL_LOG", str(log))
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", os.defpath))
    return log


@pytest.mark.parametrize("family", list(INHERITED_FAMILIES))
def test_a_register_path_drops_each_inherited_pg_variable_before_psql(tmp_path, monkeypatch,
                                                                       family):
    """R-PG-1 (lane 3, #165 comment 6747611042): on a register path `psql`
    gets only what the configuration gives it, the URL's mapping (SVC-2),
    the configured `PGPASSFILE` and `PGCONNECT_TIMEOUT` at `c` (Y:4970);
    every inherited variable whose name begins `PG` is dropped first. Each
    case sets its family in the caller's environment, sends one register
    request, the reader's `read` row through `PostgresStore(cfg,
    "register_reader")` in process (lane 1, #165 6752661856: "a phase N case
    at T106 can drive only the store, in process"), through T203's register
    fake `psql`, whose URL names a loopback host and no query parameter
    (lane 2's reading, NOTES question 26), and asserts each variable absent
    at every `psql` call, `--version` included. T106 sets `PGOPTIONS` itself,
    to D9's bounds, so `[pgoptions]` asserts the inherited value absent. It
    fails until lane 1's T106 lands (L1-A5). Its `[J3]` word is
    `sql_register_bounds and inherited_pg_variable`, and each case's adds
    `and <id>`."""
    log = _register_fake(tmp_path, monkeypatch)
    inherited = INHERITED_FAMILIES[family]
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)
    mod = load_indexer()
    error = None
    try:
        store = mod.PostgresStore(mod.load_config(), "register_reader")
        store.request(["SELECT 1"], "read")
    except Exception as exc:  # the code under test, not this test, failed
        error = exc
    assert error is None, f"PostgresStore(cfg, 'register_reader').request(...) raised {error!r}"
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    requests = [r for r in records if r.get("kind") != "version"]
    assert len(requests) == 1, f"one psql call carries the request: {len(requests)}"
    assert requests[0]["pg"].get("PGHOST") == "127.0.0.1", \
        f"the URL's mapping reached psql: {requests[0]['pg']}"
    for record in records:
        pg = record["pg"]
        for key, value in inherited.items():
            if key == "PGOPTIONS":
                assert pg.get(key) != value, f"the inherited PGOPTIONS reached {record['argv']}"
            else:
                assert key not in pg, f"the inherited {key} reached {record['argv']}: {pg[key]!r}"


def test_a_connect_timeout_under_2_is_refused_at_load_config(tmp_path, monkeypatch):
    """AT-D9c (b)'s refusal (SVC-2; the phase plan's "`c` and `N_a`, the
    connect bound"): `connect_timeout=1` and `connect_timeout=0`, in
    `register_url=` or in `reader_url=`, are refused at `load_config`, as
    `Refusal` (2), naming the key and its value, before any `psql` call:
    libpq reads 1 as 2 and 0 as no limit. `connect_timeout=2`, `c`'s floor,
    loads. No engine. It fails until lane 1's line C (T103's `pg_url_env`,
    which `load_config` runs on each URL by T106)."""
    log = _register_fake(tmp_path, monkeypatch)
    config = Path(os.environ["LANES_INDEX_CONFIG"])
    text = config.read_text(encoding="utf-8")
    mod = load_indexer()
    for value in ("1", "0"):
        for key in ("register_url", "reader_url"):
            config.write_text("".join(
                line + (f"?connect_timeout={value}" if line.startswith(f"{key}=") else "") + "\n"
                for line in text.splitlines()), encoding="utf-8")
            error = None
            try:
                mod.load_config()
            except Exception as exc:  # the refusal under test, or another failure
                error = exc
            assert isinstance(error, mod.Refusal), \
                f"{key}=...?connect_timeout={value} loaded: {error!r}"
            assert f"connect_timeout={value}" in str(error) and key in str(error), str(error)
    config.write_text("".join(
        line + ("?connect_timeout=2" if line.startswith(("register_url=", "reader_url=")) else "")
        + "\n" for line in text.splitlines()), encoding="utf-8")
    assert mod.load_config()["register_url"].endswith("?connect_timeout=2")
    assert not log.exists(), "load_config called psql"


# ===================== AT-D9c (a) and (b), no engine, and AT-D9's lookup tries (T257c)

#: A write's identity, as lane 1's commands take it (contract sections 3.2 to 3.4).
WRITE = {"write_id": "7d3c2b1a-0f9e-4d8c-8b7a-6e5d4c3b2a19",
         "generation": "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9",
         "lane": "repoA-2", "verb": "set-row-state", "args_sha256": "ab" * 32}
#: `_register_fake`'s `register_schema=`.
T257_SCHEMA = "lanes_register_t257"
#: A FOUND ANSWER AS THE FAKE PRINTS IT for lane 1's T114 follow-up 3
#: (`refs/l1/T114-fu3`, `fdd5fd04`; lane 1, #165 6775027958): statement 2's seq
#: bare under `-A -t`, then statement 3's ONE escaped text column, one value a
#: line, `workstation=`, `utc=`, then each `journal_files` row, its two tabs
#: printed as COPY's text format escapes them, `\t`.
FOUND_SHA = "c0ffee" + "0" * 58
FOUND_OUT = ("7\nworkstation=ws-t257\nutc=1762790400\n"
             f"lanes/LANES.md\\t1\\t{FOUND_SHA}\nlanes/log/repoA-2.md\\t0\\t-\n")
#: What `journal --write-id` prints for it (contract section 3.4; draft 4.15's
#: E3, F13b-OWED items 11 and 15): `found <seq>`, `workstation=`, `utc=`, then
#: the `file=` rows.
FOUND_PRINTED = ("found 7\nworkstation=ws-t257\nutc=1762790400\n"
                 f"file=lanes/LANES.md\t1\t{FOUND_SHA}\nfile=lanes/log/repoA-2.md\t0\t-\n")


def _one_request(call: dict) -> list:
    """One call's stdin read as ONE request (contract section 2.3, "one
    request per call"): one line, ending with the request's one `;`, its
    statements joined by `psql`'s `\\;`. A statement left to its own `;` fails
    the case (AT-D9c (a)). Returns the statements."""
    request = call["stdin"].strip()
    assert "\n" not in request and request.endswith(";"), f"not one request: {call['stdin']!r}"
    body = request[:-1]
    loose = [m.start() for m in re.finditer(r"(?<!\\);", body)]
    assert not loose, f"a statement is left to its own semicolon: {request!r}"
    return [part.strip() for part in body.split("\\;")]


def _cli(argv: list, tmp_path: Path, answers: list | None = None) -> subprocess.CompletedProcess:
    """`lanes-index <argv>` in a child, with `_register_fake`'s environment and
    configuration and the fake taught `answers`; no lane's, harness's or
    tmux's variable."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LANES_", "CLAUDE_", "TMUX"))}
    env.update(LANES_INDEX_CONFIG=os.environ["LANES_INDEX_CONFIG"], HOME=str(tmp_path))
    if answers is not None:
        path = tmp_path / "answers.json"
        path.write_text(json.dumps(answers), encoding="utf-8")
        env["FAKE_PSQL_ANSWERS"] = str(path)
    return subprocess.run([sys.executable, str(INDEXER), *argv], capture_output=True, text=True,
                          env=env, cwd=str(tmp_path), timeout=120, stdin=subprocess.DEVNULL)


def _fake_log(log: Path) -> tuple:
    """The fake's log: (the calls that carry a request, the `--version` calls)."""
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] \
        if log.exists() else []
    return ([r for r in records if r.get("kind") != "version"],
            [r for r in records if r.get("kind") == "version"])


#: `register snapshot`'s form for a new write (contract section 3.2; lane 5's
#: T111 for lane 1, `refs/l5/T111p2`, `6df75975`).
SNAPSHOT_ARGV = ["register", "snapshot", "--write-id", "new", "--lane", WRITE["lane"],
                 "--verb", WRITE["verb"], "--args-sha256", WRITE["args_sha256"]]


@pytest.mark.parametrize("call", ["snapshot", "commit", "lookup", "snapshot-psql-14"])
def test_each_register_call_is_one_request(tmp_path, monkeypatch, call):
    """AT-D9c (a), FP (FR-012; contract section 2.3; the phase plan's "One
    request per call"): in T203's register fake's log, each register call is
    ONE `psql` call whose stdin is one request, its statements joined by
    `\\;`, with section 2.2's argv; a statement left to its own semicolon
    fails the case.

    - `[snapshot]`: `register snapshot --write-id new ...` (lane 5's T111 for
      lane 1, `refs/l5/T111p2`) sends one call: `SET search_path`, a
      `BEGIN ISOLATION LEVEL REPEATABLE READ`, then #160's statements, each
      a `COPY (...) TO STDOUT`, the marker among them as `COPY (SELECT
      E'\\x1eLANES-INDEX-NEXT') TO STDOUT`, then `COMMIT`. It fails until
      T111 lands.
    - `[commit]`: `BEGIN ISOLATION LEVEL SERIALIZABLE \\; SELECT
      <schema>.commit_write(...) \\; COMMIT;`. `register commit` reads an
      attempt directory (contract section 3.3) that only the writer's whole
      path makes, so this case drives lane 1's own form in process,
      `register_commit_request` through `PostgresStore(cfg,
      "register_writer").request(..., "commit")` (lane 2's reading, as
      T257b's R-PG-1 cases drive the store). It fails until T112 lands
      (`refs/l1/T112-fu2`, in `refs/l1/R-merge6`).
    - `[lookup]`: `journal --write-id ...` sends draft 4.16's four statements,
      byte for byte (lane 1's T114 follow-up 3, `refs/l1/T114-fu3`; its
      `contract-lines-fu3.md`, C1, for `:236`; ERR-50): `BEGIN ISOLATION
      LEVEL READ COMMITTED`; `b16f078`'s `SELECT coalesce(<schema>.find_write(
      ...)::text, 'absent')`; the one-column `COPY` of `workstation=`, `utc=`
      and the `file=` rows; `ROLLBACK`. Taught a found answer in the fakes'
      form, the rows as one escaped column, it prints `found <seq>`,
      `workstation=`, `utc=`, then the `file=` rows, with 0, after one try
      (F13b-OWED items 11 and 15). It fails until T114's follow-up 3 lands.
    - `[snapshot-psql-14]` (R-F9b-psql14; lane 1, #165 6752661856 point 1):
      the fake's `psql --version` answers 14.11; `register snapshot` exits 69
      naming the version, after one `--version` call and no request
      (L1v4.10:152). It fails until T111 lands."""
    log = _register_fake(tmp_path, monkeypatch)
    if call == "commit":
        answers = tmp_path / "answers.json"
        answers.write_text(json.dumps([{"stdout": ""}]), encoding="utf-8")
        monkeypatch.setenv("FAKE_PSQL_ANSWERS", str(answers))
        mod = load_indexer()
        error = None
        try:
            store = mod.PostgresStore(mod.load_config(), "register_writer")
            store.request(mod.register_commit_request(store.schema, 41, WRITE, {"t257": "commit"}),
                          "commit")
        except Exception as exc:  # the code under test, not this test, failed
            error = exc
        assert error is None, f"lane 1's commit request could not be sent: {error!r}"
        calls, _ = _fake_log(log)
        assert len(calls) == 1, f"one psql call carries the commit: {len(calls)}"
        assert calls[0]["argv"] == REGISTER_ARGV
        parts = _one_request(calls[0])
        assert len(parts) == 3, f"the commit is three statements: {parts}"
        assert parts[0] == "BEGIN ISOLATION LEVEL SERIALIZABLE", parts[0]
        assert parts[1].startswith(f"SELECT {T257_SCHEMA}.commit_write(41, '{WRITE['write_id']}', ") \
            and parts[1].endswith("::jsonb)"), parts[1]
        assert parts[2] == "COMMIT", parts[2]
        return
    if call == "lookup":
        not_after = int(time.time()) - 60
        utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(not_after))
        proc = _cli(["journal", "--write-id", WRITE["write_id"], "--not-after", str(not_after),
                     "--generation", WRITE["generation"], "--lane", WRITE["lane"], "--verb",
                     WRITE["verb"], "--args-sha256", WRITE["args_sha256"]], tmp_path,
                    [{"match": "find_write", "stdout": FOUND_OUT}])
        calls, _ = _fake_log(log)
        assert len(calls) == 1, \
            f"one try, one psql call: {len(calls)}; exit {proc.returncode}: {proc.stderr}"
        assert calls[0]["argv"] == REGISTER_ARGV
        write = f"'{WRITE['write_id']}'"
        assert _one_request(calls[0]) == [
            "BEGIN ISOLATION LEVEL READ COMMITTED",
            f"SELECT coalesce({T257_SCHEMA}.find_write({write}, '{utc}', '{WRITE['generation']}', "
            f"'{WRITE['lane']}', '{WRITE['verb']}', '{WRITE['args_sha256']}')::text, 'absent')",
            f"COPY (WITH j AS (SELECT seq, workstation, utc FROM {T257_SCHEMA}.journal "
            f"WHERE write_id = {write}) SELECT x.line FROM (SELECT 1 AS o, '' AS p, "
            "'workstation=' || j.workstation AS line FROM j UNION ALL SELECT 2, '', 'utc=' || "
            "extract(epoch FROM j.utc)::bigint::text FROM j UNION ALL SELECT 3, f.path, "
            "f.path || chr(9) || CASE WHEN f.present THEN '1' ELSE '0' END || chr(9) || "
            f"coalesce(f.sha256, '-') FROM {T257_SCHEMA}.journal_files f JOIN j ON f.seq = j.seq) x "
            "ORDER BY x.o, x.p COLLATE \"C\") TO STDOUT",
            "ROLLBACK"]
        assert (proc.returncode, proc.stdout) == (0, FOUND_PRINTED), \
            f"exit {proc.returncode}: {proc.stdout!r}: {proc.stderr}"
        return
    if call == "snapshot-psql-14":
        proc = _cli(SNAPSHOT_ARGV, tmp_path,
                    [{"kind": "version", "stdout": "psql (PostgreSQL) 14.11\n"}])
        calls, probes = _fake_log(log)
        assert proc.returncode == 69, f"exit {proc.returncode}: {proc.stderr}"
        assert "14.11" in proc.stderr, f"the 69 names the version: {proc.stderr}"
        assert len(probes) == 1 and calls == [], \
            f"one --version call and no request: {len(probes)}, {len(calls)}"
        return
    proc = _cli(SNAPSHOT_ARGV, tmp_path)
    calls, _ = _fake_log(log)
    assert len(calls) == 1, \
        f"one psql call carries the snapshot: {len(calls)}; exit {proc.returncode}: {proc.stderr}"
    assert calls[0]["argv"] == REGISTER_ARGV
    parts = _one_request(calls[0])
    assert parts[0].startswith("SET search_path TO ") and T257_SCHEMA in parts[0], parts[0]
    assert parts[1].startswith("BEGIN ISOLATION LEVEL REPEATABLE READ"), parts[1]
    assert parts[-1] == "COMMIT", parts[-1]
    reads = parts[2:-1]
    assert reads and all(p.startswith("COPY (") and p.endswith(") TO STDOUT") for p in reads), \
        f"between the BEGIN and the COMMIT, only COPYs: {reads}"
    assert r"COPY (SELECT E'\x1eLANES-INDEX-NEXT') TO STDOUT" in reads, \
        f"the marker goes as a COPY: {reads}"


#: AT-D9c (b)'s three settings: the URLs' tail, the configuration's other
#: lines, `c`, and each row's client timer in s, `S`, `C` and `T_L`: `N_a`.`c`
#: + 6 s, + 6 s and + 7 s, never below the row's 8, 8 and 9 s.
TIMER_CASES = {
    "default": ("", (), 2, {"snapshot": 8, "commit": 8, "lookup": 9}),
    "c3": ("?connect_timeout=3", (), 3, {"snapshot": 9, "commit": 9, "lookup": 10}),
    "c3-two-addresses": ("?connect_timeout=3", ("register_addresses=2",), 3,
                         {"snapshot": 12, "commit": 12, "lookup": 13}),
}


@pytest.mark.parametrize("case", list(TIMER_CASES))
def test_connect_timeout_and_register_addresses_set_each_calls_timer(tmp_path, monkeypatch, case):
    """AT-D9c (b), FP (D9; SVC-2): `c`, the URLs' `connect_timeout=`, and
    `N_a`, `register_addresses=`, set every timer that holds a connect.
    `connect_timeout=3` in the URLs gives `PGCONNECT_TIMEOUT=3` in each
    call's environment. T203's register fake never answers (it sleeps past
    every timer), and each register call ends by its client timer, no
    earlier than it (timing rule 3) and under twice it (timing rule 2), its
    time recorded against the timer with its margin: the snapshot at `S`,
    the commit at `C` and a lookup try at `T_L`, 8, 8 and 9 s with neither
    key, 9, 9 and 10 s at `[c3]`, and 12, 12 and 13 s at
    `[c3-two-addresses]`.

    Lane 2's reading: the plan's writer, whose snapshot the fake answers and
    whose commit and lookup it never does, under `LANES_REGISTER_DEADLINE_S=1`,
    is lane 4's L4-B3, so each row's call is made in process, one
    `PostgresStore(cfg, "register_writer").request(["SELECT 1"], <row>)` a
    row, as T257b's R-PG-1 cases drive the store (lane 1, #165 6752661856).
    Each call is cut by its own timer, `PsqlFailed.timer_expired`. It fails
    until lane 1's T106 lands (L1-A5: `REGISTER_BOUNDS`' `snapshot`,
    `commit` and `lookup` rows). The refusal of a `c` under 2 is
    `test_a_connect_timeout_under_2_is_refused_at_load_config`."""
    tail, extra, c, timers = TIMER_CASES[case]
    log = _register_fake(tmp_path, monkeypatch, tail, extra)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps([{"sleep": 120}]), encoding="utf-8")
    monkeypatch.setenv("FAKE_PSQL_ANSWERS", str(answers))
    mod = load_indexer()
    error = None
    try:
        store = mod.PostgresStore(mod.load_config(), "register_writer")
    except Exception as exc:  # the code under test, not this test, failed
        error = exc
    assert error is None, f"PostgresStore(cfg, 'register_writer') at [{case}]: {error!r}"
    for row, timer in timers.items():
        failure = None
        start = time.monotonic()
        try:
            store.request(["SELECT 1"], row)
        except Exception as exc:  # the timer under test, or another failure
            failure = exc
        took = time.monotonic() - start
        assert failure is not None, f"{row}: a call that never answers was answered"
        assert getattr(failure, "timer_expired", False) is True, \
            f"{row}: ended by {failure!r}, not by its client timer"
        assert timer <= took < 2 * timer, f"{row} at [{case}]: {took:.2f} s against its {timer} s"
        _record(f"{row}-{case}", took, timer, "timing rules 2 and 3")
    calls, probes = _fake_log(log)
    assert len(calls) == len(timers), f"one psql call a row: {len(calls)}"
    for record in calls + probes:
        assert record["connect_timeout"] == str(c), \
            f"PGCONNECT_TIMEOUT at [{case}]: {record['connect_timeout']!r}, not {c}"


#: D9's lookup row (AT-D9's table): the window every try starts inside, from
#: the first try's start, and `T_L`, each try's client timer, at `c` = 2 and
#: `N_a` = 1; the lookup's `statement_timeout`, 6000 ms; and the begin stamp's
#: own allowance, the timing wrapper's start, on each 1 s spacing.
LOOKUP_WINDOW_S, LOOKUP_T_L, LOOKUP_STATEMENT_S, WRAPPER_START_S = 10, 9, 6, 0.1


def _hold_head(pg):
    """F3 for a writer's commit and the lookup (AT-D9's F3: "for a writer's
    commit, the head row held `FOR UPDATE`"): the head row held by the test's
    own session in an open transaction, until the session is closed. Returns
    the session once it holds the row."""
    session = pg.session(appname="t257-f3")
    session.stdin.write(f"BEGIN;\nSELECT seq FROM {SCHEMA}.register_head FOR UPDATE;\n")
    session.stdin.flush()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        held = pg.psql("SELECT count(*) FROM pg_stat_activity WHERE application_name = "
                       "'t257-f3' AND state = 'idle in transaction';").stdout.strip()
        if held not in ("", "0"):
            return session
        time.sleep(0.1)
    session.kill()
    raise AssertionError("F3's head row was never held")


def _slow_lookup(pg, seconds: float) -> None:
    """F4 for the lookup (AT-D9's F4: "a policy forced on `journal` for its
    owner, since `find_write` runs as the owner"): a sleep the test creates in
    its own database, never the template, in a policy for every role, forced
    so that it binds the tables' owner: on `journal`, as the plan says, and on
    `register_head`, whose one row `find_write` locks first, since a fresh
    clone's journal may hold no row for a row policy to run on (lane 2's
    reading)."""
    pg.psql(f"SET search_path TO {SCHEMA};\n"
            f"CREATE FUNCTION t257_slow() RETURNS boolean LANGUAGE sql VOLATILE AS "
            f"$$ SELECT pg_sleep({seconds}) IS NOT NULL $$;\n"
            f"GRANT EXECUTE ON FUNCTION t257_slow() TO PUBLIC;\n"
            + "".join(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;\n"
                      f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;\n"
                      f"CREATE POLICY t257_slow ON {table} FOR ALL TO PUBLIC "
                      f"USING (t257_slow());\n" for table in ("journal", "register_head")))


@pytest.mark.parametrize("fault", ["F1", "F2", "F3", "F4"])
def test_the_lookups_tries_start_inside_the_window_and_end_in_3(pg, tmp_path, request, fault):
    """AT-D9's lookup row (D9; lane 4's answer 40; lane 1's T114,
    `refs/l1/T114-fu3`): `journal --write-id ...` for a write the database
    never saw, its `--not-after` a minute past and no `--clock`, so it calls
    at once and a healthy try would answer `absent`. Under each fault no try
    answers, and it exits 3 naming the id, the pending record kept: F1, a
    silent listener, each connect failing at `c`; F2, a relay silent after the
    startup, each try cut by `T_L`, 9 s, so a try starts no sooner than the
    last one's `T_L` after its start; F3, the head row held `FOR UPDATE`, each
    try a 55P03 at its 2000 ms `lock_timeout`; F4, a forced policy that sleeps
    (`_slow_lookup`), the first try ending with 57014 no earlier than its
    6000 ms and under twice it (timing rules 3 and 2), whether a further try
    follows not asserted.

    From the begin stamps of the command's own `psql` calls (T220f): at least
    one try; each try begun at least 1 s after the last began, less the
    wrapper's own start (`WRAPPER_START_S`); no try begun after the window,
    10 s from the first try's start, asserted at twice it (timing rule 2);
    and from the first try's start to the exit, at most `R` + `T_L` =
    10 + 9 = 19 s, asserted at twice it, its time recorded with its margin.
    It fails until lane 1's T114 lands (L1-A3), on T227's template and T228's
    logins; until T228 the writer's login is made here."""
    bench = Bench(pg, tmp_path, request)
    user = bench.login("lanes_register_writer")
    listener, session = None, None
    try:
        if fault == "F1":
            listener = SilentListener()
            config = bench.config("127.0.0.1", listener.port, user)
        elif fault == "F2":
            listener = StartupRelay(f"{pg.host}/.s.PGSQL.{pg.port}")
            config = bench.config("127.0.0.1", listener.port, user)
        else:
            if fault == "F3":
                session = _hold_head(pg)
            else:
                _slow_lookup(pg, 4 * LOOKUP_STATEMENT_S + 5)
            config = bench.config(quote(str(pg.host), safe=""), pg.port, user)
        proc, _ = bench.run("lookup", config)
    finally:
        if listener is not None:
            listener.close()
        if session is not None:
            _end(session)
    assert proc.returncode == 3, f"lookup-{fault}: {proc.returncode}: {proc.stderr}"
    assert bench.write_id in proc.stderr, f"the 3 names the write's id: {proc.stderr}"
    tries = [b["begin"] for b in bench.begins()]
    assert tries, "the lookup made no try"
    for before, after in zip(tries, tries[1:]):
        assert after - before >= 1 - WRAPPER_START_S, \
            f"lookup-{fault}: a try began {after - before:.2f} s after the last"
        if fault == "F2":
            assert after - before >= LOOKUP_T_L - WRAPPER_START_S, \
                f"lookup-F2: a try began {after - before:.2f} s after the last, inside its T_L"
    late = [round(t - tries[0], 2) for t in tries if t - tries[0] >= 2 * LOOKUP_WINDOW_S]
    assert not late, f"lookup-{fault}: tries began after the window: {late}"
    elapsed = bench.exited - tries[0]
    bound = LOOKUP_WINDOW_S + LOOKUP_T_L
    assert elapsed < 2 * bound, f"lookup-{fault}: {elapsed:.2f} s against {bound} s"
    _record(f"lookup-tries-{fault}", elapsed, bound, f"timing rule 2, {len(tries)} tries")
    if fault == "F3":
        assert any("55P03" in c["first"] for c in bench.calls()), \
            f"lookup-F3: no try ended with 55P03: {bench.calls()}"
    if fault == "F4":
        ended = [c for c in bench.calls() if "57014" in c["first"]]
        assert ended, f"lookup-F4: no try ended with 57014: {bench.calls()}"
        took = ended[0]["end"] - ended[0]["start"]
        assert LOOKUP_STATEMENT_S <= took < 2 * LOOKUP_STATEMENT_S, \
            f"lookup-F4: 57014 after {took:.2f} s"


# ======== AT-D9's orphaned writer, and AT-D9c's engine half of (a), (c) and (d) (T257d)

#: `psql`'s statement separator inside one request, `\;`, and #160's marker
#: line as `\echo` prints it (contract section 2.3), built here so that no
#: escape is spelled in this file.
SEP = chr(92) + ";"
ECHO_MARKER = chr(92) + "echo '" + chr(92) + "036LANES-INDEX-NEXT'"


def _shim(bench: Bench, arms: list, *, timed: bool = False) -> Path:
    """T203's shim (`PSQL_SHIM`, section 3.2) in front of the real `psql`,
    armed with `arms`. With `timed`, `TIMING_PSQL` stays first on `PATH` and
    hands each call to the shim, so each call's start and end are logged
    beside the shim's own log of its script; otherwise the shim is first on
    `PATH`. Returns the shim's directory, which holds its logs."""
    from sql_register_helpers import PSQL_SHIM
    where = bench.root / "shim" if timed else bench.bin
    where.mkdir(exist_ok=True)
    (where / "psql").write_text(PSQL_SHIM, encoding="utf-8")
    (where / "psql").chmod(0o755)
    _arm(where, bench, arms)
    if timed:
        bench.env["T220_REAL_PSQL"] = str(where / "psql")
    return where


def _arm(where: Path, bench: Bench, arms: list) -> None:
    from sql_register_helpers import PSQL_SHIM_CONTROL
    (where / PSQL_SHIM_CONTROL).write_text(json.dumps({"psql": bench.pg.psql_bin, "arms": arms}),
                                           encoding="utf-8")


def _shim_calls(where: Path) -> list:
    """The shim's log: each call that carries a request, in call order."""
    from sql_register_helpers import PSQL_SHIM_LOG
    log = where / PSQL_SHIM_LOG
    if not log.exists():
        return []
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]
    return [entry for entry in entries if entry.get("kind") != "version"]


def _writer(bench: Bench, config: Path, state: str, *,
            deadline: str | None = None) -> subprocess.Popen:
    """A writer's whole path, started: `lanes-edit.sh set-row-state` on the
    bench's lane, T257a's rows' path, which on primary is lane 4's L4-B3
    (T413 to T415). `deadline` is `LANES_REGISTER_DEADLINE_S`; unset, the
    deadline is D7's 30 s, as in AT-4 (c). The lane's own checkout is made
    first, where the bench has none yet (`Bench.lane_checkout`, T257l)."""
    bench.lane_checkout()
    env = dict(bench.env, LANES_INDEX_CONFIG=str(config), LANES_LANE="repoA-2")
    env.pop("LANES_REGISTER_DEADLINE_S", None)
    if deadline is not None:
        env["LANES_REGISTER_DEADLINE_S"] = deadline
    return subprocess.Popen(["bash", str(bench.copy.parent / "lanes-edit.sh"), "set-row-state",
                             "repoA-2", state], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
                            cwd=str(bench.wip))


def _activity(pg, appname: str) -> tuple:
    """(the session's state, the seconds since that state began), or ('', 0)
    where no session of `appname` is connected."""
    said = pg.psql("SELECT state, extract(epoch FROM clock_timestamp() - state_change) "
                   f"FROM pg_stat_activity WHERE application_name = '{appname}';").stdout.strip()
    if not said:
        return "", 0.0
    state, _, age = said.splitlines()[0].partition("|")
    return state, float(age or 0)


#: The idle bound on a writer's open transaction, the group's
#: `idle_in_transaction_session_timeout` (AT-D9, "Beside the table").
IDLE_BOUND_S = 5


def test_an_orphaned_writer_transaction_is_ended_by_the_idle_bound(pg, tmp_path, request):
    """AT-D9, beside the table: a session as `lanes_register_writer` that
    replays a commit call's script without its `COMMIT` (test 12's held
    session) holds the head row and idles. `idle_in_transaction_session_
    timeout` ends it no earlier than 5 s after it idles (timing rule 3) and
    under twice that (timing rule 2), from `pg_stat_activity.state_change`,
    after which a waiting write commits, 0.

    The script is a real one: a first writer, `lanes-edit.sh set-row-state`
    through T203's shim, whose `fail-match` on `commit_write` fails its
    commit calls unsent; the shim's log holds the commit call's script, which
    the held session replays as the writer's login with its last statement,
    `COMMIT`, left off, and its entry's `not_after` moved 30 s past the
    replay's start (T257m). The login has the writer's floors, the idle
    bound among them, as `login add` sets them (`Bench.login`'s `floors`,
    T257m). The waiting write is a second writer under D7's 30 s,
    started once the session idles. It fails until lane 4's L4-B3 (T414's
    seam and T415's attempt loop; only T413 is in lane 4's share) and lane
    1's T112 land, on T227's template and T228's logins. The bench's
    database is at `primary` first (`Bench.to_primary`, T257m)."""
    bench = Bench(pg, tmp_path, request)
    bench.to_primary()
    user = bench.login("lanes_register_writer", floors=True)
    config = bench.config(quote(str(pg.host), safe=""), pg.port, user)
    where = _shim(bench, [{"mode": "fail-match", "match": "commit_write"}])
    first = _writer(bench, config, f"PAUSED {DOT} T257's orphan, unsent", deadline="3")
    out, err = first.communicate(timeout=300)
    scripts = [e["stdin"] for e in _shim_calls(where) if "commit_write" in e.get("stdin", "")]
    assert scripts, f"the first writer sent no commit call: {first.returncode}: {err}"
    parts = [part.strip() for part in scripts[0].strip().rstrip(";").split(SEP)]
    assert parts[-1] == "COMMIT", f"the commit call's script ends with COMMIT: {parts}"
    # ITS `not_after` MOVES WITH THE REPLAY (T257m; line BD-18): the entry's
    # `not_after` (F3) is the snapshot's clock plus `C` and 2 s, about 10 s on,
    # and the replay starts once the first writer has exited, past it, where
    # `commit_write` refuses the entry and the session ends before it idles. The
    # held session stands for a commit sent in time whose client went away, so it
    # carries a `not_after` 30 s past the replay's start; nothing else changes.
    fresh = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 30))
    parts = [re.sub(r'"not_after":"[^"]*"', f'"not_after":"{fresh}"', part) for part in parts]
    assert sum(part.count('"not_after"') for part in parts) == 1, \
        f"the commit call's entry carries one not_after: {parts}"
    _arm(where, bench, [])
    orphan = pg.session(user=user, appname="t257-orphan")
    waiting = None
    try:
        orphan.stdin.write((" " + SEP + " ").join(parts[:-1]) + ";\n")
        orphan.stdin.flush()
        deadline = time.monotonic() + 30
        state, age = _activity(pg, "t257-orphan")
        while state != "idle in transaction" and time.monotonic() < deadline:
            time.sleep(0.05)
            state, age = _activity(pg, "t257-orphan")
        assert state == "idle in transaction", f"the replayed commit never idled: {state!r}"
        idled = time.monotonic() - age
        waiting = _writer(bench, config, f"PAUSED {DOT} T257's waiting write")
        while _activity(pg, "t257-orphan")[0] and time.monotonic() - idled < 4 * IDLE_BOUND_S:
            time.sleep(0.05)
        ended = time.monotonic() - idled
        assert not _activity(pg, "t257-orphan")[0], \
            f"the orphan still holds the head row {ended:.2f} s after it idled"
        assert IDLE_BOUND_S <= ended < 2 * IDLE_BOUND_S, \
            f"the idle bound ended the orphan {ended:.2f} s after it idled"
        _record("orphaned-writer", ended, IDLE_BOUND_S, "timing rules 2 and 3")
        out, err = waiting.communicate(timeout=300)
        assert waiting.returncode == 0, f"the waiting write did not commit: {waiting.returncode}: {err}"
    finally:
        if waiting is not None and waiting.poll() is None:
            waiting.kill()
        _end(orphan)


#: AT-D9c (a)'s engine half: #160's reads that need no clock, so that two
#: sends of them answer the same bytes.
SNAPSHOT_READS = ["SELECT version, writers_from, readers_from FROM schema_version WHERE id = 1",
                  "SELECT mode, marker_state, generation FROM register_switch WHERE id = 1",
                  "SELECT seq FROM register_head WHERE id = 1"]


def test_the_joined_snapshot_logs_one_statement_and_reads_byte_identical_to_the_one_by_one_form(
        counting_cluster, tmp_path, monkeypatch):
    """AT-D9c (a), the engine half, on section 5.6's counting cluster
    (`log_statement=all`: one `statement:` line per Query message): each of
    the three register calls, the snapshot, the commit and the lookup, logs
    ONE `statement:` line; and the joined snapshot's stdout equals, byte for
    byte, the same statements sent one by one, the marker as `\\echo` prints
    it, so #160's parse is unchanged.

    The calls are made in process as the fixture's writer login, through
    `PostgresStore(cfg, "register_writer")` (lane 2's reading, as T257c's
    `[commit]`): the snapshot by `_query_many(SNAPSHOT_READS, snapshot=True,
    row="snapshot")`, whose `psql` stdout is kept; the commit by lane 1's
    `register_commit_request`, which `commit_write` may refuse, a refusal
    being one statement too; the lookup by `register_lookup_request`. The
    one-by-one form is the real `psql`, with section 2.2's argv, fed the same
    statements each with its own `;`. It fails until lane 1's T106, T112 and
    T114 land, on T229's counting cluster."""
    from pgcluster import FX_WRITER, Database
    db = Database(counting_cluster, counting_cluster.new_database())
    config = _private(tmp_path / "conf" / "lanes-index.conf", "\n".join([
        "mode=index", f"register_url={db.url(FX_WRITER)}",
        f"register_passfile={counting_cluster.passfile(FX_WRITER)}",
        f"reader_url={db.url(FX_WRITER)}",
        f"reader_passfile={counting_cluster.passfile(FX_WRITER)}",
        "register_schema=lanes_register", ""]))
    for key in list(os.environ):
        if key.startswith("PG"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("LANES_INDEX_CONFIG", str(config))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    mod = load_indexer()
    store = mod.PostgresStore(mod.load_config(), "register_writer")
    outs, run = [], store._run

    def kept(*args, **kwargs):
        out = run(*args, **kwargs)
        if args and "REPEATABLE READ" in str(args[0]):  # the snapshot's request alone
            outs.append(out)
        return out
    store._run = kept
    log = counting_cluster.log()

    def statements(send) -> int:
        offset = log.stat().st_size
        try:
            send()
        except Exception:  # a refusal is still one statement: counted below
            pass
        time.sleep(0.3)  # the logger's last line
        text = log.read_bytes()[offset:].decode("utf-8", "replace")
        return len(re.findall(r"statement: ", text))

    not_after = int(time.time()) - 60
    counts = {
        "snapshot": statements(lambda: store._query_many(list(SNAPSHOT_READS), snapshot=True,
                                                         row="snapshot")),
        "commit": statements(lambda: store.request(
            mod.register_commit_request(store.schema, 0, WRITE, {"t257": "commit"}), "commit")),
        "lookup": statements(lambda: store.request(
            mod.register_lookup_request(store.schema, WRITE, not_after), "lookup")),
    }
    assert counts == {"snapshot": 1, "commit": 1, "lookup": 1}, \
        f"each call is one statement line: {counts}"
    assert outs, "the snapshot's psql answered nothing to keep"
    lines = [f'SET search_path TO "{store.schema}";',
             "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;"]
    for query in SNAPSHOT_READS:
        lines += [f"COPY ({query}) TO STDOUT;", ECHO_MARKER]
    lines.append("COMMIT;")
    one_by_one = subprocess.run([db.psql_bin, *REGISTER_ARGV], input="\n".join(lines) + "\n",
                                capture_output=True, text=True, env=db.env(FX_WRITER), timeout=60)
    assert one_by_one.returncode == 0, one_by_one.stderr
    assert outs[0] == one_by_one.stdout, \
        f"the joined snapshot read {outs[0]!r}, one by one {one_by_one.stdout!r}"


#: `C`, the commit's client timer, at `c` = 2 and `N_a` = 1 (D9).
COMMIT_C_S = 8


def test_the_lookups_wait_counts_from_the_snapshot_calls_end_and_gets_no_lr011(
        pg, tmp_path, request):
    """AT-D9c (c): T203's shim holds the snapshot call 2.5 s before it hands
    it on (`window`), so the database reads its clock 2.5 s after the call
    started, and the first commit call is lost as `before` loses it, under
    `LANES_REGISTER_DEADLINE_S=1`. The lookup's first try gets no LR011, and
    it starts no earlier than the snapshot call's end plus `C` less 1 s
    (timing rule 3) and under twice `C` plus 1 s, 18 s, after that end
    (timing rule 2), `C` being 8 s here (lane 4's section, "The in-doubt rule
    (F3, D8)"). A client that counted from the call's start would call 2.5 s
    early and meet LR011.

    `TIMING_PSQL` hands each call to the shim, so each call's start and end
    are logged beside the shim's log of its script, in the same order; no
    call may be cut by its timer, or the two logs would not pair. It fails
    until lane 4's L4-B3 (T414, T415) and lane 1's T111, T112 and T114 land,
    on T227's template and T228's logins. The bench's database is at
    `primary` first (`Bench.to_primary`, T257m)."""
    bench = Bench(pg, tmp_path, request)
    bench.to_primary()
    user = bench.login("lanes_register_writer")
    config = bench.config(quote(str(pg.host), safe=""), pg.port, user)
    where = _shim(bench, [{"mode": "window", "ms": 2500, "call": 1},
                          {"mode": "before", "match": "commit_write", "call": 1}], timed=True)
    writer = _writer(bench, config, f"PAUSED {DOT} T257's lookup wait", deadline="1")
    out, err = writer.communicate(timeout=300)
    scripts, times = _shim_calls(where), bench.calls()
    assert len(times) == len(scripts), \
        f"a call was cut by its timer: {len(scripts)} sent, {len(times)} ended: {err}"
    snapshot = next((i for i, e in enumerate(scripts) if "commit_write" not in e["stdin"]
                     and "find_write" not in e["stdin"]), None)
    lookup = next((i for i, e in enumerate(scripts) if "find_write" in e["stdin"]), None)
    assert snapshot is not None and lookup is not None, \
        f"the writer made no snapshot and lookup: {writer.returncode}: {err}"
    assert "LR011" not in times[lookup]["first"], f"the first try met LR011: {times[lookup]}"
    gap = times[lookup]["start"] - times[snapshot]["end"]
    assert COMMIT_C_S - 1 <= gap < 2 * COMMIT_C_S + 1, \
        f"the lookup's first try started {gap:.2f} s after the snapshot call's end"
    _record("lookup-wait", gap, COMMIT_C_S, "timing rules 2 and 3, from the snapshot call's end")


#: AT-D9c (d)'s link: 75 ms each way, TLS on (T229's relay, R-P23), `c` = 3
#: and one address, so `S` = `C` = 9 s, `T_L` = 10 s and a reader's 7 s.
DELAY_S = 0.075
LINK_TIMERS = {"snapshot": 9, "commit": 9, "lookup": 10, "read": 7}


def _link_config(path: Path, cluster, port: int, writer: str) -> Path:
    """A configuration for the TLS cluster through the relay at `port`:
    lane 1's URL form (`TLSCluster.url`, `verify-full`, the root alone) with
    the relay's port and `connect_timeout=3`, as a workstation at that round
    trip sets `c`, and one address; `writer` and the fixture's reader, each
    with its password file."""
    from pgcluster import FX_READER

    def url(user: str) -> str:
        return cluster.url(user).replace(f"@127.0.0.1:{cluster.port}/",
                                         f"@127.0.0.1:{port}/") + "&connect_timeout=3"
    return _private(path, "\n".join([
        "mode=primary", f"register_url={url(writer)}",
        f"register_passfile={cluster.passfile(writer)}", f"reader_url={url(FX_READER)}",
        f"reader_passfile={cluster.passfile(FX_READER)}",
        f"register_label={cluster.label_of()}", "register_schema=lanes_register", ""]))


def test_over_a_delayed_tls_link_no_healthy_call_meets_its_timer(tls_cluster, tmp_path,
                                                                    request):
    """AT-D9c (d), test 9's per-call runs over the delayed loopback, TLS on:
    a writer's whole write (its snapshot and its commit), a lookup of a write
    the database never saw, and a reader's read. No healthy call meets its
    timer: every call that began has ended with `psql`'s own exit, in the
    timing log, none cut by its client timer, and each call's time is
    recorded against its timer, `S` = `C` = 9 s, `T_L` = 10 s and a reader's
    7 s, with its margin. The TLS cluster's database is at `primary` first
    (`Bench.to_primary`, T257m). It fails until lane 4's L4-B3 (T414, T415)
    and lane 1's T111 to T114 land, on T229's TLS cluster and relay."""
    from pgcluster import FX_WRITER, Database, delayed_loopback
    bench = Bench(Database(tls_cluster, tls_cluster.database_name), tmp_path, request)
    bench.to_primary()
    where = _shim(bench, [], timed=True)
    with delayed_loopback(tls_cluster.port, DELAY_S) as relay:
        config = _link_config(tmp_path / "conf" / "lanes-index.conf", tls_cluster, relay.port,
                              FX_WRITER)
        writer = _writer(bench, config, f"PAUSED {DOT} T257's delayed link")
        _, err = writer.communicate(timeout=300)
        assert writer.returncode == 0, f"the healthy write: {writer.returncode}: {err}"
        kinds = ["commit" if "commit_write" in e["stdin"] else "snapshot"
                 for e in _shim_calls(where)]
        proc, _ = bench.run("lookup", config)
        kinds += ["lookup"] * (len(_shim_calls(where)) - len(kinds))
        proc, _ = bench.run("reader", config)
        kinds += ["read"] * (len(_shim_calls(where)) - len(kinds))
    times = bench.calls()
    assert len(times) == len(kinds), \
        f"a healthy call was cut by its timer: {len(kinds)} began, {len(times)} ended"
    assert {"snapshot", "commit", "lookup", "read"} <= set(kinds), f"the calls made: {kinds}"
    for kind, call in zip(kinds, times):
        took = call["end"] - call["start"]
        assert took < LINK_TIMERS[kind], f"{kind}: {took:.2f} s, at its {LINK_TIMERS[kind]} s timer"
        _record(f"link-{kind}", took, LINK_TIMERS[kind], "AT-D9c (d), recorded")


@pytest.mark.parametrize("logins", ["one-login", "two-logins"])
def test_a_burst_of_ten_over_a_delayed_tls_link_commits_each_once_or_exits_75_with_nothing_written(
        tls_cluster, tmp_path, request, logins):
    """AT-D9c (d), test 4's burst of ten over the delayed loopback, TLS on,
    one request per call, under D7's 30 s, `LANES_REGISTER_DEADLINE_S`
    unset as in AT-4 (c): every writer commits once, or exits 75 with nothing
    written, its write id absent from the journal, and no writer ends any
    other way; the new seqs have no gap and no repeat. Each writer's time
    from the release to its exit, and the burst's snapshot calls in the
    shim's log, are recorded, never asserted: act 3's test 4 decides D7.
    `[two-logins]` splits the ten across two engineers' writer logins, five
    each, the second's made by `lanes-index login add` through the admin
    service, as the fixture's are (X, logins), since the head row serialises
    every login's commits.

    Lane 2's reading: the ten writers share the bench's one checkout, as
    `set-row-state` on one lane, each its own state. The TLS cluster's
    database is at `primary` first (`Bench.to_primary`, T257m). It fails
    until lane 4's L4-B3 (T414, T415) and lane 1's T111 to T114 land, on
    T229's TLS cluster and relay."""
    from pgcluster import FX_WRITER, PASSWORD_LINE, Database, delayed_loopback
    db = Database(tls_cluster, tls_cluster.database_name)
    bench = Bench(db, tmp_path, request)
    bench.to_primary()
    where = _shim(bench, [], timed=True)
    writers = [FX_WRITER] * 10
    if logins == "two-logins":
        service = tls_cluster.admin_service(tls_cluster.database_name)
        code, out, _ = tls_cluster.lanes_index_tty(["login", "add", "fx2",
                                                    "--admin-service", service])
        assert code == 0, f"login add fx2 exited {code}"
        tls_cluster.passwords.update(PASSWORD_LINE.findall(out))
        writers = [FX_WRITER] * 5 + ["lanes_w_fx2"] * 5
    head = int(db.psql(f"SELECT seq FROM {SCHEMA}.register_head;").stdout.strip() or 0)
    with delayed_loopback(tls_cluster.port, DELAY_S) as relay:
        configs = {login: _link_config(tmp_path / "conf" / login / "lanes-index.conf", tls_cluster,
                                       relay.port, login) for login in set(writers)}
        bench.lane_checkout()
        release = time.monotonic()
        procs = [_writer(bench, configs[login], f"PAUSED {DOT} T257's burst {i}")
                 for i, login in enumerate(writers)]
        ends = []
        for proc in procs:
            _, err = proc.communicate(timeout=300)
            ends.append((proc.returncode, time.monotonic() - release, err))
    codes = [code for code, _, _ in ends]
    assert set(codes) <= {0, 75}, f"a writer ended another way: {[(c, e[-200:]) for c, _, e in ends]}"
    rows = db.psql(f"SELECT seq, write_id FROM {SCHEMA}.journal WHERE seq > {head} "
                   f"ORDER BY seq;").stdout.split()
    seqs = [int(row.split("|")[0]) for row in rows]
    assert seqs == list(range(head + 1, head + 1 + codes.count(0))), \
        f"one entry for each writer that committed, no gap, no repeat: {seqs}, {codes}"
    sent = set(re.findall(r"commit_write\([0-9-]+, '([0-9a-f-]{36})'",
                          "".join(e["stdin"] for e in _shim_calls(where))))
    written = [row.split("|")[1] for row in rows]
    assert len(set(written)) == len(written) and set(written) <= sent, \
        f"each write id committed once, and only the burst's: {written}"
    snapshots = sum(1 for e in _shim_calls(where) if "commit_write" not in e["stdin"])
    for i, (code, took, _) in enumerate(ends):
        print(f"D9c burst [{logins}] writer {i} ({writers[i]}): exit {code} after {took:.2f} s")
    print(f"D9c burst [{logins}]: {codes.count(0)} committed, {codes.count(75)} out with 75, "
          f"{snapshots} snapshot calls")


# ============================== D9's rollback and cutover rows (T278), real engine

#: The `git` wrapper that fails each push (TP:3633-3634, "a cutover whose push
#: the `git` wrapper fails"), first on `PATH`; every other git call goes on to
#: the real `git`, which `T278_REAL_GIT` names.
GIT_NO_PUSH = ('#!/bin/sh\n'
               '# T278: the git wrapper that fails the push; every other call goes on\n'
               'for arg in "$@"; do\n'
               '  if [ "$arg" = push ]; then echo "T278: push failed by the test" >&2; exit 1; fi\n'
               'done\n'
               'exec "$T278_REAL_GIT" "$@"\n')
#: The rollback's lost turns (TP:3607 at B14): `LANES_REGISTER_DEADLINE_S=6` and its
#: calls' 5000 ms `lock_timeout`. Its check has no figure of its own: the 75
#: cell's bound takes the last try's check as measured from the `git`
#: wrapper's and the shim's logs, not a fixed 15 s (lane 3's batch 11 (7)(b),
#: #165 6783909985; `_rollback_checks`).
ROLLBACK_DEADLINE_S, ROLLBACK_LOCK_S = 6, 5
#: T278b's `git` wrapper for the rollback's check (TP:3607 at B14, "where the
#: check is the fetch of `origin main` and the head read, timed from the `git`
#: wrapper's and the shim's logs"): first on `PATH`, it runs the real `git`,
#: which `T278_REAL_GIT` names, on the same standard streams, and then logs
#: the call's argv, its parent's pid, its start and end on the monotonic
#: clock and its exit, one JSON object a call, in `git-timing.log` beside it.
GIT_TIMING = r'''#!/usr/bin/env python3
# T278b's git wrapper: each call's start and end, logged beside it.
import time
start = time.monotonic()
import json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
real = os.environ.get("T278_REAL_GIT") or next(
    (os.path.join(d, "git") for d in os.environ.get("PATH", "").split(os.pathsep)
     if d and os.path.realpath(d) != os.path.realpath(here)
     and os.access(os.path.join(d, "git"), os.X_OK)), "git")
code = subprocess.call([real] + sys.argv[1:])
with open(os.path.join(here, "git-timing.log"), "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": sys.argv[1:], "ppid": os.getppid(), "start": start,
                             "end": time.monotonic(), "exit": code}) + "\n")
sys.exit(code if code >= 0 else 128 - code)
'''
#: The register's write functions, as a request calls them (`TIMING_PSQL`'s
#: and the shim's logs).
WRITE_CALLS = ("commit_write(", "switch_to_files(", "record_marker(")


class Operator:
    """T278's operator estate (TP:3627-3641, "The operator rows run the real
    commands"): test 7's fixture register, T211's `FixtureRegister` (a bare
    origin and the operator lane's checkout), imported at C into this test's
    own database by `lanes-index import --at` (lane 1's T115), as
    `pgcluster`'s `tmpl_imported` is built, since a template keeps no origin
    a cutover can push to. T203's flipped copy of `lanes-index`
    (`RENDER_GIT_HALF` True), so the operator's commands run on the
    register's own schema; a login of REGISTER-WRITER's, made here as T220's
    rows make theirs (the cluster's socket takes it by trust); and
    `TIMING_PSQL` first on `PATH`.

    `estate`: `imported`, as the import leaves it, the switch at `files` with
    the marker `absent`; `primary`, brought to `primary` with the marker
    `present` by AT-LR006's route (the import module's `_to_primary`), which
    pushes nothing, so origin carries no marker commit (T257's writer rows);
    `cutover-done`, AT-6's "the cutover done (the switch at `primary`, and
    `lanes/STORE` on a bare origin)": the imported estate cut over by the
    real `cutover --import <C>` (lane 3's T327), whose marker commit, with
    its `Register-Seq`, is pushed to origin, read back and recorded (T278d);
    or `stray`, `cutover-done` with test 6's stray commit on origin after
    the marker commit, so that it never reached the register (T278e,
    `_stand_in_stray`).

    THE STRAY IS A STAND-IN (T278e; line BD15; TP open point 5's second
    choice, "a stand-in stray commit, which does not prove the real old
    writer"): AT-6's stray is the v1.1.0 `lanes-edit.sh`'s `log NOTED`,
    pushed by a stale workstation that knows no marker, and its pinned copy
    is test 6's, in another module's fixtures. Today's `lanes-edit.sh`
    refuses a files-mode write once origin carries `lanes/STORE` (FR-004's
    marker check), so it can make no stray on this estate. So a clone of
    origin with no configuration appends one `NOTED` line, in the form the
    fixture's own `log NOTED` wrote at C, to the same `lanes/log/` file, and
    pushes it by plain `git`. T278 made its stray with today's writer on
    `_to_primary`'s estate, whose origin carried no `Register-Seq`, so both
    ways out refused 2 there ("origin main's last Register-Seq could not be
    found"). Line BD15 saw that only on a scratch probe: on T326-m23 both
    ways out end 1 first, a traceback, since T324's `_stray_recognised`
    unpacks five of the six values T326 made `_render_read_head` return.

    WHY THE ROLLBACK'S ESTATE IS `cutover-done` (T278d; line BD15): T326's
    step 0 fetches `origin main` on every try and walks its first-parent
    line for the last `Register-Seq` (`rollback_step_0_git_half`, T322's
    pass bounded at seq 0). On `_to_primary`'s estate no commit carries one,
    so the rollback refused 2, "walk-failed", before step 1 ever ran. The
    setup cutover runs with `TIMING_PSQL` off its `PATH`, so the timing,
    send and begin logs hold the test's own command alone."""

    def __init__(self, pg, tmp_path: Path, request, estate: str = "imported"):
        from sql_register_helpers import flipped_copy
        from test_sql_register_import import OPERATOR, TIP_A, FixtureRegister, _to_primary
        self.pg, self.root, self.request, self.lane = pg, tmp_path, request, OPERATOR
        self.reg = FixtureRegister(tmp_path / "reg")
        noted = self.reg.c
        if estate in ("imported", "cutover-done", "stray"):
            # THE SEED'S HOLD WITH NO TIME IS RELEASED BEFORE THE IMPORT (line HC14; W3a's
            # T211n `3fe23d7`, whose `HOLD_NO_UTC_RELEASE` this inlines, since BD's import
            # module predates it): lane 1's open-`HOLD` check (merge21f6) counts
            # `TAKE_LINES["hold-no-utc"]` as open, so a first-form cutover over it refuses 2.
            # Its holder, the operator lane, releases it in files mode, and C is the tip after.
            # `imported`, `cutover-done` and `stray` cut over; `primary` comes through
            # `_to_primary`.
            proc = self.reg.edit("append-line", "HOLD RELEASED — lane repoA-2 (Eagle), "
                                 f"2026-10-01T05:20:00Z: opensoft/repoH main {TIP_A}",
                                 env={"LANES_LANE": OPERATOR})
            assert proc.returncode == 0, (
                f"the dead HOLD's release, lanes-edit.sh append-line: {proc.stdout}{proc.stderr}")
            self.reg.c = self.reg.tip()
        proc = self.reg.import_at(pg, self.reg.c)
        assert proc.returncode == 0, \
            f"lanes-index import --at C (lane 1's T115): {proc.returncode}: {proc.stderr}"
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        (self.bin / "psql").write_text(TIMING_PSQL, encoding="utf-8")
        (self.bin / "psql").chmod(0o755)
        self.timing = self.bin / "psql-timing.log"
        self.copy = flipped_copy(INDEXER, tmp_path / "tool", True)
        for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
            if (REPO / name).exists():
                shutil.copy2(REPO / name, tmp_path / "tool" / name)
        self.passfile = _private(tmp_path / "conf" / "pgpass")
        self.user = f"t278_{uuid.uuid4().hex[:12]}"
        pg.psql(f"CREATE ROLE {self.user} LOGIN IN ROLE lanes_register_writer;")
        request.addfinalizer(lambda: pg.cluster.psql(f"DROP ROLE IF EXISTS {self.user};",
                                                     check=False))
        self.env = dict(self.reg.env, T220_REAL_PSQL=pg.psql_bin, LANES_LANE=OPERATOR,
                        PATH=str(self.bin) + os.pathsep + self.reg.env["PATH"])
        self.mode, self.stray = "index", None
        if estate == "primary":
            _to_primary(pg, self.reg, load_indexer())
            self.mode = "primary"
        if estate in ("cutover-done", "stray"):
            # THE REAL CUTOVER (T278d), off `TIMING_PSQL`: the setup's own calls never
            # reach the logs the test reads, and no fault is armed by its `commit_write`.
            proc, _ = self.run(self.argv("cutover"), self.config(),
                               {"PATH": self.reg.env["PATH"]})
            assert proc.returncode == 0, (
                f"the estate's cutover --import C (lane 3's T327): {proc.returncode}: "
                f"{proc.stderr}")
            switch = self.state()[0].split("|")[:2]
            assert switch == ["primary", "present"], f"the estate's cutover left {switch}"
            assert self.origin_tip() != self.reg.c, "the cutover's marker commit is not on origin"
            self.mode = "primary"
        if estate == "stray":
            marker = self.origin_tip()
            self.stray = self._stand_in_stray(noted)
            assert self.stray not in (self.reg.c, marker), "the stray commit reached origin"

    def _git(self, *argv: str) -> str:
        """`git` with the fixture's environment; its stdout."""
        return subprocess.run(["git", *argv], capture_output=True, text=True, check=True,
                              env=self.reg.env, stdin=subprocess.DEVNULL).stdout

    def _stand_in_stray(self, noted: str) -> str:
        """Test 6's stray, a stand-in (T278e; the class's docstring): a
        clone of origin with no configuration appends one line to the
        `lanes/log/` file that the fixture's `log NOTED` at `noted` changed,
        that commit's own added line with its text made the stray's, and
        pushes it to origin's `main` by plain `git`. Returns origin's tip,
        the stray."""
        wip = str(self.reg.wip)
        paths = [p for p in self._git("-C", wip, "diff-tree", "--no-commit-id", "--name-only",
                                      "-r", noted).split() if p.startswith("lanes/log/")]
        assert len(paths) == 1, f"the fixture's log NOTED changed one log file: {paths}"
        added = [line[1:] for line in self._git("-C", wip, "diff", f"{noted}^", noted, "--",
                                                paths[0]).splitlines()
                 if line.startswith("+") and not line.startswith("+++")
                 and "the import's fixture, at C" in line]
        assert len(added) == 1, f"the fixture's log NOTED added one line of its text: {added}"
        clone = self.root / "stale"
        self._git("clone", "-q", str(self.reg.origin), str(clone))
        target = clone / paths[0]
        text = target.read_text(encoding="utf-8")
        target.write_text(text + ("" if text.endswith("\n") else "\n")
                          + added[0].replace("the import's fixture, at C", "T278's stray commit")
                          + "\n", encoding="utf-8")
        message = self._git("-C", wip, "log", "-1", "--format=%B", noted).replace(
            "the import's fixture, at C", "T278's stray commit")
        self._git("-C", str(clone), "add", "--", paths[0])
        self._git("-C", str(clone), "commit", "-q", "-m", message)
        self._git("-C", str(clone), "push", "-q", "origin", "HEAD:main")
        return self.origin_tip()

    def origin_tip(self) -> str:
        """The bare origin's `main`, read there, so a push from any checkout
        shows."""
        return subprocess.run(["git", "--git-dir", str(self.reg.origin), "rev-parse", "main"],
                              capture_output=True, text=True, check=True,
                              env=self.reg.env).stdout.strip()

    def config(self, host: str | None = None, port: int | None = None) -> Path:
        """The operator's configuration (CLI section 2.5): both URLs name
        `host:port`, or the cluster's socket, as this test's login, a private
        password file, `register_label=` and `register_schema=`."""
        from test_sql_register_import import LABEL
        host = host or quote(str(self.pg.host), safe="")
        url = f"postgresql://{self.user}@{host}:{port or self.pg.port}/{self.pg.name}"
        return _private(self.root / "conf" / "lanes-index.conf", "\n".join([
            f"mode={self.mode}", f"register_url={url}", f"register_passfile={self.passfile}",
            f"reader_url={url}", f"reader_passfile={self.passfile}",
            f"register_label={LABEL}", f"register_schema={SCHEMA}", ""]))

    def argv(self, row: str, form: str = "import-single") -> list:
        """The row's command (CLI's USAGE; lane 3's T304, T324, T326 and T327
        for the forms merge10 lacks): `rollback`; `cutover --import <C>`,
        which its abort and `record_marker` follow; and the stray ways out,
        `import --single <sha>` or `render --revert <sha>` on the stray."""
        if row == "rollback":
            return ["rollback"]
        if row in ("cutover", "switch-to-files", "record-marker"):
            return ["cutover", "--import", self.reg.c]
        if form == "render-revert":
            return ["render", "--revert", self.stray]
        return ["import", "--single", self.stray]

    def fail_push(self) -> None:
        """`GIT_NO_PUSH` first on `PATH`, for the cutover's abort."""
        (self.bin / "git").write_text(GIT_NO_PUSH, encoding="utf-8")
        (self.bin / "git").chmod(0o755)
        self.env["T278_REAL_GIT"] = shutil.which("git", path=self.reg.env["PATH"]) or "git"

    def time_git(self) -> None:
        """`GIT_TIMING` first on `PATH`, for the rollback's check (T278b)."""
        (self.bin / "git").write_text(GIT_TIMING, encoding="utf-8")
        (self.bin / "git").chmod(0o755)
        self.env["T278_REAL_GIT"] = shutil.which("git", path=self.reg.env["PATH"]) or "git"

    def git_calls(self) -> list:
        """`GIT_TIMING`'s log: each `git` call that ended, in order."""
        log = self.bin / "git-timing.log"
        return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] \
            if log.exists() else []

    def run(self, argv: list, config: Path, extra: dict | None = None) -> tuple:
        """`lanes-index <argv>` from the operator's checkout, as the operator
        lane; (the process, its elapsed seconds). Its pid and exit stamp are
        kept for `begins`."""
        env = dict(self.env, LANES_INDEX_CONFIG=str(config), **(extra or {}))
        start = time.monotonic()
        with subprocess.Popen([sys.executable, str(self.copy), *argv], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              env=env, cwd=str(self.reg.wip)) as child:
            self.pid = child.pid
            try:
                out, err = child.communicate(timeout=300)
            except subprocess.TimeoutExpired:
                child.kill()
                raise
            self.exited = time.monotonic()
        return subprocess.CompletedProcess(argv, child.returncode, out, err), self.exited - start

    def lane_checkout(self) -> Path:
        """`<c>`, the operator lane's own register checkout, made once (T257l;
        lane 4's triage, #165 6833813092, its group b1), as
        `Bench.lane_checkout` makes the bench's: `<W>-lanes/<lane>`, W being
        the real path of the fixture's `workspace.yaml` `path:`, its view of
        the clone (`self.reg.ws`; Amendment 23 S5), and a clone of W's
        origin. On primary a write refuses with nothing sent where it is not
        there (`pw_checkout`, T415's R17). Only a writer makes it, after the
        estate is built, so no operator command meets it."""
        real = Path(os.path.realpath(self.reg.ws))
        target = real.parent / f"{real.name}-lanes" / self.lane
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            self._git("clone", "-q", str(self.reg.origin), str(target))
        return target

    def write(self, config: Path) -> tuple:
        """A writer's whole path on this estate (T257j): `lanes-edit.sh
        set-row-state` on the operator's lane, from its checkout, at
        `LANES_REGISTER_DEADLINE_S=3`, D9's test value, as T257a's rows ran it
        on `Bench`; (the process, its elapsed seconds), its pid and exit
        stamp kept. The lane's own checkout is made first (T257l)."""
        argv = ["bash", str(self.copy.parent / "lanes-edit.sh"), "set-row-state", self.lane,
                f"PAUSED {DOT} T257's writer row"]
        env = dict(self.env, LANES_INDEX_CONFIG=str(config), LANES_REGISTER_DEADLINE_S="3")
        self.lane_checkout()
        start = time.monotonic()
        with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, env=env,
                              cwd=str(self.reg.wip)) as child:
            self.pid = child.pid
            try:
                out, err = child.communicate(timeout=300)
            except subprocess.TimeoutExpired:
                child.kill()
                raise
            self.exited = time.monotonic()
        return subprocess.CompletedProcess(argv, child.returncode, out, err), self.exited - start

    def calls(self) -> list:
        """`TIMING_PSQL`'s log: each call that ended, in order."""
        if not self.timing.exists():
            return []
        return [json.loads(l) for l in self.timing.read_text(encoding="utf-8").splitlines()
                if l and json.loads(l)["argv"] != ["--version"]]

    def sent(self) -> list:
        """`TIMING_PSQL`'s send stamps: each request read, with the write
        functions it calls, before its `psql` connects (T278)."""
        log = self.bin / "psql-sent.log"
        return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] \
            if log.exists() else []

    def armed_for(self, target: str):
        """F1's or F2's arming for the faulted call: True once a request
        calling `target` has been sent, so that call's own connect, and
        every later one, meets the fault."""
        return lambda: any(target in s["calls"] for s in self.sent())

    def begins(self) -> list:
        """The begin stamps of the last run's own register calls, a call its
        timer killed among them (T220f)."""
        log = self.bin / "psql-begin.log"
        begins = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] \
            if log.exists() else []
        return [b for b in begins if b["ppid"] == self.pid and b["argv"] == REGISTER_ARGV]

    def state(self) -> tuple:
        """(the switch's mode, marker and set_seq; the head; origin's tip),
        read as the superuser and from the bare origin."""
        switch = self.pg.psql(f"SELECT mode, marker_state, set_seq FROM {SCHEMA}.register_switch "
                              f"WHERE id = 1;").stdout.strip()
        head = self.pg.psql(f"SELECT seq FROM {SCHEMA}.register_head WHERE id = 1;").stdout.strip()
        return switch, head, self.origin_tip()


class ArmedFault(StartupRelay):
    """A fault armed once an earlier, healthy call has ended (TP:3586-3589):
    a relay to the cluster's socket that passes each connection whole while
    `armed()` answers False, asked at each accept; once it answers True, F1
    holds each new connection and never speaks, and F2 goes silent after
    the startup, as `StartupRelay` does."""

    def __init__(self, unix_path: str, fault: str, armed):
        self.fault = fault
        super().__init__(unix_path, armed=armed)

    def _accept(self):
        self.sock.settimeout(0.2)
        while not self.done:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                continue
            on = bool(self.armed())
            if on and self.fault == "F1":
                self.held.append(conn)
                self.silenced += 1
                continue
            upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            upstream.connect(self.unix_path)
            self.held += [conn, upstream]
            threading.Thread(target=self._pump, args=(conn, upstream, on and self.fault == "F2"),
                             daemon=True).start()


def _did(call: dict, what: str) -> bool:
    """Whether a logged call is `what`: `snapshot`, or a write function's name."""
    return bool(call.get("snapshot")) if what == "snapshot" else what in call.get("calls", ())


def _slow_trigger(pg, table: str, event: str, seconds: float) -> None:
    """F4 for an operator's write (TP:3618-3621): a trigger the test creates in
    its own database, after the import, never in the template, that sleeps
    past the call's `statement_timeout`: `BEFORE <event>` on `table`, for each
    row. On `register_switch` it fires only where the marker becomes
    `present`, so the cutover's own update passes and `record_marker`'s
    meets it; on `journal`, an `INSERT` trigger takes the write's entry and a
    `DELETE` one the abort's."""
    when = " WHEN (NEW.marker_state = 'present')" if table == "register_switch" else ""
    pg.psql(f"SET search_path TO {SCHEMA};\n"
            f"CREATE FUNCTION t278_slow() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"PERFORM pg_sleep({seconds}); "
            f"RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END; END $$;\n"
            f"GRANT EXECUTE ON FUNCTION t278_slow() TO PUBLIC;\n"
            f"CREATE TRIGGER t278_slow BEFORE {event} ON {table} FOR EACH ROW{when} "
            f"EXECUTE FUNCTION t278_slow();\n")


def _faulted_start(op: Operator, target: str | None) -> float:
    """The faulted call's start (TP:3577-3579, "from the faulted call's
    start"): the send stamp of the run's first request calling `target`
    where the row names one, else the begin stamp of its first call."""
    if target is None:
        begins = [b["begin"] for b in op.begins()]
        assert begins, "the command made no register call"
        return begins[0]
    sends = [s["sent"] for s in op.sent() if s["ppid"] == op.pid and target in s["calls"]]
    assert sends, f"the command sent no {target} call"
    return sends[0]


def _fetches_origin(argv: list) -> bool:
    """Whether a `git` call is a fetch from `origin`."""
    return "fetch" in argv and "origin" in argv


def _rollback_checks(op: Operator) -> list:
    """Each try's check, as the 75 cell times it (TP:3607 at B14; lane 3's
    batch 11 (7)(b), #165 6783909985): step 0's head read, T304's
    `_rollback_read`, in the shim's log (`TIMING_PSQL`'s), and T326's fetch
    of `origin main` right before step 1 (B14 tasks:1539), in the `git`
    wrapper's (`GIT_TIMING`'s); a try's parts are the calls that start after
    the try before's step 1 call ended and before its own step 1 call
    starts. Returns each try's (its check's start, its check's span in s),
    the span from its first part's start to its last part's end. The last
    try's check must hold both its head read and its fetch: the bound is
    measured on them."""
    calls, gits = op.calls(), op.git_calls()
    steps = [c for c in calls if "commit_write" in c.get("calls", ())]
    assert steps, f"the rollback made no step 1 call: {calls}"
    checks, after = [], float("-inf")
    for n, step in enumerate(steps, 1):
        reads = [c for c in calls if not c.get("calls") and after <= c["start"] < step["start"]]
        fetches = [g for g in gits if _fetches_origin(g["argv"])
                   and after <= g["start"] < step["start"]]
        parts = reads + fetches
        if n == len(steps):
            assert reads, f"the last try made no head read before its step 1: {calls}"
            assert fetches, ("the last try fetched no origin main before its step 1 (T326's "
                             f"step 0, B14 tasks:1539): {gits}")
        if parts:
            begin = min(p["start"] for p in parts)
            checks.append((begin, max(p["end"] for p in parts) - begin))
        after = step["end"]
    return checks


def _operator_row(pg, tmp_path: Path, request, row: str, fault: str) -> None:
    """`test_each_database_path_exits_inside_its_bound`'s T278 rows, at F1:
    each operator command whose faulted call meets a silent listener at its
    connect, armed at that call's own send where the row follows a healthy
    call (`target`; `after`, the earlier call), exits with its row's outcome
    inside twice its bound, timed from the faulted call's start. Where the
    fault is armed, the earlier call reached the cluster. They fail until
    lane 1's L1-A14 and lane 3's T304, T324, T326 and T327 land."""
    spec = ROWS[row]
    op = Operator(pg, tmp_path, request, spec["estate"])
    before = op.state()
    if row == "switch-to-files":
        op.fail_push()
    after, target = spec["after"], spec["target"]
    if target is None:
        listener = SilentListener()
    else:
        listener = ArmedFault(f"{pg.host}/.s.PGSQL.{pg.port}", fault, op.armed_for(target))
    try:
        proc, _ = op.run(op.argv(row), op.config("127.0.0.1", listener.port))
    finally:
        listener.close()
    case = f"{row}-{fault}"
    assert proc.returncode == spec["exit"], f"{case}: {proc.returncode}: {proc.stderr}"
    if after is not None:
        assert any(_did(c, after) and c["exit"] == 0 for c in op.calls()), \
            f"{case}: the {after} call before the fault never reached the cluster"
        assert listener.silenced, f"{case}: the {target} call never met F1"
    if row in ("rollback", "cutover", "stray-calls"):
        assert op.state() == before, f"{case}: something was written: {before} -> {op.state()}"
    elapsed = op.exited - _faulted_start(op, target)
    assert elapsed < 2 * spec["bound"], f"{case}: {elapsed:.2f} s against {spec['bound']} s"
    _record(case, elapsed, spec["bound"], "timing rule 2, from the faulted call's start")


def _operator_57014(pg, tmp_path: Path, request, row: str) -> None:
    """`test_a_slow_statement_meets_57014_before_the_client_timer`'s T278
    rows: F4's slow statement where the row's call works (`slow`), made
    after the estate is built; the call ends with 57014 no earlier than its
    `statement_timeout` after its start and under twice it, and the command
    exits with the row's F4 outcome (`f4_exit`). They fail until lane 1's
    L1-A14 and lane 3's T304, T324, T326 and T327 land."""
    spec = ROWS[row]
    op = Operator(pg, tmp_path, request, spec["estate"])
    statement_s = spec["statement_ms"] / 1000
    table, event = spec["slow"]
    if event == "policy":
        _slow_statement(pg, table, "lanes_register_writer", 4 * statement_s + 5)
    else:
        _slow_trigger(pg, table, event, 4 * statement_s + 5)
    if row == "switch-to-files":
        op.fail_push()
    proc, _ = op.run(op.argv(row), op.config())
    ended = [c for c in op.calls() if "57014" in c["first"]]
    assert ended, f"{row}: no call ended with 57014: {op.calls()}"
    took = ended[0]["end"] - ended[0]["start"]
    assert statement_s <= took < 2 * statement_s, f"{row}: 57014 after {took:.2f} s"
    assert proc.returncode == spec["f4_exit"], f"{row}: {proc.returncode}: {proc.stderr}"
    _record(f"{row}-F4", took, statement_s, "timing rules 2 and 3")


#: T257g: the image cache's head planted above the register's head, through
#: the flipped copy's own `image_cache_put` and `image_cache_record` (lane 1's
#: cache, design Y:4963), run in the operator's environment, so the cache is
#: the one `state_dir()` names for the command. A head above `k` is a miss
#: once the snapshot's request answers (`_register_snapshot_start`; lane 3's
#: ruling, #165 6746004829). Prints the cache's head as read back.
MISS_CACHE = r'''
import importlib.util, sys
from importlib.machinery import SourceFileLoader
copy, seq, path, text = sys.argv[1:5]
loader = SourceFileLoader("lanes_index_t257g", copy)
module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(module)
module.image_cache_record(int(seq), {path: module.image_cache_put(text.encode("utf-8"))})
head = module.image_cache_head()
print(head[0] if head else "none")
'''


def _snapshot_miss(pg, tmp_path: Path, request, fault: str) -> None:
    """`[snapshot-miss-F2]` (T257g; F13c's T257 bullet, R-F13c-18; lane 3's
    batch 7, #165 6780364102, text change 18 and its ruling on T111's
    SHOULD-2, option (b)): a writer's `register snapshot --write-id new
    ... --tree <dir> --checkout <c>` (contract section 3.2) on the imported
    register at `primary` misses the image cache, whose head is planted
    above the register's (`MISS_CACHE`). F2 is armed once the first request
    has ended, so that request reaches the cluster and the second, the whole
    fetch (Y:2515-2516), meets the relay, silent after the startup.
    `bounds` cuts that request's client timer to what is left of `S` from
    the first request's start (lane 1's cut, #165 6783051626), so the
    command sends both requests and ends 69 within `S`, 8 s, from the first
    request's start (timing rule 2). It fails until lane 1's cut in T106 and
    T111's use of it are on line R."""
    spec = ROWS["snapshot-miss"]
    case = f"snapshot-miss-{fault}"
    op = Operator(pg, tmp_path, request, "primary")
    head = int(op.state()[1])
    planted = subprocess.run([sys.executable, "-c", MISS_CACHE, str(op.copy), str(head + 5),
                              "lanes/LANES.md", "# LANES.md\n"], capture_output=True, text=True,
                             env=op.env, cwd=str(op.reg.wip), timeout=120,
                             stdin=subprocess.DEVNULL)
    assert planted.stdout.strip() == str(head + 5), \
        f"{case}: the cache's head was not planted at {head + 5}: {planted.stdout}{planted.stderr}"
    relay = StartupRelay(f"{pg.host}/.s.PGSQL.{pg.port}",
                         armed=lambda: any(c.get("snapshot") for c in op.calls()))
    argv = ["register", "snapshot", "--write-id", "new", "--lane", op.lane,
            "--verb", WRITE["verb"], "--args-sha256", WRITE["args_sha256"],
            "--tree", str(tmp_path / "snapshot-tree"), "--checkout", str(op.reg.wip)]
    try:
        proc, _ = op.run(argv, op.config("127.0.0.1", relay.port))
    finally:
        relay.close()
    assert proc.returncode == spec["exit"], f"{case}: {proc.returncode}: {proc.stderr}"
    first = [c for c in op.calls() if c.get("snapshot")]
    assert first and first[0]["exit"] == 0, \
        f"{case}: the first request never reached the cluster: {op.calls()}"
    requests = op.begins()
    assert len(requests) == 2, \
        f"{case}: the miss's second request was not sent: {len(requests)} requests: {proc.stderr}"
    assert relay.silenced, f"{case}: the second request never met F2"
    elapsed = op.exited - requests[0]["begin"]
    assert elapsed < 2 * spec["bound"], f"{case}: {elapsed:.2f} s against {spec['bound']} s"
    _record(case, elapsed, spec["bound"], "timing rule 2, from the first request's start")


#: T257j: the writer's SQL path is lane 4's (L4-B2, `lanes-edit.sh`'s SQL
#: writer), which line R's `lanes-edit.sh` lacks: until it lands, the writer
#: sends no snapshot request, and the cases say so rather than fail later.
NO_SQL_WRITER = "it fails until L4-B2, lanes-edit.sh's SQL writer"


def _sent_a_snapshot(op: Operator, case: str, proc) -> None:
    """The writer sent its snapshot request: its SQL path ran (T257j)."""
    assert any(s.get("snapshot") for s in op.sent()), \
        (f"{case}: the writer sent no snapshot request, so {NO_SQL_WRITER}: "
         f"{proc.returncode}: {proc.stderr}")


def _primary_writer_row(pg, tmp_path: Path, request, row: str, fault: str) -> None:
    """`test_each_database_path_exits_inside_its_bound`'s T257a writer rows
    whose fault comes after the snapshot's check 4 (T257j; line BD10's
    doubt 1): `writer-commit-f2` at F2, `writer-commit-f3` and `whole-write`
    at F3, each with its id, its fault and its expected exit, on the
    imported register at `primary` (`Operator`), since `pg` alone is a
    bootstrap-only clone whose switch reads `files` with the marker `absent`
    and whose head is -1, where check 4 would end each write 69 before its
    commit. The writer is `Operator.write`. F2 is armed at the commit's own
    send (T257i; TP:3586-3589); F3 is the head row held `FOR UPDATE`
    (`_hold_head`). They fail until L4-B2 and L4-B5."""
    spec = ROWS[row]
    case = f"{row}-{fault}"
    op = Operator(pg, tmp_path, request, "primary")
    listener, session = None, None
    try:
        if fault == "F2":
            # THE COMMIT'S F2 IS ARMED AT THE COMMIT'S OWN SEND (T257i; T257f
            # armed it after the snapshot's end, TP:3586-3589): the relay
            # passes each snapshot request whole, a missed snapshot's second
            # request among them, which lane 1's cut sends under what is left
            # of `S` (#165 6783051626) and which F2 would end 69, not 3.
            listener = StartupRelay(f"{pg.host}/.s.PGSQL.{pg.port}",
                                    armed=op.armed_for("commit_write"))
            config = op.config("127.0.0.1", listener.port)
        else:
            session = _hold_head(pg) if row in HEAD_HELD_F3 else _hold(pg, spec["table"])
            config = op.config()
        proc, elapsed = op.write(config)
    finally:
        if listener is not None:
            listener.close()
        if session is not None:
            _end(session)
    _sent_a_snapshot(op, case, proc)
    assert proc.returncode == spec["exit"], f"{case}: {proc.returncode}: {proc.stderr}"
    if row == "writer-commit-f2":
        # Every snapshot request sent before the commit's, a miss's second
        # among them, reached the cluster and ended 0, and the commit's
        # connection met the armed relay (TP:3589; T257i).
        sends = [s["sent"] for s in op.sent() if "commit_write" in s["calls"]]
        assert sends, f"{case}: the write sent no commit call: {op.sent()}"
        snapshots = [c for c in op.calls() if c.get("snapshot") and c["start"] < sends[0]]
        assert snapshots and all(c["exit"] == 0 for c in snapshots), \
            f"{case}: a snapshot request before the commit failed: {op.calls()}"
        assert listener.silenced, f"{case}: no call met F2 at the commit's send"
    if row == "whole-write":
        # ITS OWN CELL (T257f): no attempt, each begun by its snapshot call,
        # starts after the deadline, asserted at twice it (timing rule 2); the
        # time runs from the first attempt's start, and stays under `T_write`.
        # An attempt's start is its process's first snapshot request: a
        # missed snapshot's second request, in the same process, starts no
        # attempt (T257i; lane 1's cut, #165 6783051626).
        firsts: dict = {}
        for c in op.calls():
            if c.get("snapshot"):
                firsts.setdefault(c.get("ppid"), c["start"])
        starts = sorted(firsts.values())
        assert starts, f"{case}: the write made no attempt"
        late = [round(s - starts[0], 2) for s in starts
                if s - starts[0] >= 2 * WHOLE_WRITE["deadline_s"]]
        assert not late, f"{case}: attempts started after the deadline: {late}"
        elapsed = op.exited - starts[0]
        assert elapsed < WHOLE_WRITE["t_write_s"], \
            f"{case}: {elapsed:.2f} s, over T_write's {WHOLE_WRITE['t_write_s']} s"
        _record(f"{case}-T_write", elapsed, WHOLE_WRITE["t_write_s"],
                f"T_write, from the first attempt's start, {len(starts)} attempts")
    assert elapsed < 2 * spec["bound"], f"{case}: {elapsed:.2f} s against {spec['bound']} s"
    _record(case, elapsed, spec["bound"], "timing rule 2" + (
        ", from the first attempt's start" if row == "whole-write" else ""))


def _primary_writer_57014(pg, tmp_path: Path, request, row: str) -> None:
    """`test_a_slow_statement_meets_57014_before_the_client_timer`'s
    `[writer-commit-f2]` (T257h, T257j): on the imported register at
    `primary` (`Operator`), past the snapshot's check 4, the commit's entry
    meets a trigger on `journal` that sleeps (`slow`), made after the
    estate is built; the call ends with 57014 no earlier than its
    `statement_timeout` after its start and under twice it, and the writer
    exits 69 (`f4_exit`), a refusal the database made (TP:3621-3626 at
    B14). It fails until L4-B2 and L4-B5."""
    spec = ROWS[row]
    op = Operator(pg, tmp_path, request, "primary")
    statement_s = spec["statement_ms"] / 1000
    _slow_trigger(pg, *spec["slow"], 4 * statement_s + 5)
    proc, _ = op.write(op.config())
    _sent_a_snapshot(op, row, proc)
    ended = [c for c in op.calls() if "57014" in c["first"]]
    assert ended, f"{row}: no call ended with 57014: {op.calls()}"
    took = ended[0]["end"] - ended[0]["start"]
    assert statement_s <= took < 2 * statement_s, f"{row}: 57014 after {took:.2f} s"
    assert proc.returncode == spec["f4_exit"], f"{row}: {proc.returncode}: {proc.stderr}"
    _record(f"{row}-F4", took, statement_s, "timing rules 2 and 3")


def test_a_rollback_whose_first_call_expires_rereads_the_switch(pg, tmp_path, request):
    """AT-D9's `rollback` row (TP:3604): "Where step 1's call expires, the
    rollback reads the switch again and never goes on to step 2 on an
    unknown switch." On the `cutover-done` estate (T278d), F2 is armed at
    step 1's own send, its `commit_write` (TP:3586-3589, "once the shim's
    log shows the earlier call's end"), so every call of the check before
    it reaches the cluster, and step 1's call expires at its 15 s timer, and
    so does the switch's re-read: 69, inside twice 15 + 15 = 30 s from step
    1's start; exactly two calls after the check's last, step 1's and then
    the re-read, a read that calls no write function, and none after them;
    the switch, the head and origin unchanged.

    THE ARMING (T278d; line BD15): T278 armed F2 once the rollback's first
    call had ended, its head read (lane 3's batch 11 (7)(b), #165
    6783909985). Since T326 the check is that read, then step 0's fetch of
    `origin main` and the head read after it (`rollback_step_0_git_half`),
    so that arming put F2 on step 0's read, and the rollback ended 69 with
    one call after the first, never reaching step 1. It fails until lane 3's
    T304, T326 and T327 land (the estate's cutover is T327's)."""
    op = Operator(pg, tmp_path, request, "cutover-done")
    before = op.state()
    relay = ArmedFault(f"{pg.host}/.s.PGSQL.{pg.port}", "F2", op.armed_for("commit_write"))
    try:
        proc, _ = op.run(["rollback"], op.config("127.0.0.1", relay.port))
    finally:
        relay.close()
    assert proc.returncode == 69, f"rollback: {proc.returncode}: {proc.stderr}"
    calls = op.calls()
    assert calls and all(c["exit"] == 0 for c in calls), \
        f"a call of the check before step 1 did not answer: {calls}"
    healthy = max(c["end"] for c in calls)
    later = [b["begin"] for b in op.begins() if b["begin"] >= healthy]
    assert len(later) == 2, \
        f"step 1's call and the switch's re-read, and nothing after: {len(later)} calls"
    sends = [s for s in op.sent() if s["ppid"] == op.pid and s["sent"] >= healthy]
    assert [s["calls"] for s in sends] == [["commit_write"], []], \
        f"step 1's commit_write, then a read of the switch: {sends}"
    assert op.state() == before, f"the rollback wrote: {before} -> {op.state()}"
    elapsed = op.exited - later[0]
    assert elapsed < 2 * 30, f"rollback: {elapsed:.2f} s against 15 + 15 s"
    _record("rollback-first-call", elapsed, 30, "timing rule 2, step 1's and the re-read's")


def test_a_rollback_that_keeps_losing_its_turn_exits_75_at_the_deadline_with_nothing_written(
        pg, tmp_path, request):
    """AT-D9's `rollback` row under F3 (TP:3604): step 1's call ends in a lost
    turn, 55P03 at its 5000 ms `lock_timeout`, against the head row held
    `FOR UPDATE` by the test's own session (`_hold_head`); the rollback reads
    the head afresh and tries again, and at `LANES_REGISTER_DEADLINE_S=6`
    exits 75, with nothing written and the switch still `primary`. From the
    rollback's start (TP:3607 at B14): no check starts after the deadline,
    asserted at twice it (timing rule 2), and the run ends inside twice the
    deadline, plus one check, plus the last call's 5 s. The check is each
    try's head read and its fetch of `origin main`, timed from the shim's
    log and the `git` wrapper's (`GIT_TIMING`), and the bound takes the last
    try's as measured, not a fixed 15 s (lane 3's batch 11 (7)(b),
    `_rollback_checks`). It runs on the `cutover-done` estate (T278d): on
    `_to_primary`'s, T326's step 0 found no `Register-Seq` on origin and
    refused 2 before step 1. It fails until lane 3's T304, T326 and T327
    land (the estate's cutover is T327's)."""
    op = Operator(pg, tmp_path, request, "cutover-done")
    before = op.state()
    op.time_git()
    session = _hold_head(pg)
    try:
        proc, elapsed = op.run(["rollback"], op.config(),
                               {"LANES_REGISTER_DEADLINE_S": str(ROLLBACK_DEADLINE_S)})
    finally:
        _end(session)
    assert proc.returncode == 75, f"rollback-F3: {proc.returncode}: {proc.stderr}"
    assert any("55P03" in c["first"] for c in op.calls()), \
        f"no call ended with 55P03: {op.calls()}"
    assert op.state() == before, f"the rollback wrote: {before} -> {op.state()}"
    start = op.exited - elapsed
    checks = _rollback_checks(op)
    late = [round(begin - start, 2) for begin, _ in checks
            if begin - start >= 2 * ROLLBACK_DEADLINE_S]
    assert not late, f"rollback-F3: checks started after the deadline: {late}"
    check = checks[-1][1]
    bound = ROLLBACK_DEADLINE_S + check + ROLLBACK_LOCK_S
    assert elapsed < 2 * bound, \
        f"rollback-F3: {elapsed:.2f} s against {bound:.2f} s, the last check {check:.2f} s"
    _record("rollback-F3-75", elapsed, bound, f"timing rule 2, from the rollback's start; "
            f"the last try's check measured at {check:.2f} s, {len(checks)} tries")


@pytest.mark.parametrize("fault", ["F1", "F2", "F3", "F4"])
def test_a_cutover_whose_call_expires_leaves_the_switch_unknown_and_its_rerun_reads_it_first(
        pg, tmp_path, request, fault):
    """AT-D9's `cutover` row (TP:3606; TP:3629-3631): on the imported
    register and its origin, the fault takes the transaction's call, so no
    marker is pushed: F1 and F2 armed at the transaction's own send, after
    the cutover's read has ended (TP:3586-3589), F3 the head row held `FOR
    UPDATE`, which `commit_write` takes, and F4 a trigger on `journal` that
    sleeps (`_slow_trigger`). It
    exits 69, the switch still `files` with the marker `absent`, the head
    and origin unchanged; the transaction's call inside twice 15 s, or under
    F3 twice its 5000 ms `lock_timeout`, from its start. A rerun after the
    fault is removed reads the switch and the journal first, its first call
    no commit, and goes on: 0, one `cutover` entry, the switch `primary` with
    the marker `adding` or, with T327's push and read-back, `present`. It
    fails until lane 1's L1-A14 and lane 3's T327 land."""
    op = Operator(pg, tmp_path, request, "imported")
    before = op.state()
    listener, session = None, None
    try:
        if fault in ("F1", "F2"):
            listener = ArmedFault(f"{pg.host}/.s.PGSQL.{pg.port}", fault,
                                  op.armed_for("commit_write"))
            config = op.config("127.0.0.1", listener.port)
        else:
            if fault == "F3":
                session = _hold_head(pg)
            else:
                _slow_trigger(pg, "journal", "INSERT", 45)
            config = op.config()
        proc, _ = op.run(op.argv("cutover"), config)
    finally:
        if listener is not None:
            listener.close()
        if session is not None:
            _end(session)
    assert proc.returncode == 69, f"cutover-{fault}: {proc.returncode}: {proc.stderr}"
    assert op.state() == before, f"cutover-{fault} wrote or pushed: {before} -> {op.state()}"
    calls = op.calls()
    assert calls and calls[0]["exit"] == 0, f"the cutover's read never answered: {calls}"
    bound = 5 if fault == "F3" else 15
    elapsed = op.exited - _faulted_start(op, "commit_write")
    assert elapsed < 2 * bound, f"cutover-{fault}: {elapsed:.2f} s against {bound} s"
    _record(f"cutover-{fault}", elapsed, bound, "timing rule 2, from the transaction's start")
    if fault == "F4":
        pg.psql(f"DROP TRIGGER t278_slow ON {SCHEMA}.journal;")
    mark = len(op.calls())
    proc, _ = op.run(op.argv("cutover"), op.config())
    assert proc.returncode == 0, f"the rerun: {proc.returncode}: {proc.stderr}"
    rerun = op.calls()[mark:]
    assert rerun and "commit_write" not in rerun[0]["calls"], \
        f"the rerun's first call is not a read of the switch: {rerun}"
    entries = pg.psql(f"SELECT count(*) FROM {SCHEMA}.journal WHERE kind = 'cutover';").stdout
    assert entries.strip() == "1", f"one cutover entry: {entries.strip()}"
    mode, marker, _ = op.state()[0].split("|")
    assert mode == "primary" and marker in ("adding", "present"), op.state()


@pytest.mark.parametrize("landed", ["not-landed", "landed"])
def test_the_aborts_call_that_expires_is_run_again_or_found_done_by_its_rerun(
        pg, tmp_path, request, landed):
    """AT-D9's `switch_to_files` row (TP:3606; TP:3632-3635): a cutover whose
    push the `git` wrapper fails (`GIT_NO_PUSH`) runs its abort, whose call
    meets T203's shim, first on `PATH`: `[not-landed]`, its `before` mode, so
    the call is lost before its `COMMIT`; `[landed]`, its `timer` mode at
    20 s, so the call commits and its answer comes after the 15 s timer.
    Either way the cutover exits 69, inside twice 15 s from the abort's call.
    Once the fault is removed, the rerun, `cutover` again with the push
    still failing (lane 3's batch 11 (7)(c), #165 6783909985), reads the
    switch. After `before` the abort did not land, so the rerun runs it
    again, one `switch_to_files` call, and ends with the abort's 2, the
    switch `files` with the marker `absent`. After `timer` it landed, and
    the switch at `files` with the marker `absent` is also "before any
    cutover" (Y:1531), so the rerun runs no abort for that entry and goes on
    as a first cutover would: its first write call is `commit_write`, never
    `switch_to_files`; with the push still failing it then aborts its own
    entry once and ends 2, the switch `files` with the marker `absent` and
    the head back at the import's seq. "Sends nothing" (TP:3641-3642 at B14)
    cannot hold, and B15 drops it. It fails until lane 1's L1-A14 and lane
    3's T327 land."""
    op = Operator(pg, tmp_path, request, "imported")
    imported = op.state()[1]
    op.fail_push()
    arm = {"mode": "before"} if landed == "not-landed" else {"mode": "timer", "ms": 20000}
    where = _shim(op, [dict(arm, match="switch_to_files")])
    proc, _ = op.run(op.argv("switch-to-files"), op.config())
    assert proc.returncode == 69, f"abort-{landed}: {proc.returncode}: {proc.stderr}"
    sent = [e for e in _shim_calls(where) if "switch_to_files(" in e["stdin"]]
    assert len(sent) == 1, f"abort-{landed}: one abort call: {len(sent)}"
    mode = op.state()[0].split("|")[:2]
    assert mode == (["primary", "adding"] if landed == "not-landed" else ["files", "absent"]), \
        f"abort-{landed}: the switch reads {mode}"
    _arm(where, op, [])
    mark = len(_shim_calls(where))
    proc, _ = op.run(op.argv("switch-to-files"), op.config())
    rerun = _shim_calls(where)[mark:]
    aborts = [e for e in rerun if "switch_to_files(" in e["stdin"]]
    if landed == "not-landed":
        assert len(aborts) == 1, f"the rerun runs the abort again, once: {len(aborts)}"
        assert proc.returncode == 2, f"the rerun's abort: {proc.returncode}: {proc.stderr}"
    else:
        writes = [[w[:-1] for w in WRITE_CALLS if w in e["stdin"]] for e in rerun]
        writes = [w for w in writes if w]
        assert writes and writes[0] == ["commit_write"], \
            f"the rerun's first write call is commit_write, never switch_to_files: {writes}"
        assert len(aborts) == 1, f"the rerun aborts its own entry once: {len(aborts)}"
        assert proc.returncode == 2, f"the rerun's own abort: {proc.returncode}: {proc.stderr}"
        assert op.state()[1] == imported, \
            f"the head is back at the import's seq {imported}: {op.state()}"
    assert op.state()[0].split("|")[:2] == ["files", "absent"], op.state()


def test_a_record_marker_that_expires_leaves_the_marker_adding_and_writes_refusing(
        pg, tmp_path, request):
    """AT-D9's `record_marker` row (TP:3607; TP:3636-3638): reached after the
    cutover's push and read-back. The fault takes its call: T203's shim,
    first on `PATH`, holds the `record_marker` call on a FIFO no one opens,
    so it is never sent and the cutover's 15 s timer ends it: 69. The push
    stands, the marker reads `adding`, and a writer's commit, `lanes-edit.sh
    set-row-state` on the operator's lane with `mode=primary` (lane 3's batch
    11 (7)(d), #165 6783909985), refuses with 69, its stderr naming the
    marker's refusal (TP:4180-4181; Y:3580): LR002, or its snapshot's words
    on the switch it read, the marker `adding` (TP:4221-4222; T278f).
    T409's placeholder exits 69 on primary too (B14 tasks:937), so the exit
    alone proves nothing. The
    rerun, the fault removed, records the marker once: one `record_marker`
    call, 0, the marker `present`. The writer runs from the operator lane's
    own checkout, made first (`Operator.lane_checkout`, T278f; lane 4's
    triage, #165 6833813092, b1): without it T415's write refuses before
    any call (R17). It fails until lane 1's L1-A14, lane 3's T327 and lane
    4's L4-B2 land, and its writer until lane 4's T415."""
    op = Operator(pg, tmp_path, request, "imported")
    fifo = tmp_path / "hold-record-marker"
    os.mkfifo(fifo)
    where = _shim(op, [{"mode": "hold", "match": "record_marker", "fifo": str(fifo)}])
    proc, elapsed = op.run(op.argv("record-marker"), op.config())
    assert proc.returncode == 69, f"record-marker: {proc.returncode}: {proc.stderr}"
    assert any("record_marker(" in e["stdin"] for e in _shim_calls(where)), \
        "the cutover made no record_marker call"
    assert op.origin_tip() != op.reg.c, "the cutover's push stands on origin"
    assert op.state()[0].split("|")[:2] == ["primary", "adding"], op.state()
    _arm(where, op, [])
    config = op.config()
    config.write_text(config.read_text().replace("mode=index", "mode=primary"))
    op.lane_checkout()
    writer = subprocess.run(["bash", str(op.copy.parent / "lanes-edit.sh"), "set-row-state",
                             op.lane, f"PAUSED {DOT} T278's write behind the marker"],
                            capture_output=True, text=True, timeout=300, cwd=str(op.reg.wip),
                            stdin=subprocess.DEVNULL,
                            env=dict(op.env, LANES_INDEX_CONFIG=str(config)))
    assert writer.returncode == 69, f"the writer's commit: {writer.returncode}: {writer.stderr}"
    # THE MARKER'S REFUSAL (T278f; line BD17): the write "exits 69 on the switch
    # its snapshot reads, or on LR002" (TP:4221-4222). T415's writer meets
    # the marker at its first snapshot, whose own words name the switch it read,
    # the marker `adding`, before any commit call; a commit call would get LR002.
    # Either is the marker's, never T409's placeholder, which names no marker.
    assert "LR002" in writer.stderr or "marker adding" in writer.stderr, \
        (f"the writer's 69 is the marker's refusal, at its snapshot or LR002, not T409's "
         f"placeholder: {writer.stderr}")
    mark = len(_shim_calls(where))
    proc, _ = op.run(op.argv("record-marker"), op.config())
    recorded = [e for e in _shim_calls(where)[mark:] if "record_marker(" in e["stdin"]]
    assert proc.returncode == 0 and len(recorded) == 1, \
        f"the rerun records the marker once: {proc.returncode}, {len(recorded)}: {proc.stderr}"
    assert op.state()[0].split("|")[:2] == ["primary", "present"], op.state()


@pytest.mark.parametrize("form", ["import-single", "render-revert"])
def test_a_stray_ways_out_commit_call_is_in_doubt_like_a_writers(pg, tmp_path, request, form):
    """AT-D9's rows for `import --single <sha>` and `render --revert <sha>`
    (TP:3607; TP:3639): on test 6's stray commit, F2 is armed at the commit
    call's own send, after the command's snapshot has ended (TP:3586-3589),
    so a missed snapshot's second request still reaches the cluster (lane
    1's cut, `refs/l1/R-rulings` 8121903), and the commit call meets the
    silent relay: in doubt, as a writer's commit, then the lookup, whose
    tries meet it too, and 3. The snapshot reached the cluster, a call met
    the relay, and nothing was written; from the commit call's start, inside
    twice the commit's F2 row's 35.5 s (`C` + `S` + `R` + `T_L` + `p`), and
    no call begins after D7's 30 s deadline, at twice it. The stray sits on
    the `cutover-done` estate, after the marker commit (T278e). It fails
    until lane 1's L1-A14 and lane 3's T324 and T327 land, and until T326's
    `_render_read_head` and T324's `_stray_recognised` agree on its values
    (line BD15: on T326-m23 `552c22d4` both forms end 1, a traceback)."""
    op = Operator(pg, tmp_path, request, "stray")
    before = op.state()
    relay = ArmedFault(f"{pg.host}/.s.PGSQL.{pg.port}", "F2", op.armed_for("commit_write"))
    try:
        proc, _ = op.run(op.argv("stray-commit", form), op.config("127.0.0.1", relay.port))
    finally:
        relay.close()
    assert proc.returncode == 3, f"{form}: {proc.returncode}: {proc.stderr}"
    assert any(c.get("snapshot") and c["exit"] == 0 for c in op.calls()), \
        f"{form}: the snapshot never reached the cluster: {op.calls()}"
    assert relay.silenced, f"{form}: no call met F2 after the snapshot"
    assert op.state()[:2] == before[:2], f"{form} wrote: {before} -> {op.state()}"
    start = _faulted_start(op, "commit_write")
    late = [round(b["begin"] - start, 2) for b in op.begins() if b["begin"] - start >= 2 * 30]
    assert not late, f"{form}: calls began after the deadline: {late}"
    elapsed = op.exited - start
    assert elapsed < 2 * 35.5, f"{form}: {elapsed:.2f} s against 35.5 s"
    _record(f"stray-{form}", elapsed, 35.5, "timing rule 2, from the commit call's start")
