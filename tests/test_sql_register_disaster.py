# SPDX-License-Identifier: Apache-2.0
"""Feature 007's D22 and AT-F18: the disaster path (L2-G4; L2-G5's AT-F18;
AT-D22; AT-F18; T274; FR-053, FR-059) (opensoft/openRepoTools#165).

T274 writes this module: 12 tests, AT-D22's 6 and AT-F18's 6 (B15 tasks:2511,
"Write D22 and AT-F18, the disaster path"). The test plan's AT-F18 gives the
label rules' test four ids, `[no-label-reimport]`, `[no-label-restore]`,
`[own-label-at-primary]` and `[reimport-at-files]`, so T274's verify, which
names that function bare, collects 15 ids from the 12 tests.

THE ESTATE, `Disaster` (the test plan's AT-D22, "Fixture"):

- CLUSTER A, the live database: section 5.6's TLS cluster, T229's
  `tls_cluster`, stoppable, with SCRAM on loopback. The register is a database
  of its own on it, made empty and bootstrapped through the admin service with
  `--label register-a` (`TLSCluster.second_database`). The engineer `ds`'s two
  logins are made on it by `lanes-index login add ds` under a pty; the dump
  login, `lanes_register_dump`, is the one T228's `login add --dump-job` made
  on the same cluster when its template was built.
- A BARE ORIGIN WITH THE FIXTURE REGISTER, test 7's (pgcluster's
  `ImportedRegister`, T227b). Its operator checkout, with its W and
  `workspace.yaml`, is ws1's: the operator lane `repoA-2` on `Eagle` (F12).
- WS1'S TOOLS AND CONFIGURATION, as test 13's drill has them: T203's flipped
  `lanes-index` (`RENDER_GIT_HALF = True`), `lanes-edit.sh`, `lanes`,
  `lane-start` and `repos.tsv` beside it, check 1's digest list, and a 0600
  `lanes-index.conf` naming `ds`'s two logins over `verify-full` with their
  password files, `register_label=` and `register_addresses=1`. In front of
  them on `PATH`: test 5's `git` wrapper, which fails each `fetch`, or the
  push of the commit carrying one `Register-Seq`, when armed, and section
  3.2's `psql` shim, which logs every request.
- THE OPERATOR LANE'S OWN REGISTER CHECKOUT, `<c>`, `<W>-lanes/repoA-2/`, W
  being `ro/wip`, the path `workspace.yaml` names: a clone of the origin,
  made with ws1 before A's first write, as `lane-checkout repoA-2 --create`
  makes one (the writes module's `make_lane_checkout`, T241e). On primary a
  write refuses with 2 where it is missing (lane 4's T415; tasks:1154).
  Every operator command runs "through its checkout" (AT-D22's fixture;
  design.md S5, "`<W>-lanes/<operator lane>/`"), and the loss is the
  database's, not the host's: the re-pointing is one edit of the
  configuration alone (AT-D22's fixture; S5's disaster path, step 5). So the
  `<c>` made before the loss serves every write on B too.
- A WRITTEN THROUGH `m`, THEN `k`: the import at C (T115) and the first
  cutover (T116, T327) from ws1, `set-mode primary` (T120), then writes on
  primary from ws1, `log NOTED` (lane 4's T415), each forking its render (lane
  4's T416; lane 3's T321 to T323). The first `RENDERED` writes reach origin,
  so `m` is the mirror's last `Register-Seq`. The wrapper then fails every
  `fetch`, and the next writes are each waited for by the renderer's exit
  (open point 8's second wait: a failed `fetch` logged, then a free
  `lanes-render.lock`), so `k` is the head and `status` shows a lag of
  `k - m`. The restore branch's backup is taken between them, at `b`.
- THE BACKUP (act 3's daily dump): O2's command, `pg_dump --format=custom` of
  both schemas as `lanes_register_dump` over TLS, its password file from its
  environment; `b` is read from the file alone by `pg_restore --data-only
  --schema=lanes_register --table=register_head --file=-`. `pg_dump` and
  `pg_restore` are the fixture's, from its binaries' directory (open point 15).
- THE LOSS: `status` reads A at `k` (recording `h`), A is stopped, `status`
  prints `m` and `h`, the outage is declared on ws1 (D20), and A is destroyed.
- CLUSTER B, the replacement: a TLS cluster of the test's own whose template
  holds nothing, so no register role exists on it; its one database stands
  for the one the admin creates first (R-P41). One admin service naming it
  serves every step (R1's S4): `bootstrap --roles-only`, then for the
  re-import `bootstrap --label register-b` and `login add ds` and `login add
  --dump-job`; for the restore `login add` for both, `pg_restore
  --exit-on-error --no-password` through the service, then `bootstrap
  --label register-b`, which prints `unchanged`.
- THE RE-POINTING (F18): ws1's configuration is rewritten in one edit,
  `register_url=`, `reader_url=`, their password files and
  `register_label=`, B's, before any `lanes-index` command of ws1's reaches
  B. A second configuration that still reaches A keeps A's label: the host
  not yet re-pointed.

WHAT EACH FAILS UNTIL. B15's Order (tasks:2511's last bullet): it waits for
T205, and its tests fail until L1-A7, L1-A13 and T327 land. Each labelled
assertion also names the tasks its own commands rest on: `bootstrap` and
`--roles-only` (T109, L1-A7); `login` (T110); `import --at` and `--after-loss`
(T115, L1-A13); `cutover` in its three forms (T116, L1-A14) and its marker's
push, read-back, `record_marker`, the restore form's render and the abort's
trigger (lane 3's T327); `set-mode` (T120); `status`'s two seqs (T117) and the
declaration (T121, L1-A18); `ready`'s check 10 (T119); a write on primary
(lane 4's T415) and its render's fork (T416), rendered by lane 3's T321 to
T323; the pending record, its generation and exit 3's printed rerun (lane 4's
T412 and T417); the rollback (T304, lane 3's T326). The label rules (direct
calls, T107) and `--roles-only` (T109) rest on nothing else, and can pass on
line R now. The host still on the live database needs A at `primary` with the
marker `present`, so T327 alone.

READINGS, NOT FOUND IN A CONTRACT:
- WHICH ESTATE EACH RUNS. The re-import, the restore, the abort, `status` and
  the restore route's label run A through `m` and `k`. The host still on the
  live database runs on A at `primary` just after the cutover: its oracle reads
  no lag. AT-F18's four estate cases run D22's re-import with A written
  through `m` and then the write in doubt at `m`, with no lost tail after it,
  since their oracles read only the record and B's generation.
- THE PENDING RECORD "for a write at a seq up to `m`" is a write whose commit
  call is lost before COMMIT (the shim's `no-reconnect` arm, `as: before`, as
  T244's `exit3` makes one): it ends 3 with its record kept and its printed
  rerun, at head `m`, and its effect is on neither A nor the mirror, so B's
  effect check finds it absent.
- "LR007'S TEXT" is read as naming the write id and both generations, as
  `commit_write`'s LR007 message does ("write <id> belongs to register
  generation <A>, not <B>").
- "A PLAIN RERUN AFTER IT FINDS NO RECORD OF A'S": the same command with no
  variable, after the replacement's write, is not refused for A's record: it
  exits 0, names neither A's id nor A's generation, and journals a write of its
  own.
- THE ABORT'S DUMP orders each of the twelve tables by its primary key's
  columns, as `pg_index` gives them, and holds each row as `to_jsonb` prints
  it. `stderr`'s first line naming the abort is read as carrying "abort".
- `STATUS` AT A IS READ BY ITS REGISTER LINES, NOT ITS EXIT. The test plan
  gives it no exit ("`status` shows a lag of `k - m`"; "`status` reads A at
  `k`, recording `h`"). Its exit is #160's index's as well, and ws1 syncs no
  index, so it is 1 there (`index: missing`) while it reads A. So A's lag
  line, or its `n` at `k`, is the oracle, with 69, the register unread,
  refused; with A stopped it is 69, as the loss asserts.
- `bootstrap` on B runs with `--no-passwords`: no password of the indexer's
  is under test here, and the logins' are `login add`'s (as pgcluster's own
  bootstrap runs).

HELPERS COPIED, NEVER SHARED (a module's own): the drill's `Workstation`
form, `_rows`, `_renders`, `RENDER_SET`, `REGISTER_SEQ`, `LAG_0`, `CHECK_LINE`,
`_checks`, `mirror_problem` and `wait_for_seq` from T276's
`test_sql_register_drill.py` (line DR's `ca9b1a3a`); test 5's `git` wrapper
from T273b's `GIT_WRAPPER` (`test_sql_register_rollback.py`, this base), with
a `fail` arm and a push arm added; AT-LR006's entries (`_entry` and its
kinds) from T273's `RollbackRegister`; `exit3`'s arm, the record's path and
the rerun's two patterns from T244's `test_sql_register_in_doubt.py` (line
ID's `3965033`); O2's `DUMP_COMMAND`, the object lines and the three
database-level checks of `dump_restore_privileges` from T224's
`test_sql_register_managed.py` (line MG). From the fixture and H's helpers,
which each real-engine module imports: `tls_cluster`, `pg`, `TLSCluster`,
`ImportedRegister`, `PASSWORD_LINE`, `ClusterError`, `PSQL_SHIM`,
`flipped_copy` and `guard_strip_env`.

THE PATH (wave 11's policy, mask and never drop): no call here drops a `PATH`
directory. ws1 puts its fake `tmux`, the wrapper and the shim, its tools and
the engine's binaries first, and keeps every inherited directory behind them.

Every wait here has a ceiling: each poll, `SETTLE_S`; each command, its
`timeout`. Every id is RE: without PostgreSQL 16 it skips with T205's banner.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from pgcluster import (FX_DUMP, FX_LANE, FX_REPOSITORY, PASSWORD_LINE, ClusterError, Database,
                       ImportedRegister, TLSCluster)
from sql_register_helpers import (PSQL_SHIM, PSQL_SHIM_CONTROL, PSQL_SHIM_LOG, flipped_copy,
                                  guard_strip_env)

#: THE LANDING GATE'S TABLE (T280's reader, `tests/sql_register_gate.py`), TEMPORARY:
#: T281 removes it in the last set. Where the gate is active, an id is skipped until
#: every task its rows name has landed: the `"*"` row holds for every id of the module,
#: and a function's row adds to it for each of that function's ids. Each row is the
#: fails-until clause of T274's **Order** (tasks:2521 at lane 3's commit 17, 204145ae),
#: each lane 1 label read as the tasks it covers. `"*"` is T109, which every case waits
#: for; the label rules' four ids, by direct calls, add T107 alone; and
#: `test_bootstrap_roles_only_makes_the_roles_and_no_schema` has no row of its own,
#: since it waits only for T109.
SQL_REGISTER_GATE_TABLE = {
    "*": ("T109",),  # every id: the tasks all its rows share
    "test_a_backup_newer_than_the_mirror_is_restored_and_rendered": ("T110", "T115", "T117", "T120", "T121", "T327", "T415", "T416"),  # T274; tasks:2521
    "test_a_pending_record_from_the_lost_database_is_refused_2_at_the_snapshot": ("T110", "T115", "T117", "T120", "T121", "T327", "T412", "T415", "T416", "T417"),  # T274; tasks:2521
    "test_an_abort_after_a_restore_form_cutover_restores_every_table_byte_for_byte": ("T110", "T115", "T117", "T120", "T121", "T327", "T415", "T416"),  # T274; tasks:2521
    "test_an_after_loss_cutover_from_a_host_still_on_the_live_database_is_refused_with_2_and_writes_nothing": ("T110", "T115", "T120", "T327"),  # T274; tasks:2521
    "test_lanes_write_id_new_on_the_replacement_replaces_the_old_record_and_writes_once": ("T110", "T115", "T117", "T120", "T121", "T327", "T412", "T415", "T416", "T417"),  # T274; tasks:2521
    "test_status_prints_the_mirror_tip_and_the_last_head_that_bound_the_loss": ("T110", "T115", "T117", "T120", "T121", "T327", "T415", "T416"),  # T274; tasks:2521
    "test_the_after_loss_cutovers_label_rules_in_the_transaction": ("T107",),  # T274; tasks:2521
    "test_the_disaster_path_reimports_at_the_mirrors_tip_and_continues_the_sequence": ("T110", "T115", "T117", "T120", "T121", "T327", "T415", "T416"),  # T274; tasks:2521
    "test_the_disaster_path_rewrites_the_marker_by_the_after_loss_cutover": ("T110", "T115", "T117", "T120", "T121", "T304", "T326", "T327", "T412", "T415", "T416", "T417"),  # T274; tasks:2521
    "test_the_printed_rerun_between_a_reimports_bootstrap_and_its_cutover_exits_2_not_69": ("T110", "T115", "T117", "T120", "T121", "T327", "T412", "T415", "T416", "T417"),  # T274; tasks:2521
    "test_the_restore_route_commits_under_the_replacements_register_label_and_check_10_fails_until_it_does": ("T110", "T115", "T117", "T119", "T120", "T121", "T327", "T415", "T416"),  # T274; tasks:2521
}

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

INDEXER = REPO / "lanes-index"

#: The register's schema, `register_schema=`'s default.
SCHEMA = "lanes_register"
#: The lost database's label and the replacement's (each its bootstrap's
#: `--label`): they differ, as a restore needs (N4).
LABEL_A, LABEL_B = "register-a", "register-b"
#: The engineer, its two logins, and the dump job's login.
ENGINEER = "ds"
WRITER_LOGIN, READER_LOGIN = f"lanes_w_{ENGINEER}", f"lanes_r_{ENGINEER}"
LOGINS = (WRITER_LOGIN, READER_LOGIN, FX_DUMP)
#: ws1: its name (Rule 10) and the operator lane, which test 7's register
#: holds LIVE.
WORKSTATION, OPERATOR = "Eagle", "repoA-2"
#: The release `ready` checks the installed tools against (check 1's list).
RELEASE, ENV_NAME = "0.0.0-t274", "disaster"
DIGEST_LIST = f"openRepoTools-{RELEASE}.sha256"
#: Step 2's declaration, on Brett's word (D20).
UNTIL = "2999-01-01T00:00:00Z"
WHY = "the disaster path: the register database is lost"

#: The writes A takes: `RENDERED` reach origin (so the head is `m`), then
#: `LOST` are never rendered (so the head is `k`); the backup is taken after
#: `BACKUP_AFTER` of them (so `m < b < k`).
RENDERED, LOST, BACKUP_AFTER = 1, 3, 2
#: The ceiling of every poll here.
SETTLE_S = 60

#: The render set (Q18 (A); CLI4.10 section 3.6), as T211's module has it.
RENDER_SET = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|archive/[^/]+\.md"
                        r"|log/(?!README\.md$)[^/]+\.md)$")
#: The trailer each mirror commit and each operator entry's commit carry.
REGISTER_SEQ = re.compile(r"^Register-Seq: ([0-9]+)$", re.M)
#: `status`'s lag lines (lane 1's T117): read, and unread.
LAG_0 = re.compile(r"^\s*lag:\s+0 seq", re.M)
LAG_N = re.compile(r"^\s*lag:\s+([0-9]+) seq\(s\)", re.M)
LAG_AT_LEAST = re.compile(r"^\s*lag:\s+at least ([0-9]+) seq\(s\)", re.M)
#: `status`'s `n`, the head it read and records as `h` (T117); where the
#: register cannot be read its `n` is "unknown", which this does not match.
REGISTER_N = re.compile(r"^\s*n:\s+(-?[0-9]+)\b", re.M)
#: `status`'s two seqs where the register cannot be read (T117; ops 2.3, step 4).
MIRROR_M = re.compile(r"^\s*mirror:\s+Register-Seq ([0-9]+) at ([0-9a-f]{12})", re.M)
LAST_HEAD = re.compile(r"^\s*last head:\s+(-?[0-9]+),", re.M)
#: One check's line of `ready` (T119's form).
CHECK_LINE = re.compile(r"^check (\d+): (ok|FAIL)\b:?[ \t]*(.*)$", re.M)
#: An object line of `bootstrap` (T109's form).
OBJECT_LINE = re.compile(r"^(.+?): (created|unchanged)\b", re.M)
#: The printed rerun's two variables (T417's report; T244's patterns).
UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
WRITE_ID_SAID = re.compile(r"LANES_WRITE_ID=(" + UUID_RE + r")")
GENERATION_SAID = re.compile(r"LANES_WRITE_GENERATION=(" + UUID_RE + r")")
#: The pending records, `<state>/openRepoTools/register-pending/<d>` (T412).
PENDING = Path("openRepoTools") / "register-pending"
#: The shim's arm that loses the first commit call before its COMMIT and every
#: call after it, so the writer ends 3 with its record kept (T244's `exit3`).
NO_RECONNECT = {"mode": "no-reconnect", "as": "before", "match": "commit_write", "call": 1}
#: A password-file line's last field, hidden by `_masked`.
_SECRET_FIELD = re.compile(r"^(\*:\*:.*:)[^:\n]*$", re.M)

#: O2's dump command, run as the dump job's login (6722541787; T224's).
DUMP_COMMAND = ("umask 077 && pg_dump --no-password --schema=lanes_register "
                "--schema=lanes_index --format=custom --file={file}")

#: Section 1.2's tables but `schema_version`, `migrations` and `mirror_state`:
#: the twelve the restore form's abort puts back (AT-D22's abort).
ABORT_TABLES = ("register_switch", "register_head", "journal", "journal_edits", "journal_files",
                "journal_scopes", "files", "doc_lines", "lanes", "log_lines", "object_holds",
                "register_lines")

#: The roles `--roles-only` makes (design.md section 1.4; T109).
REGISTER_ROLES = ("lanes_register_owner", "lanes_register_writer", "lanes_register_reader",
                  "lanes_indexer")
WRITER_GROUP = "lanes_register_writer"


# ------------------------------------------------------------------ test 5's git wrapper
#: TEST 5'S `git` WRAPPER (TP:1060-1080), T273b's, with two arms AT-D22 adds:
#: `fail`, the subcommands it fails without running them (every `fetch`, for
#: the lag), and `fail_push_seq`, a `Register-Seq` whose commit's push it fails
#: (the abort: only the marker's). Each call is one JSON line of
#: `git-wrapper.log`: its subcommand, its argv, its pid, and its outcome.
GIT_WRAPPER = r'''#!/usr/bin/env -S python3 -I
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL = os.path.join(HERE, "git-wrapper.json")
LOG = os.path.join(HERE, "git-wrapper.log")
WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
              "--config-env"}
PUSH_VALUE = {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}


def split(args):
    """(the options before the subcommand, the subcommand, its arguments)."""
    i = 0
    while i < len(args):
        if args[i] in WITH_VALUE:
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            return args[:i], args[i], args[i + 1:]
    return args, "", []


def pushed_seqs(git, prefix, rest):
    """The Register-Seq values of each commit a push names as its source."""
    words, i = [], 0
    while i < len(rest):
        if rest[i] in PUSH_VALUE:
            i += 2
            continue
        if not rest[i].startswith("-"):
            words.append(rest[i])
        i += 1
    seqs = []
    for spec in words[1:]:
        source = spec.lstrip("+").split(":", 1)[0]
        if not source:
            continue
        proc = subprocess.run([git] + prefix + ["log", "-1", "--format=%B", source, "--"],
                              capture_output=True, text=True)
        if proc.returncode == 0:
            seqs += [int(s) for s in re.findall(r"^Register-Seq: ([0-9]+)$", proc.stdout, re.M)]
    return seqs


def log(record):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def main():
    args = sys.argv[1:]
    with open(CONTROL, encoding="utf-8") as handle:
        control = json.load(handle)
    prefix, sub, rest = split(args)
    record = {"sub": sub, "argv": args, "pid": os.getpid()}
    if sub in control.get("fail", []):
        log(dict(record, outcome="failed", rc=1))
        sys.stderr.write("fatal: t274 wrapper: this %s fails\n" % sub)
        return 1
    seq = control.get("fail_push_seq")
    if sub == "push" and seq is not None:
        seqs = pushed_seqs(control["git"], prefix, rest)
        if seq in seqs:
            log(dict(record, outcome="failed", rc=1, seqs=seqs))
            sys.stderr.write("fatal: t274 wrapper: the push of Register-Seq %d fails\n" % seq)
            return 1
    rc = subprocess.run([control["git"]] + args).returncode
    log(dict(record, outcome="ran", rc=rc))
    return rc


sys.exit(main())
'''


# ------------------------------------------------------------------ small helpers
def _private(path: Path, text: str) -> Path:
    """`text` at `path`, 0600, replaced in one rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(text, encoding="utf-8")
    temp.chmod(0o600)
    os.replace(temp, path)
    return path


