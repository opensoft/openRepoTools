# SPDX-License-Identifier: Apache-2.0
"""Feature 007's test 3, the marker `lanes/STORE` (AT-3; opensoft/openRepoTools#165).

T225 (L2-N7; A8): `wip init`'s two cases, AT-3's three reader cases and lane
5's three marker guesses, all in phase N, all FM, with no database:

- `openRepoTools wip init` refuses under the marker, and wherever any file
  under `lanes/` exists with no marker, with no configuration and with
  `mode=index` (Q14(a); FR-005). The refusal exits 2, under the marker and
  without it, names the path it found, and prints no `mode=primary` line: that
  line and AT-3's 69 are the writers' (lane 3, #165 6771319904; T225c). They
  fail until lane 3's T303 lands.
- The readers' marker check, F17 (design Y, "F17: the marker check for
  readers"; Y:3055-3068): on a workstation that is not `mode=primary`, a
  reader checks the ref its read uses for `lanes/STORE`; an act refuses 69
  and the guard 2, both with Amendment 22's text, and the listings and the
  `SessionStart` block read on with the `read: mirror` line. All six are
  lane 5's L5-A5, T504 to T508 (T225's Order), and each fails only until the
  task whose `verify:` runs it: AT-3's three reader cases until T504
  (tasks:713, at B19 and at the follow-up head `09096c6d`), and lane 5's
  three guesses until T506, T507 and T508, one each, as their docstrings
  say.

T242 (L2-W1, L2-W5; FR-002, FR-004, FR-059) adds test 3's unit form and
AT-F8, phase W, FM, with no database: the writers' marker check, and every
failure of the mode query. They fail until lane 4's L4-B1 (T409) and L4-B12
(T419) and lane 5's L5-A5 land. See "phase W: T242" below.

The estate is T215's and T220's, as T203c's helper test builds it: a bare
origin, the lane's checkout under `$HOME/projects`, `$HOME/.agents/
workspace.yaml` naming it, and the register pushed. The marker is committed
by hand on the origin (lane 4's row 8), with D21's five fields one per line in
D21's order (Y:613-615; lane 1, F10's items 22 and 23).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import textwrap
import time
import uuid
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from sql_register_helpers import GUARD_WINDOW, guard_session, guard_strip_env

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280; task sets version 12b's rule 11,
#: opensoft/openRepoTools#165 6877673742), TEMPORARY: T281 removes it in the
#: last set. `tests/sql_register_gate.py` reads it: in a code pull request's
#: full CI, each id of a function below is skipped until every task its row
#: names has landed, and the skip names them. The rows are T225's Order
#: (tasks:2166) and T242's (tasks:2331), tasks.md at lane 3's commit 17
#: `204145ae`. No task is common to all 13 functions, so there is no "*" row.
SQL_REGISTER_GATE_TABLE = {
    # T225: `wip init`'s two cases until T303; AT-3's three reader cases until
    # T504, whose verify runs them (tasks:713); lane 5's three guesses until
    # their own tasks, one each: T506 (tasks:769), T508 (tasks:822) and T507
    # (tasks:780).
    "test_wip_init_refuses_under_the_marker": ("T303",),
    "test_wip_init_refuses_where_a_lanes_file_exists_with_no_marker": ("T303",),
    "test_a_readers_refusal_under_the_marker_names_the_refs_age": ("T504",),
    "test_a_reader_refuses_when_its_read_ref_carries_the_marker_and_its_tree_does_not": ("T504",),
    "test_an_unconfigured_workstations_acts_refuse_and_listings_read_the_mirror": ("T504",),
    "test_the_marker_check_runs_at_the_end_of_log_sync": ("T506",),
    "test_the_session_start_block_reads_on_under_the_marker_with_its_mirror_line": ("T508",),
    "test_a_mode_index_guard_refuses_2_under_the_marker": ("T507",),
    # T242: the writer cases until T419 (L4-B12), the `mode=index` one also
    # until T409 (L4-B1); the q6c case until T409; and AT-F8's ids until
    # T409, its `sql` ones also until T419: the function's row holds both,
    # and each of its 20 `files` ids has its own row, T409 alone (lane 3's
    # ruling 7, opensoft/openRepoTools#165 6879724890).
    "test_a_files_mode_writer_refuses_under_the_marker": ("T419",),
    "test_a_mode_index_writer_refuses_under_the_marker": ("T409", "T419"),
    "test_a_writer_with_no_fetch_refuses_when_its_tip_carries_the_marker": ("T419",),
    "test_the_q6c_refusal_has_its_own_code_and_the_writer_exits_69": ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning": ("T409", "T419"),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[refused-2-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[refused-2-primary-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[too-old-64-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[too-old-64-primary-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[crash-1-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[crash-1-primary-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[removed-127-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[removed-127-primary-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[signal-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[signal-primary-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[not-one-line-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[not-one-line-primary-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[exit-69-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[exit-69-primary-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[exit-75-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[exit-75-primary-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[exit-3-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[exit-3-primary-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[hang-index-files]":
        ("T409",),
    "test_any_other_mode_query_failure_runs_files_mode_with_a_warning[hang-primary-files]":
        ("T409",),
}

EDIT = REPO / "lanes-edit.sh"
LANES = REPO / "lanes"
COMMAND = REPO / "openRepoTools"

#: Amendment 22's text, the refusal of an act and of the guard under the
#: marker (Y:3060-3062; AT-3's oracle).
AMENDMENT_22 = "this estate's register is SQL; configure `mode=primary`"
#: The third line of the `read:` family (Y:3048-3050): `read: mirror at
#: <sha12>, <k> sequences behind or unknown (sql unreachable: <why>)`.
MIRROR_LINE = "read: mirror at "
#: How old the ref is, in the refusal (AT-3: "its text says how old the ref it
#: read is"): a count with a unit, or "ago". The form is not fixed by any
#: contract; this is the loosest reading of it.
AGE = re.compile(r"\b\d+ ?(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hour|hours|"
                 r"d|day|days|w|week|weeks)\b|\bago\b", re.I)

#: D21's five fields, one per line, in D21's order.
STORE_TEXT = ("store=primary\ndatabase=lanes-register-test\n"
              "import=0123456789abcdef0123456789abcdef01234567\n"
              "lanes-tree=89abcdef0123456789abcdef0123456789abcdef\n"
              "utc=2026-10-01T00:00:00Z\n")
#: The marker commit's date, so its age is days, never seconds.
MARKER_DATE = "2026-10-01T00:00:00Z"
DOT = chr(0xB7)
REGISTER_HEADER = ["# LANES.md", "",
                   "| lane | session id | workstation / env / user | started (UTC) | objects "
                   "owned | handoff path | state |",
                   "|---|---|---|---|---|---|---|"]
CONFIGURATIONS = ("none", "index")
#: `wip init`'s refusal code, under the marker and without it (lane 3, #165
#: 6771319904; `openRepoTools:3682`: "EXIT CODES ARE 0 AND 2"), and the text of
#: the `mode=primary` line, which is the writers' and never `wip init`'s.
WIP_REFUSED = 2
MODE_PRIMARY = "mode=primary"


def _register(session_id: str) -> str:
    """A register whose one row binds `GUARD_WINDOW` to `session_id`, in
    T215's row form."""
    row = (f"| `{GUARD_WINDOW}` | harness `{session_id}` | Eagle / test / brett "
           f"| 2026-10-01T00:00Z | none | handoffs/{GUARD_WINDOW}.md "
           f"| LIVE {DOT} 2026-10-01T02:00:00Z {DOT} working |")
    return "\n".join(REGISTER_HEADER + [row, ""])


