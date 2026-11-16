# SPDX-License-Identifier: Apache-2.0
"""Feature 007's AT-F13 (opensoft/openRepoTools#165, L2-W5; lane 2's T253):
`LANDING EXPIRED`'s verb, `append-line --landing-expired`, and a take with no
UTC.

THE RULING (F13, Brett's "Adopt, on my word (Recommended)", #165 6721583757;
U3 and U7, lane 3's ruling, #165 6722541787; lane 4's section, "`LANDING
EXPIRED`'s verb"): on primary a `LANDING EXPIRED` line is written only by
`append-line --landing-expired <holder> --pr <n> --repo <repo>`, with Brett's
word as `--word`, `--word-where` and `--word-utc`. The form copies the holder,
the PR, the repository's token and the UTC from the holder's open `LANDING` at
`n`, byte for byte, the newest post where there are several; it refuses with
2, sending nothing, without the word, off primary, and where that `LANDING` is
not open or is 30 minutes old or less by the snapshot's clock. On primary
`append-line` refuses, before the lock, the kind typed by hand and a take whose
UTC it cannot read (U3). F13's check in the commit decides what the line
releases; its LR005 exits 2 with the server's message and its DETAIL token,
and a caller that branches reads the token, never the message (U7). On primary
`who --landing` no longer lists a released `LANDING`, through `RULE6_PRIMARY`,
`rule6_primary_on` and `RULE6_EXPIRED_AWK`; off primary `RULE6_AWK` is
byte-identical to today's.

THE CASES: (a) to (g) and (k) to (m) are FP; (i) and (j) are RE, on T205's
`pg_cluster`, skipped without PostgreSQL 16 by its banner. Case (h), with
its rollback, is T279's, RE, at the module's end. The fifteenth test, new
since v3f, is T112's AT-F13
case (R-F10-34): `register commit` expires an imported stale `LANDING` by
Rule 6's key, the shipped table then the per-wip one (RE; at its section).

THE FP BENCH (`Bench`): `lanes-edit.sh` copied beside a `lanes-index` that is
T207's contract stub (`contract_stub`, CLI4.5 section 6's copy rule, with
`repos.tsv` and `lane-start` beside it), behind a small wrapper that sets the
clock `register snapshot` prints to the test's `CLOCK`, far from `date` (D13:
every age is the snapshot's time less the `LANDING`'s UTC). The stub's
register at `n` holds the case's `lanes/LANES.md`, as the files-mode workspace
under it does (test 1's sync form, `test_sql_register_render.py`'s
`workspace`), and its `register read` is the fake prefetch. T203's register
fake `psql` is first on `PATH`, and the configuration names a Unix socket
directory (the fake-`psql` host rule, L1v4.5:525; lane 1, #165 6741670709 item
9). "Nothing sent" is read here as: no `register commit` reached the stub and
no `psql` call was made; on primary T424's and T425's refusals run in the
attempt's child, after the parent's snapshot and before its seam, so a
snapshot call may precede a refusal (B11 tasks:1087, :1152, :1271). Beside
the checkout, each lane the module writes for has its own register checkout,
`<W>-lanes/<lane>`, a clone of the same origin (`WRITE_LANES`; lane 3's
(119), #165 6813027223), as every estate at primary does.

TWO READS OF `who --landing` (lane 4's RC-W49, #165 6871131058): off primary
it prints each `LANDING`'s age by the host's `date`, not by `CLOCK`, so (f)
and (l), which compare two of its reads, compare them through `aged_out`:
each age is masked, once it is shown to be its UTC's age by the host's clock
during its own read. Every other byte is still compared.

WHAT THEY FAIL UNTIL. At this base `lanes-edit.sh` never asks `lanes-index`
its mode and writes the files whatever it would say, and its `append-line`
takes `--landing-expired` as the line's text. So every FP case is red by its
own assertion, and fails until lane 4's T424 (L4-B10's refusals) and T425
(L4-B10, the form, `RULE6_PRIMARY` and `RULE6_EXPIRED_AWK`), with T415's
attempt loop (L4-B3) and lane 5's T504 (the mode door, `reg_open`) under them;
(g) fails only until lane 1's T118 (L1-A16), and (i) and (j) until lane 1's
T107, T111 and T112 (L1-A6, L1-A9, L1-A10) and lane 2's T227 and T228, with
T425 for the form and the awk.
"""

from __future__ import annotations

import atexit
import calendar
import hashlib
import importlib.machinery
import importlib.util
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest

from conftest import WINDOWS_SKIP
from sql_register_helpers import (ARGV_LOG, LANES_INDEX, PSQL_SHIM, PSQL_SHIM_CONTROL,
                                  REGISTER_FAKE_PSQL, REPO, contract_stub, flipped_copy,
                                  stub_outcome)

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280; `tests/sql_register_gate.py` reads it, and
#: T281 removes it in the last set): the tasks each id of this module waits
#: for, by T253's and T279's Orders (tasks.md at 204145ae), keyed by function.
#: Lane 2's plan GP-24 wrote it (task sets 12b's rule 11); C1's fourth text and
#: (b, U3) also wait for T415 and T504, as tasks:2408 names them.
SQL_REGISTER_GATE_TABLE = {
    "test_a_landed_between_the_forms_snapshot_and_commit_leaves_the_retry_nothing_to_release": ("T107", "T108", "T111", "T112", "T115", "T118", "T227", "T228", "T415", "T424", "T425"),  # T253; tasks:2408
    "test_a_landing_expired_on_primary_frees_main_and_who_landing_until_a_rollback_to_files": ("T121", "T304", "T326", "T424", "T425"),  # T279; tasks:2564
    "test_in_files_mode_the_landing_expired_form_exits_2_and_changes_nothing": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_off_primary_rule6_awk_is_the_pin_and_the_flag_cannot_be_inherited": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_on_primary_a_landing_take_whose_lane_cannot_be_read_is_refused_before_the_lock_and_written_off_primary": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_on_primary_a_take_with_no_readable_utc_is_refused_before_the_lock_and_written_off_primary": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_on_primary_the_landing_expired_kind_typed_by_hand_is_refused_naming_the_form": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_parse_register_line_reads_the_landing_expired_fields_before_the_word_clause": ("T107", "T108", "T118", "T424", "T425"),  # T253; tasks:2408
    "test_register_commit_expires_an_imported_stale_landing_by_the_shipped_then_per_wip_repo_key": ("T105", "T107", "T111", "T112", "T227", "T228"),  # T253; tasks:2408
    "test_rule6_primary_on_is_called_only_where_lane_4_places_it_and_who_landing_stays_pinned": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_rule6_with_the_expired_branch_agrees_with_main_slots_on_imported_history": ("T107", "T108", "T111", "T112", "T118", "T227", "T228", "T424", "T425"),  # T253; tasks:2408
    "test_the_landing_expired_form_composes_its_line_from_the_open_landing": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_the_landing_expired_form_prints_its_seq_once_and_an_lr005_with_its_detail_token": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_the_landing_expired_form_refuses_with_2_before_the_lock_without_the_word": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_the_landing_expired_form_sends_nothing_where_no_landing_is_stale_at_the_snapshot": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_the_writer_reads_lr005s_reason_from_its_detail_token_never_its_message": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
    "test_who_landing_on_primary_drops_only_the_released_landing": ("T107", "T108", "T118", "T415", "T424", "T425", "T504"),  # T253; tasks:2408
}

LANES_EDIT = REPO / "lanes-edit.sh"

#: The register's punctuation, by code point, so no raw character enters this
#: file: the em dash, the middle dot of a state cell, the arrow of a `LANDED`.
EM, DOT, ARROW = chr(0x2014), chr(0x00B7), chr(0x2192)

#: The workstation, and the lanes: the writer who releases, the holder whose
#: `LANDING` goes stale, a third lane, and the holder's former name.
WS = "Eagle"
WRITER, HOLDER, OTHER, OLD_NAME = "repoA-2", "repoB-1", "repoC-1", "repoOld-1"
SID_W = "aaaaaaaa-0253-4000-8000-00000000a253"
SID_H = "bbbbbbbb-0253-4000-8000-00000000b253"
SID_O = "cccccccc-0253-4000-8000-00000000c253"
SESSIONS = {WRITER: SID_W, HOLDER: SID_H, OTHER: SID_O}
TIP = "0123456789abcdef0123456789abcdef01234567"

#: The repository: `lanes/repos.tsv` maps `r9` to `opensoft/r9` (the test
#: plan's AT-F13 fixture), and `r8` to another key.
KEY, ALIAS, OTHER_KEY = "opensoft/r9", "r9", "opensoft/r8"
PR, OTHER_PR = 9, 8
REPOS_TSV = f"# alias\towner/repo\n{ALIAS}\t{KEY}\nr8\t{OTHER_KEY}\n"

#: THE SNAPSHOT'S CLOCK (D13), far from `date`: 2026-06-01T12:00:00Z. Every
#: `LANDING`'s UTC is set from it, so a form that dated by `date` would see
#: each one months old.
CLOCK = calendar.timegm((2026, 6, 1, 12, 0, 0, 0, 0, 0))

#: Brett's word, as the form's three arguments carry it.
WORD = "Release the stale LANDING (Recommended)"
WHERE = "lane openRepoTools-2's session"
WORD_UTC = "2026-06-01T11:58:00Z"

#: RULE 6'S PROGRAM AS IT IS PINNED, `RULE6_AWK`'s text at code `a2073eae`
#: (`lanes-edit.sh:6959`), between its quotes: 1874 bytes.
RULE6_AWK_PIN = "618e9235c3a838ea0fe67134097063377c21f6acf57eb1f240a5cda1ad00007e"
#: `who_landing`'s pinned line (`lanes-edit.sh:7057` at `a2073eae`).
WHO_LANDING_LINE = ('  wd_rows="$(register_text | LANES_RULE6_ALIASES="$wd_aliases" '
                    'awk "$RULE6_AWK")"')
#: What the files-mode refusal says (AT-F13 (f)), word by word.
FILES_MODE_WORDS = ("release of a stale", "exists only on", "mode=primary", "nothing was written")
STALE_MARK = "STALE (Rule 6: >30 min)"
#: A `who --landing` line's age, `<UTC> (<h>h <mm>m ago)` (`age_of`), the one
#: part of its output that the host's clock decides and the register does not.
#: Off primary `now_epoch` is `date -u +%s`, so two reads that straddle a
#: minute differ there alone (`lanes-edit.sh`'s `now_epoch`, `age_of` and
#: `who_landing`, `:7443-7446`, `:12769-12775` and `:16233` at line R's
#: merge104 `142afd90`; lane 4's RC-W49, #165 6871131058: `3976h 04m ago`
#: against `3976h 05m ago`).
WHO_AGE_RE = re.compile(r"(?P<utc>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2})?Z)"
                        r" \((?P<hours>[0-9]+)h (?P<minutes>[0-9]{2})m ago\)")


