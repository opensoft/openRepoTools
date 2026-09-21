# SPDX-License-Identifier: Apache-2.0
"""Coordinator-interrupt persistence across the real store/daemon/IPC seams.

The tests use the production controller, daemon owner checks, state store, and
SDK reader tasks with only the byte streams replaced by bounded in-memory
queues.  No client interrupt, model, account, or public daemon route is
invoked.  A positive intent acknowledgement is evidence that the durable
controller transaction committed; it is never an SDK-send result.
"""

from __future__ import annotations

import asyncio
import copy

import pytest

import lane_managed_sdk as sdk
from lane_managed_controller import LineageRecord, ManagedController
from lane_managed_daemon import DaemonError, _current_process_domain
from lane_managed_state import ManagedStateStore
from test_lane_managed_coordinator_interrupt import _evidence, _intent, _roster
from test_lane_managed_daemon_admission_integration import (
    HookAdapter,
    context_intent,
    daemon_for,
    native_fixture,
    trusted_definitions,
)
from test_lane_managed_sdk_admission_ipc import FakeProcess, QueueBridge, cancel
from test_lane_managed_state import _identity


class CoordinatorAdapter(HookAdapter):
    """Capture the daemon's real internal coordinator callbacks."""

    def bind_coordinator_interrupt(self, intent_callback, evidence_callback):
        self.interrupt_intent = intent_callback
        self.interrupt_evidence = evidence_callback


def real_interrupt_authority(tmp_path, managed_workspace):
    """Create a real on-disk owner/claim/controller before the hook starts."""
    # The synthetic fixture contributes only a valid enrolled roster and
    # release record.  Native context/admission and all interrupt writes use
    # the actual ManagedStateStore and public controller methods below.
    _, memory, _, seed_lineage = native_fixture(tmp_path)
    store = ManagedStateStore(_identity(managed_workspace, lane="build"))
    owner = store.enroll_managed(
        daemon_id="daemon-test", process_domain=_current_process_domain()
    )
    generation = owner["generation"]
    claim = store.claim_lineage(
        "lineage-1",
        coordinator_session_uuid=seed_lineage.session_uuid,
        owner_generation=generation,
        lineage_generation=1,
        parent_read_only=True,
    )
    raw = copy.deepcopy(memory.documents["controller.json"])
    raw["generation"] = generation
    raw["operations"][0]["generation"] = generation
    # A context with no interrupt yet has an explicit empty ledger.  Keeping
    # that namespace in the real snapshot makes the no-record state visible
    # and protects it from native-stop ledger migrations.
    raw.setdefault("coordinator_interrupts", {})
    store.write_json("controller.json", raw)
    lineage = seed_lineage.to_dict()
    lineage.update(
        owner_generation=generation,
        workspace=str(store.identity.workspace_root),
        common_dir=str(store.identity.common_dir),
        workspace_claim=claim,
    )
    lineage = LineageRecord.from_dict(lineage)
    adapter = CoordinatorAdapter()
    daemon, _, _ = daemon_for(store=store, adapter=adapter)
    return daemon, store, adapter, lineage


async def admitted_interrupt(daemon, adapter, lineage):
    """Register trusted context/admission, then create a real fenced op."""
    await daemon.start()
    context = daemon.controller.register_native_context(
        lineage.owner_generation,
        lineage,
        "runner-1",
        "invocation-1",
        trusted_definitions(),
        invocation_watermark=1,
    )
    admission = context_intent(context)
    admission["owner_generation"] = lineage.owner_generation
    await adapter.callback(admission)

    operation = daemon.controller.begin_operation(
        "coordinator-interrupt-operation",
        "swap",
        lineage.owner_generation,
        request_content={"target": "synthetic-test-profile"},
    )
    daemon.controller.fence(operation.operation_id)
    return _intent(
        lineage.to_dict(),
        admission,
        operation.operation_id,
        roster=_roster(admission),
        runner_instance_id="runner-1",
    )


def interrupt_bridge(adapter, intent):
    """Connect production reader/demux tasks through bounded queue streams."""
    identity = {
        key: intent[key]
        for key in ("participant_id", "session_id", "runner_instance_id")
    }
    spec = sdk.RunnerSpec(
        session_id=identity["session_id"],
        participant_id="coordinator",
        account_email="fake@example.invalid",
        permission_mode="default",
        model="sonnet",
        supported_models=("sonnet",),
        operation_deadline=1,
        fingerprint={
            "lineage_context": {
                "owner_generation": intent["interrupt"]["owner_generation"],
                "lineage_id": intent["interrupt"]["lineage_id"],
                "runner_incarnation": identity["runner_instance_id"],
            }
        },
    )
    connection = sdk._RunnerConnection(
        "coordinator",
        spec,
        FakeProcess(),
        identity["runner_instance_id"],
        strict_process_group=False,
        coordinator_interrupt_intent=adapter.interrupt_intent,
        coordinator_interrupt_evidence=adapter.interrupt_evidence,
    )
    supervisor, runner = QueueBridge(), QueueBridge()
    supervisor.incoming, supervisor.outgoing = runner.outgoing, runner.incoming
    connection.bridge = supervisor
    connection.started = connection.ready = True
    channel = sdk._NativeAdmissionIPC(runner, identity)
    controls = asyncio.Queue(maxsize=8)
    readers = (
        asyncio.create_task(connection._read_events()),
        asyncio.create_task(sdk._queue_controls(runner, controls, channel)),
    )
    return connection, channel, readers