def _git(cwd: Path, env: dict, *argv: str) -> str:
    return subprocess.run(["git", *argv], cwd=str(cwd), check=True, env=env,
                          capture_output=True, text=True).stdout.strip()


def _configure(root: Path, env: dict, configuration: str) -> None:
    """No configuration, or `mode=index` (AT-3's two configurations), in
    `$XDG_CONFIG_HOME/openRepoTools/lanes-index.conf`, mode 0600 (CLI section 2.5)."""
    if configuration == "index":
        conf = Path(env["XDG_CONFIG_HOME"]) / "openRepoTools" / "lanes-index.conf"
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text("mode=index\n", encoding="utf-8")
        conf.chmod(0o600)


def _push_marker(root: Path, origin: Path, env: dict) -> str:
    """Commit `lanes/STORE` by hand on origin's `main`, from a clone of its
    own (lane 4's row 8). Returns the marker commit's sha."""
    hand = root / "hand"
    subprocess.run(["git", "clone", "-q", str(origin), str(hand)], check=True, env=env,
                   capture_output=True)
    (hand / "lanes" / "STORE").write_text(STORE_TEXT, encoding="utf-8")
    dated = dict(env, GIT_AUTHOR_DATE=MARKER_DATE, GIT_COMMITTER_DATE=MARKER_DATE)
    _git(hand, dated, "add", "lanes/STORE")
    _git(hand, dated, "commit", "-q", "-m", "cutover: lanes/STORE")
    _git(hand, dated, "push", "-q", "origin", "main")
    return _git(hand, env, "rev-parse", "HEAD")


def _estate(root: Path, session_id: str, configuration: str = "none") -> tuple:
    """T215's and T220's estate, whose register's row names `session_id`.
    Returns (`home`, the checkout, the origin, the base environment)."""
    home = root / "home"
    wip = home / "projects" / "wip"
    origin = root / "origin.git"
    wip.parent.mkdir(parents=True)
    (root / "t").mkdir()
    env = guard_strip_env(os.environ)
    env.update(HOME=str(home), XDG_STATE_HOME=str(root / "state"),
               XDG_CONFIG_HOME=str(root / "config"), TMPDIR=str(root / "t"),
               LANES_WORKSTATION="Eagle", LANES_NO_GITHUB="1", LANES_NO_FETCH="1",
               LANES_REPO=str(wip),
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True,
                   env=env)
    subprocess.run(["git", "clone", "-q", str(origin), str(wip)], check=True, env=env,
                   capture_output=True)
    (wip / "lanes" / "log").mkdir(parents=True)
    (wip / "lanes" / "LANES.md").write_text(_register(session_id), encoding="utf-8")
    (wip / "lanes" / "log" / "README.md").write_text("logs.\n", encoding="utf-8")
    for argv in (["add", "-A"], ["commit", "-q", "-m", "C"], ["push", "-q", "origin", "main"]):
        _git(wip, env, *argv)
    (home / ".agents").mkdir()
    (home / ".agents" / "workspace.yaml").write_text(
        f"repository: {origin}\npath: {wip}\n", encoding="utf-8")
    _configure(root, env, configuration)
    return home, wip, origin, env


def _run(argv: list, env: dict, cwd: Path, stdin: str = "") -> tuple:
    """One run of the lane tooling. Returns (its exit, stdout, stderr)."""
    proc = subprocess.run(["bash", *map(str, argv)], input=stdin, capture_output=True,
                          text=True, cwd=str(cwd), env=env, timeout=120,
                          start_new_session=True)
    return proc.returncode, proc.stdout, proc.stderr


# --- `wip init` (T303) --------------------------------------------------------

#: The nine template files (`openRepoTools`' `WIP_TEMPLATE_FILES`), served by
#: the fake `gh` from a directory of its own, so these cases need no submodule.
TEMPLATE_FILES = ("README.md", "AGENTS.md", "CLAUDE.md", ".gitattributes",
                  ".gitignore", "handoffs/README.md", "lanes/LANES.md",
                  "lanes/log/README.md", "workspaces/.gitkeep")


def _template_text(rel: str) -> str:
    """A template file's stand-in text: one comment line, so `.gitignore`
    ignores nothing, and `.gitkeep` empty, as upstream's is."""
    return "" if rel.endswith(".gitkeep") else f"# {rel}\n"


def _wip_fake_gh(root: Path) -> Path:
    """A `gh` that answers `wip init`'s calls as `test_wip_init_command.py`'s
    does, with the repository already created by an administrator, and serves
    the template from `<root>/shape`. A `curl` that refuses."""
    shape = root / "shape" / "templates" / "workspace-root"
    for rel in TEMPLATE_FILES:
        (shape / rel).parent.mkdir(parents=True, exist_ok=True)
        (shape / rel).write_text(_template_text(rel), encoding="utf-8")
    server = root / "github"
    fake = root / "fake-path"
    fake.mkdir()
    (fake / "gh").write_text(textwrap.dedent(f"""\
        #!/usr/bin/env bash
        set -u
        server={server!s}
        slug_path() {{ printf '%s\\n' "$server/$1.git"; }}
        case "$1 ${{2-}}" in
        "api user") printf '%s\\n' brettheap; exit 0 ;;
        "api --paginate") printf '%s\\n' platform; exit 0 ;;
        esac
        case "$*" in
        "repo view "*) [ -d "$(slug_path "$3")" ] && exit 0; exit 1 ;;
        "repo create "*) exit 1 ;;
        "repo clone "*)
            git clone -q "$(slug_path "$3")" "$4" || exit 1
            git -C "$4" config user.email wip@example.invalid
            git -C "$4" config user.name "wip init tests"
            exit 0 ;;
        "api --method PUT"*) exit 0 ;;
        *"/contents/"*)
            path="${{*}}"; path="${{path##*/contents/}}"; path="${{path%%\\?*}}"
            src="{root / 'shape'!s}/$path"
            [ -f "$src" ] && exec cat -- "$src"
            exit 1 ;;
        esac
        printf 'fake gh: unexpected call: %s\\n' "$*" >&2
        exit 1
        """), encoding="utf-8")
    (fake / "curl").write_text("#!/bin/sh\nprintf 'no test here may reach the network\\n' >&2\n"
                               "exit 1\n", encoding="utf-8")
    for name in ("gh", "curl"):
        (fake / name).chmod(0o755)
    return fake


def _wip_origin(root: Path, files: dict, env: dict) -> Path:
    """`opensoft/brettheap-wip` on the fake server, its `main` carrying
    `files` (path to text), as an administrator or a cutover left it."""
    origin = root / "github" / "opensoft" / "brettheap-wip.git"
    origin.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True,
                   env=env)
    seed = root / "seed"
    subprocess.run(["git", "clone", "-q", str(origin), str(seed)], check=True, env=env,
                   capture_output=True)
    for rel, text in files.items():
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        (seed / rel).write_text(text, encoding="utf-8")
    _git(seed, env, "add", "-A")
    _git(seed, env, "commit", "-q", "-m", "the estate as it stands")
    _git(seed, env, "push", "-q", "origin", "main")
    return origin


