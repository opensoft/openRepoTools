# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 1 (AT-1, L2-N1; opensoft/openRepoTools#165): the mirror
byte-identical to a full render from SQL after a write.

THIS MODULE TODAY holds test 1's phase-N part, lane 2's T210:

  * `test_a_storage_layer_entry_renders_byte_identical_to_a_full_render[<entry>]`
    (N, RE): the storage layer's write entry, called as the projection writer
    will call it, then the pure renderer;
  * `test_the_render_of_one_entry_and_of_a_full_render_is_timed_and_recorded`
    (N, RE; M6): the pure renderer timed, never asserted;
  * `test_sync_source_register_does_nothing_on_primary_and_says_so` (FP, no
    engine);

and the image cache's own cases, lane 2's T210e (B10 tasks:972's
`PENDING-L2`), each named with `image_cache` so that lane 1's T302 selects
them with `-k 'sql_register_render and image_cache'`, with no engine: see
"the image cache (T302's API)" below;

and the render read's one case with `start`, lane 2's T210f (B10 tasks:1003;
lane 1's T301 cache-forward, #165 6767347563): with `start`,
`register_render_read` returns the images, `{path: bytes}`, and not the rows.
No engine, no image cache: see "the render read's `start`" below;

and test 1's phase-W part, lane 2's T240: each verb through `lanes-edit.sh`
on `mode=primary` with the pure renderer writing a scratch mirror, its
files-mode twin, `rename-lane`'s transaction then its move, a caller's UTC
kept, and no register `sync` nudge on primary (see "phase W: T240" below);

and test 1's phase-G part, lane 2's T270's one case here: the mirror read
from the bare origin's `main` after the forked render (see "phase G: T270"
below).

THE STORAGE-LAYER ENTRY (design S4; the delta spec's "The managed seam stays
the ledger's"). The managed projection writer arrives with the 001 feature's
T024; this change provides the entry it will call and tests it with a fake
writer. Its storage layer is `lanes-index`, the one database client (D2), and
one attempt of S1's loop is two calls (contract section 1):

  1. `lanes-index register snapshot --write-id new --lane <l> --verb <v>
     --args-sha256 <h> --tree <attempt>/tree --checkout <c>` (section 3.2),
     which mints the write id and builds the scratch tree at `n`;
  2. the verb's edit in the scratch tree, then the attempt directory, as the
     seam writes it (section 3.3's table: `snapshot`, `changes.tsv`,
     `images/`, `tree/`, `msg`, `author`, `files`, `not_after`);
  3. `lanes-index register commit --write-id <w> --generation <g> --lane <l>
     --verb <v> --args-sha256 <h> --workstation <ws> <attempt>` (section 3.3).

The fake writer, `projection_entry`, does exactly that, and abandons on any
end of the snapshot but 0 (section 3.3, "The caller's map"). Its cases are
the managed projection itself, which rewrites a row's state cell to carry a
managed-owner marker (`lanes-edit.sh`'s ported reader at 3c26041), and two
other entries of S1's writes, a log line and a `LANES.md` take, so that the
renderer is checked on a row, a line of `LANES.md` and a log.

THE REGISTER, "against an import": a files-mode repository at commit C,
holding AT-1's fixture register (three lanes, one archived; aliases; a lane
with `HOLD`, `LANDING` and `LANDED` lines; a log with `WORD` lines whose UTC
carries milliseconds), loaded by AT-LR006's route (the test plan at
4610-4615): as `lanes_register_writer`, `commit_write` with an `import` entry
of C's render set, then a `cutover` entry, then `record_marker`, so the
switch is `primary` with the marker `present`. No `lanes-index import` or
`cutover` runs (those are L1-A13's and group C's).

