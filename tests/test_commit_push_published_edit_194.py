# SPDX-License-Identifier: Apache-2.0
"""A register edit that is already a local commit is PUBLISHED by the re-run
its own RECOVERY prints (opensoft/openRepoTools#194).

`commit_push` returned at *"nothing staged … no commit made"* BEFORE its push
loop. So when a peer's uncommitted file had blocked the rebase and the helper
had exited 3 with the edit as a local commit, the RECOVERY it printed — the
peer commits its file, then `LANES_LANE=<lane> lanes-edit.sh commit "<what you
wrote>"` — staged nothing, exited 0 and pushed nothing. The commit stayed local
until some later write from that checkout happened to carry it.

Every run here is the real `lanes-edit.sh` in a sandbox: a bare origin, the
workstation's shared workspace checkout `wip` that `workspace.yaml` names, and
a second clone `peer` standing in for another workstation. `LANES_GIT` is a
wrapper that logs every NETWORK call the helper makes and runs the real git,
so a case can say whether the push loop was reached at all. Nothing reaches a
real remote.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

LANE = "repoP-1"
PEER_LANE = "repoQ-1"
REGISTER = "lanes/LANES.md"
PEER_HANDOFF = f"handoffs/{PEER_LANE}.md"
#: A tracked file outside `lanes/` and `handoffs/`, the kind the #214 review
#: saw a queued commit delete from origin.
TOOL = "scripts/link-estates"
SUBJECT = "row rewritten by hand"

#: The environment a case must not inherit from the host that runs it.
SCRUBBED_PREFIXES = ("LANES_", "LANE_START_", "CLAUDE_", "OPENREPOTOOLS_",
                     "FAKE_", "GIT_", "TMUX")
SCRUBBED = {"AGENT_PROTOCOL_ROOT", "PROJECTS_ROOT", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME"}

#: With FAKE_NET_RACE naming a tracked file, the FIRST push is raced: another
#: lane commits that file's deletion into the shared checkout after the
#: helper's fence has read the queue and before the push runs.
NET_GIT = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FAKE_NET_LOG"
if [ -n "${FAKE_NET_RACE:-}" ] && [ "${3:-}" = push ] && [ ! -e "$FAKE_NET_LOG.raced" ]; then
  : > "$FAKE_NET_LOG.raced"
  git -C "$2" rm -q -- "$FAKE_NET_RACE" && git -C "$2" commit -q -m "another lane, racing: retire the tool"
fi
exec git "$@"
"""

FAKE_GH = """#!/usr/bin/env bash
printf 'FAKE gh REFUSED: %s -- this suite reaches no GitHub surface\\n' "$*" >&2
exit 90
"""


def _row(lane: str, state: str) -> str:
    return (f"| `{lane}` | `{lane}-uuid` / window `{lane}` | Eagle / WSL2 / tester "
            f"| 2026-10-11T00:00Z | — | handoffs/{lane}.md | {state} |")


