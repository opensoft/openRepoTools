# SPDX-License-Identifier: Apache-2.0
"""`tests/run.sh` leaves nothing beside the code (opensoft/openRepoTools#162).

The wrapper's lock is `test_repo_hygiene.py`'s to pin; what is held here is
what #162 added around it:

  * bytecode goes to `${XDG_CACHE_HOME:-$HOME/.cache}/openRepoTools/pycache`
    and pytest's cache is off, so no `__pycache__` or `.pytest_cache` lands in
    a worktree;
  * every temporary directory of a run is under ONE run root,
    `${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/tmp/<UTC>-<pid>/`,
    and the run root is gone when the run ends - however it ends: a pass, a
    failure, a TERM or an INT in the middle of the suite;
  * the lock stays where every lane names it, computed BEFORE `TMPDIR` moves;
  * the `mkdir` lock (macOS has no `flock`) is released the same way;
  * the repository's virtual environment is used when it has pytest, with the
    command line still reading `python3 -m pytest`.

THE SUITE ITSELF IS A STUB. A fake `python3` records how it was called and
sleeps or exits on cue, and a fake `pgrep` reports no other run - the real one
would see THIS suite's own `python3 -m pytest` and wait for ever.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(shutil.which("bash") is None,
                                               reason="the wrapper is bash")]

WRAPPER = REPO / "tests" / "run.sh"

FAKE_SUITE = """#!/bin/sh
# Records its own argv, the two environment values the wrapper sets, its pid
# and where it was found, then sleeps or exits on cue.
{
  printf 'argv0 %s\\n' "$0"
  for a in "$@"; do printf 'arg %s\\n' "$a"; done
  printf 'TMPDIR %s\\n' "$TMPDIR"
  printf 'PYTHONPYCACHEPREFIX %s\\n' "$PYTHONPYCACHEPREFIX"
  printf 'pid %s\\n' "$$"
} > "$FAKE_SUITE_LOG"
: > "$TMPDIR/the-suite-wrote-here"
if [ -n "${FAKE_SUITE_SLEEP:-}" ]; then
  # A CHILD OF ITS OWN, as pytest waits on a shell suite or a `git`: the
  # wrapper must stop it too, not only the process it started.
  sleep "$FAKE_SUITE_SLEEP" &
  printf '%s\n' "$!" > "$FAKE_SUITE_LOG.child"
  : > "$FAKE_SUITE_LOG.started"
  wait
  exit 0