def _wip_init(root: Path, files: dict, configuration: str) -> tuple:
    """Runs `openRepoTools wip init` against an origin carrying `files`.
    Returns (exit, output, origin's refs before, origin's refs after, the
    checkouts under `$HOME/projects` with a commit origin's `main` lacks)."""
    root.mkdir(parents=True, exist_ok=True)
    home = root / "home"
    (home / "projects").mkdir(parents=True)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("LANES_", "OPENREPOTOOLS_", "CLAUDE_", "GIT_"))
           and k not in ("AGENT_PROTOCOL_ROOT", "PROJECTS_DIR", "PROJECTS_ROOT", "TMUX",
                         "TMUX_PANE")}
    env.update(HOME=str(home), AGENT_PROTOCOL_ROOT=str(home / ".agents"),
               PROJECTS_DIR=str(home / "projects"), OPENREPOTOOLS_BIN_DIR=str(home / "bin"),
               XDG_CONFIG_HOME=str(root / "config"), XDG_STATE_HOME=str(root / "state"),
               GIT_AUTHOR_NAME="wip tests", GIT_COMMITTER_NAME="wip tests",
               GIT_AUTHOR_EMAIL="wip@example.invalid",
               GIT_COMMITTER_EMAIL="wip@example.invalid")
    fake = _wip_fake_gh(root)
    env["PATH"] = f"{fake}{os.pathsep}{env.get('PATH', '/usr/bin:/bin')}"
    origin = _wip_origin(root, files, env)
    _configure(root, env, configuration)
    before = _git(origin, env, "for-each-ref", "--format=%(refname) %(objectname)")
    main = _git(origin, env, "rev-parse", "main")
    proc = subprocess.run(["bash", str(COMMAND), "wip", "init"], capture_output=True,
                          text=True, cwd=str(REPO), env=env, input="", timeout=120,
                          check=False)
    after = _git(origin, env, "for-each-ref", "--format=%(refname) %(objectname)")
    ahead = []
    for checkout in sorted((home / "projects").iterdir()):
        if (checkout / ".git").exists():
            head = _git(checkout, env, "rev-parse", "HEAD")
            status = _git(checkout, env, "status", "--porcelain", "--", ".")
            if head != main or status:
                ahead.append(f"{checkout.name}: HEAD {head[:12]}, status {status!r}")
    return proc.returncode, proc.stdout + proc.stderr, before, after, ahead


def _assert_wip_refused(code: int, out: str, before: str, after: str, ahead: list,
                        path: str, where: str) -> None:
    """T303's refusal (lane 3, #165 6771319904): exit 2, `openRepoTools`'
    refusal code ("EXIT CODES ARE 0 AND 2", `openRepoTools:3682`), the path it
    found named, no `mode=primary` line, nothing committed or queued, and
    origin's refs unchanged."""
    assert code == WIP_REFUSED, \
        f"{where}: wip init exited {code}, not {WIP_REFUSED}, with {path} on origin\n{out[-900:]}"
    assert path in out, f"{where}: the refusal does not name {path}\n{out[-900:]}"
    primary = [x for x in out.splitlines() if MODE_PRIMARY in x]
    assert not primary, \
        f"{where}: wip init prints a {MODE_PRIMARY} line, which is the writers': {primary}"
    assert after == before, f"{where}: origin's refs moved\n{before}\n->\n{after}"
    assert not ahead, f"{where}: a commit or a write is queued: {ahead}\n{out[-900:]}"


def test_wip_init_refuses_under_the_marker(tmp_path):
    """AT-3 (Q14(a); FR-005): with `lanes/STORE` on origin's `main`, `wip init`
    refuses with 2, names the marker, prints no `mode=primary` line and
    commits nothing, the same with no configuration and with `mode=index`.
    Fails until T303."""
    files = {rel: _template_text(rel) for rel in TEMPLATE_FILES
             if not rel.endswith(".gitkeep")}
    files["lanes/log/README.md"] = "logs.\n"
    files["lanes/STORE"] = STORE_TEXT
    for configuration in CONFIGURATIONS:
        code, out, before, after, ahead = _wip_init(tmp_path / configuration, files,
                                                    configuration)
        _assert_wip_refused(code, out, before, after, ahead, "lanes/STORE", configuration)


@pytest.mark.parametrize("found", ["LANES.md", "repos.tsv"])
@pytest.mark.parametrize("configuration", CONFIGURATIONS)
def test_wip_init_refuses_where_a_lanes_file_exists_with_no_marker(tmp_path, configuration,
                                                                   found):
    """AT-3's third exception: with no marker and one file under `lanes/`,
    `wip init` refuses with 2, names the file, prints no `mode=primary` line
    and commits nothing. `LANES.md` is found with `lanes/log/README.md`
    missing, the file today's run commits as owed (`openRepoTools:5026-5080`);
    `repos.tsv` is found alone. Fails until T303."""
    files = {"README.md": _template_text("README.md"), f"lanes/{found}": f"lanes/{found}\n"}
    code, out, before, after, ahead = _wip_init(tmp_path, files, configuration)
    _assert_wip_refused(code, out, before, after, ahead, f"lanes/{found}",
                        f"{configuration}-{found}")


# --- the readers' marker check, F17 (L5-A5) -----------------------------------

def _who(wip: Path, env: dict) -> tuple:
    return _run([EDIT, "who", "--lane", GUARD_WINDOW], env, wip)


def test_a_readers_refusal_under_the_marker_names_the_refs_age(tmp_path):
    """AT-3 (Q21(a)(A)): an unconfigured reader whose read ref carries the
    marker refuses with 69, Amendment 22's text, and how old that ref is
    (Y:3065: "the refusal says how old it is"). Fails until T504."""
    home, wip, origin, env = _estate(tmp_path, str(uuid.uuid4()))
    _push_marker(tmp_path, origin, env)
    _git(wip, env, "fetch", "-q", "origin", "main")
    _git(wip, env, "merge", "-q", "--ff-only", "origin/main")
    code, out, err = _who(wip, env)
    assert code == 69, f"who exited {code} under the marker\n{out[-600:]}{err[-600:]}"
    assert AMENDMENT_22 in err, f"no Amendment 22 text on stderr\n{err[-900:]}"
    line = next(x for x in err.splitlines() if AMENDMENT_22 in x or "origin/main" in x)
    assert "origin/main" in err and AGE.search(err), \
        f"the refusal names no age for the ref it read ({line!r})\n{err[-900:]}"


def test_a_reader_refuses_when_its_read_ref_carries_the_marker_and_its_tree_does_not(
        tmp_path):
    """AT-3: the check runs on the ref the read uses, never the working tree.
    The checkout's tree lacks `lanes/STORE` and `origin/main` carries it: the
    reader refuses 69. Then a tree that carries it over a ref that does not
    reads on as today. Fails until T504."""
    home, wip, origin, env = _estate(tmp_path / "a", str(uuid.uuid4()))
    _push_marker(tmp_path / "a", origin, env)
    _git(wip, env, "fetch", "-q", "origin", "main")
    assert not (wip / "lanes" / "STORE").exists()
    code, out, err = _who(wip, env)
    assert code == 69 and AMENDMENT_22 in err, \
        f"the ref carries the marker, the tree does not: {code}\n{out[-600:]}{err[-600:]}"

    home, wip, origin, env = _estate(tmp_path / "b", str(uuid.uuid4()))
    (wip / "lanes" / "STORE").write_text(STORE_TEXT, encoding="utf-8")
    _git(wip, env, "add", "lanes/STORE")
    _git(wip, env, "commit", "-q", "-m", "a local marker, never pushed")
    code, out, err = _who(wip, env)
    assert code != 69 and AMENDMENT_22 not in err, \
        f"the tree carries the marker, the ref does not: {code}\n{out[-600:]}{err[-600:]}"


