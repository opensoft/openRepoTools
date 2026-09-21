# SPDX-License-Identifier: Apache-2.0
"""Fresh-controller recovery at the durable native rollover boundaries.

The companion rollover tests cover one live controller from preparation through
delivery.  These tests deliberately reload a second controller from the real
durable snapshots at each crash window.  Runtime preparation/send callbacks
only observe those snapshots (and optionally cancel); they do not forge a
finalized record or bypass any controller validator.
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any, Callable, Dict, Mapping, Optional

import pytest

from lane_managed_controller import ControllerError, ManagedController
from test_lane_managed_controller_rollover import (
    RolloverRuntime,
    _canonical_digest,
    _operation_id,
    _released_native_fixture,
    _submit_next,
    _value,
)


_NATIVE_NO_SEND_RECEIPT_FIELDS = frozenset({
    "schema_version",
    "architecture",
    "record_kind",
    "observation_id",
    "reservation_binding",
    "reservation_digest",
    "observation_watermark",
    "state",
    "transport_attempted",
    "receipt_digest",
})
_NATIVE_NO_SEND_CONSUMPTION_FIELDS = frozenset({
    "observation_id",
    "receipt_digest",
    "mailbox_id",
    "consumed",
})


def _native_no_send_receipt(
        reservation: Mapping[str, Any], *, observation_id: str,
        observation_watermark: int,
) -> Dict[str, Any]:
    receipt = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-reservation-no-send",
        "observation_id": observation_id,
        "reservation_binding": copy.deepcopy(dict(reservation)),
        "reservation_digest": _canonical_digest(reservation),
        "observation_watermark": observation_watermark,
        "state": "reserved-unconsumed",
        "transport_attempted": False,
        "receipt_digest": "",
    }
    receipt["receipt_digest"] = _canonical_digest(
        {key: value for key, value in receipt.items() if key != "receipt_digest"}
    )
    return receipt


def _refresh_no_send_receipt_digest(receipt: Mapping[str, Any]) -> Dict[str, Any]:
    refreshed = copy.deepcopy(dict(receipt))
    refreshed["receipt_digest"] = _canonical_digest(
        {key: value for key, value in refreshed.items() if key != "receipt_digest"}
    )
    return refreshed


def _refresh_reservation_digest(receipt: Mapping[str, Any]) -> Dict[str, Any]:
    refreshed = copy.deepcopy(dict(receipt))
    reservation = refreshed.get("reservation_binding")
    assert isinstance(reservation, Mapping)
    refreshed["reservation_digest"] = _canonical_digest(reservation)
    return _refresh_no_send_receipt_digest(refreshed)


def _native_no_send_consumption(
        receipt: Mapping[str, Any], mailbox_id: str,
) -> Dict[str, Any]:
    return {
        "observation_id": receipt["observation_id"],
        "receipt_digest": receipt["receipt_digest"],
        "mailbox_id": mailbox_id,
        "consumed": True,
    }


def _refresh_rollover_integrity(rollover: Mapping[str, Any]) -> Dict[str, Any]:
    refreshed = copy.deepcopy(dict(rollover))
    refreshed["integrity_digest"] = _canonical_digest({
        key: value for key, value in refreshed.items()
        if key != "integrity_digest"
    })
    return refreshed


class RecoveryRuntime(RolloverRuntime):
    """Rollover runtime with observation seams immediately before boundaries."""

    def __init__(self) -> None:
        super().__init__()
        self.prepare_observer: Optional[Callable[..., Any]] = None
        self.send_observer: Optional[Callable[..., Any]] = None
        self.status_calls = 0
        self.status_receipt_mode = "missing"
        self.cached_reservation: Optional[Dict[str, Any]] = None
        self.cached_receipt: Optional[Dict[str, Any]] = None
        self.receipt_mutator: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
        self.reuse_status_receipt = False
        self.no_send_message_id: Optional[str] = None
        self.transport_attempted_message_ids: set[str] = set()
        self.cancel_after_transport_marker = False

    def cache_no_send_reservation(self, response: Mapping[str, Any]) -> None:
        """Retain the adapter-owned reservation returned before controller bind."""
        assert response.get("state") == "reserved"
        self.cached_reservation = copy.deepcopy(dict(response))
        self.status_receipt_mode = "valid"
        self.cached_receipt = None

    async def status(self, participant_id: str) -> Dict[str, Any]:
        result = await super().status(participant_id)
        self.status_calls += 1
        if self.status_receipt_mode == "valid":
            reservation = self.cached_reservation
            assert reservation is not None
            if self.reuse_status_receipt and self.cached_receipt is not None:
                receipt = copy.deepcopy(self.cached_receipt)
            else:
                receipt = _native_no_send_receipt(
                    reservation,
                    observation_id="status-%d" % self.status_calls,
                    observation_watermark=reservation["terminal_watermark"],
                )
                self.cached_receipt = copy.deepcopy(receipt)
            if self.receipt_mutator is not None:
                receipt = self.receipt_mutator(copy.deepcopy(receipt))
            result["evidence"]["native_reservation_no_send"] = receipt
        elif self.status_receipt_mode == "malformed":
            result["evidence"]["native_reservation_no_send"] = {
                "record_kind": "native-reservation-no-send",
                "transport_attempted": False,
            }
        return result

    async def prepare_invocation(
            self, participant_id: str, request: Mapping[str, Any], *,
            deadline: Any = None,
    ) -> Dict[str, Any]:
        response = await super().prepare_invocation(
            participant_id, request, deadline=deadline,
        )
        if self.prepare_observer is not None:
            self.prepare_observer(
                self, copy.deepcopy(dict(request)), copy.deepcopy(response),
            )
        return response

    async def send(
            self, participant_id: str, message_id: str, payload_ref: Any,
    ) -> Dict[str, Any]:
        self.send_started.set()
        if self.send_observer is not None:
            self.send_observer(self, participant_id, message_id, payload_ref)
        # This marker is deliberately before entering the inherited send
        # implementation.  A cancellation from send_observer is therefore a
        # genuine pre-transport crash, while a cancellation after this line
        # must never be presented as proven no-send evidence.
        if message_id == self.no_send_message_id:
            self.transport_attempted_message_ids.add(message_id)
            if self.cancel_after_transport_marker:
                raise asyncio.CancelledError()
        return await super().send(participant_id, message_id, payload_ref)


def _durable_record(store: Any) -> Dict[str, Any]:
    """Read the latest store-written controller snapshot, not controller memory."""
    assert store.write_calls
    name, written = store.write_calls[-1]
    assert name == "controller.json"
    assert store.documents["controller.json"] == written
    return copy.deepcopy(written)


def _authority_snapshot(store: Any) -> Dict[str, Any]:
    record = _durable_record(store)
    return {
        "native_context": copy.deepcopy(record.get("native_context")),
        "native_invocation_history": copy.deepcopy(
            record.get("native_invocation_history")
        ),
        "lineage_claims": copy.deepcopy(getattr(store, "lineage_claims", [])),
    }


def _fresh_reload(store: Any, *, runtime: Any) -> tuple[ManagedController, Dict[str, Any]]:
    """Reload and status-read without allowing a constructor/read to write."""
    writes = copy.deepcopy(store.write_calls)
    journal = copy.deepcopy(store.journal)
    controller = ManagedController(
        store,
        runtime=runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    controller.payload_resolver = lambda payload_ref: str(payload_ref)
    status = controller.status()
    assert store.write_calls == writes
    assert store.journal == journal
    return controller, status


def _only_rollover(status: Mapping[str, Any]) -> Dict[str, Any]:
    rollovers = status.get("native_invocation_rollovers")
    assert isinstance(rollovers, Mapping)
    assert len(rollovers) == 1
    return copy.deepcopy(next(iter(rollovers.values())))


def _assert_preparation_pending(
        status: Mapping[str, Any], *, prior_id: str, next_id: str,
        reservation_id: str,
) -> None:
    assert status["native_context"]["invocation_id"] == prior_id
    assert status.get("native_invocation_history", {}) in ({}, None)
    rollover = _only_rollover(status)
    assert rollover["state"] == "preparation-pending"
    assert rollover["prior_invocation_id"] == prior_id
    assert rollover["next_invocation_id"] == next_id
    assert rollover["reservation_id"] == reservation_id
    assert rollover["reservation_binding"] is None
    assert rollover["history_id"] is None
    assert rollover["next_context"] is None
    assert rollover["startup_binding"] is None
    assert rollover["dispatch_intent"] is None


def _assert_native_no_send_receipt(
        receipt: Mapping[str, Any], reservation: Mapping[str, Any],
) -> None:
    assert set(receipt) == _NATIVE_NO_SEND_RECEIPT_FIELDS
    assert receipt["schema_version"] == 2
    assert receipt["architecture"] == "native-coordinator-lineage"
    assert receipt["record_kind"] == "native-reservation-no-send"
    assert isinstance(receipt["observation_id"], str)
    assert receipt["reservation_binding"] == reservation
    assert receipt["reservation_digest"] == _canonical_digest(reservation)
    assert (
        isinstance(receipt["observation_watermark"], int)
        and not isinstance(receipt["observation_watermark"], bool)
        and receipt["observation_watermark"] >= reservation["terminal_watermark"]
    )
    assert receipt["state"] == "reserved-unconsumed"
    assert receipt["transport_attempted"] is False
    assert receipt["receipt_digest"] == _canonical_digest(
        {key: value for key, value in receipt.items() if key != "receipt_digest"}
    )


def _assert_native_no_send_consumption(
        consumption: Mapping[str, Any], receipt: Mapping[str, Any],
        mailbox_id: str,
) -> None:
    assert set(consumption) == _NATIVE_NO_SEND_CONSUMPTION_FIELDS
    assert consumption["observation_id"] == receipt["observation_id"]
    assert consumption["receipt_digest"] == receipt["receipt_digest"]
    assert consumption["mailbox_id"] == mailbox_id
    assert consumption["consumed"] is True


def _assert_atomic_no_send_pair(
        store: Any, *, writes_before: int, receipt: Mapping[str, Any],
        mailbox_id: str,
) -> None:
    """Every newly persisted receipt/consumption appearance is one pair."""
    saw_pair = False
    for _name, written in store.write_calls[writes_before:]:
        rollovers = written.get("native_invocation_rollovers", {})
        assert isinstance(rollovers, Mapping)
        if not rollovers:
            continue
        candidate = next(iter(rollovers.values()))
        has_receipt = candidate.get("native_reservation_no_send") is not None
        has_consumption = (
            candidate.get("native_reservation_no_send_consumption") is not None
        )
        if not has_receipt and not has_consumption:
            continue
        assert has_receipt and has_consumption
        assert candidate["native_reservation_no_send"] == receipt
        _assert_native_no_send_receipt(
            candidate["native_reservation_no_send"],
            receipt["reservation_binding"],
        )
        _assert_native_no_send_consumption(
            candidate["native_reservation_no_send_consumption"],
            candidate["native_reservation_no_send"],
            mailbox_id,
        )
        saw_pair = True
    assert saw_pair


def _mailbox(status: Mapping[str, Any], message_id: str) -> Dict[str, Any]:
    return next(
        item for item in status["mailboxes"] if item["message_id"] == message_id
    )


def _rollover(status: Mapping[str, Any]) -> Dict[str, Any]:
    return _only_rollover(status)


def _recompute_reservation_binding_digest(
        receipt: Mapping[str, Any],
) -> Dict[str, Any]:
    refreshed = copy.deepcopy(dict(receipt))
    reservation = refreshed.get("reservation_binding")
    assert isinstance(reservation, Mapping)
    reservation = copy.deepcopy(dict(reservation))
    reservation["binding_digest"] = _canonical_digest({
        key: value for key, value in reservation.items()
        if key != "binding_digest"
    })
    refreshed["reservation_binding"] = reservation
    return _refresh_reservation_digest(refreshed)


def _assert_fixture_identities(
        first: Mapping[str, Any], second: Mapping[str, Any],
        operation_id: Any,
) -> None:
    """Keep tuple-unpacking mistakes from turning identity checks into None."""
    first_message_id = _value(first, "message_id")
    second_message_id = _value(second, "message_id")
    assert isinstance(first_message_id, str) and first_message_id
    assert isinstance(second_message_id, str) and second_message_id
    assert isinstance(operation_id, str) and operation_id


def _committed_unsent_fixture(*, attempted: bool = False):
    """Crash after the durable B bind, before/at the transport entry marker."""
    runtime = RecoveryRuntime()
    controller, store, runtime, coordinator, released, first = (
        _released_native_fixture(runtime=runtime)
    )
    second = _submit_next(controller, coordinator, "recovery-bound-status")
    operation_id = _operation_id(released)
    _assert_fixture_identities(first, second, operation_id)
    runtime.no_send_message_id = _value(second, "message_id")
    observed: Dict[str, Any] = {}

    def observe_send(
            observed_runtime: RecoveryRuntime,
            participant_id: str,
            message_id: str,
            payload_ref: Any,
    ) -> None:
        assert observed_runtime is runtime
        assert participant_id == coordinator.participant_id
        assert message_id == _value(second, "message_id")
        assert payload_ref == "opaque://mail-b"
        request = runtime.prepare_requests[0]
        response = runtime.prepare_responses[request["reservation_id"]]
        runtime.cache_no_send_reservation(response)
        observed["reservation"] = copy.deepcopy(response)
        observed["record"] = _durable_record(store)
        if not attempted:
            # This callback is before RecoveryRuntime's transport marker and
            # therefore models a genuine pre-entry crash, not an inferred
            # no-send result after the SDK boundary.
            raise asyncio.CancelledError()

    runtime.send_observer = observe_send
    runtime.cancel_after_transport_marker = attempted
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(controller.dispatch_next(
            operation_id, recipient_id=coordinator.participant_id,
        ))
    assert _durable_record(store) == observed["record"]
    assert runtime.prepare_requests and len(runtime.prepare_requests) == 1
    if attempted:
        assert _value(second, "message_id") in runtime.transport_attempted_message_ids
        runtime.status_receipt_mode = "missing"
    else:
        assert _value(second, "message_id") not in runtime.transport_attempted_message_ids
    assert runtime.sent == [
        (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
    ]
    return (
        controller,
        store,
        runtime,
        coordinator,
        first,
        released,
        second,
        operation_id,
        observed,
    )


def _assert_native_recovery_held(
        controller: ManagedController, store: Any, runtime: RecoveryRuntime,
        coordinator: Any, first: Mapping[str, Any], second: Mapping[str, Any],
        baseline_claims: Any, before: Mapping[str, Any],
) -> None:
    after = controller.status()
    assert after["native_invocation_history"] == before["native_invocation_history"]
    assert after["native_context"] == before["native_context"]
    assert _mailbox(after, _value(second, "message_id"))["state"] != "queued"
    assert _rollover(after)["state"] != "delivered"
    assert getattr(store, "lineage_claims", []) == baseline_claims
    assert len(runtime.prepare_requests) == 1
    assert runtime.sent == [
        (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
    ]


async def _refuse_replacement_reservation(
        controller: ManagedController, operation_id: str, recipient_id: str,
) -> None:
    """A reload may inspect a pending reservation but must not mint another."""
    with pytest.raises(ControllerError) as raised:
        await controller.dispatch_next(operation_id, recipient_id=recipient_id)
    assert raised.value.code == "busy"


def test_reload_at_preparation_pending_keeps_exact_request_and_no_query():
    runtime = RecoveryRuntime()
    runtime.gate_prepare = True
    controller, store, runtime, coordinator, released, first = (
        _released_native_fixture(runtime=runtime)
    )
    second = _submit_next(controller, coordinator, "recovery-preparation-pending")
    operation_id = _operation_id(released)
    baseline_authority = _authority_snapshot(store)
    captured: Dict[str, Any] = {}

    async def scenario() -> None:
        task = asyncio.create_task(controller.dispatch_next(
            operation_id, recipient_id=coordinator.participant_id,
        ))
        await asyncio.wait_for(runtime.prepare_started.wait(), 1)
        durable = _durable_record(store)
        pending = next(iter(durable["native_invocation_rollovers"].values()))
        captured["record"] = durable
        captured["reservation_id"] = pending["reservation_id"]
        _assert_preparation_pending(
            durable,
            prior_id=_value(first, "message_id"),
            next_id=_value(second, "message_id"),
            reservation_id=pending["reservation_id"],
        )

        reloaded, status = _fresh_reload(store, runtime=object())
        _assert_preparation_pending(
            status,
            prior_id=_value(first, "message_id"),
            next_id=_value(second, "message_id"),
            reservation_id=pending["reservation_id"],
        )
        assert _authority_snapshot(store) == baseline_authority
        writes = copy.deepcopy(store.write_calls)
        journal = copy.deepcopy(store.journal)
        await _refuse_replacement_reservation(
            reloaded, operation_id, coordinator.participant_id,
        )
        assert store.write_calls == writes
        assert store.journal == journal
        assert len(runtime.prepare_requests) == 1

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert _durable_record(store) == captured["record"]
    assert _authority_snapshot(store) == baseline_authority
    assert runtime.sent == [
        (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
    ]
    assert len(runtime.prepare_requests) == 1


@pytest.mark.parametrize(
    "cancel_after_response", [False, True],
    ids=["commit", "cancel-before-bind"],
)
def test_reload_after_reservation_response_before_atomic_history_bind(
        cancel_after_response: bool,
):
    runtime = RecoveryRuntime()
    controller, store, runtime, coordinator, released, first = (
        _released_native_fixture(runtime=runtime)
    )
    second = _submit_next(controller, coordinator, "recovery-reservation-response")
    operation_id = _operation_id(released)
    baseline_authority = _authority_snapshot(store)
    observed: Dict[str, Any] = {}

    def observe_reservation(
            observed_runtime: RecoveryRuntime,
            request: Mapping[str, Any],
            response: Mapping[str, Any],
    ) -> None:
        assert observed_runtime is runtime
        assert response["state"] == "reserved"
        reloaded, status = _fresh_reload(store, runtime=object())
        del reloaded
        observed["record"] = _durable_record(store)
        observed["status"] = status
        observed["request"] = copy.deepcopy(dict(request))
        observed["response"] = copy.deepcopy(dict(response))
        pending = observed["record"]["native_invocation_rollovers"]
        assert len(pending) == 1
        pending_rollover = next(iter(pending.values()))
        _assert_preparation_pending(
            status,
            prior_id=_value(first, "message_id"),
            next_id=_value(second, "message_id"),
            reservation_id=request["reservation_id"],
        )
        assert pending_rollover["reservation_binding"] is None
        assert observed["record"]["native_invocation_history"] in ({}, None)
        assert _authority_snapshot(store) == baseline_authority
        if cancel_after_response:
            raise asyncio.CancelledError()

    runtime.prepare_observer = observe_reservation
    if cancel_after_response:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(controller.dispatch_next(
                operation_id, recipient_id=coordinator.participant_id,
            ))
        assert _durable_record(store) == observed["record"]
        assert runtime.sent == [
            (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
        ]
        reloaded, status = _fresh_reload(store, runtime=object())
        _assert_preparation_pending(
            status,
            prior_id=_value(first, "message_id"),
            next_id=_value(second, "message_id"),
            reservation_id=observed["request"]["reservation_id"],
        )
        writes = copy.deepcopy(store.write_calls)
        asyncio.run(_refuse_replacement_reservation(
            reloaded, operation_id, coordinator.participant_id,
        ))
        assert store.write_calls == writes
        assert len(runtime.prepare_requests) == 1
    else:
        delivered = asyncio.run(controller.dispatch_next(
            operation_id, recipient_id=coordinator.participant_id,
        ))
        assert _value(delivered, "message_id") == _value(second, "message_id")
        assert _only_rollover(controller.status())["state"] == "delivered"
        assert len(runtime.prepare_requests) == 1
        assert [item[1] for item in runtime.sent] == [
            _value(first, "message_id"), _value(second, "message_id")
        ]
    assert _authority_snapshot(store)["lineage_claims"] == baseline_authority[
        "lineage_claims"
    ]


@pytest.mark.parametrize(
    "unbound_no_send_proof",
    [
        pytest.param(None, id="send"),
        pytest.param(True, id="reject-bare-true"),
        pytest.param("no-send", id="reject-bare-string"),
        pytest.param(
            {"authoritative": True, "send_occurred": False},
            id="reject-unbound-assertion",
        ),
    ],
)
def test_reload_after_committed_dispatch_intent_rejects_unbound_no_send_proof(
        unbound_no_send_proof: Any,
):
    runtime = RecoveryRuntime()
    controller, store, runtime, coordinator, released, first = (
        _released_native_fixture(runtime=runtime)
    )
    second = _submit_next(controller, coordinator, "recovery-dispatch-intent")
    operation_id = _operation_id(released)
    baseline_claims = copy.deepcopy(getattr(store, "lineage_claims", []))
    observed: Dict[str, Any] = {}

    def observe_send(
            observed_runtime: RecoveryRuntime,
            participant_id: str,
            message_id: str,
            payload_ref: Any,
    ) -> None:
        assert observed_runtime is runtime
        assert participant_id == coordinator.participant_id
        assert message_id == _value(second, "message_id")
        assert payload_ref == "opaque://mail-b"
        reloaded, status = _fresh_reload(store, runtime=object())
        del reloaded
        record = _durable_record(store)
        rollover = _only_rollover(status)
        observed["record"] = record
        observed["status"] = status
        observed["history"] = copy.deepcopy(status["native_invocation_history"])
        assert len(status["native_invocation_history"]) == 1
        assert status["native_context"]["invocation_id"] == message_id
        assert rollover["state"] == "send-pending"
        assert rollover["reservation_binding"] is not None
        assert rollover["history_id"] in status["native_invocation_history"]
        assert rollover["dispatch_intent"]["message_id"] == message_id
        mailbox = next(
            item for item in status["mailboxes"] if item["message_id"] == message_id
        )
        assert mailbox["state"] == "dispatch-intent"
        assert record["native_invocation_history"] == observed["history"]
        assert getattr(store, "lineage_claims", []) == baseline_claims
        if unbound_no_send_proof is not None:
            raise asyncio.CancelledError()

    runtime.send_observer = observe_send
    if unbound_no_send_proof is not None:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(controller.dispatch_next(
                operation_id, recipient_id=coordinator.participant_id,
            ))
        assert _durable_record(store) == observed["record"]
        assert runtime.sent == [
            (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
        ]

        # A fresh controller cannot infer no-send from a durable dispatch
        # intent.  These values are caller assertions, not an exact,
        # identity-bound transport proof, so recovery must reject them and
        # retain the uncertainty.  The positive bound-proof reconciliation
        # case remains deferred until that controller/runtime seam exists.
        runtime.send_observer = None
        reloaded, before_recovery = _fresh_reload(store, runtime=runtime)
        writes = copy.deepcopy(store.write_calls)
        journal = copy.deepcopy(store.journal)
        with pytest.raises(ControllerError):
            reloaded.recover_dispatch(
                _value(second, "message_id"),
                unbound_no_send_proof,
            )
        after_recovery = reloaded.status()
        assert store.write_calls == writes
        assert store.journal == journal
        assert _durable_record(store) == observed["record"]
        assert after_recovery["native_invocation_history"] == (
            before_recovery["native_invocation_history"]
        )
        assert after_recovery["native_context"] == before_recovery["native_context"]
        assert _only_rollover(after_recovery)["state"] == "send-pending"
        assert next(
            item for item in after_recovery["mailboxes"]
            if item["message_id"] == _value(second, "message_id")
        )["state"] == "dispatch-intent"
        assert getattr(store, "lineage_claims", []) == baseline_claims
        assert len(runtime.prepare_requests) == 1
        assert runtime.sent == [
            (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
        ]
    else:
        delivered = asyncio.run(controller.dispatch_next(
            operation_id, recipient_id=coordinator.participant_id,
        ))
        assert _value(delivered, "message_id") == _value(second, "message_id")
        assert len(runtime.prepare_requests) == 1
        assert [item[1] for item in runtime.sent] == [
            _value(first, "message_id"), _value(second, "message_id")
        ]
    assert getattr(store, "lineage_claims", []) == baseline_claims


def test_public_recover_reconciles_cached_reservation_before_atomic_bind():
    """A lost controller bind may consume only the SDK's cached reservation."""
    runtime = RecoveryRuntime()
    controller, store, runtime, coordinator, released, first = (
        _released_native_fixture(runtime=runtime)
    )
    second = _submit_next(controller, coordinator, "recovery-cached-reservation")
    operation_id = _operation_id(released)
    baseline_claims = copy.deepcopy(getattr(store, "lineage_claims", []))
    observed: Dict[str, Any] = {}

    def observe_reservation(
            observed_runtime: RecoveryRuntime,
            request: Mapping[str, Any],
            response: Mapping[str, Any],
    ) -> None:
        assert observed_runtime is runtime
        runtime.cache_no_send_reservation(response)
        observed["reservation"] = copy.deepcopy(dict(response))
        observed["record"] = _durable_record(store)
        raise asyncio.CancelledError()

    runtime.prepare_observer = observe_reservation
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(controller.dispatch_next(
            operation_id, recipient_id=coordinator.participant_id,
        ))
    assert runtime.transport_attempted_message_ids == set()
    assert runtime.sent == [
        (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
    ]
    pending_controller, pending_status = _fresh_reload(store, runtime=runtime)
    _assert_preparation_pending(
        pending_status,
        prior_id=_value(first, "message_id"),
        next_id=_value(second, "message_id"),
        reservation_id=observed["reservation"]["reservation_id"],
    )
    status_calls_before = runtime.status_calls
    writes_before_recovery = len(store.write_calls)

    recovered = asyncio.run(pending_controller.recover(operation_id, 7))
    assert recovered.operation_id == operation_id
    assert runtime.status_calls == status_calls_before + 1
    assert len(runtime.prepare_requests) == 1
    after_recovery = pending_controller.status()
    assert after_recovery["operation"]["phase"] == "released"
    assert after_recovery["operation"]["release_count"] == 1
    assert after_recovery["native_context"]["invocation_id"] == _value(
        second, "message_id"
    )
    assert len(after_recovery["native_invocation_history"]) == 1
    recovered_rollover = _rollover(after_recovery)
    assert recovered_rollover["state"] in {"send-pending", "reconciled"}
    assert recovered_rollover["reservation_binding"] == observed["reservation"]
    receipt = recovered_rollover["native_reservation_no_send"]
    _assert_native_no_send_receipt(receipt, observed["reservation"])
    _assert_native_no_send_consumption(
        recovered_rollover["native_reservation_no_send_consumption"],
        receipt,
        _value(second, "message_id"),
    )
    _assert_atomic_no_send_pair(
        store,
        writes_before=writes_before_recovery,
        receipt=receipt,
        mailbox_id=_value(second, "message_id"),
    )
    assert _mailbox(after_recovery, _value(second, "message_id"))["state"] == "queued"
    assert getattr(store, "lineage_claims", []) == baseline_claims
    assert runtime.sent == [
        (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
    ]

    # A repeated public recovery is observational: it cannot poll/reconsume
    # the receipt or mint a second reservation before the normal pump.
    writes = copy.deepcopy(store.write_calls)
    journal = copy.deepcopy(store.journal)
    asyncio.run(pending_controller.recover(operation_id, 7))
    assert runtime.status_calls == status_calls_before + 1
    assert store.write_calls == writes
    assert store.journal == journal
    assert len(runtime.prepare_requests) == 1

    runtime.send_observer = None
    delivered = asyncio.run(pending_controller.dispatch_next(
        operation_id, recipient_id=coordinator.participant_id,
    ))
    assert _value(delivered, "message_id") == _value(second, "message_id")
    assert len(runtime.prepare_requests) == 1
    assert [item[1] for item in runtime.sent] == [
        _value(first, "message_id"), _value(second, "message_id")
    ]
    assert [item[1] for item in runtime.sent].count(
        _value(second, "message_id")
    ) == 1


def test_public_recover_reconciles_committed_unsent_binding_then_pumps_once():
    (
        _controller,
        store,
        runtime,
        coordinator,
        first,
        _released,
        second,
        operation_id,
        observed,
    ) = _committed_unsent_fixture()
    _assert_fixture_identities(first, second, operation_id)
    baseline_claims = copy.deepcopy(getattr(store, "lineage_claims", []))
    reloaded, before = _fresh_reload(store, runtime=runtime)
    before_history = copy.deepcopy(before["native_invocation_history"])
    before_context = copy.deepcopy(before["native_context"])
    status_calls_before = runtime.status_calls
    writes_before_recovery = len(store.write_calls)

    recovered = asyncio.run(reloaded.recover(operation_id, 7))
    assert recovered.operation_id == operation_id
    assert runtime.status_calls == status_calls_before + 1
    assert len(runtime.prepare_requests) == 1
    after_recovery = reloaded.status()
    assert after_recovery["native_invocation_history"] == before_history
    assert after_recovery["native_context"] == before_context
    assert after_recovery["native_context"]["invocation_id"] == _value(
        second, "message_id"
    )
    recovered_rollover = _rollover(after_recovery)
    assert recovered_rollover["state"] in {"send-pending", "reconciled"}
    assert recovered_rollover["reservation_binding"] == observed["reservation"]
    _assert_native_no_send_receipt(
        recovered_rollover["native_reservation_no_send"],
        observed["reservation"],
    )
    _assert_native_no_send_consumption(
        recovered_rollover["native_reservation_no_send_consumption"],
        recovered_rollover["native_reservation_no_send"],
        _value(second, "message_id"),
    )
    _assert_atomic_no_send_pair(
        store,
        writes_before=writes_before_recovery,
        receipt=recovered_rollover["native_reservation_no_send"],
        mailbox_id=_value(second, "message_id"),
    )
    assert _mailbox(after_recovery, _value(second, "message_id"))["state"] == "queued"
    assert getattr(store, "lineage_claims", []) == baseline_claims
    assert runtime.sent == [
        (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
    ]

    runtime.send_observer = None
    delivered = asyncio.run(reloaded.dispatch_next(
        operation_id, recipient_id=coordinator.participant_id,
    ))
    assert _value(delivered, "message_id") == _value(second, "message_id")
    assert len(runtime.prepare_requests) == 1
    assert [item[1] for item in runtime.sent] == [
        _value(first, "message_id"), _value(second, "message_id")
    ]
    assert [item[1] for item in runtime.sent].count(
        _value(second, "message_id")
    ) == 1

    # Once normal dispatch has begun, even a later fresh status observation
    # cannot reset the consumed reconciliation grant or requeue B.
    consumed_receipt = copy.deepcopy(
        _rollover(reloaded.status())["native_reservation_no_send"]
    )
    runtime.cached_receipt = None
    status_calls_after_send = runtime.status_calls
    try:
        asyncio.run(reloaded.recover(operation_id, 7))
    except ControllerError:
        pass
    after_retry = reloaded.status()
    assert after_retry["native_invocation_history"] == before_history
    assert after_retry["native_context"] == before_context
    assert _mailbox(after_retry, _value(second, "message_id"))["state"] == "acknowledged"
    assert _rollover(after_retry)["state"] == "delivered"
    assert _rollover(after_retry)["native_reservation_no_send"] == consumed_receipt
    _assert_native_no_send_consumption(
        _rollover(after_retry)["native_reservation_no_send_consumption"],
        consumed_receipt,
        _value(second, "message_id"),
    )
    assert len(runtime.prepare_requests) == 1
    assert [item[1] for item in runtime.sent].count(
        _value(second, "message_id")
    ) == 1
    assert runtime.status_calls >= status_calls_after_send


def test_consumed_no_send_grant_never_requeues_after_ambiguous_send():
    (
        _controller,
        store,
        runtime,
        coordinator,
        first,
        _released,
        second,
        operation_id,
        _observed,
    ) = _committed_unsent_fixture()
    _assert_fixture_identities(first, second, operation_id)
    baseline_claims = copy.deepcopy(getattr(store, "lineage_claims", []))
    reloaded, _before = _fresh_reload(store, runtime=runtime)
    asyncio.run(reloaded.recover(operation_id, 7))
    consumed_before_send = copy.deepcopy(_rollover(reloaded.status()))

    runtime.send_observer = None
    runtime.fail_send_after = True
    with pytest.raises(ControllerError):
        asyncio.run(reloaded.dispatch_next(
            operation_id, recipient_id=coordinator.participant_id,
        ))
    assert [item[1] for item in runtime.sent] == [
        _value(first, "message_id"), _value(second, "message_id")
    ]
    runtime.fail_send_after = False
    runtime.cached_receipt = None
    try:
        asyncio.run(reloaded.recover(operation_id, 7))
    except ControllerError:
        pass
    after = reloaded.status()
    assert _mailbox(after, _value(second, "message_id"))["state"] == "uncertain"
    assert _rollover(after)["state"] == "uncertain"
    assert _rollover(after)["native_reservation_no_send"] == (
        consumed_before_send["native_reservation_no_send"]
    )
    _assert_native_no_send_consumption(
        _rollover(after)["native_reservation_no_send_consumption"],
        consumed_before_send["native_reservation_no_send"],
        _value(second, "message_id"),
    )
    assert getattr(store, "lineage_claims", []) == baseline_claims
    assert [item[1] for item in runtime.sent].count(
        _value(second, "message_id")
    ) == 1


@pytest.mark.parametrize(
    "negative_case",
    [
        pytest.param("missing-receipt", id="missing-receipt"),
        pytest.param("attempted-transport", id="attempted-transport"),
        pytest.param("new-connection", id="new-connection"),
        pytest.param("stale-owner", id="stale-owner"),
        pytest.param("malformed-receipt", id="malformed-receipt"),
        pytest.param("wrong-reservation", id="wrong-reservation"),
        pytest.param("lower-watermark", id="lower-watermark"),
    ],
)
def test_public_recover_rejects_missing_or_nonbinding_no_send_evidence(
        negative_case: str,
):
    (
        _controller,
        store,
        runtime,
        coordinator,
        first,
        _released,
        second,
        operation_id,
        observed,
    ) = _committed_unsent_fixture(attempted=negative_case == "attempted-transport")
    _assert_fixture_identities(first, second, operation_id)
    baseline_claims = copy.deepcopy(getattr(store, "lineage_claims", []))
    recovery_runtime = runtime
    stale_owner = False

    if negative_case == "missing-receipt":
        runtime.status_receipt_mode = "missing"
    elif negative_case == "new-connection":
        recovery_runtime = RecoveryRuntime()
        recovery_runtime.no_send_message_id = _value(second, "message_id")
    elif negative_case == "stale-owner":
        stale_owner = True
    elif negative_case == "malformed-receipt":
        runtime.receipt_mutator = lambda receipt: {
            **receipt,
            "receipt_digest": "0" * 64,
        }
    elif negative_case == "wrong-reservation":
        def mutate_wrong_reservation(receipt: Dict[str, Any]) -> Dict[str, Any]:
            changed = copy.deepcopy(receipt)
            changed["reservation_binding"]["next_invocation_id"] = "mail-other"
            changed["reservation_binding"]["next_mailbox_id"] = "mail-other"
            return _recompute_reservation_binding_digest(changed)

        runtime.receipt_mutator = mutate_wrong_reservation
    elif negative_case == "lower-watermark":
        def mutate_lower_watermark(receipt: Dict[str, Any]) -> Dict[str, Any]:
            changed = copy.deepcopy(receipt)
            changed["observation_watermark"] = max(
                1, observed["reservation"]["terminal_watermark"] - 1
            )
            return _refresh_no_send_receipt_digest(changed)

        runtime.receipt_mutator = mutate_lower_watermark

    reloaded, before = _fresh_reload(store, runtime=recovery_runtime)
    if stale_owner:
        # Keep the reload genuine, then let the recovery authority check see a
        # daemon replacement after the durable snapshot was read.
        store.owner["daemon_id"] = "daemon-replacement"
    status_calls_before = runtime.status_calls
    writes_before_recovery = copy.deepcopy(store.write_calls)
    journal_before_recovery = copy.deepcopy(store.journal)
    documents_before_recovery = copy.deepcopy(store.documents)
    try:
        asyncio.run(reloaded.recover(operation_id, 7))
    except ControllerError:
        pass
    else:
        # A refusal may durably retain an explicit uncertain state, but never
        # returns B to the queue on absent, attempted, stale, reused, or
        # malformed evidence.
        pass
    after = reloaded.status()
    if negative_case == "stale-owner":
        # The authority fence rejects before runtime.status; stale ownership
        # must therefore leave the durable snapshot and journal untouched.
        assert runtime.status_calls == status_calls_before
        assert store.write_calls == writes_before_recovery
        assert store.journal == journal_before_recovery
        assert store.documents == documents_before_recovery
    elif negative_case != "new-connection":
        assert runtime.status_calls == status_calls_before + 1
    assert after["native_invocation_history"] == before["native_invocation_history"]
    assert after["native_context"] == before["native_context"]
    assert _mailbox(after, _value(second, "message_id"))["state"] != "queued"
    assert _rollover(after)["state"] != "delivered"
    assert getattr(store, "lineage_claims", []) == baseline_claims
    assert len(runtime.prepare_requests) == 1
    assert runtime.sent == [
        (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
    ]


def test_public_recover_rejects_receipt_reused_from_another_rollover():
    (
        _first_controller,
        first_store,
        first_runtime,
        first_coordinator,
        _first_mail,
        _first_released,
        first_second,
        _first_operation_id,
        first_observed,
    ) = _committed_unsent_fixture()
    _assert_fixture_identities(_first_mail, first_second, _first_operation_id)
    first_runtime.no_send_message_id = _value(first_second, "message_id")
    first_status = asyncio.run(first_runtime.status(first_coordinator.participant_id))
    reused_receipt = copy.deepcopy(
        first_status["evidence"]["native_reservation_no_send"]
    )
    assert reused_receipt == first_runtime.cached_receipt

    (
        _controller,
        store,
        runtime,
        coordinator,
        first,
        _released,
        second,
        operation_id,
        _observed,
    ) = _committed_unsent_fixture()
    _assert_fixture_identities(first, second, operation_id)
    runtime.receipt_mutator = lambda _receipt: copy.deepcopy(reused_receipt)
    baseline_claims = copy.deepcopy(getattr(store, "lineage_claims", []))
    reloaded, before = _fresh_reload(store, runtime=runtime)
    try:
        asyncio.run(reloaded.recover(operation_id, 7))
    except ControllerError:
        pass
    after = reloaded.status()
    assert after["native_invocation_history"] == before["native_invocation_history"]
    assert after["native_context"] == before["native_context"]
    assert _mailbox(after, _value(second, "message_id"))["state"] != "queued"
    assert _rollover(after)["state"] != "delivered"
    assert getattr(store, "lineage_claims", []) == baseline_claims
    assert len(runtime.prepare_requests) == 1
    assert runtime.sent == [
        (coordinator.participant_id, _value(first, "message_id"), "opaque://mail-a")
    ]


@pytest.mark.parametrize(
    "optional_form, accepted",
    [
        pytest.param("absent", True, id="legacy-absent"),
        pytest.param("null-receipt", True, id="legacy-null-receipt"),
        pytest.param("receipt-only", False, id="partial-receipt-only"),
        pytest.param("consumption-only", False, id="partial-consumption-only"),
        pytest.param("null-consumption", False, id="null-consumption"),
        pytest.param(
            "null-receipt-with-consumption", False,
            id="null-receipt-with-consumption",
        ),
        pytest.param("extra-consumption", False, id="extra-consumption-field"),
    ],
)
def test_reload_preserves_legacy_no_send_bytes_and_rejects_partial_pairs(
        optional_form: str, accepted: bool,
):
    (
        _controller,
        store,
        runtime,
        coordinator,
        _first,
        _released,
        second,
        _operation_id_value,
        observed,
    ) = _committed_unsent_fixture()
    _assert_fixture_identities(_first, second, _operation_id_value)
    status = asyncio.run(runtime.status(coordinator.participant_id))
    receipt = copy.deepcopy(status["evidence"]["native_reservation_no_send"])
    consumption = _native_no_send_consumption(
        receipt, _value(second, "message_id")
    )
    record = _durable_record(store)
    rollover_id, rollover = next(iter(record["native_invocation_rollovers"].items()))
    rollover = copy.deepcopy(rollover)
    if optional_form == "null-receipt":
        rollover["native_reservation_no_send"] = None
    elif optional_form == "receipt-only":
        rollover["native_reservation_no_send"] = receipt
    elif optional_form == "consumption-only":
        rollover["native_reservation_no_send_consumption"] = consumption
    elif optional_form == "null-consumption":
        rollover["native_reservation_no_send"] = receipt
        rollover["native_reservation_no_send_consumption"] = None
    elif optional_form == "null-receipt-with-consumption":
        rollover["native_reservation_no_send"] = None
        rollover["native_reservation_no_send_consumption"] = consumption
    elif optional_form == "extra-consumption":
        rollover["native_reservation_no_send"] = receipt
        rollover["native_reservation_no_send_consumption"] = {
            **consumption,
            "extra": "refuse",
        }
    elif optional_form != "absent":
        raise AssertionError("unknown optional form")
    record["native_invocation_rollovers"][rollover_id] = _refresh_rollover_integrity(
        rollover
    )
    store.write_json("controller.json", record)
    before_documents = copy.deepcopy(store.documents)
    before_writes = copy.deepcopy(store.write_calls)
    before_journal = copy.deepcopy(store.journal)

    if not accepted:
        with pytest.raises(ControllerError):
            ManagedController(
                store,
                runtime=runtime,
                clock=lambda: 1000.0,
                transcript_verifier=store.transcript_verifier,
            )
        assert store.documents == before_documents
        assert store.write_calls == before_writes
        assert store.journal == before_journal
        return

    reloaded = ManagedController(
        store,
        runtime=runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    reloaded.payload_resolver = lambda payload_ref: str(payload_ref)
    observed_status = reloaded.status()
    observed_rollover = _rollover(observed_status)
    if optional_form == "absent":
        assert "native_reservation_no_send" not in observed_rollover
        assert "native_reservation_no_send_consumption" not in observed_rollover
    else:
        assert observed_rollover["native_reservation_no_send"] is None
        assert "native_reservation_no_send_consumption" not in observed_rollover
    assert store.documents == before_documents
    assert store.write_calls == before_writes
    assert store.journal == before_journal

    # A later unrelated durable mailbox submission must preserve the exact
    # legacy optional-field representation; it may not insert a default pair.
    reloaded.submit(
        "legacy-unrelated-" + optional_form,
        coordinator.participant_id,
        "opaque://mail-unrelated",
        sender_id="user",
        task_id="task-root-coordinator",
        generation=7,
    )
    persisted = _durable_record(store)
    persisted_rollover = _rollover(persisted)
    if optional_form == "absent":
        assert "native_reservation_no_send" not in persisted_rollover
        assert "native_reservation_no_send_consumption" not in persisted_rollover
    else:
        assert persisted_rollover["native_reservation_no_send"] is None
        assert "native_reservation_no_send_consumption" not in persisted_rollover
