# SPDX-License-Identifier: Apache-2.0
"""opensoft/openRepoTools#113, #114 and #115: the crash-consistent lifecycle's
remaining fail-open reads, `set-lane-tree`'s fence, and a sidecar's validation.
Each case runs the real `lane-start` and `lanes-edit.sh` in the lane-start
sandbox (a bare origin, a register clone, a fake tmux and a fake gh; nothing
reaches the network). A read that FAILED is injected by a `git` on PATH that
passes every call through to the real one except the one a case names.

  * #113 item 1. `lane_reconcile`'s holder ids ended in `|| :`, so this
    checkout's register copy that could not be read came out as an id set with
    nothing of its own in it, and a crash was pronounced on liveness nobody
    established. (The published half is caught one step earlier by the managed
    seam, which already reads an empty register as unknown.)
  * #113 item 2's remainder. An unreadable sidecar became a row of its own in
    8.12, but `lane_reconcile` still swallowed `lane-trees`' 10 for a `trees`
    directory that cannot be listed (#157 item 4e), so the whole inventory
    vanished and the verdict could read `resumable`.
  * #113 item 3. `git config --get branch.<b>.remote` was unguarded, so a read
    that failed became the fabricated local upstream `./<merge>`.
  * #113 item 4. `git worktree list --porcelain` was swallowed, so a checkout
    whose registrations could not be read was one with none; a lane root that
    cannot be listed was the same silence on disk.
  * #114 item 1. `set-lane-tree`'s fence compared the generation and the
    operation only, and `SWAPPED` keeps both, so a poll from a FINISHED
    operation was filed over the inventory its commit point closed. (Item 2,
    the partial observation, is refused with 64 since 8.12.)
  * #115. A sidecar passed validation on its `schema:` line alone, so a
    truncated `schema: 1` record was read as empty fields AND replaced.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_lane_start_claude_current import Sandbox, LANE, pytestmark  # noqa: F401

US = "\x1f"

#: A `git` that is the real one, except for the one call FAKE_GIT_FAIL names,
#: which fails the way a read git cannot complete does. The suite's own `git`
#: calls never set it.
FAKE_GIT = """#!/usr/bin/env bash
if [ -n "${FAKE_GIT_FAIL:-}" ]; then
  case " $* " in
    *" $FAKE_GIT_FAIL "*)
      printf 'fatal: injected failure of: git %s\\n' "$*" >&2
      exit 128 ;;
  esac
