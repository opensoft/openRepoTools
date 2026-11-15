# SPDX-License-Identifier: Apache-2.0
"""Feature 007's AT-LRLABEL: `register_label=`, and the cutover's two
refusals (L2-N5; T218; FR-001, FR-059) (opensoft/openRepoTools#165).

The test plan's four names, byte for byte. T218 writes them here, in phase
N, since the cutover's cases check lane 1's T116, `cutover`'s transaction
against a scratch schema (FR-059; R1's M3); T116 selects them with
`sql_register_cutover and (cutover_without_register or cutover_at_files or
a_first_cutovers)`. Its other cases (T272's) are phase G's, in this module
too.

THE KEY needs no engine: a file carrying `register_label=` beside
`register_url=` is not refused as an unknown key, and `lanes-index mode`
reads it and exits 0. THE REFUSAL BEFORE `cutover` CONNECTS is FP: a file
with no `register_label=` exits 2 naming the key and S-2, and the fake
`psql`'s log holds no request. THE REST is RE: a label not the switch's at
`files`, at a first cutover and in the after-loss form, exits 2 with no
commit call; and a first cutover's `lanes/STORE` says `database=` the
label. They skip with T205's banner on a bench with no engine.

THE COMMAND FORMS are operations.md's (act 4's step 7 and section 2.3):
`lanes-index cutover --import <C>` and `lanes-index cutover --import <M>
--after-loss`. The refusals' texts are the test plan's (AT-LRLABEL,
"Oracle"); a case asserts their words that name the key and S-2.

EACH CASE ON ITS OWN CAUSE, against lane 1's T116 (#165 6770325296) and lane
3's ruling on it (6770600106):
- A SCRATCH SCHEMA. While `RENDER_GIT_HALF` is False, `cutover` refuses
  `register_schema=lanes_register` with 2 before it connects (T116 runs only
  on a scratch schema, ruling on point 1), which would answer before any
  case's own cause. Every configuration here names `SCHEMA`, a scratch
  schema, which the RE fixture's bootstrap makes.
- THE OPERATOR LANE AND A GIT IDENTITY (T116's point 4). `cutover` refuses
  with 2, after its one read and before the commit call, where `LANES_LANE`
  is unset or not a lane's name, where a container has no
  `LANES_WORKSTATION`, and where git names no author (`git var
  GIT_AUTHOR_IDENT`). Every host sets `LANES_LANE`, `LANES_WORKSTATION` and
  the author and committer in its environment, so no case meets them.
- The refusal before it connects is shown against its control: the same
  host with `register_label=` sends its read.
- EXIT 0 IS THE TRANSACTION ALONE until T327 (T116's point 1, accepted as an
  interim): nothing is pushed and the marker stays `adding`. So the first
  cutover's `lanes/STORE` on origin fails, by its own assertion, until T327
  pushes it.
- T116's other refusals (no import, an `--import` not the latest, a head
  past it, a switch that does not fit the form; `--marker-first`, 64) come
  after the label's checks, or need a form no case here uses, and `--import`
  is always origin's tip, its full 40-hex sha (point 5).

READ, NOT FOUND IN A CONTRACT: "the fake `psql`'s log holds no call" is
read as "no call that carries a request": a `psql --version` probe is not
counted (T203's fake), since it sends nothing to a database.

AT-F2 (T272; TP:5515-5564), phase G, RE, at the end of this module:
operator entries and a failed seq-1 push. Each case is test 7's cutover on
a bare origin (`CutoverRegister`, from `test_sql_register_import.py`), run by
the operator lane, with `GIT_WRAPPER` first on the command's `PATH`: test
5's `git` wrapper (TP:1060-1080), here with the arms AT-F2 needs, each a
line of `git-wrapper.json`: fail a call; push, then report the push failed;
fail every `fetch` once a push has been made (the read-back's fetch); hold
a push on a FIFO; and, for the deploy key, test 5's GitHub-shaped origin,
whose URLs the wrapper sends to the bare origin on the calls that reach it,
`fetch`, `push` and `ls-remote`, with `workspace.yaml` naming that GitHub
repository too. The cases fail until L1-A14
and lane 3's T327 (the marker's push, read-back and abort, through T320's
one push function); the renders until T321 to T323; and the `[rollback]`
cases also until lane 3's T304 and T326, `rollback`'s transaction and its
render and push (T327's and T326's Depends).

READINGS, NOT FOUND IN A CONTRACT:
- "Push failed: no renderer renders seq 1, and a render ends rather than
  retry it" needs a render while seq 1 stands unpushed. A cutover whose
  push fails aborts at once, so `[cutover]` of the render's case holds the
  cutover's push on the wrapper's FIFO and renders meanwhile.
- "The rerun reads origin back first" is read as: the rerun's first `git`
  call that reaches origin is a `fetch`, before any `push`.
- "A rollback's entry at `k+1`, with seqs up to `k` not yet on origin" is
  made by failing every push while two writes commit and while `rollback`
  writes `k+1`, so its own render (step 2) cannot push them either.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from sql_register_helpers import (PSQL_SHIM, PSQL_SHIM_CONTROL, PSQL_SHIM_LOG,
                                  REGISTER_FAKE_PSQL, RENDER_GIT_HALF_LINE, flipped_copy,
                                  guard_strip_env)

pytestmark = [WINDOWS_SKIP]

#: THE LANDING GATE'S TABLE (T280, `tests/sql_register_gate.py`; task sets
#: version 12b's rule 11, opensoft/openRepoTools#165 6877673742), TEMPORARY:
#: T281 removes it in the last set. Where the gate is active, each id here is
#: skipped until every task its row names has landed, and the skip names them.
#: Each row is the fails-until clause of T218's Order (tasks:2072) or T272's
#: (tasks:2497) in tasks.md at lane 3's commit 17, 204145ae, each L-label as
#: the task that covers it (L1-A3 T104, L1-A7 T109, L1-A13 T115, L1-A14 T116,
#: L1-A17 T119 and T120), as lane 2's plan GP-24 v1 (sha256 16d738b9) gives
#: it. An id waits for the "*" row and its own, and a `[rollback]` id's row
#: replaces its function's.
SQL_REGISTER_GATE_TABLE = {
    "*": ("T116",),  # every id: the tasks all its rows share
    "test_a_cutover_abort_deletes_seq_1_only_when_the_marker_is_proved_absent": ("T327",),  # T272; tasks:2497
    "test_a_first_cutovers_store_names_the_register_label": ("T104", "T109", "T115", "T119", "T120", "T229", "T327"),  # T218; tasks:2072
    "test_a_marker_only_entry_is_an_operator_entry_the_renderer_skips": ("T327",),  # T272; tasks:2497
    "test_a_render_stops_before_an_operator_seq_not_yet_on_origin": ("T327",),  # T272; tasks:2497
    "test_an_unconfirmed_operator_push_exits_3_and_its_rerun_reads_origin_first": ("T327",),  # T272; tasks:2497
    "test_cutover_at_files_with_a_label_not_the_switchs_is_refused_2_before_it_sends": ("T104", "T109", "T115", "T119", "T120", "T229"),  # T218; tasks:2072
    "test_cutover_without_register_label_is_refused_2_before_it_connects": ("T104", "T109", "T115", "T119", "T120", "T229"),  # T218; tasks:2072
    "test_lanes_index_accepts_the_register_label_key": ("T104", "T109", "T115", "T119", "T120", "T229"),  # T218; tasks:2072
    "test_no_operator_command_holds_a_transaction_across_git": ("T327",),  # T272; tasks:2497
    "test_the_operator_entry_is_pushed_with_the_renderer_identity_and_read_back": ("T327",),  # T272; tasks:2497
    "test_a_render_stops_before_an_operator_seq_not_yet_on_origin[rollback]": ("T304", "T326", "T327"),  # T272; tasks:2497
    "test_an_unconfirmed_operator_push_exits_3_and_its_rerun_reads_origin_first[rollback]": ("T304", "T326", "T327"),  # T272; tasks:2497
}

LABEL = "register-lrlabel"
OTHER = "register-lrlabel-other"

#: A scratch schema, never `lanes_register` (T116; lane 3, 6770600106).
SCHEMA = "lrlabel_scratch"
URL = "postgresql://lrlabel_login@127.0.0.1:55432/register_db"

#: The operator lane, `LANES_LANE` (T116's point 4: a lane's name, with no
#: space, control character, '<', '>' or '@').
OPERATOR_LANE = "t218-operator"

#: The git identity `git var GIT_AUTHOR_IDENT` names (T116's point 4): the
#: author and the committer, `Name <email>`.
IDENTITY = {"GIT_AUTHOR_NAME": "t218 operator", "GIT_AUTHOR_EMAIL": "t218@example.invalid",
            "GIT_COMMITTER_NAME": "t218 operator", "GIT_COMMITTER_EMAIL": "t218@example.invalid"}


def _private(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    return path


def _script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _said(proc: subprocess.CompletedProcess) -> str:
    return f"exit {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"


class Host:
    """One host: a `lanes-index` copy beside `lanes-edit.sh`, a workspace
    checkout of a bare origin, and the register's fake `psql` first on
    `PATH`.

    `LANES_REPO` names the checkout, the operator lane's own, and `W` is a
    directory of its own, `LANES_WORKSPACE_ROOT` (`lanes-edit.sh`'s test
    seam), as T221i's and T231d's import cases have it: the operator
    commands run through the operator lane's checkout, never `W` (D24), and
    the import refuses a `LANES_REPO` that names `W` ("REFUSED: import:
    LANES_REPO names W itself"; lane 1's triage, group 6, #165 comment
    6807494089). `workspace.yaml` still names the checkout; the seam is
    read first."""

    def __init__(self, root: Path):
        self.root = root
        self.w = root / "W"
        self.w.mkdir(parents=True)
        tool = root / "tool"
        tool.mkdir(parents=True)
        source = REPO / "lanes-index"
        if len(RENDER_GIT_HALF_LINE.findall(source.read_bytes())) == 1:
            self.copy = flipped_copy(source, tool, False)
        else:
            self.copy = tool / "lanes-index"
            shutil.copy2(source, self.copy)
        for name in ("lanes-edit.sh", "repos.tsv"):
            if (REPO / name).exists():
                shutil.copy2(REPO / name, tool / name)
        self.fakebin = root / "fakebin"
        _script(self.fakebin / "psql", REGISTER_FAKE_PSQL)
        self.psql_log = root / "psql.log"
        self.home = root / "home"
        self.origin = root / "origin.git"
        self.seed = root / "seed"
        self.wip = self.home / "projects" / "wip"
        self.wip.parent.mkdir(parents=True)
        (root / "t").mkdir()
        self.passfile = _private(root / "secret" / "pgpass",
                                 "127.0.0.1:55432:register_db:lrlabel_login:not-a-secret\n")
        env = guard_strip_env(os.environ, strip=("T218_",))
        for name in ("XDG_CONFIG_HOME", "LANES_INDEX_CONFIG"):
            env.pop(name, None)
        for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE", "EMAIL"):
            env.pop(name, None)
        env.update(HOME=str(self.home), XDG_STATE_HOME=str(root / "state"),
                   XDG_CONFIG_HOME=str(root / "config"), TMPDIR=str(root / "t"),
                   LANES_WORKSTATION="Eagle", LANES_NO_GITHUB="1", LANES_REPO=str(self.wip),
                   LANES_WORKSPACE_ROOT=str(self.w),
                   LANES_LANE=OPERATOR_LANE, FAKE_PSQL_LOG=str(self.psql_log),
                   GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
                   PATH=os.pathsep.join([str(self.fakebin),
                                         os.environ.get("PATH", os.defpath)]))
        env.update(IDENTITY)
        self.env = env
        self._git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self._git("init", "-q", "-b", "main", str(self.seed))
        (self.seed / "lanes").mkdir()
        (self.seed / "lanes" / "LANES.md").write_text("# Lanes\n", encoding="utf-8")
        self._git("-C", str(self.seed), "add", "lanes/LANES.md")
        self._git("-C", str(self.seed), "commit", "-q", "-m", "seed")
        self._git("-C", str(self.seed), "push", "-q", str(self.origin), "main")
        self._git("clone", "-q", str(self.origin), str(self.wip))
        (self.home / ".agents").mkdir()
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.wip}\n", encoding="utf-8")

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], check=True, env=self.env, capture_output=True,
                              text=True, stdin=subprocess.DEVNULL)

    def tip(self) -> str:
        return self._git("-C", str(self.wip), "rev-parse", "refs/remotes/origin/main").stdout.strip()

    def config(self, *, label: str | None = LABEL, url: str = URL, reader: str = URL,
               mode: str = "index") -> Path:
        lines = [f"mode={mode}", f"register_url={url}", f"register_passfile={self.passfile}",
                 f"reader_url={reader}", f"reader_passfile={self.passfile}",
                 f"register_schema={SCHEMA}"]
        if label is not None:
            lines.append(f"register_label={label}")
        return _private(self.root / "conf" / "lanes-index.conf", "\n".join(lines) + "\n")

    def run(self, config: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.copy), *args], capture_output=True,
                              text=True, env=dict(self.env, LANES_INDEX_CONFIG=str(config)),
                              cwd=str(self.wip), timeout=300, stdin=subprocess.DEVNULL)

    def requests(self, log: Path | None = None) -> list:
        log = log or self.psql_log
        if not log.exists():
            return []
        entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
                   if line]
        return [entry for entry in entries if entry.get("kind") != "version"]


# --------------------------------------------------------------------- the key
def test_lanes_index_accepts_the_register_label_key(tmp_path):
    host = Host(tmp_path)
    config = host.config()
    proc = host.run(config, "mode")
    assert proc.returncode == 0, (
        f"lanes-index mode refuses a file carrying register_label=:\n{_said(proc)}")
    assert proc.stdout == "index\n", _said(proc)
    assert host.requests() == [], "lanes-index mode ran psql"


# --------------------------------------------------- the refusal before it connects
def test_cutover_without_register_label_is_refused_2_before_it_connects(tmp_path):
    host = Host(tmp_path)
    config = host.config(label=None)
    proc = host.run(config, "cutover", "--import", host.tip())
    assert proc.returncode == 2, (
        f"cutover with no register_label= is not refused with 2:\n{_said(proc)}")
    assert "register_label=" in proc.stderr and "S-2" in proc.stderr, _said(proc)
    assert host.requests() == [], "cutover connected before it refused"

    # THE CONTROL: the same host with register_label= passes every refusal
    # before it connects, and sends its read.
    control = host.run(host.config(), "cutover", "--import", host.tip())
    assert host.requests() != [], (
        f"the control, with register_label= set, is refused before it connects too, so the "
        f"refusal is not the missing label's alone:\n{_said(control)}")


# ------------------------------------------------------------- the RE half
class RegisterHost(Host):
    """RE: a database of its own, bootstrapped through the admin service with
    `--label LABEL` (T109), the writer and reader logins as fixtures, test 7's
    import at origin's tip, the switch at `files`, and section 3.2's shim in
    front of the real `psql`."""

    def __init__(self, request, root: Path):
        cluster = request.getfixturevalue("stoppable_cluster")
        import pgcluster
        super().__init__(root)
        self.cluster = cluster
        self.dbname = "t218_lrlabel"
        cluster.psql(f"CREATE DATABASE {self.dbname} TEMPLATE template0;")
        _private(self.home / ".pg_service.conf", "\n".join([
            "[t218admin]", f"host={cluster.root}", f"port={pgcluster.PORT}",
            f"user={pgcluster.SUPERUSER}", f"dbname={self.dbname}", ""]))
        self.env["PATH"] = os.pathsep.join([str(self.fakebin), str(cluster.bindir),
                                            os.environ.get("PATH", os.defpath)])
        # The shim, not the fake, is `psql` here.
        _script(self.fakebin / "psql", PSQL_SHIM)
        (self.fakebin / PSQL_SHIM_CONTROL).write_text(
            json.dumps({"psql": str(Path(cluster.bindir) / "psql"), "arms": []}),
            encoding="utf-8")
        self.shim_log = self.fakebin / PSQL_SHIM_LOG
        base = self.config(label=LABEL, url="postgresql://unused@127.0.0.1/unused")
        proc = self.run(base, "bootstrap", "--admin-service", "t218admin", "--label", LABEL,
                        "--repository", "opensoft/t218-workspace", "--lane", "t218-operator",
                        "--no-passwords")
        assert proc.returncode == 0, f"the bootstrap (T109) failed:\n{_said(proc)}"
        for login, group in (("t218_writer", "lanes_register_writer"),
                             ("t218_reader", "lanes_register_reader")):
            cluster.psql(f"CREATE ROLE {login} LOGIN IN ROLE {group};", dbname=self.dbname)
        where = f"{str(cluster.root).replace('/', '%2F')}:{pgcluster.PORT}/{self.dbname}"
        self.writer = f"postgresql://t218_writer@{where}"
        self.reader = f"postgresql://t218_reader@{where}"
        imported = self.run(self.config(label=LABEL, url=self.writer, reader=self.reader),
                            "import", "--at", self.tip())
        assert imported.returncode == 0, f"test 7's import failed:\n{_said(imported)}"
        self.shim_log.write_text("", encoding="utf-8")

    def commits(self) -> list:
        """The shim's commit calls (AT-LRLABEL's "the shim's log holds no
        commit call"): each call that carries `commit_write`, the design's
        commit call (design.md:1469 at spec#17 `8523aa0c`), or a `COMMIT`
        outside a `READ ONLY` transaction. The cutover's one read, the
        snapshot read, is `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY`
        ... `COMMIT;` (design.md:1420), which writes nothing, so it is not
        one."""
        found = []
        for entry in self.requests(self.shim_log):
            sent = entry.get("sent", "")
            if "commit_write" in sent or ("COMMIT" in sent and "READ ONLY" not in sent):
                found.append(entry)
        return found


@pytest.mark.parametrize("form", ["first", "after-loss"])
def test_cutover_at_files_with_a_label_not_the_switchs_is_refused_2_before_it_sends(
        tmp_path, request, form):
    host = RegisterHost(request, tmp_path)
    config = host.config(label=OTHER, url=host.writer, reader=host.reader)
    args = ["cutover", "--import", host.tip()] + (["--after-loss"] if form == "after-loss" else [])
    before = host.cluster.psql(f"SELECT * FROM {SCHEMA}.register_switch", dbname=host.dbname).stdout
    proc = host.run(config, *args)
    assert proc.returncode == 2, (
        f"[{form}] cutover with register_label= not the switch's is not refused:\n{_said(proc)}")
    for word in (f"register_label={OTHER}", LABEL, "S-2"):
        assert word in proc.stderr, f"[{form}] the refusal does not name {word}:\n{_said(proc)}"
    assert host.commits() == [], f"[{form}] the refused cutover sent a commit call"
    after = host.cluster.psql(f"SELECT * FROM {SCHEMA}.register_switch", dbname=host.dbname).stdout
    assert after == before, f"[{form}] the refused cutover changed the switch"


def test_a_first_cutovers_store_names_the_register_label(tmp_path, request):
    host = RegisterHost(request, tmp_path)
    config = host.config(label=LABEL, url=host.writer, reader=host.reader)
    proc = host.run(config, "cutover", "--import", host.tip())
    assert proc.returncode == 0, f"the first cutover failed:\n{_said(proc)}"
    host._git("-C", str(host.wip), "fetch", "-q", "origin")
    shown = subprocess.run(["git", "-C", str(host.wip), "show",
                            "refs/remotes/origin/main:lanes/STORE"], capture_output=True,
                           text=True, env=host.env, stdin=subprocess.DEVNULL)
    assert shown.returncode == 0, (
        f"origin has no lanes/STORE after the first cutover: the marker's push is T327's, and "
        f"until it lands exit 0 is the transaction alone (T116's point 1):\n{_said(proc)}")
    store = shown.stdout
    assert f"database={LABEL}" in store.splitlines(), f"lanes/STORE does not name {LABEL}: {store}"


# ============================================================ AT-F2 (T272)
#: Test 5's `git` wrapper (TP:1060-1080), with the arms AT-F2 needs. It logs
#: each call as one JSON line, `git-wrapper.log`: the subcommand, the argv,
#: its pid and parent's, and the push environment's names D23 sets (design.md,
#: "The push"). `git-wrapper.json` holds the real `git` and the arms, each
#: `{"call": <subcommand>, "mode": "fail" | "after-fail" | "hold", ...}`:
#: `fail` exits 1 and runs nothing; `after-fail` runs the call, then exits 1
#: (a push made, then reported failed); `hold` blocks on `fifo` until the
#: test closes its end, then runs the call. `after_push` makes an arm wait
#: for a push that ran and exited 0; `count` limits the calls it takes.
#: `redirect` sends test 5's GitHub URLs to the bare origin, as `-c
#: url.<origin>.insteadOf=<url>` before the call's own arguments, on the
#: calls that reach origin alone: `fetch`, `push` and `ls-remote` (`REACH`).
#: On any other call the redirect would be seen. `git remote get-url origin`
#: expands `insteadOf`, so T320's `render_push_url` would read the bare
#: origin's path and refuse it as no GitHub repository; and `git config`
#: lists `-c`, so T320's `_render_push_config_check` would find a rewrite of
#: the push URL and refuse it (lane 3's T327 builder, #165 6812549487).
GIT_WRAPPER = r'''#!/usr/bin/env -S python3 -I
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL = os.path.join(HERE, "git-wrapper.json")
LOG = os.path.join(HERE, "git-wrapper.log")
STATE = os.path.join(HERE, "git-wrapper.state")
WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
              "--config-env"}
SHOWN = ("GIT_SSH_COMMAND", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "SSH_AUTH_SOCK")
REACH = ("fetch", "push", "ls-remote")


def subcommand(args):
    i = 0
    while i < len(args):
        if args[i] in WITH_VALUE:
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            return args[i]
    return ""


def log(record):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def state():
    try:
        with open(STATE, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {"pushed": False, "used": {}}


def save(st):
    with open(STATE, "w", encoding="utf-8") as handle:
        json.dump(st, handle)


def main():
    args = sys.argv[1:]
    with open(CONTROL, encoding="utf-8") as handle:
        control = json.load(handle)
    sub = subcommand(args)
    record = {"sub": sub, "argv": args, "pid": os.getpid(), "ppid": os.getppid(),
              "env": {k: os.environ[k] for k in SHOWN if k in os.environ}}
    st = state()
    arm = None
    for n, candidate in enumerate(control.get("arms", [])):
        if candidate.get("call") != sub:
            continue
        if candidate.get("after_push") and not st["pushed"]:
            continue
        if "count" in candidate and st["used"].get(str(n), 0) >= candidate["count"]:
            continue
        arm = candidate
        st["used"][str(n)] = st["used"].get(str(n), 0) + 1
        save(st)
        break
    prefix = []
    redirect = control.get("redirect")
    if redirect and sub in REACH:
        for url in redirect["from"]:
            prefix += ["-c", "url.%s.insteadOf=%s" % (redirect["to"], url)]
    mode = arm["mode"] if arm else "run"
    if mode == "fail":
        log(dict(record, outcome="failed"))
        sys.stderr.write("fatal: the test's git wrapper failed this %s\n" % sub)
        return 1
    if mode == "hold":
        log(dict(record, outcome="held"))
        with open(arm["fifo"], "rb") as fifo:
            fifo.read()
    rc = subprocess.run([control["git"]] + prefix + args).returncode
    if sub == "push" and rc == 0:
        st = state()
        st["pushed"] = True
        save(st)
    if mode == "after-fail" and rc == 0:
        log(dict(record, outcome="pushed, reported failed", rc=rc))
        sys.stderr.write("error: the test's git wrapper reports this push failed\n")
        return 1
    log(dict(record, outcome="ran", rc=rc))
    return rc


sys.exit(main())
'''

#: Test 5's GitHub-shaped origin, for the deploy key's case: the bootstrap's
#: repository (`pgcluster.FX_REPOSITORY`), by HTTPS and by the SSH URL the
#: push names (design.md, "The push").
F2_REPOSITORY = "opensoft/openRepoTools-fixture"
GH_HTTPS = f"https://github.com/{F2_REPOSITORY}.git"
GH_SSH = f"ssh://git@github.com/{F2_REPOSITORY}.git"


def _import_module():
    """`test_sql_register_import`, whose fixture register and cutover host
    AT-F2 builds on ("Test 7's cutover on a bare origin")."""
    import test_sql_register_import as module
    return module


class F2Register:
    """AT-F2's fixture: test 7's cutover host with `GIT_WRAPPER` first on
    each command's `PATH`. `github=True` gives test 5's GitHub-shaped origin,
    `workspace.yaml` naming that repository, and a `render_key=` file, for
    the deploy key's case."""

    def __init__(self, root: Path, pg, *, github: bool = False):
        imp = _import_module()
        self.imp = imp
        self.pg = pg
        self.wrapper = root / "wrapper"
        _script(self.wrapper / "git", GIT_WRAPPER)
        self.reg = imp.CutoverRegister(root, pg, extra_path=self.wrapper)
        reg = self.reg
        self.real_git = shutil.which("git", path=os.pathsep.join(
            p for p in reg.env["PATH"].split(os.pathsep) if p and Path(p) != self.wrapper))
        assert self.real_git, "no git on PATH"
        self.redirect = None
        self.conf = reg.index_conf
        if github:
            reg.git("remote", "set-url", "origin", GH_HTTPS)
            # `workspace.yaml` names the repository origin now names. T320's
            # `render_push_url` refuses an origin that is not `source_of`'s,
            # which reads `repository:`; and `lanes-edit.sh`'s workspace
            # resolver refuses a `path:` whose origin is not the
            # `repository:` beside it (`lanes_ws_same_repo`). Only this arm's
            # origin is GitHub-shaped: the import module's `Workspace` names
            # the bare origin, as every other case's origin is.
            yaml = reg.agents / "workspace.yaml"
            lines = yaml.read_text(encoding="utf-8").splitlines()
            assert sum(line.startswith("repository:") for line in lines) == 1, lines
            yaml.write_text("\n".join(f"repository: {F2_REPOSITORY}"
                                      if line.startswith("repository:") else line
                                      for line in lines) + "\n", encoding="utf-8")
            self.redirect = {"to": str(reg.origin), "from": [GH_HTTPS, GH_SSH]}
            self.key = _private(reg.conf / "render_key",
                                "-----BEGIN OPENSSH PRIVATE KEY-----\nnot a key\n"
                                "-----END OPENSSH PRIVATE KEY-----\n")
            self.conf = _private(reg.conf / "lanes-index-key.conf",
                                 reg.index_conf.read_text(encoding="utf-8")
                                 + f"render_key={self.key}\n")
        self.arm()

    def arm(self, *arms: dict) -> None:
        """Set the wrapper's arms, and start its log and state afresh."""
        control = {"git": self.real_git, "arms": list(arms)}
        if self.redirect:
            control["redirect"] = self.redirect
        (self.wrapper / "git-wrapper.json").write_text(json.dumps(control), encoding="utf-8")
        for name in ("git-wrapper.log", "git-wrapper.state"):
            (self.wrapper / name).unlink(missing_ok=True)

    def calls(self) -> list:
        log = self.wrapper / "git-wrapper.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]

    def settle(self, quiet: float = 3, limit: float = 90) -> None:
        """Wait until the wrapper's log has not grown for `quiet` seconds:
        the renders the writes forked, detached, have ended."""
        log = self.wrapper / "git-wrapper.log"
        deadline, last, since = time.monotonic() + limit, -1, time.monotonic()
        while time.monotonic() < deadline:
            size = log.stat().st_size if log.exists() else 0
            if size != last:
                last, since = size, time.monotonic()
            elif time.monotonic() - since >= quiet:
                return
            time.sleep(0.25)


def _first_reach(calls: list) -> str | None:
    """The first call that reaches origin: a `fetch`, `push` or `ls-remote`."""
    for call in calls:
        if call["sub"] in ("fetch", "push", "ls-remote"):
            return call["sub"]
    return None


def _open_when_held(fifo: Path, proc: subprocess.Popen, seconds: float = 120):
    """The FIFO's write end, opened once the wrapper holds a call on it; None
    where `proc` ends, or the time runs out, first. Closing it releases the
    call."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and proc.poll() is None:
        try:
            return os.open(str(fifo), os.O_WRONLY | os.O_NONBLOCK)
        except OSError:
            time.sleep(0.1)
    return None


def _fifo(directory: Path) -> Path:
    path = directory / "hold.fifo"
    os.mkfifo(str(path), 0o600)
    assert stat.S_ISFIFO(os.lstat(path).st_mode)
    return path


def test_a_marker_only_entry_is_an_operator_entry_the_renderer_skips(pg, tmp_path):
    """Clean: seq 1, the cutover's entry, touches `lanes/STORE` alone and
    carries the operator flag, and no write entry does. A render forked
    after it, by the first write, pushes no commit for seq 1: on origin only
    the cutover's own marker commit carries `Register-Seq: 1`. `status`,
    read after the harness's fetch of W (`fetch_w`; lane 3's ruling (a),
    #165 6833830078), shows no lag (AT-F2, "Clean", TP:5534-5537; D24)."""
    f2 = F2Register(tmp_path / "e", pg)
    reg, imp = f2.reg, f2.imp
    proc = reg.cutover(conf=f2.conf)
    assert proc.returncode == 0, proc.stderr
    switch = imp._switch(pg)
    assert switch["marker_state"] == "present", switch
    assert imp._rows(pg, "SELECT path FROM journal_files WHERE seq = 1") == \
        [{"path": "lanes/STORE"}], "the cutover's entry touches lanes/STORE alone"
    wrote = reg.write("a write after the cutover")
    assert wrote.returncode == 0, f"{wrote.stdout}{wrote.stderr}"
    assert imp._rows(pg, "SELECT seq, kind, operator FROM journal WHERE seq > 0 ORDER BY seq") == [
        {"seq": 1, "kind": "cutover", "operator": True},
        {"seq": 2, "kind": "write", "operator": False}]
    assert reg.wait_for_seq(2), f"the render pushed no seq 2: {reg.seqs_on_origin()}"
    seqs = reg.seqs_on_origin()
    assert [sha for sha, s in seqs.items() if "1" in s] == [switch["marker_commit"]], seqs
    assert [s for sha, s in seqs.items() if sha != switch["marker_commit"]] == [["2"]], seqs
    reg.fetch_w()   # `status` reads W as last fetched, and the render pushed from <c>
    status = reg.index("status", conf=f2.conf)
    assert imp.LAG_0.search(status.stdout), f"{status.stdout}{status.stderr}"


def test_the_operator_entry_is_pushed_with_the_renderer_identity_and_read_back(pg, tmp_path):
    """Clean, on test 5's GitHub-shaped origin with `render_key=` set and
    `SSH_AUTH_SOCK` in the command's own environment: the cutover makes one
    push, to `ssh://git@github.com/<owner>/<repo>.git` from origin's own URL,
    with `--no-verify`, whose environment alone carries `GIT_SSH_COMMAND`
    with `-i` the key, `IdentitiesOnly=yes` and `BatchMode=yes`,
    `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`, and no
    `SSH_AUTH_SOCK`; a `fetch` of origin follows it, the read-back; the
    checkout's configuration is unchanged; and the marker reads `present`,
    `record_marker` naming the commit pushed (AT-F2, "Ruling" and "Clean",
    TP:5517-5535; D23; design.md, "The push")."""
    f2 = F2Register(tmp_path / "e", pg, github=True)
    reg, imp = f2.reg, f2.imp
    config_before = reg.git("config", "--local", "--list")
    proc = reg.cutover(conf=f2.conf, env={"SSH_AUTH_SOCK": str(tmp_path / "agent.sock")})
    assert proc.returncode == 0, proc.stderr
    calls = f2.calls()
    pushes = [n for n, c in enumerate(calls) if c["sub"] == "push"]
    assert len(pushes) == 1, f"one push: {calls}"
    push = calls[pushes[0]]
    assert GH_SSH in push["argv"] and "--no-verify" in push["argv"], push["argv"]
    env = push["env"]
    ssh = env.get("GIT_SSH_COMMAND", "")
    for word in ("-i", str(f2.key), "IdentitiesOnly=yes", "BatchMode=yes"):
        assert word in ssh, f"GIT_SSH_COMMAND lacks {word!r}: {ssh!r}"
    assert (env.get("GIT_CONFIG_GLOBAL"), env.get("GIT_CONFIG_NOSYSTEM")) == ("/dev/null", "1"), env
    assert "SSH_AUTH_SOCK" not in env, env
    others = [c for n, c in enumerate(calls) if n != pushes[0]]
    assert not any(str(f2.key) in c["env"].get("GIT_SSH_COMMAND", "") for c in others), \
        "the key is in the push's environment alone"
    assert any(c["sub"] == "fetch" for c in calls[pushes[0] + 1:]), f"no read-back: {calls}"
    assert reg.git("config", "--local", "--list") == config_before, "the checkout's config changed"
    switch = imp._switch(pg)
    assert switch["marker_state"] == "present", switch
    assert switch["marker_commit"] == reg.origin_tip(), switch


@pytest.mark.parametrize("case", ["not-pushed", "pushed"])
def test_a_cutover_abort_deletes_seq_1_only_when_the_marker_is_proved_absent(pg, tmp_path, case):
    """`[not-pushed]`: the wrapper fails the push (exit 1, nothing pushed).
    The abort's read-back finds the commit carrying `Register-Seq: 1` absent
    from origin, so seq 1 is deleted, the head reads the import's seq, 0,
    and the switch reads `files` with the marker `absent`; the cutover exits
    with PC-10's abort code. `[pushed]`: the wrapper pushes, then exits 1.
    The read-back finds the marker, so the cutover completes:
    `record_marker` sets it `present`, and seq 1 stays (AT-F2, "Push
    failed" and "Pushed, reported failed", TP:5538-5547)."""
    f2 = F2Register(tmp_path / "e", pg)
    reg, imp = f2.reg, f2.imp
    f2.arm({"call": "push", "mode": "fail" if case == "not-pushed" else "after-fail"})
    proc = reg.cutover(conf=f2.conf)
    calls = f2.calls()
    pushed = [n for n, c in enumerate(calls) if c["sub"] == "push"]
    assert pushed, f"the cutover made no push: exit {proc.returncode}: {proc.stderr}"
    assert any(c["sub"] == "fetch" for c in calls[pushed[0] + 1:]), f"no read-back: {calls}"
    if case == "not-pushed":
        assert proc.returncode == imp.load_indexer().EXIT_CUTOVER_ABORTED, proc.stderr
        assert reg.origin_tip() == reg.c and reg.seqs_on_origin() == {}
        assert imp._seqs(pg) == [(0, "import")], "seq 1 is deleted"
        assert imp._head(pg) == 0
        switch = imp._switch(pg)
        assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), switch
    else:
        assert proc.returncode == 0, proc.stderr
        assert imp._seqs(pg) == [(0, "import"), (1, "cutover")], "seq 1 stays"
        switch = imp._switch(pg)
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
        assert list(reg.seqs_on_origin().values()) == [["1"]]
        assert switch["marker_commit"] == reg.origin_tip()


