# SPDX-License-Identifier: Apache-2.0
"""TEST C5: THE SQL REGISTER'S READERS (feature 007, T217, L2-N4; the test
plan's AT-C5; R29; FR-033, FR-034, FR-036, FR-059).

This module supersedes lane 5's seed of the same name (T502 part 1,
`refs/l5/T502`), and keeps its one test, `lanes --decide`, by name.

WHAT IT HOLDS, by its five sources:

  * AT-C5's sixteen (the test plan, "The readers' table, the one-call
    failure, and the callers' default arms"): each reader by the design's
    S3 table with the store unreachable; each mirror read's `read: mirror`
    line; the `none` arms; the read door's classification, a hygiene test;
    the callers that act on a listing; one failed call anywhere in a caller's
    read sequence; `lane-start`'s seven read arms at 75 and 3, and at 69; the
    other callers' arms (lane 4's table, "The callers' default arms (Q9)");
    the writer's printed rerun relayed on a 3; an expectation's 2 at
    `lane-start`'s last write, under a seq base, with its twin under an
    `@files` base, a note, a stamp and a launch (ERR-56; lane 3, #165
    6871338814), and ERR-56's second case, an `@files` base whose re-read
    answers a seq base, which dies (lane 4, #165 6879449852), and its
    row-making 2, a new lane's under an `@files` base, which dies too (lane
    4, #165 6880188792);
    `register-row-local`; `lane-worktrees`' reads; `--index` on
    primary; and `managed-projection`.
  * Lane 1's three (L1v4.5's T113 and T114): `guard_second_read_at`,
    `log_key_hex_slot` and `journal_last_pickaxe`, each `lanes-index`'s own,
    on a real engine.
  * Lane 5's nine (A5; T504 to T506 and T509), their guessed names kept.
  * Lane 4's two read verbs (R29; GB section 4.3; T401), `register-text` and
    `register-grep`, with T401's two exit-2 cases each (O21a), and
    `register-grep`'s one snapshot and quoted names on primary (lane 3's Q2
    and Q3, #165 6851977580).
  * Lane 4's `key()` trim (T259; R31; GB section 4.3; T426): the one test that
    asks `retired-identity` about spellings that differ only past the
    sixteenth digit, in files mode and on primary.
  * Lane 2's T235 (F13b's proposed task, for lane 3 to place; lane 5's
    choice (b), #165 6778955065): on primary, T505's three read sites,
    `known_lanes`, `remote_log_events` and `worktree_rows`, read the store and
    never git, by the fake `git`'s argv log, on a real engine; and its
    moved-head ids, T505's two reruns where the head moves under a read, on
    the stub door (lane 5's proposal, #165 6860943489; lane 3, 6861148117).

THE ARMS' IDS ARE THEIR LINES AT `2a057a6d`, as the test plan names them (the
block, T217), so they move with slices 1a and 1b and are re-cited at each
landing. `test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_
table_gives` names each arm's script first (lane 4's question 2, #165
6752694348), `<script>-<lines at 2a057a6d>-<code>`, so `-k
'the_other_callers_arms and lane-end'`, `and lane-handoff`, `and
skill-handoff`, `and skill-restart`, `and lane-rename`, `and lane-worktrees`
and `and lane-start` each select one script's arms; the bare `lane` script's
arms are `lane-416`, `lane-444`, `lane-1058` and `lane-1144`, which a word
selects by its line (`and (lane-416 or lane-444 or lane-1058 or lane-1144)`),
since `lane-` alone also matches every other script's. Each arm's `Arm`
names its line at the base this module was built on (`a2073eae`, with
T207c), found by its text at `2a057a6d`.

TWO STORES, ONE REGISTER. Every primary case here runs the CHECKOUT's
`lanes-edit.sh`, copied beside the contract's stub `lanes-index` (T207's
`contract_stub`, CLI4.5 section 6's copy rule, at drafts 4.10 and 4.11 since
T207c), on a workstation whose configuration says `mode=primary`. The stub's
register (the "store") holds the git register's files plus one row the git
register lacks, `STORE_ONLY_LANE`; so an answer that names it came from the
store, and one that does not came from the mirror. A small wrapper in front
of the stub (`DOOR_WRAPPER`) counts the register calls and fails the ones a
case names, the way the store fails when it cannot be reached: 69, `mode
primary` on stdout, and the cause on stderr (CLI4.5 section 3.6's exits).
That is the one-call failure's counter, at the `lanes-index` seam: the fake
`psql`'s own counter is the real `lanes-index`'s, which lane 1's three use.

THE ARMS' WRAPPER (AT-C5's fixture). `ARM_EDIT` is a `LANES_EDIT` that runs
the checkout's `lanes-edit.sh` for every verb but the one under test, which
exits the code under test and prints nothing on stdout; for the rerun cases
it prints the writer's rerun line on stderr. It logs each call of the verb
under test, so every arm case first asserts that its arm was REACHED, and a
case that never reaches its arm fails on that, never vacuously.

NO NETWORK. Every remote is a bare repository under `tmp_path`, `tmux`,
`claude` and `gh` are fakes, and `$HOME` is temporary. The real-engine cases
take `pg` from `tests/pgcluster.py` and skip where no PostgreSQL 16 is found,
unless `OPENREPOTOOLS_REQUIRE_PG=1`.

WHAT EACH WAITS FOR (the block's Order): L4-A1, L5-A4 and L5-A5; lane 1's
three for L1v4.5's T113 and T114; lane 5's for T504 to T506 and T509; the
`--decide` test for T502; the read verbs' for lane 4's T401, the one-snapshot
and quoted-name cases for its round on lane 3's Q2 and Q3 (#165 6851977580),
`8d72e579`;
the arms for
lane 4's T402 to T408; `key()`'s trim, on primary only, for lane 4's T426;
T235's for lane 5's T505, its three door forms included, whose oracles are
lane 3's batch 7 (#165 6780364102), by batch 5's answers 3 and 4; and its
moved-head notes id for T505 round 2b's B.
Every case on `RealRegister` (lane 1's three and `managed-projection`'s RE
case) also fails until lane 2's T227 (`tmpl` built by the bootstrap) and
T228 (the `lanes_w_fx` and `lanes_r_fx` logins), each by the fixture's own
assertion (T217h).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import sql_register_helpers as helpers
from conftest import REPO
from test_lane_start_claude_current import FAKE_CLAUDE_CURRENT, Sandbox, _write
from test_lanes_index import (UUID_A1, UUID_A1B, UUID_A2, UUID_M1, Estate,
                              estate, load_indexer)

__all__ = ["estate"]  # the fixture, imported so that pytest finds it here

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                                 reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280; task sets version 12b's rule 11, #165
#: 6877673742), TEMPORARY: T281 removes it. The gate in `tests/conftest.py`
#: skips each id until every task its row names has landed (the reader is
#: `tests/sql_register_gate.py`). Written from T217's Order (tasks:2055 at
#: lane 3's commit 17, `204145ae`), T235's (:2267) and T259's (:2469), as
#: lane 2's plan GP-24 v2 gives it, with lane 3's ruling on T217's lane 5
#: clause (#165 6877365776): each id of the 19 functions a lane 5 verify
#: selects waits for the tasks that lane 2's per-id verdict rows give it
#: (AN11a's and AN13a's), and for T504, T505, T506 and T509 where it has
#: none. T504 to T506 are in the Order's own list too (L5-A5), so those rows
#: drop T509 where they do not name it, and add T502 to the listing callers'
#: two ids and T507 to the reader table's `[guard]`.
SQL_REGISTER_GATE_TABLE = {
    "test_69_refuses_at_canon_lane_and_session_lane_and_stays_a_note_at_the_other_four_arms": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_75_and_3_refuse_the_launch_at_each_lane_start_arm": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_caller_that_acts_on_a_listings_answer_refuses_69_where_the_store_is_unreachable": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T502", "T504", "T505", "T506", "T508", "T509"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_a_carry_on_act_names_lane_start_no_launch_on_a_69_or_75_under_a_seq_base": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_none_class_arm_makes_no_register_call_with_the_store_unreachable": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_a_primary_reader_makes_one_prefetch_and_every_read_site_reads_its_cache_at_one_n": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_a_read_site_with_no_prefetched_file_makes_one_more_register_read_and_never_a_git_read": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_an_expectation_2_at_lane_starts_last_write_dies": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_an_expectation_2_at_lane_starts_last_write_that_makes_a_row_under_an_at_files_base_dies": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; ERR-56's row-making 2, its twin's row
    "test_an_expectation_2_at_lane_starts_last_write_under_an_at_files_base_notes_stamps_and_launches": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_an_expectation_2_at_lane_starts_last_write_under_an_at_files_base_whose_reread_answers_a_seq_base_dies": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; ERR-56's second case, its twin's row (T217zu)
    "test_each_mirror_read_prints_its_line_and_keeps_its_exit": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508", "T509"),  # T217; tasks:2055
    "test_each_reader_follows_the_table_when_the_store_is_unreachable": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508", "T509"),  # T217; tasks:2055
    "test_every_dispatcher_arm_is_classified_for_the_read_door": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_guard_second_read_at_its_head_writes_one_log_and_fails_open": ("T113", "T114", "T227", "T228", "T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_index_flag_on_primary_changes_nothing_and_prints_no_index_line": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508", "T509"),  # T217; tasks:2055
    "test_journal_last_pickaxe_finds_the_newest_entry_that_changes_the_keys_count": ("T113", "T114", "T227", "T228", "T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_lane_worktrees_register_reads_go_through_a_verb_and_refuse_69": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_lanes_accepts_decide_and_reads_as_without_it": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T502", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_lanes_fetch_on_primary_prints_no_no_fetch_note": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508", "T509"),  # T217; tasks:2055
    "test_log_key_hex_slot_holds_a_key_outside_the_class_and_is_never_cached": ("T113", "T114", "T227", "T228", "T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_log_sync_on_primary_makes_no_fetch_and_no_flush": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_managed_projection_answers_0_1_8_from_sql_as_files_mode_does": ("T227", "T228", "T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508", "T509"),  # T217; tasks:2055
    "test_managed_projection_with_the_database_unreachable_exits_1_never_legacy": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_on_primary_known_lanes_remote_log_events_and_worktree_rows_read_the_store_and_never_git": ("T227", "T228", "T505"),  # T235; tasks:2267
    "test_on_primary_remote_log_events_and_worktree_rows_read_again_when_the_head_moves": ("T505",),  # T235; tasks:2267
    "test_one_failed_call_anywhere_in_a_callers_read_sequence_never_fails_open": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508", "T509"),  # T217; tasks:2055
    "test_register_grep_on_primary_answers_one_snapshot_and_69_after_three_moved_runs": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_register_grep_on_primary_prints_each_path_as_git_grep_does_under_gits_defaults": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_register_grep_prints_what_git_grep_prints_and_1_with_no_match": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_register_row_local_reads_the_database_on_primary_and_is_69_never_8": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_register_text_answers_the_bytes_the_scripts_read_today_and_69_on_a_failed_read": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_retired_rows_key_trims_leading_zeros_as_text_on_primary": ("T426",),  # T259; tasks:2469
    "test_swapped_ranks_through_journal_last_on_primary": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_the_flush_helper_drops_the_whole_read_family": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_the_lanes_footer_on_primary_names_the_register_and_claims_no_local_read": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508", "T509"),  # T217; tasks:2055
    "test_the_local_file_unions_are_skipped_on_primary": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_read_mirror_variable_lowers_each_read_that_names_the_lane_on_primary": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T508"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-end-2490]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T430", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-handoff-2878]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T429", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-handoff-2890]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T429", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-handoff-2913]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T429", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-start-3851]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-start-3872]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-start-3909]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-start-3989]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-start-4022]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3[lane-start-4181]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_each_reader_follows_the_table_when_the_store_is_unreachable[guard]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506", "T507", "T508", "T509"),  # T217; tasks:2055; lane 2's per-id rows (AN11a, AN13a), lane 3's 6877365776
    "test_one_failed_call_anywhere_in_a_callers_read_sequence_never_fails_open[lane-rename]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T415", "T422", "T504", "T505", "T506", "T508", "T509"),  # T217; tasks:2055
    "test_retired_rows_key_trims_leading_zeros_as_text_on_primary[files]": (),  # T259; [files] passes at the base; lane 3's 6894592205
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-1144-3]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T432", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-1144-69]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T432", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-1144-75]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T432", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-end-2490-3]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T430", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-end-2490-69]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T430", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-end-2490-75]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T430", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-handoff-2817-3]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T429", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-handoff-2817-69]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T429", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-handoff-2817-75]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T429", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-rename-241-3]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T433", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-rename-241-69]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T433", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-rename-241-75]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T433", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-start-2511-2512-3]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-start-2511-2512-69]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
    "test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives[lane-start-2511-2512-75]": ("T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T428", "T504", "T505", "T506", "T508"),  # T217; tasks:2055
}

LANES_EDIT = REPO / "lanes-edit.sh"

#: THE STORE'S OWN ROW: a lane the store's `lanes/LANES.md` holds and the git
#: register does not, so a reader's answer says which store answered.
STORE_ONLY_LANE = "repoS-1"
STORE_ONLY_UUID = "99999999-0001-4000-8000-000000009001"
STORE_ONLY_ROW = (f"| `{STORE_ONLY_LANE}` | harness `{STORE_ONLY_UUID}` | Eagle / test / brett "
                  f"| 2026-10-05T00:00Z | none | handoffs/{STORE_ONLY_LANE}.md "
                  f"| LIVE · 2026-10-05T00:00:00Z · a row only the store holds |")
STORE_ONLY_LOG = (f"STARTED — lane {STORE_ONLY_LANE}, session {STORE_ONLY_UUID}@Eagle, "
                  f"2026-10-05T00:00:00Z, lane:{STORE_ONLY_LANE} → home opensoft/repoS; "
                  f"dir /work/repoS\n")

#: THE STORE UNREACHABLE (CLI4.5 section 3.6's exits, forms 1 and 3): a
#: failed direct read is 69, and the first stdout line is the mode.
UNREACHABLE_EXIT = 69
UNREACHABLE_STDERR = ("lanes-index: register read: refuse db could not connect to server: "
                      "No such file or directory (the test's store is unreachable)\n")

#: The `read: mirror` line (design S3, "The mirror reads"): stderr, never
#: stdout, `read: mirror at <sha12>, <k> sequences behind or unknown (sql
#: unreachable: <why>)`.
MIRROR_LINE = re.compile(r"^read: mirror at [0-9a-f]{12}, .*$", re.M)

#: THE DOOR'S WRAPPER: `lanes-index` beside the copied `lanes-edit.sh`. It
#: logs every call, counts the register calls (every call but `mode` and the
#: derived index's `sync` nudge), and fails those `lanes-index.fail` names:
#: `{"calls": [k, ...]}` or `{"all": true}`, optionally only for some forms
#: (`"forms": [1, 3]`), with the exit, stdout and stderr given. `"narrow":
#: "register,aliases"` makes a form-1 prefetch fetch only those members (a
#: read site with no prefetched file). `"move_each": {"key": k, "times": t,
#: "path": p, "line": l}` moves the store's head by one seq at each of the
#: first `t` form-3 reads of `--log-key=<k>`, before the store answers it,
#: appending `l % <the move's number>` to `p`, which the first move makes where
#: `p` is absent: a write that lands between a reader's calls (T401's one
#: snapshot, T217zh; T505's two reruns, T235e). With `"generation": true` the
#: move keeps `n` and gives the store a new generation instead, the append
#: made in the image at `n`: a new generation whose head lands on the same `n`
#: (T217zh's `[generation-moved]`). Every other call is the contract stub's,
#: in `store/`.
DOOR_WRAPPER = r'''#!/usr/bin/env python3
# THE DOOR'S WRAPPER (T217): counts and fails register calls, else the stub.
import fcntl, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "store", "lanes-index")
args = sys.argv[1:]


def form(argv):
    if argv[:2] != ["register", "read"]:
        return 0
    rest = set(a.split("=", 1)[0] for a in argv[2:])
    if "--at" in rest:
        return 4
    if "--for" in rest:
        return 2
    if "--since" in rest:
        return 3
    return 1


def caller_verb():
    """The `lanes-edit.sh` verb whose process (or subshell) called this one."""
    try:
        with open("/proc/%d/cmdline" % os.getppid(), "rb") as handle:
            argv = [a.decode("utf-8", "replace") for a in handle.read().split(b"\0")]
    except OSError:
        return ""
    for i, a in enumerate(argv[:-1]):
        if a.endswith("lanes-edit.sh"):
            return argv[i + 1]
    return ""


counted = args[:1] not in (["mode"], ["sync"])
with open(os.path.join(HERE, "lanes-index.calls"), "a+", encoding="utf-8") as log:
    fcntl.flock(log, fcntl.LOCK_EX)
    log.seek(0)
    number = sum(1 for line in log if json.loads(line)["counted"]) + (1 if counted else 0)
    log.write(json.dumps({"argv": args, "counted": counted, "k": number if counted else 0,
                          "form": form(args), "verb": caller_verb()}) + "\n")
try:
    with open(os.path.join(HERE, "lanes-index.fail"), encoding="utf-8") as handle:
        fail = json.load(handle)
except FileNotFoundError:
    fail = {}
if os.environ.get("T217_DOOR_FAIL") == "all":       # the arms' real failure, one process
    fail = dict(fail, all=True, exit=69, stdout="mode primary\n",
                stderr="lanes-index: register read: refuse db could not connect to server\n")
if counted and fail:
    hit = fail.get("all") or number in fail.get("calls", [])
    if fail.get("forms") and form(args) not in fail["forms"]:
        hit = False
    if hit:
        sys.stdout.write(fail.get("stdout", "mode primary\n"))
        sys.stderr.write(fail.get("stderr", ""))
        sys.exit(int(fail.get("exit", 69)))
MOVED = os.path.join(HERE, "lanes-index.moved")
if fail.get("move") and form(args) == 3 and not os.path.exists(MOVED):
    # The head moves once, between the prefetch and the first second read.
    import hashlib, shutil
    open(MOVED, "w").close()
    state_path = os.path.join(HERE, "store", "lanes-index.state")
    with open(state_path, encoding="utf-8") as handle:
        state = json.load(handle)
    old = os.path.join(HERE, "store", "lanes-index.register", str(state["n"]))
    new = os.path.join(HERE, "store", "lanes-index.register", str(state["n"] + 1))
    shutil.copytree(old, new)
    rows = []
    for path, text in fail["move"].items():
        target = os.path.join(new, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(text.encode("utf-8"))
        rows.append("%s\t1\t%s" % (path, hashlib.sha256(text.encode("utf-8")).hexdigest()))
    state["n"] += 1
    state["journal"]["00000000-0000-4000-8000-%012d" % state["n"]] = {
        "seq": state["n"], "lane": "repoA-1", "verb": "log", "args_sha256": "0" * 64,
        "workstation": "Eagle", "generation": state["generation"], "files": rows}
    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
EACH = fail.get("move_each")
if EACH and form(args) == 3 and "--log-key=" + EACH["key"] in args:
    # The head moves at each of the first `times` reads of the key, one seq
    # each, before the store answers the read (T401's one snapshot); or,
    # with `generation`, its generation moves and its `n` stays.
    import hashlib, shutil, uuid
    done_path = os.path.join(HERE, "lanes-index.moves")
    try:
        with open(done_path, encoding="utf-8") as handle:
            done = int(handle.read().strip() or 0)
    except FileNotFoundError:
        done = 0
    if done < int(EACH["times"]):
        done += 1
        with open(done_path, "w", encoding="utf-8") as handle:
            handle.write("%d\n" % done)
        state_path = os.path.join(HERE, "store", "lanes-index.state")
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)
        old = os.path.join(HERE, "store", "lanes-index.register", str(state["n"]))
        if EACH.get("generation"):
            new = old
            state["generation"] = str(uuid.uuid4())
        else:
            new = os.path.join(HERE, "store", "lanes-index.register", str(state["n"] + 1))
            shutil.copytree(old, new)
        target = os.path.join(new, EACH["path"])
        data = b""
        if os.path.exists(target):                    # absent at n: the move makes it
            with open(target, "rb") as handle:
                data = handle.read()
        data += (EACH["line"] % done).encode("utf-8")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
        if not EACH.get("generation"):
            state["n"] += 1
            state["journal"]["00000000-0000-4000-8000-%012d" % state["n"]] = {
                "seq": state["n"], "lane": "repoA-2", "verb": "log", "args_sha256": "0" * 64,
                "workstation": "Eagle", "generation": state["generation"],
                "files": ["%s\t1\t%s" % (EACH["path"], hashlib.sha256(data).hexdigest())]}
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
if fail.get("narrow") and form(args) == 1:
    kept, skip = [], False
    for i, a in enumerate(args):
        if skip:
            skip = False
            continue
        if a == "--all":
            kept += ["--files", fail["narrow"]]
        elif a == "--files":
            kept += ["--files", fail["narrow"]]
            skip = True
        else:
            kept.append(a)
    args = kept
os.execv(STORE, [STORE] + args)
'''

#: THE ARMS' WRAPPER, a `LANES_EDIT` (AT-C5's fixture). `ARM_VERB` is the
#: verb under test; `ARM_MATCH`, where set, a glob its other arguments must
#: match; `ARM_NTH`, where set, the one call of it (counted from 1) that
#: fails. That call exits `ARM_CODE`, prints `ARM_STDERR` on stderr and
#: nothing on stdout, and is logged to `ARM_LOG`; every other call is the
#: real `lanes-edit.sh` at `ARM_REAL`. `ARM_REAL_FAIL`, where set, makes that
#: call the REAL verb with every store read it makes failing (the door's
#: `T217_DOOR_FAIL=all`), for a verb whose failed read has its own answer,
#: such as `managed-projection`'s 1 (lane 3's ruling, #165 6754439281, item
#: 6). `ARM_REREAD_FAIL`, where set, makes every LATER call of it, after the
#: one that fails, the REAL verb with every store read failing the same way,
#: logged to `ARM_LOG.reread`: the caller's re-read meets the store still
#: down, as a `69)` arm's re-read under `LANES_READ_MIRROR=1` must, since a
#: mirror read prints `read: mirror …` only where the read failed (Y:4895;
#: T217zg, lane 4's triage, #165 6850919392). `ARM_FAKE_VERB`, where set, is one
#: more verb the wrapper answers itself, 0 with `ARM_FAKE_OUT`: a scenario's
#: fact a sandbox cannot make, such as a live session in this window, which
#: `window-session` reads from a live process's record. `ARM_VERB` may name
#: several verbs joined by `|`, for a write one build makes as its own verb
#: and another carries in a call of another verb (`lane-start`'s writes in
#: `start-record`'s one call, lane 4's T428). `ARM_ACT_BASE`, where set, is
#: the base the wrapper answers `act-begin` with, 0, logging each such call
#: to `ARM_LOG.act`: an act's seq base, which only primary prints.
#: `ARM_ACT_BASE_AGAIN`, where set, answers every `act-begin` after the first
#: in its place: ERR-56's re-read after an `@files` 2 finding a seq base.
ARM_EDIT = r'''#!/usr/bin/env bash
# THE ARMS' WRAPPER (T217; the test plan's AT-C5 fixture).
if [ -n "${ARM_FAKE_VERB-}" ] && [ "${1-}" = "$ARM_FAKE_VERB" ]; then
  printf '%s\n' "${ARM_FAKE_OUT-}"
  exit 0
fi
if [ -n "${ARM_ACT_BASE-}" ] && [ "${1-}" = act-begin ]; then
  printf '%s\n' "$*" >> "$ARM_LOG.act"
  if [ -n "${ARM_ACT_BASE_AGAIN-}" ] && (( $(wc -l < "$ARM_LOG.act") > 1 )); then
    printf '%s\n' "$ARM_ACT_BASE_AGAIN"
  else
    printf '%s\n' "$ARM_ACT_BASE"
  fi
  exit 0
fi
if [[ "|${ARM_VERB-}|" == *"|${1-}|"* ]]; then
  arm_rest="${*:2}"
  # shellcheck disable=SC2053
  if [ -z "${ARM_MATCH-}" ] || [[ "$arm_rest" == $ARM_MATCH ]]; then
    arm_n=$(( $(cat "$ARM_LOG.count" 2>/dev/null || echo 0) + 1 ))
    printf '%s\n' "$arm_n" > "$ARM_LOG.count"
    if [ -z "${ARM_NTH-}" ] || [ "$arm_n" = "$ARM_NTH" ]; then
      printf '%s\n' "$*" >> "$ARM_LOG"
      if [ -n "${ARM_REAL_FAIL-}" ]; then
        # The verb's REAL answer to a failed read: every store read it makes fails.
        T217_DOOR_FAIL=all exec bash "$ARM_REAL" "$@"
      fi
      [ -z "${ARM_STDERR-}" ] || printf '%s\n' "$ARM_STDERR" >&2
      exit "$ARM_CODE"
    fi
    if [ -n "${ARM_REREAD_FAIL-}" ] && [ "$arm_n" -gt "${ARM_NTH:-0}" ]; then
      # A later call, the caller's re-read: the REAL verb, the store still down.
      printf '%s\n' "$*" >> "$ARM_LOG.reread"
      T217_DOOR_FAIL=all exec bash "$ARM_REAL" "$@"
    fi
  fi
fi
exec bash "$ARM_REAL" "$@"
'''

#: The writer's printed rerun on a 3 (AT-C5's fixture, "For the rerun
#: cases"), with the write id and generation a case can find in stderr.
RERUN_WRITE_ID = "77777777-0001-4000-8000-000000007001"
RERUN_GENERATION = "66666666-0001-4000-8000-000000006001"

#: A session id only this checkout's copy of a row holds (the local unions).
LOCAL_SID = "aaaaaaaa-0006-4000-8000-00000000a006"

#: The arms' sandbox's two further lanes' sessions.
UUID_A3 = "aaaaaaaa-0004-4000-8000-00000000a004"
UUID_H1 = "aaaaaaaa-0005-4000-8000-00000000a005"
UUID_N1 = "aaaaaaaa-0007-4000-8000-00000000a007"


def rerun_line(lane: str, argv: str) -> str:
    return (f"LANES_WRITE_ID={RERUN_WRITE_ID} LANES_WRITE_GENERATION={RERUN_GENERATION} "
            f"LANES_LANE={lane} LANES_SESSION={UUID_A1} lanes-edit.sh {argv}")


# ---------------------------------------------------------------- the stores
def render_set(root: Path) -> dict:
    """The render set's files under `root` (a checkout), as `contract_stub`
    takes them: `lanes/LANES.md`, `lanes/aliases.tsv`, each lane log but the
    README, and `lanes/archive/*`."""
    found = {}
    for path in sorted((root / "lanes").rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and helpers.RENDER_SET_PATH.match(rel):
            found[rel] = path.read_bytes()
    return found


class Door:
    """The primary store beside a copied `lanes-edit.sh`: the contract stub
    in `<bin>/store/`, the wrapper `<bin>/lanes-index`, and `mode=primary` in
    the configuration `lanes-index` reads."""

    def __init__(self, bin_dir: Path, register: dict, config: Path):
        self.bin = bin_dir
        self.store = bin_dir / "store"
        lanes = register.get("lanes/LANES.md", b"").decode("utf-8")
        register = dict(register)
        register["lanes/LANES.md"] = (lanes.rstrip("\n") + "\n" + STORE_ONLY_ROW + "\n").encode()
        register[f"lanes/log/{STORE_ONLY_LANE}.md"] = STORE_ONLY_LOG.encode()
        self.register = register
        helpers.contract_stub(self.store, register)
        _write(bin_dir / "lanes-index", DOOR_WRAPPER)
        config.parent.mkdir(parents=True, exist_ok=True)
        # A configuration `load_config` would accept once the constant is flipped (T217h; lane
        # 5's finding 1, #165 6771208498): `register_url=` the writer's login and `reader_url=`
        # the reader's beside it. The stub answers `mode` alone and reads none of it.
        config.write_text("mode=primary\n"
                          f"register_url=postgresql://{RealRegister.WRITER}@localhost:5432/lanes\n"
                          f"reader_url=postgresql://{RealRegister.READER}@localhost:5432/lanes\n",
                          encoding="utf-8")
        config.chmod(0o600)
        self.config = config
        self.psql_dir = bin_dir.parent / "psqlbin"
        _write(self.psql_dir / "psql", helpers.REGISTER_FAKE_PSQL)
        self.psql_log = bin_dir.parent / "psql.log"
        self.psql_answers = bin_dir.parent / "psql-answers.json"
        self.psql_answers.write_text(json.dumps([{"exit": 2, "stderr":
                                                  "psql: error: connection refused\n"}]))

    def env(self) -> dict:
        return {"LANES_INDEX_CONFIG": str(self.config), "FAKE_PSQL_LOG": str(self.psql_log),
                "FAKE_PSQL_ANSWERS": str(self.psql_answers), "LANES_INDEX": None}

    def fail(self, **spec) -> None:
        (self.bin / "lanes-index.fail").write_text(json.dumps(spec), encoding="utf-8")

    def unreachable(self, forms=None) -> None:
        spec = {"all": True, "exit": UNREACHABLE_EXIT, "stdout": "mode primary\n",
                "stderr": UNREACHABLE_STDERR}
        if forms:
            spec["forms"] = forms
        self.fail(**spec)

    def reachable(self) -> None:
        path = self.bin / "lanes-index.fail"
        if path.exists():
            path.write_text("{}", encoding="utf-8")

    def calls(self) -> list:
        path = self.bin / "lanes-index.calls"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def register_calls(self) -> list:
        return [c for c in self.calls() if c["counted"]]

    def forget_calls(self) -> None:
        for name in ("lanes-index.calls",):
            path = self.bin / name
            if path.exists():
                path.write_text("", encoding="utf-8")
        if self.psql_log.exists():
            self.psql_log.write_text("", encoding="utf-8")

    def psql_calls(self) -> list:
        if not self.psql_log.exists():
            return []
        return [line for line in self.psql_log.read_text(encoding="utf-8").splitlines() if line]

    def commit(self, files: dict) -> int:
        """Advance the store's head by one seq holding `files` (render-set
        paths to text, or None to delete), as a committed write would."""
        state_path = self.store / "lanes-index.state"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        old = self.store / "lanes-index.register" / str(state["n"])
        new = self.store / "lanes-index.register" / str(state["n"] + 1)
        shutil.copytree(old, new)
        rows = []
        for path, text in files.items():
            target = new / path
            if text is None:
                if target.exists():
                    target.unlink()
                rows.append(f"{path}\t0\t-")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            data = text.encode() if isinstance(text, str) else text
            target.write_bytes(data)
            import hashlib
            rows.append(f"{path}\t1\t{hashlib.sha256(data).hexdigest()}")
        state["n"] += 1
        state["journal"][f"00000000-0000-4000-8000-{state['n']:012d}"] = {
            "seq": state["n"], "lane": "repoA-1", "verb": "log", "args_sha256": "0" * 64,
            "workstation": "Eagle", "generation": state["generation"], "files": rows}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return state["n"]

    def head(self) -> tuple:
        state = json.loads((self.store / "lanes-index.state").read_text(encoding="utf-8"))
        return state["n"], state["generation"]

    def rows(self, lane: str) -> int:
        """How many rows the store's `lanes/LANES.md` holds for `lane` at its head."""
        path = self.store / "lanes-index.register" / str(self.head()[0]) / "lanes" / "LANES.md"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        return sum(1 for line in text.splitlines() if line.startswith(f"| `{lane}` "))


