# SPDX-License-Identifier: Apache-2.0
"""Release-gated native child restoration contracts.

The fixture in :mod:`test_lane_managed_native_ctx_integration` is the real
offline public path: a durable state store, controller, daemon, coordinator
runner, and public ``ctx``/``release`` requests.  The child observations are
published through the existing authenticated admission and observation
callbacks; this module never edits a controller snapshot to manufacture a
positive restoration.

The target restart implementation is intentionally test-first.  In
particular, an accepted coordinator instruction or native admission ACK is
not a restart.  Only a fresh, joined child observation can consume the
controller-created restart slot.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
from collections.abc import Mapping
from typing import Any, Callable

import pytest

from lane_managed_controller import ControllerError
from test_lane_managed_coordinator_interrupt import _evidence, _intent, _roster
from test_lane_managed_native_ctx_integration import (
    NATIVE_CHILD_STATUS_FIELDS,
    NativeCtxRuntime,
    NativeSwapEvidenceProvider,
    _ctx_harness,
    _ctx_request,
    _operation,
    _reload_ctx_fixture_controller,
)
from test_lane_managed_native_swap_integration import _digest, _start_and_release
from test_lane_managed_native_swap_integration import SOURCE_CAPABILITY_PIN


_SOURCE_IDENTITY_FIELDS = frozenset({
    "owner_generation",
    "lineage_id",
    "lineage_generation",
    "session_uuid",
    "runner_incarnation",
    "invocation_id",
})
_RESTORATION_FIELDS = frozenset({
    "operation_id",
    "policy",
    "disposition",
    "restart_attempt_id",
    "instruction_mailbox_id",
    "new_child_run_id",
    "evidence_refs",
})
_SLOT_FIELDS = frozenset({
    "schema_version",
    "architecture",
    "record_kind",
    "restart_attempt_id",
    "old_child_run_id",
    "instruction_mailbox_id",
    "target_source_identity",
    "agent_type",
    "trusted_definition_digest",
    "admission_binding",
    "new_child_run_id",
    "evidence_refs",
    "slot_digest",
})
_ADMISSION_FIELDS = frozenset({
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
})
_HEX64 = "0123456789abcdef"


class CompletedSourceNativeCtxRuntime(NativeCtxRuntime):
    """Native ctx runtime whose source child really completed before ctx.

    ``NativeSwapRuntime`` normally seals an active child in its later
    coordinator-interrupt roster.  This fixture uses the same admission,
    lineage, and child identities as the completed observation below, so the
    subsequent interrupt cannot silently manufacture a second active child.
    """

    def __init__(self) -> None:
        super().__init__()
        self._source_completed = False

    def mark_source_completed(self) -> None:
        self._source_completed = True

    async def _persist_typed_interrupt(self, selection: Mapping[str, Any]) -> None:
        if not self._source_completed:
            await super()._persist_typed_interrupt(selection)
            return
        if not callable(self._interrupt_intent_callback) or not callable(
                self._interrupt_evidence_callback
        ):
            raise RuntimeError("typed coordinator interrupt callbacks are unavailable")
        if self.controller is None or self._admission is None:
            raise RuntimeError("native A admission is unavailable for interrupt")
        context = self.controller.status().get("native_context")
        if not isinstance(context, Mapping):
            raise RuntimeError("native context was not committed before interrupt")
        lineage = context.get("lineage")
        if not isinstance(lineage, Mapping):
            raise RuntimeError("native context lineage is unavailable")
        admission = copy.deepcopy(self._admission)
        seal = max(8, int(admission["watermark"]) + 4)
        roster = _roster(
            admission,
            child_status="completed",
            terminal_watermark=max(7, int(admission["watermark"]) + 3),
        )
        frame = _intent(
            lineage,
            admission,
            selection["operation_id"],
            roster=roster,
            interrupt_id=selection["interrupt_id"],
            fence_epoch=selection["fence_epoch"],
            runner_instance_id=context["runner_incarnation"],
            roster_seal_watermark=seal,
            request_entry_watermark=5,
        )
        frame["interrupt"].update({
            "invocation_id": context["invocation_id"],
            "capability_digest": selection["capability_digest"],
            "request_epoch_id": selection["request_epoch_id"],
        })
        if selection["capability_digest"] != SOURCE_CAPABILITY_PIN:
            raise RuntimeError("interrupt did not use the source capability pin")
        intent_ack = self._interrupt_intent_callback(copy.deepcopy(frame))
        if inspect.isawaitable(intent_ack):
            intent_ack = await intent_ack
        if (
            not isinstance(intent_ack, Mapping)
            or intent_ack.get("recorded") is not True
            or intent_ack.get("authorize_send") is not True
        ):
            raise RuntimeError("typed interrupt intent was not durably authorized")

        child = roster["children"][0]
        observed = seal + 4
        entry_request_count = (
            self.evidence_provider.entry_request_count
            if self.evidence_provider is not None
            else 0
        )
        if entry_request_count is None:
            raise RuntimeError("native swap entry request cursor is unavailable")
        new_requests = self.request_observation_cursor - entry_request_count
        if new_requests < 0:
            raise RuntimeError("native swap source request cursor moved backwards")
        # A completed child has no active child tool to cancel.  The member
        # terminal fact and resolved effect still use the exact sealed source
        # child; omitting tool-terminal is the natural completed projection.
        facts = {
            "runtime-ack": {
                "accepted": True,
                "ack_kind": "accepted-interrupt",
            },
            "member-terminal": {
                "agent_id": child["agent_id"],
                "task_id": child["task_id"],
                "lineage_incarnation": child["lineage_incarnation"],
                "tool_use_id": child["tool_use_id"],
                "event_kind": "task_notification",
                "event_uuid": "task-complete-native-swap",
                "status": "completed",
            },
            "effect-outcome": {
                "effect_id": child["unresolved_effect_ids"][0],
                "status": "resolved",
            },
            "admission-closed": {
                "admission_id": admission["admission_id"],
                "closed": True,
            },
            "parent-drained": {
                "invocation_id": context["invocation_id"],
                "state": "drained",
            },
            "request-observation": {
                "epoch_id": selection["request_epoch_id"],
                "entry_watermark": 5,
                "through_watermark": observed,
                "new_requests": new_requests,
                "observable": True,
            },
        }
        for kind, data in facts.items():
            evidence = _evidence(
                frame,
                kind,
                observed_watermark=observed,
                data=data,
            )
            evidence_ack = self._interrupt_evidence_callback(evidence)
            if inspect.isawaitable(evidence_ack):
                evidence_ack = await evidence_ack
            if (
                not isinstance(evidence_ack, Mapping)
                or evidence_ack.get("recorded") is not True
            ):
                raise RuntimeError("typed interrupt evidence was not durably recorded")
        self._typed_observation_watermark = observed
        if self.evidence_provider is not None:
            self.evidence_provider.record_source_cursor(observed)
        self._interrupt_frames.append(copy.deepcopy(frame))
        self._interrupt_seen = True


def _record(fixture: Any) -> dict[str, Any]:
    value = fixture.state.read_json("controller.json")
    assert isinstance(value, dict)
    return copy.deepcopy(value)


def _status(fixture: Any, request_id: str) -> dict[str, Any]:
    response = fixture.request(request_id, "status")
    assert response["ok"] is True, json.dumps(response, sort_keys=True)
    result = response["result"]
    assert isinstance(result, Mapping)
    return copy.deepcopy(dict(result))


def _operation_record(record: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
    operation = _operation(record, operation_id)
    assert isinstance(operation, Mapping)
    return operation


def _operation_metadata(
        record: Mapping[str, Any], operation_id: str,
) -> Mapping[str, Any]:
    metadata = _operation_record(record, operation_id).get("metadata")
    assert isinstance(metadata, Mapping)
    return metadata


def _children(status: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = status.get("native_children")
    assert isinstance(values, list)
    assert values == sorted(values, key=lambda value: value["child_run_id"])
    for value in values:
        assert isinstance(value, Mapping)
        assert set(value) == NATIVE_CHILD_STATUS_FIELDS
    return values


def _child_by_run(
        status: Mapping[str, Any], child_run_id: str,
) -> Mapping[str, Any]:
    matches = [
        value for value in _children(status)
        if value.get("child_run_id") == child_run_id
    ]
    assert len(matches) == 1
    return matches[0]


def _restoration(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = row.get("restoration")
    if value is None:
        return None
    assert isinstance(value, Mapping)
    assert set(value) == _RESTORATION_FIELDS
    return value


def _assert_not_restarted(row: Mapping[str, Any]) -> None:
    restoration = _restoration(row)
    if restoration is None:
        return
    assert restoration["disposition"] not in {"restarted", "exact-resumed"}
    assert restoration["new_child_run_id"] is None


def _slots(
        record: Mapping[str, Any], operation_id: str,
) -> Mapping[str, Any]:
    metadata = _operation_metadata(record, operation_id)
    value = metadata.get("native_restart_slots", {})
    assert isinstance(value, Mapping)
    return value


def _slot_for_child(
        record: Mapping[str, Any], operation_id: str, old_child_run_id: str,
) -> tuple[str, Mapping[str, Any]]:
    matches = [
        (str(restart_attempt_id), value)
        for restart_attempt_id, value in _slots(record, operation_id).items()
        if isinstance(value, Mapping)
        and value.get("old_child_run_id") == old_child_run_id
    ]
    assert len(matches) == 1
    return matches[0]


def _target_identity(runtime: NativeCtxRuntime) -> dict[str, Any]:
    context = runtime.controller.status().get("native_context")
    assert isinstance(context, Mapping)
    lineage = context.get("lineage")
    assert isinstance(lineage, Mapping)
    identity = {
        "owner_generation": lineage["owner_generation"],
        "lineage_id": lineage["lineage_id"],
        "lineage_generation": lineage["lineage_generation"],
        "session_uuid": lineage["session_uuid"],
        "runner_incarnation": context["runner_incarnation"],
        "invocation_id": context["invocation_id"],
    }
    assert set(identity) == _SOURCE_IDENTITY_FIELDS
    return identity


def _assert_slot(
        slot: Mapping[str, Any], *, restart_attempt_id: str,
        old_child_run_id: str, instruction_mailbox_id: str,
        target_identity: Mapping[str, Any],
) -> None:
    assert set(slot) == _SLOT_FIELDS
    assert slot["schema_version"] == 2
    assert slot["architecture"] == "native-coordinator-lineage"
    assert slot["record_kind"] == "native-restart-slot"
    assert slot["restart_attempt_id"] == restart_attempt_id
    assert slot["old_child_run_id"] == old_child_run_id
    assert slot["instruction_mailbox_id"] == instruction_mailbox_id
    assert slot["target_source_identity"] == target_identity
    assert set(slot["target_source_identity"]) == _SOURCE_IDENTITY_FIELDS
    assert isinstance(slot["agent_type"], str) and slot["agent_type"]
    assert isinstance(slot["trusted_definition_digest"], str)
    assert len(slot["trusted_definition_digest"]) == 64
    assert all(value in _HEX64 for value in slot["trusted_definition_digest"])
    admission = slot["admission_binding"]
    if admission is not None:
        assert isinstance(admission, Mapping)
        assert set(admission) == {
            "admission_id", "tool_use_id", "admission_watermark",
        }
        assert isinstance(admission["admission_id"], str)
        assert isinstance(admission["tool_use_id"], str)
        assert type(admission["admission_watermark"]) is int
        assert admission["admission_watermark"] > 0
    new_child_run_id = slot["new_child_run_id"]
    if new_child_run_id is not None:
        assert isinstance(new_child_run_id, str)
        assert len(new_child_run_id) == 64
        assert all(value in _HEX64 for value in new_child_run_id)
    assert isinstance(slot["evidence_refs"], list)
    assert slot["evidence_refs"]
    assert len(slot["evidence_refs"]) == len(set(slot["evidence_refs"]))
    assert all(isinstance(value, str) and value for value in slot["evidence_refs"])
    assert slot["slot_digest"] == _digest({
        key: value for key, value in slot.items() if key != "slot_digest"
    })


def _assert_no_restart_field(admission: Mapping[str, Any]) -> None:
    """The SDK admission remains its existing closed shape."""
    assert set(admission) == _ADMISSION_FIELDS
    assert "restart_attempt_id" not in admission
    assert "old_child_run_id" not in admission


def _source_observation_entry(
        record: Mapping[str, Any], observation_id: str,
) -> Mapping[str, Any] | None:
    current = record.get("native_child_observations")
    if isinstance(current, Mapping) and observation_id in current:
        return current[observation_id]
    archives = record.get("native_source_archives")
    if not isinstance(archives, Mapping):
        return None
    for archive in archives.values():
        if not isinstance(archive, Mapping):
            continue
        snapshot = archive.get("snapshot")
        if not isinstance(snapshot, Mapping):
            continue
        observations = snapshot.get("native_child_observations")
        if isinstance(observations, Mapping) and observation_id in observations:
            return observations[observation_id]
    return None


async def _publish_admission(
        runtime: NativeCtxRuntime, instruction_mailbox_id: str, *,
        slot: Mapping[str, Any], suffix: str = "target",
        watermark: int | None = None,
        mutate: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    """Use the existing authenticated admission callback, never store writes."""
    context = runtime.controller.status().get("native_context")
    assert isinstance(context, Mapping)
    lineage = context.get("lineage")
    definitions = context.get("definitions")
    assert isinstance(lineage, Mapping)
    assert isinstance(definitions, Mapping) and definitions
    assert context["invocation_id"] == instruction_mailbox_id
    target_identity = _target_identity(runtime)
    assert slot["instruction_mailbox_id"] == instruction_mailbox_id
    assert slot["target_source_identity"] == target_identity
    agent_type = slot["agent_type"]
    definition = definitions.get(agent_type)
    assert isinstance(agent_type, str) and isinstance(definition, Mapping)
    assert definition["digest"] == slot["trusted_definition_digest"]
    if watermark is None:
        watermark = max(int(context["invocation_watermark"]) + 1, 100)
    assert type(watermark) is int
    assert watermark > int(context["invocation_watermark"])
    admission = {
        "admission_id": "admission-restart-" + suffix,
        "tool_use_id": "tool-restart-" + suffix,
        "agent_type": agent_type,
        "invocation_id": context["invocation_id"],
        "parent": {
            "session_id": lineage["session_uuid"],
            "invocation_id": context["invocation_id"],
        },
        "custom_definition": copy.deepcopy(dict(definition)),
        "definition_digest": definition["digest"],
        "trusted_definition_digest": definition["digest"],
        "watermark": watermark,
        "owner_generation": lineage["owner_generation"],
        "lineage_id": lineage["lineage_id"],
        "runner_incarnation": context["runner_incarnation"],
        "launch_completed": False,
    }
    if context.get("prompt_id") is not None:
        admission["parent"]["prompt_id"] = context["prompt_id"]
    if mutate is not None:
        mutate(admission)
    _assert_no_restart_field(admission)
    callback = runtime._admission_callback
    assert callable(callback)
    acknowledgement = callback(copy.deepcopy(admission))
    if inspect.isawaitable(acknowledgement):
        acknowledgement = await acknowledgement
    assert isinstance(acknowledgement, Mapping)
    assert acknowledgement.get("accepted") is True
    return admission, copy.deepcopy(dict(acknowledgement))


async def _publish_joined_observation(
        runtime: NativeCtxRuntime, admission: Mapping[str, Any], *,
        suffix: str, terminal_outcome: str | None = None,
        reuse_source_ids: bool = False,
        mutate: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    """Publish one callback-bound joined observation.

    Restart observations use fresh child identities.  The completed-source
    case deliberately reuses the real source child identity so the later
    interrupt roster and terminal facts remain one logical run.
    """
    context = runtime.controller.status().get("native_context")
    assert isinstance(context, Mapping)
    lineage = context.get("lineage")
    assert isinstance(lineage, Mapping)
    claims = runtime.controller.store.read_lineage_claims()
    target_claims = [
        claim for claim in claims
        if isinstance(claim, Mapping)
        and claim.get("lineage_id") == lineage.get("lineage_id")
        and claim.get("state") == "active"
    ]
    assert len(target_claims) == 1
    completed = terminal_outcome == "completed"
    task_start_watermark = int(admission["watermark"]) + 1
    terminal_watermark = task_start_watermark + 1 if completed else None
    if reuse_source_ids:
        assert completed
        child = copy.deepcopy(
            _roster(
                admission,
                child_status="completed",
                terminal_watermark=terminal_watermark,
            )["children"][0]
        )
        child["active_tool_ids"] = []
        child["uncertain_tool_ids"] = []
        child["unresolved_effect_ids"] = []
        marker = getattr(runtime, "mark_source_completed", None)
        assert callable(marker)
        marker()
    else:
        child = copy.deepcopy(
            _roster(
                admission,
                child_status="completed" if completed else "active",
                terminal_watermark=terminal_watermark,
                task_id="task-restarted-" + suffix,
            )["children"][0]
        )
        child["agent_id"] = "agent-restarted-" + suffix
        child["task_id"] = "task-restarted-" + suffix
        child["start_watermark"] = task_start_watermark
        child["task_start_event"] = {
            "event_uuid": "task-start-restarted-" + suffix,
            "watermark": task_start_watermark + 1,
            "task_type": "local_agent",
        }
        child["active_tool_ids"] = []
        child["uncertain_tool_ids"] = []
        child["unresolved_effect_ids"] = []
    observation = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-child-observation",
        "observation_id": "observation-restarted-" + suffix,
        "source_identity": {
            "owner_generation": lineage["owner_generation"],
            "lineage_id": lineage["lineage_id"],
            "lineage_generation": lineage["lineage_generation"],
            "session_uuid": lineage["session_uuid"],
            "runner_incarnation": context["runner_incarnation"],
            "invocation_id": context["invocation_id"],
        },
        "context_binding_digest": _digest({
            key: value for key, value in context.items() if key != "fenced"
        }),
        "claim_digest": _digest(target_claims[0]),
        "observation_watermark": (
            (terminal_watermark or child["task_start_event"]["watermark"]) + 1
        ),
        "terminal_outcome": terminal_outcome,
        "child": child,
    }
    if mutate is not None:
        mutate(observation)
    callback = runtime._native_child_observation_callback
    assert callable(callback)
    frame = {
        "type": "native-child-observation",
        "participant_id": runtime.controller.status()["coordinator_id"],
        "session_id": lineage["session_uuid"],
        "runner_instance_id": context["runner_incarnation"],
        "observation": observation,
    }
    acknowledgement = callback(frame)
    if inspect.isawaitable(acknowledgement):
        acknowledgement = await acknowledgement
    assert isinstance(acknowledgement, Mapping)
    assert acknowledgement.get("recorded") is True
    return observation, copy.deepcopy(dict(acknowledgement))


def _begin_restart(
        fixture: Any, runtime: NativeCtxRuntime, *, request_id: str,
) -> tuple[str, str, int, Mapping[str, Any]]:
    """Start A, retain its actual observation, and enter released ctx restart."""
    _start_and_release(fixture)
    source_ack = asyncio.run(runtime.emit_joined_child_observation())
    old_child_run_id = source_ack["child_run_id"]
    sends_before = len(runtime.send_calls)
    held = _ctx_request(
        fixture, request_id, "restart", "checkpoint://native-restoration-restart"
    )
    operation_id = held["result"]["operation_id"]
    assert held["result"]["phase"] == "ready-held"
    return old_child_run_id, operation_id, sends_before, held


def test_ctx_hold_retains_native_child_without_restart_instruction(tmp_path):
    provider = NativeSwapEvidenceProvider()
    runtime = NativeCtxRuntime()
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        source_ack = asyncio.run(runtime.emit_joined_child_observation())
        before_record = _record(fixture)
        sends_before = len(runtime.send_calls)

        held = _ctx_request(
            fixture, "native-restoration-hold", "hold",
            "checkpoint://native-restoration-hold",
        )
        operation_id = held["result"]["operation_id"]
        assert held["result"]["phase"] == "ready-held"
        assert len(runtime.send_calls) == sends_before

        after_record = _record(fixture)
        assert _source_observation_entry(
            after_record, "observation-native-ctx-1"
        ) == _source_observation_entry(
            before_record, "observation-native-ctx-1"
        )
        assert _slots(after_record, operation_id) == {}
        status = _status(fixture, "native-restoration-hold-status")
        row = _child_by_run(status, source_ack["child_run_id"])
        _assert_not_restarted(row)
        restoration = _restoration(row)
        if restoration is not None:
            assert restoration["policy"] == "hold"
            assert restoration["new_child_run_id"] is None


def test_ctx_restart_is_release_gated_and_accepted_ack_is_not_restarted(tmp_path):
    provider = NativeSwapEvidenceProvider()
    runtime = NativeCtxRuntime()
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        old_child_run_id, operation_id, sends_before, held = _begin_restart(
            fixture, runtime, request_id="native-restoration-gated"
        )
        held_status = _status(fixture, "native-restoration-gated-status")
        _assert_not_restarted(_child_by_run(held_status, old_child_run_id))
        assert _slots(_record(fixture), operation_id) == {}
        assert len(runtime.send_calls) == sends_before

        released = fixture.request(
            "native-restoration-gated-release", "release",
            {"operation_id": operation_id},
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        assert released["result"]["phase"] == "released"
        target_calls = runtime.send_calls[sends_before:]
        assert len(target_calls) == 1
        instruction_mailbox_id = target_calls[0]["message_id"]

        record = _record(fixture)
        restart_attempt_id, slot = _slot_for_child(
            record, operation_id, old_child_run_id
        )
        _assert_slot(
            slot,
            restart_attempt_id=restart_attempt_id,
            old_child_run_id=old_child_run_id,
            instruction_mailbox_id=instruction_mailbox_id,
            target_identity=_target_identity(runtime),
        )
        assert slot["admission_binding"] is None
        assert slot["new_child_run_id"] is None
        admissions = record.get("native_admissions", {})
        assert isinstance(admissions, Mapping)
        for admission_record in admissions.values():
            assert isinstance(admission_record, Mapping)
            _assert_no_restart_field(admission_record["admission"])
        status = _status(fixture, "native-restoration-gated-after-release")
        _assert_not_restarted(_child_by_run(status, old_child_run_id))


def test_unique_restart_slot_requires_joined_fresh_child_before_restarted(tmp_path):
    provider = NativeSwapEvidenceProvider()
    runtime = NativeCtxRuntime()
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        old_child_run_id, operation_id, sends_before, _held = _begin_restart(
            fixture, runtime, request_id="native-restoration-positive"
        )
        released = fixture.request(
            "native-restoration-positive-release", "release",
            {"operation_id": operation_id},
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        target_calls = runtime.send_calls[sends_before:]
        assert len(target_calls) == 1
        instruction_mailbox_id = target_calls[0]["message_id"]
        record = _record(fixture)
        restart_attempt_id, slot = _slot_for_child(
            record, operation_id, old_child_run_id
        )
        _assert_slot(
            slot,
            restart_attempt_id=restart_attempt_id,
            old_child_run_id=old_child_run_id,
            instruction_mailbox_id=instruction_mailbox_id,
            target_identity=_target_identity(runtime),
        )
        admission, admission_ack = asyncio.run(
            _publish_admission(
                runtime, instruction_mailbox_id, slot=slot,
            )
        )
        _assert_no_restart_field(admission)
        assert admission_ack["accepted"] is True
        record_after_admission = _record(fixture)
        _, pending_slot = _slot_for_child(
            record_after_admission, operation_id, old_child_run_id
        )
        assert pending_slot["new_child_run_id"] is None
        status_after_ack = _status(fixture, "native-restoration-positive-ack")
        _assert_not_restarted(_child_by_run(status_after_ack, old_child_run_id))

        observation, observation_ack = asyncio.run(
            _publish_joined_observation(
                runtime, admission, suffix="positive",
            )
        )
        status = _status(fixture, "native-restoration-positive-final")
        old_row = _child_by_run(status, old_child_run_id)
        restoration = _restoration(old_row)
        assert restoration is not None
        assert restoration["operation_id"] == operation_id
        assert restoration["policy"] == "restart"
        assert restoration["disposition"] == "restarted"
        assert restoration["restart_attempt_id"] == restart_attempt_id
        assert restoration["instruction_mailbox_id"] == instruction_mailbox_id
        assert restoration["new_child_run_id"] == observation_ack["child_run_id"]
        assert restoration["evidence_refs"]
        fresh_row = _child_by_run(status, observation_ack["child_run_id"])
        assert fresh_row["child_run_id"] != old_child_run_id
        assert fresh_row["agent_id"] == observation["child"]["agent_id"]
        final_record = _record(fixture)
        _, final_slot = _slot_for_child(final_record, operation_id, old_child_run_id)
        assert final_slot["new_child_run_id"] == observation_ack["child_run_id"]
        assert final_slot["admission_binding"] == {
            "admission_id": admission["admission_id"],
            "tool_use_id": admission["tool_use_id"],
            "admission_watermark": admission["watermark"],
        }
        _assert_slot(
            final_slot,
            restart_attempt_id=restart_attempt_id,
            old_child_run_id=old_child_run_id,
            instruction_mailbox_id=instruction_mailbox_id,
            target_identity=_target_identity(runtime),
        )

        # A fresh controller sees the same one-shot slot and restoration join;
        # reloading cannot issue another instruction or create another child.
        _reload_ctx_fixture_controller(fixture)
        reloaded_status = _status(fixture, "native-restoration-positive-reload")
        reloaded_old = _child_by_run(reloaded_status, old_child_run_id)
        assert _restoration(reloaded_old) == restoration
        assert len(fixture.runtime.send_calls) == sends_before + 1


@pytest.mark.parametrize(
    "case",
    [
        pytest.param("wrong-definition", id="wrong-definition"),
        pytest.param("wrong-parent", id="wrong-parent"),
        pytest.param("wrong-source", id="wrong-source"),
        pytest.param("missing-join", id="missing-join"),
    ],
)
def test_restart_mismatches_remain_unresolved_without_new_child(
        tmp_path, case: str,
):
    provider = NativeSwapEvidenceProvider()
    runtime = NativeCtxRuntime()
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        old_child_run_id, operation_id, sends_before, _held = _begin_restart(
            fixture, runtime, request_id="native-restoration-negative-" + case
        )
        released = fixture.request(
            "native-restoration-negative-release-" + case,
            "release",
            {"operation_id": operation_id},
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        target_calls = runtime.send_calls[sends_before:]
        assert len(target_calls) == 1
        instruction_mailbox_id = target_calls[0]["message_id"]
        record = _record(fixture)
        restart_attempt_id, slot = _slot_for_child(
            record, operation_id, old_child_run_id
        )
        _assert_slot(
            slot,
            restart_attempt_id=restart_attempt_id,
            old_child_run_id=old_child_run_id,
            instruction_mailbox_id=instruction_mailbox_id,
            target_identity=_target_identity(runtime),
        )

        if case == "missing-join":
            admission, admission_ack = asyncio.run(
                _publish_admission(
                    runtime,
                    instruction_mailbox_id,
                    slot=slot,
                    suffix="missing-join",
                )
            )
            _assert_no_restart_field(admission)
            assert admission_ack["accepted"] is True
            after_admission = _record(fixture)
            _, bound_slot = _slot_for_child(
                after_admission, operation_id, old_child_run_id
            )
            assert bound_slot["admission_binding"] == {
                "admission_id": admission["admission_id"],
                "tool_use_id": admission["tool_use_id"],
                "admission_watermark": admission["watermark"],
            }
            assert bound_slot["new_child_run_id"] is None
        elif case == "wrong-definition":
            def mutate(admission: dict[str, Any]) -> None:
                admission["custom_definition"]["model"] = "foreign-model"

            with pytest.raises(ControllerError):
                asyncio.run(_publish_admission(
                    runtime, instruction_mailbox_id,
                    slot=slot,
                    suffix="wrong-definition", mutate=mutate,
                ))
        elif case == "wrong-parent":
            def mutate(admission: dict[str, Any]) -> None:
                admission["parent"]["agent_id"] = "foreign-parent"

            with pytest.raises(ControllerError):
                asyncio.run(_publish_admission(
                    runtime, instruction_mailbox_id,
                    slot=slot,
                    suffix="wrong-parent", mutate=mutate,
                ))
        else:
            def mutate(admission: dict[str, Any]) -> None:
                admission["lineage_id"] = "foreign-lineage"

            with pytest.raises(ControllerError):
                asyncio.run(_publish_admission(
                    runtime, instruction_mailbox_id,
                    slot=slot,
                    suffix="wrong-source", mutate=mutate,
                ))

        after = _record(fixture)
        _, after_slot = _slot_for_child(after, operation_id, old_child_run_id)
        assert after_slot["new_child_run_id"] is None
        status = _status(fixture, "native-restoration-negative-status-" + case)
        _assert_not_restarted(_child_by_run(status, old_child_run_id))
        assert len(runtime.send_calls) == sends_before + 1


def test_duplicate_target_admissions_do_not_consume_one_restart_slot_twice(tmp_path):
    provider = NativeSwapEvidenceProvider()
    runtime = NativeCtxRuntime()
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        old_child_run_id, operation_id, sends_before, _held = _begin_restart(
            fixture, runtime, request_id="native-restoration-duplicate"
        )
        released = fixture.request(
            "native-restoration-duplicate-release", "release",
            {"operation_id": operation_id},
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        instruction_mailbox_id = runtime.send_calls[-1]["message_id"]
        record = _record(fixture)
        restart_attempt_id, slot = _slot_for_child(
            record, operation_id, old_child_run_id
        )
        _assert_slot(
            slot,
            restart_attempt_id=restart_attempt_id,
            old_child_run_id=old_child_run_id,
            instruction_mailbox_id=instruction_mailbox_id,
            target_identity=_target_identity(runtime),
        )
        first, _ack = asyncio.run(
            _publish_admission(
                runtime, instruction_mailbox_id, slot=slot, suffix="one",
            )
        )
        first_record = _record(fixture)
        _, first_slot = _slot_for_child(
            first_record, operation_id, old_child_run_id
        )
        assert first_slot["admission_binding"] == {
            "admission_id": first["admission_id"],
            "tool_use_id": first["tool_use_id"],
            "admission_watermark": first["watermark"],
        }
        with pytest.raises(ControllerError):
            asyncio.run(
                _publish_admission(
                    runtime,
                    instruction_mailbox_id,
                    slot=slot,
                    suffix="two",
                    watermark=first["watermark"] + 1,
                )
            )
        assert first["tool_use_id"] != "tool-restart-two"
        record = _record(fixture)
        _, slot = _slot_for_child(record, operation_id, old_child_run_id)
        assert slot["new_child_run_id"] is None
        status = _status(fixture, "native-restoration-duplicate-status")
        _assert_not_restarted(_child_by_run(status, old_child_run_id))
        assert len(runtime.send_calls) == sends_before + 1


def test_completed_child_remains_completed_and_is_never_restarted(tmp_path):
    provider = NativeSwapEvidenceProvider()
    runtime = CompletedSourceNativeCtxRuntime()
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        admission = runtime._admission
        assert isinstance(admission, Mapping)
        observation, acknowledgement = asyncio.run(
            _publish_joined_observation(
                runtime,
                admission,
                suffix="completed-source",
                terminal_outcome="completed",
                reuse_source_ids=True,
            )
        )
        completed_run_id = acknowledgement["child_run_id"]
        sends_before = len(runtime.send_calls)
        before_restart_children = _children(
            _status(fixture, "native-restoration-completed-before")
        )
        before_restart_child_ids = [
            row["child_run_id"] for row in before_restart_children
        ]
        held = _ctx_request(
            fixture, "native-restoration-completed", "restart",
            "checkpoint://native-restoration-completed",
        )
        operation_id = held["result"]["operation_id"]
        released = fixture.request(
            "native-restoration-completed-release", "release",
            {"operation_id": operation_id},
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        status = _status(fixture, "native-restoration-completed-status")
        completed = _child_by_run(status, completed_run_id)
        assert completed["lifecycle_status"] == "completed"
        restoration = _restoration(completed)
        if restoration is not None:
            assert restoration["disposition"] == "completed"
            assert restoration["new_child_run_id"] is None
        assert _slots(_record(fixture), operation_id) == {}
        assert observation["terminal_outcome"] == "completed"
        postrelease = runtime.send_calls[sends_before:]
        assert len(postrelease) == 1
        assert postrelease[0]["payload_ref"] == "checkpoint://native-restoration-completed"
        after_children = _children(status)
        assert [row["child_run_id"] for row in after_children] == before_restart_child_ids
        completed_after = _child_by_run(status, completed_run_id)
        assert completed_after["agent_id"] == "agent-1"
        assert completed_after["task_id"] == "task-1"
