# SPDX-License-Identifier: Apache-2.0
"""Fake-only controller tests for bounded same-runner invocation rollover.

These tests deliberately stop at the controller/runtime adapter boundary.  A
``prepare-invocation`` response is an implementation-owned reservation and
terminal-proof fixture; it is not a Claude API, an SDK session, or account
evidence.  The imported startup helpers exercise the existing first-mail
binding so the new tests cover the transition from a real invocation A to a
later invocation B rather than inventing a native context.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from typing import Any, Dict, Mapping, Optional

import pytest

from lane_managed_controller import ControllerError, LineageRecord
from test_lane_managed_controller import (
    NativeStartStore,
    StartRuntime,
    _native_start_controller,
    _native_start_definitions,
    _native_start_spec,
    _operation_id,
    _run_native_start,
    _run_release,
    _value,
)


PREPARE_REQUEST_FIELDS = frozenset({
    "schema_version",
    "architecture",
    "reservation_version",
    "reservation_id",
    "operation_id",
    "owner_generation",
    "daemon_id",
    "participant_id",
    "session_id",
    "runner_incarnation",
    "lineage_id",
    "lineage_generation",
    "prior_invocation_id",
    "next_invocation_id",
    "prior_mailbox_id",
    "next_mailbox_id",
    "prior_watermark",
    "definitions_digest",
    "permissions_digest",
    "claim_digest",
    "binding_digest",
})

_HISTORY_FIELDS = frozenset({
    "schema_version",
    "architecture",
    "record_kind",
    "history_schema",
    "history_id",
    "integrity_digest",
    "operation_id",
    "owner_generation",
    "lineage_id",
    "lineage_generation",
    "daemon_id",
    "coordinator",
    "runner_incarnation",
    "invocation_id",
    "mailbox_id",
    "context",
    "admissions",
    "terminal_controls",
    "terminal_result",
    "independent_drain",
    "joined_roster",
    "terminal_watermark",
    "source_watermark",
    "terminal_proof_digest",
    "runtime_correlation",
})

_ROLLOVER_FIELDS = frozenset({
    "schema_version",
    "architecture",
    "record_kind",
    "rollover_schema",
    "rollover_id",
    "integrity_digest",
    "operation_id",
    "owner_generation",
    "lineage_id",
    "lineage_generation",
    "daemon_id",
    "daemon_incarnation",
    "coordinator",
    "runner_incarnation",
    "prior_invocation_id",
    "next_invocation_id",
    "prior_mailbox_id",
    "next_mailbox_id",
    "preparation_intent",
    "history_id",
    "next_context",
    "startup_binding",
    "reservation_binding",
    "dispatch_intent",
    "reservation_version",
    "reservation_id",
    "prior_watermark",
    "next_watermark",
    "state",
    "uncertainty",
})

_FORBIDDEN_EVIDENCE_KEYS = {
    "body",
    "payload",
    "payload_ref",
    "payload_digest",
    "resolved_payload",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
    "api_key",
}


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_no_sensitive_evidence(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            assert str(key).casefold() not in _FORBIDDEN_EVIDENCE_KEYS
            _assert_no_sensitive_evidence(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_sensitive_evidence(child)


def _terminal_proof(request: Mapping[str, Any], *, complete: bool = True) -> Dict[str, Any]:
    """Build the exact proof envelope owned by the native adapter."""
    prior_watermark = int(request["prior_watermark"])
    result_watermark = prior_watermark + 1
    reader_drained_watermark = prior_watermark + 2
    roster = {
        "parent_state": "idle" if complete else "active",
        "children": [],
        "pending_admission_ids": [] if complete else ["admission-pending"],
        "pending_task_ids": [],
        "parent_active_tool_ids": [],
        "parent_uncertain_tool_ids": [],
        "parent_unresolved_effect_ids": [],
        "descendant_ids": [],
    }
    return {
        "parent_result": {
            "session_id": request["session_id"],
            "invocation_id": request["prior_invocation_id"],
            "message_id": request["prior_mailbox_id"],
            "result_watermark": result_watermark,
            "reader_drained_watermark": reader_drained_watermark,
        },
        "roster": roster,
        "roster_digest": _canonical_digest(roster),
        "observation_watermark": reader_drained_watermark,
        "uncertainty": [] if complete else ["parent-not-terminal"],
        "overflow": False,
    }


def _reservation_response(
        request: Mapping[str, Any], *, state: str = "reserved",
        complete: bool = True,
) -> Dict[str, Any]:
    response = copy.deepcopy(dict(request))
    response["state"] = state
    if state == "reserved":
        proof = _terminal_proof(request, complete=complete)
        response.update({
            "terminal_watermark": proof["observation_watermark"],
            "next_watermark": proof["observation_watermark"] + 1,
            "terminal_proof": proof,
            "terminal_proof_digest": _canonical_digest(proof),
        })
    return response


class RolloverRuntime(StartRuntime):
    """Startup/send fake plus the implementation-owned reservation frame."""

    def __init__(
            self,
            *,
            prepare_state: str = "reserved",
            prepare_complete: bool = True,
            fail_send_after: bool = False,
    ) -> None:
        super().__init__()
        self.prepare_state = prepare_state
        self.prepare_complete = prepare_complete
        self.fail_send_after = fail_send_after
        self.prepare_requests: list[Dict[str, Any]] = []
        self.prepare_responses: Dict[str, Dict[str, Any]] = {}
        self.prepare_started = asyncio.Event()
        self.allow_prepare = asyncio.Event()
        self.gate_prepare = False
        self.send_started = asyncio.Event()
        self.allow_send = asyncio.Event()
        self.gate_send = False

    async def prepare_invocation(
            self, participant_id: str, request: Mapping[str, Any], *,
            deadline: Any = None,
    ) -> Dict[str, Any]:
        assert participant_id == request["participant_id"]
        assert set(request) == PREPARE_REQUEST_FIELDS
        captured = copy.deepcopy(dict(request))
        self.prepare_requests.append(captured)
        self.prepare_started.set()
        if self.gate_prepare:
            await self.allow_prepare.wait()
        reservation_id = str(request["reservation_id"])
        if reservation_id not in self.prepare_responses:
            self.prepare_responses[reservation_id] = _reservation_response(
                request,
                state=self.prepare_state,
                complete=self.prepare_complete,
            )
        return copy.deepcopy(self.prepare_responses[reservation_id])

    async def send(
            self, participant_id: str, message_id: str, payload_ref: Any
    ) -> Dict[str, Any]:
        self.send_started.set()
        if self.gate_send:
            await self.allow_send.wait()
        result = await super().send(participant_id, message_id, payload_ref)
        if self.fail_send_after:
            raise RuntimeError("injected ambiguous rollover send")
        return result


class BusyThenReservedRuntime(RolloverRuntime):
    """Model the SDK's pre-reservation busy refusal, then terminal proof."""

    def __init__(self) -> None:
        super().__init__()
        self.prepare_attempts = 0

    async def prepare_invocation(
            self, participant_id: str, request: Mapping[str, Any], *,
            deadline: Any = None,
    ) -> Dict[str, Any]:
        self.prepare_attempts += 1
        self.prepare_requests.append(copy.deepcopy(dict(request)))
        self.prepare_started.set()
        if self.prepare_attempts == 1:
            refusal = RuntimeError("native parent invocation is not terminal and drained")
            refusal.code = "busy"  # type: ignore[attr-defined]
            raise refusal
        reservation_id = str(request["reservation_id"])
        if reservation_id not in self.prepare_responses:
            self.prepare_responses[reservation_id] = _reservation_response(request)
        return copy.deepcopy(self.prepare_responses[reservation_id])


