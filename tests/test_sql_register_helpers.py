# SPDX-License-Identifier: Apache-2.0
"""Feature 007's own test of T203c's `guard_session`, in
`tests/sql_register_helpers.py` (L2-0d; opensoft/openRepoTools#165).

T203's and T207's helpers are checked by their tasks' `verify:` lines; the
guard's session helper is checked here, against today's `lanes-edit.sh
guard`, because its whole job is what that guard does with it: with it, the
guard gets past its session-record check (`transcript_holders`, clause (d))
to its next step, the register's text; without it, the guard stops at that
check with 2 (lane 5, #165 6755266457; F10's items 27 and 28).

The estate is T215's and T220's (`test_sql_register_outage.py`,
`test_sql_register_bounds.py`): a bare origin, the lane's checkout under
`$HOME/projects` with `lanes/LANES.md` pushed, `$HOME/.agents/workspace.yaml`
naming it, and the compact hook JSON, in files mode (no configuration), so
nothing here waits for another lane's code. Three registers tell the step the
guard reached: an empty one (the guard refuses at the register's text), one
whose row names the session (it lets the prompt through, 0) and one whose row
names another session (it refuses on the row).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from sql_register_helpers import GUARD_WINDOW, guard_session, guard_strip_env

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

GUARD = REPO / "lanes-edit.sh"
#: The guard's refusal at its session-record check (`lanes-edit.sh:11010` at
#: `a2073eae`), and at its next step, the register's text (`:11050`).
NO_RECORD = "no live session record in THIS window"
NO_TEXT = "the register's TEXT could not be read"
DOT = chr(0xB7)
REGISTER_HEADER = ["# LANES.md", "",
                   "| lane | session id | workstation / env / user | started (UTC) | objects "
                   "owned | handoff path | state |",
                   "|---|---|---|---|---|---|---|"]


def _register(session_cell: str) -> str:
    """A register whose one row binds `GUARD_WINDOW` to `session_cell`, in
    T215's row form."""
    row = (f"| `{GUARD_WINDOW}` | harness `{session_cell}` | Eagle / test / brett "
           f"| 2026-10-01T00:00Z | none | handoffs/{GUARD_WINDOW}.md "
           f"| LIVE {DOT} 2026-10-01T02:00:00Z {DOT} working |")
    return "\n".join(REGISTER_HEADER + [row, ""])


def _estate(root: Path, register: str) -> tuple:
    """T215's and T220's estate, with `register` as `lanes/LANES.md`. Returns
    (`home`, the checkout, the `bin` directory, the guard's base
    environment)."""
    home = root / "home"
    wip = home / "projects" / "wip"
    origin = root / "origin.git"
    wip.parent.mkdir(parents=True)
    (root / "t").mkdir()
    env = guard_strip_env(os.environ)
    env.update(HOME=str(home), XDG_STATE_HOME=str(root / "state"),
               XDG_CONFIG_HOME=str(root / "config"), TMPDIR=str(root / "t"),
               LANES_WORKSTATION="Eagle", LANES_NO_GITHUB="1", LANES_NO_FETCH="1",
               LANES_REPO=str(wip), LANES_LANE=GUARD_WINDOW,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True,
                   env=env)
    subprocess.run(["git", "clone", "-q", str(origin), str(wip)], check=True, env=env,
                   capture_output=True)
    (wip / "lanes" / "log").mkdir(parents=True)
    (wip / "lanes" / "LANES.md").write_text(register, encoding="utf-8")
    (wip / "lanes" / "log" / "README.md").write_text("logs.\n", encoding="utf-8")
    for argv in (["add", "-A"], ["commit", "-q", "-m", "C"], ["push", "-q", "origin", "main"]):
        subprocess.run(["git", *argv], cwd=str(wip), check=True, env=env, capture_output=True)
    (home / ".agents").mkdir()
    (home / ".agents" / "workspace.yaml").write_text(
        f"repository: {origin}\npath: {wip}\n", encoding="utf-8")
    return home, wip, root / "bin", env


def _guard(session, env: dict, **extra) -> tuple:
    """`lanes-edit.sh guard` at the base, the session's hook JSON on stdin.
    Returns (its exit, its stdout and stderr)."""
    proc = subprocess.run(["bash", str(GUARD), "guard"], input=session.hook_input(),
                          capture_output=True, text=True, cwd=str(session.cwd),
                          env=session.env(env, **extra), timeout=60, start_new_session=True)
    return proc.returncode, proc.stdout + proc.stderr


