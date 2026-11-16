# SPDX-License-Identifier: Apache-2.0
"""The register's schema at the engine (#165, L2-N6 and L2-W4): AT-MIR's phase-N
cases, AT-VER, AT-LR010, the one-number rule, `register snapshot`'s own output,
and AT-SET, AT-SPL and AT-LR4.

WHAT IT CHECKS, by the test plan's entries and lane 2's task T221:

  * AT-MIR (D16): `mirror_state` starts as one empty row; `record_mirror_state`
    records a divergence and a failed pass, keeps the first divergence, and
    never clears one; a malformed sha is 23514; REGISTER-WRITER alone may
    execute it, and no role may UPDATE or DELETE the table; only a
    `stray-import` or `stray-revert` entry clears the divergence. Its gating
    case, "the row never gates alone", is T271's, in phase G.
  * AT-VER (design §1.5): a client outside the version window is refused,
    LR003 at `commit_write` and 69 from `lanes-index`; a migration against an
    older writer snapshot ends 40001 then LR003, or LR003 at once; a second
    bootstrap adds no migration; a migration out of order is LR003; `ready`'s
    check 9 fails a client outside the window. The out-of-window clients are
    copies of `lanes-index` made by T203's `flipped_copy`, as test 14's are,
    with `REGISTER_SCHEMA_VERSION` rewritten in the copy alone.
  * AT-LR010 (lane 1's v2.5): `line_scopes` and `doc_line_scopes` by the scopes
    table's rules, S3's normalized `archive:` key, `entry_new_keys`, and N2's
    `scope_fault` and `scope_checked`, whose LR010 refuses a write or an import
    a line of which derives a key that is not well formed. The five functions
    are called as `lanes_register_owner`, since section 1.4 grants no role
    EXECUTE on them.
  * `test_every_copy_of_register_schema_version_in_a_release_is_one_number`,
    new since v3f (NOTES question 4): design §1.5's hygiene test. It reads
    files, and needs no engine.
  * `test_register_snapshot_prints_its_keys_in_the_contracts_order_and_refuses_with_its_codes`,
    new since v3f (R-F9-3): lane 1's T111 alone, from CLI4.10 and L1v4.10.
  * `test_the_bootstrap_renders_register_schema_both_ways_and_refuses_the_rest`,
    new since v3f (R-F10-1): DEC-23's rendering of `register_schema=` by
    `lanes-index bootstrap`, lane 1's T109 with T104's key. Its two rendering
    ids ask for the session cluster at run time and bootstrap empty databases
    of their own; its four refusal ids need no engine.
  * `test_commit_write_derives_step_6s_deletes_so_the_tables_equal_the_imports_derivation`,
    new since v3f (R-F10-34, R-F13-2): T107's step 6 and step 7 at the engine. Its
    four ids from lane 3's ruling (c) (two renames, two strays), and case 6a's two,
    `[6a-replace]` and `[6a-remove]`, where the entry takes away the line that holds
    a lane's hold on an object and sends no hold on it: the tables equal the
    import's derivation, step 7 re-marks `superseded_by` and stamps no `seq` or
    `mode`, and step 5a's `objects:` keys name every lane holding the object.
  * T231 (L2-W4, in phase N by R1's M3): AT-SET, `set_seq` and the marker's
    states, moved only by `commit_write` and `record_marker`, LR002 while
    `adding` or `removing`, the rollback's entry, each kind against each state,
    `switch_to_files`, the re-import form's abort, `restore_prior`, LR004 for
    an operator entry outside `lanes/STORE`, and the switch's checks; AT-SPL, a
    claim's spellings; and AT-LR4, LR004 by the shim's `edit-entry` mode on
    `register commit`'s own call, LR004's one re-read (R02), `not_after`, the
    operator flag and a file with no final newline. Its section's head says
    which lane 1 task each part drives.
  * `test_an_entry_without_a_path_in_changes_tsv_is_refused_2_before_the_store_opens`,
    new since B15 (lane 3, #165 6808937880, batch e Q88): T112's refusal of an
    empty change set, 2 from `register commit` before the store opens, through
    the same writer as AT-LR4's cases. T112's word `an_entry_without` selects it.
  * `test_a_write_with_a_files_row_for_a_path_it_does_not_edit_is_refused_lr004_at_commit`,
    new since spec#17's re-review r4 (lane 3's ruling 5, #165 6878977318): a
    `write`'s `files` rows are its edited paths, each a render-set path or
    `lanes/STORE`; one more row, outside the render set or for a file the
    write leaves untouched, is LR004 at `commit_write`, by a direct call.
  * `test_a_stray_revert_with_a_files_row_for_lanes_store_is_refused_lr004_at_commit`,
    new since spec#17's re-review r5 (its finding 10; lane 3's ruling, commit
    22's post): an edit-free `stray-revert` whose one `files` row is
    `lanes/STORE`, which is not rendered, is LR004 at `commit_write`, by a
    direct call.
  * `test_a_final_newline_only_change_on_a_render_set_path_commits` and
    `test_a_final_newline_only_change_to_lanes_store_is_refused_lr004_at_commit`,
    new since spec#17's re-review r9 (lane 3's ruling 3, #165 6885378657; its
    commit 27): a change of only a final newline is an edit, so a `write`'s or a
    `stray-import`'s present `files` row that only flips `lanes/aliases.tsv`'s
    stored final newline commits, while the same row for `lanes/STORE` is LR004
    at `commit_write`, by direct calls.
  * `test_a_stray_revert_files_row_that_would_change_the_register_is_refused_lr004_at_commit`
    and `test_a_stray_revert_files_row_that_proves_the_register_commits`, new
    since spec#17's re-review r10 (lane 3's commit 28): a stray revert's `files`
    rows prove the register's current truth and never change it, so a row that
    would change it is LR004 at `commit_write`'s fourth check of step 8, and
    rows that prove it commit, by direct calls. Since spec#17's re-review r11
    (lane 3's commit 29), so is a present-false row for a path in `files`, with
    the fourth check's own message (r12).

REAL ENGINE. Every case but the one-number rule and DEC-23's test asks for
`pg`, one database cloned from the session's template, so its fixture closure
holds `pg_engine` (T200's rule). The cases assume the template that T227
builds by `lanes-index bootstrap --no-passwords`; on T205's empty template they
fail, since the schema is not there. Without PostgreSQL 16 they skip with
T205's banner. DEC-23's two rendering ids take `pg_cluster` by
`request.getfixturevalue`, so they skip the same way, but that function's
closure does not hold `pg_engine`; its name holds neither word of the launch
job's filter, so T200's check is unaffected. T231's three cutover cases take
`pg_cluster` itself, so their closure holds `pg_engine`, and bootstrap a
database of their own with a scratch `register_schema=`.

A REGISTER ON `primary` with the marker `present` is reached as AT-LR006's
fixture reaches it (the test plan at 4610-4615): by the documented functions as
`lanes_register_writer`, `commit_write` with an `import` entry, then with a
`cutover` entry, then `record_marker`. Only T231's three cutover cases run
`lanes-index cutover`, against a scratch schema of their own: its whole row,
T116's transaction and T327's push of the marker, from the operator lane's
own checkout onto a real commit C on a local bare origin (lane 3's (c), #165
6828023371; T221k).

THE ROLES. The test's own `psql` connects as the fixture's superuser and takes
each role by `SET ROLE`, so a case needs no login of its own except where
`lanes-index` connects: there two logins, made once per session, join the
writer and the reader groups, and connect by the cluster's trust.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import REPO, git
from pgcluster import Database
from sql_register_helpers import (LANES_INDEX, LANES_INDEX_MODULE, PSQL_SHIM, PSQL_SHIM_CONTROL,
                                  PSQL_SHIM_LOG, REGISTER_FAKE_PSQL, RENDER_GIT_HALF_LINE,
                                  flipped_copy)

#: THE LANDING GATE'S TABLE (T280's reader, `tests/sql_register_gate.py`), TEMPORARY:
#: T281 removes it in the last set. Where the gate is active, an id is skipped until
#: every task its row names has landed: a function's row holds for each of its ids, and
#: an id's own row, `name[param]`, takes the place of its function's. There is no `"*"`
#: row, since the waits share no task. Each row is the fails-until clause of its task's
#: **Order**, T221's (tasks:2127) or T231's (tasks:2231) at lane 3's commit 17,
#: 204145ae, each lane 1 label read as the tasks it covers; T221's "only until" rows on
#: `pg` add T110, by that Order's L1-A8 clause. DEC-23's rendering test waits for T104,
#: T105 and T109, and its two engine ids for T110 as well.
SQL_REGISTER_GATE_TABLE = {
    "test_a_claim_records_its_spelling_its_key_and_its_aliases": ("T107", "T108", "T111", "T112"),  # T231; tasks:2231
    "test_a_client_outside_the_version_window_is_refused_lr003": ("T107", "T108", "T109", "T110", "T111", "T113", "T119", "T120"),  # T221; tasks:2127
    "test_a_failed_pass_record_leaves_the_divergence_as_it_was": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_a_file_without_a_final_newline_renders_back_byte_identical": ("T107", "T108", "T111", "T112"),  # T231; tasks:2231
    "test_a_final_newline_only_change_on_a_render_set_path_commits": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231, lane 3's ruling 3 (#165 6885378657), spec#17's re-review r9 (lane 3's commit 27, 07a40aef)
    "test_a_final_newline_only_change_to_lanes_store_is_refused_lr004_at_commit": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231, spec#17's re-review r9 and its delta review 7i (lane 3's commit 27, 07a40aef)
    "test_a_migration_against_an_older_snapshot_ends_69": ("T107", "T108", "T109", "T110", "T111", "T119", "T120"),  # T221; tasks:2127
    "test_a_migration_out_of_order_is_refused_lr003": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_a_released_claims_spellings_block_nothing": ("T107", "T108", "T111", "T112"),  # T231; tasks:2231
    "test_a_second_bootstrap_at_the_same_version_adds_no_migration": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_a_second_divergence_report_keeps_the_first": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_a_stray_import_or_revert_clears_the_divergence": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_a_stray_revert_files_row_that_proves_the_register_commits": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231, Codex's delta review 7j of commit 27, its item 4 (lane 3's commit 28, 6450dce2)
    "test_a_stray_revert_files_row_that_would_change_the_register_is_refused_lr004_at_commit": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231, spec#17's re-review r10 (lane 3's commit 28, 6450dce2)
    "test_a_stray_revert_with_a_files_row_for_lanes_store_is_refused_lr004_at_commit": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231, spec#17's re-review r5, its finding 10 (lane 3's commit 22, 4d00a20b)
    "test_a_write_is_refused_lr002_while_the_marker_is_adding_or_removing": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_a_write_that_deletes_a_line_with_a_bad_key_is_refused_lr010": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_a_write_with_a_files_row_for_a_path_it_does_not_edit_is_refused_lr004_at_commit": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231, lane 3's ruling 5 (#165 6878977318)
    "test_an_entry_without_a_path_in_changes_tsv_is_refused_2_before_the_store_opens": ("T107", "T108", "T111", "T112"),  # T231; tasks:2231
    "test_an_entry_without_a_valid_not_after_is_refused": ("T107", "T108", "T111", "T112"),  # T231; tasks:2231
    "test_an_import_carries_not_after_of_its_330_s_timer_plus_2_s": ("T115",),  # T231; tasks:2231
    "test_an_import_whose_line_derives_a_bad_key_is_refused_lr010_and_writes_nothing": ("T107", "T108", "T109", "T110", "T115"),  # T221; tasks:2127
    "test_an_operator_entry_with_a_row_outside_lanes_store_is_refused_lr004_at_commit": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_commit_write_derives_step_6s_deletes_so_the_tables_equal_the_imports_derivation": ("T107", "T110", "T227"),  # T221; tasks:2127
    "test_doc_line_scopes_adds_objects_from_the_structured_rows": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_entry_new_keys_reads_the_new_side_and_every_holder": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_every_copy_of_register_schema_version_in_a_release_is_one_number": ("T107", "T108", "T109", "T110", "T119", "T120"),  # T221; tasks:2127
    "test_line_scopes_derives_each_scope_by_its_rule": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_lr004_on_an_edit_or_proof_that_does_not_apply_leaves_everything_unchanged": ("T107", "T108", "T111", "T112"),  # T231; tasks:2231
    "test_lr004_reloads_once_then_exits_69": ("T107", "T108", "T111", "T112"),  # T231; tasks:2231
    "test_mirror_state_refuses_a_malformed_sha": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_mirror_state_starts_as_one_empty_row": ("T107", "T108", "T109", "T110", "T119", "T120"),  # T221; tasks:2127
    "test_no_kind_commits_in_a_state_its_kinds_table_row_refuses": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_only_register_writer_executes_record_mirror_state_and_none_updates_the_table": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_ready_fails_a_client_outside_the_version_window": ("T107", "T108", "T109", "T110", "T119", "T120"),  # T221; tasks:2127
    "test_record_mirror_state_records_a_divergence_and_a_failed_pass": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_register_snapshot_prints_its_keys_in_the_contracts_order_and_refuses_with_its_codes": ("T107", "T109", "T110", "T111"),  # T221; tasks:2127
    "test_restore_prior_is_set_by_the_restore_form_and_cleared_by_record_marker": ("T116", "T327"),  # T231; tasks:2231
    "test_scope_checked_raises_lr010_naming_the_path_the_line_and_the_key": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_scope_fault_shows_each_white_space_character": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_set_seq_after_a_cutover_is_the_cutovers_own_seq": ("T116", "T327"),  # T231; tasks:2231
    "test_set_seq_is_minus_1_after_the_bootstrap": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_switch_to_files_aborts_only_an_unconfirmed_cutover": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_the_bootstrap_renders_register_schema_both_ways_and_refuses_the_rest": ("T104", "T105", "T109"),  # T221; tasks:2127
    "test_the_journal_scopes_check_takes_a_no_break_space": ("T107", "T108", "T109", "T110"),  # T221; tasks:2127
    "test_the_marker_moves_only_through_commit_write_and_record_marker": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_the_operator_flag_rules_refuse_lr004": ("T107", "T108", "T111", "T112"),  # T231; tasks:2231
    "test_the_reimport_forms_abort_leaves_label_and_generation": ("T116", "T327"),  # T231; tasks:2231
    "test_the_rollbacks_entry_makes_an_older_writer_snapshot_fail_lr001_or_40001_then_69": ("T107", "T108", "T111", "T112"),  # T231; tasks:2231
    "test_the_rollbacks_entry_sets_files_removing_and_its_own_seq": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_the_switch_checks_refuse_a_bad_set_seq_and_a_mode_marker_mismatch": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_lr004_on_an_edit_or_proof_that_does_not_apply_leaves_everything_unchanged[operator-no-edit]": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_lr004_on_an_edit_or_proof_that_does_not_apply_leaves_everything_unchanged[root-seq-on-a-non-empty-journal]": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_the_bootstrap_renders_register_schema_both_ways_and_refuses_the_rest[default-unchanged]": ("T104", "T105", "T109", "T110"),  # T221; tasks:2127
    "test_the_bootstrap_renders_register_schema_both_ways_and_refuses_the_rest[scratch-every-site]": ("T104", "T105", "T109", "T110"),  # T221; tasks:2127
    "test_the_operator_flag_rules_refuse_lr004[operator-edits-nothing]": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
    "test_the_operator_flag_rules_refuse_lr004[operator-edits-other]": ("T107", "T108", "T109", "T110"),  # T231; tasks:2231
}

SCHEMA = "lanes_register"
OWNER, WRITER, READER = "lanes_register_owner", "lanes_register_writer", "lanes_register_reader"

#: The logins `lanes-index` connects as in this module's cases. Made once per
#: cluster, members of the writer and the reader groups, with no password.
LOGIN_WRITER, LOGIN_READER = "t221_register_writer", "t221_register_reader"

#: The tables of design §1.2, compared whole where a case says "nothing written".
TABLES = ("schema_version", "migrations", "register_switch", "register_head", "mirror_state",
          "journal", "journal_edits", "journal_files", "journal_scopes", "files", "doc_lines",
          "lanes", "log_lines", "object_holds", "register_lines")

#: What the cases stamp an entry with.
LANE, WS, AUTHOR = "Lane-T221", "ws-t221", "T221 <t221@example.invalid>"
COMMIT_C, TREE_C, MARKER_COMMIT = "c" * 40, "d" * 40, "e" * 40
ARGS_SHA256 = "a" * 64
NOT_AFTER = "2100-01-01T00:00:00Z"            # well past every case (lane 1's v2.3)
STORE_LABEL = "t221"                          # the bootstrap case's `--label`; `config()` sets no label
STORE_UTC = "2026-11-09T10:00:00Z"            # fixed, so the file's sha256 is the same every run
# D21 (Y:613-615 at a6497d00); one field per line is a reading until T116 writes it; lane 1, #165 6754714549
STORE_LINES = ("store=primary", f"database={STORE_LABEL}", f"import={COMMIT_C}",
               f"lanes-tree={TREE_C}", f"utc={STORE_UTC}")
SHA_A, SHA_B = "1" * 40, "2" * 40

#: The configuration's own values, so `c=` and `n_a=` are not the defaults.
CONNECT_TIMEOUT, ADDRESSES = 3, 2

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ERROR_RE = re.compile(r"ERROR:\s+([0-9A-Z]{5}):\s+(.*)")

#: Unicode's 25 White_Space code points (PropList.txt), U+00A0 among them.
WHITE_SPACE = (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0x85, 0xA0, 0x1680,
               *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000)
EM_DASH = "\u2014"
NBSP = "\u00a0"


# ------------------------------------------------------------------ the SQL side
def sql_text(text: str) -> str:
    """`text` as a SQL expression of ASCII alone: quoted runs, and `chr(n)` for
    every character outside printable ASCII, so no client encoding decides it."""
    parts, run = [], []
    for ch in text:
        if 0x20 <= ord(ch) < 0x7F:
            run.append(ch)
            continue
        if run:
            parts.append("'" + "".join(run).replace("'", "''") + "'")
            run = []
        parts.append(f"chr({ord(ch)})")
    if run or not parts:
        parts.append("'" + "".join(run).replace("'", "''") + "'")
    return "(" + " || ".join(parts) + ")"


def psql(db, script: str, role: str = None, appname: str = "t221") -> subprocess.CompletedProcess:
    """One `psql` as the fixture's superuser, with the commit call's settings
    (`VERBOSITY=verbose`, `SHOW_CONTEXT=never`), so a refusal's first stderr
    line is `ERROR:  <SQLSTATE>: <message>`; as `role` where one is named."""
    head = "\\set VERBOSITY verbose\n\\set SHOW_CONTEXT never\nSET client_encoding = 'UTF8';\n"
    if role:
        head += f"SET ROLE {role};\n"
    return subprocess.run([db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                          input=head + script, capture_output=True, encoding="utf-8",
                          errors="replace", env=db.env(appname=appname), timeout=120,
                          check=False)


def sql(db, script: str, role: str = None) -> str:
    """`psql`, which must succeed; its stdout, stripped."""
    proc = psql(db, script, role)
    assert proc.returncode == 0, (f"psql{' as ' + role if role else ''} exited "
                                  f"{proc.returncode}: {proc.stderr.strip()}\n{script}")
    return proc.stdout.strip()


def error_of(proc: subprocess.CompletedProcess):
    """(SQLSTATE, message) of the first `ERROR:` line on stderr, or (None, None)."""
    m = ERROR_RE.search(proc.stderr or "")
    return (m.group(1), m.group(2).strip()) if m else (None, None)


def refused(proc: subprocess.CompletedProcess, code: str, what: str) -> str:
    """Assert that `proc` ended with `code`, and give the message."""
    got, message = error_of(proc)
    assert proc.returncode != 0 and got == code, (
        f"{what}: expected {code}, got exit {proc.returncode} and {got}: {proc.stderr.strip()}")
    return message


def state(db) -> dict:
    """Every table of design §1.2, each as one sorted JSON array."""
    lines = sql(db, "\n".join(
        f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), '[]') "
        f"FROM {SCHEMA}.{table} t;" for table in TABLES)).splitlines()
    assert len(lines) == len(TABLES), lines
    return {table: json.loads(line) for table, line in zip(TABLES, lines)}


def mirror_row(db) -> dict:
    rows = json.loads(sql(db, f"SELECT coalesce(jsonb_agg(to_jsonb(m)), '[]') "
                              f"FROM {SCHEMA}.mirror_state m;"))
    assert len(rows) == 1, f"mirror_state holds {len(rows)} rows, not one: {rows}"
    return rows[0]


def window(db, schema: str = SCHEMA) -> dict:
    return json.loads(sql(db, f"SELECT to_jsonb(v) FROM {schema}.schema_version v;"))


def generation(db, schema: str = SCHEMA) -> str:
    return sql(db, f"SELECT generation FROM {schema}.register_switch;")


def head(db, schema: str = SCHEMA) -> int:
    return int(sql(db, f"SELECT seq FROM {schema}.register_head;"))


def record_mirror_state(db, ws, sha, error, role=WRITER) -> subprocess.CompletedProcess:
    return psql(db, f"SELECT {SCHEMA}.record_mirror_state({sql_text(ws)}, "
                    f"{'NULL' if sha is None else sql_text(sha)}, "
                    f"{'NULL' if error is None else sql_text(error)});", role)


# ------------------------------------------------------------------ the entries
def file_bytes(lines, final_newline: bool = True) -> bytes:
    """A file of `lines` as `render_file` renders it: LF-joined, with a final
    LF where `final_newline` (`journal_files.final_newline`, AT-LR4)."""
    return ("\n".join(lines) + ("\n" if final_newline and lines else "")).encode("utf-8")


def rendered(lines, final_newline: bool = True) -> str:
    """The sha256 of a file of `lines`, as `render_file` renders it."""
    return hashlib.sha256(file_bytes(lines, final_newline)).hexdigest()


def line_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def entry(kind: str, verb: str, **parts) -> dict:
    """One `commit_write` entry: the journal object, `not_after`, and `parts`."""
    journal = {"kind": kind, "verb": verb, "lane": LANE, "workstation": WS,
               "author": AUTHOR, "message": f"t221: {kind}"}
    journal.update(parts.pop("journal", {}))
    return {"journal": journal, "not_after": NOT_AFTER, **parts}


def import_entry(files: dict, no_newline=(), *, commit: str = COMMIT_C, tree: str = TREE_C,
                 **rows) -> dict:
    """An import of `files` (path to its lines): each created, then its lines
    appended, and each path's digest as it renders; each path in `no_newline`
    with no final newline (AT-LR4's fixture file). The journal names `commit`
    and its `lanes` tree `tree`: the fixed `COMMIT_C` and `TREE_C`, but for
    the cutover's cases, whose step 2 reads a real C (`OperatorEstate`)."""
    edits, ord_ = [], 0
    for path in sorted(files):
        ord_ += 1
        edits.append({"ord": ord_, "op": "create", "path": path})
        for text in files[path]:
            ord_ += 1
            edits.append({"ord": ord_, "op": "append", "path": path, "new_text": text})
    return entry("import", "import", journal={"git_commit": commit, "git_tree": tree},
                 edits=edits,
                 files=[{"path": p, "present": True,
                         "sha256": rendered(files[p], p not in no_newline),
                         "final_newline": p not in no_newline} for p in sorted(files)], **rows)


def cutover_entry() -> dict:
    return entry("cutover", "cutover",
                 edits=[{"ord": 1, "op": "create", "path": "lanes/STORE"},
                        *({"ord": n, "op": "append", "path": "lanes/STORE", "new_text": line}
                          for n, line in enumerate(STORE_LINES, start=2))],
                 files=[{"path": "lanes/STORE", "present": True,
                         "sha256": rendered(STORE_LINES), "final_newline": True}])


def commit_call(db, base: int, body: dict, *, write_id: str = None, client: int = None,
                gen: str = None, role: str = WRITER, appname: str = "t221",
                schema: str = SCHEMA) -> subprocess.CompletedProcess:
    """The commit call as the writer sends it (section 1.3's step 3; AT-LR006's
    fixture): one SERIALIZABLE transaction around `commit_write`, in `schema`."""
    write_id = write_id or str(uuid.uuid4())
    client = window(db, schema)["version"] if client is None else client
    gen = gen or generation(db, schema)
    literal = json.dumps(body, ensure_ascii=True).replace("'", "''")
    return psql(db, f"BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
                    f"SELECT {schema}.commit_write({base}, '{write_id}'::uuid, {client}, "
                    f"'{gen}'::uuid, '{literal}'::jsonb);\nCOMMIT;\n", role, appname)


def committed(db, base: int, body: dict, what: str, schema: str = SCHEMA) -> int:
    proc = commit_call(db, base, body, schema=schema)
    assert proc.returncode == 0, f"{what}: commit_write refused it: {proc.stderr.strip()}"
    return int(proc.stdout.strip().splitlines()[-1])


DEFAULT_FILES = {"lanes/LANES.md": ["# Lanes"]}


def bring_to_primary(db, files: dict = None, **rows) -> int:
    """AT-LR006's route (TP:4610-4615): as `lanes_register_writer`, an import,
    then a cutover, then `record_marker`. Returns the head, the cutover's seq."""
    imported = committed(db, head(db), import_entry(files or DEFAULT_FILES, **rows), "the import")
    cut = committed(db, imported, cutover_entry(), "the cutover")
    marker = sql(db, f"SELECT {SCHEMA}.record_marker({window(db)['version']}, {cut}, "
                     f"'{MARKER_COMMIT}', '{WS}');", WRITER)
    assert marker == "present", f"record_marker answered {marker!r}, not present"
    switch = json.loads(sql(db, f"SELECT to_jsonb(s) FROM {SCHEMA}.register_switch s;"))
    assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
    return cut


def scopes(db, call: str) -> set:
    """A set-returning scope function's rows, called as the owner."""
    out = sql(db, f"SELECT coalesce(jsonb_agg(s), '[]') FROM {call} AS s;", OWNER)
    return set(json.loads(out))


# ------------------------------------------------------------------ lanes-index
def ensure_logins(db) -> None:
    """The writer's and the reader's login, once per cluster (roles are
    cluster-wide), members of their groups, with no floor and no password."""
    for login, group in ((LOGIN_WRITER, WRITER), (LOGIN_READER, READER)):
        sql(db, f"DO $l$ BEGIN CREATE ROLE {login} LOGIN IN ROLE {group}; "
                f"EXCEPTION WHEN duplicate_object THEN NULL; END $l$;")


def config(tmp_path: Path, db, mode: str = "primary") -> Path:
    """A 0600 `lanes-index.conf` whose register URLs name the session cluster's
    socket, with `connect_timeout=` and `register_addresses=` of its own."""
    ensure_logins(db)
    path = tmp_path / "lanes-index.conf"
    query = f"?connect_timeout={CONNECT_TIMEOUT}"
    path.write_text(f"mode={mode}\n"
                    f"register_url={db.url(LOGIN_WRITER)}{query}\n"
                    f"reader_url={db.url(LOGIN_READER)}{query}\n"
                    f"register_addresses={ADDRESSES}\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def index_env(tmp_path: Path, conf: Path, **extra) -> dict:
    """The environment `lanes-index` runs in: no inherited `PG*`, no
    `LANES_INDEX` (#160's switch, which `tests/conftest.py` sets), this case's
    configuration and state directory."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG") and k != "LANES_INDEX"}
    env.update(LANES_INDEX_CONFIG=str(conf), XDG_STATE_HOME=str(tmp_path / "state"), **extra)
    return env


def run_index(copy: Path, args, env: dict, cwd: Path = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(copy), *args], capture_output=True,
                          encoding="utf-8", errors="replace", env=env, timeout=120,
                          cwd=str(cwd) if cwd else None, check=False)


def flipped(tmp_path: Path, name: str = "bin") -> Path:
    """T203's flipped copy, `RENDER_GIT_HALF = True`, so `mode=primary` loads."""
    return flipped_copy(LANES_INDEX, tmp_path / name, True)


CONSTANT_LINE = re.compile(r"^REGISTER_SCHEMA_VERSION = [0-9]+$", re.M)


def window_copy(tmp_path: Path, number: int) -> Path:
    """A flipped copy whose `REGISTER_SCHEMA_VERSION` is `number`: AT-VER's
    client outside the window (open point 3), in the copy alone, whose body
    is T124's module beside it."""
    copy = flipped(tmp_path, f"client-{number}")
    module = copy.with_name(LANES_INDEX_MODULE)
    text = module.read_text(encoding="utf-8")
    assert len(CONSTANT_LINE.findall(text)) == 1, (
        f"{LANES_INDEX_MODULE} holds no single `REGISTER_SCHEMA_VERSION = <n>` line to rewrite")
    module.write_text(CONSTANT_LINE.sub(f"REGISTER_SCHEMA_VERSION = {number}", text),
                      encoding="utf-8")
    return copy


def shown(proc: subprocess.CompletedProcess) -> str:
    return (f"exit {proc.returncode}\n--- stdout ---\n{proc.stdout[-3000:]}"
            f"\n--- stderr ---\n{proc.stderr[-3000:]}")


def names_both(text: str, a: int, b: int) -> bool:
    return bool(re.search(rf"\b{a}\b", text)) and bool(re.search(rf"\b{b}\b", text))


# =================================================================== AT-MIR
def test_mirror_state_starts_as_one_empty_row(pg):
    """After the bootstrap, exactly one row, every column but `id` NULL."""
    row = mirror_row(pg)
    assert row.pop("id") == 1, row
    assert row and all(value is None for value in row.values()), (
        f"a bootstrapped mirror_state row has a value set: {row}")


def test_record_mirror_state_records_a_divergence_and_a_failed_pass(pg):
    """`record_mirror_state(ws, <40-hex sha>, NULL)` sets `diverged_sha`,
    `found_utc` and `found_by_ws`; `(ws, NULL, '<error>')` sets `last_error` and
    `last_error_utc`."""
    proc = record_mirror_state(pg, "ws-a", SHA_A, None)
    assert proc.returncode == 0, proc.stderr
    row = mirror_row(pg)
    assert (row["diverged_sha"], row["found_by_ws"]) == (SHA_A, "ws-a"), row
    assert row["found_utc"] is not None, row
    assert row["last_error"] is None and row["last_error_utc"] is None, row
    proc = record_mirror_state(pg, "ws-b", None, "the push was refused")
    assert proc.returncode == 0, proc.stderr
    row = mirror_row(pg)
    assert row["last_error"] == "the push was refused" and row["last_error_utc"] is not None, row


def test_a_failed_pass_record_leaves_the_divergence_as_it_was(pg):
    """A failed pass's record, and a clean pass's after it, leave the
    divergence as it was: only the single-write import and the revert clear
    it (D16)."""
    assert record_mirror_state(pg, "ws-a", SHA_A, None).returncode == 0
    before = mirror_row(pg)
    assert record_mirror_state(pg, "ws-b", None, "render failed").returncode == 0
    after = mirror_row(pg)
    for key in ("diverged_sha", "found_utc", "found_by_ws"):
        assert after[key] == before[key], f"a failed pass's record changed {key}: {after}"
    assert after["last_error"] == "render failed", after
    assert record_mirror_state(pg, "ws-c", None, None).returncode == 0
    clean = mirror_row(pg)
    for key in ("diverged_sha", "found_utc", "found_by_ws"):
        assert clean[key] == before[key], f"a clean pass's record changed {key}: {clean}"
    assert clean["last_error"] is None and clean["last_error_utc"] is None, clean


def test_a_second_divergence_report_keeps_the_first(pg):
    """A second call with another sha leaves the first divergence as it was:
    the function keeps the first one found (section 1.3)."""
    assert record_mirror_state(pg, "ws-a", SHA_A, None).returncode == 0
    first = mirror_row(pg)
    time.sleep(1.1)                               # found_utc is whole seconds
    assert record_mirror_state(pg, "ws-b", SHA_B, None).returncode == 0
    second = mirror_row(pg)
    assert (second["diverged_sha"], second["found_utc"], second["found_by_ws"]) == (
        first["diverged_sha"], first["found_utc"], first["found_by_ws"]), (first, second)


def test_mirror_state_refuses_a_malformed_sha(pg):
    """A sha that is not 40 lower-case hex digits fails with 23514, and the
    row is unchanged."""
    before = mirror_row(pg)
    for bad in ("1" * 39, "1" * 41, "A" * 40, "g" * 40, "", " " + "1" * 39):
        proc = record_mirror_state(pg, "ws-a", bad, None)
        refused(proc, "23514", f"record_mirror_state with the sha {bad!r}")
        assert mirror_row(pg) == before, f"the sha {bad!r} changed the row"


def test_only_register_writer_executes_record_mirror_state_and_none_updates_the_table(pg):
    """READER's call fails with 42501. REGISTER-WRITER's direct `UPDATE` or
    `DELETE` of `mirror_state`, inside `BEGIN READ WRITE`, fails with 42501
    (section 1.4: SELECT on the tables, EXECUTE on the functions). The
    writer's own call, the control, commits."""
    before = mirror_row(pg)
    refused(record_mirror_state(pg, "ws-r", SHA_A, None, role=READER), "42501",
            "READER's call of record_mirror_state")
    for statement in (f"UPDATE {SCHEMA}.mirror_state SET last_error = 'x' WHERE id = 1;",
                      f"DELETE FROM {SCHEMA}.mirror_state WHERE id = 1;"):
        refused(psql(pg, f"BEGIN READ WRITE;\n{statement}\nCOMMIT;\n", WRITER), "42501",
                f"REGISTER-WRITER's {statement.split()[0]}")
    assert mirror_row(pg) == before
    assert record_mirror_state(pg, "ws-w", SHA_A, None).returncode == 0
    assert mirror_row(pg)["diverged_sha"] == SHA_A


@pytest.mark.parametrize("kind", ["import", "revert"])
def test_a_stray_import_or_revert_clears_the_divergence(pg, kind):
    """A `stray-import` entry, and in a second case a `stray-revert` entry,
    through `commit_write`, leaves `diverged_sha` and `found_utc` NULL. The
    revert is an empty journal entry (D16)."""
    n = bring_to_primary(pg)
    assert record_mirror_state(pg, "ws-a", SHA_A, None).returncode == 0
    assert mirror_row(pg)["diverged_sha"] == SHA_A
    if kind == "import":
        lines = DEFAULT_FILES["lanes/LANES.md"] + ["a stray line"]
        body = entry("stray-import", "import --single", journal={"git_commit": SHA_B},
                     edits=[{"ord": 1, "op": "append", "path": "lanes/LANES.md",
                             "new_text": lines[-1]}],
                     files=[{"path": "lanes/LANES.md", "present": True,
                             "sha256": rendered(lines), "final_newline": True}])
    else:
        body = entry("stray-revert", "render --revert", journal={"git_commit": SHA_B})
    assert committed(pg, n, body, f"the stray-{kind} entry") == n + 1
    row = mirror_row(pg)
    assert row["diverged_sha"] is None and row["found_utc"] is None, row
    assert row["found_by_ws"] is None, row


# =================================================================== AT-VER
@pytest.mark.parametrize("case", ["writer-old", "writer-new", "reader-old", "reader-new"])
def test_a_client_outside_the_version_window_is_refused_lr003(pg, tmp_path, case):
    """A writer below `writers_from`, or above `version`, gets LR003 from
    `commit_write`, naming both numbers, with nothing written, and its
    `lanes-index` exits 69 naming both numbers and the remedy. A reader outside
    `readers_from` to `version` exits 69 with nothing on stdout past its
    `mode` line, which `register read` prints first in every form (lane 3,
    #165 6807694145: "the contract stands"; 4.18:758-760; B14 tasks:454;
    T221j). The copies' constant is one below the floor or one above
    `version` (open point 3)."""
    role, side = case.split("-")
    win = window(pg)
    floor = win["writers_from" if role == "writer" else "readers_from"]
    number = floor - 1 if side == "old" else win["version"] + 1
    remedy = "upgrade the tools" if side == "old" else "run the bootstrap"
    before = state(pg)
    copy = window_copy(tmp_path, number)
    env = index_env(tmp_path, config(tmp_path, pg))
    if role == "writer":
        lines = DEFAULT_FILES["lanes/LANES.md"]
        message = refused(commit_call(pg, head(pg), import_entry({"lanes/LANES.md": lines}),
                                      client=number), "LR003", f"a writer at {number}")
        assert names_both(message, win["version"], number), message
        proc = run_index(copy, ["register", "snapshot", "--write-id", "new", "--lane", LANE,
                                "--verb", "log", "--args-sha256", ARGS_SHA256], env)
    else:
        (tmp_path / "cache").mkdir()
        proc = run_index(copy, ["register", "read", "--prefetch", "--cache",
                                str(tmp_path / "cache" / "register"), "--files", "register"],
                         env)
    assert proc.returncode == 69, f"a {role} at {number}:\n{shown(proc)}"
    assert names_both(proc.stderr, win["version"] if side == "new" else floor, number), shown(proc)
    assert remedy in proc.stderr, f"the refusal names no remedy ({remedy!r}):\n{shown(proc)}"
    # A refused writer prints nothing; a refused reader, its `mode primary`
    # line and nothing more (this configuration is mode=primary).
    printed = "mode primary\n" if role == "reader" else ""
    assert proc.stdout == printed, \
        f"a refused {role} printed {proc.stdout!r}, not {printed!r}:\n{shown(proc)}"
    assert state(pg) == before, f"a {role} outside the window changed the register"


def migration_script(number: int, commit: bool = True) -> str:
    """A migration as section 1.5's step 3 gives it, sent by the admin as the
    bootstrap sends a script: one transaction that touches the head row,
    checks that `version` is one below its own (else LR003), adds a table,
    raises `version` and the floors, and records its `migrations` row."""
    body = (f"BEGIN;\nSET LOCAL ROLE {OWNER};\nSET LOCAL search_path TO {SCHEMA}, pg_catalog;\n"
            f"SET LOCAL lock_timeout = '2000ms';\n"
            f"UPDATE register_head SET seq = seq WHERE id = 1;\n"
            f"DO $m$ BEGIN IF (SELECT version FROM schema_version WHERE id = 1) <> {number - 1} "
            f"THEN RAISE EXCEPTION 'migration {number} needs schema version {number - 1}, not %', "
            f"(SELECT version FROM schema_version WHERE id = 1) USING ERRCODE = 'LR003'; "
            f"END IF; END $m$;\n"
            f"CREATE TABLE t221_migration_{number} (id integer);\n"
            f"UPDATE schema_version SET version = {number}, writers_from = {number}, "
            f"readers_from = {number}, applied_utc = date_trunc('second', clock_timestamp()) "
            f"WHERE id = 1;\n"
            f"INSERT INTO migrations (version, script_sha256, by_lane, by_ws) "
            f"VALUES ({number}, '{'f' * 64}', '{LANE}', '{WS}');\n")
    return body + ("COMMIT;\n" if commit else "")


def wait_for(db, appname: str, condition: str, what: str, ceiling: float = 5.0) -> None:
    """Poll `pg_stat_activity` for `appname`'s backend, in 0.05 s steps under
    `ceiling`, until `condition` holds. No sleep stands in for a barrier."""
    end = time.monotonic() + ceiling
    while time.monotonic() < end:
        if sql(db, f"SELECT count(*) FROM pg_stat_activity a WHERE a.application_name = "
                   f"'{appname}' AND a.datname = current_database() AND ({condition});") != "0":
            return
        time.sleep(0.05)
    pytest.fail(f"{what}: not seen in pg_stat_activity within {ceiling} s")


def session(db, appname: str) -> subprocess.Popen:
    return subprocess.Popen([db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                            env=db.env(appname=appname))


def a_write(db) -> dict:
    lines = DEFAULT_FILES["lanes/LANES.md"] + ["a written line"]
    return entry("write", "log", journal={"args_sha256": ARGS_SHA256},
                 edits=[{"ord": 1, "op": "append", "path": "lanes/LANES.md",
                         "new_text": lines[-1]}],
                 files=[{"path": "lanes/LANES.md", "present": True, "sha256": rendered(lines),
                         "final_newline": True}])


@pytest.mark.parametrize("case", ["held-40001", "in-turn-lr003"])
def test_a_migration_against_an_older_snapshot_ends_69(pg, tmp_path, case):
    """Held: the migration's transaction holds the head row uncommitted, the
    writer's commit call is seen waiting on it, and the migration commits:
    40001, then the re-read meets the new window, LR003, so 69. In turn: the
    migration commits before the commit call starts; the head's seq is
    unchanged, so there is no LR001, and step 2 raises LR003. Either way the
    shipped client's next snapshot exits 69 naming both numbers."""
    n = bring_to_primary(pg)
    win, gen = window(pg), generation(pg)
    client, number = win["version"], win["version"] + 1
    body = a_write(pg)
    if case == "held-40001":
        migration = session(pg, "t221-migration")
        migration.stdin.write("\\set VERBOSITY verbose\n" + migration_script(number, commit=False))
        migration.stdin.flush()
        wait_for(pg, "t221-migration", "a.state = 'idle in transaction'", "the migration held")
        writer = session(pg, "t221-commit")
        writer.stdin.write("\\set VERBOSITY verbose\n\\set SHOW_CONTEXT never\n"
                           f"SET ROLE {WRITER};\nBEGIN ISOLATION LEVEL SERIALIZABLE;\n"
                           f"SELECT {SCHEMA}.commit_write({n}, '{uuid.uuid4()}'::uuid, {client}, "
                           f"'{gen}'::uuid, '{json.dumps(body).replace(chr(39), chr(39) * 2)}'"
                           f"::jsonb);\nCOMMIT;\n")
        writer.stdin.close()
        writer.stdin = None
        wait_for(pg, "t221-commit", "a.wait_event_type = 'Lock' AND cardinality("
                 "pg_blocking_pids(a.pid)) > 0", "the commit call waiting on the head row")
        _, err = migration.communicate("COMMIT;\n", timeout=60)
        assert migration.returncode == 0, f"the migration failed: {err}"
        out, err = writer.communicate(timeout=60)
        code, _ = error_of(subprocess.CompletedProcess([], writer.returncode, out, err))
        assert writer.returncode != 0 and code == "40001", (
            f"the held commit call ended {writer.returncode}, {code}: {err}")
    else:
        assert psql(pg, migration_script(number)).returncode == 0
    assert window(pg)["version"] == number
    message = refused(commit_call(pg, n, body, client=client), "LR003",
                      "the commit call after the migration")
    assert names_both(message, number, client), message
    assert head(pg) == n, "a commit call that met LR003 moved the head"
    proc = run_index(flipped(tmp_path), ["register", "snapshot", "--write-id", "new", "--lane",
                                         LANE, "--verb", "log", "--args-sha256", ARGS_SHA256],
                     index_env(tmp_path, config(tmp_path, pg)))
    assert proc.returncode == 69 and names_both(proc.stderr, number, client), shown(proc)


def admin_env(tmp_path: Path, db) -> dict:
    """The bootstrap's environment: its admin service in `$HOME/.pg_service.conf`,
    naming this case's database, since `lanes-index` drops every inherited
    `PG*` variable before it sets `PGSERVICE` (ops:404), and no configuration
    file, which the bootstrap does not need."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (home / ".pg_service.conf").write_text(
        f"[t221_admin]\nhost={db.host}\nport={db.port}\ndbname={db.name}\nuser=lanes_test\n",
        encoding="utf-8")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PG") and k not in ("LANES_INDEX", "LANES_INDEX_CONFIG")}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
               XDG_STATE_HOME=str(tmp_path / "state"), LANES_WORKSTATION=WS)
    return env


def test_a_second_bootstrap_at_the_same_version_adds_no_migration(pg, tmp_path):
    """`bootstrap` run again at the same version prints `unchanged` and adds no
    `migrations` row. Each `migrations` row carries its script's sha256,
    `by_lane` and `by_ws`."""
    before = json.loads(sql(pg, f"SELECT coalesce(jsonb_agg(to_jsonb(m) ORDER BY m.version), "
                                f"'[]') FROM {SCHEMA}.migrations m;"))
    assert before, "a bootstrapped register has no migrations row"
    for row in before:
        assert re.fullmatch(r"[0-9a-f]{64}", row["script_sha256"]), row
        assert row["by_lane"] and row["by_ws"], row
    proc = run_index(LANES_INDEX, ["bootstrap", "--admin-service", "t221_admin", "--label",
                                   "t221", "--repository", "opensoft/t221", "--lane", LANE,
                                   "--no-passwords"], admin_env(tmp_path, pg))
    assert proc.returncode == 0, shown(proc)
    assert re.search(rf"^schema {SCHEMA}: unchanged\b", proc.stdout, re.M), shown(proc)
    assert not re.search(r"^migration [0-9]+: created", proc.stdout, re.M), shown(proc)
    after = json.loads(sql(pg, f"SELECT coalesce(jsonb_agg(to_jsonb(m) ORDER BY m.version), "
                               f"'[]') FROM {SCHEMA}.migrations m;"))
    assert after == before, f"a second bootstrap changed migrations: {before} -> {after}"


def test_a_migration_out_of_order_is_refused_lr003(pg):
    """A migration whose number is not one above `version` fails with LR003
    and changes nothing."""
    before = state(pg)
    number = window(pg)["version"] + 2
    refused(psql(pg, migration_script(number)), "LR003", f"migration {number}")
    assert state(pg) == before, "a migration out of order changed the register"
    assert sql(pg, f"SELECT to_regclass('{SCHEMA}.t221_migration_{number}') IS NULL;") == "t"


def test_ready_fails_a_client_outside_the_version_window(pg, tmp_path):
    """`ready`'s check 9 (operations §2.4; lane 3's ruling 6578020193) fails a
    client outside the window, naming both numbers; the shipped client's
    check 9 does not fail."""
    conf = config(tmp_path, pg, mode="index")
    env = index_env(tmp_path, conf, LANES_WORKSTATION=WS)
    args = ["ready", "--expect", "index", "--release", "0.0.0", "--env", "t221"]
    win = window(pg)
    number = min(win["writers_from"], win["readers_from"]) - 1    # too old: "upgrade the tools"

    def schema_fails(proc):
        return [line for line in proc.stdout.splitlines() if line.startswith("check 9: FAIL")]

    inside = run_index(flipped(tmp_path), args, env)
    assert not schema_fails(inside), f"the shipped client fails check 9:\n{shown(inside)}"
    outside = run_index(window_copy(tmp_path, number), args, env)
    assert outside.returncode == 2, shown(outside)
    fails = schema_fails(outside)
    # lane 1's [P] line form for T119, #165 6754498682 item 1
    assert fails and any("upgrade the tools" in line and names_both(line, win["version"], number)
                         for line in fails), (
        f"check 9 does not fail, upgrade the tools, naming {win['version']} and {number}:\n"
        f"{shown(outside)}")


# =================================================================== AT-LR010
UUID_U = "0f8fad5b-d9cb-469f-a165-70867728950e"

#: Each `line_scopes` rule: (path, line, the scopes as a set), compared as sets.
LINE_SCOPES = {
    "row": [("lanes/LANES.md", f"| `Lane-A` | {UUID_U} | x |", {"row:lane-a", f"sid:{UUID_U}"}),
            ("lanes/LANES.md", f" | `Lane-A` | {UUID_U} |", set()),
            ("lanes/LANES.md", "| Lane-A | x |", set()),
            ("lanes/LANES.md", "| `` | x |", set())],
    "archive": [("lanes/archive/a.md", "| `foo-3` | x |", {"archive:foo-3"}),
                ("lanes/archive/a.md", "| `alpha` | x |", {"archive:alpha"}),
                ("lanes/archive/a.md", "| `foo-x3` | x |", {"archive:foo-x3"})],
    "archive-normalized": [
        ("lanes/archive/a.md", "| `foo-03` | x |", {"archive:foo-03", "archive:foo-3"}),
        ("lanes/archive/a.md", "| `Foo-3b` | x |", {"archive:foo-3b", "archive:foo-3"}),
        ("lanes/archive/a.md", "| `foo-033` | x |", {"archive:foo-033", "archive:foo-33"}),
        ("lanes/archive/a.md", "| `foo-00` | x |", {"archive:foo-00", "archive:foo-0"})],
    "long-digit-run": [
        ("lanes/archive/a.md", "| `foo-09007199254740993` | x |",
         {"archive:foo-09007199254740993", "archive:foo-9007199254740993"}),
        ("lanes/archive/a.md", "| `foo-0" + "123456789" * 3 + "12` | x |",
         {"archive:foo-0" + "123456789" * 3 + "12", "archive:foo-" + "123456789" * 3 + "12"})],
    "bind": [("lanes/log/Lane-B.md", f"{pad}{verb}{pad2}{EM_DASH} {UUID_U} on ws-b",
              {"bind:lane-b", f"sid:{UUID_U}"})
             for verb, pad, pad2 in (("STARTED", "", " "), ("RESUMED", " ", " "),
                                     ("PAUSED", "\t", "\t "), ("ENDED", "", "  "),
                                     ("RETIRED", " \t", " \t "), ("RENAMED", "", "\t "))],
    "bind-unreadable": [("lanes/log/Lane-B.md", f"PAUSED {EM_DASH} ???", {"bind:lane-b"})],
    "not-lane-kind": [("lanes/log/Lane-B.md", f"CLAIMED {EM_DASH} {UUID_U} o1", set()),
                      ("lanes/log/Lane-B.md", f"HANDOFF-REQUESTED {EM_DASH} {UUID_U}", set())],
    "alias": [("lanes/aliases.tsv", "X\tO\t2026-11-09T10:00:00Z", {"alias:x", "alias:o"})],
    "alias-comment": [("lanes/aliases.tsv", "# X\tO\t2026-11-09T10:00:00Z", set()),
                      ("lanes/aliases.tsv", "  \t O\t2026-11-09T10:00:00Z", {"alias:o"}),
                      ("lanes/aliases.tsv", " \t \t2026-11-09T10:00:00Z", set())],
    "store": [("lanes/STORE", "store=primary", set()), ("lanes/STORE", f"| `Lane-A` | {UUID_U} |", set())],
}


@pytest.mark.parametrize("case", list(LINE_SCOPES))
def test_line_scopes_derives_each_scope_by_its_rule(pg, case):
    """`line_scopes(path, text)`, one case per rule of the scopes table,
    compared as sets. A long digit run keys with no digit lost and no exponent;
    `RETIRED_ROWS_AWK`'s float key under mawk is lane 4's, and not asserted."""
    for path, text, want in LINE_SCOPES[case]:
        got = scopes(pg, f"{SCHEMA}.line_scopes({sql_text(path)}, {sql_text(text)})")
        assert got == want, f"line_scopes({path!r}, {text!r}) is {got}, not {want}"


#: `doc_line_scopes`' rows: an import of these lines and their structured rows.
DOC_LOG = "lanes/log/Lane-B.md"
DOC_FILES = {
    "lanes/LANES.md": ["# Lanes", "HOLD opensoft/r9 by Lane-D",
                       "LANDING EXPIRED opensoft/r9 #7 for lane Lane-D by Lane-E"],
    DOC_LOG: [f"CLAIMED {EM_DASH} opensoft/r9#12", "?? not a line",
              f"CLAIMED {EM_DASH} lane:Lane-C"],
}


def doc_rows() -> dict:
    log = [{"path": DOC_LOG, "line_no": 1, "raw": DOC_FILES[DOC_LOG][0], "lane": "Lane-B",
            "verb": "CLAIMED", "object": "opensoft/r9#12", "unreadable": False},
           {"path": DOC_LOG, "line_no": 2, "raw": DOC_FILES[DOC_LOG][1], "lane": "Lane-B",
            "verb": None, "object": "opensoft/r9#13", "unreadable": True,
            "unreadable_why": "no verb"},
           {"path": DOC_LOG, "line_no": 3, "raw": DOC_FILES[DOC_LOG][2], "lane": "Lane-B",
            "verb": "CLAIMED", "object": "lane:Lane-C", "unreadable": False}]
    lanes_md = DOC_FILES["lanes/LANES.md"]
    register = [{"path": "lanes/LANES.md", "line_no": 2, "raw": lanes_md[1], "kind": "HOLD",
                 "slot_role": "take", "slot_kind": "hold", "lane": "Lane-D",
                 "repo": "opensoft/r9", "repo_key": "opensoft/r9"},
                {"path": "lanes/LANES.md", "line_no": 3, "raw": lanes_md[2],
                 "kind": "LANDING EXPIRED", "slot_role": "close", "slot_kind": "landing",
                 "lane": "Lane-E", "repo": "opensoft/r9", "repo_key": "opensoft/r9", "pr": 7,
                 "for_lane": "Lane-D"}]
    return {"log_lines": log, "register_lines": register}


DOC_CASES = {"log-line": (DOC_LOG, 1, {"objects:lane-b"}),
             "unreadable": (DOC_LOG, 2, set()),
             "lane-object": (DOC_LOG, 3, set()),
             "slot-line": ("lanes/LANES.md", 2, {"objects:lane-d"}),
             "landing-expired": ("lanes/LANES.md", 3, {"objects:lane-e", "objects:lane-d"})}


@pytest.mark.parametrize("case", list(DOC_CASES))
def test_doc_line_scopes_adds_objects_from_the_structured_rows(pg, case):
    """`doc_line_scopes` adds `objects:` from a line's structured row: a
    readable `log_lines` row on an object that is not `lane:...` gives its lane,
    lower-cased; an unreadable one, or one on `lane:<x>`, gives none; a slot
    line gives its lane, and a `LANDING EXPIRED` also its `for_lane`. The lines
    are stored by an import, at `files`."""
    committed(pg, head(pg), import_entry(DOC_FILES, **doc_rows()), "the import")
    path, line_no, want = DOC_CASES[case]
    line_id = sql(pg, f"SELECT line_id FROM {SCHEMA}.doc_lines WHERE path = {sql_text(path)} "
                      f"AND line_no = {line_no};")
    assert line_id, f"{path} line {line_no} is not stored"
    got = scopes(pg, f"{SCHEMA}.doc_line_scopes({line_id}, {sql_text(path)})")
    assert got == want, f"doc_line_scopes of {path} line {line_no} is {got}, not {want}"


def test_entry_new_keys_reads_the_new_side_and_every_holder(pg):
    """`entry_new_keys(seq)` for a write's seq: each appended or replaced line's
    keys, with its path and `line_no`; each line a rename moved, at its new
    path; and `objects:` with `lower(lane_key)` for every holder of an object
    the write wrote a hold for, at that holder's file and ordinal (N1)."""
    held = f"CLAIMED {EM_DASH} o1"
    n = bring_to_primary(
        pg, {"lanes/LANES.md": ["# Lanes", "| `Lane-A` | x |"],
             "lanes/log/Lane-A.md": [held], "lanes/log/Old.md": [f"STARTED {EM_DASH} s"]},
        log_lines=[{"path": "lanes/log/Lane-A.md", "line_no": 1, "raw": held, "lane": "Lane-A",
                    "verb": "CLAIMED", "object": "o1", "unreadable": False}],
        object_holds=[{"object": "o1", "lane_key": "lane-a", "lane": "Lane-A",
                       "verb": "CLAIMED", "file": "lanes/log/Lane-A.md", "ordinal": 1}])
    opened = f"OPENED {EM_DASH} o1"
    lanes_md = ["# Lanes", "| `Lane-A2` | x |", "| `Lane-B` | y |"]
    body = entry(
        "write", "claim", journal={"args_sha256": ARGS_SHA256},
        edits=[{"ord": 1, "op": "replace", "path": "lanes/LANES.md", "line_no": 2,
                "old_sha256": line_sha("| `Lane-A` | x |"), "new_text": lanes_md[1]},
               {"ord": 2, "op": "append", "path": "lanes/LANES.md", "new_text": lanes_md[2]},
               {"ord": 3, "op": "create", "path": "lanes/log/Lane-B.md"},
               {"ord": 4, "op": "append", "path": "lanes/log/Lane-B.md", "new_text": opened},
               {"ord": 5, "op": "rename", "path": "lanes/log/Old.md",
                "to_path": "lanes/log/Lane-R.md"}],
        files=[{"path": "lanes/LANES.md", "present": True, "sha256": rendered(lanes_md),
                "final_newline": True},
               {"path": "lanes/log/Lane-B.md", "present": True, "sha256": rendered([opened]),
                "final_newline": True},
               {"path": "lanes/log/Lane-R.md", "present": True,
                "sha256": rendered([f"STARTED {EM_DASH} s"]), "final_newline": True},
               {"path": "lanes/log/Old.md", "present": False}],
        log_lines=[{"path": "lanes/log/Lane-B.md", "line_no": 1, "raw": opened, "lane": "Lane-B",
                    "verb": "OPENED", "workstation": WS, "utc": "2026-11-09T10:00:00Z",
                    "utc_ts": "2026-11-09T10:00:00Z", "object": "o1", "unreadable": False}],
        object_holds=[{"object": "o1", "lane_key": "lane-b", "lane": "Lane-B", "verb": "OPENED",
                       "utc_ts": "2026-11-09T10:00:00Z", "file": "lanes/log/Lane-B.md",
                       "ordinal": 1}])
    seq = committed(pg, n, body, "the write")
    rows = json.loads(sql(pg, f"SELECT coalesce(jsonb_agg(jsonb_build_array(k.path, k.line_no, "
                              f"k.scope)), '[]') FROM {SCHEMA}.entry_new_keys({seq}) AS k;", OWNER))
    got = {tuple(row) for row in rows}
    want = {("lanes/LANES.md", 2, "row:lane-a2"), ("lanes/LANES.md", 3, "row:lane-b"),
            ("lanes/log/Lane-R.md", 1, "bind:lane-r"),
            ("lanes/log/Lane-B.md", 1, "objects:lane-b"),
            ("lanes/log/Lane-A.md", 1, "objects:lane-a")}
    assert got == want, f"entry_new_keys({seq}) is {sorted(got)}, not {sorted(want)}"


FAULT_CASES = {f"U+{cp:04X}": (f"row:x{chr(cp)}y", f"row:x[U+{cp:04X}]y") for cp in WHITE_SPACE}
FAULT_CASES.update({"row-no-name": ("row:", "row:"), "row-upper-case": ("row:X", "row:X")})


@pytest.mark.parametrize("case", list(FAULT_CASES))
def test_scope_fault_shows_each_white_space_character(pg, case):
    """`scope_fault` is NULL for a well-formed key, and otherwise the key with
    each white-space character shown as `[U+hhhh]`: each of Unicode's 25
    White_Space code points, U+00A0 among them. `row:`, with no name, and
    `row:X`, in upper case, are returned as they are."""
    key, want = FAULT_CASES[case]
    assert len(WHITE_SPACE) == 25
    got = sql(pg, f"SELECT coalesce({SCHEMA}.scope_fault({sql_text(key)}), '<NULL>');", OWNER)
    assert got == want, f"scope_fault({key!r}) is {got!r}, not {want!r}"
    for good in ("row:xy", "archive:foo-3", "bind:lane-b", "objects:lane-b", "alias:x",
                 f"sid:{UUID_U}"):
        assert sql(pg, f"SELECT {SCHEMA}.scope_fault({sql_text(good)}) IS NULL;", OWNER) == "t", good


def test_scope_checked_raises_lr010_naming_the_path_the_line_and_the_key(pg):
    """`scope_checked(path, line, key)` returns a well-formed key as it is,
    and otherwise raises LR010 with `key: <path> line <n> derives <shown>, which
    is not a scope (...)`."""
    assert sql(pg, f"SELECT {SCHEMA}.scope_checked('lanes/LANES.md', 7, 'row:lane-a');",
               OWNER) == "row:lane-a"
    message = refused(psql(pg, f"SELECT {SCHEMA}.scope_checked('lanes/LANES.md', 7, "
                               f"{sql_text('row:x' + NBSP + 'y')});", OWNER),
                      "LR010", "scope_checked of row:x<U+00A0>y")
    assert message == ("key: lanes/LANES.md line 7 derives row:x[U+00A0]y, which is not a scope "
                       "(a scope's name is lower case, not empty, and holds no white space)"), message


def test_the_journal_scopes_check_takes_a_no_break_space(pg):
    """The CHECK is a backstop only: as the owner, in transactions the test
    rolls back, a `journal_scopes` row `row:x y` fails with 23514 on
    `journal_scopes_scope_check`, but the same key with U+00A0 is stored, since
    `[:space:]` under `COLLATE "C"` is ASCII's alone. Only `scope_checked`
    stops it."""
    seed = (f"BEGIN;\nINSERT INTO {SCHEMA}.journal (seq, write_id, kind, verb, lane, workstation, "
            f"author, message, args_sha256) VALUES (0, '{uuid.uuid4()}', 'write', 'log', "
            f"'{LANE}', '{WS}', '{AUTHOR}', 'seed', '{ARGS_SHA256}');\n")
    proc = psql(pg, seed + f"INSERT INTO {SCHEMA}.journal_scopes (seq, scope) VALUES "
                           f"(0, 'row:x y');\nROLLBACK;\n", OWNER)
    refused(proc, "23514", "a journal_scopes row row:x y")
    assert "journal_scopes_scope_check" in proc.stderr, proc.stderr
    out = sql(pg, seed + f"INSERT INTO {SCHEMA}.journal_scopes (seq, scope) VALUES "
                         f"(0, {sql_text('row:x' + NBSP + 'y')});\n"
                         f"SELECT count(*) FROM {SCHEMA}.journal_scopes WHERE seq = 0;\n"
                         f"ROLLBACK;\n", OWNER)
    assert out == "1", f"the no-break space's row was not stored: {out!r}"
    assert sql(pg, f"SELECT count(*) FROM {SCHEMA}.journal;") == "0"


def test_a_write_that_deletes_a_line_with_a_bad_key_is_refused_lr010(pg):
    """At a write's old side: a stored line that derives such a key, put in
    place by the admin as the owner, since no write or import can store one,
    and a direct call whose entry deletes it: LR010 from step 5a, naming that
    path and line, and nothing written."""
    n = bring_to_primary(pg)
    bad = "| `x y` | x |"
    sql(pg, f"INSERT INTO {SCHEMA}.doc_lines (path, line_no, text, written_seq, written_mode) "
            f"VALUES ('lanes/LANES.md', 2, {sql_text(bad)}, {n - 1}, 'files');", OWNER)
    before = state(pg)
    lines = DEFAULT_FILES["lanes/LANES.md"]
    body = entry("write", "log", journal={"args_sha256": ARGS_SHA256},
                 edits=[{"ord": 1, "op": "delete", "path": "lanes/LANES.md", "line_no": 2,
                         "old_sha256": line_sha(bad)}],
                 files=[{"path": "lanes/LANES.md", "present": True, "sha256": rendered(lines),
                         "final_newline": True}])
    message = refused(commit_call(pg, n, body), "LR010", "a write deleting a bad key's line")
    assert message.startswith("key: lanes/LANES.md line 2 derives row:x[U+0020]y,"), message
    assert state(pg) == before, "a write refused LR010 changed the register"


IMPORT_CASES = {"space": (["| `x y` | x |"], "row:x[U+0020]y", 2),
                "no-break-space": ([f"| `x{NBSP}y` | x |"], "row:x[U+00A0]y", 2),
                "two-lines": (["| `x y` | x |", "| `p q` | x |"], "row:x[U+0020]y", 2)}


def workspace_at(tmp_path: Path, bad_lines) -> tuple:
    """A files-mode workspace repository whose commit C, on a bare origin,
    holds `lanes/LANES.md` with `bad_lines` after its heading."""
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    git("init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    git("init", "-q", "-b", "main", str(work), cwd=tmp_path)
    files = {"lanes/LANES.md": ["# Lanes", *bad_lines], "lanes/repos.tsv": ["r9\topensoft/r9"],
             "lanes/log/README.md": ["# Logs"], "lanes/aliases.tsv": []}
    for rel, lines in files.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes("".join(line + "\n" for line in lines).encode("utf-8"))
    git("add", "lanes", cwd=work)
    git("-c", "user.name=T221", "-c", "user.email=t221@example.invalid", "commit", "-q", "-m",
        "C", cwd=work)
    git("remote", "add", "origin", str(origin), cwd=work)
    git("push", "-q", "origin", "main", cwd=work)
    git("fetch", "-q", "origin", cwd=work)
    return work, git("rev-parse", "HEAD", cwd=work).stdout.strip()


@pytest.mark.parametrize("case", list(IMPORT_CASES))
def test_an_import_whose_line_derives_a_bad_key_is_refused_lr010_and_writes_nothing(
        pg, tmp_path, case):
    """At an import: a commit whose `lanes/LANES.md` holds the row-shaped line
    ``| `x y` |``: `lanes-index import --at <C>` exits 2 naming
    `lanes/LANES.md`, that line's number and the key, and the head, the journal
    and every table of §1.2 equal their values before. With two such lines,
    the message names the first in path and line order. The same with U+00A0.
    The import runs as the operator lane (`LANES_LANE`, D24), with git's
    author named, through `LANES_REPO`, the lane's checkout; `W` is a
    directory of its own (`LANES_WORKSPACE_ROOT`, `lanes-edit.sh`'s test
    seam), since the import refuses a `LANES_REPO` that is `W` or a `W` it
    cannot read."""
    bad_lines, shown_key, line_no = IMPORT_CASES[case]
    work, commit = workspace_at(tmp_path, bad_lines)
    w = tmp_path / "W"
    w.mkdir()
    env = index_env(tmp_path, config(tmp_path, pg, mode="index"), LANES_REPO=str(work),
                    LANES_WORKSPACE_ROOT=str(w), LANES_LANE=LANE, LANES_WORKSTATION=WS,
                    **OPERATOR_GIT)
    before = state(pg)
    proc = run_index(LANES_INDEX, ["import", "--at", commit], env, cwd=work)
    assert proc.returncode == 2, shown(proc)
    assert "lanes/LANES.md" in proc.stderr and f"line {line_no}" in proc.stderr, shown(proc)
    assert shown_key in proc.stderr, shown(proc)
    if case == "two-lines":
        assert "row:p[U+0020]q" not in proc.stderr and "line 3" not in proc.stderr, shown(proc)
    assert state(pg) == before, "an import refused LR010 changed the register"


# =================================================================== the one number
FORCE_INCLUDE = "[tool.hatch.build.targets.wheel.force-include]"
PAYLOAD_ENTRY = re.compile(r'^"([^"]+)"\s*=\s*"openrepotools/payload/', re.M)
CONSTANT = re.compile(r"^[ \t]*(?:export[ \t]+|readonly[ \t]+|declare[ \t]+-[A-Za-z]+[ \t]+)?"
                      r"REGISTER_SCHEMA_VERSION[ \t]*(?::[ \t]*[A-Za-z_][\w\[\], ]*)?=[ \t]*"
                      r"[\"']?([0-9]+)", re.M)
SCHEMA_ROW = re.compile(r"INSERT INTO schema_version \([^)]*\)\s+VALUES \(([0-9]+),"
                        r"|UPDATE schema_version SET version = ([0-9]+)")
MIGRATION_ROW = re.compile(r"INSERT INTO migrations \([^)]*\)\s+VALUES \(([0-9]+),")


def release_files() -> list:
    """Every file a release ships: the wheel's payload, as `pyproject.toml`'s
    force-include table declares it, and the package's own modules."""
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert FORCE_INCLUDE in text, f"pyproject.toml has no {FORCE_INCLUDE}"
    table = text.split(FORCE_INCLUDE, 1)[1].split("\n[", 1)[0]
    found = []
    for rel in [*PAYLOAD_ENTRY.findall(table), "src/openrepotools"]:
        path = REPO / rel
        found += sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    return found


def test_every_copy_of_register_schema_version_in_a_release_is_one_number():
    """Design §1.5, "The row and the constant": every program that opens the
    register carries one constant, `REGISTER_SCHEMA_VERSION`, and every copy
    in a release is one number: each assignment in the shipped files, and the
    version the newest migration records in `schema_version` and in
    `migrations`. `lanes-index` carries it (CLI4.10 §2.8). Lane 1's T107
    relies on it. No engine: it reads files."""
    copies = {}
    # T124's module, which `lanes-index` runs its body from, ships beside it;
    # T347 adds it to the payload, which until then does not list it.
    module = LANES_INDEX.with_name(LANES_INDEX_MODULE)
    files = release_files()
    for path in files + ([module] if module not in files else []):
        text = path.read_text(encoding="utf-8", errors="replace")
        for value in CONSTANT.findall(text):
            copies.setdefault(int(value), []).append(str(path.relative_to(REPO)))
    index = module.read_text(encoding="utf-8")
    assert any(LANES_INDEX_MODULE in where for found in copies.values() for where in found), (
        f"lanes-index's module carries no `REGISTER_SCHEMA_VERSION = <n>` (CLI4.10 §2.8, "
        f"design §1.5); the release's copies are {copies or 'none'}")
    assert len(copies) == 1, f"the release's copies of REGISTER_SCHEMA_VERSION differ: {copies}"
    (number,) = copies
    recorded = [int(a or b) for a, b in SCHEMA_ROW.findall(index)]
    assert recorded and max(recorded) == number, (
        f"the migrations record schema_version {recorded}, whose newest is not {number}")
    rows = [int(v) for v in MIGRATION_ROW.findall(index)]
    assert rows and max(rows) == number and sorted(rows) == list(range(1, number + 1)), (
        f"the migrations rows record {rows}, not 1 to {number}")


# =================================================================== T111 alone
SNAPSHOT_KEYS = ("format", "generation", "write_id", "switch", "marker", "n", "clock",
                 "not_after", "schema", "c", "n_a")


@pytest.mark.parametrize("case", ["new-write", "switch-not-primary", "at-without-generation"])
def test_register_snapshot_prints_its_keys_in_the_contracts_order_and_refuses_with_its_codes(
        pg, tmp_path, case):
    """`lanes-index register snapshot`, from T203's flipped copy, with a
    `mode=primary` configuration whose `register_url=` names the session
    cluster's socket (R-F9-3, lane 1's T111):

      * `[new-write]`: on `primary` with the marker `present`, reached by
        AT-LR006's route on a plain clone, `--write-id new --lane --verb
        --args-sha256` exits 0, and stdout is one `key=value` per line,
        LF-ended, in CLI4.10's order (430-446), with no `found=`, `file=` or
        `repos_blob=`; `c=` is `register_url=`'s `connect_timeout=` and `n_a=`
        is `register_addresses=` (CLI4.10:296-297; L1v4.10:255);
      * `[switch-not-primary]`: on the bootstrap's `files` with the marker
        `absent`, check 4 ends the call with 69 (CLI4.10:427), and the case
        asserts the 69 only;
      * `[at-without-generation]`: `--at <k>` without `--generation` ends 64
        (CLI4.10:416; L1v4.10:258), where the act-begin form, no identity
        flag at all, is not refused on the same register."""
    copy = flipped(tmp_path)
    if case != "switch-not-primary":
        n = bring_to_primary(pg)
    env = index_env(tmp_path, config(tmp_path, pg))
    new_write = ["register", "snapshot", "--write-id", "new", "--lane", LANE, "--verb", "log",
                 "--args-sha256", ARGS_SHA256]
    if case == "switch-not-primary":
        proc = run_index(copy, new_write, env)
        assert proc.returncode == 69, shown(proc)
        return
    if case == "at-without-generation":
        control = run_index(copy, ["register", "snapshot"], env)
        assert control.returncode == 0 and control.stdout.startswith("format=1\n"), (
            f"the act-begin form, the control, is refused:\n{shown(control)}")
        proc = run_index(copy, ["register", "snapshot", "--at", str(n)], env)
        assert proc.returncode == 64, shown(proc)
        return
    early = int(float(sql(pg, "SELECT extract(epoch FROM clock_timestamp());")))
    proc = run_index(copy, new_write, env)
    late = int(float(sql(pg, "SELECT extract(epoch FROM clock_timestamp());"))) + 1
    assert proc.returncode == 0, shown(proc)
    assert proc.stdout.endswith("\n") and "\r" not in proc.stdout, repr(proc.stdout)
    lines = proc.stdout[:-1].split("\n")
    pairs = [line.split("=", 1) for line in lines]
    assert all(len(pair) == 2 for pair in pairs), lines
    keys = [key for key, _ in pairs]
    assert tuple(keys) == SNAPSHOT_KEYS, f"the keys are {keys}, not {list(SNAPSHOT_KEYS)}"
    got = dict(pairs)
    assert got["format"] == "1" and got["generation"] == generation(pg), got
    assert UUID_RE.match(got["write_id"]), got
    assert (got["switch"], got["marker"], got["n"]) == ("primary", "present", str(n)), got
    assert re.fullmatch(r"[0-9]+", got["clock"]) and early <= int(got["clock"]) <= late, (
        got, early, late)
    assert re.fullmatch(r"[0-9]+", got["not_after"]) and int(got["not_after"]) >= int(
        got["clock"]) + 2, got
    assert got["schema"] == str(window(pg)["version"]), got
    assert (got["c"], got["n_a"]) == (str(CONNECT_TIMEOUT), str(ADDRESSES)), got


# =================================================================== DEC-23's rendering
#: The scratch name the rendering cases bootstrap: any `register_schema=` but
#: the default (lane 2's reading of "a scratch schema", NOTES question 6).
SCRATCH = "t221_scratch"
ADMIN_SERVICE = "t221_admin"
BOOTSTRAP = ["bootstrap", "--admin-service", ADMIN_SERVICE, "--label", "t221",
             "--repository", "opensoft/t221", "--lane", LANE, "--no-passwords"]

#: `lanes_register` as one whole identifier token: the three roles, whose names
#: begin with it, are other tokens (DEC-23; lane 3, #165 6748109738).
SCHEMA_TOKEN = re.compile(r"(?<![A-Za-z0-9_$])lanes_register(?![A-Za-z0-9_$])")
DIGEST = re.compile(r"\b[0-9a-f]{64}\b")

#: Each refusal id's configurations: `register_schema=` that is not
#: `[a-z_][a-z0-9_]{0,62}` (upper case, a leading digit, a hyphen, 64
#: characters), one beginning `pg_`, and one equal to the index half's schema,
#: `lanes_index` or the configured `schema=` (lane 3, #165 6748109738).
SCHEMA_REFUSALS = {
    "identifier-rule": ["register_schema=T221_scratch\n", "register_schema=1t221\n",
                        "register_schema=t221-scratch\n", f"register_schema={'t' * 64}\n"],
    "pg-prefix": ["register_schema=pg_t221\n"],
    "index-schema": ["register_schema=lanes_index\n",
                     "schema=t221_index\nregister_schema=t221_index\n"],
}

#: Migration 1's own `CREATE SCHEMA` line (Y's §1.2 block), where
#: `[leftover-refused]`'s copy names the schema once more after it.
CREATE_SCHEMA_LINE = re.compile(r"^CREATE SCHEMA (?:IF NOT EXISTS )?lanes_register\b[^\n]*$", re.M)
LEFTOVER = "ALTER SCHEMA lanes_register OWNER TO lanes_register_owner;   -- t221: a leftover"


def bootstrap_conf(where: Path, text: str) -> Path:
    """A 0600 `lanes-index.conf` holding `text`, outside every work tree."""
    where.mkdir(parents=True, exist_ok=True)
    path = where / "lanes-index.conf"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    return path


def fake_admin(tmp_path: Path, conf: Path, tag: str) -> tuple:
    """The bootstrap's environment with the register's fake `psql` first on
    `PATH`, taught to fail every request as a database that cannot be reached
    does, and `conf` as the configuration: so a run that gets past every
    refusal reaches the admin connection and exits 69, and its log shows the
    request; a refused run sends nothing. No engine is needed."""
    base = tmp_path / tag
    base.mkdir()
    fake = base / "fake"
    fake.mkdir()
    (fake / "psql").write_text(REGISTER_FAKE_PSQL, encoding="utf-8")
    (fake / "psql").chmod(0o755)
    answers = base / "answers.json"
    answers.write_text(json.dumps([{"exit": 2, "stderr": (
        f'psql: error: connection to server on socket "{base}/.s.PGSQL.5432" failed: '
        f'No such file or directory\n')}]), encoding="utf-8")
    log = base / "psql.log"
    nowhere = SimpleNamespace(host=base / "no-cluster", port=5432, name="t221_none")
    env = admin_env(base, nowhere)
    env.update(PATH=f"{fake}{os.pathsep}{env.get('PATH', os.defpath)}",
               FAKE_PSQL_LOG=str(log), FAKE_PSQL_ANSWERS=str(answers),
               LANES_INDEX_CONFIG=str(conf))
    return env, log


def requests_of(log: Path) -> list:
    """The fake's entries that carried a request (never a `--version`)."""
    if not log.exists():
        return []
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    return [e for e in entries if e.get("kind") != "version"]


def reaches_the_admin_connection(copy: Path, tmp_path: Path, tag: str) -> None:
    """THE CONTROL: with `register_schema=` the scratch name, the same run gets
    past every refusal to the admin service, so a 2 in the case is the
    refusal it asserts and not a bootstrap this build lacks."""
    env, log = fake_admin(tmp_path, bootstrap_conf(tmp_path / tag, f"register_schema={SCRATCH}\n"),
                          f"{tag}-run")
    proc = run_index(copy, BOOTSTRAP, env)
    sent = requests_of(log)
    assert proc.returncode == 69 and sent, (
        f"the control, register_schema={SCRATCH} through a database that cannot be reached, "
        f"does not reach the admin connection and end 69 ({len(sent)} request(s) sent):\n"
        f"{shown(proc)}")
    assert all(e["service"] == ADMIN_SERVICE for e in sent), sent


def refused_and_sent_nothing(proc: subprocess.CompletedProcess, log: Path, what: str) -> None:
    sent = requests_of(log)
    assert proc.returncode == 2, f"{what}: not refused with 2:\n{shown(proc)}"
    assert not sent, f"{what}: refused, but {len(sent)} request(s) reached psql: {sent}"
    assert not re.search(r": created\b", proc.stdout), f"{what}: created something:\n{shown(proc)}"


def fresh_database(cluster, tag: str) -> Database:
    """An empty database of the session cluster, from `template0`, owned by
    the fixture's superuser, which the admin service connects as."""
    name = f"t221_{tag}_{uuid.uuid4().hex[:8]}"
    cluster.psql(f"CREATE DATABASE {name} TEMPLATE template0;")
    return Database(cluster, name)


def migration_digests(proc: subprocess.CompletedProcess) -> dict:
    """Each `migration <n>: created` line's two digests: `script_sha256`'s, and
    the rendered one the bootstrap prints beside it (lane 1, #165 6748099727)."""
    found = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"^migration ([0-9]+): created\b", line)
        if not m:
            continue
        script = re.search(r"script_sha256\W+([0-9a-f]{64})\b", line)
        digests = DIGEST.findall(line)
        assert script and len(digests) == 2, f"no two digests beside script_sha256: {line!r}"
        other = digests[1] if digests[0] == script.group(1) else digests[0]
        found[int(m.group(1))] = (script.group(1), other)
    assert found, f"the bootstrap created no migration:\n{shown(proc)}"
    return found


#: One schema's objects, its owners and its privileges, as one JSON object:
#: every relation with its columns, defaults, constraints and definition,
#: every function's whole definition (its `SET search_path` among it), the
#: triggers, the types, and the ACLs and default privileges.
DESCRIBE = """
SELECT jsonb_build_object(
  'owner', n.nspowner::regrole::text, 'acl', n.nspacl::text,
  'relations', (SELECT coalesce(jsonb_agg(jsonb_build_array(
      c.relname, c.relkind, c.relowner::regrole::text, c.relacl::text,
      (SELECT coalesce(jsonb_agg(jsonb_build_array(a.attname, format_type(a.atttypid, a.atttypmod),
              a.attnotnull, pg_get_expr(d.adbin, d.adrelid), a.attacl::text) ORDER BY a.attnum), '[]')
         FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped),
      (SELECT coalesce(jsonb_agg(jsonb_build_array(k.conname, pg_get_constraintdef(k.oid))
              ORDER BY k.conname), '[]') FROM pg_constraint k WHERE k.conrelid = c.oid),
      CASE WHEN c.relkind = 'i' THEN pg_get_indexdef(c.oid)
           WHEN c.relkind IN ('v', 'm') THEN pg_get_viewdef(c.oid) END) ORDER BY c.relname), '[]')
    FROM pg_class c WHERE c.relnamespace = n.oid),
  'functions', (SELECT coalesce(jsonb_agg(jsonb_build_array(
      p.proname, pg_get_function_identity_arguments(p.oid), p.proowner::regrole::text,
      p.proacl::text, CASE WHEN p.prokind IN ('f', 'p') THEN pg_get_functiondef(p.oid) END)
      ORDER BY p.proname, pg_get_function_identity_arguments(p.oid)), '[]')
    FROM pg_proc p WHERE p.pronamespace = n.oid),
  'triggers', (SELECT coalesce(jsonb_agg(pg_get_triggerdef(t.oid) ORDER BY t.tgname), '[]')
    FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
   WHERE c.relnamespace = n.oid AND NOT t.tgisinternal),
  'types', (SELECT coalesce(jsonb_agg(jsonb_build_array(y.typname, y.typtype, y.typacl::text)
      ORDER BY y.typname), '[]') FROM pg_type y WHERE y.typnamespace = n.oid),
  'defaults', (SELECT coalesce(jsonb_agg(jsonb_build_array(d.defaclrole::regrole::text,
      d.defaclobjtype, d.defaclacl::text) ORDER BY d.defaclrole::regrole::text, d.defaclobjtype),
      '[]') FROM pg_default_acl d WHERE d.defaclnamespace = n.oid))
FROM pg_namespace n WHERE n.nspname = '{schema}';
"""


def describe(db, schema: str) -> dict:
    out = sql(db, DESCRIBE.format(schema=schema))
    assert out, f"there is no schema {schema} in {db.name}"
    return json.loads(out)


@pytest.mark.parametrize("case", ["default-unchanged", "scratch-every-site", "leftover-refused",
                                  "identifier-rule", "pg-prefix", "index-schema"])
def test_the_bootstrap_renders_register_schema_both_ways_and_refuses_the_rest(
        request, tmp_path, case):
    """DEC-23 (lane 3, #165 6748109738; R-F10-1): `lanes-index bootstrap`
    through the admin service, as T109 builds it.

      * `[default-unchanged]`: with `register_schema=` unset, on an empty
        database, the rendered script is T107's migration byte for byte: the
        digest printed beside `script_sha256` equals it, and so does the
        `migrations` row's;
      * `[scratch-every-site]`: with a scratch name, that schema holds every
        relation, function, trigger and type a default bootstrap makes, with
        the same owners and privileges, each definition the default's with
        the whole token `lanes_register` replaced and nothing else changed;
        the three roles keep their names; and no `lanes_register` schema is
        made;
      * `[leftover-refused]`: a copy whose migration names `lanes_register`
        once more, at a site DEC-23 does not render, is refused with 2 and
        sends nothing (lane 2's reading, NOTES question 33);
      * `[identifier-rule]`, `[pg-prefix]` and `[index-schema]`: each
        configuration of `SCHEMA_REFUSALS` is refused with 2, sending nothing.

    The last four need no engine: the register's fake `psql` stands in for
    the database, and a control run shows the same bootstrap reaching it.
    The first two ask for the session cluster at run time, so without
    PostgreSQL 16 they skip with T205's banner."""
    if case in SCHEMA_REFUSALS:
        reaches_the_admin_connection(LANES_INDEX, tmp_path, "control")
        for n, text in enumerate(SCHEMA_REFUSALS[case], start=1):
            env, log = fake_admin(tmp_path, bootstrap_conf(tmp_path / f"conf-{n}", text), f"run-{n}")
            refused_and_sent_nothing(run_index(LANES_INDEX, BOOTSTRAP, env), log,
                                     f"{text.strip()!r}")
        return
    if case == "leftover-refused":
        reaches_the_admin_connection(LANES_INDEX, tmp_path, "control")
        found = RENDER_GIT_HALF_LINE.search(LANES_INDEX.read_bytes())
        assert found, f"{LANES_INDEX} holds no RENDER_GIT_HALF line for T203's flipped_copy"
        copy = flipped_copy(LANES_INDEX, tmp_path / "leftover", found.group(1) == b"True")
        module = copy.with_name(LANES_INDEX_MODULE)
        text = module.read_text(encoding="utf-8")
        sites = CREATE_SCHEMA_LINE.findall(text)
        assert len(sites) == 1, (f"{LANES_INDEX_MODULE} holds {len(sites)} `CREATE SCHEMA "
                                 f"lanes_register` lines")
        module.write_text(CREATE_SCHEMA_LINE.sub(lambda m: m.group(0) + "\n" + LEFTOVER, text),
                          encoding="utf-8")
        env, log = fake_admin(tmp_path, bootstrap_conf(tmp_path / "conf", f"register_schema={SCRATCH}\n"),
                              "run")
        refused_and_sent_nothing(run_index(copy, BOOTSTRAP, env), log, "the leftover's copy")
        return
    cluster = request.getfixturevalue("pg_cluster")
    made = []
    try:
        default = fresh_database(cluster, "default")
        made.append(default.name)
        (tmp_path / "default").mkdir()
        proc = run_index(LANES_INDEX, BOOTSTRAP, admin_env(tmp_path / "default", default))
        assert proc.returncode == 0, shown(proc)
        template, rendered_digest = migration_digests(proc)[1]
        if case == "default-unchanged":
            assert rendered_digest == template, (
                f"on {SCHEMA} the rendered script's digest {rendered_digest} is not "
                f"script_sha256 {template}:\n{shown(proc)}")
            assert sql(default, f"SELECT script_sha256 FROM {SCHEMA}.migrations "
                                f"WHERE version = 1;") == template
            return
        scratch = fresh_database(cluster, "scratch")
        made.append(scratch.name)
        (tmp_path / "scratch").mkdir()
        env = admin_env(tmp_path / "scratch", scratch)
        env["LANES_INDEX_CONFIG"] = str(bootstrap_conf(tmp_path / "scratch" / "conf",
                                                       f"register_schema={SCRATCH}\n"))
        proc = run_index(LANES_INDEX, BOOTSTRAP, env)
        assert proc.returncode == 0, shown(proc)
        script, rendered_scratch = migration_digests(proc)[1]
        assert script == template and rendered_scratch != template, (
            f"for {SCRATCH} the bootstrap prints {script} and {rendered_scratch}, not the "
            f"template's {template} beside a rendered digest of its own:\n{shown(proc)}")
        assert sql(scratch, f"SELECT to_regnamespace('{SCHEMA}') IS NULL;") == "t", (
            f"a bootstrap for {SCRATCH} made a {SCHEMA} schema")
        assert sql(scratch, f"SELECT count(*) FROM pg_roles WHERE rolname IN "
                            f"('{OWNER}', '{WRITER}', '{READER}');") == "3"
        assert sql(scratch, f"SELECT count(*) FROM pg_roles WHERE rolname LIKE "
                            f"'{SCRATCH.replace('_', chr(92) + '_')}%';") == "0"
        want = json.loads(SCHEMA_TOKEN.sub(SCRATCH, json.dumps(describe(default, SCHEMA))))
        got = describe(scratch, SCRATCH)
        assert want["relations"] and want["functions"] and want["acl"], want
        for part in want:
            assert got[part] == want[part], (
                f"{SCRATCH}'s {part} differ from {SCHEMA}'s with the token replaced:\n"
                f"want {json.dumps(want[part], indent=1)[:3000]}\n"
                f"got  {json.dumps(got[part], indent=1)[:3000]}")
    finally:
        for name in made:
            cluster.drop_database(name)


# =================================================================== T107's step 6
#: The small mirrors of T107's step-6 cases (lane 3, #165 6755386771, ruling (c)
#: and "Lane 2's cases"; PLACEMENT.md section 1). Every row is literal, in Y
#: section 1.3's entry form, as T223's direct calls are: no case calls T112's
#: or T115's derivation code.
STEP6_UTC = "2026-11-09T10:00:00Z"
STEP6_ROW_A, STEP6_ROW_B, STEP6_ROW_R = "| `Lane-A` | x |", "| `Lane-B` | y |", "| `Lane-R` | x |"
STEP6_LOG_A, STEP6_LOG_B, STEP6_LOG_R = ("lanes/log/Lane-A.md", "lanes/log/Lane-B.md",
                                         "lanes/log/Lane-R.md")
STEP6_WORD_MS = "2026-11-09T10:00:00.123Z"           # a WORD line with milliseconds (lane 3)
STEP6_STRAY_SHA = "5" * 40


def step6_log(verb: str, obj, utc: str = STEP6_UTC) -> tuple:
    """One log line: its text, and its parsed fields (Y's derivation, by hand)."""
    text = f"{verb} {EM_DASH} {obj if obj else 'note'} {EM_DASH} {utc}"
    return text, {"verb": verb, "object": obj, "utc": utc, "utc_ts": utc}


def step6_rows(files: dict, holds_spelled=("CLAIMED", "TAKEOVER")) -> dict:
    """The structured rows of `files` by lane 2's literal derivation of these
    small mirrors (Y:1193-1273, reading 7's corrections): a `lanes` row per
    row line; a `log_lines` row per log line, its lane the file's, NULL
    workstation; each lane's last line per object a hold, `spellings` on
    CLAIMED and TAKEOVER only; no `register_lines`, since no line has a kind;
    no `lane:` objects; NULL `owner`."""
    lanes, logs, holds = [], [], {}
    for path, lines in sorted(files.items()):
        for n, text in enumerate(lines, start=1):
            m = re.fullmatch(r"\| `([^`]+)` \| [a-z] \|", text)
            if path == "lanes/LANES.md" and m:
                lanes.append({"path": path, "line_no": n, "raw": text, "lane_key": m.group(1).lower(),
                              "lane": m.group(1), "archived": False, "owner": None})
            elif path.startswith("lanes/log/"):
                lane = path[len("lanes/log/"):-len(".md")]
                fields = STEP6_FIELDS[text]
                logs.append({"path": path, "line_no": n, "raw": text, "lane": lane,
                             "workstation": None, "unreadable": False, **fields})
                if fields["object"]:
                    holds[(fields["object"], lane.lower())] = {
                        "object": fields["object"], "lane_key": lane.lower(), "lane": lane,
                        "verb": fields["verb"], "utc_ts": fields["utc_ts"], "file": path,
                        "ordinal": n,
                        "spellings": [fields["object"]] if fields["verb"] in holds_spelled else None}
    return {"lanes": lanes, "log_lines": logs, "object_holds": list(holds.values())}


STEP6_CLAIM_O1, _f1 = step6_log("CLAIMED", "o1")
STEP6_CLAIM_O2, _f2 = step6_log("CLAIMED", "o2")
STEP6_OPEN_O3, _f3 = step6_log("OPENED", "o3")
STEP6_TAKE_O1, _f4 = step6_log("TAKEOVER", "o1", "2026-11-09T11:00:00Z")   # Lane-B's, on Lane-A's o1
STEP6_WORD, _fw = step6_log("WORD", None, STEP6_WORD_MS)
STEP6_RENAMED, _fr = step6_log("RENAMED", None, "2026-11-10T12:00:00Z")
STEP6_STRAY, _fs = step6_log("NOTED", None)
STEP6_FIELDS = {STEP6_CLAIM_O1: _f1, STEP6_CLAIM_O2: _f2, STEP6_OPEN_O3: _f3, STEP6_TAKE_O1: _f4,
                STEP6_WORD: _fw, STEP6_RENAMED: _fr, STEP6_STRAY: _fs}

#: Each case: the mirror before, and the mirror after the write.
STEP6_CASES = {
    "rename-live-claim": (
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_A], STEP6_LOG_A: [STEP6_CLAIM_O1]},
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_R], STEP6_LOG_R: [STEP6_CLAIM_O1, STEP6_RENAMED]}),
    "rename-millisecond-word-log": (
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_A], STEP6_LOG_A: [STEP6_WORD]},
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_R], STEP6_LOG_R: [STEP6_WORD, STEP6_RENAMED]}),
    "stray-deletes-a-row": (
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_A, STEP6_ROW_B]},
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_B]}),
    "stray-inserts-before-the-end": (
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_A],
         STEP6_LOG_A: [STEP6_CLAIM_O1, STEP6_CLAIM_O2, STEP6_OPEN_O3]},
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_A],
         STEP6_LOG_A: [STEP6_CLAIM_O1, STEP6_STRAY, STEP6_CLAIM_O2, STEP6_OPEN_O3]}),
    # Case 6a (R-F13-2; lane 3, #165 6771318480, option (i)): Lane-B's TAKEOVER on o1 is
    # the line that supersedes Lane-A's CLAIMED, and the write takes that line away (a
    # replace by a stray; a remove of its log by a write) and sends NO hold on o1.
    "6a-replace": (
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_A, STEP6_ROW_B],
         STEP6_LOG_A: [STEP6_CLAIM_O1], STEP6_LOG_B: [STEP6_TAKE_O1]},
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_A, STEP6_ROW_B],
         STEP6_LOG_A: [STEP6_CLAIM_O1], STEP6_LOG_B: [STEP6_STRAY]}),
    "6a-remove": (
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_A, STEP6_ROW_B],
         STEP6_LOG_A: [STEP6_CLAIM_O1], STEP6_LOG_B: [STEP6_TAKE_O1]},
        {"lanes/LANES.md": ["# Lanes", STEP6_ROW_A, STEP6_ROW_B],
         STEP6_LOG_A: [STEP6_CLAIM_O1]}),
}


