# SPDX-License-Identifier: Apache-2.0
"""THE LANDING GATE, T280: ITS ELEVEN CASES (Brett's "Temporary landing gate
(Recommended)", 2026-11-13; FR-059). TEMPORARY: T281 removes this module with
the gate, in the last set.

`tests/conftest.py`'s hook, through its reader `tests/sql_register_gate.py`,
skips each 007 test whose tasks have not all landed, and the skip names them.
A test waits for what its module's `SQL_REGISTER_GATE_TABLE` says. A task has
landed when its marker is in `tests/sql_register_landed/`. The gate is active
only in a GitHub Actions run whose workflow is not `verify` and whose ref is
not a `verify/` branch, unless `SQL_REGISTER_GATE` is `on` or `off` (lane 3's
rulings, 2026-11-13, and (b), 2026-11-14, opensoft/openRepoTools#165 comments
6867533114 and 6870017590). Eight cases are T280's; the ninth is (b)'s; the
tenth, a gated run with no marker directory, is lane 2's review RV26's; the
eleventh, a table key naming no test, is Codex's review of E `d58f3b82`.

EACH CASE RUNS A CHILD PYTEST, since a table or a marker the gate cannot read
ends the session that reads it. The child runs in a code root of the case's
own, made of:
  * a copy of this suite's `conftest.py` and the local modules it imports, so
    the hook under test is the suite's own, byte for byte;
  * a probe module with a table;
  * a module with no table;
  * the marker directory the case writes.

The child sees no `GITHUB_*`, `SQL_REGISTER_GATE`, `OPENREPOTOOLS_*`, `PG*` or
`PYTEST_*` of the outer run, only what the case sets. It reports each id
through a JUnit file, which names the reason of every skip.

The cases about WHEN the gate is active also ask the reader's `active()`
directly. That covers the refs a child cannot be put on cheaply: a pull
request's head, the merge queue's branches, and a `verify/` head.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Dict, Iterable, NamedTuple, Tuple

import pytest

import sql_register_gate
from sql_register_gate import SWITCH, active

#: THIS SUITE: the child's `conftest.py` is a copy of the one beside this file.
SUITE = Path(__file__).resolve().parent

#: The probe module's table. Its ids wait for:
#:   * `test_gate_probe_waits`: T205, T415 and T416;
#:   * `test_gate_probe_runs`: T205 alone, from the `"*"` row;
#:   * `test_gate_probe_param[a]`: T205 and T415, by the function's row;
#:   * `test_gate_probe_param[b]`: T205 and T416, by its own row, which
#:     replaces the function's.
TABLE: Dict[str, Tuple[str, ...]] = {
    "*": ("T205",),
    "test_gate_probe_waits": ("T416", "T415"),
    "test_gate_probe_param": ("T415",),
    "test_gate_probe_param[b]": ("T416",),
}

PROBE = '''\
import pytest

SQL_REGISTER_GATE_TABLE = {table!r}


def test_gate_probe_waits():
    pass


def test_gate_probe_runs():
    pass


@pytest.mark.parametrize("case", ["a", "b"])
def test_gate_probe_param(case):
    pass
'''

#: A module with no table: its id runs, gated or not.
FREE = '''\
def test_gate_free_runs():
    pass
'''

ALL_IDS = ("test_gate_probe_waits", "test_gate_probe_runs",
           "test_gate_probe_param[a]", "test_gate_probe_param[b]",
           "test_gate_free_runs")

#: An Actions run of `tests.yml` on a push to `main`, where the gate is active.
ON_MAIN = {"GITHUB_ACTIONS": "true", "GITHUB_WORKFLOW": "tests",
           "GITHUB_EVENT_NAME": "push", "GITHUB_REF_NAME": "main"}

#: THE SKIP'S WORDS, WRITTEN OUT: what follows the tasks in every reason. A case
#: that pins the words compares with this and never with the reader's own
#: `reason()` (lane 2's RV26, SHOULD 2).
REASON_TAIL = " (the landing gate, T280: no marker in tests/sql_register_landed/)"

#: pgcluster's tag, which its banner counts as an engine skip: a gated id's
#: reason must never hold it (`pgcluster.py`'s `SKIP_TAG`).
ENGINE_TAG = "real PostgreSQL 16"

#: What the child must not inherit from the outer run.
NOT_INHERITED = ("GITHUB_", "OPENREPOTOOLS_", "PG", "PYTEST_", SWITCH)


def local_imports(path: Path) -> set:
    """The modules beside this one that `path` imports, at any depth."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return {name for name in names if (SUITE / f"{name}.py").is_file()}