def _released_native_fixture(*, runtime: Optional[RolloverRuntime] = None):
    selected_runtime = RolloverRuntime() if runtime is None else runtime
    controller, store, coordinator, _workers, specs = _native_start_controller(
        runtime=selected_runtime
    )
    controller.payload_resolver = lambda payload_ref: str(payload_ref)
    started = _run_native_start(
        controller,
        request_id="rollover-start",
        coordinator=coordinator,
        runner_spec=specs[coordinator.participant_id],
    )
    released = _run_release(controller, _operation_id(started))
    operation_id = _operation_id(released)
    first = controller.submit(
        "rollover-mail-a",
        coordinator.participant_id,
        "opaque://mail-a",
        sender_id="user",
        task_id="task-root-coordinator",
        generation=7,
    )
    # Failure injection belongs to the later B dispatch.  Let the initial A
    # invocation establish the released fixture before exercising an
    # ambiguous send during rollover.
    initial_failure = getattr(selected_runtime, "fail_send_after", None)
    if initial_failure is not None:
        selected_runtime.fail_send_after = False
    try:
        sent = asyncio.run(controller.dispatch_next(
            operation_id, recipient_id=coordinator.participant_id
        ))
    finally:
        if initial_failure is not None:
            selected_runtime.fail_send_after = initial_failure
    assert _value(sent, "message_id") == _value(first, "message_id")
    assert _value(sent, "state") == "acknowledged"
    return controller, store, selected_runtime, coordinator, released, first


