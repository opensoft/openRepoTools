# SPDX-License-Identifier: Apache-2.0
"""Schema-v2 tests for the managed native-lineage daemon boundary.

These tests deliberately stop at the public daemon/socket seam.  The fakes do
not start Claude, read credentials, or create a second child owner.  Durable
records from the superseded independent-runner prototype are refusal inputs,
not migration fixtures.
"""

from __future__ import annotations

import asyncio
import copy
import json
import socket
import threading
import time
from pathlib import Path
from typing import Any, Mapping

import pytest

from lane_managed_daemon import (
    NATIVE_ADMISSION_OPERATION,
    DaemonError,
    ManagedDaemon,
    serve_daemon,
)


LANE = "build"
GENERATION = 7
SCHEMA_VERSION = 2
ARCHITECTURE = "native-coordinator-lineage"
SCHEMA_REFUSALS = {"schema-mismatch", "migration-required"}


def _request(
    request_id: str,
    *,
    operation: str = "status",
    body: Mapping[str, Any] | None = None,
    schema: int = SCHEMA_VERSION,
    schema_version: int = SCHEMA_VERSION,
    architecture: str = ARCHITECTURE,
) -> dict[str, Any]:
    """Build one canonical v2 request without compatibility aliases."""
    return {
        "schema": schema,
        "schema_version": schema_version,
        "architecture": architecture,
        "request_id": request_id,
        "lane": LANE,
        "generation": GENERATION,
        "operation": operation,
        "body": dict(body or {}),
    }


def _native_owner() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "architecture": ARCHITECTURE,
        "record_kind": "owner",
        "mode": "managed",
        "lane": LANE,
        "generation": GENERATION,
        "daemon_id": "daemon-test",
    }


class RecordingState:
    """Small state authority used to prove refusal paths are non-mutating."""

    def __init__(self, owner: Mapping[str, Any]) -> None:
        self.owner = copy.deepcopy(dict(owner))
        self.calls: list[str] = []

    def read_owner(self, **_kwargs: Any) -> dict[str, Any]:
        self.calls.append("read_owner")
        return copy.deepcopy(self.owner)

    def discover_owner(self, lane: str) -> dict[str, Any]:
        self.calls.append("discover_owner")
        assert lane == LANE
        return copy.deepcopy(self.owner)

    def enroll_managed(self, daemon_id: str, **_kwargs: Any) -> dict[str, Any]:
        self.calls.append("enroll_managed")
        assert daemon_id == "daemon-test"
        return copy.deepcopy(self.owner)


class LegacyState(RecordingState):
    """An old record must be preserved, never normalized into native state."""

    def enroll_managed(self, daemon_id: str, **_kwargs: Any) -> dict[str, Any]:
        self.calls.append("enroll_managed")
        assert daemon_id == "daemon-test"
        raise DaemonError("schema-mismatch", "migration-required")


class Profiles:
    """Credential-free profile seam required by daemon startup."""

    def resolve(self, name: str) -> dict[str, str]:
        assert name == "team-a"
        return {
            "name": "team-a",
            "email": "a@example.invalid",
            "family": "family-a",
        }

    def verify_transcript(
        self, profile: Any, session_id: str, workspace: str
    ) -> dict[str, Any]:
        return {
            "profile": profile,
            "session_id": session_id,
            "workspace": workspace,
            "transcript_store": "/private/fake/store",
            "transcript_project": "/private/fake/project",
            "transcript": {},
            "holders": [],
            "unknown_holders": [],
            "ambiguous": False,
            "native_children": [],
            "child_transcript_stores": [],
            "runtime_capabilities": {},
        }


class Adapter:
    """Marker adapter; no SDK import or runtime operation is allowed."""


class StatusController:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.loops: list[asyncio.AbstractEventLoop] = []

    async def status(self) -> dict[str, Any]:
        self.calls.append("status")
        self.loops.append(asyncio.get_running_loop())
        return {
            "schema_version": SCHEMA_VERSION,
            "architecture": ARCHITECTURE,
            "lane": LANE,
            "generation": GENERATION,
            "phase": "ready-held",
            "coordinator": {"lineage": "native-coordinator"},
            "native_children": [],
            "uncertainty": [],
        }


