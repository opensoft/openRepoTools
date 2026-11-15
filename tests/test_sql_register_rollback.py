# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 8, section 4.2 and AT-F1: the rollback (L2-G4; L2-G5's
AT-F1; AT-8; T273; FR-051, FR-052, FR-059; also US6) (opensoft/openRepoTools#165).

T273 writes this module: 21 tests, 20 from AT-8 (11), AT-F1 (7) and section
4.2 (2), and T304's own (R-F10-34), and T273d a 22nd: AT-F2's rollback rerun
after a 3 with a files-mode write between (lane 3's #165 6814260122), not yet
in B15's T273 text. T304's own test,
`test_rollback_steps_0_and_1_run_only_against_a_scratch_schema` (NOTES
question 6; B10 tasks:1011-1024; `PLACEMENT.md` section 4), is phase 1's,
and lane 3's T304 selects it with its word `sql_register_rollback and
scratch`: those six ids and nothing else. No other name or id in this module
holds that word. The other 20 (T273b) are after it, with their own notes.

T304'S OWN TEST: steps 0 and 1 of `lanes-index rollback` (lane 3's T304), run
by the shipped `lanes-index` with Q6(c)'s constant unset (`RENDER_GIT_HALF =
False`), as the operator lane, `LANES_LANE=<operator lane>` (B10 tasks:1015),
with this workstation's name and git's author set, on a database of the
session cluster that `lanes-index bootstrap` made for a scratch
`register_schema=` (T109's DEC-23 rendering), brought to `primary` with the
marker `present` by AT-LR006's route (TP:4610-4615). A scratch schema is any
`register_schema=` but the default `lanes_register` (Y:2323; lane 2's
reading). Its ids:

  * `[diverged-refuses-2]`: with `mirror_state.diverged_sha` set, it exits 2,
    and the switch, the marker and the head do not move (B10 tasks:1016);
  * `[step-1-one-transaction]`: one transaction leaves the switch at `files`,
    the head at `k+1`, an operator entry removing `lanes/STORE` last, and the
    marker `removing` (tasks:1017). The case asserts the database's state, not
    the exit after step 1, which T326's steps follow;
  * `[outage-declared-with-mirror-seq]`: its start declares the outage,
    marked as from a rollback, through `outage declare --rollback --mirror-seq
    <k>` (tasks:1020; T121);
  * `[lost-turn-rechecks-step-0]`: a second session holds the head row past
    `rollback`'s `lock_timeout`, so step 1 meets 55P03, and records a
    divergence meanwhile; once released, the rollback goes back to step 0 with
    the head read afresh and exits 2, with the switch and the marker unchanged
    (tasks:1018, :1016);
  * `[database-unreachable-69]`: 69, with neither the switch nor the marker
    changed (tasks:1021);
  * `[not-a-scratch-schema-2]`: with `register_schema=` unset and the constant
    unset, 2 (tasks:1023; `exit-codes.md` :145 at `23e4494`; Y:4872).

D7's 75 (tasks:1019) and the rerun's step 2 (tasks:1022) stay with the phase
G cases (T273b). Each id fails until T107, T109's rendering, T121 and T304
land (L1-A6, L1-A7, L1-A18; R-F10-34). Every id is RE: it asks for the
session cluster, and without PostgreSQL 16 it skips with T205's banner.

READINGS, NOT FOUND IN A CONTRACT:
- AT-LR006'S ROUTE is the documented functions as REGISTER-WRITER, by direct
  calls, as T231's cases reach `primary`: `commit_write` with an `import`
  entry at seq 0, then a `cutover` entry at 1, then `record_marker`, then one
  write at 2, so the rollback's `k` (2) is neither the import's seq nor the
  cutover's.
- "ONE TRANSACTION" is read as: of every `psql` call the rollback makes, one
  alone carries a function that writes (`commit_write`, `record_marker`,
  `switch_to_files`, `record_mirror_state`), and that call is step 1's one
  request, `BEGIN ISOLATION LEVEL SERIALIZABLE`, the `commit_write` call,
  then `COMMIT` (section 3.2's shim logs each call as sent). The database
  then holds what that one call leaves.
- THE SECOND SESSION of `[lost-turn-rechecks-step-0]` is the fixture's
  superuser holding `register_head`'s row `FOR UPDATE`. The divergence is
  recorded in that same session, as REGISTER-WRITER by `record_mirror_state`,
  so its `COMMIT` records it and releases the row at once. The shim holds the
  rollback's second read (the second call carrying `diverged_sha`) until
  then, so the read after the lost turn is the one that finds the divergence,
  whatever the machine's speed.
- "THE DATABASE UNREACHABLE" is a configuration whose URLs name the cluster's
  socket directory at a port where no server listens. The database itself,
  read by the test, shows the switch, the marker and the head unchanged.
- THE CONSTANT: the shipped `lanes-index` must carry `RENDER_GIT_HALF =
  False`. Each id says so where it does not (lane 3's T328 sets it True), since
  the scratch-schema rule holds only while it is unset. Once T328 has set it,
  with one `RENDER_GIT_HALF = True` line, each id skips before its setup,
  saying why (`CONSTANT_SET`; tasks:2511). Anything else fails.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from conftest import WINDOWS_SKIP
from pgcluster import SUPERUSER, Database
from sql_register_helpers import (LANES_INDEX, PSQL_SHIM, PSQL_SHIM_CONTROL, PSQL_SHIM_LOG,
                                  REGISTER_FAKE_PSQL, RENDER_GIT_HALF_LINE, flipped_copy,
                                  guard_strip_env)

pytestmark = [WINDOWS_SKIP]

#: THE LANDING GATE'S TABLE (T280; `tests/sql_register_gate.py` reads it): the
#: tasks each id waits for, from T273's Order (tasks:2512 at 204145ae). In a
#: gated run an id is skipped while any of its tasks has no marker in
#: `tests/sql_register_landed/`. T281 removes it with the gate.
SQL_REGISTER_GATE_TABLE = {
    "test_a_cutover_and_a_rollback_leave_exactly_two_operator_entries": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_a_files_mode_claim_after_rollback_leaves_one_holder": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_a_missed_primary_writer_is_refused_after_rollback": ("T111", "T121", "T304", "T326", "T327", "T415", "T416", "T420"),  # T273; tasks:2512
    "test_a_missed_writer_is_refused_once_the_partitioned_rollback_completes": ("T111", "T121", "T304", "T326", "T327", "T415", "T416", "T420"),  # T273; tasks:2512
    "test_a_reimport_after_a_rollback_continues_the_journal": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_a_rerun_after_an_unconfirmed_removal_and_a_files_mode_write_ends_0_with_the_marker_absent": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_a_rollback_entry_over_a_recorded_divergence_is_lr012": ("T107", "T109"),  # T273; tasks:2512
    "test_a_rollback_finds_a_stray_not_yet_recorded_records_it_and_exits_2": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_a_rollback_goes_back_to_its_check_on_each_lost_turn_code": ("T326",),  # T273; tasks:2512
    "test_a_rollback_goes_back_to_its_check_past_a_last_error_and_refuses_a_divergence_recorded_meanwhile": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_a_rollback_rerun_resumes_after_its_own_entry": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_a_rollback_retries_a_lost_turn_on_a_fresh_k_through_its_check": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_a_write_that_committed_before_the_rollback_is_found_by_its_rerun_after_it": ("T121", "T304", "T326", "T327", "T415", "T416", "T417"),  # T273; tasks:2512
    "test_rollback_exits_2_on_lr012_naming_the_divergence_and_both_ways_out": ("T107", "T109", "T121", "T304"),  # T273; tasks:2512
    "test_rollback_from_a_partitioned_clone_is_refused_and_removes_no_marker": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_rollback_leaves_files_byte_identical_marker_gone_and_sql_writes_refused": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_rollback_refuses_to_start_while_the_mirror_is_diverged": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_rollback_steps_0_and_1_run_only_against_a_scratch_schema": ("T107", "T109", "T121", "T304"),  # T273; tasks:2512
    "test_rollback_with_the_database_stopped_is_refused_and_changes_neither_switch_nor_marker": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_the_marker_removal_entry_is_written_with_the_switch_in_step_1": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_the_rollback_oracle_fails_on_a_last_fetched_tip_writer": ("T121", "T304", "T326"),  # T273; tasks:2512
    "test_the_rollback_oracle_fails_on_a_switch_reset_when_the_database_returns": ("T121", "T304", "T326"),  # T273; tasks:2512
}

#: The scratch schema the cases bootstrap: any `register_schema=` but the
#: default (Y:2323; lane 2's reading, NOTES question 6).
SCRATCH = "t273_scratch"
DEFAULT_SCHEMA = "lanes_register"
WRITER, READER = "lanes_register_writer", "lanes_register_reader"

#: The logins `lanes-index` connects as, made once per cluster (roles are
#: cluster-wide), members of the writer and the reader groups, with no
#: password: the cluster's socket trusts them.
LOGIN_WRITER, LOGIN_READER = "t273_register_writer", "t273_register_reader"

#: The bootstrap's admin service and the switch's label, which the
#: configuration's `register_label=` names too (the declaration's `database=`).
ADMIN_SERVICE = "t273_admin"
LABEL = "t273"

#: The operator lane (D24; F12), this workstation (Rule 10) and git's author
#: (D15), through git's own variables and no git configuration.
OPERATOR_LANE = "t273-operator"
WS = "ws-t273"
AUTHOR = "T273 operator <t273@example.invalid>"
OPERATOR_GIT = {"GIT_AUTHOR_NAME": "T273 operator", "GIT_AUTHOR_EMAIL": "t273@example.invalid",
                "GIT_COMMITTER_NAME": "T273 operator",
                "GIT_COMMITTER_EMAIL": "t273@example.invalid",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

#: What AT-LR006's entries carry.
COMMIT_C, TREE_C, MARKER_COMMIT = "c" * 40, "d" * 40, "e" * 40
ARGS_SHA256 = "a" * 64
NOT_AFTER = "2100-01-01T00:00:00Z"
LANES_MD = ["# Lanes"]
STORE_UTC = "2026-11-11T10:00:00Z"
STORE_LINES = ("store=primary", f"database={LABEL}", f"import={COMMIT_C}",
               f"lanes-tree={TREE_C}", f"utc={STORE_UTC}")

#: The divergences the cases record, and who records them.
SHA_DIVERGED, SHA_MEANWHILE = "1" * 40, "2" * 40
WS_MEANWHILE = "ws-t273-meanwhile"

#: The configuration's own values (`c`, `n_a`), so neither is the default.
CONNECT_TIMEOUT, ADDRESSES = 3, 2

#: The functions that write, which "one transaction" counts.
WRITE_CALLS = ("commit_write(", "record_marker(", "switch_to_files(", "record_mirror_state(")

#: The declaration's file, beside the configuration (D20; config.md section 6.1).
OUTAGE_FILE = "register-outage"

#: The second session's `application_name`, which the case waits on.
HOLDER = "t273-holder"


def _private(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    return path


def _said(proc) -> str:
    return (f"exit {proc.returncode}\n--- stdout ---\n{(proc.stdout or '')[-3000:]}"
            f"\n--- stderr ---\n{(proc.stderr or '')[-3000:]}")


def _render_git_half() -> list:
    """The shipped `lanes-index`'s `RENDER_GIT_HALF = ` values, each line's
    `True` or `False`; none where it cannot be read."""
    try:
        return RENDER_GIT_HALF_LINE.findall(LANES_INDEX.read_bytes())
    except OSError:
        return []


#: T328'S CONSTANT SET (tasks:2511; lane 2, #165 6859084292; lane 3's sweep,
#: #165 6851829112). T304's own test reads the shipped `lanes-index`'s
#: `RENDER_GIT_HALF = ` line at collection, before its setup. With one True
#: line, T328's, each of its six ids skips with this reason, which never holds
#: `tests/pgcluster.py`'s `SKIP_TAG`, so no run counts it as a real-engine
#: skip. With one False line they run. Anything else fails at
#: `_constant_unset()`.
CONSTANT_SET = (
    "RENDER_GIT_HALF = True in the shipped lanes-index (lane 3's T328): the scratch-schema "
    "rule this test checks ends with T328, and test 8's and AT-F1's cases carry steps 0 and 1 "
    "on lanes_register")


def _constant_unset() -> None:
    """The shipped `lanes-index` carries Q6(c)'s constant unset: the
    scratch-schema rule this test checks holds only while it does."""
    found = _render_git_half()
    assert found == [b"False"], (
        f"{LANES_INDEX} carries {found!r} for `RENDER_GIT_HALF = `, not one False line: T304's "
        f"own test runs the shipped lanes-index with the constant unset (B10 tasks:1015), and "
        f"lane 3's T328 sets it")


# ------------------------------------------------------------------ AT-LR006's entries
def _rendered(lines) -> str:
    """The sha256 of a file of `lines`, LF-joined with a final LF, as
    `render_file` renders it."""
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def _entry(kind: str, verb: str, **parts) -> dict:
    """One `commit_write` entry: the journal object, `not_after`, and `parts`."""
    journal = {"kind": kind, "verb": verb, "lane": OPERATOR_LANE, "workstation": WS,
               "author": AUTHOR, "message": f"t273: {kind}"}
    journal.update(parts.pop("journal", {}))
    return {"journal": journal, "not_after": NOT_AFTER, **parts}


def _import_entry() -> dict:
    edits = [{"ord": 1, "op": "create", "path": "lanes/LANES.md"}]
    edits += [{"ord": n, "op": "append", "path": "lanes/LANES.md", "new_text": text}
              for n, text in enumerate(LANES_MD, start=2)]
    return _entry("import", "import", journal={"git_commit": COMMIT_C, "git_tree": TREE_C},
                  edits=edits, files=[{"path": "lanes/LANES.md", "present": True,
                                       "sha256": _rendered(LANES_MD), "final_newline": True}])


def _cutover_entry() -> dict:
    edits = [{"ord": 1, "op": "create", "path": "lanes/STORE"}]
    edits += [{"ord": n, "op": "append", "path": "lanes/STORE", "new_text": line}
              for n, line in enumerate(STORE_LINES, start=2)]
    return _entry("cutover", "cutover", edits=edits,
                  files=[{"path": "lanes/STORE", "present": True,
                          "sha256": _rendered(STORE_LINES), "final_newline": True}])


def _write_entry(text: str) -> dict:
    """A write that appends `text` to `lanes/LANES.md`."""
    return _entry("write", "log", journal={"args_sha256": ARGS_SHA256},
                  edits=[{"ord": 1, "op": "append", "path": "lanes/LANES.md", "new_text": text}],
                  files=[{"path": "lanes/LANES.md", "present": True,
                          "sha256": _rendered([*LANES_MD, text]), "final_newline": True}])


def _open_when_held(fifo: Path, proc: subprocess.Popen, seconds: float = 120):
    """The FIFO's write end, opened once the shim holds a call on it; None
    where `proc` ends, or the time runs out, first. Closing it releases the
    call."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and proc.poll() is None:
        try:
            return os.open(str(fifo), os.O_WRONLY | os.O_NONBLOCK)
        except OSError:
            time.sleep(0.05)
    return None


# ------------------------------------------------------------------ the register
class RollbackRegister:
    """A database of the session cluster, from `template0`, bootstrapped by
    `lanes-index bootstrap` for `SCRATCH` (T109; DEC-23), brought to `primary`
    with the marker `present` by AT-LR006's route at head `k`, and section
    3.2's shim in front of the real `psql` for every `lanes-index` run here."""

    def __init__(self, cluster, root: Path):
        self.cluster, self.root = cluster, root
        root.mkdir(parents=True, exist_ok=True)
        name = f"t273_{uuid.uuid4().hex[:8]}"
        cluster.psql(f"CREATE DATABASE {name} TEMPLATE template0;")
        self.db = Database(cluster, name)
        try:
            self._bootstrap()
            for login, group in ((LOGIN_WRITER, WRITER), (LOGIN_READER, READER)):
                self.sql(f"DO $l$ BEGIN CREATE ROLE {login} LOGIN IN ROLE {group}; "
                         f"EXCEPTION WHEN duplicate_object THEN NULL; END $l$;")
            self.k = self._to_primary()
        except BaseException:
            cluster.drop_database(name)
            raise
        self.shim = root / "shim"
        self.shim.mkdir()
        (self.shim / "psql").write_text(PSQL_SHIM, encoding="utf-8")
        (self.shim / "psql").chmod(0o755)
        self.arm([])
        (root / "operator").mkdir()

    def drop(self) -> None:
        self.cluster.drop_database(self.db.name)

    # ---------------------------------------------------------------- the SQL side
    def psql(self, script: str, role: str = None, appname: str = "t273") -> subprocess.CompletedProcess:
        """One `psql` as the fixture's superuser, as `role` where one is named,
        with the commit call's settings, so a refusal's first stderr line is
        `ERROR:  <SQLSTATE>: <message>`."""
        head = "\\set VERBOSITY verbose\n\\set SHOW_CONTEXT never\nSET client_encoding = 'UTF8';\n"
        if role:
            head += f"SET ROLE {role};\n"
        return subprocess.run([self.db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                              input=head + script, capture_output=True, encoding="utf-8",
                              errors="replace", env=self.db.env(appname=appname), timeout=120,
                              check=False)

    def sql(self, script: str, role: str = None) -> str:
        proc = self.psql(script, role)
        assert proc.returncode == 0, (f"psql{' as ' + role if role else ''} exited "
                                      f"{proc.returncode}: {proc.stderr.strip()}\n{script}")
        return proc.stdout.strip()

    def _bootstrap(self) -> None:
        """`lanes-index bootstrap` through the admin service, with a
        configuration that holds `register_schema=` `SCRATCH` alone."""
        home = self.root / "admin"
        _private(home / ".pg_service.conf",
                 f"[{ADMIN_SERVICE}]\nhost={self.db.host}\nport={self.db.port}\n"
                 f"dbname={self.db.name}\nuser={SUPERUSER}\n")
        conf = _private(self.root / "boot" / "lanes-index.conf", f"register_schema={SCRATCH}\n")
        env = guard_strip_env(os.environ, strip=("XDG_",))
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                   XDG_STATE_HOME=str(self.root / "admin-state"), LANES_WORKSTATION=WS,
                   LANES_INDEX_CONFIG=str(conf))
        proc = subprocess.run([sys.executable, str(LANES_INDEX), "bootstrap", "--admin-service",
                               ADMIN_SERVICE, "--label", LABEL, "--repository", "opensoft/t273",
                               "--lane", OPERATOR_LANE, "--no-passwords"],
                              capture_output=True, encoding="utf-8", errors="replace", env=env,
                              timeout=300, stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0, (f"the scratch schema's bootstrap (T109's DEC-23 rendering) "
                                      f"failed:\n{_said(proc)}")
        schemas = self.sql(f"SELECT string_agg(nspname, ',' ORDER BY nspname) FROM pg_namespace "
                           f"WHERE nspname IN ('{SCRATCH}', '{DEFAULT_SCHEMA}');")
        assert schemas == SCRATCH, (f"the bootstrap for {SCRATCH} made the schemas {schemas!r}, "
                                    f"not {SCRATCH} alone")

    def window(self) -> dict:
        return json.loads(self.sql(f"SELECT to_jsonb(v) FROM {SCRATCH}.schema_version v;"))

    def commit(self, base: int, body: dict, what: str) -> int:
        """The commit call as a writer sends it (section 1.3's step 3; AT-LR006's
        fixture): one SERIALIZABLE transaction around `commit_write`, as
        REGISTER-WRITER. Returns the entry's seq."""
        literal = json.dumps(body, ensure_ascii=True).replace("'", "''")
        proc = self.psql(f"BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
                         f"SELECT {SCRATCH}.commit_write({base}, '{uuid.uuid4()}'::uuid, "
                         f"{self.window()['version']}, '{self.switch()['generation']}'::uuid, "
                         f"'{literal}'::jsonb);\nCOMMIT;\n", WRITER)
        assert proc.returncode == 0, f"{what}: commit_write refused it: {proc.stderr.strip()}"
        return int(proc.stdout.strip().splitlines()[-1])

    def _to_primary(self) -> int:
        """AT-LR006's route (TP:4610-4615): an import, a cutover and
        `record_marker`, then one write. Returns the head, `k`."""
        imported = self.commit(self.head(), _import_entry(), "the import")
        cut = self.commit(imported, _cutover_entry(), "the cutover")
        marker = self.sql(f"SELECT {SCRATCH}.record_marker({self.window()['version']}, {cut}, "
                          f"'{MARKER_COMMIT}', '{WS}');", WRITER)
        assert marker == "present", f"record_marker answered {marker!r}, not present"
        k = self.commit(cut, _write_entry("t273: a write after the cutover"), "the write")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"], k) == ("primary", "present", 2), (
            f"AT-LR006's route left the switch {switch} and the head {k}, not primary, present "
            f"and 2")
        return k

    def switch(self) -> dict:
        return json.loads(self.sql(f"SELECT to_jsonb(s) FROM {SCRATCH}.register_switch s;"))

    def head(self) -> int:
        return int(self.sql(f"SELECT seq FROM {SCRATCH}.register_head;"))

    def mirror(self) -> dict:
        return json.loads(self.sql(f"SELECT to_jsonb(m) FROM {SCRATCH}.mirror_state m;"))

    def journal(self) -> list:
        """Each entry's seq, kind and generated `operator` flag, by seq."""
        return json.loads(self.sql(
            f"SELECT coalesce(jsonb_agg(jsonb_build_array(j.seq, j.kind, j.operator) "
            f"ORDER BY j.seq), '[]') FROM {SCRATCH}.journal j;"))

    def state(self) -> dict:
        """The switch whole, the head and the journal: what "does not move" compares."""
        return {"switch": self.switch(), "head": self.head(), "journal": self.journal()}

    def wait_sql(self, count_query: str, what: str, ceiling: float = 10.0) -> None:
        """Poll `count_query` in 0.05 s steps under `ceiling` until it counts
        one row or more."""
        end = time.monotonic() + ceiling
        while time.monotonic() < end:
            if self.sql(count_query) != "0":
                return
            time.sleep(0.05)
        pytest.fail(f"{what}: not seen within {ceiling} s")

    # ---------------------------------------------------------------- lanes-index
    def config(self, name: str, *, schema: str | None = SCRATCH, port: int | None = None) -> Path:
        """A 0600 `lanes-index.conf` in a directory of its own: `mode=index`,
        the URLs of the cluster's socket (at `port` where it is given), the
        label, and `register_schema=` `schema` where it is not None."""
        where = (f"{quote(str(self.db.host), safe='')}:{self.db.port if port is None else port}"
                 f"/{self.db.name}?connect_timeout={CONNECT_TIMEOUT}")
        lines = ["mode=index", f"register_url=postgresql://{LOGIN_WRITER}@{where}",
                 f"reader_url=postgresql://{LOGIN_READER}@{where}",
                 f"register_addresses={ADDRESSES}", f"register_label={LABEL}"]
        if schema is not None:
            lines.append(f"register_schema={schema}")
        return _private(self.root / name / "lanes-index.conf", "\n".join(lines) + "\n")

    def env(self, conf: Path) -> dict:
        """The operator lane's environment (D24): no inherited `PG*`, lane,
        session, git or XDG variable; `LANES_LANE`, this workstation, git's
        author, the configuration, and the shim first on `PATH`."""
        env = guard_strip_env(os.environ, strip=("GIT_", "XDG_", "EMAIL"))
        env.update(HOME=str(self.root / "home"), XDG_STATE_HOME=str(self.root / "state"),
                   XDG_CONFIG_HOME=str(self.root / "config"), LANES_INDEX_CONFIG=str(conf),
                   LANES_LANE=OPERATOR_LANE, LANES_WORKSTATION=WS,
                   PATH=f"{self.shim}{os.pathsep}{os.environ.get('PATH', os.defpath)}",
                   **OPERATOR_GIT)
        return env

    def argv(self) -> list:
        return [sys.executable, str(LANES_INDEX), "rollback"]

    def rollback(self, conf: Path) -> subprocess.CompletedProcess:
        """`lanes-index rollback`, the shipped one, in the operator's directory."""
        return subprocess.run(self.argv(), capture_output=True, encoding="utf-8",
                              errors="replace", env=self.env(conf), cwd=str(self.root / "operator"),
                              timeout=180, stdin=subprocess.DEVNULL, check=False)

    def arm(self, arms: list) -> None:
        (self.shim / PSQL_SHIM_CONTROL).write_text(
            json.dumps({"psql": self.db.psql_bin, "arms": arms}), encoding="utf-8")

    def calls(self) -> list:
        """The shim's entries that carried a request, in call order."""
        log = self.shim / PSQL_SHIM_LOG
        if not log.exists():
            return []
        entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
                   if line]
        return [entry for entry in entries if entry.get("kind") != "version"]

    def writes(self) -> list:
        """The calls that carried a function that writes (`WRITE_CALLS`)."""
        return [c for c in self.calls() if any(w in c.get("sent", "") for w in WRITE_CALLS)]


@pytest.fixture
def rb_register(pg_cluster, tmp_path):
    reg = RollbackRegister(pg_cluster, tmp_path / "reg")
    try:
        yield reg
    finally:
        reg.drop()


# =================================================================== T304's own test
def _diverged_refuses_2(reg: RollbackRegister) -> None:
    proc = reg.psql(f"SELECT {SCRATCH}.record_mirror_state('{WS}', '{SHA_DIVERGED}', NULL);",
                    WRITER)
    assert proc.returncode == 0, f"record_mirror_state refused the divergence: {proc.stderr}"
    before = reg.state()
    conf = reg.config("conf")
    proc = reg.rollback(conf)
    assert proc.returncode == 2, f"a rollback with a divergence recorded is not refused 2:\n{_said(proc)}"
    assert f"diverged at {SHA_DIVERGED}" in proc.stderr, _said(proc)
    for way in ("import --single", "render --revert"):
        assert way in proc.stderr, f"the refusal does not name S2's way out {way!r}:\n{_said(proc)}"
    assert reg.writes() == [], (
        f"step 0's database half did not refuse before step 1: a call that writes was sent: "
        f"{[c.get('sent') for c in reg.writes()]}")
    assert reg.state() == before, "the refused rollback moved the switch, the marker or the head"
    assert not (conf.parent / OUTAGE_FILE).exists(), "the refused rollback declared the outage"


def _step_1_one_transaction(reg: RollbackRegister) -> None:
    k = reg.k
    proc = reg.rollback(reg.config("conf"))
    switch = reg.switch()
    assert (switch["mode"], switch["marker_state"]) == ("files", "removing"), (
        f"step 1 left the switch {switch}, not files with the marker removing:\n{_said(proc)}")
    assert (switch["set_seq"], switch["marker_seq"]) == (k + 1, k + 1), (
        f"set_seq and marker_seq are not the rollback's own seq {k + 1}: {switch}")
    assert reg.head() == k + 1, f"the head is {reg.head()}, not k+1 = {k + 1}:\n{_said(proc)}"
    journal = reg.journal()
    assert journal[-1] == [k + 1, "rollback", True], (
        f"the last entry is {journal[-1]}, not the operator's rollback entry at {k + 1}: {journal}")
    assert [seq for seq, _kind, _operator in journal] == list(range(k + 2)), journal
    edits = json.loads(reg.sql(
        f"SELECT coalesce(jsonb_agg(jsonb_build_array(e.ord, e.op, e.path) ORDER BY e.ord), '[]') "
        f"FROM {SCRATCH}.journal_edits e WHERE e.seq = {k + 1};"))
    assert edits == [[1, "remove", "lanes/STORE"]], f"the rollback's entry's edits are {edits}"
    files = json.loads(reg.sql(
        f"SELECT coalesce(jsonb_agg(jsonb_build_array(f.path, f.present) ORDER BY f.path), '[]') "
        f"FROM {SCRATCH}.journal_files f WHERE f.seq = {k + 1};"))
    assert files == [["lanes/STORE", False]], f"the rollback's entry's files rows are {files}"
    writes = reg.writes()
    assert len(writes) == 1 and "commit_write(" in writes[0]["sent"], (
        f"not one call that writes, step 1's commit call: "
        f"{[c.get('sent', '')[:300] for c in writes]}")
    sent = writes[0]["sent"]
    begin, call, end = (sent.find("BEGIN ISOLATION LEVEL SERIALIZABLE"),
                        sent.find("commit_write("), sent.rfind("COMMIT"))
    assert 0 <= begin < call < end, (
        f"step 1's call is not one SERIALIZABLE transaction around commit_write: {sent[:600]}")


def _outage_declared_with_mirror_seq(reg: RollbackRegister) -> None:
    k = reg.k
    conf = reg.config("conf")
    proc = reg.rollback(conf)
    path = conf.parent / OUTAGE_FILE
    assert path.exists(), (f"the rollback's start declared no outage beside its configuration "
                           f"({path}):\n{_said(proc)}")
    lines = path.read_text(encoding="utf-8").splitlines()
    fields = dict(line.split("=", 1) for line in lines)
    assert lines[0] == "format=1", lines
    assert (fields.get("kind"), fields.get("mirror-seq")) == ("rollback", str(k)), (
        f"the declaration is not marked as from a rollback with mirror-seq k = {k}: {lines}")
    assert (fields.get("database"), fields.get("host")) == (LABEL, WS), lines
    assert "until" not in fields, f"a rollback's declaration carries an expiry: {lines}"
    assert "outage declared:" in proc.stdout, _said(proc)


def _lost_turn_rechecks_step_0(reg: RollbackRegister) -> None:
    k = reg.k
    before = reg.state()
    fifo = reg.root / "hold.fifo"
    os.mkfifo(str(fifo), 0o600)
    # The rollback's second read, the second call carrying `diverged_sha`, is held.
    reg.arm([{"mode": "hold", "fifo": str(fifo), "match": "diverged_sha", "call": 2}])
    holder = reg.db.session(appname=HOLDER)
    proc, fd = None, None
    try:
        holder.stdin.write(f"BEGIN;\nSELECT seq FROM {SCRATCH}.register_head WHERE id = 1 "
                           f"FOR UPDATE;\n")
        holder.stdin.flush()
        reg.wait_sql(f"SELECT count(*) FROM pg_stat_activity WHERE application_name = '{HOLDER}' "
                     f"AND state = 'idle in transaction' AND backend_xid IS NOT NULL;",
                     "the second session's lock on the head row")
        proc = subprocess.Popen(reg.argv(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                env=reg.env(reg.config("conf")), cwd=str(reg.root / "operator"))
        fd = _open_when_held(fifo, proc)
        assert fd is not None, "the rollback never reached a second read: it did not lose its turn"
        # Step 1's call has ended; the divergence is recorded and the row released at once.
        out, err = holder.communicate(
            input=(f"SET ROLE {WRITER};\nSELECT {SCRATCH}.record_mirror_state('{WS_MEANWHILE}', "
                   f"'{SHA_MEANWHILE}', NULL);\nCOMMIT;\n"), timeout=60)
        assert holder.returncode == 0, f"the second session could not record the divergence: {err}"
        assert reg.mirror()["diverged_sha"] == SHA_MEANWHILE, reg.mirror()
        os.close(fd)
        fd = None
        out, err = proc.communicate(timeout=120)
    finally:
        if fd is not None:
            os.close(fd)
        for p in (proc, holder):
            if p is not None and p.poll() is None:
                p.kill()
                p.wait()
    ended = f"exit {proc.returncode}\n--- stdout ---\n{out[-3000:]}\n--- stderr ---\n{err[-3000:]}"
    assert proc.returncode == 2, f"the rollback did not end 2 after its lost turn:\n{ended}"
    assert "55P03" in err and "lost its turn" in err, (
        f"step 1 did not meet 55P03 at rollback's lock_timeout and go back:\n{ended}")
    assert f"diverged at {SHA_MEANWHILE}" in err, (
        f"step 0 did not refuse the divergence recorded meanwhile:\n{ended}")
    kinds = ["write" if any(w in c.get("sent", "") for w in WRITE_CALLS) else
             "read" if "diverged_sha" in c.get("sent", "") else "other" for c in reg.calls()]
    assert kinds == ["read", "write", "read"], (
        f"not step 0's read, step 1's one lost call, then step 0's read afresh: {kinds}")
    after = reg.state()
    assert after == before, f"the switch, the marker or the head moved: {before} -> {after}"
    assert after["head"] == k


def _database_unreachable_69(reg: RollbackRegister) -> None:
    port = reg.db.port + 1
    assert not (Path(reg.db.host) / f".s.PGSQL.{port}").exists()
    before = reg.state()
    conf = reg.config("unreachable", port=port)
    proc = reg.rollback(conf)
    assert proc.returncode == 69, f"a rollback that cannot reach the database is not 69:\n{_said(proc)}"
    assert "could not be read" in proc.stderr, _said(proc)
    assert reg.calls(), "the rollback sent no read, so it never met the database's silence"
    assert reg.writes() == [], "a call that writes was sent"
    assert reg.state() == before, "the switch, the marker or the head moved"
    assert not (conf.parent / OUTAGE_FILE).exists(), "the failed rollback declared the outage"


def _not_a_scratch_schema_2(reg: RollbackRegister) -> None:
    before = reg.state()
    conf = reg.config("default-schema", schema=None)
    proc = reg.rollback(conf)
    assert proc.returncode == 2, (f"a rollback with register_schema= unset is not refused 2 "
                                  f"while the constant is unset:\n{_said(proc)}")
    assert f"register_schema={DEFAULT_SCHEMA}" in proc.stderr and "scratch schema" in proc.stderr, (
        f"the refusal does not name the default schema and the scratch-schema rule:\n{_said(proc)}")
    assert reg.calls() == [], f"the refused rollback sent a request: {reg.calls()}"
    assert reg.state() == before, "the switch, the marker or the head moved"
    assert not (conf.parent / OUTAGE_FILE).exists(), "the refused rollback declared the outage"


T304_CASES = {
    "diverged-refuses-2": _diverged_refuses_2,
    "step-1-one-transaction": _step_1_one_transaction,
    "outage-declared-with-mirror-seq": _outage_declared_with_mirror_seq,
    "lost-turn-rechecks-step-0": _lost_turn_rechecks_step_0,
    "database-unreachable-69": _database_unreachable_69,
    "not-a-scratch-schema-2": _not_a_scratch_schema_2,
}


@pytest.mark.skipif(_render_git_half() == [b"True"], reason=CONSTANT_SET)
@pytest.mark.parametrize("case", list(T304_CASES))
def test_rollback_steps_0_and_1_run_only_against_a_scratch_schema(rb_register, case):
    """T304's own test (R-F10-34): steps 0 and 1 of the shipped `lanes-index
    rollback`, the constant unset, on `SCRATCH` at `primary` with the marker
    `present` and head `k`. Each id is in the module's docstring."""
    _constant_unset()
    T304_CASES[case](rb_register)


# =================================================================== T273b: test 8, 4.2, AT-F1
#: T273b: AT-8's test 8 (11), section 4.2 (2) and AT-F1 (7), as the test plan
#: (TP:1546-1734, TP:5447-5509, TP:7568-7609) and F13d's T273 bullet give them.
#:
#: THE ESTATE (TP:1592-1636). Test 7's cutover host, `CutoverRegister` in
#: `test_sql_register_import.py` (line W3a's T211j, merged into this line for
#: it, as AT-F2's cases build on it): the fixture register at C imported, ws1
#: the operator lane's checkout (`LANES_LANE=repoA-2`, F12) running T203's
#: flipped copy, so that `rollback` takes `lanes_register` with the renderer's
#: git half; then the cutover, and two writes on primary from ws1, each
#: rendered, so `k` is the head, 3. Test 5's `git` wrapper and section 3.2's
#: shim are first on ws1's `PATH`. ws2, the missed workstation, is a clone of
#: its own with its own `$HOME` and a `mode=primary` configuration, lane
#: `repoW-1`, and a shim of its own.
#:
#: WHAT EACH WAITS FOR. Every estate case fails until lane 3's T327 (the
#: cutover's push and read-back, so the marker reads `present`), lane 4's
#: T415 and T416 (a write on primary, and its render's fork), lane 3's T321 to
#: T323 (the render), and T326 (step 0's fetch and steps 2 to 4). Of the
#: missed writer's ids, the eight `commit-*` also wait for lane 4's T420
#: (D10's refusals on primary), and the other 40 for lane 1's T111 (AT-3's
#: line in check 4's 69); case (i) also waits for T417 (exit 3 and its
#: rerun). No id waits for lane 4's T421 or lane 5's T507: none runs the
#: guard, and with T421's merge reverted the `claim` ids fail as they do with
#: it (T273's Order, tasks:2512 at 204145ae; lane 2's RB15; lane 4, #165
#: 6826679959). `test_a_rollback_entry_over_a_recorded_divergence_is_lr012` (direct
#: calls, lane 1's T107) and `test_rollback_exits_2_on_lr012_naming_the_
#: divergence_and_both_ways_out` (a False copy on the scratch schema, T304)
#: need neither, and can pass on line R now. The four FP lost-turn ids need
#: no engine, and fail until T326, at their own assertion.
#:
#: READINGS, NOT FOUND IN A CONTRACT:
#: - "A fetch of `origin main`" is a `git fetch` whose arguments name
#:   `origin`, logged by the wrapper; "between" two `psql` calls is read from
#:   the wrapper's own count of the requests the shim or the fake had logged
#:   when the fetch started, so no clock is shared.
#: - The held session of (g) and of T304's lost turn is the fixture's
#:   superuser holding `register_head`'s row `FOR UPDATE`, not a writer
#:   replaying a commit call: the rollback's call meets the same lock, and a
#:   divergence recorded meanwhile then fails its `FOR SHARE` read of
#:   `mirror_state` with 40001 in the same way.
#: - (g)'s `[last-error-only]` and AT-F1's retries read "the marker
#:   `removing`" as step 1's state: where T326's steps 2 to 4 have run to
#:   their end, the marker reads `absent` and the rollback exits 0, which the
#:   case accepts too.
#: - (c)'s ids are `<verb>-<fetch>-<no_fetch>`, with `fetched` or
#:   `not-fetched`, and `unset` or `no-fetch` for `LANES_NO_FETCH`.
#: - AT-F1's removal entry and rerun cases run on the clean estate, not after
#:   a single-write import: what they check is step 1 and the rerun, which the
#:   import does not change.
#: - (h)'s FP register is a clean estate at `Register-Seq: 1`: the import at
#:   0, whose images are the workspace's render set, and the cutover at 1, the
#:   head, with no divergence. The fake answers from it every read a try makes
#:   before step 1, T326's git half's two included (`HEAD_READ_MARK` and
#:   `IMAGE_READ_MARK`), so each try's check passes and reaches step 1's lost
#:   turn (lane 3's #165 6813528630).

EM, DOT = chr(0x2014), chr(0xB7)
#: AT-3's line, which the missed writer's refusal carries (TP:1651-1652).
AT3_LINE = "this estate's register is SQL; configure `mode=primary`"
#: The missed workstation's lane: a LIVE row of test 7's fixture register.
MISSED_LANE = "repoW-1"
#: The object every `claim` case names, held by no lane at C.
CLAIMED = "opensoft/repoQ#8"
VERB_NAMES = ("set-row-state", "replace-in-row", "append-session-id", "append-line", "commit",
              "claim")
MISSED_CASES = [f"{verb}-{fetch}-{no_fetch}" for verb in VERB_NAMES
                for fetch in ("fetched", "not-fetched") for no_fetch in ("unset", "no-fetch")]
#: The text the `commit` case's hand edit changes in `MISSED_LANE`'s row.
ROW_TEXT = "its log has WORD lines"
#: A `Register-Seq` trailer.
REGISTER_SEQ = re.compile(r"^Register-Seq: ([0-9]+)$", re.M)
#: The rollback's read, and its step-1 call, as the shim and the fake see them.
READ_MARK, STEP_1_MARK = "diverged_sha", "commit_write("
EXIT_BUSY = 75
#: A push it cannot confirm (exit-codes.md's 3; ops:340).
EXIT_IN_DOUBT = 3


def _imp():
    """`test_sql_register_import`: test 7's fixture register and cutover host."""
    import test_sql_register_import as module
    return module


def _cut():
    """`test_sql_register_cutover`: AT-F2's fixture, `F2Register`, test 7's
    cutover host with test 5's `git` wrapper, whose arms leave a push
    unconfirmed, and `_first_reach`."""
    import test_sql_register_cutover as module
    return module


def _script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _requests(log: Path) -> list:
    """A `psql` log's entries that carried a request: never a `--version`."""
    return [entry for entry in _jsonl(log) if entry.get("kind") != "version"]


#: TEST 5'S `git` WRAPPER (TP:1060-1080), with what AT-8 needs: each call is
#: one JSON line of `git-wrapper.log`, its subcommand, its argv, its pid, and
#: `psql_before`, the number of requests the `psql` log named in the control
#: file held when it started. `hold`, `{"call": <subcommand>, "fifo": path}`,
#: blocks that call on the FIFO until the test closes its end.
GIT_WRAPPER = r'''#!/usr/bin/env -S python3 -I
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL = os.path.join(HERE, "git-wrapper.json")
LOG = os.path.join(HERE, "git-wrapper.log")
WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
              "--config-env"}


def subcommand(args):
    i = 0
    while i < len(args):
        if args[i] in WITH_VALUE:
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            return args[i]
    return ""


def requests(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return sum(1 for line in handle
                       if line.strip() and json.loads(line).get("kind") != "version")
    except (OSError, ValueError):
        return 0


def log(record):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def main():
    args = sys.argv[1:]
    with open(CONTROL, encoding="utf-8") as handle:
        control = json.load(handle)
    sub = subcommand(args)
    record = {"sub": sub, "argv": args, "pid": os.getpid(),
              "psql_before": requests(control.get("psql_log") or "")}
    hold = control.get("hold")
    if hold and hold.get("call") == sub:
        log(dict(record, outcome="held"))
        with open(hold["fifo"], "rb") as fifo:
            fifo.read()
    rc = subprocess.run([control["git"]] + args).returncode
    log(dict(record, outcome="ran", rc=rc))
    return rc


sys.exit(main())
'''


def _real_git() -> str:
    found = shutil.which("git")
    assert found, "no git on PATH"
    return found


def _lane_checkout(origin: Path, checkout: Path, lane: str, env: dict) -> Path:
    """`<c>`, THE WRITE LANE'S OWN CHECKOUT (lane 3's batch g Q119, #165
    6813027223): beside the checkout `workspace.yaml` names as W, at
    `<W>-lanes/<lane>`, W being its real path, as `lane_checkout_path` puts
    it (Amendment 23 S1). On primary a write reads its author, its pending
    hand edits and its `repos.tsv` from there, and refuses 2 where it is not
    there, "Nothing was sent" (B15 tasks:1154). A clone of W's own origin, as
    `lane-checkout <lane> --create` makes one, made after the case's last
    push from W, as LX's T253f and N2's T243f make theirs. One that is
    already there is kept, so a register that makes its own keeps it."""
    real = Path(os.path.realpath(checkout))
    target = real.parent / f"{real.name}-lanes" / lane
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", str(origin), str(target)], check=True, env=env,
                       capture_output=True, stdin=subprocess.DEVNULL)
    return target


class MissedWorkstation:
    """ws2, THE MISSED WORKSTATION (TP:1600-1604): a clone of origin of its
    own, its own `$HOME` and `workspace.yaml`, a `mode=primary`
    configuration naming the same database, lane `MISSED_LANE`, the flipped
    copy's `lanes-edit.sh`, and a shim of its own first on `PATH`."""

    def __init__(self, estate: "RollbackEstate", name: str):
        reg = estate.reg
        self.estate, self.root = estate, estate.root / name
        self.home = self.root / "home"
        agents = self.home / ".agents"
        agents.mkdir(parents=True)
        self.clone = self.home / "projects" / "wip"
        subprocess.run(["git", "clone", "-q", str(reg.origin), str(self.clone)], check=True,
                       env=reg.env, capture_output=True, stdin=subprocess.DEVNULL)
        # `MISSED_LANE`'s `<c>`, cloned with W: a ws2 kept behind the
        # rollback's push keeps it behind too (Q119), and `fetch` moves both.
        self.c = _lane_checkout(reg.origin, self.clone, MISSED_LANE, reg.env)
        (agents / "workspace.yaml").write_text(f"repository: {reg.origin}\npath: {self.clone}\n",
                                               encoding="utf-8")
        self.conf = _private(self.root / "conf" / "lanes-index.conf",
                             reg.primary_conf.read_text(encoding="utf-8"))
        self.shim = self.root / "shim"
        _script(self.shim / "psql", PSQL_SHIM)
        self.arm([])
        for d in ("state", "config", "tmp"):
            (self.root / d).mkdir()
        env = dict(reg.env)
        env.pop("LANES_INDEX", None)
        env.update(HOME=str(self.home), AGENT_PROTOCOL_ROOT=str(agents),
                   XDG_STATE_HOME=str(self.root / "state"),
                   XDG_CONFIG_HOME=str(self.root / "config"), TMPDIR=str(self.root / "tmp"),
                   CLAUDE_CONFIG_DIR=str(self.home / ".claude"), LANES_REPO=str(self.clone),
                   LANES_INDEX_CONFIG=str(self.conf), LANES_LANE=MISSED_LANE,
                   LANES_EDIT=str(reg.copy.parent / "lanes-edit.sh"),
                   PATH=f"{self.shim}{os.pathsep}{reg.env['PATH']}")
        self.env = env

    def arm(self, arms: list) -> None:
        """The shim's arms, with its log, ends and counters started afresh."""
        (self.shim / PSQL_SHIM_CONTROL).write_text(
            json.dumps({"psql": self.estate.db.psql_bin, "arms": arms}), encoding="utf-8")
        for name in (PSQL_SHIM_LOG, "psql-shim.ends"):
            (self.shim / name).write_text("", encoding="utf-8")
        (self.shim / "psql-shim.state").write_text("{}", encoding="utf-8")

    def git(self, *args: str) -> str:
        proc = subprocess.run(["git", "-C", str(self.clone), *args], capture_output=True,
                              text=True, env=self.env, stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0, f"git {' '.join(args)} in ws2: {proc.stderr}"
        return proc.stdout

    def fetch(self) -> None:
        self.git("fetch", "-q", "origin")
        subprocess.run(["git", "-C", str(self.c), "fetch", "-q", "origin"], check=True,
                       env=self.env, capture_output=True, stdin=subprocess.DEVNULL)

    def edit(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        child = dict(self.env)
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return subprocess.run(["bash", str(self.estate.reg.copy.parent / "lanes-edit.sh"),
                               *args], capture_output=True, text=True, env=child,
                              cwd=str(self.clone), timeout=300, stdin=subprocess.DEVNULL)

    def snapshot(self) -> dict:
        """ws2's HEAD, its index, its last-fetched tip, and the bytes of every
        file under `lanes/` in its work tree."""
        lanes = {str(p.relative_to(self.clone)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted((self.clone / "lanes").rglob("*")) if p.is_file()}
        return {"head": self.git("rev-parse", "HEAD").strip(),
                "fetched": self.git("rev-parse", "refs/remotes/origin/main").strip(),
                "index": hashlib.sha256(self.git("ls-files", "-s").encode()).hexdigest(),
                "lanes": lanes}

    def hand_edit(self) -> bool:
        """`commit`'s hand edit of `MISSED_LANE`'s row, left uncommitted."""
        path = self.clone / "lanes" / "LANES.md"
        text = path.read_text(encoding="utf-8")
        if ROW_TEXT not in text:
            return False
        path.write_text(text.replace(ROW_TEXT, ROW_TEXT + " by hand", 1), encoding="utf-8")
        return True

    def undo_hand_edit(self) -> None:
        self.git("checkout", "-q", "--", "lanes/LANES.md")


def _verb_args(verb: str) -> list:
    """The verb's arguments, as lane `MISSED_LANE` writes them (each checked
    in files mode on test 7's fixture register)."""
    imp = _imp()
    return {
        "set-row-state": ["set-row-state", MISSED_LANE, f"PAUSED {DOT} test 8"],
        "replace-in-row": ["replace-in-row", MISSED_LANE, ROW_TEXT, f"{ROW_TEXT}, test 8"],
        "append-session-id": ["append-session-id", MISSED_LANE, f"harness `{imp.UUID_W1}`",
                              " (test 8)"],
        "append-line": ["append-line", f"HOLD {EM} lane {MISSED_LANE} (Eagle), window w, "
                        f"2026-11-11T00:00:00Z: opensoft/repoQ main {imp.TIP_A} for test 8"],
        "commit": ["commit", "test 8's hand edit"],
        "claim": ["claim", CLAIMED, "--no-github"],
    }[verb]


class RollbackEstate:
    """TEST 8'S ESTATE (TP:1592-1636), on test 7's cutover host: see the
    notes above T273b. `prepare()` makes the cutover and the writes; until
    their tasks land it fails at its own assertion, naming them."""

    def __init__(self, root: Path, db, *, writes: int = 2):
        imp = _imp()
        self.imp, self.db, self.root, self.writes = imp, db, root, writes
        self.bin = root / "bin"
        _script(self.bin / "git", GIT_WRAPPER)
        _script(self.bin / "psql", PSQL_SHIM)
        self.real_git = _real_git()
        self.arm()
        self.reg = imp.CutoverRegister(root / "ws1", db, extra_path=self.bin)
        self.k = None

    # ------------------------------------------------------------ the wrapper and the shim
    def arm(self, arms=(), hold: dict | None = None) -> None:
        """The shim's arms and the wrapper's hold, each log started afresh."""
        (self.bin / PSQL_SHIM_CONTROL).write_text(
            json.dumps({"psql": self.db.psql_bin, "arms": list(arms)}), encoding="utf-8")
        for name in (PSQL_SHIM_LOG, "psql-shim.ends", "git-wrapper.log"):
            (self.bin / name).write_text("", encoding="utf-8")
        (self.bin / "psql-shim.state").write_text("{}", encoding="utf-8")
        control = {"git": self.real_git, "psql_log": str(self.bin / PSQL_SHIM_LOG)}
        if hold:
            control["hold"] = hold
        (self.bin / "git-wrapper.json").write_text(json.dumps(control), encoding="utf-8")

    def calls(self) -> list:
        return _requests(self.bin / PSQL_SHIM_LOG)

    def git_calls(self) -> list:
        return [c for c in _jsonl(self.bin / "git-wrapper.log") if c.get("outcome") == "ran"
                or c.get("outcome") == "held"]

    # ------------------------------------------------------------ the database
    def rows(self, sql: str) -> list:
        return self.imp._rows(self.db, sql)

    def switch(self) -> dict:
        return self.rows("SELECT * FROM register_switch")[0]

    def head(self) -> int:
        return self.rows("SELECT seq FROM register_head")[0]["seq"]

    def journal(self) -> list:
        return [[r["seq"], r["kind"], r["operator"]]
                for r in self.rows("SELECT seq, kind, operator FROM journal ORDER BY seq")]

    def count(self) -> int:
        return self.rows("SELECT count(*) AS n FROM journal")[0]["n"]

    def mirror(self) -> dict:
        return self.rows("SELECT * FROM mirror_state")[0]

    def state(self) -> dict:
        return {"switch": self.switch(), "head": self.head(), "journal": self.journal()}

    # ------------------------------------------------------------ origin
    def store_on_origin(self) -> bool:
        return "lanes/STORE" in self.reg.origin_git("ls-tree", "-r", "--name-only",
                                                    "refs/heads/main", "lanes/").split()

    def origin_seqs(self) -> list:
        """Every `Register-Seq` on origin's `main`, oldest first."""
        out = self.reg.origin_git("log", "--reverse", "--format=%B%x00", "refs/heads/main")
        return [int(s) for body in out.split("\0") for s in REGISTER_SEQ.findall(body)]

    # ------------------------------------------------------------ the commands
    def prepare(self) -> None:
        """The cutover, then `writes` writes on primary from ws1, each
        rendered: `k` is the head. The operator lane's `<c>` is made after
        the cutover's push from W, before the first write."""
        proc = self.reg.cutover()
        assert proc.returncode == 0, f"the cutover (T116) failed:\n{_said(proc)}"
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), (
            f"after the cutover the switch reads {switch['mode']} with the marker "
            f"{switch['marker_state']}: the marker's push, read-back and record_marker are lane "
            f"3's T327, so test 8's estate fails until it lands")
        self.c = _lane_checkout(self.reg.origin, self.reg.ws, self.imp.OPERATOR, self.reg.env)
        for n in range(1, self.writes + 1):
            proc = self.reg.write(f"test 8: write {n}")
            assert proc.returncode == 0, (
                f"write {n} on primary from ws1 failed (lane 4's T415 and T416):\n{_said(proc)}")
        self.k = self.head()
        assert self.reg.wait_for_seq(self.k), (
            f"no mirror commit carries Register-Seq: {self.k} (lane 3's T321 to T323): "
            f"{self.reg.seqs_on_origin()}")
        self.arm()

    def rollback(self, conf: Path | None = None, env: dict | None = None,
                 timeout: float = 300) -> subprocess.CompletedProcess:
        """`lanes-index rollback` from ws1, as the operator lane, with ws1's
        `mode=primary` configuration."""
        return self.reg.index("rollback", conf=conf or self.reg.primary_conf, env=env,
                              timeout=timeout)

    def popen_rollback(self) -> subprocess.Popen:
        return self.reg.popen("rollback", conf=self.reg.primary_conf)

    def outage_file(self) -> Path:
        return self.reg.primary_conf.parent / OUTAGE_FILE


def _estate(request, tmp_path: Path, *, stoppable: bool = False, prepare: bool = True):
    """A `RollbackEstate` on a database of its own: the session cluster's,
    or a `stoppable_cluster`'s where the case stops the database. The
    database is dropped at the case's end."""
    cluster = request.getfixturevalue("stoppable_cluster" if stoppable else "pg_cluster")
    name = cluster.new_database()
    request.addfinalizer(lambda: cluster.drop_database(name) if cluster.ready() else None)
    estate = RollbackEstate(tmp_path / "estate", Database(cluster, name))
    estate.cluster = cluster
    if prepare:
        estate.prepare()
    return estate


def _origin_blob(reg, rev: str, path: str) -> bytes:
    """`path` at `rev` in the bare origin, as bytes."""
    proc = subprocess.run(["git", f"--git-dir={reg.origin}", "show", f"{rev}:{path}"],
                          capture_output=True, env=reg.env, check=True, stdin=subprocess.DEVNULL)
    return proc.stdout


def _assert_rolled_back(estate: RollbackEstate, proc) -> None:
    """TEST 8 (a)'S ORACLE (TP:1638-1647): exit 0; the switch at `files` with
    the marker `absent`; origin's last commit removes `lanes/STORE` and
    carries the rollback entry's seq, `k+1`, the journal's last; and origin's
    rendered paths equal a full render from SQL, byte for byte."""
    imp, reg = estate.imp, estate.reg
    assert proc.returncode == 0, f"the rollback did not end 0:\n{_said(proc)}"
    switch = estate.switch()
    assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), (
        f"the switch is {switch['mode']}/{switch['marker_state']}, not files/absent after "
        f"record_marker confirmed the removal")
    journal = estate.journal()
    last = journal[-1]
    assert last[1:] == ["rollback", True], f"the journal's last entry is {last}: {journal}"
    tip = reg.origin_tip()
    assert REGISTER_SEQ.findall(reg.origin_git("log", "-1", "--format=%B", tip)) == [str(last[0])], (
        f"origin's last commit does not carry Register-Seq: {last[0]}")
    changed = reg.origin_git("diff-tree", "--no-commit-id", "--name-status", "-r", f"{tip}^", tip)
    assert changed.split("\n") == ["D\tlanes/STORE", ""], (
        f"origin's last commit does not remove lanes/STORE alone: {changed!r}")
    on_origin = {p: _origin_blob(reg, tip, p)
                 for p in reg.origin_git("ls-tree", "-r", "--name-only", tip, "lanes/").split()
                 if imp.RENDER_SET.match(p)}
    from_sql = {p: b for p, b in imp._renders(estate.db).items() if imp.RENDER_SET.match(p)}
    assert on_origin == from_sql, (
        f"origin's rendered paths differ from a full render from SQL: "
        f"{sorted(set(on_origin) ^ set(from_sql))} or "
        f"{sorted(p for p in on_origin if p in from_sql and on_origin[p] != from_sql[p])}")


# ------------------------------------------------------------------ (a), (b)
def test_rollback_leaves_files_byte_identical_marker_gone_and_sql_writes_refused(request,
                                                                                  tmp_path):
    """Test 8 (a) (TP:1549-1550, :1638-1647): the rollback with the database
    up, then a `mode=primary` write from ws1 exits 69, and `set-mode index`
    on ws1, as Brett runs it at the rollback's step 5 (operations.md 2.3),
    leaves ws1's configuration without `mode=primary`. Fails until T326,
    T327, T321 to T323, T415 and T416."""
    estate = _estate(request, tmp_path)
    proc = estate.rollback()
    _assert_rolled_back(estate, proc)
    count = estate.count()
    wrote = estate.reg.write("test 8 (a): a write after the rollback")
    assert wrote.returncode == 69, f"a mode=primary write after the rollback is not 69:\n{_said(wrote)}"
    assert estate.count() == count, "the refused write journaled"
    mode = estate.reg.index("set-mode", "index", conf=estate.reg.primary_conf)
    assert mode.returncode == 0, f"set-mode index on ws1:\n{_said(mode)}"
    lines = estate.reg.primary_conf.read_text(encoding="utf-8").splitlines()
    assert "mode=primary" not in lines, f"ws1's configuration still says mode=primary: {lines}"


def test_rollback_with_the_database_stopped_is_refused_and_changes_neither_switch_nor_marker(
        request, tmp_path):
    """Test 8 (b) (TP:1551-1552, :1648-1655): with the database stopped
    (`stoppable_cluster`), the rollback exits 69 and stops at its step 1;
    after the restart the switch still reads `primary` with the marker
    `present`, `lanes/STORE` is still on origin, ws1 is still
    `mode=primary`, and no `register-outage` is beside ws1's configuration.
    Fails until T327, T321 to T323, T415 and T416 (its estate)."""
    estate = _estate(request, tmp_path, stoppable=True)
    before = estate.switch()
    estate.cluster.stop()
    try:
        proc = estate.rollback()
    finally:
        estate.cluster.start_again()
    assert proc.returncode == 69, f"a rollback with the database stopped is not 69:\n{_said(proc)}"
    assert not any(STEP_1_MARK in c.get("sent", "") for c in estate.calls()), (
        "a step-1 call was sent with the database stopped")
    after = estate.switch()
    assert (after["mode"], after["marker_state"]) == ("primary", "present"), after
    assert after == before, f"the switch moved: {before} -> {after}"
    assert estate.store_on_origin(), "lanes/STORE is no longer on origin"
    assert "mode=primary" in estate.reg.primary_conf.read_text(encoding="utf-8").splitlines()
    assert not estate.outage_file().exists(), "a rollback refused at its step 1 declared"


# ------------------------------------------------------------------ (c), (e) and the claim
def _missed_failures(estate: RollbackEstate, ws2: MissedWorkstation, verb: str, *,
                     no_fetch: bool, writer=None) -> list:
    """TEST 8 (c)'S ORACLE (TP:1648-1667), as a list of what fails, empty
    where it holds: the writer exits 69 with AT-3's line (`commit`: 2, with
    nothing reaching SQL or `lanes/`); the journal's count is unchanged; and
    ws2's HEAD, index, last-fetched tip and files under `lanes/` are
    unchanged. `writer` stands in for ws2's `lanes-edit.sh` (case (e))."""
    edited = verb == "commit" and ws2.hand_edit()
    try:
        before, count = ws2.snapshot(), estate.count()
        env = {"LANES_NO_FETCH": "1" if no_fetch else None}
        proc = (writer or ws2.edit)(*_verb_args(verb), env=env)
        failures = []
        want = 2 if verb == "commit" else 69
        if proc.returncode != want:
            failures.append(f"{verb} exited {proc.returncode}, not {want}: {proc.stderr[-800:]}")
        if verb != "commit" and AT3_LINE not in proc.stderr:
            failures.append(f"{verb}'s stderr does not carry AT-3's line: {proc.stderr[-800:]}")
        if estate.count() != count:
            failures.append(f"{verb}: the journal's count moved from {count} to {estate.count()}")
        if ws2.snapshot() != before:
            failures.append(f"{verb}: ws2's HEAD, index, last-fetched tip or lanes/ files changed")
        return failures
    finally:
        if edited:
            ws2.undo_hand_edit()


@pytest.fixture(scope="module")
def missed_estate(pg_cluster, tmp_path_factory):
    """Test 8's estate after a whole rollback, shared by (c)'s 24 ids, (e)'s
    two stubs and the files-mode claim: ws2 cloned at the cutover's estate,
    twice, one fetched after the rollback's push and one not. Where the
    estate cannot be built or the rollback does not end 0, each case fails
    with why."""
    name = pg_cluster.new_database()
    shared = SimpleNamespace(problem=None)
    try:
        estate = RollbackEstate(tmp_path_factory.mktemp("missed"), Database(pg_cluster, name))
        estate.prepare()
        ws2 = {fetch: MissedWorkstation(estate, f"ws2-{fetch}")
               for fetch in ("fetched", "not-fetched")}
        cached = estate.switch()["mode"]
        proc = estate.rollback()
        _assert_rolled_back(estate, proc)
        ws2["fetched"].fetch()
        shared = SimpleNamespace(problem=None, estate=estate, ws2=ws2, cached_mode=cached)
    except AssertionError as exc:
        shared = SimpleNamespace(problem=f"test 8's estate after a whole rollback: {exc}")
    try:
        yield shared
    finally:
        pg_cluster.drop_database(name)


def _ready(shared):
    if shared.problem:
        pytest.fail(shared.problem[:4000], pytrace=False)
    return shared


@pytest.mark.parametrize("case", MISSED_CASES)
def test_a_missed_primary_writer_is_refused_after_rollback(missed_estate, case):
    """Test 8 (c) (TP:1553-1561, :1656-1667): once the rollback has run to
    its end, ws2, whose `mode=primary` was not cleared, exits 69 for each
    verb (`commit`: 2), fetched or not, with `LANES_NO_FETCH=1` or without,
    and changes nothing. Fails until T326, T327, T415, T420 and T421."""
    shared = _ready(missed_estate)
    fetch = "not-fetched" if "-not-fetched-" in case else "fetched"
    verb = case[:case.index(f"-{fetch}-")]
    failures = _missed_failures(shared.estate, shared.ws2[fetch], verb,
                                no_fetch=case.endswith("-no-fetch"))
    assert not failures, "\n".join(failures)


def _leak(estate: RollbackEstate, lane: str) -> subprocess.CompletedProcess:
    """A stub's write: one journal row through the real `psql`, as the admin
    under `SET ROLE lanes_register_owner`, since REGISTER-WRITER has no INSERT
    and `commit_write` would refuse it LR002 (TP:1609-1616)."""
    return estate.db.psql(
        f"SET search_path TO {estate.imp.SCHEMA};\nSET ROLE lanes_register_owner;\n"
        f"INSERT INTO journal (seq, base_seq, write_id, kind, verb, lane, workstation, author, "
        f"message, args_sha256) SELECT max(seq) + 1, max(seq), '{uuid.uuid4()}'::uuid, 'write', "
        f"'log', '{lane}', 'Eagle', 'stub <stub@example.invalid>', 'a stub writer''s leak', "
        f"'{'b' * 64}' FROM journal;\n", check=False)


def _stub(estate: RollbackEstate, leaks) -> callable:
    """A stub writer for (e): it writes `_leak`'s row and exits 0 where
    `leaks()` says so, and otherwise refuses as the product does."""
    def writer(*args, env=None):
        if leaks():
            written = _leak(estate, MISSED_LANE)
            assert written.returncode == 0, (
                f"the stub could not write its row, so it models no leak: {written.stderr}")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=69, stdout="", stderr=AT3_LINE + "\n")
    return writer


def test_the_rollback_oracle_fails_on_a_last_fetched_tip_writer(missed_estate):
    """Test 8 (e), the first stub (TP:1562-1564, :1668-1670, Q4(b)(i)): a
    writer that refuses only when its last-fetched tip lacks `lanes/STORE`
    leaks on ws2's clone that has not fetched since the rollback's push, and
    (c)'s oracle reports it. Fails until (c)'s estate can be built."""
    shared = _ready(missed_estate)
    ws2 = shared.ws2["not-fetched"]
    stub = _stub(shared.estate, lambda: subprocess.run(
        ["git", "-C", str(ws2.clone), "cat-file", "-e", "refs/remotes/origin/main:lanes/STORE"],
        env=ws2.env, capture_output=True).returncode == 0)
    failures = _missed_failures(shared.estate, ws2, "append-line", no_fetch=False, writer=stub)
    assert failures, "test 8's oracle passed a writer that leaks on its last-fetched tip"


def test_the_rollback_oracle_fails_on_a_switch_reset_when_the_database_returns(missed_estate):
    """Test 8 (e), the second stub (TP:1562-1564, :1668-1670, Q4(b)(ii)): a
    writer that checks the switch only when it first reconnects, and so
    keeps the `primary` it read before the rollback, leaks, and (c)'s oracle
    reports it. Fails until (c)'s estate can be built."""
    shared = _ready(missed_estate)
    stub = _stub(shared.estate, lambda: shared.cached_mode == "primary")
    failures = _missed_failures(shared.estate, shared.ws2["fetched"], "claim", no_fetch=True,
                                writer=stub)
    assert failures, "test 8's oracle passed a writer that keeps the switch it first read"


def _claim_holders(estate: RollbackEstate) -> set:
    """The lanes holding `CLAIMED`, across SQL's live claims and the files on
    origin's `main` (a lane whose log's last line on it is `CLAIMED`)."""
    rows = estate.rows(f"SELECT lane FROM object_holds WHERE lower(object) = lower('{CLAIMED}') "
                       f"AND verb IN ('CLAIMED', 'TAKEOVER') AND superseded_by IS NULL")
    held = {r["lane"] for r in rows}
    reg = estate.reg
    for path in reg.origin_git("ls-tree", "-r", "--name-only", "refs/heads/main",
                               "lanes/log/").split():
        last = None
        for line in reg.origin_git("show", f"refs/heads/main:{path}").splitlines():
            if CLAIMED.lower() in line.lower():
                last = line
        if last and last.startswith("CLAIMED"):
            match = re.match(r"CLAIMED \S+ lane ([^,\s]+),", last)
            held.add(match.group(1) if match else path)
    return held


def test_a_files_mode_claim_after_rollback_leaves_one_holder(missed_estate):
    """Test 8 (c)'s last step (TP:1666-1667): after the missed writer's
    cases, a files-mode `claim` of the same object on ws1 exits 0, and the
    object has exactly one holder across SQL and the files. Fails until
    (c)'s estate can be built."""
    shared = _ready(missed_estate)
    operator = _imp().OPERATOR
    proc = shared.estate.reg.edit("claim", CLAIMED, "--no-github", env={"LANES_LANE": operator})
    assert proc.returncode == 0, f"a files-mode claim on ws1 after the rollback:\n{_said(proc)}"
    assert _claim_holders(shared.estate) == {operator}, _claim_holders(shared.estate)


# ------------------------------------------------------------------ section 4.2: the partition
def _partitioned_conf(estate: RollbackEstate) -> Path:
    """ws1's configuration naming a fresh, empty socket directory (TP:1605)."""
    empty = estate.root / "empty-socket"
    empty.mkdir(exist_ok=True)
    live = quote(str(estate.db.host), safe="")
    text = estate.reg.primary_conf.read_text(encoding="utf-8").replace(
        live, quote(str(empty), safe=""))
    assert text != estate.reg.primary_conf.read_text(encoding="utf-8"), (
        "ws1's configuration does not name the cluster's socket directory")
    return _private(estate.root / "partitioned" / "lanes-index.conf", text)


def test_rollback_from_a_partitioned_clone_is_refused_and_removes_no_marker(request, tmp_path):
    """Section 4.2, while partitioned (TP:7579-7584): ws1's rollback, from a
    configuration naming an empty socket directory, exits 69; the switch
    reads `primary`; `lanes/STORE` is still on origin's `main`; and ws2's
    writes exit 0, since the estate is still primary. Fails until T327, T415,
    T416 and T421."""
    estate = _estate(request, tmp_path)
    ws2 = MissedWorkstation(estate, "ws2")
    proc = estate.rollback(conf=_partitioned_conf(estate))
    assert proc.returncode == 69, f"the partitioned rollback is not 69:\n{_said(proc)}"
    switch = estate.switch()
    assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
    assert estate.store_on_origin(), "lanes/STORE left origin's main"
    for verb in ("append-line", "claim"):
        wrote = ws2.edit(*_verb_args(verb))
        assert wrote.returncode == 0, f"ws2's {verb} on the still-primary estate:\n{_said(wrote)}"


@pytest.fixture(scope="module")
def partitioned_estate(pg_cluster, tmp_path_factory):
    """Section 4.2's estate after the partitioned rollback and the whole one:
    ws1's rollback from the empty socket directory (69), then from its own
    configuration to its end. ws2 cloned before, twice; one fetched after."""
    name = pg_cluster.new_database()
    try:
        estate = RollbackEstate(tmp_path_factory.mktemp("partition"),
                                Database(pg_cluster, name))
        estate.prepare()
        ws2 = {fetch: MissedWorkstation(estate, f"ws2-{fetch}")
               for fetch in ("fetched", "not-fetched")}
        refused = estate.rollback(conf=_partitioned_conf(estate))
        assert refused.returncode == 69, f"the partitioned rollback:\n{_said(refused)}"
        proc = estate.rollback()
        _assert_rolled_back(estate, proc)
        ws2["fetched"].fetch()
        shared = SimpleNamespace(problem=None, estate=estate, ws2=ws2,
                                 last=estate.journal()[-1][0])
    except AssertionError as exc:
        shared = SimpleNamespace(problem=f"section 4.2's estate: {exc}")
    try:
        yield shared
    finally:
        pg_cluster.drop_database(name)


@pytest.mark.parametrize("case", MISSED_CASES)
def test_a_missed_writer_is_refused_once_the_partitioned_rollback_completes(partitioned_estate,
                                                                            case):
    """Section 4.2, after the rollback completes (TP:7585-7590): every ws2
    case exits 69 (`commit`: 2); the journal's count no longer changes; the
    files equal a full render at the rollback's last seq; and every object
    has one holder. Fails until T326, T327, T415, T420 and T421."""
    shared = _ready(partitioned_estate)
    fetch = "not-fetched" if "-not-fetched-" in case else "fetched"
    verb = case[:case.index(f"-{fetch}-")]
    failures = _missed_failures(shared.estate, shared.ws2[fetch], verb,
                                no_fetch=case.endswith("-no-fetch"))
    assert not failures, "\n".join(failures)
    assert shared.estate.journal()[-1][0] == shared.last, "the journal moved past the rollback"
    live = shared.estate.rows("SELECT object, count(*) AS n FROM object_holds WHERE verb IN "
                              "('CLAIMED', 'TAKEOVER') AND superseded_by IS NULL AND NOT exempt "
                              "GROUP BY object HAVING count(*) > 1")
    assert live == [], f"an object has more than one holder: {live}"


# ------------------------------------------------------------------ (f), (g), (h), (i)
@pytest.mark.parametrize("stray", ["rendered-path", "register-seq-above-head"])
def test_a_rollback_finds_a_stray_not_yet_recorded_records_it_and_exits_2(request, tmp_path,
                                                                          stray):
    """Test 8 (f) (TP:1565-1567, :1671-1679): a stray pushed to origin with no
    write after it, so `diverged_sha` is NULL when the rollback starts, is
    caught by its fetch right before its transaction: it exits 2 naming
    `diverged at <sha>` and S2's two ways out, records the stray's sha, and
    leaves the switch, the journal, the head and `lanes/STORE` as they were.
    `[rendered-path]` changes a rendered path; `[register-seq-above-head]`
    changes none and carries `Register-Seq: <h+10>`. Fails until T326."""
    estate = _estate(request, tmp_path)
    reg = estate.reg
    other = reg.other_clone("stray")
    if stray == "rendered-path":
        log = "lanes/log/repoB-1.md"
        sha = reg.push_from(other, log, _origin_blob(reg, "refs/heads/main", log).decode("utf-8")
                            + "a stray line, pushed past the renderer\n", "a stray commit")
    else:
        h = estate.head()
        target = other / "handoffs" / "stray.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# a stray, outside the render set\n", encoding="utf-8")
        for argv in (["add", "--", "handoffs/stray.md"],
                     ["commit", "-q", "-m", f"a stray commit\n\nRegister-Seq: {h + 10}"],
                     ["push", "-q", "origin", "HEAD:main"]):
            subprocess.run(["git", "-C", str(other), *argv], check=True, env=reg.env,
                           capture_output=True, stdin=subprocess.DEVNULL)
        sha = reg.origin_tip()
    assert estate.mirror()["diverged_sha"] is None, "the stray was recorded before the rollback"
    before, count = estate.state(), estate.count()
    proc = estate.rollback()
    assert proc.returncode == 2, f"[{stray}] the rollback is not 2:\n{_said(proc)}"
    assert f"diverged at {sha}" in proc.stderr, _said(proc)
    for way in ("import --single", "render --revert"):
        assert way in proc.stderr, f"S2's way out {way!r} is not named:\n{_said(proc)}"
    assert estate.mirror()["diverged_sha"] == sha, estate.mirror()
    assert estate.state() == before and estate.count() == count, "the rollback wrote"
    assert estate.store_on_origin(), "lanes/STORE left origin"


