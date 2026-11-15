# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 2 (AT-2; opensoft/openRepoTools#165): a register write
exits 69 when the database is unreachable, with nothing written.

THIS MODULE holds test 2's storage-layer case, phase N (the test plan's
section 1.3; lane 2's T210):
`test_the_storage_layer_entry_exits_69_when_the_database_is_unreachable`;
and test 2's per-verb cases, its refused transactions, its partial failures
and S1's other tests, phase W, lane 2's T241 (see "phase W: T241" below),
with lane 3's reading 3 of T112, an image holding a CR or a NUL refused with
2 by `register commit`, and lane 3's Q35, `request-handoff`'s refusals before
its claim, 64 and never 2 (T241d).

THE STORAGE-LAYER ENTRY is the managed projection writer's (design S4), driven
by the fake writer AT-1's part N drives it with,
`test_sql_register_render.py`'s `projection_entry`: one attempt of S1's loop,
`register snapshot --write-id new ... --tree <dir> --checkout <c>` (contract
section 3.2), then, on 0 alone, the attempt directory and `register commit`
(section 3.3), as the verb `managed-projection`.

WHY THE 69 IS THE SNAPSHOT'S. With the database unreachable, the entry's first
call is a read, and a read that cannot reach its database is 69 (contract
section 2.7, "On a read"; section 3.2's exits; AT-2's outcome table, "no
connection at the first snapshot is 69"). `register commit` against an
unreachable database is 3, in doubt, never 69 (section 2.7, CO-5 and CO-6;
lane 1's T112 builds it so), so the entry never reaches it: the writer
abandons on a snapshot's 69 (section 3.3, "The caller's map"). The case fails
until L1-A9 (lane 1's T111, `register snapshot`) lands, and, for the flipped
copy, L1-A4 (T105's constant).

THE FAULT, WITH NO ENGINE (AT-2's "Unreachable"): the configuration's
`register_url=` names a fresh, empty socket directory, and the `psql` first on
`PATH` is T203's register fake, which since T203b answers T106's `psql
--version` itself with 16.4 (logged as its own kind, and left out of
`fake_calls`), and every call that carries a request with `psql`'s own exit 2
and its "connection to server ... failed" text, as the real `psql` answers an
empty socket directory. The fake's log is the oracle for what reached the store:
one call, the snapshot's, with no `commit_write` in it, the configured
password file and no `PGPASSWORD`, and no call after it (no retry that reads
as a write, and no fallback). With no request that reached a database, the
register's rows and the journal are unchanged; on the real engine, the
per-verb cases (T241) read them back by digest.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest

from conftest import WINDOWS_SKIP
from pgcluster import Database
from sql_register_helpers import PSQL_SHIM, PSQL_SHIM_CONTROL, PSQL_SHIM_LOG
from test_sql_register_render import (AUTHOR, DOT, EM, LOGIN_READER, LOGIN_WRITER, SCHEMA, SEED,
                                      SID_A1, SID_A2, TIP, WRITER, WS, Estate, _canonical_rows,
                                      ensure_logins, fake_calls, fake_psql_dir,
                                      flipped, git, import_to_primary, index_env, primary_config,
                                      projection_entry, rows, run_index, sql, workspace)

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280; `tests/sql_register_gate.py` reads it, and
#: T281 removes it in the last set): the tasks each id of this module waits
#: for, by T210's and T241's Orders (tasks.md at 204145ae), keyed by function
#: or by one id, with T241's As built for `[log]`. Lane 2's plan GP-24 wrote
#: it (task sets 12b's rule 11).
SQL_REGISTER_GATE_TABLE = {
    "test_a_failure_in_a_late_statement_leaves_journal_lines_and_head_unchanged": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_a_hand_edit_commit_is_refused_on_primary": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_a_pending_hand_edit_names_the_file_and_a_recovery_that_works": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_a_queued_handoff_commit_is_still_published": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_a_queued_lanes_commit_is_refused_as_a_divergence": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_a_refused_write_leaves_no_lock": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_a_write_goes_on_with_the_service_down": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_an_image_holding_a_cr_or_a_nul_is_refused_with_2_and_nothing_sent": ("T112",),  # T241; tasks:2324
    "test_each_direct_write_refuses_with_2_on_primary": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_each_write_exits_69_when_the_database_is_unreachable": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_each_write_exits_69_when_the_database_refuses_the_transaction": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_each_write_exits_69_when_the_switch_is_not_primary": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_request_handoff_refuses_64_never_2_on_primary": ("T413", "T414", "T415", "T420"),  # T241; tasks:2324
    "test_the_storage_layer_entry_exits_69_when_the_database_is_unreachable": ("T105", "T107", "T108", "T111", "T112", "T227", "T301"),  # T210; tasks:1951
    "test_a_failure_in_a_late_statement_leaves_journal_lines_and_head_unchanged[rename-lane]": ("T413", "T414", "T415", "T420", "T422"),  # T241; tasks:2324
    "test_a_refused_write_leaves_no_lock[rename-lane]": ("T413", "T414", "T415", "T420", "T422"),  # T241; tasks:2324
    "test_each_write_exits_69_when_the_switch_is_not_primary[log]": ("T412", "T413", "T414", "T415", "T417", "T420"),  # T241; tasks:2322
}

#: Contract section 2.2's argv, exactly.
PSQL_ARGV = ["--no-psqlrc", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-v",
             "VERBOSITY=verbose", "-v", "SHOW_CONTEXT=never"]

#: The writer's login and its password, which must never be printed.
WRITER_LOGIN = "lanes_w_t210"
SECRET = "t210-never-printed-0b5e"

#: The session `request-handoff --force` writes its `PAUSED` for (`--session`).
#: Without it the verb refuses with 2, naming no uuid (`lanes-edit.sh`'s
#: `requester_uuid`, at a2073eae:10691), before it reaches any SQL, so a case
#: that expects the write's own refusal or 69 would fail by that usage refusal.
SID_REQUESTER = "bbbbbbbb-0007-4000-8000-00000000b007"

#: What `_masked_path` keeps off a case's `PATH`: an installed `lanes-index`,
#: a real `psql`, and every `pg_` client that `postgresql-16` puts beside it.
_MASKED_NAMES = ("psql", "lanes-index")
_MASKED_PREFIX = "pg_"
#: `_masked_path`'s mirrors, built once per process: each masked directory's
#: real path, to its mirror under the one `l2-pathmask-` directory.
_PATH_MIRRORS: dict = {}
_PATH_MIRROR_ROOT: list = []


def _masked_path() -> str:
    """The caller's PATH with every directory kept, in its place, and each one
    that holds a masked name swapped for a mirror of it without them. A real
    `psql` or `pg_` client, or an installed `lanes-index`, is never what a
    case runs; but dropping the directory that holds one drops what sits
    beside it. On a GitHub runner, `postgresql-16`'s client package puts
    `psql` in `/usr/bin` together with `git` and `bash`, and `/bin` links
    there, so a filter that drops the directory leaves a case no `git` or
    `bash` to run. The mirror is a directory of symlinks, one per entry, each
    to the original entry's absolute path, the masked names left out. It is
    built once per process, keyed by the directory's real path, under one
    temporary directory that an `atexit` handler removes. A directory that
    holds no masked name passes through unchanged, so where no `PATH`
    directory holds one, the PATH is what the old filter gave; empty entries
    are left out, as that filter left them."""
    kept = []
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if not part:
            continue
        real = os.path.realpath(part)
        if real not in _PATH_MIRRORS:
            try:
                names = os.listdir(real)
            except OSError:
                names = []
            if not any(_is_masked(name) for name in names):
                kept.append(part)
                continue
            _PATH_MIRRORS[real] = _path_mirror(real, names)
        kept.append(_PATH_MIRRORS[real])
    return os.pathsep.join(kept)


def _is_masked(name: str) -> bool:
    return name in _MASKED_NAMES or name.startswith(_MASKED_PREFIX)


def _path_mirror(real: str, names: list) -> str:
    """`real`'s mirror: a new directory under the one `l2-pathmask-`
    directory, holding a symlink to each entry of `real` but the masked."""
    if not _PATH_MIRROR_ROOT:
        root = tempfile.mkdtemp(prefix="l2-pathmask-")
        atexit.register(shutil.rmtree, root, ignore_errors=True)
        _PATH_MIRROR_ROOT.append(root)
    mirror = tempfile.mkdtemp(prefix=(os.path.basename(real) or "root") + "-",
                              dir=_PATH_MIRROR_ROOT[0])
    for name in names:
        if not _is_masked(name):
            os.symlink(os.path.join(real, name), os.path.join(mirror, name))
    return mirror


def test_the_storage_layer_entry_exits_69_when_the_database_is_unreachable(tmp_path):
    """The storage-layer entry, called as AT-1's part N calls it, against a
    `register_url=` whose socket directory is fresh and empty: it exits 69,
    and stderr names the store and the error, `psql`'s own first line, which
    names the socket, with no credential and no URL. The fake's log holds one
    call, the snapshot's, sent with section 2.2's argv, as the configured
    login, with the configured password file and no `PGPASSWORD`, and
    carrying no `commit_write`; no call follows it. Nothing is written: no
    scratch tree, no attempt directory beyond it, and the lane checkout's
    HEAD, status, index and `origin/main` as they were (AT-2, "Unreachable
    (RE), the storage-layer entry"; the delta spec's "Unreachable or refused
    is exit 69 with nothing written")."""
    dead = tmp_path / "dead"
    dead.mkdir()
    socket = dead / ".s.PGSQL.5432"
    psql_error = (f'psql: error: connection to server on socket "{socket}" failed: '
                  f"No such file or directory")
    fake = fake_psql_dir(tmp_path / "fakebin", answers=[
        {"exit": 2, "stderr": psql_error + "\n\tIs the server running locally and accepting "
                                           "connections on that socket?\n"}])
    estate = Estate(tmp_path / "estate")
    copy = flipped(tmp_path)
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()
    passfile = conf_dir / "pgpass"
    passfile.write_text(f"*:*:*:{WRITER_LOGIN}:{SECRET}\n", encoding="utf-8")
    passfile.chmod(0o600)
    host = quote(dead.as_posix(), safe="")
    conf = primary_config(conf_dir / "lanes-index.conf",
                          f"postgresql://{WRITER_LOGIN}@{host}:5432/lanes_t210",
                          f"postgresql://lanes_r_t210@{host}:5432/lanes_t210", passfile)
    env = index_env(tmp_path, conf, estate.home, **fake)
    env["PATH"] = str(tmp_path / "fakebin") + os.pathsep + _masked_path()
    before = estate.state()

    done = projection_entry(copy, env, estate.checkout, tmp_path, "managed-projection",
                            "lanes-edit.sh managed-projection: test 2's storage-layer case")
    snap = done["snapshot"]
    said = snap.stdout + snap.stderr
    assert done["code"] == 69, (f"the storage-layer entry exited {done['code']}, not 69: "
                                f"{snap.stderr}")
    assert done["commit"] is None, "the entry went on to `register commit` after a 69"

    # THE ERROR AND THE STORE, WITHOUT CREDENTIALS (contract section 2.6).
    assert psql_error in snap.stderr, f"stderr does not carry psql's error: {snap.stderr!r}"
    assert SECRET not in said, "a password reached the output"
    assert not re.search(r"postgres(ql)?://", said), f"a URL reached the output: {said!r}"

    # WHAT REACHED THE STORE: the snapshot's one call, and nothing after it.
    calls = fake_calls(fake)
    assert len(calls) == 1, f"{len(calls)} psql calls reached the store, not one: {calls}"
    call = calls[0]
    assert call["argv"] == PSQL_ARGV, call["argv"]
    assert call["url"].startswith(f"postgresql://{WRITER_LOGIN}@"), call["url"]
    assert call["passfile"] == str(passfile) and call["pgpassword"] is False, call
    assert "commit_write" not in call["stdin"], "the snapshot's call carried a commit"

    # NOTHING WRITTEN: no scratch tree, and the lane checkout as it was.
    tree = done["attempt"] / "tree"
    assert not tree.exists() or not any(tree.iterdir()), "a scratch tree was built"
    assert not (done["attempt"] / "snapshot").exists()
    assert estate.state() == before, "the lane checkout changed"


# ============================================================ phase W: T241
#
# TEST 2'S REFUSALS AND ITS PARTIAL FAILURE (lane 2's T241; AT-2, the test
# plan's lines 646-781; FR-018, FR-019, FR-026, FR-059). Each of S1's writes
# runs as `lanes-edit.sh <verb>` on a `mode=primary` workstation, from the
# flipped copy (T203's, `RENDER_GIT_HALF = True`) with `lanes-edit.sh` beside
# it, so the verb's `lanes-index` is that copy (CLI4.5 section 6's copy rule).
#
# THE VERBS are S1's writes but `commit` (the test plan's line 750): the
# fourteen arms of `lanes-edit.sh`'s write dispatch at a2073eae (`:16537`),
# `commit` left out, whose direct write is 2 (D10). Each runs once, with the
# argument list `WRITE_VERBS` gives it; `log` runs once, as `log NOTED`.
#
# NO ENGINE (FP): the database unreachable, as a fake `psql` (T203's register
# fake, which answers T106's `--version` itself) that exits 2 with `psql`'s own
# "connection to server ... failed" text; D10's refusals; the queued commits;
# `request-handoff`'s 64s before its claim.
# REAL ENGINE (RE, on `pg`, skipped without PostgreSQL 16 by T205's banner):
# the switch not `primary`, the refused GRANTs, the late statement, the lock,
# the pending hand edit and the service down, each over test 1's imported
# register (`import_to_primary`, AT-LR006's route).
#
# They fail until lane 4's L4-B3 (T415's attempt loop), L4-B4 and L4-B11
# (T420, D10's refusals) land, each by its own assertion here: today's
# `lanes-edit.sh` writes the files whatever `mode=` says.
#
# R02 (lane 1, #165 6755590769; lane 3, 6755615338; F10-OWED items 35 and
# 37): after LR004, `register commit` re-reads once and never resends. No case
# here meets LR004; the refused-transaction and late-statement cases assert
# that a refused commit call is never sent again, so a resend under any
# refusal fails them. LR004's own cases are T221's (`lr004_on_an_edit`,
# `lr004_reloads_once`).
#
# LANE 3'S READING 3 OF T112 (#165 6755386771; F10-OWED item 31): the
# malformed-directory refusals are 2, with nothing sent. An image that holds a
# CR or a NUL is one, so its case below expects 2 and never 69; it needs no
# engine and no lane 4 code, and runs `register commit` directly.

def _with_row(lane: str, sid: str, cell: str, log: str = None) -> dict:
    """A prep: test 1's SEED with one more row in `LANES.md`'s table, after
    repoA-2's, and the lane's log (its header, then `log`'s lines)."""
    lanes = SEED["lanes/LANES.md"]
    anchor = next(line for line in lanes.split("\n") if line.startswith("| `repoA-2` |"))
    row = (f"| `{lane}` | harness `{sid}` | Eagle / test / brett | 2026-09-01T00:00Z | none "
           f"| handoffs/{lane}.md | {cell} |")
    header = f"# lane {lane} {EM} object log (lane-collision-protocol Amendment 7)\n"
    return {"lanes/LANES.md": lanes.replace(anchor + "\n", anchor + "\n" + row + "\n", 1),
            f"lanes/log/{lane}.md": header + (log or "")}


#: The starting state three verbs need, or they refuse for want of work (2):
#: `archive-rows <repo>` moves a repository's RETIRED rows; `retire-rows`
#: takes a dormant row, whose log has no lane-kind line and whose cell is not
#: a current state (`lanes-edit.sh:13316-13352` at a2073eae); and
#: `migrate-state-cells` migrates a diary cell, one that is not Amendment
#: 13(a)'s phrase. Each is committed and pushed before the case runs, and on
#: the real engine before the import.
PREPS = {
    "archive-rows": _with_row(
        "repoZ-2", "eeeeeeee-0002-4000-8000-00000000e002",
        f"RETIRED {DOT} 2026-09-03T00:00:00Z {DOT} retired",
        f"RETIRED {EM} lane repoZ-2, session eeeeeeee-0002-4000-8000-00000000e002@Eagle, "
        f"2026-09-03T00:00:00Z, lane:repoZ-2 {EM} retired\n"),
    "retire-rows": _with_row("repoA-4", "aaaaaaaa-0005-4000-8000-00000000a005",
                             f"MIGRATED {DOT} 2026-09-01T00:00:00Z {DOT} migrated"),
    "migrate-state-cells": _with_row("repoA-5", "aaaaaaaa-0006-4000-8000-00000000a006",
                                     f"parked 2026-09-01 {DOT} picked up 2026-09-02"),
}

#: S1's writes but `commit`: {verb: (its arguments, the lane it writes as)}.
#: The argument forms are `lanes-edit.sh`'s usage lines at a2073eae.
WRITE_VERBS = {
    "add-row": (["add-row", f"| `repoA-3` | harness `aaaaaaaa-0004-4000-8000-00000000a004` | "
                 f"Eagle / test / brett | 2026-11-10T00:00Z | none | handoffs/repoA-3.md | "
                 f"LIVE {DOT} 2026-11-10T00:00:00Z {DOT} test 2 |"], "repoA-2"),
    "append-line": (["append-line", f"HOLD {EM} lane repoA-2 ({WS}), window w, "
                     f"2026-11-10T00:00:00Z: opensoft/repoB main {TIP} for test 2"], "repoA-2"),
    "append-session-id": (["append-session-id", "repoA-2", f"harness `{SID_A2}`",
                           " (test 2)"], "repoA-2"),
    "archive-rows": (["archive-rows", "repoZ", "--yes"], "repoA-2"),
    "claim": (["claim", "opensoft/repoA#9", "--no-github"], "repoA-2"),
    "log": (["log", "NOTED", "lane:repoA-2", "test 2's write"], "repoA-2"),
    "migrate-state-cells": (["migrate-state-cells", "--yes"], "repoA-2"),
    "release": (["release", "opensoft/repoA#7", "test 2", "--no-github"], "repoA-1"),
    "rename-lane": (["rename-lane", "repoA-2", "repoA-3", "test 2", "--no-github"], "repoA-2"),
    "replace-in-row": (["replace-in-row", "repoA-2", "parked", "parked for test 2"], "repoA-2"),
    "request-handoff": (["request-handoff", "repoA-1", "--force", "test 2", "--session",
                         SID_REQUESTER], "repoA-2"),
    "retire-rows": (["retire-rows", "repoA-4", "--reason", "test 2"], "repoA-2"),
    "set-row-state": (["set-row-state", "repoA-2", f"PAUSED {DOT} test 2"], "repoA-2"),
}

#: P11's writes that change several files (the test plan's lines 653-656).
LATE_WRITES = {
    "LANDING": (["append-line", f"LANDING {EM} lane repoA-2, session {SID_A2}@{WS}, "
                 f"2026-11-10T00:00:00Z, PR #8 into opensoft/repoA main"], "repoA-2"),
    "LANDED": (["append-line", f"LANDED {EM} lane repoA-1, session {SID_A1}@{WS}, "
                f"2026-11-10T00:00:00Z, PR #7 into opensoft/repoA main {chr(0x2192)} "
                f"abc1234"], "repoA-1"),
    "rename-lane": WRITE_VERBS["rename-lane"],
    "retire-rows": WRITE_VERBS["retire-rows"],
    "archive-rows": WRITE_VERBS["archive-rows"],
    "migrate-state-cells": WRITE_VERBS["migrate-state-cells"],
}

#: EACH LATE WRITE'S LAST STRUCTURED ROW, AND HOW IT IS BROKEN (TP:686-690,
#: "its last structured row breaks a CHECK"; T241i): the `edit-entry` arm's
#: `field` and `value` for the last row of the last list the write's entry
#: carries, in the order `commit_write`'s step 7 applies them, `lanes`,
#: `log_lines`, `register_lines`, then `object_holds` (a2935aee:lanes-index:7282).
#: - A `LANDING` or `LANDED` that `append-line` writes changes `lanes/LANES.md`
#:   alone: one `register_lines` row (lane 4's TRIAGE-W12 run 2 logged
#:   LANDED's entry: `lanes`, `log_lines` and `object_holds` empty).
#: - `rename-lane`, `retire-rows` and `migrate-state-cells` end with the
#:   `log_lines` rows of the lines they add to a log.
#: - `archive-rows` writes `lanes/LANES.md` and the archive alone: its last
#:   row is the archived lane's `lanes` row.
#: The `register_lines` and `log_lines` rows lose their `workstation`, which
#: each table's primary CHECK requires (`mode = 'files' OR
#: coalesce(workstation, '') <> ''`, a2935aee:lanes-index:7122 and :7065); the
#: database stamps `mode`, so the row breaks it on primary alone. A `lanes`
#: row has no such CHECK, so it gets a `lane` that is not its key
#: (`lower(lane) = lane_key`, :7038).
LATE_ROWS = {
    "LANDING": ("register_lines.-1.workstation", ""),
    "LANDED": ("register_lines.-1.workstation", ""),
    "rename-lane": ("log_lines.-1.workstation", ""),
    "retire-rows": ("log_lines.-1.workstation", ""),
    "archive-rows": ("lanes.-1.lane", "t241i-not-its-key"),
    "migrate-state-cells": ("log_lines.-1.workstation", ""),
}

#: AT-3's line, which a writer prints where the switch is not `primary`.
NOT_PRIMARY_LINE = "this estate's register is SQL; configure `mode=primary`"

#: EACH WRITE LANE'S OWN CHECKOUT, `<c>` (T241e; B14 tasks:1142's T415
#: bullets; R17). On primary a write reads its pending hand edits, its author
#: and the snapshot's `repos.tsv` from the checkout of the lane it writes for,
#: `<W>-lanes/<lane>`, and refuses with nothing sent where that is not there
#: (2, or 64 for `request-handoff`), since a clone would be D12's fetch. The
#: lanes these writes are for (`lanes-edit.sh`'s `write_lane_of`): repoA-1 and
#: repoA-2, as `LANES_LANE` or a verb's `<lane>`, and repoA-3, `add-row`'s new
#: row. `PrimaryWorkstation` makes `<c>` for each, unless a case asks for none.
WRITE_LANES = ("repoA-1", "repoA-2", "repoA-3")


class PrimaryWorkstation:
    """A `mode=primary` workstation for `lanes-edit.sh`'s writes: the
    files-mode workspace of test 1's sync case (`workspace`), at C, the
    flipped copy with `lanes-edit.sh` beside it, and a `lanes-index.conf`
    whose `register_url=` and `reader_url=` name `urls`, or a fresh, empty
    socket directory, with a 0600 `register_passfile=`. `fakebin` is first on
    `PATH`. Each lane in `checkouts` gets `<c>`, its own checkout, a clone of
    origin made after the case's prep (`WRITE_LANES` by default)."""

    def __init__(self, tmp_path: Path, urls: tuple = None, fakebin: Path = None,
                 prep: dict = None, checkouts: tuple = WRITE_LANES):
        self.fakebin = fakebin or tmp_path / "fakebin"
        self.fakebin.mkdir(parents=True, exist_ok=True)
        self.estate, self.env, _source = workspace(tmp_path / "ws", self.fakebin)
        if prep:
            self._prep(prep)
        self.copy = flipped(tmp_path)
        self.lanes_edit = self.copy.parent / "lanes-edit.sh"
        conf_dir = tmp_path / "conf"
        conf_dir.mkdir()
        self.passfile = conf_dir / "pgpass"
        self.passfile.write_text(f"*:*:*:{WRITER_LOGIN}:{SECRET}\n", encoding="utf-8")
        self.passfile.chmod(0o600)
        self.dead = tmp_path / "dead"
        self.dead.mkdir()
        host = quote(self.dead.as_posix(), safe="")
        register_url, reader_url = urls or (
            f"postgresql://{WRITER_LOGIN}@{host}:5432/lanes_t241",
            f"postgresql://lanes_r_t241@{host}:5432/lanes_t241")
        self.conf = primary_config(conf_dir / "lanes-index.conf", register_url, reader_url,
                                   self.passfile)
        self.env.update(LANES_INDEX_CONFIG=str(self.conf))
        self.env.pop("LANES_INDEX", None)
        for lane in checkouts:
            self.make_lane_checkout(lane)

    def _prep(self, files: dict) -> None:
        """`files` written over the checkout, committed and pushed, so the
        case starts from them; C is that commit."""
        estate = self.estate
        for path, text in files.items():
            (estate.checkout / path).parent.mkdir(parents=True, exist_ok=True)
            (estate.checkout / path).write_bytes(text.encode("utf-8"))
        git(estate.checkout, "add", "-A", env=estate.env)
        git(estate.checkout, "commit", "-q", "-m", "C': the case's starting state",
            env=estate.env)
        git(estate.checkout, "push", "-q", "origin", "main", env=estate.env)
        estate.files.update(files)
        estate.c = git(estate.checkout, "rev-parse", "HEAD", env=estate.env).strip()
        estate.lanes_tree = git(estate.checkout, "rev-parse", f"{estate.c}:lanes",
                                env=estate.env).strip()

    def lane_checkout(self, lane: str) -> Path:
        """`<c>`, lane `lane`'s own register checkout, where `lanes-edit.sh`'s
        `lane_checkout_path` puts it (Amendment 23 S1): `<W>-lanes/<lane>`, W
        being the real path of `workspace.yaml`'s `path:`, this checkout."""
        real = Path(os.path.realpath(self.estate.checkout))
        return real.parent / f"{real.name}-lanes" / lane

    def make_lane_checkout(self, lane: str) -> Path:
        """`<c>` for `lane`, a clone of W's origin, as `lane-checkout <lane>
        --create` makes one."""
        target = self.lane_checkout(lane)
        target.parent.mkdir(parents=True, exist_ok=True)
        git(target.parent, "clone", "-q", str(self.estate.origin), str(target),
            env=self.estate.env)
        return target

    def run(self, argv: list, lane: str | None, **extra) -> subprocess.CompletedProcess:
        """`lanes-edit.sh <argv>` in the checkout, as lane `lane`
        (`LANES_LANE`), or with `LANES_LANE` unset where `lane` is None."""
        env = dict(self.env, **extra)
        if lane is None:
            env.pop("LANES_LANE", None)
        else:
            env["LANES_LANE"] = lane
        return subprocess.run(["bash", str(self.lanes_edit), *argv], capture_output=True,
                              encoding="utf-8", errors="replace", env=env, timeout=120,
                              cwd=str(self.estate.checkout), check=False,
                              stdin=subprocess.DEVNULL)

    def git_state(self) -> tuple:
        """AT-2's git oracle: the checkout's HEAD, status, index digest and
        `origin/main`, the files under `lanes/`, and origin's refs."""
        lanes = self.estate.checkout / "lanes"
        files = {p.relative_to(lanes).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(lanes.rglob("*")) if p.is_file()}
        refs = git(self.estate.origin, "for-each-ref", "--format=%(refname) %(objectname)",
                   env=self.estate.env)
        return self.estate.state(), files, refs


def unreachable_answers(dead: Path) -> list:
    """The fake's answer for every call that carries a request: `psql`'s own
    exit 2 and its text for an empty socket directory (AT-2, "Unreachable
    (FP)")."""
    socket = dead / ".s.PGSQL.5432"
    return [{"exit": 2, "stderr": f'psql: error: connection to server on socket "{socket}" '
                                  f"failed: No such file or directory\n\tIs the server running "
                                  f"locally and accepting connections on that socket?\n"}]


def _lock_files(ws: PrimaryWorkstation) -> list:
    """The writers' mutexes left anywhere under the workspace: the lane
    checkout's and any scratch tree's `.lanes-edit.lock` (`lanes-edit.sh`'s
    `LOCK`, :1212 at a2073eae; `design.md` S1, step 2), and git's
    `index.lock`."""
    root = ws.estate.root
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                  if p.name in (".lanes-edit.lock", "index.lock"))


# ------------------------------------------------------------ no engine (FP)

@pytest.mark.parametrize("verb", list(WRITE_VERBS))
def test_each_write_exits_69_when_the_database_is_unreachable(tmp_path, verb):
    """AT-2, "Unreachable (FP)": with every `psql` call answered by `psql`'s
    exit 2 and its "connection to server ... failed" text, `lanes-edit.sh
    <verb>` on primary exits 69; stderr names the store and the error with
    no credential and no URL; a read verb's stdout is empty; the fake's log
    shows the writer connected with `register_url=`'s login and
    `register_passfile=`, `PGPASSWORD` never set, and no call after the
    failed one (no retry that reads as a write, no fallback); and git is as
    it was (the checkout, the files under `lanes/`, origin's refs)."""
    ws = PrimaryWorkstation(tmp_path, prep=PREPS.get(verb))
    fake = fake_psql_dir(ws.fakebin, answers=unreachable_answers(ws.dead))
    ws.env.update(fake)
    argv, lane = WRITE_VERBS[verb]
    before = ws.git_state()
    proc = ws.run(argv, lane)
    said = proc.stdout + proc.stderr
    assert proc.returncode == 69, (
        f"lanes-edit.sh {verb} on primary exited {proc.returncode}, not 69, with the database "
        f"unreachable (L4-B3, T415's attempt loop): {proc.stderr[-800:]}")
    assert "connection to server" in proc.stderr, f"stderr names no error: {proc.stderr!r}"
    assert SECRET not in said and not re.search(r"postgres(ql)?://", said), said
    calls = fake_calls(fake)
    assert len(calls) == 1, (
        f"{len(calls)} psql calls carried a request, not one: a call followed the failed one "
        f"(a retry that reads as a write, or a fallback): {calls}")
    for call in calls:
        assert call["url"].startswith(f"postgresql://{WRITER_LOGIN}@"), call["url"]
        assert call["passfile"] == str(ws.passfile) and call["pgpassword"] is False, call
    assert ws.git_state() == before, "git changed: a write fell back to the files"


@pytest.mark.parametrize("write", ["commit-carry", "push-beyond-handoffs"])
def test_each_direct_write_refuses_with_2_on_primary(tmp_path, write):
    """D10, as T420 builds it at 1b (B10 tasks:1213-1231; R16): on primary,
    `commit`'s carry form (a hand edit under `lanes/`, staged and committed by
    `lanes-edit.sh commit`) and a push of a commit that changes a path
    outside `handoffs/` (T420's backstop) each exit 2 before any SQL: the
    fake's log holds no call that carries a request, the files under `lanes/`
    are as they were, and origin's refs are unchanged. The captures and
    `add-row`'s compensating commit do not exist at 1b (T420: "compensat"
    matches nothing), so they have no id."""
    ws = PrimaryWorkstation(tmp_path)
    fake = fake_psql_dir(ws.fakebin, answers=unreachable_answers(ws.dead))
    ws.env.update(fake)
    checkout = ws.estate.checkout
    if write == "commit-carry":
        target = checkout / "lanes" / "LANES.md"
        target.write_bytes(target.read_bytes() + b"a hand edit\n")
        argv = ["commit", "a hand edit, carried"]
    else:
        (checkout / "notes.md").write_text("outside handoffs/\n", encoding="utf-8")
        git(checkout, "add", "notes.md", env=ws.estate.env)
        git(checkout, "commit", "-q", "-m", "a queued commit outside handoffs/",
            env=ws.estate.env)
        argv = ["commit", "publish the queued commit"]
    refs = git(ws.estate.origin, "for-each-ref", "--format=%(refname) %(objectname)",
               env=ws.estate.env)
    lanes_before = {p: (checkout / p).read_bytes() for p in SEED if (checkout / p).exists()}
    proc = ws.run(argv, "repoA-1")
    assert proc.returncode == 2, (
        f"{write} on primary exited {proc.returncode}, not 2 (D10; L4-B11, T420): "
        f"{proc.stderr[-800:]}")
    assert fake_calls(fake) == [], f"a direct write reached SQL: {fake_calls(fake)}"
    assert git(ws.estate.origin, "for-each-ref", "--format=%(refname) %(objectname)",
               env=ws.estate.env) == refs, "origin moved"
    if write == "push-beyond-handoffs":
        assert {p: (checkout / p).read_bytes() for p in lanes_before} == lanes_before


def test_a_hand_edit_commit_is_refused_on_primary(tmp_path):
    """GB section 4.3's D10 case (R29; R16): `lanes-edit.sh commit`'s carry
    form, over a hand edit of `lanes/LANES.md`, exits 2 on primary, says the
    register is SQL, reaches no SQL, and leaves the file, the index, HEAD and
    origin as they were (the test plan's line 734)."""
    ws = PrimaryWorkstation(tmp_path)
    fake = fake_psql_dir(ws.fakebin, answers=unreachable_answers(ws.dead))
    ws.env.update(fake)
    target = ws.estate.checkout / "lanes" / "LANES.md"
    target.write_bytes(target.read_bytes() + b"a hand edit\n")
    edited = target.read_bytes()
    before = ws.estate.state()
    proc = ws.run(["commit", "a hand edit"], "repoA-1")
    assert proc.returncode == 2, (
        f"a hand-edit commit on primary exited {proc.returncode}, not 2 (D10; T420's carry "
        f"form): {proc.stderr[-800:]}")
    assert fake_calls(fake) == [], f"the refusal reached SQL: {fake_calls(fake)}"
    assert target.read_bytes() == edited, "the hand edit was changed"
    assert ws.estate.state() == before, "HEAD, the index or origin moved"


def _queue(ws: PrimaryWorkstation, path: str, text: str) -> str:
    """A local commit, not pushed, that writes `path`. Returns its sha."""
    checkout = ws.estate.checkout
    target = checkout / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))
    git(checkout, "add", "--", path, env=ws.estate.env)
    git(checkout, "commit", "-q", "-m", f"queued: {path}", env=ws.estate.env)
    return git(checkout, "rev-parse", "HEAD", env=ws.estate.env).strip()


def test_a_queued_handoff_commit_is_still_published(tmp_path):
    """GB section 4.3's D10 case (R16): on primary, the publish act stays,
    fenced to `handoffs/`. A queued local commit that writes only
    `handoffs/repoA-1.md` is published by `lanes-edit.sh commit` with nothing
    staged: it exits 0, origin's `main` is that commit, and no `psql` call is
    made, since `commit` is exempt from the attempt loop (T420, review M2)."""
    ws = PrimaryWorkstation(tmp_path)
    fake = fake_psql_dir(ws.fakebin, answers=unreachable_answers(ws.dead))
    ws.env.update(fake)
    sha = _queue(ws, "handoffs/repoA-1.md", "# repoA-1's handoff, queued\n")
    proc = ws.run(["commit", "publish the queued commit"], "repoA-1")
    assert proc.returncode == 0, (
        f"the publish act exited {proc.returncode} on primary (T420 keeps it): "
        f"{proc.stderr[-800:]}")
    assert git(ws.estate.origin, "rev-parse", "refs/heads/main",
               env=ws.estate.env).strip() == sha, "the queued handoff commit was not published"
    assert fake_calls(fake) == [], f"the publish act reached SQL: {fake_calls(fake)}"


def test_a_queued_lanes_commit_is_refused_as_a_divergence(tmp_path):
    """GB section 4.3's D10 case (R16): on primary, a queued local commit that
    writes under `lanes/` is refused by the publish act as a divergence: a
    nonzero exit that names the divergence and the commit, no push (origin's
    refs unchanged), no SQL, and the local commit left for the operator."""
    ws = PrimaryWorkstation(tmp_path)
    fake = fake_psql_dir(ws.fakebin, answers=unreachable_answers(ws.dead))
    ws.env.update(fake)
    refs = git(ws.estate.origin, "for-each-ref", "--format=%(refname) %(objectname)",
               env=ws.estate.env)
    lanes = ws.estate.checkout / "lanes" / "LANES.md"
    sha = _queue(ws, "lanes/LANES.md", lanes.read_text(encoding="utf-8") + "queued\n")
    proc = ws.run(["commit", "publish the queued commit"], "repoA-1")
    assert proc.returncode == 2, (
        f"a queued lanes/ commit on primary exited {proc.returncode}, not 2 (T420's fence): "
        f"{proc.stderr[-800:]}")
    assert "diverge" in proc.stderr.lower() and sha[:7] in proc.stderr, proc.stderr
    assert git(ws.estate.origin, "for-each-ref", "--format=%(refname) %(objectname)",
               env=ws.estate.env) == refs, "origin moved"
    assert git(ws.estate.checkout, "rev-parse", "HEAD", env=ws.estate.env).strip() == sha
    assert fake_calls(fake) == [], f"the refusal reached SQL: {fake_calls(fake)}"


#: An image that breaks the register's text: a line holding a CR, and one
#: holding a NUL, each in `lanes/LANES.md`'s new image.
BAD_IMAGES = {"image-cr": "\r", "image-nul": "\0"}


@pytest.mark.parametrize("bad", list(BAD_IMAGES))
def test_an_image_holding_a_cr_or_a_nul_is_refused_with_2_and_nothing_sent(tmp_path, bad):
    """Lane 3's reading 3 of T112 (#165 6755386771; F10-OWED item 31; contract
    section 3.3, "a listed file breaks its format ... 2"): `register commit`
    over an attempt directory whose image of `lanes/LANES.md` holds a CR (the
    line ends CRLF) or a NUL exits 2, never 69, before anything is sent: no
    `psql` call at all, not even T106's `--version` probe, and the attempt
    directory is as it was. Stderr names the image's path. No engine and no
    lane 4 code: the directory is built by hand, in section 3.3's table."""
    copy = flipped(tmp_path)
    fake = fake_psql_dir(tmp_path / "fakebin", answers=[{"exit": 3, "stderr":
                                                         "ERROR:  XX000: never sent\n"}])
    estate = Estate(tmp_path / "estate")
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()
    passfile = conf_dir / "pgpass"
    passfile.write_text(f"*:*:*:{WRITER_LOGIN}:{SECRET}\n", encoding="utf-8")
    passfile.chmod(0o600)
    host = quote((tmp_path / "dead").as_posix(), safe="")
    conf = primary_config(conf_dir / "lanes-index.conf",
                          f"postgresql://{WRITER_LOGIN}@{host}:5432/lanes_t241",
                          f"postgresql://lanes_r_t241@{host}:5432/lanes_t241", passfile)
    env = index_env(tmp_path, conf, estate.home, **fake)
    env["PATH"] = str(tmp_path / "fakebin") + os.pathsep + _masked_path()

    write_id, generation = str(uuid.uuid4()), str(uuid.uuid4())
    args_sha256 = hashlib.sha256(b"t241 " + bad.encode("ascii")).hexdigest()
    not_after = str(int(time.time()) + 300)
    attempt = tmp_path / "attempt"
    path = "lanes/LANES.md"
    old = SEED[path].encode("utf-8")
    new = old + (f"HOLD {EM} lane repoA-2 ({WS}), window w, 2026-11-10T00:00:00Z: "
                 f"opensoft/repoB main {TIP} for a check{BAD_IMAGES[bad]}").encode("utf-8")
    new += b"\n"
    blob = lambda data: hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: E731
    (attempt / "images" / "lanes").mkdir(parents=True)
    (attempt / "images" / path).write_bytes(new)
    (attempt / "tree").mkdir()
    (attempt / "snapshot").write_text(
        f"format=1\nwrite_id={write_id}\ngeneration={generation}\nn=5\n"
        f"not_after={not_after}\nclock={int(time.time())}\n", encoding="utf-8")
    (attempt / "not_after").write_text(not_after + "\n", encoding="utf-8")
    (attempt / "changes.tsv").write_text(f"M\t{path}\t{blob(old)}\t{blob(new)}\n",
                                         encoding="utf-8")
    (attempt / "files").write_text(_canonical_rows([("M", path, "", "")], {path: new}),
                                   encoding="utf-8")
    (attempt / "msg").write_text("lanes-edit.sh append-line: test 2's bad image\n",
                                 encoding="utf-8")
    (attempt / "author").write_text(AUTHOR + "\n", encoding="utf-8")
    before = {p.relative_to(attempt).as_posix(): p.read_bytes()
              for p in sorted(attempt.rglob("*")) if p.is_file()}

    proc = run_index(copy, ["register", "commit", "--write-id", write_id, "--generation",
                            generation, "--lane", "repoA-2", "--verb", "append-line",
                            "--args-sha256", args_sha256, "--workstation", WS, attempt], env)
    assert proc.returncode != 69, (
        f"an image holding {bad[6:].upper()} gave 69; lane 3's reading 3 makes it 2: "
        f"{proc.stderr}")
    assert proc.returncode == 2, f"register commit exited {proc.returncode}: {proc.stderr}"
    assert f"images/{path}" in proc.stderr, f"stderr names no image: {proc.stderr!r}"
    log = Path(fake["FAKE_PSQL_LOG"])
    assert not log.exists() or log.read_text(encoding="utf-8") == "", (
        f"psql was called before the refusal: {log.read_text(encoding='utf-8')}")
    assert {p.relative_to(attempt).as_posix(): p.read_bytes()
            for p in sorted(attempt.rglob("*")) if p.is_file()} == before


# REQUEST-HANDOFF'S 64S (lane 2's T241d; R-F13c-23; lane 3's batch 8, #165
# 6780753157, Q35 and its text change 5 for B14 tasks:1149; lane 4's
# questions, `QUESTIONS-L3-1110g-b-a5582b2d.md`, 35). On primary every write
# runs four checks before its claim (B14 tasks:1142's T415 bullets): it names
# its lane, the lane's own checkout `<c>` is there (`lanes-edit.sh
# lane-checkout <lane> --create` makes it; a write makes no clone, which
# would be D12's fetch), `LANES_LANE` is a lane name, and `LANES_NO_GIT=1` is
# not set. Each refuses with nothing sent: 2 for every verb but
# `request-handoff`, which refuses 64, never 2, since `lane` reads a 2 from it
# as "lane <L> is still bound elsewhere" (REV415b NIT 6's reason). `lane`
# calls it with no `LANES_LANE` (lane 4's question 35), and lane 3 rules that
# `lane` sets it (T432), and that the verb's refusal is 64 all the same.
#
# The write's lane is `request-handoff`'s `<lane>`, repoA-1, and its `<c>` is
# `<W>-lanes/repoA-1`. Every check but the id's own is met, so each id meets
# its own refusal and no other: `<c>` is made first, a clone of origin, but
# for `[missing-checkout]`. No engine; fails until lane 4's T415 takes Q35.
#
# Lane 3's batch c, Q67 (#165 6807881675; B15 text 5 for B14 tasks:1149 and
# text 7 for F13d:513), adds the two other refusals the primary branch makes
# before its claim: a pending hand edit of a rendered file in `<c>`
# (`pw_hand_edit_refuse`, `[hand-edit]`) and no author identity in `<c>`
# (`pw_author_read`, `[no-author]`). Each is 64 for `request-handoff`, by
# `pw_pre_rc`. They fail until lane 4's T415 takes Q67; the first four ids
# pass on lane 4's T415 `15af6b9c`.

#: The arguments `WRITE_VERBS` gives `request-handoff`, and its `<lane>`.
REQUEST_HANDOFF_ARGV = WRITE_VERBS["request-handoff"][0]
REQUEST_HANDOFF_LANE = REQUEST_HANDOFF_ARGV[1]

#: {id: (the arguments, `LANES_LANE` or None for it unset, what the run adds
#: to the environment, whether `<c>` is made first, what stderr names)}.
REQUEST_HANDOFF_64 = {
    # No `<lane>`: the arm's own usage code (B14 tasks:1162).
    "missing-lane": (["request-handoff"], "repoA-2", {}, True, "request-handoff <lane>"),
    # B14 tasks:1149: refused "before the claim, naming it".
    "no-git": (REQUEST_HANDOFF_ARGV, "repoA-2", {"LANES_NO_GIT": "1"}, True, "LANES_NO_GIT"),
    # `pw_lane_given`: `LANES_LANE` unset, as `lane` calls the verb; B14
    # tasks:1142, "naming the command with it".
    "lane-given": (REQUEST_HANDOFF_ARGV, None, {}, True, "LANES_LANE"),
    # B14 tasks:1142: "naming `lanes-edit.sh lane-checkout <lane> --create`".
    "missing-checkout": (REQUEST_HANDOFF_ARGV, "repoA-2", {}, False,
                         f"lane-checkout {REQUEST_HANDOFF_LANE} --create"),
    # Q67, `pw_hand_edit_refuse`: Y:2459's refusal names each file.
    "hand-edit": (REQUEST_HANDOFF_ARGV, "repoA-2", {}, True, "lanes/LANES.md"),
    # Q67, `pw_author_read`: "no author identity in `<c>`" (B15 text 5).
    "no-author": (REQUEST_HANDOFF_ARGV, "repoA-2", {}, True, "author identity"),
}


def _hand_edit_in_c(ws: PrimaryWorkstation, checkout: Path) -> None:
    """A pending hand edit of a rendered file in `<c>`: a line appended to
    its `lanes/LANES.md`, not committed (B14 tasks:1151, "looked for in the
    lane checkout")."""
    with open(checkout / "lanes" / "LANES.md", "a", encoding="utf-8") as handle:
        handle.write("a hand edit in the lane's checkout, never committed\n")


def _no_author_in_c(ws: PrimaryWorkstation, checkout: Path) -> None:
    """No author identity in `<c>`: the run loses the estate's `GIT_AUTHOR_*`
    (and any `EMAIL`), and `<c>` sets `user.useConfigOnly`, so `git -C <c>
    var GIT_AUTHOR_IDENT` gives none, whatever the host's name; the global
    and system configurations are already empty (`git_env`)."""
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "EMAIL"):
        ws.env.pop(name, None)
    git(checkout, "config", "user.useConfigOnly", "true", env=ws.estate.env)


#: What a `REQUEST_HANDOFF_64` id does to `<c>` before its run, where it does
#: anything.
REQUEST_HANDOFF_C_PREP = {"hand-edit": _hand_edit_in_c, "no-author": _no_author_in_c}


@pytest.mark.parametrize("refusal", list(REQUEST_HANDOFF_64))
def test_request_handoff_refuses_64_never_2_on_primary(tmp_path, refusal):
    """Lane 3's batch 8, Q35 (B15 text 5 for B14 tasks:1149): on primary,
    `request-handoff` refuses 64, never 2, for its missing lane
    (`[missing-lane]`, no `<lane>` at all), `LANES_NO_GIT=1` (`[no-git]`),
    `pw_lane_given`'s refusal (`[lane-given]`, `LANES_LANE` unset), a
    missing `<c>`, the lane's own checkout (`[missing-checkout]`), and, by
    lane 3's batch c, Q67 (B15 text 7 for F13d:513), a pending hand edit of
    a rendered file in `<c>` (`[hand-edit]`) and no author identity in
    `<c>` (`[no-author]`), since `lane` reads a 2 from it as "lane <L> is
    still bound elsewhere". Each is a refusal before the claim: stderr names
    its cause, the fake's log holds no call that carries a request, git is
    as it was, and no clone is made. The other writer verbs' `LANES_NO_GIT=1`
    refusal stays 2 (B14 tasks:1149), and is not this case's. Its first four
    ids fail until lane 4's T415 takes Q35, and pass on T415 `15af6b9c`;
    `[missing-lane]` passes before it, since main's arm already refuses a
    missing lane 64, and holds that code against a 2. `[hand-edit]` and
    `[no-author]` fail until lane 4's T415 takes Q67."""
    argv, lane, extra, with_checkout, names = REQUEST_HANDOFF_64[refusal]
    ws = PrimaryWorkstation(tmp_path,
                            checkouts=(REQUEST_HANDOFF_LANE,) if with_checkout else ())
    fake = fake_psql_dir(ws.fakebin, answers=unreachable_answers(ws.dead))
    ws.env.update(fake)
    checkout = ws.lane_checkout(REQUEST_HANDOFF_LANE)
    if refusal in REQUEST_HANDOFF_C_PREP:
        REQUEST_HANDOFF_C_PREP[refusal](ws, checkout)
    before = ws.git_state()
    proc = ws.run(argv, lane, **extra)
    assert proc.returncode != 2, (
        f"request-handoff on primary refused [{refusal}] with 2, which `lane` reads as 'lane "
        f"{REQUEST_HANDOFF_LANE} is still bound elsewhere' (Q35, Q67; lane 4's T415): "
        f"{proc.stderr[-800:]}")
    assert proc.returncode == 64, (
        f"request-handoff on primary exited {proc.returncode} for [{refusal}], not 64 (Q35, "
        f"Q67; lane 4's T415): {proc.stderr[-800:]}")
    assert names in proc.stderr, f"stderr does not name {names!r}: {proc.stderr!r}"
    assert fake_calls(fake) == [], f"the refusal reached SQL: {fake_calls(fake)}"
    assert ws.git_state() == before, "git changed: the refusal wrote"
    assert checkout.is_dir() == with_checkout, (
        f"the refusal {'removed' if with_checkout else 'made'} {checkout}: a write on primary "
        f"makes no clone (D12)")


# ------------------------------------------------------------ real engine (RE)

class RegisterWorkstation(PrimaryWorkstation):
    """`PrimaryWorkstation` over the test's database: its workspace's C is
    imported and brought to `primary` with the marker `present` (test 1's
    `import_to_primary`), and `lanes-edit.sh` connects as this module's
    logins, through T203's `psql` shim, first on `PATH`, which hands every
    call to the cluster's `psql` until a case arms it."""

    def __init__(self, pg, tmp_path: Path, prep: dict = None):
        fakebin = tmp_path / "fakebin"
        fakebin.mkdir(parents=True, exist_ok=True)
        (fakebin / "psql").write_text(PSQL_SHIM, encoding="utf-8")
        (fakebin / "psql").chmod(0o755)
        (fakebin / PSQL_SHIM_CONTROL).write_text(json.dumps({"psql": pg.psql_bin}),
                                                 encoding="utf-8")
        ensure_logins(pg)
        super().__init__(tmp_path, (pg.url(LOGIN_WRITER), pg.url(LOGIN_READER)), fakebin,
                         prep)
        self.pg = pg
        import_to_primary(pg, self.estate)

    def arm(self, arms: list) -> None:
        (self.fakebin / PSQL_SHIM_CONTROL).write_text(
            json.dumps({"psql": self.pg.psql_bin, "arms": arms}), encoding="utf-8")

    def shim_calls(self) -> list:
        log = self.fakebin / PSQL_SHIM_LOG
        if not log.exists():
            return []
        entries = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x]
        return [e for e in entries if e.get("kind") != "version"]

    def db_digest(self) -> dict:
        """Each register table, the journal and the head row, copied out in
        a fixed order and digested (AT-2's database oracle)."""
        tables = [r["t"] for r in rows(self.pg, f"SELECT table_name AS t FROM "
                                                f"information_schema.tables WHERE table_schema "
                                                f"= '{SCHEMA}' AND table_type = 'BASE TABLE' "
                                                f"ORDER BY 1")]
        return {t: rows(self.pg, f"SELECT md5(coalesce(string_agg(x::text, E'\\n' ORDER BY "
                                 f"x::text), '')) AS d FROM {t} x")[0]["d"] for t in tables}

    def foreign_locks(self) -> list:
        return rows(self.pg, "SELECT pid, locktype, mode FROM pg_locks WHERE pid <> "
                             "pg_backend_pid() AND pid IN (SELECT pid FROM pg_stat_activity "
                             "WHERE application_name NOT LIKE 't210%' AND backend_type = "
                             "'client backend')")