class Box:
    """One workstation's shared workspace checkout, its origin and a peer."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "home"
        self.origin = root / "origin.git"
        self.wip = self.home / "projects" / "wip"
        self.peer = root / "peer"
        self.net_log = root / "net.log"
        fakebin = root / "fakebin"
        for d in (self.home / ".agents", self.home / "projects", root / "tmp", fakebin):
            d.mkdir(parents=True, exist_ok=True)
        self.net_log.write_text("", encoding="utf-8")
        for name, text in (("net-git", NET_GIT), ("gh", FAKE_GH)):
            (fakebin / name).write_text(text, encoding="utf-8")
            (fakebin / name).chmod(0o755)

        env = {k: v for k, v in os.environ.items()
               if k not in SCRUBBED and not k.startswith(SCRUBBED_PREFIXES)}
        env.update({
            "HOME": str(self.home),
            "TMPDIR": str(root / "tmp"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "PATH": f"{fakebin}{os.pathsep}{env.get('PATH', '')}",
            "AGENT_PROTOCOL_ROOT": str(self.home / ".agents"),
            "LANES_WORKSTATION": "Eagle",
            "LANES_NO_GITHUB": "1",
            "LANES_INDEX": "off",
            "LANES_GIT": str(fakebin / "net-git"),
            "FAKE_NET_LOG": str(self.net_log),
            "GIT_AUTHOR_NAME": "commit_push tests",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "commit_push tests",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        self.env = env

        self.git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.git("clone", "-q", str(self.origin), str(self.wip))
        self.write(self.wip, REGISTER,
                   "# LANES.md -- the sandbox register\n\n"
                   "| lane | session id | workstation / env / user | started (UTC) "
                   "| objects owned | handoff path | state |\n"
                   "|---|---|---|---|---|---|---|\n"
                   f"{_row(LANE, 'LIVE · seeded')}\n"
                   f"{_row(PEER_LANE, 'LIVE · seeded')}\n")
        self.write(self.wip, PEER_HANDOFF, f"# {PEER_LANE}\n")
        self.write(self.wip, TOOL, "#!/usr/bin/env bash\n")
        self.git("-C", str(self.wip), "add", "--", REGISTER, PEER_HANDOFF, TOOL)
        self.git("-C", str(self.wip), "commit", "-q", "-m", "seed")
        self.git("-C", str(self.wip), "push", "-q", "origin", "main")
        self.git("clone", "-q", str(self.origin), str(self.peer))
        # AMENDMENT 23 S5: W, the readers' copy that workspace.yaml names, takes
        # no write, and a write that resolves by default goes through the lane's
        # own checkout beside it. These cases are about `commit_push` in the
        # checkout a write runs in, so they name `self.wip` by the explicit seam
        # (`LANES_REPO`, ort186 Q9), and W is a separate reader clone.
        self.ws = root / "ro" / "wip"
        self.git("clone", "-q", str(self.origin), str(self.ws))
        for key, value in (("gc.auto", "0"), ("maintenance.auto", "false")):
            self.git("-C", str(self.ws), "config", key, value)
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.ws}\n", encoding="utf-8")
        self.env["LANES_REPO"] = str(self.wip)

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    def wgit(self, *args: str) -> str:
        return self.git("-C", str(self.wip), *args)

    def ogit(self, *args: str) -> str:
        return self.git("--git-dir", str(self.origin), *args)

    @staticmethod
    def write(checkout: Path, rel: str, text: str) -> None:
        path = checkout / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def set_state(self, checkout: Path, lane: str, state: str) -> None:
        """A hand edit of one row's state cell, the edit `commit` wraps."""
        path = checkout / REGISTER
        text = path.read_text(encoding="utf-8")
        old = _row(lane, "LIVE · seeded")
        assert old in text, text
        path.write_text(text.replace(old, _row(lane, state)), encoding="utf-8")

    def peer_pushes(self, rel: str, text: str, message: str) -> None:
        """Origin moves on: a commit from another workstation."""
        self.write(self.peer, rel, text)
        self.git("-C", str(self.peer), "add", "--", rel)
        self.git("-C", str(self.peer), "commit", "-q", "-m", message)
        self.git("-C", str(self.peer), "push", "-q", "origin", "main")

    def peer_edit_in_wip(self, line: str) -> None:
        """A peer lane's handoff, mid-write and uncommitted in THIS checkout."""
        with (self.wip / PEER_HANDOFF).open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def queue(self, message: str, *, write: str = "", delete: str = "") -> str:
        """A commit made in THIS checkout and not pushed: someone's queue."""
        if write:
            with (self.wip / write).open("a", encoding="utf-8") as fh:
                fh.write(f"{message}\n")
            self.wgit("add", "--", write)
        if delete:
            self.wgit("rm", "-q", "--", delete)
        self.wgit("commit", "-q", "-m", message)
        return self.wgit("rev-parse", "HEAD").strip()

    def helper(self, *args: str, lane: str = LANE, **extra: str) -> subprocess.CompletedProcess:
        self.net_log.write_text("", encoding="utf-8")
        env = dict(self.env, LANES_LANE=lane, **extra)
        return subprocess.run(["bash", str(REPO / "lanes-edit.sh"), *args],
                              env=env, cwd=str(self.wip), capture_output=True,
                              text=True, timeout=180, check=False)

    def net_calls(self) -> list[str]:
        return self.net_log.read_text(encoding="utf-8").splitlines()

    def unpublished(self) -> list[str]:
        return self.wgit("rev-list", "origin/main..HEAD").split()

    def origin_file(self, rel: str) -> str:
        return self.ogit("show", f"main:{rel}")

    def origin_subjects(self) -> list[str]:
        return self.ogit("log", "--format=%s", "main").splitlines()


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def _line_of(stderr: str, needle: str) -> int:
    for number, line in enumerate(stderr.splitlines()):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} is on no line of:\n{stderr}")


