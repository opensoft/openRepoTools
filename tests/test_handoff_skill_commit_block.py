# SPDX-License-Identifier: Apache-2.0
"""`skills/handoff/SKILL.md`'s step-2 handoff commit, held to
opensoft/openRepoTools#197, in seconds rather than the shell suite's hour.

The block a session runs after publishing its handoff was

    cd ~/projects/brett-wip
    git add "$handoff"
    git commit -m "handoff(<lane>@<ws>): PAUSED, <one-line state>" -m "Lane: <lane>"
    git pull --rebase && git push

and its own paragraph said "Commit with an explicit pathspec" and "On a
rebase conflict: abort". A bare `git commit` takes the WHOLE index, so in a
checkout holding another lane's staged entry it published that entry; the
spelled path is not the checkout a lane window writes (`LANES_REPO` names the
lane's own clone); and a same-file conflict left the checkout mid-rebase.
Amendment 4(d) requires *"explicit pathspecs — never `git add -A`, never a bare
`git commit` … on a rebase conflict the writer ABORTS, leaves the checkout
clean and reports"*, and Amendment 5(c) bans a bare `git commit` too.

THE BLOCK IS RUN, NOT READ. It is extracted from the skill by the commit
message it writes, which the shipped block and the fixed one BOTH carry, so
every behavioural case below runs whichever block the file holds: each RED
case fails against the shipped block for the reason #197 measured, and passes
with the fix. Each runs under `bash`, and under `zsh` where one is installed,
because the Bash tool runs a skill's block under the user's own shell.

NOTHING HERE READS THE CALLER'S ENVIRONMENT. The block READS `LANES_REPO`,
and a lane window exports it to that lane's REAL clone, so the environment is
an explicit dict, never `os.environ` plus changes: no `LANES_*`, no `TMUX*`,
`HOME` under `tmp_path`, no system git config. Every repository is under
`tmp_path`: a bare origin, the "shared" checkout at
`$HOME/projects/brett-wip` (which the stub `lanes-edit.sh` names as the
workspace root), the lane's own clone, and a peer clone that lands other
lanes' work. `maintenance.auto=false` and `gc.auto=0` keep git from starting
background work in the fixtures (#599's cleanup flake).
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the skill's blocks are shell, and they run git")]

SKILL = REPO / "skills/handoff/SKILL.md"

#: THE COMMIT MESSAGE, which the shipped block and the fixed one both write and
#: no other fenced block of the skill carries: it is how the block is found.
MARKER = "PAUSED, <one-line state>"

HANDOFF = "handoffs/h1.md"      # this lane's handoff: the row's own cell
PEER = "handoffs/h2.md"         # another lane's handoff
REGISTER = "lanes/LANES.md"

H1_V1, H1_V2 = "h1 v1\n", "h1 v2 (this lane PAUSED)\n"
H2_V1, H2_V2 = "h2 v1\n", "h2 v2 (peer P1)\n"
ROWS = "| row1 | a |\n| row2 | a |\n| row3 | a |\n| row4 | {} |\n"

GITCONFIG = """[user]
\tname = sandbox
\temail = sandbox@example.invalid
[init]
\tdefaultBranch = main
[maintenance]
\tauto = false
[gc]
\tauto = 0
[advice]
\tdetachedHead = false
[commit]
\tgpgsign = false
"""

#: The stub helper: `workspace-root` is the only verb the block calls.
STUB = """#!/bin/sh
case "$1" in
  workspace-root) printf '%s\\n' "$HOME/projects/brett-wip" ;;
  *) exit 2 ;;
