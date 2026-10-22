# SPDX-License-Identifier: Apache-2.0
"""The runner for `tests/test_lane_helpers.sh`, so that suite runs at all.

A SUITE NOTHING RUNS IS NOT A SUITE. This repository's CI is pytest-only
(`.github/workflows/tests.yml` runs `python3 -m pytest tests -q`, and
`test_repo_hygiene.py` globs `tests/*.py`), so the 196 KB of bash that arrived
at `tests/test_lane_helpers.sh` under lane-collision-protocol Amendment 9's
move would otherwise run in NO job — which is act 3's obligation 6 in its own
words. This file is the wrapper that obligation names.

IT IS ONE TEST, NOT NINE HUNDRED, and the asymmetry is deliberate. The bash
suite owns its own assertion vocabulary — `ok` / `FAIL` lines and a
`N passed, M failed` footer — and re-expressing 897 of them as pytest cases
would mean parsing that output into parametrized ids, which is a second
implementation of the suite's own reporting and a second thing to keep right.
What pytest needs to know is one bit: did every assertion pass? So this runs
the file, and on failure prints the WHOLE transcript into the assertion
message, which is what a person reading a red CI job actually needs. A PASS
prints only the suite's own account of where its time went (`show_timings`,
opensoft/openRepoTools#77), because a green job is where nobody reads the
transcript and where that one account is wanted.

IT TOUCHES NOTHING REAL. The suite redirects `$HOME`, `$TMPDIR`,
`$AGENT_PROTOCOL_ROOT` and `$OPENREPOTOOLS_BIN_DIR` into a `mktemp -d` sandbox
of its own, seeds a bare repository plus two clones there, fakes `tmux` and
`claude` on `PATH`, and exports `LANES_NO_GITHUB=1` so no case can reach
GitHub. Its own last assertions are the ones that check that — see the foot of
that file.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from conftest import REPO, ROOTS, WINDOWS_SKIP

SUITE = REPO / "tests" / "test_lane_helpers.sh"

#: Generous, and not a performance claim: the suite runs real `git` against
#: real repositories several hundred times and spawns a real `sleep` for the
#: liveness cases. A CI runner under load is slower than a workstation, and a
#: timeout that fires there reads as a broken suite rather than a slow one.
#:
#: 900 -> 2400 on 2026-09-13 (A9 Addendum 4, R-A9-11). This is the round that
#: made the suite RUN on macOS rather than fail in its first hundred
#: assertions, and running is slower than failing: at `9000e86` the job took
#: 1033 s to reach 507 passed / 447 failed, and at `c405eb4`, with those 447
#: now doing real work, 900 s was not enough to finish — the run died as a
#: TimeoutExpired rather than a red assertion, which is the least readable
#: failure this file can produce. Measured for comparison: 229 s under pytest
#: on the Linux container this was written on. The bound still exists for the
#: thing it was written for — a helper that hangs on a lock or a network call
#: must not hold a runner for six hours — it is just no longer tighter than
#: the slowest platform this suite is required to pass on.
#:
#: 2400 -> 3600 on 2026-09-15, AND FOR THE SAME REASON ONE ROUND LATER: the
#: suite crossed it. Measured, `b9018c1` (#45 with Amendment 18 Addendum 1's
#: section merged beside Amendment 17's, 2102 cases -> 2345):
#:
#:     tests-macos   03:18:03 -> 04:03:37, `1 failed, 654 passed in 2722.13s`
#:                   and the one failure is this wrapper —
#:                   `subprocess.TimeoutExpired: … timed out after 2400 seconds`
#:     tests         16 min 47 s, green, the same 655 cases
#:
#: EVERY OTHER CASE IN THAT macOS JOB PASSED. What the bound caught was the
#: suite being long on the slowest platform it must pass on, not a helper
#: hanging — and a TimeoutExpired says nothing about which assertion was in
#: flight, which is exactly the unreadable failure the paragraph above warns
#: against. It is one number rather than a per-platform pair because a bound
#: that is different where a person is not looking is a bound nobody can
#: reason about: a loaded WORKSTATION is slow too, and a legitimate run of this
#: same tree took 2129 s here with six sibling suites building beside it.
#:
#: 3600 -> 5400 on 2026-10-03, AND FOR THE SAME REASON A THIRD TIME: #93
#: (Amendment 19, ~3016 cases against main's ~2795) crossed it on darwin.
#: Measured, both on that PR's head, both the same single failure —
#: `subprocess.TimeoutExpired: … timed out after 3600 seconds` — so neither
#: run says which assertion was in flight:
#:
#:     tests-macos   `08dad90`  `1 failed, 680 passed in 3961.39s`
#:     tests-macos   `968ab5e`  `1 failed, 693 passed in 3927.56s`
#:     tests         `968ab5e`  green, `694 passed in 2466.84s`
#:
#: and on main at `69bf48d`, where the suite still FINISHED, the job's pytest
#: took 3741.66 s in all: it was already within minutes of this bound. Since
#: #119 `tests-macos` is the landing gate on the `ready` label, so a bound the
#: suite cannot finish inside is a gate nothing can pass and nobody can read.
#:
#: THE HONEST FIX IS THE SUITE'S DURATION AND NOT THIS NUMBER — one bash file
#: that runs real `git` several thousand times, serially, for 45 minutes — and
#: it is opensoft/openRepoTools#77. This is the cap moving out of that work's
#: way, not a decision that 45 minutes is fine.
#:
#: The job itself has no `timeout-minutes` in `.github/workflows/tests.yml`, so
#: nothing under it bites before this does; GitHub's own default is 360 min.
TIMEOUT_SECONDS = 5400


#: THE SUITE'S LIVENESS FIXTURE MUST OUTLIVE THE BOUND ABOVE, and at `758a536`
#: it did not. `tests/test_lane_helpers.sh` starts one `sleep <n> & LIVE_PID=$!`
#: and every "a live holder …" case in that file — on macOS, where there is no
#: `/proc`, ALL of them — is `kill -0` on that pid. At `sleep 3000` against a
#: 3600 s timeout the wrapper was still waiting on a run whose evidence had
#: already expired 600 s earlier, and the suite answered "no live holder" for
#: cases that had a live holder: four of tests-macos' ten red lines at that
#: commit, in the last 5% of the file, with nothing in the output saying why.
#:
#: A comment in each file saying "keep these two in step" is what was there
#: before, and it did not survive TIMEOUT_SECONDS being raised from 2400. This
#: reads the bash line and REFUSES the pair, so raising one without the other
#: is red in seconds on every platform rather than red in an hour on one.
#:
#: AND SINCE #83 THE FIXTURE MAY BE DERIVED RATHER THAN WRITTEN: `sleep
#: "$LIVE_SLEEP"`, where `LIVE_SLEEP` is this file's own `TIMEOUT_SECONDS`
#: read back out of it by `sed`, plus a margin. That form is accepted only where
#: the same pattern, applied to THIS file, finds the number this module runs
#: with — so the pair is still proved, now by the read the suite makes.
_SED_READ = r"s/^TIMEOUT_SECONDS = \([0-9][0-9]*\).*/\1/p"


def test_the_liveness_fixture_outlives_the_suite_timeout():
    text = SUITE.read_text(encoding="utf-8")
    hit = [ln for ln in text.splitlines() if "LIVE_PID=$!" in ln]
    assert len(hit) == 1, (
        "expected exactly one liveness fixture in tests/test_lane_helpers.sh, "
        f"found {len(hit)}: {hit}")
    literal = re.search(r"\bsleep\s+(\d+)\s*&\s*LIVE_PID=\$!", hit[0])
    if literal:
        bound = int(literal.group(1))
    else:
        assert re.search(r'\bsleep\s+"\$LIVE_SLEEP"\s*&\s*LIVE_PID=\$!', hit[0]), (
            f"the liveness fixture is neither a bounded sleep nor the derived one: {hit[0]!r}")
        margin = re.search(r"^LIVE_SLEEP=\$\(\(\s*LIVE_BOUND\s*\+\s*(\d+)\s*\)\)", text, re.M)
        assert margin, "LIVE_SLEEP is no longer LIVE_BOUND plus a fixed margin"
        assert _SED_READ in text and "test_lane_helpers_suite.py" in text, (
            "LIVE_BOUND is no longer read out of this file's TIMEOUT_SECONDS")
        own = re.search(r"^TIMEOUT_SECONDS = ([0-9][0-9]*)",
                        Path(__file__).read_text(encoding="utf-8"), re.M)
        assert own and int(own.group(1)) == TIMEOUT_SECONDS, (
            "the suite's sed read of TIMEOUT_SECONDS would not find the number "
            "this module runs with, so its fixture would fall back to a default")
        bound = TIMEOUT_SECONDS + int(margin.group(1))
    assert bound > TIMEOUT_SECONDS, (
        f"the liveness fixture is bounded at {bound}s while this wrapper lets "
        f"the suite run for TIMEOUT_SECONDS={TIMEOUT_SECONDS}s, so the suite is "
        "licensed to outlive its own evidence: every liveness case after "
        f"{bound}s would read 'no live holder' and say nothing about why. "
        "Raise the sleep in tests/test_lane_helpers.sh above this bound.")


#: How long the suite's process group gets to answer a TERM - its own trap
#: removes the sandbox it made - before it is KILLed.
#:
#: FIVE, AND NOT THE TEN `tests/run.sh` GIVES ITS OWN GROUP. run.sh's
#: `stop_group` polls fifty times at 0.2 s and each poll runs `ps`, so it waits
#: about 10.7 s before it KILLs pytest. This stop is TERM, this wait, KILL and a
#: reap, and all of it has to finish well inside that: a stop that takes as long
#: as run.sh's gets pytest killed in the middle of it, with the suite's group
#: left running - which is the orphan this exists to prevent.
GROUP_TERM_GRACE = 5

#: How often `run_in_own_group` looks up from waiting on the suite to see
#: whether a TERM or a hangup has arrived.
_SIGNAL_POLL = 0.5


def stop_group(child) -> None:
    """Stop the process group `child` leads: TERM, up to GROUP_TERM_GRACE
    seconds for its leader to answer it, then KILL for whatever is left, and
    reap the leader. A group that is already gone is not an error.

    THE KILL IS IN A `finally`, AND CTRL-C IS IGNORED UNTIL IT HAS BEEN SENT.
    A second Ctrl-C during the grace used to leave the wait with a
    KeyboardInterrupt, skip the KILL, and orphan a suite that was ignoring
    TERM. The stop is bounded, so ignoring a person's Ctrl-C for it costs at
    most GROUP_TERM_GRACE seconds."""
    on_main = threading.current_thread() is threading.main_thread()
    held = signal.signal(signal.SIGINT, signal.SIG_IGN) if on_main else None
    try:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(child.pid, signal.SIGTERM)
        with contextlib.suppress(subprocess.TimeoutExpired):
            child.wait(timeout=GROUP_TERM_GRACE)
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait()
        if held is not None:
            signal.signal(signal.SIGINT, held)


def run_in_own_group(argv, *, timeout, **popen_kwargs):
    """`subprocess.run(argv, capture_output=True, timeout=timeout)` with the
    command in a session of its own, which is stopped whenever this does not
    return normally.

    THE SUITE RUNS IN A SESSION OF ITS OWN (opensoft/openRepoTools#142, item
    3). `subprocess.run(timeout=)` kills only the bash it started, and the
    suite's `EXIT` trap does not run on that SIGKILL, so the liveness
    fixture's `sleep` - longer than TIMEOUT_SECONDS on purpose - and every
    later fixture's were orphaned for up to 70 minutes. The child leads its
    session, so its pid is its group's id, and the group is what `stop_group`
    stops: TERM first, so the suite's own TERM trap removes its sandbox.

    A SESSION OF ITS OWN IS NOT THE GROUP `tests/run.sh` STOPS, NOR THE
    TERMINAL'S. A TERM to that group, a hangup and a Ctrl-C now reach THIS
    process and no longer reach the suite. pytest has no handler for the first
    two, so one is installed here for as long as this waits - only where the
    disposition is still the default, so a `nohup`'d run goes on ignoring a
    hangup. The handler only NOTES the signal, and the wait is made in slices
    of _SIGNAL_POLL that look for it: a handler that raised would raise inside
    `Popen()` as well, after the fork and before `child` is bound, and leave
    the suite with nobody to stop it. A noted signal stops the group, and then
    the signal is sent to this process again with its default action restored,
    so it ends as it would have had nothing been handling it. The timeout and
    a KeyboardInterrupt stop the group too.

    WHAT THIS DOES NOT REACH: the pty driver's children (`LANE_PTY` in the
    suite) are session leaders of their own (`pty.fork` runs `setsid`), so they
    are outside the group; each is bounded by that driver's own silence limit.

    `errors="replace"`, because the thing the wrapper below exists to print is
    the TRANSCRIPT, and a decode that raises loses all of it. The suite renders
    its own failures with bash substrings for that reason (R-A9-11), so a
    stray byte here should be impossible - and if one ever gets through, a
    `\\ufffd` in one line is a readable result where `UnicodeDecodeError` is
    none at all. Measured: at `dcf1027` one truncated em dash cost the whole
    998-line transcript on the macOS job.
    """
    pending = []   # the TERM or HUP numbers that arrived, oldest first
    handled = []

    def note(signum, _frame):
        pending.append(signum)

    try:
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGTERM, signal.SIGHUP):
                if signal.getsignal(signum) == signal.SIG_DFL:
                    signal.signal(signum, note)
                    handled.append(signum)
        with subprocess.Popen(argv, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, encoding="utf-8",
                              errors="replace", start_new_session=True,
                              **popen_kwargs) as child:
            try:
                deadline = time.monotonic() + timeout
                while not pending:
                    left = deadline - time.monotonic()
                    try:
                        stdout, stderr = child.communicate(
                            timeout=max(min(_SIGNAL_POLL, left), 0))
                    except subprocess.TimeoutExpired as expired:
                        if left > _SIGNAL_POLL:
                            continue
                        # The bound that was passed, not the last slice's: a
                        # CI log reads "timed out after 5400 seconds".
                        raise subprocess.TimeoutExpired(
                            child.args, timeout, output=expired.output,
                            stderr=expired.stderr) from None
                    break
            except BaseException:
                stop_group(child)
                raise
            if pending:   # also a signal that came as the suite finished
                stop_group(child)
        if pending:
            raise SystemExit(128 + pending[0])   # the `finally` sends the signal itself
        return subprocess.CompletedProcess(child.args, child.returncode,
                                           stdout, stderr)
    finally:
        for signum in handled:
            signal.signal(signum, signal.SIG_DFL)
        if pending:
            os.kill(os.getpid(), pending[0])


#: WHAT THE SUITE SAYS ABOUT ITS OWN CLOCK (opensoft/openRepoTools#77, step 1a
#: put it in the suite; step 1b is this file carrying it out). The two strings
#: are the ones `tests/test_lane_helpers.sh` prints, and
#: `test_the_wrapper_looks_for_what_the_suite_prints` reads that file to hold
#: them to it: the table's first line on STDOUT, whose rows follow it up to the
#: rule that precedes the footer, and the teardown line on STDERR, said by the
#: exit trap after the footer by nature.
TIMING_HEADER = "wall time per section, longest first"
TEARDOWN_PREFIX = "teardown: rm -rf of the sandbox"

#: A row of that table: `%6s s  %3s%%  <heading>`. The seconds may be NEGATIVE:
#: they are differences of bash's `SECONDS`, which a clock step can send
#: backwards, and a row the pattern did not know would end the table there and
#: lose every row after it, the whole-run row among them.
_TIMING_ROW = re.compile(r"^\s*-?\d+ s\s")


def suite_timings(stdout: str, stderr: str) -> tuple[list[str], list[str]]:
    """The suite's timing table and its teardown line, each as lines, or as an
    empty list where the suite printed none. Reads text only and cannot fail:
    what to do about a missing one is `show_timings`' to say."""
    table: list[str] = []
    lines = stdout.splitlines()
    for at, line in enumerate(lines):
        if line.startswith(TIMING_HEADER):
            table = [line]
            for row in lines[at + 1:]:
                if not _TIMING_ROW.match(row):
                    break
                table.append(row)
            break
    teardown = [ln for ln in stderr.splitlines() if ln.startswith(TEARDOWN_PREFIX)]
    return table, teardown


