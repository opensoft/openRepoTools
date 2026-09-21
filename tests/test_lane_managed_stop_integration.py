# SPDX-License-Identifier: Apache-2.0
"""Native stop persistence across real private-store reloads; no live runtime."""

import asyncio
import copy

import pytest
import lane_managed_sdk as sdk

from lane_managed_controller import ControllerError, LineageRecord, ManagedController
from lane_managed_daemon import DaemonError, _current_process_domain
from lane_managed_state import ManagedStateStore
from test_lane_managed_state import _identity
from test_lane_managed_daemon_admission_integration import (
    HookAdapter, context_intent, daemon_for, native_fixture, trusted_definitions,
)
from test_lane_managed_sdk_admission_ipc import FakeProcess, QueueBridge, cancel


class StopAdapter(HookAdapter):
    """Capture the real daemon's internal callbacks without opening an SDK."""

    def bind_native_stop(self, intent_callback, evidence_callback):
        self.stop_intent = intent_callback
        self.stop_evidence = evidence_callback


def stop_bridge(adapter, intent):
    """Real protocol readers/callbacks with only the byte transport replaced."""
    identity = {key: intent[key] for key in
                ("participant_id", "session_id", "runner_instance_id")}
    spec = sdk.RunnerSpec(
        session_id=identity["session_id"], participant_id="coordinator",
        account_email="fake@example.invalid", permission_mode="default",
        model="sonnet", supported_models=("sonnet",), operation_deadline=1,
        fingerprint={"lineage_context": {
            "owner_generation": intent["stop"]["owner_generation"],
            "lineage_id": intent["stop"]["lineage_id"],
            "runner_incarnation": identity["runner_instance_id"],
        }},
    )
    connection = sdk._RunnerConnection(
        "coordinator", spec, FakeProcess(), identity["runner_instance_id"],
        strict_process_group=False, native_stop_intent=adapter.stop_intent,
        native_stop_evidence=adapter.stop_evidence,
    )
    supervisor, runner = QueueBridge(), QueueBridge()
    supervisor.incoming, supervisor.outgoing = runner.outgoing, runner.incoming
    connection.bridge = supervisor
    # The fixture starts after the synthetic coordinator's held startup;
    # startup and SDK construction are outside this transport/persistence test.
    connection.started = connection.ready = True
    channel = sdk._NativeAdmissionIPC(runner, identity)
    controls = asyncio.Queue(maxsize=8)
    readers = (
        asyncio.create_task(connection._read_events()),
        asyncio.create_task(sdk._queue_controls(runner, controls, channel)),
    )
    return connection, channel, readers


def real_stop_authority(tmp_path, managed_workspace):
    # Reuse only the synthetic lifecycle setup. Persistence and claim authority
    # below use the actual secure on-disk store, never the memory-store methods.
    _, memory, _, seed_lineage = native_fixture(tmp_path)
    store = ManagedStateStore(_identity(managed_workspace, lane="build"))
    owner = store.enroll_managed(daemon_id="daemon-test",
                                 process_domain=_current_process_domain())
    generation = owner["generation"]
    claim = store.claim_lineage(
        "lineage-1", coordinator_session_uuid=seed_lineage.session_uuid,
        owner_generation=generation, lineage_generation=1, parent_read_only=True,
    )
    raw = copy.deepcopy(memory.documents["controller.json"])
    raw["generation"] = generation
    raw["operations"][0]["generation"] = generation
    store.write_json("controller.json", raw)
    lineage = seed_lineage.to_dict()
    lineage.update(owner_generation=generation,
                   workspace=str(store.identity.workspace_root),
                   common_dir=str(store.identity.common_dir), workspace_claim=claim)
    lineage = LineageRecord.from_dict(lineage)
    adapter = StopAdapter()
    daemon, _, _ = daemon_for(store=store, adapter=adapter)
    return daemon, store, adapter, lineage