def test_the_printed_recovery_publishes_the_edit_it_stranded(box):
    """THE ISSUE'S OWN SEQUENCE, END TO END. Origin moves on; a peer's handoff
    is uncommitted in the shared checkout; a register write commits, cannot
    pull, has its push rejected six times and exits 3 with the RECOVERY. The
    peer then commits its file exactly as that RECOVERY says, and the re-run it
    names must PUBLISH: one copy of the edit on origin, the peer's commit with
    it, and the commit origin already had kept — not exit 0 with nothing sent.
    """
    box.peer_pushes("handoffs/repoR-1.md", "# repoR-1\n",
                    "handoff(repoR-1@Raven): another workstation's write")
    box.peer_edit_in_wip("a peer's line, mid-write")
    box.set_state(box.wip, LANE, "LIVE · edited by hand")

    stranded = box.helper("commit", SUBJECT)
    assert stranded.returncode == 3, stranded.stderr
    assert "a peer's uncommitted file blocks the rebase" in stranded.stderr
    assert len(box.unpublished()) == 1, "the edit is a local commit and only that"
    # The RECOVERY names the re-run and says what it does once nothing is staged.
    assert 'LANES_LANE=<lane> lanes-edit.sh commit "<what you wrote>"' in stranded.stderr
    assert "If lanes/LANES.md is clean, that re-run makes no commit of its own" in stranded.stderr
    assert "pushes the local commits this lists" in stranded.stderr, stranded.stderr

    box.wgit("commit", "-q", "-m", f"handoff({PEER_LANE}@Eagle): the mid-write line",
             "--", PEER_HANDOFF)
    rerun = box.helper("commit", SUBJECT)
    assert rerun.returncode == 0, rerun.stderr
    assert "pushed origin/main" in rerun.stderr, rerun.stderr
    assert box.wgit("rev-parse", "HEAD") == box.ogit("rev-parse", "main")
    assert _row(LANE, "LIVE · edited by hand") in box.origin_file(REGISTER)
    assert "a peer's line, mid-write" in box.origin_file(PEER_HANDOFF)
    assert box.origin_file("handoffs/repoR-1.md") == "# repoR-1\n"
    subjects = box.origin_subjects()
    assert sum(s.endswith(f"): {SUBJECT}") for s in subjects) == 1, subjects
    assert len(subjects) == 4, ("seed, the other workstation's write, the edit and "
                                f"the peer's handoff — no commit of the re-run's own: {subjects}")


