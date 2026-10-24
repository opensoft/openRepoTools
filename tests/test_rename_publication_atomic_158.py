# SPDX-License-Identifier: Apache-2.0
"""`rename-lane`'s Rule 3 stamp is published whole or not at all
(opensoft/openRepoTools#158).

The stamp was written with `cat <stamped copy> > <handoff>`. The redirect
TRUNCATES the handoff before the first stamped byte is written, so a writer
killed inside that `cat` — or a machine that lost power there — left a handoff
cut short, and nothing undid it: `rename_undo` is an EXIT trap, and a process
that dies by SIGKILL runs no trap at all. Every later read takes a short
handoff for the real one, and a handoff is the document the next session reads
first.

EVERY RUN HERE IS A REAL `rename-lane` IN `test_lane_start_claude_current`'s
SANDBOX: a bare origin, a workspace clone, a row and a log made by a real
`lane-start --no-launch`, and a handoff seeded at the path that row names. The
faults are two stubs first on `PATH`, both passing every other call to the real
utility:

  * `cat` — the one call whose single operand already carries the stamp writes
    two lines of it to wherever its stdout was opened, then kills the writer
    with SIGKILL: a crash INSIDE the write;
  * `mv` — the one call whose destination already IS the published handoff
    (the handoff's own rename moves onto a path that does not exist yet, so it
    never matches) kills the writer, signals it, or fails: a fault BETWEEN the
    write and the replace.

Two shapes of handoff, because the stamp is published in both: one named
`…-lane-<old>.md`, which the rename moves and then stamps, and one named
otherwise, which is stamped where it is (Amendment 16(d)).

What is claimed, and only this: the HANDOFF's bytes survive whole. A crash
between two of the rename's four moves still leaves them apart — the issue
scopes that recovery separately, and nothing here says otherwise.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
from pathlib import Path

import pytest

from test_lane_start_claude_current import Sandbox, LANE, _write, pytestmark

NEW = "repoZ-2"
RENAMER = "10101010-1111-4111-8111-111111111111"

#: A handoff with a header block, so the stamp goes under it (line 5) and
#: there are lines on both sides of it to lose.
HANDOFF = (
    "# Session handoff — lane repoZ-1\n"
    "Lane: repoZ-1\n"
    "Updated: 2026-10-11T00:00:00Z\n"
    "\n"
    "## Top block\n"
    "Preserved task: the next session reads this first.\n"
    "---\n"
    "History.\n"
).encode("utf-8")
STAMP_AT = 4  # the first blank line after line 1; the stamp is line 5

CAT_STUB = r"""#!/usr/bin/env bash
# opensoft/openRepoTools#158: a crash INSIDE the stamp's write.
if [ "${FAULT_158-}" = crash-mid-write ] && [ "$PPID" != "$FAULT_158_GUARD" ]; then
  ops=()
  for a in "$@"; do [ "$a" = -- ] || ops+=("$a"); done
  if [ "${#ops[@]}" = 1 ] && [ -f "${ops[0]}" ] &&
     __GREP__ -q "^RENAMED from $FAULT_158_OLD by " "${ops[0]}"; then
    __HEAD__ -n 2 "${ops[0]}"
    : > "$FAULT_158_MARK"
    kill -KILL "$PPID"
    exit 137
  fi
fi
exec __CAT__ "$@"
"""

MV_STUB = r"""#!/usr/bin/env bash
# opensoft/openRepoTools#158: a fault BETWEEN the write and the replace.
if [ -n "${FAULT_158-}" ] && [ "$#" -ge 2 ] && [ "$PPID" != "$FAULT_158_GUARD" ]; then
  dest="${@: -1}"
  if [ "$dest" -ef "$FAULT_158_TARGET" ]; then
    case "$FAULT_158" in
      kill-before-replace) : > "$FAULT_158_MARK"; kill -KILL "$PPID"; exit 137 ;;
      term-before-replace) : > "$FAULT_158_MARK"; kill -TERM "$PPID"; exit 1 ;;
      fail-replace)        : > "$FAULT_158_MARK"; exit 1 ;;
    esac
  fi
