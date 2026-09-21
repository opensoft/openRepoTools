# SPDX-License-Identifier: Apache-2.0
"""Fake-only tests for the persistent managed daemon's status boundary.

This first daemon slice deliberately injects all four authorities and does
not import the Claude SDK, authentication, credentials, network clients, or a
live runner.  The fake controller uses the exact ``status`` operation and the
daemon's public request envelope; no alternate operation/evidence aliases are
provided.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import hashlib
import inspect
import json
import os
import runpy
import socket
import threading
import time
from pathlib import Path
from typing import Any, Iterator, Mapping

import pytest

from lane_managed_controller import (
    ControllerError,
    ManagedController,
    Operation,
    Participant,
    WriterClaim,
)
from lane_managed_daemon import (
    DaemonError,
    ManagedDaemon,
    _current_process_domain,
    resolve_payload_reference,
    run_supervisor,
    serve_daemon,
)
from lane_managed_sdk import RunnerSpec
from lane_managed_state import ManagedStateStore, resolve_workspace


LANE = "build"
BOUND_LANE = LANE
GENERATION = 7


def _canonical_session_name(participant_id: str) -> str:
    """Return the one durable, distinct runner name used by every fixture."""
    return "managed-%s-%s" % (BOUND_LANE, participant_id)


def _request(request_id: str) -> dict[str, Any]:
    return {
        "schema": 2,
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "request_id": request_id,
        "lane": LANE,
        "generation": GENERATION,
        "operation": "status",
        "body": {},
    }


def _unenroll_request(
        request_id: str, generation: int = GENERATION) -> dict[str, Any]:
    request = _request(request_id)
    request["operation"] = "unenroll"
    request["generation"] = generation
    return request


class FakeState:
    """Injected state authority; status must not discover state globally."""

    def __init__(self) -> None:
        self.owner = {
            "mode": "managed",
            "lane": LANE,
            "generation": GENERATION,
            "daemon_id": "daemon-test",
        }

    def discover_owner(self, lane: str) -> dict[str, Any]:
        assert lane == LANE
        return dict(self.owner)

    def enroll_managed(
            self, daemon_id: str, process_domain: str | None = None
    ) -> dict[str, Any]:
        assert daemon_id == "daemon-test"
        owner = dict(self.owner)
        if process_domain is not None:
            owner["process_domain"] = process_domain
        return owner


class FakeProfiles:
    """Injected profile authority; no profile files or credentials are read."""

    def resolve(self, name: str) -> dict[str, str]:
        assert name == "team-a"
        return {
            "name": "team-a",
            "email": "a@example.invalid",
            "family": "family-a",
        }


class VerifyingProfiles(FakeProfiles):
    """Profile authority with the exact transcript-verifier seam."""

    def __init__(self) -> None:
        self.verifier_calls: list[tuple[Any, str, str | Path]] = []

    def verify_transcript(
            self, profile: Any, session_id: str,
            workspace: str | Path) -> dict[str, Any]:
        self.verifier_calls.append((profile, session_id, workspace))
        return {
            "participant_id": "unknown-until-controller",
            "session_id": session_id,
            "runner_instance_id": "transcript-" + session_id,
            "evidence": {
                "ready": False,
                "released": False,
                "active_turn": False,
                "turn_terminal": True,
                "drained": True,
                "participant_quiescent": True,
                "tools_quiescent": True,
                "uncertain_effects": [],
                "process": {
                    "pid": 100,
                    "process_group_id": 100,
                    "process_start_token": "token",
                    "process_group_owned": True,
                    "exited": False,
                    "group_excluded": False,
                },
                "initialization": {
                    "account_email": "a@example.invalid",
                    "permission_mode": "default",
                    "model": "model-a",
                    "fingerprint": {},
                },
            },
        }


class FakeAdapter:
    """Injected adapter marker; status must not import or invoke an SDK."""


class FakeController:
    """Exact status route recording its owning asyncio loop."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.loops: list[asyncio.AbstractEventLoop] = []

    async def status(self) -> dict[str, Any]:
        self.loops.append(asyncio.get_running_loop())
        self.calls.append({"operation": "status"})
        return {
            "owner": "daemon-test",
            "lane": LANE,
            "generation": GENERATION,
            "phase": "ready-held",
            "live_sdk": "verified",
        }


class UnenrollController(FakeController):
    """Authoritative quiescence result with a cross-authority event trace."""

    def __init__(self, events: list[tuple[str, Any]]) -> None:
        super().__init__()
        self.events = events
        self.unenroll_calls: list[int] = []

    async def unenroll(self, generation: int) -> dict[str, Any]:
        self.events.append(("controller.unenroll", generation))
        self.unenroll_calls.append(generation)
        return {
            "phase": "complete",
            "unenrolled": True,
            "claims_released": True,
            "owner_clear_ready": True,
        }


class UnenrollState(FakeState):
    """State fake that records the required owner-removal ordering."""

    def __init__(self, events: list[tuple[str, Any]]) -> None:
        super().__init__()
        self.events = events
        self.runtime: dict[str, Any] | None = {
            "daemon_id": "daemon-test",
            "generation": GENERATION,
        }
        self.fail_clear_runtime = False
        self.fail_unenroll = False

    def enroll_managed(
            self, daemon_id: str, process_domain: str | None = None
    ) -> dict[str, Any]:
        self.events.append(("state.enroll", daemon_id))
        return super().enroll_managed(daemon_id, process_domain)

    def clear_runtime(self, **identity: Any) -> dict[str, Any]:
        self.events.append(("state.clear_runtime", dict(identity)))
        if self.fail_clear_runtime:
            raise DaemonError("unknown", "runtime clear refused")
        self.runtime = None
        return {}

    def unenroll_managed(
            self, daemon_id: str, generation: int, *,
            quiescent: bool, claims_released: bool = True,
    ) -> dict[str, Any]:
        self.events.append((
            "state.unenroll",
            {
                "daemon_id": daemon_id,
                "generation": generation,
                "quiescent": quiescent,
                "claims_released": claims_released,
            },
        ))
        assert quiescent is True
        assert claims_released is True
        if self.fail_unenroll:
            raise DaemonError("ownership-conflict", "owner clear refused")
        self.owner = {}
        return {}


