# SPDX-License-Identifier: Apache-2.0
"""Focused durable acceptance/refusal checks for the unsupported child route."""

from __future__ import annotations

import asyncio
import copy

import pytest

from lane_managed_controller import ControllerError, ManagedController, _digest
from lane_managed_sdk import _event_to_mapping
from test_lane_managed_native_worker_boundaries import (
    NATIVE_AGENT,
    NATIVE_TASK,
    NATIVE_TOOL,
    _native_task_notification,
    _observation,
    _observation_frame,
    _persist_joined_observation,
)


def _accepted_child(tmp_path, managed_workspace):
    values = asyncio.run(_persist_joined_observation(tmp_path, managed_workspace))
    (
        _daemon,
        controller,
        store,
        adapter,
        lineage,
        _context,
        _ledger,
        _snapshot,
        observation,
        _frame,
        _ack,
    ) = values
    entry = controller.submit(
        "native-child-route-request",
        NATIVE_AGENT,
        "payload://native-child-route",
        task_id=NATIVE_TASK,
        generation=lineage.owner_generation,
    )
    return values, entry


async def _complete_child(values):
    (
        _daemon,
        _controller,
        _store,
        adapter,
        lineage,
        context,
        ledger,
        _snapshot,
        _observation_before,
        _frame,
        _ack,
    ) = values
    assert ledger.observe(_event_to_mapping(_native_task_notification(
        NATIVE_TASK,
        "task-event-native-complete",
        status="completed",
        tool_use_id=NATIVE_TOOL,
    ))) is None
    completed_snapshot = ledger.snapshot()
    completed = _observation(
        context=context,
        lineage=lineage,
        snapshot=completed_snapshot,
        observation_id="observation-native-complete",
        terminal_outcome="completed",
        status="completed",
    )
    frame = _observation_frame(completed, context)
    await adapter.observation_callback(frame)
    return completed


