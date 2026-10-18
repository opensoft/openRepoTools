# SPDX-License-Identifier: Apache-2.0
"""Amendment 23 S2's locks: the lane checkout's mutex and the workstation's.

* A live holder is never aged out: the mutex's ten-minute age test yields to
  its pid test, so a write that is still running keeps its lock (S2).
* A pid does not cross a pid namespace (Amendment 18), so the pid file records
  `<pid> <container> <host>`, and a holder in another container is judged by
  the lock's age alone — an age its holder refreshes before every network call.
* A lock this very process took before an `exec` is still its own (S4's replay
  re-runs the verb with the lock held); an inherited marker is not.
* The lifecycle, restart and tree sidecars, and `publish-handoff`, share ONE
  lock beside the lane checkouts, `<W>-lanes/.lane-state.lock` (ort186 Q3), and
  no lock is ever taken in W.

The sandbox is the real `lanes-edit.sh`, with `LANES_CONTAINER` and
`LANES_HOST` pinned so "this container" means the same thing on every runner.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

LANE = "repoLK-1"
REGISTER = "lanes/LANES.md"
UUID = "a23b0001-1c1c-4000-8000-a23b00011c1c"
ME = "bench-a hosta"            # LANES_CONTAINER and LANES_HOST, below
#: How long a waiter is watched to prove it is still waiting. The helper polls
#: once a second, so a writer that was going to take the lock has long done so.
WATCH = 4

SCRUBBED_PREFIXES = ("LANES_", "LANE_START_", "CLAUDE_", "OPENREPOTOOLS_",
                     "FAKE_", "GIT_", "TMUX")
SCRUBBED = {"AGENT_PROTOCOL_ROOT", "PROJECTS_ROOT", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME"}

REFUSE = """#!/usr/bin/env bash
printf 'FAKE %s REFUSED: %s -- this suite reaches no real surface\\n' "${0##*/}" "$*" >&2
exit 90
"""


def _row(lane: str, state: str = "LIVE · seeded") -> str:
    return (f"| `{lane}` | harness `{UUID}` | Eagle / test / tester | 2026-10-17T00:00Z "
            f"| — | handoffs/repoLK/{lane}.md | {state} |")


class Box:
    """A bare origin, W cloned from it, and the workspace.yaml naming W."""

    def __init__(self, root: Path) -> None:
        root = Path(os.path.realpath(root))
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.home = root / "home"
        self.origin = root / "origin.git"
        self.w = self.home / "projects" / "brett-wip"
        self.lanes_root = self.home / "projects" / "brett-wip-lanes"
        self.state = root / "state"
        self.fakebin = root / "fakebin"
        for d in (self.home / ".agents", self.home / "projects", root / "tmp", self.fakebin):
            d.mkdir(parents=True, exist_ok=True)
        for name in ("gh", "tmux"):
            (self.fakebin / name).write_text(REFUSE, encoding="utf-8")
            (self.fakebin / name).chmod(0o755)
        env = {k: v for k, v in os.environ.items()
               if k not in SCRUBBED and not k.startswith(SCRUBBED_PREFIXES)}
        env.update({
            "HOME": str(self.home),
            "TMPDIR": str(root / "tmp"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "PATH": f"{self.fakebin}{os.pathsep}{env.get('PATH', '')}",
            "AGENT_PROTOCOL_ROOT": str(self.home / ".agents"),
            "LANES_WORKSTATION": "Eagle",
            "LANES_HOST": "hosta",
            "LANES_CONTAINER": "bench-a",
            "LANES_NO_GITHUB": "1",
            "LANES_INDEX": "off",
            "LANE_WORKTREES_REPORT": "off",
            "LANES_LANE_STATE_ROOT": str(self.state),
            "GIT_AUTHOR_NAME": "a23 tests",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "a23 tests",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        self.env = env
        self.git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.quiet(self.origin, bare=True)
        seed = root / "seed"
        self.git("clone", "-q", str(self.origin), str(seed))
        self.quiet(seed)
        self.write(seed, REGISTER,
                   "# LANES.md -- the sandbox register\n\n"
                   "| lane | session id | workstation / env / user | started (UTC) "
                   "| objects owned | handoff path | state |\n"
                   "|---|---|---|---|---|---|---|\n"
                   f"{_row(LANE)}\n{_row('repoLK-2')}\n")
        self.git("-C", str(seed), "add", "--", REGISTER)
        self.git("-C", str(seed), "commit", "-q", "-m", "seed")
        self.git("-C", str(seed), "push", "-q", "origin", "main")
        self.git("clone", "-q", str(self.origin), str(self.w))
        self.quiet(self.w)
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.w}\n", encoding="utf-8")

    def quiet(self, repo: Path, *, bare: bool = False) -> None:
        where = ["--git-dir", str(repo)] if bare else ["-C", str(repo)]
        self.git(*where, "config", "gc.auto", "0")
        self.git(*where, "config", "maintenance.auto", "false")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    @staticmethod
    def write(checkout: Path, rel: str, text: str) -> None:
        path = checkout / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def cmd(self, *args: str) -> list[str]:
        return ["bash", str(REPO / "lanes-edit.sh"), *args]

    def helper(self, *args: str, timeout: int = 120, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(self.cmd(*args), env=dict(self.env, **extra), cwd=str(self.root),
                              capture_output=True, text=True, timeout=timeout, check=False)

    def popen(self, *args: str, **extra: str) -> subprocess.Popen:
        return subprocess.Popen(self.cmd(*args), env=dict(self.env, **extra), cwd=str(self.root),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def stamp(self, words: str, **extra: str) -> subprocess.CompletedProcess:
        return self.helper("set-row-state", LANE, f"LIVE · {words}", **extra)

    def checkout(self) -> Path:
        """The lane's checkout, made by an ordinary first write."""
        c = self.lanes_root / LANE
        if not c.exists():
            made = self.stamp("made the checkout")
            assert made.returncode == 0, (made.stdout, made.stderr)
        return c

    def lock(self) -> Path:
        return self.checkout() / "lanes" / ".lanes-edit.lock"

    def origin_register(self) -> str:
        return self.git("--git-dir", str(self.origin), "show", f"main:{REGISTER}")


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def hold(lock: Path, pid_line: str, *, age_minutes: float = 0) -> None:
    lock.mkdir(parents=True)
    (lock / "pid").write_text(pid_line + "\n", encoding="utf-8")
    if age_minutes:
        then = time.time() - age_minutes * 60
        os.utime(lock, (then, then))