def _submit_next(controller: Any, coordinator: Any, request_id: str = "rollover-mail-b"):
    return controller.submit(
        request_id,
        coordinator.participant_id,
        "opaque://mail-b",
        sender_id="user",
        task_id="task-root-coordinator",
        generation=7,
    )


def _latest_records(store: NativeStartStore):
    record = copy.deepcopy(store.documents["controller.json"])
    histories = record.get("native_invocation_history", {})
    rollovers = record.get("native_invocation_rollovers", {})
    assert isinstance(histories, Mapping)
    assert isinstance(rollovers, Mapping)
    assert len(histories) == 1
    assert len(rollovers) == 1
    return record, next(iter(histories.values())), next(iter(rollovers.values()))


def test_same_runner_rollover_requires_exact_terminal_reservation_and_binds_once():
    controller, store, runtime, coordinator, released, first = _released_native_fixture()
    second = _submit_next(controller, coordinator)

    dispatched = asyncio.run(controller.dispatch_next(
        _operation_id(released), recipient_id=coordinator.participant_id
    ))

    assert _value(dispatched, "message_id") == _value(second, "message_id")
    assert _value(dispatched, "state") == "acknowledged"
    assert len(runtime.prepare_requests) == 1
    request = runtime.prepare_requests[0]
    assert set(request) == PREPARE_REQUEST_FIELDS
    assert request["schema_version"] == 2
    assert request["architecture"] == "native-coordinator-lineage"
    assert request["reservation_version"] == 1
    assert request["operation_id"] == _operation_id(released)
    assert request["owner_generation"] == 7
    assert request["daemon_id"] == "daemon-test"
    assert request["participant_id"] == coordinator.participant_id
    assert request["session_id"] == coordinator.session_id
    assert request["prior_invocation_id"] == _value(first, "message_id")
    assert request["next_invocation_id"] == _value(second, "message_id")
    assert request["prior_mailbox_id"] == _value(first, "message_id")
    assert request["next_mailbox_id"] == _value(second, "message_id")
    assert request["lineage_id"] == "native-start-lineage"
    assert request["lineage_generation"] == 1
    assert isinstance(request["prior_watermark"], int)
    for key in (
        "definitions_digest",
        "permissions_digest",
        "claim_digest",
        "binding_digest",
    ):
        assert isinstance(request[key], str) and len(request[key]) == 64

    response = runtime.prepare_responses[request["reservation_id"]]
    assert response["state"] == "reserved"
    assert response["terminal_watermark"] > response["prior_watermark"]
    assert response["next_watermark"] > response["terminal_watermark"]
    assert response["terminal_proof_digest"] == _canonical_digest(
        response["terminal_proof"]
    )
    proof = response["terminal_proof"]
    assert proof["parent_result"]["invocation_id"] == request["prior_invocation_id"]
    assert proof["parent_result"]["message_id"] == request["prior_mailbox_id"]
    assert proof["parent_result"]["session_id"] == request["session_id"]
    assert (
        proof["parent_result"]["result_watermark"]
        <= proof["parent_result"]["reader_drained_watermark"]
        <= proof["observation_watermark"]
    )
    assert proof["roster"]["parent_state"] == "idle"
    assert proof["roster"]["pending_admission_ids"] == []
    assert proof["roster"]["pending_task_ids"] == []
    assert proof["roster"]["parent_active_tool_ids"] == []
    assert proof["roster"]["parent_uncertain_tool_ids"] == []
    assert proof["roster"]["parent_unresolved_effect_ids"] == []
    assert proof["roster"]["descendant_ids"] == []
    assert proof["uncertainty"] == []
    assert proof["overflow"] is False

    record, history, rollover = _latest_records(store)
    assert set(history) == _HISTORY_FIELDS
    assert history["record_kind"] == "native-invocation-history"
    assert history["history_schema"] == 1
    assert history["operation_id"] == _operation_id(released)
    assert history["invocation_id"] == _value(first, "message_id")
    assert history["mailbox_id"] == _value(first, "message_id")
    assert history["terminal_watermark"] == response["terminal_watermark"]
    assert history["source_watermark"] == request["prior_watermark"]
    assert history["terminal_proof_digest"] == response["terminal_proof_digest"]
    assert history["coordinator"]["session_uuid"] == coordinator.session_id
    assert set(rollover) == _ROLLOVER_FIELDS
    assert rollover["record_kind"] == "native-invocation-rollover"
    assert rollover["rollover_schema"] == 1
    assert rollover["prior_invocation_id"] == _value(first, "message_id")
    assert rollover["next_invocation_id"] == _value(second, "message_id")
    assert rollover["prior_mailbox_id"] == _value(first, "message_id")
    assert rollover["next_mailbox_id"] == _value(second, "message_id")
    assert rollover["reservation_id"] == request["reservation_id"]
    assert rollover["reservation_binding"]["reservation_id"] == request["reservation_id"]
    assert rollover["dispatch_intent"]["message_id"] == _value(second, "message_id")
    assert rollover["state"] == "delivered"
    assert rollover["uncertainty"] is None
    assert record["native_context"]["invocation_id"] == _value(second, "message_id")
    assert record["native_context"]["invocation_watermark"] == response["next_watermark"]
    assert record["operations"][-1]["metadata"]["native_startup"]["invocation_id"] == (
        _value(second, "message_id")
    )
    assert [item[1] for item in runtime.sent] == [
        _value(first, "message_id"), _value(second, "message_id")
    ]
    _assert_no_sensitive_evidence(history)
    _assert_no_sensitive_evidence(rollover)


