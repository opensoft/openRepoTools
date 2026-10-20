# SPDX-License-Identifier: Apache-2.0
"""The register sweeps and their reads fail closed: opensoft/openRepoTools#138
(the `lanes-edit.sh` items) and #157 item 4b.

Each case builds a throwaway register — a bare repository and a clone of it in
a temporary directory, with a temporary `$HOME` — and runs the real
`lanes-edit.sh` against it. A read that has to FAIL is made to fail by a `git`
on `PATH` that refuses one exact argument and hands every other call to the
real one, or by a permission or a file type the case puts on disk. Nothing here
reaches a network or the operator's own register.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None, reason="lanes-edit.sh is a bash command")]

#: The sweeping lane's transcript, and the old one the dormant rows carry.
WRITER_ID = "aaaa0138-0001-4000-8000-000000000001"
OLD_ID = "bbbb0138-0002-4000-8000-000000000002"
HEADER = ("| lane | session id | workstation / env / user | started (UTC) "
          "| objects owned | handoff path | state |\n|---|---|---|---|---|---|---|\n")
UNPRIVILEGED_ONLY = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="a permission case needs an unprivileged runner")


def row(lane: str, sid: str, state: str, started: str = "2026-08-27") -> str:
    return (f"| `{lane}` | harness `{sid}` | Eagle / test / brett | {started} "
            f"| none | none | {state} |\n")


def log_text(lane: str, *lines: str) -> str:
    head = f"# lane {lane} — object log (lane-collision-protocol Amendment 7)\n"
    return head + "".join(line + "\n" for line in lines)


def lane_line(verb: str, lane: str, sid: str, utc: str) -> str:
    return f"{verb} — lane {lane}, session {sid}@Eagle, {utc}, lane:{lane}"


class Register:
    """One workspace repository: `origin` bare, `wip` its clone, and W.

    THE EXPLICIT SEAM (Amendment 23; the review of opensoft/openRepoTools#282,
    MUST 5): every case writes through `wip`, named by `LANES_REPO`, which is
    where it puts its faults; W, the readers' copy `LANES_WORKSPACE_ROOT` names,
    is a clone of its own beside it. With `LANES_WORKSPACE_ROOT` at `wip` and
    no `LANES_REPO`, Amendment 23's routing would send every write to
    `<wip>-lanes/<lane>/`, away from the faults."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.origin = tmp / "origin.git"
        self.wip = tmp / "wip"
        self.home = tmp / "home"
        self.fakebin = tmp / "fakebin"
        for d in (self.home / ".agents", self.home / ".claude" / "sessions",
                  self.home / "projects", tmp / "tmp", self.fakebin):
            d.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("LANES_", "CLAUDE_", "TMUX"))}
        env.update(HOME=str(self.home), TMPDIR=str(tmp / "tmp"),
                   AGENT_PROTOCOL_ROOT=str(self.home / ".agents"),
                   PROJECTS_ROOT=str(self.home / "projects"),
                   LANES_WORKSTATION="Eagle",
                   LANES_HOST="Eagle", LANES_CONTAINER="none", LANES_IN_CONTAINER="0",
                   LANES_OS="linux", LANES_NO_GITHUB="1", LANES_INDEX="off",
                   GIT_AUTHOR_NAME="register tests", GIT_AUTHOR_EMAIL="t@example.invalid",
                   GIT_COMMITTER_NAME="register tests", GIT_COMMITTER_EMAIL="t@example.invalid",
                   PATH=str(self.fakebin) + os.pathsep + os.environ.get("PATH", ""))
        self.env = env
        self.raw_git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.raw_git("clone", "-q", str(self.origin), str(self.wip))
        (self.wip / "lanes" / "log").mkdir(parents=True)
        self.write("lanes/LANES.md", "# LANES.md\n\n" + HEADER
                   + row("repoX-1", WRITER_ID, "PAUSED · 2026-09-11T00:00:00Z · the sweeper", "2026-09-11")
                   + row("repoX-2", OLD_ID, "old words")
                   + row("repoX-3", OLD_ID, "more old words"))
        self.write("lanes/log/repoX-1.md", log_text(
            "repoX-1", lane_line("STARTED", "repoX-1", WRITER_ID, "2026-09-11T00:00:00Z"),
            lane_line("PAUSED", "repoX-1", WRITER_ID, "2026-09-11T01:00:00Z")))
        self.publish("seed the register")
        self.ws = tmp / "ro" / "wip"
        self.raw_git("clone", "-q", str(self.origin), str(self.ws))
        self.env.update(LANES_WORKSPACE_ROOT=str(self.ws), LANES_REPO=str(self.wip))

    def raw_git(self, *args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              check=True, env=self.env).stdout

    def git(self, *args: str) -> str:
        return self.raw_git("-C", str(self.wip), *args)

    def write(self, rel: str, text: str) -> Path:
        path = self.wip / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def read(self, rel: str) -> str:
        return (self.wip / rel).read_text(encoding="utf-8")

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def publish(self, message: str) -> None:
        self.commit(message)
        self.git("push", "-q", "-u", "origin", "main")

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def dirty(self) -> str:
        return self.git("status", "--porcelain")

    def refuse_git(self, *needles: str) -> None:
        """A `git` first on PATH that exits 128 when its arguments contain any
        of `needles`, and runs the real one otherwise."""
        real = shutil.which("git", path=os.environ.get("PATH"))
        cases = "\n".join(f'  *"{n}"*) echo "test shim: git $* refused" >&2; exit 128 ;;'
                          for n in needles)
        shim = self.fakebin / "git"
        shim.write_text(f'#!/usr/bin/env bash\ncase " $* " in\n{cases}\nesac\nexec "{real}" "$@"\n')
        shim.chmod(0o755)

    def live(self, sid: str) -> None:
        """A session record this workstation reads as LIVE: this test's own pid."""
        (self.home / ".claude" / "sessions" / f"{sid}.json").write_text(
            f'{{"pid":{os.getpid()},"sessionId":"{sid}","cwd":"x","procStart":"",'
            f'"tmux":"","name":"n","status":"idle"}}\n')

    def run(self, *args: str, **extra: str) -> subprocess.CompletedProcess:
        env = dict(self.env)
        env.update(extra)
        return subprocess.run(["bash", str(REPO / "lanes-edit.sh"), *args],
                              cwd=str(self.wip), env=env, text=True,
                              capture_output=True, timeout=120, check=False)

    def sweep(self, *lanes: str, **extra: str) -> subprocess.CompletedProcess:
        extra.setdefault("LANES_LANE", "repoX-1")
        return self.run("retire-rows", *lanes, "--reason", "test sweep", **extra)


