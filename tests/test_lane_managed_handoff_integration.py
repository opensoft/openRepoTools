# SPDX-License-Identifier: Apache-2.0
"""T022 acceptance through the real managed daemon and public socket.

The runner is an injected lifecycle double, while ownership, controller
durability, and the request router are the production implementations.  This
keeps the acceptance proof local and deterministic: a user checkpoint must
not become a runtime, owner, claim, projection, account, or native-worker
mutation.
"""

from __future__ import annotations

import asyncio
import copy
import subprocess
import threading
from pathlib import Path
from typing import Any, Mapping

from lane_managed_controller import ManagedController
from lane_managed_daemon import ManagedDaemon, serve_daemon
from lane_managed_state import ManagedStateStore, resolve_workspace
from test_lane_managed_controller_rollover import RolloverRuntime
from test_lane_managed_daemon import (
    VerifyingProfiles,
    _load_cli_api,
    _native_start_body,
    _start_request,
    _stop_server_thread,
    _wait_for_socket,
)


def _transcript_verifier(
        _profile: Any, session_id: str, workspace: str | Path,
) -> dict[str, Any]:
    workspace = str(workspace)
    return {
        "profile": {
            "name": "team-a",
            "email": "a@example.invalid",
            "family": "family-a",
            "config_dir": "/managed/profiles/team-a",
        },
        "session_id": session_id,
        "workspace": workspace,
        "transcript_store": "/managed/transcripts",
        "transcript_project": str(Path(workspace) / "transcripts"),
        "holders": [],
        "unknown_holders": [],
        "ambiguous": False,
        "transcript": {
            "session_id": session_id,
            "exists": True,
            "written": True,
            "reserved": False,
        },
    }


def _wire_request(
        request_id: str, operation: str, generation: int,
        body: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": 2,
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "request_id": request_id,
        "lane": "build",
        "generation": generation,
        "operation": operation,
        "body": dict(body),
    }