class ReleaseController(StatusController):
    async def release(self, *_args: Any, **_kwargs: Any) -> Any:
        self.calls.append("release")
        raise DaemonError("uncertain-effect", "accepted send has no native event")

    def dispatch_candidates(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def dispatch_next(self, *_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("uncertain release must not reach dispatch")


def _daemon(
    state: RecordingState | None = None,
    controller: Any | None = None,
) -> ManagedDaemon:
    return ManagedDaemon(
        state=state or RecordingState(_native_owner()),
        profiles=Profiles(),
        controller=controller or StatusController(),
        adapter=Adapter(),
        daemon_id="daemon-test",
        opt_in=True,
        lane=LANE,
    )


async def _started_daemon(
    state: RecordingState | None = None,
    controller: Any | None = None,
) -> ManagedDaemon:
    daemon = _daemon(state, controller)
    await daemon.start()
    return daemon


def _read_response(client: socket.socket) -> dict[str, Any]:
    chunks: list[bytes] = []
    while True:
        chunk = client.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    return json.loads(b"".join(chunks).split(b"\n", 1)[0].decode("utf-8"))


def _send(socket_path: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.dumps(dict(request), sort_keys=True, separators=(",", ":"))
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3.0)
        client.connect(str(socket_path))
        client.sendall(payload.encode("utf-8") + b"\n")
        return _read_response(client)


def _wait_for_socket(socket_path: Path, thread: threading.Thread) -> None:
    deadline = time.monotonic() + 3.0
    while not socket_path.exists() and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert socket_path.exists(), "managed daemon did not bind its socket"


def _stop_server(
    socket_path: Path,
    stop_event: threading.Event,
    thread: threading.Thread,
) -> None:
    stop_event.set()
    # The transport checks stop_event between accepts; wake it if it is
    # currently waiting for a client.  This is test cleanup, not a protocol
    # operation.
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.2)
            client.connect(str(socket_path))
    except OSError:
        pass
    thread.join(timeout=3.0)
    assert not thread.is_alive(), "managed daemon transport did not stop"


def test_v2_status_routes_one_native_lineage_and_echoes_wire_identity() -> None:
    controller = StatusController()
    daemon = asyncio.run(_started_daemon(controller=controller))

    response = asyncio.run(daemon.handle_request(_request("status-direct")))

    assert response["schema"] == SCHEMA_VERSION
    assert response["schema_version"] == SCHEMA_VERSION
    assert response["architecture"] == ARCHITECTURE
    assert response["request_id"] == "status-direct"
    assert response["generation"] == GENERATION
    assert response["ok"] is True
    assert response["result"]["phase"] == "ready-held"
    assert response["result"]["architecture"] == ARCHITECTURE
    assert controller.calls == ["status"]
    assert len(controller.loops) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"schema": 1, "schema_version": 1},
        {"schema_version": 1},
        {"architecture": "independent-worker-mailbox"},
    ],
)
def test_old_or_unknown_wire_is_refused_before_controller_or_state_mutation(
    changes: Mapping[str, Any],
) -> None:
    state = RecordingState(_native_owner())
    controller = StatusController()
    daemon = asyncio.run(_started_daemon(state, controller))
    before = copy.deepcopy(state.owner)
    request = _request("legacy-wire", **dict(changes))

    response = asyncio.run(daemon.handle_request(request))

    assert response["ok"] is False
    assert response["code"] in SCHEMA_REFUSALS
    assert controller.calls == []
    assert state.owner == before


@pytest.mark.parametrize(
    "owner",
    [
        {
            "schema": 1,
            "mode": "managed",
            "lane": LANE,
            "generation": GENERATION,
            "daemon_id": "daemon-test",
            "participants": [{"participant_id": "worker-a", "mailbox_id": "m1"}],
        },
        {
            "schema_version": SCHEMA_VERSION,
            "architecture": "independent-worker-mailbox",
            "mode": "managed",
            "lane": LANE,
            "generation": GENERATION,
            "daemon_id": "daemon-test",
            "runner_instance_id": "runner-a",
            "mailbox_id": "mailbox-a",
        },
    ],
)
def test_legacy_or_unknown_prototype_state_is_preserved_and_not_aliased(
    owner: Mapping[str, Any],
) -> None:
    state = LegacyState(owner)
    before = copy.deepcopy(state.owner)
    daemon = _daemon(state=state)

    with pytest.raises(DaemonError) as caught:
        asyncio.run(daemon.start())

    assert caught.value.code in SCHEMA_REFUSALS
    assert state.owner == before
    assert "architecture" not in state.owner or state.owner.get("architecture") != ARCHITECTURE
    assert not any(key in state.owner for key in ("native_children", "children"))