# ------------------------------------------------------------------ the lines
def utc_of(epoch: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def ago(minutes: float, clock: int = CLOCK) -> str:
    """The UTC `minutes` before the snapshot's clock."""
    return utc_of(clock - int(round(minutes * 60)))


def _epoch_of(utc: str):
    """`utc` as epoch seconds, or None where the line carries no UTC."""
    return calendar.timegm(time.strptime(utc, "%Y-%m-%dT%H:%M:%SZ")) if utc else None


def aged_out(stdout: str, before: int, after: int) -> str:
    """`who --landing`'s `stdout` with each age masked, `<UTC> (<age> ago)`,
    once it is shown to be its line's UTC's age by the host's clock at some
    whole second from `before` to `after`, the clock as `date -u +%s` reads it
    just before the read began and just after it ended (`age_of`'s whole
    minutes, 0 for a UTC ahead of the clock). So two reads compared through it
    still differ at every other byte that changed, the UTC and the STALE mark
    among them, and an age that is not the host clock's, such as one by the
    snapshot's `CLOCK`, fails here (RC-W49's SHOULD 1)."""
    def masked(m) -> str:
        utc = m["utc"]
        epoch = calendar.timegm(time.strptime(
            utc, "%Y-%m-%dT%H:%M:%SZ" if utc.count(":") == 2 else "%Y-%m-%dT%H:%MZ"))
        shown = int(m["hours"]) * 60 + int(m["minutes"])
        low, high = max(0, before - epoch) // 60, max(0, after - epoch) // 60
        assert int(m["minutes"]) < 60 and low <= shown <= high, (
            f"who --landing's age {m.group(0)!r} is not its UTC's age by the host's "
            f"clock during the read, {low} to {high} min")
        return f"{utc} (<age> ago)"
    return WHO_AGE_RE.sub(masked, stdout)


def landing(lane: str = HOLDER, minutes: float = 31, pr: int = PR, repo: str = KEY,
            session: str = None) -> str:
    sid = session or SESSIONS.get(lane, SID_H)
    return f"LANDING {EM} lane {lane}, session {sid}@{WS}, {ago(minutes)}, PR #{pr} into {repo} main"


def landed(lane: str = HOLDER, minutes: float = 40, pr: int = PR, repo: str = KEY) -> str:
    sid = SESSIONS.get(lane, SID_H)
    return (f"LANDED {EM} lane {lane}, session {sid}@{WS}, {ago(minutes)}, PR #{pr} into {repo} "
            f"main {ARROW} abc1234")


def expired(writer: str = OTHER, minutes: float = 5, holder: str = HOLDER, pr: int = PR,
            repo: str = KEY, landing_utc: str = None, word: str = WORD, where: str = WHERE,
            word_utc: str = WORD_UTC, clause: bool = True) -> str:
    """A `LANDING EXPIRED` line in the form's own shape (Y:5109;
    `lanes-edit.sh:3375` at `c8acf67c`), as the form composes it (case (a)),
    a re-import after a rollback holds it, or a line typed by hand in files
    mode copies it: `lane <writer>` first, the session, its UTC `minutes`
    before the snapshot's clock, `for lane <holder>:`, the PR, the
    repository, `its LANDING of <landing UTC>` (`landing_utc`, 45 minutes
    before the clock where it is not given), the whole minutes past Rule 6's
    30 (0 where the two are 30 minutes apart or less, which only a line typed
    by hand can be), and the word clause last: where and when Brett gave his
    word, then his quote. `clause=False` leaves the word clause off."""
    sid = SESSIONS.get(writer, SID_O)
    landing_utc = landing_utc or ago(45)
    apart = _epoch_of(ago(minutes)) - _epoch_of(landing_utc)
    text = (f"LANDING EXPIRED {EM} lane {writer}, session {sid}@{WS}, {ago(minutes)}, "
            f"for lane {holder}: PR #{pr} into {repo} main, its LANDING of {landing_utc}, "
            f"{max(0, (apart - 30 * 60) // 60)} min past Rule 6's 30")
    if clause:
        text += f"; on Brett's word ({where}, {word_utc}): \"{word}\""
    return text


def _row(lane: str, sid: str) -> str:
    return (f"| `{lane}` | harness `{sid}` | {WS} / test / brett | 2026-05-01T00:00Z | none "
            f"| handoffs/{lane}.md | LIVE {DOT} 2026-05-01T00:00:00Z {DOT} working |")


def register_files(lines=(), repos: str = REPOS_TSV) -> dict:
    """The case's checkout and register: three lanes' rows, `lines` after the
    table, the holder's former name in `aliases.tsv`, a log per lane, and
    `lanes/repos.tsv` (outside the render set, from the checkout)."""
    lanes = "\n".join([
        f"# LANES.md {EM} AT-F13's register (T253)", "",
        "| lane | session id | workstation / env / user | started (UTC) | objects owned "
        "| handoff path | state |",
        "|---|---|---|---|---|---|---|",
        *(_row(lane, sid) for lane, sid in SESSIONS.items()), "", *lines, ""])
    files = {"lanes/LANES.md": lanes,
             "lanes/aliases.tsv": f"# old\tnew\tutc\n{OLD_NAME}\t{HOLDER}\t2026-05-01T00:00:00Z\n",
             "lanes/log/README.md": "# the object logs\n",
             "lanes/repos.tsv": repos}
    for lane in SESSIONS:
        files[f"lanes/log/{lane}.md"] = (f"# lane {lane} {EM} object log "
                                         f"(lane-collision-protocol Amendment 7)\n")
    return files


RENDER_SET = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|archive/[^/]+\.md"
                        r"|log/(?!README\.md$)[^/]+\.md)$")


# ------------------------------------------------------------------ the estate
def git(cwd: Path, *args: str, env: dict = None) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          env=env, check=False)
    assert proc.returncode == 0, f"git {' '.join(args)} in {cwd}: {proc.stderr}{proc.stdout}"
    return proc.stdout


#: `_masked_path`'s mirrors, by each directory's real path (None where the
#: directory holds no masked name), and the one temporary root they share.
_PATH_MIRRORS: dict = {}
_PATH_MIRROR_ROOT: list = []


def _masked_path() -> str:
    """The caller's PATH with every directory kept in its place, and each one
    that holds a `psql`, a `lanes-index` or a name that starts `pg_` swapped
    for a private mirror of it: a directory of links, one to each of its
    entries by its absolute path, those names left out. An installed
    indexer, a real `psql` or one of the `pg_` client wrappers shipped beside
    it is never what a case runs, but the tools beside them are: on a GitHub
    runner `postgresql-16`'s client puts `psql` in `/usr/bin` with `git` and
    `bash` (and `/bin` is a link to it), so dropping the directory dropped
    `git` and `bash` too (lane 1's census, #165 6807454856). A directory that
    holds none of those names passes through unchanged. Each mirror is made
    once per process, under one `mkdtemp` that an `atexit` handler removes."""
    parts = []
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if not part:
            continue
        real = os.path.realpath(part)
        if real not in _PATH_MIRRORS:
            try:
                names = os.listdir(real)
            except OSError:
                names = []
            masked = {name for name in names
                      if name in ("psql", "lanes-index") or name.startswith("pg_")}
            mirror = None
            if masked:
                if not _PATH_MIRROR_ROOT:
                    _PATH_MIRROR_ROOT.append(tempfile.mkdtemp(prefix="l2-pathmask-"))
                    atexit.register(shutil.rmtree, _PATH_MIRROR_ROOT[0], ignore_errors=True)
                mirror = os.path.join(_PATH_MIRROR_ROOT[0], str(len(_PATH_MIRRORS)))
                os.mkdir(mirror)
                for name in names:
                    if name not in masked:
                        os.symlink(os.path.join(real, name), os.path.join(mirror, name))
            _PATH_MIRRORS[real] = mirror
        parts.append(_PATH_MIRRORS[real] or part)
    return os.pathsep.join(parts)


#: EACH WRITE LANE'S OWN REGISTER CHECKOUT, `<c>` (lane 3, #165 6813027223,
#: batch g Q119; T241e's `WRITE_LANES` in `test_sql_register_writes.py` is the
#: model). On primary a write reads its author, its pending hand edits and its
#: `repos.tsv` from the checkout of the lane it is made for, `<W>-lanes/<lane>`
#: (`lanes-edit.sh`'s `lane_checkout_path`, `R-merge20:lanes-edit.sh:18342`),
#: W being the real path of `workspace.yaml`'s `path:`, and refuses with 2,
#: sending nothing, where that is not there, since a clone there would be
#: D12's fetch (B15 tasks:1154; T415's `pw_checkout`). So `_workspace` makes
#: it itself, because `lane-start` makes it only under `LANES_ROUTE_WRITES=1`
#: with neither `LANES_REPO` nor `LANES_FILE` set (lane 3, #165 6841265575;
#: `dfc4ce4c:lane-start:1209-1210`). It makes it for each lane this module's
#: writes are made for (`write_lane_of`'s): `WRITER`, the `LANES_LANE` of every
#: form and take, and `HOLDER`, (a)'s `[writer-is-the-holder]`. Until T415
#: nothing reads it: no case sets `LANES_ROUTE_WRITES`, so each write goes
#: through `LANES_REPO` as before.
WRITE_LANES = (WRITER, HOLDER)


def _lane_checkouts(origin: Path, checkout: Path, env: dict, lanes=WRITE_LANES) -> list:
    """`<c>` for each of `lanes`, beside the checkout `workspace.yaml` names
    as W: `<W>-lanes/<lane>`, W being its real path, as `lane_checkout_path`
    puts it (Amendment 23 S1). Each is a clone of W's own origin, as
    `lane-checkout <lane> --create` makes one, so it is at W's commit when
    made after the case's last push from W (T241e's "after the case's
    prep")."""
    real = Path(os.path.realpath(checkout))
    made = []
    for lane in lanes:
        target = real.parent / f"{real.name}-lanes" / lane
        target.parent.mkdir(parents=True, exist_ok=True)
        git(target.parent, "clone", "-q", str(origin), str(target), env=env)
        made.append(target)
    return made


def _workspace(root: Path, fakebin: Path, files: dict, source: Path = None,
               lanes=WRITE_LANES) -> tuple:
    """A files-mode workspace on a bare origin at `files`, in test 1's sync
    form (`test_sql_register_render.py`'s `workspace`): `workspace.yaml`
    names the origin and the checkout, a fake `tmux` and `fakebin` are first
    on `PATH`, and the workstation is configured. Where `source` is given
    (T279's case (h)), the origin is a bare clone of that repository and
    `files` is not written. Each of `lanes` has its own register checkout
    beside the checkout (`_lane_checkouts`); a case that pushes from the
    checkout afterwards passes none and makes them after its push. Returns
    (the origin, the checkout, the environment)."""
    home = root / "home"
    home.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "PG", "LANES_", "TMUX", "RULE6_", "FAKE_PSQL"))}
    env.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME="T253 estate", GIT_AUTHOR_EMAIL="t253@example.invalid",
               GIT_COMMITTER_NAME="T253 estate", GIT_COMMITTER_EMAIL="t253@example.invalid",
               LC_ALL="C")
    origin, checkout = root / "origin.git", root / "checkout"
    if source is not None:
        git(root, "clone", "-q", "--bare", str(source), str(origin), env=env)
        git(root, "clone", "-q", str(origin), str(checkout), env=env)
    else:
        git(root, "init", "-q", "--bare", "-b", "main", str(origin), env=env)
        git(root, "clone", "-q", str(origin), str(checkout), env=env)
        for path, text in files.items():
            target = checkout / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
        git(checkout, "add", "-A", env=env)
        git(checkout, "commit", "-q", "-m", "C: AT-F13's register", env=env)
        git(checkout, "push", "-q", "origin", "main", env=env)
    _lane_checkouts(origin, checkout, env, lanes)
    agents = home / ".agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "workspace.yaml").write_text(f"repository: {origin}\npath: {checkout}\n",
                                           encoding="utf-8")
    fakebin.mkdir(parents=True, exist_ok=True)
    (fakebin / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (fakebin / "tmux").chmod(0o755)
    for d in ("state", "config", "tmp"):
        (root / d).mkdir(parents=True, exist_ok=True)
    env.update(AGENT_PROTOCOL_ROOT=str(agents), TMPDIR=str(root / "tmp"),
               XDG_STATE_HOME=str(root / "state"), XDG_CONFIG_HOME=str(root / "config"),
               CLAUDE_CONFIG_DIR=str(home / ".claude"), LANES_WORKSTATION=WS,
               LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none",
               LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1", LANES_REPO=str(checkout),
               PATH=str(fakebin) + os.pathsep + _masked_path())
    return origin, checkout, env


#: THE SNAPSHOT'S CLOCK, SET BY THE TEST: the contract stub's `register
#: snapshot` prints `clock=` from `time.time()`; this wrapper hands every call
#: to the stub and, on `register snapshot` alone, rewrites that one line to the
#: epoch in its clock file. `not_after=` stays the stub's, so a commit is in
#: time.
_CLOCK_WRAPPER = r'''#!/usr/bin/env python3
# AT-F13's snapshot clock (T253): the contract stub, its `clock=` set.
import os, subprocess, sys
STUB = STUB_PATH
CLOCK = CLOCK_PATH
args = sys.argv[1:]
if args[:2] != ["register", "snapshot"] or not os.path.exists(CLOCK):
    os.execv(sys.executable, [sys.executable, STUB] + args)
with open(CLOCK, encoding="utf-8") as handle:
    clock = handle.read().strip()
proc = subprocess.run([sys.executable, STUB] + args, stdout=subprocess.PIPE)
out = proc.stdout.decode("utf-8")
sys.stdout.write("\n".join("clock=" + clock if line.startswith("clock=") else line
                           for line in out.split("\n")))
sys.stdout.flush()
sys.exit(proc.returncode)
'''


class Bench:
    """One case's workstation (see the module's docstring): `mode` is what
    the mode query answers, `primary`, `files`, `index`, `unconfigured`
    (no configuration, answered `files`) or `fall` (the query fails, F8's
    fall to files mode)."""

    def __init__(self, tmp_path: Path, lines=(), mode: str = "primary", repos: str = REPOS_TSV):
        self.root = tmp_path
        self.fakebin = tmp_path / "fakebin"
        self.fakebin.mkdir(parents=True, exist_ok=True)
        (self.fakebin / "psql").write_text(REGISTER_FAKE_PSQL, encoding="utf-8")
        (self.fakebin / "psql").chmod(0o755)
        self.psql_log = self.fakebin / "psql.log"
        self.files = register_files(lines, repos)
        self.origin, self.checkout, self.env = _workspace(tmp_path / "ws", self.fakebin,
                                                          self.files)
        self.stub_dir = tmp_path / "stub"
        contract_stub(self.stub_dir, register={p: t for p, t in self.files.items()
                                               if RENDER_SET.match(p)})
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
            shutil.copy2(str(REPO / name), str(self.bin / name))
        self.lanes_edit = self.bin / "lanes-edit.sh"
        clock = tmp_path / "snapshot-clock"
        clock.write_text(f"{CLOCK}\n", encoding="utf-8")
        wrapper = self.bin / "lanes-index"
        wrapper.write_text(_CLOCK_WRAPPER.replace("STUB_PATH", repr(str(self.stub_dir / "lanes-index")))
                           .replace("CLOCK_PATH", repr(str(clock))), encoding="utf-8")
        wrapper.chmod(0o755)
        conf_dir = tmp_path / "conf"
        conf_dir.mkdir()
        sock = tmp_path / "sock"
        sock.mkdir()
        host = quote(sock.as_posix(), safe="")
        passfile = conf_dir / "pgpass"
        passfile.write_text("", encoding="utf-8")
        passfile.chmod(0o600)
        if mode != "unconfigured":
            conf = conf_dir / "lanes-index.conf"
            conf.write_text("\n".join([
                f"mode={'files' if mode == 'fall' else mode}",
                f"register_url=postgresql://lanes_w_t253@{host}:5432/lanes_t253",
                f"reader_url=postgresql://lanes_r_t253@{host}:5432/lanes_t253",
                f"register_passfile={passfile}", f"reader_passfile={passfile}", ""]),
                encoding="utf-8")
            conf.chmod(0o600)
            self.env["LANES_INDEX_CONFIG"] = str(conf)
        self.env["FAKE_PSQL_LOG"] = str(self.psql_log)
        self.env.pop("LANES_INDEX", None)
        self.mode = mode
        if mode in ("files", "index", "unconfigured"):
            said = "files" if mode == "unconfigured" else mode
            self.outcome("mode", stdout=f"{said}\n")
            self.outcome("register read", stdout=f"mode {said}\n")
        elif mode == "fall":
            for prefix in ("mode", "register read"):
                self.outcome(prefix, exit=1, stderr="lanes-index: the mode query failed (T253)\n")

    def outcome(self, prefix, **answer) -> None:
        stub_outcome(self.stub_dir, prefix, **answer)

    def run(self, argv, lane: str = WRITER, session: str = None, extra: dict = None,
            drop=()) -> subprocess.CompletedProcess:
        env = dict(self.env)
        if lane:
            env["LANES_LANE"] = lane
            env["LANES_SESSION"] = session or SESSIONS.get(lane, SID_W)
        env.update(extra or {})
        for name in drop:
            env.pop(name, None)
        return subprocess.run(["bash", str(self.lanes_edit), *[str(a) for a in argv]],
                              capture_output=True, encoding="utf-8", errors="replace", env=env,
                              timeout=120, cwd=str(self.checkout), check=False,
                              stdin=subprocess.DEVNULL)

    def who(self, extra: dict = None) -> subprocess.CompletedProcess:
        return self.run(["who", "--landing", KEY], lane=None, extra=extra)

    def who_aged(self, extra: dict = None) -> tuple:
        """`who()`, with the host's clock read just before and just after it:
        (the process, its stdout through `aged_out`). Two reads compare by that
        stdout, so a minute the clock crosses between them is no change."""
        before = int(time.time())
        proc = self.who(extra)
        return proc, aged_out(proc.stdout, before, int(time.time()))

    # -------------------------------------------------- what reached the store
    def calls(self, *words: str) -> list:
        """The stub's calls whose arguments begin with `words`."""
        log = self.stub_dir / ARGV_LOG
        if not log.exists():
            return []
        found = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]
        return [argv for argv in found if argv[:len(words)] == list(words)]

    def asked_the_mode(self) -> bool:
        return bool(self.calls("mode") or self.calls("register", "read"))

    def psql_calls(self) -> list:
        if not self.psql_log.exists():
            return []
        entries = [json.loads(line) for line in self.psql_log.read_text(encoding="utf-8")
                   .splitlines() if line]
        return [e for e in entries if e.get("kind") != "version"]

    def head(self) -> int:
        return json.loads((self.stub_dir / "lanes-index.state").read_text(encoding="utf-8"))["n"]

    def register(self, seq: int, path: str = "lanes/LANES.md") -> str:
        target = self.stub_dir / "lanes-index.register" / str(seq) / path
        return target.read_text(encoding="utf-8") if target.exists() else None

    def added_lines(self) -> list:
        """The lines `lanes/LANES.md` gained from seq 1 to the head."""
        before = self.register(1).split("\n")
        after = self.register(self.head()).split("\n")
        assert after[:len(before) - 1] == before[:-1], "lines before the end changed"
        return [line for line in after[len(before) - 1:] if line]

    def git_state(self) -> tuple:
        """The checkout's HEAD and status, `origin/main`, and origin's
        `lanes/LANES.md`."""
        return (git(self.checkout, "rev-parse", "HEAD", env=self.env),
                git(self.checkout, "status", "--porcelain=v1", "-uall", env=self.env),
                git(self.origin, "log", "--format=%H", "main", env=self.env),
                git(self.origin, "show", "main:lanes/LANES.md", env=self.env))

    def locks(self) -> list:
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")
                      if p.name in (".lanes-edit.lock", "index.lock"))