def still_waiting(proc: subprocess.Popen) -> bool:
    time.sleep(WATCH)
    return proc.poll() is None


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
    proc.communicate(timeout=30)


def gone_pid() -> int:
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


# ----------------------------------------------------- the checkout's lock

def test_live_holder_is_not_aged_out(box: Box):
    lock = box.lock()
    holder = subprocess.Popen(["sleep", "300"])
    try:
        hold(lock, f"{holder.pid} {ME}", age_minutes=20)
        writer = box.popen("set-row-state", LANE, "LIVE · after the holder")
        assert still_waiting(writer), \
            "a lock held by a LIVE process in this container is never aged out, however old"
        assert (lock / "pid").read_text(encoding="utf-8") == f"{holder.pid} {ME}\n"
    finally:
        holder.kill()
        holder.wait()
    out, err = writer.communicate(timeout=90)
    assert writer.returncode == 0, (out, err)
    assert f"taking over {lock}" in err and f"(pid {holder.pid}) is gone" in err, err
    assert " · after the holder |" in box.origin_register()


@pytest.mark.parametrize("line", ["{pid} " + ME, "{pid}"], ids=["pid-container-host", "pid-only"])
def test_dead_holder_is_taken_over(box: Box, line: str):
    lock = box.lock()
    dead = gone_pid()
    hold(lock, line.format(pid=dead))
    result = box.stamp("after a dead holder", timeout=45)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert f"(pid {dead}) is gone" in result.stderr, result.stderr
    assert not lock.exists(), "the writer released the lock it took over"
    assert " · after a dead holder |" in box.origin_register()


def test_a_lock_naming_no_holder_is_judged_by_its_age(box: Box):
    """A LOCK WITH NO PID names nobody a pid test could ask about, so its age
    decides: it is held while fresh, and taken over once ten minutes old."""
    lock = box.lock()
    lock.mkdir(parents=True)
    writer = box.popen("set-row-state", LANE, "LIVE · never written")
    assert still_waiting(writer), "a fresh lock that names no holder is held"
    stop(writer)
    then = time.time() - 11 * 60
    os.utime(lock, (then, then))
    result = box.stamp("after a lock that named nobody", timeout=45)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "names no holder and is over ten minutes old" in result.stderr, result.stderr
    assert " · after a lock that named nobody |" in box.origin_register()