#: HOW `show_timings` SPEAKS PAST PYTEST'S CAPTURE: a context manager that
#: suspends it. It is `capsys.disabled` while one of THIS module's tests runs,
#: put there by the fixture below, and a no-op anywhere else.
_past_capture = contextlib.nullcontext


@pytest.fixture(autouse=True)
def _speak_past_capture(request, monkeypatch):
    """Give `show_timings` the one fixture it needs WITHOUT A PARAMETER ON THE
    TEST. `tests/test_lane_helpers_suite_timeout.py` calls
    `test_the_lane_helper_suite_passes()` itself, with no arguments, at six call
    sites, so that the call site and not a copy of it is what it proves; a
    `capsys` parameter would make every one a TypeError. Called from there the
    fixture is not in play (it is this module's, and autouse only reaches this
    module's tests), `_past_capture` stays a no-op, and the block goes into the
    capture a passing test discards: nothing there reads it.

    `capsys` IS ASKED FOR, NOT REQUIRED. Under `-p no:capture` the fixture does
    not exist, and a parameter named `capsys` on an AUTOUSE fixture would make
    every test in this file, the liveness test among them, an ERROR for it.
    Nothing captures there, so nothing needs suspending, and the no-op serves.
    Only pytest's own `FixtureLookupError` is let go: a wider clause would read
    a fault of some other kind as "no capture plugin" and hide it."""
    try:
        capsys = request.getfixturevalue("capsys")
    except pytest.FixtureLookupError:   # the capture plugin is off
        return
    monkeypatch.setitem(globals(), "_past_capture", capsys.disabled)


