# SPDX-License-Identifier: Apache-2.0
"""`lane-worktrees sweep` - one act that archives, rescues and removes a lane's
abandoned worktrees (opensoft/openRepoTools#162).

What these tests hold it to, row for row with the issue's disposition table:

  * a tree a LIVE writer stands in is never touched;
  * clean and MERGED (by the register's LANDED line or `gh`, never by
    ancestry alone) is removed with its branches;
  * clean and pushed is removed and its branch stays;
  * unpushed commits are pushed as is - or, where origin diverged, to a
    rescue branch - and only then removed;
  * dirty or untracked work becomes a WIP commit on a rescue branch, pushed,
    then removed; detached with commits of its own is rescued the same way;
  * a registration whose directory is gone is pruned;
  * a FOREIGN tree is reported and left;
  * the rescue is ON ORIGIN before anything is removed - a refused push leaves
    the tree exactly as it was;
  * the dry run changes nothing at all;
  * `--yes` is refused for a lane bound elsewhere (Amendment 18(b));
  * `--branches`, `--links`, alternates, `--expire` and the porcelain exit
    codes `lane-end`'s gate (#163) reads.

NOTHING REAL IS SWEPT. Every estate is built under `tmp_path`: bare
repositories stand in for origin (reached through a `url.<path>.insteadOf` for
a GitHub-shaped URL, so the code under test reads a real `owner/repo` slug),
`gh`, `tmux` and `lanes-edit.sh` are fakes on `PATH`, and the sandbox sweep is
pointed at a root of its own. One case runs the REAL `lanes-edit.sh` against a
fixture workspace, so the inventory, the reconciliation and the register line
are the helper's own.
"""

from __future__ import annotations

import datetime as _dt
import getpass
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="the sweep drives git, and the lane helper is bash")]

LW = REPO / "lane-worktrees"
LANES_EDIT = REPO / "lanes-edit.sh"
LANE = "repoA-1"
ME = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
#: The session that recorded the inventory: an EARLIER one, which the fake
#: `transcript-holders` answers is not live. A tree THIS session (ME) recorded
#: wants the coordinator's writer count under `--yes` (#170 B5).
WRITER = "44444444-4444-4444-8444-444444444444"
SLUG = "opensoft/repoA"
GH_URL = f"git@github.com:{SLUG}.git"
US = "\x1f"

FAKE_HELPER = r'''#!/usr/bin/env python3
import json, os, sys
spec = json.load(open(os.environ["FAKE_HELPER_SPEC"]))
args = sys.argv[1:]
with open(os.environ["FAKE_HELPER_LOG"], "a") as fh:
    fh.write(json.dumps({"argv": args, "lane": os.environ.get("LANES_LANE", ""),
                         "no_fetch": os.environ.get("LANES_NO_FETCH", "")}) + "\n")
ans = spec.get(args[0] if args else "", {"rc": 2, "err": "unknown subcommand\n"})
sys.stdout.write(ans.get("out", ""))
sys.stderr.write(ans.get("err", ""))
sys.exit(ans.get("rc", 0))
'''

FAKE_GH = r'''#!/usr/bin/env python3
import os, sys
if sys.argv[1:3] == ["pr", "list"]:
    path = os.environ.get("FAKE_GH_PRS", "")
    sys.stdout.write(open(path).read() if path and os.path.exists(path) else "[]")
    sys.exit(0)
sys.exit(1)
'''

FAKE_TMUX = """#!/bin/sh
if [ -n "${FAKE_TMUX_PANES:-}" ] && [ -f "$FAKE_TMUX_PANES" ]; then cat "$FAKE_TMUX_PANES"; exit 0; fi
exit 1
"""


def _clean_path() -> str:
    """PATH without any directory holding an installed lane command."""
    keep = []
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if part and not any(os.path.exists(os.path.join(part, n))
                            for n in ("lanes-edit.sh", "lane-worktrees", "lanes-index")):
            keep.append(part)
    return os.pathsep.join(keep)


class Estate:
    """One lane's estate under `tmp_path`: a bare origin, the lane's
    checkout, its two worktree roots, the fakes, and the environment the
    sweep is run in."""

    def __init__(self, root: Path):
        self.root = root
        self.home = root / "home"
        self.projects = root / "projects"
        self.remotes = root / "remotes"
        self.fakebin = root / "fakebin"
        self.state = root / "state"
        self.config = root / "config"
        self.sandboxes = root / "sandboxes"
        for d in (self.home, self.projects, self.remotes, self.fakebin, self.state,
                  self.config, self.sandboxes, root / "tmp"):
            d.mkdir(parents=True, exist_ok=True)
        self.origin = self.remotes / "repoA.git"
        self.checkout = self.projects / "repoA"
        self.claude_root = self.checkout / ".claude" / "worktrees"
        self.lane_root = self.projects / ".lane-worktrees" / LANE
        self.spec_file = root / "helper-spec.json"
        self.helper_log = root / "helper.log"
        self.prs_file = root / "prs.json"
        for name, text in (("lanes-edit.sh", FAKE_HELPER), ("gh", FAKE_GH), ("tmux", FAKE_TMUX)):
            (self.fakebin / name).write_text(text)
            (self.fakebin / name).chmod(0o755)
        (self.home / ".gitconfig").write_text(
            f'[url "{self.origin}"]\n\tinsteadOf = {GH_URL}\n'
            "[user]\n\tname = sweep tests\n\temail = sweep@example.invalid\n"
            "[init]\n\tdefaultBranch = main\n"
            '[protocol "file"]\n\tallow = always\n'
            "[advice]\n\tdetachedHead = false\n")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("LANES_", "CLAUDE_", "WORKBENCHES_", "TMUX", "XDG_",
                                    "PROJECTS_", "GH_", "GIT_", "FAKE_", "LANE_WORKTREES_",
                                    "AGENT_PROTOCOL_ROOT"))}
        env.update(
            HOME=str(self.home), TMPDIR=str(root / "tmp"),
            XDG_STATE_HOME=str(self.state), XDG_CONFIG_HOME=str(self.config),
            PROJECTS_ROOT=str(self.projects), LANES_EDIT=str(self.fakebin / "lanes-edit.sh"),
            FAKE_HELPER_SPEC=str(self.spec_file), FAKE_HELPER_LOG=str(self.helper_log),
            FAKE_GH_PRS=str(self.prs_file), CLAUDE_CODE_SESSION_ID=ME,
            LANE_WORKTREES_SANDBOX_ROOTS=str(self.sandboxes), LANES_WORKSTATION="Eagle",
            GIT_CONFIG_NOSYSTEM="1",
            PATH=str(self.fakebin) + os.pathsep + _clean_path())
        self.env = env
        self.inventory: list = []
        self.prs: list = []
        self.holder = "none"
        self.binding = ("here", "Eagle/none")
        self.state_word = "RUNNING"
        self.verdict = "ungraceful-stop"
        self.workspace = ""
        self.log_rc = 0
        self.extra_spec: dict = {}
        self._seed()

    # ------------------------------------------------------------ git
    def git(self, *args, cwd=None, check=True, env=None) -> str:
        child = dict(self.env)
        child.update(env or {})
        proc = subprocess.run(["git", *[str(a) for a in args]], cwd=str(cwd or self.checkout),
                              capture_output=True, text=True, env=child, check=False)
        if check:
            assert proc.returncode == 0, f"git {' '.join(map(str, args))}: {proc.stderr}"
        return proc.stdout.strip()

    def _seed(self) -> None:
        self.git("init", "-q", "--bare", "-b", "main", self.origin, cwd=self.root)
        self.git("clone", "-q", GH_URL, self.checkout, cwd=self.root)
        (self.checkout / "README.md").write_text("repoA\n")
        (self.checkout / ".gitignore").write_text(".env\n__pycache__/\n*.pyc\n")
        self.git("add", "-A")
        self.commit(self.checkout, "seed")
        self.git("push", "-q", "origin", "main")
        # THE WORKSPACE REPOSITORY, which `--yes` fetches before it reads a
        # binding (#170 A1) and whose lane logs name every lane's directory
        # (#170 G6). Outside `projects/`, so it is no repository of the estate.
        ws_origin = self.root / "workspace.git"
        ws = self.root / "workspace"
        self.git("init", "-q", "--bare", "-b", "main", ws_origin, cwd=self.root)
        self.git("clone", "-q", ws_origin, ws, cwd=self.root)
        (ws / "lanes" / "log").mkdir(parents=True)
        (ws / "lanes" / "LANES.md").write_text("# register\n")
        self.git("add", "-A", cwd=ws)
        self.git("commit", "-q", "-m", "seed", cwd=ws)
        self.git("push", "-q", "origin", "main", cwd=ws)
        self.workspace = str(ws)

    def register_line(self, lane: str, line: str) -> None:
        """One line appended to `lane`'s log in the workspace, pushed."""
        ws = Path(self.workspace)
        log = ws / "lanes" / "log" / f"{lane}.md"
        log.write_text((log.read_text() if log.exists() else "") + line + "\n")
        self.git("add", "-A", cwd=ws)
        self.git("commit", "-q", "-m", f"log {lane}", cwd=ws)
        self.git("push", "-q", "origin", "main", cwd=ws)

    def commit(self, cwd: Path, message: str, files: dict | None = None,
               lane: str | None = LANE) -> str:
        for rel, text in (files or {}).items():
            path = Path(cwd) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git("add", "-A", cwd=cwd)
        body = f"{message}\n\nLane: {lane}\n" if lane else message
        self.git("commit", "-q", "--allow-empty", "-m", body, cwd=cwd)
        return self.git("rev-parse", "HEAD", cwd=cwd)

    def worktree(self, name: str, branch: str | None = None, where: str = "lane",
                 start: str = "origin/main", record: bool = True) -> Path:
        root = self.lane_root if where == "lane" else self.claude_root
        root.mkdir(parents=True, exist_ok=True)
        path = root / name
        if branch:
            self.git("worktree", "add", "-q", "-b", branch, path, start)
        else:
            self.git("worktree", "add", "-q", "--detach", path, start)
        if record:
            self.record(path)
        return path

    def record(self, path: Path, branch: str = "", head: str = "",
               writer: str = WRITER) -> None:
        """An inventory row, as `lanes-edit.sh lane-trees` prints one."""
        if path.is_dir():
            branch = self.git("symbolic-ref", "-q", "--short", "HEAD", cwd=path, check=False) or "detached"
            head = self.git("rev-parse", "HEAD", cwd=path)
        row = [f"c{len(self.inventory)}-{path.name}", str(path), branch or "unknown",
               head or "unknown", "none", "0", "0", writer, "2026-10-05T00:00:00Z",
               str(self.checkout), "1", "op-1", "1"]
        self.inventory.append(US.join(row))

    # ------------------------------------------------------------ the fakes
    def write_spec(self) -> None:
        holder = {"none": "HOLDER" + US + "none",
                  "me": f"HOLDER{US}live{US}{ME} sess:1.0 {LANE} 4242 here",
                  "other": f"HOLDER{US}live{US}{OTHER} sess:2.0 {LANE} 4343 here",
                  "unknown": f"HOLDER{US}unknown{US}the records could not be read"}[self.holder]
        reconcile = "\n".join([
            f"ROOT{US}{self.root}/lane-state/{LANE}",
            f"STATE{US}{self.state_word}{US}generation 1{US}operation op-1{US}owner {ME}{US}updated now",
            holder,
            f"BINDING{US}{self.binding[0]}{US}{self.binding[1]}",
            f"TREES{US}{len(self.inventory)} inventoried",
            f"VERDICT{US}{self.verdict}{US}the fixture says so", ""])
        spec = {
            "lane-reconcile": {"rc": 0, "out": reconcile},
            "lane-dir": {"rc": 0, "out": f"{self.checkout}\n"},
            "lane-trees": ({"rc": 0, "out": "\n".join(self.inventory) + "\n"}
                           if self.inventory else {"rc": 8}),
            "managed-projection": {"rc": 8},
            "workspace-root": ({"rc": 0, "out": self.workspace + "\n"} if self.workspace
                               else {"rc": 1, "err": "no workspace\n"}),
            "transcript-holders": {"rc": 8},
            "log": {"rc": self.log_rc, "err": "" if self.log_rc == 0 else "refused\n"},
        }
        spec.update(self.extra_spec)
        self.spec_file.write_text(json.dumps(spec))
        self.prs_file.write_text(json.dumps(self.prs))

    def pr(self, number: int, branch: str, state: str, head: str, base: str = "main") -> None:
        self.prs.append({"number": number, "headRefName": branch, "state": state,
                         "headRefOid": head, "baseRefName": base, "isCrossRepository": False,
                         "mergedAt": "2026-10-01T00:00:00Z" if state == "MERGED" else None})

    # ------------------------------------------------------------ running
    def sweep(self, *args, env: dict | None = None, timeout: int = 180,
              cwd: Path | None = None) -> subprocess.CompletedProcess:
        self.write_spec()
        child = dict(self.env)
        for key, value in (env or {}).items():
            if value is None:
                child.pop(key, None)
            else:
                child[key] = value
        return subprocess.run([sys.executable, str(LW), "sweep", *[str(a) for a in args]],
                              capture_output=True, text=True, env=child, timeout=timeout,
                              cwd=str(cwd or self.root), stdin=subprocess.DEVNULL)

    def notes(self) -> list:
        if not self.helper_log.exists():
            return []
        rows = [json.loads(line) for line in self.helper_log.read_text().splitlines() if line]
        return [r for r in rows if r["argv"][:1] == ["log"]]

    def remote_heads(self) -> dict:
        out = self.git("ls-remote", "--heads", self.origin, cwd=self.root)
        heads = {}
        for line in out.splitlines():
            sha, ref = line.split("\t")
            heads[ref[len("refs/heads/"):]] = sha
        return heads

    def archives(self) -> list:
        base = self.state / "openRepoTools" / "sweeps" / LANE
        return sorted(base.iterdir()) if base.is_dir() else []