class RecordingProjection:
    """Injected LANES projection helper with a retryable refusal switch."""

    def __init__(self, events: list[tuple[str, Any]], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail
        self.calls: list[dict[str, Any]] = []
        self.projected = True

    def managed_clear(self, context: Mapping[str, Any]) -> dict[str, Any]:
        context = dict(context)
        self.events.append(("projection.managed_clear", context))
        self.calls.append(context)
        if self.fail:
            raise DaemonError("unknown", "projection refused")
        self.projected = False
        return {"cleared": True, **context}

    def managed_owner(self, context: Mapping[str, Any]) -> dict[str, Any]:
        context = dict(context)
        self.events.append(("projection.managed_owner", context))
        self.projected = True
        return {"projected": True, **context}


def _daemon(controller: Any) -> ManagedDaemon:
    return ManagedDaemon(
        state=FakeState(),
        profiles=FakeProfiles(),
        controller=controller,
        adapter=FakeAdapter(),
        daemon_id="daemon-test",
        opt_in=True,
    )


def test_unenroll_clears_managed_projection_after_quiescence_before_owner_removal():
    events: list[tuple[str, Any]] = []
    state = UnenrollState(events)
    controller = UnenrollController(events)
    projection = RecordingProjection(events)
    daemon = ManagedDaemon(
        state=state,
        profiles=FakeProfiles(),
        controller=controller,
        adapter=FakeAdapter(),
        daemon_id="daemon-test",
        opt_in=True,
        lane=LANE,
        projection=projection,
    )
    asyncio.run(daemon.start())
    daemon.discovery_identity = (
        "daemon-test", GENERATION, 100, "start-token", 101, "local",
    )
    daemon.discovery_record = {"daemon_id": "daemon-test"}

    response = asyncio.run(daemon.handle_request(_unenroll_request("unenroll-order")))

    assert response["ok"] is True
    assert response["result"]["owner_cleared"] is True
    assert [event[0] for event in events] == [
        "state.enroll",
        "controller.unenroll",
        "projection.managed_clear",
        "state.clear_runtime",
        "state.unenroll",
    ]
    assert projection.calls == [{
        "lane": LANE,
        "mode": "managed",
        "daemon_id": "daemon-test",
        "generation": GENERATION,
        "bound_lane": LANE,
        "authoritative_unenroll": True,
    }]
    assert state.owner == {}
    assert daemon.owner_record is None
    assert daemon._owner_enrolled is False
    assert daemon.started is False


def test_unenroll_projection_refusal_retains_runtime_discovery_and_owner():
    events: list[tuple[str, Any]] = []
    state = UnenrollState(events)
    controller = UnenrollController(events)
    projection = RecordingProjection(events, fail=True)
    daemon = ManagedDaemon(
        state=state,
        profiles=FakeProfiles(),
        controller=controller,
        adapter=FakeAdapter(),
        daemon_id="daemon-test",
        opt_in=True,
        lane=LANE,
        projection=projection,
    )
    asyncio.run(daemon.start())
    identity = (
        "daemon-test", GENERATION, 100, "start-token", 101, "local",
    )
    daemon.discovery_identity = identity
    daemon.discovery_record = {"daemon_id": "daemon-test"}
    owner_before = dict(state.owner)
    runtime_before = dict(state.runtime or {})

    refused = asyncio.run(
        daemon.handle_request(_unenroll_request("unenroll-projection-refused-runtime"))
    )

    assert refused["ok"] is False
    assert refused["code"] == "unknown"
    assert [event[0] for event in events] == [
        "state.enroll",
        "controller.unenroll",
        "projection.managed_clear",
    ]
    assert state.owner == owner_before
    assert state.runtime == runtime_before
    assert projection.projected is True
    assert daemon.discovery_identity == identity
    assert daemon.discovery_record == {"daemon_id": "daemon-test"}
    assert daemon.owner_record is not None
    assert daemon._owner_enrolled is True
    assert daemon.started is True

    projection.fail = False
    retried = asyncio.run(
        daemon.handle_request(_unenroll_request("unenroll-projection-retry-runtime"))
    )

    assert retried["ok"] is True
    assert retried["result"]["owner_cleared"] is True
    assert state.owner == {}
    assert state.runtime is None
    assert daemon.discovery_identity is None


@pytest.mark.parametrize("failure", ["runtime", "owner"])
def test_unenroll_local_failure_restores_projection_for_clean_retry(failure: str):
    events: list[tuple[str, Any]] = []
    state = UnenrollState(events)
    if failure == "runtime":
        state.fail_clear_runtime = True
    else:
        state.fail_unenroll = True
    projection = RecordingProjection(events)
    daemon = ManagedDaemon(
        state=state,
        profiles=FakeProfiles(),
        controller=UnenrollController(events),
        adapter=FakeAdapter(),
        daemon_id="daemon-test",
        opt_in=True,
        lane=LANE,
        projection=projection,
    )
    asyncio.run(daemon.start())
    identity = (
        "daemon-test", GENERATION, 100, "start-token", 101, "local",
    )
    daemon.discovery_identity = identity
    daemon.discovery_record = {"daemon_id": "daemon-test"}
    owner_before = dict(state.owner)
    runtime_before = dict(state.runtime or {})

    refused = asyncio.run(
        daemon.handle_request(_unenroll_request("unenroll-local-failure-" + failure))
    )

    assert refused["ok"] is False
    assert refused["code"] in {"unknown", "ownership-conflict"}
    assert state.owner == owner_before
    assert projection.projected is True
    assert daemon.owner_record is not None
    assert daemon._owner_enrolled is True
    assert daemon.started is True
    expected_events = [
        "state.enroll",
        "controller.unenroll",
        "projection.managed_clear",
        "state.clear_runtime",
    ]
    if failure == "owner":
        expected_events.append("state.unenroll")
    expected_events.append("projection.managed_owner")
    assert [event[0] for event in events] == expected_events
    if failure == "runtime":
        assert state.runtime == runtime_before
        assert daemon.discovery_identity == identity
    else:
        assert state.runtime is None
        assert daemon.discovery_identity is None

    state.fail_clear_runtime = False
    state.fail_unenroll = False
    generation = daemon.owner_record["generation"]
    retried = asyncio.run(
        daemon.handle_request(_unenroll_request("unenroll-local-retry-" + failure, generation))
    )

    assert retried["ok"] is True
    assert retried["result"]["owner_cleared"] is True
    assert state.owner == {}
    assert state.runtime is None
    assert projection.projected is False
    assert daemon.owner_record is None
    assert daemon.started is False


def test_clear_owner_projection_uses_exact_production_managed_clear_argv(
        tmp_path: Path):
    helper = tmp_path / "lanes-edit.sh"
    arguments = tmp_path / "projection-arguments"
    helper.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$@\" > \"$PROJECTION_ARGS\"\n",
        encoding="utf-8",
    )
    helper.chmod(0o700)
    state = FakeState()
    daemon = ManagedDaemon(
        state=state,
        profiles=FakeProfiles(),
        controller=FakeController(),
        adapter=FakeAdapter(),
        daemon_id="daemon-test",
        opt_in=True,
        lane=LANE,
        env={
            "LANES_EDIT": str(helper),
            "PROJECTION_ARGS": str(arguments),
        },
    )
    daemon.owner_record = dict(state.owner)
    daemon._owner_enrolled = True

    result = daemon.clear_owner_projection()

    assert result == {
        "cleared": True,
        "lane": LANE,
        "mode": "managed",
        "daemon_id": "daemon-test",
        "generation": GENERATION,
        "bound_lane": LANE,
        "authoritative_unenroll": True,
    }
    assert arguments.read_text(encoding="utf-8").splitlines() == [
        "managed-clear",
        LANE,
        "--mode",
        "managed",
        "--daemon-id",
        "daemon-test",
        "--generation",
        str(GENERATION),
        "--bound-lane",
        LANE,
        "--authoritative-unenroll",
    ]


def test_unenroll_projection_refusal_retains_real_owner_for_retry(
        managed_workspace):
    env = dict(managed_workspace.env)
    env["LANES_WORKSTATION"] = "daemon-test-host"

    def workspace_runner(command: Any, **_: Any) -> tuple[str, int, str]:
        assert list(command) == ["lanes-edit.sh", "workspace-root"]
        return str(managed_workspace.workspace_repo.resolve()) + "\n", 0, ""

    identity = resolve_workspace(
        LANE,
        env=env,
        helper=lambda: None,
        runner=workspace_runner,
    )
    state = ManagedStateStore(identity)
    events: list[tuple[str, Any]] = []
    projection = RecordingProjection(events, fail=True)
    daemon = ManagedDaemon(
        state=state,
        profiles=FakeProfiles(),
        controller=UnenrollController(events),
        adapter=FakeAdapter(),
        daemon_id="daemon-test",
        opt_in=True,
        lane=LANE,
        env=env,
        projection=projection,
    )
    asyncio.run(daemon.start())
    owner_before = state.read_json("owner.json")
    generation = owner_before["generation"]

    refused = asyncio.run(
        daemon.handle_request(_unenroll_request("unenroll-projection-refused", generation))
    )

    assert refused["ok"] is False
    assert refused["code"] == "unknown"
    assert state.read_json("owner.json") == owner_before
    assert daemon.owner_record == owner_before
    assert daemon._owner_enrolled is True
    assert daemon.started is True
    assert [event[0] for event in events] == [
        "controller.unenroll",
        "projection.managed_clear",
    ]

    projection.fail = False
    retried = asyncio.run(
        daemon.handle_request(_unenroll_request("unenroll-projection-retry", generation))
    )

    assert retried["ok"] is True
    assert retried["result"]["owner_cleared"] is True
    assert state.read_json("owner.json") == {}


def _read_response(client: socket.socket) -> dict[str, Any]:
    chunks: list[bytes] = []
    while True:
        chunk = client.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    frame = b"".join(chunks).split(b"\n", 1)[0]
    return json.loads(frame.decode("utf-8"))


def _send(socket_path: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.dumps(dict(request), sort_keys=True,
                         separators=(",", ":")).encode("utf-8") + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2.0)
        client.connect(str(socket_path))
        client.sendall(payload)
        return _read_response(client)


def _wait_for_socket(socket_path: Path, thread: threading.Thread,
                     timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not socket_path.exists() and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert socket_path.exists()


def _wake_socket(socket_path: Path) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.1)
            client.connect(str(socket_path))
    except OSError:
        pass


def _stop_server_thread(socket_path: Path, stop_event: threading.Event,
                        thread: threading.Thread) -> None:
    stop_event.set()
    deadline = time.monotonic() + 1.0
    while thread.is_alive() and time.monotonic() < deadline:
        if socket_path.exists():
            _wake_socket(socket_path)
        thread.join(timeout=0.05)
    thread.join(timeout=1.0)


def test_handle_request_routes_status_to_injected_controller():
    controller = FakeController()
    daemon = _daemon(controller)
    request = _request("status-direct")

    response = asyncio.run(daemon.handle_request(request))

    assert response["schema"] == 2
    assert response["schema_version"] == 2
    assert response["architecture"] == "native-coordinator-lineage"
    assert response["request_id"] == "status-direct"
    assert response["ok"] is True
    assert response["generation"] == GENERATION
    assert response["result"]["phase"] == "ready-held"
    assert controller.calls == [{"operation": "status"}]
    assert len(controller.loops) == 1


class CancelledController:
    """A cancellation must cross the daemon boundary, not become a result."""

    async def status(self) -> dict[str, Any]:
        raise asyncio.CancelledError


def test_handle_request_propagates_asyncio_cancellation():
    daemon = _daemon(CancelledController())  # type: ignore[arg-type]

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(daemon.handle_request(_request("status-cancelled")))


class GenerationRefusal(RuntimeError):
    code = "stale-generation"


class SubmitController:
    """Exact submit seam; generation is an authority argument, not body data."""

    def __init__(self) -> None:
        self.generation = GENERATION
        self.calls: list[dict[str, Any]] = []
        self.mailboxes: list[dict[str, Any]] = []

    def submit(self, request_id: str, recipient_id: str, payload_ref: Any,
               sender_id: str, task_id: Any, *, generation: int) -> dict[str, Any]:
        self.calls.append({
            "request_id": request_id,
            "recipient_id": recipient_id,
            "payload_ref": payload_ref,
            "sender_id": sender_id,
            "task_id": task_id,
            "generation": generation,
        })
        if generation != self.generation:
            raise GenerationRefusal("expected generation does not match")
        entry = {
            "message_id": "msg-real-1",
            "request_id": request_id,
            "recipient_id": recipient_id,
            "payload_ref": payload_ref,
            "state": "queued",
            "generation": generation,
        }
        self.mailboxes.append(entry)
        return dict(entry)