def test_lock_survives_exec(box: Box):
    c = box.checkout()
    lock = c / "lanes" / ".lanes-edit.lock"
    script = box.root / "held-across-exec"
    script.write_text(f"""#!/usr/bin/env bash
# THIS process takes the checkout's lock and then BECOMES lanes-edit.sh, as
# S4's replay does: same pid, the lock naming it, LANES__PID its own.
mkdir '{lock}' && printf '%s {ME}\\n' "$$" > '{lock}/pid' || exit 99
export LANES__CHECKOUT_LANE='{LANE}' LANES__PID="$$"
export LANES_REPO='{c}' LANES_DIR='{c}/lanes' LANES_FILE='{c}/lanes/LANES.md'
exec bash '{REPO / "lanes-edit.sh"}' set-row-state '{LANE}' 'LIVE · held across exec'
""", encoding="utf-8")
    script.chmod(0o755)
    result = subprocess.run([str(script)], env=box.env, cwd=str(box.root), capture_output=True,
                            text=True, timeout=45, check=False)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "taking over" not in result.stderr
    assert not lock.exists(), "the lock is released at the end, as any holder's is"
    assert " · held across exec |" in box.origin_register()


@pytest.mark.parametrize("how", ["inherited marker", "own pid, no marker"])
def test_a_lock_naming_a_pid_is_not_adopted_without_the_marker(box: Box, how: str):
    c = box.checkout()
    lock = c / "lanes" / ".lanes-edit.lock"
    run = f"bash '{REPO / 'lanes-edit.sh'}' set-row-state '{LANE}' 'LIVE · never written'"
    if how == "inherited marker":
        # A CHILD of the holder inherits LANES__PID naming its parent: not its own.
        tail = f"""export LANES__CHECKOUT_LANE='{LANE}' LANES__PID="$$"
export LANES_REPO='{c}' LANES_DIR='{c}/lanes' LANES_FILE='{c}/lanes/LANES.md'
{run} & child=$!"""
    else:
        # The holder's own pid, and no marker: a reused pid, which waits.
        tail = f"""LANES_REPO='{c}' exec {run}"""
    script = box.root / "not-adopted"
    script.write_text(f"""#!/usr/bin/env bash
mkdir '{lock}' && printf '%s {ME}\\n' "$$" > '{lock}/pid' || exit 99
{tail}
sleep {WATCH}
if kill -0 "$child" 2>/dev/null; then printf 'WAITING\\n'; kill "$child"; fi
wait "$child" 2>/dev/null
exit 0
""", encoding="utf-8")
    script.chmod(0o755)
    before = box.origin_register()
    proc = subprocess.Popen([str(script)], env=box.env, cwd=str(box.root),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if how == "inherited marker":
        out, err = proc.communicate(timeout=60)
        assert "WAITING" in out, (out, err)
    else:
        assert still_waiting(proc), "its own pid in the lock is not its own lock without the marker"
        stop(proc)
    assert box.origin_register() == before, "nothing was written by a process that did not hold the lock"


def test_other_container_holder_judged_by_heartbeat_age(box: Box):
    lock = box.lock()
    # A pid that is ALIVE here — this test's own — recorded by another
    # container: `kill -0` here says nothing about it, so only the age counts.
    hold(lock, f"{os.getpid()} bench-b hosta")
    writer = box.popen("set-row-state", LANE, "LIVE · never written")
    assert still_waiting(writer), "a fresh lock from another container is held"
    stop(writer)
    then = time.time() - 11 * 60
    os.utime(lock, (then, then))
    result = box.stamp("after another container went quiet", timeout=45)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "container bench-b on hosta" in result.stderr and "ten minutes" in result.stderr, result.stderr
    assert " · after another container went quiet |" in box.origin_register()


def test_holder_refreshes_its_lock_before_every_network_call(box: Box):
    lock = box.lock()
    out = box.root / "lock-age-at-push"
    shim = box.fakebin / "heartbeat-git"
    shim.write_text(f"""#!/usr/bin/env bash
case " $* " in
  *" pull "*) python3 -c 'import os,sys,time; t=time.time()-3600; os.utime(sys.argv[1], (t, t))' '{lock}' ;;
  *" push "*) python3 -c 'import os,sys,time; print(int(time.time()-os.stat(sys.argv[1]).st_mtime))' '{lock}' >> '{out}' ;;
esac
exec git "$@"
""", encoding="utf-8")
    shim.chmod(0o755)
    result = box.stamp("with a heartbeat", LANES_GIT=str(shim))
    assert result.returncode == 0, (result.stdout, result.stderr)
    ages = [int(a) for a in out.read_text(encoding="utf-8").split()]
    assert ages and all(a < 60 for a in ages), \
        f"the lock aged an hour before the push, and the holder refreshed it first: {ages}"


def test_a_claim_that_finds_a_new_holder_puts_the_lock_back(box: Box):
    """THE TAKEOVER IS A CLAIM, NOT A DELETE. Two waiters read the same dead
    holder; the first takes over and makes its own lock; the second's rename
    then claims THAT one. It reads what it claimed again, finds a live holder,
    and puts the lock back whole, so the first writer is never left unlocked."""
    lock = box.lock()
    hold(lock, f"{gone_pid()} {ME}")
    holder = subprocess.Popen(["sleep", "300"])
    claimed = box.root / "claimed-once"
    real_mv = shutil.which("mv")
    (box.fakebin / "mv").write_text(f"""#!/usr/bin/env bash
# THE CLAIM'S RENAME: just before it, another waiter took over and made its
# own lock, so the directory this rename claims is that waiter's, not the dead one.
case " $* " in
  *" {lock} {lock}.taken."*)
    [ -e '{claimed}' ] || {{ printf '%s {ME}\\n' '{holder.pid}' > '{lock}/pid'; : > '{claimed}'; }} ;;
esac
exec '{real_mv}' "$@"
""", encoding="utf-8")
    (box.fakebin / "mv").chmod(0o755)
    try:
        writer = box.popen("set-row-state", LANE, "LIVE · after the claim")
        deadline = time.monotonic() + 90
        while not claimed.exists() and writer.poll() is None and time.monotonic() < deadline:
            time.sleep(.1)
        assert claimed.exists(), "the waiter did claim the lock it read as dead"
        assert still_waiting(writer), "a claim that finds a live holder waits for it"
        assert (lock / "pid").read_text(encoding="utf-8") == f"{holder.pid} {ME}\n", \
            "the live holder's lock is back at its name, whole"
        assert not list(lock.parent.glob(".lanes-edit.lock.taken.*")), "no claimed copy is left"
    finally:
        holder.kill()
        holder.wait()
    out, err = writer.communicate(timeout=90)
    assert writer.returncode == 0, (out, err)
    assert " · after the claim |" in box.origin_register()


def test_release_leaves_a_lock_another_holder_took(box: Box):
    """A LOCK IS RELEASED ONLY WHILE IT IS STILL THIS PROCESS'S, and the one a
    writer makes names its container and host beside its pid. Here the lock
    changes hands while the writer pushes (another container's waiter judged it
    by an age it missed): the writer finishes, and leaves that holder's lock."""
    lock = box.lock()
    seen = box.root / "pid-line-at-push"
    holder = subprocess.Popen(["sleep", "300"])
    shim = box.fakebin / "handover-git"
    shim.write_text(f"""#!/usr/bin/env bash
case " $* " in
  *" push "*)
    cat '{lock}/pid' >> '{seen}'
    printf '%s bench-b hostb\\n' '{holder.pid}' > '{lock}/pid' ;;
esac
exec git "$@"
""", encoding="utf-8")
    shim.chmod(0o755)
    try:
        result = box.stamp("handed over mid-write", LANES_GIT=str(shim))
        assert result.returncode == 0, (result.stdout, result.stderr)
        first = seen.read_text(encoding="utf-8").splitlines()[0]
        assert re.fullmatch(r"[0-9]+ bench-a hosta", first), \
            f"the writer's pid file is `<pid> <container> <host>`: {first!r}"
        assert (lock / "pid").read_text(encoding="utf-8") == f"{holder.pid} bench-b hostb\n", \
            "the lock another holder took is that holder's, and is left as it is"
        assert f"held by pid {holder.pid} now" in result.stderr, result.stderr
        assert " · handed over mid-write |" in box.origin_register()
    finally:
        holder.kill()
        holder.wait()


# ----------------------------------------------------- the workstation's lock

@pytest.mark.parametrize("act", ["set-lane-state", "set-lane-tree", "publish-handoff"])
def test_sidecar_acts_share_the_workstation_lock(box: Box, act: str):
    box.lanes_root.mkdir(parents=True, exist_ok=True)
    sidecar = box.lanes_root / ".lane-state.lock"
    # W'S OLD LOCK IS A FILE HERE, so anything that still took a lock in W
    # would wedge on it for its whole minute.
    (box.w / "lanes" / ".lanes-edit.lock").write_text("a wedge\n", encoding="utf-8")
    target = box.root / "handoff.md"
    prepared = box.root / "prepared.md"
    target.write_text("# before\n", encoding="utf-8")
    prepared.write_text("# after\n", encoding="utf-8")
    tree = ("set-lane-tree", LANE, str(box.root / "a-tree"), "--branch", "main", "--head", "0" * 40,
            "--upstream", "origin/main", "--dirty", "0", "--unpushed", "0")
    if act == "set-lane-state":
        args = ("set-lane-state", LANE, "RUNNING", "--expect", "none", "--owner", UUID)
        written = lambda: (box.state / LANE / "lane-state.yaml").is_file()  # noqa: E731
    elif act == "set-lane-tree":
        args = tree
        written = lambda: any((box.state / LANE / "trees").glob("*.yaml"))  # noqa: E731
    else:
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        args = ("publish-handoff", LANE, str(target), str(prepared), "--expect-digest", digest)
        written = lambda: target.read_text(encoding="utf-8") == "# after\n"  # noqa: E731
    holder = subprocess.Popen(["sleep", "300"])
    try:
        hold(sidecar, f"{holder.pid} {ME}")
        waiter = box.popen(*args)
        assert still_waiting(waiter), f"{act} waits on the workstation's sidecar lock"
        assert not written()
    finally:
        holder.kill()
        holder.wait()
    out, err = waiter.communicate(timeout=90)
    assert waiter.returncode == 0, (out, err)
    assert written()
    assert not sidecar.exists()
    # …and neither it nor a routed write ever took a lock in W, or each would
    # have waited out its minute on the file there.
    if act == "set-lane-state":
        again_args = ("set-lane-state", LANE, "RUNNING", "--expect", "RUNNING", "--owner", UUID)
    elif act == "set-lane-tree":
        again_args = tree
    else:
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        again_args = ("publish-handoff", LANE, str(target), str(prepared), "--expect-digest", digest)
    again = box.helper(*again_args, timeout=45)
    assert again.returncode == 0, (again.stdout, again.stderr)
    routed = box.stamp("past a wedged W", timeout=45)
    assert routed.returncode == 0, (routed.stdout, routed.stderr)
    assert (box.w / "lanes" / ".lanes-edit.lock").read_text(encoding="utf-8") == "a wedge\n"


def test_a_lifecycle_follow_takes_the_workstation_lock(box: Box):
    """A LIFECYCLE LINE'S FOLLOW-UP moves the lane's snapshot under the
    workstation's sidecar lock, taken inside the checkout lock its write holds.
    With that lock held elsewhere, the line lands and the snapshot is left one
    act behind, as the follow-up says: it is never moved unlocked."""
    made = box.helper("set-lane-state", LANE, "RUNNING", "--expect", "none", "--owner", UUID)
    assert made.returncode == 0, (made.stdout, made.stderr)
    snapshot = box.state / LANE / "lane-state.yaml"
    before = snapshot.read_text(encoding="utf-8")
    box.lanes_root.mkdir(parents=True, exist_ok=True)
    sidecar = box.lanes_root / ".lane-state.lock"
    holder = subprocess.Popen(["sleep", "300"])
    try:
        hold(sidecar, f"{holder.pid} {ME}")
        result = box.helper("log", "ENDED", f"lane:{LANE}", LANES_LANE=LANE, LANES_SESSION=UUID)
        assert (sidecar / "pid").read_text(encoding="utf-8") == f"{holder.pid} {ME}\n"
    finally:
        holder.kill()
        holder.wait()
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "was NOT moved to CLOSED" in result.stderr, result.stderr
    assert snapshot.read_text(encoding="utf-8") == before, "the snapshot was not moved unlocked"
    log = box.git("--git-dir", str(box.origin), "show", f"main:lanes/log/{LANE}.md")
    assert f"ENDED — lane {LANE}" in log, log