@pytest.fixture
def reg(tmp_path: Path) -> Register:
    return Register(tmp_path)


def peer_edit(reg: Register) -> str:
    """A peer's uncommitted edit to the register, which a capture would commit."""
    text = reg.read("lanes/LANES.md").replace("more old words", "a peer's half-written cell")
    reg.write("lanes/LANES.md", text)
    return text


# ---------------------------------------------------------------- #157 item 4b

@pytest.mark.parametrize("act", [
    ("retire-rows", "repoX-2", "repoX-2", "--reason", "test sweep"),
    ("archive-rows", "repoX", "--yes"),
    ("migrate-state-cells", "--yes"),
], ids=["retire-rows", "archive-rows", "migrate-state-cells"])
def test_a_refusal_in_the_scan_commits_no_peer_edit(reg, act):
    """#157 4b: each sweep captured a peer's register edit as its own commit
    BEFORE its scan, so a refusal in the scan left HEAD moved. The refusal now
    comes first, and the peer's edit is still uncommitted after it."""
    edited = peer_edit(reg)
    before = reg.head()
    result = reg.run(*act, LANES_LANE="repoX-1")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "captured pre-existing edit" not in result.stderr
    assert reg.head() == before
    assert reg.read("lanes/LANES.md") == edited
    assert reg.dirty().strip() == "M lanes/LANES.md"