def rows_of(out: str) -> dict:
    """The porcelain's tree rows, by path: (disposition, retire, reason)."""
    rows = {}
    for line in out.splitlines():
        cols = line.split("\t")
        if cols[0] == "tree":
            rows[cols[3]] = (cols[1], cols[2], cols[6] if len(cols) > 6 else "")
    return rows


def items_of(out: str, kind: str) -> dict:
    rows = {}
    for line in out.splitlines():
        cols = line.split("\t")
        if cols[0] == kind:
            rows[cols[3]] = (cols[1], cols[2], cols[4], cols[6] if len(cols) > 6 else "")
    return rows


def snapshot(root: Path, skip: tuple = ()) -> dict:
    """Every path under `root` with its kind, size, mode, mtime and content
    digest - what a run that CHANGES NOTHING leaves exactly as it found."""
    out = {}
    for base, dirs, files in os.walk(root):
        for name in dirs + files:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root)
            if any(rel == s or rel.startswith(s + os.sep) for s in skip):
                continue
            st = os.lstat(full)
            digest = ""
            if os.path.islink(full):
                digest = "->" + os.readlink(full)
            elif os.path.isfile(full):
                with open(full, "rb") as fh:
                    digest = hashlib.sha256(fh.read()).hexdigest()
            out[rel] = (st.st_mode, st.st_size if not os.path.isdir(full) else 0,
                        st.st_mtime_ns if not os.path.isdir(full) else 0, digest)
    return out


@pytest.fixture
def estate(tmp_path):
    return Estate(tmp_path)