def test_an_unconfigured_workstations_acts_refuse_and_listings_read_the_mirror(tmp_path):
    """AT-3 (Q21(a)(A)): on an unconfigured workstation under the marker,
    `who` exits 69 with Amendment 22's text, and the listing, `lanes --all`
    (which today exits 0 and lists the lane), reads on, exits 0 and prints the
    `read: mirror` line at origin's tip. Fails until T504, whose `verify:`
    runs it (tasks:713); T507, the guard's, does not bear on it (T225d)."""
    home, wip, origin, env = _estate(tmp_path, str(uuid.uuid4()))
    marker = _push_marker(tmp_path, origin, env)
    _git(wip, env, "fetch", "-q", "origin", "main")
    code, out, err = _who(wip, env)
    assert code == 69 and AMENDMENT_22 in err, f"who: {code}\n{out[-600:]}{err[-600:]}"
    code, out, err = _run([LANES, "--all"], env, wip)
    assert code == 0, f"lanes --all: {code}\n{out[-600:]}{err[-600:]}"
    assert f"{MIRROR_LINE}{marker[:12]}" in err, \
        f"lanes --all printed no `read: mirror at {marker[:12]}` line on stderr\n{err[-900:]}"
    assert GUARD_WINDOW in out, f"lanes --all did not read on\n{out[-900:]}"


def test_the_marker_check_runs_at_the_end_of_log_sync(tmp_path):
    """Lane 5's guess for T506 (A5), its name kept: the checkout has not
    fetched since the cutover, so its ref has no marker; the act's own
    `log_sync` fetch brings it, and F17 at `log_sync`'s end refuses 69 with
    Amendment 22's text. Fails until T506."""
    home, wip, origin, env = _estate(tmp_path, str(uuid.uuid4()))
    _push_marker(tmp_path, origin, env)
    env = dict(env)
    env.pop("LANES_NO_FETCH")
    code, out, err = _who(wip, env)
    assert _git(wip, env, "rev-parse", "origin/main") == _git(origin, env, "rev-parse", "main"), \
        "the act's log_sync did not fetch"
    assert code == 69 and AMENDMENT_22 in err, \
        f"log_sync brought the marker: {code}\n{out[-600:]}{err[-600:]}"


def test_the_session_start_block_reads_on_under_the_marker_with_its_mirror_line(tmp_path):
    """Lane 5's guess for T508 (A5), its name kept: off primary, under the
    marker, the `SessionStart` block reads on, exits 0, and prints the
    `read: mirror` line at origin's tip. Fails until T508."""
    sid = str(uuid.uuid4())
    home, wip, origin, env = _estate(tmp_path, sid)
    marker = _push_marker(tmp_path, origin, env)
    _git(wip, env, "fetch", "-q", "origin", "main")
    hook = '{"session_id":"%s","source":"startup"}' % sid
    code, out, err = _run([EDIT, "session-start"], env, wip, stdin=hook)
    assert code == 0, f"session-start: {code}\n{out[-600:]}{err[-600:]}"
    assert f"{MIRROR_LINE}{marker[:12]}" in out + err, \
        f"no `read: mirror at {marker[:12]}` line\n{out[-600:]}{err[-600:]}"
    assert GUARD_WINDOW in out + err, f"the block did not read on\n{out[-900:]}"


def test_a_mode_index_guard_refuses_2_under_the_marker(tmp_path):
    """Lane 5's guess for T507 (A7), its name kept: on a `mode=index`
    workstation, the guard whose register row names its session refuses 2
    with Amendment 22's text once its read ref carries the marker (F17 in
    `guard_run`; W:4896). Without the marker the same guard passes, 0.
    Fails until T507."""
    sid = str(uuid.uuid4())
    home, wip, origin, env = _estate(tmp_path, sid, configuration="index")
    env = dict(env, LANES_LANE=GUARD_WINDOW)
    with guard_session(home, tmp_path / "bin", wip, session_id=sid) as session:
        def guard():
            return subprocess.run(["bash", str(EDIT), "guard"], input=session.hook_input(),
                                  capture_output=True, text=True, cwd=str(wip),
                                  env=session.env(env), timeout=60, start_new_session=True)
        proc = guard()
        assert proc.returncode == 0, \
            f"the mode=index guard with no marker: {proc.returncode}\n" \
            f"{proc.stdout[-600:]}{proc.stderr[-600:]}"
        _push_marker(tmp_path, origin, env)
        _git(wip, env, "fetch", "-q", "origin", "main")
        proc = guard()
    assert proc.returncode == 2 and AMENDMENT_22 in proc.stderr, \
        f"the mode=index guard under the marker: {proc.returncode}\n" \
        f"{proc.stdout[-600:]}{proc.stderr[-600:]}"


# ============================================================ phase W: T242
#
# TEST 3'S UNIT FORM AND AT-F8 (lane 2's T242; the test plan's AT-3 and AT-F8).
#
# THE WRITERS' MARKER CHECK (T419, L4-B12): a writer that is not `mode=primary`
# tests the tip its own S3 fetch brought for `lanes/STORE`, and under the
# marker exits 69 with Amendment 22's text, writing nothing; under
# `LANES_NO_FETCH=1` it tests the tip as last fetched. The marker is committed
# by hand on a bare origin (lane 4's row 8), and the writer's clone is one
# commit behind it, so the writer's own fetch brings it.
#
# THE MODE QUERY (T409, L4-B1; design Y, "The mode query's failures", F8's
# table): where a configuration exists the writer asks `lanes-index mode` once,
# on a 2 s client timer. Q6(c)'s 78 exits 69 with the build's refusal text,
# writing nothing; every other failure runs files mode with one warning, and
# the marker check then refuses it on a SQL estate. `LANES_INDEX=off` never
# skips the ask. The answers come from a stand-in at `lanes-index`'s path,
# `$SCRIPT_DIR/lanes-index`, the resolver's first choice (T409, "One
# resolver"), so the case runs a copy of `lanes-edit.sh` beside it, with
# `repos.tsv` and `lane-start`, the other files it reads from `$SCRIPT_DIR`
# (T409, "The tests' copy rule"; plan section 4.1).
#
# THE VERBS are S1's writes, the write guard's fourteen verbs at a2073eae
# (`lanes-edit.sh:16537`), `commit`'s publish act among them (T419: "That is
# the write guard's verbs, `commit`'s publish act included"). Each one's
# arguments reach its write today: with no marker each writes, pushes and
# exits 0. Under the marker, at a2073eae, eleven still write and exit 0, and
# `archive-rows`, `migrate-state-cells` and `retire-rows` refuse 2, since
# their own fetch leaves the checkout behind origin; from slice 1b on, each
# of the three runs `checkout_sync` first, which fast-forwards it, and T419's
# check sits there, after the fetch. `start-record` (T427, L4-B9) is not
# among them: it lands in no fixed order with T419, whose verify selects
# these ids.
#
# THE ESTATE is test 1's fixture register (T210's `SEED`, at C) on a bare
# origin, with the start state three verbs need (T241's `PREPS`), the
# workspace `workspace.yaml` names, and a `tmux` that answers nothing.
#
# They fail until L4-B1, L4-B12 and L5-A5 land, each by its own assertion:
# today's `lanes-edit.sh` asks no mode and checks no marker, so every write
# lands and exits 0.

