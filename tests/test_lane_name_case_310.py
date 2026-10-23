# SPDX-License-Identifier: Apache-2.0
"""A LANE NAME TYPED IN ANOTHER CASE RESOLVES BY EVERY SOURCE THAT KNOWS THE
LANE, AND A SOURCE NOBODY COULD READ IS NEVER "NO SUCH LANE"
(opensoft/openRepoTools#310, from #290).

Amendment 15 makes a lane name ONE name under any case, with the register
row's spelling canonical, and `canon_lane` is the resolver every `<lane>`
argument goes through. It resolved by the register's rows and the alias table
alone, and it handed a name back as typed - status 0, no word - in two more
cases:

  * the register could not be read: `rows_named_ci` said so with a 1 and
    `rows_named_ci_alias` threw it away, so "could not read" was "no row";
  * the lane has no row and the archive's rows or the logs' file names know
    it: the listing names lanes from those too, the resolver never asked.

A name kept as typed builds a control root no lane has: on a case-sensitive
file system `lane-state`, `lane-trees`, `worktrees` and `restart-intent`
answered 8 over a snapshot and trees that are there, `lane-reconcile` said
`no-state`, and the writers filed a second directory beside the lane's own.

Brett Heap ruled R1 "Refuse": over an unreadable register every name refuses
(66 from `canon-lane`, 2 from every read and writer behind it), the handoff
included. Lane 3 ruled R2 (66 for an unreadable archive or list of the logs,
for a name no row answers), R3 and 584 (the callers' words name every input
and every source), 583 (66 has one meaning) and R4 (`lanes --lane` and the
log-only reads refuse too). The order is the row, the alias, the archive, the
logs, then the name as typed; two spellings in ONE source are 15(d)'s refusal.

`worktrees <lane>` keeps #290's contract: over an unreadable register it reads
the name as typed and says `UNREAD`, and the canonical spelling still answers.

Every case runs on `test_lanes_index`'s own estate and its helpers. Asserts
about a second directory are made by listing names, so a file system that
folds case proves them too.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from conftest import REPO, ROOTS
from test_lanes_index import (HEADS, UUID_A1B, US, _row, _sidecar, _unreadable, _wt, inv)

__all__ = ["inv"]  # the fixture, imported so that pytest finds it here

REGISTER = "origin/main:lanes/LANES.md"
ARCHIVE = "origin/main:lanes/archive/LANES-retired.md"
LOG_TREE = "origin/main:lanes/log"
NOF = {"LANES_NO_FETCH": "1"}

#: The words 583 gives exit 66 in `lanes-edit.sh`'s exit table: ONE meaning.
ONE_66 = "an input that `canon-lane` resolves names by could not be read"
#: Every input a name is resolved by, as R3's four 66 messages name them.
R3_INPUTS = "the register, the lane alias table, the archive or the list of the object logs"
#: Every source a pair can be in, as 584's six recognisers name them.
PAIR_SOURCES = "two register rows, two archived rows or two object logs"
#: Each source's remedy, as those six name them.
ROW_REMEDY = "the newer row's session id(s)"
LOG_REMEDY = "oldest lines first"

#: A tmux on PATH for the callers that ask for one: this window is
#: `testsess:@1`, index 0, named `claude`; EVERY call is logged, so a rename or
#: a respawn the refusal should have stopped is seen.
FAKE_TMUX = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_TMUX_LOG"
case "${1-}" in
  display-message)
    shift
    t=""; f=""
    while [ $# -gt 0 ]; do
      case "$1" in
        -p) shift ;;
        -t) t="${2-}"; shift 2 ;;
        *)  f="$1"; shift ;;
      esac
    done
    if [ -n "$t" ]; then
      case "$t" in testsess:0|testsess:@1|@1) : ;; *) exit 1 ;; esac
    fi
    case "$f" in
      '#{session_name}:#{window_id}')    echo 'testsess:@1' ;;
      '#{session_name}:#{window_index}') echo 'testsess:0' ;;
      '#S:#I')                           echo 'testsess:0' ;;
      '#{window_id}')                    echo '@1' ;;
      '#W'|'#{window_name}')             echo 'claude' ;;
      '#{session_name}')                 echo 'testsess' ;;
      '#{pane_current_command}')         echo 'claude' ;;
      *)                                 echo ;;
    esac ;;
esac
exit 0
"""

UUID_P1 = "aaaaaaaa-0310-4000-8000-000000000001"
UUID_P2 = "aaaaaaaa-0310-4000-8000-000000000002"
UUID_Q1 = "aaaaaaaa-0310-4000-8000-000000000003"
UUID_Q2 = "aaaaaaaa-0310-4000-8000-000000000004"
UUID_W1 = "aaaaaaaa-0310-4000-8000-000000000005"


# ------------------------------------------------------------- the helpers


