# SPDX-License-Identifier: Apache-2.0
"""AT-LR007 and AT-LR011: the order of `commit_write`'s first checks, and
`find_write` (#165; FR-008, FR-016).

PHASE N, ON A REAL POSTGRESQL 16, by direct calls to lane 1's SQL (design.md
§1.3, §1.3.1). `commit_write` takes the head row's lock, then checks the
generation (LR007 `generation`), then the write id (LR006, or LR007
`another-write` for another write's entry), and only then the head (LR001),
the version (LR003) and the switch (LR002), so a write id of another
generation never ends in 69 or 0 (V2's S-3). `find_write`, F3's one lookup,
waits on the server's clock, holding no lock, until it has passed
`p_not_after`, at most 3 s (LR011 past that); then it takes the head row's
lock under the caller's `lock_timeout`, checks the clock again, then the
generation, then the entry, and returns the write's seq, or NULL.

THE FIXTURE, AT-LR006'S, ON A CLONE OF ITS OWN: each test clones `tmpl`
(T205 makes it, T227 builds it by the bootstrap), as T221's `[new-write]`
does, runs §1.4's two database-level statements on the clone, and drops it
`WITH (FORCE)` at the end. Nothing needs `tmpl_imported` (lane 3, #165
6768050756 point 1, which lane 2 accepts; R-F11-23), so T114 need not wait for
T115. A clone of `tmpl` is at `files` with the marker `absent` and an empty
journal, and each test brings it where it needs by AT-LR006's route
(TP:4610–4615), by the documented functions as `lanes_w_fx` and nothing else:
`Clone.imported` commits an `import` entry (one file, `lanes/LANES.md`, of one
line), which is what a clone of `tmpl_imported` held, and `Clone.to_primary`
goes on with a `cutover` entry over that import, then `record_marker`:

  * database R, between a re-import's bootstrap and its cutover: the clone
    after `Clone.imported`, at `files` with the marker `absent`, whose
    generation is `g1`; `g0`, the lost database's, is a uuid of the test's
    own;
  * database S, a restore: the clone brought to `primary` with the marker
    `present` by `Clone.to_primary` (the import, a `cutover` entry over it,
    then `record_marker`: TP:4610–4615), standing in for a restored
    backup. W0 and W1 commit under its generation `g0`; then its restore-form
    cutover, an after-loss `cutover` entry whose label is not the switch's,
    sets a new generation `g1`, and `record_marker` confirms it; then W2
    commits under `g1`;
  * AT-LR011's: S's route to `primary`, with write W committed (lane L1,
    verb V, `args_sha256` a).

Every call logs in as the fixture's writer login, `lanes_w_fx` (T228), in
the commit call's own form, `psql -X -q -A -t -v ON_ERROR_STOP=1 -v
VERBOSITY=verbose -v SHOW_CONTEXT=never` with the script on stdin, so a
refusal's first stderr line is `ERROR:  <SQLSTATE>: <message>` and its second
the `DETAIL:` token. A lookup runs at READ COMMITTED in a transaction the test
rolls back, with D9's bounds set in it (`lock_timeout=2000ms`,
`statement_timeout=6000ms`). A holder of the head row is a superuser session
fed on stdin, and every barrier is a state polled in `pg_stat_activity`, by
the session's `application_name`. No elapsed time is asserted: the one time
read, `clock_timestamp()` not before `p_not_after`, is a bound on the
server's own clock.

Each refused call writes nothing: the head, the journal and the switch equal
their values before.

Every case FAILS UNTIL lane 1's T107 (L1-A6: `commit_write` and
`find_write`) and T114 (L1-A12) land, with lane 2's T227 (`tmpl` holding the
register) and T228 (`lanes_w_fx`). A clone of `tmpl` with no register is
refused by the fixture's own assertion. Without PostgreSQL 16 each skips.

THE MODULE ALSO HOLDS, each at its own section below: T244's test 12 (AT-12)
and section 4.3's rival, and T245's D8 and AT-F34 (phase W, the client's
writers on a real register, through the shim), with T245's texts for 3, which
read the scripts and run with no engine; and T246's AT-F3, a write in doubt at
the deadline (phase W, with its direct calls in phase N); T247's AT-F10, a
pending record against an unrelated identical command (phase W); and T251's
AT-LR006 and AT-F33, two attempts of one write meeting at the commit (phase
N, on these clones).

PHASE W'S WORKSTATION IS T243's: `Estate`, its `estates` fixture, and the
logging tools of T248 are imported from `test_sql_register_order`, as
`test_handoff_skill_80_85` imports its sibling's `Sandbox`, so one
workstation serves both modules and neither keeps a copy.
"""

from __future__ import annotations

import datetime
import hashlib
import itertools
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pytest

from pgcluster import SUPERUSER, TEMPLATE, Database
from sql_register_helpers import _proc_start
from test_sql_register_order import (ARROW, BURST, CLIENT, DOT, EM, LA, LB, LC, OBJ, UUID_RE, Barrier,  # noqa: F401
                                     Estate, Writer, claim, estates, hold_point, kind_line, loggers, run_git,
                                     session_of, tool_calls)

