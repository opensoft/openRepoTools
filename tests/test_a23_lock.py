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

from a23_box import ME, REGISTER, RegisterBox, register_text
from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

LANE = "repoLK-1"
UUID = "a23b0001-1c1c-4000-8000-a23b00011c1c"
#: How long a waiter is watched to prove it is still waiting. The helper polls
#: once a second, so a writer that was going to take the lock has long done so.
WATCH = 4


def _row(lane: str, state: str = "LIVE · seeded") -> str:
    return (f"| `{lane}` | harness `{UUID}` | Eagle / test / tester | 2026-10-17T00:00Z "
            f"| — | handoffs/repoLK/{lane}.md | {state} |")


class Box(RegisterBox):
    """Two rows, and the lanes' sidecars under a state root of the box's own."""

    def __init__(self, root: Path) -> None:
        state = Path(os.path.realpath(root)) / "state"
        super().__init__(root, {REGISTER: register_text([_row(LANE), _row("repoLK-2")])},
                         env={"LANES_LANE_STATE_ROOT": str(state)})
        self.state = state

    def stamp(self, words: str, **extra: str) -> subprocess.CompletedProcess:
        return self.helper("set-row-state", LANE, f"LIVE · {words}", **extra)

    def made_checkout(self) -> Path:
        """The lane's checkout, made by an ordinary first write."""
        c = self.checkout(LANE)
        if not c.exists():
            made = self.stamp("made the checkout")
            assert made.returncode == 0, (made.stdout, made.stderr)
        return c

    def lock(self) -> Path:
        return self.made_checkout() / "lanes" / ".lanes-edit.lock"


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
    c = box.made_checkout()
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
    c = box.made_checkout()
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
        assert f"held by pid {holder.pid} in container bench-b on hostb now" in result.stderr, \
            result.stderr
        assert " · handed over mid-write |" in box.origin_register()
    finally:
        holder.kill()
        holder.wait()


def test_release_leaves_a_lock_with_its_pid_in_another_container(box: Box):
    """NIT 3: a pid is not "this process" in another container. The lock that
    changes hands here names the WRITER's own pid with another container and
    host, and the writer still leaves it."""
    lock = box.lock()
    shim = box.fakebin / "same-pid-git"
    shim.write_text(f"""#!/usr/bin/env bash
case " $* " in
  *" push "*)
    read -r p _ < '{lock}/pid'
    printf '%s bench-b hostb\\n' "$p" > '{lock}/pid' ;;
esac
exec git "$@"
""", encoding="utf-8")
    shim.chmod(0o755)
    result = box.stamp("same pid, another container", LANES_GIT=str(shim))
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert re.fullmatch(r"[0-9]+ bench-b hostb\n", (lock / "pid").read_text(encoding="utf-8"))
    assert "in container bench-b on hostb now, not by this process" in result.stderr, result.stderr


# ----------------------------------------------------- the workstation's lock

@pytest.mark.parametrize("act", ["set-lane-state", "set-lane-tree", "publish-handoff",
                                 "set-restart-intent"])
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
    elif act == "set-restart-intent":
        args = ("set-restart-intent", LANE, "pending", "--expect", "none")
        written = lambda: (box.state / LANE / "restart-intent.yaml").is_file()  # noqa: E731
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
    elif act == "set-restart-intent":
        again_args = ("set-restart-intent", LANE, "pending", "--expect", "pending")
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


# ----------------------------------------------------- fix round 1 (#282's review)

def test_without_the_opt_in_a_sidecar_act_takes_the_checkouts_lock(box: Box):
    """MUST 2: with no `LANES_ROUTE_WRITES`, the sidecar acts take W's own
    lock, as before Amendment 23, and no `<W>-lanes/` is made for one."""
    w_lock = box.w / "lanes" / ".lanes-edit.lock"
    holder = subprocess.Popen(["sleep", "300"])
    try:
        hold(w_lock, f"{holder.pid} {ME}")
        waiter = box.popen("set-lane-state", LANE, "RUNNING", "--expect", "none", "--owner", UUID,
                           LANES_ROUTE_WRITES="")
        assert still_waiting(waiter), "it waits on W's lock"
    finally:
        holder.kill()
        holder.wait()
    out, err = waiter.communicate(timeout=90)
    assert waiter.returncode == 0, (out, err)
    assert (box.state / LANE / "lane-state.yaml").is_file()
    assert not box.lanes_root.exists(), "no workstation lock, so no <W>-lanes/"
    assert not w_lock.exists()


def test_a_lock_that_vanished_under_its_holder_is_not_made_again(box: Box):
    """MUST 4: the heartbeat refreshes a lock and never makes one. A lock
    directory removed under its holder (another container's takeover, a
    person's `rmdir`) used to come back from `git_net`'s `touch` as a REGULAR
    FILE that no release removes, and every later write waited out its
    minute and exited 4."""
    lock = box.lock()
    peer = box.clone(box.root / "peer")
    box.write(peer, "handoffs/peer.md", "from a peer\n")
    box.commit(peer, "a peer writes", "handoffs/peer.md")
    box.git("-C", str(peer), "push", "-q", "origin", "main")
    # The lane's checkout is now behind, so its write pulls and then pushes:
    # two network calls under the lock, and the lock is taken away between.
    real = shutil.which("git")
    wrapper = box.root / "takes-the-lock"
    mark = box.root / "taken"
    wrapper.write_text(f"""#!/usr/bin/env bash
case " $* " in *" pull "*)
  if [ ! -e '{mark}' ]; then : > '{mark}'; rm -f '{lock}/pid'; rmdir '{lock}'; fi ;;
esac
exec '{real}' "$@"
""", encoding="utf-8")
    wrapper.chmod(0o755)
    first = box.stamp("the lock went away under me", LANES_GIT=str(wrapper))
    assert first.returncode == 0, (first.stdout, first.stderr)
    assert mark.exists(), "the lock was taken away mid-write"
    assert not lock.exists(), "nothing was made in its place"
    started = time.monotonic()
    second = box.stamp("the next write", timeout=45)
    assert second.returncode == 0, (second.stdout, second.stderr)
    assert time.monotonic() - started < 30, "it did not wait on a leftover"
