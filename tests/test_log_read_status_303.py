# SPDX-License-Identifier: Apache-2.0
"""A READ OF A LANE'S LOG THAT COULD NOT BE MADE IS NEVER A LANE WITH NO LOG
(opensoft/openRepoTools#303, which #290 listed for a ruling and left open).

#290 gave `lane_log_events` an opt-in `checked` argument, so that a read of a
lane's log says whether it HAPPENED: a log `origin`'s tree names and git could
not show is 1, and so is a tree that could not be listed to ask; a path the
tree does not name is no log and 0; with no `origin`, a log directory that
cannot be searched and a file that will not open are 1. Only the named
worktree read and `lane-state` ask for it. Every other reader of a lane's log
takes the parser's status, which `git show ... | parse_log_stream` makes 0
over a `git show` that failed, so it answers a log nobody read exactly as it
answers a lane with none: 8. These cases hold the issue's Suggested fix to
what it says, for every reader that lives in `lanes-edit.sh`:

  * each NAMED read - `lane-dir`, `lane-profile`, `lane-agent`,
    `lane-transcript`, `lane-last`, `history <lane>`, `binding`,
    `last-session`, `resolve-home`, `lane-objects`, `who --lane` and
    `request-handoff` - answers 1 with a sentence for a log that could not be
    read, in each of the five shapes a read can fail in (the published blob,
    the published log tree, and with no `origin` a directory that lists and
    cannot be searched, one that cannot be listed, and a file that will not
    open), and still answers 8 for a lane with no log at all;
  * the readers that find a lane's control root by its log - `lane-trees`,
    `set-lane-state`, `set-lane-tree` and `lane-reconcile` - say so, and file
    nothing under `$PROJECTS_ROOT/.lane-state`, the third rung, where a failed
    read used to put every lane's records;
  * with no `origin`, a log directory that can be listed and not searched
    drops the lanes that have only a log from `lanes` and says nothing.

`lane-end`'s gate reads `lane-objects`, and 8 there is "this lane has no
object log (pre-cutover)": a lane whose log could not be read, and which may
hold an open claim, was ended on it. That gate is run here, and it is
RELEASE-BLOCKING. `lane-start`, `lane-handoff`, `lane-worktrees` and the two
skills each carry a `case` for the 1 and are not run here; what each does with
it is read from its own `case`.

And the guards the review of #303 asked for beside them: `lane-objects` answers
from the read it proved and not a later one (544); a write that needs no home -
a swap's `PAUSED`, a `NOTED` - still lands over a log nobody could read, and
`--home` and a `#n` are refused (542, 546); the `SessionStart` hook's `open:`
line says the log could not be read (546); and a lifecycle follow-up over a log
it could not read for its root moves nothing and says why (R4), while the same
follow-up over a lane that has no root at all, which is not a log nobody read,
says nothing (lane 3's review of R7, 1002).

AND R7, BRETT HEAP'S RULING "Write swap, name the gap", with the items held for
it (the review of #303's 541 and 546, and lane 3's review of R7's change,
651-662). The restart intent is kept beside the directory the lane's log
records, so a log nobody could read hid an intent in flight: `restart-intent`
said 8, "no restart in flight", and `set-restart-intent` filed beside the
third rung. It is 10 now, never 8, in each shape a read fails in, while a log
that was read still answers 8 or 0. An ordinary `lane-handoff` over such a log
writes the PAUSED record, the register line, the row and the restart line,
publishes no handoff file, and says so on stdout; `--exit` writes them, types
nothing and says at its gate what to wait on before publishing (lane 3's
ruling 6367537964, question 1), and `--restart` refuses before it writes
anything. `lane-start`
refuses at its restart fence and says the log is why, `rename-lane` refuses
before the mutex rather than leave the lane's records under its old name, and
`lane-objects` with nowhere to keep its read's warnings is no answer either.
`skills/handoff/SKILL.md`'s twin of the handoff is held in
`test_handoff_skill_303.py`.

Every case runs on `test_lanes_index`'s own estate and its helpers, and builds
on `test_named_read_unreadable_290`'s way of making a log unreadable.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import subprocess
import types

import pytest

from conftest import REPO, WINDOWS_SKIP
from test_lane_start_claude_current import FAKE_TMUX
from test_lane_start_claude_current import LANE as START_LANE
from test_lane_start_claude_current import Sandbox as StartSandbox
from test_lanes_index import (HEADS, LANES_EDIT, SHOW_LOG_B1, UUID_A1B, UUID_B1, US, _git_shim,
                              _shim_calls, _sidecar, _unreadable, inv)

__all__ = ["inv"]  # the fixture, imported so that pytest finds it here

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

LANE = "repoB-1"
NO_LOG_LANE = "repoC-1"  # a row, and no log at all
LOG_B1 = "origin/main:lanes/log/repoB-1.md"
LOG_TREE = "origin/main:lanes/log"
NO_GIT = {"LANES_NO_GIT": "1"}
REQUESTER = "cccccccc-0009-4000-8000-00000000c009"

#: WORDS A READ MAY NEVER SAY OF A LOG IT COULD NOT READ: each is what `who
#: --lane` and `request-handoff` said of repoB-1 over one, and a fact about a lane
#: whose log was read. Whole sentences, so that a refusal which names them in
#: order to say what the failure is NOT does not trip them.
FALSE_CLAIMS = ("no log for repoB-1", "is FREE — its last lane-kind line")


def _this_account_gets_in_anyway(target, what: str) -> bool:
    """root reads a mode-000 file and searches a directory whatever its mode, and
    then there is nothing to prove with a `chmod`."""
    return os.access(target, os.R_OK) if what == "file" else os.access(target, os.X_OK)


def _a_lane_with_a_whole_record(inv):
    """repoB-1 RESUMED in a checkout of its own, its RESUMED line carrying every
    sub-field a reader asks of a lane's log (`dir`, `profile`, `agent` and
    `transcript`) and no release after it, so the lane is BOUND; one tree
    sidecar and a SWAPPING snapshot filed by `set-lane-state` under
    `<parent of that dir>/.lane-state`. No override names a control root, so
    where its records are is its log's `dir` and nothing else. Returns the
    environment every read runs in, the checkout, and the snapshot."""
    away = inv.root / "elsewhere"
    checkout = away / "repoB"
    checkout.mkdir(parents=True)
    log = inv.e.wip / "lanes" / "log" / f"{LANE}.md"
    log.write_text(log.read_text(encoding="utf-8") +
                   f"RESUMED — lane {LANE}, session {UUID_B1}@Eagle, 2026-10-05T00:00:00Z, "
                   f"lane:{LANE} → dir {checkout}; profile team-02a; agent claude; "
                   f"transcript {UUID_B1}\n", encoding="utf-8")
    inv.e._git("add", "-A")
    inv.e._git("commit", "-q", "-m", "repoB-1 resumed in a checkout of its own")
    inv.e._git("push", "-q", "origin", "main")
    _sidecar(away / ".lane-state", LANE, HEADS[LANE])
    env = {"LANES_LANE_STATE_ROOT": None, "LANES_NO_FETCH": "1"}
    put = inv.e.edit("set-lane-state", LANE, "SWAPPING", "--operation", "op-test-b1", env=env)
    assert put.returncode == 0, put.stderr
    snap = away / ".lane-state" / LANE / "lane-state.yaml"
    assert snap.is_file(), snap  # where the log's `dir` places it: not vacuous
    return env, checkout, snap


def _exactly(*lines):
    return lambda res, _ck: res.stdout.strip() in lines


#: EVERY READ OF A LANE'S LOG THAT LIVES IN `lanes-edit.sh`:
#: (name, argv for a lane, what it prints of a whole log, the arm's OWN words for
#: a log that could not be read, and the exit code). The words are each arm's
#: own sentence and never a phrase any read says: `log_events`' note for a file
#: that will not open ("the file could not be read") names the lane's log too,
#: and a check met by it passed an arm that said nothing (the review of #303,
#: 547). The lifecycle reads answer 10 beside `lane-state`, which #290 made 10
#: for this: "the record may be there and nobody could look" (R22).
READS = [
    ("lane-dir", lambda lane: ("lane-dir", lane),
     lambda res, ck: res.stdout.strip() == str(ck),
     "lane-dir could not read lane repoB-1's log", 1),
    ("lane-profile", lambda lane: ("lane-profile", lane), _exactly("team-02a"),
     "lane-profile could not read lane repoB-1's log", 1),
    ("lane-agent", lambda lane: ("lane-agent", lane), _exactly("claude"),
     "lane-agent could not read lane repoB-1's log", 1),
    ("lane-transcript", lambda lane: ("lane-transcript", lane), _exactly(UUID_B1),
     "lane-transcript could not read lane repoB-1's log", 1),
    ("lane-last", lambda lane: ("lane-last", lane),
     lambda res, _ck: res.stdout.startswith(f"RESUMED\t2026-10-05T00:00:00Z\t{UUID_B1}\t"),
     "lane-last could not read lane repoB-1's log", 1),
    ("history", lambda lane: ("history", lane),
     lambda res, _ck: "a log with no row" in res.stdout,
     "history could not read lane repoB-1's log", 1),
    ("binding", lambda lane: ("binding", lane),
     lambda res, _ck: len(res.stdout.rstrip("\n").split("\t")) == 8,
     "binding could not read lane repoB-1's object log", 1),
    ("last-session", lambda lane: ("last-session", lane), _exactly(UUID_B1),
     "last-session could not read the register or the log for repoB-1", 1),
    ("resolve-home", lambda lane: ("resolve-home", lane), _exactly("opensoft/repoB"),
     "lane repoB-1's object log could not be read, so its home is NOT established", 1),
    ("lane-objects", lambda lane: ("lane-objects", lane),
     lambda res, _ck: "OPENED" in res.stdout and "opensoft/repoB#3" in res.stdout,
     "lane-objects could not read lane repoB-1's object log", 1),
    ("who --lane", lambda lane: ("who", "--lane", lane),
     lambda res, _ck: "opensoft/repoB#3" in res.stdout,
     "UNKNOWN  lane repoB-1's object log could not be read, so what it holds open is NOT "
     "established", 1),
    ("request-handoff", lambda lane: ("request-handoff", lane, "--no-wait", "--dry-run",
                                      "--session", REQUESTER),
     lambda res, _ck: "PLAN:" in res.stderr,
     "request-handoff could not read lane repoB-1's object log", 1),
    ("lane-trees", lambda lane: ("lane-trees", lane),
     lambda res, _ck: res.stdout.startswith(f"c0-{LANE}{US}/nowhere/{LANE}/w{US}"),
     "lane repoB-1's object log could not be read, so the directory its worktree inventory "
     "is kept beside is NOT established", 10),
    ("lane-state", lambda lane: ("lane-state", lane),
     lambda res, _ck: res.stdout.startswith("state\tSWAPPING\n"),
     "lane repoB-1's object log could not be read, so the directory its lifecycle snapshot "
     "is kept beside is NOT established", 10),
]

#: WHAT A LANE WITH NO PUBLISHED LOG STILL ANSWERS: 8, "none". `last-session`
#: answers out of the row's own session cell first, which repoC-1 has.
NO_LOG_ANSWERS = {
    "lane-dir": 8, "lane-profile": 8, "lane-agent": 8, "lane-transcript": 8,
    "lane-last": 8, "history": 8, "binding": 8, "last-session": 0, "resolve-home": 8,
    "lane-objects": 8, "who --lane": 8, "request-handoff": 8, "lane-trees": 8,
    "lane-state": 8,
}


def _said(res) -> str:
    """The last line a read said that is its own: not the 'not fetching' note
    and not the parser's complaints about the seed's deliberately bad lines."""
    own = [line for line in res.stderr.splitlines()
           if line.strip() and "not fetching" not in line and "unreadable" not in line]
    return (own[-1] if own else "")[:150]


def _failures(inv, env) -> list[str]:
    """Every read of repoB-1's log, asked for it where its log could not be
    read: one line for each that does not answer with its code and its own
    sentence, or that says what a lane with a log could not be said to have."""
    problems = []
    for name, argv, _whole, words, code in READS:
        res = inv.e.edit(*argv(LANE), env=env)
        text = res.stdout + res.stderr
        said = words in text
        false = [claim for claim in FALSE_CLAIMS if claim in text]
        if res.returncode != code or not said or false:
            problems.append(f"{name}: exit {res.returncode} (wanted {code}); "
                            f"{'said so' if said else 'said nothing of it'}"
                            f"{'; claimed ' + repr(false) if false else ''}; "
                            f"stdout {res.stdout.strip()[:60]!r}; stderr {_said(res)!r}")
    return problems


# ---------------------------------------------------------------- the controls


def test_a_log_git_can_show_answers_what_it_records(inv):
    """THE CONTROL FOR EVERY CASE BELOW: with repoB-1's log whole, each read
    answers what the log records, so a read that says 1 below says it of a log
    it could not read and not of one it had nothing to say about."""
    env, checkout, _snap = _a_lane_with_a_whole_record(inv)
    wrong = []
    for name, argv, whole, _words, _code in READS:
        res = inv.e.edit(*argv(LANE), env=env)
        if res.returncode != 0 or not whole(res, checkout):
            wrong.append(f"{name}: exit {res.returncode}; stdout {res.stdout.strip()[:80]!r}; "
                         f"stderr {_said(res)!r}")
    assert not wrong, "\n".join(wrong)
    rec = inv.e.edit("lane-reconcile", LANE, env=env)
    assert rec.returncode == 0, rec.stderr
    verdict = [f for f in (line.split(US) for line in rec.stdout.splitlines())
               if f[0] == "VERDICT"]
    assert [v[1] for v in verdict] == ["interrupted-swap"], rec.stdout


def test_a_lane_with_no_published_log_still_answers_none_to_every_read(inv):
    """A LOG THAT IS NOT THERE IS NOT ONE THAT COULD NOT BE READ. repoC-1 has a
    row and no log: its tree does not name one, and every read of it is the 8
    it always was - which a fix that makes a failed read 1 must not turn into
    1. (`last-session` answers from the row's own session cell, where the log
    is the second source and is not asked.)"""
    env, _checkout, _snap = _a_lane_with_a_whole_record(inv)
    wrong = []
    for name, argv, _whole, _words, _code in READS:
        res = inv.e.edit(*argv(NO_LOG_LANE), env=env)
        want = NO_LOG_ANSWERS[name]
        if res.returncode != want:
            wrong.append(f"{name}: exit {res.returncode} (wanted {want}); "
                         f"stdout {res.stdout.strip()[:60]!r}; stderr {_said(res)!r}")
    assert not wrong, "\n".join(wrong)
    rec = inv.e.edit("lane-reconcile", NO_LOG_LANE, env=env)
    assert rec.returncode == 0, rec.stderr
    assert f"VERDICT{US}no-state" in rec.stdout, rec.stdout


# --------------------------------------------- a log git could not read: published


def test_a_published_log_whose_blob_git_could_not_show_is_a_failed_read_for_every_read(inv):
    """THE ISSUE'S PROBE: repoB-1's blob is a loose object in the clone, moved
    aside, so `git show origin/main:lanes/log/repoB-1.md` fails (128) while
    `git ls-tree` still names the path - a clone with a damaged object, or a
    partial clone that cannot fetch it. Each read said 8, "none", and nothing
    reached stderr: no caller could tell it from a lane with no log."""
    env, _checkout, _snap = _a_lane_with_a_whole_record(inv)
    with _unreadable(inv.e, LOG_B1):
        problems = _failures(inv, env)
    assert not problems, "\n" + "\n".join(problems)


def test_a_published_log_tree_git_could_not_list_is_a_failed_read_for_every_read(inv):
    """THE SAME WHERE THE TREE OF THE LOGS CANNOT BE LISTED (the review of
    #290, SHOULD-1(b)). `git show` fails there as it does for a path the tree
    does not name, and the `ls-tree` of the log's own path that tells the two
    apart fails as well: that is a read that did not happen. Every read took it
    for a lane with no log."""
    env, _checkout, _snap = _a_lane_with_a_whole_record(inv)
    with _unreadable(inv.e, LOG_TREE):
        problems = _failures(inv, env)
    assert not problems, "\n" + "\n".join(problems)


# ------------------------------------------------- a log git could not read: no origin


@pytest.mark.parametrize("what,mode", [("dir", 0o400), ("dir", 0o000), ("file", 0o000)],
                         ids=["dir-400", "dir-000", "file-000"])
def test_a_log_with_no_origin_that_will_not_open_is_a_failed_read_for_every_read(inv, what, mode):
    """WITH NO `origin` (`LANES_NO_GIT=1`) THE LOG IS THIS CHECKOUT'S FILE. A
    log directory that can be listed and not searched (`r--`) hides the file
    from `-f`, and one that cannot be listed hides it from `ls`: each read found
    no log and said 8. A file that will not open went through the parser's own
    status instead: `history` exited 2, awk's, which its `case` reads as the
    two-logs refusal and says nothing of, `lane-objects` said "this lane holds
    nothing" over it, and `lane-trees` and `last-session` said 8."""
    env, checkout, _snap = _a_lane_with_a_whole_record(inv)
    env = {**env, **NO_GIT}
    whole = inv.e.edit("lane-dir", LANE, env=env)
    assert whole.returncode == 0 and whole.stdout.strip() == str(checkout), whole.stderr
    logdir = inv.e.wip / "lanes" / "log"
    target = logdir if what == "dir" else logdir / f"{LANE}.md"
    before = target.stat().st_mode & 0o777
    target.chmod(mode)
    try:
        if _this_account_gets_in_anyway(target, what):
            pytest.skip(f"this account reads a mode-{mode:03o} {what} (root): nothing to prove")
        problems = _failures(inv, env)
    finally:
        target.chmod(before)
    assert not problems, "\n" + "\n".join(problems)


# -------------------------------------- the lifecycle reads, which find a root by the log


@pytest.mark.parametrize("verb", ["set-lane-state", "set-lane-tree"])
def test_a_lifecycle_write_over_a_log_git_could_not_read_files_nothing_at_the_third_rung(inv, verb):
    """A WRITER THAT COULD NOT FIND ITS ROOT WRITES NOTHING (the issue's probe).
    `lane_control_root` threw a failed read of the lane's `dir` away, so the
    root fell to `$PROJECTS_ROOT/.lane-state/<lane>`, the rung for a lane whose
    record names no directory, and `set-lane-state` and `set-lane-tree` exited
    0 and filed their records THERE, beside the real root, whose own
    `lane-state.yaml` stayed as it was. A start or a handoff that ran over such
    a log would have filed its lifecycle records in a place no reader looks."""
    env, _checkout, snap = _a_lane_with_a_whole_record(inv)
    real = snap.parent
    third = inv.e.home / "projects" / ".lane-state" / LANE
    first, again = (
        (("set-lane-state", LANE, "RUNNING", "--operation", "op-test-b1b"),
         ("set-lane-state", LANE, "SWAPPED"))
        if verb == "set-lane-state" else
        (("set-lane-tree", LANE, str(inv.run_tree), "--checkout", str(inv.repo)),
         ("set-lane-tree", LANE, str(inv.dirty_tree), "--checkout", str(inv.repo))))
    ok = inv.e.edit(*first, env=env)
    assert ok.returncode == 0, (ok.stdout, ok.stderr)  # the write lands where the log's `dir` places it
    assert not third.exists(), list(third.rglob("*"))

    def files() -> dict:
        return {str(p.relative_to(real)): p.read_bytes() for p in real.rglob("*") if p.is_file()}

    before = files()
    with _unreadable(inv.e, LOG_B1):
        res = inv.e.edit(*again, env=env)
    problems = []
    if res.returncode != 1:
        problems.append(f"{verb} exited {res.returncode}, not 1; stdout {res.stdout.strip()[:60]!r}")
    if f"lane {LANE}'s object log could not be read" not in res.stderr:
        problems.append(f"it did not say that the lane's log could not be read: {_said(res)!r}")
    if third.exists():
        problems.append(f"it filed records at the third rung: "
                        f"{sorted(str(p.relative_to(third)) for p in third.rglob('*') if p.is_file())}")
    if files() != before:
        problems.append("it changed the real root's records")
    assert not problems, "\n" + "\n".join(problems)


def test_a_reconcile_over_a_log_git_could_not_read_is_indeterminate_not_no_state(inv):
    """A LOG NOBODY COULD READ IS NOT A LANE WITH NO SNAPSHOT (the issue's
    probe, and `lane_reconcile`'s own comment on `lane_payload_field`'s 1).
    `lane_control_root` threw the failed read away, so `lane_reconcile` took the
    third rung's root, found no snapshot, no tree and no binding, and said
    `no-state`, "this lane has no lifecycle snapshot: it has not started or
    handed off under this capability", for a lane whose real root holds a
    SWAPPING snapshot - exit 0, and nothing on stderr. It is `indeterminate`,
    whose reason names the log, with no state, no binding and no root of a lane
    that was never read."""
    env, _checkout, _snap = _a_lane_with_a_whole_record(inv)
    third = inv.e.home / "projects" / ".lane-state" / LANE
    with _unreadable(inv.e, LOG_B1):
        res = inv.e.edit("lane-reconcile", LANE, env=env)
    lines = [line.split(US) for line in res.stdout.splitlines()]
    verdict = [f for f in lines if f[0] == "VERDICT"]
    problems = []
    if res.returncode != 0:
        problems.append(f"it exited {res.returncode}: {_said(res)!r}")
    if [v[1] for v in verdict] != ["indeterminate"]:
        problems.append(f"its verdict is {[v[1:2] for v in verdict]}, not indeterminate")
    elif "object log" not in verdict[0][2]:
        problems.append(f"its reason does not name the lane's log: {verdict[0][2][:120]!r}")
    if any(f[0] == "ROOT" and f[1] == str(third) for f in lines):
        problems.append(f"it took the third rung, {third}, for the lane's root")
    if any(f[0] == "STATE" and f[1] == "NONE" for f in lines):
        problems.append("it says the lane has no state")
    if any(f[0] == "BINDING" and f[1] == "free" for f in lines):
        problems.append("it says the lane's binding is free")
    assert not problems, "\n" + "\n".join(problems) + "\n" + res.stdout.replace(US, "<US>")


# ------------------------------------------------ with no origin, the lanes that have only a log


@pytest.mark.parametrize("mode", [0o400, 0o000], ids=["dir-400", "dir-000"])
def test_a_listing_with_no_origin_says_a_log_directory_it_cannot_search(inv, mode):
    """THE `lanes` LISTING WITH NO `origin`, which names the lanes that have a
    log and no row by listing this checkout's log directory (the issue's third
    point, probed there with `repoL-1`; here `repoB-1` is that lane). A
    directory that lists and cannot be searched (`r--`, 0400) named none of
    its files - the glob names them and `[ -e ]` needs search permission - so
    the lane with only a log was dropped without a word, and the lanes with
    both read as `NO LOG`. One that cannot be listed said so for the DORMANT
    class and not for the lanes it dropped. Both are said now, once, with the
    directory named, as the origin's own unlistable tree is said."""
    no_git = dict(NO_GIT)
    whole = inv.e.edit("lanes", "--all", env=no_git)
    assert whole.returncode == 0, whole.stderr
    rows = [line.split("\t")[0] for line in whole.stdout.splitlines()]
    assert LANE in rows, whole.stdout  # a lane with a log and no row, named by the directory
    assert "could not be" not in whole.stderr, whole.stderr
    logdir = inv.e.wip / "lanes" / "log"
    logdir.chmod(mode)
    try:
        if _this_account_gets_in_anyway(logdir, "dir"):
            pytest.skip(f"this account searches a mode-{mode:03o} directory (root): "
                        "nothing to prove here")
        res = inv.e.edit("lanes", "--all", env=no_git)
    finally:
        logdir.chmod(0o755)
    assert res.returncode == 0, (res.stdout, res.stderr)
    problems = []
    if f"{logdir} exists and could not be listed" not in res.stderr:
        problems.append("it does not say that the log directory could not be listed")
    if "a lane with a log and no row in the register or the archive is missing from this " \
            "listing" not in res.stderr:
        problems.append("it does not say that a lane with a log and no row is missing from it")
    if "no row is classed DORMANT here" not in res.stderr:
        problems.append("it does not withhold the DORMANT class")
    assert not problems, "\n" + "\n".join(problems) + f"\nstderr: {res.stderr.strip()!r}"


@pytest.mark.parametrize("mode", [0o400, 0o000], ids=["dir-400", "dir-000"])
def test_a_listing_with_an_origin_says_a_log_directory_it_cannot_list_or_search(inv, mode):
    """LANE 3'S 1005, CONSEQUENCE 3 OF 6353304444. With an `origin` the `lanes`
    listing uses only the NAMES of this checkout's log files, to tell a log
    this checkout has and `origin` has not; it asks the directory to be
    searchable as well as listable (`-x`), and the behaviour stays: no row is
    classed DORMANT over one that is not. The words were "could not be
    listed", which `ls` contradicts for an `r--` directory (0400): it lists
    one and the search is what fails. They say "could not be listed or
    searched" now, for both shapes, with the directory named."""
    env = {"LANES_NO_FETCH": "1"}
    whole = inv.e.edit("lanes", "--all", env=env)
    assert whole.returncode == 0, whole.stderr
    assert "exists and could not be listed" not in whole.stderr, whole.stderr
    logdir = inv.e.wip / "lanes" / "log"
    logdir.chmod(mode)
    try:
        if _this_account_gets_in_anyway(logdir, "dir"):
            pytest.skip(f"this account searches a mode-{mode:03o} directory (root): "
                        "nothing to prove here")
        res = inv.e.edit("lanes", "--all", env=env)
    finally:
        logdir.chmod(0o755)
    assert res.returncode == 0, (res.stdout, res.stderr)
    problems = []
    if f"{logdir} exists and could not be listed or searched, so whether a row has a log this " \
            "checkout has and origin has not is not known" not in res.stderr:
        problems.append("it does not say that the log directory could not be listed or searched")
    if "no row is classed DORMANT here" not in res.stderr:
        problems.append("it does not withhold the DORMANT class")
    assert not problems, "\n" + "\n".join(problems) + f"\nstderr: {res.stderr.strip()!r}"


# ------------------------------------------------ the review of #303: its guards


LOG_A1 = "origin/main:lanes/log/repoA-1.md"
LANE_END = REPO / "lane-end"


def test_lane_objects_answers_from_the_read_it_proved_and_not_a_later_one(inv):
    """THE ANSWER IS THE READ'S OWN (the review of #303, 544). `lane-objects`
    proves the lane's log readable and then answers out of `state_events`,
    which reads every log again: a log that failed between the two left no
    line of the lane's in the stream, and the answer was 0 with no rows -
    "this lane holds nothing", which `lane-end`'s gate ends a lane on. The shim
    lets the proof's read of repoB-1's log through and fails the second, the
    stream's own: the answer is 1, said, and no row."""
    env = {"LANES_NO_FETCH": "1"}
    whole = inv.e.edit("lane-objects", LANE, env=env)
    assert whole.returncode == 0 and "opensoft/repoB#3" in whole.stdout, whole.stderr
    shim, log = _git_shim(inv, SHOW_LOG_B1, first=2, last=2)
    res = inv.e.edit("lane-objects", LANE, env={**env, **shim})
    calls = _shim_calls(log)
    assert len(calls) >= 2 and calls[1].startswith("2 "), calls  # a LATER read failed: not vacuous
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr, calls)
    assert "lane-objects could not read lane repoB-1's object log" in res.stderr, res.stderr
    assert res.stdout == "", res.stdout


