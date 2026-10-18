# SPDX-License-Identifier: Apache-2.0
"""T018 (opensoft/openRepoTools#186): the lane tooling sees a TRIAD's trees.

A lane's checkout is an ASSEMBLY when its own `project.yaml` declares a leg
other than itself - the standard's rule, read by `lanes-edit.sh project-legs`
with `lane-start`'s rung-5 grammar. Its legs (`spec/`, `code/`) are submodules
and its feature trees are worktrees of the LEGS' repositories, under
`<assembly>/worktrees/<feature>/{spec,code}` - so before this every lane tool
was blind to them (docs/triad-lane-tooling-analysis.md §4.4).

TWO THINGS ARE HELD HERE, and the second is the condition of the first:

  * on an assembly built from openRepoShape's OWN template bytes at the
    pinned commit (`upstream/openRepoShape/templates/assembly-root/`), with
    every leg a real git repository behind a bare local origin and a fake `gh`
    that exits 1, the sweep, `lane-end`'s gate (and, in later commits, the
    handoff poll, the daily report and `add`) see the legs, their worktrees and
    the paired feature trees;
  * on a SINGLE REPOSITORY - no `project.yaml`, a submodule that is no leg, and
    a `project.yaml` naming no leg but itself - every output of every touched
    command is byte for byte what the tools at `c45a452` printed. The "before"
    is STORED (`tests/fixtures/t018/single-repository.golden`), generated ONCE
    from `c45a452`'s own tools by this module's `--capture` and committed: CI
    checks out at depth 1, where `c45a452` is not there to run. It is
    normalised for what no two runs share - the bench's path, UTC stamps,
    hashes, ages and byte sizes - and for nothing else.

NOTHING REAL IS TOUCHED: every repository, origin, register, `$HOME` and
state directory is under `tmp_path`, and the network is never reached.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import NEEDS_UPSTREAM, REPO, UPSTREAM, WINDOWS_SKIP  # noqa: E402

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="the lane tools are bash and Python over git")]

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "t018" / "single-repository.golden"
#: The assembly is built from the pinned openRepoShape's own template bytes,
#: so every assembly case wears conftest's `NEEDS_UPSTREAM`: standalone it
#: skips where the submodule is not checked out, and composed it FAILS.
TEMPLATE = UPSTREAM / "templates" / "assembly-root"

UUID = "18018018-1111-4180-8180-180180180001"
#: Every command the bench installs beside each other, as `--install` does.
TOOLS = ("lanes-edit.sh", "lane-worktrees", "lane-end", "lane-handoff", "lane-start",
         "repos.tsv")
GATE = ("--branches", "--include-scratch", "--include-caches")
US = "\x1f"

FAKE_GH = "#!/bin/sh\nprintf 'fake gh: no GitHub here (%s)\\n' \"$*\" >&2\nexit 1\n"
FAKE_TMUX = "#!/bin/sh\nexit 1\n"
FAKE_STATUS = ("#!/bin/sh\nprintf 'status --all: reading every estate:\\n\\n"
               "=== status repoS ===\\n    - a fixed finding\\n'\nexit 1\n")


class Bench:
    """One workstation under `root`: a workspace repository with a register,
    `$HOME`, the projects directory, bare origins, fakes, and the tools under
    test copied side by side into `root/bin`."""

    def __init__(self, root: Path, tools: Path):
        self.root = root
        self.home = root / "home"
        self.projects = self.home / "projects"
        self.remotes = root / "remotes"
        self.fake = root / "fakebin"
        self.bin = root / "bin"
        self.wip = self.projects / "wip"
        for d in (self.home, self.projects, self.remotes, self.fake, self.bin, root / "tmp",
                  root / "sandboxes", self.home / ".agents", self.home / ".claude" / "sessions"):
            d.mkdir(parents=True, exist_ok=True)
        for name in TOOLS:
            shutil.copy2(tools / name, self.bin / name)
            (self.bin / name).chmod(0o755)
        for name, text in (("gh", FAKE_GH), ("tmux", FAKE_TMUX), ("status", FAKE_STATUS)):
            (self.fake / name).write_text(text)
            (self.fake / name).chmod(0o755)
        (self.home / ".gitconfig").write_text(
            "[user]\n\tname = t018\n\temail = t018@example.invalid\n"
            "[init]\n\tdefaultBranch = main\n[protocol \"file\"]\n\tallow = always\n"
            "[advice]\n\tdetachedHead = false\n")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("LANES_", "LANE_", "CLAUDE_", "WORKBENCHES_", "TMUX", "XDG_",
                                    "PROJECTS_", "GH_", "GIT_", "FAKE_", "OPENREPOTOOLS_",
                                    "PYTEST_"))
               and k not in ("AGENT_PROTOCOL_ROOT",)}
        system_path = os.pathsep.join(p for p in env.get("PATH", "/usr/bin:/bin").split(os.pathsep)
                                      if p and not any(os.path.exists(os.path.join(p, n))
                                                       for n in TOOLS + ("lanes-index",)))
        env.update(
            HOME=str(self.home), TMPDIR=str(root / "tmp"),
            PATH=os.pathsep.join([str(self.fake), str(self.bin), system_path]),
            AGENT_PROTOCOL_ROOT=str(self.home / ".agents"),
            XDG_STATE_HOME=str(self.home / ".local" / "state"),
            XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / ".cache"),
            PROJECTS_ROOT=str(self.projects), LANES_WORKSTATION="Eagle", LANES_HOST="eagle",
            LANES_OS="linux", LANES_CONTAINER="none", LANES_IN_CONTAINER="0",
            LANES_NO_GITHUB="1", LANES_INDEX="off", LANE_WORKTREES_REPORT="off",
            LANE_WORKTREES_SANDBOX_ROOTS=str(root / "sandboxes"),
            LANE_WORKTREES_STATUS=str(self.fake / "status"),
            CLAUDE_CONFIG_DIR=str(self.home / ".claude"), LANES_SESSION=UUID,
            GIT_CONFIG_NOSYSTEM="1", OPENREPOTOOLS_BIN_DIR=str(self.bin), LC_ALL="C")
        self.env = env
        self._seed_workspace()

    # ------------------------------------------------------------ plumbing
    def run(self, *argv, cwd=None, env=None, timeout=300) -> subprocess.CompletedProcess:
        child = dict(self.env)
        child.update(env or {})
        return subprocess.run([str(a) for a in argv], cwd=str(cwd or self.root), env=child,
                              capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)

    def tool(self, name, *args, cwd=None, env=None) -> subprocess.CompletedProcess:
        return self.run(self.bin / name, *args, cwd=cwd, env=env)

    def git(self, *args, cwd=None) -> str:
        proc = self.run("git", *args, cwd=cwd)
        assert proc.returncode == 0, f"git {' '.join(map(str, args))}: {proc.stderr}"
        return proc.stdout.strip()

    def commit(self, cwd: Path, message: str, files: dict | None = None,
               lane: str | None = None) -> str:
        for rel, text in (files or {}).items():
            path = Path(cwd) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git("add", "-A", cwd=cwd)
        self.git("commit", "-q", "--allow-empty", "-m",
                 f"{message}\n\nLane: {lane}\n" if lane else message, cwd=cwd)
        return self.git("rev-parse", "HEAD", cwd=cwd)

    def origin(self, name: str) -> Path:
        bare = self.remotes / f"{name}.git"
        self.git("init", "-q", "--bare", "-b", "main", bare)
        return bare

    def seeded(self, name: str, files: dict) -> Path:
        """A bare origin holding one commit of `files`."""
        bare = self.origin(name)
        work = self.root / "seed" / name
        self.git("clone", "-q", bare, work)
        self.commit(work, f"{name}: seed", files)
        self.git("push", "-q", "origin", "main", cwd=work)
        return bare

    # ------------------------------------------------------------ register
    def _seed_workspace(self) -> None:
        bare = self.origin("wip")
        self.git("clone", "-q", bare, self.wip)
        (self.wip / "lanes" / "log").mkdir(parents=True)
        (self.wip / "handoffs").mkdir()
        (self.wip / "lanes" / "LANES.md").write_text(
            "# LANES.md\n\n| lane | session id | workstation / env / user | started (UTC) "
            "| objects owned | handoff path | state |\n|---|---|---|---|---|---|---|\n")
        self.git("add", "-A", cwd=self.wip)
        self.git("commit", "-q", "-m", "seed", cwd=self.wip)
        self.git("push", "-q", "origin", "main", cwd=self.wip)
        # AMENDMENT 23 S5: W, the readers' copy that workspace.yaml names, takes
        # no write, and a write that resolves by default goes through the lane's
        # own checkout beside it. These cases hold c45a452's single-repository
        # outputs, so the tools write through `self.wip` by the explicit seam
        # (ort186 Q9): `LANES_REPO`, and `LANES_FILE`, which lane-start,
        # lane-end and lane-handoff derive from W whenever it is empty. W is a
        # VIEW of `self.wip` outside the projects root — its `.git` names
        # `self.wip`'s, and its `lanes` and `handoffs` are links into it —
        # because `lane-worktrees` reads W directly and a separate clone would
        # stay behind every write these cases make.
        self.ws = self.root / "ro" / "wip"
        self.ws.mkdir(parents=True)
        (self.ws / ".git").write_text(f"gitdir: {os.path.realpath(self.wip / '.git')}\n")
        for name in ("lanes", "handoffs"):
            (self.ws / name).symlink_to(self.wip / name)
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {bare}\npath: {self.ws}\n")
        self.env["LANES_REPO"] = str(self.wip)
        self.env["LANES_FILE"] = str(self.wip / "lanes" / "LANES.md")

    def lanes(self, home: str, checkout: Path, *names: str) -> None:
        """A register row, a handoff and a STARTED line naming `checkout` for
        each lane, pushed in one commit; and a RUNNING #97 snapshot."""
        reg = self.wip / "lanes" / "LANES.md"
        text = reg.read_text()
        for lane in names:
            text += (f"| `{lane}` | harness `{UUID}` | Eagle / test / brett | 2026-10-08T00:00Z "
                     f"| none | handoffs/{lane}.md | LIVE · 2026-10-08T00:00:00Z · working |\n")
            (self.wip / "handoffs" / f"{lane}.md").write_text(f"# handoff {lane}\n\nwork.\n")
            (self.wip / "lanes" / "log" / f"{lane}.md").write_text(
                f"STARTED — lane {lane}, session {UUID}@Eagle, 2026-10-08T00:00:00Z, lane:{lane} "
                f"→ home {home}; dir {checkout}; host eagle; container none; os linux\n")
        reg.write_text(text)
        self.git("add", "-A", cwd=self.wip)
        self.git("commit", "-q", "-m", "lanes", cwd=self.wip)
        self.git("push", "-q", "origin", "main", cwd=self.wip)
        for lane in names:
            proc = self.tool("lanes-edit.sh", "set-lane-state", lane, "RUNNING", "--expect", "none",
                             "--operation", "op-seed", "--owner", UUID)
            assert proc.returncode == 0, proc.stderr

    def row(self, lane: str) -> str:
        return next(line for line in (self.wip / "lanes" / "LANES.md").read_text().splitlines()
                    if line.startswith(f"| `{lane}`"))

    def last_log(self, lane: str) -> str:
        return (self.wip / "lanes" / "log" / f"{lane}.md").read_text().splitlines()[-1]

    def sweep(self, lane: str, *args) -> subprocess.CompletedProcess:
        return self.tool("lane-worktrees", "sweep", lane, *args)


