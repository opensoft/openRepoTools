# SPDX-License-Identifier: Apache-2.0
"""Fake-only native reservation no-send status evidence tests.

The tests exercise the existing authenticated runner ``status`` path.  They
do not call a model, create a public recovery operation, or treat a caller
boolean as transport evidence.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Mapping

import pytest

import lane_managed_sdk as sdk


SESSION = "11111111-1111-4111-8111-111111111111"
PARTICIPANT = "coordinator"
RUNNER = "runner-incarnation-1"
CONTEXT = {
    "owner_generation": 7,
    "lineage_id": "lineage-1",
    "lineage_generation": 3,
    "runner_incarnation": RUNNER,
}


class IdleProcess:
    pid = None
    stdin = stdout = stderr = None

    @staticmethod
    def poll():
        return None


class StatusBridge:
    def __init__(self, *, reader_cursor=11, barrier_overrides=None):
        self.writes: list[dict] = []
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.reader_cursor = reader_cursor
        self.barrier_overrides = dict(barrier_overrides or {})

    async def read(self):
        return copy.deepcopy(await self.incoming.get())

    async def write(self, frame):
        frame = copy.deepcopy(dict(frame))
        self.writes.append(frame)
        operation = frame.get("operation")
        if operation == "prepare-invocation":
            response = _reservation(frame["payload_ref"])
            response.update(
                {
                    "type": "prepare-invocation-ack",
                    "request_id": frame["request_id"],
                    "participant_id": frame["participant_id"],
                    "session_id": frame["session_id"],
                    "runner_instance_id": frame["runner_instance_id"],
                }
            )
            await self.incoming.put(response)
        elif operation == "status":
            await self.incoming.put(_status_event(frame, self))


def _binding(**changes):
    value = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "reservation_version": 1,
        "reservation_id": "reservation-1",
        "operation_id": "operation-1",
        "owner_generation": CONTEXT["owner_generation"],
        "daemon_id": "daemon-1",
        "participant_id": PARTICIPANT,
        "session_id": SESSION,
        "runner_incarnation": RUNNER,
        "lineage_id": CONTEXT["lineage_id"],
        "lineage_generation": CONTEXT["lineage_generation"],
        "prior_invocation_id": "A",
        "next_invocation_id": "B",
        "prior_mailbox_id": "A",
        "next_mailbox_id": "B",
        "prior_watermark": 1,
        "definitions_digest": "1" * 64,
        "permissions_digest": "2" * 64,
        "claim_digest": "3" * 64,
        "binding_digest": "",
    }
    value.update(changes)
    value["binding_digest"] = sdk._native_full_digest(
        {key: item for key, item in value.items() if key != "binding_digest"}
    )
    return value


def _roster():
    return {
        "parent_state": "idle",
        "children": [],
        "pending_admission_ids": [],
        "pending_task_ids": [],
        "parent_active_tool_ids": [],
        "parent_uncertain_tool_ids": [],
        "parent_unresolved_effect_ids": [],
        "descendant_ids": [],
    }


def _reservation(binding=None, *, terminal_watermark=11, next_watermark=12):
    binding = _binding() if binding is None else copy.deepcopy(binding)
    proof = {
        "parent_result": {
            "session_id": SESSION,
            "invocation_id": binding["prior_invocation_id"],
            "message_id": binding["prior_mailbox_id"],
            "result_watermark": 10,
            "reader_drained_watermark": 10,
        },
        "roster": _roster(),
        "roster_digest": "",
        "observation_watermark": terminal_watermark,
        "uncertainty": [],
        "overflow": False,
    }
    proof["roster_digest"] = sdk._native_full_digest(proof["roster"])
    proof["terminal_proof_digest"] = sdk._native_full_digest(proof)
    response = {
        **binding,
        "state": "reserved",
        "terminal_watermark": terminal_watermark,
        "next_watermark": next_watermark,
        "terminal_proof": proof,
        "terminal_proof_digest": proof.pop("terminal_proof_digest"),
    }
    return response


def _status_event(frame, bridge):
    reservation = _reservation_from_connection(frame)
    reader_evidence = {
        "reader_done": False,
        "reader_frame_inflight": False,
        "reader_cursor": bridge.reader_cursor,
        "hooks_inflight": 0,
        "stop_evidence_inflight": 0,
        "coordinator_evidence_inflight": 0,
        "reader_error": False,
        "control_error": False,
        "task_failure": False,
    }
    reader_evidence.update(bridge.barrier_overrides)
    return {
        "type": "status",
        "request_id": frame["request_id"],
        "participant_id": frame["participant_id"],
        "session_id": frame["session_id"],
        "runner_instance_id": frame["runner_instance_id"],
        "ready": True,
        "released": True,
        "active_turn": False,
        "turn_terminal": True,
        "drained": True,
        "participant_quiescent": True,
        "tools_quiescent": True,
        "quiescent": True,
        "lineage": {
            "lineage_context": copy.deepcopy(CONTEXT),
            "current_invocation": reservation["prior_invocation_id"],
            "native_invocation_reservation": copy.deepcopy(reservation),
            "parent_state": {"active": False, "drained": True},
            "pending_admissions": [],
            "pending_tasks": [],
            "quiescent": True,
        },
        "reader_evidence": reader_evidence,
    }


def _reservation_from_connection(frame):
    # The bridge has no connection reference in its callback.  The test
    # replaces this helper with the current reservation before each scenario.
    return copy.deepcopy(_CURRENT_RESERVATION)


_CURRENT_RESERVATION = _reservation()


def _spec():
    return sdk.RunnerSpec(
        session_id=SESSION,
        participant_id=PARTICIPANT,
        account_email="target@example.invalid",
        permission_mode="default",
        model="sonnet",
        supported_models=("sonnet",),
        operation_deadline=0.5,
        startup_deadline=0.5,
        fingerprint={"lineage_context": copy.deepcopy(CONTEXT)},
    )


def _connection(bridge):
    connection = sdk._RunnerConnection(
        PARTICIPANT,
        _spec(),
        IdleProcess(),
        RUNNER,
        strict_process_group=False,
    )
    connection.bridge = bridge
    connection.started = True
    connection.ready = True
    connection.released = True
    connection._initialization.update(
        {
            "account_email": connection.spec.account_email,
            "permission_mode": connection.spec.permission_mode,
            "model": connection.spec.model,
            "fingerprint": copy.deepcopy(connection.spec.fingerprint),
        }
    )
    return connection


def test_status_produces_exact_native_reservation_no_send_receipt():
    async def scenario():
        global _CURRENT_RESERVATION
        binding = _binding()
        _CURRENT_RESERVATION = _reservation(binding)
        bridge = StatusBridge(reader_cursor=11)
        connection = _connection(bridge)
        connection.start_reader()
        try:
            reservation = await connection.prepare_invocation(binding)
            result = await connection.status()
            receipt = result["evidence"]["native_reservation_no_send"]
            assert set(receipt) == set(sdk._NATIVE_RESERVATION_NO_SEND_FIELDS)
            assert receipt["observation_id"] == bridge.writes[-1]["request_id"]
            assert receipt["reservation_binding"] == reservation
            assert receipt["reservation_digest"] == sdk._native_full_digest(reservation)
            assert receipt["observation_watermark"] == 11
            assert receipt["transport_attempted"] is False
            assert receipt["receipt_digest"] == sdk._native_full_digest(
                {
                    key: receipt[key]
                    for key in sdk._NATIVE_RESERVATION_NO_SEND_FIELDS
                    if key != "receipt_digest"
                }
            )
        finally:
            await connection.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "overrides",
    [
        {"reader_cursor": None},
        {"reader_frame_inflight": True},
        {"hooks_inflight": 1},
        {"stop_evidence_inflight": 1},
        {"coordinator_evidence_inflight": 1},
        {"reader_error": True},
        {"control_error": True},
        {"task_failure": True},
    ],
)
def test_status_omits_no_send_receipt_when_reader_or_evidence_barrier_is_unknown(
    overrides,
):
    async def scenario():
        global _CURRENT_RESERVATION
        binding = _binding()
        _CURRENT_RESERVATION = _reservation(binding)
        bridge = StatusBridge(reader_cursor=11, barrier_overrides=overrides)
        connection = _connection(bridge)
        connection.start_reader()
        try:
            await connection.prepare_invocation(binding)
            result = await connection.status()
            assert result["evidence"]["native_reservation_no_send"] is None
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_attempt_marker_precedes_native_b_binder_await_and_blocks_no_send():
    async def scenario():
        global _CURRENT_RESERVATION
        binding = _binding()
        _CURRENT_RESERVATION = _reservation(binding)
        bridge = StatusBridge(reader_cursor=11)
        connection = _connection(bridge)
        connection.start_reader()
        adapter = sdk.SdkRunnerAdapter()
        observed = []

        async def binder(*_args):
            observed.append(connection._reservation_transport_attempts.copy())
            raise sdk.SdkAdapterError("loader-failed", "binder unavailable")

        adapter.bind_native_invocation(binder)
        adapter._connections[PARTICIPANT] = connection
        try:
            await connection.prepare_invocation(binding)
            with pytest.raises(sdk.SdkAdapterError):
                await adapter.send(PARTICIPANT, "B", "payload-B")
            assert observed == [{binding["reservation_id"]: True}]
            result = await connection.status()
            assert result["evidence"]["native_reservation_no_send"] is None
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_no_send_receipt_is_absent_after_exact_reservation_is_consumed():
    async def scenario():
        global _CURRENT_RESERVATION
        binding = _binding()
        _CURRENT_RESERVATION = _reservation(binding)
        bridge = StatusBridge(reader_cursor=11)
        connection = _connection(bridge)
        connection.start_reader()
        try:
            reservation = await connection.prepare_invocation(binding)
            assert connection.consume_invocation_reservation(reservation) is None
            result = await connection.status()
            assert result["evidence"]["native_reservation_no_send"] is None
        finally:
            await connection.close()

    asyncio.run(scenario())


class _RealReaderClient:
    """A continuous fake SDK client for the runner-owned cursor path."""

    STOP = object()

    def __init__(self, options):
        self.options = options
        self.events: asyncio.Queue = asyncio.Queue()

    async def connect(self, prompt=None):
        del prompt
        await self.events.put(
            {
                "type": "system",
                "subtype": "init",
                "session_id": SESSION,
                "account": {"email": "target@example.invalid"},
                "current_permission_mode": "default",
                "session_state": "idle",
                "model": "sonnet",
                "models": ["sonnet"],
            }
        )

    async def receive_messages(self):
        while True:
            event = await self.events.get()
            if event is self.STOP:
                return
            yield event

    async def query(self, payload, message_id):
        assert payload == "prompt-A"
        await self.events.put(
            {
                "type": "result",
                "subtype": "success",
                "session_id": SESSION,
                "message_id": message_id,
                "sequence": 2,
            }
        )

    async def disconnect(self):
        await self.events.put(self.STOP)


def _real_runner_spec(tmp_path):
    return sdk.RunnerSpec(
        profile="team-a",
        participant="coordinator",
        participant_id=PARTICIPANT,
        session_id=SESSION,
        resume=True,
        model="sonnet",
        permission_mode="default",
        worktree=tmp_path,
        account_email="target@example.invalid",
        supported_models=("sonnet",),
        operation_deadline=0.5,
        startup_deadline=0.5,
        read_only=True,
        read_only_tools=("Read",),
        fingerprint={
            "lineage_context": copy.deepcopy(CONTEXT),
            "trusted_definitions": {
                "reviewer": {
                    "description": "authorized native child",
                    "prompt": "inspect the requested files",
                    "tools": ["Read"],
                    "permissionMode": "default",
                }
            },
        },
    )


def _real_ledger():
    ledger = sdk.NativeLineageLedger(
        SESSION,
        trusted_definitions={
            "reviewer": {
                "description": "authorized native child",
                "prompt": "inspect the requested files",
                "tools": ["Read"],
                "permissionMode": "default",
            }
        },
        parent_read_only=True,
        lineage_context=copy.deepcopy(CONTEXT),
        coordinator_enabled=True,
    )
    assert ledger.begin_invocation("A", "A") is None
    assert ledger.mark_released() is None
    assert ledger.note_parent_state(
        active=False, drained=True, invocation_id="A"
    ) is None
    assert ledger.note_parent_result(
        invocation_id="A",
        message_id="A",
        result_watermark=2,
        reader_drained_watermark=2,
    ) is None
    return ledger


def _real_binding():
    ledger = _real_ledger()
    binding = _binding()
    definitions_digest, permissions_digest, claim_digest = (
        ledger._invocation_context_digests()
    )
    binding.update(
        definitions_digest=definitions_digest,
        permissions_digest=permissions_digest,
        claim_digest=claim_digest,
    )
    binding["binding_digest"] = sdk._native_full_digest(
        {
            key: value
            for key, value in binding.items()
            if key != "binding_digest"
        }
    )
    return binding


async def _wait_for_runner_event(observed, predicate):
    deadline = asyncio.get_running_loop().time() + 1
    while asyncio.get_running_loop().time() < deadline:
        if any(
            isinstance(event, Mapping) and predicate(event) for event in observed
        ):
            return
        await asyncio.sleep(0)
    raise AssertionError("timed out waiting for runner event")


def test_real_runner_result_prepare_status_publishes_sealed_reader_cursor(tmp_path):
    """The real runner path accepts no-send proof after a terminal prepare.

    The prepare checkpoint allocates a cursor in the persistent-reader domain.
    STATUS must report that same committed cursor; a status-local increment or
    a fixture-provided cursor would not exercise this producer boundary.
    """

    async def scenario():
        spec = _real_runner_spec(tmp_path)
        controls: asyncio.Queue = asyncio.Queue()
        observed = []
        clients = []

        def factory(options):
            client = _RealReaderClient(options)
            clients.append(client)
            return client

        task = asyncio.create_task(
            sdk.drive_client(
                spec,
                controls=controls,
                emit=observed.append,
                client_factory=factory,
                coordinator_interrupt_identity={
                    "participant_id": PARTICIPANT,
                    "session_id": SESSION,
                    "runner_instance_id": RUNNER,
                },
            )
        )
        try:
            await _wait_for_runner_event(
                observed, lambda event: event.get("type") == "ready-held"
            )
            await controls.put({"operation": "release", "request_id": "release-1"})
            await _wait_for_runner_event(
                observed, lambda event: event.get("type") == "released"
            )
            await controls.put(
                {
                    "operation": "query",
                    "request_id": "query-1",
                    "message_id": "A",
                    "payload_ref": "prompt-A",
                }
            )
            await _wait_for_runner_event(
                observed, lambda event: event.get("type") == "query-dispatched"
            )
            await _wait_for_runner_event(
                observed,
                lambda event: event.get("type") == "result"
                and event.get("message_id") == "A",
            )
            await controls.put(
                {
                    "operation": "prepare-invocation",
                    "request_id": "prepare-1",
                    "payload_ref": _real_binding(),
                }
            )
            await _wait_for_runner_event(
                observed,
                lambda event: event.get("type") == "prepare-invocation-ack",
            )
            prepare_ack = next(
                event
                for event in observed
                if event.get("type") == "prepare-invocation-ack"
            )
            await controls.put({"operation": "status", "request_id": "status-1"})
            await _wait_for_runner_event(
                observed,
                lambda event: event.get("type") == "status"
                and event.get("request_id") == "status-1",
            )
            status = next(
                event
                for event in observed
                if event.get("type") == "status"
                and event.get("request_id") == "status-1"
            )
            reader_evidence = status["reader_evidence"]
            assert reader_evidence["reader_done"] is False
            assert reader_evidence["reader_frame_inflight"] is False
            assert reader_evidence["reader_cursor"] == prepare_ack["terminal_watermark"]
            assert status["lineage"]["native_invocation_reservation"] == {
                key: prepare_ack[key]
                for key in sdk._NATIVE_INVOCATION_RESPONSE_FIELDS
            }
            assert not any(
                event.get("type") == "adapter-error" for event in observed
            )
        finally:
            await controls.put({"operation": "shutdown", "request_id": "shutdown-1"})
            try:
                await asyncio.wait_for(task, timeout=1)
            except asyncio.CancelledError:
                raise
            except Exception:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise
            assert clients

    asyncio.run(scenario())
