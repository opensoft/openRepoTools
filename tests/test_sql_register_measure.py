# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 9, the measured cost of one write and what a lane feels
(AT-9; the test plan's section 5; opensoft/openRepoTools#165).

THIS MODULE TODAY holds lane 2's T226 part (L2-N8, phase N):

  * `test_one_write_cost_is_recorded_and_every_write_commits[<path>-<store>]`
    (M1 and M2), at the fixture's settings and durable: `[new-psql-<store>]`,
    200 writes through a new `psql` process each; `[design-<store>]`, M1 in
    the design's form (Q7 (A'')), a `register snapshot` call and a `register
    commit` call, each a `lanes-index` process, cold once and 20 warm; and
    `[session-<store>]`, 200 writes in one session under `\\timing`;
  * `test_a_tls_and_scram_connect_on_loopback_is_timed_and_verified` (M12's
    CI row), on T229's TLS cluster;
  * lane 3's `--last` cost rows (#165 6755922262; F10-OWED item 35):
    `test_journal_last_is_explained_per_statement_and_timed_against_t_r[<log>]`,
    on a clone of `tmpl_imported` for its largest log and for a renamed log,
    then with the journal grown 2x and 5x; and
    `test_swapped_with_several_candidates_is_timed_beside_its_journal_last_calls`.

and lane 2's T255 part (L2-W6, phase W):

  * `test_each_verb_is_timed_end_to_end_in_both_modes[<verb>]` (M7), in files
    mode against a local bare origin and on primary;
  * `test_each_paths_connections_and_queries_are_counted[<path>]` (M13), the
    paths `m1`, `m2`, `m6`, `m7`, `m9` and `m10` once each on T229's counting
    cluster (T237 writes `[m5]`);
  * `test_the_image_cache_check_and_a_miss_are_timed_per_attempt`, through
    lane 1's T302 API;
  * `test_each_shape_on_a_delayed_relay_is_recorded[<shape>-<rtt>]`, under
    section 5.6's option B, which lane 3 ruled (R-P23);

and T254's M9 (L2-W5, phase W):
`test_the_bind_and_the_guards_set_row_state_are_timed_in_both_modes[<mode>]`,
one case per mode, `[files]` and `[primary]` (TP:6346; F12b's T254 text,
R-F11-2). T254's AT-F6 guard cases are in `tests/test_sql_register_guard.py`,
the guard line's.

T226's guard parts, M5b's `test_todays_direct_guard_is_timed_in_its_four_parts`
and M10's `test_the_guards_register_parse_is_timed_on_a_real_sized_register_beside_todays_six_reads_through_git`,
are in `tests/test_sql_register_guard.py`, which a later line writes once
T203c's session-record helper is built.

EACH CASE ASSERTS CORRECTNESS ONLY (section 5.4): every timed write
committed, so the journal grew by exactly n and each `write_id` appears once;
every call exited 0 with the answer it must give. Its figures go to the
job's log and to `$GITHUB_STEP_SUMMARY` where that is set, each row naming
the host, the store, the path, the statistic and n, and the link (the RTT,
TLS, and the path's connections and Query messages from M13), never into a
CI threshold. Statistics are section 5.3's: the first call apart as cold,
then median and p95 by nearest rank, min-max and n over the warm calls.

THE REGISTER, "against an import", in T210's form (lane 2's
`test_sql_register_render.py`, whose helpers are copied below, since each
task owns one file): a files-mode estate at commit C with a bare origin,
loaded by AT-LR006's route (TP:4610-4615) as `lanes_register_writer`:
`commit_write` with an `import` entry of C's render set, a `cutover` entry
writing D21's five `lanes/STORE` fields, then `record_marker`, so the switch
is `primary` with the marker `present`. The `--last` rows clone
`tmpl_imported` instead (T227; N2's form in `test_sql_register_order.py`),
since lane 3 asks for them there, and bring the clone to `primary` the same
way.

A WRITE HERE IS ONE APPENDED LOG LINE (a `log NOTED` line), sent as the
commit call sends it (contract section 2.3; lane 1's
`register_commit_request` at `refs/l1/T112`): one request on stdin,
`BEGIN ISOLATION LEVEL SERIALIZABLE \\; SELECT lanes_register.commit_write(n,
'<write id>', <client>, '<generation>', '<entry>'::jsonb) \\; COMMIT;`, with
section 2.2's argv and D9's commit row in `PGOPTIONS`. Its entry carries the
edit and the `files` row, the image's digest computed here, and no
structured rows, which `commit_write` takes as empty lists.

REAL ENGINE. Every case depends on `pg_engine` (T205), so without
PostgreSQL 16 each skips with T205's banner. They fail until lane 1's T107
(L1-A6, the schema and `commit_write`), T111 (L1-A9, `register snapshot`),
T112 (L1-A10, `register commit`) and T114 (L1-A12, `journal --last`), lane
5's L5-A3 and L5-A5 (T506's `swapped` on primary), and lane 2's T227 (the
bootstrap's template and `tmpl_imported`), T228 and T229 (the TLS and
counting clusters, and the relay) land; T255's also wait for lane 4's L4-B3
and L4-B8 (the verbs on primary) and lane 1's T302 (the image cache); M9
waits for lane 4's L4-B9 and lane 5's L5-A1 and L5-B1. `lanes-index` runs as T203's flipped copy, `RENDER_GIT_HALF = True`,
so `mode=primary` loads (open point 3), and connects as two logins of this
module's own, members of the writer and the reader groups, by the cluster's
trust.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

import pgcluster
from conftest import REPO, WINDOWS_SKIP
from pgcluster import Database
from sql_register_helpers import LANES_INDEX, RENDER_GIT_HALF_LINE, flipped_copy

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280; `tests/sql_register_gate.py` reads it): the
#: tasks each id waits for, from the Orders of T226, T237, T254 and T255
#: (tasks:2177, :2302, :2412, :2419 and :2428 at 204145ae). In a gated run an
#: id is skipped while any of its tasks has no marker in
#: `tests/sql_register_landed/`; M9's `[files]` waits for none. T281 removes
#: it with the gate.
SQL_REGISTER_GATE_TABLE = {
    "test_a_tls_and_scram_connect_on_loopback_is_timed_and_verified": ("T111", "T112", "T229"),  # T226; tasks:2177
    "test_each_paths_connections_and_queries_are_counted": ("T302", "T413", "T414", "T415", "T421", "T422"),  # T255; tasks:2428
    "test_each_shape_on_a_delayed_relay_is_recorded": ("T302", "T413", "T414", "T415", "T421", "T422"),  # T255; tasks:2428
    "test_each_verb_is_timed_end_to_end_in_both_modes": ("T302", "T413", "T414", "T415", "T421", "T422"),  # T255; tasks:2428
    "test_journal_last_is_explained_per_statement_and_timed_against_t_r": ("T111", "T112", "T114"),  # T226; tasks:2177
    "test_one_write_cost_is_recorded_and_every_write_commits": ("T105", "T107", "T227"),  # T226; tasks:2177
    "test_swapped_with_several_candidates_is_timed_beside_its_journal_last_calls": ("T111", "T112", "T114", "T401", "T402", "T403", "T404", "T405", "T406", "T407", "T408", "T504", "T505", "T506"),  # T226; tasks:2177
    "test_the_bind_and_the_guards_set_row_state_are_timed_in_both_modes": ("T427", "T428", "T502", "T510"),  # T254; tasks:2419
    "test_the_image_cache_check_and_a_miss_are_timed_per_attempt": ("T302", "T413", "T414", "T415", "T421", "T422"),  # T255; tasks:2428
    "test_each_paths_connections_and_queries_are_counted[m5]": ("T229", "T512", "T513"),  # T237; tasks:2302
    "test_the_bind_and_the_guards_set_row_state_are_timed_in_both_modes[files]": (),  # T254; tasks:2412
    "test_one_write_cost_is_recorded_and_every_write_commits[design-durable]": ("T105", "T107", "T111", "T112", "T227"),  # T226; tasks:2177
    "test_one_write_cost_is_recorded_and_every_write_commits[design-fixture]": ("T105", "T107", "T111", "T112", "T227"),  # T226; tasks:2177
}

LANES_EDIT = REPO / "lanes-edit.sh"

#: The register's schema, `register_schema=`'s default (contract section 2.5).
SCHEMA = "lanes_register"
WRITER, READER = "lanes_register_writer", "lanes_register_reader"
#: The logins `lanes-index` and this module's own calls connect as. Made
#: once per cluster, members of the writer and the reader groups, with no
#: password.
LOGIN_WRITER, LOGIN_READER = "t226_register_writer", "t226_register_reader"
#: T227's template with test 7's register imported, and the database-level
#: grants a clone does not copy (section 1.4; N2's `CONNECT_TO`).
IMPORTED = "tmpl_imported"
CONNECT_TO = "lanes_register_writer, lanes_register_reader, lanes_indexer"

WS = "Eagle"
AUTHOR = "T226 measure <t226@example.invalid>"
OPERATOR = "repoA-2"
MARKER_COMMIT = "e" * 40
STORE_UTC = "2026-11-09T10:00:00Z"

#: The register's punctuation, spelled by code point so no raw character
#: enters this file: the em dash, the middle dot of a state cell, the arrow.
EM, DOT, ARROW = chr(0x2014), chr(0x00B7), chr(0x2192)

SID_A1 = "aaaaaaaa-0001-4000-8000-00000000a001"
SID_A2 = "aaaaaaaa-0003-4000-8000-00000000a003"
SID_Z1 = "eeeeeeee-0001-4000-8000-00000000e001"
TIP = "0123456789abcdef0123456789abcdef01234567"

RENDER_SET = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|archive/[^/]+\.md"
                        r"|log/(?!README\.md$)[^/]+\.md)$")
LOG_PATH = re.compile(r"^lanes/log/(?!README\.md$)[^/]+\.md$")
STORE_PATH = "lanes/STORE"

#: Section 2.2's one argv for every register call (F10-OWED item 4), and
#: D9's rows as `PGOPTIONS` (lane 1's `REGISTER_BOUNDS` at `refs/l1/T114`,
#: CLI412:250-255): the commit's, and the reader's for `journal --last`.
PSQL_REGISTER_ARGV = ("--no-psqlrc", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                      "-v", "VERBOSITY=verbose", "-v", "SHOW_CONTEXT=never")
COMMIT_OPTIONS = "-c lock_timeout=2000 -c statement_timeout=5000"
READ_STATEMENT_MS = 3000
#: `T_r` = `N_a`*`c` + 4 s (CLI412:255): 6 s at `c` = 2 and one address,
#: the URL's `connect_timeout` default (CLI412:296).
T_R_S = 1 * 2 + 4

N_WRITES = 200       # M1 and M2: at least 200 writes (section 5.3; R1)
N_WARM = 20          # M7, M12 and act 3's rows: 20 warm runs and the first

def _row(lane: str, sid: str, state: str, started: str = "2026-10-01T00:00Z") -> str:
    return (f"| `{lane}` | harness `{sid}` | Eagle / test / brett | {started} | none "
            f"| handoffs/{lane}.md | {state} |")


#: AT-1's fixture register at C ("Fixture"): three lanes, one of them
#: archived; `aliases.tsv` entries; a lane with `HOLD`, `LANDING` and
#: `LANDED` lines; a log with `WORD` lines whose UTC carries milliseconds
#: (Q4(d)(i)). `lanes/repos.tsv` and `lanes/log/README.md` are outside the
#: render set, and `register snapshot --tree` takes them from the checkout.
SEED = {
    "lanes/LANES.md": "\n".join([
        f"# LANES.md {EM} test 1's fixture register",
        "",
        "| lane | session id | workstation / env / user | started (UTC) | objects owned "
        "| handoff path | state |",
        "|---|---|---|---|---|---|---|",
        _row("repoA-1", SID_A1, f"LIVE {DOT} 2026-10-01T01:00:00Z {DOT} working"),
        _row("repoA-2", SID_A2, f"PAUSED {DOT} 2026-10-01T02:00:00Z {DOT} parked"),
        "",
        f"HOLD {EM} lane repoA-1 (Eagle), window w, 2026-10-01T03:00:00Z: opensoft/repoA main "
        f"{TIP} for a frozen window",
        f"LANDING {EM} lane repoA-1, session {SID_A1}@Eagle, 2026-10-01T03:10:00Z, PR #7 into "
        f"opensoft/repoA main",
        f"LANDED {EM} lane repoA-1, session {SID_A1}@Eagle, 2026-10-01T03:15:00Z, PR #7 into "
        f"opensoft/repoA main {ARROW} abc1234",
        ""]),
    "lanes/aliases.tsv": "# old\tnew\tutc\nrepoOld-1\trepoA-2\t2026-09-30T00:00:00Z\n",
    "lanes/archive/LANES-retired.md": "\n".join([
        "# retired rows (Amendment 19(d))", "",
        _row("repoZ-1", SID_Z1, f"RETIRED {DOT} 2026-09-02T00:00:00Z {DOT} retired"),
        ""]),
    "lanes/log/repoA-1.md": "\n".join([
        f"# lane repoA-1 {EM} object log (lane-collision-protocol Amendment 7)",
        f"STARTED {EM} lane repoA-1, session {SID_A1}@Eagle, 2026-10-01T00:00:00Z, "
        f"lane:repoA-1 {ARROW} home opensoft/repoA; dir /work/repoA1",
        ""]),
    "lanes/log/repoA-2.md": "\n".join([
        f"# lane repoA-2 {EM} object log (lane-collision-protocol Amendment 7)",
        f"STARTED {EM} lane repoA-2, session {SID_A2}@Eagle, 2026-10-01T02:00:00Z, "
        f"lane:repoA-2 {ARROW} home opensoft/repoA; dir /work/repoA2",
        f"NOTED {EM} lane repoA-2, session {SID_A2}@Eagle, 2026-10-01T02:10:00.123Z, "
        f"lane:repoA-2 {EM} a stamp with milliseconds",
        f"NOTED {EM} lane repoA-2, session {SID_A2}@Eagle, 2026-10-01T02:11:00.456Z, "
        f"lane:repoA-2 {EM} another",
        ""]),
    "lanes/log/README.md": "# the object logs\n",
    "lanes/repos.tsv": "# alias\towner/repo\nrepoA\topensoft/repoA\n",
}


# ------------------------------------------------------------------ the estate
def git(cwd: Path, *args: str, env: dict | None = None) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          env=env, check=False)
    assert proc.returncode == 0, f"git {' '.join(args)} in {cwd}: {proc.stderr}{proc.stdout}"
    return proc.stdout


def git_env(home: Path) -> dict:
    """A git with no person's configuration in it, and an identity of its own."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "PG", "LANES_", "TMUX"))}
    env.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME="T226 estate", GIT_AUTHOR_EMAIL="t226@example.invalid",
               GIT_COMMITTER_NAME="T226 estate", GIT_COMMITTER_EMAIL="t226@example.invalid",
               LC_ALL="C")
    return env


class Estate:
    """A bare origin and the lane's checkout at C: SEED (or `files`) committed
    and pushed to `main`. `register snapshot --checkout` reads
    `lanes/repos.tsv` and `lanes/log/README.md` from its `origin/main`."""

    def __init__(self, root: Path, files: dict = None):
        self.root = root
        self.home = root / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.env = git_env(self.home)
        self.origin = root / "origin.git"
        self.checkout = root / "checkout"
        git(root, "init", "-q", "--bare", "-b", "main", str(self.origin), env=self.env)
        git(root, "clone", "-q", str(self.origin), str(self.checkout), env=self.env)
        self.files = dict(files if files is not None else SEED)
        for path, text in self.files.items():
            target = self.checkout / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
        git(self.checkout, "add", "-A", env=self.env)
        git(self.checkout, "commit", "-q", "-m", "C: the fixture register", env=self.env)
        git(self.checkout, "push", "-q", "origin", "main", env=self.env)
        self.c = git(self.checkout, "rev-parse", "HEAD", env=self.env).strip()
        self.lanes_tree = git(self.checkout, "rev-parse", f"{self.c}:lanes", env=self.env).strip()

    def render_set(self) -> dict:
        """C's render set, {path: bytes}."""
        return {p: t.encode("utf-8") for p, t in self.files.items() if RENDER_SET.match(p)}

    def state(self) -> tuple:
        """What a write through the storage layer never changes in the
        checkout: HEAD, `status --porcelain=v1 -uall`, the index's digest and
        `origin/main`."""
        index = self.checkout / ".git" / "index"
        return (git(self.checkout, "rev-parse", "HEAD", env=self.env),
                git(self.checkout, "status", "--porcelain=v1", "-uall", env=self.env),
                hashlib.sha256(index.read_bytes()).hexdigest() if index.exists() else "-",
                git(self.checkout, "rev-parse", "origin/main", env=self.env))


# ------------------------------------------------------------------ the SQL side
def psql(db, script: str, role: str = None) -> subprocess.CompletedProcess:
    """One `psql` as the fixture's superuser, as `role` where one is named,
    with the commit call's settings, so a refusal's first stderr line is
    `ERROR:  <SQLSTATE>: <message>`."""
    head = "\\set VERBOSITY verbose\n\\set SHOW_CONTEXT never\nSET client_encoding = 'UTF8';\n"
    if role:
        head += f"SET ROLE {role};\n"
    return subprocess.run([db.psql_bin, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                          input=head + script, capture_output=True, encoding="utf-8",
                          errors="replace", env=db.env(appname="t226"), timeout=120, check=False)


def sql(db, script: str, role: str = None) -> str:
    proc = psql(db, script, role)
    assert proc.returncode == 0, (f"psql{' as ' + role if role else ''} exited "
                                  f"{proc.returncode}: {proc.stderr.strip()}\n{script}")
    return proc.stdout.strip()


def rows(db, query: str) -> list:
    """`query`'s rows as JSON objects, read in the register's schema."""
    out = sql(db, f"SET search_path TO {SCHEMA};\n"
                  f"SELECT coalesce(jsonb_agg(q), '[]'::jsonb) FROM ({query}) q;")
    return json.loads(out.splitlines()[-1])


def head(db) -> int:
    return rows(db, "SELECT seq FROM register_head")[0]["seq"]


def _lines(data: bytes) -> list:
    text = data.decode("utf-8")
    assert text.endswith("\n"), "every fixture file ends with a newline"
    return text[:-1].split("\n")


def _entry(kind: str, verb: str, journal: dict = None, **parts) -> dict:
    body = {"kind": kind, "verb": verb, "lane": OPERATOR, "workstation": WS, "author": AUTHOR,
            "message": f"t226: {kind}"}
    body.update(journal or {})
    return {"journal": body, "not_after": "2100-01-01T00:00:00Z", **parts}


def _creates(files: dict) -> tuple:
    """Each of `files` ({path: bytes}) created, then its lines appended, and
    each path's digest as it renders: the edits and the `files` rows."""
    edits, ordinal = [], 0
    for path in sorted(files):
        ordinal += 1
        edits.append({"ord": ordinal, "op": "create", "path": path})
        for text in _lines(files[path]):
            ordinal += 1
            edits.append({"ord": ordinal, "op": "append", "path": path, "new_text": text})
    return edits, [{"path": p, "present": True, "sha256": hashlib.sha256(files[p]).hexdigest(),
                    "final_newline": True} for p in sorted(files)]


def _commit_call(db, base: int, body: dict) -> int:
    """The commit call as the writer sends it, as `lanes_register_writer`
    (section 1.3's step 3; AT-LR006's fixture), and the seq it committed."""
    gen = rows(db, "SELECT generation FROM register_switch")[0]["generation"]
    version = rows(db, "SELECT version FROM schema_version")[0]["version"]
    literal = json.dumps(body, ensure_ascii=True).replace("'", "''")
    out = sql(db, f"BEGIN ISOLATION LEVEL SERIALIZABLE;\n"
                  f"SELECT {SCHEMA}.commit_write({base}, '{uuid.uuid4()}'::uuid, {version}, "
                  f"'{gen}'::uuid, '{literal}'::jsonb);\nCOMMIT;", WRITER)
    return int(out.splitlines()[-1])


def import_to_primary(db, estate: Estate) -> int:
    """AT-LR006's route (TP:4610-4615) over C: an `import` entry of C's render
    set, a `cutover` entry, then `record_marker`, by the documented functions
    as `lanes_register_writer`. Returns the import's seq."""
    edits, files = _creates(estate.render_set())
    imported = _commit_call(db, head(db), _entry(
        "import", "import", {"git_commit": estate.c, "git_tree": estate.lanes_tree},
        edits=edits, files=files))
    store = "".join(f"{line}\n" for line in (
        "store=primary", "database=t226", f"import={estate.c}",
        f"lanes-tree={estate.lanes_tree}", f"utc={STORE_UTC}")).encode("utf-8")
    edits, files = _creates({STORE_PATH: store})
    cut = _commit_call(db, imported, _entry("cutover", "cutover", edits=edits, files=files))
    version = rows(db, "SELECT version FROM schema_version")[0]["version"]
    marker = sql(db, f"SELECT {SCHEMA}.record_marker({version}, {cut}, '{MARKER_COMMIT}', "
                     f"'{WS}');", WRITER)
    assert marker.splitlines()[-1] == "present", f"record_marker answered {marker!r}"
    assert rows(db, "SELECT mode, marker_state FROM register_switch") == \
        [{"mode": "primary", "marker_state": "present"}]
    return imported


# ------------------------------------------------------------------ lanes-index
def require_the_constant() -> None:
    """The flipped copy needs Q6(c)'s constant (lane 1's T105, L1-A4): an
    assertion, so a case without it fails by saying so."""
    assert len(RENDER_GIT_HALF_LINE.findall(LANES_INDEX.read_bytes())) == 1, (
        f"{LANES_INDEX} holds no single `RENDER_GIT_HALF = ...` line, Q6(c)'s build constant "
        f"(L1-A4, lane 1's T105), so no copy can be flipped to load mode=primary")


def flipped(tmp_path: Path, name: str = "bin") -> Path:
    """T203's flipped copy, `RENDER_GIT_HALF = True`, so `mode=primary` loads,
    with `lanes-edit.sh` beside it (the copy rule, CLI4.5 section 6)."""
    require_the_constant()
    copy = flipped_copy(LANES_INDEX, tmp_path / name, True)
    shutil.copy2(str(LANES_EDIT), str(copy.parent / "lanes-edit.sh"))
    return copy


def ensure_logins(db) -> None:
    """The writer's and the reader's login, once per cluster (roles are
    cluster-wide), members of their groups, with no password."""
    for login, group in ((LOGIN_WRITER, WRITER), (LOGIN_READER, READER)):
        sql(db, f"DO $l$ BEGIN CREATE ROLE {login} LOGIN IN ROLE {group}; "
                f"EXCEPTION WHEN duplicate_object THEN NULL; END $l$;")


def primary_config(path: Path, register_url: str, reader_url: str,
                   passfile: Path | None = None) -> Path:
    """A 0600 `lanes-index.conf` with `mode=primary` and the register's two
    URLs (contract section 2.5), outside every work tree."""
    lines = ["mode=primary", f"register_url={register_url}", f"reader_url={reader_url}"]
    if passfile is not None:
        lines += [f"register_passfile={passfile}", f"reader_passfile={passfile}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def index_env(tmp_path: Path, conf: Path, home: Path, **extra) -> dict:
    """The environment `lanes-index` runs in: no inherited `PG*`, `LANES_*`,
    `GIT_*` or `TMUX*` (#160's run-wide `LANES_INDEX=off` among them), this
    case's configuration, state directory and git identity."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PG", "LANES_", "GIT_", "TMUX"))}
    env.update(git_env(home))
    env.update(LANES_INDEX_CONFIG=str(conf), XDG_STATE_HOME=str(tmp_path / "state"), LC_ALL="C")
    env.update(extra)
    return env


def run_index(copy: Path, args, env: dict, cwd: Path = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(copy), *[str(a) for a in args]],
                          capture_output=True, encoding="utf-8", errors="replace", env=env,
                          timeout=120, cwd=str(cwd) if cwd else None, check=False,
                          stdin=subprocess.DEVNULL)


def keys(stdout: str) -> dict:
    """A `key=value` output's keys, each its first value (section 3.2)."""
    found = {}
    for line in stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key not in found:
            found[key] = value
    return found


def utc_of(epoch: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _canonical_rows(changes: list, images: dict) -> str:
    """Section 3.2's canonical rows for every path in `changes.tsv`, sorted by
    path bytewise, each LF-ended: `<path>` TAB `1` TAB `<sha256>`, or `0` and
    `-` for a path the write removes."""
    out = []
    for path in sorted({c[1] for c in changes}, key=lambda p: p.encode("utf-8")):
        if path in images:
            out.append(f"{path}\t1\t{hashlib.sha256(images[path]).hexdigest()}\n")
        else:
            out.append(f"{path}\t0\t-\n")
    return "".join(out)


class PrimaryRegister:
    """C imported and brought to `primary`, a flipped copy, and the
    configuration that reaches the test's database as this module's logins."""

    def __init__(self, pg, tmp_path: Path, files: dict = None):
        self.pg = pg
        self.estate = Estate(tmp_path / "estate", files)
        self.imported = import_to_primary(pg, self.estate)
        ensure_logins(pg)
        self.copy = flipped(tmp_path)
        (tmp_path / "conf").mkdir()
        conf = primary_config(tmp_path / "conf" / "lanes-index.conf", pg.url(LOGIN_WRITER),
                              pg.url(LOGIN_READER))
        self.env = index_env(tmp_path, conf, self.estate.home)


# ------------------------------------------------------------------ the fake writer
def _edit_log_noted(lane: str, sid: str, words: str):
    """`log NOTED`'s line on `lane`'s log, as an edit of the scratch tree."""
    def edit(tree: Path, utc: str) -> dict:
        line = f"NOTED {EM} lane {lane}, session {sid}@{WS}, {utc}, lane:{lane} {EM} {words}"
        path = tree / "lanes" / "log" / f"{lane}.md"
        path.write_bytes(path.read_bytes() + line.encode("utf-8") + b"\n")
        return {"line": line, "renames": {}}
    return edit


def _edit_rename_log(old: str, new: str):
    """A log renamed whole (`renames.tsv`, contract section 3.3; the verb's
    `LOG_RENAMED_FROM`, Y:5060): a `D` and an `A` line in `changes.tsv`."""
    def edit(tree: Path, utc: str) -> dict:
        (tree / new).parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(tree / old), str(tree / new))
        return {"line": None, "renames": {old: new}}
    return edit


def fake_write(copy: Path, env: dict, checkout: Path, root: Path, lane: str, verb: str,
               edit, message: str) -> dict:
    """One attempt of the storage layer's write entry, as T210's
    `projection_entry` makes it (contract sections 3.2 and 3.3): `register
    snapshot --write-id new ... --tree <root>/tree --checkout <c>`; on 0
    alone, the edit, the attempt directory (with `renames.tsv` where the
    edit renamed) and `register commit`. Returns each call, the code (the
    snapshot's where it did not answer 0, else the commit's) and the
    snapshot's fields."""
    args_sha256 = hashlib.sha256(json.dumps([lane, verb, message]).encode("utf-8")).hexdigest()
    root.mkdir(parents=True, exist_ok=True)
    out = {"snapshot": None, "commit": None, "code": None, "fields": {}, "line": None}
    snap = run_index(copy, ["register", "snapshot", "--write-id", "new", "--lane", lane,
                            "--verb", verb, "--args-sha256", args_sha256,
                            "--tree", root / "tree", "--checkout", checkout], env)
    out["snapshot"] = snap
    if snap.returncode != 0:
        out["code"] = snap.returncode
        return out
    fields = out["fields"] = keys(snap.stdout)
    tree = root / "tree"
    (root / "snapshot").write_text(snap.stdout, encoding="utf-8")
    done = edit(tree, utc_of(int(fields["clock"])))
    out["line"] = done["line"]
    git(tree, "add", "-A", "--", "lanes", env=env)
    changes = []
    for raw in git(tree, "diff", "--cached", "--no-renames", "--raw", "--no-abbrev", "HEAD",
                   env=env).splitlines():
        meta, path = raw.split("\t", 1)
        parts = meta.split()
        changes.append((parts[4], path, parts[2], parts[3]))
    assert changes, "the edit staged a change"
    (root / "changes.tsv").write_text(
        "".join(f"{s}\t{p}\t{o}\t{n}\n" for s, p, o, n in changes), encoding="utf-8")
    if done["renames"]:
        (root / "renames.tsv").write_text(
            "".join(f"{a}\t{b}\n" for a, b in done["renames"].items()), encoding="utf-8")
    images = {}
    for status, path, _old, _new in changes:
        if status in ("A", "M"):
            images[path] = (tree / path).read_bytes()
            target = root / "images" / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(images[path])
    (root / "files").write_text(_canonical_rows(changes, images), encoding="utf-8")
    (root / "msg").write_text(message, encoding="utf-8")
    (root / "author").write_text(AUTHOR + "\n", encoding="utf-8")
    (root / "not_after").write_text(fields["not_after"] + "\n", encoding="utf-8")
    commit = run_index(copy, ["register", "commit", "--write-id", fields["write_id"],
                              "--generation", fields["generation"], "--lane", lane,
                              "--verb", verb, "--args-sha256", args_sha256,
                              "--workstation", WS, root], env)
    out["commit"] = commit
    out["code"] = commit.returncode
    return out


# ------------------------------------------------------------------ the writes
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def images_of(db, paths) -> dict:
    """`render_file` (lane 1's T107) of each of `paths`, {path: bytes}."""
    wanted = ", ".join("'" + p.replace("'", "''") + "'" for p in paths)
    return {r["path"]: base64.b64decode(r["b64"]) for r in rows(
        db, f"SELECT path, encode(render_file(path), 'base64') AS b64 FROM files "
            f"WHERE path IN ({wanted}) ORDER BY path")}


class Appends:
    """Writes of appended log lines, each built as AT-LR006 builds an entry:
    the edits and each touched path's `files` row, whose digest is the image
    `render_file` gives after the write, tracked here from the images read
    at the start. `base` is the head each next write is sent against."""

    def __init__(self, db, paths) -> None:
        self.db = db
        self.images = images_of(db, paths)
        missing = sorted(set(paths) - set(self.images))
        assert not missing, f"no such file in the register: {missing}"
        switch = rows(db, "SELECT generation FROM register_switch")[0]
        self.generation = switch["generation"]
        self.version = rows(db, "SELECT version FROM schema_version")[0]["version"]
        self.base = head(db)
        self.write_ids: list = []

    def entry(self, lane: str, path: str, texts) -> dict:
        edits = []
        for text in texts:
            assert "\n" not in text and "\r" not in text
            edits.append({"ord": len(edits) + 1, "op": "append", "path": path, "new_text": text})
            self.images[path] += text.encode("utf-8") + b"\n"
        args = sha256(json.dumps([lane, "log", list(texts)]).encode("utf-8"))
        return _entry("write", "log", {"lane": lane, "args_sha256": args}, edits=edits,
                      files=[{"path": path, "present": True, "sha256": sha256(self.images[path]),
                              "final_newline": True}])

    def statements(self, entry: dict) -> list:
        """The commit call's three statements for the next write (lane 1's
        `register_commit_request`), and the base moved on by one."""
        write_id = str(uuid.uuid4())
        self.write_ids.append(write_id)
        literal = json.dumps(entry, ensure_ascii=True, separators=(",", ":")).replace("'", "''")
        sent = ["BEGIN ISOLATION LEVEL SERIALIZABLE",
                f"SELECT {SCHEMA}.commit_write({self.base}, '{write_id}', {self.version}, "
                f"'{self.generation}', '{literal}'::jsonb)",
                "COMMIT"]
        self.base += 1
        return sent


def one_call(db, statements: list) -> subprocess.CompletedProcess:
    """One commit call through a new `psql` process: ONE request, the
    statements joined by `\\;`, as the writer's login with D9's commit row."""
    env = db.env(LOGIN_WRITER, appname="t226-commit")
    env["PGOPTIONS"] = COMMIT_OPTIONS
    return subprocess.run([db.psql_bin, *PSQL_REGISTER_ARGV], input=" \\; ".join(statements) + ";\n",
                          capture_output=True, encoding="utf-8", errors="replace", env=env,
                          timeout=60, check=False)


def in_one_session(db, writes: list, timing: bool = False) -> subprocess.CompletedProcess:
    """`writes` (each the commit call's three statements) in ONE `psql`
    session as the writer's login, each statement its own Query, under
    `\\timing` where asked (M2: it leaves out the client)."""
    script = ["\\timing on"] if timing else []
    for statements in writes:
        script += [s + ";" for s in statements]
    env = db.env(LOGIN_WRITER, appname="t226-session")
    return subprocess.run([db.psql_bin, "--no-psqlrc", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                          input="\n".join(script) + "\n", capture_output=True, encoding="utf-8",
                          errors="replace", env=env, timeout=1800, check=False)


def committed_once(db, before: int, write_ids: list) -> None:
    """Section 5.3's correctness alongside: the journal grew by exactly n
    above `before`, and each of the writes' ids appears once."""
    n = len(write_ids)
    assert head(db) == before + n, f"the head is {head(db)}, not {before} + {n}"
    grown = rows(db, f"SELECT count(*) AS n, count(DISTINCT write_id) AS d FROM journal "
                     f"WHERE seq > {before}")[0]
    assert grown == {"n": n, "d": n}, f"the journal grew by {grown}, not {n} distinct writes"
    ids = ", ".join(f"'{w}'" for w in write_ids)
    found = rows(db, f"SELECT count(*) AS n FROM journal WHERE write_id IN ({ids})")[0]["n"]
    assert found == n, f"{found} of the {n} write ids are in the journal"


# ------------------------------------------------------------------ the record
def _stats(samples: list) -> dict:
    """Section 5.3's statistics: median and p95 by nearest rank, min-max, n."""
    ordered = sorted(samples)
    rank = lambda p: ordered[max(0, -(-p * len(ordered) // 100) - 1)]  # noqa: E731
    return {"median": rank(50), "p95": rank(95), "min": ordered[0], "max": ordered[-1],
            "n": len(ordered)}


def figure(measure: str, store: str, path: str, times_ms: list, link: str,
           cold: bool = True) -> str:
    """One recorded row (section 5.4): the host, the store, the path, the
    statistic and n, and the link."""
    warm = _stats(times_ms[1:] if cold else times_ms)
    first = f"cold {times_ms[0]:.2f} ms" if cold else "-"
    return (f"| {measure} | {platform.node()}, {store} | {path} | {first} | median "
            f"{warm['median']:.2f} ms, p95 {warm['p95']:.2f} ms, {warm['min']:.2f}-"
            f"{warm['max']:.2f} ms, n={warm['n']} | {link} |")


def record(lines: list) -> None:
    """The job's log, and `$GITHUB_STEP_SUMMARY` where it is set."""
    print("\n" + "\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


def timed(run) -> tuple:
    """`run()` bracketed on the monotonic clock, exec to exit: (ms, its value)."""
    start = time.monotonic_ns()
    value = run()
    return (time.monotonic_ns() - start) / 1e6, value


def needs(request, name: str, owner: str):
    """A fixture another task provides, looked up only once the engine is
    there, so a case without PostgreSQL 16 skips with T205's banner, and one
    with it fails by saying which task it waits for."""
    try:
        return request.getfixturevalue(name)
    except pytest.FixtureLookupError:
        pytest.fail(f"no fixture `{name}`: {owner} provides it", pytrace=False)


def setting(db, name: str) -> str:
    return sql(db, f"SHOW {name};").splitlines()[-1]


# ------------------------------------------------------------------ the stores
@pytest.fixture()
def durable_db(pg_engine, pg_template_sql, monkeypatch):
    """Test 8's stoppable cluster started with the defaults (section 5.1:
    `fsync`, `synchronous_commit` and `full_page_writes` on): T205's
    `Cluster`, its `FAST` settings left out for this start alone, its own
    template from `pg_template_sql`, and one database cloned from it."""
    monkeypatch.setattr(pgcluster, "FAST", ())
    cluster = pgcluster._started(pg_engine, pg_template_sql)
    monkeypatch.undo()
    patch = pytest.MonkeyPatch()
    patch.setenv("PATH", pgcluster._engine_first(pg_engine.bindir, os.environ.get("PATH", os.defpath)))
    try:
        name = cluster.new_database()
        yield Database(cluster, name)
    finally:
        patch.undo()
        cluster.destroy()


STORES = {"fixture": "pg", "durable": "durable_db"}
#: The store's settings the figure names, as each store must show them.
STORE_SETTINGS = {"fixture": "off", "durable": "on"}


# ============================================================ T226: M1 and M2 (phase N)

@pytest.mark.parametrize("store", list(STORES))
@pytest.mark.parametrize("path", ["new-psql", "design", "session"])
def test_one_write_cost_is_recorded_and_every_write_commits(pg_engine, request, tmp_path, path,
                                                            store):
    """M1 and M2 (section 5.1), at the fixture's settings and durable: 200
    writes, each one appended log line on a register brought to `primary`.

    `[new-psql-<store>]` is M1 as R1 measured it: each write one commit
    call through a new `psql` process. `[design-<store>]` is M1 in the
    design's form under Q7 (A''): a `register snapshot` call and a `register
    commit` call, each a `lanes-index` process with its own Python start,
    cold once and 20 warm (act 3's count, section 5.3; 200 would add minutes
    to the job). `[session-<store>]` is M2: the 200 writes in one `psql`
    session, each write's time the sum of its three statements' `\\timing`.

    The oracle: each call exits 0 and answers the seq it committed; the
    journal grew by exactly n and each `write_id` appears once; the store
    shows the settings its id names. The figures are recorded, never
    asserted."""
    db = request.getfixturevalue(STORES[store])
    reg = PrimaryRegister(db, tmp_path)
    for name in ("fsync", "synchronous_commit", "full_page_writes"):
        assert setting(db, name) == STORE_SETTINGS[store], (
            f"the {store} store runs {name}={setting(db, name)}")
    log = "lanes/log/repoA-1.md"
    writes = Appends(db, [log])
    before = writes.base
    lines = []
    texts = [f"NOTED {EM} lane repoA-1, session {SID_A1}@{WS}, 2026-11-10T00:00:00Z, "
             f"lane:repoA-1 {EM} t226 {path} {store} write {k}" for k in range(N_WRITES)]
    if path == "new-psql":
        times = []
        for k, text in enumerate(texts):
            sent = writes.statements(writes.entry("repoA-1", log, [text]))
            ms, proc = timed(lambda: one_call(db, sent))
            assert (proc.returncode, proc.stdout.strip()) == (0, str(before + k + 1)), (
                f"write {k}: exit {proc.returncode}: {proc.stderr.strip()[-600:]}")
            times.append(ms)
        committed_once(db, before, writes.write_ids)
        lines.append(figure("M1", f"{store} cluster, Unix socket", "one commit call, new `psql`",
                            times, "rtt=0, tls=none, c=1, q=1"))
    elif path == "design":
        design_before, totals = head(db), []
        for k in range(1 + N_WARM):
            ms, done = timed(lambda: fake_write(
                reg.copy, reg.env, reg.estate.checkout, tmp_path / "attempts" / str(k), "repoA-1",
                "log", _edit_log_noted("repoA-1", SID_A1, f"t226 design write {k}"),
                f"lanes-edit.sh log: t226 design write {k}"))
            assert done["code"] == 0, (done["snapshot"].stderr,
                                       done["commit"] and done["commit"].stderr)
            assert done["commit"].stdout.split() == ["committed", str(design_before + k + 1)], (
                done["commit"].stdout)
            totals.append(ms)
        assert head(db) == design_before + 1 + N_WARM, "each design-form write committed once"
        assert rows(db, f"SELECT count(DISTINCT write_id) AS d FROM journal WHERE seq > "
                        f"{design_before}")[0]["d"] == 1 + N_WARM
        lines.append(figure("M1", f"{store} cluster, Unix socket",
                            "the design's write: `register snapshot` + `register commit`",
                            totals, "rtt=0, tls=none, c=2, q=2"))
    else:
        batch = [writes.statements(writes.entry("repoA-1", log, [text])) for text in texts]
        proc = in_one_session(db, batch, timing=True)
        assert proc.returncode == 0, proc.stderr.strip()[-800:]
        out = proc.stdout.splitlines()
        seqs = [line for line in out if line.isdigit()]
        stamps = [float(m.group(1)) for m in map(re.compile(r"^Time: ([0-9.]+) ms").match, out) if m]
        assert seqs == [str(before + k + 1) for k in range(N_WRITES)], "each write answered its seq"
        assert len(stamps) == 3 * N_WRITES, f"{len(stamps)} timings, not three per write"
        committed_once(db, before, writes.write_ids)
        per_write = [sum(stamps[3 * k:3 * k + 3]) for k in range(N_WRITES)]
        lines.append(figure("M2", f"{store} cluster, Unix socket", "one write in a held session",
                            per_write, "rtt=0, tls=none, c=0, q=3"))
    record(lines)


# ============================================================ T226: M12 (phase N)

def test_a_tls_and_scram_connect_on_loopback_is_timed_and_verified(pg_engine, request):
    """M12's CI row (section 5.1; section 5.6): `psql -X -A -t -c 'SELECT 1'`
    against T229's TLS cluster on loopback TCP, with `sslmode=verify-full`
    and SCRAM, exec to exit, cold once and 20 warm; each answers `1`. It is
    verified once: a connect that requires SCRAM (`PGREQUIREAUTH`, libpq 16)
    succeeds, and `pg_stat_ssl` for its own backend says TLS, whose version is
    recorded beside the time (on T229's cluster, `TLSv1.3`). X changed no
    oracle: it asserts TLS in use, never the figure."""
    tls = needs(request, "tls_cluster", "lane 2's T229 (section 5.6's TLS cluster)")
    env = tls.client_env()
    argv = [tls.tool("psql"), "-X", "-A", "-t", "-c", "SELECT 1"]
    times = []
    for _ in range(1 + N_WARM):
        ms, proc = timed(lambda: subprocess.run(argv, capture_output=True, text=True, env=env,
                                                timeout=60, check=False))
        assert (proc.returncode, proc.stdout.strip()) == (0, "1"), proc.stderr
        times.append(ms)
    check = dict(env, PGREQUIREAUTH="scram-sha-256")
    said = subprocess.run([tls.tool("psql"), "-X", "-A", "-t", "-F", "|", "-c",
                           "SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()"],
                          capture_output=True, text=True, env=check, timeout=60, check=False)
    assert said.returncode == 0, f"a connect that requires SCRAM failed: {said.stderr}"
    ssl, version = said.stdout.strip().split("|")
    assert ssl == "t", f"pg_stat_ssl says the connect is not TLS: {said.stdout!r}"
    record([figure("M12", "TLS cluster, loopback TCP", "`psql -c 'SELECT 1'`, a new connect",
                   times, f"rtt=0 (loopback), tls={version}, scram, c=1, q=1")])


# ============================================================ T226: lane 3's `--last` cost rows

#: `journal --last`'s five reads, in `register_last_queries`' order
#: (`refs/l1/T114`, `lanes-index:7086-7108`).
LAST_READS = ("the head", "the generation", "the import seqs",
              "the edits of the path's rename closure", "the journal_files rows of the closure")


def _lanes_index_module():
    """`lanes-index` loaded as a module, as T207's stub loads it for
    `classify`, so this module calls lane 1's own functions."""
    loader = importlib.machinery.SourceFileLoader("lanes_index_t226", str(LANES_INDEX))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def last_statements(path: str) -> list:
    """`journal --last`'s reads as lane 1's code builds them,
    `register_last_queries(path, None)`, so what is explained is what is
    sent."""
    make = getattr(_lanes_index_module(), "register_last_queries", None)
    assert make is not None, ("lanes-index has no `register_last_queries`: lane 1's T114 "
                              "(L1-A12, `journal --last`) builds it")
    statements = make(path, None)
    assert len(statements) == len(LAST_READS), statements
    return statements


@pytest.fixture()
def imported_clone(pg_cluster):
    """One clone of `tmpl_imported` (T227), with section 1.4's two
    database-level statements, dropped `WITH (FORCE)` at the end (N2's
    `clones`)."""
    found = pg_cluster.psql(f"SELECT datname FROM pg_database WHERE datname = '{IMPORTED}';").stdout.split()
    assert found == [IMPORTED], f"no {IMPORTED} on the session cluster: lane 2's T227 builds it"
    name = f"t226_last_{uuid.uuid4().hex[:8]}"
    pg_cluster.psql(f"CREATE DATABASE {name} TEMPLATE {IMPORTED};")
    try:
        pg_cluster.psql(f"REVOKE ALL ON DATABASE {name} FROM PUBLIC;\n"
                        f"GRANT CONNECT ON DATABASE {name} TO {CONNECT_TO};\n")
        yield Database(pg_cluster, name)
    finally:
        pg_cluster.drop_database(name)


def imported_to_primary(db) -> int:
    """The clone's import brought to `primary` by AT-LR006's route: a
    `cutover` entry writing D21's five `lanes/STORE` fields over the import,
    then `record_marker`, as T210's `import_to_primary` does. Returns the
    cutover's seq."""
    switch = rows(db, "SELECT mode, marker_state FROM register_switch")[0]
    assert (switch["mode"], switch["marker_state"]) == ("files", "absent"), switch
    last = rows(db, "SELECT seq, git_commit, git_tree FROM journal WHERE kind = 'import' "
                    "ORDER BY seq DESC LIMIT 1")
    assert last and last[0]["seq"] == head(db), f"{IMPORTED}'s head is not its import"
    imp = last[0]
    store = "".join(f"{line}\n" for line in (
        "store=primary", "database=t226", f"import={imp['git_commit']}",
        f"lanes-tree={imp['git_tree']}", f"utc={STORE_UTC}")).encode("utf-8")
    edits, files = _creates({STORE_PATH: store})
    cut = _commit_call(db, imp["seq"], _entry("cutover", "cutover", edits=edits, files=files))
    version = rows(db, "SELECT version FROM schema_version")[0]["version"]
    marker = sql(db, f"SELECT {SCHEMA}.record_marker({version}, {cut}, '{MARKER_COMMIT}', "
                     f"'{WS}');", WRITER)
    assert marker.splitlines()[-1] == "present", f"record_marker answered {marker!r}"
    return cut


def lane_logs(db) -> list:
    return [r["path"] for r in rows(
        db, "SELECT path FROM files WHERE path LIKE 'lanes/log/%' AND path <> 'lanes/log/README.md' "
            "ORDER BY path")]


def largest_log(db) -> str:
    """The register's longest lane log, by its lines."""
    found = rows(db, "SELECT f.path, count(d.line_id) AS n FROM files f LEFT JOIN doc_lines d "
                     "ON d.path = f.path WHERE f.path LIKE 'lanes/log/%' AND f.path <> "
                     "'lanes/log/README.md' GROUP BY f.path ORDER BY n DESC, f.path LIMIT 1")
    assert found, f"{IMPORTED} holds no lane log"
    return found[0]["path"]


def journal_size(db) -> dict:
    return rows(db, "SELECT (SELECT count(*) FROM journal) AS entries, "
                    "(SELECT count(*) FROM journal_edits) AS edits")[0]


def explained(db, statements: list) -> list:
    """Each statement under `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, as
    the reader's login, in one REPEATABLE READ READ ONLY transaction with the
    schema on `search_path`, as `_query_many` reads (lane 1's
    `lanes-index:2227-2262` at T114): each plan's server time, buffers and
    rows. No D9 bound is set here, so a statement past 3000 ms is measured,
    and the timed `journal --last` below meets the bound itself."""
    script = [f'SET search_path TO "{SCHEMA}";', "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;"]
    script += [f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {statement};" for statement in statements]
    script.append("COMMIT;")
    proc = subprocess.run([db.psql_bin, "--no-psqlrc", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
                          input="\n".join(script) + "\n", capture_output=True, encoding="utf-8",
                          errors="replace", env=db.env(LOGIN_READER, appname="t226-explain"),
                          timeout=600, check=False)
    assert proc.returncode == 0, f"EXPLAIN as {LOGIN_READER}: {proc.stderr.strip()[-800:]}"
    plans, text, at, decoder = [], proc.stdout, 0, json.JSONDecoder()
    while True:
        while at < len(text) and text[at].isspace():
            at += 1
        if at >= len(text):
            break
        value, at = decoder.raw_decode(text, at)
        plans.append(value[0])
    assert len(plans) == len(statements), f"{len(plans)} plans for {len(statements)} statements"
    return [{"execution_ms": p["Execution Time"], "planning_ms": p["Planning Time"],
             "hit": p["Plan"].get("Shared Hit Blocks", 0), "read": p["Plan"].get("Shared Read Blocks", 0),
             "rows": p["Plan"].get("Actual Rows")} for p in plans]


def grow_to(db, target_edits: int, logs: list, batch: int, tag: str) -> int:
    """Writes of `batch` appended lines each, round robin over `logs`, in
    one session, until `journal_edits` holds at least `target_edits` rows.
    No line holds the measured key. Returns the writes made."""
    have, appends, writes, k = journal_size(db)["edits"], Appends(db, logs), [], 0
    while have < target_edits:
        path = logs[k % len(logs)]
        lane = path[len("lanes/log/"):-len(".md")]
        texts = [f"NOTED {EM} lane {lane}, session {SID_A1}@{WS}, 2026-11-10T00:00:00Z, "
                 f"lane:{lane} {EM} t226 growth {tag} {k}.{i}" for i in range(batch)]
        writes.append(appends.statements(appends.entry(lane, path, texts)))
        have += batch
        k += 1
    if writes:
        before = head(db)
        proc = in_one_session(db, writes)
        assert proc.returncode == 0, f"growth write: {proc.stderr.strip()[-800:]}"
        committed_once(db, before, appends.write_ids)
    return len(writes)


@pytest.mark.parametrize("log", ["largest-log", "renamed-log"])
def test_journal_last_is_explained_per_statement_and_timed_against_t_r(pg_engine, imported_clone,
                                                                        tmp_path, log):
    """Lane 3's `--last` cost rows (#165 6755922262; F10-OWED item 35), on a
    clone of `tmpl_imported` brought to `primary`:

      * `[largest-log]`: the register's longest log, with one line holding
        the case's key appended by one write, so the match is that write's
        seq;
      * `[renamed-log]`: the same, then that log renamed whole through
        `register commit`'s `renames.tsv`, so `journal --last` reads the
        new path's rename closure, and the match is the rename's seq (a
        file renamed in counts what it brings, C7 as lane 1's
        `register_pickaxe` reads it).

    At the clone's own size, then with `journal_edits` grown to 2x and 5x
    its rows by writes of appended lines round robin over every lane log:
    each of the five reads' server time by `EXPLAIN (ANALYZE, BUFFERS)`, as
    the reader's login; and `journal --last --path <p> --grep <key>`'s wall
    time, exec to exit, cold once and 20 warm, beside `T_r`. Each run exits
    0 and prints `format=1`, `n=<head>` and `seq=<the match>`. The figures
    are recorded, never asserted; each statement's share of the read row's
    3000 ms is printed beside it, so a statement that nears it is seen
    (lane 3: indexes on `journal_edits (path)` and `(to_path) WHERE op =
    'rename'` go into migration 1, T107)."""
    db = imported_clone
    imported_to_primary(db)
    ensure_logins(db)
    estate = Estate(tmp_path / "estate", {p: SEED[p] for p in ("lanes/repos.tsv", "lanes/log/README.md")})
    copy = flipped(tmp_path)
    (tmp_path / "conf").mkdir()
    conf = primary_config(tmp_path / "conf" / "lanes-index.conf", db.url(LOGIN_WRITER),
                          db.url(LOGIN_READER))
    env = index_env(tmp_path, conf, estate.home)
    target = largest_log(db)
    lane = target[len("lanes/log/"):-len(".md")]
    key = f"t226-last-key-{uuid.uuid4().hex[:12]}"
    appends = Appends(db, [target])
    proc = one_call(db, appends.statements(appends.entry(lane, target, [
        f"NOTED {EM} lane {lane}, session {SID_A1}@{WS}, 2026-11-10T00:00:00Z, lane:{lane} {EM} {key}"])))
    assert proc.returncode == 0, proc.stderr
    match, measured = int(proc.stdout.strip()), target
    if log == "renamed-log":
        measured = f"lanes/log/{lane}-t226-renamed.md"
        done = fake_write(copy, env, estate.checkout, tmp_path / "rename", lane, "rename-lane",
                          _edit_rename_log(target, measured),
                          f"lanes-edit.sh rename-lane: t226 renames {target}")
        assert done["code"] == 0, (done["snapshot"].stderr, done["commit"] and done["commit"].stderr)
        match = int(done["commit"].stdout.split()[1])
        assert rows(db, f"SELECT count(*) AS n FROM journal_edits WHERE seq = {match} AND op = "
                        f"'rename' AND path = '{target}' AND to_path = '{measured}'")[0]["n"] == 1
    statements = last_statements(measured)
    base = journal_size(db)["edits"]
    batch = max(1, base // 1000)
    lines = []
    for size, factor in (("1x", 1), ("2x", 2), ("5x", 5)):
        if factor > 1:
            grow_to(db, factor * base, lane_logs(db), batch, f"{log}-{size}")
        grown = journal_size(db)
        where = (f"tmpl_imported clone, {size}: {grown['entries']} entries, {grown['edits']} "
                 f"edits, Unix socket")
        for what, plan in zip(LAST_READS, explained(db, statements)):
            lines.append(f"| --last | {platform.node()}, {where} | {log} `{measured}`: {what} | "
                         f"server {plan['execution_ms']:.2f} ms, planning {plan['planning_ms']:.2f} ms "
                         f"| buffers hit {plan['hit']}, read {plan['read']}; rows {plan['rows']} | "
                         f"{100 * plan['execution_ms'] / READ_STATEMENT_MS:.1f} % of "
                         f"{READ_STATEMENT_MS} ms |")
        n, times = head(db), []
        for _ in range(1 + N_WARM):
            ms, proc = timed(lambda: run_index(copy, ["journal", "--last", "--path", measured,
                                                      "--grep", key], env))
            assert proc.returncode == 0, f"journal --last exited {proc.returncode}: {proc.stderr}"
            assert proc.stdout.splitlines() == ["format=1", f"n={n}", f"seq={match}"], proc.stdout
            times.append(ms)
        lines.append(figure("--last", where, f"{log} `journal --last`, exec to exit", times,
                            f"rtt=0, tls=none, c=1, q=1; T_r={T_R_S} s (CLI412:255)"))
    record(lines)


# ------------------------------------------------------------------ `swapped`
CANDIDATES = [f"repoC-{k}" for k in range(1, 7)]

#: The wrapper that stands where `lanes-edit.sh` finds `lanes-index`,
#: beside it (the copy rule, CLI4.5 section 6): it logs each call's argv and
#: hands it to the flipped copy, so each `journal --last` is counted.
CALL_LOG_WRAPPER = r'''#!/usr/bin/env python3
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "lanes-index.calls"), "a", encoding="utf-8") as handle:
    handle.write("\t".join(sys.argv[1:]) + "\n")
real = os.path.join(here, "lanes-index.real")
os.execv(sys.executable, [sys.executable, real] + sys.argv[1:])
'''


def _sid(k: int) -> str:
    return f"cccccccc-{k:04d}-4000-8000-{k:012d}"


def _candidate_log(lane: str, k: int) -> str:
    return "\n".join([
        f"# lane {lane} {EM} object log (lane-collision-protocol Amendment 7)",
        f"STARTED {EM} lane {lane}, session {_sid(k)}@{WS}, 2026-10-02T00:00:00Z, "
        f"lane:{lane} {ARROW} home opensoft/repoC; dir /work/{lane}", ""])


def _paused(lane: str, k: int) -> str:
    """A swap's PAUSED line, its payload after the arrow that follows the
    object (Amendment 7's grammar: object, then the arrow and the payload,
    then the em dash and the free text), which `swapped_candidates` reads as
    the line's payload: `swap; window ...; workstation ...; dir ...; profile
    ...; agent ...; transcript ...`. After the em dash it is free text, which
    `swapped` does not read."""
    return (f"PAUSED {EM} lane {lane}, session {_sid(k)}@{WS}, 2026-11-10T0{k}:00:00Z, "
            f"lane:{lane} {ARROW} swap; window w{k}; workstation {WS}; dir /work/{lane}; "
            f"profile p{k}; agent a{k}; transcript t{k}")


def test_swapped_with_several_candidates_is_timed_beside_its_journal_last_calls(pg_engine, pg, tmp_path):
    """Lane 3's third `--last` row (#165 6755922262): `lanes-edit.sh swapped
    <ws>` with one, three and six swapped lanes, exec to exit, cold once and
    ten warm, in files mode (one `git log -S` pickaxe per candidate,
    `swapped_lanes` at the base) and on primary (one `journal --last` per
    candidate, T506). Each candidate's PAUSED line is one write, committed in
    the register and pushed to the estate's origin in the same order, so
    both modes rank alike.

    The oracle: every run exits 0 and lists the candidates most recently
    paused first, the same in both modes; on primary, each run makes exactly
    one `journal --last` call per candidate, naming its log. That last
    assertion is red until lane 5's T506 (L5-A5) reads `swapped`'s rank
    through `journal --last`."""
    files = dict(SEED)
    for k, lane in enumerate(CANDIDATES, 1):
        files[f"lanes/log/{lane}.md"] = _candidate_log(lane, k)
    reg = PrimaryRegister(pg, tmp_path, files)
    bin_dir = reg.copy.parent
    os.replace(str(reg.copy), str(bin_dir / "lanes-index.real"))
    wrapper = bin_dir / "lanes-index"
    wrapper.write_text(CALL_LOG_WRAPPER, encoding="utf-8")
    wrapper.chmod(0o755)
    calls = bin_dir / "lanes-index.calls"
    checkout = reg.estate.checkout
    base_env = {k: v for k, v in reg.env.items() if k != "LANES_INDEX_CONFIG"}
    base_env.update(LANES_REPO=str(checkout), LANES_BRANCH="main", LANES_WORKSTATION=WS)
    modes = {"files": base_env, "primary": dict(base_env, LANES_INDEX_CONFIG=reg.env["LANES_INDEX_CONFIG"])}
    lines, paused = [], 0
    for count in (1, 3, 6):
        while paused < count:
            lane = CANDIDATES[paused]
            path = f"lanes/log/{lane}.md"
            text = _paused(lane, paused + 1)
            appends = Appends(pg, [path])
            proc = one_call(pg, appends.statements(appends.entry(lane, path, [text])))
            assert proc.returncode == 0, proc.stderr
            target = checkout / path
            target.write_bytes(target.read_bytes() + text.encode("utf-8") + b"\n")
            git(checkout, "commit", "-q", "-am", f"{lane}: PAUSED", env=reg.estate.env)
            git(checkout, "push", "-q", "origin", "main", env=reg.estate.env)
            paused += 1
        expected = list(reversed(CANDIDATES[:count]))
        for mode, env in modes.items():
            times = []
            for _ in range(11):
                calls.write_text("", encoding="utf-8")
                ms, proc = timed(lambda: subprocess.run(
                    ["bash", str(bin_dir / "lanes-edit.sh"), "swapped", WS], capture_output=True,
                    encoding="utf-8", errors="replace", env=env, cwd=str(checkout), timeout=120,
                    check=False))
                assert proc.returncode == 0, f"swapped in {mode} mode: {proc.stderr}"
                listed = [line.split("\t", 1)[0] for line in proc.stdout.splitlines() if line]
                assert listed == expected, f"{mode} mode listed {listed}, not {expected}"
                if mode == "primary":
                    lasts = [c.split("\t") for c in calls.read_text(encoding="utf-8").splitlines()
                             if c.startswith("journal\t--last")]
                    paths = sorted(c[c.index("--path") + 1] for c in lasts)
                    assert paths == sorted(f"lanes/log/{lane}.md" for lane in expected), (
                        f"swapped on primary made {len(lasts)} `journal --last` call(s), not one "
                        f"per candidate: lane 5's T506 (L5-A5) reads the rank through it")
                times.append(ms)
            lines.append(figure("--last", f"{mode} mode, {count} candidate(s), local bare origin",
                                f"`lanes-edit.sh swapped {WS}`, exec to exit", times,
                                f"rtt=0, tls=none; {count} pickaxe(s)"))
    record(lines)


# ============================================================ T255: test 9's phase-W measurements

#: M7's verbs (section 5.1), each as `lanes-edit.sh` (or `lane-start`) takes
#: it, with `{k}` for the run's number so no two runs collide, and the
#: register writes each makes. The argv are read from `lanes-edit.sh`'s usage
#: at the base; "a landing's five writes" is lane 2's reading of Rule 6's
#: landing (the take, its log line, the close, its log line, the release),
#: for lane 4 to confirm against its [L4-c] section. A landing's object is
#: an `owner/repo#<n>` key, one of the forms `lanes-edit.sh`'s `canon_object`
#: takes (`owner/repo#<n>`, `#<n>`, `lane:<name>` and the OpenSpec form),
#: which has no `pr:` form. `{dir}` is the estate's checkout: SEED's log
#: records `dir /work/repoA1`, which exists on no host, so the dry run names
#: a directory that exists with `--dir`, and it runs in a tmux window of its
#: own, `_window`'s, since `lane-start` refuses outside tmux.
VERBS = {
    "log-noted": ([["log", "NOTED", "lane:repoA-1", "t255 measured note {k}"]], 1),
    "claim": ([["claim", "opensoft/repoA#{k}", "--no-github"]], 1),
    "landing": ([
        ["append-line", f"LANDING {EM} lane repoA-1, session {SID_A1}@{WS}, {{utc}}, PR #{{k}} into "
                        f"opensoft/repoA main"],
        ["log", "LANDING", "opensoft/repoA#{k}", "t255 landing {k}"],
        ["append-line", f"LANDED {EM} lane repoA-1, session {SID_A1}@{WS}, {{utc}}, PR #{{k}} into "
                        f"opensoft/repoA main {ARROW} abc1234"],
        ["log", "CLOSED", "opensoft/repoA#{k}", "merged abc1234"],
        ["release", "opensoft/repoA#{k}", "landed", "--no-github"]], 5),
    "lane-start-dry-run": ([["@lane-start", "--dry-run", "--dir", "{dir}", "repoA", "1"]], 0),
}
MODES = ("files", "primary")


class VerbEstate:
    """The estate a verb runs in, in one mode: T210's estate at C, with the
    workspace `lanes-edit.sh workspace-root` answers (`$HOME/.agents/
    workspace.yaml`, W4a's form) and the lane's identity; on primary the
    register brought to `primary` and `LANES_INDEX_CONFIG`, in files mode
    the twin on its own local bare origin (AT-9's fixture: the files-mode
    figure is a lower bound of today's cost)."""

    def __init__(self, db, root: Path, mode: str, reg=None, files: dict = None):
        self.mode, self.db = mode, db
        if mode == "primary":
            self.reg = reg or PrimaryRegister(db, root, files)
            self.estate, self.bin = self.reg.estate, self.reg.copy.parent
            if (REPO / "lane-start").exists():
                shutil.copy2(str(REPO / "lane-start"), str(self.bin / "lane-start"))
            env = dict(self.reg.env)
        else:
            self.reg, self.estate = None, Estate(root / "estate", files)
            self.bin = root / "bin"
            self.bin.mkdir(parents=True)
            for name in ("lanes-edit.sh", "lanes-index", "lane-start"):
                if (REPO / name).exists():
                    shutil.copy2(str(REPO / name), str(self.bin / name))
            env = index_env(root, root / "no-config", self.estate.home)
            env.pop("LANES_INDEX_CONFIG")
        (self.estate.home / ".agents").mkdir(parents=True, exist_ok=True)
        (self.estate.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.estate.origin}\npath: {self.estate.checkout}\n", encoding="utf-8")
        env.update(LANES_REPO=str(self.estate.checkout), LANES_BRANCH="main", LANES_WORKSTATION=WS,
                   LANES_NO_GITHUB="1", LANES_LANE="repoA-1", LANES_SESSION=SID_A1)
        self.env = env
        # EACH WRITE LANE'S OWN REGISTER CHECKOUT, `<c>`: on primary a write runs
        # from `<W>-lanes/<lane>` (`lane_checkout_path`), W being the real path of
        # `workspace.yaml`'s `path:`, and refuses 2 where it is not there, since a
        # clone is a fetch (T415's `pw_checkout`, `23bbd25f:lanes-edit.sh:7934-7936`).
        # The estate makes it itself, because `lane-start` makes it only under
        # `LANES_ROUTE_WRITES=1` with neither `LANES_REPO` nor `LANES_FILE` set
        # (lane 3, #165 6841265575; `dfc4ce4c:lane-start:1209-1210`): a clone of
        # W's origin, as the writes module's `make_lane_checkout` makes one, for
        # `repoA-1`, every verb's lane, and `BIND_TO`, the bind's. It is made once
        # per W, since `[m7]` and `[m9]` build their estates on one register.
        if mode == "primary":
            real = Path(os.path.realpath(self.estate.checkout))
            for lane in ("repoA-1", BIND_TO):
                target = real.parent / f"{real.name}-lanes" / lane
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    git(target.parent, "clone", "-q", str(self.estate.origin), str(target),
                        env=self.estate.env)

    def run(self, argv: list) -> subprocess.CompletedProcess:
        if argv[0].startswith("@"):
            command = ["bash", str(self.bin / argv[0][1:]), *argv[1:]]
        else:
            command = ["bash", str(self.bin / "lanes-edit.sh"), *argv]
        return subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace",
                              env=self.env, cwd=str(self.estate.checkout), timeout=300,
                              stdin=subprocess.DEVNULL, check=False)

    def origin_commits(self) -> int:
        return int(git(self.estate.origin, "rev-list", "--count", "main", env=self.estate.env).strip())