def _submit_request(request_id: str, generation: int) -> dict[str, Any]:
    return {
        "schema": 2,
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "request_id": request_id,
        "lane": LANE,
        "generation": generation,
        "operation": "submit",
        "body": {
            "recipient_id": "worker-a",
            "payload_ref": "payload-ref-1",
            "sender_id": "user",
            "task_id": "task-a",
        },
    }


def test_submit_passes_expected_generation_and_stale_request_has_zero_mailbox_mutation():
    controller = SubmitController()
    daemon = _daemon(controller)

    async def exercise() -> tuple[dict[str, Any], dict[str, Any]]:
        await daemon.start()
        stale = await daemon.handle_request(_submit_request("submit-stale", GENERATION - 1))
        current = await daemon.handle_request(_submit_request("submit-current", GENERATION))
        return stale, current

    stale, current = asyncio.run(exercise())

    assert stale["ok"] is False
    assert stale["code"] == "stale-generation"
    assert current["ok"] is True
    assert current["result"]["message_id"] == "msg-real-1"
    assert len(controller.calls) == 2
    assert controller.calls[0]["generation"] == GENERATION - 1
    assert controller.calls[1]["generation"] == GENERATION
    assert len(controller.mailboxes) == 1
    assert controller.mailboxes[0]["request_id"] == "submit-current"
    assert controller.mailboxes[0]["message_id"] != "forged-message"
    assert "evidence" not in controller.calls[1]


class BoundedHistoryController(FakeController):
    """Status fake used by a long-lived bounded-response-history service."""

    def __init__(self) -> None:
        super().__init__()
        self.status_count = 0

    async def status(self) -> dict[str, Any]:
        self.status_count += 1
        self.loops.append(asyncio.get_running_loop())
        self.calls.append({"operation": "status"})
        return {
            "owner": "daemon-test",
            "lane": LANE,
            "generation": GENERATION,
            "phase": "ready-held",
            "status_count": self.status_count,
            "large_diagnostic": "x" * 4096,
        }


def test_long_lived_service_bounds_response_history(tmp_path: Path):
    """A bounded history seam prevents indefinite service from retaining frames."""
    controller = BoundedHistoryController()
    daemon = _daemon(controller)
    socket_path = tmp_path / "bounded-history.sock"
    stop_event = threading.Event()
    served: list[list[dict[str, Any]]] = []
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            served.append(serve_daemon(
                str(socket_path), daemon,
                max_requests=40,
                operation_timeout=1.0,
                stop_event=stop_event,
            ))
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(
        target=serve, name="managed-daemon-bounded-history", daemon=True
    )
    thread.start()
    try:
        _wait_for_socket(socket_path, thread)
        for index in range(40):
            response = _send(socket_path, _request("history-%d" % index))
            assert response["ok"] is True
    finally:
        _stop_server_thread(socket_path, stop_event, thread)

    assert not thread.is_alive()
    assert not errors
    assert len(served) == 1
    assert len(served[0]) == 32
    assert [response["request_id"] for response in served[0]] == [
        "history-%d" % index for index in range(8, 40)
    ]
    assert all("large_diagnostic" not in response for response in served[0])
    assert controller.status_count == 40
    assert len(controller.loops) == 40
    assert len({id(loop) for loop in controller.loops}) == 1


def test_serve_daemon_status_socket_reuses_one_loop_and_reports_unverified(
        tmp_path: Path):
    controller = FakeController()
    daemon = _daemon(controller)
    socket_path = tmp_path / "managed.sock"
    stop_event = threading.Event()
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            serve_daemon(
                str(socket_path), daemon,
                max_requests=2,
                operation_timeout=1.0,
                stop_event=stop_event,
            )
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(
        target=serve, name="managed-daemon-status", daemon=True
    )
    thread.start()
    try:
        _wait_for_socket(socket_path, thread)
        first = _send(socket_path, _request("status-socket-1"))
        second = _send(socket_path, _request("status-socket-2"))
    finally:
        _stop_server_thread(socket_path, stop_event, thread)

    assert not thread.is_alive()
    assert not errors
    for response, request_id in (
        (first, "status-socket-1"), (second, "status-socket-2"),
    ):
        assert response["schema"] == 2
        assert response["schema_version"] == 2
        assert response["architecture"] == "native-coordinator-lineage"
        assert response["request_id"] == request_id
        assert response["ok"] is True
        assert response["result"]["live_sdk"] == "UNVERIFIED"
        assert response["result"]["capability_status"] == "experimental"
    assert len(controller.loops) == 2
    assert controller.loops[0] is controller.loops[1]
    assert controller.calls == [
        {"operation": "status"}, {"operation": "status"}
    ]


def _wire_claim(participant_id: str) -> dict[str, Any]:
    return {
        "participant_id": participant_id,
        "worktree": "/managed/worktrees/" + participant_id,
        "repository": "/managed/repository",
        "state": "active",
        "lane": BOUND_LANE,
        "metadata": {},
    }


def _wire_participant(
        participant_id: str, session_id: str, role: str,
        parent_id: Any, task_id: str, mailbox_id: str) -> dict[str, Any]:
    session_name = _canonical_session_name(participant_id)
    return {
        "participant_id": participant_id,
        "session_id": session_id,
        "session_name": session_name,
        "bound_lane": BOUND_LANE,
        "role": role,
        "parent_id": parent_id,
        "task_id": task_id,
        "mailbox_id": mailbox_id,
        "kind": "independent",
        "state": "reserved",
        "writer_claim": _wire_claim(participant_id),
        "read_only": False,
        "background": False,
        "detached": False,
        "model": "model-a",
        "permission_mode": "default",
        "fingerprint": {
            "profile_name": "team-a",
            "session_name": session_name,
            "bound_lane": BOUND_LANE,
        },
        "metadata": {
            "session_name": session_name,
            "bound_lane": BOUND_LANE,
            "profile_name": "team-a",
            "profile_family": "family-a",
            "profile_status": "active",
            "profile_authentication": {"type": "subscription_oauth"},
            "account_email": "a@example.invalid",
            "config_dir": "/managed/profiles/team-a",
            "workspace": "/managed/workspace",
            "transcript_store": "/managed/transcripts",
            "transcript_project": "/managed/transcripts/workspace",
            "transcript": {
                "session_id": session_id,
                "exists": True,
                "written": True,
                "reserved": False,
            },
        },
    }


def _wire_runner_spec(
        participant_id: str, session_id: str) -> dict[str, Any]:
    session_name = _canonical_session_name(participant_id)
    return {
        "session_id": session_id,
        "session_name": session_name,
        "bound_lane": BOUND_LANE,
        "mode": "resume",
        "resume": True,
        "account_email": "a@example.invalid",
        "permission_mode": "default",
        "model": "model-a",
        "fingerprint": {
            "profile_name": "team-a",
            "session_name": session_name,
            "bound_lane": BOUND_LANE,
        },
        "config_dir": "/managed/profiles/team-a",
        "cwd": "/managed/workspace",
        "transcript_store": "/managed/transcripts",
        "transcript_project": "/managed/transcripts/workspace",
        "profile_family": "family-a",
        "profile_name": "team-a",
        "participant_id": participant_id,
    }


def _independent_start_body() -> dict[str, Any]:
    coordinator = _wire_participant(
        "coordinator", "session-coordinator", "coordinator", None,
        "task-root", "mailbox-coordinator",
    )
    workers = [
        _wire_participant(
            "worker-a", "session-worker-a", "worker", "coordinator",
            "task-a", "mailbox-worker-a",
        ),
        _wire_participant(
            "worker-b", "session-worker-b", "worker", "coordinator",
            "task-b", "mailbox-worker-b",
        ),
    ]
    roster = [coordinator] + workers
    return {
        "coordinator": coordinator,
        "participants": workers,
        "runner_specs": {
            item["participant_id"]: _wire_runner_spec(
                item["participant_id"], item["session_id"],
            )
            for item in roster
        },
    }


def _native_definition_payload() -> dict[str, Any]:
    return {
        "writer": {
            "model": "configured-model",
            "effort": "high",
            "tools": ["Read", "Write"],
            "description": "synthetic native definition",
            "prompt": "synthetic native definition prompt",
        },
    }


def _native_start_body() -> dict[str, Any]:
    coordinator = _wire_participant(
        "coordinator", "session-coordinator", "coordinator", None,
        "task-root", "mailbox-coordinator",
    )
    coordinator["writer_claim"] = None
    coordinator["read_only"] = True
    coordinator["metadata"].update({
        "read_only_enforced": True,
        "tool_allowlist": ["Read"],
        "tool_denylist": ["Write", "Edit", "Bash", "Agent", "Task", "Team"],
        "tools": [],
        "mcp_servers": [],
        "permissions": {
            "mode": "allowlist",
            "enforced": True,
            "allow": ["Read"],
            "deny": ["Write", "Edit", "Bash", "Agent", "Task", "Team"],
            "mcp": [],
        },
    })
    spec = _wire_runner_spec(
        "coordinator", "session-coordinator",
    )
    spec["fingerprint"]["native_config"] = {
        "lineage_id": "daemon-native-lineage",
        "lineage_generation": 1,
        "runner_incarnation": "runner-coordinator",
        "trusted_definitions": _native_definition_payload(),
    }
    return {
        "coordinator": coordinator,
        "participants": [],
        "runner_specs": {"coordinator": spec},
    }


def _start_body() -> dict[str, Any]:
    """Canonical public start body: one managed coordinator only."""
    return _native_start_body()


def _start_request(request_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": 2,
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "request_id": request_id,
        "lane": LANE,
        "generation": GENERATION,
        "operation": "start",
        "body": dict(body),
    }