THE PURE RENDERER is lane 3's T301, as lane 1 built it (#165 6754569755):
`lanes-index render --images --at <k> --out <dir>` (contract section 3.6),
which writes the render set's images at seq `k` from the journal alone. The
full render from SQL is `render_file` (lane 1's T107) of every path in
`files`.

REAL ENGINE. The entry's cases ask for `pg` (`tests/pgcluster.py`), one
database cloned from the template that T227 builds by the bootstrap; on T205's
empty template they fail, since the schema is not there, and without
PostgreSQL 16 they skip with T205's banner. They fail until L1-A6 (T107 and
T108), L1-A9 (T111, `register snapshot`), L1-A10 (T112, `register commit`)
and T301 land. `lanes-index` runs as T203's flipped copy, `RENDER_GIT_HALF =
True`, so `mode=primary` loads (open point 3), and connects as two logins of
this module's own, members of the writer and the reader groups, by the
cluster's trust.

`sync --source register` NEEDS NO ENGINE: on primary it makes no `psql`
call, writes nothing and says it does nothing on primary (L1-A15, lane 1's
T117). It runs with T203's register fake first on `PATH`, whose log, with no
call that carries a request in it, is the oracle for "no `psql` call"; the
fake answers T106's `psql --version` probe itself since T203b.
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
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest

from conftest import REPO, WINDOWS_SKIP
from sql_register_helpers import (LANES_INDEX, PSQL_SHIM, PSQL_SHIM_CONTROL, PSQL_SHIM_LOG,
                                  REGISTER_FAKE_PSQL, RENDER_GIT_HALF_LINE, contract_stub,
                                  flipped_copy)

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280; `tests/sql_register_gate.py` reads it, and
#: T281 removes it in the last set): the tasks each id of this module waits
#: for, by T210's, T240's and T270's Orders (tasks.md at 204145ae), keyed by
#: function. Lane 2's plan GP-24 wrote it (task sets 12b's rule 11).
SQL_REGISTER_GATE_TABLE = {
    "test_a_caller_composed_utc_and_log_paused_utc_stay_as_written": ("T414", "T415", "T416", "T421", "T422"),  # T240; tasks:2313
    "test_a_storage_layer_entry_renders_byte_identical_to_a_full_render": ("T105", "T107", "T108", "T111", "T112", "T227", "T301"),  # T210; tasks:1951
    "test_each_write_leaves_the_mirror_byte_identical_to_a_full_render": ("T414", "T415", "T416", "T421", "T422"),  # T240; tasks:2313
    "test_each_write_matches_its_files_mode_twin_byte_for_byte": ("T414", "T415", "T416", "T421", "T422"),  # T240; tasks:2313
    "test_each_write_reads_back_primary_as_the_mode_that_wrote_it_last": ("T414", "T415", "T416", "T421", "T422"),  # T240; tasks:2313
    "test_on_primary_a_write_does_not_nudge_a_register_sync": ("T414", "T415", "T416", "T421", "T422"),  # T240; tasks:2313
    "test_rename_lane_commits_the_transaction_only_where_its_handoffs_path_has_no_cache_part_on_primary": ("T414", "T415", "T416", "T421", "T422"),  # T240; tasks:2313
    "test_rename_lane_commits_the_transaction_then_a_rerun_makes_only_the_move": ("T414", "T415", "T416", "T421", "T422"),  # T240; tasks:2313
    "test_rename_lane_commits_the_transaction_then_its_move_on_primary_takes_no_bytecode_to_to": ("T414", "T415", "T416", "T421", "T422"),  # T240; tasks:2313
    "test_sync_source_register_does_nothing_on_primary_and_says_so": ("T105", "T107", "T108", "T111", "T112", "T227", "T301"),  # T210; tasks:1951
    "test_the_image_cache_collects_all_but_the_last_three_manifests_past_the_floor": ("T302",),  # T210; tasks:1951
    "test_the_image_cache_follows_no_symlink_at_its_lock_or_its_head": ("T302",),  # T210; tasks:1951
    "test_the_image_cache_puts_and_gets_an_object_only_by_its_digest": ("T302",),  # T210; tasks:1951
    "test_the_image_cache_records_manifests_and_a_head_that_moves_only_forward": ("T302",),  # T210; tasks:1951
    "test_the_image_cache_skips_a_busy_or_odd_lock_and_never_waits": ("T302",),  # T210; tasks:1951
    "test_the_mirror_on_origin_equals_a_full_render_after_each_write": ("T320", "T321", "T322", "T323", "T325", "T415", "T416"),  # T270; tasks:2479
    "test_the_render_of_one_entry_and_of_a_full_render_is_timed_and_recorded": ("T105", "T107", "T108", "T111", "T112", "T227", "T301"),  # T210; tasks:1951
    "test_the_render_read_with_start_returns_the_images_and_a_bad_start_costs_one_full_read": ("T301",),  # T210; tasks:1951
}

LANES_EDIT = REPO / "lanes-edit.sh"

#: The register's schema, `register_schema=`'s default (contract section 2.5).
SCHEMA = "lanes_register"
WRITER, READER = "lanes_register_writer", "lanes_register_reader"
#: The logins `lanes-index` connects as in this module's real-engine cases.
#: Made once per cluster, members of the writer and the reader groups, with
#: no password.
LOGIN_WRITER, LOGIN_READER = "t210_register_writer", "t210_register_reader"

#: What the fake writer stamps: the workstation (`--workstation`, and each
#: line's `session <uuid>@<ws>`), the author, and the operator lane.
WS = "Eagle"
AUTHOR = "T210 fake writer <t210@example.invalid>"
OPERATOR = "repoA-2"
MARKER_COMMIT = "e" * 40
STORE_UTC = "2026-11-09T10:00:00Z"

#: The register's punctuation, spelled by code point so no raw character
#: enters this file: the em dash, the middle dot of a state cell, the arrow
#: of a `LANDED` line.
EM, DOT, ARROW = chr(0x2014), chr(0x00B7), chr(0x2192)

SID_A1 = "aaaaaaaa-0001-4000-8000-00000000a001"
SID_A2 = "aaaaaaaa-0003-4000-8000-00000000a003"
SID_Z1 = "eeeeeeee-0001-4000-8000-00000000e001"
TIP = "0123456789abcdef0123456789abcdef01234567"

#: The render set (Q18 (A); contract section 3.6): `lanes/LANES.md`,
#: `lanes/aliases.tsv`, each `lanes/log/<lane>.md` but the README, and the
#: archive. `lanes/STORE` is the operator entries' alone, never a write's.
RENDER_SET = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|archive/[^/]+\.md"
                        r"|log/(?!README\.md$)[^/]+\.md)$")
STORE_PATH = "lanes/STORE"
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


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
               GIT_AUTHOR_NAME="T210 estate", GIT_AUTHOR_EMAIL="t210@example.invalid",
               GIT_COMMITTER_NAME="T210 estate", GIT_COMMITTER_EMAIL="t210@example.invalid",
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
                          errors="replace", env=db.env(appname="t210"), timeout=120, check=False)


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


def db_clock(db) -> int:
    """The database's clock, floored to whole seconds, as epoch seconds."""
    return rows(db, "SELECT floor(extract(epoch FROM clock_timestamp()))::bigint AS s")[0]["s"]


def full_render(db) -> dict:
    """The full render from SQL: `render_file` (lane 1's T107) of every path
    in `files`, {path: bytes}."""
    return {r["path"]: base64.b64decode(r["b64"]) for r in rows(
        db, "SELECT path, encode(render_file(path), 'base64') AS b64 FROM files ORDER BY path")}


def _lines(data: bytes) -> list:
    text = data.decode("utf-8")
    assert text.endswith("\n"), "every fixture file ends with a newline"
    return text[:-1].split("\n")


def _entry(kind: str, verb: str, journal: dict = None, **parts) -> dict:
    body = {"kind": kind, "verb": verb, "lane": OPERATOR, "workstation": WS, "author": AUTHOR,
            "message": f"t210: {kind}"}
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


def import_to_primary(db, estate: Estate, marker_on_origin: bool = False) -> int:
    """AT-LR006's route (TP:4610-4615) over C: an `import` entry of C's render
    set, a `cutover` entry, then `record_marker`, by the documented functions
    as `lanes_register_writer`. Returns the import's seq.

    `record_marker` records a made-up sha, `MARKER_COMMIT`, and origin stays
    at C, for every estate but part G's: only part G's `PrimaryWrites` sets
    `marker_on_origin` (T270's line, tasks:2477; lane 2, #165 6866688575;
    lane 3, #165 6866808028). There the cutover's marker commit is put on
    origin's `main` before `record_marker`, which records it by its sha
    (`_marker_commit_on_origin`). It cannot come after: `record_marker` runs
    once a cutover, and refuses LR002 once the marker is `present`."""
    edits, files = _creates(estate.render_set())
    imported = _commit_call(db, head(db), _entry(
        "import", "import", {"git_commit": estate.c, "git_tree": estate.lanes_tree},
        edits=edits, files=files))
    store = "".join(f"{line}\n" for line in (
        "store=primary", "database=t210", f"import={estate.c}",
        f"lanes-tree={estate.lanes_tree}", f"utc={STORE_UTC}")).encode("utf-8")
    edits, files = _creates({STORE_PATH: store})
    cut = _commit_call(db, imported, _entry("cutover", "cutover", edits=edits, files=files))
    marker_sha = MARKER_COMMIT
    if marker_on_origin:
        rendered = rows(db, f"SELECT encode(render_file('{STORE_PATH}'), 'base64') AS b64")
        assert base64.b64decode(rendered[0]["b64"]) == store, (
            f"SQL renders {STORE_PATH} otherwise than the cutover entry's bytes")
        marker_sha = _marker_commit_on_origin(estate, store, cut)
    version = rows(db, "SELECT version FROM schema_version")[0]["version"]
    marker = sql(db, f"SELECT {SCHEMA}.record_marker({version}, {cut}, '{marker_sha}', "
                     f"'{WS}');", WRITER)
    assert marker.splitlines()[-1] == "present", f"record_marker answered {marker!r}"
    assert rows(db, "SELECT mode, marker_state FROM register_switch") == \
        [{"mode": "primary", "marker_state": "present"}]
    if marker_on_origin:
        assert rows(db, "SELECT marker_commit FROM register_switch") == \
            [{"marker_commit": marker_sha}], "record_marker did not record the marker commit"
    return imported


def _marker_commit_on_origin(estate: Estate, store: bytes, cut: int) -> str:
    """The cutover's marker commit, put on the bare origin's `main` as a
    cutover's own push puts it (Y:2812-2814), and its sha: C's tree plus
    `STORE_PATH` holding `store`, the cutover entry's bytes, on parent C, with
    `Register-Seq: <cut>` alone in its message's last paragraph. It is made in
    the origin through an index of its own, as RG's `commit_in_origin` makes
    one (`fdab9267:tests/test_sql_register_renderer_git.py:573-586`), and
    `main` moves to it from C, so no clone's refs move; the lane checkouts
    that `PrimaryWrites` clones after this are at it."""
    git_dir = f"--git-dir={estate.origin}"
    env = dict(estate.env, GIT_INDEX_FILE=str(estate.root / "marker.index"))
    blob_file = estate.root / "marker-STORE"
    blob_file.write_bytes(store)
    git(estate.root, git_dir, "read-tree", estate.c, env=env)
    blob = git(estate.root, git_dir, "hash-object", "-w", str(blob_file), env=env).strip()
    git(estate.root, git_dir, "update-index", "--add", "--cacheinfo",
        f"100644,{blob},{STORE_PATH}", env=env)
    tree = git(estate.root, git_dir, "write-tree", env=env).strip()
    commit = git(estate.root, git_dir, "commit-tree", tree, "-p", estate.c,
                 "-m", "t270: the cutover, by AT-LR006's route",
                 "-m", f"Register-Seq: {cut}", env=estate.env).strip()
    git(estate.root, git_dir, "update-ref", "refs/heads/main", commit, estate.c,
        env=estate.env)
    trailer = git(estate.root, git_dir, "log", "-1",
                  "--format=%(trailers:key=Register-Seq,valueonly)", commit,
                  env=estate.env).strip()
    assert trailer == str(cut), f"the marker commit's Register-Seq reads {trailer!r}, not {cut}"
    return commit


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


def epoch_of(utc: str) -> int:
    import calendar
    return calendar.timegm(time.strptime(utc, "%Y-%m-%dT%H:%M:%SZ"))


# ------------------------------------------------------------------ the fake writer
def _edit_managed_projection(tree: Path, utc: str) -> str:
    """S4's projection: repoA-1's row's state cell carries a managed-owner
    marker, in the form `lanes-edit.sh`'s ported reader parses (3c26041's
    T019): `<STATE> . <utc> . managed-owner mode=... daemon=... generation=...
    bound-lane=<lane>`. Returns the new line."""
    path = tree / "lanes" / "LANES.md"
    text = path.read_text(encoding="utf-8")
    old = _row("repoA-1", SID_A1, f"LIVE {DOT} 2026-10-01T01:00:00Z {DOT} working")
    new = _row("repoA-1", SID_A1, f"LIVE {DOT} {utc} {DOT} managed-owner mode=managed "
                                  f"daemon=t210d generation=7 bound-lane=repoA-1")
    assert text.count(old + "\n") == 1, "the fixture row is in the scratch tree once"
    path.write_text(text.replace(old + "\n", new + "\n"), encoding="utf-8")
    return new


def _edit_log_noted(tree: Path, utc: str) -> str:
    """`log NOTED`'s line, appended to repoA-1's log."""
    line = (f"NOTED {EM} lane repoA-1, session {SID_A1}@{WS}, {utc}, lane:repoA-1 {EM} "
            f"test 1's part N")
    path = tree / "lanes" / "log" / "repoA-1.md"
    path.write_bytes(path.read_bytes() + line.encode("utf-8") + b"\n")
    return line


def _edit_append_hold(tree: Path, utc: str) -> str:
    """`append-line`'s take: a `HOLD` on a repository nobody holds."""
    line = (f"HOLD {EM} lane repoA-2 ({WS}), window w, {utc}: opensoft/repoB main {TIP} "
            f"for a check")
    path = tree / "lanes" / "LANES.md"
    path.write_bytes(path.read_bytes() + line.encode("utf-8") + b"\n")
    return line


#: The entries the fake writer drives: {id: (lane, verb, the edit, the path
#: it touches)}. The managed projection is S4's own verb (design S4: "run
#: through S1's attempt loop as the verb `managed-projection`").
ENTRIES = {
    "managed-projection": ("repoA-1", "managed-projection", _edit_managed_projection,
                           "lanes/LANES.md"),
    "log-noted": ("repoA-1", "log", _edit_log_noted, "lanes/log/repoA-1.md"),
    "append-line-hold": ("repoA-2", "append-line", _edit_append_hold, "lanes/LANES.md"),
}


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


def projection_entry(copy: Path, env: dict, checkout: Path, root: Path, entry: str,
                     message: str) -> dict:
    """The storage layer's write entry, driven by a fake writer as the
    projection writer will call it (design S4; contract sections 3.2 and 3.3):
    `register snapshot --write-id new ... --tree <root>/attempt/tree
    --checkout <checkout>`; on 0 alone, the edit, the attempt directory and
    `register commit`. Returns what each call answered, the entry's code
    (the snapshot's where it did not answer 0, else the commit's), the
    attempt directory, the message and the line the edit wrote."""
    lane, verb, edit, _path = ENTRIES[entry]
    args_sha256 = hashlib.sha256(json.dumps([lane, verb, message]).encode("utf-8")).hexdigest()
    attempt = root / "attempt"
    out = {"snapshot": None, "commit": None, "code": None, "attempt": attempt,
           "message": message, "line": None, "fields": {}, "args_sha256": args_sha256}
    # THE ATTEMPT DIRECTORY EXISTS BEFORE THE FIRST SNAPSHOT, as the seam's
    # does (contract section 3.3: its digest, run nonce and attempt "are
    # known before the first snapshot"); `--tree` names an empty `tree/` in it.
    attempt.mkdir(parents=True, exist_ok=True)
    snap = run_index(copy, ["register", "snapshot", "--write-id", "new", "--lane", lane,
                            "--verb", verb, "--args-sha256", args_sha256,
                            "--tree", attempt / "tree", "--checkout", checkout], env)
    out["snapshot"] = snap
    if snap.returncode != 0:
        out["code"] = snap.returncode
        return out
    fields = keys(snap.stdout)
    out["fields"] = fields
    tree = attempt / "tree"
    (attempt / "snapshot").write_text(snap.stdout, encoding="utf-8")
    out["line"] = edit(tree, utc_of(int(fields["clock"])))
    git(tree, "add", "-A", "--", "lanes", env=env)
    changes = []
    for raw in git(tree, "diff", "--cached", "--no-renames", "--raw", "--no-abbrev", "HEAD",
                   env=env).splitlines():
        meta, path = raw.split("\t", 1)
        parts = meta.split()
        changes.append((parts[4], path, parts[2], parts[3]))
    assert changes, "the edit staged a change"
    (attempt / "changes.tsv").write_text(
        "".join(f"{s}\t{p}\t{o}\t{n}\n" for s, p, o, n in changes), encoding="utf-8")
    images = {}
    for status, path, _old, _new in changes:
        if status in ("A", "M"):
            images[path] = (tree / path).read_bytes()
            target = attempt / "images" / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(images[path])
    (attempt / "files").write_text(_canonical_rows(changes, images), encoding="utf-8")
    (attempt / "msg").write_text(message, encoding="utf-8")
    (attempt / "author").write_text(AUTHOR + "\n", encoding="utf-8")
    (attempt / "not_after").write_text(fields["not_after"] + "\n", encoding="utf-8")
    commit = run_index(copy, ["register", "commit", "--write-id", fields["write_id"],
                              "--generation", fields["generation"], "--lane", lane,
                              "--verb", verb, "--args-sha256", args_sha256,
                              "--workstation", WS, attempt], env)
    out["commit"] = commit
    out["code"] = commit.returncode
    return out


def render_images(copy: Path, env: dict, k: int, out_dir: Path) -> tuple:
    """The pure renderer, T301: `render --images --at <k> --out <dir>`
    (contract section 3.6). Returns the call and {path: bytes} of every file
    it wrote under `out_dir`."""
    proc = run_index(copy, ["render", "--images", "--at", k, "--out", out_dir], env)
    written = {}
    if out_dir.is_dir():
        for path in sorted(out_dir.rglob("*")):
            if path.is_file():
                written[path.relative_to(out_dir).as_posix()] = path.read_bytes()
    return proc, written


def _rendered_only(files: dict) -> dict:
    return {p: b for p, b in files.items() if RENDER_SET.match(p)}


class PrimaryRegister:
    """C imported and brought to `primary`, a flipped copy, and the
    configuration that reaches the test's database as this module's logins."""

    def __init__(self, pg, tmp_path: Path):
        self.pg = pg
        self.estate = Estate(tmp_path / "estate")
        self.imported = import_to_primary(pg, self.estate)
        ensure_logins(pg)
        self.copy = flipped(tmp_path)
        (tmp_path / "conf").mkdir()
        conf = primary_config(tmp_path / "conf" / "lanes-index.conf", pg.url(LOGIN_WRITER),
                              pg.url(LOGIN_READER))
        self.env = index_env(tmp_path, conf, self.estate.home)


# ============================================================ part N (real engine)

@pytest.mark.parametrize("entry", list(ENTRIES))
def test_a_storage_layer_entry_renders_byte_identical_to_a_full_render(pg, tmp_path, entry):
    """AT-1's part N: the storage layer's write entry, called as the
    projection writer will call it, commits one entry; then the pure
    renderer's images at that seq equal the full render from SQL, path set
    and bytes, over the four paths, and it writes nothing outside them. The
    journal gains exactly one entry, at the old head plus one, carrying the
    write's message byte for byte and its write id, unique in the journal;
    every row the entry touched reads `primary` as the mode that wrote it
    last; the new line's UTC is the database's, in whole seconds, between the
    clock read before the write and after it. The checkout is unchanged."""
    reg = PrimaryRegister(pg, tmp_path)
    before_head = head(pg)
    before_ids = {r["write_id"] for r in rows(pg, "SELECT write_id FROM journal")}
    checkout_before = reg.estate.state()
    message = f"lanes-edit.sh {ENTRIES[entry][1]}: test 1's part N, {entry}"
    clock_before = db_clock(pg)
    done = projection_entry(reg.copy, reg.env, reg.estate.checkout, tmp_path, entry, message)
    clock_after = db_clock(pg)
    assert done["snapshot"].returncode == 0, (
        f"register snapshot exited {done['snapshot'].returncode}: {done['snapshot'].stderr}")
    assert done["code"] == 0, f"register commit exited {done['code']}: {done['commit'].stderr}"
    seq = before_head + 1
    assert done["commit"].stdout == f"committed {seq}\n", done["commit"].stdout

    # THE JOURNAL: one entry, at the old head plus one, with the message and
    # the write id the snapshot minted, unique in the journal.
    new = rows(pg, f"SELECT seq, write_id, kind, verb, lane, message FROM journal "
                   f"WHERE seq > {before_head} ORDER BY seq")
    lane, verb, _edit, path = ENTRIES[entry]
    assert new == [{"seq": seq, "write_id": done["fields"]["write_id"], "kind": "write",
                    "verb": verb, "lane": lane, "message": message}], new
    assert done["fields"]["write_id"] not in before_ids
    assert rows(pg, f"SELECT count(*) AS n FROM journal "
                    f"WHERE write_id = '{done['fields']['write_id']}'") == [{"n": 1}]

    # THE ROWS: every row the entry wrote reads `primary` as its last writer's.
    touched = rows(pg, f"SELECT 'doc_lines' AS t, written_mode AS m FROM doc_lines "
                       f"WHERE written_seq = {seq} "
                       f"UNION ALL SELECT 'lanes', last_mode FROM lanes WHERE last_seq = {seq} "
                       f"UNION ALL SELECT 'log_lines', mode FROM log_lines WHERE seq = {seq} "
                       f"UNION ALL SELECT 'register_lines', mode FROM register_lines "
                       f"WHERE seq = {seq} "
                       f"UNION ALL SELECT 'object_holds', mode FROM object_holds WHERE seq = {seq}")
    assert touched and {r["m"] for r in touched} == {"primary"}, touched

    # THE UTC: the database's clock in whole seconds (S6, D13).
    utc = utc_of(int(done["fields"]["clock"]))
    assert UTC_RE.match(utc) and utc in done["line"]
    assert clock_before <= epoch_of(utc) <= clock_after, (clock_before, utc, clock_after)

    # THE MIRROR: the pure renderer at seq equals the full render from SQL.
    proc, images = render_images(reg.copy, reg.env, seq, tmp_path / "mirror")
    assert proc.returncode == 0, f"render --images exited {proc.returncode}: {proc.stderr}"
    assert all(RENDER_SET.match(p) or p == STORE_PATH for p in images), (
        f"the renderer wrote outside its four paths: {sorted(images)}")
    full = _rendered_only(full_render(pg))
    assert sorted(_rendered_only(images)) == sorted(full), "the path sets are equal"
    for name in full:
        assert _rendered_only(images)[name] == full[name], f"{name}'s bytes differ"
    assert done["line"].encode("utf-8") + b"\n" in full[path]
    assert images[path] == (done["attempt"] / "images" / path).read_bytes(), (
        "the image the writer sent is the one rendered")
    assert reg.estate.state() == checkout_before, "the lane checkout is unchanged"


def _stats(samples: list) -> dict:
    """Section 5.3's statistics: median and p95 by nearest rank, min-max, n."""
    ordered = sorted(samples)
    rank = lambda p: ordered[max(0, -(-p * len(ordered) // 100) - 1)]  # noqa: E731
    return {"median": rank(50), "p95": rank(95), "min": ordered[0], "max": ordered[-1],
            "n": len(ordered)}


def test_the_render_of_one_entry_and_of_a_full_render_is_timed_and_recorded(pg, tmp_path):
    """M6 (section 5.1): the pure renderer's time, exec to exit, cold once
    and ten warm, for a full render of the fixture register (its images at
    the import's seq) and for one journal entry's image (its images at the
    seq of one entry the storage layer committed on top), each recorded with
    section 5.3's statistics and its n in the job's log and
    `$GITHUB_STEP_SUMMARY` where it is set; never asserted. The correctness
    alongside: every run answers 0; the full render equals C's files byte for
    byte; the one entry's render equals the full render from SQL for the
    same paths, so a measurement that rendered wrongly fails, whatever its
    time."""
    reg = PrimaryRegister(pg, tmp_path)
    done = projection_entry(reg.copy, reg.env, reg.estate.checkout, tmp_path, "log-noted",
                            "lanes-edit.sh log: test 1's measured entry")
    assert done["code"] == 0, (done["snapshot"].stderr, done["commit"] and done["commit"].stderr)
    seq = int(done["commit"].stdout.split()[1])
    path = ENTRIES["log-noted"][3]
    sql_render = _rendered_only(full_render(reg.pg))
    figures = {}
    for label, k in (("full render, the fixture register", reg.imported),
                     ("one entry's image", seq)):
        times = []
        for n in range(11):
            out_dir = tmp_path / "timed" / f"{k}-{n}"
            start = time.monotonic_ns()
            proc, images = render_images(reg.copy, reg.env, k, out_dir)
            times.append((time.monotonic_ns() - start) / 1e6)
            assert proc.returncode == 0, f"render --images --at {k}: {proc.stderr}"
            if k == reg.imported:
                assert _rendered_only(images) == reg.estate.render_set(), (
                    "the full render is C's render set, byte for byte")
            else:
                assert images[path] == sql_render[path], (
                    "the one entry's render equals the full render from SQL")
        figures[label] = (times[0], _stats(times[1:]))
    lines = []
    for label, (cold, warm) in figures.items():
        lines.append(f"| M6 | fixture cluster, Unix socket | `render --images`, {label} | "
                     f"cold {cold:.1f} ms | median {warm['median']:.1f} ms, p95 "
                     f"{warm['p95']:.1f} ms, {warm['min']:.1f}-{warm['max']:.1f} ms, "
                     f"n={warm['n']} |")
    print("\n" + "\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


# ============================================================ `sync --source register` (FP)

def fake_psql_dir(directory: Path, answers: list = None) -> dict:
    """T203's register fake, written to `directory` as `psql`, which a case
    puts first on `PATH`. Since T203b it answers `psql --version` itself,
    `psql (PostgreSQL) 16.4` (`PSQL_VERSION_LINE`), the probe lane 1's T106
    makes once per process on a register path, and logs that probe as its
    own kind (`"kind": "version"`, no `call`). Returns the variables the fake
    reads: its log, and its answers where `answers` teaches any (T203's
    docstring)."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "psql").write_text(REGISTER_FAKE_PSQL, encoding="utf-8")
    (directory / "psql").chmod(0o755)
    env = {"FAKE_PSQL_LOG": str(directory / "psql.log")}
    if answers is not None:
        (directory / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
        env["FAKE_PSQL_ANSWERS"] = str(directory / "answers.json")
    return env


def fake_calls(fake: dict) -> list:
    """The fake's log, one object per call that carried a request: the
    entries with no `kind`. A `psql --version` probe (T203b's `"kind":
    "version"`) sends nothing, so it is left out, as T210's own wrapper
    left it out before T203b."""
    log = Path(fake["FAKE_PSQL_LOG"])
    if not log.exists():
        return []
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]
    return [e for e in entries if e.get("kind") != "version"]


#: What `_masked_path` keeps off a case's `PATH`: an installed `lanes-index`,
#: a real `psql`, and every `pg_` client that `postgresql-16` puts beside it.
_MASKED_NAMES = ("psql", "lanes-index")
_MASKED_PREFIX = "pg_"
#: `_masked_path`'s mirrors, built once per process: each masked directory's
#: real path, to its mirror under the one `l2-pathmask-` directory.
_PATH_MIRRORS: dict = {}
_PATH_MIRROR_ROOT: list = []


def _masked_path() -> str:
    """The caller's PATH with every directory kept, in its place, and each one
    that holds a masked name swapped for a mirror of it without them. A real
    `psql` or `pg_` client, or an installed `lanes-index`, is never what a
    case runs; but dropping the directory that holds one drops what sits
    beside it. On a GitHub runner, `postgresql-16`'s client package puts
    `psql` in `/usr/bin` together with `git` and `bash`, and `/bin` links
    there, so a filter that drops the directory leaves a case no `git` or
    `bash` to run. The mirror is a directory of symlinks, one per entry, each
    to the original entry's absolute path, the masked names left out. It is
    built once per process, keyed by the directory's real path, under one
    temporary directory that an `atexit` handler removes. A directory that
    holds no masked name passes through unchanged, so where no `PATH`
    directory holds one, the PATH is what the old filter gave; empty entries
    are left out, as that filter left them."""
    kept = []
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if not part:
            continue
        real = os.path.realpath(part)
        if real not in _PATH_MIRRORS:
            try:
                names = os.listdir(real)
            except OSError:
                names = []
            if not any(_is_masked(name) for name in names):
                kept.append(part)
                continue
            _PATH_MIRRORS[real] = _path_mirror(real, names)
        kept.append(_PATH_MIRRORS[real])
    return os.pathsep.join(kept)


def _is_masked(name: str) -> bool:
    return name in _MASKED_NAMES or name.startswith(_MASKED_PREFIX)


def _path_mirror(real: str, names: list) -> str:
    """`real`'s mirror: a new directory under the one `l2-pathmask-`
    directory, holding a symlink to each entry of `real` but the masked."""
    if not _PATH_MIRROR_ROOT:
        root = tempfile.mkdtemp(prefix="l2-pathmask-")
        atexit.register(shutil.rmtree, root, ignore_errors=True)
        _PATH_MIRROR_ROOT.append(root)
    mirror = tempfile.mkdtemp(prefix=(os.path.basename(real) or "root") + "-",
                              dir=_PATH_MIRROR_ROOT[0])
    for name in names:
        if not _is_masked(name):
            os.symlink(os.path.join(real, name), os.path.join(mirror, name))
    return mirror


def workspace(root: Path, fakebin: Path) -> tuple:
    """A files-mode workspace on a bare origin, at C (SEED), whose
    `workspace.yaml` names that origin as its `repository:` and the checkout
    as its `path:`, as `test_sql_register_import.py`'s `Workspace` names
    them, with a fake `tmux` and `fakebin` first on `PATH`, in the
    environment that `Workspace` sets. Returns (the estate, the environment,
    the register source `sync --source` must name: `register:` and the
    repository as `lanes-index`'s `source_of` normalizes it, its `.git`
    dropped)."""
    estate = Estate(root)
    agents = estate.home / ".agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "workspace.yaml").write_text(
        f"repository: {estate.origin}\npath: {estate.checkout}\n", encoding="utf-8")
    source = "register:" + re.sub(r"\.git$", "", str(estate.origin))
    fakebin.mkdir(parents=True, exist_ok=True)
    (fakebin / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (fakebin / "tmux").chmod(0o755)
    for d in ("state", "config", "tmp"):
        (root / d).mkdir(parents=True, exist_ok=True)
    env = dict(estate.env)
    env.update(AGENT_PROTOCOL_ROOT=str(agents), TMPDIR=str(root / "tmp"),
               XDG_STATE_HOME=str(root / "state"), XDG_CONFIG_HOME=str(root / "config"),
               CLAUDE_CONFIG_DIR=str(estate.home / ".claude"), LANES_WORKSTATION=WS,
               LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none",
               LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1", LANES_REPO=str(estate.checkout),
               PATH=str(fakebin) + os.pathsep + _masked_path())
    return estate, env, source


def test_sync_source_register_does_nothing_on_primary_and_says_so(tmp_path):
    """`lanes-index sync --source register:<owner/repo>` on a `mode=primary`
    workstation, this workstation's own source, makes no `psql` call, writes
    nothing (the checkout's HEAD, status, index and `origin/main` as they
    were, and nothing in `lanes-index`'s state directory but its sync lock:
    no index store, no status record), exits 0, and its output says it does
    nothing on primary (AT-1's
    FP case; lane 1's T117, "`cmd_sync` with a `register:<owner/repo>`
    source does nothing on primary, and says so"; the delta's "The post-write
    nudge does not re-index the mirror into its own source"). #160's
    run-wide `LANES_INDEX=off` is unset, or it would say nothing of
    primary."""
    fakebin = tmp_path / "fakebin"
    fake = fake_psql_dir(fakebin)
    estate, env, source = workspace(tmp_path / "ws", fakebin)
    copy = flipped(tmp_path)
    sock = tmp_path / "sock"
    sock.mkdir()
    passfile = tmp_path / "conf" / "pgpass"
    passfile.parent.mkdir()
    passfile.write_text("", encoding="utf-8")
    passfile.chmod(0o600)
    host = quote(sock.as_posix(), safe="")
    conf = primary_config(tmp_path / "conf" / "lanes-index.conf",
                          f"postgresql://lanes_w_t210@{host}:5432/lanes_t210",
                          f"postgresql://lanes_r_t210@{host}:5432/lanes_t210", passfile)
    env.update(fake, LANES_INDEX_CONFIG=str(conf))
    env.pop("LANES_INDEX", None)
    state_root = Path(env["XDG_STATE_HOME"])
    before, state_before = estate.state(), _files_under(state_root)
    proc = run_index(copy, ["sync", "--source", source], env, cwd=estate.checkout)
    said = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"sync exited {proc.returncode}: {said}"
    assert fake_calls(fake) == [], f"sync made a psql call on primary: {fake_calls(fake)}"
    assert "primary" in said, f"sync's output does not say it does nothing on primary: {said!r}"
    assert estate.state() == before, "sync wrote to the checkout"
    state_after = _files_under(state_root)
    written = sorted(p for p, digest in state_after.items() if state_before.get(p) != digest)
    assert all(SYNC_LOCK_FILES.match(p) for p in written), (
        f"sync wrote under {state_root} on primary, beyond its lock: {written}")


#: What a sync may leave in `lanes-index`'s state directory,
#: `$XDG_STATE_HOME/openRepoTools/`, when it does nothing: its one-at-a-time
#: lock and the lock's rerun marks (`SyncLock`, 14(d) and #161). An index
#: store (`lanes-index.sqlite`) or a status record is a write.
SYNC_LOCK_FILES = re.compile(r"^openRepoTools/lanes-index\.(lock|rerun(-[a-z]+)?)$")


def _files_under(root: Path) -> dict:
    """Every file under `root`, {relative path: sha256}."""
    if not root.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


# ============================================================ the image cache (T302's API)
#
# THE IMAGE CACHE'S OWN TEST (lane 2's T210e; B10 tasks:972's `PENDING-L2`;
# F10-OWED items 26 and 34): lane 1's T302 adds the cache to `lanes-index`,
# under its state directory, `register-images/` (design Y:4963; PC-1), with
# the five functions and two constants of lane 3's ruling (#165 6746004829,
# extended by 6755051914) and lane 1's formats (#165 6755106847, "The
# formats, for lane 2's test"), as its fix round left them (6755799745; lane
# 3's delta check, 6755954683). T302's first run selects these cases with
# `-k 'sql_register_render and image_cache'`. They need no engine: each loads
# `lanes-index` as a module, with `XDG_STATE_HOME` under the case's own
# directory, and calls the API in process. They fail until T302 lands, by the
# assertion `image_cache_module` makes; the last one fails until lane 1's
# follow-up commit too (6755954683, doubts 1 and 2).

#: The API lane 3's ruling fixes: five functions and two constants.
IMAGE_CACHE_API = ("image_cache_get", "image_cache_put", "image_cache_head",
                   "image_cache_record", "image_cache_collect")
IMAGE_CACHE_CONSTANTS = {"IMAGE_CACHE_KEEP": 3, "IMAGE_CACHE_FLOOR_SECONDS": 600}
#: A temp file as lane 1's format names it: `.<name>.tmp-<pid>-<8 hex>`.
IMAGE_CACHE_TEMP = re.compile(r"^\..+\.tmp-[0-9]+-[0-9a-f]{8}$")
#: Older than collection's floor, with room: an hour before now.
IMAGE_CACHE_OLD = 3600


class ImageCache:
    """`lanes-index` loaded as a module whose state directory is `state`
    (`XDG_STATE_HOME`), with the cache's paths."""

    def __init__(self, module, state: Path):
        self.m = module
        self.root = state / "openRepoTools" / "register-images"
        self.objects = self.root / "objects"
        self.seq = self.root / "seq"
        self.head_file = self.root / "head"
        self.lock = self.root / "lock"

    def object(self, digest: str) -> Path:
        return self.objects / digest

    def age(self, path: Path, seconds: int = IMAGE_CACHE_OLD) -> None:
        """Sets `path`'s mtime `seconds` before now, past the floor."""
        then = time.time() - seconds
        os.utime(path, (then, then), follow_symlinks=False)

    def temps(self) -> list:
        """Every temp file of lane 1's form left anywhere in the cache."""
        if not self.root.is_dir():
            return []
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob(".*")
                      if IMAGE_CACHE_TEMP.match(p.name))


def image_cache_module(tmp_path: Path, monkeypatch) -> ImageCache:
    """`lanes-index` as a module, under its own name so nothing else in the
    run shares it, with `XDG_STATE_HOME` set to `<tmp_path>/state`, where
    `state_dir()` puts `openRepoTools/register-images/`. Asserts the API is
    there: lane 1's T302, B10 tasks:972 (the case's red until it lands)."""
    from importlib.machinery import SourceFileLoader
    import importlib.util
    loader = SourceFileLoader(f"lanes_index_image_cache_{uuid.uuid4().hex}", str(LANES_INDEX))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    missing = [name for name in (*IMAGE_CACHE_API, *IMAGE_CACHE_CONSTANTS)
               if not hasattr(module, name)]
    assert not missing, (
        f"{LANES_INDEX} has no image cache API, {missing} missing: lane 1's T302 (B10 "
        f"tasks:972; #165 6755106847) has not landed")
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    return ImageCache(module, state)


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_the_image_cache_puts_and_gets_an_object_only_by_its_digest(tmp_path, monkeypatch):
    """`image_cache_put(data)` returns `data`'s sha256 as 64 lowercase hex and
    writes `objects/<digest>` under `$XDG_STATE_HOME/openRepoTools/
    register-images/`, the file 0600 and each directory 0700, by a temp file
    and a rename that leaves no temp file; a `bytearray` is taken as bytes,
    and anything else raises `TypeError` before the cache is touched, the
    one error that escapes. `image_cache_get(digest)` returns the bytes only
    when they hash to `digest`: a missing object, a digest that is not 64
    lowercase hex, a name outside `objects/`, an object whose bytes changed
    and a symlink at the object's name are each a miss (None), and `put`
    replaces the bad object and leaves a link's target alone. A second `put`
    of an object already whole rewrites nothing and sets its mtime to now,
    so the floor keeps it (lane 1's readings 1 and 2; fix round NIT-3 and
    NIT-4)."""
    cache = image_cache_module(tmp_path, monkeypatch)
    m = cache.m
    with pytest.raises(TypeError):
        m.image_cache_put("lanes/LANES.md as text, not bytes")
    assert not (tmp_path / "state").exists(), "put touched the cache before its TypeError"

    data = f"# LANES.md {EM} the image cache's own test\n".encode("utf-8")
    digest = m.image_cache_put(data)
    assert digest == _digest(data) and re.fullmatch(r"[0-9a-f]{64}", digest), digest
    assert cache.object(digest).read_bytes() == data
    assert _mode(cache.object(digest)) == 0o600, oct(_mode(cache.object(digest)))
    for directory in (tmp_path / "state" / "openRepoTools", cache.root, cache.objects):
        assert _mode(directory) == 0o700, f"{directory} is {oct(_mode(directory))}, not 0700"
    assert m.image_cache_get(digest) == data
    assert m.image_cache_put(bytearray(data)) == digest
    assert cache.temps() == [], f"a temp file was left: {cache.temps()}"

    # MISSES: an object that is not there, and digests out of form.
    other = _digest(b"never put\n")
    assert m.image_cache_get(other) is None
    for bad in (digest.upper(), digest[:63], digest + "0", "", "../head", None, 7):
        assert m.image_cache_get(bad) is None, f"get({bad!r}) was not a miss"

    # A WHOLE OBJECT IS NOT WRITTEN AGAIN; ITS MTIME COMES TO NOW.
    inode = os.lstat(cache.object(digest)).st_ino
    cache.age(cache.object(digest))
    assert m.image_cache_put(data) == digest
    assert os.lstat(cache.object(digest)).st_ino == inode, "a whole object was rewritten"
    assert time.time() - os.lstat(cache.object(digest)).st_mtime < 60, (
        "put of a whole object left its old mtime, so the floor would not keep it")

    # AN OBJECT WHOSE BYTES CHANGED IS A MISS, AND PUT REPLACES IT.
    cache.object(digest).write_bytes(b"torn")
    assert m.image_cache_get(digest) is None, "get returned bytes that do not hash to the name"
    assert m.image_cache_put(data) == digest
    assert m.image_cache_get(digest) == data and cache.object(digest).read_bytes() == data

    # A SYMLINK AT THE OBJECT'S NAME IS A MISS, AND PUT REPLACES IT (NIT-4).
    outside = tmp_path / "outside"
    outside.write_bytes(data)
    cache.object(digest).unlink()
    cache.object(digest).symlink_to(outside)
    assert m.image_cache_get(digest) is None, "get followed a symlink at an object's name"
    assert m.image_cache_put(data) == digest
    assert not cache.object(digest).is_symlink() and cache.object(digest).read_bytes() == data
    assert outside.read_bytes() == data, "put changed a link's target"
    assert cache.temps() == [], f"a temp file was left: {cache.temps()}"


def test_the_image_cache_records_manifests_and_a_head_that_moves_only_forward(tmp_path,
                                                                               monkeypatch):
    """`image_cache_record(n, manifest)` writes `seq/<n>`, one `<path>` TAB
    `<digest>` line per path, each LF-ended, sorted by path bytewise, an
    empty manifest an empty file, 0600; a second record of one `n` merges
    into the first, a path in both taking the second's digest. `head` is
    `<n>` and an LF, read with or without the LF and never with a leading
    zero, and moves only forward; a missing `head`, or one with no seq, is
    written as the larger of `n` and the highest seq `seq/` lists (NIT-2).
    `image_cache_head()` answers (seq, manifest), or None. A record whose `n`
    is not a whole number from 0 to 2**63 - 1, or whose manifest is not a
    dict of paths with no control character to digests, is skipped, and no
    call raises (lane 1's readings 6 and 7)."""
    cache = image_cache_module(tmp_path, monkeypatch)
    m = cache.m
    assert m.image_cache_head() is None
    accented = "lanes/log/repo" + chr(0x00E9) + "-1.md"
    d1, d2, d3 = (_digest(f"image {k}\n".encode("ascii")) for k in (1, 2, 3))
    m.image_cache_record(5, {"lanes/log/repoA-1.md": d2, accented: d3, "lanes/LANES.md": d1})
    expected = [("lanes/LANES.md", d1), ("lanes/log/repoA-1.md", d2), (accented, d3)]
    assert (cache.seq / "5").read_bytes() == "".join(
        f"{p}\t{d}\n" for p, d in expected).encode("utf-8"), "the manifest's form or order"
    assert cache.head_file.read_bytes() == b"5\n"
    assert _mode(cache.seq / "5") == 0o600 and _mode(cache.head_file) == 0o600
    assert _mode(cache.seq) == 0o700
    assert m.image_cache_head() == (5, dict(expected))

    # THE HEAD NEVER MOVES BACK.
    m.image_cache_record(3, {"lanes/LANES.md": d2})
    assert (cache.seq / "3").read_bytes() == f"lanes/LANES.md\t{d2}\n".encode("ascii")
    assert cache.head_file.read_bytes() == b"5\n", "a lower record moved the head back"

    # A SECOND RECORD OF ONE SEQ MERGES, ITS OWN DIGEST WINNING.
    m.image_cache_record(5, {"lanes/LANES.md": d3, "lanes/aliases.tsv": d1})
    assert m.image_cache_head() == (5, {"lanes/LANES.md": d3, "lanes/aliases.tsv": d1,
                                        "lanes/log/repoA-1.md": d2, accented: d3})

    # AN EMPTY MANIFEST IS AN EMPTY FILE; THE HEAD READS WITH OR WITHOUT ITS LF.
    m.image_cache_record(7, {})
    assert (cache.seq / "7").read_bytes() == b"" and cache.head_file.read_bytes() == b"7\n"
    assert m.image_cache_head() == (7, {})
    cache.head_file.write_bytes(b"7")
    assert m.image_cache_head() == (7, {}), "a head with no LF is not read"
    for bad in (b"07\n", b"7\n\n", b" 7\n", b"seven\n", b""):
        cache.head_file.write_bytes(bad)
        assert m.image_cache_head() is None, f"a head of {bad!r} was read"

    # A HEAD WITH NO SEQ, OR NONE, IS WRITTEN AS THE LARGER OF n AND seq/'s HIGHEST.
    cache.head_file.write_bytes(b"seven\n")
    m.image_cache_record(4, {"lanes/LANES.md": d1})
    assert cache.head_file.read_bytes() == b"7\n", "a junk head was not repaired to 7"
    cache.head_file.unlink()
    m.image_cache_record(2, {"lanes/LANES.md": d1})
    assert cache.head_file.read_bytes() == b"7\n", "a missing head moved back to 2"

    # RECORDS OUT OF FORM ARE SKIPPED, AND RAISE NOTHING.
    before = sorted(p.name for p in cache.seq.iterdir())
    for n, manifest in ((-1, {}), (True, {}), (2 ** 63, {}), ("9", {}), (9.0, {}),
                        (9, {"lanes/LANES.md": d1.upper()}), (9, {"lanes/a\tb.md": d1}),
                        (9, {"lanes/a\nb.md": d1}), (9, {"lanes/a" + chr(0) + ".md": d1}),
                        (9, {"": d1}), (9, [("lanes/LANES.md", d1)]), (9, None)):
        m.image_cache_record(n, manifest)
    assert sorted(p.name for p in cache.seq.iterdir()) == before, (
        "a record out of form wrote a manifest")
    assert cache.head_file.read_bytes() == b"7\n"
    assert m.image_cache_record(2 ** 63 - 1, {}) is None
    assert cache.head_file.read_bytes() == str(2 ** 63 - 1).encode("ascii") + b"\n"
    assert cache.temps() == [], f"a temp file was left: {cache.temps()}"


def test_the_image_cache_collects_all_but_the_last_three_manifests_past_the_floor(
        tmp_path, monkeypatch):
    """Collection keeps the manifests of the `IMAGE_CACHE_KEEP` = 3 highest
    seqs and removes every older one; it removes an object named in none of
    them only when its mtime is over `IMAGE_CACHE_FLOOR_SECONDS` = 600 old,
    so an old object a kept manifest names, and a young one none names, both
    stay. It removes a temp file of the form `.<name>.tmp-<pid>-<8 hex>`
    only past the same floor, and no other name. Where one of the kept
    manifests is out of form, it removes no object (lane 1's readings 3, 4
    and 5). `image_cache_record` collects too, under the same lock."""
    cache = image_cache_module(tmp_path, monkeypatch)
    m = cache.m
    for name, value in IMAGE_CACHE_CONSTANTS.items():
        assert getattr(m, name) == value, f"{name} is {getattr(m, name)!r}, not {value}"
    data = [f"image {k}\n".encode("ascii") for k in range(1, 8)]
    o = [m.image_cache_put(d) for d in data]
    for k in range(1, 6):
        m.image_cache_record(k, {"lanes/LANES.md": o[k - 1]})
    assert sorted(p.name for p in cache.seq.iterdir()) == ["3", "4", "5"], (
        "record kept a manifest older than the last three")

    for k in (0, 1, 2, 3, 6):
        cache.age(cache.object(o[k]))
    temps = {"objects/.x.tmp-41-0123abcd": True, "objects/.y.tmp-42-89abcdef": False,
             ".head.tmp-43-deadbeef": True, "seq/.5.tmp-44-cafef00d": True}
    strays = ("objects/notes.txt", "objects/" + "A" * 64, "objects/.x.tmp-45-XYZ")
    for rel, old in temps.items():
        (cache.root / rel).write_bytes(b"part")
        if old:
            cache.age(cache.root / rel)
    for rel in strays:
        (cache.root / rel).write_bytes(b"stray")
        cache.age(cache.root / rel)

    m.image_cache_collect()
    kept = {k for k in range(7) if cache.object(o[k]).exists()}
    assert kept == {2, 3, 4, 5}, (
        f"objects kept: {sorted(kept)}, not images 3 and 4 (old, named by seqs 3 and 4), 5 "
        f"(named by the head) and 6 (named by none, younger than the floor)")
    assert sorted(p.name for p in cache.seq.iterdir() if not p.name.startswith(".")) == \
        ["3", "4", "5"]
    for rel, old in temps.items():
        assert (cache.root / rel).exists() is not old, (
            f"{rel}: a temp file {'over' if old else 'under'} the floor was "
            f"{'kept' if old else 'removed'}")
    for rel in strays:
        assert (cache.root / rel).exists(), f"collection removed {rel}, not a name it writes"
    assert m.image_cache_head() == (5, {"lanes/LANES.md": o[4]})

    # A KEPT MANIFEST OUT OF FORM: NO OBJECT IS REMOVED.
    cache.age(cache.object(o[5]))
    (cache.seq / "4").write_bytes(b"lanes/LANES.md")
    m.image_cache_collect()
    assert cache.object(o[5]).exists(), (
        "collection removed an object while a kept manifest could not be read")


def test_the_image_cache_skips_a_busy_or_odd_lock_and_never_waits(tmp_path, monkeypatch):
    """Recording and collection take `register-images/lock` with `LOCK_EX |
    LOCK_NB`, tried once: while another holder has it, `image_cache_record`
    writes nothing and `image_cache_collect` removes nothing, and neither
    waits. A `lock` that is not a regular file, a FIFO with no reader here,
    counts as busy, and the call returns at once with nothing changed
    (lane 1's fix round, SHOULD-1). The lock file is 0600."""
    import fcntl
    import threading
    cache = image_cache_module(tmp_path, monkeypatch)
    m = cache.m
    d1, d2 = (m.image_cache_put(f"image {k}\n".encode("ascii")) for k in (1, 2))
    m.image_cache_record(1, {"lanes/LANES.md": d1})
    assert _mode(cache.lock) == 0o600, oct(_mode(cache.lock))
    loose = m.image_cache_put(b"named by no manifest\n")
    cache.age(cache.object(loose))

    held = os.open(str(cache.lock), os.O_WRONLY | os.O_APPEND)
    try:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        start = time.monotonic()
        m.image_cache_record(2, {"lanes/LANES.md": d2})
        m.image_cache_collect()
        assert time.monotonic() - start < 5, "a call waited for the held lock"
        assert not (cache.seq / "2").exists(), "record wrote while the lock was held"
        assert cache.head_file.read_bytes() == b"1\n"
        assert cache.object(loose).exists(), "collect removed an object while the lock was held"
    finally:
        os.close(held)

    m.image_cache_collect()
    assert not cache.object(loose).exists(), "collect did nothing once the lock was free"
    m.image_cache_record(2, {"lanes/LANES.md": d2})
    assert cache.head_file.read_bytes() == b"2\n"

    # A FIFO AT THE LOCK'S NAME: BUSY, AT ONCE, WHETHER OR NOT IT BLOCKS ITS OPEN.
    os.replace(str(cache.lock), str(cache.root / "lock.aside"))
    os.mkfifo(str(cache.lock), 0o600)
    loose = m.image_cache_put(b"named by no manifest, again\n")
    cache.age(cache.object(loose))
    worker = threading.Thread(target=lambda: (m.image_cache_record(3, {"lanes/LANES.md": d1}),
                                              m.image_cache_collect()), daemon=True)
    worker.start()
    worker.join(10)
    assert not worker.is_alive(), "record or collect blocked on a FIFO at the lock's name"
    assert not (cache.seq / "3").exists() and cache.head_file.read_bytes() == b"2\n"
    assert cache.object(loose).exists(), "collect ran through a FIFO lock"
    assert stat.S_ISFIFO(os.lstat(cache.lock).st_mode)


def test_the_image_cache_follows_no_symlink_at_its_lock_or_its_head(tmp_path, monkeypatch):
    """Lane 1's follow-up to T302's fix round (lane 3's delta check, #165
    6755954683, doubts 1 and 2): the lock is opened with `O_NOFOLLOW`, so a
    symlink planted at `register-images/lock` is a skip, its target neither
    changed nor created; and `record` treats a symlinked `head` as a missing
    one, so it replaces the link with a regular `head` and leaves the link's
    target alone. Until that commit lands, this case fails by its own
    assertion, where the rest of the image cache's cases pass."""
    cache = image_cache_module(tmp_path, monkeypatch)
    m = cache.m
    d1 = m.image_cache_put(b"image 1\n")
    m.image_cache_record(1, {"lanes/LANES.md": d1})

    # A SYMLINKED HEAD: RECORD REPLACES THE LINK, NOT ITS TARGET.
    target = tmp_path / "elsewhere-head"
    target.write_bytes(b"1\n")
    cache.head_file.unlink()
    cache.head_file.symlink_to(target)
    m.image_cache_record(2, {"lanes/LANES.md": d1})
    assert target.read_bytes() == b"1\n", "record wrote through a symlinked head"
    assert not cache.head_file.is_symlink() and cache.head_file.read_bytes() == b"2\n", (
        "record left a symlinked head in place (lane 3's 6755954683, doubt 2's fix: ELOOP as "
        "FileNotFoundError), so image_cache_head() stays unreadable")

    # A SYMLINKED LOCK, DANGLING: A SKIP, AND ITS TARGET IS NOT CREATED.
    planted = tmp_path / "elsewhere" / "lock-target"
    planted.parent.mkdir()
    os.replace(str(cache.lock), str(cache.root / "lock.aside"))
    cache.lock.symlink_to(planted)
    m.image_cache_record(3, {"lanes/LANES.md": d1})
    assert not planted.exists(), (
        "the lock's open followed a symlink and created its target (lane 3's 6755954683, "
        "doubt 1: O_NOFOLLOW on the lock)")
    assert not (cache.seq / "3").exists(), "record ran under a symlinked lock"


# ======================================== the render read's `start` (T301's cache-forward)
#
# LANE 1'S CACHE-FORWARD COMMIT (T301's `e4d28a505af8`, tag `l1-007-T301-cf1`;
# #165 6767347563; the cache signature lane 3 accepted in 6755051914, B10
# tasks:996-1003). B10 gives T210 "one case with `start`, so that both arms are
# covered", and lane 1's doubt 1 says what it expects: with `start`,
# `register_render_read` returns THE IMAGES, `{path: bytes}`, and not the rows;
# without it, still `(journal, edits, files)`. T210f (line W4b, wave 6) is this
# case. It needs no engine: the read runs in process against a stand-in store
# that answers each SELECT the code sends from an in-memory sqlite database, as
# lane 1's own hand checks do ("sqlite stood in for PostgreSQL"), and fails
# until the cache-forward commit lands, by the assertion `render_read_module`
# makes.
#
# What the case reads from lane 1's code rather than from a contract, since
# section 3.6 fixes only the CLI: `register_render_read(store, k, *, start=None,
# row="render")`, `register_render_queries(k, *, since=None)`,
# `register_cache_state(images)`, `register_images(journal, edits, files, *,
# start=None)`, `RenderRefused`, and the store's one method the read calls,
# `_query_many(queries, snapshot=True, row=...)`, whose answer is a list of
# result sets of rows of text fields (`t`/`f` for a boolean, None for NULL).

#: The paths of the journal below: the render set's files, and `lanes/STORE`,
#: which is journaled and is never an image.
LANES_MD, ALPHA_LOG, BETA_LOG, GAMMA_LOG = ("lanes/LANES.md", "lanes/log/alpha.md",
                                            "lanes/log/beta.md", "lanes/log/gamma.md")
ALIASES_TSV, ARCHIVE_MD = "lanes/aliases.tsv", "lanes/archive/old.md"
#: The files whose row says `final_newline` false: an image with no last LF.
NO_LAST_LF = frozenset({ALIASES_TSV})

#: AT-1's journal in miniature, as `commit_write` leaves it (design section 1.3.1): an
#: import, then writes. An entry is `(kind, edits, no_last_lf)`; an edit is
#: `("create", path)`, `("append", path, text)`, `("replace", path, n, text)`,
#: `("delete", path, n)` or `("remove", path)`. Seq 2 touches `lanes/STORE`;
#: seq 3 replaces a line, seq 4 deletes one, seq 5 removes a file, and
#: `lanes/archive/old.md` is never touched after the import.
RENDER_JOURNAL = [
    ("import", [("create", LANES_MD), ("append", LANES_MD, "# LANES"),
                ("append", LANES_MD, "| alpha | held |"),
                ("create", ALPHA_LOG), ("append", ALPHA_LOG, "alpha 1"),
                ("append", ALPHA_LOG, f"alpha 2 {EM} two"),
                ("create", ALIASES_TSV), ("append", ALIASES_TSV, "old\talpha"),
                ("create", ARCHIVE_MD), ("append", ARCHIVE_MD, "archived")], NO_LAST_LF),
    ("write", [("append", LANES_MD, "| beta | free |")], ()),
    ("write", [("append", ALPHA_LOG, "alpha 3"), ("create", BETA_LOG),
               ("append", BETA_LOG, "beta 1"), ("create", STORE_PATH)], ()),
    ("write", [("replace", ALPHA_LOG, 1, "alpha 1 (edited)")], ()),
    ("write", [("delete", ALPHA_LOG, 2), ("append", ALIASES_TSV, "new\tbeta")], NO_LAST_LF),
    ("write", [("remove", BETA_LOG), ("append", LANES_MD, "| gamma | free |")], ()),
]
#: The same register after a re-import at seq 4 (before a confirmed cutover):
#: the root is replaced, so alpha and beta are gone and the seqs 0 to 3 of the
#: old root are history a cache may still hold.
RENDER_REIMPORT = RENDER_JOURNAL[:4] + [
    ("import", [("create", LANES_MD), ("append", LANES_MD, "# LANES (re-imported)"),
                ("create", GAMMA_LOG), ("append", GAMMA_LOG, "gamma 1"),
                ("create", ALIASES_TSV), ("append", ALIASES_TSV, "old\tgamma")], NO_LAST_LF),
    ("write", [("append", GAMMA_LOG, "gamma 2")], ()),
]


def _render_image_bytes(lines: list, final_newline: bool) -> bytes:
    """One file's bytes as `render_file` builds them (design Y:1297), spelled
    out here so that the case's oracle is not the code's own function."""
    return ("\n".join(lines) + ("\n" if final_newline and lines else "")).encode("utf-8")


class RenderJournal:
    """`entries` replayed by this test's own model, which gives what the
    register would hold: the rows of `journal`, `journal_edits` and
    `journal_files`, and for each seq the render set's images and its state,
    `{path: (lines, final_newline)}`, as the cache's read-back should give."""

    def __init__(self, entries: list):
        self.rows = {"journal": [], "journal_edits": [], "journal_files": []}
        self.images_at, self.state_at = [], []
        state: dict = {}
        for seq, (kind, edits, no_last_lf) in enumerate(entries):
            self.rows["journal"].append((seq, kind))
            if kind == "import":
                state.clear()
            touched = []
            for ordinal, edit in enumerate(edits, 1):
                op, path = edit[0], edit[1]
                if path not in touched:
                    touched.append(path)
                lines = state[path][0] if path in state else None
                row = (None, None, None)
                if op == "create":
                    state[path] = [[], True]
                elif op == "append":
                    row = (len(lines) + 1, None, edit[2])
                    lines.append(edit[2])
                elif op == "replace":
                    row = (edit[2], _digest(lines[edit[2] - 1].encode("utf-8")), edit[3])
                    lines[edit[2] - 1] = edit[3]
                elif op == "delete":
                    row = (edit[2], _digest(lines[edit[2] - 1].encode("utf-8")), None)
                    del lines[edit[2] - 1]
                else:
                    del state[path]
                self.rows["journal_edits"].append((seq, ordinal, op, path, *row, None))
            for path in touched:
                if path not in state:
                    self.rows["journal_files"].append((seq, path, "f", None, None))
                    continue
                if path in no_last_lf:
                    state[path][1] = False
                lines, final_newline = state[path]
                self.rows["journal_files"].append(
                    (seq, path, "t", _digest(_render_image_bytes(lines, final_newline)),
                     "t" if final_newline else "f"))
            self.images_at.append({p: _render_image_bytes(*v) for p, v in state.items()
                                   if RENDER_SET.match(p)})
            self.state_at.append({p: (list(v[0]), v[1]) for p, v in state.items()
                                  if RENDER_SET.match(p)})
        self.last = len(entries) - 1


class RenderRegister:
    """The stand-in store: `register_render_read` calls `store._query_many(
    queries, snapshot=True, row=...)`, and this answers each SELECT it is
    given from an in-memory sqlite database holding `journal`'s rows. It
    records each call in `requests`, as `(queries, snapshot, row)`. With
    `raises` set, a call records itself and raises that, as a dead connection
    does. Line R's `_register_render_rows` also passes `first_request_at=`
    (`lanes-index:2434-2435` at `refs/l1/V-round4`), the bound's clock for
    `register snapshot`'s second request (#165 6780364102), which the stand-in
    takes and does not use."""

    DDL = (
        "CREATE TABLE schema_version (id INTEGER PRIMARY KEY, version INTEGER, "
        "writers_from INTEGER, readers_from INTEGER)",
        "CREATE TABLE register_head (id INTEGER PRIMARY KEY, seq INTEGER)",
        "CREATE TABLE journal (seq INTEGER PRIMARY KEY, kind TEXT)",
        "CREATE TABLE journal_edits (seq INTEGER, ord INTEGER, op TEXT, path TEXT, "
        "line_no INTEGER, old_sha256 TEXT, new_text TEXT, to_path TEXT)",
        "CREATE TABLE journal_files (seq INTEGER, path TEXT, present TEXT, sha256 TEXT, "
        "final_newline TEXT)",
    )

    def __init__(self, module, journal: RenderJournal):
        import sqlite3
        self.db = sqlite3.connect(":memory:")
        for statement in self.DDL:
            self.db.execute(statement)
        self.db.execute("INSERT INTO schema_version VALUES (1, ?, 1, 1)",
                        (module.REGISTER_SCHEMA_VERSION,))
        self.db.execute("INSERT INTO register_head VALUES (1, ?)", (journal.last,))
        for table, rows in journal.rows.items():
            self.db.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(rows[0]))})",
                                rows)
        self.requests: list = []
        self.raises = None

    def _query_many(self, queries, snapshot=False, *, row=None, timer=None,
                    first_request_at=None):
        self.requests.append((list(queries), snapshot, row))
        if self.raises is not None:
            raise self.raises
        return [[[None if value is None else str(value) for value in fetched]
                 for fetched in self.db.execute(query).fetchall()] for query in queries]