def build_table(e: Estate) -> dict:
    """A lane whose inventory holds a tree in every state of the table."""
    t = {}
    # clean, squash-MERGED: gh says MERGED and its head is this tip; the
    # squash commit on main is NOT a descendant of it.
    t["merged"] = e.worktree("merged", "feat/merged")
    tip = e.commit(t["merged"], "merged work", {"m.txt": "m\n"})
    e.git("push", "-q", "-u", "origin", "feat/merged", cwd=t["merged"])
    e.git("checkout", "-q", "main")
    e.git("merge", "-q", "--squash", "feat/merged")
    e.commit(e.checkout, "squash of feat/merged (#11)")
    e.git("push", "-q", "origin", "main")
    e.pr(11, "feat/merged", "MERGED", tip)
    # clean, pushed, unmerged (an open PR)
    t["pushed"] = e.worktree("pushed", "feat/pushed")
    tip = e.commit(t["pushed"], "pushed work", {"p.txt": "p\n"})
    e.git("push", "-q", "-u", "origin", "feat/pushed", cwd=t["pushed"])
    e.pr(12, "feat/pushed", "OPEN", tip)
    # clean, one commit beyond its pushed upstream
    t["unpushed"] = e.worktree("unpushed", "feat/unpushed")
    e.commit(t["unpushed"], "first", {"u.txt": "1\n"})
    e.git("push", "-q", "-u", "origin", "feat/unpushed", cwd=t["unpushed"])
    e.commit(t["unpushed"], "second", {"u.txt": "2\n"})
    # clean, never pushed at all
    t["fresh"] = e.worktree("fresh", "feat/fresh", where="claude")
    e.commit(t["fresh"], "fresh work", {"f.txt": "f\n"})
    # clean, DIVERGED from its remote branch
    t["diverged"] = e.worktree("diverged", "feat/diverged")
    e.commit(t["diverged"], "d1", {"d.txt": "1\n"})
    e.commit(t["diverged"], "d2", {"d.txt": "2\n"})
    e.git("push", "-q", "-u", "origin", "feat/diverged", cwd=t["diverged"])
    e.git("reset", "-q", "--hard", "HEAD~1", cwd=t["diverged"])
    e.commit(t["diverged"], "d3", {"d.txt": "3\n"})
    # dirty: a modified file, an untracked one, an ignored secret, a cache
    t["dirty"] = e.worktree("dirty", "feat/dirty")
    e.commit(t["dirty"], "base", {"w.txt": "base\n"})
    e.git("push", "-q", "-u", "origin", "feat/dirty", cwd=t["dirty"])
    (t["dirty"] / "w.txt").write_text("changed\n")
    (t["dirty"] / "new.txt").write_text("untracked\n")
    (t["dirty"] / ".env").write_text("SECRET=1\n")
    (t["dirty"] / "__pycache__").mkdir()
    (t["dirty"] / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\0bytecode")
    # detached at a commit origin holds
    t["det-on"] = e.worktree("det-on")
    # detached with a commit of its own
    t["det-own"] = e.worktree("det-own")
    e.commit(t["det-own"], "orphaned work", {"o.txt": "o\n"})
    # a registration whose directory is gone
    t["stale"] = e.worktree("stale", "feat/stale")
    shutil.rmtree(t["stale"])
    # a FOREIGN tree: git registers it, no inventory names it
    t["foreign"] = e.worktree("foreign", "feat/foreign", where="claude", record=False)
    # an inventory record whose path never existed
    t["gone"] = e.lane_root / "gone"
    e.record(t["gone"], "feat/gone", "0" * 40)
    # a locked registration
    t["locked"] = e.worktree("locked", "feat/locked")
    e.git("worktree", "lock", t["locked"])
    # a clone nested inside a tree: its work is no commit of the tree's
    t["nested"] = e.worktree("nested", "feat/nested")
    e.git("push", "-q", "-u", "origin", "feat/nested", cwd=t["nested"])
    e.git("init", "-q", t["nested"] / "inner", cwd=e.root)
    return t


# =================================================================== the table

def test_every_disposition_row_in_the_dry_run_and_it_changes_nothing(estate):
    t = build_table(estate)
    before = snapshot(estate.root, skip=("helper.log", "helper-spec.json", "prs.json"))
    proc = estate.sweep(LANE, "--porcelain")
    after = snapshot(estate.root, skip=("helper.log", "helper-spec.json", "prs.json"))
    assert proc.returncode == 3, proc.stdout + proc.stderr
    rows = rows_of(proc.stdout)
    want = {
        "merged": "remove+delete-branch", "pushed": "remove", "unpushed": "push+remove",
        "fresh": "push+remove", "diverged": "rescue+remove", "dirty": "wip-rescue+remove",
        "det-on": "remove", "det-own": "rescue+remove", "stale": "prune",
        "foreign": "foreign", "gone": "gone", "locked": "keep", "nested": "keep",
    }
    for name, disposition in want.items():
        assert str(t[name]) in rows, f"{name} is not in the table:\n{proc.stdout}"
        assert rows[str(t[name])][0] == disposition, (name, rows[str(t[name])])
    assert rows[str(t["foreign"])][1] == "-", "a FOREIGN tree is not the lane's to retire"
    assert rows[str(t["gone"])][1] == "-"
    assert rows[str(t["merged"])][1] == "retire"
    assert "PR #11 is merged (gh MERGED)" in rows[str(t["merged"])][2]
    assert "LOCKED" in rows[str(t["locked"])][2]
    assert "nested" in rows[str(t["nested"])][2]
    # ZERO CHANGE: not a ref, not an index, not a file, not a sweeps directory.
    assert before == after, sorted(set(before.items()) ^ set(after.items()))[:10]
    assert not (estate.state / "openRepoTools").exists()
    assert estate.notes() == [], "a dry run writes no register line"


def test_yes_performs_the_table_and_records_every_act(estate):
    t = build_table(estate)
    heads_before = estate.remote_heads()
    tips = {n: estate.git("rev-parse", "HEAD", cwd=p) for n, p in t.items()
            if n not in ("stale", "gone") and p.is_dir()}
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    heads = estate.remote_heads()
    for name in ("merged", "pushed", "unpushed", "fresh", "diverged", "dirty", "det-on", "det-own"):
        assert not t[name].exists(), f"{name} was not removed:\n{proc.stdout}"
    # MERGED: both branches gone (its Lane: trailer is this lane's).
    assert "feat/merged" not in heads
    assert estate.git("branch", "--list", "feat/merged") == ""
    # PUSHED: the branch stays, here and on origin.
    assert heads["feat/pushed"] == heads_before["feat/pushed"]
    assert estate.git("branch", "--list", "feat/pushed").strip() == "feat/pushed"
    # UNPUSHED and FRESH: pushed as is.
    assert heads["feat/unpushed"] == tips["unpushed"]
    assert heads["feat/fresh"] == tips["fresh"]
    rescues = {b: s for b, s in heads.items() if b.startswith(f"rescue/{LANE}/")}
    # DIVERGED: its tip went to a rescue branch; the remote branch is untouched.
    assert heads["feat/diverged"] == heads_before["feat/diverged"]
    assert [b for b, s in rescues.items() if b.startswith(f"rescue/{LANE}/diverged-")
            and s == tips["diverged"]], rescues
    # DETACHED with its own commit: rescued too.
    assert [b for b, s in rescues.items() if b.startswith(f"rescue/{LANE}/det-own-")
            and s == tips["det-own"]], rescues
    # DIRTY: a WIP commit on a rescue branch, carrying the work, named for it.
    wip = [b for b in rescues if b.startswith(f"rescue/{LANE}/dirty-")]
    assert len(wip) == 1, rescues
    subject = estate.git("log", "-1", "--format=%s", rescues[wip[0]], cwd=estate.origin)
    assert LANE in subject and "dirty" in subject and "swept, not reviewed" in subject
    stamp = wip[0].rsplit("-", 1)[1]
    assert stamp in subject
    assert estate.git("show", f"{rescues[wip[0]]}:w.txt", cwd=estate.origin) == "changed"
    # AN UNTRACKED FILE IS NEVER PUSHED (#170 A9): it is in the bundle only.
    assert "new.txt" not in estate.git("ls-tree", "--name-only", rescues[wip[0]],
                                       cwd=estate.origin).split()
    parent = estate.git("rev-parse", f"{rescues[wip[0]]}^", cwd=estate.origin)
    assert parent == tips["dirty"], "the WIP commit sits on the tree's own head"
    # STALE: pruned.
    assert str(t["stale"]) not in estate.git("worktree", "list", "--porcelain")
    # LEFT ALONE: foreign, locked, nested.
    for name in ("foreign", "locked", "nested"):
        assert t[name].is_dir(), f"{name} was touched"
    # THE ARCHIVE: one directory, a manifest that verifies, the disposition,
    # the rescues, a bundle per rescue, the ignored secret and no bytecode.
    (archive,) = estate.archives()
    files = {p.name for p in archive.iterdir()}
    assert {"MANIFEST.sha256", "DISPOSITION.md", "rescues.tsv"} <= files
    for line in (archive / "MANIFEST.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((archive / name).read_bytes()).hexdigest() == digest, name
    assert any(n.startswith("dirty") and n.endswith(".bundle") for n in files), files
    held = [r for r in _ledger(archive) if r[0] == "-" and r[1].startswith("bundle:dirty")]
    assert len(held) == 1 and estate.git("show", f"{held[0][2]}:new.txt") == "untracked"
    assert any(n.startswith("diverged") and n.endswith(".bundle") for n in files), files
    with tarfile.open(archive / "dirty-ignored.tar.gz") as tf:
        names = tf.getnames()
    assert ".env" in names and not any("__pycache__" in n for n in names), names
    disposition = (archive / "DISPOSITION.md").read_text()
    for name in ("merged", "pushed", "dirty", "stale"):
        assert str(t[name]) in disposition
    # ONE REGISTER LINE PER TREE ACTED ON, and no line breaks the grammar.
    notes = estate.notes()
    acted = ("merged", "pushed", "unpushed", "fresh", "diverged", "dirty", "det-on",
             "det-own", "stale")
    assert len(notes) == len(acted), [n["argv"] for n in notes]
    for n in notes:
        assert n["argv"][:3] == ["log", "NOTED", f"lane:{LANE}"] and n["lane"] == LANE
        text = n["argv"][3]
        assert " — " not in text and ", " not in text and "managed" not in text.lower()
    for name in acted:
        assert any(str(t[name]) in n["argv"][3] for n in notes), name


def test_the_rescue_is_on_origin_before_the_tree_is_removed(estate):
    """A refused push leaves the tree EXACTLY as it was: same branch, same
    index, same files - the WIP commit is made beside it, never into it."""
    tree = estate.worktree("dirty", "feat/dirty")
    estate.commit(tree, "base", {"w.txt": "base\n"})
    estate.git("push", "-q", "-u", "origin", "feat/dirty", cwd=tree)
    (tree / "w.txt").write_text("precious\n")
    (tree / "new.txt").write_text("also precious\n")
    hook = estate.origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nwhile read old new ref; do case $ref in "
                    "refs/heads/rescue/*) echo 'no rescues here' >&2; exit 1;; esac; done\n")
    hook.chmod(0o755)
    before = snapshot(tree)
    status_before = estate.git("status", "--porcelain", cwd=tree)
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert rows_of(proc.stdout)[str(tree)][2].count("FAILED") == 1
    assert tree.is_dir() and (tree / "w.txt").read_text() == "precious\n"
    assert estate.git("status", "--porcelain", cwd=tree) == status_before
    assert estate.git("symbolic-ref", "--short", "HEAD", cwd=tree) == "feat/dirty"
    assert snapshot(tree) == before
    assert not [b for b in estate.remote_heads() if b.startswith("rescue/")]
    assert estate.notes() == [], "no register line names a removal that did not happen"


def test_a_live_writer_is_never_touched(estate):
    tree = estate.worktree("live", "feat/live")
    estate.commit(tree, "w", {"l.txt": "l\n"})
    estate.git("push", "-q", "-u", "origin", "feat/live", cwd=tree)
    pane_tree = estate.worktree("pane", "feat/pane")
    estate.git("push", "-q", "-u", "origin", "feat/pane", cwd=pane_tree)
    panes = estate.root / "panes"
    panes.write_text(f"0\tsess:1.0\t{pane_tree}\n")
    sleeper = subprocess.Popen(["sleep", "300"], cwd=str(tree))
    try:
        proc = estate.sweep(LANE, "--yes", "--porcelain",
                            env={"FAKE_TMUX_PANES": str(panes)})
    finally:
        sleeper.kill()
        sleeper.wait()
    rows = rows_of(proc.stdout)
    assert rows[str(tree)][0] == "live", rows
    assert f"process {sleeper.pid}" in rows[str(tree)][2]
    assert rows[str(pane_tree)][0] == "live" and "tmux pane" in rows[str(pane_tree)][2]
    assert tree.is_dir() and pane_tree.is_dir()


def test_the_coordinator_states_its_writer_count_before_yes(estate):
    """THIS session holds the lane: only its ListAgents count says which
    writers are live, so `--yes` wants it (`--live <path>` or `--live none`)."""
    tree = estate.worktree("w1", "feat/w1")
    estate.git("push", "-q", "-u", "origin", "feat/w1", cwd=tree)
    busy = estate.worktree("w2", "feat/w2")
    estate.git("push", "-q", "-u", "origin", "feat/w2", cwd=busy)
    estate.holder = "me"
    estate.state_word, estate.verdict = "RUNNING", "running"
    refused = estate.sweep(LANE, "--yes")
    assert refused.returncode == 2 and "--live" in refused.stdout, refused.stdout
    assert tree.is_dir() and busy.is_dir()
    proc = estate.sweep(LANE, "--yes", "--live", busy, "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    rows = rows_of(proc.stdout)
    assert rows[str(busy)][0] == "live" and "--live" in rows[str(busy)][2]
    assert busy.is_dir() and not tree.exists()


@pytest.mark.parametrize("holder,binding,word", [
    ("none", ("elsewhere", "raven/none"), "bound on raven/none"),
    ("none", ("unknown", ""), "could not be read"),
    ("other", ("here", "Eagle/none"), f"held by live session {OTHER}"),
    ("unknown", ("here", "Eagle/none"), "could not be read"),
])
def test_yes_is_refused_for_a_lane_live_elsewhere_or_unread(estate, holder, binding, word):
    """Amendment 18(b): from outside the binding a lane is UNKNOWN, never
    dead - so nothing is acted on, and the porcelain's answer is 2."""
    tree = estate.worktree("w", "feat/w")
    estate.commit(tree, "w", {"w.txt": "w\n"})
    estate.holder, estate.binding = holder, binding
    # THE REGISTER'S FETCH (#170 A1) is the one write a refused --yes makes,
    # in the workspace repository: the estate is snapshotted without it.
    skip = ("helper.log", "helper-spec.json", "prs.json", "workspace")
    before = snapshot(estate.root, skip=skip)
    dry = estate.sweep(LANE, "--dry-run", "--porcelain")
    assert dry.returncode == 2, dry.stdout + dry.stderr
    assert dry.stdout.splitlines()[1].startswith("refused\t") and word in dry.stdout
    yes = estate.sweep(LANE, "--yes", "--live", "none")
    assert yes.returncode == 2 and word in yes.stdout
    assert tree.is_dir()
    assert snapshot(estate.root, skip=skip) == before
    assert estate.notes() == []


def test_a_managed_lane_is_the_ledgers_and_is_refused(estate):
    estate.worktree("w", "feat/w")
    estate.extra_spec = {"lane-reconcile": {"rc": 0, "out": (
        f"MANAGED{US}ledger-1\nVERDICT{US}managed-owned{US}the ledger's\n")}}
    proc = estate.sweep(LANE, "--porcelain")
    assert proc.returncode == 2 and "managed ledger" in proc.stdout


def test_merged_is_the_register_or_gh_never_ancestry(estate, tmp_path):
    """SQUASH MERGES HIDE COMPLETION BY ANCESTRY (cause 13): a squash-merged
    branch is merged by its PR, and a branch whose tip IS on main but which no
    PR names is NOT merged - its worktree goes, its branch stays."""
    # the register says #21 LANDED while gh still reads it OPEN (a stale read)
    wip_origin = tmp_path / "wip.git"
    wip = tmp_path / "wip"
    estate.git("init", "-q", "--bare", "-b", "main", wip_origin, cwd=tmp_path)
    estate.git("clone", "-q", wip_origin, wip, cwd=tmp_path)
    (wip / "lanes" / "log").mkdir(parents=True)
    (wip / "lanes" / "log" / f"{LANE}.md").write_text(
        f"LANDED — lane {LANE}, session {ME}@Eagle, 2026-10-05T00:00:00Z, {SLUG}#21 → main abc1234\n")
    (wip / "lanes" / "LANES.md").write_text("# register\n")
    estate.git("add", "-A", cwd=wip)
    estate.git("commit", "-q", "-m", "seed", cwd=wip)
    estate.git("push", "-q", "origin", "main", cwd=wip)
    estate.workspace = str(wip)
    by_register = estate.worktree("by-register", "feat/reg")
    tip = estate.commit(by_register, "r", {"r.txt": "r\n"})
    estate.git("push", "-q", "-u", "origin", "feat/reg", cwd=by_register)
    estate.pr(21, "feat/reg", "OPEN", tip)
    # on main by ancestry, and no PR at all
    ancestor = estate.worktree("ancestor", "feat/ancestor")
    estate.commit(ancestor, "a", {"a.txt": "a\n"})
    estate.git("push", "-q", "-u", "origin", "feat/ancestor", cwd=ancestor)
    estate.git("merge", "-q", "--ff-only", "feat/ancestor")
    estate.git("push", "-q", "origin", "main")
    assert "feat/ancestor" in estate.git("branch", "--merged", "main")
    proc = estate.sweep(LANE, "--porcelain")
    rows = rows_of(proc.stdout)
    assert rows[str(by_register)][0] == "remove+delete-branch"
    assert "register LANDED" in rows[str(by_register)][2]
    assert rows[str(ancestor)][0] == "remove", rows[str(ancestor)]
    yes = estate.sweep(LANE, "--yes")
    assert yes.returncode == 0, yes.stdout + yes.stderr
    assert estate.git("branch", "--list", "feat/ancestor").strip() == "feat/ancestor"
    assert estate.git("branch", "--list", "feat/reg") == ""


def test_a_merge_into_another_base_is_no_landing_and_an_open_pr_comes_first(estate):
    """Copilot on #168: a PR merged into a release branch is no landing on
    main, and an OPEN PR protects its branch however an older PR of the same
    branch was merged."""
    elsewhere = estate.worktree("elsewhere", "feat/rel")
    tip = estate.commit(elsewhere, "e", {"e.txt": "e\n"})
    estate.git("push", "-q", "-u", "origin", "feat/rel", cwd=elsewhere)
    estate.pr(41, "feat/rel", "MERGED", tip, base="release/1")
    reopened = estate.worktree("reopened", "feat/again")
    old = estate.commit(reopened, "o", {"o.txt": "o\n"})
    estate.git("push", "-q", "-u", "origin", "feat/again", cwd=reopened)
    estate.pr(42, "feat/again", "MERGED", old)
    estate.pr(43, "feat/again", "OPEN", old)
    rows = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert rows[str(elsewhere)][0] == "remove", rows[str(elsewhere)]
    assert "merged into release/1" in rows[str(elsewhere)][2]
    assert rows[str(reopened)][0] == "remove" and "PR #43 is open" in rows[str(reopened)][2]
    yes = estate.sweep(LANE, "--yes")
    assert yes.returncode == 0, yes.stdout + yes.stderr
    local = estate.git("branch", "--format=%(refname:short)").splitlines()
    assert "feat/rel" in local and "feat/again" in local, "neither branch is merged"
    assert {"feat/rel", "feat/again"} <= set(estate.remote_heads())


def test_without_gh_nothing_is_called_merged(estate):
    tree = estate.worktree("m", "feat/m")
    tip = estate.commit(tree, "m", {"m.txt": "m\n"})
    estate.git("push", "-q", "-u", "origin", "feat/m", cwd=tree)
    estate.pr(5, "feat/m", "MERGED", tip)
    proc = estate.sweep(LANE, "--porcelain", env={"LANES_NO_GITHUB": "1"})
    assert rows_of(proc.stdout)[str(tree)][0] == "remove"
    assert "LANES_NO_GITHUB=1" in estate.sweep(LANE, env={"LANES_NO_GITHUB": "1"}).stdout


def test_a_tree_another_lanes_inventory_also_names_is_kept(estate):
    """Copilot on #168: inventory records are history and a path can be
    reused, so a tree BOTH lanes' inventories name is neither's to sweep."""
    tree = estate.worktree("shared", "feat/shared")
    estate.git("push", "-q", "-u", "origin", "feat/shared", cwd=tree)
    other = estate.root / "lane-state" / "repoA-7" / "trees"
    other.mkdir(parents=True)
    (other / "c1.yaml").write_text(f"schema: 1\npath: {tree}\n")
    rows = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert rows[str(tree)][0] == "keep" and "repoA-7's inventory names it too" in rows[str(tree)][2]
    assert estate.sweep(LANE, "--yes").returncode == 0
    assert tree.is_dir()


def test_an_unreadable_claim_of_another_lane_refuses_before_any_write(estate):
    """Copilot round 2 on #168: a sibling inventory record that cannot be
    read is an unknown claim, never "no claim" - refused, and refused before
    the fetch."""
    estate.worktree("w", "feat/w")
    other = estate.root / "lane-state" / "repoA-7" / "trees"
    other.mkdir(parents=True)
    (other / "c1.yaml").write_text("schema: 1\n")
    # (the register's fetch under --yes, #170 A1, is in the workspace only)
    skip = ("helper.log", "helper-spec.json", "prs.json", "workspace")
    before = snapshot(estate.root, skip=skip)
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "lane repoA-7's inventory record c1.yaml (it names no path)" in proc.stdout
    assert snapshot(estate.root, skip=skip) == before


def test_a_submodules_ignored_files_keep_its_tree(estate):
    """Copilot round 2 on #168: an `.env` in a submodule is in no archive -
    the tree's ignored-file archive lists the superproject's only."""
    sub_origin = estate.remotes / "sub.git"
    estate.git("init", "-q", "--bare", "-b", "main", sub_origin, cwd=estate.root)
    seed = estate.root / "sub-seed"
    estate.git("clone", "-q", sub_origin, seed, cwd=estate.root)
    estate.commit(seed, "sub", {".gitignore": ".env\n", "s.txt": "s\n"})
    estate.git("push", "-q", "origin", "main", cwd=seed)
    tree = estate.worktree("withsub", "feat/withsub", record=False)
    estate.git("submodule", "add", "-q", str(sub_origin), "sub", cwd=tree)
    estate.commit(tree, "add sub")
    estate.git("push", "-q", "-u", "origin", "feat/withsub", cwd=tree)
    (tree / "sub" / ".env").write_text("SECRET=1\n")
    estate.record(tree)
    rows = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert rows[str(tree)][0] == "keep", rows[str(tree)]
    assert "submodule sub holds ignored files no commit carries (.env)" in rows[str(tree)][2]


def test_a_cache_whose_tracking_cannot_be_read_is_left(estate):
    """Copilot round 2 on #168: an index git cannot read is no proof a cache
    is untracked."""
    tree = estate.worktree("badindex", "feat/badindex")
    estate.git("push", "-q", "-u", "origin", "feat/badindex", cwd=tree)
    (tree / "__pycache__").mkdir()
    (tree / "__pycache__" / "b.pyc").write_bytes(b"\0")
    index = Path(estate.git("rev-parse", "--git-path", "index", cwd=tree))
    index = index if index.is_absolute() else tree / index
    index.write_bytes(b"not an index")
    proc = estate.sweep(LANE, "--include-caches", "--porcelain")
    assert str(tree / "__pycache__") not in items_of(proc.stdout, "cache"), proc.stdout


def test_a_clone_its_linked_worktrees_share_is_kept(estate):
    """Copilot on #168: removing a clone takes the git directory every
    worktree linked to it shares, a live writer's included."""
    clone = estate.lane_root / "cl"
    estate.git("clone", "-q", GH_URL, clone, cwd=estate.root)
    linked = estate.root / "elsewhere-wt"
    estate.git("worktree", "add", "-q", "-b", "feat/linked", linked, "origin/main", cwd=clone)
    estate.record(clone)
    rows = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert rows[str(clone)][0] == "keep", rows[str(clone)]
    assert "linked worktree(s) share" in rows[str(clone)][2]


def test_an_unreadable_inventory_record_refuses_the_sweep(estate):
    """Copilot on #168: a record that cannot be read is a tree whose owner is
    unknown, so the sweep refuses rather than report nothing to retire."""
    estate.worktree("fine", "feat/fine")
    estate.inventory.append(US.join(["c9-odd", str(estate.lane_root / "odd"), "x", "y", "none",
                                     "0", "0", WRITER, "2026-10-05T00:00:00Z",
                                     str(estate.checkout), "1", "op-1", "9"]))
    skip = ("helper.log", "helper-spec.json", "prs.json", "workspace")
    before = snapshot(estate.root, skip=skip)
    for args in (("--dry-run", "--porcelain"), ("--yes",)):
        proc = estate.sweep(LANE, *args)
        assert proc.returncode == 2, (args, proc.stdout, proc.stderr)
        assert "c9-odd is unreadable or of schema 9" in proc.stdout
    assert snapshot(estate.root, skip=skip) == before


def test_the_lane_name_is_resolved_before_anything_is_derived_from_it(estate):
    """Copilot on #168: Amendment 15's resolver first, as lane-start and
    lane-end read it; an alias table that cannot be read refuses."""
    estate.worktree("w", "feat/w")
    estate.extra_spec = {"canon-lane": {"rc": 0, "out": f"{LANE}\n"}}
    proc = estate.sweep(LANE.upper(), "--porcelain")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert proc.stdout.splitlines()[0].split("\t")[:2] == ["lane", LANE]
    reconcile = [r for r in (json.loads(x) for x in estate.helper_log.read_text().splitlines())
                 if r["argv"][:1] == ["lane-reconcile"]]
    assert reconcile[-1]["argv"] == ["lane-reconcile", LANE]
    estate.extra_spec = {"canon-lane": {"rc": 66, "err": "the alias table could not be read\n"}}
    refused = estate.sweep(LANE, "--porcelain")
    assert refused.returncode == 2 and "alias table could not be read" in refused.stdout


def test_include_foreign_takes_a_word_and_another_lanes_tree_is_never_taken(estate):
    mine = estate.worktree("foreign-a", "feat/fa", where="claude", record=False)
    estate.git("push", "-q", "-u", "origin", "feat/fa", cwd=mine)
    theirs = estate.worktree("foreign-b", "feat/fb", where="claude", record=False)
    estate.git("push", "-q", "-u", "origin", "feat/fb", cwd=theirs)
    other_trees = estate.root / "lane-state" / "repoB-2" / "trees"
    other_trees.mkdir(parents=True)
    (other_trees / "x.yaml").write_text(f"schema: 1\npath: {theirs}\n")
    conf = estate.root / "sweep.conf"
    conf.write_text("foreign_quiet_hours=0\n")
    env = {"LANE_WORKTREES_CONF": str(conf)}
    refused = estate.sweep(LANE, "--yes", "--include-foreign", env=env)
    assert refused.returncode == 2 and "--word" in refused.stdout
    proc = estate.sweep(LANE, "--yes", "--include-foreign", "--word", "sweep them", "--porcelain",
                        env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    rows = rows_of(proc.stdout)
    assert not mine.exists()
    assert rows[str(theirs)][0] == "foreign" and "repoB-2" in rows[str(theirs)][2]
    assert theirs.is_dir()
    assert any("sweep them" in n["argv"][3] for n in estate.notes())


# ================================================================ --branches

def test_branches_deletes_the_merged_lists_the_unpublished_and_spares_an_open_pr(estate):
    def branch(name, push=True, lane=LANE):
        estate.git("checkout", "-q", "-b", name, "origin/main")
        tip = estate.commit(estate.checkout, name, {name.replace("/", "_"): "x\n"}, lane=lane)
        if push:
            estate.git("push", "-q", "-u", "origin", name)
        estate.git("checkout", "-q", "main")
        return tip

    merged = branch("feat/b-merged")
    estate.pr(31, "feat/b-merged", "MERGED", merged)
    theirs = branch("feat/b-theirs", lane="repoB-2")
    estate.pr(32, "feat/b-theirs", "MERGED", theirs)
    opened = branch("feat/b-open", push=False)
    estate.pr(33, "feat/b-open", "OPEN", opened)
    unpublished = branch("feat/b-local", push=False)
    estate.git("checkout", "-q", "-b", "rescue/repoA-1/old-20260101T000000Z", "origin/main")
    estate.git("checkout", "-q", "main")
    proc = estate.sweep(LANE, "--branches", "--porcelain")
    items = items_of(proc.stdout, "branch")
    assert items["feat/b-merged"][0] == "delete+remote", items
    assert items["feat/b-theirs"][0] == "delete" and items["feat/b-theirs"][1] == "-"
    assert items["feat/b-open"][0] == "keep" and "open" in items["feat/b-open"][3]
    assert items["feat/b-local"][0] == "list"
    detail = items["feat/b-local"][2]
    assert unpublished[:12] in detail and "1 ahead/0 behind" in detail and "owner repoA-1" in detail
    assert not any(k.startswith("rescue/") for k in items)
    yes = estate.sweep(LANE, "--branches", "--yes")
    assert yes.returncode == 0, yes.stdout + yes.stderr
    heads = estate.remote_heads()
    local = estate.git("branch", "--format=%(refname:short)").splitlines()
    assert "feat/b-merged" not in local and "feat/b-merged" not in heads
    assert "feat/b-theirs" not in local and "feat/b-theirs" in heads, "not ours: remote kept"
    assert "feat/b-open" in local and "feat/b-local" in local
    assert "rescue/repoA-1/old-20260101T000000Z" in local
    assert any("branches merged by PR" in n["argv"][3] for n in estate.notes())


# ========================================== scratch, caches, sandboxes, links

def test_scratch_is_archived_then_removed_and_caches_are_removed(estate):
    scratch = estate.lane_root / "x-scratch"
    (scratch / "notes").mkdir(parents=True)
    (scratch / "notes" / "a.md").write_text("findings\n")
    (scratch / "__pycache__").mkdir()
    (scratch / "__pycache__" / "z.pyc").write_bytes(b"\0")
    briefs = estate.lane_root / "briefs"
    briefs.mkdir(parents=True)
    (briefs / "b.md").write_text("brief\n")
    # a tree the sweep KEEPS (its registration is locked), with caches in it
    kept = estate.worktree("kept", "feat/kept")
    estate.commit(kept, "k", {"k.txt": "k\n", ".gitignore": "__pycache__/\nenv/\n"})
    estate.git("push", "-q", "-u", "origin", "feat/kept", cwd=kept)
    (kept / "__pycache__").mkdir()
    (kept / "__pycache__" / "y.pyc").write_bytes(b"\0")
    venv = kept / "env"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr\n")
    estate.git("worktree", "lock", kept)
    # a tree a LIVE writer stands in: its caches are its writer's
    busy = estate.worktree("busy", "feat/busy")
    estate.git("push", "-q", "-u", "origin", "feat/busy", cwd=busy)
    (busy / "__pycache__").mkdir()
    sleeper = subprocess.Popen(["sleep", "300"], cwd=str(busy))
    try:
        proc = estate.sweep(LANE, "--include-scratch", "--include-caches", "--yes", "--porcelain")
    finally:
        sleeper.kill()
        sleeper.wait()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    scratch_rows = items_of(proc.stdout, "scratch")
    assert scratch_rows[str(scratch)][0] == "archive+remove"
    assert not scratch.exists() and not briefs.exists()
    (archive,) = estate.archives()
    with tarfile.open(archive / "scratch-x-scratch.tar.gz") as tf:
        names = tf.getnames()
    assert "x-scratch/notes/a.md" in names and not any("__pycache__" in n for n in names)
    caches = items_of(proc.stdout, "cache")
    assert str(kept / "__pycache__") in caches and str(venv) in caches
    assert not (kept / "__pycache__").exists() and not venv.exists()
    assert (kept / "k.txt").exists(), "a cache sweep removes caches and nothing else"
    assert (busy / "__pycache__").is_dir(), "a live writer's caches are left"
    assert str(scratch / "__pycache__") not in caches, "it went with its scratch"


def test_caches_are_never_taken_from_a_foreign_tree(estate):
    """Copilot on #168: a FOREIGN tree under the lane's root is somebody's,
    live or not, and so are its caches."""
    foreign = estate.worktree("theirs", "feat/theirs", where="claude", record=False)
    (foreign / "__pycache__").mkdir()
    (foreign / "__pycache__" / "t.pyc").write_bytes(b"\0")
    proc = estate.sweep(LANE, "--include-caches", "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert str(foreign / "__pycache__") not in items_of(proc.stdout, "cache")
    assert (foreign / "__pycache__" / "t.pyc").exists()


def test_branch_deletes_wait_for_a_fetch_that_worked(estate):
    """Copilot on #168: --yes deletes a merged branch only once origin was
    read NOW - the lane's own checkout is fetched too, and a fetch that
    failed deletes nothing."""
    estate.git("checkout", "-q", "-b", "feat/gone-merged", "origin/main")
    tip = estate.commit(estate.checkout, "g", {"g.txt": "g\n"})
    estate.git("push", "-q", "-u", "origin", "feat/gone-merged")
    estate.git("checkout", "-q", "main")
    estate.pr(51, "feat/gone-merged", "MERGED", tip)
    estate.origin.rename(estate.origin.with_name("moved.git"))
    try:
        proc = estate.sweep(LANE, "--branches", "--yes", "--porcelain")
    finally:
        estate.origin.with_name("moved.git").rename(estate.origin)
    items = items_of(proc.stdout, "branch")
    assert items["feat/gone-merged"][0] == "keep", items
    assert "origin could not be fetched" in items["feat/gone-merged"][3]
    assert "feat/gone-merged" in estate.git("branch", "--format=%(refname:short)").splitlines()


def test_a_clean_tree_without_origin_is_bundled_and_removed_under_bundle_yes(estate):
    """Copilot on #168: `--yes` fetches, and a repository with no origin is
    no failed fetch - the dry run's `bundle+remove` is what `--yes` does."""
    solo = estate.projects / "solo"
    estate.git("init", "-q", "-b", "main", solo, cwd=estate.root)
    estate.commit(solo, "solo", {"s.txt": "s\n"})
    lone = estate.lane_root / "lone"
    estate.lane_root.mkdir(parents=True, exist_ok=True)
    estate.git("worktree", "add", "-q", "-b", "feat/lone", lone, "main", cwd=solo)
    estate.commit(lone, "lone", {"l.txt": "l\n"})
    estate.record(lone)
    dry = rows_of(estate.sweep(LANE, "--bundle", "--porcelain").stdout)
    assert dry[str(lone)][0] == "bundle+remove", dry
    yes = estate.sweep(LANE, "--bundle", "--yes", "--porcelain")
    assert yes.returncode == 0, yes.stdout + yes.stderr
    assert not lone.exists()
    (archive,) = estate.archives()
    assert (archive / "lone.bundle").is_file()


def test_a_distance_to_origin_that_cannot_be_read_keeps_the_tree(estate):
    """Copilot on #168: a failed `rev-list` is a read error, never "0 ahead"
    - which is what lets a tree go without a rescue."""
    tree = estate.worktree("broken", "feat/broken", record=False)
    pushed = estate.commit(tree, "c", {"c.txt": "c\n"})
    estate.git("push", "-q", "-u", "origin", "feat/broken", cwd=tree)
    estate.commit(tree, "d", {"d.txt": "d\n"})
    estate.record(tree)
    # origin's tip goes missing from the clone's object store: the distance
    # from it to HEAD can no longer be walked
    obj = estate.checkout / ".git" / "objects" / pushed[:2] / pushed[2:]
    assert obj.is_file()
    obj.unlink()
    proc = estate.sweep(LANE, "--porcelain")
    rows = rows_of(proc.stdout)
    assert rows[str(tree)][0] == "keep", rows[str(tree)]
    assert "could not be read" in rows[str(tree)][2]


def test_killed_suite_sandboxes_whose_owner_is_gone_are_removed(estate):
    user = os.environ.get("USER") or __import__("getpass").getuser()
    base = estate.sandboxes
    old = time.time() - 7200
    dead = base / "tmp.deadbeef01"
    young = base / "tmp.youngone02"
    held = base / "tmp.heldopen03"
    for d in (dead, young, held):
        d.mkdir()
        (d / "f").write_text("x")
    # A SUITE'S MARK (#170 item 1): pytest's `.lock`, naming a pid that is gone.
    (dead / ".lock").write_text("999999\n")
    for d in (dead, held):
        for p in (d / "f", d / ".lock", d):
            if p.exists():
                os.utime(p, (old, old))
    pyroot = base / f"pytest-of-{user}"
    gone_run = pyroot / "pytest-7"
    live_run = pyroot / "pytest-8"
    for d in (gone_run, live_run):
        d.mkdir(parents=True)
    (gone_run / ".lock").write_text("999999\n")
    (live_run / ".lock").write_text(f"{os.getpid()}\n")
    sleeper = subprocess.Popen(["sleep", "300"], cwd=str(held))
    try:
        proc = estate.sweep(LANE, "--include-sandboxes", "--yes", "--porcelain")
    finally:
        sleeper.kill()
        sleeper.wait()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not dead.exists() and not gone_run.exists()
    assert young.is_dir(), "younger than the minimum age"
    assert held.is_dir(), "a live process stands in it"
    assert live_run.is_dir(), "its .lock names a live pid"


def test_links_lists_every_broken_symlink_and_gitdir_pointer(estate):
    estate.git("push", "-q", "origin", "main")
    (estate.projects / "dangling").symlink_to(estate.projects / "nowhere")
    (estate.projects / "fine").symlink_to(estate.checkout)
    tree = estate.worktree("moved", "feat/moved")
    shutil.move(str(estate.checkout / ".git" / "worktrees" / "moved"),
                str(estate.root / "elsewhere"))
    proc = estate.sweep(LANE, "--links", "--porcelain")
    links = items_of(proc.stdout, "link")
    assert str(estate.projects / "dangling") in links
    assert "nowhere" in links[str(estate.projects / "dangling")][3]
    assert str(tree / ".git") in links and "gitdir pointer" in links[str(tree / ".git")][3]
    assert str(estate.projects / "fine") not in links


def test_a_clone_something_leans_on_is_load_bearing_and_never_removed(estate):
    """CLONES AS SHARED GIT STORES (cause 14): a clone another repository
    reads objects from, or names as a remote, is never removed."""
    store = estate.lane_root / "store"
    estate.git("clone", "-q", GH_URL, store, cwd=estate.root)
    dependent = estate.projects / "dependent"
    estate.git("clone", "-q", "--shared", store, dependent, cwd=estate.root)
    assert (dependent / ".git" / "objects" / "info" / "alternates").exists()
    conf = estate.root / "sweep.conf"
    conf.write_text("foreign_quiet_hours=0\n")
    proc = estate.sweep(LANE, "--include-foreign", "--word", "go", "--yes", "--porcelain",
                        env={"LANE_WORKTREES_CONF": str(conf)})
    rows = rows_of(proc.stdout)
    assert rows[str(store)][0] == "load-bearing", rows
    assert str(dependent) in rows[str(store)][2] and "repack" in rows[str(store)][2]
    assert store.is_dir()
    again = estate.sweep(LANE, "--porcelain", env={"LANE_WORKTREES_CONF": str(conf)})
    assert "LOAD-BEARING" in rows_of(again.stdout)[str(store)][2]


# =================================================================== --expire

def _archive(estate, days: int, branch: str | None, sha: str = "0" * 40,
             manifest: bool = True) -> Path:
    """A sweep archive `days` old, as `--yes` leaves one: DISPOSITION.md,
    rescues.tsv naming `branch` at `sha`, and a MANIFEST.sha256 of both."""
    when = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days, hours=1)
    d = estate.state / "openRepoTools" / "sweeps" / LANE / when.strftime("%Y%m%dT%H%M%SZ")
    d.mkdir(parents=True)
    (d / "DISPOSITION.md").write_text("# x\n")
    rows = "# origin\tbranch\tsha\tcheckout\ttree\n"
    if branch:
        rows += f"{GH_URL}\t{branch}\t{sha}\t-\t-\n"
    (d / "rescues.tsv").write_text(rows)
    if manifest:
        (d / "MANIFEST.sha256").write_text("".join(
            f"{hashlib.sha256((d / n).read_bytes()).hexdigest()}  {n}\n"
            for n in ("DISPOSITION.md", "rescues.tsv")))
    return d


def test_expire_keeps_young_archives_and_any_whose_rescue_left_origin(estate):
    estate.git("push", "-q", "origin", "main:refs/heads/rescue/repoA-1/kept-1")
    sha = estate.git("rev-parse", "main")
    young = _archive(estate, 89, "rescue/repoA-1/kept-1", sha)
    due = _archive(estate, 90, "rescue/repoA-1/kept-1", sha)
    orphan = _archive(estate, 120, "rescue/repoA-1/gone-1", sha)
    plain = _archive(estate, 91, None)
    # THE RESCUED COMMIT, NOT THE NAME: the branch is on origin at another sha.
    moved = _archive(estate, 92, "rescue/repoA-1/kept-1", "1" * 40)
    # AN ARCHIVE A SWEEP NEVER FINISHED (no manifest), and one holding a file
    # its manifest does not list (a bundle the ledger never recorded).
    unfinished = _archive(estate, 93, None, manifest=False)
    stray = _archive(estate, 94, None)
    (stray / "x.bundle").write_bytes(b"bundle")
    # ... and one whose manifest lists a file that is gone (round 2)
    lost = _archive(estate, 95, None)
    with open(lost / "MANIFEST.sha256", "a") as fh:
        fh.write(f"{'0' * 64}  lost.bundle\n")
    dry = estate.sweep("--expire", "--porcelain")
    assert dry.returncode == 3, dry.stdout + dry.stderr
    rows = {line.split("\t")[2]: line.split("\t")[1] for line in dry.stdout.splitlines()}
    why = {line.split("\t")[2]: line.split("\t")[4] for line in dry.stdout.splitlines()}
    assert rows[str(young)] == "keep" and rows[str(due)] == "expire"
    assert rows[str(orphan)] == "keep" and rows[str(plain)] == "expire"
    assert rows[str(moved)] == "keep" and "not the rescued 1111111" in why[str(moved)]
    assert rows[str(unfinished)] == "keep" and "MANIFEST" in why[str(unfinished)]
    assert rows[str(stray)] == "keep" and "x.bundle" in why[str(stray)]
    assert rows[str(lost)] == "keep" and "lost.bundle" in why[str(lost)]
    assert young.is_dir() and due.is_dir()
    yes = estate.sweep("--expire", "--yes")
    assert yes.returncode == 0, yes.stdout + yes.stderr
    assert young.is_dir() and orphan.is_dir()
    assert moved.is_dir() and unfinished.is_dir() and stray.is_dir() and lost.is_dir()
    assert not due.exists() and not plain.exists()
    log = (estate.state / "openRepoTools" / "sweeps" / "EXPIRED.log").read_text()
    assert str(due) in log and str(orphan) not in log
    conf = estate.root / "sweep.conf"
    conf.write_text("retention_days=200\n")
    later = estate.sweep("--expire", "--porcelain", env={"LANE_WORKTREES_CONF": str(conf)})
    assert later.returncode == 0 and "\texpire\t" not in later.stdout


# ======================================================= the porcelain contract

def test_the_porcelain_exit_codes_lane_end_reads(estate):
    """#163's gate: 0 nothing to retire, 3 something to retire, 2 refused."""
    nothing = estate.sweep(LANE, "--dry-run", "--porcelain")
    assert nothing.returncode == 0, nothing.stdout + nothing.stderr
    last = nothing.stdout.splitlines()[-1].split("\t")
    assert last[:2] == ["summary", "0"]
    estate.worktree("w", "feat/w")
    something = estate.sweep(LANE, "--dry-run", "--porcelain")
    assert something.returncode == 3
    assert something.stdout.splitlines()[0].split("\t")[:2] == ["lane", LANE]
    assert something.stdout.splitlines()[-1].split("\t")[:2] == ["summary", "1"]
    estate.extra_spec = {"lane-reconcile": {"rc": 1, "err": "the log could not be read\n"}}
    refused = estate.sweep(LANE, "--dry-run", "--porcelain")
    assert refused.returncode == 2 and "refused\t" in refused.stdout


def test_yes_needs_no_enabling_variable(estate):
    """#170 landed: `--yes` and `--expire --yes` act with no switch in the
    environment (LANE_WORKTREES_ENABLE_YES is gone)."""
    tree = estate.worktree("w", "feat/w")
    estate.git("push", "-q", "-u", "origin", "feat/w", cwd=tree)
    old = _archive(estate, 120, None)
    assert "LANE_WORKTREES_ENABLE_YES" not in estate.env
    yes = estate.sweep(LANE, "--yes", "--porcelain")
    assert yes.returncode == 0, yes.stdout + yes.stderr
    assert not tree.exists()
    expire = estate.sweep("--expire", "--yes")
    assert expire.returncode == 0, expire.stdout + expire.stderr
    assert not old.exists()


def test_trees_under_the_lanes_root_or_carrying_its_trailer_are_its_own(estate):
    """B1: a tree #97's inventory does not name is the lane's when it stands
    under `.lane-worktrees/<lane>/`, or sits in `.claude/worktrees` on a branch
    whose own commits carry this lane's trailer - so the gate does not pass a
    lane whose trees were never recorded."""
    conf = estate.root / "sweep.conf"
    conf.write_text("foreign_quiet_hours=0\n")
    estate.env["LANE_WORKTREES_CONF"] = str(conf)
    rooted = estate.worktree("rooted", "feat/rooted", record=False)
    trailed = estate.worktree("trailed", "feat/trailed", where="claude", record=False)
    estate.commit(trailed, "mine", {"m.txt": "m\n"})
    other = estate.worktree("other", "feat/other", where="claude", record=False)
    estate.commit(other, "theirs", {"o.txt": "o\n"}, lane="repoB-2")
    # A CLONE under the lane's root is never adopted: a lane makes worktrees.
    clone = estate.lane_root / "cloned"
    estate.git("clone", "-q", GH_URL, clone, cwd=estate.root)
    proc = estate.sweep(LANE, "--dry-run", "--porcelain")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    rows = rows_of(proc.stdout)
    assert rows[str(rooted)][:2] == ("remove", "retire") and "the lane's by its root" in rows[str(rooted)][2]
    assert rows[str(trailed)][1] == "retire" and "Lane: trailer" in rows[str(trailed)][2]
    assert rows[str(other)][0] == "foreign"
    assert rows[str(clone)][:2] == ("foreign", "-"), rows[str(clone)]
    # NO SNAPSHOT AT ALL, and trees of its own: the gate does not pass.
    estate.extra_spec = {"lane-reconcile": {"rc": 8},
                         "binding": {"rc": 0, "out": "x\tx\tx\tx\tx\tx\there\tnone\n"},
                         "live-holder": {"rc": 8}}
    none = estate.sweep(LANE, "--dry-run", "--porcelain")
    assert none.returncode == 2, none.stdout + none.stderr
    assert "has no #97 snapshot (state NONE)" in none.stdout
    assert str(rooted) in rows_of(none.stdout), "the table is still printed"


def test_porcelain_escapes_a_tab_and_a_newline_in_a_path(estate):
    """B3: a TAB or a newline in a tree's name is still one field of one row."""
    estate.lane_root.mkdir(parents=True, exist_ok=True)
    tab = estate.lane_root / "tab\tname"
    nl = estate.lane_root / "nl\nname"
    for i, path in enumerate((tab, nl)):
        estate.git("worktree", "add", "-q", "-b", f"feat/odd{i}", path, "origin/main")
    proc = estate.sweep(LANE, "--dry-run", "--porcelain")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert all(ln.split("\t")[0] in ("lane", "tree", "summary") for ln in lines), lines
    trees = [ln for ln in lines if ln.startswith("tree\t")]
    assert all(len(ln.split("\t")) == 7 for ln in trees), lines
    paths = [ln.split("\t")[3] for ln in trees]
    assert str(tab).replace("\t", "\\t") in paths and str(nl).replace("\n", "\\n") in paths
    if subprocess.run(["git", "worktree", "list", "--porcelain", "-z"], cwd=str(estate.checkout),
                      capture_output=True).returncode == 0:
        assert len(trees) == 2, "a newline in a registered path is one registration, not two"


def test_a_path_that_is_not_utf8_is_a_row_not_a_traceback(estate):
    """B2: a worktree named in Latin-1 is reported - exit inside 0/3/2."""
    estate.lane_root.mkdir(parents=True, exist_ok=True)
    bad = os.fsencode(str(estate.lane_root)) + b"/caf\xe9"
    subprocess.run(["git", "-C", str(estate.checkout), "worktree", "add", "-q", "-b", "feat/latin1",
                    bad, "origin/main"], env=estate.env, check=True, capture_output=True)
    estate.write_spec()
    for args in (("--dry-run", "--porcelain"), ("--dry-run",)):
        proc = subprocess.run([sys.executable, str(LW), "sweep", LANE, *args], capture_output=True,
                              env=estate.env, timeout=180, cwd=str(estate.root),
                              stdin=subprocess.DEVNULL)
        assert proc.returncode in (0, 3), (args, proc.stdout[-500:], proc.stderr[-800:])
        assert b"Traceback" not in proc.stderr
        assert bad in proc.stdout, "the path is reported as the bytes it is"


def test_an_unreadable_pytest_sandbox_root_is_a_row_not_a_traceback(estate):
    """B2: an unreadable `pytest-of-$USER` is listed as kept, exit 0."""
    root = estate.sandboxes / f"pytest-of-{getpass.getuser()}"
    root.mkdir()
    root.chmod(0)
    try:
        proc = estate.sweep(LANE, "--include-sandboxes", "--dry-run", "--porcelain")
    finally:
        root.chmod(0o755)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr
    if os.geteuid() != 0:
        rows = items_of(proc.stdout, "sandbox")
        assert rows[str(root)][0] == "keep" and "could not be listed" in rows[str(root)][3]


def test_usage_errors_are_64(estate):
    for argv in (["--bogus"], [], ["--word", "x"]):
        proc = estate.sweep(*argv) if argv != [] else estate.sweep()
        assert proc.returncode == 64, (argv, proc.stdout, proc.stderr)
    proc = subprocess.run([sys.executable, str(LW), "--help"], capture_output=True, text=True)
    assert proc.returncode == 0 and "sweep <lane>" in proc.stdout


# ========================================== the real helper, end to end (#97)

UUID_R = "33333333-3333-4333-8333-333333333333"


def _real_estate(tmp_path: Path, host: str) -> tuple:
    """The fake estate, with the REAL `lanes-edit.sh` and a workspace."""
    e = Estate(tmp_path)
    wip_origin = tmp_path / "wip.git"
    wip = e.projects / "wip"
    e.git("init", "-q", "--bare", "-b", "main", wip_origin, cwd=tmp_path)
    e.git("clone", "-q", wip_origin, wip, cwd=tmp_path)
    (wip / "lanes" / "log").mkdir(parents=True)
    (wip / "lanes" / "LANES.md").write_text("\n".join([
        "# LANES.md", "",
        "| lane | session id | workstation / env / user | started (UTC) | objects owned | handoff path | state |",
        "|---|---|---|---|---|---|---|",
        f"| `{LANE}` | harness `{UUID_R}` | Eagle / test / brett | 2026-10-05T00:00Z | none | handoffs/{LANE}.md | LIVE · 2026-10-05T00:00:00Z · working |",
        ""]))
    (wip / "lanes" / "log" / f"{LANE}.md").write_text(
        f"STARTED — lane {LANE}, session {UUID_R}@Eagle, 2026-10-05T00:00:00Z, "
        f"lane:{LANE} → home {SLUG}; dir {e.checkout}; host {host}; container none; os linux\n")
    e.git("add", "-A", cwd=wip)
    e.git("commit", "-q", "-m", "seed", cwd=wip)
    e.git("push", "-q", "origin", "main", cwd=wip)
    agents = e.home / ".agents"
    agents.mkdir()
    (agents / "workspace.yaml").write_text(f"repository: {wip_origin}\npath: {wip}\n")
    e.env.update(AGENT_PROTOCOL_ROOT=str(agents), LANES_EDIT=str(LANES_EDIT),
                 LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none",
                 LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1", LANES_INDEX="off",
                 LANES_LANE_STATE_ROOT=str(tmp_path / "lane-state"),
                 CLAUDE_CONFIG_DIR=str(e.home / ".claude"), LANES_SESSION=UUID_R)
    e.env.pop("CLAUDE_CODE_SESSION_ID", None)
    return e, wip


def _real_tree(e: Estate, name: str) -> Path:
    path = e.worktree(name, f"feat/{name}", record=False)
    e.commit(path, name, {f"{name}.txt": "x\n"})
    e.git("push", "-q", "-u", "origin", f"feat/{name}", cwd=path)
    proc = subprocess.run(["bash", str(LANES_EDIT), "set-lane-tree", LANE, str(path),
                           "--checkout", str(e.checkout)], capture_output=True, text=True,
                          env=e.env, check=False)
    assert proc.returncode == 0, proc.stderr
    return path


def test_the_real_helper_inventory_and_register_line(tmp_path):
    """The inventory is #97's own (`set-lane-tree`), the reconciliation is
    the helper's own, and the register line lands in the lane's own log."""
    e, wip = _real_estate(tmp_path, host="eagle")
    mine = _real_tree(e, "mine")
    foreign = e.worktree("other", "feat/other", where="claude", record=False)
    dry = e.sweep(LANE, "--porcelain")
    rows = rows_of(dry.stdout)
    assert rows[str(mine)][0] == "remove", dry.stdout + dry.stderr
    assert rows[str(foreign)][0] == "foreign"
    yes = e.sweep(LANE, "--yes")
    assert yes.returncode == 0, yes.stdout + yes.stderr
    assert not mine.exists() and foreign.is_dir()
    e.git("pull", "-q", "origin", "main", cwd=wip)
    log = (wip / "lanes" / "log" / f"{LANE}.md").read_text()
    noted = [ln for ln in log.splitlines() if ln.startswith("NOTED")]
    assert len(noted) == 1 and str(mine) in noted[0] and "remove" in noted[0], log


def test_the_real_helper_refuses_a_lane_bound_on_another_host(tmp_path):
    e, _wip = _real_estate(tmp_path, host="raven")
    mine = _real_tree(e, "mine")
    dry = e.sweep(LANE, "--porcelain")
    assert dry.returncode == 2, dry.stdout + dry.stderr
    yes = e.sweep(LANE, "--yes", "--live", "none")
    assert yes.returncode == 2 and "raven" in yes.stdout
    assert mine.is_dir()


# ============================================= #170: the --yes data-loss paths

def _rebind_elsewhere(e: Estate, tmp_path: Path) -> None:
    """ANOTHER PLACE binds the lane after this workstation last fetched the
    register: its STARTED line is on origin and not in this clone's ref."""
    other = tmp_path / "other-wip"
    e.git("clone", "-q", tmp_path / "wip.git", other, cwd=tmp_path)
    log = other / "lanes" / "log" / f"{LANE}.md"
    log.write_text(log.read_text() +
                   f"STARTED — lane {LANE}, session {UUID_R}@Raven, 2026-10-05T09:00:00Z, "
                   f"lane:{LANE} → home {SLUG}; dir {e.checkout}; host raven; container none; "
                   "os linux\n")
    e.git("commit", "-q", "-am", "raven binds the lane", cwd=other)
    e.git("push", "-q", "origin", "main", cwd=other)


@pytest.mark.parametrize("case", ["origin-unreachable", "LANES_NO_FETCH-inherited"])
def test_yes_reads_the_register_now_or_refuses(tmp_path, case):
    """#170 A1: `log_sync` answers 0 when it cannot fetch, and an inherited
    LANES_NO_FETCH skips the fetch, so a lane rebound on another host read as
    bound HERE and its tree was removed. --yes fetches the register itself:
    a fetch that fails refuses, and the inherited variable is not obeyed."""
    e, _wip = _real_estate(tmp_path, host="eagle")
    mine = _real_tree(e, "mine")
    _rebind_elsewhere(e, tmp_path)
    env = {}
    if case == "origin-unreachable":
        (tmp_path / "wip.git").rename(tmp_path / "wip-offline.git")
    else:
        env = {"LANES_NO_FETCH": "1"}
    proc = e.sweep(LANE, "--yes", "--live", "none", "--porcelain", env=env)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert mine.is_dir() and (mine / "mine.txt").is_file()
    refused = [ln for ln in proc.stdout.splitlines() if ln.startswith("refused\t")]
    assert refused, proc.stdout
    if case == "origin-unreachable":
        assert "could not be fetched" in refused[0]
    else:
        assert "raven" in refused[0]


def test_a_mirror_style_fetch_refspec_prunes_no_local_branch(estate):
    """#170 item 6: with `remote.origin.fetch = +refs/heads/*:refs/heads/*`,
    `git fetch --prune origin` deletes every local branch origin lacks - before
    anything was classified or rescued. The sweep's fetch pins its refspec."""
    estate.git("config", "--replace-all", "remote.origin.fetch", "+refs/heads/*:refs/heads/*")
    estate.git("checkout", "-q", "-b", "feat/local-only")
    local_only = estate.commit(estate.checkout, "local only", {"lo.txt": "lo\n"})
    # NOTHING CHECKED OUT THAT ORIGIN HAS: git refuses to fetch into a checked
    # out branch, which would have hidden the prune.
    estate.git("checkout", "-q", "--detach", "origin/main")
    estate.git("tag", "local-tag", local_only)
    tree = estate.worktree("det")
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert estate.git("rev-parse", "-q", "--verify", "refs/heads/feat/local-only",
                      check=False) == local_only, "a local-only branch was pruned"
    assert estate.git("rev-parse", "-q", "--verify", "refs/tags/local-tag",
                      check=False) == local_only
    assert not tree.exists()


def test_a_lane_root_that_cannot_be_listed_refuses_the_dry_run(estate):
    """#170 G1: a lane worktree root that cannot be listed was read as an
    absent one, so with an empty inventory the dry run exited 0 and cleared
    #163's gate over trees nobody could see."""
    if os.geteuid() == 0:
        pytest.skip("root lists a mode-000 directory")
    estate.lane_root.mkdir(parents=True)
    (estate.lane_root / "hidden").mkdir()
    estate.lane_root.chmod(0)
    try:
        proc = estate.sweep(LANE, "--dry-run", "--porcelain")
    finally:
        estate.lane_root.chmod(0o755)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert f"the lane's worktree root {estate.lane_root} could not be listed" in proc.stdout


def _git_shim(estate, refuse: str) -> dict:
    """A PATH whose `git` fails `git ... worktree list`, as a repository git
    cannot read would, and runs every other git as itself."""
    shim = estate.root / "shim"
    shim.mkdir(exist_ok=True)
    real_git = shutil.which("git")
    (shim / "git").write_text(
        "#!/bin/sh\nw=0\nfor a in \"$@\"; do\n"
        f"  case \"$a\" in worktree) w=1 ;; {refuse}) [ \"$w\" = 1 ] && "
        "{ echo 'fatal: the shim refuses' >&2; exit 128; } ;; esac\n"
        f"done\nexec \"{real_git}\" \"$@\"\n")
    (shim / "git").chmod(0o755)
    return {"PATH": f"{shim}{os.pathsep}{estate.env['PATH']}"}


def test_registrations_that_cannot_be_read_refuse_the_dry_run(estate):
    """#170 G5: when both `git worktree list` calls failed, the answer was an
    empty list - the same as a repository with no worktrees - so discovery
    could report nothing to retire."""
    tree = estate.worktree("w", "feat/w")
    proc = estate.sweep(LANE, "--dry-run", "--porcelain", env=_git_shim(estate, "list"))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert f"the worktree registrations of {estate.checkout} could not be read" in proc.stdout
    assert tree.is_dir()


def test_a_dependent_anywhere_in_the_estate_makes_a_clone_load_bearing(estate):
    """#170 A11: the estate walk never entered a plain directory inside a
    repository, so a clone there that borrows a lane clone's objects was
    unseen and the clone was deleted from under it."""
    store = estate.lane_root / "store"
    estate.git("clone", "-q", GH_URL, store, cwd=estate.root)
    host = estate.projects / "host"
    estate.git("init", "-q", "-b", "main", host, cwd=estate.root)
    dependent = host / "vendor" / "dep"
    estate.git("clone", "-q", "--shared", store, dependent, cwd=estate.root)
    conf = estate.root / "sweep.conf"
    conf.write_text("foreign_quiet_hours=0\n")
    proc = estate.sweep(LANE, "--include-foreign", "--word", "go", "--yes", "--porcelain",
                        env={"LANE_WORKTREES_CONF": str(conf)})
    rows = rows_of(proc.stdout)
    assert rows[str(store)][0] == "load-bearing", rows
    assert str(dependent) in rows[str(store)][2]
    assert store.is_dir()
    assert estate.git("log", "-1", "--format=%s", cwd=dependent) == "seed"


def test_a_partial_dependents_scan_removes_no_clone(estate):
    """#170 A11: a dependent in a directory the walk could not read is as
    unseen as one it never looked for; a partial scan deletes no clone."""
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 directory")
    store = estate.lane_root / "store"
    estate.git("clone", "-q", GH_URL, store, cwd=estate.root)
    sealed = estate.projects / "sealed"
    (sealed / "inner").mkdir(parents=True)
    sealed.chmod(0)
    conf = estate.root / "sweep.conf"
    conf.write_text("foreign_quiet_hours=0\n")
    try:
        proc = estate.sweep(LANE, "--include-foreign", "--word", "go", "--yes", "--porcelain",
                            env={"LANE_WORKTREES_CONF": str(conf)})
    finally:
        sealed.chmod(0o755)
    rows = rows_of(proc.stdout)
    assert rows[str(store)][0] == "keep", rows
    assert "was partial" in rows[str(store)][2] and str(sealed) in rows[str(store)][2]
    assert store.is_dir()


@pytest.mark.parametrize("where", ["nested-in-the-estate", "recorded-in-the-register"])
def test_another_lanes_claim_is_read_wherever_its_control_root_is(estate, where):
    """#170 G6: other lanes' claims were read only beside THIS lane's control
    root. A lane whose checkout is nested keeps its `.lane-state` beside that
    checkout, so its claim was missed and the tree was not contested."""
    tree = estate.worktree("shared", "feat/shared")
    estate.git("push", "-q", "-u", "origin", "feat/shared", cwd=tree)
    if where == "nested-in-the-estate":
        group = estate.projects / "group"
        other = "repoB-3"
    else:
        group = estate.root / "away" / "group"
        other = "repoC-4"
        estate.register_line(other, (
            f"STARTED — lane {other}, session {OTHER}@Eagle, 2026-10-05T00:00:00Z, "
            f"lane:{other} → home opensoft/repoC; dir {group / 'repoC'}; host eagle; "
            "container none; os linux"))
    # THE OTHER LANE'S CHECKOUT, nested one level down in a plain directory.
    estate.git("init", "-q", "-b", "main", group / "repoC", cwd=estate.root)
    claims = group / ".lane-state" / other / "trees"
    claims.mkdir(parents=True)
    (claims / "c1.yaml").write_text(f"schema: 1\npath: {tree}\n")
    rows = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert rows[str(tree)][0] == "keep", rows[str(tree)]
    assert f"lane {other}'s inventory names it too" in rows[str(tree)][2]
    assert estate.sweep(LANE, "--yes").returncode == 0
    assert tree.is_dir()


@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_an_edit_git_status_hides_keeps_the_tree(estate, flag):
    """#170 A2: a file flagged skip-worktree or assume-unchanged reads as
    clean in `git status` and `git add -A` skips it, so its edit was in no
    rescue and the tree was removed with it."""
    tree = estate.worktree("hidden", "feat/hidden")
    estate.commit(tree, "cfg", {"config.yml": "shared: 1\n"})
    estate.git("push", "-q", "-u", "origin", "feat/hidden", cwd=tree)
    estate.git("update-index", flag, "config.yml", cwd=tree)
    (tree / "config.yml").write_text("shared: 1\nlocal_secret: PRECIOUS\n")
    assert estate.git("status", "--porcelain", cwd=tree) == ""
    dry = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert dry[str(tree)][0] == "keep", dry[str(tree)]
    assert "skip-worktree or assume-unchanged differ" in dry[str(tree)][2]
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (tree / "config.yml").read_text().endswith("PRECIOUS\n")


def test_a_sparse_checkouts_absent_files_are_no_edit(estate):
    """A skip-worktree file that is NOT in the tree (a sparse checkout's) is
    no edit: the tree is still removed."""
    tree = estate.worktree("sparse", "feat/sparse")
    estate.commit(tree, "two", {"keep/a.txt": "a\n", "drop/b.txt": "b\n"})
    estate.git("push", "-q", "-u", "origin", "feat/sparse", cwd=tree)
    estate.git("update-index", "--skip-worktree", "drop/b.txt", cwd=tree)
    (tree / "drop" / "b.txt").unlink()
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not tree.exists()


def test_a_clone_inside_a_venv_keeps_its_tree(estate):
    """#170 A3: `pip install -e git+...` clones into `<venv>/src/<pkg>`, and
    the nested-repository walk passed over venvs before it looked for a
    `.git` - so the dependency's unpushed fix was deleted with the tree."""
    tree = estate.worktree("venvsrc", "feat/venvsrc")
    estate.commit(tree, "ignore venv", {".gitignore": ".env\n__pycache__/\n*.pyc\n.venv/\n"})
    estate.git("push", "-q", "-u", "origin", "feat/venvsrc", cwd=tree)
    venv = tree / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr\n")
    dep = venv / "src" / "somedep"
    estate.git("init", "-q", "-b", "main", dep, cwd=estate.root)
    estate.commit(dep, "my unpushed fix", {"fix.py": "FIX = 1\n"})
    rows = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert rows[str(tree)][0] == "keep", rows[str(tree)]
    assert f"nested inside it at {dep}" in rows[str(tree)][2]
    assert estate.sweep(LANE, "--yes").returncode == 0
    assert (dep / "fix.py").is_file()


def test_a_clones_tag_only_commits_keep_it(estate):
    """#170 item 4: a clone can hold unpublished commits reachable only
    from a local tag; the clone check read branches and the stash only."""
    clone = estate.lane_root / "tagged"
    estate.git("clone", "-q", GH_URL, clone, cwd=estate.root)
    estate.commit(clone, "released locally", {"r.txt": "r\n"})
    estate.git("tag", "-a", "-m", "v1", "v1.0", cwd=clone)
    estate.git("reset", "-q", "--hard", "origin/main", cwd=clone)
    conf = estate.root / "sweep.conf"
    conf.write_text("foreign_quiet_hours=0\n")
    env = {"LANE_WORKTREES_CONF": str(conf)}
    proc = estate.sweep(LANE, "--include-foreign", "--word", "go", "--yes", "--porcelain", env=env)
    rows = rows_of(proc.stdout)
    assert rows[str(clone)][0] == "keep", rows[str(clone)]
    assert "its tag v1.0 holds commits origin lacks" in rows[str(clone)][2]
    assert estate.git("cat-file", "-t", "v1.0", cwd=clone) == "tag"


def _with_submodule(estate, name: str) -> tuple:
    sub_origin = estate.remotes / "sub.git"
    estate.git("init", "-q", "--bare", "-b", "main", sub_origin, cwd=estate.root)
    seed = estate.root / "sub-seed"
    estate.git("clone", "-q", sub_origin, seed, cwd=estate.root)
    estate.commit(seed, "sub", {"s.txt": "s\n"})
    estate.git("push", "-q", "origin", "main", cwd=seed)
    tree = estate.worktree(name, f"feat/{name}", record=False)
    estate.git("submodule", "add", "-q", str(sub_origin), "sub", cwd=tree)
    estate.commit(tree, "add sub")
    estate.git("push", "-q", "-u", "origin", f"feat/{name}", cwd=tree)
    estate.record(tree)
    return tree, tree / "sub"


@pytest.mark.parametrize("what", ["branch", "stash"])
def test_a_submodules_unpublished_branch_or_stash_keeps_its_tree(estate, what):
    """#170 item 5: only a submodule's HEAD was checked, while a worktree's
    submodule keeps its whole repository under `.git/worktrees/<id>/modules/`
    - its branches and stash went with the tree."""
    tree, sub = _with_submodule(estate, "withsub")
    if what == "branch":
        estate.git("checkout", "-q", "-b", "side", cwd=sub)
        estate.commit(sub, "side work", {"side.txt": "x\n"})
        estate.git("checkout", "-q", "--detach", "origin/main", cwd=sub)
    else:
        (sub / "s.txt").write_text("stashed\n")
        estate.git("stash", "-q", cwd=sub)
    assert estate.git("status", "--porcelain", cwd=tree) == ""
    rows = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert rows[str(tree)][0] == "keep", rows[str(tree)]
    want = "its branch side holds commits" if what == "branch" else "has a stash"
    assert f"submodule sub" in rows[str(tree)][2] and want in rows[str(tree)][2]
    assert estate.sweep(LANE, "--yes").returncode == 0
    assert tree.is_dir()


def test_an_ignored_file_beneath_a_build_named_directory_is_archived(estate):
    """#170 A6: an ignored file was dropped unarchived when ANY ancestor was
    named like build output - `docker/build/prod.env` went, `top.env` beside
    it was archived."""
    tree = estate.worktree("deploy", "feat/deploy")
    estate.commit(tree, "compose", {".gitignore": ".env\n*.env\n__pycache__/\n",
                                    "docker/build/Dockerfile": "FROM x\n"})
    estate.git("push", "-q", "-u", "origin", "feat/deploy", cwd=tree)
    (tree / "docker" / "build" / "prod.env").write_text("DB_PASSWORD=PRECIOUS\n")
    (tree / "top.env").write_text("TOKEN=kept\n")
    (tree / "build").mkdir()
    (tree / "build" / "out.bin").write_bytes(b"\0" * 16)
    (tree / ".gitignore").write_text(".env\n*.env\n__pycache__/\n/build/\n")
    estate.git("add", ".gitignore", cwd=tree)
    estate.commit(tree, "ignore build output")
    estate.git("push", "-q", "origin", "feat/deploy", cwd=tree)
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not tree.exists()
    (archive,) = estate.archives()
    with tarfile.open(archive / "deploy-ignored.tar.gz") as tf:
        names = tf.getnames()
    assert "docker/build/prod.env" in names and "top.env" in names, names
    assert not any(n.startswith("build") for n in names), "build output is not archived"


@pytest.mark.parametrize("why", ["open-pr", "another-lanes-trailer", "gh-unreadable"])
def test_unreviewed_commits_never_go_onto_somebody_elses_branch(estate, why):
    """#170 A7: push+remove pushed the lane's local commit onto a teammate's
    OPEN pull request's branch. Where an open PR names the branch, its tip
    carries another lane's trailer, or whether a PR names it cannot be read,
    the commits go to a rescue branch and origin's branch is left alone."""
    tree = estate.worktree("review", "feat/teammate")
    tip = estate.commit(tree, "teammate's work", {"t.txt": "t\n"},
                        lane="repoB-9" if why != "gh-unreadable" else LANE)
    estate.git("push", "-q", "-u", "origin", "feat/teammate", cwd=tree)
    if why == "open-pr":
        estate.pr(77, "feat/teammate", "OPEN", tip)
    mine = estate.commit(tree, "the lane's experiment while reviewing", {"t.txt": "x\n"})
    env = {"LANES_NO_GITHUB": "1"} if why == "gh-unreadable" else {}
    before = estate.remote_heads()["feat/teammate"]
    dry = rows_of(estate.sweep(LANE, "--porcelain", env=env).stdout)
    assert dry[str(tree)][0] == "rescue+remove", dry[str(tree)]
    want = {"open-pr": "PR #77 is open", "another-lanes-trailer": "carries lane repoB-9's work",
            "gh-unreadable": "whether an open pull request names"}[why]
    assert want in dry[str(tree)][2]
    proc = estate.sweep(LANE, "--yes", "--porcelain", env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    heads = estate.remote_heads()
    assert heads["feat/teammate"] == before, "origin's branch moved"
    assert [b for b, s in heads.items() if b.startswith(f"rescue/{LANE}/review-") and s == mine]
    assert not tree.exists()


def test_a_landed_line_never_deletes_a_branch_gh_answers_open(estate):
    """#170 A8: a register LANDED line naming the wrong number (#21 for #20)
    beat gh's live OPEN for #21, and --yes deleted the open PR's remote
    branch - which closes the PR."""
    estate.register_line(LANE, f"LANDED — lane {LANE}, session {ME}@Eagle, "
                               f"2026-10-05T00:00:00Z, {SLUG}#21 → main abc1234")
    tree = estate.worktree("openpr", "feat/open")
    tip = estate.commit(tree, "work under review", {"r.txt": "r\n"})
    estate.git("push", "-q", "-u", "origin", "feat/open", cwd=tree)
    estate.pr(21, "feat/open", "OPEN", tip)
    dry = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert dry[str(tree)][0] == "remove+delete-branch", dry[str(tree)]
    assert "gh still answers PR #21 OPEN" in dry[str(tree)][2]
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert estate.remote_heads().get("feat/open") == tip, "the open PR's branch was deleted"
    assert "remote branch kept (gh still answers PR #21 OPEN)" in rows_of(proc.stdout)[str(tree)][2]


def _bundle_holds(estate, bundle: Path, sha: str) -> bool:
    """`sha` is reachable from a head of `bundle` (fetched into the lane's
    checkout under refs/restored/, where the bundle's prerequisites are)."""
    estate.git("fetch", "-q", str(bundle), "+refs/*:refs/restored/*")
    heads = estate.git("for-each-ref", "--format=%(objectname)", "refs/restored/").split()
    found = bool(heads) and sha in estate.git("rev-list", *heads).split()
    for ref in estate.git("for-each-ref", "--format=%(refname)", "refs/restored/").split():
        estate.git("update-ref", "-d", ref)
    return found


def _ledger(archive: Path) -> list:
    return [ln.split("\t") for ln in (archive / "rescues.tsv").read_text().splitlines()
            if ln and not ln.startswith("#")]


def test_a_pruned_registrations_detached_commit_is_rescued_first(estate):
    """#170 A4: `prune` dropped the only pointer to a detached commit - the
    directory is gone and its registration's HEAD names a commit no branch
    or origin has."""
    tree = estate.worktree("ext", None)
    own = estate.commit(tree, "work on a disk that is offline now", {"x.txt": "PRECIOUS\n"})
    shutil.rmtree(tree)
    dry = rows_of(estate.sweep(LANE, "--porcelain").stdout)
    assert dry[str(tree)][0] == "rescue+prune", dry[str(tree)]
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert str(tree) not in estate.git("worktree", "list", "--porcelain")
    rescued = [b for b, s in estate.remote_heads().items()
               if b.startswith(f"rescue/{LANE}/ext-") and s == own]
    assert rescued, estate.remote_heads()
    (archive,) = estate.archives()
    assert _bundle_holds(estate, next(archive.glob("ext*.bundle")), own)


def test_a_commit_only_the_reflog_names_is_bundled_before_removal(estate):
    """#170 A5: a commit made in a detached tree and then checked out away
    from is in no ref - only the tree's HEAD reflog names it - so the
    removal (which deletes that reflog) lost it. It is bundled first, and
    the ledger records the bundle as its only copy (#170 item 8)."""
    tree = estate.worktree("det", None)
    own = estate.commit(tree, "an experiment", {"exp.txt": "PRECIOUS\n"})
    estate.git("checkout", "-q", "--detach", "origin/main", cwd=tree)
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not tree.exists()
    (archive,) = estate.archives()
    bundles = sorted(archive.glob("det*.bundle"))
    assert bundles and _bundle_holds(estate, bundles[0], own)
    assert [r for r in _ledger(archive) if r[0] == "-" and r[1].startswith("bundle:")
            and r[2] == own], _ledger(archive)


def test_the_self_check_refuses_a_removal_that_would_lose_a_commit(estate):
    """The invariant - nothing deleted that is not first on origin or in a
    bundle - is asked of git once more right before each removal. With the
    reflog bundle switched off (the suite's seam), the commit only the
    reflog names would be lost: the removal is refused, exit 2, a
    DISPOSITION.md line says so, and nothing after it is acted on."""
    first = estate.worktree("a-det", None)
    own = estate.commit(first, "an experiment", {"exp.txt": "PRECIOUS\n"})
    estate.git("checkout", "-q", "--detach", "origin/main", cwd=first)
    second = estate.worktree("b-clean", "feat/b")
    estate.git("push", "-q", "-u", "origin", "feat/b", cwd=second)
    proc = estate.sweep(LANE, "--yes", "--porcelain",
                        env={"LANE_WORKTREES_SEAM_NO_LOSS_BUNDLE": "1"})
    assert proc.returncode == 2, proc.stdout + proc.stderr
    rows = rows_of(proc.stdout)
    assert "REFUSED by the self-check" in rows[str(first)][2]
    assert first.is_dir() and second.is_dir(), "nothing is acted on after the refusal"
    assert own in estate.git("rev-list", "--reflog")
    (archive,) = estate.archives()
    assert "REFUSED by the self-check" in (archive / "DISPOSITION.md").read_text()


@pytest.mark.parametrize("tracked", [True, False])
def test_untracked_files_go_to_the_bundle_never_to_origin(estate, tracked):
    """#170 A9: the WIP rescue committed and PUSHED every untracked,
    un-ignored file - a `gcp-service-account.json` included. Untracked
    files now go to the bundle only (the ledger says it is their only
    copy); tracked changes are still pushed."""
    tree = estate.worktree("svc", "feat/svc")
    estate.commit(tree, "w", {"w.txt": "base\n"})
    estate.git("push", "-q", "-u", "origin", "feat/svc", cwd=tree)
    (tree / "gcp-service-account.json").write_text('{"private_key": "PRECIOUS"}\n')
    if tracked:
        (tree / "w.txt").write_text("changed\n")
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not tree.exists()
    for branch, sha in estate.remote_heads().items():
        files = estate.git("ls-tree", "-r", "--name-only", sha, cwd=estate.origin)
        assert "gcp-service-account.json" not in files.split(), branch
    rescues = [b for b in estate.remote_heads() if b.startswith(f"rescue/{LANE}/svc-")]
    if tracked:
        assert len(rescues) == 1
        assert estate.git("show", f"{rescues[0]}:w.txt", cwd=estate.origin) == "changed"
    else:
        assert rescues == [], "nothing tracked changed and the head is on origin"
    (archive,) = estate.archives()
    held = [r for r in _ledger(archive) if r[0] == "-" and r[1].startswith("bundle:")]
    assert len(held) == 1, _ledger(archive)
    assert _bundle_holds(estate, archive / held[0][1][len("bundle:"):], held[0][2])
    assert estate.git("show", f"{held[0][2]}:gcp-service-account.json") == \
        '{"private_key": "PRECIOUS"}'
    assert "refs/lane-worktrees/" not in estate.git("for-each-ref", "--format=%(refname)")


def test_push_untracked_pushes_them(estate):
    tree = estate.worktree("svc", "feat/svc")
    estate.git("push", "-q", "-u", "origin", "feat/svc", cwd=tree)
    (tree / "notes.md").write_text("meant to be pushed\n")
    proc = estate.sweep(LANE, "--yes", "--push-untracked", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    (rescue,) = [b for b in estate.remote_heads() if b.startswith(f"rescue/{LANE}/svc-")]
    assert estate.git("show", f"{rescue}:notes.md", cwd=estate.origin) == "meant to be pushed"


@pytest.mark.parametrize("lfs", [True, False])
def test_a_push_runs_the_hooks_where_git_lfs_is_configured(estate, lfs):
    """#170 A10: `push --no-verify` skips git-lfs's pre-push upload, so a
    rescued branch reached origin as pointers only - and then the tree, the
    one copy of the objects, was removed. With git-lfs configured the
    hooks run; without it `--no-verify` stays."""
    marker = estate.root / "pre-push.ran"
    hook = estate.checkout / ".git" / "hooks" / "pre-push"
    hook.write_text(f"#!/bin/sh\necho ran >> '{marker}'\nexit 0\n")
    hook.chmod(0o755)
    if lfs:
        for key, value in (("filter.lfs.clean", "cat"), ("filter.lfs.smudge", "cat"),
                           ("filter.lfs.required", "true")):
            estate.git("config", key, value)
    tree = estate.worktree("big", "feat/big")
    estate.commit(tree, "assets", {"a.bin": "binary\n"})
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "feat/big" in estate.remote_heads()
    assert marker.exists() == lfs


def test_an_archive_whose_bundle_is_the_only_copy_never_expires(estate):
    """#170 item 8: an origin-less tree removed through `bundle+remove`
    left no row in rescues.tsv, so `--expire --yes` read the archive as
    holding no rescue and could delete the only copy."""
    solo = estate.projects / "solo"
    estate.git("init", "-q", "-b", "main", solo, cwd=estate.root)
    estate.commit(solo, "solo", {"s.txt": "s\n"})
    lone = estate.lane_root / "lone"
    estate.lane_root.mkdir(parents=True, exist_ok=True)
    estate.git("worktree", "add", "-q", "-b", "feat/lone", lone, "main", cwd=solo)
    tip = estate.commit(lone, "lone", {"l.txt": "l\n"})
    estate.record(lone)
    yes = estate.sweep(LANE, "--bundle", "--yes", "--porcelain")
    assert yes.returncode == 0, yes.stdout + yes.stderr
    (archive,) = estate.archives()
    assert [r for r in _ledger(archive) if r[:2] == ["-", "bundle:lone.bundle"] and r[2] == tip]
    conf = estate.root / "sweep.conf"
    conf.write_text("retention_days=0\n")
    env = {"LANE_WORKTREES_CONF": str(conf)}
    dry = estate.sweep("--expire", "--porcelain", env=env)
    row = [ln.split("\t") for ln in dry.stdout.splitlines() if ln.startswith("archive\t")]
    assert row and row[0][1] == "keep" and "only copy" in row[0][4], dry.stdout
    assert estate.sweep("--expire", "--yes", env=env).returncode == 0
    assert archive.is_dir()


def test_scratch_holding_a_repository_is_kept(estate):
    """#170 item 7: scratch was archived and removed when it had no `.git`
    of its own, so a repository nested in it - a clone with an unpushed
    commit, which no table row names - went with the rmtree."""
    scratch = estate.lane_root / "x-scratch"
    scratch.mkdir(parents=True)
    (scratch / "notes.md").write_text("findings\n")
    inner = scratch / "deps" / "lib"
    estate.git("clone", "-q", GH_URL, inner, cwd=estate.root)
    own = estate.commit(inner, "unpushed", {"i.txt": "i\n"})
    proc = estate.sweep(LANE, "--include-scratch", "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    items = items_of(proc.stdout, "scratch")
    assert items[str(scratch)][0] == "keep", items
    assert f"a repository lies under it ({inner})" in items[str(scratch)][3]
    assert estate.git("rev-parse", "HEAD", cwd=inner) == own
    assert (scratch / "notes.md").is_file()


def test_a_live_path_that_names_no_tree_is_a_usage_error(estate):
    """#170 B4: a misspelt `--live` path was accepted in silence, so the
    writer it was meant to protect was not protected."""
    tree = estate.worktree("w1", "feat/w1")
    estate.git("push", "-q", "-u", "origin", "feat/w1", cwd=tree)
    for live in ((str(estate.lane_root / "w1-typo"),), ("none", str(tree))):
        args = []
        for value in live:
            args += ["--live", value]
        proc = estate.sweep(LANE, "--yes", *args)
        assert proc.returncode == 64, (live, proc.stdout, proc.stderr)
        assert tree.is_dir()
    assert estate.sweep(LANE, "--yes", "--live", str(tree)).returncode == 0
    assert tree.is_dir(), "the tree --live names is a live writer's"


def test_trees_this_session_recorded_want_the_writer_count(estate):
    """#170 B5: a tree this session recorded skips the transcript check (it
    is this session's), and --live was demanded only when the holder read
    as this session - so with the holder read as none, --yes removed the
    trees this session's own writers could be standing in."""
    tree = estate.worktree("mine", "feat/mine", record=False)
    estate.git("push", "-q", "-u", "origin", "feat/mine", cwd=tree)
    estate.record(tree, writer=ME)
    assert estate.holder == "none"
    refused = estate.sweep(LANE, "--yes", "--porcelain")
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "this session recorded 1 of lane" in refused.stdout
    assert tree.is_dir()
    assert estate.sweep(LANE, "--yes", "--live", "none").returncode == 0
    assert not tree.exists()


def test_the_first_register_line_refused_stops_the_sweep(estate):
    """#170 B6: removals went on after a NOTED line failed, so acts piled
    up that the register never recorded."""
    first = estate.worktree("a-one", "feat/one")
    estate.git("push", "-q", "-u", "origin", "feat/one", cwd=first)
    second = estate.worktree("b-two", "feat/two")
    estate.git("push", "-q", "-u", "origin", "feat/two", cwd=second)
    estate.log_rc = 1
    proc = estate.sweep(LANE, "--yes", "--porcelain")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    rows = rows_of(proc.stdout)
    assert not first.exists() and second.is_dir()
    assert "the register refused a line" in rows[str(second)][2]
    assert len(estate.notes()) == 1


def test_a_lane_owned_open_pr_branch_origin_lacks_is_still_counted(estate):
    """#170 G2: every OPEN PR's branch was left out of the retire count, so
    a lane-owned branch holding commits origin lacks let `--branches
    --dry-run --porcelain` exit 0 and clear #163's gate. The delete
    protection stays; the count does not hide it."""
    estate.git("checkout", "-q", "-b", "feat/g2", "origin/main")
    tip = estate.commit(estate.checkout, "unpushed", {"g2.txt": "g\n"})
    estate.git("checkout", "-q", "main")
    estate.pr(61, "feat/g2", "OPEN", tip)
    proc = estate.sweep(LANE, "--branches", "--dry-run", "--porcelain")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    items = items_of(proc.stdout, "branch")
    assert items["feat/g2"][:2] == ("keep", "retire"), items
    yes = estate.sweep(LANE, "--branches", "--yes")
    assert yes.returncode == 0, yes.stdout + yes.stderr
    assert estate.git("rev-parse", "feat/g2") == tip, "an open PR's branch is never touched"


def test_a_branch_published_under_its_own_name_is_not_unfinished(estate):
    """#170 G7: a branch made from origin/main tracks main, so its upstream
    read 'ahead' and `--branches` exited 3 although origin held every
    commit under the branch's own name."""
    estate.git("checkout", "-q", "-b", "feat/g7", "origin/main")
    estate.commit(estate.checkout, "published", {"g7.txt": "g\n"})
    estate.git("push", "-q", "origin", "feat/g7")
    assert estate.git("rev-parse", "--abbrev-ref", "feat/g7@{u}") == "origin/main"
    estate.git("checkout", "-q", "main")
    proc = estate.sweep(LANE, "--branches", "--dry-run", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "feat/g7" not in items_of(proc.stdout, "branch")


def _age(path: Path, seconds: float) -> None:
    when = time.time() - seconds
    for p in sorted(path.rglob("*"), reverse=True) + [path]:
        os.utime(p, (when, when), follow_symlinks=False)


def test_a_tmp_dir_with_no_mark_of_a_suite_is_listed_until_it_is_old(estate):
    """#170 item 1 (the coordinator's default): an hour-old `tmp.*` with
    nobody in it was removed with no proof a suite made it - a person's
    `mktemp -d` checkout or saved scratch included. It is removed now only
    with a suite's mark whose pid is gone, or untouched for aging_days
    (14); any other is listed and left."""
    base = estate.sandboxes
    unmarked, ancient, marked, layout = (base / n for n in (
        "tmp.person01", "tmp.ancient02", "tmp.suite03", "tmp.layout04"))
    for d in (unmarked, ancient, marked, layout):
        d.mkdir()
        (d / "f").write_text("x")
    (marked / ".lock").write_text("999999\n")
    (layout / "basetemp").mkdir()
    (layout / "tmp").mkdir()
    for d in (unmarked, marked, layout):
        _age(d, 7200)
    _age(ancient, 20 * 86400)
    proc = estate.sweep(LANE, "--include-sandboxes", "--yes", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    rows = items_of(proc.stdout, "sandbox")
    assert rows[str(unmarked)][0] == "list" and "no mark of a test suite" in rows[str(unmarked)][3]
    assert unmarked.is_dir() and (unmarked / "f").is_file()
    for gone in (ancient, marked, layout):
        assert rows[str(gone)][0] == "remove" and not gone.exists(), rows[str(gone)]


def test_an_unreadable_process_of_this_account_keeps_the_tree_it_names(estate):
    """#170 item 2 (the coordinator's default): a same-account process whose
    `/proc` entries cannot be read (not dumpable) was read as absent, and
    its tree was removed under it. It is placed by its command line and its
    parent's directory; a tree it is placed in is kept."""
    if not os.path.isdir("/proc/self/fd") or os.geteuid() == 0:
        pytest.skip("needs /proc, and an account that cannot read a non-dumpable process")
    tree = estate.worktree("held", "feat/held")
    estate.git("push", "-q", "-u", "origin", "feat/held", cwd=tree)
    ready = estate.root / "ready"
    code = ("import ctypes, sys, time; ctypes.CDLL(None).prctl(4, 0, 0, 0, 0); "
            "open(sys.argv[1], 'w').close(); time.sleep(300)")
    child = subprocess.Popen([sys.executable, "-c", code, str(ready), str(tree)], cwd=str(tree))
    try:
        deadline = time.time() + 20
        while not ready.exists() and time.time() < deadline:
            time.sleep(0.05)
        try:
            os.readlink(f"/proc/{child.pid}/cwd")
            pytest.skip("this kernel lets the owner read a non-dumpable process")
        except PermissionError:
            pass
        proc = estate.sweep(LANE, "--yes", "--porcelain")
    finally:
        child.kill()
        child.wait()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert tree.is_dir(), "the tree an unreadable process stands in was removed"
    row = rows_of(proc.stdout)[str(tree)]
    assert row[0] == "keep" and f"process {child.pid}" in row[2] and "could not be read" in row[2]


def test_an_inventory_row_with_no_id_refuses_the_dry_run(estate):
    """#170 G9: a `lane-trees` row with no id was skipped in silence, so a
    tree it named outside the scanned roots went unseen and the dry run
    exited 0, clearing #163's gate."""
    elsewhere = estate.root / "elsewhere" / "tree"
    estate.inventory.append(US.join(["", str(elsewhere), "feat/x", "0" * 40, "none", "0", "0",
                                     WRITER, "2026-10-05T00:00:00Z", str(estate.checkout),
                                     "1", "op-1", "1"]))
    proc = estate.sweep(LANE, "--dry-run", "--porcelain")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "inventory record ? is unreadable" in proc.stdout


def test_a_dot_git_file_that_is_no_pointer_leaves_the_scan_whole(estate):
    """uv keeps an EMPTY `.git` file in its cache to stop git looking upward.
    It is no repository, and no reason to call the dependents scan partial
    (measured on Eagle: two of them kept every clone and scratch)."""
    marker = estate.projects / "tool-cache" / "uv" / "sdists-v9"
    marker.mkdir(parents=True)
    (marker / ".git").write_text("")
    store = estate.lane_root / "store"
    estate.git("clone", "-q", GH_URL, store, cwd=estate.root)
    conf = estate.root / "sweep.conf"
    conf.write_text("foreign_quiet_hours=0\n")
    proc = estate.sweep(LANE, "--include-foreign", "--word", "go", "--yes", "--porcelain",
                        env={"LANE_WORKTREES_CONF": str(conf)})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not store.exists(), rows_of(proc.stdout)[str(store)]


# ===================================================== #174, Copilot round 1

def _foreign_clone(estate, name: str) -> tuple:
    """A standalone clone under the lane's root, published, and the
    environment that lets `--include-foreign --word go` act on it at once."""
    clone = estate.lane_root / name
    estate.lane_root.mkdir(parents=True, exist_ok=True)
    estate.git("clone", "-q", GH_URL, clone, cwd=estate.root)
    conf = estate.root / "sweep.conf"
    conf.write_text("foreign_quiet_hours=0\n")
    return clone, {"LANE_WORKTREES_CONF": str(conf)}


def test_a_clones_reflogs_that_cannot_be_listed_remove_nothing(estate):
    """#174 Copilot round 1: the clone's loss plan walked `.git/logs` with
    `os.walk`, which passes over a directory it cannot list in silence - so
    a commit only `logs/refs/heads/<b>` named was in no plan, no bundle took
    it, the self-check asked the same blind question, and the clone was
    deleted with it. A reflog directory that cannot be listed is unknown."""
    if os.geteuid() == 0:
        pytest.skip("root lists a mode-000 directory")
    clone, env = _foreign_clone(estate, "blind")
    main = estate.git("rev-parse", "HEAD", cwd=clone)
    tree = estate.git("rev-parse", "HEAD^{tree}", cwd=clone)
    own = estate.git("commit-tree", tree, "-p", main, "-m", "an experiment", cwd=clone)
    estate.git("update-ref", "-m", "experiment", "refs/heads/exp", own, cwd=clone)
    estate.git("update-ref", "-m", "back", "refs/heads/exp", main, cwd=clone)
    assert own in estate.git("rev-list", "--reflog", cwd=clone).split()
    sealed = clone / ".git" / "logs" / "refs" / "heads"
    sealed.chmod(0)
    try:
        proc = estate.sweep(LANE, "--include-foreign", "--word", "go", "--yes", "--porcelain",
                            env=env)
    finally:
        sealed.chmod(0o755)
    assert clone.is_dir(), "a clone whose reflogs could not be read was removed"
    assert estate.git("cat-file", "-t", own, cwd=clone) == "commit"
    row = rows_of(proc.stdout)[str(clone)]
    assert "could not be listed" in row[2] and "left in place" in row[2], row
    assert proc.returncode == 1, proc.stdout + proc.stderr