async def admitted_stop(daemon, adapter, lineage):
    await daemon.start()
    context = daemon.controller.register_native_context(
        lineage.owner_generation, lineage, "runner-1", "invocation-1",
        trusted_definitions(), invocation_watermark=1,
    )
    admission = context_intent(context)
    admission["owner_generation"] = lineage.owner_generation
    await adapter.callback(admission)
    return {
        "type": "native-stop-intent", "participant_id": "coordinator",
        "session_id": lineage.session_uuid, "runner_instance_id": "runner-1",
        "stop": {
            "stop_id": "stop-1", "owner_generation": lineage.owner_generation,
            "lineage_id": lineage.lineage_id, "invocation_id": "invocation-1",
            "admission_id": admission["admission_id"], "tool_use_id": "tool-1",
            "agent_id": "actual-agent-1", "task_id": "actual-task-1",
            "lineage_incarnation": 1,
            "trusted_definition_digest": admission["trusted_definition_digest"],
            "observed_watermark": 5,
            "observation": {
                "status": "active", "task_terminal": False, "start_watermark": 3,
                "task_start_event": {"event_uuid": "task-start-event-1",
                                     "watermark": 4, "task_type": "local_agent"},
                "active_tool_ids": ["unfinished-tool"], "uncertain_tool_ids": [],
                "unresolved_effect_ids": [],
            },
        },
    }


def evidence_frame(intent, kind):
    value = {key: intent[key] for key in
             ("participant_id", "session_id", "runner_instance_id")}
    evidence = {
        "evidence_id": "evidence-" + kind, "stop_id": intent["stop"]["stop_id"],
        "kind": kind, "agent_id": intent["stop"]["agent_id"],
        "task_id": intent["stop"]["task_id"], "lineage_incarnation": 1,
        "observed_watermark": 5 if kind == "runtime-ack" else 6,
    }
    if kind == "runtime-ack":
        evidence.update(accepted=True, ack_kind="accepted-stop")
    else:
        evidence.update(
            event_kind="task_notification", event_uuid="task-stopped-event-1",
            status="stopped", tool_use_id="tool-1",
            observation={"task_terminal": True, "active_tool_ids": ["unfinished-tool"],
                         "uncertain_tool_ids": [], "unresolved_effect_ids": []},
        )
    return {**value, "type": "native-stop-evidence", "evidence": evidence}


@pytest.mark.parametrize("order", [("runtime-ack", "terminal"), ("terminal", "runtime-ack")])
def test_stop_ipc_crosses_real_daemon_and_store_without_control_lock_deadlock(
        tmp_path, managed_workspace, order):
    daemon, store, adapter, lineage = real_stop_authority(tmp_path, managed_workspace)

    async def scenario():
        intent = await admitted_stop(daemon, adapter, lineage)
        claims = store.read_lineage_claims()
        connection, channel, readers = stop_bridge(adapter, intent)
        try:
            # A real control waiter can hold this lock while the independent
            # readers service durability acknowledgements in either direction.
            async with connection._control_lock:
                ack = await asyncio.wait_for(channel.request_native_stop_intent(intent), 2)
                assert ack == {"recorded": True, "authorize_send": True, "stop_id": "stop-1"}
                after_intent = store.read_json("controller.json")
                assert await asyncio.wait_for(channel.request_native_stop_intent(intent), 2) == {
                    "recorded": True, "authorize_send": False, "stop_id": "stop-1"}
                assert store.read_json("controller.json") == after_intent
                for kind in order:
                    frame = evidence_frame(intent, kind)
                    ack = await asyncio.wait_for(channel.request_native_stop_evidence(frame), 2)
                    assert ack == {"recorded": True, "evidence_id": "evidence-" + kind,
                                   "stop_id": "stop-1"}
                    after_evidence = store.read_json("controller.json")
                    assert await asyncio.wait_for(channel.request_native_stop_evidence(frame), 2) == ack
                    assert store.read_json("controller.json") == after_evidence
            record = store.read_json("controller.json")["native_stops"]["stop-1"]
            assert record["authorization_count"] == 1
            assert record["runtime_ack"]["evidence"]["accepted"] is True
            assert record["terminal_evidence"]["evidence"]["observation"]["active_tool_ids"] == ["unfinished-tool"]
            assert store.read_lineage_claims() == claims
            assert channel.pending == {}
        finally:
            await cancel(*readers)

    asyncio.run(scenario())