def test_lane_end_will_not_end_a_lane_whose_log_it_could_not_read(inv):
    """RELEASE-BLOCKING (the review of #303: "make its test release-blocking";
    the suite has no marker for it, so this sentence is the marking).
    `lane-end`'s claim gate reads `lane-objects`, and it read a log git could
    not show as 8, "this lane has no object log (pre-cutover)": the row's state
    cell decided instead, and repoA-1's says only that it is parked, so the
    lane was ended over the claim and the PR its log holds open - Rule 1 and
    Rule 6 both stopped for it, in silence. The gate refuses now, before it
    writes anything, naming the read; with the log whole it refuses on the two
    objects, which is the control."""
    env = {"LANES_NO_FETCH": "1"}
    register = inv.e.wip / "lanes" / "LANES.md"
    log_file = inv.e.wip / "lanes" / "log" / "repoA-1.md"
    held = inv.e.run("bash", LANE_END, "repoA-1", env=env)
    assert held.returncode == 2, (held.stdout, held.stderr)
    assert "lane repoA-1 still holds 2 object(s)" in held.stderr, held.stderr  # the gate reads the log
    before = (inv.e.tip(), register.read_bytes(), log_file.read_bytes())
    with _unreadable(inv.e, LOG_A1):
        res = inv.e.run("bash", LANE_END, "repoA-1", env=env)
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
    assert "lane-objects repoA-1 failed (exit 1)" in res.stderr, res.stderr
    assert "lane-objects could not read lane repoA-1's object log" in res.stderr, res.stderr
    assert (inv.e.tip(), register.read_bytes(), log_file.read_bytes()) == before, \
        "lane-end wrote something over a log it could not read"