class Primary:
    """An `Estate` (test_lanes_index's register) whose workstation is
    configured `mode=primary`, with the checkout's `lanes-edit.sh`, `lanes`,
    `repos.tsv` and `lane-start` copied beside the door (CLI4.5:885)."""

    def __init__(self, estate: Estate):
        self.e = estate
        self.bin = estate.root / "primary-bin"
        self.bin.mkdir(parents=True, exist_ok=True)
        for name in ("lanes-edit.sh", "lanes", "repos.tsv", "lane-start", "lane-worktrees"):
            shutil.copy2(REPO / name, self.bin / name)
        self.edit_path = self.bin / "lanes-edit.sh"
        self.door = Door(self.bin, render_set(estate.wip),
                         estate.config / "openRepoTools" / "lanes-index.conf")

    def env(self, extra: dict | None = None) -> dict:
        env = {"LANES_EDIT": str(self.edit_path),
               "PATH": self.e.path_with(self.door.psql_dir)}
        env.update(self.door.env())
        env.update(extra or {})
        return env

    def edit(self, *args, env: dict | None = None, **kw) -> subprocess.CompletedProcess:
        return self.e.run("bash", self.edit_path, *args, env=self.env(env), **kw)

    def files_edit(self, *args, env: dict | None = None, **kw) -> subprocess.CompletedProcess:
        """The same read in files mode: the checkout's own `lanes-edit.sh`,
        no configuration, no door. `XDG_CONFIG_HOME` is empty, so the
        configuration falls to the estate's empty `$HOME/.config`: the
        estate's own names the folder the door's `mode=primary` file is in,
        which lane 1's T113 refuses there with 78 (T217m; lane 5's triage,
        #165 6782743644: `window-lane` answered 69, not the mirror's 8)."""
        merged = {"XDG_CONFIG_HOME": ""}
        merged.update(env or {})
        return self.e.run("bash", LANES_EDIT, *args, env=merged, **kw)

    def script(self, name: str, *args, env: dict | None = None, **kw):
        return self.e.run("bash", self.bin / name, *args, env=self.env(env), **kw)


@pytest.fixture
def primary(estate):
    return Primary(estate)


# ------------------------------------------------- AT-C5: the readers' table
#: THE READERS' TABLE (design S3, "Each reader with the database
#: unreachable"), for each reader that is a `lanes-edit.sh` arm: its argv, the
#: exit with the store unreachable, and whether 8 is barred ("never 8").
#: `lane`, `lane-end` and `lane-rename` are the callers' cases below; the
#: listings are the mirror test's; the guard reads its hook JSON on stdin.
READERS = {
    "who": (("who", "opensoft/repoA#7"), 69),
    "binding": (("binding", "repoA-1"), 69),
    "live-holder": (("live-holder", "repoA-1"), 69),
    "next-free": (("next-free", "repoA"), 69),
    "lane-last": (("lane-last", "repoA-1"), 69),
    "register-row": (("register-row", "repoC-9"), 69),
    "session-lane": (("session-lane", UUID_A2), 69),
    "canon-lane": (("canon-lane", "repoA-1"), 69),
    "resolve-home": (("resolve-home", "repoA-1"), 69),
    "register-row-local": (("register-row-local", "repoC-9"), 69),
    "managed-projection": (("managed-projection", "repoM-1"), 1),
    "guard": (("guard",), 2),
}

#: THE GUARD'S SESSION (AN13a's B3). The hook's JSON is compact, as the harness
#: sends it, since the guard's `jstr` reads `"cwd":"<dir>"` with no blank after
#: the colon; and the guard runs in the lane's window, `repoA-2`, whose row names
#: `UUID_A2`, with a live session record whose `cwd` is under `$HOME/projects`.
#: Without that record it refuses 2 before any read, and T507's prefetch comes
#: after the session-record check (lane 3's T507 ruling (1), #165 6783977598).
#: T203c's `helpers.guard_session` makes both, as W4a's T215e runs AT-P3's
#: guard; it is looked up only when the case runs, so the module loads on a
#: tree whose helpers predate T203c.
GUARD_BIN = "guard-bin"


@pytest.mark.parametrize("reader", sorted(READERS))
def test_each_reader_follows_the_table_when_the_store_is_unreachable(primary, reader):
    """Each reader in the design's S3 table, with the store unreachable,
    exits the table's code (69; 1 for `managed-projection`; 2 for the
    guard), prints no answer on stdout, and never says 8 for a read that
    failed. The door asked the store first: the read that failed is the
    store's, not a git read's."""
    argv, code = READERS[reader]
    primary.door.unreachable()
    if reader == "guard":
        with helpers.guard_session(primary.e.home, primary.e.root / GUARD_BIN, primary.e.wip,
                                   session_id=UUID_A2) as session:
            result = primary.e.run("bash", primary.edit_path, *argv,
                                   env=session.env(primary.env(), LANES_LANE=session.window),
                                   input_text=session.hook_input())
    else:
        result = primary.edit(*argv)
    assert primary.door.register_calls(), \
        (reader, "the door never asked the store", result.returncode, result.stderr)
    assert result.returncode == code, (reader, result.returncode, result.stdout, result.stderr)
    assert result.returncode != 8, (reader, result.stderr)
    if reader != "guard":
        assert result.stdout == "", (reader, result.stdout)
    if reader == "managed-projection":
        assert "UNKNOWN" in result.stderr, result.stderr
        assert "legacy" not in result.stdout + result.stderr, result.stderr


#: THE LISTINGS AND THE OFFLINE READS (AT-C5's oracle): each prints `read:
#: mirror at <sha12>, …` on stderr and exits with its own code. The fourth,
#: the launcher's bare window reads, is `swapped`, the launcher's read of this
#: workstation's swapped lanes, made before any lane is bound. It answers 0
#: only where a lane's last lane-kind line is a `PAUSED` whose payload begins
#: `swap;` and names this workstation, and 8 where none is, so the case seeds
#: `SWAP_LANE` (AN13a's B4). (`window-lane` needs a window: without one it is
#: a usage refusal, 64.)
MIRROR_READS = {
    "lanes": ("lanes",),
    "history": ("history", "--all"),
    "session-start": ("session-start",),
    "launcher-window-reads": ("swapped",),
}

#: The swapped lane `[launcher-window-reads]` seeds in the git register, which
#: the mirror and files mode read: a log whose last lane-kind line is a swap's
#: `PAUSED` on this workstation (Eagle), in the shape `swapped` reads.
SWAP_LANE = "repoW-1"
SWAP_UUID = "aaaaaaaa-0012-4000-8000-00000000a012"
SWAP_LOG = (f"STARTED — lane {SWAP_LANE}, session {SWAP_UUID}@Eagle, 2026-10-01T04:00:00Z, "
            f"lane:{SWAP_LANE} → home opensoft/repoW; dir /work/repoW; profile team-01c\n"
            f"PAUSED — lane {SWAP_LANE}, session {SWAP_UUID}@Eagle, 2026-10-01T05:00:00Z, "
            f"lane:{SWAP_LANE} → swap; window sess:2 @5; workstation Eagle; dir /work/repoW; "
            f"profile team-01c; agent claude; transcript {SWAP_UUID}\n")


def seed_swapped_lane(estate: Estate) -> None:
    """`SWAP_LANE`'s log, committed and pushed to the git register."""
    path = estate.wip / "lanes" / "log" / f"{SWAP_LANE}.md"
    path.write_text(SWAP_LOG, encoding="utf-8")
    estate._git("add", "--", str(path.relative_to(estate.wip)))
    estate._git("commit", "-q", "-m", f"a swapped lane, {SWAP_LANE}")
    estate._git("push", "-q", "origin", "main")


@pytest.mark.parametrize("listing", sorted(MIRROR_READS))
def test_each_mirror_read_prints_its_line_and_keeps_its_exit(primary, listing):
    """With the store unreachable, a mirror read reads the mirror: it prints
    the `read: mirror` line on stderr, never on stdout, and exits as the same
    read does in files mode, with the mirror's answer (no row only the store
    holds). `session-start` and the bare window reads exit 0; for the
    window reads the git register holds a swapped lane, which files mode
    names first, as the scenario's control (AN13a's B4)."""
    argv = MIRROR_READS[listing]
    env = {"LANES_READ_MIRROR": "1"} if listing == "launcher-window-reads" else None
    if listing == "launcher-window-reads":
        seed_swapped_lane(primary.e)
    files = primary.files_edit(*argv, env=env)
    if listing == "launcher-window-reads":
        assert files.returncode == 0 and SWAP_LANE in files.stdout, (
            listing, "the scenario's control: files mode does not name the swapped lane",
            files.returncode, files.stdout, files.stderr)
    primary.door.unreachable()
    result = primary.edit(*argv, env=env)
    assert primary.door.register_calls() or listing == "session-start", \
        (listing, "the door never asked the store", result.stderr)
    assert MIRROR_LINE.search(result.stderr), (listing, result.stderr)
    assert not MIRROR_LINE.search(result.stdout), (listing, result.stdout)
    assert result.returncode == files.returncode, (listing, result.returncode, files.returncode,
                                                   result.stderr)
    assert STORE_ONLY_LANE not in result.stdout, (listing, result.stdout)
    if listing in ("session-start", "launcher-window-reads"):
        assert result.returncode == 0, (listing, result.stderr)


#: THE `none` ARMS (design, "The readers' SQL path": the L and F arms), each
#: with an argv it answers today.
NONE_ARMS = {
    "workstation": ("workstation",),
    "fetch-age": ("fetch-age",),
    "window-session": ("window-session", "testsess:@1"),
    "transcript-holders": ("transcript-holders", UUID_A1),
}


@pytest.mark.parametrize("arm", sorted(NONE_ARMS))
def test_a_none_class_arm_makes_no_register_call_with_the_store_unreachable(primary, arm):
    """A `none` arm has no door: with the store unreachable it makes no
    register call and runs no `psql`, and answers as it does in files mode.
    The control: in the same estate, a decide arm asks the store, so the
    silence is the class's and not an unconfigured workstation's."""
    primary.door.unreachable()
    control = primary.edit("register-row", "repoA-1")
    assert primary.door.register_calls(), \
        ("the configuration is not live: a decide arm asked nothing", control.stderr)
    primary.door.forget_calls()
    argv = NONE_ARMS[arm]
    files = primary.files_edit(*argv)
    result = primary.edit(*argv)
    assert primary.door.calls() == [], (arm, primary.door.calls())
    assert primary.door.psql_calls() == [], (arm, primary.door.psql_calls())
    assert (result.returncode, result.stdout) == (files.returncode, files.stdout), \
        (arm, result.returncode, result.stdout, files.returncode, files.stdout)


#: THE SIX CLASSES (design, "The readers' SQL path"; T504's class table; R46).
CLASSES = ("decide", "mirror", "guard", "projection", "none", "writer")

#: What the table must say for the arms whose class is named in the design
#: and in T504's rows, of the arms every tree has; every other arm must be in
#: exactly one class. T401's `register-text` and `register-grep`, T410's
#: `act-begin`, T427's `start-record` and T502's `guard-bind` are not named
#: here: whichever of T504 and the arm's task lands second adds the arm's
#: row, and the table is held to the dispatcher (T217n; lane 3, #165
#: 6782923063).
NAMED_CLASSES = {
    "lanes": "mirror", "history": "mirror", "session-start": "mirror",
    "guard": "guard", "managed-projection": "projection",
    "workstation": "none", "fetch-age": "none", "window-session": "none",
    "transcript-holders": "none", "canon-lane": "decide",
    "who": "decide", "binding": "decide", "register-row": "decide",
    "register-row-local": "decide",
    "add-row": "writer", "set-row-state": "writer", "log": "writer", "claim": "writer",
}

#: THE CLASS TABLE'S FORM (lane 5's answer 12, #165 6746507353): one function
#: before the dispatcher, `reg_class_of`, with one `case` arm per row, in the
#: form `register-text) REG_CLASS=decide ;;`. A row may also set
#: `REG_MIRROR_VAR=1` (item 1's ten arms, and with T504 `lane-last` and
#: `restart-intent`, twelve; ERR-30, #165 6859801732), and `*)` is decide.
CLASS_FUNCTION = re.compile(r"^reg_class_of\(\)\s*\{[^\n]*$(.*?)^\}\s*$", re.M | re.S)
CLASS_ARM = re.compile(r"^\s*([A-Za-z0-9_|*-]+)\)[^\n]*?\bREG_CLASS=['\"]?"
                       r"(decide|mirror|guard|projection|none|writer)\b", re.M)


def dispatcher_arms(text: str) -> list:
    """The arms of `lanes-edit.sh`'s dispatcher: the `case "$cmd" in` that
    holds `who)`, each arm at two spaces' indent, its patterns split on
    `|`."""
    blocks = [m.start() for m in re.finditer(r'^case "\$cmd" in\s*$', text, re.M)]
    for start in reversed(blocks):
        end = re.compile(r"^esac\s*$", re.M).search(text, start)
        body = text[start:end.start() if end else len(text)]
        arms = re.findall(r"^  ([a-z][a-z0-9|-]*)\)", body, re.M)
        if "who" in arms:
            names = []
            for arm in arms:
                names += arm.split("|")
            return names
    return []


def test_every_dispatcher_arm_is_classified_for_the_read_door():
    """THE HYGIENE TEST (AT-C5; R46): every dispatcher arm of `lanes-edit.sh`
    is in exactly one of the six classes of the read door's one table,
    `writer` among them for the write guard's verbs; the arms the design
    and T504 name, of those every tree has (`NAMED_CLASSES`), have the
    class they name; and the table names no arm the dispatcher lacks."""
    text = LANES_EDIT.read_text(encoding="utf-8")
    arms = dispatcher_arms(text)
    assert len(arms) > 50 and "who" in arms, arms
    table = CLASS_FUNCTION.search(text)
    assert table, "lanes-edit.sh has no read door class table (reg_class_of)"
    seen = {}
    for patterns, klass in CLASS_ARM.findall(table.group(1)):
        for arm in patterns.split("|"):
            seen.setdefault(arm, []).append(klass)
    assert seen, ("reg_class_of holds no `<arm>) REG_CLASS=<class> ;;` row", table.group(1))
    default = seen.pop("*", [])
    assert default in ([], ["decide"]), ("the default row must be decide (answer 12)", default)
    twice = {arm: k for arm, k in seen.items() if len(k) != 1}
    assert not twice, ("arms in more than one class", twice)
    missing = sorted(set(arms) - set(seen)) if not default else []
    assert not missing, ("dispatcher arms in no class", missing)
    stray = sorted(set(seen) - set(arms))
    assert not stray, ("classes for arms the dispatcher lacks", stray)
    for arm, klass in NAMED_CLASSES.items():
        assert arm in arms, (arm, "is not a dispatcher arm")
        assert seen.get(arm, default) == [klass], (arm, seen.get(arm, default), klass)
    assert set(k for ks in seen.values() for k in ks) <= set(CLASSES), seen


# ------------------------------------------ the callers that act on a listing
@pytest.mark.parametrize("caller", ["lane", "lane-end-retire-dormant"])
def test_a_caller_that_acts_on_a_listings_answer_refuses_69_where_the_store_is_unreachable(
        primary, caller):
    """`lane` and `lane-end --retire-dormant` act on the `lanes` listing's
    answer, so they pass `--decide` and refuse 69 where the store cannot be
    read, acting on nothing: never the mirror's answer (design S3; R38)."""
    primary.door.unreachable()
    before = primary.e.tip()
    for name in ("lane", "lane-end"):
        shutil.copy2(REPO / name, primary.bin / name)
    if caller == "lane":
        result = primary.script("lane", "--all")
    else:
        result = primary.script("lane-end", "--retire-dormant", "repoA", "--yes")
    lanes_calls = [c["argv"] for c in primary.door.register_calls()]
    assert lanes_calls, (caller, "the listing never reached the store", result.stderr)
    assert result.returncode == 69, (caller, result.returncode, result.stdout, result.stderr)
    assert primary.e.tip() == before, (caller, "the register moved")
    assert "repoA-1" not in result.stdout, (caller, result.stdout)


# ----------------------------------------------------- the one-call failure
#: Each caller's run on primary, from the arms' sandbox: (script, argv).
#: Open point 14: k runs over every call of the run's sequence, or the
#: first `ONE_CALL_SAMPLE` of them and the last, where the sequence is longer.
ONE_CALL_SAMPLE = 12
CALLERS = {
    "lane-start": ("lane-start", ("repoZ", "1")),
    "lane-end": ("lane-end", ("repoA-2",)),
    "lane": ("lane", ("repoA-2",)),
    "lane-handoff": ("lane-handoff", ("--lane", "repoA-2", "the one-call test")),
    "lane-rename": ("lane-rename", ("repoA-2", "repoA-7", "the one-call test", "--no-tmux",
                                    "--no-github")),
}


@pytest.mark.parametrize("caller", sorted(CALLERS))
def test_one_failed_call_anywhere_in_a_callers_read_sequence_never_fails_open(tmp_path, caller):
    """ADV-C5: a store that fails exactly one call, run across each caller's
    read sequence. For each k the caller refuses (or notes, where round 1's 2A
    allows a note), never makes a second row, and where it refused the
    register's rows and logs are unchanged. The sequence is first measured
    with no failure: a caller on primary that makes no register call at all
    has no door yet."""
    world = PrimaryWorld(tmp_path)
    script, argv = CALLERS[caller]
    clean = world.run(script, *argv)
    sequence = world.door.register_calls()
    assert sequence, (caller, "no register call on primary", clean.returncode, clean.stderr)
    ks = list(range(1, len(sequence) + 1))
    if len(ks) > ONE_CALL_SAMPLE:
        ks = ks[:ONE_CALL_SAMPLE] + ks[-1:]
    for k in ks:
        world = PrimaryWorld(tmp_path / f"k{k}")
        before = (world.register_bytes(), world.door.head())
        world.door.fail(calls=[k], exit=UNREACHABLE_EXIT, stdout="mode primary\n",
                        stderr=UNREACHABLE_STDERR)
        result = world.run(script, *argv)
        failed = [c for c in world.door.register_calls() if c["k"] == k]
        if not failed:
            continue  # this run's sequence is shorter: the failure moved its path
        lane = caller_lane(caller)
        rows = max(world.store_rows(lane), world.door.rows(lane))
        assert rows <= 1, (caller, k, "a second row", rows)
        if failed[0].get("verb") == "managed-projection" and caller in ("lane-start", "lane-end"):
            # Lane 3's ruling (#165 6754439281, item 6): projection-class, its
            # failed read is 1, and the caller refuses 1, UNKNOWN, never 69.
            assert result.returncode == 1 and "UNKNOWN" in result.stderr, \
                (caller, k, "managed-projection's failed read", result.returncode,
                 result.stderr[-2000:])
        if result.returncode != 0:
            assert (world.register_bytes(), world.door.head()) == before, \
                (caller, k, "refused, yet wrote")
        else:
            assert "69" in result.stderr or MIRROR_LINE.search(result.stderr), \
                (caller, k, "carried on past a failed read without a word", result.stderr)


def caller_lane(caller: str) -> str:
    return {"lane-start": "repoZ-1", "lane-rename": "repoA-7"}.get(caller, "repoA-2")


# ---------------------------------------------------- the arms' sandbox
class ArmWorld(Sandbox):
    """`test_lane_start_claude_current`'s sandbox (a bare origin, a register
    clone, fake `tmux`, `claude` and `gh`), with every lifecycle script
    copied beside `lanes-edit.sh`, `ARM_EDIT` written beside them, a fake
    `codex` (a second agent, for `lane-start`'s non-`claude` read), and a
    register holding, each with its log:

      * `repoA-1` PAUSED, its log naming its directory and its last PAUSED
        transcript (a resume);
      * `repoA-2` LIVE here (an end, a handoff, a rename);
      * `repoA-3` LIVE on another workstation (`lane`'s `elsewhere` group);
      * `repoH-1` PAUSED, its log naming its home and no directory, where
        `$PROJECTS_ROOT/repoH` does not exist (`lane-start`'s `resolve-home`);
      * `repoN-1` LIVE, a row with no log (`lane-end`'s state-cell read)."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        for name in ("lane-end", "lane", "lane-handoff", "lane-rename", "lane-worktrees",
                     "lanes"):
            shutil.copy2(REPO / name, self.bin / name)
            (self.bin / name).chmod(0o755)
        self.resolver()
        self.arm_log = root / "arm.log"
        self.codex_log = root / "codex.log"
        _write(self.bin / "arm-edit", ARM_EDIT)
        _write(self.fakebin / "codex", f'#!/usr/bin/env bash\nprintf "codex %s\\n" "$*" >> "{self.codex_log}"\n')
        # THE LAUNCHER (`lane`'s `launcher()`, `$PCLAUDE` first, else `lclaude`, `pclaude` or
        # `claude-profile` on PATH): a fake that logs and exits 0, off PATH. The sandbox scrubs
        # `PCLAUDE`, so without it a GitHub runner refuses "no launcher on PATH" and a
        # workstation would exec its own installed launcher (AN11a's latent defect).
        self.launcher_log = root / "launcher.log"
        self.env["PCLAUDE"] = str(_write(
            root / "launcher" / "pclaude",
            f'#!/usr/bin/env bash\nprintf "pclaude %s\\n" "$*" >> "{self.launcher_log}"\nexit 0\n'))
        # `$PROJECTS_ROOT/repoA`, repoA's default directory: where a noted
        # `lane-dir` failure carries a resume on to, so the launch goes on.
        self.default_dir = self.home / "projects" / "repoA"
        self.git("init", "-q", "-b", "main", str(self.default_dir))
        self.git("-C", str(self.default_dir), "remote", "add", "origin",
                 "https://github.com/opensoft/repoA.git")
        rows = [
            f"| `repoA-1` | harness `{UUID_A1}` → `{UUID_A1B}` | Eagle / test / brett "
            f"| 2026-10-01T00:00Z | none | handoffs/repoA-1.md "
            f"| PAUSED · 2026-10-01T01:00:00Z · parked |",
            f"| `repoA-2` | harness `{UUID_A2}` | Eagle / test / brett | 2026-10-01T02:00Z "
            f"| none | handoffs/repoA-2.md | LIVE · 2026-10-01T02:00:00Z · working |",
            f"| `repoA-3` | harness `{UUID_A3}` | Falcon / test / brett | 2026-10-01T02:30Z "
            f"| none | handoffs/repoA-3.md | LIVE · 2026-10-01T02:30:00Z · working elsewhere |",
            f"| `repoH-1` | harness `{UUID_H1}` | Eagle / test / brett | 2026-10-01T03:00Z "
            f"| none | handoffs/repoH-1.md | PAUSED · 2026-10-01T03:30:00Z · parked |",
            f"| `repoN-1` | harness `{UUID_N1}` | Eagle / test / brett | 2026-10-01T04:00Z "
            f"| none | handoffs/repoN-1.md | LIVE · 2026-10-01T04:00:00Z · a row with no log |",
        ]
        lanes = self.wip / "lanes"
        (lanes / "log").mkdir(exist_ok=True)
        with open(lanes / "LANES.md", "a", encoding="utf-8") as handle:
            handle.write("\n".join(rows) + "\n")
        (lanes / "log" / "README.md").write_text("# the object logs\n", encoding="utf-8")
        (lanes / "log" / "repoA-1.md").write_text(
            f"STARTED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:00:00Z, "
            f"lane:repoA-1 → home opensoft/repoA; dir {self.lane_dir}; profile team-01a\n"
            f"PAUSED — lane repoA-1, session {UUID_A1B}@Eagle, 2026-10-01T01:00:00Z, "
            f"lane:repoA-1 → dir {self.lane_dir}; profile team-01a; agent claude; "
            f"transcript {UUID_A1B}\n", encoding="utf-8")
        (lanes / "log" / "repoA-2.md").write_text(
            f"STARTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T02:00:00Z, "
            f"lane:repoA-2 → home opensoft/repoA; dir {self.lane_dir}; profile team-01b\n",
            encoding="utf-8")
        (lanes / "log" / "repoA-3.md").write_text(
            f"STARTED — lane repoA-3, session {UUID_A3}@Falcon, 2026-10-01T02:30:00Z, "
            f"lane:repoA-3 → home opensoft/repoA; dir /work/repoA3; window w:@7\n",
            encoding="utf-8")
        (lanes / "log" / "repoH-1.md").write_text(
            f"STARTED — lane repoH-1, session {UUID_H1}@Eagle, 2026-10-01T03:00:00Z, "
            f"lane:repoH-1 → home opensoft/repoH\n"
            f"PAUSED — lane repoH-1, session {UUID_H1}@Eagle, 2026-10-01T03:30:00Z, "
            f"lane:repoH-1 → swap; agent claude; transcript {UUID_H1}\n", encoding="utf-8")
        self.git("-C", str(self.wip), "add", "-A")
        self.git("-C", str(self.wip), "commit", "-q", "-m", "the arms' register")
        self.git("-C", str(self.wip), "push", "-q", "origin", "main")
        self.git("-C", str(self.ws), "pull", "-q", "--ff-only")

    def arm_env(self, verb: str, code: int, match: str = "", nth: int = 0,
                stderr: str = "") -> dict:
        env = {"LANES_EDIT": str(self.bin / "arm-edit"), "ARM_REAL": str(self.bin / "lanes-edit.sh"),
               "ARM_VERB": verb, "ARM_CODE": str(code), "ARM_LOG": str(self.arm_log),
               "FAKE_CC_PATH": str(self.resolved)}
        if match:
            env["ARM_MATCH"] = match
        if nth:
            env["ARM_NTH"] = str(nth)
        if stderr:
            env["ARM_STDERR"] = stderr
        return env

    def reached(self) -> list:
        return self.arm_log.read_text(encoding="utf-8").splitlines() if self.arm_log.exists() else []

    def run(self, script: str, *args: str, env: dict | None = None,
            cwd: Path | None = None, stdin: str | None = None) -> subprocess.CompletedProcess:
        full = dict(self.env)
        full.setdefault("FAKE_CC_PATH", str(self.resolved))
        for key, value in (env or {}).items():
            if value is None:
                full.pop(key, None)
            else:
                full[key] = value
        return subprocess.run([str(self.bin / script), *args], env=full,
                              cwd=str(cwd or self.lane_dir), capture_output=True, text=True,
                              timeout=180, check=False, input=stdin,
                              stdin=None if stdin is not None else subprocess.DEVNULL)

    def register_bytes(self) -> dict:
        """The register as origin holds it: LANES.md and every log."""
        self.git("-C", str(self.wip), "fetch", "-q", "origin")
        out = self.git("-C", str(self.wip), "ls-tree", "-r", "--name-only", "origin/main",
                       "--", "lanes")
        files = {}
        for path in out.split():
            files[path] = self.git("-C", str(self.wip), "show", f"origin/main:{path}")
        return files

    def store_rows(self, lane: str) -> int:
        text = self.git("-C", str(self.wip), "show", "origin/main:lanes/LANES.md")
        return sum(1 for line in text.splitlines() if line.startswith(f"| `{lane}` "))


class PrimaryWorld(ArmWorld):
    """The arms' sandbox on primary: the copied `lanes-edit.sh` beside the
    door, `mode=primary` configured, and `LANES_EDIT` the copy."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.door = Door(self.bin, render_set(self.wip),
                         self.home / ".config" / "openRepoTools" / "lanes-index.conf")
        self.env.update({"LANES_EDIT": str(self.bin / "lanes-edit.sh"),
                         "PATH": f"{self.door.psql_dir}{os.pathsep}{self.env['PATH']}"})
        for key, value in self.door.env().items():
            if value is None:
                self.env.pop(key, None)
            else:
                self.env[key] = value


# ----------------------------------------------------- the arms' table
class Arm:
    """One arm of lane 4's table ("The callers' default arms (Q9)"): the
    script and argv whose run reaches it, the verb it reads, which call of
    that verb is the arm's (`nth`, counted from 1; `match`, a glob the verb's
    other arguments must match), the arm's line at the base (`base`), the
    world it runs in (`arm`, files mode; `primary`, beside the door), and a
    verb the wrapper answers itself (`fake`, `(verb, line)`)."""

    def __init__(self, script: str, argv: tuple, verb: str, base: str, *, nth: int = 1,
                 match: str = "", world: str = "arm", fake: tuple = (), env: dict | None = None):
        self.script, self.argv, self.verb, self.base = script, argv, verb, base
        self.nth, self.match, self.world, self.fake = nth, match, world, fake
        self.env = env or {}


#: A live session in this window that the row's cell does not hold
#: (`window-session`'s five fields, `\037`-joined): what `lane-start`'s
#: `session-lane` read needs, and a sandbox cannot make from a live process.
WINDOW_SID = "aaaaaaaa-0009-4000-8000-00000000a009"
WINDOW_RECORD = "\037".join([WINDOW_SID, "testsess:@1", "claude", "99999", "team-01a"])

#: `lane-start`'s seven read arms, by their lines at `2a057a6d` (the test
#: plan's ids), each with its line at the base and a run that reaches it.
LANE_START_ARMS = {
    "1154": Arm("lane-start", ("repoA", "1"), "canon-lane", "1161"),
    "1262": Arm("lane-start", ("repoA", "1"), "swapped", "1315"),
    "1271": Arm("lane-start", ("repoA", "1"), "lane-dir", "1324"),
    "1332": Arm("lane-start", ("repoH", "1"), "resolve-home", "1385"),
    "2184-2186": Arm("lane-start", ("repoA", "1"), "session-lane", "2237",
                     fake=("window-session", WINDOW_RECORD)),
    "3079": Arm("lane-start", ("repoA", "2", "--agent", "codex"), "lane-transcript", "3132"),
    "3430": Arm("lane-start", ("repoA", "1"), "lane-transcript", "3483"),
}

