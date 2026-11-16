# SPDX-License-Identifier: Apache-2.0
"""THE LANDING GATE'S READER (T280; Brett's "Temporary landing gate
(Recommended)", 2026-11-13; FR-059). TEMPORARY: T281 removes it in the last
set, T328's, with the hook in `tests/conftest.py`, the marker directory,
`tests/test_sql_register_gate.py`, its `repo_hygiene` row and every module's
table, and the whole suite then runs ungated.

Every 007 code pull request passes full CI, and 007's tests land before the
code they test. So from the first set until the last, a 007 test whose tasks
have not all landed is SKIPPED, and the skip names the tasks it waits for:
"waits for T415, T416".

THE TABLES. A 007 test module carries its own table, `SQL_REGISTER_GATE_TABLE`,
written from its task's **Order** and lane 2's per-id verdict rows, in that
task's own files. A key is one of:

  * `"*"`, the tasks every id of the module waits for;
  * a test function's name, for every id of that function;
  * one id with its parameters, `name[param]`, which replaces the function's
    row for that one id.

Each value is a tuple of 007 task ids. An id waits for the union of the
module's `"*"` row and its own row. An id that no table names runs, and so does
every id of a module with no table. This module adds no table of its own.

A key other than `"*"` that names no test of its module FAILS THE RUN, gated or
not, since a misspelled key matches nothing and the test it meant would run
ungated (Codex's review of E `d58f3b82`, BLOCKING 1). The names are every id
pytest's collection of the module holds and each id's function, read from the
module's own collect report before any `-k`, `-m`, `--deselect` or node-id
selection: `tests/conftest.py` gathers them. A module whose test class was not
collected (a node id elsewhere in it was named) is not checked in that run.

THE MARKERS. `tests/sql_register_landed/<Txxx>` is one empty file for each
landed task: a marker that is not an empty regular file, or a marker
directory that is a symlink, fails the run. Each code PR adds its tasks' markers at its cut, outside every
task's `files:`, and that one change turns the set's own tests on in its own
full CI. Git keeps no empty directory, so before the first set's cut there is
no directory, and a missing directory is read as "no task has landed".

007'S TASK IDS. The code leg holds no `tasks.md`, so the ids are carried here,
as `TASK_IDS`: tasks.md's task lines at `SPEC_COMMIT`. A table or a marker that
names anything else FAILS THE RUN, gated or not, so a bad row fails a local run
too. A task added to tasks.md later is added to `TASK_IDS` by the first code
PR whose table or marker names it.

WHEN THE GATE IS ACTIVE (lane 3's rulings, 2026-11-13 and 2026-11-14). Only in
a GitHub Actions run (`GITHUB_ACTIONS=true`) whose workflow is not `verify` and
whose ref is not a `verify/` branch. The ref is `GITHUB_HEAD_REF` on a
`pull_request` or `pull_request_target` event, whose `GITHUB_REF_NAME` is
`<number>/merge`, and `GITHUB_REF_NAME` on any other event. That covers each
pull request's CI, `main`'s CI and the merge queue's runs. Local runs, line R's
census, every `verify/` branch and every run of `verify.yml` run ungated: those
branches are cut from line R, which holds no markers, and a dispatched verify
run may be on any ref (`GITHUB_WORKFLOW` is `verify`), so no verify passes by
the gate's skip. `SQL_REGISTER_GATE=on` or `=off` overrides that either way,
and any other value of it is refused. Nothing under `.github/` sets it, nor
does `tests/run.sh`, as a `repo_hygiene` row holds.

The gate decides by landing state alone. With `OPENREPOTOOLS_REQUIRE_PG=1`, a
missing engine still refuses the run in `pgcluster.py`'s `pytest_configure`,
before any test is collected, so the gate's skip cannot hide one. Nor does
the reason carry pgcluster's "real PostgreSQL 16", so its banner never counts
a gated id as an engine skip.

Python 3.9 or later, standard library only. `tests/conftest.py` calls `gate()`
from its `pytest_collection_modifyitems`, after `-k` has deselected.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import AbstractSet, Dict, Iterable, List, Mapping, Optional, Tuple

#: The variable that overrides when the gate is active.
SWITCH = "SQL_REGISTER_GATE"

#: The name of a module's table.
TABLE = "SQL_REGISTER_GATE_TABLE"

#: The marker directory's name, beside `tests/conftest.py`.
LANDED = "sql_register_landed"

#: The key of a table's row for every id of its module.
EVERY = "*"

#: The spec commit `TASK_IDS` was read from: lane 3's commit 17 of 007's
#: follow-up, whose tasks.md has 158 task lines, T236's among them.
SPEC_COMMIT = "204145ae4b1acaeee0a841306a0563c3550c3528"

#: 007'S TASK IDS: the id of every task line of tasks.md at `SPEC_COMMIT`.
TASK_IDS = frozenset("""
    T101 T102 T103 T104 T105 T106 T107 T108 T109 T110 T111 T112 T113 T114
    T115 T116 T117 T118 T119 T120 T121 T122 T123 T124
    T200 T201 T202 T203 T204 T205 T206 T207 T210 T211 T212 T213 T214 T215
    T216 T217 T218 T219 T220 T221 T222 T223 T224 T225 T226 T227 T228 T229
    T230 T231 T232 T233 T234 T235 T236 T237 T240 T241 T242 T243 T244 T245
    T246 T247 T248 T251 T252 T253 T254 T255 T256 T257 T258 T259 T270 T271
    T272 T273 T274 T275 T276 T277 T278 T279 T280 T281
    T301 T302 T303 T304 T320 T321 T322 T323 T324 T325 T326 T327 T328 T340
    T341 T342 T343 T344 T345 T346 T347
    T401 T402 T403 T404 T405 T406 T407 T408 T409 T410 T411 T412 T413 T414
    T415 T416 T417 T418 T419 T420 T421 T422 T423 T424 T425 T426 T427 T428
    T429 T430 T431 T432 T433 T434
    T501 T502 T503 T504 T505 T506 T507 T508 T509 T510 T511 T512 T513 T514