def step6_entry(case: str, before: dict, after: dict) -> dict:
    """The write each case commits. The renames as T112 now builds them (B10
    tasks:428): the row line's `replace`, the log's `rename`, and `log_lines`
    rows only for the lines written, with the holds from every line of the
    renamed log. The strays as `import --single` sends them: a `delete`; and,
    with no insert op, a `replace` of every later line and an `append`
    (6755386771, "No insert op now"). Case 6a's two (lane 3, #165 6771318480):
    a stray's `replace` of Lane-B's TAKEOVER line by a line on no object, with
    the replaced line's own `log_lines` row, and a write's `remove` of Lane-B's
    log; each sends no `object_holds` row, since no line of Lane-B names o1
    after it (T112's `register_commit_entry` sends none for a pair left with
    no line)."""
    rows = step6_rows(after)
    if case == "6a-replace":
        return entry("stray-import", "import --single", journal={"git_commit": STEP6_STRAY_SHA},
                     edits=[{"ord": 1, "op": "replace", "path": STEP6_LOG_B, "line_no": 1,
                             "old_sha256": line_sha(before[STEP6_LOG_B][0]),
                             "new_text": after[STEP6_LOG_B][0]}],
                     files=[{"path": STEP6_LOG_B, "present": True,
                             "sha256": rendered(after[STEP6_LOG_B]), "final_newline": True}],
                     log_lines=[r for r in rows["log_lines"] if r["path"] == STEP6_LOG_B])
    if case == "6a-remove":
        return entry("write", "remove-log", journal={"args_sha256": ARGS_SHA256},
                     edits=[{"ord": 1, "op": "remove", "path": STEP6_LOG_B}],
                     files=[{"path": STEP6_LOG_B, "present": False}])
    if case.startswith("rename-"):
        renamed = {**rows["log_lines"][-1], "workstation": WS}      # primary: Rule 10's CHECK
        lanes = [r for r in rows["lanes"] if r["lane"] == "Lane-R"]
        return entry("write", "rename-lane", journal={"args_sha256": ARGS_SHA256},
                     edits=[{"ord": 1, "op": "replace", "path": "lanes/LANES.md", "line_no": 2,
                             "old_sha256": line_sha(STEP6_ROW_A), "new_text": STEP6_ROW_R},
                            {"ord": 2, "op": "rename", "path": STEP6_LOG_A, "to_path": STEP6_LOG_R},
                            {"ord": 3, "op": "append", "path": STEP6_LOG_R,
                             "new_text": STEP6_RENAMED}],
                     files=[{"path": "lanes/LANES.md", "present": True,
                             "sha256": rendered(after["lanes/LANES.md"]), "final_newline": True},
                            {"path": STEP6_LOG_R, "present": True,
                             "sha256": rendered(after[STEP6_LOG_R]), "final_newline": True},
                            {"path": STEP6_LOG_A, "present": False}],
                     lanes=lanes, log_lines=[renamed],
                     object_holds=[h for h in rows["object_holds"] if h["file"] == STEP6_LOG_R])
    stray = {"journal": {"git_commit": STEP6_STRAY_SHA}}
    if case == "stray-deletes-a-row":
        return entry("stray-import", "import --single", **stray,
                     edits=[{"ord": 1, "op": "delete", "path": "lanes/LANES.md", "line_no": 2,
                             "old_sha256": line_sha(STEP6_ROW_A)}],
                     files=[{"path": "lanes/LANES.md", "present": True,
                             "sha256": rendered(after["lanes/LANES.md"]), "final_newline": True}])
    old, new = before[STEP6_LOG_A], after[STEP6_LOG_A]
    edits = [{"ord": n - 1, "op": "replace", "path": STEP6_LOG_A, "line_no": n,
              "old_sha256": line_sha(old[n - 1]), "new_text": new[n - 1]}
             for n in range(2, len(old) + 1)]
    edits.append({"ord": len(edits) + 1, "op": "append", "path": STEP6_LOG_A, "new_text": new[-1]})
    return entry("stray-import", "import --single", **stray, edits=edits,
                 files=[{"path": STEP6_LOG_A, "present": True, "sha256": rendered(new),
                         "final_newline": True}],
                 log_lines=[r for r in rows["log_lines"] if r["path"] == STEP6_LOG_A
                            and r["line_no"] >= 2],
                 object_holds=[h for h in rows["object_holds"] if h["file"] == STEP6_LOG_A
                               and h["ordinal"] >= 2])


