# SPDX-License-Identifier: Apache-2.0
"""Feature 007's AT-LRMPG, a managed PostgreSQL: its phase-N cases (T224;
FR-009, FR-053, FR-054, FR-055, FR-059) and its phase-W cases (T258; FR-009,
FR-054, FR-059) (opensoft/openRepoTools#165).

The test plan's thirteen phase-N names, byte for byte (AT-LRMPG, "Tests."),
and lane 1's two new since v3f, `dump_restore_privileges` (L1-2, T109's option
(a)) and `rotate_dump_job` (L1-3, T110's `rotate --dump-job`): 15 tests. The
phase-W cases, the logins' writes and reads through the flipped copy, are
T258's five, in the last section, "phase W (T258)", which says how they run.

THE SERVER (X, `97147aa8`, kept at Y): the register runs on CNPG, so the
admin of every case stands for the database's owner as CNPG's `initdb` makes
it, `lanes_register_admin` (lane 1's T109 name), `LOGIN CREATEROLE CREATEDB`
and no `SUPERUSER`. The cluster's own superuser stands for the provider: it
makes that admin and nothing of the register. One admin service (R-P41, lane
3's ruling on open point 41): the admin creates the register's database
first, as his own act, through his own maintenance connection, so he owns
it; every `lanes-index` step then runs through ONE service in the test's own
`$HOME/.pg_service.conf`, which names that database. `lanes-index` never
picks a database.

THE FIXTURE (AT-LRMPG, "Fixture"). Each engine case runs on a
`stoppable_cluster` of its own, since roles are global to a cluster and no
test changes a role on the session cluster; with no engine it skips with
T205's banner. Its `pg_hba.conf` takes `scram-sha-256` on the socket for
every login but the superuser and the admin, and it logs as section 5.6's
counting cluster does (`log_connections`, `log_statement=all`, each line
prefixed with its backend's pid). `bootstrap` runs with `--no-passwords`
where no password is under test, and under a pty where a password line is;
every `lanes-index login` runs under a pty, since it refuses off a terminal.
Each password line the run prints goes into a 0600 file under the test's
`$HOME/passfiles` (`passfiles-new` after a restore), which a login's
`PGPASSFILE` names. A second server, for a restore, is a `pgcluster.Cluster`
the test starts itself and destroys at its teardown.

CHECK 11 runs on section 5.6's TLS cluster, T229's `tls_cluster`, which
`tests/pgcluster.py` gives since this line merged line FX at T229d: each id
skips with T205's banner where there is no engine. What this module reads
of that fixture, from F12b's T229 text and not from a contract, is
`TlsEnvironment`'s docstring.

THE NO-ENGINE CASE is `login`'s refusals: each is refused before any
connection, so the register's fake `psql` (T203) stands in for the server and
its log shows that nothing was made. Its control, a good name under the pty,
reaches the fake, so each refusal is the condition's and never a verb this
build lacks.

READ FROM LANE 1'S CODE, NOT A CONTRACT (T109, T110 and T119 at
`l1-007-R-merge5`, `1511fa7f`): each object line is `<what>: created` or
`<what>: unchanged`, with a detail in brackets after it; a password-file line
is `*:*:<database>:<login>:<password>`; `login`'s argv is `login add|rotate
<engineer>|--dump-job --admin-service <service>`; the floors as
`pg_roles.rolconfig` holds them; and `ready`'s line form, `check <n>: ok` or
`check <n>: FAIL: <reason>`, as T218b reads it.
"""

from __future__ import annotations

import atexit
import contextlib
import errno
import hashlib
import itertools
import json
import os
import re
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest

from conftest import REPO, WINDOWS_SKIP
from sql_register_helpers import (LANES_INDEX, PSQL_SHIM, PSQL_SHIM_CONTROL, PSQL_SHIM_ENDS,
                                  PSQL_SHIM_LOG, REGISTER_FAKE_PSQL, RENDER_SET_PATH, flipped_copy,
                                  guard_strip_env)

pytestmark = [WINDOWS_SKIP]

#: THE LANDING GATE'S TABLE (T280; task sets version 12b's rule 11,
#: opensoft/openRepoTools#165 6877673742), TEMPORARY: T281 removes it in the
#: last set. `tests/sql_register_gate.py` reads it: in a code pull request's
#: full CI, each id of a function below is skipped until every task its row
#: names has landed, and the skip names them. The rows are T224's Order
#: (tasks:2156), T230's (tasks:2220, with its As built at :2219) and T258's
#: (tasks:2464), tasks.md at lane 3's commit 17 `204145ae`. No task is common
#: to all 21 functions, so there is no "*" row.
SQL_REGISTER_GATE_TABLE = {
    # T224: until L1-A7 (T109), L1-A8 (T110), L1-A17 (T119, T120) and T229.
    # Lane 1's two cases' T109 and T110, and `[in-recovery]`'s T229, are in
    # that list. T230's three check-11 ids keep check 11's row, which holds
    # their T119 (L1-A17).
    "test_bootstrap_without_a_superuser_runs_twice_with_one_catalog":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_bootstrap_refuses_a_database_its_admin_does_not_own":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_login_add_makes_an_engineers_two_logins_with_their_floors_and_prints_their_lines_once":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_login_add_run_again_puts_back_a_lost_membership_and_changes_nothing_else":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_a_member_made_without_the_login_step_carries_no_floor_and_fails_ready_check_12":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_ready_check_12_passes_the_logins_the_step_made":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_login_rotate_keeps_an_open_session_and_refuses_the_old_password":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_login_refuses_a_bad_name_a_connection_string_and_a_pipe":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_an_open_session_gets_42501_between_the_revokes_steps_then_57p01":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_the_reader_login_dumps_both_schemas_and_still_cannot_write":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_a_restore_from_the_dump_equals_its_source_with_new_passwords":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_a_restore_from_the_providers_copy_keeps_the_roles_and_takes_new_passwords":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_ready_check_11_needs_tls_and_the_primary":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_dump_restore_privileges_hold_after_roles_only_the_restore_and_bootstrap":
        ("T109", "T110", "T119", "T120", "T229"),
    "test_rotate_dump_job_changes_only_the_dump_logins_password":
        ("T109", "T110", "T119", "T120", "T229"),
    # T230: `tls_at_load` until L1-A3 (T104); its `[for-guard]` also until
    # T113, which builds the `register read` it needs (tasks:2219).
    "test_tls_at_load_refuses_a_url_off_loopback_without_verify_full_and_a_root_file":
        ("T104",),
    "test_tls_at_load_refuses_a_url_off_loopback_without_verify_full_and_a_root_file[for-guard]":
        ("T104", "T113"),
    # T258: until L1-A8 (T110), L4-B3 (T413, T414, T415) and L4-B5 (T417).
    "test_two_writer_logins_write_alike_and_the_log_names_each":
        ("T110", "T413", "T414", "T415", "T417"),
    "test_a_revoked_login_is_refused_69_and_writes_nothing":
        ("T110", "T413", "T414", "T415", "T417"),
    "test_a_write_cut_by_a_revoke_mid_commit_is_in_doubt_and_ends_3_with_nothing_written":
        ("T110", "T413", "T414", "T415", "T417"),
    "test_reader_url_takes_target_session_attrs_primary_not_read_write":
        ("T110", "T413", "T414", "T415", "T417"),
    "test_after_login_rotate_the_old_password_files_write_exits_69_and_the_new_lines_commit_once":
        ("T110", "T413", "T414", "T415", "T417"),
}

#: The admin, as CNPG's `initdb` makes the database's owner (lane 1's T109
#: name, opsXfactory-6's; `[X: hosting]`).
ADMIN = "lanes_register_admin"

#: Design.md section 1.4's roles.
OWNER, WRITER, READER = "lanes_register_owner", "lanes_register_writer", "lanes_register_reader"
INDEXER, DUMP = "lanes_indexer", "lanes_register_dump"
REGISTER, INDEX = "lanes_register", "lanes_index"

#: The bootstrap's inputs.
LABEL, REPOSITORY, LANE = "register-t224", "opensoft/t224-workspace", "t224-managed"

#: Each half's floors as `pg_roles.rolconfig` holds them (the login step,
#: Y:2288-2300), and as `SHOW` prints them in a session of that login.
ROLCONFIG = {"w": ["lock_timeout=2000ms", "statement_timeout=5s",
                   "idle_in_transaction_session_timeout=5s"],
             "r": ["default_transaction_read_only=on", "lock_timeout=1000ms",
                   "statement_timeout=1500ms"]}
SHOWN = {"w": {"lock_timeout": "2s", "statement_timeout": "5s",
               "idle_in_transaction_session_timeout": "5s"},
         "r": {"default_transaction_read_only": "on", "lock_timeout": "1s",
               "statement_timeout": "1500ms"}}
#: What a member made without the login step shows (lane 1's run).
NO_FLOORS = {"lock_timeout": "0", "statement_timeout": "0",
             "idle_in_transaction_session_timeout": "0", "default_transaction_read_only": "off"}

#: One object line of `bootstrap` or `login` (lane 1's `_bootstrap_say`).
OBJECT_LINE = re.compile(r"^(?P<what>[^\n]+?): (?P<state>created|unchanged)(?: \([^\n]*\))?$", re.M)
#: One password-file line (lane 1's `_register_pgpass_line`).
PASS_LINE = re.compile(r"^\*:\*:(?P<db>[^:\n]+):(?P<login>[^:\n]+):(?P<password>[^:\s]+)$", re.M)
#: One of `ready`'s check lines (T119's line form).
CHECK_LINE = re.compile(r"^check (\d+): (ok|FAIL)\b:?[ \t]*(.*)$", re.M)

#: The three database-level statements `--roles-only` runs (T109's option (a)).
DB_LEVEL = ("REVOKE ALL FROM PUBLIC", "GRANT CONNECT", "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC")

#: O2's dump command, run as the dump job's login (6722541787).
DUMP_COMMAND = ("umask 077 && pg_dump --no-password --schema=lanes_register "
                "--schema=lanes_index --format=custom --file={file}")

#: The import entry's fields (T222f's form, AT-LR006's first step).
WS, AUTHOR, OPERATOR = "ws-t224", "T224 Fixture <t224@example.invalid>", "operator-t224"
MARKER_COMMIT = "c0ffee" + "4" * 34


def _said(proc: subprocess.CompletedProcess) -> str:
    return f"exit {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"