def test_a_sweep_over_a_peer_register_edit_refuses_and_captures_nothing(reg):
    """The capture moved in #157 4b; Amendment 23 S3 step 4 withdraws it
    (ratified choice 9, #198 slice 1b). A sweep that would write refuses (2)
    over a peer's pending register edit, commits nothing, and leaves the edit
    as it was, for `commit` to commit as its own act. It never lands inside
    the sweep's commit, which is what the capture was for."""
    edited = peer_edit(reg)
    before = reg.head()
    result = reg.sweep("repoX-2")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "never swept into another write" in result.stderr
    assert "captured pre-existing edit" not in result.stderr
    assert reg.head() == before
    assert reg.read("lanes/LANES.md") == edited


# ------------------------------------------------- #138: retire_rows' scan

def test_item_17_a_published_log_git_cannot_read_refuses_the_sweep(reg):
    """#138 item 17: the probe was `cat-file -e`, which fails for an unreadable
    blob exactly as for a missing path, so a log the tree names and git cannot
    read was "no published log" and the row was retired. The tree answers now.
    The local copy is out of the sparse checkout, so only origin speaks."""
    reg.write("lanes/log/repoX-2.md", log_text(
        "repoX-2", lane_line("STARTED", "repoX-2", OLD_ID, "2026-09-11T00:00:00Z"),
        lane_line("PAUSED", "repoX-2", OLD_ID, "2026-09-11T01:00:00Z")))
    reg.publish("repoX-2 is parked")
    reg.git("update-index", "--skip-worktree", "lanes/log/repoX-2.md")
    (reg.wip / "lanes/log/repoX-2.md").unlink()
    reg.refuse_git("origin/main:lanes/log/repoX-2.md")
    before = reg.head()
    result = reg.sweep("repoX-2")
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "exists on origin/main and could not be read" in result.stderr
    assert reg.head() == before
    assert not (reg.wip / "lanes/log/repoX-2.md").exists()


@UNPRIVILEGED_ONLY
def test_item_9_a_log_directory_that_cannot_be_listed_refuses_in_the_scan(reg):
    """#138 item 9: `log_files_named_ci` was `ls 2>/dev/null | awk`, so an
    unreadable log directory passed the scan as "no log" and the sweep failed
    on it later, inside its write loop (exit 5). It refuses in the scan now."""
    logs = reg.wip / "lanes" / "log"
    before = reg.head()
    logs.chmod(0)
    try:
        result = reg.sweep("repoX-2")
    finally:
        logs.chmod(0o755)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "exists and could not be listed" in result.stderr
    assert reg.head() == before
    assert reg.dirty() == ""


def test_item_12_a_symlinked_log_path_refuses_and_writes_nothing_through_it(reg):
    """#138 item 12: a tracked symlink at a lane's log path passed the scan, and
    the sweep's `>>` put the RETIRED line in the file it named — outside the
    repository — while the commit published only the link."""
    outside = reg.tmp / "outside.md"
    outside.write_text("# not the register's\n")
    (reg.wip / "lanes/log/repoX-2.md").symlink_to(os.path.join("..", "..", "..", "outside.md"))
    reg.publish("a link where a log belongs")
    before = reg.head()
    result = reg.sweep("repoX-2")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "is a symlink" in result.stderr
    assert outside.read_text() == "# not the register's\n"
    assert reg.head() == before