def test_schema_v2_start_rejects_independent_child_runner_and_mailbox_fields() -> None:
    controller = StatusController()
    daemon = asyncio.run(_started_daemon(controller=controller))
    body = {
        "coordinator": {
            "session_uuid": "11111111-1111-4111-8111-111111111111",
            "profile": "team-a",
        },
        # These fields are the superseded prototype's aliases.  A v2 request
        # cannot smuggle them through a native lineage envelope.
        "participants": [
            {
                "participant_id": "worker-a",
                "runner_instance_id": "runner-a",
                "mailbox_id": "mailbox-a",
                "session_id": "child-session-a",
            }
        ],
        "runner_specs": [{"participant_id": "worker-a", "runner_uuid": "uuid-a"}],
    }

    response = asyncio.run(
        daemon.handle_request(_request("prototype-start", operation="start", body=body))
    )

    assert response["ok"] is False
    assert response["code"] in {"invalid", "unsupported", *SCHEMA_REFUSALS}
    assert controller.calls == []


@pytest.mark.parametrize(
    "operation,body",
    [
        (
            "start",
            {
                "coordinator": {"profile": "team-a"},
                "participants": ["worker-a"],
                "runner_specs": {"worker-a": {"uuid": "child-uuid"}},
            },
        ),
        (
            "add-worker",
            {
                "participant": {
                    "participant_id": "worker-a",
                    "session_uuid": "child-uuid",
                    "mailbox_id": "mailbox-a",
                },
                "runner_spec": {"runner_uuid": "runner-uuid"},
            },
        ),
    ],
)
def test_schema_v2_rejects_unversioned_roster_and_child_uuid_aliases(
    operation: str, body: Mapping[str, Any]
) -> None:
    """A list/alias roster is not a native child lineage record."""
    controller = StatusController()
    daemon = asyncio.run(_started_daemon(controller=controller))

    response = asyncio.run(
        daemon.handle_request(_request("bad-roster", operation=operation, body=body))
    )

    assert response["ok"] is False
    assert response["code"] in {"invalid", "unsupported", *SCHEMA_REFUSALS}
    assert controller.calls == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", 2.0),
        ("schema", True),
        ("schema_version", 2.0),
        ("schema_version", True),
    ],
)
def test_schema_markers_require_integer_type_not_numeric_coercion(
    field: str, value: Any
) -> None:
    controller = StatusController()
    daemon = asyncio.run(_started_daemon(controller=controller))
    request = _request("bad-marker")
    request[field] = value

    response = asyncio.run(daemon.handle_request(request))

    assert response["ok"] is False
    assert response["code"] in SCHEMA_REFUSALS | {"invalid"}
    assert controller.calls == []


def test_conflicting_handler_response_marker_is_refused_not_overwritten(
    tmp_path: Path,
) -> None:
    """The transport cannot turn an old handler response into a v2 result."""
    socket_path = tmp_path / "conflicting.sock"
    stop_event = threading.Event()
    result: list[dict[str, Any]] = []

    def handler(_request: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema": 1,
            "schema_version": 1,
            "architecture": "independent-worker-mailbox",
            "ok": True,
            "result": {"phase": "ready-held"},
        }

    def serve() -> None:
        result.extend(
            serve_daemon(
                socket_path,
                handler,
                max_requests=1,
                stop_event=stop_event,
            )
        )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    _wait_for_socket(socket_path, thread)
    try:
        response = _send(socket_path, _request("conflicting-response"))
    finally:
        _stop_server(socket_path, stop_event, thread)

    assert response["ok"] is False
    assert response["code"] in SCHEMA_REFUSALS
    assert result and result[-1]["ok"] is False
    assert result[-1]["code"] in SCHEMA_REFUSALS


@pytest.mark.parametrize(
    "operation,body",
    [
        (
            "add-worker",
            {
                "participant": {
                    "participant_id": "child-agent-a",
                    "session_uuid": "child-session-a",
                    "mailbox_id": "mailbox-a",
                },
                "runner_spec": {"participant_id": "child-agent-a"},
            },
        ),
        (
            "complete-worker",
            {"participant_id": "child-agent-a", "runner_uuid": "runner-a"},
        ),
        (
            "submit",
            {
                "recipient_id": "child-agent-a",
                "mailbox_id": "mailbox-a",
                "payload_ref": {"path": "/private/fake/payload"},
            },
        ),
    ],
)
def test_obsolete_independent_child_operations_refuse_under_schema2(
    operation: str, body: Mapping[str, Any]
) -> None:
    controller = StatusController()
    daemon = asyncio.run(_started_daemon(controller=controller))

    response = asyncio.run(
        daemon.handle_request(_request("obsolete-child-op", operation=operation, body=body))
    )

    assert response["ok"] is False
    assert response["code"] in {"invalid", "unsupported", *SCHEMA_REFUSALS}
    assert controller.calls == []