def test_lost_stop_ipc_ack_reconnect_cannot_authorize_a_second_send(
        tmp_path, managed_workspace, monkeypatch):
    monkeypatch.setattr(sdk, "_NATIVE_ADMISSION_DEADLINE", 0.1)
    daemon, store, adapter, lineage = real_stop_authority(tmp_path, managed_workspace)

    async def scenario():
        intent = await admitted_stop(daemon, adapter, lineage)
        connection, channel, readers = stop_bridge(adapter, intent)
        lost_ack = asyncio.Event()

        async def drop_ack(frame):
            assert frame["operation"] == "native-stop-intent-ack"
            assert frame["ack"]["authorize_send"] is True
            # The durable write has happened; the caller never receives it.
            assert store.read_json("controller.json")["native_stops"]["stop-1"]["may_have_been_sent"] is True
            lost_ack.set()

        connection.bridge.write = drop_ack
        try:
            with pytest.raises(sdk.SdkAdapterError) as caught:
                await channel.request_native_stop_intent(intent)
            assert caught.value.code == "loader-failed"
            assert lost_ack.is_set()
        finally:
            await cancel(*readers)
        before = store.read_json("controller.json")
        daemon.controller = ManagedController(store, runtime=adapter,
                                               _native_stop_daemon_id="daemon-test")
        _, channel, readers = stop_bridge(adapter, intent)
        try:
            assert await channel.request_native_stop_intent(intent) == {
                "recorded": True, "authorize_send": False, "stop_id": "stop-1"}
            assert store.read_json("controller.json") == before
        finally:
            await cancel(*readers)

    asyncio.run(scenario())


def test_concurrent_stop_ids_for_one_incarnation_authorize_only_one(
        tmp_path, managed_workspace):
    daemon, store, adapter, lineage = real_stop_authority(tmp_path, managed_workspace)

    async def scenario():
        intent = await admitted_stop(daemon, adapter, lineage)
        other = copy.deepcopy(intent)
        other["stop"]["stop_id"] = "competing-stop"
        results = await asyncio.gather(adapter.stop_intent(intent),
                                       adapter.stop_intent(other), return_exceptions=True)
        successes = [value for value in results if isinstance(value, dict)]
        failures = [value for value in results if isinstance(value, DaemonError)]
        assert len(successes) == len(failures) == 1
        assert successes[0]["recorded"] is True
        assert successes[0]["authorize_send"] is True
        assert failures[0].code == "busy"
        records = store.read_json("controller.json")["native_stops"]
        assert list(records) == [successes[0]["stop_id"]]
        assert sum(record["authorization_count"] for record in records.values()) == 1

    asyncio.run(scenario())


def test_stop_store_write_failure_never_returns_authorization(
        tmp_path, managed_workspace, monkeypatch):
    daemon, store, adapter, lineage = real_stop_authority(tmp_path, managed_workspace)

    async def scenario():
        intent = await admitted_stop(daemon, adapter, lineage)
        before = store.read_json("controller.json")
        claims = store.read_lineage_claims()
        original_write = store.write_json

        def refuse_write(name, value):
            if name == "controller.json":
                raise OSError("synthetic disk failure before commit")
            return original_write(name, value)

        monkeypatch.setattr(store, "write_json", refuse_write)
        with pytest.raises(DaemonError) as caught:
            await adapter.stop_intent(intent)
        assert caught.value.code == "uncertain-effect"
        assert store.read_json("controller.json") == before
        assert store.read_lineage_claims() == claims
        assert "stop-1" not in before["native_stops"]

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["native-stop", "native-stop-intent",
                                        "native-stop-evidence", "stop-task"])
