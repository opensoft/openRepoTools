# SPDX-License-Identifier: Apache-2.0
"""Fail-closed ctx and public-swap policy regressions.

These tests deliberately reuse the controller's in-memory roster and runtime
fixtures.  They do not exercise native accounts or the internal native
coordinator-interrupt seam; the public paths under test must refuse before
their first durable or runtime effect when native state is present.
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any, Callable

import pytest

from lane_managed_controller import ControllerError, ManagedController
from test_lane_managed_controller import (
    MemoryStore,
    SwapRuntime,
    _checkpoint_entry,
    _operation_id,
    _prepare_released_swap,
    _run_ctx,
    _run_release,
    _run_swap,
    _successful_swap_statuses,
    _swap_roster,
)


def _released_fixture():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    operation = _prepare_released_swap(controller, store, runtime)
    return controller, store, runtime, operation


def _replace_record(store: MemoryStore, mutate: Callable[[dict[str, Any]], None]) -> None:
    record = copy.deepcopy(store.documents["controller.json"])
    mutate(record)
    store.documents["controller.json"] = record


def _operation_raw(record: dict[str, Any], request_id: str) -> dict[str, Any]:
    for operation in record["operations"]:
        if operation["request_id"] == request_id:
            return operation
    raise AssertionError("operation request is not durably recorded")


def _reload(store: MemoryStore, runtime: Any) -> ManagedController:
    return ManagedController(
        store,
        runtime=runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )


def _assert_invalid(error: pytest.ExceptionInfo[ControllerError]) -> None:
    assert error.value.code == "invalid"


def _assert_unsupported(error: pytest.ExceptionInfo[ControllerError]) -> None:
    assert error.value.code == "unsupported"


@pytest.mark.parametrize(
    "worker_mapping",
    [
        {},
        {"worker-a": {"coordinator": "new-coordinator"}},
    ],
)
def test_ctx_rejects_every_explicit_mapping_before_request_or_runtime_effect(
    worker_mapping,
):
    controller, store, runtime, _ = _released_fixture()
    before_status = copy.deepcopy(controller.status())
    before_record = copy.deepcopy(store.documents["controller.json"])
    before_claims = copy.deepcopy(store.claims)
    before_calls = copy.deepcopy(runtime.calls)
    before_writes = copy.deepcopy(store.write_calls)

    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            controller,
            "ctx-mapping-refused",
            "checkpoint://ctx/mapping-refused",
            "hold",
            worker_mapping,
        )

    _assert_invalid(raised)
    assert controller.status() == before_status
    assert store.documents["controller.json"] == before_record
    assert store.claims == before_claims
    assert runtime.calls == before_calls
    assert store.write_calls == before_writes
    assert "ctx-mapping-refused" not in store.documents["controller.json"]["requests"]


def _add_native_startup(record: dict[str, Any]) -> None:
    operation = _operation_raw(record, "swap-request")
    operation["metadata"]["native_startup"] = {
        "record_kind": "native-coordinator-startup",
        "participant_id": "coordinator",
        "runner_incarnation": "native-runner-before-bind",
    }


def _add_native_fingerprint(record: dict[str, Any]) -> None:
    operation = _operation_raw(record, "swap-request")
    target_specs = operation["metadata"].setdefault("target_specs", {})
    coordinator_spec = copy.deepcopy(target_specs.get("coordinator", {}))
    fingerprint = copy.deepcopy(coordinator_spec.get("fingerprint", {}))
    fingerprint["native_config"] = {"lineage_id": "native-lineage-before-bind"}
    coordinator_spec["fingerprint"] = fingerprint
    target_specs["coordinator"] = coordinator_spec


@pytest.mark.parametrize("marker", [_add_native_startup, _add_native_fingerprint])
def test_ctx_refuses_native_state_before_fence_claim_transfer_or_runtime(marker):
    controller, store, runtime, _ = _released_fixture()
    _replace_record(store, marker)
    before_record = copy.deepcopy(store.documents["controller.json"])
    before_claims = copy.deepcopy(store.claims)
    before_writes = copy.deepcopy(store.write_calls)
    native_probe_runtime = SwapRuntime(_successful_swap_statuses())
    reloaded = _reload(store, native_probe_runtime)

    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            reloaded,
            "ctx-native-refused",
            "checkpoint://ctx/native-refused",
            "hold",
        )

    _assert_unsupported(raised)
    assert store.documents["controller.json"] == before_record
    assert store.claims == before_claims
    assert store.write_calls == before_writes
    assert native_probe_runtime.calls == []
    assert reloaded._native_context is None
    assert controller.status()["operation"]["phase"] == "released"


def test_ctx_restart_refuses_independent_workers_before_fence_or_claim_effects():
    controller, store, runtime, _ = _released_fixture()
    before_status = copy.deepcopy(controller.status())
    before_record = copy.deepcopy(store.documents["controller.json"])
    before_claims = copy.deepcopy(store.claims)
    before_calls = copy.deepcopy(runtime.calls)
    before_writes = copy.deepcopy(store.write_calls)

    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            controller,
            "ctx-independent-restart",
            "checkpoint://ctx/independent-restart",
            "restart",
        )

    _assert_unsupported(raised)
    assert controller.status() == before_status
    assert store.documents["controller.json"] == before_record
    assert store.claims == before_claims
    assert runtime.calls == before_calls
    assert store.write_calls == before_writes


def _released_coordinator_only_fixture():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    with controller._transaction():
        for participant_id in ("worker-a", "worker-b"):
            controller._participants[participant_id].state = "completed"
        controller._persist({"event": "test-complete-independent-workers"})
    operation = _run_swap(controller, request_id="coordinator-only-swap")
    return controller, store, runtime, _run_release(controller, _operation_id(operation))


def test_ctx_restart_refuses_even_when_no_independent_workers_remain():
    controller, store, runtime, _ = _released_coordinator_only_fixture()
    before_record = copy.deepcopy(store.documents["controller.json"])
    before_claims = copy.deepcopy(store.claims)
    before_calls = copy.deepcopy(runtime.calls)
    before_writes = copy.deepcopy(store.write_calls)

    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            controller,
            "ctx-coordinator-only-restart",
            "checkpoint://ctx/coordinator-only-restart",
            "restart",
        )

    _assert_unsupported(raised)
    assert store.documents["controller.json"] == before_record
    assert store.claims == before_claims
    assert runtime.calls == before_calls
    assert store.write_calls == before_writes
    assert "ctx-coordinator-only-restart" not in store.documents["controller.json"]["requests"]


class _HeldStartProbeRuntime(SwapRuntime):
    def __init__(self):
        super().__init__(_successful_swap_statuses())
        self.preflight_calls = 0

    def preflight_held_swap(self, spec, evidence_record):
        self.preflight_calls += 1
        raise AssertionError("native swap guard was after held-start preflight")


def test_public_swap_refuses_mixed_native_startup_before_any_effects():
    _, store, _, _ = _released_fixture()
    _replace_record(store, _add_native_startup)
    before_record = copy.deepcopy(store.documents["controller.json"])
    before_claims = copy.deepcopy(store.claims)
    before_writes = copy.deepcopy(store.write_calls)
    runtime = _HeldStartProbeRuntime()
    reloaded = _reload(store, runtime)

    with pytest.raises(ControllerError) as raised:
        _run_swap(reloaded, request_id="native-swap-refused")

    # This fixture retains legacy independent workers. Native swap classifies
    # that mixed roster as migration-required, before any runtime preflight.
    assert raised.value.code == "migration-required"
    assert str(raised.value) == "native swap cannot mix independent workers"
    assert runtime.preflight_calls == 0
    assert runtime.calls == []
    assert store.documents["controller.json"] == before_record
    assert store.claims == before_claims
    assert store.write_calls == before_writes
    assert "native-swap-refused" not in store.documents["controller.json"]["requests"]


def _peer_persist_native_startup(store: MemoryStore) -> None:
    peer = _reload(store, SwapRuntime(_successful_swap_statuses()))
    operation = peer._operations[peer._active_operation_id]
    operation.metadata["native_startup"] = {
        "record_kind": "native-coordinator-startup",
        "participant_id": "coordinator",
        "runner_incarnation": "peer-native-runner",
    }
    peer._persist({"event": "peer-native-startup"})


@pytest.mark.parametrize("entrypoint", ["ctx", "swap"])
def test_stale_controller_reloads_peer_native_marker_before_public_effect(entrypoint):
    controller, store, runtime, _ = _released_fixture()
    _peer_persist_native_startup(store)
    before_record = copy.deepcopy(store.documents["controller.json"])
    before_claims = copy.deepcopy(store.claims)
    before_calls = copy.deepcopy(runtime.calls)
    before_writes = copy.deepcopy(store.write_calls)

    with pytest.raises(ControllerError) as raised:
        if entrypoint == "ctx":
            _run_ctx(
                controller,
                "ctx-stale-native-peer",
                "checkpoint://ctx/stale-native-peer",
                "hold",
            )
        else:
            _run_swap(controller, request_id="swap-stale-native-peer")

    if entrypoint == "swap":
        assert raised.value.code == "migration-required"
        assert str(raised.value) == "native swap cannot mix independent workers"
    else:
        _assert_unsupported(raised)
    assert store.documents["controller.json"] == before_record
    assert store.claims == before_claims
    assert runtime.calls == before_calls
    assert store.write_calls == before_writes
    assert "ctx-stale-native-peer" not in store.documents["controller.json"]["requests"]
    assert "swap-stale-native-peer" not in store.documents["controller.json"]["requests"]


@pytest.mark.parametrize("state_kind", ["operation", "participant", "intent"])
def test_historical_rebind_state_is_refused_on_reload_without_rewrite(state_kind):
    _, store, runtime, _ = _released_fixture()

    def mutate(record):
        operation = _operation_raw(record, "swap-request")
        if state_kind == "operation":
            operation["metadata"]["rebound_participants"] = ["worker-a"]
        elif state_kind == "participant":
            participant = next(
                item for item in record["participants"]
                if item["participant_id"] == "worker-a"
            )
            participant["metadata"]["ctx_rebind"] = {
                "operation_id": operation["operation_id"],
                "policy": "rebind",
            }
        else:
            operation["metadata"]["ctx_intent"] = {"worker_policy": "rebind"}

    _replace_record(store, mutate)
    before_record = copy.deepcopy(store.documents["controller.json"])
    before_claims = copy.deepcopy(store.claims)
    before_writes = copy.deepcopy(store.write_calls)

    with pytest.raises(ControllerError) as raised:
        _reload(store, SwapRuntime(_successful_swap_statuses()))

    assert raised.value.code == "schema-mismatch"
    assert store.documents["controller.json"] == before_record
    assert store.claims == before_claims
    assert store.write_calls == before_writes
    assert runtime.calls


def test_nonnative_hold_keeps_workers_held_and_cannot_bypass_release_dispatch_gate():
    controller, store, runtime, _ = _released_fixture()
    controller.payload_resolver = lambda ref: ref
    ctx_operation = _run_ctx(
        controller,
        "ctx-hold-dispatch-policy",
        "checkpoint://ctx/hold-dispatch-policy",
        "hold",
    )
    held = controller.submit(
        "ctx-held-worker-message",
        "worker-a",
        "payload://held-worker",
        sender_id="user",
        task_id="task-a",
    )
    released = _run_release(controller, _operation_id(ctx_operation))

    assert released.phase == "released"
    candidates = controller.dispatch_candidates(_operation_id(ctx_operation))
    new_coordinator = controller.status()["coordinator_id"]
    assert any(item["recipient_id"] == new_coordinator for item in candidates)
    assert all(item["recipient_id"] != "worker-a" for item in candidates)
    assert store.documents["controller.json"]["mailboxes"]
    assert held.state == "fenced"
    worker_a = next(
        item for item in controller.status()["participants"]
        if item["participant_id"] == "worker-a"
    )
    assert "ctx_restart" not in worker_a["metadata"]
    assert worker_a["metadata"]["ctx_hold"]["restart_pending"] is False

    checkpoint = _checkpoint_entry(controller.status(), "ctx-hold-dispatch-policy")
    dispatched = asyncio.run(controller.dispatch_next(_operation_id(ctx_operation)))
    assert dispatched.message_id == checkpoint["message_id"]
    assert runtime.sent == [
        (new_coordinator, checkpoint["message_id"], "checkpoint://ctx/hold-dispatch-policy")
    ]
    assert all(call[0] != "send" or call[1] != "worker-a" for call in runtime.calls)