# ================================================================ normalising

_RULES = (
    (re.compile(r"\bc\d{3,}-[A-Za-z0-9._-]*"), "<TREE-ID>"),
    (re.compile(r"op-\d{8}T\d{6}Z-\d+-\d+"), "<OPERATION>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}"), "<ISO>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z"), "<UTC>"),
    (re.compile(r"\d{8}T\d{6}Z"), "<STAMP>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}"), "<DATE>"),
    (re.compile(r"\b[0-9a-f]{7,40}\b"), "<HEX>"),
    (re.compile(r"\b\d+ d\b"), "<N> d"),
    (re.compile(r"active \d+ min ago"), "active <N> min ago"),
    (re.compile(r"\b\d+(\.\d+)? (B|KB|MB|GB)\b"), "<SIZE>"),
    (re.compile(r"\(\d+ bytes\)"), "(<N> bytes)"),
)


_PROC_NOTE = re.compile(r"^  note: \d+ process\(es\) of this account could not be read in /proc ")


def normalise(text: str, bench: Bench) -> str:
    """What no two runs share, and nothing else: the bench's own path and its
    `$HOME` (both spellings), tree ids (a checksum of that path), operation ids, stamps,
    hashes, ages and byte sizes - and a porcelain row's byte count."""
    # `$HOME` FIRST, and as a word of its own: `tests/test_repo_hygiene.py`
    # rightly refuses a committed `/home/<user>/` path, and the bench's home
    # sits under its root. W GOES FIRST (Amendment 23 S5): the bench's W is a
    # view outside the projects root, and a line that names W reads as the
    # workspace checkout's path did before W stopped taking writes.
    for place, word in ((bench.ws, "<HOME>/projects/wip"), (bench.home, "<HOME>"),
                        (bench.root, "<ROOT>")):
        for spelling in sorted({str(place), os.path.realpath(place)}, key=len, reverse=True):
            text = text.replace(spelling, word)
    for rx, sub in _RULES:
        text = rx.sub(sub, text)
    out = []
    for line in text.split("\n"):
        # A HOST FACT, NOT THE TOOL'S: how many of this account's processes
        # `/proc` would not show the sweep is whatever else runs beside it.
        if _PROC_NOTE.match(line):
            continue
        cols = line.split("\t")
        if cols[0] in ("scratch", "cache", "sandbox") and len(cols) > 5:
            cols[5] = "<N>"
        out.append("\t".join(cols))
    return "\n".join(out)


