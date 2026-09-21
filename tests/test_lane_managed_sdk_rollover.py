# SPDX-License-Identifier: Apache-2.0
"""Fake-only same-runner invocation rollover contract tests.

These tests exercise the adapter boundary only.  They do not authenticate,
contact a model, or establish live runtime capability.  A rollover is a
bounded internal reservation: invocation A must have an adapter-produced
terminal proof before invocation B can consume a mailbox, and the same
runner/connection/release boundary is retained for B and C.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Mapping
from types import SimpleNamespace

import pytest

import lane_managed_sdk as sdk


SESSION = "11111111-1111-4111-8111-111111111111"
RUNNER = "runner-incarnation-1"
OPERATION = "operation-1"
DAEMON = "daemon-1"
LINEAGE = "lineage-1"


class IdleProcess:
    pid = None
    stdin = stdout = stderr = None

    @staticmethod
    def poll():
        return None


class PrepareBridge:
    """A bounded bridge that answers prepare frames from a fixed queue."""

    def __init__(self, replies=()):
        self.writes: list[dict] = []
        self.replies = list(replies)
        self._written = asyncio.Event()

    async def write(self, frame):
        self.writes.append(copy.deepcopy(dict(frame)))
        self._written.set()

    async def read(self):
        await self._written.wait()
        self._written.clear()
        if not self.replies:
            await asyncio.Event().wait()
        reply = self.replies.pop(0)
        if callable(reply):
            reply = reply(self.writes[-1])
        if isinstance(reply, Mapping):
            reply = dict(reply)
            reply.setdefault("request_id", self.writes[-1]["request_id"])
            reply.setdefault("participant_id", self.writes[-1]["participant_id"])
            reply.setdefault("session_id", self.writes[-1]["session_id"])
            reply.setdefault("runner_instance_id", self.writes[-1]["runner_instance_id"])
        return copy.deepcopy(reply)


class ReaderClient:
    """Minimal held client for the persistent-reader checkpoint seam."""

    STOP = object()

    def __init__(self, options, *, emit_result=True):
        self.options = options
        self.emit_result = emit_result
        self.events: asyncio.Queue = asyncio.Queue()
        self.calls: list[tuple] = []

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

    async def receive_messages(self):
        self.calls.append(("receive_messages",))
        while True:
            event = await self.events.get()
            if event is self.STOP:
                return
            yield event

    async def query(self, payload, message_id):
        self.calls.append(("query", payload, message_id))
        if self.emit_result:
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
        self.calls.append(("disconnect",))
        await self.events.put(self.STOP)


class _FakeHookMatcher:
    def __init__(self, matcher=None, hooks=()):
        self.matcher = matcher
        self.hooks = list(hooks)


class _FakeAgentDefinition:
    def __init__(self, **values):
        self.values = dict(values)


class _FakeAgentOptions:
    def __init__(self, **values):
        self.__dict__.update(values)


class KnownChildClient:
    """Fake SDK-shaped client with a real native hook/reader child join."""

    STOP = object()

    def __init__(self, options):
        self.options = options
        self.events: asyncio.Queue = asyncio.Queue()
        self.child_terminal = asyncio.Event()
        self._terminal_task = None
        self.terminal_task_id = "task-A"
        self.calls: list[tuple] = []

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

    async def receive_messages(self):
        self.calls.append(("receive_messages",))
        while True:
            event = await self.events.get()
            if event is self.STOP:
                return
            yield event

    async def query(self, payload):
        self.calls.append(("query", payload))
        pre_hook = self.options.hooks["PreToolUse"][0].hooks[0]
        await pre_hook(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "reviewer"},
                "session_id": SESSION,
                "invocation_id": "A",
            },
            "launch-A",
            None,
        )
        await self.events.put(
            {
                "type": "system",
                "subtype": "subagent_start",
                "session_id": SESSION,
                "agent_id": "agent-A",
                "agent_type": "reviewer",
                "tool_use_id": "launch-A",
                "invocation_id": "A",
                "uuid": "child-start-A",
            }
        )
        await self.events.put(
            {
                "type": "system",
                "subtype": "task_started",
                "session_id": SESSION,
                "task_id": "task-A",
                "task_type": "local_agent",
                "agent_id": "agent-A",
                "tool_use_id": "launch-A",
                "invocation_id": "A",
                "uuid": "task-start-A",
            }
        )
        # Deliberately publish the parent result while the known child is
        # still active.  The terminal notification is released separately so
        # the test proves the reader remains busy until that joined child is
        # complete, rather than treating the result as quiet-time authority.
        await self.events.put(
            {
                "type": "result",
                "subtype": "success",
                "session_id": SESSION,
                "message_id": "A",
                "sequence": 4,
            }
        )
        post_hook = self.options.hooks["PostToolUse"][0].hooks[0]
        await post_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Agent",
                "session_id": SESSION,
                "invocation_id": "A",
            },
            "launch-A",
            None,
        )
        self._terminal_task = asyncio.create_task(self._publish_child_terminal())

    async def _publish_child_terminal(self):
        await self.child_terminal.wait()
        await self.events.put(
            {
                "type": "system",
                "subtype": "task_notification",
                "session_id": SESSION,
                "task_id": self.terminal_task_id,
                "task_type": "local_agent",
                "agent_id": "agent-A",
                "tool_use_id": "launch-A",
                "invocation_id": "A",
                "status": "completed",
                "authoritative": True,
                "uuid": "task-complete-A",
            }
        )

    async def disconnect(self):
        self.calls.append(("disconnect",))
        self.child_terminal.set()
        if self._terminal_task is not None:
            await self._terminal_task
        await self.events.put(self.STOP)


def _spec(tmp_path, **overrides):
    values = {
        "profile": "team-a",
        "participant": "coordinator",
        "participant_id": "coordinator",
        "session_id": SESSION,
        "resume": True,
        "model": "sonnet",
        "permission_mode": "default",
        "worktree": tmp_path,
        "account_email": "fake@example.invalid",
        "supported_models": ("sonnet",),
        "operation_deadline": 0.2,
        "startup_deadline": 0.2,
        "fingerprint": {
            "lineage_context": {
                "owner_generation": 7,
                "lineage_id": LINEAGE,
                "lineage_generation": 3,
                "runner_incarnation": RUNNER,
            },
            "trusted_definitions": {
                "reviewer": {
                    "description": "authorized native child",
                    "prompt": "inspect the requested files",
                    "tools": ["Read"],
                    "permissionMode": "default",
                }
            },
        },
    }
    values.update(overrides)
    return sdk.RunnerSpec(**values)


def _binding(*, prior="A", next_id="B", prior_mailbox=None, next_mailbox=None,
             prior_watermark=10):
    value = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "reservation_version": 1,
        "reservation_id": f"reservation-{next_id}",
        "operation_id": OPERATION,
        "owner_generation": 7,
        "daemon_id": DAEMON,
        "participant_id": "coordinator",
        "session_id": SESSION,
        "runner_incarnation": RUNNER,
        "lineage_id": LINEAGE,
        "lineage_generation": 3,
        "prior_invocation_id": prior,
        "next_invocation_id": next_id,
        "prior_mailbox_id": prior_mailbox or prior,
        "next_mailbox_id": next_mailbox or next_id,
        "prior_watermark": prior_watermark,
        "definitions_digest": "1" * 64,
        "permissions_digest": "2" * 64,
        "claim_digest": "3" * 64,
    }
    value["binding_digest"] = sdk._native_full_digest(value)
    return value


def _terminal_proof(binding, *, terminal_watermark=11, complete=True):
    roster = {
        "parent_state": "idle" if complete else "active",
        "children": [],
        "pending_admission_ids": [],
        "pending_task_ids": [],
        "parent_active_tool_ids": [],
        "parent_uncertain_tool_ids": [],
        "parent_unresolved_effect_ids": [],
        "descendant_ids": [],
    }
    proof = {
        "parent_result": {
            "session_id": SESSION,
            "invocation_id": binding["prior_invocation_id"],
            "message_id": binding["prior_mailbox_id"],
            "result_watermark": terminal_watermark,
            "reader_drained_watermark": terminal_watermark,
        },
        "roster": roster,
        "roster_digest": sdk._native_full_digest(roster),
        "observation_watermark": terminal_watermark,
        "uncertainty": [] if complete else ["incomplete"],
        "overflow": not complete,
    }
    return proof


def _prepare_ack(binding, *, terminal_watermark=11, next_watermark=12,
                 proof=None, state="reserved", **changes):
    value = {
        **binding,
        "type": "prepare-invocation-ack",
        "state": state,
        "terminal_watermark": terminal_watermark,
        "next_watermark": next_watermark,
        "terminal_proof": _terminal_proof(binding, terminal_watermark=terminal_watermark)
        if proof is None else proof,
    }
    value["terminal_proof_digest"] = sdk._native_full_digest(value["terminal_proof"])
    value.update(changes)
    return value


def _binding_with_changes(binding, **changes):
    value = {**binding, **changes}
    value["binding_digest"] = sdk._native_full_digest(
        {key: value[key] for key in value if key != "binding_digest"}
    )
    return value


def _status_event(connection, frame):
    return {
        "type": "status",
        "participant_id": connection.participant_id,
        "session_id": connection.spec.session_id,
        "runner_instance_id": connection.runner_instance_id,
        "request_id": frame["request_id"],
        "ready": True,
        "released": True,
        "quiescent": True,
        "reservation": copy.deepcopy(connection.reservation),
    }


def _real_ledger(*, include_result=True):
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
        lineage_context={
            "owner_generation": 7,
            "lineage_id": LINEAGE,
            "lineage_generation": 3,
            "runner_incarnation": RUNNER,
        },
        coordinator_enabled=True,
    )
    assert ledger.begin_invocation("A", "A") is None
    assert ledger.mark_released() is None
    # Idle/drained state is intentionally insufficient on its own.
    assert ledger.note_parent_state(
        active=False, drained=True, invocation_id="A"
    ) is None
    assert ledger.invocation_reservation is None
    if include_result:
        assert ledger.note_parent_result(
            invocation_id="A",
            message_id="A",
            result_watermark=2,
            reader_drained_watermark=2,
        ) is None
    return ledger


def test_idle_only_parent_observation_cannot_reserve(tmp_path):
    del tmp_path
    ledger = _real_ledger(include_result=False)
    binding = _real_binding(ledger)
    with pytest.raises(sdk.SdkAdapterError) as caught:
        ledger.prepare_invocation_reservation(
            binding,
            participant_id="coordinator",
            tool_evidence=sdk._ToolEvidence(),
        )
    assert caught.value.code == "unsupported"
    assert ledger.invocation_reservation is None


def test_child_task_after_parent_result_blocks_terminal_reservation(tmp_path):
    del tmp_path
    ledger = _real_ledger()
    assert ledger.observe(
        {
            "type": "system",
            "subtype": "task_started",
            "session_id": SESSION,
            "task_id": "queued-child-task",
            "task_type": "local_agent",
            "uuid": "queued-child-event",
        }
    ) is None
    binding = _real_binding(ledger)
    with pytest.raises(sdk.SdkAdapterError) as caught:
        ledger.prepare_invocation_reservation(
            binding,
            participant_id="coordinator",
            tool_evidence=sdk._ToolEvidence(),
        )
    # An admitted-but-unjoined child is an unknown effect, not merely a
    # missing optional proof.  The current invocation and seal remain intact.
    assert caught.value.code == "uncertain-effect"
    assert ledger.current_invocation == "A"
    assert ledger.current_message_id == "A"
    assert ledger._reservation_sealed is False
    assert ledger.invocation_reservation is None


def _real_binding(ledger, *, prior="A", next_id="B", prior_watermark=1):
    binding = _binding(prior=prior, next_id=next_id, prior_watermark=prior_watermark)
    definitions_digest, permissions_digest, claim_digest = ledger._invocation_context_digests()
    binding.update(
        definitions_digest=definitions_digest,
        permissions_digest=permissions_digest,
        claim_digest=claim_digest,
    )
    binding["binding_digest"] = sdk._native_full_digest(
        {key: binding[key] for key in binding if key != "binding_digest"}
    )
    return binding


async def _wait_for_event(observed, predicate):
    deadline = asyncio.get_running_loop().time() + 1
    while asyncio.get_running_loop().time() < deadline:
        if any(isinstance(event, Mapping) and predicate(event) for event in observed):
            return
        await asyncio.sleep(0)
    raise AssertionError("timed out waiting for runner event")


async def _drive_checkpoint_case(tmp_path, *, emit_result=True, follow_up=None):
    spec = _spec(
        tmp_path,
        read_only=True,
        read_only_tools=("Read",),
    )
    clients = []
    observed = []

    def factory(options):
        client = ReaderClient(options, emit_result=emit_result)
        clients.append(client)
        return client

    controls: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        sdk.drive_client(
            spec,
            controls=controls,
            emit=observed.append,
            client_factory=factory,
            coordinator_interrupt_identity={
                "participant_id": "coordinator",
                "session_id": SESSION,
                "runner_instance_id": RUNNER,
            },
        )
    )
    await _wait_for_event(observed, lambda event: event.get("type") == "ready-held")
    await controls.put({"operation": "release", "request_id": "release-1"})
    await _wait_for_event(observed, lambda event: event.get("type") == "released")
    await controls.put(
        {
            "operation": "query",
            "request_id": "query-1",
            "message_id": "A",
            "payload_ref": "prompt-A",
        }
    )
    await _wait_for_event(observed, lambda event: event.get("type") == "query-dispatched")
    if emit_result:
        await _wait_for_event(observed, lambda event: event.get("type") == "result")
    if follow_up is not None:
        await clients[0].events.put(follow_up)
        if follow_up.get("invocation_id") or follow_up.get("message_id"):
            await _wait_for_event(
                observed,
                lambda event: event.get("type") == "adapter-error",
            )
        else:
            await _wait_for_event(
                observed,
                lambda event: event.get("type") == follow_up.get("type")
                and event.get("task_id") == follow_up.get("task_id"),
            )
    binding = _real_binding(_real_ledger())
    await controls.put(
        {
            "operation": "prepare-invocation",
            "request_id": "prepare-1",
            "payload_ref": binding,
        }
    )
    await _wait_for_event(
        observed,
        lambda event: event.get("type") == "prepare-invocation-ack"
        or event.get("type") == "adapter-error",
    )
    await controls.put({"operation": "shutdown", "request_id": "shutdown-1"})
    result = await asyncio.wait_for(task, timeout=1)
    return result, observed


async def _drive_known_child_checkpoint_case(tmp_path, *, stale_child=False):
    spec = _spec(
        tmp_path,
        read_only=True,
        read_only_tools=("Read",),
    )
    clients = []
    observed = []

    class CapturingClient(KnownChildClient):
        def __init__(self, options):
            super().__init__(options)
            if stale_child:
                self.terminal_task_id = "task-A-stale-incarnation"
            clients.append(self)

    sdk_module = SimpleNamespace(
        HookMatcher=_FakeHookMatcher,
        AgentDefinition=_FakeAgentDefinition,
        ClaudeAgentOptions=_FakeAgentOptions,
        ClaudeSDKClient=CapturingClient,
    )

    async def persist_admission(admission):
        return {
            "accepted": True,
            **{
                key: admission[key]
                for key in (
                    "admission_id",
                    "owner_generation",
                    "lineage_id",
                    "runner_incarnation",
                    "invocation_id",
                    "tool_use_id",
                    "trusted_definition_digest",
                )
            },
        }

    controls: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        sdk.drive_client(
            spec,
            controls=controls,
            emit=observed.append,
            sdk_module=sdk_module,
            persist_admission=persist_admission,
            coordinator_interrupt_identity={
                "participant_id": "coordinator",
                "session_id": SESSION,
                "runner_instance_id": RUNNER,
            },
        )
    )
    await _wait_for_event(observed, lambda event: event.get("type") == "ready-held")
    await controls.put({"operation": "release", "request_id": "release-child"})
    await _wait_for_event(observed, lambda event: event.get("type") == "released")
    await controls.put(
        {
            "operation": "query",
            "request_id": "query-child",
            "message_id": "A",
            "payload_ref": "prompt-A",
        }
    )
    await _wait_for_event(observed, lambda event: event.get("type") == "query-dispatched")
    await _wait_for_event(observed, lambda event: event.get("type") == "result")

    binding = _real_binding(_real_ledger())
    await controls.put(
        {
            "operation": "prepare-invocation",
            "request_id": "prepare-child-busy",
            "payload_ref": binding,
        }
    )
    await _wait_for_event(
        observed,
        lambda event: event.get("type") == "adapter-error"
        and event.get("code") == "busy",
    )
    assert not any(
        event.get("type") == "prepare-invocation-ack" for event in observed
    )

    clients[0].child_terminal.set()
    await _wait_for_event(
        observed,
        lambda event: event.get("subtype") == "task_notification"
        and event.get("status") == "completed",
    )
    await controls.put(
        {
            "operation": "prepare-invocation",
            "request_id": "prepare-child-complete",
            "payload_ref": binding,
        }
    )
    if stale_child:
        await _wait_for_event(
            observed,
            lambda event: event.get("type") == "adapter-error",
        )
    else:
        await _wait_for_event(
            observed,
            lambda event: event.get("type") == "prepare-invocation-ack",
        )
    await controls.put({"operation": "shutdown", "request_id": "shutdown-child"})
    result = await asyncio.wait_for(task, timeout=1)
    return result, observed


def test_persistent_reader_allows_joined_child_completion_after_parent_result(tmp_path):
    async def scenario():
        result, observed = await _drive_known_child_checkpoint_case(tmp_path)
        acknowledgement = next(
            event
            for event in observed
            if event.get("type") == "prepare-invocation-ack"
        )
        proof = acknowledgement["terminal_proof"]
        assert result["ok"] is True
        assert len(proof["roster"]["children"]) == 1
        child = proof["roster"]["children"][0]
        assert child["agent_id"] == "agent-A"
        assert child["task_id"] == "task-A"
        assert child["invocation_id"] == "A"
        assert child["status"] == "completed"

    asyncio.run(scenario())


def test_persistent_reader_rejects_stale_child_incarnation_after_parent_result(tmp_path):
    async def scenario():
        _result, observed = await _drive_known_child_checkpoint_case(
            tmp_path, stale_child=True
        )
        refusal = next(
            event
            for event in observed
            if event.get("type") == "adapter-error"
            and event.get("request_id") == "prepare-child-complete"
        )
        assert refusal["code"] in {
            "busy", "uncertain-effect", "stale-generation", "ownership-conflict"
        }
        assert not any(
            event.get("type") == "prepare-invocation-ack" for event in observed
        )

    asyncio.run(scenario())


def test_persistent_reader_result_and_local_checkpoint_produce_reservation(tmp_path):
    async def scenario():
        result, observed = await _drive_checkpoint_case(tmp_path)
        acknowledgement = next(
            event
            for event in observed
            if event.get("type") == "prepare-invocation-ack"
        )
        proof = acknowledgement["terminal_proof"]
        assert proof["parent_result"]["invocation_id"] == "A"
        assert proof["parent_result"]["message_id"] == "A"
        assert proof["parent_result"]["result_watermark"] == 2
        assert proof["parent_result"]["reader_drained_watermark"] > 2
        assert proof["observation_watermark"] == acknowledgement["terminal_watermark"]
        assert result["ok"] is True

    asyncio.run(scenario())


def test_idle_alias_without_correlated_result_cannot_reserve(tmp_path):
    async def scenario():
        _result, observed = await _drive_checkpoint_case(
            tmp_path,
            emit_result=False,
            follow_up={"type": "idle", "session_id": SESSION},
        )
        refusal = next(
            event
            for event in observed
            if event.get("type") == "adapter-error"
        )
        assert refusal["code"] == "unsupported"
        assert not any(
            event.get("type") == "prepare-invocation-ack" for event in observed
        )

    asyncio.run(scenario())


def test_uncorrelated_child_status_after_result_cannot_close_reader_checkpoint(tmp_path):
    async def scenario():
        _result, observed = await _drive_checkpoint_case(
            tmp_path,
            follow_up={
                "type": "idle",
                "session_id": SESSION,
                "task_id": "child-not-correlated",
            },
        )
        refusal = next(
            event
            for event in observed
            if event.get("type") == "adapter-error"
        )
        assert refusal["code"] == "stale-generation"
        assert not any(
            event.get("type") == "prepare-invocation-ack" for event in observed
        )

    asyncio.run(scenario())


def test_old_invocation_drain_alias_is_rejected_as_stale(tmp_path):
    async def scenario():
        with pytest.raises(sdk.SdkAdapterError) as caught:
            await _drive_checkpoint_case(
                tmp_path,
                follow_up={
                    "type": "idle",
                    "session_id": SESSION,
                    "invocation_id": "old-A",
                },
            )
        assert caught.value.code == "stale-generation"

    asyncio.run(scenario())


def test_native_ledger_produces_and_consumes_one_terminal_reservation(tmp_path):
    del tmp_path
    ledger = _real_ledger()
    binding = _real_binding(ledger)
    proof = ledger.prepare_invocation_reservation(
        binding,
        participant_id="coordinator",
        tool_evidence=sdk._ToolEvidence(),
    )
    assert proof["state"] == "reserved"
    assert proof["terminal_watermark"] == 2
    assert proof["next_watermark"] == 3
    assert proof["terminal_proof"]["parent_result"]["message_id"] == "A"
    assert proof["terminal_proof"]["roster"]["children"] == []
    assert ledger.prepare_invocation_reservation(
        binding,
        participant_id="coordinator",
        tool_evidence=sdk._ToolEvidence(),
    ) == proof
    # A valid B reservation must not be consumed while a caller asks for C.
    # This is the refuse-before-mutation fence: the sealed A state remains
    # available for the controller's eventual B commit.
    wrong = ledger.begin_invocation("C", "C", reservation_binding=proof)
    assert isinstance(wrong, sdk.SdkAdapterError)
    assert wrong.code == "stale-generation"
    assert ledger.invocation_reservation == proof
    assert ledger._reservation_sealed is True
    assert ledger.current_invocation == "A"
    assert ledger.current_message_id == "A"
    assert ledger.begin_invocation(
        "B", "B", reservation_binding=proof
    ) is None
    assert ledger.current_invocation == "B"
    assert ledger.invocation_reservation is None
    assert ledger._reservation_sealed is False
    stale = ledger.note_parent_result(
        invocation_id="A",
        message_id="A",
        result_watermark=4,
        reader_drained_watermark=4,
    )
    assert isinstance(stale, sdk.SdkAdapterError)
    assert stale.code == "stale-generation"


def _connection(tmp_path, bridge):
    connection = sdk._RunnerConnection(
        "coordinator", _spec(tmp_path), IdleProcess(), RUNNER,
        strict_process_group=False,
    )
    connection.bridge = bridge
    connection.ready = True
    connection.released = True
    return connection


def test_prepare_invocation_uses_exact_versioned_binding_and_terminal_proof(tmp_path):
    async def scenario():
        binding = _binding(prior="A", next_id="B")
        bridge = PrepareBridge([_prepare_ack(binding)])
        connection = _connection(tmp_path, bridge)
        connection.start_reader()
        try:
            result = await connection.prepare_invocation(binding)
            assert result["state"] == "reserved"
            assert set(binding).issubset(result)
            assert result["terminal_proof"]["parent_result"]["invocation_id"] == "A"
            assert result["terminal_proof"]["parent_result"]["reader_drained_watermark"] == 11
            assert result["terminal_proof"]["roster"]["parent_state"] == "idle"
            assert result["terminal_watermark"] > result["prior_watermark"]
            frame = bridge.writes[0]
            assert frame["operation"] == "prepare-invocation"
            assert frame["type"] == "prepare-invocation"
            assert frame["payload_ref"] == binding
            assert frame["schema"] == 1
            assert frame["request_id"]
        finally:
            await connection.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "change",
    [
        {"prior_invocation_id": "stale-A"},
        {"runner_incarnation": "runner-incarnation-old"},
        {"daemon_id": "daemon-old"},
        {"next_watermark": 10},
        {"state": "busy"},
    ],
)
def test_prepare_invocation_refuses_stale_or_nonterminal_response_before_reservation(
    tmp_path, change
):
    async def scenario():
        binding = _binding()
        response_binding = binding
        if "prior_invocation_id" in change:
            response_binding = _binding(
                prior="stale-A", next_id="B", prior_watermark=binding["prior_watermark"]
            )
        elif "runner_incarnation" in change:
            response_binding = _binding_with_changes(
                binding, runner_incarnation="runner-incarnation-old"
            )
        elif "daemon_id" in change:
            response_binding = _binding_with_changes(binding, daemon_id="daemon-old")
        response = _prepare_ack(response_binding, **change)
        if change == {"state": "busy"}:
            response["terminal_proof"] = _terminal_proof(binding, complete=False)
        bridge = PrepareBridge([response])
        connection = _connection(tmp_path, bridge)
        connection.start_reader()
        try:
            with pytest.raises(sdk.SdkAdapterError):
                await connection.prepare_invocation(binding)
            assert connection.reservation is None
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_prepare_invocation_duplicate_is_idempotent_and_competing_binding_is_refused(tmp_path):
    async def scenario():
        binding = _binding()
        competing = _binding(next_id="C")
        bridge = PrepareBridge([_prepare_ack(binding)])
        connection = _connection(tmp_path, bridge)
        connection.start_reader()
        try:
            first = await connection.prepare_invocation(binding)
            second = await connection.prepare_invocation(binding)
            assert second == first
            assert len(bridge.writes) == 1
            with pytest.raises(sdk.SdkAdapterError):
                await connection.prepare_invocation(competing)
            assert len(bridge.writes) == 1
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_prepare_invocation_rejects_distinct_invocation_and_mailbox_ids(tmp_path):
    async def scenario():
        binding = _binding(next_mailbox="mail-B")
        connection = _connection(tmp_path, PrepareBridge([]))
        try:
            with pytest.raises(sdk.SdkAdapterError):
                await connection.prepare_invocation(binding)
            assert connection.reservation is None
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_prepare_invocation_rejects_partial_native_child_roster(tmp_path):
    async def scenario():
        binding = _binding()
        roster = {
            "parent_state": "idle",
            "children": [{"status": "completed"}],
            "pending_admission_ids": [],
            "pending_task_ids": [],
            "parent_active_tool_ids": [],
            "parent_uncertain_tool_ids": [],
            "parent_unresolved_effect_ids": [],
            "descendant_ids": [],
        }
        proof = _terminal_proof(binding)
        proof["roster"] = roster
        proof["roster_digest"] = sdk._native_full_digest(roster)
        proof_digest = sdk._native_full_digest(proof)
        response = _prepare_ack(binding, proof=proof)
        response["terminal_proof_digest"] = proof_digest
        bridge = PrepareBridge([response])
        connection = _connection(tmp_path, bridge)
        connection.start_reader()
        try:
            with pytest.raises(sdk.SdkAdapterError):
                await connection.prepare_invocation(binding)
            assert connection.reservation is None
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_same_runner_a_to_b_to_c_has_one_connection_and_one_release_boundary(tmp_path):
    async def scenario():
        bindings = [
            _binding(prior="A", next_id="B"),
            _binding(prior="B", next_id="C", prior_watermark=12),
        ]
        bridge = PrepareBridge([_prepare_ack(bindings[0]), _prepare_ack(bindings[1], terminal_watermark=13, next_watermark=14)])
        connection = _connection(tmp_path, bridge)
        connection.start_reader()
        sent = []

        async def native_binder(participant_id, session_id, runner_instance_id, message_id):
            reservation = connection.reservation
            assert reservation is not None
            if message_id not in {"B", "C"}:
                return {
                    "bound": True,
                    "participant_id": participant_id,
                    "session_id": session_id,
                    "runner_instance_id": runner_instance_id,
                    "message_id": message_id,
                }
            return {
                "bound": True,
                "participant_id": participant_id,
                "session_id": session_id,
                "runner_instance_id": runner_instance_id,
                "message_id": message_id,
                "reservation_binding": copy.deepcopy(reservation),
            }

        async def fake_send(message_id, payload_ref):
            sent.append((message_id, payload_ref))
            return {
                "message_id": message_id,
                "accepted": True,
                "ack_kind": "accepted-send",
            }

        connection.send = fake_send
        adapter = sdk.SdkRunnerAdapter()
        adapter.bind_native_invocation(native_binder)
        adapter._connections["coordinator"] = connection
        try:
            await adapter.prepare_invocation("coordinator", bindings[0])
            await adapter.send("coordinator", "B", "payload-B")
            await adapter.prepare_invocation("coordinator", bindings[1])
            await adapter.send("coordinator", "C", "payload-C")
            assert sent == [("B", "payload-B"), ("C", "payload-C")]
            assert connection.released is True
            assert connection.reservation is None
            assert len(bridge.writes) == 2
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_reservation_mismatch_or_ambiguous_send_cannot_replay_mailbox(tmp_path):
    async def scenario():
        binding = _binding()
        bridge = PrepareBridge([
            _prepare_ack(binding),
            lambda frame: _status_event(connection, frame),
        ])
        connection = _connection(tmp_path, bridge)
        connection.start_reader()
        adapter = sdk.SdkRunnerAdapter()
        calls = []

        async def wrong_binder(participant_id, session_id, runner_instance_id, message_id):
            calls.append(message_id)
            return {
                "bound": True,
                "participant_id": participant_id,
                "session_id": session_id,
                "runner_instance_id": runner_instance_id,
                "message_id": message_id,
                "reservation_binding": _binding_with_changes(
                    binding, daemon_id="other-daemon"
                ),
            }

        adapter.bind_native_invocation(wrong_binder)
        adapter._connections["coordinator"] = connection
        try:
            await adapter.prepare_invocation("coordinator", binding)
            with pytest.raises(sdk.SdkAdapterError):
                await adapter.send("coordinator", "B", "payload-B")
            assert calls == ["B"]
            with pytest.raises(sdk.SdkAdapterError):
                await adapter.send("coordinator", "B", "payload-B")
            assert calls == ["B", "B"]
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_status_exposes_only_bounded_observational_reservation(tmp_path):
    async def scenario():
        binding = _binding()
        bridge = PrepareBridge([
            _prepare_ack(binding),
            lambda frame: _status_event(connection, frame),
        ])
        connection = _connection(tmp_path, bridge)
        connection.start_reader()
        try:
            await connection.prepare_invocation(binding)
            result = await connection.status()
            reservation = result["evidence"]["native_invocation_reservation"]
            assert reservation["reservation_id"] == binding["reservation_id"]
            assert reservation["next_mailbox_id"] == binding["next_mailbox_id"]
            assert "payload" not in reservation
            assert "prompt" not in reservation
        finally:
            await connection.close()

    asyncio.run(scenario())