def estate(where: Path, table=TABLE, markers: Iterable[str] = ()) -> Path:
    """A code root for one child: the suite's `conftest.py` and what it imports,
    the probe with `table`, the free module, and a marker for each of
    `markers`. No marker directory at all where `markers` is empty."""
    tests = where / "code" / "tests"
    tests.mkdir(parents=True)
    todo, copied = ["conftest"], set()
    while todo:
        name = todo.pop()
        if name not in copied:
            copied.add(name)
            shutil.copyfile(SUITE / f"{name}.py", tests / f"{name}.py")
            todo.extend(local_imports(SUITE / f"{name}.py") - copied)
    assert "sql_register_gate" in copied, f"conftest.py imports no reader: {copied}"
    (tests / "test_gate_probe.py").write_text(PROBE.format(table=table), encoding="utf-8")
    (tests / "test_gate_free.py").write_text(FREE, encoding="utf-8")
    markers = list(markers)
    if markers:
        landed = tests / sql_register_gate.LANDED
        landed.mkdir()
        for name in markers:
            (landed / name).write_text("", encoding="utf-8")
    return where / "code"


class Run(NamedTuple):
    code: int
    output: str
    #: Each id's outcome, `passed`, `skipped` or `failed`, and a skip's reason.
    ids: Dict[str, Tuple[str, str]]


def child(root: Path, *args: str, where: str = "tests", **env: str) -> Run:
    """`python -m pytest -q -rs tests` in `root`, with `env` and nothing of the
    outer run's that the gate or the suite's switches read. `args`, such as a
    `-k` selection, go before `tests`. `where`, in place of `tests`, names one
    node id to collect alone."""
    environ = {key: value for key, value in os.environ.items()
               if not key.startswith(NOT_INHERITED)}
    environ["PYTHONDONTWRITEBYTECODE"] = "1"
    environ.update(env)
    junit = root.parent / "junit.xml"
    command = [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider",
               f"--basetemp={root.parent / 'basetemp'}", f"--rootdir={root}",
               f"--junitxml={junit}", *args, where]
    proc = subprocess.run(command, cwd=str(root), env=environ, capture_output=True,
                          text=True, timeout=600, check=False)
    ids: Dict[str, Tuple[str, str]] = {}
    if junit.is_file():
        for case in ElementTree.parse(str(junit)).getroot().iter("testcase"):
            skipped = case.find("skipped")
            if skipped is not None:
                ids[case.get("name")] = ("skipped", skipped.get("message", ""))
            elif case.find("failure") is not None or case.find("error") is not None:
                ids[case.get("name")] = ("failed", "")
            else:
                ids[case.get("name")] = ("passed", "")
    return Run(proc.returncode, proc.stdout + proc.stderr, ids)


def shown(run: Run) -> str:
    return f"exit {run.code}; ids {run.ids}\n{run.output}"


def waits(*tasks: str) -> Tuple[str, str]:
    """A gated id's outcome: skipped, naming `tasks`."""
    return ("skipped", sql_register_gate.reason(tasks))


def every_id_runs(run: Run) -> bool:
    return run.code == 0 and run.ids == {name: ("passed", "") for name in ALL_IDS}


def gated_on_t205_alone(run: Run) -> bool:
    """With T205's marker alone, the outcome of a run whose gate is active."""
    return run.code == 0 and run.ids == {
        "test_gate_probe_waits": waits("T415", "T416"),
        "test_gate_probe_runs": ("passed", ""),
        "test_gate_probe_param[a]": waits("T415"),
        "test_gate_probe_param[b]": waits("T416"),
        "test_gate_free_runs": ("passed", ""),
    }