def test_public_daemon_cannot_route_internal_stop_transactions(
        tmp_path, managed_workspace, operation):
    daemon, store, adapter, lineage = real_stop_authority(tmp_path, managed_workspace)

    async def scenario():
        intent = await admitted_stop(daemon, adapter, lineage)
        before = store.read_json("controller.json")
        claims = store.read_lineage_claims()
        response = await daemon.handle_request({
            "schema": 2, "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "request_id": "forged-stop", "lane": "build",
            "generation": lineage.owner_generation,
            "operation": operation, "body": intent,
        })
        assert response["ok"] is False
        assert response["code"] == "unsupported"
        assert store.read_json("controller.json") == before
        assert store.read_lineage_claims() == claims

    asyncio.run(scenario())


@pytest.mark.parametrize("order", [("runtime-ack", "terminal"), ("terminal", "runtime-ack")])
@pytest.mark.parametrize("shape", ["distinct-ids", "equal-observed-ids", "task-before-agent"])
def test_real_stop_store_preserves_claim_and_both_event_orders_after_reload(
        tmp_path, managed_workspace, order, shape):
    daemon, store, adapter, lineage = real_stop_authority(tmp_path, managed_workspace)

    async def scenario():
        intent = await admitted_stop(daemon, adapter, lineage)
        if shape == "equal-observed-ids":
            # Equal observed IDs are legitimate in the pinned local_agent
            # runtime; equality alone is neither fabrication nor evidence.
            intent["stop"]["task_id"] = intent["stop"]["agent_id"]
        elif shape == "task-before-agent":
            observation = intent["stop"]["observation"]
            observation["start_watermark"] = 4
            observation["task_start_event"]["watermark"] = 3
            observation["uncertain_tool_ids"] = ["unfinished-tool"]
        claims = store.read_lineage_claims()
        first = await adapter.stop_intent(intent)
        assert first == {"recorded": True, "authorize_send": True, "stop_id": "stop-1"}
        persisted = store.read_json("controller.json")
        assert persisted["native_stops"]["stop-1"]["may_have_been_sent"] is True
        assert persisted["native_stops"]["stop-1"]["authorization_count"] == 1
        # A fresh controller has no in-memory knowledge of the prior send.
        # It must still refuse to grant another send, including while fenced.
        persisted["native_context"]["fenced"] = True
        store.write_json("controller.json", persisted)
        daemon.controller = ManagedController(store, runtime=adapter,
                                               _native_stop_daemon_id="daemon-test")
        before = store.read_json("controller.json")
        assert await adapter.stop_intent(intent) == {
            "recorded": True, "authorize_send": False, "stop_id": "stop-1"}
        assert store.read_json("controller.json") == before
        for kind in order:
            frame = evidence_frame(intent, kind)
            ack = await adapter.stop_evidence(frame)
            assert ack == {"recorded": True, "evidence_id": "evidence-" + kind,
                           "stop_id": "stop-1"}
            after = store.read_json("controller.json")
            daemon.controller = ManagedController(store, runtime=adapter,
                                                   _native_stop_daemon_id="daemon-test")
            assert await adapter.stop_evidence(frame) == ack
            assert store.read_json("controller.json") == after
            conflicting = copy.deepcopy(frame)
            conflicting["evidence"]["observed_watermark"] += 1
            with pytest.raises(DaemonError) as caught:
                await adapter.stop_evidence(conflicting)
            assert caught.value.code == "invalid"
            assert store.read_json("controller.json") == after
        record = store.read_json("controller.json")["native_stops"]["stop-1"]
        assert record["runtime_ack"] is not None
        assert record["terminal_evidence"] is not None
        assert record.get("restore_state_clear", "unknown") == "unknown"
        assert record.get("quiescent", False) is False
        assert store.read_lineage_claims() == claims

    asyncio.run(scenario())