class StartAdapter(FakeAdapter):
    """Adapter fake proving held submit never reaches runtime dispatch."""

    def __init__(self) -> None:
        self.dispatches: list[dict[str, Any]] = []

    async def send(self, participant_id: str, message_id: str,
                   payload_ref: str) -> dict[str, Any]:
        self.dispatches.append({
            "participant_id": participant_id,
            "message_id": message_id,
            "payload_ref": payload_ref,
        })
        return {
            "participant_id": participant_id,
            "message_id": message_id,
            "accepted": True,
            "ack_kind": "accepted-send",
        }

    async def status(self, participant_id: str) -> dict[str, Any]:
        assert participant_id == "coordinator"
        evidence = {
            "participant_id": participant_id,
            "session_id": "session-coordinator",
            "runner_instance_id": "runner-coordinator",
            "ready": True,
            "released": True,
            "active_turn": False,
            "turn_terminal": True,
            "drained": True,
            "participant_quiescent": True,
            "tools_quiescent": True,
            "quiescent": True,
            "tools": [],
            "uncertain_effects": [],
            "uncertain_effects_overflow": False,
            "process": {
                "pid": 5102,
                "process_group_id": 6102,
                "process_start_token": "start-coordinator",
                "process_group_owned": True,
                "exited": False,
                "group_excluded": False,
            },
        }
        return {
            "participant_id": participant_id,
            "session_id": evidence["session_id"],
            "runner_instance_id": evidence["runner_instance_id"],
            "evidence": evidence,
        }


class DurableMailboxState(FakeState):
    """Durable fake retaining only opaque mailbox refs and their digests."""

    def __init__(self) -> None:
        super().__init__()
        self.persisted_records: list[dict[str, Any]] = []


