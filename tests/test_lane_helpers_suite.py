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
import shutil
import subprocess

import pytest

from conftest import REPO, WINDOWS_SKIP

SUITE = REPO / "tests" / "test_lane_helpers.sh"

#: Generous, and not a performance claim: the suite runs real `git` against
#: real repositories several hundred times and spawns a real `sleep` for the
#: liveness cases. A CI runner under load is slower than a workstation, and a
#: timeout that fires there reads as a broken suite rather than a slow one.
TIMEOUT_SECONDS = 900


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

    proc = subprocess.run(["bash", str(SUITE)], capture_output=True, text=True,
                          check=False, cwd=str(REPO), timeout=TIMEOUT_SECONDS,
                          env=env)
    tail = proc.stdout.strip().splitlines()[-1:] or ["(no output)"]
    assert proc.returncode == 0, (
        f"tests/test_lane_helpers.sh failed ({tail[0]}):\n"
        f"{proc.stdout}\n{proc.stderr}")
    # The footer, read rather than assumed: a suite that exited 0 having run
    # nothing at all would otherwise pass this.
    assert " passed, 0 failed" in proc.stdout, proc.stdout[-2000:]