def shown(proc: subprocess.CompletedProcess, bench: Bench) -> str:
    return normalise(f"exit {proc.returncode}\n--- stdout\n{proc.stdout}--- stderr\n{proc.stderr}",
                     bench)


# =================================================== the single repository

def single_repository(bench: Bench) -> list:
    """THE SCENARIO WHOSE OUTPUTS MAY NOT MOVE: one repository with a
    submodule (as openRepoTools has `upstream/openRepoShape`) and a second with
    a `project.yaml` naming no leg but itself, every kind of row the touched
    commands print, and each command's output in the order it ran."""
    b = bench
    out = []
    dep = b.seeded("dep", {"d.txt": "a dependency\n"})
    b.origin("repoS")
    s = b.projects / "repoS"
    b.git("clone", "-q", b.remotes / "repoS.git", s)
    b.commit(s, "seed", {"README.md": "S\n", ".gitignore": ".env\n__pycache__/\n"})
    b.git("submodule", "add", "-q", dep, "vendor/dep", cwd=s)
    b.commit(s, "a submodule that is no leg")
    b.git("push", "-q", "origin", "main", cwd=s)
    b.lanes("opensoft/repoS", s, "repoS-1", "repoS-2")

    # add: the dry run, then the act; work in the tree it made.
    out.append(("add --dry-run", shown(b.tool("lane-worktrees", "add", "repoS-1", "inv",
                                              "--dry-run"), b)))
    out.append(("add", shown(b.tool("lane-worktrees", "add", "repoS-1", "inv"), b)))
    inv = b.projects / ".lane-worktrees" / "repoS-1" / "inv"
    b.commit(inv, "inv work", {"i.txt": "i\n"}, lane="repoS-1")
    (inv / "i.txt").write_text("changed\n")
    (inv / ".env").write_text("SECRET=1\n")
    (inv / "__pycache__").mkdir()
    (inv / "__pycache__" / "x.pyc").write_bytes(b"\0" * 64)
    # a tree under .claude/worktrees carrying the lane's trailer, unrecorded
    tr = s / ".claude" / "worktrees" / "tr"
    b.git("worktree", "add", "-q", "-b", "tr", tr, "origin/main", cwd=s)
    b.commit(tr, "trailer work", {"t.txt": "t\n"}, lane="repoS-1")
    # a FOREIGN registration elsewhere, another lane's
    b.git("worktree", "add", "-q", "-b", "elsewhere", b.projects / "elsewhere", "origin/main", cwd=s)
    b.commit(b.projects / "elsewhere", "theirs", {"e.txt": "e\n"}, lane="repoS-9")
    # scratch, and a branch of the lane's own with no tree
    (b.projects / ".lane-worktrees" / "repoS-1" / "notes-scratch").mkdir()
    (b.projects / ".lane-worktrees" / "repoS-1" / "notes-scratch" / "n.md").write_text("n\n")
    tmp = b.root / "tmp-branch"
    b.git("worktree", "add", "-q", "-b", "old-work", tmp, "origin/main", cwd=s)
    b.commit(tmp, "old work", {"o.txt": "o\n"}, lane="repoS-1")
    b.git("worktree", "remove", tmp, cwd=s)

    out.append(("sweep porcelain", shown(b.sweep("repoS-1", *GATE, "--dry-run", "--porcelain"), b)))
    out.append(("sweep table", shown(b.sweep("repoS-1", *GATE, "--dry-run"), b)))
    out.append(("lane-reconcile", shown(b.tool("lanes-edit.sh", "lane-reconcile", "repoS-1"), b)))
    out.append(("lane-end refused", shown(b.tool("lane-end", "repoS-1"), b)))
    out.append(("lane-end refused: row and log", normalise(
        b.row("repoS-1") + "\n" + b.last_log("repoS-1"), b)))

    # a repository whose project.yaml names no leg but itself
    p = b.projects / "repoP"
    b.origin("repoP")
    b.git("clone", "-q", b.remotes / "repoP.git", p)
    b.commit(p, "seed", {"project.yaml": (
        "schema_version: 1\nkind: project-manifest\nid: repoP\nlegs:\n"
        "  - role: assembly\n    repository: opensoft/repoP\n    path: \".\"\n")})
    b.git("push", "-q", "origin", "main", cwd=p)
    b.lanes("opensoft/repoP", p, "repoP-1")
    pt = b.projects / ".lane-worktrees" / "repoP-1" / "w"
    out.append(("add (manifest, no leg)", shown(b.tool("lane-worktrees", "add", "repoP-1", "w"), b)))
    b.commit(pt, "p work", {"p.txt": "p\n"}, lane="repoP-1")
    out.append(("sweep porcelain (manifest, no leg)",
                shown(b.sweep("repoP-1", *GATE, "--dry-run", "--porcelain"), b)))

    out.append(("lane-handoff", shown(b.tool("lane-handoff", "--lane", "repoS-1", "--transcript",
                                             "none", "--agent", "claude", "t018 handoff",
                                             cwd=s), b)))
    handoff = (b.wip / "handoffs" / "repoS-1.md").read_text()
    out.append(("lane-handoff: top block", normalise(handoff.split("\n---\n", 1)[0], b)))
    # ONE SIDECAR PER TREE, LISTED IN THE ORDER OF THEIR FILE NAMES - a
    # checksum of each tree's path, so of the bench's own path: sorted here.
    trees = b.tool("lanes-edit.sh", "lane-trees", "repoS-1")
    trees.stdout = "".join(sorted(trees.stdout.splitlines(keepends=True),
                                  key=lambda line: normalise(line, b)))
    out.append(("lane-handoff: inventory", shown(trees, b)))
    out.append(("sweep porcelain after the handoff",
                shown(b.sweep("repoS-1", *GATE, "--dry-run", "--porcelain"), b)))
    out.append(("lane-end passes", shown(b.tool("lane-end", "repoS-2"), b)))
    out.append(("lane-end passes: row and log", normalise(
        b.row("repoS-2") + "\n" + b.last_log("repoS-2"), b)))
    out.append(("report", shown(b.tool("lane-worktrees", "sweep", "--all", "--dry-run", "--report",
                                       "--estate", b.projects), b)))
    return out


