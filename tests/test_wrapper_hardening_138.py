# SPDX-License-Identifier: Apache-2.0
"""The three wrapper fail-opens of opensoft/openRepoTools#138 (items 6, 13, 15).

Each is a read the wrapper could not make, taken for an answer:

  * item 13, `lane` (`go_live`): the window-name collision check asked only the
    PUBLISHED register, so a lane whose row is committed here and not yet pushed
    could have its window renamed out from under it;
  * item 15, `lanes` (the empty listing's hidden-row probe): `grep -q .` under
    `pipefail` ends its producer with SIGPIPE on a large listing, and the
    pipeline's 141 read as "no hidden row";
  * item 6, `lane-end --retire-dormant`: no capture file for the listing's
    stderr left the "session records could not be read" sentence unread, and
    the sweep went on.

Older gaps beside those lines are closed with them: `lanes` claimed none was
recorded when the hidden-row read itself FAILED, and `lane-end --retire-dormant`
left its stderr capture file behind when the note could not be relayed, resumed
after a signal that had removed it, and took an unreadable capture for an empty
one.

The register helper, tmux and mktemp are fakes on a controlled PATH, as in
`test_guard_launch_mode.py`; nothing here touches a real register or a real
tmux server.
"""

from __future__ import annotations

import os
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None, reason="the wrappers are bash commands")]

UUID = "aaaa0001-1111-4000-8000-aaaa00019999"
TAB = "\t"