@pytest.mark.parametrize("corruption", ["missing-ledger", "boolean-count"])
def test_real_stop_store_refuses_corruption_without_losing_no_replay_record(
        tmp_path, managed_workspace, corruption):
    daemon, store, adapter, lineage = real_stop_authority(tmp_path, managed_workspace)

    async def scenario():
        intent = await admitted_stop(daemon, adapter, lineage)
        await adapter.stop_intent(intent)
        corrupted = store.read_json("controller.json")
        if corruption == "missing-ledger":
            del corrupted["native_stops"]
        else:
            corrupted["native_stops"]["stop-1"]["authorization_count"] = True
        store.write_json("controller.json", corrupted)
        with pytest.raises(ControllerError) as caught:
            ManagedController(store, _native_stop_daemon_id="daemon-test")
        assert caught.value.code == "invalid"
        assert store.read_json("controller.json") == corrupted

    asyncio.run(scenario())


def test_real_stop_store_uncertain_intent_survives_recovery_without_reauthorization(
        tmp_path, managed_workspace):
    daemon, store, adapter, lineage = real_stop_authority(tmp_path, managed_workspace)

    async def scenario():
        intent = await admitted_stop(daemon, adapter, lineage)
        await adapter.stop_intent(intent)
        # Simulate a lost permission ACK before an SDK call. Durable state is
        # deliberately identical to a crash after the call: neither may replay.
        replacement_store = ManagedStateStore(store.identity)
        daemon.controller = ManagedController(replacement_store, runtime=adapter,
                                               _native_stop_daemon_id="daemon-test")
        assert (await adapter.stop_intent(intent))["authorize_send"] is False
        changed = copy.deepcopy(intent)
        changed["stop"]["task_id"] = "different-task"
        before = replacement_store.read_json("controller.json")
        with pytest.raises(DaemonError) as caught:
            await adapter.stop_intent(changed)
        assert caught.value.code == "invalid"
        assert replacement_store.read_json("controller.json") == before
        another_id = copy.deepcopy(intent)
        another_id["stop"]["stop_id"] = "stop-second-id"
        with pytest.raises(DaemonError) as caught:
            await adapter.stop_intent(another_id)
        assert caught.value.code == "busy"
        assert replacement_store.read_json("controller.json") == before
        record = before["native_stops"]["stop-1"]
        assert record["runtime_ack"] is None
        assert record["terminal_evidence"] is None

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["intent", "evidence"])
def test_stop_takeover_between_daemon_precheck_and_controller_write_refuses(
        tmp_path, managed_workspace, monkeypatch, stage):
    daemon, store, adapter, lineage = real_stop_authority(tmp_path, managed_workspace)

    async def scenario():
        intent = await admitted_stop(daemon, adapter, lineage)
        if stage == "evidence":
            await adapter.stop_intent(intent)
        before = store.read_json("controller.json")
        claims = store.read_lineage_claims()
        check = daemon._assert_native_stop_owner

        async def takeover_after_check(deadline):
            await check(deadline)
            owner = store.read_owner()
            owner["daemon_id"] = "replacement-daemon"
            store.write_json("owner.json", owner)

        monkeypatch.setattr(daemon, "_assert_native_stop_owner", takeover_after_check)
        with pytest.raises(DaemonError) as caught:
            if stage == "intent":
                await adapter.stop_intent(intent)
            else:
                await adapter.stop_evidence(evidence_frame(intent, "runtime-ack"))
        assert caught.value.code == "ownership-conflict"
        assert store.read_json("controller.json") == before
        assert store.read_lineage_claims() == claims

    asyncio.run(scenario())