def _private(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    return path


def _run(argv: list, env: dict, cwd: Path, *, pty_run: bool) -> subprocess.CompletedProcess:
    """`argv`, its stdout a pipe, or a terminal (`pty.openpty()`) where
    `pty_run`; its stdin is /dev/null and its stderr a pipe."""
    if not pty_run:
        return subprocess.run(argv, capture_output=True, text=True, env=env, cwd=str(cwd),
                              timeout=300, stdin=subprocess.DEVNULL)
    import pty
    primary, secondary = pty.openpty()
    try:
        proc = subprocess.Popen(argv, stdout=secondary, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, env=env, cwd=str(cwd))
        os.close(secondary)
        secondary = -1
        out = b""
        while True:
            try:
                chunk = os.read(primary, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        err = proc.stderr.read().decode("utf-8", "replace")
        proc.wait(timeout=300)
    finally:
        os.close(primary)
        if secondary >= 0:
            os.close(secondary)
    return subprocess.CompletedProcess(argv, proc.returncode,
                                       out.decode("utf-8", "replace").replace("\r\n", "\n"), err)


def _objects(text: str) -> list:
    """Each object line's (what, state), in order."""
    return [(m.group("what"), m.group("state")) for m in OBJECT_LINE.finditer(text)]


def _passwords(text: str) -> dict:
    """Each password-file line, by login."""
    found: dict = {}
    for m in PASS_LINE.finditer(text):
        assert m.group("login") not in found, f"{m.group('login')}'s line is printed twice:\n{text}"
        found[m.group("login")] = m.group(0)
    return found


def _checks(text: str) -> dict:
    return {int(m.group(1)): (m.group(2), m.group(3) or "") for m in CHECK_LINE.finditer(text)}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Session:
    """A `psql` session of a login, held open by the test (AT-LRMPG's FIFO):
    its statements go on stdin, each followed by a `\\warn` marker, and the
    test waits for each marker on stderr, which `psql` writes unbuffered. No
    `ON_ERROR_STOP`, so a refused statement leaves the session open."""

    def __init__(self, argv: list, env: dict):
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env)
        self.err = b""

    def send(self, sql: str, marker: str, deadline: float = 30.0) -> str:
        """`sql`, then the marker; the stderr written until the marker, or
        until `psql` ended."""
        start = len(self.err)
        try:
            self.proc.stdin.write(f"{sql}\n\\warn {marker}\n".encode("utf-8"))
            self.proc.stdin.flush()
        except BrokenPipeError:
            pass
        fd = self.proc.stderr.fileno()
        end = time.monotonic() + deadline
        while marker.encode() not in self.err[start:]:
            assert time.monotonic() < end, (
                f"psql gave no {marker!r} within {deadline:.0f} s: {self.err[start:]!r}")
            ready, _, _ = select.select([fd], [], [], 0.2)
            if ready:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                self.err += chunk
        return self.err[start:].decode("utf-8", "replace")

    def close(self) -> subprocess.CompletedProcess:
        try:
            self.proc.stdin.close()
        except BrokenPipeError:
            pass
        out = self.proc.stdout.read().decode("utf-8", "replace")
        self.err += self.proc.stderr.read()
        self.proc.wait(timeout=60)
        return subprocess.CompletedProcess([], self.proc.returncode, out,
                                           self.err.decode("utf-8", "replace"))


def _another_cluster(request, *, data_from: Path | None = None):
    """A second server for a restore: a `pgcluster.Cluster` of the test's
    own, destroyed at its teardown. With `data_from`, it starts on a copy of
    that stopped data directory, which stands for the provider's snapshot or
    point-in-time restore; otherwise it is a new cluster."""
    engine = request.getfixturevalue("pg_engine")
    import pgcluster
    cluster = pgcluster.Cluster(engine.bindir)
    request.addfinalizer(cluster.destroy)
    if data_from is None:
        cluster.start()
        return cluster
    cluster.root = Path(tempfile.mkdtemp(prefix=pgcluster.PREFIX, dir=pgcluster.SOCKET_PARENT))
    (cluster.root / "owner").write_text(f"{os.getpid()} {pgcluster._ticks(os.getpid())}\n")
    shutil.copytree(data_from, cluster.root / "data", symlinks=True)
    (cluster.root / "data").chmod(0o700)
    cluster.launch()
    return cluster


class Managed:
    """One test's managed PostgreSQL: a cluster whose superuser stands for
    the provider, the admin it made, the admin's services, and the
    `lanes-index` runs, each with the test's own `$HOME`."""

    def __init__(self, request, root: Path, *, cluster=None, scram: bool = True):
        # A CLUSTER OF THE TEST'S OWN WITH AN EMPTY TEMPLATE, as the provider's
        # new server is: T227 makes `stoppable_cluster`'s template the bootstrap,
        # with T228's logins, which would leave this admin, no superuser,
        # without ADMIN OPTION on roles it did not make (PostgreSQL 16).
        self.cluster = cluster if cluster is not None else _another_cluster(request)
        import pgcluster
        self.pgcluster = pgcluster
        self.port = int(getattr(self.cluster, "port", pgcluster.PORT))
        self.root = root
        self.home = root / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        (root / "t").mkdir(exist_ok=True)
        self.services: dict = {}
        env = guard_strip_env(os.environ, strip=("T224_", "XDG_"))
        env.update(HOME=str(self.home), XDG_CONFIG_HOME=str(root / "config"),
                   XDG_STATE_HOME=str(root / "state"), TMPDIR=str(root / "t"),
                   LANES_WORKSTATION="Eagle", LANES_NO_GITHUB="1", LC_ALL="C",
                   PATH=os.pathsep.join([str(self.cluster.bindir),
                                         os.environ.get("PATH", os.defpath)]))
        self.env = env
        # THE PROVIDER makes the admin, CNPG's initdb owner: no SUPERUSER.
        self.cluster.psql(f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ADMIN}') THEN "
                          f"CREATE ROLE {ADMIN} LOGIN CREATEROLE CREATEDB NOSUPERUSER; END IF; END $$;")
        # SECTION 5.6'S COUNTING CLUSTER'S LOG: each connection and statement,
        # each line prefixed with its backend's pid.
        self.cluster.psql("ALTER SYSTEM SET log_connections = on;\n"
                          "ALTER SYSTEM SET log_statement = 'all';\n"
                          "ALTER SYSTEM SET log_line_prefix = '%p ';\n"
                          "SELECT pg_reload_conf();\n")
        if scram:
            # SCRAM ON THE SOCKET for every login but the provider and the admin.
            (self.cluster.root / "data" / "pg_hba.conf").write_text(
                f"local all {pgcluster.SUPERUSER} trust\nlocal all {ADMIN} trust\n"
                "local all all scram-sha-256\n", encoding="utf-8")
            self.cluster.psql("SELECT pg_reload_conf();")

    # ------------------------------------------------------------ the server
    def psql(self, sql: str, db: str = "postgres", user: str | None = None,
             check: bool = True) -> subprocess.CompletedProcess:
        """`sql` as the provider (the cluster's superuser), or as `user`
        where trust lets it in: the admin's own maintenance connection."""
        return self.cluster.psql(sql, dbname=db, user=user or self.pgcluster.SUPERUSER,
                                 check=check)

    def value(self, sql: str, db: str) -> str:
        return self.psql(sql, db).stdout.strip()

    def log(self) -> str:
        return (self.cluster.root / "server.log").read_text(encoding="utf-8", errors="replace")

    def database(self, name: str) -> str:
        """The admin's own act (R-P41): he creates the register's database
        through his maintenance connection, so he owns it, and one service
        in `~/.pg_service.conf` names it. Returns the service."""
        self.psql(f"CREATE DATABASE {name};", user=ADMIN)
        return self.service(name)

    def service(self, database: str) -> str:
        service = f"t224_{database}"
        self.services[service] = database
        _private(self.home / ".pg_service.conf", "".join(
            f"[{s}]\nhost={self.cluster.root}\nport={self.port}\nuser={ADMIN}\ndbname={d}\n\n"
            for s, d in self.services.items()))
        return service

    # ------------------------------------------------------------ lanes-index
    def lanes(self, *args: str, pty_run: bool = False,
              config: Path | None = None) -> subprocess.CompletedProcess:
        env = dict(self.env)
        if config is not None:
            env["LANES_INDEX_CONFIG"] = str(config)
        return _run([sys.executable, str(REPO / "lanes-index"), *args], env, self.root,
                    pty_run=pty_run)

    def bootstrap(self, service: str, *flags: str, pty_run: bool = False) -> subprocess.CompletedProcess:
        args = ["bootstrap", "--admin-service", service]
        if "--roles-only" not in flags:
            args += ["--label", LABEL, "--repository", REPOSITORY, "--lane", LANE]
        return self.lanes(*args, *flags, pty_run=pty_run)

    def bootstrapped(self, service: str) -> None:
        proc = self.bootstrap(service, "--no-passwords")
        assert proc.returncode == 0, f"the bootstrap failed:\n{_said(proc)}"

    def login(self, action: str, who: str, service: str, *, pty_run: bool = True) -> subprocess.CompletedProcess:
        target = ["--dump-job"] if who == DUMP else [who]
        return self.lanes("login", action, *target, "--admin-service", service, pty_run=pty_run)

    def logins(self, service: str, *engineers: str, dump: bool = True,
               folder: str = "passfiles") -> dict:
        """`login add` for each engineer, and for the dump job, under the pty:
        each printed line in its login's 0600 file. Returns the files."""
        files: dict = {}
        for who in [*engineers, *([DUMP] if dump else [])]:
            proc = self.login("add", who, service)
            assert proc.returncode == 0, f"login add {who} failed:\n{_said(proc)}"
            files.update(self.passfiles(proc.stdout, folder))
        return files

    def passfiles(self, text: str, folder: str = "passfiles") -> dict:
        return {login: _private(self.home / folder / login, line + "\n")
                for login, line in _passwords(text).items()}

    # ------------------------------------------------------------ the logins
    def login_env(self, login: str, db: str, passfile: Path | None) -> dict:
        env = {k: v for k, v in self.env.items() if not k.startswith("PG")}
        env.update(PGHOST=str(self.cluster.root), PGPORT=str(self.port), PGUSER=login,
                   PGDATABASE=db, PGCONNECT_TIMEOUT="10")
        if passfile is not None:
            env["PGPASSFILE"] = str(passfile)
        return env

    def as_login(self, login: str, db: str, sql: str, passfile: Path | None,
                 **variables) -> subprocess.CompletedProcess:
        """`sql` in a new session of `login`, on the socket, with its
        password file; `VERBOSITY=verbose`, so an error carries its SQLSTATE."""
        argv = [self.cluster.tool("psql"), "-X", "-q", "-A", "-t", "-w", "-v", "ON_ERROR_STOP=1",
                "-v", "VERBOSITY=verbose"]
        for name, value in variables.items():
            argv += ["-v", f"{name}={value}"]
        return subprocess.run(argv + ["-f", "-"], input=sql, capture_output=True, text=True,
                              timeout=60, env=self.login_env(login, db, passfile), check=False)

    def session(self, login: str, db: str, passfile: Path | None) -> Session:
        argv = [self.cluster.tool("psql"), "-X", "-q", "-A", "-t", "-w", "-v", "VERBOSITY=verbose"]
        return Session(argv, self.login_env(login, db, passfile))

    def shown(self, login: str, db: str, passfile: Path | None) -> dict:
        """`SHOW` of the four floors in a session of `login`."""
        names = sorted(NO_FLOORS)
        proc = self.as_login(login, db, "".join(f"SHOW {name};\n" for name in names), passfile)
        assert proc.returncode == 0, f"{login} could not log in to SHOW its floors:\n{_said(proc)}"
        return dict(zip(names, proc.stdout.split()))

    def role(self, login: str) -> dict:
        """A role's attributes, its own settings, its verifier and its groups,
        read by the provider."""
        row = self.value(
            "SELECT json_build_object('canlogin', a.rolcanlogin, 'super', a.rolsuper, "
            "'config', coalesce(r.rolconfig, '{}'), 'verifier', a.rolpassword, "
            "'groups', ARRAY(SELECT g.rolname::text FROM pg_auth_members m JOIN pg_roles g "
            "ON g.oid = m.roleid WHERE m.member = a.oid ORDER BY 1)) "
            f"FROM pg_authid a JOIN pg_roles r ON r.oid = a.oid WHERE a.rolname = '{login}';", "postgres")
        return json.loads(row) if row else {}

    # ------------------------------------------------------------ the register
    def entry(self, db: str, kind: str, path: str, text: str) -> dict:
        """An entry creating `path` with one line (T222f's form): `import` for
        `lanes/LANES.md`, AT-LR006's first step, or `cutover` for
        `lanes/STORE`."""
        clock = self.value("SELECT (clock_timestamp() + interval '60 s')::text;", db)
        journal = {"kind": kind, "verb": kind, "lane": OPERATOR, "workstation": WS,
                   "author": AUTHOR, "message": f"{kind} by {OPERATOR} (T224)"}
        if kind == "import":
            journal.update(git_commit="c" * 40, git_tree="d" * 40)
        return {"journal": journal, "not_after": clock,
                "edits": [{"ord": 1, "op": "create", "path": path},
                          {"ord": 2, "op": "append", "path": path, "new_text": text}],
                "files": [{"path": path, "present": True, "final_newline": True,
                           "sha256": _sha256((text + "\n").encode("utf-8"))}]}

    def commit(self, db: str, login: str, passfile: Path, entry: dict) -> subprocess.CompletedProcess:
        """ONE `commit_write` call as `login`, at SERIALIZABLE (T222f's form)."""
        head = self.value(f"SELECT seq FROM {REGISTER}.register_head;", db)
        client = self.value(f"SELECT version FROM {REGISTER}.schema_version;", db)
        generation = self.value(f"SELECT generation FROM {REGISTER}.register_switch;", db)
        sql = ("BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
               f"SELECT {REGISTER}.commit_write(:base, :'wid'::uuid, :client, :'gen'::uuid, "
               ":'entry'::jsonb);\nCOMMIT;\n")
        return self.as_login(login, db, sql, passfile, base=head, wid=str(uuid.uuid4()),
                             client=client, gen=generation,
                             entry=json.dumps(entry, ensure_ascii=False))

    def to_primary(self, db: str, login: str, passfile: Path) -> None:
        """AT-LR006's route on a bootstrapped database: an `import` entry, a
        `cutover` entry over it, then `record_marker`, as `login`."""
        for kind, path, text in (("import", "lanes/LANES.md", "# Lanes"),
                                 ("cutover", "lanes/STORE", "primary")):
            proc = self.commit(db, login, passfile, self.entry(db, kind, path, text))
            assert proc.returncode == 0, f"the {kind} entry did not commit:\n{_said(proc)}"
        seq = self.value(f"SELECT seq FROM {REGISTER}.register_head;", db)
        client = self.value(f"SELECT version FROM {REGISTER}.schema_version;", db)
        proc = self.as_login(login, db, f"SELECT {REGISTER}.record_marker(:client, :seq, "
                             ":'commit', :'ws');\n", passfile, client=client, seq=seq,
                             commit=MARKER_COMMIT, ws=WS)
        assert proc.returncode == 0 and proc.stdout.strip() == "present", _said(proc)

    def config(self, name: str, register_url: str, register_passfile: Path,
               reader_url: str, reader_passfile: Path) -> Path:
        return _private(self.root / name / "lanes-index.conf", "\n".join([
            "mode=index", f"register_url={register_url}", f"register_passfile={register_passfile}",
            f"reader_url={reader_url}", f"reader_passfile={reader_passfile}",
            f"register_label={LABEL}", ""]))

    def socket_url(self, login: str, db: str) -> str:
        return f"postgresql://{login}@{quote(str(self.cluster.root), safe='')}:{self.port}/{db}"

    def ready(self, config: Path) -> subprocess.CompletedProcess:
        return self.lanes("ready", "--expect", "index", "--release", "0.0.0-t224", "--env",
                          "t224", config=config)

    def dump(self, db: str, passfile: Path, name: str) -> tuple:
        """O2's command as the dump job's login, its connection from its
        environment and `PGPASSFILE` naming its password file."""
        target = self.root / name
        proc = subprocess.run(["bash", "-c", DUMP_COMMAND.format(file=target)],
                              capture_output=True, text=True, timeout=300,
                              env=self.login_env(DUMP, db, passfile), check=False)
        return proc, target

    def catalog(self, db: str) -> list:
        """Both schemas' catalogs: each object, its kind, its owner and its
        ACL as a set of its elements; each function's signature, owner, ACL
        and security; each default ACL; and the roles' attributes and
        memberships. One sorted list."""
        sql = f"""
SELECT json_agg(x ORDER BY x) FROM (
  SELECT format('rel %s.%s %s owner=%s acl=%s', n.nspname, c.relname, c.relkind,
                pg_get_userbyid(c.relowner),
                (SELECT string_agg(a::text, ',' ORDER BY a::text) FROM unnest(c.relacl) a)) AS x
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname IN ('{REGISTER}', '{INDEX}')
  UNION ALL
  SELECT format('fn %s.%s(%s) owner=%s secdef=%s acl=%s', n.nspname, p.proname,
                pg_get_function_identity_arguments(p.oid), pg_get_userbyid(p.proowner),
                p.prosecdef,
                (SELECT string_agg(a::text, ',' ORDER BY a::text) FROM unnest(p.proacl) a))
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname IN ('{REGISTER}', '{INDEX}')
  UNION ALL
  SELECT format('ns %s owner=%s acl=%s', n.nspname, pg_get_userbyid(n.nspowner),
                (SELECT string_agg(a::text, ',' ORDER BY a::text) FROM unnest(n.nspacl) a))
    FROM pg_namespace n WHERE n.nspname IN ('{REGISTER}', '{INDEX}')
  UNION ALL
  SELECT format('defacl %s %s %s %s', pg_get_userbyid(d.defaclrole),
                coalesce(d.defaclnamespace::regnamespace::text, '-'), d.defaclobjtype,
                (SELECT string_agg(a::text, ',' ORDER BY a::text) FROM unnest(d.defaclacl) a))
    FROM pg_default_acl d
  UNION ALL
  SELECT format('role %s login=%s super=%s createrole=%s createdb=%s config=%s', r.rolname,
                r.rolcanlogin, r.rolsuper, r.rolcreaterole, r.rolcreatedb,
                coalesce(array_to_string(r.rolconfig, ' '), '-'))
    FROM pg_roles r WHERE r.rolname LIKE 'lanes%'
  UNION ALL
  SELECT format('member %s of %s inherit=%s set=%s', pg_get_userbyid(m.member),
                pg_get_userbyid(m.roleid), m.inherit_option, m.set_option)
    FROM pg_auth_members m
   WHERE pg_get_userbyid(m.roleid) LIKE 'lanes%' OR pg_get_userbyid(m.member) LIKE 'lanes%'
) AS t(x);
"""
        return json.loads(self.value(sql, db) or "[]")

    def rows(self, db: str) -> str:
        """Both schemas' rows, table by table, each table's rows sorted."""
        tables = self.value(
            "SELECT string_agg(format('%I.%I', schemaname, tablename), ' ' ORDER BY schemaname, tablename) "
            f"FROM pg_tables WHERE schemaname IN ('{REGISTER}', '{INDEX}');", db).split()
        views = self.value(
            "SELECT string_agg(format('%I.%I', schemaname, viewname), ' ' ORDER BY schemaname, viewname) "
            f"FROM pg_views WHERE schemaname IN ('{REGISTER}', '{INDEX}');", db).split()
        return "\n".join(f"{name}: " + self.value(
            f"SELECT coalesce(json_agg(r ORDER BY r::text), '[]') FROM {name} r;", db)
            for name in tables + views)

    def connects(self, login: str, db: str, passfile: Path) -> bool:
        return self.as_login(login, db, "SELECT 1;\n", passfile).returncode == 0


