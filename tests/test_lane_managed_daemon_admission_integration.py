# SPDX-License-Identifier: Apache-2.0
"""Fake-only native admission wiring; never evidence of live SDK support."""

from __future__ import annotations

import asyncio
import copy
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from lane_managed_controller import LineageRecord, ManagedController, Operation, Participant
from lane_managed_daemon import DaemonError, ManagedDaemon


ACK_FIELDS = (
    "admission_id", "owner_generation", "lineage_id", "runner_incarnation",
    "invocation_id", "tool_use_id", "trusted_definition_digest",
)


def intent():
    return {
            "admission_id": "admission-1", "tool_use_id": "tool-1",
        "agent_type": "writer", "invocation_id": "invocation-1",
        "parent": {"session_id": "11111111-1111-4111-8111-111111111111",
                   "invocation_id": "invocation-1"},
        "custom_definition": {"model": "configured-model", "effort": "high"},
        "definition_digest": "a" * 64, "trusted_definition_digest": "a" * 64,
        "watermark": 1, "owner_generation": 7, "lineage_id": "lineage-1",
        "runner_incarnation": "runner-1", "launch_completed": False,
    }


class MemoryStore:
    def __init__(self):
        self.identity = SimpleNamespace(lane="build", lane_key="build")
        self.documents = {}
        self.claims = []
        self.writes = []
        self.lock_depth = 0
        self.owner = {
            "schema_version": 2, "architecture": "native-coordinator-lineage",
            "record_kind": "managed-owner", "mode": "managed", "lane": "build",
            "daemon_id": "daemon-test", "generation": 7,
        }

    def enroll_managed(self, daemon_id, **kwargs):
        assert daemon_id == self.owner["daemon_id"]
        return copy.deepcopy(self.owner)

    def read_owner(self, **kwargs):
        return copy.deepcopy(self.owner)

    def read_json(self, name):
        return copy.deepcopy(self.documents.get(name))

    def write_json(self, name, value):
        assert self.lock_depth > 0
        self.writes.append((name, copy.deepcopy(value)))
        self.documents[name] = copy.deepcopy(value)

    def read_lineage_claims(self):
        assert self.lock_depth > 0
        return copy.deepcopy(self.claims)

    def append_journal(self, name, event):
        pass

    @contextmanager
    def locked(self, **kwargs):
        self.lock_depth += 1
        try:
            yield self
        finally:
            self.lock_depth -= 1


class HookAdapter:
    def __init__(self):
        self.callback = None
        self.bind_count = 0
        self.stop_intent_callback = None
        self.stop_evidence_callback = None
        self.stop_bind_count = 0

    def bind_native_admission(self, callback):
        # This is the real construction-order dependency, not a constructor
        # callback that captures an as-yet missing controller.
        assert callback.__self__.controller is not None
        self.callback = callback
        self.bind_count = getattr(self, "bind_count", 0) + 1

    def bind_native_stop(self, intent_callback, evidence_callback):
        assert intent_callback.__self__.controller is not None
        assert evidence_callback.__self__.controller is not None
        self.stop_intent_callback = intent_callback
        self.stop_evidence_callback = evidence_callback
        self.stop_bind_count += 1


class RecordingAuthority:
    """Authority double solely for transport/ack validation tests."""

    def __init__(self, store):
        self.store = store
        self.calls = []
        self.stop_intent_calls = []
        self.stop_evidence_calls = []
        self.ack_override = None

    def persist_native_admission(self, request_id, generation, admission):
        assert self.store.lock_depth == 0
        self.calls.append((request_id, generation, copy.deepcopy(admission)))
        ack = {"accepted": True, **{key: admission[key] for key in ACK_FIELDS}}
        if self.ack_override is not None:
            self.ack_override(ack)
        return ack

    def persist_native_stop_intent(self, frame):
        self.stop_intent_calls.append(frame)
        return {
            "recorded": True,
            "authorize_send": True,
            "stop_id": frame["stop"]["stop_id"],
        }

    def persist_native_stop_evidence(self, frame):
        self.stop_evidence_calls.append(frame)
        return {
            "recorded": True,
            "evidence_id": frame["evidence"]["evidence_id"],
            "stop_id": frame["evidence"]["stop_id"],
        }