def _durable_files(state: ManagedStateStore) -> dict[str, bytes]:
    """Capture JSON ledgers and journals without invoking a writer."""

    files: dict[str, bytes] = {}
    for label, root in (
            ("state", state.identity.state_root),
            ("global", state.identity.global_root),
    ):
        for path in sorted(root.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.suffix in {".json", ".jsonl"}:
                files["%s/%s" % (label, path.name)] = path.read_bytes()
    return files


def _runtime_snapshot(runtime: Any) -> dict[str, Any]:
    """Capture every lifecycle/dispatch collection exposed by the fake."""

    names = (
        "calls", "opened", "released", "sent", "prepare_requests",
        "prepare_responses", "open_evidence", "interrupted", "shutdowns",
    )
    return {
        name: copy.deepcopy(getattr(runtime, name, None))
        for name in names
    }


def _snapshot(
        state: ManagedStateStore, controller: ManagedController,
        daemon: ManagedDaemon, runtime: Any, profiles: Any,
) -> dict[str, Any]:
    """Collect durable and in-memory authorities around one handoff."""

    return {
        "files": _durable_files(state),
        "controller": copy.deepcopy(state.read_json("controller.json")),
        "owner": copy.deepcopy(state.read_json("owner.json")),
        "generation": copy.deepcopy(state.read_json("generation.json")),
        "claims": copy.deepcopy(state.read_lineage_claims()),
        "runtime_record": copy.deepcopy(state.read_json("runtime.json")),
        "adoptions": copy.deepcopy(state.read_json("native-adoptions.json")),
        "status": copy.deepcopy(controller.status()),
        "owner_record": copy.deepcopy(daemon.owner_record),
        "discovery_record": copy.deepcopy(daemon.discovery_record),
        "projection": copy.deepcopy(daemon.projection),
        "runtime": _runtime_snapshot(runtime),
        "profile_verifier_calls": copy.deepcopy(
            getattr(profiles, "verifier_calls", None)
        ),
    }


def _status_without_checkpoints(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    result.pop("checkpoints", None)
    return result


def _assert_handoff_only_controller_change(
        before: Mapping[str, Any], after: Mapping[str, Any],
        request_id: str, result: Mapping[str, Any],
) -> None:
    assert set(before) == set(after)
    for key in set(before).difference({"requests", "checkpoints"}):
        assert after[key] == before[key], key

    before_requests = before["requests"]
    after_requests = after["requests"]
    assert isinstance(before_requests, Mapping)
    assert isinstance(after_requests, Mapping)
    assert set(after_requests).difference(before_requests) == {request_id}
    assert after_requests[request_id]["result"] == dict(result)

    before_checkpoints = before["checkpoints"]
    after_checkpoints = after["checkpoints"]
    assert isinstance(before_checkpoints, list)
    assert isinstance(after_checkpoints, list)
    assert after_checkpoints == before_checkpoints + [dict(result)]


def test_public_socket_handoff_changes_only_checkpoint_ledger(
        tmp_path: Path,
) -> None:
    """A released real operation accepts a checkpoint without lifecycle writes."""

    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
    )
    agents_root = tmp_path / "agents"
    agents_root.mkdir(mode=0o700)
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    env = {
        "HOME": str(home),
        "AGENT_PROTOCOL_ROOT": str(agents_root),
        "LANES_WORKSTATION": "handoff-test",
    }
    identity = resolve_workspace(
        "build",
        env=env,
        helper=lambda *_args, **_kwargs: (str(workspace) + "\n", 0, ""),
    )
    state = ManagedStateStore(identity)
    state.ensure_layout()
    runtime = RolloverRuntime()
    profiles = VerifyingProfiles()
    controller = ManagedController(
        state,
        runtime=runtime,
        payload_resolver=lambda payload_ref: str(payload_ref),
        transcript_verifier=_transcript_verifier,
        clock=lambda: 1000.0,
    )
    daemon = ManagedDaemon(
        state=state,
        profiles=profiles,
        controller=controller,
        adapter=runtime,
        daemon_id="daemon-handoff-test",
        opt_in=True,
        lane="build",
        env=env,
    )
    asyncio.run(daemon.start())
    generation = int(daemon.owner_record["generation"])

    start_body = _native_start_body()
    start_body["coordinator"]["metadata"].update({
        "workspace": str(workspace),
        "transcript_project": str(workspace / "transcripts"),
    })
    runner_spec = start_body["runner_specs"]["coordinator"]
    runner_spec.update({
        "cwd": str(workspace),
        "transcript_project": str(workspace / "transcripts"),
    })
    runner_spec["fingerprint"].update({"workspace": str(workspace)})
    runner_spec["fingerprint"]["native_config"].update({
        "workspace": str(workspace),
        "repository": str(workspace),
    })

    api = _load_cli_api()
    socket_path = tmp_path / "managed-handoff.sock"
    stop_event = threading.Event()
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            serve_daemon(
                str(socket_path),
                daemon,
                operation_timeout=2.0,
                stop_event=stop_event,
            )
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(
        target=serve, name="managed-public-handoff", daemon=True,
    )
    thread.start()
    _wait_for_socket(socket_path, thread)

    def request(
            request_id: str, operation: str,
            body: Mapping[str, Any],
    ) -> dict[str, Any]:
        wire = (
            _start_request(request_id, start_body)
            if operation == "start"
            else _wire_request(request_id, operation, generation, body)
        )
        wire["generation"] = generation
        return api["request_socket"](
            str(socket_path), wire,
            connect_timeout=0.5, operation_timeout=2.0,
        )

    try:
        started = request("handoff-start", "start", {})
        assert started["ok"] is True
        operation_id = started["result"]["operation_id"]
        assert started["result"]["phase"] == "ready-held"

        released = request("handoff-release", "release", {
            "operation_id": operation_id,
        })
        assert released["ok"] is True
        assert released["result"]["phase"] == "released"

        before = _snapshot(state, controller, daemon, runtime, profiles)
        assert before["status"]["phase"] == "released"
        assert before["status"]["operation"]["phase"] == "released"
        assert before["owner"]["generation"] == generation

        checkpoint = "checkpoint://handoff/t022"
        first = request("handoff-request", "handoff", {
            "checkpoint": checkpoint,
        })
        assert first["ok"] is True
        result = first["result"]
        assert set(result) == {
            "request_id", "generation", "checkpoint", "checkpoint_digest",
            "operation_id", "operation_phase", "created_at",
        }
        assert result["request_id"] == "handoff-request"
        assert result["generation"] == generation
        assert result["checkpoint"] == checkpoint
        assert result["operation_id"] == operation_id
        assert result["operation_phase"] == "released"

        after_first = _snapshot(state, controller, daemon, runtime, profiles)
        _assert_handoff_only_controller_change(
            before["controller"], after_first["controller"],
            "handoff-request", result,
        )
        changed_files = {
            name for name, payload in after_first["files"].items()
            if before["files"].get(name) != payload
        }
        assert changed_files.issubset({
            "state/controller.json", "state/controller.jsonl",
        })
        assert "state/controller.json" in changed_files
        assert "state/controller.jsonl" in changed_files

        # The complete non-checkpoint status and all authorities remain at
        # the released boundary.  This includes account/native participant
        # facts carried inside the controller snapshot.
        assert after_first["owner"] == before["owner"]
        assert after_first["generation"] == before["generation"]
        assert after_first["claims"] == before["claims"]
        assert after_first["runtime_record"] == before["runtime_record"]
        assert after_first["adoptions"] == before["adoptions"]
        assert after_first["owner_record"] == before["owner_record"]
        assert after_first["discovery_record"] == before["discovery_record"]
        assert after_first["projection"] == before["projection"]
        assert _status_without_checkpoints(after_first["status"]) == (
            _status_without_checkpoints(before["status"])
        )
        assert after_first["runtime"] == before["runtime"]
        assert after_first["profile_verifier_calls"] == before[
            "profile_verifier_calls"
        ]

        # Exact retry is a read of the durable result: no record or journal
        # bytes may move, and no runtime boundary may be consulted.
        retry = request("handoff-request", "handoff", {
            "checkpoint": checkpoint,
        })
        assert retry["ok"] is True
        assert retry["result"] == result
        after_retry = _snapshot(state, controller, daemon, runtime, profiles)
        assert after_retry == after_first

        # Reusing the request ID for different content is refused before a
        # request/checkpoint write and preserves the same released snapshot.
        changed = request("handoff-request", "handoff", {
            "checkpoint": "checkpoint://handoff/changed",
        })
        assert changed["ok"] is False
        assert changed["code"] == "invalid"
        after_changed = _snapshot(state, controller, daemon, runtime, profiles)
        assert after_changed == after_first
    finally:
        _stop_server_thread(socket_path, stop_event, thread)

    assert not thread.is_alive()
    assert errors == []