def render_read_module():
    """`lanes-index` as a module, under its own name so nothing else in the run
    shares it. Asserts lane 1's cache-forward commit is there: the case's red
    until `register_render_read`, `register_images` and `register_render_queries`
    take their `start` and `since`, and `register_cache_state` reads images
    back (#165 6755040818, 6767347563)."""
    from importlib.machinery import SourceFileLoader
    import importlib.util
    import inspect
    loader = SourceFileLoader(f"lanes_index_render_read_{uuid.uuid4().hex}", str(LANES_INDEX))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    missing = [name for name in ("register_render_read", "register_render_queries",
                                 "register_images", "register_cache_state", "RenderRefused",
                                 "PsqlFailed", "REGISTER_SCHEMA_VERSION")
               if not hasattr(module, name)]
    assert not missing, (
        f"{LANES_INDEX} has no render read, {missing} missing: lane 1's T301, with its "
        f"cache-forward commit (`e4d28a505af8`, #165 6767347563), has not landed")
    wanting = [f"{name}'s {keyword}" for name, keyword in (
        ("register_render_read", "start"), ("register_images", "start"),
        ("register_render_queries", "since"))
        if keyword not in inspect.signature(getattr(module, name)).parameters]
    assert not wanting, (
        f"{LANES_INDEX} takes no {wanting}: lane 1's T301 cache-forward commit "
        f"(`e4d28a505af8`, #165 6767347563) has not landed")
    return module


