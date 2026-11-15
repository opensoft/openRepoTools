# SPDX-License-Identifier: Apache-2.0
"""AT-LR5's `LANDING EXPIRED` (F13) and take-with-no-UTC (U3) cases (#165, L2-W4).

PHASE N, ON A REAL POSTGRESQL 16: `commit_write`'s step 7 is lane 1's SQL
(design.md §1.3's step 7, §1.3.1), so each case calls it directly, with no
verb; the verb is AT-F13's. The rest of AT-LR5 is T232's, in this module too.

THE FIXTURE, AT-LR006'S, ON A CLONE OF ITS OWN: each case clones
`tmpl_imported` (section 3.1; T227), runs §1.4's two database-level
statements on the clone, since a clone does not copy `pg_database.datacl`,
and drops it `WITH (FORCE)` at the end. `Clone.to_primary` then brings it to
`primary` with the marker `present` by the documented functions, as
REGISTER-WRITER: `commit_write` with a `cutover` entry over the template's
import, then `record_marker` (TP:4610–4615; the plan's fixtures at TP:4354
and :4806). Every call logs in as the fixture's writer login, `lanes_w_fx`
(T228), whose privileges come through REGISTER-WRITER, in the commit call's
own form:

    psql -X -q -A -t -v ON_ERROR_STOP=1 -v VERBOSITY=verbose -v SHOW_CONTEXT=never
    BEGIN ISOLATION LEVEL SERIALIZABLE;
    SELECT lanes_register.commit_write(:base, :'wid'::uuid, :client, :'gen'::uuid, :'entry'::jsonb);
    COMMIT;

with the script on stdin, so a refusal's first stderr line is
`ERROR:  <SQLSTATE>: <message>` and its second `DETAIL:  <token>` (U7).

EACH ENTRY IS AN APPEND OF ONE LINE TO `lanes/LANES.md`, built as AT-LR006
builds one: the edit, the file's digest after it (`render_file`'s bytes,
computed here from `doc_lines` as the superuser reads them), and the line's
`register_lines` row, whose fields the test sets as the client would parse
them. Lines name `opensoft/r9`, which `lanes/repos.tsv` maps from `r9`, so a
row's `repo_spellings` is `{opensoft/r9,r9}` where the case says both. A
take's `utc_ts` is set from the database's clock at the snapshot, past Rule
6's 30 minutes where the case says so, so no case waits for the window.

THE ORACLE OF A REFUSAL: `psql` exits 3; its first stderr line is the
code's, naming the rule; its second is exactly the rule's `DETAIL:` token;
and the head, the journal, its edits, the files, `doc_lines`,
`register_lines` and the switch equal their values before, with the write id
absent.

Every case FAILS UNTIL lane 1's T107 (L1-A6, `commit_write` and its step 7)
and T118 (L1-A16, the kinds' slots), and lane 2's T227 (`tmpl_imported`) and
T228 (`lanes_w_fx`) land. Without PostgreSQL 16 each skips.

THE MODULE ALSO HOLDS, each at its own section below, in this order: T243's
test 4, C10, D19 and section 4.1 (phase W, the client's writers on a real
register); T248's AT-F14 (phase W); T233's AT-F5 group A (phase N, the act's
client half, its off-primary and walk cases with no engine); T252's AT-F5
group B (phase W);
T232's AT-LR5 and AT-LR009 (phase N, `commit_write` called directly on this
section's `Clone`, as here), whose rollback entry is T304's form; and, last,
T243d's `register commit` path refusal (lane 1's follow-up 2: phase W, as
T243's, but with no engine).
"""

from __future__ import annotations

import atexit
import errno
import hashlib
import itertools
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pytest

from pgcluster import SUPERUSER, Database
from sql_register_helpers import (LANES_INDEX, PSQL_SHIM, PSQL_SHIM_CONTROL, PSQL_SHIM_ENDS,
                                  PSQL_SHIM_LOG, REPO, flipped_copy, guard_session)
from test_lane_start_claude_current import Sandbox, _write

#: THE LANDING GATE'S TABLE (T280's `SQL_REGISTER_GATE_TABLE`; task sets
#: version 12b's rule 11, lane 3, opensoft/openRepoTools#165 6877673742):
#: the 007 tasks each id waits for, from the Orders of the module's six
#: tasks, T223, T232, T233, T243, T248 and T252 (tasks:2140, :2239, :2247,
#: :2341, :2384 and :2397 at `204145ae`). Each row names its task and the
#: clause it rests on. A key is a test's name, or one id, `name[param]`,
#: whose row takes the place of its function's; the module has no `"*"`
#: row, since its waits share no task. The table is lane 2's GP-24 plan's
#: (`GP-24-gate-tables-plan.md`, sha256 `16d738b9`), with T415 added to two
#: T233 rows ahead of T233's Order, since each writes on primary through
#: T415's `pw_run` (lane 4, opensoft/openRepoTools#165 6879601079; T223c).
#: Only where the gate is active (`tests/sql_register_gate.py`) does it skip
#: an id until all its tasks have landed; elsewhere it changes nothing.
SQL_REGISTER_GATE_TABLE = {
    "test_a_child_at_the_seam_stops_with_none_and_runs_no_tail": ("T413", "T414", "T415", "T423"),  # T248; tasks:2384
    "test_a_handoff_request_never_refuses_the_holders_own_handoff": ("T107", "T108", "T111", "T112", "T410", "T415"),  # T252; tasks:2397
    "test_a_hold_line_that_names_no_repository_is_refused_with_2": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_a_landing_expired_closes_only_the_holders_landings_for_that_pr_and_repository": ("T107", "T108", "T115", "T118", "T227", "T228"),  # T223; tasks:2140
    "test_a_landing_expired_for_a_stale_landing_commits_and_frees_main_in_main_slots": ("T107", "T108", "T115", "T118", "T227", "T228"),  # T223; tasks:2140
    "test_a_landing_expired_that_names_no_stale_landing_is_lr005_and_writes_nothing": ("T107", "T108", "T115", "T118", "T227", "T228"),  # T223; tasks:2140
    "test_a_line_deriving_a_key_that_is_not_a_scope_exits_2_on_lr010_once": ("T107", "T108", "T111", "T112", "T410", "T415"),  # T252; tasks:2397
    "test_a_malformed_act_is_refused_lr004_before_the_head_lock": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_a_refresh_or_a_line_of_no_kind_with_no_utc_commits_and_a_take_with_none_loads_at_files": ("T107", "T108", "T115", "T118", "T227", "T228"),  # T223; tasks:2140
    "test_a_refused_writer_replays_its_output_then_the_refusal": ("T413", "T414", "T415", "T423"),  # T248; tasks:2384
    "test_a_second_reach_of_the_seam_in_one_run_exits_2": ("T413", "T414", "T415", "T423"),  # T248; tasks:2384
    "test_a_serialization_failure_is_retried_never_reported_as_69": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_a_side_effect_runs_once_after_commit_and_never_for_a_refusal": ("T413", "T414", "T415", "T423"),  # T248; tasks:2384
    "test_a_slot_line_of_another_shape_commits_0": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_a_star_key_after_the_base_is_reported_as_the_first_listed_scope": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_a_stray_import_stores_its_keys_and_a_stray_revert_none": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_a_write_that_cannot_get_its_turn_exits_75_register_busy": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_a_writer_prints_its_output_once_however_many_attempts_it_made": ("T413", "T414", "T415", "T421"),  # T248; tasks:2384
    "test_act_begin_on_primary_prints_id_seq_and_generation": ("T111", "T410", "T411"),  # T233; tasks:2247
    "test_act_begin_prints_its_base_and_touches_no_database_off_primary": ("T111", "T410", "T411"),  # T233; tasks:2247
    "test_act_begin_rebase_keeps_the_id_and_takes_the_new_base": ("T111", "T410", "T411", "T415"),  # T233; tasks:2247, and T415 ahead of its Order (lane 4, opensoft/openRepoTools#165 6879601079)
    "test_act_begin_rebase_refuses_with_2": ("T111", "T410", "T411"),  # T233; tasks:2247
    "test_act_id_is_the_acts_id_on_a_write_and_null_on_every_other_entry": ("T107", "T108", "T227", "T228", "T304"),  # T232; tasks:2239
    "test_act_variables_change_nothing_in_files_mode": ("T107", "T108", "T111", "T112", "T410", "T415"),  # T252; tasks:2397
    "test_an_aborted_cutover_and_a_reimport_leave_no_scopes_at_a_deleted_seq": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_an_act_that_decided_on_canon_lane_is_refused_by_a_row_added_on_its_walk": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417"),  # T252; tasks:2397
    "test_an_acts_own_earlier_write_never_refuses_its_later_one": ("T107", "T108", "T111", "T112", "T410", "T415"),  # T252; tasks:2397
    "test_an_alias_edit_racing_a_claim_cannot_let_two_claims_of_one_object_pass": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_an_empty_expectation_records_act_id_and_checks_nothing": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_an_entry_outside_any_act_refuses_an_acts_write_lr009": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_an_import_a_cutover_and_a_rollback_store_only_the_star_key": ("T107", "T108", "T227", "T228", "T304"),  # T232; tasks:2239
    "test_canon_lane_walk_prints_each_hop_with_canon_lanes_exit_code": ("T411",),  # T233; tasks:2247
    "test_canon_lane_walk_whose_register_read_fails_off_primary_exits_1_and_prints_nothing": ("T411",),  # T233; tasks:2247
    "test_claim_prints_its_register_seq": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_each_claim_and_main_rule_lr005_carries_its_detail_token": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_each_entry_stores_the_keys_its_lines_derive": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_each_line_kind_takes_or_releases_main_as_q17_b_says": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_each_of_the_three_conditions_holds": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417"),  # T252; tasks:2397
    "test_lanes_act_is_unset_before_a_launch": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417"),  # T252; tasks:2397
    "test_lr002_comes_before_lr009_after_a_rollback": ("T107", "T108", "T227", "T228", "T304"),  # T232; tasks:2239
    "test_lr005_does_not_fire_on_a_released_claims_spellings": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_lr005_refuses_a_claim_whose_spellings_meet_another_lanes_live_claim": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_lr005_refuses_a_hold_over_another_lanes_open_taker": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_lr005_rolls_back_the_head_and_every_row": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_lr009_names_the_first_changed_scope_its_seq_lane_and_verb": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_on_primary_a_take_with_no_readable_utc_is_lr005_take_no_utc_and_writes_nothing": ("T107", "T108", "T115", "T118", "T227", "T228"),  # T223; tasks:2140
    "test_register_commit_refuses_an_unrenderable_path_with_2_before_the_store_opens": ("T107", "T108", "T112", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_seam_out_is_written_once_before_the_child_acts": ("T413", "T414", "T415", "T423"),  # T248; tasks:2384
    "test_ten_writers_released_together_all_commit_in_order": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_the_act_id_checks_refuse_an_act_id_on_another_kind_and_a_malformed_one": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_the_burst_window_is_effective_a_short_deadline_sends_writers_busy": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_the_claim_behind_the_alias_is_refused_by_lr005_on_its_spellings": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_the_client_refuses_a_bad_act_with_2_before_any_call": ("T111", "T410", "T411", "T415"),  # T233; tasks:2247, and T415 ahead of its Order (lane 4, opensoft/openRepoTools#165 6879601079)
    "test_the_client_refuses_an_acts_stale_base_with_2_at_the_snapshot": ("T107", "T108", "T111", "T112", "T410", "T415"),  # T252; tasks:2397
    "test_the_commits_act_backstops_are_lr007_act_generation_and_lr004": ("T107", "T227", "T228"),  # T252; tasks:2397
    "test_the_default_deadline_is_30_s_for_a_write_that_never_gets_its_turn": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_the_for_lane_checks_refuse_a_for_lane_off_a_landing_expired_and_a_landing_expired_that_closes_no_landing": ("T107", "T108", "T115", "T118", "T227", "T228"),  # T223; tasks:2140
    "test_the_holder_may_write_its_own_landing_expired": ("T107", "T108", "T115", "T118", "T227", "T228"),  # T223; tasks:2140
    "test_the_image_cache_stays_content_addressed_under_the_burst_and_a_corrupt_object_is_refetched": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_the_later_hold_exits_2_and_prints_the_earlier_line": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_the_scratch_flag_is_honoured_only_for_its_own_attempt_directory": ("T413", "T414", "T415", "T423"),  # T248; tasks:2384
    "test_the_scratch_flag_never_reaches_git_gh_or_tmux": ("T413", "T414", "T415", "T423"),  # T248; tasks:2384
    "test_two_claimants_one_claimed_and_the_other_exits_2": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_two_spellings_of_one_object_claimed_at_once_leave_one_claimed_and_exit_2": ("T107", "T108", "T227", "T228", "T302", "T413", "T414", "T415", "T421", "T422"),  # T243; tasks:2341
    "test_two_spellings_of_one_repository_hold_one_main": ("T107", "T108", "T227", "T228"),  # T232; tasks:2239
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[guard-answer-2-child]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T502", "T510"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-end-retire-rows]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T430"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-end-w13-set-row-state]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T430"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-end-w14-log-ended]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T430"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-handoff-late-paused]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T429"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-handoff-w11-append-line]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T429"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-handoff-w12-set-row-state]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T429"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-handoff-w9-log-paused]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T429"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-request-handoff]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T432"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-start-start-record]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T427", "T428"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-start-w1-add-row]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T428"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-start-w1-start-record]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T428"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[lane-start-w8-request-handoff]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T428"),  # T252; tasks:2397
    "test_an_act_whose_scope_changed_before_its_commit_writes_nothing[skill-step-4-writes]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T431"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[guard-answer-2-child]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T502", "T510"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-end-retire-rows]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T430"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-end-w13-set-row-state]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T430"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-end-w14-log-ended]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T430"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-handoff-late-paused]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T429"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-handoff-w11-append-line]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T429"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-handoff-w12-set-row-state]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T429"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-handoff-w9-log-paused]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T429"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-request-handoff]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T432"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-start-start-record]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T427", "T428"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-start-w1-add-row]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T428"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-start-w1-start-record]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T428"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[lane-start-w8-request-handoff]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T428"),  # T252; tasks:2397
    "test_an_act_whose_scopes_held_commits[skill-step-4-writes]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T431"),  # T252; tasks:2397
    "test_each_of_the_three_conditions_holds[lane-end-gate]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T430"),  # T252; tasks:2397
    "test_each_of_the_three_conditions_holds[lane-start-reread]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T428"),  # T252; tasks:2397
    "test_each_of_the_three_conditions_holds[skill-step-4]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T431"),  # T252; tasks:2397
    "test_lanes_act_is_unset_before_a_launch[exec]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T428"),  # T252; tasks:2397
    "test_lanes_act_is_unset_before_a_launch[respawn-pane]": ("T107", "T108", "T410", "T411", "T413", "T414", "T415", "T417", "T429"),  # T252; tasks:2397
}

REGISTER = "lanes_register"
IMPORTED = "tmpl_imported"
WRITER_LOGIN = "lanes_w_fx"
CONNECT_TO = "lanes_register_writer, lanes_register_reader, lanes_indexer"
LANES_MD, STORE = "lanes/LANES.md", "lanes/STORE"
WS, AUTHOR = "ws-t223", "T223 Fixture <t223@example.invalid>"
OPERATOR = "operator-t223"
MARKER_COMMIT = "c0ffee" + "0" * 34
GIT_COMMIT, GIT_TREE = "1" * 40, "2" * 40

#: The lanes and the repository of the cases: L1 holds, L2 writes the
#: release, L3 holds nothing on `opensoft/r9`.
L1, L2, L3 = "L1-t223", "L2-t223", "L3-t223"
KEY, ALIAS, OTHER_KEY = "opensoft/r9", "r9", "opensoft/r8"
BOTH = [KEY, ALIAS]
PR, OTHER_PR = 7, 8
BAD_STAMP = "2026-13-45T99:99Z"

#: Q17 (B)'s slots for the kinds these cases write (lane 1's REGISTER_SLOTS).
SLOTS = {"HOLD": ("take", "hold"), "LANDING": ("take", "landing"),
         "LANDED": ("close", "landing"), "LANDING EXPIRED": ("close", "landing"),
         "HOLD (refresh)": (None, None), None: (None, None)}

COMMIT_SQL = ("BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
              f"SELECT {REGISTER}.commit_write(:base, :'wid'::uuid, :client, :'gen'::uuid, :'entry'::jsonb);\n"
              "COMMIT;\n")
MARKER_SQL = f"SELECT {REGISTER}.record_marker(:client, :seq, :'commit', :'ws');\n"

#: Everything a refused call must leave as it was.
STATE_SQL = f"""
SELECT md5(concat_ws('|',
  (SELECT seq::text FROM {REGISTER}.register_head),
  (SELECT string_agg(j::text, ',' ORDER BY j.seq) FROM {REGISTER}.journal j),
  (SELECT string_agg(e::text, ',' ORDER BY e.seq, e.ord) FROM {REGISTER}.journal_edits e),
  (SELECT string_agg(f::text, ',' ORDER BY f.path) FROM {REGISTER}.files f),
  (SELECT string_agg(d::text, ',' ORDER BY d.line_id) FROM {REGISTER}.doc_lines d),
  (SELECT string_agg(r::text, ',' ORDER BY r.line_id) FROM {REGISTER}.register_lines r),
  (SELECT string_agg(s::text, ',') FROM {REGISTER}.register_switch s)));
"""

_NAMES = itertools.count(1)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rendered(lines: Sequence[str], final_newline: bool) -> bytes:
    """`render_file`'s bytes: the lines joined by LF, and a last LF where
    the file ends with one and holds a line."""
    text = "\n".join(lines) + ("\n" if final_newline and lines else "")
    return text.encode("utf-8")


class Clone:
    """One clone of `tmpl_imported`, and the documented functions called on
    it as REGISTER-WRITER, through `lanes_w_fx` (AT-LR006's fixture)."""

    def __init__(self, cluster, name: str) -> None:
        self.cluster, self.name = cluster, name
        self.db = Database(cluster, name)

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

    def stamp(self, minutes_ago: float) -> Tuple[str, str]:
        """The database's clock less `minutes_ago`: the line's UTC, as a line
        spells it, and `utc_ts`."""
        said = self.value(
            "SELECT to_char(t AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI\"Z\"') || '|' || t::text "
            f"FROM (SELECT clock_timestamp() - make_interval(secs => {minutes_ago * 60}) AS t) s;")
        utc, utc_ts = said.split("|")
        return utc, utc_ts

    def not_after(self, seconds: float = 60) -> str:
        return self.value(f"SELECT (clock_timestamp() + make_interval(secs => {seconds}))::text;")

    def file(self, path: str) -> Tuple[Optional[bool], List[str]]:
        """`files.final_newline` (None where there is no such file) and the lines."""
        said = self.json(
            f"SELECT json_build_object('nl', (SELECT final_newline FROM {REGISTER}.files WHERE path = '{path}'), "
            f"'lines', (SELECT coalesce(jsonb_agg(text ORDER BY line_no), '[]') FROM {REGISTER}.doc_lines "
            f"WHERE path = '{path}'));")
        return said["nl"], said["lines"]

    def open_takes(self, lane: str, slot_kind: str) -> List[List[str]]:
        out = self.value(f"SELECT coalesce(json_agg(json_build_array(repo_key, pr) ORDER BY line_id), '[]') "
                         f"FROM {REGISTER}.main_slots WHERE lane = '{lane}' AND slot_kind = '{slot_kind}';")
        return json.loads(out)

    def no_taker(self) -> None:
        """The cases' lines must meet no take of the template's own."""
        held = self.value(f"SELECT count(*) FROM {REGISTER}.main_slots WHERE repo_key IN "
                          f"('{KEY}', '{ALIAS}', '{OTHER_KEY}') OR repo_spellings && "
                          f"ARRAY['{KEY}', '{ALIAS}', '{OTHER_KEY}'];")
        assert held == "0", f"{IMPORTED} holds {held} open take(s) on {KEY}, which every case here writes"

    # -------------------------------------------------- the calls, as the writer
    def call(self, sql: str, **variables) -> subprocess.CompletedProcess:
        argv = [self.db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                "-v", "VERBOSITY=verbose", "-v", "SHOW_CONTEXT=never"]
        for name, value in variables.items():
            argv += ["-v", f"{name}={value}"]
        return subprocess.run(argv, input=sql, capture_output=True, text=True, timeout=60,
                              env=self.db.env(WRITER_LOGIN), check=False)

    def commit(self, entry: dict, *, base: Optional[int] = None, write_id: Optional[str] = None,
               generation: Optional[str] = None) -> Tuple[subprocess.CompletedProcess, str]:
        write_id = write_id or str(uuid.uuid4())
        proc = self.call(COMMIT_SQL, base=self.head() if base is None else base, wid=write_id,
                         client=self.client(), gen=generation or self.switch()["generation"],
                         entry=json.dumps(entry, ensure_ascii=False))
        return proc, write_id

    def committed(self, entry: dict, **options) -> int:
        proc, _ = self.commit(entry, **options)
        assert proc.returncode == 0, (
            f"commit_write as {WRITER_LOGIN} exited {proc.returncode}: {proc.stderr.strip()[-800:]}")
        return int(proc.stdout.strip())

    # -------------------------------------------------- entries
    def journal(self, kind: str, verb: str, lane: str, **extra) -> dict:
        row = {"kind": kind, "verb": verb, "lane": lane, "workstation": WS, "author": AUTHOR,
               "message": f"{verb} by {lane} (T223)"}
        row.update(extra)
        return row

    def appended(self, path: str, texts: Sequence[str], *, create: bool = False) -> Tuple[list, list, int]:
        """The edits and the files row of appending `texts` to `path`, and the
        first appended line's number."""
        final_newline, lines = (None, []) if create else self.file(path)
        edits = []
        if final_newline is None:
            edits.append({"ord": 1, "op": "create", "path": path})
            final_newline = True
        for text in texts:
            edits.append({"ord": len(edits) + 1, "op": "append", "path": path, "new_text": text})
        files = [{"path": path, "present": True, "sha256": sha256(rendered([*lines, *texts], final_newline)),
                  "final_newline": final_newline}]
        return edits, files, len(lines) + 1

    def append(self, lane: str, line: str, row: dict, *, verb: str = "append-line") -> dict:
        """A write entry: one line appended to `lanes/LANES.md`, and its row."""
        edits, files, line_no = self.appended(LANES_MD, [line])
        args = sha256(f"{lane}\0{verb}\0{line}".encode("utf-8"))
        return {"journal": self.journal("write", verb, lane, args_sha256=args),
                "not_after": self.not_after(), "edits": edits, "files": files,
                "register_lines": [dict(row, path=LANES_MD, line_no=line_no, raw=line, workstation=WS)]}

    def write(self, lane: str, line_row: Tuple[str, dict]) -> int:
        line, row = line_row
        return self.committed(self.append(lane, line, row))

    def to_primary(self, confirm: bool = True) -> int:
        """A `cutover` entry over the template's import, then `record_marker`:
        `primary`, the marker `present`. Returns the cutover's seq. With
        `confirm` False, no `record_marker`: the cutover is left unconfirmed,
        `primary` with the marker `adding`, which `switch_to_files` aborts."""
        sw = self.switch()
        assert (sw["mode"], sw["marker_state"]) == ("files", "absent"), sw
        head = self.head()
        last_import = int(self.value(f"SELECT coalesce(max(seq), -2) FROM {REGISTER}.journal WHERE kind = 'import';"))
        assert last_import == head >= 0, f"{IMPORTED}'s head {head} is not its import ({last_import})"
        edits, files, _ = self.appended(STORE, ["primary"])
        seq = self.committed({"journal": self.journal("cutover", "cutover", OPERATOR),
                              "not_after": self.not_after(), "edits": edits, "files": files})
        if not confirm:
            sw = self.switch()
            assert (sw["mode"], sw["marker_state"], sw["marker_seq"]) == ("primary", "adding", seq), sw
            return seq
        marked =self.call(MARKER_SQL, client=self.client(), seq=seq, commit=MARKER_COMMIT, ws=WS)
        assert (marked.returncode, marked.stdout.strip()) == (0, "present"), marked.stderr
        sw = self.switch()
        assert (sw["mode"], sw["marker_state"]) == ("primary", "present"), sw
        return seq

    def refused(self, entry: dict, code: str, detail: Optional[str], *says: str) -> List[str]:
        """The call ends with `code` and `detail`, and writes nothing."""
        before = self.state()
        proc, write_id = self.commit(entry)
        lines = proc.stderr.splitlines()
        assert proc.returncode == 3, f"exit {proc.returncode}, not 3: {proc.stderr.strip()}"
        assert lines and lines[0].startswith(f"ERROR:  {code}: "), lines
        if detail is not None:
            assert lines[1:2] == [f"DETAIL:  {detail}"], lines
        for text in says:
            assert text in lines[0], f"{text!r} is not in {lines[0]!r}"
        assert self.state() == before, "the refused call changed the register"
        assert self.value(f"SELECT count(*) FROM {REGISTER}.journal WHERE write_id = '{write_id}';") == "0"
        return lines


# ------------------------------------------------------------ the lines
def line(c: Clone, kind: Optional[str], lane: str, *, repo: str = KEY, key: Optional[str] = None,
         spellings: Optional[List[str]] = None, pr: Optional[int] = PR, age: Optional[float] = 0,
         stamp: Optional[str] = None, for_lane: Optional[str] = None,
         slot: Optional[Tuple[Optional[str], Optional[str]]] = None, text: Optional[str] = None) -> Tuple[str, dict]:
    """A LANES.md line of `kind` and its `register_lines` row. `age` is in
    minutes by the database's clock; None, a line with no UTC, or with
    `stamp`, a UTC that cannot be read."""
    utc, utc_ts = c.stamp(age) if age is not None else (stamp, None)
    tail = f" — {utc}" if utc else ""
    pr_part = f"PR #{pr} into {repo} main" if pr is not None else f"{repo} main"
    if text is None:
        if kind == "LANDING EXPIRED":
            names = f" for lane {for_lane}" if for_lane else ""
            text = f"{kind} — lane {lane} — {pr_part}{names}{tail}"
        elif kind == "LANDED":
            text = f"{kind} — lane {lane} — {pr_part} → 0123abc{tail}"
        else:
            text = f"{kind} — lane {lane} — {pr_part}{tail}"
    slot_role, slot_kind = slot if slot is not None else SLOTS[kind]
    row = {"kind": kind, "slot_role": slot_role, "slot_kind": slot_kind, "lane": lane, "repo": repo,
           "repo_key": key or repo, "repo_spellings": spellings, "pr": pr, "tip": None, "utc": utc,
           "utc_ts": utc_ts, "session": None, "for_lane": for_lane}
    return text, row


def landing(c: Clone, lane: str = L1, **options) -> Tuple[str, dict]:
    return line(c, "LANDING", lane, **options)


def hold(c: Clone, lane: str, **options) -> Tuple[str, dict]:
    return line(c, "HOLD", lane, pr=None, **options)


def expired(c: Clone, lane: str = L2, for_lane: str = L1, **options) -> Tuple[str, dict]:
    return line(c, "LANDING EXPIRED", lane, for_lane=for_lane, **options)


@pytest.fixture()
def clones(pg_cluster):
    """Clones of `tmpl_imported`, or of the template a case names (the act
    backstops clone `tmpl`; T252r), each the case's own, dropped at the end."""
    made: List[str] = []

    def clone(template: str = IMPORTED) -> Clone:
        found = pg_cluster.psql(f"SELECT datname FROM pg_database WHERE datname = '{template}';").stdout.split()
        assert found == [template], f"no {template} on the session cluster: lane 2's T227 builds it"
        name = f"t223_{next(_NAMES)}"
        pg_cluster.psql(f"CREATE DATABASE {name} TEMPLATE {template};")
        made.append(name)
        pg_cluster.psql(f"REVOKE ALL ON DATABASE {name} FROM PUBLIC;\n"
                        f"GRANT CONNECT ON DATABASE {name} TO {CONNECT_TO};\n")
        return Clone(pg_cluster, name)

    yield clone
    for name in made:
        pg_cluster.drop_database(name)


def primary(clones) -> Clone:
    c = clones()
    c.to_primary()
    c.no_taker()
    return c


# ------------------------------------------------------------ F13
def test_a_landing_expired_for_a_stale_landing_commits_and_frees_main_in_main_slots(clones):
    """[stale]: a stale LANDING still takes `main`, so L2's HOLD is refused
    `main-held`; L2's LANDING EXPIRED for L1 commits at the next seq, frees
    `main` in `main_slots` and holds `for_lane` L1; L2's HOLD then commits."""
    c = primary(clones)
    c.write(L1, landing(c, age=40))
    hold_line, hold_row = hold(c, L2)
    c.refused(c.append(L2, hold_line, hold_row), "LR005", "main-held", "(D18)")

    head = c.head()
    seq = c.write(L2, expired(c))
    assert (seq, c.head()) == (head + 1, head + 1)
    assert c.open_takes(L1, "landing") == []
    assert c.value(f"SELECT for_lane FROM {REGISTER}.register_lines WHERE seq = {seq};") == L1
    c.committed(c.append(L2, hold_line, hold_row))
    assert c.open_takes(L2, "hold") == [[KEY, None]]


def test_a_landing_expired_closes_only_the_holders_landings_for_that_pr_and_repository(clones):
    """[closes-only-its-own]: the release for L1's PR closes both of that
    PR's posts, as L1's LANDED would; L1's HOLD, its other PR's LANDING and
    L3's LANDING on another repository stay open, and no LANDED is written."""
    c = primary(clones)
    c.write(L1, hold(c, L1, age=50))
    c.write(L1, landing(c, age=50))
    c.write(L1, landing(c, age=40))
    c.write(L1, landing(c, pr=OTHER_PR, age=40))
    c.write(L3, landing(c, L3, repo=OTHER_KEY, age=40))
    head = c.head()

    c.write(L2, expired(c))
    assert c.open_takes(L1, "landing") == [[KEY, OTHER_PR]]
    assert c.open_takes(L1, "hold") == [[KEY, None]]
    assert c.open_takes(L3, "landing") == [[OTHER_KEY, PR]]
    assert c.value(f"SELECT count(*) FROM {REGISTER}.register_lines WHERE kind = 'LANDED' AND seq > {head};") == "0"


def test_the_holder_may_write_its_own_landing_expired(clones):
    """[holder-writes]: a close is matched by `coalesce(for_lane, lane)`, so
    L1's own LANDING EXPIRED, `for_lane` L1, commits and frees `main`."""
    c = primary(clones)
    c.write(L1, landing(c, age=40))
    seq = c.write(L1, expired(c, L1, for_lane=L1))
    assert seq == c.head()
    assert c.open_takes(L1, "landing") == []


def _imported_take(c: Clone) -> dict:
    """Test 7's imported LANDING whose UTC cannot be read, still open."""
    takes = c.json(f"SELECT coalesce(json_agg(json_build_object('lane', t.lane, 'pr', t.pr, 'key', t.repo_key, "
                   f"'spellings', t.repo_spellings, 'line_id', t.line_id) ORDER BY t.line_id), '[]') "
                   f"FROM {REGISTER}.register_lines t JOIN {REGISTER}.main_slots m ON m.line_id = t.line_id "
                   f"WHERE t.slot_role = 'take' AND t.slot_kind = 'landing' AND t.utc_ts IS NULL;")
    assert takes, f"{IMPORTED} holds no open LANDING whose UTC cannot be read (test 7's register; T227)"
    take = takes[-1]
    newer = c.value(f"SELECT count(*) FROM {REGISTER}.register_lines WHERE slot_role = 'take' "
                    f"AND slot_kind = 'landing' AND lower(lane) = lower('{take['lane']}') AND pr = {take['pr']} "
                    f"AND line_id > {take['line_id']};")
    assert newer == "0", f"a newer LANDING follows the imported one: {take}"
    return take


def _setup(c: Clone, case: str) -> Tuple[str, dict, str, Tuple[str, ...]]:
    """Each case's lines, then the LANDING EXPIRED it sends, its token and
    what its message says."""
    young = ("is too young (F13)", "its age by the database's clock is ")
    if case == "fresh":
        c.write(L1, landing(c, age=0))
        return (*expired(c), "expired-young", young)
    if case == "posted-again":
        c.write(L1, landing(c, age=40))
        c.write(L1, landing(c, age=10))
        return (*expired(c), "expired-young", young)
    if case in ("posted-again-two-spellings", "newest-keyed-another-way"):
        c.write(L1, landing(c, key=KEY, spellings=BOTH, age=40))
        c.write(L1, landing(c, repo=ALIAS, key=ALIAS, spellings=BOTH, age=10))
        if case == "posted-again-two-spellings":
            return (*expired(c, repo=ALIAS, key=ALIAS, spellings=BOTH), "expired-young", young)
        return (*expired(c, key=KEY, spellings=BOTH), "expired-none",
                (f"no open LANDING by {L1} for PR #{PR} under repo_key {KEY} (F13)",
                 f"its newest is keyed {ALIAS}"))
    if case == "unreadable-utc":
        take = _imported_take(c)
        text, row = expired(c, for_lane=take["lane"], pr=take["pr"], repo=take["key"], key=take["key"],
                            spellings=take["spellings"])
        return text, row, "expired-young", ("is too young (F13)",
                                            "is unknown, since its UTC cannot be read")
    if case == "wrong-lane":
        c.write(L1, landing(c, age=40))
        return (*expired(c, for_lane=L3), "expired-none",
                (f"no open LANDING by {L3} for PR #{PR} under repo_key {KEY} (F13)",))
    if case == "wrong-pr":
        c.write(L1, landing(c, age=40))
        return (*expired(c, pr=OTHER_PR), "expired-none",
                (f"no open LANDING by {L1} for PR #{OTHER_PR} under repo_key {KEY} (F13)",))
    if case == "other-spelling":
        c.write(L1, landing(c, key=KEY, spellings=BOTH, age=40))
        return (*expired(c, repo=ALIAS, key=ALIAS, spellings=BOTH), "expired-none",
                (f"under repo_key {ALIAS} (F13)", f"its newest is keyed {KEY}"))
    if case == "already-closed":
        c.write(L1, landing(c, age=40))
        c.write(L1, line(c, "LANDED", L1, age=20))
        return (*expired(c), "expired-closed", (f"is already closed, by a LANDED of {L1} (F13)",))
    if case == "closed-under-another-spelling":
        c.write(L1, landing(c, key=KEY, spellings=BOTH, age=40))
        c.write(L1, line(c, "LANDED", L1, repo=ALIAS, key=ALIAS, spellings=BOTH, age=20))
        return (*expired(c, key=KEY, spellings=BOTH), "expired-closed",
                (f"is already closed, by a LANDED of {L1} (F13)",))
    if case == "already-released":
        c.write(L1, landing(c, age=40))
        c.write(L2, expired(c))
        return (*expired(c), "expired-closed", (f"is already closed, by a LANDING EXPIRED of {L2} (F13)",))
    raise AssertionError(case)


