# SPDX-License-Identifier: Apache-2.0
"""Amendment 23 S4: after the edit, commit by pathspec, push with no pull, and
read back — and a refused push replays the one edit.

`commit_publish` commits the write's own pathspecs, pushes `main` with no
pull, and fetches origin to confirm the commit is on it: confirmed is 0 and
`pushed`; a push that went (or timed out) and could not be confirmed is 3,
`pushed, not confirmed: <sha>`, never success. A push refused because origin
moved drops this write's commit (`reset --keep`, the only unpublished commit
S3 allows) and runs the verb again from the top on origin's new tip, so the
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
import shlex
import shutil
from pathlib import Path

import pytest

from a23_box import REGISTER, RegisterBox, register_text
from conftest import WINDOWS_SKIP

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
    assert len(new) == 2 and new[1] == "a peer's row lands first", new
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
    assert "LIVE · rewritten by a peer" in register and "reseeded" not in register
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
    assert "1 unpublished commit(s)" in after.stderr and f"+ {sha}" in after.stderr
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


def test_replay_refused_by_a_change_in_the_way_keeps_the_commit_exit_6(box: Box):
    """`reset --keep` never runs over an uncommitted change: a hand edit of
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
    assert "LIVE · moved on origin" in register and "LIVE · a hand edit" in register
    assert box.head(c) == box.origin_head()
    assert box.git("-C", str(c), "status", "--porcelain").strip() == ""
    saved = list((c / ".git" / "lanes-edit").glob("hand-edit-*.diff"))
    assert len(saved) == 1 and "a hand edit" in saved[0].read_text(encoding="utf-8")
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
    assert "no longer applies" in result.stderr and str(saved[0]) in result.stderr
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
    assert "LIVE · landed mid-push" in register and "LIVE · a hand edit" in register
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
        assert words in result.stderr and "Nothing was written." in result.stderr
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
    assert "refs/heads/archive/" in err and f"git -C {c} reset --keep origin/main" in err
    assert "push" not in box.net_ops()
    assert box.origin_head() == tip and box.head(c) == shas[-1]
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
    assert "push refused (attempt 1 of 6)" not in result.stderr, "no reset was made"
    assert box.subject(c) == "handoff(repoS4-2@Eagle): a stamp from an unlocked writer"
    assert box.subject(c, "HEAD~1").startswith(f"LANES({LANE}@"), "this write's commit is under it"
    assert (c / "handoffs" / "stamp.md").is_file(), "the other writer's file is still there"
    assert len(box.unpublished(c)) == 2, "both kept on HEAD, for the publish act"
    _settled(box, c)