#: The 69 arms (the design's table): a 69 refuses at `canon-lane` and
#: `session-lane`, and stays a note at the other four. `:1332` has no 69 row.
LANE_START_69 = {"1154": "refuse", "2184-2186": "refuse", "1262": "note", "1271": "note",
                 "3079": "note", "3430": "note"}

#: THE OTHER CALLERS' ARMS (lane 4's table), each id `<script>-<lines at
#: 2a057a6d>`, its codes, and what it must do: `refuse` (the verb's code,
#: nothing written), `code` (exit with the verb's code, never 1), `mirror`
#: (a `69)` arm that re-reads from the mirror and prints the `read: mirror`
#: line), `rename` (new text for the code), `lread` (the restart skill's
#: refusal, exit 1, for every code).
OTHER_ARMS = {
    "lane-end-930-938": (Arm("lane-end", ("repoA-2",), "canon-lane", "937"), (69, 75, 3), "refuse"),
    "lane-end-2490": (Arm("lane-end", ("repoA-2",), "log", "2543", match="ENDED*"),
                      (69, 75, 3), "code"),
    "lane-worktrees-508-524": (Arm("lane-worktrees", ("add", "repoA-2", "s1", "--dry-run"),
                                   "canon-lane", "508"), (69, 75, 3), "refuse-own-exit"),
    # The two `69)` arms' re-reads meet the store still down (`ARM_REREAD_FAIL`, T217zg): a
    # re-read that reached a readable store answered from it, with no `read: mirror` line.
    "lane-handoff-1463": (Arm("lane-handoff", ("--lane", "repoA-2", "the arms' test"),
                              "canon-lane", "1463", world="primary",
                              env={"ARM_REREAD_FAIL": "1"}), (69,), "mirror"),
    "lane-handoff-2817": (Arm("lane-handoff", ("--late", "--at", "2026-10-01T03:00:00Z", "--lane",
                                               "repoA-2", "the arms' late test"),
                              "log", "2817", match="PAUSED*"), (69, 75, 3), "code"),
    "skill-handoff-112": (Arm("skills/handoff/SKILL.md", ("canon-lane", "repoA-2"), "canon-lane",
                              "112", world="primary", env={"ARM_REREAD_FAIL": "1"}),
                          (69,), "mirror"),
    "skill-restart-70": (Arm("skills/restart/SKILL.md", ("binding", "repoA-1"), "binding", "70"),
                         (69, 75, 3), "lread"),
    "lane-rename-241": (Arm("lane-rename", ("repoA-2", "repoA-7", "the arms' test", "--no-tmux",
                                            "--no-github"), "rename-lane", "241"),
                        (3, 75, 69), "rename"),
    # LANE 3'S RULING (#165 6754439281, item 6; the erratum to Y:5730 and
    # TP:2832): `managed-projection` is projection-class, so a failed read
    # answers 1, and `lane-start` exits 1, UNKNOWN, never 69. Its real 1 is
    # driven, and no 69, 75 or 3 is stubbed (the arm at `:1555`, by its text).
    "lane-start-1555": (Arm("lane-start", ("repoA", "1"), "managed-projection", "1608",
                            world="primary", env={"ARM_REAL_FAIL": "1"}), (1,), "unknown"),
    "lane-start-1641-1643": (Arm("lane-start", ("repoZ", "1"), "register-row", "1694",
                                 match="repoZ-1"), (75, 3, 69), "code"),
    "lane-start-1661-1663": (Arm("lane-start", ("repoA", "1"), "register-row", "1714",
                                 match="repoA-1"), (75, 3, 69), "code"),
    "lane-start-2305": (Arm("lane-start", ("repoA", "1"), "retired-identity", "2358"),
                        (75, 3, 69), "code"),
    "lane-start-2335": (Arm("lane-start", ("repoA", "1"), "lane-last", "2388"), (75, 3, 69), "code"),
    "lane-start-2444": (Arm("lane-start", ("repoA", "1"), "binding", "2497"), (75, 3, 69), "code"),
    "lane-start-2511-2512": (Arm("lane-start", ("repoA", "3", "--request-handoff", "--dir",
                                                "{lane_dir}"),
                                 "request-handoff", "2564"), (75, 3, 69), "code"),
    "lane-start-2534": (Arm("lane-start", ("repoA", "1"), "lane-agent", "2587"), (75, 3, 69), "code"),
    "lane-start-2638": (Arm("lane-start", ("repoA", "1"), "binding", "2691", nth=2),
                        (75, 3, 69), "code"),
    "lane-end-769": (Arm("lane-end", ("--retire-dormant", "repoA", "--yes"), "lanes", "776"),
                     (75, 3, 69), "code"),
    # The same ruling's first sentence: a case where only `managed-projection`'s
    # call fails follows the erratum, so `lane-end:955` drives the real 1 too.
    "lane-end-955": (Arm("lane-end", ("repoA-2",), "managed-projection", "1008",
                         world="primary", env={"ARM_REAL_FAIL": "1"}), (1,), "unknown"),
    "lane-end-1806": (Arm("lane-end", ("repoA-2",), "lane-objects", "1859"), (75, 3, 69), "code"),
    "lane-end-1984": (Arm("lane-end", ("repoN-1",), "register-row", "2037"), (75, 3, 69), "code"),
    "lane-416": (Arm("lane", ("repoA-2",), "lanes", "416"), (75, 3, 69), "code"),
    "lane-444": (Arm("lane", ("repoA-2",), "lane-groups", "444"), (75, 3, 69), "code"),
    "lane-1058": (Arm("lane", ("repoA-3",), "binding", "1088"), (75, 3, 69), "code"),
    "lane-1144": (Arm("lane", ("--request-handoff", "repoA-3"), "request-handoff", "1174"),
                  (75, 3, 69), "code"),
}

OTHER_ARM_CASES = [pytest.param(arm_id, code, id=f"{arm_id}-{code}")
                   for arm_id, (_arm, codes, _kind) in OTHER_ARMS.items() for code in codes]


def skill_function(path: str, name: str) -> str:
    """A skill's shell function by its text: from `<name>() {` at the start of
    a line to the first `}` alone at the start of a line after it."""
    text = (REPO / path).read_text(encoding="utf-8")
    found = re.search(rf"^{re.escape(name)}\(\) *\{{.*?^\}}[ \t]*$", text, re.M | re.S)
    assert found, (path, name, "not found by its text")
    return found.group(0)


def arm_world(tmp_path: Path, arm: Arm) -> ArmWorld:
    return (PrimaryWorld if arm.world == "primary" else ArmWorld)(tmp_path / "w")


def run_arm(world: ArmWorld, arm: Arm, code: int, stderr: str = "") -> subprocess.CompletedProcess:
    """Run `arm`'s script with the verb under test exiting `code` at the
    arm's call, and assert that the arm was REACHED: its call is in the
    wrapper's log, so a case never passes or fails vacuously."""
    env = world.arm_env(arm.verb, code, match=arm.match, nth=arm.nth, stderr=stderr)
    if arm.fake:
        env.update({"ARM_FAKE_VERB": arm.fake[0], "ARM_FAKE_OUT": arm.fake[1]})
    env.update(arm.env)
    argv = [a.replace("{lane_dir}", str(world.lane_dir)) for a in arm.argv]
    if arm.script.startswith("skills/"):
        name = "lread" if "restart" in arm.script else "sread"
        script = (skill_function(arm.script, name) + "\n"
                  f'L="$ARM_SKILL_L"\n{name} answer "the arms\' test" "$@"\n'
                  'printf "%s" "$answer"\n')
        env["ARM_SKILL_L"] = env["LANES_EDIT"]
        full = dict(world.env)
        full.update(env)
        result = subprocess.run(["bash", "-c", script, "skill", *argv], env=full,
                                cwd=str(world.lane_dir), capture_output=True, text=True,
                                timeout=180, check=False, stdin=subprocess.DEVNULL)
    else:
        result = world.run(arm.script, *argv, env=env)
    assert world.reached(), (arm.script, arm.argv, arm.verb, "the arm was never reached: fix "
                             "the case's scenario", result.returncode, result.stderr[-3000:])
    return result


def launched(world: ArmWorld) -> bool:
    """Whether `lane-start` launched an agent: the fake `claude` or `codex`
    ran."""
    codex = world.codex_log.read_text(encoding="utf-8") if world.codex_log.exists() else ""
    return bool(world.claude_runs().strip() or codex.strip())


def names_the_code(stderr: str, code: int) -> bool:
    return re.search(rf"(?<![0-9]){code}(?![0-9])", stderr) is not None


LANE_START_CASES = [pytest.param(arm, code, id=f"{arm}-{code}")
                    for arm in LANE_START_ARMS for code in (75, 3)]


@pytest.mark.parametrize(("arm_id", "code"), LANE_START_CASES)
def test_75_and_3_refuse_the_launch_at_each_lane_start_arm(tmp_path, arm_id, code):
    """At each of `lane-start`'s seven read arms the verb exits 75 or 3, and
    the launch refuses: `lane-start` exits non-zero before the launch (with
    the verb's own code at `:1154`, which passes it), the fake agent never
    runs, stderr names the code and says nothing was written, and the
    register's rows and logs are unchanged (the design's S3; lane 4's table)."""
    arm = LANE_START_ARMS[arm_id]
    world = arm_world(tmp_path, arm)
    before = world.register_bytes()
    result = run_arm(world, arm, code)
    assert result.returncode != 0, (arm_id, code, "the launch went on", result.stderr[-3000:])
    if arm_id == "1154":
        assert result.returncode == code, (arm_id, code, result.returncode, result.stderr[-2000:])
    assert not launched(world), (arm_id, code, "the agent ran")
    assert names_the_code(result.stderr, code), (arm_id, code, result.stderr[-2000:])
    # T217j (lane 4's T402 finding; lane 3, 6770688147): the early refusal says "Nothing was
    # launched, renamed or written.", the late one "has written no row, no STARTED or RESUMED
    # line and no stamp"; each says nothing was written.
    assert re.search(r"(?i)\bnothing (was|has been|is)\b[^.\n]*\bwritten\b|\bwrote nothing\b|\bhas written no\b",
                     result.stderr), (arm_id, code, result.stderr[-2000:])
    assert re.search(r"(?i)\b(retry|re-?run|again)\b", result.stderr), \
        (arm_id, code, "no word that a retry is safe", result.stderr[-2000:])
    assert world.register_bytes() == before, (arm_id, code, "the register moved")


@pytest.mark.parametrize("arm_id", sorted(LANE_START_69))
def test_69_refuses_at_canon_lane_and_session_lane_and_stays_a_note_at_the_other_four_arms(
        tmp_path, arm_id):
    """A 69 refuses at `:1154` (`canon-lane`) and `:2184-2186`
    (`session-lane`), by round 1's 2A, with the register unchanged and no
    launch; at `:1262`, `:1271`, `:3079` and `:3430` it stays a note naming
    the 69, and the launch goes on."""
    arm = LANE_START_ARMS[arm_id]
    world = arm_world(tmp_path, arm)
    before = world.register_bytes()
    result = run_arm(world, arm, 69, stderr=UNREACHABLE_STDERR.rstrip("\n"))
    if LANE_START_69[arm_id] == "refuse":
        assert result.returncode == 69, (arm_id, result.returncode, result.stderr[-3000:])
        assert not launched(world), (arm_id, "the agent ran")
        assert world.register_bytes() == before, (arm_id, "the register moved")
    else:
        assert launched(world), (arm_id, "a note's 69 refused the launch", result.returncode,
                                 result.stderr[-3000:])
        assert names_the_code(result.stderr, 69), (arm_id, result.stderr[-2000:])


@pytest.mark.parametrize(("arm_id", "code"), OTHER_ARM_CASES)
def test_the_other_callers_arms_pass_the_code_or_refuse_as_lane_4s_table_gives(
        tmp_path, arm_id, code):
    """Each other caller's arm with its verb exiting `code`, as lane 4's
    table gives it: `lane-end:930-938` and `lane-worktrees:508-524` refuse
    with the verb's own code and write nothing; `lane-end:2490`,
    `lane-handoff:2817` and each arm that already refuses exit with the
    verb's code, never 1; the `69)` arm of `lane-handoff:1463` and the
    handoff skill's `sread` (`SKILL.md:112`) re-reads from the mirror and
    prints the `read: mirror` line; `lane-rename:241` prints new text for the
    code, never the note that a 3 means the commit is local; the restart
    skill's `lread` exits 1 with its REFUSED line, so it binds no window,
    writes no stamp and prints no resume command; and where only
    `managed-projection`'s call fails (`lane-start:1555`, `lane-end:955`), its
    real failed read, projection-class, gives 1, and the caller refuses 1,
    UNKNOWN, never 69 (lane 3's ruling, #165 6754439281, item 6)."""
    arm, _codes, kind = OTHER_ARMS[arm_id]
    world = arm_world(tmp_path, arm)
    before = world.register_bytes()
    result = run_arm(world, arm, code)
    if kind == "refuse":
        assert result.returncode == code, (arm_id, code, result.returncode, result.stderr[-3000:])
        assert world.register_bytes() == before, (arm_id, code, "a refusal that wrote")
    elif kind == "refuse-own-exit":
        # T217j (lane 3, 6770688147): lane-worktrees refuses with its own exit, 2 (its header's
        # exit table: lane-end's gate reads 3 as "something to retire", add's 1 as "made"),
        # naming the read's code, with nothing made.
        assert result.returncode == 2, (arm_id, code, result.returncode, result.stderr[-3000:])
        assert re.search(rf"REFUSED, nothing was made: .*exited {code}\b", result.stderr), \
            (arm_id, code, result.stderr[-2000:])
        assert world.register_bytes() == before, (arm_id, code, "a refusal that wrote")
    elif kind == "code":
        assert result.returncode == code, (arm_id, code, result.returncode, result.stderr[-3000:])
    elif kind == "mirror":
        assert result.returncode != 1, (arm_id, "the 69 died as a failed read", result.stderr[-3000:])
        # T217zg: the line is the re-read's own, made with the store still down (Y:4895).
        reread = Path(f"{world.arm_log}.reread")
        assert reread.exists() and reread.read_text(encoding="utf-8").strip(), (
            arm_id, "no re-read after the 69", result.stderr[-3000:])
        assert MIRROR_LINE.search(result.stderr), (arm_id, "no `read: mirror` line",
                                                   result.stderr[-3000:])
    elif kind == "unknown":
        assert result.returncode == 1, (arm_id, "a failed projection read is 1, UNKNOWN, "
                                        "never 69", result.returncode, result.stderr[-3000:])
        assert "UNKNOWN" in result.stderr, (arm_id, result.stderr[-2000:])
        assert world.register_bytes() == before, (arm_id, "a refusal that wrote")
        if arm.script == "lane-start":
            assert not launched(world), (arm_id, "the agent ran")
    elif kind == "rename":
        assert result.returncode == code, (arm_id, code, result.returncode, result.stderr[-2000:])
        assert not re.search(r"a 3 mean", result.stderr), (arm_id, code, "the old note",
                                                           result.stderr[-2000:])
        assert names_the_code(result.stderr, code), (arm_id, code, result.stderr[-2000:])
    elif kind == "lread":
        assert result.returncode == 1, (arm_id, code, result.returncode, result.stderr)
        assert re.search(rf"^REFUSED: .*\(exit {code}\)", result.stderr, re.M), \
            (arm_id, code, result.stderr)
        assert result.stdout == "", (arm_id, code, result.stdout)
    else:
        raise AssertionError(kind)


# ------------------------------------------------- the rerun on a 3, and the 2
#: A transcript id the lane's last PAUSED record names (the fake
#: `lane-transcript` answers it), here and not in the row's cell: a resume
#: restores it and appends it to the cell, the write at `lane-start-3872`.
RERUN_RESTORED = "aaaaaaaa-0011-4000-8000-00000000a011"

#: Each act that carries on after a failed write (lane 4's section, F9, item
#: 2), by its line at `2a057a6d`: the run that reaches it, and the write.
#: `match`, where set, is the write's own words, since one run can make more
#: than one call of the verb; `fake` is a fact the scenario needs.
#:
#: WHICH CALL GETS THE 3 (lane 3's (L2-2), #165 6808937880): "A 3 is relayed
#: from whichever call made the write." Where a transcript uuid is known, T428
#: makes the writes one `start-record` call; where none is, W2 to W6 are their
#: own verbs. So `-3851` (W2), `-3989` (W6) and `-4022` (W5) run with no uuid
#: knowable and name their own verb alone: a scenario that came to know one
#: would reach `start-record` instead and fail as never reached. `-4181` (W7)
#: runs with one known, since its line is deferred where none is (Amendment
#: 7(b)), and its stub gives the 3 to `start-record` at T428 and to `log`
#: before it. W3 (`-3872`) and W4 (`-3909`) are written only where a uuid is
#: known: the restored transcript is resumed by id, and a minted id is
#: `lane_sid` (lane 4's T428 `f2c16de`, `lane-start:4132`, `:4148`, `:4206`,
#: `:4251`), so T428 always carries them in the one call (`:4602`, `:4653`).
#: They name both verbs, as the `--no-launch` case's w3 and w4 do.
RERUN_SITES = {
    # 2a057a6d:3851 is the harness's id for this window, appended to the cell (the
    # `--no-launch` case's W2); :3909 the id `lane-start` mints, stamped on it (W4).
    "lane-start-3851": Arm("lane-start", ("repoA", "1"), "append-session-id", "3904",
                           match="*the harness minted*", fake=("window-session", WINDOW_RECORD)),
    "lane-start-3872": Arm("lane-start", ("repoA", "1"), "append-session-id|start-record", "3925",
                           match="*restored from the lane*",
                           fake=("lane-transcript", RERUN_RESTORED)),
    "lane-start-3909": Arm("lane-start", ("repoA", "1"), "append-session-id|start-record", "3962",
                           match="*lane-start minted*"),
    # W6 with no uuid knowable: the window's live session is taken, as at 3851, so
    # nothing is minted and the state cell is its own verb (T428 `lane-start:4193–4194`).
    "lane-start-3989": Arm("lane-start", ("repoA", "1"), "set-row-state", "4042",
                           fake=("window-session", WINDOW_RECORD)),
    "lane-start-4022": Arm("lane-start", ("repoA", "2", "--agent", "codex"), "append-session-id",
                           "4075", match="*launched codex*",
                           fake=("lane-transcript", "codex-session-7")),
    # W7 with a minted uuid known: the STARTED line is `log`'s own call before T428,
    # and rides in `start-record`'s at T428 (`<lane> STARTED … --log lane:<lane> → …`).
    "lane-start-4181": Arm("lane-start", ("repoA", "1"), "log|start-record", "4234",
                           match="*STARTED*"),
    "lane-handoff-2878": Arm("lane-handoff", ("--lane", "repoA-2", "the rerun test"), "log",
                             "2878", match="PAUSED*"),
    "lane-handoff-2890": Arm("lane-handoff", ("--lane", "repoA-2", "the rerun test"), "append-line",
                             "2890"),
    "lane-handoff-2913": Arm("lane-handoff", ("--lane", "repoA-2", "the rerun test"),
                             "set-row-state", "2913", match="repoA-2 PAUSED*"),
    "lane-end-2490": Arm("lane-end", ("repoA-2",), "log", "2543", match="ENDED*"),
    "skill-738": Arm("skills/handoff/SKILL.md", (), "append-line", "743"),
}
#: A transcript a site's run must find in the lane's directory (`lane-start`'s
#: `recorded_transcript`): the restored one, as the `--no-launch` case's W3 has.
RERUN_TRANSCRIPTS = {"lane-start-3872": RERUN_RESTORED}


def place_transcript(world: ArmWorld, sid: str) -> None:
    """A transcript `<sid>.jsonl` in the sandbox's projects directory for the
    lane's directory, where `lane-start` looks for one."""
    here = (Path(world.env["CLAUDE_CONFIG_DIR"]) / "projects"
            / re.sub(r"[^A-Za-z0-9]", "-", str(world.lane_dir)))
    here.mkdir(parents=True, exist_ok=True)
    (here / f"{sid}.jsonl").write_text('{"type":"user"}\n', encoding="utf-8")


#: The skill's `(b)` write (`SKILL.md:738-742` at `2a057a6d`), run by its
#: text with the variables its step 4 has set. Code v1.2.0 (slice 3, `98e2ec0`)
#: names the lane on the write, `LANES_LANE="$lane" "$L" append-line …`
#: (Amendment 23 S2), and lane 4's T431 (`7c74b907`, line R's merge67) puts
#: the act and its expectations first, `LANES_ACT="$act_line"
#: LANES_EXPECT="$act_scopes" LANES_LANE="$lane" "$L" append-line …`
#: (`f9e1449c:skills/handoff/SKILL.md:1361`), so the line may open with any
#: number of `NAME="$var" ` prefixes, or none (T217zj; round 6h, TR21's 2d).
#: Run alone, `$act_line` and `$act_scopes` are empty, and the arms' wrapper
#: answers `append-line` itself, reading neither variable.
SKILL_738_LINE = re.compile(
    r'^(?:[A-Z][A-Z_]*="\$[a-z_]+" )*"\$L" append-line "PAUSED — lane \$lane, .*$', re.M)


def rerun_argv(arm: Arm, lane: str) -> str:
    """The writer's own arguments, as its printed rerun repeats them. Where
    the arm names two verbs, the first, the write's own: the line is the
    stub's and is relayed as printed, whichever call the stub fails."""
    return f"{arm.verb.split('|')[0]} lane:{lane} the-same-arguments"


def own_hints(stderr: str, verb: str) -> list:
    """The act's own rerun hints: a line, other than the writer's printed
    rerun, that tells the person to run the verb (`LANES_LANE=… <verb>`)."""
    return [line for line in stderr.splitlines()
            if "LANES_WRITE_ID=" not in line and "LANES_LANE=" in line
            and re.search(rf"(?<![A-Za-z-]){re.escape(verb)}(?![A-Za-z-])", line)]


@pytest.mark.parametrize("site", sorted(RERUN_SITES))
def test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3(tmp_path, site):
    """Each carry-on act, with its write exiting 3 and printing the writer's
    rerun line (`LANES_WRITE_ID=… LANES_WRITE_GENERATION=… LANES_LANE=…
    LANES_SESSION=… lanes-edit.sh <args>`): the act's stderr carries that
    line as printed, and none of the act's own hint, so none that reads a 3
    as written and none that leaves out `LANES_SESSION` (`lane-start:4182`
    today); `lane-handoff:2890-2891` and `:2913-2914`, which send the
    writer's stderr to `/dev/null` today, keep it; and `lane-start` carries
    on to its launch, as it did before. The 3 is the call's that made the
    write: a write's own verb where no transcript uuid is knowable, and
    `start-record`'s one call at T428 where one is (lane 3's (L2-2), #165
    6808937880; `RERUN_SITES`), so no act's own hint names either verb."""
    arm = RERUN_SITES[site]
    world = arm_world(tmp_path, arm)
    lane = "repoA-2" if "2" in arm.argv[:2] or "repoA-2" in arm.argv or not arm.argv else "repoA-1"
    line = rerun_line(lane, rerun_argv(arm, lane))
    if arm.script.startswith("skills/"):
        found = SKILL_738_LINE.search((REPO / arm.script).read_text(encoding="utf-8"))
        assert found, (site, "the skill's (b) write is not found by its text")
        env = world.arm_env(arm.verb, 3, stderr=line)
        full = dict(world.env)
        full.update(env)
        full.update({"lane": "repoA-2", "uuid": UUID_A2, "ws": "Eagle", "why_text": "the rerun test"})
        script = ('L="$LANES_EDIT"; lane="$lane"; uuid="$uuid"; ws="$ws"; '
                  'why_text="$why_text"\n' + found.group(0) + "\n")
        result = subprocess.run(["bash", "-c", script], env=full, cwd=str(world.lane_dir),
                                capture_output=True, text=True, timeout=120, check=False,
                                stdin=subprocess.DEVNULL)
        assert world.reached(), (site, "the arm was never reached", result.stderr)
    else:
        if site in RERUN_TRANSCRIPTS:
            place_transcript(world, RERUN_TRANSCRIPTS[site])
        result = run_arm(world, arm, 3, stderr=line)
    assert line in result.stderr.splitlines(), (site, "the writer's rerun was not relayed",
                                                result.stderr[-3000:])
    hints = [hint for verb in arm.verb.split("|") for hint in own_hints(result.stderr, verb)]
    assert not hints, (site, "the act's own hint", hints)
    if arm.script == "lane-start":
        assert launched(world), (site, "the launch did not carry on", result.returncode,
                                 result.stderr[-2000:])


#: AN EXPECTATION'S 2 AT `start-record` (LR010): the writer's own words,
#: which `lane-start` keeps on stderr whatever it makes of the 2.
EXPECTATION_2_STDERR = ("ERROR:  LR010: an expectation of this act no longer holds\n"
                        "DETAIL:  expectation bind:repoA-1")
#: `lane-start`'s OWN REFUSAL of a 2 at `start-record`, under a seq base or
#: where ERR-56's re-read answers one (its `2)` arm and the die after the
#: re-read open alike): its first words, and the call with its 2.
EXPECTATION_2_REFUSED = "lane-start: lane repoA-1's bind was REFUSED: "
EXPECTATION_2_CALL_2 = "start-record` exited 2 (its words are above)"
#: An act's base off primary, `<act-id>@files` (Y:5577), which the arms'
#: wrapper answers each `act-begin` with (`ARM_ACT_BASE`), as files mode
#: does, and logs: the act's own call, and ERR-56's re-read after a 2.
FILES_ACT_BASE = f"{'a2' * 16}@files"
#: ERR-56'S TWIN of `lane-start-4181`: the same lane and arguments, resuming
#: `repoA-1`'s own last transcript by id (`UUID_A1B`, which its last PAUSED
#: names), so its one `start-record` call carries `--state` and the RESUMED
#: line and no `--add-row`, under an `@files` base. A RESUMED, because 5c
#: writes the Rule 3 stamp for a RESUMED alone (`142afd90:lane-start:5351`).
EXPECTATION_2_RESUME = Arm("lane-start", ("repoA", "1"), "start-record", "5142",
                           match="*RESUMED*", env={"ARM_ACT_BASE": FILES_ACT_BASE})
#: The handoff that `repoA-1`'s row names, committed in the register for the
#: twin, whose resume stamps it under its header block (5c).
EXPECTATION_2_HANDOFF = "handoffs/repoA-1.md"
EXPECTATION_2_HANDOFF_TEXT = "# repoA-1, the handoff\n\nThe top block: parked.\n"


def act_begins(world: ArmWorld) -> list:
    """The `act-begin` calls that the arms' wrapper answered with
    `ARM_ACT_BASE`, in order, each as its arguments."""
    acts = Path(f"{world.arm_log}.act")
    return acts.read_text(encoding="utf-8").splitlines() if acts.exists() else []


def test_an_expectation_2_at_lane_starts_last_write_dies(tmp_path):
    """Any 2 at `lane-start:4181`, its last write (the STARTED log line),
    dies with 2 under a seq base, an expectation's included (LR010): on
    primary it is a second binding, a deciding refusal, never a stamp to
    carry on past (lane 4's table; the design's outcomes table). The run
    knows a minted uuid, so at T428 the line rides in `start-record`'s one
    call, and the stub fails that call ("any 2 dies, LR010's included";
    lane 3's (L2-2), #165 6808937880).
    THE SEQ BASE (ERR-56, research.md:1747-1801 at lane 3's commit 14
    `bc4a66bb`; lane 3, #165 6871338814, on lane 4's 6871294666): that rule
    holds under a base `<act-id>@<seq>:<generation>`, where LR010 can occur,
    so the arms' wrapper answers `act-begin` with `NO_LAUNCH_ACT_BASE`, as
    the `--no-launch` acts take it, and the case asserts that `lane-start`
    asked it: ERR-56 asks for a re-read only after an `@files` 2, and forbids
    none under a seq base, so the count is not held (lane 4, #165
    6879449852, note 1). The refusal it asserts is `lane-start`'s own,
    "bind was REFUSED", which names the call and its 2 and says nothing was
    launched: the stub prints LR010's words, and `lane-start` only passes
    them through, so they prove nothing of its path (note 2). Under `@files`
    the same 2 is Amendment 23's refusal, and the launch goes on: the twin
    below. With the real `act-begin`'s `@files`, this case failed in line
    R's rounds 6k and 6l, from merge101's T428 join (`47b7d15d`,
    `12fe0e43`), which follows ERR-56."""
    rerun = RERUN_SITES["lane-start-4181"]
    arm = Arm(rerun.script, rerun.argv, rerun.verb, rerun.base, nth=rerun.nth,
              match=rerun.match, env={"ARM_ACT_BASE": NO_LAUNCH_ACT_BASE})
    world = arm_world(tmp_path, arm)
    result = run_arm(world, arm, 2, stderr=EXPECTATION_2_STDERR)
    assert "act-begin" in act_begins(world), (
        "the act did not take its seq base", act_begins(world), result.returncode,
        result.stderr[-3000:])
    assert result.returncode == 2, (result.returncode, result.stderr[-3000:])
    assert any(line.startswith(EXPECTATION_2_REFUSED) and EXPECTATION_2_CALL_2 in line
               and "nothing has been launched" in line
               for line in result.stderr.splitlines()), result.stderr[-3000:]
    assert not launched(world), "the agent ran after the 2"


