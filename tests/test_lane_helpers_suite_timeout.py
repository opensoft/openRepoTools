# SPDX-License-Identifier: Apache-2.0
"""What `tests/test_lane_helpers_suite.py` leaves behind when it gives up on the
shell suite, or is told to stop (opensoft/openRepoTools#142, item 3).

`subprocess.run(..., timeout=)` kills the child it started and nothing under
it. The suite's `EXIT` trap does not run on that SIGKILL, so the `sleep` that is
its liveness fixture - made longer than the wrapper's own bound on purpose - and
every later fixture's were orphaned for up to 70 minutes. The wrapper now runs
the suite in a session of its own and stops the whole group: on the timeout, on
a Ctrl-C, and on the TERM and hangup that a session of its own no longer
receives by itself from `tests/run.sh`'s group or from a terminal.

THE SUITE ITSELF IS NOT RUN HERE: it is the 45 minutes `test_lane_helpers_suite`
already spends. Each test points that module's `SUITE` at a stand-in script that
starts a `sleep` of its own, the way the suite does, with the bound cut to
seconds, and asks whether the `sleep` is still there afterwards. Most call the
module's own test function, so the call site is the one under test and not a
copy of it; the signal tests run `run_in_own_group` in a process of their own,
in a group of its own, as `tests/run.sh` runs pytest, and signal that group.
"""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import NamedTuple

import pytest

import test_lane_helpers_suite as wrapper
from conftest import WINDOWS_SKIP

pytestmark = [
    WINDOWS_SKIP,
    pytest.mark.skipif(shutil.which("bash") is None, reason="the suite is bash"),
    pytest.mark.skipif(shutil.which("ps") is None,
                       reason="the stand-in's `sleep` is looked for with ps"),
]

TESTS = Path(__file__).resolve().parent

#: The stand-in answers TERM the way the suite does (`trap 'cleanup; exit 143'
#: TERM`), leaving a marker where the suite would remove its sandbox. Its
#: `sleep` outlives every bound below by a wide margin, so it is only ever gone
#: because the wrapper stopped it.
STANDIN = '''\
trap 'echo trapped > {marker}; exit 143' TERM
sleep 600 &
echo $! > {pidfile}
wait
'''

#: The same, but TERM is ignored by the script and, since an ignored signal is
#: inherited, by its `sleep`: only a KILL ends either.
STANDIN_DEAF = '''\
trap '' TERM
sleep 600 &
echo $! > {pidfile}
wait
'''


class Standin(NamedTuple):
    script: Path
    pidfile: Path     # where the stand-in's `sleep` writes its pid
    marker: Path      # written by the stand-in's TERM trap


def running(pid: int) -> bool:
    """Whether `pid` is a live process. A zombie that nothing has reaped is not
    one, and where the machine's init never reaps (a container whose pid 1 is
    not an init) a killed orphan stays one for good."""
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                          capture_output=True, text=True, check=False).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def sleep_pid(pidfile: Path) -> int:
    assert pidfile.is_file(), (
        "the stand-in never started its sleep, so nothing below would prove "
        "anything")
    return int(pidfile.read_text(encoding="utf-8"))


def assert_gone_within(pid: int, seconds: float = 5.0) -> None:
    """The group is killed, so this is a matter of the kernel reaping and not
    of the sleep's own timing; the poll is for a slow runner."""
    deadline = time.monotonic() + seconds
    while running(pid):
        assert time.monotonic() < deadline, (
            f"pid {pid}, a `sleep 600` the stand-in suite started, is still "
            f"running {seconds}s after the wrapper gave up: what it stopped "
            "was the suite's bash and nothing under it")
        time.sleep(0.05)