def _holder(db, appname: str) -> subprocess.Popen:
    """The held session: the fixture's superuser holding `register_head`'s row
    `FOR UPDATE`, in a transaction left open (see the readings)."""
    holder = db.session(appname=appname)
    holder.stdin.write("BEGIN;\nSELECT seq FROM lanes_register.register_head WHERE id = 1 "
                       "FOR UPDATE;\n")
    holder.stdin.flush()
    return holder


def _wait_for(db, query: str, what: str, ceiling: float = 20.0) -> None:
    """Poll `query`, a count, in 0.05 s steps under `ceiling` until it counts
    one row or more."""
    end = time.monotonic() + ceiling
    while time.monotonic() < end:
        if db.psql(query).stdout.strip() not in ("", "0"):
            return
        time.sleep(0.05)
    pytest.fail(f"{what}: not seen within {ceiling} s")


def _locked(db, appname: str) -> str:
    return (f"SELECT count(*) FROM pg_stat_activity WHERE datname = '{db.name}' AND "
            f"application_name = '{appname}' AND wait_event_type = 'Lock';")


def _holding(db, appname: str) -> str:
    return (f"SELECT count(*) FROM pg_stat_activity WHERE datname = '{db.name}' AND "
            f"application_name = '{appname}' AND state = 'idle in transaction' AND "
            f"backend_xid IS NOT NULL;")