def _edit(inv, *args: str, env: dict | None = None):
    return inv.e.edit(*args, env={**NOF, **(env or {})})


def _tool(inv, name: str, *args: str, env: dict | None = None):
    return inv.e.run("bash", REPO / name, *args, env={**NOF, **(env or {})})


def _files(root: Path) -> dict:
    """Every path under `root` with its bytes (None for a directory)."""
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))}


def _written(inv) -> tuple:
    """What a write would move: the workspace clone's status, HEAD and
    origin, and every file under the control roots. Asked OUTSIDE an
    `_unreadable` block, whose moved object `git status` may need."""
    e = inv.e
    return (e._git("status", "--porcelain"), e._git("rev-parse", "HEAD").strip(),
            e._git("rev-parse", "origin/main").strip(), _files(inv.lsr))


def _publish(inv, rel: str, text: str, message: str) -> None:
    """`rel` written through the working tree, committed and pushed."""
    path = inv.e.wip / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    inv.e._git("add", "-A")
    inv.e._git("commit", "-q", "-m", message)
    inv.e._git("push", "-q", "origin", "main")


def _archive_rows(inv, *rows: str, message: str) -> None:
    rel = "lanes/archive/LANES-retired.md"
    text = (inv.e.wip / rel).read_text(encoding="utf-8")
    _publish(inv, rel, text.rstrip("\n") + "\n" + "".join(r + "\n" for r in rows), message)


def _log(lane: str, uid: str) -> str:
    return (f"# lane {lane} — object log (lane-collision-protocol Amendment 7)\n"
            f"STARTED — lane {lane}, session {uid}@Eagle, 2026-10-01T00:00:00Z, "
            f"lane:{lane} → home opensoft/repoQ; dir /work/repoQ\n")


def _register_pair(inv) -> tuple:
    rel = "lanes/LANES.md"
    text = (inv.e.wip / rel).read_text(encoding="utf-8")
    rows = [_row("repoR-1", f"`{UUID_P1}`", "LIVE · 2026-10-02T00:00:00Z · one spelling"),
            _row("repor-1", f"`{UUID_P2}`", "LIVE · 2026-10-03T00:00:00Z · the other")]
    _publish(inv, rel, text.rstrip("\n") + "\n" + "\n".join(rows) + "\n", "a register pair")
    return "repoR-1", "repor-1"


def _archive_pair(inv) -> tuple:
    _archive_rows(inv, _row("repoP-1", f"`{UUID_P1}`", "RETIRED · 2026-09-02T00:00:00Z · retired"),
                  _row("repop-1", f"`{UUID_P2}`", "RETIRED · 2026-09-03T00:00:00Z · retired"),
                  message="an archive pair")
    return "repoP-1", "repop-1"


def _archive_repeat(inv) -> tuple:
    """ONE LANE ARCHIVED TWICE UNDER ONE SPELLING: retired, re-added and
    retired again (788). The estate archives `repoZ-1` once; this is its second
    row, spelled alike. It is one lane and no pair, so it is not one of PAIRS."""
    _archive_rows(inv, _row("repoZ-1", f"`{UUID_W1}`", "RETIRED · 2026-09-06T00:00:00Z · retired again"),
                  message="repoZ-1 archived a second time under one spelling")
    return "REPOZ-1", "repoZ-1"


def _log_pair(inv) -> tuple:
    """Two published logs one case apart, through git alone: a case-folding
    disk would make them one file (`commit_paths`)."""
    inv.e.commit_paths({"lanes/log/repoQ-1.md": _log("repoQ-1", UUID_Q1),
                        "lanes/log/repoq-1.md": _log("repoq-1", UUID_Q2)}, "a log pair")
    return "repoQ-1", "repoq-1"


PAIRS = {"register": _register_pair, "archive": _archive_pair, "logs": _log_pair}
SOURCE_WORD = {"register": "register", "archive": "archive", "logs": "object log"}


def _seed_known_lane(inv, lane: str) -> None:
    """A lane the register has no row for, with a snapshot (RUNNING, then
    SWAPPING), a tree record and a restart intent - each written under the
    lane's own spelling, as the fixture's lanes are."""
    op = "op-" + lane.lower()
    for args in (("set-lane-state", lane, "RUNNING", "--operation", op),
                 ("set-lane-state", lane, "SWAPPING", "--operation", op + "s",
                  "--expect", "RUNNING"),
                 ("set-restart-intent", lane, "pending", "--operation", op + "i",
                  "--reason", "seeded by #310")):
        res = _edit(inv, *args)
        assert res.returncode == 0, (args, res.stdout, res.stderr)
    _sidecar(inv.lsr, lane, HEADS[lane])