def show_timings(proc) -> None:
    """Print a PASSING suite's timings to pytest's real output.

    WHY THIS EXISTS (opensoft/openRepoTools#77). A passing run's stdout and
    stderr were both captured here and dropped, so the numbers step 1a added
    reached no log `gh run view --log` returns, and a step summary only a
    person signed in to the web UI can open.

    `capsys.disabled()` AND NOT A PRINT: pytest captures at the file
    descriptor, so `print` and even `sys.__stdout__` land in the capture
    buffer, which a passing test throws away. The fixture is the supported way
    to speak past it, and it keeps the data inside this file. A
    `pytest_terminal_summary` hook in `conftest.py` (there is one, for the test
    roots) would print at the foot of the log instead, but it needs this test to
    leave the numbers somewhere for the hook to find, in a file every other
    test shares. What the fixture costs is the block's place: it lands in
    `-q`'s row of dots, at the moment the test passes, so it opens and closes
    with a newline.

    A MISSING TABLE OR TEARDOWN LINE IS SAID, AND NEVER FAILS THE RUN: a suite
    that stopped printing its clock is a regression `gh run view` would
    otherwise hide for ever, and a timing table is not a reason to turn a green
    run red. THE CALLER PRINTS ONLY AFTER ITS ASSERTIONS HAVE PASSED, so a
    failing run says its transcript once, in the assertion message, and not
    again here.

    THE SAME RULE MAKES THE WRITE ITSELF SAFE. The suite's headings carry em
    dashes, and a stdout that cannot spell one (`PYTHONIOENCODING=ascii`, a
    stray `LANG`) would raise `UnicodeEncodeError` from a plain `print`, in a
    test that had already passed. So the block is cut down to what the stream's
    own encoding can say, with `\\uXXXX` for the rest, and a stream that cannot
    be written to at all (an `OSError`) is let go: the numbers are lost and the
    run is not."""
    table, teardown = suite_timings(proc.stdout, proc.stderr)
    block = [f"{SUITE.name} passed; its own clock, which a pass would otherwise "
             "discard (opensoft/openRepoTools#77):"]
    block += table or [f"(no timing table: no line of its stdout starts "
                       f"{TIMING_HEADER!r})"]
    block += teardown or [f"(no teardown line: no line of its stderr starts "
                          f"{TEARDOWN_PREFIX!r})"]
    text = "\n" + "\n".join(block) + "\n"
    with _past_capture():
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        text = text.encode(encoding, "backslashreplace").decode(encoding)
        with contextlib.suppress(OSError):
            print(text, flush=True)