def _window(estate: VerbEstate, root: Path, lane: str, session_id: str = None):
    """The tmux window `lane-start` runs in, named `lane`, with a live session
    in it (T203c's `guard_session`, imported here so the module still loads
    where T203c is not in the tree). `lane-start` refuses outside tmux (its
    step 2: "run this inside the tmux window that will carry the lane"), and
    `--bind` takes only the transcript uuid of the session live in its
    window. So a run gets the stand-in `tmux` in `<root>/window`, answering
    as the window `lane`, and a live session record under the estate's
    `HOME` whose `sessionId` is `session_id` (a new uuid where None); the
    estate's environment then carries that window's `TMUX`, `TMUX_PANE` and
    the stand-in first on `PATH`, no inherited `CLAUDE_*` (a person's
    `CLAUDE_CONFIG_DIR` would move the records), and `CLAUDE_CODE_SESSION_ID`
    naming the session, as the harness exports it. The record's `cwd`,
    `<HOME>/projects/repoA`, is the helper's rule; `lane-start` does not read
    it. The caller closes the session."""
    try:
        from sql_register_helpers import guard_session
    except ImportError:
        pytest.fail("tests/sql_register_helpers.py has no `guard_session`: T203c provides it",
                    pytrace=False)
    home = estate.estate.home
    session = guard_session(home, root / "window", home / "projects" / "repoA", window=lane,
                            session_id=session_id)
    base = {k: v for k, v in estate.env.items() if not k.startswith("CLAUDE_")}
    estate.env = session.env(base, CLAUDE_CODE_SESSION_ID=session.session_id)
    return session


