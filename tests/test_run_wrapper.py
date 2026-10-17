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

And what #72 asked of the `mkdir` lock itself: a run that cannot record its
pid in the lock does not start, and a run's exit removes the lock only while
that pid is still the one inside.

THE SUITE ITSELF IS A STUB. A fake `python3` records how it was called and
sleeps or exits on cue, and a fake `pgrep` reports no other run - the real one
would see THIS suite's own `python3 -m pytest` and wait for ever.
"""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import sys
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
if [ -n "${FAKE_SUITE_READ:-}" ]; then
  # A DEBUGGER'S PROMPT: it reads the terminal, as `--pdb` would.
  printf 'prompt>\n'
  read -r line
  printf 'got: %s\n' "$line"
  exit 0
fi
if [ -n "${FAKE_SUITE_IGNORE_TERM:-}" ]; then
  # A LEADER THAT IGNORES TERM (#170 item 3), and children that inherit it.
  trap '' TERM
  : > "$FAKE_SUITE_LOG.started"
  while :; do sleep 1; done
fi
if [ -n "${FAKE_SUITE_LEAVE:-}" ]; then
  # A CHILD LEFT RUNNING when the suite returns (#170 G14), deaf to the hangup
  # its session leader's exit sends, so only the wrapper can stop it.
  ( trap '' HUP; exec sleep 300 ) &
  printf '%s\n' "$!" > "$FAKE_SUITE_LOG.child"
  exit 0
fi
if [ -n "${FAKE_SUITE_TAKEOVER:-}" ]; then
  # THE LOCK IS TAKEN OVER WHILE THIS RUN HOLDS IT (#72 item 2): claimed as a
  # waiter that read this holder as gone claims it, and made again with that
  # waiter's pid inside.
  mv "$FAKE_SUITE_TAKEOVER" "$FAKE_SUITE_TAKEOVER.claimed" &&
    rm -rf "$FAKE_SUITE_TAKEOVER.claimed" &&
    mkdir "$FAKE_SUITE_TAKEOVER" &&
    printf '%s\\n' "$FAKE_SUITE_OTHER" > "$FAKE_SUITE_TAKEOVER/pid" || exit 99
  exit 0
fi
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

# THE REAL `mkdir`, and then - for the workstation's lock directory alone - a
# DIRECTORY where the holder's pid file goes, so the wrapper's write of its pid
# fails (#72 item 1) the same way on every platform and for every user, root
# included, where a directory it cannot write would not stop root.
FAKE_MKDIR = """#!/bin/sh
REAL_MKDIR "$@" || exit
case "$1" in
  *.lock.d) REAL_MKDIR "$1/pid" || exit 99 ;;
esac
exit 0
"""


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
    # THE LOCK IS THE WORKSTATION'S, under the caller's TMPDIR and not the
    # run's: the `flock` file where there is `flock`, and on macOS, which has
    # none, the `mkdir` lock beside it - released by the exit.
    if shutil.which("flock"):
        assert (box.lockdir / "openrepotools-pytest.lock").exists(), (
            "the lock is the workstation's, under the caller's TMPDIR, not the run's")
    else:
        assert not (box.lockdir / "openrepotools-pytest.lock.d").exists(), "the lock was kept"


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
        # NOR A COPY OF IT (#72 item 2): the lock is released by renaming it
        # to a name only this run uses, and that copy goes too.
        assert os.listdir(box.lockdir) == [], os.listdir(box.lockdir)


def test_a_run_that_cannot_record_its_pid_in_the_mkdir_lock_does_not_start(tmp_path):
    """#72 item 1: the holder's pid write was `|| :`, so a run that could not
    write it entered the suite anyway - holding a lock every waiter reads as
    stale, claims after three polls and runs beside. A pid that is not there
    to be read is a refusal before the suite: the run releases the directory
    it made and exits 1, naming the path."""
    box = Box(tmp_path, flock=False)
    fake = box.fakebin / "mkdir"
    real = os.readlink(fake)
    fake.unlink()
    fake.write_text(FAKE_MKDIR.replace("REAL_MKDIR", shlex.quote(real)))
    fake.chmod(0o755)
    lock = box.lockdir / "openrepotools-pytest.lock.d"
    proc = box.popen()
    err = box.finish(proc)
    assert not box.log.exists(), "the suite started with no pid in its lock"
    assert proc.returncode == 1, err
    assert f"cannot record this run's pid in {lock}/pid" in err, err
    assert not lock.exists(), "a run that did not start kept the lock"
    assert os.listdir(box.lockdir) == [], os.listdir(box.lockdir)
    assert box.runs() == [], "a run that did not start made a run root"


def test_a_holder_whose_mkdir_lock_was_taken_over_leaves_the_new_lock(tmp_path):
    """#72 item 2: a waiter that reads a live holder as gone claims the lock
    and makes it again with its own pid inside, and the old holder's EXIT
    trap then removed the path - the NEW holder's lock. The trap removes the
    lock only while it still carries this run's pid."""
    box = Box(tmp_path, flock=False)
    lock = box.lockdir / "openrepotools-pytest.lock.d"
    other = str(os.getpid())                     # a live run that is not this one
    proc = box.popen(FAKE_SUITE_TAKEOVER=str(lock), FAKE_SUITE_OTHER=other)
    err = box.finish(proc)
    assert proc.returncode == 0, err
    assert lock.is_dir(), "the old holder's exit removed the new holder's lock"
    assert (lock / "pid").read_text() == f"{other}\n"
    assert os.listdir(box.lockdir) == [lock.name], os.listdir(box.lockdir)
    assert box.runs() == [], "the run root outlived the run"