def _record(db, ws: str, sha: str | None, error: str | None,
            schema: str = "lanes_register") -> subprocess.CompletedProcess:
    """`record_mirror_state` as REGISTER-WRITER, in a session of its own."""
    lit = (lambda v: "NULL" if v is None else "'" + v.replace("'", "''") + "'")
    return db.psql(f"SET ROLE {WRITER};\nSELECT {schema}.record_mirror_state({lit(ws)}, "
                   f"{lit(sha)}, {lit(error)});\n", check=False)


@pytest.mark.parametrize("case", ["recorded", "last-error-only"])
def test_a_rollback_goes_back_to_its_check_past_a_last_error_and_refuses_a_divergence_recorded_meanwhile(
        request, tmp_path, case):
    """Test 8 (g) (TP:1568-1572, :1680-1692): with the held session on the
    head row and the rollback's call waiting on it (`wait_event_type =
    'Lock'`), the test records with `record_mirror_state`, then ends the held
    session by `ROLLBACK`; the call's `FOR SHARE` on `mirror_state` raises
    40001, and the command goes back to its check. `[recorded]`: it exits 2
    with `diverged at <sha>`, the switch, marker and journal unchanged.
    `[last-error-only]`: the check finds no divergence and the retry commits
    at `k+1`, the journal's last. Fails until T326 and T327."""
    estate = _estate(request, tmp_path)
    db, k, sha = estate.db, estate.k, "3" * 40
    before = estate.state()
    holder = _holder(db, "t273-g-holder")
    proc = None
    try:
        _wait_for(db, _holding(db, "t273-g-holder"), "the held session's lock on the head row")
        proc = estate.popen_rollback()
        _wait_for(db, _locked(db, "lanes-index"), "the rollback's call waiting on the head row")
        recorded = _record(db, "ws-t273-g", sha if case == "recorded" else None,
                           None if case == "recorded" else "the push was refused")
        assert recorded.returncode == 0, recorded.stderr
        holder.communicate(input="ROLLBACK;\n", timeout=60)
        out, err = proc.communicate(timeout=300)
    finally:
        for p in (proc, holder):
            if p is not None and p.poll() is None:
                p.kill()
                p.wait()
    ended = f"exit {proc.returncode}\n--- stdout ---\n{out}\n--- stderr ---\n{err}"
    assert "40001" in err and "lost its turn" in err, f"[{case}] no 40001 sent it back:\n{ended}"
    if case == "recorded":
        assert proc.returncode == 2 and f"diverged at {sha}" in err, ended
        assert estate.state() == before, "the refused rollback moved the switch or the journal"
    else:
        switch, journal = estate.switch(), estate.journal()
        assert switch["mode"] == "files", f"the retry did not commit:\n{ended}"
        assert journal[-1] == [k + 1, "rollback", True], journal
        assert switch["marker_state"] == "removing" or (
            switch["marker_state"] == "absent" and proc.returncode == 0), ended