def _tmux(inv) -> tuple:
    """The logging tmux on PATH, and the environment that makes it this
    window's server."""
    fake = inv.e.fakebin / "tmux"
    fake.write_text(FAKE_TMUX, encoding="utf-8")
    fake.chmod(0o755)
    log = inv.root / "tmux.log"
    log.write_text("", encoding="utf-8")
    return {"TMUX": f"{inv.root}/fake-tmux-socket,0,0", "FAKE_TMUX_LOG": str(log)}, log


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _said(lines: list, at: int, count: int) -> str:
    """`count` source lines from `at`, as one line of text: Python's adjacent
    string literals are joined, as the interpreter joins them."""
    return re.sub(r'"\s+f?"', "", _flat(" ".join(line.strip() for line in lines[at:at + count])))


# ---------------------------------------- R1: an unreadable register refuses


@pytest.mark.parametrize("name", ["REPOA-1", "repoA-1", "NEWLANE-9"])
def test_canon_lane_over_an_unreadable_register_refuses_every_name(inv, name):
    """R1, "Refuse": a register nobody could read resolves NO name - not the
    other-case one, not the row's own spelling, not a name that is new. It
    is 66, `canon-lane`'s code for an input it could not read, with nothing
    on stdout and a note naming the register."""
    with _unreadable(inv.e, REGISTER):
        res = _edit(inv, "canon-lane", name)
    assert res.returncode == 66, (res.returncode, res.stdout, res.stderr)
    assert res.stdout == "", res.stdout
    assert "NOT established" in res.stderr and "lanes/LANES.md" in res.stderr, res.stderr


TREE_OBSERVATION = ("--branch", "feat/x", "--head", "9" * 40, "--upstream", "none",
                    "--dirty", "0", "--unpushed", "0")
UNREADABLE_REGISTER_ACTS = [
    ("register-row-canonical", ("register-row", "repoA-1")),
    ("register-row", ("register-row", "REPOA-1")),
    ("lane-state-canonical", ("lane-state", "repoA-1")),
    ("lane-state", ("lane-state", "REPOA-1")),
    ("lane-trees", ("lane-trees", "REPOA-1")),
    ("lane-reconcile", ("lane-reconcile", "REPOA-1")),
    ("restart-intent", ("restart-intent", "REPOA-1")),
    ("set-lane-state", ("set-lane-state", "REPOA-1", "SWAPPING", "--operation", "op-310")),
    ("set-lane-tree", ("set-lane-tree", "REPOA-1", "/nowhere/repoA-1/x") + TREE_OBSERVATION),
    ("set-restart-intent", ("set-restart-intent", "REPOA-1", "preparing", "--operation",
                            "op-310", "--reason", "#310")),
]


@pytest.mark.parametrize("args", [a for _, a in UNREADABLE_REGISTER_ACTS],
                         ids=[i for i, _ in UNREADABLE_REGISTER_ACTS])
def test_a_read_or_a_writer_over_an_unreadable_register_refuses_and_files_nothing(inv, args):
    """AND EVERY READ AND WRITER BEHIND IT REFUSES (2), never the 8 of "no
    row", "no snapshot" or "no trees" over records that are there, never
    `no-state` or `indeterminate`, and never the managed-owner fence's 1 in
    place of the resolver's own refusal. `register-row repoA-1` said 8 over
    a register that HAS the row."""
    before = _written(inv)
    with _unreadable(inv.e, REGISTER):
        res = _edit(inv, *args)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert res.stdout == "", res.stdout
    assert "NOT established" in res.stderr, res.stderr
    assert _written(inv) == before


def test_commit_with_a_lane_named_refuses_the_name_before_the_pathspec_check(inv):
    """#170 G13's COMMIT CASE WITH `LANES_LANE` SET (lane 3's ruling 1). The
    shell suite's case unsets it: `$LANES_PATH` is also where the register is
    read on origin, so a bogus one leaves a register nobody could read, and a
    lane that is named is refused by the resolver (2, "NOT established")
    before the pathspec check the case pins - HEAD, origin and the tree
    unmoved. Unnamed, the same call reaches that check (the control)."""
    bogus = {"LANES_PATH": ":(bogus)x"}
    before = _written(inv)
    named = _edit(inv, "commit", "attach nothing", env={**bogus, "LANES_LANE": "repoA-1"})
    assert named.returncode == 2, (named.returncode, named.stdout, named.stderr)
    assert "NOT established" in named.stderr, named.stderr
    unnamed = _edit(inv, "commit", "attach nothing", env=bogus)
    assert unnamed.returncode == 2, (unnamed.returncode, unnamed.stdout, unnamed.stderr)
    assert "could not read what this commit would stage" in unnamed.stderr, unnamed.stderr
    assert _written(inv) == before