def _script(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class Box:
    """A private HOME, a fake-first PATH and a clean environment."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.tmpdir = tmp_path / "tmp"
        self.tmpdir.mkdir()
        self.log = tmp_path / "calls.log"
        self.log.write_text("")
        self.env = {name: value for name, value in os.environ.items()
                    if not name.startswith(("LANES_", "LANE_", "CLAUDE_", "TMUX", "FAKE_"))}
        self.env.update(HOME=str(self.home), TMPDIR=str(self.tmpdir),
                        AGENT_PROTOCOL_ROOT=str(self.home / ".agents"),
                        FAKE_LOG=str(self.log),
                        PATH=str(self.bin) + os.pathsep + self.env.get("PATH", ""))

    def edit(self, body: str) -> Path:
        """The fake `lanes-edit.sh`, named to the wrapper by `$LANES_EDIT`."""
        path = _script(self.root / "lanes-edit-fake.sh", body)
        self.env["LANES_EDIT"] = str(path)
        return path

    def calls(self) -> str:
        return self.log.read_text()

    def run(self, command: str, *args: str, **env: str) -> subprocess.CompletedProcess:
        child_env = dict(self.env)
        child_env.update(env)
        return subprocess.run(["bash", str(REPO / command), *args], env=child_env,
                              stdin=subprocess.DEVNULL, text=True, capture_output=True,
                              timeout=60, check=False)


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


# --- item 13: `lane`, go_live's window-name collision check -------------------

#: A tmux with one window, `@31` of `picksess`, whose current name is the file
#: `$FAKE_NAME_FILE`, and which logs every call. Every act succeeds.
FAKE_TMUX = r'''
printf '%s\n' "$*" >> "$FAKE_LOG"
case "${1-}" in
  display-message)
    shift; t=""; f=""
    while [ $# -gt 0 ]; do
      case "$1" in -p) shift ;; -t) t="${2-}"; shift 2 ;; *) f="$1"; shift ;; esac
    done
    case "$f" in
      '#{session_name}') [ "${t##*:}" = "@31" ] && printf 'picksess\n' || exit 1 ;;
      '#{window_name}') cat "$FAKE_NAME_FILE" ;;
      *) printf '\n' ;;
    esac ;;
  list-windows) printf '@31\t%s\n' "$(cat "$FAKE_NAME_FILE")" ;;
  rename-window) for last; do :; done; printf '%s\n' "$last" > "$FAKE_NAME_FILE" ;;
esac
exit 0
'''

#: The register helper `lane <name>` reads a LIVE lane through. `thislane-1` is
#: live in `@31`, and both of its register copies end in the live transcript.
#: `otherlane-9` is the lane-shaped name the window carries now: its PUBLISHED
#: row answers `$FAKE_PUB_RC` and its LOCAL row `$FAKE_LOCAL_RC` (0 prints a
#: row, 8 says there is none, anything else is a read that failed).
FAKE_LANE_EDIT = r'''
sub="${1-}"; shift || :
tab="$(printf '\t')"
row_for() { printf '| %s | %s |\n' "$1" "$FAKE_UUID"; }
other() {   # <rc> — what a register read about otherlane-9 answers
  case "$1" in 0) row_for otherlane-9 ;; esac
  return "$1"
}
case "$sub" in
  workstation) printf 'Eagle\tseam\n' ;;
  canon-lane) printf '%s\n' "$1" ;;
  lanes)
    printf '%s\n' "thislane-1${tab}LIVE${tab}Eagle${tab}team${tab}picksess:@31.%31${tab}${FAKE_UUID}${tab}/work${tab}none${tab}5m${tab}tmux attach${tab}owner/repo${tab}0${tab}here${tab}none${tab}2026-10-01${tab}none${tab}none" ;;
  lane-groups) while IFS= read -r row; do [ -n "$row" ] && printf 'live\t%s\n' "$row"; done; exit 0 ;;
  register-row)
    printf 'register-row %s\n' "$1" >> "$FAKE_LOG"
    case "$1" in thislane-1) row_for thislane-1 ;; otherlane-9) other "${FAKE_PUB_RC:-8}" ;; *) exit 8 ;; esac ;;
  register-row-local)
    printf 'register-row-local %s\n' "$1" >> "$FAKE_LOG"
    case "$1" in thislane-1) row_for thislane-1 ;; otherlane-9) other "${FAKE_LOCAL_RC:-8}" ;; *) exit 8 ;; esac ;;
  window-session) printf '%s\037%s\037%s\037%s\037%s\n' "$FAKE_UUID" "$1.%31" thislane-1 4242 team ;;
  *) printf 'fake lanes-edit: unexpected subcommand %s\n' "$sub" >&2; exit 99 ;;
esac
'''


def live_box(box: Box, window_name: str = "otherlane-9", pub: int = 8, local: int = 8):
    name_file = box.root / "window-name"
    name_file.write_text(window_name + "\n")
    _script(box.bin / "tmux", FAKE_TMUX)
    box.edit(FAKE_LANE_EDIT)
    box.env.update(FAKE_NAME_FILE=str(name_file), FAKE_UUID=UUID,
                   FAKE_PUB_RC=str(pub), FAKE_LOCAL_RC=str(local))
    return name_file


def test_live_attach_renames_a_window_no_register_row_names(box):
    name_file = live_box(box)
    result = box.run("lane", "thislane-1")
    assert result.returncode == 0, result.stderr
    assert "rename-window -t picksess:@31 thislane-1" in box.calls()
    assert "attach -t picksess:@31" in box.calls()
    assert name_file.read_text().strip() == "thislane-1"
    # Both copies of the register were asked about the old name.
    assert "register-row otherlane-9" in box.calls()
    assert "register-row-local otherlane-9" in box.calls()


def test_live_attach_refuses_a_window_named_for_a_row_not_yet_pushed(box):
    name_file = live_box(box, pub=8, local=0)
    result = box.run("lane", "thislane-1")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "otherlane-9, which has its own lane row" in result.stderr
    assert "nothing was renamed or attached" in result.stderr
    assert "rename-window" not in box.calls()
    assert "attach" not in box.calls()
    assert name_file.read_text().strip() == "otherlane-9"


@pytest.mark.parametrize("local", [1, 2])
def test_live_attach_fails_closed_when_the_local_row_cannot_be_read(box, local):
    name_file = live_box(box, pub=8, local=local)
    result = box.run("lane", "thislane-1")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "could not be read" in result.stderr and f"(exit {local})" in result.stderr
    assert "rename-window" not in box.calls()
    assert "attach" not in box.calls()
    assert name_file.read_text().strip() == "otherlane-9"


def test_live_attach_still_refuses_a_window_named_for_a_published_row(box):
    live_box(box, pub=0, local=8)
    result = box.run("lane", "thislane-1")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "otherlane-9, which has its own lane row" in result.stderr
    assert "rename-window" not in box.calls()


# --- item 15: `lanes`, the empty listing's hidden-row probe ------------------

#: `lanes` is empty (exit 8, no rows) and `lanes --closed` is `$FAKE_ROWS` rows
#: of CLOSED lanes, written one printf at a time so that a reader which stops
#: at the first line leaves the producer writing into a closed pipe, then exits
#: `$FAKE_CLOSED_RC` where that is set (a read that FAILED, rows or no rows).
FAKE_LANES_EDIT = r'''
sub="${1-}"; shift || :
case "$sub" in
  workstation) printf 'Eagle\tseam\n' ;;
  lanes)
    case " $* " in
      *" --closed "*)
        i=0
        while [ "$i" -lt "${FAKE_ROWS:-0}" ]; do
          printf 'repoH-%s\tENDED\tEagle\tteam\tnone\t%s\t/work\tnone\t1d\tnone\towner/repoH\t0\there\tclosed\t2026-09-01\tnone\tnone\n' "$i" "$FAKE_UUID"
          i=$((i + 1))
        done
        [ -z "${FAKE_CLOSED_RC:-}" ] || exit "$FAKE_CLOSED_RC"
        [ "${FAKE_ROWS:-0}" -gt 0 ] || exit 8 ;;
      *) exit 8 ;;
    esac ;;
  next-free) cat > /dev/null; printf '1\n' ;;
  *) printf 'fake lanes-edit: unexpected subcommand %s\n' "$sub" >&2; exit 99 ;;
esac
'''


def listing(box: Box, rows: int, closed_rc: int | None = None):
    box.edit(FAKE_LANES_EDIT)
    extra = {} if closed_rc is None else {"FAKE_CLOSED_RC": str(closed_rc)}
    return box.run("lanes", "--prefix", "repoH", FAKE_ROWS=str(rows), FAKE_UUID=UUID, **extra)


@pytest.mark.parametrize("rows", [1, 40000])
def test_empty_listing_says_closed_rows_are_hidden_however_many_there_are(box, rows):
    # 40000 rows of ~150 bytes is far past a pipe's buffer: the producer is
    # still writing when a `grep -q` would have gone, and it would take SIGPIPE.
    result = listing(box, rows)
    assert result.returncode == 8, (result.stdout, result.stderr)
    assert "is not the same as none being recorded" in result.stdout
    assert "see them:" in result.stdout
    assert "no lane of repoH is recorded" not in result.stdout


def test_empty_listing_of_an_empty_repository_still_says_none_is_recorded(box):
    result = listing(box, 0)
    assert result.returncode == 8, (result.stdout, result.stderr)
    assert "no lane of repoH is recorded." in result.stdout
    assert "is not the same as none being recorded" not in result.stdout


@pytest.mark.parametrize("rows", [0, 3])
@pytest.mark.parametrize("closed_rc", [1, 2])
def test_empty_listing_claims_nothing_when_the_hidden_row_read_fails(box, rows, closed_rc):
    # A read that FAILED, with or without rows, is not "none is recorded".
    result = listing(box, rows, closed_rc=closed_rc)
    assert result.returncode == 8, (result.stdout, result.stderr)
    assert "no lane of repoH is recorded" not in result.stdout
    assert "could not be read" in result.stdout
    assert f"exited {closed_rc}" in result.stdout


def test_empty_listing_treats_rows_printed_before_an_exit_8_as_hidden(box):
    # The real helper never does this; a listing that says "none is recorded"
    # over rows it was just handed would be saying something it can see is false.
    result = listing(box, 3, closed_rc=8)
    assert result.returncode == 8, (result.stdout, result.stderr)
    assert "is not the same as none being recorded" in result.stdout
    assert "no lane of repoH is recorded" not in result.stdout


# --- item 6: `lane-end --retire-dormant`, the stderr capture -----------------

#: The sweep's read: one DORMANT row (class, the fourteenth column), and the
#: sentence `lanes_rows` says on stderr when it could not read this
#: workstation's session records, when `$FAKE_UNREAD` is 1. Where `$FAKE_READY`
#: names a file the read touches it once its notes are written and then takes
#: two seconds, so a test can signal the sweep mid-read. `retire-rows` is the
#: sweep's one write and only logs that it was called.
FAKE_SWEEP_EDIT = r'''
sub="${1-}"; shift || :
case "$sub" in
  lanes)
    [ "${FAKE_UNREAD:-0}" != 1 ] || printf "this workstation's session records could not be read\n" >&2
    [ -z "${FAKE_NOTE:-}" ] || printf '%s\n' "$FAKE_NOTE" >&2
    [ -z "${FAKE_READY:-}" ] || { : > "$FAKE_READY"; sleep 2; }
    printf 'repoD-1\tNO LOG\tEagle\tnone\tnone\tnone\tnone\tnone\t9d\tnone\tnone\t0\there\tdormant\t2026-09-02\told cell\tnone\n' ;;
  retire-rows) printf 'retire-rows %s\n' "$*" >> "$FAKE_LOG" ;;
  *) printf 'fake lanes-edit: unexpected subcommand %s\n' "$sub" >&2; exit 99 ;;
esac
'''


def sweep_box(box: Box, mktemp_works: bool = True, unread: bool = False):
    register = box.root / "LANES.md"
    register.write_text("# register\n")
    box.edit(FAKE_SWEEP_EDIT)
    box.env.update(LANES_FILE=str(register), LANES_REPO=str(box.root),
                   LANES_LANE="repoW-1", FAKE_UNREAD="1" if unread else "0")
    if not mktemp_works:
        # The case under test is `mktemp` itself failing — a `$TMPDIR` that is
        # full or read-only — while the shell's own temp files still work.
        _script(box.bin / "mktemp", "exit 1\n")


@pytest.mark.parametrize("extra", [(), ("--yes",)])
def test_sweep_refuses_when_the_stderr_capture_cannot_be_made(box, extra):
    sweep_box(box, mktemp_works=False)
    result = box.run("lane-end", "--retire-dormant", "repoD", *extra)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "no temporary file could be made" in result.stderr
    assert "Nothing was written" in result.stderr
    assert "DRY RUN" not in result.stdout
    assert "retire-rows" not in box.calls()


@pytest.mark.parametrize("extra", [(), ("--yes",)])
def test_sweep_refuses_on_unread_session_records(box, extra):
    sweep_box(box, unread=True)
    result = box.run("lane-end", "--retire-dormant", "repoD", *extra)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "session records could not be read" in result.stderr
    assert "retire-rows" not in box.calls()


def test_sweep_dry_run_and_act_still_work_with_a_capture_file(box):
    sweep_box(box)
    dry = box.run("lane-end", "--retire-dormant", "repoD")
    assert dry.returncode == 0, (dry.stdout, dry.stderr)
    assert "DRY RUN" in dry.stdout and "repoD-1" in dry.stdout
    assert "retire-rows" not in box.calls()
    act = box.run("lane-end", "--retire-dormant", "repoD", "--yes")
    assert act.returncode == 0, (act.stdout, act.stderr)
    assert "retire-rows repoD-1 --writer repoW-1" in box.calls()


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="needs /dev/full to fail a write")
def test_sweep_leaves_no_capture_file_when_its_note_cannot_be_relayed(box):
    # The read's stderr is relayed to the person's own; where that write fails
    # the script exits under `set -e` before it reaches its `rm`.
    sweep_box(box)
    box.env["FAKE_NOTE"] = "a note to relay"
    with open("/dev/full", "w") as full:
        result = subprocess.run(["bash", str(REPO / "lane-end"), "--retire-dormant", "repoD"],
                                env=box.env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=full, text=True, timeout=60, check=False)
    assert result.returncode != 0, result.stdout
    assert "DRY RUN" not in result.stdout
    assert list(box.tmpdir.glob("lane-end-sweep.*")) == []


def signalled_sweep(box: Box, sig: signal.Signals) -> subprocess.Popen:
    """`lane-end --retire-dormant repoD --yes`, sent `sig` ALONE (not its process
    group) once `$FAKE_READY` appears, which the fake read or the slow `mktemp`
    shim touches, and reaped. The caller has set `FAKE_READY`."""
    if sig == signal.SIGINT and signal.getsignal(signal.SIGINT) is signal.SIG_IGN:
        pytest.skip("SIGINT is ignored at entry, so no script can trap it")
    ready = Path(box.env["FAKE_READY"])
    proc = subprocess.Popen(["bash", str(REPO / "lane-end"), "--retire-dormant", "repoD", "--yes"],
                            env=box.env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 30
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "the sweep never reached the read"
        proc.send_signal(sig)
        proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    return proc


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_sweep_does_not_resume_after_a_signal_during_the_read(box, sig):
    # A signal that reaches the lane-end shell ALONE (not its process group)
    # while the read runs. `cleanup` used to be the whole trap, so the script
    # resumed after it: with the capture file gone the unread-records refusal
    # read an empty note, and `--yes` went on to write.
    sweep_box(box, unread=True)
    box.env["FAKE_READY"] = str(box.root / "ready")
    proc = signalled_sweep(box, sig)
    assert proc.returncode == 128 + sig, proc.returncode
    assert "retire-rows" not in box.calls()
    assert list(box.tmpdir.glob("lane-end-sweep.*")) == []


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_sweep_leaves_no_capture_file_when_a_signal_lands_as_it_is_made(box, sig):
    # The window between `mktemp` creating the file and `cleanup` knowing its
    # name: a `mktemp` that takes a moment after it has made the file.
    sweep_box(box)
    box.env["FAKE_READY"] = str(box.root / "ready")
    _script(box.bin / "mktemp",
            f'f="$({shutil.which("mktemp")} "$@")" || exit $?\n'
            ': > "$FAKE_READY"\nsleep 2\nprintf \'%s\\n\' "$f"\n')
    proc = signalled_sweep(box, sig)
    assert proc.returncode == 128 + sig, proc.returncode
    assert "retire-rows" not in box.calls()
    assert list(box.tmpdir.glob("lane-end-sweep.*")) == []


def test_sweep_refuses_when_the_capture_cannot_be_read_back(box):
    # `cat` fails on the capture file, which `|| printf ''` used to turn into
    # an empty note, and an empty note is the one that never refuses.
    sweep_box(box, unread=True)
    _script(box.bin / "cat", f'case "$*" in *lane-end-sweep.*) exit 1 ;; esac\nexec {shutil.which("cat")} "$@"\n')
    result = box.run("lane-end", "--retire-dormant", "repoD", "--yes")
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "could not be read back" in result.stderr
    assert "Nothing was written" in result.stderr
    assert "retire-rows" not in box.calls()
    assert list(box.tmpdir.glob("lane-end-sweep.*")) == []