def test_the_render_read_with_start_returns_the_images_and_a_bad_start_costs_one_full_read():
    """T210's case with `start` (B10 tasks:1003; lane 1, #165 6767347563, doubt
    1: "**Lane 2:** T210's `start` case should expect images"). Both arms of
    `register_render_read`, against a register built by this test's own model
    of `commit_write`:

    WITHOUT `start` it returns `(journal, edits, files)`, the rows from the
    latest import to `k`, which `register_images` builds into the images, in
    one request.

    WITH `start=(c, state)`, `state` being `register_cache_state` of the
    images at `c`, it returns THE IMAGES AT `k`, a `dict` of `bytes` and not
    the rows, equal to the model's for every `c` from 0 to `k`: in ONE request,
    which reads only the entries after `c` (`register_render_queries(k,
    since=c)`), and `start` is left as it was.

    A START IT CANNOT TRUST IS A MISS, NOT AN ERROR, AND THE COUNT SAYS
    WHICH KIND (lane 1, #165 6769176187, for the cache-forward commit
    `e4d28a5`): a `start` of another form, or a `c` above `k`, is refused
    before any request and costs exactly ONE, the full read; a cached image
    of an untouched path that is wrong (a cache from a reused seq), a cached
    image that an edit does not apply on, and a path the cache lacks are
    found after the read since `c` and cost exactly TWO, that read and then
    the full one. Each returns the right images, the full read last. An
    import among entries `c+1` to `k` sets `start` aside, so even a wrong
    cache is no miss there, one request. Only the full read's failure ends in
    `RenderRefused`, after the two requests; a dead connection (`PsqlFailed`)
    is raised as it is, after one, and is never tried twice. And
    `register_cache_state` misses (None) on an image that is empty, is not
    UTF-8 or is not bytes, so an estate with an empty file in its render set
    always replays in full."""
    pytest.importorskip("sqlite3")
    import copy
    m = render_read_module()
    journal = RenderJournal(RENDER_JOURNAL)
    register = RenderRegister(m, journal)
    last = journal.last

    def read(k, **kwargs):
        """One call and the requests it made. A `RenderRefused` is no answer, and
        fails the expectation that asked."""
        before = len(register.requests)
        try:
            answer = m.register_render_read(register, k, **kwargs)
        except m.RenderRefused as refusal:
            raise AssertionError(f"read(k={k}) ended in RenderRefused: {refusal}") from None
        return answer, register.requests[before:]

    def kinds(k, sent):
        """The requests as `full` or `since`, for a failure's message."""
        return ["full" if queries == m.register_render_queries(k) else "since"
                for queries, _snapshot, _row in sent]

    def full(k, row="render"):
        return (m.register_render_queries(k), True, row)

    def since(k, c, row="render"):
        return (m.register_render_queries(k, since=c), True, row)

    # THE READ WITHOUT `start` GIVES THE ROWS, IN ONE REQUEST, AND THE ROWS BUILD THE IMAGES.
    for k in range(last + 1):
        rows, sent = read(k)
        assert isinstance(rows, tuple) and len(rows) == 3, (
            f"read(k={k}) without start returned {type(rows).__name__}, not "
            f"(journal, edits, files)")
        assert sent == [full(k)], f"read({k}) sent {kinds(k, sent)}"
        assert rows[0][0] == (0, "import") and rows[0][-1][0] == k, rows[0]
        assert m.register_images(*rows) == journal.images_at[k], f"the images at seq {k}"

    # THE CACHE'S READ-BACK: THE STATE THE MODEL HOLDS, FOR EVERY SEQ.
    for c in range(last + 1):
        assert m.register_cache_state(journal.images_at[c]) == journal.state_at[c], (
            f"register_cache_state of the images at seq {c}")

    # WITH `start`: THE IMAGES AT `k`, FOR EVERY `c` UP TO `k`, IN ONE REQUEST SINCE `c`.
    for c in range(last + 1):
        start = (c, m.register_cache_state(journal.images_at[c]))
        frozen = copy.deepcopy(start)
        for k in range(c, last + 1):
            images, sent = read(k, start=start)
            assert isinstance(images, dict) and not isinstance(images, tuple), (
                f"read(k={k}, start at {c}) returned {type(images).__name__}: with `start` "
                f"it returns the images, {{path: bytes}}, and not the rows")
            assert all(isinstance(p, str) and isinstance(b, bytes) for p, b in images.items())
            assert images == journal.images_at[k], f"the images at seq {k} from a cache at {c}"
            assert sent == [since(k, c)], (
                f"read(k={k}, start at {c}) sent {kinds(k, sent)}, not one request since {c}")
            assert start == frozen, "register_render_read changed `start`"

    # A START IT CANNOT TRUST IS A MISS: THE RIGHT IMAGES, AND A FULL READ LAST.
    k, c = last, 2
    good = dict(journal.images_at[c])
    wrong_untouched = {**good, ARCHIVE_MD: b"another root's archive\n"}
    wrong_edit_base = {**good, ALPHA_LOG: b"not alpha's first line\nalpha 2\nalpha 3\n"}
    lacks_untouched = {p: b for p, b in good.items() if p != ARCHIVE_MD}
    for what, images in (("a wrong image of an untouched path (a cache from a reused seq)",
                          wrong_untouched),
                         ("an image the seq-3 replace does not apply on", wrong_edit_base),
                         ("a cache that lacks an untouched path", lacks_untouched)):
        state = m.register_cache_state(images)
        assert state is not None, f"register_cache_state refused {what}"
        answer, sent = read(k, start=(c, state))
        assert answer == journal.images_at[k], f"the images after {what}"
        assert sent == [since(k, c), full(k)], (
            f"{what}: a failed proof or edit costs exactly two requests, the first since "
            f"seq {c} and the second the full read; sent {kinds(k, sent)}")
    ok_state = m.register_cache_state(good)
    for what, start, at in (("a `c` above `k`", (5, m.register_cache_state(journal.images_at[5])),
                             3),
                            ("a `c` that is not an int", ("2", ok_state), last),
                            ("a `c` that is a bool", (True, ok_state), last),
                            ("a state that is not a dict", (2, "not a state"), last),
                            ("a state of the wrong value form", (2, {LANES_MD: "text"}), last),
                            ("a start of one item", (2,), last),
                            ("a start that is not a pair", [], last)):
        answer, sent = read(at, start=start)
        assert isinstance(answer, dict) and answer == journal.images_at[at], (
            f"the images after {what}")
        assert sent == [full(at)], (
            f"{what}: a start of another form, or a `c` above `k`, is refused before any "
            f"request and costs exactly one, the full read; sent {kinds(at, sent)}")

    # AN IMPORT AMONG ENTRIES `c+1` TO `k` SETS `start` ASIDE: EVEN A WRONG CACHE IS NO MISS.
    again = RenderJournal(RENDER_REIMPORT)
    reimport = RenderRegister(m, again)
    old_root = m.register_cache_state(journal.images_at[2])
    for caches, cached in (("the old root's images", old_root),
                           ("images the seq-3 replace does not apply on, which is never "
                            "applied", m.register_cache_state(wrong_edit_base))):
        for c, k in ((2, 5), (2, 4), (3, 5)):
            before = len(reimport.requests)
            answer = m.register_render_read(reimport, k, start=(c, cached))
            assert answer == again.images_at[k], f"the images at seq {k} past the re-import"
            assert reimport.requests[before:] == [(m.register_render_queries(k, since=c), True,
                                                   "render")], (
                f"a start at {c}, {caches}, was set aside by the re-import at 4, and cost "
                f"one request")
    # A CACHE AT OR AFTER THE IMPORT IS BROUGHT FORWARD AS ANY IS.
    new_root = m.register_cache_state(again.images_at[4])
    before = len(reimport.requests)
    assert m.register_render_read(reimport, 5, start=(4, new_root)) == again.images_at[5]
    assert reimport.requests[before:] == [(m.register_render_queries(5, since=4), True, "render")]

    # ONLY THE FULL READ'S FAILURE ENDS IN `RenderRefused`: k=3 is before the latest import.
    before = len(reimport.requests)
    with pytest.raises(m.RenderRefused):
        m.register_render_read(reimport, 3, start=(2, old_root))
    assert reimport.requests[before:] == [
        (m.register_render_queries(3, since=2), True, "render"),
        (m.register_render_queries(3), True, "render")], (
        "a refused k, with a start, is two requests and then the refusal")

    # A DEAD CONNECTION IS RAISED AS IT IS, AFTER ONE REQUEST, AND NEVER TRIED TWICE.
    register.raises = m.PsqlFailed("unreachable", "the database did not answer")
    before = len(register.requests)
    with pytest.raises(m.PsqlFailed):
        m.register_render_read(register, last, start=(2, ok_state))
    assert register.requests[before:] == [since(last, 2)], "a dead connection was tried twice"
    register.raises = None

    # THE CACHE'S READ-BACK MISSES ON AN IMAGE IT CANNOT READ BACK: THE ESTATE REPLAYS IN FULL.
    images = journal.images_at[last]
    assert m.register_cache_state(images) == journal.state_at[last]
    for what, bad in (("an empty image", {**images, "lanes/log/empty.md": b""}),
                      ("an image that is not UTF-8", {**images, ALPHA_LOG: b"\xff\xfe\n"}),
                      ("an image that is not bytes", {**images, ALPHA_LOG: "alpha\n"}),
                      ("images that are not a dict", list(images.items()))):
        assert m.register_cache_state(bad) is None, f"register_cache_state took {what}"


