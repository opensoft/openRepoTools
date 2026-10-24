# SPDX-License-Identifier: Apache-2.0
"""What CI running the Python tests three-wide asks of this suite (#77, step 2).

`.github/workflows/tests.yml` runs its two test jobs as `python3 -m pytest
tests -q -n 3 --dist loadfile --no-loadscope-reorder`, with pytest-xdist pinned
(`tests/test_tests_workflow.py` holds the workflow's own lines). Four things
about this suite had to change or be proven for that, and this file is where
each is held:

1. THE SHELL SUITE STARTS FIRST. It is one test of 20 to 30 minutes in
   `tests/test_lane_helpers_suite.py`, and a worker that took it last would wait
   it out alone. `tests/conftest.py` moves that module to the front of a
   worker's collection; the flags keep the order when xdist hands work out.
2. ITS CLOCK STILL REACHES THE LOG. A worker's stdout reaches no log, so the
   wrapper leaves the table on its report and the controller prints it.
3. THE JOB'S STEP SUMMARY IS STILL WRITTEN. The suite writes it itself, to the
   file `$GITHUB_STEP_SUMMARY` names, from inside its own process.
4. THE WRAPPER'S TERM AND HANGUP RELAY WORKS IN A WORKER. It is installed only
   on the main thread, and a worker has to run its tests there.

Items 2 to 4 are proved through REAL xdist workers, `-n 1` children of this
run over a stand-in for the suite, never the 20-minute suite itself, and skip
where xdist is not installed (a local `tests/run.sh` is serial and does not
need it). Item 1's order is read from a one-worker child, where the order the
tests run in IS the order they were handed out in.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

import test_lane_helpers_suite as wrapper
from conftest import (SHELL_SUITE_TIMINGS, SHELL_SUITE_WRAPPER, WINDOWS_SKIP,
                      pytest_collection_modifyitems, shell_suite_first,
                      shell_suite_timings)

REAL_CONFTEST = Path(__file__).resolve().with_name("conftest.py")

#: A child's environment must not carry what changes how pytest WRITES or what it
#: RUNS: the colour and CI variables, `PYTEST_ADDOPTS` and the like, and the
#: variables an xdist worker sets for itself, which a child of a worker (this
#: run, under CI's `-n 3`) would otherwise inherit.
_NOT_INHERITED = ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST",
                  "PYTEST_XDIST_TESTRUNUID", "PYTEST_XDIST_WORKER",
                  "PYTEST_XDIST_WORKER_COUNT", "CI", "BUILD_NUMBER", "NO_COLOR",
                  "FORCE_COLOR")

needs_xdist = pytest.mark.skipif(
    importlib.util.find_spec("xdist") is None,
    reason="pytest-xdist is not installed (CI installs it; a local run is serial)")


def child_pytest(directory: Path, *args: str, env_extra=None, timeout=300):
    """`python3 -m pytest` over `directory`, as a child of this run, with its
    output as lines."""
    env = dict(os.environ)
    for name in _NOT_INHERITED:
        env.pop(name, None)
    env.update(PY_COLORS="0", PYTHONDONTWRITEBYTECODE="1", **(env_extra or {}))
    proc = wrapper.run_in_own_group(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        timeout=timeout, cwd=str(directory), env=env)
    return proc, (proc.stdout + proc.stderr).splitlines()


# --- 1. the shell suite starts first -------------------------------------------

def collected(*names):
    """Fake collected items: a file name and a position, in the order given."""
    return [types.SimpleNamespace(path=Path("/repo/tests") / file, label=f"{file}#{at}")
            for at, file in enumerate(names)]


def test_the_shell_suite_wrapper_goes_first_in_a_worker_and_nowhere_else():
    names = ("test_a.py", SHELL_SUITE_WRAPPER, "test_b.py", SHELL_SUITE_WRAPPER,
             "test_lane_helpers_suite_timeout.py", "test_c.py")
    items = collected(*names)
    want_first = [i.label for i in items if i.path.name == SHELL_SUITE_WRAPPER]
    want_rest = [i.label for i in items if i.path.name != SHELL_SUITE_WRAPPER]
    assert len(want_first) == 2, "the fixture is wrong: two of the six are the wrapper's"

    # An xdist worker (`workerinput` is what xdist's own `is_xdist_worker` reads):
    # the wrapper's tests first, and nothing else moves relative to anything else.
    moved = list(items)
    pytest_collection_modifyitems(types.SimpleNamespace(workerinput={}), moved)
    assert [i.label for i in moved] == want_first + want_rest
    assert [i.label for i in shell_suite_first(items)] == want_first + want_rest
    # `..._timeout.py` is another module, and stays where it was among the rest.
    assert "test_lane_helpers_suite_timeout.py#4" in want_rest

    # Anywhere else, with xdist absent or installed and not asked for, as in
    # `tests/run.sh`: the order is untouched.
    unmoved = list(items)
    pytest_collection_modifyitems(types.SimpleNamespace(), unmoved)
    assert [i.label for i in unmoved] == [i.label for i in items]


_CHILD_CONFTEST = """\
import importlib.util