def test_a_table_naming_an_id_that_is_no_007_task_fails_the_run(tmp_path):
    """A table whose rows name T999 (a number no task line has) and T252x (a
    slice's letter, not a task) fails the run: pytest's own
    `UsageError`, exit 4, before any test runs. The refusal names the module's
    table, each row and each id. The run here is not gated (no Actions, no
    switch), so a bad row fails a local run too. A row whose task id is a list,
    which cannot be looked up, is refused the same way, exit 4, and is not
    pytest's internal error, exit 3 (lane 2's RV26, NIT 3). So is a table that
    is not a dict, a list of pairs here, named by its type. And a bad table
    fails the run even where `-k` deselects every id of its module, since the
    hook checks the table of every module the run collected, selected or not
    (lane 2's RV26, NIT 4). The control is the same code root with a good
    table, where every id runs, and where the same `-k` runs the module with
    no table alone."""
    bad = dict(TABLE)
    bad["test_gate_probe_waits"] = ("T415", "T999")
    bad["test_gate_probe_param[b]"] = ("T252x",)
    run = child(estate(tmp_path / "bad", table=bad))
    assert run.code == 4, f"a table naming no 007 task must fail the run:\n{shown(run)}"
    assert "ERROR: the landing gate (T280): SQL_REGISTER_GATE_TABLE in " in run.output, shown(run)
    assert "test_gate_probe.py" in run.output, shown(run)
    assert "'test_gate_probe_waits' names T999, which is not one of 007's task ids" in run.output, shown(run)
    assert "'test_gate_probe_param[b]' names T252x, which is not one of 007's task ids" in run.output, shown(run)
    assert "passed" not in run.output and not run.ids, f"a test ran:\n{shown(run)}"
    listed = dict(TABLE)
    listed["*"] = (["T205"],)
    unhashable = child(estate(tmp_path / "unhashable", table=listed))
    assert unhashable.code == 4, (
        f"a task id that is a list must be the gate's own refusal, not pytest's "
        f"internal error:\n{shown(unhashable)}")
    assert "'*' names ['T205'], which is not one of 007's task ids" in unhashable.output, shown(unhashable)
    assert "INTERNALERROR" not in unhashable.output and not unhashable.ids, shown(unhashable)
    wrong = child(estate(tmp_path / "wrong", table=[("*", ("T205",))]))
    assert wrong.code == 4, f"a table that is not a dict must fail the run:\n{shown(wrong)}"
    assert "test_gate_probe.py is a list, not a dict of test name to the task ids it waits for" in wrong.output, shown(wrong)
    assert "INTERNALERROR" not in wrong.output and not wrong.ids, shown(wrong)
    deselected = child(estate(tmp_path / "deselected", table=bad), "-k", "gate_free")
    assert deselected.code == 4, (
        f"a bad table must fail the run where -k deselects its module:\n{shown(deselected)}")
    assert "'test_gate_probe_waits' names T999, which is not one of 007's task ids" in deselected.output, shown(deselected)
    assert "passed" not in deselected.output and not deselected.ids, f"a test ran:\n{shown(deselected)}"
    good = child(estate(tmp_path / "good"))
    assert every_id_runs(good), f"the same root with a good table must run:\n{shown(good)}"
    good_k = child(estate(tmp_path / "good-k"), "-k", "gate_free")
    assert good_k.code == 0 and good_k.ids == {"test_gate_free_runs": ("passed", "")}, (
        f"-k 'gate_free' must deselect every id of the probe:\n{shown(good_k)}")
    assert "4 deselected" in good_k.output, shown(good_k)