def _between(calls: list, git_calls: list, sub: str = "fetch") -> list:
    """For each two step-1 calls in `calls` (the shim's or the fake's
    requests), whether a read came between them, and whether a `git <sub>`
    naming `origin` started between them."""
    steps = [n for n, c in enumerate(calls) if STEP_1_MARK in c.get("sent", c.get("stdin", ""))]
    found = []
    for a, b in zip(steps, steps[1:]):
        read = any(READ_MARK in calls[n].get("sent", calls[n].get("stdin", ""))
                   for n in range(a + 1, b))
        fetch = any(g["sub"] == sub and "origin" in g["argv"] and a + 1 <= g["psql_before"] <= b
                    for g in git_calls)
        found.append((read, fetch))
    return found


def test_a_rollback_retries_a_lost_turn_on_a_fresh_k_through_its_check(request, tmp_path):
    """Test 8 (h), RE (TP:1573-1576, :1693-1699): the shim holds the
    rollback's step-1 call for a window, and ws2 commits one write in it.
    The call gets LR001, the rollback reads the head afresh, runs its check
    again and commits on the new head: its entry is seq `k+2`, the journal's
    last; the shim's log shows two step-1 calls with a head read between
    them, and the wrapper's a fetch of `origin main` between them. Fails
    until T326, T327, T415 and T416."""
    estate = _estate(request, tmp_path)
    ws2 = MissedWorkstation(estate, "ws2")
    k = estate.k
    estate.arm([{"mode": "window", "match": "commit_write", "call": 1, "ms": 8000}])
    proc = estate.popen_rollback()
    try:
        end = time.monotonic() + 60
        while not any(STEP_1_MARK in c.get("sent", "") for c in estate.calls()):
            assert proc.poll() is None and time.monotonic() < end, (
                f"the rollback sent no step-1 call: {proc.poll()}")
            time.sleep(0.05)
        wrote = ws2.edit("log", "NOTED", f"lane:{MISSED_LANE}", "test 8 (h): in the window")
        out, err = proc.communicate(timeout=300)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    ended = f"exit {proc.returncode}\n--- stdout ---\n{out}\n--- stderr ---\n{err}"
    assert wrote.returncode == 0, f"ws2's write in the window:\n{_said(wrote)}"
    assert "LR001" in err, f"the step-1 call did not get LR001:\n{ended}"
    journal = estate.journal()
    assert journal[-2:] == [[k + 1, "write", False], [k + 2, "rollback", True]], (
        f"the rollback's entry is not k+2 = {k + 2} after ws2's write: {journal}\n{ended}")
    between = _between(estate.calls(), estate.git_calls())
    assert between and between[0] == (True, True), (
        f"two step-1 calls with a head read and a fetch of origin main between them: {between}")