def _no_clear_text(log: str, lines: dict) -> None:
    """The server's log holds each printed password only as a SCRAM
    verifier, never as clear text (O6)."""
    for login, line in lines.items():
        secret = line.rsplit(":", 1)[1]
        assert secret not in log, f"the server's log holds {login}'s password in clear text"


# ============================================================ the bootstrap
def test_bootstrap_without_a_superuser_runs_twice_with_one_catalog(tmp_path, request):
    m = Managed(request, tmp_path)
    service = m.database("t224_reg")
    first = m.bootstrap(service, "--no-passwords")
    assert first.returncode == 0, f"the first bootstrap, as {ADMIN}, failed:\n{_said(first)}"
    assert m.role(ADMIN)["super"] is False, f"{ADMIN} is a superuser: the case proves nothing"
    catalog = m.catalog("t224_reg")
    second = m.bootstrap(service, "--no-passwords")
    assert second.returncode == 0, f"the second bootstrap failed:\n{_said(second)}"
    states = {state for _what, state in _objects(second.stdout)}
    assert states == {"unchanged"}, f"the second run changed something:\n{_said(second)}"
    assert m.catalog("t224_reg") == catalog, "the second run changed the catalog"
    # A SECURITY DEFINER function owned by a role that cannot log in works:
    # `commit_write`, as a writer login, commits an import entry.
    files = m.logins(service, "e1", dump=False)
    proc = m.commit("t224_reg", "lanes_w_e1", files["lanes_w_e1"],
                    m.entry("t224_reg", "import", "lanes/LANES.md", "# Lanes"))
    assert proc.returncode == 0, f"commit_write as lanes_w_e1 did not commit:\n{_said(proc)}"
    assert m.value(f"SELECT seq FROM {REGISTER}.register_head;", "t224_reg") == "0"


def test_bootstrap_refuses_a_database_its_admin_does_not_own(tmp_path, request):
    m = Managed(request, tmp_path)
    m.psql("CREATE DATABASE t224_theirs;")                  # the provider's, not the admin's
    service = m.service("t224_theirs")
    acl = m.value("SELECT coalesce(datacl, acldefault('d', datdba))::text FROM pg_database "
                  "WHERE datname = 't224_theirs';", "postgres")
    proc = m.bootstrap(service, "--no-passwords")
    assert proc.returncode == 2, f"bootstrap on a database its admin does not own is not 2:\n{_said(proc)}"
    assert m.value(f"SELECT count(*) FROM pg_namespace WHERE nspname = '{REGISTER}';",
                   "t224_theirs") == "0", "the refused bootstrap made the register's schema"
    # THE CONTROL: there, as that admin, the database-level REVOKE and GRANT
    # only warn, 01006 and 01007, and `datacl` is unchanged.
    warned = m.psql("\\set VERBOSITY verbose\nREVOKE ALL ON DATABASE t224_theirs FROM PUBLIC;\n"
                    f"GRANT CONNECT ON DATABASE t224_theirs TO {ADMIN};\n", user=ADMIN)
    assert "01006" in warned.stderr and "01007" in warned.stderr, _said(warned)
    assert m.value("SELECT coalesce(datacl, acldefault('d', datdba))::text FROM pg_database "
                   "WHERE datname = 't224_theirs';", "postgres") == acl


# ============================================================ the login step
def test_login_add_makes_an_engineers_two_logins_with_their_floors_and_prints_their_lines_once(
        tmp_path, request):
    m = Managed(request, tmp_path)
    service = m.database("t224_reg")
    m.bootstrapped(service)
    proc = m.login("add", "e1", service)
    assert proc.returncode == 0, f"login add e1 failed:\n{_said(proc)}"
    lines = _passwords(proc.stdout)
    assert sorted(lines) == ["lanes_r_e1", "lanes_w_e1"], _said(proc)
    for key, login in (("register_url=", "lanes_w_e1"), ("reader_url=", "lanes_r_e1")):
        urls = [line for line in proc.stdout.splitlines() if line.startswith(key)]
        assert len(urls) == 1 and f"//{login}@" in urls[0], f"no one {key} line for {login}"
    files = m.passfiles(proc.stdout)
    for login, half, group in (("lanes_w_e1", "w", WRITER), ("lanes_r_e1", "r", READER)):
        role = m.role(login)
        assert role["canlogin"] and role["groups"] == [group], (login, role)
        assert sorted(role["config"]) == sorted(ROLCONFIG[half]), (login, role["config"])
        assert role["verifier"].startswith("SCRAM-SHA-256$"), f"{login}'s password is not SCRAM"
        assert {k: v for k, v in m.shown(login, "t224_reg", files[login]).items()
                if k in SHOWN[half]} == SHOWN[half]
    _no_clear_text(m.log(), lines)
    # THE DUMP JOB: `lanes_register_dump`, a member of READER alone, with the
    # reader's floors, and its one line.
    dump = m.login("add", DUMP, service)
    assert dump.returncode == 0, f"login add --dump-job failed:\n{_said(dump)}"
    assert sorted(_passwords(dump.stdout)) == [DUMP], _said(dump)
    role = m.role(DUMP)
    assert role["groups"] == [READER] and sorted(role["config"]) == sorted(ROLCONFIG["r"]), role
    _no_clear_text(m.log(), _passwords(dump.stdout))


def test_login_add_run_again_puts_back_a_lost_membership_and_changes_nothing_else(
        tmp_path, request):
    m = Managed(request, tmp_path)
    service = m.database("t224_reg")
    m.bootstrapped(service)
    m.logins(service, "e1", dump=False)
    before = {login: m.role(login) for login in ("lanes_w_e1", "lanes_r_e1")}
    m.psql(f"REVOKE {WRITER} FROM lanes_w_e1 GRANTED BY {ADMIN};")
    assert m.role("lanes_w_e1")["groups"] == [], "the membership was not revoked by hand"
    again = m.login("add", "e1", service)
    assert again.returncode == 0, f"login add e1, run again, failed:\n{_said(again)}"
    assert _passwords(again.stdout) == {}, f"the rerun printed a password line:\n{_said(again)}"
    after = {login: m.role(login) for login in ("lanes_w_e1", "lanes_r_e1")}
    assert after == before, f"the rerun changed more than the membership: {before} -> {after}"


def test_a_member_made_without_the_login_step_carries_no_floor_and_fails_ready_check_12(
        tmp_path, request):
    m = Managed(request, tmp_path)
    service = m.database("t224_reg")
    m.bootstrapped(service)
    files = m.logins(service, "e1", dump=False)
    bare = {}
    for login, group in (("lanes_w_bare", WRITER), ("lanes_r_bare", READER)):
        password = uuid.uuid4().hex
        m.psql(f"CREATE ROLE {login} LOGIN PASSWORD '{password}';\nGRANT {group} TO {login};\n")
        bare[login] = _private(m.home / "passfiles" / login, f"*:*:t224_reg:{login}:{password}\n")
        assert m.shown(login, "t224_reg", bare[login]) == NO_FLOORS, login
    config = m.config("bare", m.socket_url("lanes_w_bare", "t224_reg"), bare["lanes_w_bare"],
                      m.socket_url("lanes_r_e1", "t224_reg"), files["lanes_r_e1"])
    proc = m.ready(config)
    state, reason = _checks(proc.stdout).get(12, ("", ""))
    assert proc.returncode == 2 and state == "FAIL", f"check 12 does not fail:\n{_said(proc)}"
    assert "lanes_w_bare" in reason, f"check 12 does not name the login:\n{_said(proc)}"
    for floor in ROLCONFIG["w"]:
        assert floor.split("=", 1)[0] in reason, f"check 12 does not name {floor}:\n{_said(proc)}"


def test_ready_check_12_passes_the_logins_the_step_made(tmp_path, request):
    m = Managed(request, tmp_path)
    service = m.database("t224_reg")
    m.bootstrapped(service)
    files = m.logins(service, "e1", dump=False)
    config = m.config("e1", m.socket_url("lanes_w_e1", "t224_reg"), files["lanes_w_e1"],
                      m.socket_url("lanes_r_e1", "t224_reg"), files["lanes_r_e1"])
    proc = m.ready(config)
    checks = _checks(proc.stdout)
    state, _reason = checks.get(12, ("", ""))
    assert state == "ok", f"check 12 fails the logins the step made:\n{_said(proc)}"
    # "check 12 passes, `check 12: ok`" (lane 3's batch 7, ruling 1: lane 1's
    # bare line stands, Y-ops:457; tasks:572): the line is bare, with no floor.
    assert re.search(r"^check 12: ok$", proc.stdout, re.M), (
        f"check 12's line is not the bare `check 12: ok`:\n{_said(proc)}")
    # Exit 0 where every check passes. On this socket fixture not every check
    # can (check 11 always fails on a Unix socket, AT-LRMPG's own
    # `[unix-socket]`), so the run's exit follows the other checks: 2, with
    # check 12 not among the failures `ready` names.
    failed = sorted(number for number, (said, _why) in checks.items() if said == "FAIL")
    assert proc.returncode == (2 if failed else 0), (
        f"ready's exit does not follow its checks ({failed} failed):\n{_said(proc)}")
    assert 12 not in failed
    # Check 11 fails on this case's Unix socket by TP:5382-5384's own oracle
    # (`[unix-socket]`), so the exit's 2 arm is always the one exercised
    # (lane 3's batch 11 (3), its optional assertion).
    assert 11 in failed, (
        f"check 11 does not fail on this case's Unix socket, so the exit's 2 arm is not "
        f"exercised:\n{_said(proc)}")


def test_login_rotate_keeps_an_open_session_and_refuses_the_old_password(tmp_path, request):
    m = Managed(request, tmp_path)
    service = m.database("t224_reg")
    m.bootstrapped(service)
    old = m.logins(service, "e1", dump=False)
    held = m.session("lanes_w_e1", "t224_reg", old["lanes_w_e1"])
    assert "ERROR" not in held.send("SELECT 'before';", "t224-before"), "the session did not open"
    proc = m.login("rotate", "e1", service)
    assert proc.returncode == 0, f"login rotate e1 failed:\n{_said(proc)}"
    new = m.passfiles(proc.stdout, "passfiles-new")
    assert sorted(new) == ["lanes_r_e1", "lanes_w_e1"], _said(proc)
    assert "ERROR" not in held.send("SELECT 'after';", "t224-after")
    ended = held.close()
    assert ended.returncode == 0 and ended.stdout.split() == ["before", "after"], (
        f"the session open across the rotation did not go on:\n{_said(ended)}")
    for login in ("lanes_w_e1", "lanes_r_e1"):
        refused = m.as_login(login, "t224_reg", "SELECT 1;\n", old[login])
        assert refused.returncode == 2 and "password authentication failed" in refused.stderr, (
            f"{login}'s old password file is not refused at login:\n{_said(refused)}")
        assert m.connects(login, "t224_reg", new[login]), f"{login}'s new line does not connect"
    _no_clear_text(m.log(), _passwords(proc.stdout))