def test_a_table_key_naming_no_test_of_its_module_fails_the_run(tmp_path):
    """A table key that names no test of its module fails the run, exit 4,
    before any test runs, gated or not: a misspelled function name,
    `test_gate_probe_wiats`, and an id with parameters its function does not
    have, `test_gate_probe_param[c]`. Either would otherwise match nothing,
    and the test it meant would run ungated (Codex's review of E `d58f3b82`,
    BLOCKING 1). The refusal names the module's table and each key. It holds
    where `-k` deselects every id of the module. The keys are checked against
    every id pytest's collection of the module holds, before any selection:
    with a good table, a run that names one node id, a function or one
    parametrized id, still accepts the rows of the ids it did not select, and
    gates the id it did."""
    bad = dict(TABLE)
    bad["test_gate_probe_wiats"] = bad.pop("test_gate_probe_waits")
    bad["test_gate_probe_param[c]"] = ("T416",)
    run = child(estate(tmp_path / "typo", table=bad))
    assert run.code == 4, f"a key naming no test must fail the run:\n{shown(run)}"
    assert "ERROR: the landing gate (T280): SQL_REGISTER_GATE_TABLE in " in run.output, shown(run)
    assert "test_gate_probe.py" in run.output, shown(run)
    assert "'test_gate_probe_wiats' names no test of its module" in run.output, shown(run)
    assert "'test_gate_probe_param[c]' names no test of its module" in run.output, shown(run)
    assert "passed" not in run.output and not run.ids, f"a test ran:\n{shown(run)}"
    deselected = child(estate(tmp_path / "typo-k", table=bad), "-k", "gate_free", **{SWITCH: "on"})
    assert deselected.code == 4, (
        f"a key naming no test must fail the run where -k deselects its module:\n{shown(deselected)}")
    assert "'test_gate_probe_wiats' names no test of its module" in deselected.output, shown(deselected)
    assert "passed" not in deselected.output and not deselected.ids, f"a test ran:\n{shown(deselected)}"
    good = child(estate(tmp_path / "good"))
    assert every_id_runs(good), f"the same root with a good table must run:\n{shown(good)}"
    one = child(estate(tmp_path / "one", markers=("T205",)),
                where="tests/test_gate_probe.py::test_gate_probe_runs", **{SWITCH: "on"})
    assert one.code == 0 and one.ids == {"test_gate_probe_runs": ("passed", "")}, (
        f"one node id must not refuse the rows of the ids it did not select:\n{shown(one)}")
    param = child(estate(tmp_path / "param", markers=("T205",)),
                  where="tests/test_gate_probe.py::test_gate_probe_param[a]", **{SWITCH: "on"})
    assert param.code == 0 and param.ids == {"test_gate_probe_param[a]": waits("T415")}, (
        f"one parametrized id must not refuse its sibling's row:\n{shown(param)}")


def test_a_marker_naming_an_id_that_is_no_007_task_fails_the_run(tmp_path):
    """A marker directory holding `T999` (a number no task line has) and a
    `.gitkeep` (the placeholder git's lack of empty directories invites) fails
    the run, exit 4, naming both and the directory. The run is not gated, so a
    bad marker fails a local run too. So does a marker named for a 007 task
    that is a directory, `T415`, or a symlink, `T416`, here to T205's own
    marker file: a marker is a file, and not a symlink (lane 2's RV26,
    NIT 4). So does a marker that is not empty, `T415` here, since a marker
    is one empty file; and a marker directory that is itself a symlink, here
    to a directory of good markers, since the markers are read in the tree
    (Codex's review of E `d58f3b82`, SHOULD 7). The control holds only 007
    tasks' markers, T236's among them (a task line since lane 3's commit 17,
    `204145ae`), and every id runs."""
    run = child(estate(tmp_path / "bad", markers=("T205", "T999", ".gitkeep")))
    assert run.code == 4, f"a marker naming no 007 task must fail the run:\n{shown(run)}"
    assert "ERROR: the landing gate (T280): " in run.output, shown(run)
    assert f"{sql_register_gate.LANDED} holds .gitkeep, T999: a marker is a file named for one of 007's task ids" in run.output, shown(run)
    assert "passed" not in run.output and not run.ids, f"a test ran:\n{shown(run)}"
    kinds = estate(tmp_path / "kinds", markers=("T205",))
    landed = kinds / "tests" / sql_register_gate.LANDED
    (landed / "T415").mkdir()
    (landed / "T416").symlink_to("T205")
    assert (landed / "T416").is_symlink() and (landed / "T416").is_file()
    shapes = child(kinds)
    assert shapes.code == 4, f"a marker that is a directory or a symlink must fail the run:\n{shown(shapes)}"
    assert f"{sql_register_gate.LANDED} holds T415, T416: a marker is a file named for one of 007's task ids" in shapes.output, shown(shapes)
    assert "passed" not in shapes.output and not shapes.ids, f"a test ran:\n{shown(shapes)}"
    full = estate(tmp_path / "full", markers=("T205",))
    (full / "tests" / sql_register_gate.LANDED / "T415").write_text("landed\n", encoding="utf-8")
    nonempty = child(full)
    assert nonempty.code == 4, f"a marker that is not empty must fail the run:\n{shown(nonempty)}"
    assert f"{sql_register_gate.LANDED} holds T415: a marker is a file named for one of 007's task ids" in nonempty.output, shown(nonempty)
    assert "passed" not in nonempty.output and not nonempty.ids, f"a test ran:\n{shown(nonempty)}"
    linked = estate(tmp_path / "linked")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    for name in ("T205", "T415", "T416"):
        (elsewhere / name).write_text("", encoding="utf-8")
    (linked / "tests" / sql_register_gate.LANDED).symlink_to(elsewhere, target_is_directory=True)
    rooted = child(linked, **{SWITCH: "on"})
    assert rooted.code == 4, f"a marker directory that is a symlink must fail the run:\n{shown(rooted)}"
    assert f"{sql_register_gate.LANDED} is a symlink" in rooted.output, shown(rooted)
    assert "passed" not in rooted.output and not rooted.ids, f"a test ran:\n{shown(rooted)}"
    good = child(estate(tmp_path / "good", markers=("T205", "T236", "T415")))
    assert every_id_runs(good), f"markers of 007 tasks must not fail the run:\n{shown(good)}"