def _commit_calls(ws: RegisterWorkstation) -> list:
    return [c for c in ws.shim_calls() if "commit_write(" in (c.get("stdin") or "")]


@pytest.mark.parametrize("verb", list(WRITE_VERBS))
def test_each_write_exits_69_when_the_switch_is_not_primary(pg, tmp_path, verb):
    """AT-2, "Refused: the switch" (P170-171): with the switch row set to
    `files`, `lanes-edit.sh <verb>` exits 69, stderr carries AT-3's line,
    the register's tables and git are unchanged, and no commit call is sent
    twice."""
    ws = RegisterWorkstation(pg, tmp_path, PREPS.get(verb))
    sql(pg, f"UPDATE {SCHEMA}.register_switch SET mode = 'files', marker_state = 'absent';")
    before_db, before_git = ws.db_digest(), ws.git_state()
    argv, lane = WRITE_VERBS[verb]
    proc = ws.run(argv, lane)
    assert proc.returncode == 69, f"{verb} exited {proc.returncode}: {proc.stderr[-800:]}"
    assert NOT_PRIMARY_LINE in proc.stderr, proc.stderr
    assert ws.db_digest() == before_db and ws.git_state() == before_git
    assert len(_commit_calls(ws)) <= 1, "a refused commit call was sent again"