def test_nonmanaged_legacy_transport_route_remains_available(tmp_path: Path) -> None:
    """Schema-v2 managed wire changes do not erase legacy lane inspection."""
    socket_path = tmp_path / "legacy-inspect.sock"
    stop_event = threading.Event()
    result: list[dict[str, Any]] = []

    def handler(request: Mapping[str, Any]) -> dict[str, Any]:
        assert request["operation"] == "legacy-check"
        return {"ok": True, "result": {"mode": "legacy", "present": False}}

    def serve() -> None:
        result.extend(
            serve_daemon(
                socket_path,
                handler,
                max_requests=1,
                stop_event=stop_event,
            )
        )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    _wait_for_socket(socket_path, thread)
    try:
        response = _send(
            socket_path,
            _request("legacy-inspection", operation="legacy-check", body={}),
        )
    finally:
        _stop_server(socket_path, stop_event, thread)

    assert response["ok"] is True
    assert response["result"] == {"mode": "legacy", "present": False}
    assert result and result[-1]["ok"] is True


def test_child_targeted_mailbox_alias_is_not_a_v2_public_operation() -> None:
    controller = StatusController()
    daemon = asyncio.run(_started_daemon(controller=controller))
    request = _request(
        "child-mailbox",
        operation="submit",
        body={
            "recipient_id": "child-agent-a",
            "mailbox_id": "mailbox-a",
            "payload_ref": {"path": "/private/fake/payload"},
        },
    )

    response = asyncio.run(daemon.handle_request(request))

    assert response["ok"] is False
    assert response["code"] in {"invalid", "unsupported", *SCHEMA_REFUSALS}
    assert controller.calls == []


def test_unknown_effect_refusal_is_stable_and_does_not_dispatch() -> None:
    controller = ReleaseController()
    daemon = asyncio.run(_started_daemon(controller=controller))
    request = _request(
        "release-uncertain",
        operation="release",
        body={"operation_id": "op-uncertain"},
    )

    response = asyncio.run(daemon.handle_request(request))

    assert response["ok"] is False
    assert response["code"] == "uncertain-effect"
    assert controller.calls == ["release"]


def test_v2_socket_round_trip_uses_one_native_transport_loop(tmp_path: Path) -> None:
    socket_path = tmp_path / "managed.sock"
    stop_event = threading.Event()
    controller = StatusController()
    daemon = asyncio.run(_started_daemon(controller=controller))
    result: list[dict[str, Any]] = []

    def serve() -> None:
        result.extend(
            serve_daemon(
                socket_path,
                daemon,
                max_requests=1,
                stop_event=stop_event,
            )
        )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    _wait_for_socket(socket_path, thread)
    try:
        response = _send(socket_path, _request("status-socket"))
    finally:
        _stop_server(socket_path, stop_event, thread)

    assert response["ok"] is True
    assert response["schema"] == SCHEMA_VERSION
    assert response["schema_version"] == SCHEMA_VERSION
    assert response["architecture"] == ARCHITECTURE
    assert response["request_id"] == "status-socket"
    assert response["result"]["phase"] == "ready-held"
    assert len(controller.loops) == 1
    assert result and result[-1]["request_id"] == "status-socket"


def test_v2_socket_rejects_schema1_without_invoking_controller(tmp_path: Path) -> None:
    socket_path = tmp_path / "legacy.sock"
    stop_event = threading.Event()
    controller = StatusController()
    daemon = asyncio.run(_started_daemon(controller=controller))
    result: list[dict[str, Any]] = []

    def serve() -> None:
        result.extend(
            serve_daemon(
                socket_path,
                daemon,
                max_requests=1,
                stop_event=stop_event,
            )
        )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    _wait_for_socket(socket_path, thread)
    try:
        response = _send(
            socket_path,
            _request("legacy-socket", schema=1, schema_version=1),
        )
    finally:
        _stop_server(socket_path, stop_event, thread)

    assert response["ok"] is False
    assert response["code"] in SCHEMA_REFUSALS
    assert response["schema"] == SCHEMA_VERSION
    assert response["schema_version"] == SCHEMA_VERSION
    assert response["architecture"] == ARCHITECTURE
    assert controller.calls == []
    assert result and result[-1]["code"] in SCHEMA_REFUSALS