def test_rollover_persists_preparation_before_await_without_controller_lock_or_effect():
    runtime = RolloverRuntime()
    runtime.gate_prepare = True
    controller, store, runtime, coordinator, released, first = _released_native_fixture(
        runtime=runtime
    )
    second = _submit_next(controller, coordinator)

    async def scenario():
        task = asyncio.create_task(controller.dispatch_next(
            _operation_id(released), recipient_id=coordinator.participant_id
        ))
        await asyncio.wait_for(runtime.prepare_started.wait(), 1)
        # The runtime reservation is awaited outside the controller
        # transaction.  A status read must remain available and show the
        # original A context while the B preparation intent is pending.
        status = controller.status()
        durable = copy.deepcopy(store.documents["controller.json"])
        assert status["native_context"]["invocation_id"] == _value(first, "message_id")
        assert _value(
            next(item for item in status["mailboxes"]
                 if item["message_id"] == _value(second, "message_id")),
            "state",
        ) == "queued"
        pending = durable["native_invocation_rollovers"]
        assert len(pending) == 1
        pending_record = next(iter(pending.values()))
        assert pending_record["state"] == "preparation-pending"
        assert pending_record["preparation_intent"]["next_mailbox_id"] == (
            _value(second, "message_id")
        )
        assert durable.get("native_invocation_history", {}) in ({}, None)
        assert runtime.sent == [(
            coordinator.participant_id,
            _value(first, "message_id"),
            "opaque://mail-a",
        )]
        runtime.allow_prepare.set()
        await asyncio.wait_for(task, 1)

    asyncio.run(scenario())