def test_an_expectation_2_at_lane_starts_last_write_under_an_at_files_base_notes_stamps_and_launches(
        tmp_path):
    """ERR-56'S TWIN of the case above (research.md:1747-1801 at lane 3's
    commit 14 `bc4a66bb`; lane 3, #165 6871338814): the same `start-record`
    2 with LR010's words, on the one call, which makes no row (`--state`, no
    `--add-row`), under a base `<act-id>@files`, whose second `act-begin`
    still answers `@files`. Off primary no write reads `LANES_EXPECT`
    (Y:5596), so that 2 is no second binding: it is Amendment 23's refusal,
    and `lane-start` keeps the writer's words, prints the note it prints for
    a resume's other codes, with the command that writes the record later,
    writes the Rule 3 stamp and launches, exit 0 (T428's fix round,
    `47b7d15d` and `12fe0e43`; its arm at `142afd90:lane-start:5172-5199`).
    The run resumes `repoA-1`'s own last transcript by id, so its line is a
    RESUMED and 5c owes the stamp, and the row's handoff is in the register
    (`EXPECTATION_2_RESUME`). The stamp is read on origin, once. Before
    ERR-56 the 2 died, 2 and no launch, as under a seq base, so this case
    fails there."""
    arm = EXPECTATION_2_RESUME
    world = arm_world(tmp_path, arm)
    place_transcript(world, UUID_A1B)
    (world.wip / EXPECTATION_2_HANDOFF).write_text(EXPECTATION_2_HANDOFF_TEXT, encoding="utf-8")
    world.git("-C", str(world.wip), "add", "--", EXPECTATION_2_HANDOFF)
    world.git("-C", str(world.wip), "commit", "-q", "-m", "repoA-1's handoff")
    world.git("-C", str(world.wip), "push", "-q", "origin", "main")
    world.git("-C", str(world.ws), "pull", "-q", "--ff-only")
    result = run_arm(world, arm, 2, stderr=EXPECTATION_2_STDERR)
    lines = result.stderr.splitlines()
    where = (result.returncode, result.stderr[-4000:])
    # THE PREMISE: the stub's 2 met the `start-record` call, a resume's, which makes no row,
    # and `lane-start` made that call once (the wrapper's count of matching calls; its log
    # holds the first alone, so its length proves nothing, lane 4's #165 6879449852, note 3);
    # and `act-begin` was asked twice, the act's own and ERR-56's re-read, both `@files`.
    calls = world.reached()
    assert calls and " --state " in f" {calls[0]} " and "--add-row" not in calls[0] \
        and calls[0].startswith("start-record repoA-1 RESUMED "), (calls,) + where
    count = Path(f"{world.arm_log}.count")
    assert count.exists() and count.read_text(encoding="utf-8").strip() == "1", \
        ("start-record was called again", count.read_text(encoding="utf-8")
         if count.exists() else None) + where
    assert act_begins(world) == ["act-begin", "act-begin"], (
        "the act's base was not read again after the 2", act_begins(world)) + where
    # WHAT TELLS ERR-56'S REFUSAL FROM THE `2)` ARM'S DIE, which also names `start-record`
    # and "exited 2" (note 3): exit 0, no "bind was REFUSED", the note that the launch is not
    # refused, its hint, and the launch below.
    assert result.returncode == 0, where
    assert not any(line.startswith(EXPECTATION_2_REFUSED) for line in lines), where
    # THE WRITER'S WORDS, kept as the writer printed them.
    assert all(line in lines for line in EXPECTATION_2_STDERR.splitlines()), where
    # THE NOTE, naming the call and its 2, the launch not refused for it, with the command
    # that writes the record later.
    assert any(line.startswith("lane-start: ") and "start-record` exited 2, and its words" in line
               and "The launch is not refused for it" in line for line in lines), where
    hints = own_hints(result.stderr, "start-record")
    assert any(f"LANES_LANE=repoA-1 LANES_SESSION={UUID_A1B} " in hint
               and re.search(r"(?:^|\s)start-record repoA-1 RESUMED\s", hint) for hint in hints), \
        (hints,) + where
    # THE RULE 3 STAMP, under the handoff's header block, committed and pushed: on origin once.
    published = world.git("--git-dir", str(world.origin), "show", f"main:{EXPECTATION_2_HANDOFF}")
    stamps = [line for line in published.splitlines()
              if line.startswith(f"RESUMED by {UUID_A1B} (lane repoA-1) at ")]
    assert len(stamps) == 1, (published,) + where
    # THE LAUNCH, of the transcript it resumed.
    assert launched(world), where
    assert f"--resume {UUID_A1B}" in world.claude_runs(), (world.claude_runs(),) + where


def test_an_expectation_2_at_lane_starts_last_write_under_an_at_files_base_whose_reread_answers_a_seq_base_dies(
        tmp_path):
    """ERR-56'S SECOND CASE (research.md:1747-1801 at lane 3's commit 14
    `bc4a66bb`; the path lane 4 found untested, #165 6879449852): the twin's
    `start-record` 2 with LR010's words, on the one call, which makes no row,
    under a base `<act-id>@files`; but ERR-56's re-read after the 2 answers
    a seq base (`ARM_ACT_BASE_AGAIN`), as when the register was switched to
    primary after the launch began. Under a seq base a 2 stops the launch,
    so `lane-start` dies 2 (`lane-start:5196` at line R's merge106
    `bc9ed80b`): its refusal names the seq base it read, and it writes no
    stamp and launches nothing. A `lane-start` that took any answer of the
    re-read as Amendment 23's refusal would note, stamp and launch, as the
    twin does, and fail here."""
    twin = EXPECTATION_2_RESUME
    arm = Arm(twin.script, twin.argv, twin.verb, twin.base, match=twin.match,
              env={"ARM_ACT_BASE": FILES_ACT_BASE, "ARM_ACT_BASE_AGAIN": NO_LAUNCH_ACT_BASE})
    world = arm_world(tmp_path, arm)
    place_transcript(world, UUID_A1B)
    (world.wip / EXPECTATION_2_HANDOFF).write_text(EXPECTATION_2_HANDOFF_TEXT, encoding="utf-8")
    world.git("-C", str(world.wip), "add", "--", EXPECTATION_2_HANDOFF)
    world.git("-C", str(world.wip), "commit", "-q", "-m", "repoA-1's handoff")
    world.git("-C", str(world.wip), "push", "-q", "origin", "main")
    world.git("-C", str(world.ws), "pull", "-q", "--ff-only")
    result = run_arm(world, arm, 2, stderr=EXPECTATION_2_STDERR)
    lines = result.stderr.splitlines()
    where = (result.returncode, result.stderr[-4000:])
    # THE PREMISE: the twin's call and 2, and the re-read, which answered the seq base.
    calls = world.reached()
    assert calls and " --state " in f" {calls[0]} " and "--add-row" not in calls[0] \
        and calls[0].startswith("start-record repoA-1 RESUMED "), (calls,) + where
    assert act_begins(world) == ["act-begin", "act-begin"], (
        "the act's base was not read again after the 2", act_begins(world)) + where
    # THE DIE: 2, `lane-start`'s own refusal naming the seq base it read, the writer's words.
    assert result.returncode == 2, where
    assert any(line.startswith(EXPECTATION_2_REFUSED) and EXPECTATION_2_CALL_2 in line
               and f"now answers a seq base, `{NO_LAUNCH_ACT_BASE}`" in line
               and "nothing has been launched" in line for line in lines), where
    assert all(line in lines for line in EXPECTATION_2_STDERR.splitlines()), where
    # NO STAMP on origin, and NO LAUNCH.
    published = world.git("--git-dir", str(world.origin), "show", f"main:{EXPECTATION_2_HANDOFF}")
    assert not any(line.startswith(f"RESUMED by {UUID_A1B} ") for line in published.splitlines()), \
        (published,) + where
    assert not launched(world), where


#: ERR-56'S ROW-MAKING 2 (research.md:1757-1758 at lane 3's commit 24 `f9d6069e`, "A
#: `start-record` that makes the row still dies with 2"; T428's line, tasks:1351, "a new
#: row's 2 dies in both"): a NEW lane, `repoZ-1`, which has no row, started from the
#: sandbox's own checkout of `repoZ`, where there is nothing to resume, so `lane-start`
#: mints the new session's id, and its one `start-record` call carries `--add-row` and the
#: STARTED line (W1 with W7: `lane-start:4655-4657` and `:5124-5126` at line R's merge106
#: `bc9ed80b`), under a base `<act-id>@files`.
EXPECTATION_2_NEW_LANE = "repoZ-1"
EXPECTATION_2_NEW_ROW = Arm("lane-start", ("repoZ", "1"), "start-record", "5142",
                            match="*--add-row*", env={"ARM_ACT_BASE": FILES_ACT_BASE})


def test_an_expectation_2_at_lane_starts_last_write_that_makes_a_row_under_an_at_files_base_dies(
        tmp_path):
    """ERR-56'S ROW-MAKING 2 (research.md:1748-1801 at lane 3's commit 24
    `f9d6069e`; T428's line, tasks:1351; the path lane 4 found driven by no
    test, #165 6879449852 and 6880188792): the twin's `start-record` 2 with
    LR010's words, under a base `<act-id>@files`, on the one call of a NEW
    lane, which makes its row (`--add-row`, no `--state`). Off primary only
    a call that makes no row is Amendment 23's refusal; "a `start-record`
    that makes the row still dies with 2". So `lane-start` takes its `2)`
    arm (the re-read's guard, `[ -z "$LS_SR_ROW" ]`, keeps this call off
    ERR-56's refusal path: `lane-start:5173` and `:5209-5210` at line R's
    merge106 `bc9ed80b`): exit 2, its own refusal naming the call, its 2 and
    the new row, no command of its own for the write (Y:5601), the writer's
    words kept, nothing written to the register, and nothing launched. A
    `lane-start` that took this 2 for Amendment 23's refusal, as it takes a
    resume's, would note it with the command that writes the record later
    and launch a lane that has no row; one that read the base again and then
    died in the `*)` arm's row branch would print that command for a write
    by hand; each fails here. How many times `act-begin` was asked is not
    held: ERR-56 asks for its re-read on the way to the refusal, and forbids
    none before a die (lane 4's note 1, #165 6879449852)."""
    arm = EXPECTATION_2_NEW_ROW
    lane = EXPECTATION_2_NEW_LANE
    world = arm_world(tmp_path, arm)
    before = world.register_bytes()
    assert world.store_rows(lane) == 0, (lane, "the sandbox's register already has its row")
    result = run_arm(world, arm, 2, stderr=EXPECTATION_2_STDERR)
    lines = result.stderr.splitlines()
    where = (result.returncode, result.stderr[-4000:])
    # THE PREMISE: the stub's 2 met the one `start-record` call, a new lane's, which makes its
    # row with its STARTED line, and the act took its `@files` base.
    calls = world.reached()
    assert calls and calls[0].startswith(f"start-record {lane} STARTED ") \
        and " --add-row " in f" {calls[0]} " and " --state " not in f" {calls[0]} ", \
        (calls,) + where
    count = Path(f"{world.arm_log}.count")
    assert count.exists() and count.read_text(encoding="utf-8").strip() == "1", \
        ("start-record was called again", count.read_text(encoding="utf-8")
         if count.exists() else None) + where
    assert "act-begin" in act_begins(world), (
        "the act did not take its @files base", act_begins(world)) + where
    # THE DIE: 2, and `lane-start`'s own refusal, its `2)` arm's, naming the call, its 2 and
    # the new row that was not written, with nothing launched.
    assert result.returncode == 2, where
    assert any(line.startswith(f"lane-start: lane {lane}'s bind was REFUSED: ")
               and EXPECTATION_2_CALL_2 in line
               and f"none of lane {lane}'s new row and its STARTED line was written" in line
               and "nothing has been launched" in line for line in lines), where
    # NOT AMENDMENT 23'S REFUSAL: no note that the launch is not refused, and no command of
    # its own for the write (Y:5601), such as the `*)` arm's row branch prints for one by hand.
    assert not any("The launch is not refused for it" in line for line in lines), where
    hints = own_hints(result.stderr, "start-record")
    assert not hints, (hints,) + where
    # THE WRITER'S WORDS, kept as the writer printed them.
    assert all(line in lines for line in EXPECTATION_2_STDERR.splitlines()), where
    # NOTHING WRITTEN: the register on origin as it was, with no row for the new lane; and NO
    # LAUNCH.
    assert world.register_bytes() == before, ("the refusal wrote to the register",) + where
    assert world.store_rows(lane) == 0, where
    assert not launched(world), where


# ------------------------------- the `--no-launch` act under a seq base (Q41)
#: An act's base on primary, `<act-id>@<seq>:<generation>` (Y:5577), which the
#: arms' wrapper answers `act-begin` with (`ARM_ACT_BASE`): a seq base, not
#: `@files`, so `lane-start` prints no hand command of its own for a write.
NO_LAUNCH_ACT_BASE = f"{'a1' * 16}@41:{RERUN_GENERATION}"
#: The writer's own words, which the act keeps on stderr.
NO_LAUNCH_WRITER_SAYS = "lanes-edit: the T217 writer's own words for its failed write"
#: A transcript id the lane's last PAUSED record names, here and not in the
#: row's cell: a resume restores it (W3).
NO_LAUNCH_RESTORED = "aaaaaaaa-0010-4000-8000-00000000a010"

#: `lane-start`'s writes W2 to W6 (lane 4's names, `lane-start` at T428
#: `e35b06ed`; lane 3's batch 8, Q39 and Q41) and a resume's `start-record`:
#: each a run whose write fails, matched by the write's own words. Where no
#: transcript uuid is knowable each write is its own verb, on the base and at
#: T428; where one is, T428 carries W2 to W6 in `start-record`'s one call
#: ("W4, carried by the one call at 5b"), so W3's and W4's runs, which know
#: one, name both verbs (`ARM_VERB`'s `|`). The table's `base` is lane 4's
#: line at T428 (lane 4's T428 report 6, `83ad8df`). `NO_LAUNCH_TRANSCRIPTS`
#: puts a transcript where `lane-start` looks for one.
NO_LAUNCH_WRITES = {
    # W2: the window's live session, appended to the cell (`--agent claude` with nothing to
    # resume here, so no uuid is knowable and the append is its own verb).
    "w2": Arm("lane-start", ("repoA", "1"), "append-session-id|start-record", "4533",
              match="*the harness minted*", fake=("window-session", WINDOW_RECORD)),
    # W3: the transcript the lane's last PAUSED record names, restored to the cell.
    "w3": Arm("lane-start", ("repoA", "1"), "append-session-id|start-record", "4568",
              match="*restored from the lane*", fake=("lane-transcript", NO_LAUNCH_RESTORED)),
    # W4: the id `lane-start` mints for a new session, stamped on the cell.
    "w4": Arm("lane-start", ("repoA", "1"), "append-session-id|start-record", "4619",
              match="*lane-start minted*"),
    # W5: another agent's own id, appended to the cell (`codex`, whose id is unknowable).
    "w5": Arm("lane-start", ("repoA", "2", "--agent", "codex"), "append-session-id|start-record",
              "4755", match="*launched codex*", fake=("lane-transcript", "codex-session-7")),
    # W6: the row's state cell.
    "w6": Arm("lane-start", ("repoA", "2", "--agent", "codex"), "set-row-state|start-record",
              "4709", match="*LIVE*"),
    # A resume's one write: the row's own last transcript is here, so it resumes by id and
    # `start-record` carries the state and the RESUMED line (W6, W7).
    "resume": Arm("lane-start", ("repoA", "1"), "start-record", "4986", match="* --state *"),
}
NO_LAUNCH_TRANSCRIPTS = {"w3": NO_LAUNCH_RESTORED, "resume": UUID_A1B}
NO_LAUNCH_CASES = [pytest.param(write, code, id=f"lane-start-{write}-{code}")
                   for write in NO_LAUNCH_WRITES for code in (69, 75)]


@pytest.mark.parametrize("write,code", NO_LAUNCH_CASES)
def test_a_carry_on_act_names_lane_start_no_launch_on_a_69_or_75_under_a_seq_base(
        tmp_path, write, code):
    """`lane-start`'s `--no-launch` act under a seq base (R-F13c-23; lane 3's
    batch 8, #165 6780753157, Q39, Q41 and text change 6): at W2 to W6, and at
    a resume's `start-record`, a write that exits 69 or 75 under the act's seq
    base keeps the writer's stderr, prints no rerun of its own, never says to
    run the act again from its start, launches as today, and names `lane-start
    --no-launch <the same arguments>` as the launched session's first act: the
    act's note for the write, then that line. Where no transcript uuid is
    knowable, Amendment 7(b)'s own `--no-launch` line prints later as well, so
    the act is asked for right after the write's note (lane 4's T428 report 6,
    its question 3). A 3 keeps relaying the writer's rerun
    (`test_a_carry_on_act_relays_the_writers_printed_rerun_on_a_3`). The ids
    name the writes, not TP:2951's sites (NOTES question 38). FAILS UNTIL lane
    4's T428 takes Q41 (`83ad8df`), and its act base (T428 (a))."""
    arm = NO_LAUNCH_WRITES[write]
    world = arm_world(tmp_path, arm)
    if write in NO_LAUNCH_TRANSCRIPTS:
        here = (Path(world.env["CLAUDE_CONFIG_DIR"]) / "projects"
                / re.sub(r"[^A-Za-z0-9]", "-", str(world.lane_dir)))
        here.mkdir(parents=True, exist_ok=True)
        (here / f"{NO_LAUNCH_TRANSCRIPTS[write]}.jsonl").write_text('{"type":"user"}\n',
                                                                     encoding="utf-8")
    env = world.arm_env(arm.verb, code, match=arm.match, nth=arm.nth, stderr=NO_LAUNCH_WRITER_SAYS)
    env.update({"ARM_FAKE_VERB": arm.fake[0], "ARM_FAKE_OUT": arm.fake[1]} if arm.fake else {})
    env["ARM_ACT_BASE"] = NO_LAUNCH_ACT_BASE
    result = world.run(arm.script, *arm.argv, env=env)
    lines = result.stderr.splitlines()
    acts = Path(f"{world.arm_log}.act")
    assert acts.exists() and acts.read_text(encoding="utf-8").strip(), (
        write, code, "the act took no seq base: lane-start asked no act-begin",
        result.returncode, result.stderr[-3000:])
    assert world.reached(), (write, code, arm.verb, "the write was never reached: fix the case's "
                             "scenario", result.returncode, result.stderr[-3000:])
    assert NO_LAUNCH_WRITER_SAYS in lines, (write, code, "the writer's stderr was not kept",
                                            result.stderr[-3000:])
    verb = world.reached()[0].split(" ", 1)[0]
    hints = own_hints(result.stderr, verb)
    assert not hints, (write, code, "a rerun of the act's own", hints)
    assert not re.search(r"again from its start", result.stderr), (
        write, code, "the act says to run it again from its start, a second launch",
        result.stderr[-3000:])
    assert launched(world), (write, code, "the launch did not go on", result.returncode,
                             result.stderr[-3000:])
    # THE ACT IT NAMES: the first two of `lane-start`'s lines after the writer's are the
    # write's note and the act, `lane-start --no-launch` with this run's own arguments.
    named = " ".join(("lane-start", "--no-launch", *arm.argv))
    after = [line for line in lines[lines.index(NO_LAUNCH_WRITER_SAYS) + 1:]
             if line.startswith("lane-start: ")][:2]
    assert any(re.search(rf"(?:^|\s){re.escape(named)}\s*$", line) for line in after), (
        write, code, f"the write's note does not name `{named}`", after, result.stderr[-3000:])


# ------------------------------------------------ the read door's other cases
def test_register_row_local_reads_the_database_on_primary_and_is_69_never_8(primary):
    """`register-row-local` reads the database on primary, 8 included (D11):
    it finds the row only the store holds, and answers 8 for a lane the store
    lacks though this checkout's own copy holds it; with the store
    unreachable it exits 69 with nothing on stdout, never 8."""
    lanes = primary.e.wip / "lanes" / "LANES.md"
    local_only = "repoL-1"
    with open(lanes, "a", encoding="utf-8") as handle:     # this checkout's copy only
        handle.write(f"| `{local_only}` | harness `{UUID_M1}` | Eagle / test / brett | 2026-10-06T00:00Z "
                     f"| none | handoffs/{local_only}.md | LIVE · 2026-10-06T00:00:00Z · local |\n")
    found = primary.edit("register-row-local", STORE_ONLY_LANE)
    assert primary.door.register_calls(), ("the read never reached the store", found.stderr)
    assert found.returncode == 0 and STORE_ONLY_UUID in found.stdout, \
        (found.returncode, found.stdout, found.stderr)
    absent = primary.edit("register-row-local", local_only)
    assert absent.returncode == 8, (absent.returncode, absent.stdout, absent.stderr)
    primary.door.unreachable()
    failed = primary.edit("register-row-local", STORE_ONLY_LANE)
    assert failed.returncode == 69, (failed.returncode, failed.stdout, failed.stderr)
    assert failed.stdout == "", failed.stdout


#: `lane-worktrees`' three direct reads of the register (lane 4's T404, by
#: lane 4's line cites): the run that reaches each, and a glob its
#: `register-grep` arguments match.
WORKTREE_READS = {
    "lifecycle-events-711": (("sweep", "repoA-2", "--dry-run"), "*STARTED|PAUSED*"),
    "landed-1002": (("sweep", "repoA-2", "--dry-run"), "*LANDED*"),
    "lifecycle-events-5596": (("sweep", "--all", "--report"), "*STARTED|RESUMED*"),
}
#: `landed-1002`'s tree: its branch, and the pull request `gh` lists for it.
LANDED_BRANCH = "s1"
LANDED_PR = 7


def landed_gh(log: Path, tip: str) -> str:
    """`landed-1002`'s `gh`: `pr list … --head <LANDED_BRANCH>` answers one
    row, that branch's pull request merged into `main` at the tree's tip;
    every other call refuses, as the sandbox's own fake does. Each call is
    logged to `log`."""
    row = json.dumps([{"number": LANDED_PR, "state": "MERGED", "mergedAt": "2026-10-01T05:00:00Z",
                       "headRefName": LANDED_BRANCH, "headRefOid": tip, "baseRefName": "main",
                       "isCrossRepository": False}])
    return ("#!/usr/bin/env bash\n"
            f"printf '%s\\n' \"$*\" >> '{log}'\n"
            'case " $* " in\n'
            f"  *' pr list '*' --head {LANDED_BRANCH} '*) printf '%s\\n' '{row}' ;;\n"
            "  *) printf 'FAKE gh REFUSED: %s\\n' \"$*\" >&2; exit 90 ;;\n"
            "esac\n")


@pytest.mark.parametrize("read", sorted(WORKTREE_READS))
def test_lane_worktrees_register_reads_go_through_a_verb_and_refuse_69(tmp_path, read):
    """Each of `lane-worktrees`' three direct reads of `origin/<branch>`
    (`:711`, `:1002`, `:5596`) goes through `register-grep`, and a 69 from it
    is the register unreadable (Y:4926; the design's S3). In TP:2847-2848's
    new words (lane 2's TX13b item 1; lane 3, #165 6812295982): "on the
    verb's 69 nothing is deleted and the register is named as unreadable,
    and `lane-worktrees` ends with that site's own code, 0 under
    `--report`". So the 69 is the verb's, never the run's. The read is named
    on stdout, where `lane-worktrees` names every read that failed (lane 3's
    ruling on question 121, #165 6813290335: "Stdout stands").
    `[landed-1002]` also keeps the tree and the branch its failed `LANDED`
    read would have let go, and its stdout names `register-grep` and its 69
    (lane 3's (L2-3), #165 6808937880, its stream re-ruled by 6813290335)."""
    argv, match = WORKTREE_READS[read]
    world = ArmWorld(tmp_path / "w")
    stray = world.home / "projects" / "repoA-2-stray"
    stray.mkdir(parents=True)
    tree = world.lane_dir.parent / ".lane-worktrees" / "repoA-2" / "s1"
    if read == "lifecycle-events-711":
        # T217j (lane 4's T404 finding): with no tree the failed read is a note (T404's task
        # line, lane 3's item 2); a lane's tree is what an unreadable claim can take.
        tree.parent.mkdir(parents=True)
        world.git("-C", str(world.lane_dir), "worktree", "add", "-q", "-b", "s1", str(tree))
    gh_log = world.root / "gh.log"
    if read == "landed-1002":
        # AN11a's bug 4 (F13d:237 and :240; lane 4's INV402-404, T404-B): `lane-worktrees`
        # reads `LANDED` only in `MergeEvidence.judge()`, for a lane's tree on a branch whose
        # pull request `gh` lists. So the lane's checkout has a commit and a GitHub origin,
        # the tree is on a branch, `gh` lists one pull request for it, and `LANES_NO_GITHUB`
        # is unset (below).
        world.git("-C", str(world.lane_dir), "commit", "-q", "--allow-empty", "-m", "the lane's work")
        world.git("-C", str(world.lane_dir), "remote", "set-url", "origin",
                  "https://github.com/opensoft/repoA.git")
        tree.parent.mkdir(parents=True)
        world.git("-C", str(world.lane_dir), "worktree", "add", "-q", "-b", LANDED_BRANCH, str(tree))
        _write(world.fakebin / "gh",
               landed_gh(gh_log, world.git("-C", str(tree), "rev-parse", "HEAD").strip()))
        # A #97 SNAPSHOT WHOSE INVENTORY HOLDS THE TREE (lane 3's batch h, #165 6814531692, N1
        # question 2), so that the sweep's 2 is the failed `LANDED` read's alone. Without one,
        # `_lane_claims()` refuses first, "lane repoA-2 has no #97 snapshot (state NONE), yet 1
        # tree(s) are its", and the first refusal set wins (`51eeed8d:lane-worktrees:2508-2509`,
        # `:2531`, `:2656-2661`): an oracle's refusal must come from the fault under test alone
        # (6812490130). It is recorded as a handoff records it, by the checkout's own
        # `lanes-edit.sh`: SWAPPING, the tree, then SWAPPED, which `lane-reconcile` reads as
        # `resumable`, with no live holder.
        for step in (("set-lane-state", "repoA-2", "SWAPPING", "--expect", "none",
                      "--owner", UUID_A2),
                     ("set-lane-tree", "repoA-2", str(tree), "--checkout", str(world.lane_dir)),
                     ("set-lane-state", "repoA-2", "SWAPPED", "--expect", "SWAPPING")):
            done = world.run("lanes-edit.sh", *step)
            assert done.returncode == 0, (read, "the #97 snapshot was not recorded: fix the "
                                          "case's scenario", step, done.stdout, done.stderr)
        listed = world.run("lanes-edit.sh", "lane-trees", "repoA-2")
        assert listed.returncode == 0 and str(tree) in listed.stdout, (
            read, "the snapshot's inventory does not hold the tree: fix the case's scenario",
            listed.returncode, listed.stdout, listed.stderr)
    env = world.arm_env("register-grep", 69, match=match, stderr=UNREACHABLE_STDERR.rstrip("\n"))
    if read == "landed-1002":
        env["LANES_NO_GITHUB"] = None
    result = world.run("lane-worktrees", *argv, env=env)
    if read == "landed-1002" and not world.reached():
        # THE SCENARIO'S CONTROL: `judge()` asked `gh` for the branch's pull request and got
        # its row, so the `LANDED` read came next; what is missing is the read's verb.
        asked = gh_log.read_text(encoding="utf-8") if gh_log.exists() else ""
        assert re.search(rf"^pr list .*--head {LANDED_BRANCH}( |$)", asked, re.M), (
            read, "the scenario never reached judge(): fix the case's scenario", asked,
            result.returncode, result.stdout[-2000:], result.stderr[-2000:])
    assert world.reached(), (read, "the read never went through register-grep",
                             result.returncode, result.stderr[-3000:])
    if read == "lifecycle-events-5596":
        # T217j: the estate report changes nothing and exits 0 (its header), naming what it
        # could not read.
        assert result.returncode == 0, (read, result.stdout[-2000:], result.stderr[-2000:])
        assert re.search(r"Records the report could not read[\s\S]*register-grep` exited 69",
                         result.stdout), (read, result.stdout[-2000:])
    else:
        # THAT SITE'S OWN CODE (TP:2847-2848's new words): on a lane with a tree, a failed read
        # refuses the sweep with `lane-worktrees`' own 2, its exit table's "2 refused: ... or a
        # read failed" (another lane's claim, `:711`'s read, at the base; the register's
        # `LANDED` lines too, at lane 4's T404 `51eeed8d`), never the verb's 69.
        assert result.returncode == 2, (read, "not the site's own code, 2", result.returncode,
                                        result.stdout[-2000:], result.stderr[-2000:])
        # THE REGISTER NAMED AS UNREADABLE, ON STDOUT (lane 3, #165 6813290335). A bare
        # "register" proved nothing: every sweep's "merged means: the register's LANDED line
        # ..." header holds the word.
        assert any(re.search(r"(?i)\bregister\b.*\b(could not be read|unreadable)\b", line)
                   for line in result.stdout.splitlines()), (
            read, "stdout does not name the register as unreadable", result.stdout[-2000:],
            result.stderr[-2000:])
    assert stray.is_dir(), (read, "the sweep deleted on a failed read")
    if read == "lifecycle-events-711":
        assert tree.is_dir(), (read, "the sweep deleted a tree on a failed read")
    if read == "landed-1002":
        # LANE 3'S (L2-3) (#165 6808937880), ITS STREAM RE-RULED (#165 6813290335): a failed
        # `LANDED` read keeps the trees it would have let go, and names the read (B15 tasks:897,
        # T404's "On 69,": "deletes nothing, and names the register as unreadable"). So the
        # tree and its branch remain, and stdout names `register-grep` and its 69: T404's note,
        # "the register's LANDED lines could not be read: `lanes-edit.sh register-grep` exited
        # 69: ", then the read's first stderr line. Nothing need echo it on stderr. The
        # scenario's #97 snapshot (above) leaves the failed read the run's only refusal, so the
        # 2 is the read's (lane 3, #165 6814531692).
        assert tree.is_dir(), (read, "the sweep let the tree go on a failed LANDED read")
        branch = world.git("-C", str(world.lane_dir), "for-each-ref", "--format=%(refname)",
                           f"refs/heads/{LANDED_BRANCH}").strip()
        assert branch == f"refs/heads/{LANDED_BRANCH}", (
            read, "the sweep let the branch go on a failed LANDED read", branch)
        assert any("register-grep" in line and names_the_code(line, 69)
                   for line in result.stdout.splitlines()), (
            read, "stdout does not name register-grep's 69", result.returncode,
            result.stdout[-2000:], result.stderr[-2000:])