def daemon_for(controller=None, store=None, adapter=None):
    store = store or MemoryStore()
    adapter = adapter or HookAdapter()
    profiles = SimpleNamespace(resolve=lambda name: name,
                               verify_transcript=lambda *args: {})
    daemon = ManagedDaemon(
        state=store, adapter=adapter, profiles=profiles, controller=controller,
        lane="build", daemon_id="daemon-test", opt_in=True,
    )
    return daemon, store, adapter


def native_stop_intent_frame():
    return {
        "type": "native-stop-intent",
        "participant_id": "coordinator",
        "session_id": "coordinator-session-1",
        "runner_instance_id": "runner-1",
        "stop": {
            "stop_id": "stop-1",
            "owner_generation": 7,
            "lineage_id": "lineage-1",
            "invocation_id": "invocation-1",
            "admission_id": "admission-1",
            "tool_use_id": "tool-1",
            "agent_id": "agent-1",
            "task_id": "task-1",
            "lineage_incarnation": 1,
            "trusted_definition_digest": "a" * 64,
            "observed_watermark": 13,
            "observation": {
                "status": "active",
                "task_terminal": False,
                "start_watermark": 12,
                "task_start_event": {
                    "event_uuid": "task-start-event-1",
                    "watermark": 12,
                    "task_type": "local_agent",
                },
                "active_tool_ids": [],
                "uncertain_tool_ids": [],
                "unresolved_effect_ids": [],
            },
        },
    }


def native_stop_evidence_frame():
    return {
        "type": "native-stop-evidence",
        "participant_id": "coordinator",
        "session_id": "coordinator-session-1",
        "runner_instance_id": "runner-1",
        "evidence": {
            "evidence_id": "evidence-1",
            "stop_id": "stop-1",
            "kind": "runtime-ack",
            "agent_id": "agent-1",
            "task_id": "task-1",
            "lineage_incarnation": 1,
            "observed_watermark": 13,
            "accepted": True,
            "ack_kind": "accepted-stop",
            "observation": {
                "status": "active",
                "task_terminal": False,
                "active_tool_ids": [],
                "uncertain_tool_ids": [],
                "unresolved_effect_ids": [],
            },
        },
    }


def test_callback_is_bound_after_real_controller_construction_and_only_once():
    daemon, store, adapter = daemon_for()

    async def scenario():
        await daemon.start()
        await daemon.start()
        assert type(daemon.controller) is ManagedController
        assert daemon.controller.runtime is adapter
        assert adapter.bind_count == 1
        assert adapter.callback.__self__ is daemon
        assert adapter.stop_bind_count == 1
        assert adapter.stop_intent_callback.__self__ is daemon
        assert adapter.stop_evidence_callback.__self__ is daemon
        # Enrollment/binding is not a native start or an invocation context.
        assert store.documents == {}
        with pytest.raises(DaemonError):
            await adapter.callback(intent())
        assert store.documents == {}
        assert store.lock_depth == 0

    asyncio.run(scenario())


def test_native_stop_callbacks_preserve_full_frames_at_trusted_controller_seam():
    store = MemoryStore()
    authority = RecordingAuthority(store)
    daemon, _, adapter = daemon_for(authority, store)
    intent_frame = native_stop_intent_frame()
    evidence_frame = native_stop_evidence_frame()

    async def scenario():
        await daemon.start()
        intent_ack = await adapter.stop_intent_callback(intent_frame)
        evidence_ack = await adapter.stop_evidence_callback(evidence_frame)
        assert intent_ack == {
            "recorded": True,
            "authorize_send": True,
            "stop_id": "stop-1",
        }
        assert evidence_ack == {
            "recorded": True,
            "evidence_id": "evidence-1",
            "stop_id": "stop-1",
        }

    asyncio.run(scenario())
    assert authority.stop_intent_calls == [intent_frame]
    assert authority.stop_evidence_calls == [evidence_frame]