def test_a_write_that_needs_no_home_lands_over_a_log_git_could_not_read(inv):
    """A SWAP IS NEVER LEFT UNWRITTEN (`R-A11-11` in `skills/handoff/SKILL.md`,
    which openspec/changes/add-supervised-context-restart/design.md calls
    `R-A11-5`), and the fix holds to it (the review of #303, 542 and 546). The
    `log`, `claim`, `release` and `who` arms resolve the lane's home from its
    log for every verb, and a home is needed only by `--home`, whose one
    refusal is a log that records one, and by a `#n` - the line's object or a
    RULED's payload. Those are refused over a log nobody could read, writing
    nothing: `--home` used to be TAKEN there, over a log that records a home.
    Everything else lands: a `NOTED`, and a swap's `PAUSED`."""
    env = {"LANES_NO_FETCH": "1", "LANES_LANE": LANE, "LANES_SESSION": UUID_B1}
    log_rel = "lanes/log/repoB-1.md"
    with _unreadable(inv.e, LOG_B1):
        tip = inv.e.tip()
        refused = {
            "--home": inv.e.edit("log", "NOTED", f"lane:{LANE}", "a note", "--home",
                                 "opensoft/repoB", env=env),
            "claim #5": inv.e.edit("claim", "#5", env=env),
            "RULED → #5": inv.e.edit("log", "RULED", f"lane:{LANE}", "→", "#5",
                                     "Brett Heap, verbatim: take it", env=env),
        }
        problems = [f"{name}: exit {res.returncode}, {res.stderr.strip()[-160:]!r}"
                    for name, res in refused.items()
                    if res.returncode != 1 or f"lane {LANE}'s object log could not be read"
                    not in res.stderr]
        assert not problems, "\n".join(problems)
        assert "whether it already records a home" in refused["--home"].stderr
        assert "the home '#5' is shorthand for is NOT established" in refused["claim #5"].stderr
        assert inv.e.tip() == tip, "a refused write moved origin/main"
        noted = inv.e.edit("log", "NOTED", f"lane:{LANE}", "noted over a log nobody read", env=env)
        assert noted.returncode == 0, (noted.stdout, noted.stderr)
    assert inv.e._git("show", f"origin/main:{log_rel}").rstrip("\n").endswith(
        "noted over a log nobody read"), "the NOTED line is not the log's last"
    with _unreadable(inv.e, LOG_B1):  # the log as the NOTED left it, unreadable again
        paused = inv.e.edit("log", "PAUSED", f"lane:{LANE}", "swapped over a log nobody read",
                            env=env)
        assert paused.returncode == 0, (paused.stdout, paused.stderr)
    last = inv.e._git("show", f"origin/main:{log_rel}").rstrip("\n").splitlines()[-1]
    assert last.startswith(f"PAUSED — lane {LANE}, session {UUID_B1}@") and \
        last.endswith("swapped over a log nobody read"), last


