# SPDX-License-Identifier: Apache-2.0
"""Coordinator-interrupt IPC and runner-reader tests.

These tests exercise only the authenticated SDK bridge.  They do not dispatch
an SDK interrupt, start a model, or claim that the fake callbacks provide live
runtime support.
"""

from __future__ import annotations

import asyncio
import copy

import pytest

import lane_managed_sdk as sdk


SESSION = "11111111-1111-4111-8111-111111111111"
IDENTITY = {
    "participant_id": "coordinator",
    "session_id": SESSION,
    "runner_instance_id": "runner-1",
}
EOF = object()


class QueueBridge:
    """Bounded fake duplex stream used without a control consumer."""

    def __init__(self) -> None:
        self.incoming: asyncio.Queue[object] = asyncio.Queue()
        self.outgoing: asyncio.Queue[dict[str, object]] = asyncio.Queue()

    async def read(self):
        value = await self.incoming.get()
        if value is EOF:
            raise StopAsyncIteration
        return copy.deepcopy(value)

    async def write(self, value):
        await self.outgoing.put(copy.deepcopy(value))


class FakeProcess:
    pid = None
    stdin = stdout = stderr = None

    @staticmethod
    def poll():
        return None


def _spec() -> sdk.RunnerSpec:
    return sdk.RunnerSpec(
        session_id=SESSION,
        participant_id="coordinator",
        account_email="target@example.invalid",
        permission_mode="default",
        model="sonnet",
        supported_models=("sonnet",),
        operation_deadline=0.2,
    )


def _intent(interrupt_id: str = "interrupt-1") -> dict:
    return {
        "type": "coordinator-interrupt-intent",
        **IDENTITY,
        "interrupt": {
            "interrupt_id": interrupt_id,
            "operation_id": "operation-1",
            "fence_epoch": 3,
            "roster_identity_digest": "a" * 64,
        },
    }


def _evidence(
    evidence_id: str = "evidence-1", interrupt_id: str = "interrupt-1"
) -> dict:
    return {
        "type": "coordinator-interrupt-evidence",
        **IDENTITY,
        "evidence": {
            "evidence_id": evidence_id,
            "interrupt_id": interrupt_id,
            "kind": "runtime-ack",
            "observed_watermark": 4,
            "data": {"accepted": True},
        },
    }


def _intent_ack(
    interrupt_id: str, *, authorize_send: bool, recorded: bool = True
) -> dict:
    return {
        "operation": "coordinator-interrupt-intent-ack",
        **IDENTITY,
        "interrupt_id": interrupt_id,
        "ack": {
            "recorded": recorded,
            "authorize_send": authorize_send,
            "interrupt_id": interrupt_id,
        },
    }


def _evidence_ack(
    evidence_id: str, interrupt_id: str, *, recorded: bool = True
) -> dict:
    return {
        "operation": "coordinator-interrupt-evidence-ack",
        **IDENTITY,
        "evidence_id": evidence_id,
        "interrupt_id": interrupt_id,
        "ack": {
            "recorded": recorded,
            "evidence_id": evidence_id,
            "interrupt_id": interrupt_id,
        },
    }


def test_ipc_does_not_replay_positive_authorization_to_a_retry() -> None:
    async def scenario() -> None:
        bridge = QueueBridge()
        channel = sdk._NativeAdmissionIPC(bridge, IDENTITY)
        frame = _intent()
        first = asyncio.create_task(
            channel.request_coordinator_interrupt_intent(frame)
        )
        try:
            await asyncio.wait_for(bridge.outgoing.get(), 1)
            positive = _intent_ack("interrupt-1", authorize_send=True)
            channel.receive(positive)
            assert await asyncio.wait_for(first, 1) == positive["ack"]

            retry = asyncio.create_task(
                channel.request_coordinator_interrupt_intent(frame)
            )
            await asyncio.wait_for(bridge.outgoing.get(), 1)
            # A delayed copy of the first receipt cannot grant the retry.
            channel.receive(positive)
            await asyncio.sleep(0)
            assert not retry.done()

            durable_duplicate = _intent_ack(
                "interrupt-1", authorize_send=False
            )
            channel.receive(durable_duplicate)
            assert await asyncio.wait_for(retry, 1) == durable_duplicate["ack"]
            assert channel._coordinator_interrupt_authorized_ids == {
                "interrupt-1"
            }
        finally:
            if not first.done():
                first.cancel()
            if "retry" in locals() and not retry.done():
                retry.cancel()
            await asyncio.gather(first, *( [retry] if "retry" in locals() else [] ), return_exceptions=True)

    asyncio.run(scenario())