# Native admission is deliberately a separate public operation from the old
# independent-worker ``add-worker``/``submit`` surface.  The body is one
# canonical projection of the SDK's pending Agent/Task admission record.  It
# contains the coordinator lineage and the exact launch definition, but no
# child session/runner/mailbox identity.  The controller/state fakes below are
# intentionally close to the production seam: the controller owns the
# admission call, the state owns the durable pre-allow write, and all effects
# are recorded in one order list.
NATIVE_ADMISSION_FIELDS = frozenset(
    {
        "admission_id",
        "tool_use_id",
        "agent_type",
        "invocation_id",
        "parent",
        "custom_definition",
        "definition_digest",
        "trusted_definition_digest",
        "watermark",
        "owner_generation",
        "lineage_id",
        "runner_incarnation",
        "launch_completed",
    }
)
NATIVE_CHILD_ID_ALIASES = frozenset(
    {
        "session_id",
        "session_uuid",
        "child_session_id",
        "child_session_uuid",
        "runner_id",
        "runner_uuid",
        "runner_instance_id",
        "mailbox_id",
        "process_group_id",
    }
)
NATIVE_ADMISSION_ACK_FIELDS = (
    "admission_id",
    "owner_generation",
    "lineage_id",
    "runner_incarnation",
    "invocation_id",
    "tool_use_id",
    "trusted_definition_digest",
)


def _native_admission_intent(**overrides: Any) -> dict[str, Any]:
    """Build the exact durable pre-allow Agent/Task intent projection."""
    definition = {
        "name": "writer",
        "digest": "a" * 64,
        "description": "authorized native child",
        "prompt": "inspect and update the requested files",
        "tools": ["Read", "Edit"],
        "model": "claude-sonnet-4-20250514",
        "effort": "high",
        "permissionMode": "default",
        "permissions": {"workspace": "lineage"},
    }
    intent: dict[str, Any] = {
        "admission_id": "admission-1",
        "tool_use_id": "tool-use-1",
        "agent_type": "writer",
        "invocation_id": "invocation-1",
        "parent": {
            "session_id": "coordinator-session-1",
            "agent_id": None,
            "invocation_id": "invocation-1",
            "prompt_id": "prompt-1",
        },
        "custom_definition": copy.deepcopy(definition),
        "definition_digest": definition["digest"],
        "trusted_definition_digest": definition["digest"],
        "watermark": 11,
        "owner_generation": GENERATION,
        "lineage_id": "lineage-build-7",
        "runner_incarnation": "runner-build-1",
        "launch_completed": False,
    }
    intent.update(overrides)
    return intent


def _native_admission_ack(
    intent: Mapping[str, Any], *, accepted: bool = True, **overrides: Any
) -> dict[str, Any]:
    """Return the only acknowledgement fields the native boundary trusts."""
    acknowledgement = {
        "accepted": accepted,
        **{field: intent[field] for field in NATIVE_ADMISSION_ACK_FIELDS},
    }
    acknowledgement.update(overrides)
    return acknowledgement