def test_the_session_start_open_line_says_a_log_git_could_not_read(inv):
    """THE FIRST LINE A SESSION READS ABOUT ITS LANE'S HOLDS (the review of
    #303, 543 and 546). The `SessionStart` hook's `open:` line read the lane's
    objects inside a here-document, whose status nothing tests, after a
    `lane_log_exists` that took a log git could not show for no log: it said
    `no log for repoA-1 (pre-cutover lane)` over a lane holding a claim and a
    PR. It says the log could not be read now - and, a hook, still exits 0."""
    hook = '{"session_id":"%s","source":"startup"}' % UUID_A1B  # compact, as the harness writes it

    def opened(res) -> list[str]:
        assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
        return [line for line in res.stdout.splitlines() if line.startswith("open: ")]

    whole = opened(inv.e.edit("session-start", input_text=hook))
    assert len(whole) == 1 and "opensoft/repoA#12" in whole[0] and \
        "opensoft/repoA#13" in whole[0], whole  # the lane is found and its holds read
    with _unreadable(inv.e, LOG_A1):
        said = opened(inv.e.edit("session-start", input_text=hook))
    assert said == ["open: UNKNOWN — lane repoA-1's object log could not be read, so what it "
                    "holds open is NOT established, which is not the same as none (Amendment "
                    "7(d)); see: lanes-edit.sh who --lane repoA-1"], said


def test_a_lifecycle_follow_up_over_a_log_it_could_not_read_moves_nothing_and_says_why(inv):
    """R4 OF THE REVIEW OF #303: NOTE AND SKIP. A `STARTED`, `RESUMED`, `ENDED`
    or `RETIRED` line moves the lane's snapshot after it lands, under the root
    its log's `dir` places, and that read threw a failure away: the root fell
    to the third rung, beside the real one. Here the reads before the line -
    the home's and the pre-image's - are let through and every later read of
    repoB-1's log fails, so the follow-up meets a log it could not read. The
    `ENDED` lands; the real root's SWAPPING snapshot is not touched, nothing is
    filed at the third rung, and the note says the log is why - not that "the
    lane lifecycle moved under this ENDED", which is what a root found at the
    third rung made it say."""
    env, _checkout, snap = _a_lane_with_a_whole_record(inv)
    third = inv.e.home / "projects" / ".lane-state" / LANE
    before = snap.read_bytes()
    shim, log = _git_shim(inv, SHOW_LOG_B1, first=3)
    res = inv.e.edit("log", "ENDED", f"lane:{LANE}", "ended with its log unreadable",
                     env={**env, **shim, "LANES_LANE": LANE, "LANES_SESSION": UUID_B1})
    calls = _shim_calls(log)
    assert len(calls) >= 3, calls  # the follow-up's read is one the shim failed: not vacuous
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr, calls)
    assert f"the lane lifecycle snapshot for {LANE} was NOT moved to CLOSED: its object log " \
        "could not be read" in res.stderr, (res.stderr, calls)
    assert "moved under this ENDED" not in res.stderr, res.stderr
    assert snap.read_bytes() == before, "the real root's snapshot was replaced"
    assert not third.exists(), sorted(str(p) for p in third.rglob("*"))


def test_a_lifecycle_follow_up_over_a_lane_with_no_root_says_nothing(inv):
    """LANE 3'S 1002, A TEST GAP (the code is right). The follow-up's `8) return
    0` is the pre-cutover case, and nothing pinned it: dropping the arm sends a
    lane that has no control root to the arm that says "its object log could not
    be read", on every `STARTED`, `RESUMED`, `ENDED` and `RETIRED` it writes,
    and all of the cases above still passed. No root is not a log nobody read:
    repoB-1's log is READ and records no `dir`, `$PROJECTS_ROOT` is not a
    directory here, and no override names a root, so `lane-state` finds no rung
    (8's own sentence, not a failed read). A `NOTED` and an `ENDED` then land,
    and neither says the snapshot "was NOT moved", nor that a log could not be
    read - nothing is said at all, and nothing is filed at the third rung."""
    env = {"LANES_LANE_STATE_ROOT": None, "LANES_NO_FETCH": "1",
           "PROJECTS_ROOT": str(inv.root / "no-projects-root"),
           "LANES_LANE": LANE, "LANES_SESSION": UUID_B1}
    no_root = inv.e.edit("lane-state", LANE, env=env)
    assert no_root.returncode == 1 and "has no lifecycle control root" in no_root.stderr, \
        (no_root.returncode, no_root.stderr)  # no rung answers: not vacuous
    assert "could not be read" not in no_root.stderr, no_root.stderr  # ... and no read failed
    log_rel = "lanes/log/repoB-1.md"
    for verb, text in (("NOTED", "noted by a lane with no root"),
                       ("ENDED", "ended by a lane with no root")):
        res = inv.e.edit("log", verb, f"lane:{LANE}", text, env=env)
        assert res.returncode == 0, (verb, res.returncode, res.stdout, res.stderr)
        assert "was NOT moved" not in res.stderr, (verb, res.stderr)
        assert "object log could not be read" not in res.stderr, (verb, res.stderr)
        assert "lifecycle snapshot" not in res.stderr, (verb, res.stderr)
        last = inv.e._git("show", f"origin/main:{log_rel}").rstrip("\n").splitlines()[-1]
        assert last.startswith(f"{verb} — lane {LANE}, session {UUID_B1}@") and \
            last.endswith(text), last  # the line landed
    assert not (inv.root / "no-projects-root").exists(), "a snapshot was filed at the third rung"


# ======================================== R7: "Write swap, name the gap", and what it held

LANE_HANDOFF = REPO / "lane-handoff"
HANDOFF_CELL = f"handoffs/{LANE}.md"
#: WHAT `lane-handoff` NAMES, on its stderr, on stdout after `READY` and in the
#: top block it prints for publishing later.
GAP = f"lane {LANE}'s object log could not be read, so where its restart intent is kept is NOT established"
#: THE REGISTER LINE'S TAIL WHERE NO HANDOFF WAS PUBLISHED, ruled with R7 in
#: place of `; handoff refreshed`.
R7_TAIL = "; handoff NOT published: object log unreadable"
#: `restart-intent`'s own sentence for its 10, and the advice that ends it: a
#: read, for any caller, and never "re-run" - a caller mid-handoff that re-ran
#: would write a second PAUSED (the review of R7, 654).
INTENT_10 = (f"lane {LANE}'s object log could not be read, so the directory its restart intent is "
             "kept beside is NOT established")
READ_AGAIN = "Read it again once git can read the log."
#: WHAT A PUBLICATION WAITS ON, which is the intent and not the log (the review
#: of R7, 653(c)): right after the swap's own PAUSED the log reads again, while
#: a restart may still own the lane.
WAIT_ON = (f"once `lanes-edit.sh restart-intent {LANE}` answers 8, `ready` or `failed`, publish "
           f"this block with `publish-handoff`; read `lane-handoff --restart-status --lane {LANE}` "
           "before relaunching")
NOTE_HEAD = "lane-handoff: the handoff file was NOT published"
#: WHAT THE NOTE AND THE TOP BLOCK'S STATE LINE SAY OF THE SWAP'S OWN RECORDS,
#: which holds only where a workstation is configured: with none, `R-A11-14`
#: writes no PAUSED line, no register line and no row, and neither may say they
#: are written (lane 3's review of R7, 1004).
SWAP_WRITTEN_NOTE = "The PAUSED record, the register line, the row and the restart line below are still written"
SWAP_WRITTEN_BLOCK = "The PAUSED record, the register line and the row ARE written"
#: `--exit`'s GATE ON R7'S PATH, word for word as lane 3 ruled it (6367537964,
#: question 1): no handoff was published there, so it says what to wait on
#: before publishing, and never to put the block at the head of the handoff,
#: which is an edit by hand around `publish-handoff` (653(b) and (c)).
GATE_R7 = ("lane-handoff: REFUSED: The handoff was NOT published: the lane's object log could not "
           f"be read. Once `lanes-edit.sh restart-intent {LANE}` answers 8, `ready` or `failed`, "
           "publish the block printed above with `publish-handoff`, and read `--restart-status` "
           "before relaunching. Then re-run.")
#: THE SAME GATE ON EVERY OTHER PATH, as it was at 969806f, up to the restart
#: command it ends on.
GATE_OTHER = ("lane-handoff: REFUSED: the lane's PAUSED line is written and the HANDOFF WAS NOT "
              "REFRESHED (the note above says why), so this pane is left exactly as it is: the top "
              "block of that file is what the new session is started with, and respawning now "
              "would hand it the block of a handoff this act has replaced. Put the block printed "
              "above at the head of the handoff, then re-run — or restart by hand once you have:  ")


