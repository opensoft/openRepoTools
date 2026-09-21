# SPDX-License-Identifier: Apache-2.0
"""Focused daemon tests for the bounded same-runner mailbox pump.

These tests stop at the daemon/controller boundary.  The runtime is always a
fake: it reports the coordinator's current invocation and accepts a mailbox
only after the daemon has observed a fresh idle envelope.  In particular,
these tests do not turn a fake reservation into Gate-0 or live SDK evidence.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import subprocess
import threading
import time
from typing import Any, Mapping
from pathlib import Path

import pytest

from lane_managed_controller import ManagedController
from lane_managed_daemon import (
    DaemonError,
    ManagedDaemon,
    _current_process_domain,
    serve_daemon,
)
from lane_managed_state import ManagedStateStore, resolve_workspace
from test_lane_managed_daemon import (
    VerifyingProfiles,
    _load_cli_api,
    _native_start_body,
    _start_request,
    _stop_server_thread,
    _wait_for_socket,
)
from test_lane_managed_controller_rollover import RolloverRuntime


LANE = "rollover"
GENERATION = 7


def _owner(daemon_id: str = "daemon-rollover") -> dict[str, Any]:
    return {
        "mode": "managed",
        "lane": LANE,
        "generation": GENERATION,
        "daemon_id": daemon_id,
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _reservation(
    *,
    participant_id: str,
    session_id: str,
    runner_instance_id: str,
    message_id: str,
    prior_invocation_id: str = "invocation-A",
    prior_watermark: int = 10,
) -> dict[str, Any]:
    binding = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "reservation_version": 1,
        "reservation_id": "reservation-1",
        "operation_id": "operation-rollover",
        "owner_generation": GENERATION,
        "daemon_id": "daemon-rollover",
        "participant_id": participant_id,
        "session_id": session_id,
        "runner_incarnation": runner_instance_id,
        "lineage_id": "lineage-rollover",
        "lineage_generation": 1,
        "prior_invocation_id": prior_invocation_id,
        "next_invocation_id": message_id,
        "prior_mailbox_id": prior_invocation_id,
        "next_mailbox_id": message_id,
        "prior_watermark": prior_watermark,
        "definitions_digest": "a" * 64,
        "permissions_digest": "b" * 64,
        "claim_digest": "c" * 64,
    }
    binding["binding_digest"] = _digest(binding)
    roster = {
        "parent_state": "idle",
        "children": [],
        "pending_admission_ids": [],
        "pending_task_ids": [],
        "parent_active_tool_ids": [],
        "parent_uncertain_tool_ids": [],
        "parent_unresolved_effect_ids": [],
        "descendant_ids": [],
    }
    proof = {
        "parent_result": {
            "session_id": session_id,
            "invocation_id": prior_invocation_id,
            "message_id": prior_invocation_id,
            "result_watermark": prior_watermark + 1,
            "reader_drained_watermark": prior_watermark + 1,
        },
        "roster": roster,
        "roster_digest": _digest(roster),
        "observation_watermark": prior_watermark + 1,
        "uncertainty": [],
        "overflow": False,
    }
    return {
        **binding,
        "state": "reserved",
        "terminal_watermark": prior_watermark + 1,
        "next_watermark": prior_watermark + 2,
        "terminal_proof": proof,
        "terminal_proof_digest": _digest(proof),
    }


class OwnerState:
    def __init__(self, owner: Mapping[str, Any] | None = None) -> None:
        self.owner = dict(owner or _owner())
        self.reads = 0

    async def read_owner(self, *, deadline: float | None = None) -> dict[str, Any]:
        del deadline
        self.reads += 1
        return dict(self.owner)


class RolloverController:
    """Small durable projection for pump tests.

    ``invocation-A`` is represented by the runtime status.  B and C are
    queued durable mailbox rows.  One pump pass can consume only one row for
    the coordinator; a later pass must obtain another fresh terminal status.
    """

    def __init__(self) -> None:
        self.phase = "released"
        self.daemon_id = "daemon-rollover"
        self.runner_instance_id = "runner-rollover"
        self.session_id = "session-rollover"
        self.queue = ["invocation-B", "invocation-C"]
        self.dispatches: list[str] = []
        self.status_reads = 0
        self._busy = True

    def set_busy(self, value: bool) -> None:
        self._busy = value

    def status(self) -> dict[str, Any]:
        self.status_reads += 1
        return {
            "operation": {
                "operation_id": "operation-rollover",
                "phase": self.phase,
                "metadata": {
                    "runner_instances": {"coordinator": self.runner_instance_id},
                },
            },
            "participants": [{
                "participant_id": "coordinator",
                "session_id": self.session_id,
            }],
        }

    def dispatch_candidates(self, operation_id: str) -> list[dict[str, str]]:
        assert operation_id == "operation-rollover"
        if self.phase != "released":
            raise DaemonError("busy", "operation is no longer released")
        return [
            {
                "message_id": message_id,
                "recipient_id": "coordinator",
            }
            for message_id in self.queue
        ]

    async def dispatch_next(
        self, operation_id: str, *, recipient_id: str | None = None,
    ) -> dict[str, Any] | None:
        assert operation_id == "operation-rollover"
        assert recipient_id == "coordinator"
        if self.phase != "released":
            raise DaemonError("busy", "phase fence crossed before dispatch")
        if not self.queue:
            return None
        message_id = self.queue.pop(0)
        self.dispatches.append(message_id)
        return {
            "message_id": message_id,
            "recipient_id": "coordinator",
            "state": "acknowledged",
            "runtime_ack": {
                "message_id": message_id,
                "accepted": True,
                "ack_kind": "accepted-send",
            },
        }


class RolloverAdapter:
    def __init__(self, controller: RolloverController) -> None:
        self.controller = controller
        self.status_calls = 0

    async def status(self, participant_id: str) -> dict[str, Any]:
        self.status_calls += 1
        assert participant_id == "coordinator"
        active = self.controller._busy
        evidence = {
            "participant_id": participant_id,
            "session_id": self.controller.session_id,
            "runner_instance_id": self.controller.runner_instance_id,
            "ready": True,
            "released": True,
            "active_turn": active,
            "turn_terminal": not active,
            "drained": not active,
            "participant_quiescent": not active,
            "tools_quiescent": not active,
            "quiescent": not active,
            "tools": [],
            "uncertain_effects": [],
            "uncertain_effects_overflow": False,
            "process": {
                "pid": 101,
                "process_group_id": 101,
                "process_start_token": "runner-token",
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


def _daemon(
    controller: RolloverController,
    *,
    state: OwnerState | None = None,
    adapter: Any | None = None,
) -> ManagedDaemon:
    daemon = ManagedDaemon(
        state=state or OwnerState(),
        controller=controller,
        adapter=adapter or RolloverAdapter(controller),
        daemon_id="daemon-rollover",
        opt_in=True,
        lane=LANE,
    )
    daemon.owner_record = _owner()
    daemon._owner_enrolled = True
    daemon.started = True
    return daemon


def test_bounded_pump_retains_busy_a_then_accepts_b_and_c_once() -> None:
    async def scenario() -> None:
        controller = RolloverController()
        daemon = _daemon(controller)

        busy = await daemon.dispatch_pump_tick("operation-rollover")
        assert busy["dispatched"] == []
        assert busy["skipped"] == [{
            "recipient_id": "coordinator",
            "message_id": "invocation-B",
            "code": "busy",
            "reason": "status-not-idle",
        }]
        assert controller.queue == ["invocation-B", "invocation-C"]

        controller.set_busy(False)
        first = await daemon.dispatch_pump_tick("operation-rollover")
        second = await daemon.dispatch_pump_tick("operation-rollover")
        duplicate = await daemon.dispatch_pump_tick("operation-rollover")

        assert [item["message_id"] for item in first["dispatched"]] == [
            "invocation-B"
        ]
        assert [item["message_id"] for item in second["dispatched"]] == [
            "invocation-C"
        ]
        assert duplicate["dispatched"] == []
        assert controller.dispatches == ["invocation-B", "invocation-C"]
        assert controller.queue == []
        assert daemon._dispatch_pump_task is None

    asyncio.run(scenario())


def test_pump_keeps_b_queued_when_phase_changes_after_runtime_await() -> None:
    async def scenario() -> None:
        controller = RolloverController()
        adapter = RolloverAdapter(controller)
        daemon = _daemon(controller, adapter=adapter)

        original_status = adapter.status

        async def status_then_fence(participant_id: str) -> dict[str, Any]:
            value = await original_status(participant_id)
            controller.phase = "paused"
            return value

        adapter.status = status_then_fence  # type: ignore[method-assign]
        controller.set_busy(False)

        result = await daemon.dispatch_pump_tick("operation-rollover")

        assert result["dispatched"] == []
        assert controller.dispatches == []
        assert controller.queue == ["invocation-B", "invocation-C"]
        assert result["skipped"] == [{
            "recipient_id": "coordinator",
            "message_id": "invocation-B",
            "code": "busy",
            "reason": "dispatch-not-acknowledged",
        }]

    asyncio.run(scenario())


class BindingController:
    def __init__(self, mutate: Any | None = None) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.mutate = mutate

    async def native_invocation_dispatch_binding(
        self, generation: int, participant_id: str, runner_instance_id: str,
        message_id: str, *, session_id: str,
    ) -> dict[str, Any]:
        self.calls.append((generation, participant_id, runner_instance_id, message_id))
        context = {
            "lineage": {
                "owner_generation": generation,
                "lineage_id": "lineage-rollover",
                "lineage_generation": 1,
                "session_uuid": session_id,
            },
            "runner_incarnation": runner_instance_id,
            "invocation_id": message_id,
        }
        result = {
            "context": context,
            "reservation_binding": _reservation(
                participant_id=participant_id,
                session_id=session_id,
                runner_instance_id=runner_instance_id,
                message_id=message_id,
            ),
        }
        if self.mutate is not None:
            result = self.mutate(result)
        return result


def test_native_binding_ack_wraps_optional_reservation_without_polluting_context() -> None:
    async def scenario() -> None:
        controller = BindingController()
        daemon = _daemon(RolloverController())
        daemon.controller = controller
        ack = await daemon._prepare_native_invocation_callback(
            "coordinator", "session-rollover", "runner-rollover", "invocation-B"
        )

        assert ack["bound"] is True
        assert ack["participant_id"] == "coordinator"
        assert ack["session_id"] == "session-rollover"
        assert ack["runner_instance_id"] == "runner-rollover"
        assert ack["message_id"] == "invocation-B"
        assert ack["context"] == {
            "lineage": {
                "owner_generation": GENERATION,
                "lineage_id": "lineage-rollover",
                "lineage_generation": 1,
                "session_uuid": "session-rollover",
            },
            "runner_incarnation": "runner-rollover",
            "invocation_id": "invocation-B",
        }
        assert ack["reservation_binding"]["reservation_id"] == "reservation-1"
        assert "reservation_binding" not in ack["context"]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mutate, expected_code",
    [
        (lambda value: {"context": value["context"]}, "invalid"),
        (lambda value: {**value, "extra": True}, "invalid"),
        (
            lambda value: {
                **value,
                "reservation_binding": {
                    **value["reservation_binding"],
                    "schema_version": 3,
                },
            },
            "schema-mismatch",
        ),
        (
            lambda value: {
                **value,
                "reservation_binding": {
                    **value["reservation_binding"],
                    "next_mailbox_id": "other-mailbox",
                },
            },
            "stale-generation",
        ),
        (
            lambda value: {
                **value,
                "reservation_binding": {
                    **value["reservation_binding"],
                    "owner_generation": GENERATION + 1,
                },
            },
            "stale-generation",
        ),
        (
            lambda value: {
                **value,
                "reservation_binding": {
                    **value["reservation_binding"],
                    "terminal_proof": {
                        **value["reservation_binding"]["terminal_proof"],
                        "overflow": True,
                    },
                },
            },
            "uncertain-effect",
        ),
    ],
)
def test_native_binding_rejects_partial_or_changed_committed_reservation(
        mutate: Any, expected_code: str,
) -> None:
    async def scenario() -> None:
        controller = BindingController(mutate=mutate)
        daemon = _daemon(RolloverController())
        daemon.controller = controller

        with pytest.raises(DaemonError) as raised:
            await daemon._prepare_native_invocation_callback(
                "coordinator", "session-rollover", "runner-rollover", "invocation-B"
            )
        assert raised.value.code == expected_code

    asyncio.run(scenario())


def test_native_binding_does_not_probe_legacy_context_only_binder() -> None:
    async def scenario() -> None:
        class LegacyOnlyController:
            def __init__(self) -> None:
                self.called = False

            async def bind_native_invocation(self, *args: Any, **kwargs: Any) -> Any:
                del args, kwargs
                self.called = True
                return {}

        controller = LegacyOnlyController()
        daemon = _daemon(RolloverController())
        daemon.controller = controller

        with pytest.raises(DaemonError) as raised:
            await daemon._prepare_native_invocation_callback(
                "coordinator", "session-rollover", "runner-rollover", "invocation-B"
            )
        assert raised.value.code == "unsupported"
        assert controller.called is False

    asyncio.run(scenario())


class TakeoverBindingController(BindingController):
    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def native_invocation_dispatch_binding(
            self, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        self.entered.set()
        await self.release.wait()
        return {
            "context": {
                "lineage": {
                    "owner_generation": GENERATION,
                    "lineage_id": "lineage-rollover",
                    "lineage_generation": 1,
                    "session_uuid": kwargs["session_id"],
                },
                "runner_incarnation": args[2],
                "invocation_id": args[3],
            },
            "reservation_binding": None,
        }


def test_native_binding_rechecks_daemon_authority_after_await() -> None:
    async def scenario() -> None:
        state = OwnerState()
        controller = TakeoverBindingController()
        daemon = _daemon(RolloverController(), state=state)
        daemon.controller = controller

        task = asyncio.create_task(daemon._prepare_native_invocation_callback(
            "coordinator", "session-rollover", "runner-rollover", "invocation-B"
        ))
        await asyncio.wait_for(controller.entered.wait(), timeout=0.5)
        state.owner = _owner("replacement-daemon")
        controller.release.set()

        with pytest.raises(DaemonError) as raised:
            await task
        assert raised.value.code == "ownership-conflict"

    asyncio.run(scenario())


class PublicRolloverRuntime(RolloverRuntime):
    """Synthetic trusted runner used behind the public daemon socket.

    The adapter is constructor-injected evidence, not a public capability
    grant.  Its busy flag models A's live turn; the reservation/proof frame is
    still produced only by the implementation-owned ``prepare_invocation``
    seam inherited from the rollover runtime fixture.
    """

    def __init__(self) -> None:
        super().__init__()
        self.busy = False
        self.second_send_started = threading.Event()
        self.allow_third_send = threading.Event()

    async def status(self, participant_id: str) -> dict[str, Any]:
        value = await super().status(participant_id)
        evidence = value["evidence"]
        busy = self.busy
        evidence.update({
            "released": participant_id in self.released,
            "active_turn": busy,
            "turn_terminal": not busy,
            "drained": not busy,
            "participant_quiescent": not busy,
            "tools_quiescent": not busy,
            "quiescent": not busy,
            "tools": [],
            "uncertain_effects": [],
            "uncertain_effects_overflow": False,
        })
        return value

    async def send(
            self, participant_id: str, message_id: str, payload_ref: Any
    ) -> dict[str, Any]:
        result = await super().send(participant_id, message_id, payload_ref)
        if len(self.sent) == 2:
            # Hold the transport after B has crossed the runtime boundary so
            # the test can inspect A's committed history before C is admitted.
            self.second_send_started.set()
            while not self.allow_third_send.is_set():
                await asyncio.sleep(0.01)
        return result


def _public_transcript_verifier(
        _profile: Any, session_id: str, workspace: str | Path
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


def _public_request(
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


def test_public_socket_real_state_retains_busy_a_then_delivers_b_c_once(
        tmp_path: Path,
) -> None:
    """Exercise A→B→C through the real daemon, socket, controller, and state.

    The runner remains synthetic and trusted by construction; no account or
    network behavior is involved.  Durable state is the real
    ``ManagedStateStore`` and all lifecycle mutations enter through the
    public socket router.
    """

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
        "LANES_WORKSTATION": "daemon-rollover-test",
    }
    identity = resolve_workspace(
        "build",
        env=env,
        helper=lambda *_args, **_kwargs: (str(workspace) + "\n", 0, ""),
    )
    state = ManagedStateStore(identity)
    state.ensure_layout()
    runtime = PublicRolloverRuntime()
    controller = ManagedController(
        state,
        runtime=runtime,
        payload_resolver=lambda payload_ref: str(payload_ref),
        transcript_verifier=_public_transcript_verifier,
        clock=lambda: 1000.0,
    )
    daemon = ManagedDaemon(
        state=state,
        profiles=VerifyingProfiles(),
        controller=controller,
        adapter=runtime,
        daemon_id="daemon-test",
        opt_in=True,
        lane="build",
        env=env,
    )
    asyncio.run(daemon.start())
    owner_generation = int(daemon.owner_record["generation"])

    body = _native_start_body()
    body["coordinator"]["metadata"].update({
        "workspace": str(workspace),
        "transcript_project": str(workspace / "transcripts"),
    })
    runner_spec = body["runner_specs"]["coordinator"]
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
    socket_path = tmp_path / "managed-rollover.sock"
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
        target=serve, name="managed-public-rollover", daemon=True
    )
    thread.start()
    _wait_for_socket(socket_path, thread)

    def request(
            request_id: str, operation: str, body_value: Mapping[str, Any]
    ) -> dict[str, Any]:
        request_value = (
            _start_request(request_id, body)
            if operation == "start"
            else _public_request(
                request_id, operation, owner_generation, body_value
            )
        )
        request_value["generation"] = owner_generation
        return api["request_socket"](
            str(socket_path), request_value,
            connect_timeout=0.5, operation_timeout=2.0,
        )

    try:
        started = request("public-start", "start", {})
        assert started["ok"] is True, json.dumps(started, sort_keys=True)
        operation_id = started["result"]["operation_id"]

        first = request("public-a", "submit", {
            "recipient_id": "coordinator",
            "payload_ref": "opaque://a",
            "sender_id": "user",
            "task_id": "task-root",
        })
        assert first["ok"] is True
        assert first["result"]["state"] == "fenced"
        message_a = first["result"]["message_id"]

        released = request("public-release", "release", {
            "operation_id": operation_id,
        })
        assert released["ok"] is True
        assert [
            item["message_id"] for item in released["result"]["dispatch"]["dispatched"]
        ] == [message_a]
        assert [item[1] for item in runtime.sent] == [message_a]

        runtime.busy = True
        second = request("public-b", "submit", {
            "recipient_id": "coordinator",
            "payload_ref": "opaque://b",
            "sender_id": "user",
            "task_id": "task-root",
        })
        third = request("public-c", "submit", {
            "recipient_id": "coordinator",
            "payload_ref": "opaque://c",
            "sender_id": "user",
            "task_id": "task-root",
        })
        assert second["ok"] is True and third["ok"] is True
        assert second["result"]["state"] == "queued"
        assert third["result"]["state"] == "queued"
        message_b = second["result"]["message_id"]
        message_c = third["result"]["message_id"]
        for response in (second, third):
            assert response["result"]["dispatch_pump"]["dispatched"] == []
            assert response["result"]["dispatch_pump"]["skipped"][0]["code"] == "busy"
        busy_record = state.read_json("controller.json")
        busy_mailboxes = {
            item["message_id"]: item["state"]
            for item in busy_record["mailboxes"]
        }
        assert busy_mailboxes[message_b] == "queued"
        assert busy_mailboxes[message_c] == "queued"
        assert [item[1] for item in runtime.sent] == [message_a]

        runtime.busy = False
        assert runtime.second_send_started.wait(5.0), (
            "bounded pump did not accept B; controller="
            + json.dumps(controller.status(), sort_keys=True, default=str)
        )
        before_c = state.read_json("controller.json")
        before_c_history = copy.deepcopy(
            before_c["native_invocation_history"]
        )
        assert len(before_c_history) == 1
        history_a = next(iter(before_c_history.values()))
        assert history_a["invocation_id"] == message_a
        assert history_a["context"]["fenced"] is True

        runtime.allow_third_send.set()
        deadline = time.monotonic() + 5.0
        while len(runtime.sent) < 3 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert [item[1] for item in runtime.sent] == [
            message_a, message_b, message_c
        ]
    finally:
        runtime.allow_third_send.set()
        _stop_server_thread(socket_path, stop_event, thread)

    assert not thread.is_alive()
    assert errors == []
    final_record = state.read_json("controller.json")
    final_mailboxes = {
        item["message_id"]: item["state"]
        for item in final_record["mailboxes"]
    }
    assert [final_mailboxes[item] for item in (message_a, message_b, message_c)] == [
        "acknowledged", "acknowledged", "acknowledged",
    ]
    assert final_record["native_invocation_history"]
    assert final_record["native_context"]["invocation_id"] == message_c
    assert before_c_history[next(iter(before_c_history))] == (
        final_record["native_invocation_history"][next(iter(before_c_history))]
    )
    assert len(final_record["native_invocation_rollovers"]) == 2
    assert all(
        item["state"] == "delivered"
        for item in final_record["native_invocation_rollovers"].values()
    )