# ============================================================ phase W: T240
#
# TEST 1'S PHASE-W PART (lane 2's T240; AT-1, the test plan's lines 537-645;
# FR-018, FR-027, FR-042, FR-059): each of S1's writes through `lanes-edit.sh`
# on a `mode=primary` workstation, from T203's flipped copy (`RENDER_GIT_HALF =
# True`, test 14's second state) with `lanes-edit.sh` beside it, over test 1's
# imported register (`import_to_primary`, AT-LR006's route), then the pure
# renderer writing a scratch mirror, `render --images --at <seq> --out <dir>`.
#
# THE VERBS (`W_VERBS`) are the thirteen of P192-196, `log` once per verb of
# its grammar: the fourteen arms of `lanes-edit.sh`'s write dispatch but
# `commit`, whose direct write is 2 (D10), with the argument lists the writes
# module's `WRITE_VERBS` gives them (T241), and `log` once for each verb of
# `VERB_LIST` that `log` writes by hand. That is twelve: `log` refuses CLAIMED,
# TAKEOVER, RELEASED, CLAIM-LOST, HANDOFF-REQUESTED and RENAMED, which their own
# verbs write. The lists are copied here, never imported: the writes module
# imports this one. Every verb runs from the same starting state, C with the
# verb's prep (`W_PREPS`), and each case gets a database of its own. Each
# argument list exits 0 and makes one commit in files mode on line R's
# V-round4 (line W1-12's probe).
#
# THE TWIN (AT-1, "Part W adds an FM twin"): a files-mode clone of W's origin
# at C, with its own origin and its own `$HOME`, makes the same verb. The
# mirror's render set equals the twin's origin's, path set and bytes, with
# every UTC masked in both, in a line or in a path (`migrate-state-cells`'
# archive is named by its UTC): open point 4 leaves the mask in place until a
# test can fix the database's clock. The journal entry's message is the twin's
# commit message, but `rename-lane`'s, which on primary is the message the
# design names under Q13(a) (lane 3's ruling (A), #165 6859179515).
#
# GB SECTION 4.3'S CASES (R29), each an assertion of a named test: D12, the
# fake `git`'s log holding no `fetch` on primary that the verb itself makes,
# for any verb, the renderer the write forks left out by the process above
# the call (lane 3, #165 6859073786), in the mirror case; `rename-lane`'s
# `register seq` and its tail under Q13(a), the
# transaction first and then the move, in
# `test_rename_lane_commits_the_transaction_then_a_rerun_makes_only_the_move`;
# and `start-record` in both modes, its twin run once more under
# `LANES_ROUTE_WRITES=1`, as the twin case's `[start-record]`.
#
# THE MOVE ON PRIMARY (lane 3's batch c, #165 6807881675, Q55 and Q56, B15
# texts (2) to (4) for F13d:502, :497 and :496): `rename-lane` renames one
# regular file inside its own folder and commits those two paths alone, so a
# folder's tracked bytecode never rides it (#162); a handoff whose own path has
# a cache, bytecode or environment part refuses 2 before the seam (Y:5138;
# REV422c N1). The rerun is `LANES_LANE=<new> lanes-edit.sh rename-lane <old>
# <new>` (batch c Q71 and Q74, #165 6808141050).
#
# THEY FAIL UNTIL lane 4's L4-B4 (T414's seam), L4-B8 (T422, `rename-lane`'s
# tail and its seq) and L4-B13 (T415's author, T416's fork, `<c>` and the
# nudge) land, each by its own assertion here: line R's `lanes-edit.sh` writes
# the files whatever `mode=` says. `[start-record]` fails until L4-B9 (T427)
# too, and the two `rename-lane` cases B15 adds until lane 4's T422.

#: The lanes these writes are for, each with its own checkout `<c>`,
#: `<W>-lanes/<lane>` (B14 tasks:1142's T415 bullets; R17): repoA-1 and
#: repoA-2, as `LANES_LANE` or a verb's `<lane>`, and repoA-3, `add-row`'s new
#: row and `rename-lane`'s new name (the writes module's `WRITE_LANES`).
W_LANES = ("repoA-1", "repoA-2", "repoA-3")

#: The writer's password in the 0600 `register_passfile=` (AT-1's fixture),
#: which the cluster's trust never asks for and no output may carry.
W_SECRET = "t240-never-printed-5d2a"


def _w_with_row(lane: str, sid: str, cell: str, log: str = None) -> dict:
    """A prep: test 1's SEED with one more row in `LANES.md`'s table, after
    repoA-2's, and the lane's log (its header, then `log`'s lines). Copied
    from the writes module's `_with_row`."""
    lanes = SEED["lanes/LANES.md"]
    anchor = next(line for line in lanes.split("\n") if line.startswith("| `repoA-2` |"))
    row = (f"| `{lane}` | harness `{sid}` | Eagle / test / brett | 2026-09-01T00:00Z | none "
           f"| handoffs/{lane}.md | {cell} |")
    header = f"# lane {lane} {EM} object log (lane-collision-protocol Amendment 7)\n"
    return {"lanes/LANES.md": lanes.replace(anchor + "\n", anchor + "\n" + row + "\n", 1),
            f"lanes/log/{lane}.md": header + (log or "")}


def _w_with_handoffs(handoffs: dict, extra: dict = None) -> dict:
    """A prep: test 1's SEED with each lane of `handoffs`, {lane: (path,
    bytes)}, naming the handoff at `path` in its row's handoff column, and that
    handoff committed there; and `extra`, {path: bytes}, committed beside
    them."""
    lanes = SEED["lanes/LANES.md"]
    files: dict = {}
    for lane, (path, data) in handoffs.items():
        old = next(line for line in lanes.split("\n") if line.startswith(f"| `{lane}` |"))
        assert old.count(f"| handoffs/{lane}.md |") == 1, old
        lanes = lanes.replace(old, old.replace(f"| handoffs/{lane}.md |", f"| {path} |"), 1)
        files[path] = data
    files["lanes/LANES.md"] = lanes
    files.update(extra or {})
    return files


#: The starting state three verbs need, or they refuse for want of work (2),
#: as the writes module's `PREPS` gives it: `archive-rows <repo>` moves a
#: repository's RETIRED rows, `retire-rows` takes a dormant row, and
#: `migrate-state-cells` migrates a diary cell.
W_PREPS = {
    "archive-rows": _w_with_row(
        "repoZ-2", "eeeeeeee-0002-4000-8000-00000000e002",
        f"RETIRED {DOT} 2026-09-03T00:00:00Z {DOT} retired",
        f"RETIRED {EM} lane repoZ-2, session eeeeeeee-0002-4000-8000-00000000e002@Eagle, "
        f"2026-09-03T00:00:00Z, lane:repoZ-2 {EM} retired\n"),
    "retire-rows": _w_with_row("repoA-4", "aaaaaaaa-0005-4000-8000-00000000a005",
                               f"MIGRATED {DOT} 2026-09-01T00:00:00Z {DOT} migrated"),
    "migrate-state-cells": _w_with_row("repoA-5", "aaaaaaaa-0006-4000-8000-00000000a006",
                                       f"parked 2026-09-01 {DOT} picked up 2026-09-02"),
}

#: The session `request-handoff --force` writes its `PAUSED` for, as the
#: writes module's `SID_REQUESTER`.
W_SID_REQUESTER = "bbbbbbbb-0007-4000-8000-00000000b007"

#: A lane's binding payload, for `log STARTED` and `log RESUMED`.
W_BINDING = "home opensoft/repoA; dir /work/repoA2"

#: S1's writes but `commit`, `log` once per verb of its grammar: {id: (its
#: arguments, the lane it writes as)}. The forms are `lanes-edit.sh`'s usage
#: lines at a2073eae; `log`'s are its arm's, at line R's V-round4.
#: THE LANE IT WRITES AS is the lane the write is for, D12's writing lane,
#: whose checkout `<c>` T415's `pw_checkout` takes through `write_lane_of`
#: (lane 3, #165 6869860086; lane 4, #165 6869806372): for `add-row` the new
#: row's, repoA-3, and for `request-handoff` its target's, repoA-1, as
#: `lane-start` and `lane` set `LANES_LANE` for those two verbs. For every
#: other verb the two lanes are one already.
W_VERBS = {
    "add-row": (["add-row", f"| `repoA-3` | harness `aaaaaaaa-0004-4000-8000-00000000a004` | "
                 f"Eagle / test / brett | 2026-11-10T00:00Z | none | handoffs/repoA-3.md | "
                 f"LIVE {DOT} 2026-11-10T00:00:00Z {DOT} test 1 |"], "repoA-3"),
    "append-line": (["append-line", f"HOLD {EM} lane repoA-2 ({WS}), window w, "
                     f"2026-11-10T00:00:00Z: opensoft/repoB main {TIP} for test 1"], "repoA-2"),
    "append-session-id": (["append-session-id", "repoA-2", f"harness `{SID_A2}`",
                           " (test 1)"], "repoA-2"),
    "archive-rows": (["archive-rows", "repoZ", "--yes"], "repoA-2"),
    "claim": (["claim", "opensoft/repoA#9", "--no-github"], "repoA-2"),
    "log-closed": (["log", "CLOSED", "opensoft/repoA#9", "closed for test 1"], "repoA-2"),
    "log-opened": (["log", "OPENED", "opensoft/repoA#8", "test 1's PR"], "repoA-2"),
    "log-landing": (["log", "LANDING", "opensoft/repoA#8", "test 1"], "repoA-2"),
    "log-landed": (["log", "LANDED", "opensoft/repoA#8", ARROW, "abc1234"], "repoA-2"),
    "log-withdrawn": (["log", "WITHDRAWN", "opensoft/repoA#8", "test 1"], "repoA-2"),
    "log-started": (["log", "STARTED", "lane:repoA-2", ARROW, W_BINDING], "repoA-2"),
    "log-paused": (["log", "PAUSED", "lane:repoA-1", "parked for test 1"], "repoA-1"),
    "log-resumed": (["log", "RESUMED", "lane:repoA-2", ARROW, W_BINDING], "repoA-2"),
    "log-ended": (["log", "ENDED", "lane:repoA-1", "ended for test 1"], "repoA-1"),
    "log-retired": (["log", "RETIRED", "lane:repoA-1", "retired for test 1"], "repoA-1"),
    "log-noted": (["log", "NOTED", "lane:repoA-2", "test 1's note"], "repoA-2"),
    "log-ruled": (["log", "RULED", "lane:repoA-2", ARROW, "opensoft/repoA#9",
                   "the words, verbatim"], "repoA-2"),
    "migrate-state-cells": (["migrate-state-cells", "--yes"], "repoA-2"),
    "release": (["release", "opensoft/repoA#7", "test 1", "--no-github"], "repoA-1"),
    "rename-lane": (["rename-lane", "repoA-2", "repoA-3", "test 1", "--no-github"], "repoA-2"),
    "replace-in-row": (["replace-in-row", "repoA-2", "parked", "parked for test 1"], "repoA-2"),
    "request-handoff": (["request-handoff", "repoA-1", "--force", "test 1", "--session",
                         W_SID_REQUESTER], "repoA-1"),
    "retire-rows": (["retire-rows", "repoA-4", "--reason", "test 1"], "repoA-2"),
    "set-row-state": (["set-row-state", "repoA-2", f"PAUSED {DOT} test 1"], "repoA-2"),
}

#: The twin's verbs: `W_VERBS`, and GB section 4.3's `start-record`, lane 4's
#: T427 verb (L4-B9), as a resume of repoA-2, which `LANES_SESSION` names by
#: its transcript uuid and `LANES_LANE` by the row's own spelling (B14
#: tasks:1325-1333): {id: (its arguments, the lane, what the run adds to the
#: environment)}.
TWIN_VERBS = {**{verb: (argv, lane, {}) for verb, (argv, lane) in W_VERBS.items()},
              "start-record": (["start-record", "repoA-2", "RESUMED", "--state",
                                f"LIVE {DOT} resumed for test 1", "--log", "lane:repoA-2",
                                ARROW, W_BINDING], "repoA-2", {"LANES_SESSION": SID_A2})}


def _logging_git(path: Path, log: Path, real: str = None) -> None:
    """A `git` at `path` that appends each call to `log`, then runs the real
    `git` (or `real`) with its arguments (D12's oracle: GB section 4.3, "the
    fake `git`'s log"). A call is one record, written by one `printf`, so a
    forked renderer's calls and the verb's never interleave: the pid above
    the call; where any argument is `fetch` or `pull`, that process's command
    line, as open point 8's wrapper reads it (`ps -ww -o command=`; TP:8799-8800,
    test 5's wrapper in `test_sql_register_renderer_git.py`), and the
    directory the call runs in; then its arguments. Each field is ended by a
    US (0x1f) and the record by an RS (0x1e) and a LF."""
    real = real or shutil.which("git")
    assert real, "no git on PATH"
    path.write_text("#!/bin/sh\n"
                    "u='\x1f' above=$PPID command= here=\n"
                    "for a in \"$@\"; do case $a in fetch|pull)\n"
                    "  command=$(ps -ww -o command= -p \"$above\" 2>/dev/null"
                    " | tr '\\n\\036\\037' '   ')\n"
                    "  here=$PWD; break ;; esac; done\n"
                    "record=\"$above$u$command$u$here$u\"\n"
                    "for a in \"$@\"; do record=\"$record$a$u\"; done\n"
                    f"printf '%s\\036\\n' \"$record\" >> {shlex.quote(str(log))}\n"
                    f"exec {shlex.quote(real)} \"$@\"\n", encoding="utf-8")
    path.chmod(0o755)


