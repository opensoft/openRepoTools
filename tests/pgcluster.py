# SPDX-License-Identifier: Apache-2.0
"""A REAL POSTGRESQL 16 FOR THE TESTS THAT NEED ONE (#165, L2-0a and L2-0b).

What only an engine decides, a fake `psql` cannot show: a SERIALIZABLE
conflict's 40001, a GRANT that refuses, a COMMIT whose session dies. This is
the fixture those tests run on, R1's option (a) as the test plan's section
3.1 settles it, from the fixture probe's prototype (sha256 `5f20d742…`).
Python 3.9 or later, standard library only. `tests/conftest.py` registers it
as a pytest plugin from its `pytest_configure`.

ONE DISPOSABLE CLUSTER PER SESSION. `initdb -N` into a 0700
`mkdtemp(prefix="orpg-", dir="/tmp")`, whose socket path is 32 bytes whatever
`TMPDIR` is; a postmaster started by `Popen` on that Unix socket alone, with
no TCP; and one database per test, cloned from the session's template. A
`Popen` postmaster stays in pytest's process group, so `tests/run.sh`'s stop
of the group reaches it, where `pg_ctl`'s would not; on Linux it also dies
with a SIGKILLed pytest, and the next session's start sweeps what a killed
one left.

THE FIXTURES:

  * `pg_engine`, session-scoped: the binaries, found once. EVERY CLUSTER
    DEPENDS ON IT, so a test whose fixture closure holds it is a real-engine
    test, which is how `test_sql_register_fixture.py` tells one apart;
  * `pg_template_sql`, session-scoped and overridable: how the template is
    built. By default it is `Bootstrap()`, P8's bootstrap (T227, below); a
    module may return SQL of its own instead, run on an empty `tmpl`;
  * `pg_cluster`, session-scoped: the session's cluster, with the template
    `tmpl` built, then closed to connections, and `tmpl_imported` beside it;
  * `pg`, one database per test, `CREATE DATABASE t_<n> TEMPLATE tmpl`, then
    section 1.4's two database-level statements, and dropped `WITH (FORCE)`
    at its teardown;
  * `pg_imported`, the same from `tmpl_imported`, the imported register: a
    case that clones it fails, saying why, where the session has none;
  * `stoppable_cluster`, a cluster of the test's own, built like the
    session's, for the tests that stop the database: `stop()` is a fast
    shutdown, SIGINT and a wait, and `start_again()` starts it on the same
    data and socket directories.

THE TEMPLATES (T227; the test plan's section 3.1, "The templates"). `tmpl` is
built on each cluster by P8's bootstrap, `lanes-index bootstrap --no-passwords`
(lane 1's T109, L1-A7), run through the admin service as AT-P8's fixture runs
it: a libpq service in `~/.pg_service.conf` of the cluster's own 0700 `admin`
home, naming the cluster's socket, its superuser and the database, so no
connection string is ever an argument. It makes the schema, the owner, the
groups REGISTER-WRITER and READER, the indexer's login and their GRANTs, and
labels the switch `register-test`. Then the fixture's logins are made (T228:
`lanes-index login add fx` and `login add --dump-job`, through the same service
under a pty, since `login` refuses off a terminal): `lanes_w_fx` and
`lanes_r_fx`, as which every session a test runs as REGISTER-WRITER or as
READER logs in, and `lanes_register_dump`; their passwords stay in memory for
`passfile()`. Then `tmpl` is marked `IS_TEMPLATE true
ALLOW_CONNECTIONS false`. A clone does not copy `pg_database.datacl`, so each
clone runs section 1.4's `REVOKE ALL ON DATABASE` and `GRANT CONNECT`, with
`-v db=` its name; the first run prints what a clone's `datacl` held before
them (open point 12). On the session cluster, `tmpl_imported` is cloned from
`tmpl`, with test 7's fixture register imported by `lanes-index import --at
<C>` (lane 1's T115, L1-A13), as the operator lane does it (T227b): the
register, AT-7's, is built on a repository of the fixture's own (a bare origin,
the operator lane's checkout that `LANES_REPO` names, and W, a view that is
never it), and the import runs as `lanes_w_fx` while the switch reads `files`
with the marker `absent`. Where it does not import, there is no
`tmpl_imported`, the run's foot says why, and the cases that clone it fail; a
bootstrap that fails fails each real-engine test, saying so.

The binaries' directory goes first on `PATH` while a cluster is up, so the
code under test runs the `psql` of the server it talks to, and every
subprocess the fixture runs has no inherited `PG*` variable.

THE SWITCH, `OPENREPOTOOLS_REQUIRE_PG`, unset, `0` or `1`, and nothing else.
Where no PostgreSQL 16 is found, or the run is root (`initdb` refuses root):

  * unset or `0`, every real-engine test SKIPS, naming each place tried,
    `PG_BIN` and the package, and a banner says so even under `-q`;
  * `1`, as CI sets it, `pytest_configure` refuses the run before any test,
    `UsageError`, exit 4. The refusal is EAGER: a run that selects no
    real-engine test is refused too, so a job cannot go green without the
    engine it was promised.

The binaries are `PG_BIN`, which is final (one that fails is reported, never
replaced), then `pg_config --bindir`, then `/usr/lib/postgresql/16/bin`. Each
candidate needs `initdb`, `pg_ctl`, `postgres` and `psql`, all saying
`(PostgreSQL) 16`. Where they were found is printed at the run's foot whenever
they were looked for, which under the switch is every run (open point 12).

THE SMOKE, `python3 -I -B tests/pgcluster.py --smoke <name>…`, runs without
pytest. `session` starts a cluster, clones a database from an empty template
and runs `SELECT 1` in it; `stoppable` starts a cluster, stops it by SIGINT,
starts it again on the same directories and runs `SELECT 1`. It exits 0 when
each named smoke passes, 1 when one fails or there is no engine, and 2 for a
name it does not know.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

#: THE SMOKE IMPORTS NO PYTEST: run as a script, this module is standard
#: library only, and the fixtures below are plain functions it never calls.
if __name__ == "__main__":
    pytest = None
else:
    import pytest

#: The name `tests/conftest.py` registers this plugin under.
PLUGIN_NAME = "openrepotools-pg"

ENV_REQUIRE = "OPENREPOTOOLS_REQUIRE_PG"
MAJOR, PACKAGE = 16, "postgresql-16"
DEBIAN_BIN = Path("/usr/lib/postgresql/16/bin")
TOOLS = ("initdb", "pg_ctl", "postgres", "psql")
SUPERUSER, PORT, TEMPLATE = "lanes_test", 5432, "tmpl"
SOCKET_PARENT, PREFIX = "/tmp", "orpg-"   # /tmp/orpg-XXXXXXXX/.s.PGSQL.5432 = 32 bytes
SOCKET_MAX = 100                          # sun_path: 107 usable on Linux, 103 on macOS
FAST = ("fsync=off", "synchronous_commit=off", "full_page_writes=off")
DEADLINE, POLL = 30.0, 0.005
SKIP_TAG = "real PostgreSQL 16"
DIE_WITH_PYTEST = True                    # Linux: PR_SET_PDEATHSIG(SIGQUIT) on the postmaster
DEVNULL = subprocess.DEVNULL
_SKIPPED: List[str] = []
_SWEPT: List[str] = []

#: THE CODE UNDER TEST'S `lanes-index`, which the template's build runs.
REPO = Path(__file__).resolve().parent.parent
LANES_INDEX = REPO / "lanes-index"
LANES_EDIT = REPO / "lanes-edit.sh"

#: THE TEMPLATES (T227): the imported template's name, and the bootstrap's
#: inputs. The label is the one the import, outage and bounds modules name in
#: their `register_label=`; the others fill the switch's and the migrations
#: row's columns, whose CHECKs ask only that each is not empty.
IMPORTED = "tmpl_imported"
FX_LABEL = "register-test"
FX_REPOSITORY = "opensoft/openRepoTools-fixture"
FX_LANE = "fixture"
FX_WORKSTATION = "fixture"

#: SECTION 1.4'S TWO DATABASE-LEVEL STATEMENTS, as lane 1's role block holds
#: them (Y:2243-2244; `lanes-index`'s `_REGISTER_ROLE_BLOCK`), with `-v db=`.
DATABASE_LEVEL = ('REVOKE ALL ON DATABASE :"db" FROM PUBLIC;\n'
                  'GRANT CONNECT ON DATABASE :"db" TO lanes_register_writer, '
                  'lanes_register_reader, lanes_indexer;\n')

#: What the admin's `lanes-index` never inherits: the configuration's and the
#: workspace's variables. `PG*` goes too, as everywhere here.
ADMIN_ENV_DROPPED = ("LANES_", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "AGENT_PROTOCOL_ROOT",
                     "PROJECTS_", "TMUX", "CLAUDE_")
_DATACL: List[str] = []
_IMPORTED: List[str] = []
_IMPORTED_AT: List[str] = []

#: THE FIXTURE'S LOGINS (T228): the engineer `login add` is run for, and the
#: three logins it and `login add --dump-job` make. Every session a test runs
#: as REGISTER-WRITER or as READER logs in as the writer or the reader.
FX_ENGINEER = "fx"
FX_WRITER, FX_READER, FX_DUMP = "lanes_w_fx", "lanes_r_fx", "lanes_register_dump"
FX_LOGINS = (FX_WRITER, FX_READER, FX_DUMP)

#: A password-file line as `login add` prints it once, to a terminal:
#: `*:*:<database>:<login>:<password>` (lane 1's `_register_pgpass_line`).
PASSWORD_LINE = re.compile(r"^\*:\*:(?:[^:\\\n]|\\.)*:(lanes_[a-z0-9_]+):([^:\s]+)$", re.M)
_SECRET_FIELD = re.compile(r"^(\*:\*:.*:)[^:\n]*$", re.M)


def _fixture(**options):
    """`pytest.fixture(**options)`; in the smoke, which runs without pytest,
    the function as it is."""
    if pytest is None:
        return lambda function: function
    return pytest.fixture(**options)


def switch_problem(environ=os.environ) -> Optional[str]:
    """Why the switch's value is refused, or None for unset, `0` or `1`."""
    value = environ.get(ENV_REQUIRE, "")
    if value in ("", "0", "1"):
        return None
    return (f"{ENV_REQUIRE}={value!r} is neither 1 (the real-engine tests are "
            f"required, as in CI) nor 0 or unset (they skip, loudly, where "
            f"PostgreSQL {MAJOR} is missing)")