@pytest.mark.parametrize("verb", list(VERBS))
def test_each_verb_is_timed_end_to_end_in_both_modes(pg_engine, pg, tmp_path, verb, request):
    """M7 (section 5.1; P5, what a lane feels): the verb, exec to exit, cold
    once and 20 warm, in files mode against a local bare origin and on
    primary, on the same host. The oracle: every run exits 0; on primary the
    journal grows by exactly the verb's writes per run and each `write_id`
    appears once; in files mode the origin's `main` grows by them. The
    figures are recorded, never asserted. Fails until lane 4's L4-B3 and
    L4-B8 route the verbs through the storage layer on primary."""
    steps, writes = VERBS[verb]
    lines = []
    for mode in MODES:
        estate = VerbEstate(pg, tmp_path / mode, mode)
        if any(step[0] == "@lane-start" for step in steps):
            request.addfinalizer(_window(estate, tmp_path / mode, "repoA-1").close)
        before = head(pg) if mode == "primary" else estate.origin_commits()
        times = []
        for k in range(1 + N_WARM):
            utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            argvs = [[part.format(k=1000 + k, utc=utc, dir=estate.estate.checkout) for part in step]
                     for step in steps]
            start = time.monotonic_ns()
            for argv in argvs:
                proc = estate.run(argv)
                assert proc.returncode == 0, (f"{verb} in {mode} mode, run {k}: `{' '.join(argv)}` "
                                              f"exited {proc.returncode}: {(proc.stdout + proc.stderr)[-600:]}")
            times.append((time.monotonic_ns() - start) / 1e6)
        runs = 1 + N_WARM
        if mode == "primary":
            assert head(pg) == before + runs * writes, (
                f"{verb} on primary: the journal grew by {head(pg) - before}, not {runs * writes}")
            grown = rows(pg, f"SELECT count(*) AS n, count(DISTINCT write_id) AS d FROM journal "
                             f"WHERE seq > {before}")[0]
            assert grown == {"n": runs * writes, "d": runs * writes}, grown
        elif writes:
            assert estate.origin_commits() >= before + runs * writes, (
                f"{verb} in files mode pushed {estate.origin_commits() - before} commit(s)")
        link = ("rtt=0, tls=none, local bare origin" if mode == "files"
                else f"rtt=0, tls=none, {writes} write(s) per run")
        lines.append(figure("M7", f"{mode} mode", f"`{verb}`, exec to exit", times, link))
    record(lines)