@pytest.mark.parametrize(
    "order",
    [
        ("runtime-ack", "member-terminal", "tool-terminal", "effect-outcome"),
        ("effect-outcome", "tool-terminal", "member-terminal", "runtime-ack"),
    ],
)
def test_interrupt_ipc_progresses_under_control_lock_and_preserves_independent_facts(
    tmp_path, managed_workspace, order
):
    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )

    async def scenario():
        intent = await admitted_interrupt(daemon, adapter, lineage)
        claims = store.read_lineage_claims()
        connection, channel, readers = interrupt_bridge(adapter, intent)
        try:
            # The ordinary coordinator operation can hold this lock while the
            # dedicated event reader services internal interrupt transactions.
            async with connection._control_lock:
                assert await asyncio.wait_for(
                    channel.request_coordinator_interrupt_intent(intent), 2
                ) == {
                    "recorded": True,
                    "authorize_send": True,
                    "interrupt_id": "interrupt-1",
                }
                after_intent = store.read_json("controller.json")
                assert after_intent["coordinator_interrupts"]["interrupt-1"][
                    "authorization_count"
                ] == 1
                for kind in order:
                    evidence = _evidence(intent, kind)
                    assert await asyncio.wait_for(
                        channel.request_coordinator_interrupt_evidence(evidence), 2
                    ) == {
                        "recorded": True,
                        "evidence_id": "evidence-" + kind,
                        "interrupt_id": "interrupt-1",
                    }
                    persisted = store.read_json("controller.json")
                    assert await asyncio.wait_for(
                        channel.request_coordinator_interrupt_evidence(evidence), 2
                    ) == {
                        "recorded": True,
                        "evidence_id": "evidence-" + kind,
                        "interrupt_id": "interrupt-1",
                    }
                    assert store.read_json("controller.json") == persisted
            record = store.read_json("controller.json")["coordinator_interrupts"][
                "interrupt-1"
            ]
            assert set(record["evidence"]) == {
                "evidence-" + value for value in order
            }
            assert record["progress_watermark"] >= 9
            assert store.read_lineage_claims() == claims
            assert channel.pending == {}
        finally:
            await cancel(*readers)

    asyncio.run(scenario())


def test_lost_intent_ack_reload_and_retry_never_authorizes_second_send(
    tmp_path, managed_workspace, monkeypatch
):
    monkeypatch.setattr(sdk, "_NATIVE_ADMISSION_DEADLINE", 0.1)
    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )

    async def scenario():
        intent = await admitted_interrupt(daemon, adapter, lineage)
        connection, channel, readers = interrupt_bridge(adapter, intent)
        lost = asyncio.Event()

        async def drop_ack(frame):
            assert frame["operation"] == "coordinator-interrupt-intent-ack"
            assert frame["ack"]["authorize_send"] is True
            assert store.read_json("controller.json")["coordinator_interrupts"][
                "interrupt-1"
            ]["may_have_been_sent"] is True
            lost.set()

        connection.bridge.write = drop_ack
        try:
            with pytest.raises(sdk.SdkAdapterError) as caught:
                await channel.request_coordinator_interrupt_intent(intent)
            assert caught.value.code == "loader-failed"
            assert lost.is_set()
        finally:
            await cancel(*readers)

        before = store.read_json("controller.json")
        replacement = ManagedStateStore(store.identity)
        daemon.controller = ManagedController(
            replacement,
            runtime=adapter,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="daemon-test",
        )
        _, retry_channel, retry_readers = interrupt_bridge(adapter, intent)
        try:
            assert await retry_channel.request_coordinator_interrupt_intent(intent) == {
                "recorded": True,
                "authorize_send": False,
                "interrupt_id": "interrupt-1",
            }
            assert replacement.read_json("controller.json") == before
        finally:
            await cancel(*retry_readers)

    asyncio.run(scenario())


def test_daemon_takeover_is_checked_before_coordinator_persistence(
    tmp_path, managed_workspace, monkeypatch
):
    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )

    async def scenario():
        intent = await admitted_interrupt(daemon, adapter, lineage)
        before = store.read_json("controller.json")
        original = daemon._assert_coordinator_interrupt_owner

        async def takeover(deadline):
            await original(deadline)
            owner = store.read_owner()
            owner["daemon_id"] = "replacement-daemon"
            store.write_json("owner.json", owner)

        monkeypatch.setattr(daemon, "_assert_coordinator_interrupt_owner", takeover)
        with pytest.raises(DaemonError) as caught:
            await adapter.interrupt_intent(intent)
        assert caught.value.code == "ownership-conflict"
        assert store.read_json("controller.json") == before

    asyncio.run(scenario())


def test_public_daemon_has_no_coordinator_interrupt_route(
    tmp_path, managed_workspace
):
    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )

    async def scenario():
        intent = await admitted_interrupt(daemon, adapter, lineage)
        before = store.read_json("controller.json")
        response = await daemon.handle_request(
            {
                "schema": 2,
                "schema_version": 2,
                "architecture": "native-coordinator-lineage",
                "request_id": "forged-coordinator-interrupt",
                "lane": "build",
                "generation": lineage.owner_generation,
                "operation": "coordinator-interrupt-intent",
                "body": intent,
            }
        )
        assert response["ok"] is False
        assert response["code"] == "unsupported"
        assert store.read_json("controller.json") == before

    asyncio.run(scenario())