#: `login`'s refusals: each argv, and whether it runs under the pty.
LOGIN_REFUSALS = {
    "name": [["login", "add", name, "--admin-service", "t224_admin"]
             for name in ("E1", "1e", "e" * 42)],
    "connection-string": [["login", "add", "e1", "--admin-service", value]
                          for value in ("host=/tmp port=5432 dbname=register_db",
                                        "postgresql://lanes_register_admin@127.0.0.1/register_db")],
    "pipe": [["login", "add", "e1", "--admin-service", "t224_admin"]],
}


class LoginBench:
    """FP: the register's fake `psql` first on `PATH`, logging every call, a
    service file naming a loopback admin, and the test's own `$HOME`."""

    def __init__(self, root: Path):
        self.root = root
        fakebin = root / "fakebin"
        fakebin.mkdir(parents=True)
        (fakebin / "psql").write_text(REGISTER_FAKE_PSQL, encoding="utf-8")
        (fakebin / "psql").chmod(0o755)
        self.log = root / "psql.log"
        home = root / "home"
        home.mkdir()
        (root / "t").mkdir()
        _private(home / ".pg_service.conf", f"[t224_admin]\nhost=127.0.0.1\nport=55432\n"
                                            f"user={ADMIN}\ndbname=register_db\n")
        env = guard_strip_env(os.environ, strip=("T224_", "XDG_"))
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(root / "config"),
                   XDG_STATE_HOME=str(root / "state"), TMPDIR=str(root / "t"),
                   LANES_WORKSTATION="Eagle", LANES_NO_GITHUB="1", FAKE_PSQL_LOG=str(self.log),
                   PATH=os.pathsep.join([str(fakebin), os.environ.get("PATH", os.defpath)]))
        self.env = env

    def run(self, argv: list, *, pty_run: bool) -> subprocess.CompletedProcess:
        return _run([sys.executable, str(REPO / "lanes-index"), *argv], self.env, self.root,
                    pty_run=pty_run)

    def requests(self) -> list:
        if not self.log.exists():
            return []
        entries = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()
                   if line]
        return [entry for entry in entries if entry.get("kind") != "version"]


def _making(entries: list) -> list:
    return [entry for entry in entries
            if re.search(r"\b(CREATE|GRANT|ALTER)\b", entry.get("stdin", ""))]


@pytest.mark.parametrize("case", list(LOGIN_REFUSALS))
def test_login_refuses_a_bad_name_a_connection_string_and_a_pipe(tmp_path, case):
    bench = LoginBench(tmp_path)
    for argv in LOGIN_REFUSALS[case]:
        proc = bench.run(argv, pty_run=(case != "pipe"))
        assert proc.returncode == 2, f"[{case}] {argv[1:3]} is not refused with 2:\n{_said(proc)}"
        assert _making(bench.requests()) == [], f"[{case}] the refused login sent a making statement"
        for value in argv:
            if "=" in value or "://" in value:
                assert value not in proc.stdout + proc.stderr, f"[{case}] the refusal echoed {value}"
    # THE CONTROL: a good name, under the pty, gets past every refusal and
    # reaches the admin service (the fake), so each refusal was the case's.
    control = bench.run(["login", "add", "e1", "--admin-service", "t224_admin"], pty_run=True)
    assert bench.requests(), (
        f"[{case}] the control, a good name under a terminal, sent nothing:\n{_said(control)}")


# ============================================================ the revoke
def test_an_open_session_gets_42501_between_the_revokes_steps_then_57p01(tmp_path, request):
    m = Managed(request, tmp_path)
    service = m.database("t224_reg")
    m.bootstrapped(service)
    files = m.logins(service, "e1", "e2", dump=False)
    held = m.session("lanes_w_e2", "t224_reg", files["lanes_w_e2"])
    assert "ERROR" not in held.send("SELECT 1;", "t224-open")
    # [steps-by-hand]: the revoke block's steps 1 and 2, by the admin.
    m.psql(f"ALTER ROLE lanes_w_e2 NOLOGIN;\nREVOKE {WRITER} FROM lanes_w_e2;\n", "t224_reg",
           user=ADMIN)
    write = held.send(f"SELECT {REGISTER}.commit_write(NULL, NULL, NULL, NULL, NULL);",
                      "t224-write")
    read = held.send(f"SELECT seq FROM {REGISTER}.register_head;", "t224-read")
    for what, said in (("write", write), ("read", read)):
        assert "42501" in said and f"permission denied for schema {REGISTER}" in said, (
            f"the open session's {what} between steps 2 and 3 is not 42501: {said}")
    # Step 3 by hand: its sessions ended.
    m.psql("GRANT lanes_w_e2 TO CURRENT_USER WITH INHERIT TRUE, SET FALSE;\n"
           "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'lanes_w_e2';\n"
           "REVOKE lanes_w_e2 FROM CURRENT_USER;\n", "t224_reg", user=ADMIN)
    after = held.send(f"SELECT seq FROM {REGISTER}.register_head;", "t224-after")
    ended = held.close()
    said = after + ended.stderr
    assert "57P01" in said or "terminating connection due to administrator command" in said or \
        "server closed the connection" in said, f"the next statement after step 3 was answered: {said}"
    assert "permission denied" not in after, f"after step 3 a statement got 42501, not 57P01: {after}"
    assert m.connects("lanes_w_e1", "t224_reg", files["lanes_w_e1"]), "e1 can no longer log in"


# ============================================================ the dump
def test_the_reader_login_dumps_both_schemas_and_still_cannot_write(tmp_path, request):
    m = Managed(request, tmp_path)
    service = m.database("t224_reg")
    m.bootstrapped(service)
    files = m.logins(service, "e1")
    proc = m.commit("t224_reg", "lanes_w_e1", files["lanes_w_e1"],
                    m.entry("t224_reg", "import", "lanes/LANES.md", "# Lanes"))
    assert proc.returncode == 0, _said(proc)
    # The indexer's store, made as the indexer (`lanes-index`'s own #160
    # scripts are not run here: see the report), with a row.
    m.psql(f"SET ROLE {INDEXER};\nCREATE TABLE {INDEX}.t224_rows (id int PRIMARY KEY);\n"
           f"INSERT INTO {INDEX}.t224_rows VALUES (1);\n", "t224_reg")
    dumped, target = m.dump("t224_reg", files[DUMP], "first.dump")
    assert dumped.returncode == 0, f"the dump job's dump failed:\n{_said(dumped)}"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600, "the dump file is not 0600"
    listing = subprocess.run([m.cluster.tool("pg_restore"), "--list", str(target)],
                             capture_output=True, text=True, timeout=120, check=False).stdout
    for name in m.value("SELECT string_agg(schemaname || ' ' || tablename, ',') FROM pg_tables "
                        f"WHERE schemaname IN ('{REGISTER}', '{INDEX}');", "t224_reg").split(","):
        schema, table = name.split()
        assert re.search(rf"TABLE {schema} {table}\b", listing), f"the dump lacks {name}"
    head = subprocess.run([m.cluster.tool("pg_restore"), "--data-only", f"--schema={REGISTER}",
                           "--table=register_head", "--file=-", str(target)],
                          capture_output=True, text=True, timeout=120, check=False).stdout
    b = m.value(f"SELECT seq FROM {REGISTER}.register_head;", "t224_reg")
    assert re.search(rf"^1\t{b}\b", head, re.M) or re.search(rf"\t{b}\b", head), (
        f"the dump's register_head does not give the head {b}:\n{head}")
    # M6: a sequence the indexer makes later is dumped, by the default privilege.
    m.psql(f"SET ROLE {INDEXER};\nCREATE SEQUENCE {INDEX}.t224_seq_ok;\n", "t224_reg")
    again, _ = m.dump("t224_reg", files[DUMP], "second.dump")
    assert again.returncode == 0, f"a later sequence stopped the dump:\n{_said(again)}"
    # THE CONTROLS: the default privilege revoked before a sequence is made,
    # and the reader's SELECT on doc_lines' sequence revoked.
    m.psql(f"ALTER DEFAULT PRIVILEGES FOR ROLE {INDEXER} IN SCHEMA {INDEX} "
           f"REVOKE SELECT ON SEQUENCES FROM {READER};\n", "t224_reg", user=ADMIN)
    m.psql(f"SET ROLE {INDEXER};\nCREATE SEQUENCE {INDEX}.t224_seq_hidden;\n", "t224_reg")
    hidden, _ = m.dump("t224_reg", files[DUMP], "third.dump")
    assert hidden.returncode != 0 and "t224_seq_hidden" in hidden.stderr, _said(hidden)
    m.psql(f"SET ROLE {INDEXER};\nDROP SEQUENCE {INDEX}.t224_seq_hidden;\n", "t224_reg")
    m.psql(f"SET ROLE {OWNER};\nREVOKE SELECT ON {REGISTER}.doc_lines_line_id_seq FROM {READER};\n",
           "t224_reg")
    seq, _ = m.dump("t224_reg", files[DUMP], "fourth.dump")
    assert seq.returncode != 0 and "doc_lines_line_id_seq" in seq.stderr, _said(seq)
    # STILL CANNOT WRITE: each refused inside BEGIN READ WRITE, then ROLLBACK.
    tries = [f"SELECT nextval('{REGISTER}.doc_lines_line_id_seq')",
             f"UPDATE {REGISTER}.register_head SET seq = seq",
             f"SELECT nextval('{INDEX}.t224_seq_ok')", f"SELECT setval('{INDEX}.t224_seq_ok', 5)",
             f"INSERT INTO {INDEX}.t224_rows VALUES (2)", f"UPDATE {INDEX}.t224_rows SET id = id",
             f"DELETE FROM {INDEX}.t224_rows", f"TRUNCATE {INDEX}.t224_rows"]
    for statement in tries:
        tried = m.as_login(DUMP, "t224_reg", f"BEGIN READ WRITE;\n{statement};\nROLLBACK;\n",
                           files[DUMP])
        assert tried.returncode != 0 and "42501" in tried.stderr, (
            f"the dump login's {statement!r} was not refused with 42501:\n{_said(tried)}")


# ============================================================ the restores
def _source(request, root: Path, *, primary: bool):
    """A bootstrapped register with rows: e1's logins and the dump job's, an
    import, and, where `primary`, the cutover and the marker; and its dump,
    by O2's command."""
    m = Managed(request, root)
    service = m.database("t224_reg")
    m.bootstrapped(service)
    files = m.logins(service, "e1")
    if primary:
        m.to_primary("t224_reg", "lanes_w_e1", files["lanes_w_e1"])
    else:
        proc = m.commit("t224_reg", "lanes_w_e1", files["lanes_w_e1"],
                        m.entry("t224_reg", "import", "lanes/LANES.md", "# Lanes"))
        assert proc.returncode == 0, _said(proc)
    dumped, target = m.dump("t224_reg", files[DUMP], "source.dump")
    assert dumped.returncode == 0, f"the source's dump failed:\n{_said(dumped)}"
    return m, files, target


def _restored(request, root: Path, source_dump: Path):
    """R-P41's order on a new cluster with the admin role: the database
    created first by the admin; then, through one service naming it,
    `bootstrap --roles-only`, `login add e1` and `login add --dump-job`, the
    restore, and `bootstrap`. Returns the target, its runs and its files."""
    target = Managed(request, root, cluster=_another_cluster(request))
    service = target.database("t224_reg")
    roles = target.bootstrap(service, "--roles-only", pty_run=True)
    assert roles.returncode == 0, f"bootstrap --roles-only failed:\n{_said(roles)}"
    files = target.logins(service, "e1", folder="passfiles-new")
    env = {k: v for k, v in target.env.items() if not k.startswith("PG")}
    env["PGSERVICE"] = service
    restore = subprocess.run([target.cluster.tool("pg_restore"), "--exit-on-error", "--no-password",
                              "--dbname=t224_reg", str(source_dump)],
                             capture_output=True, text=True, timeout=300, env=env, check=False)
    assert restore.returncode == 0, f"pg_restore through the admin service failed:\n{_said(restore)}"
    mark = len(target.log())
    after = target.bootstrap(service, pty_run=True)
    assert after.returncode == 0, f"bootstrap after the restore failed:\n{_said(after)}"
    return target, roles, after, files, mark


def test_a_restore_from_the_dump_equals_its_source_with_new_passwords(tmp_path, request):
    source, old, dump = _source(request, tmp_path / "source", primary=False)
    target, roles, after, new, _mark = _restored(request, tmp_path / "target", dump)
    # `--roles-only` prints the indexer's line, and `created` for each of the
    # three database-level statements (option (a)).
    assert sorted(_passwords(roles.stdout)) == [INDEXER], _said(roles)
    objects = dict(_objects(roles.stdout))
    for words in DB_LEVEL:
        assert [state for what, state in objects.items() if words in what] == ["created"], (
            f"--roles-only does not print `created` for {words}:\n{_said(roles)}")
    assert {state for _what, state in _objects(after.stdout)} == {"unchanged"}, _said(after)
    assert target.catalog("t224_reg") == source.catalog("t224_reg"), "the catalogs differ"
    assert target.rows("t224_reg") == source.rows("t224_reg"), "the rows differ"
    for login in ("lanes_w_e1", "lanes_r_e1", DUMP):
        assert not target.connects(login, "t224_reg", old[login]), (
            f"the source's password file for {login} connects to the restore")
        assert target.connects(login, "t224_reg", new[login]), f"{login}'s printed line does not connect"
    _no_clear_text(target.log(), {**_passwords(roles.stdout), **{
        login: path.read_text(encoding="utf-8").strip() for login, path in new.items()}})