def form(holder: str = HOLDER, pr=PR, repo: str = KEY, word: str = WORD, where: str = WHERE,
         word_utc: str = WORD_UTC, omit=(), empty=()) -> list:
    """`append-line --landing-expired`'s argument list (T425's usage)."""
    argv = ["append-line", "--landing-expired", holder, "--pr", str(pr), "--repo", repo]
    for flag, value in (("--word", word), ("--word-where", where), ("--word-utc", word_utc)):
        if flag in omit:
            continue
        argv += [flag, "" if flag in empty else value]
    return argv


def assert_nothing_sent(bench: Bench, proc: subprocess.CompletedProcess, before: tuple,
                        what: str) -> None:
    """No `register commit` reached the stub, no `psql` call was made, the
    head did not move, git is as it was and no lock is left."""
    assert bench.calls("register", "commit") == [], (
        f"{what}: a `register commit` was sent: {bench.calls('register', 'commit')}")
    assert bench.psql_calls() == [], f"{what}: a psql call was made: {bench.psql_calls()}"
    assert bench.head() == 1, f"{what}: the register's head moved to {bench.head()}"
    assert bench.git_state() == before, f"{what}: git changed"
    assert bench.locks() == [], f"{what}: a lock was left: {bench.locks()}"


def lanes_index_module(source: Path = LANES_INDEX):
    """`lanes-index` loaded as a module, as T207's stub loads it for
    `register classify`, so the case reads the checkout's own classifier."""
    loader = importlib.machinery.SourceFileLoader(f"lanes_index_t253_{uuid.uuid4().hex}",
                                                  str(source))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# ============================================================ (a) compose
COMPOSE = {
    # case: (the register's lines, the form's arguments, the writer, the
    # holder's spelling the line copies, the repository token it copies, the
    # LANDING UTC it copies)
    "plain": ([landing()], form(), WRITER, HOLDER, KEY, ago(31)),
    "repo-alias-in-the-form": ([landing()], form(repo=ALIAS), WRITER, HOLDER, KEY, ago(31)),
    "repo-alias-in-the-landing": ([landing(repo=ALIAS)], form(repo=KEY), WRITER, HOLDER, ALIAS,
                                  ago(31)),
    "old-name": ([landing(lane=OLD_NAME, session=SID_H)], form(), WRITER, OLD_NAME, KEY, ago(31)),
    "other-case": ([landing(lane=HOLDER.lower(), session=SID_H)], form(), WRITER,
                   HOLDER.lower(), KEY, ago(31)),
    "writer-is-the-holder": ([landing()], form(), HOLDER, HOLDER, KEY, ago(31)),
    "newest-post": ([landing(minutes=50), landing(minutes=40)], form(), WRITER, HOLDER, KEY,
                    ago(40)),
}


@pytest.mark.parametrize("case", list(COMPOSE))
def test_the_landing_expired_form_composes_its_line_from_the_open_landing(tmp_path, case):
    """(a): on primary the form sends one `LANDING EXPIRED` line: `lane
    <writer>` first, as `canon_lane` gives `LANES_LANE`; the session; the
    snapshot's UTC (D13); `for lane <holder>`; then the PR, the repository's
    token and the `LANDING`'s UTC copied byte for byte from the holder's
    newest open `LANDING` at `n`, also where `--repo` is a `repos.tsv` alias
    or the `LANDING`'s lane is an old name or in another case; and the word
    clause last, where and when Brett gave his word, then his quote (Y:5109).
    A writer who is also the holder is accepted. One `register commit` is
    sent, and the line is the only change at `n+1`."""
    lines, argv, writer, holder, token, landing_utc = COMPOSE[case]
    bench = Bench(tmp_path, lines)
    proc = bench.run(argv, lane=writer)
    assert proc.returncode == 0, (
        f"the form exited {proc.returncode}, not 0 (L4-B10, lane 4's T425): {proc.stderr[-800:]}")
    assert len(bench.calls("register", "commit")) == 1, (
        f"{len(bench.calls('register', 'commit'))} commit calls, not one: the line was not sent "
        f"on primary (L4-B3, T415; L4-B10, T425): {bench.calls()}")
    added = bench.added_lines()
    assert len(added) == 1, f"{len(added)} lines were sent, not one: {added}"
    line = added[0]
    head = f"LANDING EXPIRED {EM} lane {writer}, session {SESSIONS[writer]}@{WS}, {utc_of(CLOCK)}"
    assert line.startswith(head), f"the line does not open with {head!r}: {line!r}"
    parts = [f"for lane {holder}", f"PR #{PR}", f"into {token} main", landing_utc]
    places = [line.find(part, len(head)) for part in parts]
    assert -1 not in places, f"the line lacks one of {parts}: {line!r}"
    word_at = line.find(WORD)
    assert word_at > max(places), f"Brett's quote is not after the copied fields: {line!r}"
    # Where and when Brett gave his word sit between the copied fields and the
    # quote, which is last (Y:5109, `lanes-edit.sh:3375`; lane 4's TRIAGE-W13c).
    where_at, when_at = line.find(WHERE, max(places)), line.find(WORD_UTC, max(places))
    assert max(places) < where_at < when_at < word_at, (
        f"the line lacks where or when Brett gave his word before his quote: {line!r}")
    assert line.endswith(f"; on Brett's word ({WHERE}, {WORD_UTC}): \"{WORD}\""), (
        f"the line does not end with the form's word clause (Y:5109): {line!r}")
    for path, text in bench.files.items():
        if RENDER_SET.match(path) and path != "lanes/LANES.md":
            assert bench.register(bench.head(), path) == text, f"{path} changed"


# ============================================================ (b) the word
WORD_REFUSALS = {
    "word-missing": (dict(argv=form(omit=("--word",))), "--word"),
    "word-empty": (dict(argv=form(empty=("--word",))), "--word"),
    "word-where-missing": (dict(argv=form(omit=("--word-where",))), "--word-where"),
    "word-where-empty": (dict(argv=form(empty=("--word-where",))), "--word-where"),
    "word-utc-missing": (dict(argv=form(omit=("--word-utc",))), "--word-utc"),
    "word-utc-empty": (dict(argv=form(empty=("--word-utc",))), "--word-utc"),
    "word-utc-not-a-utc": (dict(argv=form(word_utc="yesterday at noon")), "--word-utc"),
    # A newline or a CR in any argument is refused before any is parsed, so
    # the refusal names the break, not the flag (Y:5114; TP (b)); as
    # `[newline-in-the-holder]`.
    "newline-in-the-word": (dict(argv=form(word=WORD + "\nand more")), "newline"),
    "cr-in-the-where": (dict(argv=form(where=WHERE + "\r")), "newline"),
    "newline-in-the-holder": (dict(argv=form(holder=HOLDER + "\n")), "newline"),
    "lanes-lane-unset": (dict(argv=form(), drop=("LANES_LANE",)), "LANES_LANE"),
    "lanes-session-unset": (dict(argv=form(), drop=("LANES_SESSION",)), "LANES_SESSION"),
}


@pytest.mark.parametrize("argument", list(WORD_REFUSALS))
def test_the_landing_expired_form_refuses_with_2_before_the_lock_without_the_word(tmp_path,
                                                                                argument):
    """(b): each exits 2, the lock not taken and nothing sent, and stderr
    names what is wrong: any of the three word arguments missing or empty;
    `--word-utc` not a UTC; a newline or a CR in any argument; `LANES_LANE`
    or `LANES_SESSION` unset."""
    spec, names = WORD_REFUSALS[argument]
    bench = Bench(tmp_path, [landing()])
    before = bench.git_state()
    proc = bench.run(spec["argv"], drop=spec.get("drop", ()))
    assert proc.returncode == 2, (
        f"[{argument}] the form exited {proc.returncode}, not 2 (L4-B10, T425): "
        f"{proc.stderr[-600:]}")
    assert names.lower() in proc.stderr.lower(), (
        f"[{argument}] stderr does not name {names!r}: {proc.stderr!r}")
    assert_nothing_sent(bench, proc, before, argument)


# ============================================================ (b, U3) a take with no UTC
TAKES = {
    "hold": (f"HOLD {EM} lane {WRITER} ({WS}), window w: {KEY} main {TIP} for AT-F13", True),
    "landing": (f"LANDING {EM} lane {WRITER}, session {SID_W}@{WS}, PR #5 into {KEY} main", True),
    "bad-stamp": (f"LANDING {EM} lane {WRITER}, session {SID_W}@{WS}, 2026-13-45T99:99Z, "
                  f"PR #5 into {KEY} main", True),
    "hold-refresh": (f"HOLD (refresh) {EM} lane {WRITER} ({WS}), window w: {KEY} main {TIP} "
                     f"for AT-F13", False),
    "off-primary": (f"HOLD {EM} lane {WRITER} ({WS}), window w: {KEY} main {TIP} for AT-F13",
                    False),
}