#: The four structured tables, each row keyed by its line's `(path, line_no)`
#: in place of a line id, without the columns a write stamps: the written seq,
#: the mode and the workstation (lane 2's reading, NOTES question 33).
STRUCTURED = {
    "lanes": f"SELECT to_jsonb(t) - 'row_line_id' - 'last_seq' - 'last_mode' - 'workstation' || "
             f"jsonb_build_object('path', d.path, 'line_no', d.line_no) FROM {SCHEMA}.lanes t "
             f"LEFT JOIN {SCHEMA}.doc_lines d ON d.line_id = t.row_line_id",
    "log_lines": f"SELECT to_jsonb(t) - 'line_id' - 'seq' - 'mode' - 'workstation' || "
                 f"jsonb_build_object('path', d.path, 'line_no', d.line_no) FROM "
                 f"{SCHEMA}.log_lines t LEFT JOIN {SCHEMA}.doc_lines d ON d.line_id = t.line_id",
    "register_lines": f"SELECT to_jsonb(t) - 'line_id' - 'seq' - 'mode' - 'workstation' || "
                      f"jsonb_build_object('path', d.path, 'line_no', d.line_no) FROM "
                      f"{SCHEMA}.register_lines t LEFT JOIN {SCHEMA}.doc_lines d "
                      f"ON d.line_id = t.line_id",
    "object_holds": f"SELECT to_jsonb(t) - 'seq' - 'mode' FROM {SCHEMA}.object_holds t",
}