@pytest.mark.parametrize("verb", list(WRITE_VERBS))
def test_each_write_exits_69_when_the_database_refuses_the_transaction(pg, tmp_path, verb):
    """AT-2, "Refused: a GRANT": with `EXECUTE` on `commit_write` revoked from
    `lanes_register_writer`, the commit call fails with 42501 and the write
    exits 69; then, with that restored and `SELECT` on `register_head`
    revoked, the snapshot is refused and the write exits 69. Each time the
    register's tables and git are unchanged, stderr names the store and the
    error without credentials, and the refused commit call is never sent
    again (R02: no resend)."""
    ws = RegisterWorkstation(pg, tmp_path, PREPS.get(verb))
    argv, lane = WRITE_VERBS[verb]
    signature = f"{SCHEMA}.commit_write(bigint, uuid, integer, uuid, jsonb)"
    for revoke, grant, code in (
            (f"REVOKE EXECUTE ON FUNCTION {signature} FROM {WRITER};",
             f"GRANT EXECUTE ON FUNCTION {signature} TO {WRITER};", "42501"),
            (f"REVOKE SELECT ON {SCHEMA}.register_head FROM {WRITER};",
             f"GRANT SELECT ON {SCHEMA}.register_head TO {WRITER};", "42501")):
        sql(pg, revoke)
        before_db, before_git, calls = ws.db_digest(), ws.git_state(), len(_commit_calls(ws))
        proc = ws.run(argv, lane)
        sql(pg, grant)
        assert proc.returncode == 69, f"{verb} exited {proc.returncode}: {proc.stderr[-800:]}"
        assert code in proc.stderr and "postgresql://" not in proc.stderr, proc.stderr
        assert ws.db_digest() == before_db and ws.git_state() == before_git
        assert len(_commit_calls(ws)) - calls <= 1, "a refused commit call was sent again"