def test_a_restore_from_the_providers_copy_keeps_the_roles_and_takes_new_passwords(
        tmp_path, request):
    source, old, _dump = _source(request, tmp_path / "source", primary=False)
    logins = ("lanes_w_e1", "lanes_r_e1", DUMP)
    before = {login: source.role(login) for login in logins}
    source.cluster.stop()
    copy = Managed(request, tmp_path / "copy",
                   cluster=_another_cluster(request, data_from=source.cluster.root / "data"),
                   scram=False)
    for login in logins:
        assert copy.role(login) == before[login], f"{login} differs on the provider's copy"
        assert copy.connects(login, "t224_reg", old[login]), f"{login}'s old file does not connect"
    service = copy.service("t224_reg")
    roles = copy.bootstrap(service, "--roles-only", pty_run=True)
    assert roles.returncode == 0, f"bootstrap --roles-only failed:\n{_said(roles)}"
    assert {state for _what, state in _objects(roles.stdout)} == {"unchanged"}, _said(roles)
    assert _passwords(roles.stdout) == {}, f"--roles-only printed a password line:\n{_said(roles)}"
    new: dict = {}
    for who in ("e1", DUMP):
        proc = copy.login("rotate", who, service)
        assert proc.returncode == 0, f"login rotate {who} failed:\n{_said(proc)}"
        new.update(copy.passfiles(proc.stdout, "passfiles-new"))
        _no_clear_text(copy.log(), _passwords(proc.stdout))
    assert sorted(new) == sorted(logins)
    for login in logins:
        assert not copy.connects(login, "t224_reg", old[login]), f"{login}'s old file still connects"
        assert copy.connects(login, "t224_reg", new[login]), f"{login}'s new line does not connect"


# ============================================================ check 11
class TlsEnvironment:
    """Check 11's environment on section 5.6's TLS cluster, T229's
    `tls_cluster`, which `tests/pgcluster.py` gives since this line merged
    line FX at T229d. Each id skips with T205's banner where `pg_engine`
    finds none.

    LINE FX'S PLANNED NAMES (the coordinator, 16:50Z), NOT A CONTRACT: a
    `TLSCluster` with `root_cert`, `database_name`, `url(user)`,
    `client_env(user)`, `configuration(directory, database=None,
    mode="index")` and `second_database(label)`. This module uses
    `configuration(directory)`, a 0600 `lanes-index.conf` naming the
    fixture's logins (T228's `lanes_w_fx` and `lanes_r_fx`) on loopback TCP
    with `sslmode=verify-full` and `sslrootcert=` the root alone, and
    `root_cert`. READ FROM F12B'S T229 TEXT, and not in that list: it is a
    `pgcluster.Cluster` (`root`, `bindir`, `stop`, `start_again`), its Unix
    socket at `root`; and its two start options are
    `start_again(leaf_only=True)`, the leaf served without the intermediate
    (T230's `[leaf-only]`), and `start_again(standby=True)`, T229d's, which
    writes `standby.signal`, polls for `ready` as every start does, and
    fails the start unless `pg_is_in_recovery()` is true (the test plan's
    `[in-recovery]`; lane 3's batch 11 (1))."""

    NEEDS = ("configuration", "root_cert", "root", "bindir", "stop", "start_again")

    def __init__(self, request, root: Path):
        request.getfixturevalue("pg_engine")
        import pgcluster
        assert getattr(pgcluster, "tls_cluster", None) is not None, (
            "check 11 needs section 5.6's TLS cluster, T229's, since it always fails on a Unix "
            "socket; tests/pgcluster.py has no tls_cluster yet")
        self.tls = request.getfixturevalue("tls_cluster")
        missing = [name for name in self.NEEDS if not hasattr(self.tls, name)]
        assert not missing, f"T229's tls_cluster has no {', '.join(missing)}"
        self.root = root
        made = Path(self.tls.configuration(root / "conf"))
        self.base = made / "lanes-index.conf" if made.is_dir() else made
        self.lines = self.base.read_text(encoding="utf-8").splitlines()
        self.register_url = next(line.split("=", 1)[1] for line in self.lines
                                 if line.startswith("register_url="))
        self.login = self.register_url.split("//", 1)[1].split("@", 1)[0]
        (root / "home").mkdir(exist_ok=True)
        (root / "t").mkdir(exist_ok=True)
        env = guard_strip_env(os.environ, strip=("T224_", "XDG_"))
        env.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"),
                   XDG_STATE_HOME=str(root / "state"), TMPDIR=str(root / "t"),
                   LANES_WORKSTATION="Eagle", LANES_NO_GITHUB="1", LC_ALL="C",
                   PATH=os.pathsep.join([str(self.tls.bindir), os.environ.get("PATH", os.defpath)]))
        self.env = env

    def url(self, **query: str | None) -> str:
        """The configuration's `register_url=`, with `query`'s parameters set,
        or dropped where None."""
        head, _, tail = self.register_url.partition("?")
        params = dict(piece.split("=", 1) for piece in tail.split("&") if "=" in piece)
        params.update(query)
        tail = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        return head + (f"?{tail}" if tail else "")

    def socket_url(self) -> str:
        """The same URL at the cluster's own Unix socket."""
        head, _, tail = self.register_url.partition("?")
        _scheme, _, rest = head.partition("//")
        port = rest.split("@", 1)[1].split("/", 1)[0].rsplit(":", 1)[1]
        database = rest.split("/", 1)[1]
        return (f"postgresql://{self.login}@{quote(str(self.tls.root), safe='')}:{port}/{database}"
                + (f"?{tail}" if tail else ""))

    def ready(self, register_url: str) -> subprocess.CompletedProcess:
        config = _private(self.root / f"c{uuid.uuid4().hex[:8]}" / "lanes-index.conf", "\n".join(
            [f"register_url={register_url}" if line.startswith("register_url=") else line
             for line in self.lines]) + "\n")
        env = dict(self.env, LANES_INDEX_CONFIG=str(config))
        return _run([sys.executable, str(REPO / "lanes-index"), "ready", "--expect", "index",
                     "--release", "0.0.0-t224", "--env", "t224"], env, self.root, pty_run=False)

    def restart(self, **option: bool) -> None:
        """Stop the TLS cluster and start it again with T229's start option,
        `leaf_only=` (T230's `[leaf-only]`) or `standby=True`
        (`[in-recovery]`). The option is only passed on: T229d's
        `start_again(standby=True)` writes `standby.signal` and proves the
        recovery itself (lane 3's batch 7, ruling 2, and batch 11 (1))."""
        self.tls.stop()
        self.tls.start_again(**option)


#: Check 11's ids: what each does to the environment, and whether it passes.
CHECK_11 = {
    "passes": (lambda env: env.url(), True),
    "sslmode-prefer": (lambda env: env.url(sslmode="prefer"), False),
    "no-sslrootcert": (lambda env: env.url(sslrootcert=None), False),
    "unix-socket": (lambda env: env.socket_url(), False),
    "in-recovery": (lambda env: (env.restart(standby=True), env.url())[1], False),
    # T230 (R2's S3; X's TLS rules and FR-011's server half, R09). Each meets
    # the TLS cluster at a loopback host, so T104's refusal at load lets its
    # URL load and check 11 meets it.
    "leaf-only": (lambda env: (env.restart(leaf_only=True), env.url())[1], False),
    "system-root": (lambda env: env.url(sslrootcert="system"), False),
    "plaintext": (lambda env: env.url(sslmode="disable", sslrootcert=None), False),
}


@pytest.mark.parametrize("case", list(CHECK_11))
def test_ready_check_11_needs_tls_and_the_primary(tmp_path, request, case):
    env = TlsEnvironment(request, tmp_path)
    make, passes = CHECK_11[case]
    proc = env.ready(make(env))
    state, reason = _checks(proc.stdout).get(11, ("", ""))
    if passes:
        assert state == "ok", f"[{case}] check 11 does not pass:\n{_said(proc)}"
    else:
        assert state == "FAIL" and proc.returncode == 2, (
            f"[{case}] check 11 does not fail, or ready does not exit 2:\n{_said(proc)}")
        assert env.login in reason, f"[{case}] check 11 does not name the connection:\n{_said(proc)}"


# ============================================================ tls_at_load
#
# T230, lane 1's `tls_at_load` (L1-1; T104; CLI4.5 section 2.5): each item
# through `lanes-index mode`, with `mode=index` in the file, so Q6(c) never
# answers. FP: nothing connects. A refused file is 2 from `mode`, naming the
# key and what is missing and printing no URL; 3 from `journal --write-id`
# (CO-3); and 1 under `register read --for guard`'s prefetch, form 2 (O14).
# That read's `--pid` is a stand-in for the hook started just before it
# (`hook_pid`), so the 1 is the refused file's and never the hook's age.

#: A TCP host that is not loopback, and the loopback stand-ins.
REMOTE = "db.t230.invalid"
LOOPBACK = "127.0.0.1"


def _tls_url(login: str, host: str, query: str = "") -> str:
    return f"postgresql://{login}@{host}:5432/register_db" + (f"?{query}" if query else "")


def _tls_files(root: Path) -> dict:
    """Each item's configuration lines, and what it expects: `index` (it
    loads), or the key its refusal names and the words of what is missing."""
    rootfile = _private(root / "ca" / "root.crt", "not a certificate: only its existence counts\n")
    socket = quote("/tmp/t230-socket", safe="")
    reader = f"reader_url={_tls_url('lanes_r_t230', LOOPBACK)}"
    return {
        "no-sslmode": ([f"register_url={_tls_url('lanes_w_t230', REMOTE)}", reader],
                       ("register_url=", "sslmode")),
        "system-root": ([f"register_url={_tls_url('lanes_w_t230', REMOTE, 'sslmode=verify-full&sslrootcert=system')}",
                         reader], ("register_url=", "system")),
        "missing-root": ([f"register_url={_tls_url('lanes_w_t230', REMOTE, 'sslmode=verify-full&sslrootcert=' + str(root / 'ca' / 'absent.crt'))}",
                          reader], ("register_url=", "sslrootcert")),
        "root-file": ([f"register_url={_tls_url('lanes_w_t230', REMOTE, 'sslmode=verify-full&sslrootcert=' + str(rootfile))}",
                       reader], "index"),
        "socket": ([f"register_url={_tls_url('lanes_w_t230', socket)}", reader], "index"),
        "loopback": ([f"register_url={_tls_url('lanes_w_t230', LOOPBACK)}", reader], "index"),
        "no-register-url": ([f"url={_tls_url('lanes_writer', REMOTE)}",
                             f"reader_url={_tls_url('lanes_reader', REMOTE)}"], "index"),
        "reader-url": ([f"register_url={_tls_url('lanes_w_t230', LOOPBACK)}",
                        f"reader_url={_tls_url('lanes_r_t230', REMOTE)}"], ("reader_url=", "sslmode")),
        "two-hosts": ([f"register_url=postgresql://lanes_w_t230@{LOOPBACK}:5432,{REMOTE}:5432/register_db",
                       reader], ("register_url=", "sslmode")),
    }


