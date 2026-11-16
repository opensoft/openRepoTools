# SPDX-License-Identifier: Apache-2.0
"""Feature 007's register shape (opensoft/openRepoTools#165): what each register
call looks like from outside, its argv, its credentials and its text.

THIS MODULE TODAY holds test 2's FP case, lane 2's T241 (AT-2, the test plan's
lines 646-781; FR-018, FR-059):
`test_an_unreachable_store_is_69_naming_the_store_and_never_the_files[<verb>]`.
Lane 1's T106 and T111 select their own cases here by `sql_register_shape`
and their words (B10 tasks:275 and :399); those cases are other tasks', which
add them to this module.

THE CASE runs each of S1's writes but `commit` as `lanes-edit.sh <verb>` on a
`mode=primary` workstation (`test_sql_register_writes.py`'s
`PrimaryWorkstation` and `WRITE_VERBS`), with T203's register fake first on
`PATH` answering every call that carries a request with `psql`'s exit 2 and
its "connection to server ... failed" text (AT-2, "Unreachable (FP)"). It
needs no engine, and fails until lane 4's L4-B3 (T415's attempt loop) lands,
by its own assertion: today's `lanes-edit.sh` writes the files whatever
`mode=` says.
"""

from __future__ import annotations

import re
import shutil

import pytest

from conftest import WINDOWS_SKIP
from test_sql_register_render import fake_calls, fake_psql_dir
from test_sql_register_writes import (PREPS, SECRET, WRITE_VERBS, PrimaryWorkstation,
                                      unreachable_answers)

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the lane tooling is bash over git")]

#: THE LANDING GATE'S TABLE (T280; `tests/sql_register_gate.py` reads it, and
#: T281 removes it in the last set): every id of this module waits for the
#: tasks T241's Order names, L4-B3's, L4-B4's and L4-B11's (tasks.md at
#: 204145ae). Lane 2's plan GP-24 wrote it (task sets 12b's rule 11).
SQL_REGISTER_GATE_TABLE = {
    "*": ("T413", "T414", "T415", "T420"),  # every id: the tasks all its rows share
}

#: What a writer that fell back to the files, or offered to, would say: the
#: register's file paths as a target, or the files mode by name. None may
#: appear in a refusal on primary (P213-215: "nothing ever written to the
#: files instead").
FILES_WORDS = re.compile(r"lanes/LANES\.md|lanes/log/|mode=files|files mode|files-mode"
                         r"|fall(ing)? ?back", re.I)


@pytest.mark.parametrize("verb", list(WRITE_VERBS))
def test_an_unreachable_store_is_69_naming_the_store_and_never_the_files(tmp_path, verb):
    """AT-2's FP oracle for the refusal's text (P213-214; contract section
    2.6): `lanes-edit.sh <verb>` on primary, with the database unreachable,
    exits 69; stderr names the store, `psql`'s own first line with the socket
    it tried, and the error, with no password, no `PGPASSWORD` and no URL;
    it never names the files as a target or a fallback; no call follows the
    failed one; and the files under `lanes/` are as they were."""
    ws = PrimaryWorkstation(tmp_path, prep=PREPS.get(verb))
    fake = fake_psql_dir(ws.fakebin, answers=unreachable_answers(ws.dead))
    ws.env.update(fake)
    argv, lane = WRITE_VERBS[verb]
    lanes_before = ws.git_state()[1]
    proc = ws.run(argv, lane)
    said = proc.stdout + proc.stderr
    assert proc.returncode == 69, (
        f"lanes-edit.sh {verb} on primary exited {proc.returncode}, not 69, with the store "
        f"unreachable (L4-B3, T415's attempt loop): {proc.stderr[-800:]}")
    assert str(ws.dead) in proc.stderr and "connection to server" in proc.stderr, (
        f"stderr does not name the store and the error: {proc.stderr!r}")
    assert SECRET not in said and "PGPASSWORD" not in said, "a credential reached the output"
    assert not re.search(r"postgres(ql)?://", said), f"a URL reached the output: {said!r}"
    assert not FILES_WORDS.search(proc.stderr), (
        f"the refusal names the files: {FILES_WORDS.search(proc.stderr).group(0)!r} in "
        f"{proc.stderr!r}")
    assert len(fake_calls(fake)) == 1, f"calls after the failed one: {fake_calls(fake)}"
    assert ws.git_state()[1] == lanes_before, "a file under lanes/ changed"