def required(environ=os.environ) -> bool:
    """Whether the real-engine tests must run: a usage error, exit 4, for a
    value that is neither."""
    problem = switch_problem(environ)
    if problem:
        raise pytest.UsageError(problem)
    return environ.get(ENV_REQUIRE, "") == "1"


# ------------------------------------------------------------ the binaries
def check_bindir(bindir: Path) -> Optional[str]:
    """None where `bindir` holds the four tools at major 16, else why not."""
    if not bindir.is_dir():
        return f"{bindir} is not a directory"
    missing = [t for t in TOOLS if not os.access(str(bindir / t), os.X_OK) or (bindir / t).is_dir()]
    if missing:
        return f"{bindir} has no {', '.join(missing)}"
    for tool in TOOLS:
        try:
            said = subprocess.run([str(bindir / tool), "--version"], stdin=DEVNULL, capture_output=True,
                                  text=True, timeout=20, check=False).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            said = f"<{exc}>"
        m = re.search(r"\(PostgreSQL\) (\d+)", said)
        if not m or int(m.group(1)) != MAJOR:
            return f"{bindir / tool} is not PostgreSQL {MAJOR}: it says {said!r}"
    return None


def find_bindir(environ=os.environ) -> Tuple[Optional[Path], str]:
    """(directory, how found), or (None, every place tried and why not)."""
    named = environ.get("PG_BIN", "")
    if named:
        why = check_bindir(Path(named))
        return ((Path(named), "PG_BIN") if why is None else
                (None, f"PG_BIN={named}, and {why}; a named PG_BIN is never replaced by a found one"))
    tried = ["PG_BIN is unset"]
    pg_config = shutil.which("pg_config", path=environ.get("PATH", os.defpath))
    if pg_config:
        try:
            out = subprocess.run([pg_config, "--bindir"], stdin=DEVNULL, capture_output=True,
                                 text=True, timeout=20, check=False).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            out = ""
        why = check_bindir(Path(out)) if out else "it printed nothing"
        if why is None:
            return Path(out), f"`{pg_config} --bindir`"
        tried.append(f"`{pg_config} --bindir` says {out or '-'}, and {why}")
    else:
        tried.append("no pg_config on PATH")
    why = check_bindir(DEBIAN_BIN)
    if why is None:
        return DEBIAN_BIN, "the Debian and Ubuntu layout"
    return None, "; ".join(tried + [why])


class Probe:
    """Where the binaries are and how they were found, or the problem."""

    def __init__(self) -> None:
        self.bindir, self.how = find_bindir()
        self.problem: Optional[str] = None
        if self.bindir is None:
            self.problem = (f"no {SKIP_TAG} for the real-engine tests ({self.how}): install the "
                            f"package {PACKAGE} (server and client), or set PG_BIN to a directory "
                            f"holding {', '.join(TOOLS)} of major version {MAJOR}")
        elif hasattr(os, "geteuid") and os.geteuid() == 0:
            self.problem = (f"{SKIP_TAG} is at {self.bindir} ({self.how}), but this run is root, and "
                            f"initdb refuses to run as root: run the suite as an ordinary user")

    def found(self) -> str:
        return f"{SKIP_TAG} at {self.bindir} ({self.how})"


_PROBE: Optional[Probe] = None


def probe() -> Probe:
    global _PROBE
    if _PROBE is None:
        _PROBE = Probe()
    return _PROBE


def _engine_first(bindir: Path, path: str) -> str:
    """`path` with `bindir` first, once."""
    rest = [entry for entry in path.split(os.pathsep) if entry and entry != str(bindir)]
    return os.pathsep.join([str(bindir), *rest])


def _without_pg(environ=os.environ) -> Dict[str, str]:
    """`environ` with no variable whose name begins `PG`: a person's
    `PGHOST`, `PGSERVICE` or `PGPASSWORD` never steers a test."""
    return {k: v for k, v in environ.items() if not k.startswith("PG")}


# ------------------------------------------------------------ the cluster
#: THE STALE SWEEP'S SEAMS (T205c): where a process's identity is read, and
#: how a signal is sent. Its test points them at a fake `/proc`, or none, as
#: on macOS, and at a recorder, so that no real process can be signalled.
_PROC = Path("/proc")
_kill = os.kill
ORPHAN_WAIT = 10.0                        # seconds a stale postmaster gets to end, per signal
#: `lanes_index_tty`'s bound and launcher, named for its test (T228b).
TTY_DEADLINE = 300.0
_tty_popen = subprocess.Popen


