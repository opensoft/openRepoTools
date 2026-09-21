# SPDX-License-Identifier: Apache-2.0
"""Controller-only native stop durability and identity regressions."""

from __future__ import annotations

import copy

import pytest

from lane_managed_controller import ControllerError, ManagedController
from lane_managed_sdk import NativeLineageLedger
from test_lane_managed_controller import _enrolled, _native_lineage_payload


def _native_stop_authority(tmp_path):
    controller, store, _ = _enrolled()
    controller = ManagedController(store, _native_stop_daemon_id="daemon-test")
    lineage = _native_lineage_payload(tmp_path)
    lineage["read_only"] = True
    lineage["workspace_claim"]["parent_read_only"] = True
    claims = [copy.deepcopy(lineage["workspace_claim"])]
    owner = {
        "mode": "managed",
        "lane": "build",
        "generation": 7,
        "daemon_id": "daemon-test",
    }
    store.read_owner = lambda: copy.deepcopy(owner)
    store.read_lineage_claims = lambda: copy.deepcopy(claims)
    store.documents["controller.json"]["participants"][0]["metadata"][
        "runner_instance_id"
    ] = "runner-current"
    operation = controller.begin_operation("initial-start", "start", 7)
    saved_operation = store.documents["controller.json"]["operations"][0]
    saved_operation["phase"] = "released"
    saved_operation["release_count"] = 1
    identity = {
        "participant_id": "coordinator",
        "session_id": lineage["session_uuid"],
        "runner_instance_id": "runner-current",
    }
    saved_operation["metadata"]["release_receipts"] = {
        "coordinator": {
            **identity,
            "evidence": {
                **identity,
                "released": True,
                "uncertain_effects": [],
            },
        }
    }
    definitions = {
        "writer": {
            "prompt": "private configured instruction",
            "tools": ["Read", "Edit"],
            "model": "configured-model",
            "effort": "medium",
            "permissionMode": "default",
            "permissions": {"allow": ["Read", "Edit"]},
        }
    }
    controller.register_native_context(
        7, lineage, "runner-current", "invocation-1", definitions
    )
    context = controller.status()["native_context"]
    definition = NativeLineageLedger._definition_fact(
        "writer", definitions["writer"]
    )
    admission = {
        "admission_id": "admission-1",
        "tool_use_id": "tool-1",
        "agent_type": "writer",
        "invocation_id": "invocation-1",
        "parent": {
            "session_id": lineage["session_uuid"],
            "agent_id": None,
            "invocation_id": "invocation-1",
            "prompt_id": None,
        },
        "custom_definition": definition,
        "definition_digest": definition["digest"],
        "trusted_definition_digest": definition["digest"],
        "watermark": 2,
        "owner_generation": 7,
        "lineage_id": lineage["lineage_id"],
        "runner_incarnation": "runner-current",
        "launch_completed": False,
    }
    controller.persist_native_admission("request-1", 7, admission)
    return controller, store, lineage, admission, context


def _intent(lineage, admission, *, stop_id="stop-1", task_id="task-1"):
    return {
        "type": "native-stop-intent",
        "participant_id": "coordinator",
        "session_id": lineage["session_uuid"],
        "runner_instance_id": "runner-current",
        "stop": {
            "stop_id": stop_id,
            "owner_generation": 7,
            "lineage_id": lineage["lineage_id"],
            "invocation_id": "invocation-1",
            "admission_id": admission["admission_id"],
            "tool_use_id": admission["tool_use_id"],
            "agent_id": "agent-1",
            "task_id": task_id,
            "lineage_incarnation": 1,
            "trusted_definition_digest": admission["trusted_definition_digest"],
            "observed_watermark": 5,
            "observation": {
                "status": "active",
                "task_terminal": False,
                "start_watermark": 3,
                "task_start_event": {
                    "event_uuid": "task-start-1",
                    "watermark": 4,
                    "task_type": "local_agent",
                },
                "active_tool_ids": ["tool-active"],
                "uncertain_tool_ids": [],
                "unresolved_effect_ids": [],
            },
        },
    }


def _evidence(intent, kind, *, evidence_id=None):
    stop = intent["stop"]
    body = {
        "evidence_id": evidence_id or "evidence-" + kind,
        "stop_id": stop["stop_id"],
        "kind": kind,
        "agent_id": stop["agent_id"],
        "task_id": stop["task_id"],
        "lineage_incarnation": stop["lineage_incarnation"],
        "observed_watermark": 5 if kind == "runtime-ack" else 6,
    }
    if kind == "runtime-ack":
        body.update({"accepted": True, "ack_kind": "accepted-stop"})
    else:
        body.update({
            "event_kind": "task_notification",
            "event_uuid": "task-stop-1",
            "status": "stopped",
            "tool_use_id": stop["tool_use_id"],
            "observation": {
                "task_terminal": True,
                # The same tool may be present in active and uncertain facts;
                # the controller preserves both observations independently.
                "active_tool_ids": ["tool-active"],
                "uncertain_tool_ids": ["tool-active"],
                "unresolved_effect_ids": [],
            },
        })
    return {
        "type": "native-stop-evidence",
        "participant_id": intent["participant_id"],
        "session_id": intent["session_id"],
        "runner_instance_id": intent["runner_instance_id"],
        "evidence": body,
    }