""".split())

#: `verify.yml`'s `name:`, which GitHub gives a run of it as `GITHUB_WORKFLOW`
#: whatever its ref: a dispatched verify run is ungated too (lane 3's (b),
#: opensoft/openRepoTools#165 comment 6870017590).
VERIFY_WORKFLOW = "verify"

#: The events whose head branch is `GITHUB_HEAD_REF`.
PULL_REQUEST_EVENTS = ("pull_request", "pull_request_target")


class GateError(Exception):
    """A table, a marker or the switch the gate cannot read: the run fails.
    `tests/conftest.py` raises it as pytest's `UsageError`, exit 4."""


def in_task_order(tasks: Iterable[str]) -> Tuple[str, ...]:
    """`tasks` once each, by number: T205 before T415 before T416."""
    return tuple(sorted(set(tasks), key=lambda task: int(task[1:])))


def ref(environ: Mapping[str, str]) -> str:
    """The branch a GitHub Actions run is for."""
    if environ.get("GITHUB_EVENT_NAME", "") in PULL_REQUEST_EVENTS:
        return environ.get("GITHUB_HEAD_REF", "")
    return environ.get("GITHUB_REF_NAME", "")


def active(environ: Mapping[str, str]) -> bool:
    """Whether this run skips the ids whose tasks have not all landed."""
    value = environ.get(SWITCH, "")
    if value == "on":
        return True
    if value == "off":
        return False
    if value:
        raise GateError(f"{SWITCH}={value!r} is neither on nor off; unset, the "
                        f"landing gate (T280) is active only in a GitHub "
                        f"Actions run whose workflow is not {VERIFY_WORKFLOW} "
                        f"and whose ref is not a verify/ branch")
    if environ.get("GITHUB_ACTIONS", "") != "true":
        return False
    if environ.get("GITHUB_WORKFLOW", "") == VERIFY_WORKFLOW:
        return False
    return not ref(environ).startswith("verify/")


def landed(directory: Path) -> frozenset:
    """The tasks with a marker in `directory`. A missing directory is no task
    landed; anything in it but an empty regular file named for one of 007's
    task ids fails the run, and so does a `directory` that is a symlink or
    cannot be read (Codex's review of E `d58f3b82`, SHOULD 7)."""
    if directory.is_symlink():
        raise GateError(f"{directory} is a symlink: the landing gate (T280) "
                        f"reads its markers in a directory of the tree")
    if not directory.exists():
        return frozenset()
    if not directory.is_dir():
        raise GateError(f"{directory} is not a directory: the landing gate "
                        f"(T280) reads its markers there")
    found, refused = [], []
    try:
        entries = sorted(directory.iterdir())
    except OSError as exc:
        raise GateError(f"{directory} cannot be read ({exc.strerror or exc}): "
                        f"the landing gate (T280) reads its markers there") from None
    for entry in entries:
        try:
            mode = entry.lstat()
        except OSError:
            mode = None
        if (entry.name in TASK_IDS and mode is not None
                and stat.S_ISREG(mode.st_mode) and mode.st_size == 0):
            found.append(entry.name)
        else:
            refused.append(entry.name)
    if refused:
        raise GateError(f"{directory} holds {', '.join(refused)}: a marker is a "
                        f"file named for one of 007's task ids (tasks.md at "
                        f"{SPEC_COMMIT[:8]}), one for each landed task")
    return frozenset(found)


