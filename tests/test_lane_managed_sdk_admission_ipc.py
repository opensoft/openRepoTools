# SPDX-License-Identifier: Apache-2.0
"""Fake-only native admission transport tests; no SDK/model/account calls."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import lane_managed_sdk as sdk


SESSION = "11111111-1111-4111-8111-111111111111"
IDENTITY = {
    "participant_id": "coordinator", "session_id": SESSION,
    "runner_instance_id": "incarnation-1",
}
CONTEXT = {
    "owner_generation": 7, "lineage_id": "lineage-1",
    "runner_incarnation": IDENTITY["runner_instance_id"],
}
DEFINITION = {
    "description": "A configured reviewer", "prompt": "Read the requested code.",
    "tools": ["Read", "Grep"], "model": "sonnet", "effort": "high",
    "permissionMode": "default",
}
EOF = object()


def spec(**values):
    defaults = {
        "session_id": SESSION, "participant_id": "coordinator",
        "account_email": "fake@example.invalid", "permission_mode": "default",
        "model": "sonnet", "supported_models": ("sonnet",),
        "startup_deadline": 1, "operation_deadline": 1,
        "fingerprint": {
            "lineage_context": copy.deepcopy(CONTEXT),
            "trusted_definitions": {"reviewer": copy.deepcopy(DEFINITION)},
        },
    }
    defaults.update(values)
    return sdk.RunnerSpec(**defaults)


def admission(number=1):
    return {
        **CONTEXT, "admission_id": f"admit-{number}",
        "invocation_id": "durable-send-1", "tool_use_id": f"tool-{number}",
        "trusted_definition_digest": sdk._native_full_digest(DEFINITION),
        "agent_type": "reviewer", "parent": {"session_id": SESSION},
    }


def ack(value, accepted=True):
    return {**{key: value[key] for key in sdk._ADMISSION_ACK_FIELDS}, "accepted": accepted}


def ack_frame(value, **changes):
    frame = {
        **IDENTITY, "operation": "native-admission-ack",
        "admission_id": value["admission_id"], "ack": ack(value),
    }
    frame.update(changes)
    return frame


class QueueBridge:
    """Two bounded fake JSON frame streams without file descriptors."""

    def __init__(self):
        self.incoming = asyncio.Queue()
        self.outgoing = asyncio.Queue()

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


def connection(callback=None):
    value = sdk._RunnerConnection(
        "coordinator", spec(), FakeProcess(), IDENTITY["runner_instance_id"],
        strict_process_group=False, native_admission=callback,
    )
    value.bridge = QueueBridge()
    return value


async def cancel(*tasks):
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def test_parallel_admissions_ack_out_of_order_without_control_consumer():
    async def scenario():
        bridge = QueueBridge()
        controls = asyncio.Queue(maxsize=8)
        channel = sdk._NativeAdmissionIPC(bridge, IDENTITY)
        reader = asyncio.create_task(sdk._queue_controls(bridge, controls, channel))
        requests = [asyncio.create_task(channel.request(admission(i))) for i in (1, 2)]
        try:
            first = await asyncio.wait_for(bridge.outgoing.get(), 1)
            second = await asyncio.wait_for(bridge.outgoing.get(), 1)
            await bridge.incoming.put({"operation": "status"})
            # Nobody drains controls while hooks wait for their own ack.
            await bridge.incoming.put(ack_frame(second["admission"]))
            await bridge.incoming.put(ack_frame(first["admission"]))
            results = await asyncio.wait_for(asyncio.gather(*requests), 1)
            assert [result["admission_id"] for result in results] == ["admit-1", "admit-2"]
            assert all(result["accepted"] is True for result in results)
            assert controls.get_nowait() == {"operation": "status"}
            assert channel.pending == {}
        finally:
            await cancel(reader, *requests)

    asyncio.run(scenario())


@pytest.mark.parametrize("field", (*sdk._ADMISSION_ACK_FIELDS, *IDENTITY, "accepted", "missing"))
def test_ack_requires_exact_correlation_and_boolean(field):
    async def scenario():
        bridge = QueueBridge()
        channel = sdk._NativeAdmissionIPC(bridge, IDENTITY)
        controls = asyncio.Queue(maxsize=8)
        reader = asyncio.create_task(sdk._queue_controls(bridge, controls, channel))
        pending = asyncio.create_task(channel.request(admission()))
        try:
            await asyncio.wait_for(bridge.outgoing.get(), 1)
            frame = ack_frame(admission())
            if field in IDENTITY:
                frame[field] = "wrong"
            elif field == "missing":
                del frame["ack"]["lineage_id"]
            elif field == "accepted":
                frame["ack"][field] = 1
            else:
                frame["ack"][field] = "wrong"
            await bridge.incoming.put(frame)
            with pytest.raises(sdk.SdkAdapterError):
                await asyncio.wait_for(pending, 1)
            assert channel.error is not None
        finally:
            await cancel(reader, pending)

    asyncio.run(scenario())


@pytest.mark.parametrize("terminal", ["eof", "timeout", "unknown-ack", "overflow"])
def test_missing_ack_fails_all_waiters_closed(monkeypatch, terminal):
    monkeypatch.setattr(sdk, "_NATIVE_ADMISSION_DEADLINE", 0.03)

    async def scenario():
        bridge = QueueBridge()
        channel = sdk._NativeAdmissionIPC(bridge, IDENTITY)
        controls = asyncio.Queue(maxsize=2)
        reader = asyncio.create_task(sdk._queue_controls(bridge, controls, channel))
        pending = [asyncio.create_task(channel.request(admission(i))) for i in (1, 2)]
        try:
            for _ in pending:
                await asyncio.wait_for(bridge.outgoing.get(), 1)
            if terminal == "eof":
                await bridge.incoming.put(EOF)
            elif terminal == "unknown-ack":
                await bridge.incoming.put(ack_frame(admission(99)))
            elif terminal == "overflow":
                for _ in range(3):
                    await bridge.incoming.put({"operation": "status"})
            results = await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), 1)
            assert all(isinstance(result, sdk.SdkAdapterError) for result in results)
            assert channel.pending == {}
        finally:
            await cancel(reader, *pending)

    asyncio.run(scenario())


def test_correlated_refusal_is_never_success():
    async def scenario():
        bridge = QueueBridge()
        channel = sdk._NativeAdmissionIPC(bridge, IDENTITY)
        pending = asyncio.create_task(channel.request(admission()))
        try:
            await asyncio.wait_for(bridge.outgoing.get(), 1)
            channel.receive(ack_frame(admission(), ack=ack(admission(), accepted=False)))
            assert (await asyncio.wait_for(pending, 1))["accepted"] is False
        finally:
            await cancel(pending)

    asyncio.run(scenario())


def test_ack_followed_by_eof_cannot_release_a_waiting_hook():
    async def scenario():
        bridge = QueueBridge()
        channel = sdk._NativeAdmissionIPC(bridge, IDENTITY)
        pending = asyncio.create_task(channel.request(admission()))
        try:
            await asyncio.wait_for(bridge.outgoing.get(), 1)
            channel.receive(ack_frame(admission()))
            channel.close()
            with pytest.raises(sdk.SdkAdapterError, match="closed"):
                await pending
        finally:
            await cancel(pending)

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["missing", "none", "exception", "wrong", "boolean", "refusal", "timeout"])
def test_adapter_callback_failure_returns_strict_refusal(monkeypatch, mode):
    monkeypatch.setattr(sdk, "_NATIVE_ADMISSION_DEADLINE", 0.03)

    async def callback(value):
        if mode == "none":
            return None
        if mode == "exception":
            raise RuntimeError("private failure details")
        if mode == "wrong":
            return {**ack(value), "invocation_id": "other"}
        if mode == "boolean":
            return {**ack(value), "accepted": 1}
        if mode == "timeout":
            await asyncio.Event().wait()
        return ack(value, accepted=False)

    async def scenario():
        conn = connection(None if mode == "missing" else callback)
        await conn._answer_native_admission(admission())
        frame = conn.bridge.outgoing.get_nowait()
        assert frame["admission_id"] == "admit-1"
        assert frame["ack"]["accepted"] is False
        assert sdk._admission_ack_matches(frame["ack"], admission())
        assert "private failure details" not in repr(frame)

    asyncio.run(scenario())


def test_persistent_adapter_reader_serves_parallel_intents_without_holding_control_lock():
    async def scenario():
        gates = {name: asyncio.Event() for name in ("admit-1", "admit-2")}
        observed = asyncio.Queue()

        async def callback(value):
            await observed.put(value["admission_id"])
            await gates[value["admission_id"]].wait()
            return ack(value)

        conn = connection(callback)
        conn.start_reader()
        try:
            async with conn._control_lock:
                for i in (1, 2):
                    await conn.bridge.incoming.put({
                        **IDENTITY, "type": "native-admission-intent",
                        "admission_id": f"admit-{i}", "admission": admission(i),
                    })
                assert {await asyncio.wait_for(observed.get(), 1) for _ in range(2)} == set(gates)
                # Receipt of unrelated control replies continues while both
                # callbacks wait, even while send holds the control lock.
                await conn.bridge.incoming.put({**IDENTITY, "type": "status", "request_id": "status-1"})
                event = await asyncio.wait_for(conn.events.get(), 1)
                assert event["request_id"] == "status-1"
                for name in ("admit-2", "admit-1"):
                    gates[name].set()
                    frame = await asyncio.wait_for(conn.bridge.outgoing.get(), 1)
                    assert frame["admission_id"] == name
                    assert frame["ack"]["accepted"] is True
        finally:
            await conn.close()

    asyncio.run(scenario())


def test_adapter_eof_cancels_pending_callback():
    async def scenario():
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def callback(value):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        conn = connection(callback)
        conn.start_reader()
        await conn.bridge.incoming.put({
            **IDENTITY, "type": "native-admission-intent",
            "admission_id": "admit-1", "admission": admission(),
        })
        try:
            await asyncio.wait_for(started.wait(), 1)
            await conn.bridge.incoming.put(EOF)
            await asyncio.wait_for(conn.reader_task, 1)
            assert cancelled.is_set()
            assert conn.bridge.outgoing.empty()
        finally:
            await conn.close()

    asyncio.run(scenario())


def test_sync_callback_and_configuration_mismatch():
    async def scenario():
        observed = []

        def callback(value):
            observed.append(value)
            return ack(value)

        conn = connection(callback)
        await conn._answer_native_admission(admission())
        assert conn.bridge.outgoing.get_nowait()["ack"]["accepted"] is True
        for field in ("owner_generation", "lineage_id", "runner_incarnation", "trusted_definition_digest"):
            changed = admission()
            changed[field] = "wrong"
            await conn._answer_native_admission(changed)
            assert conn.bridge.outgoing.get_nowait()["ack"]["accepted"] is False
        assert len(observed) == 1

    asyncio.run(scenario())


def test_callback_binding_is_explicit_and_precedes_open():
    adapter = sdk.SdkRunnerAdapter()
    callback = lambda value: ack(value)
    assert adapter._native_admission is None
    adapter.bind_native_admission(callback)
    assert adapter._native_admission is callback
    with pytest.raises(sdk.SdkAdapterError, match="callable"):
        adapter.bind_native_admission(None)
    adapter._opening.add("coordinator")
    with pytest.raises(sdk.SdkAdapterError, match="before opening"):
        adapter.bind_native_admission(callback)


@dataclass
class FakeAgentDefinition:
    description: str
    prompt: str
    tools: list[str]
    model: str
    effort: str
    permissionMode: str


def test_options_include_full_immutable_native_definition():
    configured = spec()
    values = sdk.build_sdk_options(configured)
    assert values["agents"] == {"reviewer": DEFINITION}
    options = sdk._normalise_sdk_options(
        SimpleNamespace(ClaudeAgentOptions=SimpleNamespace, AgentDefinition=FakeAgentDefinition), values,
    )
    native = options.agents["reviewer"]
    assert native.prompt == DEFINITION["prompt"]
    assert native.model == "sonnet" and native.effort == "high"
    assert native.tools == ["Read", "Grep"] and native.permissionMode == "default"
    values["agents"]["reviewer"]["tools"].append("Bash")
    assert configured.fingerprint["trusted_definitions"]["reviewer"] == DEFINITION
    assert native.tools == ["Read", "Grep"]
    assert sdk.RunnerSpec.from_mapping(configured.to_dict()).fingerprint == configured.fingerprint


def test_public_definition_facts_match_ledger_and_redact_nested_bodies():
    definition = copy.deepcopy(DEFINITION)
    definition["permissions"] = {
        "allow": ["Read"], "nested": {
            "prompt": "PRIVATE-NESTED-PROMPT", "initial_prompt": "PRIVATE-INITIAL",
            "description": "PRIVATE-DESCRIPTION", "api_key": "PRIVATE-SECRET",
            "mode": "review",
        },
    }
    definition["writable_paths"] = [{"path": ".", "instructions": "PRIVATE-INSTRUCTIONS"}]
    definitions = {"reviewer": definition}
    facts = sdk.native_definition_facts(definitions)
    ledger = sdk.NativeLineageLedger(SESSION, trusted_definitions=definitions)
    assert facts == ledger._definition_facts
    assert set(facts["reviewer"]) == {
        "name", "digest", "tools", "model", "effort", "permissionMode", "permissions", "writable_paths",
    }
    assert facts["reviewer"]["permissions"] == {"allow": ["Read"], "nested": {"mode": "review"}}
    assert facts["reviewer"]["writable_paths"] == [{"path": "."}]
    encoded = json.dumps(definition, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert facts["reviewer"]["digest"] == hashlib.sha256(encoded.encode("ascii")).hexdigest()
    assert "PRIVATE" not in json.dumps(facts)
    changed = copy.deepcopy(definitions)
    changed["reviewer"]["permissions"]["nested"]["prompt"] = "DIFFERENT-PRIVATE-PROMPT"
    assert sdk.native_definition_facts(changed)["reviewer"]["digest"] != facts["reviewer"]["digest"]
    facts["reviewer"]["permissions"]["allow"].append("Write")
    assert definitions["reviewer"]["permissions"]["allow"] == ["Read"]


@pytest.mark.parametrize("bad", [
    float("nan"), float("inf"), float("-inf"), b"private", ("tuple",),
    {"set"}, {1: "non-string-key"}, object(),
])
def test_definition_digest_rejects_non_json_even_in_redacted_fields(bad):
    definition = {**DEFINITION, "prompt": bad}
    with pytest.raises(sdk.SdkAdapterError) as error:
        sdk.native_definition_facts({"reviewer": definition})
    assert error.value.code == "invalid"
    with pytest.raises(sdk.SdkAdapterError):
        sdk._native_full_digest(definition)


def test_definition_digest_never_uses_repr_and_rejects_cycles():
    class Private:
        def __repr__(self):
            raise AssertionError("repr must not be used for a definition")

    with pytest.raises(sdk.SdkAdapterError):
        sdk._native_full_digest({"prompt": Private()})
    cyclic = {}
    cyclic["self"] = cyclic
    with pytest.raises(sdk.SdkAdapterError, match="cycle"):
        sdk._native_full_digest(cyclic)


def test_definition_digest_bounds_canonical_bytes_and_structure(monkeypatch):
    monkeypatch.setattr(sdk, "MAX_NATIVE_DEFINITION_BYTES", 128)
    with pytest.raises(sdk.SdkAdapterError, match="size"):
        sdk._native_full_digest({"prompt": "x" * 129})
    # ASCII escaping counts toward the limit, not only source character count.
    with pytest.raises(sdk.SdkAdapterError, match="size"):
        sdk._native_full_digest({"prompt": "\u2603" * 30})
    # Separate values may fit individually while the aggregate is oversized.
    with pytest.raises(sdk.SdkAdapterError, match="size"):
        sdk._native_full_digest({"a": "a" * 70, "b": "b" * 70})
    nested = None
    for _ in range(sdk.MAX_NATIVE_DEFINITION_DEPTH + 2):
        nested = [nested]
    with pytest.raises(sdk.SdkAdapterError, match="structural"):
        sdk._native_full_digest(nested)
    monkeypatch.setattr(sdk, "MAX_NATIVE_DEFINITION_NODES", 4)
    with pytest.raises(sdk.SdkAdapterError, match="structural"):
        sdk._native_full_digest([1, 2, 3, 4])


@pytest.mark.parametrize("tools", [None, [], "Read", [""], ["x" * 129], ["Read"] * 129, [1], [{"prompt": "PRIVATE"}]])
def test_public_definition_facts_enforce_controller_tool_bounds(tools):
    with pytest.raises(sdk.SdkAdapterError, match="bounded tools"):
        sdk.native_definition_facts({"reviewer": {**DEFINITION, "tools": tools}})


def test_public_definition_facts_name_and_projection_bounds():
    name = "n" * 256
    definition = {
        **DEFINITION, "tools": ["t" * 128] * 128, "model": "m" * 600,
        "permissions": {"rules": ["r" * 600] * 70},
    }
    fact = sdk.native_definition_facts({name: definition})[name]
    assert fact["name"] == name
    assert fact["tools"] == definition["tools"]
    assert len(fact["model"]) == 512
    assert fact["permissions"]["rules"] == ["r" * 512] * 64
    for invalid_name in ("", " " * 3, "n" * 257):
        with pytest.raises(sdk.SdkAdapterError):
            sdk.native_definition_facts({invalid_name: DEFINITION})
    assert sdk.native_definition_facts({}) == {}


def test_standalone_ledger_refuses_long_tool_identity_but_allows_absence():
    definitions = {"reviewer": {**DEFINITION, "tools": ["Read", "x" * 200]}}
    with pytest.raises(sdk.SdkAdapterError, match="bounded tools"):
        sdk.NativeLineageLedger(SESSION, trusted_definitions=definitions)
    with pytest.raises(sdk.SdkAdapterError):
        sdk.native_definition_facts(definitions)
    without_tools = {key: value for key, value in DEFINITION.items() if key != "tools"}
    ledger = sdk.NativeLineageLedger(SESSION, trusted_definitions={"reviewer": without_tools})
    assert ledger._definition_facts["reviewer"]["tools"] == []


@pytest.mark.parametrize("policy", [
    {"permissions": {"allow": ["Bash"]}}, {"writable_paths": ["."]},
    {"permissionMode": "invented-mode"}, {"digest": "only-a-digest"},
])
def test_unsupported_native_policy_refuses_before_launch(policy):
    configured = spec()
    configured.fingerprint["trusted_definitions"]["reviewer"].update(policy)
    with pytest.raises(sdk.SdkAdapterError):
        sdk.build_sdk_options(configured)


def test_distinct_writable_child_cannot_broaden_read_only_coordinator():
    configured = spec(read_only=True, read_only_tools=("Read",))
    configured.fingerprint["trusted_definitions"]["reviewer"]["tools"] = ["Write"]
    with pytest.raises(sdk.SdkAdapterError, match="distinct writable child"):
        sdk.build_sdk_options(configured)


def test_older_sdk_cannot_silently_drop_child_effort_or_permissions():
    @dataclass
    class OldDefinition:
        description: str
        prompt: str
        tools: list[str]
        model: str

    with pytest.raises(sdk.SdkAdapterError, match="preserve"):
        sdk._normalise_sdk_options(
            SimpleNamespace(ClaudeAgentOptions=SimpleNamespace, AgentDefinition=OldDefinition),
            sdk.build_sdk_options(spec()),
        )


@pytest.mark.parametrize("bind", [True, False])
def test_runner_and_adapter_round_trip_hook_during_blocked_query(monkeypatch, bind):
    """Exercise actual runner wiring, hooks and both independent readers."""

    async def scenario():
        observed = []
        hook_results = []
        configured = spec()
        runner_bridge, adapter_bridge = QueueBridge(), QueueBridge()
        runner_bridge.outgoing = adapter_bridge.incoming
        adapter_bridge.outgoing = runner_bridge.incoming

        class FakeClient:
            def __init__(self, options):
                self.options = options
                self.events = asyncio.Queue()

            async def connect(self, prompt=None):
                assert prompt is None
                await self.events.put({
                    "type": "system", "subtype": "init", "session_id": SESSION,
                    "account": {"email": "fake@example.invalid"},
                    "current_permission_mode": "default", "session_state": "idle",
                    "models": ["sonnet"], "model": "sonnet",
                })

            async def receive_messages(self):
                while True:
                    yield await self.events.get()

            async def query(self, prompt):
                pre = self.options.hooks["PreToolUse"][0].hooks[0]
                # query() cannot return until admission is durably acknowledged.
                hook_results.append(await pre({
                    "hook_event_name": "PreToolUse", "session_id": SESSION,
                    "tool_name": "Agent", "tool_use_id": "actual-native-tool-1",
                    "tool_input": {"subagent_type": "reviewer", "prompt": prompt},
                }, "actual-native-tool-1", None))

            async def disconnect(self):
                pass

        fake_sdk = SimpleNamespace(
            __name__="lane_managed_internal_test_sdk",
            ClaudeSDKClient=FakeClient, ClaudeAgentOptions=SimpleNamespace,
            AgentDefinition=FakeAgentDefinition, HookMatcher=SimpleNamespace,
        )

        async def persist(value):
            observed.append(value)
            return ack(value)

        adapter = sdk.SdkRunnerAdapter(lambda _spec: FakeProcess(), strict_process_group=False)
        adapter.bind_native_invocation(
            lambda participant_id, session_id, runner_instance_id, message_id: {
                "bound": True,
                "participant_id": participant_id,
                "session_id": session_id,
                "runner_instance_id": runner_instance_id,
                "message_id": message_id,
            }
        )
        if bind:
            adapter.bind_native_admission(persist)
        original_bridge = sdk._BoundedJsonLines
        # Construction order: adapter connection first, then runner bridge.
        bridges = iter((adapter_bridge, runner_bridge))
        monkeypatch.setattr(sdk, "_BoundedJsonLines", lambda *args, **kwargs: next(bridges))
        monkeypatch.setattr(sdk.os, "environ", dict(sdk.os.environ))
        monkeypatch.setattr(sdk, "_process_evidence", lambda: {
            "process_group_owned": True, "process_start_token": "fake-only",
        })

        async def runner():
            first = await runner_bridge.read()
            return await sdk._runner_async(
                first,
                _test_harness=sdk._internal_test_harness(fake_sdk),
            )

        runner_task = asyncio.create_task(runner())
        try:
            ready = await asyncio.wait_for(adapter.open("coordinator", configured), 2)
            assert ready["runner_instance_id"] == CONTEXT["runner_incarnation"]
            await asyncio.wait_for(adapter.release("coordinator"), 1)
            result = await asyncio.wait_for(adapter.send("coordinator", "durable-send-1", "Inspect this fake task"), 1)
            assert result["accepted"] is True
            if bind:
                assert hook_results == [{}]
                assert len(observed) == 1
                assert observed[0]["invocation_id"] == "durable-send-1"
                assert observed[0]["parent"]["invocation_id"] == "durable-send-1"
                assert observed[0]["runner_incarnation"] == ready["runner_instance_id"]
                assert observed[0]["trusted_definition_digest"] == sdk._native_full_digest(DEFINITION)
            else:
                # Transport acceptance of the parent query is not permission
                # for its Agent tool, nor evidence that a child ran.
                assert observed == []
                assert hook_results[0]["hookSpecificOutput"]["permissionDecision"] == "deny"
        finally:
            await cancel(runner_task)
            for conn in adapter._connections.values():
                await conn.close()
            monkeypatch.setattr(sdk, "_BoundedJsonLines", original_bridge)

    asyncio.run(scenario())