def structured(db) -> dict:
    out = {}
    for table, query in STRUCTURED.items():
        rows = json.loads(sql(db, f"SELECT coalesce(jsonb_agg(r ORDER BY r::text), '[]') "
                                  f"FROM ({query}) AS q(r);"))
        out[table] = rows
    return out


def step6_holds_of(db, obj: str) -> dict:
    """Every stored `object_holds` row on `obj`, whole, by lane key."""
    rows = json.loads(sql(db, f"SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]') FROM "
                              f"{SCHEMA}.object_holds t WHERE object = {sql_text(obj)};"))
    return {row["lane_key"]: row for row in rows}


@pytest.mark.parametrize("case", list(STEP6_CASES))
def test_commit_write_derives_step_6s_deletes_so_the_tables_equal_the_imports_derivation(
        pg, case):
    """T107's step 6 under lane 3's ruling (c) (#165 6755386771): as a
    `replace` or `delete` changes a line, `commit_write` deletes that line's
    structured rows, and a `rename` deletes the old path's holds and moves
    `log_lines` to the new file's lane; the entry carries no deletes.

    Each case clones `tmpl`, brings it to `primary` with the marker `present`
    by AT-LR006's route, with its mirror as the import; a stray first records
    its sha by `record_mirror_state`. Then `commit_write` returns its seq, with
    no 23505, 23503, 23514 (Y:1217-1219) or LR005, and `lanes`, `log_lines`,
    `register_lines` and `object_holds` equal, row for row, what one `import`
    entry of the mirror after the write leaves in a second clone of `tmpl`.
    `[rename-live-claim]` also asserts the claim's hold is the new lane's, and
    `[stray-inserts-before-the-end]` that each hold below the inserted line
    points at its own line.

    CASE 6A (R-F13-2; lane 3, #165 6771318480, option (i); T107's `PENDING-L2`
    marker), `[6a-replace]` and `[6a-remove]`: Lane-B's TAKEOVER on `o1` is the
    line that supersedes Lane-A's CLAIMED on it, and the entry replaces that
    line (a stray's `replace`) or removes its log (a write's `remove`) and
    sends no hold on `o1`. Beside the tables equal to the import's derivation,
    each asserts that step 7 re-marks `superseded_by` on every stored row of
    `o1` as for an object the entry sends, so Lane-A's CLAIMED is live again, and
    stamps no `seq` or `mode` on it; and that the entry's `journal_scopes`
    hold `objects:lane-a` and `objects:lane-b`, every lane holding the object,
    so that the flip is reported (step 5a). They fail until lane 1's commit of
    6a on T107 (`lanes-index` line S), where `commit_write` as T112-fu2 reads
    it re-marks only the objects the entry sends."""
    before, after = STEP6_CASES[case]
    n = bring_to_primary(pg, before, **step6_rows(before))
    body = step6_entry(case, before, after)
    if body["journal"]["kind"] == "stray-import":       # a stray's, which clears a divergence
        assert record_mirror_state(pg, "ws-stray", STEP6_STRAY_SHA, None).returncode == 0
    if case.startswith("6a-"):                          # the control: the claim is superseded
        was = step6_holds_of(pg, "o1")
        assert {k: v["superseded_by"] for k, v in was.items()} == {"lane-a": "lane-b",
                                                                   "lane-b": None}, was
    proc = commit_call(pg, n, body)
    code, message = error_of(proc)
    assert proc.returncode == 0, (
        f"commit_write refused the {case} write with {code} (23505, 23503, 23514 and LR005 "
        f"are the gap's effects, 6755386771): {message}\n{proc.stderr.strip()}")
    assert int(proc.stdout.strip().splitlines()[-1]) == n + 1
    got = structured(pg)
    oracle = Database(pg.cluster, pg.cluster.new_database())
    try:
        committed(oracle, head(oracle), import_entry(after, **step6_rows(after)),
                  "the oracle's import of the mirror after the write")
        want = structured(oracle)
    finally:
        pg.cluster.drop_database(oracle.name)
    for table in STRUCTURED:
        assert got[table] == want[table], (
            f"{case}: {table} is not the import's derivation of the mirror after the write:\n"
            f"got  {json.dumps(got[table], indent=1)[:3000]}\n"
            f"want {json.dumps(want[table], indent=1)[:3000]}")
    holds = {(h["object"], h["lane_key"]): h for h in got["object_holds"]}
    if case == "rename-live-claim":
        assert ("o1", "lane-a") not in holds, holds
        assert (holds[("o1", "lane-r")]["file"], holds[("o1", "lane-r")]["ordinal"]) == (
            STEP6_LOG_R, 1), holds
    if case == "stray-inserts-before-the-end":
        lines = {(r["path"], r["line_no"]): r for r in got["log_lines"]}
        for h in got["object_holds"]:
            line = lines[(h["file"], h["ordinal"])]
            assert (line["object"], line["verb"]) == (h["object"], h["verb"]), (h, line)
        assert sorted(h["ordinal"] for h in got["object_holds"]) == [1, 3, 4], holds
    if case.startswith("6a-"):
        now = step6_holds_of(pg, "o1")
        assert set(now) == {"lane-a"}, (
            f"{case}: step 6 should have deleted Lane-B's hold on o1 with its line, and left "
            f"Lane-A's: {now}")
        assert now["lane-a"]["superseded_by"] is None, (
            f"{case}: Lane-A's CLAIMED on o1 is still superseded by "
            f"{now['lane-a']['superseded_by']!r}, though Lane-B's TAKEOVER is gone: step 7 did "
            f"not re-mark the object, since the entry sends no hold on it (case 6a)")
        assert (now["lane-a"]["seq"], now["lane-a"]["mode"]) == (
            was["lane-a"]["seq"], was["lane-a"]["mode"]), (
            f"{case}: the re-mark stamped Lane-A's row: it was {(was['lane-a']['seq'], was['lane-a']['mode'])}, "
            f"it is {(now['lane-a']['seq'], now['lane-a']['mode'])}; it takes no seq or mode")
        keys = set(json.loads(sql(pg, f"SELECT coalesce(jsonb_agg(scope), '[]') FROM "
                                      f"{SCHEMA}.journal_scopes WHERE seq = {n + 1};")))
        assert {"objects:lane-a", "objects:lane-b"} <= keys, (
            f"{case}: the entry's journal_scopes are {sorted(keys)}; step 5a should add objects: "
            f"for every lane holding o1, objects:lane-a and objects:lane-b, so the flip is reported")