@contextlib.contextmanager
def hook_pid():
    """THE HOOK'S `$$`, FOR A GUARD READ'S `--pid` (contract section 3.6:
    "`--pid <pid>` ... is the hook's own pid, `$$`, in forms 2 and 4", and
    "the client reads `T0` from it"). It yields the pid of a stand-in for the
    hook, a `sleep` started just before the read, as a hook's own start is,
    and stops it after the read. T507 cuts a guard read at `T0` + 3.75 s
    from that start, and an age at or above the cut exits 2, "too late to
    verify" (section 3.6's 2; `register_guard_t0`). The pytest process's own
    pid is minutes old on a runner, and with it the measure module's `[m10]`
    ended 2 (lane 1's round 6b census, #165 6827592167, item 2). Here
    `[for-guard]`'s file is refused at load, which merge27's client answers
    1 before it checks the age, so the old pid did not change that case's
    exit there; the stand-in makes its read the hook's, as the contract
    says, whatever order a client checks in. It is AT-F7's stand-in,
    `test_sql_register_outage.py`'s `_stand_in`, at an age of 0, as the
    measure and readers modules' `hook_pid` are."""
    standin = subprocess.Popen(["sleep", "120"], start_new_session=True,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    try:
        yield str(standin.pid)
    finally:
        standin.kill()
        standin.wait()


#: The items, and the two that read the refused file through another verb.
TLS_AT_LOAD = ["no-sslmode", "system-root", "missing-root", "root-file", "socket", "loopback",
               "no-register-url", "reader-url", "two-hosts", "journal-write-id", "for-guard"]


@pytest.mark.parametrize("item", TLS_AT_LOAD)
def test_tls_at_load_refuses_a_url_off_loopback_without_verify_full_and_a_root_file(tmp_path, item):
    bench = LoginBench(tmp_path)
    files = _tls_files(tmp_path)
    lines, expect = files["no-sslmode" if item in ("journal-write-id", "for-guard") else item]
    config = _private(tmp_path / "conf" / "lanes-index.conf", "\n".join(["mode=index", *lines, ""]))
    bench.env["LANES_INDEX_CONFIG"] = str(config)
    urls = [line.split("=", 1)[1] for line in lines]
    if item == "journal-write-id":
        proc = bench.run(["journal", "--write-id", str(uuid.uuid4()), "--not-after", "2000000000",
                          "--generation", str(uuid.uuid4()), "--lane", "t230", "--verb", "append-line",
                          "--args-sha256", "0" * 64], pty_run=False)
        assert proc.returncode == 3, f"[{item}] journal --write-id on a refused file is not 3:\n{_said(proc)}"
    elif item == "for-guard":
        repo = tmp_path / "repo"
        repo.mkdir()
        with hook_pid() as pid:
            proc = bench.run(["register", "read", "--for", "guard", "--prefetch", "--cache",
                              str(tmp_path / "cache"), "--pid", pid, "--repo", str(repo)],
                             pty_run=False)
        assert proc.returncode == 1, (
            f"[{item}] register read --for guard --prefetch on a refused file is not 1:\n{_said(proc)}")
    else:
        proc = bench.run(["mode"], pty_run=False)
        if expect == "index":
            assert (proc.returncode, proc.stdout) == (0, "index\n"), f"[{item}] does not load:\n{_said(proc)}"
        else:
            key, missing = expect
            assert proc.returncode == 2 and proc.stdout == "", f"[{item}] is not refused with 2:\n{_said(proc)}"
            assert key in proc.stderr and missing in proc.stderr, (
                f"[{item}] the refusal does not name {key} and {missing}:\n{_said(proc)}")
    for url in urls:
        if expect != "index" or item in ("journal-write-id", "for-guard"):
            assert url not in proc.stdout + proc.stderr, f"[{item}] the refusal printed a URL"
    assert bench.requests() == [], f"[{item}] a request was sent: nothing connects at load"


# ============================================================ lane 1's two
def test_dump_restore_privileges_hold_after_roles_only_the_restore_and_bootstrap(
        tmp_path, request):
    source, _old, dump = _source(request, tmp_path / "source", primary=True)
    label = source.value(f"SELECT database_label FROM {REGISTER}.register_switch;", "t224_reg")
    target, _roles, after, _new, mark = _restored(request, tmp_path / "target", dump)
    end = len(target.log())
    db = "t224_reg"
    acl = target.value(f"SELECT coalesce(datacl::text, '') FROM pg_database WHERE datname = '{db}';",
                       "postgres")
    assert not re.search(r"(^|[{,])=[A-Za-z]*c", acl), f"PUBLIC holds CONNECT on {db}: {acl}"
    target.psql("CREATE ROLE t224_outsider LOGIN PASSWORD 'outside-t224';")
    outsider = _private(target.home / "passfiles" / "t224_outsider", f"*:*:{db}:t224_outsider:outside-t224\n")
    refused = target.as_login("t224_outsider", db, "SELECT 1;\n", outsider)
    assert refused.returncode == 2 and "permission denied for database" in refused.stderr, _said(refused)
    for role in (WRITER, READER, INDEXER):
        assert target.value(f"SELECT has_database_privilege('{role}', '{db}', 'CONNECT');",
                            "postgres") == "t", f"{role} holds no CONNECT on {db}"
    target.psql(f"SET ROLE {OWNER};\nCREATE FUNCTION {REGISTER}.t224_later() RETURNS int "
                "LANGUAGE sql AS 'SELECT 1';\n", db)
    assert target.value(f"SELECT has_function_privilege('t224_outsider', '{REGISTER}.t224_later()', "
                        "'EXECUTE');", db) == "f", "an outsider may execute a later function of the owner's"
    # `bootstrap` after the restore re-ran no statement and wrote no label.
    assert {state for _what, state in _objects(after.stdout)} == {"unchanged"}, _said(after)
    since = target.log()[mark:end]
    ran = [line for line in since.splitlines()
           if re.search(r"statement: (CREATE|GRANT|REVOKE|ALTER|INSERT|UPDATE)\b", line)]
    assert ran == [], f"bootstrap after the restore re-ran statements: {ran}"
    assert target.value(f"SELECT database_label FROM {REGISTER}.register_switch;", db) == label


def test_rotate_dump_job_changes_only_the_dump_logins_password(tmp_path, request):
    m = Managed(request, tmp_path)
    service = m.database("t224_reg")
    m.bootstrapped(service)
    old = m.logins(service, "e1")
    verifiers = {login: m.role(login)["verifier"] for login in ("lanes_w_e1", "lanes_r_e1", DUMP)}
    # Off a terminal it refuses with 2 and changes nothing.
    piped = m.login("rotate", DUMP, service, pty_run=False)
    assert piped.returncode == 2, f"rotate --dump-job through a pipe is not 2:\n{_said(piped)}"
    assert m.role(DUMP)["verifier"] == verifiers[DUMP], "the refused rotation changed the verifier"
    # Neither an engineer nor --dump-job, or both: 64.
    for argv in (["login", "rotate", "--admin-service", service],
                 ["login", "rotate", "e1", "--dump-job", "--admin-service", service]):
        usage = m.lanes(*argv, pty_run=True)
        assert usage.returncode == 64, f"{argv[1:]} is not usage, 64:\n{_said(usage)}"
    proc = m.login("rotate", DUMP, service)
    assert proc.returncode == 0, f"login rotate --dump-job failed:\n{_said(proc)}"
    lines = _passwords(proc.stdout)
    assert sorted(lines) == [DUMP], f"not one line, the dump login's:\n{_said(proc)}"
    new = m.passfiles(proc.stdout, "passfiles-new")
    assert m.role(DUMP)["verifier"] != verifiers[DUMP], "the dump login's verifier did not change"
    for login in ("lanes_w_e1", "lanes_r_e1"):
        assert m.role(login)["verifier"] == verifiers[login], f"{login}'s verifier changed"
    assert not m.connects(DUMP, "t224_reg", old[DUMP]), "the old dump password still logs in"
    dumped, _target = m.dump("t224_reg", new[DUMP], "rotated.dump")
    assert dumped.returncode == 0, f"the new dump password does not dump:\n{_said(dumped)}"
    _no_clear_text(m.log(), lines)


# ============================================================ phase W (T258)
#
# AT-LRMPG'S PHASE W (T258; the test plan's "Phase and kind": the logins'
# writes and reads, which run through the flipped test copy of `lanes-index`,
# test 14's second state, are W). Each case runs on a managed PostgreSQL of
# its own, as phase N's do (`Managed`): the admin's database, the bootstrap,
# and `login add` for the case's engineers, whose printed lines go into 0600
# password files. `PhaseW` then brings the register to `primary` by AT-LR006's
# route (TP:4610-4615), as e1's writer login: an `import` entry of the render
# set at a bare origin's `main`, a `cutover` entry naming `lanes/STORE`, and
# `record_marker`. Each engineer gets a checkout of that origin, a protocol
# root naming it, and a `mode=primary` `lanes-index.conf` whose
# `register_url=` and `reader_url=` name that engineer's own two logins on
# the cluster's socket, each with its own password file (section 1.4, "One
# engineer's file").
#
# A WRITE is `lanes-edit.sh log NOTED lane:<lane> <text>`, a READ is
# `lanes-edit.sh binding <lane>` (S3's table), each from the flipped copy,
# with `lanes-edit.sh` beside it (CLI4.5 section 6's copy rule), as T241's
# and T243's writers run; this module builds the workstation itself, since
# neither of their modules is on this branch. Each run puts T203's shim first
# on `PATH`, in a directory of its own, so the shim's log is that run's calls,
# and the mid-commit case arms its `hold` there. The two writer logins' log
# lines are the server's own: `log_connections` and `log_statement=all`, each
# line prefixed with its backend's pid (`Managed`).
#
# Rotate's write half is the fifth case (lane 3's batch 7, lane 2's item (3);
# TP:5317-5318): with the old password file, e1's write exits 69 at its
# snapshot and the journal gains nothing; with the new lines it commits once.
# T224's rotate case keeps the connection half.
#
# They FAIL UNTIL lane 1's T110 (L1-A8, `lanes-index login`) and lane 4's
# writer on primary land, its attempt loop (L4-B3) and its in-doubt rule and
# pending record (L4-B5): merge10's `lanes-edit.sh` has no primary branch and
# writes the files whatever `mode=` says, so each write case fails at its
# own assertion. `target_session_attrs` (M5) is `psql`'s alone and needs only
# L1-A8. Without PostgreSQL 16 each skips with T205's banner.

W_DB = "t224_reg"
#: Phase W's lanes, one per engineer, and their sessions.
W_LANES = {"e1": "repoE-1", "e2": "repoE-2"}
W_SESSIONS = {"e1": "eeeeeeee-0258-4000-8000-00000000e001",
              "e2": "eeeeeeee-0258-4000-8000-00000000e002"}
W_WS = "Eagle"
#: The register's punctuation, spelled by code point, as the render module
#: spells it: the em dash, the middle dot of a state cell, the arrow.
EM, DOT, ARROW = chr(0x2014), chr(0x00B7), chr(0x2192)
STORE_PATH = "lanes/STORE"
UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
#: The pending records (L4-B5): `<state>/openRepoTools/register-pending/<d>`,
#: as T245 reads them.
PENDING = Path("openRepoTools") / "register-pending"
#: Everything a write that wrote nothing leaves as it was (T243's form).
W_STATE_SQL = f"""
SELECT md5(concat_ws('|',
  (SELECT seq::text FROM {REGISTER}.register_head),
  (SELECT string_agg(j::text, ',' ORDER BY j.seq) FROM {REGISTER}.journal j),
  (SELECT string_agg(e::text, ',' ORDER BY e.seq, e.ord) FROM {REGISTER}.journal_edits e),
  (SELECT string_agg(f::text, ',' ORDER BY f.path) FROM {REGISTER}.files f),
  (SELECT string_agg(d::text, ',' ORDER BY d.line_id) FROM {REGISTER}.doc_lines d),
  (SELECT string_agg(s::text, ',') FROM {REGISTER}.register_switch s)));
"""
#: A server log line under `log_line_prefix = '%p '`: the pid, the level and
#: the message. A line without the prefix continues the one before it.
LOG_LINE = re.compile(r"^([0-9]+) ([A-Z]+):  (.*)$")
AUTHORIZED = re.compile(r"connection authorized: user=(\S+)")


def _w_row(lane: str, sid: str) -> str:
    return (f"| `{lane}` | harness `{sid}` | {W_WS} / test / brett | 2026-10-01T00:00Z | none "
            f"| handoffs/{lane}.md | LIVE {DOT} 2026-10-01T01:00:00Z {DOT} working |")


def _w_seed() -> dict:
    """Phase W's register at C: a row and a log for each engineer's lane, an
    empty aliases table; `lanes/repos.tsv` and `lanes/log/README.md`, which
    the checkout gives and the register does not hold."""
    files = {
        "lanes/LANES.md": "\n".join([
            f"# LANES.md {EM} AT-LRMPG's phase W register (T258)", "",
            "| lane | session id | workstation / env / user | started (UTC) | objects owned "
            "| handoff path | state |",
            "|---|---|---|---|---|---|---|",
            *(_w_row(W_LANES[who], W_SESSIONS[who]) for who in W_LANES), ""]),
        "lanes/aliases.tsv": "# old\tnew\tutc\n",
        "lanes/log/README.md": "# the object logs\n",
        "lanes/repos.tsv": "# alias\towner/repo\nrepoE\topensoft/repoE\n",
    }
    for who, lane in W_LANES.items():
        files[f"lanes/log/{lane}.md"] = "\n".join([
            f"# lane {lane} {EM} object log (lane-collision-protocol Amendment 7)",
            f"STARTED {EM} lane {lane}, session {W_SESSIONS[who]}@{W_WS}, 2026-10-01T00:00:00Z, "
            f"lane:{lane} {ARROW} home opensoft/repoE; dir /work/{lane}", ""])
    return files


def _w_creates(files: dict) -> tuple:
    """Each of `files` ({path: text}) created, then its lines appended, and
    its `files` row with its digest as it renders (AT-LR006's first step)."""
    edits: list = []
    rows: list = []
    for path in sorted(files):
        edits.append({"ord": len(edits) + 1, "op": "create", "path": path})
        for text in files[path].rstrip("\n").split("\n"):
            edits.append({"ord": len(edits) + 1, "op": "append", "path": path, "new_text": text})
        rows.append({"path": path, "present": True, "final_newline": True,
                     "sha256": _sha256(files[path].encode("utf-8"))})
    return edits, rows


def _w_git(cwd: Path, env: dict, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env=env,
                          timeout=120, check=False)
    assert proc.returncode == 0, f"git {' '.join(args)} in {cwd}: {proc.stderr}{proc.stdout}"
    return proc.stdout


#: `_masked_path`'s mirrors, by each directory's real path (None where the
#: directory holds no masked name), and the one temporary root they share.
_PATH_MIRRORS: dict = {}
_PATH_MIRROR_ROOT: list = []


def _masked_path() -> str:
    """The caller's PATH with every directory kept in its place, and each one
    that holds a `psql`, a `lanes-index` or a name that starts `pg_` swapped
    for a private mirror of it: a directory of links, one to each of its
    entries by its absolute path, those names left out. Neither an installed
    indexer nor a `psql` (or a `pg_` client wrapper shipped beside it) behind
    the shim's back is what a case runs, but the tools beside them are: on a
    GitHub runner `postgresql-16`'s client puts `psql` in `/usr/bin` with
    `git` and `bash` (and `/bin` is a link to it), so dropping the directory
    dropped `git` and `bash` too (lane 1's census, #165 6807454856). A
    directory that holds none of those names passes through unchanged. Each
    mirror is made once per process, under one `mkdtemp` that an `atexit`
    handler removes."""
    parts = []
    for part in os.environ.get("PATH", os.defpath).split(os.pathsep):
        if not part:
            continue
        real = os.path.realpath(part)
        if real not in _PATH_MIRRORS:
            try:
                names = os.listdir(real)
            except OSError:
                names = []
            masked = {name for name in names
                      if name in ("psql", "lanes-index") or name.startswith("pg_")}
            mirror = None
            if masked:
                if not _PATH_MIRROR_ROOT:
                    _PATH_MIRROR_ROOT.append(tempfile.mkdtemp(prefix="l2-pathmask-"))
                    atexit.register(shutil.rmtree, _PATH_MIRROR_ROOT[0], ignore_errors=True)
                mirror = os.path.join(_PATH_MIRROR_ROOT[0], str(len(_PATH_MIRRORS)))
                os.mkdir(mirror)
                for name in names:
                    if name not in masked:
                        os.symlink(os.path.join(real, name), os.path.join(mirror, name))
            _PATH_MIRRORS[real] = mirror
        parts.append(_PATH_MIRRORS[real] or part)
    return os.pathsep.join(parts)


def _commit_logins(log: str) -> list:
    """The login of each `commit_write` call in `log`: each statement line,
    or a line continuing one, that carries `commit_write(`, tied by its
    backend's pid to that backend's `connection authorized` line."""
    users: dict = {}
    found: list = []
    pid, in_statement = None, False
    for line in log.splitlines():
        m = LOG_LINE.match(line)
        if m:
            pid, level, said = m.groups()
            in_statement = level == "LOG" and said.startswith("statement:")
            authorized = AUTHORIZED.match(said)
            if authorized:
                users[pid] = authorized.group(1)
        else:
            said = line
        if in_statement and "commit_write(" in said:
            found.append(users.get(pid, f"no connection authorized line for pid {pid}"))
            in_statement = False
    return found


class W258Writer:
    """One `lanes-edit.sh` run, its shim's directory and its outcome."""

    def __init__(self, who: str, proc: subprocess.Popen, psql_dir: Path, state: Path):
        self.who, self.proc, self.psql_dir, self.state = who, proc, psql_dir, state
        self.ended = None
        self.out = self.err = ""
        self._thread = threading.Thread(target=self._wait, daemon=True)
        self._thread.start()

    def _wait(self) -> None:
        self.out, self.err = self.proc.communicate()
        self.ended = time.monotonic()

    def wait(self, timeout: float = 150) -> int:
        self._thread.join(timeout)
        assert not self._thread.is_alive(), f"{self.who}'s run did not end in {timeout} s"
        return self.proc.returncode

    @property
    def code(self) -> int:
        return self.proc.returncode

    def said(self) -> str:
        return f"exit {self.code}\nstdout: {self.out[-800:]}\nstderr: {self.err[-1500:]}"

    def _jsonl(self, name: str) -> list:
        path = self.psql_dir / name
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def calls(self) -> list:
        """The shim's calls that carry a request, in order."""
        return [e for e in self._jsonl(PSQL_SHIM_LOG) if e.get("kind") != "version"]

    def commit_calls(self) -> list:
        return [e for e in self.calls() if "commit_write" in (e.get("stdin") or "")]

    def lookups(self) -> list:
        return [e for e in self.calls() if "find_write" in (e.get("stdin") or "")]

    def ends(self) -> dict:
        return {e["call"]: e for e in self._jsonl(PSQL_SHIM_ENDS) if "call" in e}

    def write_ids(self) -> list:
        """Each commit call's write id, `commit_write`'s second argument, as
        T243's `Writer` reads it."""
        found = []
        for call in self.commit_calls():
            m = re.search(r"commit_write\(\s*-?[0-9]+\s*,\s*'(" + UUID_RE + ")'", call.get("stdin") or "")
            assert m, f"{self.who}'s commit call carries no write id: {(call.get('stdin') or '')[:300]}"
            found.append(m.group(1))
        return found

    def pending(self) -> list:
        where = self.state / PENDING
        return sorted(p for p in where.iterdir()
                      if re.fullmatch(r"[0-9a-f]{64}", p.name)) if where.is_dir() else []


class PhaseW:
    """AT-LRMPG's phase W on one test's managed PostgreSQL (see the section's
    head): the server, the register at `primary`, the flipped copy, and a
    workstation for each engineer."""

    def __init__(self, request, root: Path, engineers: tuple = ("e1", "e2")):
        self.root = root
        self.m = Managed(request, root / "server")
        self.service = self.m.database(W_DB)
        self.m.bootstrapped(self.service)
        self.files = self.m.logins(self.service, *engineers, dump=False)
        self.genv = self._git_env(root / "git-home")
        self.seed = _w_seed()
        self.origin = root / "origin.git"
        _w_git(root, self.genv, "init", "-q", "--bare", "-b", "main", str(self.origin))
        seed = root / "seed"
        _w_git(root, self.genv, "clone", "-q", str(self.origin), str(seed))
        for path, text in self.seed.items():
            (seed / path).parent.mkdir(parents=True, exist_ok=True)
            (seed / path).write_bytes(text.encode("utf-8"))
        _w_git(seed, self.genv, "add", "-A")
        _w_git(seed, self.genv, "commit", "-q", "-m", "C: phase W's register (T258)")
        _w_git(seed, self.genv, "push", "-q", "origin", "main")
        self.c = _w_git(seed, self.genv, "rev-parse", "HEAD").strip()
        self.lanes_tree = _w_git(seed, self.genv, "rev-parse", f"{self.c}:lanes").strip()
        self.cut = self._to_primary()
        self.bindir = root / "bin"
        flipped_copy(LANES_INDEX, self.bindir, True)
        for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
            if (REPO / name).exists():
                shutil.copy2(str(REPO / name), str(self.bindir / name))
        self.lanes_edit = self.bindir / "lanes-edit.sh"
        self.fakebin = root / "fakebin"
        self.fakebin.mkdir()
        (self.fakebin / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (self.fakebin / "tmux").chmod(0o755)
        self.engineers = {who: self._engineer(who) for who in engineers}
        self.writers: list = []
        self._runs = itertools.count(1)
        request.addfinalizer(self._stop)

    @staticmethod
    def _git_env(home: Path) -> dict:
        home.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("GIT_", "PG", "LANES_", "TMUX", "RULE6_", "FAKE_PSQL", "CLAUDE_",
                                    "PROJECTS_ROOT", "XDG_", "T224_"))}
        env.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME="T258 estate", GIT_AUTHOR_EMAIL="t258@example.invalid",
                   GIT_COMMITTER_NAME="T258 estate", GIT_COMMITTER_EMAIL="t258@example.invalid",
                   LC_ALL="C")
        return env

    def _commit(self, kind: str, files: dict, **journal) -> int:
        """One entry creating `files`, committed by `commit_write` as e1's
        writer login; its seq."""
        edits, rows = _w_creates(files)
        clock = self.m.value("SELECT (clock_timestamp() + interval '60 s')::text;", W_DB)
        entry = {"journal": {"kind": kind, "verb": kind, "lane": OPERATOR, "workstation": WS,
                             "author": AUTHOR, "message": f"{kind} by {OPERATOR} (T258)", **journal},
                 "not_after": clock, "edits": edits, "files": rows}
        proc = self.m.commit(W_DB, "lanes_w_e1", self.files["lanes_w_e1"], entry)
        assert proc.returncode == 0, f"the {kind} entry did not commit:\n{_said(proc)}"
        return int(proc.stdout.split()[-1])

    def _to_primary(self) -> int:
        """AT-LR006's route over C, as e1's writer login: the render set's
        `import`, a `cutover` entry, then `record_marker`. The cutover's seq."""
        render = {p: t for p, t in self.seed.items() if RENDER_SET_PATH.match(p)}
        self._commit("import", render, git_commit=self.c, git_tree=self.lanes_tree)
        store = "".join(f"{line}\n" for line in (
            "store=primary", f"database={W_DB}", f"import={self.c}",
            f"lanes-tree={self.lanes_tree}", "utc=2026-11-10T00:00:00Z"))
        cut = self._commit("cutover", {STORE_PATH: store})
        client = self.m.value(f"SELECT version FROM {REGISTER}.schema_version;", W_DB)
        proc = self.m.as_login("lanes_w_e1", W_DB, f"SELECT {REGISTER}.record_marker(:client, :seq, "
                               ":'commit', :'ws');\n", self.files["lanes_w_e1"], client=client,
                               seq=cut, commit=MARKER_COMMIT, ws=W_WS)
        assert proc.returncode == 0 and proc.stdout.strip() == "present", _said(proc)
        switch = self.m.value(f"SELECT mode || ' ' || marker_state FROM {REGISTER}.register_switch;",
                              W_DB)
        assert switch == "primary present", f"the register is not at primary with its marker: {switch}"
        return cut

    def _engineer(self, who: str) -> dict:
        lane, where = W_LANES[who], self.root / who
        checkout = where / "checkout"
        _w_git(self.root, self.genv, "clone", "-q", str(self.origin), str(checkout))
        home = where / "home"
        agents = home / ".agents"
        agents.mkdir(parents=True)
        (agents / "workspace.yaml").write_text(f"repository: {self.origin}\npath: {checkout}\n",
                                               encoding="utf-8")
        for name in ("t", "state", "config"):
            (where / name).mkdir()
        conf = _private(where / "conf" / "lanes-index.conf", "\n".join([
            "mode=primary",
            f"register_url={self.m.socket_url(f'lanes_w_{who}', W_DB)}",
            f"register_passfile={self.files[f'lanes_w_{who}']}",
            f"reader_url={self.m.socket_url(f'lanes_r_{who}', W_DB)}",
            f"reader_passfile={self.files[f'lanes_r_{who}']}",
            f"register_label={LABEL}", ""]))
        env = dict(self.genv)
        env.update(HOME=str(home), TMPDIR=str(where / "t"), XDG_STATE_HOME=str(where / "state"),
                   XDG_CONFIG_HOME=str(where / "config"), CLAUDE_CONFIG_DIR=str(home / ".claude"),
                   AGENT_PROTOCOL_ROOT=str(agents), LANES_WORKSTATION=W_WS, LANES_HOST="eagle",
                   LANES_OS="linux", LANES_CONTAINER="none", LANES_IN_CONTAINER="0",
                   LANES_NO_GITHUB="1", LANES_REPO=str(checkout), LANES_INDEX_CONFIG=str(conf),
                   LANES_LANE=lane, LANES_SESSION=W_SESSIONS[who])
        # THE LANE CHECKOUT, made first: on primary the writer takes `<c>` from
        # `lane_checkout_path` and refuses 2 where it does not exist, naming
        # `lane-checkout <lane> --create` (lane 4's T415, B14's text).
        # `lane-checkout` reads the register through `canon_lane`, so it is a
        # decide arm (`lanes-edit.sh:4369` at `refs/l1/V-round5`), and since
        # T504 it prefetches on primary (B15 tasks:725), which needs a `psql`:
        # T203's shim, with no arms, first on `PATH` in a directory of its
        # own, as `launch()` gives a writer (AN13a's B2; line AF13b).
        psql_dir = where / "psql-lane-checkout"
        psql_dir.mkdir()
        (psql_dir / "psql").write_text(PSQL_SHIM, encoding="utf-8")
        (psql_dir / "psql").chmod(0o755)
        (psql_dir / PSQL_SHIM_CONTROL).write_text(json.dumps(
            {"psql": str(self.m.cluster.tool("psql")), "arms": []}), encoding="utf-8")
        made = subprocess.run(["bash", str(self.lanes_edit), "lane-checkout", lane, "--create"],
                              cwd=str(checkout), capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, check=False,
                              env=dict(env, PATH=os.pathsep.join([str(psql_dir), str(self.fakebin),
                                                                  _masked_path()])))
        assert made.returncode == 0 and Path(made.stdout.strip()).is_dir(), (
            f"lane-checkout {lane} --create did not make {who}'s lane checkout:\n{_said(made)}")
        return {"lane": lane, "checkout": checkout, "env": env, "state": where / "state"}

    # -------------------------------------------------- running the client
    def launch(self, who: str, argv: list, arms: tuple = ()) -> W258Writer:
        """`lanes-edit.sh <argv>` as `who`, with T203's shim, armed with
        `arms`, first on `PATH` in a directory of its own."""
        e = self.engineers[who]
        psql_dir = self.root / f"psql-{next(self._runs):02d}-{who}"
        psql_dir.mkdir()
        (psql_dir / "psql").write_text(PSQL_SHIM, encoding="utf-8")
        (psql_dir / "psql").chmod(0o755)
        (psql_dir / PSQL_SHIM_CONTROL).write_text(json.dumps(
            {"psql": str(self.m.cluster.tool("psql")), "arms": list(arms)}), encoding="utf-8")
        env = dict(e["env"], PATH=os.pathsep.join([str(psql_dir), str(self.fakebin),
                                                   _masked_path()]))
        proc = subprocess.Popen(["bash", str(self.lanes_edit), *argv], cwd=str(e["checkout"]),
                                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                                start_new_session=True)
        writer = W258Writer(who, proc, psql_dir, e["state"])
        self.writers.append(writer)
        return writer

    def run(self, who: str, argv: list, arms: tuple = ()) -> W258Writer:
        writer = self.launch(who, argv, arms)
        writer.wait()
        return writer

    def note(self, who: str, text: str) -> list:
        """One write: a `NOTED` line in the engineer's lane's log."""
        return ["log", "NOTED", f"lane:{W_LANES[who]}", text]

    def _stop(self) -> None:
        for writer in self.writers:
            if writer.ended is None and writer.proc.poll() is None:
                os.killpg(writer.proc.pid, 9)

    # -------------------------------------------------- the register, read by the provider
    def journal_after(self) -> list:
        """The journal's rows after the cutover: seq, write id, lane and verb."""
        return json.loads(self.m.value(
            "SELECT coalesce(json_agg(j ORDER BY j.seq), '[]') FROM (SELECT seq, write_id::text "
            f"AS write_id, lane, verb FROM {REGISTER}.journal WHERE seq > {self.cut}) j;", W_DB))

    def state(self) -> str:
        return self.m.value(W_STATE_SQL, W_DB)


