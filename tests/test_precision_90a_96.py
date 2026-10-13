# SPDX-License-Identifier: Apache-2.0
"""`lane-end`'s two precision defects: its synopsis says a DUPLICATE HOLDER
retire "ends nothing" (opensoft/openRepoTools#96), and its narrowed state-cell
scan skips ratified decision O1's cap and its `|` and CR/LF rules, so a cell
that is not the phrase can hide an open LANDING (#90, part (a)).

EVERY RUN HERE IS A REAL `lane-end` IN A SANDBOX: `test_lane_start_claude_current`'s
workstation (a bare origin, a workspace clone whose register is a header,
`workspace.yaml` pointing at it) with the lane's row written into it and
pushed, so the published row `register-row` reads is the same row. The lane
has NO object log, which is the one path that still decides a merge hold from
prose, and the close-out gate's `lane-worktrees` is a stub that finds nothing,
so a cell that wrongly reads clear is a lane that ENDS rather than one that
trips over the gate.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from test_lane_start_claude_current import Sandbox, LANE, _write, pytestmark
from conftest import REPO

UTC = "2026-10-11T10:00:00Z"
UUID = "aaaa0090-9090-4000-8000-aaaa00909090"


# ------------------------------------------------------------------- #96

def _synopsis(help_text: str) -> list[str]:
    """The USAGE block of `--help`, one string per synopsis entry: a line that
    opens `  lane-end` and the `#` continuation lines under it."""
    block = help_text.split("\nUSAGE\n", 1)[1].split("\n\n", 1)[0]
    entries: list[str] = []
    for line in block.splitlines():
        if line.startswith("  lane-end"):
            entries.append(line)
        else:
            entries[-1] += " " + line
    return [" ".join(entry.split()) for entry in entries]


@pytest.fixture
def synopsis(tmp_path: Path) -> list[str]:
    result = subprocess.run(["bash", str(REPO / "lane-end"), "--help"],
                            env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    return _synopsis(result.stdout)


def test_the_synopsis_says_what_a_duplicate_holder_retire_does(synopsis):
    """`--retire <pid>` on a DUPLICATE HOLDER TERMs the bg-pty-host pair, and
    the one-line summary said `ends nothing`: true of a FORK, the opposite of
    the act on a duplicate holder (#96)."""
    duplicate = [e for e in synopsis if "--retire <" in e and "DUPLICATE" in e]
    assert len(duplicate) == 1, synopsis
    assert "TERM" in duplicate[0], duplicate[0]
    assert "ends nothing" not in duplicate[0], duplicate[0]


def test_the_synopsis_keeps_the_fork_and_the_duplicate_on_their_own_lines(synopsis):
    """The split is the fix: the FORK entry still says it writes and kills
    nothing, and names no DUPLICATE, whose words differ."""
    fork = [e for e in synopsis if "--retire <" in e and "FORK" in e]
    assert len(fork) == 1, synopsis
    assert "kills nothing" in fork[0], fork[0]
    assert "DUPLICATE" not in fork[0], fork[0]


# ------------------------------------------------------------------ #90 (a)

def _line(length: int, tail: str) -> str:
    """A phrase line of exactly `length` characters ending in `tail`."""
    filler = length - len(tail)
    assert filler > 0
    return "x" * filler + tail


@pytest.fixture
def ended(tmp_path: Path):
    """`ended(cell)` runs `lane-end` on a lane whose register row carries
    `cell` as its state, in this checkout's row and in the published one, and
    returns the process and the row as the register has it afterwards."""
    box = Sandbox(tmp_path)
    shutil.copy2(REPO / "lane-end", box.bin / "lane-end")
    (box.bin / "lane-end").chmod(0o755)
    stub = _write(box.bin / "lane-worktrees", "#!/usr/bin/env bash\nexit 0\n")
    register = box.wip / "lanes" / "LANES.md"
    seed = register.read_text(encoding="utf-8")

    def row(cell: str) -> str:
        return (f"| `{LANE}` | harness `{UUID}` | Eagle / test / brett | "
                f"2026-10-11T00:00Z | none | handoffs/repoZ/x.md | {cell} |\n")

    def run(cell: str, published: str | None = None):
        """`published` is the cell origin/main carries when it is not this
        checkout's own: pushed first, then this checkout's row put back."""
        if published is not None:
            register.write_text(seed + row(published), encoding="utf-8")
            box.git("-C", str(box.wip), "commit", "-q", "-am", "the published row")
            box.git("-C", str(box.wip), "push", "-q", "origin", "main")
        register.write_text(seed + row(cell), encoding="utf-8")
        if published is None:
            box.git("-C", str(box.wip), "commit", "-q", "-am", "the row")
            box.git("-C", str(box.wip), "push", "-q", "origin", "main")
        env = dict(box.env, LANE_WORKTREES=str(stub))
        result = subprocess.run([str(box.bin / "lane-end"), LANE], env=env,
                                cwd=str(box.lane_dir), capture_output=True,
                                text=True, timeout=120, check=False)
        after = next(l for l in register.read_text(encoding="utf-8").splitlines()
                     if l.startswith(f"| `{LANE}`"))
        return result, after

    return run


HOLD = "LANDING #7 into repoZ main"
READ = "the last LANDING in its state cell"


def test_a_line_over_the_cap_cannot_hide_an_open_landing(ended):
    """THE DEFECT: `LIVE · <UTC> · <241 characters ending in LANDING #7>` had
    its scan narrowed to `LIVE`, so the lane ENDED over a hold other lanes'
    merges wait on. O1's cap is on the line; a cell past it is not the phrase
    and is read whole (#90, part (a))."""
    line = _line(241, " " + HOLD)
    assert len(line) == 241
    result, after = ended(f"LIVE · {UTC} · {line}")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert READ in result.stderr, result.stderr
    assert "lane-end on" not in after, after


@pytest.mark.parametrize("line", [
    pytest.param(f"held up | {HOLD}", id="a pipe"),
    pytest.param(f"held up\r{HOLD}", id="a carriage return"),
])
def test_a_line_with_a_pipe_or_a_carriage_return_cannot_hide_an_open_landing(ended, line):
    """O1's other two rules: the line holds no `|` and no CR/LF. A cell that
    breaks either is not the phrase, and its words are all read."""
    result, after = ended(f"LIVE · {UTC} · {line}")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert READ in result.stderr, result.stderr
    assert "lane-end on" not in after, after


def test_the_published_row_is_read_whole_when_it_is_not_the_phrase(ended):
    """The fallback reads TWO cells and either one showing a hold refuses: this
    checkout's row says nothing, the one on origin/main is past the cap."""
    published = f"LIVE · {UTC} · {_line(241, ' ' + HOLD)}"
    result, after = ended(f"LIVE · {UTC} · all quiet", published=published)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "the published row on origin/main" in result.stderr, result.stderr
    assert "lane-end on" not in after, after


def test_a_line_exactly_at_the_cap_is_still_prose(ended):
    """THE BOUNDARY IS INCLUSIVE and the phrase is unchanged: a valid line that
    says `LANDING #7` is a lane waiting for one, not a hold (Amendment 13(a)),
    and 240 characters is the longest line `set-row-state` accepts."""
    line = _line(240, " waiting for " + HOLD)
    assert len(line) == 240
    result, after = ended(f"LIVE · {UTC} · {line}")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "| ENDED · " in after, after


def test_a_line_over_the_cap_that_holds_nothing_still_ends(ended):
    """Reading the whole cell is a refusal only where the cell holds
    something: a malformed one with no LANDING or CLAIMED in it closes."""
    result, after = ended(f"LIVE · {UTC} · {_line(300, ' and all of it quiet')}")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "| ENDED · " in after, after