def _a_lane_with_a_row_and_a_handoff(inv, cell: str = HANDOFF_CELL, intent: bool = False):
    """repoB-1's whole record, and what a handoff needs beside it: a register row
    whose handoff column names `cell` - `handoffs/repoB-1.md` unless a case
    names one nobody can find - and that handoff file. With `intent`, a
    `preparing` restart intent is filed while the log reads whole, so it sits
    beside the directory the log records, as a `/ctx` in flight leaves it (E1
    of the review's probes). Returns the environment, the checkout and the
    handoff file."""
    env, checkout, _snap = _a_lane_with_a_whole_record(inv)
    e = inv.e
    register = e.wip / "lanes" / "LANES.md"
    lines = register.read_text(encoding="utf-8").split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith(f"| `{NO_LOG_LANE}` |"))
    lines.insert(at + 1, f"| `{LANE}` | harness `{UUID_B1}` | Eagle / test / brett | "
                         f"2026-10-01T00:00Z | none | {cell} | LIVE · 2026-10-05T00:00:00Z · working |")
    register.write_text("\n".join(lines), encoding="utf-8")
    handoff = e.wip / HANDOFF_CELL
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(f"Lane: {LANE} (team-02a, session old) — the older top block\n\nolder content\n",
                       encoding="utf-8")
    e._git("add", "-A")
    e._git("commit", "-q", "-m", "a row and a handoff for repoB-1")
    e._git("push", "-q", "origin", "main")
    if intent:
        put = e.edit("set-restart-intent", LANE, "preparing", "--expect", "none", "--operation",
                     "op-test-r7", "--generation", "1", "--mode", "preservation-only", "--reason",
                     "a restart owns the lane", env=env)
        assert put.returncode == 0, put.stderr
    return env, checkout, handoff


def _hand_off(inv, env, *args, extra=None):
    """`lane-handoff` as the lane's own session runs it, its transcript and its
    profile exported as the harness exports them, and tmux untouched unless
    `extra` hands it the recording one."""
    full = {**env, "CLAUDE_CODE_SESSION_ID": UUID_B1, "CLAUDE_PROFILE_NAME": "team-02a",
            "LANE_HANDOFF_NO_TMUX": "1", **(extra or {})}
    return inv.e.run("bash", LANE_HANDOFF, "--lane", LANE, "--agent", "claude", *args,
                     env=full, timeout=300)


def _recording_tmux(inv, pane: bool = False):
    """`test_lane_start_claude_current`'s recording fake tmux - this window is
    `testsess:@1`, named `claude`; `rename-window` and `send-keys` are logged -
    with `respawn-pane` logged too, first on `PATH` and with `$TMUX` set, so
    `lane-handoff` takes itself to be inside tmux and what it types is SEEN.
    `LANE_HANDOFF_NO_TMUX=1` could not see it, so "nothing typed" proved
    nothing there (the review of R7, 658). Returns the environment and the
    log."""
    shim = inv.root / "recording-tmux"
    shim.mkdir(exist_ok=True)
    (shim / "tmux").write_text(FAKE_TMUX.replace(
        "#!/usr/bin/env bash\n",
        "#!/usr/bin/env bash\n"
        "if [ \"${1-}\" = respawn-pane ]; then printf '%s\\n' \"$*\" >> \"$FAKE_TMUX_LOG\"; exit 0; fi\n",
        1), encoding="utf-8")
    (shim / "tmux").chmod(0o755)
    log = inv.root / "tmux.log"
    log.write_text("", encoding="utf-8")
    env = {"PATH": inv.e.path_with(shim), "TMUX": f"{inv.root}/fake-tmux-socket,0,0",
           "FAKE_TMUX_LOG": str(log), "LANE_HANDOFF_NO_TMUX": None}
    if pane:
        env["TMUX_PANE"] = "%1"
    return env, log


def _published(e, path: str):
    """`path` as `origin/main` holds it, or None where git cannot show it."""
    res = subprocess.run(["git", "show", f"origin/main:{path}"], cwd=str(e.wip), env=e.env,
                         capture_output=True, text=True, check=False)
    return res.stdout if res.returncode == 0 else None


def _records(e):
    """What a swap writes, as `origin` holds it: the lane's log's last line,
    the register's last line, and the lane's rows."""
    log = (_published(e, f"lanes/log/{LANE}.md") or "").rstrip("\n").split("\n")[-1]
    register = _published(e, "lanes/LANES.md") or ""
    last = register.rstrip("\n").split("\n")[-1]
    rows = [line for line in register.split("\n") if line.startswith(f"| `{LANE}` |")]
    return log, last, rows


def _intents(inv) -> list:
    return sorted(str(p.relative_to(inv.root)) for p in inv.root.rglob("restart-intent.yaml"))


def _the_swap_is_written(inv, res) -> list:
    """Every record R7 keeps, for a handoff whose file was not published: the
    log's PAUSED, the register line with R7's tail, the row's PAUSED cell, and
    the restart line with the gap named after it on STDOUT - so a caller that
    keeps only stdout still learns of it - and no top block there."""
    log, last, rows = _records(inv.e)
    problems = []
    if not log.startswith(f"PAUSED — lane {LANE}, session {UUID_B1}@Eagle, "):
        problems.append(f"the log's last line is not the PAUSED: {log[:120]!r}")
    if not (last.startswith(f"PAUSED — lane {LANE}, session {UUID_B1}@Eagle, ") and
            last.endswith(R7_TAIL)):
        problems.append(f"the register's last line is not the PAUSED naming the gap: {last[-160:]!r}")
    if len(rows) != 1 or "| PAUSED · " not in rows[0]:
        problems.append(f"the row's state cell is not PAUSED: {rows}")
    out = res.stdout.splitlines()
    if not any(line.startswith("READY — restart with: ") for line in out):
        problems.append("stdout has no restart line")
    if f"  handoff: NOT published: {GAP}" not in out:
        problems.append(f"stdout does not name the gap: {res.stdout[-400:]!r}")
    if f"Lane: {LANE} (" in res.stdout:
        problems.append("the top block is on stdout")
    return problems


@contextlib.contextmanager
def _log_unread(inv, shape: str):
    """repoB-1's log, unreadable in one of the five shapes a read fails in: the
    published blob, the published log tree, and with no `origin` a log
    directory that lists and cannot be searched, one that cannot be listed,
    and a log file that will not open. Yields what the read's environment
    takes on top (`LANES_NO_GIT` for the last three)."""
    if shape in ("blob", "tree"):
        with _unreadable(inv.e, LOG_B1 if shape == "blob" else LOG_TREE):
            yield {}
        return
    what, mode = shape.split("-")
    logdir = inv.e.wip / "lanes" / "log"
    target = logdir if what == "dir" else logdir / f"{LANE}.md"
    before = target.stat().st_mode & 0o777
    target.chmod(int(mode, 8))
    try:
        if _this_account_gets_in_anyway(target, what):
            pytest.skip(f"this account reads a mode-{mode} {what} (root): nothing to prove")
        yield dict(NO_GIT)
    finally:
        target.chmod(before)


@pytest.mark.parametrize("shape", ["blob", "tree", "dir-400", "dir-000", "file-000"])
def test_restart_intent_over_a_log_it_could_not_read_is_10_and_hides_no_intent(inv, shape):
    """THE CHANGE AT `lanes-edit.sh:12318`, HELD FOR R7 (the review of #303,
    541). A restart intent is kept beside the directory the lane's log
    records, and the log was read for it with the failure thrown away: here a
    `preparing` intent filed there reads 0 with the log whole, and with the log
    unreadable the root fell to `$PROJECTS_ROOT/.lane-state`, where none is -
    8, "this lane has no restart in flight", which every handoff and every
    launch goes past. It is 10 in each shape a read fails in, with a sentence
    that ends in a read and never in "re-run" (654), and nothing on stdout."""
    env, _checkout, _handoff = _a_lane_with_a_row_and_a_handoff(inv, intent=True)
    whole = inv.e.edit("restart-intent", LANE, env=env)
    assert whole.returncode == 0 and "state\tpreparing" in whole.stdout, (whole.stdout, whole.stderr)
    with _log_unread(inv, shape) as extra:
        res = inv.e.edit("restart-intent", LANE, env={**env, **extra})
    problems = []
    if res.returncode != 10:
        problems.append(f"exit {res.returncode}, not 10")
    if INTENT_10 not in res.stderr or READ_AGAIN not in res.stderr:
        problems.append(f"it does not say why, and what to do: {_said(res)!r}")
    if "Re-run" in res.stderr:
        problems.append("it tells its caller to re-run it")
    if res.stdout:
        problems.append(f"it printed an intent: {res.stdout[:80]!r}")
    assert not problems, "\n" + "\n".join(problems)


def test_restart_intent_still_answers_from_a_log_that_was_read(inv):
    """A LOG THAT WAS READ IS NEVER 10 (the review of R7, 658). repoC-1 has no
    log at all: 8, as it always was. repoN-1's log is read and records no
    `dir`, so its intent's root is the rung beneath, `$PROJECTS_ROOT/.lane-
    state/repoN-1`: 8 with no intent filed there, and 0 once one is."""
    env = {"LANES_LANE_STATE_ROOT": None, "LANES_NO_FETCH": "1"}
    inv.e.commit_paths({"lanes/log/repoN-1.md": (
        f"STARTED — lane repoN-1, session {UUID_B1}@Eagle, 2026-10-06T00:00:00Z, "
        "lane:repoN-1 → home opensoft/repoN\n")}, "a log that records no dir")
    read = inv.e.edit("lane-dir", "repoN-1", env=env)
    assert read.returncode == 8, (read.stdout, read.stderr)  # read, and no `dir`: not vacuous
    no_log = inv.e.edit("restart-intent", NO_LOG_LANE, env=env)
    none_yet = inv.e.edit("restart-intent", "repoN-1", env=env)
    put = inv.e.edit("set-restart-intent", "repoN-1", "preparing", "--expect", "none",
                     "--operation", "op-test-n1", "--generation", "1", "--mode",
                     "preservation-only", "--reason", "an intent at the rung beneath", env=env)
    filed = inv.e.edit("restart-intent", "repoN-1", env=env)
    got = (no_log.returncode, none_yet.returncode, put.returncode, filed.returncode)
    assert got == (8, 8, 0, 0), (got, no_log.stderr, none_yet.stderr, put.stderr, filed.stderr)
    assert "state\tpreparing" in filed.stdout, filed.stdout
    assert (inv.e.home / "projects" / ".lane-state" / "repoN-1" / "restart-intent.yaml").is_file()