@pytest.mark.parametrize("case", list(TAKES))
def test_on_primary_a_take_with_no_readable_utc_is_refused_before_the_lock_and_written_off_primary(
        tmp_path, case):
    """(b, U3): on primary `append-line` with a text the one classifier
    reads as a `HOLD` with no UTC exits 2 before the lock, names the rule
    and sends nothing; so do a `LANDING` with no UTC and a take whose stamp
    does not parse, `2026-13-45T99:99Z`. A `HOLD (refresh)` with no UTC is not
    refused by this rule, and is sent. Off primary the same `HOLD` is written
    as today, after the mode query answered files."""
    text, refused = TAKES[case]
    bench = Bench(tmp_path, [], mode="files" if case == "off-primary" else "primary")
    before = bench.git_state()
    proc = bench.run(["append-line", text])
    if refused:
        assert proc.returncode == 2, (
            f"[{case}] append-line exited {proc.returncode}, not 2 (L4-B10, lane 4's T424): "
            f"{proc.stderr[-600:]}")
        assert "UTC" in proc.stderr, f"[{case}] stderr does not name the rule: {proc.stderr!r}"
        assert_nothing_sent(bench, proc, before, case)
        return
    assert proc.returncode == 0, f"[{case}] append-line exited {proc.returncode}: {proc.stderr}"
    if case == "hold-refresh":
        assert len(bench.calls("register", "commit")) == 1, (
            f"[{case}] {len(bench.calls('register', 'commit'))} commit calls, not one "
            f"(L4-B3, T415): the line was not sent on primary")
        assert bench.added_lines() == [text]
        return
    assert bench.calls("register", "commit") == [], "files mode sent a commit"
    assert git(bench.origin, "show", "main:lanes/LANES.md", env=bench.env).rstrip("\n") \
        .endswith(text), "files mode did not write the line as today"
    assert bench.asked_the_mode(), (
        f"[{case}] the mode query was never asked, so this is not 'off primary' (lane 5's "
        f"T504, reg_open): {bench.calls()}")


# ============================================================ C1's fourth text (T253c)
#
# Lane 4's question 11 (#165 6752694348; R-F11-1; lane 3's (a), 6747761107;
# B11 tasks:608, :1267): on primary `append-line` refuses, before the lock, a
# `LANDING` take whose lane cannot be read, which would hold `main` with
# nothing able to close it; files mode, which has no slot table, writes it as
# today. The line is a `LANDING` that names no lane, lane 2's reading of
# "whose lane cannot be read" until the contract's draft after 4.9 words the
# text (F11's NOTES question 34): it has a UTC and a repository, so neither of
# T424's other take refusals meets it. The case asserts the 2 and that nothing
# is written, not the wording.
LANELESS_LANDING = f"LANDING {EM} session {SID_W}@{WS}, {ago(1)}, PR #12 into {KEY} main"


def test_on_primary_a_landing_take_whose_lane_cannot_be_read_is_refused_before_the_lock_and_written_off_primary(
        tmp_path):
    """C1's fourth text: on primary, `append-line` of a `LANDING` line that
    names no lane exits 2 before the lock, with no commit call, no `psql`
    call and nothing written; off primary, after the mode query answered
    files, the same line is written as today."""
    fields = lanes_index_module().parse_register_line(LANELESS_LANDING)
    assert fields and fields["kind"] == "LANDING" and fields["lane"] is None, fields
    assert fields["utc"] and fields["repo"] == KEY, fields
    bench = Bench(tmp_path / "primary", [])
    before = bench.git_state()
    proc = bench.run(["append-line", LANELESS_LANDING])
    assert proc.returncode == 2, (
        f"append-line of a LANDING whose lane cannot be read exited {proc.returncode}, not 2, "
        f"on primary (L4-B10, lane 4's T424): {proc.stderr[-600:]}")
    assert_nothing_sent(bench, proc, before, "laneless-landing")
    files = Bench(tmp_path / "files", [], mode="files")
    written = files.run(["append-line", LANELESS_LANDING])
    assert written.returncode == 0, f"files mode refused the line: {written.stderr}"
    assert files.calls("register", "commit") == [], "files mode sent a commit"
    assert git(files.origin, "show", "main:lanes/LANES.md", env=files.env).rstrip("\n") \
        .endswith(LANELESS_LANDING), "files mode did not write the line as today"
    assert files.asked_the_mode(), (
        f"the mode query was never asked, so this is not 'off primary' (lane 5's T504, "
        f"reg_open): {files.calls()}")


# ============================================================ (c) the kind typed by hand
TYPED = {
    "em-dash": (f"LANDING EXPIRED {EM} ", True),
    "hyphen": ("LANDING EXPIRED - ", True),
    "tab-em-dash": (f"LANDING EXPIRED\t{EM}\t", True),
    "tab-hyphen": ("LANDING EXPIRED\t-\t", True),
    "landing": (f"LANDING {EM} ", False),
    "landed": (f"LANDED {EM} ", False),
    "landing-expiredx": (f"LANDING EXPIREDX {EM} ", False),
}


def _typed(opening: str) -> str:
    rest = (f"lane {WRITER}, session {SID_W}@{WS}, {ago(1)}, for lane {HOLDER}, PR #12 into {KEY} "
            f"main")
    if opening.startswith("LANDED"):
        rest += f" {ARROW} abc1234"
    return opening + rest


@pytest.mark.parametrize("text", list(TYPED))
def test_on_primary_the_landing_expired_kind_typed_by_hand_is_refused_naming_the_form(tmp_path,
                                                                                      text):
    """(c): on primary `LANDING EXPIRED <dash> ` and its tab forms each exit
    2 with nothing sent, and stderr names `append-line --landing-expired`.
    The rule does not refuse `LANDING <dash> `, `LANDED <dash> ` or `LANDING
    EXPIREDX <dash> `. The grown `REGISTER_KIND_RE` (lane 1's T118) reads the
    kind `LANDING EXPIRED` from exactly the refused rows."""
    opening, refused = TYPED[text]
    line = _typed(opening)
    kind_re = lanes_index_module().REGISTER_KIND_RE
    m = kind_re.match(line)
    assert bool(m and m.group(1) == "LANDING EXPIRED") == refused, (
        f"[{text}] REGISTER_KIND_RE reads {(m.group(1) if m else None)!r}: the client's rule and "
        f"the one classifier disagree (L1-A16, lane 1's T118)")
    bench = Bench(tmp_path, [])
    before = bench.git_state()
    proc = bench.run(["append-line", line])
    if refused:
        assert proc.returncode == 2, (
            f"[{text}] append-line exited {proc.returncode}, not 2 (L4-B10, T424): "
            f"{proc.stderr[-600:]}")
        assert "append-line --landing-expired" in proc.stderr, (
            f"[{text}] stderr does not name the form: {proc.stderr!r}")
        assert_nothing_sent(bench, proc, before, text)
        return
    assert proc.returncode == 0, f"[{text}] append-line exited {proc.returncode}: {proc.stderr}"
    assert len(bench.calls("register", "commit")) == 1, (
        f"[{text}] the line was not sent on primary (L4-B3, T415): {bench.calls()}")
    assert bench.added_lines() == [line]


# ============================================================ (d) nothing stale
NOTHING_STALE = {
    "no-landing": ([landing(lane=OTHER)], {}),
    "closed-by-landed": ([landing(minutes=45), landed(minutes=40)], {}),
    "already-released": ([landing(minutes=45), expired(minutes=10, landing_utc=ago(45))], {}),
    "other-pr": ([landing(pr=OTHER_PR)], {}),
    "other-repository": ([landing(repo=OTHER_KEY)], {}),
    "age-29": ([landing(minutes=29)], {}),
    "age-30": ([landing(minutes=30)], {}),
    "posted-again-40-and-10": ([landing(minutes=40), landing(minutes=10)], {}),
    "landing-minutes-5": ([landing(minutes=10)], {"LANES_LANDING_MINUTES": "5"}),
}


@pytest.mark.parametrize("case", list(NOTHING_STALE))
def test_the_landing_expired_form_sends_nothing_where_no_landing_is_stale_at_the_snapshot(
        tmp_path, case):
    """(d): each exits 2 with no commit call and nothing written: no
    `LANDING`; one closed by `LANDED`; one already released by an earlier
    `LANDING EXPIRED`; the holder's `LANDING` for another PR or repository;
    ages of 29 and 30 minutes by the snapshot's clock, far from `date`; a
    `LANDING` posted again, 40 and 10 minutes before, whose newest post is not
    past 30 minutes; and `LANES_LANDING_MINUTES=5` changes nothing. At 31
    minutes the line is composed: case (a)'s `[plain]`."""
    lines, extra = NOTHING_STALE[case]
    bench = Bench(tmp_path, lines)
    before = bench.git_state()
    proc = bench.run(form(), extra=extra)
    assert proc.returncode == 2, (
        f"[{case}] the form exited {proc.returncode}, not 2 (L4-B10, T425): {proc.stderr[-600:]}")
    assert proc.stderr.strip(), f"[{case}] the refusal says nothing"
    assert_nothing_sent(bench, proc, before, case)


# ============================================================ (e) what it prints
LR005_YOUNG = (f"ERROR:  LR005: lane {HOLDER}'s LANDING of {ago(12)} for PR #{PR} into {KEY} "
               f"main is too young (F13): its age by the database's clock is 12 min\n"
               f"DETAIL:  expired-young\n")


@pytest.mark.parametrize("case", ["success", "lr005-expired-young", "in-doubt"])
def test_the_landing_expired_form_prints_its_seq_once_and_an_lr005_with_its_detail_token(tmp_path,
                                                                                        case):
    """(e): success prints one line, `register seq <s>: released lane
    <holder>'s LANDING of <UTC> (PR #<n> into <repo> main), <m> min past Rule
    6's 30`, and exits 0. A fake LR005 exits 2, and stderr has LR005, its
    token and that nothing was written. A fake in-doubt commit, whose lookup
    is in doubt too, exits 3 and prints the rerun once; the rerun with the
    same arguments sends the same `--args-sha256`, and commits."""
    bench = Bench(tmp_path, [landing(minutes=31)])
    if case == "lr005-expired-young":
        bench.outcome("register commit", exit=2, stderr=LR005_YOUNG)
    if case == "in-doubt":
        bench.outcome("register commit", exit=3,
                      stderr="ERROR:  57014: canceling statement due to statement timeout\n")
        bench.outcome("journal", exit=3, stderr="lanes-index: journal: in doubt (T253)\n")
    proc = bench.run(form())
    said = proc.stdout + proc.stderr
    if case == "success":
        assert proc.returncode == 0, f"the form exited {proc.returncode} (L4-B10): {proc.stderr}"
        want = (f"register seq 2: released lane {HOLDER}'s LANDING of {ago(31)} (PR #{PR} into "
                f"{KEY} main), 1 min past Rule 6's 30")
        assert proc.stdout.splitlines().count(want) == 1, f"stdout is not {want!r}: {proc.stdout!r}"
        assert said.count("register seq") == 1, f"the seq is printed more than once: {said!r}"
        return
    if case == "lr005-expired-young":
        assert proc.returncode == 2, f"exit {proc.returncode}, not 2 (L4-B10): {proc.stderr}"
        for part in ("LR005", "expired-young", "nothing was written"):
            assert part in proc.stderr, f"stderr lacks {part!r}: {proc.stderr!r}"
        assert "register seq" not in said
        return
    assert proc.returncode == 3, f"exit {proc.returncode}, not 3 (L4-B3, T415): {proc.stderr}"
    assert said.count("--landing-expired") == 1, f"the rerun is not printed once: {said!r}"
    first = bench.calls("register", "commit")
    assert first, "no commit call was made"
    bench.outcome("register commit")
    bench.outcome("journal")
    again = bench.run(form())
    assert again.returncode == 0, f"the rerun exited {again.returncode}: {again.stderr}"
    sums = {argv[argv.index("--args-sha256") + 1] for argv in bench.calls("register", "commit")}
    assert len(sums) == 1, f"the rerun's digest differs from the pending record's: {sums}"


# ============================================================ (f) files mode
@pytest.mark.parametrize("mode", ["files", "fall-to-files"])
def test_in_files_mode_the_landing_expired_form_exits_2_and_changes_nothing(tmp_path, mode):
    """(f): in files mode, and after the mode query's fall to files mode
    (F8), the form exits 2 saying the release of a stale `LANDING` exists
    only on `mode=primary` and nothing was written; the register file, `git
    log` and `who --landing`'s output are byte-identical before and after,
    each line's age aside, which the host's clock moves and each read must
    show as its UTC's age by that clock (`aged_out`; RC-W49's SHOULD 1).
    Plain `append-line "LANDING EXPIRED <dash> ..."` is written as today."""
    bench = Bench(tmp_path, [landing()], mode="files" if mode == "files" else "fall")
    before, (_, listed) = bench.git_state(), bench.who_aged()
    proc = bench.run(form())
    assert proc.returncode == 2, (
        f"[{mode}] the form exited {proc.returncode}, not 2 (L4-B10, T425): {proc.stderr[-600:]}")
    for part in FILES_MODE_WORDS:
        assert part in proc.stderr, f"[{mode}] stderr lacks {part!r}: {proc.stderr!r}"
    assert bench.git_state() == before, f"[{mode}] git changed"
    assert bench.who_aged()[1] == listed, f"[{mode}] who --landing changed"
    typed = _typed(f"LANDING EXPIRED {EM} ")
    plain = bench.run(["append-line", typed])
    assert plain.returncode == 0, f"[{mode}] the plain line was refused: {plain.stderr}"
    assert git(bench.origin, "show", "main:lanes/LANES.md", env=bench.env).rstrip("\n") \
        .endswith(typed), f"[{mode}] the plain line was not written as today"


