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
it could not read for its root moves nothing and says why (R4).

Every case runs on `test_lanes_index`'s own estate and its helpers, and builds
on `test_named_read_unreadable_290`'s way of making a log unreadable.
"""

from __future__ import annotations

import os
import shutil

import pytest

from conftest import REPO, WINDOWS_SKIP
from test_lanes_index import (HEADS, SHOW_LOG_B1, UUID_A1B, UUID_B1, US, _git_shim, _shim_calls,
                              _sidecar, _unreadable, inv)

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