@pytest.mark.parametrize("register", ["empty-register", "row-names-the-session",
                                      "row-names-another-session"])
def test_guard_session_takes_the_guard_past_its_session_record_check(tmp_path, register):
    """T203c: with `guard_session`'s record, the guard gets past its
    session-record check to its next step, the register's text: it refuses
    there for an empty register, lets the prompt through where the row names
    the session, and refuses on the row where it names another. With the same
    estate and stand-in but no record, or after `close()`, it stops at the
    session-record check with 2."""
    sid, other = str(uuid.uuid4()), str(uuid.uuid4())
    text = {"empty-register": "", "row-names-the-session": _register(sid),
            "row-names-another-session": _register(other)}[register]
    home, wip, bin_dir, env = _estate(tmp_path, text)
    session = guard_session(home, bin_dir, wip, session_id=sid)
    try:
        record = json.loads(session.record.read_text(encoding="utf-8"))
        assert session.record == home / ".claude" / "sessions" / f"{session.pid}.json"
        assert (session.record.stat().st_mode & 0o777) == 0o600
        assert record["sessionId"] == sid and record["pid"] == session.pid, record
        assert record["tmux"] == "testsess:@1.%1" and record["kind"] == "interactive", record

        aside = session.record.with_name(session.record.name + ".aside")
        session.record.rename(aside)
        code, out = _guard(session, env)
        assert code == 2 and NO_RECORD in out, f"without the record: {code}\n{out[-600:]}"
        aside.rename(session.record)

        code, out = _guard(session, env)
        assert NO_RECORD not in out, f"with the record: {code}\n{out[-600:]}"
        if register == "empty-register":
            assert code == 2 and NO_TEXT in out, f"{register}: {code}\n{out[-600:]}"
        elif register == "row-names-the-session":
            assert code == 0, f"{register}: {code}\n{out[-600:]}"
        else:
            assert code == 2 and f"does not name {sid} at all" in out, \
                f"{register}: {code}\n{out[-600:]}"
        calls = session.tmux_calls()
        for query in (["display-message", "-p", "#{session_name}:#{window_id}"],
                      ["display-message", "-p", "#{pane_pid}"],
                      ["display-message", "-p", "#W"],
                      ["display-message", "-p", "-t", "@1", "#{session_name}"]):
            assert query in calls, f"the stand-in was not asked {query}: {calls}"
    finally:
        session.close()
    assert session.holder.poll() is not None, "close() left the session's process alive"
    code, out = _guard(session, env)
    assert code == 2 and NO_RECORD in out, f"after close(): {code}\n{out[-600:]}"


def test_guard_session_refuses_a_checkout_outside_home_projects_and_strips_projects_root(
        tmp_path):
    """T203c: `guard_session` refuses a checkout outside `<home>/projects`,
    where the guard's scope test returns 0 before any read (T220c);
    `guard_strip_env` drops `PROJECTS_ROOT` (F10's item 28) with the other
    prefixes and a module's own; and an exported `PROJECTS_ROOT` naming
    another root does make today's guard return 0 with nothing said, before
    its session-record check."""
    with pytest.raises(ValueError, match="is not under"):
        guard_session(tmp_path / "home", tmp_path / "bin", tmp_path / "wip")
    with pytest.raises(ValueError, match="not in lower case"):
        guard_session(tmp_path / "home", tmp_path / "bin", tmp_path / "home" / "projects" / "w",
                      session_id=str(uuid.uuid4()).upper())
    kept = guard_strip_env({"PROJECTS_ROOT": "/x", "AGENT_PROTOCOL_ROOT": "/y", "TMUX": "z",
                            "TMUX_PANE": "%9", "LANES_REPO": "r", "CLAUDE_CODE_SESSION_ID": "s",
                            "PGHOST": "h", "FAKE_PSQL_LOG": "l", "T215_X": "1", "KEEP": "1"},
                           strip=("T215_",))
    assert kept == {"KEEP": "1"}, kept

    home, wip, bin_dir, env = _estate(tmp_path / "e", "")
    with guard_session(home, bin_dir, wip) as session:
        code, out = _guard(session, env, PROJECTS_ROOT=str(tmp_path / "elsewhere"))
        assert code == 0 and out == "", f"PROJECTS_ROOT elsewhere: {code}\n{out[-600:]}"
        code, out = _guard(session, env)
        assert code == 2 and NO_TEXT in out, f"stripped: {code}\n{out[-600:]}"