# ============================================================ (g) parse
def test_parse_register_line_reads_the_landing_expired_fields_before_the_word_clause():
    """(g): Brett's quote carries `lane x`, `PR #9`, `into a/b main`, a UTC
    and `session s@w`; `parse_register_line` still reads the writer, the PR,
    the repository, the UTC and the session from before the word clause, and
    `for_lane` is the holder (lane 1's T118, which grows `REGISTER_KIND_RE`
    to `LANDING EXPIRED` and adds `for_lane`)."""
    line = expired(writer=WRITER, minutes=0, pr=7, landing_utc=ago(45),
                   word="lane x, PR #9 into a/b main, 2026-01-02T03:04:05Z, session s@w",
                   where="lane x's session", word_utc="2026-01-02T03:05:00Z")
    fields = lanes_index_module().parse_register_line(line)
    assert fields is not None, (
        "parse_register_line reads no kind from a LANDING EXPIRED line (L1-A16, lane 1's T118)")
    assert fields["kind"] == "LANDING EXPIRED", fields
    assert (fields["lane"], fields["pr"], fields["repo"], fields["utc"], fields["session"]) == \
        (WRITER, "7", KEY, utc_of(CLOCK), SID_W), fields
    assert fields.get("for_lane") == HOLDER, fields


# ============================================================ (k) who --landing on primary
WHO_CASES = {
    # case: (the lines, the lanes listed, the lanes not listed)
    "released-only-one": ([landing(minutes=45), expired()], [], [HOLDER]),
    "another-lane-still-listed": ([landing(minutes=45), landing(lane=OTHER, minutes=20, pr=11),
                                   expired(writer=WRITER)], [OTHER], [HOLDER]),
    "names-another-pr": ([landing(minutes=45), expired(pr=OTHER_PR)], [HOLDER], []),
    "names-another-repository": ([landing(minutes=45), expired(repo=OTHER_KEY)], [HOLDER], []),
    "names-the-holder-in-another-case": ([landing(minutes=45), expired(holder=HOLDER.upper())],
                                         [HOLDER], []),
    "a-later-landing": ([landing(minutes=45), expired(minutes=20), landing(minutes=2)],
                        [HOLDER], []),
    "the-quote-names-another-lane": ([landing(minutes=45), landing(lane=OTHER, minutes=20, pr=11),
                                      expired(writer=WRITER, word=f"lane {OTHER}, PR #11 into "
                                                                  f"{OTHER_KEY} main")],
                                     [OTHER], [HOLDER]),
}


@pytest.mark.parametrize("case", list(WHO_CASES))
def test_who_landing_on_primary_drops_only_the_released_landing(tmp_path, case):
    """(k): on primary, with the fake `register read` prefetch whose text at
    `n` holds the lines, a released `LANDING` is not listed, and `none open
    <dash> ...` is printed where it was the only one; another lane's `LANDING`
    on that repository is still listed; a `LANDING EXPIRED` naming another
    PR, another repository or the holder in another case closes nothing; the
    holder's later `LANDING` is listed again; Brett's quote naming another
    lane, PR or repository changes nothing; and no empty row is listed."""
    lines, listed, dropped = WHO_CASES[case]
    bench = Bench(tmp_path, lines)
    proc = bench.who()
    assert proc.returncode == 0, f"[{case}] who --landing exited {proc.returncode}: {proc.stderr}"
    rows = [line for line in proc.stdout.splitlines() if line.startswith("LANDING  ")]
    for lane in dropped:
        assert not any(f"  lane {lane}," in row for row in rows), (
            f"[{case}] lane {lane}'s released LANDING is still listed on primary (L4-B10, "
            f"T425's RULE6_EXPIRED_AWK): {rows}")
    for lane in listed:
        assert any(f"  lane {lane}," in row for row in rows), (
            f"[{case}] lane {lane}'s LANDING is not listed: {proc.stdout!r}")
    if not listed:
        assert any(line.startswith(f"none open {EM} ") for line in proc.stdout.splitlines()), (
            f"[{case}] `none open` is not printed: {proc.stdout!r}")
    assert not any(re.search(r"#\s|lane ,", row) for row in rows), f"an empty row: {rows}"
    assert bench.calls("register", "read"), (
        f"[{case}] who --landing did not read the register through the prefetch (lane 5's "
        f"T504, reg_open): {bench.calls()}")


# ============================================================ (l) off primary, and the flag
INHERITED = {"RULE6_PRIMARY": "1", "RULE6_AWK": '{ print "INHERITED" }',
             "RULE6_EXPIRED_AWK": '{ print "INHERITED" }'}


@pytest.mark.parametrize("mode", ["files", "index", "unconfigured", "fall-to-files"])
def test_off_primary_rule6_awk_is_the_pin_and_the_flag_cannot_be_inherited(tmp_path, mode):
    """(l): the same register text, read in files mode, in `index` mode, on
    an unconfigured workstation and after F8's fall to files mode, lists the
    holder's `LANDING`, marked STALE, as today; a caller's environment
    carrying `RULE6_PRIMARY=1`, `RULE6_AWK` or `RULE6_EXPIRED_AWK` changes
    nothing, each line's age aside, as in (f); and `RULE6_AWK`'s text is the
    pin's. The mode query was asked where a configuration exists, and not on
    the unconfigured workstation, which starts no process (D3)."""
    bench = Bench(tmp_path, [landing(minutes=45), expired()],
                  mode="fall" if mode == "fall-to-files" else mode)
    plain, plain_aged = bench.who_aged()
    assert plain.returncode == 0, f"[{mode}] who --landing exited {plain.returncode}"
    rows = [line for line in plain.stdout.splitlines()
            if line.startswith(f"LANDING  {KEY}#{PR}  lane {HOLDER}, {ago(45)}")]
    assert len(rows) == 1 and rows[0].endswith(STALE_MARK), (
        f"[{mode}] the holder's LANDING is not listed STALE as today: {plain.stdout!r}")
    flagged, flagged_aged = bench.who_aged(extra=INHERITED)
    assert (flagged.returncode, flagged_aged) == (plain.returncode, plain_aged), (
        f"[{mode}] an inherited RULE6_* changed who --landing: {flagged.stdout!r}")
    text = bench.lanes_edit.read_text(encoding="utf-8")
    assert _rule6_awk_sha(text) == RULE6_AWK_PIN, f"[{mode}] RULE6_AWK is not the pin"
    # D3 (Y:368-371): `lanes-index mode` is asked only where a configuration
    # exists, so the unconfigured workstation starts no process and asks
    # nothing (T504's `asks_lanes_index_mode_only_where_a_configuration_exists`).
    asked = mode != "unconfigured"
    said = "was never asked" if asked else "was asked with no configuration, against D3"
    assert bench.asked_the_mode() == asked, (
        f"[{mode}] the mode query {said} (lane 5's T504, reg_open; T425's one line sets "
        f"rule6_primary_on from its answer): {bench.calls()}")


def _rule6_awk_sha(text: str) -> str:
    found = re.findall(r"^RULE6_AWK='(.*?)'$", text, re.S | re.M)
    assert len(found) == 1, f"{len(found)} `RULE6_AWK='...'` assignments, not one"
    return hashlib.sha256(found[0].encode("utf-8")).hexdigest()


def _function_body(text: str, name: str) -> str:
    m = re.search(rf"^{re.escape(name)}\(\) \{{\n(.*?)^\}}$", text, re.S | re.M)
    return m.group(1) if m else None


def _awks() -> list:
    found = []
    for name in ("awk", "mawk", "gawk", "original-awk", "nawk"):
        path = shutil.which(name)
        if path and os.path.realpath(path) not in [os.path.realpath(p) for p in found]:
            found.append(path)
    busybox = shutil.which("busybox")
    if busybox:
        found.append(f"{busybox} awk")
    return found


def test_rule6_primary_on_is_called_only_where_lane_4_places_it_and_who_landing_stays_pinned():
    """(l), the source check: `rule6_primary_on` is defined once and called
    at one site, T425's one line that reads `REG_MODE` after both doors and
    before the arm (R45; B11 tasks:729, :1102, :1282); it appends
    `RULE6_EXPIRED_AWK` to `RULE6_AWK` once and sets `RULE6_PRIMARY`;
    `RULE6_AWK` itself is the pin; `who_landing`'s pinned line is unchanged;
    and the program with the branch gives one output on every awk here."""
    text = LANES_EDIT.read_text(encoding="utf-8")
    body = _function_body(text, "rule6_primary_on")
    assert body is not None, "lanes-edit.sh defines no rule6_primary_on (L4-B10, lane 4's T425)"
    calls = [line for line in text.splitlines()
             if "rule6_primary_on" in line and not line.lstrip().startswith("#")
             and not line.startswith("rule6_primary_on()")]
    assert len(calls) == 1 and "REG_MODE" in calls[0], (
        f"rule6_primary_on is called at {len(calls)} sites, not at T425's one line on "
        f"REG_MODE: {calls}")
    assert body.count("RULE6_EXPIRED_AWK") == 1 and "RULE6_PRIMARY=" in body, body
    assert _rule6_awk_sha(text) == RULE6_AWK_PIN, "RULE6_AWK is not the pin"
    assert text.count(WHO_LANDING_LINE + "\n") == 1, "who_landing's pinned line changed"
    branch = re.findall(r"^RULE6_EXPIRED_AWK='(.*?)'$", text, re.S | re.M)
    assert len(branch) == 1, "no single RULE6_EXPIRED_AWK='...' assignment"
    program = re.findall(r"^RULE6_AWK='(.*?)'$", text, re.S | re.M)[0] + branch[0]
    sample = "\n".join([landing(minutes=45), expired(), landing(lane=OTHER, minutes=20, pr=11)])
    outputs = {}
    for awk in _awks():
        proc = subprocess.run([*awk.split(), program], input=sample + "\n", capture_output=True,
                              encoding="utf-8", env={"PATH": "/usr/bin:/bin", "LC_ALL": "C",
                                                     "LANES_RULE6_ALIASES": f"{ALIAS}\037{KEY}"},
                              timeout=60, check=False)
        assert proc.returncode == 0, f"{awk} refused the program: {proc.stderr}"
        outputs[awk] = sorted(proc.stdout.splitlines())
    assert len({json.dumps(o) for o in outputs.values()}) == 1, outputs


# ============================================================ (m) the token decides
FAKE_LR005 = {
    # case: (the verb's arguments, the lane, the server's message, the token,
    # what stderr must also carry)
    "expired-none": (form(), WRITER,
                     f"no open LANDING of lane {HOLDER} for PR #{PR} into {KEY} main to release "
                     f"(F13)", "expired-none", ()),
    "expired-closed": (form(), WRITER,
                       f"lane {HOLDER}'s LANDING for PR #{PR} is already closed, by a LANDED of "
                       f"{HOLDER} (F13)", "expired-closed", ()),
    "expired-young": (form(), WRITER, LR005_YOUNG.splitlines()[0][len("ERROR:  LR005: "):],
                      "expired-young", ()),
    "take-no-utc": (["append-line", f"HOLD {EM} lane {WRITER} ({WS}), window w, {ago(1)}: {KEY} "
                     f"main {TIP} for AT-F13"], WRITER,
                    "a take whose UTC cannot be read takes nothing (U3)", "take-no-utc", ()),
    "one-live-claim": (["claim", f"{KEY}#{PR}", "--no-github"], WRITER,
                       f"{KEY}#{PR} already has a live claim, lane {OTHER}'s at seq 4 (D19)",
                       "one-live-claim", (OTHER,)),
    "claim-spellings": (["claim", f"{ALIAS}#{PR}", "--no-github"], WRITER,
                        f"{ALIAS}#{PR} is {KEY}#{PR}, claimed by lane {OTHER} at seq 4 (D19)",
                        "claim-spellings", (OTHER,)),
    "main-held": (["append-line", f"HOLD {EM} lane {WRITER} ({WS}), window w, {ago(1)}: {KEY} "
                   f"main {TIP} for AT-F13"], WRITER,
                  f"{KEY} main is held by lane {OTHER}'s LANDING at seq 4 (D18)", "main-held",
                  (OTHER,)),
}
F13_TOKENS = ("expired-none", "expired-closed", "expired-young")


