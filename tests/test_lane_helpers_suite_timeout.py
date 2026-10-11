# SPDX-License-Identifier: Apache-2.0
"""What `tests/test_lane_helpers_suite.py` leaves behind when it gives up on the
shell suite (opensoft/openRepoTools#142, item 3).

`subprocess.run(..., timeout=)` kills the child it started and nothing under
it. The suite's `EXIT` trap does not run on that SIGKILL, so the `sleep` that is
its liveness fixture - made longer than the wrapper's own bound on purpose - and
every later fixture's were orphaned for up to 70 minutes. The wrapper now starts
the suite in a session of its own and kills the whole group on the way out.

THE SUITE ITSELF IS NOT RUN HERE: it is the 45 minutes `test_lane_helpers_suite`
already spends. Each test calls that module's own test function, so the
call site is the one under test and not a copy of it, with `SUITE` pointed at a
stand-in script and the bound cut to seconds. The stand-in starts a `sleep` of
its own, the way the suite does, and the question is whether that `sleep` is
still there afterwards.
"""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import threading
import time

import pytest

import test_lane_helpers_suite as wrapper
from conftest import WINDOWS_SKIP

pytestmark = [
    WINDOWS_SKIP,
    pytest.mark.skipif(shutil.which("bash") is None, reason="the suite is bash"),
    pytest.mark.skipif(shutil.which("ps") is None,
                       reason="the stand-in's `sleep` is looked for with ps"),
]

#: The grandchild outlives every bound below by a wide margin, so it is only
#: ever gone because the wrapper killed it.
STANDIN_START = 'sleep 600 &\necho $! > {pidfile}\nwait\n'


def standin(tmp_path, monkeypatch, body, *, timeout):
    """A stand-in suite whose `{pidfile}` is where its `sleep` writes its pid,
    wired into the wrapper in place of the real one. Returns that file."""
    pidfile = tmp_path / "sleep.pid"
    script = tmp_path / "suite.sh"
    script.write_text(body.format(pidfile=shlex.quote(str(pidfile))),
                      encoding="utf-8")
    monkeypatch.setattr(wrapper, "SUITE", script)
    monkeypatch.setattr(wrapper, "TIMEOUT_SECONDS", timeout)
    return pidfile


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


def sleep_pid(pidfile) -> int:
    assert pidfile.is_file(), (
        "the stand-in never started its sleep, so nothing below would prove "
        "anything")
    return int(pidfile.read_text(encoding="utf-8"))


def assert_gone_within(pid: int, seconds: float = 5.0) -> None:
    """The group is killed with SIGKILL, so this is a matter of the kernel
    reaping, not of the sleep's own timing; the poll is for a slow runner."""
    deadline = time.monotonic() + seconds
    try:
        while running(pid):
            assert time.monotonic() < deadline, (
                f"pid {pid}, a `sleep 600` the stand-in suite started, is still "
                f"running {seconds}s after the wrapper gave up: the kill took "
                "the suite's bash and nothing under it")
            time.sleep(0.05)
    finally:
        if running(pid):
            os.kill(pid, signal.SIGKILL)


def test_a_suite_that_times_out_leaves_no_process_behind(tmp_path, monkeypatch):
    pidfile = standin(tmp_path, monkeypatch, STANDIN_START, timeout=5)
    with pytest.raises(subprocess.TimeoutExpired):
        wrapper.test_the_lane_helper_suite_passes()
    assert_gone_within(sleep_pid(pidfile))


def test_a_suite_that_is_interrupted_leaves_no_process_behind(tmp_path, monkeypatch):
    """A session of its own is not the terminal's foreground group, so a Ctrl-C
    reaches pytest and no longer reaches the suite by itself: the wrapper takes
    the group down on that path too. The SIGINT is sent to this process alone,
    and only once the stand-in's `sleep` exists."""
    pidfile = standin(tmp_path, monkeypatch, STANDIN_START, timeout=120)

    def interrupt_once_started():
        deadline = time.monotonic() + 30
        while not pidfile.is_file() and time.monotonic() < deadline:
            time.sleep(0.05)
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
        signal.signal(signal.SIGINT, previous)
        sender.join(timeout=35)
    assert_gone_within(sleep_pid(pidfile))


def test_a_suite_that_passes_is_still_read_by_its_footer(tmp_path, monkeypatch):
    standin(tmp_path, monkeypatch, 'echo "ok   a case"\necho "1 passed, 0 failed"\n',
            timeout=60)
    wrapper.test_the_lane_helper_suite_passes()


def test_a_suite_that_fails_still_prints_its_whole_transcript(tmp_path, monkeypatch):
    standin(tmp_path, monkeypatch,
            'echo "FAIL a case"\necho "0 passed, 1 failed"\necho "on stderr" >&2\nexit 1\n',
            timeout=60)
    with pytest.raises(AssertionError) as red:
        wrapper.test_the_lane_helper_suite_passes()
    for wanted in ("0 passed, 1 failed", "FAIL a case", "on stderr"):
        assert wanted in str(red.value)
