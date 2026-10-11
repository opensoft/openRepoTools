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
        box.env["LANES_NO_FETCH"] = "1"
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