@pytest.mark.skipif(not hasattr(os, "openpty") or sys.platform.startswith("win"),
                    reason="needs a pseudo-terminal")
def test_a_suite_that_reads_the_terminal_is_not_stopped(tmp_path):
    """Adversarial review B7: with a terminal on stdin the suite runs in the
    foreground, in the terminal's process group - a debugger's prompt reads
    it. A background group would be stopped by SIGTTIN and the wrapper would
    wait on it for ever, holding the workstation's lock."""
    import pty
    import select
    box = Box(tmp_path)
    env = dict(box.env, FAKE_SUITE_READ="1")
    pid, master = pty.fork()
    if pid == 0:                                 # the child: a session on the pty
        try:
            os.execve(shutil.which("bash") or "/bin/bash", ["bash", str(WRAPPER)], env)
        finally:
            os._exit(127)
    seen, sent, status, finished = b"", False, None, False
    deadline = time.time() + 30
    try:
        while time.time() < deadline:
            ready, _w, _x = select.select([master], [], [], 0.2)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    chunk = b""
                seen += chunk
                if b"prompt>" in seen and not sent:
                    os.write(master, b"hello\n")
                    sent = True
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                finished = True
                break
        else:
            raise AssertionError(f"the wrapper hung on a suite reading the terminal: {seen!r}")
    finally:
        if not finished:
            try:
                os.killpg(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            except OSError:
                pass
        os.close(master)
    assert b"got: hello" in seen, seen
    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, (status, seen)
    assert box.runs() == [], "the run root outlived the run"


def test_a_leader_that_ignores_term_is_killed_at_the_deadline(tmp_path):
    """#170 item 3: `stop_group` reaped the leader with an unbounded `wait`
    BEFORE its ten-second grace loop, so a leader that traps or ignores TERM
    held the wrapper - and the workstation's lock - for ever, and the KILL
    was never reached."""
    box = Box(tmp_path)
    proc = box.popen(FAKE_SUITE_IGNORE_TERM="1")
    leader = 0
    try:
        box.wait_started()
        leader = int(box.recorded()["pid"])
        started = time.time()
        proc.send_signal(signal.SIGTERM)
        box.finish(proc, timeout=40)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if leader:
            try:
                os.killpg(leader, signal.SIGKILL)
            except OSError:
                pass
    assert proc.returncode == 143
    assert time.time() - started < 20, "the wrapper waited past its KILL deadline"
    assert not _running(leader), "the leader outlived its wrapper"
    assert box.runs() == [], "the run root outlived the run"


@pytest.mark.parametrize("form", [["--basetemp", "ELSEWHERE"], ["--basetemp=ELSEWHERE"]])
def test_a_callers_basetemp_is_refused(tmp_path, form):
    """#170 G8: pytest takes the LAST `--basetemp`, and a caller's, forwarded
    after the wrapper's, won - its temporary files landed outside the run root
    the EXIT trap removes. It is refused before any lock is taken."""
    box = Box(tmp_path)
    elsewhere = str(tmp_path / "elsewhere")
    proc = box.popen(*[a.replace("ELSEWHERE", elsewhere) for a in form])
    err = box.finish(proc)
    assert proc.returncode == 64, err
    assert "--basetemp is the wrapper's own" in err
    assert not box.log.exists(), "the suite ran"
    assert not Path(elsewhere).exists()


def _on_a_terminal(box, env: dict, timeout: float = 30) -> tuple:
    """Run the wrapper with a pseudo-terminal on its stdin; (wait status,
    seconds it took)."""
    import pty
    import select
    started = time.time()
    pid, master = pty.fork()
    if pid == 0:
        try:
            os.execve(shutil.which("bash") or "/bin/bash", ["bash", str(WRAPPER)], env)
        finally:
            os._exit(127)
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            ready, _w, _x = select.select([master], [], [], 0.05)
            if ready:
                try:
                    os.read(master, 4096)
                except OSError:
                    pass
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                return status, time.time() - started
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except OSError:
            pass
        raise AssertionError("the wrapper did not finish")
    finally:
        os.close(master)


NEEDS_A_PTY = pytest.mark.skipif(not hasattr(os, "openpty") or sys.platform.startswith("win"),
                                 reason="needs a pseudo-terminal")


@NEEDS_A_PTY
def test_what_a_suite_on_the_terminal_leaves_running_is_stopped(tmp_path):
    """#170 G14: with a terminal on stdin the suite runs in the foreground, in
    the wrapper's own process group, and no group id was kept - a child it
    left running was not stopped before the run root went and the lock was
    released. The group's members are read before the suite starts; what is
    there afterwards that was not is stopped."""
    box = Box(tmp_path)
    child = 0
    try:
        status, _took = _on_a_terminal(box, dict(box.env, FAKE_SUITE_LEAVE="1"))
        child = int(Path(str(box.log) + ".child").read_text().strip())
        assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, status
        assert not _running(child), "a process the suite left running outlived its wrapper"
        assert box.runs() == [], "the run root outlived the run"
    finally:
        if child and _running(child):
            os.kill(child, signal.SIGKILL)


@NEEDS_A_PTY
def test_a_terminal_run_that_leaves_nothing_waits_for_nothing(tmp_path):
    """#179 Copilot round 2: the stray scan ran in a command substitution, so
    its own subshell, `ps` and `awk` were members of the group that were not
    there before - every scan found "strays", and every terminal run waited
    out the whole ten-second deadline after a suite that left nothing."""
    box = Box(tmp_path)
    status, took = _on_a_terminal(box, dict(box.env))
    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, status
    assert took < 8, f"the wrapper took {took:.1f} s after a suite that left nothing running"
    assert box.runs() == [], "the run root outlived the run"


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