#: `git`'s own options that take the next argument as their value.
_GIT_VALUE_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                                "--exec-path", "--super-prefix", "--config-env"})


def _render_checkout(command: str):
    """The `<c>` of a `lanes-index render --checkout <c>` command line, the
    renderer a write forks (`pw_render_fork`, T416), or None for any other
    process."""
    words = command.split()
    for i in range(len(words) - 3):
        if (words[i].rsplit("/", 1)[-1] == "lanes-index"
                and words[i + 1:i + 3] == ["render", "--checkout"]):
            return words[i + 3]
    return None


def _git_calls(log: Path) -> list:
    """`_logging_git`'s log: each call as a dict, its subcommand (`sub`, the
    first argument that is not one of `git`'s own options or such an
    option's value), its arguments (`args`), the pid above it (`above`), and,
    for a `fetch` or a `pull`, the `<c>` of the `lanes-index render
    --checkout` process above it, or None (`render`), and the real path of
    the repository it ran in, its directory moved by each `-C` (`where`)."""
    if not log.exists():
        return []
    calls = []
    for record in log.read_bytes().decode("utf-8", "replace").split("\x1e\n"):
        if not record:
            continue
        above, command, here, *args = record.split("\x1f")[:-1]
        i = 0
        where = here
        while i < len(args) and args[i].startswith("-"):
            if args[i] == "-C" and i + 1 < len(args):
                where = os.path.join(where, args[i + 1])
            i += 2 if args[i] in _GIT_VALUE_OPTIONS else 1
        calls.append({"sub": args[i] if i < len(args) else "", "args": args, "above": above,
                      "render": _render_checkout(command),
                      "where": os.path.realpath(where) if here else ""})
    return calls


def _d12_control(root: Path, checkout: str) -> None:
    """D12's control: the render pass's own fetch argv (`lanes-index`'s
    `render_pass`, step 1), in `checkout`, logged by `_logging_git` with
    `true` for `git`, so nothing is fetched. Once from this test, which is
    no renderer: kept, as a fetch of the verb's would be. Once from a
    stand-in whose command line is `lanes-index render --checkout
    <checkout>`: left out, with its `<c>`. The same argv both times, so the
    two are told apart by the process above the call alone."""
    root.mkdir(parents=True, exist_ok=True)
    log, shim, stand_in = root / "git-calls.log", root / "git", root / "lanes-index"
    _logging_git(shim, log, real=shutil.which("true"))
    stand_in.write_text("#!/bin/sh\nshift 4\n\"$D12_SHIM\" \"$@\"\nexit $?\n",
                        encoding="utf-8")
    stand_in.chmod(0o755)
    argv = ["-C", checkout, "-c", "gc.auto=0", "-c", "maintenance.auto=false", "fetch",
            "--no-tags", "--no-write-fetch-head", "--no-recurse-submodules", "-q", "origin",
            "+refs/heads/main:refs/remotes/origin/main"]
    env = dict(os.environ, D12_SHIM=str(shim))
    for command in ([str(shim), *argv],
                    [str(stand_in), "render", "--checkout", checkout, "--", *argv]):
        done = subprocess.run(command, cwd=str(root), env=env, capture_output=True,
                              timeout=60, check=False)
        assert done.returncode == 0, f"the D12 control's {command[0]}: {done.stderr!r}"
    got = [(call["sub"], call["args"], call["render"], call["where"])
           for call in _git_calls(log)]
    assert got == [("fetch", argv, None, checkout), ("fetch", argv, checkout, checkout)], (
        f"the D12 control: the renderer's fetch argv run by no renderer must be kept, "
        f"and under a `lanes-index render --checkout` left out: {got}")


def _git_bytes(cwd: Path, env: dict, *args: str) -> bytes:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, env=env,
                          check=False)
    assert proc.returncode == 0, f"git {' '.join(args)} in {cwd}: {proc.stderr!r}"
    return proc.stdout


def _origin_render_set(origin: Path, env: dict, ref: str = "main") -> dict:
    """The render set on a bare repository's `ref`, read by object: {path:
    bytes}."""
    names = _git_bytes(origin, env, "ls-tree", "-r", "-z", "--name-only", ref, "--", "lanes")
    return {name: _git_bytes(origin, env, "cat-file", "blob", f"{ref}:{name}")
            for name in names.decode("utf-8").split("\0") if name and RENDER_SET.match(name)}


def _origin_paths(origin: Path, env: dict, ref: str = "main", where: str = ".") -> dict:
    """Every path under `where` on a bare repository's `ref`, to its blob."""
    out = _git_bytes(origin, env, "ls-tree", "-r", "-z", ref, "--", where).decode("utf-8")
    found = {}
    for entry in out.split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            found[path] = meta.split()[2]
    return found


def _raw_message(origin: Path, env: dict, ref: str = "main") -> str:
    """A commit's message as git stores it, every byte after the header."""
    raw = _git_bytes(origin, env, "cat-file", "commit", ref)
    return raw.split(b"\n\n", 1)[1].decode("utf-8") if b"\n\n" in raw else ""


#: A UTC in any form a register file spells it: whole minutes (a row's
#: `started` cell), whole seconds, or with a fraction (Q4(d)(i)).
_UTC_ANY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?Z")
_UTC_ANY_BYTES = re.compile(_UTC_ANY.pattern.encode("ascii"))


def _utc_masked(files: dict) -> dict:
    """`files`, {path: bytes}, with every UTC masked, in each path and in
    each file's bytes (AT-1's twin oracle; open point 4)."""
    return {_UTC_ANY.sub("<utc>", path): _UTC_ANY_BYTES.sub(b"<utc>", data)
            for path, data in files.items()}


def _first_difference(ours: bytes, theirs: bytes) -> str:
    a = ours.decode("utf-8", "replace").split("\n")
    b = theirs.decode("utf-8", "replace").split("\n")
    for n, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            return f"line {n}: {x!r} != {y!r}"
    return f"{len(a)} lines != {len(b)} lines"


def _assert_same_files(ours: dict, theirs: dict, what: str) -> None:
    assert sorted(ours) == sorted(theirs), (
        f"{what}: the path sets differ: only ours {sorted(set(ours) - set(theirs))}, only "
        f"theirs {sorted(set(theirs) - set(ours))}")
    for name in sorted(ours):
        assert ours[name] == theirs[name], (
            f"{what}: {name}'s bytes differ, {_first_difference(ours[name], theirs[name])}")


def _stamped_utcs(before: dict, after: dict, argv: list) -> list:
    """Each UTC in whole seconds or finer that a write put on a line of the
    render set, (path, line, utc): one not already anywhere in the register
    before it, and not one the caller typed. A UTC in whole minutes is a row's
    `started` cell, never a write's clock. For `migrate-state-cells` alone
    (`argv[0]`), nor is a minute already in the register with `:00` added,
    which that verb writes on primary for an entry's minute-only time or its
    row's `started` cell; no other verb adds it (design.md:5114 at
    `8e8d1b49`; `44f487d1:lanes-edit.sh:23907-23922`, its arm's `msc_eutc`;
    lane 3, #165 6859073786). Any other verb's `:00` UTC is still checked
    against the clock, though its minute was in the register."""
    old = set(_UTC_ANY.findall("\n".join(d.decode("utf-8", "replace") for d in before.values())))
    typed = set(_UTC_ANY.findall(" ".join(argv)))
    minute_kept = argv[0] == "migrate-state-cells"
    found = []
    for path, data in sorted(after.items()):
        lines_before = set(before.get(path, b"").decode("utf-8", "replace").split("\n"))
        for line in data.decode("utf-8", "replace").split("\n"):
            if line in lines_before:
                continue
            for utc in _UTC_ANY.findall(line):
                if (utc.count(":") == 2 and utc not in old and utc not in typed
                        and not (minute_kept and utc.endswith(":00Z")
                                 and utc[:-4] + "Z" in old)):
                    found.append((path, line, utc))
    return found


class PrimaryWrites:
    """AT-1's part-W workstation over the test's database, a copy of the
    writes module's `RegisterWorkstation` (that module imports this one): the
    files-mode workspace of the sync case (`workspace`) at C, the case's prep
    committed and pushed first; C imported and brought to `primary` with the
    marker `present` (`import_to_primary`, AT-LR006's route); T203's flipped
    copy with `lanes-edit.sh` beside it; a 0600 `lanes-index.conf` with
    `mode=primary`, both URLs naming the cluster's socket as this module's
    logins, and a 0600 `register_passfile=`; `<c>` for each of `W_LANES`, a
    clone of origin; and first on `PATH`, T203's `psql` shim, which hands each
    call to the cluster's `psql` and logs it, and `_logging_git`.
    `marker_on_origin`, which only part G sets, puts the cutover's marker
    commit on origin's `main` before `record_marker` (`import_to_primary`),
    so each `<c>` is cloned at it; every other case keeps a made-up marker
    sha and an origin at C (T270's line, tasks:2477)."""

    def __init__(self, pg, tmp_path: Path, prep: dict = None,
                 marker_on_origin: bool = False):
        self.pg = pg
        self.fakebin = tmp_path / "fakebin"
        self.fakebin.mkdir(parents=True, exist_ok=True)
        (self.fakebin / "psql").write_text(PSQL_SHIM, encoding="utf-8")
        (self.fakebin / "psql").chmod(0o755)
        (self.fakebin / PSQL_SHIM_CONTROL).write_text(json.dumps({"psql": pg.psql_bin}),
                                                      encoding="utf-8")
        self.git_log = tmp_path / "git-calls.log"
        _logging_git(self.fakebin / "git", self.git_log)
        self.estate, self.env, _source = workspace(tmp_path / "ws", self.fakebin)
        if prep:
            self._prep(prep)
        ensure_logins(pg)
        self.copy = flipped(tmp_path)
        self.lanes_edit = self.copy.parent / "lanes-edit.sh"
        conf_dir = tmp_path / "conf"
        conf_dir.mkdir()
        passfile = conf_dir / "pgpass"
        passfile.write_text(f"*:*:*:{LOGIN_WRITER}:{W_SECRET}\n", encoding="utf-8")
        passfile.chmod(0o600)
        self.conf = primary_config(conf_dir / "lanes-index.conf", pg.url(LOGIN_WRITER),
                                   pg.url(LOGIN_READER), passfile)
        self.env.update(LANES_INDEX_CONFIG=str(self.conf))
        self.env.pop("LANES_INDEX", None)
        #: The environment the pure renderer and `status` run in.
        self.index = index_env(tmp_path, self.conf, self.estate.home)
        self.imported = import_to_primary(pg, self.estate, marker_on_origin)
        for lane in W_LANES:
            self.make_lane_checkout(lane)

    def _prep(self, files: dict) -> None:
        """`files` ({path: text or bytes}) written over the checkout,
        committed and pushed, so the case starts from them; C is that
        commit."""
        estate = self.estate
        for path, data in files.items():
            target = estate.checkout / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        git(estate.checkout, "add", "-A", env=estate.env)
        git(estate.checkout, "commit", "-q", "-m", "C': the case's starting state",
            env=estate.env)
        git(estate.checkout, "push", "-q", "origin", "main", env=estate.env)
        estate.files.update({p: d for p, d in files.items() if isinstance(d, str)})
        estate.c = git(estate.checkout, "rev-parse", "HEAD", env=estate.env).strip()
        estate.lanes_tree = git(estate.checkout, "rev-parse", f"{estate.c}:lanes",
                                env=estate.env).strip()

    def lane_checkout(self, lane: str) -> Path:
        """`<c>`, `<W>-lanes/<lane>`, W being the real path of
        `workspace.yaml`'s `path:` (Amendment 23 S1)."""
        real = Path(os.path.realpath(self.estate.checkout))
        return real.parent / f"{real.name}-lanes" / lane

    def make_lane_checkout(self, lane: str) -> Path:
        target = self.lane_checkout(lane)
        target.parent.mkdir(parents=True, exist_ok=True)
        git(target.parent, "clone", "-q", str(self.estate.origin), str(target),
            env=self.estate.env)
        return target

    def checkouts(self) -> list:
        """W's checkout and each lane's `<c>`."""
        return [self.estate.checkout, *(self.lane_checkout(lane) for lane in W_LANES)]

    def run(self, argv: list, lane: str, **extra) -> subprocess.CompletedProcess:
        """`lanes-edit.sh <argv>` in W's checkout, as lane `lane`."""
        env = dict(self.env, LANES_LANE=lane, **extra)
        return subprocess.run(["bash", str(self.lanes_edit), *argv], capture_output=True,
                              encoding="utf-8", errors="replace", env=env, timeout=120,
                              cwd=str(self.estate.checkout), check=False,
                              stdin=subprocess.DEVNULL)

    def shim_calls(self) -> list:
        log = self.fakebin / PSQL_SHIM_LOG
        if not log.exists():
            return []
        entries = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x]
        return [e for e in entries if e.get("kind") != "version"]

    def commit_calls(self) -> list:
        return [c for c in self.shim_calls() if "commit_write(" in (c.get("stdin") or "")]

    def git_calls(self) -> list:
        return _git_calls(self.git_log)


