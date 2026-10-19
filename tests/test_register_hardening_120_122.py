# SPDX-License-Identifier: Apache-2.0
"""The register's two rewrites prove what they copied and what landed, the
sweep's preflight asks `ensure_log`'s own question, a lane whose log already
closes it is told so, and add-row's archive scan refuses a line it cannot take
apart: opensoft/openRepoTools#120 (Copilot round 5 on #93) and #122 (round 6).

Each case builds the throwaway register `test_register_scan_hardening_138.py`
builds — a bare repository and a clone of it in a temporary directory, with a
temporary `$HOME` — and runs the real `lanes-edit.sh` against it. A write that
has to come out short is cut by a `cat` first on `PATH` that cuts ONE exact
copy and hands every other call to the real one; a scan that has to fail, by
an `awk` that refuses ONE exact program. Nothing here reaches a network or the
operator's own register.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_register_scan_hardening_138 import (  # noqa: F401  (pytestmark is this module's too)
    HEADER, OLD_ID, Register as SweepRegister, lane_line, log_text, pytestmark, row)

NEW_ID = "cccc0122-0003-4000-8000-000000000003"
#: The archive exactly as `archive_rows` creates it: a title, a paragraph, then
#: the header (line 7) and its rule (line 8). Rows follow from line 9.
ARCHIVE_HEAD = ("# LANES-retired.md — rows RETIRED out of `lanes/LANES.md`\n\n"
                "lane-collision-protocol Amendment 19(d). These lanes are finished. Their\n"
                "positions are NEVER REISSUED: every reader of the next free position and\n"
                "`lanes --closed` read this file beside the register.\n\n" + HEADER)
#: The copy seam reads where a `cat`'s output is going, which only Linux says.
PROC_FD = pytest.mark.skipif(not Path("/proc/self/fd/1").exists(),
                             reason="the copy seam reads /proc/<pid>/fd/1")


class Register(SweepRegister):
    """`test_register_scan_hardening_138`'s register, with thirty rows of another
    repository below repoX's — so a copy cut at half its lines still holds every
    row a case edits — and the seams these cases need."""

    def __init__(self, tmp: Path):
        super().__init__(tmp)
        self.write("lanes/LANES.md", self.read("lanes/LANES.md") + "".join(
            row(f"repoZ-{n}", OLD_ID, f"another repository's row {n}") for n in range(1, 31)))
        self.publish("another repository's rows")

    def published(self, rel: str) -> str:
        return self.raw_git("-C", str(self.origin), "show", f"main:{rel}")

    def shim(self, name: str, body: str) -> None:
        """A `<name>` first on PATH: `body`, then the real one."""
        real = shutil.which(name, path=os.environ.get("PATH"))
        path = self.fakebin / name
        path.write_text(f'#!/usr/bin/env bash\n{body}\nexec "{real}" "$@"\n')
        path.chmod(0o755)

    def cut_cat(self, cut: str) -> None:
        """A `cat` that cuts a copy at half its lines. `copy…`: the
        register's copy into a file named `pre`, the copy every proof of a
        rewrite is made against. `write…`: the rewrite itself, `cat -- <tmp>/out`
        into the register — and with `…and restore fail`, the copy's bytes put
        back into the register as well. `…fail(s)` exits 1 after the half, as a
        full disk does; `…says done` exits 0, a short write nothing reported."""
        rc = 0 if cut.endswith("says done") else 1
        goes_to = 'case "$(readlink "/proc/$$/fd/1" 2>/dev/null)" in {} ) true ;; *) false ;; esac'
        if cut.startswith("copy"):
            when = ('[ "${1-}" = -- ] && case "${2-}" in */lanes/LANES.md) true ;; *) false ;; esac && '
                    + goes_to.format("*/pre"))
        elif cut == "write and restore fail":
            when = ('[ "${1-}" = -- ] && case "${2-}" in */out) true ;; '
                    '*/pre) ' + goes_to.format("*/lanes/LANES.md") + ' ;; *) false ;; esac')
        else:
            when = '[ "${1-}" = -- ] && case "${2-}" in */out) true ;; *) false ;; esac'
        self.shim("cat", f'if {when}; then\n'
                         f'  n=$(wc -l < "$2"); head -n $((n / 2)) -- "$2"; exit {rc}\nfi')


@pytest.fixture
def reg(tmp_path: Path) -> Register:
    return Register(tmp_path)


# ------------------------------------------- #120 item 1: the two rewrites

def retire_repo_x_3(reg: Register) -> None:
    reg.write("lanes/LANES.md", reg.read("lanes/LANES.md").replace(
        "| more old words |", "| RETIRED · 2026-09-01T00:00:00Z · swept |"))
    reg.publish("repoX-3 retired")


#: The one act per rewrite: `set-row-state` ends in `replace_line`, and
#: `archive-rows --yes` in `delete_lines`.
ACTS = {
    "replace_line": ("set-row-state", "repoX-2", "PAUSED · cut short"),
    "delete_lines": ("archive-rows", "repoX", "--yes"),
}
CUTS = ["copy fails", "copy says done", "write fails", "write says done",
        "write and restore fail"]


@PROC_FD
@pytest.mark.parametrize("cut", CUTS)
@pytest.mark.parametrize("act", sorted(ACTS))
def test_120_item_1_a_rewrite_cut_short_leaves_the_register_whole(reg, act, cut):
    """#120 item 1: `cat -- <out> > LANES.md` had its status read, but not
    its result, and `>` truncates before `cat` writes. A write that failed
    part-way left a HALF register behind a refusal that called it UNCHANGED;
    one that was short and said nothing was a half register committed (exit
    0). And the COPY every proof is made against was read with no status at
    all, so a short copy made a short register look like a one-line edit of
    itself: rewritten, committed and pushed. Each refuses (5) now, and the
    register on disk and on origin is byte for byte what it was — or, where
    the bytes could not be put back either, the refusal says the register MAY
    NOW BE TRUNCATED and how to restore it, and nothing is committed."""
    if act == "delete_lines":
        retire_repo_x_3(reg)
    register = reg.read("lanes/LANES.md")
    before = reg.head()
    reg.cut_cat(cut)
    result = reg.run(*ACTS[act], LANES_LANE="repoX-1")
    assert result.returncode == 5, (result.stdout, result.stderr)
    assert reg.head() == before
    assert reg.published("lanes/LANES.md") == register
    if cut == "write and restore fail":
        assert "IT MAY NOW BE TRUNCATED" in result.stderr
        assert "checkout -- lanes/LANES.md" in result.stderr
        assert "UNCHANGED" not in result.stderr
        return
    assert reg.read("lanes/LANES.md") == register
    if cut.startswith("copy"):
        assert "could not be copied whole" in result.stderr
    else:
        assert "have been put back and proved" in result.stderr
        assert "UNCHANGED" not in result.stderr


# ------------------------------- #120 item 2: the sweep's published-path scan

def case_sensitive(path: Path) -> bool:
    probe = path / "case-probe"
    probe.write_text("")
    try:
        return not (path / "CASE-PROBE").exists()
    finally:
        probe.unlink()


def test_120_item_2_a_rename_whose_commit_never_landed_refuses_in_the_scan(reg):
    """#120 item 2: the sweep's preflight asked whether origin publishes the
    log under another case only where this checkout had NO log, and compared a
    basename with a path besides. So the state a case-only rename leaves when
    its commit is not pushed — the row's spelling here, committed; the old
    spelling still on origin; a checkout merely AHEAD — passed the scan, and
    `ensure_log` refused it inside the write loop, after the lane before it had
    had its log created and appended. The scan refuses it now, with
    `ensure_log`'s own words, and nothing is written."""
    if not case_sensitive(reg.tmp):
        pytest.skip("two log names that differ only by case need a case-sensitive filesystem")
    reg.write("lanes/log/repox-3.md", log_text("repox-3", lane_line(
        "NOTED", "repoX-3", OLD_ID, "2026-09-13T00:00:00Z") + " — migrated; history kept here"))
    reg.publish("repoX-3's log, under the spelling it had before Amendment 15")
    reg.git("mv", "lanes/log/repox-3.md", "lanes/log/repoX-3.md")
    reg.git("commit", "-q", "-m", "repoX-3's log takes the row's spelling (not pushed)")
    before = reg.head()
    result = reg.sweep("repoX-2", "repoX-3")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "published as lanes/log/repox-3.md" in result.stderr
    assert "a case-only rename whose commit never landed" in result.stderr
    assert reg.head() == before
    assert not (reg.wip / "lanes/log/repoX-2.md").exists()
    assert reg.dirty() == ""


