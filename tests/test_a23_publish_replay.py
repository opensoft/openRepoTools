# SPDX-License-Identifier: Apache-2.0
"""Amendment 23 S4: after the edit, commit by pathspec, push with no pull, and
read back — and a refused push replays the one edit.

`commit_publish` commits the write's own pathspecs, pushes `main` with no
pull, and fetches origin to confirm the commit is on it: confirmed is 0 and
`pushed`; a push that went (or timed out) and could not be confirmed is 3,
`pushed, not confirmed: <sha>`, never success. A push refused because origin
moved drops this write's commit (only while the branch still holds it, the
only unpublished commit S3 allows) and runs the verb again from the top on origin's new tip, so the
verb's own checks re-run on the new content: `claim`'s rescan (CLAIM-LOST, 7),
the one-match guard, `add-row`'s retirement and duplicate checks. Six attempts
in all; at the bound the commit is kept on HEAD and named (6), and every later
write from that checkout refuses on S3's unpushed row (ratified choices 4 and
5). `commit` carries a hand edit of the register across the fast-forward, and
with nothing of its own is the publish act: exempt from the unpushed row
alone, listing the queue by content before it pushes, and refusing (2) a stack
origin has moved past (Open question 2). `--sweep` is withdrawn (choice 9).

Origin's moves are made by a `LANES_GIT` hook (`tests/a23_box.py`'s `NET_GIT`)
at the moment of the push, so the race is exact and needs no timing. The
sandbox is the real `lanes-edit.sh`; nothing reaches a real remote.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from a23_box import REGISTER, RegisterBox, register_text
from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lanes-edit.sh is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

LANE = "repoS4-1"
NEIGHBOUR = "repoS4-2"
NEW_LANE = "repoS4-3"
UUID = "a23b4001-a2a2-4000-8000-a23b4001a2a2"
UUID2 = "a23b4002-a2a2-4000-8000-a23b4002a2a2"
UUID3 = "a23b4003-a2a2-4000-8000-a23b4003a2a2"
OBJ = "opensoft/repoS4#1"
HOME_FLAG = ("--home", "opensoft/repoS4")
ARCHIVE = "lanes/archive/LANES-retired.md"


def _row(lane: str, uuid: str = UUID, state: str = "LIVE · seeded") -> str:
    return (f"| `{lane}` | harness `{uuid}` | Eagle / test / tester | 2026-10-20T00:00Z "
            f"| — | handoffs/repoS4/{lane}.md | {state} |")


def _set(state: str) -> str:
    """How `set-row-state "LIVE · <text>"` reads in the row: the cell is
    stamped, `LIVE · <utc> · <text>`, so a case looks for ` · <text> |`."""
    return f" · {state.split(' · ', 1)[1]} |"


def _log_head(lane: str) -> str:
    return f"# lane {lane} — object log (lane-collision-protocol Amendment 7)\n"


class Box(RegisterBox):
    """Two adjacent rows, both lanes' logs, and a peer clone that lands commits
    on origin at the moment this write pushes."""

    def __init__(self, root: Path, **kw) -> None:
        root = Path(os.path.realpath(root))
        files = {
            REGISTER: register_text([_row(LANE), _row(NEIGHBOUR, uuid=UUID2)]),
            f"lanes/log/{LANE}.md": _log_head(LANE),
            f"lanes/log/{NEIGHBOUR}.md": _log_head(NEIGHBOUR),
            "handoffs/README.md": "# handoffs\n",
        }
        super().__init__(root, files, **kw)
        self.peer = self.clone(self.root / "peer")
        self.count = self.root / "hook.count"

    # ------------------------------------------------------------ the peer
    def peer_prepares(self, rel: str, old: str | None, new: str, message: str) -> None:
        """The peer clone commits one change WITHOUT pushing it: the hook
        pushes it at the moment this write pushes. `old` None writes `new`
        as the whole file."""
        self.git("-C", str(self.peer), "fetch", "-q", "origin")
        self.git("-C", str(self.peer), "merge", "-q", "--ff-only", "refs/remotes/origin/main")
        path = self.peer / rel
        if old is None:
            self.write(self.peer, rel, new)
        else:
            text = path.read_text(encoding="utf-8")
            assert text.count(old) == 1, (rel, old)
            path.write_text(text.replace(old, new), encoding="utf-8")
        self.commit(self.peer, message, rel)

    def race(self, *, times: int = 1, prepared: bool = False) -> None:
        """A hook that lands a peer's commit on origin before each of the
        first `times` pushes of the helper: the prepared one, or an empty
        commit of its own (a moved origin is all a lost race needs)."""
        peer = shlex.quote(str(self.peer))
        count = shlex.quote(str(self.count))
        land = (f"git -C {peer} push -q origin main\n" if prepared else
                f"git -C {peer} fetch -q origin\n"
                f"git -C {peer} merge -q --ff-only refs/remotes/origin/main\n"
                f"git -C {peer} commit -q --allow-empty -m \"a peer's commit lands first ($((n + 1)))\"\n"
                f"git -C {peer} push -q origin main\n")
        self.use_net(
            '[ "$1" = push ] || exit 0\n'
            f"n=$(cat {count} 2>/dev/null || echo 0)\n"
            f'[ "$n" -lt {times} ] || exit 0\n'
            f"echo $((n + 1)) > {count}\n"
            + land +
            "exit 0\n")

    def pushes(self) -> int:
        return self.net_ops().count("push")

    def subjects(self) -> list:
        return self.git("--git-dir", str(self.origin), "log", "--format=%s", "main").splitlines()

    def head(self, checkout: Path) -> str:
        return self.git("-C", str(checkout), "rev-parse", "HEAD").strip()

    def subject(self, checkout: Path, rev: str = "HEAD") -> str:
        return self.git("-C", str(checkout), "log", "-1", "--format=%s", rev).strip()

    def hand_edit(self, checkout: Path, lane: str = LANE, state: str = "LIVE · a hand edit") -> None:
        path = checkout / REGISTER
        text = path.read_text(encoding="utf-8")
        uuid = UUID if lane == LANE else UUID2
        old = _row(lane, uuid=uuid)
        assert old in text, text
        path.write_text(text.replace(old, _row(lane, uuid=uuid, state=state)), encoding="utf-8")


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def _settled(box: Box, c: Path) -> None:
    """What every write that ended must leave: the lock released and nothing
    of a replay's markers behind."""
    assert not box.lock_of(c).exists(), "the lock is released"


# ------------------------------------------------------------ the replay

def test_refused_push_replays_on_a_fresh_fast_forward(box: Box):
    """A peer's commit lands at the moment of the push: the push is refused,
    the write's commit is dropped, and the verb runs again on origin's new tip.
    One commit of the subject reaches origin, made on the new content."""
    c = box.seam()
    box.peer_prepares(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                      _row(NEIGHBOUR, uuid=UUID2, state="LIVE · the neighbour moved first"),
                      "a peer's row lands first")
    box.race(prepared=True)
    before = box.subjects()
    result = box.helper("set-row-state", LANE, "LIVE · the replayed write")
    assert result.returncode == 0, result.stderr
    err = result.stderr
    assert "push refused (attempt 1 of 6)" in err, err
    assert "pushed origin/main (attempt 2)" in err, err
    assert "pushed origin/main (attempt 1)" not in err, "attempt 1 never pushed it"
    register = box.origin_register()
    assert "LIVE · the neighbour moved first" in register, "the peer's row is kept"
    assert _set("LIVE · the replayed write") in register, "the write was made on the new tip"
    new = box.subjects()[: len(box.subjects()) - len(before)]
    assert len(new) == 2, new
    assert new[1] == "a peer's row lands first", new
    assert box.head(c) == box.origin_head(), "one commit of this write, and it is origin's tip"
    assert box.pushes() == 2
    assert box.unpublished(c) == []
    _settled(box, c)


def test_replay_through_a_routed_lane_checkout(box: Box):
    """The replay re-runs inside the lane's own checkout, with the lock it
    held adopted across the `exec`, and releases it at the end."""
    first = box.helper("set-row-state", LANE, "LIVE · the first write")
    assert first.returncode == 0, first.stderr
    lc = box.checkout(LANE)
    box.race()
    result = box.helper("set-row-state", LANE, "LIVE · the routed replay")
    assert result.returncode == 0, result.stderr
    assert "push refused (attempt 1 of 6)" in result.stderr
    assert _set("LIVE · the routed replay") in box.origin_register()
    assert box.head(lc) == box.origin_head()
    _settled(box, lc)


def _rival_claim_hook(box: Box) -> tuple:
    """A hook that, at this claim's first push, lands a rival lane's claim on
    the same object through a checkout of its own."""
    c2 = box.clone(box.root / "c2")
    env = {k: v for k, v in box.env.items()
           if k not in ("LANES_GIT", "FAKE_NET_LOG", "FAKE_NET_HOOK")}
    env.update({"LANES_REPO": str(c2), "LANES_LANE": NEIGHBOUR, "LANES_SESSION": UUID2})
    rc = box.root / "rival.rc"
    out = box.root / "rival.out"
    words = " ".join(shlex.quote(f"{k}={v}") for k, v in sorted(env.items()))
    cmd = " ".join(shlex.quote(a) for a in box.cmd("claim", OBJ, "--no-github", *HOME_FLAG))
    count = shlex.quote(str(box.count))
    box.use_net(
        '[ "$1" = push ] || exit 0\n'
        f"[ -e {count} ] && exit 0\n"
        f"echo 1 > {count}\n"
        f"rc=0; env -i {words} {cmd} > {shlex.quote(str(out))} 2>&1 || rc=$?\n"
        f"echo $rc > {shlex.quote(str(rc))}\n"
        "exit 0\n")
    return rc, out


def test_replay_reruns_claim_to_claim_lost_exit_7(box: Box):
    """Amendment 7(f) on the replay: a rival's CLAIMED landed first, so the
    re-run's rescan finds it before anything else, and this claim is
    CLAIM-LOST (7). Its CLAIMED commit was dropped, so origin gets the
    CLAIM-LOST line alone: "this one wrote nothing" is true again."""
    c = box.seam()
    rc, out = _rival_claim_hook(box)
    result = box.helper("claim", OBJ, "--no-github", *HOME_FLAG,
                        LANES_LANE=LANE, LANES_SESSION=UUID)
    assert rc.read_text(encoding="utf-8").strip() == "0", out.read_text(encoding="utf-8")
    assert result.returncode == 7, result.stderr
    assert "push refused (attempt 1 of 6)" in result.stderr
    assert "CLAIM LOST" in result.stderr
    mine = box.origin_file(f"lanes/log/{LANE}.md")
    assert f"CLAIM-LOST — lane {LANE}" in mine, mine
    assert f"CLAIMED — lane {LANE}" not in mine, "the dropped CLAIMED never reached origin"
    assert f"CLAIMED — lane {NEIGHBOUR}" in box.origin_file(f"lanes/log/{NEIGHBOUR}.md")
    assert box.unpublished(c) == []
    _settled(box, c)


def test_replay_reruns_the_one_match_guard(box: Box):
    """A peer rewrote this lane's row at the moment of the push, so the text
    `replace-in-row` replaces is no longer there. The re-run's own guard
    refuses on the new content, with nothing of this write on origin."""
    c = box.seam()
    box.peer_prepares(REGISTER, _row(LANE), _row(LANE, state="LIVE · rewritten by a peer"),
                      "a peer rewrites the row")
    box.race(prepared=True)
    result = box.helper("replace-in-row", LANE, "seeded", "reseeded", "the guarded replace")
    assert result.returncode == 2, result.stderr
    assert "push refused (attempt 1 of 6)" in result.stderr
    assert "'seeded' occurs 0 times" in result.stderr, result.stderr
    register = box.origin_register()
    assert "LIVE · rewritten by a peer" in register
    assert "reseeded" not in register
    assert box.head(c) == box.origin_head(), "the dropped commit is gone and nothing is left ahead"
    assert box.unpublished(c) == []
    _settled(box, c)


@pytest.mark.parametrize("peer", ["retires-it", "adds-it"])
def test_add_row_replay_refuses_on_peer_retirement(box: Box, peer: str):
    """`add-row`'s checks run before the lock, so a peer's retirement of the
    name (Amendment 19(b)) or its own row for it (15(a)) that lands at the
    moment of the push is met by the re-run: refused (2), nothing written —
    where the old rescan after a `pull --rebase` left two local commits."""
    c = box.seam()
    row = _row(NEW_LANE, uuid=UUID3)
    if peer == "retires-it":
        box.peer_prepares(ARCHIVE, None,
                          "# retired rows\n\n| lane | session id |\n|---|---|\n"
                          f"| `{NEW_LANE}` | harness `{UUID3}` |\n", "a peer retires the name")
        words = f"lane '{NEW_LANE}' is RETIRED"
    else:
        box.peer_prepares(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                          _row(NEIGHBOUR, uuid=UUID2) + "\n" + row, "a peer adds the row")
        words = f"lane '{NEW_LANE}' already has a row"
    box.race(prepared=True)
    result = box.helper("add-row", row)
    assert result.returncode == 2, result.stderr
    assert "push refused (attempt 1 of 6)" in result.stderr
    assert words in result.stderr, result.stderr
    assert box.origin_register().count(f"`{NEW_LANE}`") == (1 if peer == "adds-it" else 0)
    assert box.head(c) == box.origin_head()
    assert box.unpublished(c) == []
    _settled(box, c)


# ------------------------------------------------------------ the bound