spec = importlib.util.spec_from_file_location("the_real_conftest", {real!r})
real = importlib.util.module_from_spec(spec)
spec.loader.exec_module(real)
pytest_collection_modifyitems = real.pytest_collection_modifyitems
"""

#: Six tests in the biggest module, which sorts first by name and by size, and
#: two in a module with the wrapper's own file name, which is last by both.
_CHILD_TEST = """\
import os


def log(name):
    with open(os.environ["ORDER_LOG"], "a", encoding="utf-8") as out:
        out.write(name + "\\n")

"""


@needs_xdist
@pytest.mark.parametrize("flags, first", [
    pytest.param(["--no-loadscope-reorder"], SHELL_SUITE_WRAPPER,
                 id="with-no-loadscope-reorder"),
    pytest.param([], "test_a_big.py", id="without-it-the-biggest-file-is-first"),
])
def test_a_worker_is_handed_the_shell_suite_first_only_with_the_workflows_flags(
        tmp_path, flags, first):
    """xdist 3.8.0 sorts its work units by size, biggest first, unless the run
    says `--no-loadscope-reorder` (`loadscopereorder` defaults to true), which
    would hand the wrapper's small module out nearly last whatever the hook
    does. One worker runs its units in the order it is handed them, so the
    first test to run is the first unit handed out. The second case is the
    reason the first has its flag: if a later xdist changed that default, the
    pin to this one would move and this would say so."""
    (tmp_path / "conftest.py").write_text(
        _CHILD_CONFTEST.format(real=str(REAL_CONFTEST)), encoding="utf-8")
    for module, count in (("test_a_big.py", 6), (SHELL_SUITE_WRAPPER, 2)):
        body = _CHILD_TEST + "".join(
            f"def test_{n}():\n    log({module!r} + '::test_{n}')\n\n\n"
            for n in range(count))
        (tmp_path / module).write_text(body, encoding="utf-8")
    log = tmp_path / "order.log"
    proc, lines = child_pytest(tmp_path, "-n", "1", "--dist", "loadfile", *flags,
                               env_extra={"ORDER_LOG": str(log)})
    assert proc.returncode == 0, "\n".join(lines)
    ran = log.read_text(encoding="utf-8").splitlines()
    assert len(ran) == 8, ran
    assert ran[0].startswith(first), (
        f"the first test to run was {ran[0]}, not one of {first}'s:\n" + "\n".join(ran))
    # Handed out by FILE: no test of one module runs between two of another's.
    assert [name.split("::")[0] for name in ran] == sorted(
        (name.split("::")[0] for name in ran), key=lambda m: m != first), ran


# --- 2. its clock still reaches the log ----------------------------------------

def test_a_report_carries_the_clock_to_the_summary_and_only_from_a_call():
    block = "the lead line\nthe table"
    def report(when, *properties):
        return types.SimpleNamespace(when=when, user_properties=list(properties))

    stats = [report("setup", (SHELL_SUITE_TIMINGS, "x")),
             report("call", ("something-else", "y")),
             report("call", (SHELL_SUITE_TIMINGS, block)),
             report("call"),
             report("teardown", (SHELL_SUITE_TIMINGS, "z"))]
    assert shell_suite_timings(stats) == [block]
    assert shell_suite_timings([]) == []


@needs_xdist
@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None,
                    reason="the lane helpers and their suite are bash")
def test_the_clock_of_a_passing_suite_is_in_the_log_when_a_worker_ran_it(tmp_path):
    """The wrapper's test, run IN AN XDIST WORKER over a stand-in suite: the
    table and the teardown line are in the child's own output once each. With
    step 1b's `capsys.disabled()` they would have been written into the worker,
    which nobody reads, and this would find none of them."""
    proc, lines = wrapper.run_wrapper_over(tmp_path, args=("-n", "1"))
    assert proc.returncode == 0, "\n".join(lines)
    for row in ("the slow section", "the quick section", "to this table",
                "teardown: rm -rf of the sandbox took 3 s"):
        assert wrapper.lines_ending(lines, row) == 1, f"{row!r}:\n" + "\n".join(lines)
    assert wrapper.lines_ending(lines, "opensoft/openRepoTools#77):") == 2, "\n".join(lines)
    assert wrapper.lines_ending(lines, "ok   a case") == 0, "\n".join(lines)


# --- 3. the job's step summary is still written --------------------------------

@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None,
                    reason="the lane helpers and their suite are bash")
@pytest.mark.parametrize("args", [
    pytest.param((), id="serial"),
    pytest.param(("-n", "1"), marks=needs_xdist, id="in-an-xdist-worker"),
])
def test_the_suites_step_summary_survives_an_xdist_worker(tmp_path, args):
    """`$GITHUB_STEP_SUMMARY` is written by the SUITE (`step_summary` in
    `tests/test_lane_helpers.sh`), from inside its own process, to the file the
    runner names. The wrapper passes its environment through, so a worker that
    runs the wrapper hands it on: a stand-in that appends one line to that file
    leaves it there whether or not a worker ran it."""
    summary = tmp_path / "step-summary.md"
    proc, lines = wrapper.run_wrapper_over(
        tmp_path, args=args, env_extra={"GITHUB_STEP_SUMMARY": str(summary)},
        extra="printf '### Shell suite: wall time per section\\n' >> \"$GITHUB_STEP_SUMMARY\"\n")
    assert proc.returncode == 0, "\n".join(lines)
    assert summary.read_text(encoding="utf-8") == (
        "### Shell suite: wall time per section\n"), "\n".join(lines)


# --- 4. the wrapper's relay works in a worker -----------------------------------

_MAIN_THREAD_TESTS = """\
import signal
import subprocess
import threading