class PayloadResolver:
    """Trusted resolver whose text must never enter a durable record."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, payload_ref: str) -> str:
        self.calls.append(payload_ref)
        return "resolved payload text that must not be persisted"


class DuplicateRelease(RuntimeError):
    code = "busy"


class StartController(FakeController):
    """Exact controller start/submit seams used by the public router."""

    def __init__(self, *, state: DurableMailboxState | None = None,
                 adapter: StartAdapter | None = None,
                 payload_resolver: Any = None) -> None:
        super().__init__()
        self.state = state if state is not None else DurableMailboxState()
        self.adapter = adapter if adapter is not None else StartAdapter()
        self.payload_resolver = payload_resolver
        self.start_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []
        self.release_calls: list[dict[str, Any]] = []
        self.dispatch_calls: list[str] = []
        self.resolved_payloads: list[str] = []
        self.released = False
        self.dispatch_complete = False

    async def start(
            self, request_id: str, generation: int,
            coordinator: Participant,
            participants: list[Participant],
            runner_specs: Mapping[str, RunnerSpec]) -> Operation:
        self.start_calls.append({
            "request_id": request_id,
            "generation": generation,
            "coordinator": coordinator,
            "participants": list(participants),
            "runner_specs": dict(runner_specs),
        })
        return Operation(
            operation_id="operation-start",
            request_id=request_id,
            mode="start",
            generation=generation,
            phase="ready-held",
            sealed_participants=[
                coordinator.participant_id,
                *(item.participant_id for item in participants),
            ],
        )

    def submit(self, request_id: str, recipient_id: str, payload_ref: str,
               sender_id: str, task_id: Any, *, generation: int) -> dict[str, Any]:
        self.submit_calls.append({
            "request_id": request_id,
            "recipient_id": recipient_id,
            "payload_ref": payload_ref,
            "sender_id": sender_id,
            "task_id": task_id,
            "generation": generation,
        })
        self.state.persisted_records.append({
            "message_id": "message-held",
            "request_id": request_id,
            "recipient_id": recipient_id,
            "payload_ref": payload_ref,
            "payload_digest": hashlib.sha256(
                payload_ref.encode("utf-8")
            ).hexdigest(),
            "state": "queued",
        })
        self.queued_payload_ref = payload_ref
        return {
            "message_id": "message-held",
            "recipient_id": recipient_id,
            "payload_ref": payload_ref,
            "state": "queued",
            "dispatch": "held",
            "generation": generation,
        }

    async def release(self, operation_id: str, generation: int) -> Operation:
        self.release_calls.append({
            "operation_id": operation_id,
            "generation": generation,
        })
        if self.released:
            raise DuplicateRelease("operation has already been released")
        if operation_id != "operation-start":
            raise RuntimeError("unexpected operation identity")
        self.released = True
        return Operation(
            operation_id=operation_id,
            request_id="socket-start",
            mode="start",
            generation=generation,
            phase="released",
            sealed_participants=["coordinator"],
            release_count=1,
        )

    def dispatch_candidates(self, operation_id: str) -> list[dict[str, Any]]:
        assert operation_id == "operation-start"
        if self.dispatch_complete or not hasattr(self, "queued_payload_ref"):
            return []
        return [{
            "message_id": "message-held",
            "recipient_id": "coordinator",
            "session_id": "session-coordinator",
            "runner_instance_id": "runner-coordinator",
        }]

    async def dispatch_next(
            self, operation_id: str, *, recipient_id: str = "coordinator",
    ) -> dict[str, Any]:
        self.dispatch_calls.append(operation_id)
        if len(self.dispatch_calls) != 1:
            raise RuntimeError("dispatch was repeated")
        assert recipient_id == "coordinator"
        assert self.payload_resolver is not None
        resolved = self.payload_resolver(self.queued_payload_ref)
        if inspect.isawaitable(resolved):
            resolved = await resolved
        self.resolved_payloads.append(resolved)
        acknowledgement = await self.adapter.send(
            "coordinator", "message-held", resolved
        )
        self.state.persisted_records.append({
            "message_id": "message-held",
            "payload_ref": self.queued_payload_ref,
            "payload_digest": hashlib.sha256(
                self.queued_payload_ref.encode("utf-8")
            ).hexdigest(),
            "runtime_ack": acknowledgement,
            "state": "acknowledged",
        })
        self.dispatch_complete = True
        return {
            "message_id": "message-held",
            "payload_ref": self.queued_payload_ref,
            "state": "acknowledged",
            "runtime_ack": acknowledgement,
        }


def _start_daemon(
        controller: StartController,
        *, profiles: Any = None, adapter: Any = None,
        opt_in: bool = True, state: Any = None) -> ManagedDaemon:
    return ManagedDaemon(
        state=FakeState() if state is None else state,
        profiles=FakeProfiles() if profiles is None else profiles,
        controller=controller,
        adapter=FakeAdapter() if adapter is None else adapter,
        daemon_id="daemon-test",
        opt_in=opt_in,
    )


def test_public_start_converts_native_coordinator_before_controller():
    controller = StartController()
    profiles = VerifyingProfiles()
    daemon = _start_daemon(controller, profiles=profiles)
    asyncio.run(daemon.start())

    response = asyncio.run(
        daemon.handle_request(_start_request("start-direct", _start_body()))
    )

    assert response["ok"] is True
    assert response["result"]["phase"] == "ready-held"
    assert len(controller.start_calls) == 1
    call = controller.start_calls[0]
    assert call["request_id"] == "start-direct"
    assert call["generation"] == GENERATION
    assert type(call["coordinator"]) is Participant
    assert call["participants"] == []
    assert call["coordinator"].participant_id == "coordinator"
    assert call["coordinator"].session_name == _canonical_session_name("coordinator")
    assert call["coordinator"].bound_lane == BOUND_LANE
    assert call["coordinator"].read_only is True
    assert set(call["runner_specs"]) == {"coordinator"}
    assert all(type(item) is RunnerSpec for item in call["runner_specs"].values())
    assert call["runner_specs"]["coordinator"].session_id == "session-coordinator"
    assert call["runner_specs"]["coordinator"].session_name == (
        _canonical_session_name("coordinator")
    )
    assert call["runner_specs"]["coordinator"].bound_lane == BOUND_LANE
    assert call["runner_specs"]["coordinator"].participant_id == "coordinator"
    assert call["runner_specs"]["coordinator"].mode == "resume"
    assert call["runner_specs"]["coordinator"].resume is True


@pytest.mark.parametrize("case", ["missing", "duplicate", "extra", "evidence"])
def test_public_start_refuses_bad_body_before_controller(case: str):
    controller = StartController()
    daemon = _start_daemon(controller, profiles=VerifyingProfiles())
    asyncio.run(daemon.start())
    body = _start_body()
    if case == "missing":
        del body["runner_specs"]
    elif case == "duplicate":
        body["coordinator"]["parent_id"] = "unexpected-parent"
    elif case == "extra":
        body["runner_specs"]["coordinator"]["unreviewed_setting"] = True
    else:
        body["evidence"] = {"ready": True, "accepted": True}

    response = asyncio.run(
        daemon.handle_request(_start_request("start-bad-" + case, body))
    )

    assert response["ok"] is False
    assert response["code"] in {"invalid", "unsupported"}
    assert controller.start_calls == []


def test_public_start_requires_opt_in_started_and_profile_verifier():
    body = _start_body()

    not_opted_in = _start_daemon(StartController(), opt_in=False)
    response = asyncio.run(
        not_opted_in.handle_request(_start_request("start-no-opt-in", body))
    )
    assert response["ok"] is False
    assert response["code"] == "unsupported"

    not_started_controller = StartController()
    not_started = _start_daemon(
        not_started_controller, profiles=VerifyingProfiles()
    )
    response = asyncio.run(
        not_started.handle_request(_start_request("start-not-started", body))
    )
    assert response["ok"] is False
    assert response["code"] == "unsupported"
    assert not_started_controller.start_calls == []

    no_verifier_controller = StartController()
    no_verifier = _start_daemon(no_verifier_controller, profiles=FakeProfiles())
    asyncio.run(no_verifier.start())
    response = asyncio.run(
        no_verifier.handle_request(_start_request("start-no-verifier", body))
    )
    assert response["ok"] is False
    assert response["code"] == "unsupported"
    assert no_verifier_controller.start_calls == []


def test_public_start_status_submit_socket_stays_held_without_dispatch(
        tmp_path: Path):
    controller = StartController()
    adapter = StartAdapter()
    daemon = _start_daemon(
        controller, profiles=VerifyingProfiles(), adapter=adapter
    )
    asyncio.run(daemon.start())
    socket_path = tmp_path / "managed-start.sock"
    stop_event = threading.Event()
    served: list[list[dict[str, Any]]] = []
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            served.append(serve_daemon(
                str(socket_path), daemon,
                max_requests=3,
                operation_timeout=1.0,
                stop_event=stop_event,
            ))
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(
        target=serve, name="managed-daemon-start", daemon=True
    )
    thread.start()
    try:
        _wait_for_socket(socket_path, thread)
        start = _send(socket_path, _start_request("socket-start", _start_body()))
        status = _send(socket_path, _request("socket-status"))
        submit = _send(socket_path, {
            "schema": 2,
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "request_id": "socket-submit",
            "lane": LANE,
            "generation": GENERATION,
            "operation": "submit",
            "body": {
                "recipient_id": "coordinator",
                "payload_ref": "payload-held",
                "sender_id": "user",
                "task_id": "task-root",
            },
        })
    finally:
        _stop_server_thread(socket_path, stop_event, thread)

    assert not thread.is_alive()
    assert not errors
    assert start["ok"] is True
    assert start["result"]["phase"] == "ready-held"
    assert status["ok"] is True
    assert status["result"]["live_sdk"] == "UNVERIFIED"
    assert submit["ok"] is True
    assert submit["result"]["state"] == "queued"
    assert submit["result"]["dispatch"] == "held"
    assert controller.start_calls[0]["request_id"] == "socket-start"
    assert controller.submit_calls[0]["generation"] == GENERATION
    assert adapter.dispatches == []
    assert len(controller.loops) == 1
    assert len(served) == 1


def test_public_socket_submit_then_explicit_release_and_dispatch_deduplicates(
        tmp_path: Path):
    state = DurableMailboxState()
    resolver = PayloadResolver()
    adapter = StartAdapter()
    controller = StartController(
        state=state, adapter=adapter, payload_resolver=resolver
    )
    daemon = _start_daemon(
        controller,
        profiles=VerifyingProfiles(),
        adapter=adapter,
        state=state,
    )
    asyncio.run(daemon.start())
    socket_path = tmp_path / "managed-release.sock"
    stop_event = threading.Event()
    served: list[list[dict[str, Any]]] = []
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            served.append(serve_daemon(
                str(socket_path), daemon,
                max_requests=4,
                operation_timeout=1.0,
                stop_event=stop_event,
            ))
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(
        target=serve, name="managed-daemon-release", daemon=True
    )
    thread.start()
    try:
        _wait_for_socket(socket_path, thread)
        start = _send(socket_path, _start_request("socket-start", _start_body()))
        status = _send(socket_path, _request("socket-status"))
        submit = _send(socket_path, {
            "schema": 2,
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "request_id": "socket-submit",
            "lane": LANE,
            "generation": GENERATION,
            "operation": "submit",
            "body": {
                "recipient_id": "coordinator",
                "payload_ref": "file:payload-held",
                "sender_id": "user",
                "task_id": "task-root",
            },
        })
        release = _send(socket_path, {
            "schema": 2,
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "request_id": "socket-release",
            "lane": LANE,
            "generation": GENERATION,
            "operation": "release",
            "body": {"operation_id": start["result"]["operation_id"]},
        })
        sent_before_explicit_pump = list(adapter.dispatches)
    finally:
        _stop_server_thread(socket_path, stop_event, thread)

    pumped = asyncio.run(daemon.dispatch_pump_tick("operation-start"))
    with pytest.raises(DuplicateRelease):
        asyncio.run(controller.release("operation-start", GENERATION))

    assert not thread.is_alive()
    assert not errors
    assert start["ok"] is True
    assert start["result"]["phase"] == "ready-held"
    assert status["ok"] is True
    assert status["result"]["live_sdk"] == "UNVERIFIED"
    assert submit["ok"] is True
    assert submit["result"]["state"] == "queued"
    assert release["ok"] is True
    assert release["result"]["phase"] == "released"
    assert pumped["dispatched"] == []
    assert sent_before_explicit_pump == [{
        "participant_id": "coordinator",
        "message_id": "message-held",
        "payload_ref": "resolved payload text that must not be persisted",
    }]
    assert controller.release_calls == [
        {"operation_id": "operation-start", "generation": GENERATION},
        {"operation_id": "operation-start", "generation": GENERATION},
    ]
    assert controller.dispatch_calls == ["operation-start"]
    assert resolver.calls == ["file:payload-held"]
    assert adapter.dispatches == [{
        "participant_id": "coordinator",
        "message_id": "message-held",
        "payload_ref": "resolved payload text that must not be persisted",
    }]
    assert len(state.persisted_records) == 2
    for record in state.persisted_records:
        assert record["payload_ref"] == "file:payload-held"
        assert record["payload_digest"] == hashlib.sha256(
            b"file:payload-held"
        ).hexdigest()
        encoded = json.dumps(record, sort_keys=True)
        assert "resolved payload text that must not be persisted" not in encoded
        assert "resolved_payload" not in record
        assert "payload_text" not in record
    assert len(served) == 1


class ControllerStore:
    """Durable controller store fake for the public socket acceptance path."""

    def __init__(self) -> None:
        self.documents: dict[str, Any] = {}
        self.journal: list[dict[str, Any]] = []
        self.claims: dict[tuple[str, str], Any] = {}
        self.transcript_calls: list[tuple[str, str, str]] = []
        self.owner = {
            "mode": "managed",
            "lane": BOUND_LANE,
            "generation": GENERATION,
            "daemon_id": "daemon-test",
        }
        self.lineage_claims: list[dict[str, Any]] = []

    @contextlib.contextmanager
    def locked(self, shared: bool = False) -> Iterator["ControllerStore"]:
        del shared
        yield self

    def read_json(self, name: str) -> Any:
        return copy.deepcopy(self.documents.get(name))

    def write_json(self, name: str, value: Any) -> Any:
        self.documents[name] = copy.deepcopy(value)
        return value

    def append_journal(self, name: str, value: Any) -> Any:
        self.journal.append({"name": name, "value": copy.deepcopy(value)})
        return value

    def read_owner(self) -> dict[str, Any]:
        return copy.deepcopy(self.owner)

    def read_lineage_claims(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.lineage_claims)

    def claim_lineage(self, lineage_id: str, **values: Any) -> dict[str, Any]:
        claim = {
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "record_kind": "workspace-claim",
            "claim_kind": "workspace",
            "lineage_id": lineage_id,
            "owner_generation": values["owner_generation"],
            "lineage_generation": values["lineage_generation"],
            "lane": BOUND_LANE,
            "lane_key": BOUND_LANE.casefold(),
            "host": "test-host",
            "coordinator_session_uuid": values["coordinator_session_uuid"],
            "workspace": values.get("workspace", "/managed/workspace"),
            "common_dir": values.get("common_dir", "/managed/workspace"),
            "repository": values.get("repository", "/managed/workspace"),
            "state": "active",
            "parent_read_only": values["parent_read_only"],
            "claimed_at": 1700000000.0,
        }
        self.lineage_claims.append(copy.deepcopy(claim))
        return copy.deepcopy(claim)

    def claim_writer(self, participant_id: str, worktree: Any,
                     repository: Any = None) -> dict[str, Any]:
        key = (participant_id, str(worktree))
        if key in self.claims:
            raise ControllerError("ownership-conflict", "writer claim is already held")
        self.claims[key] = {
            "participant_id": participant_id,
            "worktree": str(worktree),
            "repository": None if repository is None else str(repository),
        }
        return {"state": "active", "lane": BOUND_LANE}

    def release_writer(self, participant_id: str, worktree: Any) -> dict[str, Any]:
        key = (participant_id, str(worktree))
        self.claims.pop(key, None)
        return {"state": "released"}

    def verify_transcript(self, profile_name: str, session_id: str,
                          workspace: str) -> dict[str, Any]:
        self.transcript_calls.append((profile_name, session_id, str(workspace)))
        return {
            "profile": {
                "name": "team-a",
                "email": "a@example.invalid",
                "family": "family-a",
                "config_dir": "/managed/profiles/team-a",
            },
            "session_id": session_id,
            "workspace": str(workspace),
            "transcript_store": "/managed/transcripts",
            "transcript_project": "/managed/transcripts/workspace",
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


class CanonicalRuntime:
    """Exact async adapter boundary used by the real controller."""

    _PIDS = {"coordinator": 5101, "worker-a": 5102, "worker-b": 5103}
    _PROCESS_GROUP_IDS = {
        "coordinator": 6101,
        "worker-a": 6102,
        "worker-b": 6103,
    }

    def __init__(self) -> None:
        self.opened: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[Any, ...]] = []
        self.sent: list[tuple[str, str, str]] = []
        self.released: list[str] = []

    @staticmethod
    def preflight_held_swap(
            spec: Mapping[str, Any], evidence_record: Any,
    ) -> dict[str, Any]:
        del spec, evidence_record
        # Synthetic routing evidence for this daemon acceptance fixture.  The
        # controller still requires and records the live capability gate; this
        # fake does not claim support for an independent child runner.
        return {
            "verdict": "verified",
            "reason_code": "synthetic-test-control",
            "reason": "injected unit-test runtime only",
            "identity_digest": "a" * 64,
            "evidence_reference": "fixture://synthetic-controller-runtime",
        }

    @staticmethod
    def _evidence(participant_id: str, session_id: str,
                  runner_instance_id: str, *, released: bool,
                  fingerprint: Mapping[str, Any]) -> dict[str, Any]:
        assert fingerprint["session_name"] == _canonical_session_name(participant_id)
        assert fingerprint["bound_lane"] == BOUND_LANE
        return {
            "participant_id": participant_id,
            "session_id": session_id,
            "runner_instance_id": runner_instance_id,
            "ready": True,
            "released": released,
            "active_turn": False,
            "turn_terminal": True,
            "drained": True,
            "participant_quiescent": True,
            "quiescent": True,
            "tools_quiescent": True,
            "tools": [],
            "uncertain_effects": [],
            "uncertain_effects_overflow": False,
            "process": {
                "pid": CanonicalRuntime._PIDS[participant_id],
                "process_group_id": CanonicalRuntime._PROCESS_GROUP_IDS[participant_id],
                "process_start_token": "start-" + participant_id,
                "process_group_owned": True,
                "exited": False,
                "group_excluded": False,
            },
            "initialization": {
                "account_email": "a@example.invalid",
                "permission_mode": "default",
                "model": "model-a",
                "fingerprint": dict(fingerprint),
            },
        }

    async def open(self, participant_id: str,
                   spec: Mapping[str, Any]) -> dict[str, Any]:
        self.calls.append(("open", participant_id))
        session_id = str(spec["session_id"])
        runner_instance_id = "runner-" + participant_id
        result = {
            "participant_id": participant_id,
            "session_id": session_id,
            "runner_instance_id": runner_instance_id,
            "evidence": self._evidence(
                participant_id, session_id, runner_instance_id,
                released=False, fingerprint=spec["fingerprint"],
            ),
        }
        self.opened[participant_id] = result
        return copy.deepcopy(result)

    async def release(self, participant_id: str) -> dict[str, Any]:
        self.calls.append(("release", participant_id))
        self.released.append(participant_id)
        current = copy.deepcopy(self.opened[participant_id])
        current["evidence"]["released"] = True
        return current

    async def status(self, participant_id: str) -> dict[str, Any]:
        opened = self.opened[participant_id]
        released = participant_id in self.released
        evidence = self._evidence(
            participant_id,
            str(opened["session_id"]),
            str(opened["runner_instance_id"]),
            released=released,
            fingerprint=opened["evidence"]["initialization"]["fingerprint"],
        )
        return {
            "participant_id": participant_id,
            "session_id": opened["session_id"],
            "runner_instance_id": opened["runner_instance_id"],
            "evidence": evidence,
        }

    async def send(self, participant_id: str, message_id: str,
                   payload: str) -> dict[str, Any]:
        self.calls.append(("send", participant_id, message_id, payload))
        self.sent.append((participant_id, message_id, payload))
        return {
            "participant_id": participant_id,
            "message_id": message_id,
            "accepted": True,
            "ack_kind": "accepted-send",
        }


class RecordingResolver:
    """Canonical payload resolver injected only at the send boundary."""

    def __init__(self) -> None:
        self.refs: list[str] = []

    def __call__(self, payload_ref: str) -> str:
        self.refs.append(payload_ref)
        return "resolved private payload text"


class DispatchRuntime(CanonicalRuntime):
    """Fake adapter with per-recipient readiness and send fault controls."""

    def __init__(self) -> None:
        super().__init__()
        self.turn_state = {
            "coordinator": "idle",
        }
        self.status_calls: list[str] = []
        self.send_attempts: list[tuple[str, str]] = []
        self.send_started: asyncio.Event | None = None
        self.send_release: asyncio.Event | None = None
        self.fail_after_send = False

    async def status(self, participant_id: str) -> dict[str, Any]:
        self.status_calls.append(participant_id)
        opened = self.opened[participant_id]
        evidence = self._evidence(
            participant_id,
            str(opened["session_id"]),
            str(opened["runner_instance_id"]),
            released=True,
            fingerprint=opened["evidence"]["initialization"]["fingerprint"],
        )
        busy = self.turn_state[participant_id] == "busy"
        evidence.update({
            "active_turn": busy,
            "turn_terminal": not busy,
            "drained": not busy,
            "participant_quiescent": not busy,
            "quiescent": not busy,
        })
        return {
            "participant_id": participant_id,
            "session_id": opened["session_id"],
            "runner_instance_id": opened["runner_instance_id"],
            "evidence": evidence,
        }

    async def send(self, participant_id: str, message_id: str,
                   payload: str) -> dict[str, Any]:
        self.send_attempts.append((participant_id, message_id))
        if self.send_started is not None:
            self.send_started.set()
        if self.send_release is not None:
            await self.send_release.wait()
        if self.fail_after_send:
            self.sent.append((participant_id, message_id, payload))
            raise RuntimeError("acknowledgement was lost")
        return await super().send(participant_id, message_id, payload)


class LockingControllerStore(ControllerStore):
    """Durable fake that makes a lock held across an await observable."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self.lock_entered = threading.Event()

    @contextlib.contextmanager
    def locked(self, shared: bool = False) -> Iterator["LockingControllerStore"]:
        del shared
        with self._lock:
            self.lock_entered.set()
            yield self


