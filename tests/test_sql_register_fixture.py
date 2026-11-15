# SPDX-License-Identifier: Apache-2.0
"""The real-engine fixture's switch, `OPENREPOTOOLS_REQUIRE_PG` (#165, L2-0b).

THE TEST PLAN'S SECTION 3.3, ITS FOUR CASES. `tests/pgcluster.py` gives the
tests that need a real PostgreSQL 16 their cluster, and `tests/conftest.py`
registers it from its `pytest_configure`. The switch decides what a missing
engine is:

  * unset or `0`, a SKIP of every real-engine test, whose reason names
    `PG_BIN` and the package `postgresql-16`, loud even under `-q`;
  * `1`, as CI sets it, a REFUSAL of the whole run before any test starts:
    pytest's own `UsageError`, exit 4, even where the run selects no
    real-engine test (the refusal is eager);
  * anything else, a refusal too, as `OPENREPOTOOLS_COMPOSED` refuses a
    value that is neither.

EACH CASE RUNS A CHILD PYTEST, since a refusal ends the session that makes it.
The child is `python -m pytest` on this suite's own `conftest.py`, with no
`OPENREPOTOOLS_*`, `PG*` or `PYTEST_ADDOPTS` of the outer run, and with only
what the case sets. Its real-engine test is a PROBE written into the case's
own temporary directory, which asks for `pg`, one database cloned from the
session's template: the suite holds no such test of its own until the
template's tasks land, and a case must not wait for one.

A REAL-ENGINE TEST IS ONE WHOSE FIXTURE CLOSURE HOLDS `pg_engine`, the
session fixture through which every cluster of `tests/pgcluster.py` finds its
binaries, or skips, or fails. A test asks for `pg`, `pg_cluster`,
`stoppable_cluster` or a cluster built on them, and the closure pytest
computes from their definitions reaches `pg_engine`. So the last case reads
pytest's public `fixturenames`, and a cluster fixture added later is held to
the rule by depending on `pg_engine`, as each one must to find the binaries.

Until `tests/conftest.py` registers the plugin, each case FAILS on its own
assertion: the probe's `pg` is a fixture nobody defines, so the child errors
where it should refuse or skip, and the filter's check cannot see the probe.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pytest

from conftest import REPO

#: The variable, as `tests/pgcluster.py` and `tests.yml` spell it.
SWITCH = "OPENREPOTOOLS_REQUIRE_PG"

#: THIS MODULE AND ITS SUITE: the child loads the `conftest.py` beside it.
THIS = Path(__file__).resolve()
SUITE = THIS.parent

#: The fixture every cluster finds its binaries through.
ENGINE_FIXTURE = "pg_engine"

#: THE `guard-launch-mode` JOB'S FILTER, as `tests.yml` runs it:
#: `bash tests/run.sh -k '<filter>'`. The job is the launch contract's own,
#: and a real-engine test it selected would turn it into a database job.
LAUNCH_JOB_FILTER = "guard_launch_mode or repo_hygiene"

#: THE PROBE: one real-engine test, written by this module into a case's
#: temporary directory. Its function's name holds the launch job's first word,
#: so that job's filter selects it, and its module's name holds `PROBE_WORD`,
#: which selects it alone where a case runs it.
PROBE_MODULE = "test_engine_probe.py"
PROBE_TEST = "test_guard_launch_mode_sees_this_real_engine_probe"
PROBE_WORD = "engine_probe"
PROBE_SOURCE = f'''# A real-engine test, written by tests/test_sql_register_fixture.py.


def {PROBE_TEST}(pg):
    assert pg.name
'''

#: A PLUGIN FOR THE CHILD'S COLLECTION, loaded by `-p`: every item the
#: collection keeps, its path, and whether its fixture closure holds
#: `ENGINE_FIXTURE`, one JSON line each, in the file `$ENGINE_REPORT` names.
REPORTER_MODULE = "engine_report"
REPORTER_SOURCE = f'''import json
import os


def pytest_collection_finish(session):
    with open(os.environ["ENGINE_REPORT"], "w", encoding="utf-8") as report:
        for item in session.items:
            names = getattr(item, "fixturenames", ())
            report.write(json.dumps({{"nodeid": item.nodeid, "path": str(item.path),
                                     "engine": {ENGINE_FIXTURE!r} in names}}) + "\\n")
'''


def shown(proc: subprocess.CompletedProcess) -> str:
    return (f"exit {proc.returncode}\n--- stdout ---\n{proc.stdout[-4000:]}"
            f"\n--- stderr ---\n{proc.stderr[-4000:]}")


def write_probe(tmp_path: Path) -> Path:
    directory = tmp_path / "probe"
    directory.mkdir()
    probe = directory / PROBE_MODULE
    probe.write_text(PROBE_SOURCE, encoding="utf-8")
    return probe


def no_engine(tmp_path: Path) -> Path:
    """An empty directory for `PG_BIN`: a named `PG_BIN` is final, so it is a
    missing engine on a host that has one, CI's runners among them."""
    directory = tmp_path / "no-engine"
    directory.mkdir()
    return directory