EM, ARROW = chr(0x2014), chr(0x2192)
WRITER_WS = "Eagle"
SID_A1 = "aaaaaaaa-0001-4000-8000-00000000a001"
SID_A2 = "aaaaaaaa-0003-4000-8000-00000000a003"
SID_Z1 = "eeeeeeee-0001-4000-8000-00000000e001"
#: The session `request-handoff --force` writes its `PAUSED` for (`--session`).
SID_REQUESTER = "bbbbbbbb-0007-4000-8000-00000000b007"
TIP = "0123456789abcdef0123456789abcdef01234567"


def _row(lane: str, sid: str, state: str, started: str = "2026-10-01T00:00Z") -> str:
    return (f"| `{lane}` | harness `{sid}` | Eagle / test / brett | {started} | none "
            f"| handoffs/{lane}.md | {state} |")


#: Test 1's fixture register at C (T210's `SEED`): two lanes and an archived
#: one, `aliases.tsv`, a lane with `HOLD`, `LANDING` and `LANDED` lines, and
#: `repos.tsv` naming `repoA`.
SEED = {
    "lanes/LANES.md": "\n".join([
        f"# LANES.md {EM} test 1's fixture register",
        "",
        "| lane | session id | workstation / env / user | started (UTC) | objects owned "
        "| handoff path | state |",
        "|---|---|---|---|---|---|---|",
        _row("repoA-1", SID_A1, f"LIVE {DOT} 2026-10-01T01:00:00Z {DOT} working"),
        _row("repoA-2", SID_A2, f"PAUSED {DOT} 2026-10-01T02:00:00Z {DOT} parked"),
        "",
        f"HOLD {EM} lane repoA-1 (Eagle), window w, 2026-10-01T03:00:00Z: opensoft/repoA main "
        f"{TIP} for a frozen window",
        f"LANDING {EM} lane repoA-1, session {SID_A1}@Eagle, 2026-10-01T03:10:00Z, PR #7 into "
        f"opensoft/repoA main",
        f"LANDED {EM} lane repoA-1, session {SID_A1}@Eagle, 2026-10-01T03:15:00Z, PR #7 into "
        f"opensoft/repoA main {ARROW} abc1234",
        ""]),
    "lanes/aliases.tsv": "# old\tnew\tutc\nrepoOld-1\trepoA-2\t2026-09-30T00:00:00Z\n",
    "lanes/archive/LANES-retired.md": "\n".join([
        "# retired rows (Amendment 19(d))", "",
        _row("repoZ-1", SID_Z1, f"RETIRED {DOT} 2026-09-02T00:00:00Z {DOT} retired"),
        ""]),
    "lanes/log/repoA-1.md": "\n".join([
        f"# lane repoA-1 {EM} object log (lane-collision-protocol Amendment 7)",
        f"STARTED {EM} lane repoA-1, session {SID_A1}@Eagle, 2026-10-01T00:00:00Z, "
        f"lane:repoA-1 {ARROW} home opensoft/repoA; dir /work/repoA1",
        ""]),
    "lanes/log/repoA-2.md": "\n".join([
        f"# lane repoA-2 {EM} object log (lane-collision-protocol Amendment 7)",
        f"STARTED {EM} lane repoA-2, session {SID_A2}@Eagle, 2026-10-01T02:00:00Z, "
        f"lane:repoA-2 {ARROW} home opensoft/repoA; dir /work/repoA2",
        ""]),
    "lanes/log/README.md": "# the object logs\n",
    "lanes/repos.tsv": "# alias\towner/repo\nrepoA\topensoft/repoA\n",
}

#: The one more row, and its log, three verbs need, or they refuse for want of
#: work (T241's `PREPS`; `lanes-edit.sh:13316-13352` at a2073eae):
#: `archive-rows <repo>` moves a repository's RETIRED rows; `retire-rows`
#: takes a dormant row; `migrate-state-cells` migrates a diary cell.
PREP_ROWS = {
    "archive-rows": ("repoZ-2", "eeeeeeee-0002-4000-8000-00000000e002",
                     f"RETIRED {DOT} 2026-09-03T00:00:00Z {DOT} retired",
                     f"RETIRED {EM} lane repoZ-2, session eeeeeeee-0002-4000-8000-00000000e002"
                     f"@Eagle, 2026-09-03T00:00:00Z, lane:repoZ-2 {EM} retired\n"),
    "retire-rows": ("repoA-4", "aaaaaaaa-0005-4000-8000-00000000a005",
                    f"MIGRATED {DOT} 2026-09-01T00:00:00Z {DOT} migrated", ""),
    "migrate-state-cells": ("repoA-5", "aaaaaaaa-0006-4000-8000-00000000a006",
                            f"parked 2026-09-01 {DOT} picked up 2026-09-02", ""),
}

#: S1's writes, the write guard's verbs: {verb: (its arguments, the lane it
#: writes as)}. The forms are `lanes-edit.sh`'s usage lines at a2073eae, T241's
#: for the thirteen it shares; `commit` publishes a hand edit of `LANES.md`
#: (`HAND_EDIT`), the one thing it commits (`:16940-16970`).
WRITER_VERBS = {
    "add-row": (["add-row", f"| `repoA-3` | harness `aaaaaaaa-0004-4000-8000-00000000a004` | "
                 f"Eagle / test / brett | 2026-11-10T00:00Z | none | handoffs/repoA-3.md | "
                 f"LIVE {DOT} 2026-11-10T00:00:00Z {DOT} test 3 |"], "repoA-2"),
    "append-line": (["append-line", f"HOLD {EM} lane repoA-2 ({WRITER_WS}), window w, "
                     f"2026-11-10T00:00:00Z: opensoft/repoB main {TIP} for test 3"], "repoA-2"),
    "append-session-id": (["append-session-id", "repoA-2", f"harness `{SID_A2}`",
                           " (test 3)"], "repoA-2"),
    "archive-rows": (["archive-rows", "repoZ", "--yes"], "repoA-2"),
    "claim": (["claim", "opensoft/repoA#9", "--no-github"], "repoA-2"),
    "commit": (["commit", "test 3's hand edit"], "repoA-2"),
    "log": (["log", "NOTED", "lane:repoA-2", "test 3's write"], "repoA-2"),
    "migrate-state-cells": (["migrate-state-cells", "--yes"], "repoA-2"),
    "release": (["release", "opensoft/repoA#7", "test 3", "--no-github"], "repoA-1"),
    "rename-lane": (["rename-lane", "repoA-2", "repoA-3", "test 3", "--no-github"], "repoA-2"),
    "replace-in-row": (["replace-in-row", "repoA-2", "parked", "parked for test 3"], "repoA-2"),
    "request-handoff": (["request-handoff", "repoA-1", "--force", "test 3", "--session",
                         SID_REQUESTER], "repoA-2"),
    "retire-rows": (["retire-rows", "repoA-4", "--reason", "test 3"], "repoA-2"),
    "set-row-state": (["set-row-state", "repoA-2", f"PAUSED {DOT} test 3"], "repoA-2"),
}

#: `commit`'s hand edit: repoA-2's row in `LANES.md`, left uncommitted.
HAND_EDIT = ("lanes/LANES.md", f"{DOT} parked |", f"{DOT} parked by hand |")


def _seed(verbs=()) -> dict:
    """`SEED`, with `PREP_ROWS`' row and log for each of `verbs` that has one,
    each after repoA-2's row."""
    files = dict(SEED)
    lanes = files["lanes/LANES.md"]
    anchor = next(line for line in lanes.split("\n") if line.startswith("| `repoA-2` |"))
    rows = []
    for verb in verbs:
        if verb in PREP_ROWS:
            lane, sid, cell, log = PREP_ROWS[verb]
            rows.append(_row(lane, sid, cell, started="2026-09-01T00:00Z"))
            files[f"lanes/log/{lane}.md"] = (
                f"# lane {lane} {EM} object log (lane-collision-protocol Amendment 7)\n" + log)
    files["lanes/LANES.md"] = lanes.replace(anchor + "\n", "\n".join([anchor] + rows) + "\n", 1)
    return files


