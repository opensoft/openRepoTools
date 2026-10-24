# SPDX-License-Identifier: Apache-2.0
"""Amendment 23, act 2's slice 2b: `lane-handoff` writes the PAUSED handoff
only through the lane's own register checkout.

Until this slice `lane-handoff` resolved the row's handoff cell against
`LANES_REPO` and then W (`workspace-root`), published the new top block there
under W's lock, and then added, committed, pulled and pushed it in W with no
lock at all, its output and git's words sent to `/dev/null` (lane
openRepoTools-3's finding 282, its second writer). Under the default
resolution every other write of the lane already went through
`<W>-lanes/<lane>/` (slice 1a), so the handoff was the one write left in W.

Now:
  * the file is the one `lanes-edit.sh handoff-path <lane> --create` names,
    in the checkout the lane's writes go through;
  * the top block is ONE `write-handoff --prepend` call, under that
    checkout's lock and S3/S4: written, committed by pathspec with the
    `Lane:` trailer and pushed, and where S3 refuses, written and NOT
    committed, with git's and S3's words printed rather than discarded;
  * the register's file-level PAUSED line is appended with `LANES_LANE`.

Each case drives a real `lane-handoff` in `test_lane_start_row_stamp`'s
sandbox with the default resolution (no `LANES_REPO`, no `LANES_FILE`) and the
opt-in `LANES_ROUTE_WRITES=1`, after a real `lane-start` made the lane's row
and checkout. W is brought up to origin first, so the old code finds the
handoff there and its unlocked commit in W is what each case sees at the base.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from conftest import REPO
from test_a23_lane_start import (HANDOFF, _assert_nothing_unpublished, _assert_W_only_fast_forwarded,
                                 _cell, _edit, _origin, _peer_push, _published, _started, _tip)
from test_lane_start_row_stamp import LANE, Sandbox, pytestmark, short_root  # noqa: F401

WHY = "a test handoff"
SUBJECT = f"handoff({LANE}@Eagle): PAUSED, {WHY}"


def _handoff(box: Sandbox, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """`lane-handoff --lane repoZ-1 … <why>`, from a shell with no tmux."""
    if not (box.bin / "lane-handoff").exists():
        shutil.copy2(REPO / "lane-handoff", box.bin / "lane-handoff")
        (box.bin / "lane-handoff").chmod(0o755)
    # A LANE WINDOW'S OWN SEAMS STAY OUT: `WORKBENCHES_CLAUDE_*` names the
    # caller's window and checkout, which `lane-handoff` reads where tmux is off.
    full = {k: v for k, v in box.env.items() if not k.startswith("WORKBENCHES_")}
    full.update(LANE_HANDOFF_NO_TMUX="1", CLAUDE_PROFILE_NAME="test-profile")
    full.update(env or {})
    return subprocess.run([str(box.bin / "lane-handoff"), "--lane", LANE, *args, WHY],
                          env=full, capture_output=True, text=True, timeout=180, check=False)


def _ready(tmp_path: Path, short_root: Path) -> tuple[Sandbox, Path, str, list[str]]:
    """A started lane whose handoff a peer wrote, with W brought up to origin
    (so W has it too, as `lane-start`'s refreshes leave it)."""
    box, checkout, _lane_dir, before = _started(tmp_path, short_root)
    cell = _cell(box)
    _peer_push(box, {cell: HANDOFF}, "the lane's handoff, written elsewhere")
    assert _edit(box, "refresh-workspace").returncode == 0
    assert (box.wip / cell).read_text(encoding="utf-8") == HANDOFF
    return box, checkout, cell, before


# -------------------------------------------------------------------- cases

def test_handoff_written_and_pushed_from_checkout(tmp_path, short_root):
    box, checkout, cell, before = _ready(tmp_path, short_root)

    result = _handoff(box)
    assert result.returncode == 0, result.stderr

    published = _published(box, cell)
    block, sep, rest = published.partition("\n---\n\n")
    assert sep and rest == HANDOFF, published
    assert block.startswith(f"Lane: {LANE} (test-profile, session "), block
    assert "## RESUME PROMPT — PAUSED " in block and f"({WHY})" in block, block
    assert _origin(box, "log", "-1", "--format=%s", "main", "--", cell).strip() == SUBJECT
    assert f"Lane: {LANE}" in _origin(box, "log", "-1", "--format=%b", "main", "--", cell)
    assert f"handoff refreshed: {checkout}/{cell} " in result.stderr, result.stderr
    assert f"committed: {SUBJECT}" in result.stderr, "write-handoff's own words are printed"

    # THE ONE WRITE IN W IS GONE: W moved only by fast-forward, and its copy of
    # the handoff took no byte from this act.
    _assert_W_only_fast_forwarded(box, before)
    assert (box.wip / cell).read_text(encoding="utf-8") in (HANDOFF, published)
    assert (checkout / cell).read_text(encoding="utf-8") == published
    _assert_nothing_unpublished(box, checkout)


def test_S3_refusal_writes_file_no_commit_prints_git_words(tmp_path, short_root):
    box, checkout, cell, before = _ready(tmp_path, short_root)
    # THE CHECKOUT IS CURRENT FIRST: S3 refuses a foreign staged entry before it
    # fast-forwards, so a checkout still behind the peer's handoff commit has no
    # file to write into (`write-handoff`'s 8), which is another case.
    box.git("-C", str(checkout), "fetch", "-q", "origin", "main")
    box.git("-C", str(checkout), "merge", "-q", "--ff-only", "origin/main")
    assert (checkout / cell).read_text(encoding="utf-8") == HANDOFF
    foreign = checkout / "handoffs" / "repoQ" / "foreign.md"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text("a person's file, staged and never committed\n", encoding="utf-8")
    box.git("-C", str(checkout), "add", "--", "handoffs/repoQ/foreign.md")
    tip = _tip(box)

    result = _handoff(box)
    assert result.returncode == 0, result.stderr

    # WRITTEN (R-A11-11: a swap is never left unwritten) and NOT committed.
    written = (checkout / cell).read_text(encoding="utf-8")
    assert written.startswith(f"Lane: {LANE} (test-profile, session "), written
    assert written.endswith("\n---\n\n" + HANDOFF), written
    assert box.git("-C", str(checkout), "status", "--porcelain", "--", cell).startswith(" M "), \
        "the handoff is modified in the checkout and not committed"
    assert "handoffs/repoQ/foreign.md" in box.git("-C", str(checkout), "diff", "--cached", "--name-only")
    assert _tip(box) == tip, "nothing was published, from the lane's checkout or from W"
    # THE WORDS ARE PRINTED, NOT SENT TO /dev/null: S3's refusal naming the
    # entry, the helper's note, and lane-handoff's own.
    assert "the index holds staged entries this write did not make" in result.stderr, result.stderr
    assert "handoffs/repoQ/foreign.md" in result.stderr
    assert "the handoff is WRITTEN and NOT committed" in result.stderr
    assert f"commit -m \"{SUBJECT}\"" in result.stderr, result.stderr
    assert "NOT committed" in result.stderr and "write-handoff` exited 2" in result.stderr, result.stderr

    _assert_W_only_fast_forwarded(box, before)
    assert (box.wip / cell).read_text(encoding="utf-8") == HANDOFF, "W's copy took no byte"


def test_append_line_carries_LANES_LANE(tmp_path, short_root):
    box, checkout, cell, _before = _ready(tmp_path, short_root)
    calls = box.root / "lanes-edit-calls.log"
    wrapper = box.root / "recording-lanes-edit.sh"
    wrapper.write_text(f"""#!/usr/bin/env bash
printf '%s LANES_LANE=%s\\n' "${{1-}}" "${{LANES_LANE-<unset>}}" >> '{calls}'
exec '{box.bin / "lanes-edit.sh"}' "$@"
""", encoding="utf-8")
    wrapper.chmod(0o755)

    result = _handoff(box, env={"LANES_EDIT": str(wrapper)})
    assert result.returncode == 0, result.stderr

    recorded = calls.read_text(encoding="utf-8").splitlines()
    for verb in ("append-line", "write-handoff"):
        made = [line for line in recorded if line.startswith(verb + " ")]
        assert made == [f"{verb} LANES_LANE={LANE}"], (verb, recorded)
    register = _published(box, "lanes/LANES.md")
    assert f"PAUSED — lane {LANE}, session " in register and f", {WHY} kind unknown; handoff refreshed" in register, \
        register
    assert _published(box, cell).endswith("\n---\n\n" + HANDOFF)
    _assert_nothing_unpublished(box, checkout)


def test_no_git_handoff_says_written_and_nothing_committed(tmp_path, short_root):
    """728, and question 4 of the review of #316: under `LANES_NO_GIT=1` the
    block is written in the lane's checkout and nothing is committed, and the
    exit-0 words say so rather than point at a commit and a push."""
    box, checkout, cell, _before = _ready(tmp_path, short_root)
    # NOTHING IS FETCHED UNDER LANES_NO_GIT, so the checkout is current first.
    box.git("-C", str(checkout), "fetch", "-q", "origin", "main")
    box.git("-C", str(checkout), "merge", "-q", "--ff-only", "origin/main")
    head = box.git("-C", str(checkout), "rev-parse", "HEAD")
    tip = _tip(box)

    result = _handoff(box, env={"LANES_NO_GIT": "1"})
    assert result.returncode == 0, result.stderr
    written = (checkout / cell).read_text(encoding="utf-8")
    assert written.startswith(f"Lane: {LANE} (test-profile, session "), written
    assert written.endswith("\n---\n\n" + HANDOFF), written
    assert box.git("-C", str(checkout), "rev-parse", "HEAD") == head, "nothing is committed"
    assert _tip(box) == tip, "or pushed"
    assert "what it committed and pushed" not in result.stderr, result.stderr
    said = [line for line in result.stderr.splitlines()
            if "LANES_NO_GIT=1" in line and "nothing is committed" in line]
    assert len(said) == 1, result.stderr