fi
exec __MV__ "$@"
"""


class RenameBox:
    """One sandbox, one lane with a row, a log and a committed handoff."""

    def __init__(self, root: Path, shape: str) -> None:
        self.box = box = Sandbox(root)
        box.env["LANES_LANE_STATE_ROOT"] = str(root / "state")
        # No `LANES_NO_FETCH=1`: for a writer it is a failed fetch, and
        # Amendment 23 S3 refuses the write (ratified choice 2, #198 slice 1b).
        box.resolver()
        started = box.start("--no-launch")
        assert started.returncode == 0, (started.stdout, started.stderr)
        register = box.wip / "lanes" / "LANES.md"
        text = register.read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if line.startswith(f"| `{LANE}`"))
        named = row.split("|")[6].strip()
        assert named.endswith(f"-lane-{LANE}.md"), row
        if shape == "moved":
            rel = named
            published = named[: -len(f"{LANE}.md")] + f"{NEW}.md"
        else:
            rel = published = str(Path(named).parent / "notes.md")
            register.write_text(text.replace(row, row.replace(named, rel)), encoding="utf-8")
        self.handoff = box.wip / rel
        self.published = box.wip / published
        self.handoff.parent.mkdir(parents=True, exist_ok=True)
        self.handoff.write_bytes(HANDOFF)
        self.handoff.chmod(0o640)
        box.git("-C", str(box.wip), "add", "--", "lanes/LANES.md", rel)
        box.git("-C", str(box.wip), "commit", "-qm", "seed the handoff")
        box.git("-C", str(box.wip), "push", "-q", "origin", "main")
        self.mark = root / "fault-fired"
        self.faults = root / "faults"
        real = {name: shutil.which(name) for name in ("cat", "mv", "grep", "head")}
        assert all(real.values()), real
        for name, stub in (("cat", CAT_STUB), ("mv", MV_STUB)):
            for tool, path in real.items():
                stub = stub.replace(f"__{tool.upper()}__", path)
            _write(self.faults / name, stub)

    def tree(self) -> dict[str, bytes]:
        return {str(p.relative_to(self.box.wip)): p.read_bytes()
                for p in self.box.wip.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(self.box.wip).parts}

    def head(self) -> str:
        return self.box.git("-C", str(self.box.wip), "rev-parse", "HEAD").strip()

    def rename(self, fault: str | None = None) -> subprocess.CompletedProcess:
        env = dict(self.box.env, LANES_SESSION=RENAMER)
        if fault:
            env.update(FAULT_158=fault, FAULT_158_OLD=LANE, FAULT_158_MARK=str(self.mark),
                       FAULT_158_TARGET=str(self.published),
                       FAULT_158_GUARD=str(os.getpid()),
                       PATH=f"{self.faults}{os.pathsep}{env['PATH']}")
        return subprocess.run([str(self.box.bin / "lanes-edit.sh"), "rename-lane", LANE, NEW,
                               "--no-github"], cwd=self.box.lane_dir, env=env, text=True,
                              capture_output=True, timeout=120, check=False)

    def handoffs(self) -> list[Path]:
        """Every file in the handoff's directory a reader would take for a
        handoff: what a crash may leave beside it must not end in `.md`."""
        return sorted(p for p in self.handoff.parent.iterdir() if p.name.endswith(".md"))


@pytest.fixture(params=["moved", "in-place"])
def rbox(request, tmp_path: Path) -> RenameBox:
    return RenameBox(tmp_path, request.param)


def test_rename_stamp_is_the_same_splice_and_keeps_the_handoffs_mode(rbox):
    result = rbox.rename()
    assert result.returncode == 0, (result.stdout, result.stderr)
    published = rbox.published.read_bytes()
    lines = published.splitlines(keepends=True)
    assert re.fullmatch(rf"RENAMED from {LANE} by {RENAMER} \(lane {NEW}\) at \S+\n",
                        lines[STAMP_AT].decode("utf-8")), lines
    # Take the one line back out and the file is the handoff byte for byte.
    assert b"".join(lines[:STAMP_AT] + lines[STAMP_AT + 1:]) == HANDOFF
    assert rbox.handoffs() == [rbox.published]
    assert rbox.published.stat().st_mode & 0o777 == 0o640
    committed = subprocess.run(["git", "-C", str(rbox.box.wip), "show",
                                f"HEAD:{rbox.published.relative_to(rbox.box.wip)}"],
                               env=rbox.box.env, capture_output=True, check=True).stdout
    assert committed == published


@pytest.mark.parametrize("fault", ["crash-mid-write", "kill-before-replace"])
def test_rename_writer_killed_around_the_stamp_leaves_the_handoff_whole(rbox, fault):
    result = rbox.rename(fault)
    assert rbox.mark.exists(), ("the fault never fired", result.stdout, result.stderr)
    assert result.returncode == -signal.SIGKILL, (result.stdout, result.stderr)
    # No trap ran, so this is what a crash leaves. The handoff is the old one,
    # whole — never a truncated or half-written one in its place.
    assert rbox.handoffs() == [rbox.published]
    assert rbox.published.read_bytes() == HANDOFF


@pytest.mark.parametrize("fault", ["fail-replace", "term-before-replace"])
def test_rename_replace_refused_or_interrupted_rolls_back_and_leaves_no_temporary(rbox, fault):
    before, head = rbox.tree(), rbox.head()
    result = rbox.rename(fault)
    assert rbox.mark.exists(), ("the fault never fired", result.stdout, result.stderr)
    expected = 5 if fault == "fail-replace" else -signal.SIGTERM
    assert result.returncode == expected, (result.stdout, result.stderr)
    assert "the rename was rolled back" in result.stderr
    # The existing rollback, unchanged: every file as it was, nothing committed,
    # and the temporary copy gone with the lock — on the signal path that is
    # `cleanup`'s doing, because the trap runs before the refusal's own branch.
    assert rbox.tree() == before
    assert rbox.head() == head
    assert sorted(p.name for p in rbox.handoff.parent.iterdir()) == [rbox.handoff.name]


def test_rename_in_place_handoff_in_a_read_only_directory_refuses_and_rolls_back(tmp_path):
    """The one behaviour #158 changes on purpose. A handoff stamped where it is
    needed only the FILE writable; a temporary beside it needs the directory
    too. f87fd5a stamped this case in place and exited 0."""
    if os.geteuid() == 0:
        pytest.skip("a read-only directory binds an unprivileged writer only")
    rbox = RenameBox(tmp_path, "in-place")
    before, head = rbox.tree(), rbox.head()
    rbox.handoff.parent.chmod(0o555)
    try:
        result = rbox.rename()
    finally:
        rbox.handoff.parent.chmod(0o755)
    assert result.returncode == 5, (result.stdout, result.stderr)
    assert "no temporary file could be made beside" in result.stderr
    assert "the rename was rolled back" in result.stderr
    assert rbox.tree() == before
    assert rbox.head() == head
    assert sorted(p.name for p in rbox.handoff.parent.iterdir()) == [rbox.handoff.name]


#: EVERY NAME THE EXIT AND SIGNAL TRAPS REMOVE A PATH THROUGH — `cleanup`
#: itself, `rename_undo` and `release_lock` — with what an exported variable of
#: that name must carry to point at the victim. The undo and the lock are each
#: armed by a flag of their own, so the flag is exported beside the paths.
#: `rl_htmp`, `pbh_tmp` and `TMPD` deleted the victim before the fix; the rest
#: were already set at top level (`SE_CACHE_FILE` before any normal exit, its
#: gap being a signal before its assignment), and are held here so they stay so.
INHERITED = {
    "rl_htmp": {"rl_htmp": "{file}"},
    "pbh_tmp": {"pbh_tmp": "{file}"},
    "TMPD": {"TMPD": "{dir}"},
    "SE_CACHE_FILE": {"SE_CACHE_FILE": "{file}"},
    "RL_SNAP": {"RL_SNAP": "{dir}"},
    "LANES_IDX_DIR": {"LANES_IDX_DIR": "{dir}"},
    "LANES_WT_IDX_DIR": {"LANES_WT_IDX_DIR": "{dir}"},
    "rename_undo": {"RL_ACTIVE": "1", "RL_ALIAS_EXISTED": "0", "RL_LOG_NEW": "{file}",
                    "RL_H_NEW": "{file}", "RL_ALIAS": "{file}"},
    "release_lock": {"LOCK_HELD": "1", "LOCK": "{dir}"},
}


@pytest.mark.parametrize("name", sorted(INHERITED))
def test_cleanup_removes_no_path_a_variable_inherits_from_the_environment(tmp_path, name):
    """`cleanup` runs on every exit and removes its temporaries BY NAME, so a
    name that arrived already set removed the caller's path: with `rl_htmp`
    exported, a read-only `canon-lane` deleted that file (the review of #212),
    and `pbh_tmp` and `TMPD` — the second under `rm -rf` — had the same hole
    before it (the reviews of #212 and #213)."""
    box = Sandbox(tmp_path)
    box.env["LANES_NO_FETCH"] = "1"
    victim = tmp_path / "victim"
    victim.mkdir()
    kept = {victim / "keep.md": HANDOFF, victim / "pid": b"1\n"}
    for path, data in kept.items():
        path.write_bytes(data)
    inherited = {k: v.format(dir=victim, file=victim / "keep.md") for k, v in INHERITED[name].items()}
    result = subprocess.run([str(box.bin / "lanes-edit.sh"), "canon-lane", LANE],
                            cwd=box.lane_dir, env=dict(box.env, **inherited),
                            text=True, capture_output=True, timeout=60, check=False)
    assert {p: p.read_bytes() for p in kept if p.exists()} == kept, (result.returncode, result.stderr)
