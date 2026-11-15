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
  * `pg_template_sql`, session-scoped and overridable: the SQL that builds the
    template's schema, empty until the bootstrap lands (T227);
  * `pg_cluster`, session-scoped: the session's cluster, with the template
    `tmpl` built, then closed to connections;
  * `pg`, one database per test, `CREATE DATABASE t_<n> TEMPLATE tmpl`, and
    dropped `WITH (FORCE)` at its teardown;
  * `stoppable_cluster`, a cluster of the test's own, built like the
    session's, for the tests that stop the database: `stop()` is a fast
    shutdown, SIGINT and a wait, and `start_again()` starts it on the same
    data and socket directories.

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

    def __init__(self, bindir: Path, template_sql: str = "") -> None:
        self.bindir, self.template_sql = bindir, template_sql
        self.root: Optional[Path] = None
        self.proc: Optional[subprocess.Popen] = None
        self.count, self.timings = 0, {}

    def tool(self, name: str) -> str:
        return str(self.bindir / name)

    def server_env(self) -> dict:
        env = _without_pg()
        env.update(LC_ALL="C", TZ="UTC", PATH=_engine_first(self.bindir, env.get("PATH", os.defpath)))
        return env

    def psql(self, sql: str, dbname: str = "postgres", user: str = SUPERUSER,
             check: bool = True, appname: str = "pytest") -> subprocess.CompletedProcess:
        proc = subprocess.run([self.tool("psql"), "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                               "-f", "-"], input=sql, capture_output=True, text=True, timeout=120,
                              env=_client_env(self.root, user, dbname, appname, self.bindir),
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
        self.psql(f"CREATE DATABASE {TEMPLATE};")
        if self.template_sql.strip():
            self.psql(self.template_sql, dbname=TEMPLATE)
        self.psql(f"ALTER DATABASE {TEMPLATE} WITH IS_TEMPLATE true ALLOW_CONNECTIONS false;")
        t4 = time.monotonic()
        self.timings = {"initdb": t2 - t1, "ready": t3 - t2, "template": t4 - t3, "start": t4 - t0}

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

    def new_database(self) -> str:
        self.count += 1
        name = f"t_{self.count}"
        self.psql(f"CREATE DATABASE {name} TEMPLATE {TEMPLATE};")
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


def _started(found: Probe, template_sql: str) -> Cluster:
    cluster = Cluster(found.bindir, template_sql)
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
def pg_template_sql() -> str:
    """The template's schema. Empty until L1-A7 lands: T227 overrides this
    with the bootstrap's roles, migrations and grants."""
    return ""


@_fixture(scope="session")
def pg_cluster(pg_engine, pg_template_sql):
    cluster = _started(pg_engine, pg_template_sql)
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