# ------------------------------------------------------------------ M13
def _counted(log: Path, offset: int) -> tuple:
    """The counting cluster's log lines after `offset`: (connections,
    Query messages), from `log_connections`' "connection authorized" lines
    and `log_statement=all`'s "statement:" lines, one per simple Query."""
    text = log.read_bytes()[offset:].decode("utf-8", "replace")
    return (len(re.findall(r"connection authorized", text)),
            len(re.findall(r"LOG:  statement: ", text)))


def _path_m1(reg, root: Path):
    done = fake_write(reg.copy, reg.env, reg.estate.checkout, root / "m1", "repoA-1", "log",
                      _edit_log_noted("repoA-1", SID_A1, "t255 m1"), "lanes-edit.sh log: t255 m1")
    assert done["code"] == 0, (done["snapshot"].stderr, done["commit"] and done["commit"].stderr)


def _path_m2(reg, root: Path):
    log = "lanes/log/repoA-1.md"
    appends = Appends(reg.pg, [log])
    text = f"NOTED {EM} lane repoA-1, session {SID_A1}@{WS}, 2026-11-10T00:00:00Z, lane:repoA-1 {EM} t255 m2"
    proc = in_one_session(reg.pg, [appends.statements(appends.entry("repoA-1", log, [text]))])
    assert proc.returncode == 0, proc.stderr