def _script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _masked(text: str) -> str:
    """`text` with each password-file line's password hidden."""
    return _SECRET_FIELD.sub(lambda m: m.group(1) + "<password>", text or "")


def _said(proc) -> str:
    return (f"exit {proc.returncode}\n--- stdout ---\n{_masked(proc.stdout)[-2500:]}"
            f"\n--- stderr ---\n{_masked(proc.stderr)[-2500:]}")


def _jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _checks(text: str) -> dict:
    """`ready`'s check lines, by number: (`ok` or `FAIL`, the reason)."""
    return {int(m.group(1)): (m.group(2), m.group(3) or "") for m in CHECK_LINE.finditer(text)}


def _fields(text: str) -> dict:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def _rows(db, sql: str) -> list:
    """`sql`'s rows as JSON objects, in the register's schema, by `jsonb_agg`,
    whose text is one line."""
    out = db.psql(f"SET search_path TO {SCHEMA};\n"
                  f"SELECT coalesce(jsonb_agg(t), '[]'::jsonb) FROM ({sql}) t;\n").stdout
    return json.loads(out.strip().splitlines()[-1])


def _value(db, sql: str) -> str:
    return db.psql(sql).stdout.strip()


def _renders(db) -> dict:
    """SQL's own render (lane 1's T107, `render_file`) of every path in
    `files`, {path: bytes}."""
    return {r["path"]: base64.b64decode(r["b64"]) for r in _rows(
        db, "SELECT path, encode(render_file(path), 'base64') AS b64 FROM files ORDER BY path")}


