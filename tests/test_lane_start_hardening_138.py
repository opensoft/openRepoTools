# SPDX-License-Identifier: Apache-2.0
"""`lane-start`'s three fail-open fences from opensoft/openRepoTools#138
(items 3, 14 and 16), each proved through a real `lane-start` in the sandbox
`tests/test_lane_start_claude_current.py` builds: a bare origin, a workspace
clone holding the register, and a fake `tmux` on PATH. Nothing here reaches a
real tmux server, a real Claude Code or the network.

The fake `tmux` is STATEFUL, because two of the three items are about what the
server's window names are at a given moment: `$FAKE_TMUX_STATE` holds one
`<@id><TAB><name>` line per window, this window is `@1`, `list-windows` prints
the file and `rename-window` edits it.

  item 3   the window-name uniqueness check and the rename ran under no shared
           reservation, so two concurrent starts could both take a name. The
           rename is now read back: a name another window also carries after it
           is refused, and this window's own rename undone.
  item 14  the retired-identity fence asked only the ARCHIVE, so a row RETIRED
           in `lanes/LANES.md`, or a log ending on RETIRED, passed. ENDED is
           not terminal (Amendment 18(b): it releases the binding) and an
           ENDED lane is still resumed.
  item 16  the new-lane window-name fence skipped THIS window, so a new lane
           started from a window still named for another registered lane took
           that lane's tmux address.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from test_lane_start_claude_current import Sandbox, LANE, _write, pytestmark  # noqa: F401

SID = "aaaa0138-1111-4000-8000-aaaa01381111"

FAKE_TMUX = r"""#!/usr/bin/env bash
# The sandbox's tmux server, as a file: one `<@id><TAB><name>` line per window,
# and this window is @1. `$FAKE_TMUX_RIVAL` names a window whose own lane-start
# renames it to the same name the instant before this run's rename lands (once).
st="$FAKE_TMUX_STATE"
name_of() { awk -F'\t' -v w="$1" '$1 == w { print $2; exit }' "$st"; }
set_name() {
  awk -F'\t' -v OFS='\t' -v w="$1" -v n="$2" '$1 == w { $2 = n } { print }' "$st" > "$st.new" &&
    mv -f "$st.new" "$st"
}
case "${1-}" in
  list-windows)
    if [ -n "${FAKE_TMUX_LIST_FAILS_AFTER_RENAME:-}" ] &&
       command grep -q '^rename-window' "$FAKE_TMUX_LOG"; then
      exit 1
    fi
    cat "$st" ;;
  display-message)
    shift
    t=""; f=""
    while [ $# -gt 0 ]; do
      case "$1" in
        -p) shift ;;
        -t) t="${2-}"; shift 2 ;;
        *)  f="$1"; shift ;;
      esac
    done
    if [ -n "$t" ]; then
      case "$t" in
        testsess:0|testsess:@1|@1) : ;;
        *) exit 1 ;;
      esac
    fi
    case "$f" in
      '#{session_name}:#{window_id}')    echo 'testsess:@1' ;;
      '#{session_name}:#{window_index}') echo 'testsess:0' ;;
      '#S:#I')                           echo 'testsess:0' ;;
      '#{session_name}')                 echo 'testsess' ;;
      '#{window_id}')                    echo '@1' ;;
      '#W'|'#{window_name}')             name_of @1 ;;
      '#{pane_current_command}')         echo 'claude' ;;
      *)                                 echo ;;
    esac ;;
  rename-window)
    shift
    [ "${1-}" != -t ] || shift 2
    printf 'rename-window %s\n' "${1-}" >> "$FAKE_TMUX_LOG"
    if [ -n "${FAKE_TMUX_RIVAL:-}" ] && [ ! -e "$st.raced" ]; then
      : > "$st.raced"
      set_name "$FAKE_TMUX_RIVAL" "${1-}"
    fi
    set_name @1 "${1-}" ;;
  show-options)
    printf '%s\n' "${FAKE_TMUX_AUTO_RENAME-}" ;;
  set-option|set-window-option)
    printf '%s\n' "$*" >> "$FAKE_TMUX_LOG" ;;
  *) : ;;