def table_of(module, names: Optional[AbstractSet[str]] = None
             ) -> Optional[Dict[str, Tuple[str, ...]]]:
    """`module`'s table, checked, or None where it has none. Where `names`, the
    module's every id and function, is given, a key outside it is refused."""
    raw = getattr(module, TABLE, None)
    if raw is None:
        return None
    where = f"{TABLE} in {getattr(module, '__file__', None) or module.__name__}"
    if not isinstance(raw, dict):
        raise GateError(f"{where} is a {type(raw).__name__}, not a dict of test "
                        f"name to the task ids it waits for")
    table: Dict[str, Tuple[str, ...]] = {}
    problems: List[str] = []
    for key, tasks in raw.items():
        if not isinstance(key, str) or not key:
            problems.append(f"the key {key!r} is not a test name, an id or {EVERY!r}")
            continue
        if isinstance(tasks, str) or not isinstance(tasks, (tuple, list)):
            problems.append(f"{key!r} maps to {tasks!r}, not a tuple of task ids")
            continue
        unknown = [task for task in tasks
                   if not isinstance(task, str) or task not in TASK_IDS]
        if unknown:
            problems.append(f"{key!r} names {', '.join(map(str, unknown))}, "
                            f"which {'is' if len(unknown) == 1 else 'are'} not "
                            f"one of 007's task ids")
            continue
        table[key] = tuple(tasks)
    if problems:
        raise GateError(f"{where}: {'; '.join(problems)} (007's task ids are "
                        f"tasks.md's task lines at {SPEC_COMMIT[:8]})")
    strangers = [key for key in table if key != EVERY and names is not None
                 and key not in names]
    if strangers:
        raise GateError(f"{where}: " + "; ".join(
            f"{key!r} names no test of its module" for key in strangers) +
            f" (a key is {EVERY!r}, a test function's name, or one of its ids "
            f"with its parameters)")
    return table


def waits_for(table: Mapping[str, Tuple[str, ...]], name: str,
              function: str) -> Tuple[str, ...]:
    """The tasks the id `name` of the test `function` waits for: the module's
    `"*"` row and its own, the id's row in place of the function's."""
    own = table[name] if name in table else table.get(function, ())
    return in_task_order(tuple(table.get(EVERY, ())) + tuple(own))


def reason(missing: Iterable[str]) -> str:
    """The skip's reason, naming the tasks it still waits for."""
    return (f"waits for {', '.join(in_task_order(missing))} (the landing gate, "
            f"T280: no marker in tests/{LANDED}/)")


def gate(items, modules: Iterable[object], environ: Mapping[str, str],
         directory: Path, names: Optional[Mapping[int, Optional[AbstractSet[str]]]] = None
         ) -> List[Tuple[object, str]]:
    """Each item to skip, with its reason. Every table of `modules` and every
    marker is checked first, gated or not; nothing is skipped where the gate
    is not active. `names` maps a module's `id()` to its every id and
    function, against which its table's keys are checked."""
    items = list(items)
    names = names or {}
    tables: Dict[int, Optional[Dict[str, Tuple[str, ...]]]] = {}
    for module in [*modules, *(getattr(item, "module", None) for item in items)]:
        if module is not None and id(module) not in tables:
            tables[id(module)] = table_of(module, names.get(id(module)))
    marked = landed(directory)
    if not active(environ):
        return []
    skips = []
    for item in items:
        table = tables.get(id(getattr(item, "module", None)))
        if not table:
            continue
        name = item.name
        tasks = waits_for(table, name, getattr(item, "originalname", None) or name)
        missing = [task for task in tasks if task not in marked]
        if missing:
            skips.append((item, reason(missing)))
    return skips