# ------------------------------- #120 item 3: a log that already closes the lane

@pytest.mark.parametrize("last", ["ENDED", "RETIRED"])
def test_120_item_3_a_lane_whose_log_closes_it_is_told_it_is_closed(reg, last):
    """#120 item 3: the refusal for a lane whose log's LAST lane-kind line is
    ENDED or RETIRED read the same as the one for a running lane, and named no
    way out. It says the lane is already CLOSED and hidden (19(b)), and names
    `archive-rows <repo>` (19(d)) — never `lane-end`, which is not the exit for
    a lane that has ended."""
    reg.write("lanes/log/repoX-2.md", log_text(
        "repoX-2", lane_line("STARTED", "repoX-2", OLD_ID, "2026-09-11T00:00:00Z"),
        lane_line(last, "repoX-2", OLD_ID, "2026-09-11T02:00:00Z")))
    reg.publish(f"repoX-2 started and {last.lower()}")
    before = reg.head()
    result = reg.sweep("repoX-2")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert f"{last} line" in result.stderr
    assert "already CLOSED" in result.stderr
    assert "lanes-edit.sh archive-rows repoX" in result.stderr
    assert "lane-end" not in result.stderr
    assert reg.head() == before


def test_120_item_3_a_lane_whose_log_says_it_is_parked_is_sent_to_lane_end(reg):
    """…and the other branch: a log whose last lane-kind line is STARTED,
    PAUSED or RESUMED is a lane a person can still pick up, so the refusal
    sends it to `lane-end <lane>` and not to the archive."""
    reg.write("lanes/log/repoX-2.md", log_text(
        "repoX-2", lane_line("STARTED", "repoX-2", OLD_ID, "2026-09-11T00:00:00Z"),
        lane_line("PAUSED", "repoX-2", OLD_ID, "2026-09-11T01:00:00Z")))
    reg.publish("repoX-2 is parked")
    result = reg.sweep("repoX-2")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "carries a PAUSED line" in result.stderr
    assert "lane-end repoX-2" in result.stderr
    assert "archive-rows" not in result.stderr