def test_bound_keeps_the_commit_on_head_exit_6_and_next_write_refuses(box: Box):
    """Six refused pushes: the sixth does not reset. The commit is kept on
    HEAD and named (6), and the next write from that checkout refuses on S3's
    unpushed row until the lane publishes or archives it (choice 5)."""
    c = box.seam()
    box.race(times=99)
    result = box.helper("set-row-state", LANE, "LIVE · six times beaten")
    assert result.returncode == 6, result.stderr
    err = result.stderr
    for n in range(1, 6):
        assert f"push refused (attempt {n} of 6)" in err, (n, err)
    assert "push refused (attempt 6 of 6)" not in err
    sha = box.head(c)
    assert f"could not push origin/main after six attempts; the commit is local and kept on HEAD: {sha}" in err
    assert f"git -C {c} show {sha}" in err
    assert box.pushes() == 6
    assert _set("LIVE · six times beaten") in (c / REGISTER).read_text(encoding="utf-8")
    assert _set("LIVE · six times beaten") not in box.origin_register()
    assert [line.split()[1] for line in box.unpublished(c)] == [sha]
    _settled(box, c)
    del box.env["FAKE_NET_HOOK"]
    after = box.helper("log", "NOTED", f"lane:{LANE}", "a later write", *HOME_FLAG,
                       LANES_LANE=LANE, LANES_SESSION=UUID)
    assert after.returncode == 2, after.stderr
    assert "1 unpublished commit(s)" in after.stderr
    assert f"+ {sha}" in after.stderr
    assert box.head(c) == sha


def test_push_refused_with_origin_unmoved_is_kept_exit_6(box: Box):
    """A refusal that is no lost race — origin did not move, so a replay would
    meet it again: the commit is kept on HEAD and named (6), with one push."""
    c = box.seam()
    box.use_net('[ "$1" = push ] && { echo "remote: refusing this push" >&2; exit 1; }\nexit 0\n')
    tip = box.origin_head()
    result = box.helper("set-row-state", LANE, "LIVE · refused for another reason")
    assert result.returncode == 6, result.stderr
    sha = box.head(c)
    assert f"refused with origin/main unmoved" in result.stderr
    assert f"kept on HEAD: {sha}" in result.stderr
    assert "push refused (attempt" not in result.stderr, "no replay"
    assert box.pushes() == 1
    assert box.origin_head() == tip
    _settled(box, c)


def _refuse_push_after(box: Box, body: str) -> str:
    """A push hook that runs `body` (another writer in this write's
    checkout, with no lock) while the push is in flight, then refuses the
    push with origin unmoved, as a hook or a protected branch would. Returns
    origin's tip, which nothing moves."""
    box.use_net('[ "$1" = push ] || exit 0' + "\n" + body +
                'echo "remote: refusing this push" >&2; exit 1' + "\n")
    return box.origin_head()


def test_a_push_refused_with_origin_unmoved_names_a_commit_on_top_exit_6(box: Box):
    """w2a-c6's note on slice 1b: the refusal with origin unmoved said "the
    commit is local and kept on HEAD: <sha>" without reading HEAD, the shape
    slice 2a's A41 took out of its S4.4. An unlocked writer's stamp committed
    on top while the push was in flight then sat at HEAD, and the words named
    this write's commit as HEAD. Now HEAD is read first, and `cp_not_head`'s
    words name both, kept and neither dropped, with no replay (6)."""
    c = box.seam()
    cq = shlex.quote(str(c))
    tip = _refuse_push_after(box,
        f"printf 'stamp' > {cq}/handoffs/stamp.md" + "\n" +
        f"git -C {cq} add -- handoffs/stamp.md" + "\n" +
        f"git -C {cq} commit -q -m 'handoff(repoS4-2@Eagle): a stamp from an unlocked writer' -- handoffs/stamp.md" + "\n")
    result = box.helper("set-row-state", LANE, "LIVE · refused, a stamp on top")
    assert result.returncode == 6, result.stderr
    err = result.stderr
    assert "refused with origin/main unmoved (no lost race: a replay would meet the same refusal)" in err
    assert "is no longer HEAD, so it is not replayed" in err
    assert "in this checkout while its push was in flight." in err, "no drop is offered as the reason"
    assert "kept on HEAD: " not in err, "HEAD is not this write's commit"
    assert box.subject(c) == "handoff(repoS4-2@Eagle): a stamp from an unlocked writer"
    assert box.subject(c, "HEAD~1").startswith(f"LANES({LANE}@"), "this write's commit is under it"
    mine = _mine_named_on_head(box, c, err)
    assert mine and all(on for _, on in mine), mine
    assert "push refused (attempt" not in err, "no replay"
    assert box.pushes() == 1
    assert box.origin_head() == tip
    assert len(box.unpublished(c)) == 2, "both kept on HEAD, for the publish act"
    _settled(box, c)


def test_a_push_refused_with_origin_unmoved_names_a_rewritten_commit_exit_6(box: Box):
    """w2a-c6's note, its second case: another writer rewrote this write's
    commit while the push was in flight (here an amend, a rewrite that keeps
    the tree). The refusal said "kept on HEAD: <sha>" of a sha HEAD no longer
    holds. Now it says the commit was rewritten, in `cp_rewritten`'s words,
    names no commit of this write's as on HEAD, and replays nothing (6)."""
    c = box.seam()
    cq = shlex.quote(str(c))
    tip = _refuse_push_after(box,
        f"git -C {cq} commit -q --amend -m 'an unlocked writer reworded it'" + "\n")
    result = box.helper("set-row-state", LANE, "LIVE · refused, then rewritten")
    assert result.returncode == 6, result.stderr
    err = result.stderr
    assert "refused with origin/main unmoved (no lost race: a replay would meet the same refusal)" in err
    assert "rewrote this write's commit" in err
    assert "kept on HEAD" not in err, "nothing of this write's is on HEAD under its own sha"
    named = re.search(r"so it is not replayed: ([0-9a-f]{40}) ", err)
    assert named, err
    assert box.git("-C", str(c), "log", "-1", "--format=%s", named.group(1)).startswith(f"LANES({LANE}@")
    on_head = subprocess.run(["git", "-C", str(c), "merge-base", "--is-ancestor", named.group(1), "HEAD"],
                             env=box.env, capture_output=True, check=False)
    assert on_head.returncode == 1, "the named commit is not on HEAD"
    assert box.subject(c) == "an unlocked writer reworded it"
    assert "push refused (attempt" not in err, "no replay"
    assert box.pushes() == 1
    assert box.origin_head() == tip
    _settled(box, c)


def test_replay_refused_by_a_change_in_the_way_keeps_the_commit_exit_6(box: Box):
    """The drop never moves the tree over an uncommitted change: a hand edit of
    the register made while the push was in flight stops the replay, and the
    commit is kept on HEAD and named (6), with the edit untouched."""
    c = box.seam()
    peer = shlex.quote(str(box.peer))
    reg = shlex.quote(str(c / REGISTER))
    count = shlex.quote(str(box.count))
    box.use_net('[ "$1" = push ] || exit 0\n'
                f"[ -e {count} ] && exit 0\n"
                f"echo 1 > {count}\n"
                f"git -C {peer} commit -q --allow-empty -m \"a peer's commit lands first (1)\"\n"
                f"git -C {peer} push -q origin main\n"
                f"printf 'a person types here\\n' >> {reg}\n"
                "exit 0\n")
    result = box.helper("set-row-state", LANE, "LIVE · in the way")
    assert result.returncode == 6, result.stderr
    sha = box.head(c)
    assert "could not be dropped to replay it" in result.stderr
    assert f"kept on HEAD: {sha}" in result.stderr
    assert (c / REGISTER).read_text(encoding="utf-8").endswith("a person types here\n")
    assert box.subject(c) != "a peer's commit lands first (1)"
    _settled(box, c)


# ------------------------------------------------------------ the read-back

def test_unconfirmed_push_exits_3(box: Box):
    """The push lands and the read-back's fetch fails: 3, `pushed, not
    confirmed: <sha>`, never success, and the commit kept on HEAD. The next
    write's S3 finds it on origin by content and goes on."""
    c = box.seam()
    mark = shlex.quote(str(box.root / "pushed"))
    box.use_net(f'[ "$1" = push ] && {{ touch {mark}; exit 0; }}\n'
                f'[ "$1" = fetch ] && [ -e {mark} ] && {{ echo "fatal: the read-back cannot reach origin" >&2; exit 128; }}\n'
                "exit 0\n")
    result = box.helper("set-row-state", LANE, "LIVE · sent and not confirmed")
    assert result.returncode == 3, result.stderr
    sha = box.head(c)
    assert f"pushed, not confirmed: {sha}" in result.stderr
    assert "the read-back fetch of origin main failed" in result.stderr
    assert "pushed origin/main (attempt" not in result.stderr, "never the success line"
    assert box.origin_head() == sha, "it did land: exit 3 never says it did not"
    del box.env["FAKE_NET_HOOK"]
    nxt = box.helper("log", "NOTED", f"lane:{LANE}", "the next write", *HOME_FLAG,
                     LANES_LANE=LANE, LANES_SESSION=UUID)
    assert nxt.returncode == 0, nxt.stderr
    _settled(box, c)


@pytest.mark.parametrize("landed", [True, False], ids=["landed", "lost"])
def test_timed_out_push_is_read_back(box: Box, landed: bool):
    """A push that times out is not a failure: the read-back decides. Landed
    is 0 and confirmed; not landed is 3, naming the timeout — and never a
    replay, because a hung push may still land."""
    c = box.seam()
    box.env["LANES_GIT_TIMEOUT"] = "4"
    land = 'shift; git "$@"\n' if landed else ""
    box.use_net('[ "$1" = push ] || exit 0\n' + land + "exec sleep 30 </dev/null >/dev/null 2>&1\n")
    result = box.helper("set-row-state", LANE, "LIVE · a hung push")
    sha = box.head(c)
    if landed:
        assert result.returncode == 0, result.stderr
        assert "pushed origin/main (attempt 1)" in result.stderr
        assert box.origin_head() == sha
    else:
        assert result.returncode == 3, result.stderr
        assert f"pushed, not confirmed: {sha}" in result.stderr
        assert "the push timed out after 4s" in result.stderr
        assert "origin/main, read back, does not hold it" in result.stderr
    assert box.pushes() == 1
    assert "push refused (attempt" not in result.stderr
    _settled(box, c)


def test_a_push_git_called_failed_that_landed_under_a_peers_commit_is_written_once(box: Box):
    """293 of lane openRepoTools-3's review of #307 (its E17): the read-back
    after a refused push ("it may have landed", decision 5) had no case, and
    its mutant PB-2 (`0) cp_pushed "$cp_sha"; return 0 ;;` made `0) : ;;`)
    survived all 80 cases of the replay and #194 modules. A `log NOTED`
    whose push lands, a peer's commit lands on top of it at once, and git
    still reports the push as failed ("the remote end hung up"): origin holds
    this write's commit, so it is pushed (0), and the line is in the
    append-only log ONCE. Without the read-back, origin's tip is not under
    this write's commit, so it replays, and the line is written twice."""
    c = box.seam()
    peer = shlex.quote(str(box.peer))
    box.use_net('if [ "$1" = push ]; then' + "\n" +
                '  shift; git "$@" || exit $?' + "\n" +
                f"  git -C {peer} fetch -q origin" + "\n" +
                f"  git -C {peer} merge -q --ff-only refs/remotes/origin/main" + "\n" +
                f"  git -C {peer} commit -q --allow-empty -m \"a peer's commit lands on top at once\"" + "\n" +
                f"  git -C {peer} push -q origin main" + "\n" +
                '  echo "fatal: the remote end hung up unexpectedly" >&2; exit 1' + "\n" +
                "fi" + "\n" + "exit 0" + "\n")
    text = "a note whose push landed and was called failed"
    result = box.helper("log", "NOTED", f"lane:{LANE}", text, *HOME_FLAG,
                        LANES_LANE=LANE, LANES_SESSION=UUID)
    assert result.returncode == 0, result.stderr
    assert "pushed origin/main (attempt 1)" in result.stderr
    assert "push refused (attempt" not in result.stderr, "it landed, so nothing is replayed"
    assert box.origin_file(f"lanes/log/{LANE}.md").count(text) == 1, "the append-only log has it once"
    assert box.subjects()[0] == "a peer's commit lands on top at once"
    assert box.pushes() == 1
    assert box.unpublished(c) == []
    _settled(box, c)


def _another_writer(c: Path, state: str) -> str:
    """What an unlocked writer in `c` does while a push is in flight, as the
    lines of a hook: a stamp committed on top of this write's commit, or an
    amend that rewrites it (a rebase's effect, with the tree kept)."""
    cq = shlex.quote(str(c))
    if state == "on-top":
        return (f"printf 'stamp' > {cq}/handoffs/stamp.md" + "\n" +
                f"git -C {cq} add -- handoffs/stamp.md" + "\n" +
                f"git -C {cq} commit -q -m 'handoff(repoS4-2@Eagle): a stamp from an unlocked writer' -- handoffs/stamp.md" + "\n")
    return f"git -C {cq} commit -q --amend -m 'an unlocked writer reworded it'" + "\n"


