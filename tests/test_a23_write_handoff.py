# SPDX-License-Identifier: Apache-2.0
"""Amendment 23, act 2, slice 2a: the handoff verbs.

`publish-handoff` keeps its contract for every old caller, and its act — the
link followed to the physical file, the restart fences, the prior digest, and
the bytes replaced by one rename beside the file — is `handoff_publish_atomic`,
which `write-handoff` shares.

The sandbox is the real `lanes-edit.sh`; nothing reaches a real remote. The box
is slice 1b's (`tests/test_a23_publish_replay.py`: two rows, a peer clone, and
a push-time `race` hook), imported rather than copied, with the lane's handoff
published on origin and a restart state root of its own.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path

import pytest

from conftest import WINDOWS_SKIP
from test_a23_publish_replay import LANE, Box as ReplayBox

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

#: The handoff cell `_row` gives the lane, and the file origin carries there:
#: a header line, the blank that ends the header block, then the block.
HANDOFF_REL = f"handoffs/repoS4/{LANE}.md"
HANDOFF = (f"Lane: {LANE} (profile p, session s) — single-use resume prompt\n"
           "\n"
           "## RESUME PROMPT — the block the next session reads\n"
           "\n"
           "Preserved task.\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Box(ReplayBox):
    """Slice 1b's box, with the lane's handoff on origin and its restart
    intents under a state root of the box's own."""

    def __init__(self, root: Path, **kw) -> None:
        root = Path(os.path.realpath(root))
        state = root / "state"
        env = dict(kw.pop("env", None) or {}, LANES_LANE_STATE_ROOT=str(state))
        super().__init__(root, env=env, **kw)
        self.state = state
        self.peer_pushes(HANDOFF_REL, HANDOFF)

    def intent(self, state: str, *extra: str) -> None:
        made = self.helper("set-restart-intent", LANE, state, *extra)
        assert made.returncode == 0, (made.stdout, made.stderr)

    def intent_field(self, key: str) -> str:
        text = (self.state / LANE / "restart-intent.yaml").read_text(encoding="utf-8")
        return next(line.split(": ", 1)[1] for line in text.splitlines()
                    if line.startswith(f"{key}: "))


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def _no_temporary_beside(path: Path) -> None:
    assert [p.name for p in path.parent.iterdir() if ".resume." in p.name] == []


# ------------------------------------------------- publish-handoff's contract

def test_publish_handoff_prints_the_physical_file_and_keeps_its_mode(box: Box):
    """Through a link, the physical file is replaced by one rename beside it:
    it is the one line on stdout, it keeps its mode, the link stays a link,
    nothing is committed, and no temporary is left beside it."""
    c = box.seam()
    real = c / HANDOFF_REL
    real.chmod(0o640)
    link = box.root / "estate" / "handoff.md"
    link.parent.mkdir()
    link.symlink_to(real)
    prepared = box.root / "prepared.md"
    prepared.write_text("# published whole\n", encoding="utf-8")
    head, tip = box.head(c), box.origin_head()
    result = box.helper("publish-handoff", LANE, str(link), str(prepared),
                        "--expect-digest", sha(real))
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{real}\n"
    assert real.read_text(encoding="utf-8") == "# published whole\n"
    assert stat.S_IMODE(real.stat().st_mode) == 0o640
    assert link.is_symlink()
    _no_temporary_beside(real)
    assert box.head(c) == head and box.origin_head() == tip, "publish-handoff commits nothing"


def test_publish_handoff_refuses_a_handoff_that_changed_exit_7(box: Box):
    c = box.seam()
    real = c / HANDOFF_REL
    prepared = box.root / "prepared.md"
    prepared.write_text("# published whole\n", encoding="utf-8")
    result = box.helper("publish-handoff", LANE, str(real), str(prepared),
                        "--expect-digest", "0" * 64)
    assert result.returncode == 7, result.stderr
    assert "the handoff changed before publication; nothing was published" in result.stderr
    assert real.read_text(encoding="utf-8") == HANDOFF
    assert result.stdout == ""
    _no_temporary_beside(real)


FENCES = {
    # name: (the intent's state, the publish's fence flags, exit, words)
    "owned": ("preparing", ("--operation", "op-a23", "--generation", "3", "--attempt", "0",
                            "--state", "preparing", "--transcript", "none"), 0, ""),
    "lost": ("preparing", ("--operation", "op-a23", "--generation", "4", "--attempt", "0",
                           "--state", "preparing", "--transcript", "none"), 7,
             "this handoff publisher lost restart ownership; nothing was published"),
    "active": ("pending", (), 7, "an active restart owns this handoff; nothing was published"),
    "half": ("preparing", ("--operation", "op-a23"), 64,
             "operation publication needs generation, attempt, state and transcript fences"),
}


@pytest.mark.parametrize("case", FENCES)
def test_publish_handoff_restart_fences(box: Box, case: str):
    """The five fences are the intent's own or nothing is published: a lost
    operation is 7, an active restart with no fences is 7, and an operation
    without its other four fences is 64."""
    c = box.seam()
    real = c / HANDOFF_REL
    state, flags, code, words = FENCES[case]
    box.intent(state, "--expect", "none", "--operation", "op-a23", "--generation", "3",
               "--handoff", str(real))
    prepared = box.root / "prepared.md"
    prepared.write_text("# fenced\n", encoding="utf-8")
    result = box.helper("publish-handoff", LANE, str(real), str(prepared),
                        "--expect-digest", sha(real), *flags)
    assert result.returncode == code, result.stderr
    assert words in result.stderr
    assert real.read_text(encoding="utf-8") == ("# fenced\n" if code == 0 else HANDOFF)
    _no_temporary_beside(real)


def test_publish_handoff_refuses_a_file_the_restart_did_not_bind(box: Box):
    """Under an operation, the file published must be the one the intent
    binds — compared as the same file, never by spelling (2)."""
    c = box.seam()
    real = c / HANDOFF_REL
    other = c / "handoffs" / "README.md"
    box.intent("preparing", "--expect", "none", "--operation", "op-a23", "--generation", "3",
               "--handoff", str(other))
    prepared = box.root / "prepared.md"
    prepared.write_text("# fenced\n", encoding="utf-8")
    result = box.helper("publish-handoff", LANE, str(real), str(prepared),
                        "--expect-digest", sha(real), "--operation", "op-a23",
                        "--generation", "3", "--attempt", "0", "--state", "preparing",
                        "--transcript", "none")
    assert result.returncode == 2, result.stderr
    assert "the publication target is not the operation-bound handoff" in result.stderr
    assert real.read_text(encoding="utf-8") == HANDOFF