def test_worktrees_over_an_unreadable_register_keeps_its_unread_line(inv):
    """CONTROL (#290's contract, green before and after): `worktrees <lane>`
    reads the name as typed over an unreadable register and says so in ONE
    `UNREAD` line where it found no tree, `lanes --worktrees` does not say
    "no worktree is inventoried", and the canonical spelling still lists the
    lane's two trees with no writer pronounced."""
    folds = (inv.lsr / "REPOA-1").is_dir()
    with _unreadable(inv.e, REGISTER):
        other = _edit(inv, "worktrees", "REPOA-1")
        listed = _wt(inv, "REPOA-1")
        same = _edit(inv, "worktrees", "repoA-1")
    assert other.returncode == 0, (other.returncode, other.stdout, other.stderr)
    lines = [line.split(US) for line in other.stdout.splitlines() if line]
    if not folds:
        assert len(lines) == 1 and lines[0][:3] == ["UNREAD", "Eagle", "REPOA-1"], other.stdout
        assert "the register lanes/LANES.md could not be read" in lines[0][3], lines[0]
    assert listed.returncode == 0, (listed.stdout, listed.stderr)
    assert "no worktree is inventoried" not in listed.stdout, listed.stdout
    assert same.returncode == 0, same.stderr
    trees = [line.split(US) for line in same.stdout.splitlines() if line.startswith("TREE" + US)]
    assert len(trees) == 2 and [f[10] for f in trees] == ["", ""], same.stdout


# --------------------- a lane the archive or the logs know, typed in any case


@pytest.mark.parametrize("typed,canonical", [
    ("REPOB-1", "repoB-1"), ("RePoB-1", "repoB-1"), ("REPOZ-1", "repoZ-1"),
    ("repoB-1", "repoB-1"), ("repoZ-1", "repoZ-1"),
], ids=["log-only", "log-only-mixed", "archive-only", "control-log-only", "control-archive-only"])
def test_a_lane_only_the_logs_or_the_archive_know_resolves_to_their_spelling(inv, typed, canonical):
    """repoB-1 has a log and no row; repoZ-1 an archived row and no log.
    Typed in another case, each resolves to the spelling its source holds;
    typed as it is spelled, it is unchanged (the controls)."""
    res = _edit(inv, "canon-lane", typed)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert res.stdout.strip() == canonical, res.stdout


READS = ["lane-state", "lane-trees", "worktrees", "lane-reconcile", "restart-intent"]


@pytest.mark.parametrize("read", READS)
@pytest.mark.parametrize("lane", ["repoB-1", "repoZ-1"])
def test_the_reads_of_such_a_lane_answer_alike_in_any_case(inv, lane, read):
    """THE SAME ANSWER WHATEVER CASE IS TYPED: no read answers 8 for a lane
    that has a snapshot, a tree record and a restart intent, and
    `lane-reconcile` reads the interrupted swap instead of `no-state`."""
    _seed_known_lane(inv, lane)
    own = _edit(inv, read, lane)
    assert own.returncode == 0 and own.stdout, (own.returncode, own.stdout, own.stderr)  # not vacuous
    other = _edit(inv, read, lane.upper())
    assert (other.returncode, other.stdout) == (0, own.stdout), (other.returncode, other.stdout,
                                                                 other.stderr)


WRITES = {
    "set-lane-state": (("RUNNING", "--operation", "op-w310"), "lane-state.yaml"),
    "set-lane-tree": (("/nowhere/w310",) + TREE_OBSERVATION, "trees"),
    "set-restart-intent": (("preparing", "--operation", "op-w310", "--reason", "#310"),
                           "restart-intent.yaml"),
}


@pytest.mark.parametrize("writer", list(WRITES))
@pytest.mark.parametrize("lane", ["repoB-1", "repoZ-1"])
def test_a_writer_typed_in_another_case_files_under_the_lanes_own_spelling(inv, lane, writer):
    """NO WRITER FILES A SECOND DIRECTORY. Typed `REPOB-1`, each writer filed
    `lane-state/REPOB-1/` beside the lane's own: a snapshot, a tree record or
    an intent no read under the lane's spelling ever finds. It files under
    the spelling the lane's source holds, and nowhere else."""
    rest, made = WRITES[writer]
    res = _edit(inv, writer, lane.upper(), *rest)
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    names = sorted(os.listdir(inv.lsr))
    assert lane.upper() not in names, names
    assert (inv.lsr / lane / made).exists(), (names, sorted(_files(inv.lsr)))


# ----------------------------------------------- 15(d): a pair in one source