def test_native_stop_callbacks_require_owned_started_daemon_before_authority():
    store = MemoryStore()
    authority = RecordingAuthority(store)
    daemon, _, _ = daemon_for(authority, store)

    async def scenario():
        with pytest.raises(DaemonError) as intent_error:
            await daemon._persist_native_stop_intent_callback(
                native_stop_intent_frame()
            )
        with pytest.raises(DaemonError) as evidence_error:
            await daemon._persist_native_stop_evidence_callback(
                native_stop_evidence_frame()
            )
        assert intent_error.value.code == "unsupported"
        assert evidence_error.value.code == "unsupported"

    asyncio.run(scenario())
    assert authority.stop_intent_calls == []
    assert authority.stop_evidence_calls == []


def test_native_stop_callbacks_require_matching_frame_type_before_authority():
    store = MemoryStore()
    authority = RecordingAuthority(store)
    daemon, _, adapter = daemon_for(authority, store)

    async def scenario():
        await daemon.start()
        with pytest.raises(DaemonError) as intent_error:
            await adapter.stop_intent_callback(native_stop_evidence_frame())
        with pytest.raises(DaemonError) as evidence_error:
            await adapter.stop_evidence_callback(native_stop_intent_frame())
        assert intent_error.value.code == "invalid"
        assert evidence_error.value.code == "invalid"

    asyncio.run(scenario())
    assert authority.stop_intent_calls == []
    assert authority.stop_evidence_calls == []


def test_native_stop_callback_refuses_foreign_enrolled_owner_before_authority():
    store = MemoryStore()
    authority = RecordingAuthority(store)
    daemon, _, adapter = daemon_for(authority, store)

    async def scenario():
        await daemon.start()
        daemon.owner_record["daemon_id"] = "foreign-daemon"
        with pytest.raises(DaemonError) as caught:
            await adapter.stop_intent_callback(native_stop_intent_frame())
        assert caught.value.code == "ownership-conflict"

    asyncio.run(scenario())
    assert authority.stop_intent_calls == []


def test_native_stop_callback_refuses_same_generation_owner_replacement():
    store = MemoryStore()
    authority = RecordingAuthority(store)
    daemon, _, adapter = daemon_for(authority, store)

    async def scenario():
        await daemon.start()
        store.owner["daemon_id"] = "replacement-daemon"
        # The replacement deliberately keeps generation 7.  The fresh owner
        # read must still fence this daemon before it reaches the controller.
        with pytest.raises(DaemonError) as caught:
            await adapter.stop_evidence_callback(native_stop_evidence_frame())
        assert caught.value.code == "ownership-conflict"

    asyncio.run(scenario())
    assert authority.stop_evidence_calls == []


def test_native_stop_callback_refuses_stale_owner_generation_before_authority():
    store = MemoryStore()
    authority = RecordingAuthority(store)
    daemon, _, adapter = daemon_for(authority, store)

    async def scenario():
        await daemon.start()
        store.owner["generation"] = 8
        with pytest.raises(DaemonError) as caught:
            await adapter.stop_intent_callback(native_stop_intent_frame())
        assert caught.value.code == "stale-generation"

    asyncio.run(scenario())
    assert authority.stop_intent_calls == []


def test_native_stop_callbacks_refuse_without_fresh_owner_reader():
    store = MemoryStore()
    store.read_owner = None
    authority = RecordingAuthority(store)
    daemon, _, adapter = daemon_for(authority, store)

    async def scenario():
        await daemon.start()
        with pytest.raises(DaemonError) as intent_error:
            await adapter.stop_intent_callback(native_stop_intent_frame())
        with pytest.raises(DaemonError) as evidence_error:
            await adapter.stop_evidence_callback(native_stop_evidence_frame())
        assert intent_error.value.code == "unsupported"
        assert evidence_error.value.code == "unsupported"

    asyncio.run(scenario())
    assert authority.stop_intent_calls == []
    assert authority.stop_evidence_calls == []


