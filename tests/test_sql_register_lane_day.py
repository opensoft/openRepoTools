# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 11: a lane's day on `mode=primary` (L2-G5; AT-11; T275;
FR-025, FR-036, FR-059; also US9) (opensoft/openRepoTools#165).

T275 writes this module (B15 tasks:2520, "Write test 11, a lane's day on
`mode=primary`"): AT-11's 11 tests, with the ids its `verify:` names. The
test plan's ids are kept where the verify names a function bare
(`[75|3|69]` and `[resume|new-lane]`, TP:2222-2223), so the verify's 30 node
arguments collect 33 items.

THE ESTATE, `LaneDay` (the test plan's AT-11, "Fixture"):

- A STOPPABLE CLUSTER (test 8's, `stoppable_cluster`), with a database of the
  case's own holding test 7's fixture register imported at C
  (`CutoverRegister`, T211/T272's, in `test_sql_register_import.py`, which
  this module imports as the rollback module does), and, for every case but
  the read-mirror ids, the cutover made by `prepare()`: the switch `primary`
  with the marker `present` (T116 and lane 3's T327).
- A BARE ORIGIN, the fixture register's, with a handoff file for each lane
  the cases hand off (`handoffs/<lane>.md`), pushed after C. A handoff
  commit on the tip never aborts the cutover (T272's own case).
- ONE WORKSTATION, `Eagle`: the register's `$HOME`, its `mode=primary`
  configuration (`primary_conf`), the read-only W (`ro/wip`, a view of the
  clone), and `<W>-lanes/<lane>/` for every lane a case writes for, a clone
  of origin where `lanes-edit.sh`'s `lane_checkout_path` puts it (Amendment
  23 S1; T241e's `make_lane_checkout`; lane 3, #165 6813027223). The lane
  acts run with `LANES_REPO` unset, so each write resolves its own lane's
  checkout. The installed-tools directory is T203's flipped copy's
  (`RENDER_GIT_HALF = True`, standing for lane 3's T328), with
  `lanes-edit.sh`, `lanes`, `lane`, `lane-start`, `lane-handoff`,
  `lane-end`, `lane-worktrees` and `repos.tsv` beside it.
- THE FAKE `claude` AND FAKE `tmux` the code leg's `lane-start` tests already
  use (`test_lane_start_claude_current.py`: `FAKE_TMUX`, `FAKE_CLAUDE`,
  `FAKE_GH` and the resolver `FAKE_CLAUDE_CURRENT`), and a launcher that logs.
- A LANE NOT YET IN THE REGISTER, `repoN-1`, the day's lane.
- THE STAMP SHIM (section 3.2; AT-11's fixture): `STAMP_FRONT` is the `psql`
  first on `PATH`. It reads its ancestors' command lines (`ps -o
  ppid=,args=`), and a call made under `lanes-edit.sh <verb>`, for a verb
  the case names (`start-record`, or `canon-lane` for ADV-C5), goes to the
  ARMED section 3.2 shim (`PSQL_SHIM`, in `armed/`); every other call goes to
  an unarmed one (`plain/`), which only logs and hands on to the real
  `psql`. So `act-begin`'s snapshot and the deciding reads, which come before
  `start-record`, reach the database and pass. Where a case gives it an
  `answer` (the LR010 case), the front answers the armed call itself.

THE DAY (AT-11, "The day"): `lane-start` for the new lane, `lane-handoff`,
`lane-start` resuming the lane, `claim`, `HOLD`, `LANDING`, `LANDED`,
`lane-handoff`, `lane-end`. Each act waits for its forked render, open point
8's bounded poll of `status` until the lag is 0, before the next.

WHAT EACH FAILS UNTIL. B15's Order (tasks:2536): it waits for T205; its tests
fail until L4-B9 (lane 4's T427 and T428), L4-B14 (T429 to T431) and T328
land, the note's until lane 4's T415 and T428, the read-mirror case's until
lane 4's T405 and T406 and lane 5's T504, and the whole test until Amendment
23's slices 2a, 2b and 3. Each labelled assertion also names the tasks its
own step rests on, by their B15 bullets: the import (T115), the cutover and
its marker (T116; lane 3's T327); a write on primary (T415), its render fork
(T416) and the renderer (lane 3's T321 to T323); `status`'s lag (T117);
`claim` on primary (T421). On lane 1's merge20 (`4353eb08`), which holds T115,
T116, T117, T504 and T321 to T323 but not T327, T427, T428 or T415, every
case on a prepared estate stops at the cutover's labelled assertion (the
marker `adding`, T327).

READINGS, NOT FOUND IN A CONTRACT:
- "THE DATABASE DOWN" is the case's own cluster stopped (`stop()`), and "after
  the restart" its `start_again()`; the workstation's configuration names the
  cluster's socket throughout.
- "THE ROW READS `SWAPPING`" is the lane's lifecycle as `lanes-edit.sh
  lane-state <lane>` prints it, its `state` field.
- "THE RULE 3 STAMP COMMIT" is a commit on origin whose subject is
  `handoff(<lane>@<ws>): RESUMED by <uuid>` (`lane-start`'s header, Rule 3 +
  Amendment 8).
- "THE REGISTER HOLDS NONE OF THE THREE LINES": the journal's head does not
  move, and SQL's render of the lane's log holds no new `RESUMED` line.
- A NEW LANE'S "NO ROW" is read in both stores: SQL's render of
  `lanes/LANES.md` after the restart, and origin's.
- "THE FAKE `lanes-edit.sh`'s LOG" (R-F13-2) is `LoggedEdit`, a `LANES_EDIT`
  that logs each call's argv and then runs the flipped copy's
  `lanes-edit.sh`; a `PAUSED` write is any call whose argv holds `PAUSED`.
- THE 69 NOTE (P15; T429's "The 69 note", B15 tasks:1375) names `lane-handoff
  --late --at`; THE LATE `PAUSED` PATH is that command, run from a shell once
  the database is back.
- THE LR010 ANSWER (AT-11, "Any other 2") is the front's own: exit 3 and
  `ERROR:  LR010: key: ... which is not a scope (...)`, for the first call
  under `start-record` that carries `commit_write`.

HELPERS COPIED, NEVER SHARED: `_said`, `_script`, `_jsonl` and the
`_assert_rendered` oracle from T273b's rollback module (line RB, this
base); `MIRROR_LINE`'s form from the readers module (line N1, `e2000cca`),
narrowed to YS:626's `(sql unreachable: `; `place_transcript` from the same
module; the `<W>-lanes/<lane>` rule from T241e's `PrimaryWorkstation`
(`test_sql_register_writes.py`, `V-round5`). From this base, by import:
`CutoverRegister`, `_rows`, `_renders`, `RENDER_SET`, `REGISTER_SEQ` and
`LAG_0` (the import module), the fakes of `test_lane_start_claude_current.py`,
`PSQL_SHIM` and its file names (`sql_register_helpers`), and `Database`.

THE PATH (wave 11's policy, mask and never drop): no call here drops a
`PATH` directory. Each act puts the stamp front, the fakes and the tools
first and keeps the register's own `PATH` behind them (the import module's
`Workspace`, whose list leaves out only a directory holding a `lanes-index`).

Every wait here has a ceiling: each poll, `SETTLE_S`; each command, its
`timeout`. Every id is RE: it asks for a stoppable cluster, and without
PostgreSQL 16 it skips with T205's banner.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from pgcluster import Database
from sql_register_helpers import PSQL_SHIM, PSQL_SHIM_CONTROL, PSQL_SHIM_LOG
from test_lane_start_claude_current import (FAKE_CLAUDE, FAKE_CLAUDE_CURRENT, FAKE_GH,
                                            FAKE_TMUX, _write)

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None or shutil.which("ps") is None,
    reason="the lane tooling is bash over git, and the stamp shim reads ps")]

EM, ARROW, DOT = chr(0x2014), chr(0x2192), chr(0x00B7)
WS = "Eagle"
#: THE DAY'S LANE, not yet in the register (AT-11's fixture).
DAY_REPO, DAY_N = "repoN", "1"
DAY_LANE = f"{DAY_REPO}-{DAY_N}"
#: THE RESUMED LANE of the stamp shim's cases: the fixture's `repoA-1`,
#: `PAUSED`, its row's session `UUID_A1`.
RESUME_REPO, RESUME_N = "repoA", "1"
RESUME_LANE = f"{RESUME_REPO}-{RESUME_N}"
#: THE LANE THE OUTAGE CASES ACT AS: the operator lane, `LIVE` here.
OUTAGE_LANE = "repoA-2"
#: The object `claim` names, held by no lane at C.
CLAIMED = "opensoft/repoQ#11"
#: Each poll's ceiling.
SETTLE_S = 60.0
#: The deadline the stamp shim's 75 and 3 cases set (AT-11; lane 4's corrected
#: table, comment 6709560550).
DEADLINE_ENV = {"LANES_REGISTER_DEADLINE_S": "1"}

#: A mirror read's label (YS:626; R-Q22-4): `read: mirror at `, 12 hex digits,
#: then `(sql unreachable: `, on stderr.
MIRROR_LINE = re.compile(r"^read: mirror at [0-9a-f]{12}, .*\(sql unreachable: ", re.M)
#: The writer's printed rerun, naming the write id and its generation.
RERUN = re.compile(r"LANES_WRITE_ID=([0-9a-f-]{36}) LANES_WRITE_GENERATION=([0-9a-f-]{36}) ")
#: The Rule 3 stamp commit's subject (`lane-start`'s header).
STAMP_SUBJECT = "handoff({lane}@{ws}): RESUMED by "
#: The 69 note's command (T429, "The 69 note"; P15).
LATE_COMMAND = "lane-handoff --late --at"
#: The texts the stamp shim keys on: the snapshot's one request, the commit
#: call, and the lookup (lane 1's T112 and T114, as the in_doubt module keys).
SNAPSHOT_TEXT, COMMIT_TEXT, LOOKUP_TEXT = "REPEATABLE READ READ ONLY", "commit_write", "find_write"
#: AT-11's "any other 2": the fake's answer to the commit call.
LR010 = ("ERROR:  LR010: key: lanes/log/{lane}.md line 3 derives obj:x, which is not a scope "
         "(T275's stand-in)\n")

STAMP_FRONT = r'''#!/usr/bin/env -S python3 -I
# AT-11'S STAMP SHIM FRONT (T275): the psql first on PATH. A call made under
# `lanes-edit.sh <verb>` for a verb stamp-front.json names goes to the armed
# section 3.2 shim in armed/, or is answered here where `answer` matches it;
# every other call goes to the unarmed shim in plain/.
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))


def ancestors():
    found, pid = [], os.getppid()
    while pid > 1 and len(found) < 64:
        proc = subprocess.run(["ps", "-o", "ppid=,args=", "-p", str(pid)],
                              capture_output=True, text=True)
        line = proc.stdout.strip()
        if proc.returncode != 0 or not line:
            break
        ppid, _, args = line.partition(" ")
        found.append(args.split())
        try:
            pid = int(ppid)
        except ValueError:
            break
    return found


def under(verbs):
    for argv in ancestors():
        for i, word in enumerate(argv[:-1]):
            if os.path.basename(word) == "lanes-edit.sh" and argv[i + 1] in verbs:
                return argv
    return None


def log(record):
    with open(os.path.join(HERE, "stamp-front.log"), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def main():
    with open(os.path.join(HERE, "stamp-front.json"), encoding="utf-8") as handle:
        control = json.load(handle)
    args = sys.argv[1:]
    if args == ["--version"]:
        os.execv(os.path.join(HERE, "plain", "psql"), [os.path.join(HERE, "plain", "psql")] + args)
    data = sys.stdin.buffer.read()
    argv = under(control.get("verbs", [])) if control.get("verbs") else None
    where = "armed" if argv else "plain"
    text = data.decode("utf-8", "surrogateescape")
    answer = control.get("answer") if argv else None
    if argv:
        log({"verbs": argv, "commit": "commit_write" in text, "answered": bool(
            answer and answer["match"] in text)})
    if answer and answer["match"] in text:
        sys.stderr.write(answer["stderr"])
        sys.stderr.flush()
        return int(answer["exit"])
    proc = subprocess.run([os.path.join(HERE, where, "psql")] + args, input=data)
    return proc.returncode


sys.exit(main())
'''

#: A `LANES_EDIT` that logs each call's argv, then runs the flipped copy's
#: `lanes-edit.sh` (R-F13-2's "fake `lanes-edit.sh`'s log").
LOGGED_EDIT = r'''#!/usr/bin/env bash
printf '%s\n' "$*" >> "$LOGGED_EDIT_LOG"
exec bash "$LOGGED_EDIT_REAL" "$@"
'''


def _imp():
    """`test_sql_register_import`: test 7's fixture register and cutover host."""
    import test_sql_register_import as module
    return module


def _said(proc) -> str:
    return f"exit {proc.returncode}\n--- stdout\n{proc.stdout[-3000:]}\n--- stderr\n{proc.stderr[-4000:]}"


def _script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def place_transcript(env: dict, lane_dir: Path, sid: str) -> None:
    """A transcript `<sid>.jsonl` in the projects directory for `lane_dir`,
    where `lane-start` looks for one, so the uuid is knowable."""
    here = (Path(env["CLAUDE_CONFIG_DIR"]) / "projects"
            / re.sub(r"[^A-Za-z0-9]", "-", str(lane_dir)))
    here.mkdir(parents=True, exist_ok=True)
    (here / f"{sid}.jsonl").write_text('{"type":"user"}\n', encoding="utf-8")


class LaneDay:
    """AT-11'S ESTATE: see the notes above. `prepare()` makes the cutover;
    until its tasks land it fails at its own assertion, naming them."""

    def __init__(self, root: Path, db, cluster):
        imp = _imp()
        self.imp, self.db, self.cluster, self.root = imp, db, cluster, root
        self.bin = root / "front"
        _script(self.bin / "psql", STAMP_FRONT)
        for where in ("armed", "plain"):
            _script(self.bin / where / "psql", PSQL_SHIM)
        self.arm()
        self.reg = imp.CutoverRegister(root / "ws", db, extra_path=self.bin)
        reg = self.reg
        self.tools = reg.copy.parent
        for name in ("lanes", "lane", "lane-start", "lane-handoff", "lane-end",
                     "lane-worktrees"):
            shutil.copy2(REPO / name, self.tools / name)
            (self.tools / name).chmod(0o755)
        self.edit_path = self.tools / "lanes-edit.sh"
        # THE FAKES (`test_lane_start_claude_current`'s), and a launcher that logs.
        self.fakebin = root / "fakebin"
        _write(self.fakebin / "tmux", FAKE_TMUX)
        _write(self.fakebin / "gh", FAKE_GH)
        _write(self.fakebin / "claude", FAKE_CLAUDE)
        _write(self.tools / "claude-current", FAKE_CLAUDE_CURRENT)
        self.resolved = _write(root / "resolved" / "bin" / "claude", FAKE_CLAUDE)
        self.claude_log, self.tmux_log = root / "claude.log", root / "tmux.log"
        self.cc_log, self.launcher_log = root / "claude-current.log", root / "launcher.log"
        for path in (self.claude_log, self.tmux_log, self.cc_log, self.launcher_log):
            path.write_text("", encoding="utf-8")
        launcher = _write(root / "launcher" / "pclaude",
                          f'#!/usr/bin/env bash\nprintf "pclaude %s\\n" "$*" >> '
                          f'"{self.launcher_log}"\nexit 0\n')
        # THE HANDOFFS each case hands off, after C, on origin.
        reg.commit({f"handoffs/{lane}.md": f"# {lane}'s handoff\n\nThe fixture's first block.\n"
                    for lane in (OUTAGE_LANE, RESUME_LANE, DAY_LANE)},
                   "the fixture's handoffs (T275)")
        # THE LANES' DIRECTORIES, each a git repository naming its home.
        self.lane_dirs = {}
        for repo in (DAY_REPO, RESUME_REPO):
            path = reg.home / "projects" / repo
            path.mkdir(parents=True, exist_ok=True)
            reg.run("git", "init", "-q", "-b", "main", str(path))
            reg.run("git", "-C", str(path), "remote", "add", "origin",
                    f"https://github.com/opensoft/{repo}.git")
            self.lane_dirs[repo] = path
        env = dict(reg.env)
        env.pop("LANES_REPO", None)
        env.pop("LANES_INDEX", None)
        env.update(
            LANES_EDIT=str(self.edit_path), LANES_INDEX_CONFIG=str(reg.primary_conf),
            PATH=os.pathsep.join([str(self.bin), str(self.fakebin), str(self.tools),
                                  reg.env["PATH"]]),
            TMUX=f"{root}/fake-tmux-socket,0,0", TMUX_PANE="%1",
            OPENREPOTOOLS_BIN_DIR=str(self.tools), PCLAUDE=str(launcher),
            FAKE_TMUX_LOG=str(self.tmux_log), FAKE_CLAUDE_LOG=str(self.claude_log),
            FAKE_CC_LOG=str(self.cc_log), FAKE_CC_PATH=str(self.resolved),
            PROJECTS_ROOT=str(reg.home / "projects"))
        self.env = env
        for lane in (OUTAGE_LANE, RESUME_LANE, DAY_LANE):
            self.make_lane_checkout(lane)
        self.prepared = False

    # ------------------------------------------------------------ the stamp shim
    def arm(self, verbs=(), arms=(), answer: dict | None = None) -> None:
        """The front's verbs and answer, and the armed shim's arms; every log
        started afresh."""
        control = {"verbs": list(verbs)}
        if answer:
            control["answer"] = answer
        (self.bin / "stamp-front.json").write_text(json.dumps(control), encoding="utf-8")
        (self.bin / "stamp-front.log").write_text("", encoding="utf-8")
        for where, its_arms in (("armed", list(arms)), ("plain", [])):
            d = self.bin / where
            (d / PSQL_SHIM_CONTROL).write_text(
                json.dumps({"psql": self.db.psql_bin, "arms": its_arms}), encoding="utf-8")
            for name in (PSQL_SHIM_LOG, "psql-shim.ends"):
                (d / name).write_text("", encoding="utf-8")
            (d / "psql-shim.state").write_text("{}", encoding="utf-8")

    def armed_calls(self) -> list:
        return [c for c in _jsonl(self.bin / "armed" / PSQL_SHIM_LOG) if c.get("kind") != "version"]

    def front_calls(self) -> list:
        return _jsonl(self.bin / "stamp-front.log")

    # ------------------------------------------------------------ the checkouts
    def lane_checkout(self, lane: str) -> Path:
        """`<c>`, `<W>-lanes/<lane>`, W being the real path of
        `workspace.yaml`'s `path:` (T241e)."""
        real = Path(os.path.realpath(self.reg.ws))
        return real.parent / f"{real.name}-lanes" / lane

    def make_lane_checkout(self, lane: str) -> Path:
        target = self.lane_checkout(lane)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            self.reg.run("git", "clone", "-q", str(self.reg.origin), str(target))
        return target

    # ------------------------------------------------------------ the database
    def rows(self, sql: str) -> list:
        return self.imp._rows(self.db, sql)

    def switch(self) -> dict:
        return self.rows("SELECT mode, marker_state, generation FROM register_switch")[0]

    def head(self) -> int:
        return self.rows("SELECT seq FROM register_head")[0]["seq"]

    def journal(self) -> list:
        return self.rows("SELECT seq, kind, verb, lane FROM journal ORDER BY seq")

    def rendered(self, path: str) -> str:
        """SQL's own render of `path` (T107's `render_file`), or '' where
        `files` holds no such path."""
        return self.imp._renders(self.db).get(path, b"").decode("utf-8", "replace")

    def row_session(self, lane: str) -> str | None:
        """The last session uuid in `lane`'s row, as SQL renders
        `lanes/LANES.md`, or None where it has no row."""
        for line in self.rendered("lanes/LANES.md").splitlines():
            if line.startswith(f"| `{lane}` |"):
                cells = line.split("|")
                found = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                                   cells[2] if len(cells) > 2 else "")
                return found[-1] if found else None
        return None

    def down(self) -> None:
        self.cluster.stop()

    def up(self) -> None:
        self.cluster.start_again()

    # ------------------------------------------------------------ origin
    def origin_tip(self) -> str:
        return self.reg.origin_tip()

    def origin_text(self, path: str, rev: str = "refs/heads/main") -> str:
        proc = subprocess.run(["git", f"--git-dir={self.reg.origin}", "show", f"{rev}:{path}"],
                              capture_output=True, env=self.reg.env, stdin=subprocess.DEVNULL)
        return proc.stdout.decode("utf-8", "replace") if proc.returncode == 0 else ""

    def origin_log(self, since: str) -> list:
        """[(sha, subject, body)] on origin's `main` after `since`, oldest first."""
        out = self.reg.origin_git("log", "--reverse", "--format=%H%x1f%s%x1f%B%x1e",
                                  f"{since}..refs/heads/main")
        return [tuple(rec.strip("\n").split("\x1f", 2)) for rec in out.split("\x1e")
                if rec.strip()]

    def lifecycle(self, lane: str) -> str:
        """`lane-state <lane>`'s `state` field, read on primary."""
        proc = self.edit("lane-state", lane)
        assert proc.returncode in (0, 8), f"lane-state {lane}:\n{_said(proc)}"
        for line in proc.stdout.splitlines():
            key, _, value = line.partition("\t")
            if key == "state":
                return value.strip()
        return ""

    # ------------------------------------------------------------ the commands
    def prepare(self) -> None:
        """The cutover: the switch `primary`, the marker `present`."""
        proc = self.reg.cutover()
        assert proc.returncode == 0, f"the cutover (T116) failed:\n{_said(proc)}"
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), (
            f"after the cutover the switch reads {switch['mode']} with the marker "
            f"{switch['marker_state']}: the marker's push, read-back and record_marker are lane "
            f"3's T327, so AT-11's estate fails until it lands")
        for lane in (OUTAGE_LANE, RESUME_LANE, DAY_LANE):
            subprocess.run(["git", "-C", str(self.lane_checkout(lane)), "pull", "-q", "--ff-only"],
                           env=self.reg.env, capture_output=True, stdin=subprocess.DEVNULL)
        self.prepared = True

    def run(self, argv: list, *, lane: str | None = None, env: dict | None = None,
            cwd: Path | None = None, timeout: float = 300) -> subprocess.CompletedProcess:
        child = dict(self.env)
        if lane is not None:
            child["LANES_LANE"] = lane
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True,
                              env=child, cwd=str(cwd or self.reg.ws), timeout=timeout,
                              stdin=subprocess.DEVNULL)

    def edit(self, *args, lane: str | None = None, env: dict | None = None,
             **kw) -> subprocess.CompletedProcess:
        return self.run(["bash", self.edit_path, *args], lane=lane, env=env, **kw)

    def files_edit(self, *args, lane: str | None = None, env: dict | None = None,
                   **kw) -> subprocess.CompletedProcess:
        """The same verb in files mode: no configuration (`LANES_INDEX_CONFIG`
        unset, `XDG_CONFIG_HOME` an empty directory of its own)."""
        empty = self.root / "no-config"
        empty.mkdir(exist_ok=True)
        merged = {"LANES_INDEX_CONFIG": None, "XDG_CONFIG_HOME": str(empty)}
        merged.update(env or {})
        return self.edit(*args, lane=lane, env=merged, **kw)

    def lane_start(self, repo: str, n: str, *more: str,
                   env: dict | None = None) -> subprocess.CompletedProcess:
        """`lane-start --dir <the lane's directory> <repo>-<n>`, in it."""
        lane_dir = self.lane_dirs[repo]
        return self.run([self.tools / "lane-start", "--dir", lane_dir, *more, f"{repo}-{n}"],
                        env=env, cwd=lane_dir)

    def lane_handoff(self, lane: str, why: str, *more: str,
                     env: dict | None = None) -> subprocess.CompletedProcess:
        return self.run([self.tools / "lane-handoff", *more, "--lane", lane, why], env=env)

    def lane_end(self, lane: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return self.run([self.tools / "lane-end", lane], env=env)

    def logged_env(self) -> tuple:
        """`LoggedEdit`: (the environment that names it, its log)."""
        log = self.root / "logged-edit.log"
        log.write_text("", encoding="utf-8")
        wrapper = _script(self.tools / "logged-edit", LOGGED_EDIT)
        return {"LANES_EDIT": str(wrapper), "LOGGED_EDIT_LOG": str(log),
                "LOGGED_EDIT_REAL": str(self.edit_path)}, log

    def settle(self, what: str) -> None:
        """Open point 8's bounded poll: `status` until the lag is 0."""
        deadline = time.monotonic() + SETTLE_S
        while True:
            proc = self.reg.index("status", conf=self.reg.primary_conf, timeout=60)
            if proc.returncode == 0 and self.imp.LAG_0.search(proc.stdout):
                return
            if time.monotonic() > deadline:
                raise AssertionError(
                    f"after {what}, `status` never read a lag of 0 within {SETTLE_S:.0f} s (the "
                    f"render fork, T416; the renderer, lane 3's T321 to T323; the lag, T117):\n"
                    f"{_said(proc)}")
            time.sleep(0.5)

    def claude_ran(self) -> bool:
        return bool(self.claude_log.read_text(encoding="utf-8").strip()
                    or self.launcher_log.read_text(encoding="utf-8").strip())

    def renamed(self) -> list:
        return [line for line in self.tmux_log.read_text(encoding="utf-8").splitlines()
                if line.startswith("rename-window")]


def _estate(request, tmp_path: Path, *, prepare: bool = True) -> LaneDay:
    """A `LaneDay` on a database of the case's own stoppable cluster, dropped
    at the case's end where the cluster is up."""
    cluster = request.getfixturevalue("stoppable_cluster")
    name = cluster.new_database()
    request.addfinalizer(lambda: cluster.drop_database(name) if cluster.ready() else None)
    estate = LaneDay(tmp_path / "day", Database(cluster, name), cluster)
    if prepare:
        estate.prepare()
    return estate


# ------------------------------------------------------------------ the oracles
def _origin_blob(estate: LaneDay, rev: str, path: str) -> bytes:
    proc = subprocess.run(["git", f"--git-dir={estate.reg.origin}", "show", f"{rev}:{path}"],
                          capture_output=True, env=estate.reg.env, check=True,
                          stdin=subprocess.DEVNULL)
    return proc.stdout


def _assert_rendered(estate: LaneDay, what: str) -> None:
    """AT-11, "After each act": origin's rendered paths equal a full render
    from SQL, byte for byte (T273b's oracle)."""
    imp, reg = estate.imp, estate.reg
    tip = reg.origin_tip()
    on_origin = {p: _origin_blob(estate, tip, p)
                 for p in reg.origin_git("ls-tree", "-r", "--name-only", tip, "lanes/").split()
                 if imp.RENDER_SET.match(p)}
    from_sql = {p: b for p, b in imp._renders(estate.db).items() if imp.RENDER_SET.match(p)}
    assert on_origin == from_sql, (
        f"after {what}, origin's rendered paths differ from a full render from SQL (the "
        f"renderer, lane 3's T321 to T323): {sorted(set(on_origin) ^ set(from_sql))} or "
        f"{sorted(p for p in on_origin if p in from_sql and on_origin[p] != from_sql[p])}")


def _seq_pairs(estate: LaneDay) -> dict:
    """{seq: the commit on origin's `main` carrying `Register-Seq: <seq>`}
    after C, with each seq's every carrier."""
    pairs = {}
    for sha, _subject, body in estate.origin_log(estate.reg.c):
        for seq in estate.imp.REGISTER_SEQ.findall(body):
            pairs.setdefault(int(seq), []).append(sha)
    return pairs


def _assert_seqs_once(estate: LaneDay, cutover_seq: int, what: str) -> None:
    """Each `Register-Seq` since the cutover appears exactly once, in order,
    and every seq the journal holds since it is there (a lag of 0)."""
    order = [int(seq) for _sha, _s, body in estate.origin_log(estate.reg.c)
             for seq in estate.imp.REGISTER_SEQ.findall(body)]
    since = [seq for seq in order if seq > cutover_seq]
    assert since == sorted(set(since)), (
        f"after {what}, a Register-Seq since the cutover appears twice or out of order on "
        f"origin's main: {since}")
    wanted = [r["seq"] for r in estate.journal() if r["seq"] > cutover_seq]
    assert since == wanted, (
        f"after {what}, origin's Register-Seq values since the cutover, {since}, are not the "
        f"journal's, {wanted} (the renderer, lane 3's T321 to T323)")


def _assert_pairs_kept(estate: LaneDay, kept: dict, what: str) -> None:
    """Every (seq, sha) pair recorded after earlier acts is still on origin's
    `main` with the same sha: no render commit was rewritten."""
    now = _seq_pairs(estate)
    for seq, shas in kept.items():
        assert now.get(seq) == shas, (
            f"after {what}, Register-Seq {seq} was on {shas} and is now on {now.get(seq)}: a "
            f"render commit was rewritten")


def _assert_handoff_commits_render_nothing(estate: LaneDay, what: str) -> None:
    """Each handoff commit (one with no `Register-Seq`) since C changes
    nothing under the rendered paths."""
    imp = estate.imp
    for sha, subject, body in estate.origin_log(estate.reg.c):
        if imp.REGISTER_SEQ.search(body):
            continue
        changed = estate.reg.origin_git("diff-tree", "--no-commit-id", "--name-only", "-r",
                                        sha).split()
        rendered = [p for p in changed if imp.RENDER_SET.match(p)]
        assert not rendered, (
            f"after {what}, the commit {sha[:12]} ({subject!r}), which carries no "
            f"Register-Seq, changes rendered paths: {rendered}")


# ------------------------------------------------------------------ the day
def _day_acts(estate: LaneDay) -> list:
    """AT-11's nine acts, as (name, a function that runs it)."""
    day_dir = estate.lane_dirs[DAY_REPO]

    def resume():
        session = estate.row_session(DAY_LANE)
        assert session, (f"no row for {DAY_LANE} naming a session in SQL's render after act 2 "
                         f"(L4-B9: lane 4's T427 and T428)")
        place_transcript(estate.env, day_dir, session)
        return estate.lane_start(DAY_REPO, DAY_N)

    def append(kind: str):
        session = estate.row_session(DAY_LANE) or "unknown"
        text = {
            "HOLD": f"HOLD {EM} lane {DAY_LANE} ({WS}), window w, {_utc()}: opensoft/repoN main "
                    f"{estate.imp.TIP_A} for test 11",
            "LANDING": f"LANDING {EM} lane {DAY_LANE}, session {session}@{WS}, {_utc()}, PR #11 "
                       f"into opensoft/repoN main",
            "LANDED": f"LANDED {EM} lane {DAY_LANE}, session {session}@{WS}, {_utc()}, PR #11 into "
                      f"opensoft/repoN main {ARROW} 1111111",
        }[kind]
        return estate.edit("append-line", text, lane=DAY_LANE, cwd=day_dir)

    return [
        ("act 1, lane-start for the new lane", lambda: estate.lane_start(DAY_REPO, DAY_N)),
        ("act 2, lane-handoff", lambda: estate.lane_handoff(DAY_LANE, "test 11: act 2")),
        ("act 3, lane-start resuming the lane", resume),
        ("act 4, claim", lambda: estate.edit("claim", CLAIMED, "--no-github", lane=DAY_LANE,
                                              cwd=day_dir)),
        ("act 5, HOLD", lambda: append("HOLD")),
        ("act 6, LANDING", lambda: append("LANDING")),
        ("act 7, LANDED", lambda: append("LANDED")),
        ("act 8, lane-handoff", lambda: estate.lane_handoff(DAY_LANE, "test 11: act 8")),
        ("act 9, lane-end", lambda: estate.lane_end(DAY_LANE)),
    ]


#: Which tasks each act's exit rests on, by their B15 bullets.
ACT_TASKS = {
    1: "L4-B9: lane 4's T427 and T428; the writer on primary, T415",
    2: "L4-B14: lane 4's T429; the writer on primary, T415",
    3: "L4-B9: lane 4's T427 and T428; T415",
    4: "`claim` on primary, lane 4's T421; T415",
    5: "the writer on primary, lane 4's T415",
    6: "the writer on primary, lane 4's T415",
    7: "the writer on primary, lane 4's T415",
    8: "L4-B14: lane 4's T429; T415",
    9: "L4-B14: lane 4's T430; T415",
}


def _run_the_day(estate: LaneDay, check) -> None:
    """The day's acts in order; after each, it exits 0, the render settles,
    and `check(what, kept)` runs, `kept` the (seq, sha) pairs recorded after
    the earlier acts."""
    cutover_seq = estate.head()
    kept = _seq_pairs(estate)
    for n, (what, act) in enumerate(_day_acts(estate), start=1):
        proc = act()
        assert proc.returncode == 0, f"{what} did not exit 0 ({ACT_TASKS[n]}):\n{_said(proc)}"
        estate.settle(what)
        check(what, kept, cutover_seq)
        kept = _seq_pairs(estate)


def test_a_lanes_day_keeps_the_mirror_byte_identical_after_each_act(request, tmp_path):
    """AT-11, "After each act": the act exits 0; origin's rendered paths equal
    a full render; each `Register-Seq` since the cutover appears exactly
    once, in order. Fails until L4-B9, L4-B14 and T328, and the acts' own
    tasks (`ACT_TASKS`)."""
    estate = _estate(request, tmp_path)

    def check(what, _kept, cutover_seq):
        _assert_rendered(estate, what)
        _assert_seqs_once(estate, cutover_seq, what)

    _run_the_day(estate, check)


def test_no_handoff_commit_rewrites_a_render_commit(request, tmp_path):
    """AT-11, "After each act": every (seq, sha) pair recorded after the
    earlier acts is still on origin's `main` with the same sha, and each
    handoff commit changes nothing under the rendered paths."""
    estate = _estate(request, tmp_path)

    def check(what, kept, _cutover_seq):
        _assert_pairs_kept(estate, kept, what)
        _assert_handoff_commits_render_nothing(estate, what)

    _run_the_day(estate, check)


# ------------------------------------------------------------------ a new lane at 69
def _nothing_written(estate: LaneDay, tip: str, head: int, lane: str, what: str) -> None:
    """No row for `lane`, in SQL or on origin, no stamp commit, and the
    journal's head where it was; read with the cluster up."""
    assert estate.origin_tip() == tip, (
        f"{what}: origin's main moved, so a row, a log line or a stamp commit was written: "
        f"{[s for _h, s, _b in estate.origin_log(tip)]}")
    assert estate.head() == head, f"{what}: the journal's head moved from {head} to {estate.head()}"
    for text, where in ((estate.rendered("lanes/LANES.md"), "SQL"),
                        (estate.origin_text("lanes/LANES.md"), "origin")):
        assert f"| `{lane}` |" not in text, f"{what}: {where} holds a row for {lane}"


def test_lane_start_for_a_new_lane_refuses_69_before_anything_is_written(request, tmp_path):
    """AT-11, "With the cluster stopped, for a new lane": `lane-start` exits
    69 before anything is written: no row, no `tmux` rename in the fake's
    log, the fake `claude` not run, and no stamp commit. The same holds for a
    canonical-name read failing alone (ADV-C5), at `lane-start`'s
    `canon-lane` read (`code/lane-start:1154` by the test plan's number):
    with the cluster up, the stamp shim fails every call made under
    `lanes-edit.sh canon-lane`. Fails until T328 and the door (T504), and
    T428's arms (L4-B9)."""
    estate = _estate(request, tmp_path)
    tip, head = estate.origin_tip(), estate.head()
    estate.down()
    proc = estate.lane_start(DAY_REPO, DAY_N)
    assert proc.returncode == 69, (
        f"lane-start for a new lane with the cluster stopped did not exit 69 (the door, T504; "
        f"T428's arms, L4-B9):\n{_said(proc)}")
    assert not estate.renamed(), f"the fake tmux renamed a window: {estate.renamed()}"
    assert not estate.claude_ran(), "the fake claude ran"
    estate.up()
    _nothing_written(estate, tip, head, DAY_LANE, "lane-start for a new lane at 69")
    # ADV-C5: the canonical-name read failing alone.
    estate.arm(verbs=["canon-lane"], arms=[{"mode": "fail-call", "from": 1}])
    proc = estate.lane_start(DAY_REPO, DAY_N)
    assert estate.front_calls(), (
        "lane-start made no register call under `lanes-edit.sh canon-lane` (the door, T504; "
        f"T428's base, L4-B9):\n{_said(proc)}")
    assert proc.returncode == 69, (
        f"lane-start with its canonical-name read failing alone did not exit 69 (ADV-C5; T428's "
        f"arms, L4-B9):\n{_said(proc)}")
    assert not estate.renamed(), f"the fake tmux renamed a window: {estate.renamed()}"
    assert not estate.claude_ran(), "the fake claude ran"
    _nothing_written(estate, tip, head, DAY_LANE, "lane-start with canon-lane failing alone")


# ------------------------------------------------------------------ the stamp shim
#: Each stamp shim case's arms, keyed on the statement, never on timing
#: (AT-11, "Flakiness"), and whether it sets the deadline.
STAMP_ARMS = {
    "75": ([{"mode": "fail-match", "match": COMMIT_TEXT}], True),
    "3": ([{"mode": "fail-match", "match": COMMIT_TEXT},
           {"mode": "fail-match", "match": LOOKUP_TEXT}], True),
    "69-at-the-commit": ([{"mode": "edit-entry", "match": COMMIT_TEXT, "call": 1,
                           "field": "journal.kind", "value": "t275-no-such-kind"}], False),
    "69-at-the-snapshot": ([{"mode": "fail-match", "match": SNAPSHOT_TEXT, "call": 1}], False),
    "69-at-the-snapshot-with-an-id": ([{"mode": "fail-match", "match": SNAPSHOT_TEXT,
                                        "call": 1}], False),
}
RESUME_CASES = ["75", "3", "69-at-the-commit", "69-at-the-snapshot",
                "69-at-the-snapshot-with-an-id"]


def _start_record_reached(estate: LaneDay, proc, what: str) -> None:
    assert estate.front_calls(), (
        f"{what}: lane-start made no register call under `lanes-edit.sh start-record` (L4-B9: "
        f"lane 4's T427, the verb, and T428, lane-start on it):\n{_said(proc)}")


@pytest.mark.parametrize("case", RESUME_CASES)
def test_lane_start_resume_launches_with_a_note_and_the_stamp_and_writes_none_of_its_lines(
        request, tmp_path, case):
    """AT-11, "The stamp shim's resume" (lane 4's corrected table, comment
    6709560550; B15 tasks:2524-2529, the bind's "no row" case): the shim fails
    `start-record`'s commit calls (`[75]`), its lookups too (`[3]`), breaks a
    CHECK in its entry (`[69-at-the-commit]`, 23514), or fails its first
    snapshot (`[69-at-the-snapshot]`, and `[69-at-the-snapshot-with-an-id]`
    under an earlier printed rerun's `LANES_WRITE_ID` and
    `LANES_WRITE_GENERATION`). In each, `lane-start` prints a note with the
    writer's printed rerun, naming the write id and its generation, or, at
    `[69-at-the-snapshot]`, that nothing was sent, with no id and no
    generation; the Rule 3 stamp commit is made; the launch goes on, so the
    fake `claude` runs; and the register holds none of the three lines.
    Fails until L4-B9 and T328; the note's until lane 4's T415 and T428."""
    estate = _estate(request, tmp_path)
    lane_dir = estate.lane_dirs[RESUME_REPO]
    imp = estate.imp
    place_transcript(estate.env, lane_dir, imp.UUID_A1)
    arms, deadline = STAMP_ARMS[case]
    env = dict(DEADLINE_ENV) if deadline else {}
    given = None
    if case == "69-at-the-snapshot-with-an-id":
        given = (str(uuid.uuid4()), estate.switch()["generation"])
        env.update(LANES_WRITE_ID=given[0], LANES_WRITE_GENERATION=given[1])
    tip, head = estate.origin_tip(), estate.head()
    log_before = estate.rendered(f"lanes/log/{RESUME_LANE}.md")
    estate.arm(verbs=["start-record"], arms=arms)
    proc = estate.lane_start(RESUME_REPO, RESUME_N, env=env)
    _start_record_reached(estate, proc, f"[{case}]")
    if case == "69-at-the-commit":
        assert "23514" in proc.stderr, (
            f"[{case}]: the database's 23514 is not in lane-start's stderr (T415):\n{_said(proc)}")
    reruns = [line for line in proc.stderr.splitlines() if "start-record" in line
              and "lanes-edit.sh" in line]
    assert reruns, (f"[{case}]: lane-start printed no note with the writer's rerun of "
                    f"start-record (lane 4's T415 and T428):\n{_said(proc)}")
    named = [RERUN.search(line) for line in reruns]
    if case == "69-at-the-snapshot":
        assert not any(named), (f"[{case}]: the rerun names a write id or a generation, though "
                                f"no snapshot gave one (open point 38; T415):\n{_said(proc)}")
        assert re.search(r"nothing was sent", proc.stderr, re.I), (
            f"[{case}]: the note does not say that nothing was sent (open point 38; T415):\n"
            f"{_said(proc)}")
    else:
        assert any(named), (f"[{case}]: the rerun names no write id and generation (lane 4's "
                            f"T415 and T428):\n{_said(proc)}")
        if given:
            assert any(m and m.groups() == given for m in named), (
                f"[{case}]: the rerun does not name the id {given[0]} and the generation "
                f"{given[1]} it was run under (T415):\n{_said(proc)}")
    stamps = [s for _h, s, _b in estate.origin_log(tip)
              if s.startswith(STAMP_SUBJECT.format(lane=RESUME_LANE, ws=WS))]
    assert len(stamps) == 1, (f"[{case}]: origin holds {len(stamps)} Rule 3 stamp commits for "
                              f"{RESUME_LANE}, not one (T428's arms, L4-B9):\n{_said(proc)}")
    assert estate.claude_ran(), f"[{case}]: the launch did not go on (T428's arms):\n{_said(proc)}"
    estate.arm()
    assert estate.head() == head, (
        f"[{case}]: the journal's head moved from {head} to {estate.head()}: one transaction, "
        f"all or none (T427)")
    assert estate.rendered(f"lanes/log/{RESUME_LANE}.md") == log_before, (
        f"[{case}]: {RESUME_LANE}'s log changed in SQL")


NEW_LANE_CASES = {"75": "75", "3": "3", "69": "69-at-the-snapshot"}


@pytest.mark.parametrize("case", list(NEW_LANE_CASES))
def test_lane_start_for_a_new_lane_dies_with_start_records_code_and_writes_no_row_and_no_stamp(
        request, tmp_path, case):
    """AT-11, "The stamp shim's new lane": the same shim fails `start-record
    --add-row` as for the resume's 75, 3 and `[69-at-the-snapshot]`, and
    `lane-start` dies with the code; on a 3 its stderr carries the writer's
    printed rerun line (AT-C5's rule). There is no row and no stamp commit,
    and the fake `claude` does not run. Fails until L4-B9 and T328."""
    estate = _estate(request, tmp_path)
    arms, deadline = STAMP_ARMS[NEW_LANE_CASES[case]]
    tip, head = estate.origin_tip(), estate.head()
    estate.arm(verbs=["start-record"], arms=arms)
    proc = estate.lane_start(DAY_REPO, DAY_N, env=dict(DEADLINE_ENV) if deadline else None)
    _start_record_reached(estate, proc, f"[{case}]")
    assert any("--add-row" in call["verbs"] for call in estate.front_calls()), (
        f"[{case}]: lane-start's start-record carried no --add-row for the new lane (T428): "
        f"{estate.front_calls()}")
    assert proc.returncode == int(case), (
        f"[{case}]: lane-start for a new lane did not die with start-record's {case} (T428's "
        f"arms, L4-B9):\n{_said(proc)}")
    if case == "3":
        assert RERUN.search(proc.stderr), (
            f"[{case}]: lane-start's stderr carries no printed rerun of the writer (T415; "
            f"AT-C5):\n{_said(proc)}")
    assert not estate.claude_ran(), f"[{case}]: the fake claude ran"
    estate.arm()
    _nothing_written(estate, tip, head, DAY_LANE, f"[{case}]")


@pytest.mark.parametrize("case", ["resume", "new-lane"])
def test_lane_start_dies_with_2_on_any_2_from_start_record_not_only_the_expectations(
        request, tmp_path, case):
    """AT-11, "Any other 2" (lane 4's section, the table's 2 row): a fake
    `psql` answers `start-record`'s commit call with exit 3 and LR010.
    `lane-start` dies with 2 and launches nothing; the fake's log holds one
    commit call and no call after it, since LR010 is never retried; for a
    resume and for a new lane (`--add-row`). Fails until L4-B9 and T328."""
    estate = _estate(request, tmp_path)
    repo, n = (RESUME_REPO, RESUME_N) if case == "resume" else (DAY_REPO, DAY_N)
    lane = f"{repo}-{n}"
    if case == "resume":
        place_transcript(estate.env, estate.lane_dirs[repo], estate.imp.UUID_A1)
    estate.arm(verbs=["start-record"],
               answer={"match": COMMIT_TEXT, "exit": 3, "stderr": LR010.format(lane=lane)})
    proc = estate.lane_start(repo, n)
    _start_record_reached(estate, proc, f"[{case}]")
    calls = estate.front_calls()
    commits = [i for i, call in enumerate(calls) if call["commit"]]
    assert len(commits) == 1, (f"[{case}]: the fake's log holds {len(commits)} commit calls under "
                               f"start-record, not one (T427): {calls}")
    assert commits[0] == len(calls) - 1, (
        f"[{case}]: a call under start-record came after the LR010 commit call (T427): {calls}")
    if case == "new-lane":
        assert "--add-row" in calls[commits[0]]["verbs"], (
            f"[{case}]: the commit call was not --add-row's (T428): {calls}")
    assert proc.returncode == 2, (f"[{case}]: lane-start did not die with 2 on LR010 (T428's "
                                  f"arms: any 2 dies):\n{_said(proc)}")
    assert not estate.claude_ran(), f"[{case}]: the fake claude ran"


# ------------------------------------------------------------------ the outage acts
def test_request_handoff_and_claim_refuse_69_with_the_database_down(request, tmp_path):
    """AT-11: with the cluster stopped, `request-handoff` and `claim` each
    exit 69, and nothing is written. `request-handoff` refuses before it
    writes, so its refusal names no write (R-F10-2; ERR-34). Fails until
    T328 and lane 4's T415 and T421."""
    estate = _estate(request, tmp_path)
    tip, head = estate.origin_tip(), estate.head()
    estate.down()
    asked = estate.edit("request-handoff", RESUME_LANE, "--force", "test 11",
                        "--session", str(uuid.uuid4()), lane=OUTAGE_LANE)
    claim = estate.edit("claim", CLAIMED, "--no-github", lane=OUTAGE_LANE)
    estate.up()
    assert asked.returncode == 69, f"request-handoff did not exit 69 (T415):\n{_said(asked)}"
    assert "LANES_WRITE_ID=" not in asked.stderr, (
        f"request-handoff's refusal names a write, though it refused before writing (R-F10-2):\n"
        f"{_said(asked)}")
    assert claim.returncode == 69, f"claim did not exit 69 (T421; T415):\n{_said(claim)}"
    assert estate.origin_tip() == tip, "origin's main moved"
    assert estate.head() == head, f"the journal's head moved from {head} to {estate.head()}"


def _paused_writes(log: Path) -> list:
    return [line for line in log.read_text(encoding="utf-8").splitlines() if "PAUSED" in line]


def _outage_handoff(estate: LaneDay) -> tuple:
    """`lane-handoff` for `OUTAGE_LANE` with the cluster stopped, through
    `LoggedEdit`: (its run, the log, origin's tip before it, the head)."""
    env, log = estate.logged_env()
    tip, head = estate.origin_tip(), estate.head()
    before = (estate.lane_checkout(OUTAGE_LANE) / "handoffs" / f"{OUTAGE_LANE}.md").read_text(
        encoding="utf-8")
    estate.down()
    proc = estate.lane_handoff(OUTAGE_LANE, "test 11: the outage", env=env)
    return proc, log, tip, head, before


def test_lane_handoff_writes_the_handoff_from_a_labelled_mirror_read_and_leaves_the_lane_swapping(
        request, tmp_path):
    """AT-11, "`lane-handoff` with the cluster stopped" (TP:2198-2212;
    R-F13-2): the handoff file is published; stderr carries the `read:
    mirror at <sha12>, ... (sql unreachable: ...)` label; the `PAUSED`
    writes are not sent, the fake `lanes-edit.sh`'s log holding no `PAUSED`
    write, and the 69 note names how the record is completed later (P15;
    `lane-handoff --late --at`); after a restart the lane still reads
    `SWAPPING`. Fails until lane 4's T405, T406 and T429 (L4-B14), and
    T328."""
    estate = _estate(request, tmp_path)
    proc, log, tip, head, before = _outage_handoff(estate)
    assert MIRROR_LINE.search(proc.stderr), (
        f"lane-handoff's stderr carries no `read: mirror at` label (lane 4's T405; T504):\n"
        f"{_said(proc)}")
    assert not _paused_writes(log), (
        f"lane-handoff sent a PAUSED write with the database down (T429; R-F13-2): "
        f"{_paused_writes(log)}")
    assert LATE_COMMAND in proc.stderr + proc.stdout, (
        f"lane-handoff's 69 note does not name `{LATE_COMMAND}` (P15; T429):\n{_said(proc)}")
    text = estate.origin_text(f"handoffs/{OUTAGE_LANE}.md")
    assert text != before and text.endswith(before), (
        f"the handoff was not published: origin's handoffs/{OUTAGE_LANE}.md does not carry a new "
        f"block on top of the old file (lane 4's T405 and T429):\n{_said(proc)}")
    estate.up()
    assert estate.head() == head, f"the journal's head moved from {head} to {estate.head()}"
    assert estate.lifecycle(OUTAGE_LANE) == "SWAPPING", (
        f"after the restart {OUTAGE_LANE} reads {estate.lifecycle(OUTAGE_LANE)!r}, not SWAPPING")


def test_the_late_paused_path_completes_the_swap_once_the_database_returns(request, tmp_path):
    """AT-11, "After the restart": the late `PAUSED` path, `lane-handoff
    --late --at <UTC> --lane <L>` from a shell (T429's 69 note), completes
    the record: one journal entry, and its render on origin. Fails until
    lane 4's T429 (L4-B14) and T415, and T328."""
    estate = _estate(request, tmp_path)
    proc, _log, _tip, _head, _before = _outage_handoff(estate)
    estate.up()
    head = estate.head()
    tip = estate.origin_tip()
    late = estate.lane_handoff(OUTAGE_LANE, "test 11: the late record", "--late", "--at", _utc())
    assert late.returncode == 0, f"the late PAUSED path did not exit 0 (T429; T415):\n{_said(late)}"
    after = [r for r in estate.journal() if r["seq"] > head]
    assert len(after) == 1, (f"the late PAUSED path made {len(after)} journal entries, not one "
                             f"(T429; T415): {after}")
    seq = after[0]["seq"]
    assert estate.reg.wait_for_seq(seq, seconds=SETTLE_S), (
        f"no commit on origin carries Register-Seq: {seq}, the late record's render (T416; lane "
        f"3's T321 to T323): {[s for _h, s, _b in estate.origin_log(tip)]}")


def test_lane_end_refuses_69_with_the_database_down(request, tmp_path):
    """AT-11, "After the restart": `lane-end` with the cluster stopped exits
    69, and writes nothing. Fails until lane 4's T430 (L4-B14), T403 and
    T415, and T328."""
    estate = _estate(request, tmp_path)
    tip, head = estate.origin_tip(), estate.head()
    estate.down()
    proc = estate.lane_end(OUTAGE_LANE)
    estate.up()
    assert proc.returncode == 69, (f"lane-end with the cluster stopped did not exit 69 (T430; "
                                   f"T403):\n{_said(proc)}")
    assert estate.origin_tip() == tip, "origin's main moved"
    assert estate.head() == head, f"the journal's head moved from {head} to {estate.head()}"