def _native_admission_request(
    request_id: str,
    *,
    intent: Mapping[str, Any] | None = None,
    generation: int = GENERATION,
    body_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request = _request(
        request_id,
        operation=NATIVE_ADMISSION_OPERATION,
        body=dict(intent or _native_admission_intent()),
    )
    request["generation"] = generation
    if body_extra:
        request["body"].update(dict(body_extra))
    return request


class NativeAdmissionState(RecordingState):
    """Durable state seam for native admission and fence ordering."""

    def __init__(self) -> None:
        super().__init__(_native_owner())
        self.events: list[str] = []
        self.admissions: list[dict[str, Any]] = []
        self.sealed_admissions: list[dict[str, Any]] = []
        self.fenced = False

    def persist_native_admission(self, intent: Mapping[str, Any]) -> dict[str, Any]:
        self.events.append("state.persist")
        record = copy.deepcopy(dict(intent))
        self.admissions.append(record)
        return copy.deepcopy(record)

    def seal_native_roster(self) -> list[dict[str, Any]]:
        self.events.append("state.seal")
        self.sealed_admissions = copy.deepcopy(self.admissions)
        return copy.deepcopy(self.sealed_admissions)


class NativeAdmissionController(StatusController):
    """Controller fake with the production persist/ack/fence call order."""

    def __init__(
        self,
        state: NativeAdmissionState,
        *,
        mode: str = "accepted",
        ack_field: str | None = None,
        fence_after_persist: bool = False,
        seal_after_ack: bool = False,
    ) -> None:
        super().__init__()
        self.state = state
        # Keep controller and state transitions in one durable-order trace.
        self.events = state.events
        self.mode = mode
        self.ack_field = ack_field
        self.fence_after_persist = fence_after_persist
        self.seal_after_ack = seal_after_ack
        self.admission_calls: list[tuple[str, int, dict[str, Any]]] = []
        self.runtime_starts: list[dict[str, Any]] = []

    def _validate_intent(self, generation: int, intent: Mapping[str, Any]) -> None:
        if generation != GENERATION:
            raise DaemonError("stale-generation", "native admission generation is stale")
        if set(intent) != NATIVE_ADMISSION_FIELDS:
            raise DaemonError("invalid", "native admission intent fields are not canonical")
        if any(alias in intent for alias in NATIVE_CHILD_ID_ALIASES):
            raise DaemonError("unsupported", "native child has an independent identity alias")
        parent = intent.get("parent")
        if not isinstance(parent, Mapping):
            raise DaemonError("invalid", "native admission parent links are missing")
        if parent.get("session_id") != "coordinator-session-1":
            raise DaemonError("stale-generation", "native admission coordinator changed")
        expected = {
            "owner_generation": GENERATION,
            "lineage_id": "lineage-build-7",
            "runner_incarnation": "runner-build-1",
            "invocation_id": "invocation-1",
            "tool_use_id": "tool-use-1",
            "trusted_definition_digest": "a" * 64,
        }
        if any(intent.get(field) != value for field, value in expected.items()):
            raise DaemonError("stale-generation", "native admission correlation is stale")
        if parent.get("invocation_id") != intent.get("invocation_id"):
            raise DaemonError("stale-generation", "native admission parent invocation changed")
        definition = intent.get("custom_definition")
        if not isinstance(definition, Mapping) or definition.get("digest") != "a" * 64:
            raise DaemonError("stale-generation", "native child definition digest changed")
        if intent.get("definition_digest") != intent.get("trusted_definition_digest"):
            raise DaemonError("stale-generation", "native child definition is not immutable")
        if intent.get("launch_completed") is not False:
            raise DaemonError("invalid", "native admission cannot claim a launch")

    async def persist_native_admission(
        self,
        request_id: str,
        generation: int,
        intent: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.events.append("controller.persist_native_admission")
        captured = copy.deepcopy(dict(intent))
        self.admission_calls.append((request_id, generation, captured))
        self._validate_intent(generation, captured)
        persisted = self.state.persist_native_admission(captured)

        if self.fence_after_persist:
            self.state.fenced = True
            self.state.events.append("state.fence")
            self.state.seal_native_roster()
            raise DaemonError(
                "stale-generation",
                "native admission crossed the durable fence",
            )
        if self.mode == "timeout":
            self.events.append("controller.wait")
            await asyncio.sleep(3600)
        if self.mode == "disconnect":
            self.events.append("controller.disconnect")
            raise ConnectionError("native admission control reader disconnected")

        acknowledgement = _native_admission_ack(persisted)
        if self.mode == "wrong":
            assert self.ack_field is not None
            acknowledgement[self.ack_field] = "wrong-" + self.ack_field
        elif self.mode == "missing":
            assert self.ack_field is not None
            del acknowledgement[self.ack_field]
        self.events.append("controller.ack")
        if self.seal_after_ack:
            self.state.seal_native_roster()
        return acknowledgement


def _native_result(response: Mapping[str, Any]) -> Mapping[str, Any]:
    result = response.get("result")
    return result if isinstance(result, Mapping) else {}


def test_native_admission_ipc_persists_exact_intent_before_ack_and_preserves_policy() -> None:
    state = NativeAdmissionState()
    controller = NativeAdmissionController(state)
    daemon = asyncio.run(_started_daemon(state, controller))
    intent = _native_admission_intent()

    response = asyncio.run(
        daemon.handle_request(_native_admission_request("native-admit-1", intent=intent))
    )

    assert response["ok"] is True
    assert _native_result(response)["accepted"] is True
    assert state.events == [
        "controller.persist_native_admission", "state.persist", "controller.ack"
    ]
    assert state.admissions == [intent]
    assert set(state.admissions[0]) == NATIVE_ADMISSION_FIELDS
    assert state.admissions[0]["owner_generation"] == GENERATION
    assert state.admissions[0]["lineage_id"] == "lineage-build-7"
    assert state.admissions[0]["runner_incarnation"] == "runner-build-1"
    assert state.admissions[0]["invocation_id"] == "invocation-1"
    assert state.admissions[0]["tool_use_id"] == "tool-use-1"
    assert state.admissions[0]["custom_definition"] == intent["custom_definition"]
    assert state.admissions[0]["custom_definition"]["model"] == "claude-sonnet-4-20250514"
    assert state.admissions[0]["custom_definition"]["effort"] == "high"
    assert state.admissions[0]["trusted_definition_digest"] == "a" * 64
    assert NATIVE_CHILD_ID_ALIASES.isdisjoint(state.admissions[0])
    assert controller.runtime_starts == []


def test_native_admission_socket_persists_before_ack_on_one_controller_loop(
    tmp_path: Path,
) -> None:
    socket_path = tmp_path / "native-admission.sock"
    stop_event = threading.Event()
    state = NativeAdmissionState()
    controller = NativeAdmissionController(state)
    daemon = asyncio.run(_started_daemon(state, controller))
    served: list[dict[str, Any]] = []

    def serve() -> None:
        served.extend(
            serve_daemon(
                socket_path,
                daemon,
                max_requests=1,
                stop_event=stop_event,
            )
        )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    _wait_for_socket(socket_path, thread)
    try:
        response = _send(
            socket_path,
            _native_admission_request("native-admit-socket"),
        )
    finally:
        _stop_server(socket_path, stop_event, thread)

    assert response["ok"] is True
    assert response["schema_version"] == SCHEMA_VERSION
    assert response["architecture"] == ARCHITECTURE
    assert _native_result(response)["accepted"] is True
    assert state.events == [
        "controller.persist_native_admission", "state.persist", "controller.ack"
    ]
    assert served and served[-1]["request_id"] == "native-admit-socket"


@pytest.mark.parametrize(
    "mode,field",
    [
        ("wrong", "admission_id"),
        ("wrong", "owner_generation"),
        ("wrong", "lineage_id"),
        ("wrong", "runner_incarnation"),
        ("wrong", "invocation_id"),
        ("wrong", "tool_use_id"),
        ("wrong", "trusted_definition_digest"),
        ("missing", "invocation_id"),
        ("missing", "tool_use_id"),
        ("missing", "trusted_definition_digest"),
    ],
)
def test_native_admission_wrong_or_missing_correlation_is_not_accepted(
    mode: str,
    field: str,
) -> None:
    state = NativeAdmissionState()
    controller = NativeAdmissionController(state, mode=mode, ack_field=field)
    daemon = asyncio.run(_started_daemon(state, controller))
    intent = _native_admission_intent()

    response = asyncio.run(
        daemon.handle_request(_native_admission_request("native-bad-ack", intent=intent))
    )

    assert response["ok"] is False
    assert response["code"] in {
        "invalid",
        "unsupported",
        "ownership-conflict",
        "stale-generation",
        "uncertain-effect",
    }
    # The pre-allow record is durable even when the acknowledgement is not
    # trustworthy; no runtime start or implicit replay is allowed.
    assert state.admissions == [intent]
    assert state.events[:2] == [
        "controller.persist_native_admission", "state.persist"
    ]
    assert "controller.ack" in state.events
    assert controller.runtime_starts == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_generation", GENERATION - 1),
        ("lineage_id", "lineage-stale"),
        ("runner_incarnation", "runner-stale"),
        ("invocation_id", "invocation-stale"),
        ("tool_use_id", "tool-stale"),
        ("trusted_definition_digest", "b" * 64),
    ],
)
def test_native_admission_stale_lineage_correlation_refuses_before_persistence(
    field: str,
    value: Any,
) -> None:
    state = NativeAdmissionState()
    controller = NativeAdmissionController(state)
    daemon = asyncio.run(_started_daemon(state, controller))
    intent = _native_admission_intent(**{field: value})
    if field == "invocation_id":
        intent["parent"]["invocation_id"] = value
    if field == "trusted_definition_digest":
        intent["definition_digest"] = value
    request_generation = GENERATION - 1 if field == "owner_generation" else GENERATION

    response = asyncio.run(
        daemon.handle_request(
            _native_admission_request(
                "native-stale-" + field,
                intent=intent,
                generation=request_generation,
            )
        )
    )

    assert response["ok"] is False
    assert response["code"] in {"invalid", "unsupported", "stale-generation", "ownership-conflict"}
    assert state.admissions == []
    assert state.events == (
        [] if field == "owner_generation"
        else ["controller.persist_native_admission"]
    )
    assert controller.runtime_starts == []