def render_golden(sections: list) -> str:
    return "".join(f"=== {key} ===\n{text}\n" for key, text in sections)


def parse_golden(text: str) -> list:
    out = []
    for chunk in re.split(r"(?m)^=== (.+) ===\n", text)[1:]:
        out.append(chunk)
    return [(out[i], out[i + 1][:-1] if out[i + 1].endswith("\n") else out[i + 1])
            for i in range(0, len(out), 2)]


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="the golden was captured on Linux, where liveness is read in /proc; "
                           "macOS reads it with lsof, a host fact this proof is not about")
def test_t018_single_repository_outputs_are_c45a452s_byte_for_byte(tmp_path):
    """THE INVARIANT. Every output of every touched command on a single
    repository - a submodule that is no leg, and a `project.yaml` naming no leg
    but itself, included - equals what `c45a452`'s tools printed, stored in the
    golden file this module's `--capture` wrote from them."""
    assert GOLDEN.is_file(), f"{GOLDEN} is missing; it is generated from c45a452's tools"
    want = parse_golden(GOLDEN.read_text(encoding="utf-8"))
    got = single_repository(Bench(tmp_path / "bench", REPO))
    assert [k for k, _ in got] == [k for k, _ in want]
    for (key, have), (_k, gold) in zip(got, want):
        if have != gold:
            diff = "\n".join(difflib.unified_diff(gold.splitlines(), have.splitlines(),
                                                  f"c45a452: {key}", f"now: {key}", lineterm=""))
            raise AssertionError(f"the single-repository output of '{key}' moved:\n{diff}")


# ================================================================ the assembly