# --------------------------------------------- #122: add-row's archive scan

RETIRED_CELL = "RETIRED · 2026-08-02T00:00:00Z · moved"
#: Three ways a hand edit or a bad merge leaves a row of repoX-4 that the scan
#: cannot take apart, each with what it does to the first cell.
MANGLED = {
    "the lane lost its backticks": f"| repoX-4 | harness `{OLD_ID}` | Eagle / test / brett | 2026-08-01 | none | none | {RETIRED_CELL} |",
    "no backtick at all": f"| repoX-4 | harness {OLD_ID} | Eagle / test / brett | 2026-08-01 | none | none | {RETIRED_CELL} |",
    "one backtick lost": f"| `repoX-4 | harness {OLD_ID} | Eagle / test / brett | 2026-08-01 | none | none | {RETIRED_CELL} |",
}


def add_repo_x_4(reg: Register) -> subprocess.CompletedProcess:
    return reg.run("add-row", row("repoX-4", NEW_ID, "new here", "2026-10-19").rstrip("\n"),
                   LANES_LANE="repoX-4")


@pytest.mark.parametrize("where", ["published", "committed here, not pushed"])
@pytest.mark.parametrize("mangle", sorted(MANGLED))
def test_122_an_archive_row_the_scan_cannot_take_apart_reissues_no_position(reg, mangle, where):
    """#122: the scan skipped any archive table line with no backticked lane
    token — and read a first backtick in ANOTHER cell as the lane — so a
    retired row whose lane cell a hand edit had mangled disappeared from the
    answer, and add-row reissued its position (exit 0). Such a line is refused
    by its line number now (1). The archive's own header and its rule are
    `|` lines with no backtick on every archive `archive_rows` writes, and
    they are not named."""
    mangled = MANGLED[mangle]
    reg.write("lanes/archive/LANES-retired.md", ARCHIVE_HEAD
              + row("repoX-9", OLD_ID, RETIRED_CELL, "2026-08-01") + mangled + "\n")
    if where == "published":
        reg.publish("the archive, with a hand-mangled row 10")
    else:
        reg.commit("the archive, with a hand-mangled row 10 (not pushed)")
    before = reg.head()
    result = add_repo_x_4(reg)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert f"line 10: {mangled}" in result.stderr
    assert f"line 7: {HEADER.splitlines()[0]}" not in result.stderr
    assert "line 8: |---|" not in result.stderr
    assert reg.head() == before
    assert "`repoX-4`" not in reg.published("lanes/LANES.md")


def test_122_an_archive_scan_that_failed_is_not_an_archive_with_no_match(reg):
    """#122, the `|| :` half: the scan's status was the `sort -u` behind it,
    so an awk that FAILED read as "no archived row matched" and the archived
    repoX-4 was added again (exit 0). It is a refusal (1) now."""
    reg.write("lanes/archive/LANES-retired.md", ARCHIVE_HEAD
              + row("repoX-4", OLD_ID, RETIRED_CELL, "2026-08-01"))
    reg.publish("the archive holds repoX-4")
    reg.shim("awk", 'case "$*" in *"function key("*) echo "test shim: awk refused" >&2; exit 2 ;; esac')
    before = reg.head()
    result = add_repo_x_4(reg)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert reg.head() == before
    assert "`repoX-4`" not in reg.published("lanes/LANES.md")