@pytest.mark.parametrize("state", ["on-top", "rewritten"])
def test_an_unconfirmed_push_reads_head_before_it_says_kept_on_head_exit_3(box: Box, state: str):
    """rv1b-c3's neighbour of NIT 4, found by w1b-c6 with item 1: the exit-3
    die said "the commit is kept on HEAD" without reading HEAD. Another
    writer's stamp committed on top while the push was in flight sat at HEAD,
    and an amend took this write's commit off the branch altogether. The push
    landed and the read-back's fetch fails, so the number stays 3 (the one
    cause the table gives it: pushed, not confirmed), and HEAD is read first:
    `cp_not_head`'s words for a commit on top, `cp_rewritten`'s for a rewrite,
    each with this refusal's own clause in place of "origin moved"."""
    c = box.seam()
    mark = shlex.quote(str(box.root / "pushed"))
    box.use_net('if [ "$1" = push ]; then\n'
                '  shift; git "$@" || exit $?\n' + _another_writer(c, state) +
                f"  touch {mark}; exit 97\n"
                "fi\n"
                f'[ "$1" = fetch ] && [ -e {mark} ] && {{ echo "fatal: the read-back cannot reach origin" >&2; exit 128; }}\n'
                "exit 0\n")
    result = box.helper("set-row-state", LANE, "LIVE · sent, then something moved under it")
    assert result.returncode == 3, result.stderr
    err = result.stderr
    named = re.search(r"pushed, not confirmed: ([0-9a-f]{40}) ", err)
    assert named, err
    sha = named.group(1)
    assert box.origin_head() == sha, "it did land: exit 3 never says it did not"
    assert "the read-back fetch of origin main failed" in err
    assert "pushed origin/main (attempt" not in err, "never the success line"
    assert "the commit is kept on HEAD, and this is never reported as success" not in err, \
        "the old words claim a HEAD nobody read"
    assert "push refused (attempt" not in err, "no replay"
    on_head = subprocess.run(["git", "-C", str(c), "merge-base", "--is-ancestor", sha, "HEAD"],
                             env=box.env, capture_output=True, check=False).returncode
    if state == "on-top":
        assert on_head == 0, "this write's commit is under the stamp"
        assert f"HEAD is {box.head(c)}, not this write's commit {sha}" in err, err
        assert "in this checkout while its push was in flight." in err
        assert "it and the commit on top of it are kept on HEAD" in err
        assert len(box.unpublished(c)) == 1, "the stamp is not on origin; this write's commit is"
    else:
        assert on_head == 1, "this write's commit is not on HEAD"
        assert "rewrote this write's commit" in err
        assert "kept on HEAD" not in err, "nothing of this write's is on HEAD under its own sha"
    assert box.pushes() == 1
    _settled(box, c)


# ------------------------------------------------------------ `commit`'s carry

def test_commit_carries_a_hand_edit_across_the_ff(box: Box):
    """Choice 9: `commit` is the one writer a pending register hand edit does
    not refuse. It sets the edit aside, fast-forwards, applies it again, and
    publishes it on origin's tip."""
    c = box.seam()
    box.peer_edits(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                   _row(NEIGHBOUR, uuid=UUID2, state="LIVE · moved on origin"))
    box.hand_edit(c)
    result = box.helper("commit", "the hand edit", LANES_LANE=LANE)
    assert result.returncode == 0, result.stderr
    assert "carried the hand edit of lanes/LANES.md across the fast-forward" in result.stderr
    assert "anchored by those lines alone" in result.stderr, "the neighbour's row is the edit's context"
    register = box.origin_register()
    assert "LIVE · moved on origin" in register
    assert "LIVE · a hand edit" in register
    assert box.head(c) == box.origin_head()
    assert box.git("-C", str(c), "status", "--porcelain").strip() == ""
    saved = list((c / ".git" / "lanes-edit").glob("hand-edit-*.diff"))
    assert len(saved) == 1
    assert "a hand edit" in saved[0].read_text(encoding="utf-8")
    _settled(box, c)


def test_commit_keeps_the_diff_when_it_no_longer_applies(box: Box):
    """The hand edit and origin changed the same row: the edit no longer
    applies after the fast-forward, so `commit` refuses (2), names the file
    that keeps it, and leaves the register at origin's version."""
    c = box.seam()
    box.peer_edits(REGISTER, _row(LANE), _row(LANE, state="LIVE · origin's own edit"))
    box.hand_edit(c)
    tip = box.origin_head()
    result = box.helper("commit", "the hand edit", LANES_LANE=LANE)
    assert result.returncode == 2, result.stderr
    saved = list((c / ".git" / "lanes-edit").glob("hand-edit-*.diff"))
    assert len(saved) == 1
    assert "no longer applies" in result.stderr
    assert str(saved[0]) in result.stderr
    assert "LIVE · a hand edit" in saved[0].read_text(encoding="utf-8")
    assert (c / REGISTER).read_text(encoding="utf-8") == box.origin_register()
    assert box.origin_head() == tip, "nothing was pushed"
    assert box.git("-C", str(c), "status", "--porcelain").strip() == ""
    _settled(box, c)


def test_commit_refuses_an_insertion_whose_context_moved(box: Box):
    """A hand edit that only INSERTS a line has no line of its own to anchor
    it: where origin changed the line beside it, it is refused (2) and kept,
    never dropped in at a line number."""
    c = box.seam()
    box.peer_edits(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                   _row(NEIGHBOUR, uuid=UUID2, state="LIVE · moved on origin"))
    path = c / REGISTER
    path.write_text(path.read_text(encoding="utf-8").replace(
        _row(LANE) + "\n", _row(LANE) + "\n| `repoS4-9` | a line typed in by hand |\n"), encoding="utf-8")
    tip = box.origin_head()
    result = box.helper("commit", "an inserted line", LANES_LANE=LANE)
    assert result.returncode == 2, result.stderr
    assert "no longer applies" in result.stderr
    assert "anchored by those lines alone" not in result.stderr
    assert box.origin_head() == tip
    _settled(box, c)


TWICE = "LANDING — lane repoS4-7, session x@Eagle, 2026-10-20T00:00:00Z, PR #7 into main"
LANDED_TWICE = "LANDED — lane repoS4-7, session x@Eagle, 2026-10-20T00:10:00Z, PR #7 → 9bf26db"
EDITED = "LANDED — the second copy, edited by hand"


@pytest.mark.parametrize("dup", ["a-repeated-line", "a-blank-line",
                                 "a-copy-a-peer-changed", "the-registers-own-shape",
                                 "the-registers-own-shape-staged"])
def test_commit_refuses_a_hand_edit_whose_line_occurs_twice_on_origin(box: Box, dup: str):
    """292 of lane openRepoTools-3's review of #307, its answer to Q3: B22
    retried a failed carry with `git apply -C0` wherever every hunk removes
    a line, and `-C0` drops the context and edits the first copy of that line
    it finds. A hand edit of the SECOND of two identical lines, with origin
    changing the line after it, was pushed onto the first copy (0), "anchored
    by those lines alone"; a replaced blank line, of which the register has
    dozens, the same. Now `-C0` is tried only where every line the edit
    replaces occurs once in origin's version; otherwise the edit is refused
    (2), kept in its file and named, and the register is left at origin's.

    341 of lane 3's re-check of #307: the count was asked of origin's version
    alone. A line twice in the version the edit was made on is once on origin
    where a peer changed or removed the copy the person edited, and `-C0` then
    edited the copy nobody touched: a correction made after a peer changed
    that copy left both values on origin (0), where decision 9 refuses; and
    the register's own shape, a LANDING then two identical LANDED lines, each
    side removing one LANDED, kept the LANDING with no LANDED (0), which
    reopens Rule 6's hold. The line must now occur once in both versions.

    382 of lane 3's re-check at `15e71d9`: the version the edit was made on is
    HEAD's blob, the same version the kept diff is taken against (`diff
    HEAD`), never the index's. A hand edit that is also STAGED is the same
    edit: read from the index, the base would be the edited version, the
    LANDED line would count once there, and the register's own shape would
    be pushed onto the wrong copy again (`-staged`)."""
    line = "" if dup == "a-blank-line" else TWICE
    after = "| `repoS4-8` | the line after the second copy |"
    if dup.startswith("the-registers-own-shape"):
        block = TWICE + "\n" + LANDED_TWICE + "\n" + LANDED_TWICE + "\n" + after
    else:
        block = line + "\n" + "| `repoS4-6` | a line between the copies |" + "\n" + line + "\n" + after
    box.peer_edits(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                   _row(NEIGHBOUR, uuid=UUID2) + "\n" + block, "the same line twice")
    c = box.seam()
    path = c / REGISTER
    text = path.read_text(encoding="utf-8")
    if dup.startswith("the-registers-own-shape"):
        second = text.rindex("\n" + LANDED_TWICE + "\n" + after) + 1
        path.write_text(text[:second] + text[second + len(LANDED_TWICE) + 1:], encoding="utf-8")
        if dup.endswith("-staged"):   # the diff is HEAD's, not the index's: a staged edit is the same edit
            box.git("-C", str(c), "add", "--", REGISTER)
        box.peer_edits(REGISTER, LANDED_TWICE + "\n" + LANDED_TWICE + "\n" + after,
                       LANDED_TWICE + "\n" + after, "a peer removes one LANDED line too")
        kept = "\n-" + LANDED_TWICE + "\n"
    else:
        second = text.rindex("\n" + line + "\n" + after) + 1
        path.write_text(text[:second] + EDITED + text[second + len(line):], encoding="utf-8")
        if dup == "a-copy-a-peer-changed":
            box.peer_edits(REGISTER, "\n" + line + "\n" + after,
                           "\nLANDED — the second copy, as a peer changed it\n" + after,
                           "origin changes the second copy itself")
        else:
            box.peer_edits(REGISTER, after, "| `repoS4-8` | the line after it, changed on origin |",
                           "origin changes the line after the second copy")
        kept = EDITED
    tip = box.origin_head()
    result = box.helper("commit", "the second copy, by hand", LANES_LANE=LANE)
    assert result.returncode == 2, (result.stderr, box.origin_register())
    err = result.stderr
    assert "no longer applies" in err
    assert "occurs more than once" in err, err
    assert "anchored by those lines alone" not in err
    saved = list((c / ".git" / "lanes-edit").glob("hand-edit-*.diff"))
    assert len(saved) == 1 and str(saved[0]) in err, "the edit is kept and named"
    assert kept in saved[0].read_text(encoding="utf-8")
    assert (c / REGISTER).read_text(encoding="utf-8") == box.origin_register()
    assert box.origin_head() == tip, "nothing was pushed"
    assert box.git("-C", str(c), "status", "--porcelain").strip() == ""
    _settled(box, c)


def test_commit_replay_keeps_the_hand_edit(box: Box):
    """`commit`'s edit is the hand edit, which no argv makes again: a refused
    push gives it back to the working tree, and the re-run carries it onto
    origin's new tip — it is never dropped with the commit."""
    c = box.seam()
    box.peer_prepares(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                      _row(NEIGHBOUR, uuid=UUID2, state="LIVE · landed mid-push"),
                      "a peer's row lands first")
    box.race(prepared=True)
    box.hand_edit(c)
    result = box.helper("commit", "the hand edit", LANES_LANE=LANE)
    assert result.returncode == 0, result.stderr
    assert "left in the working tree as the hand edit it was" in result.stderr
    register = box.origin_register()
    assert "LIVE · landed mid-push" in register
    assert "LIVE · a hand edit" in register
    assert box.head(c) == box.origin_head()
    assert box.git("-C", str(c), "status", "--porcelain").strip() == ""
    _settled(box, c)


# ------------------------------------------------------------ the publish act

def _queue(box: Box, c: Path, n: int = 1) -> list:
    """`n` register and handoff commits made here and never pushed."""
    shas = []
    for i in range(n):
        if i == 0:
            box.hand_edit(c, state=f"LIVE · queued {i}")
            box.commit(c, f"LANES({LANE}@Eagle): queued {i}", REGISTER)
        else:
            box.write(c, f"handoffs/repoS4/q{i}.md", f"queued {i}\n")
            box.commit(c, f"LANES({LANE}@Eagle): queued {i}", f"handoffs/repoS4/q{i}.md")
        shas.append(box.head(c))
    return shas


def _detached(box: Box, c: Path):
    box.git("-C", str(c), "checkout", "-q", "--detach")
    return {}, "HEAD is detached, not refs/heads/main"


def _fetch_fails(box: Box, c: Path):
    box.use_net('[ "$1" = fetch ] && { echo "fatal: unable to access origin" >&2; exit 128; }\nexit 0\n')
    return {}, "the fetch of origin main failed"


def _no_fetch(box: Box, c: Path):
    return {"LANES_NO_FETCH": "1"}, "LANES_NO_FETCH=1 is set"


def _cherry_pick(box: Box, c: Path):
    (c / ".git" / "CHERRY_PICK_HEAD").write_text(box.head(c) + "\n", encoding="utf-8")
    return {}, "a cherry-pick is in progress"


PUBLISH_ROWS = {"detached": _detached, "fetch-fails": _fetch_fails,
                "no-fetch": _no_fetch, "cherry-pick": _cherry_pick}


@pytest.mark.parametrize("row", [None, *PUBLISH_ROWS], ids=["unpushed-only", *PUBLISH_ROWS])
def test_publish_act_is_exempt_from_unpushed_only(box: Box, row):
    """`commit` with nothing of its own publishes the queue S3 would refuse a
    write over (#194's remedy 1). That is its ONE exemption: every other row
    still refuses it, with nothing pushed."""
    c = box.seam()
    shas = _queue(box, c)
    extra, words = ({}, None) if row is None else PUBLISH_ROWS[row](box, c)
    tip = box.origin_head()
    result = box.helper("commit", "publish the queue", LANES_LANE=LANE, **extra)
    if row is None:
        assert result.returncode == 0, result.stderr
        assert box.origin_head() == shas[-1]
        assert "pushed origin/main (attempt 1)" in result.stderr
        assert box.unpublished(c) == []
    else:
        assert result.returncode == 2, result.stderr
        assert words in result.stderr
        assert "Nothing was written." in result.stderr
        assert box.origin_head() == tip
    _settled(box, c)