def test_restart_intent_over_two_logs_one_case_apart_names_both(inv):
    """TWO LOGS ONE CASE APART ARE THIS 10 TOO (the review of R7, 661):
    `lane_payload_field` answers 1 for them as for a log nobody could read. The
    read that finds the root throws its stderr away, so `log_path_ci`'s own
    words - both files, and Amendment 15(d)'s merge - were lost, and "once git
    can read the log" is advice no wait makes true. They are said, and the
    sentence ends on the merge."""
    env, _checkout, _handoff = _a_lane_with_a_row_and_a_handoff(inv)
    inv.e.commit_paths({"lanes/log/repob-1.md": (
        f"NOTED — lane repob-1, session {UUID_B1}@Eagle, 2026-10-06T00:00:00Z, "
        "lane:repob-1 — the other spelling\n")}, "a second spelling of repoB-1's log")
    res = inv.e.edit("restart-intent", LANE, env=env)
    assert res.returncode == 10, (res.returncode, res.stdout, res.stderr)
    assert f"lane {LANE} has 2 object logs on origin/main whose names differ only by case" \
        in res.stderr, res.stderr
    assert "lanes/log/repoB-1.md" in res.stderr and "lanes/log/repob-1.md" in res.stderr
    assert INTENT_10 in res.stderr, res.stderr
    assert "Read it again once the logs named above are merged into one (Amendment 15(d))." \
        in res.stderr, res.stderr


def test_a_root_the_environment_names_is_read_without_the_log_and_the_handoff_publishes(inv):
    """`LANES_LANE_STATE_ROOT` NAMES THE ROOT, AND THE LOG IS NOT ASKED (the
    review of R7, 658). Over a log nobody could read, `restart-intent` answers
    out of the named root - 8, never 10 - and a handoff publishes its file and
    says `handoff refreshed`, as it did: the gap R7 names is where the log
    places the intent, and here the log places nothing."""
    env, _checkout, handoff = _a_lane_with_a_row_and_a_handoff(inv)
    env = {**env, "LANES_LANE_STATE_ROOT": str(inv.lsr)}
    before = handoff.read_bytes()
    with _unreadable(inv.e, LOG_B1):
        intent = inv.e.edit("restart-intent", LANE, env=env)
        res = _hand_off(inv, env, "a swap under a named root")
    assert intent.returncode == 8, (intent.returncode, intent.stderr)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert handoff.read_bytes() != before, "the handoff was not published"
    _log, last, _rows = _records(inv.e)
    assert last.endswith("; handoff refreshed"), last
    assert "NOT published" not in res.stdout + res.stderr, res.stdout


def test_set_restart_intent_over_a_log_it_could_not_read_files_nothing_and_names_no_other_root(inv):
    """THE WRITER'S HALF (the review of #303, 546; of R7, 657). It filed the
    intent at `$PROJECTS_ROOT/.lane-state`, beside the root the log records,
    where no reader of that root looks. It writes nothing now, and its
    refusal does not send the person to `LANES_LANE_STATE_ROOT`: over a log
    nobody read, a root named that way hides an intent at the root the log
    records, which is 541's hole reached by hand."""
    env, _checkout, _handoff = _a_lane_with_a_row_and_a_handoff(inv)
    with _unreadable(inv.e, LOG_B1):
        res = inv.e.edit("set-restart-intent", LANE, "preparing", "--expect", "none",
                         "--operation", "op-test-r7w", "--generation", "1", "--mode",
                         "preservation-only", "--reason", "over a log nobody read", env=env)
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
    assert INTENT_10 in res.stderr and "Nothing was written" in res.stderr, res.stderr
    assert "configure LANES_LANE_STATE_ROOT explicitly" not in res.stderr, res.stderr
    assert _intents(inv) == [], _intents(inv)


def test_publish_handoff_over_a_log_it_could_not_read_publishes_nothing(inv):
    """THE PUBLISHER IS FENCED ON THE SAME READ (F1 of the review's probes), so
    the skill's step 2, which publishes through it and never through
    `lane-handoff`, cannot write a handoff over a restart nobody could look
    for. It published, before."""
    env, _checkout, handoff = _a_lane_with_a_row_and_a_handoff(inv)
    prepared = inv.root / "prepared.md"
    prepared.write_text("a new top block\n\n---\n\n" + handoff.read_text(encoding="utf-8"),
                        encoding="utf-8")
    before = handoff.read_bytes()
    with _unreadable(inv.e, LOG_B1):
        res = inv.e.edit("publish-handoff", LANE, str(handoff), str(prepared), "--expect-digest",
                         hashlib.sha256(before).hexdigest(), env=env)
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
    assert "restart ownership could not be read; no handoff was published" in res.stderr
    assert handoff.read_bytes() == before, "the handoff was published"


def test_an_ordinary_handoff_over_a_log_it_could_not_read_writes_the_swap_and_names_the_gap(inv):
    """R7, "WRITE SWAP, NAME THE GAP" (E1 of the review's probes). A `/ctx` is
    preparing: its intent sits beside the directory the log records, and with
    the log whole the handoff refuses. With the log unreadable the read said
    8, and the handoff PUBLISHED its file over the restart that owns it. It
    still writes the PAUSED record, the register line, the row and the restart
    line (`R-A11-11`), exits 0, publishes nothing, and names the gap: on
    stdout, in the register line, and in a note whose block is on stderr. The
    note names the file, never says to edit it by hand, and waits on the
    intent, not the log (653); the block names the gap itself (662). Right
    after the swap's own PAUSED the log reads again - and the intent still
    says `preparing`, which is why the wait is on it."""
    env, _checkout, handoff = _a_lane_with_a_row_and_a_handoff(inv, intent=True)
    intent = next(p for p in inv.root.rglob("restart-intent.yaml"))
    intent_before = intent.read_bytes()
    before = (handoff.read_bytes(), _published(inv.e, HANDOFF_CELL))
    with _unreadable(inv.e, LOG_B1):
        res = _hand_off(inv, env, "a swap over a log nobody could read")
    notes = [line for line in res.stderr.splitlines() if line.startswith(NOTE_HEAD)]
    problems = [] if res.returncode == 0 else [f"exit {res.returncode}: {_said(res)!r}"]
    problems += _the_swap_is_written(inv, res)
    if (handoff.read_bytes(), _published(inv.e, HANDOFF_CELL)) != before:
        problems.append("the handoff was published")
    if intent.read_bytes() != intent_before:
        problems.append("the restart intent was changed")
    if len(notes) != 1:
        problems.append(f"{len(notes)} gap notes on stderr")
    else:
        if GAP not in notes[0] or WAIT_ON not in notes[0] or HANDOFF_CELL not in notes[0]:
            problems.append(f"the note does not say what, where and what to wait on: {notes[0]!r}")
        if "by hand" in notes[0]:
            problems.append("the note says to edit the handoff by hand")
    if f"Lane: {LANE} (team-02a, session {UUID_B1})" not in res.stderr:
        problems.append("the top block is not on stderr")
    if f"THIS BLOCK WAS NOT PUBLISHED WITH THE SWAP: {GAP}" not in res.stderr:
        problems.append("the top block does not name the gap")
    # WHERE A WORKSTATION IS CONFIGURED the writes were made, and both say so
    # (lane 3's 1004: they say it only then).
    if SWAP_WRITTEN_NOTE not in res.stderr:
        problems.append("the note does not say the swap's records are still written")
    if SWAP_WRITTEN_BLOCK not in res.stderr:
        problems.append("the top block's state line does not say the swap's records are written")
    if "Re-run" in res.stderr:
        problems.append("a note mid-handoff says to re-run")
    assert not problems, "\n" + "\n".join(problems) + "\n" + res.stderr[-1500:]
    again = inv.e.edit("restart-intent", LANE, env=env)
    assert again.returncode == 0 and "state\tpreparing" in again.stdout, (again.stdout, again.stderr)


def test_the_control_a_handoff_over_a_whole_log_publishes_and_says_refreshed(inv):
    """THE CONTROL (E3 of the review's probes): with the log whole and no
    restart in flight, the handoff publishes its file and the register line
    says `handoff refreshed`, and nothing says NOT published."""
    env, _checkout, handoff = _a_lane_with_a_row_and_a_handoff(inv)
    before = handoff.read_bytes()
    res = _hand_off(inv, env, "a swap over a whole log")
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert handoff.read_bytes() != before, "the handoff was not published"
    _log, last, _rows = _records(inv.e)
    assert last.endswith("; handoff refreshed"), last
    assert "NOT published" not in res.stdout + res.stderr, res.stdout