def test_item_8_the_retired_line_carries_the_writers_unpushed_newest_transcript(reg):
    """#138 item 8: the writer's uuid came from the PUBLISHED row alone, so a
    sweeping lane whose newest transcript is stamped in this checkout and not
    yet pushed signed its append-only RETIRED lines with the older one. Under
    Amendment 23 S3 (#198 slice 1b) a write refuses over an unpushed commit, so
    the stamp is published first; the RETIRED line must still carry the NEWEST
    id of the row, never its first."""
    newest = "dddd0138-0004-4000-8000-000000000004"
    text = reg.read("lanes/LANES.md").replace(
        f"| harness `{WRITER_ID}` |", f"| harness `{WRITER_ID}` `{newest}` |")
    reg.write("lanes/LANES.md", text)
    reg.publish("repoX-1 resumed in a new transcript")
    result = reg.sweep("repoX-2")
    assert result.returncode == 0, (result.stdout, result.stderr)
    retired = [line for line in reg.read("lanes/log/repoX-2.md").splitlines()
               if line.startswith("RETIRED")]
    assert len(retired) == 1
    assert f"session {newest}@Eagle" in retired[0]


# ------------------------------------------------ #138: archive_rows' preflight

def retire_repo_x_2(reg: Register) -> None:
    text = reg.read("lanes/LANES.md").replace(
        "| old words |", "| RETIRED · 2026-09-01T00:00:00Z · swept |")
    reg.write("lanes/LANES.md", text)


def test_item_10_a_symlinked_archive_refuses_and_the_row_stays_in_the_register(reg):
    """#138 item 10: a tracked symlink at the archive path passed every check,
    the rows were appended through it to a file outside the repository, and the
    commit published their removal from the register: the rows left the
    repository altogether."""
    retire_repo_x_2(reg)
    outside = reg.tmp / "outside.md"
    outside.write_text("# not the archive\n")
    (reg.wip / "lanes/archive").mkdir()
    (reg.wip / "lanes/archive/LANES-retired.md").symlink_to(
        os.path.join("..", "..", "..", "outside.md"))
    reg.publish("repoX-2 retired, and a link where the archive belongs")
    before = reg.head()
    result = reg.run("archive-rows", "repoX", "--yes", LANES_LANE="repoX-1")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "is a symlink" in result.stderr
    assert outside.read_text() == "# not the archive\n"
    assert reg.head() == before
    assert "`repoX-2`" in reg.git("show", "origin/main:lanes/LANES.md")


def test_item_2_a_published_archive_this_checkout_lacks_refuses_the_move(reg):
    """#138 item 2: with the published archive outside this checkout (skip-
    worktree, as a sparse checkout leaves it), the move created a NEW archive of
    its own rows and removed them from the register before git refused to stage
    the path (exit 6). It refuses before writing now."""
    reg.write("lanes/archive/LANES-retired.md", "# archive\n\n" + HEADER + row(
        "repoX-9", OLD_ID, "RETIRED · 2026-08-02T00:00:00Z · an earlier move", "2026-08-01"))
    retire_repo_x_2(reg)
    reg.publish("an archive with repoX-9, and repoX-2 retired")
    reg.git("update-index", "--skip-worktree", "lanes/archive/LANES-retired.md")
    (reg.wip / "lanes/archive/LANES-retired.md").unlink()
    before, register = reg.head(), reg.read("lanes/LANES.md")
    result = reg.run("archive-rows", "repoX", "--yes", LANES_LANE="repoX-1")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "is published on origin/main and this checkout does not have it" in result.stderr
    assert reg.head() == before
    assert reg.read("lanes/LANES.md") == register
    assert not (reg.wip / "lanes/archive/LANES-retired.md").exists()
    assert reg.dirty() == ""


# ---------------------------------- #138: the reads that hand out a position

def next_free(reg: Register, repo: str = "repoX") -> subprocess.CompletedProcess:
    env = dict(reg.env)
    return subprocess.run(["bash", str(REPO / "lanes-edit.sh"), "next-free", repo],
                          input="repoX-1\trow\n", cwd=str(reg.wip), env=env, text=True,
                          capture_output=True, timeout=60, check=False)