esac
"""


class Box(Sandbox):
    """The claude-current sandbox, with the stateful tmux above."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.tmux_state = root / "tmux-windows"
        _write(self.fakebin / "tmux", FAKE_TMUX)
        self.windows({"@1": "claude"})
        self.env["FAKE_TMUX_STATE"] = str(self.tmux_state)

    def windows(self, names: dict[str, str] | None = None) -> dict[str, str]:
        if names is not None:
            self.tmux_state.write_text(
                "".join(f"{w}\t{n}\n" for w, n in names.items()), encoding="utf-8")
        return dict(line.split("\t", 1) for line in
                    self.tmux_state.read_text(encoding="utf-8").splitlines())

    def tmux_calls(self) -> str:
        return self.tmux_log.read_text(encoding="utf-8")

    def register(self) -> Path:
        return self.wip / "lanes" / "LANES.md"

    def row_state(self, lane: str) -> str:
        line = next(ln for ln in self.register().read_text(encoding="utf-8").splitlines()
                    if ln.startswith(f"| `{lane}`"))
        return line.split("|")[-2].strip()

    def transcript(self, sid: str = SID) -> None:
        """The row's session as a transcript here, so a start resumes it by id."""
        key = re.sub(r"[^A-Za-z0-9]", "-", str(self.lane_dir))
        _write(self.home / ".claude" / "projects" / key / f"{sid}.jsonl",
               '{"type":"user"}\n', 0o644)

    def seed(self, rows=(), logs=None, push=True) -> None:
        """Append rows to the register and write object logs, in one commit."""
        reg = self.register()
        reg.write_text(reg.read_text(encoding="utf-8")
                       + "".join(r + "\n" for r in rows), encoding="utf-8")
        paths = ["lanes/LANES.md"]
        for lane, verbs in (logs or {}).items():
            _write(self.wip / "lanes" / "log" / f"{lane}.md",
                   log_text(lane, verbs, self.lane_dir), 0o644)
            paths.append(f"lanes/log/{lane}.md")
        self.git("-C", str(self.wip), "add", "--", *paths)
        self.git("-C", str(self.wip), "commit", "-q", "-m", "seed #138 rows")
        if push:
            self.git("-C", str(self.wip), "push", "-q", "origin", "main")

    def wrap_helper(self, case_arms: str) -> None:
        """Put a `lanes-edit.sh` in front of the real one, answering the given
        `case "$1:${2-}"` arms itself and delegating everything else."""
        real = self.bin / "lanes-edit-real.sh"
        (self.bin / "lanes-edit.sh").rename(real)
        _write(self.bin / "lanes-edit.sh", f'''#!/usr/bin/env bash
case "$1:${{2-}}" in
{case_arms}
esac
exec "{real}" "$@"
''')


def row(lane: str, state: str) -> str:
    return (f"| `{lane}` | harness `{SID}` | Eagle / test / brett | 2026-09-11T00:00Z "
            f"| none | handoffs/repoZ/x.md | {state} |")


def log_text(lane: str, verbs, lane_dir: Path) -> str:
    lines = [f"# lane {lane} — object log (lane-collision-protocol Amendment 7)"]
    for i, verb in enumerate(verbs):
        head = f"{verb} — lane {lane}, session {SID}@Eagle, 2026-09-12T{9 + i:02d}:00:00Z, lane:{lane}"
        if verb in ("STARTED", "RESUMED"):
            lines.append(f"{head} → home opensoft/repoZ; estate repoZ; dir {lane_dir}")
        elif verb == "PAUSED":
            lines.append(f"{head} → swap; dir {lane_dir}; workstation Eagle")
        else:
            lines.append(f"{head} — closed in the #138 sandbox")
    return "\n".join(lines) + "\n"


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def nothing_done(box: Box, before: int, result: subprocess.CompletedProcess) -> None:
    assert box.commits() == before, result.stderr
    assert box.claude_runs() == ""
    assert result.stdout == ""