@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None,
                    reason="the lane helpers and their suite are bash")
def test_the_lane_helper_suite_passes():
    env = dict(os.environ)
    # The suite asserts on git's own output and on commit authorship in its
    # sandbox; a runner with no identity configured would fail inside it for a
    # reason that is not about the helpers.
    env.setdefault("GIT_AUTHOR_NAME", "openRepoTools CI")
    env.setdefault("GIT_AUTHOR_EMAIL", "ci@openrepotools.invalid")
    env.setdefault("GIT_COMMITTER_NAME", "openRepoTools CI")
    env.setdefault("GIT_COMMITTER_EMAIL", "ci@openrepotools.invalid")
    # Not inherited: every one of these is a seam the suite unsets or sets for
    # itself, and a developer's own shell must not change what it proves.
    for name in ("LANES_FILE", "LANES_EDIT", "LANES_REPO", "LANES_PATH",
                 "LANES_LANE", "LANES_WORKSPACE_ROOT", "LANES_REPOS_TSV",
                 "LANES_REPOS_TSV_SHIPPED", "AGENT_PROTOCOL_ROOT",
                 "OPENREPOTOOLS_BIN_DIR", "PROJECTS_ROOT", "CLAUDE_NO_LANE",
                 "LANES_DIR", "LANES_NO_FETCH", "LANES_NO_GIT", "LANES_GIT",
                 "LANES_SESSION"):
        env.pop(name, None)
    # AND EVERY OTHER `LANES_*` AND `TMUX*` (#193 item 25; ort186 Q9's
    # condition on Amendment 23's seam): a launched lane exports `LANES_REPO`
    # and `LANES_WORKSPACE_ROOT` into every shell, and the suite clears these
    # again itself, so a run from a lane window reads no real register.
    for name in [n for n in env if n.startswith(("LANES_", "TMUX"))]:
        env.pop(name, None)
    # THE LANE MANUAL IS THE SPEC LEG'S (opensoft/openRepoTools#186, T009):
    # the suite quotes `docs/README-lanes.md` back against the code, and in the
    # triad that file is not beside the code. Named from this run's roots - the
    # code root itself on today's layout - and EMPTY where the run has no spec
    # root (a standalone code leg), which the suite reads as "skip the quotes,
    # naming why". A composed run without one never gets here: conftest
    # refuses it before the first test.
    spec = ROOTS.root_of("spec")
    env["OPENREPOTOOLS_LANE_MANUAL"] = (
        "" if spec is None else str(spec / "docs" / "README-lanes.md"))

    proc = run_in_own_group(["bash", str(SUITE)], timeout=TIMEOUT_SECONDS,
                            cwd=str(REPO), env=env)
    tail = proc.stdout.strip().splitlines()[-1:] or ["(no output)"]
    assert proc.returncode == 0, (
        f"tests/test_lane_helpers.sh failed ({tail[0]}):\n"
        f"{proc.stdout}\n{proc.stderr}")
    # The footer, read rather than assumed: a suite that exited 0 having run
    # nothing at all would otherwise pass this.
    assert " passed, 0 failed" in proc.stdout, proc.stdout[-2000:]
    show_timings(proc)