@pytest.mark.parametrize("source", list(PAIRS), ids=["control-register", "archive", "logs"])
def test_a_case_pair_in_one_source_is_refused_naming_both(inv, source):
    """TWO SPELLINGS IN ONE SOURCE ARE AMENDMENT 15(d)'S REFUSAL, in every
    source a name is resolved by: two register rows (as before, the
    control), two archived rows, two published logs. 2, in the literal words
    the callers recognise, naming both spellings, the source and the merge,
    whichever spelling is typed."""
    one, two = PAIRS[source](inv)
    for typed in (one.upper(), one, two):
        res = _edit(inv, "canon-lane", typed)
        assert res.returncode == 2, (typed, res.returncode, res.stdout, res.stderr)
        assert res.stdout == "", res.stdout
        for said in ("Amendment 15(d)", one, two, SOURCE_WORD[source]):
            assert said in res.stderr, (typed, said, res.stderr)
        assert "merge" in res.stderr.lower(), res.stderr


def test_a_read_and_a_writer_refuse_an_archived_pair_and_file_nothing(inv):
    """AND THE REFUSAL REACHES EVERY `<lane>` READ AND WRITER (2), which
    filed and read under the name as typed."""
    _archive_pair(inv)
    before = _written(inv)
    for args in (("lane-state", "REPOP-1"), ("set-lane-state", "REPOP-1", "RUNNING",
                                              "--operation", "op-p310")):
        res = _edit(inv, *args)
        assert res.returncode == 2, (args, res.returncode, res.stdout, res.stderr)
        assert "Amendment 15(d)" in res.stderr, res.stderr
    assert _written(inv) == before


@pytest.mark.parametrize("source", list(PAIRS), ids=["control-register", "archive", "logs"])
def test_worktrees_of_a_case_pair_in_any_source_refuses_and_never_answers_8(inv, source):
    """787: `worktrees <lane>` REFUSES A PAIR (2) WHICHEVER SOURCE HOLDS IT, as
    the test above has the other reads and writers do for the archive's. Its
    arm keeps the typed name over a 66 (#290's `UNREAD` line) and over nothing
    else: a pair is the `*)` case, and where that case kept the name too the
    read went on and answered 8, "no worktree is inventoried", for a lane the
    register, the archive or the logs spell two ways. The words are
    `canon-lane`'s, in whichever spelling is typed, and nothing is written."""
    one, two = PAIRS[source](inv)
    before = _written(inv)
    for typed in (one.upper(), one, two):
        res = _edit(inv, "worktrees", typed)
        assert res.returncode == 2, (typed, res.returncode, res.stdout, res.stderr)
        assert res.stdout == "", res.stdout
        for said in ("Amendment 15(d)", one, two):
            assert said in res.stderr, (typed, said, res.stderr)
    assert _written(inv) == before


def test_a_lane_archived_twice_under_one_spelling_is_one_lane_and_no_pair(inv):
    """788: THE ARCHIVE SCAN COUNTS A SPELLING ONCE. A lane retired, re-added
    and retired again has two archived rows under one spelling: one lane.
    Amendment 15(d) refuses two SPELLINGS in one source, not two rows, so in
    any case typed it resolves to its spelling and nothing says "15(d)" - where
    a scan that counted rows would refuse a single-spelling lane that every act
    would then fail to name."""
    typed, canonical = _archive_repeat(inv)
    archived = (inv.e.wip / "lanes/archive/LANES-retired.md").read_text(encoding="utf-8")
    assert archived.count(f"| `{canonical}` |") == 2, archived  # the duplicate is there: not vacuous
    for name in (typed, canonical):
        res = _edit(inv, "canon-lane", name)
        assert (res.returncode, res.stdout.strip()) == (0, canonical), (name, res.returncode,
                                                                       res.stdout, res.stderr)
        assert "Amendment 15(d)" not in res.stderr, (name, res.stderr)


# ------------------------------ R2: an unreadable archive or list of the logs

UNREAD_SOURCES = {"archive": (ARCHIVE, "lanes/archive/LANES-retired.md"),
                  "log-list": (LOG_TREE, "lanes/log/")}


@pytest.mark.parametrize("name", ["NEWLANE-9", "REPOB-1"])
@pytest.mark.parametrize("source", list(UNREAD_SOURCES))
def test_an_unreadable_archive_or_log_list_refuses_a_name_no_row_answers(inv, source, name):
    """R2: 66. A name no row and no alias answers is asked of the archive and
    the logs, and where one of them could not be read whether it is a lane
    spelled another way is not established - for a new name too."""
    rev, named = UNREAD_SOURCES[source]
    with _unreadable(inv.e, rev):
        res = _edit(inv, "canon-lane", name)
    assert res.returncode == 66, (res.returncode, res.stdout, res.stderr)
    assert res.stdout == "", res.stdout
    assert "NOT established" in res.stderr and named in res.stderr, res.stderr


@pytest.mark.parametrize("typed,canonical", [("REPOA-1", "repoA-1"), ("REPOOLD-1", "repoA-2")],
                         ids=["control-row", "control-alias"])
