# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 5 and AT-C8: the renderer's git half and its push
(L2-G1; L2-G5's C8; AT-5; AT-C8; T270; FR-044, FR-045, FR-046, FR-059)
(opensoft/openRepoTools#165).

T270 writes 25 tests: AT-5's 23 and AT-C8's one are here (TP:1016-1246,
TP:3173-3196, at the test plan `8702b70a`). Its 25th, test 1's part G,
`test_the_mirror_on_origin_equals_a_full_render_after_each_write`, is in
`test_sql_register_render.py`, which line W4b owns; it is not here.

THE ESTATE (AT-5, "Fixture"; AT-C8, "Fixture"). Each case's database is
`pg_imported` (T227b): test 7's register imported at seq 0, the switch at
`files`. Its origin is a bare copy of the session's `imported_register`
origin, at C, so a case that pushes pushes to its own. The estate goes to
`primary` by AT-LR006's route (TP:4610-4615), as T304's own test does: a
`cutover` entry at seq 1 through `commit_write`, as REGISTER-WRITER, which
creates `lanes/STORE` with D21's fields; the marker commit, C plus that
`lanes/STORE` (SQL's own `render_file` of it), with `Register-Seq: 1`,
pushed to origin's `main` by hand; then `record_marker`. That is the open
point 27 form, "AT-5's `files` case pushes the marker commit by hand and
needs only the renderer's side", taken for `primary` too, so no case here
waits for lane 3's T327 (the cutover's own push). `n`, the head after the
cutover, is 1. Lane checkouts are clones of that origin, each with its own
`$HOME`, `workspace.yaml` naming a view of it, and `LANES_REPO` at it (test
7's `Workspace` form). That view is W. A lane whose writes fork the
renderer also has its own register checkout `<c>`, `<W>-lanes/<lane>/`,
made by `lanes-edit.sh lane-checkout <lane> --create`, since on primary
each write goes through it whatever `LANES_REPO` says, and its fork
renders there (T270e; `RenderEstate.own_checkout`).

ENTRIES "WRITTEN THROUGH THE WRITE PATH" (TP:1055-1056) come two ways:
- by `commit_write` as REGISTER-WRITER, the write path's SQL half (T107),
  where the case then starts the renderer itself, as a fork starts it,
  `lanes-index render --checkout <c>` in a session of its own. Each of
  these cases tests the renderer, never the writer or the fork;
- by `lanes-edit.sh log NOTED` on `primary` through T203's flipped copy,
  whose fork starts the renderer (lane 4's T415 and T416, L4-B13), where
  the oracle is about writers and forks (the writer- and fork-side cases,
  at the end).

TEST 5'S `git` WRAPPER (TP:1059-1082; open point 8, TP:8792-8812) is first
on the `PATH` of every `lanes-index` and `lanes-edit.sh` run here. It logs
each call as a JSON line: its subcommand, argv, pid, the pid above it (the
renderer) with that process's start time as `ps -o lstart=` gives it, the
repository it runs in, the time, and the environment's
`GIT_SSH_COMMAND`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`,
`SSH_AUTH_SOCK`, `LANES_NO_FETCH` and `GIT_INDEX_FILE`. Its arms, each on
one subcommand, and on one repository where `where` names it: `hold` on a
FIFO (re-armed per call, `times` bounding it); `kill`, SIGKILL to the
renderer's process group, after leaving `<GIT_INDEX_FILE>.lock` where
`index_lock` asks, as git inside `read-tree` leaves it; `fail`, exit 1;
`reject`, git's non-fast-forward refusal with exit 1, N times, then
disarmed; `stall`, a sleep before the real git. `render_only` limits an
arm to the calls of a `lanes-index render --checkout`, by the command line
of the process above the call (`ps -ww -o command=`), which the log keeps
as `render`, true or false. `redirect` sends a
`fetch` or `push` of a GitHub URL to the bare origin in its place.
Section 3.2's `psql` shim is beside it, handing every call to the
engine's own `psql` by its path.

THE PATH: every directory of the caller's `PATH` is kept, in its place; one
that holds a `psql`, a `lanes-index` or a `pg_` name is swapped for a
private mirror without them (`_masked_path`, lane 2's mask policy, as LX's
T253e has it). The case's own `psql` is the shim, in the estate's `bin`.

THE WAITS. A case that starts the renderer itself waits for its exit. A
render forked by a write is waited for by open point 8's two waits, and no
other: a poll of `status` every 100 ms until its lag is 0, under 30 s,
each poll after the harness's own fetch of the W `status` reads; or,
where the lag must stay above 0, a wait for every renderer pid the wrapper
logged after the write to exit.

WHAT EACH FAILS UNTIL. Every case fails until lane 3's T320 to T323 (the
push, the lock and its handshake, the pass, its bounds); line R holds them
at `refs/l1/V-round4`. `test_six_lost_races_leave_the_last_write_for_the_
next_write_or_reconcile`, which T325's verify selects by `reconcile`, also
fails until T325, at its own assertion: until then `reconcile` on `primary`
is T117's read-only check. The cases whose writes fork the renderer, at the end,
also fail until lane 4's T415 and T416 (L4-B13). Every case is RE: without
PostgreSQL 16 it skips with T205's banner.

COPIED, NEVER SHARED (lane 2's rule for wave 12): `_masked_path` from line
LX's T253e (`tests/test_sql_register_landing_expired.py`); `_rows`, the
`Workspace` form of a lane checkout, and T203's flipped copy with
`lanes-edit.sh` beside it (`flipped_indexer`) from line W3a's
`tests/test_sql_register_import.py`; the cutover entry and the commit call
from line RB's `tests/test_sql_register_rollback.py`; `_open_when_held`
from the same; `_stats` from the import module.

READINGS, NOT FOUND IN A CONTRACT:
- AT-LR006'S ROUTE to `primary`, and the marker commit pushed by hand, as
  above.
- "WRITTEN THROUGH THE WRITE PATH" is read as the commit call alone where
  the oracle is the renderer's, so those cases start the renderer
  themselves. The six-lost-races case is one: the renderer that loses six
  races is started as a fork starts it, for its one write.
- `reconcile` "in the given checkout" (B14 tasks:1531) is read as
  `lanes-index reconcile` run in the lane's checkout, its workspace root,
  with the `mode=primary` configuration, and no `--checkout`.
- AT DEPTH 0 "no `--skip`" (TP:1198-1199) is read as no page after the
  first: the walk's one `log` call may say `--skip 0`, as line R's does.
- THE COMMIT'S MESSAGE: "each message equals its journal entry's" is read
  through T322's form: the entry's message, then `Register-Seq: <k>`, in its
  final trailer block where its last paragraph is one, or as a new last
  paragraph after one blank line.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import REPO, WINDOWS_SKIP
from sql_register_helpers import PSQL_SHIM, PSQL_SHIM_CONTROL, PSQL_SHIM_LOG, flipped_copy

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280's reader, `tests/sql_register_gate.py`; T281
#: removes it in the last set). Every id here waits for T270's own fails-until,
#: T320 to T323, T325 and L4-B13, which is lane 4's T415 (the author) and T416
#: (the fork), and for T227, whose T227b makes `pg_imported` and
#: `pg_cluster.imported_register`, on which every case builds its estate
#: (`_estate`; lane 3, #165 6877365776, point 2). Lane 2's plan GP-24.
SQL_REGISTER_GATE_TABLE = {
    "*": ("T227", "T320", "T321", "T322", "T323", "T325", "T415", "T416"),  # every id: the tasks all its rows share
}

LANES_EDIT = REPO / "lanes-edit.sh"
INDEXER = REPO / "lanes-index"

#: The register's schema, and the role the commit call runs as.
SCHEMA = "lanes_register"
WRITER_ROLE = "lanes_register_writer"

#: Test 7's operator lane, and the two lanes whose checkouts race: `repoW-1`
#: and `repoD-1` are LIVE rows of test 7's register. `OPERATOR` is T227b's
#: `TEST7_OPERATOR` in `tests/pgcluster.py`, written out here: a name imported
#: from there at module level fails this module's collection wherever T227 has
#: not landed, and no landing gate skips a collection error (lane 3, #165
#: 6877365776, point 2). Each case checks that the two agree
#: (`_operator_is_test7s`).
OPERATOR = "repoA-2"
L1, L2 = "repoW-1", "repoD-1"
WS = "Eagle"
AUTHOR = "T270 writer <t270@example.invalid>"
OPERATOR_AUTHOR = "T270 operator <t270-operator@example.invalid>"
NOT_AFTER = "2100-01-01T00:00:00Z"
ARGS_SHA256 = "a" * 64
STORE_UTC = "2026-11-11T10:00:00Z"
#: The file the commit-call entries append to.
APPENDED = "lanes/LANES.md"

#: A commit's `Register-Seq` trailer, `status`'s lag at `primary`, and its
#: divergence and failed-pass lines (lane 1's T117; line R).
REGISTER_SEQ = re.compile(r"^Register-Seq: ([0-9]+)$", re.M)
LAG = re.compile(r"^\s*lag:\s+([0-9]+) seq", re.M)
DIVERGED = re.compile(r"diverged at ([0-9a-f]{40})")
FAILED_PASS = re.compile(r"^\s*renderer:\s+its last failed pass", re.M)

#: Open point 8's ceiling and poll.
CEILING, POLL = 30.0, 0.1

#: The GitHub repository the deploy-key case names, by HTTPS and by SSH.
GITHUB_REPO = "opensoft/t270-mirror"
GITHUB_HTTPS = f"https://github.com/{GITHUB_REPO}.git"
GITHUB_SSH = f"ssh://git@github.com/{GITHUB_REPO}.git"

#: The environment no case inherits.
DROPPED = ("LANES_", "CLAUDE_", "WORKBENCHES_", "TMUX", "XDG_", "PG", "AGENT_PROTOCOL_ROOT",
           "PROJECTS_", "GIT_", "SSH_", "FAKE_PSQL", "RULE6_", "OPENREPOTOOLS_")

#: The subcommands that would rewrite history, which no render may run.
REWRITES = ("rebase", "pull", "cherry-pick", "am", "reset", "merge", "commit")


# ------------------------------------------------------------------ the PATH mask
#: `_masked_path`'s mirrors, by each directory's real path (None where the
#: directory holds no masked name), and the one temporary root they share.
#: Copied from line LX's T253e.
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


# ------------------------------------------------------------------ small helpers
def _script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _private(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    return path


def _said(proc) -> str:
    return (f"exit {proc.returncode}\n--- stdout ---\n{(proc.stdout or '')[-3000:]}"
            f"\n--- stderr ---\n{(proc.stderr or '')[-3000:]}")


def _jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stats(samples: list) -> dict:
    """Section 5.3's statistics: median and p95 by nearest rank, min-max, n.
    Copied from the import module."""
    ordered = sorted(samples)
    rank = lambda p: ordered[max(0, -(-p * len(ordered) // 100) - 1)]  # noqa: E731
    return {"median": rank(50), "p95": rank(95), "min": ordered[0], "max": ordered[-1],
            "n": len(ordered)}


def _open_when_held(fifo: Path, proc: subprocess.Popen, seconds: float = 120):
    """The FIFO's write end, opened once a reader holds a call on it; None
    where `proc` ends, or the time runs out, first. Closing it releases the
    call. Copied from line RB's rollback module."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and proc.poll() is None:
        try:
            return os.open(str(fifo), os.O_WRONLY | os.O_NONBLOCK)
        except OSError:
            time.sleep(0.05)
    return None


def _lock_is_free(path: Path) -> bool:
    """A non-blocking `flock` on `path` succeeds (D14; [L4-4])."""
    import fcntl
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    finally:
        os.close(fd)


def _flipped(directory: Path) -> Path:
    """T203's flipped copy, `RENDER_GIT_HALF = True`, with `lanes-edit.sh`
    and `repos.tsv` beside it (the copy rule, CLI4.5 section 6), so a
    `mode=primary` configuration loads and a render runs. Copied from line
    W3a's `flipped_indexer`."""
    copy = flipped_copy(INDEXER, directory, True)
    for name in ("lanes-edit.sh", "repos.tsv"):
        if (REPO / name).exists():
            shutil.copy2(REPO / name, copy.parent / name)
    return copy


# ------------------------------------------------------------------ the wrapper
GIT_WRAPPER = r'''#!/usr/bin/env -S python3 -I
# TEST 5'S `git` WRAPPER (TP:1059-1082; open point 8, TP:8792-8812), first on
# the renderer's PATH, standard library only. Each call is one JSON line of
# git-wrapper.log beside it; git-wrapper.json beside it holds `git` (the real
# git, by its path), `arms` and `redirect`.
import fcntl, json, os, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL = os.path.join(HERE, "git-wrapper.json")
LOG = os.path.join(HERE, "git-wrapper.log")
STATE = os.path.join(HERE, "git-wrapper.state")
WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
              "--config-env"}
ENV_KEYS = ("GIT_SSH_COMMAND", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "SSH_AUTH_SOCK",
            "LANES_NO_FETCH", "GIT_INDEX_FILE")
NETWORK = ("fetch", "push", "ls-remote", "pull")


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


def where(args):
    """The repository the call runs in: its cwd, moved by each `-C`."""
    found = os.getcwd()
    i = 0
    while i < len(args):
        if args[i] == "-C" and i + 1 < len(args):
            found = os.path.join(found, args[i + 1])
            i += 2
        elif args[i] in WITH_VALUE:
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            break
    return os.path.realpath(found)


def started(pid):
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    return " ".join(out.split())


def is_render(pid):
    """Whether the process above the call is a `lanes-index render
    --checkout`, by its command line; only that answer is kept."""
    try:
        out = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return " render --checkout " in " %s " % " ".join(out.split())


def log(record):
    with open(LOG, "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps(record) + "\n")
        handle.flush()


def take(index, times):
    """Whether arm `index` takes this call: a count per arm, under a lock;
    `times` below 0 takes every call."""
    with open(STATE, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        text = handle.read()
        counts = json.loads(text) if text.strip() else {}
        used = counts.get(str(index), 0)
        if times >= 0 and used >= times:
            return False
        counts[str(index)] = used + 1
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(counts))
        return True


def applies(arm, sub, args, here, render):
    if arm.get("sub") != sub:
        return False
    if arm.get("where") and os.path.realpath(arm["where"]) != here:
        return False
    if arm.get("has") and arm["has"] not in args:
        return False
    if arm.get("render_only") and not render:
        return False
    return True


def main():
    args = sys.argv[1:]
    with open(CONTROL, encoding="utf-8") as handle:
        control = json.load(handle)
    sub = subcommand(args)
    here = where(args)
    parent = os.getppid()
    record = {"sub": sub, "argv": args, "pid": os.getpid(), "renderer": parent,
              "renderer_start": started(parent), "render": is_render(parent), "where": here,
              "env": {key: os.environ.get(key) for key in ENV_KEYS}, "t0": time.time()}
    for index, arm in enumerate(control.get("arms", [])):
        if (not applies(arm, sub, args, here, record["render"])
                or not take(index, arm.get("times", -1))):
            continue
        do = arm["do"]
        if do == "hold":
            log(dict(record, outcome="held"))
            with open(arm["fifo"], "rb") as fifo:
                fifo.read()
        elif do == "stall":
            log(dict(record, outcome="stalled"))
            time.sleep(float(arm.get("seconds", 5)))
        elif do == "fail":
            log(dict(record, outcome="failed", rc=1))
            sys.stderr.write("fatal: the test's git wrapper fails this %s\n" % sub)
            return 1
        elif do == "reject":
            log(dict(record, outcome="rejected", rc=1))
            refspec = next((a for a in reversed(args) if ":" in a and not a.startswith("-")),
                           "HEAD")
            dest = args[args.index(refspec) - 1] if refspec in args else "origin"
            if "--porcelain" in args:
                sys.stdout.write("To %s\n!\t%s\t[rejected] (non-fast-forward)\nDone\n"
                                 % (dest, refspec))
            sys.stderr.write(" ! [rejected]        %s (non-fast-forward)\nerror: failed to "
                             "push some refs to '%s'\nhint: Updates were rejected because "
                             "the remote contains work that you do not have locally.\n"
                             % (refspec, dest))
            return 1
        elif do == "kill":
            index_file = os.environ.get("GIT_INDEX_FILE")
            if arm.get("index_lock") and index_file:
                open(index_file + ".lock", "a").close()
            log(dict(record, outcome="killed"))
            # The renderer's own group where it leads one (a detached fork, or
            # a case's render in a session of its own); else the renderer
            # alone. Each git call runs in a group of its own (`_run_bounded`),
            # so this call, which stands for git, then ends itself.
            if os.getpgid(parent) == parent:
                os.killpg(parent, signal.SIGKILL)
            else:
                os.kill(parent, signal.SIGKILL)
            os.kill(os.getpid(), signal.SIGKILL)
            return 137
    command = [control["git"]]
    redirect = control.get("redirect") or {}
    if sub in NETWORK:
        for url, path in sorted(redirect.items()):
            command += ["-c", "url.%s.insteadOf=%s" % (path, url)]
        args = [redirect.get(arg, arg) for arg in args]
    ran = time.time()
    rc = subprocess.run(command + args).returncode
    log(dict(record, outcome="ran", rc=rc, ran=ran, t1=time.time()))
    return rc


sys.exit(main())
'''

#: Test 4's start barrier (TP:886-888): the launcher blocks on the FIFO it is
#: given until the test opens and closes it, then becomes the command.
LAUNCH = r'''#!/usr/bin/env -S python3 -I
import os, sys
with open(sys.argv[1], "rb") as fifo:
    fifo.read()
os.execv(sys.argv[2], sys.argv[2:])
'''


def _rows(db, sql: str) -> list:
    """`sql`'s rows as JSON objects, read in the register's schema, by
    `jsonb_agg`, whose text is one line. Copied from the import module."""
    out = db.psql(f"SET search_path TO {SCHEMA};\n"
                  f"SELECT coalesce(jsonb_agg(t), '[]'::jsonb) FROM ({sql}) t;\n").stdout
    return json.loads(out.strip().splitlines()[-1])


# ------------------------------------------------------------------ the estate
class RenderEstate:
    """TEST 5'S ESTATE: see the module's docstring. `stage` is `primary` (the
    default), `imported` (seq 0, the switch at `files`) or `empty` (no
    journal, on `pg`). At `primary`, `marker` is `pushed`, or `recorded` for
    a marker commit `record_marker` names that is not on origin's `main`."""

    def __init__(self, root: Path, db, cluster, *, stage: str = "primary",
                 marker: str = "pushed"):
        assert stage in ("primary", "imported", "empty"), stage
        source = cluster.imported_register
        if source is None:
            pytest.fail(f"no imported register on the session cluster: "
                        f"{cluster.imported_problem}", pytrace=False)
        self.root, self.db, self.stage = root, db, stage
        root.mkdir(parents=True, exist_ok=True)
        masked = _masked_path()
        self.real_git = shutil.which("git", path=masked)
        assert self.real_git, "no git on PATH"
        self.bin, self.fakebin = root / "bin", root / "fakebin"
        _script(self.bin / "git", GIT_WRAPPER)
        _script(self.bin / "psql", PSQL_SHIM)
        _script(self.bin / "launch", LAUNCH)
        _script(self.fakebin / "tmux", "#!/bin/sh\nexit 1\n")
        self.copy = _flipped(root / "flip")
        env = {k: v for k, v in os.environ.items() if not k.startswith(DROPPED)}
        env.update(TMPDIR=str(root / "tmp"), LANES_WORKSTATION=WS, LANES_HOST="eagle",
                   LANES_OS="linux", LANES_CONTAINER="none", LANES_IN_CONTAINER="0",
                   LANES_NO_GITHUB="1", LANES_EDIT=str(self.copy.parent / "lanes-edit.sh"),
                   GIT_AUTHOR_NAME="T270 estate", GIT_AUTHOR_EMAIL="t270@example.invalid",
                   GIT_COMMITTER_NAME="T270 estate", GIT_COMMITTER_EMAIL="t270@example.invalid",
                   PATH=os.pathsep.join([str(self.bin), str(self.fakebin), masked]))
        (root / "tmp").mkdir(exist_ok=True)
        self.env = env
        #: The test's own git calls: the real git, no wrapper on PATH.
        self.plain_env = dict(env, PATH=os.pathsep.join([str(self.fakebin), masked]))
        self.arm()
        self.c = source.c
        self.origin = root / "origin.git"
        self.git(None, "clone", "-q", "--bare", str(source.origin), str(self.origin))
        assert self.origin_tip() == self.c, "the imported register's origin is not at C"
        self.label = self.switch()["database_label"]
        self.conf_dir = root / "conf"
        self.passfile = _private(self.conf_dir / "empty.pgpass", "")
        self.index_conf = self.config("index", "index")
        self.primary_conf = self.config("primary", "primary")
        self.checkouts: dict = {}
        head = self.head()
        if stage == "empty":
            assert head == -1, f"`pg`'s journal is not empty: head {head}"
        else:
            assert head == 0 and self.switch()["mode"] == "files", (
                f"`pg_imported` is not test 7's register at seq 0 at files: head {head}, "
                f"switch {self.switch()}")
        self.n = head
        self.marker = None
        if stage == "primary":
            self._to_primary(marker)

    # ------------------------------------------------------------ git
    def git(self, cwd, *args: str, env: dict | None = None, data: bytes | None = None) -> str:
        proc = subprocess.run([self.real_git, *args], cwd=str(cwd) if cwd else None,
                              env=env or self.plain_env, input=data, capture_output=True,
                              timeout=300, check=False)
        assert proc.returncode == 0, (f"git {' '.join(args[:4])}: "
                                      f"{proc.stderr.decode('utf-8', 'replace')[-800:]}")
        return proc.stdout.decode("utf-8", "replace")

    def origin_git(self, *args: str, env: dict | None = None, data: bytes | None = None,
                   origin: Path | None = None) -> str:
        """git in a bare origin itself, so no clone's refs move."""
        return self.git(None, f"--git-dir={origin or self.origin}", *args, env=env, data=data)

    def origin_tip(self, origin: Path | None = None) -> str:
        return self.origin_git("rev-parse", "refs/heads/main", origin=origin).strip()

    def commit_in_origin(self, parent: str, files: dict, message: str,
                         origin: Path | None = None) -> str:
        """A commit on `parent` with `files` ({path: bytes}) changed, made in
        the bare origin through an index of its own; no ref moves."""
        index = self.root / f"build-{uuid.uuid4().hex[:8]}.index"
        env = dict(self.plain_env, GIT_INDEX_FILE=str(index))
        self.origin_git("read-tree", parent, env=env, origin=origin)
        for path, data in files.items():
            blob = self.origin_git("hash-object", "-w", "--stdin", data=data, origin=origin).strip()
            self.origin_git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}",
                            env=env, origin=origin)
        tree = self.origin_git("write-tree", env=env, origin=origin).strip()
        return self.origin_git("commit-tree", tree, "-p", parent, data=message.encode("utf-8"),
                               origin=origin).strip()

    def push_by_hand(self, commit: str, origin: Path | None = None) -> None:
        """Origin's `main` moved to `commit`, a fast-forward, as a push makes it."""
        old = self.origin_tip(origin)
        self.origin_git("merge-base", "--is-ancestor", old, commit, origin=origin)
        self.origin_git("update-ref", "refs/heads/main", commit, old, origin=origin)

    def second_origin(self, name: str) -> Path:
        """A bare copy of origin as it stands."""
        path = self.root / f"{name}.git"
        self.git(None, "clone", "-q", "--bare", str(self.origin), str(path))
        return path

    def commits_after(self, old: str, origin: Path | None = None) -> list:
        """[(sha, its Register-Seq values, its raw message)] on origin's
        `main`'s first-parent line after `old`, oldest first."""
        out = self.origin_git("rev-list", "--reverse", "--first-parent",
                              f"{old}..refs/heads/main", origin=origin)
        found = []
        for sha in out.split():
            raw = self.origin_git("cat-file", "commit", sha, origin=origin)
            message = raw.split("\n\n", 1)[1] if "\n\n" in raw else ""
            found.append((sha, [int(s) for s in REGISTER_SEQ.findall(message)], message))
        return found

    def identity(self, sha: str, origin: Path | None = None) -> dict:
        out = self.origin_git("log", "-1", "--format=%an <%ae>%x00%at%x00%cn <%ce>%x00%ct", sha,
                              origin=origin).rstrip("\n").split("\0")
        return {"author": out[0], "author_epoch": int(out[1]), "committer": out[2],
                "committer_epoch": int(out[3])}

    def form_c(self, sha: str, origin: Path | None = None) -> str:
        """Form C on one commit, with the walk's pins (Y:2843-2847)."""
        out = self.origin_git("-c", "trailer.separators=:", "-c", "core.commentChar=#",
                              "log", "-n", "1",
                              "--format=%(trailers:key=Register-Seq,valueonly)", sha,
                              origin=origin)
        return next((line.strip() for line in out.split("\n") if line.strip()), "")

    # ------------------------------------------------------------ the database
    def rows(self, sql: str) -> list:
        return _rows(self.db, sql)

    def sql(self, script: str, role: str | None = None) -> subprocess.CompletedProcess:
        head = f"SET search_path TO {SCHEMA};\n" + (f"SET ROLE {role};\n" if role else "")
        return self.db.psql(head + script, check=False)

    def head(self) -> int:
        return self.rows("SELECT seq FROM register_head")[0]["seq"]

    def window(self) -> int:
        return self.rows("SELECT version FROM schema_version")[0]["version"]

    def switch(self) -> dict:
        return self.rows("SELECT * FROM register_switch")[0]

    def mirror(self) -> dict:
        return self.rows("SELECT * FROM mirror_state")[0]

    def journal(self, after: int = -1) -> list:
        return self.rows(f"SELECT seq, kind, message, author, "
                         f"extract(epoch FROM utc)::bigint AS epoch FROM journal "
                         f"WHERE seq > {after} ORDER BY seq")

    def render_sql(self, path: str) -> bytes:
        """SQL's own render of `path` at the head (lane 1's T107)."""
        quoted = path.replace("'", "''")
        rows = self.rows(f"SELECT encode(render_file('{quoted}'), 'hex') AS hex")
        return bytes.fromhex(rows[0]["hex"])

    def commit_entries(self, bodies: list) -> list:
        """THE COMMIT CALL, as a writer sends it (section 1.3's step 3): one
        SERIALIZABLE transaction around `commit_write` per entry, as
        REGISTER-WRITER, in one `psql`. Returns the entries' seqs."""
        head, window = self.head(), self.window()
        generation = self.switch()["generation"]
        script = []
        for n, body in enumerate(bodies):
            literal = json.dumps(body, ensure_ascii=True).replace("'", "''")
            script += ["BEGIN ISOLATION LEVEL SERIALIZABLE;",
                       f"SELECT commit_write({head + n}, '{uuid.uuid4()}'::uuid, {window}, "
                       f"'{generation}'::uuid, '{literal}'::jsonb);", "COMMIT;"]
        proc = self.sql("\n".join(script) + "\n", WRITER_ROLE)
        assert proc.returncode == 0, f"commit_write refused an entry: {proc.stderr[-1500:]}"
        seqs = [int(word) for word in proc.stdout.split()]
        assert seqs == list(range(head + 1, head + 1 + len(bodies))), (
            f"the commit calls answered {seqs}, not {head + 1} to {head + len(bodies)}")
        return seqs

    def write_sql(self, texts: list, *, lane: str = L1, messages: list | None = None) -> list:
        """One write entry per text, each appending it to `APPENDED`, through
        the commit call alone (no fork). Returns their seqs."""
        data = self.render_sql(APPENDED)
        assert data.endswith(b"\n"), f"SQL's {APPENDED} does not end with a newline"
        bodies = []
        for n, text in enumerate(texts):
            data += text.encode("utf-8") + b"\n"
            bodies.append({
                "journal": {"kind": "write", "verb": "log", "lane": lane, "workstation": WS,
                            "author": AUTHOR, "args_sha256": ARGS_SHA256,
                            "message": messages[n] if messages else f"t270: {text}"},
                "not_after": NOT_AFTER,
                "edits": [{"ord": 1, "op": "append", "path": APPENDED, "new_text": text}],
                "files": [{"path": APPENDED, "present": True, "sha256": _sha256(data),
                           "final_newline": True}]})
        return self.commit_entries(bodies)

    def _to_primary(self, marker: str) -> None:
        """AT-LR006'S ROUTE (TP:4610-4615): the cutover entry at seq 1, the
        marker commit pushed by hand (or only recorded), `record_marker`."""
        tree = self.origin_git("rev-parse", f"{self.c}:lanes").strip()
        lines = ("store=primary", f"database={self.label}", f"import={self.c}",
                 f"lanes-tree={tree}", f"utc={STORE_UTC}")
        data = ("\n".join(lines) + "\n").encode("utf-8")
        message = "t270: the cutover, by AT-LR006's route"
        edits = [{"ord": 1, "op": "create", "path": "lanes/STORE"}]
        edits += [{"ord": n, "op": "append", "path": "lanes/STORE", "new_text": line}
                  for n, line in enumerate(lines, start=2)]
        (cut,) = self.commit_entries([{
            "journal": {"kind": "cutover", "verb": "cutover", "lane": OPERATOR,
                        "workstation": WS, "author": OPERATOR_AUTHOR, "message": message},
            "not_after": NOT_AFTER, "edits": edits,
            "files": [{"path": "lanes/STORE", "present": True, "sha256": _sha256(data),
                       "final_newline": True}]}])
        assert cut == 1, f"the cutover entry took seq {cut}, not 1"
        assert self.render_sql("lanes/STORE") == data, "SQL renders lanes/STORE otherwise"
        self.marker = self.commit_in_origin(self.c, {"lanes/STORE": data},
                                            f"{message}\n\nRegister-Seq: {cut}\n")
        if marker == "pushed":
            self.push_by_hand(self.marker)
        proc = self.sql(f"SELECT record_marker({self.window()}, {cut}, '{self.marker}', "
                        f"'{WS}');", WRITER_ROLE)
        assert proc.returncode == 0 and proc.stdout.strip() == "present", (
            f"record_marker answered {proc.stdout.strip()!r}: {proc.stderr[-800:]}")
        switch = self.switch()
        assert (switch["mode"], switch["marker_state"]) == ("primary", "present"), switch
        self.n = cut

    # ------------------------------------------------------------ configuration
    def config(self, name: str, mode: str, extra=()) -> Path:
        """A 0600 `lanes-index.conf` outside every work tree: `mode`, the two
        URLs on the cluster's socket as its own user, an empty password file,
        the switch's label and the schema, and `extra` lines."""
        lines = [f"mode={mode}", f"register_url={self.db.url()}",
                 f"register_passfile={self.passfile}", f"reader_url={self.db.url()}",
                 f"reader_passfile={self.passfile}", f"register_label={self.label}",
                 f"register_schema={SCHEMA}", *extra]
        return _private(self.conf_dir / name / "lanes-index.conf", "\n".join(lines) + "\n")

    # ------------------------------------------------------------ lane checkouts
    def checkout(self, name: str, lane: str = L1, *, origin: Path | None = None,
                 repository: str | None = None, own: bool = False) -> SimpleNamespace:
        """A lane's register checkout, a clone of `origin`, in test 7's
        `Workspace` form: its own `$HOME`, W a view of the clone that
        `workspace.yaml` names (with `repository:` `repository`, origin's
        path by default), and `LANES_REPO` at the clone. With `own`, for a
        lane whose writes fork the renderer, also the lane's own register
        checkout `<c>` (`own_checkout`), as `.own`."""
        root = self.root / name
        home = root / "home"
        agents = home / ".agents"
        agents.mkdir(parents=True)
        clone = home / "projects" / "wip"
        self.git(None, "clone", "-q", str(origin or self.origin), str(clone))
        view = root / "ro" / "wip"
        view.mkdir(parents=True)
        (view / ".git").write_text(f"gitdir: {os.path.realpath(clone / '.git')}\n",
                                   encoding="utf-8")
        (view / "lanes").symlink_to(clone / "lanes")
        (agents / "workspace.yaml").write_text(
            f"repository: {repository or (origin or self.origin)}\npath: {view}\n",
            encoding="utf-8")
        for d in ("state", "config", "tmp"):
            (root / d).mkdir()
        env = dict(self.env, HOME=str(home), AGENT_PROTOCOL_ROOT=str(agents),
                   XDG_STATE_HOME=str(root / "state"), XDG_CONFIG_HOME=str(root / "config"),
                   TMPDIR=str(root / "tmp"), CLAUDE_CONFIG_DIR=str(home / ".claude"),
                   LANES_REPO=str(clone), LANES_LANE=lane)
        lane_checkout = SimpleNamespace(name=name, lane=lane, root=root, home=home, clone=clone,
                                        git_dir=clone / ".git", env=env, w=view, own=None)
        if own:
            lane_checkout.own = self.own_checkout(lane_checkout)
        self.checkouts[name] = lane_checkout
        return lane_checkout

    def own_checkout(self, lc) -> SimpleNamespace:
        """THE LANE'S OWN REGISTER CHECKOUT ON PRIMARY, `<c>`, `<W>-lanes/<lane>/`
        (T270e), made by `lanes-edit.sh lane-checkout <lane> --create` through the
        flipped copy, as line G's T254s makes it for each primary lane. The estate makes
        `<c>` itself, because `lane-start` makes it only under `LANES_ROUTE_WRITES=1`
        with neither `LANES_REPO` nor `LANES_FILE` set (lane 3, #165 6841265575;
        `dfc4ce4c:lane-start:1209-1210`).

        WHY: on primary, T415's `pw_checkout` takes each write's checkout from
        `lane_checkout_path`, `<W>-lanes/<lane>`, and `LANES_REPO` never enters it
        (lane 4, #165 6840794493: `a38af255:lanes-edit.sh:6273`, `:20738`, `:1673-1674`).
        Where it is not there, the write refuses 2 and nothing is sent. The write's fork
        then renders there, `render --checkout "$PW_C"` (`pw_render_fork`). So the
        render's calls, lock and marks are `<c>`'s. The clone is a fetch, so
        `LANES_NO_FETCH` is left out. Returns `<c>`'s `clone` and `git_dir`."""
        proc = subprocess.run(["bash", str(self.copy.parent / "lanes-edit.sh"), "lane-checkout",
                               lc.lane, "--create"], cwd=str(lc.clone),
                              env=self.lane_env(lc, None, {"LANES_NO_FETCH": None}),
                              capture_output=True, text=True, timeout=300,
                              stdin=subprocess.DEVNULL, check=False)
        assert proc.returncode == 0, f"lane-checkout {lc.lane} --create:\n{_said(proc)}"
        c = Path(proc.stdout.strip().splitlines()[-1])
        expected = Path(os.path.realpath(lc.w) + "-lanes") / lc.lane
        assert c == expected and c.is_dir(), (
            f"lane-checkout {lc.lane} --create made {c}, not {expected}:\n{_said(proc)}")
        git_dir = Path(self.git(c, "rev-parse", "--absolute-git-dir").strip())
        return SimpleNamespace(clone=c, git_dir=git_dir)

    def snapshot(self, lc) -> dict:
        """The checkout's HEAD, index digest and `status --porcelain`, the
        index read first and `status` run with no optional lock, so this
        read never rewrites the index it digests."""
        index = _sha256((lc.git_dir / "index").read_bytes())
        return {"head": self.git(lc.clone, "rev-parse", "HEAD").strip(), "index": index,
                "status": self.git(lc.clone, "--no-optional-locks", "status", "--porcelain")}

    # ------------------------------------------------------------ the wrapper and the shim
    def arm(self, arms=(), redirect: dict | None = None, shim_arms=()) -> None:
        """The wrapper's arms and the shim's, each log and count started
        afresh."""
        for name in ("git-wrapper.log", "git-wrapper.state", PSQL_SHIM_LOG, "psql-shim.ends"):
            (self.bin / name).write_text("", encoding="utf-8")
        (self.bin / "psql-shim.state").write_text("{}", encoding="utf-8")
        control = {"git": self.real_git, "arms": list(arms), "redirect": redirect or {}}
        (self.bin / "git-wrapper.json").write_text(json.dumps(control), encoding="utf-8")
        (self.bin / PSQL_SHIM_CONTROL).write_text(
            json.dumps({"psql": self.db.psql_bin, "arms": list(shim_arms)}), encoding="utf-8")

    def calls(self, sub: str | None = None, lc=None) -> list:
        """The wrapper's log, in order: each call that ran, or that an arm
        took, once (its `ran` line, else its arm's line)."""
        entries = _jsonl(self.bin / "git-wrapper.log")
        ran = {e["pid"] for e in entries if e.get("outcome") == "ran"}
        kept = [e for e in entries if e.get("outcome") == "ran" or e["pid"] not in ran]
        if sub is not None:
            kept = [e for e in kept if e["sub"] == sub]
        if lc is not None:
            kept = [e for e in kept if e["where"] == os.path.realpath(lc.clone)]
        return kept

    # ------------------------------------------------------------ the commands
    def lane_env(self, lc, conf: Path | None, env: dict | None) -> dict:
        child = dict(lc.env, LANES_INDEX_CONFIG=str(conf or self.primary_conf))
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return child

    def render_argv(self, lc) -> list:
        return [sys.executable, str(self.copy), "render", "--checkout", str(lc.clone)]

    def render(self, lc, *, conf: Path | None = None, env: dict | None = None,
               timeout: float = 300) -> subprocess.CompletedProcess:
        """`lanes-index render --checkout <c>`, as a fork starts it: in a
        session of its own, through the flipped copy, with the `mode=primary`
        configuration. Waited for to its exit."""
        return subprocess.run(self.render_argv(lc), cwd=str(lc.clone),
                              env=self.lane_env(lc, conf, env), capture_output=True, text=True,
                              timeout=timeout, stdin=subprocess.DEVNULL, start_new_session=True,
                              check=False)

    def popen_render(self, lc, *, conf: Path | None = None, env: dict | None = None,
                     argv: list | None = None) -> subprocess.Popen:
        return subprocess.Popen(argv or self.render_argv(lc), cwd=str(lc.clone),
                                env=self.lane_env(lc, conf, env), text=True,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)

    def index(self, lc, *args: str, conf: Path | None = None, env: dict | None = None,
              timeout: float = 300) -> subprocess.CompletedProcess:
        """Another `lanes-index` command in the lane's checkout."""
        return subprocess.run([sys.executable, str(self.copy), *args], cwd=str(lc.clone),
                              env=self.lane_env(lc, conf or self.index_conf, env),
                              capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL, check=False)

    def status(self, lc) -> subprocess.CompletedProcess:
        """`lanes-index status` in the lane's checkout: its lag is `n` less
        the `m` origin's `main` carried as last fetched there."""
        return self.index(lc, "status")

    def lag(self, lc) -> int | None:
        found = LAG.search(self.status(lc).stdout)
        return int(found.group(1)) if found else None

    def race(self, checkouts: list, *, conf: Path | None = None) -> list:
        """Test 4's barrier (TP:886-888, TP:1083): one renderer per checkout,
        each launched blocking on a FIFO of its own, released together once
        all are waiting. Returns each one's (returncode, stdout, stderr)."""
        procs, fifos = [], []
        for lc in checkouts:
            fifo = self.root / f"barrier-{lc.name}.fifo"
            os.mkfifo(str(fifo), 0o600)
            fifos.append(fifo)
            procs.append(self.popen_render(lc, conf=conf, argv=[
                sys.executable, "-I", str(self.bin / "launch"), str(fifo), *self.render_argv(lc)]))
        fds = []
        try:
            for fifo, proc in zip(fifos, procs):
                fd = _open_when_held(fifo, proc)
                assert fd is not None, f"a launcher never waited on {fifo}"
                fds.append(fd)
        finally:
            for fd in fds:
                os.close(fd)
        ended = []
        for proc in procs:
            out, err = proc.communicate(timeout=300)
            ended.append(SimpleNamespace(returncode=proc.returncode, stdout=out, stderr=err))
        return ended

    # ------------------------------------------------------------ writes that fork
    def rearm(self, arms=()) -> None:
        """The wrapper's arms changed, its log and counts kept."""
        control = json.loads((self.bin / "git-wrapper.json").read_text(encoding="utf-8"))
        control["arms"] = list(arms)
        (self.bin / "git-wrapper.json").write_text(json.dumps(control), encoding="utf-8")

    def edit(self, lc, *args: str, env: dict | None = None,
             timeout: float = 300) -> subprocess.CompletedProcess:
        """`lanes-edit.sh <args>` in the lane's checkout, as its lane, through
        the flipped copy's `lanes-edit.sh`, with the `mode=primary`
        configuration: a write on `primary`, which forks the renderer (lane
        4's T415 and T416)."""
        return subprocess.run(["bash", str(self.copy.parent / "lanes-edit.sh"), *args],
                              cwd=str(lc.clone), env=self.lane_env(lc, None, env),
                              capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL, check=False)

    def write(self, lc, text: str, env: dict | None = None,
              timeout: float = 300) -> subprocess.CompletedProcess:
        """One `log NOTED lane:<L> <text>` from the lane's checkout."""
        return self.edit(lc, "log", "NOTED", f"lane:{lc.lane}", text, env=env, timeout=timeout)

    def entries(self) -> int:
        """The wrapper log's length, the mark a wait starts after."""
        return len(_jsonl(self.bin / "git-wrapper.log"))

    def render_calls(self, after: int = 0) -> list:
        """The calls a `lanes-index render --checkout` made, logged after the
        mark `after`, each once."""
        entries = _jsonl(self.bin / "git-wrapper.log")[after:]
        ran = {e["pid"] for e in entries if e.get("outcome") == "ran"}
        return [e for e in entries if e.get("render")
                and (e.get("outcome") == "ran" or e["pid"] not in ran)]

    def wait_lag_0(self, lc, what: str) -> None:
        """OPEN POINT 8'S FIRST WAIT: `status` every 100 ms until its lag is
        0, under 30 s, each poll after the harness's fetch of the W `status`
        reads (T270e; lane 3's ruling (a), #165 6833830078):
        `git -C <W> fetch -q origin main`, with plain git, never through the
        wrapper. `status` reads `m` on W's `origin/main` as last fetched and
        never fetches, no write on primary fetches (D12), and the
        render pushes from the lane's `<c>`. The fetch is the harness's own
        act, not a write's, as the drill's `wait_lag_0` has it (DR's
        T276f)."""
        deadline = time.monotonic() + CEILING
        while True:
            self.git(lc.w, "fetch", "-q", "origin", "main")
            if self.lag(lc) == 0:
                return
            if time.monotonic() > deadline:
                shown = self.status(lc)
                pytest.fail(f"{what}: the lag, each read after a fetch of W, is not 0 within "
                            f"{CEILING:g} s:\n{shown.stdout}"
                            f"{shown.stderr[-800:]}", pytrace=False)
            time.sleep(POLL)

    def wait_renders_exit(self, after: int, what: str) -> list:
        """OPEN POINT 8'S SECOND WAIT: under 30 s, a render's call logged
        after the mark `after` (every pass begins with a fetch), then the
        exit of every renderer pid logged after it, a re-fork's included:
        `os.pidfd_open` where it exists, else `os.kill(pid, 0)` beside the
        start time logged, a pid whose start time no longer matches counting
        as exited. Returns the renderer pids."""
        deadline = time.monotonic() + CEILING
        while not self.render_calls(after):
            if time.monotonic() > deadline:
                pytest.fail(f"{what}: no render's call was logged within {CEILING:g} s",
                            pytrace=False)
            time.sleep(POLL)
        seen: dict = {}
        while True:
            for call in self.render_calls(after):
                seen.setdefault(call["renderer"], call["renderer_start"])
            live = [pid for pid, start in seen.items() if not _exited(pid, start)]
            if not live:
                again = {c["renderer"] for c in self.render_calls(after)}
                if again <= set(seen):
                    return sorted(seen)
                continue
            if time.monotonic() > deadline:
                pytest.fail(f"{what}: renderer pids {live} did not exit within {CEILING:g} s",
                            pytrace=False)
            time.sleep(POLL)


def _exited(pid: int, start: str) -> bool:
    """Whether `pid`, which started at `start` (`ps -o lstart=`), is gone."""
    if hasattr(os, "pidfd_open"):
        try:
            fd = os.pidfd_open(pid)
        except ProcessLookupError:
            return True
        except OSError:
            fd = None
        if fd is not None:
            import select
            try:
                poller = select.poll()
                poller.register(fd, select.POLLIN)
                if poller.poll(0):
                    return True
            finally:
                os.close(fd)
    else:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
    now = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True,
                         text=True, check=False).stdout
    return " ".join(now.split()) != start


def _until(predicate, seconds: float) -> bool:
    """`predicate()` polled every 100 ms until it holds, or `seconds` pass;
    its last answer."""
    deadline = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() > deadline:
            return bool(predicate())
        time.sleep(POLL)
    return True


def _held_fd(fifo: Path, what: str, seconds: float = 120) -> int:
    """The FIFO's write end, once the wrapper or the shim holds a call on
    it; the case fails, naming `what`, where none does in time."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            return os.open(str(fifo), os.O_WRONLY | os.O_NONBLOCK)
        except OSError:
            time.sleep(0.05)
    pytest.fail(f"{what}: nothing was held on {fifo.name} within {seconds:g} s", pytrace=False)


def _held_pushes(est: RenderEstate) -> int:
    """The render pushes the wrapper has held so far, each counted by its
    own `held` line in the raw `git-wrapper.log`. Not `render_calls()`,
    which drops a pid's `held` line once its push has run."""
    return sum(1 for c in _jsonl(est.bin / "git-wrapper.log")
               if c.get("render") and c["sub"] == "push" and c.get("outcome") == "held")


def _kth_held_fd(est: RenderEstate, fifo: Path, k: int, what: str,
                 seconds: float = 120) -> int:
    """`_held_fd`, opened only once the raw log holds the `k`-th held
    render push. A pass starts only after the previous push's wrapper has
    exited, so the open lands on the `k`-th push, never on one just
    released whose wrapper has not yet seen EOF (lane 3's #38, #165
    6859801732)."""
    if not _until(lambda: _held_pushes(est) >= k, seconds):
        pytest.fail(f"{what}: the wrapper's log holds {_held_pushes(est)} held render pushes, "
                    f"not {k}, within {seconds:g} s", pytrace=False)
    return _held_fd(fifo, what, seconds)


def _wrote(proc, what: str) -> None:
    assert proc.returncode == 0, (
        f"{what} on primary did not exit 0 (lane 4's T415 and T416, L4-B13):\n{_said(proc)}")


#: Test 7's seed's session of `L1`'s row (pgcluster's `_test7_seed`).
UUID_L1 = "eeeeeeee-0002-4000-8000-00000000e002"


def _operator_is_test7s() -> None:
    """THE OPERATOR'S ONE VALUE: `OPERATOR` equals T227b's `TEST7_OPERATOR`.
    The name is imported here, when a case runs, and never at module level,
    so the module collects where T227 has not landed. Every case here waits
    for T227 anyway, since its estate is built on `pg_imported` and
    `pg_cluster.imported_register`, both T227's. So on a tree without the
    name each case fails here, naming T227, and on a tree whose value
    differs each case fails here, before it asks for the engine."""
    try:
        from pgcluster import TEST7_OPERATOR
    except ImportError as exc:
        pytest.fail(f"tests/pgcluster.py has no TEST7_OPERATOR ({exc}): every case "
                    f"here waits for T227, whose T227b adds it with `pg_imported`",
                    pytrace=False)
    assert OPERATOR == TEST7_OPERATOR, (
        f"this module's OPERATOR {OPERATOR!r} is not pgcluster's TEST7_OPERATOR "
        f"{TEST7_OPERATOR!r} (T227b): change the copy here to match")


def _estate(request, tmp_path: Path, **kw) -> RenderEstate:
    """A `RenderEstate` on `pg_imported`, or `pg` where `stage` is `empty`,
    once `OPERATOR` is checked against T227b's (`_operator_is_test7s`)."""
    _operator_is_test7s()
    stage = kw.get("stage", "primary")
    db = request.getfixturevalue("pg" if stage == "empty" else "pg_imported")
    cluster = request.getfixturevalue("pg_cluster")
    return RenderEstate(tmp_path / "estate", db, cluster, **kw)


def _assert_rendered(est: RenderEstate, old: str, seqs: list, origin: Path | None = None) -> list:
    """THE RACE'S ORACLE (TP:1092-1099): origin's `main` gains exactly one
    commit per seq after `old`, carrying `seqs` in order with none repeated,
    each message the journal entry's with its `Register-Seq` (T322's form),
    and author, committer and both dates the journal's (D15). Returns the
    commits."""
    gained = est.commits_after(old, origin)
    assert [s for _sha, carried, _m in gained for s in carried] == seqs, (
        f"origin's main gained {[(sha[:12], carried) for sha, carried, _m in gained]}, not one "
        f"commit for each of {seqs} in order")
    assert len(gained) == len(seqs), f"origin's main gained {len(gained)} commits for {seqs}"
    journal = {row["seq"]: row for row in est.journal(min(seqs) - 1)}
    for sha, (k,), message in gained:
        entry = journal[k]
        assert message.rstrip("\n") == _with_trailer(entry["message"], k), (
            f"the commit for seq {k} carries {message!r}, not the journal's message "
            f"{entry['message']!r} with Register-Seq: {k} (T322's form)")
        ident = est.identity(sha, origin)
        assert ident == {"author": entry["author"], "author_epoch": entry["epoch"],
                         "committer": entry["author"], "committer_epoch": entry["epoch"]}, (
            f"the commit for seq {k} has {ident}, not the journal's author {entry['author']} "
            f"as author and committer, both at {entry['epoch']} (D15)")
    return [sha for sha, _c, _m in gained]


#: A line of a trailer block, `Token: value` (F29; B14 tasks:1504).
TRAILER_LINE = re.compile(r"[A-Za-z0-9-]+: .*")


def _with_trailer(message: str, k: int) -> str:
    """T322'S FORM (B14 tasks:1504), with no final LF: the entry's message,
    its blank last lines dropped, then `Register-Seq: <k>` as the last line
    of its final trailer block, where it has two paragraphs or more and every
    line of the last is `Token: value`; otherwise as a new last paragraph
    after one blank line."""
    lines = message.split("\n")
    while lines and not lines[-1].strip(" \t"):
        lines.pop()
    paragraphs, current = [], []
    for line in lines:
        if line.strip(" \t"):
            current.append(line)
        elif current:
            paragraphs.append(current)
            current = []
    paragraphs.append(current)
    block = len(paragraphs) >= 2 and all(TRAILER_LINE.fullmatch(line) for line in paragraphs[-1])
    return "\n".join(lines) + ("\n" if block else "\n\n") + f"Register-Seq: {k}"


def _no_rewrite(est: RenderEstate) -> None:
    """The wrapper's log shows no `rebase`, no `pull --rebase` and no other
    command that moves a HEAD (TP:1099; P314-318)."""
    bad = [c["argv"] for c in est.calls() if c["sub"] in REWRITES]
    assert not bad, f"a render ran a command that rewrites or moves a HEAD: {bad}"


def _push_tip(call: dict) -> str:
    """The commit a push call names, from its `<tip>:refs/heads/main`."""
    spec = next((a for a in reversed(call["argv"]) if a.endswith(":refs/heads/main")), "")
    return spec.split(":", 1)[0].lstrip("+")


# =================================================================== AT-5: the race
def test_two_renderers_racing_push_one_commit_per_seq_in_order(request, tmp_path):
    """AT-5's race (TP:1092-1099): `n+1` to `n+5` committed, then two
    renderers, in `L1`'s and `L2`'s checkouts of one bare origin, started
    through test 4's barrier. Origin's `main` gains exactly five commits,
    carrying `n+1` to `n+5` in order with none repeated, each message and
    identity the journal's; both renderers exit 0; and the wrapper's log
    shows no `rebase` and no `pull --rebase`. Fails until T320 to T322."""
    est = _estate(request, tmp_path)
    one, two = est.checkout("L1", L1), est.checkout("L2", L2)
    seqs = est.write_sql([f"race entry {i}" for i in range(1, 6)])
    assert seqs == list(range(est.n + 1, est.n + 6)), seqs
    old = est.origin_tip()
    est.arm()
    ended = est.race([one, two])
    for lc, proc in zip((one, two), ended):
        assert proc.returncode == 0, f"{lc.name}'s renderer:\n{_said(proc)}"
    _assert_rendered(est, old, seqs)
    _no_rewrite(est)


def _held_and_rendered(est: RenderEstate, one, two, seqs: list) -> tuple:
    """`two`'s renderer held at its first push, `one`'s run to its end, then
    `two` released: returns (the commit `two` had built for its push,
    origin's commits for `seqs`, `two`'s exit)."""
    fifo = est.root / f"hold-{two.name}.fifo"
    os.mkfifo(str(fifo), 0o600)
    old = est.origin_tip()
    est.arm([{"sub": "push", "do": "hold", "fifo": str(fifo), "where": str(two.clone),
              "times": 1}])
    held = est.popen_render(two)
    fd = _open_when_held(fifo, held)
    try:
        assert fd is not None, (f"{two.name}'s renderer never reached its push:\n"
                                f"{held.communicate(timeout=60)}")
        proc = est.render(one)
        assert proc.returncode == 0, f"{one.name}'s renderer:\n{_said(proc)}"
    finally:
        if fd is not None:
            os.close(fd)
    out, err = held.communicate(timeout=300)
    first = next(c for c in est.calls("push", two))
    commits = _assert_rendered(est, old, seqs)
    return _push_tip(first), commits, SimpleNamespace(returncode=held.returncode, stdout=out,
                                                      stderr=err)


def test_renderers_make_identical_commits_for_one_seq(request, tmp_path):
    """AT-5's identical commits (TP:1100-1102; P1363-1367): with `n+1`
    committed, `L2`'s renderer is held at its push while `L1`'s renders and
    pushes; the commit `L2` built for `n+1`, the one its push names, is the
    sha `L1` pushed, its author and committer the journal's identity, both
    dated by the entry's commit UTC (D15). Released, `L2` exits 0. Fails
    until T320 to T322."""
    est = _estate(request, tmp_path)
    one, two = est.checkout("L1", L1), est.checkout("L2", L2)
    seqs = est.write_sql(["one seq, two renderers"])
    built, commits, two_ended = _held_and_rendered(est, one, two, seqs)
    assert built == commits[0], (f"L2's renderer built {built} for seq {seqs[0]}, and L1's "
                                 f"pushed {commits[0]}: two renderers made different commits")
    assert two_ended.returncode == 0, f"L2's renderer after the release:\n{_said(two_ended)}"


# =================================================================== AT-5: the kill
def test_a_renderer_killed_by_sigkill_leaves_the_checkout_able_to_render_at_once(request,
                                                                                tmp_path):
    """[L4-4] (TP:1107-1109): the wrapper sends SIGKILL to the renderer's
    process group just before its push. Then a non-blocking `flock` on
    `lanes-render.lock` succeeds at once, no lock directory is left, and,
    with no hand removal, the next render pushes every missing seq in order.
    Fails until T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1)
    seqs = est.write_sql(["killed before its push, 1", "killed before its push, 2"])
    old = est.origin_tip()
    est.arm([{"sub": "push", "do": "kill", "where": str(one.clone), "times": 1}])
    killed = est.render(one)
    assert killed.returncode == -signal.SIGKILL, (
        f"the renderer was not killed at its push:\n{_said(killed)}")
    assert est.origin_tip() == old, "the killed renderer pushed"
    lock = one.git_dir / "lanes-render.lock"
    assert not lock.is_dir(), "a lock directory is left behind"
    assert not [p.name for p in one.git_dir.iterdir()
                if p.is_dir() and p.name.startswith("lanes-render")], "a lock directory is left"
    assert _lock_is_free(lock), "the SIGKILL did not release lanes-render.lock (D14; [L4-4])"
    est.arm()
    proc = est.render(one)
    assert proc.returncode == 0, f"the next render, with no hand removal:\n{_said(proc)}"
    _assert_rendered(est, old, seqs)


def test_a_renderer_killed_inside_read_tree_does_not_block_the_next_render(request, tmp_path):
    """AT-5 (TP:1065-1067, :1223-1224): the wrapper leaves
    `lanes-render.index.lock` behind, as git inside `read-tree` does, and
    sends SIGKILL to the renderer's process group. The lock is free at once,
    and the next render clears the stale `.lock` under the lock and pushes
    every missing seq in order. Fails until T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1)
    seqs = est.write_sql(["killed inside read-tree"])
    old = est.origin_tip()
    est.arm([{"sub": "read-tree", "do": "kill", "index_lock": True, "where": str(one.clone),
              "times": 1}])
    killed = est.render(one)
    assert killed.returncode == -signal.SIGKILL, (
        f"the renderer was not killed inside read-tree:\n{_said(killed)}")
    stale = one.git_dir / "lanes-render.index.lock"
    assert stale.exists(), (f"no {stale.name} was left: the build ran no read-tree under "
                            f"GIT_INDEX_FILE {one.git_dir / 'lanes-render.index'}")
    assert _lock_is_free(one.git_dir / "lanes-render.lock"), "the render lock is still held"
    est.arm()
    proc = est.render(one)
    assert proc.returncode == 0, f"the next render after the stale index lock:\n{_said(proc)}"
    _assert_rendered(est, old, seqs)
    assert not stale.exists(), f"{stale.name} is still there after the next render"


# =================================================================== AT-5: the lost race
def test_a_lost_push_race_never_rebases_a_render(request, tmp_path):
    """P314-318 (TP:1034, :1181): `L1`'s renderer is held at its first push
    while another clone pushes a handoff commit, so the push is rejected as a
    non-fast-forward. The renderer fetches, builds again on the new tip, and
    pushes: origin's `main` is the handoff commit and then one commit per
    seq, in order; the wrapper's log shows two pushes with a fetch between,
    and no `rebase`, `pull` or other command that moves a HEAD; and `L1`'s
    HEAD, index and status are as before. Fails until T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1)
    seqs = est.write_sql(["a lost race, 1", "a lost race, 2"])
    before = est.snapshot(one)
    fifo = est.root / "hold.fifo"
    os.mkfifo(str(fifo), 0o600)
    est.arm([{"sub": "push", "do": "hold", "fifo": str(fifo), "where": str(one.clone),
              "times": 1}])
    held = est.popen_render(one)
    fd = _open_when_held(fifo, held)
    try:
        assert fd is not None, f"the renderer never reached its push:\n{held.communicate()}"
        handoff = est.commit_in_origin(est.origin_tip(), {
            f"handoffs/{L2}.md": b"# a handoff pushed while the render was held\n"},
            "a handoff commit, pushed during the render's push")
        est.push_by_hand(handoff)
    finally:
        if fd is not None:
            os.close(fd)
    out, err = held.communicate(timeout=300)
    assert held.returncode == 0, _said(SimpleNamespace(returncode=held.returncode, stdout=out,
                                                       stderr=err))
    _assert_rendered(est, handoff, seqs)
    pushes = est.calls("push", one)
    assert [p.get("rc") for p in pushes] == [1, 0], (
        f"not one rejected push then one that landed: {[(p['outcome'], p.get('rc')) for p in pushes]}")
    calls = est.calls(lc=one)
    first, second = (calls.index(p) for p in pushes)
    assert any(c["sub"] == "fetch" for c in calls[first + 1:second]), (
        "the renderer pushed again with no fetch after the rejection")
    _no_rewrite(est)
    assert est.snapshot(one) == before, "the render moved L1's HEAD, index or status"


# =================================================================== AT-5: the push (T320)
def test_the_render_push_alone_carries_the_deploy_key(request, tmp_path):
    """D23 (TP:1182-1193): with `render_key=` set, origin named by a GitHub
    HTTPS URL, a global `url.*.insteadOf` rewriting SSH URLs to HTTPS and
    `SSH_AUTH_SOCK` in the case's own environment, the wrapper records the
    push and makes it to the bare origin in its place. The push names
    `ssh://git@github.com/<owner>/<repo>.git` and `<tip>:refs/heads/main`,
    with `--no-verify` and no force; its environment alone carries
    `GIT_SSH_COMMAND` with `-i` the key file, `IdentitiesOnly=yes` and
    `BatchMode=yes`, `GIT_CONFIG_GLOBAL=/dev/null` and
    `GIT_CONFIG_NOSYSTEM=1`, and no `SSH_AUTH_SOCK`; the checkout's
    configuration is unchanged, with no `pushurl`; and the read-back fetches
    `origin`. Fails until T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, repository=GITHUB_HTTPS)
    est.git(one.clone, "remote", "set-url", "origin", GITHUB_HTTPS)
    (one.home / ".gitconfig").write_text(
        '[url "https://github.com/"]\n\tinsteadOf = ssh://git@github.com/\n', encoding="utf-8")
    key = _private(one.root / "keys" / "render_key", "not a key: the git wrapper makes the push\n")
    conf = est.config("deploy-key", "primary", [f"render_key={key}"])
    local_before = est.git(one.clone, "config", "--local", "--list")
    seqs = est.write_sql(["pushed with the deploy key"])
    old = est.origin_tip()
    est.arm(redirect={GITHUB_HTTPS: str(est.origin), GITHUB_SSH: str(est.origin)})
    proc = est.render(one, conf=conf, env={"SSH_AUTH_SOCK": str(one.root / "agent.sock")})
    assert proc.returncode == 0, f"the render with render_key=:\n{_said(proc)}"
    _assert_rendered(est, old, seqs)
    calls = est.calls(lc=one)
    pushes = [c for c in calls if c["sub"] == "push"]
    assert len(pushes) == 1, f"not one push: {[p['argv'] for p in pushes]}"
    push = pushes[0]
    argv = push["argv"]
    assert GITHUB_SSH in argv, f"the push does not name {GITHUB_SSH}: {argv}"
    assert any(a.endswith(":refs/heads/main") and not a.startswith("+") for a in argv), argv
    assert "--no-verify" in argv and not {"-f", "--force", "--force-with-lease"} & set(argv), argv
    ssh = push["env"]["GIT_SSH_COMMAND"] or ""
    words = shlex.split(ssh)
    assert "-i" in words and words[words.index("-i") + 1] == str(key), (
        f"GIT_SSH_COMMAND does not name the key file with -i: {ssh!r}")
    for option in ("IdentitiesOnly=yes", "BatchMode=yes"):
        assert option in ssh, f"GIT_SSH_COMMAND lacks {option}: {ssh!r}"
    assert (push["env"]["GIT_CONFIG_GLOBAL"], push["env"]["GIT_CONFIG_NOSYSTEM"]) == (
        os.devnull, "1"), push["env"]
    assert push["env"]["SSH_AUTH_SOCK"] is None, "the push inherited SSH_AUTH_SOCK"
    others = [c for c in calls if c is not push]
    assert not [c["argv"] for c in others if c["env"]["GIT_SSH_COMMAND"]], (
        "another git call than the push carried GIT_SSH_COMMAND")
    assert not [c["argv"] for c in others if str(key) in json.dumps(c["argv"])], (
        "another git call named the key file")
    local_after = est.git(one.clone, "config", "--local", "--list")
    assert local_after == local_before, f"the checkout's configuration changed:\n{local_after}"
    assert "pushurl" not in local_after.lower(), local_after
    after = calls[calls.index(push) + 1:]
    assert any(c["sub"] == "fetch" and "origin" in c["argv"] for c in after), (
        "the read-back fetched no `origin` after the push")


def test_a_non_github_origin_with_render_key_is_refused_with_2(request, tmp_path):
    """D23 (TP:1194; B14 tasks:1472): with `render_key=` set and the
    checkout's origin a plain path, no GitHub repository, `render --checkout`
    exits 2, names the origin as not a GitHub repository, makes no push, and
    origin's `main` does not move. Fails until T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1)
    key = _private(one.root / "keys" / "render_key", "not a key\n")
    conf = est.config("deploy-key", "primary", [f"render_key={key}"])
    est.write_sql(["refused: the origin is no GitHub repository"])
    old = est.origin_tip()
    est.arm()
    proc = est.render(one, conf=conf)
    assert proc.returncode == 2, f"a non-GitHub origin with render_key= is not refused 2:\n{_said(proc)}"
    assert "not a GitHub repository" in proc.stderr, _said(proc)
    assert est.calls("push") == [], f"a push was made: {[c['argv'] for c in est.calls('push')]}"
    assert est.origin_tip() == old, "origin's main moved"


def test_without_render_key_the_push_goes_to_origin(request, tmp_path):
    """Q21(b)(A) (TP:1195; B14 tasks:1473-1477): without `render_key=` the
    push names `origin` as it stands, `<tip>:refs/heads/main`, never forced,
    with no `GIT_SSH_COMMAND`; origin gains the seq; and the checkout's
    configuration is unchanged. Fails until T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1)
    local_before = est.git(one.clone, "config", "--local", "--list")
    seqs = est.write_sql(["pushed to origin as it stands"])
    old = est.origin_tip()
    est.arm()
    proc = est.render(one)
    assert proc.returncode == 0, f"the render without render_key=:\n{_said(proc)}"
    commits = _assert_rendered(est, old, seqs)
    pushes = est.calls("push", one)
    assert len(pushes) == 1, f"not one push: {[p['argv'] for p in pushes]}"
    argv = pushes[0]["argv"]
    assert argv[argv.index(next(a for a in argv if a.endswith(":refs/heads/main"))) - 1] == "origin", (
        f"the push does not name `origin`: {argv}")
    assert _push_tip(pushes[0]) == commits[-1], argv
    assert not {"-f", "--force", "--force-with-lease"} & set(argv) and not any(
        a.startswith("+") for a in argv), argv
    assert pushes[0]["env"]["GIT_SSH_COMMAND"] is None, pushes[0]["env"]
    assert est.git(one.clone, "config", "--local", "--list") == local_before


# =================================================================== AT-5: the pass and form C
def _deepen(est: RenderEstate, depth: int) -> str:
    """`depth` commits under `handoffs/` on origin's `main`, none in the
    render set, by one `git fast-import`. Returns the new tip."""
    old = est.origin_tip()
    stream = []
    for n in range(1, depth + 1):
        message = f"t270: handoff commit {n} of {depth}\n".encode()
        content = f"# handoff {n}\n".encode()
        stream.append(b"commit refs/heads/main\n")
        stream.append(f"mark :{n}\n".encode())
        stream.append(f"committer T270 estate <t270@example.invalid> {1762858800 + n} +0000\n"
                      .encode())
        stream.append(b"data %d\n" % len(message) + message)
        stream.append(f"from {old if n == 1 else ':' + str(n - 1)}\n".encode())
        stream.append(b"M 100644 inline handoffs/t270-depth.md\n")
        stream.append(b"data %d\n" % len(content) + content)
    est.origin_git("fast-import", "--quiet", data=b"".join(stream))
    tip = est.origin_tip()
    assert est.origin_git("rev-list", "--count", f"{old}..{tip}").strip() == str(depth)
    return tip


def _walks(est: RenderEstate, lc) -> list:
    """The wrapper's `log --first-parent` calls in the checkout: form C's
    walk, as (`-n`, `--skip`, whether it says `--grep`)."""
    found = []
    for call in est.calls("log", lc):
        argv = call["argv"]
        if "--first-parent" not in argv or any(a.startswith("--raw") for a in argv):
            continue
        n = argv[argv.index("-n") + 1] if "-n" in argv else None
        skip = argv[argv.index("--skip") + 1] if "--skip" in argv else None
        found.append((n, skip, any(a.startswith("--grep") for a in argv)))
    return found


@pytest.mark.parametrize("depth", ["depth-0", "depth-250"])
def test_the_renderer_finds_m_by_paging_form_c(request, tmp_path, depth):
    """Lane 4's section (TP:1040-1043, :1196-1203): at depth 0 the newest
    render commit is the tip, and the renderer finds it in one page, the
    wrapper's log showing each pass's walk as one page of `-n 200`, no page
    after the first and no `--grep`; T323's holder runs a second pass after
    a pass that made progress, F15, and that pass walks its first page
    again from the new tip. At depth 250 it is 250 first-parent commits below the
    tip: the renderer pages with `--skip` and finds it, the log showing
    `-n 200`, the `--skip 200` page and no `--grep`. Either way it renders
    the seq after it on top of the tip. Fails until T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1)
    tip = _deepen(est, 250) if depth == "depth-250" else est.origin_tip()
    seqs = est.write_sql([f"found at {depth}"])
    est.arm()
    proc = est.render(one)
    assert proc.returncode == 0, f"the render at {depth}:\n{_said(proc)}"
    _assert_rendered(est, tip, seqs)
    walks = _walks(est, one)
    assert walks and all(n == "200" for n, _skip, _grep in walks), (
        f"form C's walk is not in pages of 200: {walks}")
    assert not any(grep for _n, _skip, grep in walks), f"form C's walk used --grep: {walks}"
    if depth == "depth-0":
        assert all(skip in (None, "0") for _n, skip, _g in walks), (
            f"at depth 0 a pass's walk took more than its first page: {walks}")
    else:
        assert [skip or "0" for _n, skip, _g in walks[:2]] == ["0", "200"], (
            f"at depth 250 the walk did not page on with --skip 200: {walks}")


@pytest.mark.parametrize("why", ["none", "out-of-time"])
def test_with_no_register_seq_found_the_renderer_pushes_nothing_and_records_why(request,
                                                                               tmp_path, why):
    """Lane 4's section (TP:1040-1043, :1204-1206): `[none]`, origin's
    `main` is C, no commit of which carries a `Register-Seq` (the marker
    commit is recorded and not on origin); `[out-of-time]`, the wrapper
    stalls the walk's `log` past `LANES_GIT_TIMEOUT`, set to 2 s. The
    renderer pushes nothing and exits non-zero; `mirror_state.last_error`
    and its time are set through `record_mirror_state`, `diverged_sha` stays
    NULL; `status` shows the failed pass; and origin is unchanged. Fails
    until T320 to T322."""
    est = _estate(request, tmp_path, marker="pushed" if why == "out-of-time" else "recorded")
    one = est.checkout("L1", L1)
    est.write_sql([f"no Register-Seq found: {why}"])
    old = est.origin_tip()
    env = None
    if why == "out-of-time":
        est.arm([{"sub": "log", "do": "stall", "has": "--first-parent", "seconds": 6,
                  "where": str(one.clone)}])
        env = {"LANES_GIT_TIMEOUT": "2"}
    else:
        assert old == est.c and est.form_c(old) == "", "origin's main carries a Register-Seq"
        est.arm()
    proc = est.render(one, env=env, timeout=120)
    assert proc.returncode != 0, f"the renderer found no m and still ended 0:\n{_said(proc)}"
    assert est.calls("push") == [], f"it pushed: {[c['argv'] for c in est.calls('push')]}"
    assert est.origin_tip() == old, "origin's main moved"
    mirror = est.mirror()
    assert mirror["last_error"] and mirror["last_error_utc"], (
        f"no failed pass is recorded in mirror_state: {mirror}\n{_said(proc)}")
    assert mirror["diverged_sha"] is None, f"a divergence was recorded: {mirror}"
    shown = est.status(one)
    assert FAILED_PASS.search(shown.stdout), f"status does not show the failed pass:\n{_said(shown)}"


def test_a_pass_renders_at_most_64_seqs(request, tmp_path):
    """PC-3 (TP:1044-1045, :1207-1209): a backlog of 70 seqs reaches origin
    as `m+1` to `m+64` in one pass, one push, and the rest in the next; and
    the commits are those of any other batching: a second origin, rendered
    in batches of 10 and then 60, carries the same 70 shas. Fails until
    T320 to T323."""
    est = _estate(request, tmp_path)
    other_origin = est.second_origin("origin-batched")
    one = est.checkout("L1", L1)
    batched = est.checkout("L2", L2, origin=other_origin)
    old = est.origin_tip()
    m = est.n
    first = est.write_sql([f"backlog entry {i}" for i in range(1, 11)])
    est.arm()
    proc = est.render(batched)
    assert proc.returncode == 0, f"the batched render of 10:\n{_said(proc)}"
    rest = est.write_sql([f"backlog entry {i}" for i in range(11, 71)])
    seqs = first + rest
    assert seqs == list(range(m + 1, m + 71)), seqs
    est.arm()
    proc = est.render(one)
    assert proc.returncode == 0, f"the render of a backlog of 70:\n{_said(proc)}"
    commits = _assert_rendered(est, old, seqs)
    tips = [_push_tip(p) for p in est.calls("push", one)]
    assert tips == [commits[63], commits[69]], (
        f"the pushes named {tips}, not seq {m + 64}'s commit, then seq {m + 70}'s: a pass "
        f"renders at most 64 seqs")
    est.arm()
    proc = est.render(batched)
    assert proc.returncode == 0, f"the batched render of 60:\n{_said(proc)}"
    assert _assert_rendered(est, old, seqs, other_origin) == commits, (
        "batches of 10 and 60 made other commits than batches of 64 and 6")


@pytest.mark.parametrize("shape", ["subject-only", "trailer-block", "prose"])
def test_form_c_reads_the_trailer_from_each_message_shape(request, tmp_path, shape):
    """Lane 4's section (TP:1225-1226): a journal message of each shape, a
    subject alone, a body ending in a trailer block, and a body ending in
    prose. Two checkouts give one sha for it (`L2` held at its push while
    `L1` renders), and form C reads `<k>` from it. The trailer joins the
    final trailer block, or is a new last paragraph after one blank line
    (T322). Fails until T320 to T322."""
    message = {
        "subject-only": "t270: a subject alone",
        "trailer-block": (f"t270: a subject\n\nA body line.\n\nLane: {L1}\n"
                          f"Co-Authored-By: T270 <t270@example.invalid>"),
        "prose": ("t270: a subject\n\nA body that ends in prose, a paragraph with no "
                  "trailer in it."),
    }[shape]
    est = _estate(request, tmp_path)
    one, two = est.checkout("L1", L1), est.checkout("L2", L2)
    old = est.origin_tip()
    (k,) = est.write_sql([f"form C, {shape}"], messages=[message])
    fifo = est.root / "hold.fifo"
    os.mkfifo(str(fifo), 0o600)
    est.arm([{"sub": "push", "do": "hold", "fifo": str(fifo), "where": str(two.clone),
              "times": 1}])
    held = est.popen_render(two)
    fd = _open_when_held(fifo, held)
    try:
        assert fd is not None, f"L2's renderer never reached its push:\n{held.communicate()}"
        proc = est.render(one)
        assert proc.returncode == 0, f"L1's renderer:\n{_said(proc)}"
    finally:
        if fd is not None:
            os.close(fd)
    held.communicate(timeout=300)
    assert held.returncode == 0, "L2's renderer after the release"
    gained = est.commits_after(old)
    assert [carried for _s, carried, _m in gained] == [[k]], gained
    sha, _carried, raw = gained[0]
    assert _push_tip(est.calls("push", two)[0]) == sha, "two checkouts gave two shas"
    assert est.form_c(sha) == str(k), f"form C reads {est.form_c(sha)!r} from {sha}, not {k}"
    joined = "\n" if shape == "trailer-block" else "\n\n"
    assert raw.rstrip("\n") == f"{message}{joined}Register-Seq: {k}", (
        f"the {shape} message is not the journal's with Register-Seq: {k} "
        f"{'in its trailer block' if shape == 'trailer-block' else 'as a new paragraph'}: {raw!r}")


@pytest.mark.parametrize("case", ["marker-first-head-minus-1", "marker-first-head-0", "forged"])
def test_a_register_seq_above_the_head_with_the_switch_at_files_is_no_divergence_and_renders_nothing(
        request, tmp_path, case):
    """R2's N6, at `files` (TP:1150-1167, :1227-1228): the switch reads
    `files`, and origin's `main` carries a commit whose last `Register-Seq`
    is above the head `h`: the marker commit `S` with `Register-Seq: 1`,
    pushed ahead of the import (`h` -1, on `pg`) or after it (`h` 0); or a
    forged commit under `handoffs/` carrying `Register-Seq: <h+10>`. A pass
    run by `render --checkout <c>`, as a fork runs it, records no
    divergence (`diverged_sha` NULL, no `diverged at` in `status`), pushes
    nothing, and exits 0. Fails until T320 to T322."""
    est = _estate(request, tmp_path, stage="empty" if case.endswith("minus-1") else "imported")
    h = est.head()
    if case == "forged":
        top = est.commit_in_origin(est.c, {f"handoffs/{L1}.md": b"# a forged commit\n"},
                                   f"a forged handoff commit\n\nRegister-Seq: {h + 10}\n")
    else:
        top = est.commit_in_origin(est.c, {"lanes/STORE": b"store=primary\n"},
                                   "t270: the marker commit, pushed first\n\nRegister-Seq: 1\n")
    est.push_by_hand(top)
    one = est.checkout("L1", L1)
    est.arm()
    proc = est.render(one)
    assert proc.returncode == 0, f"the pass at files:\n{_said(proc)}"
    assert est.calls("push") == [] and est.origin_tip() == top, "the pass at files pushed"
    assert est.mirror()["diverged_sha"] is None, f"a divergence was recorded: {est.mirror()}"
    shown = est.status(one)
    assert not DIVERGED.search(shown.stdout), f"status prints a divergence:\n{shown.stdout}"
    assert est.head() == h and est.switch()["mode"] == "files"


def test_a_render_commit_with_a_private_index_and_its_push_are_timed_and_recorded(request,
                                                                                  tmp_path):
    """M6, section 5.1 (TP:1229-1235): the render commit made through the
    private index, and its push to the local origin, each timed from the
    wrapper's log, which tells the commit (`commit-tree`) from the push, over
    five renders of one seq each; recorded with section 5.3's statistics and
    their n, never asserted. Correctness alongside: each `write-tree` ran
    under `GIT_INDEX_FILE` `lanes-render.index`, and origin gains each commit
    with its `Register-Seq`. Fails until T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1)
    commits, pushes = [], []
    for n in range(1, 6):
        old = est.origin_tip()
        seqs = est.write_sql([f"timed render {n}"])
        est.arm()
        proc = est.render(one)
        assert proc.returncode == 0, f"timed render {n}:\n{_said(proc)}"
        _assert_rendered(est, old, seqs)
        trees = est.calls("write-tree", one)
        assert trees and all((c["env"]["GIT_INDEX_FILE"] or "").endswith("lanes-render.index")
                             for c in trees), (
            f"a write-tree ran without the private index: {[c['env'] for c in trees]}")
        commits += [(c["t1"] - c["ran"]) * 1000 for c in est.calls("commit-tree", one)]
        pushes += [(c["t1"] - c["ran"]) * 1000 for c in est.calls("push", one)]
    assert commits and pushes
    for what, samples in (("render commit, private index", commits), ("its push", pushes)):
        stats = _stats(samples)
        row = (f"| M6 | fixture cluster, local bare origin | {what} | median "
               f"{stats['median']:.1f} ms, p95 {stats['p95']:.1f} ms, "
               f"{stats['min']:.1f}-{stats['max']:.1f} ms, n={stats['n']} |")
        print("\n" + row)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write(row + "\n")


# =================================================================== AT-5: six lost races (T323, T325)
def test_six_lost_races_leave_the_last_write_for_the_next_write_or_reconcile(request,
                                                                             tmp_path):
    """Lane 4's known gap (TP:1044-1045, :1074-1080, :1216-1218): the wrapper
    rejects six pushes in a row as non-fast-forwards. The renderer makes six
    push attempts in all, a fetch before each new one, and ends non-zero;
    origin is unchanged and `status` shows a lag of 1. Then `reconcile`,
    run in the lane's checkout with the `mode=primary` configuration,
    renders it: origin carries the seq, and the lag is 0. Fails until T320
    to T323, and T325 (the re-render), at its own assertion."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1)
    seqs = est.write_sql(["the last write, six races lost"])
    old = est.origin_tip()
    est.arm([{"sub": "push", "do": "reject", "where": str(one.clone), "times": 6}])
    proc = est.render(one)
    assert proc.returncode != 0, f"the renderer that lost six races ended 0:\n{_said(proc)}"
    assert est.origin_tip() == old, "origin moved"
    calls = est.calls(lc=one)
    pushes = [i for i, c in enumerate(calls) if c["sub"] == "push"]
    assert len(pushes) == 6 and all(calls[i]["outcome"] == "rejected" for i in pushes), (
        f"not six rejected pushes: {[(c['sub'], c['outcome']) for c in calls]}")
    for before, after in zip(pushes, pushes[1:]):
        assert any(c["sub"] == "fetch" for c in calls[before + 1:after]), (
            "a push was retried with no fetch after its rejection")
    assert est.lag(one) == 1, f"status does not show a lag of 1:\n{est.status(one).stdout}"
    proc = est.index(one, "reconcile", conf=est.primary_conf)
    assert proc.returncode == 0, f"reconcile:\n{_said(proc)}"
    assert est.commits_after(old) and est.commits_after(old)[-1][1] == seqs, (
        f"reconcile did not render seq {seqs[0]} (T325: it re-renders what the mirror lacks, "
        f"through T322's pass): origin carries {est.commits_after(old)}\n{_said(proc)}")
    _assert_rendered(est, old, seqs)
    assert est.lag(one) == 0, f"the lag is not 0 after reconcile:\n{est.status(one).stdout}"


# =================================================================== writes that fork
#: THE WRITER- AND FORK-SIDE CASES: each write is `lanes-edit.sh log NOTED`
#: (or lane-start's stamp) on `primary` from a lane's checkout, through the
#: flipped copy, and its fork starts the renderer in the lane's own register
#: checkout `<c>` (`own=True`, T270e), whose calls, lock and marks each case
#: reads. Each fails until lane 4's T415 and T416 (L4-B13), with T320 to
#: T323. Every wait for a forked render is open point 8's.


def test_a_renderer_killed_between_commit_and_push_blocks_nothing(request, tmp_path):
    """AT-5's kill (TP:1103-1115; P319-346; concern 3, ADV-C6): `L1`'s write
    forks a render that the wrapper kills by SIGKILL just before its push.
    Read after the renderer's exit (open point 8's second wait): `L1`'s
    HEAD, index digest and `status --porcelain` are as before the render.
    Then, with no other command between, `L1`'s next write forks a render
    that pushes every missing seq in order, and `L1`'s next handoff commit,
    lane-handoff's commit block, exits 0 and is pushed. A second kill, then
    a write, then lane-start's stamp (`append-session-id`), which exits 0
    and is rendered. Fails until L4-B13 and T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, own=True)
    old = est.origin_tip()
    before = est.snapshot(one.own)
    est.arm([{"sub": "push", "do": "kill", "render_only": True, "where": str(one.own.clone),
              "times": 1}])
    mark = est.entries()
    _wrote(est.write(one, "a write whose render is killed before its push"), "log NOTED")
    est.wait_renders_exit(mark, "the killed render")
    assert [c for c in est.render_calls(mark) if c["outcome"] == "killed"], (
        "the wrapper killed no render at its push")
    assert est.snapshot(one.own) == before, "the killed render moved L1's HEAD, index or status"
    assert _lock_is_free(one.own.git_dir / "lanes-render.lock"), "the render lock is still held"
    # The next write, then lane-handoff's commit block, with nothing between.
    est.rearm()
    _wrote(est.write(one, "the next write after the kill"), "the next log NOTED")
    est.wait_lag_0(one, "the next write's render")
    _assert_rendered(est, old, list(range(est.n + 1, est.head() + 1)))
    handoff = f"handoffs/{L1}.md"
    (one.own.clone / "handoffs").mkdir(exist_ok=True)
    (one.own.clone / handoff).write_text("# a handoff, after the killed render\n",
                                         encoding="utf-8")
    env = dict(est.plain_env, HOME=str(one.home))
    for argv in (["add", "--", handoff],
                 ["commit", "-q", "-m", f"handoff({L1}@{WS}): PAUSED, t270", "-m",
                  f"Lane: {L1}", "--", handoff],
                 ["pull", "--rebase", "-q", "origin", "main"], ["push", "-q", "origin", "main"]):
        est.git(one.own.clone, *argv, env=env)
    assert handoff in est.origin_git("ls-tree", "-r", "--name-only", "refs/heads/main",
                                     "handoffs/").split(), "the handoff commit was not pushed"
    # The second case: a kill, a write, then lane-start's stamp. It arms the
    # kill afresh with `est.arm()`, which starts the wrapper's log and its
    # counts again: `rearm()` keeps each arm's count of uses, and the first
    # case's kill used arm 0's one (`times: 1`), so a re-armed kill never
    # fired and the second case passed with no kill (RV20, finding 2).
    est.arm([{"sub": "push", "do": "kill", "render_only": True, "where": str(one.own.clone),
              "times": 1}])
    mark = est.entries()
    _wrote(est.write(one, "a second write whose render is killed"), "log NOTED")
    est.wait_renders_exit(mark, "the second killed render")
    assert [c for c in est.render_calls(mark) if c["outcome"] == "killed"], (
        f"the wrapper killed no render at the second case's push: "
        f"{[(c['sub'], c['outcome']) for c in est.render_calls(mark)]}")
    est.rearm()
    _wrote(est.write(one, "the write after the second kill"), "log NOTED")
    stamp = est.edit(one, "append-session-id", L1, f"harness `{UUID_L1}`", " (t270)")
    _wrote(stamp, "lane-start's stamp, append-session-id")
    est.wait_lag_0(one, "the stamp's render")