def _wrap_start_for_diagnostics(controller: ManagedController) -> dict[str, Any]:
    """Capture the real controller refusal before the daemon wire redacts it."""
    original = controller.start
    observation: dict[str, Any] = {"calls": 0, "errors": []}

    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        observation["calls"] += 1
        try:
            return await original(*args, **kwargs)
        except ControllerError as error:
            observation["errors"].append({
                "code": error.code,
                "message": error.message,
            })
            raise

    setattr(controller, "start", wrapped)
    return observation


async def _start_real_dispatch_controller(
        runtime: DispatchRuntime | None = None,
        store: ControllerStore | None = None,
        request_id: str = "dispatch-start") -> tuple[
            ControllerStore, DispatchRuntime, ManagedController, ManagedDaemon, str]:
    selected_runtime = DispatchRuntime() if runtime is None else runtime
    selected_store = ControllerStore() if store is None else store
    resolver = RecordingResolver()
    controller = ManagedController(
        selected_store,
        runtime=selected_runtime,
        payload_resolver=resolver,
        transcript_verifier=selected_store.verify_transcript,
        clock=lambda: 1000.0,
    )
    start_observation = _wrap_start_for_diagnostics(controller)
    daemon = ManagedDaemon(
        state=FakeState(),
        profiles=VerifyingProfiles(),
        controller=controller,
        adapter=selected_runtime,
        daemon_id="daemon-test",
        opt_in=True,
    )
    await daemon.start()
    response = await daemon.handle_request(
        _start_request(request_id, _start_body())
    )
    assert response["ok"] is True, json.dumps({
        "response": response,
        "controller_start": start_observation,
    }, sort_keys=True)
    assert response["result"]["phase"] == "ready-held"
    return (
        selected_store,
        selected_runtime,
        controller,
        daemon,
        response["result"]["operation_id"],
    )


def _journal_events(store: ControllerStore) -> list[dict[str, Any]]:
    return [
        record["value"]
        for record in store.journal
        if isinstance(record.get("value"), Mapping)
    ]


def test_real_native_start_refuses_mixed_roster_without_open_admission_or_delivery():
    """Independent child runners cannot be smuggled into native startup."""

    async def scenario() -> None:
        store = ControllerStore()
        runtime = DispatchRuntime()
        controller = ManagedController(
            store,
            runtime=runtime,
            payload_resolver=RecordingResolver(),
            transcript_verifier=store.verify_transcript,
            clock=lambda: 1000.0,
        )
        start_observation = _wrap_start_for_diagnostics(controller)
        daemon = ManagedDaemon(
            state=FakeState(),
            profiles=VerifyingProfiles(),
            controller=controller,
            adapter=runtime,
            daemon_id="daemon-test",
            opt_in=True,
        )
        await daemon.start()
        mixed = _native_start_body()
        independent = _independent_start_body()
        mixed["participants"] = [independent["participants"][0]]
        mixed["runner_specs"]["worker-a"] = independent["runner_specs"]["worker-a"]

        response = await daemon.handle_request(
            _start_request("mixed-native-roster", mixed)
        )

        diagnostic = json.dumps({
            "response": response,
            "controller_start": start_observation,
        }, sort_keys=True)
        assert response["ok"] is False, diagnostic
        assert response["code"] == "migration-required", diagnostic
        assert not any(call[0] == "open" for call in runtime.calls)
        assert runtime.sent == []
        assert controller._native_context is None

    asyncio.run(scenario())