def _hold_point(fifo: Path, writer: W258Writer, timeout: float = 90):
    """`fifo` opened for writing once `writer`'s call is held on it (the
    shim's `hold`), bounded: a writer that never reaches the call fails the
    case and never hangs it. Closing the handle lets the call go (T243's)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return os.fdopen(os.open(str(fifo), os.O_WRONLY | os.O_NONBLOCK), "wb")
        except OSError as error:
            if error.errno != errno.ENXIO:
                raise
        assert writer.ended is None, (
            f"{writer.who}'s run ended before its commit call was held:\n{writer.said()}")
        assert time.monotonic() < deadline, f"{writer.who}'s commit call was not held in {timeout} s"
        time.sleep(0.05)


def test_two_writer_logins_write_alike_and_the_log_names_each(tmp_path, request):
    """Two writer logins (section 1.4, "One engineer's logins"): E1 and E2,
    each with its own `register_url=` and password file, each make one
    write, and both commit as one login does: one journal row each, at
    consecutive seqs. The server's log ties each commit call, by its
    backend's pid, to its `connection authorized` line, which names E1 or E2
    (`operations.md` act 3's step 1, "Who connected")."""
    w = PhaseW(request, tmp_path)
    marks = [len(w.m.log())]
    writers = []
    for who in ("e1", "e2"):
        writer = w.run(who, w.note(who, f"{who}'s write (T258)"))
        assert writer.code == 0, f"{who}'s write on primary did not exit 0:\n{writer.said()}"
        writers.append(writer)
        marks.append(len(w.m.log()))
    rows = w.journal_after()
    assert [r["lane"] for r in rows] == [W_LANES["e1"], W_LANES["e2"]], (
        f"the journal after the cutover (seq {w.cut}) is not one row each, e1's then e2's: {rows}")
    assert [r["seq"] for r in rows] == [w.cut + 1, w.cut + 2], (
        f"the two writes are not at consecutive seqs after the cutover's {w.cut}: {rows}")
    for writer, row in zip(writers, rows):
        assert row["write_id"] in writer.write_ids(), (
            f"{writer.who}'s row {row} is not its commit call's write id {writer.write_ids()}")
    log = w.m.log()
    for k, who in enumerate(("e1", "e2")):
        logins = _commit_logins(log[marks[k]:marks[k + 1]])
        assert logins and set(logins) == {f"lanes_w_{who}"}, (
            f"the server's log ties {who}'s commit calls to {logins or 'no commit call'}, "
            f"not to lanes_w_{who}'s connection authorized line")


#: AT-LRMPG's revoked login: `[revoke]`, `lanes-index login revoke e2`; and
#: `[membership-only]`, the revoke block's step 2 alone, by the admin's hand.
#: Each: the words a new connection by each refused login is refused with.
REVOKED = {
    "revoke": {"lanes_w_e2": "is not permitted to log in", "lanes_r_e2": "is not permitted to log in"},
    "membership-only": {"lanes_w_e2": "permission denied for database"},
}


@pytest.mark.parametrize("case", list(REVOKED))
def test_a_revoked_login_is_refused_69_and_writes_nothing(tmp_path, request, case):
    """A revoked login (section 1.4, "What a revoked login sees"; section
    2.4's `revoke`), while a session of `lanes_w_e2` is open and idle, held
    by the test. `[revoke]`: `login revoke e2` prints each step's result; a
    new connection by either of e2's logins is refused, FATAL 28000, so e2's
    write exits 69 with nothing written, since the snapshot sent nothing that
    writes, and e2's read exits 69 (S3's table); the open session's next
    statement gets FATAL 57P01, or a lost connection, and never 42501 or an
    answer; the admin, with no superuser, needed no `pg_signal_backend`; both
    roles still exist; e1 still writes. `[membership-only]`: the revoke
    block's step 2 alone, by the admin, so `lanes_w_e2` keeps `LOGIN` and
    loses its membership: a new connection is refused, FATAL 42501,
    "permission denied for database", and e2's write exits 69 with nothing
    written."""
    w = PhaseW(request, tmp_path)
    m = w.m
    held = m.session("lanes_w_e2", W_DB, w.files["lanes_w_e2"])
    assert "ERROR" not in held.send("SELECT 'open';", "t258-open"), "e2's session did not open"
    if case == "revoke":
        proc = m.login("revoke", "e2", w.service)
        assert proc.returncode == 0, f"login revoke e2 failed:\n{_said(proc)}"
        for login in ("lanes_w_e2", "lanes_r_e2"):
            for step in (1, 2, 3):
                assert re.search(rf"^login {login}, step {step}, ", proc.stdout, re.M), (
                    f"login revoke printed no result for {login}'s step {step}:\n{_said(proc)}")
    else:
        m.psql(f"REVOKE {WRITER} FROM lanes_w_e2;\n", W_DB, user=ADMIN)
        role = m.role("lanes_w_e2")
        assert role["canlogin"] and role["groups"] == [], (
            f"step 2 alone did not keep LOGIN and take the membership: {role}")
    for login, words in REVOKED[case].items():
        refused = m.as_login(login, W_DB, "SELECT 1;\n", w.files[login])
        assert refused.returncode == 2 and words in refused.stderr, (
            f"[{case}] a new connection by {login} is not refused with {words!r}:\n{_said(refused)}")
    before = w.state()
    write = w.run("e2", w.note("e2", f"e2's write after [{case}] (T258)"))
    assert write.code == 69, f"[{case}] e2's write on primary did not exit 69:\n{write.said()}"
    assert write.commit_calls() == [], (
        f"[{case}] e2's refused write sent a commit call: the snapshot must send nothing that writes")
    assert w.state() == before, f"[{case}] e2's refused write changed the register"
    if case != "revoke":
        held.close()
        return
    read = w.run("e2", ["binding", W_LANES["e2"]])
    assert read.code == 69 and read.out == "", f"e2's read on primary did not exit 69:\n{read.said()}"
    said = held.send(f"SELECT {REGISTER}.commit_write(NULL, NULL, NULL, NULL, NULL);", "t258-next")
    ended = held.close()
    said += ended.stderr
    assert ("57P01" in said or "terminating connection due to administrator command" in said
            or "server closed the connection" in said), (
        f"the open session's next statement after the revoke was not ended: {said}")
    assert "42501" not in said and "permission denied" not in said, (
        f"the open session's next statement got 42501, so revoke returned between its steps: {said}")
    assert ended.stdout.split() == ["open"], f"the open session got an answer after the revoke: {ended.stdout!r}"
    assert m.value("SELECT count(*) FROM pg_roles WHERE rolname IN ('lanes_w_e2', 'lanes_r_e2');",
                   "postgres") == "2", "a revoked login's role was dropped"
    assert m.role(ADMIN)["super"] is False and m.value(
        f"SELECT pg_has_role('{ADMIN}', 'pg_signal_backend', 'MEMBER');", "postgres") == "f", (
        f"{ADMIN} is a superuser or holds pg_signal_backend: the case proves nothing of the revoke")
    mine = w.run("e1", w.note("e1", "e1 still writes after e2's revoke (T258)"))
    assert mine.code == 0, f"e1's write after e2's revoke did not exit 0:\n{mine.said()}"
    assert [r["lane"] for r in w.journal_after()] == [W_LANES["e1"]], (
        f"e1's write is not the journal's one new row: {w.journal_after()}")


def test_a_write_cut_by_a_revoke_mid_commit_is_in_doubt_and_ends_3_with_nothing_written(
        tmp_path, request):
    """`[mid-commit]` (section 2.4's `revoke`): the shim's `hold` blocks e2's
    commit call while `login revoke e2` runs, then releases it: its `psql`
    is refused at login and exits 2, which section 1.3's signals table makes
    in doubt for a commit call; its lookup's tries are refused at login too,
    and it exits 3 naming the id, the pending record kept. The journal holds
    no entry for the id, and so answers it; nothing is written. The journal
    is read here by the provider, the cluster's superuser."""
    w = PhaseW(request, tmp_path)
    gate = tmp_path / "mid-commit.fifo"
    os.mkfifo(str(gate))
    before = w.state()
    writer = w.launch("e2", w.note("e2", "e2's write cut mid-commit (T258)"),
                      arms=({"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(gate)},))
    held = _hold_point(gate, writer)
    try:
        revoke = w.m.login("revoke", "e2", w.service)
    finally:
        held.close()
    assert revoke.returncode == 0, f"login revoke e2 failed:\n{_said(revoke)}"
    writer.wait(timeout=150)
    assert writer.code == 3, f"e2's write cut mid-commit did not exit 3:\n{writer.said()}"
    ids = writer.write_ids()
    assert ids and len(set(ids)) == 1, f"e2's commit calls carried {ids}, not one write id"
    write_id = ids[0]
    assert write_id in writer.err, f"exit 3 does not name the write id {write_id}:\n{writer.said()}"
    ends = writer.ends()
    first = writer.commit_calls()[0]["call"]
    assert ends.get(first, {}).get("exit") == 2, (
        f"the held commit call's psql was not refused at login with exit 2: {ends.get(first)}")
    tries = writer.lookups()
    assert tries and all(ends.get(t["call"], {}).get("exit") == 2 for t in tries), (
        f"the lookup's tries were not each refused at login: {[ends.get(t['call']) for t in tries]}")
    records = writer.pending()
    assert len(records) == 1 and write_id in records[0].read_text(encoding="utf-8"), (
        f"the pending record naming {write_id} was not kept: {records}")
    assert w.m.value(f"SELECT count(*) FROM {REGISTER}.journal WHERE write_id = '{write_id}';",
                     W_DB) == "0", f"the journal holds an entry for the id {write_id}"
    assert w.state() == before, "the write cut mid-commit changed the register"


#: `target_session_attrs` (M5): each id's login, the value in its URL, and
#: whether it gets in and reads `register_head`.
TARGET_SESSION_ATTRS = {
    "primary": ("lanes_r_e1", "primary", True),
    "read-write": ("lanes_r_e1", "read-write", False),
    "read-write-bare-member": ("lanes_r_bare", "read-write", True),
}


@pytest.mark.parametrize("case", list(TARGET_SESSION_ATTRS))
def test_reader_url_takes_target_session_attrs_primary_not_read_write(tmp_path, request, case):
    """`target_session_attrs` (M5; section 1.4, "TLS and the endpoint"):
    `lanes_r_e1`'s `psql` with `target_session_attrs=primary` in its URL
    connects and reads `register_head`; with `read-write`, the connection is
    refused with libpq's `session is read-only`, since the login step made
    its sessions read-only by default. `lanes_r_bare`, a member made without
    the step, is let in by `read-write`: the floor is the login's own, since
    `ALTER ROLE ... SET` binds the role it names and not its members."""
    login, attrs, gets_in = TARGET_SESSION_ATTRS[case]
    m = Managed(request, tmp_path)
    service = m.database(W_DB)
    m.bootstrapped(service)
    files = m.logins(service, "e1", dump=False)
    if login == "lanes_r_bare":
        password = uuid.uuid4().hex
        m.psql(f"CREATE ROLE {login} LOGIN PASSWORD '{password}';\nGRANT {READER} TO {login};\n")
        files[login] = _private(m.home / "passfiles" / login, f"*:*:{W_DB}:{login}:{password}\n")
    env = {k: v for k, v in m.env.items() if not k.startswith("PG")}
    env.update(PGPASSFILE=str(files[login]), PGCONNECT_TIMEOUT="10")
    url = f"{m.socket_url(login, W_DB)}?target_session_attrs={attrs}"
    proc = subprocess.run([m.cluster.tool("psql"), "-X", "-q", "-A", "-t", "-w", "-v", "ON_ERROR_STOP=1",
                           "-d", url, "-c", f"SELECT seq FROM {REGISTER}.register_head;"],
                          capture_output=True, text=True, timeout=60, env=env, check=False)
    head = m.value(f"SELECT seq FROM {REGISTER}.register_head;", W_DB)
    if gets_in:
        assert proc.returncode == 0 and proc.stdout.strip() == head, (
            f"[{case}] {login} with target_session_attrs={attrs} did not read the head {head}:\n"
            f"{_said(proc)}")
    else:
        assert proc.returncode == 2 and "session is read-only" in proc.stderr, (
            f"[{case}] {login} with target_session_attrs={attrs} was not refused with "
            f"`session is read-only`:\n{_said(proc)}")


def test_after_login_rotate_the_old_password_files_write_exits_69_and_the_new_lines_commit_once(
        tmp_path, request):
    """Rotate's write half (TP:5317-5318; lane 3's batch 7, lane 2's item
    (3)): after `login rotate e1`, e1's write with the old password file
    exits 69 at its snapshot, since a refused login is "refused in any other
    way" (CLI:336), and the journal gains nothing; with the new lines written
    into the files e1's configuration names, the write exits 0 and commits
    once."""
    w = PhaseW(request, tmp_path, engineers=("e1",))
    proc = w.m.login("rotate", "e1", w.service)
    assert proc.returncode == 0, f"login rotate e1 failed:\n{_said(proc)}"
    new = _passwords(proc.stdout)
    assert sorted(new) == ["lanes_r_e1", "lanes_w_e1"], _said(proc)
    before = w.state()
    old = w.run("e1", w.note("e1", "e1's write with the old password file (T258)"))
    assert old.code == 69, f"e1's write with the old password file did not exit 69:\n{old.said()}"
    assert old.commit_calls() == [], "e1's refused write sent a commit call: the 69 is the snapshot's"
    assert w.state() == before, "e1's refused write changed the register"
    for login, line in new.items():
        _private(w.files[login], line + "\n")
    wrote = w.run("e1", w.note("e1", "e1's write with the new lines (T258)"))
    assert wrote.code == 0, f"e1's write with the new lines did not exit 0:\n{wrote.said()}"
    rows = w.journal_after()
    assert [r["lane"] for r in rows] == [W_LANES["e1"]], f"the journal did not gain one row, e1's: {rows}"
    assert set(wrote.write_ids()) == {rows[0]["write_id"]}, (
        f"the row's write id is not the one e1's commit calls carried: {wrote.write_ids()}")