def _held_burst(est: RenderEstate, one) -> SimpleNamespace:
    """AT-5's HELD RENDERER (TP:1116-1125): `L1`'s render held at its push
    (the hold re-armed for each push) while four more writes from `L1` each
    exit 0; then the hold is disarmed and released, and both of open point
    8's waits run. Returns what the case reads."""
    fifo = est.root / "held.fifo"
    os.mkfifo(str(fifo), 0o600)
    old = est.origin_tip()
    est.arm([{"sub": "push", "do": "hold", "render_only": True, "fifo": str(fifo),
              "where": str(one.own.clone)}])
    mark = est.entries()
    _wrote(est.write(one, "the first write of a burst"), "log NOTED")
    fd = _held_fd(fifo, "the first write's render, at its push")
    rerun = one.own.git_dir / "lanes-render.rerun"
    try:
        holder = {c["renderer"] for c in est.render_calls(mark) if c["outcome"] == "held"}
        waited = []
        for n in range(2, 6):
            start = time.monotonic()
            _wrote(est.write(one, f"write {n} of a burst, while the render is held",
                             timeout=120), f"write {n}")
            waited.append(time.monotonic() - start)

        def forks() -> dict:
            return {c["renderer"]: c["renderer_start"] for c in est.render_calls(mark)
                    if c["renderer"] not in holder}
        # A detached fork may start after its write returns: wait, the hold
        # standing, until the four have run a git call and exited, or 30 s.
        _until(lambda: len(forks()) >= 4 and all(_exited(p, s) for p, s in forks().items()),
               CEILING)
        forks_live = [pid for pid, start in forks().items() if not _exited(pid, start)]
        marked = rerun.exists()
        est.rearm()
    finally:
        os.close(fd)
    est.wait_lag_0(one, "the burst's last write")
    est.wait_renders_exit(mark, "the burst's renders")
    assert _lock_is_free(one.own.git_dir / "lanes-render.lock"), "the render lock is still held"
    pushes = [c for c in est.render_calls(mark) if c["sub"] == "push" and c["outcome"] == "ran"]
    return SimpleNamespace(old=old, holder=holder, marked=marked, forks=forks(),
                           forks_live=forks_live, waited=waited, pushes=pushes,
                           rerun_left=rerun.exists())