@pytest.mark.parametrize("command", ["cutover", "rollback"])
def test_an_unconfirmed_operator_push_exits_3_and_its_rerun_reads_origin_first(pg, tmp_path,
                                                                                command):
    """The push is made and the read-back's fetch fails, so the push can be
    neither confirmed nor disproved. `[cutover]`: `cutover` exits 3 and
    changes nothing more; the switch stays `primary` with the marker
    `adding`, and a write exits 69 on the switch its snapshot reads, or on
    LR002. `[rollback]`, after a clean
    cutover and `rollback --hold-marker` (steps 0 to 2): `rollback` exits 3
    and the marker stays `removing`. Disarmed, the rerun reads origin back
    first, before any push, and completes: the marker `present`, or
    `absent` with `lanes/STORE` gone from origin's tip (AT-F2,
    "Unconfirmed", TP:5548-5554; design.md section 2.1)."""
    f2 = F2Register(tmp_path / "e", pg)
    reg, imp = f2.reg, f2.imp
    in_doubt = imp.load_indexer().EXIT_IN_DOUBT
    unconfirmed = {"call": "fetch", "mode": "fail", "after_push": True}
    if command == "cutover":
        f2.arm(unconfirmed)
        proc = reg.cutover(conf=f2.conf)
        assert proc.returncode == in_doubt, f"exit {proc.returncode}: {proc.stderr}"
        switch = imp._switch(pg)
        assert (switch["mode"], switch["marker_state"]) == ("primary", "adding"), switch
        assert list(reg.seqs_on_origin().values()) == [["1"]], "the push was made"
        head = imp._head(pg)
        f2.arm()                # disarmed: a fetch of the write's own is no failure of this case
        wrote = reg.write("a write while the marker is adding")
        assert wrote.returncode == imp.load_indexer().EXIT_UNAVAILABLE, wrote.stderr
        # THE MARKER'S REFUSAL (lane 3's LR002 ruling, #165 6836905010; T278f's
        # form): T415's writer meets the marker at its first snapshot, whose
        # check 4 names the switch it read, the marker `adding`, before any
        # commit call (`lanes-index:3834-3838` at pair-m33a `8ba10b4e`); a
        # commit call would get LR002.
        assert "LR002" in wrote.stderr or "marker adding" in wrote.stderr, wrote.stderr
        assert imp._head(pg) == head, "the refused write wrote nothing"
        f2.arm()
        rerun = reg.cutover(conf=f2.conf)
        assert rerun.returncode == 0, rerun.stderr
        assert _first_reach(f2.calls()) == "fetch", f2.calls()
        assert not any(c["sub"] == "push" for c in f2.calls()), "the rerun pushed again"
        switch = imp._switch(pg)
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
        assert switch["marker_commit"] == reg.origin_tip()
        return
    assert reg.cutover(conf=f2.conf).returncode == 0
    assert imp._switch(pg)["marker_state"] == "present", imp._switch(pg)
    held = reg.index("rollback", "--hold-marker", conf=f2.conf)
    assert held.returncode == 0, held.stderr
    f2.arm(unconfirmed)
    proc = reg.index("rollback", conf=f2.conf)
    assert proc.returncode == in_doubt, f"exit {proc.returncode}: {proc.stderr}"
    switch = imp._switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("files", "removing"), switch
    f2.arm()
    rerun = reg.index("rollback", conf=f2.conf)
    assert rerun.returncode == 0, rerun.stderr
    assert _first_reach(f2.calls()) == "fetch", f2.calls()
    switch = imp._switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), switch
    assert "lanes/STORE" not in reg.origin_git("ls-tree", "-r", "--name-only", "refs/heads/main",
                                               "lanes/")