@pytest.mark.parametrize("case", [
    "fresh", "posted-again", "posted-again-two-spellings", "unreadable-utc",
    "wrong-lane", "wrong-pr", "other-spelling", "newest-keyed-another-way",
    "already-closed", "closed-under-another-spelling", "already-released",
])
def test_a_landing_expired_that_names_no_stale_landing_is_lr005_and_writes_nothing(clones, case):
    """Each of F13's eleven: LR005, its reason's token (`expired-young`,
    `expired-none`, `expired-closed`) and nothing written."""
    c = primary(clones)
    text, row, token, says = _setup(c, case)
    lines = c.refused(c.append(L2, text, row), "LR005", token, *says)
    if case == "fresh":
        assert "unknown" not in lines[0], lines[0]


# ------------------------------------------------------------ U3
@pytest.mark.parametrize("case", ["hold", "landing", "bad-stamp", "behind-d18"])
def test_on_primary_a_take_with_no_readable_utc_is_lr005_take_no_utc_and_writes_nothing(clones, case):
    """On primary a take whose UTC cannot be read is LR005 `take-no-utc`,
    the message quoting its line; behind another lane's HOLD it is still
    `take-no-utc`, not `main-held`, since U3's test comes first."""
    c = primary(clones)
    if case == "behind-d18":
        c.write(L1, hold(c, L1, age=0))
    if case in ("hold", "behind-d18"):
        text, row = hold(c, L2, age=None)
        kind = "HOLD"
    else:
        text, row = landing(c, L2, age=None, stamp=BAD_STAMP if case == "bad-stamp" else None)
        kind = "LANDING"
    if case == "bad-stamp":
        assert BAD_STAMP in text and row["utc_ts"] is None
    c.refused(c.append(L2, text, row), "LR005", "take-no-utc",
              f"a {kind} take with no readable UTC (U3): {text}")


@pytest.mark.parametrize("case", ["hold-refresh", "no-kind", "import-at-files"])
def test_a_refresh_or_a_line_of_no_kind_with_no_utc_commits_and_a_take_with_none_loads_at_files(clones, case):
    """A `HOLD (refresh)` with no UTC takes nothing and a line of no kind is
    no take, so each commits on primary; at `files`, before the clone's
    cutover, an `import` carrying the takes with no UTC commits, each line
    loaded as it stands, since U3 binds only a write on primary."""
    if case != "import-at-files":
        c = primary(clones)
        kind = "HOLD (refresh)" if case == "hold-refresh" else None
        text = f"HOLD (refresh) — lane {L2} — {KEY} main" if kind else f"HOLD REQUESTED — lane {L2} — {KEY} main"
        text, row = line(c, kind, L2, pr=None, age=None, text=text)
        seq = c.write(L2, (text, row))
        said = c.json(f"SELECT json_build_array(kind, slot_role, utc_ts, mode) FROM {REGISTER}.register_lines "
                      f"WHERE seq = {seq};")
        assert said == [kind, None, None, "primary"], said
        return

    c = clones()
    sw = c.switch()
    assert (sw["mode"], sw["marker_state"]) == ("files", "absent"), sw
    takes = [hold(c, L2, age=None), landing(c, L2, age=None), landing(c, L3, age=None, stamp=BAD_STAMP)]
    edits, files, _ = c.appended(LANES_MD, [t for t, _ in takes], create=True)
    rows = [dict(row, path=LANES_MD, line_no=n, raw=text, workstation=WS)
            for n, (text, row) in enumerate(takes, start=1)]
    seq = c.committed({"journal": c.journal("import", "import", OPERATOR, git_commit=GIT_COMMIT, git_tree=GIT_TREE),
                       "not_after": c.not_after(), "edits": edits, "files": files, "register_lines": rows})
    said = c.json(f"SELECT json_agg(json_build_array(kind, slot_role, utc, utc_ts, mode, raw) ORDER BY line_id) "
                  f"FROM {REGISTER}.register_lines WHERE seq = {seq};")
    assert said == [[r["kind"], "take", r["utc"], None, "files", r["raw"]] for r in rows], said


# ------------------------------------------------------------ the table's checks
@pytest.mark.parametrize("case", ["for-lane-on-a-hold", "no-for-lane", "closes-a-hold"])
def test_the_for_lane_checks_refuse_a_for_lane_off_a_landing_expired_and_a_landing_expired_that_closes_no_landing(
        clones, case):
    """`register_lines`' CHECKs: `for_lane` on a line of another kind, a
    LANDING EXPIRED with none, and one that closes a HOLD are each 23514 at
    the insert, and the whole entry rolls back."""
    c = primary(clones)
    if case == "for-lane-on-a-hold":
        text, row = hold(c, L2)
        row["for_lane"] = L1
    elif case == "no-for-lane":
        text, row = expired(c, for_lane=None)
        row["for_lane"] = None
    else:
        c.write(L1, hold(c, L1, age=0))
        text, row = expired(c, pr=None, slot=("close", "hold"))
    c.refused(c.append(L2, text, row), "23514", None,
              'new row for relation "register_lines" violates check constraint')


# ============================================================ PHASE W: test 4, C10, D19 and 4.1 (T243)
#
# THE CLIENT'S WRITERS ON A REAL REGISTER (AT-4's fixture, TP:876-898). Each
# case's register is a clone of `tmpl` (T227), brought by AT-LR006's route, as
# T222f's cases bring theirs: an `import` entry at seq 0 holding the case's
# files (`Clone.import_files`), then `Clone.to_primary`'s `cutover` entry at
# seq 1 and `record_marker`, so the first write is seq 2 and the objects are
# free. The workstation (`Estate`):
#   * one configuration at `mode=primary`, naming the clone through T228's
#     `lanes_w_fx`, and one `XDG_STATE_HOME`, so every writer shares one
#     `lanes-index` state directory and one image cache, `register-images/`;
#   * T203's flipped copy of `lanes-index` beside `lanes-edit.sh`,
#     `repos.tsv` and `lane-start`;
#   * a bare origin at the register's files with `lanes/repos.tsv` beside
#     them, and one checkout per writer (a reading: AT-4 names one
#     configuration, and the writers' git fetches are kept off one index);
#   * beside each writer's checkout W, the own register checkout `<c>` of
#     each lane its write is made for, `<W>-lanes/<lane>`, a clone of W's
#     origin made with W (lane 3's (119); `write_lanes_of`, below);
#   * a fake `gh` that logs each call with its body (AT-D8's form);
#   * the test's own `PATH` behind it, every directory kept in its place,
#     with `psql`, `lanes-index` and every `pg_*` masked out (`_masked_path`);
#   * per writer, a `psql` directory of its own: a stamp wrapper, which logs
#     each call's start time, in front of T203's shim (section 3.2), so each
#     writer's arms, log and counters are its own;
#   * the start barrier: each writer is launched through a launcher that blocks
#     on a FIFO the test opens only once all N launchers wait (TP:886-888).
# The window W is the shim's `window` arm on `commit_write`, the attempt's
# second call (TP:889-893). Lines are written by the client's own verbs.
#
# They FAIL UNTIL lane 1's T107 (L1-A6), lane 4's attempt loop on primary
# (L4-B3) and `claim`'s register seq (L4-B8), lane 1's T302 (the image cache),
# and lane 2's T227 (`tmpl`) and T228 (`lanes_w_fx`) land. Without PostgreSQL
# 16 each skips.

EM, ARROW, DOT = chr(0x2014), chr(0x2192), chr(0x00B7)
W_TEMPLATE = "tmpl"
W_WS = "Eagle"
REPOS_PATH = "lanes/repos.tsv"
#: Test 4's lanes: ten burst writers, and the pairs of C10, D19 and (a)-(h).
BURST = [f"repoW{k:02d}-1" for k in range(1, 11)]
LA, LB, LC = "repoA-1", "repoB-1", "repoC-1"
W_LANES = [LA, LB, LC, *BURST]
#: Object O, and X: X's repository becomes an alias of O's at T1 (C10, D19).
ALIAS_REPO = "oldname/r9"
OBJ = f"{KEY}#41"
OBJ_X = f"{ALIAS_REPO}#41"
REPOS_T0 = f"# alias\towner/repo\n{ALIAS}\t{KEY}\n"
REPOS_T1 = REPOS_T0 + f"{ALIAS_REPO}\t{KEY}\n"
#: The busy text's words (D7; P231-233) and the default's (AT-4 (h)).
BUSY_WORDS = ("register busy", "nothing", "retry")
D7_S, TWICE_D7_S = 30, 60
#: AT-4 (c)'s measuring burst (T243u): a deadline none of its writers is
#: meant to reach, four times D7's and inside `Writer.wait`'s 150 s, so all
#: ten stay in the load until each commits, which the case checks by their
#: exit codes before it takes the p95 (T243w); and the factor of the runner's
#: own D7, `max(30 s, 10 x the runner's attempt p95)` (Y:5906; tasks:2337 at
#: `8e8d1b49`).
MEASURE_DEADLINE_S, D7_PER_P95 = 120, 10
UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
SEQ_SAID = re.compile(r"register seq ([0-9]+)")


def session_of(lane: str) -> str:
    k = int(hashlib.sha256(lane.encode()).hexdigest()[:8], 16)
    return f"{k:08x}-0243-4000-8000-{k:012x}"


def w_row(lane: str) -> str:
    return (f"| `{lane}` | harness `{session_of(lane)}` | {W_WS} / test / brett | 2026-05-01T00:00Z "
            f"| none | handoffs/{lane}.md | LIVE {DOT} 2026-05-01T00:00:00Z {DOT} working |")


def bound_line(lane: str) -> str:
    """A `STARTED` line binding `lane` on this workstation, as `lane-start`
    writes one with Amendment 18(a)'s sub-fields: host `eagle` (the estate's
    `LANES_HOST`), no container, and a window with its `@id`. `request-handoff`
    asks only a bound lane: one whose last lane-kind line is none at all is
    FREE, exit 8 (`lanes-edit.sh`'s `request-handoff` arm; T243g)."""
    k = W_LANES.index(lane) + 1 if lane in W_LANES else 99
    return (f"STARTED {EM} lane {lane}, session {session_of(lane)}@{W_WS}, 2026-05-01T00:00:00Z, "
            f"lane:{lane} {ARROW} home {KEY}; dir /work/{lane}; profile team-01a; window t243:{k} @{k}; "
            f"host eagle; container none; os linux\n")


def estate_files(lanes: Sequence[str], bound: Sequence[str] = ()) -> Dict[str, str]:
    """The register's render set: a row per lane, an empty event list, the
    aliases table and a log per lane; each lane of `bound` is bound, its log
    holding `bound_line` (T243g)."""
    table = "\n".join([f"# LANES.md {EM} test 4's register (T243)", "",
                       "| lane | session id | workstation / env / user | started (UTC) "
                       "| objects owned | handoff path | state |",
                       "|---|---|---|---|---|---|---|", *(w_row(lane) for lane in lanes), ""])
    files = {LANES_MD: table, "lanes/aliases.tsv": "# old\tnew\tutc\n",
             "lanes/log/README.md": "# the object logs\n"}
    for lane in lanes:
        files[f"lanes/log/{lane}.md"] = (f"# lane {lane} {EM} object log (Amendment 7)\n"
                                          + (bound_line(lane) if lane in bound else ""))
    return files


def import_files(c: "Clone", files: Dict[str, str]) -> int:
    """AT-LR006's first step on a clone of `tmpl` (T222f's `Clone.imported`):
    one `import` entry creating `files`, each with its last LF."""
    sw = c.switch()
    assert (sw["mode"], sw["marker_state"], c.head()) == ("files", "absent", -1), (
        f"a clone of {W_TEMPLATE} is not at files, marker absent, with an empty journal: {sw}, head {c.head()}")
    edits, rows = [], []
    for path in sorted(p for p in files if p != "lanes/log/README.md"):
        lines = files[path].rstrip("\n").split("\n")
        edits.append({"ord": len(edits) + 1, "op": "create", "path": path})
        edits += [{"ord": len(edits) + 1 + k, "op": "append", "path": path, "new_text": text}
                  for k, text in enumerate(lines)]
        rows.append({"path": path, "present": True, "final_newline": True,
                     "sha256": sha256(rendered(lines, True))})
    return c.committed({"journal": c.journal("import", "import", OPERATOR, git_commit=GIT_COMMIT,
                                             git_tree=GIT_TREE),
                        "not_after": c.not_after(), "edits": edits, "files": rows})


def run_git(cwd, *args: str, env: dict) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env=env,
                          check=False)
    assert proc.returncode == 0, f"git {' '.join(args)} in {cwd}: {proc.stderr}{proc.stdout}"
    return proc.stdout


#: `_masked_path`'s names: those the filters dropped a directory for holding.
#: Every name that starts `pg_` is masked as well.
PATH_MASKED = ("psql", "lanes-index")
_MIRRORS: Dict[Tuple[str, Tuple[str, ...]], str] = {}
_MIRROR_ROOT: List[str] = []
_MIRRORS_LOCK = threading.Lock()


def _masked_path(path: str, spared: Optional[Dict[str, Sequence[str]]] = None) -> str:
    """`path` with every directory kept, in its place, and each one that
    holds `psql`, `lanes-index` or a `pg_*` name swapped for a mirror of it
    without them: a directory of links, one per other entry, each to the
    entry's absolute path. A directory that holds none of them is kept as it
    is, and an empty entry is left out, as before.

    Why not drop the directory: on a GitHub runner, `postgresql-16`'s client
    package puts `psql` and its `pg_*` wrappers in `/usr/bin`, beside `git`
    and `bash`, and `/bin` is a link to `/usr/bin`. Dropping each directory
    that held a `psql` dropped `git` and `bash` with it, and the case's own
    `subprocess.run` failed (lane 1's census of round 4, #165 6807454856).

    `spared` maps a directory, as `path` names it, to the masked names it
    keeps: a call site's own exception. Each mirror is built once per
    process, keyed by the directory's real path and the names it masks,
    under one `l2-pathmask-` temporary directory that an `atexit` handler
    removes."""
    kept = []
    for where in path.split(os.pathsep):
        if not where:
            continue
        masked = tuple(sorted(set(PATH_MASKED) - set((spared or {}).get(where, ()))))
        try:
            names = os.listdir(where)
        except OSError:
            names = []
        if any(name in masked or name.startswith("pg_") for name in names):
            where = _path_mirror(os.path.realpath(where), masked)
        kept.append(where)
    return os.pathsep.join(kept)


def _path_mirror(real: str, masked: Tuple[str, ...]) -> str:
    """The mirror of the directory `real` less `masked` and every `pg_*`
    name, made on the first call for that pair."""
    with _MIRRORS_LOCK:
        if (real, masked) not in _MIRRORS:
            if not _MIRROR_ROOT:
                _MIRROR_ROOT.append(tempfile.mkdtemp(prefix="l2-pathmask-"))
                atexit.register(shutil.rmtree, _MIRROR_ROOT[0], ignore_errors=True)
            mirror = os.path.join(_MIRROR_ROOT[0], str(len(_MIRRORS) + 1))
            os.mkdir(mirror)
            for name in sorted(os.listdir(real)):
                if name not in masked and not name.startswith("pg_"):
                    os.symlink(os.path.join(real, name), os.path.join(mirror, name))
            _MIRRORS[(real, masked)] = mirror
        return _MIRRORS[(real, masked)]


_STAMP = r'''#!/usr/bin/env python3
# T243's stamp: each psql call's start time and argv, then T203's shim.
# Where `tee` is in this directory (a burst's writer, T243m), a forked child
# also passes the call's stderr through, and at its end logs to `tee.log`,
# keyed by the start time, the SQLSTATE of each `ERROR:` line (the register's
# VERBOSITY=verbose) and the time the call's stderr closed. The shim is still
# this process, so its pid and its exit are the call's, as before.
import json, os, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
start = time.time()
with open(os.path.join(HERE, "stamps.log"), "a", encoding="utf-8") as log:
    log.write(json.dumps({"t": start, "argv": sys.argv[1:]}) + "\n")
if sys.argv[1:] != ["--version"] and os.path.exists(os.path.join(HERE, "tee")):
    rd, wr = os.pipe()
    if os.fork() == 0:
        os.close(wr)
        os.close(0)
        os.close(1)
        seen, out = b"", True
        while True:
            chunk = os.read(rd, 65536)
            if not chunk:
                break
            seen += chunk
            view = memoryview(chunk)
            while out and view:
                try:
                    view = view[os.write(2, view):]
                except OSError:
                    out = False
        states = re.findall(r"^ERROR:\s+([0-9A-Z]{5}):", seen.decode("utf-8", "replace"), re.M)
        with open(os.path.join(HERE, "tee.log"), "a", encoding="utf-8") as log:
            log.write(json.dumps({"t": start, "end": time.time(), "states": states}) + "\n")
        os._exit(0)
    os.close(rd)
    os.dup2(wr, 2)
    os.close(wr)
shim = os.path.join(HERE, "shim", "psql")
os.execv(shim, [shim] + sys.argv[1:])
'''

_LAUNCHER = r'''#!/usr/bin/env python3
# T243's start barrier: wait on the FIFO, then become the writer.
import os, sys
ready, fifo, argv = sys.argv[1], sys.argv[2], sys.argv[3:]
open(ready, "w").close()
fd = os.open(fifo, os.O_RDONLY)
open(ready + ".go", "w").close()
os.close(fd)
os.execvp(argv[0], argv)
'''

_GH = r'''#!/usr/bin/env python3
# AT-D8's fake gh (T243): each call logged with its body; nothing answered.
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
body = sys.stdin.read() if not sys.stdin.isatty() else ""
with open(os.path.join(HERE, "gh.log"), "a", encoding="utf-8") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "stdin": body}) + "\n")
'''


class Barrier:
    """TP:886-888: N launchers wait on one FIFO, released together."""

    def __init__(self, root: Path, count: int) -> None:
        self.fifo, self.ready, self.count = root / "start.fifo", root / "ready", count
        os.mkfifo(str(self.fifo))
        self.ready.mkdir()

    def _seen(self, suffix: str) -> int:
        return sum(1 for p in self.ready.iterdir() if p.name.endswith(".go") == (suffix == ".go"))

    def release(self) -> float:
        deadline = time.monotonic() + 60
        while self._seen("") < self.count:
            assert time.monotonic() < deadline, f"only {self._seen('')} of {self.count} launchers wait"
            time.sleep(0.05)
        fd = os.open(str(self.fifo), os.O_WRONLY)
        released = time.monotonic()
        while self._seen(".go") < self.count:
            assert time.monotonic() < deadline + 30, f"only {self._seen('.go')} launchers passed"
            time.sleep(0.01)
        os.close(fd)
        return released


class Writer:
    """One `lanes-edit.sh` run: its psql directory, and its outcome."""

    def __init__(self, name: str, lane: str, proc: subprocess.Popen, psql_dir: Path) -> None:
        self.name, self.lane, self.proc, self.psql_dir = name, lane, proc, psql_dir
        self.started, self.ended = time.monotonic(), None
        self.out = self.err = ""
        self._thread = threading.Thread(target=self._wait, daemon=True)
        self._thread.start()

    def _wait(self) -> None:
        self.out, self.err = self.proc.communicate()
        self.ended = time.monotonic()

    def wait(self, timeout: float = 150) -> int:
        self._thread.join(timeout)
        assert not self._thread.is_alive(), f"{self.name} ({self.lane}) did not end in {timeout} s"
        return self.proc.returncode

    @property
    def code(self) -> int:
        return self.proc.returncode

    def _jsonl(self, name: str) -> List[dict]:
        """`name`'s lines, each a JSON object. A last line with no newline yet
        is one still being written, as by a detached render's call, which
        logs under a lock this read does not take: it is left out, never half
        read (lane 2's RV20, NIT 19; T243s)."""
        path = self.psql_dir / name
        if not path.exists():
            return []
        data = path.read_bytes()
        data = data[:data.rfind(b"\n") + 1]
        return [json.loads(line) for line in data.decode("utf-8").splitlines() if line]

    def calls(self) -> List[dict]:
        """The shim's calls that carry a request, in order."""
        return [e for e in self._jsonl("shim/" + PSQL_SHIM_LOG) if e.get("kind") != "version"]

    def commit_calls(self) -> List[dict]:
        return [e for e in self.calls() if "commit_write" in (e.get("stdin") or "")]

    def snapshot_calls(self) -> List[dict]:
        return [e for e in self.calls() if "commit_write" not in (e.get("stdin") or "")
                and "find_write" not in (e.get("stdin") or "")]

    def ends(self) -> Dict[int, dict]:
        return {e["call"]: e for e in self._jsonl("shim/" + PSQL_SHIM_ENDS) if "call" in e}

    def stamps(self) -> List[dict]:
        """Each request's start time, paired in order with the shim's log."""
        times = [s["t"] for s in self._jsonl("stamps.log") if s["argv"] != ["--version"]]
        return [dict(call, t=t) for call, t in zip(self.calls(), times)]

    def write_ids(self) -> List[str]:
        """Each commit call's write id, `commit_write`'s second argument."""
        found = []
        for call in self.commit_calls():
            m = re.search(r"commit_write\(\s*-?[0-9]+\s*,\s*'(" + UUID_RE + ")'", call.get("stdin") or "")
            assert m, f"{self.name}'s commit call carries no write id: {(call.get('stdin') or '')[:300]}"
            found.append(m.group(1))
        return found

    def seq_said(self) -> Optional[int]:
        """The seq `claim` names in its line, `lane <L> now holds <obj>
        (register seq <s>)`, which it prints by `note`, on stderr, where files
        mode printed the log commit's sha (T421; Y@a6497d00:266; T243h)."""
        m = SEQ_SAID.search(self.err)
        return int(m.group(1)) if m else None


# EACH WRITE LANE'S OWN REGISTER CHECKOUT, `<c>` (lane 3, #165 6813027223,
# batch g Q119; T241e's `WRITE_LANES` in `test_sql_register_writes.py` is the
# model). On primary a write reads its author, its pending hand edits and its
# `repos.tsv` from the checkout of the lane it is made for, `<W>-lanes/<lane>`
# (`lanes-edit.sh`'s `lane_checkout_path`, `R-merge20:lanes-edit.sh:18342`),
# W being the real path of `workspace.yaml`'s `path:`. Where that is not there
# the write refuses with 2, or 64 for `request-handoff`, sending nothing, since
# a clone there would be D12's fetch (B15 tasks:1154; T415's `pw_checkout`).
# So the estates make it themselves, because `lane-start` makes it only under
# `LANES_ROUTE_WRITES=1` with neither `LANES_REPO` nor `LANES_FILE` set
# (lane 3, #165 6841265575; `dfc4ce4c:lane-start:1209-1210`): beside each
# writer's W, a clone of W's own origin, for each lane `write_lanes_of` names.
# A W kept behind a push (`mirror_at_t0`: AT-C10, AT-D19) keeps `<c>` behind
# it too, at the same commit, and a W cloned before a push has `<c>` cloned
# with it. Until T415 nothing reads `<c>`: these estates set no
# `LANES_ROUTE_WRITES`, so each write goes through `LANES_REPO` as before.
def write_lanes_of(argv: Sequence[str], lane: Optional[str]) -> List[str]:
    """The lanes a run of `lanes-edit.sh <argv>` writes for, `lane` being its
    `LANES_LANE`: `write_lane_of`'s answer (`R-merge20:lanes-edit.sh:18553`),
    as T415's `pw_checkout` takes it, so a dry run's lane is included. Empty
    for a run that is no write (a read, `act-begin`), and for an
    `append-line` with no `LANES_LANE`, whose lane is in its text (every run
    here sets `LANES_LANE`). `rename-lane` gives both names, the old one
    first: `canon_lane` reads the old as the new once the rename is known.
    `start-record <L> ...` names its lane first, as `write-handoff` does
    (T427's arm, `f9e1449c:lanes-edit.sh:27941-27945`); the arm's own
    refusals, a `LANES_LANE` that is not `<L>`, a `LANES_SESSION` that is no
    transcript uuid and an `--add-row` with no row, come before any clone,
    so a checkout made for them changes nothing (lane 3, #165 6859307928;
    T243t)."""
    verb, args = (argv[0], [str(a) for a in argv[1:]]) if argv else ("", [])
    first = args[0] if args else ""
    if verb in ("set-row-state", "replace-in-row", "append-session-id", "request-handoff"):
        return [first] if first else []
    if verb in ("write-handoff", "start-record"):
        return [first] if first and not first.startswith("-") else []
    if verb == "rename-lane":
        names, words = [], iter(args)
        for word in words:
            if word == "--why":
                next(words, None)
            elif not word.startswith("-"):
                names.append(word)
        return names[:2]
    if verb == "add-row":
        m = re.match(r"[^`]*`([^`]*)`", first)
        return [m.group(1)] if m and m.group(1) else []
    if verb == "retire-rows":
        for k, word in enumerate(args):
            if word == "--writer" and k + 1 < len(args):
                return [args[k + 1]]
            if word.startswith("--writer="):
                return [word.split("=", 1)[1]]
    if verb in ("append-line", "commit", "log", "claim", "release", "retire-rows", "archive-rows",
                "migrate-state-cells"):
        return [lane] if lane else []
    return []