def _unarmed_control(pg, tmp_path: Path, write: str) -> None:
    """THE CONTROL (T241j; lane 3's ruling, #165 6833755920): `write`, with no
    arm, on an estate of its own in a database of its own on the same cluster,
    made the way the armed case makes its own, must exit 0 on primary. Where
    it does not, the write fails there by itself, and the armed case could
    not tell its injected row's 23514 from the write's own, so the case fails
    here, saying that it is the control."""
    name = pg.cluster.new_database()
    try:
        control = RegisterWorkstation(Database(pg.cluster, name), tmp_path / "control",
                                      PREPS.get(write))
        argv, lane = LATE_WRITES[write]
        proc = control.run(argv, lane)
    finally:
        pg.cluster.drop_database(name)
    assert proc.returncode == 0, (
        f"THE CONTROL FAILED, NOT THE INJECTED ROW: {write} with no edit-entry arm, on an "
        f"estate and a database of its own, exited {proc.returncode} on primary, so the "
        f"armed case cannot show that a 23514 is its injected row's. Its stderr ends: "
        f"{proc.stderr[-800:]}")


@pytest.mark.parametrize("write", list(LATE_WRITES))
def test_a_failure_in_a_late_statement_leaves_journal_lines_and_head_unchanged(pg, tmp_path,
                                                                               write):
    """AT-2, "Partway" (P11; D6; TP:686-690): the shim's `edit-entry` rewrites
    commit call 1's entry so that its last structured row breaks a CHECK, as
    `LATE_ROWS` names it for each write: the transaction fails with 23514
    after the head row, the line edits and the earlier rows changed inside
    it. The shim's log shows the arm applied to commit call 1 with no error,
    so an arm the shim cannot apply fails here first, not as an exit 0 when
    the next attempt commits unarmed. The write exits 69; the journal, the
    line store and the head row are unchanged (each table's digest); git is
    unchanged; the refused call is never sent again.

    NO WRITE HERE CARRIES A HOLD ROW (T241i; lane 4's #165 6827643168, item
    5): every log line these writes add, or carry through a rename, names a
    lane's own object, `lane:<name>` (a LANDING or LANDED adds none), and
    `register_hold_object` gives no hold for those
    (a2935aee:lanes-index:11570), so T241b's
    `object_holds.-1.exempt` found an empty list. Nor could a hold row's
    `exempt` break a CHECK on a write: `commit_write` stores it only for an
    import (`v_kind = 'import' AND coalesce(x.exempt, false)`,
    a2935aee:lanes-index:7656). It needs T203d's shim, which names a list's
    element by its index, a negative one from the list's end.

    THE CONTROL COMES FIRST (T241j; lane 3's ruling, #165 6833755920): the
    same write, unarmed, on an estate and a database of its own, must exit
    0 (`_unarmed_control`). Where the write fails on primary by itself, its
    own 23514 would pass this case for the injected row's, so the case fails
    at the control instead. `[rename-lane]` and `[migrate-state-cells]` fail
    there until their own causes are fixed, by a task lanes 4 and 1 name
    (HW17: the renamed log's lines go out as unreadable `log_lines` rows
    stamped primary, and migrated lines carry a time with no seconds)."""
    _unarmed_control(pg, tmp_path, write)
    ws = RegisterWorkstation(pg, tmp_path, PREPS.get(write))
    field, value = LATE_ROWS[write]
    ws.arm([{"mode": "edit-entry", "match": "commit_write", "call": 1,
             "field": field, "value": value}])
    before_db, before_git = ws.db_digest(), ws.git_state()
    argv, lane = LATE_WRITES[write]
    proc = ws.run(argv, lane)
    commits = _commit_calls(ws)
    assert commits and commits[0]["arms"] == ["edit-entry"] and "error" not in commits[0], \
        f"the shim did not rewrite {field} in commit call 1: " \
        f"{commits[0].get('error') if commits else 'no commit call'}"
    assert proc.returncode == 69, f"{write} exited {proc.returncode}: {proc.stderr[-800:]}"
    assert "23514" in proc.stderr, proc.stderr
    assert ws.db_digest() == before_db and ws.git_state() == before_git
    assert len(commits) == 1, "the failed commit call was sent again"


