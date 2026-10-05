# SPDX-License-Identifier: Apache-2.0
"""lane-collision-protocol Amendment 14 — THE DERIVED INDEX, and the eight tests
its adoption act 2 names (opensoft/openRepoTools#160).

The register's truth stays where it is: `lanes/LANES.md`, `lanes/log/*.md`,
`lanes/aliases.tsv` and `lanes/archive/` in the workspace repository, written
only by `lanes-edit.sh`. `lanes-index` keeps a DERIVED copy, written behind the
sources by itself alone, read only by tooling that decides nothing, and never a
gate. What these tests hold it to:

  * OFFLINE NO-READ — every act's answer is byte-identical with the index
    configured at a store nobody can reach;
  * POISONED INDEX — an index with WRONG rows changes no act's answer, which is
    the proof that acts do not read it (unreachability alone cannot give it);
  * WIPED-INDEX RECONCILE — the rebuild equals a synced index, row for row;
  * REPLAY — a second sync changes nothing;
  * MONOTONIC PROVENANCE — a sync from a commit that does not descend from the
    indexed one writes nothing;
  * A HUNG INDEXER delays no writer beyond the fork;
  * THE MANAGED SEAM — valid, malformed and plain rows index as `managed
    <owner>`, `unknown` and `legacy`, every one of them through #97's own
    `managed-projection`;
  * FALLBACK — each way the index can fail to answer says `read: sources` and
    returns the source read's own answer.

NO REAL DATABASE AND NO NETWORK. Every store is a SQLite file under `tmp_path`;
the Postgres path is a fake `psql` that records what it was asked; every remote
is a bare repository in a temporary directory and every `$HOME` is temporary.
The real `~/.local/bin` is taken OFF `PATH` wherever it carries a `lanes-index`,
so an installed indexer is never what a case runs.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import textwrap
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

LANES_EDIT = REPO / "lanes-edit.sh"
LANES = REPO / "lanes"
INDEXER = REPO / "lanes-index"

UUID_A1 = "aaaaaaaa-0001-4000-8000-00000000a001"
UUID_A1B = "aaaaaaaa-0002-4000-8000-00000000a002"
UUID_A2 = "aaaaaaaa-0003-4000-8000-00000000a003"
UUID_B1 = "bbbbbbbb-0001-4000-8000-00000000b001"
UUID_M1 = "cccccccc-0001-4000-8000-00000000c001"
UUID_M2 = "cccccccc-0002-4000-8000-00000000c002"
UUID_C1 = "dddddddd-0001-4000-8000-00000000d001"
UUID_Z1 = "eeeeeeee-0001-4000-8000-00000000e001"
UUID_T1 = "ffffffff-0001-4000-8000-00000000f001"

#: Lines the grammar has to agree with `LOG_AWK` on, the awkward ones included:
#: a payload behind `←`, free text with no payload, a text-only `— `, a second
#: ` — ` inside the text, a tab, a minutes-only stamp, and every way a line can
#: be UNREADABLE — each of which `LOG_AWK` names in its own words.
NASTY_LOG = "\n".join([
    "# lane repoA-1 — object log (lane-collision-protocol Amendment 7)",
    f"STARTED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:00:00Z, lane:repoA-1 → home opensoft/repoA; dir /work/repoA; profile team-01a; window sess:1 @3",
    f"CLAIMED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:01:00Z, opensoft/repoA#12 — no-github",
    f"NOTED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:02:00Z, lane:repoA-1 — found the bug — and a second dash",
    f"RULED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:03Z, lane:repoA-1 → opensoft/repoA#12 — Brett Heap, verbatim \"take it\"",
    f"OPENED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:04:00Z, opensoft/repoA#13 ← opensoft/repoA#12",
    f"NOTED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:05:00Z, lane:repoA-1\tTAB — a tab in the object",
    "",
    "this line is not the grammar at all",
    f"NOTED—lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:06:00Z, lane:repoA-1 — no spaces round the dash",
    f"TWO WORDS — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:07:00Z, lane:repoA-1 — verb",
    f"NOTED — lane repoA-1 session {UUID_A1}@Eagle, 2026-10-01T00:08:00Z, lane:repoA-1 — no comma",
    f"NOTED — lane repoA-1, {UUID_A1}@Eagle, 2026-10-01T00:09:00Z, lane:repoA-1 — no session word",
    f"NOTED — lane repoA-1, session {UUID_A1}@Eagle 2026-10-01T00:10:00Z, lane:repoA-1 — no comma after the session",
    f"NOTED — lane repoA-1, session {UUID_A1}@Eagle, yesterday, lane:repoA-1 — no stamp",
    f"NOTED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:11:00Z lane:repoA-1 — no comma after the stamp",
    f"NOTED — banana repoA-1, session {UUID_A1}@Eagle, 2026-10-01T00:12:00Z, lane:repoA-1 — no lane word",
    f"PAUSED — lane repoA-1, session {UUID_A1B}@Eagle, 2026-10-01T01:00:00Z, lane:repoA-1 → dir /work/repoA; profile team-01a; agent claude; transcript {UUID_A1B}",
    "",
])


def _sanitized_path() -> str:
    """The caller's PATH without any directory that holds a `lanes-index`:
    an INSTALLED indexer must never be what a case runs or is nudged."""
    keep = []
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if part and not os.path.exists(os.path.join(part, "lanes-index")):
            keep.append(part)
    return os.pathsep.join(keep)


def _row(lane: str, ids: str, state: str, started: str = "2026-10-01T00:00Z",
         ws: str = "Eagle / test / brett", objects: str = "none") -> str:
    return f"| `{lane}` | harness {ids} | {ws} | {started} | {objects} | handoffs/{lane}.md | {state} |"


class Estate:
    """A whole workspace in `tmp_path`: a bare origin, its clone, the pointer
    file that joins them, fake `tmux`/`psql`, and the environment every
    command here is run in."""

    def __init__(self, root: Path):
        self.root = root
        self.home = root / "home"
        self.agents = self.home / ".agents"
        self.origin = root / "origin.git"
        self.wip = self.home / "projects" / "wip"
        self.fakebin = root / "fakebin"
        self.indexbin = root / "indexbin"
        self.state = root / "state"
        self.config = root / "config"
        for d in (self.home, self.agents, self.fakebin, self.indexbin, self.state, self.config,
                  root / "tmp"):
            d.mkdir(parents=True, exist_ok=True)
        (self.fakebin / "tmux").write_text("#!/bin/sh\nexit 1\n")
        (self.fakebin / "tmux").chmod(0o755)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("LANES_", "CLAUDE_", "WORKBENCHES_", "TMUX", "XDG_", "PG",
                                    "AGENT_PROTOCOL_ROOT", "PROJECTS_"))}
        env.update(
            HOME=str(self.home), AGENT_PROTOCOL_ROOT=str(self.agents), TMPDIR=str(root / "tmp"),
            XDG_STATE_HOME=str(self.state), XDG_CONFIG_HOME=str(self.config),
            CLAUDE_CONFIG_DIR=str(self.home / ".claude"), LANES_WORKSTATION="Eagle",
            LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none",
            LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1", LANES_EDIT=str(LANES_EDIT),
            GIT_AUTHOR_NAME="lanes-index tests", GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_NAME="lanes-index tests", GIT_COMMITTER_EMAIL="test@example.invalid",
            PATH=str(self.fakebin) + os.pathsep + _sanitized_path())
        self.env = env
        self._seed()

    # ------------------------------------------------------------ the seed
    def _git(self, *args: str, cwd: Path | None = None) -> str:
        proc = subprocess.run(["git", *args], cwd=str(cwd or self.wip), capture_output=True,
                              text=True, env=self.env, check=False)
        assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"
        return proc.stdout

    def _seed(self) -> None:
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)],
                       check=True, env=self.env)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.wip)],
                       check=True, env=self.env, capture_output=True)
        lanes = self.wip / "lanes"
        (lanes / "log").mkdir(parents=True)
        (lanes / "archive").mkdir()
        register = [
            "# LANES.md — the test register",
            "",
            "| lane | session id | workstation / env / user | started (UTC) | objects owned | handoff path | state |",
            "|---|---|---|---|---|---|---|",
            _row("repoA-1", f"`{UUID_A1}` → `{UUID_A1B}`", "PAUSED · 2026-10-01T01:00:00Z · parked for the night"),
            _row("repoA-2", f"`{UUID_A2}`", "LIVE · 2026-10-01T02:00:00Z · working"),
            _row("repoM-1", f"`{UUID_M1}`", "LIVE · 2026-10-04T00:00:00Z · managed-owner mode=managed daemon=ledger-1 generation=3 bound-lane=repoM-1"),
            _row("repoM-2", f"`{UUID_M2}`", "LIVE · 2026-10-04T00:00:00Z · managed-owner mode=managed daemon=ledger-1 generation=0 bound-lane=repoM-2"),
            _row("repoC-1", f"`{UUID_C1}`", "ENDED · 2026-09-01T00:00:00Z · a row with no log", started="2026-09-01"),
            "",
            f"LANDING — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T02:00:00Z, PR #7 into opensoft/repoA main",
            f"LANDED — lane repoA-1, session {UUID_A1}@Eagle, 2026-10-01T02:05:00Z, PR #7 into opensoft/repoA main → abc1234",
            "HOLD — lane repoA-2 (Eagle), window w, 2026-10-01T03:00:00Z: opensoft/repoA main 0123456789abcdef0123456789abcdef01234567 for a frozen window",
            "HOLD RELEASED — lane repoA-2 (Eagle), 2026-10-01T03:30:00Z: opensoft/repoA main 0123456789abcdef0123456789abcdef01234567",
            "",
        ]
        (lanes / "LANES.md").write_text("\n".join(register), encoding="utf-8")
        (lanes / "log" / "README.md").write_text("# the object logs\n", encoding="utf-8")
        (lanes / "log" / "repoA-1.md").write_text(NASTY_LOG, encoding="utf-8")
        (lanes / "log" / "repoA-2.md").write_text("\n".join([
            "# lane repoA-2 — object log (lane-collision-protocol Amendment 7)",
            f"STARTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T02:00:00Z, lane:repoA-2 → home opensoft/repoA; dir /work/repoA2; profile team-01b",
            f"NOTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T02:10:00Z, lane:repoA-2 — second lane's note",
            ""]), encoding="utf-8")
        (lanes / "log" / "repoB-1.md").write_text("\n".join([
            "# lane repoB-1 — object log (lane-collision-protocol Amendment 7)",
            f"STARTED — lane repoB-1, session {UUID_B1}@Eagle, 2026-10-01T00:30:00Z, lane:repoB-1 → home opensoft/repoB; dir /work/repoB; profile team-02a",
            f"OPENED — lane repoB-1, session {UUID_B1}@Eagle, 2026-10-01T00:31:00Z, opensoft/repoB#3",
            f"NOTED — lane repoB-1, session {UUID_B1}@Eagle, 2026-10-01T00:32:00Z, lane:repoB-1 — a log with no row",
            ""]), encoding="utf-8")
        for lane, uid in (("repoM-1", UUID_M1), ("repoM-2", UUID_M2)):
            (lanes / "log" / f"{lane}.md").write_text(
                f"STARTED — lane {lane}, session {uid}@Eagle, 2026-10-04T00:00:00Z, lane:{lane} → home opensoft/repoM; dir /work/repoM\n",
                encoding="utf-8")
        (lanes / "aliases.tsv").write_text("# old\tnew\tutc\nrepoOld-1\trepoA-2\t2026-09-30T00:00:00Z\n",
                                           encoding="utf-8")
        (lanes / "archive" / "LANES-retired.md").write_text("\n".join([
            "# retired rows (Amendment 19(d))", "",
            _row("repoZ-1", f"`{UUID_Z1}`", "RETIRED · 2026-09-02T00:00:00Z · retired"),
            ""]), encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "seed the test register")
        self._git("push", "-q", "origin", "main")
        (self.agents / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.wip}\n", encoding="utf-8")

    # ------------------------------------------------------------ running
    def run(self, *argv, env: dict | None = None, timeout: float = 120,
            input_text: str | None = None) -> subprocess.CompletedProcess:
        child = dict(self.env)
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True,
                              env=child, timeout=timeout, cwd=str(self.root),
                              input=input_text, stdin=None if input_text is not None else subprocess.DEVNULL)

    def edit(self, *args, env: dict | None = None, **kw) -> subprocess.CompletedProcess:
        return self.run("bash", LANES_EDIT, *args, env=env, **kw)

    def note(self, lane: str, text: str, env: dict | None = None,
             **kw) -> subprocess.CompletedProcess:
        """`log NOTED` as that lane — one write, one commit, one push."""
        merged = {"LANES_LANE": lane}
        merged.update(env or {})
        return self.edit("log", "NOTED", f"lane:{lane}", text, env=merged, **kw)

    def index(self, *args, env: dict | None = None, **kw) -> subprocess.CompletedProcess:
        merged = {"LANES_EDIT": str(LANES_EDIT)}
        merged.update(env or {})
        return self.run(sys.executable, INDEXER, *args, env=merged, **kw)

    @property
    def sqlite(self) -> Path:
        return self.state / "openRepoTools" / "lanes-index.sqlite"

    def tip(self) -> str:
        return self._git("rev-parse", "origin/main").strip()

    def head_text(self, path: str) -> str:
        """`path` as HEAD holds it, read out of git and not off the disk."""
        return self._git("show", f"HEAD:{path}")

    def commit_paths(self, files: dict, message: str) -> None:
        """Commit and push `files` ({repository path: whole content}) THROUGH
        GIT ALONE - `hash-object` and `update-index --cacheinfo` - and never
        through the working tree. Two paths one case apart are two files to
        git on every platform, and ONE file on a case-insensitive filesystem
        (macOS's default): a fixture written to disk there merges the two logs
        it was built to keep apart (#164's gate, darwin). The indexer and
        `who` both read what was PUSHED, so the working tree does not enter."""
        for path, text in files.items():
            sha = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=str(self.wip),
                                 input=text, capture_output=True, text=True, env=self.env,
                                 check=True).stdout.strip()
            # `core.ignorecase` is what a clone on a case-insensitive disk
            # turns on; off here, the index keeps the path as it was spelled.
            self._git("-c", "core.ignorecase=false", "update-index", "--add", "--cacheinfo",
                      f"100644,{sha},{path}")
        self._git("-c", "core.ignorecase=false", "commit", "-q", "-m", message)
        self._git("push", "-q", "origin", "main")

    def write_config(self, text: str, name: str = "lanes-index.conf", mode: int = 0o600) -> Path:
        path = self.config / "openRepoTools" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        path.chmod(mode)
        return path

    def install_indexer(self) -> Path:
        """A copy of `lanes-index` ON PATH, as `--install` would place it, for
        the cases that need the nudge to find one."""
        target = self.indexbin / "lanes-index"
        shutil.copy2(INDEXER, target)
        target.chmod(0o755)
        return target

    def path_with(self, *dirs: Path) -> str:
        return os.pathsep.join([str(d) for d in dirs] + [self.env["PATH"]])


@pytest.fixture
def estate(tmp_path):
    return Estate(tmp_path / "e")


def dump(db: Path, *, with_utc: bool = False) -> dict:
    """Every row of every table, ordered, for a row-for-row comparison."""
    conn = sqlite3.connect(str(db))
    out = {}
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    for table in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        keep = [c for c in cols if with_utc or c not in ("indexed_utc", "applied_utc")]
        out[table] = conn.execute(
            f"SELECT {', '.join(keep)} FROM {table} ORDER BY {', '.join(keep)}").fetchall()
    conn.close()
    return out


HEX = re.compile(r"[0-9a-f]{7,}")
UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2})?Z")
#: THE CLOCK'S, NOT THE READ'S: the listing's AGE column and its footer's "last
#: heard from origin <n>s ago". Both are computed by the same code, at the
#: moment of the read, out of the same stamps, so two reads a second apart can
#: differ there and nowhere else.
AGE = re.compile(r"\b[0-9]+h [0-9]{2}m\b|\b[0-9]+[smhd] ago\b")


def normal(text: str, *roots: Path) -> str:
    """The parts of an answer that are the CLOCK's or the TEMPORARY DIRECTORY's
    and not the act's: a stamp, a commit id, an age, and the sandbox's paths."""
    for root in roots:
        text = text.replace(str(root), "<ROOT>")
    text = UTC.sub("<UTC>", text)
    text = AGE.sub("<AGE>", text)
    return HEX.sub("<HEX>", text)


def load_indexer():
    """`lanes-index` as a module, for the one case that drives a store directly."""
    import importlib.util
    loader = SourceFileLoader("lanes_index_module", str(INDEXER))
    spec = importlib.util.spec_from_loader("lanes_index_module", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _log_awk() -> str:
    text = LANES_EDIT.read_text(encoding="utf-8")
    # A single-quoted shell string carries no `'` of its own, so the program
    # ends at the first quote that closes a line.
    m = re.search(r"^LOG_AWK='\n(.*?)'\n", text, re.S | re.M)
    assert m, "lanes-edit.sh no longer declares LOG_AWK='…' the way this test reads it"
    return m.group(1)


# ====================================================== the parser's parity

def test_the_log_parser_is_log_awk_line_for_line(estate):
    """THE ONE GRAMMAR. `history --index` may print only what `history` prints,
    so the indexer's parse of a log must be `LOG_AWK`'s, field for field and
    warning for warning — over a log written to be awkward. `LOG_AWK` is read
    out of `lanes-edit.sh` itself and run over the same bytes."""
    assert estate.index("sync").returncode == 0
    out = estate.root / "exp"
    out.mkdir()
    res = estate.index("export", "--out", out)
    assert res.returncode == 0, res.stderr
    logs = (out / "logs").read_text().splitlines()
    assert logs == ["lanes/log/repoA-1.md", "lanes/log/repoA-2.md", "lanes/log/repoB-1.md",
                    "lanes/log/repoM-1.md", "lanes/log/repoM-2.md"]
    program = _log_awk()
    want_events, want_warn = [], []
    for rel in logs:
        proc = subprocess.run(["awk", "-v", f"FN={rel}", program],
                              input=(estate.wip / rel).read_text(encoding="utf-8"),
                              capture_output=True, text=True, check=True)
        want_events.append(proc.stdout)
        want_warn.append(proc.stderr)
    assert (out / "events").read_text(encoding="utf-8") == "".join(want_events)
    assert (out / "warn").read_text(encoding="utf-8") == "".join(want_warn)
    assert "unreadable: lanes/log/repoA-1.md:9 (no \" — \" after the verb)" in \
        (out / "warn").read_text(encoding="utf-8")


# ============================================================ replay, digests

def test_replay_a_second_sync_changes_nothing(estate):
    """REPLAY (14(d)): an upsert bearing the stored digest changes nothing, so a
    second sync of the same commit writes not one byte — `indexed_utc`
    included — and a sync after ONE more write upserts only what that write
    moved, leaving every other row's provenance where it was."""
    first = estate.index("sync")
    assert first.returncode == 0, first.stderr
    assert "upserted" in first.stdout
    before = dump(estate.sqlite, with_utc=True)
    time.sleep(1.1)
    second = estate.index("sync")
    assert second.returncode == 0, second.stderr
    assert "nothing to write" in second.stdout
    assert dump(estate.sqlite, with_utc=True) == before

    write = estate.note("repoA-2", "one more note")
    assert write.returncode == 0, write.stderr
    third = estate.index("sync")
    assert third.returncode == 0, third.stderr
    m = re.search(r"(\d+) upserted, (\d+) removed", third.stdout)
    assert m, third.stdout
    # one log line, and the file record whose blob moved — nothing else
    assert (int(m.group(1)), int(m.group(2))) == (2, 0), third.stdout
    conn = sqlite3.connect(str(estate.sqlite))
    tip = estate.tip()
    moved = conn.execute("SELECT COUNT(*) FROM log_lines WHERE provenance = ?", (tip,)).fetchone()[0]
    assert moved == 1
    assert conn.execute("SELECT commit_sha FROM provenance").fetchone()[0] == tip


def test_reconcile_finds_and_rights_a_row_changed_by_hand(estate):
    """RECONCILE READS THE CONTENT. A row somebody edited in the store still
    carries its old digest, so a digest compare passes over it; `reconcile`
    recomputes the digest from what the row SAYS, and puts it right."""
    assert estate.index("sync").returncode == 0
    clean = dump(estate.sqlite)
    conn = sqlite3.connect(str(estate.sqlite))
    conn.execute("UPDATE lanes SET state_phrase = 'LIVE · forged' WHERE lane = 'repoA-1'")
    conn.commit()
    conn.close()
    assert estate.index("sync").stdout.count("nothing to write") == 1
    dry = estate.index("reconcile", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert re.search(r"lanes\s+\d+ kept\s+1 upserted", dry.stdout), dry.stdout
    assert "nothing written (--dry-run)" in dry.stdout
    res = estate.index("reconcile")
    assert res.returncode == 0, res.stderr
    assert dump(estate.sqlite) == clean


# ===================================================== wiped-index reconcile

def test_wiped_index_reconcile_equals_a_synced_index_row_for_row(estate):
    """WIPED-INDEX RECONCILE (14(d)): on a wiped index, the rebuild — and it is
    the same index a sync made, row for row and digest for digest."""
    assert estate.index("sync").returncode == 0
    synced = dump(estate.sqlite)
    estate.sqlite.unlink()
    dry = estate.index("reconcile", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert not estate.sqlite.exists(), "a dry run created the store"
    res = estate.index("reconcile")
    assert res.returncode == 0, res.stderr
    assert dump(estate.sqlite) == synced
    # AND A WIPE THAT LEFT THE TABLES: the provenance row alone gone
    conn = sqlite3.connect(str(estate.sqlite))
    conn.execute("DELETE FROM provenance")
    conn.execute("DELETE FROM log_lines")
    conn.commit()
    conn.close()
    assert estate.index("reconcile").returncode == 0
    assert dump(estate.sqlite) == synced


# ====================================================== monotonic provenance

def test_a_sync_from_a_commit_that_does_not_descend_writes_nothing(estate):
    """MONOTONIC PROVENANCE (14(d)): the indexed commit only moves forward. A
    checkout BEHIND the index, one that has DIVERGED from it, and one that has
    never fetched the indexed commit each write nothing."""
    t1 = estate.tip()
    assert estate.note("repoA-2", "the second commit").returncode == 0
    t2 = estate.tip()
    assert estate.index("sync").returncode == 0
    synced = dump(estate.sqlite, with_utc=True)

    estate._git("update-ref", "refs/remotes/origin/main", t1)
    behind = estate.index("sync")
    assert behind.returncode == 0, behind.stderr
    assert "does not descend from the indexed" in behind.stdout
    assert "BEHIND" in behind.stdout
    assert dump(estate.sqlite, with_utc=True) == synced

    estate._git("checkout", "-q", "-b", "side", t1)
    (estate.wip / "lanes" / "log" / "repoB-1.md").write_text("rewritten\n", encoding="utf-8")
    estate._git("commit", "-q", "-am", "a history the index never saw")
    side = estate._git("rev-parse", "HEAD").strip()
    estate._git("update-ref", "refs/remotes/origin/main", side)
    diverged = estate.index("sync")
    assert diverged.returncode == 1, diverged.stdout
    assert "diverged" in diverged.stdout
    assert dump(estate.sqlite, with_utc=True) == synced
    recon = estate.index("reconcile")
    assert recon.returncode == 1 and "nothing written" in recon.stdout
    assert dump(estate.sqlite, with_utc=True) == synced

    conn = sqlite3.connect(str(estate.sqlite))
    conn.execute("UPDATE provenance SET commit_sha = ?", ("f" * 40,))
    conn.commit()
    conn.close()
    estate._git("update-ref", "refs/remotes/origin/main", t2)
    ahead = estate.index("sync")
    assert ahead.returncode == 0
    assert "another workstation is ahead" in ahead.stdout
    conn = sqlite3.connect(str(estate.sqlite))
    assert conn.execute("SELECT commit_sha FROM provenance").fetchone()[0] == "f" * 40


def test_the_compare_and_swap_refuses_a_provenance_that_moved(estate):
    """THE CAS IS IN THE TRANSACTION: a writer that read one provenance and
    finds another at commit time writes NOTHING — rows included."""
    assert estate.index("sync").returncode == 0
    mod = load_indexer()
    cfg = {"sqlite": str(estate.sqlite), "store": "sqlite"}
    store = mod.SqliteStore(cfg)
    store.open_write()
    source = [p["source"] for p in store.all_provenance()][0]
    before = dump(estate.sqlite, with_utc=True)
    stale = {"commit_sha": "0" * 40}
    upserts = {"lane_aliases": {"999": {"old_name": "x", "new_name": "y", "utc": None,
                                        "ordinal": 999, "raw": "x\ty", "digest": "d"}}}
    with pytest.raises(mod.CasLost):
        store.apply(source, stale, "1" * 40, upserts, {})
    assert dump(estate.sqlite, with_utc=True) == before


# ============================================================ the hung indexer

STUB = """#!/bin/sh
# A HUNG INDEXER: it says it started, says what its stdin was, and sleeps.
printf '%s\\n' "$$" > "$LANES_INDEX_STUB_MARK.pid"
if IFS= read -r line; then echo data > "$LANES_INDEX_STUB_MARK.stdin"; else echo eof > "$LANES_INDEX_STUB_MARK.stdin"; fi
printf '%s\\n' "$*" > "$LANES_INDEX_STUB_MARK.argv"
sleep 30
"""


def _wait_for(path: Path, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists() and path.read_text().strip():
            return True
        time.sleep(0.05)
    return False


def test_a_hung_indexer_delays_no_writer_beyond_the_fork(estate):
    """A HUNG INDEXER (14(d)): the nudge is DETACHED — stdin closed, its output
    on /dev/null, never waited — so a `lanes-index` that sleeps thirty seconds
    costs a write no more than the fork. Measured against the same write with
    the nudge switched off, and proved non-vacuous: the stub DID start, with an
    empty stdin, asked to `sync`, and was still running when the writer had
    already returned."""
    stubdir = estate.root / "stub"
    stubdir.mkdir()
    (stubdir / "lanes-index").write_text(STUB)
    (stubdir / "lanes-index").chmod(0o755)
    mark = estate.root / "stubmark"
    path = estate.path_with(stubdir)

    t0 = time.monotonic()
    control = estate.note("repoA-2", "control write",
                          env={"PATH": path, "LANES_INDEX": "off",
                               "LANES_INDEX_STUB_MARK": str(mark)})
    control_s = time.monotonic() - t0
    assert control.returncode == 0, control.stderr
    assert not _wait_for(Path(str(mark) + ".pid"), 1.0), "LANES_INDEX=off still nudged"

    t0 = time.monotonic()
    nudged = estate.note("repoA-2", "nudged write",
                         env={"PATH": path, "LANES_INDEX": None,
                              "LANES_INDEX_STUB_MARK": str(mark)}, timeout=25)
    nudged_s = time.monotonic() - t0
    assert nudged.returncode == 0, nudged.stderr
    pid_file = Path(str(mark) + ".pid")
    assert _wait_for(pid_file, 10.0), "the nudge never started the indexer"
    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, 0)
        alive = True
    except OSError:
        alive = False
    try:
        assert alive, "the stub was not running when the writer returned — was it waited?"
        assert nudged_s < control_s + 3.0, (
            f"the nudged write took {nudged_s:.2f}s against {control_s:.2f}s without "
            f"the nudge: a thirty-second indexer is delaying the writer")
        assert _wait_for(Path(str(mark) + ".stdin"), 5.0)
        assert Path(str(mark) + ".stdin").read_text().strip() == "eof"
        assert Path(str(mark) + ".argv").read_text().strip() == "sync"
        assert "lanes-index" not in nudged.stdout + nudged.stderr
    finally:
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    print(f"\nmeasured: write with LANES_INDEX=off {control_s:.3f}s; with a 30 s "
          f"indexer on PATH {nudged_s:.3f}s")


def test_a_read_never_nudges_and_no_indexer_costs_nothing(estate):
    """ONLY A PUSH THAT LANDED NUDGES. A read with an indexer on PATH starts
    none; and a write with NO indexer on PATH prints exactly what it prints
    with the nudge switched off — the absent case costs nothing and says
    nothing."""
    stubdir = estate.root / "stub"
    stubdir.mkdir()
    (stubdir / "lanes-index").write_text(STUB)
    (stubdir / "lanes-index").chmod(0o755)
    mark = estate.root / "stubmark"
    res = estate.edit("who", "opensoft/repoA#12",
                      env={"PATH": estate.path_with(stubdir), "LANES_INDEX": None,
                           "LANES_INDEX_STUB_MARK": str(mark)})
    assert res.returncode == 0, res.stderr
    assert not _wait_for(Path(str(mark) + ".pid"), 1.0), "a read nudged the indexer"
    off = estate.note("repoA-2", "the same note", env={"LANES_INDEX": "off"})
    absent = estate.note("repoA-2", "the same note")
    assert (off.returncode, normal(off.stdout), normal(off.stderr)) == \
        (absent.returncode, normal(absent.stdout), normal(absent.stderr))


# ============================================================ the managed seam

def test_the_owner_column_is_managed_projections_answer(estate):
    """THE MANAGED SEAM (14(e)): a valid marker indexes as `managed <owner>`, a
    malformed one as `unknown` — never downgraded to `legacy` — and a plain
    row as `legacy`; and every one of the three was ASKED of #97's own
    `managed-projection`, which the indexer carries no copy of."""
    calls = estate.root / "mp-calls"
    wrapper = estate.root / "lanes-edit-wrapper"
    wrapper.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {calls}\nexec bash {LANES_EDIT} \"$@\"\n")
    wrapper.chmod(0o755)
    res = estate.index("sync", env={"LANES_EDIT": str(wrapper)})
    assert res.returncode == 0, res.stderr
    conn = sqlite3.connect(str(estate.sqlite))
    owners = dict(conn.execute("SELECT lane, owner FROM lanes"))
    assert owners["repoM-1"] == "managed ledger-1"
    assert owners["repoM-2"] == "unknown"
    assert owners["repoA-1"] == "legacy"
    assert owners["repoB-1"] == "legacy"
    asked = calls.read_text().splitlines()
    for lane in ("repoM-1", "repoM-2", "repoA-1"):
        assert f"managed-projection {lane}" in asked, asked
    source = INDEXER.read_text(encoding="utf-8")
    for vocabulary in ("mode=managed", "managed-owner", "bound-lane"):
        assert vocabulary not in source, (
            f"lanes-index carries `{vocabulary}`: a parser of the marker of its own, "
            f"which clause (e) forbids")
    # and the ledger half's tables exist EMPTY, with T058's columns
    cols = [r[1] for r in conn.execute("PRAGMA table_info(swap_states)")]
    assert {"lane", "parent_uuid", "generation", "state"} <= set(cols)
    assert conn.execute("SELECT COUNT(*) FROM swap_states").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM job_summaries").fetchone()[0] == 0
    # and #161's worktree inventory table, RESERVED: its columns, no rows
    cols = [r[1] for r in conn.execute("PRAGMA table_info(worktrees)")]
    assert {"workstation", "lane", "owner", "path", "branch", "base", "lifecycle",
            "generation", "operation", "writer_live", "last_seen_utc", "last_commit",
            "dirty_count", "unpushed_count", "pr_number", "pr_state"} <= set(cols)
    assert conn.execute("SELECT COUNT(*) FROM worktrees").fetchone()[0] == 0


def test_the_schema_holds_what_clause_e_names(estate):
    """What is indexed: every lane (a log with no row, and an archived row,
    included), every log line with the unreadable ones kept by file and line,
    the register's four kinds of line, the transcript pointers, and holds as a
    VIEW in file order."""
    assert estate.index("sync").returncode == 0
    conn = sqlite3.connect(str(estate.sqlite))
    lanes = {r[0]: r for r in conn.execute(
        "SELECT lane, aliases, home, last_session, archived, session_ids, state_phrase FROM lanes")}
    assert set(lanes) >= {"repoA-1", "repoA-2", "repoB-1", "repoM-1", "repoM-2", "repoC-1", "repoZ-1"}
    assert json.loads(lanes["repoA-2"][1]) == ["repoOld-1"]
    assert lanes["repoA-1"][2] == "opensoft/repoA"
    assert lanes["repoA-1"][3] == UUID_A1B
    assert json.loads(lanes["repoA-1"][5]) == [UUID_A1, UUID_A1B]
    assert lanes["repoZ-1"][4] == 1
    assert lanes["repoA-1"][6] == "PAUSED · 2026-10-01T01:00:00Z · parked for the night"
    bad = conn.execute("SELECT file, ordinal, unreadable_why FROM log_lines WHERE unreadable = 1 "
                       "ORDER BY ordinal").fetchall()
    assert len(bad) == 9 and bad[0][:2] == ("lanes/log/repoA-1.md", 9)
    kinds = dict(conn.execute("SELECT kind, COUNT(*) FROM register_lines GROUP BY kind"))
    assert kinds == {"LANDING": 1, "LANDED": 1, "HOLD": 1, "HOLD RELEASED": 1}
    landed = conn.execute("SELECT pr, repo, tip FROM register_lines WHERE kind = 'LANDED'").fetchone()
    assert landed == ("7", "opensoft/repoA", "abc1234")
    holds = conn.execute("SELECT lane, object, verb FROM holds ORDER BY lane, object").fetchall()
    assert holds == [("repoA-1", "opensoft/repoA#12", "CLAIMED"),
                     ("repoA-1", "opensoft/repoA#13", "OPENED"),
                     ("repoB-1", "opensoft/repoB#3", "OPENED")]
    paused = conn.execute("SELECT transcript_id, agent FROM transcript_pointers "
                          "WHERE kind = 'paused'").fetchall()
    assert paused == [(UUID_A1B, "claude")]
    fields = json.loads(conn.execute(
        "SELECT payload_fields FROM log_lines WHERE verb = 'STARTED' AND lane = 'repoA-1'").fetchone()[0])
    assert fields["home"] == "opensoft/repoA" and fields["window"] == "sess:1 @3"
    assert conn.execute("SELECT version FROM schema_version").fetchall() == [(1,)]


# ================================================== the read flag, and its fallback

def _pair(estate, argv, *, env=None):
    src = estate.run(*argv, env=env)
    idx = estate.run(*argv, "--index", env=env)
    return src, idx


READS = [
    ("bash", LANES_EDIT, "history", "repoA-1"),
    ("bash", LANES_EDIT, "history", "--all"),
    ("bash", LANES_EDIT, "history", "--repo", "opensoft/repoA"),
    ("bash", LANES_EDIT, "history", "repoOld-1"),
    ("bash", LANES_EDIT, "lanes", "--all", "--closed"),
    ("bash", LANES, "--all"),
    ("bash", LANES, "--all", "--closed"),
]


def test_the_index_read_is_byte_identical_to_the_source_read(estate):
    """`--index` ANSWERS EXACTLY WHAT THE SOURCES ANSWER where the index is
    current — the listing's AGE column, which is the clock's, the one
    permitted difference — and says so on stderr. Then a write the index has
    not followed: the lag is SAID, never refused."""
    assert estate.index("sync").returncode == 0
    sha12 = estate.tip()[:12]
    for argv in READS:
        src, idx = _pair(estate, argv)
        assert idx.returncode == src.returncode, (argv, idx.stderr)
        assert AGE.sub("<AGE>", idx.stdout) == AGE.sub("<AGE>", src.stdout), argv
        assert f"read: index (sqlite) at register@{sha12}; 0 commits behind" in idx.stderr, (argv, idx.stderr)
        assert "read: " not in src.stderr
    assert estate.note("repoA-1", "a note the index has not seen").returncode == 0
    src, idx = _pair(estate, ("bash", LANES_EDIT, "history", "repoA-1"))
    assert idx.returncode == 0
    assert "1 commits behind" in idx.stderr
    assert "a note the index has not seen" in src.stdout
    assert "a note the index has not seen" not in idx.stdout


def _fallback_setups():
    def missing(e):
        return {}

    def unreachable(e):
        fake = e.root / "pgfake"
        fake.mkdir(exist_ok=True)
        (fake / "psql").write_text("#!/bin/sh\necho 'psql: error: connection to server at \"db.invalid\" failed' >&2\nexit 2\n")
        (fake / "psql").chmod(0o755)
        pw = e.config / "pgpass"
        pw.write_text("*:*:*:*:never-read\n")
        pw.chmod(0o600)
        e.write_config(f"url=postgresql://lanes_writer@db.invalid/qa\npassfile={pw}\n"
                       f"reader_url=postgresql://lanes_reader@db.invalid/qa\n")
        return {"PATH": e.path_with(fake)}

    def wiped(e):
        assert e.index("sync").returncode == 0
        conn = sqlite3.connect(str(e.sqlite))
        conn.execute("DELETE FROM provenance")
        conn.commit()
        return {}

    def unknown_schema(e):
        assert e.index("sync").returncode == 0
        conn = sqlite3.connect(str(e.sqlite))
        conn.execute("UPDATE schema_version SET version = 99")
        conn.commit()
        return {}

    def refused(e):
        e.write_config("store=sqlite\n", mode=0o644)
        return {}

    def off(e):
        assert e.index("sync").returncode == 0
        return {"LANES_INDEX": "off"}

    return [("missing", missing), ("unreachable", unreachable), ("wiped", wiped),
            ("unknown-schema", unknown_schema), ("refused", refused), ("off", off)]


@pytest.mark.parametrize("kind,setup", _fallback_setups(), ids=[k for k, _ in _fallback_setups()])
def test_each_failure_falls_back_to_the_sources_and_says_so(estate, kind, setup):
    """FALLBACK (14(b)): missing, unreachable, wiped, of an unknown schema,
    refused, or switched off — each says `read: sources (index <why>)` and
    returns the source read's own answer and exit."""
    env = setup(estate)
    for argv in READS:
        src = estate.run(*argv, env=env)
        idx = estate.run(*argv, "--index", env=env)
        assert idx.returncode == src.returncode, (kind, argv, idx.stderr)
        assert AGE.sub("<AGE>", idx.stdout) == AGE.sub("<AGE>", src.stdout), (kind, argv)
        assert f"read: sources (index {kind}" in idx.stderr, (kind, argv, idx.stderr)


def test_the_flag_is_never_taken_from_the_environment(estate):
    """`--index` IS TYPED, never inherited: a variable of the seam's own name in
    the environment changes nothing, and neither does a configured store."""
    assert estate.index("sync").returncode == 0
    forged = estate.root / "forged"
    forged.mkdir()
    (forged / "register").write_text("| `forged-1` | x | y | z | none | h | LIVE |\n")
    res = estate.edit("lanes", "--all", env={"LANES_IDX_DIR": str(forged), "LANES_INDEX": None})
    assert res.returncode == 0
    assert "forged-1" not in res.stdout
    assert "read: " not in res.stderr


# ======================================================= offline no-read, poison

#: The acts and the reads an act makes for itself, each one run against two
#: fresh copies of the same estate. A WRITE is followed by its nudge where an
#: indexer is on PATH — which is the point: it runs, it fails against the
#: configured store, and the act's answer does not move.
ACTS = [
    ("claim", "opensoft/repoA#40"),
    ("log", "NOTED", "lane:repoA-2", "an offline note"),
    ("set-row-state", "repoA-2", "PAUSED · parked offline"),
    ("release", "opensoft/repoA#12", "done with it"),
    ("who", "--landing", "opensoft/repoA"),
    ("who", "opensoft/repoA#12"),
    ("who", "--lane", "repoA-1"),
    ("lane-objects", "repoA-1"),
    ("managed-projection", "repoA-1"),
    ("managed-projection", "repoM-1"),
    ("managed-projection", "repoM-2"),
    ("binding", "repoA-1"),
    ("live-holder", "repoA-2"),
    ("register-row", "repoA-1"),
    ("canon-lane", "repoOld-1"),
    ("history", "repoA-1"),
    ("lanes", "--all", "--closed"),
]


def _act_env(e: Estate, act: tuple) -> dict:
    env = {}
    if act[0] in ("claim", "log", "set-row-state", "release"):
        env["LANES_LANE"] = "repoA-2" if act[0] != "release" else "repoA-1"
        env["LANES_SESSION"] = UUID_A2 if act[0] != "release" else UUID_A1B
    return env


def _run_act(e: Estate, act: tuple, extra: dict) -> tuple:
    env = _act_env(e, act)
    env.update(extra)
    res = e.edit(*act, env=env)
    return (res.returncode, normal(res.stdout, e.root), normal(res.stderr, e.root))


def test_offline_no_read_every_act_is_byte_identical_against_an_unreachable_index(tmp_path):
    """OFFLINE NO-READ (14(b), (f)): with an indexer installed and configured at
    a Postgres nobody can reach, every act answers byte for byte as it does
    with no index at all — and the writes' nudges DID reach for that store,
    which is what makes the sameness a finding rather than an absence."""
    control_root = tmp_path / "control"
    index_root = tmp_path / "index"
    control = Estate(control_root)
    indexed = Estate(index_root)
    indexed.install_indexer()
    fake = indexed.root / "pgfake"
    fake.mkdir()
    psql_log = indexed.root / "psql.log"
    (fake / "psql").write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {psql_log}\n"
        "echo 'psql: error: connection to server at \"lanes-index.invalid\" failed' >&2\nexit 2\n")
    (fake / "psql").chmod(0o755)
    pw = indexed.config / "pgpass"
    pw.write_text("*:*:*:*:never-read\n")
    pw.chmod(0o600)
    indexed.write_config(f"url=postgresql://lanes_writer@lanes-index.invalid/qa\npassfile={pw}\n")
    extra = {"PATH": indexed.path_with(indexed.indexbin, fake), "LANES_INDEX": None}
    for act in ACTS:
        a = _run_act(control, act, {})
        b = _run_act(indexed, act, extra)
        assert normal(a[1], control_root) == normal(b[1], index_root), act
        assert (a[0], normal(a[2], control_root)) == (b[0], normal(b[2], index_root)), (act, b[2])
    assert _wait_for(psql_log, 15.0), "no nudge ever reached for the configured store"
    assert "lanes_writer" in psql_log.read_text()


def test_a_poisoned_index_changes_no_acts_answer(tmp_path):
    """POISONED INDEX (14(b)): an index carrying WRONG rows — a forged hold, a
    forged owner, a forged state, forged narrative — changes no act's answer.
    Unreachability cannot prove that acts do not read the index; wrong rows
    that nothing repeats can. And the poison is REAL: `--index` reads it."""
    control = Estate(tmp_path / "control")
    poisoned = Estate(tmp_path / "poisoned")
    res = poisoned.index("sync")
    assert res.returncode == 0, res.stderr
    conn = sqlite3.connect(str(poisoned.sqlite))
    conn.execute("UPDATE lanes SET owner = 'managed evil', state_phrase = 'LIVE · poisoned', "
                 "session_ids = '[\"99999999-9999-4999-8999-999999999999\"]', "
                 "last_session = '99999999-9999-4999-8999-999999999999'")
    conn.execute("UPDATE log_lines SET free_text = 'POISONED' WHERE verb = 'NOTED'")
    conn.execute("UPDATE log_lines SET verb = 'CLAIMED', object = 'opensoft/repoA#40' "
                 "WHERE verb = 'NOTED' AND lane = 'repoB-1'")
    conn.execute("UPDATE register_lines SET kind = 'LANDING', raw = 'LANDING — poisoned'")
    conn.commit()
    conn.close()
    extra = {"LANES_INDEX": None}
    for act in ACTS:
        a = _run_act(control, act, {})
        b = _run_act(poisoned, act, extra)
        assert normal(a[1], control.root) == normal(b[1], poisoned.root), act
        assert (a[0], normal(a[2], control.root)) == (b[0], normal(b[2], poisoned.root)), (act, b[2])
    seen = poisoned.edit("history", "repoB-1", "--index", env=extra)
    assert "read: index (sqlite)" in seen.stderr
    assert "POISONED" in seen.stdout or seen.returncode == 8, seen.stdout
    told = poisoned.edit("history", "repoA-1", "--index", env=extra)
    assert "POISONED" in told.stdout, "the poison never reached the index read: vacuous"


# ============================================================ history across lanes

def test_history_across_lanes_reads_the_sources_on_one_timeline(estate):
    """`history --all` and `history --repo <r>` (14(g) act 2): every lane's
    `NOTED`/`RULED` on ONE timeline, by UTC and then file order, with the lane
    named — from the SOURCES, no flag needed; and the selectors refuse to be
    combined."""
    res = estate.edit("history", "--all")
    assert res.returncode == 0, res.stderr
    lines = res.stdout.splitlines()
    stamps = [line.split()[0] for line in lines]
    padded = [s if len(s) == 20 else s[:16] + ":00Z" for s in stamps]
    assert padded == sorted(padded)
    assert any(" repoB-1 " in line for line in lines)
    assert any(" repoA-2 " in line for line in lines)
    repo = estate.edit("history", "--repo", "opensoft/repoB")
    assert repo.returncode == 0, repo.stderr
    assert repo.stdout.splitlines() and all(" repoB-1 " in l for l in repo.stdout.splitlines())
    none = estate.edit("history", "--repo", "opensoft/nowhere")
    assert none.returncode == 8 and none.stdout == ""
    since = estate.edit("history", "--all", "--since", "2026-10-01T00:30Z")
    assert all(l.split()[0] >= "2026-10-01T00:30" for l in since.stdout.splitlines())
    for bad in (("history", "repoA-1", "--all"), ("history", "--all", "--repo", "x/y"),
                ("history",)):
        refused = estate.edit(*bad)
        assert refused.returncode == 64, (bad, refused.stderr)


# ================================================================ the store's rules

@pytest.mark.parametrize("text,mode,where,why", [
    ("store=sqlite\n", 0o644, "config", "mode 644"),
    ("url=postgresql://w:secret@db.invalid/qa\n", 0o600, "config", "carries a password"),
    ("url=postgresql://w@db.invalid/qa?password=secret\n", 0o600, "config", "carries a password"),
    ("url=host=db.invalid user=w password=secret\n", 0o600, "config", "carries a password"),
    ("store=oracle\n", 0o600, "config", "the store is"),
    ("colour=blue\n", 0o600, "config", "does not know"),
    ("store=postgres\n", 0o600, "config", "names no `url=`"),
    ("store=sqlite\n", 0o600, "worktree", "inside the git work tree"),
    ("store=sqlite\n", 0o600, "agents", "which on a"),
])
def test_the_configuration_is_refused_on_clause_c_grounds(estate, text, mode, where, why):
    """THE CONFIGURATION (14(c)): per workstation, 0600, never committed and
    never under `~/.agents/`, and no password in a URL. Each refusal is exit 2
    and writes nothing."""
    if where == "config":
        path = estate.write_config(text, mode=mode)
        env = {}
    elif where == "worktree":
        path = estate.wip / "lanes-index.conf"
        path.write_text(text)
        path.chmod(mode)
        env = {"LANES_INDEX_CONFIG": str(path)}
    else:
        path = estate.agents / "lanes-index.conf"
        path.write_text(text)
        path.chmod(mode)
        env = {"LANES_INDEX_CONFIG": str(path)}
    res = estate.index("sync", env=env)
    assert res.returncode == 2, (res.stdout, res.stderr)
    assert why in res.stderr, res.stderr
    assert not estate.sqlite.exists()


def test_a_named_configuration_that_is_not_there_and_a_store_in_a_work_tree_refuse(estate):
    missing = estate.index("sync", env={"LANES_INDEX_CONFIG": str(estate.root / "nope.conf")})
    assert missing.returncode == 2 and "does not exist" in missing.stderr
    estate.write_config(f"sqlite={estate.wip / 'lanes-index.sqlite'}\n")
    inside = estate.index("sync")
    assert inside.returncode == 2 and "never inside a work tree" in inside.stderr
    pw = estate.config / "loose-pgpass"
    pw.write_text("*:*:*:*:x\n")
    pw.chmod(0o644)
    estate.write_config(f"url=postgresql://w@db.invalid/qa\npassfile={pw}\n")
    loose = estate.index("sync")
    assert loose.returncode == 2 and "password file" in loose.stderr


FAKE_PSQL = r"""#!/usr/bin/env python3
# A FAKE psql: it records what it was asked and answers the few queries
# lanes-index makes as an EMPTY schema-1 store would. No database exists.
import json, os, sys
# The schema version it answers is "1" unless FAKE_PSQL_VERSION_FILE names a
# file holding another (empty: no row, a wiped store); the bootstrap DDL
# writes "1" into that file, as a real one would create the row.
log = os.environ["FAKE_PSQL_LOG"]
vfile = os.environ.get("FAKE_PSQL_VERSION_FILE", "")
version = open(vfile).read().strip() if vfile else "1"
args = sys.argv[1:]
url = args[args.index("-d") + 1] if "-d" in args else ""
stdin = sys.stdin.read()
with open(log, "a") as handle:
    handle.write(json.dumps({"url": url, "passfile": os.environ.get("PGPASSFILE", ""),
                             "pgpassword": "PGPASSWORD" in os.environ, "stdin": stdin}) + "\n")
if vfile and "CREATE TABLE IF NOT EXISTS" in stdin:
    with open(vfile, "w") as handle:
        handle.write("1\n")
for line in stdin.splitlines():
    if line.startswith("COPY (SELECT version"):
        if version:
            print(version)
    elif line.startswith("\\echo"):
        print("\x1eLANES-INDEX-NEXT")
sys.exit(0)
"""


def test_postgres_takes_the_writer_to_write_and_the_reader_to_read(estate):
    """TWO ROLES (14(c)): `sync` connects as the `url=` WRITER and `export`
    and `status` as the `reader_url=` READER, each with its own 0600 password
    file and never a `PGPASSWORD`; and the sync's writes are ONE transaction
    whose first act is the provenance compare-and-swap."""
    fake = estate.root / "pgfake"
    fake.mkdir()
    (fake / "psql").write_text(FAKE_PSQL)
    (fake / "psql").chmod(0o755)
    log = estate.root / "psql.jsonl"
    wpw = estate.config / "writer.pgpass"
    rpw = estate.config / "reader.pgpass"
    for p in (wpw, rpw):
        p.write_text("*:*:*:*:x\n")
        p.chmod(0o600)
    estate.write_config(
        f"url=postgresql://lanes_writer@db.invalid/qa\npassfile={wpw}\n"
        f"reader_url=postgresql://lanes_reader@db.invalid/qa\nreader_passfile={rpw}\n")
    env = {"PATH": estate.path_with(fake), "FAKE_PSQL_LOG": str(log),
           "PGPASSWORD": "inherited-and-never-used"}
    res = estate.index("sync", env=env)
    assert res.returncode == 0, res.stderr
    calls = [json.loads(l) for l in log.read_text().splitlines()]
    assert calls and all(c["url"] == "postgresql://lanes_writer@db.invalid/qa" for c in calls)
    assert all(c["passfile"] == str(wpw) and not c["pgpassword"] for c in calls)
    writes = [c["stdin"] for c in calls if "INSERT INTO lanes" in c["stdin"]]
    assert len(writes) == 1, "the rows went in more than one transaction"
    script = writes[0]
    assert script.index("BEGIN;") < script.index("lanes_index_cas") < script.index("INSERT INTO lanes")
    assert script.rstrip().endswith("COMMIT;")
    assert "IS NOT DISTINCT FROM NULL" in script
    log.unlink()
    out = estate.root / "exp"
    out.mkdir()
    exp = estate.index("export", "--out", out, env=env)
    assert exp.returncode == 3 and (out / "why").read_text().startswith("wiped")
    st = estate.index("status", env=env)
    calls = [json.loads(l) for l in log.read_text().splitlines()]
    assert calls and all(c["url"] == "postgresql://lanes_reader@db.invalid/qa" for c in calls)
    assert all(c["passfile"] == str(rpw) for c in calls)
    assert not any("INSERT" in c["stdin"] or "CREATE" in c["stdin"] for c in calls)
    assert "postgres" in st.stdout


def test_a_read_never_connects_with_the_writers_credential(estate):
    """THE READER OR NOTHING (14(c); Copilot round 1 on #164): a Postgres
    configuration with a writer `url=` and no `reader_url=` REFUSES the reads
    — `export` says `refused` and the read flags answer from the sources,
    `status` exits 2 — and not one of them reaches `psql` at all, so the
    writer's credential is never presented by a session typing `--index`."""
    fake = estate.root / "pgfake"
    fake.mkdir()
    (fake / "psql").write_text(FAKE_PSQL)
    (fake / "psql").chmod(0o755)
    log = estate.root / "psql.jsonl"
    wpw = estate.config / "writer.pgpass"
    wpw.write_text("*:*:*:*:x\n")
    wpw.chmod(0o600)
    estate.write_config(f"url=postgresql://lanes_writer@db.invalid/qa\npassfile={wpw}\n")
    env = {"PATH": estate.path_with(fake), "FAKE_PSQL_LOG": str(log)}
    out = estate.root / "exp"
    out.mkdir()
    exp = estate.index("export", "--out", out, env=env)
    assert exp.returncode == 2, exp.stderr
    assert (out / "why").read_text().startswith("refused:")
    assert "reader_url" in (out / "why").read_text()
    for argv in (("bash", LANES_EDIT, "history", "repoA-1"), (LANES, "--all")):
        src = estate.run(*argv, env=env)
        idx = estate.run(*argv, "--index", env=env)
        assert "read: sources (index refused" in idx.stderr, (argv, idx.stderr)
        assert idx.returncode == src.returncode, (argv, idx.stderr)
        assert AGE.sub("<AGE>", idx.stdout) == AGE.sub("<AGE>", src.stdout), argv
    st = estate.index("status", env=env)
    assert st.returncode == 2 and "reader_url" in st.stderr, st.stderr
    assert not log.exists(), "a read reached psql: " + log.read_text()
    # the WRITER is still the indexer's, untouched by the rule
    assert estate.index("sync", env=env).returncode == 0
    assert all(json.loads(l)["url"] == "postgresql://lanes_writer@db.invalid/qa"
               for l in log.read_text().splitlines())


def test_a_symlink_is_judged_where_it_points(estate):
    """RESOLVED BEFORE IT IS JUDGED (14(c); Copilot round 1 on #164): a 0600
    configuration reached through a symlink that lives outside every
    repository but points INTO a work tree is a file in that work tree, and is
    refused; so is a SQLite store whose directory is a link into one."""
    inside = estate.wip / "lanes-index.conf"
    inside.write_text("store=sqlite\n", encoding="utf-8")
    inside.chmod(0o600)
    link = estate.config / "openRepoTools" / "lanes-index.conf"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(inside)
    res = estate.index("sync")
    assert res.returncode == 2 and "inside the git work tree" in res.stderr, res.stderr
    assert not estate.sqlite.exists()
    link.unlink()
    door = estate.root / "door"
    door.symlink_to(estate.wip)
    estate.write_config(f"sqlite={door / 'lanes-index.sqlite'}\n")
    res = estate.index("sync")
    assert res.returncode == 2 and "never inside a work tree" in res.stderr, res.stderr
    assert not (estate.wip / "lanes-index.sqlite").exists()


def test_two_logs_one_case_apart_keep_two_transcript_pointers(estate):
    """KEYED AS THE LOG LINES ARE (Copilot round 1 on #164): two logs whose
    names differ only by case, each with a PAUSED carrying a transcript at
    the SAME line, are two pointers — the second keyed by its file — never one
    overwritten by the other."""
    tid = "ffffffff-0002-4000-8000-00000000f002"
    paused = (f"PAUSED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T04:00:00Z, "
              f"lane:repoA-2 → dir /work/repoA2; agent claude; transcript {{}}")
    lower = "lanes/log/repoA-2.md"
    estate.commit_paths({
        "lanes/log/REPOA-2.md": "\n".join([
            "# lane repoA-2 — object log, the other spelling",
            f"STARTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T02:00:00Z, lane:repoA-2 → home opensoft/repoA",
            f"NOTED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-01T02:10:00Z, lane:repoA-2 — padding",
            paused.format(UUID_T1), ""]),
        lower: estate.head_text(lower) + paused.format(tid) + "\n",
    }, "two spellings of one log")
    tree = estate._git("ls-tree", "--name-only", "origin/main", "lanes/log/").split()
    assert {"lanes/log/REPOA-2.md", lower} <= set(tree), tree
    res = estate.index("sync")
    assert res.returncode == 0, res.stderr
    conn = sqlite3.connect(str(estate.sqlite))
    rows = conn.execute("SELECT record_id, transcript_id FROM transcript_pointers "
                        "WHERE kind = 'paused' AND transcript_id IN (?, ?)",
                        (UUID_T1, tid)).fetchall()
    assert {t for _, t in rows} == {UUID_T1, tid}, rows
    assert len({r for r, _ in rows}) == 2, rows
    # NOT VACUOUS: the two PAUSED lines sit at the SAME line of their files,
    # so the first-choice id collides and the second is keyed by its file.
    where = conn.execute("SELECT lane, ordinal FROM log_lines WHERE verb = 'PAUSED' "
                         "AND file IN ('lanes/log/REPOA-2.md', ?)", (lower,)).fetchall()
    assert len(where) == 2 and where[0][1] == where[1][1], where


def _as_estate(monkeypatch, estate) -> None:
    """This process's environment made the estate's, for the cases that drive
    `lanes-index` as a module; `monkeypatch` puts it back."""
    for key in list(os.environ):
        if key.startswith(("LANES_", "CLAUDE_", "WORKBENCHES_", "TMUX", "XDG_", "PG",
                           "AGENT_PROTOCOL_ROOT", "PROJECTS_")):
            monkeypatch.delenv(key, raising=False)
    for key, value in estate.env.items():
        monkeypatch.setenv(key, value)


def test_a_source_that_moves_while_the_owners_are_asked_writes_nothing(estate, monkeypatch,
                                                                         capsys):
    """ONE COMMIT'S ROWS, ONE COMMIT'S OWNERS (14(d); Copilot round 1 on
    #164): `managed-projection` reads `origin/<branch>` as it stands, so the
    indexer asks the ref again once the owners are in; a ref that moved
    meanwhile writes NOTHING, and `sync` reads the new tip whole."""
    _as_estate(monkeypatch, estate)
    mod = load_indexer()
    real_tip = mod.tip_of
    asked = []

    def moving(root):
        asked.append(root)
        return "f" * 40 if len(asked) == 2 else real_tip(root)

    monkeypatch.setattr(mod, "tip_of", moving)
    with pytest.raises(mod.SourceMoved):
        mod.run_index("sync", None, False)
    conn = sqlite3.connect(str(estate.sqlite))
    assert conn.execute("SELECT COUNT(*) FROM provenance").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM lanes").fetchone()[0] == 0
    conn.close()
    asked.clear()
    assert mod.cmd_sync(None) == 0
    captured = capsys.readouterr()
    assert "moved from" in captured.err, captured.err
    assert len(asked) == 4, asked
    conn = sqlite3.connect(str(estate.sqlite))
    assert conn.execute("SELECT commit_sha FROM provenance").fetchone()[0] == estate.tip()
    assert conn.execute("SELECT COUNT(*) FROM lanes").fetchone()[0] > 0


def test_a_rerun_marked_as_the_holder_lets_go_is_never_lost(estate, monkeypatch):
    """THE HANDSHAKE (14(d); Codex on #164): a mark written after the holder's
    last look but before it released is found by the holder's look AFTER the
    release, and synced; and a sync that finds the lock held, marks, and then
    finds it free takes it itself — no mark is left with nobody to read it."""
    _as_estate(monkeypatch, estate)
    mod = load_indexer()
    runs = []
    monkeypatch.setattr(mod, "run_index", lambda *a: runs.append(a) or 0)
    real_release = mod.SyncLock.release
    released = []

    def release_late_marked(self):
        if not released and self.handle is not None:
            self.mark_rerun()  # the contender's mark, after the holder last looked
        released.append(1)
        real_release(self)

    monkeypatch.setattr(mod.SyncLock, "release", release_late_marked)
    assert mod.cmd_sync(None) == 0
    assert len(runs) == 2, runs
    lock = mod.SyncLock()
    assert not os.path.exists(lock.rerun)
    monkeypatch.setattr(mod.SyncLock, "release", real_release)

    runs.clear()
    answers = iter([False, True])  # held at the first look, free at the second

    def acquire_second_time(self, wait_seconds):
        return next(answers, True)

    monkeypatch.setattr(mod.SyncLock, "acquire", acquire_second_time)
    assert mod.cmd_sync(None) == 0
    assert len(runs) == 1, "the contender found the lock free on its second look and did not sync"
    assert not os.path.exists(lock.rerun)


def test_an_unknown_owner_is_asked_again_at_the_same_commit(estate):
    """`unknown` IS NOT AN ANSWER TO KEEP (14(e); Codex on #164): an owner
    that read as `unknown` because `managed-projection` failed is asked again
    by the next sync even when the index is already at the tip, and only the
    row it clears is written."""
    wrapper = estate.root / "lanes-edit-failing"
    wrapper.write_text("#!/bin/sh\n"
                       "if [ \"$1\" = managed-projection ] && [ \"$2\" = repoA-1 ]; then\n"
                       "  echo 'managed-projection: could not read origin' >&2; exit 1\nfi\n"
                       f"exec bash {LANES_EDIT} \"$@\"\n")
    wrapper.chmod(0o755)
    assert estate.index("sync", env={"LANES_EDIT": str(wrapper)}).returncode == 0
    conn = sqlite3.connect(str(estate.sqlite))
    assert dict(conn.execute("SELECT lane, owner FROM lanes"))["repoA-1"] == "unknown"
    conn.close()
    again = estate.index("sync")
    assert again.returncode == 0, again.stderr
    assert "1 upserted, 0 removed" in again.stdout, again.stdout
    conn = sqlite3.connect(str(estate.sqlite))
    owners = dict(conn.execute("SELECT lane, owner FROM lanes"))
    assert owners["repoA-1"] == "legacy"
    assert owners["repoM-2"] == "unknown"  # a malformed marker stays what it is
    conn.close()
    before = dump(estate.sqlite, with_utc=True)
    third = estate.index("sync")
    assert third.returncode == 0 and "nothing to write" in third.stdout, third.stdout
    assert dump(estate.sqlite, with_utc=True) == before


def test_the_holds_view_answers_as_who_does(estate):
    """THE VIEW IS `holders_of` (14(e); Copilot round 2 on #164): a lane's own
    last line on an object — the lane compared case-insensitively, "last" in
    file order — holds while its verb is open, and NOT while another lane's own
    last line there is a TAKEOVER. Checked object by object against `who`."""
    lines = {
        "repoA-1.md": [
            f"CLAIMED — lane repoA-1, session {UUID_A1B}@Eagle, 2026-10-02T00:00:00Z, opensoft/repoA#20 — mine",
            f"CLAIMED — lane repoA-1, session {UUID_A1B}@Eagle, 2026-10-02T00:30:00Z, opensoft/repoA#21 — mine again, after it came back"],
        "repoA-2.md": [
            f"TAKEOVER — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-02T00:05:00Z, opensoft/repoA#20 — a stale claim",
            f"TAKEOVER — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-02T00:10:00Z, opensoft/repoA#21 — taken",
            f"RELEASED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-02T00:20:00Z, opensoft/repoA#21 — handed back",
            f"RELEASED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-02T00:40:00Z, opensoft/repoA#22 — done with it"],
        # the same lane under another spelling: byte order puts this file
        # FIRST, so its CLAIMED is not the lane's last line on #22
        "REPOA-2.md": [
            "# lane repoA-2 — object log, the other spelling",
            f"CLAIMED — lane repoA-2, session {UUID_A2}@Eagle, 2026-10-02T00:35:00Z, opensoft/repoA#22 — under the other spelling"],
    }
    files = {}
    for name, add in lines.items():
        path = f"lanes/log/{name}"
        old = estate.head_text(path) if name != "REPOA-2.md" else ""
        files[path] = old + "\n".join(add) + "\n"
    estate.commit_paths(files, "a takeover, a hand-back and two spellings")
    tree = estate._git("ls-tree", "--name-only", "origin/main", "lanes/log/").split()
    assert {"lanes/log/REPOA-2.md", "lanes/log/repoA-2.md"} <= set(tree), tree
    assert estate.index("sync").returncode == 0
    conn = sqlite3.connect(str(estate.sqlite))
    view: dict = {}
    for lane, obj in conn.execute("SELECT lane, object FROM holds"):
        view.setdefault(obj, set()).add(lane.lower())
    objects = [r[0] for r in conn.execute(
        "SELECT DISTINCT object FROM log_lines WHERE unreadable = 0 "
        "AND object NOT LIKE 'lane:%' ORDER BY object")]
    conn.close()
    assert {"opensoft/repoA#20", "opensoft/repoA#21", "opensoft/repoA#22"} <= set(objects)
    for obj in objects:
        res = estate.edit("who", obj)
        assert res.returncode == 0, (obj, res.stderr)
        who = {m.lower() for m in re.findall(r"^HOLDS +lane (\S+)", res.stdout, re.M)}
        assert view.get(obj, set()) == who, (obj, view.get(obj), res.stdout)
    assert view["opensoft/repoA#20"] == {"repoa-2"}
    assert view["opensoft/repoA#21"] == {"repoa-1"}
    assert "opensoft/repoA#22" not in view


def test_the_holds_view_follows_file_order_not_the_clock(estate):
    """"LAST" IS THE LAST LINE IN THE FILE (R14; the macOS gate on #164): two
    lines of one lane on one object, written OUT OF UTC ORDER, are ordered by
    their position in the log - and line 10 comes after line 9, compared as
    numbers. A view that ordered by the UTC field, or by the line as text,
    answers both objects the other way round; `who` is asked as well."""
    path = "lanes/log/repoA-2.md"
    head = estate.head_text(path)
    assert len(head.split("\n")) == 4  # header, STARTED, NOTED, and the final newline
    say = lambda verb, utc, obj, text: (
        f"{verb} — lane repoA-2, session {UUID_A2}@Eagle, {utc}, {obj} — {text}")
    add = [
        say("CLAIMED", "2026-10-03T09:00:00Z", "opensoft/repoA#30", "line 4, the LATEST stamp"),
        say("RELEASED", "2026-10-03T23:00:00Z", "opensoft/repoA#31", "line 5, the LATEST stamp"),
    ] + [say("NOTED", f"2026-10-03T1{n}:00:00Z", "lane:repoA-2", f"padding {n}") for n in range(4)] + [
        say("RELEASED", "2026-10-03T01:00:00Z", "opensoft/repoA#30", "line 10, an EARLIER stamp"),
        say("CLAIMED", "2026-10-03T00:30:00Z", "opensoft/repoA#31", "line 11, an EARLIER stamp"),
    ]
    estate.commit_paths({path: head + "\n".join(add) + "\n"}, "two objects out of UTC order")
    assert estate.index("sync").returncode == 0
    conn = sqlite3.connect(str(estate.sqlite))
    placed = dict(conn.execute(
        "SELECT object || ' ' || verb, ordinal FROM log_lines WHERE file = ? "
        "AND object IN ('opensoft/repoA#30', 'opensoft/repoA#31')", (path,)).fetchall())
    assert placed == {"opensoft/repoA#30 CLAIMED": 4, "opensoft/repoA#31 RELEASED": 5,
                      "opensoft/repoA#30 RELEASED": 10, "opensoft/repoA#31 CLAIMED": 11}, placed
    held = dict(conn.execute("SELECT object, verb FROM holds "
                             "WHERE object IN ('opensoft/repoA#30', 'opensoft/repoA#31')"))
    assert held == {"opensoft/repoA#31": "CLAIMED"}, held
    for obj, state in (("opensoft/repoA#30", "FREE"), ("opensoft/repoA#31", "HELD")):
        res = estate.edit("who", obj)
        assert res.returncode == 0, res.stderr
        assert re.search(rf"^state +{state}\b", res.stdout, re.M), (obj, res.stdout)


def test_the_store_is_made_private_on_every_write(estate):
    """0600 EVERY TIME (14(c); Copilot round 2 on #164): a SQLite store whose
    mode drifted is made private again by the next sync, not only at birth."""
    assert estate.index("sync").returncode == 0
    estate.sqlite.chmod(0o644)
    assert estate.index("sync").returncode == 0
    assert stat.S_IMODE(estate.sqlite.stat().st_mode) == 0o600


def test_a_postgres_store_of_another_schema_is_not_touched(estate):
    """NEVER WRITTEN, NOT EVEN BY THE BOOTSTRAP (14(d); Copilot round 2 on
    #164): the version is read before any DDL, so a schema-2 store is refused
    with no CREATE sent at all; and an absent schema is still bootstrapped."""
    fake = estate.root / "pgfake"
    fake.mkdir()
    (fake / "psql").write_text(FAKE_PSQL)
    (fake / "psql").chmod(0o755)
    log = estate.root / "psql.jsonl"
    wpw = estate.config / "writer.pgpass"
    wpw.write_text("*:*:*:*:x\n")
    wpw.chmod(0o600)
    estate.write_config(f"url=postgresql://lanes_writer@db.invalid/qa\npassfile={wpw}\n"
                        f"reader_url=postgresql://lanes_reader@db.invalid/qa\n")
    vfile = estate.root / "pg-version"
    env = {"PATH": estate.path_with(fake), "FAKE_PSQL_LOG": str(log),
           "FAKE_PSQL_VERSION_FILE": str(vfile)}
    vfile.write_text("2\n")
    res = estate.index("sync", env=env)
    assert res.returncode == 1 and "unknown-schema" in res.stderr, res.stderr
    calls = [json.loads(l)["stdin"] for l in log.read_text().splitlines()]
    assert calls and not any("CREATE" in c or "INSERT" in c for c in calls), calls
    log.unlink()
    vfile.write_text("")
    res = estate.index("sync", env=env)
    assert res.returncode == 0, res.stderr
    calls = [json.loads(l)["stdin"] for l in log.read_text().splitlines()]
    assert sum("CREATE TABLE IF NOT EXISTS" in c for c in calls) == 1
    assert sum("INSERT INTO lanes" in c for c in calls) == 1


def test_out_belongs_to_export_alone(estate):
    """`--out` is `export`'s, as `--dry-run` is `reconcile`'s (Copilot round 2
    on #164): `sync --out <dir>` is a usage error, not a silent write."""
    out = estate.root / "exp"
    out.mkdir()
    for verb in ("sync", "reconcile", "status"):
        res = estate.index(verb, "--out", out)
        assert res.returncode == 64 and "unknown argument" in res.stderr, (verb, res.stderr)
    assert not estate.sqlite.exists()


def test_a_fetch_that_falls_back_keeps_the_read_line_off_stdout(estate):
    """`lanes --fetch --index` WHERE THE FETCH FALLS BACK (14(b); Copilot round
    3 on #164): the wrapper prints the helper's notes on stdout under that
    footer, and the `read:` line is not one of them - it is said once, on
    stderr, and the listing is the source read's."""
    assert estate.index("sync").returncode == 0
    # THE HELPER IN THAT STATE, as the shell suite builds it: it says the fetch
    # fell back, on stderr, and answers from the local refs, exit 0.
    stub = estate.root / "fetchfallback"
    stub.write_text("#!/usr/bin/env bash\n"
                    "if [ \"${1-}\" = lanes ]; then\n"
                    "  printf 'lanes-edit: fetch failed — reading the logs as they stand locally\\n' >&2\n"
                    "  shift; ff=()\n"
                    "  for a in \"$@\"; do [ \"$a\" = --fetch ] || ff+=(\"$a\"); done\n"
                    f"  exec bash {LANES_EDIT} lanes ${{ff[@]+\"${{ff[@]}}\"}}\n"
                    "fi\n"
                    f"exec bash {LANES_EDIT} \"$@\"\n", encoding="utf-8")
    stub.chmod(0o755)
    env = {"LANES_EDIT": str(stub)}
    src = estate.run("bash", LANES, "--all", "--fetch", env=env)
    idx = estate.run("bash", LANES, "--all", "--fetch", "--index", env=env)
    assert "reading the logs as they stand locally" in src.stdout, src.stdout
    assert idx.stderr.count("read: index (sqlite)") == 1, idx.stderr
    assert "read: " not in idx.stdout, idx.stdout
    assert idx.returncode == src.returncode
    assert normal(idx.stdout, estate.root) == normal(src.stdout, estate.root)


def test_no_inherited_password_file_reaches_psql(estate):
    """THE CONFIGURED PASSWORD FILE OR NONE (14(c); Copilot on #164): an
    inherited `PGPASSFILE` is never handed on. With `passfile=` set, libpq is
    given that file; without one, an EMPTY 0600 file of the indexer's own -
    never the inherited file, and never `~/.pgpass` by default."""
    fake = estate.root / "pgfake"
    fake.mkdir()
    (fake / "psql").write_text(FAKE_PSQL)
    (fake / "psql").chmod(0o755)
    log = estate.root / "psql.jsonl"
    ambient = estate.root / "ambient.pgpass"
    ambient.write_text("*:*:*:*:the-wrong-secret\n")
    ambient.chmod(0o600)
    estate.write_config("url=postgresql://lanes_writer@db.invalid/qa\n"
                        "reader_url=postgresql://lanes_reader@db.invalid/qa\n")
    env = {"PATH": estate.path_with(fake), "FAKE_PSQL_LOG": str(log),
           "PGPASSFILE": str(ambient), "PGPASSWORD": "inherited"}
    assert estate.index("sync", env=env).returncode == 0
    assert estate.index("status", env=env).returncode == 0
    calls = [json.loads(l) for l in log.read_text().splitlines()]
    assert calls and not any(c["pgpassword"] for c in calls)
    used = {c["passfile"] for c in calls}
    assert len(used) == 1 and str(ambient) not in used, used
    empty = Path(used.pop())
    assert empty.parent == estate.state / "openRepoTools", empty
    assert empty.read_text() == "" and stat.S_IMODE(empty.stat().st_mode) == 0o600


def test_an_unreachable_store_writes_nothing_waits_on_nothing_and_says_so(estate):
    fake = estate.root / "pgfake"
    fake.mkdir()
    (fake / "psql").write_text("#!/bin/sh\necho 'psql: error: could not connect' >&2\nexit 2\n")
    (fake / "psql").chmod(0o755)
    pw = estate.config / "pgpass"
    pw.write_text("*:*:*:*:x\n")
    pw.chmod(0o600)
    estate.write_config(f"url=postgresql://lanes_writer@db.invalid/qa\npassfile={pw}\n"
                        f"reader_url=postgresql://lanes_reader@db.invalid/qa\n")
    env = {"PATH": estate.path_with(fake)}
    t0 = time.monotonic()
    res = estate.index("sync", env=env)
    assert res.returncode == 1 and "unreachable" in res.stderr
    assert time.monotonic() - t0 < 30
    st = estate.index("status", env=env)
    assert st.returncode == 1
    assert "unreachable" in st.stdout
    assert "could not connect" in st.stdout


def test_status_says_the_lag_and_a_second_sync_waits_for_nobody(estate):
    assert estate.index("sync").returncode == 0
    assert estate.note("repoA-1", "unindexed").returncode == 0
    st = estate.index("status")
    assert st.returncode == 0, st.stderr
    assert "lag:         1 commit(s)" in st.stdout
    assert "last error:  none" in st.stdout
    # ONE SYNC AT A TIME: a sync that finds the lock held returns at once and
    # leaves the holder a mark to sync again.
    import fcntl
    lock = estate.state / "openRepoTools" / "lanes-index.lock"
    with open(lock, "a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        t0 = time.monotonic()
        busy = estate.index("sync")
        assert time.monotonic() - t0 < 10
    assert busy.returncode == 0 and "another sync holds" in busy.stdout
    assert (estate.state / "openRepoTools" / "lanes-index.rerun").exists()
    assert estate.index("sync").returncode == 0
    assert not (estate.state / "openRepoTools" / "lanes-index.rerun").exists()


def test_export_never_creates_a_store_and_the_store_is_private(estate):
    out = estate.root / "exp"
    out.mkdir()
    res = estate.index("export", "--out", out)
    assert res.returncode == 3
    assert (out / "why").read_text().startswith("missing:")
    assert not estate.sqlite.exists()
    assert estate.index("sync").returncode == 0
    assert stat.S_IMODE(estate.sqlite.stat().st_mode) & 0o077 == 0
    assert estate.index("sync", "--source", "ledger:Eagle").returncode == 2
    assert estate.index("sync", "--source", "register:someone/else").returncode == 2
    assert estate.index("bogus").returncode == 64