class Estate:
    """Test 4's workstation over one clone at `primary` (see the section's
    head)."""

    def __init__(self, root: Path, c: Clone, lanes: Sequence[str] = W_LANES,
                 repos: str = REPOS_T0, aliases: str = "", confirmed: bool = True,
                 bound: Sequence[str] = (LC,)) -> None:
        self.root, self.c = root, c
        # LANE C IS BOUND (T243g; lane 4's triage, #165 6833813092): every
        # `request-handoff` here asks it, and a FREE lane is refused with 8
        # before any write. The other lanes keep logs with no lane-kind line.
        self.files = estate_files(lanes, bound)
        self.files["lanes/aliases.tsv"] += aliases
        self.lanes = list(lanes)
        import_files(c, self.files)
        # `confirmed` False leaves the cutover unconfirmed, the marker `adding` (T233's [switch-at-files]).
        assert c.to_primary(confirmed) == 1, "test 4's cutover is not at seq 1 (AT-4's fixture)"
        home = root / "home"
        (home / ".agents").mkdir(parents=True)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("GIT_", "PG", "LANES_", "TMUX", "RULE6_", "FAKE_PSQL", "CLAUDE_",
                                    "PROJECTS_ROOT", "XDG_"))}
        env.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME="T243 estate", GIT_AUTHOR_EMAIL="t243@example.invalid",
                   GIT_COMMITTER_NAME="T243 estate", GIT_COMMITTER_EMAIL="t243@example.invalid",
                   LC_ALL="C")
        self.env = env
        self.origin = root / "origin.git"
        run_git(root, "init", "-q", "--bare", "-b", "main", str(self.origin), env=env)
        seed = root / "seed"
        run_git(root, "clone", "-q", str(self.origin), str(seed), env=env)
        for path, text in {**self.files, REPOS_PATH: repos}.items():
            (seed / path).parent.mkdir(parents=True, exist_ok=True)
            (seed / path).write_bytes(text.encode("utf-8"))
        run_git(seed, "add", "-A", env=env)
        run_git(seed, "commit", "-q", "-m", "T0: test 4's register", env=env)
        run_git(seed, "push", "-q", "origin", "main", env=env)
        self.seed = seed
        self.bindir = root / "bin"
        flipped_copy(LANES_INDEX, self.bindir, True)
        for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
            shutil.copy2(str(REPO / name), str(self.bindir / name))
        self.lanes_edit = self.bindir / "lanes-edit.sh"
        conf = root / "lanes-index.conf"
        conf.write_text(f"mode=primary\nregister_url={c.db.url(WRITER_LOGIN)}\n"
                        f"reader_url={c.db.url()}\n", encoding="utf-8")
        conf.chmod(0o600)
        self.gh_dir = root / "gh"
        self.gh_dir.mkdir()
        (self.gh_dir / "gh").write_text(_GH, encoding="utf-8")
        (self.gh_dir / "gh").chmod(0o755)
        (self.gh_dir / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (self.gh_dir / "tmux").chmod(0o755)
        self.launcher = root / "launch.py"
        self.launcher.write_text(_LAUNCHER, encoding="utf-8")
        self.state = root / "state"
        for d in ("state", "config", "tmp"):
            (root / d).mkdir(exist_ok=True)
        path = _masked_path(env.get("PATH", ""))
        env.update(TMPDIR=str(root / "tmp"), XDG_STATE_HOME=str(self.state),
                   XDG_CONFIG_HOME=str(root / "config"), CLAUDE_CONFIG_DIR=str(home / ".claude"),
                   LANES_WORKSTATION=W_WS, LANES_HOST="eagle", LANES_OS="linux",
                   LANES_CONTAINER="none", LANES_IN_CONTAINER="0", LANES_INDEX_CONFIG=str(conf),
                   PATH=str(self.gh_dir) + os.pathsep + path)
        self._n = itertools.count(1)
        self.writers: List[Writer] = []

    # -------------------------------------------------- the workstation's parts
    def checkout(self, name: str, origin: Optional[Path] = None,
                 lanes: Sequence[str] = ()) -> Tuple[Path, Path]:
        """A clone of the origin, and the protocol root naming it; and, made
        with it, each of `lanes`' own register checkouts beside it
        (`lane_checkout`)."""
        where = self.root / f"co-{name}"
        run_git(self.root, "clone", "-q", str(origin or self.origin), str(where), env=self.env)
        for lane in dict.fromkeys(lanes):
            self.lane_checkout(where, lane, origin)
        agents = self.root / f"agents-{name}"
        agents.mkdir()
        (agents / "workspace.yaml").write_text(f"repository: {origin or self.origin}\npath: {where}\n",
                                               encoding="utf-8")
        return where, agents

    def canon(self, lane: str) -> str:
        """`lane` as `canon_lane` answers it over this estate's rows and alias
        lines: a row wins at every hop, the last alias line for a name wins,
        names compare in lower case, a cycle answers the typed name, and a
        walk that meets no row answers its last hop. The rows are those the
        estate was made with."""
        rows = {name.lower() for name in self.lanes}
        hops: Dict[str, str] = {}
        for line in self.files["lanes/aliases.tsv"].splitlines():
            parts = line.split("\t")
            if line.startswith("#") or len(parts) < 2:
                continue
            hops[parts[0].lower()] = parts[1]
        here, seen = lane, {lane.lower()}
        while here.lower() not in rows and here.lower() in hops:
            here = hops[here.lower()]
            if here.lower() in seen:
                return lane
            seen.add(here.lower())
        return here

    def write_lanes(self, argv: Sequence[str], lane: Optional[str]) -> List[str]:
        """`write_lanes_of`'s lanes, each followed by its `canon` name: T415's
        `pw_checkout` runs `canon_lane` first and takes `<W>-lanes/<canon>`,
        so a write for a name with no row of its own, such as `add-row` for a
        name on an alias walk, needs its canonical lane's `<c>` (lane 4's
        triage, #165 6833813092, TRIAGE-W13b o9; T243j). The typed name's
        `<c>` is kept too."""
        return list(dict.fromkeys(name for typed in write_lanes_of(argv, lane)
                                  for name in (typed, self.canon(typed))))

    def lane_checkout(self, where: Path, lane: str, origin: Optional[Path] = None) -> Path:
        """`<c>`, lane `lane`'s own register checkout beside the checkout
        `where`, which `workspace.yaml` names as W: `<W>-lanes/<lane>`, W
        being `where`'s real path, as `lane_checkout_path` puts it
        (Amendment 23 S1). A clone of W's own origin, as `lane-checkout
        <lane> --create` makes one, so it is at W's commit (lane 3's (119);
        see `write_lanes_of`)."""
        real = Path(os.path.realpath(where))
        target = real.parent / f"{real.name}-lanes" / lane
        target.parent.mkdir(parents=True, exist_ok=True)
        run_git(target.parent, "clone", "-q", str(origin or self.origin), str(target), env=self.env)
        return target

    def psql_dir(self, name: str, arms: Sequence[dict] = ()) -> Path:
        where = self.root / f"psql-{name}"
        (where / "shim").mkdir(parents=True)
        (where / "psql").write_text(_STAMP, encoding="utf-8")
        (where / "psql").chmod(0o755)
        (where / "shim" / "psql").write_text(PSQL_SHIM, encoding="utf-8")
        (where / "shim" / "psql").chmod(0o755)
        (where / "shim" / PSQL_SHIM_CONTROL).write_text(
            json.dumps({"psql": self.c.db.psql_bin, "arms": list(arms)}), encoding="utf-8")
        return where

    def push_alias(self) -> None:
        """T1: a person's commit adding X's repository as an alias of O's,
        pushed by a third clone (AT-C10's fixture)."""
        (self.seed / REPOS_PATH).write_text(REPOS_T1, encoding="utf-8")
        run_git(self.seed, "commit", "-q", "-am", "T1: alias oldname/r9 for opensoft/r9", env=self.env)
        run_git(self.seed, "push", "-q", "origin", "main", env=self.env)

    def mirror_at_t0(self) -> Path:
        """A second origin frozen at T0, for a clone kept behind the alias."""
        frozen = self.root / "origin-t0.git"
        run_git(self.root, "clone", "-q", "--bare", str(self.origin), str(frozen), env=self.env)
        return frozen

    # -------------------------------------------------- running writers
    def launch(self, lane: str, argv: Sequence[str], arms: Sequence[dict] = (), extra: dict = None,
               barrier: Optional[Barrier] = None, origin: Optional[Path] = None,
               first: Sequence[Path] = (), script: Optional[Path] = None) -> Writer:
        name = f"{next(self._n):02d}-{lane}"
        given = (extra or {}).get("LANES_LANE", lane)
        where, agents = self.checkout(name, origin, self.write_lanes(argv, given))
        psql = self.psql_dir(name, arms)
        env = dict(self.env)
        env.update(LANES_LANE=lane, LANES_SESSION=session_of(lane), LANES_REPO=str(where),
                   AGENT_PROTOCOL_ROOT=str(agents),
                   PATH=os.pathsep.join([*map(str, first), str(psql), self.env["PATH"]]))
        env.update(extra or {})
        command = ["bash", str(script or self.lanes_edit), *argv]
        if barrier is not None:
            command = [sys.executable, "-I", str(self.launcher), str(barrier.ready / name),
                       str(barrier.fifo), *command]
        proc = subprocess.Popen(command, cwd=str(where), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                                errors="replace", start_new_session=True)
        writer = Writer(name, lane, proc, psql)
        self.writers.append(writer)
        return writer

    def run(self, lane: str, argv: Sequence[str], **options) -> Writer:
        writer = self.launch(lane, argv, **options)
        writer.wait()
        return writer

    def gh_calls(self) -> List[dict]:
        log = self.gh_dir / "gh.log"
        return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] if log.exists() else []

    # -------------------------------------------------- the register's reads
    def rows(self, query: str) -> list:
        return self.c.json(f"SELECT coalesce(json_agg(t), '[]'::json) FROM ({query}) t;")

    def journal_after(self, seq: int = 1) -> list:
        return self.rows(f"SELECT seq, write_id::text AS write_id, verb, lane FROM {REGISTER}.journal "
                         f"WHERE seq > {seq} ORDER BY seq")

    def has_write(self, write_id: str) -> bool:
        return self.c.value(f"SELECT count(*) FROM {REGISTER}.journal WHERE write_id = '{write_id}';") != "0"

    def claimed(self, *objects: str) -> list:
        """The live `CLAIMED` holds on `objects`, (object, lane)."""
        names = ", ".join(f"'{o}'" for o in objects)
        return [(r["object"], r["lane"]) for r in self.rows(
            f"SELECT object, lane FROM {REGISTER}.object_holds WHERE object IN ({names}) "
            f"AND verb = 'CLAIMED' AND superseded_by IS NULL ORDER BY object, lane")]

    def log_lines(self, verb: str, obj: str) -> int:
        return int(self.c.value(f"SELECT count(*) FROM {REGISTER}.log_lines WHERE verb = '{verb}' "
                                f"AND object = '{obj}';"))

    def utc(self, minutes_ago: float = 0) -> str:
        return self.c.value("SELECT to_char((clock_timestamp() - make_interval(secs => "
                            f"{minutes_ago * 60})) AT TIME ZONE 'UTC', "
                            "'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"');")

    def open_slots(self, lane: str) -> List[List]:
        return [[r["slot_kind"], r["repo_key"], r["pr"]] for r in self.rows(
            f"SELECT slot_kind, repo_key, pr FROM {REGISTER}.main_slots WHERE lane = '{lane}' "
            "ORDER BY line_id")]

    def hold_row_locked(self) -> subprocess.Popen:
        """The test's admin session holding the head row `FOR UPDATE` in an
        open transaction, as AT-D9's F3 row does."""
        admin = self.c.db.session(appname="t243-admin")
        admin.stdin.write(f"BEGIN;\nSELECT seq FROM {REGISTER}.register_head FOR UPDATE;\n")
        admin.stdin.flush()
        said = admin.stdout.readline().strip()
        assert said.isdigit(), f"the admin session did not lock the head row: {said!r}"
        return admin

    @staticmethod
    def unlock(admin: subprocess.Popen) -> None:
        admin.stdin.write("ROLLBACK;\n")
        admin.stdin.close()
        admin.wait(timeout=30)

    def waits_on_lock(self, write_id: str) -> bool:
        """D19's barrier: the backend whose query carries `write_id` waits on
        a lock, polled at 0.1 s steps under one 1.5 s ceiling."""
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if self.c.value("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' "
                            f"AND query LIKE '%{write_id}%';") != "0":
                return True
            time.sleep(0.1)
        return False


@pytest.fixture()
def estates(pg_cluster, tmp_path):
    """Test 4's estates, each on a clone of `tmpl` of its own."""
    made: List[str] = []
    alive: List[Estate] = []

    def make(**options) -> Estate:
        name = f"t243_{next(_NAMES)}"
        pg_cluster.psql(f"CREATE DATABASE {name} TEMPLATE {W_TEMPLATE};")
        made.append(name)
        found = pg_cluster.psql(f"SELECT to_regclass('{REGISTER}.register_head') IS NOT NULL;", dbname=name)
        assert found.stdout.strip() == "t", (
            f"{W_TEMPLATE} holds no {REGISTER} schema: lane 2's T227 builds it by the bootstrap")
        pg_cluster.psql(f"REVOKE ALL ON DATABASE {name} FROM PUBLIC;\n"
                        f"GRANT CONNECT ON DATABASE {name} TO {CONNECT_TO};\n")
        root = tmp_path / f"estate-{len(made)}"
        root.mkdir()
        alive.append(Estate(root, Clone(pg_cluster, name), **options))
        return alive[-1]

    yield make
    for e in alive:
        for w in e.writers:
            if w.ended is None and w.proc.poll() is None:
                os.killpg(w.proc.pid, 9)
    for name in made:
        pg_cluster.drop_database(name)


def hold_point(fifo: Path, writer: Writer, timeout: float = 90):
    """`fifo` opened for writing once `writer`'s call is held on it (the
    shim's `hold`), bounded: a writer that never reaches the call fails the
    case and never hangs it. Closing the handle lets the call go."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return os.fdopen(os.open(str(fifo), os.O_WRONLY | os.O_NONBLOCK), "wb")
        except OSError as error:
            if error.errno != errno.ENXIO:
                raise
        assert writer.ended is None, (
            f"{writer.name} exited {writer.code} before its commit call was held: {writer.err[-400:]}")
        assert time.monotonic() < deadline, f"{writer.name}'s commit call was not held in {timeout} s"
        time.sleep(0.05)


CLIENT = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                            reason="the lane tooling is bash over git")
WINDOW = {"mode": "window", "match": "commit_write", "ms": 200}


def claim(obj: str, *more: str) -> List[str]:
    return ["claim", obj, "--home", KEY, *more]


def burst(e: Estate, objects: Sequence[str], window_ms: int, extra: dict = None,
          node: Optional[pytest.Item] = None, name: str = "burst",
          wait_s: float = 150) -> Tuple[List[Writer], float]:
    """Writers on `objects`, one lane each, released together; returns them,
    and the drain from the release to the last exit. Before its caller
    asserts anything, it records the drain and each writer's attempts,
    counted as snapshot calls in the shim's log, and its seconds from the
    release to its exit, never asserted (TP:3783-3787 at `0c3750a5`; lane 3,
    #165 6838735040; T243l): `record(name, node, ...)`. Beside them, for
    lane 1's two points (#165 6840891258; T243m), also never asserted: each
    writer's calls in order with their exits, its commits' losses by
    SQLSTATE, and its commits' seconds, as `burst_calls` reads them, and the
    longest commit of the burst.

    `attempts` counts the snapshots alone, `burst_calls`' `s` calls, one per
    attempt, as the row counts them, and `reads` every other call that is
    not a commit or a lookup, its `r` and `m` calls, the detached render's
    reads among them, which a slower runner may not have made yet when the
    logs are read. UNTIL T243q `attempts` counted both, so an older figure,
    py-bench's 73 a burst (55 + 18) and CI round 6g's, is `attempts +
    reads` here (lane 2's RV20, finding 9; T243q).

    `name` is the record's, `burst`, but `burst-measure` for AT-4 (c)'s
    measuring burst, so a census tells the two apart; `wait_s` bounds each
    writer's wait, 150 s, or longer where AT-4 (c)'s deadline asks for it,
    so the case's own drain assertion decides a slow burst (T243u). The
    record ends with each writer's exit code, `codes`, so it shows how the
    burst ended, the measuring burst's among them (lane 2's RV26, NIT 7;
    T243w)."""
    barrier = Barrier(e.root, len(objects))
    arms = [dict(WINDOW, ms=window_ms)]
    writers = [e.launch(lane, claim(obj, "--no-github"), arms=arms, barrier=barrier, extra=extra)
               for lane, obj in zip(BURST, objects)]
    for w in writers:
        (w.psql_dir / "tee").write_text("", encoding="utf-8")  # the stamp's tee (T243m)
    released = barrier.release()
    for w in writers:
        w.wait(wait_s)
    drain = max(w.ended for w in writers) - released
    read = {w.lane: burst_calls(w) for w in writers}
    kinds = {lane: [call[0] for call in r[0].split()] for lane, r in read.items()}
    record(name, node, drain_s=round(drain, 2), margin_vs_30s=round(D7_S / max(drain, 0.01), 2),
           attempts={lane: k.count("s") for lane, k in kinds.items()},
           reads={lane: k.count("r") + k.count("m") for lane, k in kinds.items()},
           seconds={w.lane: round(w.ended - released, 2) for w in writers},
           calls={lane: r[0] for lane, r in read.items()}, losses={lane: r[1] for lane, r in read.items()},
           commit_s={lane: r[2] for lane, r in read.items()},
           longest_commit_s=max((x for r in read.values() for x in r[2]), default=None),
           codes={w.lane: w.code for w in writers})
    return writers, drain


def burst_calls(w: Writer) -> Tuple[str, Dict[str, int], List[float]]:
    """Lane 1's two points (#165 6840891258; T243m), read from `w`'s logs:

    - its calls in order, each `<kind><code>`, the code `psql`'s own exit
      in the shim's ends (`?` where it has none): `s` the snapshot, the
      request just before a commit; `c` a commit (`commit_write`); `l` a
      lookup (`find_write`); `m` the render's `record_mirror_state`; `r`
      any other request, the render's head read, a snapshot's second
      request or LR004's re-read among them;
    - its commits' losses, each failed commit counted under the SQLSTATE of
      each `ERROR:` line its stderr carried (LR001, 40001, 55P03, 40P01,
      LR008 or another), as the stamp's tee logs them, or `unread` where
      the tee logged none;
    - each commit's seconds, from the stamp's start to its stderr's close,
      the shim's window included, where the tee logged its end.

    A burst's figures, never asserted."""
    calls, ends = w.stamps(), w.ends()
    tees = {x["t"]: x for x in w._jsonl("tee.log")}
    letters: List[str] = []
    losses: Dict[str, int] = {}
    seconds: List[float] = []
    for k, call in enumerate(calls):
        text = call.get("stdin") or ""
        after = (calls[k + 1].get("stdin") or "") if k + 1 < len(calls) else ""
        if "commit_write" in text:
            kind = "c"
        elif "find_write" in text:
            kind = "l"
        elif "record_mirror_state" in text:
            kind = "m"
        else:
            kind = "s" if "commit_write" in after else "r"
        end = ends.get(call["call"], {})
        code = end.get("psql", end.get("exit", "?"))
        letters.append(f"{kind}{code}")
        tee = tees.get(call["t"])
        if kind == "c" and tee:
            seconds.append(round(tee["end"] - call["t"], 2))
        if kind == "c" and code != 0:
            for state in (tee or {}).get("states") or ["unread"]:
                losses[state] = losses.get(state, 0) + 1
    return " ".join(letters), losses, seconds


def attempt_starts(w: Writer) -> Tuple[List[dict], List[int]]:
    """`w`'s requests, each with its start on the stamp's wall clock
    (`Writer.stamps`), and the index among them of each attempt's start:
    its snapshot request, `burst_calls`' `s`, the request just before a
    commit call that is not itself a commit, a lookup or the render's
    `record_mirror_state`. Read by `attempt_seconds` (T243u) and `room`
    (T243v)."""
    calls = w.stamps()

    def asks(k: int, *names: str) -> bool:
        return any(name in (calls[k].get("stdin") or "") for name in names)

    return calls, [k for k in range(len(calls) - 1) if asks(k + 1, "commit_write")
                   and not asks(k, "commit_write", "find_write", "record_mirror_state")]


def attempt_seconds(w: Writer) -> List[float]:
    """Each attempt of `w`'s run, in seconds, for AT-4 (c)'s runner's own D7
    (T243u). An attempt that lost its turn runs from its snapshot request's
    start, `burst_calls`' `s`, the request just before a commit call, to the
    next attempt's: one turn of D7's loop, its decision and the next
    attempt's directory included (`44f487d1:lanes-edit.sh:11176-11190`). The
    last attempt runs from its snapshot request's start to the end of its
    commit call, since what follows a commit (the tail, the replay, the
    render's fork) is not D7's loop; where the tee has not logged that end,
    it is left out. Every time is the stamp's wall clock, `stamps.log` and
    the tee's `tee.log`, never the writer's monotonic `started` and
    `ended`. D7's clock starts at the first attempt's start
    (`lanes-edit.sh:11176`), so the first attempt, a cold image cache's,
    is one of them. The starts are `attempt_starts`' (T243v)."""
    calls, starts = attempt_starts(w)
    tees = {x["t"]: x for x in w._jsonl("tee.log")}
    seconds = [calls[b]["t"] - calls[a]["t"] for a, b in zip(starts, starts[1:])]
    if starts:
        tee = tees.get(calls[starts[-1] + 1]["t"])
        if tee:
            seconds.append(tee["end"] - calls[starts[-1]]["t"])
    return seconds


def p95(values: Sequence[float]) -> float:
    """The 95th percentile of `values` by nearest rank: the smallest value at
    or above 95% of them (T243u)."""
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def room(writers: Sequence[Writer], deadline: int) -> Tuple[Optional[float], Optional[float]]:
    """AT-4 (c)'s room under its deadline, `room_s`, and the figure it is
    taken from, `last_start_s`, in seconds (T243v; lane 2's RV26, SHOULD 3;
    lane 3, #165 6870898118: "record `room_s` beside the drain").

    D7's loop takes `PW_T0` from `SECONDS` just before a write's first
    attempt and, at the top of each later attempt, ends the run 75,
    "register busy", once `SECONDS - PW_T0` has reached D
    (`142afd90:lanes-edit.sh:11198-11201`). So D bounds, for each writer,
    the start of its last attempt, counted from the start of its first.
    `last_start_s` is the latest such start over `writers`, and `room_s` is
    `deadline - last_start_s`: the room the writer nearest its deadline still
    had when its last attempt started. A writer whose next attempt would
    start after that room is spent exits 75, and the case's oracle fails.

    Each start is an attempt's snapshot request, `attempt_starts`', on the
    stamp's wall clock. It is the attempt's first request (`pw_attempt_dir`
    makes none, `:11203-11204`), so the same short lead, the attempt's
    directory and the client up to its request, comes before the first
    attempt's snapshot as before the last's, and the difference leaves it
    out. `SECONDS` is whole seconds of the wall clock, so the deadline acts
    at the D-th whole second after `PW_T0`, between D - 1 and D seconds
    after it: a `room_s` of 1 s or less may already be past it.

    Recorded, never asserted. Both are None where no writer's logs hold an
    attempt."""
    spans = []
    for w in writers:
        calls, starts = attempt_starts(w)
        if starts:
            spans.append(calls[starts[-1]]["t"] - calls[starts[0]]["t"])
    if not spans:
        return None, None
    return round(deadline - max(spans), 2), round(max(spans), 2)


def burst_ends(e: Estate, writers: Sequence[Writer]) -> List[Writer]:
    """The ends a burst may have where its case's own row does not ask every
    writer to commit (AT-4 (g), AT-F14): each writer committed once, its
    write in the journal, or exited 75 with nothing written, its write ids
    absent from the journal, and none ended any other way; the journal grew
    by one row per committed writer, its seqs from 2 with no gap and no
    repeat. That is AT-D9c's form for its own burst (Y TP:3755-3759;
    TP:3781-3785 at `0c3750a5`). Lane 3 pointed the bursts to it (#165
    6840952649), then withdrew that (6841239274): each case's own row
    decides, (g)'s the cache's (Y TP:936-950) and AT-F14's each committed
    writer's (Y TP:6852-6854), and neither asks every writer to commit
    (T243r). Returns the writers that committed (T243n).

    At least one writer commits: a burst in which every writer ends 75 has
    lost every writer, against "A burst loses no writer" (Y TP:916-919), and
    would leave each check over the writers that committed, and (g)'s head
    order, true of nothing (lane 2's RV20, finding 8; T243p)."""
    others = [(w.lane, w.code, w.err[-300:]) for w in writers if w.code not in (0, 75)]
    assert not others, f"a burst writer ended neither 0 nor 75: {others}"
    committed = [w for w in writers if w.code == 0]
    assert committed, f"no burst writer committed: all {len(writers)} ended 75 with nothing written"
    for w in writers:
        found = [x for x in set(w.write_ids()) if e.has_write(x)]
        if w.code == 0:
            assert len(found) == 1, f"{w.lane} exited 0, and {len(found)} of its write ids are in the journal"
        else:
            assert not found, f"{w.lane} exited 75, yet its write {found} is in the journal: {w.err[-300:]}"
    grew = e.journal_after()
    assert [r["seq"] for r in grew] == list(range(2, 2 + len(committed))), (
        f"{len(committed)} writers committed, and the journal grew by {grew}")
    return committed


def record(name: str, node: Optional[pytest.Item] = None, **figures) -> str:
    """A figure recorded beside the result, never asserted (TP:7556-7559),
    and returned. With `node`, the case's item, the line is also the case's
    junit property `T243 <name>`, which a failed case's junit carries as a
    passed one's does, though it leaves out captured output (T243l)."""
    line = f"[T243 {name}] " + ", ".join(f"{k}={v}" for k, v in figures.items())
    print(line)
    if node is not None:
        node.user_properties.append((f"T243 {name}", line))
    return line


@CLIENT
def test_two_claimants_one_claimed_and_the_other_exits_2(estates):
    """AT-4 (a): two lanes claim O through the barrier, W = 200 ms. One
    `CLAIMED`, in the journal and the line store; exits {0, 2}; the journal
    grew by one; the loser's write id is absent; no `CLAIM-LOST`; the winner
    prints `register seq <n>`, its entry's seq, and the claim comment its
    tail posts through the fake `gh` cites the same `<n>`."""
    e = estates()
    barrier = Barrier(e.root, 2)
    writers = [e.launch(lane, claim(OBJ), arms=[WINDOW], barrier=barrier) for lane in (LA, LB)]
    barrier.release()
    codes = sorted(w.wait() for w in writers)
    assert codes == [0, 2], [(w.lane, w.code, w.err[-400:]) for w in writers]
    win, lose = sorted(writers, key=lambda w: w.code)
    grew = e.journal_after()
    assert [(r["verb"], r["lane"]) for r in grew] == [("claim", win.lane)], grew
    assert e.claimed(OBJ) == [(OBJ, win.lane)]
    assert e.log_lines("CLAIMED", OBJ) == 1
    assert all(not e.has_write(w) for w in lose.write_ids()), "the loser's write id is in the journal"
    assert e.c.value(f"SELECT count(*) FROM {REGISTER}.doc_lines WHERE text LIKE '%CLAIM-LOST%';") == "0"
    seq = grew[0]["seq"]
    assert win.seq_said() == seq, f"the winner printed {win.seq_said()}, its entry is seq {seq}: {win.err!r}"
    cites = [g for g in e.gh_calls() if f"register seq {seq}" in json.dumps(g)]
    assert cites, f"no claim comment through gh cites register seq {seq}: {e.gh_calls()}"


@CLIENT
def test_the_later_hold_exits_2_and_prints_the_earlier_line(estates):
    """AT-4 (b): two `HOLD`s on one repository's `main`, through the barrier.
    The journal grew by one, the first writer's `HOLD`; it exits 0; the
    second exits 2, writes nothing, and its stderr carries the earlier line
    verbatim with its register seq (D18)."""
    e = estates()
    texts = {lane: f"HOLD {EM} lane {lane} ({W_WS}), {e.utc()}: {KEY} main for T243's case (b)"
             for lane in (LA, LB)}
    barrier = Barrier(e.root, 2)
    writers = [e.launch(lane, ["append-line", texts[lane]], arms=[WINDOW], barrier=barrier)
               for lane in (LA, LB)]
    barrier.release()
    for w in writers:
        w.wait()
    grew = e.journal_after()
    assert len(grew) == 1, grew
    first = next(w for w in writers if w.lane == grew[0]["lane"])
    later = next(w for w in writers if w is not first)
    assert (first.code, later.code) == (0, 2), [(w.lane, w.code, w.err[-400:]) for w in writers]
    assert texts[first.lane] in later.err, f"the later HOLD's stderr lacks the earlier line: {later.err!r}"
    # The relay names the earlier line's seq as `held-by=<seq>`, then the path
    # and the line, tab-separated (register-cli.md:519; T243i).
    assert f"held-by={grew[0]['seq']}\t" in later.err, f"no held-by=<seq> in {later.err!r}"
    assert all(not e.has_write(w) for w in later.write_ids())


@CLIENT
def test_ten_writers_released_together_all_commit_in_order(estates, request):
    """AT-4 (c), section 4.1's oracle: ten writers on ten free objects, W =
    200 ms, under the runner's own D7 (T243u; tasks:2337 at `8e8d1b49`; Brett's
    "(d) Both (a) and (c) (Recommended)", 2026-11-13): the per-workstation
    formula of the design's "D7 stays 30 s" (Y:5906), `max(30 s, 10 x the
    runner's attempt p95)`, set as `LANES_REGISTER_DEADLINE_S` in whole
    seconds rounded up. The writer honours whole seconds only, and ignores
    any other value, keeping 30 (`pw_deadline_s`,
    `44f487d1:lanes-edit.sh:8645-8658`), so the case rounds up itself.

    Each writer reads its deadline once, before its first attempt
    (`:11157`), so the p95 comes from a measuring burst of the same shape,
    run just before in an estate of its own: ten writers on `#500` to `#509`
    released together, W = 200 ms, a cold image cache, and
    `MEASURE_DEADLINE_S`, which none is meant to reach, so all ten stay in
    the load until each commits. Every attempt of the ten, as
    `attempt_seconds` reads it, is pooled, and the p95 taken by nearest rank.
    Before that, all ten measuring writers must have exited 0: one that
    ended early lightens the load and lowers the p95, and one that ran out
    of `MEASURE_DEADLINE_S` exits 75 and cuts the pooled sample short, so
    either fails the case before its burst runs; `burst-measure` records
    each one's exit code (lane 2's RV26, NIT 7; T243w).

    The burst then holds section 4.1's oracle: all exit 0, none 75 or 69;
    seqs 2 to 11, no gap and no repeat; ten distinct write ids; one
    `CLAIMED` per object; the head reads 11. Its drain is asserted under
    twice its deadline (timing rule 2), 60 s at the default. Before any
    assertion it records, never asserted and each as the case's junit
    property (T243l): the measuring burst's own record, `burst-measure`;
    the burst's, `burst`, with each writer's attempts and seconds; and
    `burst-deadline`, the p95, the deadline and the drain side by side, with
    the burst's own attempt p95 by the same rule, so a reader sees whether
    the measure predicted it, and `room_s`, the room the deadline left
    above the latest start of a writer's last attempt, with that start,
    `last_start_s` (`room`; T243v). A 75 under this deadline is a writer
    that needed more room than it had, so `room_s` shows how near a
    passing run came to one (lane 3, #165 6870898118). Its row asks every
    writer to commit, "All ten exit 0, and none exits 75 or 69" (Y
    TP:7509; TP:7583 at `0c3750a5`), so it keeps that oracle where AT-4 (g)
    and AT-F14 take `burst_ends` (T243n). Case (h) still asserts D7's 30 s
    default once, with the variable unset."""
    measure = estates()
    measured, measure_drain = burst(measure, [f"{KEY}#{500 + k}" for k in range(10)], 200,
                                    extra={"LANES_REGISTER_DEADLINE_S": str(MEASURE_DEADLINE_S)},
                                    node=request.node, name="burst-measure")
    assert [w.code for w in measured] == [0] * 10, (
        f"the measuring burst did not end as meant, all ten committing inside its {MEASURE_DEADLINE_S} s, "
        f"so its attempts do not measure the burst's load: {[(w.lane, w.code, w.err[-300:]) for w in measured]}")
    seconds = [s for w in measured for s in attempt_seconds(w)]
    assert seconds, f"the measuring burst's logs hold no attempt: {[(w.lane, w.code) for w in measured]}"
    runner_p95 = p95(seconds)
    deadline = max(D7_S, math.ceil(D7_PER_P95 * runner_p95))
    e = estates()
    objects = [f"{KEY}#{100 + k}" for k in range(10)]
    writers, drain = burst(e, objects, 200, extra={"LANES_REGISTER_DEADLINE_S": str(deadline)},
                           node=request.node, wait_s=max(150, 2 * deadline + 30))
    own = [s for w in writers for s in attempt_seconds(w)]
    room_s, last_start_s = room(writers, deadline)
    record("burst-deadline", request.node, p95_s=round(runner_p95, 3), attempts_measured=len(seconds),
           measure_drain_s=round(measure_drain, 2), deadline_s=deadline, twice_deadline_s=2 * deadline,
           drain_s=round(drain, 2), margin_vs_deadline=round(deadline / max(drain, 0.01), 2),
           room_s=room_s, last_start_s=last_start_s,
           burst_p95_s=round(p95(own), 3) if own else None, burst_attempts=len(own))
    assert [w.code for w in writers] == [0] * 10, [(w.lane, w.code, w.err[-300:]) for w in writers]
    grew = e.journal_after()
    assert [r["seq"] for r in grew] == list(range(2, 12)), grew
    assert len({r["write_id"] for r in grew}) == 10
    assert e.claimed(*objects) == sorted(zip(objects, BURST))
    assert e.c.head() == 11
    assert drain < 2 * deadline, (
        f"the burst drained in {drain:.1f} s, past twice its deadline of {deadline} s, "
        f"10 x the measured attempt p95 of {runner_p95:.2f} s, or D7's {D7_S} s")


@CLIENT
def test_a_write_that_cannot_get_its_turn_exits_75_register_busy(estates):
    """AT-4 (d): two writers on distinct objects, W = 2 s, deadline 1 s. One
    exits 0, the other 75; the busy writer's write id is absent; its stderr
    says nothing was written and a retry in seconds is safe (P231-233)."""
    e = estates()
    barrier = Barrier(e.root, 2)
    writers = [e.launch(lane, claim(obj, "--no-github"), arms=[dict(WINDOW, ms=2000)], barrier=barrier,
                        extra={"LANES_REGISTER_DEADLINE_S": "1"})
               for lane, obj in ((LA, f"{KEY}#51"), (LB, f"{KEY}#52"))]
    barrier.release()
    assert sorted(w.wait() for w in writers) == [0, 75], [(w.lane, w.code, w.err[-400:]) for w in writers]
    busy = next(w for w in writers if w.code == 75)
    assert all(not e.has_write(w) for w in busy.write_ids())
    said = busy.err.lower()
    assert all(word in said for word in BUSY_WORDS), f"the busy text lacks {BUSY_WORDS}: {busy.err!r}"
    assert len(e.journal_after()) == 1


@CLIENT
def test_the_default_deadline_is_30_s_for_a_write_that_never_gets_its_turn(estates):
    """AT-4 (h): `LANES_REGISTER_DEADLINE_S` unset; the admin session holds
    the head row `FOR UPDATE` for the whole case, so each commit call gets
    55P03 at its `lock_timeout`, a lost turn. The writer exits 75, its write
    ids absent, its stderr carrying the busy text with "attempts in 30 s";
    it exits no earlier than 29 s after its launch (timing rule 3) and under
    2 x (30 + 8 + 8) = 92 s, and no snapshot call starts more than 60 s after
    the first (timing rule 2). Both times are recorded against 46 s and
    30 s."""
    e = estates()
    admin = e.hold_row_locked()
    try:
        w = e.run(LA, claim(f"{KEY}#61", "--no-github"))
    finally:
        e.unlock(admin)
    took = w.ended - w.started
    assert w.code == 75, f"exit {w.code}, not 75: {w.err[-600:]}"
    assert w.write_ids() and all(not e.has_write(x) for x in w.write_ids())
    assert "register busy" in w.err.lower() and f"attempts in {D7_S} s" in w.err, w.err
    assert took >= D7_S - 1, f"it exited {took:.1f} s after its launch, before D7's {D7_S} s less 1 s"
    assert took < 2 * (D7_S + 8 + 8), f"it exited {took:.1f} s after its launch, past 92 s"
    starts = [s["t"] for s in w.stamps() if "commit_write" not in (s.get("stdin") or "")]
    spread = max(starts) - min(starts) if starts else 0.0
    assert spread <= TWICE_D7_S, f"a snapshot call started {spread:.1f} s after the first"
    record("default-deadline", exit_s=round(took, 2), vs_46s=round(46 - took, 2),
           snapshot_spread_s=round(spread, 2), vs_30s=round(D7_S - spread, 2), attempts=len(starts))


#: AT-4 (f), with lane 3's text for T243 (#165 6772120103, "T243 (:2232)"):
#: each case's lines before, the line `append-line` sends, and what it must
#: do: refused with 2 and nothing written, or committed with 0, taking or
#: freeing what Q17 (B) says (`main_slots` for the writer's lane).
NO_REPO = {
    "hold-no-repo": ([], "HOLD {em} lane {lane} ({ws}), {utc}: for a frozen window", 2, None),
    "landing-no-repo": ([], "LANDING {em} lane {lane}, session {sid}@{ws}, {utc}, PR #{pr}", 2, None),
    "take-no-utc": ([], "HOLD {em} lane {lane} ({ws}): {key} main for a frozen window", 2, None),
    "free-text": ([], "NOTE {em} lane {lane}: the register's free text (T243)", 0, []),
}

#: Test 4 (f)'s slot lines of another shape, which commit 0 (lane 3,
#: 6771569269: "`append-line` writes these lines on primary ... T424 does not
#: change"), in a function of their own, outside T424's word
#: `hold_line_that_names_no_repository` (lane 3's batch 7, ruling 4). The same
#: columns as `NO_REPO`'s.
OTHER_SHAPE = {
    "landed-no-repo": (["LANDING {em} lane {lane}, session {sid}@{ws}, {utc}, PR #{pr} into {key} main"],
                       "LANDED {em} lane {lane}, session {sid}@{ws}, {utc}, PR #{pr} {arrow} abc1234", 0, []),
    "hold-released-no-repo": (["HOLD {em} lane {lane} ({ws}), {utc}: {key} main for a frozen window"],
                              "HOLD RELEASED {em} lane {lane} ({ws}), {utc}", 0, [["hold", KEY, None]]),
    "landing-no-pr": ([], "LANDING {em} lane {lane}, session {sid}@{ws}, {utc}, into {key} main", 0, []),
}


@CLIENT
@pytest.mark.parametrize("case", list(NO_REPO))
def test_a_hold_line_that_names_no_repository_is_refused_with_2(estates, case):
    """AT-4 (f) (`design.md` S6): on primary, `append-line` with a line
    matching `HOLD ` or `LANDING ` from which no repository can be read exits
    2 and writes nothing, and so does a take whose UTC cannot be read (U3;
    its client half is AT-F13 (b)). A line of another shape is written as free
    text: [free-text] commits 0, and as a line of no kind it gets no
    `register_lines` row and takes or frees nothing (T243k)."""
    append_line_case(estates(), case, NO_REPO[case])


@CLIENT
@pytest.mark.parametrize("case", list(OTHER_SHAPE))
def test_a_slot_line_of_another_shape_commits_0(estates, case):
    """Test 4 (f)'s lines of another shape (lane 3, 6771569269): on primary a
    `LANDED` naming no repository commits 0 and frees its pair in
    `main_slots`; a `HOLD RELEASED` naming none and a `LANDING` naming no PR
    commit 0 and take or free nothing. T424's classifier must let them
    through (lane 3's batch 7, ruling 4)."""
    append_line_case(estates(), case, OTHER_SHAPE[case])


def append_line_case(e: Estate, case: str, row: tuple) -> None:
    """One case of test 4 (f): `row`'s lines before, then its line, and its
    exit, and what the register then holds."""
    before_lines, text, code, slots = row

    def spell(form: str) -> str:
        return form.format(em=EM, arrow=ARROW, lane=LA, ws=W_WS, sid=session_of(LA), utc=e.utc(),
                           pr=PR, key=KEY)

    for line_form in before_lines:
        assert e.run(LA, ["append-line", spell(line_form)]).code == 0
    if before_lines:
        assert e.open_slots(LA) == [[("landing" if "LANDING" in before_lines[0] else "hold"), KEY,
                                     PR if "LANDING" in before_lines[0] else None]], e.open_slots(LA)
    head, state = e.c.head(), e.c.state()
    slots_before = e.rows(f"SELECT * FROM {REGISTER}.main_slots ORDER BY line_id")
    line = spell(text)
    w = e.run(LA, ["append-line", line])
    assert w.code == code, f"[{case}] exit {w.code}, not {code}: {w.err[-600:]}"
    if code == 2:
        assert e.c.state() == state, f"[{case}] the refusal changed the register"
        assert w.commit_calls() == [], f"[{case}] a commit call was sent"
        return
    assert e.c.head() == head + 1
    said = e.rows(f"SELECT kind, slot_role FROM {REGISTER}.register_lines WHERE seq = {head + 1}")
    if case == "free-text":
        # A LINE OF NO KIND GETS NO `register_lines` ROW (lane 1, #165
        # 6834413025, which lanes 3 and 4 agree; ERR-49, B19 tasks:515,
        # "`register_lines` for kinds only"): `parse_register_line` gives None
        # for it, and the commit sends no row. So the oracle is the line
        # written, no row, `main_slots` as it was, and another lane's `HOLD`
        # still committing (T243k).
        assert said == [], f"[{case}] a line of no kind got register_lines rows: {said}"
        sent = e.rows(f"SELECT path, new_text FROM {REGISTER}.journal_edits WHERE seq = {head + 1} "
                      "AND op = 'append'")
        assert {"path": LANES_MD, "new_text": line} in sent, f"[{case}] the line was not written: {sent}"
        after = e.rows(f"SELECT * FROM {REGISTER}.main_slots ORDER BY line_id")
        assert after == slots_before, f"[{case}] main_slots moved: {slots_before} -> {after}"
        other = e.run(LB, ["append-line", f"HOLD {EM} lane {LB} ({W_WS}), {e.utc()}: {KEY} main for T243's "
                                          "free-text case"])
        assert other.code == 0, f"[{case}] another lane's HOLD exited {other.code}: {other.err[-600:]}"
        return
    role = "close" if case == "landed-no-repo" else None
    assert len(said) == 1 and said[0]["slot_role"] == role, f"[{case}] {said}, its slot_role not {role}"
    assert e.open_slots(LA) == slots, f"[{case}] main_slots for {LA}: {e.open_slots(LA)}, not {slots}"


#: Q17 (B)'s table (lane 1's `REGISTER_SLOTS`, T118): each kind's line, the
#: line before it that it pairs with, and whether `main` is taken after it.
KINDS = {
    "hold": ([], "HOLD", True),
    "hold-refresh": ([], "HOLD (refresh)", False),
    "hold-run-id": ([], "HOLD (run id)", False),
    "hold-released": (["HOLD"], "HOLD RELEASED", False),
    "hold-withdrawn": (["HOLD"], "HOLD WITHDRAWN", False),
    "hold-expired": (["HOLD"], "HOLD EXPIRED", False),
    "queued-hold": ([], "QUEUED-HOLD", False),
    "landing": ([], "LANDING", True),
    "landed": (["LANDING"], "LANDED", False),
    "landing-expired": (["LANDING"], "LANDING EXPIRED", False),
    "landing-withdrawn": ([], "LANDING WITHDRAWN", False),
}


def kind_line(e: Estate, kind: str, lane: str, minutes_ago: float = 0) -> str:
    utc = e.utc(minutes_ago)
    if kind.startswith("LANDING") or kind == "LANDED":
        tail = f" {ARROW} abc1234" if kind == "LANDED" else ""
        return f"{kind} {EM} lane {lane}, session {session_of(lane)}@{W_WS}, {utc}, PR #{PR} into {KEY} main{tail}"
    return f"{kind} {EM} lane {lane} ({W_WS}), {utc}: {KEY} main for T243's table"


@CLIENT
@pytest.mark.parametrize("kind", list(KINDS))
def test_each_line_kind_takes_or_releases_main_as_q17_b_says(estates, kind):
    """After each kind's line, `main_slots` shows `main` taken or released as
    Q17 (B)'s table says, and another lane's `HOLD` then exits 0 or 2 to
    match. `LANDING EXPIRED` is written by AT-F13's form over a `LANDING`
    composed with a UTC 31 minutes back (TP:975-980)."""
    e = estates()
    before, name, taken = KINDS[kind]
    for pair in before:
        ago = 31 if name == "LANDING EXPIRED" else 0
        assert e.run(LA, ["append-line", kind_line(e, pair, LA, ago)]).code == 0
    if name == "LANDING EXPIRED":
        argv = ["append-line", "--landing-expired", LA, "--pr", str(PR), "--repo", KEY,
                "--word", "Release the stale LANDING (Recommended)", "--word-where",
                "lane openRepoTools-2's session", "--word-utc", e.utc(1)]
        w = e.run(LB, argv)
    else:
        w = e.run(LA, ["append-line", kind_line(e, name, LA)])
    assert w.code == 0, f"[{kind}] exit {w.code}: {w.err[-600:]}"
    slots = e.open_slots(LA)
    assert bool(slots) == taken, f"[{kind}] main_slots for {LA}: {slots}"
    other = e.run(LC, ["append-line", kind_line(e, "HOLD", LC)])
    assert other.code == (2 if taken else 0), f"[{kind}] another lane's HOLD exited {other.code}: {other.err[-400:]}"


@CLIENT
def test_claim_prints_its_register_seq(estates):
    """Q19 (A), GB section 4.3 (R29): `claim` prints `register seq <n>`, its
    entry's seq, the first write after the cutover, 2."""
    e = estates()
    w = e.run(LA, claim(OBJ, "--no-github"))
    assert w.code == 0, w.err[-600:]
    grew = e.journal_after()
    assert [(r["seq"], r["verb"]) for r in grew] == [(2, "claim")], grew
    assert w.seq_said() == 2, f"claim printed {w.err!r}"


@CLIENT
def test_a_serialization_failure_is_retried_never_reported_as_69(estates):
    """AT-4 (e): in case (a)'s race the loser's first commit call fails (its
    snapshot predates the winner's commit), and the loser re-runs from the
    pre-check and exits 2, never 69 or 75; its write ids are absent."""
    e = estates()
    barrier = Barrier(e.root, 2)
    writers = [e.launch(lane, claim(OBJ, "--no-github"), arms=[WINDOW], barrier=barrier) for lane in (LA, LB)]
    barrier.release()
    for w in writers:
        w.wait()
    lose = next((w for w in writers if w.code != 0), None)
    assert lose is not None and lose.code == 2, [(w.lane, w.code, w.err[-400:]) for w in writers]
    assert not {69, 75} & {w.code for w in writers}, [w.code for w in writers]
    calls = lose.commit_calls()
    assert calls, "the loser made no commit call: its snapshot did not predate the winner's commit"
    first = lose.ends().get(calls[0]["call"], {})
    assert first.get("psql") not in (None, 0), f"the loser's first commit call did not fail: {first}"
    assert len(lose.snapshot_calls()) >= 2, "the loser did not re-read after its failed commit"
    assert all(not e.has_write(x) for x in lose.write_ids())


def _objects_named(e: Estate) -> Dict[str, Path]:
    objects = e.state / "openRepoTools" / "register-images" / "objects"
    return {p.name: p for p in objects.iterdir()} if objects.exists() else {}


@CLIENT
def test_the_image_cache_stays_content_addressed_under_the_burst_and_a_corrupt_object_is_refetched(
        estates, request):
    """AT-4 (g): in the state directory the burst's writers shared, every
    object is named by the sha256 of its bytes and no temporary file is left;
    `head` never decreases in the samples taken during the burst and ends no
    higher than the journal's head; its manifest lists only present objects.
    An object corrupted under its name is not used: the next write exits 0,
    and its render is byte-identical to a full render."""
    e = estates()
    cache = e.state / "openRepoTools" / "register-images"
    samples: List[int] = []
    stop = threading.Event()

    def sample() -> None:
        while not stop.is_set():
            try:
                samples.append(int((cache / "head").read_text().strip()))
            except (OSError, ValueError):
                pass
            time.sleep(0.05)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        writers, _ = burst(e, [f"{KEY}#{200 + k}" for k in range(10)], 200, node=request.node)
    finally:
        stop.set()
        sampler.join(5)
    # (g)'s own row asks the cache of the state the ten writers shared, not
    # that every one commits (Y TP:936-950; TP:941-955 at `0c3750a5`): a
    # writer may end 75 with nothing written, as `burst_ends` checks (T243n).
    burst_ends(e, writers)
    named = _objects_named(e)
    assert named, f"the burst left no object under {cache}"
    for name, path in named.items():
        assert re.fullmatch(r"[0-9a-f]{64}", name), f"a file that is not an object is left: {name}"
        assert sha256(path.read_bytes()) == name, f"{name} is not named by its bytes"
    assert samples == sorted(samples), f"register-images/head went back: {samples}"
    head = int((cache / "head").read_text().strip())
    assert head <= e.c.head()
    listed = [line.split("\t")[1] for line in (cache / "seq" / str(head)).read_text().splitlines() if line]
    assert set(listed) <= set(named), f"manifest {head} lists absent objects: {set(listed) - set(named)}"

    victim = named[listed[0]]
    victim.write_bytes(victim.read_bytes() + b"corrupt\n")
    _, lines = e.c.file(LANES_MD)
    text = f"NOTE {EM} lane {LA}: written after the corrupt object (T243)"
    w = e.run(LA, ["append-line", text])
    assert w.code == 0, f"the write after the corruption exited {w.code}: {w.err[-600:]}"
    nl, after = e.c.file(LANES_MD)
    assert after == [*lines, text]
    digest = e.c.value(f"SELECT sha256 FROM {REGISTER}.files WHERE path = '{LANES_MD}';")
    assert digest == sha256(rendered(after, bool(nl))), "the render after the corruption is not a full render's"


@CLIENT
@pytest.mark.parametrize("order", ["alias-holder-first", "behind-the-alias-first"])
def test_an_alias_edit_racing_a_claim_cannot_let_two_claims_of_one_object_pass(estates, order):
    """AT-C10, both orders. [alias-holder-first]: A, at T0, claims O and is
    held at its commit call; T1 adds X as O's alias; B claims X and commits;
    A, released, loses its turn, and its next snapshot's pre-check refuses it
    with 2: one commit call from A. [behind-the-alias-first]: A, at T0,
    claims X and commits; after T1, B claims O and is refused LR005
    `claim-spellings` on its commit call, its write id absent."""
    e = estates()
    if order == "alias-holder-first":
        fifo = e.root / "hold-a.fifo"
        os.mkfifo(str(fifo))
        a = e.launch(LA, claim(OBJ, "--no-github"),
                     arms=[{"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(fifo)}])
        held = hold_point(fifo, a)
        e.push_alias()
        b = e.run(LB, claim(OBJ_X, "--no-github"))
        held.close()
        a.wait()
        assert (a.code, b.code) == (2, 0), [(w.lane, w.code, w.err[-400:]) for w in (a, b)]
        assert e.claimed(OBJ, OBJ_X) == [(OBJ, LB)]
        assert len(a.commit_calls()) == 1, "A made a second commit call"
        assert a.ends()[a.commit_calls()[0]["call"]].get("psql") not in (None, 0)
    else:
        a = e.run(LA, claim(OBJ_X, "--no-github"))
        assert a.code == 0, a.err[-600:]
        e.push_alias()
        b = e.run(LB, claim(OBJ, "--no-github"))
        assert b.code == 2, f"B exited {b.code}: {b.err[-600:]}"
        assert "LR005" in b.err and "claim-spellings" in b.err, b.err
        assert b.commit_calls(), "B's refusal came before its commit call, not from the spelling check"
        assert all(not e.has_write(x) for x in b.write_ids())
        assert e.claimed(OBJ, OBJ_X) == [(OBJ_X, LA)]
    assert e.c.value(f"SELECT count(*) FROM {REGISTER}.object_holds WHERE object = '{OBJ_X}' "
                     f"AND lane = '{LB}';") == "0"


@CLIENT
@pytest.mark.parametrize("tip", ["same-tip", "behind-the-alias"])
def test_two_spellings_of_one_object_claimed_at_once_leave_one_claimed_and_exit_2(estates, tip):
    """AT-D19: L1 claims O and L2 claims X, each held at its first commit
    call after both snapshots read `n`; the admin session holds the head row;
    L1's call is released and waits on the lock, then L2's; the admin rolls
    back, so L1 takes the head row first. L1 exits 0 and prints `register
    seq <n+1>`; L2's first commit fails, it re-reads and exits 2, never 69
    or 75, its stderr naming L1's claim; the journal grew by one; L1's
    `object_holds` row carries O as typed, the key O and the alias X; one
    live `CLAIMED` holds O and no line holds X."""
    e = estates()
    origin_l2 = e.mirror_at_t0() if tip == "behind-the-alias" else None
    e.push_alias()
    n = e.c.head()
    fifos = {lane: e.root / f"hold-{lane}.fifo" for lane in (LA, LB)}
    for f in fifos.values():
        os.mkfifo(str(f))
    arms = {lane: [{"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(fifos[lane])}]
            for lane in (LA, LB)}
    l1 = e.launch(LA, claim(OBJ, "--no-github"), arms=arms[LA])
    l2 = e.launch(LB, claim(OBJ_X, "--no-github"), arms=arms[LB], origin=origin_l2)
    holds = {LA: hold_point(fifos[LA], l1), LB: hold_point(fifos[LB], l2)}  # both snapshots read n
    admin = e.hold_row_locked()
    try:
        holds[LA].close()
        assert e.waits_on_lock(l1.write_ids()[0]), "L1's commit never waited on the head row"
        holds[LB].close()
        assert e.waits_on_lock(l2.write_ids()[0]), "L2's commit never waited on the head row"
    finally:
        e.unlock(admin)
    l1.wait()
    l2.wait()
    assert (l1.code, l2.code) == (0, 2), [(w.lane, w.code, w.err[-400:]) for w in (l1, l2)]
    assert l1.seq_said() == n + 1
    assert l2.ends()[l2.commit_calls()[0]["call"]].get("psql") not in (None, 0)
    assert len(l2.snapshot_calls()) >= 2, "L2 did not re-read at n+1"
    assert LA in l2.err, f"L2's refusal does not name L1's claim: {l2.err!r}"
    assert [r["lane"] for r in e.journal_after(n)] == [LA]
    spellings = e.c.value(f"SELECT spellings::text FROM {REGISTER}.object_holds WHERE object = '{OBJ}' "
                          f"AND lane = '{LA}';")
    assert all(s in spellings for s in (OBJ, OBJ_X)), spellings
    assert all(not e.has_write(x) for x in l2.write_ids())
    assert e.claimed(OBJ, OBJ_X) == [(OBJ, LA)]
    assert e.log_lines("CLAIMED", OBJ_X) == 0
    if tip == "behind-the-alias":
        assert "LR005" in l2.err and "claim-spellings" in l2.err, l2.err


@CLIENT
def test_the_claim_behind_the_alias_is_refused_by_lr005_on_its_spellings(estates):
    """AT-D19 [behind-the-alias], by itself: L1 at the tip with the alias
    claims O and commits; L2, at the tip before the alias, claims X. Neither
    the verb's check nor `one_live_claim` sees L1's claim, so the refusal is
    LR005 `claim-spellings` on L2's last commit call: exit 2, its write id
    absent, one live `CLAIMED` on O."""
    e = estates()
    frozen = e.mirror_at_t0()
    e.push_alias()
    l1 = e.run(LA, claim(OBJ, "--no-github"))
    assert l1.code == 0, l1.err[-600:]
    l2 = e.run(LB, claim(OBJ_X, "--no-github"), origin=frozen)
    assert l2.code == 2, f"L2 exited {l2.code}: {l2.err[-600:]}"
    assert "LR005" in l2.err and "claim-spellings" in l2.err, l2.err
    calls = l2.commit_calls()
    assert calls and l2.ends()[calls[-1]["call"]].get("psql") not in (None, 0), "no refused commit call"
    assert all(not e.has_write(x) for x in l2.write_ids())
    assert e.claimed(OBJ, OBJ_X) == [(OBJ, LA)]


@CLIENT
def test_the_burst_window_is_effective_a_short_deadline_sends_writers_busy(estates):
    """Section 4.1's companion: the same burst with a 1 s deadline. At least
    one writer exits 75, none exits 69, and each busy writer's write ids are
    absent from the journal."""
    e = estates()
    writers, drain = burst(e, [f"{KEY}#{300 + k}" for k in range(10)], 200,
                           extra={"LANES_REGISTER_DEADLINE_S": "1"})
    codes = [w.code for w in writers]
    assert 75 in codes and 69 not in codes, codes
    assert set(codes) <= {0, 75}, codes
    for w in writers:
        if w.code == 75:
            assert all(not e.has_write(x) for x in w.write_ids()), f"{w.lane} busy, yet written"
    record("window-effective", busy=codes.count(75), drain_s=round(drain, 2))


# ============================================================ PHASE W: AT-F14, output once (T248)
#
# F14 (S1, "Output and side effects, once"; lane 4's section): the verb runs
# as a child that stops at the seam; only the deciding attempt's output is
# replayed, stdout first; every side effect outside the register runs once,
# after COMMIT; one run makes one journal entry. On test 4's estate (T243's
# `Estate`), with logging fakes for `gh`, `tmux` and a `git` wrapper that log
# their environment (TP:6847-6851). The child's state directory is read as
# `<XDG_STATE_HOME>/openRepoTools/register-writes/` (a reading: lane 4 names
# `<state>/register-writes/`). They FAIL UNTIL L4-B3 and L4-B7 land (T413,
# T414, T415), with T243's own; without PostgreSQL 16 each skips.
#
# THE TAIL'S `gh` CALL IS THE COMMENT (T248a; lane 4's triage, #165
# 6827643168, item 3). `claim` also calls `gh` for Rule 1's three reads,
# `issue view --comments` and `pr list` (`gh_reads_live`), at its step 2,
# before `write_event` reaches the seam. Under the flag they are made once a
# run, by its first attempt, and cached for the rest (T413; Y:5043), and they
# decide nothing. So the cases count only `gh`'s comment calls
# (`comment_calls`), `issue comment` or `pr comment` (`gh_comment`, T421).

_ENV_LOGGER = r'''#!/usr/bin/env python3
# T248's logging stand-in: its name, argv, whether the flag reached it, and
# each seam.out it can see; then the real tool, where one is named. For `gh`
# with `--body-file -` (`gh_comment`), the body it reads from stdin too, and
# no other call's stdin is read (T248a). A `tmux` given answers prints the
# one its `display-message` format asks for, keyed `t:<format>` where the
# call names a target with `-t` (T248b).
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
NAME = os.path.basename(sys.argv[0])
REAL = REAL_TOOL
STATE = STATE_DIR
ANSWERS = TMUX_ANSWERS
ARGV = sys.argv[1:]
seams = {p: open(p, encoding="utf-8", errors="replace").read()
         for p in glob.glob(os.path.join(STATE, "**", "seam.out"), recursive=True)}
body = None
if NAME == "gh" and "--body-file" in ARGV and ARGV[ARGV.index("--body-file") + 1:][:1] == ["-"]:
    body = sys.stdin.read()
with open(os.path.join(HERE, "tools.log"), "a", encoding="utf-8") as log:
    log.write(json.dumps({"tool": NAME, "argv": ARGV, "scratch": os.environ.get(
        "LANES_REGISTER_SCRATCH"), "seams": seams, "body": body}) + "\n")
if ANSWERS and NAME == "tmux" and ARGV[:1] == ["display-message"]:
    said = ANSWERS.get(("t:" if "-t" in ARGV else "") + ARGV[-1])
    if said is not None:
        print(said)
if REAL:
    os.execv(REAL, [REAL] + ARGV)
'''

#: The answers of a `tmux` whose server holds the bound window live (T248b):
#: any window asked for by `-t` is in session `t243`, `bound_line`'s, and runs
#: `claude`, so `binding_window_state` reads it `live` and `guard_type` types
#: into it; the asking pane is `asker:1`, window `@90`, never a bound one.
TMUX_LIVE = {"t:#{session_name}": "t243", "t:#{pane_current_command}": "claude",
             "#{session_name}:#{window_index}": "asker:1", "#{window_id}": "@90", "#{pane_id}": "%90"}


def loggers(e: Estate, tmux_live: bool = False) -> Path:
    """`git` (a wrapper), `gh` and `tmux` (fakes), each logging to
    `tools.log` beside them. With `tmux_live`, the fake `tmux` answers its
    `display-message` reads from `TMUX_LIVE` (T248b); otherwise it prints
    nothing, as before."""
    where = e.root / "loggers"
    where.mkdir(exist_ok=True)
    for tool, real in (("git", shutil.which("git")), ("gh", None), ("tmux", None)):
        answers = repr(TMUX_LIVE) if tool == "tmux" and tmux_live else "None"
        (where / tool).write_text(_ENV_LOGGER.replace("REAL_TOOL", repr(real))
                                  .replace("STATE_DIR", repr(str(e.state)))
                                  .replace("TMUX_ANSWERS", answers), encoding="utf-8")
        (where / tool).chmod(0o755)
    return where


def tool_calls(where: Path, tool: Optional[str] = None) -> List[dict]:
    log = where / "tools.log"
    calls = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] if log.exists() else []
    return [c for c in calls if tool is None or c["tool"] == tool]


def comment_calls(where: Path) -> List[dict]:
    """The fake `gh`'s comment calls, `issue comment` or `pr comment`: the
    tail's `gh` (`gh_comment`), never Rule 1's reads (see the section's
    head; T248a)."""
    return [c for c in tool_calls(where, "gh") if c["argv"][:1] in (["issue"], ["pr"])
            and c["argv"][1:2] == ["comment"]]


def typed_calls(where: Path) -> List[dict]:
    """The fake `tmux`'s typing, `send-keys` (`guard_type`): the tail's
    `tmux`, never its reads before the seam, `display-message` for the
    asking window and the bound window's session and command (T248b)."""
    return [c for c in tool_calls(where, "tmux") if c["argv"][:1] == ["send-keys"]]


def register_writes(e: Estate) -> Path:
    return e.state / "openRepoTools" / "register-writes"


def seam_outs(e: Estate) -> Dict[str, str]:
    return {str(p): p.read_text(encoding="utf-8", errors="replace")
            for p in register_writes(e).rglob("seam.out")} if register_writes(e).exists() else {}


@CLIENT
def test_a_writer_prints_its_output_once_however_many_attempts_it_made(estates, request):
    """Test 4's burst of ten: each committed writer's success text, claim's
    `register seq <s>` line, is printed exactly once, however many attempts
    it made, and its stderr no line twice (only the deciding attempt's). The
    line is a `note`, on stderr (T421; T243h). The row's oracle is each
    committed writer's (Y TP:6852-6854; TP:6925-6927 at `0c3750a5`), so a
    writer may end 75 with nothing written, as `burst_ends` checks (T248d).

    Its record counts each writer's attempts by its snapshots alone,
    `burst_calls`' `s` calls, and `reads` its `r` and `m` calls, the detached
    render's reads among them, as the burst record does (T243q). Read after
    the burst's own record, it can hold more render reads than that one,
    never more attempts. UNTIL T248e `attempts` here counted both, so an
    older figure is `attempts + reads` (lane 2's RV20, finding 9; T248e)."""
    e = estates()
    writers, _ = burst(e, [f"{KEY}#{400 + k}" for k in range(10)], 200, node=request.node)
    for w in burst_ends(e, writers):
        assert len(SEQ_SAID.findall(w.err)) == 1, f"{w.lane} printed its success text not once: {w.err!r}"
        lines = [l for l in w.err.splitlines() if l.strip()]
        assert len(lines) == len(set(lines)), f"{w.lane}'s stderr repeats an attempt's lines: {w.err!r}"
    kinds = {w.lane: [call[0] for call in burst_calls(w)[0].split()] for w in writers}
    record("output-once", attempts={lane: k.count("s") for lane, k in kinds.items()},
           reads={lane: k.count("r") + k.count("m") for lane, k in kinds.items()})


@CLIENT
def test_a_refused_writer_replays_its_output_then_the_refusal(estates):
    """Test 4's case (a): the writer refused at its commit prints its
    buffered output, then the refusal, last, naming the holder, and no
    success text. The success text, claim's `register seq <s>` line, is a
    `note`, on stderr (T421), so stderr is where its absence is read
    (T248c)."""
    e = estates()
    barrier = Barrier(e.root, 2)
    writers = [e.launch(lane, claim(OBJ, "--no-github"), arms=[WINDOW], barrier=barrier) for lane in (LA, LB)]
    barrier.release()
    assert sorted(w.wait() for w in writers) == [0, 2]
    win, lose = sorted(writers, key=lambda w: w.code)
    assert not SEQ_SAID.search(lose.err), f"the refused writer printed success text: {lose.err!r}"
    lines = [l for l in lose.err.splitlines() if l.strip()]
    assert lines and win.lane in lines[-1], f"the refusal naming {win.lane} is not last: {lose.err!r}"
    assert len(lines) == len(set(lines)), f"the refused writer's stderr repeats lines: {lose.err!r}"


@CLIENT
@pytest.mark.parametrize("effect", ["tmux", "gh"])
def test_a_side_effect_runs_once_after_commit_and_never_for_a_refusal(estates, effect):
    """[gh]: two claimants on O; the fake `gh` comments once, by the
    committed claim, its body citing its seq, never by the refused one
    (Rule 1's reads, which each claimant makes before the seam, are not
    counted; T248a). [tmux]: two `request-handoff`s for lane C, which is
    bound to a window this tmux server holds live; the fake `tmux` types
    (`send-keys`) once per committed request, naming its requester, after
    its COMMIT (the journal holds it when `tmux` runs), and never for an
    attempt refused at its commit, whose child runs no tail.

    [tmux] as the engine does it (T248b; N2-17b's reading 3): a request for a
    bound or already requested lane is taken, so both requests may commit,
    and the journal, not the exit, says which did. Each runs `--no-wait`, so
    its wait ends at once, 2, "THE WAIT ENDED WITH NOTHING", after its
    commit. The reads `tmux` answers before the seam (`display-message` for
    the asking window, the bound window's session and its command) are not
    counted: only `send-keys`, and the fake answers them from `TMUX_LIVE`.

    After COMMIT: when the call runs, a `seam.out` reads `tail`, so an
    attempt has taken `committed`, and none reads other than `tail` or
    `none`: the refused claimant's abandoned attempt may have written its own
    `none` by then, and the logger sees every `seam.out` under
    `register-writes/` (T248a)."""
    e = estates()
    where = loggers(e, tmux_live=effect == "tmux")
    barrier = Barrier(e.root, 2)
    if effect == "gh":
        writers = [e.launch(lane, claim(OBJ), arms=[WINDOW], barrier=barrier, first=[where])
                   for lane in (LA, LB)]
    else:
        writers = [e.launch(lane, ["request-handoff", LC, "--session", session_of(lane), "--no-wait"],
                            arms=[WINDOW], barrier=barrier, first=[where]) for lane in (LA, LB)]
    barrier.release()
    for w in writers:
        w.wait()
    grew = e.journal_after()
    if effect == "gh":
        committed = [w.lane for w in writers if w.code == 0]
    else:
        assert {w.code for w in writers} <= {0, 2}, [(w.lane, w.code, w.err[-300:]) for w in writers]
        committed = [r["lane"] for r in grew if r["verb"] == "request-handoff"]
    assert len(committed) == len(grew) >= 1, ([(w.lane, w.code, w.err[-300:]) for w in writers], grew)
    calls = comment_calls(where) if effect == "gh" else typed_calls(where)
    assert len(calls) == len(committed), f"{effect} ran {len(calls)} times for {len(committed)} commits: {calls}"
    if effect == "gh":
        assert all(str(grew[0]["seq"]) in SEQ_SAID.findall(c["body"] or "") for c in calls), calls
    else:
        typed = sorted(lane for lane in (LA, LB) for c in calls if session_of(lane) in " ".join(c["argv"]))
        assert typed == sorted(committed), f"tmux typed for {typed}, the journal's requests are {committed}: {calls}"
    for call in calls:
        said = [text.strip() for text in call["seams"].values()]
        assert "tail" in said and set(said) <= {"tail", "none"}, f"{effect} ran before COMMIT: {call}"


#: The test copy of `lanes-edit.sh` whose writes reach the seam twice: its
#: `commit_publish` (T414's seam) is renamed and called twice by a wrapper.
TWICE = ('commit_publish() { commit_publish_t248_once "$@" || return; '
         'commit_publish_t248_once "$@"; }\n')


@CLIENT
def test_a_second_reach_of_the_seam_in_one_run_exits_2(estates):
    """One run, one journal entry: an arm the test copy makes reach the seam
    twice exits 2, "a second register write in one run", naming the first
    seq, and the journal holds that one entry."""
    e = estates()
    text = e.lanes_edit.read_text(encoding="utf-8")
    assert text.count("\ncommit_publish() {") == 1, "lanes-edit.sh has no commit_publish, T414's seam"
    twice = e.bindir / "lanes-edit-twice.sh"
    twice.write_text(text.replace("\ncommit_publish() {", "\n" + TWICE + "commit_publish_t248_once() {", 1),
                     encoding="utf-8")
    w = e.run(LA, ["append-line", f"NOTE {EM} lane {LA}: one run, two reaches (T248)"], script=twice)
    grew = e.journal_after()
    assert w.code == 2, f"exit {w.code}, not 2: {w.err[-600:]}"
    assert len(grew) == 1, grew
    assert "a second register write in one run" in w.err and str(grew[0]["seq"]) in w.err, w.err


@CLIENT
@pytest.mark.parametrize("case", ["outside-register-writes", "wrong-mode", "other-parent"])
def test_the_scratch_flag_is_honoured_only_for_its_own_attempt_directory(estates, case):
    """A write run with `LANES_REGISTER_SCRATCH` exported, naming a directory
    outside `<state>/register-writes/`, one of mode 0755, or one whose
    `parent.pid` is not the run's parent, does not take it as the flag: the
    shim's log shows the run's own snapshot and commit calls, and it
    commits."""
    e = estates()
    base = e.root / "elsewhere" if case == "outside-register-writes" else register_writes(e)
    attempt = base / "attempt-t248"
    attempt.mkdir(parents=True)
    attempt.chmod(0o755 if case == "wrong-mode" else 0o700)
    (attempt / "parent.pid").write_text("1\n" if case == "other-parent" else f"{os.getpid()}\n",
                                        encoding="utf-8")
    w = e.run(LA, ["append-line", f"NOTE {EM} lane {LA}: the flag refused, {case} (T248)"],
              extra={"LANES_REGISTER_SCRATCH": str(attempt)})
    assert w.code == 0, f"[{case}] exit {w.code}: {w.err[-600:]}"
    assert w.snapshot_calls() and w.commit_calls(), f"[{case}] the run made no snapshot or commit call"
    assert len(e.journal_after()) == 1


@CLIENT
def test_the_scratch_flag_never_reaches_git_gh_or_tmux(estates):
    """The child unsets `LANES_REGISTER_SCRATCH` at once, so the logged
    environments of the `git` wrapper, the fake `gh` and the fake `tmux`
    never hold it, over a committed claim and a refused one."""
    e = estates()
    where = loggers(e)
    barrier = Barrier(e.root, 2)
    writers = [e.launch(lane, claim(OBJ), arms=[WINDOW], barrier=barrier, first=[where]) for lane in (LA, LB)]
    barrier.release()
    assert sorted(w.wait() for w in writers) == [0, 2]
    calls = tool_calls(where)
    assert {c["tool"] for c in calls} >= {"git", "gh"}, f"the loggers saw too little: {calls[:3]}"
    held = [c for c in calls if c["scratch"]]
    assert held == [], f"LANES_REGISTER_SCRATCH reached {sorted({c['tool'] for c in held})}"


@CLIENT
@pytest.mark.parametrize("case", ["parent-gone", "cap"])
def test_a_child_at_the_seam_stops_with_none_and_runs_no_tail(estates, case):
    """With its parent killed ([parent-gone]) or stopped by SIGSTOP at the
    cap (`LANES_REGISTER_SEAM_CAP_S=3`, [cap]) while it waits at the seam,
    the child writes `seam.out` as `none` and runs no tail: the fake `gh`
    makes no comment, and nothing is written. The parent's commit call is
    held by the shim and never sent. Rule 1's reads, made before the seam,
    are not the tail and are not counted (T248a)."""
    e = estates()
    where = loggers(e)
    fifo = e.root / "hold.fifo"
    os.mkfifo(str(fifo))
    w = e.launch(LA, claim(OBJ), first=[where], extra={"LANES_REGISTER_SEAM_CAP_S": "3"},
                 arms=[{"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(fifo)}])
    held = hold_point(fifo, w)
    try:
        os.kill(w.proc.pid, 9 if case == "parent-gone" else 19)
        deadline = time.monotonic() + 20
        while "none" not in "".join(seam_outs(e).values()):
            assert time.monotonic() < deadline, f"[{case}] no seam.out reads none: {seam_outs(e)}"
            time.sleep(0.1)
        time.sleep(0.5)
        assert comment_calls(where) == [], f"[{case}] the tail ran: {comment_calls(where)}"
        assert e.journal_after() == []
    finally:
        if case == "cap":
            os.kill(w.proc.pid, 18)
    assert held is not None  # never closed: the held commit call is never sent


@CLIENT
@pytest.mark.parametrize("decision", ["committed", "abandon"])
def test_seam_out_is_written_once_before_the_child_acts(estates, decision):
    """`seam.out` is written once, with noclobber: `tail` before the child
    acts on `committed` (the fake `gh`'s comment, the claim's tail, sees
    `tail`), and `none` before it acts on `abandon` (the refused claim's
    child runs no tail). No `seam.out` holds anything else. Only `gh`'s
    comment calls are read, never Rule 1's reads (T248a)."""
    e = estates()
    where = loggers(e)
    if decision == "committed":
        w = e.run(LA, claim(OBJ), first=[where])
        assert w.code == 0, w.err[-600:]
        gh = comment_calls(where)
        assert gh and all(set(c["seams"].values()) == {"tail"} or set(c["seams"].values()) == {"tail\n"}
                          for c in gh), f"gh's comment saw no seam.out reading tail: {gh}"
    else:
        assert e.run(LB, claim(OBJ, "--no-github")).code == 0
        w = e.run(LA, claim(OBJ), first=[where])
        assert w.code == 2, w.err[-600:]
        assert comment_calls(where) == [], "the abandoned attempt ran its tail"
    for path, said in seam_outs(e).items():
        assert said.strip() in ("tail", "none") and said.count("\n") <= 1, f"{path}: {said!r}"


# ============================================================ PHASE N: AT-F5 group A, the act's client half (T233)
#
# AT-F5 (TP:5818-5946; Y:5567-5624): lane 4's L4-A2, group A, which is T410's
# `act-begin` with `--rebase` and the client's checks on `LANES_ACT` and
# `LANES_EXPECT`, and T411's `canon-lane --walk`. They are written to the
# test plan's text and B14's T410 and T411 bullets: L4-A2 is in no bundle
# lane 4 has shared (its share folder holds T409, T413 and T419 only), and
# neither verb is in line R's merge10.
#
# Off primary, and `canon-lane --walk`, they run in files mode with no engine,
# on `test_lane_start_claude_current`'s `Sandbox` (`LANES_INDEX=off`) with a
# `psql` first on `PATH` that only logs its calls, so they are red at the base
# by their own assertions. The others run on test 4's estate at `primary`
# (T243's `Estate`), each writer with its own `psql` log, and skip without
# PostgreSQL 16. Every case FAILS UNTIL L4-A2 (lane 4's T410 and T411) and
# L1-A9 land.

WALK_A, WALK_B = "repoWA-1", "repoWB-1"
#: The walk's alias lines on test 4's estate: `a` to `b`, `b` to `c` (LC, which has a row).
WALK_ALIASES = f"{WALK_A}\t{WALK_B}\t2026-10-01T00:00:00Z\n{WALK_B}\t{LC}\t2026-10-01T00:00:00Z\n"
_ACT_ID = re.compile(r"^([0-9a-f]{32})@")


class FilesBox(Sandbox):
    """A files-mode workstation (`Sandbox`) with rows of its own, an alias
    table, and a `psql` that logs each call and answers nothing."""

    def __init__(self, root: Path, rows: Sequence[str] = (), aliases: Sequence[Tuple[str, str]] = ()) -> None:
        super().__init__(root)
        self.psql_log = root / "psql.log"
        _write(self.fakebin / "psql", f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "{self.psql_log}"\nexit 2\n')
        lanes = self.wip / "lanes"
        with open(lanes / "LANES.md", "a", encoding="utf-8") as handle:
            for lane in rows:
                handle.write(f"| `{lane}` | harness `{session_of(lane)}` | Eagle / test / brett "
                             f"| 2026-10-01T00:00Z | none | handoffs/{lane}.md "
                             f"| LIVE {DOT} 2026-10-01T00:00:00Z {DOT} working |\n")
        if aliases:
            (lanes / "aliases.tsv").write_text(
                "# old\tnew\tutc\n" + "".join(f"{old}\t{new}\t2026-10-01T00:00:00Z\n" for old, new in aliases),
                encoding="utf-8")
        if rows or aliases:
            self.git("-C", str(self.wip), "add", "-A")
            self.git("-C", str(self.wip), "commit", "-q", "-m", "T233's register")
            self.git("-C", str(self.wip), "push", "-q", "origin", "main")
            self.git("-C", str(self.ws), "pull", "-q", "--ff-only")

    def edit(self, *argv: str, env: Optional[dict] = None) -> subprocess.CompletedProcess:
        full = dict(self.env, **(env or {}))
        return subprocess.run([str(self.bin / "lanes-edit.sh"), *argv], env=full, cwd=str(self.lane_dir),
                              capture_output=True, text=True, timeout=120, check=False,
                              stdin=subprocess.DEVNULL)

    def psql_calls(self) -> List[str]:
        return self.psql_log.read_text(encoding="utf-8").splitlines() if self.psql_log.exists() else []


def test_act_begin_prints_its_base_and_touches_no_database_off_primary(tmp_path):
    """Off primary `act-begin` prints `<act-id>@files`, the id 32 lower-case
    hex digits, new for every act, and touches no database: the `psql` on
    `PATH` is never called (TP:5828-5830; Y:5571-5575; T410)."""
    box = FilesBox(tmp_path / "box")
    first, second = box.edit("act-begin"), box.edit("act-begin")
    for r in (first, second):
        assert r.returncode == 0, f"act-begin exited {r.returncode}: {r.stderr[-600:]}"
        assert re.fullmatch(r"[0-9a-f]{32}@files\n", r.stdout), f"act-begin printed {r.stdout!r}"
    assert first.stdout != second.stdout, "two acts were given one id"
    assert box.psql_calls() == [], f"act-begin off primary called psql: {box.psql_calls()}"


#: `canon-lane --walk`'s cases (TP:5866-5873): the rows, the alias lines, the
#: typed name, and the names the walk prints.
WALKS = {
    "two-hops": ((LC,), ((WALK_A, WALK_B), (WALK_B, LC)), WALK_A, [WALK_A, WALK_B, LC]),
    "no-alias": ((LC,), (), LC, [LC]),
    "refused": (("repoWR-1", "RepoWR-1"), (), "repoWR-1", []),
}


@pytest.mark.parametrize("case", list(WALKS))
def test_canon_lane_walk_prints_each_hop_with_canon_lanes_exit_code(tmp_path, case):
    """[two-hops]: alias lines lead `a` to `b` and `b` to `c`, which has a
    row; `canon-lane --walk a` prints `a`, `b` and `c`, one per line, the typed
    name first, and exits as `canon-lane a` does. [no-alias]: the lane alone.
    [refused]: where `canon-lane` refuses (two rows that differ only by case,
    its 2), the walk exits with the same code and prints nothing on stdout
    (T411)."""
    rows, aliases, typed, names = WALKS[case]
    box = FilesBox(tmp_path / "box", rows, aliases)
    plain = box.edit("canon-lane", typed)
    walk = box.edit("canon-lane", "--walk", typed)
    assert (plain.returncode != 0) == (case == "refused"), f"[{case}] canon-lane exited {plain.returncode}"
    assert walk.returncode == plain.returncode, (
        f"[{case}] the walk exited {walk.returncode}, canon-lane {plain.returncode}: {walk.stderr[-600:]}")
    assert walk.stdout.splitlines() == names, f"[{case}] the walk printed {walk.stdout!r}, not {names}"
    if case == "refused":
        # The refusal is canon-lane's own (its two-rows note), not a refusal of the flag.
        assert "differ only by case" in walk.stderr, f"[{case}] not canon-lane's refusal: {walk.stderr[-600:]}"


def test_canon_lane_walk_whose_register_read_fails_off_primary_exits_1_and_prints_nothing(tmp_path):
    """Off primary, where the register cannot be read, `canon-lane --walk`
    exits 1 and prints nothing on stdout: a read that failed is never "no
    row" (R22; Amendment 7(d)), so the walk lists no name from a register
    nobody read (lane 3, #165 6827722997, Q-A and item 3; lane 4's E5;
    T233b). A failed files read is never cached, so `canon_lane`, which
    still reads that failure as no row, answers, and the walk's own read of
    the register fails again. `canon-lane`'s own answer is not asserted: its
    reading is a follow-up item for its own ruling.

    The register is made unreadable as `test_lanes_index`'s `_unreadable`
    makes a published object unreadable: the loose object of `lanes/LANES.md`
    at `origin/main`, which the checkout wrote itself, is moved aside, so its
    `git show` fails while every other object reads, the alias table among
    them. First, with the register readable, the same walk prints its three
    names, so the 1 is the failed read's.

    It fails until lane 4's T411 lands with its `b637ce0d`, which ends the
    walk with a failed register read's own status, the 1 here (#165 6814837872,
    Question 126). Without T411, as on line R before merge44 (round 6d's
    census), `canon-lane --walk` is the usage 64, "canon-lane takes one
    lane" (lane 1, #165 6837462215 and 6850698453); with
    only T411's first commit, `2ee320e1`, as at pair-m33a `8ba10b4e`, the
    walk still reads that failure as no row and exits 0 with its three names
    (lane 4's pair-m33a CI, s2 15, read by lane 2's triage, #165 6838261062;
    T233c, T233d, T233e)."""
    rows, aliases, typed, names = WALKS["two-hops"]
    box = FilesBox(tmp_path / "box", rows, aliases)
    walk = box.edit("canon-lane", "--walk", typed)
    assert (walk.returncode, walk.stdout.splitlines()) == (0, names), (
        f"with the register readable the walk exited {walk.returncode} and printed {walk.stdout!r}: "
        f"{walk.stderr[-600:]}")
    sha = box.git("-C", str(box.wip), "rev-parse", f"origin/main:{LANES_MD}").strip()
    blob = box.wip / ".git" / "objects" / sha[:2] / sha[2:]
    assert blob.is_file(), f"the register's blob {sha} is not a loose object of {box.wip}"
    blob.rename(blob.with_name(blob.name + ".aside"))
    walk = box.edit("canon-lane", "--walk", typed)
    assert walk.returncode == 1, (
        f"the walk over a register that could not be read exited {walk.returncode}, not 1: {walk.stderr[-600:]}")
    assert walk.stdout == "", f"the walk over a register that could not be read printed {walk.stdout!r}"


@CLIENT
@pytest.mark.parametrize("case", ["present", "switch-at-files", "snapshot-fails"])
def test_act_begin_on_primary_prints_id_seq_and_generation(estates, case):
    """[present]: on primary `act-begin` prints 32 lower-case hex digits, `@`,
    the head seq with no leading zero, `:` and the switch's generation as a
    lower-case uuid, and the shim's log holds its one snapshot call.
    [switch-at-files] (the cutover aborted by `switch_to_files`, which aborts
    only a cutover left unconfirmed, the marker `adding`, so this estate's
    cutover gets no `record_marker`) and [snapshot-fails] (the shim fails the
    call): exit 69, nothing on stdout (TP:5874-5878; T410)."""
    e = estates(confirmed=case != "switch-at-files")
    arms = []
    if case == "switch-at-files":
        aborted = e.c.call(ABORT_SQL, client=e.c.client(), seq=e.c.head(), lane=OPERATOR, ws=WS)
        assert aborted.returncode == 0 and e.c.switch()["mode"] == "files", aborted.stderr
    elif case == "snapshot-fails":
        arms = [{"mode": "fail-call", "call": 1}]
    w = e.run(LA, ["act-begin"], arms=arms)
    if case != "present":
        assert (w.code, w.out) == (69, ""), f"[{case}] exit {w.code}, stdout {w.out!r}: {w.err[-600:]}"
        return
    gen = e.c.switch()["generation"]
    assert w.code == 0, f"exit {w.code}: {w.err[-600:]}"
    assert re.fullmatch(r"[0-9a-f]{32}@" + str(e.c.head()) + ":" + re.escape(gen) + r"\n", w.out), (
        f"act-begin printed {w.out!r}, not <id>@{e.c.head()}:{gen}")
    assert len(w.calls()) == 1, f"act-begin made {len(w.calls())} calls, not its one snapshot"


@CLIENT
def test_act_begin_rebase_keeps_the_id_and_takes_the_new_base(estates):
    """`act-begin`; a rival touches one of the act's scopes; `act-begin
    --rebase` prints the same id with the head seq then and the switch's
    generation; the act's write on that scope commits; a second rival entry
    after the new base on the same scope still refuses it with 2
    (TP:5850-5858; Y:5591-5595; T410)."""
    e = estates()
    act = act_begin(e)
    scope = f"objects:{LA.lower()}"
    other = {"LANES_SESSION": "dddddddd-0233-4000-8000-00000000d233"}
    assert e.run(LA, act_write(e, "objects", tag="rival-1"), extra=other).code == 0
    rebased = e.run(LA, ["act-begin", "--rebase"], extra={"LANES_ACT": act})
    gen = e.c.switch()["generation"]
    assert rebased.code == 0, f"--rebase exited {rebased.code}: {rebased.err[-600:]}"
    assert rebased.out == f"{_ACT_ID.match(act).group(1)}@{e.c.head()}:{gen}\n", (
        f"--rebase printed {rebased.out!r}; the act was {act}, the head is {e.c.head()}")
    new = rebased.out.strip()
    w = e.run(LA, act_write(e, "objects", tag="after-rebase"), extra=acted(new, scope))
    assert w.code == 0, f"the act's write after its rebase exited {w.code}: {w.err[-600:]}"
    assert e.run(LA, act_write(e, "objects", tag="rival-2"), extra=other).code == 0
    late = e.run(LA, act_write(e, "objects", tag="after-rival-2"), extra=acted(new, scope))
    assert late.code == 2 and f"expectation: {scope} changed" in late.err, (late.code, late.err[-600:])


@CLIENT
@pytest.mark.parametrize("case", ["malformed", "files-base", "generation-changed"])
def test_act_begin_rebase_refuses_with_2(estates, case):
    """`act-begin --rebase` refuses with 2, printing nothing and writing
    nothing, where `LANES_ACT` is malformed (the old `<id>@<seq>`), where its
    base is `files` on primary, and where its generation is not the switch's
    (TP:5859-5861; T410)."""
    e = estates()
    act = {"malformed": f"{'a' * 32}@{e.c.head()}", "files-base": f"{'a' * 32}@files",
           "generation-changed": f"{'a' * 32}@{e.c.head()}:{uuid.uuid4()}"}[case]
    state = e.c.state()
    w = e.run(LA, ["act-begin", "--rebase"], extra={"LANES_ACT": act})
    assert (w.code, w.out) == (2, ""), f"[{case}] exit {w.code}, stdout {w.out!r}: {w.err[-600:]}"
    assert e.c.state() == state


#: The client's checks before the first snapshot (TP:5879-5887; Y:5597-5605):
#: each case's `LANES_ACT` and `LANES_EXPECT` pairs, `None` for unset, and the
#: variable the refusal names. `{act}` is a well-formed base from `act-begin`.
BAD_ACTS = {
    "malformed": ([(f"{'a' * 32}@1", "objects:{lane}"), (f"{'a' * 32}@1:{'A' * 8}-0000-4000-8000-{'0' * 12}", ""),
                   ("{id}@01:{gen}", "")], "LANES_ACT"),
    "expect-without-act": ([(None, "objects:{lane}"), ("", "objects:{lane}")], "LANES_EXPECT"),
    "bad-scope": ([("{act}", "*"), ("{act}", "row:*"), ("{act}", "lane:{lane}")], "LANES_EXPECT"),
    "files-base": ([("{id}@files", "objects:{lane}")], "LANES_ACT"),
}


@CLIENT
@pytest.mark.parametrize("case", list(BAD_ACTS))
def test_the_client_refuses_a_bad_act_with_2_before_any_call(estates, case):
    """On primary a write whose `LANES_ACT` is malformed (the old form, an
    upper-case uuid, a seq with a leading zero), whose `LANES_EXPECT` is set
    with no `LANES_ACT`, whose scope is outside the six forms (`*` and `row:*`
    among them), or whose base is `files` (the text naming `<id>@files`)
    exits 2 naming the variable, with the shim's log empty and nothing
    written (TP:5879-5887; T410)."""
    e = estates()
    act = act_begin(e)
    ident, gen = _ACT_ID.match(act).group(1), e.c.switch()["generation"]
    pairs, variable = BAD_ACTS[case]
    for raw_act, raw_expect in pairs:
        state = e.c.state()
        extra = {"LANES_EXPECT": raw_expect.format(lane=LA.lower())}
        if raw_act is not None:
            extra["LANES_ACT"] = raw_act.format(act=act, id=ident, gen=gen)
        w = e.run(LA, act_write(e, "objects", tag=case), extra=extra)  # unset: the estate never carries it
        assert w.code == 2, f"[{case}] {extra}: exit {w.code}: {w.err[-600:]}"
        assert variable in w.err, f"[{case}] {extra}: the refusal does not name {variable}: {w.err[-600:]}"
        if case == "files-base":
            assert f"{ident}@files" in w.err, w.err[-600:]
        assert w.calls() == [], f"[{case}] {extra}: a call was made: {w.calls()}"
        assert e.c.state() == state, f"[{case}] {extra}: the register changed"


# ============================================================ PHASE W: AT-F5 group B, acts racing (T252)
#
# F5 (D5; lane 4's section, "The acts and their expectations"): an act runs
# `act-begin`, exports `LANES_ACT=<id>@<n>:<generation>`, and each write
# carries `LANES_EXPECT="<scope> ..."`; the commit refuses with LR009, the
# writer with 2, `expectation: <scope> changed at seq <k> by <lane>/<verb>`,
# when an entry of another act touched a listed scope after the base. The two
# race functions run lane 4's acts to each write of its tables, on a world of
# their own (T252b, below). The other cases run on test 4's estate (T243's
# `Estate`), where the writes are `append-line` of a row-shaped line
# (`row:<L>`) and `log` (`objects:<L>`), a reading of lane 1's derived keys.
# The five cases that read lane 4's tools' text now run their flows on
# T252b's world (lane 3's batch 7, item 5): `[lane-end-gate]` and
# `[skill-step-4]` (T252f) and `[lane-start-reread]` (T252i) at the three
# conditions below, and the two launches (T252h) after them. They FAIL UNTIL
# L1-A6, L4-A2 (T410), L4-B3 and L4-B14 land; without PostgreSQL 16 the RE
# cases skip.

ACT_RE = re.compile(r"^[0-9a-f]{32}@[1-9][0-9]*:" + UUID_RE + r"$|^[0-9a-f]{32}@0:" + UUID_RE + r"$")


def act_begin(e: Estate, lane: str = LA) -> str:
    w = e.run(lane, ["act-begin"])
    act = w.out.strip()
    assert w.code == 0 and ACT_RE.match(act), f"act-begin exited {w.code}, printed {w.out!r}: {w.err[-300:]}"
    return act


def act_write(e: Estate, scope: str, lane: str = LA, tag: str = "") -> List[str]:
    """The act's write on `scope`, `row` or `objects`. The `objects` write is
    an object-kind line, `OPENED` on `opensoft/r9#77`: `NOTED` has been a
    lane-kind line since Amendment 13(b) (`aa6cf53d`), so `log NOTED` on an
    object is refused with 2 before any write (T252l)."""
    if scope == "row":
        return ["append-line", f"| `{lane}` | harness `{session_of(lane)}` | {W_WS} / test / brett "
                               f"| 2026-05-01T00:00Z | none | handoffs/{lane}.md | T252 row {tag} |"]
    return ["log", "OPENED", f"{KEY}#77", f"T252 {tag}"]


def acted(act: str, *scopes: str) -> dict:
    return {"LANES_ACT": act, "LANES_EXPECT": " ".join(scopes)}


# ---------------------------------------- the race, on each write of lane 4's tables (T252b)
#
# TP:5848-5853 parametrise the race "for each write of lane 4's tables", and
# lane 3's batch 7 (ruling 5) takes one id per write and drops `[row|objects]`,
# since T233's group A cases hold the commit's half. So each case runs the act,
# lane 4's own tool, to that write on a workstation at `primary`; the shim
# holds that write's commit call; a rival from a second session commits; and
# the hold is let go (TP:5854-5856). The rival writes the lane's own `PAUSED`
# in its log, as a forced release does (Y:5673): a lane-kind line, `bind:<L>`,
# which every write of the tables lists (Y:5640-5680), W1's new lane among
# them (`new-lane`, below). The held case's rival writes that `PAUSED` (or,
# for W1, a row line) for another lane, which no write of the act lists,
# whatever the act's own rival is (`held_rival`).
#
# THE RIVAL LEAVES THE VERB'S ANSWER AS IT WAS (lane 3's ruling, option (b),
# #165 6860075071). It commits after the attempt's snapshot, so the held
# commit has lost its turn (LR001, Y:2570), and a new attempt runs the verb
# again, on the register with the rival in it (Y:2546-2552, Y:2602). Where
# the verb itself decides on a scope the act lists, a rival that changes its
# answer ends the act before any commit, and LR009 is never met. So:
# - W8's `request-handoff` reads the lane's binding, and a `PAUSED` makes it
#   answer 8 (`7893339:lanes-edit.sh:31788-31791`), after which `lane-start`
#   goes on (Y:5656). Its rival is the holder's `RESUMED` from the holder's
#   own place, Falcon (`resumed`), which leaves the lane bound elsewhere;
#   from the act's own window `request-handoff` would refuse first
#   (`:31808-31810`). `lane`'s `request-handoff` takes the same rival.
# - `retire-rows` proves again that the row is dormant, and refuses 2 on a
#   live session here and on any lane-kind line in its log
#   (`7893339:lanes-edit.sh:24740-24837`). Its rival appends an id that no
#   session record holds to the row's session cell, a write on `row:<L>`
#   that leaves the row dormant (`session-id`).
# - W1's `add-row` refuses 2 where its lane has a row, "already has a row
#   ... (Amendment 15(a))" (`add_row_checks`,
#   `44f487d1:lanes-edit.sh:15341-15361`), and reads no lane-kind line. So
#   its rival is the new lane's own `PAUSED` in its log (`new-lane`), a
#   `bind:<L>` line that W1's `LANES_EXPECT` lists (`ls_expect_for`,
#   `44f487d1:lane-start:4621`, called at `:4672`) and that leaves the lane
#   without a row, so the retried `add-row` passes its checks and its
#   commit meets LR009 (lane 3, #165 6869860086, taking 6860075071's rule;
#   T252y). UNTIL T252y its rival was a row line for it, `row:<L>`, and the
#   retried `add-row` refused 2 before any commit call, so this id never
#   reached LR009 (lane 4's R6J-A, #165 6869806372).
#
# THE WORLD is `test_lane_start_claude_current`'s `Sandbox` (fake `tmux`,
# `claude` and `gh`) holding the register N1's arms run on (lane 2's T217):
# repoA-1 PAUSED here, repoA-2 LIVE here, repoA-3 LIVE on Falcon, repoH-1
# DORMANT, and no repoZ-1. It is imported into a clone of `tmpl`
# that `Clone.to_primary` brings to `primary`, with the flipped `lanes-index`
# beside `lanes-edit.sh`, `mode=primary` configured, and its `PATH` masked
# (`_masked_path`, its own bin spared its `lanes-index`), as test 4's estate is.
# Each of its five lanes has its own register checkout beside W, the
# `workspace.yaml` checkout `ws` (`ActWorld.lane_checkout`; lane 3's (119)).
# Readings: each act's argv (N1's arms at `2a057a6d`, with `--no-launch` for
# W1, `lane-end --retire-dormant` and `lane --request-handoff`); the write's
# commit call, found by a text its entry's JSON carries (its verb, or its
# line's kind, lane or state); the skill's step-4 block, the fenced block of
# its section 4 that opens with `act-begin`; and the guard's child, run as
# T502 writes its body, `guard-bind --body <uuid>`, whose record's path T502
# owns: the world writes that record, `mode=binding`, and gives the window
# the session it binds, live and named for its lane, as the guard's answer 2
# leaves them for its child (`ActWorld.offer`, `guard_session`; T252q).
#
# `lane-end`'S CLOSE-OUT GATE (T252g): every `lane-end` act runs with
# `LANE_WORKTREES` set to a stand-in that prints nothing and exits 0, as
# `[lane-end-gate]`'s does, so the gate finds nothing left and W13 and W14 are
# reached. Without it the gate runs whatever `lane-worktrees` the host has:
# py-bench's own `/usr/local/bin/lane-worktrees`, and on a host with none an
# exit 127, on which `lane-end` refuses 1 before W13 (round 5, #165
# 6810924785; OR12's report). `--retire-dormant` exits after `retire-rows`,
# before the gate (`lane-end:764-952` at V-round5), and never runs it.
#
# They FAIL UNTIL L1-A6, L4-A2 (T410, T411), L4-B3, L4-B5 and L4-B14 (T428 to
# T432) land; the skill's id also until T431's block, and the guard's until
# T502's `guard-bind` and T510's expectations on its `set-row-state`. Without
# PostgreSQL 16 each skips.

#: The em dash as the entry's ASCII JSON spells it.
EM_JSON = json.dumps(EM)[1:-1]
#: The world's lanes (N1's arms) and their sessions.
R_PAUSED, R_HERE, R_FAR, R_DORMANT, R_NEW = "repoA-1", "repoA-2", "repoA-3", "repoH-1", "repoZ-1"
R_SID = {R_PAUSED: "aaaaaaaa-0002-4000-8000-00000000a002", R_HERE: "aaaaaaaa-0003-4000-8000-00000000a003",
         R_FAR: "aaaaaaaa-0253-4000-8000-00000000a253", R_DORMANT: "aaaaaaaa-0254-4000-8000-00000000a254",
         R_NEW: "aaaaaaaa-0255-4000-8000-00000000a255"}
#: repoH-1's state cell (T252j). `lane-end --retire-dormant <repo>` retires
#: only DORMANT rows, "a row with no object log and no live session here"
#: (Amendment 19(a); `lanes-edit.sh lanes --closed`), and a cell in Amendment
#: 13's phrase whose word is not ENDED, RETIRED or MIGRATED keeps a row with
#: no log listed. So repoH-1 has no log and this cell, which is no phrase.
DORMANT_CELL = "parked long ago, before every lane had a log"
#: For each lane, a lane that none of its acts' writes lists (the held case).
R_OTHER = {R_PAUSED: R_FAR, R_HERE: R_FAR, R_FAR: R_HERE, R_DORMANT: R_FAR, R_NEW: R_FAR}
#: The id the `session-id` rival appends to a row's session cell: no session
#: record holds it, so it is live nowhere.
RIVAL_SID = "aaaaaaaa-0259-4000-8000-00000000a259"


def verb_is(verb: str) -> str:
    return f'"verb":"{verb}"'


def lane_line(kind: str, lane: str) -> str:
    return f"{kind} {EM_JSON} lane {lane}"


#: Each rival's kind (`ActWorld.rival`): the scope prefix and the verb of its
#: entry, which the refused write's `expectation:` line names (`commit_write`'s
#: LR009, `7893339:lanes-index:9981-9983`), and the kind the held case writes
#: for another lane.
#: `new-lane` is W1's (T252y): the `bind` rival's `PAUSED`, for a lane with no
#: row, whose held case keeps W1's row line for another lane, as before.
RIVALS = {"bind": ("bind", "log", "bind"), "row": ("row", "append-line", "row"),
          "resumed": ("bind", "log", "bind"), "session-id": ("row", "append-session-id", "bind"),
          "new-lane": ("bind", "log", "row")}


class ActWrite:
    """One write of lane 4's tables: the act that makes it (`tool`, `argv`),
    the lane it writes, its commit call (`match`, a text its entry carries,
    the first commit call that carries it), the rival's kind (`rival`, one
    of `RIVALS`), its entry's scope prefix and verb (`rival_scope`,
    `rival_verb`) and the held case's rival (`held_rival`), and the act's
    exit where lane 4's arm names one for a refused write (`code`; else only
    never 0)."""

    def __init__(self, tool: str, argv: Tuple[str, ...], lane: str, match: str, rival: str = "bind",
                 code: Optional[int] = None, env: Optional[dict] = None) -> None:
        self.tool, self.argv, self.lane, self.match = tool, argv, lane, match
        self.rival, self.code, self.env = rival, code, env or {}
        self.rival_scope, self.rival_verb, self.held_rival = RIVALS[rival]


_HANDOFF = ("--lane", R_HERE, "T252b's race")
#: TP:5848-5853's list, in its order: `lane-start`'s W1, W8 and `start-record`
#: (W2 to W7); `lane-handoff`'s late `log PAUSED --utc`, W9, W11 and W12;
#: `lane-end`'s W13, W14 and `retire-rows`; the handoff skill's step-4 writes;
#: the guard's answer 2, its child's `set-row-state` on the lane left; and
#: `lane`'s `request-handoff`. The codes: `start-record`'s and W1's 2 die 2
#: (T428, "any 2 dies"); W8's arm passes the code (T428); `:2817` keeps 2
#: (T429); W13 under `set -e` and W14's note arm exit with the writer's code
#: (T430); `lane`'s `2)` arm dies 2, as Y:5722 and Y:5740 say (T432; ERR-36;
#: `7893339:lane:1382-1386`; lane 3, #165 6860075071); the handoff skill's step-4
#: stop ends 2 alone, its writer's code staying in that writer's own stderr
#: (T431; lane 3's question 4, #165 6835210568; T252n); and the guard's child
#: ends 0, its refused `set-row-state` a `note=`, since the bind landed (lane
#: 3's point 4(b), #165 6841918192; T252s). W1 runs with `LANE_START_SESSION_ID=0`,
#: minting off: where a transcript uuid is knowable, T428 carries W1 inside the
#: one `start-record --add-row` call, and no commit call is `add-row`'s; with
#: none, W1 stays the separate `add-row` that TP:5848 names
#: (`f9e1449c:lane-start:4315-4320`, `:4363-4364`, `:4562-4563`, `:4640-4644`;
#: lane 2's TR21, section 2a, option 1; T252t). `[lane-start-w1-start-record]`
#: is W1's twin with minting on, the form every new lane takes where a uuid is
#: knowable: the act mints one (`:4315-4320`), and W1's row rides in the one
#: `start-record --add-row` call, with the union of the expectations
#: (`7893339:lane-start:4589-4612`, `:4626-4630`, `:5094-5097`); its 2 dies 2
#: (`:5129-5130`; T428; lane 2's RV23, SHOULD 2). Its rival is the lane's
#: `PAUSED` (`bind:<L>`), not a row: the retried attempt runs the verb again,
#: and a row for the lane makes `add_row_checks` refuse it 2, "already has a
#: row", before LR009 (`7893339:lanes-edit.sh:15352-15354`, `:29789`; lane 3's
#: option (b), #165 6860075071).
ACT_WRITES = {
    "lane-start-w1-add-row": ActWrite("lane-start", ("repoZ", "1", "--no-launch"), R_NEW,
                                      verb_is("add-row"), rival="new-lane", code=2,
                                      env={"LANE_START_SESSION_ID": "0"}),
    "lane-start-w1-start-record": ActWrite("lane-start", ("repoZ", "1", "--no-launch"), R_NEW,
                                           verb_is("start-record"), code=2),
    "lane-start-w8-request-handoff": ActWrite("lane-start", ("repoA", "3", "--request-handoff", "--dir",
                                                             "{lane_dir}"), R_FAR,
                                              verb_is("request-handoff"), rival="resumed", code=2),
    "lane-start-start-record": ActWrite("lane-start", ("repoA", "1"), R_PAUSED, verb_is("start-record"),
                                        code=2),
    "lane-handoff-late-paused": ActWrite("lane-handoff", ("--late", "--at", "{utc}", *_HANDOFF), R_HERE,
                                         lane_line("PAUSED", R_HERE), code=2),
    "lane-handoff-w9-log-paused": ActWrite("lane-handoff", _HANDOFF, R_HERE, lane_line("PAUSED", R_HERE)),
    "lane-handoff-w11-append-line": ActWrite("lane-handoff", _HANDOFF, R_HERE, verb_is("append-line")),
    "lane-handoff-w12-set-row-state": ActWrite("lane-handoff", _HANDOFF, R_HERE, verb_is("set-row-state")),
    "lane-end-w13-set-row-state": ActWrite("lane-end", (R_HERE,), R_HERE, verb_is("set-row-state"), code=2),
    "lane-end-w14-log-ended": ActWrite("lane-end", (R_HERE,), R_HERE, lane_line("ENDED", R_HERE), code=2),
    "lane-end-retire-rows": ActWrite("lane-end", ("--retire-dormant", "repoH", "--yes", "--reason=T252b's race"),
                                     R_DORMANT, verb_is("retire-rows"), rival="session-id",
                                     env={"LANES_LANE": R_HERE}),
    "skill-step-4-writes": ActWrite("skill", (), R_HERE, lane_line("PAUSED", R_HERE), code=2),
    "guard-answer-2-child": ActWrite("guard", ("guard-bind", "--body", R_SID[R_PAUSED]), R_HERE,
                                     verb_is("set-row-state"), env={"LANES_LANE": R_PAUSED}),
    "lane-request-handoff": ActWrite("lane", (R_FAR, "--request-handoff"), R_FAR, verb_is("request-handoff"),
                                     rival="resumed", code=2),
}


class ActWorld(Sandbox):
    """A workstation at `primary` whose lanes' acts run their own tools (see
    the section's head)."""

    def __init__(self, root: Path, c: "Clone") -> None:
        super().__init__(root)
        self.c = c
        for name in ("lane-end", "lane", "lane-handoff", "lanes"):
            shutil.copy2(str(REPO / name), str(self.bin / name))
            (self.bin / name).chmod(0o755)
        self.resolver()
        seat = "Eagle / test / brett"
        rows = [(R_PAUSED, seat, "2026-10-01T00:00Z", f"PAUSED {DOT} 2026-10-01T01:00:00Z {DOT} parked"),
                (R_HERE, seat, "2026-10-01T02:00Z", f"LIVE {DOT} 2026-10-01T02:00:00Z {DOT} working"),
                (R_FAR, "Falcon / test / brett", "2026-10-01T02:30Z",
                 f"LIVE {DOT} 2026-10-01T02:30:00Z {DOT} working elsewhere"),
                (R_DORMANT, seat, "2026-10-01T03:00Z", DORMANT_CELL)]
        lanes = self.wip / "lanes"
        (lanes / "log").mkdir(exist_ok=True)
        with open(lanes / "LANES.md", "a", encoding="utf-8") as handle:
            for lane, ws, utc, state in rows:
                handle.write(f"| `{lane}` | harness `{R_SID[lane]}` | {ws} | {utc} | none "
                             f"| handoffs/{lane}.md | {state} |\n")
        for lane, ws, utc, state in rows:
            if lane == R_DORMANT:
                continue  # a dormant row has no object log (Amendment 19(a); T252j)
            host = ws.split(" ")[0]
            text = (f"STARTED {EM} lane {lane}, session {R_SID[lane]}@{host}, {utc[:-1]}:00Z, "
                    f"lane:{lane} {ARROW} home opensoft/repoA; dir {self.lane_dir}; profile team-01a\n")
            if state.startswith("PAUSED"):
                text += (f"PAUSED {EM} lane {lane}, session {R_SID[lane]}@{host}, {state.split(' ')[2]}, "
                         f"lane:{lane} {ARROW} dir {self.lane_dir}; profile team-01a; agent claude; "
                         f"transcript {R_SID[lane]}\n")
            (lanes / "log" / f"{lane}.md").write_text(text, encoding="utf-8")
        self.git("-C", str(self.wip), "add", "-A")
        self.git("-C", str(self.wip), "commit", "-q", "-m", "T252b's register")
        self.git("-C", str(self.wip), "push", "-q", "origin", "main")
        self.git("-C", str(self.ws), "pull", "-q", "--ff-only")
        # Each world lane's own register checkout beside W (lane 3's (119)).
        self.checkouts = [self.lane_checkout(lane) for lane in R_SID]
        import_files(c, {str(p.relative_to(self.wip)): p.read_text(encoding="utf-8")
                         for p in sorted(lanes.rglob("*.md"))})
        assert c.to_primary() == 1, "T252b's cutover is not at seq 1"
        flipped_copy(LANES_INDEX, self.bin, True)
        conf = self.home / ".config" / "openRepoTools" / "lanes-index.conf"
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text(f"mode=primary\nregister_url={c.db.url(WRITER_LOGIN)}\nreader_url={c.db.url()}\n",
                        encoding="utf-8")
        conf.chmod(0o600)
        # Its own bin keeps the flipped copy's `lanes-index` (T243e's `_masked_path`).
        path = _masked_path(self.env["PATH"], spared={str(self.bin): ("lanes-index",)})
        self.env.pop("LANES_INDEX", None)
        self.env.update(PATH=path, LANES_INDEX_CONFIG=str(conf), LANES_EDIT=str(self.bin / "lanes-edit.sh"),
                        XDG_STATE_HOME=str(root / "state"), FAKE_CC_PATH=str(self.resolved),
                        LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none", LANES_IN_CONTAINER="0")
        self._n = itertools.count(1)
        self.writers: List[Writer] = []
        self.sessions: list = []  # the guard's live sessions (T252q), closed by `act_worlds`
        self.record: Optional[Path] = None  # the guard child's bind record (`offer`; T252s)

    def lane_checkout(self, lane: str) -> Path:
        """`<c>`, lane `lane`'s own register checkout beside this world's W,
        `ws`, which `workspace.yaml` names: `<W>-lanes/<lane>`, a clone of
        the world's origin, as `Estate.lane_checkout` makes one (lane 3's
        (119); see `write_lanes_of`). Each of the world's lanes gets one,
        made once the register is pushed, and each is pulled with W after a
        later push (`handoff`), so it is at W's commit."""
        real = Path(os.path.realpath(self.ws))
        target = real.parent / f"{real.name}-lanes" / lane
        target.parent.mkdir(parents=True, exist_ok=True)
        self.git("clone", "-q", str(self.origin), str(target))
        return target

    def psql_dir(self, name: str, arms: Sequence[dict] = ()) -> Path:
        return Estate.psql_dir(self, name, arms)  # the same stamp and shim as test 4's

    def launch(self, name: str, command: Sequence[str], lane: str, arms: Sequence[dict] = (),
               extra: Optional[dict] = None) -> Writer:
        psql = self.psql_dir(f"{next(self._n):02d}-{name}", arms)
        env = dict(self.env, LANES_LANE=lane, LANES_SESSION=R_SID[lane])
        env.update(extra or {})
        env["PATH"] = str(psql) + os.pathsep + env["PATH"]
        proc = subprocess.Popen(list(command), cwd=str(self.lane_dir), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                                errors="replace", start_new_session=True)
        writer = Writer(name, lane, proc, psql)
        self.writers.append(writer)
        return writer

    def act(self, write: ActWrite, arms: Sequence[dict]) -> Writer:
        """The act that makes `write`, run by its own tool."""
        if write.tool == "skill":
            # Step 4's block with the skill's prelude and steps 1 and 2's
            # values, as the flow case runs it, `L` being this world's
            # `lanes-edit.sh`: alone, the block's `"$L" act-begin` ran an
            # empty command and exited 127 (T252p).
            command, extra = skill_step_4_command(self, skill_prelude_block(), skill_step_4_block(),
                                                  write.lane, "race", self.bin / "lanes-edit.sh")
            return self.launch("skill", command, write.lane, arms, dict(extra, **write.env))
        if write.tool == "guard":
            # What the guard's answer 2 leaves its child: the record, which
            # says `mode=binding`, and this window renamed for the lane it
            # binds, with the session it binds live in it (`guard_session`,
            # T203c's: a live process, its record naming `testsess:@1.%1`, and
            # a stand-in `tmux` that answers for that window). With neither,
            # `guard-bind --body` refused 2, "does not say mode=binding (it
            # says nothing)"; with the record alone, `lane-start --bind`
            # refused 2, "no live session record names this window" (T252q).
            sid, to = write.argv[-1], dict(self.env, **write.env)["LANES_LANE"]
            self.record = self.offer(sid, write.lane, to)
            live = guard_session(self.home, self.root / "guard-session", self.lane_dir, window=to,
                                 session_id=sid)
            self.sessions.append(live)
            extra = dict(live.env({"PATH": self.env["PATH"]}), LANES_SESSION=sid, **write.env)
            return self.launch("guard", ["bash", str(self.bin / "lanes-edit.sh"), *write.argv], write.lane,
                               arms, extra)
        utc = self.c.value("SELECT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"');")
        argv = [a.format(lane_dir=self.lane_dir, utc=utc) for a in write.argv]
        extra = dict(write.env)
        if write.tool == "lane-end":
            extra.setdefault("LANE_WORKTREES", str(self.gate_stand_in()))
        return self.launch(write.tool, [str(self.bin / write.tool), *argv], write.lane, arms, extra)

    def offer(self, sid: str, left: str, to: str) -> Path:
        """The bind's record for session `sid`, as the name guard's answer 2
        leaves it for its child, `guard-bind --body <sid>` (T502;
        `contracts/bind-record.md`): `guard_offer`'s lines, the window's lane
        `left` and the session's lane `to`, rewritten by `guard_answer`'s
        choice 2 to `mode=binding` with the attempt's first keys, `mode`
        first. It is `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/lanes/offers/<sid>`
        (`guard_offer_file`), 0600 in a 0700 `offers/`, beside the attempt's
        empty `.bind.1.out`, which the outer's fork creates. No prefetch ran,
        so the record has no `c`, `n_a` or `w_s_ms`, and `bound_s` is
        `guard_bind_bound_s`'s default, 500. `guard_bind_body` reads `mode`,
        `from`, `to`, `out` and `act`, binds `to` with `lane-start --no-launch
        --bind`, and then sets `left`'s row (T252q).

        ITS `act` is the guard's base at the offer, `<act-id>@<n>:<generation>`
        (tasks:1426; W:5378), which `guard_offer` writes after `pane`; here it
        is taken from `act-begin` on primary (Y:5572), before the rival
        commits. Without it the `set-row-state` on `left` sends `LANES_EXPECT`
        with no `LANES_ACT`, which the client refuses with 2 before any commit
        call (T510's part 5), so the race never reaches its hold (lane 3,
        #165 6841918192, point 4(b); lane 5, #165 6842157774; T252s)."""
        begun = self.launch("act-begin", ["bash", str(self.bin / "lanes-edit.sh"), "act-begin"], left)
        begun.wait(60)
        act = begun.out.strip()
        assert begun.code == 0 and ACT_RE.match(act), (
            f"act-begin for the offer's act exited {begun.code}, printed {begun.out!r}: {begun.err[-300:]}")
        offers = Path(self.env.get("CLAUDE_CONFIG_DIR") or Path(self.env["HOME"]) / ".claude") / "lanes" / "offers"
        offers.mkdir(parents=True, exist_ok=True)
        offers.chmod(0o700)
        record = offers / sid
        now = int(time.time())
        utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        bound_s = 500
        lines = ["mode=binding", f"from={left}", f"to={to}", f"session={to}", f"uuid={sid}", f"utc={utc}",
                 "window=", "pane=", f"act={act}", "bind=1", f"started_utc={utc}", f"bound_s={bound_s}", "bounded=yes",
                 f"deadline_epoch={now + bound_s + 5}", f"host={self.env['LANES_WORKSTATION']}",
                 f"container={self.env['LANES_CONTAINER']}", f"out={record}.bind.1.out", "detach=setsid"]
        for path, text in ((record, "\n".join(lines) + "\n"), (Path(f"{record}.bind.1.out"), "")):
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
        return record

    def handoff(self, lane: str) -> None:
        """The lane's handoff file, at the path its row names, committed and
        published, as a live lane has one (T252h): `lane-handoff --restart`
        respawns nothing over a handoff it could not refresh."""
        path = self.wip / "handoffs" / f"{lane}.md"
        path.write_text(f"# handoff {EM} lane {lane}\n\nT252h's world: the lane's handoff before its /ctx.\n",
                        encoding="utf-8")
        self.git("-C", str(self.wip), "add", "--", f"handoffs/{lane}.md")
        self.git("-C", str(self.wip), "commit", "-q", "-m", f"handoff({lane}): T252h's world")
        self.git("-C", str(self.wip), "push", "-q", "origin", "main")
        self.git("-C", str(self.ws), "pull", "-q", "--ff-only")
        for checkout in self.checkouts:
            self.git("-C", str(checkout), "pull", "-q", "--ff-only")

    def gate_stand_in(self) -> Path:
        """`lane-end`'s close-out gate for the race's acts (T252g): a
        `LANE_WORKTREES` stand-in that logs its argv and `LANES_ACT`, prints
        nothing and exits 0, so the gate passes and the act goes on to its
        write (see the section's head)."""
        return act_logger(self.root / "race-gate", "lane-worktrees")

    def rival(self, kind: str, lane: str) -> Writer:
        """A second session's write (`RIVALS`): `bind`, the lane's own
        `PAUSED` in its log (lane-handoff's W9 form); `new-lane`, the same
        `PAUSED`, W1's, for a lane with no row, which it leaves without one
        (T252y); `row`, a row line for the lane; `resumed`, the lane's
        `RESUMED`, written by its own session
        from the holder's place, Falcon (`LANES_WORKSTATION`, `LANES_HOST`),
        which leaves the lane bound there: `lane_binding_scan` reads a
        `RESUMED` as `bound` (`7893339:lanes-edit.sh:19808-19815`), at the
        `host` that `binding_subfields_add` writes into its payload
        (`:15157-15158`), and that host is not this one; `session-id`, an
        id that no session record holds, `RIVAL_SID`, appended to the lane's
        session cell by `append-session-id`, as `[lane-start-reread]`'s
        holder appends one: a dormant row stays dormant, since `retire-rows`
        refuses only an id that is live here (`7893339:lanes-edit.sh:24740-24751`)."""
        edit = ["bash", str(self.bin / "lanes-edit.sh")]
        extra: dict = {}
        if kind in ("bind", "new-lane"):
            argv = ["log", "PAUSED", f"lane:{lane}", ARROW, "T252b's rival", "the rival's release"]
        elif kind == "resumed":
            argv = ["log", "RESUMED", f"lane:{lane}", ARROW, "T252b's rival", "the holder resumes in place"]
            extra = {"LANES_WORKSTATION": "Falcon", "LANES_HOST": "falcon"}
        elif kind == "session-id":
            argv = ["append-session-id", lane, R_SID[lane], f"{ARROW} harness `{RIVAL_SID}`",
                    "T252b's rival: an id no session holds"]
        else:
            argv = ["append-line", f"| `{lane}` | harness `{R_SID[lane]}` | Eagle / test / brett "
                                   f"| 2026-11-01T00:00Z | none | handoffs/{lane}.md | T252b's rival row |"]
        w = self.launch("rival", [*edit, *argv], lane, extra=extra)
        w.wait()
        return w


def skill_step_4_block() -> str:
    """The handoff skill's step-4 block that opens with `act-begin` (T431;
    Y:5678), the first fenced `bash` block of its section 4 that holds it."""
    text = (REPO / "skills" / "handoff" / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("\n## 4.", 1)[-1].split("\n## 5.", 1)[0]
    blocks = re.findall(r"```(?:bash|sh)\n(.*?)```", section, re.S)
    found = [b for b in blocks if "act-begin" in b]
    assert found, "skills/handoff/SKILL.md's step 4 has no block that opens with act-begin (T431)"
    return found[0]


@pytest.fixture()
def act_worlds(pg_cluster, tmp_path):
    """T252b's worlds, each on a clone of `tmpl` of its own."""
    made: List[str] = []
    alive: List[ActWorld] = []

    def make() -> ActWorld:
        name = f"t252_{next(_NAMES)}"
        pg_cluster.psql(f"CREATE DATABASE {name} TEMPLATE {W_TEMPLATE};")
        made.append(name)
        found = pg_cluster.psql(f"SELECT to_regclass('{REGISTER}.register_head') IS NOT NULL;", dbname=name)
        assert found.stdout.strip() == "t", (
            f"{W_TEMPLATE} holds no {REGISTER} schema: lane 2's T227 builds it by the bootstrap")
        pg_cluster.psql(f"REVOKE ALL ON DATABASE {name} FROM PUBLIC;\n"
                        f"GRANT CONNECT ON DATABASE {name} TO {CONNECT_TO};\n")
        alive.append(ActWorld(tmp_path / f"world-{len(made)}", Clone(pg_cluster, name)))
        return alive[-1]

    yield make
    for world in alive:
        for w in world.writers:
            if w.ended is None and w.proc.poll() is None:
                os.killpg(w.proc.pid, 9)
        for live in world.sessions:
            live.close()
    for name in made:
        pg_cluster.drop_database(name)


def race(world: ActWorld, write: ActWrite, rival_lane: str,
         kind: Optional[str] = None) -> Tuple[Writer, Writer, List[str], int]:
    """The act run to `write`, its commit call held while the rival, of
    `kind` (by default `write.rival`), commits on `rival_lane`; then let go.
    Returns the act, which may still run (a `lane-start` whose W8 committed
    waits for the holder), the rival, the held write's id, read from the
    shim's log, which logs a call before its hold, and the head at the hold,
    before the rival commits (T252s)."""
    fifo = world.root / "hold.fifo"
    os.mkfifo(str(fifo))
    act = world.act(write, [{"mode": "hold", "match": write.match, "call": 1, "fifo": str(fifo)}])
    held = hold_point(fifo, act)
    base = world.c.head()
    calls = [c.get("stdin") or "" for c in act.commit_calls() if write.match in (c.get("stdin") or "")]
    ids = [m.group(1) for m in (re.search(r"commit_write\(\s*-?[0-9]+\s*,\s*'(" + UUID_RE + ")'", s)
                                for s in calls[:1]) if m]
    assert ids, f"the held commit call carries no write id: {calls[:1]}"
    rival = world.rival(kind or write.rival, rival_lane)
    assert rival.code == 0, f"the rival exited {rival.code}: {rival.err[-400:]}"
    held.close()
    return act, rival, ids, base


@CLIENT
@pytest.mark.parametrize("write", list(ACT_WRITES))
def test_an_act_whose_scope_changed_before_its_commit_writes_nothing(act_worlds, write):
    """TP:5854-5862: the act runs to `write`, held at its commit call; a rival
    from a second session commits on one of its scopes, leaving the verb's
    own answer as it was (`RIVALS`; see the section's head). On release the
    held commit has lost its turn, and the retried one refuses with 2 and
    `expectation: <scope> changed at seq <k> by <lane>/<verb>`, naming the
    rival's seq, lane and verb; the held write is not in the journal; and
    the act exits with the code lane 4's arm gives, never 0.

    `[guard-answer-2-child]` alone ends 0 (lane 3's point 4(b), #165
    6841918192; tasks:1438): the bind landed, so the guard's body exits 0;
    its record holds one `note=`, for the refused write, in the facts file
    beside `out=` that the outer folds into the record (`guard_bind_facts`);
    the `set-row-state` itself exited 2, with its `expectation:` line; and
    the journal grew only by the rival's entry after the hold (T252s).

    A `new-lane` rival (`[lane-start-w1-add-row]`) holds its premise too:
    it leaves the lane without a row, so the retried `add-row` is never
    refused for one, and its output holds no "already has a row"
    (`add_row_checks`, `bc9ed80b:lanes-edit.sh:15420`, `:15433`), the
    refusal T252y's rival was chosen to remove (lane 2's RV26, NIT 10;
    T252z)."""
    world = act_worlds()
    w = ACT_WRITES[write]
    act, rival, ids, base = race(world, w, w.lane)
    act.wait(240)
    k = max(int(r["seq"]) for r in world.c.json(
        f"SELECT coalesce(jsonb_agg(q), '[]'::jsonb) FROM (SELECT seq FROM {REGISTER}.journal "
        f"WHERE write_id = ANY(ARRAY{rival.write_ids()}::uuid[])) q;"))
    if w.rival == "new-lane":
        assert "already has a row" not in act.err + act.out, (
            f"[{write}] the retried add-row was refused for a row, against its rival's premise: {act.err[-900:]!r}")
    said = f"expectation: {w.rival_scope}:{w.lane.lower()} changed at seq {k} by {w.lane}/{w.rival_verb}"
    assert said in act.err + act.out, f"[{write}] {said!r} is not in {act.err[-900:]!r}"
    assert all(world.c.value(f"SELECT count(*) FROM {REGISTER}.journal WHERE write_id = '{x}';") == "0"
               for x in ids), f"[{write}] the held write is in the journal"
    if w.tool == "guard":
        assert act.code == 0, f"[{write}] the guard's body exited {act.code}, not 0: {act.err[-600:]}"
        facts = Path(f"{world.record}.bind.1.facts")
        assert facts.is_file(), f"[{write}] the body left no facts file at {facts}: {act.err[-600:]}"
        notes = [n for n in facts.read_text(encoding="utf-8").splitlines() if n.startswith("note=")]
        assert len(notes) == 1 and "set-row-state" in notes[0] and "exit 2" in notes[0], (
            f"[{write}] the record's notes are not one for the set-row-state's 2: {notes}")
        grew = [int(r["seq"]) for r in world.c.json(
            f"SELECT coalesce(jsonb_agg(q ORDER BY q.seq), '[]'::jsonb) FROM (SELECT seq FROM {REGISTER}.journal "
            f"WHERE seq > {base}) q;")]
        assert grew == [k], f"[{write}] after the hold at {base} the journal grew by {grew}, not the rival's {k} alone"
        return
    if w.code is not None:
        assert act.code == w.code, f"[{write}] the act exited {act.code}, not {w.code}: {act.err[-600:]}"
    assert act.code != 0, f"[{write}] the act exited 0 after its write was refused: {act.err[-600:]}"


@CLIENT
@pytest.mark.parametrize("write", list(ACT_WRITES))
def test_an_act_whose_scopes_held_commits(act_worlds, write):
    """TP:5863-5864: with a rival that touches no scope the write lists,
    another lane's `PAUSED` (or row line), the held write commits. The
    rival is `held_rival`, whatever the act's own rival is (`RIVALS`)."""
    world = act_worlds()
    w = ACT_WRITES[write]
    act, _, ids, _ = race(world, w, R_OTHER[w.lane], w.held_rival)
    deadline = time.monotonic() + 60
    while True:
        ended = act.ended is not None
        if all(world.c.value(f"SELECT count(*) FROM {REGISTER}.journal WHERE write_id = '{x}';") == "1"
               for x in ids):
            break
        assert not ended and time.monotonic() < deadline, (
            f"[{write}] the held write {ids} did not commit; the act "
            f"{'exited ' + str(act.code) if ended else 'still runs after 60 s'}: {act.err[-600:]}")
        time.sleep(0.2)


@CLIENT
def test_an_acts_own_earlier_write_never_refuses_its_later_one(estates):
    """Two writes of one act on one scope: the second commits, since the
    first carries the same `act_id`."""
    e = estates()
    act = act_begin(e)
    for tag in ("first", "second"):
        w = e.run(LA, act_write(e, "objects", tag=tag), extra=acted(act, f"objects:{LA.lower()}"))
        assert w.code == 0, f"the {tag} write exited {w.code}: {w.err[-600:]}"
    assert len(e.journal_after(1)) == 2


@CLIENT
def test_a_handoff_request_never_refuses_the_holders_own_handoff(estates):
    """A `HANDOFF-REQUESTED` line is not a lane-kind line: another lane's
    request after the holder's base does not refuse the holder's write on
    `row:<L>` and `bind:<L>`.

    The holder is bound (`bound_line`), since a request for a FREE lane is
    refused with 8 before any write. The request is made with `--no-wait`:
    it commits, and its empty wait then ends 2, "THE WAIT ENDED WITH
    NOTHING", since nothing releases the lane. So the oracle for the request
    is the journal, not its code (T252k)."""
    e = estates(bound=(LA, LC))
    act = act_begin(e)
    rival = e.run(LB, ["request-handoff", LA, "--session", session_of(LB), "--no-wait"])
    grew = e.journal_after()
    assert [r["verb"] for r in grew] == ["request-handoff"], (
        f"the request exited {rival.code} and the journal holds {grew}: {rival.err[-400:]}")
    w = e.run(LA, act_write(e, "row", tag="handoff"), extra=acted(act, f"row:{LA.lower()}", f"bind:{LA.lower()}"))
    assert w.code == 0, f"the holder's write exited {w.code}: {w.err[-600:]}"


@CLIENT
def test_act_variables_change_nothing_in_files_mode(estates):
    """At `mode=files`, a write with `LANES_ACT` and `LANES_EXPECT` set
    behaves as one without them: both commit to origin, and no `psql` call
    is made."""
    e = estates()
    conf = e.root / "files.conf"
    conf.write_text("mode=files\n", encoding="utf-8")
    conf.chmod(0o600)
    files = {"LANES_INDEX_CONFIG": str(conf)}
    plain = e.run(LA, ["append-line", f"NOTE {EM} lane {LA}: files mode, plain (T252)"], extra=files)
    act = dict(files, **acted(f"{'a' * 32}@files", f"row:{LA.lower()}"))
    with_act = e.run(LA, ["append-line", f"NOTE {EM} lane {LA}: files mode, act set (T252)"], extra=act)
    assert (plain.code, with_act.code) == (0, 0), [(w.code, w.err[-300:]) for w in (plain, with_act)]
    assert plain.calls() == [] and with_act.calls() == []
    shown = run_git(e.origin, "show", "main:lanes/LANES.md", env=e.env)
    assert "files mode, plain" in shown and "files mode, act set" in shown


# ---------------------------------------- the three conditions (T252, T252f)
#
# Brett's "Accept all three" (6721583757, row 22), as TP:5874-5879 states
# them and lane 3's batch 12 rules the gate's (#165 6808010497, "Lanes 2 and
# 4, question 2"; `RULINGS-batch12-analysis-20261111.md` (`b892fb39...`),
# A3, whose B15 text replaces TP:5877-5879's "so its `NOTED` writes do not
# refuse W13"). All three run their flows on T252b's world (lane 3's batch 7,
# item 5).
#
# [lane-start-reread] (T252i): `lane-start repoA 3 --request-handoff --wait
# 120`, a new place (a session of its own) taking the world's lane bound on
# Falcon, on primary, with `$LANES_EDIT` a logging stand-in and the request
# polling every second (`LANES_POLL_SECONDS`). Once its W8, `request-handoff`,
# has committed, a second session, the holder's, writes its handoff: the row's
# state cell (`set-row-state` to PAUSED), then its `PAUSED` line, which
# releases the binding and ends the wait. `lane-start` must then re-base with
# `act-begin --rebase`, which keeps the act's id and takes a base at or past
# the holder's entries, and read the row again (`register-row`) under it
# (Y:5656: "at `:2614` `lane-start` must also re-base, then re-read
# `register-row` and refuse on a change outside the state cell"; T428, "The
# re-base"). Two halves, each on a world of its own. In `[outside]` the holder
# first appends to the row's session cell (`append-session-id`), a change
# outside the state cell: `lane-start` exits non-zero, sends no write after
# its re-base and launches nothing, and W8's is the act's only entry. With the
# state cell alone changed, the act's writes after its re-base commit past
# the holder's entries, carrying its id, with no `expectation:` refusal, and
# `exec` starts `claude` (T252h's pid test). Readings: the change outside the
# state cell is N2-10's, an `append-session-id`, where any other cell would
# do; the holder writes its `PAUSED` line last, so that the re-base is taken
# past every write of its handoff (`lane-handoff` writes W9's line before
# W12's row, a race this case leaves out); and the refusal's code is not
# asserted, since T428's text names none (lane 4's draft dies 2).
#
# [lane-end-gate]: `lane-end`'s close-out of the world's live lane, on
# primary, under its `act-begin` base. `LANE_WORKTREES` is a stand-in that
# logs its argv and `LANES_ACT` and answers the dry run with nothing left,
# and the shim holds W13's commit call. The gate's `lane-worktrees` ran with
# the act's `LANES_ACT`, as `sweep <lane> ... --dry-run` (B15's Y:5715: "It
# is `lane-worktrees sweep <lane> --dry-run --porcelain` and writes
# nothing"), and at the hold the journal holds no entry after the base: the
# gate wrote nothing. A second session then writes a `NOTED lane:L` line
# with no act, as `lane-worktrees sweep --yes` writes one (its `note_line`:
# `LANES_LANE` and the sweeping session's `LANES_SESSION`). On release,
# W13 and W14 both commit after it, each carrying the act's `act_id`: a
# `NOTED lane:L` line yields only `sid:` keys (Y:1493-1496), and neither
# write lists one.
#
# [skill-step-4]: the handoff skill's step-4 block, run as the agent runs a
# block: the file's first block (`L` and `sread`), then the values steps 1
# and 2 bound (`window`, `lane`, `ws`, `uuid`, `why`, `kind`), then the
# block, in one `bash`, with `$L` a logging stand-in for `lanes-edit.sh` and
# a `tmux` whose window is named for the world's live lane. Step 4 opens
# with `act-begin` and re-runs the identity's register reads before its
# first write (TP:5876-5877; Y:5724): for a window with a row these are step
# 1's `register-row` and `canon-lane`. Where step 1's `lane` is not the lane
# the window now names, it refuses with 2 before its first write: none of
# its three writes (`SKILL.md:735`, `:743`, `:786`) is sent, and the journal
# is as it was. With the same lane, the three commit, each carrying the act's
# `act_id`. Readings: step 1's lane reaches step 4 as `lane`, the name both
# steps use, and the case makes it differ by giving the agent's `lane` as
# another lane with a row while the window still names its own.
#
# They FAIL UNTIL L1-A6, L4-A2 (T410, T411), L4-B3 and L4-B5 land, and
# `[lane-start-reread]` until T428 (with T427's `start-record`),
# `[lane-end-gate]` until T430, `[skill-step-4]` until T431. Without
# PostgreSQL 16 each flow skips, after `[skill-step-4]`'s first check, its
# block opening with `act-begin`, which needs no engine.

#: The three conditions, in the test plan's order; each runs its flow.
CONDITIONS = ("lane-start-reread", "skill-step-4", "lane-end-gate")
#: `[lane-start-reread]`'s starter, a session of its own, and the holder's new
#: session-cell entry, `[outside]`'s change outside the state cell.
STARTER_SID, HOLDER_NEW_SID = "aaaaaaaa-0257-4000-8000-00000000a257", "aaaaaaaa-0258-4000-8000-00000000a258"
#: The register writes `lane-start` may send after its re-read: T428's one
#: call, or its parts where no transcript uuid is known.
START_WRITES = ("start-record", "add-row", "append-session-id", "set-row-state", "log")
#: The second session that writes `[lane-end-gate]`'s `NOTED` line.
SWEEP_SID = "aaaaaaaa-0256-4000-8000-00000000a256"
#: The skill's three writes, as `$L`'s first argument names them.
SKILL_WRITES = ("log", "append-line", "set-row-state")

_ACT_LOGGER = r'''#!/usr/bin/env python3
# T252f's logging stand-in: its argv, and LANES_ACT and LANES_EXPECT as it
# saw them (null where unset), and its pid (T252h); then the real tool, where
# one is named.
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REAL = REAL_TOOL
with open(os.path.join(HERE, "acts.log"), "a", encoding="utf-8") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "act": os.environ.get("LANES_ACT"),
                          "expect": os.environ.get("LANES_EXPECT"), "pid": os.getpid()}) + "\n")
if REAL:
    os.execv(REAL, [REAL] + sys.argv[1:])
'''

_SKILL_TMUX = r'''#!/usr/bin/env bash
# T252f: this window is named WINDOW_NAME; every other call is the Sandbox's fake.
case "$*" in
  "display-message -p #W" | "display-message -p #{window_name}") printf '%s\n' WINDOW_NAME; exit 0 ;;
esac
exec FAKE_TMUX "$@"
'''


def act_logger(where: Path, name: str, real: Optional[Path] = None) -> Path:
    """A logging stand-in named `name` in `where`, logging to `acts.log`
    beside it: with `real`, it then runs that; without, it prints nothing and
    exits 0."""
    where.mkdir(parents=True, exist_ok=True)
    tool = where / name
    tool.write_text(_ACT_LOGGER.replace("REAL_TOOL", repr(str(real) if real else None)), encoding="utf-8")
    tool.chmod(0o755)
    return tool


def act_calls(tool: Path) -> List[dict]:
    log = tool.parent / "acts.log"
    return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l] if log.exists() else []


def act_entries(world: ActWorld, after: int) -> List[dict]:
    """The journal's entries after seq `after`: seq, verb, `act_id` and
    write id, in seq order."""
    return world.c.json(f"SELECT coalesce(jsonb_agg(q ORDER BY q.seq), '[]'::jsonb) FROM (SELECT seq, verb, "
                        f"act_id, write_id::text AS write_id FROM {REGISTER}.journal WHERE seq > {after}) q;")


def seq_base(act: Optional[str], who: str, task: str) -> Tuple[str, int]:
    """`LANES_ACT`'s id and seq, where it is a seq base."""
    assert act is not None and ACT_RE.match(act), (
        f"{who} ran with LANES_ACT={act!r}, not the act's <id>@<seq>:<generation> ({task})")
    ident, rest = act.split("@", 1)
    return ident, int(rest.split(":", 1)[0])


def skill_prelude_block() -> str:
    """The handoff skill's first block, which sets `L` and defines `sread`
    for the blocks after it."""
    text = (REPO / "skills" / "handoff" / "SKILL.md").read_text(encoding="utf-8")
    head = text.split("\n## 1.", 1)[0]
    found = [b for b in re.findall(r"```(?:bash|sh)\n(.*?)```", head, re.S) if "sread()" in b]
    assert found, "skills/handoff/SKILL.md has no block before step 1 that defines sread"
    return found[0]


def lane_end_gate_holds(world: ActWorld) -> None:
    """`[lane-end-gate]` (see the section's head)."""
    gate = act_logger(world.root / "gate", "lane-worktrees")
    fifo = world.root / "hold.fifo"
    os.mkfifo(str(fifo))
    act = world.launch("lane-end", [str(world.bin / "lane-end"), R_HERE], R_HERE,
                       [{"mode": "hold", "match": verb_is("set-row-state"), "call": 1, "fifo": str(fifo)}],
                       {"LANE_WORKTREES": str(gate)})
    deadline = time.monotonic() + 120
    while not act_calls(gate) and act.ended is None:
        assert time.monotonic() < deadline, "lane-end did not reach its close-out gate in 120 s"
        time.sleep(0.1)
    calls = act_calls(gate)
    assert calls, f"lane-end exited {act.code} before its close-out gate ran: {act.err[-600:]}"
    ident, base = seq_base(calls[0]["act"], "the close-out gate's lane-worktrees", "T430: the gate inherits it")
    argv = calls[0]["argv"]
    assert argv[:2] == ["sweep", R_HERE] and "--dry-run" in argv, (
        f"the close-out gate is not `lane-worktrees sweep {R_HERE} ... --dry-run`: {argv}")
    held = hold_point(fifo, act)
    gained = act_entries(world, base)
    assert gained == [], f"between the act's base {base} and W13 the journal gained {gained}: the gate wrote"
    noted = world.launch("sweep-noted", ["bash", str(world.bin / "lanes-edit.sh"), "log", "NOTED", f"lane:{R_HERE}",
                                         "swept 1 cache or sandbox director(ies): they hold no work and are "
                                         "rebuilt (T252f's second session)"],
                         R_HERE, extra={"LANES_SESSION": SWEEP_SID})
    noted.wait()
    assert noted.code == 0, f"the second session's NOTED exited {noted.code}: {noted.err[-400:]}"
    held.close()
    act.wait(240)
    assert act.code == 0 and "expectation:" not in act.err, (
        f"lane-end exited {act.code} after a NOTED lane:{R_HERE} written after its base: {act.err[-900:]}")
    entries, noted_ids = act_entries(world, base), noted.write_ids()
    swept = [e for e in entries if e["write_id"] in noted_ids]
    mine = [e for e in entries if e["act_id"] == ident]
    assert len(swept) == 1 and swept[0]["act_id"] is None, f"the NOTED line is not one entry of no act: {entries}"
    assert [e["verb"] for e in mine] == ["set-row-state", "log"], (
        f"W13 and W14 did not both commit carrying the act's id {ident}: {entries}")
    assert swept[0]["seq"] < mine[0]["seq"], f"the NOTED line did not commit before W13: {entries}"


def skill_step_4_command(world: ActWorld, prelude: str, block: str, lane: str, tag: str,
                         edit: Path) -> Tuple[List[str], dict]:
    """Step 4's block as the agent runs it, in the window named for the
    world's live lane: the skill's prelude, then steps 1 and 2's values, with
    `L` as `edit` and step 1's `lane` given, then the block, in one `bash`,
    and a `tmux` first on `PATH` naming that window. The command and the
    environment it adds. The flow case (`skill_step_4`, T252f) and the race's
    skill act (`ActWorld.act`, T252b) both run it (T252p)."""
    tmux_dir = world.root / f"skill-{tag}-tmux"
    tmux_dir.mkdir()
    (tmux_dir / "tmux").write_text(_SKILL_TMUX.replace("WINDOW_NAME", R_HERE)
                                   .replace("FAKE_TMUX", shlex.quote(str(world.fakebin / "tmux"))), encoding="utf-8")
    (tmux_dir / "tmux").chmod(0o755)
    bound = [f"L={shlex.quote(str(edit))}", f"window={R_HERE}", f"lane={lane}", f"ws={W_WS}", "ws_missing=''",
             f"uuid={R_SID[R_HERE]}", "uuid_missing=''", "why='T252f skill case'", "kind=unknown"]
    command = ["bash", "-c", "\n".join([prelude, *bound, block])]
    return command, {"PATH": str(tmux_dir) + os.pathsep + world.env["PATH"]}


def skill_step_4(world: ActWorld, prelude: str, block: str, lane: str, tag: str) -> Tuple[Writer, List[dict]]:
    """Step 4's block, run in the window named for the world's live lane,
    with step 1's `lane` given: the run, and its `$L` calls."""
    edit = act_logger(world.root / f"skill-{tag}", "lanes-edit.sh", world.bin / "lanes-edit.sh")
    command, extra = skill_step_4_command(world, prelude, block, lane, tag, edit)
    run = world.launch(f"skill-{tag}", command, R_HERE, extra=extra)
    run.wait(240)
    return run, act_calls(edit)


def verbs_of(calls: List[dict]) -> List[str]:
    return [(c["argv"] or [""])[0] for c in calls]


def skill_step_4_holds(world: ActWorld, prelude: str, block: str) -> None:
    """`[skill-step-4]` (see the section's head)."""
    head = world.c.head()
    run, calls = skill_step_4(world, prelude, block, R_PAUSED, "differs")
    verbs = verbs_of(calls)
    assert verbs[:1] == ["act-begin"], f"step 4's first call is {verbs[:1]}, not act-begin (T431): {verbs}"
    assert {"register-row", "canon-lane"} <= set(verbs[1:]), (
        f"step 4 did not run the identity's register reads again after act-begin (T431): {verbs}")
    sent = [v for v in verbs if v in SKILL_WRITES]
    # The identity refusal is a step-4 stop, and the stop ends 2 (T431; lane
    # 3's question 4, #165 6835210568: step 5 runs only where the block ended
    # 0, 3, 69 or 75; T252o).
    assert run.code == 2 and sent == [] and run.commit_calls() == [], (
        f"with step 1's lane {R_PAUSED} and the window's {R_HERE}, step 4 exited {run.code} and sent {sent} "
        f"(T431): {run.err[-600:]}")
    assert world.c.head() == head, f"the journal grew from {head} though step 1's lane differs"
    run, calls = skill_step_4(world, prelude, block, R_HERE, "same")
    verbs = verbs_of(calls)
    first = next((k for k, v in enumerate(verbs) if v in SKILL_WRITES), len(verbs))
    assert verbs[:1] == ["act-begin"] and {"register-row", "canon-lane"} <= set(verbs[1:first]), (
        f"step 4 did not open with act-begin and the identity's reads before its first write (T431): {verbs}")
    acts = {c["act"] for c, v in zip(calls, verbs) if v in SKILL_WRITES}
    assert len(acts) == 1, f"step 4's writes ran under LANES_ACT {sorted(map(str, acts))} (T431)"
    ident, base = seq_base(acts.pop(), "step 4's writes", "T431")
    entries = act_entries(world, base)
    assert [(e["verb"], e["act_id"]) for e in entries] == [(v, ident) for v in SKILL_WRITES], (
        f"step 4's three writes did not all commit carrying the act's id {ident}: {entries}: {run.err[-600:]}")


def lane_start_reread(world: ActWorld, outside: bool) -> Tuple[Writer, List[dict], List[dict], List[str]]:
    """`[lane-start-reread]`'s run (see the section's head): `lane-start`
    asks for the lane bound on Falcon and waits; once its W8 has committed,
    the holder's second session writes its handoff, `[outside]` first
    changing the row's session cell. Returns the run, its verb calls, the
    `claude` its `exec` started, and the holder's write ids."""
    tag = "outside" if outside else "state"
    edit = act_logger(world.root / f"reread-{tag}", "lanes-edit.sh", world.bin / "lanes-edit.sh")
    claude = act_logger(world.root / f"reread-{tag}-claude", "claude")
    run = world.launch(f"lane-start-{tag}", [str(world.bin / "lane-start"), "repoA", "3", "--request-handoff",
                                            "--wait", "120", "--dir", str(world.lane_dir)], R_FAR,
                       extra={"LANES_EDIT": str(edit), "LANES_SESSION": STARTER_SID, "LANES_POLL_SECONDS": "1",
                              "FAKE_CC_PATH": str(claude)})
    deadline = time.monotonic() + 120
    while run.ended is None and not any(e["verb"] == "request-handoff" for e in act_entries(world, 1)):
        assert time.monotonic() < deadline, f"[{tag}] lane-start's W8 did not commit in 120 s"
        time.sleep(0.5)
    holder: List[str] = []
    if run.ended is None:
        writes = [["append-session-id", R_FAR, R_SID[R_FAR], f"{ARROW} harness `{HOLDER_NEW_SID}`",
                   "T252i's holder: a session-cell change"]] if outside else []
        writes += [["set-row-state", R_FAR, f"PAUSED {DOT} handed off on request (T252i's holder)"],
                   ["log", "PAUSED", f"lane:{R_FAR}", ARROW, "T252i's holder", "handed off on request"]]
        for argv in writes:
            w = world.launch("holder", ["bash", str(world.bin / "lanes-edit.sh"), *argv], R_FAR)
            w.wait()
            assert w.code == 0, f"[{tag}] the holder's {argv[0]} exited {w.code}: {w.err[-400:]}"
            holder += w.write_ids()
    run.wait(240)
    return run, act_calls(edit), [c for c in act_calls(claude) if c.get("pid") == run.proc.pid], holder


def lane_start_reread_holds(make) -> None:
    """`[lane-start-reread]` (see the section's head): `[outside]`, then the
    state cell alone, each on a world of its own from `make`."""
    for outside in (True, False):
        world, tag = make(), "outside" if outside else "state"
        run, calls, launched, holder = lane_start_reread(world, outside)
        verbs = verbs_of(calls)
        asked = verbs.index("request-handoff") if "request-handoff" in verbs else len(verbs)
        assert "act-begin" in verbs[:asked], f"[{tag}] lane-start ran no act-begin before its W8 (T428): {verbs}"
        assert asked < len(verbs), f"[{tag}] lane-start exited {run.code} and sent no W8: {run.err[-600:]}"
        ident, _ = seq_base(calls[asked]["act"], f"[{tag}] W8's request-handoff", "T428")
        assert holder, f"[{tag}] lane-start exited {run.code} before its W8 committed: {run.err[-600:]}"
        rebase = next((k for k in range(asked + 1, len(calls))
                       if calls[k]["argv"][:2] == ["act-begin", "--rebase"]), None)
        assert rebase is not None, (
            f"[{tag}] lane-start did not re-base with act-begin --rebase after its W8 wait (T428): {verbs[asked:]}")
        reread = next((k for k in range(rebase + 1, len(calls)) if calls[k]["argv"][:2] == ["register-row", R_FAR]),
                      None)
        assert reread is not None, (
            f"[{tag}] lane-start did not read {R_FAR}'s row again after its re-base (T428): {verbs[rebase:]}")
        entries = act_entries(world, 1)
        seqs = {e["write_id"]: e["seq"] for e in entries}
        assert set(holder) <= set(seqs), f"[{tag}] the holder's writes {holder} are not all in the journal: {entries}"
        released = max(seqs[x] for x in holder)
        again, base = seq_base(calls[reread]["act"], f"[{tag}] the row's re-read", "T428")
        assert again == ident and base >= released, (
            f"[{tag}] the row's re-read ran under {calls[reread]['act']}: not act {ident} re-based at or past "
            f"the holder's seq {released} (T428)")
        mine = [e for e in entries if e["act_id"] == ident]
        if outside:
            sent = [v for v in verbs[rebase + 1:] if v in START_WRITES]
            assert run.code != 0 and sent == [] and launched == [], (
                f"[{tag}] with {R_FAR}'s session cell changed during the wait, lane-start exited {run.code}, sent "
                f"{sent} after its re-base and launched {len(launched)} claude (T428): {run.err[-600:]}")
            assert [e["verb"] for e in mine] == ["request-handoff"], f"[{tag}] the act's entries: {mine}"
        else:
            later = [e["verb"] for e in mine if e["seq"] > released]
            assert later and "expectation:" not in run.err and launched, (
                f"[{tag}] with only {R_FAR}'s state cell changed, lane-start's writes after its re-base committed "
                f"{later} and it launched {len(launched)} claude (T428): {run.err[-900:]}")


@pytest.mark.parametrize("condition", CONDITIONS)
def test_each_of_the_three_conditions_holds(condition, request):
    """[lane-start-reread]: after its W8 wait, `lane-start` re-bases with
    `act-begin --rebase` and reads the row again: a change outside the
    state cell refuses it with no write after the re-base, and the state
    cell alone does not. [skill-step-4]: the skill's step 4 opens with
    `act-begin` and re-derives the identity; where `lane` differs from step
    1's it sends none of its three writes, and with the same lane the three
    commit. Its block is found with no engine: red until T431 lands.
    [lane-end-gate]: `lane-end`'s gate runs with the act's `LANES_ACT` and
    writes nothing, and a `NOTED lane:L` line that a second session writes
    after the base refuses neither W13 nor W14 (lane 3's batch 12). All
    three run their flows on T252b's world (see the section's head)."""
    if condition == "skill-step-4":
        prelude, block = skill_prelude_block(), skill_step_4_block()
        skill_step_4_holds(request.getfixturevalue("act_worlds")(), prelude, block)
    elif condition == "lane-end-gate":
        lane_end_gate_holds(request.getfixturevalue("act_worlds")())
    else:
        lane_start_reread_holds(request.getfixturevalue("act_worlds"))


# ---------------------------------------- the launches (T252, T252h)
#
# TP:5889-5892 (Y:5596): before a launch `LANES_ACT` is unset (`exec`,
# `respawn-pane`), so the session and its guard do not inherit it: the fake
# `claude` started by `exec`, and the command the fake `tmux` logs for
# `respawn-pane`, see no `LANES_ACT`, in a run where `act-begin` had exported
# one. Both run their flows on T252b's world (lane 3's batch 7, item 5), with
# `$LANES_EDIT` a logging stand-in (T252f's `act_logger`). Its log is the
# proof that the act exported one: a verb call after `act-begin` ran with a
# seq base.
#
# [exec]: `lane-start repoA 1`, the resume of the world's paused lane, run to
# its launch. `claude-current` names a logging stand-in as the `claude` to
# launch, and the one that ran in `lane-start`'s own process, by its pid, is
# the one `exec` started. It saw neither `LANES_ACT` nor `LANES_EXPECT`
# (T428: both are unset before the launch; Y:5581: `LANES_EXPECT` "is never
# exported").
#
# [respawn-pane]: `lane-handoff --restart --lane repoA-2`, the live lane's
# `/ctx`, run to its respawn, with `$TMUX_PANE` naming its pane and the
# lane's handoff file in the world (`ActWorld.handoff`), since a restart
# respawns nothing over a handoff it could not refresh. A `tmux`
# wrapper logs `respawn-pane`'s argv, with the two variables as tmux saw them,
# and answers 0; every other call is the Sandbox's fake. Neither variable was
# in its environment (T429), and its command names neither, since a `-e` or a
# prefix in the respawn line would hand them on too.
#
# Readings: the export is read from the act's verb calls, so an act that
# passed its base only as a prefix on each call would pass too; the oracle,
# what the launch saw, is the same. 5e's daily report, which T428 also has
# unset both for, stays off in the world (conftest's
# `LANE_WORKTREES_REPORT=off`), so it is not asserted.
#
# They FAIL UNTIL L1-A6, L4-A2 (T410, T411), L4-B3 and L4-B5 land, `[exec]`
# until T428 and `[respawn-pane]` until T429. Without PostgreSQL 16 each
# skips.

#: Each launch: the act's tool, its argv and its lane in T252b's world.
LAUNCHES = {"exec": ("lane-start", ("repoA", "1"), R_PAUSED),
            "respawn-pane": ("lane-handoff", ("--restart", "--lane", R_HERE, "T252h's restart"), R_HERE)}

_RESPAWN_TMUX = r'''#!/usr/bin/env bash
# T252h: respawn-pane is logged, with LANES_ACT and LANES_EXPECT as tmux saw
# them, and answers 0; every other call is the Sandbox's fake.
if [ "${1-}" = respawn-pane ]; then exec RESPAWN_LOGGER "$@"; fi
exec FAKE_TMUX "$@"
'''


def act_exported(calls: List[dict], who: str, task: str) -> Tuple[str, int]:
    """The act's id and base, from the first verb call after `act-begin`
    that ran with a seq base: the proof that the act exported one."""
    verbs = verbs_of(calls)
    assert "act-begin" in verbs, f"{who} never ran act-begin ({task}): {verbs}"
    acts = [c["act"] for c in calls[verbs.index("act-begin") + 1:] if c["act"]]
    based = [a for a in acts if ACT_RE.match(a)] or acts
    return seq_base(based[0] if based else None, f"{who}'s verb calls after act-begin", task)


def launch_flow(world: ActWorld, launch: str) -> Tuple[Writer, List[dict], List[dict]]:
    """The act that launches, run to its launch (see the section's head):
    the run, its verb calls, and what its launch saw."""
    tool, argv, lane = LAUNCHES[launch]
    edit = act_logger(world.root / f"{launch}-edit", "lanes-edit.sh", world.bin / "lanes-edit.sh")
    seen = act_logger(world.root / f"{launch}-seen", "claude" if launch == "exec" else "tmux-respawn")
    extra = {"LANES_EDIT": str(edit)}
    if launch == "exec":
        extra["FAKE_CC_PATH"] = str(seen)
    else:
        wrapper = world.root / f"{launch}-tmux"
        wrapper.mkdir()
        (wrapper / "tmux").write_text(_RESPAWN_TMUX.replace("RESPAWN_LOGGER", shlex.quote(str(seen)))
                                      .replace("FAKE_TMUX", shlex.quote(str(world.fakebin / "tmux"))),
                                      encoding="utf-8")
        (wrapper / "tmux").chmod(0o755)
        extra.update(PATH=str(wrapper) + os.pathsep + world.env["PATH"], TMUX_PANE="%1")
        world.handoff(lane)
    run = world.launch(launch, [str(world.bin / tool), *argv], lane, extra=extra)
    run.wait(240)
    saw = act_calls(seen)
    if launch == "exec":
        saw = [c for c in saw if c.get("pid") == run.proc.pid]
    return run, act_calls(edit), saw


@pytest.mark.parametrize("launch", list(LAUNCHES))
def test_lanes_act_is_unset_before_a_launch(launch, request):
    """`LANES_ACT` is unset before `exec` (`lane-start`) and before
    `respawn-pane` (`lane-handoff`), so the session and its guard never
    inherit it: in a run whose verb calls carried the act's seq base, the
    `claude` that `exec` started, and tmux's `respawn-pane`, saw neither
    `LANES_ACT` nor `LANES_EXPECT`, and the respawn's command names
    neither. Both run their flows on T252b's world (see the section's
    head): red until T428 and T429 land."""
    tool, task = LAUNCHES[launch][0], {"exec": "T428", "respawn-pane": "T429"}[launch]
    run, calls, saw = launch_flow(request.getfixturevalue("act_worlds")(), launch)
    act_exported(calls, tool, task)
    what = "no claude ran in its own process" if launch == "exec" else "tmux was asked for no respawn-pane"
    assert saw, f"[{launch}] {tool} exited {run.code} before its launch: {what}: {run.err[-900:]}"
    assert (saw[0]["act"], saw[0]["expect"]) == (None, None), (
        f"[{launch}] the launch saw LANES_ACT={saw[0]['act']!r} and LANES_EXPECT={saw[0]['expect']!r} ({task})")
    named = [a for a in saw[0]["argv"] if "LANES_ACT" in a or "LANES_EXPECT" in a]
    assert named == [], f"[{launch}] the launch's command hands on {named} ({task})"


@CLIENT
def test_an_act_that_decided_on_canon_lane_is_refused_by_a_row_added_on_its_walk(estates):
    """Alias lines lead `a` to `b` and `b` to `c`, which has a row: an act that
    decided on `canon-lane a` takes the names from `canon-lane --walk a` and
    lists `row:` and `alias:` for each (Y:5624), so a rival `add-row` for `b`
    after the base refuses its write with 2, LR009 naming `row:b`
    (TP:5871-5873; lane 3's batch 7, ask 3)."""
    e = estates(aliases=WALK_ALIASES)
    act = act_begin(e, LC)
    walked = e.run(LC, ["canon-lane", "--walk", WALK_A])
    names = walked.out.split()
    assert walked.code == 0 and names == [WALK_A, WALK_B, LC], (
        f"canon-lane --walk {WALK_A} exited {walked.code} and printed {walked.out!r}: {walked.err[-400:]}")
    expect = [f"{kind}:{name.lower()}" for name in names for kind in ("row", "alias")]
    rival = e.run(WALK_B, ["add-row", w_row(WALK_B)])
    assert rival.code == 0, f"the rival add-row exited {rival.code}: {rival.err[-400:]}"
    w = e.run(LC, act_write(e, "objects", lane=LC, tag="walk"), extra=acted(act, *expect))
    assert w.code == 2 and f"expectation: row:{WALK_B.lower()} changed" in w.err, (w.code, w.err[-600:])


@CLIENT
@pytest.mark.parametrize("case", ["after-loss-cutover", "base-past-n"])
def test_the_client_refuses_an_acts_stale_base_with_2_at_the_snapshot(estates, case):
    """An act whose generation is not the switch's, or whose base is past
    `n`: exit 2 at the snapshot, no commit call, nothing written."""
    e = estates()
    gen = e.c.switch()["generation"]
    n = e.c.head()
    act = (f"{'b' * 32}@{n}:{uuid.uuid4()}" if case == "after-loss-cutover"
           else f"{'b' * 32}@{n + 5}:{gen}")
    state = e.c.state()
    w = e.run(LA, act_write(e, "objects", tag=case), extra=acted(act, f"objects:{LA.lower()}"))
    assert w.code == 2, f"[{case}] exit {w.code}: {w.err[-600:]}"
    assert w.commit_calls() == [] and e.c.state() == state


@pytest.mark.parametrize("case", ["generation", "base-past-head"])
def test_the_commits_act_backstops_are_lr007_act_generation_and_lr004(clones, case):
    """The client's checks bypassed by a direct commit call (T223's
    `Clone`): an act of another generation gets LR007 `act-generation`, a
    base past the head LR004; nothing is written. `commit_write` checks an
    act's generation and base only where it lists an expectation (step 3b,
    `IF cardinality(v_expect) > 0`), before it compares any scope, so each
    act lists one: the writer's own row. (The hold line derives no scope.)

    The register is a clone of `tmpl`, not of `tmpl_imported`, brought to
    `primary` by AT-LR006's route, as T221's step-6 cases and T253b's case
    bring theirs and as this module's phase W estates do: `import_files`'
    `import` entry at seq 0, then `Clone.to_primary`'s `cutover` at seq 1
    and `record_marker`. So the ids need no T115, whose `import --at` builds
    `tmpl_imported` after T112: they fail only until T107's step 3b, T227's
    `tmpl` and T228's `lanes_w_fx` land, and T112's `-k` runs them (lane 3's
    way 1, #165 6841609469; T252r)."""
    c = clones(W_TEMPLATE)
    import_files(c, {LANES_MD: "# LANES.md: the act backstops' register (T252r)\n"})
    assert c.to_primary() == 1, "the backstops' cutover is not at seq 1 (AT-LR006's route)"
    c.no_taker()
    entry = c.append(L1, *hold(c, L1))
    head, gen = c.head(), c.switch()["generation"]
    expect = [f"row:{L1.lower()}"]
    entry["act"] = ({"id": "c" * 32, "base": head, "generation": str(uuid.uuid4()), "expect": expect}
                    if case == "generation"
                    else {"id": "c" * 32, "base": head + 5, "generation": gen, "expect": expect})
    if case == "generation":
        c.refused(entry, "LR007", "act-generation")
    else:
        c.refused(entry, "LR004", None)


@CLIENT
@pytest.mark.parametrize("case", ["space", "no-break-space"])
def test_a_line_deriving_a_key_that_is_not_a_scope_exits_2_on_lr010_once(estates, case):
    """`append-line` with a row-shaped line whose first backticked token holds
    a space or a no-break space: the commit refuses LR010, the writer exits
    2 naming the path, the line and the key, with one commit call, never
    retried, and nothing written. The key is named with each white-space
    character as `[U+hhhh]` (Y:1504), `row:x[U+0020]y` and `row:x[U+00A0]y`
    (T252m)."""
    e = estates()
    gap = " " if case == "space" else chr(0x00A0)
    line = f"| `x{gap}y` | T252 | a key that is not a scope |"
    state = e.c.state()
    w = e.run(LA, ["append-line", line])
    assert w.code == 2, f"[{case}] exit {w.code}: {w.err[-600:]}"
    key = f"row:x[U+{ord(gap):04X}]y"
    assert "LR010" in w.err and LANES_MD in w.err and key in w.err, w.err
    assert len(w.commit_calls()) == 1 and e.c.state() == state


# ============================================================ PHASE N: AT-LR5's other cases and AT-LR009 (T232)
#
# LR005'S RULES AND THE ACT'S KEY, ON `commit_write`'S SIDE (AT-LR5,
# TP:4310-4476; AT-LR009, TP:4834-4941). The test plan puts them in phase W;
# F13's block writes them in phase N, as T223's above, since they check the
# same function (R1's M3; FR-059): each case is a direct `commit_write` call as
# `lanes_w_fx`, in the commit call's own form, on a clone of `tmpl_imported`
# that `Clone.to_primary` brings to `primary`, with the entry built here as the
# client builds it. AT-F5 holds the client's half (T233, T252). The forms are
# lane 1's, read at `refs/l1/T112-fu2` and `refs/l1/R-merge6`, `lanes-index`:
#   * the entry's keys and its `act`, `{id, base, generation, expect}`, the
#     scopes in lower case in the order given: `commit_write`'s head comment
#     and its act checks, and `register_act_of_env`;
#   * a log line's `log_lines` row, and a lane's `object_holds` row on its
#     object, with D19's spellings on a claim's alone: `_register_log_row`,
#     `_register_last_hold` and `register_object_spellings`;
#   * a slot line's `repo_key`, canonical and lower case, and its
#     `repo_spellings`, the spelling as typed first: `_register_slot_row`;
#   * a row's `lanes` row: `_register_lane_row`; the cutover's abort:
#     `switch_to_files` in one SERIALIZABLE transaction (R-merge6);
#   * the stray entries' kinds, verbs and `git_commit`: lane 2's T221
#     (`test_sql_register_schema.py` at line W3b's `8f645fce`).
# THE ROLLBACK'S ENTRY is T304's form (`rollback_entry`), as line R's
# `lanes-index rollback` builds it from merge14 on, and as T231's schema module
# sends it: kind and verb `rollback`, one edit removing `lanes/STORE`, its one
# `files` row not present, and `not_after`.
# Readings: the lines' texts (a row's cells, `RENAMED`'s words) are this
# module's, in the grammar `lanes-edit.sh` and `parse_log_line` read; only the
# keys they derive are asserted. `rename-lane` and `archive-rows` need step 6's
# derived deletes (ERR-48), which R-merge6 has and T112-fu2 alone has not.
# Every case FAILS UNTIL L1-A6 (T107's `commit_write`, its steps 3b, 5a, 7 and
# 8a) and lane 2's T227 and T228 land, as T223's do; without PostgreSQL 16
# each skips.

LA5, LB5, LC5, LD5 = "L1-t232", "L2-t232", "L3-t232", "L4-t232"
LB5_NEW = "L2b-t232"
FOO = "foo-03"
#: Each lane's session uuid, fixed so a case can name its `sid:` key.
SID5 = {lane: str(uuid.uuid5(uuid.NAMESPACE_URL, f"t232/{lane}")) for lane in (LA5, LB5, LC5, LD5)}
OBJ5, OBJ5_ALIAS, OBJ5_FREE = f"{KEY}#41", f"{ALIAS}#41", f"{OTHER_KEY}#9"
RETIRED_MD, ALIASES_TSV = "lanes/archive/LANES-retired.md", "lanes/aliases.tsv"
STRAY_COMMIT = "3" * 40
ACT_ID = "act-t232"
#: D18's and D19's spellings of a repository as a line types it, the spelling
#: as typed first (`register_repo_spellings`), with `repos.tsv` mapping `r9`.
REPO_SPELLINGS = {KEY: [KEY, ALIAS], ALIAS: [ALIAS, KEY], OTHER_KEY: [OTHER_KEY]}
CLAIM_VERBS = ("CLAIMED", "TAKEOVER")
#: Every table a refused call must leave as it was (AT-LR5's and AT-LR009's oracles).
TABLES5 = ("register_head", "journal", "journal_edits", "journal_files", "journal_scopes", "files",
           "doc_lines", "lanes", "log_lines", "object_holds", "register_lines", "register_switch")
#: A call made while a session holds the head row: past its lock_timeout it would end 55P03.
LOCKED_SQL = "SET lock_timeout = '1500ms';\n" + COMMIT_SQL
#: The cutover's abort, as R-merge6's `cutover --abort` sends it, less its read of the switch.
ABORT_SQL = ("BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
             f"SELECT {REGISTER}.switch_to_files(:client, :seq, :'lane', :'ws');\n"
             "COMMIT;\n")
_ARGS5 = itertools.count(1)


def log_path(lane: str) -> str:
    return f"lanes/log/{lane}.md"


def object_spellings(obj: str) -> Optional[List[str]]:
    """`register_object_spellings`: the object as written, then the same
    object under each of its repository's spellings; a lane's has none."""
    if obj.startswith("lane:"):
        return None
    repo, _, rest = obj.partition("#")
    return [spelling + "#" + rest for spelling in REPO_SPELLINGS.get(repo, [repo])]


def stamp5(c: Clone, minutes_ago: float = 0.0) -> Tuple[str, str]:
    """A log line's UTC, to the second as `log_lines`' primary CHECK takes it,
    and its `utc_ts`, by the database's clock less `minutes_ago`."""
    said = c.value("SELECT to_char(t AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') || '|' || t::text "
                   f"FROM (SELECT date_trunc('second', clock_timestamp() - make_interval(secs => {minutes_ago * 60})) "
                   "AS t) s;")
    utc, utc_ts = said.split("|")
    return utc, utc_ts


def row_text(lane: str, sid: Optional[str], state: str = "ACTIVE", note: str = "") -> str:
    """A `lanes/LANES.md` row: the lane's backticked name first (ROW_AWK), then
    the cells `_register_lane_row` reads: the sessions, the workstation, the
    start, the objects, the handoff and the state."""
    return (f"| `{lane}`{note} | {sid or '—'} | {WS} | 2026-11-10T09:00Z | — | "
            f"lanes/handoff-{lane}.md | {state} |")


class Draft:
    """One entry, built against the clone's files as `register_commit_entry`
    builds it: the edits in order, each touched path's `files` row as it
    stands after them, and the structured rows of the lines written."""

    def __init__(self, c: Clone, lane: str, verb: str, kind: str = "write", **journal) -> None:
        self.c, self.lane, self.verb, self.kind, self.extra = c, lane, verb, kind, journal
        self.images: Dict[str, list] = {}
        self.touched: List[str] = []
        self.gone: List[str] = []
        self.edits: List[dict] = []
        self.rows: Dict[str, list] = {"lanes": [], "log_lines": [], "register_lines": [], "object_holds": []}

    def _image(self, path: str) -> list:
        if path not in self.images:
            final_newline, lines = self.c.file(path)
            self.images[path] = [final_newline, list(lines)]
        return self.images[path]

    def _edit(self, **edit) -> None:
        edit["ord"] = len(self.edits) + 1
        self.edits.append(edit)
        for path in (edit["path"], edit.get("to_path")):
            if path and path not in self.touched:
                self.touched.append(path)

    def lines(self, path: str) -> List[str]:
        return list(self._image(path)[1])

    def append(self, path: str, text: str) -> int:
        image = self._image(path)
        if image[0] is None:
            self._edit(op="create", path=path)
            image[0] = True
        image[1].append(text)
        self._edit(op="append", path=path, new_text=text)
        return len(image[1])

    def replace(self, path: str, line_no: int, text: str) -> None:
        image = self._image(path)
        old = image[1][line_no - 1]
        self._edit(op="replace", path=path, line_no=line_no, old_sha256=sha256(old.encode("utf-8")),
                   new_text=text)
        image[1][line_no - 1] = text

    def delete(self, path: str, line_no: int) -> None:
        image = self._image(path)
        old = image[1].pop(line_no - 1)
        self._edit(op="delete", path=path, line_no=line_no, old_sha256=sha256(old.encode("utf-8")))

    def rename(self, path: str, to_path: str) -> None:
        self.images[to_path] = self._image(path)
        del self.images[path]
        self.gone.append(path)
        self._edit(op="rename", path=path, to_path=to_path)

    def row(self, path: str, lane: str, text: str, line_no: int, *, archived: bool = False,
            aliases: Sequence[str] = ()) -> None:
        """The `lanes` row of a row line, as `_register_lane_row` derives it."""
        cells = [cell.strip(" \t") for cell in text.split("|")]
        ids = re.findall(UUID_RE, cells[2].lower())
        self.rows["lanes"].append({
            "path": path, "line_no": line_no, "raw": text, "lane_key": lane.lower(), "lane": lane,
            "aliases": list(aliases), "home": None, "workstation": cells[3], "started_utc": cells[4],
            "handoff_path": cells[6], "state_phrase": cells[7], "objects_cell": cells[5],
            "session_ids": ids, "last_session": ids[-1] if ids else None, "archived": archived,
            "owner": None})

    def hold(self, obj: str, lane: str, verb: str, utc_ts: Optional[str], path: str, ordinal: int) -> None:
        """A lane's `object_holds` row: its last line on the object."""
        holds = [h for h in self.rows["object_holds"] if (h["object"], h["lane_key"]) != (obj, lane.lower())]
        holds.append({"object": obj, "lane_key": lane.lower(), "lane": lane, "verb": verb, "utc_ts": utc_ts,
                      "file": path, "ordinal": ordinal,
                      "spellings": object_spellings(obj) if verb in CLAIM_VERBS else None, "exempt": False})
        self.rows["object_holds"] = holds

    def log(self, verb: str, lane: str, obj: str, minutes_ago: float = 0.0, *, sid: Optional[str] = None,
            words: str = "") -> int:
        """A line appended to `lane`'s log, its `log_lines` row, and its
        lane's `object_holds` row where the object is not a lane's."""
        path, sid = log_path(lane), sid or SID5[lane]
        utc, utc_ts = stamp5(self.c, minutes_ago)
        text = f"{verb} — lane {lane}, session {sid}@{WS}, {utc}, {obj}" + (f" — {words}" if words else "")
        line_no = self.append(path, text)
        self.rows["log_lines"].append({
            "path": path, "line_no": line_no, "raw": text, "lane": lane, "verb": verb, "session": sid,
            "workstation": WS, "utc": utc, "utc_ts": utc_ts, "object": obj, "ref": "", "payload": "",
            "payload_fields": {}, "free_text": words, "written_lane": lane, "unreadable": False,
            "unreadable_why": None})
        if not obj.startswith("lane:"):
            self.hold(obj, lane, verb, utc_ts, path, line_no)
        return line_no

    def entry(self, act: Optional[dict] = None) -> dict:
        files = []
        for path in self.touched:
            if path in self.gone:
                files.append({"path": path, "present": False, "sha256": None, "final_newline": None})
            else:
                final_newline, lines = self.images[path]
                files.append({"path": path, "present": True, "sha256": sha256(rendered(lines, final_newline)),
                              "final_newline": final_newline})
        extra = dict(self.extra)
        if self.kind == "write":
            extra["args_sha256"] = sha256(f"{self.lane}\0{self.verb}\0{next(_ARGS5)}".encode("utf-8"))
        entry = {"journal": self.c.journal(self.kind, self.verb, self.lane,
                                           message=f"{self.verb} by {self.lane} (T232)", **extra),
                 "not_after": self.c.not_after(), "edits": self.edits, "files": files, **self.rows}
        if act is not None:
            entry["act"] = act
        return entry


# ------------------------------------------------------------ the entries
def claim5(c: Clone, lane: str, obj: str, verb: str = "CLAIMED", act: Optional[dict] = None,
           minutes_ago: float = 0.0) -> dict:
    """`claim` (or `release`): one log line on the object, and the lane's hold."""
    d = Draft(c, lane, "release" if verb == "RELEASED" else "claim")
    d.log(verb, lane, obj, minutes_ago)
    return d.entry(act)


def row_line(c: Clone, lane: str) -> Tuple[int, str]:
    _, lines = c.file(LANES_MD)
    for line_no, text in enumerate(lines, 1):
        if text.startswith(f"| `{lane}`"):
            return line_no, text
    raise AssertionError(f"no row for {lane} in {LANES_MD}")


def set_row_state(c: Clone, lane: str, state: str = "PAUSED", act: Optional[dict] = None) -> dict:
    """`set-row-state`: the lane's row replaced, its state cell changed."""
    d = Draft(c, lane, "set-row-state")
    line_no, _ = row_line(c, lane)
    text = row_text(lane, SID5[lane], state)
    d.replace(LANES_MD, line_no, text)
    d.row(LANES_MD, lane, text, line_no)
    return d.entry(act)


def rename_lane(c: Clone, old: str = LB5, new: str = LB5_NEW) -> dict:
    """`rename-lane <old> <new>` (Amendment 16): the row's key cell
    `` `<new>` *(ex `<old>`, renamed <UTC>)* ``, the log renamed and a
    `RENAMED` line appended to it, and `<old>\\t<new>\\t<UTC>` appended to
    `lanes/aliases.tsv`; with the new lane's `lanes` row and its hold on each
    object its log names, at its last line on it."""
    d = Draft(c, old, "rename-lane")
    line_no, _ = row_line(c, old)
    text = row_text(new, SID5[old], note=f" *(ex `{old}`, renamed 2026-11-10T10:00Z)*")
    d.replace(LANES_MD, line_no, text)
    d.row(LANES_MD, new, text, line_no, aliases=[old])
    d.append(ALIASES_TSV, f"{old}\t{new}\t2026-11-10T10:00:00Z")
    held = c.json(f"SELECT coalesce(json_agg(json_build_array(object, verb, utc_ts::text, ordinal) ORDER BY ordinal), "
                  f"'[]') FROM {REGISTER}.log_lines WHERE file = '{log_path(old)}' AND NOT unreadable "
                  "AND object NOT LIKE 'lane:%';")
    d.rename(log_path(old), log_path(new))
    d.log("RENAMED", new, f"lane:{new}", sid=SID5[old], words=f"renamed from {old}")
    for obj, verb, utc_ts, ordinal in held:
        d.hold(obj, new, verb, utc_ts, log_path(new), ordinal)
    return d.entry()


def archive_rows(c: Clone, lane: str = FOO) -> dict:
    """`archive-rows`: the row moved from `lanes/LANES.md` to
    `lanes/archive/LANES-retired.md`, and its `lanes` row archived there."""
    d = Draft(c, LA5, "archive-rows")
    line_no, text = row_line(c, lane)
    d.delete(LANES_MD, line_no)
    d.row(RETIRED_MD, lane, text, d.append(RETIRED_MD, text), archived=True)
    return d.entry()


def stray_import(c: Clone, lane: str = LA5, obj: str = OBJ5_FREE) -> dict:
    """A `stray-import` (`import --single`), as T221's: a stray commit's line,
    here a claim, taken into the register."""
    d = Draft(c, lane, "import --single", kind="stray-import", git_commit=STRAY_COMMIT)
    d.log("CLAIMED", lane, obj)
    return d.entry()


def stray_revert(c: Clone) -> dict:
    """A `stray-revert` (`render --revert`), as T221's: no edit."""
    return {"journal": c.journal("stray-revert", "render --revert", OPERATOR, git_commit=STRAY_COMMIT,
                                 message="render --revert (T232)"), "not_after": c.not_after()}


def rollback_entry(c: Clone) -> dict:
    """The rollback's entry (S5's step 1; TP's AT-SET fixture: "`commit_write`
    with a `rollback` entry, as REGISTER-WRITER"), in T304's form, line R's
    `rollback_entry` in `lanes-index` (merge14 on): `journal` with kind and
    verb `rollback`; one edit, the `remove` of `lanes/STORE`; its one `files`
    row, not present; `not_after`. T231's schema module sends the same entry.
    The operator sends it, as the cutover's."""
    return {"journal": c.journal("rollback", "rollback", OPERATOR, message="rollback (T232)"),
            "not_after": c.not_after(),
            "edits": [{"ord": 1, "op": "remove", "path": STORE}],
            "files": [{"path": STORE, "present": False}]}


def act5(c: Clone, base: int, expect, act_id: str = ACT_ID) -> dict:
    """The entry's `act`, as `register_act_of_env` returns it."""
    return {"id": act_id, "base": base, "generation": c.switch()["generation"], "expect": expect}


# ------------------------------------------------------------ the reads
def tables(c: Clone) -> Dict[str, str]:
    """Each table's digest, row by row."""
    parts = ", ".join(f"'{t}', (SELECT md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) "
                      f"FROM {REGISTER}.{t} x)" for t in TABLES5)
    return c.json(f"SELECT json_build_object({parts});")


def scopes_at(c: Clone, seq: int) -> List[str]:
    return c.json(f"SELECT coalesce(json_agg(scope ORDER BY scope), '[]') FROM {REGISTER}.journal_scopes "
                  f"WHERE seq = {seq};")


def act_ids(c: Clone) -> Dict[int, Optional[str]]:
    said = c.json(f"SELECT coalesce(json_object_agg(seq, act_id), '{{}}') FROM {REGISTER}.journal;")
    return {int(seq): act_id for seq, act_id in said.items()}


def orphans(c: Clone) -> int:
    """`journal_scopes` rows at a seq the journal no longer holds."""
    return int(c.value(f"SELECT count(*) FROM {REGISTER}.journal_scopes s WHERE NOT EXISTS "
                       f"(SELECT 1 FROM {REGISTER}.journal j WHERE j.seq = s.seq);"))


def refused5(c: Clone, entry: dict, code: str, detail: Optional[str], first: Optional[str] = None) -> List[str]:
    """`Clone.refused`, and every table as it was; `first`, where given, is
    the first stderr line's message exactly."""
    before = tables(c)
    lines = c.refused(entry, code, detail)
    if first is not None:
        assert lines[0] == f"ERROR:  {code}: {first}", lines
    after = tables(c)
    assert after == before, f"the refused call changed {[t for t in TABLES5 if after[t] != before[t]]}"
    return lines


def lr5(clones) -> Clone:
    """A clone on `primary`, with no hold on the cases' objects."""
    c = primary(clones)
    held = c.value(f"SELECT count(*) FROM {REGISTER}.object_holds WHERE object IN ('{OBJ5}', '{OBJ5_ALIAS}', "
                   f"'{OBJ5_FREE}') OR spellings && ARRAY['{OBJ5}', '{OBJ5_ALIAS}', '{OBJ5_FREE}'];")
    assert held == "0", f"{IMPORTED} holds {held} row(s) on {OBJ5} or {OBJ5_FREE}, which the cases claim"
    return c


def estate5(clones) -> Clone:
    """AT-LR009's register (TP:4855-4858), on primary: L1, L2 and L3, each with
    a row holding its session uuid and a log opened by `STARTED`; an alias
    line; a row named `foo-03`, holding none; and an object, `opensoft/r9#41`,
    that L2 claimed five hours before. One write, before every case's base."""
    c = lr5(clones)
    d = Draft(c, LA5, "append-line")
    for lane in (LA5, LB5, LC5):
        text = row_text(lane, SID5[lane])
        d.row(LANES_MD, lane, text, d.append(LANES_MD, text))
    text = row_text(FOO, None, "RETIRED")
    d.row(LANES_MD, FOO, text, d.append(LANES_MD, text))
    d.append(ALIASES_TSV, f"L0-t232\t{LA5}\t2026-11-10T08:00:00Z")
    for lane in (LA5, LB5, LC5):
        d.log("STARTED", lane, f"lane:{lane}")
    d.log("CLAIMED", LB5, OBJ5, minutes_ago=300)
    c.committed(d.entry())
    return c


@pytest.fixture()
def head_holder(pg_cluster):
    """A superuser session holding the head row (`SELECT … FOR UPDATE`),
    confirmed in `pg_stat_activity`, rolled back at the test's end."""
    started: List[subprocess.Popen] = []

    def hold(c: Clone, appname: str = "t232-holder") -> subprocess.Popen:
        proc = c.db.session(SUPERUSER, appname)
        proc.stdin.write(f"BEGIN;\nSELECT 1 FROM {REGISTER}.register_head WHERE id = 1 FOR UPDATE;\n")
        proc.stdin.flush()
        started.append(proc)
        deadline = time.monotonic() + 20
        while c.value(f"SELECT count(*) FROM pg_stat_activity WHERE application_name = '{appname}' "
                      "AND state = 'idle in transaction';") != "1":
            assert time.monotonic() < deadline, "the holder never took the head row"
            time.sleep(0.05)
        return proc

    yield hold
    for proc in started:
        if proc.poll() is None:
            try:
                proc.stdin.write("ROLLBACK;\n")
                proc.stdin.close()
            except (BrokenPipeError, ValueError):
                pass
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


# ------------------------------------------------------------ AT-LR5: LR005's rules
def test_lr005_refuses_a_claim_whose_spellings_meet_another_lanes_live_claim(clones):
    """D19: L1 claims `opensoft/r9#41`; L2's claim of `r9#41`, another object
    whose spellings meet L1's, is LR005 `claim-spellings`, and nothing is
    written."""
    c = lr5(clones)
    c.committed(claim5(c, LA5, OBJ5))
    refused5(c, claim5(c, LB5, OBJ5_ALIAS), "LR005", "claim-spellings",
             "a claim's spellings overlap another lane's live claim (D19)")


def test_lr005_refuses_a_hold_over_another_lanes_open_taker(clones):
    """D18: L1's HOLD on `opensoft/r9` commits; L2's later HOLD on it is
    LR005 `main-held`, and nothing is written."""
    c = lr5(clones)
    c.write(LA5, hold(c, LA5, spellings=REPO_SPELLINGS[KEY]))
    refused5(c, c.append(LB5, *hold(c, LB5, spellings=REPO_SPELLINGS[KEY])), "LR005", "main-held",
             "another lane holds main for this repository first (D18)")
    assert c.open_takes(LA5, "hold") == [[KEY, None]] and c.open_takes(LB5, "hold") == []


@pytest.mark.parametrize("case", ["hold-key-first", "landing-key-first", "hold-alias-first",
                                  "landing-alias-first"])
def test_two_spellings_of_one_repository_hold_one_main(clones, case):
    """Lane 1's v2.3, in four forms: L2 takes one spelling of the repository,
    then L4 the other (`r9` after `opensoft/r9`, or the reverse), each line's
    `repo_key` the canonical key and its `repo_spellings` both; L4's take is
    LR005 `main-held`, and main has one taker."""
    c = lr5(clones)
    kind, first = case.split("-", 1)
    typed = [KEY, ALIAS] if first == "key-first" else [ALIAS, KEY]
    pr = None if kind == "hold" else PR
    slot = "HOLD" if kind == "hold" else "LANDING"

    def take(lane: str, repo: str) -> Tuple[str, dict]:
        return line(c, slot, lane, repo=repo, key=KEY, spellings=REPO_SPELLINGS[repo], pr=pr)

    c.write(LB5, take(LB5, typed[0]))
    refused5(c, c.append(LD5, *take(LD5, typed[1])), "LR005", "main-held",
             "another lane holds main for this repository first (D18)")
    assert c.open_takes(LB5, kind) == [[KEY, pr]] and c.open_takes(LD5, kind) == []


def test_lr005_rolls_back_the_head_and_every_row(clones):
    """LR005 is raised after the head moved, the journal row went in, the
    edits applied and the structured rows went in (steps 4 to 7): the head,
    the journal, its edits and files, `doc_lines`, `log_lines` and
    `object_holds` all equal their values before, and the write id is absent."""
    c = lr5(clones)
    c.committed(claim5(c, LA5, OBJ5))
    head, before = c.head(), tables(c)
    proc, write_id = c.commit(claim5(c, LB5, OBJ5_ALIAS))
    assert proc.returncode == 3 and proc.stderr.startswith("ERROR:  LR005: "), proc.stderr
    after = tables(c)
    for table in TABLES5:
        assert after[table] == before[table], f"{table} changed under LR005"
    assert c.head() == head
    assert c.value(f"SELECT count(*) FROM {REGISTER}.journal WHERE seq > {head} OR write_id = '{write_id}';") == "0"
    assert c.value(f"SELECT count(*) FROM {REGISTER}.doc_lines WHERE path = '{log_path(LB5)}';") == "0"


def test_lr005_does_not_fire_on_a_released_claims_spellings(clones):
    """L1 claims `opensoft/r9#41` and releases it; L2's claim of `r9#41` then
    commits: a released hold carries no spellings and is no live claim."""
    c = lr5(clones)
    c.committed(claim5(c, LA5, OBJ5))
    c.committed(claim5(c, LA5, OBJ5, verb="RELEASED"))
    seq = c.committed(claim5(c, LB5, OBJ5_ALIAS))
    said = c.json(f"SELECT json_agg(json_build_array(object, lane_key, verb, superseded_by, spellings) "
                  f"ORDER BY object, lane_key) FROM {REGISTER}.object_holds WHERE object IN ('{OBJ5}', '{OBJ5_ALIAS}');")
    assert said == [[OBJ5, LA5.lower(), "RELEASED", None, None],
                    [OBJ5_ALIAS, LB5.lower(), "CLAIMED", None, [OBJ5_ALIAS, OBJ5]]], said
    assert seq == c.head()


@pytest.mark.parametrize("token", ["one-live-claim", "claim-spellings", "main-held"])
def test_each_claim_and_main_rule_lr005_carries_its_detail_token(clones, token):
    """U7: each rule's LR005 names it in its message, and its DETAIL is
    exactly the rule's token: L2's claim of L1's object (one_live_claim's
    23505, raised again), of its other spelling (D19), and L2's HOLD behind
    L1's (D18)."""
    c = lr5(clones)
    if token == "main-held":
        c.write(LA5, hold(c, LA5, spellings=REPO_SPELLINGS[KEY]))
        refused5(c, c.append(LB5, *hold(c, LB5, spellings=REPO_SPELLINGS[KEY])), "LR005", token,
                 "another lane holds main for this repository first (D18)")
        return
    c.committed(claim5(c, LA5, OBJ5))
    if token == "claim-spellings":
        refused5(c, claim5(c, LB5, OBJ5_ALIAS), "LR005", token,
                 "a claim's spellings overlap another lane's live claim (D19)")
    else:
        lines = refused5(c, claim5(c, LB5, OBJ5), "LR005", token)
        assert lines[0].startswith("ERROR:  LR005: the object is held (one_live_claim): "), lines


# ------------------------------------------------------------ AT-LR009: the act's key
MALFORMED_ACTS = {
    "id-with-an-at": {"id": "act@t232"},
    "id-with-a-space": {"id": "act t232"},
    "id-not-a-string": {"id": 232},
    "base-a-string": {"base": "head"},
    "base-negative": {"base": -1},
    "base-not-whole": {"base": 1.5},
    "generation-not-a-uuid": {"generation": "generation-t232"},
    "expect-not-a-list": {"expect": "row:l1-t232"},
    "element-not-a-string": {"expect": [232]},
    "element-a-star": {"expect": ["*"]},
    "element-row-with-no-name": {"expect": ["row:"]},
    "element-with-white-space": {"expect": ["row:l1 t232"]},
    "on-an-import": None,
}


@pytest.mark.parametrize("case", list(MALFORMED_ACTS))
def test_a_malformed_act_is_refused_lr004_before_the_head_lock(clones, head_holder, case):
    """Each of the test plan's rewrites of the `act` key, and an `act` on an
    import entry, by a direct call: LR004, `the entry's act is not well
    formed`, while a session holds the head row throughout, so a check after
    the lock would end 55P03 at the call's lock_timeout; nothing is written."""
    c = lr5(clones)
    head = c.head()
    if case == "on-an-import":
        edits, files, _ = c.appended(LANES_MD, ["# Lanes (T232)"], create=True)
        entry = {"journal": c.journal("import", "import", OPERATOR, git_commit=GIT_COMMIT, git_tree=GIT_TREE),
                 "not_after": c.not_after(), "edits": edits, "files": files,
                 "act": act5(c, head, [f"row:{LA5.lower()}"])}
    else:
        act = act5(c, head, [f"row:{LA5.lower()}"])
        act.update(MALFORMED_ACTS[case])
        if case == "base-a-string":
            act["base"] = str(head)
        entry = claim5(c, LA5, OBJ5_FREE, act=act)
    before = tables(c)
    head_holder(c)
    write_id = str(uuid.uuid4())
    proc = c.call(LOCKED_SQL, base=head, wid=write_id, client=c.client(), gen=c.switch()["generation"],
                  entry=json.dumps(entry, ensure_ascii=False))
    lines = proc.stderr.splitlines()
    assert proc.returncode == 3, f"exit {proc.returncode}: {proc.stderr.strip()}"
    assert lines[:1] == ["ERROR:  LR004: the entry's act is not well formed"], lines
    assert "55P03" not in proc.stderr, proc.stderr
    assert tables(c) == before
    assert c.value(f"SELECT count(*) FROM {REGISTER}.journal WHERE write_id = '{write_id}';") == "0"


def test_act_id_is_the_acts_id_on_a_write_and_null_on_every_other_entry(clones):
    """`journal.act_id`: a write made in an act stores the act's id as
    given; a write outside any act, the import, the cutover, a
    `stray-import`, a `stray-revert` and a rollback store NULL."""
    c = estate5(clones)
    said = c.json(f"SELECT json_object_agg(kind, seq) FROM (SELECT kind, max(seq) AS seq FROM {REGISTER}.journal "
                  "WHERE kind IN ('import', 'cutover') GROUP BY kind) k;")
    in_act = c.committed(claim5(c, LA5, OBJ5_FREE, act=act5(c, c.head(), [])))
    outside = c.committed(set_row_state(c, LA5))
    stray = c.committed(stray_import(c, LC5, f"{OTHER_KEY}#10"))
    revert = c.committed(stray_revert(c))
    ids = act_ids(c)
    assert ids[in_act] == ACT_ID
    for name, seq in (("a write outside any act", outside), ("the import", said["import"]),
                      ("the cutover", said["cutover"]), ("a stray-import", stray), ("a stray-revert", revert)):
        assert ids[seq] is None, f"{name}, seq {seq}, stores act_id {ids[seq]!r}"
    rollback = c.committed(rollback_entry(c))
    assert act_ids(c)[rollback] is None


def test_the_act_id_checks_refuse_an_act_id_on_another_kind_and_a_malformed_one(clones):
    """As the admin under `SET ROLE lanes_register_owner`: `act_id` set on the
    cutover's row fails 23514 on `journal_act_id_write`, and a write's set to
    `a@b` or `a b` fails 23514 on `journal_act_id_check`."""
    c = estate5(clones)
    write = c.committed(claim5(c, LA5, OBJ5_FREE, act=act5(c, c.head(), [])))
    cases = [("kind = 'cutover'", ACT_ID, "journal_act_id_write"),
             (f"seq = {write}", "a@b", "journal_act_id_check"),
             (f"seq = {write}", "a b", "journal_act_id_check")]
    for where, value, constraint in cases:
        proc = c.db.psql("\\set VERBOSITY verbose\nSET ROLE lanes_register_owner;\n"
                         f"UPDATE {REGISTER}.journal SET act_id = '{value}' WHERE {where};\n", check=False)
        assert proc.returncode != 0 and "ERROR:  23514: " in proc.stderr, f"{where} = {value!r}: {proc.stderr}"
        assert f'violates check constraint "{constraint}"' in proc.stderr, proc.stderr
    assert act_ids(c)[write] == ACT_ID


@pytest.mark.parametrize("case", ["set-row-state", "lane-kind-line", "claim", "takeover", "rename-lane",
                                  "archive-rows"])
def test_each_entry_stores_the_keys_its_lines_derive(clones, case):
    """Steps 5a and 8a: each committed entry's `journal_scopes` holds exactly
    the keys the scopes table's rules give its lines, step 5a's old side and
    step 8a's new side, `objects:` for every lane holding an object it wrote
    a hold for, and never a key the client sent."""
    c = estate5(clones)
    l1, l2, l3, l2b = (lane.lower() for lane in (LA5, LB5, LC5, LB5_NEW))
    if case == "set-row-state":
        entry, want = set_row_state(c, LA5), {f"row:{l1}", f"sid:{SID5[LA5]}"}
    elif case == "lane-kind-line":
        d = Draft(c, LA5, "log")
        d.log("PAUSED", LA5, f"lane:{LA5}")
        entry, want = d.entry(), {f"bind:{l1}", f"sid:{SID5[LA5]}"}
    elif case == "claim":
        entry, want = claim5(c, LA5, OBJ5_FREE), {f"objects:{l1}"}
    elif case == "takeover":
        d = Draft(c, LC5, "claim")
        d.log("TAKEOVER", LC5, OBJ5)
        entry, want = d.entry(), {f"objects:{l3}", f"objects:{l2}"}
    elif case == "rename-lane":
        entry = rename_lane(c)
        want = {f"row:{l2}", f"row:{l2b}", f"sid:{SID5[LB5]}", f"bind:{l2}", f"bind:{l2b}",
                f"objects:{l2}", f"objects:{l2b}", f"alias:{l2}", f"alias:{l2b}"}
    else:
        entry, want = archive_rows(c), {f"row:{FOO}", f"archive:{FOO}", "archive:foo-3"}
    seq = c.committed(entry)
    got = scopes_at(c, seq)
    assert set(got) == want, f"[{case}] stores {got}, not {sorted(want)}"
    if case == "claim":
        assert not [k for k in got if k.startswith("bind:")], got


def test_an_import_a_cutover_and_a_rollback_store_only_the_star_key(clones):
    """`*` is the one key of an import, a cutover and a rollback."""
    c = clones()
    imported = c.head()
    assert c.value(f"SELECT kind FROM {REGISTER}.journal WHERE seq = {imported};") == "import"
    assert scopes_at(c, imported) == ["*"]
    cutover = c.to_primary()
    assert scopes_at(c, cutover) == ["*"]
    rollback = c.committed(rollback_entry(c))
    assert scopes_at(c, rollback) == ["*"]


def test_a_stray_import_stores_its_keys_and_a_stray_revert_none(clones):
    """A `stray-import` stores its lines' keys as a write does; a
    `stray-revert` stores none."""
    c = estate5(clones)
    stray = c.committed(stray_import(c))
    assert scopes_at(c, stray) == [f"objects:{LA5.lower()}"]
    revert = c.committed(stray_revert(c))
    assert scopes_at(c, revert) == []


def test_an_aborted_cutover_and_a_reimport_leave_no_scopes_at_a_deleted_seq(clones):
    """The cascade: a cutover aborted by `switch_to_files`, then an import's
    reset before any confirmed cutover, each succeed and leave no
    `journal_scopes` row at a seq the journal no longer holds."""
    c = clones()
    imported = c.head()
    edits, files, _ = c.appended(STORE, ["primary"])
    cutover = c.committed({"journal": c.journal("cutover", "cutover", OPERATOR), "not_after": c.not_after(),
                           "edits": edits, "files": files})
    assert scopes_at(c, cutover) == ["*"]
    proc = c.call(ABORT_SQL, client=c.client(), seq=cutover, lane=OPERATOR, ws=WS)
    assert (proc.returncode, proc.stdout.strip()) == (0, str(imported)), proc.stderr
    assert scopes_at(c, cutover) == [] and orphans(c) == 0
    edits, files, _ = c.appended(LANES_MD, ["# Lanes (T232's import)"], create=True)
    seq = c.committed({"journal": c.journal("import", "import", OPERATOR, git_commit=GIT_COMMIT, git_tree=GIT_TREE),
                       "not_after": c.not_after(), "edits": edits, "files": files})
    assert scopes_at(c, seq) == ["*"] and orphans(c) == 0
    assert c.value(f"SELECT count(*) FROM {REGISTER}.journal_scopes WHERE seq > {seq};") == "0"


def test_lr009_names_the_first_changed_scope_its_seq_lane_and_verb(clones):
    """Step 3b: with two entries outside the act after its base, at k1 < k2,
    each touching `row:l1`, LR009 names k1, its lane and its verb; with one
    entry touching two listed scopes, it names the first in byte order."""
    c = estate5(clones)
    row1, sid1 = f"row:{LA5.lower()}", f"sid:{SID5[LA5]}"
    base = c.head()
    k1 = c.committed(set_row_state(c, LA5, "PAUSED"))
    k2 = c.committed(set_row_state(c, LA5, "ACTIVE"))
    assert k1 < k2
    refused5(c, claim5(c, LA5, OBJ5_FREE, act=act5(c, base, [row1])), "LR009", None,
             f"expectation: {row1} changed at seq {k1} by {LA5}/set-row-state")
    base = c.head()
    k3 = c.committed(set_row_state(c, LA5, "PAUSED"))
    assert {row1, sid1} <= set(scopes_at(c, k3))
    refused5(c, claim5(c, LA5, OBJ5_FREE, act=act5(c, base, [sid1, row1])), "LR009", None,
             f"expectation: {row1} changed at seq {k3} by {LA5}/set-row-state")


def test_an_entry_outside_any_act_refuses_an_acts_write_lr009(clones):
    """Step 3b: an entry after the act's base, made outside any act
    (`act_id` NULL), that touched `row:l1` refuses the act's write with
    LR009; an `expect` sent as `ROW:L1` is compared in lower case and refused
    the same way."""
    c = estate5(clones)
    row1 = f"row:{LA5.lower()}"
    base = c.head()
    k = c.committed(set_row_state(c, LA5))
    assert act_ids(c)[k] is None
    for expect in ([row1], [row1.upper()]):
        refused5(c, claim5(c, LA5, OBJ5_FREE, act=act5(c, base, expect)), "LR009", None,
                 f"expectation: {row1} changed at seq {k} by {LA5}/set-row-state")


def test_a_star_key_after_the_base_is_reported_as_the_first_listed_scope(clones):
    """`*` after the base: an act based at the import, before the cutover's
    `*`, is refused LR009 naming its first listed scope, not the first in
    byte order, at the cutover's seq, by the cutover's lane and verb."""
    c = clones()
    base = c.head()
    cutover = c.to_primary()
    assert cutover == base + 1
    expect = [f"row:{LC5.lower()}", f"row:{LA5.lower()}"]
    refused5(c, claim5(c, LA5, OBJ5_FREE, act=act5(c, base, expect)), "LR009", None,
             f"expectation: {expect[0]} changed at seq {cutover} by {OPERATOR}/cutover")


def test_an_empty_expectation_records_act_id_and_checks_nothing(clones):
    """An empty `LANES_EXPECT`, sent as `expect: []`, records the act's id and
    checks nothing, so the write commits after an entry that touched
    `row:l1`."""
    c = estate5(clones)
    base = c.head()
    c.committed(set_row_state(c, LA5))
    seq = c.committed(claim5(c, LA5, OBJ5_FREE, act=act5(c, base, [])))
    assert seq == c.head() and act_ids(c)[seq] == ACT_ID


def test_lr002_comes_before_lr009_after_a_rollback(clones):
    """A direct call after a rollback's entry has set the switch to `files`
    gets LR002, not LR009, though an entry after its base touched its listed
    scope: step 3 comes before step 3b."""
    c = estate5(clones)
    base = c.head()
    c.committed(set_row_state(c, LA5))
    c.committed(rollback_entry(c))
    sw = c.switch()
    assert (sw["mode"], sw["marker_state"]) == ("files", "removing"), sw
    refused5(c, claim5(c, LA5, OBJ5_FREE, act=act5(c, base, [f"row:{LA5.lower()}"])), "LR002", None,
             "register switch is files with the marker removing")


# ============================================================ PHASE W, NO ENGINE: `register commit`'s path refusal (T243d)
#
# LANE 1'S FOLLOW-UP 2 (line R's merge13, `3a30ba89`, tag `l1-007-R-pathre`;
# #165 6783763467): `register commit` refuses with 2, before the store opens,
# a path that holds a control character, U+0085, U+2028 or U+2029, where
# `changes.tsv` stages it and on either side of a `renames.tsv` line
# (`register_path_unrenderable`, called from `read_attempt_dir`). No render of
# the register could write such a path as one `file=` row, and the database's
# CHECKs admit every character but `/`, so this refusal is the only guard.
# Lane 1: "no test covers the attempt directory's path checks".
#
# NO ENGINE. T203's flipped copy runs `register commit` under a `mode=primary`
# configuration whose URLs name 127.0.0.1, with a `psql` first on `PATH` that
# only logs its calls: "before the store opens" is that log left empty. Each
# attempt directory is contract section 3.3's, whole, as lane 1's hand checks
# build it (`runs/R-pathre/mkattempt.py`): a scratch tree at seq n, then
# `snapshot`, `not_after`, `changes.tsv`, `images/`, `files`, `msg` and
# `author`. A `changes` case adds a log at the path (an A line). A `renames`
# case appends a line to its lane's log (an M line) and names the path on one
# side of a `renames.tsv` line that `changes.tsv` does not name, since a side
# that `changes.tsv` also stages is refused first, as `changes.tsv stages`.
# The place asserted is lane 1's text: the file, the side, and the path as
# `repr` prints it. On merge12 a `changes` case reaches the store, and a
# `renames` case is refused by the D and A check, which names no side, so
# each FAILS there by its own assertion; from merge13 on each passes.

PATH_LANE, PATH_WS, PATH_N = "L1-t243d", "ws-t243d", 41
#: Each case: the file that names the path, the side of the `renames.tsv`
#: line (None for `changes.tsv`), and the character the path holds.
UNRENDERABLE = {
    "changes-u0001": ("changes.tsv", None, 0x0001),
    "changes-u0085": ("changes.tsv", None, 0x0085),
    "changes-u2028": ("changes.tsv", None, 0x2028),
    "changes-u2029": ("changes.tsv", None, 0x2029),
    "renames-old-u2028": ("renames.tsv", "<from>", 0x2028),
    "renames-new-u2029": ("renames.tsv", "<to>", 0x2029),
}
#: The prefixes of the test's own environment that the run of `lanes-index` does not inherit.
PATH_DROPPED = ("GIT_", "PG", "LANES_", "TMUX", "RULE6_", "FAKE_PSQL", "CLAUDE_", "PROJECTS_ROOT",
                "XDG_", "OPENREPOTOOLS_BIN_DIR", "AGENT_PROTOCOL_ROOT")


def unrenderable_attempt(root: Path, case: str, env: dict) -> Tuple[Path, List[str], str]:
    """`case`'s whole attempt directory under `root`, the `register commit`
    argv that sends it, and the place its refusal must name."""
    where, side, code = UNRENDERABLE[case]
    bad = f"lanes/log/a{chr(code)}b.md"
    att = root / "attempt"
    tree = att / "tree"
    tree.mkdir(parents=True)
    sid = session_of(PATH_LANE)

    def log_line(verb: str, lane: str, utc: str, what: str) -> str:
        return f"{verb} {EM} lane {lane}, session {sid}@{PATH_WS}, {utc}, {what}\n"

    def log_head(lane: str) -> str:
        return f"# lane {lane} {EM} object log (lane-collision-protocol Amendment 7)\n"

    log = f"lanes/log/{PATH_LANE}.md"
    register = {"lanes/LANES.md": "# Lanes\n", "lanes/repos.tsv": "# alias\towner/repo\nr9\topensoft/r9\n",
                "lanes/aliases.tsv": "# old\tnew\tutc\n", "lanes/log/README.md": "# logs\n",
                log: log_head(PATH_LANE) + log_line("STARTED", PATH_LANE, "2026-11-01T00:00:00Z",
                                                    f"lane:{PATH_LANE} home opensoft/r9")}
    for path, text in register.items():
        (tree / path).parent.mkdir(parents=True, exist_ok=True)
        (tree / path).write_bytes(text.encode("utf-8"))
    run_git(tree, "init", "-q", "-b", "main", env=env)
    run_git(tree, "add", "-A", env=env)
    run_git(tree, "commit", "-q", "-m", f"register snapshot at seq {PATH_N}", env=env)
    if where == "changes.tsv":
        path, verb, old = bad, "log", None
        new = (log_head("added") + log_line("STARTED", "added", "2026-11-09T12:00:00Z",
                                            "lane:added home opensoft/r9")).encode("utf-8")
    else:
        path, verb, old = log, "claim", register[log].encode("utf-8")
        new = old + log_line("CLAIMED", PATH_LANE, "2026-11-09T12:00:00Z", "opensoft/r9#7").encode("utf-8")
        sides = (bad, f"lanes/log/{PATH_LANE}-moved.md") if side == "<from>" else (log, bad)
        (att / "renames.tsv").write_bytes(("\t".join(sides) + "\n").encode("utf-8"))
    image = att / "images" / path
    image.parent.mkdir(parents=True)
    image.write_bytes(new)
    new_blob = run_git(tree, "hash-object", "--no-filters", str(image), env=env).strip()
    base_blob = "0" * 40 if old is None else run_git(tree, "rev-parse", f"HEAD:{path}", env=env).strip()
    (att / "changes.tsv").write_bytes(
        f"{'A' if old is None else 'M'}\t{path}\t{base_blob}\t{new_blob}\n".encode("utf-8"))
    (att / "files").write_bytes(f"{path}\t1\t{hashlib.sha256(new).hexdigest()}\n".encode("utf-8"))
    write_id, generation, clock = str(uuid.uuid4()), str(uuid.uuid4()), int(time.time())
    repos_blob = run_git(tree, "rev-parse", "HEAD:lanes/repos.tsv", env=env).strip()
    snapshot = {"format": 1, "generation": generation, "write_id": write_id, "switch": "primary",
                "marker": "present", "n": PATH_N, "clock": clock, "not_after": clock + 10, "schema": 1,
                "repos_blob": repos_blob, "c": 2, "n_a": 1}
    (att / "snapshot").write_text("".join(f"{k}={v}\n" for k, v in snapshot.items()), encoding="utf-8")
    (att / "not_after").write_text(f"{clock + 10}\n", encoding="utf-8")
    (att / "msg").write_text(f"LANES({PATH_LANE}@{PATH_WS}): {verb} {EM} T243d's case\n", encoding="utf-8")
    (att / "author").write_text("T243d Tester <t243d@example.invalid>\n", encoding="utf-8")
    argv = ["register", "commit", "--write-id", write_id, "--generation", generation, "--lane", PATH_LANE,
            "--verb", verb, "--args-sha256", hashlib.sha256(case.encode("utf-8")).hexdigest(),
            "--workstation", PATH_WS, str(att)]
    place = f"changes.tsv stages {bad!r}" if side is None else f"renames.tsv line 1's {side} is {bad!r}"
    return att, argv, place


@CLIENT
@pytest.mark.parametrize("case", list(UNRENDERABLE))
def test_register_commit_refuses_an_unrenderable_path_with_2_before_the_store_opens(tmp_path, case):
    """Lane 1's follow-up 2 (#165 6783763467): an attempt directory whose
    `changes.tsv` stages a path holding U+0001, U+0085, U+2028 or U+2029
    ([changes-*]), or whose `renames.tsv` line holds U+2028 on its `<from>`
    side ([renames-old-u2028]) or U+2029 on its `<to>` side
    ([renames-new-u2029]), makes `register commit` exit 2, with stderr naming
    the file, the side and the path, and no `psql` call: the store is never
    opened."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(PATH_DROPPED)}
    (tmp_path / "home").mkdir()
    env.update(HOME=str(tmp_path / "home"), XDG_STATE_HOME=str(tmp_path / "state"),
               XDG_CONFIG_HOME=str(tmp_path / "config"), GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="T243d", GIT_AUTHOR_EMAIL="t243d@example.invalid",
               GIT_COMMITTER_NAME="T243d", GIT_COMMITTER_EMAIL="t243d@example.invalid", LC_ALL="C")
    _att, argv, place = unrenderable_attempt(tmp_path, case, env)
    copy = flipped_copy(LANES_INDEX, tmp_path / "bin", True)
    (tmp_path / "bin" / "repos.tsv").write_text("# alias\towner/repo\n", encoding="utf-8")
    conf = tmp_path / "lanes-index.conf"
    conf.write_text("mode=primary\nregister_url=postgresql://lanes_w_t243d@127.0.0.1:9/t243d\n"
                    "reader_url=postgresql://lanes_r_t243d@127.0.0.1:9/t243d\n", encoding="utf-8")
    conf.chmod(0o600)
    calls = tmp_path / "psql.log"
    _write(tmp_path / "fakebin" / "psql", f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "{calls}"\nexit 2\n')
    env.update(LANES_INDEX_CONFIG=str(conf),
               PATH=str(tmp_path / "fakebin") + os.pathsep + env.get("PATH", os.defpath))
    r = subprocess.run([sys.executable, str(copy), *argv], cwd=str(tmp_path), env=env, capture_output=True,
                       encoding="utf-8", errors="replace", timeout=120, stdin=subprocess.DEVNULL, check=False)
    sent = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
    assert r.returncode == 2, (
        f"[{case}] register commit exited {r.returncode}, not 2, after {len(sent)} psql calls: {r.stderr[-900:]}")
    assert sent == [], f"[{case}] register commit called psql before it refused: {sent}"
    assert place in r.stderr, f"[{case}] stderr does not name {place!r}: {r.stderr[-900:]}"