def _sanitized_path() -> str:
    """The caller's `PATH` without any directory that holds a `lanes-index` or
    a `lane-start`: an installed lane tool is never what a case runs. The
    case's own `tmux` comes first."""
    return os.pathsep.join(
        part for part in os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep)
        if part and not any(os.path.exists(os.path.join(part, name))
                            for name in ("lanes-index", "lane-start")))


def _writer_estate(root: Path, verbs=(), configuration: str = "none") -> tuple:
    """A files-mode estate at C (`_seed(verbs)`) on a bare origin: the lane
    checkout, `workspace.yaml` naming it, a `tmux` that answers nothing, and no
    configuration or `mode=index` (`_configure`). Returns (the checkout, the
    origin, the environment)."""
    home, checkout, origin = root / "home", root / "checkout", root / "origin.git"
    for name in ("home/.agents", "state", "config", "t", "fakebin"):
        (root / name).mkdir(parents=True)
    env = guard_strip_env(os.environ, strip=("GIT_", "OPENREPOTOOLS_"))
    env.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, LC_ALL="C",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
               AGENT_PROTOCOL_ROOT=str(home / ".agents"), TMPDIR=str(root / "t"),
               XDG_STATE_HOME=str(root / "state"), XDG_CONFIG_HOME=str(root / "config"),
               CLAUDE_CONFIG_DIR=str(home / ".claude"), LANES_WORKSTATION=WRITER_WS,
               LANES_HOST="eagle", LANES_OS="linux", LANES_CONTAINER="none",
               LANES_IN_CONTAINER="0", LANES_NO_GITHUB="1", LANES_REPO=str(checkout),
               PATH=str(root / "fakebin") + os.pathsep + _sanitized_path())
    (root / "fakebin" / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (root / "fakebin" / "tmux").chmod(0o755)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True,
                   env=env)
    subprocess.run(["git", "clone", "-q", str(origin), str(checkout)], check=True, env=env,
                   capture_output=True)
    for rel, text in _seed(verbs).items():
        (checkout / rel).parent.mkdir(parents=True, exist_ok=True)
        (checkout / rel).write_bytes(text.encode("utf-8"))
    for argv in (["add", "-A"], ["commit", "-q", "-m", "C: the fixture register"],
                 ["push", "-q", "origin", "main"]):
        _git(checkout, env, *argv)
    (home / ".agents" / "workspace.yaml").write_text(
        f"repository: {origin}\npath: {checkout}\n", encoding="utf-8")
    _configure(root, env, configuration)
    return checkout, origin, env


def _hand_edit(checkout: Path, verb: str) -> None:
    """`commit`'s hand edit, left in the working tree; nothing for any other
    verb."""
    if verb == "commit":
        rel, old, new = HAND_EDIT
        text = (checkout / rel).read_text(encoding="utf-8")
        assert text.count(old) == 1, f"the hand edit's anchor is not once in {rel}"
        (checkout / rel).write_text(text.replace(old, new), encoding="utf-8")


def _write(edit: Path, argv: list, lane: str, env: dict, cwd: Path,
           **extra) -> subprocess.CompletedProcess:
    """One run of `<edit> <argv>` as `lane`."""
    return subprocess.run(["bash", str(edit), *argv], capture_output=True, encoding="utf-8",
                          errors="replace", env=dict(env, LANES_LANE=lane, **extra),
                          cwd=str(cwd), timeout=120, check=False, stdin=subprocess.DEVNULL,
                          start_new_session=True)


def _git_state(checkout: Path, origin: Path, env: dict) -> dict:
    """AT-3's oracle of what a refusal leaves unchanged: the clone's HEAD,
    index, working tree and files under `lanes/`, and origin's refs."""
    index = checkout / ".git" / "index"
    lanes = checkout / "lanes"
    return {
        "HEAD": _git(checkout, env, "rev-parse", "HEAD"),
        "index": hashlib.sha256(index.read_bytes()).hexdigest() if index.exists() else "-",
        "status": _git(checkout, env, "status", "--porcelain=v1", "-uall"),
        "lanes/": {p.relative_to(lanes).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(lanes.rglob("*")) if p.is_file()},
        "origin": _git(origin, env, "for-each-ref", "--format=%(refname) %(objectname)"),
    }


def _queued(checkout: Path, env: dict) -> str:
    """The local commits the publish act would push: those `origin/main`, as
    last fetched, lacks."""
    return _git(checkout, env, "log", "--oneline", "refs/remotes/origin/main..HEAD")


def _said(proc: subprocess.CompletedProcess) -> str:
    return f"\n--- stdout\n{proc.stdout[-700:]}\n--- stderr\n{proc.stderr[-1500:]}"


def _assert_wrote_nothing(before: dict, checkout: Path, origin: Path, env: dict,
                          where: str) -> None:
    after = _git_state(checkout, origin, env)
    changed = sorted(k for k in before if before[k] != after[k])
    assert not changed, f"{where}: the refusal changed {changed}: {before} -> {after}"
    queued = _queued(checkout, env)
    assert not queued, f"{where}: a commit is queued for the publish act: {queued}"


def _assert_refused_under_the_marker(root: Path, verb: str, configuration: str) -> None:
    """AT-3's oracle for one verb in one configuration: origin's `main` carries
    the marker, the clone is one commit behind, and the verb's own fetch
    brings it; the writer exits 69 with Amendment 22's text and writes
    nothing."""
    checkout, origin, env = _writer_estate(root, [verb], configuration)
    _push_marker(root, origin, env)
    _hand_edit(checkout, verb)
    argv, lane = WRITER_VERBS[verb]
    before = _git_state(checkout, origin, env)
    proc = _write(EDIT, argv, lane, env, checkout)
    where = f"lanes-edit.sh {verb}, configuration {configuration}, under the marker"
    assert proc.returncode == 69, \
        f"{where}: exited {proc.returncode}, not 69 (T419's marker check){_said(proc)}"
    assert AMENDMENT_22 in proc.stderr, f"{where}: no Amendment 22 text on stderr{_said(proc)}"
    _assert_wrote_nothing(before, checkout, origin, env, where)


@pytest.mark.parametrize("verb", list(WRITER_VERBS))
def test_a_files_mode_writer_refuses_under_the_marker(tmp_path, verb):
    """AT-3 (FR-004): with no configuration, each of S1's verbs whose own
    fetch brings `lanes/STORE` exits 69 with Amendment 22's text; the clone's
    HEAD, index, working tree and `lanes/`, and origin's refs, are unchanged,
    and no commit is queued for the publish act. Fails until T419 (L4-B12)."""
    _assert_refused_under_the_marker(tmp_path, verb, "none")


@pytest.mark.parametrize("verb", list(WRITER_VERBS))
def test_a_mode_index_writer_refuses_under_the_marker(tmp_path, verb):
    """AT-3 (Q20(B)): the same on a `mode=index` workstation, every
    workstation act 3 configured, which T409's ask answers `index`. Fails
    until T409 (L4-B1) and T419 (L4-B12)."""
    _assert_refused_under_the_marker(tmp_path, verb, "index")