@pytest.mark.parametrize("case", [*FAKE_LR005, "swapped-message"])
def test_the_writer_reads_lr005s_reason_from_its_detail_token_never_its_message(tmp_path, case):
    """(m), U7: the commit call ends LR005 with exit 2, `ERROR:  LR005:
    <message>` and `DETAIL:  <token>`. For each of F13's three tokens and
    `take-no-utc`, the writer exits 2 and stderr carries the server's
    message, the token and that nothing was written; for `one-live-claim`,
    `claim-spellings` and `main-held` it exits 2 as AT-4's losers do, naming
    the holder. `[swapped-message]`: F13's message under `main-held` gives no
    F13 token, and D18's message under `expired-young` gives `expired-young`:
    the writer follows the token."""
    bench = Bench(tmp_path, [landing(minutes=45)])
    if case == "swapped-message":
        runs = [(FAKE_LR005["main-held"][0], FAKE_LR005["expired-young"][2], "main-held"),
                (form(), FAKE_LR005["main-held"][2], "expired-young")]
        for argv, message, token in runs:
            bench.outcome("register commit", exit=2,
                          stderr=f"ERROR:  LR005: {message}\nDETAIL:  {token}\n")
            proc = bench.run(argv)
            assert proc.returncode == 2, f"[{token}] exit {proc.returncode}, not 2: {proc.stderr}"
            carried = [t for t in F13_TOKENS if t in proc.stderr]
            want = [] if token == "main-held" else [token]
            assert carried == want, (
                f"[{token}] stderr carries {carried}, not {want}: the writer read the message, "
                f"not the token (U7; L4-B10): {proc.stderr!r}")
            bench.outcome("register commit")
        return
    argv, lane, message, token, names = FAKE_LR005[case]
    bench.outcome("register commit", exit=2, stderr=f"ERROR:  LR005: {message}\nDETAIL:  {token}\n")
    before = bench.git_state()
    proc = bench.run(argv, lane=lane)
    assert proc.returncode == 2, (
        f"[{case}] the writer exited {proc.returncode}, not 2 (L4-B3, T415; L4-B10): "
        f"{proc.stderr[-600:]}")
    if names:
        for name in names:
            assert name in proc.stderr, f"[{case}] stderr does not name {name}: {proc.stderr!r}"
    else:
        for part in (message, token, "nothing was written"):
            assert part in proc.stderr, f"[{case}] stderr lacks {part!r}: {proc.stderr!r}"
    assert bench.head() == 1 and bench.git_state() == before, f"[{case}] something was written"


# ============================================================ the real engine: (i) and (j)
#
# AT-F13's fixture for (h) to (j) (the test plan's section on AT-F13,
# "Fixture"): a clone of `tmpl_imported` (or of `tmpl`, where the case imports
# its own history) brought to `primary` with the marker `present` by
# AT-LR006's route, the documented functions called as REGISTER-WRITER through
# T228's `lanes_w_fx`, in T223's form (`test_sql_register_order.py`'s `Clone`)
# and T210's (`import_to_primary`).

SCHEMA = "lanes_register"
WRITER_LOGIN = "lanes_w_fx"
CONNECT_TO = "lanes_register_writer, lanes_register_reader, lanes_indexer"
AUTHOR = "T253 Fixture <t253@example.invalid>"
OPERATOR = "operator-t253"
MARKER_COMMIT = "c0ffee" + "0" * 34
_NAMES = itertools.count(1)


class Register:
    """A clone of `template`, its own, dropped by the fixture at the end."""

    def __init__(self, cluster, template: str) -> None:
        found = cluster.psql(f"SELECT datname FROM pg_database WHERE datname = '{template}';")
        assert found.stdout.split() == [template], (
            f"no {template} on the session cluster: lane 2's T227 builds it")
        self.cluster, self.name = cluster, f"t253_{next(_NAMES)}"
        cluster.psql(f"CREATE DATABASE {self.name} TEMPLATE {template};")
        cluster.psql(f"REVOKE ALL ON DATABASE {self.name} FROM PUBLIC;\n"
                     f"GRANT CONNECT ON DATABASE {self.name} TO {CONNECT_TO};\n")
        from pgcluster import Database
        self.db = Database(cluster, self.name)

    def value(self, sql: str) -> str:
        return self.db.psql(sql).stdout.strip()

    def rows(self, query: str) -> list:
        out = self.value(f"SET search_path TO {SCHEMA};\n"
                         f"SELECT coalesce(jsonb_agg(q), '[]'::jsonb) FROM ({query}) q;")
        return json.loads(out.splitlines()[-1])

    def head(self) -> int:
        return self.rows("SELECT seq FROM register_head")[0]["seq"]

    def clock(self) -> int:
        return self.rows("SELECT floor(extract(epoch FROM clock_timestamp()))::bigint AS s")[0]["s"]

    def call(self, sql: str) -> subprocess.CompletedProcess:
        argv = [self.db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                "-v", "VERBOSITY=verbose", "-v", "SHOW_CONTEXT=never"]
        return subprocess.run(argv, input=sql, capture_output=True, text=True, timeout=60,
                              env=self.db.env(WRITER_LOGIN), check=False)

    def commit(self, body: dict) -> int:
        """The commit call, as `lanes_w_fx`, at the head; the seq it made."""
        sw = self.rows("SELECT generation FROM register_switch")[0]
        version = self.rows("SELECT version FROM schema_version")[0]["version"]
        literal = json.dumps(body, ensure_ascii=True).replace("'", "''")
        proc = self.call(f"BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
                         f"SELECT {SCHEMA}.commit_write({self.head()}, '{uuid.uuid4()}'::uuid, "
                         f"{version}, '{sw['generation']}'::uuid, '{literal}'::jsonb);\nCOMMIT;\n")
        assert proc.returncode == 0, f"commit_write exited {proc.returncode}: {proc.stderr[-800:]}"
        return int(proc.stdout.strip().splitlines()[-1])

    def entry(self, kind: str, verb: str, lane: str, **parts) -> dict:
        journal = {"kind": kind, "verb": verb, "lane": lane, "workstation": WS, "author": AUTHOR,
                   "message": f"t253: {kind}"}
        journal.update(parts.pop("journal", {}))
        return {"journal": journal, "not_after": "2100-01-01T00:00:00Z", **parts}

    def import_files(self, files: dict, register_lines: list) -> int:
        """An `import` entry of `files` ({path: text}), with `register_lines`."""
        edits, rows, ordinal = [], [], 0
        for path in sorted(files):
            ordinal += 1
            edits.append({"ord": ordinal, "op": "create", "path": path})
            for text in files[path].rstrip("\n").split("\n"):
                ordinal += 1
                edits.append({"ord": ordinal, "op": "append", "path": path, "new_text": text})
            rows.append({"path": path, "present": True, "final_newline": True,
                         "sha256": hashlib.sha256(files[path].encode("utf-8")).hexdigest()})
        return self.commit(self.entry("import", "import", OPERATOR,
                                      journal={"git_commit": "1" * 40, "git_tree": "2" * 40},
                                      edits=edits, files=rows, register_lines=register_lines))

    def to_primary(self) -> int:
        """AT-LR006's route: a `cutover` entry, then `record_marker`."""
        store = "store=primary\n"
        cut = self.commit(self.entry("cutover", "cutover", OPERATOR,
                                     edits=[{"ord": 1, "op": "create", "path": "lanes/STORE"},
                                            {"ord": 2, "op": "append", "path": "lanes/STORE",
                                             "new_text": "store=primary"}],
                                     files=[{"path": "lanes/STORE", "present": True,
                                             "final_newline": True,
                                             "sha256": hashlib.sha256(store.encode()).hexdigest()}]))
        version = self.rows("SELECT version FROM schema_version")[0]["version"]
        marked = self.call(f"SELECT {SCHEMA}.record_marker({version}, {cut}, '{MARKER_COMMIT}', "
                           f"'{WS}');\n")
        assert (marked.returncode, marked.stdout.strip()) == (0, "present"), marked.stderr
        return cut

    def open_landings(self) -> set:
        return {(r["lane"], str(r["pr"]), r["repo_key"]) for r in self.rows(
            "SELECT lane, pr, repo_key FROM main_slots WHERE slot_kind = 'landing'")}


@pytest.fixture()
def registers(pg_cluster):
    made = []

    def make(template: str = "tmpl_imported") -> Register:
        reg = Register(pg_cluster, template)
        made.append(reg.name)
        return reg

    yield make
    for name in made:
        pg_cluster.drop_database(name)


def line_rows(lines: list, clock: int, repos: dict, path: str = "lanes/LANES.md",
              first_line: int = 1) -> list:
    """Each line's `register_lines` row, as the checkout's own classifier
    (lane 1's T118: `parse_register_line`, `REGISTER_SLOTS`) reads it, its
    `repo_key` by `repos` ({spelling: key}, Rule 6's map), its `utc_ts` the
    line's UTC as epoch seconds."""
    module = lanes_index_module()
    rows = []
    for k, text in enumerate(lines):
        fields = module.parse_register_line(text)
        if fields is None:
            continue
        role, slot = module.REGISTER_SLOTS.get(fields["kind"], (None, None))
        repo = fields.get("repo")
        key = repos.get((repo or "").lower(), repo)
        utc = fields.get("utc")
        epoch = calendar.timegm(time.strptime(utc, "%Y-%m-%dT%H:%M:%SZ")) if utc else None
        rows.append({"kind": fields["kind"], "slot_role": role, "slot_kind": slot,
                     "lane": fields["lane"], "repo": repo, "repo_key": key,
                     "repo_spellings": sorted({repo, key}) if repo else None,
                     "pr": int(fields["pr"]) if fields.get("pr") else None, "tip": fields.get("tip"),
                     "utc": utc, "utc_ts": utc_of(epoch).replace("T", " ").replace("Z", "+00")
                     if epoch is not None else None,
                     "session": fields.get("session"), "for_lane": fields.get("for_lane"),
                     "path": path, "line_no": first_line + k, "raw": text, "workstation": WS})
    return rows


def _shift(text: str, clock: int) -> str:
    """`text` with every UTC read from `CLOCK` moved to `clock`, so a
    history's ages hold against the database's clock."""
    return re.sub(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                  lambda m: utc_of(calendar.timegm(time.strptime(m.group(0), "%Y-%m-%dT%H:%M:%SZ"))
                                   - CLOCK + clock), text)