def test_index_flag_on_primary_changes_nothing_and_prints_no_index_line(primary):
    """On primary, `--index` changes nothing: with and without it, stdout
    and the exit are equal, and stderr has no index line (Wspec:641-646;
    lane 5's T509).

    `history` TAKES `--all` (T217ze; lane 5, #165 6833182352). A bare
    `history` exits 64 at the arm's selector check
    (`81bd6d3:lanes-edit.sh:23738`), after the door's prefetch and before
    T509's `--index` guard (:23751), so it compared two usage errors. With
    `--all` the arm reads every log, and the estate's logs hold `NOTED` and
    `RULED` lines, so each run answers a timeline. Each half forgets the
    door's calls first, so `history`'s calls are its own, never those
    `lanes --index` left."""
    for argv in (("lanes",), ("history", "--all")):
        primary.door.forget_calls()
        bare = primary.edit(*argv)
        assert primary.door.register_calls(), (argv, "the read never reached the store", bare.stderr)
        if argv[0] == "history":
            assert bare.returncode == 0 and bare.stdout, (
                argv, "no timeline to compare", bare.returncode, bare.stderr[-1500:])
        primary.door.forget_calls()
        flagged = primary.edit(*argv, "--index")
        assert (flagged.returncode, flagged.stdout) == (bare.returncode, bare.stdout), \
            (argv, flagged.returncode, bare.returncode, flagged.stdout[-1500:], bare.stdout[-1500:])
        new = [line for line in flagged.stderr.splitlines()
               if re.search(r"(?i)\bindex\b", line) and line not in bare.stderr.splitlines()]
        assert not new, (argv, "an index line on primary", new)


def test_managed_projection_with_the_database_unreachable_exits_1_never_legacy(primary):
    """With the database unreachable (the fake `psql` exits 2, the store's
    read fails), `managed-projection` exits 1, UNKNOWN, with nothing on
    stdout, and never answers from the legacy row (D10, S4)."""
    primary.door.unreachable()
    result = primary.edit("managed-projection", "repoM-1")
    assert primary.door.register_calls(), ("the read never reached the store", result.stderr)
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
    assert result.stdout == "", result.stdout
    assert "UNKNOWN" in result.stderr, result.stderr
    assert not re.search(r"(?i)legacy", result.stdout + result.stderr), result.stderr


# ------------------------------------------------- the real engine's register
def _sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _lines(text: str) -> list:
    body = text[:-1] if text.endswith("\n") else text
    return body.split("\n") if body else []


_LANE1_INDEX: list = []


def lane1_index():
    """The checkout's `lanes-index` as a module (test_lanes_index's
    `load_indexer`), loaded once: lane 1's derivation helpers, which
    `RealRegister` derives its entries with (T217l)."""
    if not _LANE1_INDEX:
        _LANE1_INDEX.append(load_indexer())
    return _LANE1_INDEX[0]


class RealRegister:
    """A real register on the `pg` fixture's database (T205), brought to
    `primary` with the marker `present` by the documented functions, as
    AT-LR006's fixture does (`test-plan-v3f.md:4610-4615`): as the writer's
    login, `commit_write` with an `import` entry holding the render set, then
    a `cutover` entry, which writes `lanes/STORE` alone (ruling 1), then
    `record_marker`. Each `write(...)` is one more committed `write` entry, a
    seq more. The import and each write are the entries lane 1's own helpers
    derive (item 9). A copy of the checkout's `lanes-index` with `RENDER_GIT_HALF`
    flipped True (T203's `flipped_copy`, PC-5) reads it as the reader's
    login, through a `mode=primary` configuration that names both logins.

    T217h, lane 5's five findings (#165 6771208498) and three of lane 2's own,
    each checked against lane 1's code at `refs/l1/T114`:
      1. the configuration names `reader_url=` beside `register_url=`, which
         `load_config` requires (`_check_register_connections`), with the
         writer's login in `register_url=` and the reader's in `reader_url=`;
      2. `lanes-index` is the flipped copy, never `REPO/lanes-index`, whose
         `RENDER_GIT_HALF = False` ends 78 (`register read`) or 2 (every
         other command, `journal` included) on `mode=primary`;
      3. the client version is the register schema's own `version`, as
         `lanes-index` sends `REGISTER_SCHEMA_VERSION`: `commit_write` and
         `record_marker` refuse a client above `version` or below
         `writers_from` with LR003, and 5000 is above `version`, which
         migration 1 sets to 1;
      4. `[refusal-78]` keeps `mode=primary` and reads through a copy
         flipped False (`unflipped`), Q6(c)'s 78; `mode=files` was a refused
         configuration, 1 under `--for guard`;
      5. the template holds no register until T227: the fixture refuses that
         by its own assertion, as T222's module does, never by a psql error;
      6. (lane 2's) the groups `lanes_register_writer` and
         `lanes_register_reader` are NOLOGIN (lane 1's role block), so every
         session logs in as T228's `lanes_w_fx` or `lanes_r_fx` (the block's
         T228), refused by the fixture's own assertion until T228;
      7. (lane 2's) the superuser is `pgcluster`'s, `lanes_test`: the cluster
         has no `postgres` role, so a superuser read names no user;
      8. (lane 2's) a render set's bytes (`render_set`) are taken as UTF-8
         text, as `_commit` reads them;
      9. (T217l; lane 3's batch 7, #165 6780364102, other ask (4), on N1f's
         doubt in T217h) the entries carry the rows `register commit`
         builds: the import is lane 1's `import_entry` and each write its
         `register_commit_entry`, the one set of derivation helpers
         `register commit` and `import --at` build every row with (lane 3's
         reading 7, #165 6755386771; ERR-49), loaded from the checkout's
         `lanes-index`, over a bare repository that holds each text's blob,
         as their `git cat-file` reads it. So `lanes`, `log_lines`,
         `register_lines` and `object_holds` hold the rows a real register
         would, edits and rows agree, and a log line written after the
         cutover is stamped `primary`, where `log_lines`' CHECK refuses an
         unreadable one with 23514, as it refuses `register commit`'s: the
         cases write well-formed lines. The cutover's entry writes
         `lanes/STORE` alone, from which no row is derived, and is built as
         before. T228's logins are kept.

    So every case built on it FAILS UNTIL T227 and T228 land, beside the
    waits its own docstring names. UNVERIFIED HERE: this bench has no engine.
    The SQL names lane 1's functions as `refs/l1/T109`'s `lanes-index`
    creates them: `commit_write(bigint, uuid, integer, uuid, jsonb)`,
    `record_marker(integer, bigint, text, text)`, `schema_version.version`,
    `register_switch.generation` and `register_head.seq`."""

    #: T228's fixture logins, members of the two groups (block T228).
    WRITER = "lanes_w_fx"
    READER = "lanes_r_fx"
    #: Copied beside the flipped copy, as `Primary` copies them beside the door.
    TOOLS = ("lanes-edit.sh", "lanes", "repos.tsv", "lane-start", "lane-worktrees")
    #: Every entry's author (`journal_author_check`, `^[^<>]+ <[^<>]*>$`; T217k) and
    #: its `not_after`, as text and as the epoch seconds an attempt carries.
    AUTHOR = "T217 fixture <t217@example.invalid>"
    NOT_AFTER = "2999-12-31T00:00:00Z"
    NOT_AFTER_EPOCH = 32503593600
    #: Lane 1's derivation helpers (item 9), the names this fixture calls.
    LANE1_HELPERS = ("import_entry", "register_commit_entry", "RegisterView",
                     "register_doc_lines", "register_shipped_repos_text")

    def __init__(self, pg, root: Path, files: dict):
        self.pg, self.root = pg, root
        root.mkdir(parents=True, exist_ok=True)
        assert self._one("SELECT to_regclass('lanes_register.register_head') IS NOT NULL;") == "t", (
            "the pg fixture's database holds no lanes_register schema: lane 2's T227 builds "
            "tmpl by the bootstrap, which waits for lane 1's L1-A7 (lane 5's finding 5)")
        logins = self._one("SELECT count(*) FROM pg_roles WHERE rolcanlogin AND rolname IN "
                           f"('{self.WRITER}', '{self.READER}');")
        assert logins == "2", (
            f"no {self.WRITER} and {self.READER} logins: lane 2's T228 makes them by `lanes-index "
            "login add fx`; the groups lanes_register_writer and lanes_register_reader are NOLOGIN")
        source = helpers.LANES_INDEX.read_bytes()
        assert len(helpers.RENDER_GIT_HALF_LINE.findall(source)) == 1, (
            f"{helpers.LANES_INDEX} holds no single RENDER_GIT_HALF line to flip: lane 1's T105")
        self.lane1 = lane1_index()
        missing = [name for name in self.LANE1_HELPERS if not hasattr(self.lane1, name)]
        assert not missing, (
            f"{helpers.LANES_INDEX} has no {', '.join(missing)}: lane 1's T112 and T115 derive "
            "the rows `register commit` builds (T217l)")
        self.blobs = root / "blobs.git"
        self._blob_ids: dict = {}
        self._git("init", "-q", "--bare", str(self.blobs))
        self.entry: dict = {}
        self.bin = root / "bin"
        self.copy = helpers.flipped_copy(helpers.LANES_INDEX, self.bin, True)
        self.config = root / "config" / "openRepoTools" / "lanes-index.conf"
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(f"mode=primary\nregister_url={pg.url(self.WRITER)}\n"
                               f"reader_url={pg.url(self.READER)}\n", encoding="utf-8")
        self.config.chmod(0o600)
        self.cache = root / "cache" / "lanes-se"
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.client = int(self._one("SELECT version FROM lanes_register.schema_version;"))
        self.generation = self._one("SELECT generation FROM lanes_register.register_switch;")
        texts = {path: (data.decode("utf-8") if isinstance(data, bytes) else data)
                 for path, data in files.items()}
        self.files = dict(texts)
        self.first = self._commit("import", texts, base=-1)
        store = "mode primary\n"
        self._commit("cutover", {"lanes/STORE": store}, verb="cutover")
        self.n = self.head()
        marked = self._one(f"SELECT lanes_register.record_marker({self.client}, {self.n}, "
                           f"'{'3' * 40}', 'Eagle');", user=self.WRITER)
        assert marked == "present", ("record_marker answered", marked)

    def _one(self, sql: str, user: str | None = None) -> str:
        proc = self.pg.psql(sql) if user is None else self.pg.psql(sql, user=user)
        out = proc.stdout.strip().splitlines()
        return out[-1].strip() if out else ""

    def unflipped(self) -> Path:
        """A copy flipped False: Q6(c)'s refusal of this same `mode=primary`
        configuration, 78 from `register read` in all four forms (contract
        section 2.7), whatever the checkout's own constant says by then."""
        return helpers.flipped_copy(helpers.LANES_INDEX, self.root / "bin-78", False)

    def tools(self) -> Path:
        """The checkout's `lanes-edit.sh` and its siblings copied beside the
        flipped copy, so the copy is the `lanes-index` it runs; its path."""
        for name in self.TOOLS:
            shutil.copy2(REPO / name, self.bin / name)
        return self.bin / "lanes-edit.sh"

    def head(self) -> int:
        return int(self._one("SELECT seq FROM lanes_register.register_head;"))

    @staticmethod
    def _git(*args: str, data: bytes | None = None) -> str:
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        proc = subprocess.run(["git", *args], input=data, capture_output=True, env=env,
                              timeout=60, check=False,
                              stdin=None if data is not None else subprocess.DEVNULL)
        assert proc.returncode == 0, ("git", args, proc.returncode, proc.stderr[-500:])
        return proc.stdout.decode("utf-8").strip()

    def _blob(self, data: bytes) -> str:
        """`data`'s blob id, written once into the bare repository."""
        if data not in self._blob_ids:
            self._blob_ids[data] = self._git("-C", str(self.blobs), "hash-object", "-w",
                                             "--stdin", data=data)
        return self._blob_ids[data]

    def _import_entry(self, texts: dict) -> dict:
        """Lane 1's `import_entry` of `texts`, as `import --at` derives it
        from `import_source`'s answer: `C` and its lanes tree are the old
        fixed ids, and the blobs are this fixture's repository's."""
        index = self.lane1
        data = {path: text.encode("utf-8") for path, text in texts.items()}
        source = {"commit": "1" * 40, "tree": "2" * 40,
                  "blobs": {path: self._blob(raw) for path, raw in data.items()},
                  "render": sorted(data, key=lambda p: p.encode("utf-8")), "data": data,
                  "texts": dict(texts),
                  "lines": {path: index.register_doc_lines(text) for path, text in texts.items()},
                  "warnings": []}
        return index.import_entry(source, root=str(self.blobs), lane="repoA-1",
                                  workstation="Eagle", author=self.AUTHOR,
                                  not_after=self.NOT_AFTER,
                                  shipped_repos=index.register_shipped_repos_text())

    def _write_entry(self, files: dict, verb: str) -> dict:
        """Lane 1's `register_commit_entry` of a write that turns the
        register's files into `files` (a path to its new text, or None to
        remove it), from the attempt `register commit` reads: `changes`,
        `images` and the bases at `n`, over this fixture's repository."""
        index, zero = self.lane1, "0" * 40
        tree_blobs = {path: self._blob(text.encode("utf-8")) for path, text in self.files.items()}
        changes, images, bases = {}, {}, {}
        for path, text in files.items():
            old = self.files.get(path)
            if text is None:
                if old is not None:
                    changes[path] = ("D", tree_blobs[path], zero)
                    bases[path] = old.encode("utf-8")
                continue
            if old == text:
                continue
            images[path] = text.encode("utf-8")
            if old is None:
                changes[path] = ("A", zero, self._blob(images[path]))
            else:
                changes[path] = ("M", tree_blobs[path], self._blob(images[path]))
                bases[path] = old.encode("utf-8")
        att = {"tree": str(self.blobs), "tree_blobs": tree_blobs, "changes": changes,
               "renames": {}, "images": images, "author": self.AUTHOR,
               "message": "write by T217's fixture", "act": None,
               "not_after": self.NOT_AFTER_EPOCH, "repos_blob": None}
        ident = {"verb": verb or "log", "lane": "repoA-1", "workstation": "Eagle",
                 "args_sha256": "0" * 64}
        return index.register_commit_entry(att, ident, index.RegisterView(att, bases),
                                           index.register_shipped_repos_text())

    def _commit(self, kind: str, files: dict, base: int | None = None, verb: str = "") -> int:
        if kind in ("import", "write"):
            # Lane 1's entry, its rows included (item 9; T217l).
            self.entry = (self._import_entry(files) if kind == "import"
                          else self._write_entry(files, verb))
            seq = self._post(self.entry, base)
            for path, text in files.items():
                if text is None:
                    self.files.pop(path, None)
                else:
                    self.files[path] = text
            return seq
        # The cutover's `lanes/STORE`, from which no row is derived.
        # `journal_edits.ord` starts at 1 (its CHECK `ord >= 1`; lane 1's own `edit()` counts
        # `len(edits) + 1`), as T221's and T222's modules number theirs.
        edits, rows, order = [], [], 1
        for path, text in files.items():
            if text is None:
                edits.append({"ord": order, "op": "remove", "path": path})
                rows.append({"path": path, "present": False, "sha256": None, "final_newline": None})
                order += 1
                self.files.pop(path, None)
                continue
            old = self.files.get(path) if kind == "write" else None
            if old is None:
                edits.append({"ord": order, "op": "create", "path": path})
                order += 1
                kept = []
            else:
                kept = _lines(old)
            new = _lines(text)
            if kept != new[:len(kept)]:      # not an append: rewrite the file
                if old is not None:
                    edits.append({"ord": order, "op": "remove", "path": path})
                    edits.append({"ord": order + 1, "op": "create", "path": path})
                    order += 2
                kept = []
            for line in new[len(kept):]:
                edits.append({"ord": order, "op": "append", "path": path, "new_text": line})
                order += 1
            rows.append({"path": path, "present": True, "sha256": _sha(text.encode("utf-8")),
                         "final_newline": text.endswith("\n")})
            self.files[path] = text
        return self._send(kind, edits, rows, verb, base)

    def _send(self, kind: str, edits: list, rows: list, verb: str = "",
              base: int | None = None) -> int:
        """The cutover's entry, its journal object, `edits` and the `files`
        rows, sent by `_post`; the seq it made."""
        # `journal.author` is `Name <address>` (journal_author_check, `^[^<>]+ <[^<>]*>$`).
        journal = {"kind": kind, "verb": verb or ("import" if kind == "import" else "log"),
                   "lane": "repoA-1", "workstation": "Eagle",
                   "author": self.AUTHOR,
                   "message": f"{kind} by T217's fixture", "args_sha256": "0" * 64}
        if kind == "import":
            journal.update(git_commit="1" * 40, git_tree="2" * 40)
        entry = {"journal": journal, "edits": edits, "files": rows,
                 "not_after": self.NOT_AFTER}
        return self._post(entry, base)

    def _post(self, entry: dict, base: int | None = None) -> int:
        """One `commit_write` call of `entry`, as the writer's login; the
        seq it made."""
        import uuid as _uuid
        base = self.head() if base is None else base
        sql = ("BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
               f"SELECT lanes_register.commit_write({base}, '{_uuid.uuid4()}'::uuid, {self.client}, "
               f"'{self.generation}'::uuid, $entry${json.dumps(entry)}$entry$::jsonb);\nCOMMIT;\n")
        return int(self.pg.psql(sql, user=self.WRITER).stdout.split()[0])

    def write(self, files: dict) -> int:
        self._commit("write", files)
        return self.head()

    def replace(self, path: str, line_no: int, new_text: str) -> int:
        """One committed `write` entry whose one edit is a `replace` of line
        `line_no` of `path` (`commit_write`'s step 6 checks its `old_sha256`
        against the stored line, the sha256 of its UTF-8 text without its LF),
        as lane 1's `register_line_edits` sends a write that changes that line
        alone (T217l); the seq it made."""
        lines = _lines(self.files[path])
        text = "\n".join(lines[:line_no - 1] + [new_text] + lines[line_no:]) + "\n"
        seq = self._commit("write", {path: text})
        ops = [(e["op"], e["line_no"]) for e in self.entry["edits"]]
        assert ops == [("replace", line_no)], ("not one replace", ops)
        return seq

    def env(self, extra: dict | None = None) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LANES_", "PG", "TMUX"))}
        env.update({"HOME": str(self.root), "LANES_INDEX_CONFIG": str(self.config),
                    "XDG_CONFIG_HOME": str(self.config.parent.parent), "LANES_WORKSTATION": "Eagle"})
        env.update(extra or {})
        return env

    def index(self, *args, env: dict | None = None,
              copy: Path | None = None) -> subprocess.CompletedProcess:
        """`lanes-index` as the flipped copy, or as `copy` where one is named."""
        return subprocess.run([sys.executable, str(copy or self.copy), *args], env=self.env(env),
                              capture_output=True, text=True, timeout=60, check=False,
                              stdin=subprocess.DEVNULL)

    def read(self, *args, env: dict | None = None,
             copy: Path | None = None) -> subprocess.CompletedProcess:
        return self.index("register", "read", *args, env=env, copy=copy)

    def family(self) -> dict:
        return {p.name[len(self.cache.name):]: p.read_bytes()
                for p in self.cache.parent.glob(self.cache.name + ".*") if p.is_file()}


def well_formed(text: str, second: int) -> str:
    """A well-formed `NOTED` line of repoA-1's, its free text `text`: the
    lines the cases write after the cutover are stamped `primary`, and
    `log_lines`' CHECK refuses an unreadable primary row with 23514, as it
    refuses `register commit`'s (T217l). The rest of the line holds no `.`
    and no `X`, so a `--grep` key matches its text alone."""
    return (f"NOTED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-07T00:00:{second:02d}Z, "
            f"lane:repoA-1 — {text}\n")


#: `check_lane_name`'s class (CLI4.5 section 3.6; the stub's own copy).
LANE_CLASS_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")


def hex_slot(key: str) -> str:
    return "%" + key.encode("utf-8").hex()


@contextlib.contextmanager
def hook_pid():
    """THE HOOK'S `$$`, FOR A GUARD READ'S `--pid` (contract section 3.6:
    "`--pid <pid>` ... is the hook's own pid, `$$`, in forms 2 and 4", and
    "the client reads `T0` from it"). It yields the pid of a stand-in for the
    hook, a `sleep` started just before the read, as a hook's own start is,
    and stops it after the read. T507 cuts a guard read at `T0` + 3.75 s
    from that start, and an age at or above the cut exits 2, "too late to
    verify" (section 3.6's 2; `register_guard_t0`). The pytest process's own
    pid is minutes old on a runner, so with it every guard read ended 2
    (lane 1's round 6b census, #165 6827592167, item 2). The stand-in is
    AT-F7's, `test_sql_register_outage.py`'s `_stand_in`, at an age of 0."""
    standin = subprocess.Popen(["sleep", "120"], start_new_session=True,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    try:
        yield str(standin.pid)
    finally:
        # Kill it, then a reap bounded at 10 s, as `GuardSession.close()` does: a
        # stand-in that a kill does not take fails the case and never hangs the
        # run (lane 5, #165 6932056536).
        standin.kill()
        try:
            standin.wait(timeout=10)
        except subprocess.TimeoutExpired:
            standin.kill()
            standin.wait(timeout=10)


#: The render set lane 1's three read: two lanes, their logs and the aliases.
def l1_files(extra: dict | None = None) -> dict:
    files = {
        "lanes/LANES.md": ("# LANES.md\n\n| lane | session id | workstation / env / user | started "
                           "(UTC) | objects owned | handoff path | state |\n|---|---|---|---|---|---|---|\n"
                           f"| `repoA-1` | harness `{UUID_A1}` | Eagle / test / brett | 2026-10-01T00:00Z "
                           "| none | handoffs/repoA-1.md | LIVE · 2026-10-01T00:00:00Z · working |\n"),
        "lanes/aliases.tsv": "# old\tnew\tutc\n",
        "lanes/log/repoA-1.md": (f"STARTED — lane repoA-1, session {UUID_A1}@Eagle, "
                                 "2026-10-01T00:00:00Z, lane:repoA-1 → home opensoft/repoA\n"),
    }
    files.update(extra or {})
    return files


#: `guard_second_read_at`'s cases (L1v4.5:301-310): the key, what to set up
#: after form 2 has cached the family at `n`, and the end.
GUARD_SECOND_READ = ["moved-head", "case-insensitive", "outside-the-class", "no-mirror",
                     "generation-differs", "no-head", "above-the-head", "below-the-first-seq",
                     "case-duplicates", "dash-key", "refusal-78", "refused-configuration-1",
                     "empty-lane-64"]


@pytest.mark.parametrize("case", GUARD_SECOND_READ)
def test_guard_second_read_at_its_head_writes_one_log_and_fails_open(pg, tmp_path, case):
    """FORM 4, `register read --for guard --at <n> --pid <pid> --cache <file>
    --lane=<key>`, after form 2 has cached the family at `n` (lane 1's T113;
    L1v4.5:301-310; B4): it writes its one log's pair (`.log.<key>` and
    `.logpath.<key>`, or `.log.%<hex>` and `.logpath.%<hex>` for a key outside
    `check_lane_name`'s class, O18) and nothing else, at `n`; `.head` is
    byte-identical and no `.outage` is written; and every end but 0 writes no
    `.log.<key>`. Each guard read passes the pid of a stand-in started just
    before it (`hook_pid`), as the hook's `$$` is, so T507's cut at `T0` +
    3.75 s runs from that read's own start. Real engine: it skips without one
    (T205)."""
    extra = {}
    if case == "outside-the-class":
        extra["lanes/log/a,b.md"] = "NOTED — a log whose name is outside the class\n"
    if case == "dash-key":
        extra["lanes/log/-x.md"] = "NOTED — a log whose name begins with a dash\n"
    if case == "case-duplicates":
        extra["lanes/log/RepoA-1.md"] = "NOTED — the case pair's other half\n"
    reg = RealRegister(pg, tmp_path / "real", l1_files(extra))
    with hook_pid() as pid:
        pre = reg.read("--for", "guard", "--prefetch", "--cache", str(reg.cache), "--pid", pid,
                       "--repo", str(tmp_path), "--lane=repoA-1")
    assert pre.returncode == 0 and pre.stdout.startswith("mode primary"), (pre.returncode, pre.stderr)
    n, at_n = reg.head(), reg.files["lanes/log/repoA-1.md"]
    head_before = (reg.cache.parent / (reg.cache.name + ".head")).read_bytes()
    key, at, env, expect, copy = "repoA-1", str(n), {}, 0, None
    if case == "moved-head":
        reg.write({"lanes/log/repoA-1.md": at_n + well_formed("the head moved past n", 0)})
    elif case == "case-insensitive":
        key = "REPOA-1"
    elif case == "outside-the-class":
        key = "a,b"
    elif case == "no-mirror":
        mirror = tmp_path / "mirror"
        (mirror / "lanes" / "log").mkdir(parents=True)
        (mirror / "lanes" / "log" / "repoA-1.md").write_text("ANOTHER TEXT\n", encoding="utf-8")
        mirror.chmod(0)
        env = {"LANES_REPO": str(mirror)}
    elif case == "generation-differs":
        head = reg.cache.parent / (reg.cache.name + ".head")
        head.write_bytes(re.sub(rb"(?m)^generation=.*$", b"generation=" + str(UUID_M1).encode(),
                                head.read_bytes()))
        head_before, expect = head.read_bytes(), 69
    elif case == "no-head":
        head = reg.cache.parent / (reg.cache.name + ".head")
        head.rename(head.with_name(head.name + ".aside"))
        head_before, expect = None, 69
    elif case == "above-the-head":
        at, expect = str(n + 5), 69
    elif case == "below-the-first-seq":
        at, expect = str(reg.first - 1), 69
    elif case == "case-duplicates":
        expect = 69
    elif case == "dash-key":
        key = "-x"
    elif case == "refusal-78":
        # Q6(c)'s refusal (T217h; lane 5's finding 4): the same `mode=primary` configuration, read
        # by a copy flipped False, is 78 in all four forms; `mode=files` is a refused one, 1 here.
        copy, expect = reg.unflipped(), 78
    elif case == "refused-configuration-1":
        reg.config.chmod(0o644)                                      # readable by others
        expect = 1                                                   # R09's half follows
    elif case == "empty-lane-64":
        key, expect = "", 64
    before = reg.family()
    try:
        with hook_pid() as pid:
            result = reg.read("--for", "guard", "--at", at, "--pid", pid, "--cache",
                              str(reg.cache), f"--lane={key}", env=env, copy=copy)
    finally:
        if case == "no-mirror":
            (tmp_path / "mirror").chmod(0o755)
    after = reg.family()
    assert result.returncode == expect, (case, result.returncode, result.stdout, result.stderr)
    slot = key if LANE_CLASS_RE.match(key) else hex_slot(key)
    changed = sorted(k for k in after if after.get(k) != before.get(k))
    assert ".outage" not in after, (case, "an .outage was written")
    if head_before is not None:
        assert after.get(".head") == head_before, (case, ".head changed")
    if expect == 0:
        assert set(changed) <= {f".log.{slot}", f".logpath.{slot}"}, (case, changed)
        assert f".log.{slot}" in after, (case, "no log written", sorted(after))
        if case in ("moved-head", "no-mirror", "case-insensitive"):
            assert after[f".log.{slot}"] == at_n.encode("utf-8"), (case, after[f".log.{slot}"])
            assert after[f".logpath.{slot}"].strip() == b"lanes/log/repoA-1.md", \
                (case, after[f".logpath.{slot}"])
    else:
        assert not any(k.startswith(".log.") and k not in before for k in after), (case, changed)
    if case == "refused-configuration-1":
        # R09'S HALF (T217h; contract section 2.7's 1, "R09's included"): a configuration whose
        # URLs name a TCP host that is not loopback, with no `sslmode=verify-full`, refused at
        # load, before any connection.
        reg.config.write_text("mode=primary\n"
                              f"register_url=postgresql://{reg.WRITER}@db.invalid:5432/lanes\n"
                              f"reader_url=postgresql://{reg.READER}@db.invalid:5432/lanes\n",
                              encoding="utf-8")
        reg.config.chmod(0o600)
        before = reg.family()
        with hook_pid() as pid:
            tls = reg.read("--for", "guard", "--at", at, "--pid", pid, "--cache", str(reg.cache),
                           f"--lane={key}")
        after = reg.family()
        assert tls.returncode == 1, (case, "R09", tls.returncode, tls.stdout, tls.stderr)
        assert ".outage" not in after, (case, "R09", "an .outage was written")
        assert after.get(".head") == head_before, (case, "R09", ".head changed")
        assert not any(k.startswith(".log.") and k not in before for k in after), \
            (case, "R09", sorted(after))


@pytest.mark.parametrize("case", ["form-3", "dash-key", "forms-1-and-2"])
def test_log_key_hex_slot_holds_a_key_outside_the_class_and_is_never_cached(pg, tmp_path, case):
    """O18 (lane 1's T113; L1v4.5:312-317): form 3 with `--log-key=<key>`,
    for keys outside the class (one holding `,`, one `/`), writes each its
    own `.log.%<hex>` and `.logpath.%<hex>`, rewritten on each read and never
    counted as cached; a key beginning with `-` is read as the key; and
    forms 1 and 2 fetch no log for such a key and refuse nothing. Real
    engine: it skips without one (T205)."""
    reg = RealRegister(pg, tmp_path / "real",
                       l1_files({"lanes/log/a,b.md": "NOTED — a comma in the name\n",
                                 "lanes/log/-x.md": "NOTED — a dash first\n"}))
    pre = reg.read("--prefetch", "--cache", str(reg.cache), "--all")
    assert pre.returncode == 0, (pre.returncode, pre.stderr)
    n = reg.head()
    if case == "forms-1-and-2":
        assert not any(k.startswith(".log.%") for k in reg.family()), sorted(reg.family())
        with hook_pid() as pid:
            two = reg.read("--for", "guard", "--prefetch", "--cache", str(reg.cache) + "-g",
                           "--pid", pid, "--repo", str(tmp_path), "--lane=a,b")
        assert two.returncode == 0, (two.returncode, two.stderr)
        assert not list(reg.cache.parent.glob(reg.cache.name + "-g.log.*")), "form 2 fetched the log"
        return
    keys = ["a,b", "c/d"] if case == "form-3" else ["-x"]
    first = {}
    for key in keys:
        result = reg.read("--since", str(n), "--cache", str(reg.cache), f"--log-key={key}")
        assert result.returncode == 0, (case, key, result.returncode, result.stderr)
        family = reg.family()
        assert f".log.{hex_slot(key)}" in family and f".logpath.{hex_slot(key)}" in family, \
            (case, key, sorted(family))
        first[key] = (reg.cache.parent / (reg.cache.name + f".log.{hex_slot(key)}")).stat().st_mtime_ns
    head = reg.family()[".head"]
    assert b"%" not in head, ("an out-of-class slot was counted as cached", head)
    for key in keys:
        reg.read("--since", str(n), "--cache", str(reg.cache), f"--log-key={key}")
        again = (reg.cache.parent / (reg.cache.name + f".log.{hex_slot(key)}")).stat().st_mtime_ns
        assert again > first[key], (key, "not rewritten on its next read")


PICKAXE = ["dot-in-name", "count-kept", "no-match", "at-bound", "at-needs-generation",
           "past-head-or-other-generation",
           # Five more, new since v3f (R-F11-1; T217i): lane 3's accepted readings of `--last`
           # for T114 (lane 1, #165 6755628366 reading 5; lane 3, 6755922262 reading 5).
           "generation-needs-at", "empty-grep", "path-empty-or-control", "at-minus-1",
           "replay-mismatch-69"]

#: The three whose 64 is `journal`'s own argument check, made "before anything
#: is read" (lane 1's `cmd_journal`; contract section 3.6), so they need no
#: register: they run the checkout's `lanes-index` and fail by their own
#: assertion here, without an engine. The other eight read the register.
PICKAXE_NO_ENGINE = ("generation-needs-at", "empty-grep", "path-empty-or-control")


def refused_before_any_connection(tmp_path: Path, case: str) -> None:
    """`journal --last`'s 64 for `case`, by the checkout's own `lanes-index`,
    with no register and no engine. Each refusal is paired with a CONTROL, the
    same argv with only the faulty part made valid, which must not end 64: so a
    `lanes-index` too old to have `journal` at all, whose 64 is "unknown
    subcommand" (F8), fails on the control and never passes for the refusal.
    The control ends at the configuration, a named file that does not exist
    (2), which is before any connection."""
    log, key, generation = "lanes/log/repoA-1.md", "aXb", str(UUID_M1)
    root = tmp_path / "no-register"
    root.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LANES_", "PG", "TMUX"))}
    env.update({"HOME": str(root), "XDG_CONFIG_HOME": str(root / "config"),
                "LANES_INDEX_CONFIG": str(root / "no-such.conf"), "LANES_WORKSTATION": "Eagle"})

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(helpers.LANES_INDEX), "journal", "--last", *args],
                              env=env, capture_output=True, text=True, timeout=60, check=False,
                              stdin=subprocess.DEVNULL)

    def refused(control: tuple, *variants: tuple) -> None:
        valid = run(*control)
        assert valid.returncode != 64, (case, "the valid form is itself a usage error", control,
                                        valid.returncode, valid.stderr)
        for variant in variants:
            result = run(*variant)
            assert result.returncode == 64, (case, variant, result.returncode, result.stdout,
                                             result.stderr)
            assert result.stdout == "", (case, variant, "a usage error prints nothing on stdout",
                                         result.stdout)

    if case == "generation-needs-at":
        refused(("--path", log, "--grep", key, "--at", "5", "--generation", generation),
                ("--path", log, "--grep", key, "--generation", generation))
    elif case == "empty-grep":
        refused(("--path", log, "--grep", key),
                ("--path", log, "--grep", ""), ("--path", log, "--grep="))
    else:
        refused(("--path", log, "--grep", key),
                ("--path", "", "--grep", key),
                ("--path", "lanes/log/repoA" + chr(1) + "-1.md", "--grep", key),
                ("--path", "lanes/log/repoA" + chr(10) + "-1.md", "--grep", key))