def test_a_clean_checkout_with_nothing_ahead_is_still_a_no_op(box):
    """TODAY'S BEHAVIOUR, KEPT. Nothing staged and nothing on HEAD that origin
    lacks: the same note, exit 0, no commit and no network call at all."""
    head, origin = box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")
    result = box.helper("commit", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert f"nothing staged for {REGISTER} — no commit made" in result.stderr
    assert "push" not in result.stderr, result.stderr
    assert box.net_calls() == []
    assert (box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")) == (head, origin)


def test_a_checkout_behind_origin_with_nothing_of_its_own_is_still_a_no_op(box):
    """Behind is not ahead: origin's newer commits are no local commit to
    publish, so this is the no-op above and not a pull."""
    box.peer_pushes("handoffs/repoR-1.md", "# repoR-1\n", "a newer commit elsewhere")
    box.wgit("fetch", "-q", "origin")
    head = box.wgit("rev-parse", "HEAD")
    result = box.helper("commit", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert f"nothing staged for {REGISTER} — no commit made" in result.stderr
    assert box.net_calls() == []
    assert box.wgit("rev-parse", "HEAD") == head


def test_publishing_past_a_peers_dirty_file_keeps_the_dirty_elsewhere_guard(box):
    """The publish takes the SAME push loop a commit does, guard included: with
    a peer's file still uncommitted it warns, names the file, skips the pull,
    pushes straight out, and leaves that file exactly as it found it."""
    box.set_state(box.wip, LANE, "LIVE · edited by hand")
    box.wgit("commit", "-q", "-m", f"LANES({LANE}@Eagle): {SUBJECT}", "--", REGISTER)
    box.peer_edit_in_wip("a peer's line, still mid-write")

    result = box.helper("commit", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert f"nothing staged for {REGISTER} — no commit made" in result.stderr
    assert ("WARNING: this checkout has uncommitted changes to files OTHER than the register"
            in result.stderr)
    assert PEER_HANDOFF in result.stderr
    assert "pushed origin/main (attempt 1, no pull" in result.stderr, result.stderr
    calls = [f" {c} " for c in box.net_calls()]
    assert not any(" pull " in c for c in calls), calls
    assert any(" push " in c for c in calls), calls
    assert box.wgit("rev-parse", "HEAD") == box.ogit("rev-parse", "main")
    assert _row(LANE, "LIVE · edited by hand") in box.origin_file(REGISTER)
    assert box.wgit("diff", "--name-only").split() == [PEER_HANDOFF]
    assert "still mid-write" not in box.origin_file(PEER_HANDOFF)


def test_the_conflict_recovery_warns_that_a_reset_drops_a_peers_commits(box):
    """The issue's near-loss of 2026-10-09: the conflict RECOVERY ended in
    `reset --hard origin/main`, which in a shared checkout also drops a PEER's
    unpushed commit. The RECOVERY lists every unpublished commit by content and
    says, before the reset, that it must not run while any of them is not the
    reader's own — and the helper itself leaves the peer's commit in place."""
    box.peer_edit_in_wip("a peer's handoff, committed and not yet pushed")
    box.wgit("commit", "-q", "-m", f"handoff({PEER_LANE}@Eagle): unpushed",
             "--", PEER_HANDOFF)
    peer_commit = box.wgit("rev-parse", "HEAD").strip()
    box.set_state(box.peer, LANE, "LIVE · the peer rewrote this row")
    box.git("-C", str(box.peer), "commit", "-q", "-am", "the same row, elsewhere")
    box.git("-C", str(box.peer), "push", "-q", "origin", "main")
    box.set_state(box.wip, LANE, "LIVE · edited by hand")

    result = box.helper("commit", SUBJECT)
    err = result.stderr
    assert result.returncode == 3, err
    assert "REBASE CONFLICT on origin/main" in err
    assert box.wgit("merge-base", "--is-ancestor", peer_commit, "HEAD") == ""

    aborted_at = box.wgit("rev-parse", "HEAD").strip()
    count = _line_of(err, "cherry origin/main")
    moved = _line_of(err, f"rev-parse HEAD   # if this is not {aborted_at}, STOP")
    listing = _line_of(err, "cherry -v origin/main HEAD")
    warning = _line_of(err, "Never reset, stash or overwrite a peer's work")
    drops = _line_of(err, "drops EVERY '+' commit in this checkout")
    reset = _line_of(err, "reset --hard origin/main")
    assert count < moved < listing < warning < drops < reset, err
    assert f"cherry origin/main {aborted_at}" in err.splitlines()[count]
    captures = "\n".join(err.splitlines()[listing:drops + 1])
    assert "LANES(concurrent@" in captures, captures
    assert "LANES(pre-existing@" in captures, captures
    assert "names no lane, so it is NOT yours" in captures, captures
    # NIT 5 (lane openRepoShape-2, 6243280936): the two lines that stop a
    # reader from resetting a peer's commit away, word for word, because
    # lane openRepoTools-5's #68 waits on these words.
    stop = _line_of(err, "if any '+' line is not your own write, STOP and take it to the lane its subject names")
    assert listing < stop < warning, err
    assert "# only if every '+' line is yours" in err.splitlines()[reset], err

    # The listing reads HEAD, which is what the reset acts on: a peer's commit
    # made AFTER the abort is in it too, and the moved-checkout STOP fires.
    later = box.queue(f"handoff({PEER_LANE}@Eagle): written after the abort", write=PEER_HANDOFF)
    assert box.wgit("rev-parse", "HEAD").strip() != aborted_at
    command = err.splitlines()[listing].split("lanes-edit: ", 1)[1].split("#", 1)[0].split()
    listed = subprocess.run(command, env=box.env, capture_output=True,
                            text=True, check=True).stdout
    assert f"+ {peer_commit}" in listed, listed
    assert any(line.startswith("+ ") and later in line.split()[1] for line in listed.splitlines()), listed


def test_the_dirty_checkout_refusal_names_the_act_to_re_run(box):
    """`refuse_dirty_checkout`'s RECOVERY used to end in *"then re-run:"*
    followed by two COMMIT commands, which read as if `lanes-edit.sh commit`
    were the re-run. The authors commit their files; what is re-run is the
    act that was refused, whose own push publishes their commits."""
    box.peer_edit_in_wip("a peer's line, mid-write")
    # An event names the transcript taking the act (Amendment 7(b)); without
    # one the write refuses before it ever reads the checkout.
    result = box.helper("log", "NOTED", f"lane:{LANE}", "a note",
                        LANES_SESSION="0e3c9a52-6d1b-4b8e-9f3a-2a7c5d4e6f81")
    assert result.returncode == 2, result.stderr
    assert "RECOVERY — whoever wrote those files commits them:" in result.stderr
    assert "then re-run the refused write NOTED" in result.stderr, result.stderr


@pytest.mark.parametrize("exported", [False, True], ids=["plain", "CP_PUBLISH_AHEAD-exported"])
def test_a_no_op_write_never_publishes_what_the_checkout_queued(box, exported):
    """THE #214 REVIEW'S BLOCKER. This shared checkout holds another lane's
    unpushed commit that deletes a file outside lane tooling's trees. A write
    whose result is the line already there must stay what it is on `main`:
    exit 0, no network call, origin untouched. Only `commit` publishes, and
    `CP_PUBLISH_AHEAD=1` EXPORTED changes nothing: the flag is the `commit`
    arm's alone (lane openRepoShape-2's mutant M01 read it from the
    environment and survived every other case)."""
    queued = box.queue("another lane's commit: retire the tool", delete=TOOL)
    head, origin = box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")
    extra = {"CP_PUBLISH_AHEAD": "1"} if exported else {}
    result = box.helper("replace-in-row", LANE, "seeded", "seeded", **extra)
    assert result.returncode == 0, result.stderr
    assert box.net_calls() == [], result.stderr
    assert (box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")) == (head, origin)
    assert box.origin_file(TOOL) == "#!/usr/bin/env bash\n"
    assert box.unpublished()[0].startswith(queued)
    assert f"nothing staged for {REGISTER} — no commit made" in result.stderr
    assert "stay local. `lanes-edit.sh commit` would publish all of them" in result.stderr
    assert "another lane's commits are its own to publish" in result.stderr


def test_the_publish_counts_what_its_list_leaves_out(box):
    """The list of commits being pushed shows ten and counts the rest."""
    for n in range(12):
        box.queue(f"handoff({PEER_LANE}@Eagle): stamp {n}", write=PEER_HANDOFF)
    result = box.helper("commit", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert "pushing the 12 local commit(s) origin/main does not have, up to" in result.stderr
    assert "  … and 2 more" in result.stderr, result.stderr
    assert box.wgit("rev-parse", "HEAD") == box.ogit("rev-parse", "main")


# ---- #214's adversarial check and its two reviews: three ordinary checkout
# states got a deletion past the first fence (`fab2cbc`), and a fourth was a
# race. The cases below pin each, and the fence's other rules beside them.

def _stranded_edit(box: Box) -> None:
    box.set_state(box.wip, LANE, "LIVE · edited by hand")
    box.wgit("commit", "-q", "-m", f"LANES({LANE}@Eagle): {SUBJECT}", "--", REGISTER)


def _refused_untouched(box: Box, result, head: str, origin: str) -> None:
    assert result.returncode == 2, result.stderr
    assert "nothing was pushed" in result.stderr, result.stderr
    assert box.net_calls() == [], result.stderr
    assert (box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")) == (head, origin)
    assert box.origin_file(TOOL) == "#!/usr/bin/env bash\n"


# ---- `commit` refuses a queue it cannot vouch for. Each setup leaves the
# stranded register edit queued with one more commit, or in one more checkout
# state, and returns the words the refusal must name. The last three are the
# adversarial check's bypasses, and each published a deletion at `fab2cbc`.

def _deletes_a_tool(box: Box) -> str:
    _stranded_edit(box)
    return f"  {box.queue('a queued commit', delete=TOOL)[:12]} D 000000 {TOOL}"


def _outside_lane_tooling(box: Box) -> str:
    _stranded_edit(box)
    (box.wip / "workspaces").mkdir(exist_ok=True)
    sha = box.queue("a queued commit", write="workspaces/repoP.yaml")
    return f"  {sha[:12]} A 100644 workspaces/repoP.yaml"


def _deletes_a_handoff(box: Box) -> str:
    _stranded_edit(box)
    return f"  {box.queue('a queued commit', delete=PEER_HANDOFF)[:12]} D 000000 {PEER_HANDOFF}"


def _type_change(box: Box) -> str:
    """A handoff turned into a symlink is a `T`, not a modification."""
    _stranded_edit(box)
    (box.wip / PEER_HANDOFF).unlink()
    (box.wip / PEER_HANDOFF).symlink_to(f"../{TOOL}")
    box.wgit("add", "--", PEER_HANDOFF)
    box.wgit("commit", "-q", "-m", "peer: the handoff becomes a symlink to the tool")
    return f"  {box.wgit('rev-parse', 'HEAD').strip()[:12]} T 120000 {PEER_HANDOFF}"


def _bytecode_in_handoffs(box: Box) -> str:
    """#162's list rides out of a publish no more than out of a commit."""
    _stranded_edit(box)
    (box.wip / "handoffs" / "__pycache__").mkdir()
    path = "handoffs/__pycache__/x.cpython-312.pyc"
    return f"  {box.queue('peer: bytecode beside a handoff', write=path)[:12]} A 100644 {path}"


def _merge_in_queue(box: Box) -> str:
    """BYPASS 1. `git log --name-status` prints no diff for a merge, so a
    deletion made while resolving one went out unread, by the straight push a
    peer's dirty file takes."""
    _stranded_edit(box)
    box.wgit("checkout", "-q", "-b", "side", "origin/main")
    box.queue(f"handoff({PEER_LANE}@Eagle): a side line", write=PEER_HANDOFF)
    box.wgit("checkout", "-q", "main")
    box.wgit("merge", "-q", "--no-ff", "--no-commit", "side")
    box.wgit("rm", "-q", "--", TOOL)
    box.wgit("commit", "-q", "-m", "Merge branch side")
    merge = box.wgit("rev-parse", "HEAD").strip()
    box.peer_edit_in_wip("a peer mid-write")
    return f"  {merge[:12]} is a merge commit"


def _head_off_branch(box: Box) -> str:
    """BYPASS 2. The fence read HEAD while the push sent `refs/heads/main`:
    with a deletion queued on local main and HEAD on a scratch branch holding a
    register edit, the fence saw only the edit."""
    box.queue("another lane: retire the tool", delete=TOOL)
    box.wgit("checkout", "-q", "-b", "scratch", "origin/main")
    _stranded_edit(box)
    return "HEAD is refs/heads/scratch, not refs/heads/main"


def _shadowing_origin_main(box: Box) -> str:
    """BYPASS 3. A local branch named `origin/main` shadowed the tracking ref."""
    sha = box.queue("peer: retire the tool", delete=TOOL)
    box.wgit("branch", "origin/main", "HEAD")
    _stranded_edit(box)
    return f"  {sha[:12]} D 000000 {TOOL}"


def _renames_out_of_lanes(box: Box) -> str:
    """SHOULD 4 (lane openRepoShape-2, 6243280936), THE RENAME GUARD. A log
    moved out of `lanes/` is a deletion there, and `--no-renames` names it so.
    Read with rename detection it would be one `R100` line instead."""
    log = f"lanes/log/{PEER_LANE}.md"
    box.write(box.wip, log, f"# {PEER_LANE}'s log\n")
    box.wgit("add", "--", log)
    box.wgit("commit", "-q", "-m", f"LANES({PEER_LANE}@Eagle): its log")
    box.wgit("push", "-q", "origin", "main")
    _stranded_edit(box)
    box.wgit("mv", log, f"scripts/{PEER_LANE}.md")
    box.wgit("commit", "-q", "-m", "peer: move a log out of lanes/")
    return f"  {box.wgit('rev-parse', 'HEAD').strip()[:12]} D 000000 {log}"


def _beside_the_register_directory(box: Box) -> str:
    """SHOULD 4, THE PREFIX GUARD. `lanes/` is a directory: `lanes-archive/`
    beside it is not the register's, though its name starts the same way."""
    _stranded_edit(box)
    (box.wip / "lanes-archive").mkdir()
    path = "lanes-archive/notes.md"
    return f"  {box.queue('peer: notes beside the register', write=path)[:12]} A 100644 {path}"


REFUSALS = {
    "deletes-a-tool": _deletes_a_tool,
    "outside-lane-tooling": _outside_lane_tooling,
    "deletes-a-handoff": _deletes_a_handoff,
    "type-change": _type_change,
    "bytecode-in-handoffs": _bytecode_in_handoffs,
    "merge-in-queue": _merge_in_queue,
    "head-off-branch": _head_off_branch,
    "shadowing-origin-main": _shadowing_origin_main,
    "renames-out-of-lanes": _renames_out_of_lanes,
    "beside-the-register-directory": _beside_the_register_directory,
}


@pytest.mark.parametrize("variant", list(REFUSALS))
def test_commit_refuses_a_queue_that_is_not_lane_toolings_to_publish(box, variant):
    """`commit` publishes register and handoff writes, by path and kind, and
    nothing else. One queued commit, or one checkout state, it cannot vouch for
    refuses the WHOLE publish with 2, names it, makes no network call and
    pushes nothing, not even the stranded register edit."""
    expect = REFUSALS[variant](box)
    head, origin = box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")
    result = box.helper("commit", SUBJECT)
    _refused_untouched(box, result, head, origin)
    assert expect in result.stderr, result.stderr
    assert "pushing the" not in result.stderr


@pytest.mark.parametrize("path", ["rebase", "straight"])
def test_the_push_sends_the_commit_the_fence_read(box, path):
    """THE RACE. Another lane commits a deletion into this shared checkout
    after the fence read the queue and before the push: the push sends the
    commit the fence read, `<sha>:refs/heads/main`, so the late commit stays
    local, on both roads out (the pull-and-rebase and the straight push a
    peer's dirty file forces)."""
    _stranded_edit(box)
    if path == "straight":
        box.peer_edit_in_wip("a peer mid-write")
    result = box.helper("commit", SUBJECT, FAKE_NET_RACE=TOOL)
    assert result.returncode == 0, result.stderr
    assert box.origin_file(TOOL) == "#!/usr/bin/env bash\n", result.stderr
    assert _row(LANE, "LIVE · edited by hand") in box.origin_file(REGISTER)
    late = box.wgit("log", "-1", "--format=%s", "HEAD").strip()
    assert late == "another lane, racing: retire the tool", late
    assert box.wgit("rev-parse", "HEAD~1") == box.ogit("rev-parse", "main")


def test_a_publish_the_pull_empties_says_so_and_sends_no_push(box):
    """Lane openRepoShape-2's trap (6243280936). The queue `commit` read can
    already be on origin by content, under other shas: here another workstation
    made the same edit. `pull --rebase` drops it, and the push that followed
    sent origin its own tip and printed "pushed". The re-read after the pull
    finds nothing left, says so, sends no push and exits 0."""
    _stranded_edit(box)
    box.set_state(box.peer, LANE, "LIVE · edited by hand")
    box.git("-C", str(box.peer), "commit", "-q", "-am", "the same edit, made elsewhere")
    box.git("-C", str(box.peer), "push", "-q", "origin", "main")
    origin = box.ogit("rev-parse", "main")

    result = box.helper("commit", SUBJECT)
    assert result.returncode == 0, result.stderr
    assert "pushing the 1 local commit(s) origin/main does not have" in result.stderr
    assert ("origin/main already holds every commit this publish listed: `pull --rebase` "
            "found each one there by content and dropped it") in result.stderr, result.stderr
    assert "pushed origin/" not in result.stderr, result.stderr
    calls = [f" {c} " for c in box.net_calls()]
    assert any(" pull " in c for c in calls), calls
    assert not any(" push " in c for c in calls), calls
    assert box.ogit("rev-parse", "main") == origin
    assert box.wgit("rev-parse", "HEAD") == origin
    assert box.origin_subjects().count("the same edit, made elsewhere") == 1


def test_a_lane_rename_is_refused_and_told_what_carries_it(box):
    """A DELIBERATE OVER-REFUSAL. A lane rename deletes its log to re-add it,
    and a deletion is the one change the fence never lets through: the refusal
    says so, and names what does carry it."""
    box.write(box.wip, "lanes/log/repocase-1.md", "# log\n")
    box.wgit("add", "--", "lanes/log/repocase-1.md")
    box.wgit("commit", "-q", "-m", "seed a log")
    box.wgit("push", "-q", "origin", "main")
    box.wgit("mv", "lanes/log/repocase-1.md", "lanes/log/repoCase-1.md")
    box.wgit("commit", "-q", "-m", "LANES(repoCase-1@Eagle): RENAMED lane repocase-1 → repoCase-1")
    head, origin = box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")

    result = box.helper("commit", SUBJECT)
    assert result.returncode == 2, result.stderr
    assert " D 000000 lanes/log/repocase-1.md" in result.stderr, result.stderr
    assert "A lane rename (Amendment 16) deletes and re-adds its log" in result.stderr
    assert "the next register write from this checkout carries it" in result.stderr
    assert box.net_calls() == []
    assert (box.wgit("rev-parse", "HEAD"), box.ogit("rev-parse", "main")) == (head, origin)


def test_the_fence_follows_the_registers_own_directory(box):
    """The register's directory is derived (`LANES_PREFIX`), never spelled
    `lanes/`: a register kept in `registry/` publishes its own stranded edit."""
    text = (box.wip / REGISTER).read_text(encoding="utf-8")
    box.write(box.wip, "registry/LANES.md", text)
    box.wgit("add", "--", "registry/LANES.md")
    box.wgit("commit", "-q", "-m", "a register kept elsewhere")
    box.wgit("push", "-q", "origin", "main")
    path = box.wip / "registry/LANES.md"
    path.write_text(text.replace(_row(LANE, "LIVE · seeded"), _row(LANE, "LIVE · edited by hand")),
                    encoding="utf-8")
    box.wgit("commit", "-q", "-m", f"LANES({LANE}@Eagle): {SUBJECT}", "--", "registry/LANES.md")

    result = box.helper("commit", SUBJECT, LANES_DIR=str(box.wip / "registry"))
    assert result.returncode == 0, result.stderr
    assert box.wgit("rev-parse", "HEAD") == box.ogit("rev-parse", "main")
    assert _row(LANE, "LIVE · edited by hand") in box.origin_file("registry/LANES.md")


def test_a_queued_commit_git_cannot_read_refuses(box):
    """FAIL CLOSED. `diff-tree --stdin` passes over a commit it cannot read and
    still exits 0, so a queued commit whose tree is missing must refuse, not
    read as a commit with nothing in it."""
    _stranded_edit(box)
    tree = box.wgit("rev-parse", "HEAD^{tree}").strip()
    box.queue(f"handoff({PEER_LANE}@Eagle): a line", write=PEER_HANDOFF)
    # The EARLIER queued commit's tree, so HEAD's own stays readable and the
    # refusal is the fence's, not the index check's.
    (box.wip / ".git" / "objects" / tree[:2] / tree[2:]).unlink()
    origin = box.ogit("rev-parse", "main")

    result = box.helper("commit", SUBJECT)
    assert result.returncode == 2, result.stderr
    assert "nothing was pushed" in result.stderr, result.stderr
    assert box.ogit("rev-parse", "main") == origin