def test_a_handoff_over_a_log_it_could_not_read_with_no_workstation_does_not_say_it_wrote_the_swap(inv):
    """LANE 3'S 1004: R7 AND A MISSING WORKSTATION (`R-A11-14`). A container with
    no `LANES_WORKSTATION` writes no PAUSED line, no register line and no row,
    and over a log nobody could read it publishes no handoff file either: exit
    0 with the log, LANES.md, the row and the handoff all as they were. The
    note said the PAUSED record, the register line, the row and the restart
    line "are still written", and the top block's state line said they "ARE
    written", right after saying the register and object-log writes "WERE NOT
    MADE". Both depend on an empty `ws_missing` now; the gap itself is still
    named, and the restart line is still printed."""
    env, _checkout, handoff = _a_lane_with_a_row_and_a_handoff(inv)
    # `lane-handoff` reads no workstation where `lanes-edit.sh workstation`
    # exits 2, as a helper predating Amendment 11 does (`R-A11-8`): the helper
    # below passes everything else through to this checkout's own.
    old_helper = inv.root / "old-helper" / "lanes-edit.sh"
    old_helper.parent.mkdir()
    old_helper.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"${1-}\" = workstation ]; then\n"
        "  echo \"lanes-edit: unknown subcommand 'workstation'\" >&2; exit 2\n"
        "fi\n"
        f"exec bash {LANES_EDIT} \"$@\"\n", encoding="utf-8")
    old_helper.chmod(0o755)
    before = (_records(inv.e), handoff.read_bytes(), _published(inv.e, HANDOFF_CELL))
    with _unreadable(inv.e, LOG_B1):
        res = _hand_off(inv, env, "a swap with no workstation over a log nobody could read",
                        extra={"LANES_EDIT": str(old_helper)})
    notes = [line for line in res.stderr.splitlines() if line.startswith(NOTE_HEAD)]
    problems = [] if res.returncode == 0 else [f"exit {res.returncode}: {_said(res)!r}"]
    if (_records(inv.e), handoff.read_bytes(), _published(inv.e, HANDOFF_CELL)) != before:
        problems.append("something was written or published")  # not vacuous: ws_missing's own words below
    if "THE REGISTER AND OBJECT-LOG WRITES WERE NOT MADE" not in res.stderr:
        problems.append("the top block does not say the writes were not made: no workstation was missing")
    if len(notes) != 1 or GAP not in notes[0]:
        problems.append(f"the gap is not named in one note: {notes!r}")
    if f"THIS BLOCK WAS NOT PUBLISHED WITH THE SWAP: {GAP}" not in res.stderr:
        problems.append("the top block does not name the gap")
    for words in (SWAP_WRITTEN_NOTE, SWAP_WRITTEN_BLOCK, "ARE written", "are still written"):
        if words in res.stderr:
            problems.append(f"stderr says {words!r} where nothing was written")
    if not any(line.startswith("READY — restart with: ") and "--lane" in line
               for line in res.stdout.splitlines()):
        problems.append("stdout has no restart line naming the lane")
    assert not problems, "\n" + "\n".join(problems) + "\n" + res.stderr[-3000:] + "\nSTDOUT\n" + res.stdout


def test_a_row_naming_a_handoff_nobody_can_find_is_named_and_never_an_empty_path(inv):
    """E6 OF THE REVIEW'S PROBES (653(a)): the row names a handoff no rung
    finds, so there is no file to name - and the note said "at the head of
    ␣␣by hand", an empty path. It names the row's cell instead, and the swap
    and the gap are written as for any other R7 handoff."""
    env, _checkout, handoff = _a_lane_with_a_row_and_a_handoff(
        inv, cell="handoffs/missing-repoB-1.md")
    before = handoff.read_bytes()
    with _unreadable(inv.e, LOG_B1):
        res = _hand_off(inv, env, "a swap whose handoff the row misnames")
    notes = [line for line in res.stderr.splitlines() if line.startswith(NOTE_HEAD)]
    problems = [] if res.returncode == 0 else [f"exit {res.returncode}: {_said(res)!r}"]
    problems += _the_swap_is_written(inv, res)
    if len(notes) != 1:
        problems.append(f"{len(notes)} gap notes on stderr")
    elif "'handoffs/missing-repoB-1.md'" not in notes[0] or "  " in notes[0] or \
            WAIT_ON not in notes[0]:
        problems.append(f"the note names no handoff, or an empty one: {notes[0]!r}")
    if handoff.read_bytes() != before:
        problems.append("a handoff was written")
    assert not problems, "\n" + "\n".join(problems) + "\n" + res.stderr[-1500:]


def test_exit_over_a_log_it_could_not_read_writes_the_swap_and_types_nothing(inv):
    """`--exit` (E4 of the review's probes, with the recording tmux of 658):
    with the log whole it writes the swap and TYPES `/exit` into this pane -
    the control, which shows the tmux here sees what is typed. With the log
    unreadable it typed `/exit` too, over a handoff it had just published over
    the restart's intent. It writes the four records, refuses at the gate
    with 2 because the handoff was not published, and types nothing."""
    env, _checkout, handoff = _a_lane_with_a_row_and_a_handoff(inv)
    tmux, typed = _recording_tmux(inv)
    whole = _hand_off(inv, env, "--exit", "requested by a test", extra=tmux)
    assert whole.returncode == 0, (whole.returncode, whole.stdout, whole.stderr)
    assert "send-keys -t @1 /exit Enter" in typed.read_text(), typed.read_text()
    typed.write_text("", encoding="utf-8")
    before = handoff.read_bytes()
    with _unreadable(inv.e, LOG_B1):
        res = _hand_off(inv, env, "--exit", "requested by a test again", extra=tmux)
    problems = [] if res.returncode == 2 else [f"exit {res.returncode}, not 2"]
    problems += _the_swap_is_written(inv, res)
    if "lane-handoff: REFUSED: The handoff was NOT published: " not in res.stderr:
        problems.append(f"the gate did not say why: {_said(res)!r}")
    if [line for line in typed.read_text().splitlines() if line.startswith("send-keys")]:
        problems.append(f"it typed into the pane: {typed.read_text()!r}")
    if handoff.read_bytes() != before:
        problems.append("the handoff was published")
    assert not problems, "\n" + "\n".join(problems) + "\n" + res.stderr[-1500:]


def _gate_and_typed(res, typed):
    """What `lane-handoff`'s gates refused with, one line each, and what was
    typed into the pane."""
    gates = [line for line in res.stderr.splitlines() if line.startswith("lane-handoff: REFUSED: ")]
    keys = [line for line in typed.read_text().splitlines() if line.startswith("send-keys")]
    return gates, keys


def test_exit_over_a_log_it_could_not_read_says_at_its_gate_what_to_wait_on(inv):
    """`--exit`'s GATE ON R7'S PATH (lane 3's ruling 6367537964, question 1),
    under the recording tmux. It said "Put the block printed above at the head
    of the handoff, then re-run": an edit by hand, around `publish-handoff`,
    over a restart nobody could look for. It says what to wait on now, in the
    words ruled and only those; the exit status is still 2, and nothing is
    typed."""
    env, _checkout, _handoff = _a_lane_with_a_row_and_a_handoff(inv)
    tmux, typed = _recording_tmux(inv)
    with _unreadable(inv.e, LOG_B1):
        res = _hand_off(inv, env, "--exit", "requested by a test", extra=tmux)
    gates, keys = _gate_and_typed(res, typed)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr[-1500:])
    assert gates == [GATE_R7], gates
    assert "Put the block printed above" not in res.stderr, res.stderr[-1500:]
    assert keys == [], keys


def test_exit_where_the_row_names_no_handoff_keeps_its_gates_words(inv):
    """AND ONLY ON R7'S PATH (the same ruling). With the log whole, a row that
    names a handoff nobody can find is another path on which no top block is
    written, and the gate's words there are as they were at 969806f, ending on
    the restart command the `READY` line names, with nothing of R7's in them.
    The exit status is 2, and nothing is typed."""
    env, _checkout, _handoff = _a_lane_with_a_row_and_a_handoff(
        inv, cell="handoffs/missing-repoB-1.md")
    tmux, typed = _recording_tmux(inv)
    res = _hand_off(inv, env, "--exit", "requested by a test", extra=tmux)
    gates, keys = _gate_and_typed(res, typed)
    ready = [line[len("READY — restart with: "):] for line in res.stdout.splitlines()
             if line.startswith("READY — restart with: ")]
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr[-1500:])
    assert len(ready) == 1 and ready[0], res.stdout
    assert gates == [GATE_OTHER + ready[0]], gates
    assert "NOT published" not in res.stdout + res.stderr, res.stderr[-1500:]
    assert keys == [], keys


def test_restart_over_a_log_it_could_not_read_refuses_before_it_writes_anything(inv):
    """`--restart` (E5 of the review's probes): it reserved its intent at the
    third rung, wrote the swap and respawned the pane over a log nobody could
    read. It refuses at its own read of the prior intent, before any write: the
    register, the log, the handoff and the pane are as they were, and no
    intent is filed anywhere."""
    env, checkout, handoff = _a_lane_with_a_row_and_a_handoff(inv)
    tmux, typed = _recording_tmux(inv, pane=True)
    before = (handoff.read_bytes(), _published(inv.e, "lanes/LANES.md"),
              _published(inv.e, f"lanes/log/{LANE}.md"))
    with _unreadable(inv.e, LOG_B1):
        res = _hand_off(inv, env, "--restart", "--dir", str(checkout), "clear", extra=tmux)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert "the prior legacy intent cannot be read. Nothing was written or respawned." \
        in res.stderr, res.stderr
    after = (handoff.read_bytes(), _published(inv.e, "lanes/LANES.md"),
             _published(inv.e, f"lanes/log/{LANE}.md"))
    assert after == before, "a record was written"
    assert _intents(inv) == [], _intents(inv)
    assert "respawn-pane" not in typed.read_text(), typed.read_text()


def test_restart_over_a_log_it_can_read_still_publishes_and_respawns(inv):
    """`--restart` WITH THE LOG WHOLE (the review of R7, 652). What R7 adds
    to the ordinary handoff is read by every mode, and `lane-handoff` runs
    under `set -u`: a value set only where the ordinary handoff reads the
    intent would end every `/ctx` at its publication on an unbound variable.
    It publishes, respawns, and leaves its intent pending."""
    env, checkout, handoff = _a_lane_with_a_row_and_a_handoff(inv)
    tmux, typed = _recording_tmux(inv, pane=True)
    before = handoff.read_bytes()
    res = _hand_off(inv, env, "--restart", "--dir", str(checkout), "clear", extra=tmux)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "unbound variable" not in res.stderr, res.stderr
    assert handoff.read_bytes() != before, "the handoff was not published"
    assert any(line.startswith("respawn-pane ") for line in typed.read_text().splitlines()), \
        typed.read_text()
    intent = inv.e.edit("restart-intent", LANE, env=env)
    assert "state\tpending" in intent.stdout, (intent.stdout, intent.stderr)
    _log, last, _rows = _records(inv.e)
    assert last.endswith("; handoff refreshed"), last


