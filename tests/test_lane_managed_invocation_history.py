# SPDX-License-Identifier: Apache-2.0
"""Strict schema and reload tests for native invocation history.

The history collection is intentionally tested independently from the runtime
adapter.  It is immutable A-terminal evidence; preparation, reservation, and
uncertainty belong to the mutable rollover record and never become history
state.  Every malformed-record case mutates only the in-memory fake store and
then constructs a fresh controller, so no runtime effect can be hidden by a
live object.
"""

from __future__ import annotations

import asyncio
import copy

import pytest

from lane_managed_controller import ControllerError, ManagedController
from test_lane_managed_controller import (
    _native_start_controller,
    _operation_id,
    _run_native_start,
    _run_release,
)
from test_lane_managed_controller_rollover import (
    _HISTORY_FIELDS,
    _ROLLOVER_FIELDS,
    RolloverRuntime,
    _canonical_digest,
    _latest_records,
    _released_native_fixture,
    _submit_next,
)


def _fresh_controller(store, runtime=None):
    selected_runtime = RolloverRuntime() if runtime is None else runtime
    controller = ManagedController(
        store,
        runtime=selected_runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    selected_runtime.controller = controller
    return controller


def _rollover_record(controller, coordinator):
    released = controller.status()["operation"]
    second = _submit_next(controller, coordinator, "history-mail-b")
    asyncio.run(controller.dispatch_next(
        released["operation_id"], recipient_id=coordinator.participant_id
    ))
    return second


def test_schema2_absent_history_and_rollover_collections_reload_as_empty():
    runtime = RolloverRuntime()
    controller, store, coordinator, _workers, specs = _native_start_controller(
        runtime=runtime
    )
    started = _run_native_start(
        controller,
        request_id="history-absent-start",
        coordinator=coordinator,
        runner_spec=specs[coordinator.participant_id],
    )
    _run_release(controller, _operation_id(started))
    durable = copy.deepcopy(store.documents["controller.json"])
    durable.pop("native_invocation_history", None)
    durable.pop("native_invocation_rollovers", None)
    store.write_json("controller.json", durable)

    loaded = _fresh_controller(store)
    status = loaded.status()
    assert status.get("native_invocation_history", {}) in ({}, None)
    assert status.get("native_invocation_rollovers", {}) in ({}, None)
    assert status["operation"]["operation_id"] == _operation_id(started)
    assert status["phase"] == "released"


def test_history_and_rollover_schema_are_exact_and_history_is_immutable():
    controller, store, runtime, coordinator, _released, _first = _released_native_fixture()
    _rollover_record(controller, coordinator)
    _record, history, rollover = _latest_records(store)

    assert set(history) == _HISTORY_FIELDS
    assert set(rollover) == _ROLLOVER_FIELDS
    assert history["record_kind"] == "native-invocation-history"
    assert history["history_schema"] == 1
    assert rollover["record_kind"] == "native-invocation-rollover"
    assert rollover["rollover_schema"] == 1
    assert "uncertainty" not in history
    assert history["context"]["invocation_id"] == history["invocation_id"]
    assert rollover["history_id"] == history["history_id"]
    assert rollover["state"] == "delivered"
    assert rollover["uncertainty"] is None
    assert runtime.prepare_requests

    # A mutable delivery result may carry a sanitized runtime acknowledgement,
    # but no mutable update is allowed to add uncertainty or payload material
    # to the immutable archive.
    history_before = copy.deepcopy(history)
    rollover["state"] = "uncertain"
    rollover["uncertainty"] = {"reason": "test-only"}
    assert history == history_before


@pytest.mark.parametrize(
    "mutation,refresh_digest",
    [
        (
            lambda history: history.update({"terminal_watermark": history["source_watermark"]}),
            True,
        ),
        (lambda history: history.update({"integrity_digest": "0" * 64}), False),
        (
            lambda history: history["context"].update({"invocation_id": "stale-a"}),
            True,
        ),
        (
            lambda history: history["terminal_result"].update({
                "message_id": "not-the-archived-mailbox",
            }),
            True,
        ),
    ],
    ids=["non-ascending-watermark", "bad-integrity", "changed-context", "wrong-mailbox"],
)
def test_malformed_history_refuses_before_runtime_effect(mutation, refresh_digest):
    controller, store, _runtime, coordinator, _released, _first = _released_native_fixture()
    _rollover_record(controller, coordinator)
    durable = copy.deepcopy(store.documents["controller.json"])
    history_id, history = next(iter(durable["native_invocation_history"].items()))
    mutation(history)
    if refresh_digest:
        history["integrity_digest"] = _canonical_digest({
            key: value for key, value in history.items()
            if key != "integrity_digest"
        })
    durable["native_invocation_history"][history_id] = history
    store.write_json("controller.json", durable)
    fresh_runtime = RolloverRuntime()
    with pytest.raises(ControllerError) as raised:
        _fresh_controller(store, fresh_runtime)
    assert raised.value.code in {"invalid", "stale-generation", "ownership-conflict"}
    assert fresh_runtime.prepare_requests == []
    assert fresh_runtime.sent == []


def test_recomputed_history_proof_cannot_disagree_with_reservation_binding():
    controller, store, _runtime, coordinator, _released, _first = _released_native_fixture()
    _rollover_record(controller, coordinator)
    durable = copy.deepcopy(store.documents["controller.json"])
    history_id, history = next(iter(durable["native_invocation_history"].items()))

    # Keep A's history internally valid while making its reconstructed proof
    # differ from the independently valid proof sealed in the reservation.
    history["terminal_result"]["reader_drained_watermark"] += 1
    history["independent_drain"]["observation_watermark"] += 1
    history["terminal_watermark"] += 1
    history["terminal_proof_digest"] = _canonical_digest({
        "parent_result": history["terminal_result"],
        "roster": history["joined_roster"],
        "roster_digest": _canonical_digest(history["joined_roster"]),
        "observation_watermark": history["independent_drain"][
            "observation_watermark"
        ],
        "uncertainty": history["independent_drain"]["uncertainty"],
        "overflow": history["independent_drain"]["overflow"],
    })
    history["integrity_digest"] = _canonical_digest({
        key: value for key, value in history.items()
        if key != "integrity_digest"
    })
    durable["native_invocation_history"][history_id] = history
    store.write_json("controller.json", durable)

    fresh_runtime = RolloverRuntime()
    with pytest.raises(ControllerError) as raised:
        _fresh_controller(store, fresh_runtime)
    assert raised.value.code in {"stale-generation", "ownership-conflict", "invalid"}
    assert fresh_runtime.prepare_requests == []
    assert fresh_runtime.sent == []


def test_duplicate_history_identity_and_capacity_refuse_before_runtime_effect():
    controller, store, _runtime, coordinator, _released, _first = _released_native_fixture()
    _rollover_record(controller, coordinator)
    durable = copy.deepcopy(store.documents["controller.json"])
    history_id, history = next(iter(durable["native_invocation_history"].items()))
    duplicate = copy.deepcopy(history)
    duplicate["history_id"] = history_id
    durable["native_invocation_history"]["history-duplicate"] = duplicate
    store.write_json("controller.json", durable)
    fresh_runtime = RolloverRuntime()
    with pytest.raises(ControllerError) as raised:
        _fresh_controller(store, fresh_runtime)
    assert raised.value.code == "invalid"
    assert fresh_runtime.prepare_requests == []

    # A collection over the named bound refuses before its entries are used;
    # the repeated immutable identity remains deliberately untrusted data.
    controller, store, _runtime, coordinator, _released, _first = _released_native_fixture()
    _rollover_record(controller, coordinator)
    durable = copy.deepcopy(store.documents["controller.json"])
    history_id, history = next(iter(durable["native_invocation_history"].items()))
    durable["native_invocation_history"] = {
        "history-%02d" % index: copy.deepcopy(history)
        for index in range(17)
    }
    store.write_json("controller.json", durable)
    fresh_runtime = RolloverRuntime()
    with pytest.raises(ControllerError) as raised:
        _fresh_controller(store, fresh_runtime)
    assert raised.value.code == "invalid"
    assert fresh_runtime.prepare_requests == []


def test_ambiguous_send_reload_keeps_uncertainty_mutable_and_history_digest_stable():
    runtime = RolloverRuntime(fail_send_after=True)
    controller, store, runtime, coordinator, released, _first = _released_native_fixture(
        runtime=runtime
    )
    second = _submit_next(controller, coordinator, "history-ambiguous-b")
    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.dispatch_next(
            _operation_id(released), recipient_id=coordinator.participant_id
        ))
    assert raised.value.code == "uncertain-effect"
    durable, history, rollover = _latest_records(store)
    history_digest = history["integrity_digest"]
    assert rollover["state"] == "uncertain"
    assert rollover["uncertainty"]
    assert next(item for item in durable["mailboxes"]
                if item["message_id"] == second.message_id)["state"] == "uncertain"

    loaded_runtime = RolloverRuntime()
    loaded = _fresh_controller(store, loaded_runtime)
    loaded_history = next(iter(loaded.status()[
        "native_invocation_history"
    ].values()))
    loaded_rollover = next(iter(loaded.status()[
        "native_invocation_rollovers"
    ].values()))
    assert loaded_history["integrity_digest"] == history_digest
    assert loaded_rollover["state"] == "uncertain"
    assert loaded_rollover["uncertainty"]
    assert loaded_runtime.prepare_requests == []
    assert loaded_runtime.sent == []


def test_history_has_no_conversation_bodies_credentials_or_payload_digests():
    controller, store, _runtime, coordinator, _released, _first = _released_native_fixture()
    _rollover_record(controller, coordinator)
    record, history, rollover = _latest_records(store)

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert str(key).casefold() not in {
                    "body", "payload", "payload_ref", "resolved_payload",
                    "credentials", "credential", "password", "secret",
                    "token", "api_key", "payload_digest",
                }
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(history)
    walk(rollover)
    assert "native_invocation_history" in record
    assert "native_invocation_rollovers" in record