@pytest.mark.parametrize("alias", sorted(NATIVE_CHILD_ID_ALIASES))
def test_native_admission_rejects_independent_child_identity_aliases(
    alias: str,
) -> None:
    state = NativeAdmissionState()
    controller = NativeAdmissionController(state)
    daemon = asyncio.run(_started_daemon(state, controller))
    intent = _native_admission_intent(**{alias: "forged-child-identity"})

    response = asyncio.run(
        daemon.handle_request(_native_admission_request("native-alias", intent=intent))
    )

    assert response["ok"] is False
    assert response["code"] in {"invalid", "unsupported", *SCHEMA_REFUSALS}
    assert state.admissions == []
    assert state.events == []
    assert controller.runtime_starts == []


@pytest.mark.parametrize("mode", ["timeout", "disconnect"])
def test_native_admission_timeout_or_disconnect_leaves_one_unresolved_intent(
    mode: str,
) -> None:
    state = NativeAdmissionState()
    controller = NativeAdmissionController(state, mode=mode)
    daemon = asyncio.run(_started_daemon(state, controller))
    intent = _native_admission_intent()
    deadline = time.monotonic() + 0.03 if mode == "timeout" else None

    response = asyncio.run(
        daemon.handle_request(
            _native_admission_request("native-no-ack-" + mode, intent=intent),
            deadline=deadline,
        )
    )

    assert response["ok"] is False
    assert response["code"] in {
        "timeout",
        "loader-failed",
        "uncertain-effect",
        "unknown",
    }
    assert state.admissions == [intent]
    assert "state.persist" in state.events
    assert "controller.ack" not in state.events
    assert controller.runtime_starts == []