@pytest.fixture
def standin(tmp_path):
    """`make(body)`: a stand-in suite with `{pidfile}` and `{marker}` filled in.
    Whatever it leaves running is killed on the way out, so a wrapper that
    stopped stopping the group costs one red test and not a `sleep 600`."""
    pidfiles = []

    def make(body: str) -> Standin:
        pidfile, marker = tmp_path / "sleep.pid", tmp_path / "trapped"
        script = tmp_path / "suite.sh"
        script.write_text(body.format(pidfile=shlex.quote(str(pidfile)),
                                      marker=shlex.quote(str(marker))),
                          encoding="utf-8")
        pidfiles.append(pidfile)
        return Standin(script, pidfile, marker)

    yield make
    for pidfile in pidfiles:
        try:
            pid = int(pidfile.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if running(pid):
            os.kill(pid, signal.SIGKILL)


def wire(monkeypatch, stand: Standin, *, timeout: float) -> None:
    """The wrapper's own test function, run against `stand` and a short bound."""
    monkeypatch.setattr(wrapper, "SUITE", stand.script)
    monkeypatch.setattr(wrapper, "TIMEOUT_SECONDS", timeout)


def test_a_suite_that_times_out_leaves_no_process_behind(standin, monkeypatch):
    stand = standin(STANDIN)
    wire(monkeypatch, stand, timeout=5)
    with pytest.raises(subprocess.TimeoutExpired):
        wrapper.test_the_lane_helper_suite_passes()
    assert_gone_within(sleep_pid(stand.pidfile))
    assert stand.marker.is_file(), (
        "the group was KILLed with no TERM first, so the suite's own trap, "
        "which removes its sandbox, would never have run")


def test_a_group_that_ignores_term_is_killed_after_the_grace(standin, monkeypatch):
    stand = standin(STANDIN_DEAF)
    wire(monkeypatch, stand, timeout=3)
    monkeypatch.setattr(wrapper, "GROUP_TERM_GRACE", 1)
    with pytest.raises(subprocess.TimeoutExpired):
        wrapper.test_the_lane_helper_suite_passes()
    assert_gone_within(sleep_pid(stand.pidfile))


def test_a_suite_that_is_interrupted_leaves_no_process_behind(standin, monkeypatch):
    """A session of its own is not the terminal's foreground group, so a Ctrl-C
    reaches pytest and no longer reaches the suite by itself. The SIGINT is sent
    to this process alone, once the stand-in's `sleep` exists, and never after
    the wrapper has returned: a late one would abort the whole pytest session."""
    stand = standin(STANDIN)
    wire(monkeypatch, stand, timeout=120)
    done = threading.Event()

    def interrupt_once_started():
        deadline = time.monotonic() + 30
        while not stand.pidfile.is_file() and time.monotonic() < deadline:
            if done.wait(0.05):
                return
        if not done.is_set():
            os.kill(os.getpid(), signal.SIGINT)

    # A run started with SIGINT ignored (a background job's) has no handler to
    # raise KeyboardInterrupt; this puts Python's own back for the one test.
    previous = signal.signal(signal.SIGINT, signal.default_int_handler)
    sender = threading.Thread(target=interrupt_once_started, daemon=True)
    try:
        sender.start()
        with pytest.raises(KeyboardInterrupt):
            wrapper.test_the_lane_helper_suite_passes()
    finally:
        done.set()
        sender.join(timeout=5)
        signal.signal(signal.SIGINT, previous)
    assert_gone_within(sleep_pid(stand.pidfile))
    assert stand.marker.is_file()


# A SIGNAL TO THE GROUP THE WAY `tests/run.sh` SENDS IT. run.sh starts
# `python3 -m pytest` in a process group of its own and stops that group with
# `kill -TERM -- -<pgid>`; a terminal's hangup reaches the same process. The
# suite is no longer in that group, so what stops it is `run_in_own_group`'s
# handler. The runner below is that pytest: a process of its own, leading a
# group of its own, running the wrapper's helper against the stand-in.
RUNNER = '''\
import signal, sys
sys.path.insert(0, {tests!r})
{prelude}
import test_lane_helpers_suite as w
w.GROUP_TERM_GRACE = 5
w.run_in_own_group(["bash", {script!r}], timeout=120)
'''


@pytest.fixture
def runner(tmp_path):
    """`start(stand, prelude="")`: the runner, in a group of its own. Its group
    is killed on the way out if a test left it running."""
    started = []

    def start(stand: Standin, prelude: str = "") -> subprocess.Popen:
        code = RUNNER.format(tests=str(TESTS), script=str(stand.script), prelude=prelude)
        errors = tmp_path / "runner.err"
        with open(errors, "w", encoding="utf-8") as sink:
            proc = subprocess.Popen([sys.executable, "-c", code], cwd=str(tmp_path),
                                    stdout=subprocess.DEVNULL, stderr=sink,
                                    start_new_session=True)
        proc.errors = errors
        started.append(proc)
        deadline = time.monotonic() + 30
        while not stand.pidfile.is_file():
            assert proc.poll() is None and time.monotonic() < deadline, (
                "the runner never started the stand-in's sleep:\n"
                + errors.read_text(encoding="utf-8"))
            time.sleep(0.05)
        return proc

    yield start
    for proc in started:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGHUP],
                         ids=["TERM", "HUP"])
def test_a_signal_to_the_runners_group_leaves_no_process_behind(
        signum, standin, runner):
    stand = standin(STANDIN)
    proc = runner(stand)
    os.killpg(proc.pid, signum)
    assert proc.wait(timeout=30) == -signum, (
        "the runner should end by the signal it was sent, as it would have "
        "had nothing been handling it:\n" + proc.errors.read_text(encoding="utf-8"))
    assert_gone_within(sleep_pid(stand.pidfile))
    assert stand.marker.is_file()


def test_a_hangup_that_was_ignored_stays_ignored(standin, runner):
    """A `nohup`'d run has SIGHUP ignored, and goes on after the terminal is
    gone: the handler is installed only where the disposition is the default."""
    stand = standin(STANDIN)
    proc = runner(stand, prelude="signal.signal(signal.SIGHUP, signal.SIG_IGN)")
    pid = sleep_pid(stand.pidfile)
    os.killpg(proc.pid, signal.SIGHUP)
    time.sleep(1)
    assert proc.poll() is None and running(pid), (
        "a hangup the run was ignoring ended it:\n"
        + proc.errors.read_text(encoding="utf-8"))
    os.killpg(proc.pid, signal.SIGTERM)
    assert proc.wait(timeout=30) == -signal.SIGTERM
    assert_gone_within(pid)


def test_a_suite_that_passes_is_still_read_by_its_footer(standin, monkeypatch):
    wire(monkeypatch, standin('echo "ok   a case"\necho "1 passed, 0 failed"\n'),
         timeout=60)
    wrapper.test_the_lane_helper_suite_passes()


def test_a_suite_that_fails_still_prints_its_whole_transcript(standin, monkeypatch):
    wire(monkeypatch,
         standin('echo "FAIL a case"\necho "0 passed, 1 failed"\n'
                 'echo "on stderr" >&2\nexit 1\n'),
         timeout=60)
    with pytest.raises(AssertionError) as red:
        wrapper.test_the_lane_helper_suite_passes()
    for wanted in ("0 passed, 1 failed", "FAIL a case", "on stderr"):
        assert wanted in str(red.value)