# =================================================================== T231: AT-SET, AT-SPL, AT-LR4
#: T231 (R1's M3; FR-059): AT-SET, AT-SPL and AT-LR4 in phase N, each case on
#: lane 1's code alone. Its readings are in each function's docstring; the
#: three the whole task rests on:
#:
#:   * T107'S CASES (`set_seq_is_minus`, `the_marker_moves`, `a_write_is_refused`,
#:     `the_rollbacks_entry_sets`, `no_kind_commits_in`, `switch_to_files_aborts`,
#:     `an_operator_entry`, `the_switch_checks`) drive `commit_write`,
#:     `record_marker` and `switch_to_files` as REGISTER-WRITER, by AT-LR006's
#:     route, so they pass on T107 alone. The rollback's entry is the operator
#:     entry that removes `lanes/STORE`, sent by a direct call, since no task
#:     before T304 sends one.
#:   * THE CUTOVER'S CASES (`set_seq_after_a_cutover`, `the_reimport_forms`,
#:     `restore_prior_is`) run `lanes-index cutover` itself against a scratch
#:     schema (`register_schema=`, DEC-23), which it alone accepts while
#:     `RENDER_GIT_HALF` is False; the import before it is the entry
#:     `import --at` sends, by a direct call, as `root_seq` gives an after-loss
#:     import its `m`. Each runs the cutover's whole row (lane 3's (c), #165
#:     6828023371, which moves the three from T116's verify to T327's, since
#:     T327 waits for T116): T116's transaction, then T327's push of the
#:     marker, its read-back and `record_marker`, so its 0 leaves the marker
#:     `present`. The run is the operator lane's, from its own checkout by
#:     T221i's route, onto a real commit C (`OperatorEstate`); an abort is the
#:     cutover's own step 3, with origin refusing the marker's push.
#:   * T112'S CASES write through `lanes-index register snapshot --tree` and
#:     `register commit` from T203's flipped copy, with the shim's `edit-entry`
#:     mode on the commit call, so each fails until T111 is on line R as well
#:     as T112 (line R at merge10 has no `register snapshot`). Where the shim
#:     cannot make the rewrite (it neither adds a key nor sends an operator
#:     entry), the case is a direct call, and says so.