def test_a_gated_id_is_reported_skipped_naming_the_tasks_it_waits_for(tmp_path):
    """With the gate on and T205's marker alone, `test_gate_probe_waits` is
    reported skipped with "waits for T415, T416". Its tasks are in task order,
    and T205, which has landed, is not named. Under `-rs` the line is at the
    probe's own path. `[a]` waits for the function's T415 and `[b]` for its own
    row's T416. The `"*"` row's id and the module with no table run. With T415
    marked too, the skips name T416 alone. The skips are marked after `-k` has
    deselected (`tests/conftest.py`'s `trylast`): with `-k 'gate_probe and not
    skip'`, every probe id is selected and the three gated ones are skipped as
    before. A hook that marked them before `-k` would let `not skip` deselect
    them, since `-k` matches an id's marker names (lane 2's RV26, NIT 4)."""
    run = child(estate(tmp_path / "t205", markers=("T205",)), **{SWITCH: "on"})
    assert gated_on_t205_alone(run), f"the gated ids, by the table:\n{shown(run)}"
    assert "SKIPPED [1] tests/test_gate_probe.py:" in run.output, shown(run)
    assert f"{sql_register_gate.reason(('T415', 'T416'))}" in run.output, shown(run)
    assert "waits for T415, T416 (" in run.output, shown(run)
    assert run.ids["test_gate_probe_waits"] == (
        "skipped", "waits for T415, T416" + REASON_TAIL), shown(run)
    assert not any(ENGINE_TAG in message for _, message in run.ids.values()), shown(run)
    assert "3 skipped" in run.output and "2 passed" in run.output, shown(run)
    later = child(estate(tmp_path / "t415", markers=("T205", "T415")), **{SWITCH: "on"})
    assert later.code == 0 and later.ids == {
        "test_gate_probe_waits": waits("T416"),
        "test_gate_probe_runs": ("passed", ""),
        "test_gate_probe_param[a]": ("passed", ""),
        "test_gate_probe_param[b]": waits("T416"),
        "test_gate_free_runs": ("passed", ""),
    }, f"with T415 landed, only T416 is waited for:\n{shown(later)}"
    selected = child(estate(tmp_path / "selected", markers=("T205",)),
                     "-k", "gate_probe and not skip", **{SWITCH: "on"})
    assert selected.code == 0 and selected.ids == {
        "test_gate_probe_waits": waits("T415", "T416"),
        "test_gate_probe_runs": ("passed", ""),
        "test_gate_probe_param[a]": waits("T415"),
        "test_gate_probe_param[b]": waits("T416"),
    }, f"the skips are marked after -k, so `not skip` keeps every gated id:\n{shown(selected)}"
    assert "1 deselected" in selected.output, shown(selected)