def test_a_writer_with_no_fetch_refuses_when_its_tip_carries_the_marker(tmp_path):
    """AT-3: a second clone, made at the marker's commit, run with
    `LANES_NO_FETCH=1`: `log NOTED` still exits 69 with Amendment 22's text and
    writes nothing, with no configuration and with `mode=index` (T419: under
    `LANES_NO_FETCH=1` the check tests the tip as last fetched). Fails until
    T419 (L4-B12)."""
    argv, lane = WRITER_VERBS["log"]
    for configuration in CONFIGURATIONS:
        root = tmp_path / configuration
        first, origin, env = _writer_estate(root, configuration=configuration)
        marker = _push_marker(root, origin, env)
        second = root / "second"
        subprocess.run(["git", "clone", "-q", str(origin), str(second)], check=True, env=env,
                       capture_output=True)
        assert _git(second, env, "rev-parse", "HEAD") == marker
        assert (second / "lanes" / "STORE").is_file()
        (root / "home" / ".agents" / "workspace.yaml").write_text(
            f"repository: {origin}\npath: {second}\n", encoding="utf-8")
        env = dict(env, LANES_REPO=str(second), LANES_NO_FETCH="1")
        before = _git_state(second, origin, env)
        proc = _write(EDIT, argv, lane, env, second)
        where = f"log NOTED with LANES_NO_FETCH=1, configuration {configuration}"
        assert proc.returncode == 69, \
            f"{where}: exited {proc.returncode} with the marker in its tip{_said(proc)}"
        assert AMENDMENT_22 in proc.stderr, f"{where}: no Amendment 22 text{_said(proc)}"
        _assert_wrote_nothing(before, second, origin, env, where)


# --- AT-F8: every failure of the mode query ----------------------------------

#: Q6(c)'s text, as lane 1's T105 spells it (`MODE_PRIMARY_REFUSED_TEXT`;
#: design Y:4872), which the stand-in's 78 carries.
Q6C_TEXT = ("mode=primary is not available in this build: the renderer's git half is not "
            "installed, so a write could not be mirrored; nothing was written")
#: The query's client timer, D9's row for the mode query, and the bound a test
#: asserts, twice it (section 4's rule 2).
MODE_TIMER_S = 2.0
MODE_BOUND_S = 2 * MODE_TIMER_S
MODES = ("index", "primary")
ESTATES = ("files", "sql")

#: The stand-in's answers to `mode`: each row of lane 4's table ("The mode
#: query's failures") but 78, which `Q6C` answers. `exit` is the code, `signal`
#: a death by that signal, `sleep` a hang past the client timer, `stdout` and
#: `stderr` what it prints first.
MODE_FAILURES = {
    "refused-2": {"exit": 2, "stderr": "lanes-index: lanes-index.conf: line 1: the "
                                       "configuration is refused\n"},
    "too-old-64": {"exit": 64, "stderr": "lanes-index: unknown subcommand 'mode'\n"},
    "crash-1": {"exit": 1, "stderr": "Traceback (most recent call last):\n  RuntimeError\n"},
    "removed-127": {"exit": 127, "stderr": "lanes-index: python3: No such file or directory\n"},
    "signal": {"signal": "TERM"},
    "not-one-line": {"exit": 0, "stdout": "index\nprimary\n"},
    "exit-69": {"exit": 69, "stderr": "lanes-index: unavailable\n"},
    "exit-75": {"exit": 75, "stderr": "lanes-index: busy\n"},
    "exit-3": {"exit": 3, "stderr": "lanes-index: in doubt\n"},
    "hang": {"sleep": 60, "stdout": "index\n"},
}
Q6C = {"exit": 78, "stderr": f"lanes-index: {Q6C_TEXT}\n"}

#: THE STAND-IN at `lanes-index`'s path: it logs every call (its argv, its pid,
#: its start, and `LANES_INDEX` as it found it), answers `mode` as
#: `lanes-index.answer` beside it says, and every other call with 0. Where it
#: hangs, a SIGTERM is logged with its time before it ends.
_MODE_STANDIN = r'''#!/usr/bin/env python3
# A STAND-IN lanes-index (feature 007, T242; AT-F8): it logs every call, one
# JSON object per line, and answers `mode` as lanes-index.answer says.
import json, os, signal, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "lanes-index.calls")
ARGS = sys.argv[1:]


def log(record):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


log({"argv": ARGS, "pid": os.getpid(), "start": time.time(),
     "lanes_index": os.environ.get("LANES_INDEX")})
if ARGS != ["mode"]:
    sys.exit(0)
with open(os.path.join(HERE, "lanes-index.answer"), encoding="utf-8") as handle:
    ANSWER = json.load(handle)
if ANSWER.get("sleep"):
    def ended(signum, frame):
        log({"argv": ARGS, "pid": os.getpid(), "ended": time.time(), "signal": signum})
        os._exit(128 + signum)
    signal.signal(signal.SIGTERM, ended)
    time.sleep(ANSWER["sleep"])
sys.stdout.write(ANSWER.get("stdout", ""))
sys.stderr.write(ANSWER.get("stderr", ""))
sys.stdout.flush()
sys.stderr.flush()
if ANSWER.get("signal"):
    os.kill(os.getpid(), getattr(signal, "SIG" + ANSWER["signal"]))
sys.exit(ANSWER.get("exit", 0))
'''

#: One warning that the mode query failed and the write runs in files mode
#: (D3). No contract fixes its words, so this counts only a warning line of
#: `lanes-edit.sh`'s that names the query: one that starts
#: `lanes-edit: WARNING:` and names `lanes-index mode`. A line naming the
#: mode and files mode alone also matched T419's refusal note on a SQL
#: estate, "This workstation writes in files mode, so `log` refuses"
#: (`lanes-edit.sh:2771` at `refs/l1/V-round5`), and counted 2 for AT-F8's
#: `[*-sql]` ids (AN13b's cause 1; line AF13b).
MODE_WARNING = re.compile(r"^lanes-edit: WARNING: .*\blanes-index mode\b")
TIMEOUT_WORDS = re.compile(r"tim(e|ed)[ -]?out|timer|\b2 ?s\b|seconds?\b", re.I)


class _ModeBench:
    """AT-F8's fixture: `_writer_estate`'s files-mode estate with a
    `mode=<mode>` configuration, `lanes/STORE` on origin for the `sql` estate
    (the clone one commit behind it), and a copy of `lanes-edit.sh` with
    `repos.tsv`, `lane-start` and the stand-in beside it."""

    def __init__(self, root: Path, mode: str, estate: str, answer: dict, verbs=()):
        self.checkout, self.origin, self.env = _writer_estate(root, verbs)
        conf = Path(self.env["XDG_CONFIG_HOME"]) / "openRepoTools" / "lanes-index.conf"
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text(f"mode={mode}\n", encoding="utf-8")
        conf.chmod(0o600)
        self.bin = root / "bin"
        self.bin.mkdir()
        for name in ("lanes-edit.sh", "repos.tsv", "lane-start"):
            shutil.copy2(REPO / name, self.bin / name)
        self.edit = self.bin / "lanes-edit.sh"
        (self.bin / "lanes-index").write_text(_MODE_STANDIN, encoding="utf-8")
        (self.bin / "lanes-index").chmod(0o755)
        (self.bin / "lanes-index.answer").write_text(json.dumps(answer), encoding="utf-8")
        self.log = self.bin / "lanes-index.calls"
        if estate == "sql":
            _push_marker(root, self.origin, self.env)

    def calls(self) -> list:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()
                if line]

    def write(self, verb: str, index_off: bool, text: str = None) -> tuple:
        """Runs `verb`, with `LANES_INDEX=off` where `index_off`. Returns (the
        run, its `mode` calls, its wall time)."""
        argv, lane = WRITER_VERBS[verb]
        if text is not None:
            argv = argv[:-1] + [text]
        seen = len(self.calls())
        extra = {"LANES_INDEX": "off"} if index_off else {}
        started = time.monotonic()
        proc = _write(self.edit, argv, lane, self.env, self.checkout, **extra)
        wall = time.monotonic() - started
        asked = [c for c in self.calls()[seen:] if c["argv"] == ["mode"] and "start" in c]
        return proc, asked, wall

    def state(self) -> dict:
        return _git_state(self.checkout, self.origin, self.env)