def test_busy_terminal_proof_leaves_next_mail_queued_and_does_not_consume_reservation():
    runtime = RolloverRuntime(prepare_state="busy", prepare_complete=False)
    controller, store, runtime, coordinator, released, first = _released_native_fixture(
        runtime=runtime
    )
    second = _submit_next(controller, coordinator)

    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.dispatch_next(
            _operation_id(released), recipient_id=coordinator.participant_id
        ))
    assert raised.value.code == "busy"
    assert len(runtime.prepare_requests) == 1
    mailbox = next(item for item in controller.status()["mailboxes"]
                   if item["message_id"] == _value(second, "message_id"))
    assert mailbox["state"] == "queued"
    assert controller.status()["native_context"]["invocation_id"] == _value(
        first, "message_id"
    )
    assert controller.status().get("native_invocation_history", {}) in ({}, None)
    assert runtime.sent == [(
        coordinator.participant_id,
        _value(first, "message_id"),
        "opaque://mail-a",
    )]
    assert not runtime.prepare_responses[ runtime.prepare_requests[0]["reservation_id"] ].get(
        "terminal_proof"
    )
    assert store.documents["controller.json"].get("native_invocation_history", {}) in ({}, None)


def test_pre_reservation_busy_retries_same_request_after_parent_terminal():
    runtime = BusyThenReservedRuntime()
    controller, store, runtime, coordinator, released, first = _released_native_fixture(
        runtime=runtime
    )
    second = _submit_next(controller, coordinator, "rollover-busy-then-terminal")

    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.dispatch_next(
            _operation_id(released), recipient_id=coordinator.participant_id
        ))
    assert raised.value.code == "busy"
    durable = store.documents["controller.json"]
    pending = next(iter(durable["native_invocation_rollovers"].values()))
    assert pending["state"] == "preparation-pending"
    assert pending["uncertainty"]["reservation_outcome"] == "not-reserved"
    assert next(item for item in controller.status()["mailboxes"]
                if item["message_id"] == _value(second, "message_id"))["state"] == "queued"

    delivered = asyncio.run(controller.dispatch_next(
        _operation_id(released), recipient_id=coordinator.participant_id
    ))
    assert _value(delivered, "message_id") == _value(second, "message_id")
    assert runtime.prepare_attempts == 2
    assert runtime.prepare_requests[0]["reservation_id"] == runtime.prepare_requests[1]["reservation_id"]
    assert runtime.prepare_requests[0]["binding_digest"] == runtime.prepare_requests[1]["binding_digest"]
    assert [item[1] for item in runtime.sent] == [
        _value(first, "message_id"), _value(second, "message_id")
    ]


def test_competing_rollover_pump_cannot_issue_second_reservation_or_change_seal():
    runtime = RolloverRuntime()
    runtime.gate_prepare = True
    controller, store, runtime, coordinator, released, first = _released_native_fixture(
        runtime=runtime
    )
    second = _submit_next(controller, coordinator, "rollover-mail-b1")
    third = _submit_next(controller, coordinator, "rollover-mail-b2")

    async def scenario():
        first_task = asyncio.create_task(controller.dispatch_next(
            _operation_id(released), recipient_id=coordinator.participant_id
        ))
        await asyncio.wait_for(runtime.prepare_started.wait(), 1)
        with pytest.raises(ControllerError) as raised:
            await controller.dispatch_next(
                _operation_id(released), recipient_id=coordinator.participant_id
            )
        assert raised.value.code in {"busy", "conflict", "uncertain-effect"}
        assert len(runtime.prepare_requests) == 1
        runtime.allow_prepare.set()
        delivered = await asyncio.wait_for(first_task, 1)
        assert _value(delivered, "message_id") == _value(second, "message_id")

    asyncio.run(scenario())
    assert len(runtime.prepare_requests) == 1
    assert runtime.prepare_requests[0]["next_mailbox_id"] == _value(second, "message_id")
    remaining = next(item for item in controller.status()["mailboxes"]
                     if item["message_id"] == _value(third, "message_id"))
    assert remaining["state"] == "queued"
    record = store.documents["controller.json"]
    assert len(record["native_invocation_rollovers"]) == 1