# --- the timings a pass prints (opensoft/openRepoTools#77, step 1b) ---------

#: A STAND-IN FOR THE SUITE, in the shape step 1a gave its output: a heading,
#: a case, the table of its sections with its rule, the footer, and the
#: teardown line on stderr after it. `table=False` is a suite that prints no
#: clock; `failing` is one whose footer counts a failure and which exits 1.
_STAND_IN = """#!/usr/bin/env bash
echo "== a heading =="
echo "ok   a case"
{table}echo "----"
echo "{footer}"
echo "teardown: rm -rf of the sandbox took 3 s" >&2
exit {status}
"""
#: The third row carries an em dash, as the real suite's headings do.
_STAND_IN_TABLE = """echo 'wall time per section, longest first (whole seconds; opensoft/openRepoTools#77):'
echo '    12 s   60%  the slow section'
echo '     8 s   40%  the quick section'
echo '     0 s    0%  a row with a dash \u2014 in it'
echo '    20 s  100%  the whole run, from the top of this file to this table'
"""

#: THE REAL TEST, RUN BY A CHILD PYTEST over this very file, with its own
#: fixtures and signature, and with the suite it runs swapped for a stand-in by
#: this plugin. A copy of its body here would prove the copy; and a child and
#: not this process, because what is under test is what pytest's REAL output
#: holds, which `capsys` and `capfd` in a test that is itself captured cannot
#: say.
_CHILD_PLUGIN = """\
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def stand_in_suite(monkeypatch):
    import test_lane_helpers_suite as wrapper
    monkeypatch.setattr(wrapper, "SUITE", Path(os.environ["STAND_IN_SUITE"]))
"""