def test_native_child_acceptance_reloads_with_separate_caller_and_route_bindings(
    tmp_path, managed_workspace
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    _daemon, controller, store, _adapter, lineage, _context, _ledger, _snapshot, observation, _frame, _ack = values

    coordinator_id = controller.status()["coordinator_id"]
    assert entry.recipient_id == coordinator_id
    target = entry.metadata["native_target"]
    assert target["lineage_id"] == lineage.lineage_id
    assert target["agent_id"] == NATIVE_AGENT
    assert target["task_id"] == NATIVE_TASK
    assert target["lineage_incarnation"] == observation["child"]["lineage_incarnation"]
    assert entry.metadata["physical_recipient"]["participant_id"] == coordinator_id
    assert entry.metadata["physical_recipient"]["mailbox_id"] == entry.message_id
    assert entry.metadata["request_content_digest"]
    assert entry.metadata["routing_binding_digest"]
    assert entry.metadata["request_content_digest"] != entry.metadata["routing_binding_digest"]

    reloaded = ManagedController(store)
    persisted = next(
        item for item in reloaded.status()["mailboxes"]
        if item["message_id"] == entry.message_id
    )
    assert persisted["metadata"] == entry.metadata


def test_exact_retry_after_child_completion_returns_original_before_mutable_lookup(
    tmp_path, managed_workspace, monkeypatch
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    controller = values[1]
    store = values[2]
    lineage = values[4]
    asyncio.run(_complete_child(values))
    before = store.read_json("controller.json")

    def resolver_must_not_run(*_args, **_kwargs):
        raise AssertionError("exact retry resolved a mutable child target")

    monkeypatch.setattr(controller, "_native_dispatch_target_locked", resolver_must_not_run)
    retry = controller.submit(
        "native-child-route-request",
        NATIVE_AGENT,
        "payload://native-child-route",
        task_id=NATIVE_TASK,
        generation=lineage.owner_generation,
    )
    assert retry.to_dict() == entry.to_dict()
    assert store.read_json("controller.json") == before


def test_changed_request_content_refuses_before_child_lookup(
    tmp_path, managed_workspace, monkeypatch
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    controller = values[1]
    store = values[2]
    lineage = values[4]
    before = store.read_json("controller.json")

    def resolver_must_not_run(*_args, **_kwargs):
        raise AssertionError("changed request resolved a mutable child target")

    monkeypatch.setattr(controller, "_native_dispatch_target_locked", resolver_must_not_run)
    with pytest.raises(ControllerError) as raised:
        controller.submit(
            "native-child-route-request",
            NATIVE_AGENT,
            "payload://changed-content",
            task_id=NATIVE_TASK,
            generation=lineage.owner_generation,
        )
    assert raised.value.code == "invalid"
    assert store.read_json("controller.json") == before
    assert (
        before["requests"]["native-child-route-request"]["result"]["message_id"]
        == entry.message_id
    )


def test_unsupported_child_delivery_preserves_queue_before_resolver_or_send(
    tmp_path, managed_workspace
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    controller = values[1]
    coordinator_id = controller.status()["coordinator_id"]
    calls = []

    class Runtime:
        async def send(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("unsupported child route reached generic send")

    def resolve_payload(*_args, **_kwargs):
        raise AssertionError("unsupported child route resolved payload")

    controller.runtime = Runtime()
    controller.payload_resolver = resolve_payload
    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.dispatch_next(
            entry.operation_id,
            recipient_id=coordinator_id,
        ))
    assert raised.value.code == "unsupported"
    assert calls == []
    mailbox = next(
        item for item in controller.status()["mailboxes"]
        if item["message_id"] == entry.message_id
    )
    assert mailbox["state"] == "queued"
    assert mailbox["dispatch_attempt"] == 0


def test_reload_rejects_tampered_native_physical_binding(
    tmp_path, managed_workspace
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    store = values[2]
    record = copy.deepcopy(store.read_json("controller.json"))
    mailbox = next(
        item for item in record["mailboxes"]
        if item["message_id"] == entry.message_id
    )
    mailbox["metadata"]["physical_recipient"]["session_uuid"] = "tampered-session"
    store.write_json("controller.json", record)

    with pytest.raises(ControllerError) as raised:
        ManagedController(store)
    assert raised.value.code in {"ownership-conflict", "invalid"}


def test_reload_rejects_removed_native_binding_when_request_result_retains_child(
    tmp_path, managed_workspace
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    store = values[2]
    record = copy.deepcopy(store.read_json("controller.json"))
    mailbox = next(
        item for item in record["mailboxes"]
        if item["message_id"] == entry.message_id
    )
    mailbox["metadata"] = {}
    store.write_json("controller.json", record)

    with pytest.raises(ControllerError) as raised:
        ManagedController(store)
    assert raised.value.code == "invalid"


def test_reload_rejects_double_stripped_native_binding_via_generic_digest(
    tmp_path, managed_workspace
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    store = values[2]
    record = copy.deepcopy(store.read_json("controller.json"))
    mailbox = next(
        item for item in record["mailboxes"]
        if item["message_id"] == entry.message_id
    )
    mailbox["metadata"] = {}
    record["requests"][entry.request_id]["result"]["metadata"] = {}
    store.write_json("controller.json", record)

    with pytest.raises(ControllerError) as raised:
        ManagedController(store)
    assert raised.value.code == "invalid"


def test_reload_rejects_partial_native_binding_without_marker(
    tmp_path, managed_workspace
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    store = values[2]
    record = copy.deepcopy(store.read_json("controller.json"))
    mailbox = next(
        item for item in record["mailboxes"]
        if item["message_id"] == entry.message_id
    )
    partial = copy.deepcopy(mailbox["metadata"])
    partial.pop("native_target")
    mailbox["metadata"] = partial
    record["requests"][entry.request_id]["result"]["metadata"] = copy.deepcopy(
        partial
    )
    store.write_json("controller.json", record)

    with pytest.raises(ControllerError) as raised:
        ManagedController(store)
    assert raised.value.code == "invalid"


def test_reload_rejects_tampered_submit_result_snapshot(
    tmp_path, managed_workspace
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    store = values[2]
    record = copy.deepcopy(store.read_json("controller.json"))
    result = record["requests"][entry.request_id]["result"]
    result["sender_id"] = "tampered-sender"
    store.write_json("controller.json", record)

    with pytest.raises(ControllerError) as raised:
        ManagedController(store)
    assert raised.value.code == "invalid"


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param("selector", id="caller-selector"),
        pytest.param("admission-watermark", id="admission-watermark"),
        pytest.param("physical-recipient", id="physical-recipient"),
        pytest.param("physical-session", id="physical-session"),
        pytest.param("parent-read-only", id="parent-read-only"),
        pytest.param("lineage", id="lineage"),
    ],
)
def test_rehashed_native_binding_still_requires_identity_and_policy_joins(
    tmp_path, managed_workspace, tamper
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    store = values[2]
    record = copy.deepcopy(store.read_json("controller.json"))
    mailbox = next(
        item for item in record["mailboxes"]
        if item["message_id"] == entry.message_id
    )
    metadata = mailbox["metadata"]
    if tamper == "selector":
        metadata["native_target"]["agent_id"] = "other-native-agent"
    elif tamper == "admission-watermark":
        metadata["native_target"]["admission_watermark"] += 1
    elif tamper == "physical-recipient":
        metadata["physical_recipient"]["participant_id"] = "other-recipient"
    elif tamper == "physical-session":
        metadata["physical_recipient"]["session_uuid"] = "other-session"
    elif tamper == "lineage":
        metadata["native_target"]["source_identity"]["lineage_id"] = (
            "other-lineage"
        )
    else:
        metadata["effective_policy"]["parent_read_only"] = not metadata[
            "effective_policy"
        ]["parent_read_only"]
    metadata["routing_binding_digest"] = _digest({
        "native_target": metadata["native_target"],
        "physical_recipient": metadata["physical_recipient"],
        "actual_route": metadata["actual_route"],
        "effective_policy": metadata["effective_policy"],
    })
    record["requests"][entry.request_id]["result"]["metadata"] = copy.deepcopy(
        metadata
    )
    store.write_json("controller.json", record)

    with pytest.raises(ControllerError) as raised:
        ManagedController(store)
    assert raised.value.code in {
        "invalid", "ownership-conflict", "permission-mismatch",
    }


def test_completed_child_is_stale_for_new_route_and_original_queue_is_retained(
    tmp_path, managed_workspace
):
    values, entry = _accepted_child(tmp_path, managed_workspace)
    controller = values[1]
    store = values[2]
    lineage = values[4]
    asyncio.run(_complete_child(values))
    before = store.read_json("controller.json")

    with pytest.raises(ControllerError) as raised:
        controller.submit(
            "native-child-route-after-completion",
            NATIVE_AGENT,
            "payload://native-child-route-2",
            task_id=NATIVE_TASK,
            generation=lineage.owner_generation,
        )
    assert raised.value.code == "stale-generation"
    after = store.read_json("controller.json")
    assert after["mailboxes"] == before["mailboxes"]
    mailbox = next(
        item for item in after["mailboxes"]
        if item["message_id"] == entry.message_id
    )
    assert mailbox["state"] == "queued"