def test_publish_act_refused_by_staged_entry(box: Box):
    """A staged entry the publish did not make refuses it (S3's staged row):
    a queue is never published with someone's half-made commit beside it."""
    c = box.seam()
    _queue(box, c)
    box.write(c, "handoffs/README.md", "# handoffs\na peer's staged line\n")
    box.git("-C", str(c), "add", "--", "handoffs/README.md")
    before = box.snapshot(c)
    result = box.helper("commit", "publish the queue", LANES_LANE=LANE)
    assert result.returncode == 2, result.stderr
    assert "staged entries this write did not make: handoffs/README.md" in result.stderr
    assert box.snapshot(c) == before
    _settled(box, c)


def test_publish_act_lists_cherry_before_push(box: Box):
    """The queue is listed by content — `git cherry -v`'s `+` lines — before
    anything is pushed, so the person sees what is being published."""
    c = box.seam()
    shas = _queue(box, c, n=2)
    result = box.helper("commit", "publish the queue", LANES_LANE=LANE)
    assert result.returncode == 0, result.stderr
    err = result.stderr
    listed = err.index("the 2 commit(s) origin/main lacks by content, listed before anything is pushed")
    pushing = err.index("pushing the 2 local commit(s) origin/main does not have")
    for i, sha in enumerate(shas):
        at = err.index(f"+ {sha} LANES({LANE}@Eagle): queued {i}")
        assert listed < at < pushing, (i, err)
    assert box.origin_head() == shas[-1]
    _settled(box, c)


def test_publish_act_on_moved_origin_refuses(box: Box):
    """Open question 2: the publish act makes only a fast-forward push. Where
    origin has moved past the stack it refuses (2), naming S6.3's archive and
    then `reset --keep`, and pushes nothing."""
    c = box.seam()
    box.use_net()
    shas = _queue(box, c)
    box.peer_pushes("handoffs/repoS4/elsewhere.md", "a peer's file\n")
    tip = box.origin_head()
    result = box.helper("commit", "publish the queue", LANES_LANE=LANE)
    assert result.returncode == 2, result.stderr
    err = result.stderr
    assert "origin/main has moved past the local commits" in err
    assert "only a fast-forward push" in err
    assert "refs/heads/archive/" in err
    assert f"git -C {c} reset --keep refs/remotes/origin/main" in err
    assert "push" not in box.net_ops()
    assert box.origin_head() == tip
    assert box.head(c) == shas[-1]
    _settled(box, c)


def test_the_publish_acts_moved_origin_recovery_names_the_lane_and_stops_first(box: Box):
    """NIT 294 of lane openRepoTools-3's review of #307 (its E13), and its
    answer to Q2: the publish act's refusal over a stack origin has moved
    past printed a literal `archive/<lane>-stranded-…` where S3's own refusal
    fills the lane in, and it lacked the line S3, S6.3 and the manual give
    before the archive: if any `+` line is not your own write, STOP. Now the
    lane is filled in, the list and the stop line come first, and the reset
    names `refs/remotes/origin/main` in full."""
    c = box.seam()
    box.use_net()
    _queue(box, c)
    box.peer_pushes("handoffs/repoS4/elsewhere.md", "a peer's file" + "\n")
    result = box.helper("commit", "publish the queue", LANES_LANE=LANE)
    assert result.returncode == 2, result.stderr
    err = result.stderr
    assert "archive/<lane>-stranded-" not in err, "the lane is filled in"
    stop = err.find("if any '+' line is not your own write, STOP and take it to the lane its subject names")
    archive = err.find(f"git -C {c} push origin HEAD:refs/heads/archive/{LANE}-stranded-")
    reset = err.find(f"git -C {c} reset --keep refs/remotes/origin/main")
    assert 0 <= stop < archive < reset, err
    assert "push" not in box.net_ops()
    _settled(box, c)


def test_the_publish_acts_list_line_reads_origin_past_a_local_branch_named_origin_main(box: Box):
    """333 of lane openRepoTools-3's re-check of #307: the publish act's
    list line said `cherry -v origin/main HEAD`, and with a local branch
    named `origin/main` that short name is the branch, so the line listed 0
    `+` lines where origin lacks the whole queue, and the STOP check it
    exists for read nothing. It names `refs/remotes/origin/main` now."""
    c = box.seam()
    box.use_net()
    shas = _queue(box, c, 2)
    box.git("-C", str(c), "branch", "origin/main", "HEAD")   # the shadow
    box.peer_pushes("handoffs/repoS4/elsewhere.md", "a peer's file" + "\n")
    result = box.helper("commit", "publish the queue", LANES_LANE=LANE)
    err = result.stderr
    assert result.returncode == 2, err
    listed = re.search(r"list them: git (-C \S+ cherry -v \S+ HEAD);", err)
    assert listed, err
    out = box.git(*shlex.split(listed.group(1)))
    assert [l.split()[1] for l in out.splitlines() if l.startswith("+ ")] == shas, (out, err)
    assert "push" not in box.net_ops()
    _settled(box, c)


@pytest.mark.parametrize("state", ["head-is-the-tip", "on-top", "rewritten"])
def test_a_publish_act_push_refused_with_origin_unmoved_reads_head_exit_6(box: Box, state: str):
    """w1b-c6's second find, with item 1: the publish act's refusal with
    origin unmoved (a hook, a permission, a protected branch) said "they are
    kept on HEAD" without reading HEAD, the shape 638b13a took out of
    `commit_publish`'s. Where HEAD is still the commit the fence read, the
    words are what they were. Where an unlocked writer's stamp is on top, or
    an amend took the queue's tip off the branch while the push was in
    flight, `cp_not_head`'s and `cp_rewritten`'s words answer, with this
    refusal's own clause (6). Nothing is pushed twice, and nothing replayed."""
    c = box.seam()
    shas = _queue(box, c, n=2)
    tip = _refuse_push_after(box, "" if state == "head-is-the-tip" else _another_writer(c, state))
    result = box.helper("commit", "publish the queue", LANES_LANE=LANE)
    assert result.returncode == 6, result.stderr
    err = result.stderr
    assert "failed with origin/main unmoved" in err
    assert "push refused (attempt" not in err, "no replay: there is no edit to repeat"
    assert box.pushes() == 1
    assert box.origin_head() == tip
    if state == "head-is-the-tip":
        assert "they are kept on HEAD, and nothing of them reached origin by this push" in err
        assert "is no longer HEAD" not in err and "rewrote" not in err
        assert box.head(c) == shas[-1]
        assert len(box.unpublished(c)) == 2
    elif state == "on-top":
        assert f"HEAD is {box.head(c)}, not this write's commit {shas[-1]}" in err, err
        assert "it and the commit on top of it are kept on HEAD" in err
        assert "they are kept on HEAD, and nothing of them reached origin" not in err
        assert len(box.unpublished(c)) == 3, "the queue's two and the stamp, all kept for the publish act"
    else:
        assert "rewrote this write's commit" in err
        assert "kept on HEAD" not in err, "the queue's tip is not on HEAD under its own sha"
        on_head = subprocess.run(["git", "-C", str(c), "merge-base", "--is-ancestor", shas[-1], "HEAD"],
                                 env=box.env, capture_output=True, check=False).returncode
        assert on_head == 1, "the commit the words name is not on HEAD"
        assert shas[-1] in err
    _settled(box, c)


# ------------------------------------------------------------ --sweep

@pytest.mark.parametrize("argv", [
    ("set-row-state", LANE, "LIVE · swept"),
    ("log", "NOTED", f"lane:{LANE}", "swept", *HOME_FLAG),
    ("commit", "swept"),
], ids=["set-row-state", "log", "commit"])
def test_sweep_flag_is_refused(box: Box, argv):
    """Choice 9 withdraws `--sweep`: a pending register edit is committed by
    its own act and never swept into another write. Refused (2) before
    anything is read or fetched."""
    c = box.seam()
    box.use_net()
    box.hand_edit(c)
    before = box.snapshot(c)
    result = box.helper("--sweep", *argv, LANES_LANE=LANE, LANES_SESSION=UUID)
    assert result.returncode == 2, result.stderr
    assert "--sweep is withdrawn" in result.stderr
    assert box.snapshot(c) == before
    assert box.net_ops() == [], "refused before any network call"
    _settled(box, c)


def test_no_sweep_is_still_accepted(box: Box):
    """`--no-sweep`, the old default, changes nothing."""
    c = box.seam()
    result = box.helper("--no-sweep", "set-row-state", LANE, "LIVE · not swept")
    assert result.returncode == 0, result.stderr
    assert _set("LIVE · not swept") in box.origin_register()
    _settled(box, c)


# ------------------------------------- the window before S3 (rv1b's pre-review)

S3_REFSPEC = "+refs/heads/main:refs/remotes/origin/main"


def _at_s3_fetch(box: Box, body: str) -> None:
    """Run `body` once, at the helper's first fetch with S3's own refspec:
    after the verb's checks before the lock, and before S3's fetch under it."""
    count = shlex.quote(str(box.root / "s3hook.count"))
    box.use_net(
        '[ "$1" = fetch ] || exit 0' + "\n" +
        f'case "$*" in *"{S3_REFSPEC}"*) : ;; *) exit 0 ;; esac' + "\n" +
        f"[ -e {count} ] && exit 0" + "\n" +
        f"echo 1 > {count}" + "\n" + body + "\n" + "exit 0" + "\n")


def test_a_rival_claim_landing_before_S3s_fetch_loses_exit_7(box: Box):
    """MUST 1 of rv1b's pre-review: `claim`'s checks run before the lock on
    what `log_sync` fetched, and a rival's CLAIMED can land between that
    fetch and S3's. S3 then fast-forwarded onto it and this claim was pushed
    on top, so both lanes held the object. Now a fast-forward that moved
    origin's tip under this write's checks runs the verb again from the top
    on the new tip, with the lock held, and the replay's rescan finds the
    rival first: CLAIM-LOST (7), and one holder."""
    box.seam()
    c2 = box.clone(box.root / "c2")
    env = {k: v for k, v in box.env.items() if k not in ("LANES_GIT", "FAKE_NET_LOG", "FAKE_NET_HOOK")}
    env.update({"LANES_REPO": str(c2), "LANES_LANE": NEIGHBOUR, "LANES_SESSION": UUID2})
    words = " ".join(shlex.quote(f"{k}={v}") for k, v in sorted(env.items()))
    rival = " ".join(shlex.quote(a) for a in box.cmd("claim", OBJ, "--no-github", *HOME_FLAG))
    out = shlex.quote(str(box.root / "rival.out"))
    _at_s3_fetch(box, f"env -i {words} {rival} > {out} 2>&1; echo $? > {out}.rc")
    result = box.helper("claim", OBJ, "--no-github", *HOME_FLAG, LANES_LANE=LANE, LANES_SESSION=UUID)
    assert (box.root / "rival.out.rc").read_text(encoding="utf-8").strip() == "0", \
        (box.root / "rival.out").read_text(encoding="utf-8")
    assert result.returncode == 7, result.stderr
    assert "moved while this write's checks ran" in result.stderr
    assert f"another lane's claim landed on main before this one: @{NEIGHBOUR}" in result.stderr
    mine = box.origin_file(f"lanes/log/{LANE}.md")
    assert f"CLAIMED — lane {LANE}" not in mine, "this lane never holds it"
    assert f"CLAIM-LOST — lane {LANE}" in mine
    assert f"CLAIMED — lane {NEIGHBOUR}" in box.origin_file(f"lanes/log/{NEIGHBOUR}.md")


@pytest.mark.parametrize("peer", ["retires-it", "adds-it"])
def test_an_add_row_whose_name_lands_before_S3s_fetch_refuses(box: Box, peer: str):
    """MUST 2 of rv1b's pre-review: `add-row`'s retirement and duplicate
    checks run before the lock. A peer's retirement of the name, or its own
    row for it, landing before S3's fetch was fast-forwarded in and the row
    pushed on top, at attempt 1. The re-run on the new tip refuses (2), and
    nothing is written."""
    c = box.seam()
    row = _row(NEW_LANE, uuid=UUID3)
    if peer == "retires-it":
        box.peer_prepares(ARCHIVE, None,
                          "# retired rows" + "\n" + "\n" + "| lane | session id |" + "\n" + "|---|---|" + "\n" +
                          f"| `{NEW_LANE}` | harness `{UUID3}` |" + "\n", "a peer retires the name")
        words = f"lane '{NEW_LANE}' is RETIRED"
    else:
        box.peer_prepares(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                          _row(NEIGHBOUR, uuid=UUID2) + "\n" + row, "a peer adds the row")
        words = f"lane '{NEW_LANE}' already has a row"
    _at_s3_fetch(box, f"git -C {shlex.quote(str(box.peer))} push -q origin main")
    result = box.helper("add-row", row)
    assert result.returncode == 2, result.stderr
    assert "moved while this write's checks ran" in result.stderr
    assert words in result.stderr, result.stderr
    assert box.origin_register().count(f"`{NEW_LANE}`") == (1 if peer == "adds-it" else 0)
    assert "push" not in box.net_ops(), "refused before any push"
    assert box.unpublished(c) == []
    _settled(box, c)