def native_fixture(tmp_path):
    """Seed synthetic durable dispatch facts; this does not exercise start.

    Lifecycle migration remains separate.  The real controller must still
    load/validate this snapshot, register trusted context, and transact every
    admission; no controller method is replaced with an acknowledgement fake.
    """
    store = MemoryStore()
    session = intent()["parent"]["session_id"]
    workspace = str(tmp_path.resolve())
    claim = {
        "claim_kind": "workspace", "lineage_id": "lineage-1",
        "owner_generation": 7, "lineage_generation": 1,
        "workspace": workspace, "common_dir": workspace, "state": "active",
        "parent_read_only": True,
    }
    store.claims = [claim]
    lineage = LineageRecord.from_dict({
        "schema_version": 2, "architecture": "native-coordinator-lineage",
        "record_kind": "lineage", "lineage_id": "lineage-1", "lane": "build",
        "owner_generation": 7, "lineage_generation": 1, "session_uuid": session,
        "workspace": workspace, "common_dir": workspace, "state": "active",
        "transcript": {}, "workspace_claim": claim, "read_only": True,
    })
    deny = ["Write", "Edit", "Bash", "Agent", "Task", "Team"]
    coordinator = Participant(
        participant_id="coordinator", session_id=session, session_name="build",
        bound_lane="build", role="coordinator", task_id="coordinator-task",
        mailbox_id="coordinator-mailbox", state="active", read_only=True,
        metadata={
            "runner_instance_id": "runner-1", "read_only_enforced": True,
            "tool_allowlist": ["Read"], "tool_denylist": deny,
            "tools": [], "mcp_servers": [],
            "permissions": {"mode": "allowlist", "enforced": True,
                            "allow": ["Read"], "deny": deny, "mcp": []},
        },
    )
    release_identity = {
        "participant_id": "coordinator", "session_id": session,
        "runner_instance_id": "runner-1",
    }
    operation = Operation(
        operation_id="released-1", request_id="release-1", mode="start",
        generation=7, phase="released", release_count=1,
        sealed_participants=["coordinator"],
        metadata={
            "runner_instances": {"coordinator": "runner-1"},
            "release_receipts": {"coordinator": {
                **release_identity,
                "evidence": {**release_identity, "released": True,
                             "uncertain_effects": []},
            }},
        },
    )
    store.documents["controller.json"] = {
        "schema_version": 2, "architecture": "native-coordinator-lineage",
        "record_kind": "controller", "generation": 7,
        "coordinator_id": "coordinator", "active_operation_id": "released-1",
        "participants": [coordinator.to_dict()], "mailboxes": [],
        "operations": [operation.to_dict()], "requests": {},
    }
    daemon, _, adapter = daemon_for(store=store)
    return daemon, store, adapter, lineage


def trusted_definitions():
    return {"writer": {
        "model": "configured-model", "effort": "high", "tools": ["Read", "Write"],
        "prompt": "Synthetic definition prompt must not be persisted",
    }}


def register_context(controller, lineage):
    # Trusted configuration is supplied separately from the hook intent.
    return controller.register_native_context(
        7, lineage, "runner-1", "invocation-1",
        trusted_definitions(),
        invocation_watermark=1,
    )


def context_intent(context):
    admission = intent()
    admission["custom_definition"] = copy.deepcopy(context["definitions"]["writer"])
    admission["definition_digest"] = admission["trusted_definition_digest"] = (
        admission["custom_definition"]["digest"]
    )
    admission["watermark"] = 2
    return admission


def test_real_controller_persists_before_hook_ack_and_deduplicates_after_reload(tmp_path):
    daemon, store, adapter, lineage = native_fixture(tmp_path)

    async def scenario():
        await daemon.start()
        context = register_context(daemon.controller, lineage)
        admission = context_intent(context)
        ack = await adapter.callback(admission)
        record = store.documents["controller.json"]
        assert len(record["native_admissions"]) == 1
        persisted = next(iter(record["native_admissions"].values()))
        assert persisted["ack"] == ack
        assert persisted["admission"] == admission
        assert persisted["claim_ref"] == store.claims[0]
        assert persisted["admission"]["launch_completed"] is False
        assert "prompt" not in record["native_context"]["definitions"]["writer"]
        assert store.lock_depth == 0
        writes = len(store.writes)
        daemon.controller = ManagedController(store, runtime=adapter)
        assert await adapter.callback(admission) == ack
        assert len(store.writes) == writes
        assert len(store.documents["controller.json"]["native_admissions"]) == 1

    asyncio.run(scenario())