@pytest.mark.parametrize("source", list(UNREAD_SOURCES))
def test_an_unreadable_archive_or_log_list_changes_no_name_a_row_answers(inv, source, typed,
                                                                         canonical):
    """CONTROL: a name the register's row or the alias table answers never
    asks the archive or the logs, so their failed read changes nothing."""
    with _unreadable(inv.e, UNREAD_SOURCES[source][0]):
        res = _edit(inv, "canon-lane", typed)
    assert (res.returncode, res.stdout.strip()) == (0, canonical), (res.returncode, res.stdout,
                                                                    res.stderr)


def test_the_archive_answers_before_the_list_of_the_logs_is_asked(inv):
    """THE ORDER: the archive is asked before the logs, so an archived lane
    resolves over a list of the logs that could not be made."""
    with _unreadable(inv.e, LOG_TREE):
        res = _edit(inv, "canon-lane", "REPOZ-1")
    assert (res.returncode, res.stdout.strip()) == (0, "repoZ-1"), (res.returncode, res.stdout,
                                                                    res.stderr)


@pytest.mark.parametrize("source", list(UNREAD_SOURCES))
def test_worktrees_of_a_name_no_row_answers_names_the_unread_source(inv, source):
    """`worktrees <lane>` KEEPS #290's `UNREAD` LINE where `canon-lane` refuses
    (66): over an archive or a list of the logs that could not be read, a name
    no row answers is read as typed, and the ONE line names the input - never
    8, "no worktree is inventoried", which is what the read says when the arm
    hands it no marker for the input that failed, having found no row, no log
    and no tree. NEWLANE-9 has no row, no former name, no archived row and no
    log in the estate, so only the unread input can make it answer at all."""
    rev, named = UNREAD_SOURCES[source]
    with _unreadable(inv.e, rev):
        res = _edit(inv, "worktrees", "NEWLANE-9")
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    lines = [line.split(US) for line in res.stdout.splitlines() if line]
    assert len(lines) == 1 and lines[0][:3] == ["UNREAD", "Eagle", "NEWLANE-9"], res.stdout
    assert named in lines[0][3], lines[0]


# ------------------------------------------------ kept, and the order of all


def test_a_new_name_stays_as_typed_and_an_unreadable_alias_table_keeps_its_words(inv):
    """CONTROL: a name nothing knows stays as typed (0), so `add-row` can
    create it - and an alias table that cannot be read still refuses with
    66 in its own words, while a name its row answers does not ask it."""
    for name in ("NEWLANE-9", "BrandNew-7"):
        res = _edit(inv, "canon-lane", name)
        assert (res.returncode, res.stdout.strip()) == (0, name), (res.stdout, res.stderr)
        assert "NOT established" not in res.stderr, res.stderr
    table = inv.root / "aliases-as-a-directory"
    table.mkdir()
    env = {"LANES_ALIASES_TSV": str(table), "LANES_ALIASES_PATH": "lanes/aliases-dir.tsv"}
    res = _edit(inv, "canon-lane", "NEWLANE-9", env=env)
    assert res.returncode == 66, (res.returncode, res.stdout, res.stderr)
    for said in ("COULD NOT BE READ", "FORMER name", "Amendment 16(e)"):
        assert said in res.stderr, (said, res.stderr)
    row = _edit(inv, "canon-lane", "REPOA-1", env=env)
    assert (row.returncode, row.stdout.strip()) == (0, "repoA-1"), (row.stdout, row.stderr)


def _row_and_archive(inv) -> tuple:
    _archive_rows(inv, _row("REPOA-1", f"`{UUID_W1}`", "RETIRED · 2026-09-04T00:00:00Z · x"),
                  message="an archived row spelled unlike the register's")
    return "repoa-1", "repoA-1"


def _alias_and_log(inv) -> tuple:
    _publish(inv, "lanes/log/REPOOLD-1.md", _log("REPOOLD-1", UUID_W1),
             "a log spelled as the alias table's former name")
    return "repoold-1", "repoA-2"


def _archive_and_log(inv) -> tuple:
    _archive_rows(inv, _row("repoW-1", f"`{UUID_W1}`", "RETIRED · 2026-09-05T00:00:00Z · x"),
                  message="an archived row")
    _publish(inv, "lanes/log/REPOW-1.md", _log("REPOW-1", UUID_W1),
             "a log spelled unlike the archived row")
    return "repow-1", "repoW-1"


ORDER = [("control-row-over-archive", _row_and_archive),
         ("control-alias-over-log", _alias_and_log),
         ("archive-over-log", _archive_and_log)]


@pytest.mark.parametrize("make", [m for _, m in ORDER], ids=[i for i, _ in ORDER])
def test_the_order_is_the_row_the_alias_the_archive_then_the_logs(inv, make):
    """THE FIRST SOURCE THAT KNOWS THE NAME SPELLS IT, and a later source
    spelling it otherwise is not a pair: two spellings are a refusal only
    inside ONE source."""
    typed, canonical = make(inv)
    res = _edit(inv, "canon-lane", typed)
    assert (res.returncode, res.stdout.strip()) == (0, canonical), (res.returncode, res.stdout,
                                                                    res.stderr)