def test_a_held_renderer_delays_no_writer_beyond_the_fork(request, tmp_path):
    """AT-5's held renderer (TP:1116-1120, :1240-1241): with `L1`'s render
    held at its push, four more writes from `L1` each exit 0 while it is
    held, so no fork waited; each fork that found the lock held left
    `lanes-render.rerun` in the checkout's git directory and had exited
    while the hold still stood (D14). Fails until L4-B13 and T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, own=True)
    seen = _held_burst(est, one)
    assert len(seen.holder) == 1, f"not one held render: {seen.holder}"
    assert seen.marked, "no fork that found the lock held left lanes-render.rerun"
    assert seen.forks, "no fork of the four writes ran `render --checkout`"
    assert not seen.forks_live, (
        f"forks {seen.forks_live} that found the lock held had not exited while it was held")


def test_a_burst_from_one_lane_gives_at_most_two_renders(request, tmp_path):
    """[L4-3], qualified (TP:1028-1030, :1121-1125, :1242): the held
    renderer's burst of five writes. Once the lag is 0 and every renderer
    has exited, at most two renders made commits, the wrapper's log
    counting their pushes, and origin carries the burst's last seq, each
    seq once, in order. Fails until L4-B13 and T320 to T323."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, own=True)
    seen = _held_burst(est, one)
    assert 1 <= len(seen.pushes) <= 2, (
        f"{len(seen.pushes)} pushes for a burst that arrived within one pass, not at most two: "
        f"{[_push_tip(p)[:12] for p in seen.pushes]}")
    _assert_rendered(est, seen.old, list(range(est.n + 1, est.head() + 1)))