def test_phase_change_after_reservation_refuses_before_send_and_keeps_b_queued():
    runtime = RolloverRuntime()
    runtime.gate_prepare = True
    controller, store, runtime, coordinator, released, first = _released_native_fixture(
        runtime=runtime
    )
    second = _submit_next(controller, coordinator)

    async def scenario():
        task = asyncio.create_task(controller.dispatch_next(
            _operation_id(released), recipient_id=coordinator.participant_id
        ))
        await asyncio.wait_for(runtime.prepare_started.wait(), 1)
        with controller._transaction():
            operation = controller._operations[_operation_id(released)]
            operation.phase = "ready-held"
            controller._persist({"event": "test-phase-fence"})
        runtime.allow_prepare.set()
        with pytest.raises(ControllerError) as raised:
            await asyncio.wait_for(task, 1)
        assert raised.value.code == "busy"

    asyncio.run(scenario())
    assert runtime.sent == [(
        coordinator.participant_id,
        _value(first, "message_id"),
        "opaque://mail-a",
    )]
    mailbox = next(item for item in controller.status()["mailboxes"]
                   if item["message_id"] == _value(second, "message_id"))
    assert mailbox["state"] == "queued"
    assert store.documents["controller.json"].get("native_invocation_history", {}) in ({}, None)


def test_ambiguous_rollover_send_marks_mutable_record_uncertain_without_replaying_history():
    runtime = RolloverRuntime(fail_send_after=True)
    controller, store, runtime, coordinator, released, first = _released_native_fixture(
        runtime=runtime
    )
    second = _submit_next(controller, coordinator)

    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.dispatch_next(
            _operation_id(released), recipient_id=coordinator.participant_id
        ))
    assert raised.value.code == "uncertain-effect"
    record, history, rollover = _latest_records(store)
    history_digest = history["integrity_digest"]
    assert rollover["state"] == "uncertain"
    assert rollover["uncertainty"]
    assert next(item for item in record["mailboxes"]
                if item["message_id"] == _value(second, "message_id"))["state"] == "uncertain"
    calls = len(runtime.sent)
    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.dispatch_next(
            _operation_id(released), recipient_id=coordinator.participant_id
        ))
    assert raised.value.code in {"uncertain-effect", "busy"}
    assert len(runtime.sent) == calls
    current_history = next(iter(store.documents["controller.json"][
        "native_invocation_history"
    ].values()))
    assert current_history["integrity_digest"] == history_digest


def test_stale_invocation_a_callback_cannot_replace_current_b_context_or_history():
    controller, store, runtime, coordinator, released, first = _released_native_fixture()
    second = _submit_next(controller, coordinator)
    asyncio.run(controller.dispatch_next(
        _operation_id(released), recipient_id=coordinator.participant_id
    ))
    before = copy.deepcopy(store.documents["controller.json"])
    context = before["native_context"]
    with pytest.raises(ControllerError) as raised:
        controller.register_native_context(
            7,
            LineageRecord.from_dict(context["lineage"]),
            context["runner_incarnation"],
            _value(first, "message_id"),
            _native_start_definitions(),
            invocation_watermark=context["invocation_watermark"],
        )
    assert raised.value.code == "busy"
    after = store.documents["controller.json"]
    assert after["native_context"]["invocation_id"] == _value(second, "message_id")
    assert after["native_invocation_history"] == before["native_invocation_history"]
