# SPDX-License-Identifier: Apache-2.0
"""Pre-allow persistence and sealing races; no SDK or real account is used."""

import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from lane_managed_controller import ControllerError, ManagedController
from lane_managed_sdk import NativeLineageLedger
from test_lane_managed_controller import _enrolled, _native_lineage_payload


@pytest.fixture
def native_authority(tmp_path):
    controller, store, _ = _enrolled()
    lineage = _native_lineage_payload(tmp_path)
    lineage["read_only"] = True
    lineage["workspace_claim"]["parent_read_only"] = True
    claims = [copy.deepcopy(lineage["workspace_claim"])]
    owner = {"mode": "managed", "lane": "build", "generation": 7}
    store.read_owner = lambda: copy.deepcopy(owner)
    store.read_lineage_claims = lambda: copy.deepcopy(claims)
    store.documents["controller.json"]["participants"][0]["metadata"]["runner_instance_id"] = "runner-current"
    operation = controller.begin_operation("initial-start", "start", 7)
    # A completed fake release supplies the durable lifecycle authority. No
    # call into a real SDK or model is needed to test the admission boundary.
    saved_operation = store.documents["controller.json"]["operations"][0]
    saved_operation["phase"] = "released"
    saved_operation["release_count"] = 1
    identity = {"participant_id": "coordinator", "session_id": lineage["session_uuid"],
                "runner_instance_id": "runner-current"}
    saved_operation["metadata"]["release_receipts"] = {
        "coordinator": {**identity, "evidence": {**identity, "released": True, "uncertain_effects": []}}
    }
    definitions = {
        "writer": {"prompt": "private configured instruction; do not persist", "tools": ["Read", "Edit"],
                   "model": "configured-model", "effort": "medium", "permissionMode": "default",
                   "permissions": {"allow": ["Read", "Edit"],
                                   "description": "private configured instruction in policy",
                                   "prompt": "private configured instruction in policy prompt"}}
    }
    controller.register_native_context(7, lineage, "runner-current", "invocation-1", definitions)
    context = controller.status()["native_context"]
    definition = NativeLineageLedger._definition_fact("writer", definitions["writer"])
    assert definition == context["definitions"]["writer"]
    admission = {
        "admission_id": "admission-1", "tool_use_id": "tool-1", "agent_type": "writer",
        "invocation_id": "invocation-1", "parent": {"session_id": lineage["session_uuid"],
            "agent_id": None, "invocation_id": "invocation-1", "prompt_id": None},
        "custom_definition": definition, "definition_digest": definition["digest"],
        "trusted_definition_digest": definition["digest"], "watermark": 2,
        "owner_generation": 7, "lineage_id": lineage["lineage_id"],
        "runner_incarnation": "runner-current", "launch_completed": False,
    }
    return controller, store, admission, owner, claims, operation


def test_native_admission_is_durable_before_ack_and_retry_is_read_only(native_authority):
    controller, store, admission, *_ = native_authority
    ack = controller.persist_native_admission("request-1", 7, admission)
    durable = copy.deepcopy(store.documents["controller.json"])
    assert durable["native_admissions"]["request-1"]["ack"] == ack
    assert durable["native_admissions"]["request-1"]["admission"]["launch_completed"] is False
    assert "private configured instruction" not in repr(durable)
    before_writes = len(store.write_calls)
    reloaded = ManagedController(store)
    assert reloaded.persist_native_admission("request-1", 7, admission) == ack
    assert len(store.write_calls) == before_writes
    admission["custom_definition"]["tools"].append("Bash")
    assert store.documents["controller.json"] == durable


@pytest.mark.parametrize("key,value", [
    ("owner_generation", True), ("owner_generation", 8), ("lineage_id", "other-lineage"),
    ("runner_incarnation", "old-runner"), ("invocation_id", "old-invocation"),
    ("watermark", 1), ("watermark", True), ("launch_completed", True),
    ("trusted_definition_digest", "0" * 64), ("agent_type", "unconfigured"),
    ("child_session_uuid", "invented"),
])
def test_native_admission_refuses_changed_context_without_writes(native_authority, key, value):
    controller, store, admission, *_ = native_authority
    before = copy.deepcopy(store.documents)
    admission[key] = value
    with pytest.raises(ControllerError):
        controller.persist_native_admission("request-1", 7, admission)
    assert store.documents == before


@pytest.mark.parametrize("mutation", ["owner", "owner-lineage", "owner-coordinator", "claim", "runner", "policy", "parent", "nested", "held", "receipt", "release-generation"])
def test_native_admission_rechecks_authority_and_release(native_authority, mutation):
    controller, store, admission, owner, claims, _ = native_authority
    if mutation == "owner":
        owner["generation"] = 8
    elif mutation == "owner-lineage":
        owner["lineage_id"] = "different-lineage"
    elif mutation == "owner-coordinator":
        owner["coordinator_session_uuid"] = "different-coordinator"
    elif mutation == "release-generation":
        store.documents["controller.json"]["operations"][0]["generation"] = 6
    elif mutation == "claim":
        claims.clear()
    elif mutation == "runner":
        store.documents["controller.json"]["participants"][0]["metadata"]["runner_instance_id"] = "replacement"
    elif mutation == "policy":
        admission["custom_definition"]["tools"] = ["Bash"]
    elif mutation == "parent":
        admission["parent"]["session_id"] = "different-parent"
    elif mutation == "nested":
        admission["parent"]["agent_id"] = "unproven-native-parent"
    elif mutation == "receipt":
        store.documents["controller.json"]["operations"][0]["metadata"]["release_receipts"] = {}
    else:
        store.documents["controller.json"]["operations"][0]["phase"] = "ready-held"
    before = copy.deepcopy(store.documents)
    with pytest.raises(ControllerError):
        controller.persist_native_admission("request-1", 7, admission)
    assert store.documents == before


