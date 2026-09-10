# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures, and the one thing this suite needs that it does not ship.

NO NETWORK AND NO GITHUB. Every test here runs `park`, `resume` or
`openRepoTools` against BARE REPOSITORIES IN A TEMPORARY DIRECTORY, a fake
`$HOME`, and — where a fetch is under test — a fake `gh` first on `$PATH` with
a `curl` that refuses. Nothing in this suite may create a real repository; if a
test ever needs a real `gh`, it is the wrong test.

THE STANDARD IS MOUNTED, NOT COPIED. `tests/test_park_resume_commands.py`
builds estates out of eight of openRepoShape's own files, and it reads them out
of the `upstream/openRepoShape` submodule this repository pins in
`contracts/openreposhape-pin.yaml`. A clone made WITHOUT `--recurse-submodules`
therefore has no template bytes to copy — so those tests SKIP, naming the one
command that fixes it. They never fail: a fork's first `pytest` going red on a
missing submodule is a fork nobody finishes.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The pinned openRepoShape checkout. Every path this suite reads out of the
#: standard hangs off this one name, so a bump of the pin moves one line in
#: `contracts/openreposhape-pin.yaml` and the gitlink beside it, and nothing
#: here.
UPSTREAM = REPO / "upstream" / "openRepoShape"

#: THE TESTS THAT NEED THE STANDARD'S REAL BYTES. `scripts/repo_shape.py` is
#: the probe rather than the directory itself, because `git clone` without
#: `--recurse-submodules` leaves an EMPTY `upstream/openRepoShape/` behind —
#: the directory exists and holds nothing, so `is_dir()` would answer yes and
#: the tests would fail on a missing file instead of skipping.
NEEDS_UPSTREAM = pytest.mark.skipif(
    not (UPSTREAM / "scripts" / "repo_shape.py").is_file(),
    reason="the pinned openRepoShape is not checked out; "
           "run `git submodule update --init upstream/openRepoShape`")

#: THE TESTS THAT CANNOT RUN ON WINDOWS. Two shapes of test wear this: one that
#: runs `bash`, and one that puts a `#!`-shebang script named `gh` on PATH and
#: expects the operating system to execute it. Windows has neither — `bash.exe`
#: IS on the GitHub runner, so a `shutil.which("bash")` guard does not fire,
#: but `park`, `resume` and `openRepoTools` are bash scripts that run `make` in
#: a root which execs a shebang script, and a shebang means nothing to
#: CreateProcess. Skipping is honest because there is no Windows twin to run
#: instead: these three files are bash, and on Windows the way in is WSL2,
#: exactly as it is for openRepoShape's own `setup.sh`. What the Windows job
#: still proves is the checkout and the hygiene tests, which need no shell.
#: A shared `skipif` object rather than a named marker because there is no
#: pytest.ini to register one in, and an unregistered marker is a warning.
WINDOWS_SKIP = pytest.mark.skipif(
    os.name == "nt",
    reason="needs a POSIX shell and shebang execution; on Windows the way in "
           "is WSL2, as it is for openRepoShape's setup.sh")


def rmtree(path: Path) -> None:
    """`shutil.rmtree` that also works over a git object store on Windows.

    Git writes loose objects and packs READ-ONLY, and Windows refuses to
    unlink a read-only file — so a plain `rmtree` over a checkout raises
    PermissionError there and succeeds everywhere else. The handler clears the
    read-only bit and retries the one call that failed. `onerror` rather than
    `onexc`: the newer spelling is 3.12+, and this standard runs on 3.9.
    """
    def clear_readonly(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=clear_readonly)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=False)
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} in {cwd} failed:\n"
                             f"{proc.stderr}{proc.stdout}")
    return proc