# ------------------------------------------------------------- the callers


def _caller(inv, which: str, lane: str, checkout: str):
    if which == "lane-start":
        co = inv.root / "projects" / checkout
        co.mkdir(parents=True, exist_ok=True)
        env, _ = _tmux(inv)
        return _tool(inv, "lane-start", "--dry-run", "--no-launch", "--dir", str(co), lane, env=env)
    if which == "lane-end":
        return _tool(inv, "lane-end", lane)
    return _tool(inv, "lane", lane)


CALLERS = ["lane-start", "lane-end", "lane"]


@pytest.mark.parametrize("which", CALLERS)
def test_a_caller_over_an_unreadable_register_refuses_before_writing(inv, which):
    """R1 AT THE CALLERS: `lane-start` and `lane-end` take the 66 and refuse
    (2), `lane` refuses a read that did not answer (1), each relaying why -
    and nothing is written, renamed or launched."""
    before = _written(inv)
    with _unreadable(inv.e, REGISTER):
        res = _caller(inv, which, "REPOA-1", "repoA")
    want, said = {"lane-start": (2, "NOT established"), "lane-end": (2, "NOT established"),
                  "lane": (1, "exited 66")}[which]
    assert res.returncode == want, (res.returncode, res.stdout, res.stderr)
    assert said in res.stderr, res.stderr
    assert _written(inv) == before
    log = inv.root / "tmux.log"
    assert not log.exists() or "rename-window" not in log.read_text(), log.read_text()


@pytest.mark.parametrize("which", CALLERS)
@pytest.mark.parametrize("source", ["archive", "logs"])
def test_a_caller_relays_a_pair_outside_the_register(inv, source, which):
    """584 AT THE CALLERS: a pair in the archive or the logs is Amendment
    15(d)'s refusal (2), recognised by its literal words and relayed naming
    both spellings - not the retired fence's words, "no row", or 8."""
    one, two = PAIRS[source](inv)
    before = _written(inv)
    res = _caller(inv, which, one.upper(), one.lower().rsplit("-", 1)[0])
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    for said in ("Amendment 15(d)", one, two):
        assert said in res.stderr, (said, res.stderr)
    assert _written(inv) == before


def test_lane_handoff_over_an_unreadable_register_refuses_before_any_write(inv):
    """R1 AT THE HANDOFF (Brett Heap's ruling): the resolver's 66 reaches
    `lane-handoff`'s read fence, which dies (1) naming the exit - before the
    window is renamed, a PAUSED or SWAPPING record is written, a handoff
    file is filed or a pane is respawned."""
    env, log = _tmux(inv)
    env.update(CLAUDE_CODE_SESSION_ID=UUID_A1B, CLAUDE_PROFILE_NAME="team-01a")
    before = _written(inv)
    handoffs = _files(inv.e.wip / "handoffs")
    with _unreadable(inv.e, REGISTER):
        res = _tool(inv, "lane-handoff", "--lane", "REPOA-1", "--restart", "clear", env=env)
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
    assert "canon-lane` failed (exit 66)" in res.stderr, res.stderr
    assert _written(inv) == before
    assert _files(inv.e.wip / "handoffs") == handoffs
    calls = log.read_text(encoding="utf-8")
    for verb in ("rename-window", "respawn-pane", "send-keys"):
        assert verb not in calls, calls


# ----------------------------------- R4: the listing's row and the log reads


@pytest.mark.parametrize("name", ["repoA-1", "REPOA-1"])
def test_lanes_lane_over_an_unreadable_register_refuses(inv, name):
    """R4: `lanes --lane` gave a degraded row at 0 over an unreadable
    register. Its name is resolved first, so it refuses (2)."""
    with _unreadable(inv.e, REGISTER):
        res = _edit(inv, "lanes", "--lane", name)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert res.stdout == "", res.stdout
    assert "NOT established" in res.stderr, res.stderr


LOG_READS = ["lane-dir", "lane-profile", "lane-agent", "lane-transcript", "history",
             "lane-last", "last-session", "forks", "binding"]


@pytest.mark.parametrize("read", LOG_READS)
def test_a_log_only_read_over_an_unreadable_register_refuses(inv, read):
    """R4: the reads that need only the lane's log - which `log_path_ci`
    finds in any case - answered over an unreadable register. They resolve
    the name first like every other, so they refuse (2) too."""
    with _unreadable(inv.e, REGISTER):
        res = _edit(inv, read, "repoA-1")
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert res.stdout == "", res.stdout
    assert "NOT established" in res.stderr, res.stderr