#: The rollback's read as the fake answers it (FP): `_ROLLBACK_READS`' six
#: SELECTs, each a COPY's rows then the marker line: the window, the switch at
#: `primary` with the marker `present`, the head 1, the cutover's entry at it,
#: no divergence, and the database's clock.
NEXT = "\x1eLANES-INDEX-NEXT"


def _canned_read(version: int) -> str:
    rows = [f"{version}\t{version}\t{version}",
            f"primary\tpresent\t1\t{uuid.uuid4()}\t1", "1", f"cutover\t{uuid.uuid4()}",
            "\\N\t\\N\t\\N", f"{time.time():.3f}"]
    return "".join(f"{row}\n{NEXT}\n" for row in rows)


#: STEP 0'S GIT HALF AS THE FAKE ANSWERS IT (FP; lane 3's #165 6813528630, a
#: SHOULD from T326's builder). Right before step 1, T326 fetches `origin
#: main` and checks it as T322 recognises a divergence (B15 tasks:1546, "Step
#: 0's git half"). That makes two reads the rollback's own does not, each
#: answered by its own rule, placed before `READ_MARK`'s:
#: - T322's head read, after the fetch (`_render_read_head`,
#:   `4353eb08:lanes-index:15025`): four SELECTs, the window, the head with
#:   the switch, the resolved strays, and `mirror_state mir`'s `diverged_sha`
#:   and `last_error`. That last SELECT holds `READ_MARK` too, so without a
#:   rule of its own the fake gave it the rollback read's six answers, and
#:   the head read failed: 69. Since T326's `01cd35c` the second SELECT also
#:   reads the switch's `marker_state`, and any answer but those three fields
#:   is refused (`ed8e7d2:lanes-index:14995`, `:15020-15023`; lane 3's #165
#:   6814531692, a SHOULD from T326's fixer);
#: - T301's image read at `m` (`register_render_queries`, `:2265`): five
#:   SELECTs, which T322's image half replays and compares with the render
#:   set at the commit carrying `m` (`render_pass`, `:15377-15398`). No rule
#:   matched it, so the fake answered nothing: 69.
#: Each mark is a text of that request alone among the case's requests.
HEAD_READ_MARK, IMAGE_READ_MARK = "FROM mirror_state mir", "FROM journal_files f"