def _passfile(path: Path, login: str, password: str) -> Path:
    """A 0600 libpq password file holding `login`'s line at any host, port
    and database."""
    return _private(path, f"*:*:*:{login}:{password}\n")


def _connects(cluster, login: str, database: str, passfile: Path) -> bool:
    """Whether `login` logs in to `database` on `cluster` over TLS
    (`verify-full`, the root alone) with the password in `passfile`."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    env.update(PGHOST="localhost", PGHOSTADDR="127.0.0.1", PGPORT=str(cluster.port),
               PGUSER=login, PGDATABASE=database, PGSSLMODE="verify-full",
               PGSSLROOTCERT=str(cluster.root_cert), PGPASSFILE=str(passfile),
               PGCONNECT_TIMEOUT="10", LC_ALL="C")
    proc = subprocess.run([cluster.tool("psql"), "-X", "-q", "-A", "-t", "-w", "-c", "SELECT 1"],
                          env=env, capture_output=True, text=True, timeout=60,
                          stdin=subprocess.DEVNULL, check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "1"


def _abort_dump(db) -> dict:
    """AT-D22's abort dump: each of `ABORT_TABLES`, ordered by its primary
    key, each row as `to_jsonb` prints it, as one text per table, read by the
    admin connection. No identity sequence is read."""
    dumped = {}
    for table in ABORT_TABLES:
        keys = [r["k"] for r in sorted(_rows(
            db, f"SELECT a.attname AS k, array_position(i.indkey::int2[], a.attnum) AS n "
                f"FROM pg_index i JOIN pg_attribute a "
                f"ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey) "
                f"WHERE i.indrelid = '{SCHEMA}.{table}'::regclass AND i.indisprimary"),
            key=lambda r: r["n"])]
        order = ", ".join(f't."{key}"' for key in keys) or "to_jsonb(t)::text"
        dumped[table] = _value(db, f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY {order}), "
                                   f"'[]'::jsonb)::text FROM {SCHEMA}.{table} t;")
    return dumped


def _lock_free(lock: Path) -> bool:
    """A non-blocking `flock` on the render lock succeeds (AT-5's [L4-4]); a
    lock file not made yet is free."""
    try:
        fd = os.open(str(lock), os.O_RDWR)
    except FileNotFoundError:
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    finally:
        os.close(fd)


# ------------------------------------------------------------------ ws1, the operator's host
class Host:
    """ws1 (see the module's notes): test 7's operator checkout and W, its
    installed tools, test 5's wrapper and the shim, and its configuration,
    first at A, then re-pointed at B. Every command runs as the operator lane
    through its checkout (F12)."""

    def __init__(self, estate: "Disaster", register: ImportedRegister):
        self.estate, self.root = estate, estate.root / "ws1"
        self.root.mkdir(parents=True)
        self.home, self.checkout = register.home, register.wip
        self.real_git = shutil.which("git")
        self.tools = self.root / "tools"
        try:
            self.copy = flipped_copy(INDEXER, self.tools, True)
        except ValueError as exc:
            raise AssertionError(f"[estate] lanes-index cannot be flipped to its git half "
                                 f"({exc}): lane 1's RENDER_GIT_HALF (T105) has not "
                                 f"landed") from exc
        for companion in ("lanes-edit.sh", "lanes", "lane-start", "repos.tsv"):
            if (REPO / companion).exists():
                shutil.copy2(REPO / companion, self.tools / companion)
        (self.tools / DIGEST_LIST).write_text("".join(
            f"{hashlib.sha256((self.tools / tool).read_bytes()).hexdigest()}  {tool}\n"
            for tool in ("lanes-index", "lanes-edit.sh")), encoding="utf-8")
        self.fakebin = self.root / "fakebin"
        _script(self.fakebin / "tmux", "#!/bin/sh\nexit 1\n")
        self.bin = self.root / "bin"
        _script(self.bin / "git", GIT_WRAPPER)
        _script(self.bin / "psql", PSQL_SHIM)
        for directory in ("state", "config", "tmp"):
            (self.root / directory).mkdir()
        self.state = self.root / "state"
        self.conf = self.root / "conf" / "lanes-index.conf"
        env = guard_strip_env(os.environ, strip=("XDG_", "GIT_", "EMAIL", "WORKBENCHES_"))
        inherited = [entry for entry in os.environ.get("PATH", os.defpath).split(os.pathsep)
                     if entry]
        env.update(
            HOME=str(self.home), AGENT_PROTOCOL_ROOT=str(self.home / ".agents"),
            TMPDIR=str(self.root / "tmp"), XDG_STATE_HOME=str(self.state),
            XDG_CONFIG_HOME=str(self.root / "config"),
            CLAUDE_CONFIG_DIR=str(self.home / ".claude"), LANES_WORKSTATION=WORKSTATION,
            LANES_HOST=WORKSTATION.lower(), LANES_OS="linux", LANES_CONTAINER="none",
            LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1", LANES_REPO=str(self.checkout),
            LANES_EDIT=str(self.tools / "lanes-edit.sh"), LANES_INDEX_CONFIG=str(self.conf),
            LANES_LANE=OPERATOR, GIT_AUTHOR_NAME=f"Disaster {ENGINEER}",
            GIT_AUTHOR_EMAIL=f"{ENGINEER}@example.invalid",
            GIT_COMMITTER_NAME=f"Disaster {ENGINEER}",
            GIT_COMMITTER_EMAIL=f"{ENGINEER}@example.invalid",
            GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
            PATH=os.pathsep.join([str(self.fakebin), str(self.bin), str(self.tools),
                                  str(estate.a.bindir), *inherited]))
        self.env = env
        self.lane_checkout = self.make_lane_checkout(register)
        self.arm()

    def make_lane_checkout(self, register: ImportedRegister) -> Path:
        """`<c>` (see the module's notes), where `lanes-edit.sh`'s
        `lane_checkout_path` puts it: `<W>-lanes/<lane>`, W being the real
        path of `workspace.yaml`'s `path:`. A clone of the origin by the real
        git, as `lane-checkout <lane> --create` makes one."""
        real = Path(os.path.realpath(register.ws))
        target = real.parent / f"{real.name}-lanes" / OPERATOR
        target.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run([self.real_git, "clone", "-q", str(register.origin), str(target)],
                              env=self.env, capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0, f"[estate] the operator lane's own checkout:\n{_said(proc)}"
        return target

    # ------------------------------------------------------------ the wrapper and the shim
    def arm(self, *, fail=(), fail_push_seq: int | None = None, psql_arms=()) -> None:
        """The wrapper's arms and the shim's, each log started afresh."""
        (self.bin / "git-wrapper.json").write_text(json.dumps(
            {"git": self.real_git, "fail": list(fail), "fail_push_seq": fail_push_seq}),
            encoding="utf-8")
        (self.bin / PSQL_SHIM_CONTROL).write_text(json.dumps(
            {"psql": str(self.estate.a.bindir / "psql"), "arms": list(psql_arms)}),
            encoding="utf-8")
        for name in (PSQL_SHIM_LOG, "psql-shim.ends", "git-wrapper.log"):
            (self.bin / name).write_text("", encoding="utf-8")
        (self.bin / "psql-shim.state").write_text("{}", encoding="utf-8")

    def git_calls(self) -> list:
        return _jsonl(self.bin / "git-wrapper.log")

    def failed_fetches(self) -> int:
        return sum(1 for c in self.git_calls() if c["sub"] == "fetch" and c["outcome"] == "failed")

    def pushes(self) -> list:
        return [c for c in self.git_calls() if c["sub"] == "push"]

    def commit_calls(self) -> list:
        """The shim's requests that carried a `commit_write` call."""
        return [c for c in _jsonl(self.bin / PSQL_SHIM_LOG)
                if "commit_write(" in (c.get("stdin") or "")]

    # ------------------------------------------------------------ the configuration
    def point_at(self, cluster, database: str, label: str, passfiles: dict,
                 mode: str = "index", path: Path | None = None) -> Path:
        """The 0600 configuration naming `database` on `cluster`, in one edit:
        `ds`'s two logins over TLS, their password files, the label, the
        schema and check 13's count."""
        return _private(path or self.conf, "\n".join([
            f"mode={mode}", f"register_url={cluster.url(WRITER_LOGIN, database)}",
            f"register_passfile={passfiles[WRITER_LOGIN]}",
            f"reader_url={cluster.url(READER_LOGIN, database)}",
            f"reader_passfile={passfiles[READER_LOGIN]}", f"register_label={label}",
            f"register_schema={SCHEMA}", "register_addresses=1", ""]))

    def conf_lines(self) -> list:
        return self.conf.read_text(encoding="utf-8").splitlines()

    def outage_file(self) -> Path:
        return self.conf.parent / "register-outage"

    # ------------------------------------------------------------ commands
    def _env(self, env: dict | None) -> dict:
        child = dict(self.env)
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return child

    def index(self, *args: str, env: dict | None = None,
              timeout: float = 300) -> subprocess.CompletedProcess:
        """ws1's `lanes-index`, in its checkout, as the operator lane."""
        return subprocess.run([sys.executable, str(self.copy), *args], cwd=str(self.checkout),
                              env=self._env(env), capture_output=True, text=True,
                              timeout=timeout, stdin=subprocess.DEVNULL, check=False)

    def edit(self, *args: str, env: dict | None = None,
             timeout: float = 300) -> subprocess.CompletedProcess:
        """ws1's `lanes-edit.sh`, in its checkout, as the operator lane."""
        return subprocess.run(["bash", str(self.tools / "lanes-edit.sh"), *args],
                              cwd=str(self.checkout), env=self._env(env), capture_output=True,
                              text=True, timeout=timeout, stdin=subprocess.DEVNULL, check=False)

    def git(self, *args: str) -> str:
        """The real git in ws1's checkout, past the wrapper."""
        proc = subprocess.run([self.real_git, "-C", str(self.checkout), *args], env=self.env,
                              capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0, f"git {' '.join(args[:2])} in ws1:\n{_said(proc)}"
        return proc.stdout

    def render_lock(self) -> Path:
        return self.checkout / ".git" / "lanes-render.lock"

    def pending(self) -> list:
        """ws1's pending records, `<state>/openRepoTools/register-pending/<d>`."""
        where = self.state / PENDING
        return sorted(p for p in where.iterdir()
                      if re.fullmatch(r"[0-9a-f]{64}", p.name)) if where.is_dir() else []


# ------------------------------------------------------------------ the estate
class Disaster:
    """AT-D22'S ESTATE and its steps, each with its labelled assertions (see
    the module's notes). `db` is the database ws1 points at: A's, then B's."""

    def __init__(self, request, root: Path):
        # Without an engine, T205's `pg_engine` skips first, with its banner.
        self.engine = request.getfixturevalue("pg_engine")
        self.request, self.root = request, root
        self.a = request.getfixturevalue("tls_cluster")
        try:
            self.a_db = self.a.second_database(label=LABEL_A)
        except ClusterError as exc:
            raise AssertionError(f"[estate] A's register, bootstrapped through the admin service "
                                 f"with --label {LABEL_A} (T109, L1-A7): {exc}") from exc
        self.db = self.a_db
        self._login_add(self.a, self.a_db.name, [ENGINEER])
        if FX_DUMP not in self.a.passwords:
            raise AssertionError(f"[estate] cluster A has no {FX_DUMP}: T228's `login add "
                                 f"--dump-job` (T110) made none when its template was built")
        #: A's password files, kept outside A's directory, so they outlive A.
        self.a_files = {login: _passfile(root / "pass-a" / f"{login}.pgpass", login,
                                         self.a.passwords[login]) for login in LOGINS}
        try:
            self.register = ImportedRegister(root / "estate", self.a.bindir)
        except ClusterError as exc:
            raise AssertionError(f"[estate] test 7's fixture register on a bare origin "
                                 f"(T227b): {exc}") from exc
        self.origin = self.register.origin
        self.host = Host(self, self.register)
        self.host.point_at(self.a, self.a_db.name, LABEL_A, self.a_files)
        self.b = self.b_db = None
        self.b_files: dict = {}
        self.c = self.cut = self.marker = None
        self.m = self.k = self.b_seq = self.h = None
        self.dump = None
        self.generation_a = self.generation_boot = None

    # ------------------------------------------------------------ clusters and logins
    def _login_add(self, cluster, database: str, engineers: list, dump_job: bool = False) -> None:
        """`lanes-index login add` through the admin service on `database`,
        under a pty (lane 1's T110): each password line it prints is kept in
        the cluster's memory, never printed."""
        service = cluster.admin_service(database)
        argvs = [["login", "add", engineer, "--admin-service", service] for engineer in engineers]
        if dump_job:
            argvs.append(["login", "add", "--dump-job", "--admin-service", service])
        for argv in argvs:
            code, out, err = cluster.lanes_index_tty(argv)
            assert code == 0, (f"[logins] `lanes-index {' '.join(argv[:3])}` exited {code} "
                               f"(lane 1's T110, L1-A8): {_masked(out)[-400:]} | "
                               f"{_masked(err)[-400:]}")
            found = dict(PASSWORD_LINE.findall(out))
            assert found, f"[logins] `{' '.join(argv[:3])}` printed no password line"
            cluster.passwords.update(found)

    def new_b(self) -> None:
        """Cluster B, new: a TLS cluster whose template holds nothing, so no
        register role is on it; its one database is the register's."""
        cluster = TLSCluster(self.engine.bindir, "")
        try:
            cluster.start()
        except (ClusterError, OSError, subprocess.SubprocessError) as exc:
            cluster.destroy()
            raise AssertionError(f"[B] the replacement's cluster did not start: {exc}") from exc
        self.request.addfinalizer(cluster.destroy)
        self.b, self.b_db = cluster, Database(cluster, cluster.database_name)

    def b_lanes_index(self, *args: str) -> subprocess.CompletedProcess:
        """The admin's `lanes-index` on B, through the one admin service."""
        return self.b.lanes_index([args[0], "--admin-service", self.b.admin_service(
            self.b_db.name), *args[1:]])

    def b_bootstrap(self, *, roles_only: bool = False) -> subprocess.CompletedProcess:
        extra = ["--roles-only"] if roles_only else [
            "--label", LABEL_B, "--repository", FX_REPOSITORY, "--lane", FX_LANE]
        proc = self.b_lanes_index("bootstrap", *extra, "--no-passwords")
        assert proc.returncode == 0, (
            f"[B] `bootstrap {' '.join(extra[:2])}` through the admin service failed (lane 1's "
            f"T109, L1-A7):\n{_said(proc)}")
        return proc

    def b_logins(self) -> None:
        """`login add ds` and `login add --dump-job` on B: new passwords."""
        self._login_add(self.b, self.b_db.name, [ENGINEER], dump_job=True)
        self.b_files = {login: _passfile(self.root / "pass-b" / f"{login}.pgpass", login,
                                         self.b.passwords[login]) for login in LOGINS}

    def repoint(self) -> None:
        """F18's re-pointing of ws1, in one edit, at B, with B's label."""
        mode = _fields(self.host.conf.read_text(encoding="utf-8")).get("mode", "index")
        self.host.point_at(self.b, self.b_db.name, LABEL_B, self.b_files, mode=mode)
        self.db = self.b_db

    # ------------------------------------------------------------ origin and SQL
    def origin_git(self, *args: str) -> str:
        """git in the bare origin itself, so no checkout's refs move."""
        proc = subprocess.run([self.host.real_git, f"--git-dir={self.origin}", *args],
                              capture_output=True, text=True, env=self.register.env, timeout=120,
                              stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0, f"git {' '.join(args[:2])} in origin:\n{_said(proc)}"
        return proc.stdout

    def origin_tip(self) -> str:
        return self.origin_git("rev-parse", "refs/heads/main").strip()

    def seqs_of(self, sha: str) -> list:
        return [int(s) for s in REGISTER_SEQ.findall(self.origin_git("log", "-1", "--format=%B",
                                                                     sha))]

    def commits_after(self, base: str) -> list:
        """[(commit, its Register-Seq values)] on origin's `main` after `base`,
        oldest first, first parents only."""
        out = self.origin_git("rev-list", "--reverse", "--first-parent",
                              f"{base}..refs/heads/main")
        return [(sha, self.seqs_of(sha)) for sha in out.split()]

    def origin_seqs(self) -> list:
        out = self.origin_git("log", "--reverse", "--format=%B%x00", "refs/heads/main")
        return [int(s) for body in out.split("\0") for s in REGISTER_SEQ.findall(body)]

    def store_on_origin(self, rev: str = "refs/heads/main") -> dict | None:
        names = self.origin_git("ls-tree", "-r", "--name-only", rev, "lanes/").split()
        if "lanes/STORE" not in names:
            return None
        return _fields(self.origin_git("show", f"{rev}:lanes/STORE"))

    def changed_paths(self, sha: str) -> list:
        return self.origin_git("diff-tree", "--no-commit-id", "--name-status", "-r", f"{sha}^",
                               sha).splitlines()

    def head(self, db=None) -> int:
        return _rows(db or self.db, "SELECT seq FROM register_head")[0]["seq"]

    def switch(self, db=None) -> dict:
        return _rows(db or self.db, "SELECT * FROM register_switch")[0]

    def journal(self, db=None) -> list:
        return [[r["seq"], r["kind"], r["operator"]] for r in _rows(
            db or self.db, "SELECT seq, kind, operator FROM journal ORDER BY seq")]

    def mirror_problem(self, rev: str = "refs/heads/main") -> str | None:
        """None where origin's render set at `rev` equals a full render from
        `db`, byte for byte; else what differs."""
        on_origin = {}
        for path in self.origin_git("ls-tree", "-r", "--name-only", rev, "lanes/").split():
            if RENDER_SET.match(path):
                on_origin[path] = subprocess.run(
                    [self.host.real_git, f"--git-dir={self.origin}", "show", f"{rev}:{path}"],
                    capture_output=True, env=self.register.env, timeout=60, check=True,
                    stdin=subprocess.DEVNULL).stdout
        from_sql = {p: b for p, b in _renders(self.db).items() if RENDER_SET.match(p)}
        if on_origin == from_sql:
            return None
        differ = sorted(p for p in on_origin if p in from_sql and on_origin[p] != from_sql[p])
        return (f"paths on one side only: {sorted(set(on_origin) ^ set(from_sql))}; paths that "
                f"differ: {differ}")

    # ------------------------------------------------------------ waits
    def wait_for_seq(self, seq: int, label: str) -> None:
        """Poll origin's `main` until a commit carries `Register-Seq: <seq>`."""
        deadline = time.monotonic() + SETTLE_S
        while seq not in self.origin_seqs():
            assert time.monotonic() < deadline, (
                f"{label}: no commit on origin's main carries Register-Seq: {seq} within "
                f"{SETTLE_S} s (the render a write forks: lane 4's T416, lane 3's T321 to T323): "
                f"{self.origin_seqs()[-6:]}")
            time.sleep(0.25)

    def wait_renderer_exit(self, failed_before: int, label: str) -> None:
        """Open point 8's second wait: a `fetch` the wrapper failed since
        `failed_before`, then the render lock free."""
        deadline = time.monotonic() + SETTLE_S
        while not (self.host.failed_fetches() > failed_before
                   and _lock_free(self.host.render_lock())):
            assert time.monotonic() < deadline, (
                f"{label}: the renderer the write forked did not fail its fetch and exit within "
                f"{SETTLE_S} s (lane 4's T416; lane 3's T321 to T323): "
                f"{[c['sub'] + ':' + c['outcome'] for c in self.host.git_calls()][-8:]}")
            time.sleep(0.25)

    def settled(self, seq: int, label: str) -> None:
        """After a write on primary with fetches working: its render on
        origin, the renderer gone, ws1's checkout fetched, a lag of 0."""
        self.wait_for_seq(seq, label)
        deadline = time.monotonic() + SETTLE_S
        while not _lock_free(self.host.render_lock()):
            assert time.monotonic() < deadline, f"{label}: the renderer never released its lock"
            time.sleep(0.25)
        self.host.git("fetch", "-q", "origin")
        while True:
            proc = self.host.index("status", timeout=120)
            if LAG_0.search(proc.stdout):
                return
            assert time.monotonic() < deadline, (
                f"{label}: `status` shows no lag of 0 within {SETTLE_S} s (lane 1's T117):\n"
                f"{_said(proc)}")
            time.sleep(0.25)

    # ------------------------------------------------------------ A
    def a_to_primary(self) -> None:
        """`import --at C`, the first cutover with its marker, then
        `set-mode primary`, all from ws1 at A."""
        self.host.git("fetch", "-q", "origin")
        self.host.git("merge", "-q", "--ff-only", "refs/remotes/origin/main")
        self.c = self.origin_tip()
        proc = self.host.index("import", "--at", self.c, timeout=400)
        assert proc.returncode == 0, (
            f"[A] `import --at {self.c[:12]}` from ws1 failed (lane 1's T115, L1-A13):\n"
            f"{_said(proc)}")
        proc = self.host.index("cutover", "--import", self.c)
        assert proc.returncode == 0, (
            f"[A] `cutover --import {self.c[:12]}` failed (lane 1's T116, L1-A14):\n{_said(proc)}")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), (
            f"[A] after the cutover the switch reads {switch['mode']} with the marker "
            f"{switch['marker_state']}: the marker's push, its read-back and record_marker are "
            f"lane 3's T327, so this fails until it lands")
        self.cut = _rows(self.db, "SELECT seq FROM journal WHERE kind = 'cutover'")[0]["seq"]
        self.marker = self.origin_tip()
        self.generation_a = switch["generation"]
        flip = self.host.index("set-mode", "primary", "--config", str(self.host.conf))
        assert flip.returncode == 0, f"[A] `set-mode primary` (lane 1's T120):\n{_said(flip)}"

    def write(self, label: str, text: str) -> int:
        """`log NOTED` on primary from ws1 (R3b's smoke test's verb): exit 0
        and one journal entry, at the head plus 1. Returns its seq."""
        before = self.head()
        proc = self.host.edit("log", "NOTED", f"lane:{OPERATOR}", text)
        assert proc.returncode == 0, (
            f"{label}: `log NOTED` on primary from ws1 failed (lane 4's T415):\n{_said(proc)}")
        rows = _rows(self.db, f"SELECT seq, kind, lane FROM journal WHERE seq > {before} "
                              f"ORDER BY seq")
        assert rows == [{"seq": before + 1, "kind": "write", "lane": OPERATOR}], (
            f"{label}: the write's row is not the head plus 1: {rows}")
        return before + 1

    def a_written(self, *, lost: int = LOST, backup_after: int | None = None) -> None:
        """A through `m`, rendered, then `lost` writes no render reaches (a
        fetch that fails), each waited for by the renderer's exit; the
        backup after `backup_after` of them. `status` then shows `k - m`."""
        for n in range(1, RENDERED + 1):
            seq = self.write("[A]", f"T274: write {n}, rendered")
            self.settled(seq, f"[A] write {n}")
        self.m = self.head()
        assert max(self.origin_seqs()) == self.m, (
            f"[A] origin's last Register-Seq is not m = {self.m}: {self.origin_seqs()[-4:]}")
        self.host.arm(fail=["fetch"])
        for n in range(1, lost + 1):
            failed = self.host.failed_fetches()
            self.write("[A]", f"T274: write {RENDERED + n}, never rendered")
            self.wait_renderer_exit(failed, f"[A] lost write {n}")
            if backup_after == n:
                self.take_backup()
        self.k = self.head()
        assert max(self.origin_seqs()) == self.m, (
            f"[A] a render reached origin while every fetch failed: {self.origin_seqs()[-4:]}")
        status = self.host.index("status", timeout=120)
        lag = LAG_N.search(status.stdout)
        # Not its exit: that is #160's index's too, 1 on ws1 (see the readings).
        assert status.returncode != 69 and lag and int(lag.group(1)) == self.k - self.m, (
            f"[A] `status` at A does not show a lag of k - m = {self.k - self.m} (lane 1's "
            f"T117):\n{_said(status)}")
        # Every renderer has exited: the wrapper lets git through again, for B.
        self.host.arm()

    def take_backup(self) -> None:
        """O2's dump of A as `lanes_register_dump`, then `b` read from the
        file alone, equal to A's head when the dump was taken."""
        head = self.head(self.a_db)
        target = self.root / "backup" / "lanes-register.dump"
        target.parent.mkdir(parents=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
        env.update(PGHOST="localhost", PGHOSTADDR="127.0.0.1", PGPORT=str(self.a.port),
                   PGUSER=FX_DUMP, PGDATABASE=self.a_db.name, PGSSLMODE="verify-full",
                   PGSSLROOTCERT=str(self.a.root_cert), PGPASSFILE=str(self.a_files[FX_DUMP]),
                   PGCONNECT_TIMEOUT="10", LC_ALL="C",
                   PATH=os.pathsep.join([str(self.a.bindir), os.environ.get("PATH", "")]))
        proc = subprocess.run(["bash", "-c", DUMP_COMMAND.format(file=target)], env=env,
                              capture_output=True, text=True, timeout=300,
                              stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0 and target.exists(), (
            f"[backup] O2's pg_dump as {FX_DUMP} failed (T110's dump login; T224):\n{_said(proc)}")
        read = subprocess.run([self.a.tool("pg_restore"), "--data-only", f"--schema={SCHEMA}",
                               "--table=register_head", "--file=-", str(target)],
                              capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, check=False)
        block = re.search(r"^COPY \S*register_head \(([^)]*)\) FROM stdin;\n([^\n]*)\n",
                          read.stdout, re.M)
        assert read.returncode == 0 and block, (
            f"[backup] pg_restore --data-only gives no register_head row:\n{_said(read)}")
        columns = [c.strip().strip('"') for c in block.group(1).split(",")]
        b = int(block.group(2).split("\t")[columns.index("seq")])
        assert b == head, f"[backup] the dump's head is {b}, not A's head {head} when it was taken"
        self.b_seq, self.dump = b, target

    def in_doubt_write(self) -> dict:
        """A write on A whose commit call is lost before its COMMIT: exit 3,
        its record kept, its printed rerun (lane 4's T412, T415 and T417).
        Returns the argv, the id, the generation and the record."""
        argv = ["log", "NOTED", f"lane:{OPERATOR}", "T274: the write in doubt when A was lost"]
        head = self.head()
        self.host.arm(psql_arms=[NO_RECONNECT])
        proc = self.host.edit(*argv)
        self.host.arm()
        assert proc.returncode == 3, (
            f"[record] a write whose commit call is lost is not 3 with its rerun printed (lane "
            f"4's T417):\n{_said(proc)}")
        ids, gens = WRITE_ID_SAID.findall(proc.stderr), GENERATION_SAID.findall(proc.stderr)
        assert ids and gens, f"[record] exit 3 printed no LANES_WRITE_ID rerun:\n{_said(proc)}"
        records = self.host.pending()
        assert len(records) == 1, f"[record] {len(records)} pending records, not one (T412)"
        assert gens[-1] == self.generation_a, (
            f"[record] the printed rerun's generation is {gens[-1]}, not A's {self.generation_a}")
        assert self.head() == head == self.m, (
            f"[record] the lost call moved the head: {self.head()}, not m = {self.m}")
        return {"argv": argv, "id": ids[-1], "generation": gens[-1], "path": records[0],
                "bytes": records[0].read_bytes()}

    def loss_recorded(self) -> None:
        """`status` at A records `h`; A stops; `status` prints `m` and `h` and
        exits 69; the outage is declared on ws1."""
        status = self.host.index("status", timeout=120)
        read = REGISTER_N.search(status.stdout)
        assert status.returncode != 69 and read and int(read.group(1)) == self.k, (
            f"[loss] `status` at A does not read A's head k = {self.k}, so it records no h "
            f"(lane 1's T117):\n{_said(status)}")
        self.a.stop()
        status = self.host.index("status", timeout=120)
        mirror, last = MIRROR_M.search(status.stdout), LAST_HEAD.search(status.stdout)
        assert status.returncode == 69 and mirror and last, (
            f"[loss] `status` with A stopped does not exit 69 printing the mirror's m and the "
            f"last head it recorded (lane 1's T117; ops 2.3, step 4):\n{_said(status)}")
        self.h = int(last.group(1))
        assert (int(mirror.group(1)), self.h) == (self.m, self.k), (
            f"[loss] `status` prints m {mirror.group(1)} and h {self.h}, not m {self.m} and "
            f"h {self.k}:\n{_said(status)}")
        declared = self.host.index("outage", "declare", "--until", UNTIL, "--why", WHY)
        assert declared.returncode == 0 and self.host.outage_file().exists(), (
            f"[loss] `outage declare` on ws1 declared nothing (lane 1's T121, L1-A18):\n"
            f"{_said(declared)}")

    def a_destroyed(self) -> None:
        self.a.destroy()

    # ------------------------------------------------------------ B
    def b_reimport_route(self) -> None:
        """R-P41's re-import route on B: `--roles-only`, `bootstrap`, the
        logins made again after it, the re-pointing."""
        self.new_b()
        self.b_bootstrap(roles_only=True)
        self.b_bootstrap()
        self.b_logins()
        self.repoint()

    def b_restore_route(self) -> subprocess.CompletedProcess:
        """R-P41's restore route on B: `--roles-only`, the logins, the
        restore of A's dump, `bootstrap` again, the re-pointing. Returns the
        second bootstrap."""
        self.new_b()
        self.b_bootstrap(roles_only=True)
        self.b_logins()
        env = {k: v for k, v in self.b.admin_env().items() if not k.startswith("PG")}
        env["PGSERVICE"] = self.b.admin_service(self.b_db.name)
        restore = subprocess.run([self.b.tool("pg_restore"), "--exit-on-error", "--no-password",
                                  f"--dbname={self.b_db.name}", str(self.dump)],
                                 capture_output=True, text=True, timeout=300, env=env,
                                 stdin=subprocess.DEVNULL, check=False)
        assert restore.returncode == 0, (
            f"[restore] pg_restore of A's dump through the admin service failed:\n"
            f"{_said(restore)}")
        again = self.b_bootstrap()
        self.repoint()
        return again

    def reimport(self) -> str:
        """`import --at <M> --after-loss` from ws1, M origin's tip: B's head
        is `m`, and the journal's one root sits there. Returns M."""
        self.host.git("fetch", "-q", "origin")
        self.host.git("merge", "-q", "--ff-only", "refs/remotes/origin/main")
        tip = self.origin_tip()
        proc = self.host.index("import", "--at", tip, "--after-loss", timeout=400)
        assert proc.returncode == 0, (
            f"[re-import] `import --at {tip[:12]} --after-loss` failed (lane 1's T115, "
            f"L1-A13):\n{_said(proc)}")
        assert (self.head(), self.journal()) == (self.m, [[self.m, "import", False]]), (
            f"[re-import] B's head is {self.head()} with the journal {self.journal()}, not m = "
            f"{self.m} with its one root there")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"], switch["database_label"]) == (
            "files", "absent", LABEL_B), f"[re-import] B's switch after the import: {switch}"
        self.generation_boot = switch["generation"]
        return tip

    def cutover_after_loss(self, tip: str | None) -> subprocess.CompletedProcess:
        """`cutover --import <M> --after-loss` (the re-import's form), or
        `cutover --after-loss` (the restore's), from ws1 at B."""
        args = ["cutover", "--import", tip, "--after-loss"] if tip else ["cutover", "--after-loss"]
        return self.host.index(*args)

    def marker_rewritten(self, proc, seq: int, label: str) -> str:
        """The after-loss cutover's oracle: exit 0; the switch at `primary`
        with the marker `present`, B's label, a new generation and `set_seq`
        its own seq; the entry an operator entry; origin's tip its marker
        commit, carrying `Register-Seq: <seq>`, changing `lanes/STORE` alone,
        whose `database=` names B. Returns the marker commit."""
        assert proc.returncode == 0, (
            f"{label}: the after-loss cutover failed (lane 1's T116, L1-A14; its push, and the "
            f"restore form's render, are lane 3's T327):\n{_said(proc)}")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), (
            f"{label}: after the cutover B's switch reads {switch['mode']} with the marker "
            f"{switch['marker_state']}: the marker's push, read-back and record_marker are lane "
            f"3's T327")
        assert (switch["database_label"], switch["set_seq"]) == (LABEL_B, seq), (
            f"{label}: B's switch names {switch['database_label']} at set_seq "
            f"{switch['set_seq']}, not {LABEL_B} at {seq}")
        assert switch["generation"] not in (self.generation_a, self.generation_boot), (
            f"{label}: the after-loss cutover set no new generation: {switch['generation']}")
        assert self.journal()[-1] == [seq, "cutover", True], (
            f"{label}: the journal's last entry is not the cutover's operator entry at {seq}: "
            f"{self.journal()[-3:]}")
        tip = self.origin_tip()
        assert self.seqs_of(tip) == [seq] and switch["marker_commit"] == tip, (
            f"{label}: origin's tip {tip[:12]} is not the recorded marker commit carrying "
            f"Register-Seq: {seq} (T327)")
        assert self.changed_paths(tip) == ["M\tlanes/STORE"], (
            f"{label}: the marker commit does not rewrite lanes/STORE alone: "
            f"{self.changed_paths(tip)}")
        store = self.store_on_origin(tip) or {}
        assert (store.get("store"), store.get("database")) == ("primary", LABEL_B), (
            f"{label}: lanes/STORE on origin does not name B: {store}")
        return tip

    def resumed(self) -> None:
        """ops 2.3's step 7: `outage clear` on ws1 removes the declaration."""
        cleared = self.host.index("outage", "clear")
        assert cleared.returncode == 0 and not self.host.outage_file().exists(), (
            f"[resumption] `outage clear` on ws1 left the declaration (lane 1's T121):\n"
            f"{_said(cleared)}")


def _estate(request, tmp_path: Path) -> Disaster:
    return Disaster(request, tmp_path)


# =================================================================== AT-D22
def test_the_disaster_path_reimports_at_the_mirrors_tip_and_continues_the_sequence(request,
                                                                                  tmp_path):
    """AT-D22's re-import: after the loss, B's `--roles-only`, `bootstrap`
    and logins, and the re-pointing, `import --at <M> --after-loss` puts B's
    head at `m` with its one root there; `cutover --import <M> --after-loss`
    writes its operator entry at `m+1`, sets B's label, a new generation and
    `set_seq` `m+1`, and pushes `lanes/STORE` naming B; the declaration
    cleared, the next write is `m+2`, its render follows the marker commit,
    the lag is 0, and the mirror equals a full render from B. Each login's
    new password file connects to B, and its old one is refused. Fails until
    L1-A7, L1-A13 and T327 land, and lane 4's T415 and T416."""
    estate = _estate(request, tmp_path)
    estate.a_to_primary()
    estate.a_written()
    estate.loss_recorded()
    estate.a_destroyed()
    estate.b_reimport_route()
    tip = estate.reimport()
    for login in LOGINS:
        assert _connects(estate.b, login, estate.b_db.name, estate.b_files[login]), (
            f"[logins] after the re-import, {login} does not log in to B with its new password "
            f"file (T110)")
        assert not _connects(estate.b, login, estate.b_db.name, estate.a_files[login]), (
            f"[logins] {login}'s old password file logs in to B")
    m = estate.m
    marker = estate.marker_rewritten(estate.cutover_after_loss(tip), m + 1, "[cutover]")
    estate.resumed()
    seq = estate.write("[next write]", "T274: the first write on B")
    assert seq == m + 2, f"[next write] the next write is seq {seq}, not m+2 = {m + 2}"
    estate.settled(seq, "[next write]")
    assert [seqs for _sha, seqs in estate.commits_after(marker)] == [[m + 2]], (
        f"[next write] its render does not follow the marker commit: "
        f"{estate.commits_after(marker)}")
    problem = estate.mirror_problem()
    assert problem is None, f"[mirror] the mirror is not a full render from B: {problem}"


def test_a_backup_newer_than_the_mirror_is_restored_and_rendered(request, tmp_path):
    """AT-D22's restore: with `m < b < k`, B restored from the dump holds the
    journal through `b`, its switch at `primary` with the marker `present` and
    A's label, which the second `bootstrap` keeps (every object `unchanged`);
    `cutover --after-loss` renders `m+1` to `b`, in order, then writes its
    entry at `b+1`, rewriting `lanes/STORE` to name B; the next write is
    `b+2`, and `status`'s `m` and `h`, read before B existed, put the loss at
    `b+1` to `k`. Fails until L1-A7, L1-A13 and T327 land, and lane 4's T415
    and T416."""
    estate = _estate(request, tmp_path)
    estate.a_to_primary()
    estate.a_written(backup_after=BACKUP_AFTER)
    estate.loss_recorded()
    estate.a_destroyed()
    again = estate.b_restore_route()
    m, b, k = estate.m, estate.b_seq, estate.k
    assert m < b < k, f"[backup] not m < b < k: {m}, {b}, {k}"
    assert [row[0] for row in estate.journal()] == list(range(0, b + 1)), (
        f"[restore] B's journal is not seqs 0 to b = {b}: {estate.journal()[-4:]}")
    switch = estate.switch()
    assert (switch["mode"], switch["marker_state"], switch["database_label"]) == (
        "primary", "present", LABEL_A), (
        f"[restore] B's restored switch is not A's, primary with the marker present: {switch}")
    states = {state for _what, state in OBJECT_LINE.findall(again.stdout)}
    assert states == {"unchanged"}, (
        f"[restore] the second bootstrap did not print unchanged for every object (T109):\n"
        f"{_said(again)}")
    before = estate.origin_tip()
    assert max(estate.origin_seqs()) == m, f"[restore] origin is not at m = {m}"
    marker = estate.marker_rewritten(estate.cutover_after_loss(None), b + 1, "[cutover]")
    rendered = estate.commits_after(before)
    assert [seqs for _sha, seqs in rendered] == [[n] for n in range(m + 1, b + 2)], (
        f"[cutover] origin's commits after the restore are not the renders of m+1 to b, in "
        f"order, then the marker's at b+1 (lane 3's T327, ops:382): {rendered}")
    estate.resumed()
    seq = estate.write("[next write]", "T274: the first write on the restored B")
    assert seq == b + 2, f"[next write] the next write is seq {seq}, not b+2 = {b + 2}"
    estate.settled(seq, "[next write]")
    assert [seqs for _sha, seqs in estate.commits_after(marker)] == [[b + 2]], (
        f"[next write] its render does not follow the marker commit")
    assert estate.h == k and b + 1 <= k, (
        f"[loss] status's h {estate.h} does not put the loss at b+1 = {b + 1} to k = {k}")


def test_an_abort_after_a_restore_form_cutover_restores_every_table_byte_for_byte(request,
                                                                                 tmp_path):
    """AT-D22's abort: with the wrapper failing only the push of the commit
    carrying `Register-Seq: b+1`, the restore form's cutover pushes the
    renders of `m+1` to `b`, proves its own commit absent, and aborts with
    2: the twelve tables, dumped by the admin connection at head `b` before
    the cutover, equal the same dump after the abort, byte for byte, and the
    head is `b`. Fails until L1-A7, L1-A13 and T327 land, and lane 4's T415
    and T416."""
    estate = _estate(request, tmp_path)
    estate.a_to_primary()
    estate.a_written(backup_after=BACKUP_AFTER)
    estate.loss_recorded()
    estate.a_destroyed()
    estate.b_restore_route()
    m, b = estate.m, estate.b_seq
    before_dump, before_tip = _abort_dump(estate.b_db), estate.origin_tip()
    assert json.loads(before_dump["register_switch"])[0]["restore_prior"] is None, (
        "[abort] the restored switch already holds a restore_prior")
    estate.host.arm(fail_push_seq=b + 1)
    proc = estate.cutover_after_loss(None)
    first = (proc.stderr.splitlines() or [""])[0]
    assert proc.returncode == 2 and "abort" in first.lower(), (
        f"[abort] the cutover whose marker push failed did not abort with 2, its first stderr "
        f"line naming the abort (lane 3's T327; cutover_abort):\n{_said(proc)}")
    assert [c["seqs"] for c in estate.host.pushes() if c["outcome"] == "failed"] != [], (
        f"[abort] the wrapper failed no push of Register-Seq: {b + 1}")
    after = estate.commits_after(before_tip)
    assert [seqs for _sha, seqs in after] == [[n] for n in range(m + 1, b + 1)], (
        f"[abort] origin does not hold the renders of m+1 to b and nothing after them: {after}")
    assert estate.head() == b, f"[abort] the head is {estate.head()}, not b = {b}"
    after_dump = _abort_dump(estate.b_db)
    differ = [table for table in ABORT_TABLES if before_dump[table] != after_dump[table]]
    assert differ == [], (
        f"[abort] these tables differ from their dump before the cutover: {differ} "
        f"(switch_to_files at b+1)")


def test_status_prints_the_mirror_tip_and_the_last_head_that_bound_the_loss(request, tmp_path):
    """AT-D22's `status` before B exists: with A unreachable it exits 69 and
    prints `m`, the mirror tip's `Register-Seq`, and `h`, the last head it
    recorded, `k`, with a lag of at least `k - m`: the loss is `m+1` to `k`.
    Fails until L1-A13 and T327 land, and lane 4's T415 and T416."""
    estate = _estate(request, tmp_path)
    estate.a_to_primary()
    estate.a_written()
    estate.loss_recorded()
    status = estate.host.index("status", timeout=120)
    lag = LAG_AT_LEAST.search(status.stdout)
    assert status.returncode == 69 and lag and int(lag.group(1)) == estate.k - estate.m, (
        f"[status] the lag with A stopped is not at least k - m = {estate.k - estate.m} "
        f"(lane 1's T117):\n{_said(status)}")
    assert estate.m < estate.k == estate.h, (
        f"[status] the loss is not m+1 = {estate.m + 1} to k = {estate.k}: h = {estate.h}")


def test_the_restore_route_commits_under_the_replacements_register_label_and_check_10_fails_until_it_does(  # noqa: E501
        request, tmp_path):
    """AT-D22's restore route: on ws1, re-pointed at the restored B with B's
    label, `ready`'s check 10 fails naming B's label and A's, since the
    restored switch names A's; `cutover --after-loss` sends B's label and
    commits; the switch's `database_label` and `lanes/STORE`'s `database=`
    then name B, and check 10 is `ok` on the same host. Fails until L1-A7,
    L1-A13 and T327 land, and lane 4's T415 and T416."""
    estate = _estate(request, tmp_path)
    estate.a_to_primary()
    estate.a_written(backup_after=BACKUP_AFTER)
    estate.loss_recorded()
    estate.a_destroyed()
    estate.b_restore_route()
    ready = estate.host.index("ready", "--expect", "primary", "--release", RELEASE, "--env",
                              ENV_NAME)
    state, reason = _checks(ready.stdout).get(10, (None, ""))
    assert state == "FAIL" and LABEL_A in reason and LABEL_B in reason, (
        f"[check 10] before the cutover check 10 does not fail naming {LABEL_B} and {LABEL_A} "
        f"(lane 1's T119):\n{_said(ready)}")
    estate.marker_rewritten(estate.cutover_after_loss(None), estate.b_seq + 1, "[cutover]")
    ready = estate.host.index("ready", "--expect", "primary", "--release", RELEASE, "--env",
                              ENV_NAME)
    assert _checks(ready.stdout).get(10, (None, ""))[0] == "ok", (
        f"[check 10] after the cutover check 10 is not ok on the same host (T119):\n"
        f"{_said(ready)}")


def test_an_after_loss_cutover_from_a_host_still_on_the_live_database_is_refused_with_2_and_writes_nothing(  # noqa: E501
        request, tmp_path):
    """AT-D22's host still on the live database: with A at `primary`, a
    configuration that still reaches A with A's `register_label=` runs
    `cutover --after-loss`, which sends A's own label, the switch's: it
    exits 2, and A's head, its switch row, its journal and `lanes/STORE` on
    origin are as they were, with no push. Fails until T327 lands."""
    estate = _estate(request, tmp_path)
    estate.a_to_primary()
    stale = estate.root / "stale" / "lanes-index.conf"
    _private(stale, estate.host.conf.read_text(encoding="utf-8"))
    assert _fields(stale.read_text(encoding="utf-8"))["register_label"] == LABEL_A
    kept = (estate.head(), estate.switch(), estate.journal(), estate.origin_tip(),
            estate.store_on_origin())
    estate.host.arm()
    proc = estate.host.index("cutover", "--after-loss", env={"LANES_INDEX_CONFIG": str(stale)})
    assert proc.returncode == 2, (
        f"[live host] an after-loss cutover with A's own label at primary is not refused with 2 "
        f"(N4; lane 1's T116):\n{_said(proc)}")
    assert (estate.head(), estate.switch(), estate.journal(), estate.origin_tip(),
            estate.store_on_origin()) == kept, (
        "[live host] the refused cutover changed A's head, switch row or journal, or origin")
    assert estate.host.pushes() == [], f"[live host] it pushed: {estate.host.pushes()}"


# =================================================================== AT-F18
def _f18_estate(request, tmp_path: Path) -> tuple:
    """AT-F18's fixture: D22's re-import, with A written through `m` and the
    write in doubt at `m` (see the readings). Returns the estate and the
    record, with B bootstrapped and ws1 re-pointed at it."""
    estate = _estate(request, tmp_path)
    estate.a_to_primary()
    estate.a_written(lost=0)
    record = estate.in_doubt_write()
    estate.loss_recorded()
    estate.a_destroyed()
    estate.b_reimport_route()
    return estate, record


def _cut_over_on_b(estate: Disaster) -> None:
    """B's re-import, its after-loss cutover, and the declaration cleared."""
    tip = estate.reimport()
    estate.marker_rewritten(estate.cutover_after_loss(tip), estate.m + 1, "[cutover]")
    estate.resumed()


def test_a_pending_record_from_the_lost_database_is_refused_2_at_the_snapshot(request, tmp_path):
    """AT-F18: on B after its cutover, a plain rerun that meets A's record
    exits 2 at its first snapshot, naming the write id, both generations, the
    effect check and `LANES_WRITE_ID=new`, and leaves the record as it was;
    the printed rerun, under A's `LANES_WRITE_GENERATION=`, exits 2 at its
    snapshot with LR007's text. The shim logs no commit call for either, and
    the journal does not move. Fails until L1-A7, L1-A13 and T327 land, and
    lane 4's T412, T415 and T417."""
    estate, record = _f18_estate(request, tmp_path)
    _cut_over_on_b(estate)
    generation_b = estate.switch()["generation"]
    journal = estate.journal()
    estate.host.arm()
    plain = estate.host.edit(*record["argv"])
    assert plain.returncode == 2 and estate.host.commit_calls() == [], (
        f"[plain rerun] a plain rerun meeting A's record is not refused 2 before any commit "
        f"call (lane 4's T412, T415):\n{_said(plain)}")
    for said in (record["id"], record["generation"], generation_b, "LANES_WRITE_ID=new"):
        assert said in plain.stderr, (
            f"[plain rerun] the refusal does not name {said!r}:\n{_said(plain)}")
    assert [p.read_bytes() for p in estate.host.pending()] == [record["bytes"]], (
        "[plain rerun] A's record was not left as it was")
    estate.host.arm()
    printed = estate.host.edit(*record["argv"], env={
        "LANES_WRITE_ID": record["id"], "LANES_WRITE_GENERATION": record["generation"]})
    assert printed.returncode == 2 and estate.host.commit_calls() == [], (
        f"[printed rerun] the printed rerun under A's generation is not refused 2 at its "
        f"snapshot (lane 4's T412, T417):\n{_said(printed)}")
    for said in (record["id"], record["generation"], generation_b):
        assert said in printed.stderr, (
            f"[printed rerun] the refusal's LR007 text does not name {said!r}:\n{_said(printed)}")
    assert estate.journal() == journal, "[reruns] the refused reruns moved the journal"


def test_the_printed_rerun_between_a_reimports_bootstrap_and_its_cutover_exits_2_not_69(request,
                                                                                       tmp_path):
    """AT-F18: between B's re-import and its cutover, with B's switch at
    `files`, the printed rerun under A's generation exits 2, not 69, since
    the generation is checked before the switch; it sends no commit call and
    the journal holds the import's root alone. Fails until L1-A7, L1-A13 and
    T327 land, and lane 4's T412, T415 and T417."""
    estate, record = _f18_estate(request, tmp_path)
    estate.reimport()
    assert estate.switch()["mode"] == "files"
    estate.host.arm()
    proc = estate.host.edit(*record["argv"], env={"LANES_WRITE_ID": record["id"],
                                                  "LANES_WRITE_GENERATION": record["generation"]})
    assert proc.returncode == 2, (
        f"[between] the printed rerun before B's cutover is not 2 (the generation before the "
        f"switch; lane 4's T412, T417):\n{_said(proc)}")
    assert estate.host.commit_calls() == [], "[between] the printed rerun sent a commit call"
    assert record["id"] in proc.stderr and record["generation"] in proc.stderr, (
        f"[between] the refusal does not name A's write id and generation:\n{_said(proc)}")
    assert estate.journal() == [[estate.m, "import", False]], (
        f"[between] the journal moved: {estate.journal()}")


def test_lanes_write_id_new_on_the_replacement_replaces_the_old_record_and_writes_once(request,
                                                                                      tmp_path):
    """AT-F18's replacement: on B after its cutover, the effect check finds
    the write absent; the same command under `LANES_WRITE_ID=new` mints a new
    id, writes once, and leaves no record of A's generation; a plain rerun
    after it finds no record of A's. Fails until L1-A7, L1-A13 and T327 land,
    and lane 4's T412, T415, T416 and T417."""
    estate, record = _f18_estate(request, tmp_path)
    _cut_over_on_b(estate)
    text = record["argv"][-1]
    on_b = _rows(estate.db, "SELECT raw FROM log_lines")
    assert not any(text in row["raw"] for row in on_b), (
        "[effect check] the write in doubt is already on B")
    before = estate.head()
    estate.host.arm()
    proc = estate.host.edit(*record["argv"], env={"LANES_WRITE_ID": "new"})
    assert proc.returncode == 0, (
        f"[new] the command under LANES_WRITE_ID=new did not write (lane 4's T412, T415):\n"
        f"{_said(proc)}")
    rows = _rows(estate.db, f"SELECT seq, write_id::text AS id FROM journal WHERE seq > {before} "
                            f"ORDER BY seq")
    assert len(rows) == 1 and rows[0]["id"] != record["id"], (
        f"[new] the journal did not gain exactly one write under a new id: {rows}")
    assert {c["stdin"].count(rows[0]["id"]) > 0 for c in estate.host.commit_calls()} == {True}, (
        "[new] a commit call carried another write id")
    left = [p.read_text(encoding="utf-8") for p in estate.host.pending()]
    assert not any(record["generation"] in text_ or record["id"] in text_ for text_ in left), (
        "[new] a record of A's generation is left")
    again = estate.host.edit(*record["argv"])
    assert again.returncode == 0 and record["id"] not in again.stderr and \
        record["generation"] not in again.stderr, (
            f"[plain rerun] a plain rerun after the replacement met A's record:\n{_said(again)}")


@pytest.mark.parametrize("case", ["no-label-reimport", "no-label-restore", "own-label-at-primary",
                                  "reimport-at-files"])
def test_the_after_loss_cutovers_label_rules_in_the_transaction(pg, case):
    """AT-F18's label rules, by direct `commit_write` calls as REGISTER-WRITER
    on a bootstrapped register (N4; lane 1's v2.6, behaviour 5): an after-loss
    `cutover` entry with no `database_label` is LR004, after an after-loss
    import (`[no-label-reimport]`) and on a switch at `primary` with the
    marker `present` (`[no-label-restore]`); one that meets that switch with
    the switch's own label is LR004 (`[own-label-at-primary]`); each writes
    nothing. After an after-loss import at `files`, where the switch holds the
    replacement's own label, the label is not compared, and the entry commits
    (`[reimport-at-files]`). Fails until T107 and T109 land (L1-A6, L1-A7)."""
    labels = LabelRules(pg)
    own = labels.switch()["database_label"]
    if case in ("no-label-reimport", "reimport-at-files"):
        root = labels.commit(labels.head(), labels.import_entry(root_seq=M_DIRECT), "the import")
        assert root == M_DIRECT, f"[{case}] the after-loss import's root is {root}, not m"
        base = root
    else:
        base = labels.to_primary()
    switch = {"after_loss": True}
    if case in ("own-label-at-primary", "reimport-at-files"):
        switch["database_label"] = own
    kept = labels.state()
    proc = labels.send(base, labels.cutover_entry(own, switch=switch))
    if case == "reimport-at-files":
        assert proc.returncode == 0, (
            f"[{case}] the re-import form at files with the switch's own label did not commit "
            f"(T107):\n{_said(proc)}")
        after = labels.switch()
        assert (after["mode"], after["database_label"], after["set_seq"], labels.head()) == (
            "primary", own, base + 1, base + 1), f"[{case}] after the entry: {after}"
        assert after["generation"] != kept["switch"]["generation"], (
            f"[{case}] the after-loss entry kept the generation")
    else:
        assert proc.returncode != 0 and "LR004" in proc.stderr, (
            f"[{case}] the entry is not refused with LR004 (N4; T107):\n{_said(proc)}")
        assert labels.state() == kept, f"[{case}] the refused entry wrote something"


def test_bootstrap_roles_only_makes_the_roles_and_no_schema(request, tmp_path):
    """AT-F18: on cluster B, new, with no register role, `bootstrap
    --roles-only` through the admin service makes the owner, the two groups
    and the indexer, and no schema; and the three database-level statements
    hold as T224's `dump_restore_privileges` asserts them: PUBLIC has no
    CONNECT on the database, the writer, the reader and the indexer have it,
    and the owner's global default privilege gives PUBLIC no EXECUTE on its
    functions. Fails until T109 lands (L1-A7)."""
    estate = Roles(request, tmp_path)
    found = estate.roles()
    assert found == [], f"[roles-only] B already has register roles: {found}"
    estate.roles_only()
    assert estate.roles() == sorted(REGISTER_ROLES), (
        f"[roles-only] B's register roles after --roles-only: {estate.roles()}")
    schemas = _value(estate.db, f"SELECT count(*) FROM pg_namespace WHERE nspname = '{SCHEMA}';")
    assert schemas == "0", "[roles-only] --roles-only created the register's schema"
    acl = _value(estate.db, f"SELECT coalesce(datacl::text, '') FROM pg_database "
                            f"WHERE datname = '{estate.db.name}';")
    assert not re.search(r"(^|[{,])=[A-Za-z]*c", acl), f"[roles-only] PUBLIC holds CONNECT: {acl}"
    estate.db.psql("CREATE ROLE t274_outsider NOLOGIN;")
    assert _value(estate.db, f"SELECT has_database_privilege('t274_outsider', "
                             f"'{estate.db.name}', 'CONNECT');") == "f", (
        "[roles-only] a role outside the register may connect")
    for role in (WRITER_GROUP, "lanes_register_reader", "lanes_indexer"):
        assert _value(estate.db, f"SELECT has_database_privilege('{role}', '{estate.db.name}', "
                                 f"'CONNECT');") == "t", f"[roles-only] {role} holds no CONNECT"
    default = _value(estate.db, "SELECT coalesce(string_agg(defaclacl::text, ' '), '') FROM "
                                "pg_default_acl WHERE defaclrole = 'lanes_register_owner'::regrole "
                                "AND defaclnamespace = 0 AND defaclobjtype = 'f';")
    assert default and not re.search(r"(^|[{,])=[A-Za-z]*X", default), (
        f"[roles-only] the owner's global default privilege on functions is {default!r}: PUBLIC "
        f"keeps EXECUTE, or the statement made no row")


def test_the_disaster_path_rewrites_the_marker_by_the_after_loss_cutover(request, tmp_path):
    """AT-F18: the marker is rewritten by the cutover's own entry in its
    after-loss form at `m+1`, never a third operator entry: `lanes/STORE`'s
    `database=` names B, and in its life on B the journal holds exactly two
    operator entries, the cutover's at `m+1` and, after the smoke test and a
    later rollback, the rollback's. Fails until L1-A7, L1-A13 and T327 land,
    and lane 4's T415 and T416, T304 and lane 3's T326."""
    estate, _record = _f18_estate(request, tmp_path)
    _cut_over_on_b(estate)
    m = estate.m
    seq = estate.write("[smoke]", "T274: the smoke test on B")
    estate.settled(seq, "[smoke]")
    proc = estate.host.index("rollback")
    assert proc.returncode == 0, (
        f"[rollback] the rollback on B (T304, lane 3's T326):\n{_said(proc)}")
    switch = estate.switch()
    assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), (
        f"[rollback] after the rollback B's switch is {switch}")
    operators = [row[:2] for row in estate.journal() if row[2]]
    assert operators == [[m + 1, "cutover"], [seq + 1, "rollback"]], (
        f"[marker] B's journal does not hold exactly the after-loss cutover's and the "
        f"rollback's operator entries: {operators}")


# ------------------------------------------------------------------ the direct calls
#: The label rules' after-loss import root, an `m` of the test's own.
M_DIRECT = 7
#: What the direct entries carry (AT-LR006's, T273's).
COMMIT_C, TREE_C, MARKER_COMMIT = "c" * 40, "d" * 40, "e" * 40
NOT_AFTER = "2100-01-01T00:00:00Z"
LANES_MD = ["# Lanes"]
DIRECT_LANE, DIRECT_WS = "t274-operator", "ws-t274"
DIRECT_AUTHOR = "T274 operator <t274@example.invalid>"


def _sha(lines) -> str:
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def _entry(kind: str, **parts) -> dict:
    """One `commit_write` entry: the journal object, `not_after`, and `parts`."""
    journal = {"kind": kind, "verb": kind, "lane": DIRECT_LANE, "workstation": DIRECT_WS,
               "author": DIRECT_AUTHOR, "message": f"t274: {kind}"}
    journal.update(parts.pop("journal", {}))
    return {"journal": journal, "not_after": NOT_AFTER, **parts}


class LabelRules:
    """A clone of the session's template (T227), bootstrapped with its label,
    and `commit_write` sent as the writer sends it, as REGISTER-WRITER."""

    def __init__(self, pg):
        self.db = pg

    def psql(self, script: str, role: str | None = None) -> subprocess.CompletedProcess:
        head = "\\set VERBOSITY verbose\n\\set SHOW_CONTEXT never\nSET client_encoding = 'UTF8';\n"
        if role:
            head += f"SET ROLE {role};\n"
        return subprocess.run([self.db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                              input=head + script, capture_output=True, encoding="utf-8",
                              errors="replace", env=self.db.env(appname="t274"), timeout=120,
                              check=False)

    def switch(self) -> dict:
        return _rows(self.db, "SELECT * FROM register_switch")[0]

    def head(self) -> int:
        return _rows(self.db, "SELECT seq FROM register_head")[0]["seq"]

    def state(self) -> dict:
        return {"switch": self.switch(), "head": self.head(),
                "journal": _rows(self.db, "SELECT seq, kind FROM journal ORDER BY seq"),
                "files": _rows(self.db, "SELECT path, final_newline, sha256, last_seq FROM files "
                                        "ORDER BY path")}

    def send(self, base: int, entry: dict) -> subprocess.CompletedProcess:
        literal = json.dumps(entry, ensure_ascii=True).replace("'", "''")
        version = _rows(self.db, "SELECT version FROM schema_version")[0]["version"]
        return self.psql(f"BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
                         f"SELECT {SCHEMA}.commit_write({base}, '{uuid.uuid4()}'::uuid, "
                         f"{version}, '{self.switch()['generation']}'::uuid, "
                         f"'{literal}'::jsonb);\nCOMMIT;\n", WRITER_GROUP)

    def commit(self, base: int, entry: dict, what: str) -> int:
        proc = self.send(base, entry)
        assert proc.returncode == 0, f"[setup] {what}: commit_write refused it:\n{_said(proc)}"
        return int(proc.stdout.strip().splitlines()[-1])

    def import_entry(self, **parts) -> dict:
        edits = [{"ord": 1, "op": "create", "path": "lanes/LANES.md"}]
        edits += [{"ord": n, "op": "append", "path": "lanes/LANES.md", "new_text": text}
                  for n, text in enumerate(LANES_MD, start=2)]
        return _entry("import", journal={"git_commit": COMMIT_C, "git_tree": TREE_C},
                      edits=edits, files=[{"path": "lanes/LANES.md", "present": True,
                                           "sha256": _sha(LANES_MD), "final_newline": True}],
                      **parts)

    def cutover_entry(self, label: str, **parts) -> dict:
        lines = ("store=primary", f"database={label}", f"import={COMMIT_C}",
                 f"lanes-tree={TREE_C}", "utc=2026-11-12T00:00:00Z")
        edits = [{"ord": 1, "op": "create", "path": "lanes/STORE"}]
        edits += [{"ord": n, "op": "append", "path": "lanes/STORE", "new_text": line}
                  for n, line in enumerate(lines, start=2)]
        return _entry("cutover", edits=edits, files=[{"path": "lanes/STORE", "present": True,
                                                      "sha256": _sha(lines),
                                                      "final_newline": True}], **parts)

    def to_primary(self) -> int:
        """AT-LR006's route: an import at 0, a cutover over it, then
        `record_marker`. Returns the head."""
        imported = self.commit(self.head(), self.import_entry(), "the import")
        own = self.switch()["database_label"]
        cut = self.commit(imported, self.cutover_entry(own), "the cutover")
        version = _rows(self.db, "SELECT version FROM schema_version")[0]["version"]
        proc = self.psql(f"SELECT {SCHEMA}.record_marker({version}, {cut}, '{MARKER_COMMIT}', "
                         f"'{DIRECT_WS}');", WRITER_GROUP)
        assert proc.returncode == 0 and proc.stdout.strip().endswith("present"), (
            f"[setup] record_marker did not answer present:\n{_said(proc)}")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
        return cut


class Roles:
    """Cluster B alone, new, for `--roles-only`: a TLS cluster whose template
    holds nothing, its one database the register's, and the admin service
    naming it."""

    def __init__(self, request, root: Path):
        engine = request.getfixturevalue("pg_engine")
        cluster = TLSCluster(engine.bindir, "")
        try:
            cluster.start()
        except (ClusterError, OSError, subprocess.SubprocessError) as exc:
            cluster.destroy()
            raise AssertionError(f"[B] the replacement's cluster did not start: {exc}") from exc
        request.addfinalizer(cluster.destroy)
        self.cluster, self.db = cluster, Database(cluster, cluster.database_name)

    def roles(self) -> list:
        names = ", ".join(f"'{role}'" for role in REGISTER_ROLES)
        return sorted(_value(self.db, f"SELECT string_agg(rolname, ' ') FROM pg_roles "
                                      f"WHERE rolname IN ({names});").split())

    def roles_only(self) -> None:
        proc = self.cluster.lanes_index(["bootstrap", "--admin-service",
                                         self.cluster.admin_service(self.db.name),
                                         "--roles-only", "--no-passwords"])
        assert proc.returncode == 0, (
            f"[roles-only] `bootstrap --roles-only` through the admin service failed (lane 1's "
            f"T109, L1-A7):\n{_said(proc)}")