def test_native_stop_intent_is_durable_before_authorization_and_never_replays(tmp_path):
    controller, store, lineage, admission, _ = _native_stop_authority(tmp_path)
    frame = _intent(lineage, admission)

    assert controller.persist_native_stop_intent(frame) == {
        "recorded": True,
        "authorize_send": True,
        "stop_id": "stop-1",
    }
    record = store.documents["controller.json"]["native_stops"]["stop-1"]
    assert record["may_have_been_sent"] is True
    assert record["authorization_count"] == 1
    assert store.documents["controller.json"]["native_context"]["fenced"] is True

    before = copy.deepcopy(store.documents["controller.json"])
    reloaded = ManagedController(store, _native_stop_daemon_id="daemon-test")
    assert reloaded.persist_native_stop_intent(copy.deepcopy(frame)) == {
        "recorded": True,
        "authorize_send": False,
        "stop_id": "stop-1",
    }
    assert store.documents["controller.json"] == before


@pytest.mark.parametrize("order", [
    ("runtime-ack", "terminal"),
    ("terminal", "runtime-ack"),
])
def test_native_stop_evidence_orders_are_independent_and_preserve_uncertainty(
        tmp_path, order):
    controller, store, lineage, admission, _ = _native_stop_authority(tmp_path)
    frame = _intent(lineage, admission)
    controller.persist_native_stop_intent(frame)
    claims = copy.deepcopy(store.read_lineage_claims())

    for kind in order:
        evidence = _evidence(frame, kind)
        assert controller.persist_native_stop_evidence(evidence) == {
            "recorded": True,
            "evidence_id": "evidence-" + kind,
            "stop_id": "stop-1",
        }

    record = store.documents["controller.json"]["native_stops"]["stop-1"]
    assert record["runtime_ack"] is not None
    assert record["terminal_evidence"] is not None
    assert record["terminal_evidence"]["evidence"]["observation"] == {
        "task_terminal": True,
        "active_tool_ids": ["tool-active"],
        "uncertain_tool_ids": ["tool-active"],
        "unresolved_effect_ids": [],
    }
    assert "quiescent" not in record
    assert "restore_state_clear" not in record
    assert store.read_lineage_claims() == claims


def test_native_stop_accepts_equal_agent_and_task_ids_when_task_event_is_observed(
        tmp_path):
    controller, _store, lineage, admission, _ = _native_stop_authority(tmp_path)
    frame = _intent(lineage, admission, task_id="agent-1")
    assert controller.persist_native_stop_intent(frame)["authorize_send"] is True


def test_native_stop_same_task_incarnation_is_busy_and_changed_evidence_is_invalid(
        tmp_path):
    controller, store, lineage, admission, _ = _native_stop_authority(tmp_path)
    frame = _intent(lineage, admission)
    controller.persist_native_stop_intent(frame)
    before = copy.deepcopy(store.documents["controller.json"])
    with pytest.raises(ControllerError) as raised:
        controller.persist_native_stop_intent(
            _intent(lineage, admission, stop_id="stop-2")
        )
    assert raised.value.code == "busy"
    assert store.documents["controller.json"] == before

    controller.persist_native_stop_evidence(_evidence(frame, "runtime-ack"))
    before = copy.deepcopy(store.documents["controller.json"])
    changed = _evidence(frame, "runtime-ack")
    changed["evidence"]["accepted"] = False
    with pytest.raises(ControllerError) as raised:
        controller.persist_native_stop_evidence(changed)
    assert raised.value.code == "invalid"
    assert store.documents["controller.json"] == before


def test_native_stop_rechecks_daemon_owner_same_generation_before_persist(tmp_path):
    controller, store, lineage, admission, _ = _native_stop_authority(tmp_path)
    frame = _intent(lineage, admission)
    store.read_owner = lambda: {
        "mode": "managed",
        "lane": "build",
        "generation": 7,
        "daemon_id": "replacement-daemon",
    }
    before = copy.deepcopy(store.documents["controller.json"])
    with pytest.raises(ControllerError) as raised:
        controller.persist_native_stop_intent(frame)
    assert raised.value.code == "ownership-conflict"
    assert store.documents["controller.json"] == before


def test_native_context_cannot_reload_without_the_stop_ledger(tmp_path):
    controller, store, lineage, admission, _ = _native_stop_authority(tmp_path)
    controller.persist_native_stop_intent(_intent(lineage, admission))
    raw = copy.deepcopy(store.documents["controller.json"])
    del raw["native_stops"]
    store.documents["controller.json"] = raw
    with pytest.raises(ControllerError) as raised:
        ManagedController(store, _native_stop_daemon_id="daemon-test")
    assert raised.value.code == "invalid"
    assert store.documents["controller.json"] == raw