def test_with_the_gate_on_and_no_marker_directory_every_row_is_waited_for(tmp_path):
    """With the gate on and no marker directory at all, as the code leg is until
    the first set's cut (git keeps no empty directory), no task has landed.
    Every probe id is skipped, and each reason names every task of its rows in
    task order, the `"*"` row's T205 first: `test_gate_probe_runs` waits for
    T205 alone, by the `"*"` row. The module with no table runs. The reasons
    are written out here, not built by the reader. A reader that dropped the
    `"*"` row, or read a missing directory as every task landed, fails here
    (lane 2's RV26, SHOULDs 1 and 2)."""
    root = estate(tmp_path / "none")
    assert not (root / "tests" / sql_register_gate.LANDED).exists()
    run = child(root, **{SWITCH: "on"})
    assert run.code == 0 and run.ids == {
        "test_gate_probe_waits": ("skipped", "waits for T205, T415, T416" + REASON_TAIL),
        "test_gate_probe_runs": ("skipped", "waits for T205" + REASON_TAIL),
        "test_gate_probe_param[a]": ("skipped", "waits for T205, T415" + REASON_TAIL),
        "test_gate_probe_param[b]": ("skipped", "waits for T205, T416" + REASON_TAIL),
        "test_gate_free_runs": ("passed", ""),
    }, f"no marker directory is no task landed:\n{shown(run)}"
    assert "4 skipped" in run.output and "1 passed" in run.output, shown(run)
    assert not any(ENGINE_TAG in message for _, message in run.ids.values()), shown(run)


def test_an_id_whose_tasks_all_have_markers_is_never_skipped(tmp_path):
    """With the gate on and a marker for each of T205, T415 and T416, every
    id runs and passes, and nothing is skipped."""
    run = child(estate(tmp_path / "all", markers=("T205", "T415", "T416")),
                **{SWITCH: "on"})
    assert every_id_runs(run), f"every task has landed:\n{shown(run)}"
    assert "skipped" not in run.output and "SKIPPED" not in run.output, shown(run)


def test_the_gate_is_active_in_an_actions_run_on_a_ref_outside_verify(tmp_path):
    """An Actions run of a push to `main`, with no switch, is gated. So, by the
    reader, is every other run on a ref outside `verify/`:
      * a pull request's CI, whose ref is its head branch, not
        `GITHUB_REF_NAME`'s `<n>/merge`;
      * the merge queue's runs, on Mergify's `mergify/merge-queue/…`
        candidates or a `gh-readonly-queue/…` ref;
      * `main`'s nightly, a release branch, and a dispatch.
    A head ref is read only on a pull request's events."""
    run = child(estate(tmp_path / "main", markers=("T205",)), **ON_MAIN)
    assert gated_on_t205_alone(run), f"a push to main in Actions is gated:\n{shown(run)}"
    actions = {"GITHUB_ACTIONS": "true"}
    for event, ref_name, head in (
            ("pull_request", "12/merge", "lane2/007-T243"),
            ("pull_request_target", "12/merge", "lane2/007-T243"),
            ("pull_request", "13/merge", "mergify/merge-queue/0123456789"),
            ("merge_group", "gh-readonly-queue/main/pr-12-" + "0" * 40, ""),
            ("schedule", "main", ""),
            ("workflow_dispatch", "lane2/007-T280", ""),
            ("push", "release/v1.3", ""),
            ("push", "main", "verify/not-read-on-a-push")):
        environ = dict(actions, GITHUB_EVENT_NAME=event, GITHUB_REF_NAME=ref_name,
                       GITHUB_HEAD_REF=head)
        assert active(environ), f"not active on {environ}"


def test_the_gate_is_inactive_on_a_verify_ref(tmp_path):
    """An Actions run of a push to a `verify/` branch runs every id: such a
    branch is cut from line R and holds no markers, and no verify may pass by
    the gate's skip. By the reader, a pull request whose head is under
    `verify/` is not gated either."""
    run = child(estate(tmp_path / "verify", markers=("T205",)),
                GITHUB_ACTIONS="true", GITHUB_EVENT_NAME="push",
                GITHUB_REF_NAME="verify/lane2/T280")
    assert every_id_runs(run), f"a verify/ ref runs ungated:\n{shown(run)}"
    for event in ("pull_request", "pull_request_target"):
        environ = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": event,
                   "GITHUB_REF_NAME": "12/merge", "GITHUB_HEAD_REF": "verify/lane2/T280"}
        assert not active(environ), f"active on {environ}"