def primary_program_rows(text: str, aliases: dict) -> set:
    """The primary program, `RULE6_AWK` with `RULE6_EXPIRED_AWK` (lane 4's
    T425), over `text`: its open `LANDING`s, (lane, pr, canonical repo)."""
    source = LANES_EDIT.read_text(encoding="utf-8")
    base = re.findall(r"^RULE6_AWK='(.*?)'$", source, re.S | re.M)
    branch = re.findall(r"^RULE6_EXPIRED_AWK='(.*?)'$", source, re.S | re.M)
    assert len(base) == 1 and len(branch) == 1, (
        "lanes-edit.sh has no RULE6_EXPIRED_AWK beside RULE6_AWK (L4-B10, lane 4's T425)")
    table = "\n".join(f"{a}\037{k}" for a, k in aliases.items())
    proc = subprocess.run(["awk", base[0] + branch[0]], input=text, capture_output=True,
                          encoding="utf-8", env={"PATH": "/usr/bin:/bin", "LC_ALL": "C",
                                                 "LANES_RULE6_ALIASES": table},
                          timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    found = set()
    for row in proc.stdout.splitlines():
        parts = row.split("\037")
        if parts[0] == "LANDING":
            found.add((parts[1], parts[2], aliases.get(parts[4].lower(), parts[4])))
    return found


#: THE FORM'S WORD CLAUSE, the line's last part as `lanes-edit.sh:3375` composes
#: it (Y:5109): where and when Brett gave his word, then his quote.
WORD_CLAUSE_RE = re.compile(r"; on Brett's word \([^()]+, [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:"
                            r"[0-9]{2}:[0-9]{2}Z\): \"[^\"]+\"$")


def f13_findings(rows: list) -> dict:
    """LANE 2'S OWN CHECK of each imported `LANDING EXPIRED` (Y:5141, AT-F13
    (j)): the import does not run F13's check, so a line typed by hand in
    files mode would release a `LANDING` that F13 never judged, and both
    readers would agree on it. A line is a finding unless it meets F13's
    condition by its own UTC and its `LANDING`'s, matched as lane 1's check in
    the commit matches them (`lanes-index:7690-7715` at `c8acf67c`): the
    holder's newest `LANDING` before it for that PR and `repo_key`, the
    holder compared case-blind; no close of that `LANDING` between; and more
    than 30 minutes apart; and unless it ends with the form's word clause
    (Y:5109). `rows` are `line_rows`' in file order; the answer is {the line:
    what it fails}."""
    found = {}
    for k, row in enumerate(rows):
        if row["kind"] != "LANDING EXPIRED":
            continue
        holder, why = (row["for_lane"] or "").lower(), []
        takes = [j for j in range(k) if rows[j]["slot_role"] == "take"
                 and rows[j]["slot_kind"] == "landing" and (rows[j]["lane"] or "").lower() == holder
                 and rows[j]["pr"] == row["pr"] and rows[j]["repo_key"] == row["repo_key"]]
        if not takes:
            why.append("no LANDING of the holder for that PR and repo_key before it")
        else:
            take = rows[takes[-1]]
            if any(c["slot_role"] == "close" and c["slot_kind"] == "landing"
                   and (c["for_lane"] or c["lane"] or "").lower() == holder
                   and c["pr"] == row["pr"] and c["repo_key"] == row["repo_key"]
                   for c in rows[takes[-1] + 1:k]):
                why.append("a close of its LANDING between")
            own, its = _epoch_of(row["utc"]), _epoch_of(take["utc"])
            if own is None or its is None or own - its <= 30 * 60:
                why.append("not more than 30 minutes after its LANDING")
        if not WORD_CLAUSE_RE.search(row["raw"]):
            why.append("no word clause")
        if why:
            found[row["raw"]] = why
    return found


HISTORIES = {
    # history: (its lines, whether the two readers agree, and what lane 2's
    # own check of F13's condition finds in its `LANDING EXPIRED`, or None)
    "today": ([landing(minutes=45), landing(lane=OTHER, minutes=50, pr=11), landed(lane=OTHER,
                                                                                   minutes=48,
                                                                                   pr=11)],
              True, None),
    "re-import-after-a-rollback": ([landing(minutes=45), expired(minutes=10)], True, None),
    "typed-in-files-mode-meeting-f13": ([landing(minutes=45), expired(minutes=10)], True, None),
    "typed-10-minutes-after-its-landing": ([landing(minutes=45), expired(minutes=35)], True,
                                           "not more than 30 minutes"),
    "no-word-clause": ([landing(minutes=45), expired(minutes=10, clause=False)], True,
                       "no word clause"),
    "naming-another-pr": ([landing(minutes=45), expired(minutes=10, pr=OTHER_PR)], True,
                          "no LANDING"),
    "holder-in-another-case": ([landing(minutes=45), expired(minutes=10, holder=HOLDER.lower())],
                               False, None),
}


@pytest.mark.parametrize("history", list(HISTORIES))
def test_rule6_with_the_expired_branch_agrees_with_main_slots_on_imported_history(registers,
                                                                                  history):
    """(j), RE: D18's agreement on imported history (Y:5141; lane 3's ruling,
    #165 6833678789). The primary program (`RULE6_AWK` with
    `RULE6_EXPIRED_AWK`) and `main_slots` show no difference, and lane 2's
    own check of F13's condition (`f13_findings`) names nothing, on today's
    history (no `LANDING EXPIRED`), on a re-import that holds a
    primary-written `LANDING EXPIRED`, and on one typed in files mode that
    meets F13's condition by its own UTC and its `LANDING`'s and carries the
    form's word clause. Each of the four others is a finding, and the case
    shows it: one typed 10 minutes after its `LANDING`, one with no word
    clause, and one naming another PR, each by the test's own check of F13's
    condition, which names the line, since both readers agree on a typed
    line; and one whose holder is in another case, by the readers'
    difference, since `main_slots` closes it and the awk does not."""
    lines, agree, finding = HISTORIES[history]
    reg = registers("tmpl")
    clock = reg.clock()
    shifted = [_shift(text, clock) for text in lines]
    files = register_files(shifted)
    body = files["lanes/LANES.md"]
    first = body.split("\n").index(shifted[0]) + 1
    rows = line_rows(shifted, clock, {ALIAS: KEY, KEY.lower(): KEY}, first_line=first)
    reg.import_files({p: t for p, t in files.items() if RENDER_SET.match(p)}, rows)
    reg.to_primary()
    program = primary_program_rows(body, {ALIAS: KEY, KEY.lower(): KEY})
    slots = reg.open_landings()
    if agree:
        assert program == slots, f"[{history}] the awk {program} and main_slots {slots} differ"
    else:
        assert program != slots, (
            f"[{history}] the awk and main_slots agree on a history that is a finding: "
            f"{program}")
    findings = f13_findings(rows)
    if finding is None:
        assert findings == {}, (
            f"[{history}] lane 2's check of F13's condition names a line it should not: {findings}")
    else:
        assert list(findings) == [shifted[-1]], (
            f"[{history}] lane 2's check of F13's condition does not name the typed line, and "
            f"only it: {findings}")
        assert any(finding in why for why in findings[shifted[-1]]), (
            f"[{history}] the check does not find {finding!r}: {findings}")


def test_a_landed_between_the_forms_snapshot_and_commit_leaves_the_retry_nothing_to_release(
        registers, tmp_path):
    """(i), RE: lane B's `LANDED` commits between the form's snapshot and its
    commit, staged by the shim's `hold` on the commit call, not by timing. The
    commit fails with LR001, the retry exits 2 with "no open `LANDING`", and
    nothing of the form's is written."""
    reg = registers("tmpl_imported")
    reg.to_primary()
    clock = reg.clock()
    stale = _shift(landing(minutes=31), clock)
    start = int(reg.rows("SELECT count(*) AS n FROM doc_lines WHERE path = 'lanes/LANES.md'")[0]["n"])

    def append(lane: str, text: str) -> int:
        before = reg.rows("SELECT text FROM doc_lines WHERE path = 'lanes/LANES.md' ORDER BY line_no")
        lines = [r["text"] for r in before] + [text]
        rendered = ("\n".join(lines) + "\n").encode("utf-8")
        return reg.commit(reg.entry(
            "write", "append-line", lane,
            journal={"args_sha256": hashlib.sha256(text.encode()).hexdigest()},
            edits=[{"ord": 1, "op": "append", "path": "lanes/LANES.md", "new_text": text}],
            files=[{"path": "lanes/LANES.md", "present": True, "final_newline": True,
                    "sha256": hashlib.sha256(rendered).hexdigest()}],
            register_lines=line_rows([text], clock, {ALIAS: KEY, KEY.lower(): KEY},
                                     first_line=len(lines))))

    append(HOLDER, stale)
    fakebin = tmp_path / "shimbin"
    fakebin.mkdir()
    (fakebin / "psql").write_text(PSQL_SHIM, encoding="utf-8")
    (fakebin / "psql").chmod(0o755)
    fifo = tmp_path / "hold.fifo"
    os.mkfifo(fifo)
    (fakebin / PSQL_SHIM_CONTROL).write_text(json.dumps({
        "psql": reg.db.psql_bin,
        "arms": [{"mode": "hold", "match": "commit_write", "call": 1, "fifo": str(fifo)}]}),
        encoding="utf-8")
    origin, checkout, env = _workspace(tmp_path / "ws", fakebin, register_files([stale]))
    bindir = tmp_path / "bin"
    flipped_copy(LANES_INDEX, bindir, True)
    for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
        shutil.copy2(str(REPO / name), str(bindir / name))
    conf = tmp_path / "lanes-index.conf"
    conf.write_text(f"mode=primary\nregister_url={reg.db.url(WRITER_LOGIN)}\n"
                    f"reader_url={reg.db.url()}\n", encoding="utf-8")
    conf.chmod(0o600)
    env.update(LANES_INDEX_CONFIG=str(conf), LANES_LANE=WRITER, LANES_SESSION=SID_W)
    env.pop("LANES_INDEX", None)
    proc = subprocess.Popen(["bash", str(bindir / "lanes-edit.sh"), *form()], cwd=str(checkout),
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding="utf-8", stdin=subprocess.DEVNULL)
    released = {}

    def release() -> None:
        with open(fifo, "w") as held:
            released["seq"] = append(HOLDER, _shift(landed(minutes=1), clock))
            held.write("go\n")

    gate = threading.Thread(target=release, daemon=True)
    gate.start()
    out, err = proc.communicate(timeout=120)
    gate.join(timeout=60)
    assert "seq" in released, "the form's commit call never reached the shim's hold"
    assert proc.returncode == 2, f"the retry exited {proc.returncode}, not 2: {err[-800:]}"
    assert "no open" in err and "LANDING" in err, f"stderr does not say no open LANDING: {err!r}"
    assert reg.head() == released["seq"], "something was written after lane B's LANDED"
    # `register_lines` is keyed by `line_id`, and the path and the line's place
    # are `doc_lines`' (Y:1254; `lanes-index:7103`).
    kinds = reg.rows("SELECT r.kind FROM register_lines r JOIN doc_lines d USING (line_id) "
                     f"WHERE d.path = 'lanes/LANES.md' AND d.line_no > {start} ORDER BY d.line_no")
    assert [r["kind"] for r in kinds] == ["LANDING", "LANDED"], kinds


# ============================================================ T112's AT-F13 case (T253b)
#
# R-F10-34 (lane 3, #165 6755386771, reading 7; B10 tasks:413, :429;
# `PLACEMENT.md` section 2 as `PLACEMENT-2.md` amends it), with lane 3's point 4
# (#165 6768050756): the fixture is accepted, and the alias is also listed in the
# case's own shipped table, through `LANES_REPOS_TSV_SHIPPED` (lane 1, #165
# 6766921904, point 2), with a third key, so that one case proves both halves of
# Rule 6's order: the per-wip table overrides the shipped one, and within it the
# last row wins. Each table read alone, or the per-wip table's first row
# (`alias_lookup`'s, `lanes-edit.sh:3436-3446` at `39839dc`), gives another key.

#: The alias, and its three keys: the shipped table's, the per-wip table's
#: first row's, and Rule 6's (the per-wip table's last row).
STALE_ALIAS = "r7x"
SHIPPED_KEY, FIRST_ROW_KEY, RULE6_KEY = "opensoft/r7-shipped", "opensoft/r7-first", "opensoft/r7-rule6"
SHIPPED_TSV = f"# alias\towner/repo\n{STALE_ALIAS}\t{SHIPPED_KEY}\n"
PER_WIP_TSV = (f"# alias\towner/repo\n{STALE_ALIAS}\t{FIRST_ROW_KEY}\n"
               f"{STALE_ALIAS}\t{RULE6_KEY}\n")


def git_blob_id(data: bytes) -> str:
    """The blob id git gives `data`, as `changes.tsv` names it."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def test_register_commit_expires_an_imported_stale_landing_by_the_shipped_then_per_wip_repo_key(
        registers, tmp_path):
    """T112's AT-F13 case, RE (R-F10-34): a clone of `tmpl`, brought to
    `primary` by AT-LR006's route, whose `import` entry loads a `LANDING`
    older than Rule 6's 30 minutes, for one PR, on a repository the line
    spells by an alias. The case's per-wip `lanes/repos.tsv` lists the alias
    twice, the earlier row naming another key, and its own shipped table
    (`LANES_REPOS_TSV_SHIPPED`) lists it with a third key; the import's row
    carries Rule 6's key, the last row's (`rule6_aliases`,
    `lanes-edit.sh:6938` at code `39839dc`). Then `lanes-index register
    commit`, from T203's flipped copy, on an attempt directory in T101's
    format built on `register snapshot --tree`, appends a `LANDING EXPIRED`
    for that PR and spelling in T223's line form. It exits 0 with `committed
    <seq>`, with no LR005 `expired-none`, and the `LANDING`'s slot in
    `main_slots` is freed for Rule 6's key (Y:1989). It runs no
    `append-line`, so it needs no L4-B10. It fails until T107, T227's
    `tmpl`, T111 and T112 land (L1-A6, L1-A9, L1-A10; T227)."""
    reg = registers("tmpl")
    clock = reg.clock()
    stale_utc = utc_of(clock - 45 * 60)
    stale = (f"LANDING {EM} lane {HOLDER}, session {SID_H}@{WS}, {stale_utc}, PR #{PR} into "
             f"{STALE_ALIAS} main")
    files = register_files([stale], repos=PER_WIP_TSV)
    body = files["lanes/LANES.md"]
    line_no = body.split("\n").index(stale) + 1
    rows = line_rows([stale], clock, {STALE_ALIAS: RULE6_KEY}, first_line=line_no)
    assert [r["repo_key"] for r in rows] == [RULE6_KEY], rows
    reg.import_files({p: t for p, t in files.items() if RENDER_SET.match(p)}, rows)
    reg.to_primary()
    taken = (HOLDER, str(PR), RULE6_KEY)
    assert taken in reg.open_landings(), (
        f"the import's LANDING does not take main for Rule 6's key: {reg.open_landings()}")

    # THE WORKSTATION: the checkout's origin carries the per-wip table, the
    # shipped table is the case's own, and `lanes-index` is T203's flipped copy.
    fakebin = tmp_path / "fakebin"
    origin, checkout, env = _workspace(tmp_path / "ws", fakebin, files)
    shipped = tmp_path / "shipped-repos.tsv"
    shipped.write_text(SHIPPED_TSV, encoding="utf-8")
    copy = flipped_copy(LANES_INDEX, tmp_path / "bin", True)
    conf = tmp_path / "lanes-index.conf"
    conf.write_text(f"mode=primary\nregister_url={reg.db.url(WRITER_LOGIN)}\n"
                    f"reader_url={reg.db.url()}\n", encoding="utf-8")
    conf.chmod(0o600)
    env.update(LANES_INDEX_CONFIG=str(conf), LANES_REPOS_TSV_SHIPPED=str(shipped),
               PATH=str(reg.cluster.bindir) + os.pathsep + env["PATH"])
    env.pop("LANES_INDEX", None)

    def index(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(copy), *args], capture_output=True,
                              encoding="utf-8", errors="replace", env=env, timeout=120,
                              cwd=str(checkout), check=False, stdin=subprocess.DEVNULL)

    # THE ATTEMPT DIRECTORY (T101's format, contract section 3.3), on the
    # scratch tree `register snapshot --tree` builds at `n`.
    released = (f"LANDING EXPIRED {EM} lane {OTHER} {EM} PR #{PR} into {STALE_ALIAS} main "
                f"for lane {HOLDER} {EM} {utc_of(clock)}")
    args_sha = hashlib.sha256(f"{OTHER}\0append-line\0{released}".encode("utf-8")).hexdigest()
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    snap = index("register", "snapshot", "--write-id", "new", "--lane", OTHER, "--verb",
                 "append-line", "--args-sha256", args_sha, "--tree", str(attempt / "tree"),
                 "--checkout", str(checkout))
    assert snap.returncode == 0, f"register snapshot exited {snap.returncode}: {snap.stderr}"
    keys = dict(line.partition("=")[::2] for line in snap.stdout.splitlines() if "=" in line)
    (attempt / "snapshot").write_text(snap.stdout, encoding="utf-8")
    tree_head = git(attempt / "tree", "rev-parse", "HEAD:lanes/LANES.md", env=env).strip()
    base = git(attempt / "tree", "cat-file", "blob", tree_head, env=env).encode("utf-8")
    image = base + released.encode("utf-8") + b"\n"
    (attempt / "images" / "lanes").mkdir(parents=True)
    (attempt / "images" / "lanes" / "LANES.md").write_bytes(image)
    (attempt / "changes.tsv").write_text(
        f"M\tlanes/LANES.md\t{tree_head}\t{git_blob_id(image)}\n", encoding="utf-8")
    (attempt / "files").write_text(
        f"lanes/LANES.md\t1\t{hashlib.sha256(image).hexdigest()}\n", encoding="utf-8")
    (attempt / "msg").write_text(f"LANES({OTHER}@{WS}): append line {EM} T253's case\n",
                                 encoding="utf-8")
    (attempt / "author").write_text(f"{AUTHOR}\n", encoding="utf-8")
    (attempt / "not_after").write_text(keys["not_after"] + "\n", encoding="utf-8")

    done = index("register", "commit", "--write-id", keys["write_id"], "--generation",
                 keys["generation"], "--lane", OTHER, "--verb", "append-line", "--args-sha256",
                 args_sha, "--workstation", WS, str(attempt))
    assert "expired-none" not in done.stderr, (
        f"register commit met LR005 expired-none: the LANDING EXPIRED's repo_key is not Rule "
        f"6's (shipped, then per-wip, the last row winning): {done.stderr}")
    assert done.returncode == 0, f"register commit exited {done.returncode}: {done.stderr}"
    assert re.fullmatch(r"committed [0-9]+\n", done.stdout), done.stdout
    assert taken not in reg.open_landings(), (
        f"main_slots still holds the LANDING for {RULE6_KEY}: {reg.open_landings()}")



# ============================================================ (h), T279's
#
# AT-F13 (h), RE, end to end, with its rollback in phase G (B15 tasks:2557,
# T279's "AT-F13 (h): a `LANDING EXPIRED` on primary frees `main` and
# `who_landing` until a rollback to files"). Its fixture is (h) to (j)'s
# (TP's AT-F13 "Fixture"): `tmpl_imported` brought to `primary` with the
# marker `present`, and lane B's `LANDING` dated 31 minutes or more back.


def _commit_line(reg: Register, clock: int, lane: str, text: str) -> int:
    """`text` appended to `lanes/LANES.md` by one commit call as lane `lane`,
    in (i)'s form: the entry an `append-line` would send, with the line's
    `register_lines` row by the checkout's own classifier. The seq it made."""
    before = reg.rows("SELECT text FROM doc_lines WHERE path = 'lanes/LANES.md' ORDER BY line_no")
    lines = [r["text"] for r in before] + [text]
    rendered = ("\n".join(lines) + "\n").encode("utf-8")
    return reg.commit(reg.entry(
        "write", "append-line", lane,
        journal={"args_sha256": hashlib.sha256(text.encode()).hexdigest()},
        edits=[{"ord": 1, "op": "append", "path": "lanes/LANES.md", "new_text": text}],
        files=[{"path": "lanes/LANES.md", "present": True, "final_newline": True,
                "sha256": hashlib.sha256(rendered).hexdigest()}],
        register_lines=line_rows([text], clock, {ALIAS: KEY, KEY.lower(): KEY},
                                 first_line=len(lines))))


def _to_primary_with_the_marker(reg: Register, checkout: Path, env: dict) -> int:
    """AT-LR006's route, as `Register.to_primary` takes it, with the marker
    on origin as T327's push leaves it: the `cutover` entry, then a commit on
    origin's `main` that adds `lanes/STORE` with the entry's text and
    carries its `Register-Seq`, then `record_marker` naming that commit.
    Returns the entry's seq."""
    store = "store=primary\n"
    cut = reg.commit(reg.entry("cutover", "cutover", OPERATOR,
                               edits=[{"ord": 1, "op": "create", "path": "lanes/STORE"},
                                      {"ord": 2, "op": "append", "path": "lanes/STORE",
                                       "new_text": "store=primary"}],
                               files=[{"path": "lanes/STORE", "present": True,
                                       "final_newline": True,
                                       "sha256": hashlib.sha256(store.encode()).hexdigest()}]))
    (checkout / "lanes" / "STORE").write_bytes(store.encode("utf-8"))
    git(checkout, "add", "lanes/STORE", env=env)
    git(checkout, "commit", "-q", "-m", f"cutover: the marker (T279's estate)\n\nRegister-Seq: {cut}",
        env=env)
    git(checkout, "push", "-q", "origin", "HEAD:main", env=env)
    marker = git(checkout, "rev-parse", "HEAD", env=env).strip()
    version = reg.rows("SELECT version FROM schema_version")[0]["version"]
    marked = reg.call(f"SELECT {SCHEMA}.record_marker({version}, {cut}, '{marker}', '{WS}');\n")
    assert (marked.returncode, marked.stdout.strip()) == (0, "present"), marked.stderr
    return cut


def test_a_landing_expired_on_primary_frees_main_and_who_landing_until_a_rollback_to_files(
        registers, pg_cluster, tmp_path):
    """(h), RE, end to end (TP's AT-F13 oracle (h)). On a clone of
    `tmpl_imported` brought to `primary` with the marker `present`, lane B's
    (`HOLDER`'s) `LANDING`, 31 minutes back by the database's clock, is
    committed; then lane A's (`WRITER`'s) form, `append-line
    --landing-expired`, commits over it and exits 0. Then:
    - `main_slots` no longer shows lane B's `LANDING` as a take for its
      `repo_key`;
    - no other take on it being open, a later `LANDING` by lane C (`OTHER`)
      is accepted, not refused by D18;
    - on primary `who --landing` no longer lists lane B's `LANDING`, and
      lists lane C's;
    - after a rollback to files, `who --landing` lists lane B's `LANDING`
      again, marked STALE: off primary Rule 6's program is the pin, with no
      expired branch.

    READINGS:
    - "THE MARKER `present`" is read as both its halves: the switch's
      marker `present`, and `lanes/STORE` on origin. So the workstation's
      origin is a copy of the repository `tmpl_imported` was imported from
      (`pg_cluster.imported_register`, whose C the import's entry names),
      and AT-LR006's route pushes the cutover's marker commit there, with
      the entry's `Register-Seq`, before `record_marker` names it, as T327's
      push would. A rollback needs that origin: it renders onto the mirror
      of this database and removes `lanes/STORE` from it (T326).
    - Lane B's and lane C's `LANDING`s are committed as (i) commits its
      lines: one commit call each, the entry `append-line` would send.
    - "A ROLLBACK TO FILES" is `lanes-index rollback` as the operator lane,
      through that lane's own register checkout, `<W>-lanes/<operator>`,
      which `LANES_REPO` names, never W (D24); then `set-mode index` on this
      workstation, as Brett runs it at the rollback's step 5 (operations.md
      2.3), so `who --landing` reads the files: origin's `main` as the
      rollback rendered it, after the harness's fetch of W (lane 3's ruling
      (a), #165 6833830078), since the rollback pushed from the operator
      lane's checkout.

    Fails until lane 1's T107, T111 and T112 (F13 and D18 in the commit),
    lane 4's T415 and T425 (L4-B10: the form and `RULE6_EXPIRED_AWK`), lane
    5's T504 (the prefetch), and the rollback's T304 and T326 (L1-A18 for
    its declaration)."""
    reg = registers("tmpl_imported")
    source = pg_cluster.imported_register
    assert source is not None, f"no repository for tmpl_imported: {pg_cluster.imported_problem}"
    origin, checkout, env = _workspace(tmp_path / "ws", tmp_path / "fakebin", {},
                                       source=source.origin, lanes=())
    _to_primary_with_the_marker(reg, checkout, env)
    _lane_checkouts(origin, checkout, env)  # after the marker's push, at W's commit (119)
    clock = reg.clock()
    _commit_line(reg, clock, HOLDER, _shift(landing(minutes=31), clock))
    taken = (HOLDER, str(PR), KEY)
    assert taken in reg.open_landings(), (
        f"lane B's LANDING does not take main for {KEY}: {reg.open_landings()}")

    bindir = tmp_path / "bin"
    copy = flipped_copy(LANES_INDEX, bindir, True)
    for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
        shutil.copy2(str(REPO / name), str(bindir / name))
    conf = tmp_path / "conf" / "lanes-index.conf"
    conf.parent.mkdir()
    conf.write_text(f"mode=primary\nregister_url={reg.db.url(WRITER_LOGIN)}\n"
                    f"reader_url={reg.db.url()}\nregister_label={pg_cluster.label}\n",
                    encoding="utf-8")
    conf.chmod(0o600)
    env.update(LANES_INDEX_CONFIG=str(conf), PATH=str(reg.cluster.bindir) + os.pathsep + env["PATH"])
    env.pop("LANES_INDEX", None)

    def run(argv: list, lane: str = None, repo: Path = None) -> subprocess.CompletedProcess:
        child = dict(env)
        if lane:
            child.update(LANES_LANE=lane, LANES_SESSION=SESSIONS.get(lane, SID_W))
        if repo is not None:
            child["LANES_REPO"] = str(repo)
        return subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace",
                              env=child, timeout=300, cwd=str(checkout), check=False,
                              stdin=subprocess.DEVNULL)

    def who() -> list:
        proc = run(["bash", str(bindir / "lanes-edit.sh"), "who", "--landing", KEY])
        assert proc.returncode == 0, f"who --landing exited {proc.returncode}: {proc.stderr[-800:]}"
        return [line for line in proc.stdout.splitlines() if line.startswith("LANDING  ")]

    released = run(["bash", str(bindir / "lanes-edit.sh"), *form()], lane=WRITER)
    assert released.returncode == 0, (
        f"lane A's form exited {released.returncode} (L4-B10, T425's form; T415): "
        f"{released.stderr[-800:]}")
    assert taken not in reg.open_landings(), (
        f"main_slots still holds lane B's LANDING for {KEY}: {reg.open_landings()}")
    try:
        _commit_line(reg, clock, OTHER, _shift(landing(lane=OTHER, minutes=1), clock))
    except AssertionError as exc:
        raise AssertionError(f"lane C's later LANDING on {KEY} was refused, though no take on "
                             f"it is open (D18): {exc}") from None
    assert (OTHER, str(PR), KEY) in reg.open_landings(), reg.open_landings()
    rows = who()
    assert not any(f"  lane {HOLDER}," in row for row in rows), (
        f"on primary who --landing still lists lane B's released LANDING (T425's "
        f"RULE6_EXPIRED_AWK): {rows}")
    assert any(f"  lane {OTHER}," in row for row in rows), (
        f"on primary who --landing does not list lane C's LANDING: {rows}")

    # THE OPERATOR LANE'S OWN REGISTER CHECKOUT (D24; Amendment 23 S2 item 3):
    # the rollback reads origin through it, never W, and refuses 2 where
    # `LANES_REPO` names W itself (`lanes-index:19061-19106` at pair-m33a
    # `8ba10b4e`, `lane_own_checkout`). `<W>-lanes/<operator>`, a clone of
    # origin made after the case's last write, as T272d makes the cutover
    # module's and T254s the guard module's; `LANES_REPO` names it for the
    # rollback alone.
    (operator_checkout,) = _lane_checkouts(origin, checkout, env, lanes=(OPERATOR,))
    rolled = run([sys.executable, str(copy), "rollback"], lane=OPERATOR, repo=operator_checkout)
    assert rolled.returncode == 0, (
        f"the rollback to files exited {rolled.returncode} (T304, T326): {rolled.stderr[-800:]}")
    flipped = run([sys.executable, str(copy), "set-mode", "index"])
    assert flipped.returncode == 0, f"set-mode index exited {flipped.returncode}: {flipped.stderr}"
    # THE READER'S FETCH OF W (lane 3's ruling (a), #165 6833830078; T272e's
    # `fetch_w`): the rollback pushed from the operator lane's checkout, so
    # W's `origin/main`, which `who` reads off primary (`register_text`) and
    # whose `lanes/STORE` F17 checks as last fetched, moves only by a fetch.
    git(checkout, "fetch", "-q", "origin", "main", env=env)
    rows = who()
    held = [row for row in rows if f"  lane {HOLDER}," in row]
    assert held and all(row.endswith(STALE_MARK) for row in held), (
        f"after the rollback to files who --landing does not list lane B's LANDING again, "
        f"marked STALE: {rows}")