def test_real_sdk_binding_and_native_ledger_reach_real_controller_without_launch(
        tmp_path, monkeypatch):
    from lane_managed_sdk import NativeLineageLedger, SdkRunnerAdapter

    daemon, store, _, lineage = native_fixture(tmp_path)
    callbacks = []

    def refuse_launch(_spec):
        pytest.fail("admission wiring must not start a runtime")

    adapter = SdkRunnerAdapter(runner_factory=refuse_launch)
    bind = adapter.bind_native_admission

    def capture_binding(callback):
        bind(callback)
        callbacks.append(callback)

    monkeypatch.setattr(adapter, "bind_native_admission", capture_binding)
    daemon.adapter = adapter

    async def scenario():
        await daemon.start()
        assert type(daemon.controller) is ManagedController
        assert len(callbacks) == 1
        register_context(daemon.controller, lineage)
        ledger = NativeLineageLedger(
            lineage.session_uuid, trusted_definitions=trusted_definitions(),
            parent_read_only=True, lineage_claim=store.claims[0],
            lineage_context={"owner_generation": 7, "lineage_id": "lineage-1",
                             "runner_incarnation": "runner-1"},
            persist_admission=callbacks[0],
        )
        assert ledger.begin_invocation("invocation-1") is None
        assert ledger.mark_released() is None
        error = await ledger.admit_agent({
            "hook_event_name": "PreToolUse", "session_id": lineage.session_uuid,
            "tool_name": "Agent", "tool_use_id": "tool-1",
            "tool_input": {"subagent_type": "writer", "tools": ["Bash"],
                           "model": "untrusted-model"},
        })
        assert error is None
        records = store.documents["controller.json"]["native_admissions"]
        assert len(records) == 1
        record = next(iter(records.values()))
        assert record["admission"]["custom_definition"]["tools"] == ["Read", "Write"]
        assert record["admission"]["custom_definition"]["model"] == "configured-model"
        assert record["admission"]["launch_completed"] is False
        assert ledger.children == {}
        assert store.lock_depth == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("change,code", [
    ("no-context", "unsupported"), ("fenced", "busy"),
    ("not-released", "busy"), ("receipt", "uncertain-effect"),
    ("release-count", "busy"),
    ("owner", "ownership-conflict"), ("claim", "ownership-conflict"),
    ("runner", "stale-generation"), ("policy", "permission-mismatch"),
])
def test_real_controller_refuses_without_current_context_release_and_ownership(
        tmp_path, change, code):
    daemon, store, adapter, lineage = native_fixture(tmp_path)

    async def scenario():
        await daemon.start()
        if change == "no-context":
            admission = intent()
        else:
            admission = context_intent(register_context(daemon.controller, lineage))
        if change == "fenced":
            store.documents["controller.json"]["native_context"]["fenced"] = True
        elif change == "not-released":
            store.documents["controller.json"]["operations"][0]["phase"] = "ready-held"
        elif change == "receipt":
            store.documents["controller.json"]["operations"][0]["metadata"]["release_receipts"] = {}
        elif change == "release-count":
            store.documents["controller.json"]["operations"][0]["release_count"] = 0
        elif change == "owner":
            store.owner["generation"] = 8
        elif change == "claim":
            store.claims.clear()
        elif change == "runner":
            admission["runner_incarnation"] = "replacement-runner"
        elif change == "policy":
            admission["custom_definition"]["tools"].append("Bash")
        before = copy.deepcopy(store.documents)
        with pytest.raises(DaemonError) as exc:
            await adapter.callback(admission)
        assert exc.value.code == code
        assert store.documents == before
        assert store.lock_depth == 0

    asyncio.run(scenario())


def test_context_registration_is_not_a_public_wire_route(tmp_path):
    daemon, store, _, _ = native_fixture(tmp_path)

    async def scenario():
        await daemon.start()
        before = copy.deepcopy(store.documents)
        response = await daemon.handle_request({
            "schema": 2, "schema_version": 2,
            "architecture": "native-coordinator-lineage", "request_id": "forge-context",
            "lane": "build", "generation": 7, "operation": "register-native-context",
            "body": {"trusted_definitions": {"writer": {"tools": ["Bash"]}}},
        })
        assert response["ok"] is False
        assert response["code"] == "unsupported"
        assert store.documents == before

    asyncio.run(scenario())