@pytest.mark.parametrize("case", PICKAXE)
def test_journal_last_pickaxe_finds_the_newest_entry_that_changes_the_keys_count(
        request, tmp_path, case):
    """`journal --last --path <log> --grep <key> [--at <n> --generation <g>]`
    (lane 1's T114; L1v4.5:327-330; lane 5's C7, C8) gives `seq=` of the
    newest entry at or below `n` whose edits change how many times `<key>`
    occurs in the log, as a fixed string (git's `-S`). Real engine: it skips
    without one (T205), but for the three `PICKAXE_NO_ENGINE` cases, whose 64
    is decided before any connection."""
    if case in PICKAXE_NO_ENGINE:
        return refused_before_any_connection(tmp_path, case)
    log = "lanes/log/repoA-1.md"
    reg = RealRegister(request.getfixturevalue("pg"), tmp_path / "real", l1_files())
    text = reg.files[log]
    seq_axb = reg.write({log: text + well_formed("lane aXb", 1)})
    text = reg.files[log]
    seq_dot = reg.write({log: text + well_formed("lane a.b", 2)})
    text = reg.files[log]
    reg.write({log: text + well_formed("lane aXb again", 3)})
    text = reg.files[log]
    seq_kept = reg.write({log: text.replace(well_formed("lane a.b", 2),
                                            well_formed("lane a.b, reworded", 2))})

    def last(*args):
        return reg.index("journal", "--last", "--path", log, *args)

    if case == "dot-in-name":
        result = last("--grep", "a.b")
        assert result.returncode == 0 and f"seq={seq_dot}" in result.stdout.split(), \
            (result.returncode, result.stdout, result.stderr)
    elif case == "count-kept":
        result = last("--grep", "a.b")
        assert f"seq={seq_kept}" not in result.stdout.split(), (seq_kept, result.stdout)
        assert f"seq={seq_dot}" in result.stdout.split(), result.stdout
    elif case == "no-match":
        result = last("--grep", "no-such-lane")
        assert result.returncode == 0, (result.returncode, result.stderr)
        assert not re.search(r"(?m)^seq=", result.stdout), result.stdout
    elif case == "at-bound":
        result = last("--grep", "aXb", "--at", str(seq_dot), "--generation", reg.generation)
        assert result.returncode == 0 and f"seq={seq_axb}" in result.stdout.split(), \
            (result.returncode, result.stdout, result.stderr)
    elif case == "at-needs-generation":
        result = last("--grep", "aXb", "--at", str(seq_dot))
        assert result.returncode == 64, (result.returncode, result.stderr)
    elif case == "at-minus-1":
        # `--at -1` with `.head`'s generation is ACCEPTED and never 64: all this case asserts
        # until a draft states what it means (lane 1, #165 6767591676: draft 4.13's open point 3).
        result = last("--grep", "aXb", "--at", "-1", "--generation", reg.generation)
        assert result.returncode != 64, (result.returncode, result.stdout, result.stderr)
    elif case == "replay-mismatch-69":
        # A journal whose `replace` line does not match its `old_sha256` is 69, and gives no
        # rank. `commit_write` refuses a mismatched `old_sha256` when it is sent, so the entry
        # is made right and its journal row is spoiled afterwards, by the cluster's superuser.
        before = last("--grep", "aXb")
        assert before.returncode == 0 and re.search(r"(?m)^seq=[0-9]+$", before.stdout), \
            ("the journal does not replay before it is spoiled", before.returncode, before.stdout,
             before.stderr)
        line = _lines(reg.files[log])[2]
        seq = reg.replace(log, 3, line + ", reworded twice")
        reg.pg.psql("UPDATE lanes_register.journal_edits SET old_sha256 = repeat('0', 64) "
                    f"WHERE seq = {seq} AND op = 'replace';")
        spoiled = last("--grep", "aXb")
        assert spoiled.returncode == 69, (spoiled.returncode, spoiled.stdout, spoiled.stderr)
        assert not re.search(r"(?m)^seq=", spoiled.stdout), ("a rank was given", spoiled.stdout)
    else:
        above = last("--grep", "aXb", "--at", str(reg.head() + 1), "--generation", reg.generation)
        assert above.returncode == 69, (above.returncode, above.stderr)
        other = last("--grep", "aXb", "--at", str(seq_dot), "--generation", UUID_M1)
        assert other.returncode == 69, (other.returncode, other.stderr)


@pytest.mark.parametrize(("answer", "lane"), [pytest.param(0, "repoM-1", id="0"),
                                              pytest.param(1, "repoM-2", id="1"),
                                              pytest.param(8, "repoA-1", id="8")])
def test_managed_projection_answers_0_1_8_from_sql_as_files_mode_does(pg, estate, tmp_path,
                                                                      answer, lane):
    """RE (R3's N7): for a lane set up to give each of `managed-projection`'s
    answers, 0, 1 and 8, the answer and the exit on primary, read from SQL,
    equal files mode's on the same register (D10, S4). The register is the
    estate's, brought to primary on the `pg` fixture's database by AT-LR006's
    route (`RealRegister`). The primary run is the checkout's `lanes-edit.sh`
    copied beside the flipped copy, so the `lanes-index` it asks is that copy
    (T217h; lane 5's finding 2). Real engine: it skips without one (T205)."""
    files = estate.edit("managed-projection", lane)
    assert files.returncode == answer, (lane, "files mode's answer", files.returncode, files.stderr)
    reg = RealRegister(pg, tmp_path / "real", render_set(estate.wip))
    edit = reg.tools()
    sql = estate.run("bash", edit, "managed-projection", lane,
                     env={"LANES_EDIT": str(edit), "LANES_INDEX_CONFIG": str(reg.config),
                          "LANES_INDEX": None})
    assert (sql.returncode, sql.stdout) == (files.returncode, files.stdout), \
        (lane, sql.returncode, sql.stdout, sql.stderr, files.returncode, files.stdout)


# ------------------------------------------------------- lane 5's nine (A5)
#: A `git` that reads the register: `show`, `grep`, `cat-file` or `log` on a
#: `lanes/` path, as `GIT_TRACE` logs it.
GIT_REGISTER_READ = re.compile(r"trace: (?:built-in|exec): git (?:show|grep|cat-file|log)\b[^\n]*lanes")
GIT_NETWORK = re.compile(r"trace: (?:built-in|exec|run_command): git (?:fetch|ls-remote)\b")


def traced(path: Path, pattern: re.Pattern) -> list:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if pattern.search(line)]


def test_a_primary_reader_makes_one_prefetch_and_every_read_site_reads_its_cache_at_one_n(primary):
    """T505: on primary a reader makes ONE prefetch (form 1) in its main
    shell, and every read site reads the family it cached at that one `n`:
    no second read where every file it needs was prefetched, and no `git`
    read of the register. Its answer is the store's."""
    for argv in (("register-row", STORE_ONLY_LANE), ("canon-lane", STORE_ONLY_LANE)):
        trace = primary.e.root / f"git-trace-{argv[0]}"
        primary.door.forget_calls()
        result = primary.edit(*argv, env={"GIT_TRACE": str(trace)})
        calls = primary.door.register_calls()
        assert [c["form"] for c in calls] == [1], (argv, "not one prefetch alone", calls,
                                                   result.stderr[-1500:])
        assert result.returncode == 0, (argv, result.returncode, result.stderr[-1500:])
        assert STORE_ONLY_LANE in result.stdout, (argv, "not the store's answer", result.stdout)
        assert not traced(trace, GIT_REGISTER_READ), (argv, traced(trace, GIT_REGISTER_READ))


@pytest.mark.parametrize("case", ["moved-head", "case-duplicates", "failed-read"])
def test_a_read_site_with_no_prefetched_file_makes_one_more_register_read_and_never_a_git_read(
        primary, case):
    """T505 (O17's form 3; C3, C11): a read site whose file the prefetch did
    not fetch makes one more `register read`, form 3 `--since <n>`, never a
    `git` read: `[moved-head]`, the head moved past `n` before it, answers at
    `n′`; `[case-duplicates]`, two render-set logs that differ only by case,
    is 69 with nothing on stdout; `[failed-read]`, the class's failed read,
    is 69, never files mode."""
    log = f"lanes/log/{STORE_ONLY_LANE}.md"
    moved = STORE_ONLY_LOG + (f"NOTED — lane {STORE_ONLY_LANE}, session {STORE_ONLY_UUID}@Eagle, "
                              f"2026-10-05T01:00:00Z, lane:{STORE_ONLY_LANE} — the head moved\n")
    if case == "moved-head":
        primary.door.fail(narrow="register,aliases", move={log: moved})
    elif case == "case-duplicates":
        primary.door.commit({f"lanes/log/{STORE_ONLY_LANE.upper()}.md": "NOTED — the case pair\n"})
        primary.door.fail(narrow="register,aliases")
    else:
        primary.door.fail(narrow="register,aliases", all=True, forms=[3], exit=69,
                          stdout="mode primary\n", stderr=UNREACHABLE_STDERR)
    n, _gen = primary.door.head()
    trace = primary.e.root / "git-trace"
    result = primary.edit("lane-last", STORE_ONLY_LANE, env={"GIT_TRACE": str(trace)})
    calls = primary.door.register_calls()
    assert [c["form"] for c in calls].count(1) == 1, (case, calls, result.stderr[-1500:])
    thirds = [c["argv"] for c in calls if c["form"] == 3]
    assert len(thirds) == 1, (case, "not one second read", calls)
    assert thirds[0][thirds[0].index("--since") + 1] == str(n), (case, thirds[0])
    assert not traced(trace, GIT_REGISTER_READ), (case, traced(trace, GIT_REGISTER_READ))
    if case == "moved-head":
        assert result.returncode == 0, (case, result.returncode, result.stderr[-1500:])
    else:
        assert result.returncode == 69, (case, result.returncode, result.stdout, result.stderr[-1500:])
        assert result.stdout == "", (case, result.stdout)


def test_the_flush_helper_drops_the_whole_read_family(tmp_path):
    """T505 (C6): `reg_flush`, taken from `lanes-edit.sh` by its text (the
    script cannot be sourced), drops `.register`, `.aliases`, `.archive`,
    `.paths`, `.head`, `.outage`, every `.log.*` and `.logpath.*`, keeps
    `.direct`, and empties `LANES_REGISTER_CACHE` (tasks:763; lane 5's NIT,
    #165 6888923188)."""
    found = re.search(r"^reg_flush\(\) *\{.*?^\}[ \t]*$", LANES_EDIT.read_text(encoding="utf-8"),
                      re.M | re.S)
    assert found, "lanes-edit.sh has no reg_flush"
    cache = tmp_path / "se"
    members = [".register", ".aliases", ".archive", ".paths", ".head", ".outage", ".log.repoA-1",
               ".logpath.repoA-1", ".log.%2c", ".logpath.%2c"]
    kept = [".direct"]
    for member in members + kept:
        (tmp_path / f"se{member}").write_text("cached\n", encoding="utf-8")
    script = (found.group(0) + '\nSE_CACHE_FILE="$1"; LANES_REGISTER_CACHE="$1.register"\n'
              'reg_flush\nprintf "[%s]" "$LANES_REGISTER_CACHE"\n')
    result = subprocess.run(["bash", "-c", script, "flush", str(cache)], capture_output=True,
                            text=True, timeout=30, check=False, stdin=subprocess.DEVNULL)
    assert result.returncode == 0, (result.returncode, result.stderr)
    assert result.stdout == "[]", result.stdout
    left = [m for m in members if (tmp_path / f"se{m}").exists()]
    assert not left, ("the family is not all dropped", left)
    gone = [m for m in kept if not (tmp_path / f"se{m}").exists()]
    assert not gone, ("the flush dropped what it keeps", gone)


def test_swapped_ranks_through_journal_last_on_primary(primary):
    """T506 (C7, C8): on primary, `swapped`'s rank is the head less
    `lanes-index journal --last --path <log> --grep <key> --at <n>
    --generation <g>`, with `.head`'s `n` and generation, never `git log -S`.
    The store's `repoA-2` log ends on a swap's `PAUSED` on Eagle, since
    `swapped` ranks only such a lane and exits 8 where none is (lane 5's T506
    finding, #165 6812983568; the record in T217z's `SWAP_LOG` shape)."""
    log = "lanes/log/repoA-2.md"
    primary.door.commit({log: primary.door.register[log].decode("utf-8") + (
        f"PAUSED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T05:00:00Z, lane:repoA-2 → "
        f"swap; window sess:1 @3; workstation Eagle; dir /work/repoA2; profile team-01b; "
        f"agent claude; transcript {UUID_A2}\n")})
    helpers.stub_outcome(primary.door.store, "journal --last", exit=0, stdout="seq=1\n")
    trace = primary.e.root / "git-trace"
    result = primary.edit("swapped", env={"GIT_TRACE": str(trace)})
    lasts = [c["argv"] for c in primary.door.calls() if c["argv"][:2] == ["journal", "--last"]]
    assert lasts, ("swapped never asked journal --last", result.returncode, result.stderr[-1500:])
    n, generation = primary.door.head()
    for argv in lasts:
        assert argv[argv.index("--path") + 1].startswith("lanes/log/"), argv
        assert "--grep" in argv, argv
        assert argv[argv.index("--at") + 1] == str(n), (argv, n)
        assert argv[argv.index("--generation") + 1] == generation, (argv, generation)
    assert not traced(trace, re.compile(r"git log\b[^\n]*-S")), traced(trace, re.compile(r"git log"))


#: Readers whose files-mode run calls `log_sync`, which fetches: the first
#: that fetches in files mode is the case's.
LOG_SYNC_READS = (("history",), ("lanes", "--fetch"), ("lane-last", "repoA-1"))


def test_log_sync_on_primary_makes_no_fetch_and_no_flush(primary):
    """T506: `log_sync` on primary makes no fetch and no flush: the read
    that fetches in files mode makes no `git fetch` and no `ls-remote` on
    primary, and its one prefetch is never made again (a flush would empty
    the family and refetch it)."""
    chosen = None
    for argv in LOG_SYNC_READS:
        trace = primary.e.root / f"files-trace-{argv[0]}"
        primary.files_edit(*argv, env={"GIT_TRACE": str(trace)})
        if traced(trace, GIT_NETWORK):
            chosen = argv
            break
    assert chosen, "no reader fetched in files mode: the control found no log_sync"
    trace = primary.e.root / "primary-trace"
    result = primary.edit(*chosen, env={"GIT_TRACE": str(trace)})
    calls = primary.door.register_calls()
    assert [c["form"] for c in calls].count(1) == 1, (chosen, calls, result.stderr[-1500:])
    assert not traced(trace, GIT_NETWORK), (chosen, traced(trace, GIT_NETWORK))


def test_the_local_file_unions_are_skipped_on_primary(primary):
    """T506 (W:4865): on primary the local-file unions are skipped, since a
    primary write is in SQL before it returns. `row_of_lane_local` is the
    union's source: a session id only this checkout's copy of a row holds is
    in files mode's `register-row-local` answer (the control), and not in
    primary's, which answers the register's row."""
    lanes = primary.e.wip / "lanes" / "LANES.md"
    text = lanes.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| `repoA-2` |"))
    lanes.write_text(text.replace(row, row.replace(f"`{UUID_A2}`", f"`{UUID_A2}` → `{LOCAL_SID}`", 1)),
                     encoding="utf-8")                         # this checkout's copy only
    local = primary.files_edit("register-row-local", "repoA-2")
    assert local.returncode == 0 and LOCAL_SID in local.stdout, \
        ("the control: files mode did not read this checkout's row", local.returncode, local.stdout)
    result = primary.edit("register-row-local", "repoA-2")
    assert primary.door.register_calls(), ("the read never reached the store", result.stderr)
    assert result.returncode == 0 and UUID_A2 in result.stdout, (result.returncode, result.stdout)
    assert LOCAL_SID not in result.stdout, ("a local row's id on primary", result.stdout)


#: T509's footers (`81bd6d3:lanes:853-860`), as lane 5 quotes them (#165
#: 6833182352) and lane 3 keeps them (6833266940): `<k> lane(s)`, then ` of
#: <repo>` where the listing has one, then what answered.
FOOTER_HEAD = r"^[0-9]+ lane\(s\)(?: of \S+)?, "
MIRROR_FOOTER = ("read from the register's mirror and not from the register: the `read: mirror` "
                 "line above says why.")
FELL_BACK_LINE = ("  and the fetch did not answer, so the mirror is this checkout's own copy. "
                  "What the helper said:")


def test_the_lanes_footer_on_primary_names_the_register_and_claims_no_local_read(primary):
    """T509 (R43): on primary the `lanes` script's footer names the store
    that answered and claims no local read, in T509's strings (T217zf):
      * the register answered: `read: register at seq <n>` on stderr, and
        the footer `<k> lane(s), as of the register at seq <n>.`;
      * the store unreachable, so the mirror answered: the `read: mirror`
        line on stderr, the mirror footer, and no seq claimed;
      * that again under `--fetch` with origin gone: the fallback line under
        the mirror footer, then what the helper said, indented.
    Each run has the script's capture file. Where it has none, T509 keeps
    today's footer in every mode (lane 3, #165 6833266940), and no run here
    takes that path."""
    result = primary.script("lanes")
    assert primary.door.register_calls(), ("the listing never reached the store", result.stderr)
    n, _gen = primary.door.head()
    out = result.stdout + result.stderr
    assert re.search(rf"^read: register at seq {n}$", result.stderr, re.M), (
        result.returncode, result.stderr[-1500:])
    assert re.search(rf"{FOOTER_HEAD}as of the register at seq {n}\.$", result.stdout, re.M), (
        result.returncode, result.stdout[-1500:])
    assert not MIRROR_LINE.search(result.stderr), result.stderr[-1500:]
    assert not re.search(r"(?i)\blocally\b", out), out[-1500:]
    # THE MIRROR ANSWERED: the store is unreachable, and `lanes` is mirror.
    primary.door.unreachable()
    mirror = primary.script("lanes")
    assert MIRROR_LINE.search(mirror.stderr), (mirror.returncode, mirror.stderr[-1500:])
    assert re.search(FOOTER_HEAD + re.escape(MIRROR_FOOTER) + "$", mirror.stdout, re.M), (
        mirror.returncode, mirror.stdout[-1500:])
    assert "register at seq" not in mirror.stdout + mirror.stderr, mirror.stdout[-1500:]
    # AND THE FETCH DID NOT ANSWER: origin is gone, under `--fetch`.
    origin = primary.e.origin
    origin.rename(origin.with_name("origin-aside.git"))
    fell = primary.script("lanes", "--fetch")
    lines = fell.stdout.splitlines()
    at = [i for i, line in enumerate(lines)
          if re.fullmatch(FOOTER_HEAD + re.escape(MIRROR_FOOTER) + "$", line)]
    assert at, ("no mirror footer under --fetch", fell.returncode, fell.stdout[-1500:],
                fell.stderr[-1500:])
    assert lines[at[0] + 1:at[0] + 2] == [FELL_BACK_LINE], (fell.stdout[-1500:], fell.stderr[-1500:])
    assert any(line.startswith("  ") and "reading the logs as they stand locally" in line
               for line in lines[at[0] + 2:]), ("the helper's words are not under it",
                                                fell.stdout[-1500:])


def test_lanes_fetch_on_primary_prints_no_no_fetch_note(primary):
    """T509: on primary the `lanes` arm makes no fetch, so `--fetch` prints
    no "NO FETCH WAS MADE" note, where files mode, its origin gone, does (the
    control)."""
    origin = primary.e.origin
    origin.rename(origin.with_name("origin-aside.git"))
    files = primary.files_edit("lanes", "--fetch")
    assert "NO FETCH WAS MADE" in files.stderr, ("the control", files.stderr[-1500:])
    result = primary.edit("lanes", "--fetch")
    assert primary.door.register_calls(), ("the listing never reached the store", result.stderr)
    assert "NO FETCH WAS MADE" not in result.stdout + result.stderr, result.stderr[-1500:]


MIRROR_ROW = re.compile(r"^\s*([A-Za-z0-9_|-]+)\)[^\n]*\bREG_MIRROR_VAR=1\b", re.M)


def test_the_read_mirror_variable_lowers_each_read_that_names_the_lane_on_primary(primary):
    """T504 (R-L4Q1; the reads are T275's list): `LANES_READ_MIRROR=1`
    lowers each read whose row in the class table sets `REG_MIRROR_VAR=1`,
    `window-lane` and `swapped` among them, to a mirror read on primary: with
    the store unreachable each prints the `read: mirror` line and exits as
    files mode does. ERR-30, as lane 3 widened it on round 6h's #56 (#165
    6859801732), marks `lane-last` and `restart-intent` too, the two reads
    `lane-handoff` makes before its handoff file. Every other arm ignores the
    variable, `who` among them (tasks:741 at f4591a08): `who`, a decide read
    whose row sets no `REG_MIRROR_VAR`, still refuses 69 (T217m; lane 5's
    triage, #165 6782743644: `register-row`, the arm here before T217m, is
    one of the table's; and since T504 so is `lane-last`, the arm here
    before T217zk, lane 5's #165 6860020483).

    Fails until lane 5's T504 `3f838677`, at the marked pair's assert. That
    assert is the last, so a tree without T504 fails there and only there.
    T504's verify selects this case (lane 3, #165 6860626333, item 1)."""
    table = CLASS_FUNCTION.search(LANES_EDIT.read_text(encoding="utf-8"))
    assert table, "lanes-edit.sh has no read door class table (reg_class_of)"
    marked = {arm for row in MIRROR_ROW.findall(table.group(1)) for arm in row.split("|")}
    assert {"window-lane", "swapped"} <= marked, marked
    assert "who" not in marked, marked
    primary.door.unreachable()
    for argv in (("window-lane", "Eagle", "@1"), ("swapped",)):
        files = primary.files_edit(*argv)
        result = primary.edit(*argv, env={"LANES_READ_MIRROR": "1"})
        assert MIRROR_LINE.search(result.stderr), (argv, result.stderr[-1500:])
        assert result.returncode == files.returncode, (argv, result.returncode, files.returncode)
    other = primary.edit("who", "opensoft/repoA#7", env={"LANES_READ_MIRROR": "1"})
    assert other.returncode == 69, (other.returncode, other.stderr[-1500:])
    assert not MIRROR_LINE.search(other.stderr), other.stderr[-1500:]
    # T504's two marks (ERR-30, widened). Fails until lane 5's T504 3f838677.
    assert {"lane-last", "restart-intent"} <= marked, marked


# --------------------------------------------- T502's `lanes --decide` test
#: Lane 5's seed (refs/l5/T502), kept: each row's age column is masked, the
#: one value that moves between two reads.
COLUMNS = 17
AGE_COLUMN = 8
AGE_SHAPE = re.compile(r"[0-9]+h [0-9]{2}m|age unknown")
LISTINGS = [(), ("--all",), ("--closed",), ("--lane", "repoA-1")]
REFUSED = [("--no-such-flag",), ("--decided",), ("--decide", "--no-such-flag")]


def _masked(stdout: str) -> str:
    out = []
    for line in stdout.splitlines(keepends=True):
        body = line.rstrip("\n")
        fields = body.split("\t")
        assert len(fields) == COLUMNS, (len(fields), line)
        assert AGE_SHAPE.fullmatch(fields[AGE_COLUMN]), (fields[AGE_COLUMN], line)
        fields[AGE_COLUMN] = "<AGE>"
        out.append("\t".join(fields) + line[len(body):])
    return "".join(out)


def test_lanes_accepts_decide_and_reads_as_without_it(estate, primary):
    """`lanes --decide` IS `lanes` UNTIL T509 (T502, R38 as lane 3 amended
    it; lane 5's seed, kept by name): in files mode and on primary the arm
    takes the flag and answers as if it were not there, the same exit,
    stdout byte for byte with the age column masked, and the same stderr. Its
    unknown-argument `die` still meets every other argument, before
    `--decide` or after it, with 64. Files mode is `Primary.files_edit`:
    the door's `mode=primary` file is in the estate's own configuration
    folder, so `estate.edit` would run primary there (AN13a's B1)."""
    for where, edit in (("files", primary.files_edit), ("primary", primary.edit)):
        bare = edit("lanes")
        assert bare.returncode == 0 and bare.stdout, (where, bare.returncode, bare.stderr)
        closed = edit("lanes", "--closed")
        assert closed.returncode == 0, (where, closed.returncode, closed.stderr)
        assert _masked(closed.stdout) != _masked(bare.stdout), (where, closed.stdout)
        for listing in LISTINGS:
            without = edit("lanes", *listing)
            assert without.returncode == 0 and without.stdout, \
                (where, listing, without.returncode, without.stderr)
            for argv in dict.fromkeys([(*listing, "--decide"), ("--decide", *listing)]):
                with_it = edit("lanes", *argv)
                assert with_it.returncode == without.returncode, \
                    (where, argv, with_it.returncode, with_it.stdout, with_it.stderr)
                assert _masked(with_it.stdout) == _masked(without.stdout), \
                    (where, argv, with_it.stdout, without.stdout)
                assert with_it.stderr == without.stderr, (where, argv, with_it.stderr, without.stderr)
        for argv in REFUSED:
            refused = edit("lanes", *argv)
            assert refused.returncode == 64, (where, argv, refused.returncode, refused.stderr)
            assert refused.stdout == "", (where, argv, refused.stdout)
            assert f"unknown argument '{argv[-1]}' for lanes" in refused.stderr, \
                (where, argv, refused.stderr)


# ------------------------------- T235: T505's three read sites (F13b, proposed)
#: THE FAKE `git`'S ARGV LOG (T235): a `git` in front of the real one that
#: appends each call's argv, its words joined by US, one call a line, to
#: `$T235_GIT_LOG`, then runs the real one at `$T235_REAL_GIT`.
LOGGING_GIT = r'''#!/usr/bin/env bash
# THE LOGGING GIT (T235): log this call's argv in one write, then run the real git.
t235_line="$(printf '%s\037' "$@")"
printf '%s\n' "$t235_line" >> "$T235_GIT_LOG"
exec "$T235_REAL_GIT" "$@"
'''

#: The log directory `known_lanes`, `remote_log_events` and `worktree_rows`'
#: pin read by git off primary (P2's `lanes-edit.sh`, `LANES_LOG_PREFIX`).
LOG_DIR = "lanes/log"
#: The archive `archive_text` reads by git off primary (`LANES_ARCH_PATH`):
#: `register_published`'s `ls-tree`, then a `show` where it is published. On
#: primary it reads `.archive` (T505 Q6); `lanes_rows` and `worktree_rows`
#: read it on every listing (lane 5's NIT, #165 6888923188).
ARCH_PATH = "lanes/archive/LANES-retired.md"

#: T235's ids (F13c's block, T235): four the text writes whole, and three run
#: through the module's door (`DOOR_WRAPPER`), whose oracles are lane 3's
#: batch 7 (#165 6780364102), by batch 5's answers 3 and 4 (6778890211). No
#: id holds the word `worktrees`, which lane 4's T404 word
#: `sql_register_readers and worktrees` (B12b tasks:886) would otherwise
#: select.
T235_CASES = ["known-lanes", "remote-log-events-lanes", "remote-log-events-history",
              "worktree-rows", "case-pair", "out-of-class", "failed-second-read"]