def test_the_last_write_of_a_burst_is_rendered_with_no_later_write(request, tmp_path):
    """S2 (TP:1031): five writes from `L1` in a row, no hold, and no later
    write. Within open point 8's waits the lag reaches 0 and every renderer
    exits; origin carries every seq of the burst, its last included, in
    order. Fails until L4-B13 and T320 to T323."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, own=True)
    old = est.origin_tip()
    est.arm()
    for n in range(1, 6):
        _wrote(est.write(one, f"burst write {n}, with no later write"), f"write {n}")
    est.wait_lag_0(one, "the burst's last write")
    est.wait_renders_exit(0, "the burst's renders")
    _assert_rendered(est, old, list(range(est.n + 1, est.head() + 1)))


@pytest.mark.parametrize("fail", ["fetch", "push"])
def test_a_failed_render_shows_its_lag_and_the_next_render_catches_up(request, tmp_path, fail):
    """AT-5's failed render (TP:1134-1149): every render's `fetch` (or
    `push`) fails. After the write, open point 8's second wait: SQL holds
    the seq and `status` shows a lag of 1; `last_error` and its time are set
    by the failed pass, and `diverged_sha` stays NULL; in the push case each
    push follows a fetch, six pushes at most; and after the renderer's exit
    no pass follows it, no render's `fetch` or `push` until the next write.
    Released, the next write's render leaves both seqs on origin in order,
    and a lag of 0. Fails until L4-B13 and T320 to T323."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, own=True)
    old = est.origin_tip()
    est.arm([{"sub": fail, "do": "fail", "render_only": True, "where": str(one.own.clone)}])
    mark = est.entries()
    _wrote(est.write(one, f"a write whose render's {fail} fails"), "log NOTED")
    est.wait_renders_exit(mark, f"the render whose {fail} fails")
    k = est.head()
    assert k == est.n + 1 and est.origin_tip() == old, "the failed render pushed"
    assert est.lag(one) == 1, f"status does not show a lag of 1:\n{est.status(one).stdout}"
    mirror = est.mirror()
    assert mirror["last_error"] and mirror["last_error_utc"], (
        f"the failed pass recorded nothing: {mirror}")
    assert mirror["diverged_sha"] is None, f"a divergence was recorded: {mirror}"
    calls = est.render_calls(mark)
    if fail == "push":
        pushes = [i for i, c in enumerate(calls) if c["sub"] == "push"]
        assert 1 <= len(pushes) <= 6, f"{len(pushes)} pushes, not one to six"
        for i in pushes:
            assert any(c["sub"] == "fetch" for c in calls[:i]), "a push with no fetch before it"
    ended = est.entries()
    est.rearm()
    assert not [c for c in est.render_calls(ended) if c["sub"] in ("fetch", "push")], (
        "a pass followed the failed one (F15: a pass that pushed nothing ends the renderer)")
    _wrote(est.write(one, "the next write, after the release"), "the next log NOTED")
    est.wait_lag_0(one, "the next write's render")
    _assert_rendered(est, old, [k, k + 1])