def test_real_controller_write_failure_cannot_acknowledge_or_retry(tmp_path, monkeypatch):
    daemon, store, adapter, lineage = native_fixture(tmp_path)

    async def scenario():
        await daemon.start()
        admission = context_intent(register_context(daemon.controller, lineage))
        before = copy.deepcopy(store.documents)
        attempts = []

        def refuse_write(name, value):
            assert store.lock_depth > 0
            attempts.append(name)
            raise OSError("synthetic admission persistence failure")

        monkeypatch.setattr(store, "write_json", refuse_write)
        with pytest.raises(DaemonError) as exc:
            await adapter.callback(admission)
        assert exc.value.code == "uncertain-effect"
        assert attempts == ["controller.json"]
        assert store.documents == before
        assert store.lock_depth == 0

    asyncio.run(scenario())


def test_callback_reuses_wire_ack_and_stable_identity_without_policy_authority():
    store = MemoryStore()
    authority = RecordingAuthority(store)
    daemon, _, adapter = daemon_for(authority, store)

    async def scenario():
        await daemon.start()
        admission = intent()
        result = await adapter.callback(admission)
        assert result == {"accepted": True,
                          **{key: admission[key] for key in ACK_FIELDS}}
        await adapter.callback(dict(reversed(list(admission.items()))))
        changed = copy.deepcopy(admission)
        changed["custom_definition"]["effort"] = "low"
        changed["definition_digest"] = changed["trusted_definition_digest"] = "b" * 64
        await adapter.callback(changed)
        # A policy change stays under the same dedup identity, allowing the
        # real controller to reject it against trusted context/content.
        assert len({call[0] for call in authority.calls}) == 1
        assert authority.calls[0][0].startswith("native-admission-")
        assert authority.calls[0][1:] == (7, admission)
        changed["tool_use_id"] = "tool-2"
        await adapter.callback(changed)
        assert authority.calls[-1][0] != authority.calls[0][0]
        wire = await daemon.handle_request({
            "schema": 2, "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "request_id": "wire-admission", "lane": "build", "generation": 7,
            "operation": "native-admission-intent", "body": admission,
        })
        assert wire["result"] == result

    asyncio.run(scenario())


@pytest.mark.parametrize("field,value", [
    ("owner_generation", 8), ("owner_generation", True),
    ("policy", {"allow": ["Write"]}), ("agent_id", "invented-child"),
    ("launch_completed", True),
])
def test_callback_refuses_bad_intent_before_authority(field, value):
    store = MemoryStore()
    authority = RecordingAuthority(store)
    daemon, _, adapter = daemon_for(authority, store)

    async def scenario():
        await daemon.start()
        admission = intent()
        admission[field] = value
        with pytest.raises(DaemonError):
            await adapter.callback(admission)
        assert authority.calls == []

    asyncio.run(scenario())


@pytest.mark.parametrize("field", ACK_FIELDS)
def test_callback_refuses_uncorrelated_ack_without_retry(field):
    store = MemoryStore()
    authority = RecordingAuthority(store)
    authority.ack_override = lambda ack: ack.pop(field)
    daemon, _, adapter = daemon_for(authority, store)

    async def scenario():
        await daemon.start()
        with pytest.raises(DaemonError) as exc:
            await adapter.callback(intent())
        assert exc.value.code == "uncertain-effect"
        assert len(authority.calls) == 1

    asyncio.run(scenario())


def test_callback_refuses_inactive_or_foreign_owner_without_authority():
    store = MemoryStore()
    authority = RecordingAuthority(store)
    daemon, _, adapter = daemon_for(authority, store)

    async def scenario():
        with pytest.raises(DaemonError):
            await daemon._admit_native_callback(intent())
        await daemon.start()
        daemon.owner_record["daemon_id"] = "replacement-daemon"
        with pytest.raises(DaemonError) as exc:
            await adapter.callback(intent())
        assert exc.value.code == "ownership-conflict"
        assert authority.calls == []

    asyncio.run(scenario())