def test_a_commit_made_on_top_before_the_replay_is_kept_exit_6(box: Box):
    """MUST 4 of rv1b's pre-review: until slices 2b and 3, lane-start's
    stamp, lane-handoff's commit and the skill's commit are made in the same
    checkout with no lock. One landing on top of this write's commit while its
    push is in flight was dropped by the replay's `reset --keep`, with exit 0
    and nothing said. Now the replay asks HEAD first: both commits are kept
    on HEAD and named (6), and nothing is dropped."""
    c = box.seam()
    peer = shlex.quote(str(box.peer))
    cq = shlex.quote(str(c))
    count = shlex.quote(str(box.root / "push.count"))
    box.use_net(
        '[ "$1" = push ] || exit 0' + "\n" +
        f"[ -e {count} ] && exit 0" + "\n" +
        f"echo 1 > {count}" + "\n" +
        f"git -C {peer} commit -q --allow-empty -m 'a peer lands first'" + "\n" +
        f"git -C {peer} push -q origin main" + "\n" +
        f"printf 'stamp' > {cq}/handoffs/stamp.md" + "\n" +
        f"git -C {cq} add -- handoffs/stamp.md" + "\n" +
        f"git -C {cq} commit -q -m 'handoff(repoS4-2@Eagle): a stamp from an unlocked writer' -- handoffs/stamp.md" + "\n" +
        "exit 0" + "\n")
    result = box.helper("set-row-state", LANE, "LIVE · the write under it")
    assert result.returncode == 6, result.stderr
    assert "is no longer HEAD, so it is not replayed" in result.stderr
    assert "in this checkout while its push was in flight" in result.stderr, "the HEAD check fired, not the drop's"
    assert "push refused (attempt 1 of 6)" not in result.stderr, "no reset was made"
    assert box.subject(c) == "handoff(repoS4-2@Eagle): a stamp from an unlocked writer"
    assert box.subject(c, "HEAD~1").startswith(f"LANES({LANE}@"), "this write's commit is under it"
    assert (c / "handoffs" / "stamp.md").is_file(), "the other writer's file is still there"
    assert len(box.unpublished(c)) == 2, "both kept on HEAD, for the publish act"
    _settled(box, c)


def test_a_commit_made_on_top_at_the_sixth_push_is_named_before_the_bound_exit_6(box: Box):
    """m1b-c2's mutant B04 (the replay's HEAD check removed) survived every
    case, because the drop's compare-and-swap refuses a commit on top as
    well, in other words. The HEAD check comes before the six-attempt bound,
    so a commit that lands on top during the sixth push is named as not this
    write's, and is never folded into the bound's "kept on HEAD"."""
    c = box.seam()
    peer = shlex.quote(str(box.peer))
    cq = shlex.quote(str(c))
    count = shlex.quote(str(box.root / "push.count"))
    box.use_net(
        '[ "$1" = push ] || exit 0' + "\n" +
        f"n=$(cat {count} 2>/dev/null || echo 0)" + "\n" +
        f"echo $((n + 1)) > {count}" + "\n" +
        f"git -C {peer} fetch -q origin" + "\n" +
        f"git -C {peer} merge -q --ff-only refs/remotes/origin/main" + "\n" +
        f"git -C {peer} commit -q --allow-empty -m \"a peer's commit lands first ($((n + 1)))\"" + "\n" +
        f"git -C {peer} push -q origin main" + "\n" +
        '[ "$n" = 5 ] || exit 0' + "\n" +
        f"printf 'stamp' > {cq}/handoffs/stamp.md" + "\n" +
        f"git -C {cq} add -- handoffs/stamp.md" + "\n" +
        f"git -C {cq} commit -q -m 'handoff(repoS4-2@Eagle): a stamp from an unlocked writer' -- handoffs/stamp.md" + "\n" +
        "exit 0" + "\n")
    result = box.helper("set-row-state", LANE, "LIVE · beaten five times, then a stamp on top")
    assert result.returncode == 6, result.stderr
    assert "push refused (attempt 5 of 6)" in result.stderr
    assert "is no longer HEAD, so it is not replayed" in result.stderr
    assert "after six attempts" not in result.stderr, "the HEAD check comes before the bound"
    assert box.subject(c) == "handoff(repoS4-2@Eagle): a stamp from an unlocked writer"
    assert len(box.unpublished(c)) == 2, "both kept on HEAD, for the publish act"
    _settled(box, c)


# ------------------------ one checkout, several writers (rv1b-c's re-check)

def _spawn(box: Box, name: str, *args: str, **extra: str) -> subprocess.Popen:
    """The helper in the background, its output in `<name>.out` and
    `<name>.err` under the box (files, so no pipe can fill and stall it)."""
    out = (box.root / f"{name}.out").open("w", encoding="utf-8")
    err = (box.root / f"{name}.err").open("w", encoding="utf-8")
    try:
        return subprocess.Popen(box.cmd(*args), env=dict(box.env, **extra), cwd=str(box.root),
                                stdout=out, stderr=err, text=True)
    finally:
        out.close()
        err.close()


def _err(box: Box, name: str) -> str:
    return (box.root / f"{name}.err").read_text(encoding="utf-8")


def _wait_for(pred, what: str, secs: float = 60.0) -> None:
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {what}")


def _waits_on_the_lock(pid: int) -> bool:
    """True while process `pid` is in `mutex_try`'s wait for the checkout's
    lock: a `sleep` it started is running. Nothing a write does before the
    lock starts one, so its own checks have all run."""
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            text = stat.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        comm = text[text.find("(") + 1:text.rfind(")")]
        fields = text[text.rfind(")") + 2:].split()
        if comm == "sleep" and len(fields) > 1 and fields[1] == str(pid):
            return True
    return False


def _another_write_holds_the_lock(box: Box, c: Path, gate: Path) -> subprocess.Popen:
    """P3, any other write through the same checkout: it takes the lock and
    holds it at its push until the case writes `gate`."""
    hook = box.fakebin / "hold-at-push"
    hook.write_text(
        "#!/usr/bin/env bash" + "\n" +
        '[ "$1" = push ] || exit 0' + "\n" +
        f"i=0; while [ ! -e {shlex.quote(str(gate))} ] && [ $i -lt 500 ]; do sleep 0.1; i=$((i + 1)); done" + "\n" +
        "exit 0" + "\n", encoding="utf-8")
    hook.chmod(0o755)
    p3 = _spawn(box, "p3", "set-row-state", LANE, "LIVE · another write in this checkout",
                FAKE_NET_HOOK=str(hook))
    _wait_for(lambda: box.lock_of(c).exists(), "P3 to take the checkout's lock")
    return p3


def _a_reader_fetches_in(box: Box, c: Path) -> None:
    """Any reader's `log_sync` in the shared checkout (a peer's push or its
    read-back does the same): it moves the checkout's own
    `refs/remotes/origin/main` to origin's tip, takes no lock, and writes
    nothing."""
    read = box.helper("who", OBJ, *HOME_FLAG)
    assert read.returncode in (0, 8), read.stderr
    assert box.git("-C", str(c), "rev-parse", "refs/remotes/origin/main").strip() == box.origin_head(), \
        "the reader moved the shared checkout's origin/main"


def test_a_rival_claim_a_reader_fetched_into_the_shared_checkout_loses_exit_7(box: Box):
    """MUST-N of rv1b-c's re-check: B35 asked only whether S3's OWN fetch
    moved origin/main. In a checkout several writers share — W, every lane's
    while routing is off — another process moves that same ref while this
    claim waits on the lock after its checks: a reader's `log_sync`, a peer's
    push, its read-back. S3's fetch then found nothing new, this claim was
    pushed on top of the rival's, and two lanes held the object. Now S3
    compares with the tip the checks read, so the claim runs again from the
    top on the new tip, and the replay's rescan finds the rival: CLAIM-LOST
    (7), one holder."""
    c = box.seam()
    box.use_net()
    gate = box.root / "go"
    p3 = _another_write_holds_the_lock(box, c, gate)
    a = _spawn(box, "a", "claim", OBJ, "--no-github", *HOME_FLAG, LANES_LANE=LANE, LANES_SESSION=UUID)
    _wait_for(lambda: _waits_on_the_lock(a.pid), "the claim to finish its checks and wait on the lock")
    c2 = box.clone(box.root / "c2")
    rival = box.helper("claim", OBJ, "--no-github", *HOME_FLAG,
                       LANES_REPO=str(c2), LANES_LANE=NEIGHBOUR, LANES_SESSION=UUID2)
    assert rival.returncode == 0, rival.stderr
    _a_reader_fetches_in(box, c)
    gate.write_text("go" + "\n", encoding="utf-8")
    assert p3.wait(timeout=180) == 0, _err(box, "p3")
    rc = a.wait(timeout=180)
    stderr = _err(box, "a")
    assert rc == 7, stderr
    assert "moved while this write's checks ran" in stderr
    assert f"another lane's claim landed on main before this one: @{NEIGHBOUR}" in stderr
    mine = box.origin_file(f"lanes/log/{LANE}.md")
    assert f"CLAIMED — lane {LANE}" not in mine, "this lane never holds it"
    assert f"CLAIM-LOST — lane {LANE}" in mine
    assert f"CLAIMED — lane {NEIGHBOUR}" in box.origin_file(f"lanes/log/{NEIGHBOUR}.md")
    assert _set("LIVE · another write in this checkout") in box.origin_register(), "P3's write landed"
    assert box.unpublished(c) == []
    _settled(box, c)


def test_an_add_row_whose_name_a_reader_fetched_into_the_shared_checkout_refuses(box: Box):
    """MUST-N of rv1b-c's re-check, for `add-row`: a peer's retirement of the
    name lands while the add-row waits on the shared checkout's lock after its
    checks, and a reader there fetches it. S3's fetch found nothing new, and
    the retired name was issued again at attempt 1. Now the re-run on the new
    tip refuses (2), and nothing is written."""
    c = box.seam()
    box.use_net()
    gate = box.root / "go"
    row = _row(NEW_LANE, uuid=UUID3)
    box.peer_prepares(ARCHIVE, None,
                      "# retired rows" + "\n" + "\n" + "| lane | session id |" + "\n" + "|---|---|" + "\n" +
                      f"| `{NEW_LANE}` | harness `{UUID3}` |" + "\n", "a peer retires the name")
    p3 = _another_write_holds_the_lock(box, c, gate)
    a = _spawn(box, "a", "add-row", row)
    _wait_for(lambda: _waits_on_the_lock(a.pid), "the add-row to finish its checks and wait on the lock")
    box.git("-C", str(box.peer), "push", "-q", "origin", "main")
    _a_reader_fetches_in(box, c)
    gate.write_text("go" + "\n", encoding="utf-8")
    assert p3.wait(timeout=180) == 0, _err(box, "p3")
    rc = a.wait(timeout=180)
    stderr = _err(box, "a")
    assert rc == 2, stderr
    assert "moved while this write's checks ran" in stderr
    assert f"lane '{NEW_LANE}' is RETIRED" in stderr
    assert box.origin_register().count(f"`{NEW_LANE}`") == 0, "the retired name is not issued again"
    assert not [s for s in box.subjects() if s.endswith("add row")], "no add-row commit reached origin"
    assert box.unpublished(c) == []
    _settled(box, c)


# 281 of lane openRepoTools-3's review of #307 (its P1 and P7): the window
# between S3's compare and S3's fast-forward.

def _clean_words(box: Box, **extra: str) -> str:
    """An `env -i` prefix for a nested helper run: the box's own environment,
    with none of this case's shims or hooks."""
    env = {k: v for k, v in box.env.items() if k not in ("LANES_GIT", "FAKE_NET_LOG", "FAKE_NET_HOOK")}
    env.update(extra)
    return "env -i " + " ".join(shlex.quote(f"{k}={v}") for k, v in sorted(env.items()))


def _between_s3s_compare_and_its_ff(box: Box, c: Path, body: str) -> dict:
    """`body` runs once, after S3's fetch and its compare (`cs_now` against
    the tip the checks read) and before its fast-forward: at step 3's
    `symbolic-ref -q HEAD` in `c`, the first git call after the compare. The
    net hook arms it at S3's own fetch (its refspec), and a `git` first on
    PATH fires it; `@GIT@` in `body` is the real git. Returns the env that
    puts the shim on PATH."""
    real = shutil.which("git")
    assert real, "git is on PATH"
    armed = shlex.quote(str(box.root / "armed"))
    fired = shlex.quote(str(box.root / "fired"))
    box.use_net('[ "$1" = fetch ] || exit 0' + "\n" +
                f'case "$*" in *"{S3_REFSPEC}"*) : ;; *) exit 0 ;; esac' + "\n" +
                f"[ -e {fired} ] || [ -e {armed} ] || echo 1 > {armed}" + "\n" +
                "exit 0" + "\n")
    shim = box.root / "gitshim"
    shim.mkdir()
    step3 = shlex.quote(f"-C {c} symbolic-ref -q HEAD")
    (shim / "git").write_text(
        "#!/usr/bin/env bash" + "\n" +
        f'if [ -e {armed} ] && [ "$*" = {step3} ]; then' + "\n" +
        f"  mv -- {armed} {fired}" + "\n" +
        body.replace("@GIT@", shlex.quote(real)) +
        "fi" + "\n" +
        f'exec {shlex.quote(real)} "$@"' + "\n", encoding="utf-8")
    (shim / "git").chmod(0o755)
    return {"PATH": f"{shim}{os.pathsep}{box.env['PATH']}"}


def _a_reader_runs_in(box: Box, c: Path) -> str:
    """Any reader's `log_sync` in the shared checkout, as a line of the shim:
    it fetches, which moves `c`'s own `refs/remotes/origin/main`, takes no
    lock, and writes nothing."""
    who = " ".join(shlex.quote(a) for a in box.cmd("who", OBJ, *HOME_FLAG))
    return f"  {_clean_words(box, LANES_REPO=str(c))} {who} >/dev/null 2>&1 || :" + "\n"