esac
"""

SHELLS = [
    pytest.param("bash", id="bash"),
    pytest.param("zsh", id="zsh", marks=pytest.mark.skipif(
        shutil.which("zsh") is None, reason="no zsh here")),
]


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _blocks(text: str) -> List[str]:
    return re.findall(r"^```(?:sh|bash)\n(.*?)\n```$", text,
                      re.DOTALL | re.MULTILINE)


def _block() -> str:
    found = [b for b in _blocks(_text()) if MARKER in b]
    assert len(found) == 1, (
        f"expected exactly one fenced block of {SKILL.name} carrying "
        f"{MARKER!r}, found {len(found)}: this test is stale")
    return found[0]


def _section(heading: str) -> str:
    """The prose-and-code of one numbered `## <n>. …` step of the skill."""
    text = _text()
    start = text.index(heading)
    end = re.compile(r"\n## \d+\. ").search(text, start + 1)
    return text[start:end.start() if end else len(text)]


class Sandbox:
    """A bare origin, the clones a lane meets, and a hermetic environment."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "home"
        (self.home / "projects").mkdir(parents=True)
        (self.root / "tmp").mkdir()
        (self.home / ".gitconfig").write_text(GITCONFIG, encoding="utf-8")
        self.bin = root / "bin"
        self.bin.mkdir()
        self.helper = self.bin / "lanes-edit.sh"
        self.helper.write_text(STUB, encoding="utf-8")
        self.helper.chmod(self.helper.stat().st_mode | stat.S_IXUSR)
        self.origin = root / "origin.git"
        self.shared = self.home / "projects" / "brett-wip"
        self.own = self.home / "projects" / "brett-wip-own"
        self.peer = root / "peer"
        dirs: List[str] = [str(self.bin)]
        for tool in ("git", "bash", "zsh"):
            found = shutil.which(tool)
            if found and os.path.dirname(found) not in dirs:
                dirs.append(os.path.dirname(found))
        for fallback in ("/usr/bin", "/bin"):
            if fallback not in dirs:
                dirs.append(fallback)
        self.env: Dict[str, str] = {
            "HOME": str(self.home), "PATH": os.pathsep.join(dirs),
            "TMPDIR": str(self.root / "tmp"), "LC_ALL": "C", "TZ": "UTC",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_EDITOR": "true",
        }
        self._seed()

    # --- git, always in the sandbox's own environment ---------------------

    def git(self, *args: str, cwd: Optional[Path] = None,
            check: bool = True) -> subprocess.CompletedProcess:
        proc = subprocess.run(["git", *args], cwd=str(cwd or self.root),
                              env=self.env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, check=False,
                              timeout=120)
        if check and proc.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} in {cwd} failed:\n"
                                 f"{proc.stderr}{proc.stdout}")
        return proc

    def out(self, *args: str, cwd: Optional[Path] = None) -> str:
        return self.git(*args, cwd=cwd).stdout.strip()

    def _seed(self) -> None:
        self.git("init", "-q", "--bare", str(self.origin))
        seed = self.root / "seed"
        self.git("init", "-q", str(seed))
        (seed / "handoffs").mkdir()
        (seed / "lanes").mkdir()
        (seed / HANDOFF).write_text(H1_V1, encoding="utf-8")
        (seed / PEER).write_text(H2_V1, encoding="utf-8")
        (seed / REGISTER).write_text(ROWS.format("a"), encoding="utf-8")
        self.git("add", "--", HANDOFF, PEER, REGISTER, cwd=seed)
        self.git("commit", "-q", "-m", "seed", "--", HANDOFF, PEER, REGISTER,
                 cwd=seed)
        self.git("remote", "add", "origin", str(self.origin), cwd=seed)
        self.git("push", "-q", "origin", "main", cwd=seed)

    def clone(self, dest: Path) -> Path:
        self.git("clone", "-q", str(self.origin), str(dest))
        return dest

    def land(self, path: str, content: str, message: str) -> None:
        """Another lane lands `path` on origin, from its own clone."""
        if not self.peer.exists():
            self.clone(self.peer)
        self.git("pull", "-q", "--rebase", "origin", "main", cwd=self.peer)
        (self.peer / path).write_text(content, encoding="utf-8")
        self.git("commit", "-q", "-m", message, "--", path, cwd=self.peer)
        self.git("push", "-q", "origin", "main", cwd=self.peer)

    def regime2(self, checkout: Path) -> None:
        """The shared checkout's state from 2026-10-11T20:07Z (#197): a peer's
        v2 of `h2` lands, then `main` moves to it WITHOUT the index (a linked
        worktree's `checkout -B`), so the index still holds `h2` v1 — a
        STAGED reversal of the peer's work."""
        self.land(PEER, H2_V2, "P1: peer handoff v2")
        self.git("fetch", "-q", "origin", cwd=checkout)
        self.git("update-ref", "refs/heads/main", "origin/main", cwd=checkout)

    # --- reads -------------------------------------------------------------

    def head(self, checkout: Path) -> str:
        return self.out("rev-parse", "HEAD", cwd=checkout)

    def origin_head(self) -> str:
        return self.out("--git-dir", str(self.origin), "rev-parse", "main")

    def origin_file(self, path: str) -> str:
        return self.git("--git-dir", str(self.origin), "show",
                        f"main:{path}").stdout

    def staged(self, checkout: Path) -> List[str]:
        return self.out("diff", "--cached", "--name-only",
                        cwd=checkout).splitlines()

    def counts(self, checkout: Path) -> tuple:
        """(ahead, behind) against origin's main, after a fetch."""
        self.git("fetch", "-q", "origin", cwd=checkout)
        row = self.out("rev-list", "--left-right", "--count",
                       "HEAD...origin/main", cwd=checkout).split()
        return int(row[0]), int(row[1])

    def in_progress(self, checkout: Path) -> List[str]:
        gitdir = Path(self.out("rev-parse", "--absolute-git-dir", cwd=checkout))
        return [op for op in ("rebase-merge", "rebase-apply", "MERGE_HEAD",
                              "CHERRY_PICK_HEAD", "REVERT_HEAD")
                if (gitdir / op).exists()]

    # --- the block ----------------------------------------------------------

    def run(self, shell: str, lanes_repo: Optional[Path] = None,
            block: Optional[str] = None) -> subprocess.CompletedProcess:
        script = "\n".join([f"L={shlex.quote(str(self.helper))}",
                            f"handoff={shlex.quote(HANDOFF)}",
                            block if block is not None else _block()])
        env = dict(self.env)
        if lanes_repo is not None:
            env["LANES_REPO"] = str(lanes_repo)
        argv = [shutil.which(shell) or shell]
        if shell == "zsh":
            argv.append("-f")
        return subprocess.run([*argv, "-c", script], cwd=str(self.home),
                              env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, check=False,
                              timeout=120)