def _path_m6(reg, root: Path):
    proc = run_index(reg.copy, ["render", "--images", "--at", head(reg.pg), "--out", root / "m6"], reg.env)
    assert proc.returncode == 0, proc.stderr


def _path_m7(reg, root: Path):
    proc = VerbEstate(reg.pg, root, "primary", reg).run(["log", "NOTED", "lane:repoA-1", "t255 m7"])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _path_m9(reg, root: Path):
    """M9's path: answer 2's bind, `lane-start --no-launch --bind <uuid>
    repoA 2`, then the guard's `set-row-state` on the lane it leaves (section
    5.1), as `_bind_run` runs them: the body's argv (`_bind_argv`), from
    SID_BIND's live session in a window named `BIND_TO` (`_window`). The
    case builds `[m9]`'s register with `_bind_seed`, so the lane's log
    records a `dir` that exists."""
    estate = VerbEstate(reg.pg, root, "primary", reg)
    estate.env.update(LANES_BIND_BOUND_S=str(BOUND_S), LANES_SESSION=SID_BIND)
    session = _window(estate, root, BIND_TO, SID_BIND)
    try:
        for argv in (_bind_argv(), ["set-row-state", "repoA-1", f"PAUSED {DOT} t255 m9"]):
            proc = estate.run(argv)
            assert proc.returncode == 0, f"`{' '.join(argv)}`: {(proc.stdout + proc.stderr)[-600:]}"
    finally:
        session.close()