#: WHAT THE CHILD IS NOT TO INHERIT. Each of these changes how pytest WRITES,
#: not what it says, and a test that reads its output line by line must not
#: depend on which of them the runner set. `CI` and `BUILD_NUMBER` make pytest
#: print a whole failure message in its short summary where it prints the first
#: line elsewhere; `NO_COLOR` and `FORCE_COLOR` are two of the four things that
#: decide whether it colours. The fourth is the terminal, which a pipe is not,
#: and the first, `PY_COLORS`, is read before the rest, so it is SET to "0"
#: below rather than only removed: a runner that exports `FORCE_COLOR=1` and a
#: `PY_COLORS=1` ends every `E` line in an escape sequence, and `lines_ending`
#: then counts nothing.
_CHILD_NOT_INHERITED = ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST",
                        "CI", "BUILD_NUMBER", "NO_COLOR", "FORCE_COLOR")

_REAL_TEST = "test_the_lane_helper_suite_passes"


def run_wrapper_over(tmp_path, *, table=True, failing=False, inherited=None,
                     env_extra=None, args=(), tests=(_REAL_TEST,)):
    """Run the wrapper's own test, as `pytest tests -q` runs it, over a
    stand-in suite. Returns the child's process and its output as lines.

    `inherited` is what the CHILD'S PARENT is imagined to have set, which the
    child must not see; `env_extra` is what it IS to see; `args` are more
    pytest options and `tests` the names, in this file, it is to run."""
    stand_in = tmp_path / "stand-in-suite.sh"
    stand_in.write_text(_STAND_IN.format(
        table=_STAND_IN_TABLE if table else "",
        footer="1 passed, 1 failed, 0 skipped, 0 pending" if failing
        else "2 passed, 0 failed, 0 skipped, 0 pending",
        status=1 if failing else 0), encoding="utf-8")
    (tmp_path / "stand_in_plugin.py").write_text(_CHILD_PLUGIN, encoding="utf-8")
    env = dict(os.environ, **(inherited or {}))
    # THE COLOUR TESTS PIN `PY_COLORS="0"`, set below, and the escape-sequence
    # assertion; these pops only keep a runner's own settings out of the child.
    for name in _CHILD_NOT_INHERITED:
        env.pop(name, None)
    env.update(
        STAND_IN_SUITE=str(stand_in), PY_COLORS="0", PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join(
            [str(tmp_path), *filter(None, [os.environ.get("PYTHONPATH")])]),
        **(env_extra or {}))
    proc = run_in_own_group(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "-p", "stand_in_plugin", *args,
         *(f"{Path(__file__).resolve()}::{name}" for name in tests)],
        timeout=600, cwd=str(tmp_path), env=env)
    return proc, (proc.stdout + proc.stderr).splitlines()