def _copy_field(value) -> str:
    """One field as `COPY ... TO STDOUT` writes it in TEXT format, which
    `_pg_unescape` reads back: `\\N` for NULL, `t` or `f` for a boolean, and
    a backslash, a tab, an LF or a CR escaped."""
    if value is None:
        return "\\N"
    if isinstance(value, bool):
        return "t" if value else "f"
    return (str(value).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
            .replace("\r", "\\r"))


def _copy_answer(selects: list) -> str:
    """The fake's stdout for one request of SELECTs, as `_query_many` reads
    it: each SELECT's rows, one line each, then the marker line."""
    return "".join("".join("\t".join(_copy_field(field) for field in row) + "\n"
                           for row in rows) + f"{NEXT}\n" for rows in selects)


def _canned_head_read(version: int) -> str:
    """T322's head read as the fake answers it, from the same canned register
    as `_canned_read`: the window, the head 1 with the switch at `primary`
    and the marker `present` (T326's three fields), no resolved stray, and
    neither a divergence nor a `last_error`."""
    return _copy_answer([[(version, version, version)], [(1, "primary", "present")], [],
                         [(None, None)]])


def _image_lines(data: bytes) -> tuple:
    """A file's lines, and whether it ends with an LF, as T301's
    `register_image_bytes` joins them back into `data`."""
    text = data.decode("utf-8")
    if not text:
        return [], True
    final = text.endswith("\n")
    return (text[:-1] if final else text).split("\n"), final