def test_native_admission_concurrent_fence_after_persistence_is_sealed_and_refused() -> None:
    state = NativeAdmissionState()
    controller = NativeAdmissionController(state, fence_after_persist=True)
    daemon = asyncio.run(_started_daemon(state, controller))
    intent = _native_admission_intent()

    response = asyncio.run(
        daemon.handle_request(_native_admission_request("native-fenced", intent=intent))
    )

    assert response["ok"] is False
    assert response["code"] in {"stale-generation", "busy", "uncertain-effect"}
    assert state.fenced is True
    assert state.events == [
        "controller.persist_native_admission",
        "state.persist",
        "state.fence",
        "state.seal",
    ]
    assert state.sealed_admissions == [intent]
    assert controller.runtime_starts == []


def test_native_ack_before_subagent_start_remains_pending_in_sealed_roster() -> None:
    state = NativeAdmissionState()
    controller = NativeAdmissionController(state, seal_after_ack=True)
    daemon = asyncio.run(_started_daemon(state, controller))
    intent = _native_admission_intent()

    response = asyncio.run(
        daemon.handle_request(_native_admission_request("native-ack-before-start", intent=intent))
    )

    assert response["ok"] is True
    assert _native_result(response)["accepted"] is True
    assert state.sealed_admissions == [intent]
    sealed = state.sealed_admissions[0]
    assert sealed["launch_completed"] is False
    assert "agent_id" not in sealed
    assert "task_id" not in sealed
    assert controller.runtime_starts == []
    assert state.events == [
        "controller.persist_native_admission",
        "state.persist",
        "controller.ack",
        "state.seal",
    ]


def test_public_body_ack_evidence_cannot_forge_native_admission() -> None:
    state = NativeAdmissionState()
    controller = NativeAdmissionController(state)
    daemon = asyncio.run(_started_daemon(state, controller))
    intent = _native_admission_intent()
    forged_ack = _native_admission_ack(intent)

    response = asyncio.run(
        daemon.handle_request(
            _native_admission_request(
                "native-forged-ack",
                intent=intent,
                body_extra={
                    "ack": forged_ack,
                    "runtime": {"accepted": True},
                },
            )
        )
    )

    assert response["ok"] is False
    assert response["code"] in {"invalid", "unsupported", *SCHEMA_REFUSALS}
    assert state.admissions == []
    assert state.events == []
    assert controller.admission_calls == []
    assert controller.runtime_starts == []