def _where(verb: str, mode: str, estate: str, index_off: bool) -> str:
    return (f"lanes-edit.sh {verb} on mode={mode}, {estate} estate, "
            f"LANES_INDEX {'off' if index_off else 'unset'}")


def _assert_asked_once(asked: list, where: str, proc: subprocess.CompletedProcess) -> None:
    """T409: the writer asks `lanes-index mode` once, where a configuration
    exists, and `LANES_INDEX=off` never skips the ask (lane 4's row 25)."""
    assert len(asked) == 1, \
        f"{where}: the stand-in was asked `mode` {len(asked)} times, not once (T409's ask)" \
        f"{_said(proc)}"


def test_the_q6c_refusal_has_its_own_code_and_the_writer_exits_69(tmp_path):
    """AT-F8: the stand-in answers `mode` with Q6(c)'s 78 and its text. On
    `mode=index` and `mode=primary`, on a files estate and a SQL estate, with
    `LANES_INDEX` unset and `off`, `log NOTED` asks once, exits 69, its stderr
    repeats the text, and nothing is written. Then AT-14's refusing line for
    the writer (T14C's SHOULD-2: this case holds it): each of S1's verbs, on
    `mode=primary` and a files estate, exits 69 repeating the text, with the
    files, HEAD and origin unchanged. Fails until T409 (L4-B1)."""
    for estate in ESTATES:
        for mode in MODES:
            bench = _ModeBench(tmp_path / f"{mode}-{estate}", mode, estate, Q6C)
            for index_off in (False, True):
                where = _where("log NOTED", mode, estate, index_off)
                before = bench.state()
                proc, asked, _wall = bench.write("log", index_off)
                _assert_asked_once(asked, where, proc)
                assert proc.returncode == 69, \
                    f"{where}: Q6(c)'s 78 gave {proc.returncode}, not 69{_said(proc)}"
                assert Q6C_TEXT in proc.stderr, f"{where}: stderr lacks Q6(c)'s text{_said(proc)}"
                _assert_wrote_nothing(before, bench.checkout, bench.origin, bench.env, where)
    verbs = [v for v in WRITER_VERBS if v != "commit"] + ["commit"]
    bench = _ModeBench(tmp_path / "verbs", "primary", "files", Q6C, verbs)
    for verb in verbs:
        _hand_edit(bench.checkout, verb)
        where = _where(verb, "primary", "files", False)
        before = bench.state()
        proc, asked, _wall = bench.write(verb, False)
        _assert_asked_once(asked, where, proc)
        assert proc.returncode == 69, \
            f"{where}: Q6(c)'s 78 gave {proc.returncode}, not 69{_said(proc)}"
        assert Q6C_TEXT in proc.stderr, f"{where}: stderr lacks Q6(c)'s text{_said(proc)}"
        _assert_wrote_nothing(before, bench.checkout, bench.origin, bench.env, where)


def _process_alive(pid: int, program: Path) -> bool:
    """Whether `pid` is still the stand-in: a pid reused by another program,
    or a reaped one, is not."""
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False
    return str(program).encode() in cmdline


def _record(where: str, elapsed: float) -> None:
    """Timing rule 2's record: the query's measured end beside D9's 2 s timer,
    and its margin to the bound."""
    print(f"AT-F8 {where}: the mode query ended {elapsed:.2f} s after it started, against "
          f"D9's {MODE_TIMER_S:g} s timer (bound {MODE_BOUND_S:g} s); "
          f"margin {MODE_BOUND_S - elapsed:+.2f} s")


@pytest.mark.parametrize(("failure", "mode", "estate"), [
    pytest.param(failure, mode, estate, id=f"{failure}-{mode}-{estate}")
    for failure in MODE_FAILURES for mode in MODES for estate in ESTATES])
def test_any_other_mode_query_failure_runs_files_mode_with_a_warning(tmp_path, failure, mode,
                                                                     estate):
    """AT-F8: each failure of the mode query but 78 (lane 4's table), on
    `mode=<mode>` and a `<estate>` estate, with `LANES_INDEX` unset and then
    `off`: `log NOTED` asks once and prints one warning on stderr, then runs in
    files mode. On a files estate the write exits 0 and lands on origin; on a
    SQL estate the marker check after S3's fetch refuses it, 69 with Amendment
    22's text, and nothing is written. The hang: the query's 2 s client timer
    ends the stand-in, which is gone once the verb returns; the query ends
    under 4 s, recorded with its margin, and the warning names the timeout.
    Fails until T409 (L4-B1), and on a SQL estate T419 (L4-B12)."""
    bench = _ModeBench(tmp_path, mode, estate, MODE_FAILURES[failure])
    for index_off in (False, True):
        where = _where("log NOTED", mode, estate, index_off) + f", the query's {failure}"
        text = f"test 3's AT-F8 write, {failure}, LANES_INDEX {'off' if index_off else 'unset'}"
        before = bench.state()
        proc, asked, wall = bench.write("log", index_off, text)
        _assert_asked_once(asked, where, proc)
        warnings = [line for line in proc.stderr.splitlines() if MODE_WARNING.search(line)]
        assert len(warnings) == 1, \
            f"{where}: {len(warnings)} warnings that the write runs in files mode, not one" \
            f"{_said(proc)}"
        if failure == "hang":
            call = asked[0]
            ended = [c["ended"] for c in bench.calls()
                     if c.get("pid") == call["pid"] and "ended" in c]
            elapsed = (ended[0] if ended else call["start"] + wall) - call["start"]
            _record(where, elapsed)
            assert not _process_alive(call["pid"], bench.bin / "lanes-index"), \
                f"{where}: the hanging stand-in (pid {call['pid']}) outlived the verb"
            assert elapsed < MODE_BOUND_S, \
                f"{where}: the query ended {elapsed:.2f} s after it started, not under " \
                f"{MODE_BOUND_S:g} s"
            assert TIMEOUT_WORDS.search(warnings[0]), \
                f"{where}: the warning does not name the timeout: {warnings[0]!r}"
        if estate == "files":
            assert proc.returncode == 0, \
                f"{where}: the files-mode write exited {proc.returncode}, not 0{_said(proc)}"
            landed = _git(bench.origin, bench.env, "show", "main:lanes/log/repoA-2.md")
            assert text in landed, f"{where}: the write did not land on origin{_said(proc)}"
        else:
            assert proc.returncode == 69, \
                f"{where}: exited {proc.returncode}, not 69 (the marker check after the " \
                f"files-mode fallback){_said(proc)}"
            assert AMENDMENT_22 in proc.stderr, \
                f"{where}: no Amendment 22 text on stderr{_said(proc)}"
            _assert_wrote_nothing(before, bench.checkout, bench.origin, bench.env, where)
