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
from conftest import REPO, UPSTREAM, WINDOWS_SKIP  # noqa: E402

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="the lane tools are bash and Python over git")]

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "t018" / "single-repository.golden"
TEMPLATE = UPSTREAM / "templates" / "assembly-root"
NEEDS_TEMPLATE = pytest.mark.skipif(
    not (TEMPLATE / "project.yaml").is_file(),
    reason="the pinned openRepoShape is not checked out; "
           "run `git submodule update --init upstream/openRepoShape`")

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
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {bare}\npath: {self.wip}\n")

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
    # sits under its root.
    for place, word in ((bench.home, "<HOME>"), (bench.root, "<ROOT>")):
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


@NEEDS_TEMPLATE
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


@NEEDS_TEMPLATE
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


@NEEDS_TEMPLATE
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


@NEEDS_TEMPLATE
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


@NEEDS_TEMPLATE
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


@NEEDS_TEMPLATE
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


@NEEDS_TEMPLATE
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


@NEEDS_TEMPLATE
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


# ========================================================= (c) the daily report

def _section(text: str, title: str) -> str:
    start = text.index(f"## {title}")
    end = text.find("\n## ", start + 3)
    return text[start:end if end != -1 else len(text)]


@NEEDS_TEMPLATE
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


@NEEDS_TEMPLATE
def test_t018_a_report_with_no_assembly_has_no_legs_section(tmp_path):
    b = Bench(tmp_path / "bench", REPO)
    b.seeded("plain", {"p.txt": "p\n"})
    b.git("clone", "-q", b.remotes / "plain.git", b.projects / "plain")
    proc = b.tool("lane-worktrees", "sweep", "--all", "--dry-run", "--report", "--estate",
                  b.projects)
    assert proc.returncode == 0, proc.stderr
    assert "Assembly legs" not in proc.stdout


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


@NEEDS_TEMPLATE
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


@NEEDS_TEMPLATE
def test_t018_add_from_the_assembly_itself_says_its_legs_are_empty(triad):
    b, t = triad
    a = t["assembly"]
    made = b.tool("lane-worktrees", "add", "triad-1", "root-work")
    assert made.returncode == 0, made.stderr
    assert "is an ASSEMBLY, and this tree is of the assembly itself" in made.stderr
    assert f"--checkout {a}/code" in made.stderr
    assert _inventory(b, "triad-1")[made.stdout.strip()] == str(a)


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