@pytest.mark.parametrize("kind", ["directory", "broken symlink", "fifo"])
def test_item_7_a_local_archive_that_is_not_a_regular_file_offers_no_position(reg, kind):
    """#138 item 7: `archive_text`'s local rung asked `-f` alone, so an archive
    path that is there and not a regular file read as no archive, and the
    positions it should reserve were offered again."""
    path = reg.wip / "lanes/archive/LANES-retired.md"
    path.parent.mkdir()
    if kind == "directory":
        path.mkdir()
    elif kind == "broken symlink":
        path.symlink_to("gone.md")
    else:
        os.mkfifo(path)
    result = next_free(reg)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert result.stdout == ""
    assert "could not be read" in result.stderr


@pytest.mark.parametrize("kind", ["zero bytes", "broken symlink"])
def test_item_5_a_register_path_that_renders_empty_offers_no_position(reg, kind):
    """#138 item 5: where origin has no register, the working-tree register
    counted as a source only under `[ -s ]`, so a zero-byte one — what a failed
    rewrite leaves — or a broken symlink was skipped and `next-free` answered
    from its stdin rows alone."""
    reg.git("rm", "-q", "-r", "--cached", "lanes")
    reg.write("README", "a workspace whose register is not published yet\n")
    reg.git("add", "README")
    reg.git("commit", "-q", "-m", "publish no register")
    reg.git("push", "-q", "origin", "main")
    register = reg.wip / "lanes/LANES.md"
    register.unlink()
    if kind == "zero bytes":
        register.write_text("")
    else:
        register.symlink_to("gone.md")
    result = next_free(reg)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert result.stdout == ""


# ------------------------------------------- #138: the listing's DORMANT class

def classes(reg: Register) -> tuple:
    result = reg.run("lanes", "--closed", "--prefix", "repoX")
    assert result.returncode == 0, (result.stdout, result.stderr)
    return {f[0]: f[13] for f in (line.split("\t") for line in result.stdout.splitlines()) if len(f) > 13}, result.stderr


@UNPRIVILEGED_ONLY
def test_item_4_a_log_directory_that_cannot_be_listed_classes_no_row_dormant(reg):
    """#138 item 4: the listing's fence of this checkout's logs was
    `ls 2>/dev/null`, so an unreadable directory hid a log committed here and
    not yet pushed, and its lane was classed DORMANT — hidden, and offered to
    the sweep."""
    reg.write("lanes/log/repoX-2.md", log_text(
        "repoX-2", lane_line("STARTED", "repoX-2", OLD_ID, "2026-10-13T00:00:00Z")))
    reg.commit("repoX-2 started here, not yet pushed")
    readable, _ = classes(reg)
    assert readable["repoX-2"] == "none" and readable["repoX-3"] == "dormant"
    logs = reg.wip / "lanes" / "log"
    logs.chmod(0)
    try:
        unreadable, err = classes(reg)
    finally:
        logs.chmod(0o755)
    assert unreadable["repoX-2"] == "none"
    assert "could not be listed" in err


@UNPRIVILEGED_ONLY
def test_item_4_the_sweep_refuses_rather_than_finding_nothing_to_do(reg):
    """The review of #230: with the class withheld, `lane-end --retire-dormant`
    counted zero dormant rows and exited 8, "there is nothing to do", about rows
    nobody could class. It turns the listing's sentence into a refusal (1)."""
    logs = reg.wip / "lanes" / "log"
    logs.chmod(0)
    try:
        result = retire_dormant(reg)
    finally:
        logs.chmod(0o755)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "classed none of them DORMANT" in result.stderr


def retire_dormant(reg: Register) -> subprocess.CompletedProcess:
    """`lane-end --retire-dormant repoX`, the dry run, with this checkout's helper."""
    env = dict(reg.env, LANES_EDIT=str(REPO / "lanes-edit.sh"))
    return subprocess.run(["bash", str(REPO / "lane-end"), "--retire-dormant", "repoX"],
                          cwd=str(reg.wip), env=env, text=True, capture_output=True,
                          timeout=120, check=False)