#: THE LANDING GATE'S TABLE (T280; its reader, `tests/sql_register_gate.py`,
#: says how a table is read), TEMPORARY: T281 removes it in the last set.
#: Where the gate is active, each id is skipped until every task its row
#: names has landed, and the skip names them; an id's own row, `name[param]`,
#: replaces its function's. Each row holds the fails-until clauses of the task
#: that owns the test (T222, T244, T245, T246, T247 or T251), each L-label read
#: as the task that covers it, as lane 2's gate tables plan (GP-24, version 2)
#: gives them, with lane 3's rulings on T245's texts for 3 and T247's
#: record-less text. T247's rows also name T415, whose `pw_run` is the write
#: path on primary that each of its tests takes, and T417 where an id
#: asserts its 3, ahead of T247's Order (lane 4's GT-L4, #165 6879601079).
#: No row is `"*"`, since the six tasks' waits share no task. Each
#: `tasks:<n>` is tasks.md's line at `204145ae`, the reader's `SPEC_COMMIT`.
SQL_REGISTER_GATE_TABLE = {
    "test_a_call_in_doubt_that_committed_runs_its_tail_once_from_the_kept_child": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_callers_rerun_after_a_failed_reconnect_reuses_the_write_id": ("T107", "T108", "T114", "T412", "T417"),  # T244; tasks:2350
    "test_a_claim_from_another_host_or_container_counts_as_live_for_120_s": ("T412", "T415", "T417"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_a_claim_with_no_record_beside_it_is_waited_for": ("T412", "T415"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_a_commit_lost_before_it_landed_is_retried_cleanly_and_ends_with_one_entry": ("T107", "T108", "T114", "T412", "T417"),  # T244; tasks:2350
    "test_a_commit_past_its_not_after_raises_lr008_and_one_within_it_commits": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_a_commit_that_landed_before_the_connection_was_lost_ends_with_one_entry_and_exit_0": ("T107", "T108", "T114", "T412", "T417"),  # T244; tasks:2350
    "test_a_committed_write_leaves_no_pending_record": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_generation_change_after_the_snapshot_read_gives_lr007_generation": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_a_lanes_write_id_run_waits_for_a_live_owner": ("T412", "T415", "T417"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_a_live_pending_record_is_waited_for_not_shared": ("T412", "T415", "T417"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_a_lookup_held_at_the_head_row_ends_55p03_inside_its_statement_timeout": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_a_lookup_made_too_early_exits_3_and_keeps_the_record": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_a_lookup_never_mistakes_a_rivals_row_for_the_lost_write": ("T107", "T108", "T114", "T412", "T417"),  # T244; tasks:2350
    "test_a_lookup_refused_for_another_generation_exits_2_and_keeps_the_record": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_a_lookup_refused_for_another_write_exits_2_and_removes_the_record": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_a_lookup_try_without_an_answer_is_made_again_inside_the_window": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_a_pending_record_is_owned_through_numbered_claim_files_and_two_reruns_never_both_take_it": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_plain_rerun_reuses_the_pending_write_id_once_and_says_so": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_record_of_another_generation_is_refused_2_until_lanes_write_id_new": ("T412", "T415", "T417"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_a_replay_of_rename_lane_or_request_handoff_that_stops_or_differs_runs_none_of_the_tail": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_replay_of_request_handoff_types_into_no_pane": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_replay_that_stops_or_differs_runs_no_tail_and_warns": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_request_handoff_that_runs_none_of_its_tail_exits_2_and_writes_nothing": ("T107", "T108", "T114", "T412", "T417"),  # T244; tasks:2350
    "test_a_rerun_after_a_3_replays_the_verbs_tail_once": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_rerun_that_finds_its_write_committed_runs_the_verbs_after_commit_tail": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_rerun_that_finds_tail_sent_runs_no_tail_and_writes_the_done_mark": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_rerun_with_other_arguments_does_not_take_the_pending_id": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_retry_with_the_old_connection_still_open_writes_no_second_row": ("T107", "T108", "T114", "T412", "T417"),  # T244; tasks:2350
    "test_a_reused_pid_in_a_pending_record_reads_as_dead": ("T412", "T415", "T417"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_a_run_killed_after_its_call_line_or_mid_call_is_taken_over_in_doubt_and_waits_past_not_after": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_run_with_no_record_runs_no_tail_and_names_it": ("T412", "T415", "T417", "T418"),  # T245; tasks:2363
    "test_a_same_generation_id_after_a_restore_form_cutover_gets_lr006": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_a_sent_record_whose_child_never_read_committed_replays_and_an_owed_mark_runs_no_tail": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_tail_record_a_takeover_cannot_use_is_refused_2_and_kept": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_write_id_already_journaled_for_the_same_arguments_exits_0_at_the_snapshot": ("T412", "T415"),  # T247; tasks:2377
    "test_a_write_id_of_other_arguments_verb_or_generation_is_refused_2_at_the_snapshot": ("T412", "T415"),  # T247; tasks:2377
    "test_a_write_in_doubt_at_the_deadline_makes_one_lookup": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_a_write_killed_by_an_outer_timer_is_retried_under_its_own_id": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_write_of_another_generation_at_files_gets_lr007_not_lr002_or_lr001": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_a_write_whose_every_call_ended_lr008_exits_75_with_no_lookup": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_an_attempt_committed_after_the_commits_snapshot_gives_40001_without_a_wait": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_an_attempt_committed_after_the_snapshot_read_gives_lr006": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_an_attempt_committed_while_the_commit_waits_gives_40001_then_exit_0": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_an_attempt_holding_past_lock_timeout_gives_55p03_then_exit_0": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_an_attempt_that_never_commits_leaves_the_write_to_the_retry": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_an_expired_pending_record_is_not_reused": ("T412", "T415"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_an_id_in_the_journal_for_another_lane_gets_lr007": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_an_in_doubt_claim_never_leaves_two_claimed_lines_or_a_false_69": ("T107", "T108", "T114", "T412", "T417"),  # T244; tasks:2350
    "test_an_in_doubt_write_whose_next_attempt_is_refused_makes_its_lookup_before_it_exits": ("T107", "T108", "T114", "T412", "T417"),  # T244; tasks:2350
    "test_an_old_generation_id_after_a_restore_form_cutover_gets_lr007_not_lr006": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_an_orphan_that_takes_the_lock_past_its_not_after_gets_lr008_and_the_lookup_finds_it_absent": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_an_orphaned_commit_call_released_after_its_not_after_writes_nothing": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_an_outer_timer_expiry_is_in_doubt_like_exit_2": ("T107", "T108", "T114", "T412", "T417"),  # T244; tasks:2350
    "test_another_writes_entry_committed_after_the_snapshot_read_gives_lr007_another_write": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_find_write_gives_lr011_before_lr007": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_find_write_refuses_another_generation_lr007": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_find_write_refuses_another_writes_entry_lr007": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_find_write_refuses_lr011_at_once": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_find_write_returns_this_writes_seq_or_null": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_find_write_waits_on_the_server_clock_holding_no_lock": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_lanes_write_id_of_another_write_is_refused_2_and_the_pending_record_kept": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_lanes_write_id_of_the_records_own_write_takes_it_over_past_its_age": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_liveness_is_the_highest_claims_never_the_records_pid": ("T412", "T415", "T417"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_lr006_comes_before_lr001": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_lr008_alone_never_gives_3_or_69": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_lr008_at_the_deadline_leaves_the_exit_to_find_write": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_lr008_inside_the_deadline_is_a_lost_turn_and_the_write_exits_0": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_no_interleaving_of_two_attempts_of_one_write_reaches_23505": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_status_lists_and_resolves_pending_records": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_the_after_commit_tail_of_log_runs_once_when_a_rerun_finds_the_write": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_the_after_commit_tail_of_release_runs_once_when_a_rerun_finds_the_write": ("T412", "T415", "T417", "T418"),  # T245; tasks:2363
    "test_the_after_commit_tail_of_request_handoff_types_once_in_the_kept_child_and_polls": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_the_after_commit_tail_of_retire_rows_runs_once_when_a_rerun_finds_the_write": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_the_after_commit_tail_of_start_record_runs_once_when_a_rerun_finds_the_write": ("T412", "T417", "T418", "T427"),  # T245; tasks:2363
    "test_the_deadlines_lookup_waits_past_the_largest_not_after": ("T107", "T108", "T114", "T417"),  # T246; tasks:2371
    "test_the_no_lookup_control_gives_lr001_where_the_lookup_gives_lr006": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_the_no_lookup_control_reaches_23505_so_the_oracle_can_fail": ("T107", "T108", "T413", "T414", "T415", "T417"),  # T251; tasks:2390
    "test_the_pending_digest_covers_the_session_and_equals_args_sha256": ("T412", "T415"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_the_pending_records_call_lines_are_written_before_the_send_and_dropped_only_for_a_call_that_did_not_commit": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_the_switchs_own_generation_at_files_still_gets_lr002": ("T107", "T108", "T114", "T227", "T228"),  # T222; tasks:2135
    "test_the_texts_for_3_say_may_not_be_written_and_relay_the_writers_rerun": ("T412", "T417", "T418", "T433", "T434"),  # T245; tasks:2363
    "test_two_matching_calls_of_one_change_set_leave_the_replays_tail_owed": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_with_the_kept_child_gone_a_replay_runs_the_tail_once": ("T412", "T417", "T418"),  # T245; tasks:2363
    "test_a_claim_with_no_record_beside_it_is_waited_for[live-at-deadline]": ("T412", "T415", "T417"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_a_claim_with_no_record_beside_it_is_waited_for[write-id-live-at-deadline]": ("T412", "T415", "T417"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_a_live_pending_record_is_waited_for_not_shared[ends-in-time]": ("T412", "T415"),  # T247; tasks:2377; lane 4, #165 6879601079
    "test_a_replay_of_rename_lane_or_request_handoff_that_stops_or_differs_runs_none_of_the_tail[rename-lane-stops]": ("T412", "T417", "T418", "T422"),  # T245; tasks:2363
    "test_the_pending_records_call_lines_are_written_before_the_send_and_dropped_only_for_a_call_that_did_not_commit[refusal]": ("T412", "T415", "T417", "T418"),  # T245; tasks:2363
}

REGISTER = "lanes_register"
WRITER_LOGIN = "lanes_w_fx"
CONNECT_TO = "lanes_register_writer, lanes_register_reader, lanes_indexer"
LANES_MD, STORE = "lanes/LANES.md", "lanes/STORE"
WS, AUTHOR = "ws-t222", "T222 Fixture <t222@example.invalid>"
OPERATOR = "operator-t222"
MARKER_COMMIT = "c0ffee" + "1" * 34
IMPORT_COMMIT, IMPORT_TREE = "c" * 40, "d" * 40
IMPORT_LINES = ["# Lanes"]
RESTORED_LABEL = "restored-t222"
L1, L2, VERB, OTHER_VERB = "L1-t222", "L2-t222", "append-line", "lane-end"

COMMIT_SQL = ("BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
              "{set}"
              f"SELECT {REGISTER}.commit_write(:base, :'wid'::uuid, :client, :'gen'::uuid, :'entry'::jsonb);\n"
              "COMMIT;\n")
MARKER_SQL = f"SELECT {REGISTER}.record_marker(:client, :seq, :'commit', :'ws');\n"

#: F3's lookup: READ COMMITTED, D9's bounds, the call, the clock read next in
#: the same transaction, and the rollback.
LOOKUP_SQL = ("BEGIN ISOLATION LEVEL READ COMMITTED;\n"
              "SET LOCAL lock_timeout = '2000ms';\n"
              "SET LOCAL statement_timeout = '6000ms';\n"
              f"SELECT coalesce({REGISTER}.find_write(:'wid'::uuid, :'not_after'::timestamptz, :'gen'::uuid, "
              ":'lane', :'verb', nullif(:'args', ''))::text, 'NULL');\n"
              "SELECT clock_timestamp() >= :'not_after'::timestamptz;\n"
              "ROLLBACK;\n")

#: What a refused call must leave as it was: the head, the journal, the switch.
STATE_SQL = f"""
SELECT md5(concat_ws('|',
  (SELECT seq::text FROM {REGISTER}.register_head),
  (SELECT string_agg(j::text, ',' ORDER BY j.seq) FROM {REGISTER}.journal j),
  (SELECT string_agg(s::text, ',') FROM {REGISTER}.register_switch s)));
"""

HOLD_HEAD = f"BEGIN;\nSELECT 1 FROM {REGISTER}.register_head WHERE id = 1 FOR UPDATE;\n"

_NAMES = itertools.count(1)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rendered(lines: Sequence[str], final_newline: bool) -> bytes:
    """`render_file`'s bytes: the lines joined by LF, and a last LF where
    the file ends with one and holds a line."""
    return ("\n".join(lines) + ("\n" if final_newline and lines else "")).encode("utf-8")


class Clone:
    """One clone of `tmpl`, and the documented functions called on it as
    REGISTER-WRITER, through `lanes_w_fx` (AT-LR006's fixture)."""

    def __init__(self, cluster, name: str) -> None:
        self.cluster, self.name = cluster, name
        self.db = Database(cluster, name)
        self.made = 0

    # -------------------------------------------------- the superuser's reads
    def value(self, sql: str) -> str:
        return self.db.psql(sql).stdout.strip()

    def json(self, sql: str):
        return json.loads(self.value(sql))

    def switch(self) -> dict:
        return self.json(f"SELECT row_to_json(s) FROM {REGISTER}.register_switch s;")

    def head(self) -> int:
        return int(self.value(f"SELECT seq FROM {REGISTER}.register_head;"))

    def client(self) -> int:
        return int(self.value(f"SELECT version FROM {REGISTER}.schema_version;"))

    def state(self) -> str:
        return self.value(STATE_SQL)

    def clock(self, seconds: float = 0) -> str:
        """The database's clock, plus `seconds`."""
        return self.value(f"SELECT (clock_timestamp() + make_interval(secs => {seconds}))::text;")

    def file(self, path: str) -> Tuple[Optional[bool], List[str]]:
        said = self.json(
            f"SELECT json_build_object('nl', (SELECT final_newline FROM {REGISTER}.files WHERE path = '{path}'), "
            f"'lines', (SELECT coalesce(jsonb_agg(text ORDER BY line_no), '[]') FROM {REGISTER}.doc_lines "
            f"WHERE path = '{path}'));")
        return said["nl"], said["lines"]

    def activity(self, appname: str) -> List[List[str]]:
        """Each backend of `appname`: pid, wait_event_type, wait_event."""
        out = self.value(
            "SELECT coalesce(json_agg(json_build_array(pid, wait_event_type, wait_event)), '[]') "
            f"FROM pg_stat_activity WHERE application_name = '{appname}' AND state = 'active';")
        return json.loads(out)

    def head_locks(self, pid: int) -> int:
        """The locks `pid` holds or waits for on the head row's table, its
        tuples, or a transaction id."""
        return int(self.value(
            f"SELECT count(*) FROM pg_locks WHERE pid = {pid} AND (relation = '{REGISTER}.register_head'::regclass "
            "OR locktype IN ('tuple', 'transactionid'));"))

    # -------------------------------------------------- the calls, as the writer
    def argv(self, variables: Dict[str, object]) -> List[str]:
        argv = [self.db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                "-v", "VERBOSITY=verbose", "-v", "SHOW_CONTEXT=never"]
        for name, value in variables.items():
            argv += ["-v", f"{name}={value}"]
        return argv

    def call(self, sql: str, appname: str = "t222", **variables) -> subprocess.CompletedProcess:
        return subprocess.run(self.argv(variables), input=sql, capture_output=True, text=True, timeout=60,
                              env=self.db.env(WRITER_LOGIN, appname), check=False)

    def start(self, sql: str, appname: str, user: str = WRITER_LOGIN, **variables) -> subprocess.Popen:
        """The same call, in the background: its script sent and its stdin closed."""
        proc = subprocess.Popen(self.argv(variables), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=self.db.env(user, appname))
        proc.stdin.write(sql)
        proc.stdin.close()
        proc.stdin = None
        return proc

    def commit_variables(self, entry: dict, base: Optional[int], write_id: str,
                         generation: Optional[str]) -> Dict[str, object]:
        return {"base": self.head() if base is None else base, "wid": write_id, "client": self.client(),
                "gen": generation or self.switch()["generation"],
                "entry": json.dumps(entry, ensure_ascii=False)}

    def commit(self, entry: dict, *, base: Optional[int] = None, write_id: Optional[str] = None,
               generation: Optional[str] = None) -> Tuple[subprocess.CompletedProcess, str]:
        write_id = write_id or str(uuid.uuid4())
        proc = self.call(COMMIT_SQL.format(set=""), **self.commit_variables(entry, base, write_id, generation))
        return proc, write_id

    def committed(self, entry: dict, **options) -> Tuple[int, str]:
        proc, write_id = self.commit(entry, **options)
        assert proc.returncode == 0, (
            f"commit_write as {WRITER_LOGIN} exited {proc.returncode}: {proc.stderr.strip()[-800:]}")
        return int(proc.stdout.strip()), write_id

    def lookup(self, write_id: str, not_after: str, *, generation: Optional[str] = None, lane: str = L1,
               verb: str = VERB, args: str = "") -> subprocess.CompletedProcess:
        return self.call(LOOKUP_SQL, appname="t222-lookup", **self.lookup_variables(
            write_id, not_after, generation, lane, verb, args))

    def lookup_variables(self, write_id, not_after, generation, lane, verb, args) -> Dict[str, object]:
        return {"wid": write_id, "not_after": not_after,
                "gen": generation or self.switch()["generation"], "lane": lane, "verb": verb, "args": args}

    # -------------------------------------------------- entries
    def journal(self, kind: str, verb: str, lane: str, **extra) -> dict:
        row = {"kind": kind, "verb": verb, "lane": lane, "workstation": WS, "author": AUTHOR,
               "message": f"{verb} by {lane} (T222)"}
        row.update(extra)
        return row

    def appended(self, path: str, texts: Sequence[str]) -> Tuple[list, list]:
        final_newline, lines = self.file(path)
        edits = []
        if final_newline is None:
            edits.append({"ord": 1, "op": "create", "path": path})
            final_newline = True
        for text in texts:
            edits.append({"ord": len(edits) + 1, "op": "append", "path": path, "new_text": text})
        return edits, [{"path": path, "present": True, "final_newline": final_newline,
                        "sha256": sha256(rendered([*lines, *texts], final_newline))}]

    def write_entry(self, lane: str = L1, verb: str = VERB, *, seconds: float = 60) -> dict:
        """A write: one line of no kind appended to `lanes/LANES.md`."""
        self.made += 1
        text = f"t222 note {self.made} — lane {lane}"
        edits, files = self.appended(LANES_MD, [text])
        args = sha256(f"{lane}\0{verb}\0{text}".encode("utf-8"))
        return {"journal": self.journal("write", verb, lane, args_sha256=args),
                "not_after": self.clock(seconds), "edits": edits, "files": files}

    def operator_entry(self, **switch) -> dict:
        edits, files = self.appended(STORE, ["primary"])
        entry = {"journal": self.journal("cutover", "cutover", OPERATOR), "not_after": self.clock(60),
                 "edits": edits, "files": files}
        if switch:
            entry["switch"] = switch
        return entry

    def mark(self, seq: int) -> None:
        marked = self.call(MARKER_SQL, client=self.client(), seq=seq, commit=MARKER_COMMIT, ws=WS)
        assert (marked.returncode, marked.stdout.strip()) == (0, "present"), marked.stderr
        sw = self.switch()
        assert (sw["mode"], sw["marker_state"]) == ("primary", "present"), sw

    def imported(self) -> int:
        """AT-LR006's route, its first step (TP:4610-4615): an `import` entry
        on the clone of `tmpl`, at `files` with the marker `absent` and an
        empty journal, as T221's `bring_to_primary` starts. It creates
        `lanes/LANES.md` with `IMPORT_LINES`, so the clone holds what a clone
        of `tmpl_imported` did, and the switch stays as it was."""
        sw = self.switch()
        assert (sw["mode"], sw["marker_state"], self.head()) == ("files", "absent", -1), (
            f"a clone of {TEMPLATE} is not at files, marker absent, with an empty journal: {sw}, head {self.head()}")
        edits, files = self.appended(LANES_MD, IMPORT_LINES)
        entry = {"journal": self.journal("import", "import", OPERATOR, git_commit=IMPORT_COMMIT,
                                         git_tree=IMPORT_TREE),
                 "not_after": self.clock(60), "edits": edits, "files": files}
        seq, _ = self.committed(entry)
        sw = self.switch()
        assert (sw["mode"], sw["marker_state"]) == ("files", "absent"), sw
        return seq

    def to_primary(self) -> int:
        """AT-LR006's route (TP:4610-4615): `imported`, then a `cutover`
        entry over that import, then `record_marker`."""
        self.imported()
        head = self.head()
        last_import = int(self.value(f"SELECT coalesce(max(seq), -2) FROM {REGISTER}.journal WHERE kind = 'import';"))
        assert last_import == head >= 0, f"the clone's head {head} is not its import ({last_import})"
        seq, _ = self.committed(self.operator_entry())
        self.mark(seq)
        return seq

    def refused(self, entry: dict, code: str, detail: Optional[str], *says: str, **options) -> List[str]:
        """The call ends with `code` and `detail`, and writes nothing."""
        before = self.state()
        proc, _ = self.commit(entry, **options)
        return self.check_refused(proc, before, code, detail, *says)

    def check_refused(self, proc, before: Optional[str], code: str, detail: Optional[str], *says: str) -> List[str]:
        lines = proc.stderr.splitlines()
        assert proc.returncode == 3, f"exit {proc.returncode}, not 3: {proc.stderr.strip()}"
        assert lines and lines[0].startswith(f"ERROR:  {code}: "), lines
        if detail is not None:
            assert lines[1:2] == [f"DETAIL:  {detail}"], lines
        for text in says:
            assert text in lines[0], f"{text!r} is not in {lines[0]!r}"
        if before is not None:
            assert self.state() == before, "the refused call changed the head, the journal or the switch"
        return lines


@pytest.fixture()
def clones(pg_cluster):
    """Clones of `tmpl`, each the test's own, dropped at the end."""
    made: List[str] = []

    def clone() -> Clone:
        name = f"t222_{next(_NAMES)}"
        pg_cluster.psql(f"CREATE DATABASE {name} TEMPLATE {TEMPLATE};")
        made.append(name)
        found = pg_cluster.psql(f"SELECT to_regclass('{REGISTER}.register_head') IS NOT NULL;", dbname=name)
        assert found.stdout.strip() == "t", (
            f"{TEMPLATE} holds no {REGISTER} schema: lane 2's T227 builds it by the bootstrap, "
            "which waits for lane 1's L1-A7")
        pg_cluster.psql(f"REVOKE ALL ON DATABASE {name} FROM PUBLIC;\n"
                        f"GRANT CONNECT ON DATABASE {name} TO {CONNECT_TO};\n")
        return Clone(pg_cluster, name)

    yield clone
    for name in made:
        pg_cluster.drop_database(name)


@pytest.fixture()
def holders(pg_cluster):
    """Superuser sessions fed on stdin, each ended at the test's end."""
    started: List[subprocess.Popen] = []

    def hold(c: Clone, appname: str = "t222-holder") -> subprocess.Popen:
        proc = c.db.session(SUPERUSER, appname)
        proc.stdin.write(HOLD_HEAD)
        proc.stdin.flush()
        started.append(proc)
        until(c, lambda: c.value(f"SELECT count(*) FROM pg_stat_activity WHERE application_name = '{appname}' "
                                 "AND state = 'idle in transaction';") == "1", "the holder took the head row")
        return proc

    yield hold
    for proc in started:
        end(proc)


def end(proc: subprocess.Popen) -> None:
    """Roll the holder back and let it exit."""
    if proc.poll() is None:
        try:
            proc.stdin.write("ROLLBACK;\n")
            proc.stdin.close()
            proc.stdin = None
        except (BrokenPipeError, ValueError):
            pass
        try:
            proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()


def until(c: Clone, ready, what: str, deadline: float = 20.0):
    """Poll `ready` until it answers truly, or fail naming `what`."""
    end_at = time.monotonic() + deadline
    while True:
        said = ready()
        if said:
            return said
        assert time.monotonic() < end_at, f"not seen within {deadline:.0f} s: {what}"
        time.sleep(0.05)


def restored(clones) -> Tuple[Clone, Dict[str, dict]]:
    """Database S: W0 and W1 under `g0`, the restore-form cutover to `g1`,
    confirmed, then W2 under `g1`. Returns each write's id, entry and seq."""
    c = clones()
    c.to_primary()
    writes: Dict[str, dict] = {}
    for name in ("W0", "W1"):
        entry = c.write_entry()
        seq, write_id = c.committed(entry)
        writes[name] = {"id": write_id, "entry": entry, "seq": seq, "gen": c.switch()["generation"]}
    g0 = writes["W0"]["gen"]
    assert c.switch()["database_label"] != RESTORED_LABEL
    seq, _ = c.committed(c.operator_entry(after_loss=True, database_label=RESTORED_LABEL))
    sw = c.switch()
    assert (sw["mode"], sw["marker_state"], sw["database_label"]) == ("primary", "adding", RESTORED_LABEL), sw
    assert sw["generation"] != g0
    c.mark(seq)
    entry = c.write_entry()
    seq, write_id = c.committed(entry)
    writes["W2"] = {"id": write_id, "entry": entry, "seq": seq, "gen": c.switch()["generation"]}
    return c, writes


def at_lr011(clones) -> Tuple[Clone, dict]:
    """A clone on `primary` with write W committed: lane L1, verb V, args a."""
    c = clones()
    c.to_primary()
    entry = c.write_entry()
    seq, write_id = c.committed(entry)
    return c, {"id": write_id, "seq": seq, "args": entry["journal"]["args_sha256"],
               "gen": c.switch()["generation"]}


# ------------------------------------------------------------ AT-LR007
@pytest.mark.parametrize("base", ["current-base", "stale-base"])
def test_a_write_of_another_generation_at_files_gets_lr007_not_lr002_or_lr001(clones, base):
    """In R, at `files`: a write of `g0` is LR007 `generation`, not LR002,
    with the base current, and not LR001 with it stale."""
    c = clones()
    c.imported()
    head = c.head()
    g0 = str(uuid.uuid4())
    c.refused(c.write_entry(), "LR007", "generation", f"belongs to register generation {g0}",
              generation=g0, base=head if base == "current-base" else head - 1)


def test_the_switchs_own_generation_at_files_still_gets_lr002(clones):
    """In R, a write of `g1`, the switch's own, with the base current: LR002."""
    c = clones()
    c.imported()
    c.refused(c.write_entry(), "LR002", None, "register switch is files with the marker absent")


@pytest.mark.parametrize("base", ["current-base", "stale-base"])
def test_an_old_generation_id_after_a_restore_form_cutover_gets_lr007_not_lr006(clones, base):
    """In S, after the restore form's cutover, W0's id with `g0`, found in
    the restored journal: LR007 `generation`, not LR006."""
    c, writes = restored(clones)
    w0 = writes["W0"]
    head = c.head()
    c.refused(w0["entry"], "LR007", "generation", f"write {w0['id']} belongs to register generation {w0['gen']}",
              write_id=w0["id"], generation=w0["gen"], base=head if base == "current-base" else head - 1)


@pytest.mark.parametrize("base", ["current-base", "stale-base"])
def test_a_same_generation_id_after_a_restore_form_cutover_gets_lr006(clones, base):
    """In S, W2's id with `g1` and W2's own lane, verb and `args_sha256`:
    LR006, naming its seq."""
    c, writes = restored(clones)
    w2 = writes["W2"]
    head = c.head()
    c.refused(w2["entry"], "LR006", None, f"write {w2['id']} is in the journal at seq {w2['seq']}",
              write_id=w2["id"], generation=w2["gen"], base=head if base == "current-base" else head - 1)


def test_an_id_in_the_journal_for_another_lane_gets_lr007(clones):
    """In S, W2's id with `g1` and another lane: LR007 `another-write`."""
    c, writes = restored(clones)
    w2 = writes["W2"]
    other = json.loads(json.dumps(w2["entry"]))
    other["journal"]["lane"] = L2
    c.refused(other, "LR007", "another-write", f"write {w2['id']} is seq {w2['seq']}, another write's (F10)",
              write_id=w2["id"], generation=w2["gen"])


# ------------------------------------------------------------ AT-LR011
@pytest.mark.parametrize("case", ["found", "absent"])
def test_find_write_returns_this_writes_seq_or_null(clones, case):
    """With `p_not_after` passed, W's id with its own generation, lane, verb
    and `args_sha256` returns W's seq; an id not in the journal, NULL."""
    c, w = at_lr011(clones)
    write_id = w["id"] if case == "found" else str(uuid.uuid4())
    proc = c.lookup(write_id, c.clock(-1), args=w["args"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split() == [str(w["seq"]) if case == "found" else "NULL", "t"]


@pytest.mark.parametrize("case", ["lane", "verb", "args", "null-args"])
def test_find_write_refuses_another_writes_entry_lr007(clones, case):
    """W's id with another lane, another verb, another `args_sha256`, or a
    NULL one, which never matches a write's entry: LR007 `another-write`."""
    c, w = at_lr011(clones)
    options = {"lane": L1, "verb": VERB, "args": w["args"]}
    options.update({"lane": {"lane": L2}, "verb": {"verb": OTHER_VERB},
                    "args": {"args": sha256(b"another write")}, "null-args": {"args": ""}}[case])
    proc = c.lookup(w["id"], c.clock(-1), **options)
    c.check_refused(proc, None, "LR007", "another-write", f"write {w['id']} is seq {w['seq']}")


@pytest.mark.parametrize("case", ["found", "absent"])
def test_find_write_refuses_another_generation_lr007(clones, case):
    """W's id, and an id not in the journal, each with a generation not the
    switch's: LR007 `generation`."""
    c, w = at_lr011(clones)
    write_id = w["id"] if case == "found" else str(uuid.uuid4())
    other = str(uuid.uuid4())
    proc = c.lookup(write_id, c.clock(-1), generation=other, args=w["args"])
    c.check_refused(proc, None, "LR007", "generation", f"belongs to register generation {other}")


def test_find_write_gives_lr011_before_lr007(clones):
    """With `p_not_after` 4 s ahead and a generation not the switch's: LR011."""
    c, w = at_lr011(clones)
    proc = c.lookup(w["id"], c.clock(4), generation=str(uuid.uuid4()), args=w["args"])
    c.check_refused(proc, None, "LR011", None, "past the 3 s wait")


def test_find_write_waits_on_the_server_clock_holding_no_lock(clones, holders):
    """With `p_not_after` 2 s ahead and the head row held, the lookup's
    backend is seen first in `PgSleep`, holding no lock, then waiting on a
    `Lock`; once the holder ends it returns W's seq, and the clock read next
    is not before `p_not_after`."""
    c, w = at_lr011(clones)
    holder = holders(c)
    not_after = c.clock(2)
    proc = c.start(LOOKUP_SQL, "t222-lookup", **c.lookup_variables(w["id"], not_after, None, L1, VERB, w["args"]))
    try:
        pid = until(c, lambda: [a[0] for a in c.activity("t222-lookup") if a[2] == "PgSleep"],
                    "the lookup sleeping in PgSleep")[0]
        assert c.head_locks(pid) == 0, "the lookup holds a lock while it sleeps"
        until(c, lambda: [a for a in c.activity("t222-lookup") if a[1] == "Lock"], "the lookup waiting on a Lock")
    finally:
        end(holder)
        out, err = proc.communicate(timeout=30)
    assert proc.returncode == 0, err
    assert out.split() == [str(w["seq"]), "t"]


def test_a_lookup_held_at_the_head_row_ends_55p03_inside_its_statement_timeout(clones, holders):
    """With `p_not_after` 2.9 s ahead and the head row held throughout, the
    lookup ends with 55P03 from its `lock_timeout`, not 57014: its wait and
    its lock fit its `statement_timeout`."""
    c, w = at_lr011(clones)
    holder = holders(c)
    try:
        proc = c.lookup(w["id"], c.clock(2.9), args=w["args"])
    finally:
        end(holder)
    c.check_refused(proc, None, "55P03", None)


def test_an_orphan_that_takes_the_lock_past_its_not_after_gets_lr008_and_the_lookup_finds_it_absent(clones, holders):
    """Commit call O of write X, `not_after` 2 s ahead, waits on the head row
    behind a holder, under `SET LOCAL lock_timeout = '5s'`; the lookup for X
    waits past `not_after`, then queues. The holder rolls back once the
    clock is past `not_after` and both wait on a `Lock`. Whichever takes the
    lock first, O ends LR008, the lookup returns NULL, and no journal row
    holds X's id."""
    c, w = at_lr011(clones)
    holder = holders(c)
    entry = c.write_entry(seconds=2)
    write_id = str(uuid.uuid4())
    variables = c.commit_variables(entry, None, write_id, None)
    orphan = c.start(COMMIT_SQL.format(set="SET LOCAL lock_timeout = '5s';\n"), "t222-orphan", **variables)
    lookup = c.start(LOOKUP_SQL, "t222-lookup", **c.lookup_variables(
        write_id, entry["not_after"], variables["gen"], L1, VERB, entry["journal"]["args_sha256"]))
    try:
        until(c, lambda: c.value(f"SELECT clock_timestamp() > '{entry['not_after']}'::timestamptz;") == "t"
              and any(a[1] == "Lock" for a in c.activity("t222-orphan"))
              and any(a[1] == "Lock" for a in c.activity("t222-lookup")),
              "the clock past not_after, with the orphan and the lookup each waiting on a Lock")
    finally:
        end(holder)
        orphan_out, orphan_err = orphan.communicate(timeout=30)
        lookup_out, lookup_err = lookup.communicate(timeout=30)
    c.check_refused(subprocess.CompletedProcess(orphan.args, orphan.returncode, orphan_out, orphan_err),
                    None, "LR008", None, f"write {write_id} reached its end")
    assert lookup.returncode == 0, lookup_err
    assert lookup_out.split() == ["NULL", "t"]
    assert c.value(f"SELECT count(*) FROM {REGISTER}.journal WHERE write_id = '{write_id}';") == "0"


# ============================================================ PHASE W: AT-12 and section 4.3's rival (T244)
#
# A COMMIT IN DOUBT (AT-12, ADV-C3; TP:2245-2420), ON T243's WORKSTATION: a
# clone of `tmpl` brought to `primary` by AT-LR006's route, one configuration
# naming it through `lanes_w_fx`, and per writer a `psql` directory holding
# T203's shim, armed by its control file for the writer's FIRST commit call
# only. Commit calls are the requests carrying `commit_write`, lookup tries
# those carrying `find_write`, and the snapshots lane 1's one read-only
# request, `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY` (`lanes-index`'s
# `_query_many`). The oracle never matches on stderr where AT-12 says so: the
# shim's `FATAL` line is one a real loss does not print.
#
# The lookup's timer is D9's `T_L`, `N_a`·`c` + 7 s, 9 s at `c` = 2 (open
# point 37). YS:685 as amended (R-F10-2): where `request-handoff` already
# wrote, its refusal names what it wrote; which of `[tail-sent]`,
# `[tail-done]` and `[no-record]` follow a committed write is NOTES question
# 33, so each asserts the journal's one entry and no `send-keys`.
#
# They FAIL UNTIL lane 1's T107 (L1-A6) and T114 (L1-A12, `journal
# --write-id`), lane 4's attempt loop on primary (L4-B2), its in-doubt rule
# and pending record (L4-B5) and its tail, once (L4-B15) land, with lane 2's
# T227 and T228. Without PostgreSQL 16 each skips.

SNAPSHOT_TEXT = "REPEATABLE READ READ ONLY"
AFTER = {"mode": "after", "match": "commit_write", "call": 1}
BEFORE = {"mode": "before", "match": "commit_write", "call": 1}
#: D9's commit-call timer, `C`, and AT-12's figures from it (TP:2331-2357).
C_S, WINDOW_S, T_L_S = 8, 10, 9
#: The tries' spacing, with lane 2's tolerance (T246's bullet; NOTES question 34).
GAP_S, LATE_S = 0.75, 1.25
#: The earliest exit 3 after `no-reconnect`, from the snapshot call's start
#: (TP:2346-2349, "no earlier than about 17 s": 8 s of waiting, and the 10 s
#: window less up to 1 s). The client's wait may itself end up to 1 s early,
#: since its estimate adds whole `SECONDS` to a whole-second clock, which is
#: why try 1 is allowed at `C_S - 1`; so the exit is allowed 1 s early too:
#: 16 s (T244e; lane 4's triage, #165 6833813092: 16.96 s on CI).
EXIT3_EARLIEST_S = (C_S - 1) + (WINDOW_S - 1)
PENDING = Path("openRepoTools") / "register-pending"
WRITE_ID_SAID = re.compile(r"LANES_WRITE_ID=(" + UUID_RE + r")")
GENERATION_SAID = re.compile(r"LANES_WRITE_GENERATION=(" + UUID_RE + r")")
NOT_AFTER_SAID = re.compile(r'"not_after"\s*:\s*"([^"]+)"')
#: The commit call's last COMMIT, with the `\;` that joins it to the statement
#: before it. `lanes-index` sends the commit as ONE request, `BEGIN ISOLATION
#: LEVEL SERIALIZABLE \; SELECT ...commit_write(...) \; COMMIT;`
#: (`PostgresStore.request`; contract §2.3; Y:1419), and `psql` sends its query
#: buffer only at a `;` that is not `\;`: a replay left ending ` \;` is never
#: sent, and its session never holds the head row (T244c; lane 4's triage,
#: #165 6833813092).
LAST_COMMIT = re.compile(r"(?:[ \t]*\\;)?[ \t]*\bCOMMIT\b[ \t]*;?(?![\s\S]*\bCOMMIT\b)", re.I)


def without_commit(script: str) -> str:
    """The commit call's script with its last COMMIT dropped, and sent whole:
    a ` \\; COMMIT;` becomes `;`, so `psql` sends the BEGIN and the
    `commit_write` call as one request and the session is left idle in its
    transaction; a `COMMIT;` of its own is dropped (`LAST_COMMIT`)."""
    return LAST_COMMIT.sub(lambda m: ";" if "\\;" in m.group(0) else "", script, count=1)


def note(lane: str, tag: str) -> List[str]:
    """A plain write: one `NOTE` line, by `append-line`."""
    return ["append-line", f"NOTE {EM} lane {lane}: {tag} (T244)"]


def one_entry(e: Estate, w: Writer, grew: int = 1) -> str:
    """AT-12's oracle: every commit call of `w` carried one write id, the
    journal grew by exactly `grew`, and that id appears once."""
    ids = w.write_ids()
    assert ids and len(set(ids)) == 1, f"{w.name}'s commit calls carried {ids}, not one write id"
    rows = e.journal_after()
    assert len(rows) == grew, f"the journal grew by {len(rows)}, not {grew}: {rows}"
    assert [r["write_id"] for r in rows].count(ids[0]) == 1, (ids[0], rows)
    return ids[0]


def lookups(w: Writer) -> List[dict]:
    return [c for c in w.stamps() if "find_write" in (c.get("stdin") or "")]


def pending(e: Estate) -> List[Path]:
    """The pending records, `<state>/openRepoTools/register-pending/<d>`."""
    where = e.state / PENDING
    return sorted(p for p in where.iterdir() if re.fullmatch(r"[0-9a-f]{64}", p.name)) if where.is_dir() else []


def until_seen(what: str, ready, w: Optional[Writer] = None, deadline: float = 90.0):
    end_at = time.monotonic() + deadline
    while True:
        said = ready()
        if said:
            return said
        if w is not None:
            assert w.ended is None, f"{w.name} exited {w.code} before {what}: {w.err[-400:]}"
        assert time.monotonic() < end_at, f"not seen within {deadline:.0f} s: {what}"
        time.sleep(0.05)


def fifo(e: Estate, name: str) -> Path:
    path = e.root / f"{name}.fifo"
    os.mkfifo(str(path))
    return path


def first_not_after(w: Writer) -> str:
    m = NOT_AFTER_SAID.search(w.commit_calls()[0].get("stdin") or "")
    assert m, "the first commit call's entry carries no not_after"
    return m.group(1)


def db_past(e: Estate, utc: str) -> bool:
    """Whether the database's clock has passed `utc`: an entry's
    `not_after`, UTC text, or a `call` line's, whole epoch seconds
    (pending-record.md §3.2), which `::timestamptz` cannot read, so it is
    read with `to_timestamp` (T244f; lane 4's triage, #165 6833813092)."""
    when = f"to_timestamp({int(utc)})" if re.fullmatch(r"[0-9]+", utc) else f"'{utc}'::timestamptz"
    return e.c.value(f"SELECT clock_timestamp() >= {when};") == "t"


# ------------------------------------------------------------ AT-12: after, before, timer
@CLIENT
def test_a_commit_that_landed_before_the_connection_was_lost_ends_with_one_entry_and_exit_0(estates):
    """`after`: the first COMMIT lands, then its backend is terminated. One
    entry, its write id once, exit 0."""
    e = estates()
    w = e.run(LA, note(LA, "after"), arms=[AFTER])
    assert w.code == 0, w.err[-800:]
    one_entry(e, w)


@CLIENT
def test_a_commit_lost_before_it_landed_is_retried_cleanly_and_ends_with_one_entry(estates):
    """`before`: the first COMMIT never lands. The writer retries cleanly,
    under the same write id, and exits 0 with one entry."""
    e = estates()
    w = e.run(LA, note(LA, "before"), arms=[BEFORE])
    assert w.code == 0, w.err[-800:]
    assert len(w.commit_calls()) >= 2, "the lost commit was not retried"
    one_entry(e, w)


@CLIENT
def test_an_outer_timer_expiry_is_in_doubt_like_exit_2(estates):
    """`timer`: the real `psql` commits, then the shim sleeps past the
    commit call's 8 s client timer (D9), whose expiry is in doubt as an exit
    2 is. One entry, exit 0; the time is recorded, not asserted."""
    e = estates()
    started = time.monotonic()
    w = e.run(LA, note(LA, "timer"), arms=[{"mode": "timer", "match": "commit_write", "call": 1,
                                                 "ms": 3 * C_S * 1000}])
    assert w.code == 0, w.err[-800:]
    one_entry(e, w)
    print(f"[T244 timer] took={time.monotonic() - started:.1f}s against C={C_S}s")


# ------------------------------------------------------------ AT-12: the half-open case
@CLIENT
@pytest.mark.parametrize("ending", ["rollback", "commit", "idle"])
def test_a_retry_with_the_old_connection_still_open_writes_no_second_row(estates, ending):
    """`before` loses the first commit call; the old connection, still open,
    is the test's session as `lanes_w_fx`, replaying that call's script
    without its COMMIT, so it holds the head row with the row inserted. The
    shim's `hold` keeps the next snapshot until the replay has returned.
    While the session is open no second row exists; [rollback]: the retry
    inserts once; [commit]: the waiting retry gets 40001, the next snapshot
    finds the id, and no commit call starts after the session's COMMIT;
    [idle]: the role's 5 s idle bound ends the session, and the writer
    commits once. One row, exit 0, in each."""
    e = estates()
    gate = fifo(e, "snapshot-2")
    w = e.launch(LA, note(LA, f"half-open {ending}"),
                 arms=[BEFORE, {"mode": "hold", "match": SNAPSHOT_TEXT, "call": 2, "fifo": str(gate)}])
    first = until_seen("the first commit call", lambda: w.commit_calls()[:1], w)[0]
    script = without_commit(first["stdin"])
    assert "commit_write" in script and script != first["stdin"], "the first commit call has no COMMIT to drop"
    assert script.rstrip().endswith(";") and not script.rstrip().endswith("\\;"), (
        f"the replay does not end in a `;` that psql sends: {script[-80:]!r}")
    session = e.c.db.session(WRITER_LOGIN, "t244-half-open")
    try:
        if ending != "idle":
            session.stdin.write("SET idle_in_transaction_session_timeout = 0;\n")
        session.stdin.write(script.rstrip() + "\n")
        session.stdin.flush()
        until_seen("the replay holding the head row", lambda: e.c.value(
            "SELECT count(*) FROM pg_stat_activity WHERE application_name = 't244-half-open' "
            "AND state = 'idle in transaction';") == "1", w)
        write_id = w.write_ids()[0]
        hold_point(gate, w).close()
        if ending != "idle":
            until_seen("a retry's commit call", lambda: len(w.commit_calls()) >= 2, w)
            assert not e.has_write(write_id), "a second row exists while the old transaction is open"
            closed = time.time()
            session.stdin.write("ROLLBACK;\n" if ending == "rollback" else "COMMIT;\n")
            session.stdin.flush()
        session.stdin.close()
        session.stdin = None
        assert w.wait() == 0, w.err[-800:]
    finally:
        if session.poll() is None:
            session.kill()
        session.communicate()
    assert one_entry(e, w) == write_id
    if ending == "commit":
        late = [c for c in w.stamps() if "commit_write" in (c.get("stdin") or "") and c["t"] > closed]
        assert not late, f"a commit call started after the old transaction committed: {late}"


# ------------------------------------------------------------ AT-12: no-reconnect, and the rerun
@CLIENT
@pytest.mark.parametrize("rerun", ["write-id", "plain"])
def test_a_callers_rerun_after_a_failed_reconnect_reuses_the_write_id(estates, rerun):
    """`no-reconnect`: the first commit call is lost, and every later call
    exits 2. The writer waits about 8 s, makes at least two lookup tries in
    the 10 s window, each at least 1 s after the last (with lane 2's 0.75 s
    tolerance) and none past 20 s from the first, and exits 3 no earlier than
    about 17 s after its snapshot (asserted at `EXIT3_EARLIEST_S`, 16 s) and
    under 54 s. Its report names the id and
    the rerun, read from it. [write-id]: the rerun under `LANES_WRITE_ID`
    and `LANES_WRITE_GENERATION`; [plain]: the same command line, which finds
    the pending record. Either exits 0, never mints a new id, never 69, and
    the journal holds one row for the id."""
    e = estates()
    argv = claim(OBJ, "--no-github")
    w = e.run(LA, argv, arms=[{"mode": "no-reconnect", "as": "before", "match": "commit_write", "call": 1}])
    assert w.code == 3, f"exit {w.code}, not 3: {w.err[-800:]}"
    snap = w.stamps()[0]["t"]
    tries = lookups(w)
    assert len(tries) >= 2, f"{len(tries)} lookup tries"
    assert tries[0]["t"] - snap >= C_S - 1, "a lookup try started before the client's wait ended"
    for k, (last, this) in enumerate(zip(tries, tries[1:]), 2):
        assert this["t"] - last["t"] >= GAP_S, f"try {k} started {this['t'] - last['t']:.2f} s after the last"
    assert tries[-1]["t"] - tries[0]["t"] <= 2 * WINDOW_S, "a try started past twice the window"
    took = time.time() - (time.monotonic() - w.ended) - snap
    assert EXIT3_EARLIEST_S <= took < 2 * (C_S + WINDOW_S + T_L_S), (
        f"exit 3 after {took:.1f} s, not in [{EXIT3_EARLIEST_S}, {2 * (C_S + WINDOW_S + T_L_S)}) s")
    print(f"[T244 no-reconnect] exit3={took:.1f}s against {C_S + WINDOW_S + T_L_S}s, "
          f"spread={tries[-1]['t'] - tries[0]['t']:.1f}s against {WINDOW_S}s")
    ids, gens = WRITE_ID_SAID.findall(w.err), GENERATION_SAID.findall(w.err)
    assert ids and gens, f"the report names no LANES_WRITE_ID rerun: {w.err[-800:]}"
    write_id = ids[-1]
    assert write_id == w.write_ids()[0]
    assert f"lanes-index journal --write-id {write_id}" in w.err
    extra = {"LANES_WRITE_ID": write_id, "LANES_WRITE_GENERATION": gens[-1]} if rerun == "write-id" else {}
    again = e.run(LA, argv, extra=extra)
    assert again.code == 0, f"the {rerun} rerun exited {again.code}: {again.err[-800:]}"
    assert set(again.write_ids()) <= {write_id}, f"the rerun minted a new id: {again.write_ids()}"
    assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1
    assert e.claimed(OBJ) == [(OBJ, LA)] and e.log_lines("CLAIMED", OBJ) == 1


@CLIENT
@pytest.mark.parametrize("mode", ["after", "before", "timer"])
def test_an_in_doubt_claim_never_leaves_two_claimed_lines_or_a_false_69(estates, mode):
    """`claim` in doubt by `after`, `before` or `timer`: exit 0, never 69,
    one entry, and the object has exactly one `CLAIMED` line."""
    e = estates()
    arm = {"after": AFTER, "before": BEFORE,
           "timer": {"mode": "timer", "match": "commit_write", "call": 1, "ms": 3 * C_S * 1000}}[mode]
    w = e.run(LA, claim(OBJ, "--no-github"), arms=[arm])
    assert w.code == 0, f"exit {w.code}: {w.err[-800:]}"
    one_entry(e, w)
    assert e.claimed(OBJ) == [(OBJ, LA)]
    assert e.log_lines("CLAIMED", OBJ) == 1


# ------------------------------------------------------------ AT-12: a next attempt refused for another reason
@CLIENT
@pytest.mark.parametrize("reason,code", [("database", 69), ("register", 2), ("verb", 2)])
def test_an_in_doubt_write_whose_next_attempt_is_refused_makes_its_lookup_before_it_exits(estates, reason, code):
    """The first commit call is lost before it lands, so the write is in
    doubt with no row; the second attempt is refused. [database]: `claim`,
    whose second commit's entry breaks a CHECK (test 2's late failure),
    23514; [register]: a `HOLD` line, whose second snapshot is held while
    another lane commits a `HOLD` for the same repository, LR005; [verb]:
    `claim`, held the same way while another lane claims the object, refused
    by the verb's own pre-check. In each the writer makes a `find_write` call
    after the refused attempt, once the database's clock has passed the
    first call's `not_after`, and exits with the refusal's own code; the
    journal holds no row for its id, and the pending record is removed."""
    e = estates()
    gate = fifo(e, "snapshot-2")
    arms = [BEFORE]
    if reason == "database":
        arms.append({"mode": "edit-entry", "match": "commit_write", "call": 2, "field": "journal.kind",
                     "value": "t244-no-such-kind"})
        argv = claim(OBJ, "--no-github")
    else:
        arms.append({"mode": "hold", "match": SNAPSHOT_TEXT, "call": 2, "fifo": str(gate)})
        argv = (["append-line", kind_line(e, "HOLD", LA)] if reason == "register"
                else claim(OBJ, "--no-github"))
    w = e.launch(LA, argv, arms=arms)
    if reason != "database":
        held = hold_point(gate, w)
        rival = (["append-line", kind_line(e, "HOLD", LB)] if reason == "register"
                 else claim(OBJ, "--no-github"))
        assert e.run(LB, rival).code == 0
        held.close()
    assert w.wait() == code, f"exit {w.code}, not {code}: {w.err[-800:]}"
    # Before T415 the writer's 69 is T409's placeholder, which makes no
    # commit call and equals [database]'s own 69: the case fails here, at its
    # own assertion, not at `write_ids()[0]` (AN13b's cause 5; line AF13b).
    assert w.commit_calls(), (f"exit {w.code}, but the writer made no commit call, so the "
                              f"write has no id (T415's primary branch): {w.err[-800:]}")
    write_id = w.write_ids()[0]
    stamps = w.stamps()
    attempts = [c for c in stamps if (SNAPSHOT_TEXT if reason == "verb" else "commit_write") in (c.get("stdin") or "")]
    assert len(attempts) >= 2, f"no second attempt: {len(attempts)}"
    assert [t for t in lookups(w) if t["t"] > attempts[1]["t"]], "no find_write call after the refused attempt"
    assert db_past(e, first_not_after(w)), "the writer exited before the first call's not_after"
    assert not e.has_write(write_id)
    assert pending(e) == [], f"the pending record was kept: {pending(e)}"


# ------------------------------------------------------------ AT-12: request-handoff runs none of its tail
@CLIENT
@pytest.mark.parametrize("state", ["tail-sent", "tail-done", "no-record"])
def test_a_request_handoff_that_runs_none_of_its_tail_exits_2_and_writes_nothing(estates, state):
    """GB §4.3's case (R29): `request-handoff`, with T248's fake `tmux` on
    `PATH`, is killed after its commit call returned, so the row has landed
    and its pending record holds a `call` line and no `tail` key. The rerun
    of the same command line, with the record at `tail=sent`, `tail=done`, or
    removed and rerun under `LANES_WRITE_ID` with its `LANES_WRITE_GENERATION`
    (an id with no generation and no record is refused 2 before any call:
    pending-record.md §5.2, R08; T244d), finds its write id and exits 2,
    not 0; the journal holds one entry for the id (YS:685 as amended: the
    write committed, so the refusal names it), the fake `tmux` logs no
    `send-keys` from the rerun, and stderr names the tail it did not run: the
    write's "after-COMMIT steps", the words every form of the engine's text
    names it by (`8ba10b4e:lanes-edit.sh:10168`, `:10169` and `:10319`); it
    never prints the word "tail" (T244g; PM33A-TRIAGE L1)."""
    e = estates()
    where = loggers(e)
    gate = fifo(e, "commit-1")
    argv = ["request-handoff", LC, "--session", session_of(LC)]
    w = e.launch(LA, argv, arms=[{"mode": "timer", "match": "commit_write", "call": 1, "fifo": str(gate)}],
                 first=[where])
    write_id = until_seen("the first commit call", lambda: w.commit_calls()[:1] and w.write_ids()[0], w)
    until_seen("the row landed", lambda: e.has_write(write_id), w)
    os.killpg(w.proc.pid, signal.SIGKILL)
    w.wait()
    records = pending(e)
    assert len(records) == 1, records
    text = records[0].read_text(encoding="utf-8")
    assert "\ncall=" in "\n" + text and "\ntail=" not in "\n" + text, text
    seq = e.journal_after()[-1]["seq"]
    extra = {}
    if state == "no-record":
        for path in records[0].parent.glob(records[0].name + "*"):
            path.unlink()
        extra = {"LANES_WRITE_ID": write_id, "LANES_WRITE_GENERATION": e.c.switch()["generation"]}
    else:
        with records[0].open("a", encoding="utf-8") as record:
            record.write(f"tail=sent {seq} {e.utc()}\n" if state == "tail-sent"
                         else f"tail=done {seq} 0 {e.utc()}\n")
    before = len(tool_calls(where, "tmux"))
    again = e.run(LA, argv, extra=extra, first=[where])
    assert again.code == 2, f"the rerun exited {again.code}, not 2: {again.err[-800:]}"
    assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1
    sent = [c for c in tool_calls(where, "tmux")[before:] if "send-keys" in c["argv"]]
    assert not sent, f"the rerun typed into a pane: {sent}"
    assert "after-COMMIT steps" in again.err, f"stderr names no after-COMMIT steps: {again.err[-800:]}"


# ------------------------------------------------------------ section 4.3: the rival
@CLIENT
def test_a_lookup_never_mistakes_a_rivals_row_for_the_lost_write(estates):
    """Section 4.3's rival: LA's first commit is lost before it lands, and
    LA's next call, its lookup try or its retry's snapshot, is held while LB
    commits the same line's text. A lookup by LA's id finds LA's write
    absent, never LB's row: LA retries under its own id and exits 0, and
    the journal holds each id once."""
    e = estates()
    gate = fifo(e, "call-3")
    argv = note(LA, "rival")
    w = e.launch(LA, argv, arms=[BEFORE, {"mode": "hold", "call": 3, "fifo": str(gate)}])
    held = hold_point(gate, w)
    rival = e.run(LB, argv)
    assert rival.code == 0, rival.err[-800:]
    held.close()
    assert w.wait() == 0, w.err[-800:]
    mine, theirs = w.write_ids()[0], rival.write_ids()[0]
    assert mine != theirs
    assert set(w.write_ids()) == {mine}, "the lost write's retry took another id"
    ids = [r["write_id"] for r in e.journal_after()]
    assert ids.count(mine) == 1 and ids.count(theirs) == 1, ids


# ============================================================ PHASE W: D8 and AT-F34 (T245)
#
# THE PENDING RECORD'S RERUN AND THE TAIL, ONCE (AT-D8, TP:3265-3528; AT-F34,
# TP:6941-7036), on T244's workstation and shim. The record is
# `<state>/openRepoTools/register-pending/<d>`, `key=value` lines with one
# `call=<base> <clock> <not_after> <files> <dir>` line per commit call that
# may have committed; its claim files are `<d>.take.<k>`; the done mark is
# `<state>/openRepoTools/register-done/<write_id>`. Every kill is sent on a
# FIFO signal, never after a sleep: the shim's `timer` joined to a FIFO
# blocks once the real `psql` has returned, and the test kills the run's
# process group there, so the row has landed and the writer cannot print.
#
# THE TAKEOVER (Q-L2-6; R26, lane 4's answer to 36): on this host a run that
# takes a killed run's record over waits past that call's `not_after`,
# whether its own snapshot passes or fails, on the record's clock when it
# has none of its own; `[snapshot-fails]` holds it. A record from another
# host keeps "calls at once" (T246's `[too-early]`).
#
# A `tail` RECORD A TAKEOVER CANNOT USE (R-F13c-23; lane 3's batch 8, #165
# 6780753157, Q46, Q34 and text change 1): a takeover of a record holding
# `tail` whose first snapshot has no `found=` refuses 2 and keeps the record,
# giving the effect check and, where the effect is not there, the same command
# with no `LANES_WRITE_ID` once the record is `LANES_REGISTER_PENDING_MAX_AGE_S`
# past its `updated_utc`, printing that time, never `LANES_WRITE_ID=new`
# (Y:5207, Y:5215); a `tail` of neither Y:5179 form is a record that cannot be
# read, T412's 2, the record kept.
#
# `found`'s two lines (R-F13-2, R-F13-7; F13b-OWED items 11 and 15): every
# `found` answer the shim and the fakes give here carries `workstation=` and
# `utc=` after its seq line, as lane 1's T114-fu3 prints them (`found <seq>`,
# `workstation=<name>`, `utc=<epoch s>`, then the `file=` rows), and AT-F34's
# no-record reruns choose Y:5347's text for this host or another by
# `workstation=`, naming the entry's UTC from `utc=`.
#
# THE TAIL'S `gh` CALL IS THE COMMENT (T245c; lane 4's triage, #165
# 6833813092): a case counts only `gh issue comment` and `gh pr comment`
# (`comments`), never `claim`'s Rule 1 reads, which every run of `claim`
# makes before the seam, a killed one and a refused one included.
#
# They FAIL UNTIL L4-B2, L4-B5 and L4-B6 land; `[snapshot-fails]` until lane
# 4's T417 and lane 1's T114 take the record's clock (Q-L1-1); the texts for 3
# until lane 4's T417, T433 and T434; the `tail` record a takeover cannot use
# until lane 4's T418 takes Q46 and Q34; and the `found` lines until lane 1's
# T114 and lane 5's T111 print them. Without PostgreSQL 16 each skips, except
# the texts for 3, which read the scripts and run here.

DONE = Path("openRepoTools") / "register-done"
CALL_LINE = re.compile(r"^-?[0-9]+ \S+ \S+ [0-9a-f]{64} /\S+$")
NO_RECONNECT = {"mode": "no-reconnect", "as": "before", "match": "commit_write", "call": 1}
#: D8's text for 3 (R29; GB §4.3; W:459-460, W:5647-5649; R2's S5), byte for byte.
D8_TEXT_3 = "may not be written; run the printed `LANES_WRITE_ID` rerun, which writes it once or finds it"
_KILLS = itertools.count(1)


def killed(e: Estate, lane: str, argv: Sequence[str], **options) -> Tuple[Writer, str]:
    """AT-D8's killed write: the first commit call's real `psql` returns,
    the shim blocks on its FIFO, and the test kills the run's group there."""
    gate = fifo(e, f"killed-{next(_KILLS)}")
    arms = [*options.pop("arms", ()), {"mode": "timer", "match": "commit_write", "call": 1, "fifo": str(gate)}]
    w = e.launch(lane, argv, arms=arms, **options)
    held = hold_point(gate, w)
    os.killpg(w.proc.pid, signal.SIGKILL)
    held.close()
    w.wait()
    write_id = w.write_ids()[0]
    assert e.has_write(write_id), "the killed call's row has not landed"
    return w, write_id


def exit3(e: Estate, lane: str, argv: Sequence[str], **options) -> Tuple[Writer, str, str]:
    """A run ended 3 by `no-reconnect`: the writer, its id and generation,
    read from its report."""
    w = e.run(lane, argv, arms=[NO_RECONNECT], **options)
    assert w.code == 3, f"exit {w.code}, not 3: {w.err[-800:]}"
    ids, gens = WRITE_ID_SAID.findall(w.err), GENERATION_SAID.findall(w.err)
    assert ids and gens, f"the report names no LANES_WRITE_ID rerun: {w.err[-800:]}"
    return w, ids[-1], gens[-1]


def the_record(e: Estate) -> dict:
    """The one pending record: its path, its first value of each key, and
    its `call` lines."""
    records = pending(e)
    assert len(records) == 1, f"{len(records)} pending records"
    fields: Dict[str, str] = {}
    calls: List[str] = []
    for line in records[0].read_text(encoding="utf-8").splitlines():
        key, eq, value = line.partition("=")
        if eq and key == "call":
            calls.append(value)
        elif eq:
            fields.setdefault(key, value)
    return {"path": records[0], "fields": fields, "calls": calls}


def take_files(e: Estate) -> List[str]:
    where = e.state / PENDING
    return sorted(p.name for p in where.glob("*.take.*")) if where.is_dir() else []


def mark_of(e: Estate, write_id: str) -> Path:
    return e.state / DONE / write_id


def gh_reads(where: Path) -> List[dict]:
    """The fake `gh`'s `issue view` calls: `claim`'s Rule 1 reads, which
    each run of the verb makes at its step 2, before the seam, an attempt's
    child or a replay's (`gh_reads_live`; Y:5043, Y:5326)."""
    return [c for c in tool_calls(where, "gh") if c["argv"][:2] == ["issue", "view"]]


def comments(where: Path) -> List[dict]:
    """The fake `gh`'s comment calls, `issue comment` or `pr comment`: a
    verb's tail. `claim`'s is its step 6, `gh_comment` once `write_event`
    returns (`91bfa229:lanes-edit.sh:24731-24737`), which under the flag is
    after the commit, from T414's seam: `commit_publish` returns through
    `cp_seam` (`:3710-3716`), whose committed step writes `tail`, sets
    `REGISTER_SEQ` and returns 0 (`:4247-4264`). This module counts those
    calls and never reads their text; T421 changes that text, and the order
    module's cases for T243 and T421 assert it (lane 4, #165 6852035770).
    Never Rule 1's reads, `issue view --comments` and `pr list`, which
    `claim` makes at its step 2, before the seam (`gh_reads_live`; Y:5043),
    and which decide nothing (T245c; lane 4's triage, #165 6833813092;
    T248a's `comment_calls` has the same shape)."""
    return [c for c in tool_calls(where, "gh") if c["argv"][:1] in (["issue"], ["pr"])
            and c["argv"][1:2] == ["comment"]]


def sidecar_text(lane: str, generation: int, utc: str, state: str = "RUNNING") -> str:
    """A whole lane-state snapshot, as `lane_state_put` writes one
    (`c8acf67c:lanes-edit.sh:23002`): `schema: 1` and every key its writer
    writes, none empty. A snapshot short of one is not a whole record, and
    every writer refuses it (`lane_sidecar_schema_ok`, `:22826-22846`; #115),
    so a sidecar of three keys was never followed (T245h; lane 4's triage,
    #165 6833813092)."""
    return (f"schema: 1\nlane: {lane}\nstate: {state}\ngeneration: {generation}\noperation: none\n"
            f"owner: none\nagent: none\nprofile: none\nworkstation: none\nkind: none\nupdated: {utc}\n")


def sidecars(e: Estate, lanes: Sequence[str] = (LA, LB, LC)) -> Path:
    root = e.root / "lane-state"
    utc = e.utc()
    for lane in lanes:
        (root / lane).mkdir(parents=True, exist_ok=True)
        (root / lane / "lane-state.yaml").write_text(sidecar_text(lane, 1, utc), encoding="utf-8")
    return root


def generation_of(root: Path, lane: str) -> str:
    for line in (root / lane / "lane-state.yaml").read_text(encoding="utf-8").splitlines():
        if line.startswith("generation:"):
            return line.split(":", 1)[1].strip()
    return ""


def tail_rerun(e: Estate, lane: str, argv: Sequence[str], where: Path, extra: Optional[dict] = None):
    """AT-D8's tail oracle around a killed write: no effect before the rerun;
    the rerun exits 0 with one row; the record wrote `tail=sent`, then
    `tail=done`, and is removed; the mark holds `done`; a second rerun under
    the id, with its generation (an id with no generation and no record is
    refused 2 before any call: pending-record.md §5.2, R08; T245d), finds
    the mark and runs none of the tail, so the effects stay at one
    (TP:3366-3367): no comment and no `tmux` call of its own, and the
    callers' checks of the sidecars and the handoff come after it. The
    logging `git` wrapper logs every `git` call a run makes, so its count is
    no oracle of the tail. Returns the rerun and the id."""
    _, write_id = killed(e, lane, argv, first=[where], extra=extra)
    before = len(tool_calls(where))
    again = e.run(lane, argv, first=[where], extra=extra)
    assert again.code == 0, f"the rerun exited {again.code}: {again.err[-800:]}"
    assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1
    assert pending(e) == [] and take_files(e) == []
    assert "done" in mark_of(e, write_id).read_text(encoding="utf-8")
    effects = len(comments(where)), len(tool_calls(where, "tmux"))
    third = e.run(lane, argv, first=[where], extra=dict(extra or {}, LANES_WRITE_ID=write_id,
                                                         LANES_WRITE_GENERATION=e.c.switch()["generation"]))
    assert third.code == 0, f"the second rerun exited {third.code}: {third.err[-800:]}"
    assert (len(comments(where)), len(tool_calls(where, "tmux"))) == effects, "a second rerun ran the tail again"
    return again, write_id, before


# ------------------------------------------------------------ D8: the record
@CLIENT
def test_a_committed_write_leaves_no_pending_record(estates):
    """After a committed write no record and no claim file remains, and the
    done mark does: 0600 in a 0700 directory, holding the id, the seq and
    the `tail` value, `done`."""
    e = estates()
    w = e.run(LA, note(LA, "committed"))
    assert w.code == 0, w.err[-800:]
    write_id = one_entry(e, w)
    assert pending(e) == [] and take_files(e) == []
    mark = mark_of(e, write_id)
    assert mark.stat().st_mode & 0o777 == 0o600 and mark.parent.stat().st_mode & 0o777 == 0o700
    text = mark.read_text(encoding="utf-8")
    assert write_id in text and str(e.journal_after()[-1]["seq"]) in text and "done" in text, text


@CLIENT
def test_a_plain_rerun_reuses_the_pending_write_id_once_and_says_so(estates):
    """After exit 3 the record names the id and holds the call's `call` line
    (base, clock, `not_after`, the `files` digest, the attempt directory),
    and no other key says the write is in doubt. A plain rerun says on
    stderr that it reuses the id, exits 0, leaves one row and removes the
    record; a second plain rerun is a new write, under a new id."""
    e = estates()
    argv = note(LA, "plain rerun")
    _, write_id, _ = exit3(e, LA, argv)
    rec = the_record(e)
    assert rec["fields"].get("write_id", "").lower() == write_id
    assert len(rec["calls"]) == 1 and CALL_LINE.match(rec["calls"][0]), rec["calls"]
    again = e.run(LA, argv)
    assert again.code == 0, again.err[-800:]
    assert write_id in again.err and "reus" in again.err.lower(), again.err[-800:]
    assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1
    assert pending(e) == []
    third = e.run(LA, argv)
    assert third.code == 0 and set(third.write_ids()) and write_id not in third.write_ids()


@CLIENT
def test_a_write_killed_by_an_outer_timer_is_retried_under_its_own_id(estates):
    """A write killed after its call returned prints nothing; its plain
    rerun reuses the id, exits 0, and leaves one row."""
    e = estates()
    argv = note(LA, "killed")
    _, write_id = killed(e, LA, argv)
    again = e.run(LA, argv)
    assert again.code == 0, again.err[-800:]
    assert set(again.write_ids()) <= {write_id}
    assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1


@CLIENT
def test_a_rerun_with_other_arguments_does_not_take_the_pending_id(estates):
    """A rerun with other arguments is a write of its own: it never sends
    the pending id, and the record stays."""
    e = estates()
    _, write_id, _ = exit3(e, LA, note(LA, "first arguments"))
    other = e.run(LA, note(LA, "other arguments"))
    assert other.code == 0, other.err[-800:]
    assert write_id not in other.write_ids()
    assert the_record(e)["fields"].get("write_id", "").lower() == write_id


@CLIENT
def test_lanes_write_id_of_another_write_is_refused_2_and_the_pending_record_kept(estates):
    """G6 (pending-record.md §5.2, T412's G6; lane 3's ruling "G6 stands",
    #165 6834271321; T245g): after exit 3 the record of a command line holds
    write P and its `call` line. `LANES_WRITE_ID`, set to a fresh id with
    its generation, is refused with 2: the fresh id is never sent, no
    commit call is made, the record still holds P and its `call` line, and
    stderr names P and its lookup, `lanes-index journal --write-id P`. A
    fresh id cannot win: it would drop another write's in-doubt record
    without F3's lookup, or write with no record, and Y forbids both
    (Y:5171, Y:5196-5198, Y:5215). The test was
    `test_lanes_write_id_wins_over_a_pending_record`, from the test plan's
    "wins over a record" (TP:3350 at B19, :3359 at `a91df2c4`), which
    predates the contract and G6."""
    e = estates()
    argv = note(LA, "explicit id")
    _, pending_id, generation = exit3(e, LA, argv)
    rec = the_record(e)
    mine = str(uuid.uuid4())
    w = e.run(LA, argv, extra={"LANES_WRITE_ID": mine, "LANES_WRITE_GENERATION": generation})
    assert w.code == 2, f"exit {w.code}, not 2: {w.err[-800:]}"
    sent = [c for c in w.calls() if mine in (c.get("stdin") or "")]
    assert w.commit_calls() == [] and not sent, (w.commit_calls(), sent)
    kept = the_record(e)
    assert kept["fields"].get("write_id", "").lower() == pending_id and kept["calls"] == rec["calls"], kept
    assert pending_id in w.err and f"lanes-index journal --write-id {pending_id}" in w.err, w.err[-800:]


@CLIENT
def test_lanes_write_id_of_the_records_own_write_takes_it_over_past_its_age(estates):
    """The case that holds under G6 (pending-record.md §5.2, :225: an id
    whose record holds it is "the record taken over, at any age"; T245g):
    after exit 3, with the record past the maximum age
    (`LANES_REGISTER_PENDING_MAX_AGE_S=2`), where a plain rerun writes anew
    under a new id, the printed rerun, `LANES_WRITE_ID` of the record's own
    write with its generation, takes it over: exit 0, every commit call
    under that id, one row for it, and the record removed."""
    e = estates()
    argv = note(LA, "own id past the age")
    _, pending_id, generation = exit3(e, LA, argv)
    time.sleep(3)
    w = e.run(LA, argv, extra=dict(MAX_AGE, LANES_WRITE_ID=pending_id, LANES_WRITE_GENERATION=generation))
    assert w.code == 0, w.err[-800:]
    assert set(w.write_ids()) == {pending_id}, w.write_ids()
    assert [r["write_id"] for r in e.journal_after()].count(pending_id) == 1
    assert pending(e) == [] and take_files(e) == []


@CLIENT
@pytest.mark.parametrize("case", ["absent", "found"])
def test_status_lists_and_resolves_pending_records(estates, case):
    """`lanes-index status` lists each pending record and reports whether
    its id is in the journal: [absent], the first call lost before it
    landed; [found], after it."""
    e = estates()
    arm = dict(NO_RECONNECT, **{"as": "before" if case == "absent" else "after"})
    w = e.run(LA, note(LA, f"status {case}"), arms=[arm])
    assert w.code == 3, w.err[-800:]
    write_id = WRITE_ID_SAID.findall(w.err)[-1]
    env = dict(e.env, PATH=os.pathsep.join([str(e.psql_dir(f"status-{case}")), e.env["PATH"]]))
    status = subprocess.run([str(e.bindir / "lanes-index"), "status"], capture_output=True, text=True,
                            env=env, check=False, timeout=120)
    assert write_id in status.stdout, status.stdout[-800:]
    line = next(l for l in status.stdout.splitlines() if write_id in l)
    if case == "found":
        assert str(e.journal_after()[-1]["seq"]) in line, line
    else:
        assert "absent" in line or "not in the journal" in line, line


# ------------------------------------------------------------ D8: each verb's tail
@CLIENT
def test_a_rerun_that_finds_its_write_committed_runs_the_verbs_after_commit_tail(estates):
    """`rename-lane`'s tail: `lane_state_rename` moves the old control root
    to the new name once; the handoff file at the new path holds one
    `RENAMED from <old>` line, under its header, never two (TP:3384-3389),
    moved there, with nothing left at the old path, in the lane checkouts
    and on the lanes origin's `main`, where it is pushed; the fake `gh`
    logs one comment per held claim (none here). The estate
    holds the lane's handoff in its checkout (TP:3315): `seed_handoff`."""
    e = estates()
    where, root = loggers(e), sidecars(e)
    new = "repoA-9"
    extra = {"LANES_LANE_STATE_ROOT": str(root)}
    seed_handoff(e, LA)
    again, _, _ = tail_rerun(e, LA, ["rename-lane", LA, new, "T245", "--no-github"], where, extra)
    assert (root / new).is_dir() and not (root / LA).exists()
    # The move and stamp are made in the lane's own register checkout, `PW_C`,
    # `<W>-lanes/<lane>` (`8ba10b4e:lanes-edit.sh:25251-25256`), which the
    # estate makes at `co-<n>-lanes/<lane>`, never in W (T245l; PM33A-TRIAGE L2).
    # It is a move (TP:3386-3387, "The handoff's move and stamp run once"), so
    # no checkout that holds the moved file still holds the old one; and it is
    # pushed (Y:5092's S3-S4 commit; `f42d2c85:lanes-edit.sh:21173-21177` warns
    # where the push is not confirmed), so the lanes origin's `main` holds the
    # moved file, stamped once, and nothing at the old path (RV20's NIT 15).
    old, moved, stamp = lane_handoff(LA), lane_handoff(new), f"RENAMED from {LA} "

    def one_stamp(label: str, lines: List[str]) -> None:
        assert sum(l.startswith(stamp) for l in lines) == 1 and lines[3:4] and lines[3].startswith(stamp), (
            f"{label} does not hold one Rule 3 stamp under its header: {lines[:6]}")

    handoffs = list(e.root.glob(f"co-*-lanes/*/{moved}"))
    assert handoffs, f"no lane checkout holds {moved}"
    for h in handoffs:
        co = h.parents[len(Path(moved).parts) - 1]
        assert not (co / old).exists(), f"{co} holds both {old} and {moved}: a copy, not a move"
        one_stamp(str(h), h.read_text(encoding="utf-8").splitlines())
    on_main = run_git(e.origin, "ls-tree", "-r", "--name-only", "main", "--", "handoffs/", env=e.env).split()
    assert moved in on_main and old not in on_main, f"the lanes origin's main holds {on_main}: the move is not pushed"
    one_stamp(f"{e.origin} main:{moved}", run_git(e.origin, "show", f"main:{moved}", env=e.env).splitlines())
    assert comments(where) == []


def by_hand(e: Estate, message: str, *change: str, emptied: str = "") -> None:
    """A person's commit on the lanes origin, made from the estate's seed
    clone brought up to the origin first: the file `emptied` names, if any,
    emptied, and `git <change>`, then commit and push. Every checkout a
    later run makes holds it."""
    run_git(e.seed, "pull", "-q", "--ff-only", "origin", "main", env=e.env)
    if emptied:
        (e.seed / emptied).write_text("", encoding="utf-8")
    run_git(e.seed, *change, env=e.env)
    run_git(e.seed, "commit", "-q", "-m", message, env=e.env)
    run_git(e.seed, "push", "-q", "origin", "main", env=e.env)


def lane_handoff(lane: str) -> str:
    """A handoff named for its lane, `session-handoff-<date>-lane-<lane>.md`:
    the one shape `rename-lane` moves, to the same date with `-lane-<new>`
    (Amendment 16(d); `8ba10b4e:lanes-edit.sh:28903-28925`). Test 4's rows
    name `handoffs/<lane>.md` (`w_row`), which it stamps where it is and
    never moves (`:29155-29156`)."""
    return f"handoffs/session-handoff-2026-05-01-lane-{lane}.md"


def seed_handoff(e: Estate, lane: str) -> str:
    """AT-D8's `rename-lane` estate, "the lane's handoff file in its
    checkout" (TP:3315). A run looks for the handoff its row names in the
    lane's own register checkout, `<W>-lanes/<lane>`, cloned from the lanes
    origin, and where that checkout holds none it moves and stamps nothing
    (`8ba10b4e:lanes-edit.sh:25064-25065`, `:29133-29136`). So the handoff,
    a header block and the blank line Rule 3's stamp goes under
    (`rl_stamp_build`, `:25000-25021`), is committed on the lanes origin
    from the estate's seed clone, before any run, and `lane`'s row is
    pointed at it by `replace-in-row`, the verb the engine names for that
    (`:24985`). Returns its path in a checkout."""
    rel = lane_handoff(lane)
    (e.seed / rel).parent.mkdir(parents=True, exist_ok=True)
    (e.seed / rel).write_text(f"# Handoff: lane {lane}\nT245's seed.\n\nNothing is owed.\n", encoding="utf-8")
    run_git(e.seed, "add", "--", rel, env=e.env)
    run_git(e.seed, "commit", "-q", "-m", f"handoff({lane}): T245's seed", env=e.env)
    run_git(e.seed, "push", "-q", "origin", "main", env=e.env)
    w = e.run(lane, ["replace-in-row", lane, f"handoffs/{lane}.md", rel, "T245: a handoff named for its lane"])
    assert w.code == 0, f"replace-in-row exited {w.code}: {w.err[-800:]}"
    return rel


@CLIENT
@pytest.mark.parametrize("verb", ["RESUMED", "ENDED", "RESUMED-moved-since"])
def test_the_after_commit_tail_of_log_runs_once_when_a_rerun_finds_the_write(estates, verb):
    """`log`'s tail for a verb `lane_state_follow` moves: the sidecar goes
    from g to g+1 once. [RESUMED-moved-since]: another act moved the lane
    since the kill, the replay's fence refuses, the sidecar stays as that act
    left it, a note says the lifecycle moved under the line, exit 0."""
    e = estates()
    where, root = loggers(e), sidecars(e)
    extra = {"LANES_LANE_STATE_ROOT": str(root)}
    argv = ["log", verb.split("-")[0], f"lane:{LA}", f"T245 {verb}"]
    _, write_id = killed(e, LA, argv, first=[where], extra=extra)
    assert generation_of(root, LA) == "1", "the tail ran before the rerun"
    if verb == "RESUMED-moved-since":
        (root / LA / "lane-state.yaml").write_text(sidecar_text(LA, 7, e.utc()), encoding="utf-8")
    again = e.run(LA, argv, first=[where], extra=extra)
    assert again.code == 0, again.err[-800:]
    assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1
    if verb == "RESUMED-moved-since":
        assert generation_of(root, LA) == "7" and "moved" in again.err, again.err[-800:]
    else:
        assert generation_of(root, LA) == "2"


@CLIENT
def test_the_after_commit_tail_of_release_runs_once_when_a_rerun_finds_the_write(estates):
    """`release`: its one comment, once, after the rerun finds the write."""
    e = estates()
    where = loggers(e)
    assert e.run(LA, claim(OBJ, "--no-github")).code == 0
    tail_rerun(e, LA, ["release", OBJ, "T245", "--home", OBJ.split("#")[0]], where)
    assert len(comments(where)) == 1, comments(where)


@CLIENT
def test_the_after_commit_tail_of_request_handoff_types_once_in_the_kept_child_and_polls(estates):
    """`request-handoff`: the kept child ran the tail, so the fake `tmux`
    logs one `send-keys`, and the poll reads and ends the run; the request is
    in the register once. Run with `--wait 2` and `LANES_POLL_SECONDS=1`.
    The fake `tmux` answers the bound window as live (T248b's
    `loggers(e, tmux_live=True)`): the silent one answers no window read, so
    the window never reads live and nothing is typed (T245m; PM33A-TRIAGE L3;
    N2-17b's reading 2)."""
    e = estates()
    where = loggers(e, tmux_live=True)
    w = e.run(LA, ["request-handoff", LC, "--session", session_of(LC), "--wait", "2"], arms=[AFTER],
              first=[where], extra={"LANES_POLL_SECONDS": "1"})
    assert w.code in (0, 2), w.err[-800:]
    one_entry(e, w)
    sent = [c for c in tool_calls(where, "tmux") if "send-keys" in c["argv"]]
    assert len(sent) == 1, sent
    assert len(tool_calls(where, "tmux")) > 1, "the poll never read the pane"


#: The two rows `retire-rows` retires: lane B, and the first burst lane, which
#: no estate binds (T243g binds lane C, whose `STARTED` line `retire-rows`
#: refuses; T245k).
DORMANT = (LB, BURST[0])


@CLIENT
def test_the_after_commit_tail_of_retire_rows_runs_once_when_a_rerun_finds_the_write(estates):
    """`retire-rows`: each retired lane's sidecar goes through its follow
    once, with its own pre-image.

    THE ROWS ARE DORMANT FIRST (Amendment 19(a); T245k; lane 4's triage,
    #165 6833813092). `retire-rows` takes only a dormant row: its object log
    carries no lane-kind line at all, an `ENDED` or `RETIRED` last line
    included, which it refuses as a lane already CLOSED
    (`c8acf67c:lanes-edit.sh:21966-21977`), and its state cell is not
    Amendment 13(a)'s phrase naming anything but `ENDED`, `RETIRED` or
    `MIGRATED` (`:21995-21999`). Test 4's rows read `LIVE` (`w_row`), so each
    lane's cell is first set to `ENDED` by `set-row-state`, which replaces the
    row line alone, writes no log line and has no tail (TP:3368-3371). Its
    log keeps no lane-kind line. Lane C is not one of them: T243g's estate
    binds it with a `STARTED` line."""
    e = estates()
    where, root = loggers(e), sidecars(e, (LA, *DORMANT))
    for lane in DORMANT:
        ended = e.run(lane, ["set-row-state", lane, f"ENDED {DOT} dormant, for T245's retire-rows tail"])
        assert ended.code == 0, f"set-row-state {lane} exited {ended.code}: {ended.err[-800:]}"
    tail_rerun(e, LA, ["retire-rows", *DORMANT, "--reason", "T245"], where, {"LANES_LANE_STATE_ROOT": str(root)})
    assert [generation_of(root, lane) for lane in DORMANT] == ["2", "2"]


@CLIENT
def test_the_after_commit_tail_of_start_record_runs_once_when_a_rerun_finds_the_write(estates):
    """`start-record`: `lane_state_follow` runs once after the lock: one
    move of the lane's sidecar.

    The call is in T427's form, as the arm parses it
    (`7893339:lanes-edit.sh:29679-29722`, `SR_USE` at `:15521`): the lane,
    then the log line's verb, `RESUMED`, then `--state` for the row that is
    there, then `--log` with `lane:<lane>`, the arrow and a payload.
    `Estate.launch` sets `LANES_LANE` to the lane and `LANES_SESSION` to its
    transcript uuid, which the arm asks for before any read
    (`:29736-29743`). T245's `--session` was no word of the arm's: it
    refused it as the verb, 2 (`:29686`; line N2-23's r1b). The lane's own
    checkout comes from N2's T243t (`c900063a`, `write_lanes_of`'s
    `start-record` arm; lane 3, #165 6859307928)."""
    e = estates()
    where, root = loggers(e), sidecars(e)
    argv = ["start-record", LA, "RESUMED", "--state", f"LIVE {DOT} T245 start-record",
            "--log", f"lane:{LA}", ARROW, "T245 start-record"]
    tail_rerun(e, LA, argv, where, {"LANES_LANE_STATE_ROOT": str(root)})
    assert generation_of(root, LA) == "2"


@CLIENT
def test_a_rerun_after_a_3_replays_the_verbs_tail_once(estates):
    """`no-reconnect` ends the first `claim` with 3 (its first call landed),
    abandoning its kept child, with no comment made. A plain rerun finds the
    record, its snapshot finds the id, it replays at `s-1` (one `--at` call)
    and runs the tail: one comment, exit 0."""
    e = estates()
    where = loggers(e)
    argv = claim(OBJ)
    w = e.run(LA, argv, arms=[dict(NO_RECONNECT, **{"as": "after"})], first=[where])
    assert w.code == 3 and comments(where) == [], w.err[-800:]
    again = e.run(LA, argv, first=[where])
    assert again.code == 0, again.err[-800:]
    assert len(comments(where)) == 1, comments(where)


@CLIENT
@pytest.mark.parametrize("state", ["sent-child-never-read", "owed-mark"])
def test_a_sent_record_whose_child_never_read_committed_replays_and_an_owed_mark_runs_no_tail(estates, state):
    """[sent-child-never-read]: a record holding `tail=sent` while the dead
    child's `seam.out` says `none`: the owner removes `tail` and replays,
    once, one comment, exit 0 (Y:5342; lane 3's rule, #165 6838365309 and
    6838735040). The takeover reads the `seam.out` in the directory of the
    record's `call=` line (Y:5173), so the case writes `none` there: the
    child, killed while its parent's commit call was held, wrote none
    (it writes one only at its seam, `8ba10b4e:lanes-edit.sh:5150-5164`,
    `:5453`). The replay ran once: its child made `claim`'s Rule 1 reads,
    `gh issue view`, as many times as the killed run's child did, since a
    replay reads `gh_reads` again (Y:5326) and the takeover's parent runs
    no verb. Y:5043's cache, "in the write's directory across attempts",
    does not reach the replay: the engine keeps it in the run's directory,
    `<d>/<run>/`, which every attempt of one run shares (T413;
    `f42d2c85:lanes-edit.sh:17911-17912`), and a replay makes no commit
    call, so it is no attempt, and runs in a fresh run segment,
    `<d>/<new run>/1` (`:8548-8550`; lane 3, #165 6770688147, "The fresh
    run segment and what the replay reads: confirmed"). Were the cache to
    reach across a replay, its child would make no reads and this count
    would fail, not pass (RV20's NIT 14). `tail` was removed: the done
    mark holds the replayed tail's `done`, not the `sent` the record held,
    which a run that keeps the `sent` row writes the mark from
    (Y:5338-5342). [owed-mark]: a mark
    holding `owed <utc>`; a rerun
    under `LANES_WRITE_ID`, with its generation (T245d), runs no tail, adds
    no comment, and names the steps as owed again. The mark is written in
    its contract's form, one `key=value` a line, `write_id`, `seq`, `tail`,
    `pid`, `host`, `container` and `utc` (pending-record.md §6), the form
    the run reads (`wr_done_read`, `c8acf67c:lanes-edit.sh:7778`): one of
    another form is no mark (T245f)."""
    e = estates()
    where = loggers(e)
    argv = claim(OBJ)
    _, write_id = killed(e, LA, argv, first=[where])
    rec = the_record(e)
    if state == "sent-child-never-read":
        with rec["path"].open("a", encoding="utf-8") as f:
            f.write(f"tail=sent {e.journal_after()[-1]['seq']} {e.utc()}\n")
        assert len(rec["calls"]) == 1, rec["calls"]
        old = Path(rec["calls"][0].split(None, 4)[4].strip())
        assert old.is_dir(), f"the record's call= directory {old} is not there"
        (old / "seam.out").write_text("none\n", encoding="utf-8")
        killed_reads = len(gh_reads(where))
        again = e.run(LA, argv, first=[where])
        assert again.code == 0 and len(comments(where)) == 1, (again.err[-800:], comments(where))
        assert killed_reads > 0 and len(gh_reads(where)) == 2 * killed_reads, (
            f"the replay's child made {len(gh_reads(where)) - killed_reads} of claim's Rule 1 reads, "
            f"the killed run's child {killed_reads}: not one replay")
        mark = mark_of(e, write_id).read_text(encoding="utf-8")
        assert pending(e) == [] and re.search(r"(?m)^tail=done ", mark), f"tail was not replayed to done: {mark!r}"
    else:
        mark = mark_of(e, write_id)
        mark.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fields, utc = rec["fields"], e.utc()
        mark.write_text(f"write_id={write_id}\nseq={e.journal_after()[-1]['seq']}\ntail=owed {utc}\n"
                        f"pid={fields.get('pid', '')}\nhost={fields.get('host', '')}\n"
                        f"container={fields.get('container', '')}\nutc={utc}\n", encoding="utf-8")
        mark.chmod(0o600)
        rec["path"].unlink()
        again = e.run(LA, argv, first=[where], extra={"LANES_WRITE_ID": write_id,
                                                      "LANES_WRITE_GENERATION": e.c.switch()["generation"]})
        assert again.code == 0 and comments(where) == [] and "owed" in again.err, again.err[-800:]


@CLIENT
@pytest.mark.parametrize("case", ["rename-lane-stops", "rename-lane-differs", "request-handoff-differs"])
def test_a_replay_of_rename_lane_or_request_handoff_that_stops_or_differs_runs_none_of_the_tail(estates, case):
    """The write is committed either way. [rename-lane-stops]: the handoff
    file emptied, so the replay stops before its write; [rename-lane-differs]:
    the handoff removed by hand, so the row's handoff cell is left as it is
    and the change set differs first at `lanes/LANES.md` (TP:3447-3450 at
    `f4591a08`; in Y's frame, TP:3424-3427 said the handoff "is moved to
    the new path by hand"; lane 3, #165 6851669848). Each writes
    the mark `owed <utc>`, removes the record, prints one WARNING, exits 0
    and runs no tail. [request-handoff-differs]: the fake `tmux` reports the
    holder's window gone; the run exits 2, saying the request is written at
    seq `<s>` and it did not wait for the release.

    The two `rename-lane` forms need the lane's handoff in its checkout
    (TP:3315), named for its lane so that the rename changes the row's
    cell (`seed_handoff`, T245r). Each run clones its own W and lane
    checkouts from the lanes origin (`Estate.launch`), so the rerun never
    sees a change made in the killed run's checkouts: the handoff is
    emptied or removed by hand on the origin (`by_hand`), before the rerun.

    [rename-lane-stops] empties the handoff, as lane 3 ruled (#165
    6841366245) and as the test plan says since fold 1112p (`e7b1ed5e`):
    the handoff file "is committed empty in the lane's checkout", and "the
    replay's stamp proof (Y:5092) refuses it with 5 before the seam"
    (TP:3442-3444 at `b8e3df74`; in Y's frame, TP:3419-3421 said "removed
    from"). The handoff is still there, tracked under `handoffs/` with no
    pending change, so the replay's checks pass and `rl_stamp_build`'s
    proof refuses it with 5 before the seam
    (`049c0da1:lanes-edit.sh:20870-20874`), Y:5092's "a handoff that
    cannot be stamped refuses". A handoff removed instead
    keeps Amendment 16(d)'s note on primary too, so its replay takes the
    differs path (Y:5330; the same ruling). The case tells its form from
    [rename-lane-differs] by Y:5329's text: "replayed at seq `<s-1>` it now
    stops before its write (exit 5: `<its last line>`), so its after-COMMIT
    steps did NOT run: `<owed>`". The WARNING carries only the child's last
    line (`pw_last_line`, `f42d2c85:lanes-edit.sh:8581`, `:8629`), and
    after the stamp proof's refusal, "the handoff at `<path>` cannot take
    Rule 3's stamp" (`:20908`), the rename's undo prints its note, "the
    rename was rolled back: ... nothing was committed" (`rename_undo`,
    `:2188`), as it does after `rename-lane`'s other refusals with 5 in
    its transaction. So the case cannot tell the stamp proof's 5 from those
    by the text, as RV20's NIT 13 asked (line ID-21's r02 saw the note): it
    requires exit 5 with that note as the last line, and `<owed>` naming
    steps (TP:3423, "names the steps that did NOT run"). And there is no
    "another change set", the differs form's words. It fails until lane 4's
    T422, whose stamp check runs before the seam on primary (tasks:1280 at
    `717ed04d`, "the stamp's checks run before the seam"; lane 3, #165
    6841366245).

    [rename-lane-differs] removes the handoff by a commit on the lanes
    origin, as lane 3 ruled (b) (#165 6851669848): a source that is not
    there passes the checks and takes Amendment 16(d)'s note, which leaves
    the row's handoff cell as it is (`9a314c09:lanes-edit.sh:24914-24915`,
    `:24981-24984`), so the change set differs first at `lanes/LANES.md`,
    since `pw_first_diff` sorts bytewise (`:8718`). A hand move onto the
    rename's new path, as TP:3424 had it, stops instead: `rename-lane`
    refuses an occupied target with 2 before it reads the source
    (`:24781-24782`), so this form's earlier passes, which checked no text,
    went by the stop path (line ID-21's r01 and r06). The case tells this
    form from the stops form by Y:5330's text: "replayed at seq `<s-1>` it
    now reaches the seam with another change set, the first path whose
    digest differs being lanes/LANES.md" (`f42d2c85:lanes-edit.sh:8587`),
    and no "now stops before its write" (RV20's finding 7). Its `<owed>`
    names a step, as the stops form's does: the pattern ends with a word
    character after "did NOT run: " (RV22's NIT 8). `pw_tail_owed` puts
    `<owed>` there (`7893339:lanes-edit.sh:10905`), and `rename-lane`'s
    row of it begins "lane <new>'s lifecycle directory moved" (`:8360`)."""
    e = estates()
    where, root = loggers(e), sidecars(e)
    extra = {"LANES_LANE_STATE_ROOT": str(root)}
    argv = (["request-handoff", LC, "--session", session_of(LC), "--no-wait"] if case.startswith("request")
            else ["rename-lane", LA, "repoA-9", "T245", "--no-github"])
    handoff = seed_handoff(e, LA) if case.startswith("rename") else ""
    _, write_id = killed(e, LA, argv, first=[where], extra=extra)
    seq = e.journal_after()[-1]["seq"]
    if case == "rename-lane-stops":
        by_hand(e, "T245: the handoff emptied by hand", "add", "--", handoff, emptied=handoff)
    elif case == "rename-lane-differs":
        by_hand(e, "T245: the handoff removed by hand", "rm", "-q", "--", handoff)
    else:
        (where / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    again = e.run(LA, argv, first=[where], extra=extra)
    if case.startswith("request"):
        assert again.code == 2 and f"seq {seq}" in again.err, again.err[-800:]
    else:
        assert again.code == 0 and again.err.count("WARNING") == 1, again.err[-800:]
        assert "owed" in mark_of(e, write_id).read_text(encoding="utf-8")
        assert (root / LA).is_dir(), "the tail ran"
    if case == "rename-lane-stops":
        stops = (re.escape(f"register write {write_id} is in the register at seq {seq}; replayed at seq {seq - 1} "
                           "it now stops before its write (exit 5: ")
                 + r"lanes-edit: the rename was rolled back: [^\n]*?nothing was committed\.[^\n]*?\), "
                 + r"so its after-COMMIT steps did NOT run: \w")
        assert re.search(stops, again.err) and "another change set" not in again.err, (
            f"the replay did not stop before its write: {again.err[-800:]}")
    if case == "rename-lane-differs":
        differs = (re.escape(f"register write {write_id} is in the register at seq {seq}; replayed at seq {seq - 1} "
                             "it now reaches the seam with another change set, the first path whose digest "
                             f"differs being {LANES_MD}, so its after-COMMIT steps did NOT run: ")
                   + r"\w")
        assert re.search(differs, again.err) and "now stops before its write" not in again.err, (
            f"the replay did not reach the seam with another change set: {again.err[-800:]}")
    assert pending(e) == []


# ------------------------------------------------------------ D8: the takeover, the call lines, the claims
@CLIENT
@pytest.mark.parametrize("when", ["before-the-send", "mid-call"])
@pytest.mark.parametrize("snapshot", ["snapshot-passes", "snapshot-fails"])
def test_a_run_killed_after_its_call_line_or_mid_call_is_taken_over_in_doubt_and_waits_past_not_after(
        estates, when, snapshot):
    """A `claim` killed after its `call` line is written ([before-the-send]:
    the shim holds the call before `psql`) or mid-call (the admin session
    holds the head row while the call runs, then rolls back). Another lane
    then claims the object. A plain rerun takes the record over, in doubt
    from its start. [snapshot-passes]: its verb refuses at the snapshot with
    2, sending no commit call, and it exits only after the database's clock
    has passed the record's `not_after`. [snapshot-fails] (Q-L2-6; R26): the
    shim fails the takeover's snapshot; with no clock of its own it waits on
    the record's (`--clock` from the newest `call` line, `--clock-age` from
    `updated_utc`), makes its lookup and ends by it, never LR011's 3. The
    journal never holds two rows for the id; the record goes."""
    e = estates()
    gate = fifo(e, "commit-1")
    argv = claim(OBJ, "--no-github")
    admin = e.hold_row_locked() if when == "mid-call" else None
    arms = [{"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(gate)}] if admin is None else []
    w = e.launch(LA, argv, arms=arms)
    if admin is None:
        held = hold_point(gate, w)
    else:
        until_seen("the shim logging the commit call's start", lambda: w.commit_calls()[:1], w)
    rec = the_record(e)
    assert len(rec["calls"]) == 1, "the call line was not written before the send"
    os.killpg(w.proc.pid, signal.SIGKILL)
    w.wait()
    write_id = rec["fields"]["write_id"].lower()
    if admin is not None:
        e.unlock(admin)
        # THE KILLED CALL'S BACKEND RUNS ON (T245n; PM33A-TRIAGE L4): its
        # client is gone, but once the head row is let go it finishes the
        # request it was sent, COMMIT included, so `landed` is read only once
        # no backend carries the write's id.
        until_seen("the killed call's backend ended", lambda: e.c.value(
            f"SELECT count(*) FROM pg_stat_activity WHERE query LIKE '%{write_id}%' "
            "AND pid <> pg_backend_pid();") == "0")
    else:
        held.close()
    not_after = rec["calls"][0].split()[2]
    landed = e.has_write(write_id)
    rival = e.run(LB, argv)
    arms = [{"mode": "fail-match", "match": SNAPSHOT_TEXT, "call": 1}] if snapshot == "snapshot-fails" else []
    again = e.run(LA, argv, arms=arms)
    assert [r["write_id"] for r in e.journal_after()].count(write_id) <= 1
    if landed:
        assert (rival.code, again.code) == (2, 0), (rival.err[-300:], again.err[-300:])
    else:
        # ITS LAST ATTEMPT'S CODE (TP:3458-3460 at `a91df2c4`): the verb's 2
        # where the snapshot passes; where it fails, the snapshot's own 69
        # (`8ba10b4e:lanes-edit.sh:9083-9087`), after F3's lookup. R26 rules
        # the wait, on the record's clock, and no code (research.md DEC-12,
        # ERR-22; T245o; PM33A-TRIAGE L5).
        code = 69 if snapshot == "snapshot-fails" else 2
        assert rival.code == 0 and again.code == code, again.err[-800:]
        assert snapshot == "snapshot-fails" or again.commit_calls() == []
        assert db_past(e, not_after), "the takeover exited before the record's not_after"
    assert "LR011" not in again.err
    assert pending(e) == []


@CLIENT
@pytest.mark.parametrize("case", ["before-the-send", "lost-turn", "refusal", "in-doubt"])
def test_the_pending_records_call_lines_are_written_before_the_send_and_dropped_only_for_a_call_that_did_not_commit(
        estates, case):
    """[before-the-send]: while the shim holds the first commit call, the
    record already holds its line. [lost-turn]: after a 40001 from a rival's
    commit, the record read while the next call is held holds one line, the
    next call's, with base n+1. [refusal]: after a refusal the record is
    gone. [in-doubt]: after a call in doubt it keeps the line, and the
    attempt directory keeps the files `snapshot` and `files`, and
    `preimages/`, a directory (B19 tasks:1104), where the attempt made one:
    only a write with a lane-state sidecar does (`lane_state_preimage`,
    `c8acf67c:lanes-edit.sh:23056`), and a `NOTE` line has none (T245f;
    lane 4's triage, #165 6833813092). `<dir>` is the line's rest after its
    four first fields (pending-record.md §3.2)."""
    e = estates()
    if case == "before-the-send":
        gate = fifo(e, "commit-1")
        w = e.launch(LA, note(LA, case), arms=[{"mode": "hold", "match": "commit_write", "call": 1,
                                                 "fifo": str(gate)}])
        held = hold_point(gate, w)
        assert len(the_record(e)["calls"]) == 1
        held.close()
        assert w.wait() == 0
    elif case == "lost-turn":
        gates = fifo(e, "commit-1"), fifo(e, "commit-2")
        w = e.launch(LA, note(LA, case), arms=[
            {"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(gates[0])},
            {"mode": "hold", "match": "commit_write", "call": 2, "fifo": str(gates[1])}])
        first = hold_point(gates[0], w)
        base = int(the_record(e)["calls"][0].split()[0])
        assert e.run(LB, note(LB, "the rival")).code == 0
        first.close()
        second = hold_point(gates[1], w)
        calls = the_record(e)["calls"]
        assert len(calls) == 1 and int(calls[0].split()[0]) == base + 1, calls
        second.close()
        assert w.wait() == 0
    elif case == "refusal":
        assert e.run(LB, claim(OBJ, "--no-github")).code == 0
        w = e.run(LA, claim(OBJ, "--no-github"))
        assert w.code == 2 and pending(e) == []
    else:
        w, _, _ = exit3(e, LA, note(LA, case))
        calls = the_record(e)["calls"]
        assert len(calls) == 1
        attempt = Path(calls[0].split(" ", 4)[4])
        assert all((attempt / name).is_file() for name in ("snapshot", "files")), sorted(attempt.iterdir())
        assert not (attempt / "preimages").exists() or (attempt / "preimages").is_dir(), sorted(attempt.iterdir())


@CLIENT
@pytest.mark.parametrize("case", ["take-0", "take-1", "two-reruns"])
def test_a_pending_record_is_owned_through_numbered_claim_files_and_two_reruns_never_both_take_it(estates, case):
    """[take-0]: a run with no record creates `<d>.take.0`, read while the
    shim holds the first commit call, holding the run's pid, start time,
    host, container and UTC. [take-1]: after a kill a rerun creates
    `<d>.take.1`. [two-reruns]: two printed reruns under `LANES_WRITE_ID`
    released together against a dead owner, in 10 rounds: one create of
    `<d>.take.1` succeeds, one comment and one row each round, both exit 0.
    After a run's end no record and no claim file remains."""
    e = estates()
    if case == "take-0":
        gate = fifo(e, "commit-1")
        w = e.launch(LA, note(LA, case), arms=[{"mode": "hold", "match": "commit_write", "call": 1,
                                                 "fifo": str(gate)}])
        held = hold_point(gate, w)
        takes = take_files(e)
        assert [t.rsplit(".", 1)[1] for t in takes] == ["0"], takes
        text = (e.state / PENDING / takes[0]).read_text(encoding="utf-8")
        assert str(w.proc.pid) in text or "pid" in text, text
        held.close()
        assert w.wait() == 0
    elif case == "take-1":
        argv = note(LA, case)
        killed(e, LA, argv)
        assert [t.rsplit(".", 1)[1] for t in take_files(e)] == ["0"]
        assert e.run(LA, argv).code == 0
    else:
        where = loggers(e)
        for k in range(10):
            obj = f"opensoft/r9#{100 + k}"
            argv = claim(obj)
            _, write_id = killed(e, LA, argv, first=[where])
            generation = e.c.switch()["generation"]
            (e.root / f"round-{k}").mkdir()
            barrier = Barrier(e.root / f"round-{k}", 2)
            before = len(comments(where))
            pair = [e.launch(LA, argv, barrier=barrier, first=[where],
                             extra={"LANES_WRITE_ID": write_id, "LANES_WRITE_GENERATION": generation})
                    for _ in range(2)]
            barrier.release()
            assert [p.wait() for p in pair] == [0, 0], [p.err[-300:] for p in pair]
            assert len(comments(where)) - before == 1, f"round {k}: {len(comments(where)) - before} comments"
            assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1
    assert pending(e) == [] and take_files(e) == []


# ------------------------------------------------------------ AT-F34: the tail, once
#: [lr006]'s seam cap with the kept child gone (`learnt`): 10 s leaves the next
#: attempt's child 9 s to reach its seam, and holds its commit call about
#: 4 to 6 s where the gap between the two children's seams is runs r5's and
#: r7b's 7 s and 5.4 s (T245i, T245j).
LR006_SEAM_CAP_S = 10


def learnt(e: Estate, way: str, where: Path, *, gone: bool = False, script: Optional[Path] = None) -> Writer:
    """A `claim` whose first commit call committed while in doubt, learnt by
    [snapshot] (`after`, then the next snapshot), [lr006] (the first call
    forked and held as AT-F3's orphan, the shim exiting 2 at once; the
    orphan let go once the next attempt's snapshot has ended, having read
    the write absent, and committed before that attempt's commit call, which
    so gets LR006, as AT-LR006-1 orders them) or [lookup] (`after`, the next
    snapshot failed, so AT-F3's lookup finds it). The call that learns it is
    held; with `gone`, until the kept child's `seam.out` says `none` under
    `LANES_REGISTER_SEAM_CAP_S=3`, or `LR006_SEAM_CAP_S` for [lr006].

    [lr006]'s timing (T245f, T245i, T245j). The orphan carries the first
    snapshot's clock plus 10 s as its `not_after` (`lanes-index`'s
    `not_after=`), so it must commit within about 10 s of that snapshot:
    let go only once the next commit call was held, it ended LR008 in line
    ID17's run r7b, at 11 s on py-bench. With `gone`, the next attempt's
    child must reach its seam before the parent's wait ends, 1 s before the
    kept child's cap (Y:5004; `c8acf67c:lanes-edit.sh:9192`), and its commit
    call, sent at that seam and held until the kept child's `none`, should
    stay under its own 8 s timer, `C`: the cap must exceed the gap between
    the two children's seams by more than 1 s, and by less than about `C`.
    Runs r5 and r7b measured that gap at about 7 s and 5.4 s, so 3 s and 7 s
    were short and 12 s near `C`. Where the hold does pass `C`, that call is
    in doubt too, and the next snapshot learns the write instead."""
    gate = fifo(e, f"learn-{way}")
    if way == "lr006":
        orphan = fifo(e, "orphan")
        arms = [{"mode": "fork", "match": "commit_write", "call": 1, "fifo": str(orphan), "exit": True},
                {"mode": "hold", "match": "commit_write", "call": 2, "fifo": str(gate)}]
    elif way == "snapshot":
        arms = [AFTER, {"mode": "hold", "match": SNAPSHOT_TEXT, "call": 2, "fifo": str(gate)}]
    else:
        arms = [AFTER, {"mode": "fail-match", "match": SNAPSHOT_TEXT, "call": 2},
                {"mode": "hold", "match": "find_write", "call": 1, "fifo": str(gate)}]
    extra = {"LANES_REGISTER_SEAM_CAP_S": str(LR006_SEAM_CAP_S if way == "lr006" else 3)} if gone else {}
    w = e.launch(LA, claim(OBJ), first=[where], arms=arms, extra=extra, script=script)
    if way == "lr006":
        until_seen("the next attempt's snapshot ended", lambda: len(w.snapshot_calls()) >= 2
                   and w.snapshot_calls()[1]["call"] in w.ends(), w)
        hold_point(orphan, w).close()
        until_seen("the orphan's commit", lambda: e.journal_after(), w)
    held = hold_point(gate, w)
    if gone:
        until_seen("the kept child's seam.out saying none", lambda: any(
            p.read_text(encoding="utf-8").strip() == "none" for p in e.state.rglob("seam.out")), w)
    held.close()
    return w


@CLIENT
@pytest.mark.parametrize("way", ["snapshot", "lr006", "lookup"])
def test_a_call_in_doubt_that_committed_runs_its_tail_once_from_the_kept_child(estates, way):
    """The call in doubt committed, learnt by [snapshot], [lr006] or
    [lookup] (`learnt`). The fake `gh` comments once, after the COMMIT, and
    the `seam.out` files it saw then hold the kept child's `tail`, once,
    and no other child's anything but `none`; the mark keeps `done`; exit
    0, one row. The seams are read as the comment saw them, during the run
    (the logging stand-in reads every `seam.out` under the state directory
    at each call): at its end the run removes its own `<d>/<run>/`, its
    attempt directories and their `seam.out` with it (B19 tasks:1179, T415;
    T245e; lane 4's triage, #165 6833813092)."""
    e = estates()
    where = loggers(e)
    w = learnt(e, way, where)
    assert w.wait() == 0, w.err[-800:]
    write_id = one_entry(e, w)
    said = comments(where)
    assert len(said) == 1, said
    seams = sorted(text.strip() for text in said[0]["seams"].values())
    assert seams.count("tail") == 1 and set(seams) <= {"tail", "none"}, seams
    assert "done" in mark_of(e, write_id).read_text(encoding="utf-8")


@CLIENT
@pytest.mark.parametrize("way", ["snapshot", "lr006", "lookup"])
def test_with_the_kept_child_gone_a_replay_runs_the_tail_once(estates, way):
    """The same three, with the cap ending the kept child first. The run
    replays at `s-1` (lanes-index's `register snapshot --tree <dir> --at
    <s-1>`, which the shim does not see, so its count is lane 4's to log)
    and sends no commit call after it; the fake `gh` is called once."""
    e = estates()
    where = loggers(e)
    w = learnt(e, way, where, gone=True)
    assert w.wait() == 0, w.err[-800:]
    one_entry(e, w)
    assert len(comments(where)) == 1, comments(where)


@CLIENT
def test_two_matching_calls_of_one_change_set_leave_the_replays_tail_owed(estates):
    """NIT-4 (b) (lane 3, #165 6851422597; T418 `91bfa229`): a takeover whose
    record holds two `call` lines whose `<files>` is the entry's, and whose
    own commit never answered `committed`, does not replay. Y:5317 takes
    "the `call` line whose `<files>` is the entry's", one line. Two are
    resends of one change set whose snapshots read the same database
    second; their `preimages/` need not agree, and which of their calls
    committed is not known. So the tail is owed: one WARNING naming the two
    lines, exit 0, the mark `owed <utc>`, the record removed, no comment,
    and no replay child, so `claim`'s Rule 1 reads (`gh issue view`) stay
    at the killed run's count. T418 ends it before `pw_wdir_ok` and the
    `replayed` token (`91bfa229:lanes-edit.sh:8470-8471`).

    No fixture makes two such calls today: the `[lr006]` fixture moves the
    clock past a second (TP:6981-6982). So the case writes the second line
    itself. The killed `claim` leaves one `call=` line and no `tail`
    (`killed`). The case adds a line with the same `<base> <clock>
    <not_after> <files>`, naming its own attempt directory, `<run>/2`, as a
    resend in the same second would, since matching lines are never
    byte-identical (lane 3, the same post). That directory holds a copy of
    the first's `snapshot`, `files` and `preimages` (Y:5177), mode 0700, so
    it passes `pw_wdir_ok`, and the record's `attempts` goes up by one. The
    rerun's snapshot finds the write, and with the killed child gone
    `pw_tail` goes to the replay (`:8367`).

    It fails until T418 `91bfa229`. Before NIT-4 the replay took the last
    matching line (`9a314c09:lanes-edit.sh:8546`), so it replayed from the
    second directory and ran the tail: one comment and `tail=done`. Its
    name holds `tail`, so T418's verify selects it and T417's, which
    leaves out `tail`, does not (tasks:1231 and :1199 at `94fab177`).

    The exception, where the run whose own commit answered `committed`
    keeps that call's line (Y:5306), is not built here. It needs that run's
    own in-memory `call` lines to hold a second matching line, from an
    earlier call of its own in the same database second, with its kept
    child gone. A line written into the record file never reaches a live
    run, and no fixture pins two calls to one second."""
    e = estates()
    where = loggers(e)
    argv = claim(OBJ)
    _, write_id = killed(e, LA, argv, first=[where])
    seq = e.journal_after()[-1]["seq"]
    rec = the_record(e)
    assert len(rec["calls"]) == 1 and "tail" not in rec["fields"], rec
    base, clock, not_after, files, first = rec["calls"][0].split(None, 4)
    first_dir = Path(first.strip())
    assert first_dir.name.isdigit() and (first_dir / "files").is_file(), f"{first_dir} is not a kept call's directory"
    second = first_dir.parent / str(int(first_dir.name) + 1)
    second.mkdir(mode=0o700)
    second.chmod(0o700)
    kept = [first_dir / "snapshot", first_dir / "files", first_dir / "preimages"]
    if kept[2].is_dir() and not kept[2].is_symlink():
        kept += sorted(kept[2].rglob("*"))
    for src in kept:
        if src.is_symlink() or not src.exists():
            continue
        dst = second / src.relative_to(first_dir)
        if src.is_dir():
            dst.mkdir(mode=0o700, parents=True, exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            dst.chmod(src.stat().st_mode & 0o777)
    text = re.sub(r"(?m)^attempts=(\d+)$", lambda m: f"attempts={int(m.group(1)) + 1}",
                  rec["path"].read_text(encoding="utf-8"))
    rec["path"].write_text(f"{text}call={base} {clock} {not_after} {files} {second}\n", encoding="utf-8")
    assert len(the_record(e)["calls"]) == 2
    killed_reads = len(gh_reads(where))
    again = e.run(LA, argv, first=[where])
    # The one WARNING must be the owed tail's own, so this assert alone tells
    # the build before NIT-4, whose replay printed the comment's WARNING
    # instead, from T418's (lane 2's RV23 NIT 12).
    warned = [line for line in again.err.splitlines() if "WARNING" in line]
    assert (again.code == 0 and again.err.count("WARNING") == 1
            and "2 call lines of its pending record" in warned[0]), (
        f"not one WARNING, the owed tail's: {again.err[-800:]}")
    owed = (re.escape(f"register write {write_id} is in the register at seq {seq}; 2 call lines of its pending "
                      "record sent the entry's change set")
            + r"[^\n]*?" + re.escape("so it cannot be replayed, so its after-COMMIT steps did NOT run: ") + r"\w")
    assert re.search(owed, again.err) and "replayed at seq" not in again.err, (
        f"the replay was not left owed for two matching call lines: {again.err[-800:]}")
    assert comments(where) == [] and len(gh_reads(where)) == killed_reads, (
        f"a replay ran: {len(comments(where))} comment(s), {len(gh_reads(where)) - killed_reads} new Rule 1 read(s)")
    mark = mark_of(e, write_id).read_text(encoding="utf-8")
    assert re.search(r"(?m)^tail=owed ", mark), f"the mark does not hold owed: {mark!r}"
    assert pending(e) == []


@CLIENT
def test_a_replay_of_request_handoff_types_into_no_pane(estates):
    """With the kept child gone, `request-handoff`'s replay runs its tail
    with no `guard_type`: the fake `tmux` logs no `send-keys`, and the poll
    runs."""
    e = estates()
    where = loggers(e)
    argv = ["request-handoff", LC, "--session", session_of(LC), "--wait", "2"]
    killed(e, LA, argv, first=[where])
    before = len(tool_calls(where, "tmux"))
    again = e.run(LA, argv, first=[where], extra={"LANES_POLL_SECONDS": "1"})
    assert again.code in (0, 2), again.err[-800:]
    later = tool_calls(where, "tmux")[before:]
    assert not [c for c in later if "send-keys" in c["argv"]], later
    assert later, "the poll never ran"


@CLIENT
def test_a_rerun_that_finds_tail_sent_runs_no_tail_and_writes_the_done_mark(estates):
    """The record holds `tail=sent` from a run killed after `sent` and
    before the child's exit. A plain rerun takes it over, finds its id at
    the snapshot and `tail` sent, runs no tail, writes the mark with `sent`,
    removes the record, exits 0, and says the steps may have run at the
    record's UTC in its pid."""
    e = estates()
    where = loggers(e)
    argv = claim(OBJ)
    _, write_id = killed(e, LA, argv, first=[where])
    rec = the_record(e)
    utc = e.utc()
    with rec["path"].open("a", encoding="utf-8") as f:
        f.write(f"tail=sent {e.journal_after()[-1]['seq']} {utc}\n")
    again = e.run(LA, argv, first=[where])
    assert again.code == 0 and comments(where) == [], again.err[-800:]
    assert "sent" in mark_of(e, write_id).read_text(encoding="utf-8")
    assert pending(e) == [] and utc in again.err, again.err[-800:]


def replay_copy(e: Estate, control: Path) -> Path:
    """AT-F34's test copy (TP:6962-6965): a `lanes-edit.sh` whose runs under
    the seam's scratch flag read `control` once the test writes it: `stops`
    exits 1 before `ready`, and `differs` adds one more word to the line, so
    a replay stops or reaches the seam with another change set."""
    text = e.lanes_edit.read_text(encoding="utf-8")
    shebang, rest = text.split("\n", 1)
    quoted = "'" + str(control).replace("'", "'\\''") + "'"
    hook = (f'if [ -n "${{LANES_REGISTER_SCRATCH:-}}" ] && [ -f {quoted} ]; then\n'
            f'  case "$(cat {quoted})" in\n'
            '    stops) echo "T245: the replay stops" >&2; exit 1 ;;\n'
            '    differs) set -- "$@" "T245 differs" ;;\n'
            '  esac\nfi\n')
    copy = e.bindir / "lanes-edit-t245.sh"
    copy.write_text(shebang + "\n" + hook + rest, encoding="utf-8")
    copy.chmod(0o755)
    return copy


@CLIENT
@pytest.mark.parametrize("case", ["stops", "differs"])
def test_a_replay_that_stops_or_differs_runs_no_tail_and_warns(estates, case):
    """With the kept child gone and the test copy's control file written,
    the replay exits 1 before `ready` ([stops]) or reaches the seam with one
    more word ([differs]). The run exits 0 with one WARNING naming the seq;
    the fake `gh` is not called, and the record is removed."""
    e = estates()
    where = loggers(e)
    control = e.root / "t245-replay"
    script = replay_copy(e, control)
    argv = claim(OBJ)
    killed(e, LA, argv, first=[where], script=script)
    seq = e.journal_after()[-1]["seq"]
    control.write_text(case + "\n", encoding="utf-8")
    again = e.run(LA, argv, first=[where], script=script)
    assert again.code == 0 and again.err.count("WARNING") == 1 and str(seq) in again.err, again.err[-800:]
    assert comments(where) == [] and pending(e) == []


@CLIENT
@pytest.mark.parametrize("case", ["done-mark", "this-host", "other-host"])
def test_a_run_with_no_record_runs_no_tail_and_names_it(estates, case):
    """A rerun under `LANES_WRITE_ID` of a write committed and settled, with
    no record here, and so with its `LANES_WRITE_GENERATION` (an id with no
    generation and no record is refused 2 before any call: pending-record.md
    §5.2, R08; T245d), exits 0 and runs no tail. [done-mark]: it says what the
    mark's `tail` says, that the steps ran at `<utc>` in pid `<p>` (TP:7048-7049
    at `a91df2c4`), the mark's `tail=done <s> <rc> <utc>` and `pid=` (T245i;
    line ID17's run r3 printed "its after-COMMIT steps ran at <utc> in pid
    <p>"); [this-host]: with the mark removed and
    `journal.workstation` this host (`found`'s `workstation=`), it says the
    steps may already have run here, naming the entry's UTC from `utc=`;
    [other-host]: the write made from ws2, it names ws2 and says to rerun
    there if that run ended 3."""
    e = estates()
    where = loggers(e)
    argv = claim(OBJ)
    extra = {"LANES_WORKSTATION": "ws2"} if case == "other-host" else {}
    w = e.run(LA, argv, first=[where], extra=extra)
    assert w.code == 0
    write_id = w.write_ids()[-1]
    said = mark_of(e, write_id).read_text(encoding="utf-8")
    if case != "done-mark":
        mark_of(e, write_id).unlink()
    before = len(comments(where))
    again = e.run(LA, argv, first=[where], extra={"LANES_WRITE_ID": write_id,
                                                  "LANES_WRITE_GENERATION": e.c.switch()["generation"]})
    assert again.code == 0 and len(comments(where)) == before, again.err[-800:]
    if case == "other-host":
        assert "ws2" in again.err and "rerun" in again.err, again.err[-800:]
    elif case == "this-host":
        assert "may already have run" in again.err, again.err[-800:]
    else:
        mark = dict(line.split("=", 1) for line in said.splitlines() if "=" in line)
        tail = mark.get("tail", "").split()
        assert tail[:1] == ["done"] and len(tail) == 4, f"the mark's tail is not done <s> <rc> <utc>: {said}"
        assert f"ran at {tail[3]}" in again.err and f"pid {mark.get('pid')}" in again.err, (
            f"the text does not say the steps ran at {tail[3]} in pid {mark.get('pid')}: {again.err[-800:]}")


# ------------------------------------------------------------ D8: a `tail` record a takeover cannot use
#: The maximum age these cases set (`LANES_REGISTER_PENDING_MAX_AGE_S`, Y:5207),
#: so the time the refusal prints, the record's `updated_utc` plus the age, is
#: the test's to compute, in the record's own UTC form.
TAIL_AGE_S = 600
TAIL_AGE = {"LANES_REGISTER_PENDING_MAX_AGE_S": str(TAIL_AGE_S)}
UTC_FORM = "%Y-%m-%dT%H:%M:%SZ"


@CLIENT
@pytest.mark.parametrize("case", ["no-found", "tail-of-another-form"])
def test_a_tail_record_a_takeover_cannot_use_is_refused_2_and_kept(estates, case):
    """A `claim` ended 3 by `no-reconnect`, and its record given a `tail`
    by hand (R-F13c-23; lane 3's batch 8, Q46 and Q34). [no-found]: its
    call never landed (`before`), and the record holds `tail=sent <s> <utc>`,
    as a damaged record does, so the takeover's first snapshot answers with
    no `found=`. A plain rerun refuses 2, sending no commit call and running
    no tail, and leaves the record as it was. Its text gives Y:5211-5213's
    effect check and, where the effect is not there, the same command again
    with no `LANES_WRITE_ID` once the record is
    `LANES_REGISTER_PENDING_MAX_AGE_S` past its `updated_utc`, printing that
    time, and never `LANES_WRITE_ID=new`, which replaces only a record of
    another generation (Y:5215). With `updated_utc` set past the age, that
    rerun writes anew by Y:5207's aged plan: it warns, prints the lookup of
    the record's id, and commits once under a new id, its tail run once.
    [tail-of-another-form] (Q34): its call landed (`after`), so a snapshot
    would find it, and the record's `tail` is `owed <utc>`, a done mark's
    value and neither Y:5179 form, `sent <s> <utc>` or `done <s> <rc>
    <utc>`: a record that cannot be read, T412's 2, with no commit call and
    no tail, the record kept."""
    e = estates()
    where = loggers(e)
    argv = claim(OBJ)
    arm = dict(NO_RECONNECT, **{"as": "before" if case == "no-found" else "after"})
    w = e.run(LA, argv, arms=[arm], first=[where])
    assert w.code == 3 and comments(where) == [], f"exit {w.code}, not 3: {w.err[-800:]}"
    rec = the_record(e)
    write_id = rec["fields"]["write_id"].lower()
    assert e.has_write(write_id) == (case != "no-found"), f"[{case}]: the first call's outcome is not the case's"
    tail = f"sent {e.c.head() + 1} {e.utc()}" if case == "no-found" else f"owed {e.utc()}"
    with rec["path"].open("a", encoding="utf-8") as f:
        f.write(f"tail={tail}\n")
    kept, journal = rec["path"].read_bytes(), e.journal_after()
    again = e.run(LA, argv, first=[where], extra=TAIL_AGE)
    assert again.code == 2, f"[{case}] the takeover exited {again.code}, not 2: {again.err[-800:]}"
    assert again.commit_calls() == [] and comments(where) == [], again.err[-800:]
    assert rec["path"].read_bytes() == kept, f"[{case}] the refused run changed the record"
    assert e.journal_after() == journal
    if case == "tail-of-another-form":
        assert "cannot be read" in again.err, f"the refusal is not T412's 2: {again.err[-800:]}"
        return
    assert f"lanes-edit.sh history {LA} --since" in again.err or f"lanes-edit.sh register-row {LA}" in again.err
    aged_at = (datetime.datetime.strptime(rec["fields"]["updated_utc"], UTC_FORM)
               + datetime.timedelta(seconds=TAIL_AGE_S)).strftime(UTC_FORM)
    assert aged_at in again.err, f"the text does not print {aged_at}, updated_utc plus the age: {again.err[-800:]}"
    assert "LANES_WRITE_ID=new" not in again.err and not WRITE_ID_SAID.search(again.err), (
        f"the text offers a LANES_WRITE_ID rerun: {again.err[-800:]}")
    set_field(rec["path"], "updated_utc", e.utc((TAIL_AGE_S + 60) / 60))
    anew = e.run(LA, argv, first=[where], extra=TAIL_AGE)
    assert anew.code == 0, f"the rerun past the age exited {anew.code}: {anew.err[-800:]}"
    assert anew.write_ids() and write_id not in anew.write_ids(), anew.err[-800:]
    assert "WARNING" in anew.err and f"--write-id {write_id}" in anew.err, anew.err[-800:]
    ids = [r["write_id"] for r in e.journal_after()]
    assert ids.count(write_id) == 0 and ids.count(anew.write_ids()[-1]) == 1, ids
    assert len(comments(where)) == 1 and pending(e) == [], (comments(where), pending(e))


# ------------------------------------------------------------ GB §4.3: the texts for 3 (runs here)
#: Each site's file, and the clause it must hold: the writer's exit table's
#: row 3 primary clause (lane 4's T417, R21); `lane-rename`'s header and
#: default arm (T433); `lane-worktrees`' note (T434).
TEXTS_FOR_3 = {"exit-table": "lanes-edit.sh", "lane-rename": "lane-rename", "lane-worktrees": "lane-worktrees"}


@pytest.mark.parametrize("site", list(TEXTS_FOR_3))
def test_the_texts_for_3_say_may_not_be_written_and_relay_the_writers_rerun(site):
    """On exit 3 on primary each site prints D8's text for 3, byte for byte
    with its backticks, relays the writer's printed rerun verbatim, and never
    prints its own hint, "was NOT added" or "NOT WRITTEN". Read from the
    scripts, with no engine: each must hold D8's text and none of the
    refused hints, where its exit-3 arm stands. A site may split the text
    over adjacent string literals on consecutive source lines (T434's
    `lane-worktrees` does, in one parenthesised Python string), so the
    search also reads the file with each such seam joined. The refused hints
    are looked for in what a site can print, so its full-line comments are
    left out there: one may name a refused hint to forbid it, as T434's
    `lane-worktrees:192` does at 3a5b303f."""
    from sql_register_helpers import REPO
    path = REPO / TEXTS_FOR_3[site]
    assert path.is_file(), f"{path.name} is not in the code root"
    raw = path.read_text(encoding="utf-8")
    views = [raw, joined_literals(raw)]
    forms = [D8_TEXT_3, D8_TEXT_3.replace("`", "\\`")]
    assert any(form in text for text in views for form in forms), (
        f"{path.name} does not hold D8's text for 3: {D8_TEXT_3!r}")
    for refused in ("was NOT added", "NOT WRITTEN"):
        for text in map(uncommented, views):
            near = [m.start() for form in forms for m in re.finditer(re.escape(form), text)]
            assert not any(refused in text[max(0, k - 400):k + 400] for k in near), (
                f"{path.name} prints {refused!r} beside D8's text for 3")


def joined_literals(text: str) -> str:
    """`text` with each seam of two adjacent string literals on consecutive
    source lines joined: a closing quote, the line's end and the next line's
    indent, and an opening quote of the same kind, are dropped, as Python
    joins `("a " NEWLINE "b")`."""
    return re.sub(r"""(["'])[ \t]*\n[ \t]*\1""", "", text)


def uncommented(text: str) -> str:
    """`text` without its full-line `#` comments, which a site never prints."""
    return re.sub(r"(?m)^[ \t]*#.*\n?", "", text)


# ============================================================ PHASE W (and N): AT-F3 (T246)
#
# A WRITE IN DOUBT AT THE DEADLINE (AT-F3, TP:5564-5780). AT-F3's estate is
# test 12's half-open case at `LANES_REGISTER_DEADLINE_S=1` (`HalfOpen`): the
# first commit call lost by `before`; the test's session, as `lanes_w_fx`
# with `idle_in_transaction_session_timeout = 0`, replaying that call's script
# without its COMMIT, ended in a `;` that `psql` sends (`without_commit`,
# T244c), so it holds the head row with the row inserted; the
# next snapshot held until the replay returned; and the lookup's first try
# held on a FIFO while the case decides. `<n>` is the first call's
# `not_after`. Its timer is D9's 9 s (open point 37).
#
# AT MOST ONE RETRY (TP:5634-5636): at a 1 s deadline the lost first call
# may end past it, and then no attempt starts and the writer goes straight
# to the lookup, with no next snapshot (T246c; on `pair-m23t` `c8acf67c` the
# shim logged the lookup's two tries after the lost call, and no snapshot).
# So `HalfOpen` waits for the writer's next call after its first commit
# call, that snapshot or the lookup's first try, and releases the snapshot's
# hold only where the snapshot came.
#
# THE TRIES (R26, lane 4's answer to 40): each try starts at least 0.75 s
# after the last one's start, never before the last one has ended, the k-th
# at least k - 1.25 s after the first's, and any up to the window's 10 s
# mark, on the monotonic clock. The 0.75 s and 1.25 s are lane 2's (NOTES
# question 34); the exact spacing is lane 1's virtual-clock check (T114).
# The try endings the shim cannot make (57014, an exit 1, a signal, an exit 3
# with no SQLSTATE, an exit 0 whose answer cannot be read; ERR-50, R-F11-5)
# come from `_ANSWER`, a stand-in put first on `PATH` that answers one
# lookup try as taught and hands every other call on.
#
# TOO EARLY (R26, 36): `[too-early]` takes over a record written on another
# host, so the run has no clock to age and calls at once: LR011's 3, the
# record kept. On this host the takeover waits (T245's `[snapshot-fails]`).
# The killed run's claim names that host, so it counts as live for the
# seam's cap, 120 s, from the later of its `utc` and the record's
# `updated_utc` (Y:5220; pending-record.md §4.3), and the rerun sets the
# cap's test variable, `LANES_REGISTER_SEAM_CAP_S`, to 1 s to take it over
# at once (T246d; lane 4's triage, #165 6833813092).
#
# They FAIL UNTIL L1-A6, L1-A12 and L4-B5 land. Without PostgreSQL 16 each
# skips; the direct calls (LR011 at once, LR008's engine half) are phase N on
# T222's clones.

DEADLINE = {"LANES_REGISTER_DEADLINE_S": "1"}
PAST = "2000-01-01 00:00:00+00"
ENTRY_IN_SCRIPT = re.compile(r"'((?:[^']|'')*)'::jsonb")
_HALVES = itertools.count(1)

_ANSWER = r'''#!/usr/bin/env python3
# T246's answer stand-in: the k-th call carrying MATCH answered as taught,
# sending nothing; every other call handed to the next psql on PATH.
import json, os, signal, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
rule = json.load(open(os.path.join(HERE, "answer.json"), encoding="utf-8"))
args = sys.argv[1:]
nxt = next(os.path.join(d, "psql") for d in os.environ["PATH"].split(os.pathsep)
           if d and os.path.abspath(d) != HERE and os.access(os.path.join(d, "psql"), os.X_OK))
if args == ["--version"]:
    os.execv(nxt, [nxt] + args)
data = sys.stdin.buffer.read()
if rule["match"].encode() in data:
    count = os.path.join(HERE, "answer.count")
    seen = int(open(count).read()) + 1 if os.path.exists(count) else 1
    open(count, "w").write(str(seen))
    if seen == rule.get("call", 1):
        with open(os.path.join(HERE, "answer.log"), "a", encoding="utf-8") as log:
            log.write(json.dumps({"t": __import__("time").time(), "call": seen}) + "\n")
        sys.stdout.write(rule.get("stdout", ""))
        sys.stderr.write(rule.get("stderr", ""))
        sys.stdout.flush()
        sys.stderr.flush()
        if rule.get("signal"):
            os.kill(os.getpid(), getattr(signal, "SIG" + rule["signal"]))
        sys.exit(rule.get("exit", 0))
done = subprocess.run([nxt] + args, input=data, capture_output=True)
sys.stdout.buffer.write(done.stdout)
sys.stderr.buffer.write(done.stderr)
sys.exit(done.returncode if done.returncode >= 0 else 128 - done.returncode)
'''

#: The try endings with no answer (ERR-50; lane 3, #165 6755922262; R-F11-5).
NO_ANSWER = {
    "57014": {"exit": 3, "stderr": "ERROR:  57014: canceling statement due to statement timeout\n"},
    "exit-1": {"exit": 1, "stderr": "psql: error: out of memory\n"},
    "signal": {"signal": "KILL"},
    "exit-3-no-sqlstate": {"exit": 3, "stderr": "ERROR:  the lookup failed\n"},
    "unreadable-exit-0": {"exit": 0, "stdout": "not an answer\n"},
}


def answering(e: Estate, rule: dict) -> Path:
    where = e.root / f"answer-{next(_HALVES)}"
    where.mkdir()
    (where / "psql").write_text(_ANSWER, encoding="utf-8")
    (where / "psql").chmod(0o755)
    (where / "answer.json").write_text(json.dumps(dict(rule, match="find_write")), encoding="utf-8")
    return where


def another_writes_script(script: str) -> str:
    """The call's script with the entry's `args_sha256` changed: another
    write's entry under the same id (AT-F3's [another-write])."""
    m = ENTRY_IN_SCRIPT.search(script, script.find("commit_write("))
    entry = json.loads(m.group(1).replace("''", "'"))
    entry["journal"]["args_sha256"] = sha256(b"another write, T246")
    text = json.dumps(entry, ensure_ascii=False, separators=(",", ":")).replace("'", "''")
    return script[:m.start()] + "'" + text + "'::jsonb" + script[m.end():]


class HalfOpen:
    """AT-F3's estate (see the section's head): `w`, the writer; `session`,
    the old connection; `write_id`; `n`, the first call's `not_after`; and
    `held`, the lookup's first try on its FIFO, where `hold_lookup`."""

    def __init__(self, e: Estate, argv: Optional[Sequence[str]] = None, *, arms: Sequence[dict] = (),
                 hold_lookup: bool = True, alter=None, first: Sequence[Path] = (), extra: Optional[dict] = None):
        k = next(_HALVES)
        self.e, self.first = e, list(first)
        self.argv = list(argv or note(LA, f"F3 {k}"))
        snap, look = fifo(e, f"f3-snapshot-{k}"), fifo(e, f"f3-lookup-{k}")
        held = [{"mode": "hold", "match": "find_write", "call": 1, "fifo": str(look)}] if hold_lookup else []
        self.w = e.launch(LA, self.argv, first=first, extra=dict(DEADLINE, **(extra or {})),
                          arms=[BEFORE, {"mode": "hold", "match": SNAPSHOT_TEXT, "call": 2, "fifo": str(snap)},
                                *held, *arms])
        call = until_seen("the first commit call", lambda: self.w.commit_calls()[:1], self.w)[0]
        # The replay waits for that call's end. The shim logs a call at its
        # start, before the real `psql` runs, so a replay sent then could take
        # the head row first: the writer's own `commit_write` then waits out
        # the commit row's 2000 ms `lock_timeout` and ends 55P03, a lost turn,
        # and with the 1 s deadline past the run ends 75, "register busy",
        # before any next call (round 6h's `[connect]`; lane 2's TR21, 2c).
        # The `before` arm's lost call ends 2, its backend gone and its
        # transaction rolled back, so the head row is free for the replay.
        # THAT RACE IS READ FROM THE CODE, NOT SEEN: no run has caught it, and
        # the runs since the wait came in (ID-25's four) show only that it
        # keeps the flow, not that it closed the race. The first commit call
        # is always the `before` arm's, since this estate puts BEFORE first
        # among every writer's arms, so the 2 asserted here holds for each
        # caller (lane 2's RV23 NIT 11).
        ended = until_seen("the first commit call's end", lambda: self.w.ends().get(call["call"]), self.w)
        assert ended.get("exit") == 2, f"the first commit call ended {ended}, not 2, the `before` arm's lost call"
        script = without_commit(call["stdin"])
        assert "commit_write" in script and script.rstrip().endswith(";") and not script.rstrip().endswith("\\;"), (
            f"the replay does not end in a `;` that psql sends: {script[-80:]!r}")
        self.session = e.c.db.session(WRITER_LOGIN, "t246-held")
        self.session.stdin.write("SET idle_in_transaction_session_timeout = 0;\n"
                                 + (alter(script) if alter else script).rstrip() + "\n")
        self.session.stdin.flush()
        until_seen("the replay holding the head row", lambda: e.c.value(
            "SELECT count(*) FROM pg_stat_activity WHERE application_name = 't246-held' "
            "AND state = 'idle in transaction';") == "1", self.w)
        self.write_id, self.n = self.w.write_ids()[0], first_not_after(self.w)
        after = until_seen("the writer's next call after its first commit call: its next snapshot, held, "
                           "or its lookup's first try", self.next_call, self.w)
        if SNAPSHOT_TEXT in (after.get("stdin") or ""):
            hold_point(snap, self.w).close()
        self.held = hold_point(look, self.w) if hold_lookup else None

    def next_call(self) -> Optional[dict]:
        """The writer's first snapshot or lookup try after its first commit
        call, as the shim logs each at its start, before any hold: a next
        attempt's snapshot, or, where the deadline passed with no attempt
        started, the lookup's first try (at most one retry, TP:5634-5636;
        T246c)."""
        calls = self.w.calls()
        commits = [k for k, c in enumerate(calls) if "commit_write" in (c.get("stdin") or "")]
        later = calls[commits[0] + 1:] if commits else []
        return next((c for c in later if SNAPSHOT_TEXT in (c.get("stdin") or "")
                     or "find_write" in (c.get("stdin") or "")), None)

    def end(self, how: str) -> None:
        self.session.stdin.write(f"{how};\n")
        self.session.stdin.flush()

    def release(self) -> None:
        if self.held is not None:
            self.held.close()
            self.held = None

    def finish(self) -> int:
        self.release()
        code = self.w.wait()
        if self.session.poll() is None:
            self.end("ROLLBACK")
            self.session.stdin.close()
            self.session.stdin = None
            self.session.communicate(timeout=30)
        return code

    def tries(self) -> List[dict]:
        """Each lookup try's start: the shim's stamps, and the tries the
        answer stand-in answered before the shim saw them."""
        answered = []
        for where in self.first:
            log = where / "answer.log"
            if log.exists():
                answered += [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l]
        return sorted(lookups(self.w) + answered, key=lambda t: t["t"])

    def n_epoch(self) -> float:
        return float(self.e.c.value(f"SELECT extract(epoch FROM '{self.n}'::timestamptz);"))

    def tries_obey_the_window(self, least: int = 2) -> List[dict]:
        """The tries' timing rules, on the stamps (section 4's rules 2 and 3,
        with lane 2's tolerance), the spread recorded against 10 s."""
        tries = self.tries()
        assert len(tries) >= least, f"{len(tries)} lookup tries, not at least {least}"
        for k, (last, this) in enumerate(zip(tries, tries[1:]), 2):
            assert this["t"] - last["t"] >= GAP_S, f"try {k} began {this['t'] - last['t']:.2f} s after the last"
            assert this["t"] - tries[0]["t"] >= k - LATE_S, f"try {k} began early on the first's start"
        assert tries[-1]["t"] - tries[0]["t"] <= 2 * WINDOW_S, "a try began past twice the window"
        print(f"[T246 tries] n={len(tries)} last={tries[-1]['t'] - tries[0]['t']:.2f}s against {WINDOW_S}s")
        return tries


def busy(w: Writer) -> bool:
    return w.code == 75 and all(word in w.err for word in ("register busy", "nothing", "retry"))


@CLIENT
@pytest.mark.parametrize("case", ["found", "absent", "held", "no-answer"])
def test_a_write_in_doubt_at_the_deadline_makes_one_lookup(estates, case):
    """While the first try is held: [found] the session commits, exit 0, one
    row, the record removed; [absent] it rolls back, exit 75 with the busy
    text, no row, the record removed; [held] it stays open, every try meets
    55P03, at least two tries by the window's rules, exit 3 naming the id,
    never 75, the record kept, and after the rollback a plain rerun writes
    it once; [no-answer] every try fails as a failed connect, exit 3, the
    record kept. The first try starts no earlier than `<n>` less 3 s."""
    e = estates()
    arms = [{"mode": "fail-match", "match": "find_write"}] if case == "no-answer" else []
    h = HalfOpen(e, arms=arms, hold_lookup=case != "no-answer")
    if case in ("found", "absent"):
        h.end("COMMIT" if case == "found" else "ROLLBACK")
    h.release()
    code = h.w.wait()
    assert h.tries()[0]["t"] >= h.n_epoch() - 3, "the first try began before <n> less 2 s"
    rows = [r["write_id"] for r in e.journal_after()].count(h.write_id)
    if case == "found":
        assert (code, rows, pending(e)) == (0, 1, []), h.w.err[-800:]
    elif case == "absent":
        assert busy(h.w) and rows == 0 and pending(e) == [], h.w.err[-800:]
    else:
        assert code == 3 and h.write_id in h.w.err and len(pending(e)) == 1, h.w.err[-800:]
        h.tries_obey_the_window()
    h.finish()
    if case == "held":
        again = e.run(LA, h.argv)
        assert again.code == 0, again.err[-800:]
        assert [r["write_id"] for r in e.journal_after()].count(h.write_id) == 1


@CLIENT
def test_the_deadlines_lookup_waits_past_the_largest_not_after(estates):
    """[held]'s first try is seen in `PgSleep` until the database's clock
    passes `<n>`, then waiting on the head row's lock (lane 1's v2.6,
    behaviour 1); its script calls `find_write` with the write id, `<n>`,
    and the generation, lane, verb and `args_sha256` the commit calls sent.
    The session then rolls back, and the writer exits 75."""
    e = estates()
    h = HalfOpen(e, hold_lookup=False)
    slept = until_seen("the lookup in PgSleep", lambda: e.c.value(
        "SELECT count(*) FROM pg_stat_activity WHERE query LIKE '%find_write%' "
        "AND wait_event = 'PgSleep' AND pid <> pg_backend_pid();") != "0", h.w)
    assert slept and not db_past(e, h.n)
    until_seen("the lookup waiting on a Lock", lambda: e.c.value(
        "SELECT count(*) FROM pg_stat_activity WHERE query LIKE '%find_write%' "
        "AND wait_event_type = 'Lock' AND pid <> pg_backend_pid();") != "0", h.w)
    assert db_past(e, h.n)
    script = lookups(h.w)[0]["stdin"]
    entry = json.loads(ENTRY_IN_SCRIPT.search(h.w.commit_calls()[0]["stdin"]).group(1).replace("''", "'"))
    for value in (h.write_id, entry["journal"]["lane"], entry["journal"]["verb"],
                  entry["journal"]["args_sha256"]):
        assert value in script, f"the lookup's script does not carry {value!r}"
    h.end("ROLLBACK")
    assert h.finish() == 75, h.w.err[-800:]


@CLIENT
@pytest.mark.parametrize("ending", ["timer", "55p03", "connect", *NO_ANSWER])
def test_a_lookup_try_without_an_answer_is_made_again_inside_the_window(estates, ending):
    """The first try ends with no answer: [timer] held past `T_L`; [55p03]
    the session holds the head row until the shim's ends show the try's
    55P03; [connect] a failed connect; and [57014], [exit-1], [signal],
    [exit-3-no-sqlstate] and [unreadable-exit-0] (ERR-50; R-F11-5). The
    session rolls back, and a second try, by the window's rules, takes the
    lock and finds the write absent: exit 75, and the record removed."""
    e = estates()
    first: List[Path] = [answering(e, NO_ANSWER[ending])] if ending in NO_ANSWER else []
    arms = [{"mode": "fail-match", "match": "find_write", "call": 1}] if ending == "connect" else []
    h = HalfOpen(e, arms=arms, first=first, hold_lookup=ending in ("timer", "55p03"))
    if ending == "55p03":
        h.release()
        until_seen("the first try's end in 55P03", lambda: lookups(h.w) and lookups(h.w)[0]["call"] in h.w.ends(), h.w)
    elif ending != "timer":
        until_seen("the first try", lambda: h.tries(), h.w)
    h.end("ROLLBACK")
    code = h.w.wait()
    h.finish()
    assert code == 75 and pending(e) == [], f"exit {code}: {h.w.err[-800:]}"
    h.tries_obey_the_window(least=2)


@CLIENT
def test_a_lookup_refused_for_another_generation_exits_2_and_keeps_the_record(estates):
    """[generation]: while the first try is held the switch row's generation
    becomes a new uuid, as a re-import's bootstrap sets it, and the session
    rolls back. One try: LR007 `generation`; exit 2 with the server's
    message, the record kept; a plain rerun then refuses with 2 at its first
    snapshot, sending nothing."""
    e = estates()
    argv = note(LA, "F3 generation")
    h = HalfOpen(e, argv)
    e.c.db.psql(f"UPDATE {REGISTER}.register_switch SET generation = '{uuid.uuid4()}';")
    h.end("ROLLBACK")
    assert h.finish() == 2 and "LR007" in h.w.err and len(pending(e)) == 1, h.w.err[-800:]
    assert len(lookups(h.w)) == 1
    again = e.run(LA, argv)
    assert again.code == 2 and again.commit_calls() == [], again.err[-800:]


@CLIENT
def test_a_lookup_refused_for_another_write_exits_2_and_removes_the_record(estates):
    """[another-write]: the session's replay carries another `args_sha256`
    under the same id and commits while the first try is held. One try:
    LR007 `another-write`; exit 2, the record removed; the journal holds
    only the session's entry for the id."""
    e = estates()
    h = HalfOpen(e, alter=another_writes_script)
    h.end("COMMIT")
    assert h.finish() == 2 and "LR007" in h.w.err and pending(e) == [], h.w.err[-800:]
    assert len(lookups(h.w)) == 1
    rows = e.rows(f"SELECT args_sha256 FROM {REGISTER}.journal WHERE write_id = '{h.write_id}'")
    assert rows == [{"args_sha256": sha256(b"another write, T246")}], rows


@CLIENT
def test_a_lookup_made_too_early_exits_3_and_keeps_the_record(estates):
    """[too-early]: a write killed once its in-doubt call returned, on
    another host, keeps its `call` line. A plain rerun here, whose snapshot
    the shim fails, takes the record over with no clock to age and calls at
    once: LR011, exit 3 naming the id with the server's message, the record
    kept, one try. Once snapshots pass, a plain rerun exits 0 with one row.
    The other host's claim lives the seam's cap, so the first rerun runs at
    `LANES_REGISTER_SEAM_CAP_S=1` (see the section's head; T246d), and so
    does the last: the first rerun's 3 removes its own claim
    (`c8acf67c:lanes-edit.sh:9734`), so the last meets the other host's
    claim again, its cap counted afresh from the record's `updated_utc`,
    which the takeover rewrote (T246e)."""
    e = estates()
    argv = note(LA, "F3 too early")
    cap = {"LANES_REGISTER_SEAM_CAP_S": "1"}
    _, write_id = killed(e, LA, argv, extra={"LANES_HOST": "eagle-2"})
    early = e.run(LA, argv, arms=[{"mode": "fail-match", "match": SNAPSHOT_TEXT, "call": 1}], extra=cap)
    assert early.code == 3 and write_id in early.err and "LR011" in early.err, early.err[-800:]
    assert len(lookups(early)) == 1 and len(pending(e)) == 1
    again = e.run(LA, argv, extra=cap)
    assert again.code == 0 and [r["write_id"] for r in e.journal_after()].count(write_id) == 1


@pytest.mark.parametrize("case", ["missing", "ahead"])
def test_find_write_refuses_lr011_at_once(clones, case):
    """Phase N, direct calls: `p_not_after` NULL, or the clock plus 5 s,
    under a 2 s `statement_timeout`, so a 3 s wait would end 57014 instead:
    LR011 (lane 1's v2.6, behaviour 2)."""
    c, w = at_lr011(clones)
    sql = LOOKUP_SQL.replace("'6000ms'", "'2000ms'")
    if case == "missing":
        sql = sql.replace(":'not_after'::timestamptz", "nullif(:'not_after', '')::timestamptz")
    proc = c.call(sql, appname="t246-lookup", **c.lookup_variables(
        w["id"], "" if case == "missing" else c.clock(5), None, L1, VERB, w["args"]))
    c.check_refused(proc, None, "LR011", None)


@CLIENT
def test_an_orphaned_commit_call_released_after_its_not_after_writes_nothing(estates):
    """The shim forks the first commit call into its own session, held on a
    FIFO before `psql`; the writer's 8 s timer kills the shim, not the call.
    The write reaches its deadline, the lookup finds it absent and the
    writer exits 75; then the held call is released: `commit_write` reaches
    step 9 past `not_after`, raises LR008, and the head, the journal and the
    lines are as before; the id stays absent."""
    e = estates()
    orphan = fifo(e, "orphan")
    w = e.run(LA, note(LA, "orphan"), extra=DEADLINE,
              arms=[{"mode": "fork", "match": "commit_write", "call": 1, "fifo": str(orphan)}])
    assert w.code == 75, w.err[-800:]
    write_id = w.write_ids()[0]
    before = e.c.state()
    hold_point(orphan, w).close()
    until_seen("the orphan's end", lambda: e.c.value(
        f"SELECT count(*) FROM pg_stat_activity WHERE query LIKE '%{write_id}%' "
        "AND pid <> pg_backend_pid();") == "0")
    assert e.c.state() == before and not e.has_write(write_id)


@pytest.mark.parametrize("case", ["past", "within"])
def test_a_commit_past_its_not_after_raises_lr008_and_one_within_it_commits(clones, case):
    """LR008's engine half, by direct calls: an entry whose `not_after` is
    the clock plus 2 s, sent 3 s later, gets LR008 and changes nothing; the
    same with the clock plus 8 s commits."""
    c, _ = at_lr011(clones)
    entry = c.write_entry(seconds=2 if case == "past" else 8)
    time.sleep(3)
    if case == "past":
        c.refused(entry, "LR008", None, "reached its end")
    else:
        assert c.committed(entry)[0] == c.head()


@CLIENT
def test_lr008_inside_the_deadline_is_a_lost_turn_and_the_write_exits_0(estates):
    """LR008's client half (lane 4, 6709038351): the first commit call's
    `not_after` is set past by the shim, so it answers LR008 inside its
    timer. The writer drops that call's line, takes a fresh snapshot, makes
    a new attempt under the same id, commits, exits 0 with one row, and
    makes no lookup."""
    e = estates()
    w = e.run(LA, note(LA, "lr008 inside"),
              arms=[{"mode": "edit-entry", "match": "commit_write", "call": 1, "field": "not_after", "value": PAST}])
    assert w.code == 0, w.err[-800:]
    assert len(w.commit_calls()) >= 2 and lookups(w) == []
    one_entry(e, w)


@CLIENT
@pytest.mark.parametrize("case", ["found", "absent", "held"])
def test_lr008_at_the_deadline_leaves_the_exit_to_find_write(estates, case):
    """The first call in doubt (AT-F3's estate) and each later call ending
    LR008: the writer makes F3's lookup and exits as it says: [found] 0,
    [absent] 75, [held] 3."""
    e = estates()
    h = HalfOpen(e, arms=[{"mode": "edit-entry", "match": "commit_write", "from": 2, "field": "not_after",
                           "value": PAST}])
    if case != "held":
        h.end("COMMIT" if case == "found" else "ROLLBACK")
        code = h.finish()
    else:
        h.release()
        code = h.w.wait()
        h.finish()
    assert lookups(h.w), "no lookup"
    assert code == {"found": 0, "absent": 75, "held": 3}[case], h.w.err[-800:]


@CLIENT
def test_a_write_whose_every_call_ended_lr008_exits_75_with_no_lookup(estates):
    """Every commit call answers LR008, so each dropped its `call` line and
    the write was never in doubt: exit 75 with no lookup in the shim's log."""
    e = estates()
    w = e.run(LA, note(LA, "lr008 every"), extra=DEADLINE,
              arms=[{"mode": "edit-entry", "match": "commit_write", "field": "not_after", "value": PAST}])
    assert w.code == 75 and lookups(w) == [], w.err[-800:]
    assert not e.has_write(w.write_ids()[0]) and pending(e) == []


@CLIENT
@pytest.mark.parametrize("case", ["first-call", "every-call"])
def test_lr008_alone_never_gives_3_or_69(estates, case):
    """LR008 on the first call only, or on every call, at a 1 s deadline:
    the exit is decided by a later attempt or the lookup, never 3 or 69."""
    e = estates()
    arm = {"mode": "edit-entry", "match": "commit_write", "field": "not_after", "value": PAST}
    if case == "first-call":
        arm["call"] = 1
    w = e.run(LA, note(LA, f"lr008 {case}"), extra=DEADLINE, arms=[arm])
    assert w.code not in (3, 69), w.err[-800:]


# ============================================================ PHASE W: AT-F10 (T247)
#
# A PENDING RECORD AND AN UNRELATED IDENTICAL COMMAND (AT-F10, TP:6443-6580).
# The record's name `<d>` is the entry's `journal.args_sha256`, the sha256
# of `lanes-pending/1`, `LANES_LANE`, `LANES_SESSION`, the verb and each
# argument, NUL-separated; it is owned by the run in its highest-numbered
# claim file `<d>.take.<k>`, whose liveness is tested on that claim's pid
# and start time, never on the record's `pid`. The claims the test writes
# hold `pid=`, `pid_start=`, `host=`, `container=` and `utc=`, one per line,
# in that order (pending-record.md §4.1, the key `lanes-edit.sh` reads,
# `wr_claim_read`; T247b, lane 4's triage, #165 6833813092), each owner a live
# stand-in (`Owner`) where it is on this host.
#
# A CLAIM WITH NO RECORD BESIDE IT (Q-L2-6; R26, lane 4's answer to 42):
# `[live-at-deadline]` asserts the 3's text: it names the claim by pid, host
# and container and the UTC it was claimed; says the record is not yet
# written, so its write id is not known, and that this run sent nothing; and
# gives the effect check, `lanes-edit.sh history <lane> --since <utc>` or
# `lanes-edit.sh register-row <lane>`. `[write-id-live-at-deadline]`: a run
# under `LANES_WRITE_ID` prints its own id again with its generation.
#
# They FAIL UNTIL L4-B2 lands, and the record-less text until lane 4's T417.
# Without PostgreSQL 16 each skips.

MAX_AGE = {"LANES_REGISTER_PENDING_MAX_AGE_S": "2"}


class Owner:
    """A live stand-in owner on this host: a process blocked on its stdin."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen([sys.executable, "-I", "-c", "import sys; sys.stdin.read()"],
                                     stdin=subprocess.PIPE)
        self.pid, self.start = self.proc.pid, _proc_start(self.proc.pid)
        self.ended_at: Optional[float] = None

    def end(self) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.close()
            self.proc.wait(timeout=30)
            self.ended_at = time.time()


#: How long the stand-in owner lives once an identical run is launched (T247c).
OWNER_LIVES_S = 3


def owner_lives(w: Writer) -> None:
    """Let the run meet the live owner's claim for `OWNER_LIVES_S`, then
    check it is still waiting, having sent nothing (T247c; PM33A-TRIAGE L6).
    The run takes and waits on its claim before its first snapshot
    (`pw_run`: `wr_claim_take`, then `pw_owner_live_end`;
    `8ba10b4e:lanes-edit.sh:10820`), so it makes no shim call while the owner
    lives: ending the owner on the run's first call waited for a call that
    never came, and the run ended 3 at its deadline."""
    time.sleep(OWNER_LIVES_S)
    assert w.ended is None, f"{w.name} exited {w.code} while the owner lived: {w.err[-400:]}"
    assert w.calls() == [], f"{w.name} sent a call while the owner lived: {w.calls()[:1]}"


def dead_pid() -> int:
    gone = subprocess.Popen([sys.executable, "-I", "-c", "pass"])
    gone.wait()
    return gone.pid


def digest(lane: str, argv: Sequence[str]) -> str:
    return sha256("\0".join(["lanes-pending/1", lane, session_of(lane), *argv]).encode("utf-8"))


def write_claim(e: Estate, d: str, k: int, pid: int, start: str = "", *, host: str = "eagle",
                container: str = "none", utc: Optional[str] = None) -> Path:
    where = e.state / PENDING
    where.mkdir(mode=0o700, parents=True, exist_ok=True)
    claim_file = where / f"{d}.take.{k}"
    claim_file.write_text(f"pid={pid}\npid_start={start}\nhost={host}\ncontainer={container}\n"
                          f"utc={utc or e.utc()}\n", encoding="utf-8")
    return claim_file


def set_field(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(f"{key}={value}" if l.startswith(key + "=") else l for l in lines) + "\n",
                    encoding="utf-8")


def snapshot_state(e: Estate) -> Dict[str, str]:
    where = e.state / PENDING
    return {p.name: p.read_text(encoding="utf-8") for p in where.iterdir()} if where.is_dir() else {}


@CLIENT
def test_an_expired_pending_record_is_not_reused(estates):
    """A record from a write that committed, older than the maximum age
    (`LANES_REGISTER_PENDING_MAX_AGE_S=2`): the identical command warns,
    prints the lookup, mints a new id and writes."""
    e = estates()
    argv = note(LA, "expired record")
    _, old = killed(e, LA, argv)
    time.sleep(3)
    w = e.run(LA, argv, extra=MAX_AGE)
    assert w.code == 0 and "WARNING" in w.err and f"--write-id {old}" in w.err, w.err[-800:]
    assert old not in w.write_ids()
    ids = [r["write_id"] for r in e.journal_after()]
    assert ids.count(old) == 1 and len(ids) == 2, ids


@CLIENT
@pytest.mark.parametrize("case", ["ends-in-time", "live-at-deadline"])
def test_a_live_pending_record_is_waited_for_not_shared(estates, case):
    """The second of two identical runs waits while the first's owner lives.
    [ends-in-time]: the first ends inside the deadline, and the second writes
    under its own id: two entries. [live-at-deadline]: at a 1 s deadline the
    second exits 3, never 75, saying an identical write is still running in
    the first's pid (write id, start UTC), with no commit call of its own, and
    the record and its claims as the first left them."""
    e = estates()
    gate = fifo(e, "first")
    argv = note(LA, f"identical {case}")
    first = e.launch(LA, argv, arms=[{"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(gate)}])
    held = hold_point(gate, first)
    left = snapshot_state(e)
    second = e.launch(LA, argv, extra=DEADLINE if case == "live-at-deadline" else None)
    if case == "ends-in-time":
        until_seen("the second's first call", lambda: second.calls(), second)
        held.close()
        assert first.wait() == 0 and second.wait() == 0, second.err[-800:]
        ids = {r["write_id"] for r in e.journal_after()}
        assert len(ids) == 2 and set(second.write_ids()) & ids and not set(second.write_ids()) & set(first.write_ids())
    else:
        assert second.wait() == 3, second.err[-800:]
        assert "an identical write is still running in pid" in second.err and str(first.proc.pid) in second.err
        assert first.write_ids()[0] in second.err and second.commit_calls() == []
        assert snapshot_state(e) == left
        held.close()
        assert first.wait() == 0


@CLIENT
@pytest.mark.parametrize("case", ["host-now", "container-now", "claim-old-record-fresh", "both-old"])
def test_a_claim_from_another_host_or_container_counts_as_live_for_120_s(estates, case):
    """The highest claim names another host or container, with a pid dead
    here; it counts as live for 120 s from the later of its UTC and the
    record's `updated_utc`. [host-now], [container-now] and
    [claim-old-record-fresh]: a plain rerun waits and at a 1 s deadline exits
    3, sending nothing, naming the claim's pid. [both-old]: it creates the
    next claim and takes the record over."""
    e = estates()
    argv = note(LA, f"other host {case}")
    exit3(e, LA, argv)
    rec = the_record(e)["path"]
    pid, old = dead_pid(), e.utc(121 / 60)
    other = {"container": "ctr-2"} if case == "container-now" else {"host": "eagle-2"}
    write_claim(e, rec.name, 1, pid, utc=old if case in ("claim-old-record-fresh", "both-old") else e.utc(), **other)
    if case == "both-old":
        set_field(rec, "updated_utc", old)
        gate = fifo(e, "both-old")
        w = e.launch(LA, argv, arms=[{"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(gate)}])
        held = hold_point(gate, w)
        assert f"{rec.name}.take.2" in take_files(e), take_files(e)
        held.close()
        assert w.wait() == 0, w.err[-800:]
    else:
        w = e.run(LA, argv, extra=DEADLINE)
        assert w.code == 3 and str(pid) in w.err and w.commit_calls() == [], w.err[-800:]


@CLIENT
@pytest.mark.parametrize("case", ["ends-in-time", "live-at-deadline"])
def test_a_lanes_write_id_run_waits_for_a_live_owner(estates, case):
    """A record whose highest claim's owner is a live stand-in, met by the
    printed rerun under `LANES_WRITE_ID`. [live-at-deadline]: exit 3, no
    commit call, the record and its claims unchanged. [ends-in-time]: the
    owner ends; the run goes on, its one commit call after the owner's end,
    and the write commits once under that id."""
    e = estates()
    argv = note(LA, f"write id {case}")
    _, write_id, generation = exit3(e, LA, argv)
    rec = the_record(e)["path"]
    owner = Owner()
    try:
        write_claim(e, rec.name, 1, owner.pid, owner.start)
        left = snapshot_state(e)
        w = e.launch(LA, argv, extra=dict(DEADLINE if case == "live-at-deadline" else {},
                                          LANES_WRITE_ID=write_id, LANES_WRITE_GENERATION=generation))
        if case == "ends-in-time":
            owner_lives(w)
            owner.end()
        code = w.wait()
    finally:
        owner.end()
    if case == "live-at-deadline":
        assert code == 3 and w.commit_calls() == [] and snapshot_state(e) == left, w.err[-800:]
    else:
        assert code == 0, w.err[-800:]
        commits = [c for c in w.stamps() if "commit_write" in (c.get("stdin") or "")]
        assert len(commits) == 1 and commits[0]["t"] >= owner.ended_at
        assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1


@CLIENT
@pytest.mark.parametrize("case", ["ends-in-time", "live-at-deadline", "write-id-live-at-deadline"])
def test_a_claim_with_no_record_beside_it_is_waited_for(estates, case):
    """`<d>.take.0` with no record, its owner a live stand-in. At a 1 s
    deadline an identical run exits 3 with no commit call and no claim of
    its own; [live-at-deadline]'s text names the claim by pid, host,
    container and UTC, says the record is not yet written so its write id is
    not known and this run sent nothing, and gives the effect check;
    [write-id-live-at-deadline] prints its own id again with its generation.
    [ends-in-time]: the owner ends, and the run creates `<d>.take.1`, writes
    and commits once."""
    e = estates()
    argv = note(LA, f"no record {case}")
    d = digest(LA, argv)
    owner = Owner()
    utc = e.utc()
    extra: Dict[str, str] = {} if case == "ends-in-time" else dict(DEADLINE)
    mine = str(uuid.uuid4())
    if case == "write-id-live-at-deadline":
        extra.update(LANES_WRITE_ID=mine, LANES_WRITE_GENERATION=e.c.switch()["generation"])
    try:
        write_claim(e, d, 0, owner.pid, owner.start, utc=utc)
        w = e.launch(LA, argv, extra=extra)
        if case == "ends-in-time":
            owner_lives(w)
            owner.end()
        code = w.wait()
    finally:
        owner.end()
    if case == "ends-in-time":
        assert code == 0 and len(e.journal_after()) == 1, w.err[-800:]
        return
    assert code == 3 and w.commit_calls() == [], w.err[-800:]
    assert take_files(e) == [f"{d}.take.0"], take_files(e)
    if case == "live-at-deadline":
        for said in (str(owner.pid), "eagle", utc, "not yet written", "sent nothing"):
            assert said in w.err, f"{said!r} is not in the 3's text: {w.err[-800:]}"
        assert f"lanes-edit.sh history {LA} --since" in w.err or f"lanes-edit.sh register-row {LA}" in w.err
    else:
        assert f"LANES_WRITE_ID={mine}" in w.err and extra["LANES_WRITE_GENERATION"] in w.err, w.err[-800:]


@CLIENT
def test_a_reused_pid_in_a_pending_record_reads_as_dead(estates):
    """The highest claim's pid is live, but its start time differs: the
    owner reads as dead, so the run creates the next claim and takes the
    record over."""
    e = estates()
    argv = note(LA, "reused pid")
    _, write_id, _ = exit3(e, LA, argv)
    rec = the_record(e)["path"]
    owner = Owner()
    try:
        write_claim(e, rec.name, 1, owner.pid, "1")
        w = e.run(LA, argv)
    finally:
        owner.end()
    assert w.code == 0, w.err[-800:]
    assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1


@CLIENT
@pytest.mark.parametrize("case", ["record-pid-live", "record-pid-dead"])
def test_liveness_is_the_highest_claims_never_the_records_pid(estates, case):
    """[record-pid-live]: the record's `pid` is live, its highest claim's
    owner dead: taken over. [record-pid-dead]: the converse is waited for,
    and at a 1 s deadline the run exits 3 with no commit call."""
    e = estates()
    argv = note(LA, f"liveness {case}")
    _, write_id, _ = exit3(e, LA, argv)
    rec = the_record(e)["path"]
    owner = Owner()
    try:
        if case == "record-pid-live":
            set_field(rec, "pid", str(owner.pid))
            write_claim(e, rec.name, 1, dead_pid())
        else:
            set_field(rec, "pid", str(dead_pid()))
            write_claim(e, rec.name, 1, owner.pid, owner.start)
        w = e.run(LA, argv, extra=DEADLINE if case == "record-pid-dead" else None)
    finally:
        owner.end()
    if case == "record-pid-live":
        assert w.code == 0 and [r["write_id"] for r in e.journal_after()].count(write_id) == 1, w.err[-800:]
    else:
        assert w.code == 3 and w.commit_calls() == [], w.err[-800:]


@CLIENT
def test_the_pending_digest_covers_the_session_and_equals_args_sha256(estates):
    """The record is 0600 in a 0700 directory, and its name equals the
    entry's `args_sha256`, the digest of `lanes-pending/1`, the lane, the
    session, the verb and each argument, NUL-separated. Two runs differing
    only in `LANES_SESSION` have different digests, and neither takes the
    other's record: two records while both are held, two entries after."""
    e = estates()
    argv = note(LA, "digest")
    gates = fifo(e, "digest-1"), fifo(e, "digest-2")
    one = e.launch(LA, argv, arms=[{"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(gates[0])}])
    first = hold_point(gates[0], one)
    rec = the_record(e)["path"]
    entry = json.loads(ENTRY_IN_SCRIPT.search(one.commit_calls()[0]["stdin"]).group(1).replace("''", "'"))
    assert rec.name == entry["journal"]["args_sha256"] == digest(LA, argv)
    assert rec.stat().st_mode & 0o777 == 0o600 and rec.parent.stat().st_mode & 0o777 == 0o700
    two = e.launch(LA, argv, extra={"LANES_SESSION": str(uuid.uuid4())},
                   arms=[{"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(gates[1])}])
    second = hold_point(gates[1], two)
    assert len(pending(e)) == 2, pending(e)
    first.close()
    second.close()
    assert (one.wait(), two.wait()) == (0, 0)
    assert len({r["write_id"] for r in e.journal_after()}) == 2


@CLIENT
@pytest.mark.parametrize("case", ["arguments", "verb", "generation"])
def test_a_write_id_of_other_arguments_verb_or_generation_is_refused_2_at_the_snapshot(estates, case):
    """A `LANES_WRITE_ID` naming a committed entry of other arguments, or
    of another verb, or a printed rerun whose `LANES_WRITE_GENERATION` is
    not the switch's: exit 2 at the snapshot, naming the id (and what
    differs), with no commit call, and nothing written."""
    e = estates()
    w = e.run(LA, note(LA, "the entry"))
    assert w.code == 0
    write_id = w.write_ids()[0]
    generation = e.c.switch()["generation"] if case != "generation" else str(uuid.uuid4())
    argv = {"arguments": note(LA, "other arguments"), "verb": ["log", "NOTED", f"lane:{LA}", "T247 other verb"],
            "generation": note(LA, "the entry")}[case]
    before = e.journal_after()
    again = e.run(LA, argv, extra={"LANES_WRITE_ID": write_id, "LANES_WRITE_GENERATION": generation})
    assert again.code == 2 and again.commit_calls() == [] and write_id in again.err, again.err[-800:]
    assert e.journal_after() == before


@CLIENT
@pytest.mark.parametrize("case", ["fresh", "past-max-age"])
def test_a_record_of_another_generation_is_refused_2_until_lanes_write_id_new(estates, case):
    """A record of another generation, fresh or past the maximum age: a
    plain rerun refuses with 2 at its first snapshot, with no commit call;
    its text names the write id, `created_utc` and both generations, the
    effect check, and `LANES_WRITE_ID=new`; the record is left as it is,
    `lanes-index status` lists it, and a second plain rerun refuses the same
    way."""
    e = estates()
    argv = note(LA, f"generation {case}")
    _, write_id, generation = exit3(e, LA, argv)
    rec = the_record(e)
    other = str(uuid.uuid4())
    set_field(rec["path"], "generation", other)
    extra = dict(MAX_AGE) if case == "past-max-age" else {}
    if extra:
        time.sleep(3)
    left = snapshot_state(e)
    for _ in range(2):
        w = e.run(LA, argv, extra=extra)
        assert w.code == 2 and w.commit_calls() == [], w.err[-800:]
        for said in (write_id, rec["fields"].get("created_utc", "created_utc"), other, generation,
                     "LANES_WRITE_ID=new"):
            assert said in w.err, f"{said!r} is not in the refusal: {w.err[-800:]}"
        assert f"lanes-edit.sh history {LA} --since" in w.err or f"lanes-edit.sh register-row {LA}" in w.err
        assert snapshot_state(e) == left
    env = dict(e.env, PATH=os.pathsep.join([str(e.psql_dir(f"status-{case}")), e.env["PATH"]]))
    status = subprocess.run([str(e.bindir / "lanes-index"), "status"], capture_output=True, text=True,
                            env=env, check=False, timeout=120)
    assert write_id in status.stdout, status.stdout[-800:]


@CLIENT
def test_a_write_id_already_journaled_for_the_same_arguments_exits_0_at_the_snapshot(estates):
    """A `LANES_WRITE_ID` rerun of a write already in the journal with the
    same arguments exits 0 at the snapshot, with no commit call, and the
    journal holds it once."""
    e = estates()
    argv = note(LA, "journaled")
    w = e.run(LA, argv)
    assert w.code == 0
    write_id = w.write_ids()[0]
    again = e.run(LA, argv, extra={"LANES_WRITE_ID": write_id,
                                   "LANES_WRITE_GENERATION": e.c.switch()["generation"]})
    assert again.code == 0 and again.commit_calls() == [], again.err[-800:]
    assert [r["write_id"] for r in e.journal_after()].count(write_id) == 1


# ============================================================ PHASE N: AT-LR006 and AT-F33 (T251)
#
# TWO ATTEMPTS OF ONE WRITE MEETING AT THE COMMIT (AT-LR006, TP:4595-4754;
# AT-F33, TP:4755-4786), on T222's clones, as the writer login in the commit
# call's own form. Attempts A and B carry one write W: the same id, lane,
# verb and `args_sha256`, and a `not_after` well past the case. A is a
# session of its own whose transaction is held open on its stdin; B's
# snapshot read is one `REPEATABLE READ READ ONLY` transaction as the
# writer; every barrier is a state polled in `pg_stat_activity` by
# `application_name` (A `idle in transaction`, or B waiting on a `Lock` with
# `pg_blocking_pids` naming A). The no-lookup control is `commit_write`'s
# own text from `pg_get_functiondef`, step 1's lookup cut and nothing else,
# created in the case's clone as `lanes_register_owner` and granted to the
# writer. The client's halves (`register commit` exits 0, 75 or 2, and the
# write exits 0 once its next snapshot finds W) stand as the next snapshot
# read finding W at n+1.
#
# They FAIL UNTIL L1-A6 (T107), with L4-B3 and L4-B5 for the client's
# halves. Without PostgreSQL 16 each skips.

_SESSIONS = itertools.count(1)


class Two:
    """AT-LR006's fixture on one clone at `primary` with W's entry made:
    the commit calls of A and B, their sessions and their outcomes."""

    def __init__(self, c: Clone, fn: str = "commit_write") -> None:
        self.c, self.fn = c, fn
        self.entry = c.write_entry(seconds=600)
        self.wid, self.n = str(uuid.uuid4()), c.head()
        self.gen, self.client = c.switch()["generation"], c.client()
        self.outcomes: List[Tuple[str, int, str]] = []

    def sql(self, base: int, *, entry: Optional[dict] = None, level: str = "SERIALIZABLE",
            gen: Optional[str] = None, commit: bool = True) -> str:
        body = json.dumps(entry or self.entry, ensure_ascii=False)
        return (f"BEGIN ISOLATION LEVEL {level};\n"
                f"SELECT {REGISTER}.{self.fn}({base}, '{self.wid}'::uuid, {self.client}, "
                f"'{gen or self.gen}'::uuid, $t251${body}$t251$::jsonb);\n" + ("COMMIT;\n" if commit else ""))

    def session(self, name: str) -> subprocess.Popen:
        appname = f"t251-{name}-{next(_SESSIONS)}"
        proc = subprocess.Popen(self.c.argv({}), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=self.c.db.env(WRITER_LOGIN, appname))
        proc.appname = appname
        return proc

    def state_of(self, appname: str) -> str:
        return self.c.value(f"SELECT coalesce(string_agg(state, ','), '') FROM pg_stat_activity "
                            f"WHERE application_name = '{appname}';")

    def hold_a(self, entry: Optional[dict] = None) -> subprocess.Popen:
        """A runs `commit_write(n, W)` and stays idle in transaction."""
        a = self.session("a")
        a.stdin.write(self.sql(self.n, entry=entry, commit=False))
        a.stdin.flush()
        until(self.c, lambda: self.state_of(a.appname) == "idle in transaction", "A idle in transaction")
        return a

    def finish(self, proc: subprocess.Popen, who: str, tail: str = "") -> Tuple[int, str]:
        if tail:
            proc.stdin.write(tail)
        proc.stdin.close()
        proc.stdin = None
        _, err = proc.communicate(timeout=30)
        self.outcomes.append((who, proc.returncode, err))
        return proc.returncode, err

    def call_b(self, base: int, **options) -> Tuple[int, str]:
        proc = self.c.call(self.sql(base, **options), appname="t251-b")
        self.outcomes.append(("B", proc.returncode, proc.stderr))
        return proc.returncode, proc.stderr

    def start_b(self, base: int, **options) -> subprocess.Popen:
        appname = f"t251-bw-{next(_SESSIONS)}"
        proc = self.c.start(self.sql(base, **options), appname)
        proc.appname = appname
        return proc

    def b_waits_on(self, b: subprocess.Popen, a: subprocess.Popen) -> None:
        until(self.c, lambda: self.c.value(
            "SELECT count(*) FROM pg_stat_activity w JOIN pg_stat_activity h "
            f"ON h.application_name = '{a.appname}' WHERE w.application_name = '{b.appname}' "
            "AND w.wait_event_type = 'Lock' AND h.pid = ANY (pg_blocking_pids(w.pid));") == "1",
              "B waiting on a Lock that A blocks")

    def ended(self, proc: subprocess.Popen, who: str) -> Tuple[int, str]:
        _, err = proc.communicate(timeout=30)
        self.outcomes.append((who, proc.returncode, err))
        return proc.returncode, err

    def snapshot(self) -> str:
        """B's snapshot read: W's seq, or `absent`."""
        proc = self.c.call("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n"
                           f"SELECT coalesce((SELECT seq FROM {REGISTER}.journal WHERE write_id = "
                           f"'{self.wid}')::text, 'absent');\nCOMMIT;\n", appname="t251-snap")
        assert proc.returncode == 0, proc.stderr
        return proc.stdout.strip()

    def rows(self) -> int:
        return int(self.c.value(f"SELECT count(*) FROM {REGISTER}.journal WHERE write_id = '{self.wid}';"))


def code_of(rc: int, err: str) -> str:
    if rc == 0:
        return "committed"
    m = re.match(r"(?:ERROR|FATAL):  ([0-9A-Z]{5}):", err.splitlines()[0] if err else "")
    return m.group(1) if m else f"exit {rc}"


def control(c: Clone) -> str:
    """The no-lookup control, `commit_write_nolookup`, in this clone only."""
    text = c.value(f"SELECT pg_get_functiondef('{REGISTER}.commit_write'::regproc);")
    cut = re.subn(r"SELECT \* INTO v_old FROM journal WHERE write_id = p_write_id;.*?ERRCODE = 'LR006'; END IF;",
                  "", text, count=1, flags=re.S)
    assert cut[1] == 1, "commit_write holds no step-1 lookup to cut for the control"
    made = cut[0].replace(f"FUNCTION {REGISTER}.commit_write(", f"FUNCTION {REGISTER}.commit_write_nolookup(", 1)
    done = c.db.psql(f"SET ROLE lanes_register_owner;\n{made};\nRESET ROLE;\n"
                     f"GRANT EXECUTE ON FUNCTION {REGISTER}.commit_write_nolookup(bigint, uuid, integer, uuid, jsonb) "
                     "TO lanes_register_writer;\n")
    assert done.returncode == 0, done.stderr
    return "commit_write_nolookup"


def two(clones, fn: str = "commit_write", c: Optional[Clone] = None) -> Two:
    if c is None:
        c = clones()
        c.to_primary()
    return Two(c, control(c) if fn != "commit_write" else fn)


# -------------------------------------------- the scenarios, each run by its case and by AT-F33's matrix
def case_0(t: Two) -> str:
    """A commits before B's snapshot read; B's call made anyway."""
    t.finish(t.hold_a(), "A", "COMMIT;\n")
    assert t.snapshot() == str(t.n + 1)
    return code_of(*t.call_b(t.n + 1))


def lr006_1(t: Two, variant: str) -> Tuple[str, str]:
    if variant == "held":
        a = t.hold_a()
        said = t.snapshot()
        t.finish(a, "A", "COMMIT;\n")
    else:
        said = t.snapshot()
        t.finish(t.hold_a(), "A", "COMMIT;\n")
    rc, err = t.call_b(t.n)
    return said, err.splitlines()[0] if rc == 3 and err else code_of(rc, err)


def lr006_2(t: Two, base: str) -> str:
    t.finish(t.hold_a(), "A", "COMMIT;\n")
    return code_of(*t.call_b(t.n if base == "stale-base" else t.n + 1))


def lr006_3(t: Two, level: str, resend: bool = False) -> List[str]:
    a = t.hold_a()
    assert t.snapshot() == "absent"
    b = t.start_b(t.n, level=level)
    t.b_waits_on(b, a)
    t.finish(a, "A", "COMMIT;\n")
    codes = [code_of(*t.ended(b, "B"))]
    if resend:
        codes.append(code_of(*t.call_b(t.n + 1, level=level)))
    return codes


def lr006_4(t: Two, resend: bool = False) -> List[str]:
    a = t.hold_a()
    b = t.session("b4")
    b.stdin.write("BEGIN ISOLATION LEVEL SERIALIZABLE;\nSELECT pg_current_snapshot();\n")
    b.stdin.flush()
    until(t.c, lambda: t.state_of(b.appname) == "idle in transaction", "B's snapshot taken")
    t.finish(a, "A", "COMMIT;\n")
    rest = t.sql(t.n).split("\n", 1)[1]
    codes = [code_of(*t.finish(b, "B", rest))]
    if resend:
        codes.append(code_of(*t.call_b(t.n + 1)))
    return codes


def lr006_5(t: Two, resend: bool = False) -> List[str]:
    a = t.hold_a()
    b = t.start_b(t.n)
    t.b_waits_on(b, a)
    codes = [code_of(*t.ended(b, "B"))]
    t.finish(a, "A", "COMMIT;\n")
    if resend:
        codes.append(code_of(*t.call_b(t.n + 1)))
    return codes


def lr006_6(t: Two, variant: str) -> Tuple[str, str]:
    a = t.hold_a()
    if variant == "rollback":
        b = t.start_b(t.n)
        t.b_waits_on(b, a)
        a_code = code_of(*t.finish(a, "A", "ROLLBACK;\n"))
        return a_code, code_of(*t.ended(b, "B"))
    until(t.c, lambda: t.state_of(a.appname) == "", "A's session ended by the 5 s idle bound", deadline=15)
    rc, err = t.finish(a, "A", "COMMIT;\n")
    assert rc == 2 and "25P03" in err, (rc, err)
    assert t.snapshot() == "absent"
    return "25P03", code_of(*t.call_b(t.n))


# ------------------------------------------------------------ AT-LR006
@pytest.mark.parametrize("variant", ["held", "whole"])
def test_an_attempt_committed_after_the_snapshot_read_gives_lr006(clones, variant):
    """B's snapshot read finds W absent at head n; A commits W ([held]: A's
    transaction open across the read; [whole]: A runs whole after it); B's
    commit call exits 3 with exactly `ERROR:  LR006: write W is in the
    journal at seq n+1`; one row for W at n+1, and the head is n+1."""
    t = two(clones)
    said, first = lr006_1(t, variant)
    assert said == "absent"
    assert first == f"ERROR:  LR006: write {t.wid} is in the journal at seq {t.n + 1}", first
    assert t.rows() == 1 and t.c.head() == t.n + 1


@pytest.mark.parametrize("base", ["stale-base", "fresh-base"])
def test_lr006_comes_before_lr001(clones, base):
    """W committed at n+1: a commit call with the stale base n, or the fresh
    n+1, gives LR006, never LR001, and writes nothing."""
    t = two(clones)
    t.finish(t.hold_a(), "A", "COMMIT;\n")
    before = t.c.state()
    rc, err = t.call_b(t.n if base == "stale-base" else t.n + 1)
    assert code_of(rc, err) == "LR006" and t.c.state() == before, err


@pytest.mark.parametrize("level", ["SERIALIZABLE", "REPEATABLE READ"], ids=["serializable", "repeatable-read"])
def test_an_attempt_committed_while_the_commit_waits_gives_40001_then_exit_0(clones, level):
    """A holds; B's snapshot read; B's commit call waits on a lock A blocks;
    A commits. B gets 40001, never LR006 or 23505; the next snapshot read
    finds W at n+1; one row for W."""
    t = two(clones)
    assert lr006_3(t, level) == ["40001"]
    assert t.snapshot() == str(t.n + 1) and t.rows() == 1


def test_an_attempt_committed_after_the_commits_snapshot_gives_40001_without_a_wait(clones):
    """A holds; B begins SERIALIZABLE and takes its snapshot with `SELECT
    pg_current_snapshot()`; A commits; then B calls `commit_write`: 40001,
    with no lock wait. The next snapshot finds W; one row."""
    t = two(clones)
    assert lr006_4(t) == ["40001"]
    assert t.snapshot() == str(t.n + 1) and t.rows() == 1


def test_an_attempt_holding_past_lock_timeout_gives_55p03_then_exit_0(clones):
    """A holds and neither commits nor rolls back; B's commit call, seen
    waiting, gets 55P03 at its 2000 ms `lock_timeout`. After A commits the
    next snapshot finds W; one row."""
    t = two(clones)
    assert lr006_5(t) == ["55P03"]
    assert t.snapshot() == str(t.n + 1) and t.rows() == 1


@pytest.mark.parametrize("variant", ["rollback", "idle-bound"])
def test_an_attempt_that_never_commits_leaves_the_write_to_the_retry(clones, variant):
    """[rollback]: A holds, B is seen waiting, A rolls back: B commits W at
    n+1. [idle-bound]: the role's 5 s idle bound ends A's session; A's
    COMMIT then exits 2 with 25P03 on its `FATAL:` line; B's snapshot finds
    W absent, and B commits W at n+1. One row, no 23505."""
    t = two(clones)
    _, b = lr006_6(t, variant)
    assert b == "committed" and t.rows() == 1
    assert int(t.c.value(f"SELECT seq FROM {REGISTER}.journal WHERE write_id = '{t.wid}';")) == t.n + 1
    assert not any("23505" in err for _, _, err in t.outcomes)


def test_the_no_lookup_control_gives_lr001_where_the_lookup_gives_lr006(clones):
    """AT-LR006-1's interleaving against the control: LR001, where
    `commit_write` gives LR006 (so the test detects the lookup's absence);
    and AT-LR006-2's fresh base against it: 23505 on
    `journal_write_id_key`."""
    t = two(clones, "control")
    _, first = lr006_1(t, "held")
    assert first.startswith("ERROR:  LR001: "), first
    u = two(clones, "control", c=t.c)
    u.finish(u.hold_a(), "A", "COMMIT;\n")
    rc, err = u.call_b(u.n + 1)
    assert code_of(rc, err) == "23505" and "journal_write_id_key" in err, err


def test_another_writes_entry_committed_after_the_snapshot_read_gives_lr007_another_write(clones):
    """A carries W's id with other arguments and commits after B's snapshot
    read: B exits 3, `ERROR:  LR007: write W is seq n+1, another write's
    (F10)` then exactly `DETAIL:  another-write`; the journal holds A's one
    row. Under `VERBOSITY=sqlstate` the same call prints `ERROR:  LR007`
    alone, with no `DETAIL:` line."""
    t = two(clones)
    other = json.loads(json.dumps(t.entry))
    other["journal"]["args_sha256"] = sha256(b"another write, T251")
    assert t.snapshot() == "absent"
    t.finish(t.hold_a(entry=other), "A", "COMMIT;\n")
    before = t.c.state()
    rc, err = t.call_b(t.n)
    t.c.check_refused(subprocess.CompletedProcess([], rc, "", err), before, "LR007", "another-write",
                      f"write {t.wid} is seq {t.n + 1}, another write's (F10)")
    assert t.rows() == 1
    terse = subprocess.run([a if a != "VERBOSITY=verbose" else "VERBOSITY=sqlstate" for a in t.c.argv({})],
                           input=t.sql(t.n), capture_output=True, text=True, timeout=60,
                           env=t.c.db.env(WRITER_LOGIN, "t251-terse"), check=False)
    assert terse.stderr.splitlines()[:1] == ["ERROR:  LR007"] and "DETAIL:" not in terse.stderr, terse.stderr


def test_a_generation_change_after_the_snapshot_read_gives_lr007_generation(clones):
    """B's snapshot read; then the restore form's after-loss cutover commits
    at n+1 (a new generation, the marker `adding`); then B's commit call
    with the generation it read: LR007 `generation`, not LR002 or LR001;
    no row for W."""
    t = two(clones)
    assert t.snapshot() == "absent"
    t.c.committed(t.c.operator_entry(after_loss=True, database_label=RESTORED_LABEL))
    assert t.c.switch()["generation"] != t.gen
    before = t.c.state()
    rc, err = t.call_b(t.n)
    t.c.check_refused(subprocess.CompletedProcess([], rc, "", err), before, "LR007", "generation")
    assert t.rows() == 0


# ------------------------------------------------------------ AT-F33
def matrix(clones, fn: str) -> List[Tuple[str, int, str]]:
    """Case 0 and AT-LR006-1 to -6, each on a clone of its own, with the
    fresh-base resend after each 40001 or 55P03, run twice. Returns every
    session's outcome, and checks one row for W after each case."""
    seen: List[Tuple[str, int, str]] = []
    runs = [lambda t: case_0(t)]
    runs += [lambda t, v=v: lr006_1(t, v) for v in ("held", "whole")]
    runs += [lambda t, b=b: lr006_2(t, b) for b in ("stale-base", "fresh-base")]
    runs += [lambda t, lv=lv: lr006_3(t, lv, resend=True) for lv in ("SERIALIZABLE", "REPEATABLE READ")]
    runs += [lambda t: lr006_4(t, resend=True), lambda t: lr006_5(t, resend=True)]
    runs += [lambda t, v=v: lr006_6(t, v) for v in ("rollback", "idle-bound")]
    for _ in range(2):
        for run in runs:
            t = two(clones, fn)
            run(t)
            seen += t.outcomes
            if fn == "commit_write":
                assert t.rows() == 1, f"{t.rows()} rows for W"
                assert t.c.value(f"SELECT count(*) = count(DISTINCT write_id) FROM {REGISTER}.journal;") == "t"
    return seen


def test_no_interleaving_of_two_attempts_of_one_write_reaches_23505(clones):
    """Every B call ends committed, LR006, 40001 or 55P03; A's committed,
    rolled back, or 25P03; 23505 occurs in no session's output; one row for
    W after each case."""
    seen = matrix(clones, "commit_write")
    for who, rc, err in seen:
        allowed = {"committed", "LR006", "40001", "55P03"} if who == "B" else {"committed", "25P03"}
        assert code_of(rc, err) in allowed, (who, rc, err[:300])
    assert not any("23505" in err for _, _, err in seen)


def test_the_no_lookup_control_reaches_23505_so_the_oracle_can_fail(clones):
    """The same matrix against the no-lookup control shows 23505 on
    `journal_write_id_key` at least once, or the oracle above could not
    have caught the branch."""
    seen = matrix(clones, "control")
    hits = [err for _, _, err in seen if "23505" in err and "journal_write_id_key" in err]
    print(f"[T251 control] 23505 on journal_write_id_key: {len(hits)}")
    assert hits, "the control never reached 23505"