T235_LATER = ("case-pair", "out-of-class", "failed-second-read")

#: Lines only the store's logs hold (T235): a `dir` for repoA-2, and a note.
T235_DIR = "/work/t235-only-in-the-store"
T235_NOTE = "T235: a note only the store holds"
#: `[worktree-rows]`' sidecar's schema, one no reader knows: `worktree_rows`'
#: unknown-schema arm lists its tree as `unknown schema <it>`, by its path.
T235_TREE_SCHEMA = "t235-a-schema-no-reader-knows"

#: `[case-pair]`'s two logs (C11; CLI:674), which differ only by case.
T235_PAIR = ("lanes/log/repoP-1.md", "lanes/log/RepoP-1.md")
#: `[out-of-class]`'s log (O18; CLI:670-672, :729), a stem outside the class,
#: and its own event, a well-formed line naming a lane (batch 7); its lane is
#: the file's, `a,b` (Amendment 16(e)).
T235_OUT_KEY = "a,b"
T235_OUT_LOG = f"lanes/log/{T235_OUT_KEY}.md"
T235_OUT_NOTE = "T235: an event only the log outside the class holds"
T235_OUT_LINE = (f"NOTED — lane repoO-1, session {STORE_ONLY_UUID}@Eagle, "
                 f"2026-10-06T00:00:01Z, lane:repoO-1 — {T235_OUT_NOTE}\n")
#: `lanes`' fence for the logs a read could not read (`lanes_rows`), and the
#: two reads each door form makes.
T235_FENCE = "these published logs could not be read, so no lane of theirs is classed DORMANT:"
T235_RUNS = (("lanes", "--all", "--closed"), ("history", "--all"))
#: `cleanup`'s note of a failed second read at exit (`reg_fail`'s first line,
#: by `note`): a mirror arm has said its failure in its mirror line, and must
#: not say it again here (lane 3's review of T505, SHOULD-1, #165 6783977065).
T235_READ_FAILED = re.compile(r"^lanes-edit: the register could not be read", re.M)


def git_log_reads(log: Path, upto: re.Pattern | None = None) -> list:
    """The calls in the fake `git`'s argv log that read `lanes/log` or the
    archive by git: an `ls-tree` naming either, or a `show` of a path under
    `lanes/log` or of the archive. Each call's line holds US. Where the log
    is also the run's stderr (`[failed-second-read]`), every other line is
    stderr's, and `upto`, where given, ends the scan at the first of those it
    matches."""
    if not log.exists():
        return []
    found = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if "\037" not in line:
            if upto is not None and upto.search(line):
                break
            continue
        argv = line.split("\037")
        if argv and argv[-1] == "":
            argv = argv[:-1]
        rest, i = [], 0
        while i < len(argv):
            if argv[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
                i += 2
                continue
            if argv[i].startswith("-"):
                i += 1
                continue
            rest = argv[i:]
            break
        if not rest:
            continue
        verb, args = rest[0], rest[1:]
        if verb == "ls-tree" and any(read in a for a in args for read in (LOG_DIR, ARCH_PATH)):
            found.append(argv)
        elif verb == "show" and any(a.startswith(read) or f":{read}" in a
                                    for a in args for read in (LOG_DIR, ARCH_PATH)):
            found.append(argv)
    return found


def _rows(stdout: str) -> dict:
    """A listing's rows by their first column, the lane."""
    return {line.split("\t", 1)[0]: line for line in stdout.splitlines() if line}


def asked_logs(argv: list) -> list:
    """How one `register read` call asks for logs (CLI:670-672, :729): `("=",
    <key>)` for each `--log-key=<key>`, `(" ", <key>)` for a `--log-key <key>`,
    and `("files", <list>)` for each `--files` list, whole, since a key that
    holds `,` would be split across its items."""
    found = []
    for i, arg in enumerate(argv):
        after = argv[i + 1] if i + 1 < len(argv) else ""
        if arg.startswith("--log-key="):
            found.append(("=", arg[len("--log-key="):]))
        elif arg == "--log-key":
            found.append((" ", after))
        elif arg.startswith("--files="):
            found.append(("files", arg[len("--files="):]))
        elif arg == "--files":
            found.append(("files", after))
    return found


def files_names_log(value: str, key: str) -> bool:
    """Whether a `--files` list names `key`'s log, `log:<key>`, in any case."""
    return re.search(rf"(?:^|,)log:{re.escape(key)}(?:,|$)", value, re.I) is not None


def unreadable_notes(stderr: str, path: str) -> int:
    """How many `unreadable log: <path> — ` notes stderr holds, as `note`
    prints them, `lanes-edit: ` first, the form `lanes_rows`' and
    `worktree_rows`' `sed` patterns read back."""
    return len(re.findall(rf"(?m)^lanes-edit: unreadable log: {re.escape(path)} — ", stderr))


@pytest.mark.parametrize("case", T235_CASES)
def test_on_primary_known_lanes_remote_log_events_and_worktree_rows_read_the_store_and_never_git(
        pg, estate, tmp_path, case):
    """T235 (lane 5's T505 plan, #165 6774988528, question 12; lane 5's
    choice (b), 6778955065; placed in B14, 6779844884; FR-033, FR-034): on
    primary, `known_lanes`, `remote_log_events` and `worktree_rows` read the
    store and never git. Each id asserts the store's answer, and that no `git
    ls-tree` and no `git show` of `lanes/log` ran, by the fake `git`'s argv
    log (`LOGGING_GIT`), nor of the archive, which `archive_text` reads from
    `.archive` on primary for `lanes_rows` and `worktree_rows` (T505 Q6; lane
    5's NIT, #165 6888923188):

      * `[known-lanes]`: a lane's log with no register row, only in the store,
        which `known_lanes` lists from the family (`lanes --all --closed`);
      * `[remote-log-events-lanes]` and `[remote-log-events-history]`: events
        only the store holds, which `remote_log_events` returns through
        `lanes` without `--lane`, and through `history --all`;
      * `[worktree-rows]`: the `worktrees` arm on primary, through
        `worktree_rows` and its log-set pin (P2's `lanes-edit.sh:17222`): a
        tree under a `dir` only the store's log names.

    The three door forms run through the module's door in front of the
    flipped copy, which logs every register call, and their oracles are lane
    3's batch 7 (#165 6780364102), by batch 5's answers 3 and 4 (6778890211):

      * `[case-pair]`, the store holding `lanes/log/repoP-1.md` and
        `lanes/log/RepoP-1.md` (C11; CLI:674): `lanes --all --closed` and
        `history --all` exit 0, never 69; no form 3 names either log, as
        `log:<key>` in `--files` or as `--log-key=`, by the door's call log
        with failures off; stderr carries one `unreadable log: <path> — `
        note per path, its reason words T505's, which both `sed` patterns
        must accept; `lanes` prints its fence naming both paths; the other
        lanes' rows are the store's answer; and no git read;
      * `[out-of-class]`, `lanes/log/a,b.md` (O18; CLI:670-672, :729): every
        form 3 that asks for it carries `--log-key=a,b`, in the `=` form,
        and none puts it inside `--files`; its own event is in `history
        --all`; exit 0, no `unreadable log:` note for it, and no git read;
      * `[failed-second-read]`, every form 3 failing 69, with `a,b.md` in
        `.paths`: `lanes` and `history` print `read: mirror at <sha12>` on
        stderr and then the mirror's answer, files mode's (its exit, and its
        stdout, `lanes`' age column masked), never the store's answer with
        `a,b`'s lines silently missing. The no-git check holds only up to
        that label, since the mirror read is a git read: the fake `git`'s
        log and the run's stderr are one file, appended in the order written.
        The failure is said once: one mirror line, and no note at exit that
        "the register could not be read" beyond any files mode's own run
        prints (lane 3's review of T505, SHOULD-1, #165 6783977065).

    The register is the estate's, brought to primary on the `pg` fixture's
    database by AT-LR006's route (`RealRegister`), with the store-only files
    in its import; the run is the checkout's `lanes-edit.sh` copied beside
    the flipped copy, as `managed-projection`'s RE case runs. FAILS UNTIL
    lane 5's T505, and, with the module's other real-register cases, until
    lane 2's T227 and T228. Real engine: it skips without one (T205)."""
    files = render_set(estate.wip)
    a2 = files["lanes/log/repoA-2.md"].decode("utf-8")
    a2_dir = (f"STARTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-06T00:00:00Z, "
              f"lane:repoA-2 → home opensoft/repoA; dir {T235_DIR}; profile team-01b\n")
    a2_note = (f"NOTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-06T00:00:00Z, "
               f"lane:repoA-2 — {T235_NOTE}\n")
    trees = tmp_path / "t235-roots"
    if case == "known-lanes":
        files[f"lanes/log/{STORE_ONLY_LANE}.md"] = STORE_ONLY_LOG.encode()
    elif case == "remote-log-events-lanes":
        files["lanes/log/repoA-2.md"] = (a2 + a2_dir).encode()
    elif case == "remote-log-events-history":
        files["lanes/log/repoA-2.md"] = (a2 + a2_note).encode()
    elif case == "worktree-rows":
        # `lane_control_root`: a `dir` whose parent is there gives `<parent>/.lane-state/<lane>`,
        # and a sidecar of a schema no reader knows is listed by its path, never parsed: its
        # `tree:` claim stands in only where it names no path (`worktree_rows`' unknown-schema
        # arm, `[ -n "${t_p:-}" ] || t_p="$t_id"`), so this one's id is never printed.
        sidecar = trees / ".lane-state" / STORE_ONLY_LANE / "trees" / "t235.yaml"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text(f"schema: {T235_TREE_SCHEMA}\ntree: t235-store-tree\n"
                           f"path: {trees / 'tree'}\n", encoding="utf-8")
        files[f"lanes/log/{STORE_ONLY_LANE}.md"] = (
            f"STARTED — lane {STORE_ONLY_LANE}, session {STORE_ONLY_UUID}@Eagle, "
            f"2026-10-05T00:00:00Z, lane:{STORE_ONLY_LANE} → home opensoft/repoS; "
            f"dir {trees / 'repoS-1'}\n").encode()
    elif case == "case-pair":
        files["lanes/log/repoA-2.md"] = (a2 + a2_dir + a2_note).encode()
        files[T235_PAIR[0]] = ("STARTED — lane repoP-1, session "
                               f"{STORE_ONLY_UUID}@Eagle, 2026-10-05T00:00:00Z, "
                               "lane:repoP-1 → home opensoft/repoP\n").encode()
        files[T235_PAIR[1]] = "NOTED — the case pair's other half\n".encode()
    elif case == "out-of-class":
        files[T235_OUT_LOG] = T235_OUT_LINE.encode()
    else:                                                    # failed-second-read
        files["lanes/log/repoA-2.md"] = (a2 + a2_dir + a2_note).encode()
        files[T235_OUT_LOG] = T235_OUT_LINE.encode()
    reg = RealRegister(pg, tmp_path / "real", files)
    edit = reg.tools()
    door = None
    if case in T235_LATER:
        # The module's door in front of a flipped copy, which logs every register call ("count
        # this from the door's call log, with failures off"); for [failed-second-read] every
        # second read (form 3) fails 69.
        door = tmp_path / "real" / "door"
        helpers.flipped_copy(helpers.LANES_INDEX, door / "store", True)
        _write(door / "lanes-index", DOOR_WRAPPER)
        for name in RealRegister.TOOLS:
            shutil.copy2(REPO / name, door / name)
        if case == "failed-second-read":
            (door / "lanes-index.fail").write_text(json.dumps(
                {"all": True, "forms": [3], "exit": UNREACHABLE_EXIT, "stdout": "mode primary\n",
                 "stderr": UNREACHABLE_STDERR}), encoding="utf-8")
        edit = door / "lanes-edit.sh"
    shim = tmp_path / "t235-git"
    real_git = shutil.which("git")
    _write(shim / "git", LOGGING_GIT)

    def git_env(log: Path) -> dict:
        return {"LANES_EDIT": str(edit), "LANES_INDEX_CONFIG": str(reg.config), "LANES_INDEX": None,
                "PATH": str(shim) + os.pathsep + estate.env["PATH"],
                "T235_GIT_LOG": str(log), "T235_REAL_GIT": real_git}

    # THE CONTROL: the fake `git` is the one on PATH, and its log shows the reads the sites
    # make off primary, of `lanes/log` and of the archive, so a run that logs none made none
    # (a T505 run may log no call at all).
    control = tmp_path / "t235-git-control.log"
    for count, path in enumerate((f"{LOG_DIR}/", ARCH_PATH), 1):
        listed = estate.run("git", "-C", estate.wip, "ls-tree", "--name-only", "origin/main", "--",
                            path, env=git_env(control))
        assert listed.returncode == 0 and len(git_log_reads(control)) == count, (
            "the control: the fake git logged no ls-tree of", path, listed.stderr)

    def run(*argv: str) -> subprocess.CompletedProcess:
        log = tmp_path / f"t235-git-{'-'.join(argv)}.log"
        result = estate.run("bash", edit, *argv, env=git_env(log))
        assert not git_log_reads(log), (case, argv, "git read lanes/log or the archive",
                                        git_log_reads(log), result.stderr[-1500:])
        return result

    def run_in_order(*argv: str) -> tuple:
        """The run with the fake `git`'s log and its stderr in ONE file, each
        line appended as it is written, so that a git call can be placed
        before or after a line of stderr: the result, stderr, and the file."""
        both = tmp_path / f"t235-order-{'-'.join(argv)}.log"
        child = dict(estate.env)
        for key, value in git_env(both).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        with open(both, "ab") as err:                        # O_APPEND, as the shim's `>>`
            result = subprocess.run(["bash", str(edit), *argv], stdout=subprocess.PIPE,
                                    stderr=err, text=True, env=child, cwd=str(estate.root),
                                    timeout=120, stdin=subprocess.DEVNULL, check=False)
        lines = both.read_text(encoding="utf-8", errors="replace").splitlines()
        return result, "\n".join(line for line in lines if "\037" not in line), both

    if case == "known-lanes":
        result = run("lanes", "--all", "--closed")
        assert result.returncode == 0, (case, result.returncode, result.stderr[-1500:])
        rows = _rows(result.stdout)
        assert "repoB-1" in rows, (case, "the control: a log with no row in both stores",
                                   result.stdout)
        assert STORE_ONLY_LANE in rows, (case, "not the store's answer", result.stdout)
    elif case == "remote-log-events-lanes":
        result = run("lanes", "--all", "--closed")
        assert result.returncode == 0, (case, result.returncode, result.stderr[-1500:])
        rows = _rows(result.stdout)
        assert "repoA-2" in rows, (case, result.stdout)
        assert T235_DIR in rows["repoA-2"], (case, "not the store's answer", rows["repoA-2"])
    elif case == "remote-log-events-history":
        result = run("history", "--all")
        assert result.returncode == 0, (case, result.returncode, result.stderr[-1500:])
        assert T235_NOTE in result.stdout, (case, "not the store's answer", result.stdout)
    elif case == "worktree-rows":
        result = run("worktrees")
        assert result.returncode == 0, (case, result.returncode, result.stdout,
                                        result.stderr[-1500:])
        # The store's answer (batch 5's answer 5: the pin reads `.paths`): a TREE row for the
        # lane only the store's log names, carrying the sidecar's path and the unknown-schema
        # arm's branch. The row's columns are `worktree_rows`': TREE, the workstation, the lane,
        # the owner, the path, the branch, ...; the sidecar's `tree:` id is not among them,
        # since its path is set (lane 5's T505 sample, #165 6783860030).
        rows = [line.split("\037") for line in result.stdout.splitlines()
                if line.startswith("TREE\037")]
        assert any(len(row) > 5 and row[2] == STORE_ONLY_LANE and row[4] == str(trees / "tree")
                   and row[5] == f"unknown schema {T235_TREE_SCHEMA}" for row in rows), (
            case, "not the store's answer: no row of the store-only lane's tree", result.stdout)
    elif case == "case-pair":
        for argv in T235_RUNS:
            result = run(*argv)
            assert result.returncode == 0, (case, argv, "exit 0, never 69", result.returncode,
                                            result.stderr[-1500:])
            for path in T235_PAIR:
                assert unreadable_notes(result.stderr, path) == 1, (
                    case, argv, path, "one `unreadable log:` note per path", result.stderr[-1500:])
            if argv[0] == "lanes":
                fence = [line.split(T235_FENCE, 1)[1].split()
                         for line in result.stderr.splitlines() if T235_FENCE in line]
                assert fence and all(path in fence[0] for path in T235_PAIR), (
                    case, "lanes fences both logs", fence, result.stderr[-1500:])
                rows = _rows(result.stdout)
                assert T235_DIR in rows.get("repoA-2", ""), (
                    case, "the other lanes' rows are not the store's answer", result.stdout)
            else:
                assert T235_NOTE in result.stdout, (case, "not the store's answer", result.stdout)
        for argv in (c["argv"] for c in door_second_reads(door)):
            for how, value in asked_logs(argv):
                named = (files_names_log(value, "repoP-1") if how == "files"
                         else value.lower() == "repop-1")
                assert not named, (case, "a form 3 asked for a log of the case pair", argv)
    elif case == "out-of-class":
        for argv in T235_RUNS:
            result = run(*argv)
            assert result.returncode == 0, (case, argv, result.returncode, result.stderr[-1500:])
            assert unreadable_notes(result.stderr, T235_OUT_LOG) == 0, (
                case, argv, "an `unreadable log:` note for it", result.stderr[-1500:])
            if argv[0] == "history":
                assert T235_OUT_NOTE in result.stdout, (
                    case, "its event is not in history --all", result.stdout)
        seconds = [c["argv"] for c in door_second_reads(door)]
        assert any(("=", T235_OUT_KEY) in asked_logs(argv) for argv in seconds), (
            case, "no form 3 asked for it as --log-key=a,b", seconds)
        for argv in seconds:
            for how, value in asked_logs(argv):
                assert not (how == "files" and files_names_log(value, T235_OUT_KEY)), (
                    case, "asked for inside --files", argv)
                assert not (how == " " and value == T235_OUT_KEY), (
                    case, "asked for, but not in the `=` form", argv)
    else:                                                    # failed-second-read
        for argv in T235_RUNS:
            mirror = estate.edit(*argv)                      # the mirror's answer: files mode's
            result, stderr, both = run_in_order(*argv)
            reads = git_log_reads(both, upto=MIRROR_LINE)
            assert not reads, (case, argv, "git read lanes/log or the archive before the mirror's "
                               "label", reads, stderr[-1500:])
            assert MIRROR_LINE.search(stderr), (case, argv, "no `read: mirror at` line",
                                                stderr[-1500:])
            # SAID ONCE (lane 3's review of T505, SHOULD-1, #165 6783977065): the mirror line
            # once, and no second report at exit, `cleanup`'s "the register could not be read".
            assert len(MIRROR_LINE.findall(stderr)) == 1, (
                case, argv, "the mirror line, once", MIRROR_LINE.findall(stderr), stderr[-1500:])
            assert (len(T235_READ_FAILED.findall(stderr))
                    == len(T235_READ_FAILED.findall(mirror.stderr))), (
                case, argv, "the failed read said twice: a second note at exit",
                T235_READ_FAILED.findall(stderr), stderr[-1500:])
            assert not MIRROR_LINE.search(result.stdout), (case, argv, result.stdout)
            assert result.returncode == mirror.returncode, (
                case, argv, result.returncode, mirror.returncode, stderr[-1500:])
            for only in (T235_DIR, T235_NOTE, T235_OUT_NOTE):
                assert only not in result.stdout, (
                    case, argv, "the store's answer, not the mirror's", only, result.stdout)
            if argv[0] == "lanes":
                assert _masked(result.stdout) == _masked(mirror.stdout), (
                    case, argv, result.stdout, mirror.stdout)
            else:
                assert result.stdout == mirror.stdout, (case, argv, result.stdout, mirror.stdout)
        assert door_second_reads(door), (case, "no second read was made, so none failed")


def door_second_reads(door: Path) -> list:
    """The form-3 calls the door in `door` was asked (`DOOR_WRAPPER`'s log)."""
    path = door / "lanes-index.calls"
    if not path.exists():
        return []
    calls = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [c for c in calls if c.get("form") == 3]


#: T235'S MOVED HEAD (T505's two reruns; lane 5's proposal, #165 6860943489,
#: which lane 3 agreed, 6861148117). Each id seeds `[out-of-class]`'s log,
#: `lanes/log/a,b.md`, outside `check_lane_name`'s class, as T217zh's
#: one-snapshot case seeds its own: `--all` never fetches it, so every run of
#: `reg_remote_log_events` reads it by form 3's `--log-key=a,b` (O18), and the
#: door's `move_each` moves the store's head one seq at each of the first `t`
#: of those reads, before the store answers. That read is the one both sites
#: take their head pair around: `reg_remote_log_events` after its
#: out-of-class reads, and `worktree_rows` after `lanes_rows`, whose events
#: come from the same reads. `T235_EVERY` is more moves than three runs make:
#: every read moves the head.
T235_EVERY = 99
#: WHAT A MOVE WRITES. Through `remote_log_events`, a NOTED line on
#: `repoA-2`'s log, which the prefetch cached, so form 3 finds a cached member
#: changed in `(n, n']` and rewrites the family at `n'`. Through
#: `worktree_rows`, `repoN-1`'s log, absent at `n`, whose `dir` places a tree,
#: so only a log list pinned again at `n'` names that lane and its tree.
T235_MOVED_PATH = "lanes/log/repoA-2.md"
T235_MOVED_WORDS = "T235: a write that moved the head under the read, move %d"
T235_MOVED_LINE = (f"NOTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-06T01:00:00Z, "
                   f"lane:repoA-2 — {T235_MOVED_WORDS}\n")
T235_NEW_LANE = "repoN-1"
T235_NEW_LOG = f"lanes/log/{T235_NEW_LANE}.md"
T235_NEW_UUID = "aaaaaaaa-0013-4000-8000-00000000a013"
#: Each id: the verb's argv, and how many reads move the head. No id holds the
#: word `worktrees` (lane 4's T404 word, B12b tasks:886, as T235's ids).
T235_MOVED = {
    "history-one-move": (("history", "--all"), 1),
    "history-every-move": (("history", "--all"), T235_EVERY),
    "decide-every-move": (("lanes", "--decide", "--all"), T235_EVERY),
    "worktree-rows-one-move": (("worktrees",), 1),
    "worktree-rows-every-move": (("worktrees",), T235_EVERY),
    "worktree-rows-notes-once": (("worktrees",), 1),
}


@pytest.mark.parametrize("case", list(T235_MOVED))
def test_on_primary_remote_log_events_and_worktree_rows_read_again_when_the_head_moves(
        estate, case):
    """T235's moved-head ids, T505's two reruns (lane 5's proposal, #165
    6860943489; lane 3's agreement, 6861148117; T505's verify is tasks:746 at
    f4591a08). On primary `reg_remote_log_events` takes the head pair after
    its list read and again after its last read, and `worktree_rows` after its
    pins and again after `lanes_rows`; where either moved, the run is dropped
    and made again, three runs at most, then the class's failed read (lane 3,
    #165 6851977580, Q2; round 2b, 6859073786). The door moves the head at
    each of the first t reads of `--log-key=a,b` (`move_each`), and each id
    counts those reads in the door's call log:

      * `[history-one-move]`: `history --all`, a mirror verb, one move: exit
        0 with the events at n + 1, byte for byte what the same read answers
        at n + 1 with no move, the moved line once and nothing of the dropped
        run; `a,b` is read twice, and the head is at n + 1;
      * `[history-every-move]`: every read moves the head, so the class's
        failed read, then the mirror: one `read: mirror at …` line on stderr,
        and files mode's exit and stdout, with nothing of the store's before
        it; three reads, never a fourth;
      * `[decide-every-move]`: the same through a decide verb, `lanes
        --decide --all`: 69 with nothing on stdout and no mirror line; three
        reads;
      * `[worktree-rows-one-move]`: `worktrees` on primary (decide), one move,
        which writes `repoN-1`'s log, absent at n, whose `dir` places a tree:
        exit 0 with the listing at n + 1, byte for byte the same read's with
        no move, `repoN-1`'s tree in it, so the log list was pinned again;
        two reads. No move changes the archive, so its own re-pin is not seen
        here beyond that byte equality;
      * `[worktree-rows-every-move]`: 69 with nothing on stdout and no mirror
        line; three reads;
      * `[worktree-rows-notes-once]`: `[worktree-rows-one-move]` with T235's
        case pair in the register, so the listing notes each of its two logs
        as unreadable and fences them (`lanes_rows`): each note is printed as
        often as the same read prints it at n + 1 with no move, and never
        again for the dropped run. Its last assert, the notes', FAILS UNTIL
        lane 5's T505 round 2b B (`l5-for-l3-007-T505-round2b-B-on-R79-
        5c416d1d3f0d`), which holds a listing's notes aside and drops them with
        a dropped run; before it, each run of `lanes_rows` says them again.

    The stub door, not `RealRegister`: `move_each` moves the contract stub's
    head, so these ids need no engine. Every id but the notes one passes from
    rounds 2 and 2b's A, in line R since merge89 (T235e)."""
    argv, moves = T235_MOVED[case]
    logs = {T235_OUT_LOG: T235_OUT_LINE}
    if case == "worktree-rows-notes-once":
        logs[T235_PAIR[0]] = (f"STARTED — lane repoP-1, session {STORE_ONLY_UUID}@Eagle, "
                              "2026-10-05T00:00:00Z, lane:repoP-1 → home opensoft/repoP\n")
        logs[T235_PAIR[1]] = "NOTED — the case pair's other half\n"
    seed_logs(estate, logs)
    path, line, roots = T235_MOVED_PATH, T235_MOVED_LINE, estate.root / "t235-moved-roots"
    if argv[0] == "worktrees":
        sidecar = roots / ".lane-state" / T235_NEW_LANE / "trees" / "t235.yaml"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text(f"schema: {T235_TREE_SCHEMA}\ntree: t235-moved-tree\n"
                           f"path: {roots / 'tree'}\n", encoding="utf-8")
        path = T235_NEW_LOG
        line = (f"STARTED — lane {T235_NEW_LANE}, session {T235_NEW_UUID}@Eagle, "
                f"2026-10-06T02:0%d:00Z, lane:{T235_NEW_LANE} → home opensoft/repoN; "
                f"dir {str(roots / T235_NEW_LANE).replace('%', '%%')}\n")
    primary = Primary(estate)
    files = primary.files_edit(*argv) if case == "history-every-move" else None
    first = primary.door.head()[0]
    primary.door.fail(move_each={"key": T235_OUT_KEY, "times": moves, "path": path,
                                 "line": line})
    result = primary.edit(*argv)
    reads = [call for call in primary.door.calls()
             if call["form"] == 3 and f"--log-key={T235_OUT_KEY}" in call["argv"]]
    head = primary.door.head()[0]
    where = (case, "exit", result.returncode, "head", first, "->", head, "reads of",
             T235_OUT_KEY, len(reads), result.stdout[-1500:], result.stderr[-1500:])
    if moves == T235_EVERY:
        assert (len(reads), head) == (3, first + 3), where
        if files is not None:
            assert files.returncode == 0 and T235_OUT_NOTE in files.stdout, (
                "the control: files mode's history --all lacks the out-of-class event",
                files.returncode, files.stdout[-1500:], files.stderr[-1500:])
            assert len(MIRROR_LINE.findall(result.stderr)) == 1, where
            assert not MIRROR_LINE.search(result.stdout), where
            assert (result.returncode, result.stdout) == (files.returncode, files.stdout), (
                where + ("files mode's:", files.stdout[-1500:]))
        else:
            assert (result.returncode, result.stdout) == (69, ""), where
            assert not MIRROR_LINE.search(result.stderr), where
        return
    assert (len(reads), head) == (2, first + 1), where
    primary.door.reachable()                     # no move: the same read at n + 1
    again = primary.edit(*argv)
    assert again.returncode == 0 and primary.door.head()[0] == first + 1, (
        "the oracle: the same read at n + 1", again.returncode, again.stderr[-1500:])
    assert (result.returncode, result.stdout) == (0, again.stdout), (
        where + ("at n + 1, with no move:", again.stdout[-1500:]))
    assert not MIRROR_LINE.search(result.stderr), where
    if argv[0] == "history":
        assert result.stdout.count(T235_MOVED_WORDS % 1) == 1, where
        assert T235_OUT_NOTE in result.stdout, where
    else:
        rows = [row.split("\037") for row in result.stdout.splitlines()
                if row.startswith("TREE\037")]
        assert any(len(row) > 5 and row[2] == T235_NEW_LANE and row[4] == str(roots / "tree")
                   and row[5] == f"unknown schema {T235_TREE_SCHEMA}" for row in rows), (
            where + ("no tree of the lane only the log list at n + 1 names",))
    if case == "worktree-rows-notes-once":
        # THE HELD NOTES, PRINTED ONCE (round 2b's B): fails until B's merge.
        said = {p: unreadable_notes(result.stderr, p) for p in T235_PAIR}
        said["fence"] = result.stderr.count(T235_FENCE)
        once = {p: unreadable_notes(again.stderr, p) for p in T235_PAIR}
        once["fence"] = again.stderr.count(T235_FENCE)
        assert all(count >= 1 for count in once.values()), (
            "the control: the read at n + 1 does not note the case pair", once,
            again.stderr[-1500:])
        assert said == once, where + ("each note as often as at n + 1:", once, "said:", said)


# ------------------------------------------------- lane 4's two read verbs
#: The set both verbs answer (O21 (a)): the render set without the archive.
VERB_PATHS = ("lanes/LANES.md", "lanes/aliases.tsv", "lanes/log/repoA-2.md")
OUTSIDE_PATHS = {"other-path": "lanes/repos.tsv", "log-readme": "lanes/log/README.md"}
LOG_PATHSPEC = (":(glob)lanes/log/*.md", ":(exclude)lanes/log/README.md")


def index_env(estate: Estate) -> dict:
    """`mode=index`, by its own configuration file beside the estate's."""
    path = estate.config / "openRepoTools" / "lanes-index-index-mode.conf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("mode=index\n", encoding="utf-8")
    path.chmod(0o600)
    return {"LANES_INDEX_CONFIG": str(path)}


def origin_text(estate: Estate, path: str) -> str:
    return estate._git("show", f"origin/main:{path}")


def mode_runs(estate: Estate, primary: Primary) -> dict:
    """The three modes' runs of `lanes-edit.sh`: files, `mode=index`, and
    primary with the store reachable (the contract stub, R2f4-S14). Files
    mode is `Primary.files_edit`, whose empty `XDG_CONFIG_HOME` leaves out
    the door's `mode=primary` file, which `Primary` writes into the estate's
    own configuration folder; `estate.edit` there is a primary run, refused
    78 by the checkout's unflipped `lanes-index` (AN13a's B1, as T217m found
    for `files_edit`). `mode=index` names its own file, so it keeps it."""
    return {"files": lambda *a: primary.files_edit(*a),
            "index": lambda *a: estate.edit(*a, env=index_env(estate)),
            "primary": lambda *a: primary.edit(*a)}


def store_asks(primary: Primary) -> int:
    """How many register calls the door has put to the store so far (the
    wrapper's counted calls, as the one-call failure counts them). A read
    verb on primary answers from the register through the door, never from
    the checkout's files or from git (FR-034; T401's primary branch,
    `reg_image` and `reg_paths`), so a primary run that answered leaves this
    count higher than it was before the run. Where it stays put the run read
    the files, as files mode does, and a case that loops over all three modes
    passes without having tested primary."""
    return len(primary.door.register_calls())


def strip_end(text: str) -> str:
    """`.register` normalizes trailing newlines and files mode's `cat` does
    not (lane 5's note on answer 14), so a byte case holds up to them."""
    return text.rstrip("\n")


@pytest.mark.parametrize("case", ["files", "index", "primary", "failed-read", "other-path",
                                  "log-readme"])
def test_register_text_answers_the_bytes_the_scripts_read_today_and_69_on_a_failed_read(
        estate, primary, case):
    """`register-text <path>` (lane 4's T401; GB section 4.3): in files and
    `mode=index` the bytes the scripts read today, on primary the image at
    the door's `n` (`reg_image`); 69 on a failed read in every mode; and 2,
    with nothing on stdout, for a path outside the set (`lanes/repos.tsv`,
    and `lanes/log/README.md`, O21 (a)) in every mode, the store reachable on
    primary. Each 2 case first shows the verb answers in its mode, and on
    primary that the answer came through the register: the door asked the
    store for it, as FR-034 has it, and the files did not answer (T217g)."""
    runs = mode_runs(estate, primary)
    if case in ("files", "index"):
        for path in VERB_PATHS:
            result = runs[case]("register-text", path)
            assert result.returncode == 0, (case, path, result.returncode, result.stderr)
            assert strip_end(result.stdout) == strip_end(origin_text(estate, path)), (case, path)
    elif case == "primary":
        for path in VERB_PATHS:
            result = runs["primary"]("register-text", path)
            assert result.returncode == 0, (path, result.returncode, result.stderr)
            assert strip_end(result.stdout) == strip_end(primary.door.register[path].decode()), path
        assert STORE_ONLY_ROW in runs["primary"]("register-text", "lanes/LANES.md").stdout
    elif case == "failed-read":
        primary.door.unreachable()
        result = runs["primary"]("register-text", "lanes/LANES.md")
        assert (result.returncode, result.stdout) == (69, ""), (result.returncode, result.stderr)
        gone = primary.files_edit("register-text", "lanes/LANES.md",
                                  env={"LANES_REPO": str(estate.root / "no-such-checkout")})
        assert (gone.returncode, gone.stdout) == (69, ""), (gone.returncode, gone.stderr)
    else:
        for mode, run in runs.items():
            asked = store_asks(primary)
            control = run("register-text", "lanes/LANES.md")
            assert control.returncode == 0, (case, mode, "the verb does not answer",
                                             control.returncode, control.stderr)
            if mode == "primary":
                assert store_asks(primary) > asked, \
                    (case, mode, "the primary answer never came through the register: the door "
                     "asked the store nothing, so it read the files, which FR-034 forbids",
                     primary.door.calls())
            result = run("register-text", OUTSIDE_PATHS[case])
            assert (result.returncode, result.stdout) == (2, ""), \
                (case, mode, result.returncode, result.stdout, result.stderr)


def git_grep(estate: Estate, ere: str, *paths: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "grep", "-E", "-e", ere, "origin/main", "--", *paths],
                          cwd=str(estate.wip), env=estate.env, capture_output=True, text=True,
                          check=False)


