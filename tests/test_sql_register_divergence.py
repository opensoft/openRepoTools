# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 6, a stray commit and its two ways out, with AT-MIR's
gating case and the model of the server-side gate (L2-G2; L2-G5's AT-MIR
gating case; AT-6; AT-MIR; T271; FR-047, FR-048, FR-059; US6)
(opensoft/openRepoTools#165).

T271 writes this module: 11 tests, 10 from AT-6 (9) and AT-MIR (1), and one
new since v3f, R-F10-34's, which holds lane 3's two strays for T324,
R-F13c-10's third id and, new in B15, lane 3's L2-8 fourth,
`[stray-no-longer-applies]`. Lane 3's T324 runs the whole module by its
word, `sql_register_divergence`.

THE V1.1.0 WRITER (PC-12; the test plan's open point 5).
`tests/fixtures/lanes-edit-v1.1.0/lanes-edit.sh` is `lanes-edit.sh` byte for
byte as code `2a057a6d` (tag `v1.1.0`) holds it: blob `d28ed8f2`, 1139720
bytes. CI checks out at depth 1 with no tags, so the copy is the only way the
suite runs the real old writer. Its digest is recorded twice: in
`tests/fixtures/lanes-edit-v1.1.0/SHA256SUMS`, in `sha256sum`'s form, and in
this module's `V110_SHA256`, beside its git blob id and size. Every case that
runs it calls `v1_1_0_writer()` first, which checks all four, so a drift in
the fixture fails loudly instead of testing something else (AT-6,
"Flakiness"). The copy is never run from its own directory's neighbours: no
`lanes-index` and no `repos.tsv` sit beside it, and the stale clone's `PATH`
masks `lanes-index`, so it makes no index nudge.

THE ESTATE (AT-6, "Fixture"), `Estate`, built inside each case so that a
step a lane has not built fails the case at its own assertion:

- the fixture register at C: a files-mode workspace on a bare origin
  (`Workspace`), its seed `SEED`, and a files-mode `log NOTED` on top as the
  operator lane, so C's tip is bytes `lanes-edit.sh` wrote, as test 7's
  fixture register is built;
- imported on `pg` by `lanes-index import --at <C>` (lane 1's T115), as the
  operator lane through its checkout;
- the cutover by AT-LR006's route (TP:4610-4615): `commit_write` with a
  `cutover` entry, as REGISTER-WRITER, then the marker commit, `lanes/STORE`
  with D21's fields and `Register-Seq: 1`, pushed to the bare origin as a
  fast-forward of C, then `record_marker`, so the switch reads `primary`
  with the marker `present`. Neither T116 nor T327 is in T271's Order, so the
  estate runs neither `cutover` nor its push;
- each primary write is a `commit_write` call of a `write` entry, as
  REGISTER-WRITER (AT-LR006's "one write"), that appends a line of no kind to
  `lanes/LANES.md`, so it carries no structured row; and each render a fork
  would start is `lanes-index render --checkout <c>` run by the case, as a
  fork runs it (TP:1160-1167), in the operator lane's checkout. Lane 4's
  writes on primary and their fork (T415, T416) are not in T271's Order.

The commands run from the operator lane's checkout, `LANES_LANE=repoA-2`, by
T203's flipped copy of `lanes-index` (`RENDER_GIT_HALF = True`), which the
renderer and the two ways out need on `lanes_register`; `import --at` runs the
shipped `lanes-index`, as test 7's does. Their configuration names the
session cluster's socket as its superuser, as test 7's does.

THE STALE WORKSTATION (AT-6, "Fixture"), `StaleWorkstation`: a clone of
origin with a home, a workspace pointer and a lane of its own (`repoW-1`), no
`lanes-index` configuration, and the v1.1.0 writer. Its `log NOTED` pushes a
commit changing `lanes/log/repoW-1.md`; it knows no marker.

THE WAITS (open point 8). The stop is read after the renderer's exit: the
case runs the render itself, in the foreground, so its exit is the wait.
Where the lag must reach 0, the case polls `lanes-index status` every 100 ms
until it prints a lag of 0, with a 30 s ceiling, after a render of its own;
a render a way out forks itself is the same render lock's, so the case's own
render then marks a rerun and the poll waits for both.

THE GATE MODEL (AT-6, "Options", Q21(b)): `GATE_HOOK`, a pre-receive hook in
the bare origin, refuses a push whose commits change a path of the render
set or `lanes/STORE` (`lanes/LANES.md`, `lanes/log/<lane>.md`,
`lanes/aliases.tsv`, anything under `lanes/archive/`, and `lanes/STORE`), and
lets every other path through, `lanes/repos.tsv` and `lanes/log/README.md`
among them. It is a model: the suite cannot reach GitHub. Its two tests need
no engine.

WHAT EACH FAILS UNTIL (T271's Order, B15 tasks:2487): it waits for T205,
and its tests fail until L1-A6, L1-A15, T322, T324 and T326 land. Case by
case: the estate needs lane 1's T107 (`commit_write`, `record_marker`,
`record_mirror_state`; L1-A6) and T115 (`import --at`, L1-A13), and each
case reads `status` (T117, L1-A15) and runs the renderer's pass (lane 3's
T321 to T323). Then:

- the stop, the row's two ids and the three commits outside the render set
  fail until those alone;
- `test_status_prints_diverged_at_the_stray_sha_and_reconcile_imports_nothing`
  also fails until T325, whose re-render gives `reconcile` the renderer's 1
  for a recorded `diverged at`, where T117's check alone, like `--dry-run`,
  exits 0 (lane 3, #165 6809045090, L2-6);
- the two ways out, the strays and the `Register-Seq` above the head fail
  until T324 too;
- `test_rollback_works_after_each_way_out` and the `Register-Seq` case's last
  part fail until T326 (the rollback's render and push);
- `[stray-revives-a-pair]` fails until T324's refusal and T107's
  `one_live_claim`; `[stray-no-longer-applies]` also fails until T324's
  `import --single` refusal (lane 3, #165 6809045090, L2-8); the other two
  strays' oracle needs T115's `import --at`;
- the gate model's seven ids wait for nothing: they test the model and the
  pinned copy, and pass now.

COPIED, NOT SHARED (lane 2's rule for wave 12: no module imports another's
helpers). From `test_sql_register_import.py` (line W3a at T211m, `c9989b5`):
`Workspace`, the fixture register's `config` and `import_at`,
`flipped_indexer`, `_rows`, `_renders`, `RENDER_SET`, `REGISTER_SEQ` and
`LAG_0`. From `test_sql_register_landing_expired.py` (line LX at T253e,
`e9b949e`): `_masked_path`, with its mirrors. From
`test_sql_register_schema.py` (line W3b at T221j, `0154c91`): `STRUCTURED`
and `structured`, T221's step-6 comparison, and the commit call's form. From
`test_sql_register_rollback.py` (line RB at T273b, `35b616ff`): test 8's first
oracle, `_assert_rolled_back`, and `_said`.

READINGS, NOT FOUND IN A CONTRACT:

- "A later primary write still commits to SQL" is a `commit_write` of a
  `write` entry that returns the next seq while `diverged at` is recorded.
- "SQL writes refused", in test 8's first oracle, is `commit_write`'s LR002
  for a `write` entry once the switch reads `files`, with the head unmoved.
- "Its line edits equal the stray commit's diff": the v1.1.0 writer's stray
  appends lines to one log, so the entry's edits are one `append` per added
  line, in order, on that path.
- A revert's message "names" the stray where it holds the stray's first 7
  hex digits, git's shortest abbreviation, or more; its `git_commit` is the
  full sha (design.md's kinds paragraph).
- "Its render commit puts SQL's state back over the stray" is read over the
  render commits that follow the stray up to the revert's seq: a write that
  lands between the stray and the revert is rendered first and already puts
  the stray's path back (design.md's prototype note on the import), so on
  each path the stray changed, the tip after the resume equals the stray's
  parent.
- "The pending seqs reach origin in order": the `Register-Seq` values of the
  commits after the stray, oldest first, are each seq from `m+1` to the head,
  once each.
- "Between renders": the `repos.tsv` and `handoffs/` commits land after a
  render of their own estate's first write; the cutover's `lanes/STORE`
  commit is origin's tip when the first render starts.
- The negative and the row-only cases' "status shows no divergence" is
  `status`'s `divergence:  none recorded` line, where the row is empty.
- `[stray-revives-a-pair]`'s "writes nothing" also leaves `mirror_state`
  recording the stray.
- `[stray-no-longer-applies]`'s "a primary write changes a line after the
  stray commit changed it": the stray retitles `lanes/LANES.md`'s first
  line, its heading, a line of no kind, by hand; then a `commit_write` of a
  `write` entry replaces the same line in SQL with other text, by its old
  text's digest. So the stray's one edit, a `replace` at line 1, finds there
  a line its parent never held.
- Its "sends no commit call" is read through a `psql` first on the import's
  `PATH` that logs each call's stdin, where `lanes-index` sends each request:
  no request holds `commit_write(`, and at least one was sent, since the
  refusal reads SQL's images. Its "naming the edit" is stderr naming the
  edit's path and that its edits "no longer apply" (TP:1292). Its "writes
  nothing" is the head, the journal's count, the four structured tables and
  SQL's images as they were, `mirror_state` still recording the stray, and
  origin's tip still the stray.
- The ways out run "on a person's word from the operator lane's checkout"
  (TP:1276-1277), where that person's git names an author: the checkout's
  own `user.name` and `user.email` name `AUTHOR`, set once C is made. A way
  out removes every inherited `GIT_*` variable before it asks git (D12), so
  the module's `GIT_AUTHOR_*` variables, which still sign the estate's own
  commits, cannot name it; T324 as built refuses with 2 where git names no
  author there.
- The stale clone's `sleep` is a stub that returns at once, so the v1.1.0
  writer's six push attempts, three seconds apart, take no time; what it
  does at each attempt is unchanged.

RULED BY LANE 3 (#165 6809045090; its RULINGS-batch-e-analysis-20261111.md,
L2-6 to L2-8; B15 folds them):

- L2-6: AT-6's stop stands (TP:1285): `reconcile` exits non-zero on a
  diverged mirror once T325 lands. T325 re-renders what the mirror lacks
  through T322's pass, and the pass's recorded stop, `diverged at` among
  them, is the renderer's 1 (exit-codes.md section 3.4's `reconcile` 1
  row). T117's check alone, like `reconcile --dry-run`, exits 0 whatever it
  found. So the status case asserts 1, the code the contract names, and
  fails until T325.
- L2-7: T117 is right. With `m` above the head there is no lag (Y:2850):
  until a revert names `R`, its `Register-Seq` counts, so `m` = `h`+10 is
  past `n` = `h`+1, and `status` prints the lag as "none, and the mirror's
  <m> is past n <n>" (TP:1319 at B15: "no lag: its `m` is past `n`
  (Y:2850), as `status` says"). The `Register-Seq` case asserts that line,
  naming `h`+10 and `h`+1. The plain stray's "a lag of at least 1"
  (TP:1284) stands: that stray carries no `Register-Seq`.
- L2-8: AT-6's "case of its own", the import's refusal where the stray's
  edits no longer apply to SQL's images (TP:1292-1293), is
  `[stray-no-longer-applies]`, a fourth id of the strays' function beside
  `[stray-revives-a-pair]`, whose LR005 is the other refusal: `import
  --single` refuses with 2 before any commit call, naming `render --revert
  <sha>` as the way out (PC-4; T324 `9a664ef`:16115-16117), writes nothing,
  and leaves the tables unchanged (B15 tasks:2486). It fails until T324's
  refusal.
"""

from __future__ import annotations

import atexit
import base64
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from pgcluster import Database

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

# ------------------------------------------------------------------ the landing gate
#: THE LANDING GATE'S TABLE (T280; task sets version 12b's rule 11,
#: opensoft/openRepoTools#165 6877673742), read by `tests/sql_register_gate.py`.
#: Where the gate is active, an id whose tasks have not all landed is skipped,
#: and the skip names them; an id waits for the `"*"` row and its own. T281
#: removes this block in the last set. It is T271's Order (tasks:2489 at lane
#: 3's commit 17, 204145ae), as lane 2's plan GP-24 keys it (sha256 16d738b9):
#:
#: - `"*"`: the module's tests fail until L1-A6 (T107, T108), L1-A15 (T117),
#:   T322, T324 and T326. The gate model's seven ids need none of them (their
#:   docstrings: "waits for nothing"), but the Order names the module's tests
#:   whole, so `"*"` holds them too;
#: - the status case also fails until T325 (lane 3's L2-6): its own row;
#: - `[stray-no-longer-applies]`'s T324, and `[stray-revives-a-pair]`'s T324
#:   and T107, are in `"*"` already. The two other strays' T115 (L1-A13) has
#:   no row: it lands in an earlier set than T326, so a row would hold no id
#:   longer.
SQL_REGISTER_GATE_TABLE = {
    "*": ("T107", "T108", "T117", "T322", "T324", "T326"),
    "test_status_prints_diverged_at_the_stray_sha_and_reconcile_imports_nothing": ("T325",),
}

LANES_EDIT = REPO / "lanes-edit.sh"
INDEXER = REPO / "lanes-index"

# ------------------------------------------------------------------ the v1.1.0 writer
#: PC-12's copy and its pin (see the module's docstring).
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "lanes-edit-v1.1.0"
V110 = FIXTURE_DIR / "lanes-edit.sh"
V110_SUMS = FIXTURE_DIR / "SHA256SUMS"
V110_COMMIT = "2a057a6d84e58c8acb4bda20d2b7b667b552c3fe"
V110_BLOB = "d28ed8f2d18adcabc4483eaf2a9424410e288cc6"
V110_SHA256 = "b68d0cbac35ac3bbac9e70790cafe63538821be582ca28cec0f7ec0f5c4745d2"
V110_SIZE = 1139720


def v1_1_0_writer() -> Path:
    """The pinned v1.1.0 `lanes-edit.sh`, once its bytes are proved: its
    size, its sha256 against this module's pin and against `SHA256SUMS`, and
    its git blob id against the tag's. Any drift fails here, loudly."""
    assert V110.is_file(), f"PC-12's copy of the v1.1.0 writer is missing: {V110}"
    data = V110.read_bytes()
    sums = V110_SUMS.read_text(encoding="ascii") if V110_SUMS.is_file() else None
    assert sums == f"{V110_SHA256}  lanes-edit.sh\n", (
        f"{V110_SUMS} does not record the pinned digest {V110_SHA256} (PC-12): {sums!r}")
    got = (len(data), hashlib.sha256(data).hexdigest(),
           hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest())
    assert got == (V110_SIZE, V110_SHA256, V110_BLOB), (
        f"{V110} is not lanes-edit.sh as v1.1.0 ({V110_COMMIT[:8]}) holds it: size, sha256 and "
        f"blob {got}, pinned {(V110_SIZE, V110_SHA256, V110_BLOB)}. The fixture drifted, so "
        f"test 6 would test something else (PC-12; open point 5)")
    return V110


# ------------------------------------------------------------------ the register
EM, DOT, ARROW = chr(0x2014), chr(0xB7), chr(0x2192)

#: The register's schema, `register_schema=`'s default, and the writer's group.
SCHEMA = "lanes_register"
WRITER = "lanes_register_writer"
#: The operator lane (lane 1's T115: "It runs with `LANES_LANE=<operator
#: lane>`, through that lane's checkout"), its workstation and git's author.
OPERATOR = "repoA-2"
WS = "Eagle"
AUTHOR_NAME, AUTHOR_EMAIL = "T271 operator", "t271@example.invalid"
AUTHOR = f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>"
#: The label the configuration's `register_label=` and `lanes/STORE` carry.
LABEL = "t271"
#: The stale workstation's lane and name.
STALE_LANE = "repoW-1"
STALE_WS = "Stale"

ARGS_SHA256 = "a" * 64
NOT_AFTER = "2100-01-01T00:00:00Z"
STORE_UTC = "2026-11-11T10:00:00Z"

UUID_A2 = "aaaaaaaa-0003-4000-8000-00000000a003"
UUID_D1 = "dddddddd-0002-4000-8000-00000000d002"
UUID_I1 = "11111111-0001-4000-8000-000000001001"
UUID_W1 = "eeeeeeee-0002-4000-8000-00000000e002"
UUID_X1 = "cccccccc-0001-4000-8000-00000000c001"
UUID_Y1 = "cccccccc-0002-4000-8000-00000000c002"
UUID_Z1 = "eeeeeeee-0001-4000-8000-00000000e001"

#: The object two lanes held, one after the other: repoX-1 claimed and
#: released it, then repoY-1 claimed it. One claim is live at C, so the
#: import marks no pair `exempt`.
PAIR_OBJECT = "opensoft/repoQ#1"


def _row(lane: str, uid: str, state: str) -> str:
    return (f"| `{lane}` | harness `{uid}` | Eagle / test / brett | 2026-10-01T00:00Z | none | "
            f"handoffs/{lane}.md | {state} |")


def _started(lane: str, uid: str, home: str, utc: str = "2026-10-01T00:00:00Z") -> str:
    return (f"STARTED {EM} lane {lane}, session {uid}@Eagle, {utc}, lane:{lane} {ARROW} home "
            f"{home}; dir /work/{lane}")


def _line(verb: str, lane: str, uid: str, utc: str, obj: str, text: str) -> str:
    return f"{verb} {EM} lane {lane}, session {uid}@Eagle, {utc}, {obj} {EM} {text}"


def _log(lane: str, *lines: str) -> str:
    return "\n".join([f"# lane {lane} {EM} object log (lane-collision-protocol Amendment 7)",
                      *lines, ""])


#: The row the first stray deletes, with no archive copy.
ROW_D = _row("repoD-1", UUID_D1, f"PAUSED {DOT} 2026-10-02T00:00:00Z {DOT} a row a stray deletes")
#: The release the third stray deletes, which revives repoX-1's claim.
RELEASED_X = _line("RELEASED", "repoX-1", UUID_X1, "2026-10-01T03:00:00Z", PAIR_OBJECT,
                   "handed back")
#: The line the second stray inserts before its log's end.
INSERTED_I = _line("NOTED", "repoI-1", UUID_I1, "2026-10-03T00:00:00Z", "lane:repoI-1",
                   "a line a person inserted by hand")
#: `lanes/LANES.md`'s first line, a heading of no kind. The fourth stray
#: retitles it by hand, then a primary write retitles it in SQL (L2-8).
TITLE = f"# LANES.md {EM} test 6's register"
TITLE_BY_HAND = TITLE + ", retitled by hand"
TITLE_IN_SQL = TITLE + ", retitled by a primary write"

#: C's files, before the `lanes-edit.sh` write on top. `lanes/repos.tsv` and
#: `lanes/log/README.md` are outside the render set (Q18 (A)).
SEED = {
    "lanes/LANES.md": "\n".join([
        TITLE,
        "",
        "| lane | session id | workstation / env / user | started (UTC) | objects owned | "
        "handoff path | state |",
        "|---|---|---|---|---|---|---|",
        _row("repoA-2", UUID_A2, f"LIVE {DOT} 2026-10-01T02:00:00Z {DOT} the operator lane"),
        _row("repoW-1", UUID_W1, f"LIVE {DOT} 2026-10-02T00:00:00Z {DOT} the stale workstation"),
        _row("repoX-1", UUID_X1, f"LIVE {DOT} 2026-10-01T00:00:00Z {DOT} it released repoQ#1"),
        _row("repoY-1", UUID_Y1, f"LIVE {DOT} 2026-10-01T00:00:00Z {DOT} it holds repoQ#1"),
        ROW_D,
        _row("repoI-1", UUID_I1, f"LIVE {DOT} 2026-10-01T00:00:00Z {DOT} a log with claims"),
        "",
    ]),
    "lanes/log/README.md": "# the object logs\n",
    "lanes/repos.tsv": "# alias\towner/repo\nrepoE\topensoft/repoE\n",
    "lanes/aliases.tsv": "# old\tnew\tutc\nrepoOld-1\trepoA-2\t2026-09-30T00:00:00Z\n",
    "lanes/archive/LANES-retired.md": "\n".join([
        "# retired rows (Amendment 19(d))", "",
        _row("repoZ-1", UUID_Z1, f"RETIRED {DOT} 2026-09-02T00:00:00Z {DOT} retired"), ""]),
    "lanes/log/repoA-2.md": _log("repoA-2", _started("repoA-2", UUID_A2, "opensoft/repoA")),
    "lanes/log/repoW-1.md": _log("repoW-1", _started("repoW-1", UUID_W1, "opensoft/repoW")),
    "lanes/log/repoX-1.md": _log(
        "repoX-1", _started("repoX-1", UUID_X1, "opensoft/repoQ"),
        _line("CLAIMED", "repoX-1", UUID_X1, "2026-10-01T01:00:00Z", PAIR_OBJECT, "mine"),
        RELEASED_X),
    "lanes/log/repoY-1.md": _log(
        "repoY-1", _started("repoY-1", UUID_Y1, "opensoft/repoQ"),
        _line("CLAIMED", "repoY-1", UUID_Y1, "2026-10-01T04:00:00Z", PAIR_OBJECT,
              "after repoX-1 let it go")),
    "lanes/log/repoI-1.md": _log(
        "repoI-1", _started("repoI-1", UUID_I1, "opensoft/repoI"),
        _line("CLAIMED", "repoI-1", UUID_I1, "2026-10-01T01:00:00Z", "opensoft/repoI#1", "one"),
        _line("CLAIMED", "repoI-1", UUID_I1, "2026-10-01T01:10:00Z", "opensoft/repoI#2", "two"),
        _line("OPENED", "repoI-1", UUID_I1, "2026-10-01T01:20:00Z", "opensoft/repoI#3",
              "three")),
}

#: The render set (Q18 (A); CLI4.10 section 3.6): `lanes/LANES.md`,
#: `lanes/aliases.tsv`, each `lanes/log/<lane>.md` but the README, and the
#: archive. `lanes/STORE` is the marker, never rendered.
RENDER_SET = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|archive/[^/]+\.md"
                        r"|log/(?!README\.md$)[^/]+\.md)$")
#: The trailer each mirror commit and the marker commit carry (section 1.3).
REGISTER_SEQ = re.compile(r"^Register-Seq: ([0-9]+)$", re.M)
#: `status`'s lag line (lane 1's T117): at 0, and as a number of seqs.
LAG_0 = re.compile(r"^\s*lag:\s+0 seq", re.M)
LAG_N = re.compile(r"^\s*lag:\s+([0-9]+) seq", re.M)
#: ... and with `m` above `n` at `primary`, no lag (R2's N6; Y:2850; lane 3's
#: L2-7): "none, and the mirror's <m> is past n <n>".
LAG_PAST_N = re.compile(r"^\s*lag:\s+none\b[^\n]*?\b([0-9]+) is past n ([0-9]+)", re.M)
NO_DIVERGENCE = re.compile(r"^\s*divergence:\s+none recorded", re.M)


def _said(proc) -> str:
    return (f"exit {proc.returncode}\n--- stdout ---\n{(proc.stdout or '')[-3000:]}"
            f"\n--- stderr ---\n{(proc.stderr or '')[-3000:]}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ the PATH mask
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
    `bash` (and `/bin` is a link to it), so dropping the directory would drop
    `git` and `bash` too (lane 1's census, #165 6807454856). A directory that
    holds none of those names passes through unchanged. Each mirror is made
    once per process, under one `mkdtemp` that an `atexit` handler removes.
    The estate's commands reach the session cluster's `psql` through a
    directory of their own, first on their `PATH`."""
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


def _script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _logging_psql(directory: Path, real: str, log: Path) -> Path:
    """A directory for the front of one command's `PATH`, holding a `psql`
    that appends `--- psql <its argv>` and then its stdin to `log` as it
    streams them, through `tee`, to the real `psql` at `real`, whose exit it
    keeps. `lanes-index` sends each request as one `psql` call with its SQL on
    stdin, so `log` holds every request the command sent."""
    _script(directory / "psql", "#!/bin/sh\n"
            f"printf '%s\\n' \"--- psql $*\" >> {shlex.quote(str(log))}\n"
            f"tee -a {shlex.quote(str(log))} | {shlex.quote(str(real))} \"$@\"\n")
    return directory


# ------------------------------------------------------------------ the workspace
class Workspace:
    """A whole files-mode workspace in `root`: a bare origin, its clone, the
    pointer file that joins them (Amendment 23 S5's view of the clone), a
    fake `tmux`, and the environment every command here runs in. With
    `files`, a new origin is made and `files` committed and pushed by git
    alone; with `origin`, that origin is cloned as it stands."""

    def __init__(self, root: Path, files: dict | None = None, *, origin: Path | None = None,
                 lane: str = OPERATOR, workstation: str = WS):
        self.root = root
        self.home = root / "home"
        self.agents = self.home / ".agents"
        self.origin = origin or root / "origin.git"
        self.wip = self.home / "projects" / "wip"
        self.fakebin = root / "fakebin"
        self.conf = root / "conf"
        for d in (self.home, self.agents, self.fakebin, self.conf, root / "state",
                  root / "config", root / "tmp"):
            d.mkdir(parents=True, exist_ok=True)
        _script(self.fakebin / "tmux", "#!/bin/sh\nexit 1\n")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("LANES_", "CLAUDE_", "WORKBENCHES_", "TMUX", "XDG_", "PG",
                                    "AGENT_PROTOCOL_ROOT", "PROJECTS_", "GIT_"))}
        env.update(
            HOME=str(self.home), AGENT_PROTOCOL_ROOT=str(self.agents), TMPDIR=str(root / "tmp"),
            XDG_STATE_HOME=str(root / "state"), XDG_CONFIG_HOME=str(root / "config"),
            CLAUDE_CONFIG_DIR=str(self.home / ".claude"), LANES_WORKSTATION=workstation,
            LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none",
            LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1", LANES_EDIT=str(LANES_EDIT),
            GIT_AUTHOR_NAME="lanes-index tests", GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_NAME="lanes-index tests", GIT_COMMITTER_EMAIL="test@example.invalid",
            PATH=str(self.fakebin) + os.pathsep + _masked_path())
        self.env = env
        if origin is None:
            subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)],
                           check=True, env=self.env, capture_output=True)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.wip)],
                       check=True, env=self.env, capture_output=True)
        if files:
            self.commit(files, "seed the register")
        self.ws = root / "ro" / "wip"
        self.ws.mkdir(parents=True)
        (self.ws / ".git").write_text(f"gitdir: {os.path.realpath(self.wip / '.git')}\n",
                                      encoding="utf-8")
        (self.ws / "lanes").symlink_to(self.wip / "lanes")
        (self.agents / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.ws}\n", encoding="utf-8")
        self.env["LANES_REPO"] = str(self.wip)
        self.lane = lane

    def git(self, *args: str, input_bytes: bytes | None = None, check: bool = True) -> str:
        proc = subprocess.run(["git", *args], cwd=str(self.wip), capture_output=True,
                              input=input_bytes, env=self.env, check=False)
        assert not check or proc.returncode == 0, (
            f"git {' '.join(args)}: {proc.stderr.decode(errors='replace')}")
        return proc.stdout.decode("utf-8", "replace")

    def commit(self, files: dict, message: str, *, push: bool = True) -> str:
        """Commit `files` ({path: str or bytes, or None to remove}) through
        git alone, push it unless told not to, and return the commit."""
        for path, text in files.items():
            if text is None:
                self.git("rm", "-q", "--cached", "--", path)
                continue
            data = text.encode("utf-8") if isinstance(text, str) else text
            sha = self.git("hash-object", "-w", "--stdin", input_bytes=data).strip()
            self.git("-c", "core.ignorecase=false", "update-index", "--add", "--cacheinfo",
                     f"100644,{sha},{path}")
        self.git("-c", "core.ignorecase=false", "commit", "-q", "-m", message)
        if push:
            self.git("push", "-q", "origin", "main")
        self.git("-c", "core.ignorecase=false", "checkout", "-q", "-f", "HEAD")
        return self.git("rev-parse", "HEAD").strip()

    def run(self, *argv, env: dict | None = None, timeout: float = 120,
            cwd: Path | None = None) -> subprocess.CompletedProcess:
        child = dict(self.env)
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True,
                              env=child, timeout=timeout, cwd=str(cwd or self.root),
                              stdin=subprocess.DEVNULL)

    def edit(self, *args, env: dict | None = None, **kw) -> subprocess.CompletedProcess:
        return self.run("bash", LANES_EDIT, *args, env=env, **kw)

    def tip(self) -> str:
        return self.git("rev-parse", "origin/main").strip()

    def tree(self, sha: str, path: str = "lanes") -> str:
        return self.git("rev-parse", f"{sha}:{path}").strip()

    # ------------------------------------------------------------ the bare origin
    def origin_git(self, *args: str) -> str:
        """git in the bare origin itself, so no clone's refs move."""
        proc = subprocess.run(["git", f"--git-dir={self.origin}", *args], capture_output=True,
                              env=self.env, check=False, stdin=subprocess.DEVNULL)
        assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr.decode(errors='replace')}"
        return proc.stdout.decode("utf-8", "replace")

    def origin_tip(self) -> str:
        return self.origin_git("rev-parse", "refs/heads/main").strip()

    def origin_blob(self, rev: str, path: str) -> bytes | None:
        proc = subprocess.run(["git", f"--git-dir={self.origin}", "cat-file", "blob",
                               f"{rev}:{path}"], capture_output=True, env=self.env,
                              check=False, stdin=subprocess.DEVNULL)
        return proc.stdout if proc.returncode == 0 else None

    def origin_changed(self, sha: str) -> list:
        """The paths `sha` changes against its first parent."""
        out = self.origin_git("diff-tree", "--root", "--no-commit-id", "-r", "--no-renames",
                              "--name-only", "-z", sha)
        return sorted(p for p in out.split("\0") if p)

    def origin_parent(self, sha: str) -> str:
        return self.origin_git("rev-parse", f"{sha}^").strip()

    def commits_after(self, since: str) -> list:
        """The commits on origin's `main` after `since`, oldest first, each
        with its `Register-Seq` values."""
        commits = self.origin_git("rev-list", "--reverse", f"{since}..refs/heads/main").split()
        return [(sha, [int(s) for s in REGISTER_SEQ.findall(
            self.origin_git("log", "-1", "--format=%B", sha))]) for sha in commits]

    def origin_render_set(self, rev: str) -> dict:
        """The render set at `rev` on origin, {path: bytes}."""
        paths = self.origin_git("ls-tree", "-r", "--name-only", "-z", rev, "--", "lanes/")
        return {p: self.origin_blob(rev, p) for p in paths.split("\0") if p and RENDER_SET.match(p)}


class StaleWorkstation(Workspace):
    """THE STALE WORKSTATION (AT-6, "Fixture"): a clone of `origin` with no
    `lanes-index` configuration, its own home and pointer, lane `STALE_LANE`,
    and the pinned v1.1.0 writer. `lanes-index` and `psql` are masked off its
    `PATH`, and its `sleep` returns at once (the module's readings)."""

    def __init__(self, root: Path, origin: Path):
        super().__init__(root, origin=origin, lane=STALE_LANE, workstation=STALE_WS)
        _script(self.fakebin / "sleep", "#!/bin/sh\nexit 0\n")
        self.env.update(LANES_LANE=STALE_LANE, GIT_AUTHOR_NAME="A stale workstation",
                        GIT_COMMITTER_NAME="A stale workstation")
        self.env.pop("LANES_EDIT", None)
        self.writer = v1_1_0_writer()

    def v110(self, *args, env: dict | None = None) -> subprocess.CompletedProcess:
        """The v1.1.0 `lanes-edit.sh`, run by `bash` in the stale clone."""
        return self.run("bash", self.writer, *args, env=env, cwd=self.wip, timeout=300)

    def note(self, text: str) -> subprocess.CompletedProcess:
        """`log NOTED`, AT-6's stale write: a commit changing the lane's log."""
        return self.v110("log", "NOTED", f"lane:{STALE_LANE}", text)

    def local_commit(self, path: str, text: str, message: str) -> str:
        """A person's commit in the stale clone, appending `text` to `path`,
        not pushed."""
        target = self.wip / path
        target.write_text(target.read_text(encoding="utf-8") + text, encoding="utf-8")
        self.git("add", "--", path)
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()


# ------------------------------------------------------------------ the gate model
#: AT-6'S MODEL OF Q21(b)'s PUSH RULESET (Brett's scope, "Render set +
#: STORE", lane 3's 6721583757), a pre-receive hook in the bare origin: it
#: refuses a push whose commits change a path of the render set or
#: `lanes/STORE`, and lets every other path through. Each push is one JSON
#: line of its log.
GATE_HOOK = r'''#!/usr/bin/env -S python3 -I
# T271's model of the server-side gate (test plan, AT-6, "Options"): a model,
# since the suite cannot reach GitHub.
import json, re, subprocess, sys
LOG = LOG_PATH
GUARDED = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|STORE|archive/.+"
                     r"|log/(?!README\.md$)[^/]+\.md)$")
ZERO = "0" * 40


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=True).stdout


def changed(old, new):
    revs = git("rev-list", new if old == ZERO else f"{old}..{new}").split()
    paths = set()
    for rev in revs:
        out = git("diff-tree", "--root", "--no-commit-id", "-r", "-m", "--no-renames",
                  "--name-only", "-z", rev)
        paths.update(p for p in out.split("\0") if p)
    return sorted(paths)


def main():
    pushes, refused = [], []
    for line in sys.stdin:
        old, new, ref = line.split()
        if new == ZERO:
            continue
        paths = changed(old, new)
        hits = [p for p in paths if GUARDED.match(p)]
        pushes.append({"ref": ref, "old": old, "new": new, "paths": paths, "guarded": hits})
        refused += hits
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"outcome": "refused" if refused else "accepted",
                                 "pushes": pushes}) + "\n")
    if refused:
        sys.stderr.write("t271 gate model: a push to the render set or lanes/STORE is "
                         "refused: " + ", ".join(sorted(set(refused))) + "\n")
        return 1
    return 0


sys.exit(main())
'''


class GatedOrigin(Workspace):
    """The gate model's register: the seed and a files-mode write, then
    `lanes/STORE` as the cutover's marker commit leaves it, on a bare origin
    that `GATE_HOOK` guards. No database: the model needs none."""

    def __init__(self, root: Path):
        super().__init__(root, SEED)
        proc = self.edit("log", "NOTED", f"lane:{OPERATOR}", "test 6's register, at C",
                         env={"LANES_LANE": OPERATOR})
        assert proc.returncode == 0, f"lanes-edit.sh log NOTED: {_said(proc)}"
        self.c = self.tip()
        self.marker = self.commit({"lanes/STORE": _store_text(LABEL, self.c, self.tree(self.c))},
                                  "cutover: lanes/STORE, the marker\n\nRegister-Seq: 1")
        self.gate_log = root / "gate.log"
        _script(self.origin / "hooks" / "pre-receive",
                GATE_HOOK.replace("LOG_PATH", repr(str(self.gate_log))))

    def gate_records(self) -> list:
        if not self.gate_log.exists():
            return []
        return [json.loads(line) for line in self.gate_log.read_text(encoding="utf-8").splitlines()
                if line]


# ------------------------------------------------------------------ the estate
def flipped_indexer(directory: Path) -> Path:
    """T203's flipped copy, `RENDER_GIT_HALF = True`, in `directory`, with
    `lanes-edit.sh` and `repos.tsv` beside it (the copy rule, CLI4.5 section
    6), so that the renderer and the two ways out take `lanes_register`."""
    from sql_register_helpers import RENDER_GIT_HALF_LINE, flipped_copy
    assert len(RENDER_GIT_HALF_LINE.findall(INDEXER.read_bytes())) == 1, (
        f"{INDEXER} holds no single `RENDER_GIT_HALF = ...` line, Q6(c)'s build constant "
        f"(L1-A4, lane 1's T105), so no copy can be flipped")
    copy = flipped_copy(INDEXER, directory, True)
    for name in ("lanes-edit.sh", "repos.tsv"):
        if (REPO / name).exists():
            shutil.copy2(REPO / name, copy.parent / name)
    return copy


def _store_text(label: str, c: str, tree: str) -> str:
    """`lanes/STORE` with D21's fields, one per line."""
    return "\n".join(_store_lines(label, c, tree)) + "\n"


def _store_lines(label: str, c: str, tree: str) -> list:
    return ["store=primary", f"database={label}", f"import={c}", f"lanes-tree={tree}",
            f"utc={STORE_UTC}"]


def _entry(kind: str, verb: str, message: str, **parts) -> dict:
    """One `commit_write` entry (section 1.3): the journal object,
    `not_after`, and `parts`."""
    journal = {"kind": kind, "verb": verb, "lane": OPERATOR, "workstation": WS,
               "author": AUTHOR, "message": message}
    journal.update(parts.pop("journal", {}))
    return {"journal": journal, "not_after": NOT_AFTER, **parts}


#: The four structured tables, each row keyed by its line's `(path, line_no)`
#: in place of a line id, without the columns a write stamps: the written seq,
#: the mode and the workstation (T221's step-6 comparison; lane 2's reading,
#: NOTES question 33).
STRUCTURED = {
    "lanes": f"SELECT to_jsonb(t) - 'row_line_id' - 'last_seq' - 'last_mode' - 'workstation' || "
             f"jsonb_build_object('path', d.path, 'line_no', d.line_no) FROM {SCHEMA}.lanes t "
             f"LEFT JOIN {SCHEMA}.doc_lines d ON d.line_id = t.row_line_id",
    "log_lines": f"SELECT to_jsonb(t) - 'line_id' - 'seq' - 'mode' - 'workstation' || "
                 f"jsonb_build_object('path', d.path, 'line_no', d.line_no) FROM "
                 f"{SCHEMA}.log_lines t LEFT JOIN {SCHEMA}.doc_lines d ON d.line_id = t.line_id",
    "register_lines": f"SELECT to_jsonb(t) - 'line_id' - 'seq' - 'mode' - 'workstation' || "
                      f"jsonb_build_object('path', d.path, 'line_no', d.line_no) FROM "
                      f"{SCHEMA}.register_lines t LEFT JOIN {SCHEMA}.doc_lines d "
                      f"ON d.line_id = t.line_id",
    "object_holds": f"SELECT to_jsonb(t) - 'seq' - 'mode' FROM {SCHEMA}.object_holds t",
}


def _psql(db, script: str, role: str | None = None) -> subprocess.CompletedProcess:
    """One `psql` as the fixture's superuser, as `role` where one is named,
    with the commit call's settings, so a refusal's first stderr line is
    `ERROR:  <SQLSTATE>: <message>`."""
    head = "\\set VERBOSITY verbose\n\\set SHOW_CONTEXT never\nSET client_encoding = 'UTF8';\n"
    if role:
        head += f"SET ROLE {role};\n"
    return subprocess.run([db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                          input=head + script, capture_output=True, encoding="utf-8",
                          errors="replace", env=db.env(appname="t271"), timeout=120, check=False)


def _sql(db, script: str, role: str | None = None) -> str:
    proc = _psql(db, script, role)
    assert proc.returncode == 0, (f"psql{' as ' + role if role else ''} exited "
                                  f"{proc.returncode}: {proc.stderr.strip()}\n{script}")
    return proc.stdout.strip()


def _rows(db, query: str) -> list:
    """`query`'s rows as JSON objects, read in the register's schema, by
    `jsonb_agg`, whose text is one line."""
    return json.loads(_sql(db, f"SET search_path TO {SCHEMA};\n"
                               f"SELECT coalesce(jsonb_agg(t), '[]'::jsonb) FROM ({query}) t;")
                      .splitlines()[-1])


def structured(db) -> dict:
    """The four structured tables of `db`, as `STRUCTURED` reads them, each a
    sorted list."""
    return {table: json.loads(_sql(db, f"SELECT coalesce(jsonb_agg(r ORDER BY r::text), '[]') "
                                       f"FROM ({query}) AS q(r);"))
            for table, query in STRUCTURED.items()}


def _renders(db) -> dict:
    """SQL's own render (lane 1's T107, `render_file`) of every path in
    `files`, {path: bytes}."""
    return {r["path"]: base64.b64decode(r["b64"]) for r in _rows(
        db, "SELECT path, encode(render_file(path), 'base64') AS b64 FROM files ORDER BY path")}


class Estate(Workspace):
    """TEST 6'S PRIMARY ESTATE (AT-6, "Fixture"), as the module's docstring
    sets it out: the fixture register at C imported on `pg`, and the cutover
    by AT-LR006's route, its marker commit on the bare origin. Until a step's
    task lands, the case fails at that step's own assertion, naming it."""

    def __init__(self, root: Path, pg):
        super().__init__(root, SEED)
        proc = self.edit("log", "NOTED", f"lane:{OPERATOR}", "test 6's register, at C",
                         env={"LANES_LANE": OPERATOR})
        assert proc.returncode == 0, f"lanes-edit.sh log NOTED: {_said(proc)}"
        self.c = self.tip()
        # The operator lane's git author, in its checkout's own configuration:
        # a way out names its entry's author as git does there, with every
        # inherited `GIT_*` variable removed first (D12), so this module's
        # `GIT_AUTHOR_*` never reach it (the module's readings).
        self.git("config", "user.name", AUTHOR_NAME)
        self.git("config", "user.email", AUTHOR_EMAIL)
        self.pg = pg
        self.bin = root / "bin"
        self.bin.mkdir()
        (self.bin / "psql").symlink_to(pg.psql_bin)
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        self.copy = flipped_indexer(root / "flip")
        self.index_conf = self.config(pg, "index")
        self.primary_conf = self.config(pg, "primary")
        self.persons = 0
        imported = self.import_at(self.c)
        assert imported.returncode == 0, (
            f"test 6's import at C failed (lane 1's T115, `import --at`):\n{_said(imported)}")
        assert self.head() == 0, f"after the import the head is {self.head()}, not 0"
        self.marker = self._cutover()

    # ------------------------------------------------------------ the configuration
    def config(self, pg, mode: str, name: str = "") -> Path:
        """The operator's configuration (CLI4.10 section 2.5): `mode`, the
        register's two URLs on the cluster's Unix socket, a private password
        file each, `register_label=` and `register_schema=`. Mode 0600."""
        passfile = self.conf / "pgpass"
        if not passfile.exists():
            passfile.write_text("", encoding="utf-8")
            passfile.chmod(0o600)
        path = self.conf / f"lanes-index-{name or mode}.conf"
        path.write_text("\n".join([
            f"mode={mode}", f"register_url={pg.url()}", f"register_passfile={passfile}",
            f"reader_url={pg.url()}", f"reader_passfile={passfile}",
            f"register_label={LABEL}", f"register_schema={SCHEMA}", ""]), encoding="utf-8")
        path.chmod(0o600)
        return path

    # ------------------------------------------------------------ the SQL side
    def rows(self, query: str) -> list:
        return _rows(self.pg, query)

    def head(self) -> int:
        return self.rows("SELECT seq FROM register_head")[0]["seq"]

    def switch(self) -> dict:
        return self.rows("SELECT * FROM register_switch")[0]

    def mirror(self) -> dict:
        return self.rows("SELECT * FROM mirror_state")[0]

    def count(self) -> int:
        return self.rows("SELECT count(*) AS n FROM journal")[0]["n"]

    def entry(self, seq: int) -> dict:
        found = self.rows(f"SELECT seq, kind, verb, message, git_commit, operator FROM journal "
                          f"WHERE seq = {seq}")
        assert len(found) == 1, f"the journal holds no entry at seq {seq}: {found}"
        return found[0]

    def edits(self, seq: int) -> list:
        return [(r["op"], r["path"], r["new_text"]) for r in self.rows(
            f"SELECT ord, op, path, new_text FROM journal_edits WHERE seq = {seq} ORDER BY ord")]

    def renders(self) -> dict:
        return _renders(self.pg)

    def commit_call(self, base: int, body: dict) -> subprocess.CompletedProcess:
        """The commit call as a writer sends it (section 1.3's step 3;
        AT-LR006's fixture): one SERIALIZABLE transaction around
        `commit_write`, as REGISTER-WRITER."""
        version = self.rows("SELECT version FROM schema_version")[0]["version"]
        generation = self.switch()["generation"]
        literal = json.dumps(body, ensure_ascii=True).replace("'", "''")
        return _psql(self.pg, f"BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
                              f"SELECT {SCHEMA}.commit_write({base}, '{uuid.uuid4()}'::uuid, "
                              f"{version}, '{generation}'::uuid, '{literal}'::jsonb);\nCOMMIT;\n",
                     WRITER)

    def committed(self, base: int, body: dict, what: str) -> int:
        proc = self.commit_call(base, body)
        assert proc.returncode == 0, (f"{what}: commit_write refused it (lane 1's T107):\n"
                                      f"{proc.stderr.strip()}")
        return int(proc.stdout.strip().splitlines()[-1])

    def _cutover(self) -> str:
        """AT-LR006's route from the import: the `cutover` entry, its marker
        commit pushed as a fast-forward of C, then `record_marker`."""
        lines = _store_lines(LABEL, self.c, self.tree(self.c))
        text = "\n".join(lines) + "\n"
        edits = [{"ord": 1, "op": "create", "path": "lanes/STORE"}]
        edits += [{"ord": n, "op": "append", "path": "lanes/STORE", "new_text": line}
                  for n, line in enumerate(lines, start=2)]
        cut = self.committed(0, _entry(
            "cutover", "cutover", "t271: the cutover", edits=edits,
            files=[{"path": "lanes/STORE", "present": True,
                    "sha256": _sha256(text.encode("utf-8")), "final_newline": True}]),
            "the cutover entry")
        marker = self.commit({"lanes/STORE": text},
                             f"cutover: lanes/STORE, the marker\n\nRegister-Seq: {cut}")
        assert self.origin_parent(marker) == self.c, "the marker commit is a fast-forward of C"
        version = self.rows("SELECT version FROM schema_version")[0]["version"]
        answer = _sql(self.pg, f"SELECT {SCHEMA}.record_marker({version}, {cut}, '{marker}', "
                               f"'{WS}');", WRITER)
        assert answer == "present", f"record_marker answered {answer!r}, not present"
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"], self.head()) == ("primary", "present", 1), (
            f"AT-LR006's route left the switch {switch} and the head {self.head()}, not primary, "
            f"present and 1")
        return marker

    def write_body(self, text: str) -> dict:
        """A write that appends `text`, a line of no kind, to
        `lanes/LANES.md`: no structured row."""
        after = self.renders()["lanes/LANES.md"] + (text + "\n").encode("utf-8")
        return _entry("write", "log", f"LANES({OPERATOR}@{WS}): {text}",
                      journal={"args_sha256": ARGS_SHA256},
                      edits=[{"ord": 1, "op": "append", "path": "lanes/LANES.md",
                              "new_text": text}],
                      files=[{"path": "lanes/LANES.md", "present": True,
                              "sha256": _sha256(after), "final_newline": True}])

    def write(self, text: str) -> int:
        """A primary write (the module's docstring): its seq."""
        base = self.head()
        seq = self.committed(base, self.write_body(text), f"a primary write, {text!r}")
        assert seq == base + 1, f"the write took seq {seq}, not {base + 1}"
        return seq

    def replace_line(self, path: str, line_no: int, text: str) -> int:
        """A primary write that replaces line `line_no` of `path`, a line of
        no kind, with `text`: one `replace` edit, naming the line by its old
        text's digest (section 1.3), and no structured row. Its seq."""
        image = self.renders()[path]
        lines = image.decode("utf-8").split("\n")
        assert image.endswith(b"\n") and 1 <= line_no < len(lines), (path, line_no, lines)
        old, lines[line_no - 1] = lines[line_no - 1], text
        after = "\n".join(lines).encode("utf-8")
        base = self.head()
        seq = self.committed(base, _entry(
            "write", "log", f"LANES({OPERATOR}@{WS}): t271: {path} line {line_no} replaced",
            journal={"args_sha256": ARGS_SHA256},
            edits=[{"ord": 1, "op": "replace", "path": path, "line_no": line_no,
                    "old_sha256": _sha256(old.encode("utf-8")), "new_text": text}],
            files=[{"path": path, "present": True, "sha256": _sha256(after),
                    "final_newline": True}]),
            f"a primary write replacing line {line_no} of {path}")
        assert seq == base + 1, f"the write took seq {seq}, not {base + 1}"
        return seq

    def record(self, sha: str | None, error: str | None = None,
               ws: str = "ws-t271") -> subprocess.CompletedProcess:
        return _psql(self.pg, f"SELECT {SCHEMA}.record_mirror_state('{ws}', "
                              f"{'NULL' if sha is None else repr(sha)}, "
                              f"{'NULL' if error is None else repr(error)});", WRITER)

    # ------------------------------------------------------------ lanes-index
    def index(self, *args, conf: Path | None = None, env: dict | None = None,
              timeout: float = 300) -> subprocess.CompletedProcess:
        """The flipped copy, as the operator lane through its checkout."""
        child = {"LANES_INDEX_CONFIG": str(conf or self.primary_conf), "LANES_LANE": OPERATOR,
                 "LANES_INDEX": None, "LANES_EDIT": str(self.copy.parent / "lanes-edit.sh")}
        child.update(env or {})
        return self.run(sys.executable, self.copy, *args, cwd=self.wip, timeout=timeout,
                        env=child)

    def import_at(self, sha: str, *, conf: Path | None = None,
                  cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
        """`lanes-index import --at <sha>`, the shipped one, as the operator
        lane through its checkout (test 7's form)."""
        child = {"LANES_INDEX_CONFIG": str(conf or self.index_conf), "LANES_LANE": OPERATOR,
                 "LANES_INDEX": None}
        child.update(env or {})
        return self.run(sys.executable, INDEXER, "import", "--at", sha, cwd=cwd or self.wip,
                        timeout=400, env=child)

    def render(self) -> subprocess.CompletedProcess:
        """The render a primary write forks, `render --checkout <c>`, run in
        the foreground: its exit is the wait for it."""
        return self.index("render", "--checkout", str(self.wip))

    def status(self) -> subprocess.CompletedProcess:
        """`lanes-index status`, after a fetch in the checkout: `status`
        never fetches, and reads `m` on `origin/main` as last fetched."""
        self.git("fetch", "-q", "origin", check=False)
        return self.index("status", conf=self.index_conf)

    def wait_lag_0(self, ceiling: float = 30.0) -> subprocess.CompletedProcess:
        """Open point 8's first wait: `status` every 100 ms until its lag is
        0, under `ceiling`. Returns the last `status`."""
        end = time.monotonic() + ceiling
        while True:
            proc = self.status()
            if LAG_0.search(proc.stdout) or time.monotonic() > end:
                return proc
            time.sleep(0.1)

    def reconcile(self) -> subprocess.CompletedProcess:
        return self.index("reconcile")

    def import_single(self, sha: str) -> subprocess.CompletedProcess:
        """The single-write import, on a person's word (T324)."""
        return self.index("import", "--single", sha)

    def revert(self, sha: str) -> subprocess.CompletedProcess:
        """The renderer's revert, on a person's word (T324)."""
        return self.index("render", "--revert", sha)

    def rollback(self) -> subprocess.CompletedProcess:
        return self.index("rollback")

    # ------------------------------------------------------------ other hands
    def stale(self) -> StaleWorkstation:
        return StaleWorkstation(self.root / "stale", self.origin)

    def push_as_person(self, files: dict, message: str) -> str:
        """A person's commit of `files` ({path: str}), from a clone of their
        own, pushed to origin's `main`. Returns it."""
        self.persons += 1
        clone = self.root / f"person-{self.persons}"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(clone)], check=True,
                       env=self.env, capture_output=True, stdin=subprocess.DEVNULL)
        for path, text in files.items():
            target = clone / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
        for argv in (["add", "--", *files], ["commit", "-q", "-m", message],
                     ["push", "-q", "origin", "HEAD:main"]):
            subprocess.run(["git", "-C", str(clone), *argv], check=True, env=self.env,
                           capture_output=True, stdin=subprocess.DEVNULL)
        sha = self.origin_tip()
        assert subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True,
                              text=True, env=self.env).stdout.strip() == sha
        return sha

    def origin_text(self, path: str) -> str:
        return self.origin_blob(self.origin_tip(), path).decode("utf-8")


# ------------------------------------------------------------------ the oracles
def _lag(text: str) -> int | None:
    m = LAG_N.search(text)
    return int(m.group(1)) if m else None


def _stop(est: Estate) -> tuple:
    """AT-6's stray and stop: the stale workstation's `log NOTED`, then a
    primary write and its render. Returns (the stray, the write's seq, the
    render)."""
    before = est.origin_tip()
    stale = est.stale()
    proc = stale.note("a note the v1.1.0 writer pushes to a primary estate")
    assert proc.returncode == 0, (
        f"the v1.1.0 writer's log NOTED did not push (it knows no marker, so on an estate "
        f"with no gate it pushes):\n{_said(proc)}")
    stray = est.origin_tip()
    assert stray != before and est.origin_parent(stray) == before, (
        f"origin's tip {stray} is not one commit on {before}")
    assert est.origin_changed(stray) == [f"lanes/log/{STALE_LANE}.md"], (
        f"the stale write changes {est.origin_changed(stray)}, not its lane's log alone")
    k = est.write("t271: a primary write after the stray")
    return stray, k, est.render()


def _assert_stopped(est: Estate, stray: str, render) -> None:
    """The stop, read after the renderer's exit: no render commit, origin's
    tip still the stray, and `diverged at` recorded (D16)."""
    assert est.origin_tip() == stray, (
        f"origin's tip moved past the stray {stray} to {est.origin_tip()}: the render pushed "
        f"over a commit it did not make (lane 3's T322)\n{_said(render)}")
    diverged = est.mirror()["diverged_sha"]
    assert diverged == stray, (
        f"mirror_state.diverged_sha is {diverged!r}, not the stray {stray} (D16; lane 3's T322)"
        f"\n{_said(render)}")


def _assert_status_diverged(est: Estate, sha: str, past: tuple | None = None) -> None:
    """`status` prints `diverged at <sha>` with the full sha, and the lag:
    for a plain stray, a lag of at least 1 (TP:1284); with `past`, `(m, n)`
    for a `Register-Seq` above the head, no lag, `m` past `n`, as `status`
    says (TP:1319 at B15; lane 3's L2-7)."""
    proc = est.status()
    assert f"diverged at {sha}" in proc.stdout, (
        f"status does not print `diverged at {sha}` with the full sha (lane 1's T117):\n"
        f"{_said(proc)}")
    if past is not None:
        found = LAG_PAST_N.search(proc.stdout)
        assert found and _lag(proc.stdout) is None and (
            int(found.group(1)), int(found.group(2))) == past, (
            f"status does not print no lag, the mirror's {past[0]} past n {past[1]} "
            f"(TP:1319; Y:2850; lane 3's L2-7):\n{_said(proc)}")
        return
    lag = _lag(proc.stdout)
    assert lag is not None and lag >= 1, (
        f"status does not print a lag of at least 1 seq (AT-6's stop):\n{_said(proc)}")


def _resume(est: Estate, since: str, first: int) -> None:
    """THE RESUME (AT-6, each way out): the renderer renders every pending
    seq onto origin's tip in order; `status` then shows a lag of 0 and no
    divergence; origin's rendered paths equal a full render from SQL, byte
    for byte; and `reconcile` exits 0."""
    render = est.render()
    proc = est.wait_lag_0()
    assert LAG_0.search(proc.stdout), (
        f"after the way out, status shows no lag of 0 within 30 s (the renderer did not "
        f"resume):\n{_said(proc)}\nthe render: {_said(render)}")
    assert NO_DIVERGENCE.search(proc.stdout) and "diverged at" not in proc.stdout, (
        f"status still shows a divergence:\n{_said(proc)}")
    seqs = [s for _sha, found in est.commits_after(since) for s in found]
    assert seqs == list(range(first, est.head() + 1)), (
        f"the seqs pushed after {since[:12]} are {seqs}, not {first} to {est.head()} in order")
    tip = est.origin_tip()
    from_sql = {p: b for p, b in est.renders().items() if RENDER_SET.match(p)}
    on_origin = est.origin_render_set(tip)
    assert on_origin == from_sql, (
        f"origin's rendered paths at {tip[:12]} differ from a full render from SQL: "
        f"{sorted(set(on_origin) ^ set(from_sql))} or "
        f"{sorted(p for p in on_origin if p in from_sql and on_origin[p] != from_sql[p])}")
    rec = est.reconcile()
    assert rec.returncode == 0, f"reconcile does not pass after the way out:\n{_said(rec)}"


def _way_out(est: Estate, stray: str, way: str) -> int:
    """`import --single <stray>` or `render --revert <stray>`, on a person's
    word: one journal entry naming the stray, and `diverged at` cleared.
    Returns the entry's seq."""
    n, count = est.head(), est.count()
    proc = est.import_single(stray) if way == "import" else est.revert(stray)
    verb = "import --single" if way == "import" else "render --revert"
    assert proc.returncode == 0, f"lanes-index {verb} {stray} (lane 3's T324):\n{_said(proc)}"
    assert (est.head(), est.count()) == (n + 1, count + 1), (
        f"{verb} did not add exactly one journal entry: the head {n} -> {est.head()}, the "
        f"count {count} -> {est.count()}")
    got = est.entry(n + 1)
    kind = "stray-import" if way == "import" else "stray-revert"
    assert (got["kind"], got["git_commit"]) == (kind, stray), (
        f"seq {n + 1} is {got}, not a {kind} entry naming {stray} (design.md's kinds)")
    mirror = est.mirror()
    assert mirror["diverged_sha"] is None, (
        f"after {verb} mirror_state still records diverged at {mirror['diverged_sha']} (D16)")
    return n + 1


def _assert_rolled_back(est: Estate, proc) -> None:
    """TEST 8'S FIRST ORACLE (test 8 (a)): exit 0; the switch at `files`
    with the marker `absent`; origin's last commit removes `lanes/STORE`
    alone and carries the rollback entry's seq, the journal's last; origin's
    rendered paths equal a full render from SQL, byte for byte; and SQL
    writes refused: a `write` entry is LR002, and the head does not move."""
    assert proc.returncode == 0, f"the rollback did not end 0 (lane 3's T326):\n{_said(proc)}"
    switch = est.switch()
    assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), (
        f"the switch is {switch['mode']}/{switch['marker_state']}, not files/absent")
    last = est.rows("SELECT seq, kind, operator FROM journal ORDER BY seq DESC LIMIT 1")[0]
    assert (last["kind"], last["operator"]) == ("rollback", True), f"the last entry is {last}"
    tip = est.origin_tip()
    assert REGISTER_SEQ.findall(est.origin_git("log", "-1", "--format=%B", tip)) == [
        str(last["seq"])], f"origin's last commit does not carry Register-Seq: {last['seq']}"
    changed = est.origin_git("diff-tree", "--no-commit-id", "--name-status", "-r", f"{tip}^", tip)
    assert changed.split("\n") == ["D\tlanes/STORE", ""], (
        f"origin's last commit does not remove lanes/STORE alone: {changed!r}")
    from_sql = {p: b for p, b in est.renders().items() if RENDER_SET.match(p)}
    assert est.origin_render_set(tip) == from_sql, (
        "origin's rendered paths differ from a full render from SQL after the rollback")
    head = est.head()
    refused = est.commit_call(head, est.write_body("t271: a write after the rollback"))
    assert refused.returncode != 0 and "LR002" in refused.stderr, (
        f"a write after the rollback was not refused with LR002:\n{_said(refused)}")
    assert est.head() == head


# =================================================================== the gate model
GUARDED = {
    "lanes-md": "lanes/LANES.md",
    "log-lane": f"lanes/log/{STALE_LANE}.md",
    "aliases-tsv": "lanes/aliases.tsv",
    "archive": "lanes/archive/LANES-retired.md",
    "store": "lanes/STORE",
}
UNGUARDED = {"repos-tsv": "lanes/repos.tsv", "log-readme": "lanes/log/README.md"}


@pytest.mark.parametrize("path", list(GUARDED))
def test_a_server_side_gate_refuses_the_stale_writers_push(tmp_path, path):
    """A MODEL (AT-6, "Options", Q21(b)): with `GATE_HOOK` in the bare
    origin, the v1.1.0 writer's push to each guarded path is refused. Its
    exit is v1.1.0's 6 (six rejected pushes, "your commit is local"), the
    hook's log names the path, and origin's `main` does not move.

    `[lanes-md]` is a hand edit the writer commits (`commit`); `[log-lane]`
    is `log NOTED`; `[aliases-tsv]`, `[archive]` and `[store]` are a
    person's local commit that the writer publishes (`commit`, #194's
    publish of the commits ahead, which takes any added or modified file
    under `lanes/`). Needs no engine, and waits for nothing."""
    reg = GatedOrigin(tmp_path / "e")
    stale = StaleWorkstation(tmp_path / "stale", reg.origin)
    target = GUARDED[path]
    before = reg.origin_tip()
    if path == "lanes-md":
        page = stale.wip / target
        page.write_text(page.read_text(encoding="utf-8") + "a hand edit of the register\n",
                        encoding="utf-8")
        proc = stale.v110("commit", "t271: a hand edit of LANES.md")
    elif path == "log-lane":
        proc = stale.note("a note the gate refuses")
    else:
        stale.local_commit(target, "a line a person added\n", f"t271: an edit of {target}")
        proc = stale.v110("commit", f"t271: publish the edit of {target}")
    assert proc.returncode == 6, (
        f"the v1.1.0 writer's push to {target} did not end with its six-attempt refusal, "
        f"6:\n{_said(proc)}")
    records = reg.gate_records()
    assert records and all(r["outcome"] == "refused" for r in records), records
    assert {p for r in records for push in r["pushes"] for p in push["guarded"]} == {target}, (
        f"the gate model refused {records}, not {target} alone")
    assert reg.origin_tip() == before, "origin's main moved under a refused push"


@pytest.mark.parametrize("path", list(UNGUARDED))
def test_the_gate_model_lets_a_push_to_an_unguarded_path_through(tmp_path, path):
    """A MODEL (AT-6, "Options"): a person's push of an edit to
    `lanes/repos.tsv` or `lanes/log/README.md`, from the stale workstation's
    clone, is accepted ("A person's `repos.tsv` edit is not gated"): origin's
    `main` is that commit, and the hook's log says it was let through. Needs
    no engine, and waits for nothing."""
    reg = GatedOrigin(tmp_path / "e")
    stale = StaleWorkstation(tmp_path / "stale", reg.origin)
    target = UNGUARDED[path]
    sha = stale.local_commit(target, "a line a person added\n", f"t271: an edit of {target}")
    stale.git("push", "-q", "origin", "main")
    assert reg.origin_tip() == sha, "the push to an unguarded path did not land"
    records = reg.gate_records()
    assert [r["outcome"] for r in records] == ["accepted"], records
    assert records[0]["pushes"][0]["paths"] == [target], records


# =================================================================== the stop
def test_the_v1_1_0_writer_pushing_to_a_primary_estate_stops_the_renderer(pg, tmp_path):
    """AT-6, the stop: the stale workstation's `log NOTED`, by the pinned
    v1.1.0 writer, lands on origin over a primary estate; the next primary
    write's render makes no commit, origin's tip is still the stray, and
    `mirror_state.diverged_sha` records it (D16). A later primary write
    still commits to SQL, since the mirror is write-behind. Fails until
    T107, T115, T117 and lane 3's T321 to T323 land."""
    est = Estate(tmp_path / "e", pg)
    stray, k, render = _stop(est)
    _assert_stopped(est, stray, render)
    assert est.commits_after(stray) == [], "the render pushed a commit after the stray"
    later = est.write("t271: a later write, while the mirror is diverged")
    assert later == k + 1 and est.head() == later
    assert est.mirror()["diverged_sha"] == stray


def test_status_prints_diverged_at_the_stray_sha_and_reconcile_imports_nothing(pg, tmp_path):
    """AT-6, the stop: after the renderer's exit, `status` prints `diverged
    at <the stray's full sha>` and a lag of at least 1; `reconcile` exits
    non-zero, the journal's count is unchanged, and `status` still prints
    `diverged at` after it. The non-zero is 1: T325's re-render runs T322's
    pass, whose recorded stop is the renderer's 1 (exit-codes.md section
    3.4's `reconcile` 1 row; lane 3's L2-6). Fails until T107, T115, T117
    and T321 to T323 land, and also until T325, where T117's check alone
    exits 0 (B15 tasks:2487)."""
    est = Estate(tmp_path / "e", pg)
    stray, _k, render = _stop(est)
    _assert_stopped(est, stray, render)
    _assert_status_diverged(est, stray)
    count, head = est.count(), est.head()
    rec = est.reconcile()
    assert (est.count(), est.head()) == (count, head), "reconcile wrote to the journal"
    assert rec.returncode == 1, (
        f"reconcile on a diverged mirror does not exit 1, the renderer's code for a recorded "
        f"`diverged at` (AT-6: non-zero; exit-codes.md section 3.4; lane 3's T325, without "
        f"which T117's check alone exits 0; L2-6):\n{_said(rec)}")
    after = est.status()
    assert f"diverged at {stray}" in after.stdout, (
        f"status no longer prints `diverged at {stray}` after reconcile:\n{_said(after)}")


# =================================================================== the ways out
def test_the_single_write_import_resumes_the_renderer_and_reconcile_passes(pg, tmp_path):
    """AT-6, the single-write import: `lanes-index import --single <stray>`
    adds exactly one journal entry, a `stray-import` naming the stray, whose
    line edits equal the stray commit's diff; `mirror_state` no longer
    records `diverged at`; the renderer resumes and the pending seqs reach
    origin in order; `status` shows a lag of 0 and no divergence; origin's
    rendered paths equal a full render; and `reconcile` exits 0. Fails until
    T324 (and T107, T115, T117, T321 to T323)."""
    est = Estate(tmp_path / "e", pg)
    stray, _k, render = _stop(est)
    _assert_stopped(est, stray, render)
    path = f"lanes/log/{STALE_LANE}.md"
    old = est.origin_blob(f"{stray}^", path).decode("utf-8").split("\n")
    new = est.origin_blob(stray, path).decode("utf-8").split("\n")
    assert new[:len(old) - 1] == old[:-1] and old[-1] == new[-1] == "", "the stray only appends"
    added = new[len(old) - 1:-1]
    seq = _way_out(est, stray, "import")
    assert est.edits(seq) == [("append", path, line) for line in added], (
        f"the import's edits {est.edits(seq)} are not the stray's diff, {added} appended to "
        f"{path}")
    _resume(est, stray, 2)
    assert all(line.encode("utf-8") in est.renders()[path] for line in added)


def test_the_renderers_revert_resumes_it_and_reconcile_passes(pg, tmp_path):
    """AT-6, the renderer's revert: `lanes-index render --revert <stray>`
    journals one `stray-revert` entry with no edits, whose message names the
    stray (D16); `diverged at` clears; the resume as for the import; and the
    render puts SQL's state back over the stray: on each path the stray
    changed, origin's tip equals the stray's parent (the module's readings).
    Fails until T324 (and T107, T115, T117, T321 to T323)."""
    est = Estate(tmp_path / "e", pg)
    stray, _k, render = _stop(est)
    _assert_stopped(est, stray, render)
    seq = _way_out(est, stray, "revert")
    assert est.edits(seq) == [], f"the revert's entry has edits: {est.edits(seq)}"
    assert stray[:7] in (est.entry(seq)["message"] or ""), (
        f"the revert's message does not name the stray: {est.entry(seq)['message']!r}")
    _resume(est, stray, 2)
    tip = est.origin_tip()
    for path in est.origin_changed(stray):
        assert est.origin_blob(tip, path) == est.origin_blob(f"{stray}^", path), (
            f"{path} at origin's tip is not SQL's state from before the stray")


@pytest.mark.parametrize("way", ["import", "revert"])
def test_rollback_works_after_each_way_out(pg, tmp_path, way):
    """AT-6, after each way out and the resume: a rollback, with the
    database up, ends with the files byte-identical, the marker gone and SQL
    writes refused (test 8's first oracle). Fails until T324 and T326 (and
    T107, T115, T117, T321 to T323)."""
    est = Estate(tmp_path / "e", pg)
    stray, _k, render = _stop(est)
    _assert_stopped(est, stray, render)
    _way_out(est, stray, way)
    _resume(est, stray, 2)
    _assert_rolled_back(est, est.rollback())


# =================================================================== the negative cases
OUTSIDE = ["cutover-store", "repos-tsv", "handoff"]


@pytest.mark.parametrize("commit", OUTSIDE)
def test_commits_outside_the_render_set_do_not_stop_the_renderer(pg, tmp_path, commit):
    """AT-6's negative cases (P366-374): the cutover's own `lanes/STORE`
    commit, a person's `lanes/repos.tsv` edit, and a person's commit under
    `handoffs/`, each between renders, do not stop the renderer: the next
    render renders onto that tip, and `status` shows a lag of 0 and no
    divergence. Fails until T107, T115, T117 and T321 to T323 land."""
    est = Estate(tmp_path / "e", pg)
    if commit == "cutover-store":
        tip = est.origin_tip()
        assert tip == est.marker and est.origin_changed(tip) == ["lanes/STORE"]
    else:
        est.write("t271: a write rendered before the commit")
        settled = est.render(), est.wait_lag_0()
        assert LAG_0.search(settled[1].stdout), (
            f"the first write was not rendered:\n{_said(settled[0])}\n{_said(settled[1])}")
        if commit == "repos-tsv":
            files = {"lanes/repos.tsv": est.origin_text("lanes/repos.tsv")
                     + "repoQ\topensoft/repoQ\n"}
        else:
            files = {f"handoffs/{OPERATOR}.md": "# a handoff, between renders\n"}
        tip = est.push_as_person(files, f"t271: a person's {commit} commit")
        assert est.origin_changed(tip) == sorted(files)
    k = est.write("t271: the write after the commit")
    render = est.render()
    proc = est.wait_lag_0()
    assert LAG_0.search(proc.stdout) and NO_DIVERGENCE.search(proc.stdout), (
        f"after the {commit} commit the render stopped or lags:\n{_said(proc)}\n{_said(render)}")
    gained = est.commits_after(tip)
    assert gained and gained[-1][1] == [k], f"origin gained {gained} after {tip[:12]}, not seq {k}"
    assert est.origin_parent(gained[0][0]) == tip, "the render did not render onto that tip"
    assert est.mirror()["diverged_sha"] is None


# =================================================================== R2's N6 at primary
def test_a_register_seq_above_the_head_stops_the_renderer_at_primary_and_the_revert_resumes_it(
        pg, tmp_path):
    """AT-6, a `Register-Seq` above the head (R2's N6), at `primary`: a
    person's commit of a file under `handoffs/` carrying `Register-Seq:
    <h+10>` in its final trailer block, then a write at `h+1` and its
    render. The pass records a divergence at that commit and pushes nothing;
    `status` prints `diverged at` its full sha and no lag, its `m` (`h`+10)
    past `n` (`h`+1), as `status` says (TP:1319 at B15; Y:2850; lane 3's
    L2-7); `render --revert <sha>` journals one entry with no
    edits naming it, and `diverged at` clears; the renderer then finds `m`
    at the last render commit before it and renders on, on top of it, to the
    revert's own seq; origin equals a full render, `reconcile` exits 0, and a
    rollback afterwards works. Fails until T324 and T326 (and T107, T115,
    T117, T321 to T323)."""
    est = Estate(tmp_path / "e", pg)
    est.write("t271: a write rendered before the forged trailer")
    est.render()
    assert LAG_0.search(est.wait_lag_0().stdout), "the first write was not rendered"
    h = est.head()
    forged = est.push_as_person({f"handoffs/{OPERATOR}.md": "# a handoff, its trailer copied\n"},
                                f"t271: a handoff carrying a copied trailer\n\n"
                                f"Register-Seq: {h + 10}")
    assert est.origin_changed(forged) == [f"handoffs/{OPERATOR}.md"]
    est.write("t271: a write after the forged trailer")
    render = est.render()
    _assert_stopped(est, forged, render)
    _assert_status_diverged(est, forged, past=(h + 10, h + 1))
    seq = _way_out(est, forged, "revert")
    assert est.edits(seq) == [], f"the revert's entry has edits: {est.edits(seq)}"
    assert forged[:7] in (est.entry(seq)["message"] or "")
    _resume(est, forged, h + 1)
    assert est.origin_parent(est.commits_after(forged)[0][0]) == forged, (
        "the renderer did not render on top of the commit it passed over")
    _assert_rolled_back(est, est.rollback())


# =================================================================== AT-MIR's gating case
@pytest.mark.parametrize("case", ["row-only", "git-only"])
def test_the_mirror_state_row_never_gates_alone(pg, tmp_path, case):
    """AT-MIR, the row never gates alone (G; D16): `[row-only]`, with
    `mirror_state` recording a divergence by `record_mirror_state` and git
    holding no stray, the next render renders and `status` shows a lag of
    0; `[git-only]`, with a stray on origin and the row empty, the renderer
    still stops (test 6's oracle). Fails until T107, T115, T117 and T321 to
    T323 land."""
    est = Estate(tmp_path / "e", pg)
    if case == "row-only":
        recorded = est.record("1" * 40)
        assert recorded.returncode == 0, f"record_mirror_state: {_said(recorded)}"
        assert est.mirror()["diverged_sha"] == "1" * 40
        tip = est.origin_tip()
        k = est.write("t271: a write with the row set")
        render = est.render()
        proc = est.wait_lag_0()
        assert LAG_0.search(proc.stdout), (
            f"with the row set and no stray, the render did not render:\n{_said(proc)}\n"
            f"{_said(render)}")
        gained = est.commits_after(tip)
        assert [s for _sha, found in gained for s in found] == [k], gained
        return
    assert est.mirror()["diverged_sha"] is None, "the row is not empty before the stray"
    stray, _k, render = _stop(est)
    _assert_stopped(est, stray, render)
    _assert_status_diverged(est, stray)


# =================================================================== T324's strays
def _stray_files(est: Estate, stray: str) -> tuple:
    """The stray's files, from origin's tip: `[stray-deletes-a-row]` deletes
    repoD-1's row with no archive copy; `[stray-inserts-before-the-end]`
    inserts a line in repoI-1's log after its `STARTED`, above its claims;
    `[stray-revives-a-pair]` deletes repoX-1's `RELEASED`, so its `CLAIMED`
    on `PAIR_OBJECT` is live beside repoY-1's; `[stray-no-longer-applies]`
    retitles `lanes/LANES.md`'s heading by hand."""
    if stray == "stray-deletes-a-row":
        path, old, new = "lanes/LANES.md", ROW_D + "\n", ""
    elif stray == "stray-inserts-before-the-end":
        path = "lanes/log/repoI-1.md"
        old = _started("repoI-1", UUID_I1, "opensoft/repoI") + "\n"
        new = old + INSERTED_I + "\n"
    elif stray == "stray-no-longer-applies":
        path, old, new = "lanes/LANES.md", TITLE + "\n", TITLE_BY_HAND + "\n"
    else:
        path, old, new = "lanes/log/repoX-1.md", RELEASED_X + "\n", ""
    text = est.origin_text(path)
    assert text.count(old) == 1, f"{path} does not hold the line the stray changes once"
    return path, {path: text.replace(old, new)}


def _assert_no_longer_applies(est: Estate, sha: str, path: str) -> None:
    """L2-8'S REFUSAL (TP:1292-1293; B15 tasks:2486): `import --single <sha>`,
    where the stray's edits no longer apply to SQL's images, refuses with 2
    on stderr, naming the edit's path, that its edits no longer apply, and
    `render --revert <sha>` as the way out (PC-4); it sends no commit call;
    and it writes nothing (the module's readings)."""
    before = (est.head(), est.count(), structured(est.pg), est.renders())
    log = est.root / "psql-calls.log"
    front = _logging_psql(est.root / "psql-log-bin", est.pg.psql_bin, log)
    proc = est.index("import", "--single", sha,
                     env={"PATH": str(front) + os.pathsep + est.env["PATH"]})
    assert proc.returncode == 2 and all(w in proc.stderr for w in (
            "no longer apply", path, f"render --revert {sha}")), (
        f"import --single of a stray whose edits no longer apply to SQL's images is not "
        f"refused with 2 on stderr, naming {path}, that they no longer apply, and "
        f"`render --revert {sha}` (lane 3's T324; L2-8):\n{_said(proc)}")
    calls = (log.read_text(encoding="utf-8", errors="replace").split("--- psql ")[1:]
             if log.exists() else [])
    requests = [call for call in calls if not call.startswith("--version")]
    assert requests, (
        "the refused import sent no request through the psql first on its PATH, so the log "
        "cannot show that it sent no commit call")
    sent = [call for call in requests if "commit_write(" in call]
    assert not sent, (
        f"the refused import sent {len(sent)} commit call(s): it refuses before any (TP:1292; "
        f"B15 tasks:2486):\n{sent[0][:1500]}")
    assert (est.head(), est.count(), structured(est.pg), est.renders()) == before, (
        "the refused import changed the head, the journal, the structured tables or SQL's "
        "images")
    assert est.mirror()["diverged_sha"] == sha, "the refused import cleared the divergence"
    assert est.origin_tip() == sha, "the refused import moved origin's main"


@pytest.mark.parametrize("stray", ["stray-deletes-a-row", "stray-inserts-before-the-end",
                                   "stray-revives-a-pair", "stray-no-longer-applies"])
def test_a_strays_single_write_import_leaves_the_tables_equal_to_the_imports_derivation(
        pg, tmp_path, stray):
    """T324'S STRAYS (R-F10-34; lane 3, #165 6755386771; ERR-48) and a stray
    that revives a pair (R-F13c-10; lane 3's batch 5, #165 6778890211): a
    person's stray commit on origin's `lanes`; the next write's render stops
    `diverged at <sha>`.

    `[stray-deletes-a-row]` and `[stray-inserts-before-the-end]`: `lanes-index
    import --single <sha>` loads it through `register commit` and exits 0;
    the renderer resumes and `reconcile` passes; and the four structured
    tables equal what `import --at` of the same mirror leaves in a second
    clone's database, compared as T221's step-6 cases compare them, without
    the columns a write stamps, which ERR-48's re-stamped later lines are.
    The insert's holds below its line each point at their own line.

    `[stray-revives-a-pair]`: two claims on one object are live after it,
    neither `exempt`, since only an import sets `exempt`; `import --single`
    refuses with 2, LR005 `one-live-claim` and `held-by=`, writes nothing,
    and leaves the four tables as they were. Its way out is the revert,
    which `test_the_renderers_revert_resumes_it_and_reconcile_passes` covers.

    `[stray-no-longer-applies]` (lane 3, #165 6809045090, L2-8; AT-6,
    TP:1292-1293; B15 tasks:2486): a primary write changes a line after the
    stray commit changed it, so the stray's edits no longer apply to SQL's
    images; `import --single` refuses with 2, naming the edit and `render
    --revert <sha>` as the way out (PC-4), sends no commit call, writes
    nothing, and leaves the four tables as they were.

    Fail until T324 (and T107, T115, T117, T321 to T323); the oracle, until
    T115's `import --at`; `[stray-revives-a-pair]`, until T324's refusal and
    T107's `one_live_claim`; `[stray-no-longer-applies]`, until T324's
    `import --single` refusal."""
    est = Estate(tmp_path / "e", pg)
    if stray == "stray-revives-a-pair":
        holds = {(h["lane_key"], h["verb"], h["exempt"]) for h in est.rows(
            f"SELECT lane_key, verb, exempt FROM object_holds "
            f"WHERE lower(object) = lower('{PAIR_OBJECT}')")}
        assert holds == {("repox-1", "RELEASED", False), ("repoy-1", "CLAIMED", False)}, (
            f"the control: at C repoX-1 has released {PAIR_OBJECT} and repoY-1 holds it, "
            f"neither exempt: {holds}")
    path, files = _stray_files(est, stray)
    sha = est.push_as_person(files, f"t271: a stray edit of {path}, by hand")
    assert est.origin_changed(sha) == [path]
    if stray == "stray-no-longer-applies":
        est.replace_line(path, 1, TITLE_IN_SQL)
    else:
        est.write("t271: a primary write after the stray")
    render = est.render()
    _assert_stopped(est, sha, render)
    if stray == "stray-no-longer-applies":
        _assert_no_longer_applies(est, sha, path)
        return
    if stray == "stray-revives-a-pair":
        before, head, count = structured(est.pg), est.head(), est.count()
        proc = est.import_single(sha)
        said = proc.stdout + proc.stderr
        assert proc.returncode == 2 and all(w in said for w in ("LR005", "one-live-claim",
                                                                "held-by=")), (
            f"import --single of a stray that revives a pair is not refused with 2, LR005 "
            f"one-live-claim and held-by= (lane 3's T324):\n{_said(proc)}")
        assert (est.head(), est.count()) == (head, count), "the refused import wrote an entry"
        assert structured(est.pg) == before, "the refused import changed the structured tables"
        assert est.mirror()["diverged_sha"] == sha, "the refused import cleared the divergence"
        return
    _way_out(est, sha, "import")
    _resume(est, sha, 2)
    got = structured(est.pg)
    tip = est.origin_tip()
    second = Workspace(tmp_path / "oracle", origin=est.origin)
    oracle_db = Database(est.pg.cluster, est.pg.cluster.new_database())
    try:
        conf = est.config(oracle_db, "index", name="oracle")
        proc = est.import_at(tip, conf=conf, cwd=second.wip,
                             env={"LANES_REPO": str(second.wip), "HOME": str(second.home),
                                  "AGENT_PROTOCOL_ROOT": str(second.agents)})
        assert proc.returncode == 0, (
            f"the oracle's import --at {tip[:12]} of the mirror failed (lane 1's T115):\n"
            f"{_said(proc)}")
        want = structured(oracle_db)
    finally:
        est.pg.cluster.drop_database(oracle_db.name)
    for table in STRUCTURED:
        assert got[table] == want[table], (
            f"{stray}: {table} is not the import's derivation of the mirror:\n"
            f"got  {json.dumps(got[table], indent=1)[:3000]}\n"
            f"want {json.dumps(want[table], indent=1)[:3000]}")
    if stray == "stray-inserts-before-the-end":
        lines = {(r["path"], r["line_no"]): r for r in got["log_lines"]}
        for hold in got["object_holds"]:
            if hold["file"] == path:
                line = lines[(hold["file"], hold["ordinal"])]
                assert (line["object"], line["verb"]) == (hold["object"], hold["verb"]), (
                    hold, line)