def child(tmp_path: Path, args: list, switch=None, pg_bin=None,
          extra_env=None) -> subprocess.CompletedProcess:
    """`python -m pytest -q` on `args`, from the case's temporary directory,
    with `switch` and `pg_bin` as the only switch and `PG_BIN` it sees."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("OPENREPOTOOLS_", "PG"))
           and key not in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if switch is not None:
        env[SWITCH] = switch
    if pg_bin is not None:
        env["PG_BIN"] = str(pg_bin)
    env.update(extra_env or {})
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               f"--basetemp={tmp_path / 'child-basetemp'}",
               f"--rootdir={SUITE.parent}", *args]
    return subprocess.run(command, cwd=str(tmp_path), env=env,
                          capture_output=True, text=True, timeout=900,
                          check=False)


def probe_run(tmp_path: Path, probe: Path, *options: str, **kwargs):
    """The probe alone: this module is collected beside it, so the child
    loads this suite's `conftest.py`, and `-k` keeps only the probe."""
    return child(tmp_path, [*options, "-k", PROBE_WORD, str(THIS), str(probe)],
                 **kwargs)


def test_the_engine_switch_turns_a_missing_engine_into_a_failure(tmp_path):
    """`OPENREPOTOOLS_REQUIRE_PG=1` with `PG_BIN` naming an empty directory:
    pytest exits 4 before the probe runs, and says why, naming the switch and
    the `PG_BIN` it could not use (section 3.3; the probe's b1, b8 and b9).
    Exit 4 alone is not enough: a missing file is a usage error too."""
    empty = no_engine(tmp_path)
    proc = probe_run(tmp_path, write_probe(tmp_path), switch="1", pg_bin=empty)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 4, (
        f"{SWITCH}=1 with no engine must refuse the run, exit 4:\n{shown(proc)}")
    assert f"{SWITCH}=1" in output and f"PG_BIN={empty}" in output, (
        f"the refusal names neither the switch nor the PG_BIN it could not "
        f"use:\n{shown(proc)}")
    assert PROBE_TEST not in output, f"the probe ran:\n{shown(proc)}"


def test_without_the_switch_a_missing_engine_skips_naming_pg_bin_and_postgresql_16(
        tmp_path):
    """The switch unset, and at `0`, with `PG_BIN` naming an empty directory:
    the probe SKIPS, the run exits 0, and the skip's reason names `PG_BIN`
    and the package `postgresql-16` (the probe's a1 and b10). The child runs
    `-q` with no `-rs`, as the `tests` job does, and its output names both
    too, since a skip a person cannot read is a skip nobody audits."""
    empty = no_engine(tmp_path)
    probe = write_probe(tmp_path)
    for switch in (None, "0"):
        label = "unset" if switch is None else f"at {switch}"
        junit = tmp_path / f"probe-{label.replace(' ', '-')}.xml"
        proc = probe_run(tmp_path, probe, f"--junitxml={junit}",
                         switch=switch, pg_bin=empty)
        assert proc.returncode == 0, (
            f"with the switch {label}, a missing engine must skip, exit 0:\n"
            f"{shown(proc)}")
        cases = {case.get("name"): case for case in
                 ElementTree.parse(str(junit)).getroot().iter("testcase")}
        assert PROBE_TEST in cases, f"the probe did not run:\n{shown(proc)}"
        skipped = cases[PROBE_TEST].find("skipped")
        assert skipped is not None, (
            f"with the switch {label}, the probe did not skip:\n{shown(proc)}")
        reason = (skipped.get("message") or "") + (skipped.text or "")
        for word in ("PG_BIN", "postgresql-16"):
            assert word in reason, (
                f"with the switch {label}, the skip's reason names no "
                f"{word}: {reason}")
            assert word in proc.stdout, (
                f"with the switch {label}, the -q output names no {word}, so "
                f"the tests job's log would not show why:\n{shown(proc)}")


def test_the_engine_switch_refuses_a_value_that_is_not_0_or_1(tmp_path):
    """A value that is neither `1` nor `0` (nor unset) is pytest's usage
    error, exit 4, naming the variable and the value, before any engine is
    looked for (the probe's b3). `true` and `yes` are what a person might
    write; neither is `1`."""
    probe = write_probe(tmp_path)
    for value in ("2", "yes", "true"):
        proc = probe_run(tmp_path, probe, switch=value)
        output = proc.stdout + proc.stderr
        assert proc.returncode == 4, (
            f"{SWITCH}={value!r} must be refused, exit 4:\n{shown(proc)}")
        assert f"{SWITCH}={value!r}" in output, (
            f"the refusal of {SWITCH}={value!r} does not name it:\n"
            f"{shown(proc)}")
        assert PROBE_TEST not in output, f"the probe ran:\n{shown(proc)}"