def test_ipc_keeps_interrupt_and_native_stop_namespaces_distinct() -> None:
    async def scenario() -> None:
        bridge = QueueBridge()
        channel = sdk._NativeAdmissionIPC(bridge, IDENTITY)
        interrupt = _intent("shared-id")
        native_stop = {
            "type": "native-stop-intent",
            **IDENTITY,
            "stop": {"stop_id": "shared-id"},
        }
        interrupt_waiter = asyncio.create_task(
            channel.request_coordinator_interrupt_intent(interrupt)
        )
        stop_waiter = asyncio.create_task(
            channel.request_native_stop_intent(native_stop)
        )
        try:
            operations = {
                (await asyncio.wait_for(bridge.outgoing.get(), 1))["type"]
                for _ in range(2)
            }
            assert operations == {"coordinator-interrupt-intent", "native-stop-intent"}
            channel.receive(_intent_ack("shared-id", authorize_send=True))
            channel.receive({
                "operation": "native-stop-intent-ack",
                **IDENTITY,
                "stop_id": "shared-id",
                "ack": {
                    "recorded": True,
                    "authorize_send": True,
                    "stop_id": "shared-id",
                },
            })
            assert (await asyncio.wait_for(interrupt_waiter, 1))["interrupt_id"] == "shared-id"
            assert (await asyncio.wait_for(stop_waiter, 1))["stop_id"] == "shared-id"

            evidence = _evidence()
            evidence_waiter = asyncio.create_task(
                channel.request_coordinator_interrupt_evidence(evidence)
            )
            await asyncio.wait_for(bridge.outgoing.get(), 1)
            mismatched = _evidence_ack("evidence-1", "another-interrupt")
            with pytest.raises(sdk.SdkAdapterError):
                channel.receive(mismatched)
            channel.close()
            with pytest.raises(sdk.SdkAdapterError):
                await asyncio.wait_for(evidence_waiter, 1)
        finally:
            for waiter in (interrupt_waiter, stop_waiter):
                if not waiter.done():
                    waiter.cancel()
            await asyncio.gather(interrupt_waiter, stop_waiter, return_exceptions=True)

    asyncio.run(scenario())


def test_reader_services_interrupt_callbacks_while_control_lock_is_held() -> None:
    async def scenario() -> None:
        bridge = QueueBridge()
        intent_started = asyncio.Event()
        evidence_started = asyncio.Event()
        release_callbacks = asyncio.Event()

        async def intent_callback(frame):
            intent_started.set()
            await release_callbacks.wait()
            return {
                "recorded": True,
                "authorize_send": True,
                "interrupt_id": frame["interrupt"]["interrupt_id"],
            }

        async def evidence_callback(frame):
            evidence_started.set()
            await release_callbacks.wait()
            return {
                "recorded": True,
                "evidence_id": frame["evidence"]["evidence_id"],
                "interrupt_id": frame["evidence"]["interrupt_id"],
            }

        connection = sdk._RunnerConnection(
            "coordinator",
            _spec(),
            FakeProcess(),
            IDENTITY["runner_instance_id"],
            strict_process_group=False,
            coordinator_interrupt_intent=intent_callback,
            coordinator_interrupt_evidence=evidence_callback,
        )
        connection.bridge = bridge
        connection.started = connection.ready = True
        connection.start_reader()
        try:
            async with connection._control_lock:
                await bridge.incoming.put(_intent())
                await bridge.incoming.put(_evidence())
                await asyncio.wait_for(intent_started.wait(), 1)
                await asyncio.wait_for(evidence_started.wait(), 1)

                # A normal control/event frame remains readable while both
                # persistence callbacks await, even though this lock is held.
                await bridge.incoming.put({**IDENTITY, "type": "status"})
                status = await asyncio.wait_for(connection.events.get(), 1)
                assert status["type"] == "status"
                release_callbacks.set()

                acknowledgements = {
                    (await asyncio.wait_for(bridge.outgoing.get(), 1))["operation"]
                    for _ in range(2)
                }
                assert acknowledgements == {
                    "coordinator-interrupt-intent-ack",
                    "coordinator-interrupt-evidence-ack",
                }
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_reader_cancels_pending_interrupt_callback_on_eof() -> None:
    async def scenario() -> None:
        bridge = QueueBridge()
        callback_started = asyncio.Event()
        callback_cancelled = asyncio.Event()

        async def intent_callback(_frame):
            callback_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                callback_cancelled.set()

        connection = sdk._RunnerConnection(
            "coordinator",
            _spec(),
            FakeProcess(),
            IDENTITY["runner_instance_id"],
            strict_process_group=False,
            coordinator_interrupt_intent=intent_callback,
        )
        connection.bridge = bridge
        connection.started = connection.ready = True
        connection.start_reader()
        await bridge.incoming.put(_intent())
        try:
            await asyncio.wait_for(callback_started.wait(), 1)
            await bridge.incoming.put(EOF)
            await asyncio.wait_for(connection.reader_task, 1)
            await asyncio.sleep(0)
            assert callback_cancelled.is_set()
            assert not connection._coordinator_interrupt_tasks
            assert not connection._coordinator_interrupt_intent_inflight
            assert bridge.outgoing.empty()
        finally:
            await connection.close()

    asyncio.run(scenario())