def test_no_operator_command_holds_a_transaction_across_git(pg, tmp_path):
    """Held across git: with the cutover's push held on the wrapper's FIFO
    for 6 s, past the writer role's 5 s idle bound, no session is idle in a
    transaction while git holds, and the cutover still completes, since its
    transaction committed before any git step (AT-F2, "Held across git",
    TP:5555-5557; F23; design.md section 2.1)."""
    f2 = F2Register(tmp_path / "e", pg)
    reg, imp = f2.reg, f2.imp
    fifo = _fifo(tmp_path)
    f2.arm({"call": "push", "mode": "hold", "fifo": str(fifo), "count": 1})
    run = reg.popen("cutover", "--import", reg.c, conf=f2.conf)
    writer = _open_when_held(fifo, run)
    try:
        assert writer is not None, \
            f"the cutover never reached its push: {run.communicate(timeout=300)}"
        idle = imp._rows(pg, "SELECT count(*) AS n FROM pg_stat_activity WHERE state LIKE "
                             "'idle in transaction%' AND datname = current_database()")
        time.sleep(6)
        idle += imp._rows(pg, "SELECT count(*) AS n FROM pg_stat_activity WHERE state LIKE "
                              "'idle in transaction%' AND datname = current_database()")
    finally:
        if writer is not None:
            os.close(writer)
    out, err = run.communicate(timeout=300)
    assert idle == [{"n": 0}, {"n": 0}], "a session sat idle in a transaction across git"
    assert run.returncode == 0, err
    switch = imp._switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch


@pytest.mark.parametrize("command", ["cutover", "rollback"])
def test_a_render_stops_before_an_operator_seq_not_yet_on_origin(pg, tmp_path, command):
    """`[cutover]`: with the cutover's push held, seq 1 stands in SQL and is
    not on origin; a render meanwhile renders nothing for it and ends, with
    no push, and the cutover then completes. `[rollback]`: after a clean
    cutover, two writes and `rollback`'s entry at `k+1` commit while every
    push fails, so seqs 2 to `k` are not on origin; disarmed, a render
    pushes them, stops before `k+1`, and ends (AT-F2, "Push failed" and "A
    rollback's entry at k+1", TP:5538-5545; lane 4's section, "F2, the stop
    at an operator seq")."""
    f2 = F2Register(tmp_path / "e", pg)
    reg, imp = f2.reg, f2.imp
    if command == "cutover":
        fifo = _fifo(tmp_path)
        f2.arm({"call": "push", "mode": "hold", "fifo": str(fifo), "count": 1})
        run = reg.popen("cutover", "--import", reg.c, conf=f2.conf)
        writer = _open_when_held(fifo, run)
        try:
            assert writer is not None, \
                f"the cutover never reached its push: {run.communicate(timeout=300)}"
            assert imp._seqs(pg)[-1] == (1, "cutover")
            render = reg.index("render", "--checkout", reg.wip, conf=reg.primary_conf,
                               timeout=120)
            ran = [c for c in f2.calls() if c["sub"] == "push" and c["outcome"] != "held"]
            assert ran == [], f"the render pushed: {ran}; {render.stderr}"
            assert reg.origin_tip() == reg.c, "the render pushed a commit for seq 1"
        finally:
            if writer is not None:
                os.close(writer)
        out, err = run.communicate(timeout=300)
        assert run.returncode == 0, err
        assert list(reg.seqs_on_origin().values()) == [["1"]]
        return
    assert reg.cutover(conf=f2.conf).returncode == 0
    assert imp._switch(pg)["marker_state"] == "present", imp._switch(pg)
    marker = reg.origin_tip()
    f2.arm({"call": "push", "mode": "fail"})
    for n in (1, 2):
        wrote = reg.write(f"write {n} before the rollback")
        assert wrote.returncode == 0, f"{wrote.stdout}{wrote.stderr}"
    f2.settle()
    k = imp._head(pg)
    assert k == 3
    rolled = reg.index("rollback", conf=f2.conf)
    assert rolled.returncode != 0, "the rollback's render pushed with every push failing"
    assert imp._seqs(pg)[-1] == (k + 1, "rollback"), imp._seqs(pg)
    switch = imp._switch(pg)
    assert (switch["mode"], switch["marker_state"]) == ("files", "removing"), switch
    assert reg.origin_tip() == marker, "a seq reached origin with every push failing"
    f2.arm()
    render = reg.index("render", "--checkout", reg.wip, conf=reg.primary_conf, timeout=120)
    seqs = [s for s in reg.seqs_on_origin(marker).values()]
    assert seqs == [["2"], ["3"]], f"the render pushes 2 to k and stops before k+1: {seqs}; " \
                                   f"{render.stderr}"