def test_a_renderer_hands_over_once_after_16_passes(request, tmp_path):
    """PC-3's handover (TP:1046-1049, :1210-1215): a stream of 17 writes
    from `L1`, one per pass, each made while that pass is held at its push
    (the hold re-arms for each push). Each write waits for that pass's push
    in the wrapper's raw log, so no two writes share a pass. No renderer
    process makes more than 16 passes (a pass begins with its fetch), a
    second process follows once, and the last write reaches origin. Fails
    until L4-B13 and T320 to T323."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, own=True)
    old = est.origin_tip()
    fifo = est.root / "pass.fifo"
    os.mkfifo(str(fifo), 0o600)
    est.arm([{"sub": "push", "do": "hold", "render_only": True, "fifo": str(fifo),
              "where": str(one.own.clone)}])
    _wrote(est.write(one, "stream write 1"), "write 1")
    # Write n waits for pass n-1's push, the (n-1)-th held line in the raw
    # log (lane 3's #38, #165 6859801732). `_held_fd` alone could reopen the
    # FIFO onto the push just released, before its wrapper saw EOF: that
    # push stayed held through write n, and the next pass rendered two seqs.
    for n in range(2, 18):
        fd = _kth_held_fd(est, fifo, n - 1, f"pass {n - 1}'s push")
        try:
            _wrote(est.write(one, f"stream write {n}", timeout=120), f"write {n}")
        finally:
            os.close(fd)
    fd = _kth_held_fd(est, fifo, 17, "the last pass's push")
    est.rearm()
    os.close(fd)
    est.wait_lag_0(one, "the stream's last write")
    est.wait_renders_exit(0, "the stream's renders")
    # Each pass renders one write and pushes it once (nothing rejects here),
    # so a renderer's pushes count its passes that made progress.
    passes: dict = {}
    for call in est.render_calls(0):
        if call["sub"] == "push" and call["outcome"] == "ran":
            passes[call["renderer"]] = passes.get(call["renderer"], 0) + 1
    assert sum(passes.values()) == 17, (
        f"the 17 writes did not go out in 17 render pushes, one per pass: {passes}")
    assert passes and max(passes.values()) <= 16, f"a renderer made more than 16 passes: {passes}"
    assert len(passes) == 2, (
        f"{len(passes)} renderer processes pushed, not the first and one that follows it: "
        f"{passes}")
    _assert_rendered(est, old, list(range(est.n + 1, est.n + 18)))


def test_no_rerun_mark_is_left_and_the_last_write_is_rendered_after_a_burst(request, tmp_path):
    """D14's handshake (TP:1219-1221): after each of two bursts of 10 forks
    from `L1`, both halves of the `flock` handshake leave no
    `lanes-render.rerun`, and origin carries the last seq. Fails until
    L4-B13 and T320 to T323."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, own=True)
    old = est.origin_tip()
    est.arm()
    for burst in (1, 2):
        mark = est.entries()
        for n in range(1, 11):
            _wrote(est.write(one, f"burst {burst}, fork {n}"), f"burst {burst}, write {n}")
        est.wait_lag_0(one, f"burst {burst}")
        est.wait_renders_exit(mark, f"burst {burst}'s renders")
        assert not (one.own.git_dir / "lanes-render.rerun").exists(), (
            f"burst {burst} left lanes-render.rerun")
        assert est.commits_after(old)[-1][1] == [est.head()], (
            f"origin does not carry burst {burst}'s last seq {est.head()}")
    _assert_rendered(est, old, list(range(est.n + 1, est.head() + 1)))


