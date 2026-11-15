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