def test_real_controller_coordinator_busy_then_idle_dispatches_once_after_release():
    """The daemon pump waits for coordinator idle and never opens a child."""

    async def scenario() -> None:
        store, runtime, controller, daemon, operation_id = (
            await _start_real_dispatch_controller()
        )
        released = await controller.release(operation_id, GENERATION)
        assert released.phase == "released"
        runtime.turn_state["coordinator"] = "busy"

        queued = controller.submit(
            "dispatch-coordinator", "coordinator", "payload-coordinator",
            generation=GENERATION,
        )
        assert queued.state == "queued"
        assert any(
            item["message_id"] == queued.message_id
            for item in controller.dispatch_candidates(operation_id)
        )
        busy_status = await runtime.status("coordinator")
        assert busy_status["evidence"]["active_turn"] is True

        # Exercise the actual daemon pump while the coordinator is busy.  A
        # readiness observation alone is not a dispatch guard: this pump must
        # leave both transport and durable dispatch intent untouched.
        busy_pump = await daemon.dispatch_pump_tick(operation_id)
        assert busy_pump["dispatched"] == []
        assert busy_pump["skipped"] == [{
            "recipient_id": "coordinator",
            "message_id": queued.message_id,
            "code": "busy",
            "reason": "status-not-idle",
        }]
        assert runtime.sent == []
        assert not any(
            event.get("event") == "dispatch-intent"
            and event.get("message_id") == queued.message_id
            for event in _journal_events(store)
        )

        # A child-directed request is not a second delivery target or a
        # mailbox: the durable coordinator roster refuses it before runtime.
        with pytest.raises(ControllerError) as child:
            controller.submit(
                "dispatch-child-invalid", "agent-native-1", "payload-child",
                generation=GENERATION,
            )
        assert child.value.code == "unknown"
        assert runtime.sent == []

        runtime.turn_state["coordinator"] = "idle"
        status = await runtime.status("coordinator")
        assert status["evidence"]["turn_terminal"] is True
        idle_pump = await daemon.dispatch_pump_tick(operation_id)
        assert len(idle_pump["dispatched"]) == 1
        assert runtime.sent == [
            ("coordinator", queued.message_id, "resolved private payload text"),
        ]
        native_context = controller.status()["native_context"]
        assert isinstance(native_context, Mapping)
        assert native_context["lineage"]["lineage_id"] == "daemon-native-lineage"
        assert native_context["lineage"]["owner_generation"] == GENERATION
        assert native_context["runner_incarnation"] == "runner-coordinator"
        assert native_context["invocation_id"] == queued.message_id
        assert native_context["definitions"]["writer"]["digest"]
        durable_context = store.documents["controller.json"]["native_context"]
        assert durable_context == native_context
        second_pump = await daemon.dispatch_pump_tick(operation_id)
        assert second_pump["dispatched"] == []
        assert len(runtime.send_attempts) == 1

    asyncio.run(scenario())


def test_real_controller_uncertain_dispatch_is_not_replayed_automatically():
    """A send without a correlated ack stays uncertain and is never resent."""

    async def scenario() -> None:
        store, runtime, controller, _daemon_instance, operation_id = (
            await _start_real_dispatch_controller()
        )
        await controller.release(operation_id, GENERATION)
        runtime.fail_after_send = True
        entry = controller.submit(
            "dispatch-uncertain", "coordinator", "payload-uncertain",
            generation=GENERATION,
        )

        with pytest.raises(ControllerError) as raised:
            await controller.dispatch_next(
                operation_id, recipient_id="coordinator"
            )
        assert raised.value.code == "uncertain-effect"
        assert runtime.send_attempts == [("coordinator", entry.message_id)]
        mailbox = next(
            item for item in controller.status()["mailboxes"]
            if item["message_id"] == entry.message_id
        )
        assert mailbox["state"] == "uncertain"
        assert controller.dispatch_candidates(operation_id) == []

        with pytest.raises(ControllerError) as replay:
            await controller.dispatch_next(
                operation_id, recipient_id="coordinator"
            )
        assert replay.value.code == "uncertain-effect"
        assert runtime.send_attempts == [("coordinator", entry.message_id)]
        assert not any(
            event.get("event") == "dispatch-intent"
            and event.get("message_id") == entry.message_id
            and event.get("attempt", 0) > 1
            for event in _journal_events(store)
        )

    asyncio.run(scenario())


def test_real_controller_stale_generation_after_await_fence_blocks_send():
    """A coordinator fence after payload await blocks the runtime boundary."""

    async def scenario() -> None:
        store, runtime, controller, _daemon_instance, operation_id = (
            await _start_real_dispatch_controller()
        )
        await controller.release(operation_id, GENERATION)
        resolver_started = asyncio.Event()
        allow_resolver = asyncio.Event()

        async def delayed_resolver(payload_ref: str) -> str:
            assert payload_ref == "payload-held"
            resolver_started.set()
            await allow_resolver.wait()
            return "resolved private payload text"

        controller.payload_resolver = delayed_resolver
        entry = controller.submit(
            "dispatch-held", "coordinator", "payload-held",
            generation=GENERATION,
        )
        candidates = controller.dispatch_candidates(operation_id)
        assert any(item["message_id"] == entry.message_id for item in candidates)

        dispatch_task = asyncio.create_task(
            controller.dispatch_next(operation_id, recipient_id="coordinator")
        )
        await asyncio.wait_for(resolver_started.wait(), timeout=0.5)

        # Model the durable fence that arrives after the payload await but
        # before the final runtime send admission transaction.
        with controller._transaction():
            operation = controller._operations[operation_id]
            operation.phase = "paused"
            controller._persist({
                "event": "test-concurrent-fence",
                "operation_id": operation_id,
            })

        allow_resolver.set()
        with pytest.raises(ControllerError) as raised:
            await dispatch_task
        assert raised.value.code in {"busy", "stale-generation", "uncertain-effect"}
        assert runtime.sent == []
        assert any(
            event.get("event") == "dispatch-intent"
            and event.get("message_id") == entry.message_id
            for event in _journal_events(store)
        )

    asyncio.run(scenario())


def test_real_controller_dispatch_releases_store_lock_before_runtime_await():
    """Status/reconciliation can acquire the durable lock while send awaits."""

    async def scenario() -> None:
        store = LockingControllerStore()
        runtime = DispatchRuntime()
        runtime.send_started = asyncio.Event()
        runtime.send_release = asyncio.Event()
        _store, _runtime, controller, _daemon_instance, operation_id = (
            await _start_real_dispatch_controller(runtime=runtime, store=store)
        )
        await controller.release(operation_id, GENERATION)
        entry = controller.submit(
            "dispatch-lock", "coordinator", "payload-lock",
            generation=GENERATION,
        )
        dispatch_task = asyncio.create_task(
            controller.dispatch_next(operation_id, recipient_id="coordinator")
        )
        await asyncio.wait_for(runtime.send_started.wait(), timeout=0.5)

        store.lock_entered.clear()
        status_task = asyncio.create_task(asyncio.to_thread(controller.status))
        try:
            acquired = await asyncio.to_thread(store.lock_entered.wait, 0.5)
            assert acquired is True
            status = await asyncio.wait_for(status_task, timeout=0.5)
            assert status["operation_id"] == operation_id
        finally:
            runtime.send_release.set()
        acknowledged = await dispatch_task
        assert acknowledged.message_id == entry.message_id
        assert runtime.send_attempts == [("coordinator", entry.message_id)]

    asyncio.run(scenario())


def _load_cli_api() -> dict[str, Any]:
    script = Path(__file__).resolve().parents[1] / "lane-managed"
    return runpy.run_path(str(script), run_name="lane_managed_daemon_e2e")