def test_no_real_engine_test_is_selected_by_the_launch_jobs_filter(tmp_path):
    """L2-0b's hygiene rule: the `guard-launch-mode` job's `-k` selects no
    real-engine test. The child collects this whole suite as the job does,
    with the job's own filter, which pytest matches against each test's
    function, class, module and parametrize id, case-insensitively, so every
    test any later task adds is held to it. The probe, which the filter
    selects on purpose, shows that the check sees a real-engine test; it
    cannot, until the plugin defines `pg`."""
    workflow = (REPO / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8")
    assert f"bash tests/run.sh -k '{LAUNCH_JOB_FILTER}'" in workflow, (
        f"tests.yml no longer runs `bash tests/run.sh -k "
        f"'{LAUNCH_JOB_FILTER}'`: this case must follow the job's filter")
    probe = write_probe(tmp_path)
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / f"{REPORTER_MODULE}.py").write_text(REPORTER_SOURCE,
                                                   encoding="utf-8")
    report = tmp_path / "selected.jsonl"
    path = os.pathsep.join([str(plugins), *filter(None, [os.environ.get(
        "PYTHONPATH")])])
    proc = child(tmp_path, ["--collect-only", "-p", REPORTER_MODULE,
                            "-k", LAUNCH_JOB_FILTER, str(SUITE), str(probe)],
                 switch="0",
                 extra_env={"ENGINE_REPORT": str(report), "PYTHONPATH": path})
    assert proc.returncode == 0 and report.is_file(), shown(proc)
    rows = [json.loads(line) for line in
            report.read_text(encoding="utf-8").splitlines()]
    probes = [row for row in rows if Path(row["path"]).resolve() == probe.resolve()]
    assert probes and all(row["engine"] for row in probes), (
        f"the filter selected the probe, a test that asks for `pg`, and its "
        f"fixture closure holds no `{ENGINE_FIXTURE}`: this check cannot see "
        f"a real-engine test, so it would pass whatever the suite held. "
        f"The probe's rows: {probes}")
    suite = [row for row in rows
             if Path(row["path"]).resolve().is_relative_to(SUITE)]
    assert suite, (f"the launch job's filter selects nothing in {SUITE}:\n"
                   f"{shown(proc)}")
    offenders = sorted(row["nodeid"] for row in suite if row["engine"])
    assert not offenders, (
        f"`-k '{LAUNCH_JOB_FILTER}'`, the guard-launch-mode job's filter, "
        f"selects {len(offenders)} real-engine test(s); rename each so that "
        f"no part of its id holds either word: {offenders}")


# ---------------------------------------------------------------- T229's relay
#: THE DELAYED-LOOPBACK RELAY'S OWN TEST (T229; R-P23), before the cases that
#: use it: `tests/pgcluster.py`'s `delayed_loopback(target_port, delay_s)`.
#: `[each-direction]`, `[clean-close]` and `[no-root]` run on a loopback
#: peer of the standard library, so they need no engine; `[tls-untouched]`
#: checks the bytes on such a peer, then asks for T229's TLS cluster for its
#: `verify-full` connect and query, and skips with T205's banner without one.
RELAY_DELAY = 0.2
RELAY_CASES = ["each-direction", "tls-untouched", "clean-close", "no-root"]


def _peer(handler):
    """A loopback server for one connection: `handler(conn, seen)` in a
    thread. Returns (port, thread, seen)."""
    server = socket.create_server(("127.0.0.1", 0))
    seen: dict = {}

    def run():
        try:
            conn, _ = server.accept()
            with conn:
                handler(conn, seen)
        finally:
            server.close()
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return server.getsockname()[1], thread, seen