fi
exit "${FAKE_SUITE_RC:-0}"
"""

FAKE_PGREP = "#!/bin/sh\nexit 1\n"


class Box:
    def __init__(self, root: Path, flock: bool = True):
        self.root = root
        self.fakebin = root / "fakebin"
        self.fakebin.mkdir()
        self.lockdir = root / "locktmp"
        self.lockdir.mkdir()
        self.state = root / "state"
        self.cache = root / "cache"
        self.log = root / "suite.log"
        for name, text in (("python3", FAKE_SUITE), ("pgrep", FAKE_PGREP)):
            (self.fakebin / name).write_text(text)
            (self.fakebin / name).chmod(0o755)
        if flock:
            path = f"{self.fakebin}{os.pathsep}{os.environ.get('PATH', '')}"
        else:
            # NO `flock` ON THIS PATH: the wrapper takes its `mkdir` lock, the
            # one macOS uses. Every other tool it calls is linked in by name.
            for tool in ("dirname", "awk", "mkdir", "cat", "mv", "rm", "sleep", "date",
                         "chmod", "ps"):
                found = shutil.which(tool)
                assert found, tool
                (self.fakebin / tool).symlink_to(found)
            path = str(self.fakebin)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("XDG_", "PYTHON", "FAKE_"))}
        self.env.update(PATH=path, TMPDIR=str(self.lockdir), XDG_STATE_HOME=str(self.state),
                        XDG_CACHE_HOME=str(self.cache), HOME=str(root / "home"),
                        FAKE_SUITE_LOG=str(self.log))

    def popen(self, *args, **env) -> subprocess.Popen:
        """The wrapper, its output to FILES: a pipe is held open by every
        process that inherited it, and `communicate` waits for all of them."""
        child = dict(self.env)
        child.update(env)
        self.out = open(self.root / "wrapper.out", "w")
        self.err = open(self.root / "wrapper.err", "w")
        return subprocess.Popen([shutil.which("bash") or "bash", str(WRAPPER), *args],
                                env=child, stdout=self.out, stderr=self.err,
                                stdin=subprocess.DEVNULL)

    def finish(self, proc: subprocess.Popen, timeout: float = 60) -> str:
        proc.wait(timeout=timeout)
        self.out.close()
        self.err.close()
        return (self.root / "wrapper.err").read_text()

    def recorded(self) -> dict:
        out: dict = {"arg": []}
        for line in self.log.read_text().splitlines():
            key, _, value = line.partition(" ")
            if key == "arg":
                out["arg"].append(value)
            else:
                out[key] = value
        return out

    def runs(self) -> list:
        base = self.state / "openRepoTools" / "tmp"
        return sorted(base.iterdir()) if base.is_dir() else []

    def wait_started(self, timeout: float = 30) -> None:
        deadline = time.time() + timeout
        marker = Path(str(self.log) + ".started")
        while time.time() < deadline:
            if marker.exists():
                return
            time.sleep(0.1)
        raise AssertionError("the stub suite never started")


def test_a_run_relocates_bytecode_caches_and_temp_and_leaves_none_of_it(tmp_path):
    box = Box(tmp_path)
    proc = box.popen("-k", "lane_worktrees", FAKE_SUITE_RC="5")
    err = box.finish(proc)
    assert proc.returncode == 5, err
    rec = box.recorded()
    run_root = Path(rec["TMPDIR"]).parent
    assert run_root.parent == box.state / "openRepoTools" / "tmp"
    assert run_root.name.endswith(f"-{proc.pid}"), run_root.name
    assert rec["PYTHONPYCACHEPREFIX"] == str(box.cache / "openRepoTools" / "pycache")
    assert rec["arg"][:5] == ["-m", "pytest", "tests", "-q", "-p"], rec["arg"]
    assert "no:cacheprovider" in rec["arg"]
    assert f"--basetemp={run_root}/basetemp" in rec["arg"]
    assert rec["arg"][-2:] == ["-k", "lane_worktrees"]
    assert not run_root.exists(), "the run root outlived the run"
    assert box.runs() == []
    assert (box.lockdir / "openrepotools-pytest.lock").exists(), (
        "the lock is the workstation's, under the caller's TMPDIR, not the run's")


@pytest.mark.parametrize("sig,rc", [(signal.SIGTERM, 143), (signal.SIGINT, 130)])
@pytest.mark.parametrize("flock", [True, False], ids=["flock", "mkdir-lock"])
def test_a_killed_run_removes_its_run_root_and_stops_the_suite(tmp_path, sig, rc, flock):
    """THE TRAP, PROVED: the wrapper is signalled while the suite is running.
    It stops the suite, removes the run root (and, on the `mkdir` path, the
    lock), and exits with the signal's code - not after the suite would have
    finished, which is what a foreground child would have made it do."""
    if flock and shutil.which("flock") is None:
        pytest.skip("this host has no flock; the mkdir-lock case covers it")
    box = Box(tmp_path, flock=flock)
    proc = box.popen(FAKE_SUITE_SLEEP="120")
    try:
        box.wait_started()
        rec = box.recorded()
        run_root = Path(rec["TMPDIR"]).parent
        assert (run_root / "tmp" / "the-suite-wrote-here").exists()
        if not flock:
            assert (box.lockdir / "openrepotools-pytest.lock.d").is_dir()
        started = time.time()
        proc.send_signal(sig)
        box.finish(proc, timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert proc.returncode == rc
    assert time.time() - started < 20, "the trap waited for the suite"
    assert not run_root.exists(), "the run root outlived a killed run"
    child = Path(str(box.log) + ".child").read_text().strip()
    for pid, what in ((int(rec["pid"]), "the suite"), (int(child), "the suite's own child")):
        deadline = time.time() + 10
        while time.time() < deadline and _running(pid):
            time.sleep(0.1)
        if _running(pid):
            os.kill(pid, signal.SIGKILL)
            raise AssertionError(f"{what} outlived its wrapper")
    if not flock:
        assert not (box.lockdir / "openrepotools-pytest.lock.d").exists(), "the lock was kept"


def _running(pid: int) -> bool:
    """Alive and not a zombie: an orphan's zombie answers `kill -0` until
    whoever adopted it reaps it."""
    proc = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    state = proc.stdout.strip()
    return bool(state) and not state.startswith("Z")


def test_the_repository_venv_is_used_when_it_has_pytest(tmp_path):
    box = Box(tmp_path)
    venv_bin = box.cache / "openRepoTools" / "venvs" / "openRepoTools" / "bin"
    venv_bin.mkdir(parents=True)
    stub = venv_bin / "python3"
    stub.write_text("#!/bin/sh\ncase \"$1\" in -c) exit 0 ;; esac\nexec "
                    f"{box.fakebin / 'python3'} \"$@\"\n")
    stub.chmod(0o755)
    proc = box.popen()
    err = box.finish(proc)
    assert proc.returncode == 0, err
    assert "runs from the repository venv" in err
    assert box.recorded()["arg"][:2] == ["-m", "pytest"]
    assert box.runs() == []