def test_a_rival_claim_a_reader_fetched_in_after_S3s_compare_loses_exit_7(box: Box):
    """281 of lane openRepoTools-3's review of #307 (its P1): S3 compared the
    tip the claim's checks read with the one its own fetch found (decision
    22), and then fast-forwarded to `refs/remotes/origin/main` BY NAME, about
    ten git calls later. A reader's `log_sync` in the shared checkout moved
    that ref in between, to a rival's CLAIMED that had just landed: it was
    fast-forwarded in unchecked, this claim was written on top of it, and its
    push, a plain fast-forward, landed at attempt 1 (exit 0). Two lanes held
    one object. Now the fast-forward goes to the sha S3's fetch read, so the
    push is refused, and the replay's rescan finds the rival: CLAIM-LOST (7),
    and one holder."""
    c = box.seam()
    c2 = box.clone(box.root / "c2")
    rival = " ".join(shlex.quote(a) for a in box.cmd("claim", OBJ, "--no-github", *HOME_FLAG))
    out = shlex.quote(str(box.root / "rival.out"))
    env = _between_s3s_compare_and_its_ff(box, c,
        f"  {_clean_words(box, LANES_REPO=str(c2), LANES_LANE=NEIGHBOUR, LANES_SESSION=UUID2)} {rival} > {out} 2>&1" + "\n" +
        f"  echo $? > {out}.rc" + "\n" + _a_reader_runs_in(box, c))
    result = box.helper("claim", OBJ, "--no-github", *HOME_FLAG, LANES_LANE=LANE, LANES_SESSION=UUID, **env)
    assert (box.root / "fired").exists(), "the rival landed, and a reader fetched it in, inside the window"
    assert (box.root / "rival.out.rc").read_text(encoding="utf-8").strip() == "0", \
        (box.root / "rival.out").read_text(encoding="utf-8")
    assert f"CLAIMED — lane {NEIGHBOUR}" in box.origin_file(f"lanes/log/{NEIGHBOUR}.md")
    mine = box.origin_file(f"lanes/log/{LANE}.md")
    assert f"CLAIMED — lane {LANE}" not in mine, "two lanes hold one object"
    assert result.returncode == 7, result.stderr
    assert "push refused (attempt 1 of 6)" in result.stderr
    assert f"another lane's claim landed on main before this one: @{NEIGHBOUR}" in result.stderr
    assert f"CLAIM-LOST — lane {LANE}" in mine
    assert box.unpublished(c) == []
    _settled(box, c)


def test_an_add_row_whose_retirement_a_reader_fetched_in_after_S3s_compare_refuses(box: Box):
    """281's P7: the same window for `add-row`. A peer's retirement of the
    name lands and a reader fetches it into the shared checkout after S3's
    compare and before its fast-forward. It was fast-forwarded in unchecked,
    and the retired name was issued again at attempt 1 (exit 0). Now the row
    is made on the sha S3's fetch read, its push is refused, and the re-run
    on origin's new tip refuses (2): the name is not issued again."""
    c = box.seam()
    row = _row(NEW_LANE, uuid=UUID3)
    box.peer_prepares(ARCHIVE, None,
                      "# retired rows" + "\n" + "\n" + "| lane | session id |" + "\n" + "|---|---|" + "\n" +
                      f"| `{NEW_LANE}` | harness `{UUID3}` |" + "\n", "a peer retires the name")
    env = _between_s3s_compare_and_its_ff(box, c,
        f"  @GIT@ -C {shlex.quote(str(box.peer))} push -q origin main" + "\n" + _a_reader_runs_in(box, c))
    result = box.helper("add-row", row, **env)
    assert (box.root / "fired").exists(), "the retirement landed, and a reader fetched it in, inside the window"
    assert f"`{NEW_LANE}`" in box.origin_file(ARCHIVE), "the retirement landed"
    assert box.origin_register().count(f"`{NEW_LANE}`") == 0, "a retired name was issued again"
    assert result.returncode == 2, result.stderr
    assert "push refused (attempt 1 of 6)" in result.stderr
    assert f"lane '{NEW_LANE}' is RETIRED" in result.stderr, result.stderr
    assert box.unpublished(c) == []
    _settled(box, c)


# 284 of lane openRepoTools-3's review of #307 (its P3): a claim that runs
# again from the top runs with the checkout's lock held, and its top held
# Rule 1's network reads, none bounded by `git_net`.

CLAIM_URL = "https://github.com/opensoft/repoS4/issues/1#issuecomment-284"


def _network_reads_logged(box: Box, c: Path) -> tuple:
    """`gh`, and `git ls-remote` of a GitHub URL, each logged with whether
    `c`'s lock is held at that moment; `gh issue view ... --json comments`
    answers a claim comment's URL. Nothing reaches the network. Returns the
    log and the env that puts both first and lets the claim ask GitHub."""
    lock = shlex.quote(str(box.lock_of(c)))
    log = shlex.quote(str(box.root / "net-reads.log"))
    held = f'if [ -d {lock} ]; then s="LOCK HELD"; else s="no lock"; fi'
    gh = box.fakebin / "gh"
    gh.write_text("#!/usr/bin/env bash" + "\n" + held + "\n" +
                  f'printf "gh %s :: %s\\n" "$*" "$s" >> {log}' + "\n" +
                  f'case "$*" in *"--json comments"*) echo "{CLAIM_URL}" ;; esac' + "\n" +
                  "exit 0" + "\n", encoding="utf-8")
    gh.chmod(0o755)
    real = shutil.which("git")
    assert real, "git is on PATH"
    shim = box.root / "gitshim"
    shim.mkdir()
    (shim / "git").write_text(
        "#!/usr/bin/env bash" + "\n" +
        'case " $* " in *" ls-remote --heads git@github.com:"*)' + "\n" +
        "  " + held + "\n" +
        f'  printf "git %s :: %s\\n" "$*" "$s" >> {log}' + "\n" +
        "  exit 0 ;;" + "\n" + "esac" + "\n" +
        f'exec {shlex.quote(real)} "$@"' + "\n", encoding="utf-8")
    (shim / "git").chmod(0o755)
    return box.root / "net-reads.log", {"PATH": f"{shim}{os.pathsep}{box.env['PATH']}", "LANES_NO_GITHUB": "0"}


def _origin_moves_once_at_s3s_fetch(box: Box) -> None:
    peer = shlex.quote(str(box.peer))
    _at_s3_fetch(box, f"git -C {peer} fetch -q origin && git -C {peer} merge -q --ff-only refs/remotes/origin/main" + "\n" +
                 f"git -C {peer} commit -q --allow-empty -m 'a peer moves origin'" + "\n" +
                 f"git -C {peer} push -q origin main")


def test_a_claims_re_run_makes_no_network_read_while_it_holds_the_lock(box: Box):
    """284 (its P3): origin moves at S3's fetch, so the claim runs again from
    the top with the lock held (decision 19/22), and all four of Rule 1's
    reads (`gh issue view`, two `gh pr list`, `git ls-remote` of GitHub) ran
    again under it, with no time limit and no lock refresh: a stalled one
    held W's lock for every lane. Now the re-run makes none: the reads made
    at attempt 1, before the lock, cross the `exec` and are printed, and
    cited, as they were. The rescan decides the race."""
    c = box.seam()
    log, env = _network_reads_logged(box, c)
    _origin_moves_once_at_s3s_fetch(box)
    result = box.helper("claim", OBJ, *HOME_FLAG, LANES_LANE=LANE, LANES_SESSION=UUID, **env)
    reads = log.read_text(encoding="utf-8").splitlines()
    assert result.returncode == 0, result.stderr
    assert "moved while this write's checks ran" in result.stderr, "the claim ran again with the lock held"
    assert any(r.startswith("gh issue view") for r in reads), "attempt 1 made Rule 1's reads"
    assert any(r.startswith("git ls-remote --heads git@github.com:") for r in reads), reads
    assert [r for r in reads if "LOCK HELD" in r] == [], reads
    assert "made at attempt 1, before the lock" in result.stderr
    # 332 of lane 3's re-check: S3's fetch, the push and its read-back still
    # run on the re-run, each bounded by `git_net`; what it makes none of is
    # a GitHub read, and the note says that, not "no network read".
    assert "makes no GitHub read with it held" in result.stderr, result.stderr
    assert "no network read" not in result.stderr
    assert result.stdout.count("1. existing `CLAIMED —` comments on") == 2, "printed at both attempts"
    assert f"CLAIMED — lane {LANE}" in box.origin_file(f"lanes/log/{LANE}.md")
    _settled(box, c)


def test_a_takeovers_re_run_cites_the_claim_url_attempt_1_read_and_reads_nothing_with_the_lock(box: Box):
    """284's takeover half: `gh_stale_claim_url`, the read of the stale
    claim's comment a TAKEOVER cites, ran again on the re-run with the lock
    held. Now the URL attempt 1 read crosses the `exec`, as the takeover's
    source does, and the TAKEOVER line cites it, with no read under the
    lock."""
    stale = f"CLAIMED — lane {NEIGHBOUR}, session {UUID2}@Eagle, 2026-10-01T00:00:00Z, {OBJ} — no-github" + "\n"
    box.peer_pushes(f"lanes/log/{NEIGHBOUR}.md", _log_head(NEIGHBOUR) + stale)
    c = box.seam()
    log, env = _network_reads_logged(box, c)
    _origin_moves_once_at_s3s_fetch(box)
    result = box.helper("claim", OBJ, "--force", *HOME_FLAG, LANES_LANE=LANE, LANES_SESSION=UUID, **env)
    reads = log.read_text(encoding="utf-8").splitlines()
    assert result.returncode == 0, result.stderr
    assert "moved while this write's checks ran" in result.stderr, "the takeover ran again with the lock held"
    assert any("--json comments" in r for r in reads), "attempt 1 read the stale claim's URL"
    assert [r for r in reads if "LOCK HELD" in r] == [], reads
    mine = box.origin_file(f"lanes/log/{LANE}.md")
    assert f"TAKEOVER — lane {LANE}" in mine and CLAIM_URL in mine, mine
    _settled(box, c)


def test_a_claim_that_meets_a_move_at_every_S3_fetch_stops_at_six_exit_2(box: Box):
    """SHOULD B of rv1b-c's re-check: `cs_recheck`'s six-attempt bound. A
    peer moves origin at every one of S3's fetches, so every attempt finds
    the tip moved under its checks. The sixth refuses (2) with nothing
    written, rather than re-running for as long as origin is busy."""
    c = box.seam()
    peer = shlex.quote(str(box.peer))
    count = shlex.quote(str(box.root / "moves"))
    box.use_net(
        '[ "$1" = fetch ] || exit 0' + "\n" +
        f'case "$*" in *"{S3_REFSPEC}"*) : ;; *) exit 0 ;; esac' + "\n" +
        f'n=$(cat {count} 2>/dev/null || echo 0); [ "$n" -lt 8 ] || exit 0; echo $((n + 1)) > {count}' + "\n" +
        f"git -C {peer} fetch -q origin && git -C {peer} merge -q --ff-only refs/remotes/origin/main" + "\n" +
        f'git -C {peer} commit -q --allow-empty -m "a peer moves origin ($((n + 1)))"' + "\n" +
        f"git -C {peer} push -q origin main" + "\n" +
        "exit 0" + "\n")
    result = box.helper("claim", OBJ, "--no-github", *HOME_FLAG, LANES_LANE=LANE, LANES_SESSION=UUID)
    assert result.returncode == 2, result.stderr
    assert "on each of six attempts" in result.stderr
    assert (box.root / "moves").read_text(encoding="utf-8").strip() == "6", "one move per attempt, six in all"
    assert re.findall(r"checks ran \([^)]*\): nothing is written yet.*?attempt (\d) of 6", result.stderr) == \
        ["1", "2", "3", "4", "5"]
    assert f"lane {LANE}" not in box.origin_file(f"lanes/log/{LANE}.md").split("\n", 1)[1], \
        "nothing of this claim's reached origin"
    assert "push" not in box.net_ops(), "refused before any push"
    assert box.unpublished(c) == []
    _settled(box, c)


def test_a_commit_another_writer_rewrote_is_named_as_rewritten_exit_6(box: Box):
    """SHOULD A of rv1b-c's re-check: until slices 2b and 3, lane-start's
    stamp and lane-handoff run `pull --rebase` and push in the same checkout
    with no lock. One that runs while this write's push is in flight rebases
    this write's commit, and here pushes its copy. Exit 6 said the commit and
    the one on top of it were "kept on HEAD"; its sha is on no branch here,
    and its change is on origin. Now the words say another writer rewrote it
    and point to the read by content, and still nothing is replayed."""
    c = box.seam()
    peer = shlex.quote(str(box.peer))
    cq = shlex.quote(str(c))
    pushed = shlex.quote(str(box.root / "pushed"))
    done = shlex.quote(str(box.root / "rebased"))
    box.use_net(
        f'if [ "$1" = push ] && [ ! -e {pushed} ]; then echo 1 > {pushed}' + "\n" +
        f"  git -C {peer} commit -q --allow-empty -m 'a peer lands first'" + "\n" +
        f"  git -C {peer} push -q origin main" + "\n" +
        "  exit 0" + "\n" + "fi" + "\n" +
        f'if [ "$1" = fetch ] && [ -e {pushed} ] && [ ! -e {done} ]; then echo 1 > {done}' + "\n" +
        f"  printf 'stamp' > {cq}/handoffs/stamp.md" + "\n" +
        f"  git -C {cq} add -- handoffs/stamp.md" + "\n" +
        f"  git -C {cq} commit -q -m 'handoff(repoS4-2@Eagle): a stamp, rebased and pushed with no lock' -- handoffs/stamp.md" + "\n" +
        f"  git -C {cq} pull --rebase -q origin main" + "\n" +
        f"  git -C {cq} push -q origin main" + "\n" +
        "fi" + "\n" + "exit 0" + "\n")
    result = box.helper("set-row-state", LANE, "LIVE · rewritten under it")
    assert result.returncode == 6, result.stderr
    assert "rewrote this write's commit" in result.stderr
    assert "kept on HEAD" not in result.stderr, "nothing of this write's is on HEAD under its own sha"
    assert "cherry -v origin/main HEAD" in result.stderr
    named = re.search(r"so it is not replayed: ([0-9a-f]{40}) ", result.stderr)
    assert named, result.stderr
    on_head = subprocess.run(["git", "-C", str(c), "merge-base", "--is-ancestor", named.group(1), "HEAD"],
                             env=box.env, capture_output=True, check=False)
    assert on_head.returncode == 1, "the named commit is not on HEAD"
    assert _set("LIVE · rewritten under it") in box.origin_register(), "the rewritten copy reached origin"
    assert "push refused (attempt 1 of 6)" not in result.stderr, "no reset was made"
    assert box.unpublished(c) == []
    _settled(box, c)