def test_the_gate_is_inactive_in_a_dispatched_verify_run_on_any_ref(tmp_path):
    """A run of `verify.yml` dispatched on `main` runs every id: GitHub names
    its workflow `verify` (`GITHUB_WORKFLOW`, verify.yml's `name:`), and a
    verify run is ungated on any ref, so no verify passes by the gate's skip
    (lane 3's (b), 6870017590). By the reader the same holds on a lane's
    branch and on a pull request's head. The same dispatch of `tests.yml`
    is gated, and so is a workflow merely named like it. `SQL_REGISTER_GATE=on`
    still gates a verify run."""
    run = child(estate(tmp_path / "dispatch", markers=("T205",)),
                GITHUB_ACTIONS="true", GITHUB_WORKFLOW="verify",
                GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REF_NAME="main")
    assert every_id_runs(run), f"a dispatched verify run is ungated:\n{shown(run)}"
    verify = {"GITHUB_ACTIONS": "true", "GITHUB_WORKFLOW": "verify"}
    for event, ref_name, head in (
            ("workflow_dispatch", "lane2/007-T280", ""),
            ("pull_request", "12/merge", "lane2/007-T243"),
            ("push", "main", "")):
        environ = dict(verify, GITHUB_EVENT_NAME=event, GITHUB_REF_NAME=ref_name,
                       GITHUB_HEAD_REF=head)
        assert not active(environ), f"active on {environ}"
    for workflow in ("tests", "Verify", "verify-shadow"):
        environ = {"GITHUB_ACTIONS": "true", "GITHUB_WORKFLOW": workflow,
                   "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF_NAME": "main"}
        assert active(environ), f"not active on {environ}"
    assert active(dict(verify, GITHUB_EVENT_NAME="workflow_dispatch",
                       GITHUB_REF_NAME="main", **{SWITCH: "on"})), "on must gate verify"


def test_the_gate_is_inactive_outside_github_actions(tmp_path):
    """A run on `main` that is not a GitHub Actions run runs every id:
    `GITHUB_ACTIONS` is not `true` there. Local runs and line R's census are such
    runs."""
    run = child(estate(tmp_path / "local", markers=("T205",)),
                GITHUB_EVENT_NAME="push", GITHUB_REF_NAME="main")
    assert every_id_runs(run), f"a run outside Actions runs ungated:\n{shown(run)}"
    for value in (None, "", "false", "1"):
        environ = {"GITHUB_EVENT_NAME": "push", "GITHUB_REF_NAME": "main"}
        if value is not None:
            environ["GITHUB_ACTIONS"] = value
        assert not active(environ), f"active on {environ}"


def test_the_switch_at_on_or_off_overrides_where_the_gate_is_active(tmp_path):
    """`SQL_REGISTER_GATE=on` gates a run outside Actions, and `=off` ungates
    an Actions run on `main`. By the reader, each holds on any ref. Any other
    value is refused, exit 4, naming it, as the suite's other switches refuse
    a value that is neither."""
    on = child(estate(tmp_path / "on", markers=("T205",)), **{SWITCH: "on"})
    assert gated_on_t205_alone(on), f"on, outside Actions, is gated:\n{shown(on)}"
    off = child(estate(tmp_path / "off", markers=("T205",)), **dict(ON_MAIN, **{SWITCH: "off"}))
    assert every_id_runs(off), f"off, in Actions on main, is ungated:\n{shown(off)}"
    bad = child(estate(tmp_path / "bad", markers=("T205",)), **{SWITCH: "1"})
    assert bad.code == 4, f"{SWITCH}=1 must be refused:\n{shown(bad)}"
    assert f"ERROR: the landing gate (T280): {SWITCH}='1' is neither on nor off" in bad.output, shown(bad)
    assert "passed" not in bad.output and not bad.ids, f"a test ran:\n{shown(bad)}"
    verify = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
              "GITHUB_REF_NAME": "verify/lane2/T280"}
    assert active(dict(verify, **{SWITCH: "on"})), "on must gate a verify/ ref"
    assert not active({**ON_MAIN, SWITCH: "off"}), "off must ungate main"
    assert not active({SWITCH: "off"}), "off must ungate a local run"
    with pytest.raises(sql_register_gate.GateError):
        active({SWITCH: "ON"})
