# SPDX-License-Identifier: Apache-2.0
"""Fake-only SDK native-swap release-boundary tests.

The tests exercise the private authorization bridge and the runner's held to
released transition.  No provider, account, model, prompt, or live process is
used; an injected client/bridge is the only runtime seam.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncIterator, Mapping

import pytest

import lane_managed_sdk as sdk
from lane_managed_swap import canonical_digest


SESSION = "11111111-1111-4111-8111-111111111111"
PARTICIPANT = "coordinator"
RUNNER = "runner-incarnation-1"
LINEAGE = "lineage-1"
IDENTITY = {
    "participant_id": PARTICIPANT,
    "session_id": SESSION,
    "runner_instance_id": RUNNER,
}
CONTEXT = {
    "owner_generation": 7,
    "lineage_id": LINEAGE,
    "lineage_generation": 3,
    "runner_incarnation": RUNNER,
}


def _binding(**changes):
    value = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-swap-release-binding",
        "operation_id": "swap-operation-1",
        "owner_generation": 7,
        "expected_daemon_id": "daemon-1",
        "participant_id": PARTICIPANT,
        "session_id": SESSION,
        "runner_incarnation": RUNNER,
        "lineage_id": LINEAGE,
        "lineage_generation": 3,
        "request_epoch_id": "epoch-1",
        "release_id": "release-1",
        "release_intent_digest": "1" * 64,
        "pre_release_evidence_digest": "2" * 64,
        "binding_digest": "",
    }
    value.update(changes)
    value["binding_digest"] = canonical_digest(
        {key: item for key, item in value.items() if key != "binding_digest"}
    )
    return value


def _authorization(binding, validation_id, *, authorized=True, authorization_id="auth-1"):
    value = {
        "validation_id": validation_id,
        "authorized": authorized,
        "authorization_id": authorization_id,
        "binding": copy.deepcopy(binding),
        "authorization_digest": "",
    }
    value["authorization_digest"] = canonical_digest(
        {key: item for key, item in value.items() if key != "authorization_digest"}
    )
    return value


def _spec(**changes):
    values = {
        "session_id": SESSION,
        "participant_id": PARTICIPANT,
        "account_email": "fake@example.invalid",
        "permission_mode": "default",
        "model": "sonnet",
        "supported_models": ("sonnet",),
        "startup_deadline": 1,
        "operation_deadline": 1,
        "fingerprint": {"lineage_context": copy.deepcopy(CONTEXT)},
    }
    values.update(changes)
    return sdk.RunnerSpec(**values)


class IdleProcess:
    pid = None
    stdin = stdout = stderr = None

    @staticmethod
    def poll():
        return None


class QueueBridge:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.outgoing = asyncio.Queue()
        self.writes = []

    async def read(self):
        return copy.deepcopy(await self.incoming.get())

    async def write(self, value):
        frame = copy.deepcopy(dict(value))
        self.writes.append(frame)
        await self.outgoing.put(frame)


class ReleaseReplyBridge(QueueBridge):
    def __init__(self, identity, boundary=None):
        super().__init__()
        self.identity = dict(identity)
        self.boundary = copy.deepcopy(boundary)

    async def write(self, value):
        await super().write(value)
        if value.get("operation") == "release":
            reply = {
                "type": "released",
                **self.identity,
                "request_id": value["request_id"],
                "release_receipt": True,
            }
            if self.boundary is not None:
                reply["native_swap_release_boundary"] = copy.deepcopy(self.boundary)
            await self.incoming.put(reply)


class HeldClient:
    STOP = object()

    def __init__(self, options):
        self.options = options
        self.events = asyncio.Queue()
        self.calls = []

    async def connect(self, prompt=None):
        self.calls.append(("connect", prompt))
        await self.events.put(
            {
                "type": "system",
                "subtype": "init",
                "session_id": SESSION,
                "account": {"email": "fake@example.invalid"},
                "current_permission_mode": "default",
                "session_state": "idle",
                "model": "sonnet",
                "models": ["sonnet"],
            }
        )

    async def receive_messages(self) -> AsyncIterator[object]:
        while True:
            event = await self.events.get()
            if event is self.STOP:
                return
            yield event

    async def query(self, *args, **kwargs):
        self.calls.append(("query", args, kwargs))

    async def disconnect(self):
        self.calls.append(("disconnect",))
        await self.events.put(self.STOP)


class AuthIPC:
    def __init__(self, *, authorized=True, timeout=False):
        self.authorized = authorized
        self.timeout = timeout
        self.frames = []

    async def request_native_swap_release(self, frame):
        self.frames.append(copy.deepcopy(frame))
        if self.timeout:
            raise asyncio.TimeoutError
        return _authorization(
            frame["binding"],
            frame["validation_id"],
            authorized=self.authorized,
            authorization_id="auth-1" if self.authorized else "refused-controller",
        )


def _connection(bridge, *, callback=None, spec=None):
    connection = sdk._RunnerConnection(
        PARTICIPANT,
        _spec() if spec is None else spec,
        IdleProcess(),
        RUNNER,
        strict_process_group=False,
        native_swap_release=callback,
    )
    connection.bridge = bridge
    connection.started = True
    connection.ready = True
    return connection


async def _cancel(*tasks):
    for task in tasks:
        if task is not None and not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def test_adapter_native_release_frame_has_exact_binding_and_gate_receipt():
    async def scenario():
        binding = _binding()
        boundary = {
            "binding": copy.deepcopy(binding),
            "gate_event_id": "gate-1",
            "gate_watermark": 9,
        }
        bridge = ReleaseReplyBridge(IDENTITY, boundary)
        connection = _connection(bridge)
        reader = None
        try:
            connection.start_reader()
            reader = connection.reader_task
            result = await connection.release(native_swap_binding=binding)
            frame = bridge.writes[0]
            assert frame["operation"] == "release"
            assert frame["payload_ref"] == binding
            assert "prompt" not in frame
            assert result["native_swap_release_boundary"] == boundary
            assert connection.evidence()["native_swap_release_boundary"] == boundary
        finally:
            await connection.close()
            await _cancel(reader)

    asyncio.run(scenario())


def test_adapter_legacy_release_has_no_native_payload_or_boundary():
    async def scenario():
        bridge = ReleaseReplyBridge(IDENTITY)
        connection = _connection(bridge)
        reader = None
        try:
            connection.start_reader()
            reader = connection.reader_task
            result = await connection.release()
            assert "payload_ref" not in bridge.writes[0]
            assert "native_swap_release_boundary" not in result
            assert connection.evidence()["native_swap_release_boundary"] is None
        finally:
            await connection.close()
            await _cancel(reader)

    asyncio.run(scenario())


def test_native_release_missing_boundary_is_uncertain_and_not_retried():
    async def scenario():
        binding = _binding()
        bridge = ReleaseReplyBridge(IDENTITY)
        connection = _connection(bridge)
        reader = None
        try:
            connection.start_reader()
            reader = connection.reader_task
            with pytest.raises(sdk.SdkAdapterError) as caught:
                await connection.release(native_swap_binding=binding)
            assert caught.value.code == "uncertain-effect"
            assert connection.released is True
            assert connection.quiescent is False
            assert len(bridge.writes) == 1
        finally:
            await connection.close()
            await _cancel(reader)

    asyncio.run(scenario())


def test_private_release_authorization_duplicate_is_false_and_binder_runs_once():
    async def scenario():
        binding = _binding()
        bridge = QueueBridge()
        calls = []

        async def binder(*args):
            calls.append(args)
            return _authorization(binding, args[3], authorized=True)

        connection = _connection(bridge, callback=binder)
        reader = None
        frame = {
            "type": "native-swap-release-authorize",
            **IDENTITY,
            "validation_id": "validation-1",
            "binding": copy.deepcopy(binding),
        }
        try:
            connection.start_reader()
            reader = connection.reader_task
            await bridge.incoming.put(frame)
            first = await asyncio.wait_for(bridge.outgoing.get(), 1)
            assert first["operation"] == "native-swap-release-authorize-ack"
            assert first["ack"]["authorized"] is True
            await bridge.incoming.put(copy.deepcopy(frame))
            duplicate = await asyncio.wait_for(bridge.outgoing.get(), 1)
            assert duplicate["ack"]["authorized"] is False
            assert duplicate["ack"]["authorization_id"] == first["ack"]["authorization_id"]
            assert len(calls) == 1
            changed = copy.deepcopy(frame)
            changed["validation_id"] = "validation-2"
            await bridge.incoming.put(changed)
            new_id = await asyncio.wait_for(bridge.outgoing.get(), 1)
            assert new_id["ack"]["authorized"] is False
            assert len(calls) == 1
        finally:
            await connection.close()
            await _cancel(reader)

    asyncio.run(scenario())


def test_private_release_authorization_rejects_stale_binding_without_binder():
    async def scenario():
        binding = _binding(runner_incarnation="old-runner")
        bridge = QueueBridge()
        calls = []

        async def binder(*args):
            calls.append(args)
            return _authorization(binding, args[3], authorized=True)

        connection = _connection(bridge, callback=binder)
        reader = None
        try:
            connection.start_reader()
            reader = connection.reader_task
            await bridge.incoming.put(
                {
                    "type": "native-swap-release-authorize",
                    **IDENTITY,
                    "validation_id": "validation-stale",
                    "binding": binding,
                }
            )
            refusal = await asyncio.wait_for(bridge.outgoing.get(), 1)
            assert refusal["ack"]["authorized"] is False
            assert calls == []
        finally:
            await connection.close()
            await _cancel(reader)

    asyncio.run(scenario())


def test_drive_native_release_authorizes_gate_without_prompt():
    async def scenario():
        binding = _binding()
        auth = AuthIPC()
        client = None
        observed = []

        def factory(options):
            nonlocal client
            client = HeldClient(options)
            return client

        controls = asyncio.Queue()
        task = asyncio.create_task(
            sdk.drive_client(
                _spec(),
                controls=controls,
                emit=observed.append,
                client_factory=factory,
                native_swap_release_ipc=auth,
                native_swap_release_identity=IDENTITY,
            )
        )
        try:
            for _ in range(100):
                if any(event.get("type") == "ready-held" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "release", "payload_ref": binding})
            for _ in range(100):
                if any(event.get("type") == "released" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, 1)
            released = next(event for event in observed if event.get("type") == "released")
            assert result["released"] is True
            assert released["native_swap_release_boundary"]["binding"] == binding
            assert released["native_swap_release_boundary"]["gate_watermark"] > 0
            assert len(auth.frames) == 1
            assert client is not None
            assert not any(call[0] == "query" for call in client.calls)
        finally:
            await _cancel(task)

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["false", "timeout", "stale"])
def test_drive_native_release_refuses_without_crossing_gate(mode):
    async def scenario():
        binding = _binding(
            runner_incarnation="old-runner" if mode == "stale" else RUNNER
        )
        auth = AuthIPC(
            authorized=False if mode == "false" else True,
            timeout=mode == "timeout",
        )
        observed = []
        clients = []

        def factory(options):
            value = HeldClient(options)
            clients.append(value)
            return value

        controls = asyncio.Queue()
        task = asyncio.create_task(
            sdk.drive_client(
                _spec(),
                controls=controls,
                emit=observed.append,
                client_factory=factory,
                native_swap_release_ipc=auth,
                native_swap_release_identity=IDENTITY,
            )
        )
        try:
            for _ in range(100):
                if any(event.get("type") == "ready-held" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "release", "payload_ref": binding})
            for _ in range(100):
                if any(event.get("type") == "adapter-error" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, 1)
            assert result["released"] is False
            assert not any(event.get("type") == "released" for event in observed)
            assert all(call[0] != "query" for call in clients[0].calls)
            assert len(auth.frames) == (0 if mode == "stale" else 1)
        finally:
            await _cancel(task)

    asyncio.run(scenario())


def test_drive_native_release_rechecks_identity_after_authorization():
    async def scenario():
        binding = _binding()
        identity = dict(IDENTITY)
        auth = AuthIPC()
        original = auth.request_native_swap_release

        async def mutate_then_authorize(frame):
            identity["runner_instance_id"] = "replacement-runner"
            return await original(frame)

        auth.request_native_swap_release = mutate_then_authorize
        observed = []

        def factory(options):
            return HeldClient(options)

        controls = asyncio.Queue()
        task = asyncio.create_task(
            sdk.drive_client(
                _spec(),
                controls=controls,
                emit=observed.append,
                client_factory=factory,
                native_swap_release_ipc=auth,
                native_swap_release_identity=identity,
            )
        )
        try:
            for _ in range(100):
                if any(event.get("type") == "ready-held" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "release", "payload_ref": binding})
            for _ in range(100):
                if any(event.get("type") == "adapter-error" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, 1)
            assert result["released"] is False
            assert not any(event.get("type") == "released" for event in observed)
            assert len(auth.frames) == 1
        finally:
            await _cancel(task)

    asyncio.run(scenario())


def test_adapter_binder_is_private_and_cannot_change_after_open():
    adapter = sdk.SdkRunnerAdapter()

    def callback(*args):
        return None

    adapter.bind_native_swap_release(callback)
    assert adapter._native_swap_release is callback
    adapter._connections[PARTICIPANT] = object()
    with pytest.raises(sdk.SdkAdapterError) as caught:
        adapter.bind_native_swap_release(callback)
    assert caught.value.code == "busy"


def test_adapter_native_swap_target_rejects_unbound_release_before_wire():
    async def scenario():
        fingerprint = {
            "lineage_context": copy.deepcopy(CONTEXT),
            "native_config": {"native_swap_target": True},
        }
        bridge = ReleaseReplyBridge(IDENTITY)
        connection = _connection(bridge, spec=_spec(fingerprint=fingerprint))
        try:
            with pytest.raises(sdk.SdkAdapterError) as caught:
                await connection.release()
            assert caught.value.code == "unsupported"
            assert bridge.writes == []
            assert connection.released is False
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_native_swap_target_marker_cannot_be_shadowed_by_nested_fingerprint_key():
    async def scenario():
        fingerprint = {
            "lineage_context": copy.deepcopy(CONTEXT),
            "native_config": {"native_swap_target": True},
            # This is an unrelated fingerprint-shaped value.  It must not
            # replace the already-extracted launch fingerprint.
            "fingerprint": {},
        }
        bridge = ReleaseReplyBridge(IDENTITY)
        connection = _connection(bridge, spec=_spec(fingerprint=fingerprint))
        try:
            with pytest.raises(sdk.SdkAdapterError) as caught:
                await connection.release()
            assert caught.value.code == "unsupported"
            assert bridge.writes == []
        finally:
            await connection.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("marker", [False, 1, None, "true"])
def test_native_swap_target_marker_requires_literal_nested_true(marker):
    fingerprint = {
        "lineage_context": copy.deepcopy(CONTEXT),
        "native_config": {"native_swap_target": marker},
    }
    with pytest.raises(sdk.SdkAdapterError) as caught:
        _connection(QueueBridge(), spec=_spec(fingerprint=fingerprint))
    assert caught.value.code == "invalid"


@pytest.mark.parametrize("native_config", [None, [], "malformed"])
def test_native_swap_target_rejects_malformed_native_config(native_config):
    fingerprint = {
        "lineage_context": copy.deepcopy(CONTEXT),
        "native_config": native_config,
    }
    with pytest.raises(sdk.SdkAdapterError) as caught:
        _connection(QueueBridge(), spec=_spec(fingerprint=fingerprint))
    assert caught.value.code == "invalid"


def test_native_swap_target_rejects_top_level_fingerprint_alias():
    fingerprint = {
        "lineage_context": copy.deepcopy(CONTEXT),
        "native_swap_target": True,
    }
    with pytest.raises(sdk.SdkAdapterError) as caught:
        _connection(QueueBridge(), spec=_spec(fingerprint=fingerprint))
    assert caught.value.code == "invalid"


def test_spec_mapping_top_level_marker_alias_is_not_dropped_during_normalization():
    payload = _spec().to_dict()
    payload["native_swap_target"] = True
    adapter = sdk.SdkRunnerAdapter()
    with pytest.raises(sdk.SdkAdapterError) as caught:
        adapter._prepare_spec(PARTICIPANT, payload)
    assert caught.value.code == "invalid"


def test_adapter_unbound_retry_after_bound_attempt_is_fenced():
    async def scenario():
        binding = _binding()
        bridge = ReleaseReplyBridge(IDENTITY)
        connection = _connection(bridge)
        reader = None
        try:
            connection.start_reader()
            reader = connection.reader_task
            # A missing bound receipt is an uncertain native attempt.  The
            # following legacy-shaped release must not cross a second gate.
            with pytest.raises(sdk.SdkAdapterError) as first:
                await connection.release(native_swap_binding=binding)
            assert first.value.code == "uncertain-effect"
            with pytest.raises(sdk.SdkAdapterError) as second:
                await connection.release()
            assert second.value.code == "uncertain-effect"
            assert len(bridge.writes) == 1
        finally:
            await connection.close()
            await _cancel(reader)

    asyncio.run(scenario())


def test_drive_native_swap_target_rejects_omitted_or_null_payload_without_gate():
    async def scenario(payload_present):
        fingerprint = {
            "lineage_context": copy.deepcopy(CONTEXT),
            "native_config": {"native_swap_target": True},
        }
        observed = []
        clients = []

        def factory(options):
            value = HeldClient(options)
            clients.append(value)
            return value

        controls = asyncio.Queue()
        task = asyncio.create_task(
            sdk.drive_client(
                _spec(fingerprint=fingerprint),
                controls=controls,
                emit=observed.append,
                client_factory=factory,
            )
        )
        try:
            for _ in range(100):
                if any(event.get("type") == "ready-held" for event in observed):
                    break
                await asyncio.sleep(0)
            command = {"operation": "release"}
            if payload_present:
                command["payload_ref"] = None
            await controls.put(command)
            for _ in range(100):
                if any(event.get("type") == "adapter-error" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, 1)
            assert result["released"] is False
            assert not any(event.get("type") == "released" for event in observed)
            assert all(call[0] != "query" for call in clients[0].calls)
        finally:
            await _cancel(task)

    asyncio.run(scenario(False))
    asyncio.run(scenario(True))


def test_drive_ordinary_initial_release_without_marker_remains_compatible():
    async def scenario():
        observed = []
        clients = []

        def factory(options):
            value = HeldClient(options)
            clients.append(value)
            return value

        controls = asyncio.Queue()
        task = asyncio.create_task(
            sdk.drive_client(
                _spec(),
                controls=controls,
                emit=observed.append,
                client_factory=factory,
            )
        )
        try:
            for _ in range(100):
                if any(event.get("type") == "ready-held" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "release"})
            for _ in range(100):
                if any(event.get("type") == "released" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, 1)
            assert result["released"] is True
            assert any(event.get("type") == "released" for event in observed)
            assert all(call[0] != "query" for call in clients[0].calls)
        finally:
            await _cancel(task)

    asyncio.run(scenario())


def test_drive_native_swap_reader_eof_refuses_gate_without_authorization_query():
    async def scenario():
        binding = _binding()
        auth = AuthIPC()
        observed = []
        client = None

        def factory(options):
            nonlocal client
            client = HeldClient(options)
            return client

        controls = asyncio.Queue()
        task = asyncio.create_task(
            sdk.drive_client(
                _spec(),
                controls=controls,
                emit=observed.append,
                client_factory=factory,
                native_swap_release_ipc=auth,
                native_swap_release_identity=IDENTITY,
            )
        )
        try:
            for _ in range(100):
                if any(event.get("type") == "ready-held" for event in observed):
                    break
                await asyncio.sleep(0)
            assert client is not None
            await client.events.put(HeldClient.STOP)
            for _ in range(100):
                if task.done() or any(event.get("type") == "adapter-error" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "release", "payload_ref": binding})
            for _ in range(100):
                if any(event.get("type") == "adapter-error" for event in observed):
                    break
                await asyncio.sleep(0)
            assert not any(event.get("type") == "released" for event in observed)
            assert auth.frames == []
            if not task.done():
                await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, 1)
            assert result["released"] is False
        finally:
            await _cancel(task)

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["denied", "timeout"])
def test_drive_native_swap_failed_auth_rejects_later_unbound_release(failure):
    async def scenario():
        binding = _binding()
        fingerprint = {
            "lineage_context": copy.deepcopy(CONTEXT),
            "native_config": {"native_swap_target": True},
        }
        auth = AuthIPC(authorized=False, timeout=failure == "timeout")
        observed = []
        clients = []

        def factory(options):
            value = HeldClient(options)
            clients.append(value)
            return value

        controls = asyncio.Queue()
        task = asyncio.create_task(
            sdk.drive_client(
                _spec(fingerprint=fingerprint),
                controls=controls,
                emit=observed.append,
                client_factory=factory,
                native_swap_release_ipc=auth,
                native_swap_release_identity=IDENTITY,
            )
        )
        try:
            for _ in range(100):
                if any(event.get("type") == "ready-held" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "release", "payload_ref": binding})
            for _ in range(100):
                if any(event.get("type") == "adapter-error" for event in observed):
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "release"})
            for _ in range(100):
                if len([event for event in observed if event.get("type") == "adapter-error"]) >= 2:
                    break
                await asyncio.sleep(0)
            await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, 1)
            assert result["released"] is False
            assert not any(event.get("type") == "released" for event in observed)
            assert len(auth.frames) == 1
            assert all(call[0] != "query" for call in clients[0].calls)
        finally:
            await _cancel(task)

    asyncio.run(scenario())


def test_private_authorization_positive_ack_is_rechecked_after_callback_await():
    async def scenario():
        binding = _binding()
        bridge = QueueBridge()
        callback_started = asyncio.Event()
        continue_callback = asyncio.Event()
        calls = []

        async def binder(*args):
            calls.append(args)
            callback_started.set()
            await continue_callback.wait()
            return _authorization(binding, args[3], authorized=True)

        connection = _connection(bridge, callback=binder)
        reader = None
        frame = {
            "type": "native-swap-release-authorize",
            **IDENTITY,
            "validation_id": "validation-race",
            "binding": copy.deepcopy(binding),
        }
        try:
            connection.start_reader()
            reader = connection.reader_task
            await bridge.incoming.put(frame)
            await asyncio.wait_for(callback_started.wait(), 1)
            connection.released = True
            continue_callback.set()
            acknowledgement = await asyncio.wait_for(bridge.outgoing.get(), 1)
            assert acknowledgement["ack"]["authorized"] is False
            assert connection._native_swap_release_granted is False
            assert len(calls) == 1
        finally:
            await connection.close()
            await _cancel(reader)

    asyncio.run(scenario())


def test_private_authorization_cancellation_tombstones_id_without_recalling_binder():
    async def scenario():
        binding = _binding()
        bridge = QueueBridge()
        callback_started = asyncio.Event()
        calls = []

        async def binder(*args):
            calls.append(args)
            callback_started.set()
            await asyncio.Future()

        connection = _connection(bridge, callback=binder)
        reader = None
        frame = {
            "type": "native-swap-release-authorize",
            **IDENTITY,
            "validation_id": "validation-cancelled",
            "binding": copy.deepcopy(binding),
        }
        try:
            connection.start_reader()
            reader = connection.reader_task
            await bridge.incoming.put(frame)
            await asyncio.wait_for(callback_started.wait(), 1)
            attempt = connection._native_swap_release_tasks["validation-cancelled"]
            attempt.cancel()
            await asyncio.gather(attempt, return_exceptions=True)
            await asyncio.sleep(0)
            await bridge.incoming.put(copy.deepcopy(frame))
            acknowledgement = await asyncio.wait_for(bridge.outgoing.get(), 1)
            assert acknowledgement["ack"]["authorized"] is False
            assert len(calls) == 1
            assert connection._native_swap_release_granted is False
        finally:
            await connection.close()
            await _cancel(reader)

    asyncio.run(scenario())