# The drop's two moments, as `git` first on PATH sees them: the helper at
# d9ff4e6 dropped with one `reset -q --keep`; since SHOULD C the branch moves
# first (`update-ref`, a compare-and-swap) and the tree after it
# (`read-tree -m -u`). Each pattern names both, so a case runs on either.
DROP_STARTS = '*" reset -q --keep "*|*" update-ref -m lanes-edit: the replay drops "*'
DROP_ENDS = '*" reset -q --keep "*|*" read-tree -m -u "*'
STATE = "LIVE · the write under it"


def _git_shim(box: Box, pattern: str, *, before: str = "", after: str = "") -> dict:
    """A `git` first on PATH for the helper: the first call matching
    `pattern` runs `before`, then the real command, then `after`, and keeps
    the real command's status; every other call is the real git. `{git}` in
    the snippets is the real git. Returns the env that puts it on PATH."""
    real = shutil.which("git")
    assert real, "git is on PATH"
    shim = box.root / "gitshim"
    shim.mkdir()
    rq = shlex.quote(real)
    mark = shlex.quote(str(box.root / "fired"))
    (shim / "git").write_text(
        "#!/usr/bin/env bash" + "\n" +
        f'case " $* " in {pattern})' + "\n" +
        f"  if [ ! -e {mark} ]; then echo 1 > {mark}" + "\n" +
        before.format(git=rq) +
        f'    {rq} "$@"; rc=$?' + "\n" +
        after.format(git=rq) +
        "    exit $rc" + "\n" +
        "  fi ;;" + "\n" +
        "esac" + "\n" +
        f'exec {rq} "$@"' + "\n", encoding="utf-8")
    (shim / "git").chmod(0o755)
    return {"PATH": f"{shim}{os.pathsep}{box.env['PATH']}"}


def _stamp(c: Path) -> str:
    """An unlocked writer's stamp, committed by pathspec as lane-start does."""
    cq = shlex.quote(str(c))
    return (f"    printf 'stamp' > {cq}/handoffs/stamp.md" + "\n" +
            f"    {{git}} -C {cq} add -- handoffs/stamp.md" + "\n" +
            f"    {{git}} -C {cq} commit -q -m 'handoff(repoS4-2@Eagle): a stamp from an unlocked writer' -- handoffs/stamp.md" + "\n")


def _pull(c: Path) -> str:
    """An unlocked writer's `pull --rebase` (lane-start's, lane-handoff's)."""
    return f"    {{git}} -C {shlex.quote(str(c))} pull --rebase -q origin main >/dev/null 2>&1" + "\n"


def _mine_named_on_head(box: Box, c: Path, stderr: str) -> list:
    """Every sha the words name that is this write's commit, with whether
    HEAD holds it."""
    out = []
    for sha in sorted(set(re.findall(r"\b[0-9a-f]{40}\b", stderr))):
        subj = subprocess.run(["git", "-C", str(c), "log", "-1", "--format=%s", sha],
                              env=box.env, capture_output=True, text=True, check=False).stdout.strip()
        if subj.startswith(f"LANES({LANE}@"):
            on = subprocess.run(["git", "-C", str(c), "merge-base", "--is-ancestor", sha, "HEAD"],
                                env=box.env, capture_output=True, check=False).returncode == 0
            out.append((sha, on))
    return out


def test_a_commit_landing_before_the_replays_drop_is_never_dropped_exit_6(box: Box):
    """NIT 2 of rv1b-c's re-check, and SHOULD C of rv1b-c2's: the replay's
    HEAD check and its drop are two git calls, and an unlocked commit landing
    between them was dropped with this write's commit, with exit 0. The window
    is milliseconds, so a `git` first on PATH makes it exact: it commits on
    top just before the drop runs. The drop is a compare-and-swap of the
    branch from this write's own commit, so git refuses it and nothing moves:
    both commits are kept on HEAD and named (6), and nothing is dropped."""
    c = box.seam()
    box.race()
    env = _git_shim(box, DROP_STARTS, before=_stamp(c))
    result = box.helper("set-row-state", LANE, STATE, **env)
    assert (box.root / "fired").exists(), "the commit landed in the window"
    assert result.returncode == 6, result.stderr
    assert "between the replay's HEAD check and its drop" in result.stderr
    assert "is no longer HEAD, so it is not replayed" in result.stderr
    assert "push refused (attempt 1 of 6)" not in result.stderr, "nothing is replayed"
    assert box.subject(c) == "handoff(repoS4-2@Eagle): a stamp from an unlocked writer"
    assert box.subject(c, "HEAD~1").startswith(f"LANES({LANE}@"), "this write's commit is under it"
    assert (c / "handoffs" / "stamp.md").is_file(), "the other writer's file is still there"
    assert len(box.unpublished(c)) == 2, "both kept on HEAD, for the publish act"
    assert "the replay drops" not in box.git("-C", str(c), "reflog", "refs/heads/main"), "the branch never moved"
    _settled(box, c)


def test_a_drop_refused_for_another_reason_names_git_and_no_commit_on_top_exit_6(box: Box):
    """rv1b-c3's NIT E (its probe P2): the drop's compare-and-swap is refused
    for a reason other than a moved branch: another git process holds
    `refs/heads/main.lock` (a peer's commit, or a `pack-refs`, in flight), and
    HEAD is still this write's commit. The refusal went to `cp_not_head`,
    which said "HEAD is X, not this write's commit X: another commit was made
    on top of it" and "it and the commit on top of it are kept", and git's own
    words, in the file the helper read them into, were never shown. Now git's
    words are printed, and where HEAD is still this write's commit the words
    say that git could not move the branch and that nothing was moved (6),
    with no commit on top named."""
    c = box.seam()
    box.race()
    gd = box.git("-C", str(c), "rev-parse", "--absolute-git-dir").strip()
    lock = shlex.quote(f"{gd}/refs/heads/main.lock")
    env = _git_shim(box, DROP_STARTS, before=f"    : > {lock}\n")
    result = box.helper("set-row-state", LANE, STATE, **env)
    assert (box.root / "fired").exists(), "the lock was held at the drop"
    assert result.returncode == 6, result.stderr
    err = result.stderr
    sha = box.head(c)
    assert box.subject(c).startswith(f"LANES({LANE}@"), "HEAD is still this write's commit"
    assert re.search(r"git said: .*(cannot lock ref|main\.lock)", err), "git's own words are shown"
    assert "another commit was made on top" not in err, "no commit is on top"
    assert "it and the commit on top of it" not in err
    assert f"not this write's commit {sha}" not in err
    assert f"HEAD is still this write's commit {sha}" in err
    assert f"git could not move the branch off this write's commit to drop it, so nothing was moved and it is kept on HEAD: {sha}" in err
    assert "push refused (attempt 1 of 6)" not in err, "nothing is replayed"
    assert len(box.unpublished(c)) == 1, "the one commit is kept, for the publish act"
    _settled(box, c)


def test_an_up_to_date_pull_after_the_replays_drop_is_no_commit_on_top(box: Box):
    """SHOULD C of rv1b-c2's re-check, its case A: no commit lands anywhere,
    and an unlocked `pull --rebase` that is up to date runs just after the
    replay's drop. It rewrites ORIG_HEAD without moving HEAD, and the helper
    at d9ff4e6 read that as a commit on top: its "undo" did nothing, it said
    both commits were kept on HEAD, and the write was on neither HEAD nor
    origin (6). Nothing is read from ORIG_HEAD now, so the replay goes on and
    the write lands, as it did before the check (0)."""
    c = box.seam()
    box.race()
    env = _git_shim(box, DROP_ENDS, after=_pull(c))
    result = box.helper("set-row-state", LANE, STATE, **env)
    assert (box.root / "fired").exists(), "the pull ran just after the drop"
    assert result.returncode == 0, result.stderr
    assert "push refused (attempt 1 of 6)" in result.stderr
    assert "pushed origin/main (attempt 2)" in result.stderr
    assert "kept on" not in result.stderr, "nothing is said to be kept"
    assert box.origin_register().count(_set(STATE)) == 1, "the write landed once"
    assert box.head(c) == box.origin_head()
    assert box.unpublished(c) == []
    _settled(box, c)


def test_a_stamp_committed_and_pulled_around_the_replays_drop_is_never_lost(box: Box):
    """SHOULD C's case B, lane-start's own order: its stamp is committed on
    top of this write's commit just before the drop, and its `pull --rebase`
    runs just after. At d9ff4e6 the reset took both commits, the pull rewrote
    ORIG_HEAD, and the helper said both were kept on HEAD while neither was on
    it, nor on origin. Now the drop is refused with nothing moved: the stamp
    and this write's change stay on HEAD (here the pull rebases them, so the
    words say rewritten), the replay is not run (6), and "kept" is said only
    of a commit HEAD holds."""
    c = box.seam()
    box.race()
    env = _git_shim(box, DROP_STARTS, before=_stamp(c), after=_pull(c))
    result = box.helper("set-row-state", LANE, STATE, **env)
    assert (box.root / "fired").exists(), "the stamp and the pull ran around the drop"
    assert result.returncode == 6, result.stderr
    assert "push refused (attempt 1 of 6)" not in result.stderr, "nothing is replayed"
    head_register = box.git("-C", str(c), "show", f"HEAD:{REGISTER}")
    assert _set(STATE) in head_register or _set(STATE) in box.origin_register(), \
        "the write is on HEAD or on origin, never lost"
    assert box.git("-C", str(c), "show", "HEAD:handoffs/stamp.md") == "stamp", "the stamp is on HEAD"
    if "kept on" in result.stderr:
        named = _mine_named_on_head(box, c, result.stderr)
        assert named, result.stderr
        assert all(on for _, on in named), f"called kept, and not on HEAD: {named}"
    _settled(box, c)


# 291 of lane openRepoTools-3's review of #307: this write's own commit is
# known by what it is, and the drop takes it alone. The window is the one
# `git commit` call: a `git` first on PATH lands an unlocked writer's commit
# just after it (E8), just before it, or with this write's own message.
COMMIT_CALL = '*" commit -q -m LANES("*'


def test_a_commit_landing_just_after_this_writes_commit_is_never_taken_for_it_exit_6(box: Box):
    """291's E8: the write took its own sha from `rev-parse HEAD` after
    `git commit`, so an unlocked writer's stamp landing between the two was
    taken as this write's. The HEAD check and the drop's compare-and-swap
    both passed on the stamp's sha, the replay dropped it (exit 0, "Commit
    <the stamp> is dropped"), and `stamp.md` went from the working tree, on
    no branch and not on origin. Now this write's commit is the one under
    the stamp, the replay finds a commit on top of it, and both are kept on
    HEAD and named (6), with nothing dropped."""
    c = box.seam()
    box.race()
    env = _git_shim(box, COMMIT_CALL, after=_stamp(c))
    result = box.helper("set-row-state", LANE, STATE, **env)
    assert (box.root / "fired").exists(), "the stamp landed just after this write's commit"
    assert result.returncode == 6, result.stderr
    err = result.stderr
    stamp, mine = box.head(c), box.git("-C", str(c), "rev-parse", "HEAD~1").strip()
    assert box.subject(c) == STAMP_SUBJECT
    assert box.subject(c, "HEAD~1").startswith(f"LANES({LANE}@"), "this write's commit is under the stamp"
    assert f"Commit {stamp} is dropped" not in err, "the stamp was taken for this write's commit"
    assert f"HEAD is {stamp}, not this write's commit {mine}" in err, err
    assert "push refused (attempt 1 of 6)" not in err, "nothing is replayed"
    assert (c / "handoffs" / "stamp.md").is_file(), "the other writer's file is still there"
    assert len(box.unpublished(c)) == 2, "both kept on HEAD, for the publish act"
    _settled(box, c)