def test_item_11_a_published_log_git_cannot_read_is_never_classed_dormant(reg):
    """#138 item 11: DORMANT is read from a lane's absence from the facts pass,
    and a published log whose `git show` failed gave that pass no lines, so an
    IDLE lane read as NO LOG, was hidden, and was offered to the sweep. Its
    local copy is out of the sparse checkout, so only origin speaks for it."""
    reg.write("lanes/log/repoX-2.md", log_text(
        "repoX-2", lane_line("STARTED", "repoX-2", OLD_ID, "2026-10-13T00:00:00Z")))
    reg.publish("repoX-2 started")
    reg.git("update-index", "--skip-worktree", "lanes/log/repoX-2.md")
    (reg.wip / "lanes/log/repoX-2.md").unlink()
    readable, _ = classes(reg)
    assert readable["repoX-2"] == "none" and readable["repoX-3"] == "dormant"
    reg.refuse_git("origin/main:lanes/log/repoX-2.md")
    unreadable, err = classes(reg)
    assert unreadable["repoX-2"] == "none"
    assert unreadable["repoX-3"] == "dormant"
    assert "lanes/log/repoX-2.md" in err


# ----------------------------------------------- #138: add-row's published scan

def peer_publishes_repo_x_5(reg: Register) -> None:
    """A peer publishes a row for repoX-5 above the others, so this checkout's
    append of a second one would rebase cleanly over it."""
    peer = reg.tmp / "peer"
    reg.raw_git("clone", "-q", str(reg.origin), str(peer))
    lines = (peer / "lanes/LANES.md").read_text(encoding="utf-8").splitlines(True)
    rule = next(n for n, line in enumerate(lines) if line.startswith("|---"))
    lines.insert(rule + 1, row("repoX-5", "eeee0138-0005-4000-8000-000000000005", "started on the peer", "2026-10-13"))
    (peer / "lanes/LANES.md").write_text("".join(lines), encoding="utf-8")
    reg.raw_git("-C", str(peer), "commit", "-q", "-am", "the peer adds repoX-5")
    reg.raw_git("-C", str(peer), "push", "-q", "origin", "main")


def delete_published_register_blob(reg: Register, *, pull: bool) -> None:
    """Fetch (or pull) the peer's register, then delete its blob from this
    clone's object store: the tree still names the path, and git cannot read it."""
    reg.git("config", "fetch.unpackLimit", "100000")
    reg.git(*(("pull", "-q", "--rebase") if pull else ("fetch", "-q")))
    blob = reg.git("rev-parse", "origin/main:lanes/LANES.md").strip()
    loose = reg.wip / ".git" / "objects" / blob[:2] / blob[2:]
    assert loose.is_file(), "the register blob is not a loose object here"
    loose.unlink()


def add_repo_x_5(reg: Register) -> subprocess.CompletedProcess:
    return reg.run("add-row", row("repoX-5", "ffff0138-0006-4000-8000-000000000006", "new here",
                                  "2026-10-13").rstrip("\n"), LANES_LANE="repoX-5")


def published_repo_x_5_rows(reg: Register) -> int:
    return reg.raw_git("-C", str(reg.origin), "show", "main:lanes/LANES.md").count("| `repoX-5` |")


@pytest.mark.parametrize("mode", ["git refuses cat-file and show", "the blob is gone"])
def test_item_18_a_published_register_git_cannot_read_is_not_this_checkouts_copy(reg, mode):
    """#138 item 18, the review of #230: `register_text` asked `cat-file -e`
    whether the register is published, which fails for an unreadable blob as for
    an absent path, so it read THIS checkout's copy instead and add-row's check
    passed — a duplicate landed (exit 0), or was committed here and stopped only
    by the rebase (exit 3). The tree answers now, and the read refuses."""
    peer_publishes_repo_x_5(reg)
    if mode == "the blob is gone":
        delete_published_register_blob(reg, pull=False)
    else:
        reg.refuse_git("origin/main:lanes/LANES.md")
    before = reg.head()
    result = add_repo_x_5(reg)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "published register on origin/main could not be read" in result.stderr
    assert reg.head() == before
    assert published_repo_x_5_rows(reg) == 1