@contextlib.contextmanager
def hook_pid():
    """THE HOOK'S `$$`, FOR A GUARD READ'S `--pid` (contract section 3.6:
    "`--pid <pid>` ... is the hook's own pid, `$$`, in forms 2 and 4", and
    "the client reads `T0` from it"). It yields the pid of a stand-in for the
    hook, a `sleep` started just before the read, as a hook's own start is,
    and stops it after the read. T507 cuts a guard read at `T0` + 3.75 s
    from that start, and an age at or above the cut exits 2, "too late to
    verify" (section 3.6's 2; `register_guard_t0`). The pytest process's own
    pid is minutes old on a runner, so with it `[m10]` ended 2 (lane 1's
    round 6b census, #165 6827592167, item 2). `[m10]` and `[m5]` each take
    one. The stand-in is AT-F7's, `test_sql_register_outage.py`'s
    `_stand_in`, at an age of 0."""
    standin = subprocess.Popen(["sleep", "120"], start_new_session=True,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    try:
        yield str(standin.pid)
    finally:
        standin.kill()
        standin.wait()


def _path_m10(reg, root: Path):
    """M10's part 4 on primary: the guard's register read through the
    direct read, the service down: form 2, the guard's prefetch,
    `register read --for guard --prefetch --cache <file> --pid <pid> --repo
    <dir> [--lane=<window>]` (CLI412:661; lane 1's T113, called by T507's
    `guard_run`). Its `--pid` is a stand-in started just before the read
    (`hook_pid`), as the hook's `$$` is, so T507's cut at `T0 + 3.75 s` runs
    from the read's own start. The cache file's directory is made first: the
    read writes the file's family beside it and makes no directory."""
    (root / "m10").mkdir(parents=True, exist_ok=True)
    with hook_pid() as pid:
        proc = run_index(reg.copy, ["register", "read", "--for", "guard", "--prefetch", "--cache",
                                    root / "m10" / "cache", "--pid", pid, "--repo",
                                    reg.estate.checkout, "--lane=repoA-1"], reg.env)
    assert proc.returncode == 0, proc.stderr


#: `[m5]`'S STATE HOME: SHORT, AND OUTSIDE THE TEMPORARY ROOT. The service's
#: one socket is `${XDG_STATE_HOME}/openRepoTools/run/register.sock` (lane 5's
#: socket contract d8, section 2.1): `serve` binds it, and the client
#: connects to it. `sun_path` holds 107 bytes on Linux and 103 on macOS, and
#: the contract's `serve` refuses a path over 103 bytes (`path-too-long`,
#: exit 2). Under `tmp_path` the path followed the temporary root, about 147
#: bytes on the runner, where lane 1's guard rerun met `OSError: AF_UNIX path
#: too long` (verify-r5-c2b, CI run 43140203269; line AN14). So `[m5]`'s
#: `XDG_STATE_HOME` is a `mkdtemp` of its own in `/tmp`, as line G's estates
#: make theirs (T213i): `/tmp/l2m-` and mkdtemp's 8 characters, 17 bytes,
#: which puts the socket at 49 whatever `TMPDIR` or `--basetemp` is. The case
#: removes it when it ends.
STATE_PARENT = "/tmp"
STATE_PREFIX = "l2m-"
#: The contract's bound on the socket's path, in bytes (section 2.1).
SOCKET_MAX = 103
#: The guard's line for a read the service did not answer (`7893339:lanes-index:7499`),
#: and how long `[m5]` warms the service before the read it asserts on, as the
#: guard module's `_warm` does (`afc5b2b4:tests/test_sql_register_guard.py:3198`,
#: `:3480`).
FALLBACK = "guard: direct (service unavailable)"
WARM_S = 15.0


def _path_m5(reg, root: Path):
    """M13's `[m5]`, T237's (R1's M1): the guard's register read through the
    service. `lanes-index serve` starts on the reader's configuration at the
    one socket path lane 5's socket contract d8 fixes,
    `${XDG_STATE_HOME}/openRepoTools/run/register.sock` (its section 2.1),
    under a short state home of the case's own (`STATE_PREFIX`); then form 2,
    the guard's prefetch, with the service up, so the counting cluster logs
    the service's connection and its one Query per request (section 5.6).
    Its `--pid` is a stand-in started just before the read, once the socket
    is bound (`hook_pid`), as `[m10]`'s is, so T507's cut at `T0 + 3.75 s`
    runs from the read's own start, never from the pytest process's or the
    service's. The cache file's directory is made first, as `[m10]`'s is.

    THE SERVICE IS WARMED FIRST, by reads of the same form until one is
    answered by the service, with no fallback line, for `WARM_S` at most,
    as the guard module's `_warm` warms it
    (`afc5b2b4:tests/test_sql_register_guard.py:3483-3496`; lane 2's RV23,
    SHOULD 3). One read was not enough: the service answers `unavailable`
    while its child is `down` or `connecting` and while a background
    whole-file fetch holds it (`7893339:lanes-index:8786-8790`; d8:502),
    and a cache miss answers so and starts that fetch (`:8627-8632`), so a
    second read could still meet a cold service. The read the case asserts
    on is the one after, M5's "with the service warm" (TP:7797). Each
    warming read has its own stand-in pid and its own cache file, so the
    asserted read is the one this case made before, and a warming read's
    end is asserted only by its fallback line: it may fall back to the
    direct read. The counts this path adds therefore hold the service's
    connection, each warming read's, their direct reads' where they fell
    back, and the asserted read's (lane 3's round 6h reading, #165
    6859307928).
    Fails until L5-S1 (lane 5's T512) and T229."""
    state = Path(tempfile.mkdtemp(prefix=STATE_PREFIX, dir=STATE_PARENT))
    try:
        sock = state / "openRepoTools" / "run" / "register.sock"
        assert len(os.fsencode(str(sock))) <= SOCKET_MAX, \
            f"the service's socket path {sock} is over {SOCKET_MAX} bytes"
        env = dict(reg.env, XDG_STATE_HOME=str(state))
        (root / "m5").mkdir(parents=True, exist_ok=True)
        serve = subprocess.Popen([sys.executable, str(reg.copy), "serve"], env=env,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            end = time.monotonic() + 10
            while not sock.exists() and time.monotonic() < end and serve.poll() is None:
                time.sleep(0.05)
            assert sock.exists(), f"lanes-index serve bound no socket at {sock}: {serve.poll()}"

            def read(name: str) -> subprocess.CompletedProcess:
                with hook_pid() as pid:
                    return run_index(reg.copy, ["register", "read", "--for", "guard", "--prefetch",
                                                "--cache", root / "m5" / name, "--pid", pid, "--repo",
                                                reg.estate.checkout, "--lane=repoA-1"], env)

            end, warmed = time.monotonic() + WARM_S, 0
            while True:
                warmed += 1
                warm = read(f"warm-{warmed}")
                if FALLBACK not in warm.stderr:
                    break
                assert time.monotonic() < end, \
                    (f"no warming read was answered by the service in {WARM_S:.0f} s ({warmed} reads)",
                     warm.returncode, warm.stderr)
                time.sleep(0.2)
            proc = read("cache")
            assert proc.returncode == 0, (proc.stderr, f"the last of {warmed} warming reads: {warm.returncode}",
                                          warm.stderr)
            assert FALLBACK not in proc.stderr, \
                (proc.stderr, f"the last of {warmed} warming reads: {warm.returncode}", warm.stderr)
        finally:
            serve.terminate()
            try:
                serve.wait(10)
            except subprocess.TimeoutExpired:
                serve.kill()
    finally:
        shutil.rmtree(state, ignore_errors=True)


M13_PATHS = {"m1": _path_m1, "m2": _path_m2, "m5": _path_m5, "m6": _path_m6, "m7": _path_m7,
             "m9": _path_m9, "m10": _path_m10}


@pytest.mark.parametrize("path", list(M13_PATHS))
def test_each_paths_connections_and_queries_are_counted(pg_engine, request, tmp_path, path):
    """M13 (section 5.1; section 5.6): each path run once on T229's counting
    cluster, whose log holds each connection and each Query message; the
    path's connections (c) and Query messages (q) are read from the lines it
    added and recorded, with the path's own oracle (it exits 0). Whether a
    ceiling is asserted per path is open point 24, so none is. T237 writes
    `[m5]` through the service; each `verify:` names its own ids, so
    neither passes with the other's alone (R1's M1)."""
    counting = needs(request, "counting_cluster", "lane 2's T229 (section 5.6's counting cluster)")
    db = Database(counting, counting.new_database())
    try:
        reg = PrimaryRegister(db, tmp_path, _bind_seed(tmp_path / "estate" / "checkout")
                              if path == "m9" else None)
        log = Path(counting.root) / "server.log"
        offset = log.stat().st_size
        M13_PATHS[path](reg, tmp_path)
        c, q = _counted(log, offset)
        assert c >= 1, f"{path} made no connection the counting cluster logged"
        record([f"| M13 | {platform.node()}, counting cluster, Unix socket | `{path}` | "
                f"c={c}, q={q} | n=1 (a count does not vary with load) |"])
    finally:
        counting.drop_database(db.name)


# ------------------------------------------------------------------ the image cache
def test_the_image_cache_check_and_a_miss_are_timed_per_attempt(pg_engine, pg, tmp_path, monkeypatch):
    """Per attempt (AT-9's oracle; lane 4's "[L4-c]", about 3 ms for the
    check and about 10 ms for a miss), through lane 1's T302 API in process
    (#165 6755106847): the snapshot's image-cache check, `image_cache_head()`
    and one `image_cache_get` per path of the head's manifest, each a hit;
    and a miss, `image_cache_get` answering None, then `image_cache_put` of
    the image read from SQL. Cold once, then 20 warm, each in this case's own
    state directory. The oracle: every hit returns bytes that hash to its
    digest and equal `render_file`'s image; a miss's put returns that digest,
    and the next get returns the bytes. AT-4 (g) proves the cache correct;
    this case times it. Fails until T302."""
    reg = PrimaryRegister(pg, tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "cache-state"))
    module = _lanes_index_module()
    for name in ("image_cache_get", "image_cache_put", "image_cache_head", "image_cache_record"):
        assert hasattr(module, name), f"lanes-index has no `{name}`: lane 1's T302 builds it"
    paths = sorted(p for p in reg.estate.render_set())
    images = images_of(pg, paths)
    n = head(pg)
    manifest = {p: module.image_cache_put(images[p]) for p in paths}
    assert manifest == {p: sha256(images[p]) for p in paths}, "put returns each image's digest"
    module.image_cache_record(n, manifest)
    checks, misses = [], []
    for k in range(1 + N_WARM):
        start = time.monotonic_ns()
        found = module.image_cache_head()
        hits = {p: module.image_cache_get(d) for p, d in (found[1] if found else {}).items()}
        checks.append((time.monotonic_ns() - start) / 1e6)
        assert found is not None and found[0] == n, f"the cache's head is {found and found[0]}, not {n}"
        assert hits == images, "each hit is the image render_file gives"
        fresh = f"t255 miss {k} {uuid.uuid4()}\n".encode("utf-8")
        start = time.monotonic_ns()
        assert module.image_cache_get(sha256(fresh)) is None, "a new image is a miss"
        digest = module.image_cache_put(fresh)
        misses.append((time.monotonic_ns() - start) / 1e6)
        assert digest == sha256(fresh) and module.image_cache_get(digest) == fresh
    record([figure("AT-9", "fixture cluster, Unix socket", f"the image cache's check, {len(paths)} paths",
                   checks, "in process, no psql; lane 4: about 3 ms"),
            figure("AT-9", "fixture cluster, Unix socket", "an image-cache miss: get, then put",
                   misses, "in process, no psql; lane 4: about 10 ms")])


# ------------------------------------------------------------------ the delayed relay
#: Section 5.6's shapes as lane 5's netem run times them (#165 6722703424),
#: on T229's TLS cluster: A, a new `psql` per read with one query through
#: `-c`; B1, a held session sending a reader's statements one by one; B2,
#: the same as one Query joined with `\;`. C stays on the bench.
SHAPE_READS = ["SET search_path TO pg_catalog", "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY",
               "SELECT 1", "COMMIT"]
RTTS_MS = (20, 150)


def _held(env: dict, psql: str):
    return subprocess.Popen([psql, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, bufsize=1)


def _ask(session, text: str) -> None:
    """Send `text` on the held session and wait for its marker line."""
    marker = f"t255-{uuid.uuid4().hex[:8]}"
    session.stdin.write(text + f"\n\\echo {marker}\n")
    session.stdin.flush()
    for line in session.stdout:
        if line.strip() == marker:
            return
    raise AssertionError(f"the held session ended: {session.stderr.read()}")


@pytest.mark.parametrize("rtt", RTTS_MS, ids=[str(r) for r in RTTS_MS])
@pytest.mark.parametrize("shape", ["a", "b1", "b2"])
def test_each_shape_on_a_delayed_relay_is_recorded(pg_engine, request, shape, rtt):
    """Section 5.6's option B, which lane 3 ruled for open point 23 (R-P23;
    #165 6741861590): each shape through T229's `delayed_loopback` in front
    of the TLS cluster, `delay_s` = RTT / 2 each way, 30 timed runs after 3
    warm-ups (lane 5's counts), beside the same shape at RTT 0 on the TLS
    cluster itself, so the row gives the network share and the round trips
    it implies (n = (median - median at 0) / RTT). Every run answers. Never
    asserted; the relay models no slow start, loss or kernel timer, so it
    checks n for small messages."""
    tls = needs(request, "tls_cluster", "lane 2's T229 (section 5.6's TLS cluster)")
    relay_of = getattr(pgcluster, "delayed_loopback", None)
    assert relay_of is not None, "tests/pgcluster.py has no delayed_loopback: lane 2's T229 builds it"
    psql = tls.tool("psql")

    def timings(env: dict) -> list:
        times = []
        if shape == "a":
            for _ in range(33):
                ms, proc = timed(lambda: subprocess.run([psql, "-X", "-A", "-t", "-c", "SELECT 1"],
                                                        capture_output=True, text=True, env=env,
                                                        timeout=120, check=False))
                assert (proc.returncode, proc.stdout.strip()) == (0, "1"), proc.stderr
                times.append(ms)
        else:
            session = _held(env, psql)
            try:
                text = ("\n".join(s + ";" for s in SHAPE_READS) if shape == "b1"
                        else " \\; ".join(SHAPE_READS) + ";")
                for _ in range(33):
                    ms, _none = timed(lambda: _ask(session, text))
                    times.append(ms)
            finally:
                session.stdin.close()
                session.wait(timeout=60)
        return times[3:]

    env = tls.client_env()
    local = _stats(timings(env))
    with relay_of(int(env["PGPORT"]), rtt / 2000.0) as relay:
        port = getattr(relay, "port", relay)
        delayed = _stats(timings(dict(env, PGHOST="127.0.0.1", PGPORT=str(port))))
    trips = (delayed["median"] - local["median"]) / rtt
    record([f"| relay | {platform.node()}, TLS cluster behind the delayed loopback | shape {shape.upper()} "
            f"at RTT {rtt} ms | median {delayed['median']:.1f} ms, p95 {delayed['p95']:.1f} ms, "
            f"n={delayed['n']}; at RTT 0 median {local['median']:.1f} ms | about {trips:.1f} round trips |"])


# ============================================================ T254: M9 (phase W)

#: `bound_s` at `c` = 2 with one address, as `guard-bind` computes it from
#: the configuration (section 5.1's M9 rule; lane 4's "The record, and its
#: liveness test"), and the variable tests set it by.
BOUND_S = 500
#: The session that answers 2 and binds, and the lane it leaves.
SID_BIND = "bbbbbbbb-0009-4000-8000-00000000b009"
#: The lane answer 2 binds, whose name the guard gives the window before the
#: bind (`guard_answer`'s rename), and its `lane-start` arguments as the
#: guard's `lane_start_args` prints them.
BIND_TO, BIND_ARGS = "repoA-2", ("repoA", "2")


def _bind_argv() -> list:
    """The body's bind, `lane-start --no-launch --bind "$G_ID" <args>` (B14
    tasks:677; design W:5444; the guard's call in `lanes-edit.sh`): `--bind`
    takes the transcript uuid of the session live in the window, then the
    lane's arguments."""
    return ["@lane-start", "--no-launch", "--bind", SID_BIND, *BIND_ARGS]


def _bind_seed(checkout: Path) -> dict:
    """SEED with `BIND_TO`'s log recording `checkout` as its `dir`, so the
    bind finds a directory that exists where `lane-start` looks for it (its
    rung 3, the lane's log), with the guard's own arguments. SEED's
    `dir /work/repoA2` exists on no host."""
    files = dict(SEED)
    log = f"lanes/log/{BIND_TO}.md"
    assert files[log].count("; dir /work/repoA2\n") == 1, files[log]
    files[log] = files[log].replace("; dir /work/repoA2\n", f"; dir {checkout}\n")
    return files


def _bind_run(db, root: Path, mode: str) -> tuple:
    """One M9 run on a fresh estate with a local bare origin (section 5.3):
    answer 2's bind, `lane-start --no-launch --bind repoA 2`, then the
    guard's `set-row-state` on the lane it leaves, each exec to exit in the
    guard's own path. Returns (the bind's ms, `set-row-state`'s ms, the
    register writes on primary or the origin's new commits in files mode,
    and the head or the commit count before the bind).
    The bind's argv is the body's (`_bind_argv`), run from SID_BIND's live
    session in a window named `BIND_TO` (`_window`), on an estate whose log
    records a `dir` that exists (`_bind_seed`)."""
    estate = VerbEstate(db, root, mode, files=_bind_seed(root / "estate" / "checkout"))
    estate.env.update(LANES_BIND_BOUND_S=str(BOUND_S), LANES_SESSION=SID_BIND,
                      CLAUDE_CODE_SESSION_ID=SID_BIND)
    session = _window(estate, root, BIND_TO, SID_BIND)
    try:
        before = head(db) if mode == "primary" else estate.origin_commits()
        spent = []
        for argv in (_bind_argv(),
                     ["set-row-state", "repoA-1", f"PAUSED {DOT} answer 2 bound this session to repoA-2"]):
            ms, proc = timed(lambda: estate.run(argv))
            assert proc.returncode == 0, (f"{mode}: `{' '.join(argv)}` exited {proc.returncode}: "
                                          f"{(proc.stdout + proc.stderr)[-600:]}")
            spent.append(ms)
    finally:
        session.close()
    grown = (head(db) if mode == "primary" else estate.origin_commits()) - before
    return spent[0], spent[1], grown, before


@pytest.mark.parametrize("mode", list(MODES))
def test_the_bind_and_the_guards_set_row_state_are_timed_in_both_modes(pg_engine, pg, tmp_path, mode):
    """M9 (section 5.1; AT-F6): answer 2's bind and the guard's
    `set-row-state` on the lane it leaves, exec to exit, cold once and 20
    warm, each run on a fresh estate with a local bare origin; recorded
    beside `bound_s` (500 s at `c` = 2), never asserted (ruling 16: the
    detached form applies, so M9 decides nothing). One case per mode, as
    TP:6346 gives them and F12b's T254 text owes them (R-F11-2): `[files]`
    and `[primary]`. Each id records its own two figures, the bind's and
    `set-row-state`'s, and asserts no time.

    The oracle, in each id: every call exits 0; on primary each run's bind
    is one `start-record` write and `set-row-state` one more, so the journal
    grows by exactly two and their write ids are distinct (AT-F6: one
    journal entry for the bind, two for answer 2); in files mode the
    origin's `main` grows by at least those two commits. `[files]` passes
    today, and `[primary]` fails until lane 4's L4-B9 and lane 5's L5-A1 and
    L5-B1 land (tasks:2412; lane 3, #165 6808937880, batch e L2-5)."""
    binds, rows_set = [], []
    for k in range(1 + N_WARM):
        if mode == "primary":
            name = pg.cluster.new_database()
            db = Database(pg.cluster, name)
        else:
            name, db = None, pg
        try:
            bind_ms, set_ms, grown, before = _bind_run(db, tmp_path / f"{mode}-{k}", mode)
            if mode == "primary":
                assert grown == 2, f"run {k}: the journal grew by {grown}, not 2"
                ids = rows(db, f"SELECT count(DISTINCT write_id) AS d FROM journal WHERE seq > {before}")
                assert ids == [{"d": 2}], ids
            else:
                assert grown >= 2, f"run {k}: the origin's main grew by {grown} commit(s)"
        finally:
            if name is not None:
                pg.cluster.drop_database(name)
        binds.append(bind_ms)
        rows_set.append(set_ms)
    link = f"rtt=0, tls=none; bound_s={BOUND_S} (c=2, N_a=1)"
    record([figure("M9", f"{mode} mode, fresh estate, local bare origin",
                   "`lane-start --no-launch --bind`, exec to exit", binds, link),
            figure("M9", f"{mode} mode, fresh estate, local bare origin",
                   "the guard's `set-row-state` on the lane it leaves", rows_set, link)])