def lines_ending(lines, text):
    """How many lines of the output end in `text`: a row of the stand-in's
    table, whether bare (a pass) or after pytest's `E   ` (a failure's message).
    A failure's assertion explanation holds the whole `CompletedProcess` as one
    escaped line, which ends in something else and so is not counted."""
    return sum(1 for ln in lines if ln.rstrip().endswith(text))


@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None,
                    reason="the lane helpers and their suite are bash")
def test_a_passing_suite_shows_its_timings_in_pytests_own_output(tmp_path):
    proc, lines = run_wrapper_over(tmp_path)
    assert proc.returncode == 0, "\n".join(lines)
    assert lines_ending(lines, "the slow section") == 1, "\n".join(lines)
    assert lines_ending(lines, "the quick section") == 1, "\n".join(lines)
    assert lines_ending(lines, "to this table") == 1, "\n".join(lines)
    assert lines_ending(lines, "teardown: rm -rf of the sandbox took 3 s") == 1, (
        "\n".join(lines))
    assert lines_ending(lines, "opensoft/openRepoTools#77):") == 2, (
        "the table's own header and the lead line over it, once each:\n"
        + "\n".join(lines))
    # What the suite printed that is NOT its clock stays out of a green log.
    assert lines_ending(lines, "ok   a case") == 0, "\n".join(lines)


#: What a runner may have set that the child is not to see: the colour
#: variables and `CI`, alone and together.
_RUNNER_SETS = [
    pytest.param({"FORCE_COLOR": "1"}, id="FORCE_COLOR=1"),
    pytest.param({"PY_COLORS": "1"}, id="PY_COLORS=1"),
    pytest.param({"CI": "true"}, id="CI=true"),
    pytest.param({"CI": "true", "FORCE_COLOR": "1"}, id="CI=true+FORCE_COLOR=1"),
    pytest.param({"BUILD_NUMBER": "7"}, id="BUILD_NUMBER=7"),
    pytest.param({}, id="nothing"),
]


@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None,
                    reason="the lane helpers and their suite are bash")
@pytest.mark.parametrize("inherited", _RUNNER_SETS)
def test_a_failing_suite_prints_no_timings_block_beside_its_transcript(
        tmp_path, inherited):
    proc, lines = run_wrapper_over(tmp_path, failing=True, inherited=inherited)
    assert proc.returncode != 0, "\n".join(lines)
    # The child's output is the same whatever the runner set: no escape
    # sequence ends a row (the lines below are counted by how they END), and
    # the same message is printed the same number of times.
    assert not any("\x1b[" in ln for ln in lines), (
        "the child coloured its output:\n" + "\n".join(lines))
    # The transcript is in the assertion message, and that it is THERE is all
    # that is counted: how many times pytest repeats the message is not this
    # file's to pin.
    assert lines_ending(lines, "the slow section") >= 1, "\n".join(lines)
    assert lines_ending(lines, "teardown: rm -rf of the sandbox took 3 s") >= 1, (
        "\n".join(lines))
    # What is pinned is that the wrapper said nothing of its own: every block
    # `show_timings` prints opens with its lead line, which names the run a
    # PASS.
    assert not any("its own clock" in ln for ln in lines), (
        "a failing run printed the passing run's lead line:\n" + "\n".join(lines))


@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None,
                    reason="the lane helpers and their suite are bash")
def test_a_passing_suite_that_printed_no_clock_is_said_to_have_none(tmp_path):
    proc, lines = run_wrapper_over(tmp_path, table=False)
    assert proc.returncode == 0, "\n".join(lines)
    assert any(ln.startswith("(no timing table: ") for ln in lines), "\n".join(lines)


@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None,
                    reason="the lane helpers and their suite are bash")
def test_a_stdout_that_cannot_spell_the_table_does_not_fail_a_pass(tmp_path):
    """The real suite's headings carry em dashes. On an ASCII stdout the block
    is written with `\\uXXXX` in their place, and the run stays green."""
    proc, lines = run_wrapper_over(tmp_path, env_extra={"PYTHONIOENCODING": "ascii"})
    assert proc.returncode == 0, "\n".join(lines)
    assert any(ln.endswith("a row with a dash \\u2014 in it") for ln in lines), (
        "\n".join(lines))
    assert not any("UnicodeEncodeError" in ln for ln in lines), "\n".join(lines)


