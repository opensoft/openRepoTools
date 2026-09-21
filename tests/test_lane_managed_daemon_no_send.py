# SPDX-License-Identifier: Apache-2.0
"""Daemon entry routing for private native-reservation no-send recovery.

These tests cover only the supervisor/controller seam.  The controller stub
stands in for the frozen private recovery consumer; it does not manufacture a
runtime no-send receipt.  The real controller/runtime evidence path remains a
separate implementation tranche.
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any, Mapping

import pytest

from lane_managed_controller import Operation
from lane_managed_daemon import ManagedDaemon


LANE = "recovery"
GENERATION = 11
DAEMON_ID = "daemon-native-recovery"
OPERATION_ID = "operation-native-recovery"
SESSION_ID = "session-native-recovery"
RUNNER_ID = "runner-native-recovery"
LINEAGE_ID = "lineage-native-recovery"
PRIOR_MESSAGE_ID = "mail-A"
NEXT_MESSAGE_ID = "mail-B"


def _owner(
        *, daemon_id: str = DAEMON_ID, generation: int = GENERATION,
) -> dict[str, Any]:
    return {
        "mode": "managed",
        "lane": LANE,
        "generation": generation,
        "daemon_id": daemon_id,
    }


class OwnerState:
    def __init__(self, owner: Mapping[str, Any] | None = None) -> None:
        self.owner = dict(owner or _owner())
        self.reads = 0

    async def read_owner(self, *, deadline: float | None = None) -> dict[str, Any]:
        del deadline
        self.reads += 1
        return copy.deepcopy(self.owner)


def _rollover(*, state: str = "uncertain") -> dict[str, Any]:
    return {
        "record_kind": "native-invocation-rollover",
        "rollover_schema": 1,
        "rollover_id": "rollover-native-recovery",
        "integrity_digest": "d" * 64,
        "operation_id": OPERATION_ID,
        "owner_generation": GENERATION,
        "lineage_id": LINEAGE_ID,
        "lineage_generation": 1,
        "daemon_id": DAEMON_ID,
        "daemon_incarnation": DAEMON_ID,
        "coordinator": {
            "participant_id": "coordinator",
            "session_uuid": SESSION_ID,
        },
        "runner_incarnation": RUNNER_ID,
        "prior_invocation_id": PRIOR_MESSAGE_ID,
        "next_invocation_id": NEXT_MESSAGE_ID,
        "prior_mailbox_id": PRIOR_MESSAGE_ID,
        "next_mailbox_id": NEXT_MESSAGE_ID,
        "preparation_intent": {"state": "pending"},
        "history_id": "history-native-recovery",
        "next_context": {"invocation_id": NEXT_MESSAGE_ID},
        "startup_binding": {"runner_instance_id": RUNNER_ID},
        "reservation_binding": {"reservation_id": "reservation-native-recovery"},
        "dispatch_intent": {
            "message_id": NEXT_MESSAGE_ID,
            "operation_id": OPERATION_ID,
            "attempt": 1,
        },
        "reservation_version": 1,
        "reservation_id": "reservation-native-recovery",
        "prior_watermark": 10,
        "next_watermark": 12,
        "state": state,
        "uncertainty": {
            "stage": "send",
            "reason": "transport outcome is unresolved",
        },
    }


def _operation(*, mode: str = "start", native_swap_metadata: bool = False) -> dict[str, Any]:
    metadata = {
        "native_startup": {
            "participant_id": "coordinator",
            "session_id": SESSION_ID,
        },
        "runner_instances": {"coordinator": RUNNER_ID},
    }
    if native_swap_metadata:
        metadata["native_swap"] = {
            "state": "ready-held",
            "target_runner_instance_id": RUNNER_ID,
        }
    return {
        "operation_id": OPERATION_ID,
        "request_id": "request-native-recovery",
        "mode": mode,
        "generation": GENERATION,
        "phase": "released",
        "sealed_participants": ["coordinator"],
        "release_count": 1,
        "readiness": {"coordinator": {"session_id": SESSION_ID}},
        "uncertainty": ["mail:%s" % NEXT_MESSAGE_ID],
        "metadata": metadata,
    }


def _status(
        *, rollover_rows: Mapping[str, Any] | None = None,
        generation: int = GENERATION,
        phase: str = "released",
        prior_state: str = "acknowledged",
        next_state: str = "dispatch-intent",
        mode: str = "start",
        native_swap_metadata: bool = False,
) -> dict[str, Any]:
    operation = _operation(
        mode=mode,
        native_swap_metadata=native_swap_metadata,
    )
    operation["generation"] = generation
    operation["phase"] = phase
    rows = (
        dict(rollover_rows)
        if rollover_rows is not None
        else {"rollover-native-recovery": _rollover()}
    )
    return {
        "generation": generation,
        "operation": operation,
        "active_operation": operation,
        "active_operation_id": OPERATION_ID,
        "native_context": {
            "lineage": {
                "owner_generation": GENERATION,
                "lineage_id": LINEAGE_ID,
                "lineage_generation": 1,
                "session_uuid": SESSION_ID,
            },
            "runner_incarnation": RUNNER_ID,
            "invocation_id": PRIOR_MESSAGE_ID,
            "fenced": False,
        },
        "native_invocation_rollovers": rows,
        "participants": [{
            "participant_id": "coordinator",
            "session_id": SESSION_ID,
            "metadata": {"runner_instance_id": RUNNER_ID},
        }],
        "mailboxes": [
            {
                "message_id": PRIOR_MESSAGE_ID,
                "recipient_id": "coordinator",
                "session_id": SESSION_ID,
                "operation_id": OPERATION_ID,
                "generation": GENERATION,
                "state": prior_state,
            },
            {
                "message_id": NEXT_MESSAGE_ID,
                "recipient_id": "coordinator",
                "session_id": SESSION_ID,
                "operation_id": OPERATION_ID,
                "generation": GENERATION,
                "state": next_state,
            },
        ],
    }


class RecoveryController:
    """Bounded stand-in for the controller's private native recovery consumer."""

    def __init__(self, status: Mapping[str, Any] | None = None) -> None:
        self.status_value = copy.deepcopy(status or _status())
        self.status_calls = 0
        self.recover_calls: list[tuple[Any, ...]] = []

    def status(self) -> dict[str, Any]:
        self.status_calls += 1
        return copy.deepcopy(self.status_value)

    async def recover(self, operation_id: str, generation: int) -> Operation:
        self.recover_calls.append((operation_id, generation))
        raw = copy.deepcopy(self.status_value["operation"])
        raw["phase"] = "released"
        return Operation.from_dict(raw)