# ------------------------------------------------------------------- item 3

def test_item3_a_name_another_window_took_during_the_rename_is_given_back(box):
    """Two starts of one new lane in two windows: the rival's rename lands
    between this run's last check and its own rename. Read back, the name is
    on two windows, so this run refuses and undoes ITS rename."""
    box.windows({"@1": "claude", "@2": "zsh"})
    before = box.commits()
    result = box.start("--no-launch", FAKE_TMUX_RIVAL="@2")
    assert result.returncode == 2, result.stderr
    assert box.windows() == {"@1": "claude", "@2": LANE}, box.tmux_calls()
    assert "rename-window claude" in box.tmux_calls()
    assert "@2" in result.stderr
    nothing_done(box, before, result)
    assert LANE not in box.register().read_text(encoding="utf-8")
    assert box.lane_log() == ""


def test_item3_the_undo_restores_automatic_rename_when_the_window_had_it(box):
    box.windows({"@1": "claude", "@2": "zsh"})
    result = box.start("--no-launch", FAKE_TMUX_RIVAL="@2", FAKE_TMUX_AUTO_RENAME="")
    assert result.returncode == 2, result.stderr
    assert "set-option -w -u automatic-rename" in box.tmux_calls()


def test_item3_a_window_with_no_name_to_go_back_to_says_the_undo_was_not_made(box):
    box.windows({"@1": "", "@2": "zsh"})
    before = box.commits()
    result = box.start("--no-launch", FAKE_TMUX_RIVAL="@2")
    assert result.returncode == 2, result.stderr
    assert "could NOT be undone" in result.stderr
    assert "rename is undone" not in result.stderr
    assert box.tmux_calls().count("rename-window") == 1, box.tmux_calls()
    nothing_done(box, before, result)


def test_item3_a_read_back_that_fails_is_not_a_name_that_is_free(box):
    before = box.commits()
    result = box.start("--no-launch", FAKE_TMUX_LIST_FAILS_AFTER_RENAME="1")
    assert result.returncode == 2, result.stderr
    assert box.windows() == {"@1": "claude"}, box.tmux_calls()
    nothing_done(box, before, result)


def test_item3_an_uncontested_rename_is_kept(box):
    box.windows({"@1": "claude", "@2": "zsh"})
    result = box.start("--no-launch")
    assert result.returncode == 0, result.stderr
    assert box.windows() == {"@1": LANE, "@2": "zsh"}
    assert "set-option" not in box.tmux_calls()


# ------------------------------------------------------------------ item 14

RETIRED_CELL = "RETIRED · 2026-10-01T00:00:00Z · swept as dormant"
ENDED_CELL = "ENDED · 2026-10-01T00:00:00Z · lane-end on Eagle: window closing"
PAUSED_CELL = "PAUSED · 2026-10-01T00:00:00Z · swapped"


@pytest.mark.parametrize("cell, verbs", [
    (RETIRED_CELL, ("STARTED", "RETIRED")),
    (RETIRED_CELL, ()),
    (PAUSED_CELL, ("STARTED", "RETIRED")),
])
def test_item14_a_retired_lane_still_in_the_register_is_not_started(box, cell, verbs):
    """No archive row exists, so `retired-identity` answers 8: only the row's
    state cell or its log's last lane-kind line says the lane is retired."""
    box.seed([row(LANE, cell)], {LANE: verbs} if verbs else None)
    box.transcript()
    before = box.commits()
    result = box.start("--no-launch")
    assert result.returncode == 2, result.stderr
    assert "RETIRED" in result.stderr
    assert "rename-window" not in box.tmux_calls()
    nothing_done(box, before, result)