def build_assembly(b: Bench, name: str = "triad") -> dict:
    """An assembly made of openRepoShape's own template bytes at the pinned
    commit: every file of `templates/assembly-root/` copied, `project.yaml`'s
    placeholders filled, the legs mounted as submodules from bare local
    origins, and a dependency nested in the code leg (`upstream/dep`), as
    openRepoTools' code leg will carry `upstream/openRepoShape`."""
    dep = b.seeded(f"{name}-dep", {"dep.txt": "a nested dependency\n"})
    spec = b.seeded(f"{name}-spec", {"spec.md": "the spec leg\n"})
    code_bare = b.origin(f"{name}-code")
    seed = b.root / "seed" / f"{name}-code"
    b.git("clone", "-q", code_bare, seed)
    b.commit(seed, "code: seed", {"tool.sh": "#!/bin/sh\n"})
    b.git("submodule", "add", "-q", dep, "upstream/dep", cwd=seed)
    b.commit(seed, "code: the nested dependency")
    b.git("push", "-q", "origin", "main", cwd=seed)
    b.origin(name)
    a = b.projects / name
    b.git("clone", "-q", b.remotes / f"{name}.git", a)
    for src in TEMPLATE.rglob("*"):
        rel = src.relative_to(TEMPLATE)
        if src.is_dir():
            (a / rel).mkdir(parents=True, exist_ok=True)
        else:
            (a / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, a / rel)
    manifest = (TEMPLATE / "project.yaml").read_text(encoding="utf-8")
    fill = {"ASSEMBLY_REPOSITORY": f"opensoft/{name}", "SPEC_REPOSITORY": f"opensoft/{name}-spec",
            "CODE_REPOSITORY": f"opensoft/{name}-code", "SPEC_PATH": "spec", "CODE_PATH": "code"}
    lines = []
    for line in manifest.splitlines():
        if re.fullmatch(r"\{\{[A-Z_]+_NAMING\}\}", line.strip()):
            continue
        lines.append(re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: fill.get(m.group(1), m.group(0)), line))
    (a / "project.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    b.commit(a, "the assembly, from the template")
    b.git("submodule", "add", "-q", spec, "spec", cwd=a)
    b.git("submodule", "add", "-q", code_bare, "code", cwd=a)
    b.commit(a, "the legs")
    b.git("push", "-q", "origin", "main", cwd=a)
    b.git("submodule", "update", "-q", "--init", "--recursive", cwd=a)
    return {"assembly": a, "code": a / "code", "spec": a / "spec",
            "dep": a / "code" / "upstream" / "dep"}


def porcelain_rows(out: str, kind: str) -> dict:
    rows = {}
    for line in out.splitlines():
        cols = line.split("\t")
        if cols[0] == kind and len(cols) > 6:
            rows[cols[3]] = {"disposition": cols[1], "retire": cols[2], "branch": cols[4],
                             "head": cols[5], "why": cols[6]}
    return rows


@pytest.fixture
def triad(tmp_path):
    b = Bench(tmp_path / "bench", REPO)
    t = build_assembly(b)
    b.lanes("opensoft/triad", t["assembly"], "triad-1", "triad-2")
    return b, t


def _lane_start_reader() -> list:
    text = (REPO / "lane-start").read_text(encoding="utf-8")
    start = text.index("    ls_cand=\"$(awk -v want=\"$ls_home\" '\n")
    lines = text[start:].splitlines()[1:8]
    return [ln.strip() for ln in lines]


def _shared_reader() -> list:
    text = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    start = text.index("project_leg_paths_file() {")
    lines = text[start:].splitlines()[3:10]
    return [ln.strip() for ln in lines]


def test_t018_the_legs_reader_is_lane_starts_rung_5_line_for_line():
    """NEVER A SECOND GRAMMAR: the seven lines that decide what a leg is are
    the ones `lane-start` resolves a lane's directory with."""
    theirs, ours = _lane_start_reader(), _shared_reader()
    assert len(theirs) == 7 and theirs[0].startswith("/^[A-Za-z_]"), theirs
    assert theirs == ours


@NEEDS_UPSTREAM
def test_t018_project_legs_reads_the_templates_manifest(tmp_path):
    b = Bench(tmp_path / "bench", REPO)
    t = build_assembly(b)
    a = t["assembly"]
    proc = b.tool("lanes-edit.sh", "project-legs", a, env={"AGENT_PROTOCOL_ROOT": str(tmp_path / "none")})
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == [f"opensoft/triad-spec\tspec\t{a}/spec",
                                        f"opensoft/triad-code\tcode\t{a}/code"]
    for where, rc in ((b.projects, 8), (b.projects / "wip", 8)):
        proc = b.tool("lanes-edit.sh", "project-legs", where)
        assert proc.returncode == rc, proc.stdout + proc.stderr
    assert b.tool("lanes-edit.sh", "project-legs", "relative").returncode == 64
    os.chmod(a / "project.yaml", 0)
    try:
        if os.geteuid() != 0:
            proc = b.tool("lanes-edit.sh", "project-legs", a)
            assert proc.returncode == 1 and "could not be read" in proc.stderr
    finally:
        os.chmod(a / "project.yaml", 0o644)


@NEEDS_UPSTREAM
def test_t018_the_sweep_reads_every_leg_and_its_nested_dependency(triad):
    b, t = triad
    proc = b.sweep("triad-1", "--dry-run", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    legs = porcelain_rows(proc.stdout, "leg")
    assert list(legs) == [str(t["spec"]), str(t["code"]), str(t["dep"])]
    assert all(r["disposition"] == "clean" and r["retire"] == "-" for r in legs.values()), legs
    assert "the code leg of" in legs[str(t["code"])]["why"]
    assert "nested in the code leg (code/upstream/dep)" in legs[str(t["dep"])]["why"]
    table = b.sweep("triad-1", "--dry-run")
    assert "LEGS (the assembly's own checkouts" in table.stdout
    assert "3 leg checkout(s), 0 counted" in table.stdout


@NEEDS_UPSTREAM
def test_t018_a_paired_code_tree_with_unpushed_lane_work_holds_lane_end(triad):
    """THE GAP §4.4 MEASURED: a paired `worktrees/<feature>/code` tree, made
    as Speckit makes one (a worktree of the code leg's repository), holding the
    lane's unpushed commit, passed `lane-end`. Now the sweep claims it by its
    HEAD's own `Lane:` trailer and the gate refuses, naming it."""
    b, t = triad
    tree = t["assembly"] / "worktrees" / "005-x" / "code"
    b.git("worktree", "add", "-q", "-b", "005-x", tree, "origin/main", cwd=t["code"])
    b.commit(tree, "the feature's code", {"f.txt": "f\n"}, lane="triad-1")
    # the paired spec tree carries another lane's work: never this lane's
    spec_tree = t["assembly"] / "worktrees" / "005-x" / "spec"
    b.git("worktree", "add", "-q", "-b", "005-x", spec_tree, "origin/main", cwd=t["spec"])
    b.commit(spec_tree, "the feature's spec", {"s.md": "s\n"}, lane="triad-2")
    proc = b.sweep("triad-1", *GATE, "--dry-run", "--porcelain")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    trees = porcelain_rows(proc.stdout, "tree")
    assert trees[str(tree)]["retire"] == "retire", trees
    assert "Lane: trailer" in trees[str(tree)]["why"]
    assert trees[str(spec_tree)]["disposition"] == "foreign", trees
    assert "paired feature worktrees" in trees[str(spec_tree)]["why"]
    assert "the spec leg of" in trees[str(spec_tree)]["why"]
    end = b.tool("lane-end", "triad-1")
    assert end.returncode == 2, end.stderr
    assert "lane triad-1 is NOT ended" in end.stderr and str(tree) in end.stderr
    assert "1 tree(s)" in end.stderr
    # and the other lane's own sweep claims the spec tree, not the code one
    other = porcelain_rows(b.sweep("triad-2", "--dry-run", "--porcelain").stdout, "tree")
    assert other[str(spec_tree)]["retire"] == "retire"
    assert other[str(tree)]["disposition"] == "foreign"


@NEEDS_UPSTREAM
def test_t018_a_leg_tree_made_elsewhere_is_registered_in_its_leg(triad):
    b, t = triad
    away = b.projects / "away-code"
    b.git("worktree", "add", "-q", "-b", "away", away, "origin/main", cwd=t["code"])
    proc = b.sweep("triad-1", "--dry-run", "--porcelain")
    row = porcelain_rows(proc.stdout, "tree")[str(away)]
    assert row["disposition"] == "foreign" and row["retire"] == "-", row
    assert "registered in the code leg of" in row["why"]
    # and a tree recorded with the leg as its checkout is the lane's
    rec = b.tool("lanes-edit.sh", "set-lane-tree", "triad-1", away, "--checkout", t["code"])
    assert rec.returncode == 0, rec.stderr
    row = porcelain_rows(b.sweep("triad-1", "--dry-run", "--porcelain").stdout, "tree")[str(away)]
    assert row["retire"] == "retire" and row["disposition"] == "remove", row


@NEEDS_UPSTREAM
def test_t018_a_leg_holding_the_lanes_unpushed_commit_is_counted(triad):
    """A lane working in the code leg itself: its HEAD's own trailer is this
    lane's and origin lacks it, so the leg is COUNTED - the gate refuses, and
    offers no `--yes`, which never acts on a leg."""
    b, t = triad
    b.git("checkout", "-q", "-b", "in-place", cwd=t["code"])
    b.commit(t["code"], "worked in the leg", {"w.txt": "w\n"}, lane="triad-1")
    proc = b.sweep("triad-1", "--dry-run", "--porcelain")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    leg = porcelain_rows(proc.stdout, "leg")[str(t["code"])]
    assert leg["disposition"] == "unpushed" and leg["retire"] == "retire", leg
    assert leg["branch"] == "in-place"
    end = b.tool("lane-end", "triad-1")
    assert end.returncode == 2
    assert "1 leg checkout(s)" in end.stderr and str(t["code"]) in end.stderr
    assert "no sweep acts on one" in end.stderr
    assert "--yes" not in end.stderr
    # another lane's sweep lists that leg and does not count it
    other = b.sweep("triad-2", "--dry-run", "--porcelain")
    assert other.returncode == 0, other.stdout
    assert porcelain_rows(other.stdout, "leg")[str(t["code"])]["retire"] == "-"
    assert b.tool("lane-end", "triad-2").returncode == 0


@NEEDS_UPSTREAM
def test_t018_a_dirty_leg_that_is_no_lanes_is_listed_never_counted(triad):
    b, t = triad
    (t["code"] / "scratch.txt").write_text("someone's edit\n")
    (t["dep"] / "d2.txt").write_text("an edit in the dependency\n")
    proc = b.sweep("triad-1", "--dry-run", "--porcelain")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    legs = porcelain_rows(proc.stdout, "leg")
    assert legs[str(t["code"])]["disposition"] == "dirty"
    assert legs[str(t["dep"])]["disposition"] == "dirty"
    assert all(r["retire"] == "-" for r in legs.values())
    end = b.tool("lane-end", "triad-1")
    assert end.returncode == 0, end.stderr
    assert "close-out gate: nothing of lane triad-1's is left on disk" in end.stderr
    assert "listed and NOT counted" in end.stderr and str(t["dep"]) in end.stderr


@NEEDS_UPSTREAM
def test_t018_the_legs_branches_are_read_under_branches(triad):
    b, t = triad
    tmp = b.root / "leg-branch"
    b.git("worktree", "add", "-q", "-b", "leg-old", tmp, "origin/main", cwd=t["code"])
    b.commit(tmp, "leg work", {"l.txt": "l\n"}, lane="triad-1")
    b.git("worktree", "remove", tmp, cwd=t["code"])
    proc = b.sweep("triad-1", "--branches", "--dry-run", "--porcelain")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    rows = [ln.split("\t") for ln in proc.stdout.splitlines() if ln.startswith("branch\t")]
    assert [r[3] for r in rows] == ["leg-old"], rows
    assert rows[0][2] == "retire" and rows[0][4].startswith("in the code leg of"), rows


@NEEDS_UPSTREAM
def test_t018_a_manifest_or_leg_that_cannot_be_read_refuses(triad):
    b, t = triad
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file")
    os.chmod(t["assembly"] / "project.yaml", 0)
    try:
        proc = b.sweep("triad-1", "--dry-run", "--porcelain")
    finally:
        os.chmod(t["assembly"] / "project.yaml", 0o644)
    assert proc.returncode == 2, proc.stdout
    assert "the legs of the assembly" in proc.stdout and "could not be read" in proc.stdout


@NEEDS_UPSTREAM
def test_t018_a_leg_git_cannot_read_is_counted_and_holds_lane_end(triad):
    """A LEG WITH A `.git` OF ITS OWN THAT GIT CANNOT READ is a read that
    failed, never an absent or a clean leg (Amendment 7(d)): its row is
    `unreadable` and counted, the dry run exits 3, and `lane-end` refuses,
    naming it."""
    b, t = triad
    (t["spec"] / ".git").write_text("gitdir: /nonexistent/t018-spec\n")
    proc = b.sweep("triad-1", "--dry-run", "--porcelain")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    leg = porcelain_rows(proc.stdout, "leg")[str(t["spec"])]
    assert leg["disposition"] == "unreadable" and leg["retire"] == "retire", leg
    assert "git could not be read through it" in leg["why"], leg
    end = b.tool("lane-end", "triad-1")
    assert end.returncode == 2, end.stderr
    assert "lane triad-1 is NOT ended" in end.stderr and str(t["spec"]) in end.stderr


@NEEDS_UPSTREAM
def test_t018_dependencies_a_leg_nests_that_cannot_be_listed_refuse_the_sweep(triad):
    """THE SWEEP'S OWN REFUSAL, UNSHADOWED: `git submodule status --recursive`
    failing in a checked-out leg - here a nested dependency whose `.git` names
    no repository - leaves the assembly's checkouts unknown, so the sweep
    refuses, exit 2. `lane-reconcile` does not read nested dependencies, so its
    verdict is no `indeterminate` that refuses first: this is `_assembly`'s."""
    b, t = triad
    a = t["assembly"]
    (t["dep"] / ".git").write_text("gitdir: /nonexistent/t018-dep\n")
    rec = b.tool("lanes-edit.sh", "lane-reconcile", "triad-1")
    verdict = next((ln.split(US)[1] for ln in rec.stdout.splitlines()
                    if ln.split(US)[0] == "VERDICT"), "")
    assert verdict and verdict != "indeterminate", rec.stdout
    proc = b.sweep("triad-1", "--dry-run", "--porcelain")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert f"the legs of the assembly {a} could not be read" in proc.stdout, proc.stdout
    assert "the dependencies nested in the code leg" in proc.stdout
    assert "could not be listed (git submodule status failed)" in proc.stdout


@NEEDS_UPSTREAM
def test_t018_a_leg_that_is_not_checked_out_is_absent_and_claims_no_tree_of_the_assembly(triad):
    """A DEINITIALIZED LEG is an empty directory of the assembly's, where git
    answers the ASSEMBLY. The sweep lists it `absent`, counted for nobody; the
    assembly's own trees and registrations stay the assembly's rather than
    becoming that leg's (`probe_leg`'s toplevel guard); and `add` from the
    assembly records the assembly, never the empty leg (`add`'s guard)."""
    b, t = triad
    a = t["assembly"]
    b.git("submodule", "deinit", "-q", "spec", cwd=a)
    assert not any((a / "spec").iterdir())
    made = b.tool("lane-worktrees", "add", "triad-1", "root-work")
    assert made.returncode == 0, made.stderr
    tree = made.stdout.strip()
    assert "is an ASSEMBLY, and this tree is of the assembly itself" in made.stderr
    assert "the spec leg of" not in made.stderr, made.stderr
    assert _inventory(b, "triad-1")[tree] == str(a)
    away = b.projects / "away-root"
    b.git("worktree", "add", "-q", "-b", "away-root", away, "origin/main", cwd=a)
    proc = b.sweep("triad-1", "--dry-run", "--porcelain")
    legs = porcelain_rows(proc.stdout, "leg")
    assert legs[str(t["spec"])]["disposition"] == "absent", legs
    assert legs[str(t["spec"])]["retire"] == "-", legs
    assert "not checked out here" in legs[str(t["spec"])]["why"], legs
    assert legs[str(t["code"])]["disposition"] == "clean", legs
    trees = porcelain_rows(proc.stdout, "tree")
    assert trees[tree]["retire"] == "retire", trees
    for path in (tree, str(away)):
        assert "spec leg" not in trees[path]["why"], trees[path]
    assert trees[str(away)]["disposition"] == "foreign", trees


def _lane_worktrees_module():
    """`lane-worktrees` as a module, its bytecode written nowhere (as
    tests/test_lane_worktrees.py loads it)."""
    import importlib.util
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("lane_worktrees_t018", str(REPO / "lane-worktrees"))
    spec = importlib.util.spec_from_loader("lane_worktrees_t018", loader)
    module = importlib.util.module_from_spec(spec)
    was = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = was
    return module


def test_t018_the_sweeps_paired_root_refuses_what_it_cannot_list_or_search(tmp_path):
    """THE SWEEP'S OWN PAIRED-ROOT REFUSAL (`Sweep._paired`), which no run
    shows: `lane-reconcile` reads the same directories first and says
    `indeterminate`, and the sweep refuses on that verdict before it looks.
    Called directly: the root, a feature directory, or a leg's directory under
    it that cannot be listed or searched each refuse, naming it; readable,
    the tree in it is found."""
    if os.geteuid() == 0:
        pytest.skip("root lists and searches a mode-000 directory")
    import types
    lw = _lane_worktrees_module()
    root = tmp_path / "worktrees"
    feature = root / "001-a"
    tree = feature / "code"
    tree.mkdir(parents=True)
    (tree / ".git").write_text("gitdir: /nonexistent\n")
    legs = [types.SimpleNamespace(decl="spec", nested_in=""),
            types.SimpleNamespace(decl="code", nested_in="")]

    def paired():
        sweep = types.SimpleNamespace(paired_root=str(root), legs=legs, refusal="")
        seen: dict = {}
        lw.Sweep._paired(sweep, seen)
        return sweep.refusal, seen

    refusal, seen = paired()
    assert refusal == "" and list(seen) == [lw.real(str(tree))], (refusal, seen)
    for target, mode, words in ((root, 0, "worktree root"), (root, 0o600, "worktree root"),
                                (feature, 0, "feature directory"),
                                (feature, 0o600, "feature directory"),
                                (tree, 0o600, "paired tree directory")):
        os.chmod(target, mode)
        try:
            refusal, seen = paired()
        finally:
            os.chmod(target, 0o755)
        assert f"{words} {target} could not be" in refusal, (target, oct(mode), refusal)
        assert not seen, (target, oct(mode), seen)


@NEEDS_UPSTREAM
def test_t018_project_legs_reads_quoted_scalars_as_openreposhape_v1_writes_them(triad):
    """openRepoShape v1.0.0 (opensoft/openRepoShape#395) writes the assembly
    template's scalars QUOTED: `path: "{{SPEC_PATH}}"` under `legs:`, and `id:`,
    `elected_on:`, `visibility:` and `tracking_branch:` alike. The one reader
    every lane tool asks reads `path: "code"` and `path: 'code'` - and a quoted
    `repository:` - exactly as `path: code`, so the sweep's leg rows are the
    same three."""
    b, t = triad
    a = t["assembly"]
    want = [f"opensoft/triad-spec\tspec\t{a}/spec", f"opensoft/triad-code\tcode\t{a}/code"]
    proc = b.tool("lanes-edit.sh", "project-legs", a)
    assert proc.returncode == 0 and proc.stdout.splitlines() == want, proc.stdout + proc.stderr
    plain = (a / "project.yaml").read_text(encoding="utf-8")
    for q in ('"', "'"):
        lines, inlegs, quoted = [], False, 0
        for line in plain.splitlines():
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", line):
                inlegs = line.startswith("legs:")
            top = re.match(r"^(id|elected_on|visibility|tracking_branch):\s*(\S.*?)\s*$", line)
            leg = re.match(r"^(\s+(?:repository|path):\s*)(\S.*?)\s*$", line) if inlegs else None
            m = top or leg
            if m:
                head = f"{m.group(1)}: " if top else m.group(1)
                line = f"{head}{q}{m.group(2).strip(chr(34) + chr(39))}{q}"
                quoted += 1
            lines.append(line)
        assert quoted >= 10, quoted
        (a / "project.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert f"path: {q}spec{q}" in (a / "project.yaml").read_text()
        proc = b.tool("lanes-edit.sh", "project-legs", a)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines() == want, (q, proc.stdout)
        legs = porcelain_rows(b.sweep("triad-1", "--dry-run", "--porcelain").stdout, "leg")
        assert list(legs) == [str(t["spec"]), str(t["code"]), str(t["dep"])], (q, legs)


# ========================================================= (c) the daily report

def _section(text: str, title: str) -> str:
    start = text.index(f"## {title}")
    end = text.find("\n## ", start + 3)
    return text[start:end if end != -1 else len(text)]


@NEEDS_UPSTREAM
def test_t018_the_report_counts_each_leg_as_a_checkout_of_its_own(triad):
    b, t = triad
    a = t["assembly"]
    tmp = b.root / "leg-branch"
    b.git("worktree", "add", "-q", "-b", "leg-unpushed", tmp, "origin/main", cwd=t["code"])
    b.commit(tmp, "leg work", {"l.txt": "l\n"}, lane="triad-1")
    b.git("worktree", "remove", tmp, cwd=t["code"])
    (t["spec"] / "edit.md").write_text("an edit in the spec leg\n")
    proc = b.tool("lane-worktrees", "sweep", "--all", "--dry-run", "--report", "--estate",
                  b.projects)
    assert proc.returncode == 0, proc.stderr
    branches = _section(proc.stdout, "Unmerged branches with a missing, diverged or unpushed upstream")
    assert f"- {t['code']} leg-unpushed ·" in branches, branches
    assert f"the code leg of {a}" in branches
    legs = _section(proc.stdout, "Assembly legs with uncommitted or unpublished work")
    assert f"- {t['spec']} · the spec leg of {a} ·" in legs, legs
    assert "1 dirty or untracked path(s)" in legs
    assert str(t["code"]) + " ·" not in legs
    assert "| Assembly legs with uncommitted or unpublished work | 1 |" in proc.stdout


def test_t018_a_report_with_no_assembly_has_no_legs_section(tmp_path):
    b = Bench(tmp_path / "bench", REPO)
    b.seeded("plain", {"p.txt": "p\n"})
    b.git("clone", "-q", b.remotes / "plain.git", b.projects / "plain")
    proc = b.tool("lane-worktrees", "sweep", "--all", "--dry-run", "--report", "--estate",
                  b.projects)
    assert proc.returncode == 0, proc.stderr
    assert "Assembly legs" not in proc.stdout


def test_t018_the_report_lists_a_leg_that_is_also_a_canonical_clone_once(tmp_path):
    """FINDING 1 OF THE READ-ONLY TRIAD MEASUREMENT (2026-10-17): a leg whose
    `.git` is a DIRECTORY - a clone, not a submodule's gitfile - is also one of
    the estate's canonical checkouts, and the report read it once as each, so
    its branch rows printed twice (8 rows on that workstation) and its `main`
    row would have. Each leg's rows now appear once, still naming the leg, in
    the branch, `main` and rescue sections. The manifest is written here, so
    no template is needed."""
    b = Bench(tmp_path / "bench", REPO)
    a = b.projects / "cl"
    b.origin("cl")
    b.git("clone", "-q", b.remotes / "cl.git", a)
    b.commit(a, "the assembly, its legs clones", {
        ".gitignore": "spec/\ncode/\n",
        "project.yaml": ("schema_version: 1\nkind: project-manifest\nid: \"cl\"\nlegs:\n"
                         "  - role: assembly\n    repository: opensoft/cl\n    path: \".\"\n"
                         "  - role: spec\n    repository: opensoft/cl-spec\n    path: \"spec\"\n"
                         "  - role: code\n    repository: opensoft/cl-code\n    path: \"code\"\n")})
    b.git("push", "-q", "origin", "main", cwd=a)
    spec, code = a / "spec", a / "code"
    b.git("clone", "-q", b.seeded("cl-spec", {"s.md": "s\n"}), spec)
    b.git("clone", "-q", b.seeded("cl-code", {"c.txt": "c\n"}), code)
    assert (spec / ".git").is_dir() and (code / ".git").is_dir()
    # the code leg: a branch with no upstream, and a rescue branch past the aging line
    b.git("checkout", "-q", "-b", "leg-unpushed", cwd=code)
    b.commit(code, "leg work", {"l.txt": "l\n"}, lane="cl-1")
    b.git("checkout", "-q", "-b", "rescue/cl-1/old", "main", cwd=code)
    old = {"GIT_AUTHOR_DATE": "2020-01-01T00:00:00+00:00",
           "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+00:00"}
    made = b.run("git", "commit", "-q", "--allow-empty", "-m", "old rescue", cwd=code, env=old)
    assert made.returncode == 0, made.stderr
    b.git("checkout", "-q", "main", cwd=code)
    # the spec leg: local main ahead of origin
    b.commit(spec, "spec work on main", {"m.md": "m\n"}, lane="cl-1")

    proc = b.tool("lane-worktrees", "sweep", "--all", "--dry-run", "--report", "--estate",
                  b.projects)
    assert proc.returncode == 0, proc.stderr
    foreign = _section(proc.stdout, "FOREIGN repositories")
    assert str(spec) not in foreign and str(code) not in foreign, foreign   # both canonical
    branches = _section(proc.stdout, "Unmerged branches with a missing, diverged or unpushed upstream")
    rows = [ln for ln in branches.splitlines() if ln.startswith(f"- {code} leg-unpushed ·")]
    assert len(rows) == 1, branches
    assert rows[0].endswith(f"the code leg of {a}"), rows
    root_main = _section(proc.stdout, "Root main divergence")
    rows = [ln for ln in root_main.splitlines() if ln.startswith(f"- {spec} · local main ahead")]
    assert len(rows) == 1, root_main
    assert rows[0].endswith(f"the spec leg of {a}"), rows
    aging = _section(proc.stdout, "Awaiting disposition")
    rows = [ln for ln in aging.splitlines() if ln.startswith(f"- {code} rescue/cl-1/old ·")]
    assert len(rows) == 1, aging
    assert rows[0].endswith(f"the code leg of {a}"), rows
    legs = _section(proc.stdout, "Assembly legs with uncommitted or unpublished work")
    assert legs.count(f"- {spec} · the spec leg of {a} ·") == 1, legs


# ================================================================ (d) add

def _inventory(b: Bench, lane: str) -> dict:
    """{path: checkout} of the lane's #97 inventory."""
    proc = b.tool("lanes-edit.sh", "lane-trees", lane)
    assert proc.returncode in (0, 8), proc.stderr
    rows = {}
    for line in proc.stdout.splitlines():
        cols = line.split(US)
        if len(cols) > 9:
            rows[cols[1]] = cols[9]
    return rows


@NEEDS_UPSTREAM
def test_t018_add_records_the_leg_it_made_a_tree_from(triad):
    b, t = triad
    a = t["assembly"]
    dry = b.tool("lane-worktrees", "add", "triad-1", "c1", "--checkout", t["code"], "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert f"--checkout {t['code']} - the code leg of {a}/project.yaml (opensoft/triad-code)" \
        in dry.stderr
    made = b.tool("lane-worktrees", "add", "triad-1", "c1", "--checkout", t["code"])
    assert made.returncode == 0, made.stderr
    tree = Path(made.stdout.strip())
    assert f"in {t['code']} - the code leg of {a}/project.yaml" in made.stderr
    assert _inventory(b, "triad-1")[str(tree)] == str(t["code"])
    # FROM A WORKTREE OF THE LEG'S REPOSITORY, the leg is what is recorded
    paired = a / "worktrees" / "010-v" / "code"
    b.git("worktree", "add", "-q", "-b", "010-v", paired, "origin/main", cwd=t["code"])
    made = b.tool("lane-worktrees", "add", "triad-1", "c2", "--checkout", paired)
    assert made.returncode == 0, made.stderr
    assert f"with {t['code']} as its checkout" in made.stderr
    assert _inventory(b, "triad-1")[made.stdout.strip()] == str(t["code"])
    # the sweep then reads it through its leg
    row = porcelain_rows(b.sweep("triad-1", "--dry-run", "--porcelain").stdout,
                         "tree")[made.stdout.strip()]
    assert row["retire"] == "retire", row


@NEEDS_UPSTREAM
def test_t018_add_from_the_assembly_itself_says_its_legs_are_empty(triad):
    b, t = triad
    a = t["assembly"]
    made = b.tool("lane-worktrees", "add", "triad-1", "root-work")
    assert made.returncode == 0, made.stderr
    assert "is an ASSEMBLY, and this tree is of the assembly itself" in made.stderr
    # every leg is named, never only the last one the manifest declares
    assert f"--checkout {a}/spec or --checkout {a}/code" in made.stderr, made.stderr
    assert _inventory(b, "triad-1")[made.stdout.strip()] == str(a)



@NEEDS_UPSTREAM
def test_t018_add_refuses_where_the_manifest_cannot_be_read(triad):
    """Never "no legs" (Amendment 7(d)): which checkout the tree would be
    recorded under is unknown, so nothing is made, in the words the sweep
    and the reconciliation use for the same fact."""
    b, t = triad
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file")
    os.chmod(t["assembly"] / "project.yaml", 0)
    try:
        proc = b.tool("lane-worktrees", "add", "triad-1", "c9", "--checkout", t["code"])
    finally:
        os.chmod(t["assembly"] / "project.yaml", 0o644)
    assert proc.returncode == 2, proc.stderr
    assert (f"REFUSED, nothing was made: the legs of the assembly {t['assembly']} could not "
            "be read") in proc.stderr
    assert not (t["assembly"].parent / ".lane-worktrees" / "triad-1" / "c9").exists()
    assert not any(p.endswith("/c9") for p in _inventory(b, "triad-1"))

# ===================================================================== capture

def capture(tools: Path, golden: Path) -> None:
    """Write the golden file from the tools in `tools` - run ONCE, against
    `c45a452`'s (`git archive c45a452 | tar -x -C <dir>`), and committed."""
    with tempfile.TemporaryDirectory(prefix="t018-capture.") as tmp:
        text = render_golden(single_repository(Bench(Path(tmp) / "bench", tools)))
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) in (3, 4) and sys.argv[1] == "--capture":
        capture(Path(sys.argv[2]).resolve(), Path(sys.argv[3]) if len(sys.argv) == 4 else GOLDEN)
        sys.exit(0)
    sys.stderr.write("usage: test_triad_lane_tooling.py --capture <tools dir> [<golden>]\n")
    sys.exit(64)