#: The scratch name T116's cases bootstrap (any `register_schema=` but the default).
T231_SCHEMA = "t231_scratch"
#: An after-loss import's root `m` (any seq past the first import's 0).
REIMPORT_M = 7
#: The author the operator's git names (D15), through git's own variables.
OPERATOR_GIT = {"GIT_AUTHOR_NAME": "T231 operator", "GIT_AUTHOR_EMAIL": "t231@example.invalid",
                "GIT_COMMITTER_NAME": "T231 operator",
                "GIT_COMMITTER_EMAIL": "t231@example.invalid",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def switch_of(db, schema: str = SCHEMA) -> dict:
    """The switch row, whole."""
    return json.loads(sql(db, f"SELECT to_jsonb(s) FROM {schema}.register_switch s;"))


def pair_of(db, schema: str = SCHEMA) -> tuple:
    switch = switch_of(db, schema)
    return switch["mode"], switch["marker_state"]


def journal_of(db, schema: str = SCHEMA) -> list:
    """Each journal entry's seq, kind and generated `operator` flag, by seq."""
    return json.loads(sql(db, f"SELECT coalesce(jsonb_agg(jsonb_build_array(j.seq, j.kind, "
                              f"j.operator) ORDER BY j.seq), '[]') FROM {schema}.journal j;"))


def marker_call(db, seq: int, schema: str = SCHEMA) -> subprocess.CompletedProcess:
    """`record_marker(client, seq, commit, ws)` as REGISTER-WRITER, as each
    read-back would call it (S4)."""
    return psql(db, f"SELECT {schema}.record_marker({window(db, schema)['version']}, {seq}, "
                    f"'{MARKER_COMMIT}', '{WS}');", WRITER)


def abort_call(db, seq: int, schema: str = SCHEMA) -> subprocess.CompletedProcess:
    """`switch_to_files(client, cutover_seq, lane, ws)` as REGISTER-WRITER (F2)."""
    return psql(db, f"SELECT {schema}.switch_to_files({window(db, schema)['version']}, {seq}, "
                    f"'{LANE}', '{WS}');", WRITER)


def rollback_entry(**parts) -> dict:
    """The rollback's first transaction's entry (Q4(b)(iii)): the operator entry
    that removes `lanes/STORE` (D24), its one files row absent."""
    parts.setdefault("edits", [{"ord": 1, "op": "remove", "path": "lanes/STORE"}])
    parts.setdefault("files", [{"path": "lanes/STORE", "present": False}])
    return entry("rollback", "rollback", **parts)


def appended(lines: list, text: str) -> dict:
    """A write that appends `text` to `lanes/LANES.md`, whose lines are `lines`."""
    return entry("write", "log", journal={"args_sha256": ARGS_SHA256},
                 edits=[{"ord": 1, "op": "append", "path": "lanes/LANES.md", "new_text": text}],
                 files=[{"path": "lanes/LANES.md", "present": True,
                         "sha256": rendered([*lines, text]), "final_newline": True}])


def three_writes(db, n: int) -> int:
    """AT-SET's three writes after the cutover's `n`; returns the head `k`."""
    lines = list(DEFAULT_FILES["lanes/LANES.md"])
    for i in (1, 2, 3):
        text = f"t231: write {i}"
        n = committed(db, n, appended(lines, text), f"write {i}")
        lines.append(text)
    return n


def store_of(db, schema: str = SCHEMA) -> dict:
    """`lanes/STORE`'s `files` row and its `doc_lines`, line ids included, read
    in one snapshot with the switch row: what `restore_prior` holds."""
    return json.loads(sql(db, (
        f"SELECT jsonb_build_object('switch', (SELECT to_jsonb(s) FROM {schema}.register_switch s), "
        f"'file', (SELECT to_jsonb(f) FROM {schema}.files f WHERE f.path = 'lanes/STORE'), "
        f"'lines', (SELECT jsonb_agg(to_jsonb(d) ORDER BY d.line_no) FROM {schema}.doc_lines d "
        f"WHERE d.path = 'lanes/STORE'));")))


def wait_sql(db, count_query: str, what: str, ceiling: float = 5.0) -> None:
    """Poll `count_query` in 0.05 s steps under `ceiling` until it counts one
    row or more. No sleep stands in for a barrier."""
    end = time.monotonic() + ceiling
    while time.monotonic() < end:
        if sql(db, count_query) != "0":
            return
        time.sleep(0.05)
    pytest.fail(f"{what}: not seen within {ceiling} s")


# ------------------------------------------------------------------ T116's scratch schema
def scratch_register(cluster, where: Path) -> Database:
    """An empty database of the session cluster, bootstrapped by `lanes-index
    bootstrap` with `register_schema=` T231's scratch name (DEC-23), the switch
    labelled `t221` by `BOOTSTRAP`. The caller drops it."""
    db = fresh_database(cluster, "t231")
    try:
        where.mkdir(parents=True)
        env = admin_env(where, db)
        env["LANES_INDEX_CONFIG"] = str(bootstrap_conf(where / "boot",
                                                       f"register_schema={T231_SCHEMA}\n"))
        proc = run_index(LANES_INDEX, BOOTSTRAP, env)
        assert proc.returncode == 0, f"the scratch schema's bootstrap:\n{shown(proc)}"
        ensure_logins(db)
    except BaseException:
        cluster.drop_database(db.name)
        raise
    return db


#: T221k: ORIGIN'S REFUSAL OF A PUSH (lane 3's (c), #165 6828023371: the abort
#: "seen through the cutover's own step 3, with origin refusing the push"), as
#: a `pre-receive` hook in the estate's bare origin. Until the case arms it
#: (`ARMED_PATH`) it lets every push through. Armed, it refuses each push with
#: 1, so `git push --porcelain` reads `[remote rejected]`, T320's `failed`,
#: and T327's read-back after it proves the marker absent: the abort. Where
#: the case also holds it (`HOLD_PATH`), it marks `REACHED_PATH` and waits for
#: `RELEASE_PATH` before it refuses, under 40 s, below `LANES_GIT_TIMEOUT`'s
#: 60 s, so the case reads the switch while the cutover's entry stands. Each
#: ref update is one line of `LOG_PATH`: the verdict, the old and the new sha,
#: and the ref.
REFUSE_HOOK = r"""#!/bin/sh
if [ -e ARMED_PATH ]; then verdict=refused; else verdict=accepted; fi
while read -r old new ref; do
  printf '%s %s %s %s\n' "$verdict" "$old" "$new" "$ref" >> LOG_PATH
done
[ "$verdict" = refused ] || exit 0
if [ -e HOLD_PATH ]; then
  : > REACHED_PATH
  n=0
  while [ ! -e RELEASE_PATH ] && [ "$n" -lt 800 ]; do sleep 0.05; n=$((n + 1)); done
fi
echo "origin refuses this push (T221k's model of a server-side refusal)" >&2
exit 1
"""


class OperatorEstate:
    """T221k: THE OPERATOR LANE'S OWN CHECKOUT for the cutover's cases, by
    T221i's route (lane 3's (c), #165 6828023371): `work`, a clone whose
    origin is the bare `origin.git`, which `LANES_REPO` names, and `w`, a
    directory of its own, which `LANES_WORKSPACE_ROOT` names, since the
    cutover finds its checkout as the import does and refuses a `LANES_REPO`
    that is `W`, or one set where `W` cannot be read (T327's
    `cutover_git_preflight`, through `lane_own_checkout`). Origin's URLs are
    absolute paths, as its local-origin check needs while `RENDER_GIT_HALF`
    is False.

    Origin's `main` is a real commit C, `commit`, whose `lanes/LANES.md` is
    `DEFAULT_FILES`' as the register renders it, beside the checkout's own
    files, which are no render-set path: so the marker's commit builds on C,
    and in the restore form the render set at origin's tip is the images at
    `b`. `tree` is C's `lanes` tree, which the import's entry names and step 2
    compares origin's tip with. Origin's `pre-receive` hook is
    `REFUSE_HOOK`."""

    def __init__(self, root: Path):
        root.mkdir(parents=True)
        files = {path: file_bytes(lines).decode("utf-8") for path, lines in DEFAULT_FILES.items()}
        self.work = estate_checkout(root, {**files, **CHECKOUT_FILES})
        self.origin, self.w = root / "origin.git", root / "W"
        self.w.mkdir()
        self.commit = git("rev-parse", "HEAD", cwd=self.work).stdout.strip()
        self.tree = git("rev-parse", "HEAD:lanes", cwd=self.work).stdout.strip()
        self.armed, self.hold = root / "refuse-armed", root / "refuse-hold"
        self.reached, self.release = root / "refuse-reached", root / "refuse-release"
        self.log = root / "pushes.log"
        text = REFUSE_HOOK
        for name, path in (("ARMED_PATH", self.armed), ("HOLD_PATH", self.hold),
                           ("REACHED_PATH", self.reached), ("RELEASE_PATH", self.release),
                           ("LOG_PATH", self.log)):
            text = text.replace(name, shlex.quote(str(path)))
        hook = self.origin / "hooks" / "pre-receive"
        hook.parent.mkdir(exist_ok=True)                # no templates, no hooks/
        hook.write_text(text, encoding="utf-8")
        hook.chmod(0o755)

    def refuse(self, hold: bool = False) -> None:
        """Arm origin's refusal of every push from now on; held, where `hold`."""
        if hold:
            self.hold.write_text("", encoding="utf-8")
        self.armed.write_text("", encoding="utf-8")

    def wait_reached(self, proc: subprocess.Popen, ceiling: float = 30.0) -> bool:
        """Poll in 0.05 s steps, under `ceiling`, until a held push reaches the
        hook: True; False where `proc` ends first or the ceiling passes."""
        end = time.monotonic() + ceiling
        while time.monotonic() < end:
            if self.reached.exists():
                return True
            if proc.poll() is not None:
                return False
            time.sleep(0.05)
        return False

    def tip(self) -> str:
        """Origin's `main`, read in the bare repository itself."""
        return git("rev-parse", "refs/heads/main", cwd=self.origin).stdout.strip()

    def parent(self, commit: str) -> str:
        return git("rev-parse", f"{commit}^", cwd=self.origin).stdout.strip()

    def seq_of(self, commit: str) -> str:
        """Form C on one commit: its `Register-Seq` trailer's value."""
        return git("log", "-n", "1", "--format=%(trailers:key=Register-Seq,valueonly)", commit,
                   "--", cwd=self.origin).stdout.strip()

    def pushes(self) -> list:
        """Each ref update the hook saw, `[verdict, old, new, ref]`, in order."""
        if not self.log.exists():
            return []
        return [line.split(" ") for line in self.log.read_text(encoding="utf-8").splitlines()]


def cutover_env(where: Path, db, label: str, estate: OperatorEstate) -> dict:
    """`lanes-index cutover`'s environment as the operator lane (F12):
    `LANES_LANE`, this workstation, git's author, and a configuration naming
    the scratch schema and `register_label=` `label` (N4), its URLs the
    cluster's socket (the fake-`psql` host rule, L1v4.5:525); and the lane's
    own checkout by T221i's route (T221k): `LANES_REPO` names `estate`'s
    clone and `LANES_WORKSPACE_ROOT` its `W`."""
    where.mkdir(parents=True, exist_ok=True)
    conf = where / "lanes-index.conf"
    query = f"?connect_timeout={CONNECT_TIMEOUT}"
    conf.write_text(f"mode=index\nregister_url={db.url(LOGIN_WRITER)}{query}\n"
                    f"reader_url={db.url(LOGIN_READER)}{query}\n"
                    f"register_schema={T231_SCHEMA}\nregister_label={label}\n", encoding="utf-8")
    conf.chmod(0o600)
    return index_env(where, conf, LANES_LANE=LANE, LANES_WORKSTATION=WS,
                     LANES_REPO=str(estate.work), LANES_WORKSPACE_ROOT=str(estate.w),
                     **OPERATOR_GIT)


def cutover_run(where: Path, db, label: str, estate: OperatorEstate,
                *args: str) -> subprocess.CompletedProcess:
    """`lanes-index cutover <args>` in `cutover_env`'s environment, from the
    operator lane's checkout, to its end: its whole row (T116, T327)."""
    return run_index(LANES_INDEX, ["cutover", *args], cutover_env(where, db, label, estate),
                     cwd=estate.work)


def aborted(proc: subprocess.CompletedProcess) -> bool:
    """Whether the cutover ended in its step 3's abort: exit 2,
    `EXIT_CUTOVER_ABORTED`, with the abort's `ABORTED` line on stderr
    (`cutover_abort`)."""
    return proc.returncode == 2 and bool(
        re.search(r"^lanes-index: cutover: ABORTED: ", proc.stderr, re.M))


# ------------------------------------------------------------------ T112's writer
#: AT-LR4's fixture (TP:4523-4546): `lanes/LANES.md`, whose line 2 the write
#: replaces, and a file with no final newline, `lanes/aliases.tsv`.
LR4_OLD, LR4_NEW = "t231: the line the write replaces", "t231: the line it becomes"
LR4_ALIASES = ["# old\tnew\tutc", f"Lane-Old\t{LANE}\t2026-11-09T10:00:00Z"]
LR4_FILES = {"lanes/LANES.md": ["# Lanes", LR4_OLD], "lanes/aliases.tsv": LR4_ALIASES}
LR4_NO_NEWLINE = ("lanes/aliases.tsv",)
#: The checkout's own files, which the scratch tree takes from origin (contract section 3.2).
CHECKOUT_FILES = {"lanes/repos.tsv": "# alias\towner/repo\nr9\topensoft/r9\n",
                  "lanes/log/README.md": "# Logs\n"}


def estate_checkout(root: Path, files: dict) -> Path:
    """A lane checkout with `refs/remotes/origin/main` holding `files`, which
    `register snapshot --tree --checkout` reads `lanes/repos.tsv` and
    `lanes/log/README.md` from."""
    origin, work = root / "origin.git", root / "work"
    git("init", "-q", "--bare", "-b", "main", str(origin), cwd=root)
    git("init", "-q", "-b", "main", str(work), cwd=root)
    for rel, text in files.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    git("add", "lanes", cwd=work)
    git("-c", "user.name=T231", "-c", "user.email=t231@example.invalid", "commit", "-q", "-m",
        "the lane checkout", cwd=work)
    git("remote", "add", "origin", str(origin), cwd=work)
    git("push", "-q", "origin", "main", cwd=work)
    git("fetch", "-q", "origin", cwd=work)
    return work


def git_bytes(cwd: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, check=False)
    assert proc.returncode == 0, f"git {' '.join(args)} in {cwd}: {proc.stderr!r}"
    return proc.stdout


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


class Writer:
    """Phase N's writer (T231's bullet): `register snapshot --tree --checkout`
    and `register commit`, from T203's flipped copy with a `mode=primary`
    configuration on the cluster's socket, through the shim (section 3.2) in
    front of the real `psql`, armed by `arm`. Each attempt directory is
    T101's format, built as T253's case builds it (contract section 3.3)."""

    def __init__(self, db, root: Path, checkout: dict = None, shipped: str = "# alias\towner/repo\n"):
        self.db, self.root = db, root
        root.mkdir(parents=True, exist_ok=True)
        self.copy = flipped(root)
        self.shim = root / "shim"
        self.shim.mkdir()
        (self.shim / "psql").write_text(PSQL_SHIM, encoding="utf-8")
        (self.shim / "psql").chmod(0o755)
        self.arm([])
        self.work = estate_checkout(root, checkout or CHECKOUT_FILES)
        (root / "shipped-repos.tsv").write_text(shipped, encoding="utf-8")
        self.env = index_env(root, config(root, db), LANES_WORKSTATION=WS,
                             LANES_REPOS_TSV_SHIPPED=str(root / "shipped-repos.tsv"),
                             PATH=f"{self.shim}{os.pathsep}{os.environ.get('PATH', os.defpath)}",
                             **OPERATOR_GIT)

    def arm(self, arms: list) -> None:
        (self.shim / PSQL_SHIM_CONTROL).write_text(
            json.dumps({"psql": self.db.psql_bin, "arms": arms}), encoding="utf-8")

    def calls(self) -> list:
        """The shim's entries that carried a request, in call order."""
        log = self.shim / PSQL_SHIM_LOG
        if not log.exists():
            return []
        entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        return [e for e in entries if e.get("kind") != "version"]

    def index(self, *args: str) -> subprocess.CompletedProcess:
        return run_index(self.copy, list(args), self.env, cwd=self.work)

    def snapshot_args(self, lane: str, verb: str, args_sha: str) -> list:
        return ["register", "snapshot", "--write-id", "new", "--lane", lane, "--verb", verb,
                "--args-sha256", args_sha]

    def attempt(self, name: str, path: str, change, lane: str = LANE, verb: str = "log") -> dict:
        """One attempt: the snapshot at `n` with its scratch tree, then `path`'s
        image as `change(old bytes)` makes it."""
        att = self.root / name
        att.mkdir()
        args_sha = hashlib.sha256(f"{lane}\0{verb}\0{name}".encode("utf-8")).hexdigest()
        snap = self.index(*self.snapshot_args(lane, verb, args_sha), "--tree", str(att / "tree"),
                          "--checkout", str(self.work))
        assert snap.returncode == 0, (
            f"register snapshot --tree (T111) for the attempt {name}:\n{shown(snap)}")
        keys = dict(line.partition("=")[::2] for line in snap.stdout.splitlines() if "=" in line)
        (att / "snapshot").write_text(snap.stdout, encoding="utf-8")
        old = git_bytes(att / "tree", "cat-file", "blob", f"HEAD:{path}")
        new = change(old)
        image = att / "images" / path
        image.parent.mkdir(parents=True)
        image.write_bytes(new)
        (att / "changes.tsv").write_text(f"M\t{path}\t{blob_id(old)}\t{blob_id(new)}\n",
                                         encoding="utf-8")
        (att / "files").write_text(f"{path}\t1\t{hashlib.sha256(new).hexdigest()}\n",
                                   encoding="utf-8")
        (att / "msg").write_text(f"LANES({lane}@{WS}): {verb} {EM_DASH} T231's case\n",
                                 encoding="utf-8")
        (att / "author").write_text(f"{AUTHOR}\n", encoding="utf-8")
        (att / "not_after").write_text(keys["not_after"] + "\n", encoding="utf-8")
        return {"dir": att, "keys": keys, "lane": lane, "verb": verb, "args_sha": args_sha,
                "path": path, "old": old, "image": new}

    def empty_attempt(self, name: str, lane: str = LANE, verb: str = "log") -> dict:
        """An attempt with an empty change set (lane 3, #165 6808937880, batch e
        Q88), as only a broken seam leaves one: the snapshot at `n` with its
        scratch tree, and `msg`, `author` and `not_after` as `attempt` writes
        them, but a `changes.tsv` and a `files` of 0 bytes and no `images/`."""
        att = self.root / name
        att.mkdir()
        args_sha = hashlib.sha256(f"{lane}\0{verb}\0{name}".encode("utf-8")).hexdigest()
        snap = self.index(*self.snapshot_args(lane, verb, args_sha), "--tree", str(att / "tree"),
                          "--checkout", str(self.work))
        assert snap.returncode == 0, (
            f"register snapshot --tree (T111) for the attempt {name}:\n{shown(snap)}")
        keys = dict(line.partition("=")[::2] for line in snap.stdout.splitlines() if "=" in line)
        (att / "snapshot").write_text(snap.stdout, encoding="utf-8")
        (att / "changes.tsv").write_bytes(b"")
        (att / "files").write_bytes(b"")
        (att / "msg").write_text(f"LANES({lane}@{WS}): {verb} {EM_DASH} T231's case\n",
                                 encoding="utf-8")
        (att / "author").write_text(f"{AUTHOR}\n", encoding="utf-8")
        (att / "not_after").write_text(keys["not_after"] + "\n", encoding="utf-8")
        return {"dir": att, "keys": keys, "lane": lane, "verb": verb, "args_sha": args_sha}

    def shim_lines(self) -> list:
        """Every line of the shim's log, its `psql --version` probes included."""
        log = self.shim / PSQL_SHIM_LOG
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    def commit_args(self, att: dict) -> list:
        keys = att["keys"]
        return ["register", "commit", "--write-id", keys["write_id"], "--generation",
                keys["generation"], "--lane", att["lane"], "--verb", att["verb"],
                "--args-sha256", att["args_sha"], "--workstation", WS, str(att["dir"])]

    def commit(self, att: dict) -> subprocess.CompletedProcess:
        return self.index(*self.commit_args(att))

    def commit_calls(self) -> list:
        return [c for c in self.calls() if "commit_write(" in c.get("sent", "")]

    def after_commit(self) -> list:
        """The calls after the first commit call: LR004's one re-read, and no other."""
        calls = self.calls()
        firsts = [i for i, c in enumerate(calls) if "commit_write(" in c.get("sent", "")]
        return calls[firsts[0] + 1:] if firsts else []


def lr4_writer(db, tmp_path: Path) -> tuple:
    """AT-LR4's register: `LR4_FILES` imported, `lanes/aliases.tsv` with no final
    newline, brought to `primary` with the marker `present` by AT-LR006's route,
    and the writer whose attempt replaces `lanes/LANES.md`'s line 2."""
    n = bring_to_primary(db, LR4_FILES, no_newline=LR4_NO_NEWLINE)
    return n, Writer(db, tmp_path / "writer")


def lr4_change(old: bytes) -> bytes:
    text = old.decode("utf-8")
    assert f"\n{LR4_OLD}\n" in text, text
    return text.replace(f"\n{LR4_OLD}\n", f"\n{LR4_NEW}\n").encode("utf-8")


def lr4_edit(**changed) -> dict:
    """The replace `register_commit_entry` sends for the write (lanes-index:10887-10892 at merge10)."""
    return {"ord": 1, "op": "replace", "path": "lanes/LANES.md", "line_no": 2,
            "old_sha256": line_sha(LR4_OLD), "new_text": LR4_NEW, "to_path": None, **changed}


def lr4_body(**parts) -> dict:
    """The write's entry by hand, for a direct call: the same edit and files row."""
    lines = ["# Lanes", LR4_NEW]
    return entry("write", "log", journal={"args_sha256": ARGS_SHA256}, edits=[lr4_edit()],
                 files=[{"path": "lanes/LANES.md", "present": True, "sha256": rendered(lines),
                         "final_newline": True}], **parts)


def ended_with(proc: subprocess.CompletedProcess, code: str) -> bool:
    """Whether `register commit`'s stderr carries psql's `ERROR:  <code>:` line
    (contract section 2.6, `register_say_error`)."""
    return bool(re.search(rf"^ERROR:\s+{code}:", proc.stderr, re.M))


# =================================================================== AT-SET
def test_set_seq_is_minus_1_after_the_bootstrap(pg):
    """After the bootstrap: `mode = 'files'`, the marker `absent`, `set_seq = -1`,
    and the head -1, with no `marker_seq`, no `restore_prior` and no journal."""
    switch = switch_of(pg)
    assert (switch["mode"], switch["marker_state"], switch["set_seq"]) == ("files", "absent", -1), switch
    assert switch["marker_seq"] is None and switch["restore_prior"] is None, switch
    assert head(pg) == -1
    assert journal_of(pg) == []


@pytest.mark.parametrize("case", ["first", "after-loss"])
def test_set_seq_after_a_cutover_is_the_cutovers_own_seq(pg_cluster, tmp_path, case):
    """`set_seq` is the cutover's own seq: 1 after the first import at 0, and
    `m+1` after an after-loss import at `m` and `cutover --import <M>
    --after-loss`, whose transaction also gives the switch a generation other
    than the bootstrap's (F10, F18). The cutover is `lanes-index cutover`'s
    whole row against T231's scratch schema (T116's transaction, then T327's
    push; lane 3's (c), #165 6828023371), run from the operator lane's own
    checkout, whose origin's `main` is a real commit C (`OperatorEstate`);
    the import is the entry `import --at <C>` sends, by a direct call, with
    `root_seq` `m` for the after-loss form. Its 0 is the whole row (T327): the
    switch `primary` with the marker `present` at `marker_seq` = the head =
    `set_seq`; `marker_commit` is origin's new tip, the one push origin took,
    a child of C carrying `Register-Seq` that seq; and `journal.operator` is
    true for that seq alone."""
    db = scratch_register(pg_cluster, tmp_path / "scratch")
    try:
        estate = OperatorEstate(tmp_path / "estate")
        bootstrap_generation = generation(db, T231_SCHEMA)
        m = 0 if case == "first" else REIMPORT_M
        rows = {} if case == "first" else {"root_seq": REIMPORT_M}
        body = import_entry(DEFAULT_FILES, commit=estate.commit, tree=estate.tree, **rows)
        assert committed(db, -1, body, "the import", T231_SCHEMA) == m
        args = ["--import", estate.commit] + (["--after-loss"] if case == "after-loss" else [])
        proc = cutover_run(tmp_path / "operator", db, STORE_LABEL, estate, *args)
        assert proc.returncode == 0, f"cutover {' '.join(args)}:\n{shown(proc)}"
        switch = switch_of(db, T231_SCHEMA)
        assert switch["set_seq"] == m + 1, f"set_seq is {switch['set_seq']}, not {m + 1}: {switch}"
        assert head(db, T231_SCHEMA) == m + 1 and switch["marker_seq"] == m + 1, switch
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
        tip = estate.tip()
        assert estate.pushes() == [["accepted", estate.commit, tip, "refs/heads/main"]], (
            f"origin took not one push, the marker's, onto C: {estate.pushes()}")
        assert switch["marker_commit"] == tip, (switch, tip)
        assert estate.parent(tip) == estate.commit and estate.seq_of(tip) == str(m + 1), tip
        assert [seq for seq, _kind, operator in journal_of(db, T231_SCHEMA) if operator] == [m + 1]
        if case == "first":
            assert switch["generation"] == bootstrap_generation, switch
        else:
            assert switch["generation"] != bootstrap_generation, (
                f"the after-loss cutover kept the bootstrap's generation {bootstrap_generation}")
    finally:
        pg_cluster.drop_database(db.name)


def test_the_marker_moves_only_through_commit_write_and_record_marker(pg):
    """The marker's four states move only as section 1.3's kinds table says:
    the import leaves `files`/`absent` and `set_seq` -1; the cutover at 1 sets
    `primary`/`adding`, `marker_seq` and `set_seq` 1, and `journal.operator` is
    true for seq 1 only; `record_marker` at another seq is LR002 and changes
    nothing; REGISTER-WRITER's own `UPDATE` of the switch is 42501;
    `record_marker` at 1 reads `present` and `marker_commit` holds the
    confirmed commit, and again at 1 is LR002; a write then commits and leaves
    the switch as it was; the rollback's entry at `k+1` sets
    `files`/`removing`; `record_marker` at `k+1` reads `absent`."""
    def unchanged(proc, code, what):
        before = switch_of(pg)
        refused(proc(), code, what)
        assert switch_of(pg) == before, f"{what} changed the switch"

    boot = switch_of(pg)
    imported = committed(pg, head(pg), import_entry(DEFAULT_FILES), "the import")
    assert imported == 0 and switch_of(pg) == boot, "the import moved the switch"
    cut = committed(pg, imported, cutover_entry(), "the cutover")
    switch = switch_of(pg)
    assert (switch["mode"], switch["marker_state"], switch["marker_seq"], switch["set_seq"]) == (
        "primary", "adding", cut, cut) and cut == 1, switch
    assert switch["marker_commit"] is None, switch
    assert journal_of(pg) == [[0, "import", False], [1, "cutover", True]]
    unchanged(lambda: marker_call(pg, 0), "LR002", "record_marker at seq 0, not the cutover's")
    unchanged(lambda: psql(pg, f"BEGIN READ WRITE;\nUPDATE {SCHEMA}.register_switch SET "
                               f"marker_state = 'present', marker_commit = '{MARKER_COMMIT}' "
                               f"WHERE id = 1;\nCOMMIT;\n", WRITER),
              "42501", "REGISTER-WRITER's own UPDATE of the switch")
    confirmed = marker_call(pg, cut)
    assert confirmed.returncode == 0 and confirmed.stdout.strip() == "present", confirmed.stderr
    switch = switch_of(pg)
    assert (switch["mode"], switch["marker_state"], switch["marker_commit"],
            switch["set_seq"]) == ("primary", "present", MARKER_COMMIT, cut), switch
    unchanged(lambda: marker_call(pg, cut), "LR002", "record_marker again at the confirmed seq")
    present = switch_of(pg)
    k = committed(pg, cut, a_write(pg), "a write")
    assert switch_of(pg) == present, "a write moved the switch"
    back = committed(pg, k, rollback_entry(), "the rollback's entry")
    switch = switch_of(pg)
    assert (switch["mode"], switch["marker_state"], switch["marker_seq"], switch["set_seq"]) == (
        "files", "removing", back, back) and back == k + 1, switch
    assert [seq for seq, _kind, operator in journal_of(pg) if operator] == [cut, back]
    gone = marker_call(pg, back)
    assert gone.returncode == 0 and gone.stdout.strip() == "absent", gone.stderr
    assert pair_of(pg) == ("files", "absent")


def test_a_write_is_refused_lr002_while_the_marker_is_adding_or_removing(pg):
    """While the marker is `adding` (a cutover not yet confirmed) and while it
    is `removing` (a rollback's entry not yet confirmed), a write's commit call
    fails with LR002, naming the switch and the marker, and every table is
    unchanged; between them, the confirmed marker lets a write commit. The
    writer's 69 for LR002 is `register commit`'s exit table (T112), which this
    case does not run, so it passes on T107 alone."""
    imported = committed(pg, head(pg), import_entry(DEFAULT_FILES), "the import")
    cut = committed(pg, imported, cutover_entry(), "the cutover")
    for marker in ("adding", "removing"):
        assert pair_of(pg)[1] == marker
        before = state(pg)
        message = refused(commit_call(pg, head(pg), a_write(pg)), "LR002",
                          f"a write while the marker is {marker}")
        assert marker in message, message
        assert state(pg) == before, f"a write refused LR002 while {marker} changed the register"
        if marker == "adding":
            assert marker_call(pg, cut).stdout.strip() == "present"
            k = committed(pg, cut, a_write(pg), "the control: a write once the marker is present")
            committed(pg, k, rollback_entry(), "the rollback's entry")


def test_the_rollbacks_entry_sets_files_removing_and_its_own_seq(pg):
    """After the import, the cutover, `record_marker` and three writes, at the
    head `k`: the rollback's first transaction, `commit_write` with a `rollback`
    entry as REGISTER-WRITER, read in one snapshot: `mode = 'files'`, the marker
    `removing`, the head and `set_seq` `k+1`, and the entry at `k+1` the
    operator entry that removes `lanes/STORE`. After `record_marker` at `k+1`,
    the marker reads `absent` and `set_seq` stays `k+1`."""
    k = three_writes(pg, bring_to_primary(pg))
    assert committed(pg, k, rollback_entry(), "the rollback's entry") == k + 1
    seen = json.loads(sql(pg, (
        f"SELECT jsonb_build_object('switch', to_jsonb(s), 'head', h.seq, 'entry', to_jsonb(j), "
        f"'edits', (SELECT jsonb_agg(jsonb_build_array(e.op, e.path) ORDER BY e.ord) "
        f"FROM {SCHEMA}.journal_edits e WHERE e.seq = h.seq), "
        f"'store', EXISTS (SELECT 1 FROM {SCHEMA}.files f WHERE f.path = 'lanes/STORE')) "
        f"FROM {SCHEMA}.register_switch s, {SCHEMA}.register_head h "
        f"LEFT JOIN {SCHEMA}.journal j ON j.seq = h.seq;")))
    switch = seen["switch"]
    assert (switch["mode"], switch["marker_state"]) == ("files", "removing"), switch
    assert seen["head"] == k + 1 and switch["set_seq"] == k + 1 and switch["marker_seq"] == k + 1, seen
    assert (seen["entry"]["kind"], seen["entry"]["operator"]) == ("rollback", True), seen["entry"]
    assert seen["edits"] == [["remove", "lanes/STORE"]] and seen["store"] is False, seen
    confirmed = marker_call(pg, k + 1)
    assert confirmed.returncode == 0 and confirmed.stdout.strip() == "absent", confirmed.stderr
    switch = switch_of(pg)
    assert (switch["mode"], switch["marker_state"], switch["set_seq"]) == ("files", "absent", k + 1)


@pytest.mark.parametrize("case", ["held", "in-turn"])
def test_the_rollbacks_entry_makes_an_older_writer_snapshot_fail_lr001_or_40001_then_69(
        pg, tmp_path, case):
    """A writer whose snapshot is older than the rollback's entry (section 1.3,
    "The signals a writer gets"), the writer being `register snapshot --tree`
    and `register commit` (T111, T112):

      * `[held]`: the rollback's first transaction holds the head row
        uncommitted; the writer's commit call starts; the case polls until a
        backend running `commit_write` shows `wait_event_type = 'Lock'`, as
        AT-D19 stages it; the rollback commits. The commit gets 40001, so
        `register commit` exits 75, a lost turn;
      * `[in-turn]`: the snapshot is read before the rollback's transaction and
        the commit call starts after it commits: LR001, the head having moved
        to `k+1`, so 75.

    Either way the new attempt's snapshot reads the switch at `files` and
    exits 69, and nothing but the rollback's entry was written."""
    k = three_writes(pg, bring_to_primary(pg))
    writer = Writer(pg, tmp_path / "writer")
    att = writer.attempt("older", "lanes/LANES.md", lambda old: old + b"t231: the older writer\n")
    assert att["keys"]["n"] == str(k), att["keys"]
    gen, client = generation(pg), window(pg)["version"]
    body = json.dumps(rollback_entry()).replace("'", "''")
    if case == "in-turn":
        assert committed(pg, k, rollback_entry(), "the rollback's entry") == k + 1
        proc = writer.commit(att)
        assert proc.returncode == 75 and ended_with(proc, "LR001"), shown(proc)
    else:
        rollback = session(pg, "t231-rollback")
        rollback.stdin.write(f"\\set VERBOSITY verbose\nSET ROLE {WRITER};\n"
                             f"BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
                             f"SELECT {SCHEMA}.commit_write({k}, '{uuid.uuid4()}'::uuid, {client}, "
                             f"'{gen}'::uuid, '{body}'::jsonb);\n")
        rollback.stdin.flush()
        wait_for(pg, "t231-rollback", "a.state = 'idle in transaction'", "the rollback held")
        held = subprocess.Popen([sys.executable, str(writer.copy), *writer.commit_args(att)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                                env=writer.env, cwd=str(writer.work))
        try:
            wait_sql(pg, "SELECT count(*) FROM pg_stat_activity a WHERE a.datname = "
                         "current_database() AND a.application_name <> 't231-rollback' "
                         "AND a.query LIKE '%commit_write(%' AND a.wait_event_type = 'Lock'",
                     "the writer's commit call waiting on the head row")
            _, err = rollback.communicate("COMMIT;\n", timeout=60)
            assert rollback.returncode == 0, f"the rollback's transaction failed: {err}"
            out, err = held.communicate(timeout=60)
        finally:
            if held.poll() is None:
                held.kill()
                held.communicate()
        proc = subprocess.CompletedProcess(held.args, held.returncode, out, err)
        assert proc.returncode == 75 and ended_with(proc, "40001"), shown(proc)
    assert (head(pg), pair_of(pg)) == (k + 1, ("files", "removing"))
    assert [row[1] for row in journal_of(pg)][-2:] == ["write", "rollback"], journal_of(pg)
    again = writer.index(*writer.snapshot_args(LANE, "log", att["args_sha"]))
    assert again.returncode == 69, f"the new attempt's snapshot:\n{shown(again)}"


KINDS = ("import", "cutover", "write", "stray-import", "stray-revert", "rollback")
STATES = {"files-absent": ("files", "absent"), "primary-adding": ("primary", "adding"),
          "primary-present": ("primary", "present"), "files-removing": ("files", "removing")}
#: Section 1.3's kinds table: where each kind commits (the after-loss
#: cutover's `primary`/`present` row is the restore form's, T116's).
COMMITS_IN = {("import", "files-absent"), ("cutover", "files-absent"),
              ("write", "primary-present"), ("stray-import", "primary-present"),
              ("stray-revert", "primary-present"), ("rollback", "primary-present")}


def kind_entry(kind: str) -> dict:
    """One well-formed entry of each kind, as its writer sends it."""
    if kind == "import":
        return import_entry(DEFAULT_FILES)
    if kind == "cutover":
        return cutover_entry()
    if kind == "write":
        return appended(DEFAULT_FILES["lanes/LANES.md"], "t231: a write")
    if kind == "stray-import":
        lines = [*DEFAULT_FILES["lanes/LANES.md"], "t231: a stray line"]
        return entry("stray-import", "import --single", journal={"git_commit": SHA_B},
                     edits=[{"ord": 1, "op": "append", "path": "lanes/LANES.md",
                             "new_text": lines[-1]}],
                     files=[{"path": "lanes/LANES.md", "present": True, "sha256": rendered(lines),
                             "final_newline": True}])
    if kind == "stray-revert":
        return entry("stray-revert", "render --revert", journal={"git_commit": SHA_B})
    return rollback_entry()


def reach(db, state_name: str, kind: str) -> None:
    """The switch at `state_name`, by AT-LR006's route and the rollback's
    entry; for a cutover at `files`/`absent`, the import it follows first."""
    if state_name == "files-absent" and kind == "cutover":
        committed(db, head(db), import_entry(DEFAULT_FILES), "the import the cutover follows")
    elif state_name == "primary-adding":
        committed(db, committed(db, head(db), import_entry(DEFAULT_FILES), "the import"),
                  cutover_entry(), "the cutover")
    elif state_name == "primary-present":
        bring_to_primary(db)
    elif state_name == "files-removing":
        committed(db, bring_to_primary(db), rollback_entry(), "the rollback's entry")
    assert pair_of(db) == STATES[state_name]


@pytest.mark.parametrize("case", [f"{kind}-{name}" for kind in KINDS for name in STATES])
def test_no_kind_commits_in_a_state_its_kinds_table_row_refuses(pg, case):
    """For each kind and each state of the switch, a commit call commits only
    where section 1.3's kinds table allows it, and otherwise raises LR002 with
    the journal's count and the head unchanged. So besides the import's
    baseline, nothing is journaled while the switch is not `primary` except the
    two operator entries (D24)."""
    name = "-".join(case.split("-")[-2:])
    kind = case[:-len(name) - 1]
    reach(pg, name, kind)
    base, count = head(pg), len(journal_of(pg))
    proc = commit_call(pg, base, kind_entry(kind))
    if (kind, name) in COMMITS_IN:
        assert proc.returncode == 0, f"{kind} at {name} is refused: {proc.stderr.strip()}"
        assert int(proc.stdout.strip().splitlines()[-1]) == (0 if base == -1 else base + 1)
        assert len(journal_of(pg)) == count + 1
        return
    refused(proc, "LR002", f"{kind} at {name}")
    assert (head(pg), len(journal_of(pg))) == (base, count), f"{kind} at {name} wrote"


def test_switch_to_files_aborts_only_an_unconfirmed_cutover(pg):
    """With the cutover at seq 1 not yet confirmed, `switch_to_files(version, 1,
    lane, ws)` deletes seq 1 and its rows, sets the head to 0 and the switch to
    `files` with the marker `absent`, and `set_seq` to 0, the abort's base. With
    nothing to abort, and with the marker `present`, it fails with LR002 and
    changes nothing."""
    imported = committed(pg, head(pg), import_entry(DEFAULT_FILES), "the import")
    cut = committed(pg, imported, cutover_entry(), "the cutover")
    proc = abort_call(pg, cut)
    assert proc.returncode == 0 and proc.stdout.strip() == str(imported), proc.stderr
    switch = switch_of(pg)
    assert (switch["mode"], switch["marker_state"], switch["set_seq"], switch["marker_seq"]) == (
        "files", "absent", imported, None), switch
    assert head(pg) == imported and journal_of(pg) == [[0, "import", False]]
    left = sql(pg, f"SELECT (SELECT count(*) FROM {SCHEMA}.journal_edits WHERE seq = {cut}) + "
                   f"(SELECT count(*) FROM {SCHEMA}.journal_files WHERE seq = {cut}) + "
                   f"(SELECT count(*) FROM {SCHEMA}.files WHERE path = 'lanes/STORE') + "
                   f"(SELECT count(*) FROM {SCHEMA}.doc_lines WHERE path = 'lanes/STORE');")
    assert left == "0", f"the abort left {left} rows of seq {cut} or lanes/STORE"
    before = state(pg)
    refused(abort_call(pg, cut), "LR002", "switch_to_files with no cutover to abort")
    assert state(pg) == before
    again = committed(pg, imported, cutover_entry(), "the cutover again")
    assert marker_call(pg, again).stdout.strip() == "present"
    before = state(pg)
    refused(abort_call(pg, again), "LR002", "switch_to_files with the marker present")
    assert state(pg) == before, "switch_to_files with the marker present changed the register"


def test_the_reimport_forms_abort_leaves_label_and_generation(pg_cluster, tmp_path):
    """The re-import form's abort (the third database; lane 3, comment
    6710770304), seen through the cutover's own step 3 (T327; lane 3's (c),
    #165 6828023371): after an after-loss import at `m`, `lanes-index cutover
    --import <C> --after-loss`, from the operator lane's own checkout
    (`OperatorEstate`), commits its entry at `m+1`, and origin refuses the
    marker's push. The case holds that push at origin's hook and reads the
    switch: `primary` with the marker `adding`, `set_seq` `m+1`, and a
    generation other than the lost database's. Released, the push is
    refused, the read-back proves the marker absent, and the cutover aborts,
    exit 2 with its `ABORTED` line: its `switch_to_files` at `m+1` sets
    `files` with the marker `absent`, `set_seq` `m`, and `lanes/STORE` gone,
    and leaves the `database_label` and the `generation` its cutover set, as
    the held read saw them; origin's `main` is still C. So a commit call
    carrying the lost database's generation, as a pending record made against
    it would, still fails with LR007."""
    db = scratch_register(pg_cluster, tmp_path / "scratch")
    try:
        estate = OperatorEstate(tmp_path / "estate")
        lost = generation(db, T231_SCHEMA)
        m = REIMPORT_M
        assert committed(db, -1, import_entry(DEFAULT_FILES, commit=estate.commit, tree=estate.tree,
                                              root_seq=m), "the re-import", T231_SCHEMA) == m
        estate.refuse(hold=True)
        run = subprocess.Popen([sys.executable, str(LANES_INDEX), "cutover", "--import",
                                estate.commit, "--after-loss"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                               errors="replace", cwd=str(estate.work),
                               env=cutover_env(tmp_path / "operator", db, STORE_LABEL, estate))
        cut = None
        try:
            if estate.wait_reached(run):
                cut = switch_of(db, T231_SCHEMA)        # the entry stands; its push is held
        finally:
            estate.release.write_text("", encoding="utf-8")
            try:
                out, err = run.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                run.kill()
                out, err = run.communicate()
        proc = subprocess.CompletedProcess(run.args, run.returncode, out, err)
        assert cut is not None, f"the cutover's push never reached origin's hook:\n{shown(proc)}"
        assert (cut["mode"], cut["marker_state"], cut["set_seq"]) == (
            "primary", "adding", m + 1), cut
        assert cut["generation"] != lost, cut
        assert aborted(proc), f"the cutover did not abort at its step 3:\n{shown(proc)}"
        assert [push[0] for push in estate.pushes()] == ["refused"], estate.pushes()
        assert estate.tip() == estate.commit, "origin's main moved past C"
        switch = switch_of(db, T231_SCHEMA)
        assert (switch["mode"], switch["marker_state"], switch["set_seq"]) == (
            "files", "absent", m), switch
        assert (switch["database_label"], switch["generation"]) == (
            cut["database_label"], cut["generation"]), (
            f"the abort changed the label or the generation its cutover set: {cut} -> {switch}")
        assert head(db, T231_SCHEMA) == m
        assert sql(db, f"SELECT count(*) FROM {T231_SCHEMA}.files WHERE path = 'lanes/STORE';") == "0"
        proc = commit_call(db, m, import_entry(DEFAULT_FILES), gen=lost, schema=T231_SCHEMA)
        refused(proc, "LR007", "a commit call carrying the lost database's generation")
        assert re.search(r"^DETAIL:\s+generation\s*$", proc.stderr, re.M), proc.stderr
        assert head(db, T231_SCHEMA) == m
    finally:
        pg_cluster.drop_database(db.name)


def test_restore_prior_is_set_by_the_restore_form_and_cleared_by_record_marker(pg_cluster,
                                                                              tmp_path):
    """The restore form (a database restored at `b`, here the scratch database
    at its head after the first cutover), each cutover `lanes-index
    cutover`'s whole row (T116's transaction, then T327's push; lane 3's (c),
    #165 6828023371) from the operator lane's own checkout
    (`OperatorEstate`), so `restore_prior` is checked only by what the abort
    puts back. The first form's 0 leaves the marker `present`. Then `cutover
    --after-loss` with another `register_label=` (N4) renders up to `b`,
    which origin already carries, commits at `b+1`, pushes its marker and
    records it: its 0 leaves `primary` with the marker `present`, `set_seq`
    `b+1` and its label, and `record_marker` has cleared `restore_prior`. A
    second restore form, whose marker's push origin refuses, aborts at its
    step 3, exit 2, and its `switch_to_files` puts back what `restore_prior`
    held: `lanes/STORE`'s `files` row and lines with their old `line_id`s,
    the switch row whole, the head `b` and `set_seq` the value before that
    cutover; origin's `main` is where that cutover found it. As the admin
    under `SET ROLE lanes_register_owner`, setting `restore_prior` while the
    marker is not `adding` fails with 23514 (`register_switch_check4`)."""
    db = scratch_register(pg_cluster, tmp_path / "scratch")
    try:
        estate = OperatorEstate(tmp_path / "estate")
        imported = committed(db, -1, import_entry(DEFAULT_FILES, commit=estate.commit,
                                                  tree=estate.tree), "the import", T231_SCHEMA)
        proc = cutover_run(tmp_path / "first", db, STORE_LABEL, estate, "--import", estate.commit)
        assert proc.returncode == 0, shown(proc)
        assert pair_of(db, T231_SCHEMA) == ("primary", "present"), switch_of(db, T231_SCHEMA)
        assert head(db, T231_SCHEMA) == imported + 1
        for n, label in enumerate((f"{STORE_LABEL}-restored", f"{STORE_LABEL}-restored-2"), 1):
            b = head(db, T231_SCHEMA)                   # the restored backup's head
            before = store_of(db, T231_SCHEMA)
            assert before["file"] and before["lines"], before
            tip = estate.tip()
            if n == 2:
                estate.refuse()
            proc = cutover_run(tmp_path / f"restore-{n}", db, label, estate, "--after-loss")
            if n == 1:
                assert proc.returncode == 0, shown(proc)
                switch = switch_of(db, T231_SCHEMA)
                assert (switch["mode"], switch["marker_state"], switch["set_seq"],
                        switch["database_label"]) == ("primary", "present", b + 1, label), switch
                assert switch["restore_prior"] is None, "record_marker kept it"
                pushed = estate.tip()
                assert switch["marker_commit"] == pushed and pushed != tip, (switch, tip)
                assert estate.parent(pushed) == tip and estate.seq_of(pushed) == str(b + 1), pushed
                continue
            assert aborted(proc), f"the restore form did not abort at its step 3:\n{shown(proc)}"
            assert [push[0] for push in estate.pushes()] == ["accepted", "accepted", "refused"], (
                estate.pushes())
            assert estate.tip() == tip, "origin's main moved under the refused push"
            after = store_of(db, T231_SCHEMA)
            assert after == before, (
                f"the restore form's abort did not put back the switch row and lanes/STORE:\n"
                f"want {json.dumps(before, sort_keys=True)[:2000]}\n"
                f"got  {json.dumps(after, sort_keys=True)[:2000]}")
            assert head(db, T231_SCHEMA) == b and after["switch"]["set_seq"] == before["switch"]["set_seq"]
        proc = psql(db, f"UPDATE {T231_SCHEMA}.register_switch SET restore_prior = '{{}}'::jsonb "
                        f"WHERE id = 1;", OWNER)
        refused(proc, "23514", "restore_prior set while the marker is present")
        assert "register_switch_check4" in proc.stderr, proc.stderr
    finally:
        pg_cluster.drop_database(db.name)


@pytest.mark.parametrize("case", ["cutover", "rollback"])
def test_an_operator_entry_with_a_row_outside_lanes_store_is_refused_lr004_at_commit(pg, case):
    """Lane 3's ruling on lane 1's point 1 (comment 6710770304): a cutover entry,
    and a rollback entry, with an extra `files` row outside `lanes/STORE`, are
    each refused at their commit with LR004 (ruling 1), and the journal's count
    and the head are unchanged, so no such entry stays for a later abort to meet
    with 23503. The entry is the test's own, by a direct call: the shim's
    `edit-entry` stands in for no operator command here, since only T116's
    cutover sends one, and this case is T107's."""
    extra = {"path": "lanes/LANES.md", "present": True,
             "sha256": rendered(DEFAULT_FILES["lanes/LANES.md"]), "final_newline": True}
    if case == "cutover":
        base = committed(pg, head(pg), import_entry(DEFAULT_FILES), "the import")
        body = cutover_entry()
    else:
        base = bring_to_primary(pg)
        body = rollback_entry()
    body["files"] = [*body["files"], extra]
    before = state(pg)
    message = refused(commit_call(pg, base, body), "LR004", f"a {case} entry with a LANES.md row")
    assert "outside lanes/STORE" in message, message
    assert state(pg) == before, f"a refused {case} entry changed the register"


def test_the_switch_checks_refuse_a_bad_set_seq_and_a_mode_marker_mismatch(pg):
    """As the admin under `SET ROLE lanes_register_owner`, on a switch at
    `files`/`absent` after a confirmed rollback: an `UPDATE` setting `set_seq`
    to -2 fails with 23514, and so does one setting `primary` with the marker
    `absent` (the switch's checks); the row is unchanged. The control: the
    owner's `UPDATE` of `set_seq` to -1, rolled back, is not refused."""
    back = committed(pg, bring_to_primary(pg), rollback_entry(), "the rollback's entry")
    assert marker_call(pg, back).stdout.strip() == "absent"
    before = switch_of(pg)
    control = psql(pg, f"BEGIN;\nUPDATE {SCHEMA}.register_switch SET set_seq = -1 WHERE id = 1;\n"
                       f"ROLLBACK;\n", OWNER)
    assert control.returncode == 0, f"the owner's UPDATE, the control: {control.stderr}"
    for change in ("set_seq = -2", "mode = 'primary'"):
        proc = psql(pg, f"UPDATE {SCHEMA}.register_switch SET {change} WHERE id = 1;", OWNER)
        refused(proc, "23514", f"the owner's UPDATE setting {change}")
        assert "register_switch" in proc.stderr, proc.stderr
        assert switch_of(pg) == before, f"the refused UPDATE ({change}) changed the switch"


# =================================================================== AT-SPL
#: AT-SPL's fixture (TP:4297-4298): aliases X and Y mapping to O in
#: `lanes/repos.tsv`, here repositories, so a claim's object `<repo>#12` takes
#: D19's spellings (`register_object_spellings`).
SPL_REPOS = "# alias\towner/repo\nx9\topensoft/o9\ny9\topensoft/o9\n"
SPL_O, SPL_X, SPL_Y = "opensoft/o9#12", "x9#12", "y9#12"
SPL_LANES = {"Lane-S1": "aaaaaaaa-0231-4000-8000-00000000a231",
             "Lane-S2": "bbbbbbbb-0231-4000-8000-00000000b231"}
SPL_FILES = {"lanes/LANES.md": ["# Lanes"],
             **{f"lanes/log/{lane}.md": [f"# lane {lane} {EM_DASH} object log"] for lane in SPL_LANES}}


def spl_line(verb: str, lane: str, obj: str) -> bytes:
    """A log line in `parse_log_line`'s grammar (lanes-index at merge10)."""
    return (f"{verb} {EM_DASH} lane {lane}, session {SPL_LANES[lane]}@{WS}, "
            f"2026-11-10T12:00:00Z, {obj}\n").encode("utf-8")


def spl_write(writer: Writer, name: str, verb: str, lane: str, obj: str) -> subprocess.CompletedProcess:
    att = writer.attempt(name, f"lanes/log/{lane}.md", lambda old: old + spl_line(verb, lane, obj),
                         lane=lane, verb=verb.lower())
    return writer.commit(att)


def holds_on(db, lane_key: str) -> list:
    return json.loads(sql(db, f"SELECT coalesce(jsonb_agg(to_jsonb(h)), '[]') FROM "
                              f"{SCHEMA}.object_holds h WHERE h.lane_key = {sql_text(lane_key)};"))


@pytest.mark.parametrize("case", ["as-alias", "as-key"])
def test_a_claim_records_its_spelling_its_key_and_its_aliases(pg, tmp_path, case):
    """L1's claim line, naming X or O, through the writer (`register snapshot
    --tree` and `register commit`): its `object_holds` row keeps its line's
    object, and `spellings`, compared as a set, holds {X, O, Y}.

    `claim` canonicalises a claim typed as X and writes its line naming O
    (Y:3402-3403), so that row has `object = O` (TP:4303). Phase N sends the
    line itself, and `[as-alias]`'s line names X, a line `claim` never writes:
    its row keeps `object = X`, its line's object (Y:1224, Y:1252), with the
    same set. `[as-key]`'s line names O (lane 3's batch 11 (2))."""
    bring_to_primary(pg, SPL_FILES)
    writer = Writer(pg, tmp_path / "writer", {**CHECKOUT_FILES, "lanes/repos.tsv": SPL_REPOS})
    line_object = SPL_X if case == "as-alias" else SPL_O
    proc = spl_write(writer, "claim", "CLAIMED", "Lane-S1", line_object)
    assert proc.returncode == 0, shown(proc)
    rows = holds_on(pg, "lane-s1")
    assert len(rows) == 1, rows
    assert rows[0]["object"] == line_object, (
        f"the claim's row has object {rows[0]['object']!r}, not its line's {line_object!r}")
    assert set(rows[0]["spellings"] or ()) == {SPL_X, SPL_O, SPL_Y}, rows[0]


def test_a_released_claims_spellings_block_nothing(pg, tmp_path):
    """After L1 claims O and releases it, L2's claim of X commits, with no LR005
    `claim-spellings`, and its row holds the same set {X, O, Y}."""
    bring_to_primary(pg, SPL_FILES)
    writer = Writer(pg, tmp_path / "writer", {**CHECKOUT_FILES, "lanes/repos.tsv": SPL_REPOS})
    for name, verb, lane, obj in (("claim", "CLAIMED", "Lane-S1", SPL_O),
                                  ("release", "RELEASED", "Lane-S1", SPL_O),
                                  ("claim-2", "CLAIMED", "Lane-S2", SPL_X)):
        proc = spl_write(writer, name, verb, lane, obj)
        assert "claim-spellings" not in proc.stderr, shown(proc)
        assert proc.returncode == 0, f"{name}:\n{shown(proc)}"
    rows = holds_on(pg, "lane-s2")
    assert len(rows) == 1 and rows[0]["verb"] == "CLAIMED", rows
    assert set(rows[0]["spellings"] or ()) == {SPL_X, SPL_O, SPL_Y}, rows[0]


# =================================================================== AT-LR4
#: Each rewrite of the write's entry (TP:4564-4583), as an `edit-entry` arm's
#: `field` and `value` (no `value`: the field removed). The shim names a field
#: by a dotted path that never enters a list, so a rewrite of one edit or one
#: files row sends the whole list, as `register_commit_entry` builds it.
#: `operator-no-edit` and `root-seq-on-a-non-empty-journal` are direct calls:
#: the first by the test plan's words, and the second since the shim adds no key.
LR4_CASES = ("digest-not-hex-equal", "edit-old-sha256", "path-not-in-files", "write-edits-store",
             "operator-no-edit", "no-journal-object", "journal-value-not-string-or-null",
             "list-key-not-array", "raw-not-the-lines-text", "root-seq-on-a-non-empty-journal",
             "write-without-args-sha256")
LR4_DIRECT = ("operator-no-edit", "root-seq-on-a-non-empty-journal")


def lr4_arm(case: str, image: bytes) -> dict:
    files_row = {"path": "lanes/LANES.md", "present": True,
                 "sha256": hashlib.sha256(image).hexdigest(), "final_newline": True}
    other = "f" * 64 if files_row["sha256"] != "f" * 64 else "e" * 64
    arms = {
        "digest-not-hex-equal": {"field": "files", "value": [{**files_row, "sha256": other}]},
        "edit-old-sha256": {"field": "edits",
                            "value": [lr4_edit(old_sha256=line_sha("t231: not the line"))]},
        "path-not-in-files": {"field": "files", "value": []},
        "write-edits-store": {"field": "edits", "value": [lr4_edit(
            path="lanes/STORE", line_no=1, old_sha256=line_sha(STORE_LINES[0]))]},
        "no-journal-object": {"field": "journal"},
        "journal-value-not-string-or-null": {"field": "journal.message", "value": 231},
        "list-key-not-array": {"field": "lanes", "value": {}},
        "raw-not-the-lines-text": {"field": "lanes", "value": [
            {"path": "lanes/LANES.md", "line_no": 2, "raw": "t231: not the line's text",
             "lane_key": LANE.lower(), "lane": LANE, "archived": False, "owner": None}]},
        "write-without-args-sha256": {"field": "journal.args_sha256"},
    }
    return {"mode": "edit-entry", "match": "commit_write", **arms[case]}


def lr4_refused(pg, writer: Writer, att: dict, before: dict, code: str, what: str) -> None:
    """AT-LR4's oracle on `register commit`: one commit call, rewritten; its
    code on stderr; LR004's one re-read from SQL after it and no resend (R02),
    or none for another code, which is 69 at once; 69; nothing written."""
    proc = writer.commit(att)
    assert proc.returncode == 69, f"{what}:\n{shown(proc)}"
    assert ended_with(proc, code), f"{what}: no `ERROR:  {code}:` line:\n{shown(proc)}"
    commits = writer.commit_calls()
    assert len(commits) == 1, f"{what}: {len(commits)} commit calls, not one (R02)"
    assert commits[0]["arms"] == ["edit-entry"], commits[0]
    after = writer.after_commit()
    if code == "LR004":
        assert len(after) == 1 and "render_file(" in after[0]["sent"], (
            f"{what}: LR004's re-read is not one call after the commit call: {after}")
    else:
        assert after == [], f"{what}: {code} is 69 at once, with no re-read: {after}"
    assert state(pg) == before, f"{what}: the register changed"


@pytest.mark.parametrize("case", LR4_CASES)
def test_lr004_on_an_edit_or_proof_that_does_not_apply_leaves_everything_unchanged(
        pg, tmp_path, case):
    """Each rewrite of the write's entry ends with LR004 (23514 for
    `write-without-args-sha256`, so 69 at once); `register_head.seq`, `journal`,
    `journal_edits`, `journal_files`, `files` and `doc_lines` equal their values
    before (every table of section 1.2 is compared). The write replaces
    `lanes/LANES.md`'s line 2, so `edit-old-sha256` has an `old_sha256` to
    rewrite. `operator-no-edit` (a `rollback` entry with no edit and no other
    row) and `root-seq-on-a-non-empty-journal` are direct calls, LR004 each."""
    n, writer = lr4_writer(pg, tmp_path) if case not in LR4_DIRECT else (
        bring_to_primary(pg, LR4_FILES, no_newline=LR4_NO_NEWLINE), None)
    before = state(pg)
    if case in LR4_DIRECT:
        body = entry("rollback", "rollback") if case == "operator-no-edit" else lr4_body(root_seq=0)
        message = refused(commit_call(pg, n, body), "LR004", case)
        assert ("with no edit" if case == "operator-no-edit" else "root_seq") in message, message
        assert state(pg) == before, f"{case}: the register changed"
        return
    att = writer.attempt("rewritten", "lanes/LANES.md", lr4_change)
    writer.arm([lr4_arm(case, att["image"])])
    lr4_refused(pg, writer, att, before, "23514" if case == "write-without-args-sha256" else "LR004",
                case)


def test_lr004_reloads_once_then_exits_69(pg, tmp_path):
    """Armed for every commit call (R02; R-F10-35; lane 3, #165 6756017599): the
    writer's one commit call meets LR004; its "reload" is the one re-read of the
    bases from SQL; with equal bases it sends nothing again and exits 69, naming
    the entry and LR004's own message (B10 tasks:424); nothing is written. A
    moved head after the re-read (75) and a differing base's 69 have no case
    here (R-F13-2)."""
    _n, writer = lr4_writer(pg, tmp_path)
    before = state(pg)
    att = writer.attempt("every-call", "lanes/LANES.md", lr4_change)
    writer.arm([{**lr4_arm("digest-not-hex-equal", att["image"]), "from": 1}])
    proc = writer.commit(att)
    assert proc.returncode == 69, shown(proc)
    assert ended_with(proc, "LR004"), shown(proc)
    commits, after = writer.commit_calls(), writer.after_commit()
    assert len(commits) == 1, f"{len(commits)} commit calls: LR004 is never sent again (R02)"
    assert len(after) == 1 and "render_file(" in after[0]["sent"], (
        f"not one re-read of the bases from SQL after the commit call: {after}")
    write_id = att["keys"]["write_id"]
    assert f"LR004 on write {write_id}" in proc.stderr, shown(proc)
    assert "equals SQL's" in proc.stderr and "proof: lanes/LANES.md renders" in proc.stderr, (
        f"the 69 does not name the entry and LR004's own message:\n{shown(proc)}")
    assert state(pg) == before, "a write refused LR004 changed the register"


@pytest.mark.parametrize("case", ["missing", "not-a-string", "not-a-time"])
def test_an_entry_without_a_valid_not_after_is_refused(pg, tmp_path, case):
    """Lane 1's v2.3 (TP:4536-4541): an entry with no `not_after`, and one whose
    `not_after` is not a string, are each LR004; one whose `not_after` is not a
    time is 22007, so 69 at once. On an operator entry first, a `rollback` entry
    by a direct call, then on a `write` entry through `register commit`, whose
    `not_after` the shim rewrites."""
    rewrite = {"missing": {}, "not-a-string": {"value": 1893456000},
               "not-a-time": {"value": "not a time"}}[case]
    code = "22007" if case == "not-a-time" else "LR004"
    n, writer = lr4_writer(pg, tmp_path)
    before = state(pg)
    operator = rollback_entry()
    if case == "missing":
        del operator["not_after"]
    else:
        operator["not_after"] = rewrite["value"]
    refused(commit_call(pg, n, operator), code, f"a rollback entry whose not_after is {case}")
    assert state(pg) == before, f"a rollback entry whose not_after is {case} changed the register"
    att = writer.attempt("not-after", "lanes/LANES.md", lr4_change)
    writer.arm([{"mode": "edit-entry", "match": "commit_write", "field": "not_after", **rewrite}])
    lr4_refused(pg, writer, att, before, code, f"a write entry whose not_after is {case}")


def test_an_import_carries_not_after_of_its_330_s_timer_plus_2_s(pg, tmp_path):
    """An import's `not_after` (phase N; D9's `import` row; lane 1's v2.6):
    `lanes-index import --at <C>` (T115) of a fixture register, as the operator
    lane (`LANES_LANE`, D24), through the shim, whose log holds each of its
    commit calls' entries: each entry's
    `not_after` is more than 300 s after the import's journal row's `utc`, and
    at most 332 s after it, both on the database's clock. `utc` is whole seconds
    (its CHECK), so "at most 332 s" is read as less than 333 s. A writer's bound
    would put it at most 10 s after. `W` is a directory of its own
    (`LANES_WORKSPACE_ROOT`, `lanes-edit.sh`'s test seam), since the import
    refuses a `LANES_REPO` that is `W` or a `W` it cannot read."""
    work, commit = workspace_at(tmp_path, [])
    w = tmp_path / "W"
    w.mkdir()
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "psql").write_text(PSQL_SHIM, encoding="utf-8")
    (shim / "psql").chmod(0o755)
    (shim / PSQL_SHIM_CONTROL).write_text(json.dumps({"psql": pg.psql_bin, "arms": []}),
                                          encoding="utf-8")
    env = index_env(tmp_path, config(tmp_path, pg, mode="index"), LANES_REPO=str(work),
                    LANES_WORKSPACE_ROOT=str(w), LANES_LANE=LANE, LANES_WORKSTATION=WS,
                    **OPERATOR_GIT, PATH=f"{shim}{os.pathsep}{os.environ.get('PATH', os.defpath)}")
    proc = run_index(LANES_INDEX, ["import", "--at", commit], env, cwd=work)
    assert proc.returncode == 0, shown(proc)
    log = [json.loads(line) for line in
           (shim / PSQL_SHIM_LOG).read_text(encoding="utf-8").splitlines()]
    sent = [e["sent"] for e in log if e.get("kind") != "version" and "commit_write(" in e["sent"]]
    assert sent, "the shim's log holds no commit call of the import"
    utc = float(sql(pg, f"SELECT extract(epoch FROM utc) FROM {SCHEMA}.journal "
                        f"WHERE kind = 'import' ORDER BY seq DESC LIMIT 1;"))
    for text in sent:
        found = re.findall(r'"not_after"\s*:\s*"([^"]+)"', text)
        assert len(found) == 1, f"the commit call carries {len(found)} not_after: {text[:600]}"
        stamp = found[0].replace("Z", "+00:00")
        epoch = datetime.datetime.fromisoformat(stamp).timestamp()
        assert 300 < epoch - utc < 333, (
            f"the import's not_after {found[0]} is {epoch - utc:.1f} s after its journal "
            f"row's utc, not more than 300 s and at most 332 s (330 s timer plus 2 s)")


@pytest.mark.parametrize("case", ["write-edits-store", "operator-edits-other",
                                  "operator-edits-nothing"])
def test_the_operator_flag_rules_refuse_lr004(pg, tmp_path, case):
    """The operator flag's rules (F2, D24): a `write` entry that edits
    `lanes/STORE`, through `register commit` with the shim's rewrite; an
    operator entry, a `rollback`, that edits a path besides `lanes/STORE`; and
    one that edits nothing, each by a direct call. Each is LR004, and nothing is
    written."""
    if case == "write-edits-store":
        _n, writer = lr4_writer(pg, tmp_path)
        before = state(pg)
        att = writer.attempt("store", "lanes/LANES.md", lr4_change)
        writer.arm([lr4_arm("write-edits-store", att["image"])])
        lr4_refused(pg, writer, att, before, "LR004", case)
        return
    n = bring_to_primary(pg)
    lines = [*DEFAULT_FILES["lanes/LANES.md"], "t231: an operator's line"]
    if case == "operator-edits-other":
        body = rollback_entry(edits=[{"ord": 1, "op": "remove", "path": "lanes/STORE"},
                                     {"ord": 2, "op": "append", "path": "lanes/LANES.md",
                                      "new_text": lines[-1]}])
        want = "edits lanes/STORE alone"
    else:
        body = rollback_entry(edits=[], files=[])
        want = "with no edit"
    before = state(pg)
    message = refused(commit_call(pg, n, body), "LR004", case)
    assert want in message, message
    assert state(pg) == before, f"{case}: the register changed"


def test_a_file_without_a_final_newline_renders_back_byte_identical(pg, tmp_path):
    """The fixture's `lanes/aliases.tsv` has no final newline. As imported it
    renders back byte for byte (`render_file`), and the scratch tree `register
    snapshot --tree` builds holds it so; a write through `register commit` that
    replaces its last line keeps it so: `journal_files.final_newline` is false
    at that seq, and it renders back as the write's image, with no final LF."""
    _n, writer = lr4_writer(pg, tmp_path)
    path = "lanes/aliases.tsv"
    imported = file_bytes(LR4_ALIASES, final_newline=False)
    shown_now = sql(pg, f"SELECT encode({SCHEMA}.render_file('{path}'), 'hex');", WRITER)
    assert bytes.fromhex(shown_now) == imported, f"{path} renders as {bytes.fromhex(shown_now)!r}"
    new_row = f"Lane-Old\t{LANE}\t2026-11-10T10:00:00Z"
    att = writer.attempt("no-newline", path, lambda old: old.replace(
        LR4_ALIASES[-1].encode("utf-8"), new_row.encode("utf-8")))
    assert att["old"] == imported, f"the scratch tree's {path} is {att['old']!r}, not {imported!r}"
    assert not att["image"].endswith(b"\n"), att["image"]
    proc = writer.commit(att)
    assert proc.returncode == 0 and re.fullmatch(r"committed ([0-9]+)\n", proc.stdout), shown(proc)
    seq = int(proc.stdout.split()[1])
    row = sql(pg, f"SELECT final_newline FROM {SCHEMA}.journal_files WHERE seq = {seq} "
                  f"AND path = '{path}';")
    assert row == "f", f"journal_files.final_newline at seq {seq} is {row!r}, not false"
    shown_now = sql(pg, f"SELECT encode({SCHEMA}.render_file('{path}'), 'hex');", WRITER)
    assert bytes.fromhex(shown_now) == att["image"], (
        f"{path} renders as {bytes.fromhex(shown_now)!r}, not the write's {att['image']!r}")


# =================================================================== T112's empty change set
#: T112's words for an attempt whose `changes.tsv` names no path (B15
#: tasks:427, "An empty change set"; lane 3, #165 6808937880, batch e Q88).
EMPTY_REFUSAL = "changes.tsv names no path; nothing was sent"


def test_an_entry_without_a_path_in_changes_tsv_is_refused_2_before_the_store_opens(pg, tmp_path):
    """An empty change set (B15 tasks:427; lane 3, #165 6808937880, batch e Q88;
    lane 1, #165 6808595488): an attempt whose `changes.tsv` and `files` are
    empty, with no `images/`, and whose snapshot, scratch tree, `msg`, `author`
    and `not_after` are a write's, is refused by `register commit` with 2,
    "changes.tsv names no path; nothing was sent", before the store opens: no
    `psql` runs for it, its `--version` probe included; stdout is empty; and
    every table of section 1.2 equals its value before, so there is no journal
    row and no seq. The seam sends no empty change set (Y:5060), so only a
    broken one leaves this attempt. The refusal is the CLI arm's alone, whose
    entry is always a `write`: T324's `stray-revert` and an `import --single`
    that changes no render-set path build their entries with no edits
    in-process, and still journal, as T271's revert cases prove.

    Fails until lane 1's T112 follow-up for Q88: on `refs/l1/V-round5` the
    attempt directory parses, and the write entry with no edit commits."""
    n = bring_to_primary(pg)
    writer = Writer(pg, tmp_path / "writer")
    before = state(pg)
    att = writer.empty_attempt("empty")
    seen = len(writer.shim_lines())
    proc = writer.commit(att)
    assert proc.returncode == 2, (
        f"register commit did not refuse an empty change set with 2, which fails until "
        f"T112's refusal (B15 tasks:427; lane 3, #165 6808937880, batch e Q88):\n{shown(proc)}")
    assert EMPTY_REFUSAL in proc.stderr, (
        f"the 2 does not say {EMPTY_REFUSAL!r} (B15 tasks:427):\n{shown(proc)}")
    assert proc.stdout == "", f"a refusal of an empty change set prints nothing:\n{shown(proc)}"
    ran = writer.shim_lines()[seen:]
    assert ran == [], (
        f"register commit ran psql {len(ran)} time(s) for an empty change set, so the store "
        f"opened; the refusal comes before it: {ran}")
    assert head(pg) == n, f"the head moved from {n} to {head(pg)}: an empty change set took a seq"
    assert state(pg) == before, "an empty change set changed the register"


# =================================================================== a write's files rows
#: Lane 3's ruling 5 on spec#17's re-review r4, its BLOCKING 3 (#165 6878977318):
#: `journal_files.path` takes data-model.md's constraint, a render-set path or
#: `lanes/STORE`, and a `write`'s, an `import`'s and a `stray-import`'s `files`
#: rows equal the distinct set of their edited paths and `to_path`s. Each case's
#: one more row: absent, at a path outside the render set that the register has
#: no file at; or present, at `lanes/aliases.tsv`, which the write does not edit,
#: with the file's own digest and final newline. Step 8's proof passes each as it
#: stands (an absent row for no file, a present row that renders to its digest),
#: so only the ruling's check refuses it.
FILES_ROW_CASES = {
    "outside-the-render-set": {"path": "lanes/notes.md", "present": False, "sha256": None,
                               "final_newline": None},
    "untouched-file": {"path": "lanes/aliases.tsv", "present": True,
                       "sha256": rendered(LR4_ALIASES, False), "final_newline": False},
}


@pytest.mark.parametrize("case", list(FILES_ROW_CASES))
def test_a_write_with_a_files_row_for_a_path_it_does_not_edit_is_refused_lr004_at_commit(pg, case):
    """A `write` entry by hand (`lr4_body`: it replaces `lanes/LANES.md`'s line 2,
    with that path's one `files` row), with one more `files` row, is refused at
    its commit with LR004, and nothing changes: every table of section 1.2 equals
    its value before (lane 3's ruling 5, #165 6878977318; AT-LR4 and T231):

      * `[outside-the-render-set]`: a row for `lanes/notes.md`, outside the
        render set (`lanes/LANES.md`, `lanes/aliases.tsv`, `lanes/archive/*.md`
        and `lanes/log/*.md`) and not `lanes/STORE`;
      * `[untouched-file]`: a row for `lanes/aliases.tsv`, a render-set file of
        AT-LR4's fixture that the write does not edit.

    A direct call, as the operator entry's case: the refusal is T107's
    `commit_write`, which fails until lane 1 adds it; on line R's merge106 the
    entry commits."""
    n = bring_to_primary(pg, LR4_FILES, no_newline=LR4_NO_NEWLINE)
    body = lr4_body()
    extra = FILES_ROW_CASES[case]
    body["files"] = [*body["files"], extra]
    before = state(pg)
    refused(commit_call(pg, n, body), "LR004", f"a write with a files row for {extra['path']}")
    assert head(pg) == n, f"{case}: the head moved from {n} to {head(pg)}"
    assert state(pg) == before, f"{case}: a refused write changed the register"


# =================================================================== a stray-revert's files rows
#: Spec#17's re-review r5, its finding 10 (lane 3's ruling, commit 22 `4d00a20b`'s
#: W3; design:1545, :2058 and :2065): a `stray-revert` is edit-free, and its
#: `files` rows name the paths the renderer restores, never `lanes/STORE`, which
#: is not a rendered path (F2). The row is `lanes/STORE` as AT-LR4's fixture holds
#: it after the cutover: present, with its own digest and final newline. Step 8's
#: proof passes it as it stands, and the CHECK and the render-set check take
#: `lanes/STORE`, so only the stray-revert's own check refuses it.
STRAY_REVERT_STORE_ROW = {"path": "lanes/STORE", "present": True,
                          "sha256": rendered(STORE_LINES), "final_newline": True}


def test_a_stray_revert_with_a_files_row_for_lanes_store_is_refused_lr004_at_commit(pg):
    """A `stray-revert` entry by hand, as AT-MIR's stray-revert case sends one (no
    edits, and the stray's sha as `git_commit`, which the journal's CHECK asks of
    a stray kind), with one `files` row, `lanes/STORE`, present with its own
    digest, is refused at its commit with LR004 naming `lanes/STORE`, and nothing
    changes: every table of section 1.2 equals its value before (spec#17's
    re-review r5, its finding 10; AT-LR4 and T231). The premise is checked first:
    `lanes/STORE` renders to the row's digest, so no proof LR004 can stand in.

    A direct call, as T231f's case: the refusal is T107's `commit_write`, step 8's
    stray-revert check (design:2065), which fails until lane 1's T107 follow-up
    adds it; on line R's merge106 the entry commits."""
    n = bring_to_primary(pg, LR4_FILES, no_newline=LR4_NO_NEWLINE)
    row = STRAY_REVERT_STORE_ROW
    renders = sql(pg, f"SELECT encode(sha256({SCHEMA}.render_file('lanes/STORE')), 'hex');",
                  WRITER)
    assert renders == row["sha256"], (
        f"the premise: lanes/STORE renders {renders!r}, not the row's {row['sha256']}")
    body = entry("stray-revert", "render --revert", journal={"git_commit": SHA_B}, files=[row])
    before = state(pg)
    message = refused(commit_call(pg, n, body), "LR004",
                      "a stray-revert with a files row for lanes/STORE")
    assert "lanes/STORE" in message, f"LR004, but not for lanes/STORE: {message}"
    assert head(pg) == n, f"the head moved from {n} to {head(pg)}"
    assert state(pg) == before, "a refused stray-revert changed the register"


# =================================================================== a final newline's change
#: Lane 3's ruling 3 on lane 1's #165 6882354358 (6885378657), as spec#17's re-review r9
#: and its delta review 7i sharpened it (lane 3's commit 27 `07a40aef`; design:1604-1605,
#: :2058 and :2065 at a227bea9): a change of only a file's final newline is an edit. So
#: step 8's third check takes, for a `write` or a `stray-import`, a present `files` row for
#: a path the entry does not edit, when that path is a render-set path other than
#: `lanes/STORE`, already in `files`, whose `final_newline` differs from the stored one; a
#: `lanes/STORE` row with no edit stays LR004, since only cutover and rollback may name it.
#: AT-LR4's fixture stores `lanes/aliases.tsv` with no final newline and `lanes/STORE` with
#: one, so each case's row flips its path's stored `final_newline`, with the digest of the
#: file so rendered. No `import` form, since an import empties `files` first (design:1725),
#: and no `stray-revert` form, since a stray revert is outside the third check (TP:4642).
FINAL_NEWLINE_FORMS = ("write", "stray-import")
#: Step 8's third check's message (design:2065).
NOT_EDITED = "a files row names a path the entry does not edit"


def files_row(db, path: str):
    """`path`'s `files` row, whole, or None where `files` holds no such path."""
    out = sql(db, f"SELECT to_jsonb(f) FROM {SCHEMA}.files f WHERE f.path = {sql_text(path)};")
    return json.loads(out) if out else None


def render_of(db, path: str) -> bytes:
    """`render_file(path)`'s bytes, as REGISTER-WRITER."""
    return bytes.fromhex(sql(db, f"SELECT encode({SCHEMA}.render_file({sql_text(path)}), 'hex');",
                             WRITER))


def journal_files_at(db, seq: int) -> list:
    """`journal_files`' rows at `seq`, each as an entry's `files` row, by path."""
    return json.loads(sql(db, (
        f"SELECT coalesce(jsonb_agg(jsonb_build_object('path', j.path, 'present', j.present, "
        f"'sha256', j.sha256, 'final_newline', j.final_newline) ORDER BY j.path), '[]') "
        f"FROM {SCHEMA}.journal_files j WHERE j.seq = {seq};")))


def flipped_row(path: str, lines, stored_final_newline: bool) -> dict:
    """A present `files` row for `path`, whose `lines` are stored with the final newline
    `stored_final_newline`: the opposite final newline, and the digest of the file so
    rendered."""
    return {"path": path, "present": True, "sha256": rendered(lines, not stored_final_newline),
            "final_newline": not stored_final_newline}


def final_newline_entry(form: str, row: dict) -> dict:
    """`[write]`: `lr4_body`'s write, with `row` as one more `files` row, for a path the
    write does not edit; `[stray-import]`: a `stray-import` entry whose only change is
    `row`'s, so it carries that one `files` row and no edit (TP:4642)."""
    if form == "write":
        body = lr4_body()
        body["files"] = [*body["files"], row]
        return body
    return entry("stray-import", "import --single", journal={"git_commit": SHA_B}, files=[row])


@pytest.mark.parametrize("form", FINAL_NEWLINE_FORMS)
def test_a_final_newline_only_change_on_a_render_set_path_commits(pg, form):
    """A change of only `lanes/aliases.tsv`'s final newline, a render-set path in
    `files` that the entry does not edit, commits (lane 3's ruling 3; spec#17's
    re-review r9, its first and second BLOCKING findings; AT-LR4 and T231, TP:4642):

      * `[write]`: `lr4_body`'s write with one more `files` row, `lanes/aliases.tsv`,
        present, its `final_newline` the opposite of the stored one and its digest
        that of the file so rendered;
      * `[stray-import]`: a `stray-import` entry whose only change is that file's
        final newline, with that one `files` row and no `journal_edits` row.

    Each commits: the head moves on by one seq; `journal_files` holds the row exactly
    as sent; `files` holds its `final_newline` as sent, its `sha256` as the row's
    digest and its `last_seq` as the new seq; and `render_file` gives the file's bytes
    before with only the final newline added, hashing to that digest. The premise is
    checked first: the fixture stores the file with no final newline, and it renders so.

    A direct call, as T231f's case: the exception is T107's `commit_write`, step 8's
    third check (design:2065), which fails until lane 1's T107 follow-up for ruling 3;
    before it, the row takes the third check's LR004."""
    n = bring_to_primary(pg, LR4_FILES, no_newline=LR4_NO_NEWLINE)
    path = "lanes/aliases.tsv"
    old = file_bytes(LR4_ALIASES, final_newline=False)
    stored = files_row(pg, path)
    assert stored is not None and stored["final_newline"] is False and render_of(pg, path) == old, (
        f"the premise: {path} is stored with no final newline and renders {old!r}: {stored}")
    row = flipped_row(path, LR4_ALIASES, stored_final_newline=False)
    seq = committed(pg, n, final_newline_entry(form, row),
                    f"a {form} whose only change to {path} is its final newline")
    assert seq == n + 1 and head(pg) == n + 1, f"the head is {head(pg)} and the seq {seq}, not {n + 1}"
    sent = [r for r in journal_files_at(pg, seq) if r["path"] == path]
    assert sent == [row], f"journal_files at seq {seq} holds {sent} for {path}, not {row}"
    now = files_row(pg, path)
    assert (now["final_newline"], now["sha256"], now["last_seq"]) == (True, row["sha256"], seq), (
        f"files holds {now} for {path}, not final_newline true, sha256 {row['sha256']} "
        f"and last_seq {seq}")
    want = old + b"\n"
    shown_now = render_of(pg, path)
    assert shown_now == want and hashlib.sha256(shown_now).hexdigest() == row["sha256"], (
        f"{path} renders {shown_now!r}, not {want!r} with the digest {row['sha256']}")


@pytest.mark.parametrize("form", FINAL_NEWLINE_FORMS)
def test_a_final_newline_only_change_to_lanes_store_is_refused_lr004_at_commit(pg, form):
    """The same two entries with the row for `lanes/STORE` in place of
    `lanes/aliases.tsv`: present, its `final_newline` flipped and its digest that of
    `lanes/STORE` so rendered. Each is refused at its commit with LR004 at step 8's
    third check, "a files row names a path the entry does not edit", and nothing
    changes: every table of section 1.2 equals its value before, since only cutover
    and rollback, the operator entries, may name `lanes/STORE` (spec#17's re-review r9
    and its delta review 7i, each its first BLOCKING finding; AT-LR4 and T231,
    TP:4642). The premise is checked first: the cutover stored `lanes/STORE` with a
    final newline, and it renders so.

    A direct call, as T231f's case. Lane 1's follow-up for ruling 5 already refuses
    the row, so the case guards that ruling 3's exception keeps `lanes/STORE` out:
    with commit 26's third check, which had no such exclusion, each entry commits."""
    n = bring_to_primary(pg, LR4_FILES, no_newline=LR4_NO_NEWLINE)
    path = "lanes/STORE"
    old = file_bytes(STORE_LINES)
    stored = files_row(pg, path)
    assert stored is not None and stored["final_newline"] is True and render_of(pg, path) == old, (
        f"the premise: {path} is stored with a final newline and renders {old!r}: {stored}")
    row = flipped_row(path, STORE_LINES, stored_final_newline=True)
    before = state(pg)
    message = refused(commit_call(pg, n, final_newline_entry(form, row)), "LR004",
                      f"a {form} whose only change to {path} is its final newline")
    assert NOT_EDITED in message, f"LR004, but not step 8's third check's: {message}"
    assert head(pg) == n, f"the head moved from {n} to {head(pg)}"
    assert state(pg) == before, f"a refused {form} changed the register"


# =================================================================== a stray revert's proof
#: Spec#17's re-review r10, its one BLOCKING finding (lane 3's ruling, commit 28 `6450dce2`;
#: design:1545, :2058 and :2065 at a227bea9): a stray revert's `files` rows prove the
#: register's current truth and never change it. Step 8's fourth check, before the loop
#: and so before any `journal_files` insert, refuses with LR004 a present row whose path is
#: not in `files`, or whose `final_newline` or `sha256` is not its path's stored one, and a
#: row whose `present` is null. Each case is one row, on AT-LR4's fixture, which stores
#: `lanes/aliases.tsv` with no final newline (TP:4642):
STRAY_REVERT_ROW_CASES = {
    # present, its final newline flipped, with the digest of the file so rendered
    "changed-final-newline": {"path": "lanes/aliases.tsv", "present": True,
                              "sha256": rendered(LR4_ALIASES, True), "final_newline": True},
    # present, with no final newline given and the stored digest
    "null-final-newline": {"path": "lanes/aliases.tsv", "present": True,
                           "sha256": rendered(LR4_ALIASES, False), "final_newline": None},
    # present, a render-set path that `files` does not hold, with a digest
    "absent-path": {"path": "lanes/archive/absent.md", "present": True,
                    "sha256": rendered(["# absent"]), "final_newline": True},
    # `present` null, with the stored digest and final newline
    "null-present": {"path": "lanes/aliases.tsv", "present": None,
                     "sha256": rendered(LR4_ALIASES, False), "final_newline": False},
    # `present` false, for a path in `files` (spec#17's re-review r11; lane 3's commit 29)
    "present-false-existing-path": {"path": "lanes/aliases.tsv", "present": False,
                                    "sha256": None, "final_newline": None},
}
#: The fourth check's message, in the words commits 28 and 29 share (design:2065).
WOULD_CHANGE = "a stray-revert files row would change the register"
#: Spec#17's re-review r11 and Codex's delta review 7k of commit 28 (lane 3's commit 29
#: `a227bea9`): the fourth check also refuses, before the loop, a present-false row for a
#: path in `files`. Spec#17's re-review r12 asks that `[present-false-existing-path]`
#: assert that check's own message, never the loop's later "proof: % is present"
#: (design:2077-2078). This is the message at a227bea9's design:2065, kept as one constant
#: for lane 3's commit 30, which states the message, to restate if its words change.
PRESENT_FALSE_REFUSAL = (
    "a stray-revert files row would change the register: a present row must equal the "
    "stored final_newline and sha256 of its path, a row with present false must name a path "
    "not in files, and present may not be null")
#: The ids that assert the fourth check's whole message, in place of `WOULD_CHANGE`.
STRAY_REVERT_OWN_MESSAGE = {"present-false-existing-path": PRESENT_FALSE_REFUSAL}
#: Codex's delta review 7j of commit 27, its item 4 (lane 3's commit 28; TP:4642): the
#: valid equal proof. Its present row equals `lanes/aliases.tsv`'s stored `final_newline`
#: and digest; its present-false row names `lanes/archive/stray.md`, a render-set path not
#: in `files`, as a file the stray added and the revert removes.
STRAY_REVERT_PROOF_ROWS = (
    {"path": "lanes/aliases.tsv", "present": True, "sha256": rendered(LR4_ALIASES, False),
     "final_newline": False},
    {"path": "lanes/archive/stray.md", "present": False, "sha256": None, "final_newline": None},
)


def stray_revert(*rows) -> dict:
    """A `stray-revert` entry by hand, as AT-MIR's stray-revert case sends one (no
    edits, and the stray's sha as `git_commit`, which the journal's CHECK asks of a
    stray kind), with `rows` as its `files`."""
    return entry("stray-revert", "render --revert", journal={"git_commit": SHA_B},
                 files=list(rows))


@pytest.mark.parametrize("case", list(STRAY_REVERT_ROW_CASES))
def test_a_stray_revert_files_row_that_would_change_the_register_is_refused_lr004_at_commit(
        pg, case):
    """A `stray-revert` entry whose one `files` row would change the register is
    refused at its commit with LR004 at step 8's fourth check, "a stray-revert files
    row would change the register", and nothing changes: every table of section 1.2
    equals its value before (spec#17's re-review r10; lane 3's ruling, commit 28;
    AT-LR4 and T231, TP:4642):

      * `[changed-final-newline]`: `lanes/aliases.tsv`, present, its `final_newline`
        the opposite of the stored one and its digest that of the file so rendered;
      * `[null-final-newline]`: the same path, present, its `final_newline` null and
        its stored digest;
      * `[absent-path]`: `lanes/archive/absent.md`, a render-set path not in `files`,
        present, with a digest;
      * `[null-present]`: `lanes/aliases.tsv` with `present` null;
      * `[present-false-existing-path]`: `lanes/aliases.tsv`, a path in `files`, with
        `present` false and a null digest and `final_newline` (spec#17's re-review
        r11; lane 3's commit 29). Its LR004 must carry the fourth check's whole
        message, `PRESENT_FALSE_REFUSAL` (spec#17's re-review r12), and not the
        loop's own "proof: lanes/aliases.tsv is present", which comes after the
        `journal_files` insert.

    The premise is checked first: `files` holds `lanes/aliases.tsv` with no final
    newline and its digest, and holds no `lanes/archive/absent.md`. The message tells
    the fourth check from the loop's own proof, whose LR004 `[absent-path]` and
    `[present-false-existing-path]` would otherwise meet.

    A direct call, as T231f's case: the refusal is T107's `commit_write`, step 8's
    fourth check (design:2065), which fails until lane 1's T107 follow-up for it.
    Before it, `[changed-final-newline]` commits, `[null-final-newline]` ends 23514
    and `[null-present]` 23502 at the loop's insert, and `[absent-path]` takes the
    loop's proof LR004."""
    n = bring_to_primary(pg, LR4_FILES, no_newline=LR4_NO_NEWLINE)
    row = STRAY_REVERT_ROW_CASES[case]
    stored = files_row(pg, row["path"])
    if row["path"] == "lanes/aliases.tsv":
        assert stored is not None and (stored["final_newline"], stored["sha256"]) == (
            False, rendered(LR4_ALIASES, False)), f"the premise: {row['path']} is stored as {stored}"
    else:
        assert stored is None, f"the premise: files holds no {row['path']}, but holds {stored}"
    before = state(pg)
    message = refused(commit_call(pg, n, stray_revert(row)), "LR004",
                      f"a stray-revert's {case} row for {row['path']}")
    own = STRAY_REVERT_OWN_MESSAGE.get(case)
    assert (message == own) if own else (WOULD_CHANGE in message), (
        f"LR004, but not step 8's fourth check's own message: {message}")
    assert head(pg) == n, f"{case}: the head moved from {n} to {head(pg)}"
    assert state(pg) == before, f"{case}: a refused stray-revert changed the register"


def test_a_stray_revert_files_row_that_proves_the_register_commits(pg):
    """The valid equal proof (Codex's delta review 7j of commit 27, its item 4; lane
    3's commit 28; AT-LR4 and T231, TP:4642): a `stray-revert` entry with two `files`
    rows, `lanes/aliases.tsv`, present, with its stored `final_newline` and digest,
    and `lanes/archive/stray.md`, present false, a render-set path not in `files`, as
    a file the stray added and the revert removes, commits. The head moves on by one
    seq and `journal` gains the entry; `journal_files` holds both rows exactly as
    sent; `files` holds `lanes/aliases.tsv` with its `final_newline` and `sha256`
    unchanged and its `last_seq` the new seq, as TP:4642 words it, holds no
    `lanes/archive/stray.md`, and its other rows are unchanged; `doc_lines` is
    unchanged; and `render_file('lanes/aliases.tsv')` is byte for byte as before and
    hashes to the stored digest. The premise is checked first.

    A direct call, as T231f's case. It passes on T107's `commit_write` before the
    fourth check, and must keep passing with it, which it guards against refusing a
    row that proves the register."""
    n = bring_to_primary(pg, LR4_FILES, no_newline=LR4_NO_NEWLINE)
    proof, gone = STRAY_REVERT_PROOF_ROWS
    path = proof["path"]
    old = file_bytes(LR4_ALIASES, final_newline=False)
    stored = files_row(pg, path)
    assert stored is not None and (stored["final_newline"], stored["sha256"]) == (
        proof["final_newline"], proof["sha256"]) and render_of(pg, path) == old, (
        f"the premise: {path} is stored as {stored} and renders {old!r}")
    assert files_row(pg, gone["path"]) is None, f"the premise: files holds no {gone['path']}"
    before, journal_before = state(pg), journal_of(pg)
    seq = committed(pg, n, stray_revert(proof, gone), "a stray-revert whose rows prove the register")
    assert seq == n + 1 and head(pg) == n + 1, f"the head is {head(pg)} and the seq {seq}, not {n + 1}"
    journal_now = journal_of(pg)
    assert journal_now[:-1] == journal_before and journal_now[-1][:2] == [seq, "stray-revert"], (
        f"the journal went from {journal_before} to {journal_now}")
    rows = journal_files_at(pg, seq)
    assert rows == sorted([proof, gone], key=lambda r: r["path"]), (
        f"journal_files at seq {seq} holds {rows}, not the two rows as sent")
    now = files_row(pg, path)
    assert (now["final_newline"], now["sha256"], now["last_seq"]) == (
        stored["final_newline"], stored["sha256"], seq), (
        f"files holds {now} for {path}, not {stored} with last_seq {seq}")
    assert files_row(pg, gone["path"]) is None, f"files now holds {gone['path']}"
    after = state(pg)
    assert [f for f in after["files"] if f["path"] != path] == [
        f for f in before["files"] if f["path"] != path], "a proving stray-revert changed files"
    assert after["doc_lines"] == before["doc_lines"], "a proving stray-revert changed doc_lines"
    shown_now = render_of(pg, path)
    assert shown_now == old and hashlib.sha256(shown_now).hexdigest() == proof["sha256"], (
        f"{path} renders {shown_now!r}, not {old!r}")