def test_native_admission_changed_retry_and_reused_identity_refuse(native_authority):
    controller, store, admission, *_ = native_authority
    controller.persist_native_admission("request-1", 7, admission)
    before = copy.deepcopy(store.documents)
    changed = copy.deepcopy(admission)
    changed["watermark"] = 3
    for request_id, value in (("request-1", changed), ("request-2", admission), ("initial-start", admission)):
        with pytest.raises(ControllerError):
            controller.persist_native_admission(request_id, 7, value)
        assert store.documents == before


def test_native_admission_persistence_failure_never_returns_allow(native_authority):
    controller, store, admission, *_ = native_authority
    before = copy.deepcopy(store.documents)
    writer = store.write_json

    def failed_write(*args):
        raise OSError("injected disk write failure")

    store.write_json = failed_write
    with pytest.raises(OSError):
        controller.persist_native_admission("request-1", 7, admission)
    store.write_json = writer
    assert store.documents == before
    assert controller.status()["native_admissions"] == {}


def test_native_admission_crash_after_durable_write_reloads_and_deduplicates(
        native_authority):
    """A post-write crash leaves one durable admission and no retry write."""
    controller, store, admission, *_ = native_authority
    original_write = store.write_json
    crashed = {"value": False}

    def write_then_crash(name, data):
        result = original_write(name, data)
        if name == "controller.json" and not crashed["value"]:
            crashed["value"] = True
            raise OSError("crash after native admission snapshot write")
        return result

    store.write_json = write_then_crash
    with pytest.raises(OSError, match="after native admission"):
        controller.persist_native_admission("request-crash-after-write", 7, admission)
    store.write_json = original_write

    durable = copy.deepcopy(store.documents["controller.json"])
    assert "request-crash-after-write" in durable["native_admissions"]
    before_writes = len(store.write_calls)
    reloaded = ManagedController(store)
    ack = reloaded.persist_native_admission(
        "request-crash-after-write", 7, copy.deepcopy(admission)
    )
    assert ack == durable["native_admissions"]["request-crash-after-write"]["ack"]
    assert len(store.write_calls) == before_writes
    assert store.documents["controller.json"] == durable


@pytest.mark.parametrize("corruption", ["digest", "ack", "claim", "context", "missing", "missing-ledger", "missing-context", "private-body"])
def test_native_admission_reload_rejects_corruption_without_mutation(native_authority, corruption):
    controller, store, admission, *_ = native_authority
    controller.persist_native_admission("request-1", 7, admission)
    raw = store.documents["controller.json"]
    record = raw["native_admissions"]["request-1"]
    if corruption == "digest":
        record["digest"] = "0" * 64
    elif corruption == "ack":
        record["ack"]["accepted"] = False
    elif corruption == "claim":
        record["claim_ref"]["lineage_id"] = "foreign"
    elif corruption == "context":
        raw["native_context"]["fenced"] = "false"
    elif corruption == "missing-ledger":
        del raw["native_admissions"]
    elif corruption == "missing-context":
        del raw["native_context"]
    elif corruption == "private-body":
        raw["native_context"]["definitions"]["writer"]["permissions"]["prompt"] = "private body"
    else:
        raw["native_context"] = None
    before = copy.deepcopy(store.documents)
    with pytest.raises(ControllerError):
        ManagedController(store)
    assert store.documents == before


def test_native_context_reload_rejects_parent_read_only_claim_drift(native_authority):
    """A read-only coordinator cannot reload a writable-parent claim."""
    _controller, store, _admission, *_ = native_authority
    record = copy.deepcopy(store.documents["controller.json"])
    record["native_context"]["lineage"]["workspace_claim"][
        "parent_read_only"
    ] = False
    before = copy.deepcopy(store.documents)
    store.write_json("controller.json", record)
    with pytest.raises(ControllerError) as raised:
        ManagedController(store)
    assert raised.value.code == "ownership-conflict"
    assert store.documents["controller.json"] == record
    assert store.documents["controller.json"] != before


def test_native_admission_and_fence_serialize_complete_pending_roster(native_authority):
    controller, store, admission, *_ = native_authority
    peer = ManagedController(store)
    barrier = threading.Barrier(2)

    def admit():
        barrier.wait()
        try:
            return controller.persist_native_admission("request-1", 7, admission)
        except ControllerError as exc:
            assert exc.code == "busy"
            return None

    def fence():
        barrier.wait()
        operation = peer.begin_operation("swap-next", "swap", 7)
        return peer.fence(operation.operation_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        admitted = executor.submit(admit)
        fenced = executor.submit(fence)
        ack, operation = admitted.result(timeout=5), fenced.result(timeout=5)
    expected = [admission["admission_id"]] if ack else []
    assert operation.metadata["sealed_native_admissions"] == expected
    assert controller.status()["native_context"]["fenced"] is True
    before = copy.deepcopy(store.documents)
    with pytest.raises(ControllerError, match="fenced"):
        controller.persist_native_admission("request-1", 7, admission)
    assert store.documents == before


def test_native_admission_context_cannot_be_replaced_to_drop_pending_work(native_authority):
    controller, store, admission, *_ = native_authority
    controller.persist_native_admission("request-1", 7, admission)
    context = controller.status()["native_context"]
    before = copy.deepcopy(store.documents)
    with pytest.raises(ControllerError, match="reconciliation"):
        controller.register_native_context(7, context["lineage"], "runner-current", "invocation-2",
                                          {"writer": {"tools": ["Read"], "model": "other"}})
    assert store.documents == before