def _canned_images(version: int, rendered: dict, store: bytes) -> str:
    """T301's image read at seq 1 as the fake answers it: the import at 0,
    whose `create` and `append` edits rebuild `rendered`, the render set at
    the commit carrying `Register-Seq: 1` (`{path: bytes}`), each path proved
    by its `journal_files` row; then the cutover's entry at 1, which adds
    `lanes/STORE`, outside the render set. So the images at `m` are the
    render set there, and T322's image half finds no divergence."""
    edits, files = [], []
    for seq, paths in ((0, rendered), (1, {"lanes/STORE": store})):
        ordinal = 0
        for path in sorted(paths):
            lines, final = _image_lines(paths[path])
            ordinal += 1
            edits.append((seq, ordinal, "create", path, None, None, None, None))
            for number, line in enumerate(lines, 1):
                ordinal += 1
                edits.append((seq, ordinal, "append", path, number, None, line, None))
            files.append((seq, path, True, hashlib.sha256(paths[path]).hexdigest(), final))
    return _copy_answer([[(version, version, version)], [(1, 0)],
                         [(0, "import"), (1, "cutover")], edits, files])


@pytest.mark.parametrize("code", ["40001", "40P01", "55P03", "LR001"])
def test_a_rollback_goes_back_to_its_check_on_each_lost_turn_code(tmp_path, code):
    """Test 8 (h), FP (TP:1700-1706): the register's fake `psql` answers the
    rollback's reads, and step 0's git half's two, T322's head read and
    T301's image read (`HEAD_READ_MARK`, `IMAGE_READ_MARK`), from a canned
    register whose images at seq 1 are the workspace's render set there, and
    every step-1 call with exit 3 and `ERROR:  <code>: <message>`, and
    `LANES_REGISTER_DEADLINE_S=6` ends the tries: the fake's log shows two
    step-1 calls or more, each after the first preceded by a head read, and
    the wrapper's a fetch of `origin main` between each two; the exit is 75
    (AT-D9's row holds its bound). Runs by T203's flipped copy, on a files
    workspace whose origin carries the cutover's `lanes/STORE` at
    `Register-Seq: 1`, the canned head. Needs no engine; fails until T326,
    at its own assertion."""
    imp = _imp()
    ws = imp.Workspace(tmp_path / "w", imp.SEED)
    cutover = ws.commit({"lanes/STORE": "store=primary\ndatabase=register-test\n"},
                        "LANES(repoA-2@Eagle): cutover\n\nRegister-Seq: 1")
    copy = imp.flipped_indexer(tmp_path / "flip")
    version = int(re.search(r"^REGISTER_SCHEMA_VERSION = ([0-9]+)$",
                            copy.read_text(encoding="utf-8"), re.M).group(1))
    bin_ = tmp_path / "bin"
    _script(bin_ / "psql", REGISTER_FAKE_PSQL)
    _script(bin_ / "git", GIT_WRAPPER)
    log, answers = tmp_path / "psql.log", tmp_path / "answers.json"
    answers.write_text(json.dumps([
        {"match": HEAD_READ_MARK, "stdout": _canned_head_read(version)},
        {"match": IMAGE_READ_MARK, "stdout": _canned_images(
            version, ws.rendered(cutover), ws.blob(cutover, "lanes/STORE"))},
        {"match": READ_MARK, "stdout": _canned_read(version)},
        {"match": "commit_write", "exit": 3,
         "stderr": f"ERROR:  {code}: the test's lost turn ({code})\n"}]), encoding="utf-8")
    (bin_ / "git-wrapper.json").write_text(json.dumps({"git": _real_git(), "psql_log": str(log)}),
                                           encoding="utf-8")
    passfile = _private(tmp_path / "secret" / "pgpass",
                        "127.0.0.1:55432:register_db:t273:not-a-secret\n")
    url = "postgresql://t273@127.0.0.1:55432/register_db"
    conf = _private(tmp_path / "conf" / "lanes-index.conf", "\n".join([
        "mode=primary", f"register_url={url}", f"register_passfile={passfile}",
        f"reader_url={url}", f"reader_passfile={passfile}", "register_label=register-test",
        ""]))
    env = dict(ws.env, LANES_INDEX_CONFIG=str(conf), LANES_LANE=imp.OPERATOR,
               LANES_REGISTER_DEADLINE_S="6", FAKE_PSQL_LOG=str(log),
               FAKE_PSQL_ANSWERS=str(answers), LANES_EDIT=str(copy.parent / "lanes-edit.sh"),
               PATH=f"{bin_}{os.pathsep}{ws.env['PATH']}")
    proc = subprocess.run([sys.executable, str(copy), "rollback"], capture_output=True,
                          text=True, env=env, cwd=str(ws.wip), timeout=120,
                          stdin=subprocess.DEVNULL)
    calls = _requests(log)
    steps = [c for c in calls if STEP_1_MARK in c.get("stdin", "")]
    assert proc.returncode == EXIT_BUSY, (
        f"[{code}] the tries did not end 75 at the deadline ({len(steps)} step-1 calls):\n"
        f"{_said(proc)}")
    assert len(steps) >= 2, f"[{code}] fewer than two step-1 calls: {len(steps)}"
    between = _between(calls, [g for g in _jsonl(bin_ / "git-wrapper.log")])
    assert between and all(pair == (True, True) for pair in between), (
        f"[{code}] each two step-1 calls have a head read and a fetch of origin main "
        f"between them: {between}")


def test_a_write_that_committed_before_the_rollback_is_found_by_its_rerun_after_it(request,
                                                                                   tmp_path):
    """Test 8 (i) (TP:1577-1579, :1707-1716): ws2's write is lost after it
    lands (the shim's `no-reconnect` as `after` on its commit call), so ws2
    exits 3 with its pending record; the rollback then runs to its end from
    ws1; with the shim disarmed, the printed rerun on ws2 exits 0, not 69,
    the journal holds one entry for its id, and ws2's next new write exits
    69. Fails until T326, T327, T415, T416, T417 and T420."""
    estate = _estate(request, tmp_path)
    ws2 = MissedWorkstation(estate, "ws2")
    ws2.arm([{"mode": "no-reconnect", "as": "after", "match": "commit_write", "call": 1}])
    lost = ws2.edit("log", "NOTED", f"lane:{MISSED_LANE}", "test 8 (i): lost after it lands")
    assert lost.returncode == 3, f"ws2's lost write is not in doubt (3):\n{_said(lost)}"
    rerun = re.search(r"LANES_WRITE_ID=([0-9a-f-]{36})", lost.stderr)
    assert rerun, f"ws2 printed no rerun under the same id:\n{_said(lost)}"
    write_id = rerun.group(1)
    generation = re.search(r"LANES_WRITE_GENERATION=([0-9a-f-]{36})", lost.stderr)
    rerun_env = {"LANES_WRITE_ID": write_id}
    if generation:
        rerun_env["LANES_WRITE_GENERATION"] = generation.group(1)
    proc = estate.rollback()
    _assert_rolled_back(estate, proc)
    ws2.arm([])
    count = estate.count()
    again = ws2.edit("log", "NOTED", f"lane:{MISSED_LANE}", "test 8 (i): lost after it lands",
                     env=rerun_env)
    assert again.returncode == 0, f"the rerun is not 0 (the write id first, S1):\n{_said(again)}"
    assert estate.count() == count, "the rerun journaled"
    assert estate.rows(f"SELECT count(*) AS n FROM journal WHERE write_id = '{write_id}'") == \
        [{"n": 1}]
    fresh = ws2.edit("log", "NOTED", f"lane:{MISSED_LANE}", "test 8 (i): a new write")
    assert fresh.returncode == 69, f"ws2's next new write is not 69:\n{_said(fresh)}"


# ------------------------------------------------------------------ AT-F1
def test_rollback_refuses_to_start_while_the_mirror_is_diverged(request, tmp_path):
    """AT-F1, diverged (TP:5456-5459): test 6's diverged estate, a stray
    commit on origin that a write's render recorded; `rollback` exits 2
    before step 1, naming the divergence and S2's two tools, and the switch
    reads `primary` with the marker `present`, the journal and head unchanged,
    and `lanes/STORE` still on origin. Fails until T322, T326 and T327."""
    estate = _estate(request, tmp_path)
    reg = estate.reg
    log = "lanes/log/repoB-1.md"
    sha = reg.push_from(reg.other_clone("stray"), log, _origin_blob(
        reg, "refs/heads/main", log).decode("utf-8") + "a stray line\n", "a stray commit")
    wrote = reg.write("AT-F1: a write after the stray")
    assert wrote.returncode == 0, _said(wrote)
    deadline = time.monotonic() + 60
    while estate.mirror()["diverged_sha"] is None and time.monotonic() < deadline:
        time.sleep(0.5)
    assert estate.mirror()["diverged_sha"] == sha, (
        f"the render did not record the stray (T322): {estate.mirror()}")
    estate.arm()
    before = estate.state()
    proc = estate.rollback()
    assert proc.returncode == 2 and f"diverged at {sha}" in proc.stderr, _said(proc)
    for way in ("import --single", "render --revert"):
        assert way in proc.stderr, _said(proc)
    assert not any(STEP_1_MARK in c.get("sent", "") for c in estate.calls()), "step 1 was sent"
    assert estate.state() == before, "the refused rollback moved the switch, journal or head"
    assert estate.store_on_origin()


def _held_at_push(estate: RollbackEstate):
    """The rollback from ws1, held by the wrapper at its push: (the process,
    the FIFO's write end), or a failure where it ends first."""
    fifo = estate.root / "push.fifo"
    if not fifo.exists():
        os.mkfifo(str(fifo), 0o600)
    estate.arm(hold={"call": "push", "fifo": str(fifo)})
    proc = estate.popen_rollback()
    fd = _open_when_held(fifo, proc, 300)
    if fd is None:
        out, err = proc.communicate(timeout=60)
        pytest.fail(f"the rollback never reached its push: exit {proc.returncode}\n{out}\n{err}")
    return proc, fd


def _write_entry_now(estate: RollbackEstate, text: str) -> dict:
    """A write appending `text` to `lanes/LANES.md` as SQL renders it now."""
    old = estate.imp._renders(estate.db)["lanes/LANES.md"]
    new = old + text.encode("utf-8") + b"\n"
    return {"journal": {"kind": "write", "verb": "log", "lane": _imp().OPERATOR,
                        "workstation": "Eagle", "author": AUTHOR, "message": "AT-F1: meanwhile",
                        "args_sha256": ARGS_SHA256},
            "not_after": NOT_AFTER,
            "edits": [{"ord": 1, "op": "append", "path": "lanes/LANES.md", "new_text": text}],
            "files": [{"path": "lanes/LANES.md", "present": True,
                       "sha256": hashlib.sha256(new).hexdigest(), "final_newline": True}]}


def test_the_marker_removal_entry_is_written_with_the_switch_in_step_1(request, tmp_path):
    """AT-F1, the removal entry (TP:5460-5466): while the rollback is held at
    its push, one snapshot shows the switch at `files` with the marker
    `removing` and the removal entry, an operator entry, as the journal's
    last seq `k+1`: both or neither; a write tried meanwhile fails LR002 and
    journals nothing; on release the rollback ends with test 8 (a)'s oracle.
    Fails until T326 and T327."""
    estate = _estate(request, tmp_path)
    k = estate.k
    proc, fd = _held_at_push(estate)
    try:
        seen = estate.rows(
            "SELECT s.mode, s.marker_state, h.seq AS head, j.kind, j.operator FROM register_switch "
            "s, register_head h JOIN journal j ON j.seq = h.seq")[0]
        count = estate.count()
        entry = json.dumps(_write_entry_now(estate, "AT-F1: a write meanwhile")).replace("'", "''")
        gen = estate.switch()["generation"]
        version = estate.rows("SELECT version FROM schema_version")[0]["version"]
        tried = estate.db.psql(
            f"\\set VERBOSITY verbose\nSET search_path TO lanes_register;\nSET ROLE {WRITER};\n"
            f"BEGIN ISOLATION LEVEL SERIALIZABLE;\nSELECT commit_write({estate.head()}, "
            f"'{uuid.uuid4()}'::uuid, {version}, '{gen}'::uuid, '{entry}'::jsonb);\nCOMMIT;\n",
            check=False)
        counted = estate.count()
    finally:
        os.close(fd)
    out, err = proc.communicate(timeout=300)
    assert seen == {"mode": "files", "marker_state": "removing", "head": k + 1,
                    "kind": "rollback", "operator": True}, f"one snapshot read {seen}"
    assert tried.returncode != 0 and "LR002" in tried.stderr, (
        f"a write while the marker is removing is not LR002: {tried.stderr}")
    assert counted == count, "the refused write journaled"
    _assert_rolled_back(estate, SimpleNamespace(returncode=proc.returncode, stdout=out,
                                                stderr=err))


def test_a_rollback_rerun_resumes_after_its_own_entry(request, tmp_path):
    """AT-F1, the rerun (TP:5467-5469): a rerun after a kill at the push
    finds the marker `removing` and its own entry as the last seq, declares
    first, and goes on from the render: it ends with test 8 (a)'s oracle, no
    entry past `k+1`, and the declaration beside ws1's configuration. Fails
    until T326 and T327."""
    estate = _estate(request, tmp_path)
    k = estate.k
    proc, fd = _held_at_push(estate)
    held = [g for g in _jsonl(estate.bin / "git-wrapper.log") if g.get("outcome") == "held"]
    for pid in [g["pid"] for g in held] + [proc.pid]:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait()
    os.close(fd)
    switch = estate.switch()
    assert (switch["marker_state"], estate.journal()[-1]) == ("removing", [k + 1, "rollback", True])
    first = estate.outage_file()
    if first.exists():
        os.replace(str(first), str(first.with_name(OUTAGE_FILE + ".first-run")))
    estate.arm()
    again = estate.rollback()
    assert "stands" in again.stdout and "step 2" in again.stdout, _said(again)
    _assert_rolled_back(estate, again)
    assert estate.journal()[-1][0] == k + 1, "the rerun wrote an entry of its own"
    assert estate.outage_file().exists(), "the rerun did not declare first"