@pytest.mark.parametrize("verb", list(WRITE_VERBS))
def test_a_refused_write_leaves_no_lock(pg, tmp_path, verb):
    """AT-2's lock oracle: a write refused with the database unreachable (the
    shim's `fail-match` on every call) leaves no mutex, neither the scratch
    tree's nor the lane checkout's, and no scratch tree; once the fault is
    removed, the same write made at once exits 0; and `pg_locks` shows no
    lock held by another client backend."""
    ws = RegisterWorkstation(pg, tmp_path, PREPS.get(verb))
    ws.arm([{"mode": "fail-call", "from": 1}])
    argv, lane = WRITE_VERBS[verb]
    proc = ws.run(argv, lane)
    assert proc.returncode == 69, f"{verb} exited {proc.returncode}: {proc.stderr[-800:]}"
    assert _lock_files(ws) == [], f"a mutex was left: {_lock_files(ws)}"
    ws.arm([])
    again = ws.run(argv, lane)
    assert again.returncode == 0, f"the write after the fault exited {again.returncode}: " \
                                  f"{again.stderr[-800:]}"
    assert ws.foreign_locks() == [], ws.foreign_locks()


def test_a_pending_hand_edit_names_the_file_and_a_recovery_that_works(pg, tmp_path):
    """P361-365 (TP:764-769 and Y:2505-2507, "in the writing lane's
    checkout"; B14 tasks:1151, "It is looked for in the lane checkout"): with
    a hand edit of `lanes/LANES.md` pending in the writing lane's own
    checkout `<c>` (`<W>-lanes/<lane>`, which `RegisterWorkstation` makes),
    a write refuses before its snapshot (the shim's log is empty), naming the
    file and one recovery command, the one backticked `git` command in its
    stderr; running that command in `<c>` leaves `<c>`'s `status --porcelain`
    empty, and the next write exits 0. W's own checkout holds no edit: lane
    4's answer (#165 6808439918) puts the edit in `<c>`, and keeps this
    oracle. It fails until lane 4's T415 round that prints that one command,
    `git -C <c> restore --source=HEAD --staged --worktree -- <paths>`, in
    backticks, with its read line holding none; T415 `15af6b9c` prints both
    as plain notes."""
    ws = RegisterWorkstation(pg, tmp_path)
    argv, lane = WRITE_VERBS["set-row-state"]
    checkout = ws.lane_checkout(lane)
    target = checkout / "lanes" / "LANES.md"
    target.write_bytes(target.read_bytes() + b"a pending hand edit\n")
    proc = ws.run(argv, lane)
    assert proc.returncode != 0 and ws.shim_calls() == [], (proc.returncode, ws.shim_calls())
    assert "lanes/LANES.md" in proc.stderr, proc.stderr
    commands = re.findall(r"`(git [^`]+)`", proc.stderr)
    assert len(commands) == 1, f"the refusal names {len(commands)} recovery commands: " \
                               f"{proc.stderr!r}"
    subprocess.run(commands[0], shell=True, cwd=str(checkout), env=ws.estate.env,
                   check=True, capture_output=True)
    assert git(checkout, "status", "--porcelain", env=ws.estate.env) == ""
    assert ws.run(argv, lane).returncode == 0


def test_a_write_goes_on_with_the_service_down(pg, tmp_path):
    """Round 1's 4A: with no service started (no socket under the service's
    directory), a write goes on through its own transaction (the journal
    gains one entry) and never falls back to the files (the checkout's
    `lanes/` unchanged)."""
    ws = RegisterWorkstation(pg, tmp_path)
    before = rows(pg, f"SELECT count(*) AS n FROM {SCHEMA}.journal")[0]["n"]
    lanes_before = ws.git_state()[1]
    argv, lane = WRITE_VERBS["log"]
    proc = ws.run(argv, lane)
    assert proc.returncode == 0, f"log exited {proc.returncode}: {proc.stderr[-800:]}"
    assert rows(pg, f"SELECT count(*) AS n FROM {SCHEMA}.journal")[0]["n"] == before + 1
    assert ws.git_state()[1] == lanes_before, "the write fell back to the files"