def test_item_18_next_free_refuses_a_published_register_git_cannot_read(reg):
    """The same probe in `lane_position_rows`: with the published register's
    blob gone, `next-free` answered from this checkout's copy."""
    peer_publishes_repo_x_5(reg)
    delete_published_register_blob(reg, pull=False)
    result = next_free(reg)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert result.stdout == ""


def test_item_18_the_seam_refuses_a_sweep_over_a_published_register_git_cannot_read(reg):
    """And the seam: with the published register unreadable and this checkout
    current, `register_text` handed it this checkout's copy, called every lane
    legacy, and the sweep was published."""
    peer_publishes_repo_x_5(reg)
    delete_published_register_blob(reg, pull=True)
    before = reg.head()
    result = reg.sweep("repoX-3", LANES_SESSION=WRITER_ID)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "is UNKNOWN" in result.stderr
    assert reg.head() == before


def test_item_18_an_unreadable_register_withholds_the_class_and_the_sweep_refuses(reg):
    """The re-review of #230: the listing built its rows from `register_text`
    with its status thrown away, so with the published register's blob gone
    repoX-2 and repoX-3 vanished, and `lane-end --retire-dormant` said "nothing
    to do" (exit 8). The listing says so and withholds the class; the sweep
    refuses (1)."""
    peer_publishes_repo_x_5(reg)
    delete_published_register_blob(reg, pull=False)
    listing = reg.run("lanes", "--closed", "--prefix", "repoX")
    assert "no row is classed DORMANT here" in listing.stderr
    result = retire_dormant(reg)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "classed none of them DORMANT" in result.stderr


def peer_archives_repo_x_4(reg: Register, mode: str) -> None:
    """A peer publishes the archive, retiring repoX-4; this checkout fetches it
    and does not pull. Then git cannot read the archive's blob: refused by a
    `git` on PATH, or deleted from this clone's object store."""
    peer = reg.tmp / "peer"
    reg.raw_git("clone", "-q", str(reg.origin), str(peer))
    (peer / "lanes/archive").mkdir()
    (peer / "lanes/archive/LANES-retired.md").write_text("# archive\n\n" + HEADER + row(
        "repoX-4", OLD_ID, "RETIRED \u00b7 2026-08-02T00:00:00Z \u00b7 moved", "2026-08-01"), encoding="utf-8")
    reg.raw_git("-C", str(peer), "add", "-A")
    reg.raw_git("-C", str(peer), "commit", "-q", "-m", "the peer archives repoX-4")
    reg.raw_git("-C", str(peer), "push", "-q", "origin", "main")
    reg.git("config", "fetch.unpackLimit", "100000")
    reg.git("fetch", "-q")
    if mode == "the blob is gone":
        blob = reg.git("rev-parse", "origin/main:lanes/archive/LANES-retired.md").strip()
        loose = reg.wip / ".git" / "objects" / blob[:2] / blob[2:]
        assert loose.is_file(), "the archive blob is not a loose object here"
        loose.unlink()
    else:
        reg.refuse_git("origin/main:lanes/archive/LANES-retired.md")