def test_a_rerun_after_an_unconfirmed_removal_and_a_files_mode_write_ends_0_with_the_marker_absent(
        pg, tmp_path):
    """AT-F2, "Unconfirmed", the rollback's removal push (B15 TP:5563-5566), with
    ops:338's files-mode write between the 3 and the rerun (lane 3's #165
    6814260122: T326's review, MUST-1, and its probe). On AT-F2's fixture,
    after a clean cutover and `rollback --hold-marker`, the removal is pushed
    and the read-back's fetch fails: `rollback` exits 3, the marker stays
    `removing`, and origin's tip is the removal, with `lanes/STORE` gone and
    `Register-Seq: k+1`. With the marker gone from origin, a files-mode write
    lands on it (ops:338, "after it, a files-mode write lands"), a commit of
    `lanes/LANES.md` from another clone, as the probe makes it. The rerun
    reads origin back first (ops:340; B15 tasks:1549), finds its removal, and
    ends 0: the switch reads `files` with the marker `absent`, it pushes
    nothing, the write stays origin's tip, and no divergence is recorded.
    Fails until T326's fix round, and T327 for the cutover's marker."""
    cut = _cut()
    f2 = cut.F2Register(tmp_path / "e", pg)
    reg, imp = f2.reg, f2.imp
    cutover = reg.cutover(conf=f2.conf)
    assert cutover.returncode == 0, f"[cutover] `cutover --import <C>` (T116):\n{_said(cutover)}"
    switch = imp._switch(pg)
    assert switch["marker_state"] == "present", (
        f"[cutover] the marker reads {switch['marker_state']}: the cutover's push, its read-back "
        f"and record_marker are lane 3's T327")
    k = imp._head(pg)
    held = reg.index("rollback", "--hold-marker", conf=f2.conf)
    assert held.returncode == 0, f"[hold-marker] `rollback --hold-marker` (T326):\n{_said(held)}"
    f2.arm({"call": "fetch", "mode": "fail", "after_push": True})
    proc = reg.index("rollback", conf=f2.conf)
    assert proc.returncode == EXIT_IN_DOUBT, (
        f"[3] the removal pushed, its read-back's fetch failed: not in doubt (T326):\n"
        f"{_said(proc)}")
    switch = imp._switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("files", "removing"), f"[3] {switch}"
    removal = reg.origin_tip()
    assert REGISTER_SEQ.findall(reg.origin_git("log", "-1", "--format=%B", removal)) == [
        str(k + 1)], f"[3] origin's tip {removal} does not carry Register-Seq: {k + 1}"
    assert "lanes/STORE" not in reg.origin_git("ls-tree", "-r", "--name-only", removal,
                                               "lanes/"), "[3] the removal is not on origin"
    f2.arm()
    clone = reg.other_clone("files-mode")
    path, line = "lanes/LANES.md", "a files-mode line, after the removal (ops:338)"
    text = (clone / path).read_text(encoding="utf-8") + line + "\n"
    wrote = reg.push_from(clone, path, text, "LANES(repoA-2@Raven): a files-mode write")
    assert wrote != removal, "[files-mode write] it did not land on origin"
    f2.arm()
    rerun = reg.index("rollback", conf=f2.conf)
    assert rerun.returncode == 0, (
        f"[rerun] after the 3 and a files-mode write, the rerun did not end 0: it reads origin "
        f"back first and finds its removal (T326's fix round, MUST-1):\n{_said(rerun)}")
    calls = f2.calls()
    assert cut._first_reach(calls) == "fetch", f"[rerun] it reached origin first by: {calls}"
    assert not any(c["sub"] == "push" for c in calls), "[rerun] the rerun pushed again"
    switch = imp._switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), f"[rerun] {switch}"
    assert reg.origin_tip() == wrote, "[rerun] the files-mode write is no longer origin's tip"
    assert line in reg.origin_git("show", f"{wrote}:{path}"), "[rerun] the write's line is gone"
    mirror = imp._rows(pg, "SELECT diverged_sha FROM mirror_state")[0]
    assert mirror["diverged_sha"] is None, (
        f"[rerun] the files-mode write was recorded as a divergence: {mirror}")


def test_a_reimport_after_a_rollback_continues_the_journal(request, tmp_path):
    """AT-F1, the re-import (TP:5470-5472): after the rollback, a re-import's
    baseline takes `k+2` with base `k+1`, and a later cutover takes `k+3`, so
    no `Register-Seq` repeats on `main`. Fails until T326 and T327."""
    estate = _estate(request, tmp_path)
    reg, k = estate.reg, estate.k
    _assert_rolled_back(estate, estate.rollback())
    reg.git("fetch", "-q", "origin")
    tip = reg.origin_tip()
    imported = reg.import_at(estate.db, tip, config=reg.index_conf)
    assert imported.returncode == 0, _said(imported)
    rows = estate.rows(f"SELECT seq, base_seq, kind FROM journal WHERE seq > {k + 1} ORDER BY seq")
    assert rows == [{"seq": k + 2, "base_seq": k + 1, "kind": "import"}], rows
    cut = reg.index("cutover", "--import", tip)
    assert cut.returncode == 0, _said(cut)
    assert estate.journal()[-1][:2] == [k + 3, "cutover"], estate.journal()
    seqs = estate.origin_seqs()
    assert len(seqs) == len(set(seqs)), f"a Register-Seq repeats on main: {seqs}"


def test_a_cutover_and_a_rollback_leave_exactly_two_operator_entries(request, tmp_path):
    """AT-F1 (TP:5473-5475): over the life of one database, a cutover and then
    a rollback leave exactly two journal rows with `operator` true, the
    cutover's and the rollback's. Fails until T326 and T327."""
    estate = _estate(request, tmp_path)
    _assert_rolled_back(estate, estate.rollback())
    operators = [[seq, kind] for seq, kind, operator in estate.journal() if operator]
    assert operators == [[1, "cutover"], [estate.k + 1, "rollback"]], operators


# ------------------------------------------------------------------ AT-F1: LR012
def _writer_session(db, appname: str) -> subprocess.Popen:
    """A session as REGISTER-WRITER, with the commit call's settings."""
    session = db.session(appname=appname)
    session.stdin.write(f"\\set VERBOSITY verbose\n\\set SHOW_CONTEXT never\n"
                        f"SET ROLE {WRITER};\n")
    session.stdin.flush()
    return session


def _rollback_call(reg: RollbackRegister, base: int, open_: bool = False) -> str:
    """The rollback's commit call, by hand: one SERIALIZABLE transaction
    around `commit_write` with a `rollback` entry; without its `COMMIT` where
    `open_`."""
    body = _entry("rollback", "rollback",
                  edits=[{"ord": 1, "op": "remove", "path": "lanes/STORE"}],
                  files=[{"path": "lanes/STORE", "present": False}])
    literal = json.dumps(body, ensure_ascii=True).replace("'", "''")
    call = (f"BEGIN ISOLATION LEVEL SERIALIZABLE;\nSELECT {SCRATCH}.commit_write({base}, "
            f"'{uuid.uuid4()}'::uuid, {reg.window()['version']}, "
            f"'{reg.switch()['generation']}'::uuid, '{literal}'::jsonb);\n")
    return call if open_ else call + "COMMIT;\n"


def _mirror_text(reg: RollbackRegister) -> list:
    return reg.sql(f"SELECT diverged_sha || '|' || found_utc::text || '|' || found_by_ws "
                   f"FROM {SCRATCH}.mirror_state;").split("|")


@pytest.mark.parametrize("case", ["recorded", "recorder-first", "last-error-only",
                                  "rollback-first"])
def test_a_rollback_entry_over_a_recorded_divergence_is_lr012(rb_register, case):
    """AT-F1, LR012 in the transaction (TP:5476-5498), by direct calls as
    REGISTER-WRITER on `primary` with the marker `present` (AT-LR006's route;
    lane 1's T107):
      * `[recorded]`: with a divergence recorded, the `rollback` entry gets
        LR012 with lane 1's text and `mirror_state`'s values, and nothing
        moves;
      * `[recorder-first]`: `record_mirror_state`'s transaction open first,
        the rollback's call waits on `mirror_state`, gets 40001 once it
        commits, and its retry on the head read afresh gets LR012;
      * `[last-error-only]`: the same with only `last_error` recorded: the
        retry commits;
      * `[rollback-first]`: the rollback's call open first, before its
        `COMMIT`, `record_mirror_state` waits on the row until it ends;
      * no session gets 40P01."""
    reg = rb_register
    k, sha, ws = reg.k, "4" * 40, "ws-t273-f1"
    record = f"SELECT {SCRATCH}.record_mirror_state('{ws}', " + (
        "NULL, 'the push was refused');\n" if case == "last-error-only" else f"'{sha}', NULL);\n")
    said = []
    if case == "recorded":
        assert reg.psql(record, WRITER).returncode == 0
        before = reg.state(), reg.mirror()
        proc = reg.psql(_rollback_call(reg, k), WRITER)
        said.append(proc.stderr)
        utc = _mirror_text(reg)[1]
        first = proc.stderr.strip().splitlines()[0] if proc.stderr.strip() else ""
        assert first == (f"ERROR:  LR012: rollback refused: diverged at {sha}, found {utc} by "
                         f"{ws}; resolve it first with import --single or render --revert "
                         f"(F1, S5)"), proc.stderr
        assert (reg.state(), reg.mirror()) == before, "the refused entry moved something"
    elif case in ("recorder-first", "last-error-only"):
        recorder = _writer_session(reg.db, "t273-recorder")
        call = None
        try:
            recorder.stdin.write("BEGIN;\n" + record)
            recorder.stdin.flush()
            reg.wait_sql(f"SELECT count(*) FROM pg_stat_activity WHERE application_name = "
                         f"'t273-recorder' AND state = 'idle in transaction' AND backend_xid IS "
                         f"NOT NULL;", "the recorder's open transaction")
            call = _writer_session(reg.db, "t273-call")
            call.stdin.write(_rollback_call(reg, k))
            call.stdin.flush()
            reg.wait_sql(_locked(reg.db, "t273-call"), "the rollback's call waiting")
            out, err = recorder.communicate(input="COMMIT;\n", timeout=60)
            said.append(err)
            assert recorder.returncode == 0, err
            out, err = call.communicate(timeout=60)
            said.append(err)
            assert "40001" in err, f"the waiting call did not get 40001: {err}"
        finally:
            for p in (recorder, call):
                if p is not None and p.poll() is None:
                    p.kill()
                    p.wait()
        retry = reg.psql(_rollback_call(reg, reg.head()), WRITER)
        said.append(retry.stderr)
        if case == "recorder-first":
            assert retry.returncode != 0 and "LR012" in retry.stderr, retry.stderr
            assert reg.head() == k
        else:
            assert retry.returncode == 0, retry.stderr
            assert reg.head() == k + 1 and reg.journal()[-1] == [k + 1, "rollback", True]
    else:
        call = _writer_session(reg.db, "t273-call")
        recorder = None
        try:
            call.stdin.write(_rollback_call(reg, k, open_=True))
            call.stdin.flush()
            reg.wait_sql(_holding(reg.db, "t273-call"), "the rollback's open call")
            recorder = _writer_session(reg.db, "t273-recorder")
            recorder.stdin.write(record)
            recorder.stdin.flush()
            reg.wait_sql(_locked(reg.db, "t273-recorder"), "record_mirror_state waiting")
            assert reg.mirror()["diverged_sha"] is None, "the record did not wait"
            out, err = call.communicate(input="COMMIT;\n", timeout=60)
            said.append(err)
            assert call.returncode == 0, err
            out, err = recorder.communicate(timeout=60)
            said.append(err)
            assert recorder.returncode == 0, err
        finally:
            for p in (recorder, call):
                if p is not None and p.poll() is None:
                    p.kill()
                    p.wait()
        assert reg.journal()[-1] == [k + 1, "rollback", True]
        assert reg.mirror()["diverged_sha"] == sha
    assert not any("40P01" in text for text in said), f"a session got 40P01: {said}"


def test_rollback_exits_2_on_lr012_naming_the_divergence_and_both_ways_out(rb_register):
    """AT-F1, LR012 through the command (TP:5499-5503): the shim holds
    `lanes-index rollback`'s step-1 call after its divergence check has
    passed, and the test records a divergence meanwhile; on release the call
    gets LR012, and `rollback` exits 2 with `diverged at <sha>` and S2's two
    ways out, writing nothing: the switch still reads `primary` with the
    marker `present`. Runs a copy with the constant False on the scratch
    schema, so it needs T304 alone."""
    reg = rb_register
    sha = "5" * 40
    copy = flipped_copy(LANES_INDEX, reg.root / "false-copy", False)
    fifo = reg.root / "step1.fifo"
    os.mkfifo(str(fifo), 0o600)
    reg.arm([{"mode": "hold", "fifo": str(fifo), "match": "commit_write", "call": 1}])
    before = reg.state()
    proc = subprocess.Popen([sys.executable, str(copy), "rollback"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env=reg.env(reg.config("conf")), cwd=str(reg.root / "operator"))
    fd = None
    try:
        fd = _open_when_held(fifo, proc)
        assert fd is not None, "the rollback's step-1 call was never held"
        recorded = reg.psql(f"SELECT {SCRATCH}.record_mirror_state('ws-t273-lr012', '{sha}', "
                            f"NULL);", WRITER)
        assert recorded.returncode == 0, recorded.stderr
        os.close(fd)
        fd = None
        out, err = proc.communicate(timeout=120)
    finally:
        if fd is not None:
            os.close(fd)
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    ended = f"exit {proc.returncode}\n--- stdout ---\n{out}\n--- stderr ---\n{err}"
    assert proc.returncode == 2, ended
    assert "LR012" in err and f"diverged at {sha}" in err, ended
    for way in ("import --single", "render --revert"):
        assert way in err, ended
    assert reg.state() == before, "the refused rollback wrote"
    switch = reg.switch()
    assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