def test_a_stream_that_cannot_be_written_to_does_not_fail_a_pass(monkeypatch):
    """`show_timings` lets an `OSError` from its write go (a full disk, a pipe
    nobody reads): the numbers are lost and the run is not. NOTHING ELSE IN THIS
    FILE REACHES THAT `suppress`, and with it removed every other test here
    still passes, so this one writes into a stream that raises ENOSPC and asks
    that the write was ATTEMPTED and that the call RETURNED.

    The stream is put where `sys.stdout` is by a stand-in for `capsys.disabled()`
    (the autouse fixture's own would hand the real stdout back), and only for the
    write, so nothing is left behind for the fixtures that tear down after this
    test."""
    class Unwritable:
        encoding = "utf-8"
        attempts = 0

        def write(self, text):
            Unwritable.attempts += 1
            raise OSError(28, "No space left on device")

        def flush(self):
            raise OSError(28, "No space left on device")

    @contextlib.contextmanager
    def unwritable_stdout():
        with contextlib.redirect_stdout(Unwritable()):
            yield

    monkeypatch.setitem(globals(), "_past_capture", unwritable_stdout)
    show_timings(subprocess.CompletedProcess(
        ["bash", "suite.sh"], 0,
        stdout=f"{TIMING_HEADER} (whole seconds):\n     3 s  100%  the whole run\n",
        stderr="teardown: rm -rf of the sandbox took 0 s\n"))
    assert Unwritable.attempts >= 1, (
        "the block was never written to the stream, so nothing was tested")


@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None,
                    reason="the lane helpers and their suite are bash")
def test_a_run_without_pytests_capture_plugin_still_runs_and_shows_the_block(tmp_path):
    """`-p no:capture` removes the `capsys` fixture. The fixture that asks for
    it must not turn every test in this file into an ERROR (here the real test
    and a pure one, both of them this file's), and with nothing capturing, the
    block is on the output as it is."""
    proc, lines = run_wrapper_over(
        tmp_path, args=("-p", "no:capture"),
        tests=(_REAL_TEST,
               "test_the_timings_are_the_table_and_the_teardown_line_and_nothing_else"))
    assert proc.returncode == 0, "\n".join(lines)
    assert not any("capsys" in ln for ln in lines), "\n".join(lines)
    assert any("2 passed" in ln for ln in lines), "\n".join(lines)
    assert lines_ending(lines, "the slow section") == 1, "\n".join(lines)


def test_the_timings_are_the_table_and_the_teardown_line_and_nothing_else():
    stdout = ("== a heading ==\nok   a case\n"
              "wall time per section, longest first (whole seconds; x):\n"
              "    12 s   60%  the slow section\n"
              "    20 s  100%  the whole run\n"
              "----\n"
              "2 passed, 0 failed, 0 skipped, 0 pending\n")
    stderr = ("a note\nteardown: rm -rf of the sandbox took 3 s\n"
              "teardown: rm -rf of the sandbox FAILED after 4 s, so part of it is left\n")
    table, teardown = suite_timings(stdout, stderr)
    assert table == [
        "wall time per section, longest first (whole seconds; x):",
        "    12 s   60%  the slow section",
        "    20 s  100%  the whole run"]
    assert teardown == [
        "teardown: rm -rf of the sandbox took 3 s",
        "teardown: rm -rf of the sandbox FAILED after 4 s, so part of it is left"]
    assert suite_timings("no table here\n", "") == ([], [])


def test_a_row_of_negative_seconds_does_not_end_the_table():
    """bash's `SECONDS` can step backwards, and the suite prints the difference
    as it is: `    -9 s  -300%  <heading>`."""
    stdout = ("wall time per section, longest first (whole seconds; x):\n"
              "    12 s  400%  the slow section\n"
              "    -9 s -300%  a section the clock stepped back over\n"
              "     0 s    0%  (preamble, before the first heading)\n"
              "     3 s  100%  the whole run, from the top of this file to this table\n"
              "----\n"
              "2 passed, 0 failed, 0 skipped, 0 pending\n")
    table, _ = suite_timings(stdout, "")
    assert len(table) == 5, table
    assert table[-1].endswith("to this table"), table


def test_the_wrapper_looks_for_what_the_suite_prints():
    """The strings above are copies, and a copy nobody holds to its original
    reads as a pass that silently prints nothing. Hold them to the suite's
    own `printf`s: BOTH teardown wordings, because the wrapper takes either by
    its prefix and rewording only one of them would otherwise go unseen."""
    text = SUITE.read_text(encoding="utf-8")
    assert f"printf '{TIMING_HEADER}" in text, "the table's header moved"
    assert f"printf '{TEARDOWN_PREFIX} took " in text, (
        "the teardown line's `took` wording moved")
    assert f"printf '{TEARDOWN_PREFIX} FAILED after " in text, (
        "the teardown line's `FAILED after` wording moved")
    assert "'%6s s  %3s%%  %s'" in text, "a row of the table changed shape"