@pytest.fixture
def sb(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


def _said(proc: subprocess.CompletedProcess) -> str:
    return f"--- stdout\n{proc.stdout}--- stderr\n{proc.stderr}"


# --- RED 1: a foreign staged entry is never committed -----------------------

@pytest.mark.parametrize("shell", SHELLS)
def test_a_foreign_staged_entry_is_refused_and_nothing_is_published(sb, shell):
    shared = sb.clone(sb.shared)
    sb.regime2(shared)
    sb.land(REGISTER, ROWS.format("P2"), "P2: peer row4")   # another FILE moves
    (shared / HANDOFF).write_text(H1_V2, encoding="utf-8")
    assert sb.staged(shared) == [PEER], "the precondition: a staged reversal"
    head, origin = sb.head(shared), sb.origin_head()

    proc = sb.run(shell)

    assert sb.origin_file(PEER) == H2_V2, (
        "origin's copy of the PEER's handoff was reverted: the commit took a "
        f"staged entry this handoff did not make, and pushed it\n{_said(proc)}")
    assert sb.origin_head() == origin, f"origin moved\n{_said(proc)}"
    assert sb.head(shared) == head, f"a commit was made\n{_said(proc)}"
    assert "HANDOFF NOT COMMITTED" in proc.stdout, _said(proc)
    assert f"staged: {PEER}" in proc.stdout, (
        f"the refusal must name the staged path\n{_said(proc)}")
    assert sb.staged(shared) == [PEER], "the peer's entry is left as found"
    assert (shared / HANDOFF).read_text(encoding="utf-8") == H1_V2, (
        "the handoff file stays written")


# --- RED 2 and 3: the checkout is RESOLVED, `LANES_REPO` first --------------

@pytest.mark.parametrize("shell", SHELLS)
def test_lanes_repo_is_where_the_handoff_is_committed_and_the_shared_one_is_untouched(
        sb, shell):
    shared, own = sb.clone(sb.shared), sb.clone(sb.own)
    sb.regime2(shared)
    sb.git("pull", "-q", "--rebase", "origin", "main", cwd=own)
    (own / HANDOFF).write_text(H1_V2, encoding="utf-8")
    shared_head = sb.head(shared)

    proc = sb.run(shell, lanes_repo=own)

    assert sb.origin_file(PEER) == H2_V2, (
        "origin's copy of the peer's handoff was reverted from the SHARED "
        f"checkout, which this lane did not write\n{_said(proc)}")
    assert sb.origin_file(HANDOFF) == H1_V2, (
        f"the lane's handoff never reached origin\n{_said(proc)}")
    assert f"handoff pushed from {own}" in proc.stdout, _said(proc)
    assert sb.git("status", "--porcelain", cwd=own).stdout == "", (
        "the lane's own clone is left with its handoff uncommitted")
    assert sb.counts(own) == (0, 0)
    assert sb.head(shared) == shared_head, "the shared checkout was committed in"
    assert sb.staged(shared) == [PEER], "the shared checkout's index was touched"


@pytest.mark.parametrize("shell", SHELLS)
def test_lanes_repo_is_used_when_the_shared_checkout_is_clean(sb, shell):
    shared, own = sb.clone(sb.shared), sb.clone(sb.own)
    sb.land(PEER, H2_V2, "P1: peer handoff v2")
    for checkout in (shared, own):
        sb.git("pull", "-q", "--rebase", "origin", "main", cwd=checkout)
    (own / HANDOFF).write_text(H1_V2, encoding="utf-8")
    shared_head = sb.head(shared)

    proc = sb.run(shell, lanes_repo=own)

    assert sb.origin_file(HANDOFF) == H1_V2, (
        "the block exited without committing the handoff the lane wrote in "
        f"its own clone\n{_said(proc)}")
    assert sb.counts(own) == (0, 0), _said(proc)
    assert sb.head(shared) == shared_head


# --- RED 4: a same-file conflict is aborted, never left mid-rebase ----------

@pytest.mark.parametrize("shell", SHELLS)
def test_a_conflict_is_aborted_and_the_commit_stays_local(sb, shell):
    shared = sb.clone(sb.shared)
    sb.land(HANDOFF, "h1 v2 (someone else)\n", "P3: conflicting h1")
    (shared / HANDOFF).write_text(H1_V2, encoding="utf-8")
    origin = sb.origin_head()

    proc = sb.run(shell)

    assert sb.in_progress(shared) == [], (
        f"the checkout was left mid-operation\n{_said(proc)}")
    assert "HANDOFF NOT PUSHED" in proc.stdout, _said(proc)
    assert sb.origin_head() == origin
    assert sb.counts(shared) == (1, 1), _said(proc)
    assert sb.out("show", "--name-only", "--format=", "HEAD",
                  cwd=shared).splitlines() == [HANDOFF]
    assert sb.git("status", "--porcelain", cwd=shared).stdout == ""


# --- RED 5: an operation in progress is a refusal ---------------------------

@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("operation", ["rebase", "merge"])
def test_an_operation_in_progress_is_refused_before_any_commit(sb, shell, operation):
    shared = sb.clone(sb.shared)
    (shared / HANDOFF).write_text("h1 local\n", encoding="utf-8")
    sb.git("commit", "-q", "-m", "local h1", "--", HANDOFF, cwd=shared)
    sb.land(HANDOFF, "h1 peer\n", "P3: conflicting h1")
    if operation == "rebase":
        sb.git("pull", "-q", "--rebase", "origin", "main", cwd=shared, check=False)
    else:
        sb.git("fetch", "-q", "origin", cwd=shared)
        sb.git("merge", "-q", "--no-edit", "origin/main", cwd=shared, check=False)
    before = sb.in_progress(shared)
    assert before, f"the precondition: a {operation} stopped on its conflict"
    (shared / HANDOFF).write_text(H1_V2, encoding="utf-8")
    head, origin = sb.head(shared), sb.origin_head()

    proc = sb.run(shell)

    assert sb.head(shared) == head, (
        f"a commit was made in the middle of a {operation}\n{_said(proc)}")
    assert sb.origin_head() == origin, _said(proc)
    found = re.search(r"has an operation in progress \(([A-Za-z_-]+)\)",
                      proc.stdout)
    assert found and found.group(1) in before, (
        f"the refusal must name the operation ({before})\n{_said(proc)}")
    assert "HANDOFF NOT COMMITTED" in proc.stdout
    assert sb.in_progress(shared) == before, "the block finished what it did not start"


# --- RED 6: the text --------------------------------------------------------

def test_the_skill_never_spells_the_shared_checkout():
    spelled = [n + 1 for n, line in enumerate(_text().splitlines())
               if "~/projects/brett-wip" in line]
    assert not spelled, (
        "the handoff's checkout is resolved (`$LANES_REPO`, then the helper's "
        f"`workspace-root`), never spelled; these lines spell it: {spelled}")


#: A git INVOCATION of `add` or `commit`, with or without `-C <dir>` — and not
#: a message that only says the words ("git refused the add or the commit").
_GIT_VERB = r'\bgit(?:\s+-C\s+"[^"]*")?\s+{}\b'


def test_the_add_and_the_commit_name_the_handoff_by_its_own_path():
    lines = _block().splitlines()
    commits = [line for line in lines if re.search(_GIT_VERB.format("commit"), line)]
    adds = [line for line in lines if re.search(_GIT_VERB.format("add"), line)]
    assert commits and adds, "the block no longer adds and commits"
    for line in commits + adds:
        assert '-- "$handoff"' in line, (
            "every `git add` and `git commit` in the block carries the handoff's "
            f"own pathspec (Amendment 4(d): never a bare `git commit`): {line.strip()}")


def test_the_publication_target_is_named_as_the_committed_file():
    """`publish-handoff` writes `$handoff_file`, which no block defines; the
    prose must say it is the file the commit block resolves."""
    prose = re.sub(r"```.*?```", "", _section("## 2. Refresh the handoff"),
                   flags=re.DOTALL)
    assert "$handoff_file" in prose, (
        "step 2's prose never says which checkout `$handoff_file` is in, so the "
        "file published and the file committed can differ")
    assert "$LANES_REPO/$handoff" in prose


def test_the_block_parses_under_bash(tmp_path):
    """A keeper: the shipped block parsed too."""
    script = tmp_path / "block.sh"
    script.write_text(_block() + "\n", encoding="utf-8")
    proc = subprocess.run([shutil.which("bash") or "bash", "-n", str(script)],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr


# --- where the handoff is nowhere the block looks ---------------------------

@pytest.mark.parametrize("shell", SHELLS)
def test_a_handoff_under_neither_root_is_refused(sb, shell):
    """`$LANES_REPO` names no checkout and the workspace root has none: the
    block says so rather than running git wherever the shell stands."""
    origin = sb.origin_head()
    proc = sb.run(shell, lanes_repo=sb.root / "nowhere")
    assert "HANDOFF NOT COMMITTED" in proc.stdout, _said(proc)
    assert "under neither" in proc.stdout, _said(proc)
    assert sb.origin_head() == origin


# --- keepers: what the shipped block already did, still done ----------------

@pytest.mark.parametrize("shell", SHELLS)
def test_a_clean_current_checkout_is_committed_and_pushed(sb, shell):
    shared = sb.clone(sb.shared)
    (shared / HANDOFF).write_text(H1_V2, encoding="utf-8")
    proc = sb.run(shell)
    assert sb.origin_file(HANDOFF) == H1_V2, _said(proc)
    assert sb.counts(shared) == (0, 0)
    assert sb.out("log", "-1", "--format=%B", "origin/main",
                  cwd=shared).splitlines()[-1] == "Lane: <lane>"


@pytest.mark.parametrize("shell", SHELLS)
def test_the_handoff_already_staged_by_an_earlier_attempt_is_its_own(sb, shell):
    shared = sb.clone(sb.shared)
    (shared / HANDOFF).write_text(H1_V2, encoding="utf-8")
    sb.git("add", "--", HANDOFF, cwd=shared)
    proc = sb.run(shell)
    assert sb.origin_file(HANDOFF) == H1_V2, _said(proc)
    assert sb.counts(shared) == (0, 0)


@pytest.mark.parametrize("shell", SHELLS)
def test_a_lanes_repo_without_the_handoff_falls_back_to_the_workspace_root(sb, shell):
    shared = sb.clone(sb.shared)
    (sb.root / "elsewhere").mkdir()
    (shared / HANDOFF).write_text(H1_V2, encoding="utf-8")
    proc = sb.run(shell, lanes_repo=sb.root / "elsewhere")
    assert sb.origin_file(HANDOFF) == H1_V2, _said(proc)
    assert sb.counts(shared) == (0, 0)