def test_a_commit_landing_just_before_this_writes_commit_is_never_dropped_with_it_exit_6(box: Box):
    """291's other half, the window lane 3's sketch left: a stamp landing
    just before `git commit` is UNDER this write's commit. HEAD is this
    write's commit, so the HEAD check passed, and the drop to origin's tip
    took the stamp with it: `stamp.md` gone, the write replayed (0). Now the
    drop is made only where this write's commit sits on origin's history;
    here it sits on a commit it did not make, so both are kept on HEAD and
    named (6), and nothing is replayed."""
    c = box.seam()
    box.race()
    env = _git_shim(box, COMMIT_CALL, before=_stamp(c))
    result = box.helper("set-row-state", LANE, STATE, **env)
    assert (box.root / "fired").exists(), "the stamp landed just before this write's commit"
    assert result.returncode == 6, result.stderr
    err = result.stderr
    mine = box.head(c)
    assert box.subject(c).startswith(f"LANES({LANE}@"), "HEAD is this write's commit"
    assert box.subject(c, "HEAD~1") == STAMP_SUBJECT, "the stamp is under it"
    assert "sits on 1 commit(s) it did not make" in err, err
    assert f"it and they are kept on HEAD (Amendment 23 S4): {mine}" in err, err
    assert "push refused (attempt 1 of 6)" not in err, "nothing is replayed"
    assert (c / "handoffs" / "stamp.md").is_file(), "the other writer's file is still there"
    assert len(box.unpublished(c)) == 2, "both kept on HEAD, for the publish act"
    _settled(box, c)


def test_a_commit_with_this_writes_own_message_made_with_it_is_no_answer_exit_6(box: Box):
    """291's last word, "also match the subject": where another commit was
    made in the moment of this write's, its own commit is the one with its
    message. Two with that message are no answer, so nothing is guessed:
    nothing is pushed, both are kept on HEAD, and it says so (6)."""
    c = box.seam()
    box.race()
    cq = shlex.quote(str(c))
    same = ('    m=""; prev=""; for a in "$@"; do [ "$prev" = -m ] && m="$a"; prev="$a"; done' + "\n" +
            f"    printf 'same' > {cq}/handoffs/same.md" + "\n" +
            f"    {{git}} -C {cq} add -- handoffs/same.md" + "\n" +
            f'    {{git}} -C {cq} commit -q -m "$m" -- handoffs/same.md' + "\n")
    env = _git_shim(box, COMMIT_CALL, before=same)
    result = box.helper("set-row-state", LANE, STATE, **env)
    assert (box.root / "fired").exists(), "a commit with this write's message landed with it"
    assert result.returncode == 6, result.stderr
    err = result.stderr
    assert box.subject(c) == box.subject(c, "HEAD~1"), "two commits, one message"
    assert "cannot be told from another made in this checkout" in err, err
    assert box.pushes() == 0, "nothing is pushed on a guess"
    assert len(box.unpublished(c)) == 2, "both kept on HEAD"
    _settled(box, c)


# NIT 3 of rv1b-c2's re-check, re-aimed by SHOULD C: the drop's two refusals
# that had no case. `commit`'s carry form dropped with `reset -q --mixed` at
# d9ff4e6; since SHOULD C it takes the same compare-and-swap, then the index
# alone (`read-tree -m -i`). The keep form's tree step (`read-tree -m -u`) is
# SHOULD C's own, so d9ff4e6 has nothing for its pattern to match.
CARRY_DROP_STARTS = '*" reset -q --mixed "*|*" update-ref -m lanes-edit: the replay drops "*'
TREE_STEP = '*" read-tree -m -u "*'
STAMP_SUBJECT = "handoff(repoS4-2@Eagle): a stamp from an unlocked writer"


def test_a_commit_landing_before_the_carry_forms_drop_is_never_dropped_exit_6(box: Box):
    """`commit`'s carry form gives its commit back as the hand edit it was,
    and its drop is guarded as the keep form's is: an unlocked commit landing
    on top just before it makes the compare-and-swap fail, and nothing moves.
    The hand-edit commit and the one on top of it are kept on HEAD and named
    (6), the working tree is clean, and nothing is replayed. A drop that took
    the carry form's branch without the compare-and-swap would drop the
    stamp with it."""
    c = box.seam()
    box.peer_prepares(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                      _row(NEIGHBOUR, uuid=UUID2, state="LIVE · landed mid-push"),
                      "a peer's row lands first")
    box.race(prepared=True)
    box.hand_edit(c)
    env = _git_shim(box, CARRY_DROP_STARTS, before=_stamp(c))
    result = box.helper("commit", "the hand edit", LANES_LANE=LANE, **env)
    assert (box.root / "fired").exists(), "the commit landed in the window"
    assert result.returncode == 6, result.stderr
    err = result.stderr
    assert "between the replay's HEAD check and its drop" in err, err
    assert "is no longer HEAD, so it is not replayed" in err
    assert "push refused (attempt 1 of 6)" not in err, "nothing is replayed"
    assert box.subject(c) == STAMP_SUBJECT
    assert box.subject(c, "HEAD~1") == f"LANES({LANE}@Eagle): the hand edit", "the hand-edit commit is under it"
    assert "LIVE · a hand edit" in box.git("-C", str(c), "show", f"HEAD:{REGISTER}"), "the hand edit is on HEAD"
    assert box.git("-C", str(c), "status", "--porcelain").strip() == "", "nothing was turned back into an edit"
    assert len(box.unpublished(c)) == 2, "both kept on HEAD, for the publish act"
    assert "the replay drops" not in box.git("-C", str(c), "reflog", "refs/heads/main"), "the branch never moved"
    _settled(box, c)


def test_a_drop_whose_tree_step_and_put_back_are_both_refused_is_named_off_HEAD_exit_6(box: Box):
    """The drop moved the branch, git refused the tree step after it, and an
    unlocked writer committed on the branch in that moment, so the put-back's
    compare-and-swap is refused too. Nothing more is moved: the other writer's
    commit stays HEAD, and this write's commit is named as off HEAD with the
    reflog that names it (6), never as kept. A `git` first on PATH makes the
    moment exact: at the tree step it commits the stamp, then refuses."""
    c = box.seam()
    box.race()
    refuse = "    echo 'error: the tree step is refused here (the test)' >&2; exit 1" + "\n"
    env = _git_shim(box, TREE_STEP, before=_stamp(c) + refuse)
    result = box.helper("set-row-state", LANE, STATE, **env)
    assert (box.root / "fired").exists(), "the drop's tree step ran, with the stamp landing first"
    assert result.returncode == 6, result.stderr
    err = result.stderr
    assert "could be neither dropped cleanly nor put back" in err, err
    assert "is off HEAD" in err
    assert f"git -C {c} reflog -5" in err
    assert "kept on" not in err, "nothing of this write's is said to be kept"
    assert "push refused (attempt 1 of 6)" not in err, "nothing is replayed"
    named = _mine_named_on_head(box, c, err)
    assert named, err
    assert not any(on for _, on in named), f"named, and on HEAD: {named}"
    reflog = box.git("-C", str(c), "reflog", "--format=%H", "refs/heads/main").split()
    assert named[0][0] in reflog, "the reflog names this write's commit"
    assert box.subject(c) == STAMP_SUBJECT, "the other writer's commit is still HEAD"
    assert box.git("-C", str(c), "show", "HEAD:handoffs/stamp.md") == "stamp"
    assert _set(STATE) not in box.origin_register(), "nothing of this write's reached origin"
    _settled(box, c)


CARRY_TREE_STEP = '*" read-tree -m -i "*'


def test_a_carry_forms_drop_whose_tree_step_is_refused_keeps_the_commit_exit_6(box: Box):
    """`commit`'s carry form drops its commit to the parent in the index alone
    (`read-tree -m -i`), to give the change back as the hand edit it was.
    Where git refuses that step, the branch is put back on this write's
    commit by a compare-and-swap from where the drop put it, and the commit
    is kept on HEAD and named (6): the hand edit is in it, nothing is turned
    back into an edit, and nothing is replayed. A `git` first on PATH refuses
    the step."""
    c = box.seam()
    box.peer_prepares(REGISTER, _row(NEIGHBOUR, uuid=UUID2),
                      _row(NEIGHBOUR, uuid=UUID2, state="LIVE · landed mid-push"),
                      "a peer's row lands first")
    box.race(prepared=True)
    box.hand_edit(c)
    refuse = "    echo 'error: the tree step is refused here (the test)' >&2; exit 1" + "\n"
    env = _git_shim(box, CARRY_TREE_STEP, before=refuse)
    result = box.helper("commit", "the hand edit", LANES_LANE=LANE, **env)
    assert (box.root / "fired").exists(), "the carry form's tree step ran"
    assert result.returncode == 6, result.stderr
    err = result.stderr
    assert "git said: error: the tree step is refused here (the test)" in err, err
    named = re.search(r"could not be turned back into the hand edit it was to replay it, "
                      r"so it is kept on HEAD: ([0-9a-f]{40}) ", err)
    assert named, err
    assert named.group(1) == box.head(c), "the commit it names is HEAD: the branch was put back"
    assert box.subject(c) == f"LANES({LANE}@Eagle): the hand edit"
    assert "LIVE · a hand edit" in box.git("-C", str(c), "show", f"HEAD:{REGISTER}"), "the hand edit is on HEAD"
    assert box.git("-C", str(c), "status", "--porcelain").strip() == "", "nothing was turned back into an edit"
    assert "the replay puts back" in box.git("-C", str(c), "reflog", "refs/heads/main")
    assert "push refused (attempt 1 of 6)" not in err, "nothing is replayed"
    assert "LIVE · a hand edit" not in box.origin_register(), "nothing of this write's reached origin"
    assert len(box.unpublished(c)) == 1, "the one commit is kept, for the publish act"
    _settled(box, c)


# ------------------------------- a file the write edits in place (slice 2a's A37)

def _helper_naming(box: Box, rel: str) -> list:
    """A copy of the helper whose one load-time line names `rel` as the file
    this write edits in place, as slice 2a's `write-handoff` names its handoff
    for `--stamp` and `--prepend`. No verb of slice 1b sets the global, so the
    copy is how 1b tests its check: it differs from the helper in that one
    line, and sits in a folder of its own with the shipped `repos.tsv` beside
    it, as an install places it."""
    src = (REPO / "lanes-edit.sh").read_text(encoding="utf-8")
    line = 'CP_KEEP_IF_GONE=""\n'
    assert src.count(line) == 1, "the global is set at load, once"
    bindir = box.root / "bin-a37"
    bindir.mkdir()
    shutil.copy2(REPO / "repos.tsv", bindir / "repos.tsv")
    copy = bindir / "lanes-edit.sh"
    copy.write_text(src.replace(line, f"CP_KEEP_IF_GONE={shlex.quote(rel)}\n"), encoding="utf-8")
    copy.chmod(0o755)
    return ["bash", str(copy)]


@pytest.mark.parametrize("peer", ["deletes-it", "keeps-it", "never-had-it", "creates-it"])
def test_a_file_the_write_edits_in_place_deleted_on_origin_keeps_the_commit_exit_6(box: Box, peer: str):
    """A37 of slice 2a, whose global is 1b's: a peer that deletes the file a
    write edits in place, while that write's push is in flight, left the
    replay nothing to write into, and the write only in the commit it
    dropped. With `CP_KEEP_IF_GONE` naming the file, the commit is kept on
    HEAD and named (6) before anything is dropped: the write is in this
    checkout, origin has no such file, and one commit is unpublished. The
    lane's own log stands in for the handoff here; the check is the same for
    any path. A peer's commit that leaves the file where it was is an
    ordinary lost race, replayed and landed (0), and so is a named file the
    write's base never had: it is never "gone". That holds for a file nobody
    has, and, rv1b-c3's NIT F, for one THE WRITE ITSELF CREATES (a lane's
    first log line: origin lacks the log both before and after, and the
    write's commit has it), which the `^` in `$1^:<file>` is for: asked of
    the commit and not its base, that file would read as deleted."""
    log = f"lanes/log/{LANE}.md"
    if peer == "creates-it":
        # Origin has no log for the lane when this write starts: the write
        # creates it, and the peer that beats it to the push touches nothing.
        box.git("-C", str(box.peer), "rm", "-q", "--", log)
        box.git("-C", str(box.peer), "commit", "-q", "-m", f"the lane has no log yet: {log}")
        box.git("-C", str(box.peer), "push", "-q", "origin", "main")
    c = box.seam()
    if peer == "creates-it":
        assert not (c / log).exists(), "the write's base has no log"
    rel = "handoffs/repoS4/never-had-it.md" if peer == "never-had-it" else log
    if peer == "deletes-it":
        box.git("-C", str(box.peer), "rm", "-q", "--", log)
        box.git("-C", str(box.peer), "commit", "-q", "-m", f"a peer deletes {log}")
        box.race(prepared=True)
    else:
        box.race()
    cmd = _helper_naming(box, rel)
    result = subprocess.run([*cmd, "log", "NOTED", f"lane:{LANE}", "the in-place write", *HOME_FLAG],
                            env=dict(box.env, LANES_LANE=LANE, LANES_SESSION=UUID), cwd=str(box.root),
                            capture_output=True, text=True, timeout=180, check=False)
    err = result.stderr
    if peer == "deletes-it":
        assert result.returncode == 6, err
        sha = box.head(c)
        assert f"origin's copy of {log} was deleted while this write's push was in flight" in err, err
        assert f"kept on HEAD: {sha}" in err
        assert "push refused (attempt" not in err, "nothing is dropped or replayed"
        assert "the in-place write" in (c / log).read_text(encoding="utf-8"), "the write is in this checkout"
        assert log not in box.git("--git-dir", str(box.origin), "ls-tree", "-r", "--name-only", "main").split(), \
            "origin has no such file"
        assert [line.split()[1] for line in box.unpublished(c)] == [sha], "one commit unpublished, this write's"
    else:
        assert result.returncode == 0, err
        assert "push refused (attempt 1 of 6)" in err
        assert "pushed origin/main (attempt 2)" in err
        assert "the in-place write" in box.origin_file(log)
        assert box.unpublished(c) == []
    _settled(box, c)