def _read_all(sock, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            break
        data += chunk
    return data


def _relay_each_direction(relay_of):
    def handler(conn, seen):
        conn.recv(1)
        seen["up"] = time.monotonic()
        seen["sent"] = time.monotonic()
        conn.sendall(b"d")
    port, thread, seen = _peer(handler)
    with relay_of(port, RELAY_DELAY) as relay:
        with socket.create_connection(("127.0.0.1", relay.port), timeout=10) as client:
            sent = time.monotonic()
            client.sendall(b"u")
            assert client.recv(1) == b"d"
            down = time.monotonic()
        thread.join(10)
    assert seen["up"] - sent >= RELAY_DELAY, f"the first byte up came {seen['up'] - sent:.3f} s after it was sent"
    assert down - seen["sent"] >= RELAY_DELAY, f"the first byte down came {down - seen['sent']:.3f} s after it was sent"
    assert seen["up"] - sent < RELAY_DELAY + 5 and down - seen["sent"] < RELAY_DELAY + 5, seen


def _relay_tls_untouched(relay_of, request):
    up, down = os.urandom(200_000), os.urandom(100_000)

    def handler(conn, seen):
        seen["up"] = _read_all(conn, len(up))
        conn.sendall(down)
    port, thread, seen = _peer(handler)
    with relay_of(port, 0.01) as relay:
        with socket.create_connection(("127.0.0.1", relay.port), timeout=30) as client:
            client.sendall(up)
            got = _read_all(client, len(down))
        thread.join(30)
    assert seen.get("up") == up, "the bytes the relay delivered up are not the bytes it was sent"
    assert got == down, "the bytes the relay delivered down are not the bytes it was sent"
    tls = request.getfixturevalue("tls_cluster")
    with relay_of(tls.port, 0.01) as relay:
        env = dict(tls.client_env(), PGPORT=str(relay.port))
        proc = subprocess.run([tls.tool("psql"), "-X", "-A", "-t", "-c",
                               "SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()"],
                              capture_output=True, text=True, env=env, timeout=60, check=False)
    assert (proc.returncode, proc.stdout.strip()) == (0, "t"), (
        f"a verify-full connect and query through the relay: {shown(proc)}")


def _relay_clean_close(relay_of):
    for first in ("client", "peer"):
        def handler(conn, seen, first=first):
            if first == "peer":
                conn.close()
                return
            seen["eof"] = conn.recv(1)
        port, thread, seen = _peer(handler)
        with relay_of(port, RELAY_DELAY) as relay:
            client = socket.create_connection(("127.0.0.1", relay.port), timeout=10)
            if first == "client":
                client.close()
                thread.join(10)
                assert seen.get("eof") == b"", "the client's close did not reach the peer"
            else:
                assert client.recv(1) == b"", "the peer's close did not reach the client"
                client.close()
            end = time.monotonic() + 5
            while relay.sockets and time.monotonic() < end:
                time.sleep(0.05)
            assert not relay.sockets, f"[{first} first] the relay still holds {len(relay.sockets)} socket(s)"
        assert relay.alive() == [], f"[{first} first] the relay's threads outlive it: {relay.alive()}"


NO_ROOT_CHILD = """
import json, os, socket, sys, threading
sys.path.insert(0, sys.argv[1])
import pgcluster
server = socket.create_server(("127.0.0.1", 0))
def echo():
    conn, _ = server.accept()
    with conn:
        conn.sendall(conn.recv(16))
threading.Thread(target=echo, daemon=True).start()
with pgcluster.delayed_loopback(server.getsockname()[1], 0.05) as relay:
    with socket.create_connection(("127.0.0.1", relay.port), timeout=10) as client:
        client.sendall(b"no-root")
        said = client.recv(16)
# T229e: where there is no /proc, as on macOS, there is no capability set to read
status = open(sys.argv[2] + "/self/status").read() if os.path.isdir(sys.argv[2]) else ""
cap = [line.split()[1] for line in status.splitlines() if line.startswith("CapEff:")]
print(json.dumps({"uid": os.geteuid(), "cap": cap[0] if cap else None, "said": said.decode()}))
"""


def _relay_no_root():
    if os.geteuid() == 0:
        pytest.skip("[no-root] shows the relay needs no capability, and this run is root")
    import pgcluster
    proc = subprocess.run([sys.executable, "-I", "-B", "-c", NO_ROOT_CHILD, str(SUITE),
                           str(pgcluster._PROC)],
                          capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, shown(proc)
    said = json.loads(proc.stdout.strip().splitlines()[-1])
    assert said["said"] == "no-root", said
    assert said["uid"] == os.getuid(), f"the relay ran as uid {said['uid']}, not the job's {os.getuid()}"
    if said["cap"] is not None:
        assert int(said["cap"], 16) == 0, f"the relay's process holds capabilities {said['cap']}"


@pytest.mark.parametrize("case", RELAY_CASES)
def test_the_delayed_loopback_relay_delays_each_direction_and_passes_tls_through(request, case):
    """T229's relay (R-P23): `[each-direction]`, each direction's first byte
    arrives no sooner than the delay after it was sent, on a monotonic
    clock; `[tls-untouched]`, the bytes it delivers each way equal the bytes
    it was sent, and a `verify-full` connect and a query through it to the
    TLS cluster succeed (R2f-S11); `[clean-close]`, a close on either side
    closes the other, and leaves no thread or socket of the relay's;
    `[no-root]`, a process with no added capability, under the job's own
    uid, starts and uses it."""
    import pgcluster
    relay_of = getattr(pgcluster, "delayed_loopback", None)
    assert relay_of is not None, "tests/pgcluster.py has no delayed_loopback: T229 builds it"
    if case == "each-direction":
        _relay_each_direction(relay_of)
    elif case == "tls-untouched":
        _relay_tls_untouched(relay_of, request)
    elif case == "clean-close":
        _relay_clean_close(relay_of)
    else:
        _relay_no_root()


# ---------------------------------------------------------------- T229c's relay
#: THE SILENT-AFTER-STARTUP RELAY'S OWN TEST (T229c; lane 3's batch 8, "Lane
#: 2's relay: T229 builds it", #165 6780753157, and its text change 8;
#: TP:7682-7684), before the cases that connect through it: D9's F2, AT-F7's
#: silent host, the service's timer and the guard's `[2-service-down]`.
#: `tests/pgcluster.py`'s `silent_after_startup(target_port)`.
#: `[forwards-the-startup]`, `[then-nothing]` and `[holds-both-sockets]` run on
#: a loopback peer of the standard library that answers a startup as
#: PostgreSQL does on trust, so they need no engine; `[psql-on-the-socket]`
#: runs the engine's `psql` through it to the session cluster's Unix socket,
#: and skips with T205's banner without one.
SILENT_CASES = ["forwards-the-startup", "then-nothing", "holds-both-sockets", "psql-on-the-socket"]
#: How long a case waits to see that nothing arrives.
SILENT_WAIT = 1.0


def _message(kind: bytes, body: bytes) -> bytes:
    return kind + (len(body) + 4).to_bytes(4, "big") + body


#: A startup as libpq sends it (protocol 3.0), and PostgreSQL's answer on
#: trust: AuthenticationOk, a ParameterStatus, BackendKeyData, whose key here
#: ends like a ReadyForQuery's head, and ReadyForQuery (`Z`, length 5, idle).
_STARTUP_BODY = (196608).to_bytes(4, "big") + b"user\x00fx\x00database\x00fx\x00\x00"
STARTUP = (len(_STARTUP_BODY) + 4).to_bytes(4, "big") + _STARTUP_BODY
STARTUP_ANSWER = (_message(b"R", (0).to_bytes(4, "big"))
                  + _message(b"S", b"server_version\x0016.15\x00")
                  + _message(b"K", (4242).to_bytes(4, "big") + b"Z\x00\x00\x00")
                  + _message(b"Z", b"I"))
QUERY = _message(b"Q", b"SELECT 1;\x00")


def _within(sock, wait: float):
    """What reaches `sock` within `wait` seconds: None for nothing, b"" for a
    close, else the bytes."""
    sock.settimeout(wait)
    try:
        return sock.recv(65536)
    except socket.timeout:
        return None


def _startup_peer(after):
    """A loopback peer for one connection: it reads a startup, answers it,
    its ReadyForQuery 0.2 s after the rest, then runs `after(conn, seen)`."""
    def handler(conn, seen):
        seen["startup"] = _read_all(conn, len(STARTUP))
        cut = len(STARTUP_ANSWER) - 6
        conn.sendall(STARTUP_ANSWER[:cut])
        time.sleep(0.2)
        conn.sendall(STARTUP_ANSWER[cut:])
        after(conn, seen)
    return _peer(handler)


def _started(relay):
    client = socket.create_connection(("127.0.0.1", relay.port), timeout=10)
    client.sendall(STARTUP)
    return client, _read_all(client, len(STARTUP_ANSWER))


def _silent_forwards_the_startup(relay_of):
    port, thread, seen = _startup_peer(lambda conn, seen: None)
    with relay_of(port) as relay:
        assert relay.port != port, "the relay listens on its target's own port"
        client, got = _started(relay)
        with client:
            assert client.getpeername() == ("127.0.0.1", relay.port), client.getpeername()
            thread.join(10)
            assert seen.get("startup") == STARTUP, "the startup the peer read is not the one the client sent"
            assert got == STARTUP_ANSWER, (
                f"the client read {got!r}, not the peer's answer up to its ReadyForQuery")
            assert len(relay.silenced) == 1, f"one startup silenced the relay {len(relay.silenced)} time(s)"


def _silent_then_nothing(relay_of):
    def after(conn, seen):
        seen["up"] = _within(conn, SILENT_WAIT)
        conn.sendall(_message(b"N", b"SNOTICE\x00\x00"))
        seen["down"] = True
        _within(conn, SILENT_WAIT)
    port, thread, seen = _startup_peer(after)
    with relay_of(port) as relay:
        client, got = _started(relay)
        with client:
            assert got == STARTUP_ANSWER, got
            client.sendall(QUERY)
            heard = _within(client, 2 * SILENT_WAIT)
            thread.join(10)
    assert seen.get("up") is None, f"after the startup the client's query reached the peer: {seen.get('up')!r}"
    assert seen.get("down"), "the peer did not speak after the startup"
    assert heard is None, f"after the startup the peer's bytes reached the client: {heard!r}"


def _silent_holds_both_sockets(relay_of):
    def after(conn, seen):
        seen["eof"] = _within(conn, SILENT_WAIT)
    port, thread, seen = _startup_peer(after)
    with relay_of(port) as relay:
        client, got = _started(relay)
        with client:
            assert got == STARTUP_ANSWER, got
            client.shutdown(socket.SHUT_WR)
            thread.join(10)
            assert seen.get("eof") is None, (
                f"after the startup the client's close reached the peer: {seen.get('eof')!r}")
            held = _within(client, SILENT_WAIT)
            assert held is None, f"after the startup the peer's close reached the client: {held!r}"
            assert len(relay.sockets) == 2, f"the relay holds {len(relay.sockets)} socket(s), not both"
            relay.close()
            assert _within(client, 5) == b"", "the relay's close did not close the client's end"
    assert not relay.sockets and relay.alive() == [], (relay.sockets, relay.alive())


def _silent_psql_on_the_socket(relay_of, request):
    pg = request.getfixturevalue("pg")
    marker = f"silent-relay-{os.getpid()}"
    activity = (f"SELECT state || '|' || query FROM pg_stat_activity "
                f"WHERE application_name = '{marker}';")
    with relay_of(pg.port, socket_dir=pg.host) as relay:
        env = dict(pg.env(appname=marker), PGHOST="127.0.0.1", PGPORT=str(relay.port))
        psql = subprocess.Popen([pg.psql_bin, "-X", "-A", "-t", "-c", "SELECT 'through the relay'"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            row, end = "", time.monotonic() + 15
            while not row and time.monotonic() < end and psql.poll() is None:
                row = pg.psql(activity).stdout.strip()
                time.sleep(0.05)
            assert row, f"no session logged in through the relay, so the startup did not complete: {psql.poll()}"
            time.sleep(SILENT_WAIT)
            row = pg.psql(activity).stdout.strip()
            assert row == "idle|", f"the session through the silent relay is not idle with no query: {row!r}"
            assert psql.poll() is None, f"psql was answered through the silent relay: {psql.communicate()}"
            assert len(relay.silenced) == 1, relay.silenced
        finally:
            psql.kill()
            psql.communicate()


@pytest.mark.parametrize("case", SILENT_CASES)
def test_the_silent_after_startup_relay_forwards_the_startup_then_nothing_and_holds_both_sockets(
        request, case):
    """T229c's relay (lane 3's batch 8; TP:7682-7684), a relay of the
    standard library on 127.0.0.1 at a free port: `[forwards-the-startup]`,
    the client's startup and the server's answer, up to and including its
    first ReadyForQuery, arrive byte for byte; `[then-nothing]`, after it
    nothing is forwarded either way; `[holds-both-sockets]`, after it a close
    on either side reaches neither, and both ends stay open until the relay
    closes; `[psql-on-the-socket]`, the engine's `psql`, through it to the
    session cluster's Unix socket, logs in and is never answered, its
    session idle with no query."""
    import pgcluster
    relay_of = getattr(pgcluster, "silent_after_startup", None)
    assert relay_of is not None, (
        "tests/pgcluster.py has no silent_after_startup: T229 builds it (lane 3's batch 8)")
    if case == "forwards-the-startup":
        _silent_forwards_the_startup(relay_of)
    elif case == "then-nothing":
        _silent_then_nothing(relay_of)
    elif case == "holds-both-sockets":
        _silent_holds_both_sockets(relay_of)
    else:
        _silent_psql_on_the_socket(relay_of, request)


# ---------------------------------------------------------------- T229f's races
#: THE RELAYS' SHUTDOWN RACES (T229f; Codex's SHOULD 5 on f060619c,
#: opensoft/openRepoTools#165 6882190927). Each case opens its window with a
#: hook on the relay's seam, `tests/pgcluster.py`'s `_seam`, which holds one
#: of the relay's threads on an event where a concurrent `close()` meets it,
#: never with a sleep. Both relays, in front of a loopback listener of the
#: standard library that never accepts, so no engine is needed.
RACE_RELAYS = ["delayed-loopback", "silent-after-startup"]
#: The bound on each wait for a held thread to arrive, or for a relay's
#: thread to end: only a failure waits it out.
RACE_WAIT = 30.0


def _race_relay(kind: str):
    """A relay of `kind` in front of a listener that never accepts, whose
    backlog completes the relay's upstream connect: (relay, listener)."""
    import pgcluster
    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]
    if kind == "delayed-loopback":
        return pgcluster.delayed_loopback(port, 0.0), server
    return pgcluster.silent_after_startup(port), server


def _race_end(relay) -> list:
    """The relay closed once more, since a red case's `close()` may have
    stopped short, and each of its threads, found by its name, given until
    RACE_WAIT to end, so that no leak outlives its case: the names of those
    still alive."""
    try:
        relay.close(wait=0.0)
    except RuntimeError:
        pass
    prefixes = tuple(f"{kind}-{relay.port}-" for kind in RACE_RELAYS)
    end = time.monotonic() + RACE_WAIT
    while True:
        live = [t for t in threading.enumerate() if t.name.startswith(prefixes) and t.is_alive()]
        if not live or time.monotonic() >= end:
            return sorted(t.name for t in live)
        live[0].join(max(0.0, end - time.monotonic()))


@pytest.mark.parametrize("kind", RACE_RELAYS)
def test_a_relay_closed_while_it_connects_upstream_relays_nothing_and_leaves_no_thread(kind):
    """T229f (Codex's SHOULD 5 on f060619c): a client the relay has accepted,
    whose upstream connect is still under way when `close()` takes its
    snapshot, is closed, never relayed. The seam holds `_accept`, with the
    client and its upstream in hand, until `close()` has its snapshot, as a
    slow upstream connect would; when `close()` returns, no thread of the
    relay's is alive, and the client's end is closed.
    `[silent-after-startup]` passed before T229f, on its `done` flag;
    `[delayed-loopback]`, with no closing flag, registered the pair after the
    snapshot and started its readers, which `close()` never saw."""
    relay, server = _race_relay(kind)
    arrived, snapshot = threading.Event(), threading.Event()

    def hook(point, name):
        if point == "accepted":
            arrived.set()
            snapshot.wait(RACE_WAIT)
        elif point == "snapshot":
            snapshot.set()
    relay.seam = hook
    client = socket.create_connection(("127.0.0.1", relay.port), timeout=RACE_WAIT)
    try:
        assert arrived.wait(RACE_WAIT), f"[{kind}] the relay's accept never reached its seam"
        relay.close()
        left = relay.alive()
        assert left == [], f"[{kind}] close() has returned, and the relay's threads are alive: {left}"
        assert _within(client, RACE_WAIT) == b"", (
            f"[{kind}] the client accepted as close() began was not closed")
    finally:
        snapshot.set()
        client.close()
        server.close()
        _race_end(relay)


@pytest.mark.parametrize("kind", RACE_RELAYS)
def test_a_relay_closed_while_it_starts_a_thread_never_joins_one_not_yet_started(kind):
    """T229f (Codex's SHOULD 5 on f060619c): `close()` meets threads the
    relay is spawning, each listed by `_spawn` under the lock `close()`
    snapshots under, and held by the seam as `_spawn` leaves that lock:
    `[delayed-loopback]`'s two readers, each as it spawns its deliverer, and
    `[silent-after-startup]`'s acceptor as it spawns the pump.
    `close(wait=0)`, as when an earlier join has spent the deadline, joins
    each thread of its snapshot and raises nothing, and once the hold is
    released every thread of the relay's ends. Before T229f, `_spawn` started
    the thread only after it left the lock, so `close()` joined a thread not
    yet started, and `Thread.join` raised RuntimeError."""
    relay, server = _race_relay(kind)
    name, count = ("deliver", 2) if kind == "delayed-loopback" else ("pump", 1)
    arrived, release, lock, held = threading.Event(), threading.Event(), threading.Lock(), []

    def hook(point, spawned):
        if point != "listed" or spawned != name:
            return
        with lock:
            held.append(threading.current_thread().name)
            if len(held) == count:
                arrived.set()
        release.wait(RACE_WAIT)
    relay.seam = hook
    client = socket.create_connection(("127.0.0.1", relay.port), timeout=RACE_WAIT)
    raised = None
    try:
        assert arrived.wait(RACE_WAIT), f"[{kind}] the seam holds {held}, not {count} {name} spawn(s)"
        try:
            relay.close(wait=0.0)
        except RuntimeError as error:
            raised = error
        assert raised is None, (
            f"[{kind}] close() joined a thread `_spawn` had listed and not yet started: {raised!r}")
    finally:
        release.set()
        client.close()
        server.close()
        left = _race_end(relay)
    assert left == [], f"[{kind}] the relay's threads outlive it: {left}"


#: THE STALE SWEEP'S CASES (T205c). Every pid is fake, above any system's pid
#: limit, and every signal goes to a recorder through the module's seam.
SWEEP_CASES = ["no-proc", "pid-not-positive", "malformed", "does-not-stop", "reused-pid", "orphan"]
FAKE_PID = 2 ** 30 + 7


@pytest.mark.parametrize("case", SWEEP_CASES)
def test_the_stale_sweep_signals_and_removes_only_what_it_proves_is_a_dead_sessions_postmaster(
        monkeypatch, tmp_path, case):
    """T205c (Codex's BLOCKING 2 on f060619c): `sweep_stale` signals a stale
    root's postmaster only where its command line and start time prove it
    is that postmaster, never on the pidfile's word alone, and removes the
    root only where no such process is left. `[no-proc]`, no `/proc`, as on
    macOS, and the pidfile's pid alive: nothing signalled, the root kept;
    `[pid-not-positive]`, a pidfile naming -1 (every process) with no
    `/proc`: nothing signalled, kept; `[malformed]`, a pidfile whose pid does
    not parse: kept; `[does-not-stop]`, the proved postmaster outlives
    SIGQUIT and SIGKILL: kept; `[reused-pid]`, the pid held by another
    command line: nothing signalled, removed; `[orphan]`, the proved
    postmaster, ended by SIGQUIT: removed. No real process is signalled."""
    import signal

    import pgcluster
    parent = tmp_path / "parent"
    root = parent / f"{pgcluster.PREFIX}stale"
    (root / "data").mkdir(parents=True)
    (root / "owner").write_text(f"{FAKE_PID + 1} 1\n")          # the session that left it is gone
    datadir = str(root / "data")
    pid = {"pid-not-positive": "-1", "malformed": "7x"}.get(case, str(FAKE_PID))
    (root / "data" / "postmaster.pid").write_text(
        f"{pid}\n{datadir}\n0\n5432\n{root}\n\n0 0\nready\n")
    proc = tmp_path / "proc"
    if case not in ("no-proc", "pid-not-positive"):
        argv = (["/usr/bin/sleep", "600"] if case == "reused-pid"
                else ["/pg/bin/postgres", "-D", datadir, "-p", "5432"])
        (proc / str(FAKE_PID)).mkdir(parents=True)
        (proc / str(FAKE_PID) / "cmdline").write_bytes(b"".join(os.fsencode(a) + b"\0" for a in argv))
        fields = ["S"] + ["0"] * 18 + ["4242"]                    # the state, then the start time
        (proc / str(FAKE_PID) / "stat").write_text(f"{FAKE_PID} (postgres) {' '.join(fields)}\n")
    alive, sent = {FAKE_PID}, []

    def kill(target, sig):
        if sig:
            sent.append((target, signal.Signals(sig).name))
        if target not in alive:
            raise ProcessLookupError(target)
        if sig and case != "does-not-stop":
            alive.discard(target)

    monkeypatch.setattr(pgcluster, "SOCKET_PARENT", str(parent))
    monkeypatch.setattr(pgcluster, "_PROC", proc)
    monkeypatch.setattr(pgcluster, "_kill", kill)
    monkeypatch.setattr(pgcluster, "ORPHAN_WAIT", 0.05)
    swept = pgcluster.sweep_stale()
    want_sent, kept = {"does-not-stop": ([(FAKE_PID, "SIGQUIT"), (FAKE_PID, "SIGKILL")], True),
                       "reused-pid": ([], False),
                       "orphan": ([(FAKE_PID, "SIGQUIT")], False)}.get(case, ([], True))
    assert sent == want_sent, f"[{case}] the sweep signalled {sent}, not {want_sent}"
    assert root.is_dir() == kept, f"[{case}] the sweep {'removed' if kept else 'kept'} {root}"
    assert swept == ([] if kept else [str(root)]), f"[{case}] the sweep reports {swept}"


def test_the_delayed_loopback_relay_needs_no_proc_for_its_no_root_case(monkeypatch, tmp_path):
    """T229e (Codex's BLOCKING 3 on f060619c): T229's `[no-root]` case, run
    with the module's `/proc` a directory that does not exist, as on macOS,
    still starts and uses the relay under the job's own uid, and reads no
    capability set where there is none to read."""
    import pgcluster
    monkeypatch.setattr(pgcluster, "_PROC", tmp_path / "no-proc")
    _relay_no_root()


class _HeldChild:
    """A stand-in for `lanes-index login` (T228b's case): it never opens the
    pty, so the pty ends at once, and it holds its stderr open until it is
    killed. No real process: its kill closes a pipe, and signals nothing."""

    def __init__(self, argv, **_kw) -> None:
        read_end, self._write_end = os.pipe()
        self.stderr = os.fdopen(read_end, "rb")
        self.returncode = None
        self.killed = threading.Event()

    def poll(self):
        return self.returncode

    def kill(self) -> None:
        if self.returncode is None:
            self.returncode = -9
            os.close(self._write_end)
            self.killed.set()

    def wait(self, timeout=None):
        if not self.killed.wait(timeout):
            raise subprocess.TimeoutExpired("lanes-index", timeout)
        return self.returncode


def test_the_fixtures_pty_run_holds_its_deadline_when_the_child_closes_the_pty_and_lives_on(
        monkeypatch, tmp_path):
    """T228b (Codex's SHOULD 6 on f060619c): `lanes_index_tty`'s deadline
    bounds the whole call, not only its pty read. A child that ends the pty
    at once and holds stderr open is killed at the deadline, here 0.5 s, and
    the call returns its kill's status; it does not block on stderr. The
    case's own guard is 10 s; the child is a stand-in, so nothing is
    signalled."""
    import pgcluster
    held = []

    def launch(argv, **kw):
        held.append(_HeldChild(argv, **kw))
        return held[-1]

    monkeypatch.setattr(pgcluster, "_tty_popen", launch)
    monkeypatch.setattr(pgcluster, "TTY_DEADLINE", 0.5)

    class Admin:
        root = tmp_path

        @staticmethod
        def admin_env():
            return {}

    said = {}

    def call():
        t0 = time.monotonic()
        said["result"] = pgcluster.Cluster.lanes_index_tty(Admin(), ["login", "add"])
        said["took"] = time.monotonic() - t0

    caller = threading.Thread(target=call, daemon=True)
    caller.start()
    caller.join(10)
    blocked = caller.is_alive()
    if blocked:                           # the old code: free its read, so the thread ends
        held[0].kill()
        caller.join(10)
    assert not blocked, "lanes_index_tty blocked past its deadline on a child that holds stderr open"
    assert said["result"] == (-9, "", ""), said
    assert said["took"] < 5, f"lanes_index_tty took {said['took']:.1f} s on a 0.5 s deadline"