def test_a_write_that_commits_as_the_render_lets_go_is_rendered_with_no_later_write(request,
                                                                                    tmp_path):
    """Commit I's "A write that commits as the render lets go" (TP:1084-1090,
    :1126-1133; S2's two halves of `SyncLock`'s handshake): `L1`'s first
    write forks a render, and the `psql` shim holds that render's second
    pass, one-shot, once the real `psql` has returned its read of the head,
    which holds no entry after `m`. A second write from `L1` commits and
    exits 0; its fork finds the lock held, leaves `lanes-render.rerun`, and
    exits. The case releases the shim and makes no later write: the second
    write's seq reaches origin, `status` shows a lag of 0, and no
    `lanes-render.rerun` is left. Fails until L4-B13 and T320 to T323."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, own=True)
    old = est.origin_tip()
    fifo = est.root / "lets-go.fifo"
    os.mkfifo(str(fifo), 0o600)
    est.arm(shim_arms=[{"mode": "timer", "fifo": str(fifo),
                        "match": "FROM register_head h, register_switch s", "call": 2}])
    mark = est.entries()
    _wrote(est.write(one, "the first write; its render lets go"), "write 1")
    fd = _held_fd(fifo, "the render's second pass, after its read of the head")
    try:
        _wrote(est.write(one, "the write that commits as the render lets go", timeout=120),
               "write 2")
        assert _until(lambda: (one.own.git_dir / "lanes-render.rerun").exists(), CEILING), (
            "the second write's fork found the lock held and left no lanes-render.rerun")
    finally:
        os.close(fd)
    est.wait_lag_0(one, "the write that commits as the render lets go")
    est.wait_renders_exit(mark, "the renders")
    _assert_rendered(est, old, [est.n + 1, est.n + 2])
    assert not (one.own.git_dir / "lanes-render.rerun").exists(), "lanes-render.rerun is left"


# =================================================================== AT-C8
def test_a_render_forked_from_a_no_fetch_verb_still_renders(request, tmp_path):
    """AT-C8 (C172-184; TP:3173-3196): `log NOTED` run with
    `LANES_NO_FETCH=1` from `L1`'s checkout on a primary estate. Its render
    commit reaches origin and `status` reports a lag of 0 (open point 8's
    first wait); the wrapper's log shows the renderer's own fetch, made with
    the variable absent from its environment, and no render's call made
    with it set (D12). Fails until L4-B13 and T320 to T322."""
    est = _estate(request, tmp_path)
    one = est.checkout("L1", L1, own=True)
    old = est.origin_tip()
    est.arm()
    _wrote(est.write(one, "a write under LANES_NO_FETCH=1", env={"LANES_NO_FETCH": "1"}),
           "log NOTED under LANES_NO_FETCH=1")
    est.wait_lag_0(one, "the no-fetch write's render")
    est.wait_renders_exit(0, "the no-fetch write's render")
    _assert_rendered(est, old, [est.n + 1])
    renders = est.render_calls(0)
    fetches = [c for c in renders if c["sub"] == "fetch"]
    assert fetches and all(c["env"]["LANES_NO_FETCH"] is None for c in fetches), (
        f"the renderer made no fetch of its own with LANES_NO_FETCH absent: "
        f"{[(c['argv'], c['env']['LANES_NO_FETCH']) for c in fetches]}")
    assert not [c["argv"] for c in renders if c["env"]["LANES_NO_FETCH"] is not None], (
        "a render's git call inherited LANES_NO_FETCH")
