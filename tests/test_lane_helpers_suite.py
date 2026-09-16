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
message, which is what a person reading a red CI job actually needs.

IT TOUCHES NOTHING REAL. The suite redirects `$HOME`, `$TMPDIR`,
`$AGENT_PROTOCOL_ROOT` and `$OPENREPOTOOLS_BIN_DIR` into a `mktemp -d` sandbox
of its own, seeds a bare repository plus two clones there, fakes `tmux` and
`claude` on `PATH`, and exports `LANES_NO_GITHUB=1` so no case can reach
GitHub. Its own last assertions are the ones that check that — see the foot of
that file.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess

import pytest

from conftest import REPO, WINDOWS_SKIP

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
#: THE HONEST FIX IS THE SUITE'S DURATION AND NOT THIS NUMBER — one bash file
#: that runs real `git` several thousand times, serially, for 45 minutes — and
#: it is opensoft/openRepoTools#77. This is the cap moving out of that work's
#: way, not a decision that 45 minutes is fine.
#:
#: The job itself has no `timeout-minutes` in `.github/workflows/tests.yml`, so
#: nothing under it bites before this does; GitHub's own default is 360 min.
TIMEOUT_SECONDS = 3600


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
def test_the_liveness_fixture_outlives_the_suite_timeout():
    hit = [ln for ln in SUITE.read_text(encoding="utf-8").splitlines()
           if "LIVE_PID=$!" in ln]
    assert len(hit) == 1, (
        "expected exactly one liveness fixture in tests/test_lane_helpers.sh, "
        f"found {len(hit)}: {hit}")
    m = re.search(r"\bsleep\s+(\d+)\s*&\s*LIVE_PID=\$!", hit[0])
    assert m, f"the liveness fixture is no longer a bounded sleep: {hit[0]!r}"
    bound = int(m.group(1))
    assert bound > TIMEOUT_SECONDS, (
        f"the liveness fixture is bounded at {bound}s while this wrapper lets "
        f"the suite run for TIMEOUT_SECONDS={TIMEOUT_SECONDS}s, so the suite is "
        "licensed to outlive its own evidence: every liveness case after "
        f"{bound}s would read 'no live holder' and say nothing about why. "
        "Raise the sleep in tests/test_lane_helpers.sh above this bound.")


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
                 "OPENREPOTOOLS_BIN_DIR", "PROJECTS_ROOT"):
        env.pop(name, None)

    # `errors="replace"`, because the thing this wrapper exists to print is the
    # TRANSCRIPT, and a decode that raises loses all of it. The suite renders
    # its own failures with bash substrings for that reason (R-A9-11), so a
    # stray byte here should be impossible — and if one ever gets through, a
    # `\ufffd` in one line is a readable result where `UnicodeDecodeError` is
    # none at all. Measured: at `dcf1027` one truncated em dash cost the whole
    # 998-line transcript on the macOS job.
    proc = subprocess.run(["bash", str(SUITE)], capture_output=True,
                          encoding="utf-8", errors="replace",
                          check=False, cwd=str(REPO), timeout=TIMEOUT_SECONDS,
                          env=env)
    tail = proc.stdout.strip().splitlines()[-1:] or ["(no output)"]
    assert proc.returncode == 0, (
        f"tests/test_lane_helpers.sh failed ({tail[0]}):\n"
        f"{proc.stdout}\n{proc.stderr}")
    # The footer, read rather than assumed: a suite that exited 0 having run
    # nothing at all would otherwise pass this.
    assert " passed, 0 failed" in proc.stdout, proc.stdout[-2000:]