class FilesTwin:
    """AT-1's twin: a files-mode clone of W's origin at C, "under its own
    `$HOME`", with an origin of its own, a bare clone of W's, so its push
    moves nothing the primary case reads, and the environment `workspace`
    sets, with no `lanes-index.conf`: `lanes-edit.sh` beside the flipped copy
    asks its mode, and `files` answers. Made before the primary write, so it
    is at C whatever a forked render pushes to W's origin. A `routed` twin
    runs under `LANES_ROUTE_WRITES=1` with `LANES_REPO` unset, so each write
    goes through its lane's own checkout, `<W>-lanes/<lane>`, made on first
    use: an explicit `LANES_REPO` naming W is refused there (Amendment 23 S2,
    S5; `f9e1449c:lanes-edit.sh:28132-28160`; lane 3, #165 6859073786). The
    lane is named by `LANES_LANE`, as `run` sets it."""

    def __init__(self, root: Path, estate: Estate, lanes_edit: Path, routed: bool = False):
        self.root = root
        self.home = root / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.git_env = git_env(self.home)
        self.origin = root / "origin.git"
        self.checkout = root / "checkout"
        git(root, "clone", "-q", "--bare", str(estate.origin), str(self.origin),
            env=self.git_env)
        git(root, "clone", "-q", str(self.origin), str(self.checkout), env=self.git_env)
        self.c = git(self.origin, "rev-parse", "main", env=self.git_env).strip()
        assert self.c == estate.c, "the twin is not at C"
        agents = self.home / ".agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.checkout}\n", encoding="utf-8")
        fakebin = root / "fakebin"
        fakebin.mkdir(parents=True, exist_ok=True)
        (fakebin / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (fakebin / "tmux").chmod(0o755)
        for d in ("state", "config", "tmp"):
            (root / d).mkdir(parents=True, exist_ok=True)
        self.env = dict(self.git_env)
        self.env.update(AGENT_PROTOCOL_ROOT=str(agents), TMPDIR=str(root / "tmp"),
                        XDG_STATE_HOME=str(root / "state"),
                        XDG_CONFIG_HOME=str(root / "config"),
                        CLAUDE_CONFIG_DIR=str(self.home / ".claude"), LANES_WORKSTATION=WS,
                        LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none",
                        LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1",
                        LANES_REPO=str(self.checkout),
                        PATH=str(fakebin) + os.pathsep + _masked_path())
        self.env.pop("LANES_INDEX", None)
        self.env.pop("LANES_INDEX_CONFIG", None)
        if routed:
            self.env.pop("LANES_REPO")
            self.env.update(LANES_ROUTE_WRITES="1")
        self.lanes_edit = lanes_edit

    def run(self, argv: list, lane: str, **extra) -> subprocess.CompletedProcess:
        env = dict(self.env, LANES_LANE=lane, **extra)
        return subprocess.run(["bash", str(self.lanes_edit), *argv], capture_output=True,
                              encoding="utf-8", errors="replace", env=env, timeout=120,
                              cwd=str(self.checkout), check=False, stdin=subprocess.DEVNULL)

    def commits(self) -> list:
        """The commits the twin pushed since C, oldest first."""
        out = git(self.origin, "rev-list", "--reverse", f"{self.c}..main", env=self.git_env)
        return out.split()

    def render_set(self) -> dict:
        return _origin_render_set(self.origin, self.git_env)

    def message(self) -> str:
        return _raw_message(self.origin, self.git_env)


#: Files mode's `rename-lane` subject, "... the row, <log>, the handoff and
#: <aliases> in one commit" (`f9e1449c:lanes-edit.sh:30289`).
_RENAME_FILES_SUBJECT = re.compile(
    r"^(LANES\(\S+\): RENAMED lane .+ the row, )(\S+), the handoff and (\S+) in one commit$",
    re.M)


def _primary_message(verb: str, message: str) -> str:
    """The journal message a primary write of `verb` composes, from its
    files-mode twin's commit `message`: the same, but `rename-lane`'s, whose
    handoff is not in the entry (Q13(a)), so T422 composes "... the row,
    <log> and <aliases> in one register write; the handoff's move and stamp
    follow in the lane's checkout (Q13(a))" (`f9e1449c:lanes-edit.sh:30293-30294`),
    the message the design names (lane 3's ruling (A), #165 6859179515)."""
    if verb != "rename-lane":
        return message
    named, n = _RENAME_FILES_SUBJECT.subn(
        r"\1\2 and \3 in one register write; the handoff's move and stamp follow in "
        r"the lane's checkout (Q13(a))", message, count=1)
    assert n == 1, f"rename-lane: the twin's message has no files-mode subject: {message!r}"
    return named


def _journal_since(db, seq: int) -> list:
    return rows(db, f"SELECT seq, write_id, kind, verb, lane, message FROM journal "
                    f"WHERE seq > {seq} ORDER BY seq")


def _one_entry(db, before: int, proc: subprocess.CompletedProcess, what: str) -> dict:
    """A write on primary that exited 0, and its one journal entry, at the old
    head plus one."""
    assert proc.returncode == 0, (
        f"{what} on primary exited {proc.returncode} (L4-B4, L4-B8, L4-B13): "
        f"{proc.stderr[-800:]}")
    new = _journal_since(db, before)
    assert len(new) == 1 and new[0]["seq"] == before + 1, (
        f"{what} on primary added {len(new)} journal entries after seq {before}, not one at "
        f"{before + 1}: line R's lanes-edit.sh writes the files whatever mode= says (L4-B4, "
        f"T414's seam): {new}")
    return new[0]


def _rows_written_at(db, seq: int) -> list:
    """Every register row whose last writer is the entry at `seq`, with the
    mode it records: part N's five tables."""
    return rows(db, f"SELECT 'doc_lines' AS t, written_mode AS m FROM doc_lines "
                    f"WHERE written_seq = {seq} "
                    f"UNION ALL SELECT 'lanes', last_mode FROM lanes WHERE last_seq = {seq} "
                    f"UNION ALL SELECT 'log_lines', mode FROM log_lines WHERE seq = {seq} "
                    f"UNION ALL SELECT 'register_lines', mode FROM register_lines "
                    f"WHERE seq = {seq} "
                    f"UNION ALL SELECT 'object_holds', mode FROM object_holds WHERE seq = {seq}")


def _mirror(ws: PrimaryWrites, seq: int, out_dir: Path) -> dict:
    """The pure renderer's scratch mirror at `seq`, its render set: {path:
    bytes}. It writes nothing outside its four paths (and `lanes/STORE`)."""
    proc, images = render_images(ws.copy, ws.index, seq, out_dir)
    assert proc.returncode == 0, f"render --images --at {seq} exited {proc.returncode}: " \
                                 f"{proc.stderr}"
    assert all(RENDER_SET.match(p) or p == STORE_PATH for p in images), (
        f"the renderer wrote outside its four paths: {sorted(images)}")
    return _rendered_only(images)


@pytest.mark.parametrize("verb", list(W_VERBS))
def test_each_write_leaves_the_mirror_byte_identical_to_a_full_render(pg, tmp_path, verb):
    """AT-1's part W, the mirror: `lanes-edit.sh <verb>` on primary exits 0;
    the journal gains exactly one entry, at the old head plus one, with a
    `write_id` unique in the journal; the pure renderer's scratch mirror at
    that seq equals the full render from SQL (`render_file` of every path in
    `files`), path set and bytes, over `lanes/LANES.md`, `lanes/log/*.md`,
    `lanes/aliases.tsv` and `lanes/archive/**`, and holds nothing outside
    them; the write changed a rendered file; each UTC the write put on a line
    is the database's, in whole seconds, between its clock read before the
    write and after it (S6; D13). And D12 (GB section 4.3): the fake `git`'s
    log holds no `fetch` (nor a `pull`) on primary that the verb itself
    makes, for any verb. The renderer the write forks fetches origin, as each
    pass does (Y:2839; AT-C8, TP:3187-3188), so a call with a `lanes-index
    render --checkout` process above it is left out, by that process, never
    by the call's argv, since the pass's read-back fetch has the same argv;
    each one left out ran in the writing lane's checkout (lane 3, #165
    6859073786). A control shows the test tells them apart by process. Fails
    until L4-B4, L4-B8 and L4-B13."""
    argv, lane = W_VERBS[verb]
    ws = PrimaryWrites(pg, tmp_path, W_PREPS.get(verb))
    before_head = head(pg)
    before_ids = {r["write_id"] for r in rows(pg, "SELECT write_id FROM journal")}
    before = _rendered_only(full_render(pg))
    clock_before = db_clock(pg)
    proc = ws.run(argv, lane)
    clock_after = db_clock(pg)
    entry = _one_entry(pg, before_head, proc, verb)
    seq = entry["seq"]
    assert entry["write_id"] and entry["write_id"] not in before_ids, entry
    assert rows(pg, f"SELECT count(*) AS n FROM journal "
                    f"WHERE write_id = '{entry['write_id']}'") == [{"n": 1}]

    # THE MIRROR: the scratch mirror at seq is the full render from SQL.
    mirror = _mirror(ws, seq, tmp_path / "mirror")
    full = _rendered_only(full_render(pg))
    _assert_same_files(mirror, full, f"{verb}: the mirror at seq {seq} and the full render")
    assert mirror != before, f"{verb} changed no rendered file"

    # THE UTC: the database's clock, in whole seconds.
    for path, line, utc in _stamped_utcs(before, mirror, argv):
        assert UTC_RE.match(utc), f"{verb} wrote {utc!r}, not whole seconds, in {path}: {line!r}"
        assert clock_before <= epoch_of(utc) <= clock_after, (
            f"{verb} wrote {utc} in {path}, outside the database's clock "
            f"[{utc_of(clock_before)}, {utc_of(clock_after)}]: {line!r}")

    # D12: NO FETCH ON PRIMARY BY THE VERB ITSELF. The forked renderer's own
    # fetches are left out by the process above them, each in the writing
    # lane's checkout.
    fetches = [call for call in ws.git_calls() if call["sub"] in ("fetch", "pull")]
    own = [call["args"] for call in fetches if call["render"] is None]
    assert own == [], f"{verb} fetched on primary (D12): {own}"
    checkout = os.path.realpath(ws.lane_checkout(lane))
    astray = [call for call in fetches
              if os.path.realpath(call["render"]) != checkout or call["where"] != checkout]
    assert astray == [], (
        f"{verb}: its forked renderer fetched outside the writing lane's checkout "
        f"{checkout} (D12): {astray}")
    _d12_control(tmp_path / "d12-control", checkout)


@pytest.mark.parametrize("verb", list(TWIN_VERBS))
def test_each_write_matches_its_files_mode_twin_byte_for_byte(pg, tmp_path, verb):
    """AT-1's part W, the twin: `lanes-edit.sh <verb>` on primary exits 0 with
    one journal entry; its files-mode twin, a clone of W's origin at C under
    its own `$HOME`, makes the same verb, exits 0 and pushes one commit; the
    scratch mirror at the entry's seq equals the render set on the twin's
    origin, path set and bytes, every UTC masked in both (open point 4); and
    the entry's message is the twin's commit message, byte for byte, or but
    for the one LF git ends a stored message with; for `rename-lane`, the
    message the design names under Q13(a), `_primary_message`'s. GB section 4.3's
    `start-record` (lane 4's T427, L4-B9) is `[start-record]`, a resume of
    repoA-2 in both modes, whose twin runs once more, in a second clone at C,
    under `LANES_ROUTE_WRITES=1` with `LANES_REPO` unset, through the lane's
    own checkout (Amendment 23 S2, S5), with the same render set and message. Fails
    until L4-B4, L4-B8 and L4-B13; `[start-record]` until L4-B9 too."""
    argv, lane, extra = TWIN_VERBS[verb]
    ws = PrimaryWrites(pg, tmp_path, W_PREPS.get(verb))
    twin = FilesTwin(tmp_path / "twin", ws.estate, ws.lanes_edit)
    routed = (FilesTwin(tmp_path / "twin-routed", ws.estate, ws.lanes_edit, routed=True)
              if verb == "start-record" else None)
    before_head = head(pg)
    proc = ws.run(argv, lane, **extra)
    entry = _one_entry(pg, before_head, proc, verb)
    mirror = _mirror(ws, entry["seq"], tmp_path / "mirror")

    for label, files_twin in (("the twin", twin), ("the routed twin", routed)):
        if files_twin is None:
            continue
        done = files_twin.run(argv, lane, **extra)
        assert done.returncode == 0, (
            f"{label}'s {verb} in files mode exited {done.returncode}: {done.stderr[-800:]}")
        assert len(files_twin.commits()) == 1, (
            f"{label}'s {verb} pushed {len(files_twin.commits())} commits, not one")
        _assert_same_files(_utc_masked(mirror), _utc_masked(files_twin.render_set()),
                           f"{verb}: the mirror and {label}'s files, every UTC masked")
        message = _primary_message(verb, files_twin.message())
        bare = message[:-1] if message.endswith("\n") else message
        assert entry["message"] in (message, bare), (
            f"{verb}: the journal's message {entry['message']!r} is not {label}'s commit "
            f"message, as primary composes it, {message!r}")


@pytest.mark.parametrize("verb", list(W_VERBS))
def test_each_write_reads_back_primary_as_the_mode_that_wrote_it_last(pg, tmp_path, verb):
    """AT-1's part W, the rows (P183-188): after `lanes-edit.sh <verb>` on
    primary exits 0 with one journal entry, every register row that entry
    wrote last (`doc_lines`, `lanes`, `log_lines`, `register_lines` and
    `object_holds`, by its seq) reads `primary` as the mode that wrote it,
    and there is at least one. Fails until L4-B4, L4-B8 and L4-B13."""
    argv, lane = W_VERBS[verb]
    ws = PrimaryWrites(pg, tmp_path, W_PREPS.get(verb))
    before_head = head(pg)
    proc = ws.run(argv, lane)
    entry = _one_entry(pg, before_head, proc, verb)
    touched = _rows_written_at(pg, entry["seq"])
    assert touched, f"{verb}'s entry at seq {entry['seq']} wrote no register row"
    assert {r["m"] for r in touched} == {"primary"}, (
        f"{verb}'s rows do not all read primary as the mode that wrote them last: {touched}")


#: AT-1's `rename-lane` handoffs: a handoff named for its lane, under its
#: estate's folder, as `lane-start` computes it, and where the rename moves it.
RL_HANDOFF = "handoffs/eagle/session-handoff-2026-10-01-lane-repoA-2.md"
RL_MOVED = "handoffs/eagle/session-handoff-2026-10-01-lane-repoA-3.md"
#: A handoff Rule 3's stamp can go into: a header line, a blank line, a body.
RL_TEXT = b"# handoff of lane repoA-2\n\nwhat the lane left\n"
#: A handoff that cannot take the stamp without a byte of it rewritten: one
#: line and no LF, so the stamp would join its only line.
RL_UNSTAMPABLE = ("handoffs/eagle/session-handoff-2026-10-01-lane-repoA-1.md",
                  b"# handoff of lane repoA-1, with no LF")
#: The rename's arguments, its old lane and its new.
RL_ARGV = ["rename-lane", "repoA-2", "repoA-3", "test 1", "--no-github"]


def _rl_stamped(old: bytes, new: bytes) -> bool:
    """`new` is `old` with exactly one line put in, which names both lanes:
    Rule 3's stamp (Amendment 16(d))."""
    a, b = old.split(b"\n"), new.split(b"\n")
    return len(b) == len(a) + 1 and any(
        b[:i] + b[i + 1:] == a and b"repoA-2" in b[i] and b"repoA-3" in b[i]
        for i in range(len(b)))


def test_rename_lane_commits_the_transaction_then_a_rerun_makes_only_the_move(pg, tmp_path):
    """AT-1's part W, Brett's row 18 (comment 6721583757), with GB section
    4.3's `rename-lane` cases (R29): on primary the transaction comes first,
    and the handoff's move and Rule 3 stamp follow it as the verb's
    after-COMMIT tail (Q13(a); Y:5092; B14 tasks:1270-1279).

    A HANDOFF THAT CANNOT BE STAMPED refuses before anything is sent (Y:5138):
    repoA-1's, one line with no LF; its rename exits non-zero with no commit
    call, the journal and origin as they were.

    THEN repoA-2's, with the move made to fail after the commit (its folder in
    repoA-2's `<c>` read-only): the rename exits 0 with one WARNING, the move
    owed; it prints `register seq <s>`, the entry's seq; the journal holds the
    rename once; the handoff paths left the change set (no `handoffs/` path
    among the entry's files), and the row's handoff column names the new path
    in the transaction; origin still holds the handoff at its old path. A
    rerun, `LANES_LANE=repoA-3 lanes-edit.sh rename-lane repoA-2 repoA-3`
    (batch c Q71 and Q74), exits 0, adds no journal entry, and makes the move:
    origin holds the handoff at the new path, stamped, and not at the old.
    Fails until L4-B8 (lane 4's T422), L4-B4 and L4-B13."""
    prep = _w_with_handoffs({"repoA-2": (RL_HANDOFF, RL_TEXT), "repoA-1": RL_UNSTAMPABLE})
    ws = PrimaryWrites(pg, tmp_path, prep)
    origin, env = ws.estate.origin, ws.estate.env

    # A HANDOFF THAT CANNOT BE STAMPED: refused before anything is sent.
    before_head, refs = head(pg), _origin_paths(origin, env)
    refused = ws.run(["rename-lane", "repoA-1", "repoA-9", "test 1", "--no-github"], "repoA-1")
    assert refused.returncode != 0, (
        f"a rename of a handoff that cannot take Rule 3's stamp exited 0 (Y:5138): "
        f"{refused.stderr[-800:]}")
    assert ws.commit_calls() == [], f"the refusal sent a commit call: {ws.commit_calls()}"
    assert head(pg) == before_head and _origin_paths(origin, env) == refs

    # THE MOVE MADE TO FAIL AFTER THE COMMIT.
    folder = ws.lane_checkout("repoA-2") / Path(RL_HANDOFF).parent
    folder.chmod(0o555)
    try:
        if os.access(str(folder), os.W_OK):
            pytest.skip("this user writes into a read-only directory, so the move cannot be "
                        "made to fail")
        first = ws.run(RL_ARGV, "repoA-2")
    finally:
        folder.chmod(0o755)
    entry = _one_entry(pg, before_head, first, "rename-lane, its move made to fail")
    said = first.stdout + first.stderr
    assert re.search(rf"\bregister seq {entry['seq']}\b", said), (
        f"rename-lane on primary did not print `register seq {entry['seq']}`: {said[-800:]}")
    assert first.stderr.count("WARNING") == 1, (
        f"a failed move ends 0 with ONE WARNING, the move owed: {first.stderr[-1200:]}")
    entry_files = rows(pg, f"SELECT path FROM journal_files WHERE seq = {entry['seq']}")
    assert not [r for r in entry_files if r["path"].startswith("handoffs/")], (
        f"the handoff paths did not leave the change set: {entry_files}")
    lanes_md = _rendered_only(full_render(pg))["lanes/LANES.md"].decode("utf-8")
    row = next((line for line in lanes_md.split("\n") if line.startswith("| `repoA-3`")), "")
    assert f"| {RL_MOVED} |" in row, f"the row's handoff column is not the new path: {row!r}"
    paths = _origin_paths(origin, env)
    assert RL_HANDOFF in paths and RL_MOVED not in paths, (
        "the failed move reached origin, or the handoff left its old path")

    # THE RERUN: no entry, only the move.
    again = ws.run(RL_ARGV, "repoA-3")
    assert again.returncode == 0, f"the rerun exited {again.returncode}: {again.stderr[-800:]}"
    assert _journal_since(pg, entry["seq"]) == [], "the rerun added a journal entry"
    paths = _origin_paths(origin, env)
    assert RL_MOVED in paths and RL_HANDOFF not in paths, (
        f"the rerun did not make the move on origin: "
        f"{sorted(p for p in paths if p.startswith('handoffs/'))}")
    moved = _git_bytes(origin, env, "cat-file", "blob", f"main:{RL_MOVED}")
    assert _rl_stamped(RL_TEXT, moved), f"the moved handoff is not stamped: {moved!r}"


def test_a_caller_composed_utc_and_log_paused_utc_stay_as_written(pg, tmp_path):
    """AT-1's part W: a UTC the caller wrote into the line, `append-line`'s
    `HOLD` line, and `log PAUSED --utc`'s, Amendment 17's late PAUSED, are
    stored and rendered byte for byte, never replaced by the database's
    clock: after each write on primary (exit 0, one journal entry), the line
    is in `doc_lines`, in the full render from SQL and in the scratch mirror
    at the entry's seq, carrying the caller's UTC, which is not the
    database's clock. Fails until L4-B4, L4-B8 and L4-B13."""
    ws = PrimaryWrites(pg, tmp_path)
    hold = (f"HOLD {EM} lane repoA-2 ({WS}), window w, 2026-11-02T03:04:05Z: "
            f"opensoft/repoB main {TIP} for test 1's own UTC")
    late = "2026-11-01T09:08:07Z"
    paused = re.compile(rf"^PAUSED {EM} lane repoA-1, session [^,]+@{WS}, {late}, lane:repoA-1"
                        rf"(?: |$)")
    for what, argv, lane, path, utc, wanted in (
            ("append-line's HOLD", ["append-line", hold], "repoA-2", "lanes/LANES.md",
             "2026-11-02T03:04:05Z", lambda line: line == hold),
            ("log PAUSED --utc", ["log", "PAUSED", "lane:repoA-1", "--utc", late,
                                  "parked late for test 1"], "repoA-1", "lanes/log/repoA-1.md",
             late, lambda line: bool(paused.match(line)))):
        assert abs(db_clock(pg) - epoch_of(utc)) > 3600, "the caller's UTC is the clock's"
        before_head = head(pg)
        proc = ws.run(argv, lane)
        entry = _one_entry(pg, before_head, proc, what)
        stored = [r["text"] for r in rows(pg, f"SELECT text FROM doc_lines WHERE path = '{path}' "
                                              f"AND written_seq = {entry['seq']}")]
        assert any(wanted(text) for text in stored), (
            f"{what}: no line the write stored carries the caller's UTC as written: {stored}")
        for label, files in (("the full render", _rendered_only(full_render(pg))),
                             ("the mirror", _mirror(ws, entry["seq"],
                                                    tmp_path / f"mirror-{entry['seq']}"))):
            lines = files[path].decode("utf-8").split("\n")
            assert any(wanted(line) for line in lines), (
                f"{what}: {label}'s {path} holds no line with the caller's UTC as written")


def test_on_primary_a_write_does_not_nudge_a_register_sync(tmp_path):
    """AT-1's FP case (the delta's "The post-write nudge does not re-index the
    mirror into its own source"; FR-027; T416, "The nudge: `index_nudge`'s
    register `sync` is suppressed on primary. Its inventory nudge stays"): a
    `log RESUMED` on a `mode=primary` workstation whose `lanes-index` is the
    contract's stub (T207), beside a copy of `lanes-edit.sh`, `repos.tsv` and
    `lane-start` (CLI4.5 section 6's copy rule) and first on `PATH`, where
    `index_nudge` finds it, its register holding C's render set. The write
    exits 0 and is a primary write (the stub's log holds its `register
    commit`); then the stub's log holds no register `sync` (`sync` with no
    `--source`, or one naming the register), and holds the inventory's,
    `sync --source inventory`, which a `RESUMED`'s lifecycle follow leaves
    (`LANES_LANE_STATE_ROOT` gives it a control root). The nudges are
    detached forks, so the case waits for the inventory's, 30 s at most, and
    one second more. No engine. Fails until L4-B13 (T416's nudge) and L4-B4:
    on line R's V-round4 the write runs files mode, exits 0 and makes no
    `register commit`."""
    code = tmp_path / "code"
    code.mkdir()
    for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
        shutil.copy2(str(REPO / name), str(code / name))
    fakebin = tmp_path / "fakebin"
    estate, env, _source = workspace(tmp_path / "ws", fakebin)
    contract_stub(code, register={p: t for p, t in estate.files.items() if RENDER_SET.match(p)})
    argv_log = code / "lanes-index.argv"
    dead = tmp_path / "dead"
    dead.mkdir()
    host = quote(dead.as_posix(), safe="")
    (tmp_path / "conf").mkdir()
    conf = primary_config(tmp_path / "conf" / "lanes-index.conf",
                          f"postgresql://{LOGIN_WRITER}@{host}:5432/lanes_t240",
                          f"postgresql://{LOGIN_READER}@{host}:5432/lanes_t240")
    env.update(LANES_INDEX_CONFIG=str(conf), LANES_LANE="repoA-2",
               LANES_LANE_STATE_ROOT=str(tmp_path / "lane-state"),
               PATH=str(code) + os.pathsep + env["PATH"])
    env.pop("LANES_INDEX", None)
    real = Path(os.path.realpath(estate.checkout))
    lane_c = real.parent / f"{real.name}-lanes" / "repoA-2"
    lane_c.parent.mkdir(parents=True, exist_ok=True)
    git(lane_c.parent, "clone", "-q", str(estate.origin), str(lane_c), env=estate.env)

    proc = subprocess.run(["bash", str(code / "lanes-edit.sh"), *W_VERBS["log-resumed"][0]],
                          capture_output=True, encoding="utf-8", errors="replace", env=env,
                          timeout=120, cwd=str(estate.checkout), check=False,
                          stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, (
        f"log RESUMED on primary exited {proc.returncode} (L4-B4, L4-B13): "
        f"{proc.stderr[-800:]}")

    def calls() -> list:
        if not argv_log.exists():
            return []
        return [json.loads(x) for x in argv_log.read_text(encoding="utf-8").splitlines() if x]

    assert any(c[:2] == ["register", "commit"] for c in calls()), (
        f"the write made no `register commit`, so it was no primary write: {calls()}")
    inventory = ["sync", "--source", "inventory"]
    deadline = time.monotonic() + 30
    while inventory not in calls() and time.monotonic() < deadline:
        time.sleep(0.1)
    time.sleep(1)
    syncs = [c for c in calls() if c and c[0] == "sync"]
    register_syncs = [c for c in syncs if c != inventory]
    assert register_syncs == [], (
        f"a primary write nudged a register sync, which re-indexes the mirror into its own "
        f"source (T416): {register_syncs}")
    assert inventory in syncs, f"the inventory's nudge did not run: {calls()}"


def test_rename_lane_commits_the_transaction_then_its_move_on_primary_takes_no_bytecode_to_to(
        pg, tmp_path):
    """The move's bytecode on primary (R-F13c-23; lane 3's batch 8, Q32, as
    lane 3's batch c corrects it, #165 6807881675, Q55 and Q56; #162; B15 text
    (2) for F13d:502): `rename-lane` on primary moves a handoff whose folder
    also tracks a pre-#162 `__pycache__` file and a tool-cache path
    (`.mypy_cache`). The rename exits 0 with one journal entry; the move
    renames that one handoff inside its folder, and its commit, the one commit
    on origin that changes a path under `handoffs/`, holds only the handoff's
    D at `<from>` and A at `<to>`; the folder's other tracked paths stay in
    `<c>`'s index and on origin as they were; no note names them; and T420's
    backstop passes the push (origin holds the move). The files-mode twin
    moves as today: its rename exits 0, and its origin holds the handoff at
    `<to>` alone, with the folder's other paths kept. Fails until lane 4's
    T422 lands, with L4-B4 and L4-B13."""
    bytecode = {"handoffs/eagle/__pycache__/notes.cpython-312.pyc": b"\x00pyc, before #162",
                "handoffs/eagle/.mypy_cache/3.12/notes.meta.json": b"{}\n"}
    ws = PrimaryWrites(pg, tmp_path, _w_with_handoffs({"repoA-2": (RL_HANDOFF, RL_TEXT)},
                                                      bytecode))
    twin = FilesTwin(tmp_path / "twin", ws.estate, ws.lanes_edit)
    origin, env = ws.estate.origin, ws.estate.env
    lane_c = ws.lane_checkout("repoA-2")
    base = git(origin, "rev-parse", "main", env=env).strip()
    kept_on_origin = {p: b for p, b in _origin_paths(origin, env).items() if p in bytecode}
    kept_in_c = git(lane_c, "ls-files", "-s", "--", *bytecode, env=env)
    assert len(kept_on_origin) == 2 and len(kept_in_c.splitlines()) == 2

    before_head = head(pg)
    proc = ws.run(RL_ARGV, "repoA-2")
    _one_entry(pg, before_head, proc, "rename-lane over a folder that tracks bytecode")
    moves = git(origin, "log", "--format=%H", f"{base}..main", "--", "handoffs",
                env=env).split()
    assert len(moves) == 1, f"{len(moves)} commits on origin change handoffs/, not one: {moves}"
    changed = git(origin, "diff-tree", "--no-commit-id", "-r", "--no-renames", "--name-status",
                  moves[0], env=env).split("\n")
    assert sorted(x for x in changed if x) == sorted([f"D\t{RL_HANDOFF}", f"A\t{RL_MOVED}"]), (
        f"the move's commit holds more than the handoff's D and A: {changed}")
    assert {p: b for p, b in _origin_paths(origin, env).items() if p in bytecode} == \
        kept_on_origin, "the folder's other tracked paths changed on origin"
    assert git(lane_c, "ls-files", "-s", "--", *bytecode, env=env) == kept_in_c, (
        "the folder's other tracked paths left <c>'s index")
    said = proc.stdout + proc.stderr
    assert "__pycache__" not in said and ".mypy_cache" not in said, (
        f"a note names the folder's bytecode or tool-cache paths: {said[-800:]}")

    done = twin.run(RL_ARGV, "repoA-2")
    assert done.returncode == 0, f"the files-mode twin's rename exited {done.returncode}: " \
                                 f"{done.stderr[-800:]}"
    theirs = _origin_paths(twin.origin, twin.git_env)
    assert RL_MOVED in theirs and RL_HANDOFF not in theirs, "the twin did not move the handoff"
    assert {p: b for p, b in theirs.items() if p in bytecode} == kept_on_origin, (
        "the twin's move changed the folder's other tracked paths")


#: N1's handoff paths (REV422c N1; batch c Q56): a row whose handoff is at a
#: path with a `venv/` part, and one whose handoff is at a path with a
#: `__pycache__/` part, each named for its lane: {lane: (path, its new name)}.
RL_CACHE_PARTS = {
    "repoA-2": ("handoffs/venv/session-handoff-2026-10-01-lane-repoA-2.md", "repoA-3", "venv"),
    "repoA-1": ("handoffs/eagle/__pycache__/session-handoff-2026-10-01-lane-repoA-1.md",
                "repoA-9", "__pycache__"),
}


def test_rename_lane_commits_the_transaction_only_where_its_handoffs_path_has_no_cache_part_on_primary(  # noqa: E501
        pg, tmp_path):
    """N1's refusal (REV422c N1; lane 3's batch c, #165 6807881675, Q56; B15
    text (2) for F13d:502; Y:5138, "a handoff that cannot be stamped refuses
    before anything is sent"): on primary, a row whose handoff is at a path
    with a `venv/` part, and one whose handoff is at a path with a
    `__pycache__/` part (each tracked in the lane's `<c>`, committed there
    before #162), each refuse 2 before the seam: stderr names the part; the
    run sent the register a read, the attempt's snapshot, so the refusal is
    primary's, made in the attempt's child before the seam (files mode's own
    #162 refusal of the same move sends nothing, and exits 2 as well); no
    commit call is sent; no register line is written (the journal's head and
    the rendered files as they were); and no move is made (origin, and the
    handoff in `<c>`, as they were). Fails until lane 4's T422 lands, with
    L4-B4 and L4-B13: it passes on T422 `eda2411` over line R's V-round4."""
    prep = _w_with_handoffs({lane: (path, f"# handoff of lane {lane}\n\nbody\n".encode("ascii"))
                             for lane, (path, _new, _part) in RL_CACHE_PARTS.items()})
    ws = PrimaryWrites(pg, tmp_path, prep)
    origin, env = ws.estate.origin, ws.estate.env
    for lane, (path, new, part) in RL_CACHE_PARTS.items():
        before_head, before_files = head(pg), _rendered_only(full_render(pg))
        paths = _origin_paths(origin, env)
        handoff = ws.lane_checkout(lane) / path
        held = handoff.read_bytes()
        sent_before = len(ws.shim_calls())
        proc = ws.run(["rename-lane", lane, new, "test 1", "--no-github"], lane)
        sent = ws.shim_calls()[sent_before:]
        assert proc.returncode == 2, (
            f"rename-lane {lane} on primary, its handoff at {path}, exited {proc.returncode}, "
            f"not 2 (N1; lane 4's T422): {proc.stderr[-800:]}")
        assert part in proc.stderr, f"the refusal does not name {part!r}: {proc.stderr!r}"
        assert sent, (
            f"rename-lane {lane} sent the register nothing, so its 2 is not primary's refusal "
            f"after the attempt's snapshot (N1; lane 4's T422; L4-B4): {proc.stderr[-800:]}")
        assert not [c for c in sent if "commit_write(" in (c.get("stdin") or "")], (
            f"the refusal sent a commit call: {sent}")
        assert head(pg) == before_head and _rendered_only(full_render(pg)) == before_files, (
            "the refusal wrote a register line")
        assert _origin_paths(origin, env) == paths and handoff.read_bytes() == held, (
            "the refusal moved the handoff")


# ============================================================ phase G: T270
#
# TEST 1'S PHASE-G PART (lane 2's T270, its one case in this module; AT-1, the
# test plan's line 606; the rest of T270 is test 5 and C8, in
# `test_sql_register_renderer_git.py`): the same verbs as part W, on the same
# workstation, with the mirror read from the bare origin's `main`, by object,
# after the renderer the write forks (T416's `render --checkout <c>`, lane 3's
# T320 to T323) has pushed it. The wait is open point 8's first: `lanes-index
# status`, every 100 ms, 30 s at most, until its lag is 0 (`lag:         0
# seq(s)`, lane 1's `status_register`). `status` reads `m` from `origin/<b>` as
# last fetched in W's checkout, `workspace-root`'s answer, `workspace.yaml`'s
# `path:`, whatever `LANES_REPO` names (`7893339348a5:lanes-index:20357`,
# `:1400-1412`; `7893339348a5:lanes-edit.sh:1411-1416`), and fetches nothing
# (`_register_mirror`); the render pushes from the writing lane's `<c>`. So
# each poll comes after the harness's own fetch of W, `git -C <W> fetch -q
# origin main`, with plain git, never through `_logging_git`: lane 3's ruling
# (a), #165 6833830078, as RG's `wait_lag_0` (T270e) and the drill's have it.
# It fails until T320 to T323, T325 and L4-B13 land.
#
# ITS ESTATE, AND NO OTHER, PUTS THE CUTOVER'S MARKER COMMIT ON W'S ORIGIN
# (T270's line, tasks:2477; lane 2, #165 6866688575; lane 3, #165
# 6866808028): `PrimaryWrites(marker_on_origin=True)`, C plus `lanes/STORE`
# with the cutover entry's bytes, `Register-Seq: <cut>` in the last paragraph,
# made before `record_marker` and recorded by it. On a made-up sha and an
# origin at C the forked render finds no `m`, and renders and pushes nothing
# (Y:2845-2847), and `status`'s lag is unknown at every poll. With the commit
# `m` is the cut and the lag 0 before the write, which commits seq cut + 1
# before the poll starts, so a lag of 0 can then only be the render's push,
# and a lag that `status` cannot read for want of `m` fails at once.

#: `status`'s lag line when the mirror has caught up (`status_register`).
STATUS_LAG_ZERO = re.compile(r"^\s*lag:\s+0 seq\(s\)", re.M)
#: `status`'s lag line when no `Register-Seq` is found (`status_register`).
STATUS_LAG_NO_M = re.compile(r"^\s*lag:\s+unknown, since the mirror's m cannot be read", re.M)


def _checkout_state(checkout: Path, env: dict) -> tuple:
    """A checkout's HEAD, its index's digest and `status --porcelain=v1 -uall`."""
    index = checkout / ".git" / "index"
    return (git(checkout, "rev-parse", "HEAD", env=env),
            hashlib.sha256(index.read_bytes()).hexdigest() if index.exists() else "-",
            git(checkout, "status", "--porcelain=v1", "-uall", env=env))


def _status_after_fetching_w(ws: PrimaryWrites) -> subprocess.CompletedProcess:
    """`status` in W's checkout, after the harness's own fetch of W, with plain
    git (the estate's environment, no `_logging_git` on its `PATH`)."""
    git(ws.estate.checkout, "fetch", "-q", "origin", "main", env=ws.estate.env)
    return run_index(ws.copy, ["status"], ws.env, cwd=ws.estate.checkout)


def _wait_for_the_render(ws: PrimaryWrites, ceiling: float = 30.0) -> None:
    """Open point 8's first wait: a bounded poll of `status`, each after a
    fetch of W, until its lag is 0. Origin carries `m` from the marker commit
    on, so a lag unknown for want of `m` fails at once."""
    deadline = time.monotonic() + ceiling
    last = ""
    while True:
        proc = _status_after_fetching_w(ws)
        if STATUS_LAG_ZERO.search(proc.stdout):
            return
        last = f"exit {proc.returncode}: {proc.stdout[-700:]}{proc.stderr[-300:]}"
        assert not STATUS_LAG_NO_M.search(proc.stdout), (
            f"status found no Register-Seq on W's origin/main, though origin carries the "
            f"marker commit; status said {last}")
        assert time.monotonic() < deadline, (
            f"the forked render did not bring the lag to 0 within {ceiling:.0f} s (T320 to "
            f"T323, L4-B13); status said {last}")
        time.sleep(0.1)


@pytest.mark.parametrize("verb", list(W_VERBS))
def test_the_mirror_on_origin_equals_a_full_render_after_each_write(pg, tmp_path, verb):
    """AT-1's part G: `lanes-edit.sh <verb>` on primary exits 0 with one
    journal entry; once the forked render has brought `status`'s lag to 0
    (open point 8), origin has gained exactly one commit, whose
    `Register-Seq:` trailer, in its message's last paragraph in `Key: value`
    form, is the entry's seq, so `git log
    --format='%(trailers:key=Register-Seq,valueonly)'` reads it (AT-F11); the
    render set on origin's `main`, read by object, equals the full render from
    SQL, path set and bytes; and W's checkout and each lane's `<c>` keep their
    HEAD, index and working tree (Q27(a), the private-index form). Origin
    starts at the cutover's marker commit on C, the sha `record_marker`
    recorded, where `status`, after a fetch of W, reads a lag of 0 before the
    write, and the render commit's parent is that marker commit
    (tasks:2477). Fails until T320 to T323, T325 and L4-B13, with L4-B4 and
    L4-B8."""
    argv, lane = W_VERBS[verb]
    ws = PrimaryWrites(pg, tmp_path, W_PREPS.get(verb), marker_on_origin=True)
    origin, env = ws.estate.origin, ws.estate.env
    base = git(origin, "rev-parse", "main", env=env).strip()
    recorded = rows(pg, "SELECT marker_commit FROM register_switch")[0]["marker_commit"]
    assert base == recorded and git(origin, "rev-parse", f"{base}^", env=env).strip() == \
        ws.estate.c, (f"origin's main is {base}, not the marker commit {recorded} on C "
                      f"{ws.estate.c}")
    status = _status_after_fetching_w(ws)
    assert STATUS_LAG_ZERO.search(status.stdout), (
        f"before the write, status after a fetch of W did not read a lag of 0 from the "
        f"marker commit: exit {status.returncode}: {status.stdout[-700:]}"
        f"{status.stderr[-300:]}")
    checkouts = {str(c): _checkout_state(c, env) for c in ws.checkouts()}
    before_head = head(pg)
    proc = ws.run(argv, lane)
    entry = _one_entry(pg, before_head, proc, verb)
    _wait_for_the_render(ws)

    gained = git(origin, "rev-list", f"{base}..main", env=env).split()
    assert len(gained) == 1, f"origin gained {len(gained)} commits, not one: {gained}"
    assert git(origin, "rev-parse", f"{gained[0]}^", env=env).strip() == base, (
        "the render commit's parent is not the marker commit")
    trailer = git(origin, "log", "-1", "--format=%(trailers:key=Register-Seq,valueonly)",
                  gained[0], env=env).strip()
    assert trailer == str(entry["seq"]), (
        f"the render commit's Register-Seq trailer reads {trailer!r}, not {entry['seq']}")
    _assert_same_files(_origin_render_set(origin, env), _rendered_only(full_render(pg)),
                       f"{verb}: origin's main and the full render")
    assert {str(c): _checkout_state(c, env) for c in ws.checkouts()} == checkouts, (
        "the render changed a lane checkout's HEAD, index or working tree")