@pytest.mark.parametrize("cell, verbs", [
    (ENDED_CELL, ()),
    (PAUSED_CELL, ("STARTED", "PAUSED", "ENDED")),
    (PAUSED_CELL, ("STARTED", "PAUSED")),
])
def test_item14_an_ended_or_paused_lane_is_still_resumed(box, cell, verbs):
    """ENDED is "the window is closing", not "the lane is not coming back": it
    releases the binding as a PAUSED does (Amendment 18(b)), and the lane is
    resumed by its recorded session."""
    box.seed([row(LANE, cell)], {LANE: verbs} if verbs else None)
    box.transcript()
    result = box.start("--no-launch")
    assert result.returncode == 0, result.stderr
    assert f"--resume {SID}" in result.stdout
    assert box.windows() == {"@1": LANE}
    assert box.row_state(LANE).startswith("LIVE · "), box.row_state(LANE)
    assert box.lane_log().splitlines()[-1].startswith(f"RESUMED — lane {LANE}, session {SID}@")


def test_item14_a_retirement_this_checkout_has_not_pushed_is_still_one(box):
    box.seed([row(LANE, "PAUSED · 2026-10-01T00:00:00Z · swapped")],
             {LANE: ("STARTED", "PAUSED")})
    reg = box.register()
    reg.write_text(reg.read_text(encoding="utf-8").replace(
        "PAUSED · 2026-10-01T00:00:00Z · swapped",
        "RETIRED · 2026-10-02T00:00:00Z · retired here, not pushed"), encoding="utf-8")
    box.git("-C", str(box.wip), "commit", "-q", "-am", "unpushed retirement")
    before = box.commits()
    result = box.start("--no-launch")
    assert result.returncode == 2, result.stderr
    assert "RETIRED" in result.stderr
    assert "rename-window" not in box.tmux_calls()
    nothing_done(box, before, result)


def test_item14_a_log_that_cannot_be_read_is_not_a_lane_that_is_open(box):
    box.seed([row(LANE, "PAUSED · 2026-10-01T00:00:00Z · swapped")],
             {LANE: ("STARTED", "PAUSED")})
    box.wrap_helper("  lane-last:*) exit 1 ;;")
    before = box.commits()
    result = box.start("--no-launch")
    assert result.returncode == 1, result.stderr
    assert "lane-last" in result.stderr
    assert "rename-window" not in box.tmux_calls()
    nothing_done(box, before, result)


# ------------------------------------------------------------------ item 16

OTHER = "repoY-1"


def test_item16_a_new_lane_does_not_take_another_lanes_window(box):
    box.seed([row(OTHER, "PAUSED · 2026-10-01T00:00:00Z · swapped")])
    box.windows({"@1": OTHER})
    before = box.commits()
    result = box.start("--no-launch")
    assert result.returncode == 2, result.stderr
    assert OTHER in result.stderr
    assert box.windows() == {"@1": OTHER}
    assert "rename-window" not in box.tmux_calls()
    nothing_done(box, before, result)
    assert f"`{LANE}`" not in box.register().read_text(encoding="utf-8")


def test_item16_a_row_only_this_checkout_has_still_names_the_window(box):
    box.seed([row(OTHER, "LIVE · 2026-10-01T00:00:00Z · started")], push=False)
    box.windows({"@1": OTHER})
    result = box.start("--no-launch")
    assert result.returncode == 2, result.stderr
    assert OTHER in result.stderr
    assert "rename-window" not in box.tmux_calls()


@pytest.mark.parametrize("which", ["register-row", "register-row-local"])
def test_item16_a_window_name_read_that_fails_refuses(box, which):
    box.windows({"@1": OTHER})
    box.wrap_helper(f"  {which}:{OTHER}) exit 1 ;;")
    before = box.commits()
    result = box.start("--no-launch")
    assert result.returncode == 1, result.stderr
    assert which in result.stderr
    assert "rename-window" not in box.tmux_calls()
    nothing_done(box, before, result)


@pytest.mark.parametrize("name", ["zsh", "my notes", LANE.upper()])
def test_item16_a_generic_or_unregistered_window_name_is_reused(box, name):
    box.windows({"@1": name})
    result = box.start("--no-launch")
    assert result.returncode == 0, result.stderr
    assert box.windows() == {"@1": LANE}