import test_lane_helpers_suite as wrapper


def test_the_worker_runs_its_tests_on_its_main_thread():
    assert threading.current_thread() is threading.main_thread(), (
        "an xdist worker ran this test on " + threading.current_thread().name)
    # What `signal.signal` itself needs, and so what the relay needs.
    signal.signal(signal.SIGUSR1, signal.getsignal(signal.SIGUSR1))


def test_the_wrappers_term_relay_is_installed_in_the_worker(monkeypatch):
    seen = []
    popen = subprocess.Popen

    class Spy(popen):
        def __init__(self, *args, **kwargs):
            seen.append(signal.getsignal(signal.SIGTERM))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(wrapper.subprocess, "Popen", Spy)
    wrapper.run_in_own_group(["true"], timeout=60)
    assert seen, "run_in_own_group never started its command"
    assert callable(seen[0]) and seen[0] not in (signal.SIG_DFL, signal.SIG_IGN), (
        f"no TERM relay was installed where the command started: {seen[0]!r}")
"""


@needs_xdist
@WINDOWS_SKIP
def test_an_xdist_worker_runs_its_tests_on_the_main_thread_where_the_relay_works(tmp_path):
    """`run_in_own_group` installs its TERM and HUP relay only on the main
    thread (`threading.current_thread() is threading.main_thread()`), and
    otherwise says nothing: a suite run from any other thread would be left
    running by a TERM to the worker. xdist 3.8.0's workers run their tests on
    the main thread (`workermanage.py` builds its execnet group with
    `execmodel="main_thread_only"`); this runs a real worker and asks, so a
    version or a configuration that stopped doing so is a red test here and not
    an orphaned 20-minute suite in CI."""
    (tmp_path / "test_in_a_worker.py").write_text(_MAIN_THREAD_TESTS, encoding="utf-8")
    proc, lines = child_pytest(
        tmp_path, "-n", "1",
        env_extra={"PYTHONPATH": os.pathsep.join(
            [str(Path(__file__).resolve().parent),
             *filter(None, [os.environ.get("PYTHONPATH")])])})
    assert proc.returncode == 0, "\n".join(lines)
    assert any("2 passed" in ln for ln in lines), "\n".join(lines)