fi
exec "%(real)s" "$@"
"""


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    real_git = shutil.which("git")
    assert real_git
    box = Sandbox(tmp_path)
    shim = box.fakebin / "git"
    shim.write_text(FAKE_GIT.replace("%(real)s", real_git), encoding="utf-8")
    shim.chmod(0o755)
    box.env["LANES_LANE_STATE_ROOT"] = str(tmp_path / "state")
    box.resolver()
    seeded = box.start("--no-launch")
    assert seeded.returncode == 0, seeded.stderr
    return box


def helper(box: Sandbox, *args: str, **env: str) -> subprocess.CompletedProcess:
    full = dict(box.env, LANES_NO_FETCH="1")
    full.update(env)
    return subprocess.run([str(box.bin / "lanes-edit.sh"), *args],
                          cwd=box.lane_dir, env=full, text=True,
                          capture_output=True, timeout=120, check=False)


def ok(box: Sandbox, *args: str, **env: str) -> str:
    result = helper(box, *args, **env)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result.stdout


def control_root(box: Sandbox) -> Path:
    return Path(box.env["LANES_LANE_STATE_ROOT"]) / LANE


def snapshot(box: Sandbox) -> Path:
    return control_root(box) / "lane-state.yaml"


def tabbed(out: str) -> dict:
    return dict(line.split("\t", 1) for line in out.splitlines() if "\t" in line)


def rows(out: str, tag: str) -> list:
    return [line.split(US) for line in out.splitlines() if line.split(US)[0] == tag]


def verdict(out: str) -> str:
    found = rows(out, "VERDICT")
    assert len(found) == 1, out
    return found[0][1]


def reconcile(box: Sandbox, **env: str) -> str:
    return ok(box, "lane-reconcile", LANE, **env)


def unprivileged() -> None:
    if os.geteuid() == 0:
        pytest.skip("a permission fixture needs an unprivileged runner")


def swapped(box: Sandbox) -> tuple:
    """Take the lane RUNNING -> SWAPPING -> SWAPPED as a handoff does, and
    return the generation and operation the swap ran under."""
    took = tabbed(ok(box, "set-lane-state", LANE, "SWAPPING", "--expect", "RUNNING"))
    gen, op = took["generation"], took["operation"]
    ok(box, "set-lane-state", LANE, "SWAPPED", "--expect", "SWAPPING",
       "--expect-generation", gen, "--expect-operation", op)
    return gen, op


def first_commit(box: Sandbox) -> None:
    box.git("-C", str(box.lane_dir), "commit", "-q", "--allow-empty", "-m", "first")


# --------------------------------------------------------------- #113 item 1

def test_113_1_an_unreadable_register_copy_is_no_holder_nobody_established(box):
    # A permission, and not a dangling link: the dispatcher refuses a register
    # file that is not there ("registry not found") before any read is made.
    unprivileged()
    assert tabbed(ok(box, "lane-state", LANE))["state"] == "RUNNING"
    before = reconcile(box)
    assert rows(before, "HOLDER")[0][1] == "none", before
    assert verdict(before) == "ungraceful-stop", before
    register = box.wip / "lanes" / "LANES.md"
    register.chmod(0)
    try:
        out = reconcile(box)
    finally:
        register.chmod(0o644)
    holder = rows(out, "HOLDER")[0]
    assert holder[1] == "unknown", out
    assert "register row could not be read" in holder[2], out
    assert verdict(out) == "indeterminate", out
    assert "ungraceful-stop" not in out


# ------------------------------------------------ #113 item 2 (the remainder)

@pytest.mark.parametrize("mode", [0o000, 0o300, 0o600],
                         ids=["no-access", "no-read", "no-search"])
def test_113_2_an_inventory_nobody_could_list_is_never_a_clearance(box, mode):
    unprivileged()
    tree = str(box.lane_dir / ".claude" / "worktrees" / "gone")
    ok(box, "set-lane-tree", LANE, tree, "--checkout", str(box.lane_dir),
       "--branch", "feat/gone", "--head", "1" * 40, "--upstream", "none",
       "--dirty", "2", "--unpushed", "1")
    swapped(box)
    trees = control_root(box) / "trees"
    trees.chmod(mode)
    try:
        out = reconcile(box)
    finally:
        trees.chmod(0o700)
    assert verdict(out) == "indeterminate", out
    assert f"{trees} is there and could not be listed" in rows(out, "VERDICT")[0][2]
    assert "resumable" not in rows(out, "VERDICT")[0][1]


# --------------------------------------------------------------- #113 item 3

def test_113_3_a_failed_remote_read_is_never_a_fabricated_local_upstream(box):
    first_commit(box)
    box.git("-C", str(box.lane_dir), "config", "branch.main.remote", "origin")
    box.git("-C", str(box.lane_dir), "config", "branch.main.merge", "refs/heads/main")
    fail = {"FAKE_GIT_FAIL": "config --get branch.main.remote"}
    # The configured spelling, with no remote-tracking ref here, is an ANSWER.
    now = ok(box, "lane-tree-now", str(box.lane_dir)).rstrip("\n").split(US)
    assert (now[2], now[4]) == ("origin/main", "unknown"), now
    # A remote read that FAILED is a 1 and prints nothing.
    result = helper(box, "lane-tree-now", str(box.lane_dir), **fail)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert result.stdout == ""
    assert "./main" not in result.stdout
    # And nothing is filed for a tree this process could not read.
    result = helper(box, "set-lane-tree", LANE, str(box.lane_dir), **fail)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert not (control_root(box) / "trees").exists() or \
        not any((control_root(box) / "trees").iterdir())


# --------------------------------------------------------------- #113 item 4

def test_113_4_registrations_nobody_could_list_are_never_a_clearance(box):
    first_commit(box)
    stale = box.lane_dir / ".claude" / "worktrees" / "stale"
    box.git("-C", str(box.lane_dir), "worktree", "add", "-q", "-b", "feat/stale", str(stale))
    shutil.rmtree(stale)
    swapped(box)
    readable = reconcile(box)
    assert [r[2] for r in rows(readable, "TREE")] == ["stale-registration"], readable
    out = reconcile(box, FAKE_GIT_FAIL="worktree list --porcelain")
    assert verdict(out) == "indeterminate", out
    why = rows(out, "VERDICT")[0][2]
    assert f"the worktrees git registers in {box.lane_dir} could not be listed" in why, why
    assert "git worktree list exited 128" in why
    # A recorded directory that is NO repository registers nothing, and that
    # alone is an absence: the lane is resumable over it, as `lane-worktrees`
    # reads it (#170 G5).
    shutil.rmtree(box.lane_dir / ".git")
    out = reconcile(box, FAKE_GIT_FAIL="worktree list --porcelain")
    assert verdict(out) == "resumable", out


@pytest.mark.parametrize("mode", [0o000, 0o300, 0o600],
                         ids=["no-access", "no-read", "no-search"])
def test_113_4_a_lane_root_nobody_could_list_is_never_a_clearance(box, mode):
    unprivileged()
    swapped(box)
    # A checkout git registers nowhere, which only the on-disk sweep finds.
    root = box.lane_dir / ".claude" / "worktrees"
    box.git("init", "-q", "-b", "main", str(root / "hidden"))
    readable = reconcile(box)
    assert [(r[2], r[3]) for r in rows(readable, "TREE")] == \
        [("unmanaged", str(root / "hidden"))], readable
    root.chmod(mode)
    try:
        out = reconcile(box)
    finally:
        root.chmod(0o755)
    assert verdict(out) == "indeterminate", out
    assert f"the lane's worktree root {root} could not be listed" in rows(out, "VERDICT")[0][2]


# --------------------------------------------------------------- #114 item 1

@pytest.mark.parametrize("fence", ["generation-and-operation", "generation-only"])
def test_114_1_a_poll_from_a_finished_operation_is_refused(box, fence):
    took = tabbed(ok(box, "set-lane-state", LANE, "SWAPPING", "--expect", "RUNNING"))
    gen, op = took["generation"], took["operation"]
    named = ["--generation", gen] + (["--operation", op] if fence != "generation-only" else [])
    tree = str(box.lane_dir / ".claude" / "worktrees" / "w1")
    observed = ["--checkout", str(box.lane_dir), "--branch", "feat/w1", "--head", "a" * 40,
                "--upstream", "origin/feat/w1"]
    # The operation in flight records its poll.
    ok(box, "set-lane-tree", LANE, tree, *observed, "--dirty", "3", "--unpushed", "2", *named)
    ok(box, "set-lane-state", LANE, "SWAPPED", "--expect", "SWAPPING",
       "--expect-generation", gen, "--expect-operation", op)
    sidecar = next((control_root(box) / "trees").iterdir())
    finished = sidecar.read_bytes()
    # A poll of the same operation, delayed past its own finalizer.
    result = helper(box, "set-lane-tree", LANE, tree, *observed, "--dirty", "0",
                    "--unpushed", "0", *named)
    assert result.returncode == 7, (result.stdout, result.stderr)
    assert "the lane is SWAPPED" in result.stderr
    assert "superseded reading" in result.stderr
    assert sidecar.read_bytes() == finished
    # An observation filed under no transition is still the person's to make.
    ok(box, "set-lane-tree", LANE, tree, *observed, "--dirty", "0", "--unpushed", "0")


# ----------------------------- #114/#115: the shapes a record is read back in

@pytest.mark.parametrize("flag,value", [("--dirty", "yes"), ("--dirty", "-1"),
                                        ("--unpushed", "some"), ("--unpushed", "2x")])
def test_114_115_a_count_that_is_not_one_is_refused_before_anything_is_written(box, flag, value):
    counts = {"--dirty": "0", "--unpushed": "0", flag: value}
    result = helper(box, "set-lane-tree", LANE, str(box.lane_dir / "w"),
                    "--checkout", str(box.lane_dir), "--branch", "b", "--head", "h",
                    "--upstream", "none", "--dirty", counts["--dirty"],
                    "--unpushed", counts["--unpushed"])
    assert result.returncode == 64, (result.stdout, result.stderr)
    assert f"'{value}'" in result.stderr
    assert helper(box, "lane-trees", LANE).returncode == 8


# --------------------------------------------------------------------- #115

WHOLE_SNAPSHOT = ("schema: 1\nlane: {lane}\nstate: SWAPPING\ngeneration: 4\n"
                  "operation: op-x\nowner: none\nagent: claude\nprofile: none\n"
                  "workstation: Eagle\nkind: clear\nupdated: 2026-10-18T00:00:00Z\n")

SNAPSHOTS = {
    "schema-only": "schema: 1\n",
    "cut-after-state": "schema: 1\nlane: {lane}\nstate: SWAPPING\n",
    "cut-mid-line": WHOLE_SNAPSHOT.split("generation: 4")[0] + "generation: ",
    "no-updated": WHOLE_SNAPSHOT.rsplit("updated:", 1)[0],
    "unknown-state-word": WHOLE_SNAPSHOT.replace("SWAPPING", "WONDERLAND"),
    "generation-not-a-number": WHOLE_SNAPSHOT.replace("generation: 4", "generation: four"),
}


def plant_snapshot(box: Sandbox, body: str) -> bytes:
    snapshot(box).write_text(body.replace("{lane}", LANE), encoding="utf-8")
    return snapshot(box).read_bytes()


@pytest.mark.parametrize("shape", sorted(SNAPSHOTS))
def test_115_a_snapshot_that_is_not_whole_is_read_as_none_and_replaced_by_none(box, shape):
    planted = plant_snapshot(box, SNAPSHOTS[shape])
    # THE READERS: 10, never fields that came out empty.
    result = helper(box, "lane-state", LANE)
    assert result.returncode == 10, (shape, result.stdout, result.stderr)
    assert result.stdout == ""
    assert "nothing can be read out of it as a snapshot" in result.stderr
    out = reconcile(box)
    assert rows(out, "STATE")[0][1] == "MALFORMED", out
    assert verdict(out) == "indeterminate", out
    assert "#115" in rows(out, "VERDICT")[0][2]
    # THE WRITERS: refused, exactly as an unknown schema is, byte for byte.
    result = helper(box, "set-lane-state", LANE, "RUNNING")
    assert result.returncode == 1, (shape, result.stdout, result.stderr)
    assert "is not a record this helper can read" in result.stderr
    result = helper(box, "set-lane-tree", LANE, str(box.lane_dir / "w"),
                    "--checkout", str(box.lane_dir), "--branch", "b", "--head", "h",
                    "--upstream", "none", "--dirty", "0", "--unpushed", "0",
                    "--generation", "0")
    assert result.returncode == 1, (shape, result.stdout, result.stderr)
    assert snapshot(box).read_bytes() == planted


def test_115_the_confirming_act_does_not_replace_a_snapshot_that_is_not_whole(box):
    planted = plant_snapshot(box, SNAPSHOTS["cut-after-state"])
    resumed = box.start("--no-launch")
    assert resumed.returncode == 0, resumed.stderr
    assert "is not a record this helper can read" in resumed.stderr
    assert "it is not a whole record" in resumed.stderr
    assert snapshot(box).read_bytes() == planted


def plant_tree(box: Sandbox, how: str) -> tuple:
    """Record a vanished tree that held work, then spoil its sidecar `how`."""
    path = str(box.lane_dir / ".claude" / "worktrees" / "lost")
    tid = ok(box, "set-lane-tree", LANE, path, "--checkout", str(box.lane_dir),
             "--branch", "feat/lost", "--head", "b" * 40, "--upstream", "origin/feat/lost",
             "--dirty", "4", "--unpushed", "2").strip()
    sidecar = control_root(box) / "trees" / f"{tid}.yaml"
    whole = sidecar.read_text(encoding="utf-8")
    if how == "cut-after-path":
        body = whole.split("checkout:")[0]
    elif how == "schema-only":
        body = "schema: 1\n"
    elif how == "cut-mid-line":
        body = whole.split("dirty: 4")[0] + "dirty: "
    elif how == "claims-another-id":
        body = whole.replace(f"tree: {tid}", "tree: c1-someone-else")
    elif how == "dirty-not-a-count":
        body = whole.replace("dirty: 4", "dirty: four")
    elif how == "unpushed-not-a-count":
        body = whole.replace("unpushed: 2", "unpushed: two")
    elif how == "path-not-absolute":
        body = whole.replace(f"path: {path}", "path: relative/lost")
    else:
        raise AssertionError(how)
    sidecar.write_text(body, encoding="utf-8")
    return path, tid, sidecar


TREE_SHAPES = ["cut-after-path", "schema-only", "cut-mid-line", "claims-another-id",
               "dirty-not-a-count", "unpushed-not-a-count", "path-not-absolute"]


@pytest.mark.parametrize("how", TREE_SHAPES)
def test_115_a_tree_record_that_is_not_whole_is_said_and_never_read(box, how):
    path, tid, sidecar = plant_tree(box, how)
    listed = [line.split(US) for line in ok(box, "lane-trees", LANE).splitlines()]
    assert len(listed) == 1, listed
    assert listed[0][0] == tid and listed[0][12] == "<malformed>", listed
    assert listed[0][2:12] == [""] * 10, listed
    out = reconcile(box)
    trees = rows(out, "TREE")
    assert [(t[1], t[2]) for t in trees] == [(tid, "malformed-sidecar")], out
    assert f"{sidecar}" in trees[0][4]
    # Never `missing`, the clean-and-published word, for a tree that held work.
    assert "missing" not in [t[2] for t in trees]
    assert rows(out, "TREES")[0][3] == "1 require recovery", out


@pytest.mark.parametrize("how", TREE_SHAPES)
def test_115_a_tree_record_that_is_not_whole_is_never_replaced(box, how):
    path, tid, sidecar = plant_tree(box, how)
    planted = sidecar.read_bytes()
    result = helper(box, "set-lane-tree", LANE, path, "--checkout", str(box.lane_dir),
                    "--branch", "feat/lost", "--head", "c" * 40, "--upstream", "none",
                    "--dirty", "0", "--unpushed", "0")
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "is not a record this helper can read" in result.stderr
    assert sidecar.read_bytes() == planted


def test_115_a_record_that_is_not_whole_is_never_renamed_into_place(box):
    """`lane_sidecar_put` asks the temporary file the same question before the
    rename. A blank value is the one a writer can be handed: the reader trims
    it to nothing, so the record it would make is not whole."""
    before = snapshot(box).read_bytes()
    result = helper(box, "set-lane-state", LANE, "SWAPPING", "--expect", "RUNNING",
                    "--kind", "  ")
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "it carries no kind" in result.stderr
    assert snapshot(box).read_bytes() == before
    assert not list(control_root(box).glob("*.tmp.*"))