# --------------------------------- 583, 584 and R3: the words, in the source


def _lines(rel: str) -> list:
    return (REPO / rel).read_text(encoding="utf-8").splitlines()


def test_exit_66_has_one_meaning_in_the_table_and_in_the_manual(inv):
    """583: "no two meanings on one number". The exit table's 66 row named
    the alias table alone; it is ONE meaning now, an input `canon-lane`
    resolves names by that could not be read. And the manual's `canon-lane`
    contract, which listed 0, 2 and 64, lists 66."""
    lines = _lines("lanes-edit.sh")
    at = next(i for i, line in enumerate(lines) if line.startswith("#  66  "))
    end = next(i for i in range(at + 1, len(lines)) if lines[i].strip() == "#")
    row = _flat(" ".join(line.lstrip("#") for line in lines[at:end]))
    assert ONE_66 in row, row
    manual = ROOTS.path_for("docs/README-lanes.md").read_text(encoding="utf-8")
    start = manual.index("**A lane name is ONE name under any case")
    contract = _flat(manual[start:manual.index("\n\n", start)])
    assert "canon-lane <name>" in contract, contract  # the paragraph: not vacuous
    assert "**66**" in contract, contract


def test_every_15d_citation_in_lanes_edit_names_the_amendment(inv):
    """584: a caller recognises Amendment 15(d)'s refusal by those literal
    words, and nine messages in `lanes-edit.sh` cited a bare `15(d)`. Every
    one outside a comment now says "Amendment 15(d)"."""
    bare = []
    for n, line in enumerate(_lines("lanes-edit.sh"), 1):
        if line.lstrip().startswith("#"):
            continue
        rest = line
        while "15(d)" in rest:
            at = rest.index("15(d)")
            if not rest[:at].endswith("Amendment "):
                bare.append(n)
                break
            rest = rest[at + 5:]
    assert bare == [], bare


RECOGNISERS = [("lane-start", '*"Amendment 15(d)"*'), ("lane-end", '*"Amendment 15(d)"*'),
               ("lane", '*"Amendment 15(d)"*'), ("lane-handoff", '*"Amendment 15(d)"*'),
               ("skills/handoff/SKILL.md", '*"Amendment 15(d)"*'),
               ("lane-worktrees", '"Amendment 15(d)" in (proc.stderr')]


@pytest.mark.parametrize("rel,literal", RECOGNISERS, ids=[r for r, _ in RECOGNISERS])
def test_each_pair_recogniser_keeps_the_literal_words_and_names_every_source(inv, rel, literal):
    """584: each of the six recognisers still matches the literal words
    "Amendment 15(d)" - the only thing that tells the refusal from an older
    helper's unknown-subcommand 2 - and the refusal it prints names every
    source a pair can be in and each one's remedy, where it named the
    register's rows alone."""
    lines = _lines(rel)
    hits = [i for i, line in enumerate(lines) if literal in line]
    assert len(hits) == 1, (rel, hits)
    said = _said(lines, hits[0], 16)
    for words in (PAIR_SOURCES, ROW_REMEDY, LOG_REMEDY):
        assert words in said, (rel, words, said)


R3_SITES = [("lane-start", "(above, exit 66)"), ("lane-end", "(above, exit 66)"),
            ("lane-worktrees", "if proc.returncode == 66:"),
            ("lanes-edit.sh", '66) die "')]  # `rename-lane`'s


@pytest.mark.parametrize("rel,anchor", R3_SITES, ids=[r for r, _ in R3_SITES])
def test_each_66_message_names_every_input_a_name_is_resolved_by(inv, rel, anchor):
    """R3: the four messages a 66 reaches blamed the alias table alone, under
    notes that now name the register, the archive or the list of the logs.
    Each names every input, keeping its own anchor."""
    lines = _lines(rel)
    hits = [i for i, line in enumerate(lines) if anchor in line]
    assert len(hits) == 1, (rel, hits)
    said = _said(lines, hits[0], 6)
    assert R3_INPUTS in said, (rel, said)


def test_lane_start_over_an_unreadable_alias_table_names_every_input(inv):
    """R3 AS RUN: `lane-start` still refuses (2) a name it cannot resolve, as
    the second row it would otherwise add, and names every input."""
    table = inv.root / "aliases-as-a-directory"
    table.mkdir()
    env, _ = _tmux(inv)
    env.update(LANES_ALIASES_TSV=str(table), LANES_ALIASES_PATH="lanes/aliases-dir.tsv")
    co = inv.root / "projects" / "newlane"
    co.mkdir(parents=True)
    res = _tool(inv, "lane-start", "--dry-run", "--no-launch", "--dir", str(co), "NEWLANE-9",
                env=env)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    for said in ("second row", "(above, exit 66)", R3_INPUTS):
        assert said in _flat(res.stderr), (said, res.stderr)