class Runtime:
    async def status(self, participant_id: str) -> dict[str, Any]:
        raise AssertionError(
            "native rollover entry routing must not collect generic runtime evidence"
        )


def _daemon(
        controller: RecoveryController, *, state: OwnerState | None = None,
) -> ManagedDaemon:
    daemon = ManagedDaemon(
        state=state or OwnerState(),
        controller=controller,
        adapter=Runtime(),
        daemon_id=DAEMON_ID,
        opt_in=True,
        lane=LANE,
    )
    daemon.owner_record = _owner()
    daemon._owner_enrolled = True
    daemon.started = True
    return daemon


def _request() -> dict[str, Any]:
    return {
        "schema": 2,
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "request_id": "recover-native-request",
        "lane": LANE,
        "generation": GENERATION,
        "operation": "recover",
        "body": {"operation_id": OPERATION_ID},
    }


def test_native_rollover_recovery_skips_generic_collector_and_pump() -> None:
    async def scenario() -> None:
        controller = RecoveryController()
        daemon = _daemon(controller)

        async def forbidden_collector(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            raise AssertionError("generic recovery evidence collector was used")

        async def forbidden_pump(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            raise AssertionError("native recovery must not inline a dispatch pump")

        daemon._collect_recovery_evidence = forbidden_collector  # type: ignore[method-assign]
        daemon.dispatch_pump_tick = forbidden_pump  # type: ignore[method-assign]

        response = await daemon.handle_request(_request())

        assert response["ok"] is True
        assert controller.recover_calls == [(OPERATION_ID, GENERATION)]
        assert controller.status_calls >= 2

    asyncio.run(scenario())


def test_native_swap_rollover_recovery_uses_private_route() -> None:
    async def scenario() -> None:
        controller = RecoveryController(
            _status(mode="swap", native_swap_metadata=True)
        )
        daemon = _daemon(controller)

        async def forbidden_collector(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            raise AssertionError("generic recovery evidence collector was used")

        daemon._collect_recovery_evidence = forbidden_collector  # type: ignore[method-assign]
        response = await daemon.handle_request(_request())

        assert response["ok"] is True
        assert response["result"]["mode"] == "swap"
        assert controller.recover_calls == [(OPERATION_ID, GENERATION)]

    asyncio.run(scenario())


def test_native_rollover_recovery_refuses_legacy_boundary() -> None:
    async def scenario() -> None:
        controller = RecoveryController(_status(mode="add-worker"))
        daemon = _daemon(controller)
        response = await daemon.handle_request(_request())

        assert response["ok"] is False
        assert response["code"] == "unsupported"
        assert controller.recover_calls == []
        assert controller.status_calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mutate, expected_code",
    [
        (lambda value: {**value, "daemon_id": "replacement-daemon"}, "ownership-conflict"),
        (lambda value: {**value, "owner_generation": GENERATION + 1}, "stale-generation"),
        (lambda value: {**value, "operation_id": "other-operation"}, "stale-generation"),
        (lambda value: {**value, "state": "delivered"}, "uncertain-effect"),
    ],
)
def test_native_rollover_recovery_refuses_stale_or_noncurrent_authority(
        mutate: Any, expected_code: str,
) -> None:
    async def checked() -> None:
        row = _rollover()
        mutated = mutate(row)
        controller = RecoveryController(
            _status(rollover_rows={"rollover-native-recovery": mutated})
        )
        daemon = _daemon(controller)
        if expected_code == "ownership-conflict":
            daemon.owner_record = _owner(daemon_id="replacement-daemon")
        response = await daemon.handle_request(_request())
        assert response["ok"] is False
        assert response["code"] == expected_code
        assert controller.recover_calls == []

    asyncio.run(checked())


def test_native_rollover_recovery_refuses_duplicate_unresolved_records() -> None:
    async def scenario() -> None:
        first = _rollover()
        second = _rollover()
        second["rollover_id"] = "rollover-native-recovery-2"
        controller = RecoveryController(
            _status(rollover_rows={"first": first, "second": second})
        )
        daemon = _daemon(controller)

        response = await daemon.handle_request(_request())

        assert response["ok"] is False
        assert response["code"] in {"invalid", "uncertain-effect", "busy"}
        assert controller.recover_calls == []

    asyncio.run(scenario())


def test_native_rollover_recovery_refuses_live_original_dispatch() -> None:
    async def scenario() -> None:
        controller = RecoveryController()
        daemon = _daemon(controller)
        lock = daemon._dispatch_lock_for_loop()
        await lock.acquire()
        try:
            response = await daemon.handle_request(_request())
        finally:
            lock.release()

        assert response["ok"] is False
        assert response["code"] in {"busy", "uncertain-effect"}
        assert controller.recover_calls == []

    asyncio.run(scenario())


def test_public_recover_rejects_caller_no_send_proof_without_controller_call() -> None:
    async def scenario() -> None:
        controller = RecoveryController()
        daemon = _daemon(controller)
        request = _request()
        request["body"] = {
            "operation_id": OPERATION_ID,
            "no_send": True,
        }

        response = await daemon.handle_request(request)

        assert response["ok"] is False
        assert response["code"] == "invalid"
        assert controller.status_calls == 0
        assert controller.recover_calls == []

    asyncio.run(scenario())
