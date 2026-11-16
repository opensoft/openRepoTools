# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 13 and AT-F4: the drill, and the ruleset's order (L2-G5;
AT-13; AT-F4; T276; FR-050, FR-051, FR-059; also US7)
(opensoft/openRepoTools#165).

T276 writes this module: 5 tests, AT-13's 2 and AT-F4's 3 (B15 tasks:2535,
"Write test 13 and AT-F4, the drill and the ruleset's order"). Lane 3's T326
runs it whole: its verify's word `sql_register_drill` selects these five ids
(B15 tasks:1542).

THE ESTATE, `Drill` (the test plan's AT-13, "Fixture"):

- SECTION 5.6'S TLS CLUSTER, T229's `tls_cluster`: a stoppable cluster on
  loopback TCP with TLS 1.3 and SCRAM, and a test CA of its own. The drill's
  database is a database of its own on it, made empty and bootstrapped by P8's
  bootstrap through the admin service with `--label register-drill`, as AT-P8's
  ready environment makes one (`TLSCluster.second_database`). Step 1's
  readiness check needs check 11, which a Unix socket always fails (AT-LRMPG).
- TWO ENGINEERS' LOGINS, `drill_a` and `drill_b`, made after the bootstrap by
  `lanes-index login add <engineer> --admin-service <service>` under a pty
  (operations.md act 3's step 2, "Then the logins"; `Cluster.lanes_index_tty`,
  as T228 makes the fixture's). The passwords each prints once are kept in the
  cluster's memory for its password files, and never printed.
- A BARE ORIGIN WITH THE FIXTURE REGISTER: test 7's, by pgcluster's
  `ImportedRegister` (T227b): AT-7's seed and the operator lane's `log NOTED`
  on top. Its operator checkout, with its W and `workspace.yaml`, is ws1's.
- TWO WORKSTATIONS, ws1 (`Eagle`, the operator lane `repoA-2`, engineer
  `drill_a`) and ws2 (`Hawk`, lane `repoW-1`, engineer `drill_b`, a clone of
  its own), each with its own `$HOME`, `workspace.yaml`, register checkout, W
  and 0600 configuration at `mode=index`. A configuration names only its own
  engineer's two logins and password files, over `sslmode=verify-full` with
  the test CA's root as `sslrootcert=`, with `register_label=register-drill`
  (the cutover takes its label from it, S5) and `register_addresses=1`
  (127.0.0.1 is one address; check 13). Each workstation's installed-tools
  directory holds T203's flipped `lanes-index` (`RENDER_GIT_HALF = True`, so
  `cutover`, `rollback` and a write on primary take `lanes_register` while
  lane 3's T328 has not set the constant), with `lanes-edit.sh`, `lanes`,
  `lane-start` and `repos.tsv` beside it, and check 1's digest list naming
  both tools. Where T124's `flipped_copy` places the launcher's module,
  `lanes_index_main.py`, beside the copy (tasks:2853), the list names it too,
  as the release's does since T347, and its checked-hash bytecode is written
  beside it, compiled under the bare name as check 1 compiles it, as
  `ReadyBench` does since T218s and T218t (T276l). Before T124 there is no
  module there, and nothing changes.
- EACH LANE'S OWN REGISTER CHECKOUT, `<c>` (lane 3's batch g Q119, #165
  6813027223): on primary a write reads its author, its pending hand edits
  and its `repos.tsv` from `<W>-lanes/<lane>`, W being the real path of its
  workstation's `workspace.yaml` `path:`, and refuses 2 where it is not there
  (B15 tasks:1154; lane 4's T415). So each workstation makes its own lane's,
  `repoA-2` on ws1 and `repoW-1` on ws2, a clone of origin, as step 3 flips
  it to `mode=primary`, after the cutover's push and before any write on
  primary (`Workstation.lane_checkout`; T276e).
- THE RULESET'S MODEL (AT-F4; Q21(b), the render set and `lanes/STORE`,
  Brett's "Render set + STORE", comment 6721583757): `RULESET_HOOK`, T271's
  pre-receive hook (test 6) with a switch file the drill's runbook steps set,
  and the renderer's identity let through.
- THE FREEZE (Q4(a)(i)): no other writer runs during steps 2 and 3; the drill
  runs none.

THE ORDER (AT-F4's ruling): the drain's last `PAUSED` write, the ruleset on,
the import at C, the cutover, then the flips; the rollback stops at
`--hold-marker` once the mirror is proved current, the ruleset goes off, and
the rerun pushes the removal of `lanes/STORE`.

WHAT EACH FAILS UNTIL. B15's Order (tasks:2542): it waits for T229, and its
tests fail until L1-A18, T326 and T327 land. Each step's labelled assertion
also names the tasks its own verbs rest on, by their B15 bullets, and lane
4's by lane 4's reading of its own code (#165 6826679959, item 1):
  1. `ready` (T119; its fourteenth check, git 2.32 or later, is lane 1's
     T119 follow-up 2), the logins (T110) and the TLS cluster (T229);
  2. `import --at` (T115, L1-A13);
  3. `cutover` (T116, L1-A14) and its marker's push, read-back and
     `record_marker` (lane 3's T327); the flips (T120);
  4. a write on primary (lane 4's T415), its render fork (T416) and the
     renderer (lane 3's T321 to T323); `status`'s lag (T117);
  5. `claim` and `log` on primary from both workstations (lane 4's T415),
     each rendered and settled as at step 4 (T416);
  6. a write's 69 (T415); the guard's direct read and its refusal (lane 5's
     T507); the mirror line (lane 5's T505); `status` (T117); `outage
     declare` (T121, L1-A18) and the guard's declared path (T507's SVC-12);
  7. `rollback`'s 69 (T304) and `outage clear` (T121);
  8. `rollback --hold-marker` and its rerun (lane 3's T326), and its
     declaration (T121, T304);
  9. the writer not yet cleared, 69, ended at its snapshot (lane 4's T415);
  10. the rollback's last render (T326).
The drill runs no `commit`, and no step reads the `register seq` text of
`claim`, so lane 4's T420 and T421 are none of its waits (lane 4, #165
6826679959, item 1). Lane 5's T507 is step 6's alone: only `step_6_outage`
calls the guard (lane 5, #165 6826891706).
On line R's `V-round5` (`e8804a4a`), which holds T110, T115, T116, T119, T120,
T121, T304 and T320 to T323 but not T327, T326, T415 or T507, every test stops
at step 3's assertion on the marker: `cutover` exits 0 with the marker
`adding` and nothing pushed (T116's point 1). On lane 3's `T326-m23`
(`552c22d4`), which adds T327 and T326 but not T415, step 3 passes, and a
test that runs step 4 stops there: `lanes-edit.sh` has no SQL write path.
With lane 4's `pair-m23s` (`d949b78`) on it too, step 4 refused 2 where its
lane's `<c>` was not there (line RB15's run e03), which step 3 now makes
(T276e).

READINGS, NOT FOUND IN A CONTRACT:
- "THE RENDERER'S IDENTITY" (AT-F4's fixture): a bare origin on disk cannot
  see D23's deploy key, and a render commit carries the journal's author as
  its committer (D15), so neither tells the renderer apart. The model reads
  the pushing program instead: a push is the renderer's where a process above
  the receiving `git` runs `lanes-index` (the renderer's pass, `cutover`'s
  marker push and `rollback`'s removal, each through T320's one push
  function), and anyone else's otherwise (`lanes-edit.sh`'s files-mode push,
  a person's `git push`). Lane 3 accepted this model, with the check outside
  pytest as its control, and suggested that the hook log the process it
  found, so that a failure names it (#165 6813027223): each record carries
  `found` and `walked`.
- C IS ORIGIN'S TIP AT THE IMPORT, after the freeze's `PAUSED` write and
  AT-F4's accepted pushes: the cutover checks that the tip's `lanes` tree is
  C's (T327's step 2), and the import runs from ws1's checkout fetched to it.
- "THE LAST `PAUSED` WRITE" is the drain's row write, `set-row-state <lane>
  "PAUSED ..."` (lane-handoff's W9), for `repoD-1`, a LIVE row of the fixture
  register that no other step writes, run in files mode from ws2.
- STEP 6'S "THE GUARD ANSWERS FROM THE MIRROR" is AT-D20's oracle for a
  bound lane (T215; TP:3931 in Y's frame, "the guard exits 0 for `ok` and 2
  for `refuse`, printing the declared line"): the `read: mirror at <sha12>`
  line, the declared line in place of the cause, and exit 0. The guard runs
  in the lane's window with a live session record (T203c's
  `guard_session`), the lane's row's session id as its own, so it reaches
  its direct read (lane 3's T507 ruling (1)), and the mirror's row binds it.
  ITS CONTRAST, in the same step: the same session, its id and name, in a
  window named for the other workstation's lane, whose row names another
  session as AT-D20's `refuse` row does, gets the same two lines and exit 2,
  for that row's own cause alone: it ends on that lane's session and does
  not name this one at all, with no Amendment 18(h) duplicate (T276h). So
  the mirror's own row decides, a 0 that only fails open cannot pass, and
  neither can a 2 for another cause. T276 compared the exit with a
  reference instead, the same guard with a `mode=index` copy of the
  configuration. Once the cutover has put `lanes/STORE` on origin,
  `mode=index` refuses 2 whatever the session, by design (F17,
  `reg_marker_check`'s `guard` arm), so no bound lane's 0 could equal it
  (lane 5, #165 6868723007; lane 2's choice (a), T276g).
  THE CONTRAST'S CAUSE IS A PIN: it holds the guard's own sentence word for
  word, from the last `guard_refuse_start` in `lanes-edit.sh`'s `guard_run`,
  the name table's last arm ("whose row does not name this uuid at all"):
  `lanes-edit.sh:21565` on line R's merge106 (`bc9ed80b`), `:21515` on
  merge104 (`142afd90`) and `:21493` on merge101 (`44f487d1`), where T276h
  took it character for character. A change of that sentence fails step
  6's contrast, so change the two together (T276i).
- STEP 6'S REFUSAL names the database as `register_url=` gives it, without
  credentials (lane 3, #165 6809045090 and 6812459759, as the outage module
  holds AT-P3's oracle), and its stderr carries no password.
- WHICH STEPS EACH TEST RUNS: `test_the_drill_import_cutover_outage_rollback_
  and_files_mode_write` runs all ten. `test_a_workstation_not_yet_cleared_
  refuses_after_rollback` runs steps 1 to 4 and 8, then step 9's ws2 half
  with a fuller oracle. AT-F4's three run the order's steps they read: the
  freeze, the import, the cutover and the flips, and, for the two after the
  rollback, step 8; never steps 1, 4, 5, 6 or 7, whose oracles are AT-13's.
  So their rollback starts with the head at the cutover's seq: AT-F4's
  oracle names no write on primary, and its Order (B17 tasks:2544, "Order:
  waits for T229") has its tests fail until L1-A18, T326 and T327 alone,
  where step 4's write would also need lane 4's T415 and T416 (T276d,
  after line DR15's run on T326-m23 met T415's placeholder there).
- OPEN POINT 8'S POLL READS A FETCHED W: `status` reads `m` on W's
  `origin/main` as last fetched and never fetches (tasks:545), and no write
  on primary fetches W (D12), while the render pushes from the lane's `<c>`.
  So `wait_lag_0` fetches ws1's W with plain git before each poll (lane 3's
  ruling (a), #165 6833830078), as the drill's act, not a write's.
- STEP 10'S "EVERY OBJECT HAS AT MOST ONE HOLDER" is read for the objects the
  drill claims, across SQL's live holds and origin's logs, as T273b's
  `_claim_holders` reads one.

HELPERS COPIED, NEVER SHARED (a module's own): `_rows`, `_renders`,
`RENDER_SET`, `REGISTER_SEQ` and `LAG_0` from `test_sql_register_import.py`
(T211's and T272's, in this base); `CHECK_LINE` and `_checks` from
`test_sql_register_operator_tools.py` (T218), and `CACHED_MODULE` and
`CHECKED_HASH_COMPILE` from it (T218s, T218t); the hook's path rule and its
`changed` from T271's `GATE_HOOK` (`test_sql_register_divergence.py`, line
DV's `92fbaf27`); the guard's run and `_label` from T215's outage module
(line W4a); `MIRROR_LINE` from the readers module (line N1); the holders'
rule from T273b's `_claim_holders` (line RB); `_masked` from
`tests/pgcluster.py`. From the fixture and H's helpers, which each real-engine
module imports: `tls_cluster`, `ImportedRegister`, `PASSWORD_LINE`,
`ClusterError`, `flipped_copy`, `guard_session` and `guard_strip_env`.

THE PATH (wave 11's policy, mask and never drop): no call here drops a `PATH`
directory. Each workstation puts its fake `tmux`, its tools and the engine's
binaries first and keeps every inherited directory behind them, so its `psql`
is the server's and its `lanes-index` its own copy; nothing is masked.

Every wait here has a ceiling: each poll, `SETTLE_S`; each command, its
`timeout`; the guard, its 5 s kill. Every id is RE: it asks for the TLS
cluster, and without PostgreSQL 16 it skips with T205's banner.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from pgcluster import PASSWORD_LINE, ClusterError, ImportedRegister
from sql_register_helpers import flipped_copy, guard_session, guard_strip_env

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280, `tests/sql_register_gate.py`; task sets
#: version 12b's rule 11, opensoft/openRepoTools#165 6877673742), TEMPORARY:
#: T281 removes it in the last set. Where the gate is active, each id here is
#: skipped until every task its row names has landed, and the skip names them.
#: Each row is the fails-until clause of T276's Order (tasks:2544) in tasks.md
#: at lane 3's commit 17, 204145ae, L1-A18 as T121, the task that covers it,
#: as lane 2's plan GP-24 v2 (sha256 9600adda) gives it. Every id waits for
#: the "*" row; the drill itself also for T415, T416 and T507, and the
#: uncleared workstation's case for T415 and T416. AT-F4's three wait for
#: nothing more. Since T276k the two AT-13 ids also wait for T119: step 1,
#: which both run, counts `ready`'s fourteen checks, and check 14 is lane 1's
#: T119 follow-up 2 (T276's line, tasks:2537 at lane 3's commit 24, f9d6069e).
SQL_REGISTER_GATE_TABLE = {
    "*": ("T121", "T326", "T327"),  # every id: the tasks all its rows share
    "test_a_workstation_not_yet_cleared_refuses_after_rollback": ("T119", "T415", "T416"),  # T276; tasks:2544; T119: tasks:2537
    "test_the_drill_import_cutover_outage_rollback_and_files_mode_write": ("T119", "T415", "T416", "T507"),  # T276; tasks:2544; T119: tasks:2537
}

INDEXER = REPO / "lanes-index"

#: The register's schema, `register_schema=`'s default.
SCHEMA = "lanes_register"
#: The drill database's switch label: the bootstrap's `--label`, and each
#: configuration's `register_label=`.
LABEL = "register-drill"

#: Each workstation's engineer (`lanes-index login add <engineer>` makes
#: `lanes_w_<engineer>` and `lanes_r_<engineer>`), its name (Rule 10), its
#: lane, and that lane's row's session id in the fixture register (pgcluster's
#: `_test7_seed`), which its guard session takes as its own.
ENGINEERS = {"ws1": "drill_a", "ws2": "drill_b"}
WORKSTATIONS = {"ws1": "Eagle", "ws2": "Hawk"}
OPERATOR = "repoA-2"
WS2_LANE = "repoW-1"
SESSIONS = {OPERATOR: "aaaaaaaa-0003-4000-8000-00000000a003",
            WS2_LANE: "eeeeeeee-0002-4000-8000-00000000e002"}
#: The lane whose row the drain's last `PAUSED` write sets: LIVE at C, and
#: written by no other step.
DRAINED = "repoD-1"

#: The release `ready` checks the installed tools against (check 1's list).
RELEASE, ENV_NAME = "0.0.0-t276", "drill"
DIGEST_LIST = f"openRepoTools-{RELEASE}.sha256"
#: T124's module, which `flipped_copy` places beside a copy of `lanes-index`
#: (tasks:2853), and which check 1's list names since T347.
CACHED_MODULE = "lanes_index_main.py"
#: The install's compile of the module: checked-hash bytecode, as
#: `openRepoTools --install` writes it (T347), at `py_compile`'s own place.
#: Its `dfile` is the module's name, the filename check 1 compiles it under
#: (T347). `ReadyBench`'s, byte for byte (T218s, T218t).
CHECKED_HASH_COMPILE = ("import py_compile, sys; py_compile.compile(sys.argv[1], doraise=True, "
                        f"dfile={CACHED_MODULE!r}, "
                        "invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)")

#: The objects the drill claims: on primary from each workstation (step 5),
#: then in files mode after the rollback (step 9).
OBJECTS = {"ws1": "opensoft/repoQ#31", "ws2": "opensoft/repoQ#32",
           "ws1-files": "opensoft/repoQ#33", "ws2-files": "opensoft/repoQ#34"}

#: Step 6's declaration, on Brett's word (D20).
UNTIL = "2999-01-01T00:00:00Z"
WHY = "the drill: the register database is stopped"

#: AT-D9's `status` row, 8 s; step 6 holds it to twice that (timing rule 2).
STATUS_BOUND_S = 8
#: The prompt hook's kill timer.
GUARD_TIMEOUT = 5
#: The ceiling of every poll here: a render to reach origin, `status`'s lag.
SETTLE_S = 60
#: The declaration's file, beside the configuration (D20; config.md section 6).
OUTAGE_FILE = "register-outage"

DOT = chr(0xB7)

#: The render set (Q18 (A); CLI4.10 section 3.6), as T211's module has it.
RENDER_SET = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|archive/[^/]+\.md"
                        r"|log/(?!README\.md$)[^/]+\.md)$")
#: The trailer each mirror commit and each operator entry's commit carry.
REGISTER_SEQ = re.compile(r"^Register-Seq: ([0-9]+)$", re.M)
#: `status`'s lag line at a lag of 0, on primary (lane 1's T117).
LAG_0 = re.compile(r"^\s*lag:\s+0 seq", re.M)
#: One check's line of `ready` (T119's form).
CHECK_LINE = re.compile(r"^check (\d+): (ok|FAIL)\b:?[ \t]*(.*)$", re.M)
#: The `read: mirror` line (design S3): stderr, `read: mirror at <sha12>, ...`.
MIRROR_LINE = re.compile(r"^read: mirror at [0-9a-f]{12}, .*$", re.M)
#: The refusal's added name, after "the register could not be read (".
ADDED_NAME = re.compile(r"the register could not be read \(([^)]*)\)")
#: A holding line in a lane's log, and its lane.
HOLDS = re.compile(r"^(CLAIMED|TAKEOVER) \S+ lane ([^,\s]+),")
#: A password-file line's last field, hidden by `_masked`.
_SECRET_FIELD = re.compile(r"^(\*:\*:.*:)[^:\n]*$", re.M)


# ------------------------------------------------------------------ the ruleset's model
#: AT-F4'S MODEL OF THE ORGANISATION'S PUSH RULESET: T271's `GATE_HOOK` (test
#: 6's pre-receive hook, guarding exactly the render set and `lanes/STORE`),
#: with two things AT-F4's fixture adds. It is SWITCHED by a file the drill's
#: runbook steps set: off, it lets every push through. It LETS THE RENDERER'S
#: IDENTITY THROUGH: a push from a process tree that runs `lanes-index` (see
#: the readings). Each push is one JSON line of its log, with the switch's
#: state, who pushed, the process it found (`found`, null for `other`), the
#: processes it walked to find it (`walked`), and the outcome. So each AT-F4
#: failure, which prints the records, names the process the model saw, and a
#: refusal's stderr names the walk (lane 3, #165 6813027223).
RULESET_HOOK = r'''#!/usr/bin/env -S python3 -I
# T276's model of the organisation's push ruleset (AT-F4), from T271's model
# of the server-side gate (test 6): a model, since the suite cannot reach
# GitHub.
import json, os, re, subprocess, sys
SWITCH = SWITCH_PATH
LOG = LOG_PATH
TOP = TOP_PID
GUARDED = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|STORE|archive/.+"
                     r"|log/(?!README\.md$)[^/]+\.md)$")
ZERO = "0" * 40
RENDERER = "lanes-index"


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=True, timeout=60).stdout


def changed(old, new):
    revs = git("rev-list", new if old == ZERO else f"{old}..{new}").split()
    paths = set()
    for rev in revs:
        out = git("diff-tree", "--root", "--no-commit-id", "-r", "-m", "--no-renames",
                  "--name-only", "-z", rev)
        paths.update(p for p in out.split("\0") if p)
    return sorted(paths)


def parent(pid):
    """(the parent's pid, the first words of the process's argv)."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            stat = handle.read().decode("utf-8", "replace")
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            argv = [a.decode("utf-8", "replace") for a in handle.read().split(b"\0") if a]
        return int(stat.rsplit(") ", 1)[1].split()[1]), argv[:4]
    except (OSError, ValueError, IndexError):
        out = subprocess.run(["ps", "-o", "ppid=", "-o", "args=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=10).stdout.split()
        if not out:
            return 0, []
        return int(out[0]), out[1:5]


def pusher():
    """(who, found, walked): `renderer` where a process above this hook runs
    `lanes-index`, else `other`; `found`, that process as {"pid", "argv"},
    or None; and `walked`, each process the walk read, from the hook's
    parent up, each argv's first four words, so that a failure names what
    the model saw (lane 3's suggestion, #165 6813027223). The walk stops
    below `TOP`, the test's own process, which every push the drill makes
    descends from: no process the case did not start is read or logged."""
    pid, walked = os.getppid(), []
    for _ in range(64):
        if pid <= 1 or pid == TOP:
            break
        up, argv = parent(pid)
        seen = {"pid": pid, "argv": argv}
        walked.append(seen)
        if any(os.path.basename(word) == RENDERER for word in argv):
            return "renderer", seen, walked
        pid = up
    return "other", None, walked


def main():
    try:
        with open(SWITCH, encoding="utf-8") as handle:
            state = handle.read().strip()
    except OSError:
        state = "off"
    who, found, walked = pusher()
    pushes, hits = [], []
    for line in sys.stdin:
        old, new, ref = line.split()
        if new == ZERO:
            continue
        paths = changed(old, new)
        guarded = [p for p in paths if GUARDED.match(p)]
        pushes.append({"ref": ref, "old": old, "new": new, "paths": paths, "guarded": guarded})
        hits += guarded
    refused = state == "on" and bool(hits) and who != "renderer"
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"state": state, "pusher": who, "found": found,
                                 "walked": walked,
                                 "outcome": "refused" if refused else "accepted",
                                 "pushes": pushes}) + "\n")
    if refused:
        sys.stderr.write("t276 ruleset model: a push to the render set or lanes/STORE by "
                         "an identity other than the renderer's is refused: "
                         + ", ".join(sorted(set(hits))) + "; no lanes-index above the "
                         "hook, which walked: "
                         + " < ".join(f"{p['pid']} {' '.join(p['argv'])}" for p in walked)
                         + "\n")
        return 1
    return 0


sys.exit(main())
'''


def _private(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    return path


def _script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _masked(text: str) -> str:
    """`text` with each password-file line's password hidden."""
    return _SECRET_FIELD.sub(lambda m: m.group(1) + "<password>", text or "")


def _said(proc) -> str:
    return (f"exit {proc.returncode}\n--- stdout ---\n{_masked(proc.stdout)[-2000:]}"
            f"\n--- stderr ---\n{_masked(proc.stderr)[-2000:]}")


def _checks(text: str) -> dict:
    """`ready`'s check lines, by number: (`ok` or `FAIL`, the reason)."""
    return {int(m.group(1)): (m.group(2), m.group(3) or "") for m in CHECK_LINE.finditer(text)}


def _fields(path: Path) -> dict:
    return dict(line.split("=", 1) for line in
                path.read_text(encoding="utf-8").splitlines() if "=" in line)


def _label(fields: dict) -> str:
    """The declared line the guard prints in place of the cause (D20)."""
    return f"(declared outage {fields['utc']}: {fields['why']})"


def _rows(db, sql: str) -> list:
    """`sql`'s rows as JSON objects, in the register's schema, by `jsonb_agg`,
    whose text is one line."""
    out = db.psql(f"SET search_path TO {SCHEMA};\n"
                  f"SELECT coalesce(jsonb_agg(t), '[]'::jsonb) FROM ({sql}) t;\n").stdout
    return json.loads(out.strip().splitlines()[-1])


def _renders(db) -> dict:
    """SQL's own render (lane 1's T107, `render_file`) of every path in
    `files`, {path: bytes}."""
    return {r["path"]: base64.b64decode(r["b64"]) for r in _rows(
        db, "SELECT path, encode(render_file(path), 'base64') AS b64 FROM files ORDER BY path")}


class Ruleset:
    """`RULESET_HOOK` in origin's `hooks/`, its switch file and its log, both
    beside origin and never in a work tree, and this test's own pid, where
    the hook's walk stops. It starts off."""

    def __init__(self, root: Path, origin: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.switch, self.log = root / "ruleset-state", root / "ruleset.log"
        self.off()
        _script(origin / "hooks" / "pre-receive",
                RULESET_HOOK.replace("SWITCH_PATH", repr(str(self.switch)))
                .replace("LOG_PATH", repr(str(self.log)))
                .replace("TOP_PID", str(os.getpid())))

    def on(self) -> None:
        self.switch.write_text("on\n", encoding="utf-8")

    def off(self) -> None:
        self.switch.write_text("off\n", encoding="utf-8")

    def state(self) -> str:
        return self.switch.read_text(encoding="utf-8").strip()

    def records(self) -> list:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()
                if line]

    def record_of(self, sha: str) -> list:
        """The records of each push that moved a ref to `sha`."""
        return [r for r in self.records() if any(p["new"] == sha for p in r["pushes"])]


class Person:
    """A person's clone of origin, for AT-F4's probes: plain `git` with an
    identity of its own, outside every lane tool, so the model sees no
    renderer above its push."""

    def __init__(self, root: Path, origin: Path):
        self.root, self.clone = root, root / "clone"
        (root / "home").mkdir(parents=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "LANES_", "PG"))}
        env.update(HOME=str(root / "home"), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="A person",
                   GIT_AUTHOR_EMAIL="person@example.invalid", GIT_COMMITTER_NAME="A person",
                   GIT_COMMITTER_EMAIL="person@example.invalid")
        self.env = env
        self.git("clone", "-q", str(origin), str(self.clone), cwd=root)

    def git(self, *args: str, cwd: Path | None = None, check: bool = True):
        proc = subprocess.run(["git", *args], cwd=str(cwd or self.clone), env=self.env,
                              capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, check=False)
        if check:
            assert proc.returncode == 0, f"the person's git {' '.join(args[:2])}:\n{_said(proc)}"
        return proc

    def push(self, path: str, text: str) -> tuple:
        """One commit on origin's tip adding `text` to `path`, pushed to
        `main`: (the push, the commit)."""
        self.git("fetch", "-q", "origin")
        self.git("reset", "-q", "--hard", "origin/main")
        target = self.clone / path
        target.parent.mkdir(parents=True, exist_ok=True)
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(old + text, encoding="utf-8")
        self.git("add", "--", path)
        self.git("commit", "-q", "-m", f"a person's edit of {path}")
        sha = self.git("rev-parse", "HEAD").stdout.strip()
        return self.git("push", "-q", "origin", "HEAD:main", check=False), sha


# ------------------------------------------------------------------ the workstations
class Workstation:
    """One workstation of the drill (see the module's notes): its `$HOME`, its
    register checkout and W, its configuration, its installed tools, and the
    environment each of its commands runs in, as its lane, on its name."""

    def __init__(self, drill: "Drill", name: str, lane: str, *, home: Path | None = None,
                 checkout: Path | None = None):
        self.drill, self.name, self.lane = drill, name, lane
        self.engineer, self.workstation = ENGINEERS[name], WORKSTATIONS[name]
        self.root = drill.root / name
        self.root.mkdir(parents=True)
        if home is None:
            home = self.root / "home"
            checkout = home / "projects" / "wip"
            checkout.parent.mkdir(parents=True)
            drill.git("clone", "-q", str(drill.origin), str(checkout))
            # W, a view of the checkout (Amendment 23 S5), which
            # `workspace.yaml` names, so `LANES_REPO` is never W.
            w = self.root / "ro" / "wip"
            w.mkdir(parents=True)
            (w / ".git").write_text(f"gitdir: {os.path.realpath(checkout / '.git')}\n",
                                    encoding="utf-8")
            (w / "lanes").symlink_to(checkout / "lanes")
            (home / ".agents").mkdir(parents=True)
            (home / ".agents" / "workspace.yaml").write_text(
                f"repository: {drill.origin}\npath: {w}\n", encoding="utf-8")
        self.home, self.checkout = home, checkout
        # W, as this workstation's `workspace.yaml` names it: ws1's is the
        # estate's, ws2's the view above. Its lane's `<c>` goes beside it.
        named = [line[len("path:"):].strip() for line in
                 (home / ".agents" / "workspace.yaml").read_text(encoding="utf-8").splitlines()
                 if line.startswith("path:")]
        assert len(named) == 1, f"[estate] {name}'s workspace.yaml names no one W: {named}"
        self.w = Path(named[0])
        # THE INSTALLED TOOLS: the flipped copy, its companions, check 1's list.
        self.tools = self.root / "tools"
        try:
            self.copy = flipped_copy(INDEXER, self.tools, True)
        except ValueError as exc:
            raise AssertionError(f"[estate] lanes-index cannot be flipped to its git half "
                                 f"({exc}): lane 1's RENDER_GIT_HALF (T105) has not "
                                 f"landed") from exc
        for companion in ("lanes-edit.sh", "lanes", "lane-start", "repos.tsv"):
            if (REPO / companion).exists():
                shutil.copy2(REPO / companion, self.tools / companion)
        # T124's module, where `flipped_copy` placed it beside the copy: check
        # 1's list names it, as the release's does since T347, and its
        # checked-hash bytecode is written as the install writes it, with the
        # interpreter `lanes-index` runs on here, as `ReadyBench` does (T218s,
        # T218t). Before T124 there is no module, and nothing changes (T276l).
        cached = (CACHED_MODULE,) if (self.tools / CACHED_MODULE).exists() else ()
        if cached:
            subprocess.run([sys.executable, "-I", "-c", CHECKED_HASH_COMPILE,
                            str(self.tools / CACHED_MODULE)], check=True, capture_output=True,
                           timeout=120, stdin=subprocess.DEVNULL)
        (self.tools / DIGEST_LIST).write_text("".join(
            f"{hashlib.sha256((self.tools / tool).read_bytes()).hexdigest()}  {tool}\n"
            for tool in ("lanes-index", "lanes-edit.sh") + cached), encoding="utf-8")
        self.fakebin = self.root / "fakebin"
        _script(self.fakebin / "tmux", "#!/bin/sh\nexit 1\n")
        for directory in ("state", "config", "tmp"):
            (self.root / directory).mkdir()
        self.conf = _private(self.root / "conf" / "lanes-index.conf", self.conf_text("index"))
        cluster = drill.cluster
        env = guard_strip_env(os.environ, strip=("XDG_", "GIT_", "EMAIL", "WORKBENCHES_"))
        inherited = [entry for entry in os.environ.get("PATH", os.defpath).split(os.pathsep)
                     if entry]
        env.update(
            HOME=str(home), AGENT_PROTOCOL_ROOT=str(home / ".agents"),
            TMPDIR=str(self.root / "tmp"), XDG_STATE_HOME=str(self.root / "state"),
            XDG_CONFIG_HOME=str(self.root / "config"), CLAUDE_CONFIG_DIR=str(home / ".claude"),
            LANES_WORKSTATION=self.workstation, LANES_HOST=self.workstation.lower(),
            LANES_OS="linux", LANES_CONTAINER="none", LANES_IN_CONTAINER="0",
            LANES_NO_GITHUB="1", LANES_REPO=str(checkout),
            LANES_EDIT=str(self.tools / "lanes-edit.sh"), LANES_INDEX_CONFIG=str(self.conf),
            LANES_LANE=lane, GIT_AUTHOR_NAME=f"Drill {self.engineer}",
            GIT_AUTHOR_EMAIL=f"{self.engineer}@example.invalid",
            GIT_COMMITTER_NAME=f"Drill {self.engineer}",
            GIT_COMMITTER_EMAIL=f"{self.engineer}@example.invalid",
            GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
            PATH=os.pathsep.join([str(self.fakebin), str(self.tools), str(cluster.bindir),
                                  *inherited]))
        self.env = env
        self._session = None

    def lane_checkout(self) -> Path:
        """`<c>`, THIS LANE'S OWN REGISTER CHECKOUT (the module's notes; lane
        3's batch g Q119, #165 6813027223): `<W>-lanes/<lane>`, W being the
        real path of `workspace.yaml`'s `path:`, as `lanes-edit.sh`'s
        `lane_checkout_path` puts it (Amendment 23 S1). A clone of origin, as
        `lane-checkout <lane> --create` makes one, in LX's T253f style; one
        that is already there is kept."""
        real = Path(os.path.realpath(self.w))
        target = real.parent / f"{real.name}-lanes" / self.lane
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            self.drill.git("clone", "-q", str(self.drill.origin), str(target))
        return target

    # ------------------------------------------------------------ configuration
    def conf_text(self, mode: str) -> str:
        """The 0600 configuration's text at `mode`: this engineer's two logins
        over TLS (lane 1's URL form, `verify-full` and the root alone), their
        password files, the label, the schema, and check 13's count."""
        cluster, database = self.drill.cluster, self.drill.db.name
        writer, reader = f"lanes_w_{self.engineer}", f"lanes_r_{self.engineer}"
        return "\n".join([
            f"mode={mode}", f"register_url={cluster.url(writer, database)}",
            f"register_passfile={cluster.passfile(writer)}",
            f"reader_url={cluster.url(reader, database)}",
            f"reader_passfile={cluster.passfile(reader)}", f"register_label={LABEL}",
            f"register_schema={SCHEMA}", "register_addresses=1", ""])

    def conf_state(self) -> tuple:
        return (self.conf.read_text(encoding="utf-8").splitlines(),
                self.conf.stat().st_mode & 0o777)

    def outage_file(self) -> Path:
        return self.conf.parent / OUTAGE_FILE

    # ------------------------------------------------------------ commands
    def _env(self, env: dict | None) -> dict:
        child = dict(self.env)
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return child

    def index(self, *args: str, env: dict | None = None,
              timeout: float = 300) -> subprocess.CompletedProcess:
        """This workstation's `lanes-index`, in its checkout, as its lane."""
        return subprocess.run([sys.executable, str(self.copy), *args], cwd=str(self.checkout),
                              env=self._env(env), capture_output=True, text=True,
                              timeout=timeout, stdin=subprocess.DEVNULL, check=False)

    def edit(self, *args: str, env: dict | None = None,
             timeout: float = 300) -> subprocess.CompletedProcess:
        """This workstation's `lanes-edit.sh`, in its checkout, as its lane."""
        return subprocess.run(["bash", str(self.tools / "lanes-edit.sh"), *args],
                              cwd=str(self.checkout), env=self._env(env), capture_output=True,
                              text=True, timeout=timeout, stdin=subprocess.DEVNULL, check=False)

    def lanes(self) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(self.tools / "lanes"), "--all"],
                              cwd=str(self.checkout), env=self._env(None), capture_output=True,
                              text=True, timeout=120, stdin=subprocess.DEVNULL, check=False)

    def git(self, *args: str) -> str:
        proc = subprocess.run(["git", "-C", str(self.checkout), *args], env=self.env,
                              capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0, f"git {' '.join(args[:2])} in {self.name}:\n{_said(proc)}"
        return proc.stdout

    def tip(self) -> str:
        return self.git("rev-parse", "refs/remotes/origin/main").strip()

    def fetch_w(self) -> None:
        """THE READER'S FETCH OF W (lane 3's ruling (a), #165 6833830078):
        `git -C <W> fetch -q origin main`, with plain git, so that `status`,
        which reads `m` on W's `origin/main` as last fetched and never
        fetches (tasks:545), reads the render the lane's `<c>` pushed. It is
        the drill's own act, not a write's (D12)."""
        proc = subprocess.run(["git", "-C", str(self.w), "fetch", "-q", "origin", "main"],
                              env=self.env, capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0, (
            f"the harness's fetch of {self.name}'s W, git -C {self.w} fetch -q origin "
            f"main:\n{_said(proc)}")

    def lanes_files(self) -> dict:
        """The bytes of every file under `lanes/` in the work tree, by digest."""
        return {str(p.relative_to(self.checkout)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((self.checkout / "lanes").rglob("*")) if p.is_file()}

    # ------------------------------------------------------------ the guard
    def guard_session(self):
        """The lane's live session (T203c), its row's session id as its own,
        in a window named for the lane; ended with the test."""
        if self._session is None:
            self._session = guard_session(self.home, self.root / "guard-bin", self.checkout,
                                          window=self.lane, session_id=SESSIONS[self.lane])
            self.drill.request.addfinalizer(self._session.close)
        return self._session

    def guard(self, session=None) -> dict:
        """The hook, `lanes-edit.sh guard`, in the window of `session` (the
        lane's own, `guard_session`, where None), under its 5 s kill timer,
        in a process group of its own."""
        if session is None:
            session = self.guard_session()
        base = self._env({"LANES_INDEX_CONFIG": str(self.conf), "LANES_LANE": self.lane})
        env = session.env(base)
        proc = subprocess.Popen(["bash", str(self.tools / "lanes-edit.sh"), "guard"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, cwd=str(self.checkout),
                                env=env, start_new_session=True)
        killed = False
        try:
            out, err = proc.communicate(session.hook_input(), timeout=GUARD_TIMEOUT)
        except subprocess.TimeoutExpired:
            killed = True
            os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate(timeout=30)
        return {"exit": None if killed else proc.returncode, "killed": killed,
                "out": out + err, "err": err}

    def guard_in_another_window(self, window: str) -> dict:
        """STEP 6'S CONTRAST (the module's notes): the same guard, on the same
        checkout and configuration, for the lane's own session, its id and
        name, in a window named `window`, another lane's, which the stand-in
        `tmux` answers `#W` with (`guard_session`). The lane's own session
        ends first, so one live process holds the transcript (Amendment
        18(h)). The contrast's session then stays live until its finalizer
        ends it with the test, so a later `guard()` on this workstation
        would start a second live process on the same transcript, a second
        holder; none follows the contrast today (lane 5, #165 6870260047)."""
        if self._session is not None:
            self._session.close()
            self._session = None
        session = guard_session(self.home, self.root / f"guard-bin-{window}", self.checkout,
                                window=window, session_id=SESSIONS[self.lane], name=self.lane)
        self.drill.request.addfinalizer(session.close)
        return self.guard(session)


# ------------------------------------------------------------------ the drill
class Drill:
    """TEST 13'S ESTATE and its steps, each with its labelled assertions (see
    the module's notes). `k` is the head when the rollback starts; `cut` is
    the cutover's seq; `marker` the marker commit."""

    def __init__(self, request, root: Path):
        # Without an engine, T205's `pg_engine` skips first, with its banner.
        request.getfixturevalue("pg_engine")
        self.request, self.root = request, root
        self.cluster = request.getfixturevalue("tls_cluster")
        try:
            self.db = self.cluster.second_database(label=LABEL)
        except ClusterError as exc:
            raise AssertionError(f"[estate] the drill's database, bootstrapped through the admin "
                                 f"service with --label {LABEL} (T109): {exc}") from exc
        for engineer in ENGINEERS.values():
            self._login_add(engineer)
        try:
            self.estate = ImportedRegister(root / "estate", self.cluster.bindir)
        except ClusterError as exc:
            raise AssertionError(f"[estate] test 7's fixture register on a bare origin "
                                 f"(T227b): {exc}") from exc
        self.origin = self.estate.origin
        self.ruleset = Ruleset(root / "ruleset", self.origin)
        self.ws1 = Workstation(self, "ws1", OPERATOR, home=self.estate.home,
                               checkout=self.estate.wip)
        self.ws2 = Workstation(self, "ws2", WS2_LANE)
        self.both = (self.ws1, self.ws2)
        self.c = self.cut = self.marker = self.k = self.removal = None
        #: The journal's count and origin's tip as step 6 stops the cluster.
        self.stopped = None

    def _login_add(self, engineer: str) -> None:
        """`lanes-index login add <engineer>` through the admin service on the
        drill's database, under a pty (lane 1's T110): its two password lines
        are kept in the cluster's memory, never printed."""
        service = self.cluster.admin_service(self.db.name)
        code, out, err = self.cluster.lanes_index_tty(
            ["login", "add", engineer, "--admin-service", service])
        assert code == 0, (f"[estate] `lanes-index login add {engineer}` exited {code} (lane 1's "
                           f"T110, L1-A8): {_masked(out)[-400:]} | {_masked(err)[-400:]}")
        found = dict(PASSWORD_LINE.findall(out))
        wanted = (f"lanes_w_{engineer}", f"lanes_r_{engineer}")
        assert all(login in found for login in wanted), (
            f"[estate] `login add {engineer}` printed no password line for "
            f"{[login for login in wanted if login not in found]}")
        self.cluster.passwords.update({login: found[login] for login in wanted})

    # ------------------------------------------------------------ origin and SQL
    def git(self, *args: str, cwd: Path | None = None) -> str:
        proc = subprocess.run(["git", *args], cwd=str(cwd or self.root), env=self.estate.env,
                              capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0, f"git {' '.join(args[:2])}:\n{_said(proc)}"
        return proc.stdout

    def origin_git(self, *args: str) -> str:
        """git in the bare origin itself, so no checkout's refs move."""
        return self.git(f"--git-dir={self.origin}", *args)

    def origin_tip(self) -> str:
        return self.origin_git("rev-parse", "refs/heads/main").strip()

    def on_origin(self, path: str, rev: str = "refs/heads/main") -> bool:
        return path in self.origin_git("ls-tree", "-r", "--name-only", rev, "lanes/").split()

    def seqs_of(self, sha: str) -> list:
        return [int(s) for s in REGISTER_SEQ.findall(self.origin_git("log", "-1", "--format=%B",
                                                                     sha))]

    def commits_after(self, base: str) -> list:
        """[(commit, its Register-Seq values)] on origin's `main` after `base`,
        oldest first, first parents only."""
        out = self.origin_git("rev-list", "--reverse", "--first-parent",
                              f"{base}..refs/heads/main")
        return [(sha, self.seqs_of(sha)) for sha in out.split()]

    def origin_seqs(self) -> list:
        out = self.origin_git("log", "--reverse", "--format=%B%x00", "refs/heads/main")
        return [int(s) for body in out.split("\0") for s in REGISTER_SEQ.findall(body)]

    def head(self) -> int:
        return _rows(self.db, "SELECT seq FROM register_head")[0]["seq"]

    def switch(self) -> dict:
        return _rows(self.db, "SELECT mode, marker_state, marker_seq, marker_commit "
                              "FROM register_switch")[0]

    def journal(self) -> list:
        return [[r["seq"], r["kind"], r["operator"]] for r in
                _rows(self.db, "SELECT seq, kind, operator FROM journal ORDER BY seq")]

    def count(self) -> int:
        return _rows(self.db, "SELECT count(*) AS n FROM journal")[0]["n"]

    def mirror_problem(self, rev: str = "refs/heads/main") -> str | None:
        """None where origin's render set at `rev` equals a full render from
        SQL, byte for byte; else what differs."""
        on_origin = {}
        for path in self.origin_git("ls-tree", "-r", "--name-only", rev, "lanes/").split():
            if RENDER_SET.match(path):
                on_origin[path] = subprocess.run(
                    ["git", f"--git-dir={self.origin}", "show", f"{rev}:{path}"],
                    capture_output=True, env=self.estate.env, timeout=60, check=True,
                    stdin=subprocess.DEVNULL).stdout
        from_sql = {p: b for p, b in _renders(self.db).items() if RENDER_SET.match(p)}
        if on_origin == from_sql:
            return None
        differ = sorted(p for p in on_origin if p in from_sql and on_origin[p] != from_sql[p])
        return (f"paths on one side only: {sorted(set(on_origin) ^ set(from_sql))}; paths that "
                f"differ: {differ}")

    def wait_for_seq(self, seq: int, label: str) -> None:
        """Poll origin's `main` until a commit carries `Register-Seq: <seq>`."""
        deadline = time.monotonic() + SETTLE_S
        while seq not in self.origin_seqs():
            assert time.monotonic() < deadline, (
                f"{label}: no commit on origin's main carries Register-Seq: {seq} within "
                f"{SETTLE_S} s (the render a write forks: lane 4's T416, lane 3's T321 to T323): "
                f"{self.origin_seqs()[-6:]}")
            time.sleep(0.25)

    def wait_lag_0(self, ws: Workstation, label: str) -> None:
        """Open point 8's poll: `status` until it shows a lag of 0, each poll
        after the harness's fetch of the W `status` reads (`fetch_w`; lane
        3's ruling (a), #165 6833830078): `status` never fetches, and no
        write on primary fetches W."""
        deadline = time.monotonic() + SETTLE_S
        while True:
            ws.fetch_w()
            proc = ws.index("status", timeout=120)
            if LAG_0.search(proc.stdout):
                return
            assert time.monotonic() < deadline, (
                f"{label}: `status` on {ws.name}, each read after a fetch of its W, shows no "
                f"lag of 0 within {SETTLE_S} s (open point 8):\n{_said(proc)}")
            time.sleep(0.25)

    def settled(self, label: str) -> None:
        """After a write on primary: its render on origin, a lag of 0, the
        mirror byte-identical to SQL, and one commit per seq since the
        marker."""
        head = self.head()
        self.wait_for_seq(head, label)
        self.wait_lag_0(self.ws1, label)
        problem = self.mirror_problem()
        assert problem is None, f"{label}: the mirror is not byte-identical to SQL: {problem}"
        after = self.commits_after(self.marker)
        assert [seqs for _sha, seqs in after] == [[n] for n in range(self.cut + 1, head + 1)], (
            f"{label}: origin does not carry one commit per seq from {self.cut + 1} to {head}: "
            f"{after}")

    # ------------------------------------------------------------ the steps
    def step_1_ready(self) -> None:
        """`ready --expect index` passes in ws1 and ws2, every check `ok`."""
        for ws in self.both:
            proc = ws.index("ready", "--expect", "index", "--release", RELEASE, "--env", ENV_NAME)
            checks = _checks(proc.stdout)
            assert proc.returncode == 0, (
                f"[step 1] `ready --expect index` fails in {ws.name} (lane 1's T119; the TLS "
                f"cluster, T229; the logins, T110):\n{_said(proc)}")
            assert sorted(checks) == list(range(1, 15)) and all(
                state == "ok" for state, _ in checks.values()), (
                f"[step 1] not every check of the fourteen is ok in {ws.name} (check 14, git "
                f"2.32 or later, is lane 1's T119 follow-up 2):\n{_said(proc)}")

    def freeze(self, *, ruleset: bool = True) -> str:
        """The drain's last `PAUSED` write, in files mode from ws2 as the
        drained lane, pushed; then the ruleset on, unless `ruleset` is False.
        Returns the write's commit on origin."""
        before = self.origin_tip()
        proc = self.ws2.edit("set-row-state", DRAINED, f"PAUSED {DOT} the drill's freeze",
                             env={"LANES_LANE": DRAINED})
        assert proc.returncode == 0, (
            f"[freeze] the last PAUSED write, a files-mode set-row-state of {DRAINED}, "
            f"failed:\n{_said(proc)}")
        paused = self.origin_tip()
        assert paused != before, "[freeze] the last PAUSED write was not pushed to origin"
        row = [line for line in self.origin_git("show", f"{paused}:lanes/LANES.md").splitlines()
               if f"`{DRAINED}`" in line]
        assert row and "PAUSED" in row[0], f"[freeze] {DRAINED}'s row on origin: {row}"
        if ruleset:
            self.ruleset.on()
        return paused

    def step_2_import(self) -> None:
        """`import --at C` from ws1, C origin's tip, proves its render."""
        self.ws1.git("fetch", "-q", "origin")
        self.ws1.git("merge", "-q", "--ff-only", "refs/remotes/origin/main")
        self.c = self.origin_tip()
        proc = self.ws1.index("import", "--at", self.c, timeout=400)
        assert proc.returncode == 0, (
            f"[step 2] `import --at {self.c[:12]}` from ws1 failed (lane 1's T115, "
            f"L1-A13):\n{_said(proc)}")
        seq0 = _rows(self.db, "SELECT seq, kind, git_commit FROM journal ORDER BY seq")
        assert seq0 == [{"seq": 0, "kind": "import", "git_commit": self.c}], (
            f"[step 2] the journal after the import is {seq0}, not the one import at C")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), (
            f"[step 2] the import moved the switch: {switch}")
        problem = self.mirror_problem(self.c)
        assert problem is None, f"[step 2] SQL's render is not C's: {problem}"

    def step_3_cutover_and_flips(self) -> None:
        """The cutover sets the switch and pushes the marker; then `set-mode
        primary` in each workstation changes only that line, and the file
        stays 0600. Each workstation, once flipped, has its lane's own
        register checkout, made after the cutover's push (`lane_checkout`)."""
        proc = self.ws1.index("cutover", "--import", self.c)
        assert proc.returncode == 0, (
            f"[step 3] `cutover --import {self.c[:12]}` failed (lane 1's T116, "
            f"L1-A14):\n{_said(proc)}")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), (
            f"[step 3] after the cutover the switch reads {switch['mode']} with the marker "
            f"{switch['marker_state']}: the marker's push, its read-back and record_marker are "
            f"lane 3's T327, so the drill fails until it lands")
        self.cut = _rows(self.db, "SELECT seq FROM journal WHERE kind = 'cutover'")[0]["seq"]
        self.marker = self.origin_tip()
        assert self.on_origin("lanes/STORE") and self.seqs_of(self.marker) == [self.cut], (
            f"[step 3] origin's tip {self.marker[:12]} is not the marker commit carrying "
            f"lanes/STORE and Register-Seq: {self.cut}")
        assert switch["marker_commit"] == self.marker, (
            f"[step 3] record_marker recorded {switch['marker_commit']}, not origin's tip")
        for ws in self.both:
            lines, mode = ws.conf_state()
            flip = ws.index("set-mode", "primary", "--config", str(ws.conf))
            assert flip.returncode == 0, (
                f"[step 3] `set-mode primary` in {ws.name} failed (lane 1's T120):\n{_said(flip)}")
            after, mode_after = ws.conf_state()
            assert after == ["mode=primary" if line == "mode=index" else line for line in lines], (
                f"[step 3] the flip in {ws.name} changed more than the mode= line: "
                f"{lines} -> {after}")
            assert mode == mode_after == 0o600, f"[step 3] {ws.name}'s file is {oct(mode_after)}"
            ws.lane_checkout()

    def step_4_smoke_test(self) -> None:
        """R3b's smoke test: `log NOTED` gives its row at the cutover's seq
        plus 1, a mirror commit carrying it, and a lag of 0."""
        proc = self.ws1.edit("log", "NOTED", f"lane:{OPERATOR}", "the drill's smoke test")
        assert proc.returncode == 0, (
            f"[step 4] `log NOTED` on primary from ws1 failed (lane 4's T415):\n{_said(proc)}")
        rows = _rows(self.db, f"SELECT seq, kind, lane FROM journal WHERE seq > {self.cut} "
                              f"ORDER BY seq")
        assert rows == [{"seq": self.cut + 1, "kind": "write", "lane": OPERATOR}], (
            f"[step 4] the smoke test's row is not the cutover's seq plus 1: {rows}")
        self.settled("[step 4]")

    def step_5_writes_from_both(self) -> None:
        """`claim` and `log` from both workstations; after each, the mirror
        is byte-identical and origin has one commit per seq."""
        for ws in self.both:
            for verb, args in (("claim", ["claim", OBJECTS[ws.name], "--no-github"]),
                               ("log", ["log", "NOTED", f"lane:{ws.lane}",
                                        f"the drill: a write from {ws.name}"])):
                count = self.count()
                proc = ws.edit(*args)
                assert proc.returncode == 0, (
                    f"[step 5] `{verb}` on primary from {ws.name} failed (lane 4's "
                    f"T415):\n{_said(proc)}")
                assert self.count() == count + 1, f"[step 5] {ws.name}'s {verb} journaled no entry"
                self.settled(f"[step 5] after {ws.name}'s {verb}")

    def step_6_outage(self) -> None:
        """The cluster stopped: writes 69, the guard's refusal, the mirror
        line, `status` inside twice its bound, then the declaration, after
        which the guard answers from the mirror: 0 for the lane's bound
        session (AT-D20), and 2 for the same session in a window named for
        the other workstation's lane, whose row names another session (the
        contrast; the module's notes)."""
        self.stopped = (self.count(), self.origin_tip())
        for ws in self.both:
            ws.git("fetch", "-q", "origin")
        self.cluster.stop()
        for ws in self.both:
            wrote = ws.edit("log", "NOTED", f"lane:{ws.lane}", "the drill: during the outage")
            assert wrote.returncode == 69, (
                f"[step 6] a write on {ws.name} with the cluster stopped is not 69 (lane 4's "
                f"T415):\n{_said(wrote)}")
            refused = ws.guard()
            out = refused["out"]
            assert not refused["killed"] and refused["exit"] == 2, (
                f"[step 6] the guard on {ws.name} did not exit 2 inside 5 s (lane 5's T507): "
                f"exit {refused['exit']}: {_masked(out)[-600:]}")
            added = ADDED_NAME.search(out)
            assert added and self.db.name in added.group(1), (
                f"[step 6] the guard's refusal on {ws.name} does not name the database as "
                f"register_url= gives it (T507): {_masked(out)[-600:]}")
            users = [user for user in (f"lanes_w_{ws.engineer}", f"lanes_r_{ws.engineer}")
                     if user in added.group(1)]
            assert users == [], (
                f"[step 6] the guard's added name carries a URL's user, {users}: "
                f"{added.group(1)!r}")
            for words in ("lanes-index status", "lanes-index rollback", "CLAUDE_NO_LANE=1"):
                assert words in out, (
                    f"[step 6] the guard's refusal on {ws.name} does not carry {words!r} (P3; "
                    f"T507): {_masked(out)[-600:]}")
            secrets = [self.cluster.passwords[f"lanes_{half}_{ws.engineer}"] for half in "wr"]
            assert not any(secret in refused["err"] for secret in secrets), (
                f"[step 6] the guard's stderr on {ws.name} carries its engineer's password")
            listing = ws.lanes()
            assert MIRROR_LINE.search(listing.stderr), (
                f"[step 6] `lanes` on {ws.name} prints no `read: mirror` line (lane 5's "
                f"T505):\n{_said(listing)}")
            start = time.monotonic()
            status = ws.index("status", timeout=120,
                              env={"CLAUDE_NO_LANE": "1", "LANES_LANE": None, "TMUX": None,
                                   "TMUX_PANE": None})
            elapsed = time.monotonic() - start
            assert elapsed < 2 * STATUS_BOUND_S, (
                f"[step 6] `status` on {ws.name} took {elapsed:.2f} s, not inside twice AT-D9's "
                f"{STATUS_BOUND_S} s (lane 1's T117)")
            assert status.returncode == 69 and (LABEL in status.stdout + status.stderr or
                                                self.db.name in status.stdout + status.stderr), (
                f"[step 6] `status` on {ws.name} does not answer 69 naming the store (lane 1's "
                f"T117):\n{_said(status)}")
        for ws, other in zip(self.both, self.both[::-1]):
            declared = ws.index("outage", "declare", "--until", UNTIL, "--why", WHY)
            path = ws.outage_file()
            assert declared.returncode == 0 and path.exists(), (
                f"[step 6] `outage declare` on {ws.name} declared nothing (lane 1's T121, "
                f"L1-A18):\n{_said(declared)}")
            fields = _fields(path)
            assert (fields.get("kind"), fields.get("database"), fields.get("host")) == (
                "word", LABEL, ws.workstation), f"[step 6] {ws.name}'s declaration: {fields}"
            mirror = f"read: mirror at {ws.tip()[:12]}"
            answered = ws.guard()
            out = answered["out"]
            assert not answered["killed"], f"[step 6] the declared guard on {ws.name} was killed"
            assert mirror in out and _label(fields) in out, (
                f"[step 6] under the declaration the guard on {ws.name} does not answer from the "
                f"mirror with the declared line (lane 5's T507, SVC-12): {_masked(out)[-600:]}")
            assert answered["exit"] == 0, (
                f"[step 6] under the declaration the guard on {ws.name}, its lane's bound session "
                f"in its lane's window, exits {answered['exit']}, not AT-D20's 0 for a bound lane "
                f"(lane 5's T507, SVC-12): {_masked(out)[-600:]}")
            # THE CONTRAST: the same session in a window named for the other
            # workstation's lane, whose row on the mirror names that lane's
            # session, not this one, so the mirror's row refuses it.
            contrast = ws.guard_in_another_window(other.lane)
            out = contrast["out"]
            assert not contrast["killed"], (
                f"[step 6] the declared guard on {ws.name} in {other.lane}'s window was killed")
            assert mirror in out and _label(fields) in out, (
                f"[step 6] under the declaration the guard on {ws.name}, in a window named "
                f"{other.lane}, does not answer from the mirror with the declared line (lane 5's "
                f"T507, SVC-12): {_masked(out)[-600:]}")
            # Its own cause, in the guard's words (`lanes-edit.sh`'s table, the
            # row that names no such uuid; a pin, whose place the module's
            # notes name), not only the row's session, which the triple's
            # `row` line of any refusal after the row's read carries too,
            # Amendment 18(h)'s duplicate among them (lane 5, #165
            # 6870260047).
            cause = (f"this window is lane {other.lane}, whose row ends on "
                     f"{SESSIONS[other.lane]} and does not name {SESSIONS[ws.lane]} at all")
            assert (contrast["exit"] == 2 and cause in out
                    and "ANOTHER LIVE PROCESS" not in out), (
                f"[step 6] under the declaration the guard on {ws.name}, for its lane's session "
                f"in a window named {other.lane}, does not refuse 2 from the mirror's row for "
                f"that row's own cause alone, {cause!r}: exit {contrast['exit']}: "
                f"{_masked(out)[-600:]}")

    def step_7_rollback_refused_while_down(self) -> None:
        """A rollback with the cluster stopped is refused and changes nothing;
        the cluster restarts, and `outage clear` removes step 6's
        declaration on both workstations."""
        count, tip = self.stopped
        kept = self.ws1.outage_file().read_bytes()
        proc = self.ws1.index("rollback")
        port = self.cluster.port
        self.cluster.start_again()
        assert self.cluster.port == port, (
            f"[step 7] the TLS cluster came back on port {self.cluster.port}, not {port}, so the "
            f"configurations no longer name it")
        assert proc.returncode == 69, (
            f"[step 7] a rollback with the cluster stopped is not refused 69 (T304):\n"
            f"{_said(proc)}")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), (
            f"[step 7] the refused rollback moved the switch: {switch}")
        assert (self.count(), self.origin_tip()) == (count, tip), (
            "[step 7] the outage's writes or the refused rollback changed the journal or origin")
        assert self.on_origin("lanes/STORE"), "[step 7] lanes/STORE left origin"
        assert self.ws1.outage_file().read_bytes() == kept, (
            "[step 7] the refused rollback replaced step 6's declaration")
        for ws in self.both:
            cleared = ws.index("outage", "clear")
            assert cleared.returncode == 0 and not ws.outage_file().exists(), (
                f"[step 7] `outage clear` on {ws.name} left the declaration (lane 1's T121):\n"
                f"{_said(cleared)}")

    def step_8_rollback(self) -> None:
        """Rollback from ws1 as the operator lane: its start declares the
        outage; `--hold-marker` stops with the mirror proved current and the
        marker still on origin while the ruleset is on; the ruleset goes off;
        the rerun pushes the removal; then `set-mode index` clears ws1 alone
        (AT-F4's oracle; operations.md 2.3)."""
        self.k = k = self.head()
        assert self.ruleset.state() == "on", "[step 8] the ruleset is not on at the rollback"
        hold = self.ws1.index("rollback", "--hold-marker")
        assert hold.returncode == 0, (
            f"[step 8] `rollback --hold-marker` did not stop 0 at step 3 (lane 3's T326):\n"
            f"{_said(hold)}")
        path = self.ws1.outage_file()
        assert path.exists(), "[step 8] the rollback's start declared no outage (T121, T304)"
        fields = _fields(path)
        assert (fields.get("kind"), fields.get("mirror-seq")) == ("rollback", str(k)), (
            f"[step 8] the declaration is not the rollback's at mirror-seq {k}: {fields}")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("files", "removing"), (
            f"[step 8] at --hold-marker the switch is {switch}, not files with the marker "
            f"removing (T304, T326)")
        assert self.journal()[-1] == [k + 1, "rollback", True], (
            f"[step 8] the journal's last entry is not the rollback's at {k + 1}: "
            f"{self.journal()[-3:]}")
        assert self.on_origin("lanes/STORE"), (
            "[step 8] AT-F4: --hold-marker pushed the removal of lanes/STORE before the "
            "ruleset was off")
        assert k in self.origin_seqs(), f"[step 8] the mirror does not hold k = {k} (T326's step 2)"
        problem = self.mirror_problem()
        assert problem is None, f"[step 8] the mirror is not proved current at k: {problem}"
        self.ruleset.off()
        rerun = self.ws1.index("rollback")
        assert rerun.returncode == 0, (
            f"[step 8] the rerun after --hold-marker did not end 0 (lane 3's T326):\n"
            f"{_said(rerun)}")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), (
            f"[step 8] after the rerun the switch is {switch}, not files with the marker absent")
        self.removal = self.origin_tip()
        assert self.seqs_of(self.removal) == [k + 1], (
            f"[step 8] origin's tip does not carry the rollback's Register-Seq: {k + 1}")
        changed = self.origin_git("diff-tree", "--no-commit-id", "--name-status", "-r",
                                  f"{self.removal}^", self.removal)
        assert changed.split("\n") == ["D\tlanes/STORE", ""], (
            f"[step 8] origin's last commit does not remove lanes/STORE alone: {changed!r}")
        records = self.ruleset.record_of(self.removal)
        assert records and all(r["state"] == "off" and r["outcome"] == "accepted"
                               for r in records), (
            f"[step 8] AT-F4: the removal was not pushed after the ruleset was off: {records}")
        lines, mode = self.ws1.conf_state()
        flip = self.ws1.index("set-mode", "index", "--config", str(self.ws1.conf))
        assert flip.returncode == 0, f"[step 8] `set-mode index` on ws1 (T120):\n{_said(flip)}"
        after, mode_after = self.ws1.conf_state()
        assert after == ["mode=index" if line == "mode=primary" else line for line in lines], (
            f"[step 8] the flip on ws1 changed more than the mode= line: {lines} -> {after}")
        assert mode_after == 0o600, f"[step 8] ws1's file is {oct(mode_after)}"
        assert "mode=primary" in self.ws2.conf_state()[0], (
            "[step 8] the flip on ws1 cleared ws2 too")

    def files_mode_write(self, ws: Workstation, label: str, *args: str) -> str:
        """A files-mode write on `ws` that exits 0 and is pushed: one commit
        on origin's `main`, with no `Register-Seq`. Returns it."""
        before = self.origin_tip()
        proc = ws.edit(*args)
        assert proc.returncode == 0, f"{label}: the files-mode write on {ws.name}:\n{_said(proc)}"
        after = self.commits_after(before)
        assert len(after) == 1 and after[0][1] == [], (
            f"{label}: the files-mode write on {ws.name} is not one pushed commit with no "
            f"Register-Seq: {after}")
        return after[0][0]

    def step_9_files_mode_writes(self) -> None:
        """A files-mode `claim` on ws1 exits 0 and is pushed; a write on ws2,
        not yet cleared, exits 69; once cleared, its files-mode write exits 0."""
        sha = self.files_mode_write(self.ws1, "[step 9]", "claim", OBJECTS["ws1-files"],
                                    "--no-github")
        log = self.origin_git("show", f"{sha}:lanes/log/{OPERATOR}.md")
        assert any(line.startswith("CLAIMED") and OBJECTS["ws1-files"] in line
                   for line in log.splitlines()), (
            f"[step 9] ws1's files-mode claim is not in {OPERATOR}'s log on origin")
        count, tip = self.count(), self.origin_tip()
        refused = self.ws2.edit("claim", OBJECTS["ws2-files"], "--no-github")
        assert refused.returncode == 69, (
            f"[step 9] a write on ws2, not yet cleared, is not 69, ended at its snapshot "
            f"(lane 4's T415):\n"
            f"{_said(refused)}")
        assert (self.count(), self.origin_tip()) == (count, tip), (
            "[step 9] ws2's refused write changed the journal or origin")
        flip = self.ws2.index("set-mode", "index", "--config", str(self.ws2.conf))
        assert flip.returncode == 0, f"[step 9] `set-mode index` on ws2 (T120):\n{_said(flip)}"
        self.files_mode_write(self.ws2, "[step 9] once ws2 is cleared", "claim",
                              OBJECTS["ws2-files"], "--no-github")

    def holders(self, obj: str) -> set:
        """The lanes holding `obj`, across SQL's live claims and origin's logs
        (a lane whose log's last line naming it is a CLAIMED or TAKEOVER)."""
        rows = _rows(self.db, f"SELECT lane FROM object_holds WHERE lower(object) = "
                              f"lower('{obj}') AND verb IN ('CLAIMED', 'TAKEOVER') AND "
                              f"superseded_by IS NULL")
        held = {r["lane"] for r in rows}
        for path in self.origin_git("ls-tree", "-r", "--name-only", "refs/heads/main",
                                    "lanes/log/").split():
            last = None
            for line in self.origin_git("show", f"refs/heads/main:{path}").splitlines():
                if obj.lower() in line.lower():
                    last = line
            match = HOLDS.match(last or "")
            if match:
                held.add(match.group(2))
        return held

    def step_10_the_end(self) -> None:
        """Origin carries no `lanes/STORE`; its files are the rollback's last
        render plus the files-mode commits after it; every object the drill
        claimed has at most one holder."""
        assert not self.on_origin("lanes/STORE"), "[step 10] origin still carries lanes/STORE"
        problem = self.mirror_problem(self.removal)
        assert problem is None, (
            f"[step 10] the rollback's last commit is not a full render from SQL (T326): {problem}")
        after = self.commits_after(self.removal)
        assert len(after) == 2 and all(seqs == [] for _sha, seqs in after), (
            f"[step 10] origin's commits after the rollback's are not step 9's two files-mode "
            f"writes: {after}")
        for obj in OBJECTS.values():
            held = self.holders(obj)
            assert len(held) <= 1, f"[step 10] {obj} has more than one holder: {sorted(held)}"


# =================================================================== AT-13
def test_the_drill_import_cutover_outage_rollback_and_files_mode_write(request, tmp_path):
    """AT-13, the drill (TP's "The sequence, and its oracle at each step"):
    the readiness check, the freeze with the ruleset on, the import at C, the
    cutover and the flips, R3b's smoke test, writes from both workstations,
    the outage with its refusals and its declaration, a rollback refused
    while the cluster is down, the rollback through `--hold-marker`, the
    files-mode writes, and the end state. Each step's assertions carry its
    number. Fails until L1-A18, T326 and T327 land, and each step's own tasks
    (the module's notes); on `V-round5` it stops at step 3, T327."""
    drill = Drill(request, tmp_path)
    drill.step_1_ready()
    drill.freeze()
    drill.step_2_import()
    drill.step_3_cutover_and_flips()
    drill.step_4_smoke_test()
    drill.step_5_writes_from_both()
    drill.step_6_outage()
    drill.step_7_rollback_refused_while_down()
    drill.step_8_rollback()
    drill.step_9_files_mode_writes()
    drill.step_10_the_end()


def test_a_workstation_not_yet_cleared_refuses_after_rollback(request, tmp_path):
    """AT-13's second test: after the rollback, which `set-mode index`
    cleared on ws1 alone, ws2, still `mode=primary`, exits 69 for `claim`
    and for `log`, and changes neither the journal, nor origin, nor its own
    files under `lanes/`; once `set-mode index` clears it, its files-mode
    write exits 0 and is pushed. Runs the drill's steps 1 to 4 and 8. Fails
    until L1-A18, T326 and T327 land, and lane 4's T415 and T416."""
    drill = Drill(request, tmp_path)
    drill.step_1_ready()
    drill.freeze()
    drill.step_2_import()
    drill.step_3_cutover_and_flips()
    drill.step_4_smoke_test()
    drill.step_8_rollback()
    ws2 = drill.ws2
    count, tip, files = drill.count(), drill.origin_tip(), ws2.lanes_files()
    for verb, args in (("claim", ["claim", OBJECTS["ws2"], "--no-github"]),
                       ("log", ["log", "NOTED", f"lane:{ws2.lane}", "not yet cleared"])):
        proc = ws2.edit(*args)
        assert proc.returncode == 69, (
            f"[not yet cleared] ws2's {verb} after the rollback is not 69, ended at its "
            f"snapshot (lane 4's T415):\n"
            f"{_said(proc)}")
    assert drill.count() == count, "[not yet cleared] ws2's refused writes journaled"
    assert drill.origin_tip() == tip, "[not yet cleared] ws2's refused writes moved origin"
    assert ws2.lanes_files() == files, "[not yet cleared] ws2's files under lanes/ changed"
    flip = ws2.index("set-mode", "index", "--config", str(ws2.conf))
    assert flip.returncode == 0, f"[cleared] `set-mode index` on ws2 (T120):\n{_said(flip)}"
    drill.files_mode_write(ws2, "[cleared]", "log", "NOTED", f"lane:{ws2.lane}",
                           "cleared after the rollback")


# =================================================================== AT-F4
def test_the_ruleset_goes_on_after_the_last_paused_write_and_before_the_import(request,
                                                                               tmp_path):
    """AT-F4, the ruleset on: the last `PAUSED` write is pushed while the
    model is off; with it on, a person's push to a rendered path is refused,
    and so is one to `lanes/STORE`, while a push that changes only
    `lanes/repos.tsv`, or only `lanes/log/README.md`, goes through; the
    import, the cutover (its marker pushed through the model as the
    renderer's) and the flips succeed, and the model refused no files-mode
    write, only the two probes. Fails until L1-A18, T326 and T327 land; on
    `V-round5` it stops at the cutover's marker, T327."""
    drill = Drill(request, tmp_path)
    paused = drill.freeze(ruleset=False)
    records = drill.ruleset.record_of(paused)
    assert records and all(r["state"] == "off" and r["outcome"] == "accepted" for r in records), (
        f"[AT-F4] the last PAUSED write was not pushed before the ruleset was on: {records}")
    drill.ruleset.on()
    person = Person(tmp_path / "person", drill.origin)
    probes = []
    for path, text, accepted in (
            ("lanes/log/repoB-1.md", "a person's line in a rendered log\n", False),
            ("lanes/STORE", "store=primary\ndatabase=register-drill\n", False),
            ("lanes/repos.tsv", "repoQ\topensoft/repoQ\n", True),
            ("lanes/log/README.md", "a person's note\n", True)):
        before = drill.origin_tip()
        pushed, sha = person.push(path, text)
        if accepted:
            assert pushed.returncode == 0 and drill.origin_tip() == sha, (
                f"[AT-F4] a push that changes only {path} was refused:\n{_said(pushed)}")
        else:
            assert pushed.returncode != 0 and drill.origin_tip() == before, (
                f"[AT-F4] a person's push to {path} was not refused with the ruleset on:\n"
                f"{_said(pushed)}")
            probes.append(sha)
        found = drill.ruleset.record_of(sha)
        assert [r["outcome"] for r in found] == ["accepted" if accepted else "refused"], (
            f"[AT-F4] the model's record of the push to {path}: {found}")
    drill.step_2_import()
    drill.step_3_cutover_and_flips()
    marked = drill.ruleset.record_of(drill.marker)
    assert marked and all(r["state"] == "on" and r["pusher"] == "renderer"
                          and r["outcome"] == "accepted" for r in marked), (
        f"[AT-F4] the cutover's marker was not pushed through the ruleset as the renderer's: "
        f"{marked}")
    refused = [r for r in drill.ruleset.records() if r["outcome"] == "refused"]
    assert sorted(p["new"] for r in refused for p in r["pushes"]) == sorted(probes), (
        f"[AT-F4] the model refused a push other than the two probes: {refused}")


def test_the_rollback_turns_the_ruleset_off_before_the_marker_removal_is_pushed(request,
                                                                                tmp_path):
    """AT-F4, the ruleset off: after the freeze, the import, the cutover and
    the flips, `rollback --hold-marker` exits 0 with the mirror proved
    current at the cutover's seq and the marker still on origin, the switch
    at `files` and the marker `removing`, while the model is on; it is then
    switched off, and the rerun pushes the removal and ends with the marker
    `absent` (the drill's step 8, whose assertions are AT-F4's). No write on
    primary comes between, since AT-F4's oracle names none (T276d; see the
    module's notes). Fails until L1-A18, T326 and T327 land."""
    drill = Drill(request, tmp_path)
    drill.freeze()
    drill.step_2_import()
    drill.step_3_cutover_and_flips()
    drill.step_8_rollback()


def test_a_files_mode_write_after_the_rollback_is_pushed(request, tmp_path):
    """AT-F4, after the removal: once the rollback has run through
    `--hold-marker` and its rerun with the model off, and `set-mode index`
    has cleared ws1, a files-mode write on ws1 exits 0 and is pushed, one
    commit with no `Register-Seq` that the model let through. As in the
    test above, no write on primary comes before the rollback (T276d).
    Fails until L1-A18, T326 and T327 land."""
    drill = Drill(request, tmp_path)
    drill.freeze()
    drill.step_2_import()
    drill.step_3_cutover_and_flips()
    drill.step_8_rollback()
    sha = drill.files_mode_write(drill.ws1, "[AT-F4]", "log", "NOTED", f"lane:{OPERATOR}",
                                 "a files-mode write after the rollback")
    records = drill.ruleset.record_of(sha)
    assert records and all(r["outcome"] == "accepted" for r in records), (
        f"[AT-F4] the files-mode write after the rollback was not let through: {records}")