def test_public_cli_socket_uses_real_controller_for_held_release_and_one_ack(
        tmp_path: Path):
    """The public CLI client must exercise the real durable controller seam."""
    store = ControllerStore()
    runtime = CanonicalRuntime()
    resolver = RecordingResolver()
    controller = ManagedController(
        store,
        runtime=runtime,
        payload_resolver=resolver,
        transcript_verifier=store.verify_transcript,
        clock=lambda: 1000.0,
    )
    daemon = ManagedDaemon(
        state=FakeState(),
        profiles=VerifyingProfiles(),
        controller=controller,
        adapter=runtime,
        daemon_id="daemon-test",
        opt_in=True,
    )
    asyncio.run(daemon.start())
    api = _load_cli_api()
    socket_path = tmp_path / "real-controller.sock"
    stop_event = threading.Event()
    served: list[list[dict[str, Any]]] = []
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            served.append(serve_daemon(
                str(socket_path), daemon,
                max_requests=4,
                operation_timeout=2.0,
                stop_event=stop_event,
            ))
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(
        target=serve, name="managed-real-controller", daemon=True
    )
    thread.start()
    try:
        _wait_for_socket(socket_path, thread)

        def request(request_id: str, operation: str,
                    body: Mapping[str, Any]) -> dict[str, Any]:
            return api["request_socket"](
                str(socket_path), {
                    "schema": 2,
                    "schema_version": 2,
                    "architecture": "native-coordinator-lineage",
                    "request_id": request_id,
                    "lane": LANE,
                    "generation": GENERATION,
                    "operation": operation,
                    "body": dict(body),
                },
                connect_timeout=0.5,
                operation_timeout=2.0,
            )

        start = request("real-start", "start", _start_body())
        assert start["ok"] is True, json.dumps(start, sort_keys=True)
        status = request("real-status", "status", {})
        submit = request("real-submit", "submit", {
            "recipient_id": "coordinator",
            "payload_ref": "file:payload-real",
            "sender_id": "user",
            "task_id": "task-root",
        })
        assert submit["ok"] is True
        assert submit["result"]["state"] == "fenced"
        assert runtime.sent == []
        release = request("real-release", "release", {
            "operation_id": start["result"]["operation_id"],
        })
        sent_before_explicit_pump = list(runtime.sent)
    finally:
        _stop_server_thread(socket_path, stop_event, thread)

    explicit_pump = asyncio.run(
        daemon.dispatch_pump_tick(start["result"]["operation_id"])
    )
    with pytest.raises(ControllerError) as duplicate:
        asyncio.run(
            controller.release(start["result"]["operation_id"], GENERATION)
        )

    assert not thread.is_alive()
    assert not errors
    assert start["ok"] is True
    assert start["result"]["phase"] == "ready-held"
    assert status["ok"] is True
    assert {
        item["participant_id"] for item in status["result"]["participants"]
    } == {"coordinator"}
    assert status["result"]["live_sdk"] == "UNVERIFIED"
    assert release["ok"] is True
    assert release["result"]["phase"] == "released"
    assert sent_before_explicit_pump == [
        ("coordinator", submit["result"]["message_id"],
         "resolved private payload text"),
    ]
    assert explicit_pump["dispatched"] == []
    assert duplicate.value.code == "busy"
    assert resolver.refs == ["file:payload-real"]
    assert runtime.sent == [
        ("coordinator", submit["result"]["message_id"],
         "resolved private payload text"),
    ]
    assert len(runtime.sent) == 1
    assert len([call for call in runtime.calls if call[0] == "send"]) == 1
    assert all(
        "resolved private payload text" not in json.dumps(record, sort_keys=True)
        for record in store.documents.values()
    )
    controller_record = store.documents["controller.json"]
    encoded_record = json.dumps(controller_record, sort_keys=True)
    assert "resolved private payload text" not in encoded_record
    mailbox = controller_record["mailboxes"][0]
    assert mailbox["payload_ref"] == "file:payload-real"
    request_record = controller_record["requests"]["real-submit"]
    assert request_record["kind"] == "submit"
    assert request_record["result"]["message_id"] == mailbox["message_id"]
    canonical_submit = json.dumps(
        {
            "recipient_id": "coordinator",
            "payload_ref": "file:payload-real",
            "sender_id": "user",
            "task_id": "task-root",
            "generation": GENERATION,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    assert request_record["digest"] == hashlib.sha256(
        canonical_submit
    ).hexdigest()
    assert mailbox["payload_ref"] != "resolved private payload text"
    assert len(served) == 1


@pytest.mark.skipif(os.name == "nt", reason="private file modes require POSIX")
def test_production_file_payload_resolver_accepts_private_owner_regular_file(
        tmp_path: Path):
    payload = tmp_path / "payload.txt"
    payload.write_text("payload from private file", encoding="utf-8")
    payload.chmod(0o600)

    assert resolve_payload_reference("file:" + str(payload)) == (
        "payload from private file"
    )


@pytest.mark.skipif(os.name == "nt", reason="private file modes require POSIX")
@pytest.mark.parametrize("case", [
    "symlink", "world-readable", "nonfile", "non-utf8", "oversize", "scheme",
])
def test_production_file_payload_resolver_refuses_before_any_send(
        tmp_path: Path, case: str):
    target = tmp_path / "target.txt"
    target.write_text("private payload", encoding="utf-8")
    target.chmod(0o600)
    if case == "symlink":
        path = tmp_path / "payload-link.txt"
        path.symlink_to(target)
        reference = "file:" + str(path)
    elif case == "world-readable":
        target.chmod(0o644)
        reference = "file:" + str(target)
    elif case == "nonfile":
        directory = tmp_path / "payload-directory"
        directory.mkdir()
        reference = "file:" + str(directory)
    elif case == "non-utf8":
        target.write_bytes(b"\xff\xfe\xfa")
        target.chmod(0o600)
        reference = "file:" + str(target)
    elif case == "oversize":
        target.write_bytes(b"x" * (1024 * 1024 + 1))
        target.chmod(0o600)
        reference = "file:" + str(target)
    else:
        reference = "https://example.invalid/payload"

    sends: list[str] = []
    with pytest.raises(Exception) as raised:
        resolved = resolve_payload_reference(reference)
        sends.append(resolved)

    assert sends == []
    assert getattr(raised.value, "code", "unknown") in {
        "invalid", "unknown", "unsupported", "ownership-conflict",
    }


@pytest.mark.skipif(os.name == "nt", reason="POSIX nonregular files required")
@pytest.mark.parametrize("kind", ["fifo", "socket"])
def test_production_payload_resolver_refuses_nonregular_without_hanging(
        tmp_path: Path, kind: str):
    path = tmp_path / ("payload.fifo" if kind == "fifo" else "payload.sock")
    listener: socket.socket | None = None
    if kind == "fifo":
        os.mkfifo(path)
    else:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(path))

    errors: list[BaseException] = []

    def resolve() -> None:
        try:
            resolve_payload_reference("file:" + str(path))
        except BaseException as error:  # pragma: no cover - assertion below
            errors.append(error)

    worker = threading.Thread(target=resolve, daemon=True)
    worker.start()
    worker.join(timeout=0.5)
    if listener is not None:
        listener.close()

    assert not worker.is_alive(), "%s resolution hung" % kind
    assert len(errors) == 1
    assert getattr(errors[0], "code", "unknown") == "invalid"


class SupervisorState(FakeState):
    """Durable owner/runtime fake for supervisor ordering and retention."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, Any]] = []
        self.runtime: dict[str, Any] | None = None

    def enroll_managed(
            self, daemon_id: str, process_domain: str | None = None
    ) -> dict[str, Any]:
        self.events.append(("enroll", daemon_id))
        return super().enroll_managed(daemon_id, process_domain)

    def register_runtime(self, **record: Any) -> dict[str, Any]:
        self.events.append(("register", dict(record)))
        self.runtime = dict(record)
        return dict(record)

    def clear_runtime(self, **identity: Any) -> dict[str, Any]:
        self.events.append(("clear", dict(identity)))
        assert self.runtime is not None
        assert identity == {
        "daemon_id": self.runtime["daemon_id"],
        "generation": self.runtime["generation"],
        "pid": self.runtime["pid"],
        "start_token": self.runtime["start_token"],
        "pgid": self.runtime["pgid"],
        "process_domain": self.runtime["process_domain"],
        }
        self.runtime = None
        return {"cleared": True}


class SupervisorProjection:
    """Explicit projection seam for supervisor ordering tests."""

    def preflight(self, context: Mapping[str, Any]) -> dict[str, Any]:
        return {"preflight": True, **dict(context)}

    def managed_owner(self, context: Mapping[str, Any]) -> dict[str, Any]:
        return {"projected": True, **dict(context)}


def _patch_supervisor_seams(monkeypatch: pytest.MonkeyPatch,
                            state: SupervisorState,
                            *, crash: bool,
                            expected_max_requests: int | None = None) -> None:
    monkeypatch.setattr(
        "lane_managed_daemon._current_process_identity",
        lambda: (4242, "process-start-token", 4243),
    )

    def construct(self: ManagedDaemon) -> None:
        state.events.append(("construct-dependencies", None))
        self.profiles = VerifyingProfiles()
        self.adapter = FakeAdapter()
        self.controller = FakeController()

    monkeypatch.setattr(ManagedDaemon, "_construct_dependencies", construct)

    def serve(socket_path: str, handler: Any, **kwargs: Any) -> list[dict[str, Any]]:
        del socket_path
        on_ready = kwargs.pop("on_ready", None)
        assert callable(on_ready)
        on_ready()
        assert kwargs == {
            "connect_timeout": 5.0,
            "operation_timeout": 120.0,
            "max_bytes": 1024 * 1024,
            "max_requests": expected_max_requests,
            "stop_event": None,
        }
        state.events.append(("serve", None))
        if crash:
            raise RuntimeError("transport crashed")
        response = asyncio.run(handler(_request("supervisor-status")))
        assert response["ok"] is True
        return [response]

    monkeypatch.setattr("lane_managed_daemon.serve_daemon", serve)


def test_run_supervisor_registers_runtime_before_dependencies_and_clears_exactly(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    state = SupervisorState()
    _patch_supervisor_seams(
        monkeypatch, state, crash=False, expected_max_requests=1
    )

    result = run_supervisor(
        LANE, str(tmp_path / "managed.sock"), "daemon-test", True,
        state=state, projection=SupervisorProjection(), max_requests=1,
    )

    assert result[0]["request_id"] == "supervisor-status"
    names = [event[0] for event in state.events]
    assert names.index("register") < names.index("construct-dependencies")
    assert names.index("register") < names.index("serve")
    assert names[-1] == "clear"
    register = next(event[1] for event in state.events if event[0] == "register")
    clear = next(event[1] for event in state.events if event[0] == "clear")
    assert register == {
        "daemon_id": "daemon-test",
        "generation": GENERATION,
        "pid": 4242,
        "start_token": "process-start-token",
        "pgid": 4243,
        "process_domain": _current_process_domain(),
        "socket_path": str(tmp_path / "managed.sock"),
    }
    assert clear == {
        "daemon_id": "daemon-test",
        "generation": GENERATION,
        "pid": 4242,
        "start_token": "process-start-token",
        "pgid": 4243,
        "process_domain": _current_process_domain(),
    }
    assert state.runtime is None


def test_run_supervisor_retains_runtime_when_transport_raises(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    state = SupervisorState()
    _patch_supervisor_seams(monkeypatch, state, crash=True)

    with pytest.raises(RuntimeError, match="transport crashed"):
        run_supervisor(
            LANE, str(tmp_path / "managed.sock"), "daemon-test", True,
            state=state, projection=SupervisorProjection(),
        )

    assert [event[0] for event in state.events] == [
        "enroll", "register", "serve",
    ]
    assert state.runtime == {
        "daemon_id": "daemon-test",
        "generation": GENERATION,
        "pid": 4242,
        "start_token": "process-start-token",
        "pgid": 4243,
        "process_domain": _current_process_domain(),
        "socket_path": str(tmp_path / "managed.sock"),
    }