def test_a_restart_intent_read_that_alone_fails_writes_the_swap_and_leaves_it_swapping(inv):
    """A FAILURE THAT COMES AND GOES (the review of R7, 658): only the
    handoff's own read of the restart intent fails - `restart-intent` is run
    with a git that fails every read of repoB-1's log, and every other read of
    it, before and after, is whole. That read said 8 and the handoff published
    and called the lane SWAPPED. It is R7's path now: the swap is written, the
    file is not published, and the lifecycle stays SWAPPING, because one of
    the writes a swap is made of did not land."""
    env, _checkout, handoff = _a_lane_with_a_row_and_a_handoff(inv)
    shim, calls = _git_shim(inv, SHOW_LOG_B1, first=1)
    wrapper = inv.root / "lanes-edit-wrapper"
    wrapper.mkdir()
    (wrapper / "lanes-edit.sh").write_text(
        "#!/bin/sh\n"
        "case \"${1-}\" in restart-intent) PATH=\"$SHIM_PATH\"; export PATH ;; esac\n"
        "exec \"$REAL_LANES_EDIT\" \"$@\"\n", encoding="utf-8")
    (wrapper / "lanes-edit.sh").chmod(0o755)
    extra = {key: value for key, value in shim.items() if key != "PATH"}
    extra.update(SHIM_PATH=shim["PATH"], REAL_LANES_EDIT=str(LANES_EDIT),
                 LANES_EDIT=str(wrapper / "lanes-edit.sh"))
    before = handoff.read_bytes()
    res = _hand_off(inv, env, "a swap whose one read failed", extra=extra)
    failed = _shim_calls(calls)
    state = inv.e.edit("lane-state", LANE, env=env)
    fields = dict(line.split("\t", 1) for line in state.stdout.splitlines() if "\t" in line)
    assert failed, "no read of the log failed: vacuous"
    problems = [] if res.returncode == 0 else [f"exit {res.returncode}: {_said(res)!r}"]
    problems += _the_swap_is_written(inv, res)
    if handoff.read_bytes() != before:
        problems.append("the handoff was published")
    if (fields.get("state"), fields.get("generation")) != ("SWAPPING", "2"):
        problems.append(f"the lifecycle is {fields.get('state')} at generation "
                        f"{fields.get('generation')}, not this handoff's SWAPPING")
    assert not problems, "\n" + "\n".join(problems) + f"\nshim: {failed}\n" + res.stderr[-1500:]


def test_lane_start_refuses_at_its_restart_fence_and_says_the_log_is_why(tmp_path):
    """`lane-start` OVER A LOG NOBODY COULD READ (the review of R7, the start
    consequence and 656). Its restart fence read 8 and went on, and it stopped
    later, at `lane-last`. It stops at the fence now, before anything is
    renamed, written or launched - and the fence threw the read's own words
    away, so its refusal says what 10 is: the lane's log could not be read."""
    box = StartSandbox(tmp_path / "start")
    box.env["LANES_NO_FETCH"] = "1"
    box.resolver()
    first = box.start("--no-launch")
    assert first.returncode == 0, (first.stdout, first.stderr)
    clone = types.SimpleNamespace(wip=box.wip,
                                  _git=lambda *a: box.git("-C", str(box.wip), *a))
    register = box.wip / "lanes" / "LANES.md"
    log_file = box.wip / "lanes" / "log" / f"{START_LANE}.md"
    before = (register.read_bytes(), log_file.read_bytes(), box.tmux_log.read_text())
    with _unreadable(clone, f"origin/main:lanes/log/{START_LANE}.md"):
        res = box.start()
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert "exited 10" in res.stderr and "object log could not be read" in res.stderr, res.stderr
    assert "Nothing was changed" in res.stderr, res.stderr
    assert not box.claude_runs().strip(), box.claude_runs()
    assert (register.read_bytes(), log_file.read_bytes(), box.tmux_log.read_text()) == before


def test_rename_lane_over_a_log_it_could_not_read_refuses_before_the_mutex(inv):
    """`rename-lane`, A CALLER THE DESIGN DID NOT LIST (the review of #303,
    546, and the behaviour change lane 3 accepted with R7's review). The old
    name's lifecycle root was read with `|| rl_lsr_old=""`, so over a log
    nobody read the rename went on and left the lane's snapshot and trees
    under the old name. It refuses now, naming the log, and before the mutex:
    here another live process holds it, and the refusal does not wait for it.
    With the log whole the same rename lands - the control."""
    env, _checkout, _handoff = _a_lane_with_a_row_and_a_handoff(inv)
    lock = inv.e.wip / "lanes" / ".lanes-edit.lock"
    lock.mkdir()
    (lock / "pid").write_text(f"{inv.sleeper.pid}\n", encoding="utf-8")
    tip = inv.e.tip()
    try:
        with _unreadable(inv.e, LOG_B1):
            try:
                res = inv.e.edit("rename-lane", LANE, "repoB-9", "--no-github", env=env, timeout=45)
            except subprocess.TimeoutExpired:
                pytest.fail("rename-lane waited on the mutex over a log it could not read: it "
                            "did not refuse before it")
    finally:
        (lock / "pid").unlink()
        lock.rmdir()
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
    assert f"lane {LANE}'s object log could not be read" in res.stderr, res.stderr
    assert "under the old name" in res.stderr and "Nothing was written" in res.stderr, res.stderr
    assert inv.e.tip() == tip, "the refused rename moved origin/main"
    landed = inv.e.edit("rename-lane", LANE, "repoB-9", "--no-github", env=env)
    assert landed.returncode == 0, (landed.returncode, landed.stdout, landed.stderr[-800:])


def test_rename_lane_with_no_root_established_still_renames(inv):
    """AND NO ROOT IS NOT A LOG NOBODY READ (lane 3's change to the behaviour
    change: refuse only on 1, and on 8 the old root stays empty). repoN-1's log
    is read and records no `dir`, and `$PROJECTS_ROOT` is not a directory
    here, so neither the lifecycle root nor the restart intent's has a rung:
    8, which renames as it always did."""
    env = {"LANES_LANE_STATE_ROOT": None, "LANES_NO_FETCH": "1",
           "PROJECTS_ROOT": str(inv.root / "no-projects-root")}
    e = inv.e
    register = e.wip / "lanes" / "LANES.md"
    lines = register.read_text(encoding="utf-8").split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith(f"| `{NO_LOG_LANE}` |"))
    lines.insert(at + 1, f"| `repoN-1` | harness `{UUID_B1}` | Eagle / test / brett | "
                         "2026-10-01T00:00Z | none | handoffs/repoN-1.md | PAUSED · "
                         "2026-10-05T00:00:00Z · parked |")
    register.write_text("\n".join(lines), encoding="utf-8")
    (e.wip / "handoffs").mkdir(exist_ok=True)
    (e.wip / "handoffs" / "repoN-1.md").write_text("Lane: repoN-1 — a handoff\n\nolder\n",
                                                   encoding="utf-8")
    (e.wip / "lanes" / "log" / "repoN-1.md").write_text(
        f"STARTED — lane repoN-1, session {UUID_B1}@Eagle, 2026-10-06T00:00:00Z, "
        "lane:repoN-1 → home opensoft/repoN\n", encoding="utf-8")
    e._git("add", "-A")
    e._git("commit", "-q", "-m", "repoN-1: a row, a handoff and a log with no dir")
    e._git("push", "-q", "origin", "main")
    root = e.edit("lane-state", "repoN-1", env=env)
    assert root.returncode == 1 and "has no lifecycle control root" in root.stderr, \
        (root.returncode, root.stderr)  # no rung: not vacuous
    res = e.edit("rename-lane", "repoN-1", "repoN-2", "--no-github", env=env)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr[-800:])
    rows = [line for line in register.read_text(encoding="utf-8").split("\n")
            if line.startswith("| `repoN-")]
    assert len(rows) == 1 and rows[0].startswith("| `repoN-2` "), rows


def test_lane_objects_with_nowhere_to_keep_its_reads_warnings_is_no_answer(inv):
    """THE ANSWER IS THE READ IT PROVED (544) ONLY WHERE THE READ'S WARNINGS
    ARE KEPT (lane 3's change to the behaviour change). With no temporary file
    they go to stderr and nowhere else, so whether repoB-1's log was read
    whole is not known - and `lane-objects` answered 0 with its rows, which
    `lane-end`'s gate ends a lane on. It is 1 now, naming the temporary
    directory and not the log, which nobody showed was unread; `who --lane`
    says the same."""
    env = {"LANES_NO_FETCH": "1"}
    whole = inv.e.edit("lane-objects", LANE, env=env)
    assert whole.returncode == 0 and "opensoft/repoB#3" in whole.stdout, whole.stderr
    nowhere = inv.root / "not-there"
    res = inv.e.edit("lane-objects", LANE, env={**env, "TMPDIR": str(nowhere)})
    who = inv.e.edit("who", "--lane", LANE, env={**env, "TMPDIR": str(nowhere)})
    said = f"no temporary file could be made under {nowhere}"
    assert res.returncode == 1 and res.stdout == "", (res.returncode, res.stdout, res.stderr)
    assert said in res.stderr, res.stderr
    assert "could not read lane repoB-1's object log" not in res.stderr, res.stderr
    assert who.returncode == 1, (who.returncode, who.stdout, who.stderr)
    assert said in who.stdout and "opensoft/repoB#3" not in who.stdout, who.stdout


@pytest.mark.parametrize("mode", [0o000, 0o400], ids=["dir-000", "dir-400"])
def test_the_inventory_with_no_origin_names_a_log_directory_it_cannot_list_once(inv, mode):
    """THE NO-ORIGIN SPELLING, PINNED ONCE (the behaviour change lane 3
    accepted). With no `origin` the inventory's `PARTIAL` line names this
    checkout's log directory, in that spelling and once: the reason it adds
    for a list of the logs that failed is spelled the same way, so the check
    that keeps one reason from being said twice compares like with like, and
    the origin's spelling never stands for a directory."""
    logdir = inv.e.wip / "lanes" / "log"
    logdir.chmod(mode)
    try:
        if _this_account_gets_in_anyway(logdir, "dir"):
            pytest.skip(f"this account searches a mode-{mode:03o} directory (root)")
        res = inv.e.edit("worktrees", "--all", env=dict(NO_GIT))
    finally:
        logdir.chmod(0o755)
    assert res.returncode == 0, (res.returncode, res.stderr)
    partial = [line.split(US) for line in res.stdout.splitlines() if line.startswith("PARTIAL" + US)]
    assert partial == [["PARTIAL", "Eagle",
                        f"the log directory {logdir} is there and could not be listed"]], partial
