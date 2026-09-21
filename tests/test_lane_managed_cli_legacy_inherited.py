# SPDX-License-Identifier: Apache-2.0
"""Real-process coverage for inherited legacy pending-launch binding.

The inherited path is tested with three real Python processes: the durable
pending creator/launcher (C), its direct ``lane-start`` shell successor (S),
and the executing ``lane-managed`` helper (H). A mocked process-identity seam
would prove only that a caller can manufacture the lineage, which is exactly
what this contract refuses to trust.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]


_PROCESS_TREE = r'''
import contextlib
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[2])
OWNER = Path(sys.argv[3])
RESULT = Path(sys.argv[4])
VARIANT = sys.argv[5]
REQUEST_VARIANT = sys.argv[6]


def api():
    return runpy.run_path(str(REPO / "lane-managed"), run_name="legacy_bind_child")


def token(pid):
    return api()["_process_identity"](pid)[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def spawn(mode, *extra):
    return subprocess.Popen(
        [sys.executable, __file__, mode, str(REPO), str(OWNER), str(RESULT),
         VARIANT, REQUEST_VARIANT, *extra],
        close_fds=True,
    )


def run_helper():
    namespace = api()
    owner = json.loads(OWNER.read_text(encoding="utf-8"))
    state_calls = []
    lock_active = [False]
    real_identity = namespace["_process_identity"]
    race_calls = {}

    class Store:
        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            lock_active[0] = True
            try:
                yield self
            finally:
                lock_active[0] = False

        def read_owner(self):
            return json.loads(OWNER.read_text(encoding="utf-8"))

        def bind_pending_launch(self, *, lease_id, pid, start_token, pgid):
            assert lock_active[0]
            state_calls.append({
                "lease_id": lease_id,
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            })
            write_json(RESULT.with_suffix(".mutation"), state_calls)
            return {
                "mode": "legacy-lease",
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
                "lane": owner.get("lane", "build"),
            }

    def race_identity(pid):
        value = real_identity(pid)
        if pid == os.getppid():
            race_calls[pid] = race_calls.get(pid, 0) + 1
            if race_calls[pid] >= 2:
                return {"pid": pid, "alive": False}
        return value

    body = {
        "lease_id": owner.get("lease_id", "lease-inherited"),
        "pid": owner.get("requested_pid", owner["pid"]),
        "bind_purpose": "no-launch" if VARIANT == "normal" else "inherited-parent-launcher",
    }
    if REQUEST_VARIANT == "wrong-lease":
        body["lease_id"] = "lease-wrong"
    request_id = owner.get("request_id", "request-inherited")
    lane = owner.get("lane", "build")
    if REQUEST_VARIANT == "wrong-request":
        request_id = "request-wrong"
    if REQUEST_VARIANT == "wrong-lane":
        lane = "other-lane"
    identity = race_identity if REQUEST_VARIANT == "race" else None
    request = {
        "schema": 2,
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "request_id": request_id,
        "lane": lane,
        "generation": 7,
        "operation": "pending-launch-bind",
        "body": body,
    }
    try:
        response = namespace["durable_ownership_handler"](
            request, state_store=Store(), process_identity=identity,
        )
    except namespace["ManagedCLIError"] as error:
        response = {"ok": False, "code": error.code}
    except BaseException as error:
        response = {"ok": False, "code": "child-error", "error": repr(error)}
    response["state_calls"] = len(state_calls)
    write_json(RESULT, response)


def run_shell():
    if VARIANT == "inherited-normal":
        for _ in range(400):
            try:
                requested = json.loads(OWNER.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                requested = {}
            if "requested_pid" in requested:
                break
            import time
            time.sleep(0.005)
    child = spawn("capture") if VARIANT == "capture" else spawn("helper")
    child.wait(timeout=8)


def run_capture():
    child = spawn("helper")
    child.wait(timeout=8)


def run_grandchild():
    child = spawn("grandchild-shell")
    child.wait(timeout=8)


def run_foreign_parent():
    child = spawn("foreign-shell")
    child.wait(timeout=8)


def run_creator():
    creator_pid = os.getpid()
    owner = {
        "mode": "pending-launch",
        "lease_id": "lease-inherited",
        "request_id": "request-inherited",
        "lane": "build",
        "pid": creator_pid,
        "start_token": token(creator_pid),
    }
    if VARIANT == "changed-token":
        owner["start_token"] = "not-the-live-creator"
    if VARIANT == "normal":
        owner["requested_pid"] = os.getppid()
    write_json(OWNER, owner)
    if VARIANT == "dead":
        return
    if VARIANT == "normal":
        child = spawn("helper")
    elif VARIANT == "foreign":
        child = spawn("foreign-parent")
    elif REQUEST_VARIANT == "sibling":
        sibling = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(8)"])
        owner["requested_pid"] = sibling.pid
        write_json(OWNER, owner)
        child = spawn("shell", str(sibling.pid))
    elif VARIANT == "grandchild":
        child = spawn("grandchild")
    else:
        child = spawn("shell")
        if VARIANT == "inherited-normal":
            owner["requested_pid"] = child.pid
            write_json(OWNER, owner)
    try:
        child.wait(timeout=10)
    finally:
        if REQUEST_VARIANT == "sibling":
            try:
                sibling.terminate()
            except ProcessLookupError:
                pass


mode = sys.argv[1]
if mode == "creator":
    run_creator()
elif mode == "normal-shell":
    child = spawn("creator")
    child.wait(timeout=10)
elif mode == "shell":
    run_shell()
elif mode == "capture":
    run_capture()
elif mode == "grandchild":
    run_grandchild()
elif mode == "grandchild-shell":
    run_shell()
elif mode == "foreign-parent":
    run_foreign_parent()
elif mode == "foreign-shell":
    run_shell()
elif mode == "helper":
    run_helper()
'''


def _write_tree_script(tmp_path: Path) -> Path:
    script = tmp_path / "legacy-bind-process-tree.py"
    script.write_text(textwrap.dedent(_PROCESS_TREE), encoding="utf-8")
    script.chmod(0o700)
    return script


def _run_tree(tmp_path: Path, *, variant="valid", request_variant="valid") -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    script = _write_tree_script(tmp_path)
    owner = tmp_path / "owner.json"
    result = tmp_path / "result.json"
    mode = "normal-shell" if variant == "normal" else "creator"
    process = subprocess.Popen(
        [sys.executable, str(script), mode, str(REPO), str(owner), str(result),
         variant, request_variant],
        cwd=str(REPO),
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=12)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=3)
        raise AssertionError("process-tree fixture timed out: %s" % stderr)
    assert process.returncode == 0, stderr
    if variant == "dead":
        helper = subprocess.run(
            [sys.executable, str(script), "helper", str(REPO), str(owner),
             str(result), variant, request_variant],
            cwd=str(REPO), capture_output=True, text=True, timeout=8,
            check=False,
        )
        assert helper.returncode == 0, helper.stderr
    assert result.is_file(), stdout + stderr
    return json.loads(result.read_text(encoding="utf-8"))


def test_normal_bind_uses_the_real_direct_child_target_without_inherited_transfer(
        tmp_path):
    response = _run_tree(tmp_path, variant="normal")
    assert response["ok"] is True, response
    assert response["result"]["mode"] == "legacy-lease"
    owner = json.loads((tmp_path / "owner.json").read_text(encoding="utf-8"))
    assert response["result"]["pid"] == owner["requested_pid"]
    assert response["result"]["pid"] != owner["pid"]
    assert response["state_calls"] == 1


def test_inherited_bind_uses_real_creator_shell_helper_chain_and_binds_creator(
        tmp_path):
    response = _run_tree(tmp_path)
    assert response["ok"] is True, response
    assert response["result"]["mode"] == "legacy-lease"
    owner = json.loads((tmp_path / "owner.json").read_text(encoding="utf-8"))
    assert response["result"]["pid"] == owner["pid"]
    assert response["state_calls"] == 1
    assert (tmp_path / "result.mutation").is_file()


def test_inherited_bind_uses_real_shell_target_for_normal_exec(tmp_path):
    response = _run_tree(tmp_path, variant="inherited-normal")
    assert response["ok"] is True, response
    assert response["result"]["mode"] == "legacy-lease"
    owner = json.loads((tmp_path / "owner.json").read_text(encoding="utf-8"))
    assert response["result"]["pid"] == owner["requested_pid"]
    assert response["result"]["pid"] != owner["pid"]
    assert response["state_calls"] == 1


@pytest.mark.parametrize(
    "variant",
    ["grandchild", "capture", "foreign"],
    ids=["grandchild", "capture-subshell", "foreign-caller"],
)
def test_inherited_bind_rejects_non_direct_real_process_lineage_without_mutation(
        tmp_path, variant):
    response = _run_tree(tmp_path, variant=variant)
    assert response["ok"] is False, response
    assert response["state_calls"] == 0
    assert not (tmp_path / "result.mutation").exists()


def test_inherited_bind_rejects_a_real_sibling_target_without_mutation(tmp_path):
    response = _run_tree(tmp_path, request_variant="sibling")
    assert response["ok"] is False, response
    assert response["state_calls"] == 0
    assert not (tmp_path / "result.mutation").exists()


@pytest.mark.parametrize(
    "request_variant",
    ["wrong-lease", "wrong-request", "wrong-lane", "race"],
    ids=["wrong-lease", "wrong-request", "wrong-lane", "lineage-race"],
)
def test_inherited_bind_refuses_wrong_pending_context_or_race_without_mutation(
        tmp_path, request_variant):
    response = _run_tree(tmp_path, request_variant=request_variant)
    assert response["ok"] is False, response
    assert response["state_calls"] == 0
    assert not (tmp_path / "result.mutation").exists()


def test_inherited_bind_rejects_dead_or_changed_creator_identity(tmp_path):
    dead = _run_tree(tmp_path / "dead", variant="dead")
    assert dead["ok"] is False, dead
    assert dead["state_calls"] == 0

    changed = _run_tree(tmp_path / "changed", variant="changed-token")
    assert changed["ok"] is False, changed
    assert changed["state_calls"] == 0