@pytest.mark.parametrize("mode", ["git refuses cat-file and show", "the blob is gone"])
def test_item_18_a_published_archive_git_cannot_read_reissues_no_position(reg, mode):
    """The re-review of #230: `archive_text` asked `cat-file -e` too, so a
    published archive git could not read was "not published", this checkout's
    (absent) copy answered, `next-free` offered retired repoX-4 and add-row
    committed it. The tree answers now, and both refuse (1) before writing."""
    peer_archives_repo_x_4(reg, mode)
    offered = next_free(reg)
    assert offered.returncode == 1, (offered.stdout, offered.stderr)
    assert offered.stdout == ""
    before = reg.head()
    result = reg.run("add-row", row("repoX-4", "ffff0138-0006-4000-8000-000000000006", "new here",
                                    "2026-10-18").rstrip("\n"), LANES_LANE="repoX-4")
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert reg.head() == before
    assert "`repoX-4`" not in reg.raw_git("-C", str(reg.origin), "show", "main:lanes/LANES.md")


def test_item_18_an_unreadable_published_register_refuses_add_row(reg):
    """#138 item 18: `rows_named_ci` ended in an awk over `register_text`, which
    answered 0 with an empty text where `git show` of the published register
    failed, and `|| :` took what was left — so a row a peer had published and
    this checkout had not pulled was added a second time, and landed."""
    peer_publishes_repo_x_5(reg)
    reg.refuse_git("show origin/main:lanes/LANES.md")
    before = reg.head()
    result = add_repo_x_5(reg)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "published register on origin/main could not be read" in result.stderr
    assert reg.head() == before
    assert published_repo_x_5_rows(reg) == 1


def test_item_1_an_unreadable_published_register_refuses_the_sweep(reg):
    """#138 item 1, ALREADY FIXED on main: refusal 1 reads both rows' ids
    through `|| :`, but the seam asked just before it (`managed_seam_refuse`,
    from #97) reads the published register and this checkout's row with their
    status and refuses UNKNOWN (1) on either failing. Pinned here, because
    the fence for a live session whose id is only in the published row rests
    on that refusal. (It used to be reached with this checkout's uncommitted
    edit dropping the id; Amendment 23 S3 now refuses that edit first, choice
    9, so the published read's failure is pinned on its own.)"""
    live = "cccc0138-0003-4000-8000-000000000003"
    text = reg.read("lanes/LANES.md").replace(f"| `repoX-2` | harness `{OLD_ID}`", f"| `repoX-2` | harness `{live}`")
    reg.write("lanes/LANES.md", text)
    reg.publish("repoX-2 is live in a session here")
    reg.live(live)
    reg.refuse_git("show origin/main:lanes/LANES.md")
    before = reg.head()
    result = reg.sweep("repoX-2", LANES_SESSION=WRITER_ID)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "is UNKNOWN" in result.stderr
    assert reg.head() == before
    assert not (reg.wip / "lanes/log/repoX-2.md").exists()


# ------------------------------------- Amendment 23's routing, by default resolution

def test_a_routed_sweep_refuses_over_a_peer_edit_in_W_and_captures_nothing(reg):
    """SHOULD 4, the default-resolution case of the capture above. Under
    `LANES_ROUTE_WRITES=1` with W resolved from its root and no `LANES_REPO`,
    the sweep goes through the sweeping lane's own checkout, so nothing would
    ever capture the peer's edit in W. It refuses, names the edit and that
    checkout, and leaves W, origin and the edit as they were."""
    edited = peer_edit(reg)
    before = reg.head()
    published = reg.raw_git("--git-dir", str(reg.origin), "rev-parse", "main").strip()
    result = reg.sweep("repoX-2", LANES_ROUTE_WRITES="1", LANES_REPO="",
                       LANES_WORKSPACE_ROOT=str(reg.wip))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "uncommitted edit to its register" in result.stderr, result.stderr
    assert f"{os.path.realpath(reg.wip)}-lanes/repoX-1/lanes/LANES.md" in result.stderr
    assert reg.head() == before and reg.read("lanes/LANES.md") == edited
    assert reg.raw_git("--git-dir", str(reg.origin), "rev-parse", "main").strip() == published
    assert not (reg.tmp / "wip-lanes").exists()