def _ticks(pid: int) -> str:
    """The process's start time (Linux), so a reused pid is not taken for its owner."""
    try:
        return (_PROC / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return "-"


def _running(pid: int, ticks: str = "-") -> bool:
    try:
        _kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        if (_PROC / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
            return False                  # a zombie counts as dead
    except (OSError, IndexError):
        pass
    return ticks == "-" or _ticks(pid) == ticks


def _stop_orphan(root: Path) -> bool:
    """Stop the postmaster a dead session left in `root`, if it is provably
    that one (T205c). True when no process of the root's is left: there is no
    pidfile; its pid names no process, or one this user may not signal, or
    one whose command line does not hold the root's data directory; or the
    postmaster, proved by its command line and start time, ended on SIGQUIT
    or SIGKILL. False, with nothing signalled, where the pidfile does not
    parse to a positive pid and the root's data directory, or where the
    process cannot be proved to be that postmaster (no `/proc`, as on
    macOS); False too where the proved postmaster does not end. A pid is
    never signalled on the pidfile's word alone."""
    try:
        lines = (root / "data" / "postmaster.pid").read_text().splitlines()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    try:
        pid_n, datadir = int(lines[0]), lines[1]
    except (IndexError, ValueError):
        return False
    if pid_n <= 0 or datadir != str(root / "data"):
        return False                      # 0 is a process group, -1 every process
    try:
        _kill(pid_n, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return True                       # another user's process: not this user's postmaster
    if not _running(pid_n):
        return True                       # a zombie
    ticks = _ticks(pid_n)
    try:
        argv = (_PROC / str(pid_n) / "cmdline").read_bytes().split(b"\0")
    except OSError:
        return False                      # no `/proc`: who holds the pid cannot be proved
    if ticks == "-" or argv == [b""]:
        return False
    if os.fsencode(datadir) not in argv:
        return True                       # a reused pid: that postmaster is gone
    for sig in (signal.SIGQUIT, signal.SIGKILL):
        if not _running(pid_n, ticks):
            return True
        try:
            _kill(pid_n, sig)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        end = time.monotonic() + ORPHAN_WAIT
        while time.monotonic() < end and _running(pid_n, ticks):
            time.sleep(0.02)
        if not _running(pid_n, ticks):
            return True
    return False


def sweep_stale() -> List[str]:
    """What a SIGKILLed session left: this user's PREFIX dirs whose owner is gone."""
    swept = []
    for root in Path(SOCKET_PARENT).glob(PREFIX + "*"):
        try:
            info = root.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                continue
            owner = (root / "owner").read_text().split() if (root / "owner").exists() else []
        except OSError:
            continue
        if len(owner) == 2 and owner[0].isdigit() and _running(int(owner[0]), owner[1]):
            continue
        if not owner and time.time() - info.st_mtime < 60:
            continue                      # being made this instant: not ours to judge yet
        if not _stop_orphan(root):
            continue                      # its postmaster is unproved or alive: not to be removed
        shutil.rmtree(root, ignore_errors=True)
        swept.append(str(root))
    return swept


class ClusterError(Exception):
    pass


class Bootstrap:
    """`pg_template_sql`'S DEFAULT (T227): build `tmpl` by P8's bootstrap,
    then make the fixture's logins (T228) unless `logins` is False, then run
    `sql`, if any, on it. A plain string instead is SQL run on an empty
    `tmpl`, as the smokes' clusters have it."""

    def __init__(self, sql: str = "", logins: bool = True) -> None:
        self.sql, self.logins = sql, logins

    def __repr__(self) -> str:
        return f"Bootstrap(sql={self.sql!r}, logins={self.logins!r})"


def _masked(text: str) -> str:
    """`text` with each password-file line's last field, the password, hidden."""
    return _SECRET_FIELD.sub(lambda m: m.group(1) + "<password>", text or "")


def _tail(proc: subprocess.CompletedProcess, size: int = 800) -> str:
    """A command's last words, stdout then stderr, on one line."""
    said = " | ".join(line.strip() for line in f"{proc.stdout or ''}\n{proc.stderr or ''}".splitlines()
                      if line.strip())
    return said[-size:] or "<nothing>"


def _client_env(host: Path, user: str, dbname: str, appname: str, bindir: Path) -> dict:
    env = _without_pg()
    env.update(PGHOST=str(host), PGPORT=str(PORT), PGUSER=user, PGDATABASE=dbname,
               PGAPPNAME=appname, PGCONNECT_TIMEOUT="10", LC_ALL="C",
               PATH=_engine_first(bindir, env.get("PATH", os.defpath)))
    return env


def _die_with_parent(parent: int):
    if not (DIE_WITH_PYTEST and sys.platform.startswith("linux")):
        return None
    import ctypes
    prctl = ctypes.CDLL(None, use_errno=True).prctl

    def preexec() -> None:
        prctl(1, int(signal.SIGQUIT), 0, 0, 0)               # PR_SET_PDEATHSIG
        if os.getppid() != parent:
            os._exit(70)
    return preexec


class Cluster:
    """One cluster: its private directory, its postmaster and its template."""

    def __init__(self, bindir: Path, template_sql="", imported: bool = False) -> None:
        """`template_sql` is `pg_template_sql`'s value: a `Bootstrap`, or SQL
        for an empty `tmpl` (the smokes' default). `imported` builds
        `tmpl_imported` too."""
        self.bindir, self.template_sql, self.imported = bindir, template_sql, imported
        self.root: Optional[Path] = None
        self.proc: Optional[subprocess.Popen] = None
        self.count, self.timings = 0, {}
        #: The switch's label where the bootstrap built `tmpl`, else None.
        self.label: Optional[str] = None
        #: Why there is no `tmpl_imported`, where it was asked for and is not.
        self.imported_problem: Optional[str] = None
        #: The repository `tmpl_imported` was imported from (T227b), once it
        #: is: its origin, the operator lane's checkout, W and C. Read only.
        self.imported_register: Optional["ImportedRegister"] = None
        #: The fixture's logins' passwords, as `login add` printed them once
        #: (T228). Kept in memory for `passfile()`, never printed.
        self.passwords: Dict[str, str] = {}

    def tool(self, name: str) -> str:
        return str(self.bindir / name)

    def server_env(self) -> dict:
        env = _without_pg()
        env.update(LC_ALL="C", TZ="UTC", PATH=_engine_first(self.bindir, env.get("PATH", os.defpath)))
        return env

    def psql(self, sql: str, dbname: str = "postgres", user: str = SUPERUSER,
             check: bool = True, appname: str = "pytest",
             variables: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        argv = [self.tool("psql"), "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"]
        for name, value in (variables or {}).items():
            argv += ["-v", f"{name}={value}"]
        proc = subprocess.run([*argv, "-f", "-"], input=sql, capture_output=True, text=True,
                              timeout=120, env=_client_env(self.root, user, dbname, appname,
                                                           self.bindir),
                              check=False)
        if check and proc.returncode != 0:
            raise ClusterError(f"psql as {user} on {dbname} exited {proc.returncode}: {proc.stderr.strip()}")
        return proc

    def log_tail(self) -> str:
        try:
            return " | ".join((self.root / "server.log").read_text().splitlines()[-5:])
        except OSError:
            return "<no log>"

    def ready(self) -> bool:
        """The postmaster's own `ready` status, line 8 of postmaster.pid: what pg_ctl -w reads."""
        try:
            lines = (self.root / "data" / "postmaster.pid").read_text().splitlines()
        except OSError:
            return False
        return len(lines) >= 8 and lines[0] == str(self.proc.pid) and lines[7].strip() == "ready"

    def start(self) -> None:
        """Sweep, make the directory, `initdb`, start, and build the template."""
        t0 = time.monotonic()
        _SWEPT.extend(sweep_stale())
        self.root = Path(tempfile.mkdtemp(prefix=PREFIX, dir=SOCKET_PARENT))   # mode 0700
        (self.root / "owner").write_text(f"{os.getpid()} {_ticks(os.getpid())}\n")
        sock = self.root / f".s.PGSQL.{PORT}"
        if len(os.fsencode(str(sock))) > SOCKET_MAX:
            raise ClusterError(f"the socket path {sock} is over {SOCKET_MAX} bytes")
        t1 = time.monotonic()
        init = subprocess.run([self.tool("initdb"), "-D", str(self.root / "data"), "-N", "-A", "trust",
                               "-U", SUPERUSER, "-E", "UTF8", "--locale=C"], stdin=DEVNULL,
                              capture_output=True, text=True, env=self.server_env(), timeout=120,
                              check=False)
        if init.returncode != 0:
            raise ClusterError(f"initdb exited {init.returncode}: {init.stderr.strip()}")
        t2 = time.monotonic()
        self.launch()
        t3 = time.monotonic()
        self.build_template()
        t4 = time.monotonic()
        self.timings = {"initdb": t2 - t1, "ready": t3 - t2, "template": t4 - t3, "start": t4 - t0}

    # -------------------------------------------------------- the templates (T227)
    def build_template(self) -> None:
        """`tmpl`, by the bootstrap or by SQL, then `tmpl_imported` where it
        was asked for, then `tmpl` closed to connections."""
        self.psql(f"CREATE DATABASE {TEMPLATE};")
        sql = self.template_sql
        if isinstance(sql, Bootstrap):
            self.bootstrap(TEMPLATE, FX_LABEL)
            self.label = FX_LABEL
            if sql.logins:
                self.make_logins(TEMPLATE)
            sql = sql.sql
        if sql.strip():
            self.psql(sql, dbname=TEMPLATE)
        if self.imported:
            self.build_imported()
        self.psql(f"ALTER DATABASE {TEMPLATE} WITH IS_TEMPLATE true ALLOW_CONNECTIONS false;")

    def admin_env(self) -> dict:
        """THE ADMIN'S `lanes-index` ENVIRONMENT: no `PG*`, no configuration or
        workspace variable, `HOME` the cluster's own `admin` directory (where
        `~/.pg_service.conf` is, and no `lanes-index.conf`, so `load_config`
        reads its defaults), the workstation named, and the engine's tools
        first on `PATH`, so its `psql` is the server's."""
        env = {k: v for k, v in _without_pg().items() if not k.startswith(ADMIN_ENV_DROPPED)}
        env.update(HOME=str(self.root / "admin"), LANES_WORKSTATION=FX_WORKSTATION, LC_ALL="C",
                   TZ="UTC", PATH=_engine_first(self.bindir, env.get("PATH", os.defpath)))
        return env

    def admin_service(self, database: str) -> str:
        """The admin service naming `database`: a section of the admin home's
        `.pg_service.conf`, 0600, with the cluster's socket and superuser.
        The socket's trust needs no `~/.pgpass`."""
        home = self.root / "admin"
        home.mkdir(mode=0o700, exist_ok=True)
        name, path = f"fx_{database}", home / ".pg_service.conf"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if f"[{name}]\n" not in text:
            text += (f"[{name}]\nhost={self.root}\nport={PORT}\nuser={SUPERUSER}\n"
                     f"dbname={database}\n\n")
            path.write_text(text, encoding="utf-8")
            path.chmod(0o600)
        return name

    def lanes_index(self, argv: List[str]) -> subprocess.CompletedProcess:
        """The code under test's `lanes-index`, as the admin, from the
        cluster's directory."""
        return subprocess.run([sys.executable, str(LANES_INDEX), *argv], stdin=DEVNULL,
                              capture_output=True, text=True, env=self.admin_env(),
                              cwd=str(self.root), timeout=300, check=False)

    def lanes_index_tty(self, argv: List[str]) -> Tuple[int, str, str]:
        """`lanes_index` with its stdout a pty, for `login`, which refuses off
        a terminal (operations.md section 2.4): (exit, stdout, stderr), the
        pty's CR LF read back as LF. A run that outlasts the admin's 300 s is
        killed."""
        import pty
        import select
        primary, secondary = pty.openpty()
        try:
            proc = _tty_popen([sys.executable, str(LANES_INDEX), *argv], stdin=DEVNULL,
                                    stdout=secondary, stderr=subprocess.PIPE,
                                    env=self.admin_env(), cwd=str(self.root))
        except OSError:
            os.close(primary)
            raise
        finally:
            os.close(secondary)
        out, end = [], time.monotonic() + TTY_DEADLINE
        try:
            while time.monotonic() < end:
                ready, _, _ = select.select([primary], [], [], max(0.0, end - time.monotonic()))
                if not ready:
                    break
                try:
                    chunk = os.read(primary, 65536)
                except OSError:                     # EIO: the child closed its end
                    break
                if not chunk:
                    break
                out.append(chunk)
        finally:
            os.close(primary)
        # T228b: the deadline holds past the pty's end. A child that closed
        # the pty and lives on, or holds stderr open, is read only until the
        # deadline, then killed: no read or wait outlasts it.
        errs, fd = [], proc.stderr.fileno()
        while time.monotonic() < end:
            ready, _, _ = select.select([fd], [], [], max(0.0, end - time.monotonic()))
            if not ready:
                break
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            errs.append(chunk)
        if proc.poll() is None:
            try:
                proc.wait(timeout=max(0.0, end - time.monotonic()))
            except subprocess.TimeoutExpired:
                proc.kill()
        err = b"".join(errs).decode("utf-8", "replace")
        proc.stderr.close()
        code = proc.wait(timeout=DEADLINE)
        return code, b"".join(out).decode("utf-8", "replace").replace("\r\n", "\n"), err

    def make_logins(self, database: str) -> None:
        """THE FIXTURE'S LOGINS (T228; section 3.1, "The fixture's logins"),
        once per cluster, after the bootstrap: `lanes-index login add fx`,
        then `login add --dump-job`, each through the admin service on
        `database` and under a pty (lane 1's T110, L1-A8). They make
        `lanes_w_fx` in REGISTER-WRITER and `lanes_r_fx` in READER, each with
        its own floors, and `lanes_register_dump` in READER, each with a
        SCRAM verifier lane 1's code computes. The passwords each prints
        once are kept for `passfile()`: the socket's trust ignores them, a
        TLS cluster's SCRAM does not. No error text here holds one."""
        service = self.admin_service(database)
        for argv in (["login", "add", FX_ENGINEER, "--admin-service", service],
                     ["login", "add", "--dump-job", "--admin-service", service]):
            code, out, err = self.lanes_index_tty(argv)
            if code != 0:
                raise ClusterError(f"`lanes-index {' '.join(argv[:3])}` through the admin service "
                                   f"on {database} exited {code}, so the fixture has no logins "
                                   f"(lane 1's T110, L1-A8, builds `login`): "
                                   f"{_masked(out)[-400:]} | {_masked(err)[-400:]}")
            self.passwords.update(PASSWORD_LINE.findall(out))
        names = ", ".join(f"'{login}'" for login in FX_LOGINS)
        can = self.psql(f"SELECT rolname FROM pg_catalog.pg_roles WHERE rolcanlogin AND "
                        f"rolname IN ({names}) ORDER BY 1;").stdout.split()
        missing = sorted(set(FX_LOGINS) - set(can)) + sorted(set(FX_LOGINS) - set(self.passwords))
        if missing:
            raise ClusterError(f"after `login add`, these logins cannot log in or printed no "
                               f"password line: {', '.join(missing)}")

    def passfile(self, login: str) -> Path:
        """A 0600 libpq password file holding `login`'s line at any host,
        port and database, in the cluster's private `secrets` directory:
        what a `register_passfile=` or `reader_passfile=` names."""
        if login not in self.passwords:
            raise ClusterError(f"no password for {login}: only the fixture's logins have one")
        secrets = self.root / "secrets"
        secrets.mkdir(mode=0o700, exist_ok=True)
        path = secrets / f"{login}.pgpass"
        path.write_text(f"*:*:*:{login}:{self.passwords[login]}\n", encoding="utf-8")
        path.chmod(0o600)
        return path

    def bootstrap(self, database: str, label: str) -> str:
        """P8's bootstrap on `database`, through the admin service, with
        `--no-passwords`: the roles are global, so a second run on a cluster
        finds them `unchanged`. Its output, which holds no secret."""
        proc = self.lanes_index(["bootstrap", "--admin-service", self.admin_service(database),
                                 "--label", label, "--repository", FX_REPOSITORY,
                                 "--lane", FX_LANE, "--no-passwords"])
        if proc.returncode != 0:
            raise ClusterError(f"`lanes-index bootstrap --no-passwords` through the admin "
                               f"service on {database} exited {proc.returncode}, so the "
                               f"template has no register (lane 1's T109, L1-A7, builds the "
                               f"bootstrap): {_tail(proc)}")
        return proc.stdout

    def build_imported(self) -> None:
        """`tmpl_imported` (T227b): a clone of `tmpl`, with section 1.4's two
        statements, into which test 7's fixture register is imported by
        `lanes-index import --at <C>` as the operator lane runs it (lane 1's
        T115): from an `ImportedRegister` of the cluster's own, through the
        operator lane's checkout (`LANES_REPO`, never W), with the switch at
        `files` and the marker `absent`, as the writer login `lanes_w_fx` on
        the cluster's socket (the superuser where the template has no
        logins). Then seq 0 must be the one `import` entry, at C, with the
        switch unchanged, and the database is closed to connections. Where
        any step fails, there is no `tmpl_imported`, and `imported_problem`
        says why: the session goes on, and only the cases that clone it
        fail."""
        register, user = None, (FX_WRITER if FX_WRITER in self.passwords else SUPERUSER)
        if self.label is None:
            self.imported_problem = "tmpl was not built by the bootstrap, so it holds no register"
        else:
            self.psql(f"CREATE DATABASE {IMPORTED} TEMPLATE {TEMPLATE};")
            self.psql(DATABASE_LEVEL, variables={"db": IMPORTED})
            try:
                register = ImportedRegister(self.root / "imported", self.bindir)
                proc = register.import_at(self, IMPORTED, user)
                if proc.returncode != 0:
                    self.imported_problem = (f"`lanes-index import --at {register.c}` as {user} "
                                             f"exited {proc.returncode} (lane 1's T115, L1-A13, "
                                             f"builds it): {_tail(proc)}")
                else:
                    self.imported_problem = self._imported_check(register.c)
            except (ClusterError, OSError, subprocess.SubprocessError) as exc:
                self.imported_problem = f"test 7's fixture register was not built: {exc}"[:1200]
            if self.imported_problem is not None:
                self.drop_database(IMPORTED)
        if self.imported_problem is not None:
            _IMPORTED.append(self.imported_problem)
            return
        self.imported_register = register
        _IMPORTED_AT.append(f"test 7's register at {register.c}, by `lanes-index import --at` "
                            f"as {user}")
        self.psql(f"ALTER DATABASE {IMPORTED} WITH IS_TEMPLATE true ALLOW_CONNECTIONS false;")

    def _imported_check(self, commit: str) -> Optional[str]:
        """What the clones of `tmpl_imported` rest on (AT-LR006's route, AT-7's
        "Success"): one journal entry, seq 0, an `import` at `commit`; the
        head at 0; the switch at `files` with the marker `absent`. None, or
        what differs."""
        said = self.psql(
            "SELECT concat_ws('|', (SELECT string_agg(seq || ':' || kind || ':' || "
            "coalesce(git_commit, '-'), ',' ORDER BY seq) FROM lanes_register.journal), "
            "(SELECT seq::text FROM lanes_register.register_head), "
            "(SELECT mode || ':' || marker_state FROM lanes_register.register_switch));",
            dbname=IMPORTED).stdout.strip()
        wanted = f"0:import:{commit}|0|files:absent"
        if said != wanted:
            return (f"`lanes-index import --at {commit}` exited 0, and {IMPORTED} reads "
                    f"{said!r} (journal|head|switch), not {wanted!r}")
        return None

    def launch(self) -> None:
        """`postgres` by `Popen` on this cluster's directories, and wait until it is ready."""
        argv = [self.tool("postgres"), "-D", str(self.root / "data"), "-p", str(PORT),
                "-c", "listen_addresses=", "-c", f"unix_socket_directories={self.root}"]
        for setting in FAST:
            argv += ["-c", setting]
        with open(self.root / "server.log", "ab") as log:
            self.proc = subprocess.Popen(argv, stdin=DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                         env=self.server_env(), preexec_fn=_die_with_parent(os.getpid()))
        end = time.monotonic() + DEADLINE
        while not self.ready():
            if self.proc.poll() is not None:
                raise ClusterError(f"postgres exited {self.proc.returncode} starting: {self.log_tail()}")
            if time.monotonic() > end:
                raise ClusterError(f"postgres was not ready in {DEADLINE:.0f} s: {self.log_tail()}")
            time.sleep(POLL)

    def stop(self) -> None:
        """A fast shutdown: SIGINT to the postmaster this cluster started, and a wait."""
        if self.proc is None or self.proc.poll() is not None:
            raise ClusterError("the cluster is not running, so it cannot be stopped")
        self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(timeout=DEADLINE)
        except subprocess.TimeoutExpired:
            raise ClusterError(f"postgres did not stop in {DEADLINE:.0f} s after SIGINT: "
                               f"{self.log_tail()}") from None

    def start_again(self) -> None:
        """Start the stopped cluster on the same data and socket directories."""
        if self.proc is not None and self.proc.poll() is None:
            raise ClusterError("the cluster is running, so it cannot be started again")
        self.launch()

    def new_database(self, template: str = TEMPLATE) -> str:
        """`CREATE DATABASE t_<n> TEMPLATE <template>`, then, where the
        bootstrap built the template, section 1.4's two database-level
        statements with `-v db=t_<n>`, since a clone does not copy
        `pg_database.datacl`. The first such clone of a run records what its
        `datacl` held before them, which the run's foot prints (open point
        12)."""
        self.count += 1
        name = f"t_{self.count}"
        self.psql(f"CREATE DATABASE {name} TEMPLATE {template};")
        if self.label is not None:
            if not _DATACL:
                acl = self.psql("SELECT coalesce(datacl::text, 'NULL') FROM pg_catalog.pg_database "
                                "WHERE datname = :'db';", variables={"db": name}).stdout.strip()
                _DATACL.append(f"{'empty (NULL)' if acl == 'NULL' else acl}, on {name}, a clone "
                               f"of {template}")
            self.psql(DATABASE_LEVEL, variables={"db": name})
        return name

    def drop_database(self, name: str) -> None:
        self.psql(f"DROP DATABASE IF EXISTS {name} WITH (FORCE);")

    def destroy(self) -> None:
        """SIGQUIT, a wait (SIGKILL after the deadline), and the directory removed."""
        try:
            if self.proc is not None and self.proc.poll() is None:
                self.proc.send_signal(signal.SIGQUIT)          # immediate shutdown
                try:
                    self.proc.wait(timeout=DEADLINE)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
        finally:
            if self.root is not None:
                shutil.rmtree(self.root, ignore_errors=True)


class Database:
    """One test's database, and how to reach it as each role."""

    def __init__(self, cluster: Cluster, name: str) -> None:
        self.cluster, self.name, self.host, self.port = cluster, name, cluster.root, PORT
        self.psql_bin = cluster.tool("psql")

    def url(self, user: str = SUPERUSER) -> str:
        return f"postgresql://{user}@{quote(str(self.host), safe='')}:{PORT}/{self.name}"

    def env(self, user: str = SUPERUSER, appname: str = "pytest") -> dict:
        return _client_env(self.host, user, self.name, appname, self.cluster.bindir)

    def psql(self, sql: str, user: str = SUPERUSER, check: bool = True) -> subprocess.CompletedProcess:
        return self.cluster.psql(sql, dbname=self.name, user=user, check=check)

    def session(self, user: str = SUPERUSER, appname: str = "pytest") -> subprocess.Popen:
        """A psql of its own, fed on stdin: a separate session, for concurrency."""
        return subprocess.Popen([self.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=self.env(user, appname))


# ------------------------------------------------------------ test 7's fixture register (T227b)
#: TEST 7'S FIXTURE REGISTER, WHICH `tmpl_imported` HOLDS (T227b; the test
#: plan's AT-7, "Fixture", and section 3.1, where "the imported register" is
#: test 7's fixture register after a successful `import --at`): a files-mode
#: workspace repository at C on a bare origin, holding AT-7's additions
#: (`WORD` lines with milliseconds, the six HOLD-shaped kinds, a `HOLD` and a
#: `LANDING` with no UTC and a `LANDING` whose stamp does not parse, a
#: `LANDING EXPIRED` with no `for lane`, an archived lane, aliases,
#: `lanes/repos.tsv` and `lanes/log/README.md` outside the render set, a log
#: whose name differs from its lane's in case, and a lane with no log).
def _test7_seed() -> Dict[str, str]:
    """C'S FILES BEFORE THE OPERATOR'S WRITE (T227b): T211's `SEED`, copied
    from `tests/test_sql_register_import.py` at line W3a's `4bfef75c` byte
    for byte (its lines 97-104, 112-115, 118-164 and 185-226), so that the
    template holds test 7's register on a branch without that module. Each
    copy must stay equal to the other until one imports it from here."""
    UUID_A1 = "aaaaaaaa-0001-4000-8000-00000000a001"
    UUID_A2 = "aaaaaaaa-0003-4000-8000-00000000a003"
    UUID_B1 = "bbbbbbbb-0001-4000-8000-00000000b001"
    UUID_C1 = "dddddddd-0001-4000-8000-00000000d001"
    UUID_D1 = "dddddddd-0002-4000-8000-00000000d002"
    UUID_W1 = "eeeeeeee-0002-4000-8000-00000000e002"
    UUID_Z1 = "eeeeeeee-0001-4000-8000-00000000e001"
    TIP_A = "0123456789abcdef0123456789abcdef01234567"

    def _row(lane: str, ids: str, state: str, started: str = "2026-10-01T00:00Z",
             ws: str = "Eagle / test / brett", objects: str = "none") -> str:
        return (f"| `{lane}` | harness {ids} | {ws} | {started} | {objects} | handoffs/{lane}.md "
                f"| {state} |")

    #: THE TAKES AT-7 PUTS IN THE REGISTER, each named for the case that reads it.
    TAKE_LINES = {
        "hold-no-utc": f"HOLD — lane repoA-2 (Eagle), window w: opensoft/repoH main {TIP_A} for a "
                       f"window with no stamp",
        "landing-no-utc": f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, PR #11 into "
                          f"opensoft/repoL main",
        "bad-stamp": f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, 2026-13-45T99:99Z, PR #12 "
                     f"into opensoft/repoS main",
    }
    #: The `LANDING EXPIRED` shape with no `for lane`: it names repoA-2's open
    #: take, PR #9 on opensoft/repoE, and must release nothing (U3; F13).
    EXPIRED_NO_HOLDER = (f"LANDING EXPIRED — lane repoA-1, session {UUID_A1}@Eagle, "
                         f"2026-10-01T05:00:00Z, PR #9 into opensoft/repoE main")

    REGISTER_TEXT = "\n".join([
        "# LANES.md — the import's fixture register",
        "",
        "| lane | session id | workstation / env / user | started (UTC) | objects owned | handoff path | state |",
        "|---|---|---|---|---|---|---|",
        _row("repoA-1", f"`{UUID_A1}`", "PAUSED · 2026-10-01T01:00:00Z · parked for the night"),
        _row("repoA-2", f"`{UUID_A2}`", "LIVE · 2026-10-01T02:00:00Z · the operator lane"),
        _row("repoC-1", f"`{UUID_C1}`", "ENDED · 2026-09-01T00:00:00Z · a row with no log",
             started="2026-09-01"),
        _row("repoD-1", f"`{UUID_D1}`", "LIVE · 2026-10-02T00:00:00Z · its log is RepoD-1.md"),
        _row("repoW-1", f"`{UUID_W1}`", "LIVE · 2026-10-02T00:00:00Z · its log has WORD lines"),
        "",
        f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T02:00:00Z, PR #7 into opensoft/repoA main",
        f"LANDED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T02:05:00Z, PR #7 into opensoft/repoA main → abc1234",
        f"HOLD — lane repoA-2 (Eagle), window w, 2026-10-01T03:00:00Z: opensoft/repoA main {TIP_A} for a frozen window",
        f"HOLD (refresh) — lane repoA-2 (Eagle), window w, 2026-10-01T03:10:00Z: opensoft/repoA main {TIP_A}",
        "HOLD (run id) — lane repoA-2 (Eagle), window w, 2026-10-01T03:11:00Z: opensoft/repoA main run 4242",
        f"HOLD RELEASED — lane repoA-2 (Eagle), 2026-10-01T03:30:00Z: opensoft/repoA main {TIP_A}",
        f"HOLD — lane repoA-1 (Eagle), window w, 2026-10-01T03:35:00Z: opensoft/repoB main {TIP_A} for a check",
        "HOLD WITHDRAWN — lane repoA-1 (Eagle), 2026-10-01T03:40:00Z: opensoft/repoB main",
        f"HOLD — lane repoA-1 (Eagle), window w, 2026-10-01T03:42:00Z: opensoft/repoX main {TIP_A} for a check",
        "HOLD EXPIRED — lane repoA-1 (Eagle), 2026-10-01T03:45:00Z: opensoft/repoX main",
        "QUEUED-HOLD — lane repoA-2 (Eagle), 2026-10-01T03:50:00Z: opensoft/repoB main",
        f"LANDING WITHDRAWN — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T03:55:00Z, PR #8 into opensoft/repoA main",
        f"LANDING — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T04:00:00Z, PR #9 into opensoft/repoE main",
        f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T04:01:00Z, PR #10 into OpenSoft/RepoE main",
        f"LANDED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T04:05:00Z, PR #10 into OpenSoft/RepoE main → def5678",
        TAKE_LINES["hold-no-utc"],
        # ITS HOLDER RELEASES IT (lane 3's B16 post, #165 6814260122): lane
        # 1's open-HOLD check (T116 follow-up 6, line R's merge21f6) counts a
        # HOLD with no readable time as open (lane 3, #165 6813195977), and a
        # first-form cutover over an open one refuses with 2. So the operator
        # lane releases this dead take, as T211n's CutoverRegister does.
        f"HOLD RELEASED — lane repoA-2 (Eagle), 2026-10-01T05:20:00Z: opensoft/repoH main {TIP_A}",
        TAKE_LINES["landing-no-utc"],
        TAKE_LINES["bad-stamp"],
        EXPIRED_NO_HOLDER,
        "",
    ])

    #: `WORD` lines whose UTC carries milliseconds (Q4(d)(i)): kept verbatim, and
    #: flagged.
    WORD_LINES = [
        f"NOTED — lane repoW-1, session {UUID_W1}@Eagle, 2026-10-02T00:10:00.123Z, lane:repoW-1 — a stamp with milliseconds",
        f"NOTED — lane repoW-1, session {UUID_W1}@Eagle, 2026-10-02T00:11:00.456Z, lane:repoW-1 — another",
    ]

    #: C's files, before the `lanes-edit.sh` write on top. `lanes/repos.tsv` and
    #: `lanes/log/README.md` are outside the render set (Q18 (A)).
    SEED = {
        "lanes/LANES.md": REGISTER_TEXT,
        "lanes/log/README.md": "# the object logs\n",
        "lanes/repos.tsv": "# alias\towner/repo\nrepoE\topensoft/repoE\n",
        "lanes/log/repoA-1.md": "\n".join([
            "# lane repoA-1 — object log (lane-collision-protocol Amendment 7)",
            f"STARTED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:00:00Z, lane:repoA-1 → home opensoft/repoA; dir /work/repoA1; profile team-01a",
            f"OPENED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T01:30:00Z, opensoft/repoA#7",
            ""]),
        "lanes/log/repoA-2.md": "\n".join([
            "# lane repoA-2 — object log (lane-collision-protocol Amendment 7)",
            f"STARTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T02:00:00Z, lane:repoA-2 → home opensoft/repoA; dir /work/repoA2; profile team-01b",
            ""]),
        "lanes/log/repoB-1.md": "\n".join([
            "# lane repoB-1 — object log (lane-collision-protocol Amendment 7)",
            f"STARTED — lane repoB-1, session {UUID_B1}@Eagle, 2026-10-01T00:30:00Z, lane:repoB-1 → home opensoft/repoB; dir /work/repoB; profile team-02a",
            ""]),
        "lanes/log/RepoD-1.md": "\n".join([
            "# lane repoD-1 — object log (lane-collision-protocol Amendment 7)",
            f"STARTED — lane repoD-1, session {UUID_D1}@Eagle, 2026-10-02T00:00:00Z, lane:repoD-1 → home opensoft/repoD; dir /work/repoD",
            "a line no parser reads, in a log whose name differs from its lane's in case",
            ""]),
        "lanes/log/repoW-1.md": "\n".join([
            "# lane repoW-1 — object log (lane-collision-protocol Amendment 7)",
            f"STARTED — lane repoW-1, session {UUID_W1}@Eagle, 2026-10-02T00:00:00Z, lane:repoW-1 → home opensoft/repoW; dir /work/repoW",
            *WORD_LINES,
            ""]),
        "lanes/aliases.tsv": "# old\tnew\tutc\nrepoOld-1\trepoA-2\t2026-09-30T00:00:00Z\n",
        "lanes/archive/LANES-retired.md": "\n".join([
            "# retired rows (Amendment 19(d))", "",
            _row("repoZ-1", f"`{UUID_Z1}`", "RETIRED · 2026-09-02T00:00:00Z · retired"),
            ""]),
    }
    return SEED

TEST7_SEED: Dict[str, str] = _test7_seed()
#: The operator lane the import runs as, and its files-mode write on top of
#: the seed, so C's tip is bytes `lanes-edit.sh` wrote (T211's `OPERATOR` and
#: `FixtureRegister`).
TEST7_OPERATOR = "repoA-2"
TEST7_NOTE = ("log", "NOTED", f"lane:{TEST7_OPERATOR}", "the import's fixture, at C")

#: What the register's commands never inherit from the run: the lane
#: tooling's, the agents', the configuration's and libpq's variables.
_REGISTER_ENV_DROPPED = ("LANES_", "CLAUDE_", "WORKBENCHES_", "TMUX", "XDG_", "PG",
                         "AGENT_PROTOCOL_ROOT", "PROJECTS_")


def _without_indexer(path: str) -> str:
    """`path` without any directory that holds a `lanes-index`: an installed
    indexer is never what the fixture runs."""
    return os.pathsep.join(part for part in path.split(os.pathsep)
                           if part and not os.path.exists(os.path.join(part, "lanes-index")))


class ImportedRegister:
    """TEST 7'S FIXTURE REGISTER ON A REPOSITORY OF THE FIXTURE'S OWN (T227b),
    built in `root` as T211's `FixtureRegister` builds C, from nothing of the
    person's: a bare origin, `origin.git`; the operator lane's checkout, a
    clone of it at `home/projects/wip`, which `LANES_REPO` names (D24, Y:653);
    W, `ro/wip`, a view of that clone, which `workspace.yaml` names, so
    `LANES_REPO` is never W; `TEST7_SEED` committed and pushed by git alone;
    then the operator lane's `lanes-edit.sh log NOTED`, committed and pushed
    by the files-mode verb. `c` is origin's tip then, C.

    `import_at` runs lane 1's `lanes-index import --at <C>` (T115) as the
    operator lane, `LANES_LANE=repoA-2`, from that checkout, with origin
    fetched first, through a configuration naming one database of the
    cluster by its socket. The cases that clone `tmpl_imported` read this
    repository only; a case that pushes or edits works on a copy of its
    own."""

    def __init__(self, root: Path, bindir: Path) -> None:
        self.root, self.bindir = root, bindir
        self.home = root / "home"
        self.agents = self.home / ".agents"
        self.origin = root / "origin.git"
        self.wip = self.home / "projects" / "wip"
        self.ws = root / "ro" / "wip"
        self.fakebin, self.conf = root / "fakebin", root / "conf"
        for directory in (self.agents, self.fakebin, self.conf, root / "state", root / "config",
                          root / "tmp"):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        (self.fakebin / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (self.fakebin / "tmux").chmod(0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith(_REGISTER_ENV_DROPPED)}
        env.update(
            HOME=str(self.home), AGENT_PROTOCOL_ROOT=str(self.agents), TMPDIR=str(root / "tmp"),
            XDG_STATE_HOME=str(root / "state"), XDG_CONFIG_HOME=str(root / "config"),
            CLAUDE_CONFIG_DIR=str(self.home / ".claude"), LANES_WORKSTATION="Eagle",
            LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none",
            LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1", LANES_EDIT=str(LANES_EDIT),
            GIT_AUTHOR_NAME="lanes-index tests", GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_NAME="lanes-index tests", GIT_COMMITTER_EMAIL="test@example.invalid",
            PATH=os.pathsep.join([str(self.fakebin), _engine_first(
                bindir, _without_indexer(env.get("PATH", os.defpath)))]))
        self.env = env
        self._run_ok(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)])
        self._run_ok(["git", "clone", "-q", str(self.origin), str(self.wip)])
        for path, text in TEST7_SEED.items():
            sha = self.git("hash-object", "-w", "--stdin", data=text.encode("utf-8"))
            self.git("-c", "core.ignorecase=false", "update-index", "--add", "--cacheinfo",
                     f"100644,{sha},{path}")
        self.git("-c", "core.ignorecase=false", "commit", "-q", "-m", "seed the register")
        self.git("push", "-q", "origin", "main")
        self.git("-c", "core.ignorecase=false", "checkout", "-q", "-f", "HEAD")
        self.ws.mkdir(parents=True)
        (self.ws / ".git").write_text(f"gitdir: {os.path.realpath(self.wip / '.git')}\n",
                                      encoding="utf-8")
        (self.ws / "lanes").symlink_to(self.wip / "lanes")
        (self.agents / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.ws}\n", encoding="utf-8")
        self.env["LANES_REPO"] = str(self.wip)
        self._run_ok(["bash", str(LANES_EDIT), *TEST7_NOTE], LANES_LANE=TEST7_OPERATOR)
        self.c = self.git("rev-parse", "origin/main")

    def run(self, argv: List[str], cwd: Optional[Path] = None, timeout: float = 120,
            **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(argv, cwd=str(cwd or self.root), env=dict(self.env, **env),
                              stdin=DEVNULL, capture_output=True, text=True, timeout=timeout,
                              check=False)

    def _run_ok(self, argv: List[str], **env: str) -> str:
        proc = self.run(argv, **env)
        if proc.returncode != 0:
            raise ClusterError(f"{' '.join(argv[:3])} exited {proc.returncode} building test 7's "
                               f"fixture register: {_tail(proc)}")
        return proc.stdout.strip()

    def git(self, *args: str, data: Optional[bytes] = None) -> str:
        """git in the operator lane's checkout: its stdout, stripped."""
        proc = subprocess.run(["git", *args], cwd=str(self.wip), env=self.env, input=data,
                              capture_output=True, timeout=120, check=False)
        if proc.returncode != 0:
            raise ClusterError(f"git {' '.join(args[:2])} exited {proc.returncode} building test "
                               f"7's fixture register: "
                               f"{proc.stderr.decode('utf-8', 'replace').strip()[-400:]}")
        return proc.stdout.decode("utf-8", "replace").strip()

    def configuration(self, cluster: "Cluster", database: str, user: str) -> Path:
        """The operator's 0600 configuration, outside every work tree:
        `mode=index`, `register_url=` as `user` and `reader_url=` as the
        fixture's reader (or `user` without logins) on the cluster's socket,
        each with a password file, the switch's label and the schema."""
        def passfile(login: str) -> Path:
            if login in cluster.passwords:
                return cluster.passfile(login)
            empty = self.conf / "empty.pgpass"
            empty.write_text("", encoding="utf-8")
            empty.chmod(0o600)
            return empty
        reader = FX_READER if FX_READER in cluster.passwords else user
        db = Database(cluster, database)
        path = self.conf / "lanes-index.conf"
        path.write_text("\n".join([
            "mode=index", f"register_url={db.url(user)}", f"register_passfile={passfile(user)}",
            f"reader_url={db.url(reader)}", f"reader_passfile={passfile(reader)}",
            f"register_label={cluster.label}", "register_schema=lanes_register", ""]),
            encoding="utf-8")
        path.chmod(0o600)
        return path

    def import_at(self, cluster: "Cluster", database: str,
                  user: str = FX_WRITER) -> subprocess.CompletedProcess:
        """`lanes-index import --at <C>` into `database`, as the operator lane
        through its checkout, as `user`."""
        config = self.configuration(cluster, database, user)
        return self.run([sys.executable, str(LANES_INDEX), "import", "--at", self.c],
                        cwd=self.wip, timeout=400, LANES_INDEX_CONFIG=str(config),
                        LANES_LANE=TEST7_OPERATOR)


# ------------------------------------------------------------ pytest
def pytest_configure(config) -> None:
    if required() and probe().problem:
        raise pytest.UsageError(f"{ENV_REQUIRE}=1, so the real-engine tests must run, and they "
                                f"cannot - this run is refused rather than let them skip: "
                                f"{probe().problem}")


def pytest_runtest_logreport(report) -> None:
    if report.skipped and SKIP_TAG in str(report.longrepr):
        _SKIPPED.append(report.nodeid)


def pytest_terminal_summary(terminalreporter) -> None:
    """LOUD, where -q cannot hide it: the skips, where the binaries were found
    whenever they were looked for, and anything a killed session left."""
    if _SKIPPED:
        terminalreporter.write_sep("!", f"{len(_SKIPPED)} real-engine test(s) SKIPPED", yellow=True)
        terminalreporter.write_line(probe().problem or "")
    elif _PROBE is not None and _PROBE.problem is None:
        terminalreporter.write_line(f"real-engine: {_PROBE.found()}")
    if _SWEPT:
        terminalreporter.write_line(f"real-engine: removed {len(_SWEPT)} cluster(s) a killed "
                                    f"session left: {', '.join(_SWEPT)}")
    if _DATACL:
        terminalreporter.write_line(f"real-engine: a clone's datacl before section 1.4's two "
                                    f"statements (open point 12): {_DATACL[0]}")
    for why in _IMPORTED:
        terminalreporter.write_line(f"real-engine: no {IMPORTED}, so the cases that clone it "
                                    f"fail: {why}")
    for what in _IMPORTED_AT:
        terminalreporter.write_line(f"real-engine: {IMPORTED} holds {what}")


def _started(found: Probe, template_sql, imported: bool = False) -> Cluster:
    cluster = Cluster(found.bindir, template_sql, imported)
    try:
        cluster.start()
    except (ClusterError, OSError, subprocess.SubprocessError) as exc:
        cluster.destroy()
        pytest.fail(f"{SKIP_TAG} is at {found.bindir} ({found.how}), and its cluster did not "
                    f"start: {exc}", pytrace=False)
    return cluster


@_fixture(scope="session")
def pg_engine() -> Probe:
    """The binaries every cluster runs: a skip without them, or under the
    switch a failure (the run was refused already, so this is a guard)."""
    found = probe()
    if found.problem:
        if required():
            pytest.fail(found.problem, pytrace=False)
        pytest.skip(found.problem)
    return found


@_fixture(scope="session")
def pg_template_sql():
    """How `tmpl` is built (T227): P8's bootstrap, `lanes-index bootstrap
    --no-passwords` through the admin service, which makes the schema, the
    roles and their GRANTs. A module may override it with `Bootstrap(sql)`,
    to run its SQL after the bootstrap, or with plain SQL for an empty
    `tmpl`."""
    return Bootstrap()


@_fixture(scope="session")
def pg_cluster(pg_engine, pg_template_sql):
    cluster = _started(pg_engine, pg_template_sql, imported=True)
    patch = pytest.MonkeyPatch()
    patch.setenv("PATH", _engine_first(pg_engine.bindir, os.environ.get("PATH", os.defpath)))
    try:
        yield cluster
    finally:
        patch.undo()
        cluster.destroy()


@_fixture()
def pg(pg_cluster):
    name = pg_cluster.new_database()
    yield Database(pg_cluster, name)
    pg_cluster.drop_database(name)


@_fixture()
def pg_imported(pg_cluster):
    """One database per test cloned from `tmpl_imported` (T227b), test 7's
    register at seq 0 and the switch at `files` with the marker `absent`,
    with section 1.4's two statements, and dropped at the end. Where the
    session cluster has no `tmpl_imported`, the case fails at its setup,
    naming why. `pg_cluster.imported_register` is the repository it was
    imported from."""
    if pg_cluster.imported_register is None:
        pytest.fail(f"no {IMPORTED} on the session cluster, so this case cannot clone it: "
                    f"{pg_cluster.imported_problem}", pytrace=False)
    name = pg_cluster.new_database(template=IMPORTED)
    yield Database(pg_cluster, name)
    pg_cluster.drop_database(name)


@_fixture()
def stoppable_cluster(pg_engine, pg_template_sql):
    """A cluster of the test's own, on the same `Cluster` class: `stop()` and
    `start_again()`, and its own template."""
    cluster = _started(pg_engine, pg_template_sql)
    patch = pytest.MonkeyPatch()
    patch.setenv("PATH", _engine_first(pg_engine.bindir, os.environ.get("PATH", os.defpath)))
    try:
        yield cluster
    finally:
        patch.undo()
        cluster.destroy()


# ------------------------------------------------------------ the smoke
def _select_1(cluster: Cluster, dbname: str = "postgres") -> None:
    said = cluster.psql("SELECT 1;", dbname=dbname).stdout.strip()
    if said != "1":
        raise ClusterError(f"SELECT 1 on {dbname} answered {said!r}")


def _smoke_session(found: Probe) -> str:
    cluster = Cluster(found.bindir)
    try:
        cluster.start()
        name = cluster.new_database()
        _select_1(cluster, name)
        cluster.drop_database(name)
        return (f"{name} cloned from the empty {TEMPLATE} in {cluster.root}, and SELECT 1 "
                f"answered 1; started in {cluster.timings['start']:.2f} s")
    finally:
        cluster.destroy()


def _smoke_stoppable(found: Probe) -> str:
    cluster = Cluster(found.bindir)
    try:
        cluster.start()
        first = cluster.proc.pid
        cluster.stop()
        cluster.start_again()
        _select_1(cluster)
        return (f"postmaster {first} stopped by SIGINT, {cluster.proc.pid} started again on "
                f"{cluster.root}, and SELECT 1 answered 1")
    finally:
        cluster.destroy()


SMOKES = {"session": _smoke_session, "stoppable": _smoke_stoppable}


def main(argv: List[str]) -> int:
    """`--smoke <name>…`: 0 when each passes, 1 when one fails, 2 for a usage error."""
    if len(argv) < 2 or argv[0] != "--smoke":
        print(f"usage: python3 -I -B tests/pgcluster.py --smoke <{'|'.join(SMOKES)}>...",
              file=sys.stderr)
        return 2
    unknown = [name for name in argv[1:] if name not in SMOKES]
    if unknown:
        print(f"pgcluster: no smoke named {', '.join(unknown)}; the smokes are "
              f"{', '.join(SMOKES)}", file=sys.stderr)
        return 2
    found = Probe()
    if found.problem:
        print(f"pgcluster: FAIL: {found.problem}", file=sys.stderr)
        return 1
    print(f"pgcluster: {found.found()}")
    failed = 0
    for name in argv[1:]:
        try:
            said = SMOKES[name](found)
        except (ClusterError, OSError, subprocess.SubprocessError) as exc:
            print(f"pgcluster: smoke {name}: FAIL: {exc}", file=sys.stderr)
            failed += 1
        else:
            print(f"pgcluster: smoke {name}: ok: {said}")
    for root in _SWEPT:
        print(f"pgcluster: removed {root}, which a killed session left")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