def image_grep(images: dict, ere: str, prefix: str = "origin/main") -> str:
    """What `register-grep` prints on primary (lane 5's answer 14): each
    log's matching lines, `origin/main:<path>:<line>`, in `.paths`' bytewise
    order, each path once."""
    pattern = re.compile(ere)
    out = []
    for path in sorted(p for p in images if re.match(r"^lanes/log/[^/]+\.md$", p)):
        for line in _lines(images[path].decode("utf-8")):
            if pattern.search(line):
                out.append(f"{prefix}:{path}:{line}")
    return "".join(f"{line}\n" for line in out)


@pytest.mark.parametrize("case", ["files", "index", "primary", "no-match", "failed-read",
                                  "other-path", "log-readme", "log-dir-skips-readme", "case-pair"])
def test_register_grep_prints_what_git_grep_prints_and_1_with_no_match(estate, primary, case):
    """`register-grep [-h] -E <ERE> -- <path>…` (lane 4's T401; GB section
    4.3): what `git grep` prints today on `origin/<branch>` in files and
    `mode=index`, and the same shape from the images on primary; 1 with no
    match; 69 on a failed read; 2 for a path outside the set; `-- lanes/log`
    greps the lane logs alone, never `lanes/log/README.md`; and on primary a
    case pair of logs is 69 with nothing on stdout, while the same store
    answers `register-text` (Q-W11-4 (A); R2f4-S14). In `[no-match]`,
    `[other-path]`, `[log-readme]` and `[log-dir-skips-readme]` the primary
    run also asks the store through the door, since the files answer the same
    1, 2 or lines and so prove nothing about primary (T217g)."""
    runs = mode_runs(estate, primary)
    ere = "^(STARTED|NOTED) "
    if case in ("files", "index"):
        result = runs[case]("register-grep", "-E", ere, "--", "lanes/log")
        expect = git_grep(estate, ere, *LOG_PATHSPEC)
        assert (result.returncode, result.stdout) == (0, expect.stdout), \
            (case, result.returncode, result.stdout, expect.stdout, result.stderr)
    elif case == "primary":
        result = runs["primary"]("register-grep", "-E", ere, "--", "lanes/log")
        assert result.returncode == 0, (result.returncode, result.stderr)
        assert result.stdout == image_grep(primary.door.register, ere), result.stdout
        assert f"lanes/log/{STORE_ONLY_LANE}.md:" in result.stdout, result.stdout
    elif case == "no-match":
        for mode, run in runs.items():
            asked = store_asks(primary)
            result = run("register-grep", "-E", "^NO SUCH LINE$", "--", "lanes/log")
            assert (result.returncode, result.stdout) == (1, ""), (mode, result.returncode,
                                                                  result.stderr)
            if mode == "primary":
                assert store_asks(primary) > asked, \
                    (case, mode, "the primary 1 never came through the register: the door asked "
                     "the store nothing, so it grepped git, which FR-034 forbids",
                     primary.door.calls())
    elif case == "failed-read":
        primary.door.unreachable()
        result = runs["primary"]("register-grep", "-E", ere, "--", "lanes/log")
        assert (result.returncode, result.stdout) == (69, ""), (result.returncode, result.stderr)
        # `register-grep` never reads `LANES_REPO` (that is `register-text`'s
        # knob, above): it greps `origin/<branch>` in `$LANES_WS_ROOT`, the
        # workspace root `LANES_WORKSPACE_ROOT` or `workspace.yaml`'s `path:`
        # names, the same root `lane-worktrees` greps (T401; lane 4's INV401).
        # So the missing checkout goes in the variable the verb reads.
        gone = primary.files_edit("register-grep", "-E", ere, "--", "lanes/log",
                                  env={"LANES_WORKSPACE_ROOT": str(estate.root / "no-such-checkout")})
        assert (gone.returncode, gone.stdout) == (69, ""), (gone.returncode, gone.stderr)
    elif case in OUTSIDE_PATHS:
        for mode, run in runs.items():
            asked = store_asks(primary)
            control = run("register-grep", "-E", ere, "--", "lanes/log")
            assert control.returncode == 0, (case, mode, "the verb does not answer",
                                             control.returncode, control.stderr)
            if mode == "primary":
                assert store_asks(primary) > asked, \
                    (case, mode, "the primary answer never came through the register: the door "
                     "asked the store nothing, so it grepped git, which FR-034 forbids",
                     primary.door.calls())
            result = run("register-grep", "-E", ere, "--", OUTSIDE_PATHS[case])
            assert (result.returncode, result.stdout) == (2, ""), \
                (case, mode, result.returncode, result.stdout, result.stderr)
    elif case == "log-dir-skips-readme":
        readme_ere = "^(# the object logs|STARTED )"
        for mode, run in runs.items():
            asked = store_asks(primary)
            result = run("register-grep", "-E", readme_ere, "--", "lanes/log")
            assert result.returncode == 0, (mode, result.returncode, result.stderr)
            if mode == "primary":
                assert store_asks(primary) > asked, \
                    (case, mode, "the primary answer never came through the register: the door "
                     "asked the store nothing, so it grepped git, which FR-034 forbids",
                     primary.door.calls())
            assert "README.md" not in result.stdout, (mode, result.stdout)
            assert "lanes/log/repoA-2.md:" in result.stdout, (mode, result.stdout)
    else:
        primary.door.commit({"lanes/log/REPOA-2.md": "NOTED — the other half of a case pair\n"})
        result = runs["primary"]("register-grep", "-E", ere, "--", "lanes/log")
        assert (result.returncode, result.stdout) == (69, ""), (result.returncode, result.stdout,
                                                               result.stderr)
        text = runs["primary"]("register-text", "lanes/LANES.md")
        assert text.returncode == 0 and STORE_ONLY_ROW in text.stdout, \
            ("the store did not answer: the 69 may be a failed prefetch", text.returncode,
             text.stderr)


def seed_logs(estate: Estate, logs: dict) -> None:
    """Commit and push `logs` (render-set path to text) into the estate's
    register, so that files mode reads them from `origin/main` and the
    primary store, built from this checkout's render set afterwards, holds
    them too."""
    for path, text in logs.items():
        target = estate.wip / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    estate._git("add", "-A")
    estate._git("commit", "-q", "-m", "add the logs the case greps")
    estate._git("push", "-q", "origin", "main")


def edit_bytes(primary: Primary, *args, env: dict | None = None) -> subprocess.CompletedProcess:
    """`primary.edit`, with stdout and stderr kept as bytes, so that a case
    holds the answer to git's own bytes (`Estate.run` decodes them)."""
    child = dict(primary.e.env)
    for key, value in primary.env(env).items():
        if value is None:
            child.pop(key, None)
        else:
            child[key] = value
    return subprocess.run(["bash", str(primary.edit_path), *args], capture_output=True,
                          env=child, timeout=120, cwd=str(primary.e.root),
                          stdin=subprocess.DEVNULL, check=False)


def store_images(door: Door, n: int) -> dict:
    """The store's render-set images at seq `n`, path to bytes, as the
    contract stub keeps them (`lanes-index.register/<n>/`)."""
    root = door.store / "lanes-index.register" / str(n)
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*")) if path.is_file()}


def git_grep_at_defaults(where: Path, images: dict, ere: str) -> bytes:
    """What `git grep -E -e <ERE> origin/main` prints for `lanes/log`'s
    pathspec pair over a tree holding `images`, under git's defaults: a
    repository of its own under `where`, with no system, global or XDG
    configuration and no attributes file (an empty `$HOME` and
    `XDG_CONFIG_HOME`), under `LC_ALL=C`, as files mode greps. So the bytes a
    case expects are git's own, its tree order and its quoting of a path
    (`core.quotePath`, on by default) among them, never the case's guess."""
    for name in ("home", "xdg", "repo"):
        (where / name).mkdir(parents=True)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(where / "home"),
           "XDG_CONFIG_HOME": str(where / "xdg"), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "LC_ALL": "C"}
    repo = where / "repo"
    for path, data in images.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def git(*argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(repo), *argv], capture_output=True, env=env,
                              stdin=subprocess.DEVNULL, check=False)

    for argv in (("init", "-q"), ("add", "-A"),
                 ("-c", "user.name=readers", "-c", "user.email=readers@example.invalid",
                  "commit", "-q", "-m", "the store's images"),
                 ("update-ref", "refs/remotes/origin/main", "HEAD")):
        done = git(*argv)
        assert done.returncode == 0, (argv, done.returncode, done.stderr)
    found = git("grep", "-E", "-e", ere, "origin/main", "--", *LOG_PATHSPEC)
    assert found.returncode in (0, 1), (found.returncode, found.stderr)
    return found.stdout


#: ONE SNAPSHOT (T401's Q2): a log whose name is outside `check_lane_name`'s
#: class (`+`), which `--all` never fetches, so every run of `register-grep`
#: reads it through form 3's `--log-key=` (O18), and which sorts after every
#: other log, so its read is the run's last image. `git grep` prints its name
#: as it is (no `"`, `\` or byte from 0x80 up). The write that moves the head
#: appends a NOTED line to `repoA-2`'s log, which the prefetch cached.
SNAPSHOT_LANE = "repoX+1"
SNAPSHOT_LOG = f"lanes/log/{SNAPSHOT_LANE}.md"
SNAPSHOT_TEXT = (f"STARTED — lane {SNAPSHOT_LANE}, session {UUID_A1}@Eagle, "
                 f"2026-10-05T00:30:00Z, lane:{SNAPSHOT_LANE} → home opensoft/repoX; "
                 f"dir /work/repoX\n")
SNAPSHOT_MOVED = "lanes/log/repoA-2.md"
SNAPSHOT_LINE = (f"NOTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-05T01:00:00Z, "
                 f"lane:repoA-2 — a write that moved the head under the read, move %d\n")


@pytest.mark.parametrize("moves, generation", [(1, False), (3, False), (1, True)],
                         ids=["one-move", "three-moves", "generation-moved"])
def test_register_grep_on_primary_answers_one_snapshot_and_69_after_three_moved_runs(
        estate, moves, generation):
    """ONE SNAPSHOT (T401's Q2: lane 3's ruling, #165 6851977580, taking lane
    5's detect-and-retry, #165 6851740524; tasks:859 at `94fab177`). On
    primary `register-grep -E <ERE> -- lanes/log` takes `.head`'s `n=` and
    `generation=` after `reg_paths`, and again after its last image; where
    either moved, it drops the answer and runs again from `reg_paths`, three
    runs at most, and then exits 69 with nothing on stdout.
    THE STUB MOVES THE HEAD BETWEEN CALLS (the door's `move_each`): at each
    of the first `moves` reads of `--log-key=repoX+1`, before the store
    answers it, one write appends a NOTED line to `repoA-2`'s log. Every run
    makes that read, as its last image, after `repoA-2`'s image came from the
    prefetch's cache at `n`; the read finds `repoA-2` changed in `(n, n']`, so
    form 3 rewrites the family at `n'`, and `.head` names `n'` (contract 3.6).
    `[one-move]`: one move, then a clean run, so the verb answers once, exit
    0, with what `git grep` prints over the store's tree at `n + 1`, the moved
    line among it, and nothing of the dropped run; `repoX+1` is read twice,
    once a run. `[three-moves]`: every run's head moves, so it ends 69 with
    nothing on stdout; `repoX+1` is read three times, and never a fourth.
    `[generation-moved]`: the one move gives the store a new generation and
    keeps `n`, appending the line in the image at `n` (a new generation whose
    head lands on the same `n`). The read finds `.head`'s generation not the
    store's, so form 3 rewrites the whole family at `n` under the new one
    (contract 3.6). Only the generation half of the pair tells the runs
    apart, so a T401 that compares `n` alone answers the first run, without
    the moved line, and fails on stdout. That first run is stale because of
    the read order: the verb reads its logs in tree order (`LC_ALL=C sort`
    of their paths), so `repoA-2`'s image comes from the prefetch's cache at
    `n` before `repoX+1`'s form-3 read moves the store. A new `SNAPSHOT_LANE`
    or `SNAPSHOT_MOVED` must keep `SNAPSHOT_MOVED` sorting first, or the
    first run reads the moved log after the move, and the stdout check no
    longer tells an `n`-only T401 apart (lane 2's RV26 NIT 11). The verb
    answers once, exit 0, with what `git grep` prints over the store's tree
    at `n` after the move; `repoX+1` is read twice; the head keeps `n` under
    a new generation (lane 2's RV23 NIT 3).
    It passes from lane 4's T401 round on lane 3's Q2 ruling, `8d72e579`
    (line R's merge90 and later), and fails before it. On lane 4's
    `6318d5e5` (#165 6851877746), which reads once, `[one-move]` fails on
    stdout, its answer straddling `n` and `n + 1`, so `repoA-2`'s moved line
    is missing, `[generation-moved]` on stdout as well, and `[three-moves]`
    on its exit, 0 with lines, not 69 (T217zh)."""
    seed_logs(estate, {SNAPSHOT_LOG: SNAPSHOT_TEXT})
    primary = Primary(estate)
    first, first_generation = primary.door.head()
    primary.door.fail(move_each={"key": SNAPSHOT_LANE, "times": moves, "path": SNAPSHOT_MOVED,
                                 "line": SNAPSHOT_LINE, "generation": generation})
    ere = "^(STARTED|NOTED) "
    result = edit_bytes(primary, "register-grep", "-E", ere, "--", "lanes/log")
    reads = [call for call in primary.door.calls()
             if call["form"] == 3 and f"--log-key={SNAPSHOT_LANE}" in call["argv"]]
    head, head_generation = primary.door.head()
    where = (moves, generation, "exit", result.returncode, "head", first, first_generation, "->",
             head, head_generation, "reads of",
             SNAPSHOT_LANE, len(reads), result.stdout.decode("utf-8", "replace"),
             result.stderr.decode("utf-8", "replace")[-1500:])
    if moves == 1:
        expect = git_grep_at_defaults(estate.root / "snapshot-oracle",
                                      store_images(primary.door, first if generation else first + 1),
                                      ere)
        moved = (SNAPSHOT_LINE % 1).rstrip("\n").encode("utf-8")
        assert moved in expect and f"{SNAPSHOT_LOG}:".encode() in expect, \
            ("the oracle lacks the moved line or the log read by --log-key=", expect)
        assert (result.returncode, result.stdout) == (0, expect), \
            where + ("expected, git grep at n + 1:", expect.decode("utf-8", "replace"))
        assert len(reads) == 2, where
        if generation:
            assert head == first and head_generation != first_generation, where
        else:
            assert head == first + 1, where
    else:
        assert (result.returncode, result.stdout) == (69, b""), where
        assert len(reads) == 3, where
        assert head == first + 3, where


#: QUOTED NAMES (T401's Q3): six logs whose names are outside
#: `check_lane_name`'s class, so that each is read through form 3's
#: `--log-key=` (O18), and each holds one kind of byte that `git grep` quotes
#: under git's defaults: `"`, `\`, `é` (the two bytes 0xc3 0xa9), and three
#: control bytes (tasks:860 at `8e8d1b49`): 0x07, one of the seven git writes
#: as a letter (`\a`), and 0x01 and 0x7f, which it writes in octal. No name
#: holds a tab, a newline, 0x0b, 0x0c or 0x0d: the contract stub keeps `.head`
#: and `.paths` as tab-separated lines and reads `.head` by `splitlines()`,
#: so those bytes would break the stub, not the verb (lane 2's RV23 NIT 4).
QUOTED_LOGS = {"lanes/log/say\"hi-1.md": "say\"hi-1",
               "lanes/log/back\\slash-1.md": "back\\slash-1",
               "lanes/log/café-1.md": "café-1",
               "lanes/log/bel\x07-1.md": "bel\x07-1",
               "lanes/log/ctl\x01-1.md": "ctl\x01-1",
               "lanes/log/del\x7f-1.md": "del\x7f-1"}
#: How `git grep` prints each under git's defaults: the path in double quotes,
#: `"` and `\` escaped by a backslash, 0x07 as `\a`, and every other control
#: byte and each byte from 0x80 up as a backslash and three octal digits,
#: after the unquoted `origin/main:`.
QUOTED_AS = (b'origin/main:"lanes/log/say\\"hi-1.md":STARTED ',
             b'origin/main:"lanes/log/back\\\\slash-1.md":STARTED ',
             b'origin/main:"lanes/log/caf\\303\\251-1.md":STARTED ',
             b'origin/main:"lanes/log/bel\\a-1.md":STARTED ',
             b'origin/main:"lanes/log/ctl\\001-1.md":STARTED ',
             b'origin/main:"lanes/log/del\\177-1.md":STARTED ')
#: THE WORKSTATION'S OWN GIT CONFIGURATION, which primary's answer does not
#: follow: `core.quotePath` off, under which `git grep` prints 0xc3 0xa9 as
#: they are; `grep.lineNumber` on, under which it puts each line's number
#: before the line; `color.grep = always`, under which it colours its output
#: even into a file (`color.ui = always` sets the same for `git grep`, and
#: would colour every other git command of the run too); and an attributes
#: file at git's default place, `$XDG_CONFIG_HOME/git/attributes`, marking
#: every file binary, under which a grep without `--text` prints `Binary file
#: image matches` for each image.
WORKSTATION_GIT = {"git/config": ("[core]\n\tquotePath = false\n[grep]\n\tlineNumber = true\n"
                                  "[color]\n\tgrep = always\n"),
                   "git/attributes": "* binary\n"}


def test_register_grep_on_primary_prints_each_path_as_git_grep_does_under_gits_defaults(estate):
    """QUOTED NAMES (T401's Q3: lane 3's ruling, #165 6851977580; lane 4's
    RC-W23 N2, #165 6851877746; tasks:860 at `94fab177`). Without `-h`,
    primary prints each path as `git grep` prints it under git's defaults,
    whatever the workstation's git configuration says: a path holding `"`,
    `\\`, a control byte or a byte from 0x80 up goes in double quotes, with
    `\\a` and the six other letter escapes for those seven control bytes
    and octal escapes for the rest, after the unquoted
    `origin/$LANES_BRANCH:`; and each image is grepped as
    text (`--text`), so no attributes file outside the register makes a
    `Binary file` line of it. So answer 14's "byte for byte what files mode
    prints" holds (#165 6746507353).
    The register holds `QUOTED_LOGS` beside the estate's logs and the store's
    own `repoS-1` log, so the answer is the store's. The expected bytes are
    `git grep`'s own over the store's tree, under git's defaults
    (`git_grep_at_defaults`), first held to `QUOTED_AS`, so the case's
    premise is git's behaviour and never a guess. Then the workstation's git
    configuration turns `core.quotePath` off, numbers and colours `git
    grep`'s lines, and marks every file binary in its default attributes
    file, and primary's answer must still be those bytes, exit 0.
    It passes from lane 4's T401 round on lane 3's Q3 ruling, `8d72e579`
    (line R's merge90 and later), and fails before it. On lane 4's
    `6318d5e5` (#165 6851877746) it fails on stdout: each path after the
    prefix as it is, unquoted, and each image grepped without `--text`, so a
    `Binary file image matches` line stands for its lines (T217zi)."""
    seed_logs(estate, {path: (f"STARTED — lane {lane}, session {UUID_A1}@Eagle, "
                              f"2026-10-05T00:40:00Z, lane:{lane} → home opensoft/repoQ; "
                              f"dir /work/repoQ\n")
                       for path, lane in QUOTED_LOGS.items()})
    primary = Primary(estate)
    ere = "^(STARTED|NOTED) "
    expect = git_grep_at_defaults(estate.root / "quoted-oracle",
                                  store_images(primary.door, primary.door.head()[0]), ere)
    for quoted in QUOTED_AS:
        assert quoted in expect, ("git's defaults print this path otherwise", quoted, expect)
    assert f"lanes/log/{STORE_ONLY_LANE}.md:".encode() in expect, expect
    for name, text in WORKSTATION_GIT.items():
        target = estate.config / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    result = edit_bytes(primary, "register-grep", "-E", ere, "--", "lanes/log")
    assert (result.returncode, result.stdout) == (0, expect), \
        (result.returncode, result.stdout.decode("utf-8", "replace"),
         "expected, git grep under git's defaults:", expect.decode("utf-8", "replace"),
         result.stderr.decode("utf-8", "replace")[-1500:])


# ------------------------------------------------- lane 4's key() trim (T426)
#: THE CASES (T259; R31; the design's S3, "The normalized `archive:` key"; the
#: test plan's AT-LR010, "a long digit run"). `retired-identity <lane>` prints
#: each archived spelling that `RETIRED_ROWS_AWK` matches, and exits 0; it
#: matches by the lane's name in any case, or by `key()`; where none matches
#: it exits 8. `key()` is the name before its last `-`, lower-cased, a `-`, and
#: the digits after it (less one trailing letter) without their leading zeros.
#: v2.5's SQL trims those zeros as text, a lone `0` kept. The awk's `p + 0` is
#: a double, so two runs that differ only past the 15th digit key alike, and
#: it matches a row that no SQL key names (the design: `foo-9007199254740993`
#: keys to `foo-9007199254740992` under mawk 1.3.4, and a run of 30 prints with
#: an exponent). Lane 4's T426 trims as text on primary, and keeps `(p + 0)`
#: in files mode (spec:59; review m7), so the two columns differ on the last
#: three rows alone, and those three in files mode are the answers today.
#:
#: Each row is (case, the archived spelling, the lane asked, whether files mode
#: answers it, whether primary does). Each case has a repository name of its
#: own, so that one archive holds them all and no row answers another's
#: question. The first five are the controls: both modes answer them, so a
#: no-answer further down is the key's and not a verb that answers nothing.
KEY_ROWS = (
    ("leading-zeros", "keya-0007", "keya-7", True, True),
    ("lone-zero", "keyb-000", "keyb-0", True, True),
    ("trailing-letter", "keyc-0012b", "keyc-12", True, True),
    ("padded-16-digits", "keyd-0009007199254740993", "keyd-9007199254740993", True, True),
    ("padded-30-digits", "keye-000123456789012345678901234567890",
     "keye-123456789012345678901234567890", True, True),
    ("16-digits-differ-in-the-last", "keyf-9007199254740992", "keyf-9007199254740993",
     True, False),
    ("16-digits-differ-the-other-way", "keyg-9007199254740993", "keyg-9007199254740992",
     True, False),
    ("30-digits-differ-in-the-last", "keyh-123456789012345678901234567890",
     "keyh-123456789012345678901234567891", True, False),
)

#: An archived row as the register writes it (`archive-rows`): the lane in
#: backticks in its first cell. The state cell's separator is built, not typed.
KEY_ARCHIVE_ROW = ("| `{lane}` | harness `{uuid}` | Eagle / test / brett | 2026-10-01T00:00Z "
                   "| none | handoffs/{lane}.md | RETIRED " + chr(0xB7) + " 2026-09-02T00:00:00Z "
                   + chr(0xB7) + " retired |")


def sql_key(name: str) -> str:
    """v2.5's key of an archived name, by the design's S3 rule: the name before
    its last `-`, lower-cased, `-`, and the digits after it, less one trailing
    letter, trimmed of leading zeros as text (`0` stays `0`); `""` where there
    is no key (no `-`, or what follows is not all digits)."""
    found = re.match(r"^(.*)-([0-9]+)[A-Za-z]?$", name)
    if not found:
        return ""
    return found.group(1).lower() + "-" + (found.group(2).lstrip("0") or "0")


def seed_key_archive(estate: Estate) -> None:
    """Retire each `KEY_ROWS` spelling into the estate's archive, committed and
    pushed, so that files mode reads it from `origin/main` and the primary
    store, built from this checkout's render set afterwards, holds it too."""
    archive = estate.wip / "lanes" / "archive" / "LANES-retired.md"
    rows = [KEY_ARCHIVE_ROW.format(lane=spelling, uuid=f"eeeeeeee-0002-4000-8000-{n:012d}")
            for n, (_, spelling, _, _, _) in enumerate(KEY_ROWS, 1)]
    archive.write_text(archive.read_text(encoding="utf-8").rstrip("\n") + "\n"
                       + "\n".join(rows) + "\n", encoding="utf-8")
    estate._git("add", "-A")
    estate._git("commit", "-q", "-m", "retire the spellings the key() case asks about")
    estate._git("push", "-q", "origin", "main")


@pytest.mark.parametrize("mode", ["primary", "files"])
def test_retired_rows_key_trims_leading_zeros_as_text_on_primary(estate, mode):
    """`RETIRED_ROWS_AWK`'s `key()` trims a number's leading zeros as text on
    primary (lane 4's T426; R31; GB section 4.3), so `retired-identity` reads
    the archive by the keys v2.5 gives it; files mode keeps `(p + 0)`, byte
    for byte as today (spec:59). The archive holds the `KEY_ROWS` spellings,
    and each is asked about by its lane.
    `[primary]`: a run of 16 digits or more that differs from an archived one
    in its last digit is NOT retired (exit 8, nothing on stdout), and a run
    padded with zeros still is (exit 0, the archived spelling). The expected
    answers are first held to v2.5's own key (`sql_key`), so that the table is
    the contract's and not a guess. It fails until T426 trims on primary, and
    until `reg_open` sets `retired-identity`'s mode as a reader (T504).
    `[files]`: the same questions, answered as `(p + 0)` answers them today,
    the three near-duplicates included: they are retired, by the double's
    rounding. It passes at the base and must pass after T426."""
    seed_key_archive(estate)
    primary = Primary(estate) if mode == "primary" else None
    run = primary.edit if primary else estate.edit
    if primary:
        for case, spelling, asked, _, answers in KEY_ROWS:
            sql = spelling.lower() == asked.lower() or (
                sql_key(asked) != "" and sql_key(spelling) == sql_key(asked))
            assert answers == sql, (case, "the table disagrees with v2.5's key", spelling, asked)
    for case, spelling, asked, in_files, on_primary in KEY_ROWS:
        answers = on_primary if primary else in_files
        result = run("retired-identity", asked)
        where = (mode, case, "exit", result.returncode, "calls at the door:",
                 len(primary.door.calls()) if primary else "-", spelling, asked,
                 result.stdout, result.stderr)
        if answers:
            assert (result.returncode, result.stdout) == (0, spelling + "\n"), where
        else:
            assert (result.returncode, result.stdout) == (8, ""), where
    if primary:
        assert primary.door.calls(), ("the primary run never reached the door, so it read as "
                                      "files mode does", primary.door.calls())
